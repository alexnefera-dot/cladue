<?php

declare(strict_types=1);

namespace YandexSites\Dorgen;

use RuntimeException;
use YandexSites\Http\HttpClient;
use YandexSites\Http\HttpException;

/**
 * Клиент API системы запусков dorgen: выгружает НАШИ запущенные поддомены.
 *
 * Нужен для точного ответа «наш ли это сайт»: метки в HTML и накопленный список доменов угадывают,
 * а здесь список приходит от самой системы запусков. Сверка идёт по БАЗЕ — последним двум меткам
 * хоста (leebet.4916.team → 4916.team): каждая база несёт все бренды, поэтому множества баз хватает.
 *
 * Особенности API, с которыми приходится считаться:
 *   • не больше 28 запросов в минуту — держим паузу DELAY_MS между запросами;
 *   • /v1/subdomains случайно отвечает 500 (бывает до половины запросов) — повторяем ТОТ ЖЕ запрос
 *     с тем же курсором до RETRIES раз с паузой 3–5 с;
 *   • на 429 ждём 60 с и повторяем;
 *   • период длиннее 31 дня режем на куски по 31 дню;
 *   • ~15 тыс. строк в сутки, сырой ответ ~110 МБ — сырой JSON не храним, из каждой строки берём
 *     только нужные поля и отдаём их потоком (Generator), чтобы не собирать всё в память.
 *
 * Ключ берётся из окружения (.env) и НИКОГДА не попадает в лог или в текст ошибки.
 */
final class DorgenClient
{
    public const BASE_ENV = 'DORGEN_BASE';
    public const TOKEN_ENV = 'DORGEN_TOKEN';
    public const DEFAULT_BASE = 'https://dorgen-engine.com';

    /** Максимальная длина одного периода, дней (ограничение API). */
    public const MAX_DAYS = 31;

    /** Строк на страницу. */
    public const LIMIT = 1000;

    /** Пауза между запросами: 28 запросов в минуту — это 2,1 с. */
    private const DELAY_MS = 2100;

    /** Сколько раз повторять запрос, которому ответили 500. */
    private const RETRIES = 15;

    /** @var callable(int):void пауза в миллисекундах (в тестах заменяется на пустую) */
    private $sleep;

    public function __construct(
        private string $token,
        private string $base = self::DEFAULT_BASE,
        private ?HttpClient $http = null,
        ?callable $sleep = null,
    ) {
        $this->base = rtrim($this->base, '/');
        $this->http ??= new HttpClient(120, 'yandex-sites/dorgen');
        $this->sleep = $sleep ?? static function (int $ms): void {
            usleep($ms * 1000);
        };
    }

    /**
     * Клиент по переменным окружения; null — ключ не задан (функция просто не используется).
     */
    public static function fromEnv(?HttpClient $http = null, ?callable $sleep = null): ?self
    {
        $token = trim((string) (getenv(self::TOKEN_ENV) ?: ($_ENV[self::TOKEN_ENV] ?? '')));
        if ($token === '') {
            return null;
        }
        $base = trim((string) (getenv(self::BASE_ENV) ?: ($_ENV[self::BASE_ENV] ?? '')));

        return new self($token, $base !== '' ? $base : self::DEFAULT_BASE, $http, $sleep);
    }

    /**
     * Наши запущенные поддомены за период (включительно), потоком.
     *
     * @return \Generator<int, array{subdomain: string, content_domain_url: string, brand_label: string, pipeline_started: string, recrawl_sent_at: string, content_label: string}>
     */
    public function subdomains(string $dateFrom, string $dateTo): \Generator
    {
        foreach (self::splitPeriod($dateFrom, $dateTo) as [$from, $to]) {
            $cursor = '';
            $first = true;
            do {
                if (!$first) {
                    ($this->sleep)(self::DELAY_MS);
                }
                $first = false;
                $page = $this->page($from, $to, $cursor);
                foreach ($page['data'] as $row) {
                    $item = self::row((array) $row);
                    if ($item !== null) {
                        yield $item;
                    }
                }
                $cursor = $page['next_cursor'];
            } while ($cursor !== '');
        }
    }

    /**
     * Период на куски не длиннее MAX_DAYS дней (границы включительно).
     *
     * @return list<array{0: string, 1: string}>
     */
    public static function splitPeriod(string $dateFrom, string $dateTo): array
    {
        $from = self::day($dateFrom);
        $to = self::day($dateTo);
        if ($from > $to) {
            [$from, $to] = [$to, $from];
        }
        $out = [];
        $cursor = clone $from;
        while ($cursor <= $to) {
            $end = (clone $cursor)->modify('+' . (self::MAX_DAYS - 1) . ' days');
            if ($end > $to) {
                $end = clone $to;
            }
            $out[] = [$cursor->format('Y-m-d'), $end->format('Y-m-d')];
            $cursor = (clone $end)->modify('+1 day');
        }

        return $out;
    }

    /** База (последние две метки хоста): leebet.4916.team → 4916.team. */
    public static function baseOf(string $host): string
    {
        $host = mb_strtolower(trim($host));
        $host = (string) preg_replace('~^www\.~', '', $host);
        $host = trim($host, '.');
        if ($host === '' || !str_contains($host, '.')) {
            return '';
        }
        $parts = explode('.', $host);
        $last = array_slice($parts, -2);

        return implode('.', $last);
    }

    /**
     * Одна страница выдачи API с повторами: 500 — повторяем тот же курсор, 429 — ждём минуту.
     *
     * @return array{data: list<mixed>, next_cursor: string}
     */
    private function page(string $from, string $to, string $cursor): array
    {
        $params = [
            'date_from' => $from,
            'date_to' => $to,
            'date_field' => 'pipeline_started',
            'limit' => (string) self::LIMIT,
        ];
        if ($cursor !== '') {
            $params['cursor'] = $cursor;
        }
        $url = $this->base . '/v1/subdomains?' . http_build_query($params);
        $lastError = '';
        for ($attempt = 0; $attempt <= self::RETRIES; $attempt++) {
            try {
                // Ключ живёт только в заголовке: ни в URL, ни в тексте ошибки его нет.
                $response = $this->http->get($url, ['Authorization' => 'Bearer ' . $this->token]);
            } catch (HttpException $e) {
                $lastError = 'сеть: ' . $e->getMessage();
                ($this->sleep)(self::retryPause());
                continue;
            }
            if ($response->status === 429) {
                $lastError = 'HTTP 429 (слишком часто)';
                ($this->sleep)(60_000);
                continue;
            }
            if ($response->status >= 500) {
                // Известная особенность API: 500 приходит случайно, помогает простой повтор.
                $lastError = 'HTTP ' . $response->status;
                ($this->sleep)(self::retryPause());
                continue;
            }
            if ($response->status === 401 || $response->status === 403) {
                throw new RuntimeException('dorgen: доступ запрещён (HTTP ' . $response->status . ') — проверьте ' . self::TOKEN_ENV . ' в .env');
            }
            if ($response->status !== 200) {
                throw new RuntimeException('dorgen: неожиданный ответ HTTP ' . $response->status);
            }
            $data = json_decode($response->body, true);
            if (!is_array($data) || !isset($data['data']) || !is_array($data['data'])) {
                $lastError = 'ответ не разобран (нет поля data)';
                ($this->sleep)(self::retryPause());
                continue;
            }

            return [
                'data' => array_values($data['data']),
                'next_cursor' => trim((string) ($data['meta']['next_cursor'] ?? '')),
            ];
        }

        throw new RuntimeException(sprintf('dorgen: не удалось получить страницу за %s—%s после %d попыток (%s)', $from, $to, self::RETRIES + 1, $lastError));
    }

    /** Пауза перед повтором: 3–5 секунд, как просит API. */
    private static function retryPause(): int
    {
        return random_int(3000, 5000);
    }

    /**
     * Только нужные поля строки; null — строка без поддомена, её нет смысла хранить.
     *
     * @param array<string, mixed> $row
     * @return array{subdomain: string, content_domain_url: string, brand_label: string, pipeline_started: string, recrawl_sent_at: string, content_label: string}|null
     */
    private static function row(array $row): ?array
    {
        $subdomain = mb_strtolower(trim((string) ($row['subdomain'] ?? '')));
        if ($subdomain === '') {
            return null;
        }
        $base = mb_strtolower(trim((string) ($row['content_domain_url'] ?? '')));
        // Базу API иногда отдаёт адресом целиком — оставляем только хост, а потом две последние метки.
        if (str_contains($base, '//')) {
            $base = (string) parse_url($base, PHP_URL_HOST);
        }
        $base = self::baseOf($base !== '' ? $base : $subdomain);

        return [
            'subdomain' => $subdomain,
            'content_domain_url' => $base,
            'brand_label' => (string) ($row['brand_label'] ?? ''),
            'pipeline_started' => (string) ($row['pipeline_started'] ?? ''),
            'recrawl_sent_at' => (string) ($row['recrawl_sent_at'] ?? ''),
            'content_label' => (string) ($row['content_label'] ?? ''),
        ];
    }

    private static function day(string $date): \DateTimeImmutable
    {
        $d = \DateTimeImmutable::createFromFormat('!Y-m-d', trim($date), new \DateTimeZone('UTC'));
        if ($d === false) {
            throw new \InvalidArgumentException('dorgen: дата должна быть в виде ГГГГ-ММ-ДД, получено «' . $date . '»');
        }

        return $d;
    }
}

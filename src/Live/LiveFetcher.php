<?php

declare(strict_types=1);

namespace YandexSites\Live;

use YandexSites\Config;
use YandexSites\Http\HttpClient;
use YandexSites\Http\HttpException;
use YandexSites\Search\ApiException;
use YandexSites\Search\RawFetcherInterface;
use YandexSites\Support\Logger;

/**
 * Живая выдача yandex.ru: обычные HTTP-запросы к странице поиска
 * с паузами между ними, через список прокси пользователя.
 * Капча не обходится: прокси, получивший капчу, надолго ставится на паузу,
 * а при исчерпании прокси прогон останавливается.
 */
final class LiveFetcher implements RawFetcherInterface
{
    private float $lastRequestAt = 0.0;
    /** @var list<string> */
    private array $userAgents;

    public function __construct(
        private Config $config,
        private HttpClient $http,
        private HtmlResponseParser $parser,
        private ProxyPool $pool,
        private Logger $log,
    ) {
        $agents = array_values(array_filter((array) $config->get('live.user_agents', []), 'is_string'));
        $this->userAgents = $agents !== [] ? $agents : UserAgents::BROWSERS;
    }

    public function fetch(string $query, int $page): string
    {
        $attempts = max(1, (int) $this->config->get('live.attempts', 4));
        $maxWait = max(0, (int) $this->config->get('live.max_wait', 300));
        $url = $this->buildUrl($query, $page);
        $lastError = '';
        $attempt = 0;

        while ($attempt < $attempts) {
            $proxy = $this->pool->next();
            if ($proxy === null) {
                $wait = $this->pool->secondsUntilAvailable();
                if ($wait === null) {
                    throw new ApiException('Все прокси отключены после серии ошибок — живая выдача недоступна', fatal: true);
                }
                if ($wait > $maxWait) {
                    throw new ApiException(sprintf('Все прокси на паузе после капчи или ошибок, ближайший освободится через %d с (live.max_wait = %d)', $wait, $maxWait), fatal: true);
                }
                if ($wait > 0) {
                    $this->log->warn(sprintf('Все прокси на паузе, ждём %d с…', $wait));
                    sleep($wait);
                }
                continue;
            }

            $attempt++;
            $this->throttle($proxy);
            $proxy->requests++;
            $this->log->debug(sprintf('  GET %s через %s', $url, $proxy->label));

            try {
                $response = $this->http->request('GET', $url, $this->headers($proxy, $query, $page), null, [
                    'proxy' => $proxy->url,
                    'cookie_jar' => $this->cookieJar($proxy),
                    'follow' => true,
                    'timeout' => (int) $this->config->get('live.timeout', 25),
                    'verify_ssl' => (bool) $this->config->get('live.verify_ssl', true),
                ]);
            } catch (HttpException $e) {
                $lastError = $e->getMessage();
                $this->pool->fail($proxy, 'error', (int) $this->config->get('live.error_cooldown', 180));
                $this->log->warn(sprintf('%s: %s', $proxy->label, $lastError));
                continue;
            }

            $kind = $this->parser->classify($response->body, $response->finalUrl, $response->status);
            if ($kind === HtmlResponseParser::KIND_SERP || $kind === HtmlResponseParser::KIND_EMPTY) {
                $this->pool->success($proxy);

                return $response->body;
            }
            if ($kind === HtmlResponseParser::KIND_CAPTCHA) {
                $cooldown = (int) $this->config->get('live.captcha_cooldown', 1800);
                $this->pool->fail($proxy, 'captcha', $cooldown);
                $lastError = 'Яндекс показал капчу';
                $this->log->warn(sprintf('%s: Яндекс показал капчу — прокси на паузе %d с', $proxy->label, $cooldown));
                continue;
            }
            $lastError = sprintf('HTTP %d, %s', $response->status, $kind === HtmlResponseParser::KIND_BLOCKED ? 'доступ ограничен' : 'страница не распознана как выдача');
            $this->pool->fail($proxy, 'blocked', (int) $this->config->get('live.error_cooldown', 180));
            $this->log->warn(sprintf('%s: %s', $proxy->label, $lastError));
        }

        throw new ApiException(sprintf('Не удалось получить живую выдачу за %d попыток: %s', $attempts, $lastError !== '' ? $lastError : 'нет доступных прокси'));
    }

    public function buildUrl(string $query, int $page): string
    {
        $params = ['text' => $query];
        $region = (string) $this->config->get('search.region', '');
        if ($region !== '') {
            $params['lr'] = $region;
        }
        if ($page > 0) {
            $params['p'] = (string) $page;
        }

        return $this->baseUrl() . '/search/?' . http_build_query($params, '', '&', PHP_QUERY_RFC3986);
    }

    public function baseUrl(): string
    {
        $domain = trim((string) $this->config->get('live.domain', 'yandex.ru'));
        if (preg_match('~^https?://~i', $domain) !== 1) {
            $domain = 'https://' . $domain;
        }

        return rtrim($domain, '/');
    }

    /**
     * @return array<string, string>
     */
    public function headers(Proxy $proxy, string $query, int $page): array
    {
        $proxy->userAgent ??= $this->userAgents[crc32($proxy->label) % count($this->userAgents)];

        return [
            'User-Agent' => $proxy->userAgent,
            'Accept' => 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language' => 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer' => $page > 0 ? $this->buildUrl($query, $page - 1) : $this->baseUrl() . '/',
        ];
    }

    private function cookieJar(Proxy $proxy): ?string
    {
        if (!$this->config->get('live.cookies', true)) {
            return null;
        }
        $dir = rtrim((string) $this->config->get('live.cookie_dir', sys_get_temp_dir() . '/yandex-sites-cookies'), '/\\');
        if (!is_dir($dir) && !@mkdir($dir, 0777, true) && !is_dir($dir)) {
            return null;
        }

        return $dir . '/' . sha1($proxy->label) . '.txt';
    }

    /**
     * Пауза: между запросами через один прокси — delay_ms плюс случайная добавка до jitter_ms,
     * между любыми запросами — не меньше min_gap_ms.
     */
    private function throttle(Proxy $proxy): void
    {
        $now = microtime(true);
        $wait = 0.0;

        $delay = max(0, (int) $this->config->get('live.delay_ms', 0));
        $jitter = max(0, (int) $this->config->get('live.jitter_ms', 0));
        if ($proxy->lastRequestAt > 0 && $delay + $jitter > 0) {
            $needed = ($delay + ($jitter > 0 ? random_int(0, $jitter) : 0)) / 1000;
            $wait = max($wait, $proxy->lastRequestAt + $needed - $now);
        }
        $gap = max(0, (int) $this->config->get('live.min_gap_ms', 0));
        if ($this->lastRequestAt > 0 && $gap > 0) {
            $wait = max($wait, $this->lastRequestAt + $gap / 1000 - $now);
        }
        if ($wait > 0) {
            usleep((int) ($wait * 1000000));
        }
        $proxy->lastRequestAt = microtime(true);
        $this->lastRequestAt = $proxy->lastRequestAt;
    }
}

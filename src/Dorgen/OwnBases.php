<?php

declare(strict_types=1);

namespace YandexSites\Dorgen;

/**
 * Наши базы из системы запусков dorgen с КЭШЕМ на диске.
 *
 * Сверка «наш ли сайт из выдачи» идёт по БАЗЕ — последним двум меткам хоста (leebet.4916.team →
 * 4916.team). Каждая база несёт все бренды, поэтому множества баз достаточно, а сами поддомены
 * хранить незачем: их ~15 тыс. в сутки, за месяц это сотни мегабайт. В кэше лежат только базы,
 * сколько поддоменов на каждой видели и когда база встретилась впервые.
 *
 * Кэш помнит покрытый период, поэтому следующая выгрузка догружает ТОЛЬКО новые дни, а не всю
 * историю: `refresh()` без дат берёт период от последнего выгруженного дня (с нахлёстом в сутки,
 * чтобы не потерять запуски, доехавшие позже) до сегодня.
 */
final class OwnBases
{
    public const FILE = 'dorgen-bases.json';

    /** Нахлёст в днях при догрузке: строка могла появиться уже после прошлой выгрузки. */
    private const OVERLAP_DAYS = 1;

    public function __construct(private string $file)
    {
    }

    /** Кэш рядом с базой доменов: runs/dorgen-bases.json. */
    public static function inRuns(string $runsDir): self
    {
        return new self(rtrim($runsDir, '/\\') . '/' . self::FILE);
    }

    /**
     * @return array{updated_at: string, date_from: string, date_to: string, bases: array<string, array{subdomains: int, first_seen: string}>}
     */
    public function load(): array
    {
        $data = @json_decode((string) @file_get_contents($this->file), true);
        $bases = [];
        foreach ((array) ($data['bases'] ?? []) as $base => $info) {
            $base = DorgenClient::baseOf((string) $base);
            if ($base === '') {
                continue;
            }
            $bases[$base] = [
                'subdomains' => (int) ($info['subdomains'] ?? 0),
                'first_seen' => (string) ($info['first_seen'] ?? ''),
            ];
        }

        return [
            'updated_at' => (string) ($data['updated_at'] ?? ''),
            'date_from' => (string) ($data['date_from'] ?? ''),
            'date_to' => (string) ($data['date_to'] ?? ''),
            'bases' => $bases,
        ];
    }

    /**
     * Множество баз для сверки: ['4916.team' => true, …].
     *
     * @return array<string, bool>
     */
    public function bases(): array
    {
        return array_map(static fn (): bool => true, $this->load()['bases']);
    }

    public function count(): int
    {
        return count($this->load()['bases']);
    }

    /** Наш ли хост: его база (последние две метки) есть среди наших. */
    public function matches(string $host): bool
    {
        $base = DorgenClient::baseOf($host);

        return $base !== '' && isset($this->load()['bases'][$base]);
    }

    /**
     * С какого дня догружать: следующий после последнего выгруженного (с нахлёстом), либо $fallback.
     */
    public function nextFrom(string $fallback): string
    {
        $to = $this->load()['date_to'];
        if ($to === '') {
            return $fallback;
        }
        $d = \DateTimeImmutable::createFromFormat('!Y-m-d', $to, new \DateTimeZone('UTC'));

        return $d === false ? $fallback : $d->modify('-' . self::OVERLAP_DAYS . ' day')->format('Y-m-d');
    }

    /**
     * Догружает период и сливает его в кэш. Возвращает, сколько строк прочитано, сколько баз стало
     * всего и сколько из них новых.
     *
     * @return array{rows: int, bases: int, new_bases: int, new_base_list: list<string>, date_from: string, date_to: string}
     */
    public function refresh(DorgenClient $client, string $dateFrom, string $dateTo, ?callable $onProgress = null): array
    {
        $state = $this->load();
        $known = $state['bases'];
        $rows = 0;
        $new = [];
        // Прогресс отдаём наружу после каждой страницы: выгрузка идёт минутами, и без него непонятно,
        // сколько ждать. Число баз считаем на ходу — оно и есть полезный результат.
        $onPage = $onProgress === null ? null : static function (array $p) use (&$known, &$new, $onProgress): void {
            $onProgress($p + ['bases' => count($known), 'new_bases' => count($new)]);
        };
        foreach ($client->subdomains($dateFrom, $dateTo, $onPage) as $row) {
            $rows++;
            $base = $row['content_domain_url'];
            if ($base === '') {
                continue;
            }
            if (!isset($known[$base])) {
                $known[$base] = ['subdomains' => 0, 'first_seen' => $row['pipeline_started'] !== '' ? $row['pipeline_started'] : $dateFrom];
                $new[] = $base;
            }
            $known[$base]['subdomains']++;
        }
        ksort($known);
        $state['bases'] = $known;
        $state['updated_at'] = date(DATE_ATOM);
        $state['date_from'] = $state['date_from'] === '' || $dateFrom < $state['date_from'] ? $dateFrom : $state['date_from'];
        $state['date_to'] = $dateTo > $state['date_to'] ? $dateTo : $state['date_to'];
        $this->save($state);

        return [
            'rows' => $rows,
            'bases' => count($known),
            'new_bases' => count($new),
            'new_base_list' => array_slice($new, 0, 50),
            'date_from' => $dateFrom,
            'date_to' => $dateTo,
        ];
    }

    public function clear(): void
    {
        @unlink($this->file);
    }

    /**
     * @param array<string, mixed> $state
     */
    private function save(array $state): void
    {
        @mkdir(dirname($this->file), 0777, true);
        $tmp = $this->file . '.tmp';
        @file_put_contents($tmp, (string) json_encode($state, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));
        @rename($tmp, $this->file);
    }
}

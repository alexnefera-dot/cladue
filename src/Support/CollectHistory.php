<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Filter\Domains;
use YandexSites\Model\Site;

/**
 * История сборов — вкладка «Статистика» в панели.
 *
 * Интересуют ДОРЫ: после каждого сбора дописывается одна запись — дата, сколько доменов отобрано
 * всего, сколько из них сидит на ПОДДОМЕНАХ (это доры сетки) и какой это процент от всей массы,
 * сколько повторов-доров отсеяно как уже собранные раньше и по каким доменным зонам доры разошлись.
 * Зоны считаются ИМЕННО по дорам: зона корневого сайта ничего не говорит о сетке.
 *
 * Файл лежит в `runs/history.json` (эта папка переживает setup.php --update и «очистить базу»),
 * новые записи идут в начало списка, хранится последние LIMIT записей.
 */
final class CollectHistory
{
    public const FILE = 'history.json';

    /** Сколько последних сборов храним. */
    public const LIMIT = 500;

    /**
     * Дор ли это — сайт на поддомене: хост длиннее своего регистрируемого домена
     * (kush.casinozsd.buzz при casinozsd.buzz). `www.` сначала сбрасывается, это не поддомен.
     */
    public static function isDoor(string $host): bool
    {
        $host = Domains::normalize($host);

        return $host !== '' && Domains::registrable($host) !== $host;
    }

    /**
     * Разбор отобранных сайтов: сколько доров, сколько корневых и зоны ДОРОВ.
     *
     * @param array<int|string, Site> $sites
     * @return array{doors: int, roots: int, zones: array<string, int>}
     */
    public static function breakdown(array $sites): array
    {
        $doors = 0;
        $roots = 0;
        $zones = [];
        foreach ($sites as $site) {
            $host = Domains::normalize((string) $site->host);
            if ($host === '') {
                continue;
            }
            if (!self::isDoor($host)) {
                $roots++;
                continue;
            }
            $doors++;
            $zone = Domains::tld($host);
            if ($zone !== '') {
                $zones[$zone] = ($zones[$zone] ?? 0) + 1;
            }
        }
        arsort($zones);

        return ['doors' => $doors, 'roots' => $roots, 'zones' => $zones];
    }

    /**
     * Запись одного сбора.
     *
     * @param array<int|string, Site> $sites отобранные ЭТИМ сбором сайты
     * @param array<string, mixed> $stats RunResult::$stats
     * @param list<string> $seenBefore хосты, отклонённые как «уже в базе» (RunResult::$seenBefore)
     * @return array<string, mixed>
     */
    public static function record(array $sites, array $stats, array $seenBefore = [], bool $resume = false, bool $stopped = false): array
    {
        $breakdown = self::breakdown($sites);
        $repeats = count($seenBefore) > 0 ? count($seenBefore) : (int) (((array) ($stats['rejected'] ?? []))['seen_before'] ?? 0);
        $repeatsDoors = 0;
        foreach ($seenBefore as $host) {
            if (self::isDoor((string) $host)) {
                $repeatsDoors++;
            }
        }

        return [
            'date' => date(DATE_ATOM),
            'sites' => count($sites),
            'doors' => $breakdown['doors'],
            'roots' => $breakdown['roots'],
            // Повторы — домены, уже бывшие в базе пересечений; отдельно считаем, сколько из них доры.
            'repeats' => $repeats,
            'repeats_doors' => $repeatsDoors,
            'zones' => $breakdown['zones'], // зоны ДОРОВ
            'base_domains' => (int) ($stats['base_domains'] ?? 0),
            'resume' => $resume,
            'stopped' => $stopped,
        ];
    }

    /**
     * Доля доров от всей массы отобранного, в процентах с одним знаком.
     */
    public static function percent(int $doors, int $sites): float
    {
        return $sites > 0 ? round($doors * 100 / $sites, 1) : 0.0;
    }

    /**
     * Дописывает запись в начало истории (новые сверху) и обрезает хвост.
     *
     * @param array<string, mixed> $record
     * @return list<array<string, mixed>>
     */
    public static function append(string $runsDir, array $record): array
    {
        $records = self::load($runsDir);
        array_unshift($records, $record);
        $records = array_slice($records, 0, self::LIMIT);
        $file = rtrim($runsDir, '/\\') . '/' . self::FILE;
        @mkdir(dirname($file), 0777, true);
        file_put_contents($file, json_encode($records, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

        return $records;
    }

    /**
     * @return list<array<string, mixed>>
     */
    public static function load(string $runsDir): array
    {
        $file = rtrim($runsDir, '/\\') . '/' . self::FILE;
        if (!is_file($file)) {
            return [];
        }
        $data = json_decode((string) file_get_contents($file), true);
        if (!is_array($data)) {
            return [];
        }
        $out = [];
        foreach ($data as $record) {
            if (is_array($record)) {
                // Записи версии 1.10.0 называли доры «subdomains» — читаем и их.
                $record['doors'] ??= (int) ($record['subdomains'] ?? 0);
                $out[] = $record;
            }
        }

        return $out;
    }

    /**
     * Итог по всем сборам: сколько собрано, сколько доров и их доля, повторы доров, зоны доров.
     *
     * @param list<array<string, mixed>> $records
     * @return array{runs: int, sites: int, doors: int, roots: int, doors_percent: float, repeats: int, repeats_doors: int, zones: array<string, int>, base_domains: int}
     */
    public static function totals(array $records): array
    {
        $out = ['runs' => 0, 'sites' => 0, 'doors' => 0, 'roots' => 0, 'doors_percent' => 0.0, 'repeats' => 0, 'repeats_doors' => 0, 'zones' => [], 'base_domains' => 0];
        foreach ($records as $r) {
            $out['runs']++;
            foreach (['sites', 'doors', 'roots', 'repeats', 'repeats_doors'] as $key) {
                $out[$key] += (int) ($r[$key] ?? 0);
            }
            foreach ((array) ($r['zones'] ?? []) as $zone => $count) {
                $out['zones'][(string) $zone] = ($out['zones'][(string) $zone] ?? 0) + (int) $count;
            }
        }
        arsort($out['zones']);
        $out['doors_percent'] = self::percent($out['doors'], $out['sites']);
        // База доменов — не сумма, а её размер на момент последнего (самого свежего) сбора.
        $out['base_domains'] = (int) ($records[0]['base_domains'] ?? 0);

        return $out;
    }

    /**
     * История в CSV — чтобы открыть в Excel («Скачать CSV» на вкладке статистики).
     * Зоны складываются в одну колонку «ru: 20, com: 15», иначе таблица разъезжается от новых зон.
     *
     * @param list<array<string, mixed>> $records
     */
    public static function csv(array $records, string $delimiter = ';', bool $bom = true): string
    {
        $out = fopen('php://temp', 'w+');
        if ($out === false) {
            return '';
        }
        if ($bom) {
            fwrite($out, "\xEF\xBB\xBF");
        }
        fputcsv($out, ['Дата', 'Собрано доменов', 'Доров (поддоменов)', 'Доля доров, %', 'Повторов доров', 'Повторов всего', 'Зоны доров', 'Всего в базе', 'Продолжение', 'Остановлен'], $delimiter, '"', '');
        foreach ($records as $r) {
            $doors = (int) ($r['doors'] ?? 0);
            $sites = (int) ($r['sites'] ?? 0);
            fputcsv($out, [
                self::dateHuman((string) ($r['date'] ?? '')),
                $sites,
                $doors,
                self::percent($doors, $sites),
                (int) ($r['repeats_doors'] ?? 0),
                (int) ($r['repeats'] ?? 0),
                self::zonesText((array) ($r['zones'] ?? [])),
                (int) ($r['base_domains'] ?? 0),
                ($r['resume'] ?? false) ? 'да' : '',
                ($r['stopped'] ?? false) ? 'да' : '',
            ], $delimiter, '"', '');
        }
        rewind($out);
        $csv = (string) stream_get_contents($out);
        fclose($out);

        return $csv;
    }

    /** «ru: 20, com: 15, net: 3» — зоны по убыванию. */
    public static function zonesText(array $zones, int $limit = 0): string
    {
        arsort($zones);
        if ($limit > 0) {
            $zones = array_slice($zones, 0, $limit, true);
        }
        $parts = [];
        foreach ($zones as $zone => $count) {
            $parts[] = $zone . ': ' . (int) $count;
        }

        return implode(', ', $parts);
    }

    /** 2026-09-15T12:34:56+00:00 → 15.09.2026 12:34. */
    public static function dateHuman(string $iso): string
    {
        $ts = strtotime($iso);

        return $ts === false ? $iso : date('d.m.Y H:i', $ts);
    }
}

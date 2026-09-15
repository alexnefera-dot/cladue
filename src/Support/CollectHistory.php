<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Filter\Domains;
use YandexSites\Model\Site;

/**
 * История сборов — вкладка «Статистика» в панели.
 *
 * После каждого сбора дописывается одна запись: дата, сколько запросов обработано, сколько доменов
 * отобрано, сколько отсеяно как уже собранные раньше («повторы» из базы пересечений), сколько
 * отобранных сидит на ПОДДОМЕНАХ (доры сетки) и сколько корневых, а также разбивка по доменным зонам.
 * Файл лежит в `runs/history.json` (эта папка переживает setup.php --update), новые записи идут в
 * начало списка, хранится последние LIMIT записей — больше пользователю не нужно, а файл читается
 * панелью на каждом открытии вкладки.
 */
final class CollectHistory
{
    public const FILE = 'history.json';

    /** Сколько последних сборов храним. */
    public const LIMIT = 500;

    /**
     * Разбор списка отобранных сайтов: корневые домены, поддомены (доры) и зоны.
     *
     * @param array<int|string, Site> $sites
     * @return array{roots: int, subdomains: int, zones: array<string, int>}
     */
    public static function breakdown(array $sites): array
    {
        $roots = 0;
        $subdomains = 0;
        $zones = [];
        foreach ($sites as $site) {
            $host = Domains::normalize((string) $site->host); // www.example.ru и example.ru — один домен
            if ($host === '') {
                continue;
            }
            // Поддомен — всё, что длиннее регистрируемого домена: kush.casinozsd.buzz при
            // casinozsd.buzz. Именно так в сетке выглядят доры.
            if (Domains::registrable($host) === $host) {
                $roots++;
            } else {
                $subdomains++;
            }
            $zone = Domains::tld($host);
            if ($zone !== '') {
                $zones[$zone] = ($zones[$zone] ?? 0) + 1;
            }
        }
        arsort($zones);

        return ['roots' => $roots, 'subdomains' => $subdomains, 'zones' => $zones];
    }

    /**
     * Запись одного сбора по его результату.
     *
     * @param array<int|string, Site> $sites отобранные ЭТИМ сбором сайты
     * @param array<string, mixed> $stats RunResult::$stats
     * @return array<string, mixed>
     */
    public static function record(array $sites, array $stats, bool $resume = false, bool $stopped = false): array
    {
        $rejected = (array) ($stats['rejected'] ?? []);
        $breakdown = self::breakdown($sites);

        return [
            'date' => date(DATE_ATOM),
            'queries' => (int) ($stats['queries_done'] ?? $stats['queries'] ?? 0),
            'results' => (int) ($stats['results'] ?? 0),
            'sites' => count($sites),
            // Повторы — домены, которые уже были в базе пересечений и потому не взяты второй раз.
            'repeats' => (int) ($rejected['seen_before'] ?? 0),
            'filtered' => array_sum(array_map('intval', $rejected)) - (int) ($rejected['seen_before'] ?? 0),
            'roots' => $breakdown['roots'],
            'subdomains' => $breakdown['subdomains'],
            'zones' => $breakdown['zones'],
            'base_domains' => (int) ($stats['base_domains'] ?? 0),
            'resume' => $resume,
            'stopped' => $stopped,
        ];
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

        return is_array($data) ? array_values(array_filter($data, 'is_array')) : [];
    }

    /**
     * Итог по всем сборам: сколько всего собрано, повторов, доров, и общая разбивка по зонам.
     *
     * @param list<array<string, mixed>> $records
     * @return array{runs: int, queries: int, sites: int, repeats: int, roots: int, subdomains: int, zones: array<string, int>, base_domains: int}
     */
    public static function totals(array $records): array
    {
        $out = ['runs' => 0, 'queries' => 0, 'sites' => 0, 'repeats' => 0, 'roots' => 0, 'subdomains' => 0, 'zones' => [], 'base_domains' => 0];
        foreach ($records as $r) {
            $out['runs']++;
            foreach (['queries', 'sites', 'repeats', 'roots', 'subdomains'] as $key) {
                $out[$key] += (int) ($r[$key] ?? 0);
            }
            foreach ((array) ($r['zones'] ?? []) as $zone => $count) {
                $out['zones'][(string) $zone] = ($out['zones'][(string) $zone] ?? 0) + (int) $count;
            }
        }
        arsort($out['zones']);
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
        fputcsv($out, ['Дата', 'Запросов', 'Собрано доменов', 'Повторов (уже в базе)', 'Отсеяно фильтрами', 'Корневых', 'Поддоменов (доры)', 'Зоны', 'Всего в базе', 'Продолжение', 'Остановлен'], $delimiter, '"', '');
        foreach ($records as $r) {
            fputcsv($out, [
                self::dateHuman((string) ($r['date'] ?? '')),
                (int) ($r['queries'] ?? 0),
                (int) ($r['sites'] ?? 0),
                (int) ($r['repeats'] ?? 0),
                (int) ($r['filtered'] ?? 0),
                (int) ($r['roots'] ?? 0),
                (int) ($r['subdomains'] ?? 0),
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

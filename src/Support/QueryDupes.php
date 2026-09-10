<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Filter\Domains;
use YandexSites\Model\SearchResult;

/**
 * Запросы с одинаковой выдачей: у двух запросов совпал НАБОР сайтов (регистрируемых доменов) в выдаче —
 * позиции не важны. Из 3000 запросов часть даёт ту же выдачу, что и соседи, и тратит лимит источника
 * впустую; панель после сбора предлагает убрать такие дубли из списка запросов (в каждой группе остаётся
 * первый по списку). Данные — сырые результаты сбора (RunResult::$raw) или results.csv прошлого сбора.
 */
final class QueryDupes
{
    /** Список запросов без дублей (по одному в строке) — рядом с результатами сбора. */
    public const UNIQUE_FILE = 'queries-unique.txt';

    /** Группы дублей для просмотра: кто оставлен, кто убран. */
    public const GROUPS_FILE = 'query-dupes.txt';

    /**
     * @param iterable<array{0: string, 1: string}> $rows пары [запрос, хост] — все результаты выдачи
     * @param list<string> $queries исходный список запросов: его порядок решает, кто из дублей остаётся;
     *                              [] — порядок первого появления в $rows
     * @return array{total: int, groups: list<array{kept: string, duplicates: list<string>, sites: int}>,
     *               duplicates: list<string>, unique: list<string>, no_results: list<string>}
     */
    public static function find(iterable $rows, array $queries = []): array
    {
        $sets = [];
        $seen = [];
        foreach ($rows as [$query, $host]) {
            $query = trim((string) $query);
            if ($query === '') {
                continue;
            }
            if (!isset($sets[$query])) {
                $sets[$query] = [];
                $seen[] = $query;
            }
            $host = Domains::normalize((string) $host);
            if ($host !== '') {
                $sets[$query][Domains::registrable($host)] = true;
            }
        }
        // Порядок — исходный список; запросы, которых в нём нет (список правили после сбора), идут следом.
        $list = [];
        $inList = [];
        foreach (array_merge($queries, $seen) as $q) {
            $q = trim((string) $q);
            if ($q === '' || str_starts_with($q, '#') || isset($inList[$q])) {
                continue;
            }
            $inList[$q] = true;
            $list[] = $q;
        }

        $byKey = [];
        $noResults = [];
        $total = 0;
        foreach ($list as $q) {
            $domains = array_keys($sets[$q] ?? []);
            if ($domains === []) {
                $noResults[] = $q;
                continue;
            }
            $total++;
            sort($domains, SORT_STRING);
            $byKey[implode("\n", $domains)][] = $q;
        }
        $groups = [];
        $duplicates = [];
        $isDup = [];
        foreach ($byKey as $key => $qs) {
            if (count($qs) < 2) {
                continue;
            }
            $kept = array_shift($qs);
            $groups[] = ['kept' => $kept, 'duplicates' => $qs, 'sites' => substr_count((string) $key, "\n") + 1];
            foreach ($qs as $q) {
                $duplicates[] = $q;
                $isDup[$q] = true;
            }
        }

        return [
            'total' => $total,
            'groups' => $groups,
            'duplicates' => $duplicates,
            'unique' => array_values(array_filter($list, static fn (string $q): bool => !isset($isDup[$q]))),
            'no_results' => $noResults,
        ];
    }

    /**
     * Пары [запрос, хост] из сырых результатов прогона (RunResult::$raw).
     *
     * @param list<array{result: SearchResult}> $raw
     * @return \Generator<int, array{0: string, 1: string}>
     */
    public static function rawRows(array $raw): \Generator
    {
        foreach ($raw as $row) {
            $r = $row['result'] ?? null;
            if ($r instanceof SearchResult) {
                yield [$r->query, $r->host !== '' ? $r->host : Domains::hostFromUrl($r->url)];
            }
        }
    }

    /**
     * Пары [запрос, хост] из results.csv прошлого сбора (BOM и разделитель определяются по заголовку,
     * колонки — по именам query/host), чтобы дубли считались и без нового сбора.
     *
     * @return \Generator<int, array{0: string, 1: string}>
     */
    public static function csvRows(string $file): \Generator
    {
        $fh = is_file($file) ? @fopen($file, 'r') : false;
        if ($fh === false) {
            return;
        }
        try {
            $first = fgets($fh);
            if ($first === false) {
                return;
            }
            $first = (string) preg_replace('/^\xEF\xBB\xBF/', '', $first);
            $delimiter = substr_count($first, ';') >= substr_count($first, ',') ? ';' : ',';
            $header = str_getcsv(rtrim($first, "\r\n"), $delimiter, '"', '');
            $qi = array_search('query', $header, true);
            $hi = array_search('host', $header, true);
            if ($qi === false || $hi === false) {
                return;
            }
            while (($row = fgetcsv($fh, 0, $delimiter, '"', '')) !== false) {
                if (!isset($row[$qi], $row[$hi])) {
                    continue;
                }
                yield [(string) $row[$qi], (string) $row[$hi]];
            }
        } finally {
            fclose($fh);
        }
    }

    /**
     * Короткая сводка для статуса задания и кнопки в панели.
     *
     * @param array{total: int, groups: list<mixed>, duplicates: list<string>, no_results: list<string>} $found
     * @return array{total: int, duplicates: int, groups: int, no_results: int}
     */
    public static function summary(array $found): array
    {
        return [
            'total' => $found['total'],
            'duplicates' => count($found['duplicates']),
            'groups' => count($found['groups']),
            'no_results' => count($found['no_results']),
        ];
    }

    /**
     * Пишет рядом с результатами queries-unique.txt (список без дублей, по одному в строке) и query-dupes.txt
     * (группы: кто оставлен, кто убран; и запросы без результатов).
     *
     * @param array{groups: list<array{kept: string, duplicates: list<string>, sites: int}>, unique: list<string>, no_results: list<string>} $found
     */
    public static function writeFiles(string $dir, array $found): void
    {
        @mkdir($dir, 0777, true);
        file_put_contents($dir . '/' . self::UNIQUE_FILE, $found['unique'] === [] ? '' : implode("\n", $found['unique']) . "\n");
        $lines = ['# Запросы с одинаковой выдачей (тот же набор сайтов, позиции не важны).', '# В каждой группе первый по списку оставлен, остальные — дубли.', ''];
        foreach ($found['groups'] as $g) {
            $lines[] = sprintf('оставлен: %s (сайтов в выдаче: %d)', $g['kept'], $g['sites']);
            foreach ($g['duplicates'] as $q) {
                $lines[] = '  дубль: ' . $q;
            }
            $lines[] = '';
        }
        if ($found['groups'] === []) {
            $lines[] = 'Дублей нет.';
            $lines[] = '';
        }
        if ($found['no_results'] !== []) {
            $lines[] = '# Без результатов в выдаче:';
            foreach ($found['no_results'] as $q) {
                $lines[] = '  ' . $q;
            }
            $lines[] = '';
        }
        file_put_contents($dir . '/' . self::GROUPS_FILE, implode("\n", $lines));
    }
}

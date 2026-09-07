<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Visit\PageVisitor;

/**
 * Убранные из таблицы сайты — СЕРВЕРНЫЙ список (runs/current/removed.json), чтобы удаление было
 * окончательным и сквозным: убранный сайт не возвращается ни на докачке, ни на выгрузке, ни на очистке.
 *
 * При удалении строка сайта уходит из sites.json (и из status.json — таблица обновляется сразу), а папки
 * сайта (страницы по бакетам, превью, очищенный контент) переезжают в runs/current/removed/ с той же
 * структурой; «вернуть все» возвращает и строки, и папки. Новый сбор начинает список заново (clear()).
 * Раньше список жил только в браузере и «подчищался» под текущий статус — на переходных состояниях
 * удаления терялись и убранные сайты всплывали снова.
 */
final class RemovedSites
{
    public const FILE = 'removed.json';
    public const DIR = 'removed';

    /**
     * @return array<string, array{row: ?array, status_row: ?array, paths: list<string>, removed_at: string}>
     */
    public static function all(string $runDir): array
    {
        $data = self::readJson($runDir . '/' . self::FILE);
        $hosts = is_array($data) ? ($data['hosts'] ?? null) : null;

        return is_array($hosts) ? $hosts : [];
    }

    /** @return list<string> */
    public static function hosts(string $runDir): array
    {
        return array_map('strval', array_keys(self::all($runDir)));
    }

    /**
     * Отбрасывает убранные сайты из списка (ключ — хост).
     *
     * @template T
     * @param array<string, T> $sites
     * @return array<string, T>
     */
    public static function filter(string $runDir, array $sites): array
    {
        $removed = self::all($runDir);
        if ($removed === []) {
            return $sites;
        }

        return array_filter($sites, static fn (string $host): bool => !isset($removed[$host]), ARRAY_FILTER_USE_KEY);
    }

    /**
     * Убирает сайты: строки из sites.json/status.json → removed.json, папки → removed/.
     *
     * @param list<string> $hosts
     * @return int сколько строк ушло из sites.json
     */
    public static function remove(string $runDir, array $hosts): int
    {
        $want = [];
        foreach ($hosts as $h) {
            $h = trim((string) $h);
            if ($h !== '') {
                $want[$h] = true;
            }
        }
        if ($want === []) {
            return 0;
        }
        $removed = self::all($runDir);
        $now = date(DATE_ATOM);
        $n = 0;

        $sitesFile = $runDir . '/sites.json';
        $sites = self::readJson($sitesFile);
        if (is_array($sites)) {
            $keep = [];
            foreach ((array) ($sites['sites'] ?? []) as $row) {
                $h = (string) ($row['host'] ?? '');
                if (isset($want[$h])) {
                    $removed[$h] = array_merge(['status_row' => null, 'paths' => []], $removed[$h] ?? [], ['row' => $row, 'removed_at' => $now]);
                    $n++;
                    continue;
                }
                $keep[] = $row;
            }
            $sites['sites'] = $keep;
            self::writeJson($sitesFile, $sites, true);
        }

        // status.json — убираем строки, чтобы таблица обновилась сразу, а не после следующего задания.
        $statusFile = $runDir . '/status.json';
        $status = self::readJson($statusFile);
        if (is_array($status) && is_array($status['sites'] ?? null)) {
            $rows = [];
            foreach ($status['sites'] as $row) {
                $h = (string) ($row['host'] ?? '');
                if (isset($want[$h])) {
                    $removed[$h] = array_merge(['row' => null, 'paths' => [], 'removed_at' => $now], $removed[$h] ?? [], ['status_row' => $row]);
                    continue;
                }
                $rows[] = $row;
            }
            $status['sites'] = $rows;
            self::writeJson($statusFile, $status, false);
        }

        // Запоминаем и хосты, которых не оказалось ни в одном файле, — задание их всё равно не вернёт.
        foreach (array_keys($want) as $h) {
            if (!isset($removed[$h])) {
                $removed[$h] = ['row' => null, 'status_row' => null, 'paths' => [], 'removed_at' => $now];
            }
            $removed[$h]['paths'] = array_values(array_unique(array_merge((array) ($removed[$h]['paths'] ?? []), self::moveDirs($runDir, (string) $h))));
        }
        self::writeJson($runDir . '/' . self::FILE, ['hosts' => $removed], true);

        return $n;
    }

    /**
     * Возвращает убранные сайты (все или указанные) обратно: строки в sites.json/status.json, папки на место.
     *
     * @param list<string>|null $hosts
     * @return int сколько строк вернулось в sites.json
     */
    public static function restore(string $runDir, ?array $hosts = null): int
    {
        $removed = self::all($runDir);
        if ($removed === []) {
            return 0;
        }
        $only = $hosts === null ? null : array_flip(array_map('strval', $hosts));
        $sitesFile = $runDir . '/sites.json';
        $statusFile = $runDir . '/status.json';
        $sites = self::readJson($sitesFile) ?? ['sites' => []];
        if (!is_array($sites['sites'] ?? null)) {
            $sites['sites'] = [];
        }
        $status = self::readJson($statusFile);
        $have = [];
        foreach ($sites['sites'] as $r) {
            $have[(string) ($r['host'] ?? '')] = true;
        }
        $haveStatus = [];
        if (is_array($status) && is_array($status['sites'] ?? null)) {
            foreach ($status['sites'] as $r) {
                $haveStatus[(string) ($r['host'] ?? '')] = true;
            }
        }
        $left = [];
        $n = 0;
        foreach ($removed as $h => $info) {
            $h = (string) $h;
            if ($only !== null && !isset($only[$h])) {
                $left[$h] = $info;
                continue;
            }
            foreach ((array) ($info['paths'] ?? []) as $rel) {
                $from = $runDir . '/' . self::DIR . '/' . $rel;
                $to = $runDir . '/' . $rel;
                if (is_dir($from) && !is_dir($to)) {
                    @mkdir(dirname($to), 0777, true);
                    @rename($from, $to);
                }
            }
            if (is_array($info['row'] ?? null) && !isset($have[$h])) {
                $sites['sites'][] = $info['row'];
                $n++;
            }
            if (is_array($status) && is_array($status['sites'] ?? null) && is_array($info['status_row'] ?? null) && !isset($haveStatus[$h])) {
                $status['sites'][] = $info['status_row'];
            }
        }
        self::writeJson($sitesFile, $sites, true);
        if (is_array($status) && is_array($status['sites'] ?? null)) {
            self::writeJson($statusFile, $status, false);
        }
        if ($left === []) {
            @unlink($runDir . '/' . self::FILE);
        } else {
            self::writeJson($runDir . '/' . self::FILE, ['hosts' => $left], true);
        }

        return $n;
    }

    /** Новый сбор — новый список: список убранных и их папки очищаются. */
    public static function clear(string $runDir): void
    {
        @unlink($runDir . '/' . self::FILE);
        self::rmTree($runDir . '/' . self::DIR);
    }

    /**
     * Папки убранных сайтов, вновь появившиеся в pages/preview/content (сайт убрали, пока задание его
     * качало), — уносим в removed/, чтобы они не всплыли в результате.
     */
    public static function sweep(string $runDir): void
    {
        $removed = self::all($runDir);
        if ($removed === []) {
            return;
        }
        $changed = false;
        foreach ($removed as $h => $info) {
            $moved = self::moveDirs($runDir, (string) $h);
            if ($moved !== []) {
                $removed[$h]['paths'] = array_values(array_unique(array_merge((array) ($info['paths'] ?? []), $moved)));
                $changed = true;
            }
        }
        if ($changed) {
            self::writeJson($runDir . '/' . self::FILE, ['hosts' => $removed], true);
        }
    }

    /**
     * Переносит папки сайта (pages/<host>, pages/<бакет>/<host>, preview/…, content/…) в removed/ с той же
     * структурой; возвращает относительные пути перенесённого.
     *
     * @return list<string>
     */
    private static function moveDirs(string $runDir, string $host): array
    {
        $safe = PageVisitor::safeName($host);
        $moved = [];
        foreach (['pages', 'preview', 'content'] as $top) {
            $dirs = array_merge(glob("$runDir/$top/$safe", GLOB_ONLYDIR) ?: [], glob("$runDir/$top/*/$safe", GLOB_ONLYDIR) ?: []);
            foreach ($dirs as $dir) {
                $rel = substr($dir, strlen($runDir) + 1);
                $to = $runDir . '/' . self::DIR . '/' . $rel;
                @mkdir(dirname($to), 0777, true);
                if (is_dir($to)) {
                    self::rmTree($to); // прошлый перенос — заменяем свежим
                }
                if (@rename($dir, $to)) {
                    $moved[] = $rel;
                }
            }
        }

        return $moved;
    }

    private static function readJson(string $file): ?array
    {
        if (!is_file($file)) {
            return null;
        }
        $data = json_decode((string) file_get_contents($file), true);

        return is_array($data) ? $data : null;
    }

    /** Атомарная запись (через временный файл): панель опрашивает статус каждые 1,5 с. */
    private static function writeJson(string $file, array $data, bool $pretty): void
    {
        $flags = JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | ($pretty ? JSON_PRETTY_PRINT : 0);
        $tmp = $file . '.tmp';
        file_put_contents($tmp, json_encode($data, $flags) . ($pretty ? PHP_EOL : ''));
        @rename($tmp, $file);
    }

    private static function rmTree(string $dir): void
    {
        if (!is_dir($dir)) {
            return;
        }
        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $f) {
            if ($f instanceof \SplFileInfo) {
                $f->isDir() ? @rmdir($f->getPathname()) : @unlink($f->getPathname());
            }
        }
        @rmdir($dir);
    }
}

<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * ДИНАМИКА ПО БРЕНДАМ: что было и что стало после пересбора.
 *
 * Вручную ничего фиксировать не нужно — снимок пишется сам в конце каждого сбора. До этого между
 * сборами сохранялся только список сайтов бренда (`SerpAnalysis::index()`), и разница отвечала лишь
 * «появилось 3, пропало 1». А решения принимаются по другим числам: чем забран бренд, кто его
 * забирает, какая у нас доля. Их и хранит этот файл — по строке на бренд на каждый сбор.
 *
 * Лежит в `runs/` рядом с историей сборов (переживает `setup.php --update` и очистку базы).
 * Снимок компактный: только числа, никаких строк выдачи и списков хостов — иначе файл вырастет
 * в мегабайты на первом же сборе из 3000 запросов.
 */
final class SerpHistory
{
    public const FILE = 'serp-history.json';

    /** Сколько сборов помнить: ~25 КБ на сбор из 165 брендов, два месяца ежедневных сборов. */
    public const LIMIT = 60;

    /** Доля считается изменившейся от этого значения в процентных пунктах — ниже это шум округления. */
    public const EPS = 0.1;

    /** «Сила» захвата, чтобы сказать, в какую сторону сдвинулся бренд. */
    private const RANK = ['other' => 0, 'mixed' => 1, 'door' => 2];

    /**
     * Снимок одного сбора: `top` (с какой глубиной топа считали — сравнивать можно только одинаковые)
     * и по бренду только то, по чему принимают решение.
     *
     * @param array<string, mixed> $analysis
     * @return array<string, mixed>
     */
    public static function snapshot(array $analysis, int $top = 10, ?int $at = null): array
    {
        $brands = [];
        foreach ((array) ($analysis['brands'] ?? []) as $brand) {
            $leader = $brand['leader'] ?? null;
            $brands[(string) $brand['key']] = [
                'label' => (string) $brand['label'],
                'cap' => (string) ($brand['capture'] ?? ''),
                'ds' => (float) ($brand['door_share'] ?? 0),
                'sites' => (int) ($brand['sites'] ?? 0),
                'doors' => (int) ($brand['counts']['door'] ?? 0),
                'keys' => (int) ($brand['query_count'] ?? 0),
                'lead' => $leader !== null ? (string) $leader['host'] : '',
                'lt' => $leader !== null ? (string) $leader['type'] : '',
                'ls' => $leader !== null ? (float) $leader['share'] : 0.0,
                'own' => (int) ($brand['own_doors'] ?? 0),
                'os' => (float) ($brand['our_share'] ?? 0),
                'fresh' => (int) ($brand['fresh_sites'] ?? 0),
                // Состав бренда по типам сайтов: по нему видно РОТАЦИЮ — бренд держали доры,
                // стали держать тематические домены. Пять маленьких чисел на бренд.
                'by' => array_map('intval', (array) ($brand['counts'] ?? [])),
            ];
        }

        return [
            'id' => bin2hex(random_bytes(6)),
            'at' => date(DATE_ATOM, $at ?? time()),
            'top' => $top,
            'brands' => $brands,
        ];
    }

    /**
     * Записи, новая первой.
     *
     * @return list<array<string, mixed>>
     */
    public static function load(string $runsDir): array
    {
        $raw = @file_get_contents(rtrim($runsDir, '/') . '/' . self::FILE);
        $data = $raw === false ? null : json_decode($raw, true);

        return is_array($data) ? array_values(array_filter($data, 'is_array')) : [];
    }

    /**
     * Снимок ПРОШЛОГО сбора. Самая свежая запись описывает текущий results.csv (её пишет конец сбора),
     * поэтому сравнивать надо с предыдущей: `$skipLast` для продолженного сбора, который переписывает
     * свою же запись, а не добавляет новую.
     *
     * @return array<string, mixed>|null
     */
    public static function previous(string $runsDir, bool $skipLast = false): ?array
    {
        $records = self::load($runsDir);

        return $records[$skipLast ? 1 : 0] ?? null;
    }

    /**
     * Дописать снимок текущего сбора. Продолжение сбора (`$replaceLast`) переписывает свою же запись:
     * сбор частями — это один сбор, и история не должна распадаться на куски.
     *
     * @param array<string, mixed> $analysis
     * @return array<string, mixed> записанный снимок
     */
    public static function record(string $runsDir, array $analysis, int $top = 10, bool $replaceLast = false, ?int $at = null): array
    {
        $snapshot = self::snapshot($analysis, $top, $at);
        $records = self::load($runsDir);
        if ($replaceLast && $records !== []) {
            array_shift($records);
        }
        array_unshift($records, $snapshot);
        $records = array_slice($records, 0, self::LIMIT);
        $file = rtrim($runsDir, '/') . '/' . self::FILE;
        @file_put_contents($file, (string) json_encode($records, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), LOCK_EX);

        return $snapshot;
    }

    /**
     * ЧТО ИЗМЕНИЛОСЬ: по бренду — было/стало и разница. Бренд, которого в прошлом сборе не было,
     * помечается `is_new`; бренд, который пропал, попадает в `gone` (для него есть только «было»).
     *
     * @param array<string, mixed>|null $prev снимок прошлого сбора
     * @param array<string, mixed> $analysis текущий разбор
     * @return array{brands: array<string, array<string, mixed>>, gone: array<string, array<string, mixed>>}
     */
    public static function compare(?array $prev, array $analysis): array
    {
        $was = (array) ($prev['brands'] ?? []);
        $out = [];
        $seen = [];
        foreach ((array) ($analysis['brands'] ?? []) as $brand) {
            $key = (string) $brand['key'];
            $seen[$key] = true;
            $old = $was[$key] ?? null;
            if ($prev === null) {
                continue; // сравнивать не с чем — пустая разница честнее выдуманной
            }
            $leader = $brand['leader'] ?? null;
            $host = $leader !== null ? (string) $leader['host'] : '';
            $ds = (float) ($brand['door_share'] ?? 0);
            $os = (float) ($brand['our_share'] ?? 0);
            if ($old === null) {
                $out[$key] = ['is_new' => true];

                continue;
            }
            $change = [
                'is_new' => false,
                // РОТАЦИЯ ПО ТИПУ: бренд забирал дор, стал забирать тематический домен (или наоборот).
                // Это не то же, что смена хоста: лидер может смениться внутри одного типа.
                'lt_was' => (string) ($old['lt'] ?? ''),
                'lt_changed' => $leader !== null && ($old['lt'] ?? '') !== ''
                    && (string) $leader['type'] !== (string) $old['lt'],
                'cap_was' => (string) $old['cap'],
                'cap_changed' => (string) $old['cap'] !== (string) ($brand['capture'] ?? ''),
                'cap_dir' => (self::RANK[(string) ($brand['capture'] ?? '')] ?? 0) <=> (self::RANK[(string) $old['cap']] ?? 0),
                'ds_was' => (float) $old['ds'],
                'ds_delta' => round($ds - (float) $old['ds'], 1),
                'lead_was' => (string) $old['lead'],
                'lead_changed' => $host !== '' && (string) $old['lead'] !== '' && $host !== (string) $old['lead'],
                'os_was' => (float) $old['os'],
                'os_delta' => round($os - (float) $old['os'], 1),
                'own_was' => (int) $old['own'],
                'own_delta' => (int) ($brand['own_doors'] ?? 0) - (int) $old['own'],
                'sites_was' => (int) $old['sites'],
                'sites_delta' => (int) ($brand['sites'] ?? 0) - (int) $old['sites'],
            ];
            // Бренд без единого сдвига в список изменений не попадает — иначе фильтр «изменившиеся»
            // покажет всё подряд.
            if ($change['cap_changed'] || $change['lead_changed'] || $change['lt_changed']
                || abs($change['ds_delta']) >= self::EPS || abs($change['os_delta']) >= self::EPS
                || $change['own_delta'] !== 0 || $change['sites_delta'] !== 0) {
                $out[$key] = $change;
            }
        }
        $gone = [];
        foreach ($was as $key => $old) {
            if (!isset($seen[$key])) {
                $gone[(string) $key] = $old;
            }
        }

        return ['brands' => $out, 'gone' => $gone];
    }

    /**
     * Итог по изменениям — для журнала сбора и строки над списком брендов.
     *
     * @param array{brands: array<string, array<string, mixed>>, gone: array<string, mixed>} $changes
     * @return array<string, int>
     */
    public static function summary(array $changes): array
    {
        $out = ['brands' => 0, 'cap_changed' => 0, 'to_doors' => 0, 'from_doors' => 0,
            'lead_changed' => 0, 'type_changed' => 0, 'our_up' => 0, 'our_down' => 0,
            'new' => 0, 'gone' => count($changes['gone'] ?? [])];
        foreach ((array) ($changes['brands'] ?? []) as $c) {
            if (!empty($c['is_new'])) {
                $out['new']++;

                continue;
            }
            $out['brands']++;
            if (!empty($c['cap_changed'])) {
                $out['cap_changed']++;
                $out[((int) $c['cap_dir']) > 0 ? 'to_doors' : 'from_doors']++;
            }
            if (!empty($c['lead_changed'])) {
                $out['lead_changed']++;
            }
            if (!empty($c['lt_changed'])) {
                $out['type_changed']++;
            }
            if ((float) $c['os_delta'] >= self::EPS) {
                $out['our_up']++;
            } elseif ((float) $c['os_delta'] <= -self::EPS) {
                $out['our_down']++;
            }
        }

        return $out;
    }

    /** @param array<string, int> $summary */
    public static function summaryText(array $summary): string
    {
        return sprintf(
            'изменились %d брендов; сменился захват — %d (в сторону доров %d, от доров %d), сменился лидер — %d '
            . '(из них сменился ТИП лидера — %d), наша доля выросла у %d, упала у %d; новых брендов %d, пропало %d',
            (int) $summary['brands'], (int) $summary['cap_changed'], (int) $summary['to_doors'],
            (int) $summary['from_doors'], (int) $summary['lead_changed'], (int) $summary['type_changed'],
            (int) $summary['our_up'], (int) $summary['our_down'], (int) $summary['new'], (int) $summary['gone'],
        );
    }

    /**
     * СВОДКА ПО СБОРАМ для графика: по строке на сбор, в хронологическом порядке (слева направо —
     * как рисуется график), от старых к новым.
     *
     * Средние считаются ПО БРЕНДАМ и без блока «без бренда»: это остаток запросов, а не бренд, и в
     * среднем он сдвигал бы картину тем сильнее, чем больше в списке общетематических ключей.
     *
     * @return list<array<string, mixed>>
     */
    public static function overview(string $runsDir, int $limit = 30): array
    {
        $out = [];
        foreach (array_slice(self::load($runsDir), 0, $limit) as $record) {
            $brands = array_filter(
                (array) ($record['brands'] ?? []),
                static fn ($b, $key): bool => is_array($b) && (string) $key !== '',
                ARRAY_FILTER_USE_BOTH,
            );
            $n = count($brands);
            $cap = ['door' => 0, 'mixed' => 0, 'other' => 0];
            $ds = 0.0;
            $os = 0.0;
            $leadDoors = 0;
            $ownBrands = 0;
            $ownDoors = 0;
            foreach ($brands as $b) {
                $cap[(string) $b['cap']] = ($cap[(string) $b['cap']] ?? 0) + 1;
                $ds += (float) $b['ds'];
                $os += (float) $b['os'];
                $leadDoors += ((string) $b['lt'] === 'door') ? 1 : 0;
                // Наших СТАНОВИТСЯ БОЛЬШЕ или нет — два разных вопроса: сколько наших доров всего
                // и в скольких брендах мы вообще присутствуем. Второе важнее: 50 доров в одном
                // бренде и 50 в пятидесяти — это разные ниши.
                $ownBrands += ((int) $b['own'] > 0) ? 1 : 0;
                $ownDoors += (int) $b['own'];
            }
            $out[] = [
                'at' => (string) ($record['at'] ?? ''),
                'top' => (int) ($record['top'] ?? 0),
                'brands' => $n,
                'ds_avg' => $n > 0 ? round($ds / $n, 1) : 0.0,
                'os_avg' => $n > 0 ? round($os / $n, 1) : 0.0,
                'cap' => $cap,
                'lead_doors' => $leadDoors,
                'own_brands' => $ownBrands,
                'own_doors' => $ownDoors,
            ];
        }

        return array_reverse($out);
    }

    /**
     * РЯДЫ ПО КАЖДОМУ БРЕНДУ для спарклайнов в списке — в хронологическом порядке.
     *
     * Короткие и только три числа на сбор: ряд едет в списке брендов целиком, а их бывают сотни.
     * Бренда может не быть в каком-то сборе — тогда в ряду null, и линия рвётся, а не падает в ноль.
     *
     * @return array<string, array{ds: list<float|null>, os: list<float|null>, own: list<int|null>}>
     */
    public static function series(string $runsDir, int $limit = 12): array
    {
        $records = array_reverse(array_slice(self::load($runsDir), 0, $limit));
        $keys = [];
        foreach ($records as $record) {
            foreach ((array) ($record['brands'] ?? []) as $key => $_) {
                $keys[(string) $key] = true;
            }
        }
        $out = [];
        foreach (array_keys($keys) as $key) {
            $ds = [];
            $os = [];
            $own = [];
            foreach ($records as $record) {
                $b = $record['brands'][$key] ?? null;
                $ds[] = is_array($b) ? round((float) $b['ds'], 1) : null;
                $os[] = is_array($b) ? round((float) $b['os'], 1) : null;
                $own[] = is_array($b) ? (int) $b['own'] : null;
            }
            $out[$key] = ['ds' => $ds, 'os' => $os, 'own' => $own];
        }

        return $out;
    }

    /**
     * ДИНАМИКА ОДНОГО БРЕНДА по сборам — для раскрытого блока: дата, захват, доля доров, лидер, наша доля.
     * Сборы, в которых бренда не было, пропускаются.
     *
     * @return list<array<string, mixed>>
     */
    public static function trend(string $runsDir, string $key, int $limit = 10): array
    {
        $out = [];
        foreach (self::load($runsDir) as $record) {
            $brand = $record['brands'][$key] ?? null;
            if (!is_array($brand)) {
                continue;
            }
            $out[] = ['at' => (string) ($record['at'] ?? ''), 'top' => (int) ($record['top'] ?? 0)] + $brand;
            if (count($out) >= $limit) {
                break;
            }
        }

        return $out;
    }
}

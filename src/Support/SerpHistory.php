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

    /** За сколько дней держим снимки: «будем хранить за месяц». Старше — удаляются при записи. */
    public const KEEP_DAYS = 31;

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
                // И он же по ДОЛЕ ВИДИМОСТИ: пять сайтов внизу топа и один на первом месте — это
                // один и тот же состав по счёту и совсем разный по тому, кто держит бренд.
                'bv' => array_map('floatval', (array) ($brand['vis_by_type'] ?? [])),
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
        $records = self::prune($records, $at ?? time());
        $file = rtrim($runsDir, '/') . '/' . self::FILE;
        @file_put_contents($file, (string) json_encode($records, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES), LOCK_EX);

        return $snapshot;
    }

    /**
     * Оставить снимки за последний месяц (и не больше LIMIT штук). Самый свежий остаётся всегда,
     * даже если часы на машине ушли: без него сравнивать будет не с чем.
     *
     * @param list<array<string, mixed>> $records
     * @return list<array<string, mixed>>
     */
    private static function prune(array $records, int $now): array
    {
        $edge = $now - self::KEEP_DAYS * 86400;
        $kept = [];
        foreach ($records as $i => $rec) {
            $at = strtotime((string) ($rec['at'] ?? '')) ?: 0;
            if ($i === 0 || $at === 0 || $at >= $edge) {
                $kept[] = $rec;
            }
        }

        return array_slice($kept, 0, self::LIMIT);
    }

    /**
     * Список снимков для выбора на странице: только «паспорт» каждого сбора, без брендов.
     *
     * @return list<array{id: string, at: string, top: int, brands: int, is_last: bool}>
     */
    public static function snapshots(string $runsDir): array
    {
        $out = [];
        foreach (self::load($runsDir) as $i => $rec) {
            $out[] = [
                'id' => (string) ($rec['id'] ?? ''),
                'at' => (string) ($rec['at'] ?? ''),
                'top' => (int) ($rec['top'] ?? 0),
                'brands' => count((array) ($rec['brands'] ?? [])),
                'is_last' => $i === 0,
            ];
        }

        return $out;
    }

    /**
     * Снимок по идентификатору — чтобы показать выдачу того сбора, а не только текущего.
     *
     * @return array{snap: array<string, mixed>, prev: array<string, mixed>|null}|null
     */
    public static function byId(string $runsDir, string $id): ?array
    {
        $records = self::load($runsDir);
        foreach ($records as $i => $rec) {
            if ((string) ($rec['id'] ?? '') === $id && $id !== '') {
                return ['snap' => $rec, 'prev' => $records[$i + 1] ?? null];
            }
        }

        return null;
    }

    /**
     * Снимок → список брендов в том же виде, в каком его рисует страница. Строк выдачи в снимке нет
     * (их не хранят — это мегабайты), поэтому поля, которых нет, заполняются честными пустыми
     * значениями, а страница говорит, чего в старом снимке нет.
     *
     * @param array<string, mixed> $snap
     * @return array<string, mixed> разбор той же формы, что отдаёт SerpAnalysis::build()
     */
    public static function asAnalysis(array $snap): array
    {
        $brands = [];
        $totals = array_fill_keys(array_keys(SerpAnalysis::TYPES), 0);
        $capture = ['door' => 0, 'mixed' => 0, 'other' => 0, 'nobrand' => 0];
        $captureLeader = $capture;
        $sites = 0;
        $ownDoors = 0;
        $strong = 0;
        $real = 0;
        foreach ((array) ($snap['brands'] ?? []) as $key => $b) {
            $key = (string) $key;
            $counts = array_map('intval', (array) ($b['by'] ?? []));
            $byVis = array_map('floatval', (array) ($b['bv'] ?? []));
            foreach ($totals as $t => $_) {
                $totals[$t] += $counts[$t] ?? 0;
            }
            $cap = (string) ($b['cap'] ?? '');
            $bucket = $key === '' ? 'nobrand' : (isset($capture[$cap]) ? $cap : 'other');
            $capture[$bucket]++;
            $lt = (string) ($b['lt'] ?? '');
            if ($lt === 'door') {
                $captureLeader[$bucket]++;
            }
            $sites += (int) ($b['sites'] ?? 0);
            $ownDoors += (int) ($b['own'] ?? 0);
            if ($key !== '') {
                $real++;
            }
            $lead = (string) ($b['lead'] ?? '');
            $brands[] = [
                'key' => $key,
                'label' => (string) ($b['label'] ?? $key),
                'capture' => $cap,
                'capture_label' => SerpAnalysis::CAPTURE[$cap] ?? '',
                'door_share' => (float) ($b['ds'] ?? 0),
                'vis_by_type' => $byVis,
                'counts' => $counts,
                'sites' => (int) ($b['sites'] ?? 0),
                'query_count' => (int) ($b['keys'] ?? 0),
                'rows' => 0,
                'fresh_sites' => (int) ($b['fresh'] ?? 0),
                'own_doors' => (int) ($b['own'] ?? 0),
                'our_share' => (float) ($b['os'] ?? 0),
                'our_best' => null,
                'leader' => $lead === '' ? null : ['host' => $lead, 'type' => $lt,
                    'share' => (float) ($b['ls'] ?? 0), 'own' => false, 'keys' => 0, 'best' => 0, 'top3' => 0],
                'board' => [],
                'queries' => [],
                'crossed' => 0,
                'networked' => 0,
                // Этих чисел в снимке нет: показывать ноль как измерение нельзя, поэтому пусто.
                'strong_door' => null,
                'doors_strong' => null,
                'door_best' => null,
                'door_best_host' => '',
                'door_best_own' => false,
            ];
        }
        usort($brands, static fn (array $a, array $b): int => ($a['key'] === '') <=> ($b['key'] === '')
            ?: $b['query_count'] <=> $a['query_count'] ?: strcmp((string) $a['label'], (string) $b['label']));

        return [
            'brands' => $brands,
            'totals' => $totals,
            'totals_sum' => $totals,
            'repeats' => ['sites' => 0, 'by_type' => array_fill_keys(array_keys(SerpAnalysis::TYPES), 0)],
            'own' => ['doors' => $ownDoors, 'sites' => 0, 'by_reason' => []],
            'capture' => $capture,
            'capture_leader' => $captureLeader,
            'strong_doors' => ['brands' => $strong, 'of' => $real],
            'sites' => $sites,
            'results' => 0,
            'queries' => array_sum(array_map(static fn (array $b): int => (int) $b['query_count'], $brands)),
            'freshness' => ['rows' => 0, 'total' => 0],
            'from_snapshot' => true,
        ];
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
                // Сдвиг по КАЖДОМУ типу: «доров стало меньше» ничего не говорит о том, кто занял
                // их место — трастовые площадки, тематические домены или соцсети.
                'bv_was' => array_map('floatval', (array) ($old['bv'] ?? [])),
                'bv_delta' => self::shareDelta(
                    (array) ($brand['vis_by_type'] ?? []),
                    (array) ($old['bv'] ?? []),
                ),
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
     * Разница долей по типам, в процентных пунктах. Типы, которых не было ни там ни там, пропускаем:
     * пустая строка в подсказке — это шум.
     *
     * @param array<string, float> $now
     * @param array<string, float> $was
     * @return array<string, float>
     */
    private static function shareDelta(array $now, array $was): array
    {
        $out = [];
        foreach (array_keys(SerpAnalysis::TYPES) as $type) {
            $a = (float) ($now[$type] ?? 0);
            $b = (float) ($was[$type] ?? 0);
            if ($a === 0.0 && $b === 0.0) {
                continue;
            }
            $out[$type] = round($a - $b, 1);
        }

        return $out;
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
     * @return array<string, array{ds: list<float|null>, os: list<float|null>, own: list<int|null>, lt: list<string|null>}>
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
     * ПОСЛЕДНЯЯ РОТАЦИЯ ТИПА по каждому бренду — за всё окно сборов, а не только с прошлого.
     * `compare()` отвечает «сменился ли тип лидера с прошлого сбора», а вопрос «был у бренда дор,
     * а стал тематический» чаще всего про смену, случившуюся несколько сборов назад: с прошлым
     * сбором такой бренд уже ничем не отличается от тех, где ничего не менялось.
     * Считается по снимкам (`lt` — тип сайта, забиравшего бренд в том сборе); сборы, в которых
     * бренда не было, просто пропускаются — это разрыв в ряду, а не смена типа.
     *
     * @return array<string, array{from: string, to: string, ago: int}> ago — сколько сборов назад
     */
    public static function flips(string $runsDir, int $limit = 12): array
    {
        $records = array_reverse(array_slice(self::load($runsDir), 0, $limit));
        $last = count($records) - 1;
        $points = [];
        foreach ($records as $i => $record) {
            foreach ((array) ($record['brands'] ?? []) as $key => $brand) {
                $type = (string) ($brand['lt'] ?? '');
                if ($type !== '') {
                    $points[(string) $key][] = ['type' => $type, 'i' => $i];
                }
            }
        }
        $out = [];
        foreach ($points as $key => $row) {
            for ($k = count($row) - 1; $k > 0; $k--) {
                if ($row[$k]['type'] === $row[$k - 1]['type']) {
                    continue;
                }
                $out[(string) $key] = [
                    'from' => $row[$k - 1]['type'],
                    'to' => $row[$k]['type'],
                    'ago' => $last - $row[$k]['i'] + 1,
                ];
                break;
            }
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

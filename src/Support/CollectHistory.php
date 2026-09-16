<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Filter\Domains;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;

/**
 * История сборов — вкладка «Статистика» в панели.
 *
 * Интересуют ДОРЫ, и считаются они от ВСЕЙ МАССЫ доменов из выдачи, а не от того, что осталось после
 * фильтров: фильтр «тип домена» отсекает корневые сайты, поэтому в отобранном доров почти 100% и доля
 * ничего не говорит. Поэтому запись содержит два слоя:
 *  - НАЙДЕНО в выдаче: `results` — все строки выдачи (один сайт считается в каждом запросе, где он
 *    попался), `found`/`found_doors`/`found_roots`/`zones` — сколько среди них РАЗНЫХ доменов и
 *    поддоменов, включая отсеянные фильтрами; от `found` и считается доля доров, зоны — по дорам;
 *  - ОТОБРАНО (`sites`, `doors`, `roots`) — что реально попало в базу, плюс `repeats`/`repeats_doors`
 *    (домены, уже бывшие в базе пересечений).
 *
 * Файл лежит в `runs/history.json` (эта папка переживает setup.php --update), новые записи идут в
 * начало списка, хранится последние LIMIT записей.
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
     * Разбор отобранных сайтов: сколько доров, сколько корневых, сколько НАШИХ и зоны ДОРОВ.
     *
     * «Наш» ставится не по картинке, а по меткам в HTML страницы (Filter\OwnSites, own-markers.txt):
     * признак появляется на превью-визите после сбора, скриншот нужен только чтобы проверить глазами.
     *
     * @param array<int|string, Site> $sites
     * @return array{doors: int, roots: int, own: int, zones: array<string, int>}
     */
    public static function breakdown(array $sites): array
    {
        $doors = 0;
        $roots = 0;
        $own = 0;
        $zones = [];
        foreach ($sites as $site) {
            if ($site->own) {
                $own++; // наш шаблон: в базу он попал, но выгружать и чистить его не будем
            }
            // Именно realHost(): при дедупе по домену $site->host хранит регистрируемый домен, и все
            // доры выглядели бы корневыми (в панели это дало «доров 0» на 339 собранных доменах).
            $host = Domains::normalize($site->realHost());
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

        return ['doors' => $doors, 'roots' => $roots, 'own' => $own, 'zones' => $zones];
    }

    /**
     * Разбор ВСЕЙ выдачи: сколько разных доменов встретилось, сколько из них доров и корневых,
     * по каким зонам разошлись доры. Считается по сырым результатам (RunResult::$raw), поэтому сюда
     * попадают и домены, отсеянные фильтрами («не тот тип домена», исключения, позиция) — именно от
     * этой массы пользователь считает долю доров.
     *
     * @param list<array{result: SearchResult, reason: string|null}> $raw
     * @return array{found: int, doors: int, roots: int, zones: array<string, int>}
     */
    public static function breakdownRaw(array $raw): array
    {
        $seen = [];
        foreach ($raw as $entry) {
            $item = is_array($entry) ? ($entry['result'] ?? null) : null;
            if (!$item instanceof SearchResult) {
                continue;
            }
            $host = Domains::normalize($item->host !== '' ? $item->host : Domains::hostFromUrl($item->url));
            if ($host !== '') {
                $seen[$host] = true; // один домен считаем один раз, сколько бы запросов его ни нашло
            }
        }
        $doors = 0;
        $roots = 0;
        $zones = [];
        foreach (array_keys($seen) as $host) {
            if (!self::isDoor((string) $host)) {
                $roots++;
                continue;
            }
            $doors++;
            $zone = Domains::tld((string) $host);
            if ($zone !== '') {
                $zones[$zone] = ($zones[$zone] ?? 0) + 1;
            }
        }
        arsort($zones);

        return ['found' => count($seen), 'doors' => $doors, 'roots' => $roots, 'zones' => $zones];
    }

    /**
     * Запись одного сбора.
     *
     * @param array<int|string, Site> $sites отобранные ЭТИМ сбором сайты
     * @param array<string, mixed> $stats RunResult::$stats
     * @param list<string> $seenBefore хосты, отклонённые как «уже в базе» (RunResult::$seenBefore)
     * @param list<array{result: SearchResult, reason: string|null}> $raw все результаты выдачи сбора
     * @return array<string, mixed>
     */
    public static function record(array $sites, array $stats, array $seenBefore = [], bool $resume = false, bool $stopped = false, array $raw = []): array
    {
        $breakdown = self::breakdown($sites);
        $all = self::breakdownRaw($raw);
        $repeats = count($seenBefore) > 0 ? count($seenBefore) : (int) (((array) ($stats['rejected'] ?? []))['seen_before'] ?? 0);
        $repeatsDoors = 0;
        foreach ($seenBefore as $host) {
            if (self::isDoor((string) $host)) {
                $repeatsDoors++;
            }
        }

        return [
            // Идентификатор записи: она пишется СРАЗУ после отбора доменов, а в конце сбора
            // дополняется итоговыми числами (после визитов) — по id её и находим.
            'id' => bin2hex(random_bytes(6)),
            'date' => date(DATE_ATOM),
            // Масштаб сбора: все строки выдачи (один сайт считается в каждом запросе, где он попался).
            'results' => (int) ($stats['results'] ?? 0),
            // Вся масса: сколько среди них РАЗНЫХ доменов и поддоменов и сколько из них доров.
            'found' => $all['found'],
            'found_doors' => $all['doors'],
            'found_roots' => $all['roots'],
            // Что отобрано в базу (после фильтров).
            'sites' => count($sites),
            'doors' => $breakdown['doors'],
            'roots' => $breakdown['roots'],
            // Наши шаблоны среди отобранного: на момент этой записи визитов ещё не было, число
            // уточняется в конце сбора (признак «наш» ставится по меткам в HTML на превью-визите).
            'own' => $breakdown['own'],
            // Повторы — домены, уже бывшие в базе пересечений; отдельно считаем, сколько из них доры.
            'repeats' => $repeats,
            'repeats_doors' => $repeatsDoors,
            'zones' => $all['zones'] !== [] ? $all['zones'] : $breakdown['zones'], // зоны НАЙДЕННЫХ доров
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
     * Дописывает в САМУЮ СВЕЖУЮ запись то, что можно пересчитать по текущему списку сайтов
     * (runs/current/sites.json), — доры и наши шаблоны.
     *
     * Версии 1.10.0–1.11.0 считали доры по $site->host, а при дедупе по домену там лежит
     * регистрируемый домен — и запись получалась с «доров 0». Записи до 1.15.0 вообще не знали про
     * наши шаблоны. Перечитывать выдачу ради этого не нужно: хосты и признак «наш» видно в sites.json.
     * Трогаем только последнюю запись и только когда число сайтов совпадает с таблицей (значит, это
     * тот же сбор), после чего сохраняем — чтобы считать один раз. Повторы-доры так не восстановить
     * (отклонённых хостов на диске нет), они остаются как были.
     *
     * @param array<int|string, Site> $sites
     * @return array<string, mixed>|null обновлённая запись или null, если пересчитывать нечего
     */
    public static function backfillLatest(string $runsDir, array $sites): ?array
    {
        $records = self::load($runsDir);
        if ($records === [] || $sites === []) {
            return null;
        }
        $latest = $records[0];
        if ((int) ($latest['sites'] ?? 0) !== count($sites)) {
            return null; // таблица уже от другого сбора — пересчитывать нечего
        }
        $needDoors = (int) ($latest['doors'] ?? 0) === 0;
        $needOwn = !array_key_exists('own', $latest);
        if (!$needDoors && !$needOwn) {
            return null;
        }
        $breakdown = self::breakdown($sites);
        $fields = [];
        if ($needDoors && $breakdown['doors'] > 0) {
            $fields['doors'] = $breakdown['doors'];
            $fields['roots'] = $breakdown['roots'];
            // Зоны в записях с 1.13.0 считаются по всей выдаче (есть ключ found) — их не трогаем.
            if (!isset($latest['found'])) {
                $fields['zones'] = $breakdown['zones'];
            }
        }
        if ($needOwn) {
            $fields['own'] = $breakdown['own'];
        }
        if ($fields === []) {
            return null; // доров и правда нет — запись верна
        }
        $records[0] = array_merge($latest, $fields);
        file_put_contents(
            rtrim($runsDir, '/\\') . '/' . self::FILE,
            json_encode($records, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
        );

        return $records[0];
    }

    /**
     * Дополняет уже записанную запись (ищет по `id`): статистика пишется сразу после отбора доменов,
     * а в конце сбора уточняется — визиты могли показать редиректы на бренд-поддомены, и появляется
     * признак «остановлен». Возвращает true, если запись нашлась и обновилась.
     *
     * @param array<string, mixed> $fields
     */
    public static function update(string $runsDir, string $id, array $fields): bool
    {
        if ($id === '') {
            return false;
        }
        $records = self::load($runsDir);
        foreach ($records as $i => $record) {
            if ((string) ($record['id'] ?? '') !== $id) {
                continue;
            }
            $records[$i] = array_merge($record, $fields);
            file_put_contents(
                rtrim($runsDir, '/\\') . '/' . self::FILE,
                json_encode($records, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
            );

            return true;
        }

        return false;
    }

    /**
     * Удаляет историю сборов целиком («очистить статистику» в настройках, а также полный сброс базы).
     *
     * @return int сколько записей было удалено
     */
    public static function clear(string $runsDir): int
    {
        $n = count(self::load($runsDir));
        @unlink(rtrim($runsDir, '/\\') . '/' . self::FILE);

        return $n;
    }

    /**
     * Итог по всем сборам: сколько собрано, сколько доров и их доля, повторы доров, зоны доров.
     *
     * @param list<array<string, mixed>> $records
     * @return array{runs: int, sites: int, doors: int, roots: int, doors_percent: float, repeats: int, repeats_doors: int, zones: array<string, int>, base_domains: int}
     */
    public static function totals(array $records): array
    {
        $out = ['runs' => 0, 'results' => 0, 'found' => 0, 'found_doors' => 0, 'found_roots' => 0, 'sites' => 0, 'doors' => 0, 'roots' => 0, 'own' => 0, 'doors_percent' => 0.0, 'own_percent' => 0.0, 'repeats' => 0, 'repeats_doors' => 0, 'zones' => [], 'base_domains' => 0];
        foreach ($records as $r) {
            $out['runs']++;
            foreach (['results', 'found', 'found_doors', 'found_roots', 'sites', 'doors', 'roots', 'own', 'repeats', 'repeats_doors'] as $key) {
                $out[$key] += (int) ($r[$key] ?? 0);
            }
            foreach ((array) ($r['zones'] ?? []) as $zone => $count) {
                $out['zones'][(string) $zone] = ($out['zones'][(string) $zone] ?? 0) + (int) $count;
            }
        }
        arsort($out['zones']);
        // Доля доров — от ВСЕЙ массы найденных доменов; у записей старых версий этой массы нет,
        // тогда считаем как раньше, от отобранного.
        $out['doors_percent'] = $out['found'] > 0
            ? self::percent($out['found_doors'], $out['found'])
            : self::percent($out['doors'], $out['sites']);
        // Наши считаются от ОТОБРАННОГО: в выдаче мы их по одному адресу не узнаём, признак ставится
        // по меткам в HTML уже на визите.
        $out['own_percent'] = self::percent($out['own'], $out['sites']);
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
        fputcsv($out, ['Дата', 'Результатов в выдаче', 'Доменов и поддоменов', 'Доров из них', 'Доля доров, %', 'Корневых', 'Отобрано сайтов', 'Доров среди отобранных', 'Наших сайтов', 'Доля наших, %', 'Повторов доров', 'Повторов всего', 'Зоны доров', 'Всего в базе', 'Продолжение', 'Остановлен'], $delimiter, '"', '');
        foreach ($records as $r) {
            $found = (int) ($r['found'] ?? 0);
            $foundDoors = (int) ($r['found_doors'] ?? 0);
            $sites = (int) ($r['sites'] ?? 0);
            fputcsv($out, [
                self::dateHuman((string) ($r['date'] ?? '')),
                (int) ($r['results'] ?? 0),
                $found,
                $foundDoors,
                $found > 0 ? self::percent($foundDoors, $found) : self::percent((int) ($r['doors'] ?? 0), $sites),
                (int) ($r['found_roots'] ?? 0),
                $sites,
                (int) ($r['doors'] ?? 0),
                (int) ($r['own'] ?? 0),
                self::percent((int) ($r['own'] ?? 0), $sites),
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

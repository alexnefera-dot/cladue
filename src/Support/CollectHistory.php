<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Filter\Domains;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;

/**
 * История сборов — вкладка «Статистика» в панели.
 *
 * Интересуют ДОРЫ, и считаются они от ВСЕЙ МАССЫ выдачи, а не от того, что осталось после фильтров:
 * фильтр «тип домена» отсекает корневые сайты, поэтому в отобранном доров почти 100% и доля ничего
 * не говорит. Запись — это ВОРОНКА, где каждое число вытекает из предыдущего:
 *  - `results` — все строки выдачи (один сайт считается в каждом запросе, где он попался);
 *  - `found` — сколько среди них разных АДРЕСОВ (хостов);
 *  - `unique_sites` — сколько это САЙТОВ после группировки «один сайт на домен» (доры одной сетки —
 *    один сайт); от него считаются `found_doors`/`found_roots` и доля доров, зоны — по дорам;
 *  - `cut` — что срезали фильтры, ПО САЙТАМ и по причинам (плюс сколько из них доров);
 *  - `sites`/`doors`/`roots`/`own` — что отобрано в базу, плюс `repeats`/`repeats_doors`
 *    (домены, уже бывшие в базе пересечений; они же одна из причин в `cut`).
 * Проверка сходимости: `unique_sites` = `sites` + сумма `cut` — это и есть ответ на вопрос «куда
 * делись 6460 доменов, если отобрано 602».
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
     * Человеческие названия причин отсева — для журнала, CSV и подписей в панели.
     * Те же коды, что возвращает Filter\ResultFilter::reject() и считает Runner.
     */
    public const REASONS = [
        'position' => 'позиция ниже лимита',
        'no_host' => 'без адреса',
        'include_domains' => 'нет в списке нужных',
        'exclude_domains' => 'в списке исключений',
        'own_site' => 'наш шаблон',
        'tld' => 'зона домена не разрешена',
        'domain_scope' => 'не тот тип домена',
        'url_must_match' => 'URL не подходит',
        'url_must_not_match' => 'URL исключён',
        'title_any' => 'нет слов в заголовке',
        'title_all' => 'нет всех слов в заголовке',
        'title_none' => 'стоп-слово в заголовке',
        'snippet_any' => 'нет слов в описании',
        'snippet_none' => 'стоп-слово в описании',
        'min_queries' => 'мало запросов',
        'min_hits' => 'мало попаданий',
        'seen_before' => 'уже в базе доменов',
        'other' => 'прочее (старая запись, причина не сохранена)',
    ];

    /** Причины, которые срабатывают уже ПОСЛЕ группировки, — Runner считает их сразу по сайтам. */
    private const SITE_REASONS = ['min_queries', 'min_hits', 'seen_before'];

    /** Название причины для показа; неизвестный код (site_check:…) отдаём как есть. */
    public static function reasonLabel(string $code): string
    {
        if (str_starts_with($code, 'site_check:')) {
            return 'не ответил на проверку (' . substr($code, strlen('site_check:')) . ')';
        }

        return self::REASONS[$code] ?? $code;
    }

    /**
     * Разбор ВСЕЙ выдачи по сырым результатам (RunResult::$raw) — то, из чего строится воронка сбора.
     *
     * Считаем ДВА разных числа, потому что пользователь читал их как противоречие («а почему
     * результатов 25к, а доменов 6.5к, а отобрано 600?»):
     *  - `found` — сколько разных АДРЕСОВ (хостов) встретилось в выдаче;
     *  - `unique` — сколько это САЙТОВ после группировки «один сайт на домен»: все доры одной сетки
     *    (kush./hype./max.casinozsd.buzz) — это один сайт, а не три. Группируем тем же ключом, что и
     *    Aggregator, поэтому от `unique` воронка идёт дальше без разрывов: unique = отобрано + срезано.
     *
     * Доры и зоны считаются по `unique`: у группы берётся хост её ЛУЧШЕГО результата (как Aggregator
     * берёт bestUrl), причём у прошедшей фильтры группы — лучший из прошедших: это тот адрес, который
     * и попал бы в таблицу.
     *
     * `cut` — что срезали фильтры выдачи, ПО САЙТАМ (группа попадает сюда, только если ни один её
     * результат фильтры не прошёл; причина — у лучшего результата) и отдельно сколько из них доров.
     * Причины, работающие после группировки (мало запросов, уже в базе), сюда не попадают — их
     * добавляет record() из счётчиков Runner.
     *
     * @param list<array{result: SearchResult, reason: string|null}> $raw
     * @param string $uniqueBy как группировать: domain («один сайт на домен») или host
     * @return array{found: int, unique: int, doors: int, roots: int, zones: array<string, int>, cut: array<string, array{sites: int, doors: int}>}
     */
    public static function breakdownRaw(array $raw, string $uniqueBy = 'domain'): array
    {
        return self::breakdownRows((static function () use ($raw): \Generator {
            foreach ($raw as $entry) {
                $item = is_array($entry) ? ($entry['result'] ?? null) : null;
                if (!$item instanceof SearchResult) {
                    continue;
                }
                $reason = is_array($entry) ? ($entry['reason'] ?? null) : null;
                yield [
                    $item->host !== '' ? $item->host : Domains::hostFromUrl($item->url),
                    $item->position,
                    is_string($reason) ? $reason : null,
                ];
            }
        })(), $uniqueBy);
    }

    /**
     * Тот же разбор, но по «сырым» тройкам [хост, позиция, причина или null] — так его можно
     * посчитать и по строкам results.csv, не поднимая в память тысячи объектов выдачи.
     *
     * @param iterable<array{0: string, 1: int, 2: string|null}> $rows
     * @return array{found: int, unique: int, doors: int, roots: int, zones: array<string, int>, cut: array<string, array{sites: int, doors: int}>}
     */
    public static function breakdownRows(iterable $rows, string $uniqueBy = 'domain'): array
    {
        $hosts = [];
        /** @var array<string, array{host: string, pos: int, reason: string|null, okHost: string, okPos: int, passed: bool}> */
        $groups = [];
        foreach ($rows as [$rawHost, $position, $reason]) {
            $host = Domains::normalize((string) $rawHost);
            if ($host === '') {
                continue; // результат без адреса сайтом не считается (счётчик no_host остаётся в stats)
            }
            $position = (int) $position;
            $hosts[$host] = true; // один адрес считаем один раз, сколько бы запросов его ни нашло
            $key = $uniqueBy === 'domain' ? Domains::registrable($host) : $host;
            $group = $groups[$key] ?? ['host' => '', 'pos' => PHP_INT_MAX, 'reason' => null, 'okHost' => '', 'okPos' => PHP_INT_MAX, 'passed' => false];
            if ($position < $group['pos']) {
                $group['pos'] = $position;
                $group['host'] = $host;
                $group['reason'] = $reason;
            }
            if ($reason === null) {
                $group['passed'] = true;
                if ($position < $group['okPos']) {
                    $group['okPos'] = $position;
                    $group['okHost'] = $host;
                }
            }
            $groups[$key] = $group;
        }

        $doors = 0;
        $roots = 0;
        $zones = [];
        $cut = [];
        foreach ($groups as $group) {
            $host = $group['passed'] && $group['okHost'] !== '' ? $group['okHost'] : $group['host'];
            $isDoor = self::isDoor($host);
            if ($isDoor) {
                $doors++;
                $zone = Domains::tld($host);
                if ($zone !== '') {
                    $zones[$zone] = ($zones[$zone] ?? 0) + 1;
                }
            } else {
                $roots++;
            }
            if (!$group['passed']) {
                $reason = $group['reason'] ?? 'other';
                $cut[$reason] ??= ['sites' => 0, 'doors' => 0];
                $cut[$reason]['sites']++;
                $cut[$reason]['doors'] += $isDoor ? 1 : 0;
            }
        }
        arsort($zones);
        uasort($cut, static fn (array $a, array $b): int => $b['sites'] <=> $a['sites']);

        return ['found' => count($hosts), 'unique' => count($groups), 'doors' => $doors, 'roots' => $roots, 'zones' => $zones, 'cut' => $cut];
    }

    /**
     * От чего считается доля наших: всего доров в выдаче, иначе доры среди отобранного, иначе отобранное.
     *
     * @param array<string, mixed> $record запись сбора или итог totals()
     */
    public static function ownBase(array $record): int
    {
        foreach (['found_doors', 'doors', 'sites'] as $key) {
            $n = (int) ($record[$key] ?? 0);
            if ($n > 0) {
                return $n;
            }
        }

        return 0;
    }

    /**
     * Сколько всего сайтов срезано (сумма по причинам).
     *
     * @param array<string, array{sites: int, doors: int}> $cut
     */
    public static function cutTotal(array $cut, string $field = 'sites'): int
    {
        $n = 0;
        foreach ($cut as $row) {
            $n += (int) (((array) $row)[$field] ?? 0);
        }

        return $n;
    }

    /**
     * Строка «что срезано» для журнала и CSV: «не тот тип домена — 3200 (доров 2100); уже в базе — 1185».
     *
     * @param array<string, array{sites: int, doors: int}> $cut
     */
    public static function cutText(array $cut, int $limit = 0): string
    {
        $parts = [];
        foreach ($cut as $code => $row) {
            $row = (array) $row;
            $doors = (int) ($row['doors'] ?? 0);
            $parts[] = self::reasonLabel((string) $code) . ' — ' . (int) ($row['sites'] ?? 0) . ($doors > 0 ? sprintf(' (доров %d)', $doors) : '');
            if ($limit > 0 && count($parts) >= $limit) {
                break;
            }
        }

        return implode('; ', $parts);
    }

    /**
     * Запись одного сбора.
     *
     * @param array<int|string, Site> $sites отобранные ЭТИМ сбором сайты
     * @param array<string, mixed> $stats RunResult::$stats
     * @param list<string> $seenBefore хосты, отклонённые как «уже в базе» (RunResult::$seenBefore)
     * @param list<array{result: SearchResult, reason: string|null}> $raw все результаты выдачи сбора
     * @param list<string> $ownDomains домены НАШИХ шаблонов, найденные за все сборы (runs/own-domains.txt)
     * @return array<string, mixed>
     */
    public static function record(array $sites, array $stats, array $seenBefore = [], bool $resume = false, bool $stopped = false, array $raw = [], array $ownDomains = []): array
    {
        $breakdown = self::breakdown($sites);
        // Домены, которые держат много брендов: на их поддоменах сайты разных брендов (бренд берётся
        // из поискового запроса, написания RU/EN сводятся к одному ключу).
        $brandDomains = BrandDomains::find($raw, $sites);
        $rejected = (array) ($stats['rejected'] ?? []);
        $all = self::breakdownRaw($raw, (string) ($stats['unique_by'] ?? 'domain'));
        $repeats = count($seenBefore) > 0 ? count($seenBefore) : (int) ($rejected['seen_before'] ?? 0);
        $repeatsDoors = 0;
        foreach ($seenBefore as $host) {
            if (self::isDoor((string) $host)) {
                $repeatsDoors++;
            }
        }
        $ownRepeats = self::ownRepeats($seenBefore, $ownDomains);
        // Причины, которые срабатывают уже ПОСЛЕ группировки в сайты (мало запросов, уже в базе,
        // не ответил на проверку), Runner считает сразу по сайтам — берём его счётчики как есть.
        // Вместе с фильтрами выдачи из breakdownRaw() получается сходящаяся воронка:
        // сайтов в выдаче = отобрано + срезано по всем причинам.
        $cut = $all['cut'];
        foreach ($rejected as $code => $count) {
            $code = (string) $code;
            if (!in_array($code, self::SITE_REASONS, true) && !str_starts_with($code, 'site_check:')) {
                continue;
            }
            $count = $code === 'seen_before' ? $repeats : (int) $count;
            if ($count > 0) {
                // Доры известны только по повторам: у остальных причин Runner хостов не запоминает.
                $cut[$code] = ['sites' => $count, 'doors' => $code === 'seen_before' ? $repeatsDoors : 0];
            }
        }
        uasort($cut, static fn (array $a, array $b): int => $b['sites'] <=> $a['sites']);

        return [
            // Идентификатор записи: она пишется СРАЗУ после отбора доменов, а в конце сбора
            // дополняется итоговыми числами (после визитов) — по id её и находим.
            'id' => bin2hex(random_bytes(6)),
            'date' => date(DATE_ATOM),
            // Масштаб сбора: все строки выдачи (один сайт считается в каждом запросе, где он попался).
            'results' => (int) ($stats['results'] ?? 0),
            // Вся масса: сколько среди них РАЗНЫХ адресов (found) и сколько это САЙТОВ после
            // группировки «один сайт на домен» (unique_sites) — доры и зоны считаются по второму.
            'found' => $all['found'],
            'unique_sites' => $all['unique'],
            'found_doors' => $all['doors'],
            'found_roots' => $all['roots'],
            // Что срезали фильтры, по сайтам и по причинам: unique_sites = sites + сумма cut.
            'cut' => $cut,
            // Что отобрано в базу (после фильтров).
            'sites' => count($sites),
            'doors' => $breakdown['doors'],
            'roots' => $breakdown['roots'],
            // Наши шаблоны: отобранные (признак ставится по меткам в HTML на превью-визите — на момент
            // этой записи визитов ещё не было, число уточняется в конце сбора) ПЛЮС те, что пришли
            // повторами: домен уже в базе, сайт мы даже не открываем, но он наш и в выдаче стоит.
            'own' => $breakdown['own'] + $ownRepeats,
            'own_repeats' => $ownRepeats,
            // Домены, которые держат на поддоменах от BrandDomains::MIN_BRANDS разных брендов.
            'brand_domains' => count($brandDomains),
            'brand_domains_top' => BrandDomains::top($brandDomains),
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
     * Сколько НАШИХ шаблонов среди повторов: домен уже был в базе, поэтому сайт даже не открывался,
     * но в выдаче он стоит и он наш. Свои домены накапливаются в runs/own-domains.txt.
     *
     * @param list<string> $seenBefore хосты, отклонённые как «уже в базе»
     * @param list<string> $ownDomains домены наших шаблонов
     */
    public static function ownRepeats(array $seenBefore, array $ownDomains): int
    {
        if ($seenBefore === [] || $ownDomains === []) {
            return 0;
        }
        $own = [];
        foreach ($ownDomains as $domain) {
            $domain = mb_strtolower(trim((string) $domain));
            if ($domain !== '') {
                $own[$domain] = true;
            }
        }
        // Считаем ДОМЕНЫ, а не адреса: в воронке всё после «сайтов в выдаче» считается сайтами
        // (поддомены одного домена — один сайт), иначе наших оказалось бы больше, чем доров.
        $found = [];
        foreach ($seenBefore as $host) {
            $host = Domains::normalize((string) $host);
            $domain = $host !== '' ? Domains::registrable($host) : '';
            if ($domain !== '' && isset($own[$domain])) {
                $found[$domain] = true;
            }
        }

        return count($found);
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
     * Читает результаты прошлого сбора из results.csv тройками [хост, позиция, причина].
     *
     * @return \Generator<int, array{0: string, 1: int, 2: string|null}>
     */
    public static function resultRows(string $file): \Generator
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
            $hi = array_search('host', $header, true);
            $ui = array_search('url', $header, true);
            $pi = array_search('position', $header, true);
            $ri = array_search('result', $header, true);
            if ($hi === false || $ri === false) {
                return;
            }
            while (($row = fgetcsv($fh, 0, $delimiter, '"', '')) !== false) {
                if (!isset($row[$hi], $row[$ri])) {
                    continue;
                }
                $host = (string) $row[$hi];
                if ($host === '' && $ui !== false && isset($row[$ui])) {
                    $host = Domains::hostFromUrl((string) $row[$ui]);
                }
                $reason = (string) $row[$ri];
                yield [$host, $pi !== false && isset($row[$pi]) ? (int) $row[$pi] : 1, $reason === 'selected' || $reason === '' ? null : $reason];
            }
        } finally {
            fclose($fh);
        }
    }

    /**
     * Досчитывает воронку (сайты выдачи + что срезано) в САМОЙ СВЕЖЕЙ записи по results.csv прошлого
     * сбора — чтобы после обновления не пришлось собирать заново ради новых чисел.
     *
     * Записи до 1.16.0 считали массу выдачи по АДРЕСАМ и не знали, что именно срезали фильтры; в
     * results.csv лежат ровно те строки выдачи с причинами, по которым это считается. Берём файл
     * только если он описывает ИМЕННО этот сбор: число строк и число разных адресов должны совпасть
     * с записью (при сборе частями файл описывает весь список, а запись — только свою часть).
     * Причины, работающие после группировки, в файле не отражены — «уже в базе» берём из записи,
     * необъяснённый остаток кладём в «прочее», чтобы воронка сходилась.
     *
     * @return array<string, mixed>|null обновлённая запись или null, если пересчитывать нечего
     */
    public static function backfillFunnel(string $runsDir, string $resultsCsv, string $uniqueBy = 'domain'): ?array
    {
        $records = self::load($runsDir);
        if ($records === [] || isset($records[0]['unique_sites'])) {
            return null;
        }
        $latest = $records[0];
        $expected = (int) ($latest['results'] ?? 0);
        if ($expected <= 0 || !is_file($resultsCsv)) {
            return null;
        }
        $rows = 0;
        $all = self::breakdownRows((static function () use ($resultsCsv, &$rows): \Generator {
            foreach (self::resultRows($resultsCsv) as $row) {
                $rows++;
                yield $row;
            }
        })(), $uniqueBy);
        if ($rows !== $expected || $all['found'] !== (int) ($latest['found'] ?? -1)) {
            return null; // файл описывает другой сбор (или сбор шёл частями) — не трогаем запись
        }

        $cut = $all['cut'];
        $repeats = (int) ($latest['repeats'] ?? 0);
        if ($repeats > 0) {
            $cut['seen_before'] = ['sites' => $repeats, 'doors' => (int) ($latest['repeats_doors'] ?? 0)];
        }
        $rest = $all['unique'] - (int) ($latest['sites'] ?? 0) - self::cutTotal($cut);
        if ($rest > 0) {
            $cut['other'] = ['sites' => $rest, 'doors' => 0];
        }
        uasort($cut, static fn (array $a, array $b): int => $b['sites'] <=> $a['sites']);

        $records[0] = array_merge($latest, [
            'unique_sites' => $all['unique'],
            'found_doors' => $all['doors'],
            'found_roots' => $all['roots'],
            'zones' => $all['zones'],
            'cut' => $cut,
        ]);
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
        $out = ['runs' => 0, 'results' => 0, 'found' => 0, 'unique_sites' => 0, 'found_doors' => 0, 'found_roots' => 0, 'sites' => 0, 'doors' => 0, 'roots' => 0, 'own' => 0, 'own_repeats' => 0, 'brand_domains' => 0, 'cut' => [], 'cut_total' => 0, 'doors_percent' => 0.0, 'own_percent' => 0.0, 'repeats' => 0, 'repeats_doors' => 0, 'zones' => [], 'base_domains' => 0];
        foreach ($records as $r) {
            $out['runs']++;
            foreach (['results', 'found', 'found_roots', 'sites', 'doors', 'roots', 'own', 'own_repeats', 'brand_domains', 'repeats', 'repeats_doors'] as $key) {
                $out[$key] += (int) ($r[$key] ?? 0);
            }
            // Масса выдачи и доры в ней: у записей до 1.16.0 группировки нет — берём адреса, у совсем
            // старых (до 1.13.0) — отобранное. Иначе сумма доров делилась бы на массу только новых
            // записей и доля доров вылетала за 100%.
            $sites = (int) ($r['sites'] ?? 0);
            $mass = (int) ($r['unique_sites'] ?? 0) ?: ((int) ($r['found'] ?? 0) ?: $sites);
            $massDoors = (int) ($r['unique_sites'] ?? 0) > 0 || (int) ($r['found'] ?? 0) > 0
                ? (int) ($r['found_doors'] ?? 0)
                : (int) ($r['doors'] ?? 0); // запись без сырой выдачи: доры известны только по отобранному
            $out['unique_sites'] += $mass;
            $out['found_doors'] += $massDoors;
            foreach ((array) ($r['zones'] ?? []) as $zone => $count) {
                $out['zones'][(string) $zone] = ($out['zones'][(string) $zone] ?? 0) + (int) $count;
            }
            $cut = (array) ($r['cut'] ?? []);
            foreach ($cut as $code => $row) {
                $row = (array) $row;
                $code = (string) $code;
                $out['cut'][$code] ??= ['sites' => 0, 'doors' => 0];
                $out['cut'][$code]['sites'] += (int) ($row['sites'] ?? 0);
                $out['cut'][$code]['doors'] += (int) ($row['doors'] ?? 0);
            }
            // Чтобы итог тоже сходился (масса = отобрано + срезано), необъяснённый остаток записи
            // (у старых записей — всё срезанное) кладём в «прочее».
            $rest = $mass - $sites - self::cutTotal($cut);
            if ($rest > 0) {
                $out['cut']['other'] ??= ['sites' => 0, 'doors' => 0];
                $out['cut']['other']['sites'] += $rest;
            }
        }
        arsort($out['zones']);
        uasort($out['cut'], static fn (array $a, array $b): int => $b['sites'] <=> $a['sites']);
        $out['cut_total'] = self::cutTotal($out['cut']);
        // Доля доров — от массы САЙТОВ выдачи (после группировки «один сайт на домен»): именно из
        // этого числа дальше вычитается срезанное. У записей до 1.16.0 группировки нет — там считаем
        // от разных адресов, а у совсем старых (до 1.13.0) — от отобранного, как было.
        $out['doors_percent'] = self::percent($out['found_doors'], $out['unique_sites']);
        // Доля наших — от ОБЩЕГО ЧИСЛА ДОРОВ в выдаче: наши шаблоны и есть доры, и вопрос «сколько
        // доров ниши наши» отвечается только так. У старых записей массы доров нет — берём отобранное.
        $out['own_percent'] = self::percent($out['own'], self::ownBase($out));
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
        fputcsv($out, ['Дата', 'Результатов в выдаче', 'Адресов в выдаче', 'Сайтов в выдаче', 'Доров из них', 'Доля доров, %', 'Корневых', 'Срезано фильтрами', 'Что срезано', 'Отобрано сайтов', 'Доров среди отобранных', 'Наших сайтов', 'Доля наших, %', 'Доменов с 6+ брендами', 'Повторов доров', 'Повторов всего', 'Зоны доров', 'Всего в базе', 'Продолжение', 'Остановлен'], $delimiter, '"', '');
        foreach ($records as $r) {
            $found = (int) ($r['found'] ?? 0);
            $foundDoors = (int) ($r['found_doors'] ?? 0);
            $sites = (int) ($r['sites'] ?? 0);
            // База для доли доров: сайты выдачи после группировки, у старых записей — адреса.
            $mass = (int) ($r['unique_sites'] ?? 0);
            $cut = (array) ($r['cut'] ?? []);
            fputcsv($out, [
                self::dateHuman((string) ($r['date'] ?? '')),
                (int) ($r['results'] ?? 0),
                $found,
                $mass > 0 ? $mass : '', // у старых записей группировки нет — пусто, а не «0 сайтов»
                $foundDoors,
                $mass > 0
                    ? self::percent($foundDoors, $mass)
                    : ($found > 0 ? self::percent($foundDoors, $found) : self::percent((int) ($r['doors'] ?? 0), $sites)),
                (int) ($r['found_roots'] ?? 0),
                $cut !== [] ? self::cutTotal($cut) : '',
                self::cutText($cut),
                $sites,
                (int) ($r['doors'] ?? 0),
                (int) ($r['own'] ?? 0),
                self::percent((int) ($r['own'] ?? 0), self::ownBase($r)),
                isset($r['brand_domains']) ? (int) $r['brand_domains'] : '',
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

<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Content\BrandKeys;
use YandexSites\Filter\DefaultExclusions;
use YandexSites\Filter\Domains;
use YandexSites\Filter\OwnSites;

/**
 * ТЕХНИЧЕСКИЙ РАЗБОР ВЫДАЧИ — отдельная страница панели (/serp), которая показывает выдачу КАК ОНА ЕСТЬ,
 * до всего, что делает главная: без группировки «один сайт на домен», без фильтров, без отсева повторов.
 *
 * Главная оставляет только доры, и по ней не видно, что именно было выброшено и склеено. Здесь наоборот:
 * блок на БРЕНД (ключи бренда узнаёт Content\BrandKeys), внутри — каждый ключ со своим топом, каждая
 * строка выдачи на месте. Пересечения подсвечиваются: сайт, который встретился в нескольких ключах ОДНОГО
 * бренда, и сайт, который держится сразу на нескольких брендах (это и есть сетка). В конце бренда — сколько
 * каких сайтов: доры, тематические домены, соцсети, известные сайты рунета, прочие.
 *
 * Данные берутся из runs/current/results.csv — он описывает ВЕСЬ текущий сбор (при сборе частями строки
 * дописываются), поэтому разбор не нужно копить отдельно и он всегда соответствует тому, что собрано.
 */
final class SerpAnalysis
{
    /** Причина «наш» по накопленному списку наших доменов (вторая причина — конкретная метка). */
    public const REASON_LIST = 'домен в списке наших';

    /** Причина «наш» по выгрузке из системы запусков — самая точная: список даёт сама система. */
    public const REASON_DORGEN = 'запущен в dorgen';

    /** Индекс прошлого сбора для сравнения — рядом с историей, переживает обновление кода. */
    public const INDEX_FILE = 'serp-prev.json';

    /** Разница с прошлым сбором, посчитанная в конце сбора (лежит в папке прогона). */
    public const DIFF_FILE = 'serp-diff.json';

    /** Типы сайтов в порядке показа. */
    public const TYPES = [
        'door' => 'доры (поддомены)',
        'theme' => 'тематические домены',
        'social' => 'соцсети и видео',
        'known' => 'известные сайты рунета',
        'other' => 'прочие домены',
    ];

    /**
     * Соцсети, мессенджеры, видео и блог-платформы: у них поддомен — это не дор, а страница профиля.
     *
     * @var list<string>
     */
    private const SOCIAL = [
        'vk.com', 'vk.ru', 'vkvideo.ru', 'ok.ru', 't.me', 'telegram.org', 'telegram.me', 'tgstat.ru',
        'instagram.com', 'facebook.com', 'tiktok.com', 'twitter.com', 'x.com', 'threads.net',
        'pinterest.com', 'pinterest.ru', 'reddit.com', 'linkedin.com', 'discord.com', 'discord.gg',
        'youtube.com', 'youtu.be', 'rutube.ru', 'dzen.ru', 'zen.yandex.ru', 'likee.video', 'twitch.tv',
        'livejournal.com', 'blogspot.com', 'medium.com', 'pikabu.ru', 'habr.com', 'vc.ru', 'dtf.ru',
        'yappy.media', 'my.mail.ru',
    ];

    /**
     * Слова темы в адресе/заголовке/сниппете — по ним обычный домен считается ТЕМАТИЧЕСКИМ.
     * Сравнение по началу слова, как в BrandKeys: «слоты», «автоматами», «зеркала» ловятся разом.
     *
     * @var list<string>
     */
    private const THEME_RU = [
        'казино', 'слот', 'автомат', 'ставк', 'зеркал', 'бонус', 'промокод', 'фриспин', 'кэшбэк',
        'кешбэк', 'бездеп', 'гэмбл', 'игров', 'букмекер', 'вейджер', 'азарт',
    ];

    /** Латинские слова темы: ищем как подстроку в адресе и по границе слова в тексте. @var list<string> */
    private const THEME_EN = [
        'casino', 'kazino', 'slot', 'bet', 'gambl', 'jackpot', 'poker', 'bonus', 'freespin', 'wager',
    ];

    /**
     * Разбор выдачи по брендам.
     *
     * ВСЁ СЧИТАЕТСЯ ПО РАЗНЫМ САЙТАМ, а не по строкам: один дор на пяти ключах — это один дор. Внутри
     * бренда уникальность по домену, в итогах по всем брендам — тоже (домен, который держится на трёх
     * брендах, в общем числе доров один). Разница между суммой по брендам и общим числом — это и есть
     * повторы между брендами, она показана отдельной строкой.
     *
     * @param iterable<array{query: string, position: int, host: string, url: string, title: string, snippet: string, reason: string}> $rows
     * @param int $top оставить только первые N позиций каждого запроса (0 — все)
     * @param OwnSites|null $own метки наших шаблонов: дор помечается «наш» по домену/адресу
     * @param array<int, string> $ownDomains накопленный список НАШИХ доменов (runs/own-domains.txt)
     * @param array<string, bool> $dorgenBases наши БАЗЫ из системы запусков (Dorgen\OwnBases): самый
     *        точный источник — сверяем последние две метки хоста, метки и список доменов остаются как были
     * @return array<string, mixed>
     */
    public static function build(iterable $rows, int $top = 10, ?OwnSites $own = null, array $ownDomains = [], array $dorgenBases = []): array
    {
        $ourDomains = [];
        foreach ($ownDomains as $domain) {
            $domain = Domains::normalize(trim((string) $domain));
            if ($domain !== '') {
                $ourDomains[$domain] = true;
            }
        }
        $brands = [];
        $results = 0;
        $hostBrands = []; // host => [brandKey => true] — сколько РАЗНЫХ брендов держится на домене
        foreach ($rows as $row) {
            $position = (int) ($row['position'] ?? 0);
            if ($top > 0 && $position > $top) {
                continue;
            }
            $host = Domains::normalize((string) ($row['host'] ?? ''));
            if ($host === '') {
                continue;
            }
            $query = trim((string) ($row['query'] ?? ''));
            $key = BrandKeys::of($query);
            $bucket = $key !== '' ? $key : '';
            if (!isset($brands[$bucket])) {
                $brands[$bucket] = [
                    'key' => $bucket,
                    'label' => $bucket !== '' ? BrandKeys::label($bucket) : 'без бренда',
                    'queries' => [],
                    'hosts' => [],
                ];
            }
            $type = self::classify($host, (string) ($row['title'] ?? ''), (string) ($row['snippet'] ?? ''));
            $brands[$bucket]['queries'][$query][] = [
                'position' => $position,
                'host' => $host,
                'url' => (string) ($row['url'] ?? ''),
                'title' => (string) ($row['title'] ?? ''),
                'type' => $type,
                'reason' => (string) ($row['reason'] ?? ''),
            ];
            if (!isset($brands[$bucket]['hosts'][$host])) {
                $reason = self::ownReason($host, $own, $ourDomains, $dorgenBases);
                $brands[$bucket]['hosts'][$host] = ['type' => $type, 'keys' => [], 'count' => 0,
                    'own' => $reason !== '', 'own_reason' => $reason];
            }
            $brands[$bucket]['hosts'][$host]['keys'][$query] = true;
            $brands[$bucket]['hosts'][$host]['count']++;
            $hostBrands[$host][$bucket] = true;
            $results++;
        }

        $totals = array_fill_keys(array_keys(self::TYPES), 0);      // УНИКАЛЬНЫЕ сайты по всем брендам
        $totalsSum = array_fill_keys(array_keys(self::TYPES), 0);   // сумма по брендам (с повторами)
        $repeats = array_fill_keys(array_keys(self::TYPES), 0);     // сайты, которые держатся на 2+ брендах
        $seenHost = [];
        $ownAll = ['doors' => 0, 'sites' => 0, 'by_reason' => []];
        $out = [];
        $queries = 0;
        foreach ($brands as $bucket => $brand) {
            ksort($brand['queries']);
            $counts = array_fill_keys(array_keys(self::TYPES), 0);
            $ownDoors = 0;
            foreach ($brand['hosts'] as $host => $info) {
                // Считаем по РАЗНЫМ сайтам, а не по строкам: один дор на пяти ключах — это один дор.
                $counts[$info['type']]++;
                $totalsSum[$info['type']]++;
                if (!isset($seenHost[$host])) {
                    // В общий итог домен попадает ОДИН раз, даже если он стоит на нескольких брендах.
                    $seenHost[$host] = true;
                    $totals[$info['type']]++;
                    if (count($hostBrands[$host] ?? []) > 1) {
                        $repeats[$info['type']]++;
                    }
                    if ($info['own']) {
                        $ownAll['sites']++;
                        if ($info['type'] === 'door') {
                            $ownAll['doors']++;
                            // Разбивка «по какой причине наш»: сразу видно, какая метка ловит лишнее.
                            $r = (string) $info['own_reason'];
                            $ownAll['by_reason'][$r] = ($ownAll['by_reason'][$r] ?? 0) + 1;
                        }
                    }
                }
                if ($info['own'] && $info['type'] === 'door') {
                    $ownDoors++;
                }
                $brand['hosts'][$host]['keys'] = count($info['keys']);
                // На скольких брендах держится этот домен: 2+ — это сетка, подсвечиваем отдельно.
                $brand['hosts'][$host]['brands'] = count($hostBrands[$host] ?? []);
            }
            $brand['own_doors'] = $ownDoors;
            $queries += count($brand['queries']);
            $rowsCount = 0;
            foreach ($brand['queries'] as $list) {
                $rowsCount += count($list);
            }
            $brand['counts'] = $counts;
            $brand['sites'] = count($brand['hosts']);
            $brand['rows'] = $rowsCount;
            $brand['query_count'] = count($brand['queries']);
            // Пересечения: сколько сайтов встретилось больше чем в одном ключе бренда и на разных брендах.
            $brand['crossed'] = count(array_filter($brand['hosts'], static fn (array $h): bool => $h['keys'] > 1));
            $brand['networked'] = count(array_filter($brand['hosts'], static fn (array $h): bool => $h['brands'] > 1));
            $out[] = $brand;
        }
        // Бренды по числу ключей: самые проработанные — сверху; «без бренда» всегда последним.
        arsort($ownAll['by_reason']);
        usort($out, static function (array $a, array $b): int {
            if (($a['key'] === '') !== ($b['key'] === '')) {
                return $a['key'] === '' ? 1 : -1;
            }

            return $b['query_count'] <=> $a['query_count'] ?: strcmp((string) $a['label'], (string) $b['label']);
        });

        return [
            'brands' => $out,
            'totals' => $totals,          // уникальные сайты по всем брендам, по типам
            'totals_sum' => $totalsSum,   // сумма по брендам: больше на величину повторов между брендами
            'repeats' => ['sites' => array_sum($repeats), 'by_type' => $repeats],
            'own' => $ownAll,
            'sites' => count($seenHost),
            'results' => $results,
            'queries' => $queries,
        ];
    }

    /**
     * ПОЧЕМУ сайт считается нашим; '' — не наш. HTML здесь нет (разбор строится по строкам выдачи),
     * поэтому судим ТОЛЬКО ПО ХОСТУ: накопленный список наших доменов (по нему узнаются и те, что
     * пришли повторами и уже не открывались) и метки наших шаблонов.
     *
     * Полный АДРЕС строки выдачи намеренно НЕ проверяем, хотя при визите он проверяется: там в адресе
     * есть цепочка редиректов, где и стоит наш редиректор, а здесь это просто страница чужого сайта —
     * и метка вроде «faro» помечала нашим любой чужой `site.top/faro-bonus`. Пользователь получил
     * «много доров определены как наши» на зонах, которых у него вообще нет.
     *
     * @param array<string, bool> $ourDomains
     * @param array<string, bool> $dorgenBases
     */
    private static function ownReason(string $host, ?OwnSites $own, array $ourDomains, array $dorgenBases = []): string
    {
        $host = Domains::normalize($host);
        if ($host === '') {
            return '';
        }
        // Выгрузка из системы запусков — первая и самая точная проверка: список даёт сама система,
        // гадать по меткам не нужно. Сверяем базу — последние две метки хоста (leebet.4916.team → 4916.team).
        if ($dorgenBases !== [] && isset($dorgenBases[\YandexSites\Dorgen\DorgenClient::baseOf($host)])) {
            return self::REASON_DORGEN;
        }
        if (isset($ourDomains[$host]) || isset($ourDomains[Domains::registrable($host)])) {
            return self::REASON_LIST;
        }
        if ($own === null || $own->isEmpty()) {
            return '';
        }
        $marker = $own->markerForHost($host);

        return $marker !== '' ? 'метка «' . $marker . '»' : '';
    }

    /**
     * Тип сайта: дор / тематический / соцсеть / известный сайт рунета / прочий.
     *
     * Порядок важен: поддомен вида vk.com/... или companies.rbc.ru — это не дор, а страница известного
     * сайта, поэтому списки проверяем ПЕРЕД правилом «поддомен = дор».
     */
    public static function classify(string $host, string $title = '', string $snippet = ''): string
    {
        $host = Domains::normalize($host);
        if ($host === '') {
            return 'other';
        }
        if (self::inList($host, self::SOCIAL)) {
            return 'social';
        }
        if (self::inList($host, self::known())) {
            return 'known';
        }
        if (Domains::registrable($host) !== $host) {
            return 'door';
        }

        return self::looksThematic($host, $title, $snippet) ? 'theme' : 'other';
    }

    /**
     * Компактный слепок сбора для сравнения со следующим: бренд → сайт → тип.
     *
     * @param array{brands: list<array<string, mixed>>} $analysis
     * @return array<string, array{label: string, hosts: array<string, string>}>
     */
    public static function index(array $analysis): array
    {
        $index = [];
        foreach ($analysis['brands'] as $brand) {
            $hosts = [];
            foreach ((array) $brand['hosts'] as $host => $info) {
                $hosts[(string) $host] = (string) $info['type'];
            }
            $index[(string) $brand['key']] = ['label' => (string) $brand['label'], 'hosts' => $hosts];
        }

        return $index;
    }

    /**
     * Что изменилось по сравнению с прошлым сбором: по каждому бренду — какие сайты появились и какие
     * пропали, с разбивкой по типу. Бренд, которого раньше не было, помечается `is_new`.
     *
     * @param array<string, array{label: string, hosts: array<string, string>}> $prev
     * @param array{brands: list<array<string, mixed>>} $analysis
     * @return array<string, mixed>
     */
    public static function diff(array $prev, array $analysis): array
    {
        $byBrand = [];
        $sum = ['added' => 0, 'removed' => 0];
        foreach ($analysis['brands'] as $brand) {
            $key = (string) $brand['key'];
            $now = [];
            foreach ((array) $brand['hosts'] as $host => $info) {
                $now[(string) $host] = (string) $info['type'];
            }
            $was = $prev[$key]['hosts'] ?? [];
            $added = array_diff_key($now, $was);
            $removed = array_diff_key($was, $now);
            if ($added === [] && $removed === [] && isset($prev[$key])) {
                continue; // бренд не изменился — в списке изменений его нет
            }
            $byBrand[$key] = [
                'label' => (string) $brand['label'],
                'is_new' => !isset($prev[$key]),
                'added' => self::countTypes($added),
                'removed' => self::countTypes($removed),
                'added_hosts' => array_slice(array_keys($added), 0, 50),
                'removed_hosts' => array_slice(array_keys($removed), 0, 50),
            ];
            $sum['added'] += count($added);
            $sum['removed'] += count($removed);
        }
        // Бренды, которые были раньше, а сейчас не собрались вовсе.
        foreach ($prev as $key => $old) {
            if (isset($byBrand[$key])) {
                continue;
            }
            $found = false;
            foreach ($analysis['brands'] as $brand) {
                if ((string) $brand['key'] === (string) $key) {
                    $found = true;
                    break;
                }
            }
            if (!$found && $old['hosts'] !== []) {
                $byBrand[(string) $key] = [
                    'label' => (string) ($old['label'] ?? $key),
                    'is_new' => false,
                    'gone' => true,
                    'added' => self::countTypes([]),
                    'removed' => self::countTypes($old['hosts']),
                    'added_hosts' => [],
                    'removed_hosts' => array_slice(array_keys($old['hosts']), 0, 50),
                ];
                $sum['removed'] += count($old['hosts']);
            }
        }

        return ['brands' => $byBrand, 'totals' => $sum, 'compared_at' => date(DATE_ATOM)];
    }

    /**
     * Строки выдачи из results.csv: весь текущий сбор, со всеми повторами и отсеянными.
     *
     * @return \Generator<int, array{query: string, position: int, host: string, url: string, title: string, snippet: string, reason: string}>
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
            $at = static function (string $name) use ($header): int {
                $i = array_search($name, $header, true);

                return $i === false ? -1 : (int) $i;
            };
            $cols = ['query' => $at('query'), 'position' => $at('position'), 'host' => $at('host'),
                'url' => $at('url'), 'title' => $at('title'), 'snippet' => $at('snippet'), 'reason' => $at('result')];
            if ($cols['query'] < 0 || $cols['host'] < 0) {
                return;
            }
            while (($row = fgetcsv($fh, 0, $delimiter, '"', '')) !== false) {
                if (!isset($row[$cols['query']], $row[$cols['host']])) {
                    continue;
                }
                $get = static fn (string $name): string => $cols[$name] >= 0 ? (string) ($row[$cols[$name]] ?? '') : '';
                yield [
                    'query' => $get('query'),
                    'position' => (int) $get('position'),
                    'host' => $get('host'),
                    'url' => $get('url'),
                    'title' => $get('title'),
                    'snippet' => $get('snippet'),
                    'reason' => $get('reason'),
                ];
            }
        } finally {
            fclose($fh);
        }
    }

    /** Итог по типам одной строкой — для журнала и сообщения задания. */
    public static function totalsText(array $totals): string
    {
        $parts = [];
        foreach (self::TYPES as $type => $label) {
            $n = (int) ($totals[$type] ?? 0);
            if ($n > 0) {
                $parts[] = $label . ' — ' . $n;
            }
        }

        return implode(', ', $parts);
    }

    /**
     * @param array<string, string> $hosts host => type
     * @return array<string, int>
     */
    private static function countTypes(array $hosts): array
    {
        $counts = array_fill_keys(array_keys(self::TYPES), 0);
        $counts['total'] = 0;
        foreach ($hosts as $type) {
            if (isset($counts[$type])) {
                $counts[$type]++;
            }
            $counts['total']++;
        }

        return $counts;
    }

    /** Известные сайты рунета: список исключений по умолчанию МИНУС соцсети (у них свой тип). */
    private static function known(): array
    {
        static $known = null;
        if ($known === null) {
            $social = array_flip(self::SOCIAL);
            $known = array_values(array_filter(
                array_map(static fn (string $d): string => mb_strtolower($d), DefaultExclusions::LIST),
                static fn (string $d): bool => !isset($social[$d]),
            ));
        }

        return $known;
    }

    /**
     * @param list<string> $list
     */
    private static function inList(string $host, array $list): bool
    {
        foreach ($list as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                return true;
            }
        }

        return false;
    }

    /** Тема видна в адресе (casino-x.ru), в заголовке или в сниппете. */
    private static function looksThematic(string $host, string $title, string $snippet): bool
    {
        $addr = mb_strtolower($host);
        foreach (self::THEME_EN as $word) {
            if (str_contains($addr, $word)) {
                return true;
            }
        }
        $text = mb_strtolower(trim($title . ' ' . $snippet));
        if ($text === '') {
            return false;
        }
        foreach (self::THEME_RU as $word) {
            if (mb_strpos($text, $word) !== false) {
                return true;
            }
        }
        foreach (self::THEME_EN as $word) {
            if (preg_match('~(?<![a-z])' . preg_quote($word, '~') . '~u', $text) === 1) {
                return true;
            }
        }

        return false;
    }
}

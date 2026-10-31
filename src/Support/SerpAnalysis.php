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
    /** ЕДИНСТВЕННАЯ причина «наш»: сайт запущен в системе запусков (список даёт сама система). */
    public const REASON_DORGEN = 'запущен в dorgen';

    /** Индекс прошлого сбора для сравнения — рядом с историей, переживает обновление кода. */
    public const INDEX_FILE = 'serp-prev.json';

    /** Разница с прошлым сбором, посчитанная в конце сбора (лежит в папке прогона). */
    public const DIFF_FILE = 'serp-diff.json';

    /** Типы сайтов в порядке показа. */
    /**
     * ПРИБЛИЗИТЕЛЬНЫЕ доли кликов по позиции — ими считается «видимость» сайта по бренду.
     *
     * Точных цифр по чужой выдаче ни у кого нет, и выдавать их за трафик нельзя. Но сравнивать
     * конкурентов между собой они позволяют честно: первое место стоит примерно вдвое дороже
     * второго и в разы дороже пятого, и именно это отличает «держит бренд» от «просто присутствует».
     * Ниже десятого места вес одинаково мал — там уже не про трафик.
     *
     * @var array<int, float>
     */
    public const CTR = [1 => 0.35, 2 => 0.17, 3 => 0.11, 4 => 0.08, 5 => 0.06,
        6 => 0.05, 7 => 0.04, 8 => 0.03, 9 => 0.025, 10 => 0.02];

    /** Вес позиции за пределами первой десятки. */
    public const CTR_TAIL = 0.01;

    /**
     * ЧЕМ ЗАБРАН БРЕНД: дорами, не дорами или и теми и другими (гибрид).
     *
     * Считается по ДОЛЕ ВИДИМОСТИ, а не по числу сайтов: десять доров ниже десятого места и один
     * официальный сайт на первом — это бренд, забранный НЕ дорами, хотя доров в списке больше.
     * Границы намеренно широкие: в середине лежит ровно то, что имеет смысл называть гибридом.
     */
    public const CAPTURE_DOOR = 70.0;

    /** Ниже этой доли доров бренд считается забранным НЕ дорами. */
    public const CAPTURE_OTHER = 30.0;

    /**
     * Сколько бренда должен забирать ОДИН дор, чтобы считать, что доры здесь берут (порог задал
     * пользователь). Отвечает на вопрос, которого нет в `door_share`: та доля — СУММА всех доров,
     * и в ней тонет главное. Бренд может быть «забран не дорами» (все доры вместе 18%), а один дор
     * при этом держать 12% — значит, лезть туда дором МОЖНО. И наоборот: двадцать доров по 1% в
     * хвосте топа дают заметную сумму, но ни один из них ничего не забирает.
     * Читают отсюда и страница, и выгрузка, и журнал задания — расходиться им нельзя.
     */
    public const DOOR_SHARE_MIN = 5.0;

    /** Сколько брендов перечислять в одной ячейке выгрузки доменов: дальше ячейка нечитаема. */
    private const BRANDS_IN_CELL = 12;

    /** Подписи типов захвата (ключ `capture` бренда). */
    public const CAPTURE = [
        'door' => 'забран дорами',
        'mixed' => 'гибрид',
        'other' => 'забран не дорами',
    ];

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
     * @param OwnSites|null $own список запущенных доменов из системы запусков: по нему и только по нему
     *        дор помечается «наш» (сверка по базе = регистрируемому домену хоста)
     * @return array<string, mixed>
     */
    public static function build(iterable $rows, int $top = 10, ?OwnSites $own = null, ?int $now = null): array
    {
        $now ??= time();
        $brands = [];
        $results = 0;
        $freshRows = 0;   // строк, по которым выдача отдала отметку переобхода
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
            // Свежесть документа по выдаче: в results.csv она уже абсолютная (живая выдача переводит
            // «8 ч назад» в метку времени при разборе), поэтому здесь просто читаем.
            $fresh = Freshness::parse((string) ($row['modtime'] ?? ''), $now);
            if ($fresh !== null) {
                $freshRows++;
            }
            $weight = self::CTR[$position] ?? self::CTR_TAIL;
            $brands[$bucket]['queries'][$query][] = [
                'position' => $position,
                'host' => $host,
                'url' => (string) ($row['url'] ?? ''),
                'title' => (string) ($row['title'] ?? ''),
                'type' => $type,
                'reason' => (string) ($row['reason'] ?? ''),
                'fresh' => $fresh,
                'fresh_label' => Freshness::label($fresh, $now),
            ];
            if (!isset($brands[$bucket]['hosts'][$host])) {
                $reason = self::ownReason($host, $own);
                $brands[$bucket]['hosts'][$host] = ['type' => $type, 'keys' => [], 'count' => 0,
                    'own' => $reason !== '', 'own_reason' => $reason,
                    'best' => $position, 'top3' => 0, 'vis' => 0.0, 'fresh' => null];
            }
            $brands[$bucket]['hosts'][$host]['keys'][$query] = true;
            $brands[$bucket]['hosts'][$host]['count']++;
            // Видимость копится ПО СТРОКАМ: сайт на пяти ключах в топ-3 весит больше, чем на одном.
            $brands[$bucket]['hosts'][$host]['vis'] += $weight;
            $brands[$bucket]['hosts'][$host]['best'] = min($brands[$bucket]['hosts'][$host]['best'], $position);
            $brands[$bucket]['hosts'][$host]['top3'] += $position <= 3 ? 1 : 0;
            if ($fresh !== null) {
                // Самая СВЕЖАЯ из страниц сайта: по ней видно, когда он в нише появился/обновился.
                $brands[$bucket]['hosts'][$host]['fresh'] = max($brands[$bucket]['hosts'][$host]['fresh'] ?? 0, $fresh);
            }
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
            // КТО ЗАБИРАЕТ БРЕНД. Доля видимости = вес позиций сайта к весу всех позиций бренда:
            // «присутствует на всех ключах десятым» и «держит первое место» наконец перестают
            // выглядеть одинаково, а по доле лидера сразу видно, насколько бренд вообще занят.
            $visTotal = 0.0;
            $doorVis = 0.0;
            foreach ($brand['hosts'] as $info) {
                $visTotal += (float) $info['vis'];
                if ($info['type'] === 'door') {
                    $doorVis += (float) $info['vis'];
                }
            }
            $freshSites = 0;
            foreach ($brand['hosts'] as $host => $info) {
                $brand['hosts'][$host]['share'] = $visTotal > 0 ? round(100 * $info['vis'] / $visTotal, 1) : 0.0;
                $brand['hosts'][$host]['vis'] = round((float) $info['vis'], 4);
                $days = Freshness::days($info['fresh'], $now);
                $brand['hosts'][$host]['fresh_days'] = $days;
                $brand['hosts'][$host]['fresh_label'] = Freshness::label($info['fresh'], $now);
                if ($days !== null && $days <= Freshness::FRESH_DAYS) {
                    $freshSites++;
                }
            }
            // Таблица «кто забирает бренд»: сайты по доле видимости, сверху — победитель.
            $board = [];
            foreach ($brand['hosts'] as $host => $info) {
                $board[] = ['host' => $host] + array_intersect_key($info, array_flip(
                    ['type', 'own', 'own_reason', 'keys', 'count', 'brands', 'best', 'top3', 'share', 'fresh_days', 'fresh_label'],
                ));
            }
            usort($board, static fn (array $a, array $b): int => $b['share'] <=> $a['share'] ?: $a['best'] <=> $b['best']);
            $brand['board'] = $board;
            $brand['leader'] = $board[0] ?? null;
            // Наш лучший — чтобы отрыв «победитель против нас» читался без поиска глазами.
            $ourBest = null;
            foreach ($board as $row) {
                if ($row['own']) {
                    $ourBest = $row;
                    break;
                }
            }
            $brand['our_best'] = $ourBest;
            $brand['our_share'] = $ourBest !== null ? $ourBest['share'] : 0.0;
            $brand['fresh_sites'] = $freshSites;
            $brand['own_doors'] = $ownDoors;
            // ЧЕМ ЗАБРАН БРЕНД. Доля видимости доров, а не их число: именно по ней бренды делятся на
            // «массово доры», «не доры» и гибриды, и именно это решает, лезть ли в бренд дором вообще.
            $brand['door_share'] = $visTotal > 0 ? round(100 * $doorVis / $visTotal, 1) : 0.0;
            $brand['capture'] = self::captureOf($brand['door_share']);
            $brand['capture_label'] = self::CAPTURE[$brand['capture']];
            // ЕСТЬ ЛИ ЗДЕСЬ ДОР, КОТОРЫЙ РЕАЛЬНО ЗАБИРАЕТ (см. DOOR_SHARE_MIN). Доска уже
            // отсортирована по доле, поэтому первый дор в ней и есть лучший.
            $bestDoor = null;
            $strongDoors = 0;
            foreach ($board as $row) {
                if ($row['type'] !== 'door') {
                    continue;
                }
                $bestDoor ??= $row;
                if ((float) $row['share'] >= self::DOOR_SHARE_MIN) {
                    $strongDoors++;
                }
            }
            $brand['door_best'] = $bestDoor !== null ? (float) $bestDoor['share'] : 0.0;
            $brand['door_best_host'] = $bestDoor !== null ? (string) $bestDoor['host'] : '';
            // Чей он: чужой дор на 12% — это доказательство, что место берётся, и нас там нет.
            $brand['door_best_own'] = $bestDoor !== null && !empty($bestDoor['own']);
            $brand['doors_strong'] = $strongDoors;
            $brand['strong_door'] = $strongDoors > 0;
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
        $capture = ['door' => 0, 'mixed' => 0, 'other' => 0, 'nobrand' => 0];
        $captureLeader = $capture;
        $strongDoorBrands = 0;
        $realBrands = 0;
        foreach ($out as $brand) {
            if ($brand['key'] !== '') {
                $realBrands++;
                if ($brand['strong_door']) {
                    $strongDoorBrands++;
                }
            }
            // «без бренда» — не бренд, а остаток запросов: считаем его отдельно, иначе счёт брендов
            // по типу захвата врёт на одну строку, а сумма перестаёт сходиться с числом блоков.
            $bucket = $brand['key'] === '' ? 'nobrand' : $brand['capture'];
            $capture[$bucket]++;
            // ДОР ЛИ ПЕРВЫЙ — второй вопрос, и он не повторяет первый. На реальном сборе (165 брендов)
            // доры были 42% сайтов, но лишь 31% видимости: они заполняют хвост топа, а первое место
            // берут тематические домены и телеграм. «Гибрид» поэтому распадается надвое — бренды, где
            // дор уже стоит первым (доры там доказанно берут верх), и бренды, где они только в хвосте.
            if (!empty($brand['leader']['type']) && $brand['leader']['type'] === 'door') {
                $captureLeader[$bucket]++;
            }
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
            'capture' => $capture,       // брендов по тому, чем они забраны (+ отдельно «без бренда»)
            'capture_leader' => $captureLeader, // из них те, где ПЕРВЫЙ по видимости — дор
            // Брендов, где хотя бы один дор забирает ≥ DOOR_SHARE_MIN (и сколько брендов всего —
            // «без бренда» не в счёт, это остаток запросов, а не бренд).
            'strong_doors' => ['brands' => $strongDoorBrands, 'of' => $realBrands],
            'sites' => count($seenHost),
            'results' => $results,
            'queries' => $queries,
            // Сколько строк выдачи принесли отметку переобхода («8 ч назад», <modtime>). Ноль здесь
            // означает не «ничего свежего», а «источник её не отдал» — например, results.csv от сбора
            // до 1.42.0, где колонки modtime ещё не было. Без этого счётчика «свежих 0» читается
            // как измерение, хотя измерения не было вовсе.
            'freshness' => ['rows' => $freshRows, 'total' => $results],
        ];
    }

    /**
     * Короткий итог «кто забирает бренды» для журнала задания и сообщения о сборе: сколько брендов
     * забираем мы, сколько забрали чужие и в скольких топах стоят свежие (моложе двух суток) сайты.
     *
     * @param array<string, mixed> $analysis
     * @return array{ours: int, theirs: int, behind: int, nobody: int, fresh: int}
     */
    public static function leaders(array $analysis): array
    {
        $out = ['ours' => 0, 'theirs' => 0, 'behind' => 0, 'nobody' => 0, 'fresh' => 0];
        foreach ((array) ($analysis['brands'] ?? []) as $brand) {
            $leader = $brand['leader'] ?? null;
            if ($leader === null) {
                continue;
            }
            if (!empty($leader['own'])) {
                $out['ours']++;
            } else {
                $out['theirs']++;
                // Отдельно: мы в бренде ЕСТЬ, но первым стоит чужой — именно эти бренды и доигрываются.
                if ((float) ($brand['our_share'] ?? 0) > 0) {
                    $out['behind']++;
                } else {
                    $out['nobody']++;
                }
            }
            if ((int) ($brand['fresh_sites'] ?? 0) > 0) {
                $out['fresh']++;
            }
        }

        return $out;
    }

    /**
     * Тип захвата по доле видимости доров. Отдельный метод, чтобы границы были в ОДНОМ месте:
     * по ним считается и страница, и строка журнала, и выгрузка в CSV.
     */
    /**
     * ВСЕ САЙТЫ ВЫДАЧИ ОДНИМ СПИСКОМ — по строке на РАЗНЫЙ сайт, со всеми брендами, где он стоит.
     * Разбор по брендам отвечает «кто забрал бренд», а этот файл — «что это вообще за домены»:
     * его открывают отдельно, группируют по регистрируемому домену (сетка держит по дору на бренд)
     * и смотрят по типу. Поэтому тип — и колонка, и параметр: доры, тематические, прочие или все.
     * Числа сводятся ПО ВСЕМ брендам сайта: ключей и строк — сумма, лучшая позиция — минимум,
     * доля — МАКСИМАЛЬНАЯ из брендов (и рядом сказано, в каком именно: доля всегда внутри бренда,
     * общей доли по сбору не существует).
     *
     * @param array<string, mixed> $analysis
     * @param list<string> $types ключи `TYPES`; пустой список — все типы
     */
    public static function hostsCsv(array $analysis, array $types = [], string $delimiter = ';', bool $bom = true): string
    {
        $want = $types === [] ? null : array_flip($types);
        $leaderOf = [];
        $rows = [];
        foreach ((array) ($analysis['brands'] ?? []) as $brand) {
            $label = (string) $brand['label'];
            $leader = $brand['leader']['host'] ?? null;
            if ($leader !== null) {
                $leaderOf[(string) $leader] = ($leaderOf[(string) $leader] ?? 0) + 1;
            }
            foreach ((array) ($brand['hosts'] ?? []) as $host => $info) {
                $host = (string) $host;
                $type = (string) $info['type'];
                if ($want !== null && !isset($want[$type])) {
                    continue;
                }
                if (!isset($rows[$host])) {
                    $rows[$host] = ['host' => $host, 'registrable' => Domains::registrable($host),
                        'type' => $type, 'own' => !empty($info['own']),
                        'own_reason' => (string) ($info['own_reason'] ?? ''), 'brands' => [],
                        'keys' => 0, 'rows' => 0, 'best' => (int) $info['best'], 'top3' => 0,
                        'share' => 0.0, 'share_brand' => '', 'fresh_days' => null, 'fresh_label' => ''];
                }
                $row = &$rows[$host];
                $row['brands'][] = $label;
                $row['keys'] += (int) $info['keys'];
                $row['rows'] += (int) $info['count'];
                $row['best'] = min($row['best'], (int) $info['best']);
                $row['top3'] += (int) $info['top3'];
                if ((float) $info['share'] > $row['share']) {
                    $row['share'] = (float) $info['share'];
                    $row['share_brand'] = $label;
                }
                $days = $info['fresh_days'] ?? null;
                if ($days !== null && ($row['fresh_days'] === null || (int) $days < $row['fresh_days'])) {
                    $row['fresh_days'] = (int) $days;
                    $row['fresh_label'] = (string) ($info['fresh_label'] ?? '');
                }
                unset($row);
            }
        }
        // Сверху — то, с чего начинают разбор: сайты сразу на нескольких брендах (это сетка),
        // потом самые широкие по ключам. Остальное пользователь отсортирует у себя.
        uasort($rows, static fn (array $a, array $b): int => count($b['brands']) <=> count($a['brands'])
            ?: $b['keys'] <=> $a['keys'] ?: strcmp($a['host'], $b['host']));

        $out = fopen('php://temp', 'r+');
        if ($out === false) {
            return '';
        }
        if ($bom) {
            fwrite($out, "\xEF\xBB\xBF"); // иначе Excel открывает кириллицу кракозябрами
        }
        fputcsv($out, ['Сайт', 'Домен', 'Тип', 'Наш', 'Почему наш', 'Брендов', 'Бренды', 'Ключей',
            'Строк выдачи', 'Лучшая позиция', 'В топ-3', 'Лучшая доля в бренде %', 'Где эта доля',
            'Лидер в брендах', 'Свежесть'], $delimiter, '"', '');
        foreach ($rows as $row) {
            $brands = $row['brands'];
            $shown = array_slice($brands, 0, self::BRANDS_IN_CELL);
            if (count($brands) > self::BRANDS_IN_CELL) {
                $shown[] = '… ещё ' . (count($brands) - self::BRANDS_IN_CELL);
            }
            fputcsv($out, [
                $row['host'],
                $row['registrable'],
                self::TYPES[$row['type']] ?? $row['type'],
                $row['own'] ? 'да' : 'нет',
                $row['own_reason'],
                count($brands),
                implode(', ', $shown),
                $row['keys'],
                $row['rows'],
                $row['best'],
                $row['top3'],
                self::num($row['share']),
                $row['share_brand'],
                $leaderOf[$row['host']] ?? 0,
                $row['fresh_label'],
            ], $delimiter, '"', '');
        }
        rewind($out);
        $csv = (string) stream_get_contents($out);
        fclose($out);

        return $csv;
    }

    /**
     * Порог числом для подписи: «5», а не «5,0» — дробная часть в тексте только мешает.
     */
    public static function thresholdText(float $value): string
    {
        return rtrim(rtrim(number_format($value, 1, ',', ''), '0'), ',');
    }

    /**
     * «Дор забирает ≥ 5% в N брендах из M» — для журнала задания и сообщения о сборе. Отдельная
     * строка, а не часть `captureText()`: там счёт идёт по ТИПУ захвата (сумма доров), здесь — по
     * тому, берёт ли место ХОТЯ БЫ ОДИН дор, и эти два числа не складываются.
     *
     * @param array<string, mixed> $analysis
     */
    public static function strongDoorsText(array $analysis): string
    {
        $s = (array) ($analysis['strong_doors'] ?? []);

        return 'Берут ли место доры: хотя бы один дор забирает ≥ '
            . self::thresholdText(self::DOOR_SHARE_MIN) . '% в '
            . (int) ($s['brands'] ?? 0) . ' из ' . (int) ($s['of'] ?? 0) . ' брендов';
    }

    /**
     * Строка для журнала задания: принесла ли выдача отметку переобхода вообще. Пустая колонка
     * «Свежесть» на /serp — самый частый вопрос к этому блоку, и ответ на него почти всегда один:
     * источник её не отдал (или results.csv остался от сбора до 1.42.0). Ноль строк и «нет свежих
     * сайтов» — разные вещи, поэтому счётчик пишем отдельной строкой.
     *
     * @param array<string, mixed> $analysis
     */
    public static function freshnessText(array $analysis): string
    {
        $f = (array) ($analysis['freshness'] ?? []);
        $rows = (int) ($f['rows'] ?? 0);
        $total = (int) ($f['total'] ?? 0);
        if ($rows === 0) {
            return 'Отметка переобхода: выдача не вернула её ни по одной строке из ' . $total
                . ' — колонка «Свежесть» на /serp будет пустой'
                . ' (сбор до 1.42.0 или источник не отдаёт modtime)';
        }

        return 'Отметка переобхода: пришла у ' . $rows . ' строк из ' . $total
            . ' (' . self::thresholdText($total > 0 ? 100 * $rows / $total : 0.0) . '%)';
    }

    public static function captureOf(float $doorShare): string
    {
        if ($doorShare >= self::CAPTURE_DOOR) {
            return 'door';
        }

        return $doorShare <= self::CAPTURE_OTHER ? 'other' : 'mixed';
    }

    /**
     * Строка для журнала задания: сколько брендов забрано дорами, сколько гибридов, сколько не дорами.
     *
     * @param array<string, mixed> $analysis
     */
    public static function captureText(array $analysis): string
    {
        $c = (array) ($analysis['capture'] ?? []);
        $lead = (array) ($analysis['capture_leader'] ?? []);
        $part = static function (string $label, string $key) use ($c, $lead): string {
            $n = (int) ($c[$key] ?? 0);
            $l = (int) ($lead[$key] ?? 0);

            // «дор первым» — самое важное уточнение: без него «гибрид — 72» ничего не решает.
            return $label . ' — ' . $n . ($l > 0 ? ' (дор первым в ' . $l . ')' : '');
        };
        $parts = [$part('дорами', 'door'), $part('гибрид', 'mixed'), $part('не дорами', 'other')];
        if ((int) ($c['nobrand'] ?? 0) > 0) {
            $parts[] = 'без бренда — ' . (int) $c['nobrand'];
        }

        return implode(', ', $parts);
    }

    /**
     * ВЫГРУЗКА РАЗБОРА: одна строка на бренд со всеми числами — чтобы делить бренды самому
     * (в Excel, в скрипте, да хоть глазами), а не только фильтрами страницы.
     *
     * Строк выдачи здесь нет намеренно: их десятки тысяч, а решение принимается по бренду. Кто
     * именно забрал бренд — в колонке «Лидер», остальные сайты видно на самой странице.
     *
     * @param array<string, mixed> $analysis
     */
    public static function brandsCsv(array $analysis, string $delimiter = ';', bool $bom = true): string
    {
        $head = ['Бренд', 'Ключ', 'Чем забран', 'Доля доров %', 'Доров сайтов', 'Всего сайтов',
            'Ключей', 'Строк выдачи', 'Лидер', 'Доля лидера %', 'Тип лидера', 'Лидер наш',
            'Ключей у лидера', 'Лучшая позиция лидера', 'Наша доля %', 'Наш лучший сайт',
            'Наша лучшая позиция', 'Наших доров', 'Свежих сайтов', 'На нескольких брендах',
            'Пересечений внутри бренда'];
        foreach (self::TYPES as $label) {
            $head[] = $label;
        }
        $head[] = 'Появилось с прошлого сбора';
        $head[] = 'Пропало с прошлого сбора';
        // БЫЛО/СТАЛО по числам бренда (пусто, когда сравнивать не с чем — первый сбор или другая
        // глубина топа). Колонки В КОНЦЕ: старые фильтры в Excel от этого не разъезжаются.
        foreach (['Чем забран (прошлый сбор)', 'Доля доров % (прошлый)', 'Δ доля доров',
            'Лидер (прошлый)', 'Сменился лидер', 'Тип лидера (прошлый)', 'Сменился тип лидера',
            'Наша доля % (прошлый)', 'Δ наша доля'] as $h) {
            $head[] = $h;
        }
        // РОТАЦИЯ ЗА ВСЁ ОКНО СБОРОВ — отдельно от сравнения с прошлым: смена типа чаще всего
        // случилась не в последнем сборе, и тогда колонки «(прошлый)» выше о ней молчат.
        $head[] = 'Ротация типа за окно';
        $head[] = 'Сборов назад';
        // БЕРЁТ ЛИ ЗДЕСЬ ХОТЯ БЫ ОДИН ДОР: по сумме `Доля доров %` этого не видно.
        $thr = self::thresholdText(self::DOOR_SHARE_MIN);
        $head[] = 'Дор от ' . $thr . '%';
        $head[] = 'Доля лучшего дора %';
        $head[] = 'Лучший дор';
        $head[] = 'Лучший дор наш';
        $head[] = 'Доров от ' . $thr . '%';
        $out = fopen('php://temp', 'r+');
        if ($out === false) {
            return '';
        }
        if ($bom) {
            fwrite($out, "\xEF\xBB\xBF"); // иначе Excel открывает кириллицу кракозябрами
        }
        fputcsv($out, $head, $delimiter, '"', '');
        foreach ((array) ($analysis['brands'] ?? []) as $brand) {
            $leader = $brand['leader'] ?? null;
            $our = $brand['our_best'] ?? null;
            $diff = (array) ($brand['diff'] ?? []);
            $row = [
                (string) $brand['label'],
                (string) $brand['key'],
                self::CAPTURE[(string) ($brand['capture'] ?? 'other')] ?? '',
                self::num((float) ($brand['door_share'] ?? 0)),
                (int) (($brand['counts']['door'] ?? 0)),
                (int) ($brand['sites'] ?? 0),
                (int) ($brand['query_count'] ?? 0),
                (int) ($brand['rows'] ?? 0),
                $leader !== null ? (string) $leader['host'] : '',
                $leader !== null ? self::num((float) $leader['share']) : '',
                $leader !== null ? (self::TYPES[(string) $leader['type']] ?? '') : '',
                $leader !== null ? (!empty($leader['own']) ? 'да' : 'нет') : '',
                $leader !== null ? (int) $leader['keys'] : '',
                $leader !== null ? (int) $leader['best'] : '',
                self::num((float) ($brand['our_share'] ?? 0)),
                $our !== null ? (string) $our['host'] : '',
                $our !== null ? (int) $our['best'] : '',
                (int) ($brand['own_doors'] ?? 0),
                (int) ($brand['fresh_sites'] ?? 0),
                (int) ($brand['networked'] ?? 0),
                (int) ($brand['crossed'] ?? 0),
            ];
            foreach (array_keys(self::TYPES) as $type) {
                $row[] = (int) (($brand['counts'][$type] ?? 0));
            }
            $row[] = (int) ($diff['added']['total'] ?? 0);
            $row[] = (int) ($diff['removed']['total'] ?? 0);
            $ch = $brand['changed'] ?? null;
            if (is_array($ch) && empty($ch['is_new'])) {
                $row[] = self::CAPTURE[(string) $ch['cap_was']] ?? '';
                $row[] = self::num((float) $ch['ds_was']);
                $row[] = self::num((float) $ch['ds_delta']);
                $row[] = (string) $ch['lead_was'];
                $row[] = !empty($ch['lead_changed']) ? 'да' : 'нет';
                $row[] = self::TYPES[(string) ($ch['lt_was'] ?? '')] ?? '';
                $row[] = !empty($ch['lt_changed']) ? 'да' : 'нет';
                $row[] = self::num((float) $ch['os_was']);
                $row[] = self::num((float) $ch['os_delta']);
            } else {
                // Новый бренд или сравнивать не с чем: пустые ячейки, а не нули — ноль читался бы
                // как «было 0%», то есть как настоящее измерение.
                $row = array_merge($row, is_array($ch) && !empty($ch['is_new'])
                    ? ['новый бренд', '', '', '', '', '', '', '', '']
                    : ['', '', '', '', '', '', '', '', '']);
            }
            $flip = $brand['flip'] ?? null;
            $row[] = is_array($flip)
                ? ((self::TYPES[(string) $flip['from']] ?? $flip['from']) . ' → '
                    . (self::TYPES[(string) $flip['to']] ?? $flip['to']))
                : '';
            $row[] = is_array($flip) ? (int) $flip['ago'] : '';
            $row[] = !empty($brand['strong_door']) ? 'да' : 'нет';
            $row[] = self::num((float) ($brand['door_best'] ?? 0));
            $row[] = (string) ($brand['door_best_host'] ?? '');
            $row[] = ($brand['door_best_host'] ?? '') === '' ? '' : (!empty($brand['door_best_own']) ? 'да' : 'нет');
            $row[] = (int) ($brand['doors_strong'] ?? 0);
            fputcsv($out, $row, $delimiter, '"', '');
        }
        rewind($out);
        $csv = (string) stream_get_contents($out);
        fclose($out);

        return $csv;
    }

    /** Число для CSV: запятая как разделитель дроби — иначе Excel с русской локалью видит текст. */
    private static function num(float $value): string
    {
        return number_format($value, 1, ',', '');
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
     */
    private static function ownReason(string $host, ?OwnSites $own): string
    {
        if ($own === null || $own->isEmpty()) {
            return '';
        }
        $host = Domains::normalize($host);
        // ТОЛЬКО список из системы запусков. HTML здесь нет (разбор строится по строкам выдачи), и
        // гадать по адресу больше не нужно: раньше метка вроде «faro» помечала нашим любой чужой
        // site.top/faro-bonus, и пользователь получил «много доров определены как наши» в зонах,
        // которых у него нет вовсе.
        return $host !== '' && $own->matchesBase($host) ? self::REASON_DORGEN : '';
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
                // С ТИПОМ, а не просто именами: ротация видна не только по лидеру — топ течёт
                // постоянно, и «пришло 3 дора, ушло 2 тематических» и есть эта картина.
                'added_hosts' => self::withTypes($added),
                'removed_hosts' => self::withTypes($removed),
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
                'url' => $at('url'), 'title' => $at('title'), 'snippet' => $at('snippet'), 'reason' => $at('result'),
                // Свежесть пишется с 1.42.0; в results.csv прошлых сборов колонки нет — тогда -1 и ''.
                'modtime' => $at('modtime')];
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
                    'modtime' => $get('modtime'),
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
     * Список сайтов с их типом для разницы между сборами (срезан: 50 имён на бренд достаточно,
     * дальше это уже не чтение, а свалка).
     *
     * @param array<string, string> $hosts host => type
     * @return list<array{host: string, type: string}>
     */
    private static function withTypes(array $hosts): array
    {
        $out = [];
        foreach (array_slice($hosts, 0, 50, true) as $host => $type) {
            $out[] = ['host' => (string) $host, 'type' => (string) $type];
        }

        return $out;
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

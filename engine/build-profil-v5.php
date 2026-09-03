<?php
declare(strict_types=1);

/**
 * Сборка приёмочного профиля из корпуса доноров.
 *
 *   php engine/build-profil-v5.php <корпус> <выход.json> [--школа=проза] [--текст=<файл>]
 *
 * Профиль августа собирался руками, и повторить его было нечем: числа в нём
 * сходятся с `razbros-korpusa.php`, но связь держалась только на памяти.
 * Здесь та же арифметика записана скриптом: цель — медиана корпуса, полоса —
 * квартили, край — минимум и максимум, «держат» — поле, у которого в коридоре
 * приёмки сидит не меньше 70 % доноров.
 *
 * Прозаические разделы (запреты, структура, приёмы, регистр, семёрка…) числами
 * не выводятся: их пишет разбор. Файл `--текст=` подмешивается в результат,
 * поэтому пересборка профиля не стирает выводы.
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/PageMetrics.php';

const TIPY = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
const POROG_DERZHAT = 70;

$args = array_slice($argv, 1);
$shkola = '';
$tekstFile = '';
$semya = '';
$pos = [];
foreach ($args as $a) {
    if (str_starts_with($a, '--школа=')) { $shkola = substr($a, strlen('--школа=')); continue; }
    if (str_starts_with($a, '--текст=')) { $tekstFile = substr($a, strlen('--текст=')); continue; }
    if (str_starts_with($a, '--семья=')) { $semya = substr($a, strlen('--семья=')); continue; }
    $pos[] = $a;
}
if (count($pos) < 2) {
    fwrite(STDERR, "usage: php engine/build-profil-v5.php <корпус> <выход.json> [--школа=…] [--семья=A|B] [--текст=…]\n");
    exit(1);
}
[$root, $out] = $pos;
if (!is_dir($root)) { fwrite(STDERR, "нет папки: $root\n"); exit(1); }

/** Школа сайта — та же проверка, что в razbros-korpusa.php. */
const BLOCK_TAIL = '~(block|section|dashboard|hero|pillars|quotes-list|strip|panel|widget|banner|card)$~';
function shkolaSajta(string $dir): string
{
    $b = [];
    foreach (glob("$dir/*.html") ?: [] as $f) {
        preg_match_all('~<(?:section|div|article|aside)\s+class="([a-z][a-z0-9_-]*)((?:\s+[a-z0-9_-]+)*)"~i',
            (string) file_get_contents($f), $m, PREG_SET_ORDER);
        foreach ($m as $x) {
            if (preg_match(BLOCK_TAIL, $x[1]) || str_contains($x[2], 'variant-')) { $b[$x[1]] = 1; }
        }
    }
    return count($b) >= 5 ? 'конструктор' : 'проза';
}

/** У доноров попадается голая «<» внутри текста — иначе strip_tags глотает абзацами. */
function pochinit(string $h): string
{
    return (string) preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $h);
}

/**
 * Дубли в корпусе. В новой выкладке два имени несут побайтово один и тот же
 * комплект: без отсева такой сайт голосует за медиану дважды.
 */
function otseyatDubli(array $dirs): array
{
    $vidal = [];
    $out = [];
    foreach ($dirs as $d) {
        $h = [];
        foreach (TIPY as $t) { $h[] = is_file("$d/$t.html") ? md5_file("$d/$t.html") : ''; }
        $key = implode('|', $h);
        if (isset($vidal[$key])) {
            fwrite(STDERR, sprintf("дубль: %s повторяет %s — отброшен\n", basename($d), basename($vidal[$key])));
            continue;
        }
        $vidal[$key] = $d;
        $out[] = $d;
    }
    return $out;
}

/** Квартильная сводка одного ряда — тот же счёт, что у razbros-korpusa.php. */
function svodka(array $v): array
{
    sort($v);
    $n = count($v);
    $med = $n % 2 ? $v[intdiv($n, 2)] : ($v[$n / 2 - 1] + $v[$n / 2]) / 2;
    return [
        'низ' => round($v[(int) ($n * 0.25)], 2), 'медиана' => round($med, 2),
        'верх' => round($v[(int) ($n * 0.75)], 2),
        'нулей' => count(array_filter($v, fn($x) => $x == 0.0)), 'сайтов' => $n,
    ];
}

/**
 * Слияние измеренного профиля с писаным разбором: лист из файла текста
 * побеждает, но ветку с числами не сносит — иначе пересборка стирала бы
 * разделы вроде «бренд.правило», а правка текста — измеренные полосы.
 */
function slit(array $baza, array $sverhu): array
{
    foreach ($sverhu as $k => $v) {
        $baza[$k] = is_array($v) && isset($baza[$k]) && is_array($baza[$k]) ? slit($baza[$k], $v) : $v;
    }
    return $baza;
}

/**
 * Семья донора. Корпус распадается не по градиенту, а на два несмешивающихся
 * лагеря, и медиана между ними не описывает никого: у семьи A автора в тексте
 * нет вовсе (я/1000 = 1), у семьи B он герой рассказа (я/1000 = 26). Профиль,
 * собранный по всем сразу, требует одновременно быть спецификацией и
 * рассказчиком — его проходит один донор из тридцати восьми.
 *
 * Порог 8 на тысячу лежит в пустоте между лагерями: ближайшие значения — 4 и 18.
 */
const SEMYA_POROG = 8;
function semyaSajta(string $dir): string
{
    $f = "$dir/main.html";
    if (!is_file($f)) { return 'A'; }
    $t = preg_replace('~\s+~u', ' ', strip_tags(pochinit((string) file_get_contents($f))));
    $n = max(1, preg_match_all('~[А-Яа-яЁёA-Za-z0-9]+~u', (string) $t));
    $ya = preg_match_all('~\b(?:я|меня|мне|мной|мой|моя|мои|моих|моей|моего)\b~ui', (string) $t);
    return 1000 * $ya / $n > SEMYA_POROG ? 'B' : 'A';
}

/**
 * Стилевые меры, которых нет в PageMetrics и которые именно поэтому выпали из
 * работы: приёмка их не считает, писатель их не видит. В профиль они идут
 * справочным блоком — не порогом, а описанием того, чем семья держится.
 */
const STIL_SENSOR = '~свет|тускл|мигн|гул|шип|звук|звон|шёпот|шепч|холод|тепл|туман|запах|дрож|палец|пальц|ладон|чашк|кофе|лампа|вентилятор|тишин|сумерк|кухн|полноч|темнот~iu';
const STIL_ARKA   = '~завязк|кульминац|конфликт|развязк|первый кадр|последний кадр|сцена|финал|начало:|итог:~iu';
const STIL_TEH    = '~\b(?:SSL|TLS|HTTPS?|KYC|AML|SHA-?256|PCI-?DSS|API|SIEM|OTP|SMS|BTC|ETH|USDT|LTC|XRP|QIWI|PaySafe|Visa|Mir|TRC-?20|ERC-?20|RTP|ADR|APK|Android|iOS|Chrome|Safari|Firefox|Curacao|Antillephone|MGA|Telegram)\b~u';
function stilStranicy(string $html): array
{
    $t = (string) preg_replace('~\s+~u', ' ', strip_tags($html));
    $n = max(1, preg_match_all('~[А-Яа-яЁёA-Za-z0-9]+~u', $t));
    $slova = [];
    preg_match_all('~[А-Яа-яЁё]{5,}~u', mb_strtolower($t), $m);
    foreach ($m[0] as $w) { $slova[$w] = ($slova[$w] ?? 0) + 1; }
    arsort($slova);
    $motiv = $slova ? reset($slova) : 0;
    return [
        'я_на_1000'      => round(1000 * preg_match_all('~\b(?:я|меня|мне|мной|мой|моя|мои|моих|моей|моего)\b~ui', $t) / $n, 1),
        'сенсорных'      => preg_match_all(STIL_SENSOR, $t),
        'реплик_от_12'   => preg_match_all('~[«"][^«»"]{12,}[»"]~u', $t),
        'слов_арки'      => preg_match_all(STIL_ARKA, $t),
        'тех_на_1000'    => round(1000 * preg_match_all(STIL_TEH, $t) / $n, 1),
        'мотив_на_1000'  => round(1000 * $motiv / $n, 1),
        'прошедших'      => preg_match_all('~\b[а-яё]{3,}(?:л|ла|ли|лся|лась)\b~ui', $t),
        'настоящих'      => preg_match_all('~\b[а-яё]{3,}(?:ю|ешь|ет|ем|ете|ут|ют|ит|ат|ят)\b~ui', $t),
    ];
}

$dirs = glob(rtrim($root, '/') . '/*', GLOB_ONLYDIR) ?: [];
if ($shkola !== '') { $dirs = array_values(array_filter($dirs, fn($d) => shkolaSajta($d) === $shkola)); }
if ($semya !== '') { $dirs = array_values(array_filter($dirs, fn($d) => semyaSajta($d) === $semya)); }
$dirs = otseyatDubli($dirs);
if (!$dirs) { fwrite(STDERR, "нечего мерить\n"); exit(1); }

$a = new Analyzer();
$stranicy = [];
$polnyj = [];
$razmetka = [];
$brendPo = [];
$zhanrSyr = [];
$stilSyr = [];
$brendSet = [];   // сайт → ['лат' => сумма по семи, 'кир' => …]
$ssylok = [];     // тип → ряд числа внутренних ссылок
foreach (TIPY as $tip) {
    $rows = [];
    foreach ($dirs as $dir) {
        $f = "$dir/$tip.html";
        if (!is_file($f)) { continue; }
        $html = pochinit((string) file_get_contents($f));
        $rows[] = PageMetrics::measure($a, $tip, $html, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
        $ssylok[$tip][] = preg_match_all('~<a\s[^>]*href="/[^"]*"~i', $html);
        $zhanrSyr[$tip]['цитат'][] = preg_match_all('~<blockquote\b~i', $html);
        $zhanrSyr[$tip]['таблиц'][] = preg_match_all('~<table\b~i', $html);
        foreach (stilStranicy($html) as $k => $v) { $stilSyr[$tip][$k][] = (float) $v; }
        $s = end($rows);
        $b = basename($dir);
        $brendSet[$b]['лат'] = ($brendSet[$b]['лат'] ?? 0) + (int) $s['brand_en'];
        $brendSet[$b]['кир'] = ($brendSet[$b]['кир'] ?? 0) + (int) $s['brand_ru'];
    }
    if (!$rows) { continue; }

    // Разметочная тройка и школа бренда идут мимо «держат»: разброс широкий,
    // но нулей у доноров почти нет — приём есть у всех, меняется доза.
    foreach (['strong', 'h3_colon_pct', 'emoji'] as $k) {
        $razmetka[$tip][$k] = svodka(array_map(fn($r) => (float) $r[$k], $rows));
    }
    foreach (['лат' => 'brand_en', 'кир' => 'brand_ru'] as $pismo => $k) {
        $brendPo[$tip][$pismo] = svodka(array_map(fn($r) => (float) $r[$k], $rows));
    }

    $polya = [];
    $derzhat = 0;
    foreach (PageMetrics::FIELDS as $k => [$label, $isRate]) {
        $v = [];
        foreach ($rows as $r) { if (isset($r[$k]) && is_numeric($r[$k])) { $v[] = (float) $r[$k]; } }
        if (!$v) { continue; }
        sort($v);
        $n = count($v);
        $med = $n % 2 ? $v[intdiv($n, 2)] : ($v[$n / 2 - 1] + $v[$n / 2]) / 2;
        // Коридор приёмки: |наше − цель| ≤ max(0,25·цель; пол).
        $floor = $isRate ? 0.8 : 2.0;
        $vKoridore = count(array_filter($v, fn($x) => abs($x - $med) <= max(0.25 * $med, $floor)));
        $dolya = (int) round($vKoridore / $n * 100);
        $derzh = $dolya >= POROG_DERZHAT;
        if ($derzh) { $derzhat++; }
        $polya[$k] = [
            'цель' => round($med, 2), 'дробное' => (bool) $isRate, 'держат' => $derzh,
            'полоса' => [round($v[(int) ($n * 0.25)], 2), round($v[(int) ($n * 0.75)], 2)],
            'край' => [round($v[0], 2), round($v[$n - 1], 2)],
            'доля_доноров_в_коридоре' => $dolya,
        ];
        if ($tip === 'main') {
            $polnyj[$k] = [
                'подпись' => $label, 'цель' => round($med, 2), 'дробное' => (bool) $isRate, 'держат' => $derzh,
                'полоса' => [round($v[(int) ($n * 0.25)], 2), round($v[(int) ($n * 0.75)], 2)],
                'край' => [round($v[0], 2), round($v[$n - 1], 2)],
                'доля_доноров_в_коридоре' => $dolya,
            ];
        }
    }
    // Сначала то, что фабрика держит: по этому порядку профиль и читают.
    uasort($polya, fn($x, $y) => [$y['держат'], 0] <=> [$x['держат'], 0]);
    // Жанровая карточка типа: то, что попадает в задание писателю.
    $med = fn(array $v) => svodka($v)['медиана'];
    $stranicy[$tip] = ['поля' => $polya, 'держат_полей' => $derzhat, 'жанр' => [
        'слов' => (int) round($med(array_map(fn($r) => (float) $r['words'], $rows))),
        'цитат' => (int) round($med(array_map('floatval', $zhanrSyr[$tip]['цитат']))),
        'таблиц' => (int) round($med(array_map('floatval', $zhanrSyr[$tip]['таблиц']))),
        'пар_faq' => (int) round($med(array_map(fn($r) => (float) $r['faq_pairs'], $rows))),
        'ссылок' => (int) round($med(array_map('floatval', $ssylok[$tip]))),
        'списков' => (int) round($med(array_map(fn($r) => (float) $r['lists'], $rows))),
        'ol_pct' => (int) round($med(array_map(fn($r) => (float) $r['ordered_pct'], $rows))),
    ]];
}

$brendSum = [
    'лат' => svodka(array_map(fn($x) => (float) $x['лат'], $brendSet)),
    'кир' => svodka(array_map(fn($x) => (float) $x['кир'], $brendSet)),
];
$sGlavnoy = svodka(array_map('floatval', $ssylok['main'] ?? [0]));

$profil = [
    'версия' => 'v5-1',
    'источник' => [
        'корпус' => $root,
        'школа' => $shkola ?: 'все',
        'сайтов' => count($dirs),
        'страница' => 'main',
        'собран' => 'php engine/build-profil-v5.php ' . implode(' ', $args),
    ],
    'приёмка' => [
        'правило' => 'цель — медиана корпуса, полоса — квартили, край — минимум и максимум',
        'коридор' => '|наше − цель| ≤ max(0,25·цель; пол), пол 2 для счётчиков и 0,8 для долей',
        'требовать' => 'только поля с держат=true: в коридоре сидит не меньше ' . POROG_DERZHAT . ' % доноров',
    ],
];
$profil['поля'] = $polnyj;
$profil['страницы'] = $stranicy;
$profil['разметка'] = ['страницы' => $razmetka];
$profil['бренд'] = ['латиничная' => ['страницы' => $brendPo, 'сумма' => $brendSum]];
$profil['граф'] = ['ссылок_с_главной' => $sGlavnoy];

$stil = [];
foreach ($stilSyr as $tip => $polya) {
    foreach ($polya as $k => $ryad) { $stil[$tip][$k] = svodka($ryad)['медиана']; }
}
$profil['семья'] = $semya ?: 'все';
$profil['стиль'] = [
    'правило' => 'справочные меры: приёмка их не считает, но семья держится именно на них',
    'страницы' => $stil,
];

if ($tekstFile !== '') {
    if (!is_file($tekstFile)) { fwrite(STDERR, "нет файла текста: $tekstFile\n"); exit(1); }
    $t = json_decode((string) file_get_contents($tekstFile), true);
    if (!is_array($t)) { fwrite(STDERR, "текст не разобрался как JSON: $tekstFile\n"); exit(1); }
    $profil = slit($profil, $t);
}

file_put_contents($out, json_encode($profil, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n");
printf("%s: %d сайтов, %d типов\n", $out, count($dirs), count($stranicy));
foreach ($stranicy as $t => $s) { printf("  %-12s держат %2d из %d\n", $t, $s['держат_полей'], count($s['поля'])); }

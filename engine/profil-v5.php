<?php
declare(strict_types=1);

/**
 * Профиль поколения v5 — двенадцатистраничник, снятый с корпуса доноров.
 *
 *   php engine/profil-v5.php [папка] [--json] [--тихо]
 *
 * v3 мерил двенадцать страниц по ОДНОМУ донору (связка Pin Up) — полосу там
 * взять было неоткуда, и `profile-bundle.json` держал голые значения одного
 * набора. Здесь доноров двенадцать, поэтому впервые считается то же, что в v4:
 * медиана как цель и доля доноров внутри коридора как признак «фабрика это
 * держит».
 *
 * Два корпусных факта, ради которых скрипт не сводится к вызову
 * razbros-korpusa.php двенадцать раз:
 *
 *  1. В корпусе есть пара наборов-близнецов (один прогон фабрики с разными
 *     сидами чисел): десять страниц из двенадцати совпадают дословно. Если
 *     обе половины близнеца попадут в статистику, они удвоят свой вес в
 *     медиане. Близнецы ищутся по шинглам и вторая половина исключается.
 *  2. Полоса берётся по p10/p90, а не по «медиана ± четверть»: у части полей
 *     распределение односторонее (нули у половины доноров), и симметричный
 *     коридор для них бессмысленен.
 */

require_once __DIR__ . '/src/PageMetrics.php';
require_once __DIR__ . '/instrumenty/shingle.php';

const V5_TYPES = ['main', 'obzor', 'promo', 'news', 'info', 'partnery',
                  'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];

/** Донор пишет голую «<» внутри текста — strip_tags глотает от неё до «>». */
function v5Pochinit(string $h): string
{
    return preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $h);
}

/**
 * Близнецы: доля совпавших шинглов ≥ 95 % хотя бы на трёх типах страниц.
 * Совпадение на одной странице бывает и у независимых наборов — блок
 * библиотеки без подстановок. Три страницы подряд — это уже один прогон.
 */
function v5Bliznecy(string $root, array $sites): array
{
    $sh = [];
    foreach ($sites as $s) {
        foreach (V5_TYPES as $t) {
            $f = "$root/$s/$t.html";
            $sh[$s][$t] = is_file($f) ? shingles(chist((string) file_get_contents($f))) : [];
        }
    }
    $pары = [];
    foreach ($sites as $i => $a) {
        foreach ($sites as $j => $b) {
            if ($j <= $i) { continue; }
            $совпало = [];
            foreach (V5_TYPES as $t) {
                $x = $sh[$a][$t]; $y = $sh[$b][$t];
                if (!$x || !$y) { continue; }
                $p = count(array_intersect_key($x, $y)) / max(1, min(count($x), count($y))) * 100;
                if ($p >= 95) { $совпало[] = $t; }
            }
            if (count($совпало) >= 3) { $pары[] = [$a, $b, $совпало]; }
        }
    }
    return $pары;
}

function v5Percentil(array $v, float $p): float
{
    $n = count($v);
    if ($n === 1) { return $v[0]; }
    $i = ($n - 1) * $p;
    $lo = (int) floor($i); $hi = (int) ceil($i);
    return $v[$lo] + ($v[$hi] - $v[$lo]) * ($i - $lo);
}

// ── сбор корпуса ────────────────────────────────────────────────────
$asJson = in_array('--json', $argv, true);
$тихо   = in_array('--тихо', $argv, true);
$позиц  = array_values(array_filter(array_slice($argv, 1), fn($a) => $a[0] !== '-'));
$root   = rtrim($позиц[0] ?? 'samples/v5-donors', '/');
// Папку выкладок можно увести в сторону: так рядом живут профили разных
// корпусов, как data-v3-bundle рядом с data-v3-single у прошлого поколения.
$данные = __DIR__ . '/data-v5';
foreach (array_slice($argv, 1) as $a) {
    if (str_starts_with($a, '--данные=')) { $данные = rtrim(substr($a, strlen('--данные=')), '/'); }
}
if (!is_dir($root)) { fwrite(STDERR, "нет папки $root\n"); exit(1); }

$sites = [];
foreach (glob("$root/*", GLOB_ONLYDIR) ?: [] as $d) { $sites[] = basename($d); }
sort($sites);
if (!$sites) { fwrite(STDERR, "корпус пуст\n"); exit(1); }

$пары = v5Bliznecy($root, $sites);
$исключены = [];
foreach ($пары as [$a, $b, $где]) { if (!in_array($a, $исключены, true)) { $исключены[] = $b; } }
$рабочие = array_values(array_diff($sites, $исключены));

// ── замер ───────────────────────────────────────────────────────────
$a = new Analyzer();
$карточки = [];
foreach ($рабочие as $s) {
    foreach (V5_TYPES as $t) {
        $f = "$root/$s/$t.html";
        if (!is_file($f)) { continue; }
        $карточки[$t][$s] = PageMetrics::measure($a, $t, v5Pochinit((string) file_get_contents($f)),
            ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    }
}

$страницы = [];
foreach (V5_TYPES as $t) {
    if (empty($карточки[$t])) { continue; }
    $поля = [];
    $держат = 0;
    foreach (PageMetrics::FIELDS as $k => [$подпись, $дробное]) {
        $v = [];
        foreach ($карточки[$t] as $c) { if (isset($c[$k]) && is_numeric($c[$k])) { $v[] = (float) $c[$k]; } }
        if (!$v) { continue; }
        sort($v);
        $n = count($v);
        $med = v5Percentil($v, 0.5);
        $пол = $дробное ? 0.8 : 2.0;
        $вКоридоре = count(array_filter($v, fn($x) => abs($x - $med) <= max(0.25 * abs($med), $пол)));
        $доля = (int) round($вКоридоре / $n * 100);
        $жёстко = $доля >= 70;
        if ($жёстко) { $держат++; }
        $поля[$k] = [
            'подпись' => $подпись,
            'цель'    => round($med, 2),
            'дробное' => (bool) $дробное,
            'держат'  => $жёстко,
            'полоса'  => [round(v5Percentil($v, 0.1), 2), round(v5Percentil($v, 0.9), 2)],
            'край'    => [round($v[0], 2), round($v[$n - 1], 2)],
            'доля_доноров_в_коридоре' => $доля,
        ];
    }
    uasort($поля, fn($x, $y) => $y['доля_доноров_в_коридоре'] <=> $x['доля_доноров_в_коридоре']);
    $страницы[$t] = ['поля' => $поля, 'держат_полей' => $держат, 'доноров' => count($карточки[$t])];
}

// ── граф ссылок комплекта ───────────────────────────────────────────
$адреса = [];
$изТипа = [];
foreach ($рабочие as $s) {
    foreach (V5_TYPES as $t) {
        $f = "$root/$s/$t.html";
        if (!is_file($f)) { continue; }
        preg_match_all('~href="(/[^"#]*)"~', (string) file_get_contents($f), $m);
        foreach ($m[1] as $u) { $адреса[$u] = ($адреса[$u] ?? 0) + 1; }
        $изТипа[$t][$s] = count($m[1]);
    }
}
arsort($адреса);
$ссылки = [];
foreach ($изТипа as $t => $v) {
    $vv = array_values($v); sort($vv);
    $ссылки[$t] = ['цель' => round(v5Percentil($vv, 0.5)), 'полоса' => [round(v5Percentil($vv, 0.1)), round(v5Percentil($vv, 0.9))]];
}

// ── уникальность: естественный уровень корпуса ──────────────────────
$уник = [];
foreach (V5_TYPES as $t) {
    $sh = [];
    foreach ($рабочие as $s) {
        $f = "$root/$s/$t.html";
        if (is_file($f)) { $sh[$s] = shingles(chist((string) file_get_contents($f))); }
    }
    $v = [];
    $ks = array_keys($sh);
    foreach ($ks as $i => $x) {
        foreach ($ks as $j => $y) {
            if ($j <= $i) { continue; }
            $v[] = count(array_intersect_key($sh[$x], $sh[$y])) / max(1, min(count($sh[$x]), count($sh[$y]))) * 100;
        }
    }
    if (!$v) { continue; }
    sort($v);
    $уник[$t] = ['медиана' => round(v5Percentil($v, 0.5), 1), 'потолок' => round(v5Percentil($v, 0.9), 1),
                 'край' => [round($v[0], 1), round($v[count($v) - 1], 1)]];
}

$профиль = [
    'версия'   => 'v5-1',
    'источник' => [
        'корпус'     => $root,
        'наборов'    => count($sites),
        'в_расчёте'  => count($рабочие),
        'исключены'  => $исключены,
        'близнецы'   => array_map(fn($p) => ['пара' => [$p[0], $p[1]], 'совпало' => $p[2]], $пары),
        'страниц'    => count($рабочие) * count(V5_TYPES),
        'типы'       => V5_TYPES,
    ],
    'принцип' => 'Воспроизвести фабрику, а не превзойти её: цель — медиана корпуса, '
        . 'требуются только поля с держат=true. Полоса p10–p90, коридор приёмки — '
        . '|наше − цель| ≤ max(0,25·|цель|; пол), пол 2 для счётчиков и 0,8 для долей.',
    'приёмка' => [
        'правило'  => '|наше − цель| ≤ max(0,25·|цель|; пол), пол 2 для счётчиков и 0,8 для долей',
        'требовать' => 'поля с держат=true; порог прохождения 95 % полей типа',
    ],
    'страницы' => $страницы,
    'ссылки'   => ['адреса_корпуса' => $адреса, 'на_страницу' => $ссылки],
    'уникальность' => [
        'мера' => 'шинглы 6 слов по chist(), пересечение к меньшему множеству, %',
        'по_типам' => $уник,
        'правило' => 'новый набор против каждого донора и против наших наборов — '
            . 'не выше «потолка» типа (p90 корпуса): фабрика сама держит этот уровень',
    ],
];

if (!is_dir($данные)) { mkdir($данные, 0777, true); }
file_put_contents("$данные/profil-v5.json",
    json_encode($профиль, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");

if ($asJson) { echo json_encode($профиль, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n"; exit(0); }
if ($тихо) { exit(0); }

printf("══ профиль v5: %d наборов, в расчёте %d, %d страниц ══\n\n",
    count($sites), count($рабочие), count($рабочие) * count(V5_TYPES));
foreach ($пары as [$x, $y, $где]) {
    printf("близнецы: %s ↔ %s — дословно совпало %d страниц (%s); %s исключён\n",
        $x, $y, count($где), implode(', ', $где), $y);
}
echo "\n";
printf("%-14s %8s %8s %s\n", 'тип', 'полей', 'держат', 'самые жёсткие');
echo str_repeat('─', 78), "\n";
foreach ($страницы as $t => $p) {
    $топ = array_slice(array_keys(array_filter($p['поля'], fn($f) => $f['держат'])), 0, 5);
    printf("%-14s %8d %8d  %s\n", $t, count($p['поля']), $p['держат_полей'], implode(', ', $топ));
}
echo "\nуникальность внутри корпуса (шинглы, %):\n";
foreach ($уник as $t => $u) {
    printf("  %-14s медиана %5.1f  потолок %5.1f  край %.1f–%.1f\n",
        $t, $u['медиана'], $u['потолок'], $u['край'][0], $u['край'][1]);
}
echo "\nадреса корпуса: ";
foreach ($адреса as $u => $n) { echo "{$u}×{$n}  "; }
printf("\n\nзаписано: %s/profil-v5.json\n", $данные);

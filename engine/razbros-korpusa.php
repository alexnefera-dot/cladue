<?php
declare(strict_types=1);

/**
 * Разброс каждого параметра по корпусу.
 *
 *   php engine/razbros-korpusa.php <папка> [main] [--школа=конструктор|проза] [--json]
 *
 * Замер одной страницы против эталона отвечает «сходится или нет». На пятидесяти
 * генерациях можно спросить другое: **какие параметры фабрика вообще держит**.
 * Если поле у пятидесяти независимых страниц лежит в узкой полосе — это
 * настройка генератора. Если гуляет вдвое-втрое — фабрика его не держит, и
 * подгонять нас под его медиану значит подгоняться под шум.
 *
 * Порядок вывода — по коэффициенту вариации, снизу вверх: сверху то, что
 * держится, снизу то, что свободно.
 */

require_once __DIR__ . '/src/PageMetrics.php';

$root = $argv[1] ?? '';
$page = 'main';
$shkola = '';
$asJson = in_array('--json', $argv, true);
foreach (array_slice($argv, 2) as $a) {
    if (str_starts_with($a, '--школа=')) { $shkola = substr($a, strlen('--школа=')); }
    elseif ($a[0] !== '-') { $page = $a; }
}
if ($root === '' || !is_dir($root)) {
    fwrite(STDERR, "usage: php engine/razbros-korpusa.php <папка> [main] [--школа=…] [--json]\n");
    exit(1);
}

/** Школы делятся по устройству, а не по тексту: считаем виджеты из библиотеки. */
const BLOCK_TAIL = '~(block|section|dashboard|hero|pillars|quotes-list|strip|panel|widget|banner|card)$~';

function shkolaSajta(string $dir): string
{
    $b = [];
    foreach (glob("$dir/*.html") ?: [] as $f) {
        $h = (string) file_get_contents($f);
        preg_match_all('~<(?:section|div|article|aside)\s+class="([a-z][a-z0-9_-]*)((?:\s+[a-z0-9_-]+)*)"~i',
            $h, $m, PREG_SET_ORDER);
        foreach ($m as $x) {
            if (preg_match(BLOCK_TAIL, $x[1]) || str_contains($x[2], 'variant-')) { $b[$x[1]] = 1; }
        }
    }
    return count($b) >= 5 ? 'конструктор' : 'проза';
}

/**
 * У доноров попадается голая «<» внутри текста (`<td evolution="" gaming<="">`).
 * strip_tags глотает от неё до следующего «>» — на одном файле так пропало
 * 46 КБ из 58. Экранируем всё, что не начало тега.
 */
function pochinit(string $h): string
{
    return preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $h);
}

$a = new Analyzer();
$rows = [];
foreach (glob(rtrim($root, '/') . '/*', GLOB_ONLYDIR) ?: [] as $dir) {
    $f = "$dir/$page.html";
    if (!is_file($f)) { continue; }
    $sh = shkolaSajta($dir);
    if ($shkola !== '' && $sh !== $shkola) { continue; }
    $html = pochinit((string) file_get_contents($f));
    $card = PageMetrics::measure($a, $page, $html, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $card['__сайт'] = basename($dir);
    $card['__школа'] = $sh;
    $rows[] = $card;
}
if (!$rows) { fwrite(STDERR, "нечего мерить\n"); exit(1); }

// ── разброс ─────────────────────────────────────────────────────────
$stat = [];
foreach (PageMetrics::FIELDS as $k => [$label, $isRate]) {
    $v = [];
    foreach ($rows as $r) { if (isset($r[$k]) && is_numeric($r[$k])) { $v[] = (float) $r[$k]; } }
    if (!$v) { continue; }
    sort($v);
    $n = count($v);
    $mean = array_sum($v) / $n;
    $med = $n % 2 ? $v[intdiv($n, 2)] : ($v[$n / 2 - 1] + $v[$n / 2]) / 2;
    $var = 0.0;
    foreach ($v as $x) { $var += ($x - $mean) ** 2; }
    $sd = sqrt($var / $n);
    $q1 = $v[(int) ($n * 0.25)];
    $q3 = $v[(int) ($n * 0.75)];
    $nulls = count(array_filter($v, fn($x) => $x == 0.0));
    // Коэффициент вариации от медианы: среднее у полей с выбросами врёт.
    $cv = $med != 0.0 ? $sd / $med * 100 : ($mean != 0.0 ? $sd / $mean * 100 : 0.0);
    // Полоса «медиана ± четверть» — тот же коридор, по которому идёт приёмка.
    $floor = $isRate ? 0.8 : 2.0;
    $inCorridor = count(array_filter($v, fn($x) => abs($x - $med) <= max(0.25 * $med, $floor)));
    $stat[$k] = [
        'подпись' => $label, 'дробное' => (bool) $isRate,
        'медиана' => round($med, 2), 'среднее' => round($mean, 2), 'σ' => round($sd, 2),
        'CV%' => round($cv, 1), 'мин' => round($v[0], 2), 'макс' => round($v[$n - 1], 2),
        'q1' => round($q1, 2), 'q3' => round($q3, 2),
        'нулей' => $nulls, 'в коридоре' => $inCorridor, 'из' => $n,
        'держится%' => round($inCorridor / $n * 100),
    ];
}

// Сортировка: сначала то, что фабрика реально держит.
uasort($stat, function ($x, $y) {
    return [$y['держится%'], -$x['CV%']] <=> [$x['держится%'], -$y['CV%']];
});

if ($asJson) {
    echo json_encode(['страница' => $page, 'школа' => $shkola ?: 'все', 'сайтов' => count($rows),
        'разброс' => $stat, 'карточки' => $rows], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}

$pad = function (string $s, int $w, bool $left = false): string {
    $p = str_repeat(' ', max(0, $w - mb_strlen($s)));
    return $left ? $s . $p : $p . $s;
};

printf("══ %s / %s: %d сайтов ══\n\n", basename(rtrim($root, '/')), $page . ($shkola ? " · $shkola" : ''), count($rows));
echo $pad('поле', 20, true) . $pad('медиана', 9) . $pad('σ', 8) . $pad('CV%', 7)
    . $pad('мин', 8) . $pad('q1', 8) . $pad('q3', 8) . $pad('макс', 8)
    . $pad('нулей', 7) . $pad('держится', 10) . "\n";
echo str_repeat('─', 93), "\n";
$grup = ['держится' => [], 'плывёт' => [], 'не держится' => []];
foreach ($stat as $k => $s) {
    $g = $s['держится%'] >= 70 ? 'держится' : ($s['держится%'] >= 40 ? 'плывёт' : 'не держится');
    $grup[$g][] = $k;
    echo $pad($k, 20, true)
        . $pad((string) $s['медиана'], 9) . $pad((string) $s['σ'], 8) . $pad((string) $s['CV%'], 7)
        . $pad((string) $s['мин'], 8) . $pad((string) $s['q1'], 8) . $pad((string) $s['q3'], 8)
        . $pad((string) $s['макс'], 8) . $pad((string) $s['нулей'], 7)
        . $pad($s['держится%'] . '%', 10) . "\n";
}
echo "\n";
foreach ($grup as $g => $list) { printf("%-13s %2d: %s\n", $g, count($list), implode(', ', $list)); }
echo "\n";

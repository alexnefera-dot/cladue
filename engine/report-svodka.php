<?php
declare(strict_types=1);

/**
 * Сводка «референс и N наборов по нему» — одной таблицей на референс.
 *
 *   php report-svodka.php <out.html> <дир-референса>|<подпись> <дир>|<подпись> ...
 *   (можно повторить блок несколько раз через --razdel=<заголовок>)
 *
 * Строки — параметры приёмки, колонки — наборы, ячейка красная, если значение
 * вышло из коридора относительно референса. Внизу каждой таблицы — пересечение
 * набора с референсом и худшая страница: параметры и уникальность это два
 * разных шлюза, и смотреть их порознь неудобно.
 */

require_once __DIR__ . '/src/PageMetrics.php';

$OUT = $argv[1] ?? '/tmp/svodka.html';
$blocks = []; $cur = null;
foreach (array_slice($argv, 2) as $a) {
    if (preg_match('~^--razdel=(.*)$~', $a, $m)) {
        if ($cur) { $blocks[] = $cur; }
        $cur = ['title' => $m[1], 'cols' => []];
        continue;
    }
    [$dir, $label] = array_pad(explode('|', $a, 2), 2, '');
    if (!is_dir($dir)) { fwrite(STDERR, "нет папки: $dir\n"); exit(1); }
    if ($cur === null) { $cur = ['title' => '', 'cols' => []]; }
    $cur['cols'][] = ['dir' => rtrim($dir, '/'), 'label' => $label !== '' ? $label : basename($dir)];
}
if ($cur) { $blocks[] = $cur; }
if (!$blocks) { fwrite(STDERR, "usage: report-svodka.php <out.html> [--razdel=…] <dir|label>…\n"); exit(1); }

$an = new Analyzer();

function shingles(string $file, int $n = 6): array
{
    $t = mb_strtolower(strip_tags(NicheLexicon::unplaceholder((string) file_get_contents($file))));
    $t = preg_replace('~[^\p{L}\p{N}]+~u', ' ', $t);
    $w = preg_split('~\s+~u', trim((string) $t), -1, PREG_SPLIT_NO_EMPTY);
    $o = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $o[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $o;
}
function jacc(array $a, array $b): float
{
    return $a && $b ? round(count(array_intersect_key($a, $b)) / count($a + $b) * 100, 2) : 0.0;
}

$h = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$B = [];
$B[] = '<meta charset="utf-8"><title>Наборы против референса</title>';
$B[] = '<style>
:root{--bg:#fdfdfc;--fg:#1a1c20;--mut:#666c75;--line:#e2e4e8;--ok:#2f6f4f;--bad:#a8323f;--card:#f5f6f8;--accent:#2b5f8f}
@media (prefers-color-scheme:dark){:root{--bg:#131519;--fg:#e6e8ec;--mut:#949aa4;--line:#282c33;--ok:#6fbf8f;--bad:#e08290;--card:#191c21;--accent:#7fb0dd}}
:root[data-theme=dark]{--bg:#131519;--fg:#e6e8ec;--mut:#949aa4;--line:#282c33;--ok:#6fbf8f;--bad:#e08290;--card:#191c21;--accent:#7fb0dd}
:root[data-theme=light]{--bg:#fdfdfc;--fg:#1a1c20;--mut:#666c75;--line:#e2e4e8;--ok:#2f6f4f;--bad:#a8323f;--card:#f5f6f8;--accent:#2b5f8f}
body{background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:32px 20px}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:28px;margin:0 0 6px;text-wrap:balance}
h2{font-size:21px;margin:40px 0 8px;padding-top:18px;border-top:1px solid var(--line)}
h3{font-size:13px;margin:24px 0 6px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
p.lead{color:var(--mut);margin:0 0 16px;max-width:70ch}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:6px 11px;text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal}
thead th{color:var(--mut);font-weight:600;font-size:13px}
thead th.ref{color:var(--fg)}
thead th.set{color:var(--accent)}
tbody tr:hover{background:var(--card)}
tr.page td{background:var(--card);font-weight:600}
.bad{color:var(--bad);font-weight:700}
.ok{color:var(--ok)}
.tot{font-weight:700}
</style>';
$B[] = '<div class="wrap"><h1>Наборы против референса</h1>';
$B[] = '<p class="lead">Мерка та же, по которой идёт приёмка: ' . count(PageMetrics::fields(false))
     . ' параметра на страницу, коридор ±25% (не меньше 2 для счётных и 0.8 для долей). '
     . 'Красным — значения вне коридора относительно референса.</p>';

foreach ($blocks as $blk) {
    $ref = $blk['cols'][0];
    $sets = array_slice($blk['cols'], 1);
    if ($blk['title'] !== '') { $B[] = '<h2>' . $h($blk['title']) . '</h2>'; }

    $types = [];
    foreach (glob("{$ref['dir']}/*.html") as $f) { $types[] = pathinfo($f, PATHINFO_FILENAME); }
    sort($types);

    // мерка
    $M = [];
    foreach ($blk['cols'] as $i => $c) {
        foreach ($types as $t) {
            $f = "{$c['dir']}/$t.html";
            if (is_file($f)) { $M[$i][$t] = PageMetrics::measure($an, $t, (string) file_get_contents($f)); }
        }
    }

    // итог по каждому набору
    $score = [];
    foreach ($sets as $k => $c) {
        $i = $k + 1; $hit = 0; $cnt = 0;
        foreach ($types as $t) {
            if (!isset($M[$i][$t], $M[0][$t])) { continue; }
            foreach (PageMetrics::fields(false) as $key => [$lab, $rate]) {
                $cnt++;
                if (!PageMetrics::off($M[$i][$t][$key], $M[0][$t][$key], (bool) $rate)) { $hit++; }
            }
        }
        $score[$i] = [$hit, $cnt];
    }

    $B[] = '<h3>Итог по наборам</h3><div class="scroll"><table><thead><tr><th>набор</th><th>совпало параметров</th><th>пересечение с референсом</th><th>худшая страница</th></tr></thead><tbody>';
    foreach ($sets as $k => $c) {
        $i = $k + 1;
        $shA = []; $shB = []; $worst = 0;
        foreach ($types as $t) {
            if (!is_file("{$c['dir']}/$t.html") || !is_file("{$ref['dir']}/$t.html")) { continue; }
            $a = shingles("{$c['dir']}/$t.html"); $b = shingles("{$ref['dir']}/$t.html");
            $worst = max($worst, jacc($a, $b));
            $shA += $a; $shB += $b;
        }
        [$hit, $cnt] = $score[$i];
        $B[] = '<tr><td>' . $h($c['label']) . '</td>'
             . '<td class="tot">' . $hit . '/' . $cnt . ' = ' . ($cnt ? round($hit / $cnt * 100) : 0) . '%</td>'
             . '<td>' . jacc($shA, $shB) . '%</td><td>' . $worst . '%</td></tr>';
    }
    $B[] = '</tbody></table></div>';

    // параметры постранично
    $B[] = '<h3>Параметры постранично</h3><div class="scroll"><table><thead><tr><th>параметр</th><th class="ref">' . $h($ref['label']) . '</th>';
    foreach ($sets as $c) { $B[] = '<th class="set">' . $h($c['label']) . '</th>'; }
    $B[] = '</tr></thead><tbody>';
    foreach ($types as $t) {
        if (!isset($M[0][$t])) { continue; }
        $B[] = '<tr class="page"><td colspan="' . (count($sets) + 2) . '">' . $h($t) . '.html</td></tr>';
        foreach (PageMetrics::fields(false) as $key => [$lab, $rate]) {
            $B[] = '<tr><td>' . $h($lab) . '</td><td>' . $h((string) $M[0][$t][$key]) . '</td>';
            foreach ($sets as $k => $c) {
                $i = $k + 1;
                $v = $M[$i][$t][$key] ?? '—';
                $cls = isset($M[$i][$t]) && PageMetrics::off($v, $M[0][$t][$key], (bool) $rate) ? ' class="bad"' : ' class="ok"';
                $B[] = '<td' . $cls . '>' . $h((string) $v) . '</td>';
            }
            $B[] = '</tr>';
        }
    }
    $B[] = '</tbody></table></div>';
}
$B[] = '</div>';

file_put_contents($OUT, implode("\n", $B));
printf("→ %s (%d разделов)\n", $OUT, count($blocks));
echo "STATUS " . json_encode(['file' => $OUT, 'blocks' => count($blocks)]) . "\n";

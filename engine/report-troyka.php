<?php
declare(strict_types=1);

/**
 * Отчёт «три набора рядом»: образец, прежний повтор и новый вариант.
 *
 *   php report-troyka.php <out.html> <дир-образца>|<подпись> <дир-A>|<подпись> <дир-B>|<подпись>
 *
 * Считает ровно ту мерку, по которой идёт приёмка (PageMetrics), плюс попарные
 * пересечения по шинглам и куски текста в сравнении: зачин, один и тот же
 * раздел, врезка. Числа без текста мало что говорят: набор может сойтись по
 * двадцати параметрам и читаться иначе, поэтому рядом с каждой строкой таблицы
 * лежит то, из чего она сложилась.
 */

require_once __DIR__ . '/src/PageMetrics.php';

$OUT = $argv[1] ?? '/tmp/troyka.html';
$NOTES = '';
$COLS = [];
foreach (array_slice($argv, 2) as $a) {
    // вычитку человек пишет руками: её нельзя вывести из чисел, а без неё
    // отчёт остаётся ведомостью
    if (preg_match('~^--notes=(.*)$~', $a, $nm)) { $NOTES = is_file($nm[1]) ? (string) file_get_contents($nm[1]) : ''; continue; }
    [$dir, $label] = array_pad(explode('|', $a, 2), 2, '');
    if (!is_dir($dir)) { fwrite(STDERR, "нет папки: $dir\n"); exit(1); }
    $COLS[] = ['dir' => rtrim($dir, '/'), 'label' => $label !== '' ? $label : basename($dir)];
}
if (count($COLS) < 2) {
    fwrite(STDERR, "usage: report-troyka.php <out.html> <dir|label> <dir|label> [dir|label]\n");
    exit(1);
}

$TYPES = ['main', 'vhod', 'zerkalo', 'registracia', 'bonus', 'slots', 'app'];
$an = new Analyzer();

/** мерка всех страниц каждой колонки */
$M = [];
foreach ($COLS as $i => $c) {
    foreach ($TYPES as $t) {
        $f = "{$c['dir']}/$t.html";
        if (!is_file($f)) { continue; }
        $M[$i][$t] = PageMetrics::measure($an, $t, (string) file_get_contents($f));
    }
}

/** шинглы для попарных пересечений */
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
    if (!$a || !$b) { return 0.0; }
    return round(count(array_intersect_key($a, $b)) / count($a + $b) * 100, 2);
}

$SH = [];
foreach ($COLS as $i => $c) {
    $all = [];
    foreach ($TYPES as $t) { if (is_file("{$c['dir']}/$t.html")) { $all += shingles("{$c['dir']}/$t.html"); } }
    $SH[$i] = $all;
}

/** куски текста: зачин, первый H2 с его абзацем, первая врезка */
function pieces(string $file): array
{
    $raw = (string) file_get_contents($file);
    $txt = fn($s) => trim(preg_replace('~\s+~u', ' ', strip_tags($s)));

    $out = ['opener' => '', 'h2' => '', 'para' => '', 'quote' => '', 'headings' => []];
    if (preg_match('~<p\b[^>]*>(.*?)</p>~is', $raw, $m)) { $out['opener'] = $txt($m[1]); }
    if (preg_match('~<h2[^>]*>(.*?)</h2>~is', $raw, $m)) { $out['h2'] = $txt($m[1]); }
    // абзац из середины страницы — он показывает ритм лучше зачина
    if (preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $m)) {
        $ps = array_values(array_filter(array_map($txt, $m[1]), fn($x) => mb_strlen($x) > 200));
        if ($ps) { $out['para'] = $ps[(int) (count($ps) / 2)]; }
    }
    if (preg_match('~<blockquote[^>]*>(.*?)</blockquote>~is', $raw, $m)) { $out['quote'] = $txt($m[1]); }
    if (preg_match_all('~<h2[^>]*>(.*?)</h2>~is', $raw, $m)) {
        $out['headings'] = array_slice(array_map($txt, $m[1]), 0, 9);
    }
    return $out;
}

$P = [];
foreach ($COLS as $i => $c) { $P[$i] = pieces("{$c['dir']}/main.html"); }

/** сборка html */
$h = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
$B = [];
$B[] = '<meta charset="utf-8"><title>Три набора рядом</title>';
$B[] = '<style>
/* Нейтральные тона уведены в холодную сторону — под синий акцент таблиц;
   чистый серый читался бы как «не выбирали». */
:root{--bg:#fdfdfc;--fg:#1a1c20;--mut:#666c75;--line:#e2e4e8;--ok:#2f6f4f;--bad:#a8323f;--card:#f5f6f8;--accent:#2b5f8f}
@media (prefers-color-scheme:dark){:root{--bg:#131519;--fg:#e6e8ec;--mut:#949aa4;--line:#282c33;--ok:#6fbf8f;--bad:#e08290;--card:#191c21;--accent:#7fb0dd}}
:root[data-theme=dark]{--bg:#131519;--fg:#e6e8ec;--mut:#949aa4;--line:#282c33;--ok:#6fbf8f;--bad:#e08290;--card:#191c21;--accent:#7fb0dd}
:root[data-theme=light]{--bg:#fdfdfc;--fg:#1a1c20;--mut:#666c75;--line:#e2e4e8;--ok:#2f6f4f;--bad:#a8323f;--card:#f5f6f8;--accent:#2b5f8f}
body{background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:32px 20px}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:28px;line-height:1.2;margin:0 0 6px;text-wrap:balance}
h2{font-size:20px;margin:38px 0 10px;padding-top:16px;border-top:1px solid var(--line);text-wrap:balance}
h3{font-size:13px;margin:22px 0 8px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
p.lead{color:var(--mut);margin:0 0 18px;max-width:68ch}
.wrap>p{max-width:68ch}
.scroll{overflow-x:auto;border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:7px 12px;text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal}
thead th{color:var(--mut);font-weight:600;font-size:13px}
thead th:not(:first-child){color:var(--accent)}
tbody tr:hover{background:var(--card)}
.ok{color:var(--ok)}.bad{color:var(--bad);font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.card .who{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--accent);margin-bottom:10px}
.card p{margin:0}
.q{border-left:3px solid var(--accent);padding-left:12px;color:var(--mut);font-style:italic}
ul.hd{margin:0;padding-left:18px;font-size:14px}ul.hd li{margin:4px 0}
</style>';
$B[] = '<div class="wrap"><h1>Три набора рядом</h1>';
$B[] = '<p class="lead">Мерка та же, по которой идёт приёмка: ' . count(PageMetrics::FIELDS)
     . ' параметров на страницу, коридор ±25% (не меньше 2 для счётных и 0.8 для долей). '
     . 'Красным помечено то, что вышло за коридор относительно первой колонки.</p>';

// ——— вычитка
if ($NOTES !== '') {
    $B[] = '<h2>Вычитка</h2>';
    foreach (preg_split('~\n{2,}~', trim($NOTES)) as $block) {
        $lines = preg_split('~\n~', trim($block));
        if (str_starts_with(trim($lines[0]), '## ')) {
            $B[] = '<h3>' . $h(trim(substr(trim($lines[0]), 3))) . '</h3>';
            array_shift($lines);
        }
        $items = array_values(array_filter($lines, fn($l) => str_starts_with(trim($l), '- ')));
        if (count($items) === count(array_filter($lines, fn($l) => trim($l) !== ''))) {
            $B[] = '<ul class="hd">';
            foreach ($items as $l) { $B[] = '<li>' . $h(trim(substr(trim($l), 2))) . '</li>'; }
            $B[] = '</ul>';
        } elseif (trim(implode(' ', $lines)) !== '') {
            $B[] = '<p>' . $h(trim(implode(' ', $lines))) . '</p>';
        }
    }
}

// ——— пересечения
$B[] = '<h2>Пересечение текстов</h2>';
$B[] = '<p class="lead">Доля общих шестисловных отрезков. Порог приёмки — 6%; свои наборы по одному донору обычно дают 0.1–1%.</p>';
$B[] = '<div class="scroll"><table><thead><tr><th></th>';
foreach ($COLS as $c) { $B[] = '<th>' . $h($c['label']) . '</th>'; }
$B[] = '</tr></thead><tbody>';
foreach ($COLS as $i => $ci) {
    $B[] = '<tr><td>' . $h($ci['label']) . '</td>';
    foreach ($COLS as $j => $cj) {
        $v = $i === $j ? '—' : jacc($SH[$i], $SH[$j]) . '%';
        $B[] = '<td>' . $v . '</td>';
    }
    $B[] = '</tr>';
}
$B[] = '</tbody></table></div>';

// ——— параметры по страницам
foreach ($TYPES as $t) {
    if (!isset($M[0][$t])) { continue; }
    $B[] = '<h2>' . $h($t) . '.html</h2><div class="scroll"><table><thead><tr><th>параметр</th>';
    foreach ($COLS as $c) { $B[] = '<th>' . $h($c['label']) . '</th>'; }
    $B[] = '</tr></thead><tbody>';
    foreach (PageMetrics::FIELDS as $k => [$lab, $rate]) {
        $B[] = '<tr><td>' . $h($lab) . '</td>';
        foreach ($COLS as $i => $c) {
            $v = $M[$i][$t][$k] ?? '—';
            $cls = '';
            if ($i > 0 && isset($M[0][$t][$k])) {
                $cls = PageMetrics::off($v, $M[0][$t][$k], (bool) $rate) ? ' class="bad"' : ' class="ok"';
            }
            $B[] = '<td' . $cls . '>' . $h((string) $v) . '</td>';
        }
        $B[] = '</tr>';
    }
    // словарь терминов — поимённо
    $keys = [];
    foreach ($COLS as $i => $c) { foreach (($M[$i][$t]['terms'] ?? []) as $k2 => $v2) { $keys[$k2] = 1; } }
    foreach (array_keys($keys) as $k2) {
        $B[] = '<tr><td style="color:var(--mut)">· ' . $h($k2) . '</td>';
        foreach ($COLS as $i => $c) { $B[] = '<td>' . (int) ($M[$i][$t]['terms'][$k2] ?? 0) . '</td>'; }
        $B[] = '</tr>';
    }
    $B[] = '</tbody></table></div>';
}

// ——— куски текста
$B[] = '<h2>Тексты рядом: главная</h2>';
foreach ([['opener', 'Зачин страницы'], ['h2', 'Первый заголовок'], ['para', 'Абзац из середины'], ['quote', 'Первая врезка']] as [$key, $title]) {
    $any = false;
    foreach ($P as $p) { if (($p[$key] ?? '') !== '') { $any = true; } }
    if (!$any) { continue; }
    $B[] = '<h3>' . $h($title) . '</h3><div class="cards">';
    foreach ($COLS as $i => $c) {
        $txt = $P[$i][$key] ?? '';
        $B[] = '<div class="card"><div class="who">' . $h($c['label']) . '</div>'
             . ($key === 'quote' ? '<p class="q">' : '<p>') . $h(mb_substr($txt, 0, 900)) . '</p></div>';
    }
    $B[] = '</div>';
}
$B[] = '<h3>Заголовки H2 подряд</h3><div class="cards">';
foreach ($COLS as $i => $c) {
    $B[] = '<div class="card"><div class="who">' . $h($c['label']) . '</div><ul class="hd">';
    foreach ($P[$i]['headings'] as $x) { $B[] = '<li>' . $h($x) . '</li>'; }
    $B[] = '</ul></div>';
}
$B[] = '</div></div>';

file_put_contents($OUT, implode("\n", $B));
printf("→ %s (%d колонок, %d страниц)\n", $OUT, count($COLS), count($TYPES));
echo "STATUS " . json_encode(['file' => $OUT, 'cols' => count($COLS)]) . "\n";

<?php
declare(strict_types=1);

/**
 * Отчёт «рядом»: наш комплект против донорского, блок к блоку и поле к полю.
 *
 *   php engine/ryadom-v5.php <наша-папка> [донор] [--выход=reports/v5/<имя>.html]
 *
 * Донор по умолчанию — ближайший: тот, с кем у набора наибольшее среднее
 * совпадение шинглов. Сравнивать с ним честнее всего: если наш текст где-то
 * повторяет корпус, повторяет он именно его.
 *
 * На каждую из двенадцати страниц собирается две таблицы.
 *
 *  · **Текст рядом.** Обе страницы режутся на блоки (виджет, H2, H3, абзац,
 *    список) и выравниваются по типам через LCS — пропущенный или лишний блок
 *    сразу виден пустой ячейкой. У каждого блока стоит объём в словах и доля
 *    совпавших с соседом шинглов: видно не только «похоже», но и насколько.
 *  · **Все параметры.** Полсотни полей `PageMetrics` разом: наше значение,
 *    донорское, цель корпуса, полоса p10–p90 и держит ли это поле фабрика.
 *    Поля, которые фабрика не держит, показываются серым — по ним расхождение
 *    ничего не значит, у самих доноров они гуляют вдвое.
 */

require_once __DIR__ . '/src/V5Blocks.php';
require_once __DIR__ . '/src/PageMetrics.php';
require_once __DIR__ . '/instrumenty/shingle.php';

$позиц = array_values(array_filter(array_slice($argv, 1), fn($a) => $a[0] !== '-'));
$наш = rtrim($позиц[0] ?? '', '/');
$донорИмя = $позиц[1] ?? '';
$корпус = 'samples/v5-donors';
$выход = '';
foreach (array_slice($argv, 1) as $a) {
    if (str_starts_with($a, '--выход=')) { $выход = substr($a, strlen('--выход=')); }
    elseif (str_starts_with($a, '--корпус=')) { $корпус = rtrim(substr($a, strlen('--корпус=')), '/'); }
}
if ($наш === '' || !is_dir($наш)) {
    fwrite(STDERR, "usage: php engine/ryadom-v5.php <наша-папка> [донор] [--выход=…]\n"); exit(1);
}
$выход = $выход !== '' ? $выход : 'reports/v5/ryadom-' . basename($наш) . '.html';
$профиль = json_decode((string) file_get_contents(__DIR__ . '/data-v5/profil-v5.json'), true);

// ── выбор донора ────────────────────────────────────────────────────
$нашиШинглы = [];
foreach (V5_TYPES as $t) {
    $f = "$наш/$t.html";
    if (is_file($f)) { $нашиШинглы[$t] = shingles(chist((string) file_get_contents($f))); }
}
if ($донорИмя === '') {
    $лучший = ['', -1];
    foreach (glob("$корпус/*", GLOB_ONLYDIR) ?: [] as $d) {
        $сумма = 0; $n = 0;
        foreach ($нашиШинглы as $t => $sh) {
            $f = "$d/$t.html";
            if (!is_file($f)) { continue; }
            $их = shingles(chist((string) file_get_contents($f)));
            if (!$их || !$sh) { continue; }
            $сумма += count(array_intersect_key($sh, $их)) / min(count($sh), count($их)) * 100;
            $n++;
        }
        if ($n && $сумма / $n > $лучший[1]) { $лучший = [basename($d), $сумма / $n]; }
    }
    $донорИмя = $лучший[0];
}
$донор = "$корпус/$донорИмя";
if (!is_dir($донор)) { fwrite(STDERR, "нет донора $донор\n"); exit(1); }

/** Разбор страницы на блоки: виджет целиком, проза поштучно. */
function v5Bloki(string $html): array
{
    $out = [];
    foreach (v5Uzly($html) as $u) {
        $проза = $u['класс'] === '' && in_array($u['тег'], ['h2', 'h3', 'p', 'ul', 'ol'], true);
        $out[] = ['вид' => $проза ? $u['тег'] : 'виджет:' . v5Klass($u), 'raw' => $u['html']];
    }
    return $out;
}

/** Выравнивание двух последовательностей по видам блоков (LCS). */
function v5Vyrovnyat(array $A, array $B): array
{
    $n = count($A); $m = count($B);
    $L = array_fill(0, $n + 1, array_fill(0, $m + 1, 0));
    for ($i = $n - 1; $i >= 0; $i--) {
        for ($j = $m - 1; $j >= 0; $j--) {
            $L[$i][$j] = $A[$i]['вид'] === $B[$j]['вид']
                ? $L[$i + 1][$j + 1] + 1
                : max($L[$i + 1][$j], $L[$i][$j + 1]);
        }
    }
    $строки = []; $i = 0; $j = 0;
    while ($i < $n && $j < $m) {
        if ($A[$i]['вид'] === $B[$j]['вид']) { $строки[] = [$A[$i], $B[$j]]; $i++; $j++; }
        elseif ($L[$i + 1][$j] >= $L[$i][$j + 1]) { $строки[] = [$A[$i], null]; $i++; }
        else { $строки[] = [null, $B[$j]]; $j++; }
    }
    while ($i < $n) { $строки[] = [$A[$i++], null]; }
    while ($j < $m) { $строки[] = [null, $B[$j++]]; }
    return $строки;
}

function v5Slov(string $raw): int
{
    $t = v5Text($raw);
    return $t === '' ? 0 : count(preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY));
}

/** Показ блока: разметка чистится до читаемого минимума, виджет сворачивается. */
function v5Pokaz(?array $b): string
{
    if ($b === null) { return '<span class="net">— блока нет —</span>'; }
    if (str_starts_with($b['вид'], 'виджет:')) {
        $текст = v5Text($b['raw']);
        return '<span class="vid">' . htmlspecialchars(substr($b['вид'], 7)) . '</span> '
             . htmlspecialchars(mb_substr($текст, 0, 400)) . (mb_strlen($текст) > 400 ? ' …' : '');
    }
    $raw = preg_replace('~<a\b[^>]*>~i', '<u>', $b['raw']);
    $raw = preg_replace('~</a>~i', '</u>', $raw);
    $raw = preg_replace('~\s*(class|itemprop|itemtype|id|href|target|rel|style)="[^"]*"~i', '', $raw);
    $raw = preg_replace('~\s+itemscope~i', '', $raw);
    return trim(preg_replace('~\s+~u', ' ', $raw));
}

$a = new Analyzer();
$поляВсе = PageMetrics::FIELDS;
$тело = ''; $свод = [];

foreach (V5_TYPES as $тип) {
    $fН = "$наш/$тип.html"; $fД = "$донор/$тип.html";
    if (!is_file($fН) || !is_file($fД)) { continue; }
    $hН = (string) file_get_contents($fН);
    $hД = (string) file_get_contents($fД);
    $чинить = fn($h) => preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $h);
    $мН = PageMetrics::measure($a, $тип, $чинить($hН), ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $мД = PageMetrics::measure($a, $тип, $чинить($hД), ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $shН = shingles(chist($hН)); $shД = shingles(chist($hД));
    $совп = ($shН && $shД) ? count(array_intersect_key($shН, $shД)) / min(count($shН), count($shД)) * 100 : 0;

    // ── матрица полей
    $поля = $профиль['страницы'][$тип]['поля'] ?? [];
    $строкиПолей = ''; $держат = 0; $сошлось = 0;
    foreach ($поляВсе as $k => [$подпись, $дробное]) {
        if (!isset($мН[$k]) || !is_numeric($мН[$k])) { continue; }
        $п = $поля[$k] ?? null;
        $жёстко = (bool) ($п['держат'] ?? false);
        $цель = $п['цель'] ?? '—';
        $полоса = $п ? "{$п['полоса'][0]}–{$п['полоса'][1]}" : '—';
        $наше = is_float($мН[$k]) ? round((float) $мН[$k], 1) : $мН[$k];
        $их = isset($мД[$k]) && is_numeric($мД[$k]) ? (is_float($мД[$k]) ? round((float) $мД[$k], 1) : $мД[$k]) : '—';
        $вердикт = '';
        if ($п) {
            $пол = $дробное ? 0.8 : 2.0;
            $ок = abs((float) $мН[$k] - (float) $п['цель']) <= max(0.25 * abs((float) $п['цель']), $пол);
            if ($жёстко) { $держат++; if ($ок) { $сошлось++; } }
            $вердикт = $ок ? '<span class="ok">в коридоре</span>' : '<span class="bad">мимо</span>';
        }
        $строкиПолей .= '<tr class="' . ($жёстко ? '' : 'volno') . '">'
            . '<td><code>' . htmlspecialchars($k) . '</code><br><span class="pod">' . htmlspecialchars($подпись) . '</span></td>'
            . '<td class="ch">' . $наше . '</td><td class="ch">' . $их . '</td>'
            . '<td class="ch">' . $цель . '</td><td class="ch pod">' . $полоса . '</td>'
            . '<td>' . ($жёстко ? 'держат' : '<span class="pod">свободно</span>') . '</td>'
            . '<td>' . $вердикт . '</td></tr>';
    }

    // ── текст рядом
    $строкиТекста = ''; $i = 0;
    foreach (v5Vyrovnyat(v5Bloki($hН), v5Bloki($hД)) as [$x, $y]) {
        $i++;
        $вид = $x['вид'] ?? $y['вид'];
        $доля = '';
        if ($x && $y) {
            $sx = shingles(chist($x['raw']));
            if ($sx) {
                $d = count(array_intersect_key($sx, $shД)) / count($sx) * 100;
                $доля = '<span class="' . ($d >= 50 ? 'bad' : ($d >= 20 ? 'sred' : 'ok')) . '">'
                      . round($d) . ' %</span>';
            }
        }
        $строкиТекста .= '<tr' . (($x && $y) ? '' : ' class="odin"') . '>'
            . '<td class="ix">' . $i . '<br><code>' . htmlspecialchars($вид) . '</code><br>' . $доля . '</td>'
            . '<td class="blk">' . v5Pokaz($x) . '<span class="w">' . ($x ? v5Slov($x['raw']) : 0) . ' сл.</span></td>'
            . '<td class="blk">' . v5Pokaz($y) . '<span class="w">' . ($y ? v5Slov($y['raw']) : 0) . ' сл.</span></td>'
            . '</tr>';
    }

    $процент = $держат ? round($сошлось / $держат * 100) : 0;
    $свод[$тип] = ['сошлось' => $сошлось, 'держат' => $держат, 'процент' => $процент,
                   'совп' => round($совп, 1), 'словН' => v5Slov($hН), 'словД' => v5Slov($hД)];

    $тело .= '<section id="' . $тип . '"><h2>' . $тип . '</h2>'
        . '<p class="meta">полей держат ' . $сошлось . '/' . $держат . ' (' . $процент . ' %) · '
        . 'слов ' . $свод[$тип]['словН'] . ' против ' . $свод[$тип]['словД'] . ' · '
        . 'шинглов общих ' . $свод[$тип]['совп'] . ' % (потолок корпуса '
        . ($профиль['уникальность']['по_типам'][$тип]['потолок'] ?? '—') . ')</p>'
        . '<h3>Все параметры</h3><table class="polya"><thead><tr><th>поле</th><th>наше</th>'
        . '<th>' . htmlspecialchars($донорИмя) . '</th><th>цель</th><th>полоса</th><th>режим</th><th>вердикт</th>'
        . '</tr></thead><tbody>' . $строкиПолей . '</tbody></table>'
        . '<h3>Текст рядом</h3><table class="tekst"><thead><tr><th>№ / вид / совпало</th>'
        . '<th>наше (' . htmlspecialchars(basename($наш)) . ')</th>'
        . '<th>донор (' . htmlspecialchars($донорИмя) . ')</th></tr></thead><tbody>'
        . $строкиТекста . '</tbody></table></section>';
}

$шапка = '<p class="meta">Набор <b>' . htmlspecialchars(basename($наш)) . '</b> против донора <b>'
    . htmlspecialchars($донорИмя) . '</b> (ближайший по шинглам). Профиль — '
    . ($профиль['источник']['в_расчёте'] ?? '?') . ' наборов корпуса.</p>'
    . '<table class="svod"><thead><tr><th>страница</th><th>полей держат</th><th>%</th>'
    . '<th>слов наше</th><th>слов донор</th><th>совпало</th><th>потолок</th></tr></thead><tbody>';
foreach ($свод as $t => $s) {
    $п = $профиль['уникальность']['по_типам'][$t]['потолок'] ?? 0;
    $шапка .= '<tr><td><a href="#' . $t . '">' . $t . '</a></td>'
        . '<td class="ch">' . $s['сошлось'] . '/' . $s['держат'] . '</td>'
        . '<td class="ch"><span class="' . ($s['процент'] >= 95 ? 'ok' : 'bad') . '">' . $s['процент'] . ' %</span></td>'
        . '<td class="ch">' . $s['словН'] . '</td><td class="ch">' . $s['словД'] . '</td>'
        . '<td class="ch"><span class="' . ($s['совп'] <= $п ? 'ok' : 'sred') . '">' . $s['совп'] . ' %</span></td>'
        . '<td class="ch pod">' . $п . '</td></tr>';
}
$шапка .= '</tbody></table>';

$css = <<<'CSS'
:root { --fon:#fff; --tekst:#1a1a1a; --ramka:#e2e2e2; --pod:#767676; --pol:#f7f7f7; }
@media (prefers-color-scheme: dark) {
  :root { --fon:#16181c; --tekst:#e8e8e8; --ramka:#2e3238; --pod:#9aa0a6; --pol:#1d2025; }
}
* { box-sizing:border-box; }
body { margin:0; padding:24px; background:var(--fon); color:var(--tekst);
  font:15px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
h1 { font-size:22px; margin:0 0 4px; }
h2 { font-size:19px; margin:34px 0 6px; padding-top:14px; border-top:2px solid var(--ramka); }
h3 { font-size:15px; margin:20px 0 6px; color:var(--pod); text-transform:uppercase; letter-spacing:.05em; }
.meta { color:var(--pod); margin:0 0 14px; }
table { border-collapse:collapse; width:100%; margin:0 0 10px; font-size:13.5px; }
th,td { border:1px solid var(--ramka); padding:6px 8px; vertical-align:top; text-align:left; }
th { background:var(--pol); font-weight:600; position:sticky; top:0; }
.ch { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }
.pod { color:var(--pod); font-size:12px; }
.ok { color:#1a7f37; font-weight:600; }
.bad { color:#c2340a; font-weight:600; }
.sred { color:#9a6700; font-weight:600; }
.volno td { color:var(--pod); }
.polya td:first-child { width:230px; }
.tekst td.ix { width:104px; text-align:center; font-size:12px; color:var(--pod); }
.tekst td.blk { width:calc(50% - 52px); }
.tekst tr.odin td.blk { background:var(--pol); }
.net { color:var(--pod); font-style:italic; }
.vid { display:inline-block; padding:1px 6px; border:1px solid var(--ramka);
  border-radius:10px; font-size:11.5px; color:var(--pod); margin-right:6px; }
.w { display:block; margin-top:6px; color:var(--pod); font-size:11.5px; }
u { text-decoration:underline dotted; }
code { font-size:12px; }
.svod td:first-child a { color:inherit; }
@media (max-width:900px) { .tekst td.blk { width:auto; } }
CSS;

$html = "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
    . '<meta name="viewport" content="width=device-width,initial-scale=1">'
    . '<title>Рядом: ' . htmlspecialchars(basename($наш)) . ' и ' . htmlspecialchars($донорИмя) . '</title>'
    . "<style>$css</style></head><body>"
    . '<h1>Наш комплект рядом с донорским</h1>' . $шапка . $тело . '</body></html>';

if (!is_dir(dirname($выход))) { mkdir(dirname($выход), 0777, true); }
file_put_contents($выход, $html);

printf("══ рядом: %s против %s ══\n\n", basename($наш), $донорИмя);
printf("%-13s %10s %6s %8s %8s %8s\n", 'страница', 'держат', '%', 'слов', 'у донора', 'совпало');
foreach ($свод as $t => $s) {
    printf("%-13s %6d/%-3d %5d%% %8d %8d %7.1f%%\n",
        $t, $s['сошлось'], $s['держат'], $s['процент'], $s['словН'], $s['словД'], $s['совп']);
}
printf("\nотчёт: %s (%.0f КБ)\n", $выход, filesize($выход) / 1024);

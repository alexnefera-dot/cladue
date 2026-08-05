<?php
declare(strict_types=1);
/**
 * Сборка отчёта «блок к блоку»: страница-образец и наша страница рядом,
 * плюс матрица 55 полей. Блоки выравниваются по типам через LCS, поэтому
 * пропуск или лишний абзац видно сразу.
 *
 *   php build-ryadom.php <номер набора>
 */
require_once __DIR__ . '/src/PageMetrics.php';

const PAGES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
const TITLES = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация',
                'bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

$SET = $argv[1] ?? '';
if ($SET === '') { fwrite(STDERR, "usage: build-ryadom.php <номер>\n"); exit(1); }
$REF = __DIR__ . "/../samples/dorgen-reference/set$SET";
$OUR = __DIR__ . "/../samples/v3-final/ruchnoy-$SET";

/** Разбор страницы в последовательность блоков. */
function blocks(string $html): array
{
    $html = preg_replace('~<(script|style|noscript)\b.*?</\1>~is', '', $html);
    $atomic = [];
    foreach ([['details','faq'], ['table','table'], ['blockquote','quote']] as [$tag,$kind]) {
        if (preg_match_all("~<$tag\\b.*?</$tag>~is", $html, $m, PREG_OFFSET_CAPTURE)) {
            foreach ($m[0] as [$t,$o]) { $atomic[] = ['s'=>$o,'e'=>$o+strlen($t),'kind'=>$kind,'raw'=>$t]; }
        }
    }
    $inside = function (int $o) use ($atomic): bool {
        foreach ($atomic as $a) { if ($o > $a['s'] && $o < $a['e']) { return true; } }
        return false;
    };
    $found = [];
    foreach ($atomic as $a) { if (!$inside($a['s'])) { $found[$a['s']] = [$a['kind'], $a['raw']]; } }
    foreach ([['h2','h2'], ['h3','h3'], ['p','p'], ['ul','ul'], ['ol','ol']] as [$tag,$kind]) {
        if (preg_match_all("~<$tag\\b[^>]*>.*?</$tag>~is", $html, $m, PREG_OFFSET_CAPTURE)) {
            foreach ($m[0] as [$t,$o]) { if (!$inside($o) && !isset($found[$o])) { $found[$o] = [$kind, $t]; } }
        }
    }
    ksort($found);
    $out = [];
    foreach ($found as $b) { $out[] = ['kind'=>$b[0], 'raw'=>$b[1]]; }
    return $out;
}

/** Выравнивание двух последовательностей по типам блоков (LCS). */
function align(array $A, array $B): array
{
    $n = count($A); $m = count($B);
    $L = array_fill(0, $n+1, array_fill(0, $m+1, 0));
    for ($i = $n-1; $i >= 0; $i--) {
        for ($j = $m-1; $j >= 0; $j--) {
            $L[$i][$j] = $A[$i]['kind'] === $B[$j]['kind']
                ? $L[$i+1][$j+1] + 1
                : max($L[$i+1][$j], $L[$i][$j+1]);
        }
    }
    $rows = []; $i = 0; $j = 0;
    while ($i < $n && $j < $m) {
        if ($A[$i]['kind'] === $B[$j]['kind']) { $rows[] = [$A[$i], $B[$j]]; $i++; $j++; }
        elseif ($L[$i+1][$j] >= $L[$i][$j+1]) { $rows[] = [$A[$i], null]; $i++; }
        else { $rows[] = [null, $B[$j]]; $j++; }
    }
    while ($i < $n) { $rows[] = [$A[$i++], null]; }
    while ($j < $m) { $rows[] = [null, $B[$j++]]; }
    return $rows;
}

/** Показ блока: разметку чистим до безопасного минимума. */
function show(?array $b): string
{
    if ($b === null) { return '<span class="gap">— блока нет —</span>'; }
    $raw = $b['raw'];
    $raw = preg_replace('~<a\b[^>]*>~i', '<u>', $raw);
    $raw = preg_replace('~</a>~i', '</u>', $raw);
    $raw = preg_replace('~\s*(target|rel|href|class|itemprop|itemscope|itemtype|border|cellpadding|cellspacing|style|width)="[^"]*"~i', '', $raw);
    $raw = preg_replace('~\s+itemscope~i', '', $raw);
    $raw = preg_replace('~<(div|span)\b[^>]*>|</(div|span)>~i', '', $raw);
    $raw = preg_replace('~\s+~u', ' ', $raw);
    if ($b['kind'] === 'faq') {
        $raw = preg_replace('~<details\b[^>]*>~i', '', $raw);
        $raw = str_ireplace('</details>', '', $raw);
        $raw = preg_replace('~<summary\b[^>]*>(.*?)</summary>~is', '<b class="q">$1</b>', $raw);
    }
    return trim($raw);
}

function words(string $raw): int
{
    $t = trim(preg_replace('~\s+~u', ' ', strip_tags($raw)));
    return $t === '' ? 0 : count(preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY));
}

$a = new Analyzer();
$F = PageMetrics::fields(true);
$body = '';
$summary = [];

foreach (PAGES as $pg) {
    $refRaw = (string)file_get_contents("$REF/$pg.html");
    $ourRaw = (string)file_get_contents("$OUR/$pg.html");
    $R = PageMetrics::measure($a, $pg, $refRaw, ['ru'=>'','en'=>'']);
    $O = PageMetrics::measure($a, $pg, $ourRaw, ['ru'=>'','en'=>'']);

    $hit = 0; $matrix = '';
    foreach ($F as $k => [$lab, $rate]) {
        $bad = PageMetrics::off($O[$k], $R[$k], (bool)$rate);
        if (!$bad) { $hit++; }
        $rv = is_float($R[$k]) ? round($R[$k],1) : $R[$k];
        $ov = is_float($O[$k]) ? round($O[$k],1) : $O[$k];
        $cls = $bad ? 'bad' : 'ok';
        $matrix .= '<tr><td>'.htmlspecialchars($lab).'</td><td class="num">'.$rv.'</td>'
                 . '<td class="num"><span class="'.$cls.'">'.$ov.'</span></td></tr>';
    }
    $summary[$pg] = $hit;

    $A = blocks($refRaw); $B = blocks($ourRaw);
    $rows = ''; $i = 0;
    foreach (align($A, $B) as [$x, $y]) {
        $i++;
        $kind = $x['kind'] ?? $y['kind'];
        $wx = $x ? words($x['raw']) : 0;
        $wy = $y ? words($y['raw']) : 0;
        $mark = ($x && $y) ? '' : ' class="odd"';
        $rows .= '<tr'.$mark.'><td class="ix">'.$i.'<br><code>'.$kind.'</code></td>'
               . '<td class="blk">'.show($x).'<span class="w">'.$wx.' сл.</span></td>'
               . '<td class="blk">'.show($y).'<span class="w">'.$wy.' сл.</span></td></tr>';
    }

    $body .= '<h2 id="'.$pg.'">'.TITLES[$pg].' <span class="sub2">'.$hit.'/55 полей · '
          . count($A).' блоков у образца · '.count($B).' у нас</span></h2>'
          . '<h3>Параметры</h3><div class="scroll"><table class="mx">'
          . '<tr><th>Поле</th><th>Образец</th><th>Наше</th></tr>'.$matrix.'</table></div>'
          . '<h3>Текст блоками</h3><div class="scroll"><table class="bl">'
          . '<tr><th>№</th><th>Образец set'.$SET.'</th><th>Наша статья</th></tr>'.$rows.'</table></div>';
}

$nav = '';
foreach (PAGES as $pg) { $nav .= '<a href="#'.$pg.'">'.TITLES[$pg].' <b>'.$summary[$pg].'/55</b></a> '; }
$total = array_sum($summary);

$css = <<<CSS
:root { --bg:#fff; --fg:#1a1a1a; --mut:#666; --line:#e3e3e3; --note:#f4f4f4; --ok:#2f7d32; --bad:#b3261e; --warn:#8a6a00; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181c; --fg:#e6e6e6; --mut:#9aa0a6; --line:#2e3238; --note:#1e2126; --ok:#7ec783; --bad:#f2b8b5; --warn:#e0c060; } }
* { box-sizing:border-box; }
body { margin:0; padding:24px 16px 60px; background:var(--bg); color:var(--fg); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif; }
.wrap { max-width:1500px; margin:0 auto; }
h1 { font-size:24px; margin:0 0 6px; }
.sub { color:var(--mut); margin:0 0 18px; font-size:14px; }
.sub2 { color:var(--mut); font-weight:400; font-size:13px; }
h2 { font-size:20px; margin:38px 0 10px; padding-top:16px; border-top:2px solid var(--line); }
h3 { font-size:15px; margin:20px 0 6px; color:var(--mut); text-transform:uppercase; letter-spacing:.04em; }
table { border-collapse:collapse; width:100%; font-size:13.5px; margin:8px 0 4px; }
th,td { border:1px solid var(--line); padding:6px 9px; text-align:left; vertical-align:top; }
th { background:var(--note); font-weight:600; }
td.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
table.mx { max-width:640px; }
table.bl td.blk { width:46%; }
table.bl td.ix { width:56px; color:var(--mut); font-size:12px; text-align:center; }
td.ix code { font-size:11px; background:var(--note); padding:1px 4px; border-radius:3px; }
tr.odd td { background:rgba(179,38,30,.07); }
.gap { color:var(--bad); font-size:12.5px; }
.w { display:block; margin-top:5px; color:var(--mut); font-size:11.5px; }
.q { display:block; margin-bottom:4px; }
.ok { color:var(--ok); } .bad { color:var(--bad); font-weight:700; }
.scroll { overflow-x:auto; }
.nav { margin:14px 0 24px; font-size:13.5px; }
.nav a { display:inline-block; margin:0 10px 8px 0; padding:5px 10px; border:1px solid var(--line); border-radius:6px; color:inherit; text-decoration:none; }
.key { border-left:4px solid var(--warn); background:var(--note); border-radius:8px; padding:12px 15px; margin:16px 0; font-size:14px; }
code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }
u { text-decoration:underline dotted; }
CSS;

$html = "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
      . "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
      . "<title>Набор $SET: образец и наша статья рядом</title><style>$css</style></head><body><div class=\"wrap\">"
      . "<h1>Набор $SET: образец и наша статья рядом</h1>"
      . "<p class=\"sub\">Слева — страница образца, справа — наша. Блоки выровнены по типам: если у одной стороны блока нет, строка подсвечена. Итого $total из 385 полей.</p>"
      . "<div class=\"nav\">$nav</div>"
      . "<div class=\"key\">Строка подсвечена красным, когда блок есть только на одной стороне — это расхождение структуры. Совпадение по числу слов в блоке не требуется: коридор приёмки работает на уровне страницы, а не абзаца.</div>"
      . $body . "</div></body></html>\n";

$out = __DIR__ . "/../reports/v3/ryadom/nabor-$SET.html";
@mkdir(dirname($out), 0777, true);
file_put_contents($out, $html);
echo "set$SET: $total/385, ", strlen($html), " bytes -> $out\n";

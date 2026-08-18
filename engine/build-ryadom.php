<?php
declare(strict_types=1);
/**
 * Сборка отчёта «блок к блоку»: страница-образец и наша страница рядом,
 * плюс матрица 55 полей. Блоки выравниваются по типам через LCS, поэтому
 * пропуск или лишний абзац видно сразу.
 *
 *   php build-ryadom.php <номер набора>                      — старые наборы v3
 *   php build-ryadom.php <наша-папка> <папка-донора> [out.html] [--профиль=<файл>]
 *
 * Во второй форме рядом с двумя колонками текста встаёт полная матрица полей:
 * значение донора, наше, цель профиля и полоса корпуса. Одного сравнения «мы
 * против одного донора» мало — донор сам гуляет внутри полосы, и без профиля
 * непонятно, чьё значение странное.
 */
require_once __DIR__ . '/src/PageMetrics.php';

const PAGES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
const TITLES = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация',
                'bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

$PROFIL = '';
$VID = '';
$pos = [];
foreach (array_slice($argv, 1) as $arg) {
    if (str_starts_with($arg, '--профиль=')) { $PROFIL = substr($arg, strlen('--профиль=')); continue; }
    if (str_starts_with($arg, '--вид=')) { $VID = substr($arg, strlen('--вид=')); continue; }
    $pos[] = $arg;
}
if (!$pos) { fwrite(STDERR, "usage: build-ryadom.php <наша-папка> <папка-донора> [out.html] [--профиль=<файл>]\n"); exit(1); }

if (count($pos) === 1) {
    // Старая форма: номер набора v3.
    $SET = $pos[0];
    $REF = __DIR__ . "/../samples/dorgen-reference/set$SET";
    $OUR = __DIR__ . "/../samples/v3-final/ruchnoy-$SET";
    $OUT = __DIR__ . "/../reports/v3/ryadom/nabor-$SET.html";
    $IMYA = "Набор $SET";
    $PODPIS = "Образец set$SET";
    if ($VID === '') { $VID = 'блоки'; }
} else {
    $OUR = rtrim($pos[0], '/');
    $REF = rtrim($pos[1], '/');
    $OUT = $pos[2] ?? (__DIR__ . '/../reports/ryadom.html');
    $SET = basename($OUR);
    $IMYA = basename($OUR) . ' против ' . basename($REF);
    $PODPIS = 'Донор ' . basename($REF);
    // Целиком читается лучше, чем поблочно: выравнивание рвёт текст на куски,
    // и слитную мысль страницы по ним не видно.
    if ($VID === '') { $VID = 'текст'; }
}
foreach ([$OUR, $REF] as $d) { if (!is_dir($d)) { fwrite(STDERR, "нет папки: $d\n"); exit(1); } }
$prof = $PROFIL !== '' ? json_decode((string) file_get_contents($PROFIL), true) : null;
if ($PROFIL !== '' && !$prof) { fwrite(STDERR, "не читается профиль: $PROFIL\n"); exit(1); }

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

/**
 * Страница целиком, очищенная до читаемого HTML.
 *
 * Поблочный показ рвёт текст: выравнивание по типам ставит рядом абзацы,
 * которые ничего друг о друге не говорят, и связную мысль страницы по ним не
 * прочитать. Здесь страница остаётся сплошной, а разметка сводится к тому,
 * что видно глазом: заголовки, абзацы, списки, таблицы, цитаты, FAQ.
 */
function celikom(string $html): string
{
    $h = preg_replace('~<(script|style|noscript)\b.*?</\1>~is', ' ', $html);
    // Ссылка остаётся видимой вместе с адресом: перелинковка — часть жанра.
    $h = preg_replace_callback('~<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>~is',
        fn($m) => '<u class="lnk">' . $m[2] . '</u><sup class="href">' . htmlspecialchars($m[1]) . '</sup>', (string) $h);
    // FAQ разворачивается: вопрос жирным, ответ следом.
    $h = preg_replace('~<summary\b[^>]*>(.*?)</summary>~is', '<div class="q">$1</div>', (string) $h);
    $h = preg_replace('~<details\b[^>]*>~i', '<div class="faq">', (string) $h);
    $h = str_ireplace('</details>', '</div>', (string) $h);
    // Служебные обёртки убираем, атрибуты снимаем со всего.
    $h = preg_replace('~</?(section|article|aside|div(?![^>]*class="(faq|q)"))\b[^>]*>~i', '', (string) $h);
    $h = preg_replace('~<(?!/)(?!u |sup |div class="faq"|div class="q")([a-z0-9]+)\b[^>]*>~i', '<$1>', (string) $h);
    $h = preg_replace('~<(img|iframe|input|form|button)\b[^>]*>~i', '', (string) $h);
    return trim(preg_replace('~\n{3,}~', "\n\n", (string) $h));
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

    $pp = $prof['страницы'][$pg]['поля'] ?? [];
    $hit = 0; $matrix = ''; $vProfile = 0; $vsego = 0; $vnePolosy = 0; $rashod = [];
    foreach ($F as $k => [$lab, $rate]) {
        $bad = PageMetrics::off($O[$k], $R[$k], (bool)$rate);
        if (!$bad) { $hit++; }
        $rv = is_float($R[$k]) ? round($R[$k],1) : $R[$k];
        $ov = is_float($O[$k]) ? round($O[$k],1) : $O[$k];
        $cel = '—'; $pol = '—'; $kray = '—'; $verd = ''; $derzh = ''; $cls = '';
        if (isset($pp[$k])) {
            $c = $pp[$k];
            $cel = $c['цель'];
            $pol = $c['полоса'][0] . '–' . $c['полоса'][1];
            $kray = ($c['край'][0] ?? '?') . '–' . ($c['край'][1] ?? '?');
            $x = (float) $O[$k];
            $vPolose = $x >= (float) $c['полоса'][0] && $x <= (float) $c['полоса'][1];
            $vKrayu  = isset($c['край']) && $x >= (float) $c['край'][0] && $x <= (float) $c['край'][1];
            // Коридор приёмки — только для держимых полей. Остальные тридцать
            // с лишним у доноров гуляют сами, и мерить их коридором нечестно:
            // значение внутри полосы корпуса краснело рядом с этой же полосой.
            $vKoridore = abs($x - (float) $c['цель']) <= max(0.25 * abs((float) $c['цель']), $c['дробное'] ? 0.8 : 2.0);
            if ($c['держат']) {
                $derzh = ' hold';
                $vsego++;
                if ($vKoridore) { $vProfile++; }
                if ($vKoridore) { $verd = '<span class="ok">в коридоре</span>'; $cls = 'ok'; }
                elseif ($vPolose) { $verd = '<span class="warn">в полосе, мимо коридора</span>'; $cls = 'warn'; }
                else {
                    $verd = '<span class="bad">мимо коридора</span>'; $cls = 'bad'; $vnePolosy++;
                    $rashod[] = ['bad', $lab, $ov, $cel, $pol];
                }
            } else {
                if ($vPolose) { $verd = '<span class="ok">в полосе</span>'; $cls = 'ok'; }
                elseif ($vKrayu) { $verd = '<span class="warn">в разбросе корпуса</span>'; $cls = 'warn'; }
                else {
                    $verd = '<span class="bad">вне корпуса</span>'; $cls = 'bad'; $vnePolosy++;
                    $rashod[] = ['bad', $lab, $ov, $cel, $pol];
                }
            }
        }
        $matrix .= '<tr class="'.trim($derzh).'"><td>'.htmlspecialchars($lab).'<code class="fk">'.$k.'</code></td>'
                 . '<td class="num">'.$rv.'</td>'
                 . '<td class="num"><b class="'.$cls.'">'.$ov.'</b></td>'
                 . '<td class="num">'.$cel.'</td><td class="num">'.$pol.'</td><td class="num">'.$kray.'</td>'
                 . '<td>'.$verd.'</td></tr>';
    }
    $poProfilyu = $vsego ? round($vProfile / $vsego * 100) : 0;
    $summary[$pg] = $hit;

    $wR = words($refRaw); $wO = words($ourRaw);
    if ($VID === 'блоки') {
        $A = blocks($refRaw); $B = blocks($ourRaw);
        $rows = ''; $i = 0;
        foreach (align($A, $B) as [$x, $y]) {
            $i++;
            $kind = $x['kind'] ?? $y['kind'];
            $mark = ($x && $y) ? '' : ' class="odd"';
            $rows .= '<tr'.$mark.'><td class="ix">'.$i.'<br><code>'.$kind.'</code></td>'
                   . '<td class="blk">'.show($x).'<span class="w">'.($x ? words($x['raw']) : 0).' сл.</span></td>'
                   . '<td class="blk">'.show($y).'<span class="w">'.($y ? words($y['raw']) : 0).' сл.</span></td></tr>';
        }
        $tekst = '<h3>Текст блоками</h3><div class="scroll"><table class="bl">'
               . '<tr><th>№</th><th>'.htmlspecialchars($PODPIS).'</th><th>Наша статья</th></tr>'.$rows.'</table></div>';
        $skolko = count($A).' блоков у донора · '.count($B).' у нас';
    } else {
        $tekst = '<h3>Текст целиком</h3><div class="two">'
               . '<div class="col"><div class="colhead">'.htmlspecialchars($PODPIS).' · '.$wR.' слов</div>'
               . '<div class="page">'.celikom($refRaw).'</div></div>'
               . '<div class="col"><div class="colhead">Наша статья · '.$wO.' слов</div>'
               . '<div class="page">'.celikom($ourRaw).'</div></div></div>';
        $skolko = $wR.' слов у донора · '.$wO.' у нас';
    }

    $body .= '<h2 id="'.$pg.'">'.TITLES[$pg].' <span class="sub2">'
          . ($prof ? $vProfile.'/'.$vsego.' держимых полей в коридоре ('.$poProfilyu.' %) · вне корпуса '.$vnePolosy.' из 55 · ' : '')
          . $hit.'/55 совпало с донором · '.$skolko.'</span></h2>'
          . ($rashod
              ? '<h3>Расхождения</h3><ul class="rash">' . implode('', array_map(
                    fn($r) => '<li><b>' . htmlspecialchars($r[1]) . '</b> — наше <b class="bad">' . $r[2]
                            . '</b>, цель ' . $r[3] . ', полоса ' . $r[4] . '</li>', $rashod)) . '</ul>'
              : '<h3>Расхождения</h3><p class="none">Все 55 полей либо в коридоре приёмки, либо внутри разброса корпуса.</p>')
          . '<h3>Параметры</h3><div class="scroll"><table class="mx">'
          . '<tr><th>Поле</th><th>Донор</th><th>Наше</th><th>Цель</th><th>Полоса q1–q3</th><th>Край мин–макс</th><th>Вердикт</th></tr>'.$matrix.'</table></div>'
          . $tekst;
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
tr.hold td:first-child { font-weight:600; }
code.fk { display:block; font-size:10.5px; color:var(--mut); margin-top:2px; }
table.mx { max-width:900px; }
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
.two { display:grid; grid-template-columns:1fr 1fr; gap:18px; align-items:start; }
@media (max-width:900px) { .two { grid-template-columns:1fr; } }
.col { min-width:0; border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.colhead { position:sticky; top:0; z-index:2; background:var(--note); border-bottom:1px solid var(--line); padding:8px 14px; font-size:13px; font-weight:600; }
.page { padding:6px 16px 18px; font-size:14.5px; }
.page h2 { font-size:17px; margin:22px 0 8px; padding:0; border:0; }
.page h3 { font-size:14.5px; margin:16px 0 6px; color:var(--fg); text-transform:none; letter-spacing:0; font-weight:700; }
.page p { margin:9px 0; }
.page table { font-size:13px; }
.page blockquote { margin:12px 0; padding:8px 14px; border-left:3px solid var(--warn); background:var(--note); border-radius:0 6px 6px 0; }
.page .faq { border:1px solid var(--line); border-radius:6px; padding:8px 12px; margin:8px 0; }
.page .faq .q { font-weight:700; margin-bottom:4px; }
.page .faq p { margin:4px 0; }
.page sup.href { color:var(--mut); font-size:10px; margin-left:2px; }
.page u.lnk { text-decoration:underline; text-underline-offset:2px; }
.warn { color:var(--warn); }
tr.hold td { background:rgba(138,106,0,.06); }
ul.rash { margin:6px 0 0; padding-left:20px; font-size:14px; }
ul.rash li { margin:3px 0; }
p.none { color:var(--mut); font-size:14px; margin:6px 0 0; }
CSS;

$html = "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
      . "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
      . "<title>$IMYA: текст и параметры рядом</title><style>$css</style></head><body><div class=\"wrap\">"
      . "<h1>$IMYA</h1>"
      . "<p class=\"sub\">Слева — страница донора, справа — наша. Блоки выровнены по типам: если у одной стороны блока нет, строка подсвечена. Совпало $total из 385 полей.</p>"
      . "<div class=\"nav\">$nav</div>"
      . "<div class=\"key\">Строка подсвечена красным, когда блок есть только на одной стороне — это расхождение структуры. Совпадение по числу слов в блоке не требуется: коридор приёмки работает на уровне страницы, а не абзаца.</div>"
      . $body . "</div></body></html>\n";

@mkdir(dirname($OUT), 0777, true);
file_put_contents($OUT, $html);
echo "$SET: $total/385 полей против донора, ", strlen($html), " байт -> $OUT\n";

<?php
declare(strict_types=1);

/**
 * Отчёт: кастомный набор против всех референсов — и по четырём сигналам, и по
 * той линейке, которую мы копили всю дорогу.
 *
 *   php report-custom.php <папка-с-кастомом> <out.html>
 *
 * Смысл не в том, чтобы кастом «победил», а в том, чтобы увидеть, куда он лёг:
 * рядом с удачными наборами или в стороне от всех.
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

$CUSTOM = $argv[1] ?? '/tmp/frozen-custom';
$OUT    = $argv[2] ?? (__DIR__ . '/../reports/v3/kastom-vs-vse.html');

const RE_CTA   = '~\b(зарегистрируйся|играй|жми|получи|забери|активируй|скачай|попробуй|переходи|успей)\b~ui';
const RE_MINUS = '~\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле|важно понимать)\b~ui';
const RE_FACT  = '~\d[\d\s]*\s*(?:₽|руб|%|мин\b|час\w*|дн\w+|сут\w+|мб|гб|x\d)~ui';
const RE_SELF  = '~\b(я|мне|мой|моя|мои|моего|моей|меня|мною)\b~ui';

/** Три набора, про которые заказчик сказал, что они сработали. */
const WINNERS = ['set199', 'set240', 'донор 2'];

function esc($s): string { return htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8'); }

function files(string $dir): array
{
    return array_merge(glob("$dir/*.html") ?: [], glob("$dir/*.htm") ?: []);
}

function stats(Analyzer $an, string $dir): array
{
    $all = ''; $hs = []; $h3 = 0; $listC = 0; $totC = 0;
    $words = 0; $paras = 0; $paraWords = 0; $lists = 0; $strong = 0; $faq = 0;
    $emoji = 0; $ent = 0; $imper = 0; $vy = 0; $adj = []; $nau = []; $wat = []; $numbers = [];
    foreach (files($dir) as $f) {
        $raw  = NicheLexicon::unplaceholder((string) file_get_contents($f));
        $raw  = preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $raw);
        $r    = $an->run([['name' => 'p', 'url' => '/p', 'html' => $raw, 'keyword' => '', 'lsi' => []]]);
        $m    = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];
        $flat = trim(preg_replace('~\s+~u', ' ', strip_tags($raw)));
        $all .= ' ' . $flat;
        $totC += mb_strlen($flat);

        $words   += (int) $m['words_total'];
        $lists   += (int) $m['list_count'];
        $strong  += (int) $m['strong_count'];
        $faq     += (int) $s['faq_questions'];
        $emoji   += (int) $s['emoji'];
        $ent      = max($ent, (int) $s['entities_count']);
        $imper   += (int) $s['imperatives'];
        $vy      += (int) $s['second_person'];
        $adj[]    = (float) $s['adj_pct'];
        $nau[]    = (float) $m['nausea_academic'];
        $wat[]    = (float) $m['water_percent'];
        $numbers[] = (float) $s['numbers_per_100w'];

        if (preg_match_all('~<li\b[^>]*>(.*?)</li>~is', $raw, $lm)) {
            foreach ($lm[1] as $x) { $listC += mb_strlen(trim(strip_tags($x))); }
        }
        $h3 += preg_match_all('~<h3[^>]*>~i', $raw);
        if (preg_match_all('~<h2[^>]*>(.*?)</h2>~is', $raw, $hm)) {
            foreach ($hm[1] as $h) {
                $x = trim(preg_replace('~\s+~u', ' ', strip_tags($h)));
                if ($x !== '') { $hs[] = $x; }
            }
        }
        preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
        foreach ($pm[1] ?? [] as $x) {
            $t = trim(preg_replace('~\s+~u', ' ', strip_tags($x)));
            if (mb_strlen($t) > 40) { $paras++; $paraWords += count(preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY)); }
        }
    }
    $wc  = max(1, count(preg_split('~[^\p{L}\p{N}]+~u', mb_strtolower($all), -1, PREG_SPLIT_NO_EMPTY)));
    $avg = fn(array $a) => $a ? round(array_sum($a) / count($a), 1) : 0;
    return [
        'pages'      => count(files($dir)),
        'words'      => $words,
        'facts'      => round(preg_match_all(RE_FACT, $all) / $wc * 10000, 1),
        'cta'        => round(preg_match_all(RE_CTA, $all) / $wc * 10000, 1),
        'minus'      => round(preg_match_all(RE_MINUS, $all) / $wc * 10000, 1),
        'h3_per_h2'  => $hs ? round($h3 / count($hs), 1) : 0,
        'h2_words'   => $hs ? round(array_sum(array_map(fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)), $hs)) / count($hs), 1) : 0,
        'h2_quest'   => $hs ? round(count(array_filter($hs, fn($x) => mb_strpos($x, '?') !== false)) / count($hs) * 100, 1) : 0,
        'self'       => round(preg_match_all(RE_SELF, $all) / $wc * 10000, 1),
        'lists_pct'  => $totC ? round($listC / $totC * 100, 1) : 0,
        'paragraphs' => $paras,
        'wpp'        => $paras ? round($paraWords / $paras, 1) : 0,
        'lists'      => $lists,
        'strong'     => $strong,
        'faq'        => $faq,
        'emoji'      => $emoji,
        'imper'      => $imper,
        'vy'         => $vy,
        'adj'        => $avg($adj),
        'nausea'     => $avg($nau),
        'water'      => $avg($wat),
        'numbers'    => $avg($numbers),
        'terms10k'   => round(NicheLexicon::termsTotal(NicheLexicon::prose(implode(' ', array_map('file_get_contents', files($dir))))) / $wc * 10000, 1),
    ];
}

$an = new Analyzer();
$rows = [];
$rows['НАШ КАСТОМ'] = stats($an, $CUSTOM);
foreach (glob(__DIR__ . '/../samples/dorgen-reference/*', GLOB_ONLYDIR) as $d) {
    $rows[basename($d)] = stats($an, $d);
}
foreach ([1, 2, 3, 4, 5, 6] as $n) {
    $d = __DIR__ . "/../samples/v3-reference/$n";
    if (is_dir($d) && files($d)) { $rows["донор $n"] = stats($an, $d); }
}

/** Четыре условия, по которым удачные наборы отличались от остальных */
function conditions(array $r): array
{
    return [
        'цифр немного'      => $r['facts'] < 80,
        'не продаёт'        => $r['cta'] < 7,
        'называет минусы'   => $r['minus'] > 40,
        'тема вглубь'       => $r['h3_per_h2'] >= 2.5,
    ];
}

$SIGNALS = [
    'facts'     => ['голых цифр на 10к', '< 80'],
    'cta'       => ['призывов на 10к', '< 7'],
    'minus'     => ['названных минусов на 10к', '> 40'],
    'h3_per_h2' => ['H3 на один H2', '≥ 2.5'],
];
$REST = [
    'pages' => 'страниц', 'words' => 'слов всего', 'paragraphs' => 'абзацев', 'wpp' => 'слов в абзаце',
    'h2_words' => 'слов в заголовке', 'h2_quest' => 'заголовков-вопросов %', 'lists' => 'списков',
    'lists_pct' => 'текста в списках %', 'strong' => 'strong', 'faq' => 'вопросит. знаков',
    'emoji' => 'эмодзи', 'imper' => 'императивов', 'vy' => '«вы»', 'self' => 'личных на 10к',
    'numbers' => 'цифр на 100 слов', 'adj' => 'прилагательных %', 'nausea' => 'тошнота %',
    'water' => 'водность %', 'terms10k' => 'профильных терминов на 10к',
];

$css = <<<CSS
*{box-sizing:border-box}
body{font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:0 0 70px;color:#16181d;background:#f5f6f8}
.wrap{max-width:1400px;margin:0 auto;padding:0 18px}
header{background:linear-gradient(120deg,#123c2a,#1f6b४7);background:linear-gradient(120deg,#123c2a,#1f6b47);color:#fff;padding:32px 0 28px;margin-bottom:24px}
header h1{margin:0 0 8px;font-size:26px}header p{margin:0;opacity:.92;max-width:960px}
h2{font-size:20px;margin:34px 0 8px;padding-bottom:6px;border-bottom:2px solid #1f6b47}
.lead{color:#4a5568;max-width:980px;margin:0 0 12px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:12.5px;box-shadow:0 1px 3px rgba(0,0,0,.07)}
th,td{border:1px solid #e3e6ea;padding:6px 8px;text-align:center;white-space:nowrap}
th{background:#eef4f0;font-weight:600}
td.l,th.l{text-align:left;white-space:normal}
tr.custom td{background:#e8f5ec;font-weight:600}
tr.win td{background:#fbfaef}
.ok{color:#1a7f3c;font-weight:600}.bad{color:#c5221f}
.badge{display:inline-block;font-size:11px;border-radius:4px;padding:1px 6px;margin-left:6px}
.b-custom{background:#1f6b47;color:#fff}.b-win{background:#c9a227;color:#fff}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:14px 0}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:9px;padding:13px 15px}
.card h4{margin:0 0 4px;font-size:14px;color:#4a5568}
.card .big{font-size:22px;font-weight:700;color:#123c2a}
.card p{margin:4px 0 0;font-size:12.5px;color:#6b7280}
.note{background:#fff;border-left:4px solid #1f6b47;padding:11px 15px;margin:14px 0;border-radius:0 8px 8px 0}
.warn{border-left-color:#c5221f}
footer{color:#6b7280;font-size:12.5px;margin-top:30px}
CSS;

$h = "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>";
$h .= "<title>Кастом против всех референсов</title><style>{$css}</style>";
$h .= "<header><div class='wrap'><h1>Наш кастомный набор против всех референсов</h1>"
    . "<p>Кастом собран не как клон: числовая форма взята смесью двух удачных наборов, четыре сигнала выставлены по их общему коридору, "
    . "а голос выбран решением. Ниже — куда он лёг относительно пятнадцати референсов.</p></div></header><div class='wrap'>";

// карточки
$c = $rows['НАШ КАСТОМ'];
$h .= "<h2>Четыре сигнала кастома</h2><div class='cards'>";
foreach ($SIGNALS as $k => [$label, $rule]) {
    $pass = conditions($c)[array_keys(conditions($c))[array_search($k, array_keys($SIGNALS), true)]];
    $h .= "<div class='card'><h4>" . esc($label) . "</h4><div class='big'>{$c[$k]}</div>"
        . "<p>условие " . esc($rule) . " — <span class='" . ($pass ? 'ok' : 'bad') . "'>" . ($pass ? 'выполнено' : 'мимо') . "</span></p></div>";
}
$h .= "</div>";

// таблица сигналов по всем
$h .= "<h2>Сигналы: кастом и все референсы</h2>"
    . "<p class='lead'>Жёлтым — три набора, про которые известно, что они сработали. Зелёным — наш кастом. "
    . "Последний столбец: сколько из четырёх условий выполнено.</p><table><tr><th class='l'>Набор</th>";
foreach ($SIGNALS as [$label, $rule]) { $h .= "<th>" . esc($label) . "<br><span style='font-weight:400;color:#6b7280'>" . esc($rule) . "</span></th>"; }
$h .= "<th>условий</th></tr>";
foreach ($rows as $name => $r) {
    $isCustom = $name === 'НАШ КАСТОМ';
    $isWin = in_array($name, WINNERS, true);
    $cls = $isCustom ? 'custom' : ($isWin ? 'win' : '');
    $cond = conditions($r);
    $h .= "<tr class='{$cls}'><td class='l'>" . esc($name)
        . ($isCustom ? "<span class='badge b-custom'>наш</span>" : ($isWin ? "<span class='badge b-win'>сработал</span>" : '')) . "</td>";
    foreach (array_keys($SIGNALS) as $i => $k) {
        $ok = $cond[array_keys($cond)[$i]];
        $h .= "<td class='" . ($ok ? 'ok' : 'bad') . "'>{$r[$k]}</td>";
    }
    $h .= "<td><b>" . count(array_filter($cond)) . "</b> из 4</td></tr>";
}
$h .= "</table>";

// полная линейка
$h .= "<h2>Вся линейка, которую мы копили</h2>"
    . "<p class='lead'>Здесь без оценок — просто где кастом стоит относительно остальных по каждому параметру.</p>"
    . "<table><tr><th class='l'>Параметр</th>";
foreach (array_keys($rows) as $n) {
    $cls = $n === 'НАШ КАСТОМ' ? " style='background:#d6ecdd'" : (in_array($n, WINNERS, true) ? " style='background:#f7f2d9'" : '');
    $h .= "<th{$cls}>" . esc($n) . "</th>";
}
$h .= "</tr>";
foreach ($REST as $k => $label) {
    $h .= "<tr><td class='l'>" . esc($label) . "</td>";
    foreach ($rows as $n => $r) {
        $cls = $n === 'НАШ КАСТОМ' ? " style='background:#e8f5ec;font-weight:600'" : (in_array($n, WINNERS, true) ? " style='background:#fbfaef'" : '');
        $h .= "<td{$cls}>{$r[$k]}</td>";
    }
    $h .= "</tr>";
}
$h .= "</table>";

$h .= "<div class='note'><b>Как это читать.</b> Кастом не обязан совпадать ни с одним референсом — он и не совпадает: "
    . "по форме он между 199 и 240, по четырём сигналам стоит в их коридоре или строже, по голосу — авторский практик от «я».</div>"
    . "<div class='warn note'><b>Оговорка та же.</b> Четыре условия выведены на трёх наборах, про которые известно, что они сработали, "
    . "и проверены на тех же трёх. Это гипотеза, которую проверит выдача, а не доказанный закон.</div>";

$h .= "<footer>Замер: кастом плюс " . (count($rows) - 1) . " референсов. Все числа посчитаны одним кодом с обеих сторон.</footer></div>";

file_put_contents($OUT, $h);
echo "→ {$OUT}\nSTATUS " . json_encode(['sets' => count($rows)]) . "\n";

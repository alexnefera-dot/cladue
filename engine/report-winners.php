<?php
declare(strict_types=1);

/**
 * Отчёт «чем 199 и 240 отличаются от остальных»: таблица признаков, которых нет
 * в обычной линейке, и парные куски текста — победитель против аутсайдера,
 * референс против нашей генерации.
 *
 *   php report-winners.php <out.html>
 *
 * Признаки взяты не из головы: это то, что осталось различающимся, когда
 * привычные параметры (объём, разделы, тошнота, водность) у всех девяти доноров
 * оказались в одном коридоре.
 */

require_once __DIR__ . '/src/NicheLexicon.php';

$OUT = $argv[1] ?? (__DIR__ . '/../reports/v3/pochemu-199-240.html');

const REF = __DIR__ . '/../samples/dorgen-reference';
const GEN = [
    'set199' => '/tmp/gen-final-set199-личный-дневник-я',
    'set240' => '/tmp/gen-final-set240-циничное-эссе-ты',
    'set229' => '/tmp/gen-final-set229-сленг-ты-автор',
    'set267' => '/tmp/gen-final-set267-люкс-глянец-вы',
];

/** Маркеры, которые и оказались различающими */
const RE_HONEST = '~\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле|важно понимать)\b~ui';
const RE_CTA    = '~\b(зарегистрируйся|играй|жми|получи|забери|активируй|скачай|попробуй|переходи|успей)\b~ui';
const RE_FACT   = '~\d[\d\s]*\s*(?:₽|руб|%|мин\b|час\w*|дн\w+|сут\w+|мб|гб|x\d)~ui';
const RE_SELF   = '~\b(я|мне|мой|моя|мои|моего|моей|меня|мною)\b~ui';

function esc($s): string { return htmlspecialchars((string) $s, ENT_QUOTES, 'UTF-8'); }

function pageFiles(string $dir): array { return glob("$dir/*.html") ?: []; }

function plain(string $file): string
{
    $raw = NicheLexicon::unplaceholder((string) file_get_contents($file));
    $raw = preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $raw);
    return trim(preg_replace('~\s+~u', ' ', strip_tags($raw)));
}

/** Абзацы страницы как отдельные куски — из них и берём примеры */
function paragraphs(string $dir): array
{
    $out = [];
    foreach (pageFiles($dir) as $f) {
        $raw = NicheLexicon::unplaceholder((string) file_get_contents($f));
        if (!preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $m)) { continue; }
        foreach ($m[1] as $p) {
            $t = trim(preg_replace('~\s+~u', ' ', strip_tags($p)));
            if (mb_strlen($t) > 120) { $out[] = [basename($f, '.html'), $t]; }
        }
    }
    return $out;
}

/** $tag = 'h2' или 'h[23]' — вопросы у части доноров живут в подзаголовках */
function headings(string $dir, string $tag = 'h2'): array
{
    $out = [];
    foreach (pageFiles($dir) as $f) {
        $raw = NicheLexicon::unplaceholder((string) file_get_contents($f));
        if (!preg_match_all("~<(?:{$tag})[^>]*>(.*?)</(?:{$tag})>~is", $raw, $m)) { continue; }
        foreach ($m[1] as $h) {
            $t = trim(preg_replace('~\s+~u', ' ', strip_tags($h)));
            if ($t !== '') { $out[] = [basename($f, '.html'), $t]; }
        }
    }
    return $out;
}

/** Первые N абзацев, где срабатывает регулярка; совпадения подсвечиваем */
function pick(array $paras, string $re, int $n = 2, int $len = 460): array
{
    $hits = [];
    foreach ($paras as [$page, $t]) {
        if (!preg_match($re, $t)) { continue; }
        $short = mb_strlen($t) > $len ? mb_substr($t, 0, $len) . '…' : $t;
        $hits[] = [$page, preg_replace($re, '<mark>$0</mark>', esc($short))];
        if (count($hits) >= $n) { break; }
    }
    return $hits;
}

/** Просто первые N абзацев — когда нужен «типичный» кусок, а не по маркеру */
function firstParas(array $paras, int $n = 2, int $len = 460): array
{
    $out = [];
    foreach (array_slice($paras, 0, $n) as [$page, $t]) {
        $short = mb_strlen($t) > $len ? mb_substr($t, 0, $len) . '…' : $t;
        $out[] = [$page, esc($short)];
    }
    return $out;
}

function stats(string $dir): array
{
    $all = ''; $listChars = 0; $totalChars = 0; $h2q = 0; $h2n = 0; $h2 = 0; $h3 = 0; $h2len = 0; $h2colon = 0;
    foreach (pageFiles($dir) as $f) {
        $raw = NicheLexicon::unplaceholder((string) file_get_contents($f));
        $t = plain($f);
        $all .= ' ' . $t;
        $totalChars += mb_strlen($t);
        if (preg_match_all('~<li\b[^>]*>(.*?)</li>~is', $raw, $m)) {
            foreach ($m[1] as $x) { $listChars += mb_strlen(trim(strip_tags($x))); }
        }
        $h3 += preg_match_all('~<h3[^>]*>~i', $raw);
        if (preg_match_all('~<h2[^>]*>(.*?)</h2>~is', $raw, $hm)) {
            foreach ($hm[1] as $h) {
                $x = trim(preg_replace('~\s+~u', ' ', strip_tags($h)));
                if ($x === '') { continue; }
                $h2++; $h2n++;
                $h2len += count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY));
                if (mb_strpos($x, '?') !== false) { $h2q++; }
                if (mb_strpos($x, ':') !== false || mb_strpos($x, '—') !== false) { $h2colon++; }
            }
        }
    }
    $words = preg_split('~[^\p{L}\p{N}]+~u', mb_strtolower($all), -1, PREG_SPLIT_NO_EMPTY);
    $wc = max(1, count($words));
    return [
        'h2'        => $h2,
        'h3_per_h2' => $h2 ? round($h3 / $h2, 1) : 0,
        'h2_len'    => $h2n ? round($h2len / $h2n, 1) : 0,
        'h2_colon'  => $h2n ? round($h2colon / $h2n * 100) : 0,
        'h2_quest'  => $h2n ? round($h2q / $h2n * 100, 1) : 0,
        'cta'       => round(preg_match_all(RE_CTA, $all) / $wc * 10000, 1),
        'honest'    => round(preg_match_all(RE_HONEST, $all) / $wc * 10000, 1),
        'facts'     => round(preg_match_all(RE_FACT, $all) / $wc * 10000, 1),
        'self'      => round(preg_match_all(RE_SELF, $all) / $wc * 10000, 1),
        'lists'     => $totalChars ? round($listChars / $totalChars * 100, 1) : 0,
        'uniq'      => round(count(array_unique($words)) / $wc * 100, 1),
        'words'     => $wc,
    ];
}

$donors = [];
foreach (glob(REF . '/*', GLOB_ONLYDIR) as $d) { $donors[basename($d)] = $d; }
ksort($donors);

$S = [];
foreach ($donors as $n => $d) { $S[$n] = stats($d); }
$G = [];
foreach (GEN as $n => $d) { if (is_dir($d) && pageFiles($d)) { $G[$n] = stats($d); } }

$WIN = ['set199', 'set240'];
$FIELDS = [
    'h2'        => ['H2 на комплект', 'меньше — тема не раздроблена'],
    'h3_per_h2' => ['H3 на один H2', 'глубина раскрытия темы'],
    'h2_len'    => ['слов в заголовке', 'длинный заголовок = длинный хвост запроса'],
    'h2_colon'  => ['заголовков с двоеточием, %', 'конструкция «запрос: угол»'],
    'h2_quest'  => ['заголовков-вопросов, %', 'FAQ-простыня против разделов-тем'],
    'cta'       => ['CTA-глаголов на 10к', '«жми», «забери», «играй»'],
    'honest'    => ['маркеров риска на 10к', 'минусы, ловушки, «не стоит»'],
    'facts'     => ['голых цифр с ед. на 10к', '«500 ₽», «96%», «за 15 минут»'],
    'self'      => ['личных местоимений на 10к', 'голос автора'],
    'lists'     => ['текста в списках, %', ''],
    'uniq'      => ['уникальных слов, %', 'богатство словаря'],
];

/** насколько значение донора близко к «победному» коридору */
function verdict(string $key, float $v, array $S, array $WIN): string
{
    $w = array_map(fn($n) => (float) $S[$n][$key], $WIN);
    [$lo, $hi] = [min($w), max($w)];
    $pad = max(0.25 * max(abs($lo), 1), 1);
    if ($v >= $lo - $pad && $v <= $hi + $pad) { return 'ok'; }
    return (abs($v - $lo) > 2 * $pad && abs($v - $hi) > 2 * $pad) ? 'bad' : 'mid';
}

// ─── примеры ────────────────────────────────────────────────────────────────
$P = [];
foreach ($donors as $n => $d) { $P[$n] = paragraphs($d); }
$PG = [];
foreach (GEN as $n => $d) { if (is_dir($d)) { $PG[$n] = paragraphs($d); } }

$H = [];
foreach ($donors as $n => $d) { $H[$n] = headings($d); }
$HQ = [];   // все заголовки, включая H3: вопросы у части доноров живут там
foreach ($donors as $n => $d) { $HQ[$n] = headings($d, 'h2|h3'); }
$HG = [];
foreach (GEN as $n => $d) { if (is_dir($d)) { $HG[$n] = headings($d, 'h2|h3'); } }

function headingList(array $hs, int $n = 6, ?string $re = null): string
{
    $rows = [];
    foreach ($hs as [$page, $t]) {
        if ($re !== null && !preg_match($re, $t)) { continue; }
        $rows[] = '<li><span class="pg">' . esc($page) . '</span> ' . esc($t) . '</li>';
        if (count($rows) >= $n) { break; }
    }
    return '<ul class="hl">' . implode('', $rows) . '</ul>';
}

function quotes(array $picked): string
{
    if (!$picked) { return '<p class="none">— нет ни одного такого места —</p>'; }
    $out = '';
    foreach ($picked as [$page, $html]) {
        $out .= '<blockquote><span class="pg">' . esc($page) . '</span>' . $html . '</blockquote>';
    }
    return $out;
}

$css = <<<CSS
*{box-sizing:border-box}
body{font:15px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,sans-serif;margin:0;padding:0 0 80px;color:#16181d;background:#f5f6f8}
.wrap{max-width:1280px;margin:0 auto;padding:0 20px}
header{background:linear-gradient(120deg,#1f2b46,#33507e);color:#fff;padding:34px 0 30px;margin-bottom:26px}
header h1{margin:0 0 8px;font-size:27px}
header p{margin:0;opacity:.9;max-width:900px}
h2{font-size:21px;margin:38px 0 6px;padding-bottom:7px;border-bottom:2px solid #33507e}
h3{font-size:16px;margin:22px 0 8px}
.lead{color:#4a5568;margin:0 0 14px;max-width:940px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:13px;box-shadow:0 1px 3px rgba(0,0,0,.07)}
th,td{border:1px solid #e3e6ea;padding:7px 9px;text-align:center;white-space:nowrap}
th{background:#eef2f9;font-weight:600}
td.l,th.l{text-align:left;white-space:normal}
td.win{background:#eaf5ec;font-weight:600}
.ok{background:#eaf5ec;color:#1a7f3c}.mid{background:#fdf6e3;color:#8a6d1a}.bad{background:#fdecea;color:#c5221f}
.hint{color:#6b7280;font-size:12px;font-weight:400;display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px;margin:16px 0 8px}
.card{background:#fff;border:1px solid #e3e6ea;border-radius:9px;padding:14px 16px;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.card h4{margin:0 0 6px;font-size:15px}
.card .big{font-size:23px;font-weight:700;color:#1f2b46}
.card .vs{color:#c5221f;font-weight:600}
.card p{margin:6px 0 0;color:#4a5568;font-size:13.5px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:10px 0 4px}
.pane{background:#fff;border:1px solid #e3e6ea;border-radius:9px;padding:12px 15px}
.pane.good{border-top:3px solid #1a7f3c}
.pane.poor{border-top:3px solid #c5221f}
.pane h4{margin:0 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.03em;color:#4a5568}
blockquote{margin:0 0 10px;padding:9px 12px;background:#fafbfc;border-left:3px solid #cbd5e0;border-radius:0 6px 6px 0;font-size:13.5px}
blockquote:last-child{margin-bottom:0}
.pg{display:inline-block;font-size:11px;background:#eef2f9;color:#33507e;border-radius:4px;padding:1px 6px;margin-right:7px;vertical-align:1px}
mark{background:#ffe9a8;padding:0 2px;border-radius:2px}
ul.hl{margin:0;padding-left:0;list-style:none}
ul.hl li{padding:6px 0;border-bottom:1px dashed #e3e6ea;font-size:13.5px}
ul.hl li:last-child{border:0}
.none{color:#1a7f3c;font-weight:600;margin:0}
.note{background:#fff;border-left:4px solid #33507e;padding:12px 16px;margin:14px 0;border-radius:0 8px 8px 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.warn{border-left-color:#c5221f}
footer{color:#6b7280;font-size:12.5px;margin-top:34px}
@media(max-width:900px){.pair{grid-template-columns:1fr}}
CSS;

$html = "<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>";
$html .= "<title>Почему зашли 199 и 240</title><style>{$css}</style>";
$html .= "<header><div class='wrap'><h1>Почему сработали 199 и 240</h1>"
    . "<p>Разбор двух удачных доноров против семи остальных. Привычные параметры — объём, разделы, тошнота, водность — у всех девяти похожи. "
    . "Ниже только то, что осталось различающимся, и куски текста, на которых это видно глазами.</p></div></header><div class='wrap'>";

// ─── карточки главного вывода ──────────────────────────────────────────────
$avgOther = [];
foreach (array_keys($FIELDS) as $k) {
    $v = [];
    foreach ($S as $n => $s) { if (!in_array($n, $WIN, true)) { $v[] = (float) $s[$k]; } }
    $avgOther[$k] = round(array_sum($v) / count($v), 1);
}
$cards = [
    ['h2_quest', 'Заголовков-вопросов', 'почти нет — это не FAQ-простыня, а разделы-темы'],
    ['cta',      'CTA-глаголов',        'страница не продаёт, а объясняет'],
    ['facts',    'Голых цифр',          'вдвое меньше, чем у остальных: рассуждение вместо сводки'],
    ['h3_per_h2','H3 на один H2',       'одна тема раскрыта 3–4 подразделами вглубь'],
];
$html .= "<h2>Четыре различия, которые видно сразу</h2><div class='cards'>";
foreach ($cards as [$k, $title, $why]) {
    $w = implode(' и ', array_map(fn($n) => $S[$n][$k], $WIN));
    $html .= "<div class='card'><h4>{$title}</h4><div class='big'>{$w}</div>"
        . "<p><span class='vs'>против {$avgOther[$k]}</span> в среднем у семи остальных.<br>" . esc($why) . "</p></div>";
}
$html .= "</div>";

// ─── таблица признаков ─────────────────────────────────────────────────────
$html .= "<h2>Признаки по всем девяти донорам</h2>"
    . "<p class='lead'>Зелёное — значение попадает в коридор двух победителей, красное — далеко от него. "
    . "Столбцы 199 и 240 выделены.</p><table><tr><th class='l'>Признак</th>";
foreach (array_keys($S) as $n) {
    $cls = in_array($n, $WIN, true) ? " class='win'" : '';
    $html .= "<th{$cls}>" . esc($n) . "</th>";
}
$html .= "<th>среднее по 7</th></tr>";
foreach ($FIELDS as $k => [$label, $hint]) {
    $html .= "<tr><td class='l'><b>" . esc($label) . "</b>" . ($hint ? "<span class='hint'>" . esc($hint) . "</span>" : '') . "</td>";
    foreach ($S as $n => $s) {
        $v = $s[$k];
        if (in_array($n, $WIN, true)) { $html .= "<td class='win'>{$v}</td>"; continue; }
        $cls = verdict($k, (float) $v, $S, $WIN);
        $html .= "<td class='{$cls}'>{$v}</td>";
    }
    $html .= "<td>{$avgOther[$k]}</td></tr>";
}
$html .= "</table>";

// ─── пример 1: заголовки ───────────────────────────────────────────────────
$html .= "<h2>1. Заголовок: запрос плюс угол — против дробления и вопросов</h2>"
    . "<p class='lead'>У победителей заголовок длинный (9 слов), почти всегда с двоеточием или тире: слева запрос, справа обещание. "
    . "У аутсайдеров — либо мелкая нарезка, либо вопросы, как в FAQ.</p><div class='pair'>"
    . "<div class='pane good'><h4>set199 и set240 — сработали</h4>"
    . headingList($H['set199'], 4) . headingList($H['set240'], 4) . "</div>"
    . "<div class='pane poor'><h4>set232 (76 заголовков) и set229 (вопросы)</h4>"
    . headingList($H['set232'], 4) . headingList($HQ['set229'], 4, '~\?~') . "</div></div>";

// ─── пример 2: минусы ──────────────────────────────────────────────────────
$html .= "<h2>2. Минус называется прямо</h2>"
    . "<p class='lead'>Маркеры риска подсвечены. У победителей это часть текста, а не оговорка в подвале; "
    . "у глянцевого set267 их втрое меньше по плотности.</p><div class='pair'>"
    . "<div class='pane good'><h4>set240 — 77 маркеров на 10к слов</h4>" . quotes(pick($P['set240'], RE_HONEST, 2))
    . "<h4 style='margin-top:12px'>set199 — 67</h4>" . quotes(pick($P['set199'], RE_HONEST, 1)) . "</div>"
    . "<div class='pane poor'><h4>set267 — 19.5, и тон другой</h4>" . quotes(firstParas($P['set267'], 2)) . "</div></div>";

// ─── пример 3: CTA ─────────────────────────────────────────────────────────
$html .= "<h2>3. Прямых призывов нет</h2>"
    . "<p class='lead'>У set199 ноль CTA-глаголов на весь комплект, у set240 — 6.9 на 10 тысяч слов. "
    . "У set256 их 37.7, и текст читается как баннер.</p><div class='pair'>"
    . "<div class='pane good'><h4>set199 — вместо призыва вывод из опыта</h4>" . quotes(pick($P['set199'], RE_SELF, 2)) . "</div>"
    . "<div class='pane poor'><h4>set256 и set229 — призывы</h4>"
    . quotes(pick($P['set256'], RE_CTA, 1)) . quotes(pick($P['set229'], RE_CTA, 1)) . "</div></div>";

// ─── пример 4: цифры ───────────────────────────────────────────────────────
$html .= "<h2>4. Цифра идёт с объяснением, а не списком</h2>"
    . "<p class='lead'>Голых чисел с единицами у победителей вдвое меньше среднего. "
    . "Цифра появляется внутри рассуждения, а не как строка сводки.</p><div class='pair'>"
    . "<div class='pane good'><h4>set240 — 31 число на 10к слов</h4>" . quotes(pick($P['set240'], RE_FACT, 2)) . "</div>"
    . "<div class='pane poor'><h4>set227 — 173 на 10к</h4>" . quotes(pick($P['set227'], RE_FACT, 2)) . "</div></div>";

// ─── референс против нашей генерации ───────────────────────────────────────
if ($G) {
    $html .= "<h2>5. Где наши генерации ушли от оригинала</h2>"
        . "<p class='lead'>Голос и объём мы воспроизвели точно. Разошлись ровно там, где линейка ничего не мерила.</p>";
    $html .= "<table><tr><th class='l'>Признак</th>";
    foreach (array_keys($G) as $n) { $html .= "<th>реф " . esc(substr($n, 3)) . "</th><th>наша</th>"; }
    $html .= "</tr>";
    foreach (['h2_quest', 'facts', 'honest', 'cta', 'self', 'h3_per_h2'] as $k) {
        $html .= "<tr><td class='l'><b>" . esc($FIELDS[$k][0]) . "</b></td>";
        foreach ($G as $n => $g) {
            $ref = (float) $S[$n][$k]; $our = (float) $g[$k];
            $off = abs($our - $ref) > max(0.3 * max($ref, 1), 1);
            $html .= "<td>{$ref}</td><td class='" . ($off ? 'bad' : 'ok') . "'>{$our}</td>";
        }
        $html .= "</tr>";
    }
    $html .= "</table>";

    $html .= "<div class='pair'>"
        . "<div class='pane good'><h4>реф-199 — заголовки-темы</h4>" . headingList($H['set199'], 5) . "</div>"
        . "<div class='pane poor'><h4>наша генерация 199 — появились вопросы</h4>" . headingList($HG['set199'], 5, '~\?~') . "</div></div>";
}

// ─── что делать ────────────────────────────────────────────────────────────
$html .= "<h2>Что из этого следует для генератора</h2>"
    . "<div class='note'><b>Четыре параметра, которых в линейке нет.</b> Все считаются с обеих сторон одним правилом, как термины и абзацы:<br>"
    . "1. доля заголовков-вопросов — у победителей 1–4%, у нас стабильно 13%;<br>"
    . "2. плотность CTA-глаголов — у победителей около нуля;<br>"
    . "3. маркеры минусов и рисков — иначе текст глянцевеет незаметно;<br>"
    . "4. H3 на один H2 — глубина темы вместо дробления на заголовки.</div>"
    . "<div class='note warn'><b>Честная оговорка.</b> Это два набора из девяти и ваша оценка «зашло», а не данные о позициях. "
    . "Я вижу согласованную корреляцию четырёх признаков, а не доказанную причину. Проверяется дёшево: признаки заводятся в замер и в промпт так же, как всё остальное.</div>";

$html .= "<footer>Замер: " . count($S) . " донора-референса из samples/dorgen-reference"
    . ($G ? " и " . count($G) . " наши генерации" : '') . ". Куски текста подобраны автоматически по маркерам и подсвечены.</footer></div>";

file_put_contents($OUT, $html);
echo "→ {$OUT}\n";
echo "STATUS " . json_encode(['donors' => count($S), 'generations' => count($G)]) . "\n";

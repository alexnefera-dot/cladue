<?php
declare(strict_types=1);

/**
 * Отчёт для вычитки: таблица всех параметров сверху, ниже — референс и наша
 * генерация бок о бок, страница за страницей.
 *
 *   php build-vs-reference-v3.php <папка-с-генерацией> <донор> <out.html>
 *        [--corpus=v3-single|v3-bundle] [--brand-ru=Имя --brand-en=Name]
 *
 * Отличие от build-vs-reference.php (корпуса v1/v2): состав страниц берётся
 * из донора, а не из списка семи типов, и для одностраничников параметры
 * перелинковки в зачёт не идут — ссылок у них нет.
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

$pos = []; $CORPUS = 'v3-single'; $BR = 'Казиновия'; $BE = 'Casinovia'; $DOM = 'casinovia.win'; $DATE = 'июль 2026';
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--corpus=(.*)$/', $a, $m))        { $CORPUS = $m[1]; }
    elseif (preg_match('/^--brand-ru=(.*)$/u', $a, $m)) { $BR = $m[1]; }
    elseif (preg_match('/^--brand-en=(.*)$/', $a, $m))  { $BE = $m[1]; }
    else { $pos[] = $a; }
}
[$DIR, $DONOR, $OUT] = [$pos[0] ?? '', $pos[1] ?? '', $pos[2] ?? ''];
if ($DIR === '' || $DONOR === '' || $OUT === '') {
    fwrite(STDERR, "usage: build-vs-reference-v3.php <dir> <donor> <out.html> [--corpus=…]\n");
    exit(1);
}

$dataDir = __DIR__ . '/' . ($CORPUS === 'v3-bundle' ? 'data-v3-bundle' : 'data-v3-single');
$site    = json_decode((string) file_get_contents($dataDir . '/donors.json'), true)['sites'][$DONOR] ?? null;
if ($site === null) { fwrite(STDERR, "донор '$DONOR' не найден\n"); exit(1); }
$D        = $site['pages'];
$isSingle = !empty($site['shape']['single']);
$read     = $site['read'] ?? [];
$refDir   = __DIR__ . "/../samples/v3-reference/$DONOR";

$F = [
    'words' => ['Объём слов', 0], 'h2' => ['H2', 0], 'sections' => ['Разделы H2+H3', 0],
    'lists' => ['Списки', 0], 'tables' => ['Таблицы', 0], 'quotes' => ['Цитаты', 0],
    'strong' => ['strong', 0], 'faq' => ['Вопросит. знаков', 0], 'emoji' => ['Эмодзи', 0],
    'entities' => ['Сущности (категорий)', 0], 'first_person' => ['«я»', 0], 'we' => ['«мы»', 0],
    'vy' => ['«вы»', 0], 'imperatives' => ['Императивы на «вы»', 0],
    'numbers_per100' => ['Цифры/100', 1], 'adj_pct' => ['Прилаг%', 1],
    'nausea_acad' => ['Тошнота', 1], 'water' => ['Водность%', 1],
    'brand_ru' => ['Бренд RU', 0], 'brand_en' => ['Бренд EN', 0],
    'paragraphs' => ['Абзацев', 0], 'words_per_para' => ['Слов в абзаце', 1],
    'providers_named' => ['Студий поимённо', 0], 'games_named' => ['Игр поимённо', 0],
];
if (!$isSingle) { $F['intlinks'] = ['Ссылок внутри', 0]; }

/** Проза: только абзацы и пункты списков — плитки каталога и меню не текст. */
function proseOf(string $raw): string
{
    preg_match_all('~<(p|li)\b[^>]*>(.*?)</\1>~is', $raw, $pm);
    $parts = array_map(fn($x) => preg_replace('~<[^>]+>~', ' ', $x), $pm[2] ?? []);
    return preg_replace('~\s+~u', ' ', implode(' ', $parts));
}

function offx($our, $don, bool $rate = false): bool
{
    if ($don === null) { return false; }
    return abs($our - $don) > max(0.25 * max(abs($don), 1), $rate ? 0.8 : 2.0);
}
function esc($s): string { return htmlspecialchars((string) ($s ?? ''), ENT_QUOTES, 'UTF-8'); }

$a = new Analyzer();
$pagesCfg = json_decode((string) file_get_contents($dataDir . '/profile.json'), true)['pages'] ?? [];
$brand    = $site['brand'] ?? ['ru' => '', 'en' => ''];

function measure(Analyzer $a, string $t, string $raw, array $pagesCfg, array $brand): array
{
    $r = $a->run([['name' => $t, 'url' => "/$t", 'html' => $raw, 'keyword' => '', 'lsi' => []]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    $txt = strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $raw));
    $brRu = substr_count($raw, '%brand_name_ru%') ?: ($brand['ru'] ? mb_substr_count($txt, $brand['ru']) : 0);
    $brEn = substr_count($raw, '%brand_name_en%') ?: ($brand['en'] ? mb_substr_count($txt, $brand['en']) : 0);
    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $paras = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
    $intl = 0;
    if (preg_match_all('#<a[^>]+href="([^"]+)"#i', $raw, $hm)) {
        $paths = [];
        foreach ($pagesCfg as $pt => $c) { $paths[rtrim($c['path'] ?? "/$pt", '/') ?: '/'] = $pt; }
        foreach ($hm[1] as $h) {
            $path = rtrim((string) parse_url(trim($h), PHP_URL_PATH), '/') ?: '/';
            $tt = $paths[$path] ?? null;
            if ($tt !== null && $tt !== $t) { $intl++; }
        }
    }
    return ['words' => (int) $m['words_total'], 'h2' => (int) $m['h2_count'],
        'sections' => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)), 'lists' => (int) $m['list_count'],
        'tables' => (int) ($m['table_count'] ?? 0), 'quotes' => (int) ($m['quote_count'] ?? 0),
        'strong' => (int) $m['strong_count'], 'faq' => (int) $s['faq_questions'],
        'emoji' => (int) $s['emoji'], 'entities' => (int) $s['entities_count'],
        'first_person' => (int) $s['first_person'],
        'we' => preg_match_all('~\b(мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|наших|нашим|нашими)\b~u', mb_strtolower($txt)),
        'vy' => (int) $s['second_person'], 'imperatives' => (int) $s['imperatives'],
        'numbers_per100' => round((float) $s['numbers_per_100w'], 1), 'adj_pct' => round((float) $s['adj_pct'], 1),
        'nausea_acad' => round((float) $m['nausea_academic'], 1), 'water' => round((float) $m['water_percent'], 1),
        'brand_ru' => $brRu, 'brand_en' => $brEn, 'intlinks' => $intl,
        'providers_named' => NicheLexicon::countProviders(proseOf($raw)),
        'games_named' => NicheLexicon::countGames(proseOf($raw)),
        'paragraphs' => count($paras),
        'words_per_para' => $paras ? round(array_sum(array_map(
            fn($p) => count(preg_split('~\s+~u', $p, -1, PREG_SPLIT_NO_EMPTY)), $paras)) / count($paras), 1) : 0];
}

/** читаемый текст референса: абзацами, без скриптов и меню */
function refText(string $file): string
{
    $t = Parser::fromHtml((string) file_get_contents($file))->text;
    $lines = array_values(array_filter(array_map('trim', preg_split('~\n+~u', $t)), fn($x) => mb_strlen($x) > 2));
    $out = '';
    foreach ($lines as $l) {
        $out .= (mb_strlen($l) < 90 && !preg_match('~[.!?…]$~u', $l))
            ? '<h4>' . esc($l) . '</h4>'
            : '<p>' . esc($l) . '</p>';
    }
    return $out;
}

// файлы референса: имя типа или единственный файл у одностраничника
$refFiles = [];
foreach (array_merge(glob("$refDir/*.htm") ?: [], glob("$refDir/*.html") ?: []) as $f) {
    $stem = mb_strtolower(pathinfo($f, PATHINFO_FILENAME));
    $refFiles[mb_strlen($stem) > 14 ? 'main' : $stem] = $f;
}

$meas = []; $ours = [];
foreach (array_keys($D) as $t) {
    foreach (["$DIR/$t.html", "$DIR/$t.htm"] as $f) {
        if (is_file($f)) { $raw = (string) file_get_contents($f); $ours[$t] = $raw; $meas[$t] = measure($a, $t, $raw, $pagesCfg, $brand); break; }
    }
}
if (!$meas) { fwrite(STDERR, "в $DIR нет страниц донора\n"); exit(1); }

$totHit = 0; $totCnt = 0; $pageStat = [];
foreach ($meas as $t => $mm) {
    $h = 0; $c = 0;
    foreach ($F as $k => [$lab, $rate]) {
        $dv = $D[$t][$k] ?? null; if ($dv === null) { continue; }
        $ok = !offx($mm[$k], $dv, (bool) $rate); $h += $ok ? 1 : 0; $c++;
    }
    $pageStat[$t] = [$h, $c]; $totHit += $h; $totCnt += $c;
}
$match = $totCnt ? (int) round($totHit / $totCnt * 100) : 0;

$css = "<style>
body{font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1500px;margin:0 auto;padding:22px 18px 70px;color:#16181d;background:#f7f8fa}
h1{font-size:24px;margin-bottom:2px}h2{font-size:19px;margin-top:34px;border-bottom:2px solid #2563eb;padding-bottom:6px}
table.p{border-collapse:collapse;width:100%;margin:10px 0;background:#fff;font-size:12.5px}
table.p th,table.p td{border:1px solid #e4e6ea;padding:5px 7px;text-align:center;white-space:nowrap}
table.p th{background:#eef3ff;font-weight:600}table.p td.l,table.p th.l{text-align:left}
.ok{background:#e8f7ec;color:#137333}.bad{background:#fdecea;color:#c5221f}
.note{background:#fff;border-left:3px solid #2563eb;padding:9px 15px;margin:10px 0}
.read{background:#f4f7ff;border-left:3px solid #7aa0f5;padding:9px 14px;margin:10px 0;font-size:14px}
.tabs{display:flex;flex-wrap:wrap;gap:5px;margin:16px 0 4px}
.tabs button{font:13px inherit;padding:5px 12px;border:1px solid #d6dae0;background:#fff;border-radius:7px;cursor:pointer}
.tabs button.on{background:#2563eb;color:#fff;border-color:#2563eb}
.pane{display:none}.pane.on{display:block}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.col{background:#fff;border:1px solid #e4e6ea;border-radius:9px;padding:14px 16px;max-height:78vh;overflow:auto}
.col h3{margin:0 0 8px;font-size:15px;position:sticky;top:0;background:#fff;padding:4px 0;border-bottom:1px solid #eee}
.col h4{font-size:14px;margin:14px 0 5px;color:#2451c4}
.col p{margin:7px 0;font-size:13.5px}
.col table{border-collapse:collapse;margin:8px 0;font-size:12px;width:100%}
.col td,.col th{border:1px solid #e4e6ea;padding:3px 6px}
.col ul,.col ol{margin:7px 0 7px 20px;font-size:13.5px}
@media(max-width:1100px){.cols{grid-template-columns:1fr}}
</style>";

$H = "<meta charset='utf-8'><title>Генерация vs референс {$DONOR}</title>$css
<h1>Донор {$DONOR} — генерация против референса</h1>
<p class='note'>Совпадение по параметрам: <b>{$match}%</b> ({$totHit} из {$totCnt}). Зелёное — параметр в коридоре донора (допуск 25%, пол 2 единицы или 0.8 для долей)."
   . ($isSingle ? " Перелинковка в зачёт не идёт: у одностраничников ссылок нет." : "") . "</p>";

if ($read) {
    $H .= "<div class='read'><b>Жанр:</b> " . esc($read['genre'] ?? '—')
        . "<br><b>Кто говорит:</b> " . esc($read['voice'] ?? '—')
        . " · <b>Регистр:</b> " . esc($read['register'] ?? '—') . "</div>";
}

$H .= "<h2>Все параметры по страницам</h2><table class='p'><tr><th class='l'>Параметр</th>";
foreach (array_keys($meas) as $t) { $H .= "<th>" . esc($t) . "</th>"; }
$H .= "</tr>";
foreach ($F as $k => [$lab, $rate]) {
    $H .= "<tr><td class='l'><b>" . esc($lab) . "</b></td>";
    foreach ($meas as $t => $mm) {
        $dv = $D[$t][$k] ?? null;
        if ($dv === null) { $H .= "<td>—</td>"; continue; }
        $ok = !offx($mm[$k], $dv, (bool) $rate);
        $H .= "<td class='" . ($ok ? 'ok' : 'bad') . "'>" . $mm[$k] . "<br><small>ориг " . $dv . "</small></td>";
    }
    $H .= "</tr>";
}
$H .= "<tr><td class='l'><b>Совпадение</b></td>";
foreach ($pageStat as [$h, $c]) { $H .= "<td><b>" . ($c ? round($h / $c * 100) : 0) . "%</b></td>"; }
$H .= "</tr></table>";

$H .= "<h2>Тексты рядом</h2><div class='tabs'>";
$i = 0;
foreach (array_keys($meas) as $t) {
    $H .= "<button class='" . ($i === 0 ? 'on' : '') . "' onclick=\"sw('" . esc($t) . "',this)\">" . esc($t)
        . " · " . round($pageStat[$t][0] / max(1, $pageStat[$t][1]) * 100) . "%</button>";
    $i++;
}
$H .= "</div>";

$i = 0;
foreach ($meas as $t => $mm) {
    $gen = strtr($ours[$t], ['%brand_name_ru%' => $BR, '%brand_name_en%' => $BE, '%domain_name%' => $DOM, '%date%' => $DATE]);
    $gen = preg_replace('#<script[^>]*>.*?</script>#is', '', $gen);
    $ref = isset($refFiles[$t]) ? refText($refFiles[$t]) : '<p>—</p>';
    $H .= "<div class='pane " . ($i === 0 ? 'on' : '') . "' id='p-" . esc($t) . "'><div class='cols'>"
        . "<div class='col'><h3>Референс — " . esc($t) . "</h3>" . $ref . "</div>"
        . "<div class='col'><h3>Наша генерация — " . esc($t) . "</h3>" . $gen . "</div>"
        . "</div></div>";
    $i++;
}
$H .= "<script>function sw(t,b){document.querySelectorAll('.pane').forEach(function(p){p.className='pane'});"
    . "document.getElementById('p-'+t).className='pane on';"
    . "document.querySelectorAll('.tabs button').forEach(function(x){x.className=''});b.className='on';}</script>";

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT ({$match}%)\n");
echo "STATUS " . json_encode(['match' => $match, 'pages' => count($meas)]) . "\n";

<?php
declare(strict_types=1);

/**
 * Отчёт «референс vs наша генерация» для ВЫЧИТКИ ГЛАЗАМИ.
 * Сверху — матрица параметров по всем 7 страницам (наш / оригинал, с вердиктом),
 * ниже — вкладки по страницам, в каждой два столбца по полэкрана:
 * слева реальный текст конкурента, справа наша генерация.
 *
 *   php build-vs-reference.php <наша-папка> <референс-папка> <донор> <out.html> [Заголовок]
 *
 * Донор нужен для целевых значений из data-dorgen/donors.json (--corpus=dorgen
 * подразумевается, если донор найден там).
 */

require_once __DIR__ . '/src/Analyzer.php';

$OUR = $argv[1] ?? ''; $REF = $argv[2] ?? ''; $DONOR = $argv[3] ?? ''; $OUT = $argv[4] ?? ''; $TITLE = $argv[5] ?? '';
if ($OUR === '' || $REF === '' || $DONOR === '' || $OUT === '') {
    fwrite(STDERR, "usage: build-vs-reference.php <our-dir> <ref-dir> <donor> <out.html> [title]\n"); exit(1);
}
$dorgen = __DIR__ . '/data-dorgen/donors.json';
$sites = json_decode((string) file_get_contents(is_file($dorgen) ? $dorgen : __DIR__ . '/data/donors.json'), true)['sites'] ?? [];
if (!isset($sites[$DONOR])) { fwrite(STDERR, "донор '$DONOR' не найден\n"); exit(1); }
$D = $sites[$DONOR]['pages'];
$a = new Analyzer();

$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];
$TYPES = array_keys($LABEL);
$PM = ['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];

function meas(Analyzer $a, string $t, string $raw, array $PM): array {
    $r = $a->run([['name'=>$t,'url'=>"/$t",'html'=>$raw,'keyword'=>'','lsi'=>[]]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics']; $il = 0;
    if (preg_match_all('#<a[^>]+href="([^"]+)"#i', $raw, $hm)) foreach ($hm[1] as $h) {
        $h = rtrim(trim($h), '/'); if ($h === '') $h = '/';
        $tt = $PM[$h] ?? ($PM['/' . preg_replace('#^.*/#', '', $h)] ?? null); if ($tt !== null && $tt !== $t) $il++;
    }
    return ['words'=>(int)$m['words_total'],'h2'=>(int)$m['h2_count'],'sections'=>(int)($m['h2_count']+($m['h3_count']??0)),
     'lists'=>(int)$m['list_count'],'tables'=>(int)($m['table_count']??0),'quotes'=>(int)$m['quote_count'],'strong'=>(int)$m['strong_count'],
     'faq'=>(int)$s['faq_questions'],'intlinks'=>$il,'brand_ru'=>substr_count($raw,'%brand_name_ru%'),'brand_en'=>substr_count($raw,'%brand_name_en%'),
     'emoji'=>(int)$s['emoji'],'entities'=>(int)$s['entities_count'],'first_person'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],
     'imperatives'=>(int)$s['imperatives'],'numbers_per100'=>round((float)$s['numbers_per_100w'],1),'adj_pct'=>round((float)$s['adj_pct'],1),
     'nausea_acad'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1)];
}
function offx($o,$d,bool $r=false): bool { if ($d===null) return false; $x=abs($o-$d); $t=0.25*max(abs($d),1); $f=$r?0.8:2.0; return $x>max($t,$f); }

$F = ['words'=>['Объём слов',0],'h2'=>['H2',0],'sections'=>['Секции',0],'lists'=>['Списки',0],'tables'=>['Таблицы',0],'quotes'=>['Цитаты',0],
 'strong'=>['&lt;strong&gt;',0],'faq'=>['FAQ',0],'intlinks'=>['Ссылки',0],'brand_ru'=>['Бренд RU',0],'brand_en'=>['Бренд EN',0],'emoji'=>['Эмодзи',0],
 'entities'=>['Сущности',0],'first_person'=>['«я»',0],'vy'=>['«вы»',0],'imperatives'=>['Императивы',0],'numbers_per100'=>['Цифры/100',1],
 'adj_pct'=>['Прилаг%',1],'nausea_acad'=>['Тошнота',1],'water'=>['Водность%',1]];

// демо-бренд для читабельности обеих колонок
$sub = ['%brand_name_ru%'=>'Голд Слот','%brand_name_en%'=>'GoldSlot','%domain_name%'=>'goldslot.win','%date%'=>'27 июля 2026'];
$strip = static function (string $h) use ($sub): string {
    $h = preg_replace('~<script[^>]*>.*?</script>~is', '', $h);
    $h = preg_replace('~</?(?:html|head|body|title|meta|link)[^>]*>~i', '', $h);
    return strtr($h, $sub);
};

$meas = []; $refm = []; $ourHtml = []; $refHtml = [];
foreach ($TYPES as $t) {
    $of = "$OUR/$t.html"; $rf = "$REF/$t.html";
    if (is_file($of)) { $raw = (string) file_get_contents($of); $meas[$t] = meas($a, $t, $raw, $PM); $ourHtml[$t] = $strip($raw); }
    if (is_file($rf)) { $raw = (string) file_get_contents($rf); $refm[$t] = meas($a, $t, $raw, $PM); $refHtml[$t] = $strip($raw); }
}

// ── HTML ───────────────────────────────────────────────────────────────────
$title = $TITLE !== '' ? $TITLE : "Референс {$DONOR} vs наша генерация";
$H = "<meta charset='utf-8'><title>" . htmlspecialchars($title) . "</title><style>
:root{--line:#e2e6ef;--ink:#141821;--soft:#657084;--ok:#137a4b;--okbg:#e8f7ec;--bad:#b3261e;--badbg:#fdecea;--panel:#fff;--bg:#f4f6fa;--accent:#2f5fd0}
@media(prefers-color-scheme:dark){:root{--line:#2a3342;--ink:#e6eaf3;--soft:#94a1b8;--okbg:#12331f;--ok:#5cd68f;--badbg:#3a1c1c;--bad:#ff8a80;--panel:#171d28;--bg:#0f131b;--accent:#6f9cff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:22px}
h1{font-size:21px;margin:0 0 4px}.sub{color:var(--soft);margin:0 0 18px;font-size:14px}
table.mx{border-collapse:collapse;width:100%;background:var(--panel);font-size:12.5px;border:1px solid var(--line);border-radius:10px;overflow:hidden}
table.mx th,table.mx td{border:1px solid var(--line);padding:5px 7px;text-align:center;white-space:nowrap}
table.mx th{background:color-mix(in srgb,var(--accent) 8%,var(--panel));font-weight:600;font-size:11.5px}
table.mx td.l,table.mx th.l{text-align:left;font-weight:600}
td.ok{background:var(--okbg);color:var(--ok)}td.bad{background:var(--badbg);color:var(--bad)}td.na{color:var(--soft)}
small{color:var(--soft);font-size:10.5px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:22px 0 12px;position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
.tab{padding:7px 13px;border:1px solid var(--line);border-radius:8px;background:var(--panel);cursor:pointer;font-size:13px;color:var(--ink)}
.tab.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.pane{display:none}.pane.on{display:block}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
@media(max-width:1000px){.cols{grid-template-columns:1fr}}
.col{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.col>h3{margin:0;padding:10px 14px;font-size:13px;border-bottom:1px solid var(--line);position:sticky;top:56px;background:var(--panel);z-index:2}
.col.ref>h3{color:#b06000}.col.our>h3{color:var(--accent)}
.body{padding:14px 16px;max-height:78vh;overflow:auto;font-size:14px}
.body h2{font-size:17px;margin:18px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
.body h3{font-size:15px;margin:14px 0 6px}
.body table{border-collapse:collapse;width:100%;margin:10px 0;font-size:12.5px}
.body td,.body th{border:1px solid var(--line);padding:5px 7px;text-align:left}
.body blockquote{border-left:3px solid var(--accent);margin:10px 0;padding:5px 12px;background:color-mix(in srgb,var(--accent) 5%,transparent)}
.body ul,.body ol{padding-left:20px}.body a{color:var(--accent)}
.pagestat{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.chip{padding:3px 10px;border-radius:99px;font-size:12px;font-weight:600;background:var(--panel);border:1px solid var(--line)}
.chip.g{background:var(--okbg);color:var(--ok);border-color:transparent}.chip.r{background:var(--badbg);color:var(--bad);border-color:transparent}
</style>
<div class='wrap'>
<h1>" . htmlspecialchars($title) . "</h1>
<p class='sub'>Слева — реальный текст конкурента (<b>{$DONOR}</b>), справа — наша генерация. Бренд подставлен демо-именем в обеих колонках для чтения. В таблице: наш показатель / оригинал, зелёный — в коридоре донора.</p>";

// ── матрица параметров ─────────────────────────────────────────────────────
$H .= "<table class='mx'><tr><th class='l'>Параметр</th>";
foreach ($TYPES as $t) $H .= "<th>{$LABEL[$t]}</th>";
$H .= "</tr>";
$hit = array_fill_keys($TYPES, 0); $tot = array_fill_keys($TYPES, 0);
foreach ($F as $k => [$lab, $rate]) {
    $H .= "<tr><td class='l'>$lab</td>";
    foreach ($TYPES as $t) {
        if (!isset($meas[$t])) { $H .= "<td class='na'>—</td>"; continue; }
        $o = $meas[$t][$k]; $dv = $D[$t][$k] ?? ($k === 'sections' ? ($D[$t]['sections'] ?? null) : null);
        if ($dv === null) { $H .= "<td class='na'>$o<br><small>—</small></td>"; continue; }
        $good = !offx($o, $dv, (bool)$rate); $hit[$t] += $good?1:0; $tot[$t]++;
        $H .= "<td class='" . ($good?'ok':'bad') . "'>$o<br><small>ориг $dv</small></td>";
    }
    $H .= "</tr>";
}
$H .= "<tr><td class='l'>СОВПАДЕНИЕ</td>";
$sumH = 0; $sumT = 0;
foreach ($TYPES as $t) {
    if (!$tot[$t]) { $H .= "<td class='na'>—</td>"; continue; }
    $p = round($hit[$t]/$tot[$t]*100); $sumH += $hit[$t]; $sumT += $tot[$t];
    $H .= "<td class='" . ($p>=85?'ok':($p>=75?'':'bad')) . "'><b>{$p}%</b></td>";
}
$H .= "</tr></table>";
$H .= "<p class='sub' style='margin-top:10px'><b>Итого по связке: " . ($sumT?round($sumH/$sumT*100):0) . "%</b> ({$sumH} из {$sumT} параметров в коридоре донора).</p>";

// ── вкладки со страницами ──────────────────────────────────────────────────
$tabs = ''; $panes = ''; $i = 0;
foreach ($TYPES as $t) {
    if (!isset($ourHtml[$t]) && !isset($refHtml[$t])) continue;
    $on = $i === 0 ? ' on' : '';
    $tabs .= "<button class='tab$on' onclick='sw($i)'>{$LABEL[$t]}</button>";
    // чипы по ключевым параметрам страницы
    $chips = '';
    foreach (['words'=>'слов','intlinks'=>'ссылок','nausea_acad'=>'тошнота','numbers_per100'=>'цифры'] as $k => $nm) {
        if (!isset($meas[$t])) break;
        $o = $meas[$t][$k]; $dv = $D[$t][$k] ?? null; if ($dv === null) continue;
        $good = !offx($o, $dv, in_array($k,['nausea_acad','numbers_per100'],true));
        $chips .= "<span class='chip " . ($good?'g':'r') . "'>$nm $o <small>/ $dv</small></span>";
    }
    $refBody = $refHtml[$t] ?? "<p class='sub'>нет файла референса</p>";
    $ourBody = $ourHtml[$t] ?? "<p class='sub'>нет нашего файла</p>";
    $panes .= "<div class='pane$on' id='p$i'>
      <div class='pagestat'>$chips</div>
      <div class='cols'>
        <div class='col ref'><h3>РЕФЕРЕНС — {$DONOR} / {$LABEL[$t]}</h3><div class='body'>$refBody</div></div>
        <div class='col our'><h3>НАША ГЕНЕРАЦИЯ — {$LABEL[$t]}</h3><div class='body'>$ourBody</div></div>
      </div></div>";
    $i++;
}
$H .= "<div class='tabs'>$tabs</div>$panes
<script>function sw(n){document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('on',i===n));document.querySelectorAll('.pane').forEach((p,i)=>p.classList.toggle('on',i===n));window.scrollTo({top:0,behavior:'smooth'});}</script>
</div>";

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");
echo "STATUS " . json_encode(['match' => $sumT?round($sumH/$sumT*100):0, 'pages' => count($ourHtml)]) . "\n";

<?php
declare(strict_types=1);

/**
 * Сравнение реализованной 7-страничной связки с РЕАЛЬНЫМ конкурентом (донор
 * из корпуса data/donors.json): широкое параметрическое сравнение + отдельный
 * разбор перелинковки (объём ссылок vs донор, анкоры/разнообразие, граф
 * достижимости, повтор слов). Печатает совпадение (STATUS) и, если задан
 * out.html, пишет визуальный отчёт с цветными вердиктами.
 *
 *   php compare-vs-donor.php <папка-со-страницами> <донор> [out.html]
 *
 * Папка: плоская, файлы main.html … app.html (7 типов). Все цифры считаются
 * Analyzer'ом по самому тексту. Принцип: воспроизвести корпус, не превзойти.
 */

require_once __DIR__ . '/src/Analyzer.php';

$DIR   = $argv[1] ?? '';
$DONOR = $argv[2] ?? '';
$OUT   = $argv[3] ?? '';
if ($DIR === '' || $DONOR === '') { fwrite(STDERR, "usage: compare-vs-donor.php <dir> <donor> [out.html]\n"); exit(1); }

$sites = json_decode((string) file_get_contents(__DIR__ . '/data/donors.json'), true)['sites'] ?? [];
if (!isset($sites[$DONOR])) { fwrite(STDERR, "донор '$DONOR' не найден в data/donors.json\n"); exit(1); }
$D = $sites[$DONOR]['pages'];
$a = new Analyzer();

$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];
$TYPES = array_keys($LABEL);
$PM = ['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];

function anchors(string $raw, array $PM, string $self): array {
    $out = [];
    if (preg_match_all('#<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>#is', $raw, $m, PREG_SET_ORDER)) foreach ($m as $mm) {
        $h = rtrim(trim($mm[1]), '/'); if ($h === '') $h = '/';
        $tt = $PM[$h] ?? ($PM['/' . preg_replace('#^.*/#', '', $h)] ?? null);
        if ($tt === null || $tt === $self) continue;
        $out[] = ['target' => $tt, 'anchor' => mb_strtolower(trim(strip_tags($mm[2])))];
    }
    return $out;
}
function measureFull(Analyzer $a, string $t, string $raw): array {
    $r = $a->run([['name'=>$t,'url'=>"/$t",'html'=>$raw,'keyword'=>'','lsi'=>[]]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    return ['words'=>(int)$m['words_total'],'h2'=>(int)$m['h2_count'],'sections'=>(int)($m['h2_count']+($m['h3_count']??0)),
     'lists'=>(int)$m['list_count'],'tables'=>(int)($m['table_count']??0),'quotes'=>(int)($m['quote_count']??0),
     'strong'=>(int)$m['strong_count'],'faq'=>(int)$s['faq_questions'],'numbers_per100'=>round((float)$s['numbers_per_100w'],1),
     'adj_pct'=>round((float)$s['adj_pct'],1),'emoji'=>(int)$s['emoji'],'entities'=>(int)$s['entities_count'],
     'first_person'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],'imperatives'=>(int)$s['imperatives'],
     'nausea_acad'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1),
     'brand_ru'=>substr_count($raw,'%brand_name_ru%'),'brand_en'=>substr_count($raw,'%brand_name_en%')];
}
// в коридоре донора, если |наш-донор| <= max(25% донора, floor)
function offx($our, $don, bool $rate=false): bool { if ($don===null) return false; $d=abs($our-$don); $tol=0.25*max(abs($don),1); $f=$rate?0.8:2.0; return $d>max($tol,$f); }

$FIELDS = ['words'=>['Объём слов',0],'h2'=>['H2',0],'sections'=>['Секции H2+H3',0],'lists'=>['Списки',0],'tables'=>['Таблицы',0],
 'quotes'=>['Цитаты',0],'strong'=>['<strong>',0],'faq'=>['FAQ',0],'brand_ru'=>['Бренд RU',0],'brand_en'=>['Бренд EN',0],
 'emoji'=>['Эмодзи',0],'entities'=>['Сущности',0],'first_person'=>['«я»',0],'vy'=>['«вы»',0],'imperatives'=>['Императивы',0],
 'numbers_per100'=>['Цифры/100',1],'adj_pct'=>['Прилаг%',1],'nausea_acad'=>['Тошнота',1],'water'=>['Водность%',1]];

$meas = []; $anc = [];
foreach ($TYPES as $t) {
    $f = "$DIR/$t.html"; if (!is_file($f)) { fwrite(STDERR, "нет файла $f\n"); continue; }
    $raw = (string) file_get_contents($f); $meas[$t] = measureFull($a, $t, $raw); $anc[$t] = anchors($raw, $PM, $t);
}

// ── консоль: широкое сравнение + линковка ───────────────────────────────────
$totHit = 0; $totCnt = 0; $pageHit = []; $pageCnt = [];
echo "\n=== ШИРОКОЕ СРАВНЕНИЕ vs реальный $DONOR ===\n";
foreach ($TYPES as $t) {
    if (!isset($meas[$t])) continue;
    $hit = 0; $cnt = 0;
    foreach ($FIELDS as $k => [$lab, $rate]) {
        $ov = $meas[$t][$k]; $dv = $D[$t][$k] ?? null; if ($dv === null) continue;
        $ok = !offx($ov, $dv, (bool)$rate); $hit += $ok?1:0; $cnt++; $totHit += $ok?1:0; $totCnt++;
    }
    $pageHit[$t] = $hit; $pageCnt[$t] = $cnt;
    printf("  %-12s %d/%d = %d%%\n", $LABEL[$t], $hit, $cnt, $cnt?round($hit/$cnt*100):0);
}
$match = $totCnt ? round($totHit/$totCnt*100) : 0;
printf("  ИТОГО: %d/%d = %d%%\n", $totHit, $totCnt, $match);

echo "\n=== ЛИНКОВКА: наш vs $DONOR ===\n";
$oT=0;$dT=0;
foreach ($TYPES as $t) { if(!isset($anc[$t]))continue; $o=count($anc[$t]);$d=(int)($D[$t]['intlinks']??0);$oT+=$o;$dT+=$d;
    printf("  %-12s наш %-4d конкурент %-4d\n", $LABEL[$t], $o, $d); }
printf("  ИТОГО ссылок: наш %d / конкурент %d\n", $oT, $dT);

echo "STATUS " . json_encode(['match'=>$match,'hit'=>$totHit,'total'=>$totCnt,'links_our'=>$oT,'links_donor'=>$dT]) . "\n";

// ── HTML-отчёт (опц.) ───────────────────────────────────────────────────────
if ($OUT === '') exit(0);

$H = "<meta charset='utf-8'><title>Клон vs реальный $DONOR — параметры + линковка</title><style>
body{font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1000px;margin:0 auto;padding:24px;color:#1a1a1a;background:#fafafa}
h1{font-size:22px}h2{font-size:19px;margin-top:34px;border-bottom:2px solid #2563eb;padding-bottom:6px}h3{font-size:16px;margin-top:22px;color:#333}
table{border-collapse:collapse;width:100%;margin:10px 0;background:#fff;font-size:13.5px}
th,td{border:1px solid #e3e3e3;padding:6px 9px;text-align:center}th{background:#f0f4ff;font-weight:600}
td.l,th.l{text-align:left}.ok{background:#e8f7ec;color:#137333}.bad{background:#fdecea;color:#c5221f}.na{color:#999}
.hd{font-weight:700}.chip{display:inline-block;padding:1px 7px;border-radius:6px;font-size:12px;font-weight:600}
.g{background:#e8f7ec;color:#137333}.r{background:#fdecea;color:#c5221f}.y{background:#fff4e5;color:#b06000}
.note{background:#fff;border-left:3px solid #2563eb;padding:8px 14px;margin:10px 0;font-size:14px}small{color:#777}</style>
<h1>Клон vs реальный конкурент <code>$DONOR</code> — все параметры + разбор линковки</h1>
<p class='note'>Слева — наша генерация, справа — реальный сайт <b>$DONOR</b> (замер из корпуса). ✓ = параметр в коридоре донора. Принцип: воспроизвести, не превзойти.</p>";

$H .= "<h2>A. Широкое параметрическое сравнение</h2><table><tr><th class='l'>Параметр</th>";
foreach ($TYPES as $t) $H .= "<th>{$LABEL[$t]}</th>"; $H .= "</tr>";
foreach ($FIELDS as $k => [$lab, $rate]) {
    $H .= "<tr><td class='l hd'>" . htmlspecialchars($lab) . "</td>";
    foreach ($TYPES as $t) { if(!isset($meas[$t])){$H.="<td class='na'>—</td>";continue;}
        $o=$meas[$t][$k]; $d=$D[$t][$k]??null;
        if($d===null){$H.="<td class='na'>$o<br><small>—</small></td>";continue;}
        $ok=!offx($o,$d,(bool)$rate);$H.="<td class='".($ok?'ok':'bad')."'>$o<br><small>ориг $d</small></td>"; }
    $H .= "</tr>";
}
$H .= "<tr><td class='l hd'>Совпадение</td>";
foreach ($TYPES as $t) { if(!isset($pageCnt[$t])){$H.="<td>—</td>";continue;} $p=$pageCnt[$t]?round($pageHit[$t]/$pageCnt[$t]*100):0;$c=$p>=85?'g':($p>=75?'y':'r');$H.="<td><span class='chip $c'>{$p}%</span></td>"; }
$H .= "</tr></table><p class='note'><b>Итого: {$totHit}/{$totCnt} = {$match}%.</b></p>";

$H .= "<h2>B. Разбор перелинковки</h2><h3>B1. Объём ссылок — наш vs конкурент</h3><table><tr><th class='l'>Страница</th><th>Наш</th><th>$DONOR</th><th>Вывод</th></tr>";
foreach ($TYPES as $t) { if(!isset($anc[$t]))continue; $o=count($anc[$t]);$d=(int)($D[$t]['intlinks']??0);
    $v=$o>=$d?"<span class='chip g'>не жиже</span>":($d-$o<=2?"<span class='chip y'>почти как у них</span>":"<span class='chip r'>тоньше на ".($d-$o)."</span>");
    $H.="<tr><td class='l'>{$LABEL[$t]}</td><td class='hd'>$o</td><td>$d</td><td>$v</td></tr>"; }
$H .= "<tr><td class='l hd'>ИТОГО</td><td class='hd'>$oT</td><td class='hd'>$dT</td><td></td></tr></table>";

$H .= "<h3>B2. Анкоры (наши): объём, разнообразие, куда ведут</h3><table><tr><th class='l'>Страница</th><th>Ссылок</th><th>Уник.</th><th>Разнообр.</th><th class='l'>Куда</th><th class='l'>Топ-повторы</th></tr>";
foreach ($TYPES as $t) { if(empty($anc[$t])){$H.="<tr><td class='l'>{$LABEL[$t]}</td><td>0</td><td>—</td><td>—</td><td class='l'>—</td><td class='l'>—</td></tr>";continue;}
    $byT=[];$ph=[];foreach($anc[$t] as $x){$byT[$x['target']]=($byT[$x['target']]??0)+1;$ph[$x['anchor']]=($ph[$x['anchor']]??0)+1;}
    arsort($ph);$tot2=count($anc[$t]);$dv=count($ph);$div=round($dv/$tot2*100);$dc=$div>=70?'g':($div>=50?'y':'r');
    $tstr=[];foreach($byT as $tg=>$c)$tstr[]="{$tg}×{$c}";
    $top=[];foreach(array_slice($ph,0,3,true) as $pp=>$c)$top[]="«".htmlspecialchars(mb_substr($pp,0,20))."»×{$c}";
    $H.="<tr><td class='l'>{$LABEL[$t]}</td><td class='hd'>$tot2</td><td>$dv</td><td><span class='chip $dc'>{$div}%</span></td><td class='l'><small>".implode("  ",$tstr)."</small></td><td class='l'><small>".implode("  ",$top)."</small></td></tr>"; }
$H .= "</table>";

$H .= "<h3>B3. Граф достижимости (входящие ссылки)</h3><table><tr><th class='l'>Страница</th><th class='l'>Входящие с</th><th>Статус</th></tr>";
$reach=[];foreach($TYPES as $t)foreach(($anc[$t]??[]) as $x)$reach[$x['target']][$t]=1;
foreach($TYPES as $t){$in=array_keys($reach[$t]??[]);$st=$in?"<span class='chip g'>ок</span>":"<span class='chip r'>сирота</span>";
    $H.="<tr><td class='l'>{$LABEL[$t]}</td><td class='l'><small>".($in?implode(", ",$in):"—")."</small></td><td>$st</td></tr>";}
$H .= "</table>";

$H .= "<h3>B4. Повтор слов (тошнота) — наш vs конкурент</h3><table><tr><th class='l'>Страница</th><th>Наш</th><th>$DONOR</th><th>Вывод</th></tr>";
foreach($TYPES as $t){if(!isset($meas[$t]))continue;$o=$meas[$t]['nausea_acad'];$d=(float)($D[$t]['nausea_acad']??0);
    $v=$o<=$d+3?"<span class='chip g'>как у них / ниже</span>":"<span class='chip y'>выше на ".round($o-$d)."</span>";
    $H.="<tr><td class='l'>{$LABEL[$t]}</td><td class='hd'>$o</td><td>$d</td><td>$v</td></tr>";}
$H .= "</table>";

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");

<?php
declare(strict_types=1);

/**
 * Боевой тест: измеряет 10 РЕАЛИЗОВАННЫХ контентов (×7 страниц) против их доноров
 * по всем параметрам, считает СИСТЕМАТИЧЕСКИЕ отклонения реалайзера (для отладки),
 * совпадение по каждому прогону и уникальность между повторами одного донора.
 *
 *   php build-battle-report.php <battle-dir> <out.html>
 */

require_once __DIR__ . '/src/Analyzer.php';

$BASE = $argv[1] ?? '/tmp/claude-0/-home-user-cladue/580c9237-8e67-549d-b11b-3f159fa71245/scratchpad/battle';
$OUT  = $argv[2] ?? (__DIR__ . '/../reports/battle-test.html');

$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];
$TYPES = array_keys($LABEL);
$REG   = ['monro'=>'expert','cosmospin'=>'derzkiy','bitz'=>'delovoy','almyra'=>'neutral','vovan'=>'delovoy','bitcasino'=>'expert','vegasy'=>'derzkiy'];
$REGLABEL=['expert'=>'Экспертный «я»','derzkiy'=>'Дерзкий «ты»','delovoy'=>'Деловой «вы»','neutral'=>'Нейтральный'];

$DONORS = json_decode((string)file_get_contents(__DIR__.'/data/donors.json'), true)['sites'];
$runs = [];
foreach (explode("\n", trim((string)@file_get_contents("$BASE/runs.txt"))) as $ln) {
    $ln = trim($ln); if ($ln==='') continue;
    [$id,$donor,$seed] = array_pad(preg_split('/\s+/',$ln),3,'');
    $runs[] = ['id'=>$id,'donor'=>$donor,'seed'=>$seed];
}

$analyzer = new Analyzer();

// параметры: [key, label, isRate]. Донор-значение берём из donorPage().
$PARAMS = [
    ['words','слов',false],['h2','H2',false],['h3','H3',false],['lists','списков',false],
    ['tables','таблиц',false],['quotes','цитат',false],['strong','выделений',false],['faq','FAQ',false],
    ['first_person','1-е лицо',false],['vy','«вы»',false],['imperatives','императивы',false],['emoji','эмодзи',false],
    ['adj_pct','прилаг.%',true],['numbers_per100','цифр/100',true],['entities','сущностей',false],
    ['nausea_acad','тошнота',true],['water','вода%',true],
    ['intlinks','ссылок',false],['brand_ru','бренд ру',false],['brand_en','бренд англ',false],
];

function measurePage(Analyzer $a, string $type, string $rawHtml): array {
    $r = $a->run([[ 'name'=>$type,'url'=>"/$type",'html'=>$rawHtml,'keyword'=>'','lsi'=>[] ]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    $wc = max(1,(int)$m['words_total']);
    $txt = mb_strtolower(strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$rawHtml)));
    $sem=[]; foreach(Intent::THEMES as $ck=>$def){$cc=0;foreach($def['triggers'] as $tr)$cc+=mb_substr_count($txt,$tr);$sem[$ck]=round($cc/$wc*100,1);}
    $pathmap=['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];
    $il=0; if(preg_match_all('#<a[^>]+href="([^"]+)"#i',$rawHtml,$hm)){foreach($hm[1] as $href){$h=rtrim(trim($href),'/');if($h==='')$h='/';$tt=$pathmap[$h]??($pathmap['/'.preg_replace('#^.*/#','',$h)]??null);if($tt!==null&&$tt!==$type)$il++;}}
    return ['words'=>(int)$m['words_total'],'h2'=>(int)$m['h2_count'],'h3'=>(int)($m['h3_count']??0),
        'lists'=>(int)$m['list_count'],'tables'=>(int)($m['table_count']??0),'quotes'=>(int)($m['quote_count']??0),
        'strong'=>(int)$m['strong_count'],'faq'=>(int)$s['faq_questions'],'first_person'=>(int)$s['first_person'],
        'vy'=>(int)$s['second_person'],'imperatives'=>(int)$s['imperatives'],'emoji'=>(int)$s['emoji'],
        'adj_pct'=>round((float)$s['adj_pct'],1),'numbers_per100'=>round((float)$s['numbers_per_100w'],1),
        'entities'=>(int)$s['entities_count'],'nausea_acad'=>round((float)$m['nausea_academic'],1),
        'water'=>round((float)$m['water_percent'],1),'intlinks'=>$il,
        'brand_ru'=>substr_count($rawHtml,'%brand_name_ru%'),'brand_en'=>substr_count($rawHtml,'%brand_name_en%'),
        'sem'=>$sem,'text'=>$txt];
}
function donorPage(array $dp): array { $o=$dp; $o['h3']=max(0,(int)($dp['sections']??0)-(int)($dp['h2']??0)); return $o; }
function verdict($our,$don,bool $rate=false): string {
    if($don===null)return 'na'; $d=abs($our-$don);$tol=0.25*max(abs($don),1);$floor=$rate?0.8:2.0;
    if($d<=max($tol,$floor))return 'ok'; if($d<=max($tol*2,$floor*2))return 'warn'; return 'bad';
}
function shingles(string $t,int $n=3): array {
    $w=preg_split('/\s+/u',trim($t),-1,PREG_SPLIT_NO_EMPTY); $o=[];
    for($i=0;$i+$n<=count($w);$i++)$o[implode(' ',array_slice($w,$i,$n))]=1; return $o;
}
function jac(array $a,array $b): int { if(!$a&&!$b)return 0; $i=count(array_intersect_key($a,$b)); $u=count($a+$b); return $u?(int)round($i/$u*100):0; }

// ── измеряем всё
$data=[]; // [runid][type] = ['our'=>..,'don'=>..]
$agg=[];  // param => list of signed pct deltas
$aggSem=[]; // cluster => deltas
$missing=[];
foreach ($runs as $run) {
    $dprof = $DONORS[$run['donor']]['pages'] ?? [];
    foreach ($TYPES as $t) {
        $f = "$BASE/{$run['id']}/$t.html";
        if (!is_file($f) || filesize($f)<50) { $missing[]="{$run['id']}/$t"; continue; }
        $our = measurePage($analyzer,$t,(string)file_get_contents($f));
        $don = isset($dprof[$t]) ? donorPage($dprof[$t]) : null;
        $data[$run['id']][$t] = ['our'=>$our,'don'=>$don];
        if($don){
            // сравниваем только там, где у донора значение достаточно велико (иначе деление на ~0 даёт шум)
            foreach($PARAMS as $P){ $k=$P[0]; $dv=$don[$k]??null; $floor=$P[2]?0.8:3; if($dv===null||abs($dv)<$floor)continue;
                $agg[$k][] = ($our[$k]-$dv)/max(abs($dv),1)*100; }
            foreach(($don['sem']??[]) as $ck=>$dv){ if($dv<1.0)continue; $ov=$our['sem'][$ck]??0; $aggSem[$ck][]=($ov-$dv)/max($dv,0.1)*100; }
        }
    }
}

// ── агрегатная сводка отладки: медиана знакового отклонения по параметру
function med(array $a){ if(!$a)return 0; sort($a); $n=count($a); return $n%2?$a[($n-1)/2]:round(($a[$n/2-1]+$a[$n/2])/2,1); }
$debugRows='';
foreach($PARAMS as $P){ $k=$P[0]; $arr=$agg[$k]??[]; if(!$arr)continue;
    $m=round(med($arr)); $abs=round(med(array_map('abs',$arr)));
    $cls=abs($m)<=12?'ok':(abs($m)<=30?'warn':'bad'); $sign=$m>0?'+':'';
    $bar=min(100,abs($m)); $dir=$m>0?'right':'left';
    $debugRows.="<tr><td>{$P[1]}</td><td class='v {$cls}'>{$sign}{$m}%</td><td class='v'>{$abs}%</td>"
        ."<td><div class='dbar'><i class='d-{$dir} {$cls}' style='width:{$bar}%'></i></div></td></tr>";
}
$semRows='';
foreach($aggSem as $ck=>$arr){ if(count($arr)<3)continue; $m=round(med($arr)); $cls=abs($m)<=20?'ok':(abs($m)<=50?'warn':'bad');$sign=$m>0?'+':'';
    $lab=Intent::THEMES[$ck]['label']??$ck; $bar=min(100,abs($m));$dir=$m>0?'right':'left';
    $semRows.="<tr><td>{$lab}</td><td class='v {$cls}'>{$sign}{$m}%</td><td><div class='dbar'><i class='d-{$dir} {$cls}' style='width:{$bar}%'></i></div></td></tr>"; }

// ── матрица совпадений по прогонам (green count per page)
$matrix=''; $matHead="<tr><th>Прогон · донор</th>";
foreach($TYPES as $t)$matHead.="<th>".mb_substr($LABEL[$t],0,4)."</th>"; $matHead.="<th>Σ</th></tr>";
$perRunGreen=[];
foreach($runs as $run){ $rid=$run['id']; $reg=$REG[$run['donor']]??''; $tot=0;$okc=0; $cells='';
    foreach($TYPES as $t){ if(!isset($data[$rid][$t])||!$data[$rid][$t]['don']){$cells.="<td class='m m-na'>—</td>";continue;}
        $o=$data[$rid][$t]['our'];$d=$data[$rid][$t]['don']; $ok=0;$n=0;
        foreach($PARAMS as $P){$k=$P[0];$dv=$d[$k]??null;$floor=$P[2]?0.8:3;if($dv===null||abs($dv)<$floor)continue;$n++;if(verdict($o[$k],$dv,$P[2])==='ok')$ok++;}
        foreach(($d['sem']??[]) as $ck=>$dv){if($dv<1.0)continue;$n++;if(verdict($o['sem'][$ck]??0,$dv,true)==='ok')$ok++;}
        $pct=$n?round($ok/$n*100):0; $cls=$pct>=70?'ok':($pct>=50?'warn':'bad');
        $cells.="<td class='m m-$cls' title='$ok/$n'>$pct</td>"; $tot+=$n;$okc+=$ok;
    }
    $sp=$tot?round($okc/$tot*100):0; $scls=$sp>=70?'ok':($sp>=50?'warn':'bad'); $perRunGreen[$rid]=$sp;
    $rl=$REGLABEL[$reg]??$reg;
    $matrix.="<tr><td class='rl'><b>$rid</b> · {$run['donor']} <span class='rtag'>$rl</span></td>$cells<td class='m m-$scls'><b>$sp</b></td></tr>";
}

// ── уникальность повторов одного донора
$pairs=[]; $byDonor=[];
foreach($runs as $run)$byDonor[$run['donor']][]=$run['id'];
$uniqRows='';
foreach($byDonor as $donor=>$ids){ if(count($ids)<2)continue;
    for($i=0;$i<count($ids);$i++)for($j=$i+1;$j<count($ids);$j++){
        $A=$ids[$i];$B=$ids[$j]; $js=[];
        foreach($TYPES as $t){ if(isset($data[$A][$t],$data[$B][$t])){ $js[]=jac(shingles($data[$A][$t]['our']['text']),shingles($data[$B][$t]['our']['text'])); } }
        if(!$js)continue; $avg=round(array_sum($js)/count($js));
        $cls=$avg<=15?'ok':($avg<=35?'warn':'bad');
        $uniqRows.="<tr><td><b>$A</b> vs <b>$B</b></td><td>$donor</td><td class='v $cls'>$avg%</td><td class='v'>".(100-$avg)."%</td></tr>";
    }
}

// ── детальные вкладки по каждому прогону
function chip(string $label,$our,$don,bool $rate=false):string{
    $v=verdict($our,$don,$rate); $dv=$don===null?'—':$don;
    return "<div class='chip v-$v'><span class='cv'>$our</span><span class='cd'>ор $dv</span><span class='cl'>$label</span></div>";
}
$runTabs=''; $runPanes='';
foreach($runs as $ri=>$run){ $rid=$run['id']; $reg=$REGLABEL[$REG[$run['donor']]??'']??'';
    $ta=$ri===0?' active':''; $runTabs.="<button class='rtab{$ta}' data-run='$rid'>$rid<span class='rt2'>{$run['donor']}</span></button>";
    $pt='';$pp='';
    foreach($TYPES as $pi=>$t){ if(!isset($data[$rid][$t]))continue; $o=$data[$rid][$t]['our'];$d=$data[$rid][$t]['don'];
        $chips=''; foreach($PARAMS as $P)$chips.=chip($P[1],$o[$P[0]],$d[$P[0]]??null,$P[2]);
        // sem
        $sem=''; $dsem=$d['sem']??[]; arsort($dsem); $sh=0;
        foreach(array_keys($dsem) as $ck){if($sh>=6)break;$ov=$o['sem'][$ck]??0;$dv=$dsem[$ck]??0;if($ov<=0&&$dv<=0)continue;$sh++;
            $vd=verdict($ov,$dv,true);$sem.="<div class='chip v-$vd'><span class='cv'>$ov</span><span class='cd'>ор $dv</span><span class='cl'>".mb_substr(Intent::THEMES[$ck]['label']??$ck,0,14)."</span></div>";}
        $pa=$pi===0?' active':''; $pt.="<button class='ptab{$pa}' data-p='$rid:$t'>".$LABEL[$t]."</button>";
        $pp.="<div class='pp{$pa}' data-p='$rid:$t'><div class='chips'>$chips</div><div class='pgt'>Семантика (наш/ориг, на 100 слов)</div><div class='chips'>$sem</div></div>";
    }
    $sa=$ri===0?' active':''; $runPanes.="<section class='rp{$sa}' data-run='$rid'><p class='rd'>Донор <b>{$run['donor']}</b> · регистр $reg · совпадение <b>".($perRunGreen[$rid]??0)."%</b></p><div class='ptabs'>$pt</div>$pp</section>";
}

$miss = $missing ? "<div class='warnbox'>Не готово/пусто: ".implode(', ',$missing)."</div>" : '';

$css = <<<CSS
:root{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--ok:#1f9d6b;--warn:#c98a12;--bad:#d0552e;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--ok:#33c08a;--warn:#e0a938;--bad:#e87a52}}
:root[data-theme=dark]{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--ok:#33c08a;--warn:#e0a938;--bad:#e87a52}
:root[data-theme=light]{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--ok:#1f9d6b;--warn:#c98a12;--bad:#d0552e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans)}
.wrap{max-width:940px;margin:0 auto;padding:24px 16px 90px}
.eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:22px;margin:6px 0 8px}.lead{color:var(--muted);font-size:13.5px;max-width:82ch;margin:0 0 16px}
h2{font-size:16px;margin:26px 0 8px}.hint{color:var(--muted);font-size:12px;margin:0 0 10px}
.tabsel{display:flex;gap:8px;margin:0 0 16px;flex-wrap:wrap}
.tabsel button{cursor:pointer;border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:8px 14px;border-radius:10px;font:700 13px var(--sans)}
.tabsel button.active{background:var(--accent);border-color:var(--accent);color:#fff}
.view{display:none}.view.active{display:block}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:11px}
table{border-collapse:collapse;width:100%;font-size:12.5px;min-width:480px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right}
th{color:var(--muted);font-size:10px;text-transform:uppercase}td:first-child,th:first-child{text-align:left}
td.v{font-family:var(--mono)}.v.ok{color:var(--ok)}.v.warn{color:var(--warn)}.v.bad{color:var(--bad)}
.dbar{position:relative;width:120px;height:9px;background:var(--soft);border-radius:5px;margin-left:auto}
.dbar i{position:absolute;top:0;height:100%;border-radius:5px}.dbar i.d-right{left:50%}.dbar i.d-left{right:50%}
.dbar i.ok{background:var(--ok)}.dbar i.warn{background:var(--warn)}.dbar i.bad{background:var(--bad)}
.m{font-family:var(--mono);font-weight:700;text-align:center;color:#fff}
.m-ok{background:var(--ok)}.m-warn{background:var(--warn)}.m-bad{background:var(--bad)}.m-na{background:var(--soft);color:var(--muted)}
.rl{font-size:12px}.rtag,.rt2{color:var(--muted);font-weight:500;font-size:10.5px}
.rtab .rt2{display:block}
.warnbox{background:color-mix(in srgb,var(--warn) 12%,transparent);border:1px solid var(--warn);border-radius:9px;padding:9px 12px;font-size:12.5px;margin:10px 0}
.rd{color:var(--muted);font-size:13px;margin:0 0 12px;padding:9px 12px;background:var(--soft);border-radius:9px}
.rd b{color:var(--ink)}
.ptabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px;border-bottom:1px solid var(--line);padding-bottom:9px}
.ptab{cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--muted);padding:5px 11px;border-radius:18px;font:600 12px var(--sans)}
.ptab.active{background:var(--accent);border-color:var(--accent);color:#fff}
.pp{display:none}.pp.active{display:block}
.pgt{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:700;margin:14px 0 8px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{background:var(--soft);border-radius:8px;padding:5px 8px;min-width:58px;display:flex;flex-direction:column;gap:1px;border-left:3px solid var(--line)}
.chip .cv{font:700 15px var(--mono)}.chip .cd{font:600 10px var(--mono);color:var(--muted)}.chip .cl{font-size:10px;color:var(--muted)}
.chip.v-ok{border-left-color:var(--ok)}.chip.v-warn{border-left-color:var(--warn)}.chip.v-bad{border-left-color:var(--bad)}.chip.v-na{border-left-color:var(--line)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
@media(max-width:640px){.cards{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:13px}
.card .big{font:700 24px var(--mono)}.card .sub{color:var(--muted);font-size:12px}
.note{margin-top:14px;padding:11px 14px;border-left:3px solid var(--accent);background:var(--panel);border:1px solid var(--line);border-radius:9px;font-size:13px}
.foot{color:var(--muted);font-size:11.5px;margin-top:22px;text-align:center}
CSS;

$js = <<<JS
document.querySelectorAll('.tabsel button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('.tabsel button').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.dataset.view===b.dataset.view));});
document.querySelectorAll('.rtab').forEach(b=>b.onclick=()=>{
  const id=b.dataset.run;
  document.querySelectorAll('.rtab').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.rp').forEach(s=>s.classList.toggle('active',s.dataset.run===id));});
document.querySelectorAll('.ptab').forEach(b=>b.onclick=()=>{
  const key=b.dataset.p,run=key.split(':')[0];
  document.querySelectorAll('.rp[data-run="'+run+'"] .ptab').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.rp[data-run="'+run+'"] .pp').forEach(p=>p.classList.toggle('active',p.dataset.p===key));});
JS;

$nRuns=count($runs); $nPages=0; foreach($data as $r)$nPages+=count($r);
$html = "<!--battle test--><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
 . "<title>Боевой тест · 10 контентов · отладка</title><style>$css</style><div class='wrap'>"
 . "<div class='eyebrow'>Боевой тест · авто-реалайзер · отладка по параметрам</div>"
 . "<h1>10 контентов, разные стили, повторы — сверка с оригиналами</h1>"
 . "<p class='lead'>$nRuns прогонов ($nPages страниц) реализованы авто-реалайзером по планам генератора и сверены с донорами по всем параметрам. Первая вкладка — сводка систематических отклонений реалайзера (что докручивать), матрица совпадений и уникальность повторов. Вторая — детально по каждому прогону.</p>"
 . "$miss"
 . "<div class='tabsel'><button class='active' data-view='debug'>🔧 Сводка отладки</button><button data-view='runs'>📄 По прогонам</button></div>"

 . "<div class='view active' data-view='debug'>"
 . "<h2>Систематическое отклонение реалайзера по параметру</h2>"
 . "<p class='hint'>Медиана знакового отклонения (наш − оригинал) по всем страницам. <b>+</b> = перебор, <b>−</b> = недобор. Зелёное ≤12%, это «в норме»; оранжевое/красное — параметр, который реалайзер стабильно мажет → правим промпт/движок.</p>"
 . "<div class='tw'><table><thead><tr><th>Параметр</th><th>Медиана Δ</th><th>|Δ| тип.</th><th>Смещение (−недобор · перебор+)</th></tr></thead><tbody>$debugRows</tbody></table></div>"
 . "<h2>Семантические кластеры — систематическое отклонение</h2>"
 . "<div class='tw'><table><thead><tr><th>Кластер</th><th>Медиана Δ</th><th>Смещение</th></tr></thead><tbody>$semRows</tbody></table></div>"
 . "<h2>Матрица совпадений: прогон × страница (% параметров в норме)</h2>"
 . "<p class='hint'>Каждая ячейка — доля параметров страницы, попавших в коридор донора. Зелёное ≥70%, оранжевое ≥50%.</p>"
 . "<div class='tw'><table><thead>$matHead</thead><tbody>$matrix</tbody></table></div>"
 . "<h2>Уникальность: повторы одного донора (разный seed)</h2>"
 . "<p class='hint'>Пересечение текста (шинглы 3-грамм) между двумя прогонами ОДНОГО донора. Чем ниже — тем уникальнее контент при той же форме.</p>"
 . "<div class='tw'><table><thead><tr><th>Пара</th><th>Донор</th><th>Пересечение</th><th>Уникальность</th></tr></thead><tbody>$uniqRows</tbody></table></div>"
 . "<div class='note'>🔧 <b>Как читать для отладки:</b> смотри верхнюю таблицу — параметры с большим смещением это и есть цель докрутки (например, если «слов» стабильно −20%, поднимаем целевой объём в промпте; если кластер «Деньги» +40%, режем денежную лексику). Матрица показывает, какие страницы/стили тянут вниз.</div>"
 . "</div>"

 . "<div class='view' data-view='runs'>"
 . "<div class='tabsel' style='margin-top:4px'>$runTabs</div>$runPanes"
 . "</div>"

 . "<div class='foot'>Реализация — авто-реалайзер (сабагенты) по планам Planner+PromptBuilder. Замер — Analyzer по готовому тексту. Оригиналы — data/donors.json.</div>"
 . "</div><script>$js</script>";

file_put_contents($OUT, $html);
$avgAll = $perRunGreen ? round(array_sum($perRunGreen)/count($perRunGreen)) : 0;
fwrite(STDERR, "→ $OUT | прогонов ".count($runs)." страниц $nPages | среднее совпадение $avgAll% | не готово: ".count($missing)."\n");
echo "STATUS ".json_encode(['match'=>$avgAll,'pages'=>$nPages,'missing'=>count($missing),'perRun'=>$perRunGreen])."\n";

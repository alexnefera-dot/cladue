<?php
declare(strict_types=1);

/**
 * Before/after отладки: сравнивает СТАРЫЙ прогон (battle) и НОВЫЙ (battle2)
 * по одним и тем же донорам — показывает, как правки промпта/метрики сдвинули
 * систематические отклонения реалайзера. Печатает таблицу в stderr и пишет HTML.
 *
 *   php build-battle-compare.php <old-dir> <new-dir> <out.html>
 */

require_once __DIR__ . '/src/Analyzer.php';

$OLD = $argv[1] ?? '/tmp/claude-0/-home-user-cladue/580c9237-8e67-549d-b11b-3f159fa71245/scratchpad/battle';
$NEW = $argv[2] ?? '/tmp/claude-0/-home-user-cladue/580c9237-8e67-549d-b11b-3f159fa71245/scratchpad/battle2';
$OUT = $argv[3] ?? (__DIR__ . '/../reports/battle-compare.html');

$LABEL=['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];
$TYPES=array_keys($LABEL);
$DONORS=json_decode((string)file_get_contents(__DIR__.'/data/donors.json'),true)['sites'];
$a=new Analyzer();

$PARAMS=[['words','слов',false],['h2','H2',false],['h3','H3',false],['lists','списков',false],['tables','таблиц',false],
 ['quotes','цитат',false],['strong','выделений',false],['faq','FAQ',false],['first_person','1-е лицо',false],
 ['vy','«вы»',false],['imperatives','императивы',false],['emoji','эмодзи',false],['adj_pct','прилаг.%',true],
 ['numbers_per100','цифр/100',true],['entities','сущностей',false],['nausea_acad','тошнота',true],['water','вода%',true],
 ['intlinks','ссылок',false],['brand_ru','бренд ру',false],['brand_en','бренд англ',false]];

function measureP(Analyzer $a,string $t,string $raw):array{
 $r=$a->run([['name'=>$t,'url'=>"/$t",'html'=>$raw,'keyword'=>'','lsi'=>[]]]);$p=$r['pages'][0];$m=$p['metrics'];$s=$p['stylistics'];
 $wc=max(1,(int)$m['words_total']);$txt=mb_strtolower(strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$raw)));
 $sem=[];foreach(Intent::THEMES as $ck=>$def){$cc=0;foreach($def['triggers'] as $tr)$cc+=mb_substr_count($txt,$tr);$sem[$ck]=round($cc/$wc*100,1);}
 $pm=['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];$il=0;
 if(preg_match_all('#<a[^>]+href="([^"]+)"#i',$raw,$hm))foreach($hm[1] as $h){$h=rtrim(trim($h),'/');if($h==='')$h='/';$tt=$pm[$h]??($pm['/'.preg_replace('#^.*/#','',$h)]??null);if($tt!==null&&$tt!==$t)$il++;}
 return['words'=>(int)$m['words_total'],'h2'=>(int)$m['h2_count'],'h3'=>(int)($m['h3_count']??0),'lists'=>(int)$m['list_count'],
  'tables'=>(int)($m['table_count']??0),'quotes'=>(int)($m['quote_count']??0),'strong'=>(int)$m['strong_count'],'faq'=>(int)$s['faq_questions'],
  'first_person'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],'imperatives'=>(int)$s['imperatives'],'emoji'=>(int)$s['emoji'],
  'adj_pct'=>round((float)$s['adj_pct'],1),'numbers_per100'=>round((float)$s['numbers_per_100w'],1),'entities'=>(int)$s['entities_count'],
  'nausea_acad'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1),'intlinks'=>$il,
  'brand_ru'=>substr_count($raw,'%brand_name_ru%'),'brand_en'=>substr_count($raw,'%brand_name_en%'),'sem'=>$sem];
}
function donorP(array $dp):array{$o=$dp;$o['h3']=max(0,(int)($dp['sections']??0)-(int)($dp['h2']??0));return $o;}
function verdict($our,$don,bool $rate=false):string{if($don===null)return 'na';$d=abs($our-$don);$tol=0.25*max(abs($don),1);$f=$rate?0.8:2.0;if($d<=max($tol,$f))return 'ok';if($d<=max($tol*2,$f*2))return 'warn';return 'bad';}
function med(array $x){if(!$x)return 0;sort($x);$n=count($x);return $n%2?$x[($n-1)/2]:round(($x[$n/2-1]+$x[$n/2])/2,1);}

// читаем manifest нового прогона: newid donor seed → маппим на старый прогон того же донора
function runsOf(string $dir):array{$o=[];foreach(explode("\n",trim((string)@file_get_contents("$dir/runs.txt"))) as $l){$l=trim($l);if($l==='')continue;[$id,$d]=array_pad(preg_split('/\s+/',$l),3,'');$o[]=['id'=>$id,'donor'=>$d];}return $o;}
$oldRuns=runsOf($OLD);$newRuns=runsOf($NEW);
$oldByDonor=[];foreach($oldRuns as $r)$oldByDonor[$r['donor']]??=$r['id'];

function aggFor(Analyzer $a,string $base,array $runs,array $TYPES,array $PARAMS,array $DONORS):array{
 $agg=[];$aggSem=[];$okc=0;$tot=0;
 foreach($runs as $run){$dp=$DONORS[$run['donor']]['pages']??[];
  foreach($TYPES as $t){$f="$base/{$run['id']}/$t.html";if(!is_file($f)||filesize($f)<50)continue;
   $o=measureP($a,$t,(string)file_get_contents($f));$d=isset($dp[$t])?donorP($dp[$t]):null;if(!$d)continue;
   foreach($PARAMS as $P){$k=$P[0];$dv=$d[$k]??null;$fl=$P[2]?0.8:3;if($dv===null||abs($dv)<$fl)continue;
    $agg[$k][]=($o[$k]-$dv)/max(abs($dv),1)*100;$tot++;if(verdict($o[$k],$dv,$P[2])==='ok')$okc++;}
   foreach(($d['sem']??[]) as $ck=>$dv){if($dv<1.0)continue;$ov=$o['sem'][$ck]??0;$aggSem[$ck][]=($ov-$dv)/max($dv,0.1)*100;$tot++;if(verdict($ov,$dv,true)==='ok')$okc++;}
  }}
 return['agg'=>$agg,'sem'=>$aggSem,'match'=>$tot?round($okc/$tot*100):0];
}

// сравниваем только доноров, присутствующих в новом прогоне
$donorsNew=array_values(array_unique(array_map(fn($r)=>$r['donor'],$newRuns)));
$oldSubset=array_values(array_filter($oldRuns,fn($r)=>in_array($r['donor'],$donorsNew,true)));
// по одному старому прогону на донора (первый)
$seen=[];$oldSel=[];foreach($oldSubset as $r){if(isset($seen[$r['donor']]))continue;$seen[$r['donor']]=1;$oldSel[]=$r;}

$OLDR=aggFor($a,$OLD,$oldSel,$TYPES,$PARAMS,$DONORS);
$NEWR=aggFor($a,$NEW,$newRuns,$TYPES,$PARAMS,$DONORS);

$rows='';$watch=['numbers_per100'=>1,'entities'=>1,'faq'=>1,'nausea_acad'=>1];
foreach($PARAMS as $P){$k=$P[0];$o=$OLDR['agg'][$k]??[];$n=$NEWR['agg'][$k]??[];if(!$o&&!$n)continue;
 $mo=round(med($o));$mn=round(med($n));$impr=abs($mn)<abs($mo);$star=isset($watch[$k])?' ★':'';
 $cls=abs($mn)<=12?'ok':(abs($mn)<=30?'warn':'bad');$arrow=$impr?'↓':($mn==$mo?'=':'↑');
 $rows.="<tr><td>{$P[1]}$star</td><td class='v'>".sprintf('%+d',$mo)."%</td><td class='v {$cls}'>".sprintf('%+d',$mn)."% $arrow</td></tr>";}
$semRows='';
foreach(($NEWR['sem']) as $ck=>$n){$o=$OLDR['sem'][$ck]??[];if(count($n)<2)continue;$mo=round(med($o));$mn=round(med($n));
 $cls=abs($mn)<=20?'ok':(abs($mn)<=50?'warn':'bad');$arrow=abs($mn)<abs($mo)?'↓':($mn==$mo?'=':'↑');
 $lab=Intent::THEMES[$ck]['label']??$ck;$semRows.="<tr><td>$lab</td><td class='v'>".sprintf('%+d',$mo)."%</td><td class='v {$cls}'>".sprintf('%+d',$mn)."% $arrow</td></tr>";}

$css="body{font:15px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:720px;margin:0 auto;padding:24px 16px 70px;background:#f4f6fb;color:#161d29}@media(prefers-color-scheme:dark){body{background:#0d121b;color:#e7ecf5}}h1{font-size:21px}h2{font-size:16px;margin-top:26px}table{border-collapse:collapse;width:100%;font-size:13px;border:1px solid #ccc4;border-radius:8px;overflow:hidden}th,td{padding:7px 10px;border-bottom:1px solid #ccc3;text-align:right}th:first-child,td:first-child{text-align:left}th{font-size:10.5px;text-transform:uppercase;color:#5d6b82}td.v{font-family:ui-monospace,Menlo,monospace}.v.ok{color:#1f9d6b}.v.warn{color:#c98a12}.v.bad{color:#d0552e}.big{font-size:26px;font-weight:700;font-family:ui-monospace,monospace}.card{display:inline-block;background:#fff2;border:1px solid #ccc4;border-radius:11px;padding:12px 18px;margin:8px 8px 0 0}.muted{color:#5d6b82;font-size:13px}";
$html="<meta charset='utf-8'><meta name=viewport content='width=device-width,initial-scale=1'><title>Отладка: до/после</title><style>$css</style>"
."<h1>Отладка реалайзера: до → после правок</h1>"
."<p class='muted'>Одни и те же доноры (".implode(', ',$donorsNew)."), старый промпт против тюненного. ★ — параметры, которые чинили. Медиана знакового отклонения (наш−оригинал); стрелка ↓ = стало ближе к нулю.</p>"
."<div><div class='card'><div class='muted'>совпадение ДО</div><div class='big'>{$OLDR['match']}%</div></div>"
."<div class='card'><div class='muted'>совпадение ПОСЛЕ</div><div class='big'>{$NEWR['match']}%</div></div></div>"
."<h2>Параметры</h2><table><thead><tr><th>Параметр</th><th>Δ до</th><th>Δ после</th></tr></thead><tbody>$rows</tbody></table>"
."<h2>Семантические кластеры</h2><table><thead><tr><th>Кластер</th><th>Δ до</th><th>Δ после</th></tr></thead><tbody>$semRows</tbody></table>";
file_put_contents($OUT,$html);
fwrite(STDERR,"→ $OUT | совпадение до {$OLDR['match']}% → после {$NEWR['match']}%\n");
fwrite(STDERR,sprintf("  цифр/100: %+d%% → %+d%% | сущностей: %+d%% → %+d%% | FAQ: %+d%% → %+d%% | тошнота: %+d%% → %+d%%\n",
 round(med($OLDR['agg']['numbers_per100']??[])),round(med($NEWR['agg']['numbers_per100']??[])),
 round(med($OLDR['agg']['entities']??[])),round(med($NEWR['agg']['entities']??[])),
 round(med($OLDR['agg']['faq']??[])),round(med($NEWR['agg']['faq']??[])),
 round(med($OLDR['agg']['nausea_acad']??[])),round(med($NEWR['agg']['nausea_acad']??[]))));

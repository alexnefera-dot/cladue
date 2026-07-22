<?php
declare(strict_types=1);
/**
 * Замер уникальности контента при ОДНОМ доноре: генерит K вариантов одного
 * типа с разными seed и считает пересечение тем/фактов/сущностей (Jaccard).
 * Форма (объём/структура) фиксируется донором, начинка — из пулов.
 *   php measure-uniqueness.php <донор> <тип> <K>
 */
require_once __DIR__ . '/src/Generator/Planner.php';
require_once __DIR__ . '/src/Generator/StyleProfile.php';
$donors=json_decode(file_get_contents(__DIR__ . '/data/donors.json'),true)['sites'];
$donorName=$argv[1]??'aurora'; $type=$argv[2]??'main'; $K=(int)($argv[3]??6);
$donor=$donors[$donorName]; $donor['name']=$donorName;
$planner=new Planner();

function topics($spec){$o=[];foreach($spec['sections'] as $s){if(isset($s['topic']))$o[]=$s['topic'];}return array_values(array_unique($o));}
function facts($spec){$o=[];foreach($spec['sections'] as $s){foreach($s['fact_seeds']??[] as $f)$o[]=mb_substr($f,0,60);}return array_values(array_unique($o));}
function ents($spec){$o=[];foreach($spec['sections'] as $s){foreach($s['entities']??[] as $e)$o[]=$e;}return array_values(array_unique($o));}
function jac($a,$b){$i=count(array_intersect($a,$b));$u=count(array_unique(array_merge($a,$b)));return $u?round($i/$u*100):0;}

$specs=[];
for($v=1;$v<=$K;$v++){
  $style=StyleProfile::fromDonor($donor['style']??[],new Rng('ds:'.$donorName.':v'.$v));
  $specs[]=$planner->plan($type,['ru'=>'Демо','en'=>'Demo','domain'=>'d.win','seed'=>"v$v:$donorName"],$style,$donor);
}
// pairwise overlaps
$dims=['темы'=>'topics','факты'=>'facts','сущности'=>'ents'];
foreach($dims as $lbl=>$fn){
  $ov=[];$allitems=[];
  for($i=0;$i<$K;$i++){for($j=$i+1;$j<$K;$j++){$ov[]=jac($fn($specs[$i]),$fn($specs[$j]));}}
  for($i=0;$i<$K;$i++)$allitems=array_merge($allitems,$fn($specs[$i]));
  printf("%-9s: средн. пересечение %d%% · всего уникальных на %d вариантов: %d\n",$lbl,round(array_sum($ov)/max(1,count($ov))),$K,count(array_unique($allitems)));
}
// показать 2 варианта: темы
echo "\n— Варианты 1 и 2 (донор $donorName, $type), их разделы:\n";
foreach([0,1] as $vi){echo "  V".($vi+1).": ".implode(' · ',array_slice(topics($specs[$vi]),0,10))."\n";}
echo "\n— По 2 факт-семени из каждого:\n";
foreach([0,1] as $vi){$f=facts($specs[$vi]);echo "  V".($vi+1).": ".mb_substr($f[0]??'',0,55)." | ".mb_substr($f[1]??'',0,55)."\n";}
// целевая форма (что донор фиксирует)
$t=$specs[0]['targets'];printf("\nФорма (одинакова у всех, из донора %s): words≈%d, sect≈%d, emoji≈%d, faq≈%d, num≈%s\n",$donorName,$t['words'],$t['sections_total'],$t['emoji_body'],$t['faq_count'],$t['numbers_per100']);

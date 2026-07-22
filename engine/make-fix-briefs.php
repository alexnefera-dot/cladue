<?php
declare(strict_types=1);

/**
 * Verify-loop, шаг «замер → адресный бриф правок».
 * Меряет реализованные страницы против донора и для каждой пишет КОНКРЕТНЫЙ
 * бриф: какие параметры вылетели, в какую сторону и что именно сделать
 * (убрать N цифр, добавить абзац по кластеру X с ключами …, и т.п.).
 * Текущий HTML копируется в out-dir для правки на месте.
 *
 *   php make-fix-briefs.php <src-dir> <out-dir>
 */

require_once __DIR__ . '/src/Analyzer.php';

$SRC = $argv[1] ?? '';
$OUT = $argv[2] ?? '';
if ($SRC==='' || $OUT==='') { fwrite(STDERR,"usage: make-fix-briefs.php <src> <out>\n"); exit(1); }

$LABEL=['main'=>'главная','zerkalo'=>'зеркало','vhod'=>'вход','registracia'=>'регистрация','bonus'=>'бонусы','slots'=>'слоты','app'=>'приложение'];
$TYPES=array_keys($LABEL);
$DONORS=json_decode((string)file_get_contents(__DIR__.'/data/donors.json'),true)['sites'];
$a=new Analyzer();

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
function offx($our,$don,bool $rate=false):bool{if($don===null)return false;$d=abs($our-$don);$tol=0.25*max(abs($don),1);$f=$rate?0.8:2.0;return $d>max($tol,$f);}

function runsOf(string $dir):array{$o=[];foreach(explode("\n",trim((string)@file_get_contents("$dir/runs.txt"))) as $l){$l=trim($l);if($l==='')continue;[$id,$d]=array_pad(preg_split('/\s+/',$l),3,'');$o[]=['id'=>$id,'donor'=>$d];}return $o;}
$runs=runsOf($SRC);
if(!is_dir($OUT))mkdir($OUT,0777,true);
copy("$SRC/runs.txt","$OUT/runs.txt");

$totalFix=0;$pagesWithFix=0;
foreach($runs as $run){
 $dp=$DONORS[$run['donor']]['pages']??[];
 $od="$OUT/{$run['id']}"; if(!is_dir($od))mkdir($od,0777,true);
 foreach($TYPES as $t){
  $f="$SRC/{$run['id']}/$t.html"; if(!is_file($f))continue;
  $raw=(string)file_get_contents($f); copy($f,"$od/$t.html"); // текущий html для правки на месте
  $o=measureP($a,$t,$raw); $d=isset($dp[$t])?donorP($dp[$t]):null; if(!$d)continue;
  $w=max(1,$o['words']);
  $fixes=[];

  // объём
  if(offx($o['words'],$d['words'])){ $diff=$d['words']-$o['words'];
    $fixes[]=($diff>0?"ОБЪЁМ: добавь ~".abs($diff)." слов прозы":"ОБЪЁМ: сократи ~".abs($diff)." слов (без потери фактуры)"); }
  // плотность цифр
  if(offx($o['numbers_per100'],$d['numbers_per100'],true)){
    $cur=$o['numbers_per100'];$tg=$d['numbers_per100'];
    if($cur>$tg){$rm=(int)ceil(($cur-$tg)/100*$w); $fixes[]="ЦИФРЫ: слишком плотно ({$cur}/100 vs цель {$tg}). Убери ~{$rm} числовых упоминаний ИЗ ПРОЗЫ (проценты/суммы/сроки перепиши словами: «около трети», «за пару минут»). Числа в ТАБЛИЦАХ и в стартовой фактуре НЕ трогай.";}
    else{$ad=(int)ceil(($tg-$cur)/100*$w); $fixes[]="ЦИФРЫ: маловато ({$cur}/100 vs цель {$tg}). Добавь ~{$ad} конкретных чисел из фактуры (RTP, суммы, сроки).";}
  }
  // сущности
  if(offx($o['entities'],$d['entities'])){ $diff=$o['entities']-$d['entities'];
    if($diff>0)$fixes[]="СУЩНОСТИ: убери ~{$diff} названий игр/провайдеров (оставь ".$d['entities']."). Замени на общие слова («слот», «провайдер»).";
  }
  // FAQ
  if(offx($o['faq'],$d['faq'])){ $diff=$o['faq']-$d['faq'];
    if($diff>0)$fixes[]="FAQ: убери ~{$diff} вопросов (цель ".$d['faq']."). ".($d['faq']<=1?"Лучше вовсе без FAQ-блока.":"");
    else $fixes[]="FAQ: добавь ~".abs($diff)." вопросов (цель ".$d['faq'].").";
  }
  // H3 / strong
  if(offx($o['h3'],$d['h3'])){ $diff=$d['h3']-$o['h3']; $fixes[]=($diff>0?"H3: добавь ~$diff подзаголовков (разбей крупные блоки)":"H3: убери ~".abs($diff)." подзаголовков"); }
  if(offx($o['strong'],$d['strong'])){ $diff=$d['strong']-$o['strong']; if($diff>0)$fixes[]="ВЫДЕЛЕНИЯ: оберни ещё ~$diff ключевых фактов в <strong>"; }
  // тошнота
  if(offx($o['nausea_acad'],$d['nausea_acad'],true)&&$o['nausea_acad']>$d['nausea_acad']){
    $fixes[]="ТОШНОТА: {$o['nausea_acad']}% vs {$d['nausea_acad']}% — снизь повтор самых частых слов, замени синонимами.";
  }
  // регистр
  if(offx($o['vy'],$d['vy'])&&$d['vy']>=$o['vy']){ $diff=$d['vy']-$o['vy']; if($diff>=3)$fixes[]="РЕГИСТР «вы»: добавь ~$diff явных «вы/вам/ваш» (не только глагольные формы)."; }
  if(offx($o['first_person'],$d['first_person'])&&$d['first_person']>=$o['first_person']){ $diff=$d['first_person']-$o['first_person']; if($diff>=4)$fixes[]="РЕГИСТР «я»: усиль первое лицо (+~$diff «я/мне/мой»)."; }
  // семантические кластеры
  foreach(($d['sem']??[]) as $ck=>$dv){ if($dv<1.0)continue; $ov=$o['sem'][$ck]??0; if(!offx($ov,$dv,true))continue;
    $lab=Intent::THEMES[$ck]['label']??$ck; $trg=implode(', ',array_slice(Intent::THEMES[$ck]['triggers']??[],0,6));
    if($ov<$dv){$need=(int)ceil(($dv-$ov)/100*$w); $fixes[]="КЛАСТЕР «{$lab}» ниже цели ({$ov} vs {$dv}/100): добавь абзац/пункты по теме с ключами ({$trg}) — ещё ~{$need} вхождений СЛОВАМИ, без новых цифр.";}
    else{$fixes[]="КЛАСТЕР «{$lab}» выше цели ({$ov} vs {$dv}/100): проредь эти ключи ({$trg}), перефразируй нейтрально.";}
  }

  $brief="# Правки для страницы «{$LABEL[$t]}» (донор {$run['donor']})\n"
   ."Файл: {$t}.html — ОТРЕДАКТИРУЙ ЕГО НА МЕСТЕ, сохранив всё, что уже в норме (объём, структуру, ссылки, бренд-переменные, таблицы).\n"
   ."Правь ТОЛЬКО перечисленное ниже, точечно. Инварианты не ломай: %brand_%-переменные, ссылки без self-link, JSON-LD, дата-штамп.\n\n";
  if($fixes){ $brief.="## Что поправить (".count($fixes)." шт):\n"; foreach($fixes as $i=>$fx)$brief.=($i+1).". $fx\n"; $totalFix+=count($fixes);$pagesWithFix++; }
  else { $brief.="## Всё в норме — правки не нужны. Оставь файл как есть.\n"; }
  file_put_contents("$od/brief-$t.md",$brief);
 }
}
fwrite(STDERR,"→ $OUT | брифов по страницам, правок всего: $totalFix на $pagesWithFix страницах\n");

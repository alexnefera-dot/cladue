<?php
declare(strict_types=1);

/**
 * Боевой прогон ОДНОЙ связки, одной командой, без агентов:
 *   Planner → PromptBuilder → realize.php (1 вызов/страницу) →
 *   механическая перелинковка → [опц.] verify-loop (замер→бриф→адресный фикс) до порога.
 *
 *   php realize-run.php --donor=monro --out=/path/run [--seed=prod1] [--effort=medium]
 *                       [--verify] [--threshold=78] [--passes=2]
 *
 * Бренд — переменные %brand_%; для подстановки демо-имени добавь
 *   --brand-ru=Монрополь --brand-en=Monropol --domain=monropol.com --date="июль 2026"
 */

require_once __DIR__ . '/src/Analyzer.php';

$opts = [];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--([^=]+)=(.*)$/s', $a, $m)) { $opts[$m[1]] = $m[2]; }
    elseif (preg_match('/^--(.+)$/', $a, $m)) { $opts[$m[1]] = true; }
}
$donor  = $opts['donor'] ?? '';
$out    = rtrim($opts['out'] ?? '', '/');
$seed   = $opts['seed'] ?? 'prod';
$effort = $opts['effort'] ?? 'medium';
$verify = isset($opts['verify']);
$thr    = (int)($opts['threshold'] ?? 78);
$passes = (int)($opts['passes'] ?? 2);
if ($donor === '' || $out === '') { fwrite(STDERR, "usage: realize-run.php --donor=<name> --out=<dir> [--verify] [--threshold=78] [--passes=2]\n"); exit(1); }

$ENGINE = __DIR__;
$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
$DONORS = json_decode((string)file_get_contents("$ENGINE/data/donors.json"), true)['sites'];
if (!isset($DONORS[$donor])) { fwrite(STDERR, "донор '$donor' не найден\n"); exit(1); }
$reg  = $DONORS[$donor]['style']['register'] ?? 'neutral';
$dpAll = $DONORS[$donor]['pages'];
@mkdir($out, 0777, true);

$analyzer = new Analyzer();
$COST_IN = 0; $COST_OUT = 0;

// ── измерение готовой страницы (те же метрики, что в отчётах) ───────────────
function measureP(Analyzer $a, string $t, string $raw): array {
    $r = $a->run([['name'=>$t,'url'=>"/$t",'html'=>$raw,'keyword'=>'','lsi'=>[]]]); $p=$r['pages'][0]; $m=$p['metrics']; $s=$p['stylistics'];
    $wc = max(1,(int)$m['words_total']); $txt = mb_strtolower(strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$raw)));
    $sem=[]; foreach(Intent::THEMES as $ck=>$def){$cc=0;foreach($def['triggers'] as $tr)$cc+=mb_substr_count($txt,$tr);$sem[$ck]=round($cc/$wc*100,1);}
    $pm=['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];$il=0;
    if(preg_match_all('#<a[^>]+href="([^"]+)"#i',$raw,$hm))foreach($hm[1] as $h){$h=rtrim(trim($h),'/');if($h==='')$h='/';$tt=$pm[$h]??($pm['/'.preg_replace('#^.*/#','',$h)]??null);if($tt!==null&&$tt!==$t)$il++;}
    return['words'=>(int)$m['words_total'],'h2'=>(int)$m['h2_count'],'h3'=>(int)($m['h3_count']??0),'lists'=>(int)$m['list_count'],
     'tables'=>(int)($m['table_count']??0),'quotes'=>(int)($m['quote_count']??0),'strong'=>(int)$m['strong_count'],'faq'=>(int)$s['faq_questions'],
     'first_person'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],'imperatives'=>(int)$s['imperatives'],'emoji'=>(int)$s['emoji'],
     'adj_pct'=>round((float)$s['adj_pct'],1),'numbers_per100'=>round((float)$s['numbers_per_100w'],1),'entities'=>(int)$s['entities_count'],
     'nausea_acad'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1),'intlinks'=>$il,
     'brand_ru'=>substr_count($raw,'%brand_name_ru%'),'brand_en'=>substr_count($raw,'%brand_name_en%'),'sem'=>$sem];
}
function donorP(array $dp): array { $o=$dp; $o['h3']=max(0,(int)($dp['sections']??0)-(int)($dp['h2']??0)); return $o; }
function offx($our,$don,bool $rate=false): bool { if($don===null)return false; $d=abs($our-$don);$tol=0.25*max(abs($don),1);$f=$rate?0.8:2.0;return $d>max($tol,$f); }
function elig($dv,bool $rate=false): bool { return $dv!==null && abs($dv) >= ($rate?0.8:3); }

// ── бриф правок для страницы (регистро-осознанный) ──────────────────────────
function briefFor(array $o, array $d, string $type, string $reg, array $LABEL): string {
    $w=max(1,$o['words']); $fx=[];
    if(offx($o['words'],$d['words'])){ $diff=$d['words']-$o['words']; $fx[]=($diff>0?"ОБЪЁМ: добавь ~".abs($diff)." слов прозы":"ОБЪЁМ: сократи ~".abs($diff)." слов"); }
    if(offx($o['numbers_per100'],$d['numbers_per100'],true)){ $c=$o['numbers_per100'];$g=$d['numbers_per100'];
        if($c>$g){$rm=(int)ceil(($c-$g)/100*$w); $fx[]="ЦИФРЫ: плотно ({$c}/100 vs {$g}). Убери ~{$rm} чисел ИЗ ПРОЗЫ (перепиши словами), таблицы/фактуру не трогай.";}
        else{$ad=(int)ceil(($g-$c)/100*$w); $fx[]="ЦИФРЫ: мало ({$c}/100 vs {$g}). Добавь ~{$ad} чисел из фактуры.";}}
    if(offx($o['entities'],$d['entities'])&&$o['entities']>$d['entities']){ $fx[]="СУЩНОСТИ: убери ~".($o['entities']-$d['entities'])." названий игр/провайдеров из прозы (оставь ".$d['entities'].").";}
    if(offx($o['faq'],$d['faq'])){ $diff=$o['faq']-$d['faq']; $fx[]=($diff>0?"FAQ: убери ~$diff вопросов (цель ".$d['faq'].")":"FAQ: добавь ~".abs($diff)." вопросов (цель ".$d['faq'].")");}
    if(offx($o['h3'],$d['h3'])){ $diff=$d['h3']-$o['h3']; $fx[]=($diff>0?"H3: добавь ~$diff подзаголовков":"H3: убери ~".abs($diff)." подзаголовков"); }
    if(offx($o['strong'],$d['strong'])&&$d['strong']>$o['strong']){ $fx[]="ВЫДЕЛЕНИЯ: оберни ещё ~".($d['strong']-$o['strong'])." фактов в <strong>"; }
    if(offx($o['nausea_acad'],$d['nausea_acad'],true)&&$o['nausea_acad']>$d['nausea_acad']){ $fx[]="ТОШНОТА: {$o['nausea_acad']}% vs {$d['nausea_acad']}% — снизь повтор частых слов синонимами."; }
    if($reg==='delovoy' && offx($o['vy'],$d['vy']) && $d['vy']>=$o['vy']){ $diff=$d['vy']-$o['vy']; if($diff>=3)$fx[]="РЕГИСТР «вы»: добавь ~$diff явных «вы/вам/ваш»."; }
    if($reg==='expert' && offx($o['first_person'],$d['first_person']) && $d['first_person']>=$o['first_person']){ $diff=$d['first_person']-$o['first_person']; if($diff>=4)$fx[]="РЕГИСТР «я»: усиль первое лицо (+~$diff «я/мне/мой»)."; }
    foreach(($d['sem']??[]) as $ck=>$dv){ if($dv<1.0)continue; $ov=$o['sem'][$ck]??0; if(!offx($ov,$dv,true))continue; $lab=Intent::THEMES[$ck]['label']??$ck; $trg=implode(', ',array_slice(Intent::THEMES[$ck]['triggers']??[],0,6));
        if($ov<$dv){$need=(int)ceil(($dv-$ov)/100*$w); $fx[]="КЛАСТЕР «{$lab}» ниже ({$ov} vs {$dv}/100): добавь ~{$need} вхождений СЛОВАМИ ({$trg}), без цифр.";}
        else{$fx[]="КЛАСТЕР «{$lab}» выше ({$ov} vs {$dv}/100): проредь ключи ({$trg}) синонимами.";}}
    if(!$fx) return '';
    return "# Правки для «{$LABEL[$type]}» (донор-цель)\n" . implode("\n", array_map(fn($i,$f)=>($i+1).". $f", array_keys($fx), $fx));
}
function matchPct(Analyzer $a, string $type, string $raw, array $d): array {
    $o=measureP($a,$type,$raw); $ok=0;$n=0;
    foreach(['words'=>0,'h2'=>0,'h3'=>0,'lists'=>0,'tables'=>0,'quotes'=>0,'strong'=>0,'faq'=>0,'first_person'=>0,'vy'=>0,'imperatives'=>0,'emoji'=>0,'adj_pct'=>1,'numbers_per100'=>1,'entities'=>0,'nausea_acad'=>1,'water'=>1,'intlinks'=>0,'brand_ru'=>0,'brand_en'=>0] as $k=>$rate){
        $dv=$d[$k]??null; if(!elig($dv,(bool)$rate))continue; $n++; if(!offx($o[$k],$dv,(bool)$rate))$ok++; }
    foreach(($d['sem']??[]) as $ck=>$dv){ if($dv<1.0)continue; $n++; if(!offx($o['sem'][$ck]??0,$dv,true))$ok++; }
    return [$o, $n?round($ok/$n*100):0];
}
$LABEL=['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

// ── realize.php обёртка (учёт токенов) ──────────────────────────────────────
function callRealize(string $engine, array $args): int {
    $cmd = "php " . escapeshellarg("$engine/realize.php");
    foreach ($args as $k=>$v) { $cmd .= " --$k=" . escapeshellarg((string)$v); }
    exec($cmd . " 2>&1", $line, $rc);
    $last = end($line) ?: '';
    if (preg_match('~in (\d+) / out (\d+)~', $last, $m)) { $GLOBALS['COST_IN']+=(int)$m[1]; $GLOBALS['COST_OUT']+=(int)$m[2]; }
    return $rc;
}

// 1) планы+промпты (бренд-переменные)
exec("php " . escapeshellarg("$ENGINE/generate.php") . " --all --donor=" . escapeshellarg($donor)
   . " --brand-var --seed=" . escapeshellarg($seed) . " --out-dir=" . escapeshellarg($out) . " --prompt 2>/dev/null");
if (count(glob("$out/prompt-*.md")) < 7) { fwrite(STDERR, "промпты не сгенерились\n"); exit(2); }
fwrite(STDERR, "донор $donor · регистр $reg · порог $thr%\n");

// 2) реалайз p0 (1 вызов на страницу)
foreach ($TYPES as $t) {
    if (!is_file("$out/prompt-$t.md")) continue;
    $rc = callRealize($ENGINE, ['prompt'=>"$out/prompt-$t.md",'out'=>"$out/$t.html",'effort'=>$effort,'register'=>$reg]);
    fwrite(STDERR, "  реалайз $t: " . ($rc===0?'ok':"ошибка($rc)") . "\n");
}

// 3) механическая перелинковка-страховка (без модели)
$brRu = $opts['brand-ru'] ?? '%brand_name_ru%'; $brEn = $opts['brand-en'] ?? '%brand_name_en%';
foreach ($TYPES as $t) { $hf="$out/$t.html"; if(!is_file($hf))continue; $need=(int)($dpAll[$t]['intlinks']??0);
    $have=preg_match_all('~<a\s+href="/~i',(string)file_get_contents($hf));
    if($need>0 && $have<max(1,(int)floor($need*0.75))){ exec("php ".escapeshellarg("$ENGINE/inject-links.php")." ".escapeshellarg($hf)." ".escapeshellarg($hf)." ".escapeshellarg($brRu)." ".escapeshellarg($brEn)." '' ".$need." 2>/dev/null"); }
}

// оценка p0
$sum=0;$cnt=0; foreach($TYPES as $t){ if(!is_file("$out/$t.html")||!isset($dpAll[$t]))continue; [,$p]=matchPct($analyzer,$t,(string)file_get_contents("$out/$t.html"),donorP($dpAll[$t])); $sum+=$p;$cnt++; }
$avg = $cnt?round($sum/$cnt):0; fwrite(STDERR, "p0 совпадение: $avg%\n");

// 4) verify-loop (замер → бриф → адресный фикс) до порога
if ($verify && $avg < $thr) {
    for ($pass=1; $pass<=$passes; $pass++) {
        $fixed=0;
        foreach ($TYPES as $t) {
            $hf="$out/$t.html"; if(!is_file($hf)||!isset($dpAll[$t]))continue;
            $raw=(string)file_get_contents($hf); $d=donorP($dpAll[$t]); $o=measureP($analyzer,$t,$raw);
            $brief=briefFor($o,$d,$t,$reg,$LABEL); if($brief==='')continue;
            $tmp="$out/.fix-$t.md"; file_put_contents($tmp, $brief."\n\n## ТЕКУЩИЙ HTML (правь на месте):\n".$raw);
            $rc=callRealize($ENGINE, ['mode'=>'fix','prompt'=>$tmp,'out'=>$hf,'effort'=>$effort,'register'=>$reg]); @unlink($tmp);
            if($rc===0)$fixed++;
        }
        $sum=0;$cnt=0; foreach($TYPES as $t){ if(!is_file("$out/$t.html")||!isset($dpAll[$t]))continue; [,$p]=matchPct($analyzer,$t,(string)file_get_contents("$out/$t.html"),donorP($dpAll[$t])); $sum+=$p;$cnt++; }
        $avg=$cnt?round($sum/$cnt):0; fwrite(STDERR, "проход $pass: правок $fixed → совпадение $avg%\n");
        if($fixed===0 || $avg>=$thr) break;
    }
}

$price = $COST_IN/1e6*5 + $COST_OUT/1e6*25;
fwrite(STDERR, sprintf("=== готово: совпадение %d%% | токены in %d / out %d | ~\$%.3f (Opus 4.8) ===\n", $avg, $COST_IN, $COST_OUT, $price));

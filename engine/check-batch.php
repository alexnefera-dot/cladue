<?php
declare(strict_types=1);

/**
 * Быстрый ревью ПАЧКИ связок: пробегает все под-папки <batch>/<run>/ и для каждой
 * меряет попадание в её донора, печатает РАНЖИР-таблицу (совпадение % + топ-красные
 * параметры). Донор берётся из <run>/meta.json {donor,corpus} (его пишет realize-run),
 * либо из имени папки. Это «одна команда для проверки всей пачки».
 *
 *   php check-batch.php <batch-dir> [--corpus=dorgen]
 *
 * <batch-dir>/<run>/{main,zerkalo,…,app}.html  (+ опц. meta.json)
 */

require_once __DIR__ . '/src/Analyzer.php';

$args = array_slice($argv, 1);
$BATCH = ''; $CORPUS = '';
foreach ($args as $a) { if (preg_match('/^--corpus=(.*)$/', $a, $m)) $CORPUS = $m[1]; else $BATCH = $a; }
if ($BATCH === '' || !is_dir($BATCH)) { fwrite(STDERR, "usage: check-batch.php <batch-dir> [--corpus=dorgen]\n"); exit(1); }

$donorsFile = ($CORPUS === 'dorgen' && is_file(__DIR__ . '/data-dorgen/donors.json'))
    ? __DIR__ . '/data-dorgen/donors.json' : __DIR__ . '/data/donors.json';
$SITES = json_decode((string) file_get_contents($donorsFile), true)['sites'] ?? [];
$a = new Analyzer();
$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
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
     'faq'=>(int)$s['faq_questions'],'entities'=>(int)$s['entities_count'],'first_person'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],
     'imperatives'=>(int)$s['imperatives'],'numbers_per100'=>round((float)$s['numbers_per_100w'],1),'adj_pct'=>round((float)$s['adj_pct'],1),
     'nausea_acad'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1),'emoji'=>(int)$s['emoji'],
     'brand_ru'=>substr_count($raw,'%brand_name_ru%'),'brand_en'=>substr_count($raw,'%brand_name_en%'),'intlinks'=>$il];
}
function offx($o, $d, bool $r=false): bool { if ($d===null) return false; $x=abs($o-$d); $t=0.25*max(abs($d),1); $f=$r?0.8:2.0; return $x>max($t,$f); }

$FIELDS = ['words'=>0,'h2'=>0,'sections'=>0,'lists'=>0,'tables'=>0,'quotes'=>0,'strong'=>0,'faq'=>0,'intlinks'=>0,'brand_ru'=>0,'brand_en'=>0,
 'emoji'=>0,'entities'=>0,'first_person'=>0,'vy'=>0,'imperatives'=>0,'numbers_per100'=>1,'adj_pct'=>1,'nausea_acad'=>1,'water'=>1];
$LBL = ['numbers_per100'=>'цифры','nausea_acad'=>'тошнота','entities'=>'сущности','first_person'=>'«я»','vy'=>'«вы»','imperatives'=>'императивы',
 'adj_pct'=>'прилаг','water'=>'вода','strong'=>'strong','lists'=>'списки','sections'=>'секции','faq'=>'faq','brand_en'=>'брендEN','words'=>'объём'];

$runs = [];
foreach (glob("$BATCH/*", GLOB_ONLYDIR) as $dir) {
    if (!is_file("$dir/main.html")) continue;
    $meta = is_file("$dir/meta.json") ? json_decode((string) file_get_contents("$dir/meta.json"), true) : [];
    $donor = $meta['donor'] ?? basename($dir);
    if (!isset($SITES[$donor])) { fwrite(STDERR, "  ! пропуск " . basename($dir) . ": донор '$donor' не найден\n"); continue; }
    $D = $SITES[$donor]['pages'];
    $hit = 0; $tot = 0; $red = [];
    foreach ($TYPES as $t) {
        if (!is_file("$dir/$t.html")) continue;
        $o = meas($a, $t, (string) file_get_contents("$dir/$t.html"), $PM);
        foreach ($FIELDS as $k => $rate) {
            $dv = $D[$t][$k] ?? ($k==='sections' ? ($D[$t]['sections']??null) : null); if ($dv === null) continue;
            $isRed = offx($o[$k], $dv, (bool)$rate); $hit += $isRed?0:1; $tot++;
            if ($isRed) { $key = $LBL[$k] ?? $k; $red[$key] = ($red[$key] ?? 0) + 1; }
        }
    }
    arsort($red);
    $runs[] = ['run'=>basename($dir),'donor'=>$donor,'pct'=>$tot?round($hit/$tot*100):0,'hit'=>$hit,'tot'=>$tot,
        'red'=>implode(', ', array_map(fn($k,$v)=>"{$k}×{$v}", array_keys(array_slice($red,0,4,true)), array_slice($red,0,4,true)))];
}
usort($runs, fn($x,$y)=>$y['pct']<=>$x['pct']);

printf("\n%-22s %-10s %-8s %s\n", 'RUN', 'донор', 'совпад', 'топ-красные параметры');
echo str_repeat('─', 78) . "\n";
foreach ($runs as $r) printf("%-22s %-10s %3d%%     %s\n", $r['run'], $r['donor'], $r['pct'], $r['red'] ?: '—');
$avg = $runs ? round(array_sum(array_column($runs,'pct')) / count($runs)) : 0;
echo str_repeat('─', 78) . "\n";
printf("Связок: %d · средний %d%% · лучший %s (%d%%) · худший %s (%d%%)\n",
    count($runs), $avg, $runs[0]['run']??'-', $runs[0]['pct']??0, end($runs)['run']??'-', end($runs)['pct']??0);
echo "STATUS " . json_encode(['runs'=>count($runs),'avg'=>$avg,'best'=>$runs[0]['pct']??0]) . "\n";

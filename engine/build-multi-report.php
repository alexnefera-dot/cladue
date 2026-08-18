<?php
declare(strict_types=1);

/**
 * Сводный отчёт по НЕСКОЛЬКИМ связкам: одна страница со вкладками.
 * На каждой вкладке — матрица параметров (наш / оригинал, цветной вердикт) по
 * всем 7 страницам связки. Плюс вкладка «Сводка» с ранжиром и, если задан
 * второй прогон, вкладка «Уникальность» (пересечение текстов между прогонами).
 *
 *   php build-multi-report.php <batch-dir> <out.html> [--corpus=dorgen] [--vs=<other-batch-dir>] [--title=...]
 *
 * <batch-dir>/<set>/{main,…,app}.html (+ meta.json {donor,corpus}).
 */

require_once __DIR__ . '/src/Analyzer.php';

$BATCH = ''; $OUT = ''; $CORPUS = ''; $VS = ''; $TITLE = '';
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--corpus=(.*)$/', $a, $m)) $CORPUS = $m[1];
    elseif (preg_match('/^--vs=(.*)$/', $a, $m)) $VS = rtrim($m[1], '/');
    elseif (preg_match('/^--title=(.*)$/s', $a, $m)) $TITLE = $m[1];
    elseif ($BATCH === '') $BATCH = rtrim($a, '/');
    elseif ($OUT === '') $OUT = $a;
}
if ($BATCH === '' || $OUT === '') { fwrite(STDERR, "usage: build-multi-report.php <batch-dir> <out.html> [--corpus=dorgen] [--vs=dir]\n"); exit(1); }

$donorsFile = ($CORPUS === 'dorgen' && is_file(__DIR__ . '/data-dorgen/donors.json'))
    ? __DIR__ . '/data-dorgen/donors.json' : __DIR__ . '/data/donors.json';
$SITES = json_decode((string) file_get_contents($donorsFile), true)['sites'] ?? [];
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
// уникальность: 4-словные шинглы
function plainTxt(string $f): string {
    if (!is_file($f)) return '';
    $t = strip_tags(preg_replace('~<script.*?</script>~su', ' ', (string) file_get_contents($f)));
    $t = mb_strtolower($t); $t = preg_replace('/%[a-z_]+%/', '', $t);
    $t = preg_replace('/[^а-яё ]+/u', ' ', $t);
    return trim(preg_replace('/\s+/u', ' ', $t));
}
function shing(string $t, int $n = 4): array { $w = explode(' ', $t); $o = []; for ($i=0; $i+$n <= count($w); $i++) $o[implode(' ', array_slice($w,$i,$n))] = 1; return $o; }
function jac(array $A, array $B): float { if (!$A || !$B) return 0.0; $i = count(array_intersect_key($A,$B)); $u = count($A + $B); return $u ? round($i/$u*100, 1) : 0.0; }

$F = ['words'=>['Объём слов',0],'h2'=>['H2',0],'sections'=>['Секции',0],'lists'=>['Списки',0],'tables'=>['Таблицы',0],'quotes'=>['Цитаты',0],
 'strong'=>['&lt;strong&gt;',0],'faq'=>['FAQ',0],'intlinks'=>['Ссылки',0],'brand_ru'=>['Бренд RU',0],'brand_en'=>['Бренд EN',0],'emoji'=>['Эмодзи',0],
 'entities'=>['Сущности',0],'first_person'=>['«я»',0],'vy'=>['«вы»',0],'imperatives'=>['Императивы',0],'numbers_per100'=>['Цифры/100',1],
 'adj_pct'=>['Прилаг%',1],'nausea_acad'=>['Тошнота',1],'water'=>['Водность%',1]];

$sets = [];
foreach (glob("$BATCH/*", GLOB_ONLYDIR) as $dir) {
    if (!is_file("$dir/main.html")) continue;
    $meta = is_file("$dir/meta.json") ? json_decode((string) file_get_contents("$dir/meta.json"), true) : [];
    $donor = $meta['donor'] ?? basename($dir);
    if (!isset($SITES[$donor])) continue;
    $D = $SITES[$donor]['pages'];
    $rows = []; $ph = []; $pt = []; $hit = 0; $tot = 0;
    foreach ($TYPES as $t) {
        if (!is_file("$dir/$t.html")) { $rows[$t] = null; continue; }
        $rows[$t] = meas($a, $t, (string) file_get_contents("$dir/$t.html"), $PM);
        $ph[$t] = 0; $pt[$t] = 0;
        foreach ($F as $k => [$lab,$rate]) {
            $dv = $D[$t][$k] ?? ($k==='sections' ? ($D[$t]['sections']??null) : null); if ($dv === null) continue;
            $good = !offx($rows[$t][$k], $dv, (bool)$rate); $ph[$t] += $good?1:0; $pt[$t]++; $hit += $good?1:0; $tot++;
        }
    }
    $sets[] = ['name'=>basename($dir),'donor'=>$donor,'genre'=>$SITES[$donor]['style']['genre'] ?? '','rows'=>$rows,'D'=>$D,
        'ph'=>$ph,'pt'=>$pt,'pct'=>$tot?round($hit/$tot*100):0,'hit'=>$hit,'tot'=>$tot];
}
usort($sets, fn($x,$y)=>$y['pct']<=>$x['pct']);

// уникальность против второго прогона
$uniq = [];
if ($VS !== '') {
    foreach ($sets as $s) {
        $row = [];
        foreach ($TYPES as $t) {
            $A = plainTxt("$BATCH/{$s['name']}/$t.html"); $B = plainTxt("$VS/{$s['name']}/$t.html");
            $row[$t] = ($A === '' || $B === '') ? null : jac(shing($A), shing($B));
        }
        $uniq[$s['name']] = $row;
    }
}

$title = $TITLE !== '' ? $TITLE : 'Сводный отчёт по связкам';
$H = "<meta charset='utf-8'><title>" . htmlspecialchars($title) . "</title><style>
:root{--line:#e2e6ef;--ink:#141821;--soft:#657084;--ok:#137a4b;--okbg:#e8f7ec;--bad:#b3261e;--badbg:#fdecea;--panel:#fff;--bg:#f4f6fa;--accent:#2f5fd0;--warnbg:#fff4e5;--warn:#b06000}
@media(prefers-color-scheme:dark){:root{--line:#2a3342;--ink:#e6eaf3;--soft:#94a1b8;--okbg:#12331f;--ok:#5cd68f;--badbg:#3a1c1c;--bad:#ff8a80;--panel:#171d28;--bg:#0f131b;--accent:#6f9cff;--warnbg:#33260f;--warn:#e6bf5a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1400px;margin:0 auto;padding:22px}
h1{font-size:21px;margin:0 0 4px}.sub{color:var(--soft);margin:0 0 16px;font-size:14px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:16px 0 14px;position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:5;border-bottom:1px solid var(--line)}
.tab{padding:6px 12px;border:1px solid var(--line);border-radius:8px;background:var(--panel);cursor:pointer;font-size:13px;color:var(--ink)}
.tab.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.pane{display:none}.pane.on{display:block}
table{border-collapse:collapse;width:100%;background:var(--panel);font-size:12.5px;border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:14px}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:center;white-space:nowrap}
th{background:color-mix(in srgb,var(--accent) 8%,var(--panel));font-weight:600;font-size:11.5px}
td.l,th.l{text-align:left;font-weight:600}
td.ok{background:var(--okbg);color:var(--ok)}td.bad{background:var(--badbg);color:var(--bad)}td.na{color:var(--soft)}
td.warn{background:var(--warnbg);color:var(--warn)}
small{color:var(--soft);font-size:10.5px}
.note{background:var(--panel);border-left:3px solid var(--accent);padding:9px 14px;margin:10px 0;font-size:13.5px;border-radius:0 8px 8px 0}
</style><div class='wrap'><h1>" . htmlspecialchars($title) . "</h1>
<p class='sub'>В ячейке: наш показатель, ниже — значение референса. Зелёный — в коридоре донора, красный — вылет.</p>";

// вкладки
$tabs = "<button class='tab on' onclick='sw(0)'>Сводка</button>";
$i = 1; $panes = '';
foreach ($sets as $s) { $tabs .= "<button class='tab' onclick='sw($i)'>{$s['name']} · {$s['pct']}%</button>"; $i++; }
if ($uniq) { $tabs .= "<button class='tab' onclick='sw($i)'>Уникальность</button>"; }

// пейн 0 — сводка
$p0 = "<table><tr><th class='l'>Связка</th><th>Донор</th><th>Совпадение</th><th class='l'>Жанр</th>";
foreach ($TYPES as $t) $p0 .= "<th>{$LABEL[$t]}</th>";
$p0 .= "</tr>";
foreach ($sets as $s) {
    $cls = $s['pct']>=85?'ok':($s['pct']>=78?'':'bad');
    $p0 .= "<tr><td class='l'>{$s['name']}</td><td>{$s['donor']}</td><td class='$cls'><b>{$s['pct']}%</b></td><td class='l'><small>" . htmlspecialchars(mb_substr($s['genre'],0,46)) . "</small></td>";
    foreach ($TYPES as $t) {
        if (!isset($s['pt'][$t]) || !$s['pt'][$t]) { $p0 .= "<td class='na'>—</td>"; continue; }
        $pp = round($s['ph'][$t]/$s['pt'][$t]*100);
        $p0 .= "<td class='" . ($pp>=85?'ok':($pp>=75?'':'bad')) . "'>{$pp}%</td>";
    }
    $p0 .= "</tr>";
}
$avg = $sets ? round(array_sum(array_column($sets,'pct'))/count($sets)) : 0;
$p0 .= "</table><p class='note'><b>Связок: " . count($sets) . " · средний " . $avg . "%</b>" . ($sets ? " · лучший {$sets[0]['name']} ({$sets[0]['pct']}%) · худший " . end($sets)['name'] . " (" . end($sets)['pct'] . "%)" : '') . "</p>";
$panes .= "<div class='pane on' id='p0'>$p0</div>";

// пейны по связкам
$i = 1;
foreach ($sets as $s) {
    $t2 = "<p class='sub'>Донор <b>{$s['donor']}</b> · " . htmlspecialchars($s['genre']) . " · совпадение <b>{$s['pct']}%</b> ({$s['hit']}/{$s['tot']})</p><table><tr><th class='l'>Параметр</th>";
    foreach ($TYPES as $t) $t2 .= "<th>{$LABEL[$t]}</th>";
    $t2 .= "</tr>";
    foreach ($F as $k => [$lab,$rate]) {
        $t2 .= "<tr><td class='l'>$lab</td>";
        foreach ($TYPES as $t) {
            if (!$s['rows'][$t]) { $t2 .= "<td class='na'>—</td>"; continue; }
            $o = $s['rows'][$t][$k]; $dv = $s['D'][$t][$k] ?? ($k==='sections' ? ($s['D'][$t]['sections']??null) : null);
            if ($dv === null) { $t2 .= "<td class='na'>$o<br><small>—</small></td>"; continue; }
            $t2 .= "<td class='" . (offx($o,$dv,(bool)$rate)?'bad':'ok') . "'>$o<br><small>$dv</small></td>";
        }
        $t2 .= "</tr>";
    }
    $t2 .= "<tr><td class='l'>СОВПАДЕНИЕ</td>";
    foreach ($TYPES as $t) {
        if (!isset($s['pt'][$t]) || !$s['pt'][$t]) { $t2 .= "<td class='na'>—</td>"; continue; }
        $pp = round($s['ph'][$t]/$s['pt'][$t]*100);
        $t2 .= "<td class='" . ($pp>=85?'ok':($pp>=75?'':'bad')) . "'><b>{$pp}%</b></td>";
    }
    $t2 .= "</tr></table>";
    $panes .= "<div class='pane' id='p$i'>$t2</div>";
    $i++;
}

// пейн уникальности
if ($uniq) {
    $u = "<p class='sub'>Пересечение текста между двумя прогонами одного донора (4-словные шинглы). Чем меньше — тем уникальнее. До ~5% — практически полностью разный текст.</p><table><tr><th class='l'>Связка</th>";
    foreach ($TYPES as $t) $u .= "<th>{$LABEL[$t]}</th>";
    $u .= "<th>среднее</th></tr>";
    $allv = [];
    foreach ($uniq as $name => $row) {
        $u .= "<tr><td class='l'>$name</td>"; $vals = [];
        foreach ($TYPES as $t) {
            $v = $row[$t];
            if ($v === null) { $u .= "<td class='na'>—</td>"; continue; }
            $vals[] = $v; $allv[] = $v;
            $cls = $v <= 5 ? 'ok' : ($v <= 15 ? 'warn' : 'bad');
            $u .= "<td class='$cls'>{$v}%</td>";
        }
        $m = $vals ? round(array_sum($vals)/count($vals),1) : 0;
        $u .= "<td class='" . ($m<=5?'ok':($m<=15?'warn':'bad')) . "'><b>{$m}%</b></td></tr>";
    }
    $tot = $allv ? round(array_sum($allv)/count($allv),1) : 0;
    $u .= "</table><p class='note'><b>Среднее пересечение по всем связкам: {$tot}%</b> — насколько второй прогон повторяет первый при том же доноре.</p>";
    $panes .= "<div class='pane' id='p$i'>$u</div>";
}

$H .= "<div class='tabs'>$tabs</div>$panes
<script>function sw(n){document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('on',i===n));document.querySelectorAll('.pane').forEach((p,i)=>p.classList.toggle('on',i===n));window.scrollTo({top:0});}</script></div>";

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");
echo "STATUS " . json_encode(['sets'=>count($sets),'avg'=>$avg]) . "\n";

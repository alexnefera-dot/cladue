<?php
declare(strict_types=1);

/**
 * Сборка HTML-просмотрщика связки: вкладки по 7 страницам с отрендеренным
 * контентом + полоска метрик (значение vs коридор корпуса [p10..p90]).
 *
 *   php build-viewer.php <папка с *.html> <out.html> [Заголовок]
 */

require_once __DIR__ . '/src/Analyzer.php';

$dir   = $argv[1] ?? (__DIR__ . '/../samples/generated/demo1');
$out   = $argv[2] ?? (__DIR__ . '/../reports/demo1-viewer.html');
$title = $argv[3] ?? 'Связка Казиновия — 7 страниц (воспроизведение корпуса)';

$profile = json_decode((string) file_get_contents(__DIR__ . '/data/profile.json'), true)['types'];
$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

$METRICS = [
    ['Слов',           fn($m,$s)=>$m['words_total'],          'words'],
    ['H2',             fn($m,$s)=>$m['h2_count'],             'h2'],
    ['FAQ',            fn($m,$s)=>$s['faq_questions'],        'faq'],
    ['Списков',        fn($m,$s)=>$m['list_count'],           'lists'],
    ['Цифр/100',       fn($m,$s)=>$s['numbers_per_100w'],     'numbers_per100'],
    ['Тошнота ак.%',   fn($m,$s)=>$m['nausea_academic'],      'nausea_acad'],
    ['Водность%',      fn($m,$s)=>$m['water_percent'],        'water'],
    ['Первое лицо',    fn($m,$s)=>$s['first_person'],         'first_person'],
    ['«вы»',           fn($m,$s)=>$s['second_person'],        'vy'],
    ['Пассив%',        fn($m,$s)=>$s['passive_pct'],          'passive_pct'],
    ['Эмодзи',         fn($m,$s)=>$s['emoji'],                'emoji_body'],
    ['Сущностей',      fn($m,$s)=>$s['entities_count'],       'entities'],
];

$analyzer = new Analyzer();
$panels = [];
$tabs   = [];
$totalPass = 0; $totalCnt = 0;

foreach ($TYPES as $i => $t) {
    $path = "$dir/$t.html";
    $html = (string) file_get_contents($path);
    $res = $analyzer->run([[ 'name'=>$t,'url'=>"$t.html",'html'=>$html,'keyword'=>'','lsi'=>[] ]]);
    $p = $res['pages'][0]; $m = $p['metrics']; $s = $p['stylistics']; $P = $profile[$t];

    $chips = ''; $pass = 0; $cnt = 0;
    foreach ($METRICS as [$lbl,$get,$key]) {
        if (!isset($P[$key])) continue;
        $val = (float) $get($m,$s);
        [$lo,,$hi] = $P[$key]; $lo2=min($lo,$hi); $hi2=max($lo,$hi);
        $in = $val>=$lo2 && $val<=$hi2;
        $near = !$in && $val>=$lo2*0.8 && $val<=$hi2*1.2;
        $cls = $in ? 'ok' : ($near ? 'warn' : 'bad');
        $cnt++; if ($in) $pass++;
        $vShow = rtrim(rtrim(number_format($val,2,'.',''),'0'),'.');
        $chips .= "<div class='chip $cls'><span class='cl'>$lbl</span><span class='cv'>$vShow</span>"
                . "<span class='cc'>[{$P[$key][0]}–{$P[$key][2]}]</span></div>";
    }
    $totalPass += $pass; $totalCnt += $cnt;
    $pct = (int) round($pass/max(1,$cnt)*100);

    $tabs[] = "<button class='tab".($i===0?" active":"")."' data-p='$t'>".$LABEL[$t]
            . "<span class='tp'>{$pass}/{$cnt}</span></button>";

    $panels[] = "<div class='panel".($i===0?" active":"")."' id='p-$t'>"
        . "<div class='mstrip'><div class='mhead'>".$LABEL[$t]." · <b>$pct%</b> метрик в коридоре корпуса "
        . "<span class='leg'><i class='ok'></i>в коридоре <i class='warn'></i>рядом (±20%) <i class='bad'></i>мимо</span></div>"
        . "<div class='chips'>$chips</div></div>"
        . "<article class='doc'>$html</article></div>";
}

$overallPct = (int) round($totalPass/max(1,$totalCnt)*100);
$tabsHtml   = implode("\n", $tabs);
$panelsHtml = implode("\n", $panels);

$css = <<<CSS
:root{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;
 --ok:#1f9d6b;--warn:#d98a2a;--bad:#d23b40;--accent:#3f7bf0;
 --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;}
@media(prefers-color-scheme:dark){:root{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--ok:#33c08a;--warn:#eaa54a;--bad:#e5595c;--accent:#5b95ff;}}
:root[data-theme="dark"]{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--ok:#33c08a;--warn:#eaa54a;--bad:#e5595c;--accent:#5b95ff;}
:root[data-theme="light"]{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--ok:#1f9d6b;--warn:#d98a2a;--bad:#d23b40;--accent:#3f7bf0;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--sans)}
.wrap{max-width:900px;margin:0 auto;padding:24px 18px 80px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:23px;margin:6px 0 6px;letter-spacing:-.02em}
.sum{color:var(--muted);font-size:14px;margin-bottom:6px}
.sum b{color:var(--ok)}
.tabs{display:flex;flex-wrap:wrap;gap:6px;position:sticky;top:0;background:var(--bg);padding:12px 0 10px;z-index:5;border-bottom:1px solid var(--line)}
.tab{font:inherit;font-size:13px;font-weight:600;color:var(--muted);background:var(--panel);border:1px solid var(--line);
  border-radius:9px;padding:7px 12px;cursor:pointer;display:inline-flex;align-items:center;gap:7px}
.tab:hover{color:var(--ink)}
.tab.active{color:#fff;background:var(--accent);border-color:var(--accent)}
.tp{font-family:var(--mono);font-size:11px;opacity:.85;background:rgba(0,0,0,.12);padding:0 5px;border-radius:10px}
.tab.active .tp{background:rgba(255,255,255,.2)}
.panel{display:none}.panel.active{display:block}
.mstrip{margin:16px 0 10px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.mhead{font-size:13px;color:var(--muted);margin-bottom:9px}.mhead b{color:var(--ink);font-size:15px}
.leg{float:right;font-size:11px}.leg i{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 3px 0 8px;vertical-align:middle}
.leg i.ok{background:var(--ok)}.leg i.warn{background:var(--warn)}.leg i.bad{background:var(--bad)}
.chips{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:7px}
.chip{border:1px solid var(--line);border-radius:9px;padding:6px 9px;background:var(--panel2);display:flex;flex-direction:column;gap:1px;border-left:3px solid var(--muted)}
.chip.ok{border-left-color:var(--ok)}.chip.warn{border-left-color:var(--warn)}.chip.bad{border-left-color:var(--bad)}
.chip .cl{font-size:10.5px;color:var(--muted)}
.chip .cv{font-family:var(--mono);font-size:16px;font-weight:700}
.chip .cc{font-family:var(--mono);font-size:10px;color:var(--muted)}
.doc{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:26px 30px;overflow-wrap:break-word}
@media(max-width:620px){.doc{padding:18px 16px}}
.doc p{margin:0 0 12px}
.doc h2{font-size:20px;margin:26px 0 8px;padding-top:8px;border-top:1px solid var(--line)}
.doc h3{font-size:16px;margin:18px 0 6px}
.doc ul{margin:0 0 14px;padding-left:22px}.doc li{margin:3px 0}
.doc table{border-collapse:collapse;width:100%;margin:6px 0 16px;font-size:14px;display:block;overflow-x:auto}
.doc th,.doc td{border:1px solid var(--line);padding:7px 10px;text-align:left}
.doc th{background:var(--panel2);color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.02em}
.doc blockquote{margin:0 0 14px;padding:10px 14px;border-left:3px solid var(--accent);background:var(--panel2);border-radius:0 9px 9px 0;font-style:italic;color:var(--muted)}
.doc strong{color:var(--ink)}
.doc em{color:var(--muted);font-size:13px}
.foot{color:var(--muted);font-size:12px;margin-top:26px;text-align:center}
CSS;

$js = <<<'JS'
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{
  const id=b.dataset.p;
  document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id==='p-'+id));
  window.scrollTo({top:0,behavior:'smooth'});
}));
JS;

$page = "<meta charset='utf-8'>\n<title>".htmlspecialchars($title)."</title>\n<style>$css</style>\n"
    . "<div class='wrap'>\n"
    . "<div class='eyebrow'>Реверс-генератор · тест-генерация · движок v2</div>\n"
    . "<h1>".htmlspecialchars($title)."</h1>\n"
    . "<div class='sum'>Единый стиль-профиль на всех страницах · попадание в коридоры корпуса: <b>$overallPct%</b> ($totalPass/$totalCnt метрик). Переключай вкладки — контент + метрики каждой страницы.</div>\n"
    . "<div class='tabs'>\n$tabsHtml\n</div>\n"
    . "$panelsHtml\n"
    . "<div class='foot'>Казиновия / Casinovia · samples/generated/demo1 · зелёный = в коридоре [p10..p90], янтарный = рядом (±20%), красный = мимо.</div>\n"
    . "</div>\n<script>$js</script>\n";

file_put_contents($out, $page);
fwrite(STDERR, "→ $out ($overallPct%, $totalPass/$totalCnt)\n");

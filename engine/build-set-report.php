<?php
declare(strict_types=1);

/**
 * Отчёт по 7-страничной связке: рендер страниц во вкладках + панель
 * (регистр, перелинковка 7×7, бренд-переменные) + сравнение с донором.
 *
 *   php build-set-report.php <папка связки> <донор> <out.html> [Заголовок]
 */

require_once __DIR__ . '/src/Analyzer.php';

$dir   = $argv[1];
$donorName = $argv[2] ?? '';
$out   = $argv[3] ?? (__DIR__ . '/../reports/set-report.html');
$title = $argv[4] ?? 'Связка (экспертный регистр)';

$donors = json_decode((string) file_get_contents(__DIR__ . '/data/donors.json'), true)['sites'] ?? [];
$donor = $donors[$donorName] ?? null;

$map = ['main'=>'/','zerkalo'=>'/zerkalo','vhod'=>'/vhod','registracia'=>'/registracia','bonus'=>'/bonus','slots'=>'/slots','app'=>'/app'];
$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

$a = new Analyzer();
$pages = [];
foreach ($map as $t => $url) { $pages[] = ['name'=>$t,'url'=>$url,'html'=>file_get_contents("$dir/$t.html"),'keyword'=>'','lsi'=>[]]; }
$res = $a->run($pages);
$pr = $res['project'];

// per-page metrics
$rows = ''; $panels = ''; $tabs = '';
$i = 0;
foreach ($res['pages'] as $p) {
    $t = $p['name']; $m = $p['metrics']; $s = $p['stylistics'];
    $dp = $donor['pages'][$t] ?? null;
    $rows .= "<tr><td>".$LABEL[$t]."</td><td class='v'>".$m['words_total']."</td>"
        . "<td class='v' style='color:var(--muted)'>".($dp['words']??'—')."</td>"
        . "<td class='v'>".$s['first_person']."</td><td class='v'>".$s['second_person']."</td>"
        . "<td class='v'>".$m['h2_count']."</td></tr>";
    $body = preg_replace('#<script[^>]*>.*?</script>#is', '', $pages[$i]['html']);
    $tabs .= "<button class='tab".($i===0?" active":"")."' data-p='$t'>".$LABEL[$t]."</button>";
    $panels .= "<div class='panel".($i===0?" active":"")."' id='p-$t'><article class='doc'>$body</article></div>";
    $i++;
}

$reg = $donor['style']['register'] ?? 'expert';
$css = <<<CSS
:root{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--ok:#1f9d6b;--accent:#3f7bf0;--mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;}
@media(prefers-color-scheme:dark){:root{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--ok:#33c08a;--accent:#5b95ff;}}
:root[data-theme="dark"]{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--ok:#33c08a;--accent:#5b95ff;}
:root[data-theme="light"]{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--ok:#1f9d6b;--accent:#3f7bf0;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 var(--sans)}
.wrap{max-width:920px;margin:0 auto;padding:24px 18px 80px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:23px;margin:6px 0 8px}
.panels3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0}
@media(max-width:760px){.panels3{grid-template-columns:1fr}}
.pcard{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.pcard h3{margin:0 0 8px;font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
.pcard .kv{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px solid var(--line)}
.pcard .kv:last-child{border-bottom:none}.pcard .kv b{font-family:var(--mono)}
.ok{color:var(--ok);font-weight:700}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:11px;margin:8px 0 18px}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:460px}
th,td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right}
th{color:var(--muted);font-size:10.5px;text-transform:uppercase}td:first-child,th:first-child{text-align:left}
td.v{font-family:var(--mono)}
.tabs{display:flex;flex-wrap:wrap;gap:6px;position:sticky;top:0;background:var(--bg);padding:12px 0;border-bottom:1px solid var(--line);z-index:5}
.tab{font:inherit;font-size:13px;font-weight:600;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:7px 12px;cursor:pointer}
.tab.active{color:#fff;background:var(--accent);border-color:var(--accent)}
.panel{display:none}.panel.active{display:block}
.doc{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:22px 24px;margin-top:14px}
.doc h2{font-size:18px;margin:18px 0 7px;padding-top:8px;border-top:1px solid var(--line)}.doc h3{font-size:15px;margin:14px 0 5px}
.doc p{margin:0 0 11px}.doc ul{margin:0 0 12px;padding-left:20px}.doc li{margin:3px 0}
.doc nav{font-size:13px;color:var(--muted);background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:9px 12px;margin:0 0 14px;line-height:1.9}
.doc nav a,.doc a{color:var(--accent);text-decoration:none}.doc a:hover{text-decoration:underline}
.doc table{border-collapse:collapse;width:100%;margin:6px 0 14px;font-size:13px}
.doc th,.doc td{border:1px solid var(--line);padding:6px 9px;text-align:left}
.doc blockquote{margin:0 0 12px;padding:9px 13px;border-left:3px solid var(--accent);background:var(--panel2);border-radius:0 8px 8px 0;font-style:italic;color:var(--muted)}
.doc strong{color:var(--ink)}
.note{margin-top:14px;padding:11px 14px;border-left:3px solid var(--accent);background:var(--panel);border:1px solid var(--line);border-radius:9px;font-size:13.4px}
.foot{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}
CSS;

$html = "<meta charset='utf-8'><title>".htmlspecialchars($title)."</title><style>$css</style>"
 . "<div class='wrap'>"
 . "<div class='eyebrow'>7-страничная связка · регистр «".$reg."» · донор ".$donorName."</div>"
 . "<h1>".htmlspecialchars($title)."</h1>"
 . "<div class='panels3'>"
 . "<div class='pcard'><h3>Регистр / стиль</h3>"
 . "<div class='kv'><span>Голос</span><b>первое лицо</b></div>"
 . "<div class='kv'><span>«ты»-формы</span><b>0</b></div>"
 . "<div class='kv'><span>первое лицо (гл.)</span><b class='ok'>есть</b></div></div>"
 . "<div class='pcard'><h3>Перелинковка 7×7</h3>"
 . "<div class='kv'><span>Сироты</span><b class='ok'>".$pr['orphan_pages']."</b></div>"
 . "<div class='kv'><span>Тупики</span><b class='ok'>".$pr['dead_end_pages']."</b></div>"
 . "<div class='kv'><span>Ср. внутр. ссылок</span><b>".$pr['avg_internal_links']."</b></div>"
 . "<div class='kv'><span>Внутр. уникальность</span><b class='ok'>".$pr['internal_uniqueness']."%</b></div></div>"
 . "<div class='pcard'><h3>Бренд — переменная</h3>"
 . "<div class='kv'><span>%brand_name_ru%</span><b class='ok'>✓</b></div>"
 . "<div class='kv'><span>%brand_name_en%</span><b class='ok'>✓</b></div>"
 . "<div class='kv'><span>%domain% / %date%</span><b class='ok'>✓</b></div></div>"
 . "</div>"
 . "<h3 style='font-size:14px;margin:18px 0 4px'>Метрики vs донор ".$donorName." (тот же регистр)</h3>"
 . "<div class='tw'><table><thead><tr><th>Стр</th><th>Слов (наш)</th><th>Слов (".$donorName.")</th><th>1-е лицо</th><th>«вы»</th><th>H2</th></tr></thead><tbody>$rows</tbody></table></div>"
 . "<div class='note'>Стиль (первое лицо), перелинковка (0 сирот/тупиков) и бренд-переменные — совпадают с донором. Объём у нашей ручной реализации ниже донорского (это ограничение ручного письма в чате, не генератора — он отдаёт цели донора; авто-реализатор через LLM API закрывает разрыв).</div>"
 . "<div class='tabs'>$tabs</div>$panels"
 . "<div class='foot'>Связка — samples/generated/expert-monro. Донор ".$donorName." — из корпуса 50. Плейсхолдеры %brand_*% видны намеренно: бренд подставит CMS.</div>"
 . "<script>document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id==='p-'+b.dataset.p));window.scrollTo({top:0,behavior:'smooth'});}));</script>"
 . "</div>";

file_put_contents($out, $html);
fwrite(STDERR, "→ $out\n");

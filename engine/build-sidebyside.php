<?php
declare(strict_types=1);

/**
 * Сборка HTML «бок о бок»: слева сгенерированная страница-клон, справа реальная
 * страница сайта-донора того же типа, сверху — сравнение метрик (реал vs наш).
 *
 *   php build-sidebyside.php <наш.html> <реал.html> <тип> <донор> <out.html>
 */

require_once __DIR__ . '/src/Analyzer.php';

[$genF, $realF, $type, $donor, $out] = [$argv[1], $argv[2], $argv[3] ?? 'vhod', $argv[4] ?? 'донор', $argv[5] ?? (__DIR__.'/../reports/sidebyside.html')];
$profile = json_decode((string)file_get_contents(__DIR__.'/data/profile.json'), true)['types'][$type];

$a = new Analyzer();
function metrics(Analyzer $a, string $f, string $type): array {
    $r = $a->run([['name'=>$type,'url'=>"$type.html",'html'=>file_get_contents($f),'keyword'=>'','lsi'=>[]]]);
    $m = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];
    return ['Слов'=>$m['words_total'],'H2'=>$m['h2_count'],'Списков'=>$m['list_count'],'Таблиц'=>$m['table_count'],
        'Цитат'=>$m['quote_count'],'strong'=>$m['strong_count'],'FAQ'=>$s['faq_questions'],
        'Цифр/100'=>round((float)$s['numbers_per_100w'],1),'Прилаг%'=>round((float)$s['adj_pct'],1),
        'Тошнота%'=>round((float)$m['nausea_academic'],1),'Водность%'=>round((float)$m['water_percent'],1),
        '«вы»'=>$s['second_person'],'Первое лицо'=>$s['first_person'],'Эмодзи'=>$s['emoji'],'Сущностей'=>$s['entities_count']];
}
$mkey = ['Слов'=>'words','H2'=>'h2','Списков'=>'lists','Цифр/100'=>'numbers_per100','Тошнота%'=>'nausea_acad','Водность%'=>'water','FAQ'=>'faq','Прилаг%'=>'adj_pct'];

$gen = metrics($a, $genF, $type);
$real = metrics($a, $realF, $type);

// чистим реальную страницу: убираем script/style, достаём body, подставляем бренд
function cleanBody(string $html, string $brandRu, string $brandEn): string {
    $html = preg_replace('#<(script|style|noscript)[^>]*>.*?</\1>#is', '', $html);
    if (preg_match('#<body[^>]*>(.*)</body>#is', $html, $b)) $html = $b[1];
    // выкидываем изображения/ссылки-обёртки, оставляем разметку статьи
    $html = preg_replace('#<img[^>]*>#i', '', $html);
    $html = preg_replace('#</?(a|nav|header|footer|aside|button|svg|path)[^>]*>#i', '', $html);
    $repl = ['%brand_name_ru%'=>$brandRu,'%brand_name_en%'=>$brandEn,'%domain_name%'=>strtolower($brandEn).'.win','%mirror%'=>'зеркало'];
    $html = str_ireplace(array_keys($repl), array_values($repl), $html);
    return trim($html);
}
$realBody = cleanBody(file_get_contents($realF), 'Вован', 'Vovan');
$genBody  = preg_replace('#<script[^>]*>.*?</script>#is', '', file_get_contents($genF));

// строки сравнения
$rows = '';
foreach ($gen as $k=>$gv) {
    $rv = $real[$k];
    $band = isset($mkey[$k], $profile[$mkey[$k]]) ? $profile[$mkey[$k]] : null;
    $inCorr = $band ? ($gv>=min($band[0],$band[2]) && $gv<=max($band[0],$band[2])) : null;
    $near = is_numeric($rv)&&is_numeric($gv)&&$rv!=0 ? abs($gv-$rv)/max(1,abs($rv))<=0.25 : ($gv==$rv);
    $mark = $near ? '≈' : '≠';
    $cls = $near ? 'ok' : 'warn';
    $bandTxt = $band ? "[{$band[0]}–{$band[2]}]" : '';
    $rows .= "<tr><td class='m'>$k</td><td class='v real'>$rv</td><td class='v gen'>$gv</td>"
           . "<td class='mk $cls'>$mark</td><td class='band'>$bandTxt</td></tr>";
}

$nearCount = 0; $tot = 0;
foreach ($gen as $k=>$gv){ $rv=$real[$k]; $tot++; if((is_numeric($rv)&&is_numeric($gv)&&$rv!=0&&abs($gv-$rv)/max(1,abs($rv))<=0.25)||($gv==$rv))$nearCount++; }

$css = <<<CSS
:root{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--gen:#1f9d6b;--real:#3f7bf0;--warn:#d98a2a;--mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;}
@media(prefers-color-scheme:dark){:root{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--gen:#33c08a;--real:#5b95ff;--warn:#eaa54a;}}
:root[data-theme="dark"]{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--gen:#33c08a;--real:#5b95ff;--warn:#eaa54a;}
:root[data-theme="light"]{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--gen:#1f9d6b;--real:#3f7bf0;--warn:#d98a2a;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans)}
.wrap{max-width:1160px;margin:0 auto;padding:24px 18px 70px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:23px;margin:6px 0 8px}.lead{color:var(--muted);max-width:80ch;font-size:14px}
.summary{margin:14px 0;padding:12px 15px;border-radius:11px;background:var(--panel2);border:1px solid var(--line);font-size:14px}
.mtable{overflow-x:auto;border:1px solid var(--line);border-radius:11px;margin:14px 0 22px}
table.cmp{border-collapse:collapse;width:100%;font-size:13px;min-width:420px}
table.cmp th,table.cmp td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right}
table.cmp th{color:var(--muted);font-size:10.5px;text-transform:uppercase;letter-spacing:.03em}
table.cmp td.m,table.cmp th:first-child{text-align:left;font-weight:600}
table.cmp td.v{font-family:var(--mono)}td.v.real{color:var(--real)}td.v.gen{color:var(--gen)}
td.mk{font-weight:700}td.mk.ok{color:var(--gen)}td.mk.warn{color:var(--warn)}td.band{font-family:var(--mono);font-size:11px;color:var(--muted)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
.col h2{font-size:14px;margin:0 0 8px;display:flex;align-items:center;gap:8px}
.tag{font-size:11px;font-weight:700;color:#fff;padding:2px 9px;border-radius:20px}
.tag.gen{background:var(--gen)}.tag.real{background:var(--real)}
.doc{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:20px 22px;height:70vh;overflow:auto}
.doc :is(h1,h2){font-size:18px;margin:18px 0 7px;padding-top:7px;border-top:1px solid var(--line)}
.doc h3{font-size:15px;margin:14px 0 5px}
.doc p{margin:0 0 11px}.doc ul{margin:0 0 12px;padding-left:20px}.doc li{margin:3px 0}
.doc table{border-collapse:collapse;width:100%;margin:6px 0 14px;font-size:13px;display:block;overflow-x:auto}
.doc th,.doc td{border:1px solid var(--line);padding:6px 9px;text-align:left}
.doc blockquote{margin:0 0 12px;padding:9px 13px;border-left:3px solid var(--muted);background:var(--panel2);border-radius:0 8px 8px 0;font-style:italic;color:var(--muted)}
.doc strong{color:var(--ink)}.foot{color:var(--muted);font-size:12px;margin-top:22px;text-align:center}
CSS;

$html = "<meta charset='utf-8'><title>Генерация vs реальный сайт ($donor/$type)</title><style>$css</style>"
 . "<div class='wrap'>"
 . "<div class='eyebrow'>Донор-режим · клон одного сайта · тип «{$type}»</div>"
 . "<h1>Наша генерация против реального сайта <b>$donor</b></h1>"
 . "<p class='lead'>Слева — страница, собранная генератором в режиме клонирования донора <b>$donor</b>. Справа — реальная страница того же сайта того же типа. Форма (объём, H2, списки, таблицы, цитаты, тон, «вы») совпадает; контент — полностью свой, из пулов.</p>"
 . "<div class='summary'>📊 Совпадение формы с реальным сайтом: <b>$nearCount/$tot</b> метрик в пределах ±25%. Контент при этом другой — это клон <b>по форме</b>, а не копия текста.</div>"
 . "<div class='mtable'><table class='cmp'><thead><tr><th>Метрика</th><th style='color:var(--real)'>Реальный $donor</th><th style='color:var(--gen)'>Наш клон</th><th>≈</th><th>Коридор корпуса</th></tr></thead><tbody>$rows</tbody></table></div>"
 . "<div class='cols'>"
 . "<div class='col'><h2><span class='tag gen'>НАШ КЛОН</span> сгенерировано (форма донора, свой контент)</h2><div class='doc'>$genBody</div></div>"
 . "<div class='col'><h2><span class='tag real'>РЕАЛЬНЫЙ</span> $donor · из корпуса</h2><div class='doc'>$realBody</div></div>"
 . "</div>"
 . "<div class='foot'>Наш клон — engine/generate.php --donor=$donor. Реальный — сайт $donor из корпуса 50 (бренд заменён на «Вован»). Метрики — движок v2.</div>"
 . "</div>";

file_put_contents($out, $html);
fwrite(STDERR, "→ $out (совпадение формы $nearCount/$tot)\n");

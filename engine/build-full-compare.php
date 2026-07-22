<?php
declare(strict_types=1);

/**
 * Полное параметрическое сравнение двух связок постранично: структура,
 * стилистика, антиспам, SEO/техника, бренд (ру/англ), семантические кластеры.
 *
 *   php build-full-compare.php <наша папка> <папка донора> <out.html> [Заголовок]
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/Intent.php';

$ourDir  = $argv[1];
$donDir  = $argv[2];
$out     = $argv[3] ?? (__DIR__ . '/../reports/full-compare.html');
$title   = $argv[4] ?? 'Полное сравнение связки с донором';

$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];
$map = ['main'=>'/','zerkalo'=>'/zerkalo','vhod'=>'/vhod','registracia'=>'/registracia','bonus'=>'/bonus','slots'=>'/slots','app'=>'/app'];

// семантические кластеры (триггеры из Intent) — «раскрытие семантики»
$CLUSTERS = [
    'official'=>'Офиц. сайт','access'=>'Зеркало/доступ','registr'=>'Регистрация','money'=>'Платежи/вывод',
    'bonus'=>'Бонусы','games'=>'Слоты/игры','app'=>'Приложение','betting'=>'Ставки/спорт','support'=>'Поддержка/отзывы',
];

function clusterDensity(string $text, int $words): array {
    $t = mb_strtolower($text);
    $out = [];
    foreach (Intent::THEMES as $key => $def) {
        $c = 0;
        foreach ($def['triggers'] as $tr) { $c += mb_substr_count($t, $tr); }
        $out[$key] = $words > 0 ? round($c / $words * 100, 1) : 0.0;
    }
    return $out;
}

function pageStats(Analyzer $a, string $file, string $type, string $url): array {
    $raw = file_get_contents($file);
    $r = $a->run([['name'=>$type,'url'=>$url,'html'=>$raw,'keyword'=>'','lsi'=>[]]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    // бренд ру/англ — по плейсхолдерам (или, если подставлен, по base-именам)
    $brRu = substr_count($raw, '%brand_name_ru%');
    $brEn = substr_count($raw, '%brand_name_en%');
    // внутренние ссылки
    $pathmap = ['/'=>1,'/zerkalo'=>1,'/vhod'=>1,'/registracia'=>1,'/bonus'=>1,'/slots'=>1,'/app'=>1];
    $il = 0;
    if (preg_match_all('#href="([^"]+)"#i', $raw, $hm)) {
        foreach ($hm[1] as $h) { $h = rtrim($h,'/')?:'/'; if (isset($pathmap[$h])) $il++; }
    }
    $text = strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$raw));
    $words = $m['words_total'];
    return [
        'struct' => [
            'Слов'=>$words, 'H2'=>$m['h2_count'], 'H3'=>$m['h3_count'],
            'Списков'=>$m['list_count'], 'Таблиц'=>$m['table_count'], 'Цитат'=>$m['quote_count'],
            'strong'=>$m['strong_count'], 'FAQ'=>$s['faq_questions'],
        ],
        'style' => [
            '1-е лицо'=>$s['first_person'], '«вы»'=>$s['second_person'], 'Императивы'=>$s['imperatives'],
            'Эмодзи'=>$s['emoji'], 'Прилаг.%'=>$s['adj_pct'], 'Пассив%'=>$s['passive_pct'],
            'Цифр/100'=>$s['numbers_per_100w'], 'Сущностей'=>$s['entities_count'],
        ],
        'anti' => [
            'Тошнота ак.%'=>$m['nausea_academic'], 'Классич.тошн'=>$m['nausea_classic'],
            'Водность%'=>$m['water_percent'], 'Уник.слов%'=>round($m['words_unique_ratio']<=1?$m['words_unique_ratio']*100:$m['words_unique_ratio'],1),
            'Плотн.ключа%'=>$m['keyword_density_max'], 'Флеш'=>$m['flesch_reading_ease'],
        ],
        'seo' => [
            'Schema'=>!empty($m['schema_present'])?1:0, 'Дата-стамп'=>!empty($s['date_freshness'])?1:0,
            'Внутр.ссылок'=>$il, 'Title'=>!empty($m['title_present'])?1:0,
        ],
        'brand' => [
            'Бренд ру'=>$brRu, 'Бренд en'=>$brEn, 'Всего'=>$brRu+$brEn,
            'en:ру'=>$brRu>0?round($brEn/$brRu,1):$brEn, 'на 100 сл'=>$words>0?round(($brRu+$brEn)/$words*100,1):0,
        ],
        'sem' => clusterDensity($text, $words),
    ];
}

$a = new Analyzer();
$data = [];
foreach ($TYPES as $t) {
    $of = "$ourDir/$t.html"; $df = "$donDir/$t.html";
    if (!is_file($of) || !is_file($df)) continue;
    $data[$t] = ['our'=>pageStats($a,$of,$t,$map[$t]), 'don'=>pageStats($a,$df,$t,$map[$t])];
}

// рендер
$GROUPS = [
    'struct'=>'Структура', 'style'=>'Стилистика / тон', 'anti'=>'Антиспам / качество',
    'seo'=>'SEO / техника', 'brand'=>'Бренд (ру/англ)',
];
function near($our,$don): string {
    if (!is_numeric($our)||!is_numeric($don)) return $our==$don?'ok':'warn';
    if ($don==0) return abs($our)<=1?'ok':'warn';
    $d = abs($our-$don)/max(0.001,abs($don));
    return $d<=0.25?'ok':($d<=0.6?'warn':'bad');
}

$tabs=''; $panels=''; $i=0;
foreach ($data as $t=>$d) {
    $tabs .= "<button class='tab".($i===0?' active':'')."' data-p='$t'>".$LABEL[$t]."</button>";
    $body = "<div class='panel".($i===0?' active':'')."' id='p-$t'>";
    foreach ($GROUPS as $gk=>$gl) {
        $body .= "<h3 class='grp'>$gl</h3><div class='tw'><table><thead><tr><th>Параметр</th><th>Наш</th><th>monro</th><th>≈</th></tr></thead><tbody>";
        foreach ($d['our'][$gk] as $k=>$ov) {
            $dv = $d['don'][$gk][$k] ?? '—';
            $cls = near($ov,$dv);
            $mark = $cls==='ok'?'≈':($cls==='warn'?'~':'≠');
            $body .= "<tr><td class='m'>$k</td><td class='v'>$ov</td><td class='v' style='color:var(--muted)'>$dv</td><td class='mk $cls'>$mark</td></tr>";
        }
        $body .= "</tbody></table></div>";
    }
    // семантика — отдельным блоком с барами
    $body .= "<h3 class='grp'>Семантика — раскрытие кластеров (вхождений на 100 слов)</h3><div class='tw'><table><thead><tr><th>Кластер</th><th>Наш</th><th>monro</th><th>покрытие</th></tr></thead><tbody>";
    $maxSem = 0.1;
    foreach ($CLUSTERS as $ck=>$cl) { $maxSem = max($maxSem, $d['our']['sem'][$ck]??0, $d['don']['sem'][$ck]??0); }
    foreach ($CLUSTERS as $ck=>$cl) {
        $ov=$d['our']['sem'][$ck]??0; $dv=$d['don']['sem'][$ck]??0;
        $ow=round($ov/$maxSem*100); $dw=round($dv/$maxSem*100);
        $body .= "<tr><td class='m'>$cl</td><td class='v'>$ov</td><td class='v' style='color:var(--muted)'>$dv</td>"
              . "<td class='bar'><span class='b our' style='width:{$ow}%'></span><span class='b don' style='width:{$dw}%'></span></td></tr>";
    }
    $body .= "</tbody></table></div>";
    $body .= "</div>";
    $panels .= $body; $i++;
}

$css = <<<CSS
:root{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--ok:#1f9d6b;--warn:#d98a2a;--bad:#d23b40;--accent:#3f7bf0;--don:#9163e0;--mono:ui-monospace,Menlo,Consolas,monospace;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;}
@media(prefers-color-scheme:dark){:root{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--ok:#33c08a;--warn:#eaa54a;--bad:#e5595c;--accent:#5b95ff;--don:#a98bf0;}}
:root[data-theme="dark"]{--bg:#0e131c;--panel:#151d29;--panel2:#1b2431;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--ok:#33c08a;--warn:#eaa54a;--bad:#e5595c;--accent:#5b95ff;--don:#a98bf0;}
:root[data-theme="light"]{--bg:#f6f8fc;--panel:#fff;--panel2:#eef2f8;--ink:#1a2230;--muted:#5d6b82;--line:#e2e7ef;--ok:#1f9d6b;--warn:#d98a2a;--bad:#d23b40;--accent:#3f7bf0;--don:#9163e0;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans)}
.wrap{max-width:940px;margin:0 auto;padding:24px 18px 80px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:23px;margin:6px 0 6px}.lead{color:var(--muted);font-size:14px;max-width:80ch}
.legend{font-size:12px;color:var(--muted);margin:8px 0}
.legend b{color:var(--ink)}.sw{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:middle;margin:0 3px 0 8px}
.sw.our{background:var(--accent)}.sw.don{background:var(--don)}
.tabs{display:flex;flex-wrap:wrap;gap:6px;position:sticky;top:0;background:var(--bg);padding:12px 0;border-bottom:1px solid var(--line);z-index:5}
.tab{font:inherit;font-size:13px;font-weight:600;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:7px 12px;cursor:pointer}
.tab.active{color:#fff;background:var(--accent);border-color:var(--accent)}
.panel{display:none}.panel.active{display:block}
.grp{font-size:13px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted);margin:18px 0 6px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:11px;margin-bottom:8px}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:420px}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:right}
th{color:var(--muted);font-size:10.5px;text-transform:uppercase}td.m,th:first-child{text-align:left}
tbody tr:last-child td{border-bottom:none}td.v{font-family:var(--mono)}
td.mk{font-weight:700}td.mk.ok{color:var(--ok)}td.mk.warn{color:var(--warn)}td.mk.bad{color:var(--bad)}
td.bar{min-width:130px}td.bar .b{display:inline-block;height:8px;border-radius:2px;vertical-align:middle}
td.bar .b.our{background:var(--accent)}td.bar .b.don{background:var(--don);margin-left:2px;opacity:.7}
.foot{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}
CSS;

$html = "<meta charset='utf-8'><title>".htmlspecialchars($title)."</title><style>$css</style>"
 . "<div class='wrap'>"
 . "<div class='eyebrow'>Полное параметрическое сравнение · 7 страниц</div>"
 . "<h1>".htmlspecialchars($title)."</h1>"
 . "<p class='lead'>По каждой странице: структура, стилистика, антиспам, SEO, бренд (ру/англ) и семантические кластеры — наш клон против реального monro. ≈ — расхождение ≤25%, ~ ≤60%, ≠ больше.</p>"
 . "<div class='legend'><b>Семантика:</b><span class='sw our'></span>наш <span class='sw don'></span>monro — длина бара = плотность кластера на 100 слов.</div>"
 . "<div class='tabs'>$tabs</div>$panels"
 . "<div class='foot'>Наш — samples/generated/expert-monro. monro — из корпуса 50. Кластеры — Intent::THEMES. Бренд — по плейсхолдерам %brand_name_*%.</div>"
 . "<script>document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id==='p-'+b.dataset.p));window.scrollTo({top:0,behavior:'smooth'});}));</script>"
 . "</div>";

file_put_contents($out, $html);
fwrite(STDERR, "→ $out (страниц: ".count($data).")\n");

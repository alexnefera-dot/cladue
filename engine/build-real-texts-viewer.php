<?php
declare(strict_types=1);

/**
 * Витрина РЕАЛЬНЫХ сгенерированных текстов в двухуровневых вкладках, с
 * ПОЛНЫМ набором измеренных параметров над каждой страницей:
 *   объём/структура, стиль/регистр, анти-спам, SEO, бренд ру/англ, семантика.
 * Все цифры считаются Analyzer'ом по самому тексту — ничего синтетического.
 *
 *   php build-real-texts-viewer.php <out.html>
 */

require_once __DIR__ . '/src/Analyzer.php';

$out = $argv[1] ?? (__DIR__ . '/../reports/real-texts.html');
$SP  = getenv('SCRATCH') ?: '/tmp/claude-0/-home-user-cladue/580c9237-8e67-549d-b11b-3f159fa71245/scratchpad';

$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

// Три реальных набора в разных регистрах. brand_tokens — как ру/англ бренд
// встречается в исходнике (у exp это плейсхолдеры, у остальных — литералы).
$SETS = [
  [
    'id'=>'exp','tab'=>'Экспертный «я»','donor'=>'донор Monro','register'=>'Экспертный (первое лицо)',
    'desc'=>'Личный опыт, «я захожу / я проверял». Спокойный тон практика.',
    'dir'=>'exp','pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
    'sub'=>['%brand_name_ru%'=>'Монрополь','%brand_name_en%'=>'Monropol','%domain_name%'=>'monropol.com','%date%'=>'июль 2026'],
    'brand_ru_tok'=>'%brand_name_ru%','brand_en_tok'=>'%brand_name_en%',
  ],
  [
    'id'=>'delo','tab'=>'Деловой «вы»','donor'=>'шаблон Casinovia','register'=>'Деловой (обращение на «вы»)',
    'desc'=>'Нейтрально-деловой обзор на «вы», без сленга. Структурный разбор площадки.',
    'dir'=>'out','pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
    'sub'=>[],'brand_ru_tok'=>'Казиновия','brand_en_tok'=>'Casinovia',
  ],
  [
    'id'=>'derz','tab'=>'Дерзкий «ты»','donor'=>'донор Cosmospin','register'=>'Дерзкий (на «ты», сленг+эмодзи)',
    'desc'=>'Разговорный, на «ты», со сленгом и эмодзи — «погнали по фактам».',
    'dir'=>'cmp','pages'=>['main'],'files'=>['main'=>'gen_main_derz.html'],
    'sub'=>[],'brand_ru_tok'=>'Космоспин','brand_en_tok'=>'Cosmospin',
  ],
];

$analyzer = new Analyzer();

/** Полный набор параметров одной страницы — считаем по исходному HTML. */
function measure(Analyzer $a, string $type, string $rawHtml, array $set): array {
    $r = $a->run([[ 'name'=>$type,'url'=>"/$type",'html'=>$rawHtml,'keyword'=>'','lsi'=>[] ]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    $wc = max(1,(int)$m['words_total']);

    $txt = mb_strtolower(strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$rawHtml)));
    // семантические кластеры — плотность на 100 слов
    $sem = [];
    foreach (Intent::THEMES as $ck=>$def){ $cc=0; foreach($def['triggers'] as $tr){$cc+=mb_substr_count($txt,$tr);} $sem[$ck]=['label'=>$def['label'],'v'=>round($cc/$wc*100,1)]; }
    uasort($sem, fn($x,$y)=>$y['v']<=>$x['v']);
    // внутренние ссылки на другие страницы связки
    $pathmap=['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];
    $intlinks=0;
    if(preg_match_all('#<a[^>]+href="([^"]+)"#i',$rawHtml,$hm)){foreach($hm[1] as $href){$h=rtrim(trim($href),'/');if($h==='')$h='/';$tt=$pathmap[$h]??($pathmap['/'.preg_replace('#^.*/#','',$h)]??null);if($tt!==null&&$tt!==$type)$intlinks++;}}
    // бренд ру/англ (по токену набора)
    $brRu = substr_count($rawHtml, $set['brand_ru_tok']);
    $brEn = substr_count($rawHtml, $set['brand_en_tok']);
    $hasLd = (bool)preg_match('~application/ld\+json~',$rawHtml);

    return [
        'words'=>(int)$m['words_total'],
        'h2'=>(int)$m['h2_count'],'h3'=>(int)($m['h3_count']??0),
        'lists'=>(int)$m['list_count'],'tables'=>(int)($m['table_count']??0),
        'quotes'=>(int)($m['quote_count']??0),'strong'=>(int)$m['strong_count'],
        'faq'=>(int)$s['faq_questions'],
        'fp'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],
        'imper'=>(int)$s['imperatives'],'emoji'=>(int)$s['emoji'],
        'adj'=>round((float)$s['adj_pct'],1),'num100'=>round((float)$s['numbers_per_100w'],1),
        'entities'=>(int)$s['entities_count'],
        'nausea'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1),
        'intlinks'=>$intlinks,'brand_ru'=>$brRu,'brand_en'=>$brEn,'ld'=>$hasLd,
        'sem'=>$sem,
    ];
}

// строка-чип параметра
function chip(string $label,$val,string $hint=''):string{
    $h=$hint?" title='".htmlspecialchars($hint)."'":'';
    return "<div class='chip'$h><span class='cv'>".$val."</span><span class='cl'>".$label."</span></div>";
}
function group(string $title,string $chips):string{
    return "<div class='pg'><div class='pgt'>$title</div><div class='chips'>$chips</div></div>";
}

$topTabs=''; $panes='';
foreach ($SETS as $si=>$set) {
    $dir = rtrim($SP,'/').'/'.$set['dir'];
    $ta = $si===0?' active':'';
    $topTabs .= "<button class='stab{$ta}' data-set='{$set['id']}'>".$set['tab']."<span class='sd'>{$set['donor']}</span></button>";

    $pageTabs=''; $pagePanes=''; $tw=0;$n=0;
    foreach ($set['pages'] as $pi=>$type) {
        $file = $dir.'/'.($set['files'][$type] ?? ($type.'.html'));
        if (!is_file($file)) continue;
        $raw = (string)file_get_contents($file);
        $mx = measure($analyzer, $type, $raw, $set);
        $tw+=$mx['words'];$n++;

        // тело для чтения: без JSON-LD, с подставленным демо-брендом
        $body = preg_replace('~<script[^>]*application/ld\+json[^>]*>.*?</script>~su','',$raw);
        if($set['sub']) $body = strtr((string)$body,$set['sub']);
        $body = trim((string)$body);

        // панель параметров
        $g1 = group('Объём и структура',
            chip('слов',$mx['words']).chip('H2',$mx['h2']).chip('H3',$mx['h3'])
            .chip('списков',$mx['lists']).chip('таблиц',$mx['tables']).chip('цитат',$mx['quotes'])
            .chip('выделений',$mx['strong'],'теги <strong>').chip('FAQ',$mx['faq'],'вопросов в подзаголовках'));
        $g2 = group('Стиль и регистр',
            "<div class='chip wide'><span class='cv sm'>".$set['register']."</span><span class='cl'>регистр</span></div>"
            .chip('1-е лицо',$mx['fp'],'маркеры «я/мне/мой»').chip('«вы»',$mx['vy'])
            .chip('императивы',$mx['imper']).chip('эмодзи',$mx['emoji'])
            .chip('прилаг. %',$mx['adj']).chip('сущностей',$mx['entities'],'бренды/платежки/провайдеры'));
        $g3 = group('Анти-спам (в норме корпуса)',
            chip('тошнота',$mx['nausea'],'академическая тошнота').chip('вода %',$mx['water'])
            .chip('цифр/100сл',$mx['num100'],'плотность фактажа'));
        $g4 = group('SEO и оптимизация',
            chip('внутр. ссылок',$mx['intlinks'],'на другие страницы связки')
            .chip('бренд ру',$mx['brand_ru']).chip('бренд англ',$mx['brand_en'])
            .chip('Schema.org',$mx['ld']?'есть':'—'));

        // семантика — топ-5 кластеров как полоски
        $semRows=''; $max=1.0; foreach($mx['sem'] as $c){$max=max($max,$c['v']);}
        $shown=0; foreach($mx['sem'] as $c){ if($c['v']<=0||$shown>=6) continue; $shown++;
            $w=round($c['v']/$max*100); $semRows.="<div class='sbar'><span class='sn'>{$c['label']}</span><span class='st'><i style='width:{$w}%'></i></span><span class='sv'>{$c['v']}</span></div>"; }
        $g5 = "<div class='pg'><div class='pgt'>Семантика · плотность кластеров на 100 слов</div><div class='sem'>$semRows</div></div>";

        $pa = $pi===0?' active':'';
        $pageTabs .= "<button class='ptab{$pa}' data-page='{$set['id']}:{$type}'>".$LABEL[$type]."</button>";
        $pagePanes .= "<article class='page{$pa}' data-page='{$set['id']}:{$type}'>"
                    . "<h3 class='atitle'>".$LABEL[$type]."</h3>"
                    . "<div class='params'>$g1$g2$g3$g4$g5</div>"
                    . "<div class='readhead'>Текст страницы</div>"
                    . "<div class='body'>$body</div></article>";
    }
    $avg = $n? " · всего ~".number_format($tw,0,'',' ')." слов на {$n} стр." : '';
    $sa = $si===0?' active':'';
    $panes .= "<section class='set{$sa}' data-set='{$set['id']}'>"
            . "<p class='setdesc'>{$set['desc']}{$avg}</p>"
            . "<div class='ptabs'>$pageTabs</div>$pagePanes</section>";
}

$css = <<<CSS
:root{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--accent2:#7a5cf0;--bar:#3f6fe0;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--accent2:#a08bff;--bar:#5b8bff}}
:root[data-theme="dark"]{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--accent2:#a08bff;--bar:#5b8bff}
:root[data-theme="light"]{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--accent2:#7a5cf0;--bar:#3f6fe0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.62 var(--sans)}
.wrap{max-width:860px;margin:0 auto;padding:24px 18px 90px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:23px;margin:6px 0 8px}.lead{color:var(--muted);font-size:14px;max-width:80ch;margin:0 0 18px}
.stabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 4px}
.stab{cursor:pointer;border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:10px 14px;border-radius:11px;font:600 14px var(--sans);display:flex;flex-direction:column;gap:2px;text-align:left;line-height:1.2}
.stab .sd{font-weight:500;font-size:11px;color:var(--muted)}
.stab.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);color:var(--accent)}.stab.active .sd{color:var(--accent)}
.set{display:none}.set.active{display:block}
.setdesc{color:var(--muted);font-size:13px;margin:12px 0 12px;padding:9px 12px;background:var(--soft);border-radius:9px}
.ptabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px;border-bottom:1px solid var(--line);padding-bottom:10px}
.ptab{cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--muted);padding:6px 12px;border-radius:20px;font:600 12.5px var(--sans)}
.ptab.active{background:var(--accent);border-color:var(--accent);color:#fff}
.page{display:none}.page.active{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.atitle{font-size:19px;margin:4px 0 12px}
.params{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 22px}
@media(max-width:640px){.params{grid-template-columns:1fr}}
.pg{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:11px 12px}
.pg:last-child{grid-column:1/-1}
.pgt{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin:0 0 9px}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{background:var(--soft);border-radius:8px;padding:6px 9px;min-width:58px;display:flex;flex-direction:column;gap:1px}
.chip.wide{flex:1 1 100%}
.chip .cv{font:700 16px var(--mono);color:var(--ink)}.chip .cv.sm{font-size:13px;font-family:var(--sans)}
.chip .cl{font-size:10.5px;color:var(--muted)}
.sem{display:flex;flex-direction:column;gap:6px}
.sbar{display:grid;grid-template-columns:150px 1fr 34px;align-items:center;gap:8px;font-size:12px}
@media(max-width:640px){.sbar{grid-template-columns:110px 1fr 30px}}
.sbar .sn{color:var(--muted)}.sbar .st{height:8px;background:var(--soft);border-radius:5px;overflow:hidden}
.sbar .st i{display:block;height:100%;background:var(--bar);border-radius:5px}
.sbar .sv{font:700 12px var(--mono);text-align:right}
.readhead{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin:0 0 10px;padding-top:6px;border-top:1px dashed var(--line)}
.body{font-size:16px}
.body p{margin:0 0 14px}
.body h2{font-size:20px;margin:26px 0 8px}
.body h3{font-size:17px;margin:22px 0 6px}
.body ul{margin:0 0 16px;padding-left:22px}.body li{margin:4px 0}
.body a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 35%,transparent)}
.body blockquote{margin:16px 0;padding:10px 16px;border-left:3px solid var(--accent2);background:var(--soft);border-radius:0 9px 9px 0;color:var(--ink);font-style:italic}
.body table{border-collapse:collapse;width:100%;font-size:14px;margin:14px 0;display:block;overflow-x:auto}
.body th,.body td{padding:8px 12px;border:1px solid var(--line);text-align:left}
.body th{background:var(--soft);color:var(--muted);font-size:12px;text-transform:uppercase}
.body strong{color:var(--ink)}
.foot{color:var(--muted);font-size:12px;margin-top:30px;text-align:center}
CSS;

$js = <<<JS
document.querySelectorAll('.stab').forEach(b=>b.onclick=()=>{
  const id=b.dataset.set;
  document.querySelectorAll('.stab').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.set').forEach(s=>s.classList.toggle('active',s.dataset.set===id));
});
document.querySelectorAll('.ptab').forEach(b=>b.onclick=()=>{
  const key=b.dataset.page, set=key.split(':')[0];
  document.querySelectorAll('.set[data-set="'+set+'"] .ptab').forEach(x=>x.classList.toggle('active',x===b));
  document.querySelectorAll('.set[data-set="'+set+'"] .page').forEach(p=>p.classList.toggle('active',p.dataset.page===key));
});
JS;

$html = "<!--real generated texts + parameters--><meta charset='utf-8'>"
 . "<meta name='viewport' content='width=device-width,initial-scale=1'>"
 . "<title>Реальные тексты + все параметры · вкладки</title><style>$css</style>"
 . "<div class='wrap'>"
 . "<div class='eyebrow'>Готовый контент + измеренные параметры · три регистра</div>"
 . "<h1>Реальные тексты со всеми параметрами</h1>"
 . "<p class='lead'>Над каждой страницей — полный набор параметров, посчитанный Analyzer'ом по самому тексту: объём и структура, стиль и регистр, анти-спам, SEO, бренд ру/англ и плотность семантических кластеров. Ниже — сам текст. Верхние вкладки — стиль/донор, нижние — страницы связки.</p>"
 . "<div class='stabs'>$topTabs</div>"
 . $panes
 . "<div class='foot'>Все цифры — измерения по готовому тексту (Analyzer): structure/stylistics/anti-spam/SEO + кластеры Intent. Бренд/домен/дата — переменные, подставлены демо-значения.</div>"
 . "</div><script>$js</script>";

file_put_contents($out, $html);
fwrite(STDERR, "→ $out (".round(strlen($html)/1024)." KB)\n");

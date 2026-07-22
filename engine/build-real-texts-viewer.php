<?php
declare(strict_types=1);

/**
 * Витрина РЕАЛЬНЫХ сгенерированных текстов в двухуровневых вкладках, с
 * ПОЛНЫМ набором измеренных параметров над каждой страницей И сравнением
 * с ОРИГИНАЛОМ (пер-сайтовый профиль донора из data/donors.json):
 *   объём/структура, стиль/регистр, анти-спам, SEO, бренд ру/англ, семантика.
 * Все цифры считаются Analyzer'ом по самому тексту — ничего синтетического.
 *
 *   php build-real-texts-viewer.php <out.html>
 */

require_once __DIR__ . '/src/Analyzer.php';

$out = $argv[1] ?? (__DIR__ . '/../reports/real-texts.html');
$SP  = getenv('SCRATCH') ?: '/tmp/claude-0/-home-user-cladue/580c9237-8e67-549d-b11b-3f159fa71245/scratchpad';

$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

$DONORS = json_decode((string)file_get_contents(__DIR__.'/data/donors.json'), true)['sites'];

// Каждый набор сравниваем с ОРИГИНАЛОМ — его донором из корпуса.
// exp→monro и derz→cosmospin писались прямо под этих доноров; delo (демо-шаблон)
// сопоставляем с ближайшим по профилю корпус-донором делового регистра.
$SETS = [
  [
    'id'=>'exp','tab'=>'Экспертный «я»','donor_key'=>'monro','donor_label'=>'Monro',
    'register'=>'Экспертный (первое лицо)','origin'=>'писался под этого донора',
    'desc'=>'Личный опыт, «я захожу / я проверял». Спокойный тон практика.',
    'dir'=>'exp','pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
    'sub'=>['%brand_name_ru%'=>'Монрополь','%brand_name_en%'=>'Monropol','%domain_name%'=>'monropol.com','%date%'=>'июль 2026'],
    'brand_ru_tok'=>'%brand_name_ru%','brand_en_tok'=>'%brand_name_en%',
  ],
  [
    'id'=>'delo','tab'=>'Деловой «вы»','donor_key'=>'bitz','donor_label'=>'Bitz (деловой)',
    'register'=>'Деловой (обращение на «вы»)','origin'=>'ближайший донор по профилю (делового регистра)',
    'desc'=>'Нейтрально-деловой обзор на «вы», без сленга. Структурный разбор площадки.',
    'dir'=>'out/linked','pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
    'sub'=>['%brand_name_ru%'=>'Казиновия','%brand_name_en%'=>'Casinovia','%domain_name%'=>'casinovia.com','%date%'=>'июль 2026'],
    'brand_ru_tok'=>'%brand_name_ru%','brand_en_tok'=>'%brand_name_en%',
  ],
  [
    'id'=>'derz','tab'=>'Дерзкий «ты»','donor_key'=>'cosmospin','donor_label'=>'Cosmospin',
    'register'=>'Дерзкий (на «ты», сленг+эмодзи)','origin'=>'писался под этого донора',
    'desc'=>'Разговорный, на «ты», со сленгом и эмодзи — «погнали по фактам».',
    'dir'=>'cmp','pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
    'files'=>['main'=>'gen_main.html','zerkalo'=>'gen_zerkalo.html','vhod'=>'gen_vhod.html','registracia'=>'gen_registracia.html','bonus'=>'gen_bonus.html','slots'=>'gen_slots.html','app'=>'gen_app.html'],
    'sub'=>['%brand_name_ru%'=>'Космоспин','%brand_name_en%'=>'Cosmospin','%domain_name%'=>'cosmospin.win','%date%'=>'июль 2026'],
    'brand_ru_tok'=>'%brand_name_ru%','brand_en_tok'=>'%brand_name_en%',
  ],
];

$analyzer = new Analyzer();

/** Наши измерения одной страницы — по исходному HTML. */
function measure(Analyzer $a, string $type, string $rawHtml, array $set): array {
    $r = $a->run([[ 'name'=>$type,'url'=>"/$type",'html'=>$rawHtml,'keyword'=>'','lsi'=>[] ]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    $wc = max(1,(int)$m['words_total']);
    $txt = mb_strtolower(strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$rawHtml)));
    $sem = [];
    foreach (Intent::THEMES as $ck=>$def){ $cc=0; foreach($def['triggers'] as $tr){$cc+=mb_substr_count($txt,$tr);} $sem[$ck]=round($cc/$wc*100,1); }
    $pathmap=['/'=>'main','/zerkalo'=>'zerkalo','/vhod'=>'vhod','/registracia'=>'registracia','/bonus'=>'bonus','/slots'=>'slots','/app'=>'app'];
    $intlinks=0;
    if(preg_match_all('#<a[^>]+href="([^"]+)"#i',$rawHtml,$hm)){foreach($hm[1] as $href){$h=rtrim(trim($href),'/');if($h==='')$h='/';$tt=$pathmap[$h]??($pathmap['/'.preg_replace('#^.*/#','',$h)]??null);if($tt!==null&&$tt!==$type)$intlinks++;}}
    return [
        'words'=>(int)$m['words_total'],'h2'=>(int)$m['h2_count'],'h3'=>(int)($m['h3_count']??0),
        'lists'=>(int)$m['list_count'],'tables'=>(int)($m['table_count']??0),
        'quotes'=>(int)($m['quote_count']??0),'strong'=>(int)$m['strong_count'],'faq'=>(int)$s['faq_questions'],
        'first_person'=>(int)$s['first_person'],'vy'=>(int)$s['second_person'],
        'imperatives'=>(int)$s['imperatives'],'emoji'=>(int)$s['emoji'],
        'adj_pct'=>round((float)$s['adj_pct'],1),'numbers_per100'=>round((float)$s['numbers_per_100w'],1),
        'entities'=>(int)$s['entities_count'],
        'nausea_acad'=>round((float)$m['nausea_academic'],1),'water'=>round((float)$m['water_percent'],1),
        'intlinks'=>$intlinks,'brand_ru'=>substr_count($rawHtml,$set['brand_ru_tok']),'brand_en'=>substr_count($rawHtml,$set['brand_en_tok']),
        'ld'=>(bool)preg_match('~application/ld\+json~',$rawHtml),'sem'=>$sem,
    ];
}

/** Донор-профиль страницы в те же ключи (h3 донора выводим из sections−h2). */
function donorPage(array $dp): array {
    $out = $dp;
    $out['h3'] = max(0,(int)($dp['sections']??0) - (int)($dp['h2']??0));
    return $out;
}

/** Вердикт совпадения нашего значения с оригиналом. */
function verdict($our,$don,bool $rate=false): string {
    if ($don===null) return 'na';
    if (is_bool($our)||is_bool($don)) return ($our==$don)?'ok':'bad';
    $d = abs($our-$don); $tol = 0.25*max(abs($don),1); $floor = $rate?0.8:2.0;
    if ($d <= max($tol,$floor)) return 'ok';
    if ($d <= max($tol*2,$floor*2)) return 'warn';
    return 'bad';
}

/** Чип «наш / оригинал» с точкой-вердиктом. */
function chip(string $label,$our,$don,bool $rate=false,string $hint=''):string{
    $v = verdict($our,$don,$rate);
    $dv = $don===null ? '—' : (is_bool($don)?($don?'есть':'—'):$don);
    $ov = is_bool($our)?($our?'есть':'—'):$our;
    $h = $hint?" title='".htmlspecialchars($hint)."'":'';
    return "<div class='chip v-$v'$h><span class='cv'>$ov</span>"
         . "<span class='cd'>ориг $dv</span><span class='cl'>$label</span></div>";
}
function group(string $title,string $chips):string{
    return "<div class='pg'><div class='pgt'>$title</div><div class='chips'>$chips</div></div>";
}

$topTabs=''; $panes='';
foreach ($SETS as $si=>$set) {
    $dir = rtrim($SP,'/').'/'.$set['dir'];
    $dprof = $DONORS[$set['donor_key']]['pages'] ?? [];
    $ta = $si===0?' active':'';
    $topTabs .= "<button class='stab{$ta}' data-set='{$set['id']}'>".$set['tab']
             . "<span class='sd'>ориг: {$set['donor_label']}</span></button>";

    $pageTabs=''; $pagePanes=''; $tw=0;$n=0;
    foreach ($set['pages'] as $pi=>$type) {
        $file = $dir.'/'.($set['files'][$type] ?? ($type.'.html'));
        if (!is_file($file)) continue;
        $raw = (string)file_get_contents($file);
        $mx  = measure($analyzer, $type, $raw, $set);
        $dp  = isset($dprof[$type]) ? donorPage($dprof[$type]) : null;
        $tw+=$mx['words'];$n++;
        $D = fn($k)=> $dp[$k] ?? null;

        // счётчик совпадений по странице
        $okN=0;$totN=0;
        $acc=function($our,$don,$rate=false) use (&$okN,&$totN){ if($don===null) return; $totN++; if(verdict($our,$don,$rate)==='ok')$okN++; };

        // тело для чтения
        $body = preg_replace('~<script[^>]*application/ld\+json[^>]*>.*?</script>~su','',$raw);
        if($set['sub']) $body = strtr((string)$body,$set['sub']);
        $body = trim((string)$body);

        $g1 = group('Объём и структура',
            chip('слов',$mx['words'],$D('words')).chip('H2',$mx['h2'],$D('h2')).chip('H3',$mx['h3'],$D('h3'))
            .chip('списков',$mx['lists'],$D('lists')).chip('таблиц',$mx['tables'],$D('tables'))
            .chip('цитат',$mx['quotes'],$D('quotes')).chip('выделений',$mx['strong'],$D('strong'),false,'теги <strong>')
            .chip('FAQ',$mx['faq'],$D('faq'),false,'вопросов в подзаголовках'));
        foreach(['words','h2','h3','lists','tables','quotes','strong','faq'] as $k)$acc($mx[$k],$D($k));

        $g2 = group('Стиль и регистр',
            "<div class='chip wide v-ok'><span class='cv sm'>".$set['register']."</span>"
            . "<span class='cd'>оригинал: ".$set['donor_label']." · ".$set['origin']."</span><span class='cl'>регистр</span></div>"
            .chip('1-е лицо',$mx['first_person'],$D('first_person'),false,'маркеры «я/мне/мой»').chip('«вы»',$mx['vy'],$D('vy'))
            .chip('императивы',$mx['imperatives'],$D('imperatives')).chip('эмодзи',$mx['emoji'],$D('emoji'))
            .chip('прилаг. %',$mx['adj_pct'],$D('adj_pct'),true).chip('сущностей',$mx['entities'],$D('entities'),false,'бренды/платежки/провайдеры'));
        foreach(['first_person','vy','imperatives','emoji','entities'] as $k)$acc($mx[$k],$D($k));
        $acc($mx['adj_pct'],$D('adj_pct'),true);

        $g3 = group('Анти-спам (норма корпуса)',
            chip('тошнота',$mx['nausea_acad'],$D('nausea_acad'),true,'академическая тошнота')
            .chip('вода %',$mx['water'],$D('water'),true).chip('цифр/100сл',$mx['numbers_per100'],$D('numbers_per100'),true,'плотность фактажа'));
        foreach([['nausea_acad'],['water'],['numbers_per100']] as $k)$acc($mx[$k[0]],$D($k[0]),true);

        $g4 = group('SEO и оптимизация',
            chip('внутр. ссылок',$mx['intlinks'],$D('intlinks'),false,'на другие страницы связки')
            .chip('бренд ру',$mx['brand_ru'],$D('brand_ru')).chip('бренд англ',$mx['brand_en'],$D('brand_en'))
            .chip('Schema.org',$mx['ld'],true));
        foreach(['intlinks','brand_ru','brand_en'] as $k)$acc($mx[$k],$D($k));

        // семантика — наш vs оригинал, по кластерам донора (сорт по донору)
        $dsem = $dp['sem'] ?? [];
        $order = $dsem; arsort($order);
        $semRows=''; $max=0.1; foreach($mx['sem'] as $vv)$max=max($max,$vv); foreach($dsem as $vv)$max=max($max,$vv);
        $shown=0;
        foreach(array_keys($order) as $ck){ if($shown>=6) continue; $ov=$mx['sem'][$ck]??0; $dv=$dsem[$ck]??0; if($ov<=0&&$dv<=0)continue; $shown++;
            $lab=Intent::THEMES[$ck]['label']??$ck; $vd=verdict($ov,$dv,true);
            $wo=round($ov/$max*100);$wd=round($dv/$max*100);
            $semRows.="<div class='sbar'><span class='sn'>$lab</span>"
                    . "<span class='st'><i class='bo' style='width:{$wo}%'></i><i class='bd' style='width:{$wd}%'></i></span>"
                    . "<span class='sv v-$vd'>$ov<b>/$dv</b></span></div>";
            $acc($ov,$dv,true);
        }
        $g5 = "<div class='pg'><div class='pgt'>Семантика · наш / оригинал (плотность на 100 слов)</div><div class='sem'>$semRows"
            . "<div class='slegend'><span><i class='bo'></i> наш</span><span><i class='bd'></i> оригинал</span></div></div></div>";

        $pct = $totN? round($okN/$totN*100):0;
        $mv = $pct>=70?'ok':($pct>=45?'warn':'bad');
        $head = "<div class='matchbar v-$mv'><span class='mb-n'>$okN/$totN</span>"
              . "<span class='mb-l'>параметров совпало с оригиналом <b>{$set['donor_label']}</b> · {$pct}%</span></div>";

        $pa = $pi===0?' active':'';
        $pageTabs .= "<button class='ptab{$pa}' data-page='{$set['id']}:{$type}'>".$LABEL[$type]."</button>";
        $pagePanes .= "<article class='page{$pa}' data-page='{$set['id']}:{$type}'>"
                    . "<h3 class='atitle'>".$LABEL[$type]."</h3>$head"
                    . "<div class='params'>$g1$g2$g3$g4$g5</div>"
                    . "<div class='readhead'>Текст страницы</div><div class='body'>$body</div></article>";
    }
    $avg = $n? " · всего ~".number_format($tw,0,'',' ')." слов на {$n} стр." : '';
    $sa = $si===0?' active':'';
    $panes .= "<section class='set{$sa}' data-set='{$set['id']}'>"
            . "<p class='setdesc'>{$set['desc']} <b>Оригинал:</b> {$set['donor_label']} ({$set['origin']}).{$avg}</p>"
            . "<div class='ptabs'>$pageTabs</div>$pagePanes</section>";
}

$css = <<<CSS
:root{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--accent2:#7a5cf0;--ok:#1f9d6b;--warn:#c98a12;--bad:#d0552e;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--accent2:#a08bff;--ok:#33c08a;--warn:#e0a938;--bad:#e87a52}}
:root[data-theme="dark"]{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--accent2:#a08bff;--ok:#33c08a;--warn:#e0a938;--bad:#e87a52}
:root[data-theme="light"]{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--accent2:#7a5cf0;--ok:#1f9d6b;--warn:#c98a12;--bad:#d0552e}
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
.setdesc b{color:var(--ink)}
.ptabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px;border-bottom:1px solid var(--line);padding-bottom:10px}
.ptab{cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--muted);padding:6px 12px;border-radius:20px;font:600 12.5px var(--sans)}
.ptab.active{background:var(--accent);border-color:var(--accent);color:#fff}
.page{display:none}.page.active{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.atitle{font-size:19px;margin:4px 0 10px}
.matchbar{display:flex;align-items:baseline;gap:10px;padding:9px 13px;border-radius:10px;margin:0 0 16px;border:1px solid var(--line)}
.matchbar .mb-n{font:700 20px var(--mono)}.matchbar .mb-l{font-size:13px;color:var(--muted)}.matchbar .mb-l b{color:var(--ink)}
.matchbar.v-ok{background:color-mix(in srgb,var(--ok) 12%,transparent);border-color:var(--ok)}.matchbar.v-ok .mb-n{color:var(--ok)}
.matchbar.v-warn{background:color-mix(in srgb,var(--warn) 12%,transparent);border-color:var(--warn)}.matchbar.v-warn .mb-n{color:var(--warn)}
.matchbar.v-bad{background:color-mix(in srgb,var(--bad) 12%,transparent);border-color:var(--bad)}.matchbar.v-bad .mb-n{color:var(--bad)}
.params{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 22px}
@media(max-width:640px){.params{grid-template-columns:1fr}}
.pg{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:11px 12px}
.pg:last-child{grid-column:1/-1}
.pgt{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin:0 0 9px}
.chips{display:flex;flex-wrap:wrap;gap:7px}
.chip{background:var(--soft);border-radius:8px;padding:6px 9px;min-width:66px;display:flex;flex-direction:column;gap:1px;border-left:3px solid var(--line)}
.chip.wide{flex:1 1 100%}
.chip .cv{font:700 16px var(--mono);color:var(--ink)}.chip .cv.sm{font-size:13px;font-family:var(--sans)}
.chip .cd{font:600 10.5px var(--mono);color:var(--muted)}
.chip .cl{font-size:10.5px;color:var(--muted)}
.chip.v-ok{border-left-color:var(--ok)}.chip.v-warn{border-left-color:var(--warn)}.chip.v-bad{border-left-color:var(--bad)}.chip.v-na{border-left-color:var(--line)}
.sem{display:flex;flex-direction:column;gap:7px}
.sbar{display:grid;grid-template-columns:150px 1fr 64px;align-items:center;gap:8px;font-size:12px}
@media(max-width:640px){.sbar{grid-template-columns:104px 1fr 58px}}
.sbar .sn{color:var(--muted)}
.sbar .st{position:relative;height:14px;background:var(--soft);border-radius:5px;overflow:hidden}
.sbar .st i{position:absolute;left:0;height:7px;border-radius:5px}
.sbar .st .bo{top:0;background:var(--accent)}
.sbar .st .bd{bottom:0;background:var(--accent2);opacity:.85}
.sbar .sv{font:600 11px var(--mono);text-align:right}.sbar .sv b{color:var(--muted);font-weight:600}
.sbar .sv.v-ok{color:var(--ok)}.sbar .sv.v-warn{color:var(--warn)}.sbar .sv.v-bad{color:var(--bad)}
.slegend{display:flex;gap:16px;margin-top:4px;font-size:11px;color:var(--muted)}
.slegend i{display:inline-block;width:14px;height:7px;border-radius:3px;vertical-align:middle;margin-right:4px}
.slegend .bo{background:var(--accent)}.slegend .bd{background:var(--accent2)}
.readhead{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:700;margin:0 0 10px;padding-top:6px;border-top:1px dashed var(--line)}
.body{font-size:16px}
.body p{margin:0 0 14px}.body h2{font-size:20px;margin:26px 0 8px}.body h3{font-size:17px;margin:22px 0 6px}
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

$html = "<!--real generated texts + parameters vs original--><meta charset='utf-8'>"
 . "<meta name='viewport' content='width=device-width,initial-scale=1'>"
 . "<title>Реальные тексты + сравнение с оригиналом · вкладки</title><style>$css</style>"
 . "<div class='wrap'>"
 . "<div class='eyebrow'>Готовый контент + параметры vs оригинал · три регистра</div>"
 . "<h1>Реальные тексты со сравнением с оригиналом</h1>"
 . "<p class='lead'>Над каждой страницей — параметры нашего текста и рядом значение ОРИГИНАЛА (пер-сайтовый профиль донора из корпуса). Цветная метка слева у чипа: <b style='color:var(--ok)'>совпало</b> · <b style='color:var(--warn)'>близко</b> · <b style='color:var(--bad)'>расходится</b>. В шапке страницы — сколько параметров попало в оригинал. В семантике две полоски: наш и оригинал.</p>"
 . "<div class='stabs'>$topTabs</div>"
 . $panes
 . "<div class='foot'>Наши цифры — Analyzer по готовому тексту. Оригинал — data/donors.json (те же измерения по сайту-донору). Порог совпадения: ±25% или ±2 (для долей ±0.8).</div>"
 . "</div><script>$js</script>";

file_put_contents($out, $html);
fwrite(STDERR, "→ $out (".round(strlen($html)/1024)." KB)\n");

<?php
declare(strict_types=1);

/**
 * Витрина РЕАЛЬНЫХ сгенерированных текстов в двухуровневых вкладках:
 *   верхний ряд — стиль/регистр (донор), нижний — страница связки.
 * Никаких синтетических цифр: в файл кладётся именно тот HTML, что был написан.
 *
 *   php build-real-texts-viewer.php <out.html>
 */

$out = $argv[1] ?? (__DIR__ . '/../reports/real-texts.html');
$SP  = getenv('SCRATCH') ?: '/tmp/claude-0/-home-user-cladue/580c9237-8e67-549d-b11b-3f159fa71245/scratchpad';

$LABEL = ['main'=>'Главная','zerkalo'=>'Зеркало','vhod'=>'Вход','registracia'=>'Регистрация','bonus'=>'Бонусы','slots'=>'Слоты','app'=>'Приложение'];

// Три реальных набора в разных регистрах.
$SETS = [
  [
    'id'=>'exp','tab'=>'Экспертный «я»','donor'=>'донор Monro',
    'desc'=>'Личный опыт, первое лицо, «я захожу / я проверял». Спокойный тон практика.',
    'brand'=>['%brand_name_ru%'=>'Монрополь','%brand_name_en%'=>'Monropol','%domain_name%'=>'monropol.com','%date%'=>'июль 2026'],
    'dir'=>'exp',
    'pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
  ],
  [
    'id'=>'delo','tab'=>'Деловой «вы»','donor'=>'шаблон Casinovia',
    'desc'=>'Нейтрально-деловой обзор на «вы», без сленга. Структурный разбор площадки.',
    'brand'=>[],
    'dir'=>'out',
    'pages'=>['main','zerkalo','vhod','registracia','bonus','slots','app'],
  ],
  [
    'id'=>'derz','tab'=>'Дерзкий «ты»','donor'=>'донор Cosmospin',
    'desc'=>'Разговорный, на «ты», со сленгом и эмодзи — «погнали по фактам».',
    'brand'=>[],
    'dir'=>'cmp',
    'pages'=>['main'],
    'files'=>['main'=>'gen_main_derz.html'],
  ],
];

function wordcount(string $html): int {
    $t = preg_replace('~<script.*?</script>~su', ' ', $html);
    $t = strip_tags((string)$t);
    return count(preg_split('~\s+~u', trim((string)$t), -1, PREG_SPLIT_NO_EMPTY));
}

// article-фрагмент: срезаем JSON-LD (нужен для SEO, но не для чтения) и подставляем бренд
function prep(string $html, array $brand): array {
    $ld = preg_match_all('~application/ld\+json~', $html);
    $body = preg_replace('~<script[^>]*application/ld\+json[^>]*>.*?</script>~su', '', $html);
    $words = wordcount((string)$body);
    $links = preg_match_all('~<a\s+href=~i', (string)$body);
    if ($brand) $body = strtr((string)$body, $brand);
    return ['body'=>trim((string)$body),'words'=>$words,'links'=>$links,'ld'=>$ld];
}

$topTabs = ''; $panes = '';
foreach ($SETS as $si => $set) {
    $dir = rtrim($SP,'/').'/'.$set['dir'];
    $topActive = $si===0 ? ' active' : '';
    $topTabs .= "<button class='stab{$topActive}' data-set='{$set['id']}'>".$set['tab']
             . "<span class='sd'>{$set['donor']}</span></button>";

    // страницы набора
    $pageTabs = ''; $pagePanes = ''; $totalW = 0; $n = 0;
    foreach ($set['pages'] as $pi => $p) {
        $file = $dir.'/'.($set['files'][$p] ?? ($p.'.html'));
        if (!is_file($file)) continue;
        $raw = (string)file_get_contents($file);
        $d = prep($raw, $set['brand']);
        $totalW += $d['words']; $n++;
        $pa = $pi===0 ? ' active' : '';
        $pageTabs .= "<button class='ptab{$pa}' data-page='{$set['id']}:{$p}'>".$LABEL[$p]."</button>";
        $meta = "<div class='ameta'><span>{$d['words']} слов</span>"
              . ($d['links']?"<span>{$d['links']} внутр. ссылок</span>":"")
              . ($d['ld']?"<span>Schema.org разметка</span>":"")
              . "</div>";
        $pagePanes .= "<article class='page{$pa}' data-page='{$set['id']}:{$p}'>"
                    . "<h3 class='atitle'>".$LABEL[$p]."</h3>{$meta}<div class='body'>{$d['body']}</div></article>";
    }
    $avg = $n ? " · всего ~".number_format($totalW,0,'',' ')." слов на {$n} стр." : '';
    $paneActive = $si===0 ? ' active' : '';
    $panes .= "<section class='set{$paneActive}' data-set='{$set['id']}'>"
            . "<p class='setdesc'>{$set['desc']}{$avg}</p>"
            . "<div class='ptabs'>{$pageTabs}</div>{$pagePanes}</section>";
}

$css = <<<CSS
:root{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--accent2:#7a5cf0;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;--mono:ui-monospace,Menlo,Consolas,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--accent2:#a08bff}}
:root[data-theme="dark"]{--bg:#0d121b;--panel:#151d29;--soft:#1a2330;--ink:#e7ecf5;--muted:#8b98b0;--line:#26303f;--accent:#5b8bff;--accent2:#a08bff}
:root[data-theme="light"]{--bg:#f4f6fb;--panel:#fff;--soft:#eef2f9;--ink:#161d29;--muted:#5d6b82;--line:#e2e7f0;--accent:#3f6fe0;--accent2:#7a5cf0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.62 var(--sans)}
.wrap{max-width:820px;margin:0 auto;padding:24px 18px 90px}
.eyebrow{font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:700}
h1{font-size:23px;margin:6px 0 8px}.lead{color:var(--muted);font-size:14px;max-width:80ch;margin:0 0 18px}
.stabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 4px}
.stab{cursor:pointer;border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:10px 14px;border-radius:11px;font:600 14px var(--sans);display:flex;flex-direction:column;gap:2px;text-align:left;line-height:1.2}
.stab .sd{font-weight:500;font-size:11px;color:var(--muted)}
.stab.active{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent);color:var(--accent)}
.stab.active .sd{color:var(--accent)}
.set{display:none}.set.active{display:block}
.setdesc{color:var(--muted);font-size:13px;margin:12px 0 12px;padding:9px 12px;background:var(--soft);border-radius:9px}
.ptabs{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 16px;border-bottom:1px solid var(--line);padding-bottom:10px}
.ptab{cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--muted);padding:6px 12px;border-radius:20px;font:600 12.5px var(--sans)}
.ptab.active{background:var(--accent);border-color:var(--accent);color:#fff}
.page{display:none}.page.active{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0}to{opacity:1}}
.atitle{font-size:19px;margin:4px 0 6px}
.ameta{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font:600 11.5px var(--mono);margin:0 0 18px;padding-bottom:12px;border-bottom:1px dashed var(--line)}
.body{font-size:16px}
.body p{margin:0 0 14px}
.body h2{font-size:20px;margin:26px 0 8px;padding-top:6px}
.body h3{font-size:17px;margin:22px 0 6px}
.body ul{margin:0 0 16px;padding-left:22px}.body li{margin:4px 0}
.body a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 35%,transparent)}
.body blockquote{margin:16px 0;padding:10px 16px;border-left:3px solid var(--accent2);background:var(--soft);border-radius:0 9px 9px 0;color:var(--ink);font-style:italic}
.body table{border-collapse:collapse;width:100%;font-size:14px;margin:14px 0;display:block;overflow-x:auto}
.body th,.body td{padding:8px 12px;border:1px solid var(--line);text-align:left}
.body th{background:var(--soft);color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.03em}
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

$html = "<!--real generated texts viewer--><meta charset='utf-8'>"
 . "<meta name='viewport' content='width=device-width,initial-scale=1'>"
 . "<title>Реальные тексты генератора · вкладки</title><style>$css</style>"
 . "<div class='wrap'>"
 . "<div class='eyebrow'>Готовый контент · три регистра · связка страниц</div>"
 . "<h1>Реальные тексты генератора</h1>"
 . "<p class='lead'>Это не план и не метрики, а сам написанный контент. Верхние вкладки — стиль/регистр (взят у своего донора), нижние — страницы связки. Бренд, домен и дата — переменные-плейсхолдеры, здесь подставлены демо-значения для чтения.</p>"
 . "<div class='stabs'>$topTabs</div>"
 . $panes
 . "<div class='foot'>Тексты написаны под профиль донора: объём, регистр, семантика, перелинковка, бренд-переменные. Один шаблон → каждый прогон даёт новую начинку.</div>"
 . "</div><script>$js</script>";

file_put_contents($out, $html);
fwrite(STDERR, "→ $out (".round(strlen($html)/1024)." KB)\n");

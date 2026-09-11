<?php
// stili7.php — стили третьей системы: CSS под разметку контента (hero, слоты, выплаты, FAQ).
// php stili7.php <папка комплекта> --тема=N
declare(strict_types=1);
require __DIR__ . '/temy7.php';

function v7Шрифт(string $вид): array {
    return match ($вид) {
        'сериф' => ['Georgia, "Times New Roman", serif', 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'],
        'узкий' => ['"Segoe UI Semibold", "Helvetica Neue", Arial, sans-serif', '"Segoe UI", Roboto, Arial, sans-serif'],
        default => ['system-ui, -apple-system, "Segoe UI", Roboto, sans-serif', 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'],
    };
}

function v7Радиус(string $форма): array {
    return match ($форма) {
        'острые'  => ['2px', '2px', ''],
        'круглые' => ['20px', '14px', ''],
        'скос'    => ['12px', '10px', 'clip-path:polygon(0 0,calc(100% - 18px) 0,100% 18px,100% 100%,0 100%)'],
        default   => ['10px', '8px', ''],
    };
}

function v7Заголовок(array $т, string $sc): string {
    $а = $т['акцент'];
    return match ($т['заголовок']) {
        'капс' => "
$sc h2{font-size:1.16rem;letter-spacing:.14em;text-transform:uppercase;color:$а;margin:0 0 14px}
$sc h3{font-size:1rem;letter-spacing:.08em;text-transform:uppercase;color:var(--тек);margin:0 0 10px}",
        'крупный' => "
$sc h2{font-size:clamp(1.45rem,3vw,2.05rem);line-height:1.18;margin:0 0 16px;box-shadow:inset 0 -.3em 0 var(--мяг)}
$sc h3{font-size:1.16rem;margin:0 0 10px}",
        'номерной' => "
$sc{counter-reset:зг}
$sc h2{font-size:1.42rem;margin:0 0 15px;display:flex;gap:12px;align-items:baseline}
$sc h2::before{counter-increment:зг;content:counter(зг,decimal-leading-zero);font-size:.8em;color:$а;font-variant-numeric:tabular-nums;opacity:.85}
$sc h3{font-size:1.1rem;margin:0 0 10px;color:var(--тек)}",
        default => "
$sc h2{font-size:1.44rem;line-height:1.25;margin:0 0 16px;padding-left:15px;border-left:4px solid $а}
$sc h3{font-size:1.1rem;margin:0 0 10px;padding-left:15px;border-left:2px solid var(--рам)}",
    };
}

function v7Маркер(array $т, string $sc): string {
    $а = $т['акцент'];
    return match ($т['метка']) {
        'угол'  => "$sc ul:not(.hero-features)>li::before{content:'▸';color:$а;position:absolute;left:0;top:0}",
        'точки' => "$sc ul:not(.hero-features)>li::before{content:'';position:absolute;left:3px;top:.66em;width:7px;height:7px;border-radius:50%;background:$а}",
        default => "$sc ul:not(.hero-features)>li::before{content:'';position:absolute;left:0;top:.82em;width:12px;height:2px;background:$а}",
    };
}

function v7Слоты(array $т, string $sc): string {
    $а = $т['акцент']; $б = $т['акцент2'];
    if ($т['слот'] === 'компакт') {
        return "
$sc .slots-grid{display:grid;gap:10px}
$sc .slot-card{background:var(--карта);border:1px solid var(--рам);border-radius:var(--r2)}
$sc .slot-card-inner{display:grid;grid-template-columns:64px 1fr auto;gap:14px;align-items:center;padding:10px 14px}
$sc .slot-poster{position:relative;height:52px;border-radius:var(--r2);overflow:hidden;background:linear-gradient(135deg,$а,$б)}
$sc .slot-poster img{width:100%;height:100%;object-fit:cover;display:block}
$sc .slot-poster-fallback{display:flex;align-items:center;justify-content:center;height:100%;font-size:22px}
$sc .slot-fallback-name{display:none}
$sc .slot-badge{position:absolute;inset:auto 0 0 0;font-size:9px;text-align:center;background:#0009;color:#fff;letter-spacing:.06em}
$sc .slot-info{min-width:0}
$sc .slot-name{margin:0;font-size:1rem;border:0;padding:0}
$sc .slot-provider{font-size:.8rem;color:var(--тус)}
$sc .slot-footer{display:flex;gap:14px;align-items:center}
$sc .slot-rtp{font-size:.82rem;color:var(--тус);white-space:nowrap}
$sc .slot-rtp-value{color:$а;font-weight:700}
$sc .slot-play-btn{border:0;background:$а;color:#fff;padding:7px 14px;border-radius:999px;font-size:.82rem;font-weight:600}";
    }
    $подпись = $т['слот'] === 'картинка'
        ? "color:var(--тек);opacity:.72"
        : "color:#fff;text-shadow:0 1px 6px #0006";
    $постер = $т['слот'] === 'картинка'
        ? "background:linear-gradient(160deg,color-mix(in srgb,$а 26%,var(--карта2)),var(--карта2))"
        : "background:linear-gradient(150deg,color-mix(in srgb,$а 82%,var(--карта)),color-mix(in srgb,$б 52%,var(--карта2)))";
    return "
$sc .slots-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px}
$sc .slot-card{background:var(--карта);border:1px solid var(--рам);border-radius:var(--r);overflow:hidden}
$sc .slot-card-inner{display:flex;flex-direction:column;height:100%}
$sc .slot-poster{position:relative;aspect-ratio:16/10;$постер}
$sc .slot-poster img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
$sc .slot-poster-fallback{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;$подпись}
$sc .k7-has-img .slot-poster-fallback{display:none}
$sc .slot-fallback-icon{font-size:26px}
$sc .slot-fallback-name{font-size:.76rem;letter-spacing:.08em;text-transform:uppercase;opacity:.9;padding:0 8px;text-align:center}
$sc .slot-badge{position:absolute;top:8px;right:8px;font-size:.64rem;letter-spacing:.06em;text-transform:uppercase;padding:3px 8px;border-radius:999px;background:#000a;color:#fff}
$sc .slot-badge-high{background:$а;color:#fff}
$sc .slot-badge-medium{background:#0009;color:#fff}
$sc .slot-info{padding:12px 13px 4px}
$sc .slot-name{margin:0 0 3px;font-size:.98rem;border:0;padding:0}
$sc .slot-provider{font-size:.78rem;color:var(--тус)}
$sc .slot-footer{margin-top:auto;padding:10px 13px 13px;display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
$sc .slot-rtp{font-size:.78rem;color:var(--тус);white-space:nowrap}
$sc .slot-rtp-value{color:$а;font-weight:700;margin-left:4px}
$sc .slot-play-btn{border:0;background:var(--мяг);color:$а;padding:7px 13px;border-radius:999px;font-size:.8rem;font-weight:600;border:1px solid color-mix(in srgb,$а 40%,transparent)}";
}

function v7CSS(array $т, string $sc): string {
    [$рад, $рад2, $скос] = v7Радиус($т['форма']);
    [$шзаг, $штек] = v7Шрифт($т['шрифт']);
    $а = $т['акцент']; $б = $т['акцент2'];
    $карточка = "background:var(--карта);border:1px solid var(--рам);border-radius:var(--r)";
    $css = "
$sc{--акц:$а;--акц2:$б;--мяг:{$т['мягкий']};--фон:{$т['фон']};--карта:{$т['карта']};--карта2:{$т['карта2']};
--тек:{$т['текст']};--тус:{$т['тускло']};--рам:{$т['рамка']};--r:$рад;--r2:$рад2;
background:var(--фон);color:var(--тек);border-radius:var(--r);padding:clamp(16px,2.6vw,30px);
font:400 16px/1.68 $штек;text-align:left}
$sc *,$sc *::before,$sc *::after{box-sizing:border-box}
$sc>*+*{margin-top:24px}
$sc h2,$sc h3,$sc .hero-headline,$sc .cta-title{font-family:$шзаг;font-weight:700}
$sc p{margin:0 0 13px}
$sc p:last-child{margin-bottom:0}
$sc a{color:$а;text-decoration:none;border-bottom:1px solid color-mix(in srgb,$а 42%,transparent)}
$sc p strong,$sc li strong{background:var(--мяг);padding:0 .24em;border-radius:3px}
$sc ul:not(.hero-features):not(.quicklinks-grid),$sc ol{margin:0 0 15px;padding-left:0;list-style:none}
$sc ul:not(.hero-features)>li,$sc ol>li{position:relative;padding-left:24px;margin-bottom:8px}
" . v7Маркер($т, $sc) . "
$sc ol{counter-reset:сп}
$sc ol>li::before{content:counter(сп) '.';counter-increment:сп;background:none;width:auto;height:auto;top:0;color:$а;font-weight:700}
$sc table{width:100%;border-collapse:collapse;margin:0 0 16px;font-size:.94rem}
$sc th,$sc td{padding:9px 12px;border-bottom:1px solid var(--рам);text-align:left}
$sc th{color:$а;font-size:.8rem;letter-spacing:.08em;text-transform:uppercase}
" . v7Заголовок($т, $sc) . "

/* --- герой --- */
$sc .hero-value{ $карточка;padding:clamp(18px,3vw,30px);$скос}
$sc .hero-value-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,.95fr);gap:26px;align-items:start}
$sc .hero-value-grid:has(>:only-child){grid-template-columns:1fr}
$sc .hero-badge{display:inline-flex;align-items:center;gap:8px;padding:5px 13px;border-radius:999px;background:var(--мяг);color:$а;font-size:.78rem;letter-spacing:.1em;text-transform:uppercase;margin-bottom:14px}
$sc .hero-headline{font-size:clamp(1.7rem,4vw,2.5rem);line-height:1.1;margin:0 0 10px;padding:0;border:0;box-shadow:none;display:block;text-transform:none;letter-spacing:-.01em;color:var(--тек)}
$sc .hero-headline::before{content:none}
$sc .hero-tagline{color:var(--тус);font-size:1.05rem;margin-bottom:18px}
$sc .hero-features{list-style:none;padding:0;margin:0 0 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:9px}
$sc .hero-features li{display:flex;align-items:center;gap:9px;padding:9px 12px;background:var(--карта2);border:1px solid var(--рам);border-radius:var(--r2);font-size:.9rem}
$sc .feature-icon{font-size:17px}
$sc .hero-actions{display:flex;flex-wrap:wrap;gap:11px}
$sc .btn-apple,$sc .btn,$sc .payout-btn{display:inline-block;padding:11px 22px;border-radius:999px;font-weight:600;font-size:.94rem;border:1px solid transparent;text-align:center}
$sc .btn-apple-primary,$sc .btn-primary,$sc .payout-btn{background:$а;color:#fff;border-color:$а}
$sc .btn-apple-secondary{background:transparent;color:$а;border-color:color-mix(in srgb,$а 45%,transparent)}
$sc .hero-quicklinks{background:var(--карта2);border:1px solid var(--рам);border-radius:var(--r);padding:16px}
$sc .quicklinks-title{font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;color:var(--тус);margin:0 0 12px;padding:0;border:0}
$sc .quicklinks-title::before{content:none}
$sc .quicklinks-grid{display:grid;gap:7px}
$sc .quicklink-item{display:grid;grid-template-columns:26px 1fr auto;gap:9px;align-items:center;padding:9px 10px;border-radius:var(--r2);border:1px solid var(--рам);background:var(--карта);color:var(--тек);font-size:.9rem}
$sc .ql-icon{font-size:16px}
$sc .ql-meta{font-size:.74rem;color:var(--тус)}

/* --- колонки ценности --- */
$sc .value-pillars-heading{margin-bottom:16px}
$sc .value-pillars-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:13px}
$sc .value-pillar{display:flex;gap:12px;padding:16px;$карточка;$скос}
$sc .value-pillar-icon{font-size:22px;line-height:1}
$sc .value-pillar-title{font-size:1rem;margin:0 0 5px;padding:0;border:0}
$sc .value-pillar-title::before{content:none}
$sc .value-pillar-desc{font-size:.9rem;color:var(--тус);margin:0}

/* --- витрина слотов --- */
$sc .slots-dashboard{ $карточка;padding:clamp(16px,2.6vw,26px)}
$sc .slots-dashboard-header{margin-bottom:16px}
$sc .slots-dashboard-title-wrap{display:flex;gap:13px;align-items:center}
$sc .slots-dashboard-icon{font-size:26px}
$sc .slots-dashboard-title{margin:0;padding:0;border:0;font-size:1.3rem}
$sc .slots-dashboard-title::before{content:none}
$sc .slots-dashboard-subtitle{margin:2px 0 0;color:var(--тус);font-size:.9rem}
$sc .slots-dashboard-tabs{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
$sc .slots-tab{background:var(--карта2);border:1px solid var(--рам);color:var(--тус);padding:7px 14px;border-radius:999px;font:inherit;font-size:.84rem}
$sc .slots-tab.active{background:var(--мяг);border-color:color-mix(in srgb,$а 45%,transparent);color:$а;font-weight:600}
$sc .slots-tab-content+.slots-tab-content{margin-top:14px;padding-top:14px;border-top:1px dashed var(--рам)}
" . v7Слоты($т, $sc) . "

/* --- джекпоты и выплаты --- */
$sc .recent-payouts-block{display:grid;gap:14px;background:none;border:0;padding:0}
$sc .jackpot-strip{ $карточка;padding:15px}
$sc .jackpot-strip-title{display:flex;gap:9px;align-items:center;font-weight:700;margin-bottom:12px;font-size:.95rem}
$sc .jackpot-strip-icon{font-size:18px}
$sc .jackpot-strip-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:9px}
$sc .jackpot-cell{display:flex;gap:10px;align-items:center;padding:11px 12px;background:var(--карта2);border:1px solid var(--рам);border-radius:var(--r2)}
$sc .jackpot-cell-pulse{border-color:color-mix(in srgb,$а 50%,transparent);background:var(--мяг)}
$sc .jackpot-cell-icon{font-size:19px}
$sc .jackpot-cell-info{display:flex;flex-direction:column;min-width:0}
$sc .jackpot-cell-name{font-size:.78rem;color:var(--тус)}
$sc .jackpot-cell-amount{font-weight:700;color:$а;font-variant-numeric:tabular-nums}
$sc .payout-feed{ $карточка;padding:15px}
$sc .payout-feed-header{display:flex;gap:9px;align-items:center;margin-bottom:11px;font-weight:700;font-size:.95rem}
$sc .payout-feed-dot{width:9px;height:9px;border-radius:50%;background:$а;box-shadow:0 0 0 4px var(--мяг)}
$sc .payout-row{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;padding:8px 11px;border-radius:var(--r2);font-size:.88rem;border:1px solid transparent}
$sc .payout-row+.payout-row{margin-top:5px}
$sc .payout-row-normal{background:var(--карта2)}
$sc .payout-row-big{background:var(--мяг);border-color:color-mix(in srgb,$а 32%,transparent)}
$sc .payout-row-mega,$sc .payout-row-jackpot{background:linear-gradient(90deg,var(--мяг),transparent);border-color:color-mix(in srgb,$а 55%,transparent)}
$sc .payout-row-name{font-weight:600}
$sc .payout-row-sep{color:var(--тус)}
$sc .payout-row-amount{color:$а;font-weight:700;font-variant-numeric:tabular-nums}
$sc .payout-row-slot{color:var(--тус)}
$sc .payout-row-time{margin-left:auto;color:var(--тус);font-size:.8rem}
$sc .payout-cta{text-align:center;margin-top:13px}

/* --- показатели --- */
$sc .stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
$sc .stat-card{padding:15px;text-align:center;$карточка}
$sc .stat-icon{font-size:21px}
$sc .stat-value{display:block;font-size:1.45rem;font-weight:700;color:$а;font-variant-numeric:tabular-nums;margin:5px 0 3px}
$sc .stat-label{font-size:.82rem;color:var(--тус)}

/* --- вопросы, отзывы, тематические блоки --- */
$sc .faq-section,$sc .review-quotes-block,$sc .page-thematic-block,$sc .info-block,$sc .layout-block>section{ $карточка;padding:clamp(16px,2.6vw,26px)}
$sc .layout-block{padding:0;background:none;border:0}
$sc .faq-list{display:grid;gap:9px}
$sc .faq-item{background:var(--карта2);border:1px solid var(--рам);border-radius:var(--r2);padding:13px 15px}
$sc .faq-item.open{border-color:color-mix(in srgb,$а 42%,transparent)}
$sc .faq-question{margin:0;font-size:1rem;font-weight:700;padding:0;border:0;background:none;color:var(--тек);font-family:$шзаг;text-align:left;display:flex;gap:9px;width:100%}
$sc .faq-question::before{content:'—';color:$а;flex:none}
$sc .faq-answer{margin-top:9px;color:var(--тус);font-size:.94rem}
$sc .faq-answer p:last-child{margin-bottom:0}
$sc .review-quotes-heading{margin-bottom:6px}
$sc .review-quotes-desc{color:var(--тус);margin-bottom:14px}
$sc .review-quotes-list{display:grid;gap:10px}
$sc .review-quote-item .faq-question::before{content:'“';font-size:1.5em;line-height:.7}
$sc .review-quote-summary{font-weight:700}
$sc .review-quote-text{margin:8px 0 0;color:var(--тус);font-size:.94rem}
$sc .gradient-text{color:$а}

/* --- призывы --- */
$sc .cta-block{padding:clamp(18px,3vw,28px);border-radius:var(--r);background:linear-gradient(135deg,var(--мяг),var(--карта2));border:1px solid color-mix(in srgb,$а 34%,transparent);text-align:center}
$sc .cta-icon{font-size:27px}
$sc .cta-title{font-size:1.28rem;margin:8px 0 6px}
$sc .cta-subtitle{color:var(--тус);margin-bottom:14px}
$sc .cta-trust{font-size:.86rem;color:var(--тус);margin:12px 0 0}
$sc .badge{display:inline-block;padding:3px 10px;border-radius:999px;background:var(--мяг);color:$а;font-size:.78rem}

/* --- картинки --- */
$sc .k7-fig{margin:0 0 22px}
$sc .k7-fig img{display:block;width:100%;height:auto;border-radius:var(--r)}
$sc .k7-fig figcaption{margin-top:7px;font-size:.8rem;color:var(--тус);letter-spacing:.04em}
$sc .k7-vrezka{float:right;width:min(300px,42%);margin:0 0 16px 20px}
$sc .k7-fon{position:relative;padding:clamp(20px,4vw,38px);border-radius:var(--r);background-size:cover;background-position:center;color:#fff;border:0}
$sc .k7-fon>*{background:transparent;border-color:#ffffff33}
$sc .k7-fon h2,$sc .k7-fon h3,$sc .k7-fon .hero-headline{color:#fff}
$sc .k7-fon .hero-quicklinks,$sc .k7-fon .hero-features li,$sc .k7-fon .quicklink-item,$sc .k7-fon .value-pillar{background:#00000052;border-color:#ffffff2e;color:#fff}
$sc .k7-fon .ql-meta,$sc .k7-fon .value-pillar-desc,$sc .k7-fon .slots-dashboard-subtitle{color:#dde2ee}
$sc .k7-fon .hero-badge{background:#ffffff26;color:#fff}
$sc .k7-fon .btn-apple-secondary,$sc .k7-fon .slot-play-btn{color:#fff;border-color:#ffffff66;background:#ffffff1f}
$sc .k7-fon p,$sc .k7-fon .hero-tagline{color:#e7e9f2}

@media (max-width:760px){
$sc .hero-value-grid{grid-template-columns:1fr}
$sc .k7-vrezka{float:none;width:100%;margin:0 0 16px}
$sc .payout-row-time{margin-left:0}
}
";
    return preg_replace('/\n{2,}/', "\n", $css);
}

/** Часть сайтов приходит с обфусцированными классами — для них слой по структуре. */
function v7Структура(array $т, string $sc): string {
    $а = $т['акцент'];
    $кнопка = "display:inline-block;padding:10px 20px;border-radius:999px;font-weight:600;font-size:.92rem;border:1px solid $а;background:$а;color:#fff";
    $только = ":has(>a):not(:has(>:not(a)))";
    return "
$sc section,$sc aside{background:var(--карта);border:1px solid var(--рам);border-radius:var(--r);padding:clamp(16px,2.6vw,26px)}
$sc section>p:first-child{font-size:1.05rem;color:var(--тус)}
$sc article{background:var(--карта2);border:1px solid var(--рам);border-radius:var(--r2);padding:14px}
$sc div:has(>article+article){display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
$sc div$только{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 16px}
$sc div$только>a{ $кнопка}
$sc div$только>a:nth-child(2){background:transparent;color:$а}
$sc button{background:var(--карта2);border:1px solid var(--рам);color:var(--тус);padding:7px 14px;border-radius:999px;font:inherit;font-size:.84rem}
$sc div:has(>button+button){display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
$sc div:has(>span+span){display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
$sc article h3{margin-top:0}
";
}

/** Лента выплат приходит удвоенной (бегущая строка) — в статике повтор виден, снимаем. */
function v7Разметка(string $html): string {
    $видел = [];
    return preg_replace_callback('~<div class="payout-row.*?</div>~s', function ($m) use (&$видел) {
        $ключ = preg_replace('/\s+/', ' ', trim(strip_tags($m[0])));
        if (isset($видел[$ключ])) return '';
        $видел[$ключ] = true;
        return $m[0];
    }, $html) ?? $html;
}

/** Убирает комментарии и лишние переводы строк. */
function v7Сжать(string $css): string {
    $css = preg_replace('~/\*.*?\*/~s', '', $css);
    return trim(preg_replace('/\s*\n\s*/', "\n", $css));
}

if (PHP_SAPI === 'cli' && realpath($argv[0] ?? '') === __FILE__) {
    $арг = array_slice($argv, 1); $dir = rtrim(array_shift($арг) ?? '', '/');
    $номер = 1; $скоуп = '';
    foreach ($арг as $a) {
        if (preg_match('/^--тема=(\d+)$/u', $a, $m)) $номер = (int) $m[1];
        if (preg_match('/^--класс=([\w-]+)$/u', $a, $m)) $скоуп = $m[1];
    }
    if (!is_dir($dir)) { fwrite(STDERR, "нет папки $dir\n"); exit(2); }
    if ($скоуп === '') $скоуп = 'k7-' . substr(hash('crc32b', basename($dir) . $номер), 0, 6);
    $т = v7Tema($номер);
    $css = v7Сжать(v7CSS($т, '.' . $скоуп) . v7Структура($т, '.' . $скоуп));
    foreach (glob("$dir/*.html") as $f) {
        $html = file_get_contents($f);
        if (strpos($html, $скоуп) !== false) {   // комплект уже оформлен — обновляем только стиль
            file_put_contents($f, preg_replace('~^<style>.*?</style>~s', "<style>$css</style>", $html, 1));
            continue;
        }
        file_put_contents($f, "<style>$css</style>\n<div class=\"$скоуп\">\n" . trim(v7Разметка($html)) . "\n</div>\n");
    }
    echo "{$т['палитра']}/{$т['заголовок']}/{$т['форма']}/{$т['слот']}/{$т['картинка']}: " . strlen($css) . " байт CSS\n";
}

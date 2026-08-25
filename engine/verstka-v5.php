<?php
/**
 * Оформление блоков комплекта v5. Только инлайновые стили — внешних
 * таблиц стилей вёрстка не допускает. Структуру не меняем: настоящих
 * <table> и новых <ul> не добавляем, потому что профиль держит
 * table_cols = 0 и полосу по спискам.
 *
 * php engine/verstka-v5.php <папка> [--без-картинок]
 *
 * --без-картинок: обложек в карточках слотов нет, поэтому заглушку с эмодзи
 * не прячем, а оформляем как плитку — иначе у карточки остаётся пустой верх.
 */

$папка = null; $безКартинок = false;
foreach (array_slice($argv, 1) as $а) {
    if ($а === '--без-картинок') { $безКартинок = true; continue; }
    if ($а[0] !== '-') { $папка = rtrim($а, '/'); }
}
if ($папка === null || !is_dir($папка)) {
    fwrite(STDERR, "usage: php engine/verstka-v5.php <папка> [--без-картинок]\n"); exit(1);
}

// Палитра полупрозрачная: блоки одинаково ложатся на светлую и тёмную тему.
const ПОДЛОЖКА  = 'rgba(127,133,160,.10)';
const ПОДЛОЖКА2 = 'rgba(127,133,160,.16)';
const КАНТ      = '1px solid rgba(127,133,160,.30)';
const ЗОЛОТО    = '#f5b52a';
const ТРЕВОГА   = 'rgba(240,90,90,.12)';
const УСПЕХ     = 'rgba(80,190,130,.12)';

/** class → инлайновый стиль. Ключ — первый класс элемента. */
$ПРАВИЛА = [
    // ── шапка страницы
    'hero-value'        => 'display:block;border:' . КАНТ . ';border-radius:16px;background:' . ПОДЛОЖКА . ';padding:20px;margin:0 0 22px',
    'hero-value-grid'   => 'display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px;align-items:start',
    'hero-badge'        => 'display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:999px;background:' . ПОДЛОЖКА2 . ';font-size:12px;font-weight:600;letter-spacing:.02em',
    'hero-headline'     => 'margin:12px 0 6px;font-size:26px;line-height:1.25',
    'hero-tagline'      => 'margin:0 0 14px;opacity:.88;font-size:15px;line-height:1.5',
    'hero-features'     => 'display:flex;flex-wrap:wrap;gap:8px;margin:0 0 16px;padding:0;list-style:none',
    'feature-icon'      => 'margin-right:6px',
    'hero-actions'      => 'display:flex;flex-wrap:wrap;gap:10px',
    'btn'               => 'display:inline-block;padding:10px 18px;border-radius:10px;background:' . ЗОЛОТО . ';color:#15161c;font-weight:700;text-decoration:none',
    'btn-apple'         => 'display:inline-block;padding:10px 18px;border-radius:10px;border:' . КАНТ . ';text-decoration:none;font-weight:600;color:inherit',

    // ── куда перейти
    // Внутри лежат заголовок и своя сетка ссылок. Когда контейнер сам был
    // сеткой, заголовок вставал отдельной колонкой рядом с ссылками, и в шапке
    // висело «Куда перейти» с пустотой под ним.
    'hero-quicklinks'   => 'display:block;margin:14px 0 0;padding:0;list-style:none',
    'quicklinks-title'  => 'margin:22px 0 12px;font-size:18px',
    'quicklinks-grid'   => 'display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:0 0 22px;padding:0;list-style:none',
    'quicklink-item'    => 'display:grid;grid-template-columns:26px 1fr;column-gap:10px;align-items:center;padding:12px 14px;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА . ';text-decoration:none;color:inherit',
    'ql-icon'           => 'grid-column:1;grid-row:1/span 2;font-size:20px;line-height:1',
    'ql-text'           => 'grid-column:2;font-weight:600;line-height:1.3',
    'ql-meta'           => 'grid-column:2;font-size:12px;opacity:.84;margin-top:2px',

    // ── последние выплаты: вид таблицы без тега table
    'recent-payouts-block' => 'display:block;border:' . КАНТ . ';border-radius:14px;overflow:hidden;margin:0 0 22px',
    'payout-feed'       => 'display:block',
    'payout-feed-header' => 'display:flex;align-items:center;gap:8px;padding:12px 14px;background:' . ПОДЛОЖКА2 . ';font-weight:700;font-size:14px',
    'payout-feed-dot'   => 'width:9px;height:9px;border-radius:50%;background:#3ddc84;display:inline-block;flex:0 0 auto',
    'payout-feed-title' => 'margin:0;font-size:14px;font-weight:700',
    'payout-scroll'     => 'display:block;overflow-x:auto',
    'payout-track'      => 'display:block;min-width:520px',
    'payout-row'        => 'display:grid;grid-template-columns:34px minmax(90px,1fr) minmax(96px,auto) minmax(130px,1.3fr) minmax(88px,auto);align-items:center;gap:10px;padding:10px 14px;border-top:1px solid rgba(127,133,160,.20)',
    'payout-row-icon'   => 'font-size:16px;line-height:1',
    'payout-row-name'   => 'font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis',
    'payout-row-sep'    => 'display:none',
    'payout-row-amount' => 'font-weight:700;color:' . ЗОЛОТО . ';white-space:nowrap',
    'payout-row-slot'   => 'font-size:13px;opacity:.88;white-space:nowrap;overflow:hidden;text-overflow:ellipsis',
    'payout-row-time'   => 'font-size:12px;opacity:.9;text-align:right;white-space:nowrap',
    'payout-cta'        => 'padding:14px;background:' . ПОДЛОЖКА . ';text-align:center',
    'payout-btn'        => 'display:inline-block;padding:10px 20px;border-radius:10px;background:' . ЗОЛОТО . ';color:#15161c;font-weight:700;text-decoration:none',

    // ── джекпоты и статистика: плитки
    'jackpot-strip'      => 'display:block;border:' . КАНТ . ';border-radius:14px;background:' . ПОДЛОЖКА . ';padding:16px;margin:0 0 22px',
    'jackpot-strip-title' => 'display:flex;align-items:center;gap:8px;margin:0 0 12px;font-size:15px;font-weight:700',
    'jackpot-strip-icon' => 'font-size:18px;line-height:1',
    'jackpot-strip-grid' => 'display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px',
    'jackpot-cell'       => 'display:block;padding:12px;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА2 . ';text-align:center',
    'jackpot-cell-icon'  => 'display:block;font-size:22px;line-height:1;margin-bottom:6px',
    'jackpot-cell-name'  => 'display:block;font-size:12px;opacity:.86',
    'jackpot-cell-amount' => 'display:block;font-size:18px;font-weight:800;color:' . ЗОЛОТО . ';margin:4px 0 2px',
    'jackpot-cell-info'  => 'display:block;font-size:11px;opacity:.9',
    'stats-grid'         => 'display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0',
    'stat-card'          => 'display:block;padding:14px;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА . ';text-align:center',
    'stat-icon'          => 'display:block;font-size:22px;line-height:1;margin-bottom:6px',
    'stat-value'         => 'display:block;font-size:19px;font-weight:800;color:' . ЗОЛОТО,
    'stat-label'         => 'display:block;font-size:12px;opacity:.84;margin-top:2px',

    // ── преимущества
    'value-pillars'      => 'display:block;margin:0 0 22px',
    'value-pillars-heading' => 'margin:0 0 12px;font-size:19px',
    'value-pillars-grid' => 'display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px',
    'value-pillar'       => 'display:block;padding:14px;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА . '',
    'value-pillar-icon'  => 'display:block;font-size:24px;line-height:1;margin-bottom:8px',
    'value-pillar-title' => 'margin:0 0 6px;font-size:15px;font-weight:700',
    'value-pillar-body'  => 'display:block',
    'value-pillar-desc'  => 'margin:0;font-size:13px;line-height:1.5;opacity:.88',

    // ── отзывы
    'review-quotes-block' => 'display:block;margin:0 0 22px',
    'review-quotes-heading' => 'margin:0 0 6px;font-size:19px',
    'review-quotes-desc' => 'margin:0 0 12px;font-size:14px;opacity:.86',
    'review-quotes-list' => 'display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:0;padding:0;list-style:none',
    'review-quote-text'  => 'display:block;padding:14px 14px 12px;border:' . КАНТ . ';border-left:3px solid ' . ЗОЛОТО . ';border-radius:0 12px 12px 0;background:' . ПОДЛОЖКА . ';font-style:italic;line-height:1.55',
    'review-quote-summary' => 'display:block;margin-top:8px;font-size:12px;font-style:normal;opacity:.84',

    // ── вопросы и ответы
    'faq-section'   => 'display:block;border:' . КАНТ . ';border-radius:14px;background:' . ПОДЛОЖКА . ';padding:18px;margin:22px 0',
    'faq-list'      => 'display:grid;gap:10px;margin:12px 0 0;padding:0;list-style:none',
    'faq-item'      => 'display:block;padding:12px 14px;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА2 . '',
    'faq-question'  => 'display:block;width:100%;text-align:left;background:none;border:0;border-left:3px solid ' . ЗОЛОТО . ';color:inherit;font-family:inherit;font-size:15px;font-weight:700;line-height:1.35;margin:0 0 6px;padding:0 0 0 12px;cursor:pointer',
    'faq-answer'    => 'display:block;font-size:14px;line-height:1.6;opacity:.9',

    // ── тематические блоки и заголовки
    'layout-block'        => 'display:block;margin:0 0 22px',
    'page-thematic-block' => 'display:block;border:' . КАНТ . ';border-radius:14px;background:' . ПОДЛОЖКА . ';padding:18px',
    'info-block'          => 'display:block;border:' . КАНТ . ';border-radius:14px;background:' . ПОДЛОЖКА . ';padding:18px;margin:0 0 22px',
    'gradient-text'       => 'display:block;margin:0 0 10px;font-size:20px',
    'text-glow-animation' => 'display:block;margin:0 0 10px;font-size:20px',

    // ── дашборд слотов
    'slots-dashboard'           => 'display:block;border:' . КАНТ . ';border-radius:16px;background:' . ПОДЛОЖКА . ';padding:18px;margin:0 0 22px',
    'slots-dashboard-container' => 'display:block',
    'slots-dashboard-header'    => 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 6px',
    'slots-dashboard-icon'      => 'font-size:22px;line-height:1',
    'slots-dashboard-title-wrap' => 'display:block',
    'slots-dashboard-title'     => 'margin:0;font-size:19px',
    'slots-dashboard-subtitle'  => 'margin:2px 0 0;font-size:13px;opacity:.86',
    'slots-dashboard-tabs'      => 'display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px',
    'slots-tab'                 => 'display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border:' . КАНТ . ';border-radius:999px;background:' . ПОДЛОЖКА2 . ';color:inherit;font-family:inherit;font-size:13px;font-weight:600;cursor:pointer',
    'slots-tab-content'         => 'display:block',
    'slots-grid'    => 'display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:14px;margin:14px 0 0',
    'slot-card'     => 'display:block;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА2 . ';overflow:hidden',
    'slot-card-inner' => 'display:flex;flex-direction:column;height:100%',
    'slot-poster'   => 'position:relative;line-height:0',
    'slot-poster-fallback' => 'display:none',   // при --без-картинок заменяется ниже
    'slot-badge'    => 'position:absolute;top:8px;right:8px;padding:3px 9px;border-radius:999px;background:rgba(10,12,20,.72);color:#fff;font-size:11px;line-height:1.4',
    'slot-info'     => 'padding:9px 11px 3px',
    'slot-name'     => 'margin:0;font-size:14px;line-height:1.3',
    'slot-provider' => 'font-size:11px;opacity:.84;margin-top:3px',
    'slot-footer'   => 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 11px 11px;margin-top:auto',
    'slot-rtp'      => 'font-size:11px;opacity:.9',
    'slot-rtp-label' => 'display:block;opacity:.86',
    'slot-rtp-value' => 'display:block;font-weight:700',
    'slot-play-btn' => 'display:inline-block;font-size:12px;padding:5px 11px;border-radius:8px;background:' . ЗОЛОТО . ';color:#15161c;text-decoration:none;white-space:nowrap',
];

// Без обложек заглушка становится единственным «постером» карточки: плитка
// с эмодзи и названием игры на градиенте, ростом под ту же высоту, что
// занимала бы картинка 640×480.
if ($безКартинок) {
    $ПРАВИЛА['slot-poster-fallback'] = 'display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;'
        . 'aspect-ratio:4/3;padding:10px;text-align:center;line-height:1.3;'
        . 'background:linear-gradient(160deg,rgba(127,133,160,.26),rgba(127,133,160,.10))';
    $ПРАВИЛА['slot-fallback-icon'] = 'font-size:52px;line-height:1';
    // название игры и так стоит под плиткой в slot-name — второй раз не повторяем
    $ПРАВИЛА['slot-fallback-name'] = 'display:none';
}

/** Абзацы-предупреждения превращаем в блок внимания (тег остаётся <p>). */
const ТРЕВОЖНЫЕ = [
    'не заходи, если боишься', 'если нужны гарантии', 'гарантий нет', 'гарантий никто не даёт',
    'важно понимать', 'не заходи, если', 'можно выиграть, можно проиграть',
];
const СПОКОЙНЫЕ = [
    'ответственная игра', 'играй с лимитом', 'без развода', 'по-честному',
];

/**
 * Любой <button> наследует цвет темы: иначе браузер красит текст в чёрный, а
 * фон — в белый. Дописывается последним, поверх правила по классу, и только
 * если цвет ещё не задан.
 */
function vsКнопка(string $л, int &$правил): string
{
    if (preg_match('~<button~', $л) !== 1 || strpos($л, 'color:inherit') !== false) { return $л; }
    $правил++;
    return strpos($л, ' style="') !== false
        ? preg_replace('~ style="~', ' style="color:inherit;font-family:inherit;', $л, 1)
        : preg_replace('~(<button)~', '$1 style="color:inherit;font-family:inherit"', $л, 1);
}

$файлы = glob($папка . '/*.html');
$всего = 0; $тревог = 0; $шапок = 0;

// строка заголовков для ленты выплат — вид таблицы без тега table
$КОЛОНКИ = 'display:grid;grid-template-columns:34px minmax(90px,1fr) minmax(96px,auto)'
         . ' minmax(130px,1.3fr) minmax(88px,auto);gap:10px;padding:9px 14px;font-size:11px'
         . ';letter-spacing:.04em;text-transform:uppercase;opacity:.9;font-weight:600';

foreach ($файлы as $файл) {
    $строки = explode("\n", file_get_contents($файл));
    $правил = 0; $ряд = 0; $вЧипах = false;
    $итог = [];

    foreach ($строки as $i => $л) {
        // ── блок внимания: абзац целиком в <strong> с тревожной или спокойной формулой
        if (preg_match('~^\s*<p[\s>]~', $л) === 1 && isset($строки[$i + 1])) {
            $тело = trim($строки[$i + 1]);
            $низ = mb_strtolower(strip_tags($тело), 'UTF-8');
            if (strpos($тело, '<strong>') === 0 && mb_strlen($низ, 'UTF-8') > 40 && strpos($л, 'style=') === false) {
                $фон = ''; $цвет = '';
                foreach (ТРЕВОЖНЫЕ as $ф) if (mb_strpos($низ, $ф, 0, 'UTF-8') !== false) { $фон = ТРЕВОГА; $цвет = '#f0685a'; break; }
                if ($фон === '') foreach (СПОКОЙНЫЕ as $ф) if (mb_strpos($низ, $ф, 0, 'UTF-8') !== false) { $фон = УСПЕХ; $цвет = '#4fbe86'; break; }
                if ($фон !== '') {
                    $стиль = 'margin:16px 0;padding:12px 16px;border-left:4px solid ' . $цвет
                           . ';border-radius:0 10px 10px 0;background:' . $фон . ';line-height:1.6';
                    $итог[] = preg_replace('~^(\s*<p)(\s|>)~', '$1 style="' . $стиль . '"$2', $л, 1);
                    $правил++; $тревог++;
                    continue;
                }
            }
        }

        // ── содержательные списки: воздух и цветные маркеры
        if (preg_match('~^\\s*<ul>\\s*$~', $л) === 1) {
            $итог[] = preg_replace('~<ul>~', '<ul style="margin:14px 0;padding-left:22px;line-height:1.65">', $л, 1);
            $правил++;
            continue;
        }
        if (preg_match('~^\\s*<li>\\s*$~', $л) === 1) {
            $итог[] = preg_replace('~<li>~', '<li style="margin:0 0 8px">', $л, 1);
            $правил++;
            continue;
        }
        if (preg_match('~^\\s*<strong>(Плюс|Минус|Совет|Факт|Итог|Важно|Кстати)~u', $л) === 1 && strpos($л, 'style=') === false) {
            $карта = ['Плюс' => '#4fbe86', 'Минус' => '#f0685a', 'Совет' => ЗОЛОТО,
                      'Факт' => ЗОЛОТО, 'Итог' => ЗОЛОТО, 'Важно' => '#f0685a', 'Кстати' => ЗОЛОТО];
            $итог[] = preg_replace_callback('~<strong>(Плюс|Минус|Совет|Факт|Итог|Важно|Кстати)~u',
                function ($m) use ($карта) { return '<strong style="color:' . $карта[$m[1]] . '">' . $m[1]; }, $л, 1);
            $правил++;
            continue;
        }

        // ── чипы возможностей в шапке
        if (strpos($л, 'class="hero-features"') !== false) $вЧипах = true;
        elseif ($вЧипах && strpos($л, '</ul>') !== false) $вЧипах = false;
        elseif ($вЧипах && preg_match('~^(\s*)<li(\s|>)~', $л, $m2) === 1 && strpos($л, 'style=') === false) {
            $итог[] = preg_replace('~^(\s*<li)(\s|>)~',
                '$1 style="display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border:'
                . КАНТ . ';border-radius:999px;background:' . ПОДЛОЖКА . ';font-size:13px"$2', $л, 1);
            $правил++;
            continue;
        }

        // ── общий разбор: на строке может быть несколько элементов с классами
        //
        // Раньше цвет кнопки подставлялся до этого разбора, прямо в $л. Строка
        // получала style=, и защита «уже оформлено — не трогаем» ниже отбрасывала
        // разобранный вариант: вкладки каталога оставались белыми кнопками
        // браузера, хотя правило для slots-tab в таблице есть. Теперь цвет
        // добавляется последним, к уже готовой строке.
        if (strpos($л, 'class="') !== false) {
            $ряд_ссылка = &$ряд;
            $новая = preg_replace_callback('~class="([^"]+)"~', function ($m) use (&$правил, &$ряд_ссылка, $ПРАВИЛА) {
                $первый = strtok($m[1], ' ');
                if (!isset($ПРАВИЛА[$первый])) return $m[0];
                $стиль = $ПРАВИЛА[$первый];
                if ($первый === 'payout-row' && ($ряд_ссылка++ % 2)) $стиль .= ';background:' . ПОДЛОЖКА;
                $правил++;
                return $m[0] . ' style="' . $стиль . '"';
            }, $л);
            if (strpos($л, ' style="') !== false) $новая = $л;   // уже оформлено — не трогаем
            $новая = vsКнопка($новая, $правил);
            $итог[] = $новая;

            // шапка колонок сразу после открытия дорожки выплат
            if (strpos($л, 'class="payout-track"') !== false) {
                $отступ = str_repeat(' ', strlen($л) - strlen(ltrim($л)) + 2);
                $итог[] = $отступ . '<div style="' . $КОЛОНКИ . '"><span></span><span>Игрок</span>'
                        . '<span>Выигрыш</span><span>Игра</span><span style="text-align:right">Когда</span></div>';
                $шапок++;
            }
            continue;
        }

        $итог[] = vsКнопка($л, $правил);
    }

    file_put_contents($файл, implode("\n", $итог));
    $всего += $правил;
}

echo "оформлено правил: $всего, блоков внимания: $тревог, шапок таблиц: $шапок, файлов: " . count($файлы) . "\n";

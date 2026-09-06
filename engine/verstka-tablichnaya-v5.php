<?php
/**
 * Оформление голых табличных страниц (section / table / aside / details).
 * Инлайновые стили по тегам: у этих текстов нет классов v5, и `verstka-v5.php`
 * им ничего не даёт. Палитра та же полупрозрачная — блоки ложатся на любую тему.
 *
 * php engine/verstka-tablichnaya-v5.php <папка>
 *
 * Идемпотентно: элемент со style= не трогается. Структура не меняется.
 */
$папка = null; $тема = 0;
foreach (array_slice($argv, 1) as $а) {
    if (preg_match('~^--тема=(\d+)$~u', $а, $m)) { $тема = (int) $m[1]; continue; }
    if ($а !== '' && $а[0] !== '-') { $папка = rtrim($а, '/'); }
}
if ($папка === null || !is_dir($папка)) { fwrite(STDERR, "usage: php engine/verstka-tablichnaya-v5.php <папка>\n"); exit(1); }

require_once __DIR__ . '/temy-v5.php';
$Т = v5Tema($тема);
define('ПОДЛОЖКА', $Т['подложка']);
define('ПОДЛОЖКА2', $Т['подложка2']);
define('КАНТ', $Т['кантCSS']);
define('ЗОЛОТО', $Т['акцент']);

$ТЕГИ = [
    'table'      => 'width:100%;border-collapse:separate;border-spacing:0;border:' . КАНТ . ';border-radius:12px;overflow:hidden;margin:0 0 20px;font-size:15px',
    'thead'      => 'background:' . ПОДЛОЖКА2,
    'th'         => 'text-align:left;padding:10px 12px;border-bottom:' . КАНТ . ';background:' . ПОДЛОЖКА2 . ';font-weight:600;white-space:nowrap',
    'td'         => 'padding:9px 12px;border-bottom:1px solid rgba(127,133,160,.18);vertical-align:top',
    'aside'      => 'display:block;border-left:4px solid ' . ЗОЛОТО . ';border-radius:0 12px 12px 0;background:' . ПОДЛОЖКА . ';padding:12px 16px;margin:0 0 20px',
    'blockquote' => 'margin:0 0 20px;padding:14px 18px;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА . ';font-style:italic',
    'details'    => 'display:block;border:' . КАНТ . ';border-radius:12px;padding:10px 14px;margin:0 0 12px;background:' . ПОДЛОЖКА,
    'summary'    => 'cursor:pointer;font-weight:600;padding:2px 0',
    'h2'         => 'margin:28px 0 12px;padding:0 0 8px;border-bottom:2px solid ' . ЗОЛОТО . ';font-size:24px;line-height:1.25',
    'h3'         => 'margin:22px 0 10px;font-size:19px;line-height:1.3',
    'nav'        => 'display:block;border:' . КАНТ . ';border-radius:12px;background:' . ПОДЛОЖКА . ';padding:10px 14px;margin:0 0 20px',
    'time'       => 'display:inline-block;padding:2px 10px;border-radius:999px;background:' . ПОДЛОЖКА2 . ';font-size:13px',
    'cite'       => 'display:block;margin-top:8px;font-size:13px;opacity:.8;font-style:normal',
    'figure'     => 'margin:0 0 20px',
    'figcaption' => 'font-size:13px;opacity:.8;margin-top:6px',
];
if ($тема > 0) {
    foreach ($ТЕГИ as $к => $v) { $ТЕГИ[$к] = v5TemaRadius($v, $Т); }
    $ТЕГИ['h2'] = v5TemaZagolovok($Т, 'h2');
    $ТЕГИ['h3'] = v5TemaZagolovok($Т, 'h3');
    $ТЕГИ['ul'] = 'margin:14px 0;padding-left:22px;line-height:' . $Т['строка'] . ';list-style-type:' . $Т['маркер'];
    $ТЕГИ['ol'] = 'margin:14px 0;padding-left:24px;line-height:' . $Т['строка'];
    $ТЕГИ['p']  = 'line-height:' . $Т['строка'] . ';margin:0 0 14px';
    if ($Т['тень'] !== '') { foreach (['table', 'aside', 'blockquote', 'details', 'nav'] as $к) { $ТЕГИ[$к] .= ';' . $Т['тень']; } }
    if ($Т['кант'] === 'none') { foreach ($ТЕГИ as $к => $v) { $ТЕГИ[$к] = str_replace('border:1px solid transparent', 'border:0', $v); } }
    if ($Т['заголовок'] === 'капс') { $ТЕГИ['th'] .= ';text-transform:uppercase;font-size:12px;letter-spacing:.06em'; }
}
$ДАТА = 'display:inline-block;padding:2px 10px;border-radius:999px;background:' . ПОДЛОЖКА2 . ';font-size:13px;font-style:normal;margin-right:6px';
$КЛАССЫ = [
    'table-responsive' => 'display:block;width:100%;overflow-x:auto;margin:0 0 20px',
    'menu'             => 'display:block',
];
$СТРОНГ = ['Плюс' => $Т['плюс'], 'Минус' => $Т['минус'], 'Совет' => ЗОЛОТО, 'Факт' => ЗОЛОТО,
           'Итог' => ЗОЛОТО, 'Важно' => '#f0685a', 'Кстати' => ЗОЛОТО, 'Ключевой вывод' => ЗОЛОТО];

$всего = 0; $файлы = glob($папка . '/*.html');
foreach ($файлы as $файл) {
    $html = file_get_contents($файл); $правил = 0; $ряд = 0;
    $html = preg_replace_callback('~<([a-zA-Z][a-zA-Z0-9]*)((?:[^<>"]|"[^"]*")*)>~', function ($m) use ($ТЕГИ, $КЛАССЫ, $ДАТА, $Т, &$правил, &$ряд) {
        $тег = strtolower($m[1]); $атр = $m[2];
        if (stripos($атр, 'style=') !== false) return $m[0];
        $стиль = null;
        if (preg_match('~class="([^"]+)"~', $атр, $c)) {
            $первый = strtok($c[1], ' ');
            if (isset($КЛАССЫ[$первый])) $стиль = $КЛАССЫ[$первый];
        }
        if ($стиль === null && isset($ТЕГИ[$тег])) $стиль = $ТЕГИ[$тег];
        if ($тег === 'tr') { $ряд++; if ($ряд % 2 === 0) $стиль = 'background:' . ПОДЛОЖКА; }
        if ($тег === 'table') $ряд = 0;
        if ($тег === 'em' && $стиль === null) $стиль = '__em__';
        if ($стиль === null) return $m[0];
        if ($стиль === '__em__') return $m[0];
        $правил++;
        return '<' . $m[1] . $атр . ' style="' . $стиль . '">';
    }, $html);
    // дата в <em>%date%</em> — чип, не курсив
    $html = preg_replace_callback('~<em>(\s*(?:%date%|\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{1,2}\s+[а-яё]+\s+\d{4})\s*)</em>~u',
        function ($m) use ($ДАТА, &$правил) { $правил++; return '<em style="' . $ДАТА . '">' . trim($m[1]) . '</em>'; }, $html);
    // цветные метки «Плюс:», «Минус:», «Ключевой вывод:»
    $html = preg_replace_callback('~<(strong|b)>(' . implode('|', array_map('preg_quote', array_keys($СТРОНГ))) . ')(?=[:\s])~u',
        function ($m) use ($СТРОНГ, &$правил) { $правил++; return '<' . $m[1] . ' style="color:' . $СТРОНГ[$m[2]] . '">' . $m[2]; }, $html);
    // ссылки меню — как чипы
    $html = preg_replace_callback('~(<nav[^>]*>.*?</nav>)~su', function ($m) use (&$правил, $Т) {
        return preg_replace_callback('~<li(?![^>]*style=)([^>]*)>~', function ($x) use (&$правил, $Т) {
            $правил++;
            return '<li' . $x[1] . ' style="display:inline-block;margin:4px 8px 4px 0;padding:5px 12px;border:' . КАНТ . ';border-radius:' . ($Т['пилюля'] ? '999px' : v5TemaRadius('8px', $Т)) . ';background:' . ПОДЛОЖКА2 . ';font-size:14px;list-style:none">';
        }, $m[1]);
    }, $html);
    file_put_contents($файл, $html); $всего += $правил;
}
echo "оформлено правил: $всего, файлов: " . count($файлы) . "\n";

<?php
/**
 * go.php — НЕПОТОПЛЯЕМЫЙ редиректор.
 *
 * Ключевой принцип: редирект НИКОГДА не зависит от базы данных.
 *   - офферы читаются из файла-кэша offers.php (мгновенно, без MySQL);
 *   - клик пишется одной строкой в файл clicks.log (атомарный append);
 *   - редирект отдаётся.
 * НИ ОДНОГО обращения к MySQL. Даже при DDoS сервер только дописывает строки
 * в файл и отдаёт 302 — это выдерживает любой хостинг.
 *
 * Клики переливаются в MySQL отдельным крон-скриптом import.php (раз в 5 мин).
 * Если MySQL ляжет — клики копятся в файле, редиректы работают, ничего не теряется.
 *
 * Ссылка:  sitegrator.com/go/СЛАГ   ->   /go.php?l=СЛАГ
 */

// НЕ подключаем db.php — go.php вообще не знает про MySQL.
$cfg = require __DIR__ . '/config.php';

$slug = trim($_GET['l'] ?? '', '/');

// ---------- 1. Находим оффер из файла-кэша (без БД) ----------
$offer = null;
$offersFile = __DIR__ . '/offers.php';
if (is_file($offersFile)) {
    $offers = include $offersFile;               // include кэшируется opcache — быстро
    if (is_array($offers) && isset($offers[$slug])) $offer = $offers[$slug];
}

// АВАРИЙНЫЙ fallback: если кэша нет/слаг не найден, но задан общий fallback_offer.
if ($offer === null && !empty($cfg['fallback_offer'])) {
    $offer = $cfg['fallback_offer'];
}

if ($offer === null || $offer === '') {
    http_response_code(404);
    exit('Not found');
}

// ---------- 2. Собираем данные клика ----------
$src = '';
foreach (['site', 's', 'src', 'source', 'sub', 'subid', 'utm_source'] as $k) {
    if (isset($_GET[$k]) && $_GET[$k] !== '') { $src = (string)$_GET[$k]; break; }
}
if ($src === '' && !empty($_SERVER['HTTP_REFERER'])) {
    $refHost = parse_url($_SERVER['HTTP_REFERER'], PHP_URL_HOST);
    if ($refHost) $src = $refHost;
}
$src = preg_replace('~^https?://~i', '', trim($src));
$src = preg_replace('~[/?#].*$~', '', $src);
$src = preg_replace('~^www\.~i', '', $src);
$src = strtolower($src);
$src = substr(preg_replace('~[^\w.\-]~u', '', $src), 0, 100);

$ua = substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 255);

$ip = $_SERVER['HTTP_CF_CONNECTING_IP']
    ?? (isset($_SERVER['HTTP_X_FORWARDED_FOR'])
        ? trim(explode(',', $_SERVER['HTTP_X_FORWARDED_FOR'])[0])
        : ($_SERVER['REMOTE_ADDR'] ?? ''));
$ip = substr((string)$ip, 0, 45);

$clickid = bin2hex(random_bytes(8));

$country = strtoupper(substr(preg_replace('~[^A-Za-z]~', '', $_SERVER['HTTP_CF_IPCOUNTRY'] ?? ''), 0, 2));

$referer = substr($_SERVER['HTTP_REFERER'] ?? '', 0, 255);

// лёгкое определение бота по UA (простая проверка подстрок, без БД).
$isBot = 0;
if ($ua === '') {
    $isBot = 1;
} else {
    $ual = strtolower($ua);
    foreach (['bot','crawl','spider','slurp','curl','wget','python','java/','go-http','okhttp','headless','phantom','scrapy','facebookexternalhit','preview'] as $sig) {
        if (strpos($ual, $sig) !== false) { $isBot = 1; break; }
    }
}

// ---------- 3. Пишем клик строкой в лог-файл (атомарно, без БД) ----------
if (($cfg['db_write'] ?? true) !== false) {
    $clean = function($v) {
        return str_replace(["\t", "\r", "\n"], [' ', ' ', ' '], (string)$v);
    };
    $line = implode("\t", [
        time(),
        $clean($slug),
        $clean($ip),
        $clean($ua),
        $clean($referer),
        $clean($src),
        $isBot,
        $clickid,
        $clean($country),
    ]) . "\n";

    $logFile = ($cfg['click_log'] ?? (sys_get_temp_dir() . '/sitegrator_clicks.log'));
    @file_put_contents($logFile, $line, FILE_APPEND | LOCK_EX);
}

// ---------- 4. Формируем целевой URL и редиректим ----------
$dest = $offer;
$host = parse_url($dest, PHP_URL_HOST);
$whitelist = $cfg['postback_domains'] ?? [];
$allow = empty($whitelist)
    || ($host && in_array(strtolower($host), array_map('strtolower', $whitelist), true));
if ($host && $allow) {
    $param = $cfg['clickid_param'] ?? 'clickid';
    if (stripos($dest, $param . '=') === false) {
        $sep = (strpos($dest, '?') === false) ? '?' : '&';
        if ($sep === '?' && preg_match('~^https?://[^/?#]+$~', $dest)) $dest .= '/';
        $dest .= $sep . rawurlencode($param) . '=' . rawurlencode($clickid);
    }
}

header('Location: ' . $dest, true, 302);

if (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request();
}
exit;

<?php
/**
 * collect.php — приём клика со стороны воркера Cloudflare.
 *
 * Нужен там, где посетителя нельзя вести через наш домен: воркер на чужом
 * (забаненном) домене редиректит человека сразу на оффер, а клик досылает
 * сюда фоновым запросом. Посетитель этого запроса не ждёт и нашего домена
 * не видит вообще — его знает только воркер, поэтому домен-прокладку не
 * нужно менять при банах: он не светится ни в выдаче, ни у провайдеров.
 *
 * Как и go.php, НЕ ОБРАЩАЕТСЯ К MySQL: дописывает строку в clicks.log тем же
 * форматом из 12 полей, остальное делает крон (import.php). Поэтому приёмник
 * выдерживает любой поток и не может уронить базу.
 *
 * Запрос (POST, application/x-www-form-urlencoded):
 *   t    — секрет (config.php, ключ collect_secret)
 *   l    — слаг кампании
 *   s    — хост-источник (сабдомен дора)
 *   lp   — путь страницы
 *   cid  — clickid, тот же, что ушёл в ссылку оффера
 *   ua, ref, ip, c (страна), h (домен, на который пришёл клик), b (бот 1/0)
 *
 * Ответ: 204 без тела. Воркеру содержимое не нужно, а пустой ответ дешевле.
 */

$cfg = require __DIR__ . '/config.php';

// Секрет обязателен: без него любой желающий мог бы накручивать статистику.
// Пустой секрет в конфиге = приёмник выключен, а не «пускать всех».
$secret = (string)($cfg['collect_secret'] ?? '');
$given  = (string)($_POST['t'] ?? $_GET['t'] ?? '');
if ($secret === '' || !hash_equals($secret, $given)) {
    http_response_code(403);
    exit;
}

$P = $_POST ?: $_GET;

$clean = function ($v) {
    return str_replace(["\t", "\r", "\n"], [' ', ' ', ' '], (string)$v);
};

$slug = substr(preg_replace('~[^\w.\-]~u', '', (string)($P['l'] ?? '')), 0, 64);
if ($slug === '') { http_response_code(400); exit; }

// хост-источник: тем же правилом, что в go.php, иначе одни и те же сабдомены
// попадали бы в статистику в двух написаниях и не склеивались
$src = preg_replace('~^https?://~i', '', trim((string)($P['s'] ?? '')));
if (($slash = strpos($src, '/')) !== false) $src = substr($src, 0, $slash);
$src = preg_replace('~[?#].*$~', '', $src);
$src = preg_replace('~^www\.~i', '', $src);
$src = substr(preg_replace('~[^\w.\-]~u', '', strtolower($src)), 0, 100);

$lp = (string)($P['lp'] ?? '');
if ($lp !== '') {
    if (($q = strpos($lp, '?')) !== false) $lp = substr($lp, 0, $q);
    $lp = preg_replace('~^https?://[^/]+~i', '', $lp);
    if ($lp !== '' && $lp[0] !== '/') $lp = '/' . $lp;
    $lp = substr(preg_replace('~[^\w/.\-]~u', '', $lp), 0, 255);
}

$clickid = substr(preg_replace('~[^a-f0-9]~i', '', (string)($P['cid'] ?? '')), 0, 32);
if ($clickid === '') $clickid = bin2hex(random_bytes(8));

$ua      = substr((string)($P['ua'] ?? ''), 0, 255);
$referer = substr((string)($P['ref'] ?? ''), 0, 1024);
$ip      = substr((string)($P['ip'] ?? ''), 0, 45);
$country = strtoupper(substr(preg_replace('~[^A-Za-z]~', '', (string)($P['c'] ?? '')), 0, 2));
$host    = substr(preg_replace('~[^\w.\-:]~', '', strtolower((string)($P['h'] ?? ''))), 0, 190);
$isBot   = !empty($P['b']) ? 1 : 0;

// Событие всегда direct: преленда в этой схеме нет, посетитель уходит на оффер
// сразу. Отдельный слаг кампании отделит такие клики от остальных.
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
    $clean($lp),
    'direct',
    $clean($host),
]) . "\n";

$logFile = ($cfg['click_log'] ?? (sys_get_temp_dir() . '/sitegrator_clicks.log'));
@file_put_contents($logFile, $line, FILE_APPEND | LOCK_EX);

http_response_code(204);

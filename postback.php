<?php
/**
 * postback.php — приём конверсий от партнёрки (S2S postback).
 * Принимает и GET, и POST. Каждый запрос пишется в сырой лог (панель «Статистика»).
 *
 * Ссылка для кабинета (из панели «Кампании» → «Постбек»):
 *   https://ВАШ_ДОМЕН/postback.php?key=СЕКРЕТ&cnv_id=${clickid}&cnv_status=reg
 */

require __DIR__ . '/db.php';
$cfg = require __DIR__ . '/config.php';

header('Content-Type: text/plain; charset=utf-8');

$ip     = $_SERVER['HTTP_CF_CONNECTING_IP']
    ?? (isset($_SERVER['HTTP_X_FORWARDED_FOR'])
        ? trim(explode(',', $_SERVER['HTTP_X_FORWARDED_FOR'])[0])
        : ($_SERVER['REMOTE_ADDR'] ?? ''));
$ip     = substr((string)$ip, 0, 45);
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
// в лог пишем метод + полный запрос (для POST добавим тело)
$query  = $method . ' ' . ($_SERVER['REQUEST_URI'] ?? '');
if ($method === 'POST' && $_POST) $query .= ' | POST:' . http_build_query($_POST);

// параметры берём и из GET, и из POST
$P = $_REQUEST;

// защита секретом
$secret = (string)($cfg['postback_secret'] ?? '');
if ($secret === '' || !hash_equals($secret, (string)($P['key'] ?? ''))) {
    log_postback($ip, $query, 'forbidden_key');
    http_response_code(403);
    exit('forbidden');
}

$clickid = $P['cnv_id']     ?? $P['clickid'] ?? $P['subid'] ?? '';
$status  = $P['cnv_status'] ?? $P['status']  ?? $P['goal']  ?? 'conv';
$payout  = $P['payout']     ?? $P['sum']     ?? $P['amount'] ?? 0;

if ($clickid === '') {
    log_postback($ip, $query, 'no_cnv_id');
    http_response_code(400);
    exit('no cnv_id');
}

try {
    $res = record_conversion($clickid, $status, $payout, $ip);
    log_postback($ip, $query, $res['found'] ? 'matched' : 'unmatched');
} catch (Throwable $e) {
    log_postback($ip, $query, 'error');
    http_response_code(500);
    exit('error');
}

echo 'OK';

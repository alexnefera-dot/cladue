<?php
/**
 * health.php — точка для внешнего мониторинга (UptimeRobot, Ping-Admin, HostTracker и т.п.).
 *
 * Отдаёт 200 OK + "OK", если PHP и база живы. Если база недоступна — 503.
 * НЕ пишет клик в статистику и НЕ редиректит — вешать монитор сюда:
 *     https://sitegrator.com/health.php
 * Ожидаемый код ответа в мониторе: 200.
 *
 * Лёгкий: одна проверка БД. Под Cloudflare rate-limit не попадает (1 запрос раз в 5 мин).
 */

require __DIR__ . '/db.php';

header('Content-Type: text/plain; charset=utf-8');
header('Cache-Control: no-store');

try {
    // лёгкая проверка, что база реально открывается и отвечает (только чтение,
    // никакой записи — чтобы под блокировкой базы монитор не вис вместе с ней)
    db()->query('SELECT 1')->fetchColumn();
    http_response_code(200);
    echo 'OK';
} catch (Throwable $e) {
    // база/диск недоступны — сигналим монитору простой
    http_response_code(503);
    echo 'DB_FAIL';
}

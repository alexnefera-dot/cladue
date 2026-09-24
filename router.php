<?php
/**
 * router.php — роутер для встроенного сервера PHP (локальное тестирование).
 *
 * Встроенный сервер (php -S) не читает .htaccess, поэтому правило
 * /go/СЛАГ -> /go.php?l=СЛАГ приходится повторить здесь. На боевом сервере
 * этот файл не нужен и не используется — там работает .htaccess (Apache).
 *
 * Запуск:  php -S localhost:8000 router.php
 */

$uri  = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$path = __DIR__ . $uri;

// /go/СЛАГ -> go.php (как RewriteRule в .htaccess)
if (preg_match('~^/go/([A-Za-z0-9_-]+)/?$~', $uri, $m)) {
    $_GET['l'] = $m[1];
    $_REQUEST['l'] = $m[1];
    require __DIR__ . '/go.php';
    return true;
}

// /v1/clicks, /v1/conversions -> api.php (как RewriteRule в .htaccess)
if (preg_match('~^/v1/(clicks|conversions)/?$~', $uri, $m)) {
    $_GET['ep'] = $m[1];
    require __DIR__ . '/api.php';
    return true;
}

// /p/СЛАГ -> собранная страница преленда (как RewriteRule в .htaccess)
if (preg_match('~^/p/([A-Za-z0-9_.-]+)/?$~', $uri, $m)) {
    $f = __DIR__ . '/prelanders/out/' . $m[1] . '.html';
    if (is_file($f)) { header('Content-Type: text/html; charset=utf-8'); readfile($f); return true; }
    http_response_code(404); echo 'Not found'; return true;
}

// данные наружу не отдаём (в Apache это делает .htaccess)
if (preg_match('~\.(cache|log|sqlite)$~', $uri)) {
    http_response_code(403);
    echo 'Forbidden';
    return true;
}

// существующие файлы отдаём как есть
if ($uri !== '/' && is_file($path)) return false;

// корень -> index.php
require __DIR__ . '/index.php';
return true;

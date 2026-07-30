<?php
/**
 * index.php — заглушка для корня sitegrator.com.
 * Сайт — это редиректор (рабочее на /go/..., /stats.php, /postback.php),
 * на главной показывать нечего. Отдаём пустую 404, чтобы:
 *  - не светить структуру файлов,
 *  - не сорить в error_log ошибками "No matching DirectoryIndex",
 *  - боты/сканеры не получали полезного ответа.
 */

http_response_code(404);
header('Content-Type: text/html; charset=utf-8');
?><!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="robots" content="noindex,nofollow">
<title>404 Not Found</title>
<style>
  html,body{height:100%;margin:0}
  body{display:flex;align-items:center;justify-content:center;
       font:15px system-ui,sans-serif;color:#666;background:#fff}
</style></head>
<body>404 Not Found</body></html>

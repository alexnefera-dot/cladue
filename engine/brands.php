<?php
declare(strict_types=1);

/** Список брендов из базы — для подсказок (datalist) в форме шаблона. */
require_once __DIR__ . '/src/BrandBase.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

$base = new BrandBase();
$brands = array_map(
    fn($b) => ['name' => $b['name'], 'clicks' => $b['total_clicks'] ?? 0, 'queries' => $b['query_count'] ?? 0],
    $base->index()
);
echo json_encode($brands, JSON_UNESCAPED_UNICODE);

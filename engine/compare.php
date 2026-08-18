<?php
declare(strict_types=1);

/**
 * HTTP-эндпоинт сравнения двух наборов страниц (твой vs конкурент).
 * Поля формы: для набора A — a_name_i / a_brand_i / a_content_i / a_file_i,
 *             для набора B — b_name_i / b_brand_i / b_content_i / b_file_i.
 * Плюс: domain.
 */

require_once __DIR__ . '/src/Comparator.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

/** собрать набор страниц по префиксу (a_ / b_) */
function buildSet(string $prefix): array
{
    $pages = [];
    for ($i = 1; $i <= 7; $i++) {
        $name    = trim((string) ($_POST["{$prefix}name_{$i}"] ?? ''));
        $brand   = trim((string) ($_POST["{$prefix}brand_{$i}"] ?? ''));
        $content = (string) ($_POST["{$prefix}content_{$i}"] ?? '');

        $filePath = null; $fileName = null;
        $fk = "{$prefix}file_{$i}";
        if (!empty($_FILES[$fk]['tmp_name']) && is_uploaded_file($_FILES[$fk]['tmp_name'])) {
            $filePath = $_FILES[$fk]['tmp_name'];
            $fileName = $_FILES[$fk]['name'] ?? null;
        }
        if ($filePath === null && trim($content) === '') { continue; }

        $url = $name !== '' ? $name : ($fileName ?? "page-{$i}.html");
        $pages[] = [
            'name'     => $name !== '' ? $name : ($fileName ?? "Страница {$i}"),
            'url'      => $url,
            'file'     => $filePath,
            'filename' => $fileName,
            'html'     => $filePath === null ? $content : null,
            'brand'    => $brand,
        ];
    }
    return $pages;
}

try {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        throw new RuntimeException('Ожидается POST-запрос от формы сравнения.');
    }

    $domain = trim((string) ($_POST['domain'] ?? ''));
    $setA = buildSet('a_');
    $setB = buildSet('b_');

    if (!$setA || !$setB) {
        throw new RuntimeException('Нужно передать оба набора: и твои страницы (A), и конкурента (B).');
    }

    $comparator = new Comparator($domain);
    $result = $comparator->compare($setA, $setB);

    echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
} catch (Throwable $e) {
    http_response_code(400);
    echo json_encode(['error' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
}

<?php
declare(strict_types=1);

/**
 * HTTP-эндпоинт: принимает POST от формы шаблона (template/index.html),
 * запускает анализ и возвращает JSON в формате, который рендерит app.js.
 *
 * Поля формы (на каждую из 7 страниц i): name_i, keyword_i, lsi_i,
 * content_i (вставленный HTML/текст), file_i (загруженный HTML/DOCX).
 * Плюс: domain.
 */

require_once __DIR__ . '/src/Analyzer.php';

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

try {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
        throw new RuntimeException('Ожидается POST-запрос от формы анализа.');
    }

    $domain = trim((string) ($_POST['domain'] ?? ''));
    $pages = [];

    for ($i = 1; $i <= 7; $i++) {
        $name    = trim((string) ($_POST["name_{$i}"] ?? ''));
        $keyword = trim((string) ($_POST["keyword_{$i}"] ?? ''));
        $lsiRaw  = trim((string) ($_POST["lsi_{$i}"] ?? ''));
        $content = (string) ($_POST["content_{$i}"] ?? '');

        $filePath = null; $fileName = null;
        if (!empty($_FILES["file_{$i}"]['tmp_name']) && is_uploaded_file($_FILES["file_{$i}"]['tmp_name'])) {
            $filePath = $_FILES["file_{$i}"]['tmp_name'];
            $fileName = $_FILES["file_{$i}"]['name'] ?? null;
        }

        // страница считается заполненной, если есть файл или контент
        if ($filePath === null && trim($content) === '') { continue; }

        $lsi = array_values(array_filter(array_map('trim', explode(',', $lsiRaw)), fn($s) => $s !== ''));

        // url используется для резолва перелинковки: берём имя (файл/URL), затем имя загруженного файла
        $url = $name !== '' ? $name : ($fileName ?? "page-{$i}.html");

        $pages[] = [
            'name'     => $name !== '' ? $name : ($fileName ?? "Страница {$i}"),
            'url'      => $url,
            'file'     => $filePath,
            'filename' => $fileName,
            'html'     => $filePath === null ? $content : null,
            'keyword'  => $keyword,
            'lsi'      => $lsi,
        ];
    }

    if (!$pages) {
        throw new RuntimeException('Не передано ни одной страницы с контентом.');
    }

    $analyzer = new Analyzer($domain);
    $result = $analyzer->run($pages);

    echo json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
} catch (Throwable $e) {
    http_response_code(400);
    echo json_encode(['error' => $e->getMessage()], JSON_UNESCAPED_UNICODE);
}

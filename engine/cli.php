<?php
declare(strict_types=1);

/**
 * CLI-запуск анализа по папке с файлами (HTML/DOCX/текст).
 *
 * Использование:
 *   php cli.php <папка> [--domain=example.ru] [--keywords=keywords.json] [--out=report.json]
 *
 * keywords.json (опционально) — сопоставление имени файла ключам/LSI:
 *   { "index.html": { "keyword": "купить окна", "lsi": ["пластиковые","монтаж"] }, ... }
 *
 * Берутся первые 7 файлов папки (в алфавитном порядке).
 */

require_once __DIR__ . '/src/Analyzer.php';

$args = array_slice($argv, 1);
$opts = ['domain' => '', 'keywords' => '', 'out' => ''];
$dir = '';
foreach ($args as $a) {
    if (str_starts_with($a, '--')) {
        [$k, $v] = array_pad(explode('=', substr($a, 2), 2), 2, '');
        if (array_key_exists($k, $opts)) { $opts[$k] = $v; }
    } elseif ($dir === '') {
        $dir = $a;
    }
}

if ($dir === '' || !is_dir($dir)) {
    fwrite(STDERR, "Укажите папку с файлами страниц.\n");
    fwrite(STDERR, "Пример: php cli.php ./pages --domain=example.ru --out=report.json\n");
    exit(1);
}

$keywords = [];
if ($opts['keywords'] !== '' && is_file($opts['keywords'])) {
    $keywords = json_decode((string) file_get_contents($opts['keywords']), true) ?: [];
}

$files = array_values(array_filter(scandir($dir) ?: [], function ($f) use ($dir) {
    if ($f === '.' || $f === '..') { return false; }
    $ext = strtolower(pathinfo($f, PATHINFO_EXTENSION));
    return in_array($ext, ['html', 'htm', 'docx', 'doc', 'txt'], true) && is_file("{$dir}/{$f}");
}));
sort($files);
$files = array_slice($files, 0, 7);

if (!$files) {
    fwrite(STDERR, "В папке нет подходящих файлов (html/htm/docx/doc/txt).\n");
    exit(1);
}

$pages = [];
foreach ($files as $f) {
    $meta = $keywords[$f] ?? [];
    $pages[] = [
        'name'     => $f,
        'url'      => $f,
        'file'     => "{$dir}/{$f}",
        'filename' => $f,
        'keyword'  => (string) ($meta['keyword'] ?? ''),
        'lsi'      => (array) ($meta['lsi'] ?? []),
    ];
}

$analyzer = new Analyzer($opts['domain']);
$result = $analyzer->run($pages);

$json = json_encode($result, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
if ($opts['out'] !== '') {
    file_put_contents($opts['out'], $json);
    fwrite(STDERR, "Готово: {$opts['out']} (" . count($result['pages']) . " страниц)\n");
    // краткая сводка проекта в stderr
    $p = $result['project'];
    fwrite(STDERR, sprintf(
        "Проект: сироты=%d, тупики=%d, уникальность=%d%%, глубина=%d\n",
        $p['orphan_pages'], $p['dead_end_pages'], $p['internal_uniqueness'], $p['max_link_depth']
    ));
} else {
    echo $json, "\n";
}

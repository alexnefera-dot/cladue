<?php

declare(strict_types=1);

/*
 * Проверка синтаксиса всех PHP-файлов проекта: php tests/lint.php
 */

$root = dirname(__DIR__);
$dirs = ['bin', 'src', 'tests'];
$files = [$root . '/config.example.php'];
foreach ($dirs as $dir) {
    $iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/' . $dir));
    foreach ($iterator as $file) {
        if ($file->isFile() && $file->getExtension() === 'php') {
            $files[] = $file->getPathname();
        }
    }
}

$failed = 0;
foreach ($files as $file) {
    if (!is_file($file)) {
        continue;
    }
    exec(sprintf('%s -l %s 2>&1', escapeshellarg(PHP_BINARY), escapeshellarg($file)), $output, $code);
    if ($code !== 0) {
        $failed++;
        echo implode(PHP_EOL, $output) . PHP_EOL;
    }
    $output = [];
}

echo $failed === 0 ? 'Синтаксис в порядке: ' . count($files) . ' файлов' . PHP_EOL : "Файлов с ошибками: $failed" . PHP_EOL;
exit($failed === 0 ? 0 : 1);

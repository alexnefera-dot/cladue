#!/usr/bin/env php
<?php

declare(strict_types=1);

/*
 * Подготовка контента: из скачанных страниц (out/pages) делает шаблоны статей —
 * оставляет тело статьи, приводит ссылки к 6 путям, подставляет %domain_name% / %date% /
 * %brand_name_ru% / %brand_name_en%. Результат — в out/content и (по желанию) в zip-архив.
 *
 *   php bin/clean-content.php [--in=out/pages] [--out=out/content] [--zip=out/content.zip]
 *                             [--brand-ru=криптобосс] [--brand-en=cryptoboss] [--brands=STAKE,другой]
 *                             [--keep-slots]
 *
 * Домен берётся автоматически из имени папки сайта; --brand-en по умолчанию — из домена.
 */

error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);

$root = dirname(__DIR__);
if (is_file($root . '/vendor/autoload.php')) {
    require $root . '/vendor/autoload.php';
} else {
    spl_autoload_register(static function (string $class) use ($root): void {
        $prefix = 'YandexSites\\';
        if (str_starts_with($class, $prefix)) {
            $file = $root . '/src/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
            if (is_file($file)) {
                require $file;
            }
        }
    });
}

use YandexSites\Content\ContentCleaner;

$opts = [
    'in' => getcwd() . '/out/pages',
    'out' => getcwd() . '/out/content',
    'zip' => '',
    'brand_ru' => '',
    'brand_en' => '',
    'brands' => [],
    'remove_slots' => true,
];
foreach (array_slice($argv, 1) as $arg) {
    if (str_starts_with($arg, '--in=')) {
        $opts['in'] = substr($arg, 5);
    } elseif (str_starts_with($arg, '--out=')) {
        $opts['out'] = substr($arg, 6);
    } elseif (str_starts_with($arg, '--zip=')) {
        $opts['zip'] = substr($arg, 6);
    } elseif (str_starts_with($arg, '--brand-ru=')) {
        $opts['brand_ru'] = substr($arg, 11);
    } elseif (str_starts_with($arg, '--brand-en=')) {
        $opts['brand_en'] = substr($arg, 11);
    } elseif (str_starts_with($arg, '--brands=')) {
        $opts['brands'] = array_values(array_filter(array_map('trim', explode(',', substr($arg, 9)))));
    } elseif ($arg === '--keep-slots') {
        $opts['remove_slots'] = false;
    } elseif ($arg === '--help' || $arg === '-h') {
        fwrite(STDOUT, "php bin/clean-content.php [--in=out/pages] [--out=out/content] [--zip=out/content.zip] [--brand-ru=…] [--brand-en=…] [--brands=a,b] [--keep-slots]\n");
        exit(0);
    }
}

/**
 * @return list<string> все .html под каталогом
 */
function htmlFiles(string $dir): array
{
    if (!is_dir($dir)) {
        return [];
    }
    $files = [];
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS));
    foreach ($it as $file) {
        if ($file instanceof SplFileInfo && $file->isFile() && strtolower($file->getExtension()) === 'html') {
            $files[] = $file->getPathname();
        }
    }
    sort($files);

    return $files;
}

$cleaner = new ContentCleaner();
$inDir = rtrim($opts['in'], '/\\');
$outDir = rtrim($opts['out'], '/\\');
$files = htmlFiles($inDir);
if ($files === []) {
    fwrite(STDERR, "Не найдено .html в $inDir (сначала выполните этап выгрузки страниц).\n");
    exit(1);
}

$written = 0;
$skipped = 0;
foreach ($files as $file) {
    // Домен сайта — имя папки-сайта (родитель файла), например out/pages/7-стр/<host>/page.html
    $host = basename(dirname($file));
    if ($host === '' || !str_contains($host, '.')) {
        $host = '';
    }
    $html = (string) file_get_contents($file);
    // Бренд определяется автоматически по странице и домену; флаги CLI (если заданы) перекрывают.
    $body = $cleaner->clean($html, ContentCleaner::autoOptions($html, $host, [
        'brand_ru' => $opts['brand_ru'],
        'brand_en' => $opts['brand_en'],
        'extra_brands' => $opts['brands'],
        'remove_slots' => $opts['remove_slots'],
    ]));

    if (trim($body) === '') {
        $skipped++;
        fwrite(STDOUT, sprintf("  — %s: пропущено (нет статьи с <h1>)\n", ltrim(str_replace($inDir, '', $file), '/\\')));
        continue;
    }

    $rel = ltrim(str_replace($inDir, '', $file), '/\\');
    $dest = $outDir . '/' . $rel;
    @mkdir(dirname($dest), 0777, true);
    file_put_contents($dest, $body);
    $written++;
    fwrite(STDOUT, sprintf("  ✓ %s\n", $rel));
}

fwrite(STDOUT, sprintf("Готово: подготовлено %d, пропущено %d. Каталог: %s\n", $written, $skipped, $outDir));

if ($opts['zip'] !== '' && $written > 0) {
    if (!class_exists('ZipArchive')) {
        fwrite(STDERR, "Расширение zip не установлено — архив не создан (файлы в $outDir).\n");
        exit(0);
    }
    $zip = new ZipArchive();
    $zipPath = $opts['zip'];
    @mkdir(dirname($zipPath), 0777, true);
    if ($zip->open($zipPath, ZipArchive::CREATE | ZipArchive::OVERWRITE) === true) {
        foreach (htmlFiles($outDir) as $f) {
            $zip->addFile($f, ltrim(str_replace($outDir, '', $f), '/\\'));
        }
        $zip->close();
        fwrite(STDOUT, "Архив: $zipPath\n");
    } else {
        fwrite(STDERR, "Не удалось создать архив $zipPath\n");
    }
}

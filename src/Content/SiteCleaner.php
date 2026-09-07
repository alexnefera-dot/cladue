<?php

declare(strict_types=1);

namespace YandexSites\Content;

/**
 * Очистка страниц ОДНОГО сайта в шаблоны статей — общая логика кнопок «Очистить»/«Очистить всё»
 * панели (bin/panel.php) и фонового задания stage=clean (bin/run-job.php), чтобы они не расходились:
 * бренд определяется по ВСЕМ страницам сайта (главная бывает заглушкой), результат раскладывается в
 * content/<N>-стр/<host>/ (N — число очищенных страниц), прежняя версия сайта из любого бакета убирается.
 */
final class SiteCleaner
{
    /**
     * Скачанные .html-страницы, сгруппированные по сайту (имя папки-сайта; папки любого бакета pages/N-стр/).
     *
     * @return array<string, list<string>>
     */
    public static function pagesByHost(string $pagesDir): array
    {
        $byHost = [];
        if (is_dir($pagesDir)) {
            $iter = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($pagesDir, \FilesystemIterator::SKIP_DOTS));
            foreach ($iter as $f) {
                if ($f instanceof \SplFileInfo && $f->isFile() && strtolower($f->getExtension()) === 'html') {
                    $host = basename(dirname($f->getPathname()));
                    if (str_contains($host, '.')) {
                        $byHost[$host][] = $f->getPathname();
                    }
                }
            }
        }
        ksort($byHost);

        return $byHost;
    }

    /**
     * Чистит страницы сайта и раскладывает очищенные статьи в бакет по числу страниц:
     * <runDir>/content/<N>-стр/<host>/. Ничего не скачивает. $override — ручные brand_ru/brand_en/extra_brands
     * (непустые перекрывают автоопределение).
     *
     * @param list<string> $files
     * @param array<string, mixed> $override
     * @return array{written: int, skipped: int, dir: string, brand_ru: string, brand_en: string}
     */
    public static function cleanHost(string $runDir, string $host, array $files, array $override = []): array
    {
        sort($files);
        $html = [];
        foreach ($files as $f) {
            $html[$f] = (string) file_get_contents($f);
        }
        $home = $files[0] ?? '';
        foreach ($files as $f) {
            if (basename($f) === 'main.html') {
                $home = $f;
                break;
            }
        }
        // Бренд ищем по ВСЕМ страницам сайта, а не только по главной: если главная оказалась заглушкой
        // или редиректом, бренд и canonical есть на внутренних страницах.
        $moreHtml = [];
        foreach ($files as $f) {
            if ($f !== $home) {
                $moreHtml[] = $html[$f];
            }
        }
        $opts = ContentCleaner::autoOptions($home !== '' ? ($html[$home] ?? '') : '', $host, $override, $moreHtml);
        $cleaner = new ContentCleaner();
        // Чистим в память, чтобы узнать итоговое число страниц и назвать по нему папку-бакет.
        $cleaned = [];
        $skipped = 0;
        foreach ($files as $file) {
            $body = $cleaner->clean($html[$file], $opts);
            if (trim($body) === '') {
                $skipped++;
                continue;
            }
            $cleaned[basename($file)] = $body;
        }
        $written = count($cleaned);
        // Прежние очищенные версии этого сайта убираем из любого бакета, чтобы не осталось дублей.
        self::removeHostContent($runDir, $host);
        $rel = 'content/' . $written . '-стр/' . $host;
        if ($written > 0) {
            $outDir = $runDir . '/' . $rel;
            @mkdir($outDir, 0777, true);
            foreach ($cleaned as $name => $body) {
                file_put_contents($outDir . '/' . $name, $body);
            }
        }

        return [
            'written' => $written,
            'skipped' => $skipped,
            'dir' => $rel,
            'brand_ru' => (string) ($opts['brand_ru'] ?? ''),
            'brand_en' => (string) ($opts['brand_en'] ?? ''),
        ];
    }

    /**
     * Удаляет прежние очищенные страницы сайта из всех бакетов content/<N>-стр/<host>
     * (и старой плоской папки content/<host>), чтобы повторная очистка не плодила дубли.
     */
    public static function removeHostContent(string $runDir, string $host): void
    {
        $dirs = array_merge(
            glob($runDir . '/content/*/' . $host, GLOB_ONLYDIR) ?: [],
            glob($runDir . '/content/' . $host, GLOB_ONLYDIR) ?: [],
        );
        foreach ($dirs as $dir) {
            foreach (glob($dir . '/*') ?: [] as $f) {
                @unlink($f);
            }
            @rmdir($dir);
            @rmdir(dirname($dir)); // пустой бакет убираем тоже
        }
    }

    /** Рекурсивно удаляет папку со всем содержимым (чистый пере-сбор «Очистить всё»). */
    public static function rmTree(string $dir): void
    {
        if (!is_dir($dir)) {
            return;
        }
        $it = new \RecursiveIteratorIterator(
            new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS),
            \RecursiveIteratorIterator::CHILD_FIRST,
        );
        foreach ($it as $f) {
            if ($f instanceof \SplFileInfo) {
                $f->isDir() ? @rmdir($f->getPathname()) : @unlink($f->getPathname());
            }
        }
        @rmdir($dir);
    }
}

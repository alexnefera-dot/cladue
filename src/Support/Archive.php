<?php

declare(strict_types=1);

namespace YandexSites\Support;

use RuntimeException;
use ZipArchive;

/**
 * Zip-архив папки — кнопка «Скачать архив контента» в панели. PHP-расширение zip есть не везде
 * (в Windows-сборке оно выключено по умолчанию), поэтому запасной путь — системный tar: bsdtar
 * (Windows 10+, macOS) умеет писать zip по расширению файла (-a); GNU tar в Linux так не умеет, тогда
 * архив не появится и будет понятная ошибка. Пути внутри архива — относительно папки, с прямыми слэшами.
 */
final class Archive
{
    /**
     * Упаковывает содержимое папки $dir в $zipFile (старый архив перезаписывается). Возвращает число файлов.
     *
     * @throws RuntimeException папка пуста или архив создать нечем
     */
    public static function zipDir(string $dir, string $zipFile, bool $forceTar = false): int
    {
        $files = self::listFiles($dir);
        if ($files === []) {
            throw new RuntimeException('Папка пуста — архивировать нечего: ' . $dir);
        }
        @mkdir(dirname($zipFile), 0777, true);
        @unlink($zipFile);
        if (!$forceTar && class_exists(ZipArchive::class)) {
            $zip = new ZipArchive();
            if ($zip->open($zipFile, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
                throw new RuntimeException('Не удалось создать архив ' . $zipFile);
            }
            foreach ($files as $rel => $abs) {
                $zip->addFile($abs, $rel);
            }
            $zip->close();
        } else {
            self::zipWithTar($dir, $zipFile);
        }
        if (!self::isZip($zipFile)) {
            @unlink($zipFile);
            throw new RuntimeException('Архив не создан: в PHP нет расширения zip, а системный tar не умеет zip. Включите extension=zip в php.ini');
        }

        return count($files);
    }

    /**
     * Файлы папки (рекурсивно): относительный путь с «/» => абсолютный путь, по алфавиту.
     *
     * @return array<string, string>
     */
    public static function listFiles(string $dir): array
    {
        if (!is_dir($dir)) {
            return [];
        }
        $out = [];
        $prefix = rtrim($dir, '/\\') . DIRECTORY_SEPARATOR;
        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS));
        foreach ($it as $file) {
            if ($file->isFile()) {
                $out[str_replace('\\', '/', substr($file->getPathname(), strlen($prefix)))] = $file->getPathname();
            }
        }
        ksort($out);

        return $out;
    }

    /** Файл существует и начинается с сигнатуры zip («PK»). */
    public static function isZip(string $file): bool
    {
        return is_file($file) && (int) filesize($file) >= 4 && (string) file_get_contents($file, false, null, 0, 2) === 'PK';
    }

    /** bsdtar: формат по расширению (-a), в архив кладём элементы верхнего уровня папки, без «./» в путях. */
    private static function zipWithTar(string $dir, string $zipFile): void
    {
        $top = array_values(array_diff(scandir($dir) ?: [], ['.', '..']));
        if ($top === []) {
            return;
        }
        $process = @proc_open(
            array_merge(['tar', '-a', '-cf', $zipFile, '-C', $dir], $top),
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
        );
        if (!is_resource($process)) {
            return;
        }
        fclose($pipes[0]);
        stream_get_contents($pipes[1]);
        stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);
        proc_close($process);
    }
}

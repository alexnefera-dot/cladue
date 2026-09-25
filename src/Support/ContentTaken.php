<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * Учёт уже ЗАБРАННОГО контента: какие очищенные статьи пользователь уже скачал архивом.
 *
 * Выгрузка идёт волнами, и после каждой волны в content/ появляются новые статьи. Скачивать каждый
 * раз весь контент заново неудобно — «в новый архив вторую волну добавляй уже без первой части».
 * Поэтому храним отметку по каждому файлу: путь внутри content/ → sha1 его содержимого на момент,
 * когда файл уехал в архив. «Новое» = файла в отметках нет ИЛИ он с тех пор изменился.
 *
 * Сравниваем именно по содержимому, а не по времени файла: «Очистить всё» перечищает страницы
 * заново, время меняется у всех, а текст статьи — тот же, и весь архив снова считался бы новым.
 */
final class ContentTaken
{
    public const FILE = 'content-taken.json';

    /**
     * @return array{wave: int, files: array<string, string>}
     */
    public static function load(string $runDir): array
    {
        $data = @json_decode((string) @file_get_contents(self::path($runDir)), true);
        if (!is_array($data)) {
            return ['wave' => 0, 'files' => []];
        }
        $files = [];
        foreach ((array) ($data['files'] ?? []) as $rel => $hash) {
            $rel = trim((string) $rel);
            if ($rel !== '') {
                $files[$rel] = (string) $hash;
            }
        }

        return ['wave' => max(0, (int) ($data['wave'] ?? 0)), 'files' => $files];
    }

    /**
     * Файлы content/, которых пользователь ещё не забирал (или которые изменились после этого).
     *
     * @return array<string, string> путь внутри content/ => абсолютный путь
     */
    public static function newFiles(string $runDir, string $contentDir): array
    {
        $taken = self::load($runDir)['files'];
        $out = [];
        foreach (Archive::listFiles($contentDir) as $rel => $abs) {
            if (!isset($taken[$rel]) || $taken[$rel] !== self::hash($abs)) {
                $out[$rel] = $abs;
            }
        }

        return $out;
    }

    /**
     * Сколько страниц и сайтов в наборе файлов (сайт — папка, в которой лежит статья).
     *
     * @param array<string, string> $files путь внутри content/ => абсолютный путь
     * @return array{files: int, sites: int}
     */
    public static function stats(array $files): array
    {
        $sites = [];
        foreach (array_keys($files) as $rel) {
            $dir = dirname($rel);
            if ($dir !== '' && $dir !== '.') {
                $sites[$dir] = true;
            }
        }

        return ['files' => count($files), 'sites' => count($sites)];
    }

    /**
     * Отмечает файлы забранными и возвращает номер волны, которой они уехали.
     *
     * @param array<string, string> $files путь внутри content/ => абсолютный путь
     */
    public static function markTaken(string $runDir, array $files): int
    {
        $state = self::load($runDir);
        $state['wave']++;
        foreach ($files as $rel => $abs) {
            $state['files'][(string) $rel] = self::hash((string) $abs);
        }
        ksort($state['files']);
        self::save($runDir, $state);

        return $state['wave'];
    }

    /** Отмечает забранным ВЕСЬ контент (кнопка «Скачать всё»): следующая волна — только то, что появится потом. */
    public static function markAll(string $runDir, string $contentDir): int
    {
        return self::markTaken($runDir, Archive::listFiles($contentDir));
    }

    /** Забыть отметки — весь контент снова считается новым. */
    public static function reset(string $runDir): void
    {
        @unlink(self::path($runDir));
    }

    private static function hash(string $file): string
    {
        return is_file($file) ? (string) sha1_file($file) : '';
    }

    private static function path(string $runDir): string
    {
        return rtrim($runDir, '/\\') . '/' . self::FILE;
    }

    /**
     * @param array{wave: int, files: array<string, string>} $state
     */
    private static function save(string $runDir, array $state): void
    {
        $file = self::path($runDir);
        @mkdir(dirname($file), 0777, true);
        $tmp = $file . '.tmp';
        @file_put_contents($tmp, (string) json_encode($state, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        @rename($tmp, $file);
    }
}

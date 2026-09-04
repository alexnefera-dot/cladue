<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * Чтение списка поисковых запросов: по одному в строке, пустые строки
 * и строки, начинающиеся с «#», пропускаются, дубли удаляются.
 */
final class QueryList
{
    /** Максимальная длина запроса, которую принимает Yandex Search API. */
    public const MAX_LENGTH = 400;

    /**
     * @return list<string>
     */
    public static function fromFile(string $path): array
    {
        if (!is_file($path) || !is_readable($path)) {
            throw new \RuntimeException("Файл с запросами не найден или недоступен: $path");
        }
        $lines = file($path, FILE_IGNORE_NEW_LINES);
        if ($lines === false) {
            throw new \RuntimeException("Не удалось прочитать файл: $path");
        }

        return self::fromLines($lines);
    }

    /**
     * @param iterable<string> $lines
     * @return list<string>
     */
    public static function fromLines(iterable $lines): array
    {
        $result = [];
        $seen = [];
        foreach ($lines as $line) {
            $line = trim(str_replace("\xEF\xBB\xBF", '', (string) $line));
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            $line = preg_replace('/\s+/u', ' ', $line) ?? $line;
            $key = mb_strtolower($line);
            if (isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $result[] = $line;
        }

        return $result;
    }

    /**
     * Объединяет несколько списков, сохраняя порядок и убирая дубли.
     *
     * @param list<string> ...$lists
     * @return list<string>
     */
    public static function merge(array ...$lists): array
    {
        $all = [];
        foreach ($lists as $list) {
            foreach ($list as $query) {
                $all[] = $query;
            }
        }

        return self::fromLines($all);
    }
}

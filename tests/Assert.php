<?php

declare(strict_types=1);

namespace Tests;

final class AssertionFailed extends \Exception
{
}

final class SkipTest extends \Exception
{
}

final class Assert
{
    public static function same(mixed $expected, mixed $actual, string $message = ''): void
    {
        if ($expected !== $actual) {
            self::fail(sprintf('%sожидалось %s, получено %s', $message !== '' ? $message . ': ' : '', self::dump($expected), self::dump($actual)));
        }
    }

    public static function true(mixed $value, string $message = ''): void
    {
        if ($value !== true) {
            self::fail(($message !== '' ? $message . ': ' : '') . 'ожидалось true, получено ' . self::dump($value));
        }
    }

    public static function false(mixed $value, string $message = ''): void
    {
        if ($value !== false) {
            self::fail(($message !== '' ? $message . ': ' : '') . 'ожидалось false, получено ' . self::dump($value));
        }
    }

    public static function null(mixed $value, string $message = ''): void
    {
        if ($value !== null) {
            self::fail(($message !== '' ? $message . ': ' : '') . 'ожидалось null, получено ' . self::dump($value));
        }
    }

    public static function contains(string $needle, string $haystack, string $message = ''): void
    {
        if (!str_contains($haystack, $needle)) {
            self::fail(sprintf('%sстрока не содержит %s: %s', $message !== '' ? $message . ': ' : '', self::dump($needle), self::dump(mb_substr($haystack, 0, 300))));
        }
    }

    public static function notContains(string $needle, string $haystack, string $message = ''): void
    {
        if (str_contains($haystack, $needle)) {
            self::fail(sprintf('%sстрока содержит %s', $message !== '' ? $message . ': ' : '', self::dump($needle)));
        }
    }

    /**
     * @param array<mixed> $array
     */
    public static function inArray(mixed $needle, array $array, string $message = ''): void
    {
        if (!in_array($needle, $array, true)) {
            self::fail(sprintf('%s%s отсутствует в %s', $message !== '' ? $message . ': ' : '', self::dump($needle), self::dump($array)));
        }
    }

    /**
     * @param array<mixed> $array
     */
    public static function notInArray(mixed $needle, array $array, string $message = ''): void
    {
        if (in_array($needle, $array, true)) {
            self::fail(sprintf('%s%s присутствует в %s', $message !== '' ? $message . ': ' : '', self::dump($needle), self::dump($array)));
        }
    }

    /**
     * @param class-string<\Throwable> $class
     */
    public static function throws(string $class, callable $fn, string $messagePart = ''): \Throwable
    {
        try {
            $fn();
        } catch (\Throwable $e) {
            if (!$e instanceof $class) {
                self::fail(sprintf('ожидалось исключение %s, получено %s: %s', $class, $e::class, $e->getMessage()));
            }
            if ($messagePart !== '' && !str_contains($e->getMessage(), $messagePart)) {
                self::fail(sprintf('сообщение исключения не содержит %s: %s', self::dump($messagePart), $e->getMessage()));
            }

            return $e;
        }
        self::fail("ожидалось исключение $class, но оно не было выброшено");
    }

    public static function fail(string $message): never
    {
        throw new AssertionFailed($message);
    }

    public static function skip(string $reason): never
    {
        throw new SkipTest($reason);
    }

    private static function dump(mixed $value): string
    {
        return json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?: var_export($value, true);
    }
}

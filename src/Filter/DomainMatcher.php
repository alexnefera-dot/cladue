<?php

declare(strict_types=1);

namespace YandexSites\Filter;

/**
 * Проверка хоста по списку шаблонов.
 *
 * Поддерживаемые шаблоны:
 *  - `example.ru`     — сам домен и все его поддомены;
 *  - `*.example.ru`   — только поддомены;
 *  - `=example.ru`    — точное совпадение;
 *  - `/regex/i`, `~regex~` — регулярное выражение по хосту.
 */
final class DomainMatcher
{
    /** @var list<array{0: string, 1: string}> */
    private array $rules = [];

    /**
     * @param iterable<mixed> $patterns
     */
    public function __construct(iterable $patterns = [])
    {
        foreach ($patterns as $pattern) {
            if (!is_string($pattern)) {
                continue;
            }
            $pattern = trim($pattern);
            if ($pattern === '' || str_starts_with($pattern, '#')) {
                continue;
            }
            $this->rules[] = self::compile($pattern);
        }
    }

    /**
     * @return array{0: string, 1: string}
     */
    public static function compile(string $pattern): array
    {
        if (preg_match('@^([/~%]).+\1[a-zA-Z]*$@s', $pattern) === 1) {
            if (@preg_match($pattern, '') === false) {
                throw new \InvalidArgumentException("Некорректное регулярное выражение для домена: $pattern");
            }

            return ['regex', $pattern];
        }
        if (str_starts_with($pattern, '=')) {
            return ['exact', self::norm(substr($pattern, 1))];
        }
        if (str_starts_with($pattern, '*.')) {
            return ['subdomains', self::norm(substr($pattern, 2))];
        }

        return ['domain', self::norm($pattern)];
    }

    public function isEmpty(): bool
    {
        return $this->rules === [];
    }

    public function count(): int
    {
        return count($this->rules);
    }

    public function matches(string $host): bool
    {
        $host = self::norm($host);
        if ($host === '') {
            return false;
        }
        $unicode = Domains::toUnicode($host);

        foreach ($this->rules as [$type, $value]) {
            switch ($type) {
                case 'regex':
                    if (preg_match($value, $host) === 1 || ($unicode !== $host && preg_match($value, $unicode) === 1)) {
                        return true;
                    }
                    break;
                case 'exact':
                    if ($host === $value) {
                        return true;
                    }
                    break;
                case 'subdomains':
                    if (str_ends_with($host, '.' . $value)) {
                        return true;
                    }
                    break;
                default:
                    if ($host === $value || str_ends_with($host, '.' . $value)) {
                        return true;
                    }
            }
        }

        return false;
    }

    private static function norm(string $host): string
    {
        return Domains::toAscii(Domains::normalize($host, true));
    }
}

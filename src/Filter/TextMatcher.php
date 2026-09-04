<?php

declare(strict_types=1);

namespace YandexSites\Filter;

/**
 * Поиск по тексту: обычная строка ищется как подстрока без учёта регистра,
 * строка в разделителях (`/.../i`, `~...~u`) — как регулярное выражение.
 */
final class TextMatcher
{
    /** @var list<array{0: string, 1: string}> */
    private array $rules = [];

    /**
     * @param iterable<mixed>|string|null $patterns
     */
    public function __construct(iterable|string|null $patterns, private bool $regexOnly = false, string $name = '')
    {
        if ($patterns === null) {
            $patterns = [];
        } elseif (is_string($patterns)) {
            $patterns = [$patterns];
        }
        foreach ($patterns as $pattern) {
            if (!is_string($pattern)) {
                continue;
            }
            $pattern = trim($pattern);
            if ($pattern === '') {
                continue;
            }
            if (self::looksLikeRegex($pattern)) {
                if (@preg_match($pattern, '') === false) {
                    throw new \InvalidArgumentException(($name !== '' ? "$name: " : '') . "некорректное регулярное выражение: $pattern");
                }
                $this->rules[] = ['regex', $pattern];
            } elseif ($this->regexOnly) {
                throw new \InvalidArgumentException(($name !== '' ? "$name: " : '') . "ожидается регулярное выражение в разделителях (например, ~/catalog/~i), получено: $pattern");
            } else {
                $this->rules[] = ['text', mb_strtolower($pattern)];
            }
        }
    }

    public static function looksLikeRegex(string $pattern): bool
    {
        return preg_match('@^([/~%#]).+\1[a-zA-Z]*$@s', $pattern) === 1;
    }

    public function isEmpty(): bool
    {
        return $this->rules === [];
    }

    /** Хотя бы один шаблон найден. */
    public function matchesAny(string $text): bool
    {
        $lower = mb_strtolower($text);
        foreach ($this->rules as $rule) {
            if ($this->matchOne($rule, $text, $lower)) {
                return true;
            }
        }

        return false;
    }

    /** Все шаблоны найдены. */
    public function matchesAll(string $text): bool
    {
        $lower = mb_strtolower($text);
        foreach ($this->rules as $rule) {
            if (!$this->matchOne($rule, $text, $lower)) {
                return false;
            }
        }

        return true;
    }

    /**
     * @param array{0: string, 1: string} $rule
     */
    private function matchOne(array $rule, string $text, string $lower): bool
    {
        if ($rule[0] === 'regex') {
            return @preg_match($rule[1], $text) === 1;
        }

        return mb_strpos($lower, $rule[1]) !== false;
    }
}

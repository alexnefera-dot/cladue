<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Check\Html;

/**
 * Отпечаток видимого текста страницы — чтобы понять, отличаются ли варианты,
 * показанные разным посетителям.
 */
final class Fingerprint
{
    /**
     * @return array{hash: string, length: int, title: string}
     */
    public static function of(string $html): array
    {
        $text = self::text($html);

        return [
            'hash' => md5($text),
            'length' => mb_strlen($text),
            'title' => Html::title($html),
        ];
    }

    /**
     * Видимый текст страницы (без скриптов, стилей и тегов) в нормализованном виде.
     */
    public static function text(string $html): string
    {
        $text = preg_replace('~<(script|style|noscript|template|svg)\b[^>]*>.*?</\1>~isu', ' ', $html) ?? $html;
        $text = preg_replace('~<!--.*?-->~su', ' ', $text) ?? $text;
        $text = strip_tags($text);
        $text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');

        return trim(preg_replace('/\s+/u', ' ', $text) ?? $text);
    }

    /**
     * Похожесть двух текстов (0..1) по множествам слов (мера Жаккара). 1 — идентичны.
     */
    public static function similarity(string $a, string $b): float
    {
        if ($a === $b) {
            return 1.0;
        }
        $wa = self::words($a);
        $wb = self::words($b);
        if ($wa === [] && $wb === []) {
            return 1.0;
        }
        if ($wa === [] || $wb === []) {
            return 0.0;
        }
        $intersection = count(array_intersect_key($wa, $wb));
        $union = count($wa + $wb);

        return $union > 0 ? $intersection / $union : 0.0;
    }

    /**
     * @return array<string, true>
     */
    private static function words(string $text): array
    {
        $set = [];
        foreach (preg_split('~[^\p{L}\p{N}]+~u', mb_strtolower($text), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $word) {
            if (mb_strlen($word) >= 2) {
                $set[$word] = true;
            }
        }

        return $set;
    }
}

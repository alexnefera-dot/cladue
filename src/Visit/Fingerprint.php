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
        $text = preg_replace('~<(script|style|noscript|template|svg)\b[^>]*>.*?</\1>~isu', ' ', $html) ?? $html;
        $text = preg_replace('~<!--.*?-->~su', ' ', $text) ?? $text;
        $text = strip_tags($text);
        $text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = trim(preg_replace('/\s+/u', ' ', $text) ?? $text);

        return [
            'hash' => md5($text),
            'length' => mb_strlen($text),
            'title' => Html::title($html),
        ];
    }
}

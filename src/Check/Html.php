<?php

declare(strict_types=1);

namespace YandexSites\Check;

/**
 * Небольшие помощники для разбора HTML страниц при проверке сайтов.
 */
final class Html
{
    /**
     * Приводит тело страницы к UTF-8 по кодировке из заголовка Content-Type или <meta charset>.
     */
    public static function toUtf8(string $body, string $contentType = ''): string
    {
        $charset = null;
        if (preg_match('/charset=["\']?([\w\-]+)/i', $contentType, $m) === 1) {
            $charset = $m[1];
        } elseif (preg_match('/<meta[^>]+charset=["\']?([\w\-]+)/i', substr($body, 0, 4096), $m) === 1) {
            $charset = $m[1];
        }
        $charset = strtolower($charset ?? 'utf-8');

        if (!in_array($charset, ['utf-8', 'utf8'], true)) {
            try {
                $converted = @mb_convert_encoding($body, 'UTF-8', $charset);
                if (is_string($converted)) {
                    $body = $converted;
                }
            } catch (\ValueError) {
                // неизвестная кодировка — оставляем как есть
            }
        }

        if (!mb_check_encoding($body, 'UTF-8')) {
            $body = mb_convert_encoding($body, 'UTF-8', 'UTF-8');
        }

        return $body;
    }

    public static function title(string $html): string
    {
        if (preg_match('~<title[^>]*>(.*?)</title>~isu', $html, $m) !== 1) {
            return '';
        }
        $title = html_entity_decode(strip_tags($m[1]), ENT_QUOTES | ENT_HTML5, 'UTF-8');

        return trim(preg_replace('/\s+/u', ' ', $title) ?? $title);
    }
}

<?php

declare(strict_types=1);

namespace YandexSites\Content;

/**
 * Автоопределение названия бренда по странице: английское берём из домена, русское — ищем в тексте
 * то слово, транслитерация которого совпадает с английским (cryptoboss ↔ криптобосс). Так пользователю
 * не нужно вводить бренд руками — достаточно нажать «Забрать контент» у сайта.
 */
final class BrandDetector
{
    /** Кириллица → латиница для сравнения (упрощённая фонетическая). */
    private const CYR2LAT = [
        'а' => 'a', 'б' => 'b', 'в' => 'v', 'г' => 'g', 'д' => 'd', 'е' => 'e', 'ё' => 'e', 'ж' => 'zh',
        'з' => 'z', 'и' => 'i', 'й' => 'i', 'к' => 'k', 'л' => 'l', 'м' => 'm', 'н' => 'n', 'о' => 'o',
        'п' => 'p', 'р' => 'r', 'с' => 's', 'т' => 't', 'у' => 'u', 'ф' => 'f', 'х' => 'h', 'ц' => 'c',
        'ч' => 'ch', 'ш' => 'sh', 'щ' => 'sch', 'ъ' => '', 'ы' => 'i', 'ь' => '', 'э' => 'e', 'ю' => 'yu', 'я' => 'ya',
    ];

    /**
     * @param string $host домен сайта (например, cryptoboss.ccy.casino)
     * @return array{en: string, ru: string} английский и русский бренд ('' если не найден)
     */
    public function detect(string $html, string $host): array
    {
        $en = $this->brandFromHost($host);
        $ru = $en !== '' ? $this->detectRu($this->visibleText($html), $en) : '';

        return ['en' => $en, 'ru' => $ru];
    }

    /**
     * Английский бренд — первая метка домена (cryptoboss.ccy.casino → cryptoboss), только буквы/цифры.
     */
    public function brandFromHost(string $host): string
    {
        $host = mb_strtolower(trim($host));
        $host = preg_replace('~^www\d*\.~', '', $host) ?? $host;
        $label = explode('.', $host)[0] ?? '';

        return (string) preg_replace('~[^a-z0-9]~', '', $label);
    }

    /**
     * Русский бренд — кириллическое слово из текста, чья транслитерация ближе всего к английскому бренду.
     */
    private function detectRu(string $text, string $en): string
    {
        $target = $this->phonetic($en);
        if ($target === '') {
            return '';
        }
        $threshold = max(1, (int) floor(mb_strlen($target) / 4));

        preg_match_all('~[А-Яа-яЁё]{3,}~u', $text, $m);
        $freq = [];
        foreach ($m[0] as $token) {
            $low = mb_strtolower($token);
            $freq[$low] = ($freq[$low] ?? 0) + 1;
        }

        $best = '';
        $bestDistance = PHP_INT_MAX;
        $bestFreq = 0;
        foreach ($freq as $token => $count) {
            $distance = levenshtein($this->phonetic($this->translit($token)), $target);
            if ($distance > $threshold) {
                continue;
            }
            if ($distance < $bestDistance || ($distance === $bestDistance && $count > $bestFreq)) {
                $best = $token;
                $bestDistance = $distance;
                $bestFreq = $count;
            }
        }

        return $best;
    }

    private function translit(string $cyr): string
    {
        $out = '';
        foreach (preg_split('~~u', mb_strtolower($cyr), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
            $out .= self::CYR2LAT[$ch] ?? $ch;
        }

        return $out;
    }

    /**
     * Фонетическая нормализация для сравнения: только латинские буквы, c/q→k, y→i, w→v, без сдвоенных.
     */
    private function phonetic(string $text): string
    {
        $text = mb_strtolower($text);
        $text = (string) preg_replace('~[^a-zа-яё]~u', '', $text);
        $text = strtr($text, ['c' => 'k', 'q' => 'k', 'y' => 'i', 'w' => 'v']);
        $text = (string) preg_replace('~(.)\1+~u', '$1', $text);

        return $text;
    }

    private function visibleText(string $html): string
    {
        $text = preg_replace('~<(script|style|noscript|svg|template)\b[^>]*>.*?</\1>~isu', ' ', $html) ?? $html;
        $text = strip_tags($text);

        return html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    }
}

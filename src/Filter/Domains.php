<?php

declare(strict_types=1);

namespace YandexSites\Filter;

/**
 * Вспомогательные функции для работы с доменными именами.
 */
final class Domains
{
    /** Известные кириллические зоны в punycode. */
    private const IDN_TLDS = [
        'xn--p1ai' => 'рф',
        'xn--p1acf' => 'рус',
        'xn--80adxhks' => 'москва',
        'xn--d1acj3b' => 'дети',
        'xn--80asehdb' => 'онлайн',
        'xn--80aswg' => 'сайт',
        'xn--c1avg' => 'орг',
        'xn--j1aef' => 'ком',
        'xn--90ais' => 'бел',
        'xn--j1amh' => 'укр',
        'xn--80ao21a' => 'қаз',
        'xn--90a3ac' => 'срб',
        'xn--d1alf' => 'мкд',
        'xn--e1a4c' => 'ею',
        'xn--l1acc' => 'мон',
    ];

    /** Зоны второго уровня, в которых регистрируются домены (упрощённый список). */
    private const SECOND_LEVEL = [
        'com.ru', 'net.ru', 'org.ru', 'pp.ru', 'msk.ru', 'spb.ru', 'nov.ru', 'msk.su', 'spb.su',
        'com.ua', 'net.ua', 'org.ua', 'in.ua', 'kiev.ua', 'kyiv.ua', 'dp.ua', 'od.ua', 'kh.ua', 'lviv.ua',
        'com.by', 'org.by', 'net.by', 'minsk.by',
        'com.kz', 'org.kz', 'net.kz', 'edu.kz', 'gov.kz',
        'com.kg', 'org.kg', 'net.kg', 'com.uz', 'co.uz', 'org.uz', 'com.tj', 'com.md', 'com.ge', 'org.ge', 'com.am',
        'com.tr', 'net.tr', 'org.tr', 'gen.tr', 'web.tr',
        'co.uk', 'org.uk', 'me.uk', 'com.au', 'net.au', 'org.au', 'co.nz', 'co.za', 'co.il', 'co.jp', 'ne.jp',
        'com.br', 'com.cn', 'com.hk', 'com.sg', 'com.mx', 'com.ar', 'com.pl', 'com.de', 'co.in', 'com.es',
        'com.ee', 'com.lv', 'com.lt', 'com.cy',
    ];

    /**
     * Хост из URL (в нижнем регистре, без www не убирается).
     */
    public static function hostFromUrl(string $url): string
    {
        $url = trim($url);
        $host = parse_url($url, PHP_URL_HOST);
        if (!is_string($host) || $host === '') {
            $host = parse_url('http://' . ltrim($url, '/'), PHP_URL_HOST);
        }

        return is_string($host) ? self::normalize($host, false) : '';
    }

    /**
     * Нормализует хост: нижний регистр, без схемы/пути/порта, без точки в конце,
     * опционально без префикса www.
     */
    public static function normalize(string $host, bool $stripWww = true): string
    {
        $host = mb_strtolower(trim($host));
        $host = preg_replace('~^[a-z][a-z0-9+.\-]*://~', '', $host) ?? $host;
        $host = explode('/', $host, 2)[0];
        $host = explode('?', $host, 2)[0];
        if (!str_starts_with($host, '[')) {
            $host = explode(':', $host, 2)[0];
        }
        $host = trim($host, '. ');
        if ($stripWww) {
            $host = preg_replace('~^www\d*\.~', '', $host) ?? $host;
        }

        return $host;
    }

    /**
     * Доменная зона (последняя метка). Известные кириллические зоны возвращаются в Unicode.
     */
    public static function tld(string $host): string
    {
        $labels = explode('.', mb_strtolower($host));
        $last = (string) end($labels);

        return self::IDN_TLDS[$last] ?? $last;
    }

    /**
     * Регистрируемый домен: example.ru для shop.example.ru, example.msk.ru для www.example.msk.ru.
     */
    public static function registrable(string $host): string
    {
        $labels = explode('.', $host);
        $n = count($labels);
        if ($n <= 2) {
            return $host;
        }
        $lastTwo = $labels[$n - 2] . '.' . $labels[$n - 1];
        if (in_array($lastTwo, self::SECOND_LEVEL, true)) {
            return $labels[$n - 3] . '.' . $lastTwo;
        }

        return $lastTwo;
    }

    /**
     * Punycode → Unicode (сайт.рф). Без ext-intl переводятся только известные зоны.
     */
    public static function toUnicode(string $host): string
    {
        if (!str_contains($host, 'xn--')) {
            return $host;
        }
        if (function_exists('idn_to_utf8')) {
            $unicode = @idn_to_utf8($host, IDNA_DEFAULT, INTL_IDNA_VARIANT_UTS46);
            if (is_string($unicode) && $unicode !== '') {
                return $unicode;
            }
        }
        $labels = explode('.', $host);
        $last = array_key_last($labels);
        if ($last !== null && isset(self::IDN_TLDS[$labels[$last]])) {
            $labels[$last] = self::IDN_TLDS[$labels[$last]];
        }

        return implode('.', $labels);
    }

    /**
     * Unicode → punycode. Без ext-intl переводятся только известные зоны.
     */
    public static function toAscii(string $host): string
    {
        if (preg_match('/^[\x00-\x7f]*$/', $host) === 1) {
            return $host;
        }
        if (function_exists('idn_to_ascii')) {
            $ascii = @idn_to_ascii($host, IDNA_DEFAULT, INTL_IDNA_VARIANT_UTS46);
            if (is_string($ascii) && $ascii !== '') {
                return $ascii;
            }
        }
        $labels = explode('.', $host);
        $last = array_key_last($labels);
        $map = array_flip(self::IDN_TLDS);
        if ($last !== null && isset($map[$labels[$last]])) {
            $labels[$last] = $map[$labels[$last]];
        }

        return implode('.', $labels);
    }

    /**
     * Принадлежат ли два хоста одному сайту (одному регистрируемому домену).
     */
    public static function sameSite(string $a, string $b): bool
    {
        return self::registrable(self::normalize($a)) === self::registrable(self::normalize($b));
    }
}

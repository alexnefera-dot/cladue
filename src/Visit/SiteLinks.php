<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Filter\Domains;

/**
 * Извлекает из шапки/меню страницы ссылки, ведущие на тот же сайт.
 * Внешние ссылки, mailto/tel/якоря и повторы отбрасываются; главная не включается
 * (её открывают отдельно). Используется для обхода всех страниц из меню сайта.
 */
final class SiteLinks
{
    /** Контейнеры, которые считаем «шапкой»/навигацией/подвалом с меню. */
    private const NAV = 'header|nav|navbar|topbar|top-bar|mainmenu|main-menu|menu|topmenu|top-menu|navigation|headermenu|footer|footmenu';

    /**
     * @param string $html     HTML главной страницы
     * @param string $baseUrl  адрес главной (для разбора относительных ссылок)
     * @param string $siteDomain регистрируемый домен сайта (shop.example.ru → example.ru)
     * @return list<string> абсолютные URL страниц того же сайта, по одному разу, без главной
     */
    public static function fromHeader(string $html, string $baseUrl, string $siteDomain, int $limit = 30): array
    {
        $xpath = self::load($html);
        // Обходим только текущий поддомен: у сетки шаблонов другие бренды живут на соседних
        // поддоменах (hype.dom, max.dom …) — на них не переходим. www — тот же хост.
        $baseHost = self::hostKey(Domains::hostFromUrl($baseUrl));
        $home = self::canonical($baseUrl);

        $anchors = $xpath->query(self::navQuery());
        if ($anchors === false || $anchors->length === 0) {
            // Шапка не распознана — берём ссылки из меню где угодно на странице.
            $anchors = $xpath->query('//a[' . self::classContains(self::NAV) . '][@href]');
        }

        $result = [];
        $seen = [];
        foreach ($anchors ?: [] as $a) {
            if (!$a instanceof \DOMElement) {
                continue;
            }
            $url = self::resolve($baseUrl, $a->getAttribute('href'));
            if ($url === null) {
                continue;
            }
            $host = Domains::hostFromUrl($url);
            if ($host === '' || self::hostKey($host) !== $baseHost) {
                continue; // внешняя ссылка / другой поддомен (другой бренд) — не обходим
            }
            if (self::isJunkPage($url)) {
                continue; // карта сайта (htmlmap/sitemap) и нестраничные файлы (.xml, .pdf, картинки…)
            }
            $canon = self::canonical($url);
            if ($canon === $home || isset($seen[$canon])) {
                continue; // главная или дубль
            }
            $seen[$canon] = true;
            $result[] = $url;
            if (count($result) >= $limit) {
                break;
            }
        }

        return $result;
    }

    /**
     * Тот же ли это хост (для проверки редиректов): один и тот же поддомен, с точностью до www.
     * Редирект/переход на другой поддомен (соседний бренд) считается уходом с сайта.
     */
    public static function sameHost(string $reference, string $url): bool
    {
        $a = self::hostKey(self::hostOf($reference));
        $b = self::hostKey(self::hostOf($url));

        return $a !== '' && $a === $b;
    }

    /**
     * Хост из URL или из строки, которая уже является хостом (host или host/path).
     */
    private static function hostOf(string $urlOrHost): string
    {
        if (preg_match('~^[a-z][a-z0-9+.\-]*://~i', $urlOrHost) === 1) {
            return Domains::hostFromUrl($urlOrHost);
        }

        return Domains::hostFromUrl('http://' . ltrim($urlOrHost, '/'));
    }

    /**
     * Ключ хоста для сравнения: нормализованный хост без ведущего www / www2.
     */
    private static function hostKey(string $host): string
    {
        $host = Domains::normalize($host);

        return preg_replace('~^www\d*\.~', '', $host) ?? $host;
    }

    private static function navQuery(): string
    {
        // Меню бывает и в подвале — учитываем header, nav, footer и контейнеры с «меню»-классами.
        $inNav = 'ancestor-or-self::header or ancestor-or-self::nav or ancestor-or-self::footer'
            . ' or ancestor::*[' . self::classContains(self::NAV) . ']'
            . ' or ancestor::*[@role="navigation" or @role="banner" or @role="contentinfo"]';

        return '//a[@href][' . $inNav . ']';
    }

    private static function classContains(string $alternation): string
    {
        $c = "translate(concat(' ', normalize-space(@class), ' ', normalize-space(@id), ' '), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')";
        $parts = [];
        foreach (explode('|', $alternation) as $word) {
            $parts[] = "contains($c, '$word')";
        }

        return implode(' or ', $parts);
    }

    /**
     * Приводит относительную ссылку к абсолютной; отбрасывает нестраничные (mailto, tel, js, якоря).
     */
    public static function resolve(string $base, string $href): ?string
    {
        $href = trim(html_entity_decode($href, ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        if ($href === '' || str_starts_with($href, '#')) {
            return null;
        }
        if (preg_match('~^(mailto:|tel:|javascript:|data:|blob:|ftp:|skype:|viber:|whatsapp:)~i', $href) === 1) {
            return null;
        }
        if (str_starts_with($href, '//')) {
            $scheme = parse_url($base, PHP_URL_SCHEME) ?: 'https';
            $href = $scheme . ':' . $href;
        }
        if (preg_match('~^[a-z][a-z0-9+.\-]*://~i', $href) === 1) {
            return self::collapseRepeats(self::stripFragment($href));
        }

        $parts = parse_url($base);
        if ($parts === false || !isset($parts['host'])) {
            return null;
        }
        $scheme = $parts['scheme'] ?? 'https';
        $authority = $scheme . '://' . $parts['host'] . (isset($parts['port']) ? ':' . $parts['port'] : '');
        if (str_starts_with($href, '/')) {
            return self::collapseRepeats(self::stripFragment($authority . self::normalizePath($href)));
        }
        // относительно каталога текущей страницы
        $basePath = $parts['path'] ?? '/';
        $dir = str_contains($basePath, '/') ? substr($basePath, 0, strrpos($basePath, '/') + 1) : '/';

        return self::collapseRepeats(self::stripFragment($authority . self::normalizePath($dir . $href)));
    }

    /**
     * Схлопывает подряд идущие одинаковые сегменты пути: /RU-ru/RU-ru/RU-ru/app → /RU-ru/app,
     * /zerkalo/ru/ru/ru/ → /zerkalo/ru. Так реальные страницы за «циклом» переключателя языка
     * скачиваются (по последнему сегменту), а варианты цикла разной длины сводятся к одному адресу.
     */
    private static function collapseRepeats(string $url): string
    {
        $parts = parse_url($url);
        if ($parts === false || ($parts['path'] ?? '') === '') {
            return $url;
        }
        $path = $parts['path'];
        $trailingSlash = $path !== '/' && str_ends_with($path, '/');
        $segments = [];
        $previous = null;
        foreach (explode('/', $path) as $segment) {
            if ($segment === '') {
                continue;
            }
            $low = mb_strtolower($segment);
            if ($low === $previous) {
                continue; // подряд идущий повтор — пропускаем
            }
            $segments[] = $segment;
            $previous = $low;
        }
        $newPath = '/' . implode('/', $segments);
        if ($trailingSlash && $newPath !== '/') {
            $newPath .= '/';
        }
        $authority = ($parts['scheme'] ?? 'https') . '://' . ($parts['host'] ?? '') . (isset($parts['port']) ? ':' . $parts['port'] : '');

        return $authority . $newPath . (isset($parts['query']) ? '?' . $parts['query'] : '');
    }

    private static function stripFragment(string $url): string
    {
        $pos = strpos($url, '#');

        return $pos === false ? $url : substr($url, 0, $pos);
    }

    /**
     * Убирает ./ и ../ из пути.
     */
    private static function normalizePath(string $path): string
    {
        $query = '';
        if (($q = strpos($path, '?')) !== false) {
            $query = substr($path, $q);
            $path = substr($path, 0, $q);
        }
        $segments = [];
        foreach (explode('/', $path) as $segment) {
            if ($segment === '.' || $segment === '') {
                continue;
            }
            if ($segment === '..') {
                array_pop($segments);
                continue;
            }
            $segments[] = $segment;
        }
        $normalized = '/' . implode('/', $segments);
        if (str_ends_with($path, '/') && $normalized !== '/') {
            $normalized .= '/';
        }

        return $normalized . $query;
    }

    /**
     * Каноничная форма для сравнения и удаления дублей: хост (без www) + путь без завершающего «/»,
     * без index/default/home-файла (алиасы главной) + запрос. Одна и та же страница под разными
     * адресами (/, /index.php, /about/, /about) сводится к одному ключу, чтобы не качать её дважды.
     */
    public static function canonical(string $url): string
    {
        $parts = parse_url(self::stripFragment(self::collapseRepeats($url)));
        if ($parts === false) {
            return mb_strtolower($url);
        }
        $host = Domains::normalize($parts['host'] ?? '', true);
        $path = rtrim($parts['path'] ?? '/', '/');
        $path = preg_replace('~/(?:index|default|home)\.(?:html?|php|phtml|aspx?|jsp|cgi)$~i', '', $path) ?? $path;
        if ($path === '') {
            $path = '/';
        }
        $query = isset($parts['query']) ? '?' . $parts['query'] : '';

        return $host . $path . $query;
    }

    /**
     * Служебная/нестраничная ссылка, которую не качаем: карта сайта (htmlmap, sitemap, «карта сайта»)
     * и файлы-ресурсы (.xml, .pdf, документы, картинки, архивы, .css/.js).
     */
    private static function isJunkPage(string $url): bool
    {
        $path = mb_strtolower((string) parse_url($url, PHP_URL_PATH));
        if (preg_match('~\.(xml|rss|atom|json|pdf|docx?|xlsx?|pptx?|zip|rar|gz|tar|7z|csv|txt|jpe?g|png|gif|svg|webp|ico|bmp|mp[34]|avi|mov|webm|css|js)$~', $path) === 1) {
            return true;
        }
        foreach (explode('/', $path) as $segment) {
            if ($segment !== '' && preg_match('~^(html-?map|html-?sitemap|site-?map|sitemap|карта-?сайта|karta-?sajta)~u', $segment) === 1) {
                return true;
            }
        }

        return false;
    }

    private static function load(string $html): \DOMXPath
    {
        $previous = libxml_use_internal_errors(true);
        $dom = new \DOMDocument();
        $dom->loadHTML('<?xml encoding="utf-8" ?>' . $html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING | LIBXML_HTML_NODEFDTD);
        libxml_clear_errors();
        libxml_use_internal_errors($previous);

        return new \DOMXPath($dom);
    }
}

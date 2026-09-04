<?php

declare(strict_types=1);

namespace YandexSites\Live;

use YandexSites\Filter\Domains;
use YandexSites\Model\SearchPage;
use YandexSites\Model\SearchResult;
use YandexSites\Search\ApiException;
use YandexSites\Search\ResponseParserInterface;

/**
 * Разбор HTML-страницы выдачи yandex.ru.
 *
 * Вёрстка Яндекса меняется, поэтому разбор построен на нескольких признаках
 * с запасными вариантами: элементы результатов — `.serp-item`, ссылка заголовка —
 * `a.OrganicTitle-Link` (или первая внешняя ссылка), текст — `.OrganicTextContentSpan`
 * и т. п. Проверить разбор на сохранённой странице: `--parse-html=файл.html`.
 */
final class HtmlResponseParser implements ResponseParserInterface
{
    public const KIND_SERP = 'serp';
    public const KIND_EMPTY = 'empty';
    public const KIND_CAPTCHA = 'captcha';
    public const KIND_BLOCKED = 'blocked';
    public const KIND_UNKNOWN = 'unknown';

    private const AD_HOSTS = '~(^|\.)(yabs\.yandex\.|an\.yandex\.|ads\.adfox\.)~i';
    private const CAPTCHA_MARKERS = '~showcaptcha|checkcaptcha|SmartCaptcha|CheckboxCaptcha|AdvancedCaptcha|captcha-wrapper|id="captcha"|<title>\s*Ой!\s*</title>|похожи на автоматические|Подтвердите, что запросы отправляли вы|Are you not a robot~iu';
    private const EMPTY_MARKERS = '~ничего не (нашлось|найдено)|не нашлось ни одного|Nothing found for|no results found~iu';

    /**
     * Определяет тип страницы: выдача, пустая выдача, капча, блокировка или что-то неизвестное.
     */
    public function classify(string $html, string $finalUrl = '', int $status = 200): string
    {
        if (preg_match('~/(show|check)captcha~i', $finalUrl) === 1) {
            return self::KIND_CAPTCHA;
        }
        if ($status === 403 || $status === 429) {
            return preg_match(self::CAPTCHA_MARKERS, $html) === 1 ? self::KIND_CAPTCHA : self::KIND_BLOCKED;
        }
        if (trim($html) === '') {
            return self::KIND_BLOCKED;
        }

        $xpath = $this->load($html);
        if ($xpath->query($this->itemsXpath())->length > 0) {
            return self::KIND_SERP;
        }
        if (preg_match(self::CAPTCHA_MARKERS, $html) === 1) {
            return self::KIND_CAPTCHA;
        }
        if (preg_match(self::EMPTY_MARKERS, $html) === 1) {
            return self::KIND_EMPTY;
        }

        return $status >= 500 ? self::KIND_BLOCKED : self::KIND_UNKNOWN;
    }

    public function parse(string $raw, string $query, int $page, int $positionOffset = 0): SearchPage
    {
        $kind = $this->classify($raw);
        if ($kind === self::KIND_EMPTY) {
            return new SearchPage($query, $page, 0, 0, [], false);
        }
        if ($kind === self::KIND_CAPTCHA) {
            throw new ApiException('Страница капчи вместо выдачи', retryable: true);
        }
        if ($kind !== self::KIND_SERP) {
            throw new ApiException('Не удалось распознать страницу выдачи (изменилась вёрстка или ответ не является выдачей). Проверьте разбор: --parse-html=файл', retryable: true);
        }

        $xpath = $this->load($raw);
        $results = [];
        $seen = [];
        $position = $positionOffset;
        $items = $xpath->query($this->itemsXpath());

        foreach ($items as $item) {
            if (!$item instanceof \DOMElement || $this->isAd($xpath, $item)) {
                continue;
            }
            $url = $this->findUrl($xpath, $item);
            if ($url === null) {
                continue;
            }
            $host = Domains::hostFromUrl($url);
            if ($host === '' || isset($seen[$url])) {
                continue;
            }
            $seen[$url] = true;
            $position++;

            $results[] = new SearchResult(
                query: $query,
                page: $page,
                position: $position,
                url: $url,
                host: $host,
                title: $this->findTitle($xpath, $item),
                headline: '',
                snippet: $this->findSnippet($xpath, $item),
            );
        }

        return new SearchPage($query, $page, $this->findCount($raw), $items->length, $results, $this->hasMore($xpath, $items->length));
    }

    private function itemsXpath(): string
    {
        $cls = self::cls('serp-item');

        return "//*[$cls][not(ancestor::*[$cls])]";
    }

    private function isAd(\DOMXPath $xpath, \DOMElement $item): bool
    {
        $class = ' ' . preg_replace('/\s+/', ' ', $item->getAttribute('class')) . ' ';
        if (str_contains($class, ' serp-adv-item ') || str_contains($class, 'Organic_type_ad') || str_contains($class, 't-construct-adapter__legacy')) {
            return true;
        }
        if ($xpath->query('.//*[' . self::cls('Organic_type_ad') . ' or ' . self::cls('serp-adv-item') . ']', $item)->length > 0) {
            return true;
        }
        foreach ($xpath->query('.//a[@href]', $item) as $link) {
            $href = $link instanceof \DOMElement ? $link->getAttribute('href') : '';
            if (preg_match(self::AD_HOSTS, (string) parse_url($href, PHP_URL_HOST)) === 1) {
                return true;
            }
        }
        foreach ($xpath->query('.//*[contains(@class, "abel") or contains(@class, "Subtitle") or contains(@class, "subtitle")]', $item) as $label) {
            $text = mb_strtolower(trim(preg_replace('/\s+/u', ' ', $label->textContent) ?? ''));
            if (in_array($text, ['реклама', 'реклама ·', 'ad', 'ads', 'sponsored'], true)) {
                return true;
            }
        }

        return false;
    }

    private function findUrl(\DOMXPath $xpath, \DOMElement $item): ?string
    {
        $queries = [
            './/a[' . self::cls('OrganicTitle-Link') . '][@href]',
            './/a[' . self::cls('organic__url') . '][@href]',
            './/*[' . self::cls('OrganicTitle') . ']//a[@href]',
            './/h2//a[@href]',
            './/h3//a[@href]',
            './/a[' . self::cls('Path-Item') . '][@href]',
            './/a[' . self::cls('Link') . '][@href]',
            './/a[@href]',
        ];
        foreach ($queries as $expr) {
            foreach ($xpath->query($expr, $item) as $link) {
                if (!$link instanceof \DOMElement) {
                    continue;
                }
                $url = $this->usableUrl($link->getAttribute('href'));
                if ($url !== null) {
                    return $url;
                }
            }
        }

        return null;
    }

    private function usableUrl(string $href): ?string
    {
        $href = html_entity_decode(trim($href), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        if (str_starts_with($href, '//')) {
            $href = 'https:' . $href;
        }
        if (preg_match('~^https?://~i', $href) !== 1) {
            return null;
        }
        $host = strtolower((string) parse_url($href, PHP_URL_HOST));
        if ($host === '' || preg_match(self::AD_HOSTS, $host) === 1) {
            return null;
        }
        $path = (string) parse_url($href, PHP_URL_PATH);
        if (preg_match('~(^|\.)(yandex\.[a-z.]+|ya\.ru)$~i', $host) === 1) {
            if (str_starts_with($path, '/clck/')) {
                parse_str((string) parse_url($href, PHP_URL_QUERY), $params);
                foreach (['url', 'u', 'text'] as $key) {
                    if (isset($params[$key]) && is_string($params[$key]) && preg_match('~^https?://~i', $params[$key]) === 1) {
                        return $params[$key];
                    }
                }

                return null;
            }
            if (str_starts_with($path, '/search') || str_starts_with($path, '/support') || str_starts_with($path, '/legal') || $path === '' || $path === '/') {
                return null;
            }
        }

        return $href;
    }

    private function findTitle(\DOMXPath $xpath, \DOMElement $item): string
    {
        foreach ([
            './/*[' . self::cls('OrganicTitle-LinkText') . ']',
            './/h2',
            './/h3',
            './/a[' . self::cls('OrganicTitle-Link') . ']',
            './/a[' . self::cls('organic__url') . ']',
        ] as $expr) {
            $node = $xpath->query($expr, $item)->item(0);
            if ($node !== null) {
                $text = $this->clean($node->textContent);
                if ($text !== '') {
                    return $text;
                }
            }
        }

        return '';
    }

    private function findSnippet(\DOMXPath $xpath, \DOMElement $item): string
    {
        foreach ([
            './/*[' . self::cls('OrganicTextContentSpan') . ']',
            './/*[' . self::cls('OrganicText') . ']',
            './/*[' . self::cls('text-container') . ']',
            './/*[' . self::cls('Organic-ContentWrapper') . ']',
            './/*[' . self::cls('organic__content-wrapper') . ']',
        ] as $expr) {
            $node = $xpath->query($expr, $item)->item(0);
            if ($node !== null) {
                $text = $this->clean($node->textContent);
                if ($text !== '') {
                    return $text;
                }
            }
        }

        return '';
    }

    private function hasMore(\DOMXPath $xpath, int $itemCount): bool
    {
        if ($xpath->query('//a[' . self::cls('Pager-Item_type_next') . ']')->length > 0) {
            return true;
        }
        $pagerExpr = '//*[' . self::cls('Pager') . ' or ' . self::cls('pager') . ']';
        if ($xpath->query($pagerExpr)->length > 0) {
            foreach ($xpath->query($pagerExpr . '//a') as $link) {
                $text = mb_strtolower($this->clean($link->textContent));
                $aria = $link instanceof \DOMElement ? mb_strtolower($link->getAttribute('aria-label')) : '';
                if (str_contains($text, 'дальше') || str_contains($text, 'следующ') || str_contains($aria, 'следующ') || str_contains($text, 'next')) {
                    return true;
                }
            }

            return false;
        }

        return $itemCount >= 10;
    }

    private function findCount(string $html): ?int
    {
        if (preg_match('~Нашл[ао]сь\s+([\d][\d\s\xC2\xA0.,]*)\s*(тыс\.?|млн|млрд)?~iu', $html, $m) !== 1) {
            return null;
        }
        $number = (float) str_replace(',', '.', preg_replace('/[\s\xC2\xA0]+/u', '', $m[1]) ?? '0');
        $multiplier = match (mb_strtolower(rtrim($m[2] ?? '', '.'))) {
            'тыс' => 1000,
            'млн' => 1000000,
            'млрд' => 1000000000,
            default => 1,
        };

        return (int) round($number * $multiplier);
    }

    private function load(string $html): \DOMXPath
    {
        $previous = libxml_use_internal_errors(true);
        $dom = new \DOMDocument();
        $dom->loadHTML('<?xml encoding="utf-8" ?>' . $html, LIBXML_NONET | LIBXML_NOERROR | LIBXML_NOWARNING | LIBXML_HTML_NODEFDTD);
        libxml_clear_errors();
        libxml_use_internal_errors($previous);

        return new \DOMXPath($dom);
    }

    private static function cls(string $name): string
    {
        return "contains(concat(' ', normalize-space(@class), ' '), ' $name ')";
    }

    private function clean(string $text): string
    {
        return trim(preg_replace('/\s+/u', ' ', $text) ?? $text);
    }
}

<?php

declare(strict_types=1);

namespace YandexSites\Search;

use YandexSites\Filter\Domains;
use YandexSites\Model\SearchPage;
use YandexSites\Model\SearchResult;

/**
 * Разбор XML-ответа Yandex Search API (формат Яндекс.XML).
 */
final class XmlResponseParser implements ResponseParserInterface
{
    public const NO_RESULTS_CODE = 15;

    /**
     * Ищет элемент <error> в ответе.
     *
     * @return array{code: int, message: string}|null
     */
    public function detectError(string $xml): ?array
    {
        $xpath = new \DOMXPath($this->load($xml));
        $node = $xpath->query('/yandexsearch/response/error')->item(0);
        if ($node === null) {
            return null;
        }

        return [
            'code' => (int) $node->getAttribute('code'),
            'message' => $this->clean($node->textContent),
        ];
    }

    /**
     * @throws ApiException если в ответе ошибка (кроме кода 15 — тогда вернётся пустая страница)
     */
    public function parse(string $raw, string $query, int $page, int $positionOffset = 0): SearchPage
    {
        $xml = $raw;
        $xpath = new \DOMXPath($this->load($xml));

        $error = $xpath->query('/yandexsearch/response/error')->item(0);
        if ($error !== null) {
            $code = (int) $error->getAttribute('code');
            if ($code === self::NO_RESULTS_CODE) {
                return new SearchPage($query, $page, 0, 0, []);
            }
            throw ApiException::fromYandexCode($code, $this->clean($error->textContent));
        }

        $found = null;
        foreach ($xpath->query('/yandexsearch/response/found') as $node) {
            $value = (int) $node->textContent;
            if ($found === null || $node->getAttribute('priority') === 'all') {
                $found = $value;
            }
        }

        $results = [];
        $position = $positionOffset;
        $groups = 0;
        foreach ($xpath->query('/yandexsearch/response/results/grouping/group') as $group) {
            $groups++;
            $categ = $xpath->query('categ', $group)->item(0);
            $groupDomain = $categ instanceof \DOMElement ? $categ->getAttribute('name') : '';

            foreach ($xpath->query('doc', $group) as $doc) {
                $position++;
                $url = $this->text($xpath, 'url', $doc);
                if ($url === '') {
                    continue;
                }
                $host = $this->text($xpath, 'domain', $doc);
                if ($host === '') {
                    $host = $groupDomain !== '' ? $groupDomain : Domains::hostFromUrl($url);
                }
                $passages = [];
                foreach ($xpath->query('passages/passage', $doc) as $passage) {
                    $text = $this->clean($passage->textContent);
                    if ($text !== '') {
                        $passages[] = $text;
                    }
                }

                $results[] = new SearchResult(
                    query: $query,
                    page: $page,
                    position: $position,
                    url: $url,
                    host: Domains::normalize($host, false),
                    title: $this->text($xpath, 'title', $doc),
                    headline: $this->text($xpath, 'headline', $doc),
                    snippet: implode(' … ', $passages),
                    modtime: $this->text($xpath, 'modtime', $doc),
                );
            }
        }

        return new SearchPage($query, $page, $found, $groups, $results);
    }

    private function load(string $xml): \DOMDocument
    {
        if (trim($xml) === '') {
            throw new ApiException('Пустой ответ от API');
        }

        $previous = libxml_use_internal_errors(true);
        $dom = new \DOMDocument();
        $loaded = $dom->loadXML($xml, LIBXML_NONET | LIBXML_NOCDATA | LIBXML_NOWARNING | LIBXML_NOERROR);
        $errors = libxml_get_errors();
        libxml_clear_errors();
        libxml_use_internal_errors($previous);

        if (!$loaded) {
            $reason = isset($errors[0]) ? trim($errors[0]->message) : 'неизвестная ошибка';
            throw new ApiException(sprintf(
                'Не удалось разобрать XML-ответ (%s). Начало ответа: %s',
                $reason,
                mb_substr(trim($xml), 0, 200),
            ));
        }
        if ($dom->documentElement === null || $dom->documentElement->nodeName !== 'yandexsearch') {
            throw new ApiException(sprintf(
                'Неожиданный формат ответа: нет корневого элемента <yandexsearch>. Начало ответа: %s',
                mb_substr(trim($xml), 0, 200),
            ));
        }

        return $dom;
    }

    private function text(\DOMXPath $xpath, string $expr, \DOMNode $context): string
    {
        $node = $xpath->query($expr, $context)->item(0);

        return $node === null ? '' : $this->clean($node->textContent);
    }

    private function clean(string $text): string
    {
        return trim(preg_replace('/\s+/u', ' ', $text) ?? $text);
    }
}

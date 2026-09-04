<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Сервис XMLStock (xmlstock.com): выдача Яндекса в формате Яндекс.XML.
 * GET https://xmlstock.com/yandex/xml/?user=…&key=…&query=…&lr=…&groupby=…&page=…
 */
final class XmlStockFetcher extends AbstractApiFetcher
{
    protected function fetchOnce(string $query, int $page): string
    {
        $endpoint = (string) $this->config->get('xmlstock.endpoint');
        $url = $endpoint . (str_contains($endpoint, '?') ? '&' : '?')
            . http_build_query($this->buildParams($query, $page), '', '&', PHP_QUERY_RFC3986);

        $response = $this->http->get($url);
        if ($response->status !== 200) {
            throw $this->httpError($response, 'Проверьте user и key в личном кабинете xmlstock.com и баланс');
        }

        return $response->body;
    }

    /**
     * GET-параметры запроса к XMLStock.
     *
     * @return array<string, string>
     */
    public function buildParams(string $query, int $page): array
    {
        $s = fn (string $key): mixed => $this->config->get('search.' . $key);

        $params = [
            'user' => (string) $this->config->get('xmlstock.user'),
            'key' => (string) $this->config->get('xmlstock.key'),
            'query' => $query,
            'lr' => (string) $s('region'),
            'l10n' => (string) $s('l10n'),
            'sortby' => $this->sortBy(),
            'filter' => (string) $s('family_mode'),
            'groupby' => $this->groupBy(),
            'maxpassages' => (string) (int) $s('max_passages'),
            'page' => (string) $page,
        ];

        foreach (['domain', 'device'] as $key) {
            $value = trim((string) $this->config->get('xmlstock.' . $key, ''));
            if ($value !== '') {
                $params[$key] = $value;
            }
        }
        foreach ((array) $this->config->get('xmlstock.extra_params', []) as $key => $value) {
            if (is_string($key) && $key !== '' && is_scalar($value)) {
                $params[$key] = (string) $value;
            }
        }

        return $params;
    }
}

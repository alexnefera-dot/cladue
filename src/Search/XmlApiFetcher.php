<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Yandex Search API v1 (устаревший XML-интерфейс): GET https://yandex.ru/search/xml?folderid=...&apikey=...
 * Ответ — XML напрямую.
 */
final class XmlApiFetcher extends AbstractApiFetcher
{
    protected function fetchOnce(string $query, int $page): string
    {
        $endpoint = (string) $this->config->get('api.xml_endpoint');
        $url = $endpoint . (str_contains($endpoint, '?') ? '&' : '?')
            . http_build_query($this->buildParams($query, $page), '', '&', PHP_QUERY_RFC3986);

        // В API v1 ключ передаётся параметром apikey; заголовок Authorization используется только для IAM-токена.
        $response = $this->http->get($url, $this->authHeaders(false));
        if ($response->status !== 200) {
            throw $this->httpError($response);
        }

        return $response->body;
    }

    /**
     * GET-параметры запроса к /search/xml.
     *
     * @return array<string, string>
     */
    public function buildParams(string $query, int $page): array
    {
        $s = fn (string $key): mixed => $this->config->get('search.' . $key);

        $params = [
            'folderid' => (string) $this->config->get('api.folder_id'),
            'query' => $query,
            'lr' => (string) $s('region'),
            'l10n' => (string) $s('l10n'),
            'sortby' => $this->sortBy(),
            'filter' => (string) $s('family_mode'),
            'groupby' => $this->groupBy(),
            'maxpassages' => (string) (int) $s('max_passages'),
            'page' => (string) $page,
        ];

        $apiKey = (string) $this->config->get('api.api_key');
        $iam = (string) $this->config->get('api.iam_token');
        if ($apiKey !== '' && $iam === '') {
            $params['apikey'] = $apiKey;
        }

        return $params;
    }
}

<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Сервис XMLStock (xmlstock.com). Два режима (xmlstock.mode):
 *  - xml  — выдача Яндекса в формате Яндекс.XML, до 100 сайтов на странице:
 *           GET https://xmlstock.com/yandex/xml/?user=…&key=…&query=…&lr=…&groupby=…&page=…
 *  - live — живая выдача Яндекса (как у обычного пользователя) в том же формате ответа,
 *           но не больше 10 результатов на странице; параметры группировки не действуют:
 *           GET https://xmlstock.com/yandexlive/xml/?user=…&key=…&query=…&lr=…&page=…
 */
final class XmlStockFetcher extends AbstractApiFetcher
{
    /** Столько результатов отдаёт одна страница живой выдачи XMLStock (ограничение Яндекса). */
    public const LIVE_PAGE_SIZE = 10;

    public const MODES = ['xml', 'live'];

    protected function fetchOnce(string $query, int $page): string
    {
        $endpoint = $this->endpoint();
        $url = $endpoint . (str_contains($endpoint, '?') ? '&' : '?')
            . http_build_query($this->buildParams($query, $page), '', '&', PHP_QUERY_RFC3986);

        $response = $this->http->get($url);
        if ($response->status !== 200) {
            throw $this->httpError($response, 'Проверьте user и key в личном кабинете xmlstock.com и баланс');
        }

        return $response->body;
    }

    /** Живая выдача (xmlstock.mode = live) или Яндекс.XML. */
    public function isLive(): bool
    {
        return (string) $this->config->get('xmlstock.mode', 'xml') === 'live';
    }

    /** Адрес сервиса для выбранного режима. */
    public function endpoint(): string
    {
        return (string) $this->config->get($this->isLive() ? 'xmlstock.live_endpoint' : 'xmlstock.endpoint');
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
        ];
        if (!$this->isLive()) {
            // Параметры Яндекс.XML; у живой выдачи их нет — страница всегда 10 результатов
            $params += [
                'l10n' => (string) $s('l10n'),
                'sortby' => $this->sortBy(),
                'filter' => (string) $s('family_mode'),
                'groupby' => $this->groupBy(),
                'maxpassages' => (string) (int) $s('max_passages'),
            ];
        }
        $params['page'] = (string) $page;

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

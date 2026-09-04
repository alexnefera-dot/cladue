<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Yandex Search API v2 (REST): POST https://searchapi.api.cloud.yandex.net/v2/web/search.
 * Ответ приходит в JSON, поле rawData содержит XML в base64.
 */
final class RestApiFetcher extends AbstractApiFetcher
{
    private const SEARCH_TYPES = [
        'ru' => 'SEARCH_TYPE_RU',
        'tr' => 'SEARCH_TYPE_TR',
        'com' => 'SEARCH_TYPE_COM',
        'kk' => 'SEARCH_TYPE_KK',
        'be' => 'SEARCH_TYPE_BE',
        'uz' => 'SEARCH_TYPE_UZ',
    ];
    private const LOCALIZATIONS = [
        'ru' => 'LOCALIZATION_RU',
        'uk' => 'LOCALIZATION_UK',
        'be' => 'LOCALIZATION_BE',
        'kk' => 'LOCALIZATION_KK',
        'tr' => 'LOCALIZATION_TR',
        'en' => 'LOCALIZATION_EN',
    ];
    private const FAMILY_MODES = [
        'none' => 'FAMILY_MODE_NONE',
        'moderate' => 'FAMILY_MODE_MODERATE',
        'strict' => 'FAMILY_MODE_STRICT',
    ];
    private const PERIODS = [
        'all' => 'PERIOD_ALL_TIME',
        'day' => 'PERIOD_DAY',
        '2weeks' => 'PERIOD_2_WEEKS',
        'month' => 'PERIOD_MONTH',
    ];

    protected function fetchOnce(string $query, int $page): string
    {
        $endpoint = (string) $this->config->get('api.rest_endpoint');
        $response = $this->http->postJson($endpoint, $this->buildPayload($query, $page), $this->authHeaders());
        if ($response->status !== 200) {
            throw $this->httpError($response);
        }

        $data = json_decode($response->body, true);
        if (!is_array($data) || !isset($data['rawData']) || !is_string($data['rawData'])) {
            throw new ApiException('Неожиданный ответ API: нет поля rawData. Начало ответа: ' . mb_substr($response->body, 0, 300));
        }
        $xml = base64_decode($data['rawData'], true);
        if ($xml === false) {
            throw new ApiException('Не удалось декодировать поле rawData (base64)');
        }

        return $xml;
    }

    /**
     * Тело запроса к /v2/web/search.
     *
     * @return array<string, mixed>
     */
    public function buildPayload(string $query, int $page): array
    {
        $s = fn (string $key): mixed => $this->config->get('search.' . $key);

        $payload = [
            'query' => [
                'searchType' => self::SEARCH_TYPES[$s('search_type')] ?? 'SEARCH_TYPE_RU',
                'queryText' => $query,
                'familyMode' => self::FAMILY_MODES[$s('family_mode')] ?? 'FAMILY_MODE_MODERATE',
                'page' => (string) $page,
                'fixTypoMode' => $s('fix_typo') ? 'FIX_TYPO_MODE_ON' : 'FIX_TYPO_MODE_OFF',
            ],
            'sortSpec' => [
                'sortMode' => $s('sort') === 'time' ? 'SORT_MODE_BY_TIME' : 'SORT_MODE_BY_RELEVANCE',
                'sortOrder' => 'SORT_ORDER_DESC',
            ],
            'groupSpec' => [
                'groupMode' => $s('group_mode') === 'flat' ? 'GROUP_MODE_FLAT' : 'GROUP_MODE_DEEP',
                'groupsOnPage' => (string) (int) $s('groups_on_page'),
                'docsInGroup' => (string) (int) $s('docs_in_group'),
            ],
            'maxPassages' => (string) (int) $s('max_passages'),
            'region' => (string) $s('region'),
            'l10n' => self::LOCALIZATIONS[$s('l10n')] ?? 'LOCALIZATION_RU',
            'folderId' => (string) $this->config->get('api.folder_id'),
            'responseFormat' => 'FORMAT_XML',
            'userAgent' => (string) $this->config->get('api.user_agent'),
        ];

        $period = self::PERIODS[$s('period')] ?? 'PERIOD_ALL_TIME';
        if ($period !== 'PERIOD_ALL_TIME') {
            $payload['period'] = $period;
        }

        return $payload;
    }
}

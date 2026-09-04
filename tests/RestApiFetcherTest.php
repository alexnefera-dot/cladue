<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Http\HttpException;
use YandexSites\Http\HttpResponse;
use YandexSites\Search\ApiException;
use YandexSites\Search\RestApiFetcher;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Support\Logger;

final class RestApiFetcherTest
{
    private function config(array $extra = []): Config
    {
        return new Config(array_replace_recursive([
            'api' => ['folder_id' => 'folder-1', 'api_key' => 'key-1', 'delay_ms' => 0, 'retries' => 1, 'retry_delay_ms' => 1],
        ], $extra));
    }

    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    private function okResponse(): HttpResponse
    {
        $xml = (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml');

        return new HttpResponse(200, json_encode(['rawData' => base64_encode($xml)]) ?: '', 'application/json');
    }

    public function testPayloadMatchesApiContract(): void
    {
        $fetcher = new RestApiFetcher($this->config(['search' => ['region' => 2, 'pages' => 2, 'groups_on_page' => 20, 'sort' => 'time', 'period' => 'month', 'l10n' => 'en', 'search_type' => 'com', 'fix_typo' => false, 'family_mode' => 'strict', 'group_mode' => 'flat']]), new StubHttpClient([]), new XmlResponseParser(), $this->logger());
        $payload = $fetcher->buildPayload('окна пвх', 1);

        Assert::same([
            'query' => [
                'searchType' => 'SEARCH_TYPE_COM',
                'queryText' => 'окна пвх',
                'familyMode' => 'FAMILY_MODE_STRICT',
                'page' => '1',
                'fixTypoMode' => 'FIX_TYPO_MODE_OFF',
            ],
            'sortSpec' => ['sortMode' => 'SORT_MODE_BY_TIME', 'sortOrder' => 'SORT_ORDER_DESC'],
            'groupSpec' => ['groupMode' => 'GROUP_MODE_FLAT', 'groupsOnPage' => '20', 'docsInGroup' => '1'],
            'maxPassages' => '2',
            'region' => '2',
            'l10n' => 'LOCALIZATION_EN',
            'folderId' => 'folder-1',
            'responseFormat' => 'FORMAT_XML',
            'userAgent' => 'Mozilla/5.0 (compatible; yandex-sites/1.0)',
            'period' => 'PERIOD_MONTH',
        ], $payload);

        $default = (new RestApiFetcher($this->config(), new StubHttpClient([]), new XmlResponseParser(), $this->logger()))->buildPayload('q', 0);
        Assert::same('SEARCH_TYPE_RU', $default['query']['searchType']);
        Assert::same('GROUP_MODE_DEEP', $default['groupSpec']['groupMode']);
        Assert::same('50', $default['groupSpec']['groupsOnPage']);
        Assert::false(isset($default['period']), 'period не передаётся для all');
    }

    public function testFetchDecodesRawData(): void
    {
        $http = new StubHttpClient([$this->okResponse()]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        $xml = $fetcher->fetch('окна', 0);
        Assert::contains('<yandexsearch', $xml);

        $call = $http->calls[0];
        Assert::same('POST', $call['method']);
        Assert::same('https://searchapi.api.cloud.yandex.net/v2/web/search', $call['url']);
        Assert::same('Api-Key key-1', $call['headers']['Authorization']);
        Assert::same('application/json', $call['headers']['Content-Type']);
        Assert::contains('"queryText":"окна"', (string) $call['body']);
    }

    public function testIamTokenHasPriority(): void
    {
        $http = new StubHttpClient([$this->okResponse()]);
        $fetcher = new RestApiFetcher($this->config(['api' => ['iam_token' => 'iam-1']]), $http, new XmlResponseParser(), $this->logger());
        $fetcher->fetch('окна', 0);
        Assert::same('Bearer iam-1', $http->calls[0]['headers']['Authorization']);
    }

    public function testAuthErrorIsFatal(): void
    {
        $http = new StubHttpClient([new HttpResponse(401, '{"code":16,"message":"Unauthenticated"}')]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('окна', 0), 'Unauthenticated');
        Assert::true($e->isFatal());
        Assert::same(1, count($http->calls), 'без повторов');
    }

    public function testRetriesOnTemporaryErrors(): void
    {
        $http = new StubHttpClient([
            new HttpResponse(429, '{"message":"Too many requests"}'),
            $this->okResponse(),
        ]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        Assert::contains('<yandexsearch', $fetcher->fetch('окна', 0));
        Assert::same(2, count($http->calls));

        $http = new StubHttpClient([new HttpException('timeout'), new HttpException('timeout')]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        Assert::throws(ApiException::class, static fn () => $fetcher->fetch('окна', 0), 'timeout');
        Assert::same(2, count($http->calls), 'retries=1 — две попытки');

        $error55 = (string) file_get_contents(TESTS_ROOT . '/fixtures/response_error55.xml');
        $http = new StubHttpClient([
            new HttpResponse(200, json_encode(['rawData' => base64_encode($error55)]) ?: ''),
            $this->okResponse(),
        ]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        Assert::contains('okna-moskva.ru', $fetcher->fetch('окна', 0));
        Assert::same(2, count($http->calls), 'код 55 повторяется');
    }

    public function testNoResultsIsNotAnError(): void
    {
        $error15 = (string) file_get_contents(TESTS_ROOT . '/fixtures/response_error15.xml');
        $http = new StubHttpClient([new HttpResponse(200, json_encode(['rawData' => base64_encode($error15)]) ?: '')]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        Assert::contains('code="15"', $fetcher->fetch('окна', 0));
    }

    public function testUnexpectedBody(): void
    {
        $http = new StubHttpClient([new HttpResponse(200, '{"unexpected":true}')]);
        $fetcher = new RestApiFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        Assert::throws(ApiException::class, static fn () => $fetcher->fetch('окна', 0), 'rawData');
    }
}

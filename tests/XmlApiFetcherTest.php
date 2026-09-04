<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Http\HttpResponse;
use YandexSites\Search\ApiException;
use YandexSites\Search\XmlApiFetcher;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Support\Logger;

final class XmlApiFetcherTest
{
    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    public function testParamsAndUrl(): void
    {
        $config = new Config(['api' => ['folder_id' => 'folder-1', 'api_key' => 'key-1', 'delay_ms' => 0, 'retries' => 0], 'search' => ['groups_on_page' => 30, 'docs_in_group' => 2]]);
        $http = new StubHttpClient([new HttpResponse(200, (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml'))]);
        $fetcher = new XmlApiFetcher($config, $http, new XmlResponseParser(), $this->logger());

        Assert::same([
            'folderid' => 'folder-1',
            'query' => 'окна пвх',
            'lr' => '213',
            'l10n' => 'ru',
            'sortby' => 'rlv',
            'filter' => 'moderate',
            'groupby' => 'attr=d.mode=deep.groups-on-page=30.docs-in-group=2',
            'maxpassages' => '2',
            'page' => '1',
            'apikey' => 'key-1',
        ], $fetcher->buildParams('окна пвх', 1));

        $fetcher->fetch('окна пвх', 1);
        $url = $http->calls[0]['url'];
        Assert::same('GET', $http->calls[0]['method']);
        Assert::contains('https://yandex.ru/search/xml?folderid=folder-1&query=%D0%BE%D0%BA%D0%BD%D0%B0%20%D0%BF%D0%B2%D1%85', $url);
        Assert::contains('groupby=attr%3Dd.mode%3Ddeep.groups-on-page%3D30.docs-in-group%3D2', $url);
        Assert::false(isset($http->calls[0]['headers']['Authorization']), 'ключ передаётся параметром, а не заголовком');
    }

    public function testIamTokenUsesHeader(): void
    {
        $config = new Config(['api' => ['folder_id' => 'folder-1', 'iam_token' => 'iam-1', 'delay_ms' => 0, 'retries' => 0], 'search' => ['sort' => 'time', 'group_mode' => 'flat']]);
        $http = new StubHttpClient([new HttpResponse(200, (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml'))]);
        $fetcher = new XmlApiFetcher($config, $http, new XmlResponseParser(), $this->logger());
        $params = $fetcher->buildParams('q', 0);
        Assert::false(isset($params['apikey']));
        Assert::same('tm.order=descending', $params['sortby']);
        Assert::same('attr="".mode=flat.groups-on-page=50.docs-in-group=1', $params['groupby']);
        $fetcher->fetch('q', 0);
        Assert::same('Bearer iam-1', $http->calls[0]['headers']['Authorization']);
    }

    public function testXmlErrorsAreDetected(): void
    {
        $config = new Config(['api' => ['folder_id' => 'f', 'api_key' => 'k', 'delay_ms' => 0, 'retries' => 0]]);
        $bad = '<?xml version="1.0"?><yandexsearch version="1.0"><response><error code="43">Ключ не найден</error></response></yandexsearch>';
        $http = new StubHttpClient([new HttpResponse(200, $bad)]);
        $fetcher = new XmlApiFetcher($config, $http, new XmlResponseParser(), $this->logger());
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('q', 0), '43');
        Assert::true($e->isFatal());
    }
}

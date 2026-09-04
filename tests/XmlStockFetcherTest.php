<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Http\HttpResponse;
use YandexSites\Search\ApiException;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\Logger;

final class XmlStockFetcherTest
{
    private function config(array $extra = []): Config
    {
        return new Config(array_replace_recursive([
            'source' => 'xmlstock',
            'api' => ['delay_ms' => 0, 'retries' => 0],
            'xmlstock' => ['user' => 'u1', 'key' => 'k1'],
        ], $extra));
    }

    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    public function testParamsAndUrl(): void
    {
        $config = $this->config([
            'search' => ['groups_on_page' => 20, 'region' => 2],
            'xmlstock' => ['domain' => 'yandex.kz', 'device' => 'mobile', 'extra_params' => ['nfpr' => 1, 5 => 'ignored', 'empty' => []]],
        ]);
        $http = new StubHttpClient([new HttpResponse(200, (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml'))]);
        $fetcher = new XmlStockFetcher($config, $http, new XmlResponseParser(), $this->logger());

        Assert::same([
            'user' => 'u1',
            'key' => 'k1',
            'query' => 'окна пвх',
            'lr' => '2',
            'l10n' => 'ru',
            'sortby' => 'rlv',
            'filter' => 'moderate',
            'groupby' => 'attr=d.mode=deep.groups-on-page=20.docs-in-group=1',
            'maxpassages' => '2',
            'page' => '1',
            'domain' => 'yandex.kz',
            'device' => 'mobile',
            'nfpr' => '1',
        ], $fetcher->buildParams('окна пвх', 1));

        Assert::contains('<yandexsearch', $fetcher->fetch('окна пвх', 1));
        $call = $http->calls[0];
        Assert::same('GET', $call['method']);
        Assert::true(str_starts_with($call['url'], 'https://xmlstock.com/yandex/xml/?user=u1&key=k1&query=%D0%BE%D0%BA%D0%BD%D0%B0%20%D0%BF%D0%B2%D1%85&lr=2'), $call['url']);
        Assert::false(isset($call['headers']['Authorization']));

        $params = (new XmlStockFetcher($this->config(), $http, new XmlResponseParser(), $this->logger()))->buildParams('q', 0);
        Assert::false(isset($params['domain']));
        Assert::false(isset($params['device']));
    }

    public function testErrors(): void
    {
        $http = new StubHttpClient([new HttpResponse(401, 'Unauthorized')]);
        $fetcher = new XmlStockFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('q', 0), 'xmlstock.com');
        Assert::true($e->isFatal());

        $bad = '<?xml version="1.0"?><yandexsearch version="1.0"><response><error code="42">Invalid key</error></response></yandexsearch>';
        $http = new StubHttpClient([new HttpResponse(200, $bad)]);
        $fetcher = new XmlStockFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('q', 0), '42');
        Assert::true($e->isFatal());
    }

    public function testConfigRequiresCredentials(): void
    {
        $errors = (new Config(['source' => 'xmlstock']))->validate();
        Assert::same(1, count($errors));
        Assert::contains('XMLSTOCK_USER', $errors[0]);
        Assert::same([], $this->config()->validate());
    }
}

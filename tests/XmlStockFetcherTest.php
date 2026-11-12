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

    /** Конфиг с повторами: по умолчанию в тестах их 0, а здесь проверяется именно повтор. */
    private function config2(): Config
    {
        return $this->config(['api' => ['retries' => 2, 'retry_delay_ms' => 0]]);
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

    public function testLiveModeUsesLiveEndpointWithoutXmlParams(): void
    {
        $config = $this->config([
            'search' => ['groups_on_page' => 20, 'region' => 2],
            'xmlstock' => ['mode' => 'live', 'device' => 'mobile', 'extra_params' => ['ads' => '1']],
        ]);
        $http = new StubHttpClient([new HttpResponse(200, (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml'))]);
        $fetcher = new XmlStockFetcher($config, $http, new XmlResponseParser(), $this->logger());

        Assert::true($fetcher->isLive());
        Assert::same('https://xmlstock.com/yandexlive/xml/', $fetcher->endpoint());
        Assert::same([
            'user' => 'u1',
            'key' => 'k1',
            'query' => 'окна пвх',
            'lr' => '2',
            'page' => '1',
            'device' => 'mobile',
            'ads' => '1',
        ], $fetcher->buildParams('окна пвх', 1), 'у живой выдачи нет groupby/sortby/maxpassages');

        Assert::contains('<yandexsearch', $fetcher->fetch('окна пвх', 1));
        Assert::true(str_starts_with($http->calls[0]['url'], 'https://xmlstock.com/yandexlive/xml/?user=u1&key=k1&query='), $http->calls[0]['url']);

        $xml = new XmlStockFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        Assert::false($xml->isLive(), 'по умолчанию — Яндекс.XML');
        Assert::same('https://xmlstock.com/yandex/xml/', $xml->endpoint());
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

    public function testAuthErrorCodeIsFatal(): void
    {
        $xml = '<?xml version="1.0"?><yandexsearch version="1.0"><response><error code="-34">Не корректный ID пользователя или ключ</error></response></yandexsearch>';
        $http = new StubHttpClient([new HttpResponse(200, $xml)]);
        $fetcher = new XmlStockFetcher($this->config(), $http, new XmlResponseParser(), $this->logger());
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('q', 0), 'user и key');
        Assert::true($e->isFatal());
        Assert::false($e->isRetryable());
        Assert::same(-34, $e->getYandexCode());
        Assert::same(1, count($http->calls), 'ошибка доступа не повторяется');
    }

    public function testTransientErrorIsRetriedInsteadOfKillingTheRun(): void
    {
        // Ошибка 20 — «Не удалось получить данные. Повторите запрос еще раз»: источник сам просит
        // повторить. Пока она считалась обычной, запрос падал с первой попытки, и пятый подряд
        // останавливал весь сбор — на реальном прогоне на 17-м запросе из 1552.
        $fail = '<?xml version="1.0"?><yandexsearch version="1.0"><response><error code="20">'
            . 'Не удалось получить данные. Повторите запрос еще раз</error></response></yandexsearch>';
        $good = (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml');
        $http = new StubHttpClient([new HttpResponse(200, $fail), new HttpResponse(200, $good)]);
        $fetcher = new XmlStockFetcher($this->config2(), $http, new XmlResponseParser(), $this->logger());

        $xml = $fetcher->fetch('окна', 0);

        Assert::contains('yandexsearch', $xml, 'со второй попытки ответ получен');
        Assert::same(2, count($http->calls), 'запрос повторён, а не брошен');

        // И то же самое, когда источник нумерует сбой по-своему, но просит повторить словами.
        $other = '<?xml version="1.0"?><yandexsearch version="1.0"><response><error code="71">'
            . 'Сервис временно недоступен, попробуйте позже</error></response></yandexsearch>';
        $http = new StubHttpClient([new HttpResponse(200, $other), new HttpResponse(200, $good)]);
        $fetcher = new XmlStockFetcher($this->config2(), $http, new XmlResponseParser(), $this->logger());
        Assert::contains('yandexsearch', $fetcher->fetch('окна', 0));
        Assert::same(2, count($http->calls), 'просьба повторить важнее номера ошибки');

        // А ошибка в самом запросе повторов не стоит: повторять её бессмысленно.
        $bad = '<?xml version="1.0"?><yandexsearch version="1.0"><response><error code="102">'
            . 'Пустой поисковый запрос</error></response></yandexsearch>';
        $http = new StubHttpClient([new HttpResponse(200, $bad)]);
        $fetcher = new XmlStockFetcher($this->config2(), $http, new XmlResponseParser(), $this->logger());
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('q', 0), '102');
        Assert::false($e->isRetryable());
        Assert::same(1, count($http->calls));
    }

    public function testConfigRequiresCredentials(): void
    {
        $errors = (new Config(['source' => 'xmlstock']))->validate();
        Assert::same(1, count($errors));
        Assert::contains('XMLSTOCK_USER', $errors[0]);
        Assert::same([], $this->config()->validate());
    }
}

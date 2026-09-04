<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Http\HttpException;
use YandexSites\Http\HttpResponse;
use YandexSites\Live\HtmlResponseParser;
use YandexSites\Live\LiveFetcher;
use YandexSites\Live\ProxyPool;
use YandexSites\Live\UserAgents;
use YandexSites\Search\ApiException;
use YandexSites\Support\Logger;

final class LiveFetcherTest
{
    private string $serp;
    private string $captcha;
    private string $empty;

    public function __construct()
    {
        $this->serp = (string) file_get_contents(TESTS_ROOT . '/fixtures/serp.html');
        $this->captcha = (string) file_get_contents(TESTS_ROOT . '/fixtures/serp_captcha.html');
        $this->empty = (string) file_get_contents(TESTS_ROOT . '/fixtures/serp_empty.html');
    }

    private function config(array $extra = []): Config
    {
        return new Config(array_replace_recursive([
            'source' => 'live',
            'live' => [
                'domain' => 'yandex.ru',
                'delay_ms' => 0,
                'jitter_ms' => 0,
                'min_gap_ms' => 0,
                'attempts' => 3,
                'captcha_cooldown' => 600,
                'error_cooldown' => 60,
                'max_proxy_failures' => 2,
                'max_wait' => 0,
                'cookies' => false,
            ],
            'search' => ['region' => 213],
        ], $extra));
    }

    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    private function fetcher(Config $config, StubHttpClient $http, ProxyPool $pool): LiveFetcher
    {
        return new LiveFetcher($config, $http, new HtmlResponseParser(), $pool, $this->logger());
    }

    public function testSwitchesProxyAfterCaptcha(): void
    {
        $pool = ProxyPool::fromLines(['a.ru:1', 'b.ru:2']);
        $http = new StubHttpClient([
            new HttpResponse(200, $this->captcha, 'text/html', 'https://yandex.ru/showcaptcha?retpath=x'),
            new HttpResponse(200, $this->serp, 'text/html', 'https://yandex.ru/search/?text=x'),
        ]);
        $fetcher = $this->fetcher($this->config(), $http, $pool);

        Assert::contains('serp-item', $fetcher->fetch('окна', 0));
        Assert::same(2, count($http->calls));
        Assert::same('https://yandex.ru/search/?text=%D0%BE%D0%BA%D0%BD%D0%B0&lr=213', $http->calls[0]['url']);
        Assert::same('http://a.ru:1', $http->calls[0]['options']['proxy']);
        Assert::same('http://b.ru:2', $http->calls[1]['options']['proxy']);
        Assert::same(true, $http->calls[0]['options']['follow']);
        Assert::null($http->calls[0]['options']['cookie_jar'], 'cookies отключены');
        Assert::inArray($http->calls[0]['headers']['User-Agent'], UserAgents::BROWSERS);
        Assert::false(UserAgents::isBot($http->calls[0]['headers']['User-Agent']), 'к выдаче ходим как браузер, не как робот');
        Assert::same('https://yandex.ru/', $http->calls[0]['headers']['Referer']);

        [$a, $b] = $pool->all();
        Assert::same(1, $a->captchas);
        Assert::false($a->isAvailable(time()));
        Assert::same(0, $b->failures);
        Assert::same(1, $b->requests);
    }

    public function testSecondPageUsesPreviousPageAsReferer(): void
    {
        $pool = ProxyPool::fromLines(['direct']);
        $http = new StubHttpClient([new HttpResponse(200, $this->serp)]);
        $fetcher = $this->fetcher($this->config(), $http, $pool);
        $fetcher->fetch('окна', 1);
        Assert::contains('&p=1', $http->calls[0]['url']);
        Assert::same('https://yandex.ru/search/?text=%D0%BE%D0%BA%D0%BD%D0%B0&lr=213', $http->calls[0]['headers']['Referer']);
        Assert::null($http->calls[0]['options']['proxy'], 'прямое подключение');
    }

    public function testEmptyAndBlockedResponses(): void
    {
        $pool = ProxyPool::fromLines(['a.ru:1', 'b.ru:2']);
        $http = new StubHttpClient([
            new HttpResponse(503, '<html><body>oops</body></html>'),
            new HttpResponse(200, $this->empty),
        ]);
        $fetcher = $this->fetcher($this->config(), $http, $pool);
        Assert::contains('ничего не нашлось', $fetcher->fetch('ывапролдж', 0));
        Assert::same(1, $pool->all()[0]->totalFailures);
        Assert::same(0, $pool->all()[0]->captchas);
    }

    public function testGivesUpAfterAttempts(): void
    {
        $pool = ProxyPool::fromLines(['a.ru:1', 'b.ru:2', 'c.ru:3']);
        $http = new StubHttpClient([new HttpException('timeout'), new HttpException('timeout'), new HttpException('timeout')]);
        $fetcher = $this->fetcher($this->config(), $http, $pool);
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('окна', 0), '3 попыток');
        Assert::false($e->isFatal());
        Assert::same(3, count($http->calls));
    }

    public function testStopsWhenAllProxiesAreExhausted(): void
    {
        $pool = ProxyPool::fromLines(['a.ru:1'], 1, 1);
        $http = new StubHttpClient([new HttpException('refused')]);
        $fetcher = $this->fetcher($this->config(), $http, $pool);
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('окна', 0), 'отключены');
        Assert::true($e->isFatal());

        $pool = ProxyPool::fromLines(['a.ru:1']);
        $http = new StubHttpClient([new HttpResponse(200, $this->captcha, 'text/html', 'https://yandex.ru/showcaptcha')]);
        $fetcher = $this->fetcher($this->config(), $http, $pool);
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $fetcher->fetch('окна', 0), 'на паузе');
        Assert::true($e->isFatal(), 'ждать дольше max_wait нельзя — остановка');
    }

    public function testBaseUrlAndCustomDomain(): void
    {
        $fetcher = $this->fetcher($this->config(['live' => ['domain' => 'http://127.0.0.1:8089'], 'search' => ['region' => '']]), new StubHttpClient([]), ProxyPool::fromLines(['direct']));
        Assert::same('http://127.0.0.1:8089', $fetcher->baseUrl());
        Assert::same('http://127.0.0.1:8089/search/?text=q', $fetcher->buildUrl('q', 0));
        $fetcher = $this->fetcher($this->config(['live' => ['domain' => 'yandex.kz']]), new StubHttpClient([]), ProxyPool::fromLines(['direct']));
        Assert::same('https://yandex.kz/search/?text=q&lr=213&p=2', $fetcher->buildUrl('q', 2));
    }
}

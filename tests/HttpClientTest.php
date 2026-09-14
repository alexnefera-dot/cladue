<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Http\HttpClient;
use YandexSites\Http\HttpException;
use YandexSites\Http\HttpResponse;

final class HttpClientTest
{
    public function testRequestManyRunsInParallelAndKeepsKeys(): void
    {
        $port = FakeServer::port();
        $client = new HttpClient(20, 'yandex-sites/test');
        $url = static fn (string $query): string => "http://127.0.0.1:$port/yandex/xml/?user=u&key=k&query=" . rawurlencode($query) . '&groupby=attr%3Dd.mode%3Ddeep.groups-on-page%3D3.docs-in-group%3D1&page=0';

        $requests = [];
        foreach (['окна', 'двери', 'балконы', 'лоджии'] as $q) {
            $requests[$q] = ['url' => $url($q)];
        }
        $started = microtime(true);
        $responses = $client->requestMany($requests, 4);
        $elapsed = microtime(true) - $started;

        Assert::same(['окна', 'двери', 'балконы', 'лоджии'], array_keys($responses), 'порядок ключей сохранён');
        foreach ($responses as $query => $response) {
            Assert::true($response instanceof HttpResponse, "ответ на «{$query}»: " . ($response instanceof HttpException ? $response->getMessage() : 'нет'));
            Assert::same(200, $response->status);
            Assert::contains('<yandexsearch', $response->body);
            Assert::contains(htmlspecialchars($query, ENT_XML1), $response->body, 'ответ соответствует своему запросу');
        }
        Assert::true($elapsed < 20.0, 'четыре запроса разом, а не по очереди');

        // Сетевая ошибка возвращается на своём ключе, остальные ответы не теряются.
        $mixed = $client->requestMany(['good' => ['url' => $url('окна')], 'bad' => ['url' => 'http://127.0.0.1:1/']], 2);
        Assert::true($mixed['good'] instanceof HttpResponse);
        Assert::true($mixed['bad'] instanceof HttpException, 'недоступный адрес — ошибка, а не ответ');
        Assert::same([], $client->requestMany([]));
    }
}

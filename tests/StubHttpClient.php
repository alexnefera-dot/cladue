<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Http\HttpClient;
use YandexSites\Http\HttpException;
use YandexSites\Http\HttpResponse;

/**
 * HTTP-клиент с заранее заданными ответами (по порядку вызовов).
 */
final class StubHttpClient extends HttpClient
{
    /** @var list<array{method: string, url: string, headers: array<string, string>, body: string|null, options: array<string, mixed>}> */
    public array $calls = [];

    /**
     * @param list<HttpResponse|HttpException> $responses
     */
    public function __construct(private array $responses)
    {
        parent::__construct(1, 'stub');
    }

    public function request(string $method, string $url, array $headers = [], ?string $body = null, array $options = []): HttpResponse
    {
        $this->calls[] = ['method' => $method, 'url' => $url, 'headers' => $headers, 'body' => $body, 'options' => $options];
        if ($this->responses === []) {
            throw new \LogicException('Нет заготовленных ответов');
        }
        $response = array_shift($this->responses);
        if ($response instanceof HttpException) {
            throw $response;
        }

        return $response;
    }
}

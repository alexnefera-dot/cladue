<?php

declare(strict_types=1);

namespace YandexSites\Search;

use YandexSites\Config;
use YandexSites\Http\HttpClient;
use YandexSites\Http\HttpException;
use YandexSites\Http\HttpResponse;
use YandexSites\Support\Logger;

/**
 * Общая логика клиентов API: пауза между запросами, повторы с нарастающей задержкой,
 * разбор HTTP-ошибок и ошибок в теле XML.
 */
abstract class AbstractApiFetcher implements BatchFetcherInterface
{
    private float $lastRequestAt = 0.0;

    public function __construct(
        protected Config $config,
        protected HttpClient $http,
        protected XmlResponseParser $parser,
        protected Logger $log,
    ) {
    }

    public function fetch(string $query, int $page): string
    {
        $retries = max(0, (int) $this->config->get('api.retries'));
        $attempt = 0;

        while (true) {
            $this->throttle();
            try {
                return $this->checkXml($this->fetchOnce($query, $page));
            } catch (HttpException $e) {
                $exception = new ApiException($e->getMessage(), retryable: true, previous: $e);
            } catch (ApiException $e) {
                $exception = $e;
            }

            if (!$exception->isRetryable() || $attempt >= $retries) {
                throw $exception;
            }
            $attempt++;
            $delayMs = max(0, (int) $this->config->get('api.retry_delay_ms', 1000)) * (2 ** ($attempt - 1));
            $this->log->warn(sprintf('%s — повтор %d/%d через %d мс', $exception->getMessage(), $attempt, $retries, $delayMs));
            usleep($delayMs * 1000);
        }
    }

    /**
     * Несколько запросов выдачи ПАРАЛЛЕЛЬНО (одна пауза на всю пачку). Ответы с ошибкой, которую можно
     * повторить, добираются обычным путём — по одному, с задержками и повторами.
     *
     * @param array<array-key, array{query: string, page: int}> $requests
     * @return array<array-key, string|ApiException>
     */
    public function fetchMany(array $requests, int $concurrency = 5): array
    {
        if ($requests === []) {
            return [];
        }
        if (count($requests) === 1) {
            $only = array_key_first($requests);
            try {
                return [$only => $this->fetch((string) $requests[$only]['query'], (int) $requests[$only]['page'])];
            } catch (ApiException $e) {
                return [$only => $e];
            }
        }

        $http = [];
        foreach ($requests as $key => $req) {
            $http[$key] = $this->buildRequest((string) $req['query'], (int) $req['page']);
        }
        $this->throttle();
        $responses = $this->http->requestMany($http, $concurrency);

        $out = [];
        foreach ($requests as $key => $req) {
            $response = $responses[$key] ?? new HttpException('Нет ответа');
            try {
                if ($response instanceof HttpException) {
                    throw new ApiException($response->getMessage(), retryable: true, previous: $response);
                }
                $out[$key] = $this->checkXml($this->parseResponse($response));
            } catch (ApiException $e) {
                // Повторяемую ошибку (лимит частоты, 5xx, сеть) добираем обычным путём — с паузами.
                if ($e->isRetryable()) {
                    try {
                        $out[$key] = $this->fetch((string) $req['query'], (int) $req['page']);
                        continue;
                    } catch (ApiException $retryError) {
                        $e = $retryError;
                    }
                }
                $out[$key] = $e;
            }
        }

        return $out;
    }

    /**
     * Один HTTP-запрос к API; возвращает XML-ответ.
     *
     * @throws ApiException|HttpException
     */
    protected function fetchOnce(string $query, int $page): string
    {
        $request = $this->buildRequest($query, $page);

        return $this->parseResponse($this->http->request(
            $request['method'],
            $request['url'],
            $request['headers'],
            $request['body'],
        ));
    }

    /**
     * Описание HTTP-запроса за одну страницу выдачи (чтобы пачку можно было отправить параллельно).
     *
     * @return array{method: string, url: string, headers: array<string, string>, body: string|null}
     */
    abstract protected function buildRequest(string $query, int $page): array;

    /**
     * Достаёт XML из ответа источника (или бросает ApiException по HTTP-коду).
     *
     * @throws ApiException
     */
    abstract protected function parseResponse(HttpResponse $response): string;

    /**
     * Ошибка внутри XML (код Яндекса): «ничего не найдено» ошибкой не считается.
     *
     * @throws ApiException
     */
    private function checkXml(string $xml): string
    {
        $error = $this->parser->detectError($xml);
        if ($error !== null && $error['code'] !== XmlResponseParser::NO_RESULTS_CODE) {
            throw ApiException::fromYandexCode($error['code'], $error['message']);
        }

        return $xml;
    }

    /**
     * Заголовок авторизации: IAM-токен имеет приоритет, иначе API-ключ.
     *
     * @return array<string, string>
     */
    protected function authHeaders(bool $apiKeyAsHeader = true): array
    {
        $iam = (string) $this->config->get('api.iam_token');
        if ($iam !== '') {
            return ['Authorization' => 'Bearer ' . $iam];
        }
        $key = (string) $this->config->get('api.api_key');
        if ($key !== '' && $apiKeyAsHeader) {
            return ['Authorization' => 'Api-Key ' . $key];
        }

        return [];
    }

    /**
     * Параметр groupby в формате Яндекс.XML (используется API v1 и XMLStock).
     */
    protected function groupBy(): string
    {
        $mode = $this->config->get('search.group_mode') === 'flat' ? 'flat' : 'deep';

        return sprintf(
            'attr=%s.mode=%s.groups-on-page=%d.docs-in-group=%d',
            $mode === 'deep' ? 'd' : '""',
            $mode,
            (int) $this->config->get('search.groups_on_page'),
            (int) $this->config->get('search.docs_in_group'),
        );
    }

    protected function sortBy(): string
    {
        return $this->config->get('search.sort') === 'time' ? 'tm.order=descending' : 'rlv';
    }

    protected function httpError(HttpResponse $response, string $authHint = 'Проверьте API-ключ, folder_id и роль search-api.webSearch.user у сервисного аккаунта'): ApiException
    {
        $status = $response->status;
        $message = mb_substr(trim($response->body), 0, 300);
        $decoded = json_decode($response->body, true);
        if (is_array($decoded) && isset($decoded['message']) && is_string($decoded['message'])) {
            $message = $decoded['message'];
        }

        return match (true) {
            $status === 401 || $status === 403 => new ApiException(
                sprintf('Ошибка авторизации (HTTP %d): %s. %s', $status, $message, $authHint),
                fatal: true,
            ),
            $status === 429 => new ApiException(sprintf('Превышена частота запросов (HTTP 429): %s', $message), retryable: true),
            $status >= 500 => new ApiException(sprintf('Ошибка на стороне API (HTTP %d): %s', $status, $message), retryable: true),
            default => new ApiException(sprintf('HTTP %d: %s', $status, $message)),
        };
    }

    protected function throttle(): void
    {
        $delayMs = (int) $this->config->get('api.delay_ms');
        if ($delayMs > 0 && $this->lastRequestAt > 0) {
            $elapsedMs = (microtime(true) - $this->lastRequestAt) * 1000;
            if ($elapsedMs < $delayMs) {
                usleep((int) (($delayMs - $elapsedMs) * 1000));
            }
        }
        $this->lastRequestAt = microtime(true);
    }
}

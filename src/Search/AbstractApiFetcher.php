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
abstract class AbstractApiFetcher implements XmlFetcherInterface
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
                $xml = $this->fetchOnce($query, $page);
                $error = $this->parser->detectError($xml);
                if ($error !== null && $error['code'] !== XmlResponseParser::NO_RESULTS_CODE) {
                    throw ApiException::fromYandexCode($error['code'], $error['message']);
                }

                return $xml;
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
     * Один HTTP-запрос к API; возвращает XML-ответ.
     *
     * @throws ApiException|HttpException
     */
    abstract protected function fetchOnce(string $query, int $page): string;

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

    protected function httpError(HttpResponse $response): ApiException
    {
        $status = $response->status;
        $message = mb_substr(trim($response->body), 0, 300);
        $decoded = json_decode($response->body, true);
        if (is_array($decoded) && isset($decoded['message']) && is_string($decoded['message'])) {
            $message = $decoded['message'];
        }

        return match (true) {
            $status === 401 || $status === 403 => new ApiException(
                sprintf('Ошибка авторизации (HTTP %d): %s. Проверьте API-ключ, folder_id и роль search-api.webSearch.user у сервисного аккаунта', $status, $message),
                fatal: true,
            ),
            $status === 429 => new ApiException(sprintf('Превышена частота запросов (HTTP 429): %s', $message), retryable: true),
            $status >= 500 => new ApiException(sprintf('Ошибка на стороне API (HTTP %d): %s', $status, $message), retryable: true),
            default => new ApiException(sprintf('HTTP %d: %s', $status, $message)),
        };
    }

    private function throttle(): void
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

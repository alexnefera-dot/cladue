<?php

declare(strict_types=1);

namespace YandexSites\Http;

/**
 * Минимальная обёртка над curl для запросов к API.
 */
class HttpClient
{
    public function __construct(
        private int $timeout = 30,
        private string $userAgent = 'yandex-sites/1.0',
    ) {
    }

    /**
     * @param array<string, string> $headers
     */
    public function get(string $url, array $headers = []): HttpResponse
    {
        return $this->request('GET', $url, $headers);
    }

    /**
     * @param array<string, mixed> $payload
     * @param array<string, string> $headers
     */
    public function postJson(string $url, array $payload, array $headers = []): HttpResponse
    {
        $body = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        $headers['Content-Type'] = 'application/json';

        return $this->request('POST', $url, $headers, $body);
    }

    /**
     * @param array<string, string> $headers
     * @param array<string, mixed> $options proxy (URL вида scheme://user:pass@host:port), cookie_jar (файл),
     *                                      follow (следовать редиректам), timeout, verify_ssl
     */
    public function request(string $method, string $url, array $headers = [], ?string $body = null, array $options = []): HttpResponse
    {
        $ch = $this->handle($method, $url, $headers, $body, $options);

        $response = curl_exec($ch);
        if ($response === false) {
            $errno = curl_errno($ch);
            $error = curl_error($ch);
            throw new HttpException(sprintf('Сетевая ошибка (curl %d): %s%s', $errno, $error, self::proxyHint($error)), $errno);
        }

        return $this->response($ch, (string) $response);
    }

    /**
     * Несколько запросов ПАРАЛЛЕЛЬНО (curl_multi). Сбор большого списка ключей по одному запросу за раз
     * упирался в сеть: 3000 запросов подряд — это часы ожидания, а источник позволяет несколько потоков.
     *
     * @param array<array-key, array{method?: string, url: string, headers?: array<string, string>, body?: string|null, options?: array<string, mixed>}> $requests
     * @return array<array-key, HttpResponse|HttpException> ответ или ошибка по тем же ключам
     */
    public function requestMany(array $requests, int $concurrency = 5): array
    {
        if ($requests === []) {
            return [];
        }
        $concurrency = max(1, $concurrency);
        $queue = $requests;
        $results = [];
        $multi = curl_multi_init();
        /** @var array<int, array{key: array-key, ch: \CurlHandle}> $active */
        $active = [];

        while ($queue !== [] || $active !== []) {
            while ($queue !== [] && count($active) < $concurrency) {
                $key = array_key_first($queue);
                $req = $queue[$key];
                unset($queue[$key]);
                $ch = $this->handle(
                    (string) ($req['method'] ?? 'GET'),
                    (string) $req['url'],
                    (array) ($req['headers'] ?? []),
                    $req['body'] ?? null,
                    (array) ($req['options'] ?? []),
                );
                curl_multi_add_handle($multi, $ch);
                $active[spl_object_id($ch)] = ['key' => $key, 'ch' => $ch];
            }

            do {
                $status = curl_multi_exec($multi, $running);
            } while ($status === CURLM_CALL_MULTI_PERFORM);
            if ($running > 0 && curl_multi_select($multi, 0.5) === -1) {
                usleep(10000);
            }

            while (($info = curl_multi_info_read($multi)) !== false) {
                $ch = $info['handle'];
                $entry = $active[spl_object_id($ch)];
                unset($active[spl_object_id($ch)]);
                curl_multi_remove_handle($multi, $ch);
                $body = (string) curl_multi_getcontent($ch);
                if ((int) $info['result'] !== CURLE_OK) {
                    $error = curl_error($ch) !== '' ? curl_error($ch) : 'код ' . (int) $info['result'];
                    $results[$entry['key']] = new HttpException(
                        sprintf('Сетевая ошибка (curl %d): %s%s', (int) $info['result'], $error, self::proxyHint($error)),
                        (int) $info['result'],
                    );
                } else {
                    $results[$entry['key']] = $this->response($ch, $body);
                }
                curl_close($ch);
            }
        }
        curl_multi_close($multi);

        // Порядок ключей — как в запросе: вызывающему удобнее разбирать ответы подряд.
        $ordered = [];
        foreach ($requests as $key => $_) {
            $ordered[$key] = $results[$key] ?? new HttpException('Нет ответа');
        }

        return $ordered;
    }

    private function response(\CurlHandle $ch, string $body): HttpResponse
    {
        return new HttpResponse(
            (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE),
            $body,
            (string) curl_getinfo($ch, CURLINFO_CONTENT_TYPE),
            (string) curl_getinfo($ch, CURLINFO_EFFECTIVE_URL),
        );
    }

    /**
     * @param array<string, string> $headers
     * @param array<string, mixed> $options
     */
    private function handle(string $method, string $url, array $headers, ?string $body, array $options): \CurlHandle
    {
        $headerLines = [];
        foreach ($headers as $name => $value) {
            $headerLines[] = $name . ': ' . $value;
        }
        $timeout = max(1, (int) ($options['timeout'] ?? $this->timeout));

        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CUSTOMREQUEST => $method,
            CURLOPT_HTTPHEADER => $headerLines,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_CONNECTTIMEOUT => min(10, $timeout),
            CURLOPT_USERAGENT => $this->userAgent,
            CURLOPT_ENCODING => '',
            CURLOPT_FOLLOWLOCATION => (bool) ($options['follow'] ?? false),
            CURLOPT_MAXREDIRS => 5,
        ]);
        if ($body !== null) {
            curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
        }
        if (!empty($options['proxy'])) {
            curl_setopt($ch, CURLOPT_PROXY, (string) $options['proxy']);
            curl_setopt($ch, CURLOPT_PROXYAUTH, CURLAUTH_BASIC | CURLAUTH_DIGEST);
        }
        if (!empty($options['cookie_jar'])) {
            curl_setopt($ch, CURLOPT_COOKIEFILE, (string) $options['cookie_jar']);
            curl_setopt($ch, CURLOPT_COOKIEJAR, (string) $options['cookie_jar']);
        }
        if (array_key_exists('verify_ssl', $options) && !$options['verify_ssl']) {
            curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
            curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
        }

        return $ch;
    }

    /**
     * Подсказка по типичным ошибкам прокси.
     */
    public static function proxyHint(string $error): string
    {
        if (str_contains($error, 'response 407')) {
            return ' — прокси не принял логин или пароль (HTTP 407): проверьте строку в proxies.txt';
        }
        if (str_contains($error, 'response 403')) {
            return ' — прокси запретил доступ (HTTP 403): возможно, ваш IP не в белом списке у провайдера прокси';
        }
        if (preg_match('/response (5\d\d)/', $error, $m) === 1) {
            return sprintf(' — прокси-сервер отвечает ошибкой (HTTP %s), вероятно не работает', $m[1]);
        }

        return '';
    }
}

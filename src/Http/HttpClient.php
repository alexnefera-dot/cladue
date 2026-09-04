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

        $response = curl_exec($ch);
        if ($response === false) {
            $errno = curl_errno($ch);
            $error = curl_error($ch);
            throw new HttpException(sprintf('Сетевая ошибка (curl %d): %s%s', $errno, $error, self::proxyHint($error)), $errno);
        }

        $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $contentType = (string) curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
        $finalUrl = (string) curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);

        return new HttpResponse($status, (string) $response, $contentType, $finalUrl);
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

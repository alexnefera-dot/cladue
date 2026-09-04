<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Check\Html;

/**
 * Посещение страниц обычными HTTP-запросами (curl_multi), без выполнения JavaScript.
 * Запасной вариант, когда Playwright недоступен.
 */
final class CurlDriver implements DriverInterface
{
    public function name(): string
    {
        return 'curl';
    }

    public function visit(array $jobs, array $options, ?callable $onResult = null): array
    {
        $concurrency = max(1, (int) ($options['concurrency'] ?? 2));
        $delayMs = max(0, (int) ($options['delay_ms'] ?? 0));
        $timeout = max(1, (int) ($options['timeout'] ?? 30));
        $maxBytes = max(65536, (int) ($options['max_bytes'] ?? 2 * 1024 * 1024));
        $verifySsl = (bool) ($options['verify_ssl'] ?? true);
        $resolve = array_values(array_filter((array) ($options['resolve'] ?? []), 'is_string'));

        $queue = $jobs;
        $results = [];
        $multi = curl_multi_init();
        /** @var array<int, array{job: VisitJob, ch: \CurlHandle, buf: object, cookie: string}> $active */
        $active = [];
        $lastStart = 0.0;

        while ($queue !== [] || $active !== []) {
            while ($queue !== [] && count($active) < $concurrency) {
                if ($delayMs > 0 && $lastStart > 0) {
                    $sinceLast = (microtime(true) - $lastStart) * 1000;
                    if ($sinceLast < $delayMs) {
                        if ($active !== []) {
                            break;
                        }
                        usleep((int) (($delayMs - $sinceLast) * 1000));
                    }
                }
                $job = array_shift($queue);
                $buf = new \stdClass();
                $buf->data = '';
                $buf->truncated = false;
                $cookie = tempnam(sys_get_temp_dir(), 'ys-visit-');
                $ch = $this->handle($job, $buf, $timeout, $maxBytes, $verifySsl, $resolve, (string) $cookie);
                curl_multi_add_handle($multi, $ch);
                $active[spl_object_id($ch)] = ['job' => $job, 'ch' => $ch, 'buf' => $buf, 'cookie' => (string) $cookie];
                $lastStart = microtime(true);
            }

            do {
                $status = curl_multi_exec($multi, $running);
            } while ($status === CURLM_CALL_MULTI_PERFORM);

            if ($running > 0 && curl_multi_select($multi, 0.5) === -1) {
                usleep(10000);
            } elseif ($running === 0 && $active === [] && $queue !== []) {
                usleep(10000);
            }

            while (($info = curl_multi_info_read($multi)) !== false) {
                $ch = $info['handle'];
                $entry = $active[spl_object_id($ch)];
                unset($active[spl_object_id($ch)]);
                curl_multi_remove_handle($multi, $ch);

                $job = $entry['job'];
                $buf = $entry['buf'];
                $errno = (int) $info['result'];
                $httpStatus = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
                $finalUrl = (string) curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
                $contentType = (string) curl_getinfo($ch, CURLINFO_CONTENT_TYPE);
                @unlink($entry['cookie']);

                if ($errno !== CURLE_OK && !$buf->truncated) {
                    $result = ['ok' => false, 'error' => sprintf('curl %d: %s', $errno, curl_strerror($errno) ?? ''), 'status' => null, 'final_url' => $finalUrl, 'title' => ''];
                } else {
                    $html = Html::toUtf8($buf->data, $contentType);
                    $dir = dirname($job->htmlFile);
                    if (!is_dir($dir)) {
                        @mkdir($dir, 0777, true);
                    }
                    $saved = @file_put_contents($job->htmlFile, $html) !== false;
                    $result = [
                        'ok' => $saved,
                        'error' => $saved ? '' : 'не удалось сохранить файл ' . $job->htmlFile,
                        'status' => $httpStatus,
                        'final_url' => $finalUrl,
                        'title' => Html::title($html),
                    ];
                }
                $results[$job->id] = $result;
                if ($onResult !== null) {
                    $onResult($job, $result);
                }
            }
        }

        return $results;
    }

    /**
     * @param list<string> $resolve
     */
    private function handle(VisitJob $job, object $buf, int $timeout, int $maxBytes, bool $verifySsl, array $resolve, string $cookieFile): \CurlHandle
    {
        $headers = [
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language: ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        ];
        if ($job->referer !== '') {
            $headers[] = 'Referer: ' . $job->referer;
        }
        $ch = curl_init();
        $options = [
            CURLOPT_URL => $job->url,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS => 5,
            CURLOPT_TIMEOUT => $timeout,
            CURLOPT_CONNECTTIMEOUT => min(10, $timeout),
            CURLOPT_USERAGENT => $job->userAgent,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_ENCODING => '',
            CURLOPT_COOKIEFILE => $cookieFile,
            CURLOPT_COOKIEJAR => $cookieFile,
            CURLOPT_SSL_VERIFYPEER => $verifySsl,
            CURLOPT_SSL_VERIFYHOST => $verifySsl ? 2 : 0,
            CURLOPT_WRITEFUNCTION => static function ($ch, string $chunk) use ($buf, $maxBytes): int {
                $buf->data .= $chunk;
                if (strlen($buf->data) > $maxBytes) {
                    $buf->truncated = true;

                    return -1;
                }

                return strlen($chunk);
            },
        ];
        if ($job->proxyUrl !== null) {
            $options[CURLOPT_PROXY] = $job->proxyUrl;
            $options[CURLOPT_PROXYAUTH] = CURLAUTH_BASIC | CURLAUTH_DIGEST;
        }
        if ($resolve !== []) {
            $options[CURLOPT_RESOLVE] = $resolve;
        }
        curl_setopt_array($ch, $options);

        return $ch;
    }
}

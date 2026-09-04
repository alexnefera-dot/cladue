<?php

declare(strict_types=1);

namespace YandexSites\Check;

use YandexSites\Filter\Domains;
use YandexSites\Filter\TextMatcher;
use YandexSites\Live\UserAgents;
use YandexSites\Model\Site;
use YandexSites\Support\Logger;

/**
 * Параллельная HTTP-проверка отобранных сайтов (curl_multi): доступность,
 * код ответа, редиректы и наличие/отсутствие текста на странице.
 */
class SiteChecker
{
    private int $concurrency;
    private int $timeout;
    private bool $verifySsl;
    private int $maxBytes;
    private string $userAgent;
    private string $target;
    private bool $rejectOffsiteRedirect;
    /** @var list<int> */
    private array $requireStatus;
    private TextMatcher $mustMatch;
    private TextMatcher $mustNotMatch;

    /**
     * @param array<string, mixed> $cfg раздел `site_check` конфигурации
     */
    public function __construct(array $cfg, private Logger $log)
    {
        $this->concurrency = max(1, (int) ($cfg['concurrency'] ?? 5));
        $this->timeout = max(1, (int) ($cfg['timeout'] ?? 15));
        $this->verifySsl = (bool) ($cfg['verify_ssl'] ?? true);
        $this->maxBytes = max(1024, (int) ($cfg['max_bytes'] ?? 512 * 1024));
        $this->userAgent = (string) (($cfg['user_agent'] ?? '') !== '' ? $cfg['user_agent'] : UserAgents::YANDEX_BOT);
        $this->target = (string) ($cfg['target'] ?? 'root');
        $this->rejectOffsiteRedirect = (bool) ($cfg['reject_offsite_redirect'] ?? false);
        $this->requireStatus = array_values(array_map('intval', (array) ($cfg['require_status'] ?? [200])));
        $this->mustMatch = new TextMatcher($cfg['page_must_match'] ?? [], false, 'site_check.page_must_match');
        $this->mustNotMatch = new TextMatcher($cfg['page_must_not_match'] ?? [], false, 'site_check.page_must_not_match');
    }

    /**
     * @param array<string, Site> $sites
     * @return array<string, CheckResult> ключ сайта => результат
     */
    public function check(array $sites): array
    {
        $queue = [];
        foreach ($sites as $key => $site) {
            $queue[] = ['key' => $key, 'site' => $site, 'url' => $this->targetUrl($site, 'https'), 'httpTried' => false];
        }

        $results = [];
        $multi = curl_multi_init();
        /** @var array<int, array{job: array<string, mixed>, ch: \CurlHandle, buf: object}> $active */
        $active = [];
        $total = count($queue);
        $done = 0;

        while ($queue !== [] || $active !== []) {
            while ($queue !== [] && count($active) < $this->concurrency) {
                $job = array_shift($queue);
                $buf = new \stdClass();
                $buf->data = '';
                $buf->truncated = false;
                $ch = $this->handle((string) $job['url'], $buf);
                curl_multi_add_handle($multi, $ch);
                $active[spl_object_id($ch)] = ['job' => $job, 'ch' => $ch, 'buf' => $buf];
            }

            do {
                $status = curl_multi_exec($multi, $running);
            } while ($status === CURLM_CALL_MULTI_PERFORM);

            if ($running > 0 && curl_multi_select($multi, 1.0) === -1) {
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
                curl_close($ch);

                if ($errno !== CURLE_OK && !$buf->truncated) {
                    if (!$job['httpTried'] && str_starts_with((string) $job['url'], 'https://')) {
                        $job['httpTried'] = true;
                        $job['url'] = 'http://' . substr((string) $job['url'], 8);
                        $queue[] = $job;
                        continue;
                    }
                    $error = sprintf('curl %d: %s', $errno, curl_strerror($errno) ?? '');
                    $results[$job['key']] = new CheckResult(false, 'unreachable', null, (string) $job['url'], '', $error);
                    $done++;
                    $this->log->debug(sprintf('  [%d/%d] %s — недоступен (%s)', $done, $total, $job['site']->host, $error));
                    continue;
                }

                $result = $this->evaluate($job['site'], $httpStatus, $finalUrl, $contentType, $buf->data);
                $results[$job['key']] = $result;
                $done++;
                $this->log->debug(sprintf(
                    '  [%d/%d] %s — HTTP %d, %s',
                    $done,
                    $total,
                    $job['site']->host,
                    $httpStatus,
                    $result->ok ? 'подходит' : 'отклонён (' . $result->reason . ')',
                ));
            }
        }

        curl_multi_close($multi);

        return $results;
    }

    /**
     * Адрес, который проверяем: корень сайта или найденная в выдаче страница.
     */
    protected function targetUrl(Site $site, string $scheme): string
    {
        if ($this->target === 'found' && $site->bestUrl !== '') {
            return $site->bestUrl;
        }

        return $scheme . '://' . $site->host . '/';
    }

    /**
     * Дополнительные curl-опции для запроса (точка расширения: прокси, CURLOPT_RESOLVE в тестах).
     *
     * @return array<int, mixed>
     */
    protected function curlOptions(string $url): array
    {
        return [];
    }

    private function handle(string $url, object $buf): \CurlHandle
    {
        $max = $this->maxBytes;
        $ch = curl_init();
        curl_setopt_array($ch, $this->curlOptions($url) + [
            CURLOPT_URL => $url,
            CURLOPT_FOLLOWLOCATION => true,
            CURLOPT_MAXREDIRS => 5,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_CONNECTTIMEOUT => min(10, $this->timeout),
            CURLOPT_USERAGENT => $this->userAgent,
            CURLOPT_ENCODING => '',
            CURLOPT_SSL_VERIFYPEER => $this->verifySsl,
            CURLOPT_SSL_VERIFYHOST => $this->verifySsl ? 2 : 0,
            CURLOPT_HTTPHEADER => ['Accept: text/html,application/xhtml+xml,*/*;q=0.8', 'Accept-Language: ru,en;q=0.8'],
            CURLOPT_WRITEFUNCTION => static function ($ch, string $chunk) use ($buf, $max): int {
                $buf->data .= $chunk;
                if (strlen($buf->data) > $max) {
                    $buf->truncated = true;

                    return -1;
                }

                return strlen($chunk);
            },
        ]);

        return $ch;
    }

    private function evaluate(Site $site, int $status, string $finalUrl, string $contentType, string $body): CheckResult
    {
        $html = Html::toUtf8($body, $contentType);
        $title = Html::title($html);

        if ($this->requireStatus !== [] && !in_array($status, $this->requireStatus, true)) {
            return new CheckResult(false, 'status', $status, $finalUrl, $title);
        }

        $finalHost = Domains::hostFromUrl($finalUrl);
        if ($this->rejectOffsiteRedirect && $finalHost !== '' && !Domains::sameSite($site->host, $finalHost)) {
            return new CheckResult(false, 'redirect', $status, $finalUrl, $title);
        }
        if (!$this->mustMatch->isEmpty() && !$this->mustMatch->matchesAll($html)) {
            return new CheckResult(false, 'page_must_match', $status, $finalUrl, $title);
        }
        if (!$this->mustNotMatch->isEmpty() && $this->mustNotMatch->matchesAny($html)) {
            return new CheckResult(false, 'page_must_not_match', $status, $finalUrl, $title);
        }

        return new CheckResult(true, '', $status, $finalUrl, $title);
    }
}

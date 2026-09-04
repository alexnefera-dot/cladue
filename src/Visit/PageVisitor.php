<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Live\Proxy;
use YandexSites\Live\ProxyPool;
use YandexSites\Live\UserAgents;
use YandexSites\Model\Site;
use YandexSites\Support\Logger;

/**
 * Заходит на отобранные сайты как посетитель из поиска (с Referer выдачи Яндекса),
 * сохраняет HTML и скриншоты. Несколько вариантов на сайт — через разные прокси
 * и User-Agent, чтобы увидеть, показывает ли сайт разным посетителям разное.
 */
final class PageVisitor
{
    /** @var list<string> */
    private array $userAgents;

    /**
     * @param array<string, mixed> $cfg раздел `visit` конфигурации
     */
    public function __construct(
        private array $cfg,
        private DriverInterface $driver,
        private Logger $log,
        private ?ProxyPool $proxies = null,
        private string $searchBaseUrl = 'https://yandex.ru',
        private string $region = '',
    ) {
        $agents = array_values(array_filter((array) ($cfg['user_agents'] ?? []), 'is_string'));
        $this->userAgents = $agents !== [] ? $agents : UserAgents::DEFAULT;
    }

    public function driver(): DriverInterface
    {
        return $this->driver;
    }

    /**
     * @param array<string, Site> $sites
     */
    public function visit(array $sites): void
    {
        $maxSites = (int) ($this->cfg['max_sites'] ?? 0);
        if ($maxSites > 0) {
            $sites = array_slice($sites, 0, $maxSites, true);
        }
        if ($sites === []) {
            return;
        }

        $variants = max(1, (int) ($this->cfg['variants'] ?? 1));
        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $screenshot = (bool) ($this->cfg['screenshot'] ?? true) && $this->driver->name() === 'playwright';
        $proxies = $this->proxyList();

        $jobs = [];
        foreach ($sites as $key => $site) {
            $url = ($this->cfg['target'] ?? 'found') === 'root' || $site->bestUrl === ''
                ? 'https://' . $site->host . '/'
                : $site->bestUrl;
            $siteDir = $dir . '/' . self::safeName($site->host);
            for ($variant = 1; $variant <= $variants; $variant++) {
                $proxy = $proxies !== [] ? $proxies[($variant - 1) % count($proxies)] : null;
                $jobs[] = new VisitJob(
                    id: $key . "\t" . $variant,
                    siteKey: (string) $key,
                    variant: $variant,
                    url: $url,
                    referer: $this->referer($site),
                    userAgent: $this->userAgents[($variant - 1) % count($this->userAgents)],
                    proxyUrl: $proxy?->url,
                    proxyLabel: $proxy?->label ?? 'direct',
                    htmlFile: $siteDir . '/variant-' . $variant . '.html',
                    screenshotFile: $screenshot ? $siteDir . '/variant-' . $variant . '.png' : null,
                );
            }
        }

        $this->log->info(sprintf(
            'Визиты на сайты через %s: %d страниц (%d сайтов × %d вариантов)…',
            $this->driver->name(),
            count($jobs),
            count($sites),
            $variants,
        ));

        $done = 0;
        $total = count($jobs);
        $results = $this->driver->visit($jobs, $this->driverOptions(), function (VisitJob $job, array $result) use (&$done, $total): void {
            $done++;
            $this->log->debug(sprintf(
                '  [%d/%d] %s (вариант %d, %s) — %s',
                $done,
                $total,
                $job->url,
                $job->variant,
                $job->proxyLabel,
                $result['ok'] ? 'HTTP ' . ($result['status'] ?? '?') . ', ' . mb_substr((string) $result['title'], 0, 60) : 'ошибка: ' . $result['error'],
            ));
        });

        foreach ($jobs as $job) {
            $result = $results[$job->id] ?? ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
            $visit = [
                'variant' => $job->variant,
                'url' => $job->url,
                'proxy' => $job->proxyLabel,
                'user_agent' => $job->userAgent,
                'ok' => (bool) $result['ok'],
                'error' => (string) ($result['error'] ?? ''),
                'status' => $result['status'] ?? null,
                'final_url' => (string) ($result['final_url'] ?? ''),
                'title' => (string) ($result['title'] ?? ''),
                'html_file' => '',
                'screenshot_file' => '',
                'fingerprint' => '',
                'text_length' => 0,
            ];
            if ($visit['ok'] && is_file($job->htmlFile)) {
                $fingerprint = Fingerprint::of((string) file_get_contents($job->htmlFile));
                $visit['html_file'] = $job->htmlFile;
                $visit['fingerprint'] = $fingerprint['hash'];
                $visit['text_length'] = $fingerprint['length'];
                if ($visit['title'] === '') {
                    $visit['title'] = $fingerprint['title'];
                }
                if ($job->screenshotFile !== null && is_file($job->screenshotFile)) {
                    $visit['screenshot_file'] = $job->screenshotFile;
                }
            }
            $sites[$job->siteKey]->visits[] = $visit;
        }
    }

    /**
     * @return list<Proxy>
     */
    private function proxyList(): array
    {
        $setting = $this->cfg['proxy'] ?? null;
        if ($setting === null || $setting === '' || $setting === false) {
            return [];
        }
        if ($setting === 'list') {
            return $this->proxies?->all() ?? [];
        }

        return [Proxy::parse((string) $setting)];
    }

    private function referer(Site $site): string
    {
        $mode = (string) ($this->cfg['referer'] ?? 'serp');
        return match ($mode) {
            'serp' => $this->searchBaseUrl . '/search/?' . http_build_query(
                array_filter(['text' => $site->bestQuery !== '' ? $site->bestQuery : $site->host, 'lr' => $this->region], static fn ($v) => $v !== ''),
                '',
                '&',
                PHP_QUERY_RFC3986,
            ),
            'yandex' => $this->searchBaseUrl . '/',
            'none', '' => '',
            default => $mode,
        };
    }

    /**
     * @return array<string, mixed>
     */
    private function driverOptions(): array
    {
        return [
            'timeout' => (int) ($this->cfg['timeout'] ?? 30),
            'wait_ms' => (int) ($this->cfg['wait_ms'] ?? 0),
            'concurrency' => (int) ($this->cfg['concurrency'] ?? 2),
            'delay_ms' => (int) ($this->cfg['delay_ms'] ?? 0),
            'verify_ssl' => (bool) ($this->cfg['verify_ssl'] ?? true),
            'full_page' => (bool) ($this->cfg['full_page'] ?? false),
            'max_bytes' => (int) ($this->cfg['max_bytes'] ?? 2 * 1024 * 1024),
            'resolve' => array_values((array) ($this->cfg['resolve'] ?? [])),
            'browser_path' => $this->cfg['browser_path'] ?? null,
        ];
    }

    public static function safeName(string $host): string
    {
        $name = preg_replace('~[^a-z0-9.\-]+~i', '_', mb_strtolower($host)) ?? $host;

        return trim($name, '._-') !== '' ? trim($name, '._-') : 'site';
    }
}

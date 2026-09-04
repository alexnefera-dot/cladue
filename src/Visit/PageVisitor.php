<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Filter\Domains;
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
        private mixed $onProgress = null,
    ) {
        $agents = array_values(array_filter((array) ($cfg['user_agents'] ?? []), 'is_string'));
        $this->userAgents = $agents !== [] ? $agents : UserAgents::VISITORS;
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

        if (!empty($this->cfg['crawl'])) {
            $this->crawl($sites);

            return;
        }

        $variants = max(1, (int) ($this->cfg['variants'] ?? 1));
        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $screenshot = (bool) ($this->cfg['screenshot'] ?? true) && $this->driver->name() === 'playwright';
        $proxies = $this->proxyList();
        $proxyIndex = 0;

        $jobs = [];
        foreach ($sites as $key => $site) {
            $url = ($this->cfg['target'] ?? 'found') === 'root' || $site->bestUrl === ''
                ? 'https://' . $site->host . '/'
                : $site->bestUrl;
            $siteDir = $dir . '/' . self::safeName($site->host);
            for ($variant = 1; $variant <= $variants; $variant++) {
                $proxy = $proxies !== [] ? $proxies[$proxyIndex++ % count($proxies)] : null;
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
        $ok = 0;
        $total = count($jobs);
        if ($this->onProgress !== null) {
            ($this->onProgress)(['total' => $total, 'done' => 0, 'ok' => 0, 'current' => '']);
        }
        $results = $this->driver->visit($jobs, $this->driverOptions(), function (VisitJob $job, array $result) use (&$done, &$ok, $total): void {
            $done++;
            if ($result['ok'] ?? false) {
                $ok++;
            }
            if ($this->onProgress !== null) {
                ($this->onProgress)(['total' => $total, 'done' => $done, 'ok' => $ok, 'current' => $job->url]);
            }
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
            $sites[$job->siteKey]->visits[] = $this->assembleVisit($job, $result);
        }

        $this->logSiteSummary($sites);
    }

    /**
     * Собирает запись о визите из результата драйвера. Если задан $siteDomain и страница
     * после редиректов увела на другой сайт — визит помечается ошибкой, а файлы удаляются.
     *
     * @param array<string, mixed> $result
     * @return array<string, mixed>
     */
    private function assembleVisit(VisitJob $job, array $result, string $siteDomain = ''): array
    {
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

        if ($visit['ok'] && $siteDomain !== '' && $visit['final_url'] !== '' && !SiteLinks::sameSite($siteDomain, $visit['final_url'])) {
            @unlink($job->htmlFile);
            if ($job->screenshotFile !== null) {
                @unlink($job->screenshotFile);
            }

            return array_merge($visit, ['ok' => false, 'error' => 'редирект на другой сайт: ' . $visit['final_url']]);
        }

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

        return $visit;
    }

    /**
     * Обход всех страниц из шапки сайта: открывает главную, собирает ссылки меню того же
     * сайта и открывает их. Страницы с редиректом на другой сайт не сохраняются.
     *
     * @param array<string, Site> $sites
     */
    private function crawl(array $sites): void
    {
        $maxPages = max(1, (int) ($this->cfg['max_pages'] ?? 20));
        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $screenshot = (bool) ($this->cfg['screenshot'] ?? true) && $this->driver->name() === 'playwright';
        $proxies = $this->proxyList();
        $proxyIndex = 0;
        $ua = $this->userAgents[0];
        $options = $this->driverOptions();

        $nextProxy = function () use ($proxies, &$proxyIndex): ?Proxy {
            return $proxies !== [] ? $proxies[$proxyIndex++ % count($proxies)] : null;
        };
        $siteDir = static fn (Site $site): string => $dir . '/' . self::safeName($site->host);
        $pageFile = static fn (Site $s, int $i, string $ext): string => $siteDir($s) . '/page-' . $i . '.' . $ext;

        // Этап 1 — главные страницы
        $homeJobs = [];
        foreach ($sites as $key => $site) {
            $url = ($this->cfg['target'] ?? 'found') === 'found' && $site->bestUrl !== '' ? $site->bestUrl : 'https://' . $site->host . '/';
            $proxy = $nextProxy();
            $homeJobs[$key] = new VisitJob(
                id: $key . "\thome",
                siteKey: (string) $key,
                variant: 1,
                url: $url,
                referer: $this->referer($site),
                userAgent: $ua,
                proxyUrl: $proxy?->url,
                proxyLabel: $proxy?->label ?? 'direct',
                htmlFile: $pageFile($site, 1, 'html'),
                screenshotFile: $screenshot ? $pageFile($site, 1, 'png') : null,
            );
        }

        $done = 0;
        $ok = 0;
        $total = count($homeJobs);
        $onResult = function (VisitJob $job, array $result) use (&$done, &$ok, &$total): void {
            $done++;
            if ($result['ok'] ?? false) {
                $ok++;
            }
            if ($this->onProgress !== null) {
                ($this->onProgress)(['total' => $total, 'done' => $done, 'ok' => $ok, 'current' => $job->url]);
            }
            $this->log->debug(sprintf('  [%d/%d] %s — %s', $done, $total, $job->url, $result['ok'] ? 'HTTP ' . ($result['status'] ?? '?') : 'ошибка: ' . $result['error']));
        };

        $this->log->info(sprintf('Обход сайтов (%s): главные страницы %d…', $this->driver->name(), count($homeJobs)));
        $homeResults = $this->driver->visit(array_values($homeJobs), $options, $onResult);

        // Собираем ссылки из шапки каждой главной и готовим задания на внутренние страницы
        $pageJobs = [];
        foreach ($sites as $key => $site) {
            $job = $homeJobs[$key];
            $result = $homeResults[$job->id] ?? ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
            $site->visits[] = $this->assembleVisit($job, $result, $site->domain);

            if (($site->visits[count($site->visits) - 1]['ok'] ?? false) && is_file($job->htmlFile)) {
                $links = SiteLinks::fromHeader((string) file_get_contents($job->htmlFile), $job->url, $site->domain, $maxPages - 1);
                $index = 2;
                foreach ($links as $link) {
                    $proxy = $nextProxy();
                    $pageJobs[] = new VisitJob(
                        id: $key . "\t" . $index,
                        siteKey: (string) $key,
                        variant: $index,
                        url: $link,
                        referer: $job->url,
                        userAgent: $ua,
                        proxyUrl: $proxy?->url,
                        proxyLabel: $proxy?->label ?? 'direct',
                        htmlFile: $pageFile($site, $index, 'html'),
                        screenshotFile: $screenshot ? $pageFile($site, $index, 'png') : null,
                    );
                    $index++;
                }
            }
        }

        // Этап 2 — внутренние страницы из меню
        if ($pageJobs !== []) {
            $total += count($pageJobs);
            $this->log->info(sprintf('Обход сайтов: внутренних страниц из меню %d…', count($pageJobs)));
            $pageResults = $this->driver->visit($pageJobs, $options, $onResult);
            foreach ($pageJobs as $job) {
                $result = $pageResults[$job->id] ?? ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
                $sites[$job->siteKey]->visits[] = $this->assembleVisit($job, $result, $sites[$job->siteKey]->domain);
            }
        }

        $this->logSiteSummary($sites);
    }

    /**
     * Пишет в лог строку-итог по каждому сайту: сколько страниц открыто и первая ошибка.
     *
     * @param array<string, Site> $sites
     */
    private function logSiteSummary(array $sites): void
    {
        foreach ($sites as $site) {
            $s = $site->visitSummary();
            $this->log->info(sprintf(
                '  %-40s страниц: %d из %d%s',
                mb_substr($site->host, 0, 40),
                $s['ok'],
                $s['total'],
                $s['error'] !== '' ? ' — ошибка: ' . mb_substr($s['error'], 0, 100) : '',
            ));
        }
    }

    /**
     * Прокси для визитов: 'list' — общий список по кругу (без прокси — напрямую),
     * null — напрямую, строка — один конкретный прокси.
     *
     * @return list<Proxy>
     */
    private function proxyList(): array
    {
        $setting = array_key_exists('proxy', $this->cfg) ? $this->cfg['proxy'] : 'list';
        if ($setting === null || $setting === '' || $setting === false) {
            return [];
        }
        if ($setting === 'list') {
            return array_values(array_filter($this->proxies?->all() ?? [], static fn (Proxy $p): bool => !$p->disabled));
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

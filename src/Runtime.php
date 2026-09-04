<?php

declare(strict_types=1);

namespace YandexSites;

use YandexSites\Check\SiteChecker;
use YandexSites\Http\HttpClient;
use YandexSites\Live\HtmlResponseParser;
use YandexSites\Live\LiveFetcher;
use YandexSites\Live\ProxyPool;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\RawFetcherInterface;
use YandexSites\Search\ResponseParserInterface;
use YandexSites\Search\RestApiFetcher;
use YandexSites\Search\XmlApiFetcher;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\Logger;
use YandexSites\Visit\CurlDriver;
use YandexSites\Visit\DriverInterface;
use YandexSites\Visit\PageVisitor;
use YandexSites\Visit\PlaywrightDriver;

/**
 * Сборка зависимостей конвейера (источник выдачи, кэш, прокси, проверка сайтов, визиты)
 * из конфигурации. Используется и консольным приложением, и фоновым заданием веб-интерфейса,
 * чтобы поведение совпадало.
 */
final class Runtime
{
    public ?ProxyPool $proxies = null;

    /**
     * @param list<string> $extraProxies дополнительные строки прокси (например, из опций CLI)
     */
    public function __construct(
        private Config $config,
        private Logger $log,
        private array $extraProxies = [],
    ) {
    }

    public function fetcher(bool $offline = false): RawFetcherInterface
    {
        $source = (string) $this->config->get('source');
        $extension = 'xml';

        if ($source === 'live') {
            $pool = $this->proxyPool();
            $fetcher = new LiveFetcher($this->config, new HttpClient((int) $this->config->get('live.timeout')), new HtmlResponseParser(), $pool, $this->log);
            $extension = 'html';
        } else {
            $http = new HttpClient((int) $this->config->get('api.timeout'), (string) $this->config->get('api.user_agent'));
            $parser = new XmlResponseParser();
            if ($source === 'xmlstock') {
                $fetcher = new XmlStockFetcher($this->config, $http, $parser, $this->log);
            } elseif ($this->config->get('api.version') === 'xml') {
                $fetcher = new XmlApiFetcher($this->config, $http, $parser, $this->log);
            } else {
                $fetcher = new RestApiFetcher($this->config, $http, $parser, $this->log);
            }
        }

        if (!$this->config->get('cache.enabled') && !$offline) {
            return $fetcher;
        }

        return new CachingFetcher(
            $fetcher,
            rtrim((string) $this->config->get('cache.dir'), '/\\') . '/' . $source,
            (int) $this->config->get('cache.ttl'),
            $this->cacheKeyParts(),
            $offline,
            $extension,
        );
    }

    public function parser(): ResponseParserInterface
    {
        return $this->config->get('source') === 'live' ? new HtmlResponseParser() : new XmlResponseParser();
    }

    public function checker(): ?SiteChecker
    {
        if (!$this->config->get('site_check.enabled')) {
            return null;
        }

        return new SiteChecker((array) $this->config->get('site_check'), $this->log);
    }

    public function visitor(mixed $onProgress = null): ?PageVisitor
    {
        if (!$this->config->get('visit.enabled')) {
            return null;
        }
        $cfg = (array) $this->config->get('visit');
        $cfg['own_markers'] = \YandexSites\Filter\OwnSites::fromConfig($this->config)->markers();
        $driver = $this->visitDriver($cfg);

        $proxies = null;
        if ((array_key_exists('proxy', $cfg) ? $cfg['proxy'] : 'list') === 'list') {
            $proxies = $this->proxyPool();
        }

        $base = 'https://yandex.ru';
        if ($this->config->get('source') === 'live') {
            $domain = trim((string) $this->config->get('live.domain', 'yandex.ru'));
            $base = rtrim(preg_match('~^https?://~i', $domain) === 1 ? $domain : 'https://' . $domain, '/');
        }

        return new PageVisitor($cfg, $driver, $this->log, $proxies, $base, (string) $this->config->get('search.region', ''), $onProgress);
    }

    /**
     * Общий список прокси: config `proxies` + `proxy_file`, дополнительные строки,
     * а также `live.proxies` / `live.proxy_file` (прежнее место в конфигурации).
     */
    public function proxyPool(): ProxyPool
    {
        if ($this->proxies !== null) {
            return $this->proxies;
        }
        $lines = array_merge(
            array_values((array) $this->config->get('proxies', [])),
            $this->extraProxies,
            array_values((array) $this->config->get('live.proxies', [])),
        );
        foreach ([$this->config->get('proxy_file'), $this->config->get('live.proxy_file')] as $file) {
            if (is_string($file) && $file !== '') {
                if (!is_file($file)) {
                    throw new \RuntimeException("Файл со списком прокси не найден: $file");
                }
                $lines = array_merge($lines, file($file, FILE_IGNORE_NEW_LINES) ?: []);
            }
        }
        $requestsPerProxy = (int) $this->config->get('live.requests_per_proxy');
        $maxFailures = (int) $this->config->get('live.max_proxy_failures');
        $pool = ProxyPool::fromLines($lines, $requestsPerProxy, $maxFailures);
        if ($pool->isEmpty()) {
            $pool = ProxyPool::fromLines(['direct'], $requestsPerProxy, $maxFailures);
        }

        return $this->proxies = $pool;
    }

    /**
     * @param array<string, mixed> $cfg
     */
    private function visitDriver(array $cfg): DriverInterface
    {
        $mode = (string) ($cfg['driver'] ?? 'auto');
        if ($mode === 'curl') {
            return new CurlDriver();
        }
        $playwright = new PlaywrightDriver((string) ($cfg['node'] ?? 'node'));
        $probe = $playwright->probe(isset($cfg['browser_path']) && $cfg['browser_path'] !== '' ? (string) $cfg['browser_path'] : null);
        if ($probe['ok']) {
            $this->log->info('Браузер для визитов: ' . $probe['message']);

            return $playwright;
        }
        if ($mode === 'playwright') {
            throw new \RuntimeException('Playwright недоступен: ' . $probe['message']);
        }
        $this->log->warn('Playwright недоступен (' . $probe['message'] . '), визиты выполняются через curl без выполнения JavaScript');

        return new CurlDriver();
    }

    /**
     * Параметры, от которых зависит содержимое ответа: входят в ключ кэша.
     *
     * @return array<string, mixed>
     */
    private function cacheKeyParts(): array
    {
        $source = (string) $this->config->get('source');
        $parts = ['source' => $source, 'region' => $this->config->get('search.region')];
        if ($source === 'live') {
            $parts['domain'] = $this->config->get('live.domain');

            return $parts;
        }
        foreach (['search_type', 'l10n', 'groups_on_page', 'docs_in_group', 'group_mode', 'max_passages', 'family_mode', 'fix_typo', 'sort', 'period'] as $key) {
            $parts[$key] = $this->config->get('search.' . $key);
        }
        if ($source === 'xmlstock') {
            $parts['domain'] = $this->config->get('xmlstock.domain');
            $parts['device'] = $this->config->get('xmlstock.device');
        } else {
            $parts['api_version'] = $this->config->get('api.version');
        }

        return $parts;
    }
}

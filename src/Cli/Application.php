<?php

declare(strict_types=1);

namespace YandexSites\Cli;

use YandexSites\Check\SiteChecker;
use YandexSites\Config;
use YandexSites\Http\HttpClient;
use YandexSites\Live\HtmlResponseParser;
use YandexSites\Live\LiveFetcher;
use YandexSites\Live\Proxy;
use YandexSites\Live\ProxyPool;
use YandexSites\Output\ReportWriter;
use YandexSites\Runner;
use YandexSites\RunResult;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\RawFetcherInterface;
use YandexSites\Search\ResponseParserInterface;
use YandexSites\Search\RestApiFetcher;
use YandexSites\Search\XmlApiFetcher;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\Logger;
use YandexSites\Support\QueryList;
use YandexSites\Visit\CurlDriver;
use YandexSites\Visit\DriverInterface;
use YandexSites\Visit\PageVisitor;
use YandexSites\Visit\PlaywrightDriver;

/**
 * Консольное приложение: разбор аргументов, сборка зависимостей, вывод итогов.
 */
final class Application
{
    public const VERSION = '1.1.0';

    /** Опции, принимающие значение (остальные — флаги). */
    private const VALUE_OPTIONS = ['queries', 'query', 'config', 'out', 'pages', 'region', 'groups', 'limit', 'delay', 'source', 'proxies', 'proxy', 'parse-html', 'visit-driver', 'variants', 'user-agent', 'save-html'];
    private const FLAG_OPTIONS = ['live', 'visit', 'no-cache', 'offline', 'check-sites', 'check-proxies', 'raw', 'dry-run', 'verbose', 'quiet', 'help', 'version'];
    private const SHORT_OPTIONS = ['q' => 'query', 'c' => 'config', 'o' => 'out', 'v' => 'verbose', 'h' => 'help'];

    private ?Logger $log = null;
    private ?ProxyPool $proxies = null;
    private ?PageVisitor $visitor = null;
    /** @var list<string> прокси из опций --proxy */
    private array $cliProxies = [];

    /**
     * @param list<string> $argv
     */
    public static function main(array $argv): int
    {
        $app = new self();
        try {
            return $app->run($argv);
        } catch (UsageException $e) {
            fwrite(STDERR, 'ОШИБКА: ' . $e->getMessage() . PHP_EOL . 'Справка: php bin/yandex-sites.php --help' . PHP_EOL);

            return 2;
        } catch (\Throwable $e) {
            fwrite(STDERR, 'ОШИБКА: ' . $e->getMessage() . PHP_EOL);
            if ($app->log !== null && $app->log->level() >= Logger::VERBOSE) {
                fwrite(STDERR, $e->getTraceAsString() . PHP_EOL);
            }

            return 1;
        }
    }

    /**
     * @param list<string> $argv
     */
    public function run(array $argv): int
    {
        $opts = $this->parseArgs(array_slice($argv, 1));

        if (isset($opts['help'])) {
            fwrite(STDOUT, $this->usage());

            return 0;
        }
        if (isset($opts['version'])) {
            fwrite(STDOUT, 'yandex-sites ' . self::VERSION . PHP_EOL);

            return 0;
        }
        if (isset($opts['parse-html'])) {
            return $this->parseHtmlFile((string) $opts['parse-html']);
        }

        $level = isset($opts['quiet']) ? Logger::QUIET : (isset($opts['verbose']) ? Logger::VERBOSE : Logger::NORMAL);
        $this->log = $log = new Logger($level);

        $root = dirname(__DIR__, 2);
        Config::loadDotEnv(getcwd() . '/.env');
        Config::loadDotEnv($root . '/.env');

        $configPath = $this->resolveConfigPath($opts['config'] ?? null, $root);
        $config = Config::fromFile($configPath)->withOverrides($this->overrides($opts));
        $this->cliProxies = array_values(array_map('strval', (array) ($opts['proxy'] ?? [])));

        $dryRun = isset($opts['dry-run']);
        $checkProxies = isset($opts['check-proxies']);
        $errors = $config->validate(!$dryRun && !$checkProxies);
        if ($errors !== []) {
            throw new UsageException("некорректная конфигурация:\n  - " . implode("\n  - ", $errors));
        }
        if ($checkProxies) {
            return $this->checkProxies($config, $log, (array) ($opts['query'] ?? []));
        }

        $queries = $this->loadQueries($opts, $log);
        if (isset($opts['limit'])) {
            $queries = array_slice($queries, 0, max(0, (int) $opts['limit']));
        }
        if ($queries === []) {
            throw new UsageException('не задано ни одного запроса: укажите файл (--queries=queries.txt) или --query="текст"');
        }

        $source = (string) $config->get('source');
        $pages = (int) $config->get('search.pages');
        $log->info(sprintf(
            'Конфигурация: %s; источник: %s; регион %s; страниц на запрос: %d%s',
            $configPath ?? 'по умолчанию',
            $this->describeSource($config),
            $config->get('search.region'),
            $pages,
            $source === 'live' ? ' (около 10 результатов на странице)' : sprintf(', результатов на странице: %d', (int) $config->get('search.groups_on_page')),
        ));

        $fetcher = $this->buildFetcher($config, $log, isset($opts['offline']));
        $cache = $fetcher instanceof CachingFetcher ? $fetcher : null;

        $cached = 0;
        if ($cache !== null) {
            foreach ($queries as $query) {
                for ($page = 0; $page < $pages; $page++) {
                    if ($cache->has($query, $page)) {
                        $cached++;
                    }
                }
            }
        }
        $log->info(sprintf(
            'Запросов: %d, будет выполнено до %d обращений к источнику%s',
            count($queries),
            count($queries) * $pages - $cached,
            $cache !== null ? sprintf(' (в кэше уже %d из %d)', $cached, count($queries) * $pages) : ' (кэш отключён)',
        ));
        if ($this->proxies !== null) {
            $labels = array_map(static fn (Proxy $p): string => $p->label, array_slice($this->proxies->all(), 0, 5));
            $log->info(sprintf(
                'Прокси: %d (%s%s)',
                $this->proxies->count(),
                implode(', ', $labels),
                $this->proxies->count() > 5 ? ', …' : '',
            ));
        }

        if ($dryRun) {
            fwrite(STDOUT, 'Пробный запуск, обращений к источнику не будет. Запросы:' . PHP_EOL);
            foreach ($queries as $i => $query) {
                fwrite(STDOUT, sprintf('  %3d. %s%s', $i + 1, $query, PHP_EOL));
            }
            fwrite(STDOUT, 'Фильтры: ' . json_encode($config->get('filters'), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL);

            return 0;
        }

        $checker = $config->get('site_check.enabled') ? new SiteChecker((array) $config->get('site_check'), $log) : null;
        $this->visitor = $config->get('visit.enabled') ? $this->buildVisitor($config, $log) : null;
        $runner = new Runner($config, $fetcher, $this->buildParser($config), $log, $checker, $this->visitor);
        $result = $runner->run($queries);

        $files = $this->writeReports($config, $result);
        $this->printSummary($config, $result, $cache, $files);

        return $result->aborted ? 1 : 0;
    }

    private function describeSource(Config $config): string
    {
        return match ((string) $config->get('source')) {
            'live' => 'живая выдача ' . (preg_replace('~^https?://~', '', (string) $config->get('live.domain')) ?? ''),
            'xmlstock' => 'XMLStock',
            default => $config->get('api.version') === 'xml' ? 'Yandex Search API v1 (XML)' : 'Yandex Search API v2 (REST)',
        };
    }

    /**
     * @param array<string, mixed> $opts
     * @return array<string, mixed>
     */
    private function overrides(array $opts): array
    {
        $overrides = [];
        if (isset($opts['out'])) {
            $overrides['output.dir'] = (string) $opts['out'];
        }
        if (isset($opts['pages'])) {
            $overrides['search.pages'] = (int) $opts['pages'];
        }
        if (isset($opts['region'])) {
            $overrides['search.region'] = (string) $opts['region'];
        }
        if (isset($opts['groups'])) {
            $overrides['search.groups_on_page'] = (int) $opts['groups'];
        }
        if (isset($opts['delay'])) {
            $overrides['api.delay_ms'] = (int) $opts['delay'];
            $overrides['live.delay_ms'] = (int) $opts['delay'];
        }
        if (isset($opts['source'])) {
            $overrides['source'] = (string) $opts['source'];
        }
        if (isset($opts['live'])) {
            $overrides['source'] = 'live';
        }
        if (isset($opts['proxies'])) {
            $overrides['proxy_file'] = (string) $opts['proxies'];
        }
        if (isset($opts['visit'])) {
            $overrides['visit.enabled'] = true;
        }
        if (isset($opts['visit-driver'])) {
            $overrides['visit.driver'] = (string) $opts['visit-driver'];
        }
        if (isset($opts['variants'])) {
            $overrides['visit.variants'] = (int) $opts['variants'];
        }
        if (isset($opts['user-agent'])) {
            $overrides['visit.user_agents'] = [(string) $opts['user-agent']];
            $overrides['site_check.user_agent'] = (string) $opts['user-agent'];
        }
        if (isset($opts['save-html'])) {
            $overrides['live.save_dir'] = (string) $opts['save-html'];
        }
        if (isset($opts['no-cache'])) {
            $overrides['cache.enabled'] = false;
        }
        if (isset($opts['check-sites'])) {
            $overrides['site_check.enabled'] = true;
        }
        if (isset($opts['raw'])) {
            $overrides['output.write_raw'] = true;
        }

        return $overrides;
    }

    private function resolveConfigPath(?string $explicit, string $root): ?string
    {
        if ($explicit !== null) {
            if (!is_file($explicit)) {
                throw new UsageException("файл конфигурации не найден: $explicit");
            }

            return $explicit;
        }
        foreach ([getcwd() . '/config.php', $root . '/config.php'] as $candidate) {
            if (is_file($candidate)) {
                return $candidate;
            }
        }

        return null;
    }

    /**
     * @param array<string, mixed> $opts
     * @return list<string>
     */
    private function loadQueries(array $opts, Logger $log): array
    {
        $lists = [];
        foreach ((array) ($opts['queries'] ?? []) as $file) {
            $lists[] = QueryList::fromFile((string) $file);
        }
        foreach ((array) ($opts['_positional'] ?? []) as $file) {
            $lists[] = QueryList::fromFile((string) $file);
        }
        if (isset($opts['query'])) {
            $lists[] = QueryList::fromLines((array) $opts['query']);
        }

        $queries = QueryList::merge(...$lists);
        $valid = [];
        foreach ($queries as $query) {
            if (mb_strlen($query) > QueryList::MAX_LENGTH) {
                $log->warn(sprintf('Запрос длиннее %d символов пропущен: %s…', QueryList::MAX_LENGTH, mb_substr($query, 0, 60)));
                continue;
            }
            $valid[] = $query;
        }

        return $valid;
    }

    private function buildFetcher(Config $config, Logger $log, bool $offline): RawFetcherInterface
    {
        $source = (string) $config->get('source');
        $extension = 'xml';

        if ($source === 'live') {
            $this->proxies = $this->buildProxyPool($config);
            $fetcher = new LiveFetcher($config, new HttpClient((int) $config->get('live.timeout')), new HtmlResponseParser(), $this->proxies, $log);
            $extension = 'html';
        } else {
            $http = new HttpClient((int) $config->get('api.timeout'), (string) $config->get('api.user_agent'));
            $parser = new XmlResponseParser();
            if ($source === 'xmlstock') {
                $fetcher = new XmlStockFetcher($config, $http, $parser, $log);
            } elseif ($config->get('api.version') === 'xml') {
                $fetcher = new XmlApiFetcher($config, $http, $parser, $log);
            } else {
                $fetcher = new RestApiFetcher($config, $http, $parser, $log);
            }
        }

        if (!$config->get('cache.enabled') && !$offline) {
            return $fetcher;
        }

        return new CachingFetcher(
            $fetcher,
            rtrim((string) $config->get('cache.dir'), '/\\') . '/' . $source,
            (int) $config->get('cache.ttl'),
            $this->cacheKeyParts($config),
            $offline,
            $extension,
        );
    }

    /**
     * Параметры, от которых зависит содержимое ответа: входят в ключ кэша.
     *
     * @return array<string, mixed>
     */
    private function cacheKeyParts(Config $config): array
    {
        $source = (string) $config->get('source');
        $parts = ['source' => $source, 'region' => $config->get('search.region')];
        if ($source === 'live') {
            $parts['domain'] = $config->get('live.domain');

            return $parts;
        }
        foreach (['search_type', 'l10n', 'groups_on_page', 'docs_in_group', 'group_mode', 'max_passages', 'family_mode', 'fix_typo', 'sort', 'period'] as $key) {
            $parts[$key] = $config->get('search.' . $key);
        }
        if ($source === 'xmlstock') {
            $parts['domain'] = $config->get('xmlstock.domain');
            $parts['device'] = $config->get('xmlstock.device');
        } else {
            $parts['api_version'] = $config->get('api.version');
        }

        return $parts;
    }

    /**
     * Общий список прокси: config `proxies` + `proxy_file`, опции --proxy, а также
     * `live.proxies` / `live.proxy_file` (прежнее место в конфигурации).
     */
    private function buildProxyPool(Config $config): ProxyPool
    {
        $lines = array_merge(
            array_values((array) $config->get('proxies', [])),
            $this->cliProxies,
            array_values((array) $config->get('live.proxies', [])),
        );
        foreach ([$config->get('proxy_file'), $config->get('live.proxy_file')] as $file) {
            if (is_string($file) && $file !== '') {
                if (!is_file($file)) {
                    throw new UsageException("файл со списком прокси не найден: $file");
                }
                $lines = array_merge($lines, file($file, FILE_IGNORE_NEW_LINES) ?: []);
            }
        }
        $requestsPerProxy = (int) $config->get('live.requests_per_proxy');
        $maxFailures = (int) $config->get('live.max_proxy_failures');
        $pool = ProxyPool::fromLines($lines, $requestsPerProxy, $maxFailures);
        if ($pool->isEmpty()) {
            $pool = ProxyPool::fromLines(['direct'], $requestsPerProxy, $maxFailures);
        }

        return $pool;
    }

    /**
     * Проверка каждого прокси на живой выдаче: одна страница результатов через каждый.
     *
     * @param list<string> $queries
     */
    private function checkProxies(Config $config, Logger $log, array $queries): int
    {
        $pool = $this->buildProxyPool($config);
        $fetcher = new LiveFetcher($config, new HttpClient((int) $config->get('live.timeout')), new HtmlResponseParser(), $pool, $log);
        $query = $queries !== [] ? (string) $queries[0] : 'пластиковые окна';
        $domain = preg_replace('~^https?://~', '', (string) $config->get('live.domain')) ?? '';
        fwrite(STDOUT, sprintf('Проверка %d прокси на живой выдаче %s (запрос «%s»):%s', $pool->count(), $domain, $query, PHP_EOL));

        $okCount = 0;
        foreach ($pool->all() as $proxy) {
            $result = $fetcher->probe($proxy, $query);
            $verdict = match ($result['kind']) {
                HtmlResponseParser::KIND_SERP => sprintf('OK — выдача получена, результатов: %d', $result['results']),
                HtmlResponseParser::KIND_EMPTY => 'OK — выдача получена, но пустая',
                HtmlResponseParser::KIND_CAPTCHA => 'КАПЧА — Яндекс требует подтверждение, прокси нужен отдых',
                HtmlResponseParser::KIND_BLOCKED => sprintf('ЗАБЛОКИРОВАН — HTTP %s', $result['status'] ?? '?'),
                'error' => 'ОШИБКА — ' . $result['error'],
                default => sprintf('НЕ РАСПОЗНАНО — HTTP %s, страница не похожа на выдачу (сохраните её через --save-html и проверьте --parse-html)', $result['status'] ?? '?'),
            };
            if ($result['ok']) {
                $okCount++;
            }
            fwrite(STDOUT, sprintf('  %-36s %5.1f с  %s%s', $proxy->label, $result['seconds'], $verdict, PHP_EOL));
        }
        fwrite(STDOUT, sprintf('Рабочих прокси: %d из %d%s', $okCount, $pool->count(), PHP_EOL));

        return $okCount > 0 ? 0 : 1;
    }

    private function buildParser(Config $config): ResponseParserInterface
    {
        return $config->get('source') === 'live' ? new HtmlResponseParser() : new XmlResponseParser();
    }

    private function buildVisitor(Config $config, Logger $log): PageVisitor
    {
        $cfg = (array) $config->get('visit');
        $driver = $this->buildVisitDriver($cfg, $log);

        $proxies = null;
        if ((array_key_exists('proxy', $cfg) ? $cfg['proxy'] : 'list') === 'list') {
            $this->proxies ??= $this->buildProxyPool($config);
            $proxies = $this->proxies;
        }

        $base = 'https://yandex.ru';
        if ($config->get('source') === 'live') {
            $domain = trim((string) $config->get('live.domain', 'yandex.ru'));
            $base = rtrim(preg_match('~^https?://~i', $domain) === 1 ? $domain : 'https://' . $domain, '/');
        }

        return new PageVisitor($cfg, $driver, $log, $proxies, $base, (string) $config->get('search.region', ''));
    }

    /**
     * @param array<string, mixed> $cfg
     */
    private function buildVisitDriver(array $cfg, Logger $log): DriverInterface
    {
        $mode = (string) ($cfg['driver'] ?? 'auto');
        if ($mode === 'curl') {
            return new CurlDriver();
        }
        $playwright = new PlaywrightDriver((string) ($cfg['node'] ?? 'node'));
        $probe = $playwright->probe(isset($cfg['browser_path']) && $cfg['browser_path'] !== '' ? (string) $cfg['browser_path'] : null);
        if ($probe['ok']) {
            $log->info('Браузер для визитов: ' . $probe['message']);

            return $playwright;
        }
        if ($mode === 'playwright') {
            throw new UsageException('Playwright недоступен: ' . $probe['message']);
        }
        $log->warn('Playwright недоступен (' . $probe['message'] . '), визиты выполняются через curl без выполнения JavaScript');

        return new CurlDriver();
    }

    /**
     * Отладка разбора живой выдачи: разобрать сохранённую HTML-страницу и показать результаты.
     */
    private function parseHtmlFile(string $path): int
    {
        if (!is_file($path)) {
            throw new UsageException("файл не найден: $path");
        }
        $html = (string) file_get_contents($path);
        $parser = new HtmlResponseParser();
        $kind = $parser->classify($html, '', 200);
        fwrite(STDOUT, 'Тип страницы: ' . $kind . PHP_EOL);
        if ($kind !== HtmlResponseParser::KIND_SERP && $kind !== HtmlResponseParser::KIND_EMPTY) {
            return 1;
        }
        $page = $parser->parse($html, basename($path), 0);
        fwrite(STDOUT, sprintf(
            'Результатов: %d%s, пропущено (реклама, блоки без ссылок): %d, есть следующая страница: %s%s',
            count($page->results),
            $page->found !== null ? ', всего найдено около ' . $page->found : '',
            $page->groups - count($page->results),
            $page->hasMore === null ? 'неизвестно' : ($page->hasMore ? 'да' : 'нет'),
            PHP_EOL,
        ));
        foreach ($page->results as $r) {
            fwrite(STDOUT, sprintf('%3d. %s%s     %s%s     %s%s', $r->position, $r->url, PHP_EOL, $r->title, PHP_EOL, mb_substr($r->snippet, 0, 160), PHP_EOL));
        }

        return 0;
    }

    /**
     * @return list<string> пути записанных файлов
     */
    private function writeReports(Config $config, RunResult $result): array
    {
        $dir = rtrim((string) $config->get('output.dir'), '/\\');
        $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
        $files = [];

        $csv = $dir . '/' . $config->get('output.csv');
        $writer->writeCsv($result->sites, $csv);
        $files[] = $csv;

        $json = $dir . '/' . $config->get('output.json');
        $writer->writeJson($result->sites, $json, [
            'stats' => $result->stats,
            'errors' => $result->errors,
            'aborted' => $result->aborted,
            'source' => $config->get('source'),
            'search' => $config->get('search'),
            'filters' => $config->get('filters'),
            'proxies' => $this->proxies?->stats() ?? [],
        ]);
        $files[] = $json;

        $domains = $dir . '/' . $config->get('output.domains');
        $writer->writeDomains($result->sites, $domains);
        $files[] = $domains;

        if ($config->get('output.write_raw')) {
            $raw = $dir . '/' . $config->get('output.raw_csv');
            $writer->writeRawCsv($result->raw, $raw);
            $files[] = $raw;
        }

        return $files;
    }

    /**
     * @param list<string> $files
     */
    private function printSummary(Config $config, RunResult $result, ?CachingFetcher $cache, array $files): void
    {
        $stats = $result->stats;
        $out = [];
        $out[] = '';
        $out[] = sprintf(
            'Запросов обработано: %d из %d, обращений к источнику: %d%s, результатов в выдаче: %d',
            $stats['queries_done'],
            $stats['queries'],
            $cache !== null ? $cache->misses : $stats['requests'],
            $cache !== null ? sprintf(' (из кэша: %d)', $cache->hits) : '',
            $stats['results'],
        );
        if ($stats['rejected'] !== []) {
            $parts = [];
            arsort($stats['rejected']);
            foreach ($stats['rejected'] as $reason => $count) {
                $parts[] = sprintf('%s — %d', $reason, $count);
            }
            $out[] = 'Отклонено: ' . implode(', ', $parts);
        }
        $out[] = sprintf('Сайтов найдено: %d, отобрано: %d', $stats['sites_total'], $stats['sites_selected']);

        $top = array_slice($result->sites, 0, 10);
        if ($top !== []) {
            $out[] = 'Первые сайты:';
            foreach ($top as $site) {
                $out[] = sprintf(
                    '  %-40s запросов: %d, лучшая позиция: %s',
                    $site->host,
                    $site->queryCount(),
                    $site->bestPosition ?? '-',
                );
            }
        }
        if ($this->visitor !== null) {
            $visited = 0;
            $pages = 0;
            $differ = 0;
            foreach ($result->sites as $site) {
                if ($site->visits === []) {
                    continue;
                }
                $visited++;
                foreach ($site->visits as $visit) {
                    if ($visit['ok'] ?? false) {
                        $pages++;
                    }
                }
                if ($site->variantCount() > 1) {
                    $differ++;
                }
            }
            $out[] = sprintf(
                'Визиты (%s): сайтов %d, страниц сохранено %d в %s%s',
                $this->visitor->driver()->name(),
                $visited,
                $pages,
                $config->get('visit.dir'),
                (int) $config->get('visit.variants') > 1 ? sprintf(', сайтов с разными вариантами страницы: %d', $differ) : '',
            );
        }
        if ($this->proxies !== null) {
            $out[] = 'Прокси:';
            foreach ($this->proxies->stats() as $s) {
                $state = $s['disabled'] ? ', отключён' : ($s['cooldown'] > 0 ? sprintf(', отдыхает ещё %d с', $s['cooldown']) : '');
                $out[] = sprintf('  %-34s запросов: %d, капч: %d, ошибок: %d%s', $s['proxy'], $s['requests'], $s['captchas'], $s['failures'], $state);
            }
        }
        if ($result->errors !== []) {
            $out[] = sprintf('Ошибок: %d (подробности в %s)', count($result->errors), $config->get('output.json'));
        }
        $out[] = 'Файлы: ' . implode(', ', $files);
        fwrite(STDOUT, implode(PHP_EOL, $out) . PHP_EOL);
    }

    /**
     * Разбор аргументов: --key=value, --key value, --flag, -q value, позиционные — файлы запросов.
     *
     * @param list<string> $args
     * @return array<string, mixed>
     */
    public function parseArgs(array $args): array
    {
        $opts = [];
        $count = count($args);
        for ($i = 0; $i < $count; $i++) {
            $arg = $args[$i];
            if ($arg === '--') {
                foreach (array_slice($args, $i + 1) as $rest) {
                    $opts['_positional'][] = $rest;
                }
                break;
            }
            if (str_starts_with($arg, '--')) {
                $name = substr($arg, 2);
                $value = null;
                if (str_contains($name, '=')) {
                    [$name, $value] = explode('=', $name, 2);
                }
            } elseif (str_starts_with($arg, '-') && strlen($arg) === 2) {
                $name = self::SHORT_OPTIONS[$arg[1]] ?? null;
                if ($name === null) {
                    throw new UsageException("неизвестная опция: $arg");
                }
                $value = null;
            } else {
                $opts['_positional'][] = $arg;
                continue;
            }

            if (in_array($name, self::FLAG_OPTIONS, true)) {
                if ($value !== null) {
                    throw new UsageException("опция --$name не принимает значение");
                }
                $opts[$name] = true;
                continue;
            }
            if (!in_array($name, self::VALUE_OPTIONS, true)) {
                throw new UsageException("неизвестная опция: $arg");
            }
            if ($value === null) {
                if ($i + 1 >= $count) {
                    throw new UsageException("опция --$name требует значение");
                }
                $value = $args[++$i];
            }
            if (in_array($name, ['query', 'queries', 'proxy'], true)) {
                $opts[$name][] = $value;
            } else {
                $opts[$name] = $value;
            }
        }

        return $opts;
    }

    public function usage(): string
    {
        return <<<TXT
        yandex-sites — прогоняет список запросов через выдачу Яндекса и отбирает сайты.

        Использование:
          php bin/yandex-sites.php [опции] [queries.txt ...]

        Источники запросов (можно сочетать):
          --queries=FILE        файл с запросами, по одному в строке (# — комментарий); можно указывать несколько раз
          -q, --query="ТЕКСТ"   один запрос из командной строки; можно указывать несколько раз
          --limit=N             обработать только первые N запросов (для пробы)

        Источник выдачи:
          --source=api|xmlstock|live
                                api — Yandex Search API (по умолчанию), xmlstock — сервис XMLStock,
                                live — живая выдача yandex.ru как у обычного пользователя (через прокси)
          --live                то же, что --source=live

        Прокси (общий список для живой выдачи и визитов, используются по кругу):
          --proxies=FILE        файл со списком прокси, по одному в строке (см. proxies.example.txt)
          --proxy=АДРЕС         добавить прокси, например http://host:port:user:pass; можно указывать несколько раз
          --check-proxies       проверить каждый прокси одним запросом к живой выдаче и выйти
          --save-html=DIR       сохранять все полученные страницы живой выдачи (и капчу) с метаданными — для отладки

        Настройки:
          -c, --config=FILE     файл конфигурации (по умолчанию ./config.php, если есть; см. config.example.php)
          -o, --out=DIR         каталог для результатов (по умолчанию out/)
          --pages=N             страниц выдачи на запрос (по умолчанию 1; в живой выдаче страница — 10 результатов)
          --groups=N            результатов (сайтов) на странице для API/XMLStock, 1–100 (по умолчанию 50)
          --region=ID           регион поиска: 213 — Москва, 2 — Санкт-Петербург, 225 — Россия
          --delay=MS            пауза между обращениями к источнику в миллисекундах
          --check-sites         проверить отобранные сайты по HTTP (раздел site_check в конфигурации)
          --raw                 дополнительно записать все результаты выдачи с причинами отклонения (results.csv)

        Визиты на отобранные сайты (как посетитель из поиска; раздел visit в конфигурации):
          --visit               зайти на каждый сайт, сохранить HTML и скриншот в out/pages/<сайт>/
          --visit-driver=X      playwright — headless Chromium с выполнением JS (нужны Node.js и npm i playwright),
                                curl — без JS, auto — Playwright, если доступен (по умолчанию)
          --variants=N          зайти на каждый сайт N раз с разными прокси и User-Agent, чтобы увидеть разные версии страницы:
                                первый визит — как робот Яндекса (YandexBot), следующие — как браузеры
          --user-agent="…"      свой User-Agent для визитов и проверки сайтов вместо YandexBot

        Кэш ответов:
          --no-cache            не использовать кэш
          --offline             работать только по кэшу, без обращений к источнику

        Прочее:
          --parse-html=FILE     разобрать сохранённую HTML-страницу выдачи и показать результаты (отладка)
          --dry-run             показать запросы и настройки, ничего не запрашивать
          -v, --verbose         подробный вывод (все результаты по мере получения)
          --quiet               только ошибки
          -h, --help            эта справка            --version версия

        Доступ к источникам задаётся переменными окружения (или файлом .env, или в config.php):
          Yandex Search API — YANDEX_FOLDER_ID и YANDEX_API_KEY; XMLStock — XMLSTOCK_USER и XMLSTOCK_KEY.
        Результаты: sites.csv, sites.json, domains.txt.

        TXT;
    }
}

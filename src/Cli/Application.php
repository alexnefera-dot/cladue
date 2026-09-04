<?php

declare(strict_types=1);

namespace YandexSites\Cli;

use YandexSites\Check\SiteChecker;
use YandexSites\Config;
use YandexSites\Http\HttpClient;
use YandexSites\Output\ReportWriter;
use YandexSites\Runner;
use YandexSites\RunResult;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\RestApiFetcher;
use YandexSites\Search\XmlApiFetcher;
use YandexSites\Search\XmlFetcherInterface;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Support\Logger;
use YandexSites\Support\QueryList;

/**
 * Консольное приложение: разбор аргументов, сборка зависимостей, вывод итогов.
 */
final class Application
{
    public const VERSION = '1.0.0';

    /** Опции, принимающие значение (остальные — флаги). */
    private const VALUE_OPTIONS = ['queries', 'query', 'config', 'out', 'pages', 'region', 'groups', 'limit', 'delay'];
    private const FLAG_OPTIONS = ['no-cache', 'offline', 'check-sites', 'raw', 'dry-run', 'verbose', 'quiet', 'help', 'version'];
    private const SHORT_OPTIONS = ['q' => 'query', 'c' => 'config', 'o' => 'out', 'v' => 'verbose', 'h' => 'help'];

    private ?Logger $log = null;

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

        $level = isset($opts['quiet']) ? Logger::QUIET : (isset($opts['verbose']) ? Logger::VERBOSE : Logger::NORMAL);
        $this->log = $log = new Logger($level);

        $root = dirname(__DIR__, 2);
        Config::loadDotEnv(getcwd() . '/.env');
        Config::loadDotEnv($root . '/.env');

        $configPath = $this->resolveConfigPath($opts['config'] ?? null, $root);
        $config = Config::fromFile($configPath)->withOverrides($this->overrides($opts));

        $dryRun = isset($opts['dry-run']);
        $errors = $config->validate(!$dryRun);
        if ($errors !== []) {
            throw new UsageException("некорректная конфигурация:\n  - " . implode("\n  - ", $errors));
        }

        $queries = $this->loadQueries($opts, $log);
        if (isset($opts['limit'])) {
            $queries = array_slice($queries, 0, max(0, (int) $opts['limit']));
        }
        if ($queries === []) {
            throw new UsageException('не задано ни одного запроса: укажите файл (--queries=queries.txt) или --query="текст"');
        }

        $pages = (int) $config->get('search.pages');
        $log->info(sprintf(
            'Конфигурация: %s; API %s; регион %s; страниц на запрос: %d, результатов на странице: %d',
            $configPath ?? 'по умолчанию',
            $config->get('api.version') === 'xml' ? 'v1 (XML)' : 'v2 (REST)',
            $config->get('search.region'),
            $pages,
            (int) $config->get('search.groups_on_page'),
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
            'Запросов: %d, будет выполнено до %d обращений к API%s',
            count($queries),
            count($queries) * $pages - $cached,
            $cache !== null ? sprintf(' (в кэше уже %d из %d)', $cached, count($queries) * $pages) : ' (кэш отключён)',
        ));

        if ($dryRun) {
            fwrite(STDOUT, 'Пробный запуск, обращений к API не будет. Запросы:' . PHP_EOL);
            foreach ($queries as $i => $query) {
                fwrite(STDOUT, sprintf('  %3d. %s%s', $i + 1, $query, PHP_EOL));
            }
            fwrite(STDOUT, 'Фильтры: ' . json_encode($config->get('filters'), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL);

            return 0;
        }

        $checker = $config->get('site_check.enabled') ? new SiteChecker((array) $config->get('site_check'), $log) : null;
        $runner = new Runner($config, $fetcher, new XmlResponseParser(), $log, $checker);
        $result = $runner->run($queries);

        $files = $this->writeReports($config, $result);
        $this->printSummary($config, $result, $cache, $files);

        return $result->aborted ? 1 : 0;
    }

    /**
     * @param array<string, mixed> $opts
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

    private function buildFetcher(Config $config, Logger $log, bool $offline): XmlFetcherInterface
    {
        $http = new HttpClient((int) $config->get('api.timeout'), (string) $config->get('api.user_agent'));
        $parser = new XmlResponseParser();
        $fetcher = $config->get('api.version') === 'xml'
            ? new XmlApiFetcher($config, $http, $parser, $log)
            : new RestApiFetcher($config, $http, $parser, $log);

        if (!$config->get('cache.enabled') && !$offline) {
            return $fetcher;
        }

        $keyParts = (array) $config->get('search');
        $keyParts['api_version'] = $config->get('api.version');

        return new CachingFetcher(
            $fetcher,
            rtrim((string) $config->get('cache.dir'), '/\\'),
            (int) $config->get('cache.ttl'),
            $keyParts,
            $offline,
        );
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
            'search' => $config->get('search'),
            'filters' => $config->get('filters'),
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
            'Запросов обработано: %d из %d, обращений к API: %d%s, результатов в выдаче: %d',
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
            if (in_array($name, ['query', 'queries'], true)) {
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
        yandex-sites — прогоняет список запросов через Yandex Search API и отбирает сайты из выдачи.

        Использование:
          php bin/yandex-sites.php [опции] [queries.txt ...]

        Источники запросов (можно сочетать):
          --queries=FILE        файл с запросами, по одному в строке (# — комментарий); можно указывать несколько раз
          -q, --query="ТЕКСТ"   один запрос из командной строки; можно указывать несколько раз
          --limit=N             обработать только первые N запросов (для пробы)

        Настройки:
          -c, --config=FILE     файл конфигурации (по умолчанию ./config.php, если есть; см. config.example.php)
          -o, --out=DIR         каталог для результатов (по умолчанию out/)
          --pages=N             страниц выдачи на запрос (по умолчанию 1)
          --groups=N            результатов (сайтов) на странице, 1–100 (по умолчанию 50)
          --region=ID           регион поиска: 213 — Москва, 2 — Санкт-Петербург, 225 — Россия
          --delay=MS            пауза между обращениями к API в миллисекундах (по умолчанию 250)
          --check-sites         проверить отобранные сайты по HTTP (раздел site_check в конфигурации)
          --raw                 дополнительно записать все результаты выдачи с причинами отклонения (results.csv)

        Кэш ответов API:
          --no-cache            не использовать кэш
          --offline             работать только по кэшу, без обращений к API

        Прочее:
          --dry-run             показать запросы и настройки, ничего не запрашивать
          -v, --verbose         подробный вывод        --quiet   только ошибки
          -h, --help            эта справка            --version версия

        Доступ к API задаётся переменными окружения YANDEX_FOLDER_ID и YANDEX_API_KEY
        (или файлом .env, или в config.php). Результаты: sites.csv, sites.json, domains.txt.

        TXT;
    }
}

#!/usr/bin/env php
<?php

declare(strict_types=1);

/*
 * Фоновое задание для веб-интерфейса: выполняет один сбор (или повторяет его каждые N часов),
 * пишет прогресс в JSON-файл состояния и результаты в каталог прогона.
 *
 *   php bin/run-job.php --settings=runs/current/settings.json [--status=runs/current/status.json]
 *
 * Обычно запускается панелью (bin/panel.php) в фоне; можно запускать и вручную.
 * Остановка: создать файл stop рядом со status.json (панель делает это по кнопке «Стоп»).
 */

error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);

$root = dirname(__DIR__);
if (is_file($root . '/vendor/autoload.php')) {
    require $root . '/vendor/autoload.php';
} else {
    spl_autoload_register(static function (string $class) use ($root): void {
        $prefix = 'YandexSites\\';
        if (str_starts_with($class, $prefix)) {
            $file = $root . '/src/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
            if (is_file($file)) {
                require $file;
            }
        }
    });
}

use YandexSites\Config;
use YandexSites\Filter\DefaultExclusions;
use YandexSites\Output\ReportWriter;
use YandexSites\Runner;
use YandexSites\Runtime;
use YandexSites\Support\Logger;
use YandexSites\Support\Progress;

$settingsFile = null;
$statusFile = null;
foreach (array_slice($argv, 1) as $arg) {
    if (str_starts_with($arg, '--settings=')) {
        $settingsFile = substr($arg, 11);
    } elseif (str_starts_with($arg, '--status=')) {
        $statusFile = substr($arg, 9);
    }
}
if ($settingsFile === null || !is_file($settingsFile)) {
    fwrite(STDERR, "Не задан или не найден файл настроек (--settings=FILE)\n");
    exit(2);
}
$runDir = dirname($settingsFile);
$statusFile ??= $runDir . '/status.json';
$stopFile = $runDir . '/stop';

$settings = json_decode((string) file_get_contents($settingsFile), true);
if (!is_array($settings)) {
    fwrite(STDERR, "Некорректный файл настроек\n");
    exit(2);
}

Config::loadDotEnv(getcwd() . '/.env');
Config::loadDotEnv($root . '/.env');

$repeatHours = (float) ($settings['repeat_hours'] ?? 0);
$logFile = $runDir . '/run.log';

$progress = new Progress($statusFile, [
    'state' => 'starting',
    'pid' => getmypid(),
    'run' => 0,
    'repeat_hours' => $repeatHours,
    'started_at' => date(DATE_ATOM),
    'settings' => $settings,
]);

/**
 * @return array<string, mixed>
 */
function buildOverrides(array $s, string $runDir): array
{
    $overrides = [
        'output.dir' => $runDir,
        'output.write_raw' => true,
        'cache.dir' => dirname($runDir, 2) . '/cache',
    ];
    if (isset($s['source'])) {
        $overrides['source'] = (string) $s['source'];
    }
    if (isset($s['region']) && $s['region'] !== '') {
        $overrides['search.region'] = (string) $s['region'];
    }
    if (isset($s['pages'])) {
        $overrides['search.pages'] = max(1, (int) $s['pages']);
    }
    if (isset($s['groups_on_page'])) {
        $overrides['search.groups_on_page'] = max(1, min(100, (int) $s['groups_on_page']));
    }
    $overrides['filters.unique_by'] = ($s['dedupe_domain'] ?? true) ? 'domain' : 'host';
    if (isset($s['domain_scope'])) {
        $overrides['filters.domain_scope'] = (string) $s['domain_scope'];
    }
    if (isset($s['min_queries'])) {
        $overrides['filters.min_queries'] = max(1, (int) $s['min_queries']);
    }
    if (isset($s['allowed_tlds']) && is_array($s['allowed_tlds']) && $s['allowed_tlds'] !== []) {
        $overrides['filters.allowed_tlds'] = array_values(array_map('strval', $s['allowed_tlds']));
    }
    $exclude = DefaultExclusions::LIST;
    if (isset($s['exclude_extra']) && is_array($s['exclude_extra'])) {
        foreach ($s['exclude_extra'] as $domain) {
            $domain = trim((string) $domain);
            if ($domain !== '') {
                $exclude[] = $domain;
            }
        }
    }
    $overrides['filters.exclude_domains'] = $exclude;

    $overrides['visit.enabled'] = (bool) ($s['visit'] ?? false);
    if (isset($s['variants'])) {
        $overrides['visit.variants'] = max(1, (int) $s['variants']);
    }
    if (isset($s['visit_driver'])) {
        $overrides['visit.driver'] = (string) $s['visit_driver'];
    }
    if (isset($s['visit_dir'])) {
        $overrides['visit.dir'] = (string) $s['visit_dir'];
    } else {
        $overrides['visit.dir'] = $runDir . '/pages';
    }
    if (isset($s['proxies_file']) && (string) $s['proxies_file'] !== '') {
        $overrides['proxy_file'] = (string) $s['proxies_file'];
    }

    return $overrides;
}

/**
 * @param list<\YandexSites\Model\Site> $sites
 * @return list<array<string, mixed>>
 */
function previewSites(array $sites, int $limit = 200): array
{
    $rows = [];
    foreach (array_slice($sites, 0, $limit) as $site) {
        $data = $site->toArray();
        $visit = $site->firstVisit();
        $rows[] = [
            'host' => $data['host'],
            'domain' => $data['domain'],
            'url' => $data['url'],
            'title' => $data['title'],
            'queries_count' => $data['queries_count'],
            'best_position' => $data['best_position'],
            'variants' => $data['variants'],
            'visit_ok' => $visit !== null ? (bool) $visit['ok'] : null,
            'visit_status' => $visit['status'] ?? null,
        ];
    }

    return $rows;
}

function stopped(string $stopFile): bool
{
    return is_file($stopFile);
}

$run = 0;
$configPath = is_file(getcwd() . '/config.php') ? getcwd() . '/config.php' : (is_file($root . '/config.php') ? $root . '/config.php' : null);

while (true) {
    if (stopped($stopFile)) {
        $progress->update(['state' => 'stopped', 'phase' => 'stopped'], true);
        break;
    }
    $run++;
    $logHandle = fopen($logFile, 'a');
    $logger = new Logger(Logger::NORMAL, $logHandle ?: STDERR);
    $progress->update([
        'state' => 'running',
        'run' => $run,
        'phase' => 'starting',
        'run_started_at' => date(DATE_ATOM),
        'message' => '',
        'visit' => null,
        'sites' => [],
    ], true);

    try {
        $config = Config::fromFile($configPath)->withOverrides(buildOverrides($settings, $runDir));
        $errors = $config->validate(true);
        if ($errors !== []) {
            throw new RuntimeException('Проверьте настройки: ' . implode('; ', $errors));
        }
        $queries = array_values(array_filter(array_map('trim', (array) ($settings['queries'] ?? [])), static fn (string $q): bool => $q !== '' && !str_starts_with($q, '#')));
        if ($queries === []) {
            throw new RuntimeException('Не задано ни одного запроса');
        }

        $runtime = new Runtime($config, $logger);
        $onSearch = static function (array $event) use ($progress): void {
            $progress->update($event);
        };
        $onVisit = static function (array $event) use ($progress): void {
            $progress->update(['phase' => 'visit', 'visit' => $event]);
        };

        $fetcher = $runtime->fetcher();
        $checker = $runtime->checker();
        $visitor = $runtime->visitor($onVisit);
        $runner = new Runner($config, $fetcher, $runtime->parser(), $logger, $checker, $visitor, $onSearch);

        $logger->info(sprintf('Прогон %d: запросов %d, источник %s', $run, count($queries), $config->get('source')));
        $result = $runner->run($queries);

        $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
        $writer->writeCsv($result->sites, $runDir . '/sites.csv');
        $writer->writeJson($result->sites, $runDir . '/sites.json', [
            'stats' => $result->stats,
            'errors' => $result->errors,
            'source' => $config->get('source'),
            'settings' => $settings,
            'proxies' => $runtime->proxies?->stats() ?? [],
        ]);
        $writer->writeDomains($result->sites, $runDir . '/domains.txt');
        $writer->writeRawCsv($result->raw, $runDir . '/results.csv');

        $progress->update([
            'state' => $result->aborted ? 'error' : 'done',
            'phase' => 'done',
            'stats' => $result->stats,
            'errors' => $result->errors,
            'aborted' => $result->aborted,
            'proxies' => $runtime->proxies?->stats() ?? [],
            'sites' => previewSites($result->sites),
            'run_finished_at' => date(DATE_ATOM),
            'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv'],
            'message' => $result->aborted ? 'Прогон остановлен из-за ошибки источника, см. лог' : '',
        ], true);
        $logger->info(sprintf('Прогон %d завершён: отобрано сайтов %d', $run, $result->stats['sites_selected']));
    } catch (Throwable $e) {
        $progress->update([
            'state' => 'error',
            'phase' => 'error',
            'message' => $e->getMessage(),
            'run_finished_at' => date(DATE_ATOM),
        ], true);
        $logger->error($e->getMessage());
    }
    if (is_resource($logHandle)) {
        fclose($logHandle);
    }

    if ($repeatHours <= 0 || stopped($stopFile)) {
        if (stopped($stopFile)) {
            $progress->update(['state' => 'stopped', 'phase' => 'stopped'], true);
        }
        break;
    }

    $next = time() + (int) round($repeatHours * 3600);
    $progress->update(['state' => 'waiting', 'phase' => 'waiting', 'next_run_at' => date(DATE_ATOM, $next)], true);
    while (time() < $next) {
        if (stopped($stopFile)) {
            break;
        }
        $progress->update(['countdown_seconds' => $next - time()]);
        sleep((int) min(5, max(1, $next - time())));
    }
    if (stopped($stopFile)) {
        $progress->update(['state' => 'stopped', 'phase' => 'stopped'], true);
        break;
    }
}

exit(0);

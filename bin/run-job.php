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
use YandexSites\Content\ContentCleaner;
use YandexSites\Filter\DefaultExclusions;
use YandexSites\Output\ReportWriter;
use YandexSites\Runner;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Runtime;
use YandexSites\Support\DomainLedger;
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

// Повтор по таймеру имеет смысл только для сбора; выгрузка и очистка контента — одноразовые.
$repeatHours = in_array((string) ($settings['stage'] ?? 'collect'), ['download', 'clean'], true)
    ? 0.0
    : (float) ($settings['repeat_hours'] ?? 0);
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
    // Параметры XMLStock: устройство (mobile/desktop/tablet), домен Яндекса, произвольные доп. параметры.
    if (isset($s['xmlstock_device']) && (string) $s['xmlstock_device'] !== '') {
        $overrides['xmlstock.device'] = (string) $s['xmlstock_device'];
    }
    if (isset($s['xmlstock_domain']) && (string) $s['xmlstock_domain'] !== '') {
        $overrides['xmlstock.domain'] = (string) $s['xmlstock_domain'];
    }
    if (isset($s['xmlstock_extra']) && is_array($s['xmlstock_extra'])) {
        $extra = [];
        foreach ($s['xmlstock_extra'] as $key => $value) {
            $key = trim((string) $key);
            if ($key !== '' && is_scalar($value)) {
                $extra[$key] = (string) $value;
            }
        }
        $overrides['xmlstock.extra_params'] = $extra;
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
    // «Топ N выдачи»: берём только первые N результатов каждого запроса (одна страница по N).
    $top = (int) ($s['top'] ?? 10);
    if ($top > 0) {
        $overrides['search.groups_on_page'] = min(100, $top);
        $overrides['search.pages'] = 1;
        $overrides['filters.max_position'] = $top;
    }
    $overrides['filters.unique_by'] = ($s['dedupe_domain'] ?? true) ? 'domain' : 'host';
    if (isset($s['domain_scope'])) {
        $overrides['filters.domain_scope'] = (string) $s['domain_scope'];
    }
    if (isset($s['min_queries'])) {
        $overrides['filters.min_queries'] = max(1, (int) $s['min_queries']);
    }
    // Панель — источник истины по зонам: если ключ передан (даже пустой список) — применяем как есть.
    // Пустой список = любые зоны. Ручной запуск run-job без ключа оставляет значение из config.php.
    if (array_key_exists('allowed_tlds', $s)) {
        $overrides['filters.allowed_tlds'] = is_array($s['allowed_tlds']) ? array_values(array_map('strval', $s['allowed_tlds'])) : [];
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

    $stage = (string) ($s['stage'] ?? 'collect');
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
    // Обход всех страниц из шапки сайта.
    $overrides['visit.crawl'] = (bool) ($s['crawl'] ?? false);
    if (isset($s['max_pages'])) {
        $overrides['visit.max_pages'] = max(1, (int) $s['max_pages']);
    }
    // Продвинутое/для тестов: сопоставление host:port:ip для визитов (CURLOPT_RESOLVE / Chromium).
    if (isset($s['visit_resolve']) && is_array($s['visit_resolve'])) {
        $overrides['visit.resolve'] = array_values(array_map('strval', $s['visit_resolve']));
    }

    // Когда открываем сайты:
    //  - «Сборка + выгрузка» (both) — полная выгрузка страниц;
    //  - «Сборка» (collect) с включённым предпросмотром — только скриншот главной каждого уникального
    //    домена (без обхода), чтобы оценить объём и сразу увидеть наши сайты. Складываем в runs/current/preview.
    if ($stage === 'both') {
        $overrides['visit.enabled'] = (bool) ($s['visit'] ?? true);
    } elseif ($stage === 'collect' && (bool) ($s['preview_shots'] ?? true)) {
        $overrides['visit.enabled'] = true;
        $overrides['visit.crawl'] = false;
        $overrides['visit.variants'] = 1;
        $overrides['visit.screenshot'] = true;
        $overrides['visit.max_pages'] = 0;
        $overrides['visit.dir'] = $runDir . '/preview';
    } else {
        $overrides['visit.enabled'] = false;
    }

    return $overrides;
}

/**
 * @param list<\YandexSites\Model\Site> $sites
 * @return list<array<string, mixed>>
 */
function previewSites(array $sites, string $runDir = '', int $limit = 300): array
{
    $rel = static function (string $abs) use ($runDir): string {
        $prefix = rtrim($runDir, '/\\') . '/';
        return $runDir !== '' && str_starts_with($abs, $prefix) ? substr($abs, strlen($prefix)) : $abs;
    };
    $rows = [];
    foreach (array_slice($sites, 0, $limit) as $site) {
        $data = $site->toArray();
        $summary = $site->visitSummary();
        $own = (bool) ($data['own'] ?? false);
        // Для показа берём первый успешный визит, а если такого нет (ошибка/наш) — самый первый визит:
        // так остаётся ссылка на скриншот (у «наших» он сохранён) и видна причина ошибки.
        $visit = $site->firstVisit() ?? ($site->visits[0] ?? null);
        $rows[] = [
            'host' => $data['host'],
            'domain' => $data['domain'],
            'url' => $data['url'],
            'title' => $data['title'],
            'queries_count' => $data['queries_count'],
            'best_position' => $data['best_position'],
            'variants' => $data['variants'],
            'own' => $own,
            'pages_ok' => $own ? null : ($summary['total'] > 0 ? $summary['ok'] : null),
            'pages_total' => $own ? null : ($summary['total'] > 0 ? $summary['total'] : null),
            'page_error' => $own ? 'исключён как наш' : $summary['error'],
            'html' => !$own && $visit !== null && ($visit['html_file'] ?? '') !== '' ? $rel((string) $visit['html_file']) : '',
            'screenshot' => $visit !== null && ($visit['screenshot_file'] ?? '') !== '' ? $rel((string) $visit['screenshot_file']) : '',
        ];
    }

    return $rows;
}

function stopped(string $stopFile): bool
{
    return is_file($stopFile);
}

/**
 * Рекурсивно удаляет каталог со всем содержимым (пропускает, если каталога нет).
 */
function rrmdir(string $dir): void
{
    if (!is_dir($dir)) {
        return;
    }
    $it = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($dir, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::CHILD_FIRST,
    );
    foreach ($it as $item) {
        $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
    }
    @rmdir($dir);
}

/**
 * Восстанавливает объекты Site из ранее сохранённого sites.json (для этапа выгрузки).
 *
 * @return array<string, Site>
 */
function loadSites(string $file): array
{
    $data = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;
    $sites = [];
    foreach (is_array($data) && isset($data['sites']) ? $data['sites'] : [] as $row) {
        $host = (string) ($row['host'] ?? '');
        if ($host === '') {
            continue;
        }
        $site = new Site($host, $host, (string) ($row['domain'] ?? $host));
        $url = (string) ($row['url'] ?? '');
        $query = (string) ($row['best_query'] ?? '');
        $position = isset($row['best_position']) ? (int) $row['best_position'] : 1;
        $site->add(new SearchResult($query, 0, max(1, $position), $url !== '' ? $url : 'https://' . $host . '/', $host, (string) ($row['title'] ?? '')));
        $sites[$host] = $site;
    }

    return $sites;
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
    $logger = new Logger(Logger::VERBOSE, $logHandle ?: STDERR);
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
        $stage = (string) ($settings['stage'] ?? 'collect');
        $baseFile = dirname($runDir) . '/domains-base.txt';

        if ($stage === 'clean') {
            // --- Этап 3: подготовка контента (шаблоны статей) из ранее скачанных страниц ---
            $pagesDir = $runDir . '/pages';
            $outContent = $runDir . '/content';
            $files = [];
            if (is_dir($pagesDir)) {
                $iter = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($pagesDir, FilesystemIterator::SKIP_DOTS));
                foreach ($iter as $f) {
                    if ($f instanceof SplFileInfo && $f->isFile() && strtolower($f->getExtension()) === 'html') {
                        $files[] = $f->getPathname();
                    }
                }
            }
            if ($files === []) {
                throw new RuntimeException('Нет скачанных страниц — сначала выполните «Выгрузку страниц»');
            }
            sort($files);
            $cleaner = new ContentCleaner();
            $brandRu = trim((string) ($settings['brand_ru'] ?? ''));
            $brandEnOpt = trim((string) ($settings['brand_en'] ?? ''));
            $brands = is_array($settings['brands'] ?? null)
                ? $settings['brands']
                : (array) (preg_split('~[,\n]+~', (string) ($settings['brands'] ?? '')) ?: []);
            $brands = array_values(array_filter(array_map('trim', $brands), static fn (string $b): bool => $b !== ''));
            $written = 0;
            $skipped = 0;
            foreach ($files as $file) {
                $host = basename(dirname($file));
                if (!str_contains($host, '.')) {
                    $host = '';
                }
                $pageHtml = (string) file_get_contents($file);
                // Бренд определяется автоматически по странице и домену; поля панели (если заданы) перекрывают.
                $body = $cleaner->clean($pageHtml, ContentCleaner::autoOptions($pageHtml, $host, [
                    'brand_ru' => $brandRu,
                    'brand_en' => $brandEnOpt,
                    'extra_brands' => $brands,
                ]));
                $rel = ltrim(str_replace($pagesDir, '', $file), '/\\');
                if (trim($body) === '') {
                    $skipped++;
                    continue;
                }
                $dest = $outContent . '/' . $rel;
                @mkdir(dirname($dest), 0777, true);
                file_put_contents($dest, $body);
                $written++;
                $progress->update(['phase' => 'clean', 'message' => sprintf('Подготовлено %d…', $written)]);
            }
            $zipRel = '';
            if ($written > 0 && class_exists('ZipArchive')) {
                $zip = new ZipArchive();
                if ($zip->open($runDir . '/content.zip', ZipArchive::CREATE | ZipArchive::OVERWRITE) === true) {
                    $iter = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($outContent, FilesystemIterator::SKIP_DOTS));
                    foreach ($iter as $f) {
                        if ($f instanceof SplFileInfo && $f->isFile()) {
                            $zip->addFile($f->getPathname(), ltrim(str_replace($outContent, '', $f->getPathname()), '/\\'));
                        }
                    }
                    $zip->close();
                    $zipRel = 'content.zip';
                }
            }
            $progress->update([
                'state' => 'done',
                'phase' => 'done',
                'run_finished_at' => date(DATE_ATOM),
                'files' => $zipRel !== '' ? ['content' => $zipRel] : [],
                'message' => sprintf('Контент подготовлен: %d файлов%s, пропущено (без статьи) %d', $written, $zipRel !== '' ? ' + архив content.zip' : '', $skipped),
            ], true);
            $logger->info(sprintf('Очистка контента: подготовлено %d, пропущено %d', $written, $skipped));
        } elseif ($stage === 'download') {
            // --- Этап 2: выгрузка страниц ранее собранных сайтов (без обращения к источнику) ---
            $config = Config::fromFile($configPath)->withOverrides(array_merge(buildOverrides($settings, $runDir), [
                'visit.enabled' => true,
                'visit.dir' => $runDir . '/pages',
            ]));
            $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
            $sites = loadSites($runDir . '/sites.json');
            if ($sites === []) {
                throw new RuntimeException('Нет собранных сайтов для выгрузки — сначала выполните этап «Сборка»');
            }
            // Выгружаем только оставшиеся сайты: убранные в панели крестиком приходят в exclude_hosts.
            $excludeHosts = array_flip(array_map('strval', (array) ($settings['exclude_hosts'] ?? [])));
            if ($excludeHosts !== []) {
                $sites = array_filter($sites, static fn (string $host): bool => !isset($excludeHosts[$host]), ARRAY_FILTER_USE_KEY);
                if ($sites === []) {
                    throw new RuntimeException('Все собранные сайты убраны из списка — нечего выгружать');
                }
            }
            $runtime = new Runtime($config, $logger);
            $onVisit = static function (array $event) use ($progress): void {
                $progress->update(['phase' => 'visit', 'visit' => $event]);
            };
            $visitor = $runtime->visitor($onVisit);
            if ($visitor === null) {
                throw new RuntimeException('Визиты отключены в настройках');
            }
            // Повторная выгрузка — чистим прошлый результат (папки страниц и очищённый контент),
            // чтобы не осталось старых сайтов и версий: выгружаем заново только оставшиеся.
            rrmdir($runDir . '/pages');
            rrmdir($runDir . '/content');
            $progress->update(['phase' => 'visit', 'sites_selected' => count($sites)], true);
            $logger->info(sprintf('Выгрузка страниц: сайтов %d через %s', count($sites), $visitor->driver()->name()));
            $visitor->visit($sites);

            $siteList = array_values($sites);
            $writer->writeCsv($siteList, $runDir . '/sites.csv');
            $writer->writeJson($siteList, $runDir . '/sites.json', ['source' => 'download', 'settings' => $settings]);
            $writer->writeDomains($siteList, $runDir . '/domains.txt');
            $opened = 0;
            foreach ($siteList as $site) {
                foreach ($site->visits as $v) {
                    if ($v['ok'] ?? false) {
                        $opened++;
                    }
                }
            }
            $progress->update([
                'state' => 'done',
                'phase' => 'done',
                'stats' => ['sites_selected' => count($siteList)],
                'sites' => previewSites($siteList, $runDir),
                'run_finished_at' => date(DATE_ATOM),
                'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt'],
                'message' => sprintf('Выгружено страниц: %d', $opened),
            ], true);
            $logger->info(sprintf('Выгрузка завершена: страниц открыто %d', $opened));
        } else {
            // --- Этап 1: сборка доменов (collect) или сборка + выгрузка (both) ---
            $config = Config::fromFile($configPath)->withOverrides(buildOverrides($settings, $runDir));
            $errors = $config->validate(true);
            if ($errors !== []) {
                throw new RuntimeException('Проверьте настройки: ' . implode('; ', $errors));
            }
            $queries = array_values(array_filter(array_map('trim', (array) ($settings['queries'] ?? [])), static fn (string $q): bool => $q !== '' && !str_starts_with($q, '#')));
            if ($queries === []) {
                throw new RuntimeException('Не задано ни одного запроса');
            }

            $ledger = new DomainLedger($baseFile);
            $skipKnown = (bool) ($settings['skip_known'] ?? true);
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
            $runner = new Runner($config, $fetcher, $runtime->parser(), $logger, $checker, $visitor, $onSearch, $ledger, $skipKnown);

            $logger->info(sprintf('Прогон %d (%s): запросов %d, источник %s', $run, $stage, count($queries), $config->get('source')));
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
                'sites' => previewSites($result->sites, $runDir),
                'base_domains' => $ledger->count(),
                'run_finished_at' => date(DATE_ATOM),
                'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv'],
                'message' => $result->aborted ? 'Прогон остановлен из-за ошибки источника, см. лог' : '',
            ], true);
            $logger->info(sprintf('Прогон %d завершён: новых сайтов %d, всего в базе %d', $run, $result->stats['sites_selected'], $ledger->count()));
        }
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

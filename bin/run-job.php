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
// Страницы и их разбор бывают тяжёлыми: лимит по умолчанию (128M) ронял всё задание из-за одного сайта.
@ini_set('memory_limit', '1024M');

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
use YandexSites\Content\SiteCleaner;
use YandexSites\Filter\DefaultExclusions;
use YandexSites\Output\ReportWriter;
use YandexSites\Runner;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Runtime;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\DomainLedger;
use YandexSites\Support\Logger;
use YandexSites\Support\Progress;
use YandexSites\Support\RemovedSites;
use YandexSites\Support\SiteRows;

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
    // Режим XMLStock: xml — Яндекс.XML, live — живая выдача Яндекса через XMLStock (по 10 результатов на странице).
    $xmlstockLive = false;
    if (isset($s['xmlstock_mode']) && in_array((string) $s['xmlstock_mode'], XmlStockFetcher::MODES, true)) {
        $overrides['xmlstock.mode'] = (string) $s['xmlstock_mode'];
        $xmlstockLive = $s['xmlstock_mode'] === 'live' && (string) ($s['source'] ?? 'xmlstock') === 'xmlstock';
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
    // «Топ N выдачи»: берём только первые N результатов каждого запроса (одна страница по N;
    // у живой выдачи XMLStock страница всегда 10 результатов — значит, N/10 страниц).
    $top = (int) ($s['top'] ?? 10);
    if ($top > 0) {
        if ($xmlstockLive) {
            $overrides['search.pages'] = (int) ceil($top / XmlStockFetcher::LIVE_PAGE_SIZE);
        } else {
            $overrides['search.groups_on_page'] = min(100, $top);
            $overrides['search.pages'] = 1;
        }
        $overrides['filters.max_position'] = $top;
    }
    $overrides['filters.unique_by'] = ($s['dedupe_domain'] ?? true) ? 'domain' : 'host';
    // «Свежая выдача»: не брать ответы из кэша (ответы на те же запросы хранятся 7 дней и не тратят лимит;
    // с этой галочкой каждый сбор спрашивает источник заново).
    if (!empty($s['no_cache'])) {
        $overrides['cache.enabled'] = false;
    } else {
        // Кэш выдачи в панели живёт час, а не 7 дней, как в консоли: повтор через сутки — настоящий переобход
        // (новые сайты в выдаче), а перезапуск через пять минут (поправили фильтры) лимит не тратит.
        $overrides['cache.ttl'] = 3600;
    }
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
function previewSites(array $sites, string $runDir = '', int $limit = 1000): array
{
    return SiteRows::preview($sites, $runDir, $limit);
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
    return SiteRows::load($file);
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
            // --- Этап 3: очистка контента по сайтам — то же, что кнопки «Очистить»/«Очистить всё» в панели,
            // но ФОНОМ и с прогрессом: 250 сайтов одним HTTP-запросом упирались в таймаут и роняли кнопку.
            // Чистятся только оставленные сайты (only из панели, минус exclude_hosts и убранные removed.json);
            // прежний content/ удаляется целиком — чистый пере-сбор, убранный сайт в результате не залипает.
            $byHost = SiteCleaner::pagesByHost($runDir . '/pages');
            if ($byHost === []) {
                throw new RuntimeException('Нет скачанных страниц — сначала выполните «Выгрузку страниц»');
            }
            $only = array_flip(array_map('strval', (array) ($settings['only'] ?? [])));
            $exclude = array_flip(array_merge(array_map('strval', (array) ($settings['exclude_hosts'] ?? [])), RemovedSites::hosts($runDir)));
            $hosts = array_values(array_filter(
                array_keys($byHost),
                static fn ($h): bool => !isset($exclude[$h]) && ($only === [] || isset($only[$h])),
            ));
            $brandList = is_array($settings['brands'] ?? null)
                ? $settings['brands']
                : (array) (preg_split('~[,\n]+~', (string) ($settings['brands'] ?? '')) ?: []);
            $override = [
                // Каталоги слотов по умолчанию остаются (режем только шапку и подвал); галочка в панели включает удаление.
                'remove_slots' => filter_var($settings['remove_slots'] ?? false, FILTER_VALIDATE_BOOL),
                'remove_widgets' => filter_var($settings['remove_widgets'] ?? false, FILTER_VALIDATE_BOOL),
                'brand_ru' => trim((string) ($settings['brand_ru'] ?? '')),
                'brand_en' => trim((string) ($settings['brand_en'] ?? '')),
                'extra_brands' => array_values(array_filter(array_map('trim', array_map('strval', $brandList)), static fn (string $b): bool => $b !== '')),
            ];
            SiteCleaner::rmTree($runDir . '/content');
            $total = count($hosts);
            $done = 0;
            $written = 0;
            $skipped = 0;
            $sitesDone = 0;
            $logger->info(sprintf('Очистка контента: сайтов %d', $total));
            // Прогресс — в том же формате, что у визитов (total/done/ok/current): панель рисует его без переделок.
            $progress->update(['phase' => 'clean', 'visit' => ['total' => $total, 'done' => 0, 'ok' => 0, 'current' => ''], 'message' => sprintf('Очистка: 0 из %d сайтов…', $total)], true);
            foreach ($hosts as $host) {
                if (stopped($stopFile)) {
                    break;
                }
                $r = SiteCleaner::cleanHost($runDir, (string) $host, $byHost[$host], $override);
                $written += $r['written'];
                $skipped += $r['skipped'];
                if ($r['written'] > 0) {
                    $sitesDone++;
                }
                $done++;
                $progress->update(['phase' => 'clean', 'visit' => ['total' => $total, 'done' => $done, 'ok' => $sitesDone, 'current' => (string) $host], 'message' => sprintf('Очистка: %d из %d сайтов…', $done, $total)]);
                $logger->debug(sprintf('  [%d/%d] %s — %d стр., бренд %s / %s', $done, $total, $host, $r['written'], $r['brand_en'], $r['brand_ru']));
                if ($r['skipped_files'] !== []) {
                    $logger->info(sprintf('  %s — без статьи (пропущено): %s', $host, implode(', ', $r['skipped_files'])));
                }
            }
            // Таблица не должна пропасть после очистки: сайты — из sites.json (убранные исключены).
            $siteList = array_values(RemovedSites::filter($runDir, loadSites($runDir . '/sites.json')));
            $stoppedEarly = $done < $total;
            $progress->update([
                'state' => 'done',
                'phase' => 'done',
                'run_finished_at' => date(DATE_ATOM),
                'sites' => previewSites($siteList, $runDir),
                'files' => [],
                'message' => sprintf('%sОчищено: %d сайтов, %d стр. (без статьи: %d) → runs/current/content/N-стр/сайт', $stoppedEarly ? 'Остановлено. ' : '', $sitesDone, $written, $skipped),
            ], true);
            $logger->info(sprintf('Очистка контента: сайтов %d, страниц %d, пропущено %d', $sitesDone, $written, $skipped));
        } elseif ($stage === 'download') {
            // --- Этап 2: выгрузка страниц ранее собранных сайтов (без обращения к источнику) ---
            $config = Config::fromFile($configPath)->withOverrides(array_merge(buildOverrides($settings, $runDir), [
                'visit.enabled' => true,
                'visit.dir' => $runDir . '/pages',
            ]));
            $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
            $sites = loadSites($runDir . '/sites.json');
            // Убранные в панели сайты — окончательно: их нет ни в докачке, ни в выгрузке (removed.json).
            $sites = RemovedSites::filter($runDir, $sites);
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
            // Докачка (retry_hosts) — выгружаем заново только выбранные сайты (где были ошибки),
            // остальные сохраняют свои уже скачанные страницы. Иначе — полная (пере)выгрузка: чистим
            // весь прошлый результат и качаем все сайты заново.
            $retryHosts = array_flip(array_map('strval', (array) ($settings['retry_hosts'] ?? [])));
            $isRetry = $retryHosts !== [];
            $retryStat = ['attempted' => 0, 'recovered' => 0];
            if ($isRetry) {
                // Докачка: успешные страницы сохраняем, перекачиваем ТОЛЬКО неудачные (несколько попыток
                // через разные прокси, одной попыткой — без языкового префикса).
                $visitList = array_filter($sites, static fn (string $host): bool => isset($retryHosts[$host]), ARRAY_FILTER_USE_KEY);
                if ($visitList === []) {
                    throw new RuntimeException('Нет сайтов для докачки (все успешны или убраны)');
                }
                $progress->update(['phase' => 'visit', 'sites_selected' => count($visitList)], true);
                $logger->info(sprintf('Докачка неудачных страниц: сайтов %d через %s', count($visitList), $visitor->driver()->name()));
                $retryStat = $visitor->retryFailed($visitList);
            } else {
                // Полная (пере)выгрузка: чистим весь прошлый результат и качаем все сайты заново.
                rrmdir($runDir . '/pages');
                rrmdir($runDir . '/content');
                foreach ($sites as $site) {
                    $site->visits = [];
                }
                $visitList = $sites;
                $progress->update(['phase' => 'visit', 'sites_selected' => count($visitList)], true);
                $logger->info(sprintf('Выгрузка страниц: сайтов %d через %s', count($visitList), $visitor->driver()->name()));
                $visitor->visit($visitList);
            }

            // Пишем ВСЕ сайты: при докачке обновлённые + сохранённые, при полной выгрузке — все заново.
            // Убранные ВО ВРЕМЯ задания тоже не возвращаем: сверяемся с removed.json перед записью, а их
            // папки, которые задание успело докачать, уносим в removed/.
            $sites = RemovedSites::filter($runDir, $sites);
            RemovedSites::sweep($runDir);
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
                // Докачка: говорим честно, что добрано, а если добирать было нечего — почему (иначе
                // пользователь видит «ничего не изменилось» и думает, что докачка не запустилась).
                'message' => !$isRetry
                    ? sprintf('Выгружено страниц: %d', $opened)
                    : ($retryStat['attempted'] === 0
                        ? 'Докачка: нечего добирать — оставшиеся ошибки повтором не чинятся (404 без языкового префикса, дубликаты)'
                        : sprintf('Докачано: добрано %d из %d стр., всего открыто %d', $retryStat['recovered'], $retryStat['attempted'], $opened)),
            ], true);
            $logger->info(sprintf('%s завершена: страниц открыто %d', $isRetry ? 'Докачка' : 'Выгрузка', $opened));
        } else {
            // --- Этап 1: сборка доменов (collect) или сборка + выгрузка (both) ---
            RemovedSites::clear($runDir); // новый сбор — новый список: прежние удаления неактуальны
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
            // Сколько ответов пришло из кэша выдачи: при повторе тех же запросов новых обращений к источнику нет —
            // это не сбой, но панель должна об этом сказать («он даже не выкачивает запросы»).
            $result->stats['cache_hits'] = $fetcher instanceof CachingFetcher ? $fetcher->hits : 0;
            $result->stats['cache_misses'] = $fetcher instanceof CachingFetcher ? $fetcher->misses : (int) ($result->stats['requests'] ?? 0);

            $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
            // Пустой сбор (всё уже в базе пересечений или отсеяно) не затирает прошлый список сайтов:
            // с ним можно продолжать — выгружать, докачивать, чистить.
            $previous = $result->sites === [] ? array_values(loadSites($runDir . '/sites.json')) : [];
            $keptPrevious = $previous !== [];
            if ($keptPrevious) {
                $logger->info('Новый сбор ничего не отобрал — прошлый список сайтов оставлен без изменений');
            } else {
                $writer->writeCsv($result->sites, $runDir . '/sites.csv');
                $writer->writeJson($result->sites, $runDir . '/sites.json', [
                    'stats' => $result->stats,
                    'errors' => $result->errors,
                    'source' => $config->get('source'),
                    'settings' => $settings,
                    'proxies' => $runtime->proxies?->stats() ?? [],
                ]);
                $writer->writeDomains($result->sites, $runDir . '/domains.txt');
            }
            $writer->writeRawCsv($result->raw, $runDir . '/results.csv');

            $progress->update([
                'state' => $result->aborted ? 'error' : 'done',
                'phase' => 'done',
                'stats' => $result->stats,
                'errors' => $result->errors,
                'aborted' => $result->aborted,
                'proxies' => $runtime->proxies?->stats() ?? [],
                'sites' => previewSites($keptPrevious ? $previous : $result->sites, $runDir),
                'kept_previous' => $keptPrevious,
                'base_domains' => $ledger->count(),
                'run_finished_at' => date(DATE_ATOM),
                'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv'],
                'message' => $result->aborted
                    ? 'Прогон остановлен из-за ошибки источника, см. лог'
                    : ($keptPrevious ? 'Ничего нового не отобрано — прошлый список сайтов оставлен, с ним можно продолжать' : ''),
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

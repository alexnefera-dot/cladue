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
use YandexSites\Filter\Domains;
use YandexSites\Output\ReportWriter;
use YandexSites\Runner;
use YandexSites\RunResult;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Runtime;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\CollectHistory;
use YandexSites\Support\ContentTaken;
use YandexSites\Support\DomainLedger;
use YandexSites\Support\BrandDomains;
use YandexSites\Support\Logger;
use YandexSites\Support\ProblemSites;
use YandexSites\Support\Progress;
use YandexSites\Support\QueryDupes;
use YandexSites\Support\QueryQueue;
use YandexSites\Support\RemovedSites;
use YandexSites\Support\SiteRows;
use YandexSites\Visit\KeyPages;
use YandexSites\Visit\PageVisitor;
use YandexSites\Visit\SiteTemplate;

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
$repeatHours = in_array((string) ($settings['stage'] ?? 'collect'), ['download', 'clean', 'preview'], true) || !empty($settings['resume'])
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
    // Сколько сайтов выгружать за одну волну: после каждой волны её сайты попадают в таблицу и в
    // контент, поэтому число задаёт, как часто появляется готовая порция.
    if (isset($s['batch_size'])) {
        $overrides['visit.batch_sites'] = max(1, min(1000, (int) $s['batch_size']));
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
    // Метки НАШИХ шаблонов из панели («Настройки» → «Метки наших шаблонов»): панель — источник
    // истины, если ключ передан (даже пустым списком). Встроенная метка из Config::defaults()
    // добавляется всегда, чтобы её нельзя было потерять случайным сохранением настроек, а файл
    // own-markers.txt подмешивается отдельно в OwnSites::fromConfig() — оба способа работают вместе.
    if (array_key_exists('own_markers', $s)) {
        $markers = Config::defaults()['filters']['own_markers'];
        foreach (is_array($s['own_markers']) ? $s['own_markers'] : [] as $marker) {
            $marker = trim((string) $marker);
            if ($marker !== '') {
                $markers[] = $marker;
            }
        }
        $overrides['filters.own_markers'] = array_values(array_unique($markers));
    }

    $stage = (string) ($s['stage'] ?? 'collect');
    if (isset($s['variants'])) {
        $overrides['visit.variants'] = max(1, (int) $s['variants']);
    }
    if (isset($s['visit_driver'])) {
        $overrides['visit.driver'] = (string) $s['visit_driver'];
    }
    // Скорость: сколько запросов выдачи тянуть параллельно и сколько страниц/браузеров держать разом.
    if (isset($s['search_threads'])) {
        $overrides['search.concurrency'] = max(1, min(30, (int) $s['search_threads']));
    }
    if (isset($s['visit_threads'])) {
        $overrides['visit.concurrency'] = max(1, min(50, (int) $s['visit_threads']));
    }
    if (isset($s['browsers'])) {
        $overrides['visit.browsers'] = max(1, min(16, (int) $s['browsers']));
    }
    // Добор ключевых страниц по стандартным адресам (кнопка «Добрать ключевые»): включается только для
    // этой докачки, обычная докачка лишних запросов не делает.
    $overrides['visit.retry_key_pages'] = (bool) ($s['retry_key_pages'] ?? false);
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
    // Сколько ещё раз пробовать открыть сайты без превью (другой прокси + другой браузерный агент).
    if (isset($s['preview_retries'])) {
        $overrides['visit.preview_retries'] = max(0, (int) $s['preview_retries']);
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
function previewSites(array $sites, string $runDir = '', int $limit = SiteRows::ROW_LIMIT): array
{
    return SiteRows::preview($sites, $runDir, $limit);
}

/**
 * Запоминает домены НАШИХ шаблонов: следующий сбор такой домен пропустит как «уже в базе» и
 * открывать не станет, но в статистике он должен остаться нашим.
 *
 * @param array<int|string, \YandexSites\Model\Site> $sites
 * @return int сколько новых домен добавлено
 */
function rememberOwnDomains(DomainLedger $ledger, array $sites): int
{
    $domains = [];
    foreach ($sites as $site) {
        if ($site->own && $site->domain !== '') {
            $domains[] = $site->domain;
        }
    }

    return $domains === [] ? 0 : $ledger->add($domains);
}

/**
 * Достраивает список наших доменов по тому, что уже лежит на диске, и по ручному списку
 * own-domains.txt в корне проекта.
 *
 * Нужно вот зачем: домен, который уже есть в базе пересечений, повторный сбор даже не открывает
 * («уже в базе»), а признак «наш» ставится только при визите — по меткам в HTML. Поэтому наши
 * шаблоны, собранные ДО того, как появился этот список, ниоткуда не всплывали: в статистике
 * «наших» оставались только свежие, и процент считался от одних новых. Всё, что помнит диск:
 *   • ручной список own-domains.txt (свои домены можно просто вписать руками);
 *   • таблица прошлого сбора sites.json (строки с «наш») и убранные из неё сайты (removed.json —
 *     кнопка «Убрать наши» уводит их туда вместе со строкой);
 *   • папки раскладки visits: pages/наши/<хост> и removed/pages/наши/<хост>.
 *
 * @param list<string> $manualFiles где искать ручной список (обычно корень проекта)
 * @return int сколько доменов добавилось в список
 */
function seedOwnDomains(DomainLedger $ledger, string $runDir, array $manualFiles): int
{
    $domains = [];
    $add = static function (string $host) use (&$domains): void {
        $host = Domains::normalize($host);
        // Похоже на адрес: точка есть, пробелов нет. Иначе в список наших попадёт случайная строка
        // из файла — а по ней потом ничего не сойдётся.
        if ($host === '' || !str_contains($host, '.') || preg_match('~\s~u', $host) === 1) {
            return;
        }
        $domain = Domains::registrable($host);
        if ($domain !== '') {
            $domains[] = $domain;
        }
    };

    foreach (array_unique($manualFiles) as $file) {
        foreach (is_file($file) ? (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: []) : [] as $line) {
            $line = trim($line);
            if ($line !== '' && !str_starts_with($line, '#')) {
                $add($line);
            }
        }
    }

    foreach (SiteRows::load($runDir . '/sites.json') as $site) {
        if ($site->own) {
            $add($site->domain !== '' ? $site->domain : $site->host);
        }
    }

    foreach (RemovedSites::all($runDir) as $host => $entry) {
        $row = is_array($entry['row'] ?? null) ? $entry['row'] : [];
        $statusRow = is_array($entry['status_row'] ?? null) ? $entry['status_row'] : [];
        if (!($row['own'] ?? false) && !($statusRow['own'] ?? false)) {
            continue;
        }
        $domain = (string) ($row['domain'] ?? '');
        $add($domain !== '' ? $domain : (string) $host);
    }

    foreach ([$runDir . '/pages/наши', $runDir . '/' . RemovedSites::DIR . '/pages/наши'] as $dir) {
        foreach (is_dir($dir) ? (scandir($dir) ?: []) : [] as $name) {
            // Имя папки — хост, пропущенный через PageVisitor::safeName(): берём только то,
            // что и правда похоже на адрес, иначе в список наших попадёт мусор.
            if (is_dir($dir . '/' . $name) && preg_match('~^[a-z0-9][a-z0-9.\-]*\.[a-z0-9\-]{2,}$~i', $name) === 1) {
                $add($name);
            }
        }
    }

    return $domains === [] ? 0 : $ledger->add($domains);
}

function stopped(string $stopFile): bool
{
    return is_file($stopFile);
}

/**
 * Рекурсивно удаляет каталог со всем содержимым (пропускает, если каталога нет).
 */
/**
 * Удаляет скачанные страницы и очищенный контент ПЕРЕЧИСЛЕННЫХ сайтов (в любом бакете N-стр).
 * Перевыгрузка чистит прошлый результат только по этим сайтам: страницы других частей сбора —
 * уже выгруженных и очищенных — остаются на месте.
 *
 * @param list<string> $hosts
 */
function removeSiteFolders(string $runDir, array $hosts): void
{
    foreach ($hosts as $host) {
        $name = \YandexSites\Visit\PageVisitor::safeName((string) $host);
        foreach ([$runDir . '/pages', $runDir . '/content'] as $top) {
            rrmdir($top . '/' . $name);
            foreach (glob($top . '/*/' . $name, GLOB_ONLYDIR) ?: [] as $dir) {
                rrmdir($dir);
            }
        }
    }
}

/**
 * Настройки очистки контента из панели (галочки и ручные бренды) — одни и те же для этапа «clean»
 * и для очистки сразу после волны выгрузки.
 *
 * @param array<string, mixed> $settings
 * @return array<string, mixed>
 */
function cleanOptions(array $settings): array
{
    $brandList = is_array($settings['brands'] ?? null)
        ? $settings['brands']
        : (array) (preg_split('~[,\n]+~', (string) ($settings['brands'] ?? '')) ?: []);

    return [
        // Каталоги слотов по умолчанию остаются (режем только шапку и подвал); галочка в панели включает удаление.
        'remove_slots' => filter_var($settings['remove_slots'] ?? false, FILTER_VALIDATE_BOOL),
        'remove_widgets' => filter_var($settings['remove_widgets'] ?? false, FILTER_VALIDATE_BOOL),
        'brand_ru' => trim((string) ($settings['brand_ru'] ?? '')),
        'brand_en' => trim((string) ($settings['brand_en'] ?? '')),
        'extra_brands' => array_values(array_filter(array_map('trim', array_map('strval', $brandList)), static fn (string $b): bool => $b !== '')),
    ];
}

/**
 * Чистит контент сайтов одной волны выгрузки — сразу после того, как их страницы легли на диск.
 * Так готовую часть можно забирать архивом, не дожидаясь конца выгрузки.
 *
 * @param list<string> $hosts
 * @param array<string, mixed> $override
 * @return array{written: int, sites: int}
 */
function cleanWave(string $runDir, array $hosts, array $override, Logger $logger): array
{
    $byHost = SiteCleaner::pagesByHost($runDir . '/pages');
    $written = 0;
    $sites = 0;
    foreach ($hosts as $host) {
        $files = $byHost[$host] ?? [];
        if ($files === []) {
            continue;
        }
        $r = SiteCleaner::cleanHost($runDir, $host, $files, $override);
        $written += $r['written'];
        if ($r['written'] > 0) {
            $sites++;
        }
        if ($r['skipped_files'] !== []) {
            $logger->info(sprintf('  %s — без статьи (пропущено): %s', $host, implode(', ', $r['skipped_files'])));
        }
    }
    if ($written > 0) {
        $logger->info(sprintf('  очищено сразу: %d стр. на %d сайтах', $written, $sites));
    }

    return ['written' => $written, 'sites' => $sites];
}

/**
 * Удаляет результаты прошлого прогона: скачанные страницы, очищенный контент, превью, убранные сайты
 * и готовый архив. Вызывается только НОВЫМ сбором — продолжение прошлые части не трогает.
 *
 * @return int сколько файлов удалено
 */
function wipeRunOutput(string $runDir): int
{
    $files = 0;
    foreach (['pages', 'content', 'preview', 'removed'] as $sub) {
        $dir = $runDir . '/' . $sub;
        if (!is_dir($dir)) {
            continue;
        }
        $files += count(\YandexSites\Support\Archive::listFiles($dir));
        rrmdir($dir);
    }
    if (is_file($runDir . '/content.zip') && @unlink($runDir . '/content.zip')) {
        $files++;
    }
    // Отметки «этот контент уже скачан» относятся к удалённым статьям — новый сбор начинает счёт заново.
    ContentTaken::reset($runDir);

    return $files;
}

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
        // Наши шаблоны, найденные за ВСЕ сборы: повторный сбор такой домен даже не открывает («уже в
        // базе»), а в статистике он всё равно наш — поэтому свои домены копим отдельным списком.
        $ownLedger = new DomainLedger(dirname($runDir) . '/own-domains.txt');
        // Список появился не сразу, а старые наши домены повторный сбор не открывает — поэтому перед
        // работой добираем их с диска и из ручного own-domains.txt (до чистки нового сбора: она
        // удаляет pages/ и removed/, откуда мы их и читаем).
        $seededOwn = seedOwnDomains($ownLedger, $runDir, [getcwd() . '/own-domains.txt', $root . '/own-domains.txt']);
        if ($seededOwn > 0) {
            $logger->info(sprintf('Наших доменов добавлено из прошлых сборов и own-domains.txt: %d (всего %d)', $seededOwn, $ownLedger->count()));
        }

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
            $override = cleanOptions($settings);
            // Контент чистим ТОЧЕЧНО: cleanHost сам убирает прошлую версию своего сайта, а здесь снимаем
            // убранные из таблицы. Сносить весь content нельзя — в нём лежат уже обработанные части сбора.
            foreach (array_keys($exclude) as $excluded) {
                SiteCleaner::removeHostContent($runDir, (string) $excluded);
            }
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
                'sites_count' => count($siteList),
                'files' => [],
                'message' => sprintf('%sОчищено: %d сайтов, %d стр. (без статьи: %d) → runs/current/content/N-стр/сайт', $stoppedEarly ? 'Остановлено. ' : '', $sitesDone, $written, $skipped),
            ], true);
            $logger->info(sprintf('Очистка контента: сайтов %d, страниц %d, пропущено %d', $sitesDone, $written, $skipped));
        } elseif ($stage === 'preview') {
            // --- Перепробовать сайты без превью: ещё несколько заходов на главную, каждый с ДРУГОГО
            // прокси и под ДРУГИМ браузерным агентом. Скачанные страницы других сайтов не трогаем.
            $config = Config::fromFile($configPath)->withOverrides(array_merge(buildOverrides($settings, $runDir), [
                'visit.enabled' => true,
                'visit.crawl' => false,
                'visit.variants' => 1,
                'visit.screenshot' => true,
                'visit.max_pages' => 0,
                'visit.dir' => $runDir . '/preview',
            ]));
            $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
            $sites = RemovedSites::filter($runDir, loadSites($runDir . '/sites.json'));
            if ($sites === []) {
                throw new RuntimeException('Нет собранных сайтов — сначала выполните сбор');
            }
            // Панель присылает сайты без превью (only); если списка нет — берём все пустые сами.
            $only = array_flip(array_map('strval', (array) ($settings['only'] ?? [])));
            $visitList = $only !== []
                ? array_filter($sites, static fn (string $host): bool => isset($only[$host]), ARRAY_FILTER_USE_KEY)
                : $sites;
            $runtime = new Runtime($config, $logger);
            $visitor = $runtime->visitor(static function (array $event) use ($progress): void {
                $progress->update(['phase' => 'visit', 'visit' => $event]);
            });
            if ($visitor === null) {
                throw new RuntimeException('Визиты отключены в настройках');
            }
            $progress->update(['phase' => 'visit', 'sites_selected' => count($visitList)], true);
            $stat = $visitor->retryPreview($visitList);
            // Объекты сайтов общие с $sites, поэтому просто перезаписываем список целиком.
            $sites = RemovedSites::filter($runDir, $sites);
            rememberOwnDomains($ownLedger, $sites); // сайт мог открыться нашим шаблоном только сейчас
            $siteList = array_values($sites);
            $writer->writeCsv($siteList, $runDir . '/sites.csv');
            $writer->writeJson($siteList, $runDir . '/sites.json', ['source' => 'preview', 'settings' => $settings]);
            $writer->writeDomains($siteList, $runDir . '/domains.txt');
            $progress->update([
                'state' => 'done',
                'phase' => 'done',
                'run_finished_at' => date(DATE_ATOM),
                'sites' => previewSites($siteList, $runDir),
                'sites_count' => count($siteList),
                'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt'],
                'message' => $stat['attempted'] === 0
                    ? 'Сайтов без превью нет — пробовать нечего'
                    : sprintf('Перепробовано сайтов без превью: %d, открылось %d', $stat['attempted'], $stat['recovered']),
            ], true);
            $logger->info(sprintf('Перепробовано без превью: %d, открылось %d', $stat['attempted'], $stat['recovered']));
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
            // Панель присылает only — сайты, которые сейчас В ТАБЛИЦЕ: выгружаем ровно их. Всё, чего в таблице
            // нет (например, сверх лимита строк), не качаем — иначе «выгружаются сайты, которых не видно».
            $only = array_flip(array_map('strval', (array) ($settings['only'] ?? [])));
            if ($only !== []) {
                $notListed = array_keys(array_filter($sites, static fn (string $host): bool => !isset($only[$host]), ARRAY_FILTER_USE_KEY));
                $sites = array_filter($sites, static fn (string $host): bool => isset($only[$host]), ARRAY_FILTER_USE_KEY);
                if ($notListed !== []) {
                    $logger->info(sprintf('Выгружаем только сайты из таблицы панели: %d; ещё %d из sites.json в таблице нет — не выгружаем (%s%s)', count($sites), count($notListed), implode(', ', array_slice($notListed, 0, 5)), count($notListed) > 5 ? ', …' : ''));
                }
                if ($sites === []) {
                    throw new RuntimeException('В таблице панели нет сайтов для выгрузки');
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
            $cleanStats = ''; // сколько очищено прямо во время выгрузки (волнами)
            $waveStopped = false; // выгрузку остановили между волнами — часть сайтов не тронута
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
                // (Пере)выгрузка идёт ВОЛНАМИ по visit.batch_sites сайтов: обход устроен по этапам
                // (сначала все главные, потом пробные, потом остальные страницы), поэтому пока список
                // не кончится, ни один сайт не считается готовым — ждать пришлось бы всю выгрузку.
                // После каждой волны её сайты попадают в sites.json и в таблицу, их контент чистится
                // (если включено), и можно скачать архив только нового. Остановка срабатывает между
                // волнами: уже готовые части остаются на диске.
                removeSiteFolders($runDir, array_keys($excludeHosts));
                $batch = max(1, (int) $config->get('visit.batch_sites', 50));
                $waves = array_chunk($sites, $batch, true);
                $waveCount = count($waves);
                // Чистить контент сразу после каждой волны — чтобы работать с готовой частью, не дожидаясь конца.
                $cleanNow = filter_var($settings['clean_while_download'] ?? true, FILTER_VALIDATE_BOOL);
                $cleanOverride = cleanOptions($settings);
                $cleanedPages = 0;
                $cleanedSites = 0;
                // Прогресс копим по всем волнам: иначе счётчик страниц обнулялся бы на каждой волне.
                $base = ['done' => 0, 'ok' => 0, 'total' => 0];
                $last = ['done' => 0, 'ok' => 0, 'total' => 0];
                $waveNo = 0;
                $sitesDone = 0;
                $onVisit = static function (array $event) use ($progress, &$base, &$last, &$waveNo, $waveCount, &$sitesDone, $sites): void {
                    $last = ['done' => (int) ($event['done'] ?? 0), 'ok' => (int) ($event['ok'] ?? 0), 'total' => (int) ($event['total'] ?? 0)];
                    $progress->update(['phase' => 'visit', 'visit' => [
                        'done' => $base['done'] + $last['done'],
                        'ok' => $base['ok'] + $last['ok'],
                        'total' => $base['total'] + $last['total'],
                        'current' => (string) ($event['current'] ?? ''),
                    ], 'wave' => ['n' => $waveNo, 'total' => $waveCount, 'sites_done' => $sitesDone, 'sites_total' => count($sites)]]);
                };
                $visitor = $runtime->visitor($onVisit);
                if ($visitor === null) {
                    throw new RuntimeException('Визиты отключены в настройках');
                }
                $progress->update(['phase' => 'visit', 'sites_selected' => count($sites)], true);
                $logger->info(sprintf('Выгрузка страниц: сайтов %d волнами по %d через %s', count($sites), $batch, $visitor->driver()->name()));
                foreach ($waves as $wave) {
                    $waveNo++;
                    // Прошлые страницы и контент — только у сайтов ЭТОЙ волны: если выгрузку остановят,
                    // сайты, до которых не дошли, сохранят прежние визиты и превью.
                    removeSiteFolders($runDir, array_map('strval', array_keys($wave)));
                    foreach ($wave as $site) {
                        $site->visits = [];
                    }
                    $logger->info(sprintf('Волна %d из %d: сайтов %d', $waveNo, $waveCount, count($wave)));
                    $visitor->visit($wave);
                    $base = ['done' => $base['done'] + $last['done'], 'ok' => $base['ok'] + $last['ok'], 'total' => $base['total'] + $last['total']];
                    $last = ['done' => 0, 'ok' => 0, 'total' => 0];
                    $sitesDone += count($wave);
                    if ($cleanNow) {
                        $c = cleanWave($runDir, array_map('strval', array_keys($wave)), $cleanOverride, $logger);
                        $cleanedPages += $c['written'];
                        $cleanedSites += $c['sites'];
                    }
                    // Готовая часть — сразу в файлы: дальше с ней уже можно работать. Строки таблицы в
                    // статус НЕ кладём — панель и так берёт их из sites.json, пока задание идёт
                    // (sites_from_file), а таскать список из тысяч строк в каждом обновлении прогресса
                    // (а он пишется по 4 раза в секунду) — лишние мегабайты на диск.
                    $ready = array_values(RemovedSites::filter($runDir, $sites));
                    $writer->writeCsv($ready, $runDir . '/sites.csv');
                    $writer->writeJson($ready, $runDir . '/sites.json', ['source' => 'download', 'settings' => $settings]);
                    $writer->writeDomains($ready, $runDir . '/domains.txt');
                    $progress->update([
                        'phase' => 'visit',
                        'wave' => ['n' => $waveNo, 'total' => $waveCount, 'sites_done' => $sitesDone, 'sites_total' => count($sites)],
                        'message' => sprintf('Выгрузка: готово %d из %d сайтов (волна %d из %d)%s', $sitesDone, count($sites), $waveNo, $waveCount, $cleanNow ? sprintf(', очищено %d стр.', $cleanedPages) : ''),
                    ], true);
                    if (stopped($stopFile)) {
                        $logger->info(sprintf('Остановлено между волнами: выгружено %d из %d сайтов', $sitesDone, count($sites)));
                        break;
                    }
                }
                $visitList = $sites;
                $cleanStats = $cleanNow ? sprintf('%d стр. на %d сайтах', $cleanedPages, $cleanedSites) : '';
                $waveStopped = $sitesDone < count($sites);
            }

            // Пишем ВСЕ сайты: при докачке обновлённые + сохранённые, при полной выгрузке — все заново.
            // Убранные ВО ВРЕМЯ задания тоже не возвращаем: сверяемся с removed.json перед записью, а их
            // папки, которые задание успело докачать, уносим в removed/.
            $sites = RemovedSites::filter($runDir, $sites);
            RemovedSites::sweep($runDir);
            rememberOwnDomains($ownLedger, $sites); // наш шаблон может открыться и на выгрузке
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
            $pageStats = SiteRows::histogramText(SiteRows::pageHistogram($siteList));
            // Чего не хватает: ключевые страницы (регистрация, вход, зеркало, бонусы, приложение, слоты) —
            // именно на них ссылается готовый контент, поэтому пропуск виден как «ссылка в никуда».
            $keyHist = KeyPages::histogram($siteList);
            $keyStats = KeyPages::histogramText($keyHist);
            if ($keyStats !== '') {
                $logger->info('Не хватает ключевых страниц: ' . $keyStats);
            }
            // Сайты с фильтром по User-Agent: робота поисковика не пустили, страницы взяли под браузером.
            $uaPages = 0;
            $uaSites = 0;
            foreach ($siteList as $site) {
                $n = PageVisitor::openedAsBrowser(array_map(static fn ($v): array => (array) $v, $site->visits));
                if ($n > 0) {
                    $uaPages += $n;
                    $uaSites++;
                }
            }
            $uaStats = $uaSites > 0 ? sprintf('%d стр. на %d сайтах', $uaPages, $uaSites) : '';
            $rows = previewSites($siteList, $runDir);
            // Проблемные ПО ВЫГРУЗКЕ: сайт не отдал ни одной страницы, часть страниц упала так, что
            // докачка их доберёт, или файл пропал с диска. Одностраничник и пропуск целевой — не проблема.
            $problemHist = ProblemSites::histogram($rows);
            $problemStats = ProblemSites::histogramText($problemHist);
            if ($problemStats !== '') {
                $logger->info(sprintf('Проблемных сайтов: %d — %s', $problemHist['sites'], $problemStats));
            }
            $progress->update([
                'state' => 'done',
                'phase' => 'done',
                'stats' => ['sites_selected' => count($siteList)],
                'sites' => $rows,
                'sites_count' => count($siteList),
                'page_histogram' => SiteRows::pageHistogram($siteList),
                'template_histogram' => SiteTemplate::histogram($siteList),
                'key_pages' => $keyHist,
                'problem_histogram' => $problemHist,
                'run_finished_at' => date(DATE_ATOM),
                'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt'],
                // Докачка: говорим честно, что добрано, а если добирать было нечего — почему (иначе
                // пользователь видит «ничего не изменилось» и думает, что докачка не запустилась).
                'message' => ($waveStopped ? 'Остановлено. ' : '') . (!$isRetry
                    ? sprintf('Выгружено страниц: %d', $opened) . ($cleanStats !== '' ? '; очищено сразу: ' . $cleanStats : '') . ($keyStats !== '' ? '; не хватает: ' . $keyStats : '')
                    : ($retryStat['attempted'] === 0
                        ? 'Докачка: нечего добирать — оставшиеся ошибки повтором не чинятся (404 без языкового префикса, дубликаты)'
                        : sprintf('Докачано: добрано %d из %d стр., всего открыто %d', $retryStat['recovered'], $retryStat['attempted'], $opened)))
                    // Разбивка по числу страниц: сколько одностраничников, сколько 9/10-страничников и т.п.
                    . ($pageStats !== '' ? '; по страницам: ' . $pageStats : '')
                    . ($problemHist['sites'] > 0 ? sprintf('; проблемных: %d (фильтр над таблицей)', $problemHist['sites']) : '')
                    . ($uaStats !== '' ? '; под браузером (робота не пустили): ' . $uaStats : ''),
            ], true);
            $logger->info(sprintf('%s завершена: страниц открыто %d%s', $isRetry ? 'Докачка' : 'Выгрузка', $opened, $pageStats !== '' ? '; по страницам: ' . $pageStats : ''));
        } else {
            // --- Этап 1: сборка доменов (collect) или сборка + выгрузка (both) ---
            // Большой список обрабатывается ЧАСТЯМИ: сбор идёт, пока не нажата «Остановить», очередь
            // (queue.json) помнит позицию, а «Продолжить сбор» запускает остаток — с прошлой таблицей
            // (resume) или с чистой (resume + reset_sites), если предыдущая часть уже обработана.
            $resume = (bool) ($settings['resume'] ?? false);
            $resetSites = (bool) ($settings['reset_sites'] ?? false);
            $queueFile = $runDir . '/' . QueryQueue::FILE;
            $listed = array_values(array_filter(array_map('trim', (array) ($settings['queries'] ?? [])), static fn (string $q): bool => $q !== '' && !str_starts_with($q, '#')));
            if ($resume) {
                // Список в панели мог измениться (убрали дубли, дописали запросы) — очередь подстраиваем,
                // не теряя позицию.
                $queue = QueryQueue::sync(QueryQueue::load($queueFile), $listed);
                QueryQueue::save($queueFile, $queue);
                $queries = QueryQueue::remaining($queue);
                if ($queries === []) {
                    throw new RuntimeException('Все запросы очереди уже обработаны — нажмите «Собрать сайты», чтобы пройти список заново');
                }
            } else {
                if ($listed === []) {
                    throw new RuntimeException('Не задано ни одного запроса');
                }
                $queue = QueryQueue::start($queueFile, $listed);
                $queries = $listed;
            }
            $queueOffset = $queue['done'];
            if (!$resume || $resetSites) {
                RemovedSites::clear($runDir); // новый список (или продолжение с чистой таблицей): прежние удаления неактуальны
            }
            if (!$resume) {
                // НОВЫЙ сбор — чистый лист: прошлые скачанные страницы и очищенный контент относятся к
                // прошлому списку сайтов, их архив уже скачан. Иначе после очистки новый контент ложился
                // к старому, и архив приходил со всеми прежними сайтами. «Продолжить сбор» это не трогает.
                $wiped = wipeRunOutput($runDir);
                if ($wiped > 0) {
                    $logger->info(sprintf('Новый сбор: прежние страницы и контент удалены (%d файлов)', $wiped));
                }
            }
            $config = Config::fromFile($configPath)->withOverrides(buildOverrides($settings, $runDir));
            $errors = $config->validate(true);
            if ($errors !== []) {
                throw new RuntimeException('Проверьте настройки: ' . implode('; ', $errors));
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
            $stopCheck = static fn (): bool => stopped($stopFile);
            // Статистика сбора пишется СРАЗУ, как только домены отобраны, — не дожидаясь обхода сайтов
            // со скриншотами: он идёт долго, а цифры по доменам уже готовы (и переживут остановку).
            // В конце сбора эта же запись уточняется: визиты показывают редиректы на бренд-поддомены.
            $historyId = '';
            $onSelected = function (array $sites, RunResult $r) use ($runDir, $resume, &$historyId, $logger, $ownLedger): void {
                $record = CollectHistory::record($sites, $r->stats, $r->seenBefore, $resume, false, $r->raw, $ownLedger->all());
                $historyId = (string) $record['id'];
                CollectHistory::append(dirname($runDir), $record);
                // Воронка одной строкой: каждое число вытекает из предыдущего, и сумма срезанного
                // с отобранным даёт массу выдачи — чтобы было видно, что именно срезали фильтры.
                $logger->info(sprintf(
                    'За этот сбор: %d строк выдачи → %d адресов → %d сайтов (один на домен), из них доров %d (%s%%) → срезано фильтрами %d → отобрано в базу %d',
                    $record['results'],
                    $record['found'],
                    $record['unique_sites'],
                    $record['found_doors'],
                    CollectHistory::percent($record['found_doors'], $record['unique_sites']),
                    CollectHistory::cutTotal($record['cut']),
                    $record['sites'],
                ));
                if ($record['cut'] !== []) {
                    $logger->info('Срезано по причинам (сайтов): ' . CollectHistory::cutText($record['cut']));
                }
                if ($record['zones'] !== []) {
                    $logger->info('Зоны доров: ' . CollectHistory::zonesText($record['zones'], 8));
                }
                // Домены, которые держат много брендов: на поддоменах сайты разных брендов. Полный
                // список пишем рядом с результатами — в записи истории остаются только первые.
                $brandDomains = BrandDomains::find($r->raw, $sites);
                file_put_contents($runDir . '/' . BrandDomains::FILE, BrandDomains::text($brandDomains));
                if ($brandDomains !== []) {
                    $first = array_slice(BrandDomains::top($brandDomains), 0, 5);
                    $logger->info(sprintf(
                        'Доменов, которые держат более %d брендов: %d — %s%s',
                        BrandDomains::MIN_BRANDS - 1,
                        count($brandDomains),
                        implode(', ', array_map(static fn (array $d): string => sprintf('%s (%d)', $d['domain'], $d['brands']), $first)),
                        count($brandDomains) > count($first) ? ', …' : '',
                    ));
                }
            };
            $runner = new Runner($config, $fetcher, $runtime->parser(), $logger, $checker, $visitor, $onSearch, $ledger, $skipKnown, $stopCheck, $onSelected);

            $logger->info(sprintf(
                'Прогон %d (%s): запросов %d%s, источник %s',
                $run,
                $stage,
                count($queries),
                $queueOffset > 0 ? sprintf(' (продолжение с %d-го из %d)', $queueOffset + 1, count($queue['queries'])) : '',
                $config->get('source'),
            ));
            $result = $runner->run($queries);
            // Позиция в очереди — сколько запросов всего обработано: с неё пойдёт «Продолжить сбор».
            $queue['done'] = $queueOffset + $result->processed;
            QueryQueue::save($queueFile, $queue);
            $queueInfo = QueryQueue::summary($queue);
            // Сколько ответов пришло из кэша выдачи: при повторе тех же запросов новых обращений к источнику нет —
            // это не сбой, но панель должна об этом сказать («он даже не выкачивает запросы»).
            $result->stats['cache_hits'] = $fetcher instanceof CachingFetcher ? $fetcher->hits : 0;
            $result->stats['cache_misses'] = $fetcher instanceof CachingFetcher ? $fetcher->misses : (int) ($result->stats['requests'] ?? 0);

            $writer = new ReportWriter((string) $config->get('output.csv_delimiter', ';'), (bool) $config->get('output.csv_bom', true));
            // Продолжение сбора ПОПОЛНЯЕТ таблицу: прошлые сайты остаются (с их выгруженными страницами),
            // если при нажатии «Продолжить» не выбрано «очистить таблицу».
            $carried = ($resume && !$resetSites) ? loadSites($runDir . '/sites.json') : [];
            $merged = $carried;
            foreach ($result->sites as $site) {
                $merged[$site->host] ??= $site;
            }
            $merged = array_values(RemovedSites::filter($runDir, $merged));
            // Пустой сбор (всё уже в базе пересечений или отсеяно) не затирает прошлый список сайтов:
            // с ним можно продолжать — выгружать, докачивать, чистить.
            $previous = ($merged === [] && !$resetSites) ? array_values(loadSites($runDir . '/sites.json')) : [];
            $keptPrevious = $previous !== [];
            if ($keptPrevious) {
                $logger->info('Новый сбор ничего не отобрал — прошлый список сайтов оставлен без изменений');
            } else {
                $writer->writeCsv($merged, $runDir . '/sites.csv');
                $writer->writeJson($merged, $runDir . '/sites.json', [
                    'stats' => $result->stats,
                    'errors' => $result->errors,
                    'source' => $config->get('source'),
                    'settings' => $settings,
                    'proxies' => $runtime->proxies?->stats() ?? [],
                ]);
                $writer->writeDomains($merged, $runDir . '/domains.txt');
            }
            // При продолжении строки выдачи ДОПИСЫВАЮТСЯ: results.csv описывает весь список запросов.
            $writer->writeRawCsv($result->raw, $runDir . '/results.csv', $resume);

            // Запросы с одинаковой выдачей (тот же набор сайтов, позиции не важны): панель предлагает убрать
            // дубли из списка запросов; queries-unique.txt / query-dupes.txt лежат рядом с результатами.
            $dupes = QueryDupes::find(QueryDupes::csvRows($runDir . '/results.csv'), $queue['queries']);
            if ($result->aborted) {
                $dupes['no_results'] = []; // прерванный прогон: не дошедшие до выдачи запросы — не «без результатов»
            }
            QueryDupes::writeFiles($runDir, $dupes);
            $dupeSummary = QueryDupes::summary($dupes);
            if ($dupeSummary['duplicates'] > 0) {
                $logger->info(sprintf('Запросов с одинаковой выдачей: %d дублей в %d группах из %d — список без дублей: %s', $dupeSummary['duplicates'], $dupeSummary['groups'], $dupeSummary['total'], QueryDupes::UNIQUE_FILE));
            }

            // Тип вёрстки по превью главной (7–9 / 12–15 страниц / без категории) — виден сразу после сбора,
            // по нему панель фильтрует таблицу до выгрузки.
            $shown = $keptPrevious ? $previous : $merged;
            $templateHist = SiteTemplate::histogram($shown);
            $templateNote = $templateHist !== [] ? 'По типу вёрстки (по главной): ' . SiteTemplate::histogramText($templateHist) : '';
            // Сайты, спрятавшие себя за витриной чужих офферов: их уже перепроверили с других IP и
            // под другими агентами, настоящий сайт так и не показался — в панели их можно убрать пачкой.
            $offerWalls = 0;
            foreach ($shown as $site) {
                if (PageVisitor::isOfferWallSite(array_map(static fn ($v): array => (array) $v, $site->visits))) {
                    $offerWalls++;
                }
            }
            if ($offerWalls > 0) {
                $logger->info(sprintf('Подборок офферов вместо сайта: %d (перепроверены с других IP и агентов)', $offerWalls));
            }
            // Статистику по доменам уже записал $onSelected (сразу после отбора). Здесь только
            // уточняем её итогом: визиты могли показать редирект апекса на бренд-поддомен (это тоже
            // дор), и теперь известно, останавливали ли сбор. Если запись почему-то не появилась
            // (старое задание, отбор не дошёл) — пишем её сейчас.
            // Зоны и вся масса выдачи уже посчитаны по сырым результатам и после визитов не меняются —
            // уточняем только отобранное (редирект апекса на бренд-поддомен — тоже дор) и хвост записи.
            // Наши шаблоны тоже видно только сейчас: признак ставится по меткам в HTML на превью-визите
            // (скриншот — чтобы проверить глазами), поэтому в ранней записи там был 0.
            $finalBreakdown = CollectHistory::breakdown($result->sites);
            $newOwn = rememberOwnDomains($ownLedger, $result->sites);
            if ($newOwn > 0) {
                $logger->info(sprintf('Запомнили наших доменов: %d (всего в списке %d)', $newOwn, $ownLedger->count()));
            }
            $ownRepeats = CollectHistory::ownRepeats($result->seenBefore, $ownLedger->all());
            // Наши в записи — сумма трёх частей; здесь уточняем отобранную и повторы, срезанное по
            // метке-домену уже посчитано ранней записью (сумму пересобирает CollectHistory::update()).
            $patched = CollectHistory::update(dirname($runDir), $historyId, [
                'doors' => $finalBreakdown['doors'],
                'roots' => $finalBreakdown['roots'],
                'own_selected' => $finalBreakdown['own'],
                'own_repeats' => $ownRepeats,
                'own_known' => $ownLedger->count(),
                'base_domains' => (int) ($result->stats['base_domains'] ?? 0),
                'stopped' => $result->stopped,
            ]);
            if (!$patched) {
                CollectHistory::append(dirname($runDir), CollectHistory::record($result->sites, $result->stats, $result->seenBefore, $resume, $result->stopped, $result->raw, $ownLedger->all()));
            }
            $ownNote = '';
            // Доля наших считается от ВСЕХ доров выдачи: наши шаблоны и есть доры. Оттуда же берём
            // наших, срезанных по метке-домену: собирать их мы не собираемся, но в выдаче они стоят.
            $allRaw = CollectHistory::breakdownRaw($result->raw, (string) ($result->stats['unique_by'] ?? 'domain'));
            $doorsAll = (int) ($allRaw['doors'] ?? 0);
            $ownCut = (int) ($allRaw['cut']['own_site']['sites'] ?? 0);
            $ownTotal = $finalBreakdown['own'] + $ownRepeats + $ownCut;
            if ($ownTotal > 0) {
                $parts = [];
                if ($ownRepeats > 0) {
                    $parts[] = sprintf('%d повторами', $ownRepeats);
                }
                if ($ownCut > 0) {
                    $parts[] = sprintf('%d срезано по меткам', $ownCut);
                }
                $ownNote = sprintf(
                    'наших шаблонов: %d%s из %d доров выдачи (%s%%)',
                    $ownTotal,
                    $parts !== [] ? ' (из них ' . implode(', ', $parts) . ')' : '',
                    $doorsAll,
                    CollectHistory::percent($ownTotal, $doorsAll),
                );
                $logger->info(sprintf('Наши шаблоны (по меткам в HTML): %s — выгружать их не нужно', $ownNote));
            }
            if ($ownLedger->count() === 0) {
                $logger->info('Список наших доменов пуст (runs/own-domains.txt): среди повторов наши не опознаются — впишите свои домены в own-domains.txt');
            }
            $collectRows = previewSites($shown, $runDir);
            // Проблемные ПО СБОРУ: сайт не открылся на превью или показал витрину чужих офферов. Целевые
            // страницы здесь не считаем — открыта только главная, судить о них рано (это делает выгрузка).
            $problemHist = ProblemSites::histogram($collectRows);
            if ($problemHist['sites'] > 0) {
                $logger->info(sprintf('Проблемных сайтов по сбору: %d — %s', $problemHist['sites'], ProblemSites::histogramText($problemHist)));
            }
            $progress->update([
                'state' => $result->aborted ? 'error' : ($result->stopped ? 'stopped' : 'done'),
                'phase' => $result->stopped ? 'stopped' : 'done',
                'stats' => $result->stats,
                'errors' => $result->errors,
                'aborted' => $result->aborted,
                'proxies' => $runtime->proxies?->stats() ?? [],
                'sites' => $collectRows,
                'sites_count' => count($shown),
                'kept_previous' => $keptPrevious,
                'queue' => $queueInfo,
                'stopped_early' => $result->stopped,
                'template_histogram' => $templateHist,
                'problem_histogram' => $problemHist,
                'query_dupes' => $dupeSummary,
                'base_domains' => $ledger->count(),
                'run_finished_at' => date(DATE_ATOM),
                'files' => ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv', 'brands' => BrandDomains::FILE],
                'message' => $result->aborted
                    ? 'Прогон остановлен из-за ошибки источника, см. лог'
                    : trim(
                        ($result->stopped
                            ? sprintf(
                                'Остановлено на %d-м запросе из %d. Сайтов в таблице: %d — можно работать с этой частью (убрать лишние, выгрузить, очистить), потом «Продолжить сбор» (осталось %d запросов). ',
                                $queueInfo['done'],
                                $queueInfo['total'],
                                count($shown),
                                $queueInfo['left'],
                            )
                            : ($queueInfo['left'] > 0 ? sprintf('Обработано %d из %d запросов, осталось %d — «Продолжить сбор». ', $queueInfo['done'], $queueInfo['total'], $queueInfo['left']) : ''))
                        . ($keptPrevious ? 'Ничего нового не отобрано — прошлый список сайтов оставлен, с ним можно продолжать. ' : '')
                        . $templateNote
                        . ($ownNote !== '' ? ($templateNote !== '' ? '; ' : '') . $ownNote : '')
                        . ($offerWalls > 0 ? sprintf('; подборок офферов вместо сайта: %d', $offerWalls) : '')
                        . ($problemHist['sites'] > 0 ? sprintf('; проблемных: %d (фильтр над таблицей)', $problemHist['sites']) : ''),
                    ),
            ], true);
            $logger->info(sprintf(
                'Прогон %d завершён: новых сайтов %d, в таблице %d, запросов %d из %d%s, всего в базе %d',
                $run,
                $result->stats['sites_selected'],
                count($shown),
                $queueInfo['done'],
                $queueInfo['total'],
                $queueInfo['left'] > 0 ? sprintf(' (осталось %d)', $queueInfo['left']) : '',
                $ledger->count(),
            ));
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

#!/usr/bin/env php
<?php

declare(strict_types=1);

/*
 * Локальный веб-интерфейс: запуск сбора, прогресс, ввод ключей, таймер повторного сбора.
 *
 *   php bin/panel.php [--port=8777] [--host=127.0.0.1] [--no-open]
 *
 * Открывает http://127.0.0.1:8777 в браузере. Один и тот же файл выступает и запускающим
 * скриптом, и обработчиком запросов встроенного сервера PHP (php -S).
 * Интерфейс доступен только с этого компьютера (127.0.0.1).
 */

error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);
// Страницы и их разбор бывают тяжёлыми: лимит по умолчанию (128M) ронял всё задание из-за одного сайта.
@ini_set('memory_limit', '1024M');

$root = dirname(__DIR__);

if (PHP_SAPI !== 'cli-server') {
    // --- Запуск встроенного сервера ---
    $host = '127.0.0.1';
    $port = 8777;
    $open = true;
    foreach (array_slice($argv, 1) as $arg) {
        if (str_starts_with($arg, '--port=')) {
            $port = (int) substr($arg, 7);
        } elseif (str_starts_with($arg, '--host=')) {
            $host = substr($arg, 7);
        } elseif ($arg === '--no-open') {
            $open = false;
        } elseif ($arg === '--help' || $arg === '-h') {
            fwrite(STDOUT, "php bin/panel.php [--port=8777] [--host=127.0.0.1] [--no-open]\n");
            exit(0);
        }
    }

    $projectDir = getcwd();
    @mkdir($projectDir . '/runs/current', 0777, true);
    putenv('YS_PROJECT_DIR=' . $projectDir);

    // Порт может быть занят уже запущенной (возможно, старой) панелью — не падаем, берём свободный.
    $bindHost = $host === '0.0.0.0' ? '127.0.0.1' : $host;
    $requestedPort = $port;
    $freePort = null;
    for ($p = $port; $p <= $port + 20; $p++) {
        $probe = @stream_socket_server("tcp://$bindHost:$p", $errno, $errstr);
        if ($probe !== false) {
            fclose($probe);
            $freePort = $p;
            break;
        }
    }
    if ($freePort === null) {
        fwrite(STDERR, "Порт $requestedPort и соседние заняты. Освободите порт и запустите снова:" . PHP_EOL);
        fwrite(STDERR, PHP_OS_FAMILY === 'Windows'
            ? "  netstat -ano | findstr :$requestedPort   (затем taskkill /PID <PID> /F)" . PHP_EOL
            : "  lsof -ti tcp:$requestedPort | xargs kill" . PHP_EOL);
        fwrite(STDERR, "…или укажите другой порт: php bin/panel.php --port=8788" . PHP_EOL);
        exit(1);
    }
    if ($freePort !== $requestedPort) {
        fwrite(STDOUT, "Порт $requestedPort занят — вероятно, панель уже запущена в другом окне (возможно, СТАРАЯ версия)." . PHP_EOL);
        fwrite(STDOUT, "Остановите её там (Ctrl+C) и пользуйтесь этим окном. Запускаю на свободном порту $freePort." . PHP_EOL . PHP_EOL);
        $port = $freePort;
    }

    $url = sprintf('http://%s:%d/', $bindHost, $port);
    // Версия кода — чтобы после setup.php --update было видно, что запущена именно новая сборка.
    $verSrc = (string) @file_get_contents(dirname(__DIR__) . '/src/Cli/Application.php');
    $ver = preg_match("/VERSION = '([^']+)'/", $verSrc, $vm) === 1 ? $vm[1] : '?';
    $verDate = preg_match("/VERSION_DATE = '(\d{4})-(\d{2})-(\d{2})'/", $verSrc, $vm) === 1 ? " (код от $vm[3].$vm[2].$vm[1])" : '';
    fwrite(STDOUT, "yandex-sites — веб-интерфейс запущен. Версия $ver$verDate." . PHP_EOL);
    // Папка проекта — та, из которой запущена панель: сюда нужно cd перед php bin/setup.php --update и т. п.
    fwrite(STDOUT, "Папка проекта: $projectDir" . PHP_EOL);
    fwrite(STDOUT, "Откройте в браузере: $url" . PHP_EOL);
    fwrite(STDOUT, "Остановить: Ctrl+C" . PHP_EOL . PHP_EOL);

    if ($open) {
        $opener = PHP_OS_FAMILY === 'Darwin' ? 'open' : (PHP_OS_FAMILY === 'Windows' ? 'start' : 'xdg-open');
        @exec(sprintf('(sleep 1; %s %s) >/dev/null 2>&1 &', $opener, escapeshellarg($url)));
    }

    $cmd = sprintf(
        '%s -S %s:%d -t %s %s',
        escapeshellarg(PHP_BINARY),
        escapeshellarg($host),
        $port,
        escapeshellarg($projectDir),
        escapeshellarg($root . '/bin/panel.php'),
    );
    passthru($cmd, $code);
    exit($code);
}

// --- Обработчик запросов встроенного сервера ---

if (is_file($root . '/vendor/autoload.php')) {
    require $root . '/vendor/autoload.php';
} else {
    spl_autoload_register(static function (string $class) use ($root): void {
        if (str_starts_with($class, 'YandexSites\\')) {
            $file = $root . '/src/' . str_replace('\\', '/', substr($class, strlen('YandexSites\\'))) . '.php';
            if (is_file($file)) {
                require $file;
            }
        }
    });
}

$projectDir = getenv('YS_PROJECT_DIR') ?: getcwd();
$runDir = $projectDir . '/runs/current';
@mkdir($runDir, 0777, true);
$statusFile = $runDir . '/status.json';
$settingsFile = $runDir . '/settings.json';
$stopFile = $runDir . '/stop';
$pidFile = $runDir . '/pid';
$logFile = $runDir . '/run.log';
$envFile = $projectDir . '/.env';
$baseFile = $projectDir . '/runs/domains-base.txt';

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$path = (string) parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);

function jsonOut(mixed $data, int $code = 200): void
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function body(): array
{
    $raw = (string) file_get_contents('php://input');
    $data = json_decode($raw, true);

    return is_array($data) ? $data : [];
}

function readJsonFile(string $file): ?array
{
    if (!is_file($file)) {
        return null;
    }
    $data = json_decode((string) file_get_contents($file), true);

    return is_array($data) ? $data : null;
}

/**
 * Удаляет все рабочие файлы прогона: страницы, контент, превью, убранные сайты, списки, очередь и статус
 * (кнопка «очистить базу и файлы»). Настройки (settings.json) остаются — список запросов не теряется.
 *
 * @return array{files: int, dirs: int}
 */
function resetRunFiles(string $runDir): array
{
    $files = 0;
    $dirs = 0;
    foreach (['pages', 'content', 'preview', 'removed'] as $sub) {
        $dir = $runDir . '/' . $sub;
        if (!is_dir($dir)) {
            continue;
        }
        $files += count(\YandexSites\Support\Archive::listFiles($dir));
        $dirs++;
        rmTree($dir);
    }
    $names = ['sites.json', 'sites.csv', 'domains.txt', 'results.csv', 'content.zip', 'removed.json',
        \YandexSites\Support\ContentTaken::FILE, \YandexSites\Support\SerpAnalysis::DIFF_FILE,
        \YandexSites\Support\QueryQueue::FILE, \YandexSites\Support\QueryDupes::UNIQUE_FILE, \YandexSites\Support\QueryDupes::GROUPS_FILE, 'status.json'];
    foreach ($names as $name) {
        if (is_file($runDir . '/' . $name) && @unlink($runDir . '/' . $name)) {
            $files++;
        }
    }
    @file_put_contents($runDir . '/run.log', '');

    return ['files' => $files, 'dirs' => $dirs];
}

/**
 * Сколько очищенных статей и сайтов лежит в content/<N>-стр/<host>/ — для кнопки «Скачать архив контента».
 *
 * @return array{files: int, sites: int}
 */
function contentStats(string $runDir): array
{
    $files = 0;
    $sites = 0;
    foreach (glob($runDir . '/content/*/*', GLOB_ONLYDIR) ?: [] as $siteDir) {
        $n = count(glob($siteDir . '/*.html') ?: []);
        if ($n > 0) {
            $files += $n;
            $sites++;
        }
    }

    return ['files' => $files, 'sites' => $sites];
}

/** Атомарная запись JSON (через временный файл): задание и панель читают эти файлы параллельно. */
function writeJsonFile(string $file, array $data): void
{
    $tmp = $file . '.tmp';
    file_put_contents($tmp, json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    @rename($tmp, $file);
}

function envValue(string $file, string $key): string
{
    foreach (is_file($file) ? (file($file, FILE_IGNORE_NEW_LINES) ?: []) : [] as $line) {
        if (preg_match('~^\s*' . preg_quote($key, '~') . '\s*=\s*(.*)$~', $line, $m) === 1) {
            return trim($m[1], " \t\"'");
        }
    }

    return '';
}

function setEnvValues(string $file, array $values): void
{
    $lines = is_file($file) ? (file($file, FILE_IGNORE_NEW_LINES) ?: []) : [];
    $seen = [];
    foreach ($lines as $i => $line) {
        foreach ($values as $key => $value) {
            if (preg_match('~^\s*' . preg_quote($key, '~') . '\s*=~', $line) === 1) {
                $lines[$i] = $key . '=' . $value;
                $seen[$key] = true;
            }
        }
    }
    foreach ($values as $key => $value) {
        if (!isset($seen[$key])) {
            $lines[] = $key . '=' . $value;
        }
    }
    file_put_contents($file, implode(PHP_EOL, array_filter($lines, static fn ($l) => $l !== null)) . PHP_EOL);
}

function processAlive(int $pid): bool
{
    if ($pid <= 0) {
        return false;
    }
    if (function_exists('posix_kill')) {
        return posix_kill($pid, 0);
    }
    exec(sprintf('ps -p %d', $pid), $out, $code);

    return $code === 0;
}

/**
 * Скачанные .html-страницы, сгруппированные по сайту (имя папки-сайта).
 *
 * @return array<string, list<string>>
 */
function pagesByHost(string $pagesDir): array
{
    return \YandexSites\Content\SiteCleaner::pagesByHost($pagesDir);
}

/**
 * Чистит страницы одного сайта (бренд определяется по главной) и раскладывает очищенные статьи
 * в бакет по числу страниц: runs/current/content/<N>-стр/<host>/. Ничего не скачивает.
 *
 * @param list<string> $files
 * @return array{written:int, skipped:int, dir:string, brand_ru:string, brand_en:string}
 */
function cleanHostPages(string $runDir, string $host, array $files, array $override = []): array
{
    return \YandexSites\Content\SiteCleaner::cleanHost($runDir, $host, $files, $override);
}

/**
 * Удаляет прежние очищенные страницы сайта из всех бакетов content/<N>-стр/<host>
 * (и старой плоской папки content/<host>), чтобы повторная очистка не плодила дубли.
 */
function removeHostContent(string $runDir, string $host): void
{
    \YandexSites\Content\SiteCleaner::removeHostContent($runDir, $host);
}

/**
 * Рекурсивно удаляет папку со всем содержимым (для чистого пере-сбора «Очистить всё»).
 */
function rmTree(string $dir): void
{
    \YandexSites\Content\SiteCleaner::rmTree($dir);
}

/**
 * Метки НАШИХ шаблонов для разбора выдачи: встроенная + из config.php + из own-markers.txt + из поля
 * панели «Метки наших шаблонов». config.php читаем как обычный массив, без проверки настроек: панель
 * работает и без него, а падать из-за незаполненных ключей источника здесь незачем.
 */
function ownSitesForPanel(string $projectDir, array $settings): \YandexSites\Filter\OwnSites
{
    $markers = (array) (\YandexSites\Config::defaults()['filters']['own_markers'] ?? []);
    $file = 'own-markers.txt';
    $raw = is_file($projectDir . '/config.php') ? @include $projectDir . '/config.php' : null;
    if (is_array($raw)) {
        foreach ((array) ($raw['filters']['own_markers'] ?? []) as $m) {
            $markers[] = (string) $m;
        }
        $file = (string) ($raw['filters']['own_markers_file'] ?? $file);
    }
    $path = $file !== '' && $file[0] !== '/' ? $projectDir . '/' . $file : $file;
    if ($path !== '' && is_file($path)) {
        foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
            $markers[] = (string) $line;
        }
    }
    foreach ((array) ($settings['own_markers'] ?? []) as $m) {
        $markers[] = (string) $m;
    }

    return new \YandexSites\Filter\OwnSites($markers);
}

/**
 * Накопленный список НАШИХ доменов: его ведёт сбор (runs/own-domains.txt) плюс ручной own-domains.txt
 * в папке проекта. По нему «наш» узнаётся и у домена, который пришёл повтором и уже не открывался.
 *
 * @return list<string>
 */
function ownDomainsForPanel(string $projectDir): array
{
    $out = [];
    foreach ([$projectDir . '/runs/own-domains.txt', $projectDir . '/own-domains.txt'] as $file) {
        if (!is_file($file)) {
            continue;
        }
        foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
            $line = trim($line);
            if ($line !== '' && $line[0] !== '#') {
                $out[] = $line;
            }
        }
    }

    return array_values(array_unique($out));
}

// --- Роутинг ---

if ($path === '/' || $path === '/index.html') {
    $html = @file_get_contents(dirname(__DIR__) . '/public/panel.html');
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, must-revalidate'); // всегда свежий интерфейс после обновления
    echo $html !== false ? $html : '<h1>Не найден public/panel.html</h1>';
    exit;
}

if ($path === '/serp' || $path === '/serp.html') {
    // Технический разбор выдачи — ОТДЕЛЬНАЯ страница: собственный HTML, свой опрос API, главная не меняется.
    $html = @file_get_contents(dirname(__DIR__) . '/public/serp.html');
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, must-revalidate');
    echo $html !== false ? $html : '<h1>Не найден public/serp.html</h1>';
    exit;
}

if ($path === '/api/state') {
    $status = readJsonFile($statusFile);
    $pid = is_file($pidFile) ? (int) file_get_contents($pidFile) : 0;
    // Остановка теперь мягкая: процесс ещё жив и досохраняет собранное, поэтому «выполняется» — это
    // живой процесс, а флаг stopping говорит панели показать «останавливаю…» и кнопку аварийной остановки.
    $running = $pid > 0 && processAlive($pid);
    $stopping = $running && is_file($stopFile);
    // Таблица сайтов не должна пропадать после обновления страницы или перезапуска панели: если в статусе
    // нет списка (идёт выгрузка/докачка, была ошибка, статус стёрт), берём прошлый сбор из sites.json.
    $fromFile = empty($status['sites']);
    // Строки прошлой версии (без поля template — тип вёрстки) один раз пересобираем из sites.json, дописав тип
    // по сохранённому HTML: после обновления скрипта типы видны на прошлом сборе, новый сбор не нужен.
    $stale = !$fromFile && !$running && is_array($status['sites'][0] ?? null) && !array_key_exists('template', $status['sites'][0]);
    if (($fromFile || $stale) && is_file($runDir . '/sites.json')) {
        $sites = \YandexSites\Support\SiteRows::load($runDir . '/sites.json');
        if (!$running && \YandexSites\Support\SiteRows::backfillTemplates($sites) > 0) {
            \YandexSites\Support\SiteRows::saveTemplates($runDir . '/sites.json', $sites);
        }
        $rows = \YandexSites\Support\SiteRows::preview($sites, $runDir);
        if ($rows !== []) {
            $status = is_array($status) ? $status : ['state' => 'idle', 'phase' => 'idle'];
            $status['sites'] = $rows;
            $status['sites_count'] = count($sites);
            $status['sites_from_file'] = true;
            if ($stale) {
                writeJsonFile($statusFile, $status); // следующий опрос уже видит типы и ничего не пересобирает
            }
        }
    }
    jsonOut([
        'ok' => true,
        // Версия кода для шапки панели: после setup.php --update пользователь сверяет её здесь.
        'version' => \YandexSites\Cli\Application::VERSION,
        // Папка проекта (откуда запущена панель) — показывается в шапке, чтобы было куда делать cd в консоли.
        'project_dir' => $projectDir,
        'version_date' => \YandexSites\Cli\Application::VERSION_DATE,
        'keys' => [
            'xmlstock_user' => envValue($envFile, 'XMLSTOCK_USER'),
            'xmlstock_key_set' => envValue($envFile, 'XMLSTOCK_KEY') !== '',
            'yandex_folder' => envValue($envFile, 'YANDEX_FOLDER_ID'),
            'yandex_key_set' => envValue($envFile, 'YANDEX_API_KEY') !== '',
        ],
        'settings' => readJsonFile($settingsFile),
        'status' => $status,
        'running' => $running,
        'stopping' => $stopping,
        // Очередь запросов: сколько уже обработано и сколько осталось для «Продолжить сбор».
        'queue' => \YandexSites\Support\QueryQueue::summary(\YandexSites\Support\QueryQueue::load($runDir . '/' . \YandexSites\Support\QueryQueue::FILE)),
        // Серверный список убранных сайтов — источник истины для таблицы (см. Support\RemovedSites).
        'removed' => \YandexSites\Support\RemovedSites::hosts($runDir),
        'has_config' => is_file($projectDir . '/config.php'),
        'has_proxies' => is_file($projectDir . '/proxies.txt'),
        // Очищенный контент на диске — кнопка «Скачать архив контента» показывает, сколько статей и сайтов в архиве.
        // Результаты последнего сбора (results.csv): по ним панель считает запросы с одинаковой выдачей.
        'has_results' => is_file($runDir . '/results.csv'),
        'results_stamp' => is_file($runDir . '/results.csv') ? filemtime($runDir . '/results.csv') . '-' . filesize($runDir . '/results.csv') : '',
        'content_files' => contentStats($runDir)['files'],
        // Сколько статей ещё НЕ забирали архивом: выгрузка идёт волнами, и забирать каждый раз весь
        // контент заново незачем — кнопка «Скачать новое» отдаёт только их (см. Support\ContentTaken).
        'content_new' => \YandexSites\Support\ContentTaken::stats(\YandexSites\Support\ContentTaken::newFiles($runDir, $runDir . '/content')),
        'content_waves' => \YandexSites\Support\ContentTaken::load($runDir)['wave'],
        // Сколько папок сайтов уже выгружено: новый сбор их удалит, поэтому панель предупреждает.
        'pages_sites' => count(glob($runDir . '/pages/*/*', GLOB_ONLYDIR) ?: []) + count(glob($runDir . '/pages/*/*.html') ?: []),
        'content_sites' => contentStats($runDir)['sites'],
        'base_domains' => is_file($baseFile) ? count(array_filter(array_map('trim', file($baseFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: []), static fn ($l) => $l !== '' && $l[0] !== '#')) : 0,
    ]);
}

if ($path === '/api/keys' && $method === 'POST') {
    $b = body();
    $values = [];
    if (isset($b['xmlstock_user'])) {
        $values['XMLSTOCK_USER'] = trim((string) $b['xmlstock_user']);
    }
    if (isset($b['xmlstock_key']) && trim((string) $b['xmlstock_key']) !== '') {
        $values['XMLSTOCK_KEY'] = trim((string) $b['xmlstock_key']);
    }
    if (isset($b['yandex_folder'])) {
        $values['YANDEX_FOLDER_ID'] = trim((string) $b['yandex_folder']);
    }
    if (isset($b['yandex_key']) && trim((string) $b['yandex_key']) !== '') {
        $values['YANDEX_API_KEY'] = trim((string) $b['yandex_key']);
    }
    if ($values !== []) {
        setEnvValues($envFile, $values);
    }
    jsonOut(['ok' => true]);
}

if ($path === '/api/start' && $method === 'POST') {
    $pid = is_file($pidFile) ? (int) file_get_contents($pidFile) : 0;
    if ($pid > 0 && processAlive($pid)) {
        jsonOut(['ok' => false, 'error' => is_file($stopFile)
            ? 'Идёт остановка предыдущего задания — оно досохраняет собранное, подождите несколько секунд'
            : 'Сбор уже запущен'], 409);
    }
    $settings = body();
    $stage = (string) ($settings['stage'] ?? 'collect');
    $queries = array_values(array_filter(array_map('trim', (array) ($settings['queries'] ?? [])), static fn (string $q): bool => $q !== ''));
    if (!in_array($stage, ['download', 'clean', 'preview'], true) && $queries === []) {
        jsonOut(['ok' => false, 'error' => 'Добавьте хотя бы один запрос'], 400);
    }
    @unlink($stopFile);
    file_put_contents($settingsFile, json_encode($settings, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    @unlink($statusFile);
    @file_put_contents($logFile, '');

    $cmd = sprintf(
        '%s %s --settings=%s --status=%s >> %s 2>&1 & echo $!',
        escapeshellarg(PHP_BINARY),
        escapeshellarg(dirname(__DIR__) . '/bin/run-job.php'),
        escapeshellarg($settingsFile),
        escapeshellarg($statusFile),
        escapeshellarg($logFile),
    );
    $out = [];
    exec($cmd, $out);
    $newPid = (int) ($out[0] ?? 0);
    file_put_contents($pidFile, (string) $newPid);
    jsonOut(['ok' => true, 'pid' => $newPid]);
}

if ($path === '/api/stop' && $method === 'POST') {
    // Мягкая остановка: задание дописывает текущий запрос, сохраняет собранное и позицию в очереди —
    // с этой частью можно работать, а «Продолжить сбор» запустит остаток. force=true — аварийно убить
    // процесс (задание зависло): собранное с момента последнего сохранения теряется.
    $force = (bool) (body()['force'] ?? false);
    file_put_contents($stopFile, '1');
    $pid = is_file($pidFile) ? (int) file_get_contents($pidFile) : 0;
    if ($force && $pid > 0) {
        @exec(sprintf('pkill -P %d 2>/dev/null', $pid));
        if (function_exists('posix_kill')) {
            @posix_kill($pid, 15);
        } else {
            @exec(sprintf('kill %d 2>/dev/null', $pid));
        }
    }
    jsonOut(['ok' => true, 'force' => $force]);
}

if ($path === '/api/reset-base' && $method === 'POST') {
    // «Очистить базу и файлы»: база пересечений доменов + ВСЕ рабочие файлы прогона — скачанные страницы,
    // очищенный контент, превью, списки и очередь запросов. Итоговый архив контента пользователь скачивает
    // через панель, так что pages/ и content/ — технические папки: следующий сбор начинается с чистого листа.
    $pid = is_file($pidFile) ? (int) file_get_contents($pidFile) : 0;
    if ($pid > 0 && processAlive($pid)) {
        jsonOut(['ok' => false, 'error' => 'Сначала остановите задание — сейчас оно пишет в эти папки'], 409);
    }
    @file_put_contents($baseFile, '');
    // Список НАШИХ доменов — тоже часть базы: он накоплен прошлыми сборами.
    @file_put_contents($projectDir . '/runs/own-domains.txt', '');
    // Статистику сборов (runs/history.json) здесь НЕ трогаем: это летопись, ради которой вкладка
    // и заведена, и терять её вместе с базой пользователь не хочет. Для неё есть своя кнопка
    // «очистить статистику» (/api/reset-history) — чистки разделены намеренно.
    $wiped = resetRunFiles($runDir);
    jsonOut(['ok' => true, 'history' => 0] + $wiped);
}

if ($path === '/api/reset-history' && $method === 'POST') {
    // «Очистить статистику» — только история сборов (runs/history.json), база доменов и файлы прогона
    // не трогаются. Отдельная кнопка: статистику иногда надо начать с чистого листа, не теряя базу.
    $n = \YandexSites\Support\CollectHistory::clear($projectDir . '/runs');
    jsonOut(['ok' => true, 'records' => $n]);
}

if ($path === '/api/content-reset' && $method === 'POST') {
    // «Считать весь контент новым» — забываем отметки о скачанных архивах. Нужно, если архив потерялся
    // или его надо пересобрать по частям заново; сами статьи на диске при этом не трогаются.
    $before = \YandexSites\Support\ContentTaken::load($runDir)['files'];
    \YandexSites\Support\ContentTaken::reset($runDir);
    jsonOut(['ok' => true, 'forgotten' => count($before)]);
}

if ($path === '/api/results') {
    $data = readJsonFile($runDir . '/sites.json') ?? ['sites' => []];
    jsonOut($data);
}

if ($path === '/api/site-pages' && $method === 'POST') {
    // Детали одного сайта: список открытых страниц с результатом (для раскрытия строки в таблице,
    // чтобы посмотреть, какие именно страницы упали с ошибкой). Данные берём из sites.json.
    $host = trim((string) (body()['host'] ?? ''));
    if ($host === '' || preg_match('~^[a-z0-9.\-]+$~i', $host) !== 1) {
        jsonOut(['ok' => false, 'error' => 'некорректный сайт'], 400);
    }
    $data = readJsonFile($runDir . '/sites.json') ?? ['sites' => []];
    $prefix = rtrim($runDir, '/\\') . '/';
    $rel = static fn (string $p): string => $p !== '' && str_starts_with($p, $prefix) ? substr($p, strlen($prefix)) : $p;
    $pages = [];
    foreach ((array) ($data['sites'] ?? []) as $s) {
        if ((string) ($s['host'] ?? '') !== $host) {
            continue;
        }
        foreach ((array) ($s['visits'] ?? []) as $v) {
            $pages[] = [
                'url' => (string) ($v['url'] ?? ''),
                'final_url' => (string) ($v['final_url'] ?? ''),
                'ok' => (bool) ($v['ok'] ?? false),
                'error' => (string) ($v['error'] ?? ''),
                'status' => $v['status'] ?? null,
                'variant' => $v['variant'] ?? null,
                'duplicate_of' => (string) ($v['duplicate_of'] ?? ''),
                // Страница пришла только под браузером — сайт закрыт от робота поисковика.
                'as_browser' => ($v['ok'] ?? false)
                    && (string) ($v['user_agent'] ?? '') !== ''
                    && !\YandexSites\Live\UserAgents::isBot((string) $v['user_agent']),
                'html' => $rel((string) ($v['html_file'] ?? '')),
                'screenshot' => $rel((string) ($v['screenshot_file'] ?? '')),
            ];
        }
        break;
    }
    jsonOut(['ok' => true, 'host' => $host, 'pages' => $pages]);
}

if ($path === '/api/query-dupes') {
    // Запросы с одинаковой выдачей — по results.csv последнего сбора (работает и для сбора, сделанного до
    // обновления). Порядок списка из settings.json решает, кто из дублей остаётся; файлы пишутся рядом.
    $csv = $runDir . '/results.csv';
    if (!is_file($csv)) {
        jsonOut(['ok' => false, 'error' => 'Нет результатов сбора (results.csv) — сначала соберите сайты']);
    }
    $saved = readJsonFile($settingsFile) ?? [];
    $queryList = array_values(array_filter(array_map('trim', array_map('strval', (array) ($saved['queries'] ?? []))), static fn (string $q): bool => $q !== '' && !str_starts_with($q, '#')));
    $found = \YandexSites\Support\QueryDupes::find(\YandexSites\Support\QueryDupes::csvRows($csv), $queryList);
    \YandexSites\Support\QueryDupes::writeFiles($runDir, $found);
    jsonOut(['ok' => true, 'summary' => \YandexSites\Support\QueryDupes::summary($found)] + $found);
}

if ($path === '/api/serp') {
    // Разбор строится НА ЛЕТУ из results.csv: он описывает весь текущий сбор, поэтому разбор всегда
    // соответствует собранному и работает даже для сбора, сделанного до обновления скрипта.
    // Без параметра — список брендов с итогами; brand=<ключ> — ключи этого бренда со всей выдачей.
    $csv = $runDir . '/results.csv';
    if (!is_file($csv)) {
        jsonOut(['ok' => false, 'error' => 'Нет результатов сбора (results.csv) — сначала соберите сайты']);
    }
    $top = max(0, min(100, (int) ($_GET['top'] ?? 10)));
    $saved = readJsonFile($settingsFile) ?? [];
    $ownSites = ownSitesForPanel($projectDir, $saved);
    $ownDomains = ownDomainsForPanel($projectDir);
    $analysis = \YandexSites\Support\SerpAnalysis::build(
        \YandexSites\Support\SerpAnalysis::csvRows($csv),
        $top,
        $ownSites,
        $ownDomains,
    );
    $diff = readJsonFile($runDir . '/' . \YandexSites\Support\SerpAnalysis::DIFF_FILE) ?? ['brands' => [], 'totals' => ['added' => 0, 'removed' => 0]];
    $want = trim((string) ($_GET['brand'] ?? ''));
    if ($want !== '' || isset($_GET['brand'])) {
        foreach ($analysis['brands'] as $brand) {
            if ((string) $brand['key'] === $want) {
                jsonOut(['ok' => true, 'brand' => $brand, 'diff' => $diff['brands'][$want] ?? null]);
            }
        }
        jsonOut(['ok' => false, 'error' => 'Бренд не найден в текущем сборе']);
    }
    // В списке брендов сами строки выдачи не нужны — их запрашивает раскрытый блок.
    $list = [];
    foreach ($analysis['brands'] as $brand) {
        unset($brand['queries'], $brand['hosts']);
        $brand['diff'] = $diff['brands'][(string) $brand['key']] ?? null;
        $list[] = $brand;
    }
    jsonOut([
        'ok' => true,
        'brands' => $list,
        'totals' => $analysis['totals'],
        'totals_sum' => $analysis['totals_sum'],
        'repeats' => $analysis['repeats'],
        'own' => $analysis['own'],
        'sites' => $analysis['sites'],
        'results' => $analysis['results'],
        'queries' => $analysis['queries'],
        'top' => $top,
        'types' => \YandexSites\Support\SerpAnalysis::TYPES,
        // Действующие метки и размер списка наших доменов: без них не понять, ПОЧЕМУ сайт «наш».
        'own_markers' => $ownSites->markers(),
        'own_domains' => count($ownDomains),
        'diff_totals' => $diff['totals'] ?? ['added' => 0, 'removed' => 0],
        'diff_at' => $diff['compared_at'] ?? '',
        'version' => \YandexSites\Cli\Application::VERSION,
    ]);
}

if ($path === '/api/history') {
    // Вкладка «Статистика»: история сборов (runs/history.json) — по одной записи на сбор — и итог по всем.
    // Записи версий 1.10.0–1.11.0 считали доры по ключу группировки (при дедупе по домену это
    // регистрируемый домен), и в последней записи стояло «доров 0»; записи до 1.15.0 не знали про
    // наши шаблоны — пересчитываем последнюю запись по sites.json, где видно и хосты, и признак «наш».
    // Делается один раз: результат сохраняется обратно в историю.
    // Воронку (сайты выдачи + что срезали фильтры) прошлого сбора можно пересчитать по results.csv —
    // там лежат те же строки выдачи с причинами; иначе старая запись показывала бы прочерки.
    $savedSettings = (array) (readJsonFile($settingsFile) ?? []);
    $historyUniqueBy = ($savedSettings['dedupe_domain'] ?? true) ? 'domain' : 'host';
    \YandexSites\Support\CollectHistory::backfillFunnel($projectDir . '/runs', $runDir . '/results.csv', $historyUniqueBy);
    \YandexSites\Support\CollectHistory::backfillLatest($projectDir . '/runs', \YandexSites\Support\SiteRows::load($runDir . '/sites.json'));
    $records = \YandexSites\Support\CollectHistory::load($projectDir . '/runs');
    jsonOut([
        'ok' => true,
        'records' => $records,
        'totals' => \YandexSites\Support\CollectHistory::totals($records),
    ]);
}

if ($path === '/api/remove' && $method === 'POST') {
    // Крестик / «Убрать наши» / «Убрать с 404 > N»: удаление окончательное и сквозное — строка уходит из
    // sites.json и статуса, папки сайта переезжают в removed/. Следующие шаги сайт больше не видят.
    $hosts = array_values(array_filter(array_map('strval', (array) (body()['hosts'] ?? [])), static fn (string $h): bool => preg_match('~^[a-z0-9.\-]+$~i', $h) === 1));
    $n = \YandexSites\Support\RemovedSites::remove($runDir, $hosts);
    jsonOut(['ok' => true, 'removed' => $n, 'removed_total' => count(\YandexSites\Support\RemovedSites::hosts($runDir))]);
}

if ($path === '/api/restore' && $method === 'POST') {
    // «Вернуть все» (или указанные хосты): строки и папки возвращаются на место.
    $b = body();
    $hosts = isset($b['hosts']) && is_array($b['hosts']) && $b['hosts'] !== [] ? array_values(array_map('strval', $b['hosts'])) : null;
    $n = \YandexSites\Support\RemovedSites::restore($runDir, $hosts);
    jsonOut(['ok' => true, 'restored' => $n, 'removed_total' => count(\YandexSites\Support\RemovedSites::hosts($runDir))]);
}

if ($path === '/api/clean-site' && $method === 'POST') {
    // Кнопка «Очистить» у сайта: чистит его страницы по инструкции и кладёт в content/<N>-стр/<host>/.
    // Ничего не скачивает; бренд определяется сам.
    $b = body();
    $host = trim((string) ($b['host'] ?? ''));
    if ($host === '' || preg_match('~^[a-z0-9.\-]+$~i', $host) !== 1) {
        jsonOut(['ok' => false, 'error' => 'некорректный сайт'], 400);
    }
    $files = pagesByHost($runDir . '/pages')[$host] ?? [];
    if ($files === []) {
        jsonOut(['ok' => false, 'error' => 'нет скачанных страниц для этого сайта — сначала «Выгрузка страниц»'], 404);
    }
    // Каталоги слотов по умолчанию остаются; галочка «Убирать каталоги слотов» приходит с кнопкой.
    $r = cleanHostPages($runDir, $host, $files, [
        'remove_slots' => filter_var($b['remove_slots'] ?? false, FILTER_VALIDATE_BOOL),
        'remove_widgets' => filter_var($b['remove_widgets'] ?? false, FILTER_VALIDATE_BOOL),
    ]);
    jsonOut(['ok' => true, 'written' => $r['written'], 'skipped' => $r['skipped'], 'skipped_files' => $r['skipped_files'], 'dir' => $r['dir'], 'brand_ru' => $r['brand_ru'], 'brand_en' => $r['brand_en']]);
}

if ($path === '/api/log') {
    header('Content-Type: text/plain; charset=utf-8');
    if (!is_file($logFile)) {
        echo '';
        exit;
    }
    $lines = file($logFile, FILE_IGNORE_NEW_LINES) ?: [];
    echo implode(PHP_EOL, array_slice($lines, -400));
    exit;
}

if ($path === '/file') {
    $rel = ltrim(str_replace('\\', '/', (string) ($_GET['path'] ?? '')), '/');
    $base = realpath($runDir);
    $full = $base !== false ? realpath($runDir . '/' . $rel) : false;
    if ($rel === '' || str_contains($rel, '..') || $full === false || $base === false || !str_starts_with($full, $base . DIRECTORY_SEPARATOR) || !is_file($full)) {
        http_response_code(404);
        echo 'not found';
        exit;
    }
    $ext = strtolower(pathinfo($full, PATHINFO_EXTENSION));
    $types = ['html' => 'text/html; charset=utf-8', 'png' => 'image/png', 'jpg' => 'image/jpeg', 'txt' => 'text/plain; charset=utf-8', 'json' => 'application/json; charset=utf-8', 'csv' => 'text/csv; charset=utf-8', 'zip' => 'application/zip'];
    header('Content-Type: ' . ($types[$ext] ?? 'application/octet-stream'));
    if ($ext === 'zip') {
        header('Content-Disposition: attachment; filename="' . basename($full) . '"');
    }
    readfile($full);
    exit;
}

if ($path === '/download' && (string) ($_GET['file'] ?? '') === 'content') {
    // «Скачать архив контента»: свежий zip из runs/current/content — внутри папки N-стр/сайт/страница.html,
    // ровно как на диске; распаковывается в нужную папку без лишнего верхнего уровня.
    // part=new отдаёт ТОЛЬКО то, что ещё не забирали (следующая волна выгрузки), и помечает забранным;
    // без part отдаётся весь контент — и тоже помечается, чтобы «новое» дальше считалось от этой точки.
    $contentDir = $runDir . '/content';
    $onlyNew = (string) ($_GET['part'] ?? '') === 'new';
    $files = $onlyNew
        ? \YandexSites\Support\ContentTaken::newFiles($runDir, $contentDir)
        : \YandexSites\Support\Archive::listFiles($contentDir);
    if ($files === []) {
        http_response_code(404);
        header('Content-Type: text/plain; charset=utf-8');
        echo $onlyNew
            ? 'Нового контента нет — всё, что очищено, уже скачано. Нажмите «Скачать всё», если нужен полный архив'
            : 'Очищенного контента пока нет — сначала «Очистить» у сайта или «Очистить всё»';
        exit;
    }
    try {
        \YandexSites\Support\Archive::zipFiles($files, $runDir . '/content.zip');
    } catch (\RuntimeException $e) {
        http_response_code(500);
        header('Content-Type: text/plain; charset=utf-8');
        echo $e->getMessage();
        exit;
    }
    $wave = \YandexSites\Support\ContentTaken::markTaken($runDir, $files);
    $name = ($onlyNew ? 'content-part-' . $wave . '-' : 'content-') . date('Y-m-d') . '.zip';
    header('Content-Type: application/zip');
    header('Content-Disposition: attachment; filename="' . $name . '"');
    header('Content-Length: ' . (string) filesize($runDir . '/content.zip'));
    readfile($runDir . '/content.zip');
    exit;
}

if ($path === '/download' && (string) ($_GET['file'] ?? '') === 'history') {
    // История сборов в CSV (открывается в Excel) — строится из runs/history.json на лету.
    $records = \YandexSites\Support\CollectHistory::load($projectDir . '/runs');
    if ($records === []) {
        http_response_code(404);
        header('Content-Type: text/plain; charset=utf-8');
        echo 'История сборов пока пуста — соберите сайты хотя бы один раз';
        exit;
    }
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="collects-' . date('Y-m-d') . '.csv"');
    echo \YandexSites\Support\CollectHistory::csv($records);
    exit;
}

if ($path === '/download') {
    $map = ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv', 'queries-unique' => 'queries-unique.txt', 'query-dupes' => 'query-dupes.txt', 'brand-domains' => \YandexSites\Support\BrandDomains::FILE];
    $key = (string) ($_GET['file'] ?? '');
    $file = $runDir . '/' . ($map[$key] ?? '');
    if (!isset($map[$key]) || !is_file($file)) {
        http_response_code(404);
        echo 'not found';
        exit;
    }
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . $map[$key] . '"');
    readfile($file);
    exit;
}

http_response_code(404);
header('Content-Type: application/json; charset=utf-8');
echo json_encode(['ok' => false, 'error' => 'not found'], JSON_UNESCAPED_UNICODE);

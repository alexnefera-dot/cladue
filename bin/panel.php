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
    fwrite(STDOUT, "yandex-sites — веб-интерфейс запущен." . PHP_EOL);
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
    $byHost = [];
    if (is_dir($pagesDir)) {
        $iter = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($pagesDir, FilesystemIterator::SKIP_DOTS));
        foreach ($iter as $f) {
            if ($f instanceof SplFileInfo && $f->isFile() && strtolower($f->getExtension()) === 'html') {
                $host = basename(dirname($f->getPathname()));
                if (str_contains($host, '.')) {
                    $byHost[$host][] = $f->getPathname();
                }
            }
        }
    }
    ksort($byHost);

    return $byHost;
}

/**
 * Чистит страницы одного сайта (бренд определяется по главной) и раскладывает очищенные статьи
 * в бакет по числу страниц: runs/current/content/<N>-стр/<host>/. Ничего не скачивает.
 *
 * @param list<string> $files
 * @return array{written:int, skipped:int, dir:string, brand_ru:string, brand_en:string}
 */
function cleanHostPages(string $runDir, string $host, array $files): array
{
    sort($files);
    $home = $files[0] ?? '';
    foreach ($files as $f) {
        if (basename($f) === 'main.html') {
            $home = $f;
            break;
        }
    }
    $opts = \YandexSites\Content\ContentCleaner::autoOptions($home !== '' ? (string) file_get_contents($home) : '', $host);
    $cleaner = new \YandexSites\Content\ContentCleaner();
    // Чистим в память, чтобы узнать итоговое число страниц и назвать по нему папку-бакет.
    $cleaned = [];
    $skipped = 0;
    foreach ($files as $file) {
        $body = $cleaner->clean((string) file_get_contents($file), $opts);
        if (trim($body) === '') {
            $skipped++;
            continue;
        }
        $cleaned[basename($file)] = $body;
    }
    $written = count($cleaned);
    // Прежние очищенные версии этого сайта убираем из любого бакета, чтобы не осталось дублей.
    removeHostContent($runDir, $host);
    $rel = 'content/' . $written . '-стр/' . $host;
    if ($written > 0) {
        $outDir = $runDir . '/' . $rel;
        @mkdir($outDir, 0777, true);
        foreach ($cleaned as $name => $body) {
            file_put_contents($outDir . '/' . $name, $body);
        }
    }

    return ['written' => $written, 'skipped' => $skipped, 'dir' => $rel, 'brand_ru' => (string) ($opts['brand_ru'] ?? ''), 'brand_en' => (string) ($opts['brand_en'] ?? '')];
}

/**
 * Удаляет прежние очищенные страницы сайта из всех бакетов content/<N>-стр/<host>
 * (и старой плоской папки content/<host>), чтобы повторная очистка не плодила дубли.
 */
function removeHostContent(string $runDir, string $host): void
{
    $dirs = array_merge(
        glob($runDir . '/content/*/' . $host, GLOB_ONLYDIR) ?: [],
        glob($runDir . '/content/' . $host, GLOB_ONLYDIR) ?: [],
    );
    foreach ($dirs as $dir) {
        foreach (glob($dir . '/*') ?: [] as $f) {
            @unlink($f);
        }
        @rmdir($dir);
        @rmdir(dirname($dir)); // пустой бакет убираем тоже
    }
}

// --- Роутинг ---

if ($path === '/' || $path === '/index.html') {
    $html = @file_get_contents(dirname(__DIR__) . '/public/panel.html');
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store, must-revalidate'); // всегда свежий интерфейс после обновления
    echo $html !== false ? $html : '<h1>Не найден public/panel.html</h1>';
    exit;
}

if ($path === '/api/state') {
    $status = readJsonFile($statusFile);
    $pid = is_file($pidFile) ? (int) file_get_contents($pidFile) : 0;
    $running = $pid > 0 && processAlive($pid) && !is_file($stopFile);
    jsonOut([
        'ok' => true,
        'keys' => [
            'xmlstock_user' => envValue($envFile, 'XMLSTOCK_USER'),
            'xmlstock_key_set' => envValue($envFile, 'XMLSTOCK_KEY') !== '',
            'yandex_folder' => envValue($envFile, 'YANDEX_FOLDER_ID'),
            'yandex_key_set' => envValue($envFile, 'YANDEX_API_KEY') !== '',
        ],
        'settings' => readJsonFile($settingsFile),
        'status' => $status,
        'running' => $running,
        'has_config' => is_file($projectDir . '/config.php'),
        'has_proxies' => is_file($projectDir . '/proxies.txt'),
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
    if ($pid > 0 && processAlive($pid) && !is_file($stopFile)) {
        jsonOut(['ok' => false, 'error' => 'Сбор уже запущен'], 409);
    }
    $settings = body();
    $stage = (string) ($settings['stage'] ?? 'collect');
    $queries = array_values(array_filter(array_map('trim', (array) ($settings['queries'] ?? [])), static fn (string $q): bool => $q !== ''));
    if (!in_array($stage, ['download', 'clean'], true) && $queries === []) {
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
    file_put_contents($stopFile, '1');
    $pid = is_file($pidFile) ? (int) file_get_contents($pidFile) : 0;
    if ($pid > 0) {
        @exec(sprintf('pkill -P %d 2>/dev/null', $pid));
        if (function_exists('posix_kill')) {
            @posix_kill($pid, 15);
        } else {
            @exec(sprintf('kill %d 2>/dev/null', $pid));
        }
    }
    jsonOut(['ok' => true]);
}

if ($path === '/api/reset-base' && $method === 'POST') {
    @file_put_contents($baseFile, '');
    jsonOut(['ok' => true]);
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
                'html' => $rel((string) ($v['html_file'] ?? '')),
                'screenshot' => $rel((string) ($v['screenshot_file'] ?? '')),
            ];
        }
        break;
    }
    jsonOut(['ok' => true, 'host' => $host, 'pages' => $pages]);
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
    $r = cleanHostPages($runDir, $host, $files);
    jsonOut(['ok' => true, 'written' => $r['written'], 'skipped' => $r['skipped'], 'dir' => $r['dir'], 'brand_ru' => $r['brand_ru'], 'brand_en' => $r['brand_en']]);
}

if ($path === '/api/clean-all' && $method === 'POST') {
    // Кнопка «Очистить всё»: чистит все скачанные сайты (наши уже исключены на выгрузке) и раскладывает
    // по content/<N>-стр/<host>/. Ничего не скачивает. exclude — сайты, убранные крестиком в таблице.
    $exclude = array_flip(array_map('strval', (array) (body()['exclude'] ?? [])));
    $byHost = pagesByHost($runDir . '/pages');
    if ($byHost === []) {
        jsonOut(['ok' => false, 'error' => 'нет скачанных страниц — сначала «Выгрузка страниц»'], 404);
    }
    $written = 0;
    $skipped = 0;
    $sites = 0;
    foreach ($byHost as $host => $files) {
        if (isset($exclude[$host])) {
            continue;
        }
        $r = cleanHostPages($runDir, (string) $host, $files);
        $written += $r['written'];
        $skipped += $r['skipped'];
        if ($r['written'] > 0) {
            $sites++;
        }
    }
    jsonOut(['ok' => true, 'written' => $written, 'skipped' => $skipped, 'sites' => $sites]);
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

if ($path === '/download') {
    $map = ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv', 'content' => 'content.zip'];
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

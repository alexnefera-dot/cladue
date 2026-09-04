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

    $url = sprintf('http://%s:%d/', $host === '0.0.0.0' ? '127.0.0.1' : $host, $port);
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

// --- Роутинг ---

if ($path === '/' || $path === '/index.html') {
    $html = @file_get_contents(dirname(__DIR__) . '/public/panel.html');
    header('Content-Type: text/html; charset=utf-8');
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
    if ($stage !== 'download' && $queries === []) {
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

if ($path === '/api/log') {
    header('Content-Type: text/plain; charset=utf-8');
    if (!is_file($logFile)) {
        echo '';
        exit;
    }
    $lines = file($logFile, FILE_IGNORE_NEW_LINES) ?: [];
    echo implode(PHP_EOL, array_slice($lines, -200));
    exit;
}

if ($path === '/download') {
    $map = ['csv' => 'sites.csv', 'json' => 'sites.json', 'domains' => 'domains.txt', 'results' => 'results.csv'];
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

#!/usr/bin/env php
<?php

declare(strict_types=1);

/*
 * Первичная настройка проекта одной командой:
 *
 *   php bin/setup.php [--proxy=http://host:port:user:pass ...] [--force] [--dir=ПАПКА]
 *
 * Создаёт config.php, .env и proxies.txt из примеров (существующие файлы не трогает,
 * если не указан --force), добавляет прокси из --proxy в proxies.txt, создаёт папки
 * cache/, out/, debug/, проверяет PHP-расширения и Node.js/Playwright и печатает
 * команды для проверки прокси и пробного запуска.
 */

$root = dirname(__DIR__);
$target = $root;
$proxies = [];
$force = false;

foreach (array_slice($argv, 1) as $arg) {
    if (str_starts_with($arg, '--proxy=')) {
        $proxies[] = trim(substr($arg, 8));
    } elseif (str_starts_with($arg, '--dir=')) {
        $target = rtrim(substr($arg, 6), '/\\');
    } elseif ($arg === '--force') {
        $force = true;
    } elseif ($arg === '--help' || $arg === '-h') {
        fwrite(STDOUT, "Использование: php bin/setup.php [--proxy=http://host:port:user:pass ...] [--force] [--dir=ПАПКА]\n");
        exit(0);
    } else {
        fwrite(STDERR, "Неизвестный аргумент: $arg\n");
        exit(2);
    }
}

$ok = static fn (string $text): string => '  [OK] ' . $text . PHP_EOL;
$warn = static fn (string $text): string => '  [!!] ' . $text . PHP_EOL;
$problems = 0;

if (!is_dir($target) && !@mkdir($target, 0777, true)) {
    fwrite(STDERR, "Не удалось создать папку $target\n");
    exit(1);
}
$target = realpath($target) ?: $target;

echo "Папка проекта: $target" . PHP_EOL . PHP_EOL;

// --- PHP
echo 'PHP ' . PHP_VERSION . PHP_EOL;
if (version_compare(PHP_VERSION, '8.1.0', '<')) {
    echo $warn('нужен PHP 8.1 или новее');
    $problems++;
} else {
    echo $ok('версия подходит');
}
foreach (['curl', 'dom', 'json', 'mbstring'] as $ext) {
    if (extension_loaded($ext)) {
        echo $ok("расширение $ext");
    } else {
        echo $warn("нет расширения $ext — включите его в php.ini");
        $problems++;
    }
}
echo extension_loaded('intl') ? $ok('расширение intl') : $warn('нет расширения intl — кириллические домены в фильтрах нужно писать в punycode (необязательно)');
echo PHP_EOL;

// --- Файлы из примеров
echo 'Файлы настроек' . PHP_EOL;
$copies = [
    'config.example.php' => 'config.php',
    '.env.example' => '.env',
    'proxies.example.txt' => 'proxies.txt',
];
foreach ($copies as $example => $file) {
    $from = $root . '/' . $example;
    $to = $target . '/' . $file;
    if (!is_file($from)) {
        echo $warn("нет файла-примера $example");
        $problems++;
        continue;
    }
    if (is_file($to) && !$force) {
        echo $ok("$file уже есть, оставлен как есть (перезаписать: --force)");
        continue;
    }
    if (copy($from, $to)) {
        echo $ok("$file создан из $example");
    } else {
        echo $warn("не удалось создать $file");
        $problems++;
    }
}

// --- Прокси
if ($proxies !== []) {
    $file = $target . '/proxies.txt';
    $existing = is_file($file) ? (file($file, FILE_IGNORE_NEW_LINES) ?: []) : [];
    $added = 0;
    foreach ($proxies as $proxy) {
        if ($proxy === '' || in_array($proxy, $existing, true)) {
            continue;
        }
        $existing[] = $proxy;
        $added++;
    }
    $content = implode(PHP_EOL, $existing);
    if (file_put_contents($file, $content !== '' ? $content . PHP_EOL : '') !== false) {
        echo $ok(sprintf('в proxies.txt добавлено прокси: %d', $added));
    } else {
        echo $warn('не удалось записать proxies.txt');
        $problems++;
    }
}
$proxyLines = is_file($target . '/proxies.txt')
    ? array_filter(array_map('trim', file($target . '/proxies.txt', FILE_IGNORE_NEW_LINES) ?: []), static fn (string $l): bool => $l !== '' && !str_starts_with($l, '#'))
    : [];
echo count($proxyLines) > 0
    ? $ok(sprintf('прокси в proxies.txt: %d', count($proxyLines)))
    : $warn('в proxies.txt пока нет прокси — добавьте строки вида http://host:port:user:pass или запустите с --proxy=...');
echo PHP_EOL;

// --- Папки
echo 'Папки' . PHP_EOL;
foreach (['cache', 'out', 'debug'] as $dir) {
    $path = $target . '/' . $dir;
    if (is_dir($path) || @mkdir($path, 0777, true)) {
        echo $ok("$dir/");
    } else {
        echo $warn("не удалось создать $dir/");
        $problems++;
    }
}
echo PHP_EOL;

// --- Node.js и Playwright (только для визитов с выполнением JavaScript)
echo 'Браузер для визитов на сайты (необязательно)' . PHP_EOL;
$check = static function (array $command, int $timeoutSeconds = 30): array {
    $process = @proc_open($command, [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($process)) {
        return [127, ''];
    }
    fclose($pipes[0]);
    stream_set_blocking($pipes[1], false);
    stream_set_blocking($pipes[2], false);
    $output = '';
    $deadline = microtime(true) + $timeoutSeconds;
    while (microtime(true) < $deadline) {
        $output .= (string) stream_get_contents($pipes[1]) . (string) stream_get_contents($pipes[2]);
        $status = proc_get_status($process);
        if (!$status['running']) {
            $output .= (string) stream_get_contents($pipes[1]) . (string) stream_get_contents($pipes[2]);
            fclose($pipes[1]);
            fclose($pipes[2]);
            proc_close($process);

            return [(int) $status['exitcode'], trim($output)];
        }
        usleep(100000);
    }
    proc_terminate($process);
    fclose($pipes[1]);
    fclose($pipes[2]);
    proc_close($process);

    return [124, trim($output)];
};

[$nodeCode, $nodeVersion] = $check(['node', '--version'], 10);
if ($nodeCode !== 0) {
    echo $warn('Node.js не найден — визиты будут выполняться через curl без JavaScript (установить: https://nodejs.org)');
} else {
    echo $ok('Node.js ' . $nodeVersion);
    [$pwCode, $pwOutput] = $check(['node', $root . '/tools/render-page.js', '--check'], 60);
    $data = json_decode((string) strrchr("\n" . $pwOutput, "\n"), true);
    if ($pwCode === 0 && is_array($data) && ($data['ok'] ?? false)) {
        echo $ok(sprintf('Playwright %s, Chromium найден', $data['version'] ?? ''));
    } else {
        $reason = is_array($data) && isset($data['error']) ? (string) $data['error'] : $pwOutput;
        echo $warn('Playwright/Chromium не готовы: ' . ($reason !== '' ? $reason : 'нет ответа'));
        echo '       установка: npm install && npx playwright install chromium' . PHP_EOL;
    }
}
echo PHP_EOL;

// --- Дальнейшие шаги
$php = 'php ' . ($target === $root ? 'bin/yandex-sites.php' : $root . '/bin/yandex-sites.php');
$cfg = $target === $root ? '' : ' --config=' . $target . '/config.php';
$prx = $target === $root ? 'proxies.txt' : $target . '/proxies.txt';
echo $problems === 0 ? 'Настройка завершена.' : "Настройка завершена, но есть замечания ($problems), см. выше.";
echo PHP_EOL . PHP_EOL . 'Дальше:' . PHP_EOL;
echo "  1. Проверить прокси на живой выдаче:" . PHP_EOL;
echo "     $php --check-proxies --proxies=$prx --save-html=debug$cfg" . PHP_EOL;
echo "  2. Пробный прогон одного запроса с сохранением страниц:" . PHP_EOL;
echo "     $php --live --proxies=$prx -q \"пластиковые окна купить москва\" --pages=2 --no-cache --save-html=debug -v$cfg" . PHP_EOL;
echo "  3. Визиты на найденные сайты (робот Яндекса и браузер):" . PHP_EOL;
echo "     $php --live --proxies=$prx -q \"пластиковые окна купить москва\" --visit --variants=2 -v$cfg" . PHP_EOL;

exit($problems === 0 ? 0 : 1);

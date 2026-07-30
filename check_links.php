<?php
/**
 * check_links.php — проверка офер-ссылок «вживую».
 * Запуск на твоём сервере/компе (там, где есть доступ к доменам оферов):
 *
 *   php check_links.php                  # читает link.txt рядом со скриптом
 *   php check_links.php import_to_panel.txt
 *   php check_links.php link.txt --refka https://sitegrator.com/go/   # проверять сами рефки
 *
 * Формат входного файла — любой из наших:
 *   "имя | url"           (link.txt)
 *   "слаг | url | имя"    (import_to_panel.txt)
 *
 * Что делает: берёт уникальные URL, дергает каждый (GET, до 5 редиректов,
 * таймаут 12с), печатает HTTP-код и финальный адрес, в конце — сводку.
 * С флагом --refka вместо офер-URL проверяет рефки sitegrator.com/go/СЛАГ
 * (нужен слаг в строке — т.е. файл import_to_panel.txt).
 */

error_reporting(E_ALL & ~E_DEPRECATED);
$argvv   = $argv;
$refkaBase = null;
foreach ($argvv as $i => $a) {
    if ($a === '--refka') { $refkaBase = rtrim($argvv[$i + 1] ?? '', '/') . '/'; }
}
$file = null;
for ($i = 1; $i < count($argvv); $i++) {
    if ($argvv[$i][0] !== '-' && $argvv[$i - 1] !== '--refka') { $file = $argvv[$i]; break; }
}
$file = $file ?: (__DIR__ . '/link.txt');

if (!is_file($file)) { fwrite(STDERR, "Файл не найден: $file\n"); exit(1); }
if (!function_exists('curl_init')) { fwrite(STDERR, "Нужен php-curl\n"); exit(1); }

$lines = preg_split('/\r\n|\r|\n/', file_get_contents($file));
$targets = []; // url => [имена]
foreach ($lines as $line) {
    $line = trim($line);
    if ($line === '' || $line[0] === '#') continue;
    $p = array_map('trim', explode('|', $line));

    if ($refkaBase) {
        // ждём формат: слаг | url | имя  -> проверяем рефку
        $slug = $p[0] ?? '';
        if ($slug === '') continue;
        $url  = $refkaBase . rawurlencode($slug);
        $name = $p[2] ?? $slug;
    } else {
        // имя | url   ИЛИ   слаг | url | имя — url всегда там, где начинается http
        $url = ''; $name = $p[0] ?? '';
        foreach ($p as $part) if (preg_match('~^https?://~i', $part)) { $url = $part; break; }
        if ($url === '') continue;
        if (isset($p[2]) && $p[2] !== '') $name = $p[2];
    }
    $targets[$url][] = $name;
}

$total = count($targets);
echo "Проверяю " . $total . " " . ($refkaBase ? "рефок" : "уникальных URL") . " из " . basename($file) . "\n";
echo str_repeat('-', 60) . "\n";

$ok = 0; $warn = 0; $fail = 0; $fails = [];
$n = 0;
foreach ($targets as $url => $names) {
    $n++;
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL            => $url,
        CURLOPT_NOBODY         => false,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS      => 5,
        CURLOPT_TIMEOUT        => 12,
        CURLOPT_CONNECTTIMEOUT => 8,
        CURLOPT_SSL_VERIFYPEER => false,   // часть клоак-доменов с кривым SSL
        CURLOPT_SSL_VERIFYHOST => 0,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36',
    ]);
    $body  = curl_exec($ch);
    $code  = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $final = curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
    $err   = curl_error($ch);
    curl_close($ch);

    $cnt = count($names) > 1 ? (' x' . count($names)) : '';
    if ($err) {
        $status = 'FAIL  (' . $err . ')';
        $fail++; $fails[] = [$url, $names, $err];
    } elseif ($code >= 200 && $code < 400) {
        $status = 'OK    ' . $code;
        $ok++;
    } elseif ($code >= 400) {
        $status = 'WARN  ' . $code;
        $warn++; $fails[] = [$url, $names, 'HTTP ' . $code];
    } else {
        $status = 'FAIL  (нет ответа)';
        $fail++; $fails[] = [$url, $names, 'no response'];
    }

    printf("[%3d/%3d] %-22s %s%s\n", $n, $total, $status, $url, $cnt);
    if ($final && $final !== $url && $code >= 200 && $code < 400) {
        echo "            -> " . $final . "\n";
    }
}

echo str_repeat('-', 60) . "\n";
echo "OK: $ok   WARN(4xx): $warn   FAIL: $fail\n";
if ($fails) {
    echo "\nПроблемные:\n";
    foreach ($fails as $f) {
        echo "  " . $f[2] . "  |  " . $f[0] . "\n";
        echo "      кампании: " . implode(', ', $f[1]) . "\n";
    }
}

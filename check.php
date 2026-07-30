<?php
/**
 * check.php — временная диагностика. ОТКРОЙ В БРАУЗЕРЕ, потом УДАЛИ файл.
 * Показывает, чего не хватает для работы редиректора.
 */
header('Content-Type: text/plain; charset=utf-8');
error_reporting(E_ALL);
ini_set('display_errors', '1');

echo "PHP версия: " . PHP_VERSION . (version_compare(PHP_VERSION, '7.4', '>=') ? "  OK" : "  СТАРАЯ! нужно 7.4+") . "\n";

function chk($name, $ok, $hint = '') {
    echo str_pad($name, 28) . ($ok ? "OK" : "НЕТ  <-- " . $hint) . "\n";
}

chk('pdo',           extension_loaded('pdo'),        'включи расширение pdo');
chk('pdo_sqlite',    extension_loaded('pdo_sqlite'), 'включи pdo_sqlite в настройках PHP');
chk('curl',          extension_loaded('curl'),       'нужен для проверки ссылок и постбэка');
chk('session',       function_exists('session_start'), '');
chk('random_bytes',  function_exists('random_bytes'),  '');

$dir = __DIR__;
chk('папка на запись', is_writable($dir), "нет прав записи в $dir (нужно для stats.sqlite)");

// пробуем реально создать/открыть базу
$dbfile = $dir . '/stats.sqlite';
try {
    $pdo = new PDO('sqlite:' . $dbfile);
    $pdo->exec('CREATE TABLE IF NOT EXISTS _t(x)');
    $pdo->exec('DROP TABLE _t');
    chk('создание базы SQLite', true);
} catch (Throwable $e) {
    chk('создание базы SQLite', false, $e->getMessage());
}

echo "\nФайлы рядом:\n";
foreach (['config.php','db.php','go.php','stats.php','postback.php','.htaccess'] as $f) {
    echo '  ' . str_pad($f, 16) . (is_file($dir . '/' . $f) ? 'есть' : 'НЕТ') . "\n";
}

// если db.php есть — пробуем подключить и инициализировать
if (is_file($dir . '/db.php')) {
    echo "\nПробую загрузить db.php и инициализировать базу:\n";
    try {
        require $dir . '/db.php';
        db();
        echo "  db() — OK, база инициализирована\n";
    } catch (Throwable $e) {
        echo "  ОШИБКА: " . $e->getMessage() . "\n";
    }
}

echo "\nГотово. Удали этот файл после проверки.\n";

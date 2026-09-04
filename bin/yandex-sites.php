#!/usr/bin/env php
<?php

declare(strict_types=1);

/*
 * Точка входа CLI. Работает и без composer: если vendor/autoload.php нет,
 * подключается простой PSR-4 автозагрузчик для каталога src/.
 */

$root = dirname(__DIR__);

if (is_file($root . '/vendor/autoload.php')) {
    require $root . '/vendor/autoload.php';
} else {
    spl_autoload_register(static function (string $class) use ($root): void {
        $prefix = 'YandexSites\\';
        if (!str_starts_with($class, $prefix)) {
            return;
        }
        $file = $root . '/src/' . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
        if (is_file($file)) {
            require $file;
        }
    });
}

exit(\YandexSites\Cli\Application::main($argv));

<?php

declare(strict_types=1);

$root = dirname(__DIR__);

spl_autoload_register(static function (string $class) use ($root): void {
    foreach (['YandexSites\\' => '/src/', 'Tests\\' => '/tests/'] as $prefix => $dir) {
        if (str_starts_with($class, $prefix)) {
            $file = $root . $dir . str_replace('\\', '/', substr($class, strlen($prefix))) . '.php';
            if (is_file($file)) {
                require $file;
            }

            return;
        }
    }
});

define('TESTS_ROOT', __DIR__);
define('PROJECT_ROOT', $root);

<?php

declare(strict_types=1);

/*
 * Запуск всех тестов: php tests/run.php [фильтр по имени]
 */

require __DIR__ . '/bootstrap.php';

use Tests\AssertionFailed;
use Tests\SkipTest;

$filter = $argv[1] ?? '';
$files = glob(__DIR__ . '/*Test.php') ?: [];
sort($files);

$passed = 0;
$failed = 0;
$skipped = 0;
$failures = [];

foreach ($files as $file) {
    $class = 'Tests\\' . basename($file, '.php');
    if ($filter !== '' && stripos($class, $filter) === false) {
        continue;
    }
    if (!class_exists($class)) {
        $failed++;
        $failures[] = "$class: класс не найден в $file";
        continue;
    }
    echo basename($file, '.php') . PHP_EOL;
    $object = new $class();
    foreach (get_class_methods($object) as $method) {
        if (!str_starts_with($method, 'test')) {
            continue;
        }
        try {
            $object->$method();
            $passed++;
            echo "  ✓ $method" . PHP_EOL;
        } catch (SkipTest $e) {
            $skipped++;
            echo "  - $method (пропущен: {$e->getMessage()})" . PHP_EOL;
        } catch (AssertionFailed $e) {
            $failed++;
            $failures[] = "$class::$method: " . $e->getMessage();
            echo "  ✗ $method — " . $e->getMessage() . PHP_EOL;
        } catch (\Throwable $e) {
            $failed++;
            $failures[] = sprintf('%s::%s: %s: %s (%s:%d)', $class, $method, $e::class, $e->getMessage(), basename($e->getFile()), $e->getLine());
            echo "  ✗ $method — " . $e::class . ': ' . $e->getMessage() . PHP_EOL;
        }
    }
    if (method_exists($object, 'tearDownClass')) {
        $object->tearDownClass();
    }
}

echo PHP_EOL . sprintf('Пройдено: %d, провалено: %d, пропущено: %d', $passed, $failed, $skipped) . PHP_EOL;
foreach ($failures as $failure) {
    echo '  - ' . $failure . PHP_EOL;
}
exit($failed > 0 ? 1 : 0);

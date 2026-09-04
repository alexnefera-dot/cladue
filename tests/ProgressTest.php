<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\Progress;

final class ProgressTest
{
    public function testWritesAndMergesState(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-progress-' . uniqid() . '.json';
        $progress = new Progress($file, ['state' => 'starting', 'run' => 0]);
        Assert::true(is_file($file), 'файл состояния создан сразу');
        $first = json_decode((string) file_get_contents($file), true);
        Assert::same('starting', $first['state']);
        Assert::same(0, $first['run']);
        Assert::true(isset($first['updated_at']));

        $progress->update(['state' => 'running', 'run' => 1], true);
        $data = json_decode((string) file_get_contents($file), true);
        Assert::same('running', $data['state']);
        Assert::same(1, $data['run']);

        $progress->update(['queries_done' => 5]);
        $progress->update(['sites_total' => 12], true);
        $data = json_decode((string) file_get_contents($file), true);
        Assert::same(5, $data['queries_done'], 'непринудительное обновление всё равно попадает в файл при следующем принудительном');
        Assert::same(12, $data['sites_total']);
        Assert::same(1, $data['run'], 'прежние поля сохраняются');

        Assert::same(12, $progress->snapshot()['sites_total']);
        unlink($file);
    }
}

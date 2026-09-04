<?php

declare(strict_types=1);

namespace Tests;

/**
 * bin/setup.php: создание файлов настроек и папок в отдельной директории.
 */
final class SetupTest
{
    /**
     * @param list<string> $args
     * @return array{code: int, out: string}
     */
    private function run(array $args): array
    {
        $process = proc_open(
            array_merge([PHP_BINARY, PROJECT_ROOT . '/bin/setup.php'], $args),
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
        );
        fclose($pipes[0]);
        $out = (string) stream_get_contents($pipes[1]) . (string) stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        return ['code' => proc_close($process), 'out' => $out];
    }

    public function testCreatesFilesAndFolders(): void
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-setup-' . uniqid();

        $run = $this->run(['--dir=' . $dir, '--proxy=http://203.0.113.10:59100:login:password', '--proxy=http://203.0.113.10:59100:login:password']);
        Assert::same(0, $run['code'], $run['out']);
        Assert::contains('config.php создан', $run['out']);
        Assert::contains('.env создан', $run['out']);
        Assert::contains('proxies.txt создан', $run['out']);
        Assert::contains('добавлено прокси: 1', $run['out'], 'дубль прокси не добавляется');
        Assert::contains('прокси в proxies.txt: 1', $run['out']);
        Assert::contains('--check-proxies', $run['out']);
        foreach (['config.php', '.env', 'proxies.txt', 'cache', 'out', 'debug'] as $item) {
            Assert::true(file_exists($dir . '/' . $item), "нет $item");
        }
        Assert::contains("\nhttp://203.0.113.10:59100:login:password\n", (string) file_get_contents($dir . '/proxies.txt'));
        Assert::true(is_array(require $dir . '/config.php'), 'config.php — корректный PHP-массив');

        file_put_contents($dir . '/config.php', '<?php return ["search" => ["region" => 2]];');
        $again = $this->run(['--dir=' . $dir, '--proxy=http://203.0.113.11:59100:login:password']);
        Assert::same(0, $again['code'], $again['out']);
        Assert::contains('config.php уже есть', $again['out']);
        Assert::same(2, (require $dir . '/config.php')['search']['region'], 'без --force файл не перезаписывается');
        Assert::contains('прокси в proxies.txt: 2', $again['out']);

        $forced = $this->run(['--dir=' . $dir, '--force']);
        Assert::same(0, $forced['code'], $forced['out']);
        Assert::contains('config.php создан', $forced['out']);

        Assert::same(2, $this->run(['--dir=' . $dir, '--bogus'])['code']);

        $iterator = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($iterator as $item) {
            $item->isDir() ? rmdir($item->getPathname()) : unlink($item->getPathname());
        }
        rmdir($dir);
    }
}

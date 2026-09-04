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

    public function testUpdateFromLocalZip(): void
    {
        if (!class_exists(\ZipArchive::class)) {
            Assert::skip('нет расширения zip');
        }
        $dir = sys_get_temp_dir() . '/yandex-sites-update-target-' . uniqid();
        mkdir($dir);
        mkdir($dir . '/src/Cli', 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["search" => ["region" => 2]];');
        file_put_contents($dir . '/proxies.txt', "http://203.0.113.10:59100:login:password\n");
        file_put_contents($dir . '/src/Cli/Application.php', "<?php // старая версия VERSION = '0.0.1';");

        $zipPath = sys_get_temp_dir() . '/yandex-sites-update-' . uniqid() . '.zip';
        $zip = new \ZipArchive();
        $zip->open($zipPath, \ZipArchive::CREATE);
        $zip->addFromString('cladue-branch/bin/yandex-sites.php', (string) file_get_contents(PROJECT_ROOT . '/bin/yandex-sites.php'));
        $zip->addFromString('cladue-branch/src/Cli/Application.php', "<?php // VERSION = '9.9.9';");
        $zip->addFromString('cladue-branch/config.php', '<?php return ["must" => "not overwrite"];');
        $zip->addFromString('cladue-branch/proxies.txt', 'must-not-overwrite');
        $zip->addFromString('cladue-branch/tools/render-page.js', '// renderer');
        $zip->close();

        $run = $this->run(['--dir=' . $dir, '--update=' . $zipPath]);
        Assert::same(0, $run['code'], $run['out']);
        Assert::contains('Обновлено файлов: 3, версия yandex-sites 9.9.9', $run['out']);
        Assert::same("<?php // VERSION = '9.9.9';", (string) file_get_contents($dir . '/src/Cli/Application.php'));
        Assert::true(is_file($dir . '/tools/render-page.js'));
        Assert::same(2, (require $dir . '/config.php')['search']['region'], 'config.php не перезаписывается');
        Assert::contains('203.0.113.10', (string) file_get_contents($dir . '/proxies.txt'), 'proxies.txt не перезаписывается');

        $bad = $this->run(['--dir=' . $dir, '--update=' . $dir . '/config.php']);
        Assert::same(1, $bad['code']);

        unlink($zipPath);
        $iterator = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($iterator as $item) {
            $item->isDir() ? rmdir($item->getPathname()) : unlink($item->getPathname());
        }
        rmdir($dir);
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

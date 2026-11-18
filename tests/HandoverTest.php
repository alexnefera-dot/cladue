<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\Archive;

final class HandoverTest
{
    public function testPackageCarriesCodeWithoutGitAndWithoutAuthorship(): void
    {
        if (!class_exists('ZipArchive')) {
            Assert::skip('нет расширения zip');
        }
        $dir = sys_get_temp_dir() . '/yandex-sites-handover-' . uniqid();
        $stage = $dir . '/pkg';
        $zipFile = $dir . '/handover.zip';
        $out = [];
        $code = 1;
        exec(sprintf(
            '%s %s --dir=%s --out=%s 2>&1',
            escapeshellarg(PHP_BINARY),
            escapeshellarg(PROJECT_ROOT . '/bin/handover.php'),
            escapeshellarg($stage),
            escapeshellarg($zipFile),
        ), $out, $code);
        $log = implode("\n", $out);
        Assert::same(0, $code, 'сборка прошла: ' . $log);
        Assert::true(Archive::isZip($zipFile), 'на выходе zip');
        $zip = new \ZipArchive();
        Assert::true($zip->open($zipFile) === true);
        Assert::same('yandex-sites/', substr((string) $zip->getNameIndex(0), 0, 13), 'внутри архива одна папка проекта');
        $zip->close();

        $files = Archive::listFiles($stage);
        $names = array_keys($files);
        Assert::true(in_array('DOCS.md', $names, true), 'справочник переехал под нейтральным именем');
        Assert::false(in_array('CLAUDE.md', $names, true), 'прежнего имени в пакете нет');
        Assert::true(in_array('HANDOVER.md', $names, true), 'записка исполнителю на месте');
        Assert::true(in_array('src/Runner.php', $names, true), 'код внутри');
        Assert::true(in_array('tests/run.php', $names, true), 'тесты внутри — ими проверяют сборку');
        Assert::false(in_array('bin/handover.php', $names, true), 'сам сборщик в пакет не идёт');

        // Ни данных, ни ключей, ни истории git — пакет можно показывать кому угодно.
        foreach (['.git', 'runs', 'cache', 'out', 'config.php', '.env', 'proxies.txt', 'queries.txt'] as $forbidden) {
            $found = array_filter($names, static fn (string $n): bool => $n === $forbidden || str_starts_with($n, $forbidden . '/'));
            Assert::same([], array_values($found), $forbidden . ' в пакете быть не должно');
        }

        // Главная проверка: ни одного упоминания авторства и аккаунта в текстовых файлах.
        $words = ['claude', 'клауд', 'anthropic', 'alexnefera'];
        $hits = [];
        foreach ($files as $rel => $abs) {
            if (!in_array(strtolower(pathinfo($rel, PATHINFO_EXTENSION)), ['php', 'md', 'html', 'js', 'json', 'txt'], true)) {
                continue;
            }
            $body = mb_strtolower((string) file_get_contents($abs));
            foreach ($words as $word) {
                if (str_contains($body, $word)) {
                    $hits[] = $rel . ' — ' . $word;
                }
            }
        }
        Assert::same([], $hits, 'в пакете не осталось упоминаний');

        // Автообновление выключено (оно тянуло бы ветку из чужого репозитория) и говорит об этом вслух.
        Assert::contains("const UPDATE_URL = '';", (string) file_get_contents($stage . '/bin/setup.php'));
        $out = [];
        exec(sprintf('%s %s --update 2>&1', escapeshellarg(PHP_BINARY), escapeshellarg($stage . '/bin/setup.php')), $out, $code);
        Assert::same(2, $code, 'обновление без адреса — честный отказ');
        Assert::contains('не настроено', implode("\n", $out));

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }
}

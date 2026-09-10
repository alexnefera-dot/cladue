<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\Archive;

final class ArchiveTest
{
    public function testZipDirPacksFolderWithRelativePaths(): void
    {
        // Архив контента: внутри папки N-стр/сайт/страница.html — ровно как на диске, без лишнего верхнего уровня.
        $dir = sys_get_temp_dir() . '/yandex-sites-archive-' . uniqid();
        mkdir("$dir/content/7-стр/a.ru", 0777, true);
        mkdir("$dir/content/12-стр/b.ru", 0777, true);
        file_put_contents("$dir/content/7-стр/a.ru/main.html", '<p>a</p>');
        file_put_contents("$dir/content/7-стр/a.ru/vhod.html", '<p>v</p>');
        file_put_contents("$dir/content/12-стр/b.ru/main.html", '<p>b</p>');
        Assert::same(['12-стр/b.ru/main.html', '7-стр/a.ru/main.html', '7-стр/a.ru/vhod.html'], array_keys(Archive::listFiles("$dir/content")));
        Assert::same([], Archive::listFiles("$dir/nope"), 'нет папки — нет файлов');

        $threw = false;
        try {
            Archive::zipDir("$dir/empty", "$dir/empty.zip");
        } catch (\RuntimeException $e) {
            $threw = true;
        }
        Assert::true($threw, 'пустая папка — ошибка, а не пустой архив');

        if (!class_exists('ZipArchive')) {
            Assert::skip('нет расширения zip');
        }
        Assert::same(3, Archive::zipDir("$dir/content", "$dir/content.zip"));
        Assert::true(Archive::isZip("$dir/content.zip"));
        $zip = new \ZipArchive();
        Assert::true($zip->open("$dir/content.zip") === true);
        $names = [];
        for ($i = 0; $i < $zip->numFiles; $i++) {
            $names[] = $zip->getNameIndex($i);
        }
        sort($names);
        Assert::same(['12-стр/b.ru/main.html', '7-стр/a.ru/main.html', '7-стр/a.ru/vhod.html'], $names, 'пути в архиве — относительно папки content');
        Assert::same('<p>v</p>', $zip->getFromName('7-стр/a.ru/vhod.html'));
        $zip->close();
        // Повторный вызов перезаписывает архив, а не дописывает его.
        unlink("$dir/content/7-стр/a.ru/vhod.html");
        Assert::same(2, Archive::zipDir("$dir/content", "$dir/content.zip"));
        $zip = new \ZipArchive();
        $zip->open("$dir/content.zip");
        Assert::same(2, $zip->numFiles, 'старый архив перезаписан');
        $zip->close();
    }

    public function testTarFallbackOnlyWhenSystemTarWritesZip(): void
    {
        // Без расширения zip архив собирает системный tar: bsdtar (Windows/macOS) умеет zip, GNU tar — нет,
        // и тогда должна быть понятная ошибка, а не битый файл.
        $dir = sys_get_temp_dir() . '/yandex-sites-archive-tar-' . uniqid();
        mkdir("$dir/content/1-стр/c.ru", 0777, true);
        file_put_contents("$dir/content/1-стр/c.ru/main.html", '<p>c</p>');
        $version = (string) @shell_exec('tar --version 2>&1');
        $bsd = stripos($version, 'bsdtar') !== false;
        try {
            $n = Archive::zipDir("$dir/content", "$dir/content.zip", true);
            Assert::true($bsd, 'zip через tar получился — значит это bsdtar');
            Assert::same(1, $n);
            Assert::true(Archive::isZip("$dir/content.zip"));
        } catch (\RuntimeException $e) {
            Assert::false($bsd, 'bsdtar должен уметь zip: ' . $e->getMessage());
            Assert::contains('extension=zip', $e->getMessage(), 'подсказка, как включить zip в PHP');
            Assert::false(is_file("$dir/content.zip"), 'битого файла не остаётся');
        }
    }
}

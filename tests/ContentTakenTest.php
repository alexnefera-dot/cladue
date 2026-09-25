<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\ContentTaken;

final class ContentTakenTest
{
    /** @var list<string> */
    private array $dirs = [];

    /** Отдельная папка прогона на каждый тест: отметки и контент не должны перетекать между ними. */
    private function dir(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-taken-' . uniqid();
        mkdir($dir . '/content', 0777, true);
        $this->dirs[] = $dir;

        return $dir;
    }

    private function write(string $run, string $rel, string $html): void
    {
        $file = $run . '/content/' . $rel;
        @mkdir(dirname($file), 0777, true);
        file_put_contents($file, $html);
    }

    public function testNewFilesShrinkAfterEachWave(): void
    {
        // Выгрузка идёт волнами: после первой забрали часть, после второй архив должен приехать
        // БЕЗ первой части — «в новый архив вторую волну добавляй уже без первой».
        $run = $this->dir();
        $content = $run . '/content';
        $this->write($run, '7-стр/a.ru/main.html', '<h2>a</h2>');
        $this->write($run, '7-стр/a.ru/vhod.html', '<p>v</p>');

        $first = ContentTaken::newFiles($run, $content);
        Assert::same(2, count($first), 'до первого архива новое — это весь контент');
        Assert::same(['files' => 2, 'sites' => 1], ContentTaken::stats($first));
        Assert::same(1, ContentTaken::markTaken($run, $first), 'первая волна');
        Assert::same(0, count(ContentTaken::newFiles($run, $content)), 'забранное больше не новое');

        // Вторая волна выгрузки: появился ещё один сайт.
        $this->write($run, '12-стр/b.ru/main.html', '<h2>b</h2>');
        $second = ContentTaken::newFiles($run, $content);
        Assert::same(['12-стр/b.ru/main.html'], array_keys($second), 'в новом архиве только вторая волна');
        Assert::same(2, ContentTaken::markTaken($run, $second), 'номер волны растёт — им называется файл архива');
        Assert::same(0, count(ContentTaken::newFiles($run, $content)));
    }

    public function testRecleaningSameTextIsNotNewButChangedTextIs(): void
    {
        // «Очистить всё» перечищает страницы заново: время файлов меняется у всех, а текст статьи —
        // тот же. Считаем по содержимому, иначе весь архив снова уехал бы как новый.
        $run = $this->dir();
        $content = $run . '/content';
        $this->write($run, '7-стр/a.ru/main.html', '<h2>a</h2>');
        ContentTaken::markAll($run, $content);
        Assert::same(0, count(ContentTaken::newFiles($run, $content)));

        touch($content . '/7-стр/a.ru/main.html', time() + 60);
        Assert::same(0, count(ContentTaken::newFiles($run, $content)), 'то же содержимое — не новое');

        $this->write($run, '7-стр/a.ru/main.html', '<h2>a</h2><p>дописали</p>');
        Assert::same(['7-стр/a.ru/main.html'], array_keys(ContentTaken::newFiles($run, $content)), 'текст изменился — статья снова новая');
    }

    public function testResetMakesEverythingNewAgain(): void
    {
        $run = $this->dir();
        $content = $run . '/content';
        $this->write($run, '7-стр/a.ru/main.html', '<h2>a</h2>');
        ContentTaken::markAll($run, $content);
        Assert::same(0, count(ContentTaken::newFiles($run, $content)));

        ContentTaken::reset($run);
        Assert::same(1, count(ContentTaken::newFiles($run, $content)), 'отметки забыты — контент снова новый');
        Assert::same(0, ContentTaken::load($run)['wave'], 'счётчик волн тоже сброшен');
    }

    public function tearDownClass(): void
    {
        foreach ($this->dirs as $dir) {
            if (!is_dir($dir)) {
                continue;
            }
            $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
            foreach ($it as $item) {
                $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
            }
            @rmdir($dir);
        }
    }
}

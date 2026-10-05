<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Content\SiteCleaner;

/**
 * Очистка одного сайта: раскладка по бакету и — главное — СОХРАНЕНИЕ НАБОРА СТРАНИЦ шаблона.
 */
final class SiteCleanerTest
{
    /** @var list<string> */
    private array $dirs = [];

    private function dir(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-sitecleaner-' . uniqid();
        mkdir($dir, 0777, true);
        $this->dirs[] = $dir;

        return $dir;
    }

    private function page(string $title, string $text): string
    {
        return '<html><body><header><nav><a href="/">Логотип Бренд</a></nav></header>'
            . '<main><h1>' . $title . '</h1><div class="content">' . $text . '</div></main>'
            . '<footer class="site-footer">подвал, реквизиты</footer></body></html>';
    }

    public function testKeepsEveryDownloadedPageInTheSet(): void
    {
        // Шаблонов у нас два, и набор страниц у них фиксирован. Страница с короткой статьёй (вход,
        // зеркало — там два предложения) раньше ВЫПАДАЛА из контента: сайт «3 стр.» давал 2 статьи,
        // бакет назывался иначе, а ссылки из статей вели на страницы, которых в выгрузке нет.
        $dir = $this->dir();
        $pages = $dir . '/pages/3-стр/kush.brandnet.ru';
        mkdir($pages, 0777, true);
        $long = str_repeat('<p>Длинный абзац статьи про бренд и его бонусы для новых игроков.</p>', 8);
        file_put_contents($pages . '/main.html', $this->page('Бренд — обзор', $long));
        file_put_contents($pages . '/vhod.html', '<html><body><header><nav><a href="/">Логотип</a></nav></header>'
            . '<div class="content"><p>Вход в личный кабинет по логину и паролю.</p></div>'
            . '<footer>подвал</footer></body></html>');
        file_put_contents($pages . '/zerkalo.html', '<html><body><div class="content"><p>Рабочее зеркало сайта.</p></div></body></html>');

        $files = [$pages . '/main.html', $pages . '/vhod.html', $pages . '/zerkalo.html'];
        $r = SiteCleaner::cleanHost($dir, 'kush.brandnet.ru', $files);

        Assert::same(3, $r['written'], 'все три страницы остались в наборе');
        Assert::same(0, $r['skipped'], 'ничего не выброшено');
        Assert::same(2, $r['short'], 'две страницы оставлены по короткой статье');
        Assert::same(['vhod.html', 'zerkalo.html'], $r['short_files'], 'и названы по именам');
        Assert::same('content/3-стр/kush.brandnet.ru', $r['dir'], 'бакет совпадает с числом страниц выгрузки');

        foreach (['main.html', 'vhod.html', 'zerkalo.html'] as $name) {
            Assert::true(is_file($dir . '/' . $r['dir'] . '/' . $name), "страница $name записана");
        }
        $vhod = (string) file_get_contents($dir . '/' . $r['dir'] . '/vhod.html');
        Assert::contains('Вход в личный кабинет', $vhod, 'текст короткой страницы сохранён');
        Assert::false(str_contains($vhod, 'Логотип'), 'шапка срезана и у короткой страницы');
        Assert::false(str_contains($vhod, 'подвал'), 'подвал срезан');
    }

    public function testTrulyEmptyPageIsTheOnlyOneDropped(): void
    {
        // Оставлять нечего только если на странице нет текста вовсе (битый файл, заглушка из каркаса).
        $dir = $this->dir();
        $pages = $dir . '/pages/2-стр/empty.ru';
        mkdir($pages, 0777, true);
        $long = str_repeat('<p>Длинный абзац статьи про бренд и его бонусы для новых игроков.</p>', 8);
        file_put_contents($pages . '/main.html', $this->page('Обзор', $long));
        file_put_contents($pages . '/broken.html', '<html><body><header>шапка</header><footer>подвал</footer></body></html>');

        $r = SiteCleaner::cleanHost($dir, 'empty.ru', [$pages . '/main.html', $pages . '/broken.html']);
        Assert::same(1, $r['written']);
        Assert::same(1, $r['skipped']);
        Assert::same(['broken.html'], $r['skipped_files'], 'пустая страница названа');
        Assert::same(0, $r['short']);
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

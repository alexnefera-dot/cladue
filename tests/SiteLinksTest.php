<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Visit\SiteLinks;

final class SiteLinksTest
{
    private function page(): string
    {
        return <<<'HTML'
        <!doctype html><html><head><title>Окна</title></head>
        <body>
        <header class="site-header">
          <a href="/">Главная</a>
          <nav class="main-menu">
            <a href="https://okna-moskva.ru/about/">О компании</a>
            <a href="/contacts">Контакты</a>
            <a href="catalog/plastikovye/">Каталог</a>
            <a href="/contacts">Контакты (дубль)</a>
            <a href="/about/#team">О компании — якорь</a>
            <a href="https://www.okna-moskva.ru/prices">Цены</a>
            <a href="https://shop.okna-moskva.ru/">Магазин (поддомен)</a>
            <a href="https://vk.com/oknamoskva">ВКонтакте</a>
            <a href="mailto:info@okna-moskva.ru">Почта</a>
            <a href="tel:+74951234567">Телефон</a>
            <a href="#top">Наверх</a>
            <a href="javascript:void(0)">Меню</a>
          </nav>
        </header>
        <main>
          <a href="/blog/post-1">Статья (не в шапке)</a>
          <a href="https://okna-moskva.ru/deep/page">Глубокая (не в шапке)</a>
        </main>
        </body></html>
        HTML;
    }

    public function testCollectsOnlySameSiteHeaderLinks(): void
    {
        $links = SiteLinks::fromHeader($this->page(), 'https://okna-moskva.ru/', 'okna-moskva.ru');

        // ожидаем только внутренние страницы из шапки, по одному разу, без главной
        Assert::inArray('https://okna-moskva.ru/about/', $links);
        Assert::inArray('https://okna-moskva.ru/contacts', $links);
        Assert::inArray('https://okna-moskva.ru/catalog/plastikovye/', $links, 'относительная ссылка стала абсолютной');
        Assert::inArray('https://www.okna-moskva.ru/prices', $links, 'www — тот же хост');

        // внешние и нестраничные — не берём
        Assert::notInArray('https://shop.okna-moskva.ru/', $links, 'другой поддомен (другой бренд) не обходим');
        Assert::notInArray('https://vk.com/oknamoskva', $links);
        foreach ($links as $url) {
            Assert::false(str_contains($url, 'vk.com'), 'внешний домен исключён');
            Assert::false(str_starts_with($url, 'mailto:'), 'mailto исключён');
            Assert::false(str_starts_with($url, 'tel:'), 'tel исключён');
            Assert::false(str_contains($url, '#'), 'якорь отброшен');
            Assert::false(str_contains($url, 'javascript'), 'javascript исключён');
        }

        // главная не включается, дублей нет
        Assert::notInArray('https://okna-moskva.ru/', $links);
        Assert::notInArray('https://okna-moskva.ru', $links);
        Assert::same(count($links), count(array_unique($links)), 'без дублей');
        Assert::same(1, count(array_filter($links, static fn ($u) => str_contains($u, '/contacts'))), '/contacts один раз, якорь тоже дубль about');

        // ссылки вне шапки (main) — не в результате
        Assert::notInArray('https://okna-moskva.ru/blog/post-1', $links);
    }

    public function testCanonicalFoldsAliases(): void
    {
        // / , /index.php , /index.html , www — одна и та же главная (не качаем дважды)
        $home = SiteLinks::canonical('https://a.ru/');
        Assert::same($home, SiteLinks::canonical('https://a.ru/index.php'));
        Assert::same($home, SiteLinks::canonical('http://www.a.ru/index.html'));
        Assert::same($home, SiteLinks::canonical('https://a.ru/#top'));
        // /about и /about/ — одно; запрос различает страницы
        Assert::same(SiteLinks::canonical('https://a.ru/about'), SiteLinks::canonical('https://a.ru/about/'));
        Assert::true(SiteLinks::canonical('https://a.ru/catalog') !== SiteLinks::canonical('https://a.ru/catalog?p=2'));
    }

    public function testExcludesHomeAliasFromMenu(): void
    {
        // Ссылка на /index.php в меню — это тоже главная, её не берём как отдельную страницу
        $html = '<header><nav><a href="/">Главная</a><a href="/index.php">Главная (алиас)</a><a href="/about">О нас</a></nav></header>';
        $links = SiteLinks::fromHeader($html, 'https://site.ru/', 'site.ru');
        Assert::inArray('https://site.ru/about', $links);
        Assert::notInArray('https://site.ru/index.php', $links, 'алиас главной исключён');
        Assert::same(1, count($links), 'осталась только реальная внутренняя страница');
    }

    public function testSkipsSitemapAndFileResources(): void
    {
        // Карту сайта (htmlmap/sitemap) и файлы-ресурсы не обходим.
        $html = '<header><nav>'
            . '<a href="/htmlmap">HTML-карта</a>'
            . '<a href="/sitemap-all.xml">Sitemap</a>'
            . '<a href="/karta-sajta">Карта сайта</a>'
            . '<a href="/price.pdf">Прайс</a>'
            . '<a href="/catalog">Каталог</a>'
            . '</nav></header>';
        $links = SiteLinks::fromHeader($html, 'https://site.ru/', 'site.ru');
        Assert::inArray('https://site.ru/catalog', $links, 'обычная страница берётся');
        Assert::notInArray('https://site.ru/htmlmap', $links, 'htmlmap не качаем');
        $joined = implode(' ', $links);
        Assert::false(str_contains($joined, 'sitemap'), 'sitemap не качаем');
        Assert::false(str_contains($joined, 'karta-sajta'), 'карта сайта не качаем');
        Assert::false(str_contains($joined, '.pdf'), 'файлы не качаем');
        Assert::same(1, count($links), 'осталась только реальная страница');
    }

    public function testResolveRelativeAndBadSchemes(): void
    {
        Assert::same('https://a.ru/x/y', SiteLinks::resolve('https://a.ru/x/', 'y'));
        Assert::same('https://a.ru/y', SiteLinks::resolve('https://a.ru/x/', '/y'));
        Assert::same('https://a.ru/z', SiteLinks::resolve('https://a.ru/x/page', '../z'));
        Assert::same('http://a.ru/page', SiteLinks::resolve('http://a.ru/', '//a.ru/page'), '//host наследует схему базы');
        Assert::same('https://a.ru/p', SiteLinks::resolve('https://a.ru/x', 'https://a.ru/p#frag'), 'якорь отброшен');
        Assert::null(SiteLinks::resolve('https://a.ru/', 'mailto:x@a.ru'));
        Assert::null(SiteLinks::resolve('https://a.ru/', '#top'));
        Assert::null(SiteLinks::resolve('https://a.ru/', ''));
    }

    public function testResolveCollapsesLangLoop(): void
    {
        // Подряд идущие одинаковые сегменты схлопываются: реальная страница за циклом сохраняется.
        Assert::same('https://a.ru/RU-ru/app', SiteLinks::resolve('https://a.ru/', '/RU-ru/RU-ru/RU-ru/app'));
        Assert::same('https://a.ru/zerkalo/ru/', SiteLinks::resolve('https://a.ru/', '/zerkalo/ru/ru/ru/ru/'));
        // варианты цикла разной длины сводятся к одному ключу
        Assert::same(SiteLinks::canonical('https://a.ru/x/x/x/app'), SiteLinks::canonical('https://a.ru/x/x/app'));
    }

    public function testCanonicalStripsLocalePrefix(): void
    {
        $home = SiteLinks::canonical('https://a.ru/');
        // /promo и /RU-ru/promo (языковой префикс) — одна и та же страница (без promo-2).
        Assert::same(SiteLinks::canonical('https://a.ru/promo'), SiteLinks::canonical('https://a.ru/RU-ru/promo'));
        Assert::same(SiteLinks::canonical('https://a.ru/bonus'), SiteLinks::canonical('https://a.ru/ru/bonus'));
        Assert::same(SiteLinks::canonical('https://a.ru/app'), SiteLinks::canonical('https://a.ru/en-us/app'));
        // Путь целиком из языкового кода — та же главная (без дубля main): /ru, /ru-ru, /RU-ru, /en → корень.
        Assert::same($home, SiteLinks::canonical('https://a.ru/ru'));
        Assert::same($home, SiteLinks::canonical('https://a.ru/ru-ru'));
        Assert::same($home, SiteLinks::canonical('https://a.ru/RU-ru'));
        Assert::same($home, SiteLinks::canonical('https://a.ru/en'));
        // Двухбуквенный сегмент не из списка языков — обычная страница, не сворачиваем.
        Assert::true(SiteLinks::canonical('https://a.ru/vk') !== $home);
    }

    public function testCollectsFooterMenuLinks(): void
    {
        // Меню в подвале тоже собирается.
        $html = '<body><h1>Главная</h1><footer><div class="footer-menu"><nav>'
            . '<a href="/app">Приложение</a><a href="/bonus">Бонус</a>'
            . '<a href="https://vk.com/x">VK</a></nav></div></footer></body>';
        $links = SiteLinks::fromHeader($html, 'https://site.ru/', 'site.ru');
        Assert::inArray('https://site.ru/app', $links, 'ссылка из подвала собрана');
        Assert::inArray('https://site.ru/bonus', $links);
        Assert::notInArray('https://vk.com/x', $links, 'внешняя из подвала — нет');
    }

    public function testSameHostForRedirects(): void
    {
        // Проверка редиректов строгая по поддомену: соседний поддомен — уже другой сайт.
        Assert::true(SiteLinks::sameHost('https://hype.o5h7.lol/', 'https://hype.o5h7.lol/bonus'));
        Assert::true(SiteLinks::sameHost('https://okna-moskva.ru/', 'https://www.okna-moskva.ru/page'), 'www — тот же хост');
        Assert::false(SiteLinks::sameHost('https://hype.o5h7.lol/', 'https://max.o5h7.lol/'), 'другой поддомен — другой бренд');
        Assert::false(SiteLinks::sameHost('https://hype.o5h7.lol/', 'https://o5h7.lol/'), 'апекс — другой хост');
        Assert::false(SiteLinks::sameHost('https://okna-moskva.ru/', 'https://other-site.ru/'), 'другой домен');
        Assert::false(SiteLinks::sameHost('https://okna-moskva.ru/', 'not a url'));
    }

    public function testLimitAndNoHeaderFallback(): void
    {
        $links = SiteLinks::fromHeader($this->page(), 'https://okna-moskva.ru/', 'okna-moskva.ru', 2);
        Assert::same(2, count($links), 'лимит соблюдается');

        // страница без header/nav — берём ссылки из элементов с классом меню
        $html = '<html><body><div class="b-menu"><a href="/a">A</a><a href="https://ext.ru/x">ext</a></div><a href="/loose">loose</a></body></html>';
        $links = SiteLinks::fromHeader($html, 'https://site.ru/', 'site.ru');
        Assert::inArray('https://site.ru/a', $links);
        Assert::notInArray('https://ext.ru/x', $links);
        Assert::notInArray('https://site.ru/loose', $links, 'ссылка вне меню не берётся при fallback');
    }
}

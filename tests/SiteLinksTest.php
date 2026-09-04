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
        Assert::inArray('https://www.okna-moskva.ru/prices', $links, 'www — тот же сайт');
        Assert::inArray('https://shop.okna-moskva.ru/', $links, 'поддомен — тот же регистрируемый домен');

        // внешние и нестраничные — не берём
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

    public function testSameSiteCheckForRedirects(): void
    {
        Assert::true(SiteLinks::sameSite('okna-moskva.ru', 'https://okna-moskva.ru/page'));
        Assert::true(SiteLinks::sameSite('okna-moskva.ru', 'https://www.okna-moskva.ru/page'));
        Assert::true(SiteLinks::sameSite('okna-moskva.ru', 'https://shop.okna-moskva.ru/'));
        Assert::false(SiteLinks::sameSite('okna-moskva.ru', 'https://other-site.ru/'), 'редирект на другой сайт');
        Assert::false(SiteLinks::sameSite('okna-moskva.ru', 'not a url'));
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

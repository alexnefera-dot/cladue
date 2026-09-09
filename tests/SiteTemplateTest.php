<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\Site;
use YandexSites\Visit\SiteTemplate;

final class SiteTemplateTest
{
    public function testGuessRecognisesBothFamiliesByMarkup(): void
    {
        // Семейство «7–9 страниц»: панель фильтров, вступление, облако тегов, «Круглосуточно», «О компании».
        $seven = '<header><div class="phone">+7 (495) 111-22-33</div><span>Круглосуточно · 24/7</span><nav class="main-nav"></nav></header>'
            . '<div class="filters-section">Все игры</div><div class="promo-text"><p>Вступление</p></div><h1>Бренд</h1>'
            . '<div class="entry-content"><p>Статья</p></div><div class="tags-cloud"></div><footer class="company-info"></footer>';
        Assert::same(SiteTemplate::PAGES7, SiteTemplate::guess($seven));

        // Семейство «12–15 страниц»: попап бонуса, «выигрыши», хлебные крошки, «Куда перейти», чат.
        $twelve = '<a class="skip-link" href="#main-content">К содержимому</a><nav id="mobileNav"></nav><div class="breadcrumbs">🏠 Главная</div>'
            . '<main><div class="quicklink-item">Куда перейти</div><div class="keywords-block"><span class="keyword-pill">x</span></div></main>'
            . '<div id="winNotifications"></div><div id="bonusPopup"></div><div id="supportWidget"></div><footer class="site-footer"></footer>';
        Assert::same(SiteTemplate::PAGES12, SiteTemplate::guess($twelve));

        // Обфусцированный вариант 12–15: классы случайные (pg-xxxxx), но служебные id на месте.
        $obfuscated = '<div class="pg-navopu pulse-glow"></div><section id="jackpots"></section><section id="levels"></section><div id="reserved-aux"></div>';
        Assert::same(SiteTemplate::PAGES12, SiteTemplate::guess($obfuscated), 'узнаём по id секций');
    }

    public function testGuessDoesNotMistakeOrdinarySiteForTemplate(): void
    {
        // Типовые имена WordPress (skip-link, site-footer, breadcrumbs, entry-content) без сильных признаков — не шаблон.
        $wordpress = '<a class="skip-link">Skip</a><div class="breadcrumbs"></div><article><div class="entry-content"><p>Пост</p></div></article><footer class="site-footer"></footer>';
        Assert::same(SiteTemplate::OTHER, SiteTemplate::guess($wordpress), 'слабых признаков без сильного недостаточно');
        // Один сильный признак сам по себе (например, «Круглосуточно» у обычной клиники) — тоже не шаблон.
        Assert::same(SiteTemplate::OTHER, SiteTemplate::guess('<p>Работаем Круглосуточно</p><nav class="main-nav"></nav>'));
        Assert::same(SiteTemplate::OTHER, SiteTemplate::guess(''));
        Assert::same(SiteTemplate::OTHER, SiteTemplate::guess('<html><body><h1>Пластиковые окна</h1><p>Цены</p></body></html>'));

        $scores = SiteTemplate::scores('<div class="tags-cloud"></div><div class="promo-text"></div>');
        Assert::same(4, $scores[SiteTemplate::PAGES7]['score']);
        Assert::same(['tags-cloud', 'promo-text'], $scores[SiteTemplate::PAGES7]['hits']);
        Assert::same(0, $scores[SiteTemplate::PAGES12]['score']);
    }

    public function testTypeOfSiteIsVoteOfOpenedPages(): void
    {
        // Голосуют только успешно открытые страницы; при равенстве семейство сильнее «без категории».
        Assert::same('', SiteTemplate::ofVisits([]), 'страниц нет — типа нет');
        Assert::same('', SiteTemplate::ofVisits([['ok' => false, 'template' => 'pages7']]), 'неудачный визит не голосует');
        Assert::same(SiteTemplate::PAGES7, SiteTemplate::ofVisits([['ok' => true, 'template' => 'other'], ['ok' => true, 'template' => 'pages7']]), 'заглушка без признаков не перевешивает главную');
        Assert::same(SiteTemplate::PAGES12, SiteTemplate::ofVisits([['ok' => true, 'template' => 'pages7'], ['ok' => true, 'template' => 'pages12'], ['ok' => true, 'template' => 'pages12']]));
        Assert::same(SiteTemplate::OTHER, SiteTemplate::ofVisits([['ok' => true, 'template' => 'other']]));
        Assert::same('', SiteTemplate::ofVisits([['ok' => true]]), 'старый визит без поля template — типа нет');
    }

    public function testHistogramCountsSitesByTypeInFixedOrder(): void
    {
        $mk = static function (string $host, string $type, bool $own = false): Site {
            $s = new Site($host, $host, $host);
            $s->own = $own;
            if ($type !== '') {
                $s->visits[] = ['variant' => 1, 'url' => "https://$host/", 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => '', 'template' => $type];
            }

            return $s;
        };
        $hist = SiteTemplate::histogram([$mk('a.ru', 'other'), $mk('b.ru', 'pages12'), $mk('c.ru', 'pages7'), $mk('d.ru', 'pages7'), $mk('e.ru', ''), $mk('f.ru', 'pages7', true)]);
        Assert::same(['pages7' => 2, 'pages12' => 1, 'other' => 1], $hist, 'порядок фиксированный; без страниц и наши не считаются');
        Assert::same('7–9 стр. — 2, 12–15 стр. — 1, без категории — 1', SiteTemplate::histogramText($hist));
        Assert::same('', SiteTemplate::histogramText([]));
        Assert::same('без категории', SiteTemplate::label('unknown'), 'неизвестный тип — без категории');
    }
}

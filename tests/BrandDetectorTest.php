<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Content\BrandDetector;

final class BrandDetectorTest
{
    public function testEnglishBrandFromHost(): void
    {
        $d = new BrandDetector();
        Assert::same('cryptoboss', $d->brandFromHost('cryptoboss.ccy.casino'));
        Assert::same('cryptoboss', $d->brandFromHost('www.cryptoboss.com'));
        Assert::same('pokerdom', $d->brandFromHost('pokerdom.net'));
    }

    public function testRussianBrandByTransliteration(): void
    {
        $d = new BrandDetector();
        $r = $d->detect('<h1>Криптобосс</h1><p>Играть в Криптобосс, криптобосс топ</p>', 'cryptoboss.ccy.casino');
        Assert::same('cryptoboss', $r['en']);
        Assert::same('криптобосс', $r['ru']);

        $r2 = $d->detect('<p>Покердом — лучшее казино, Покердом бонусы</p>', 'pokerdom.com');
        Assert::same('покердом', $r2['ru']);
    }

    public function testNoFalsePositiveWhenBrandAbsent(): void
    {
        $d = new BrandDetector();
        $r = $d->detect('<p>Просто текст про казино и бонусы без названия</p>', 'unknownbrand777.com');
        Assert::same('unknownbrand777', $r['en']);
        Assert::same('', $r['ru'], 'если русского бренда нет — не выдумываем');
    }

    public function testMultiWordRussianBrand(): void
    {
        // Бренд из двух слов: одиночного токена «вулкан»/«вегас» мало — нужна пара «вулкан вегас».
        $d = new BrandDetector();
        $r = $d->detect('<h1>Обзор</h1><p>Вулкан Вегас — казино. Играть в Вулкан Вегас, Вулкан Вегас бонусы.</p>', 'vulkanvegas.com');
        Assert::same('vulkanvegas', $r['en']);
        Assert::same('вулкан вегас', $r['ru'], 'русский бренд из двух слов найден');
    }

    public function testBrandFoundOnInnerPageWhenHomeIsStub(): void
    {
        // Главная — заглушка проверки возраста (бренда нет), но бренд и canonical есть на внутренней
        // странице. По ней и определяем — иначе после очистки ничего не подставится.
        $d = new BrandDetector();
        $gate = '<html><head><title>18+</title></head><body><div>Подтвердите возраст. Вам есть 18 лет?</div></body></html>';
        $inner = '<head><link rel="canonical" href="https://twin.brandzz.buzz/promo"></head>'
            . '<body><h1>Твин</h1><p>Официальный сайт Твин казино, Твин дарит бонусы, играть в Твин.</p></body>';
        $r = $d->detect($gate, 'brandzz.buzz', [$inner]);
        Assert::same('twin', $r['en'], 'бренд взят с внутренней страницы (canonical поддомена)');
        Assert::same('твин', $r['ru']);
    }

    public function testGenericDomainDoesNotYieldCasinoAsBrand(): void
    {
        // Домен родовой (casino777), русского бренда в тексте нет — «казино» не должно стать брендом.
        $d = new BrandDetector();
        $r = $d->detect('<p>Лучшее казино онлайн, бонусы и слоты каждый день</p>', 'casino777.com');
        Assert::same('', $r['ru'], 'служебное слово «казино» не выдаём за бренд');
    }

    public function testBrandFromCanonicalSubdomain(): void
    {
        // Регистрируемый домен общий (casinozsd), бренд — в поддомене canonical/og:url (kush) и в тексте.
        $d = new BrandDetector();
        $html = '<head><link rel="canonical" href="https://kush.casinozsd.buzz/"></head>'
            . '<body><h1>Куш Казино</h1><p>Официальный сайт Куш Казино (Kush Casino), Куш топ</p></body>';
        $r = $d->detect($html, 'casinozsd.buzz');
        Assert::same('kush', $r['en'], 'бренд берётся из поддомена canonical, а не из домена casinozsd');
        Assert::same('куш', $r['ru']);

        // og:url тоже подходит как источник хоста бренда.
        $og = '<head><meta property="og:url" content="https://eva.casinopyb.buzz/ru/"></head>'
            . '<body><p>Ева Казино — заходите, Ева дарит бонусы</p></body>';
        Assert::same('eva', $d->detect($og, 'casinopyb.buzz')['en']);
    }
}

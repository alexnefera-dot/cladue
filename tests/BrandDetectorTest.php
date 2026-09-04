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
}

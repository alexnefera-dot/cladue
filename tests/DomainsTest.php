<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\Domains;

final class DomainsTest
{
    public function testNormalize(): void
    {
        Assert::same('example.ru', Domains::normalize('WWW.Example.RU.'));
        Assert::same('example.ru', Domains::normalize('https://www2.example.ru/path?x=1'));
        Assert::same('www.example.ru', Domains::normalize('www.example.ru', false));
        Assert::same('example.ru', Domains::normalize('example.ru:8080'));
        Assert::same('shop.example.ru', Domains::normalize(' shop.example.ru '));
    }

    public function testHostFromUrl(): void
    {
        Assert::same('www.avito.ru', Domains::hostFromUrl('https://www.avito.ru/moskva/okna'));
        Assert::same('example.ru', Domains::hostFromUrl('example.ru/page'));
        Assert::same('', Domains::hostFromUrl(''));
    }

    public function testTld(): void
    {
        Assert::same('ru', Domains::tld('shop.example.ru'));
        Assert::same('рф', Domains::tld('xn--80aswg.xn--p1ai'));
        Assert::same('рф', Domains::tld('x.рф'));
        Assert::same('moscow', Domains::tld('okna.moscow'));
    }

    public function testRegistrable(): void
    {
        Assert::same('example.ru', Domains::registrable('example.ru'));
        Assert::same('example.ru', Domains::registrable('shop.example.ru'));
        Assert::same('example.ru', Domains::registrable('a.b.example.ru'));
        Assert::same('okna.msk.ru', Domains::registrable('www.okna.msk.ru'));
        Assert::same('example.co.uk', Domains::registrable('shop.example.co.uk'));
        Assert::same('localhost', Domains::registrable('localhost'));
    }

    public function testUnicodeConversion(): void
    {
        $unicode = Domains::toUnicode('xn--80aswg.xn--p1ai');
        Assert::true(in_array($unicode, ['сайт.рф', 'xn--80aswg.рф'], true), 'toUnicode');
        Assert::same('example.ru', Domains::toUnicode('example.ru'));

        $ascii = Domains::toAscii('пример.рф');
        Assert::true(in_array($ascii, ['xn--e1afmkfd.xn--p1ai', 'пример.xn--p1ai'], true), 'toAscii');
        Assert::same('example.ru', Domains::toAscii('example.ru'));
    }

    public function testSameSite(): void
    {
        Assert::true(Domains::sameSite('example.ru', 'www.example.ru'));
        Assert::true(Domains::sameSite('shop.example.ru', 'example.ru'));
        Assert::false(Domains::sameSite('example.ru', 'other.ru'));
    }
}

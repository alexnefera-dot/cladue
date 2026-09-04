<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\DomainMatcher;

final class DomainMatcherTest
{
    public function testDomainPatternMatchesDomainAndSubdomains(): void
    {
        $m = new DomainMatcher(['yandex.ru']);
        Assert::true($m->matches('yandex.ru'));
        Assert::true($m->matches('market.yandex.ru'));
        Assert::true($m->matches('www.yandex.ru'));
        Assert::false($m->matches('yandex.ru.example.com'));
        Assert::false($m->matches('notyandex.ru'));
        Assert::false($m->matches('dzen.ru'));
    }

    public function testSubdomainsOnly(): void
    {
        $m = new DomainMatcher(['*.example.ru']);
        Assert::true($m->matches('shop.example.ru'));
        Assert::false($m->matches('example.ru'));
    }

    public function testExact(): void
    {
        $m = new DomainMatcher(['=example.ru']);
        Assert::true($m->matches('example.ru'));
        Assert::true($m->matches('www.example.ru'), 'www отбрасывается при нормализации');
        Assert::false($m->matches('shop.example.ru'));
    }

    public function testRegex(): void
    {
        $m = new DomainMatcher(['/^shop\d+\./i', '~\.spb\.ru$~']);
        Assert::true($m->matches('shop12.example.ru'));
        Assert::true($m->matches('okna.spb.ru'));
        Assert::false($m->matches('example.ru'));

        Assert::throws(\InvalidArgumentException::class, static fn () => new DomainMatcher(['/(unclosed/']));
    }

    public function testCyrillicDomains(): void
    {
        $m = new DomainMatcher(['сайт.рф']);
        Assert::true($m->matches('xn--80aswg.xn--p1ai'));
        Assert::true($m->matches('сайт.рф'));
    }

    public function testEmptyAndComments(): void
    {
        $m = new DomainMatcher(['', '# comment', 'a.ru']);
        Assert::same(1, $m->count());
        Assert::false((new DomainMatcher([]))->matches('a.ru'));
        Assert::true((new DomainMatcher([]))->isEmpty());
    }
}

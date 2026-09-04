<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\TextMatcher;

final class TextMatcherTest
{
    public function testSubstringCaseInsensitive(): void
    {
        $m = new TextMatcher(['Окна', 'балкон']);
        Assert::true($m->matchesAny('Пластиковые ОКНА в Москве'));
        Assert::false($m->matchesAll('Пластиковые окна в Москве'));
        Assert::true($m->matchesAll('окна и балконы'));
        Assert::false($m->matchesAny('двери'));
    }

    public function testRegex(): void
    {
        $m = new TextMatcher(['~окн[аы]~iu']);
        Assert::true($m->matchesAny('ОКНЫ'));
        Assert::false($m->matchesAny('окно'));
    }

    public function testRegexOnlyMode(): void
    {
        Assert::throws(\InvalidArgumentException::class, static fn () => new TextMatcher(['catalog'], true, 'url'), 'url');
        $m = new TextMatcher('~/catalog/~', true);
        Assert::true($m->matchesAny('https://a.ru/catalog/1'));
    }

    public function testInvalidRegex(): void
    {
        Assert::throws(\InvalidArgumentException::class, static fn () => new TextMatcher(['~(~'], false, 'title_any'), 'title_any');
    }

    public function testEmpty(): void
    {
        $m = new TextMatcher(null);
        Assert::true($m->isEmpty());
        Assert::true($m->matchesAll('anything'));
        Assert::false($m->matchesAny('anything'));
    }
}

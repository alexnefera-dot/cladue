<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\ResultFilter;
use YandexSites\Model\SearchResult;

final class ResultFilterTest
{
    private function result(string $host, string $title = 'Пластиковые окна', int $position = 1, string $url = '', string $snippet = ''): SearchResult
    {
        return new SearchResult('окна', 0, $position, $url !== '' ? $url : 'https://' . $host . '/page/', $host, $title, '', $snippet);
    }

    public function testNoRulesPassesEverything(): void
    {
        $filter = new ResultFilter([]);
        Assert::null($filter->reject($this->result('example.ru')));
    }

    public function testDomainRules(): void
    {
        $filter = new ResultFilter(['exclude_domains' => ['avito.ru', 'yandex.ru']]);
        Assert::same('exclude_domains', $filter->reject($this->result('www.avito.ru')));
        Assert::same('exclude_domains', $filter->reject($this->result('market.yandex.ru')));
        Assert::null($filter->reject($this->result('okna.ru')));

        $filter = new ResultFilter(['include_domains' => ['my-site.ru']]);
        Assert::null($filter->reject($this->result('my-site.ru')));
        Assert::same('include_domains', $filter->reject($this->result('other.ru')));
    }

    public function testTld(): void
    {
        $filter = new ResultFilter(['allowed_tlds' => ['ru', 'рф', '.su']]);
        Assert::null($filter->reject($this->result('okna.ru')));
        Assert::null($filter->reject($this->result('xn--80aswg.xn--p1ai')));
        Assert::null($filter->reject($this->result('old.su')));
        Assert::same('tld', $filter->reject($this->result('okna.com')));

        $filter = new ResultFilter(['allowed_tlds' => ['xn--p1ai']]);
        Assert::null($filter->reject($this->result('xn--80aswg.xn--p1ai')), 'зона в punycode тоже принимается');
    }

    public function testPositionAndUrl(): void
    {
        $filter = new ResultFilter(['max_position' => 10]);
        Assert::same('position', $filter->reject($this->result('a.ru', 'x', 11)));
        Assert::null($filter->reject($this->result('a.ru', 'x', 10)));

        $filter = new ResultFilter(['url_must_not_match' => ['~/(forum|blog)/~i', '~\.pdf$~i'], 'url_must_match' => ['~^https://~']]);
        Assert::same('url_must_not_match', $filter->reject($this->result('a.ru', 'x', 1, 'https://a.ru/forum/topic')));
        Assert::same('url_must_not_match', $filter->reject($this->result('a.ru', 'x', 1, 'https://a.ru/price.PDF')));
        Assert::same('url_must_match', $filter->reject($this->result('a.ru', 'x', 1, 'http://a.ru/')));
        Assert::null($filter->reject($this->result('a.ru', 'x', 1, 'https://a.ru/catalog/')));
    }

    public function testTitleAndSnippetRules(): void
    {
        $filter = new ResultFilter(['title_any' => ['окна', 'балкон'], 'title_none' => ['вакансии', 'форум']]);
        Assert::null($filter->reject($this->result('a.ru', 'Пластиковые ОКНА')));
        Assert::same('title_any', $filter->reject($this->result('a.ru', 'Двери')));
        Assert::same('title_none', $filter->reject($this->result('a.ru', 'Окна — форум')));

        $filter = new ResultFilter(['title_all' => ['окна', 'москв']]);
        Assert::null($filter->reject($this->result('a.ru', 'Окна в Москве')));
        Assert::same('title_all', $filter->reject($this->result('a.ru', 'Окна в Туле')));

        $filter = new ResultFilter(['snippet_any' => ['~\+7[\s\-(]*\d{3}~u'], 'snippet_none' => ['оптом']]);
        Assert::null($filter->reject($this->result('a.ru', 'Окна', 1, '', 'Звоните +7 (495) 111-22-33')));
        Assert::same('snippet_any', $filter->reject($this->result('a.ru', 'Окна', 1, '', 'без телефона')));
        Assert::same('snippet_none', $filter->reject($this->result('a.ru', 'Окна', 1, '', '+7 495 111 22 33, продаём оптом')));
    }

    public function testDomainScope(): void
    {
        $all = new ResultFilter([]);
        Assert::null($all->reject($this->result('example.ru')));
        Assert::null($all->reject($this->result('shop.example.ru')));

        $root = new ResultFilter(['domain_scope' => 'root']);
        Assert::null($root->reject($this->result('example.ru')));
        Assert::null($root->reject($this->result('www.example.ru')), 'www отбрасывается — считается корневым');
        Assert::null($root->reject($this->result('okna.msk.ru')), 'домен во второй зоне — корневой');
        Assert::same('domain_scope', $root->reject($this->result('shop.example.ru')));

        $sub = new ResultFilter(['domain_scope' => 'subdomain']);
        Assert::same('domain_scope', $sub->reject($this->result('example.ru')));
        Assert::null($sub->reject($this->result('shop.example.ru')));
    }

    public function testInvalidRegexIsReported(): void
    {
        Assert::throws(\InvalidArgumentException::class, static fn () => new ResultFilter(['url_must_match' => ['~(~']]), 'url_must_match');
        Assert::throws(\InvalidArgumentException::class, static fn () => new ResultFilter(['url_must_match' => ['plain text']]), 'url_must_match');
    }

    public function testResultWithoutHostUsesUrl(): void
    {
        $filter = new ResultFilter(['exclude_domains' => ['avito.ru']]);
        Assert::same('exclude_domains', $filter->reject(new SearchResult('q', 0, 1, 'https://www.avito.ru/x', '', 'T')));
        Assert::same('no_host', $filter->reject(new SearchResult('q', 0, 1, '', '', 'T')));
    }
}

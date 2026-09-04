<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Aggregator;
use YandexSites\Model\SearchResult;

final class AggregatorTest
{
    public function testAggregatesByHost(): void
    {
        $a = new Aggregator('host');
        $a->add(new SearchResult('q1', 0, 5, 'https://www.example.ru/a', 'www.example.ru', 'A'));
        $a->add(new SearchResult('q2', 0, 2, 'https://example.ru/b', 'example.ru', 'B'));
        $a->add(new SearchResult('q2', 0, 7, 'https://example.ru/c', 'example.ru', 'C'));
        $a->add(new SearchResult('q1', 0, 1, 'https://shop.example.ru/', 'shop.example.ru', 'Shop'));

        $sites = $a->sites();
        Assert::same(['example.ru', 'shop.example.ru'], array_keys($sites));

        $site = $sites['example.ru'];
        Assert::same(3, $site->hits);
        Assert::same(2, $site->queryCount());
        Assert::same(['q1' => 5, 'q2' => 2], $site->queries);
        Assert::same(2, $site->bestPosition);
        Assert::same('https://example.ru/b', $site->bestUrl);
        Assert::same('B', $site->bestTitle);
        Assert::same('q2', $site->bestQuery);
        Assert::same('example.ru', $site->domain);
        Assert::same(3, count($site->urls));
    }

    public function testAggregatesByDomain(): void
    {
        $a = new Aggregator('domain');
        $a->add(new SearchResult('q1', 0, 5, 'https://www.example.ru/a', 'www.example.ru', 'A'));
        $a->add(new SearchResult('q1', 0, 1, 'https://shop.example.ru/', 'shop.example.ru', 'Shop'));
        $a->add(new SearchResult('q1', 0, 3, 'https://okna.msk.ru/', 'okna.msk.ru', 'Msk'));

        $sites = $a->sites();
        Assert::same(['example.ru', 'okna.msk.ru'], array_keys($sites));
        Assert::same(2, $sites['example.ru']->hits);
        Assert::same('example.ru', $sites['example.ru']->host);
    }

    public function testKeepWww(): void
    {
        $a = new Aggregator('host', false);
        $a->add(new SearchResult('q1', 0, 5, 'https://www.example.ru/a', 'www.example.ru', 'A'));
        Assert::same(['www.example.ru'], array_keys($a->sites()));
    }
}

<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Support\BrandDomains;

/**
 * Домены, которые держат много брендов: на их поддоменах сайты разных брендов.
 * Главное здесь — не посчитать лишнего: один бренд в двух написаниях и портал с обзорами
 * (шесть брендовых запросов на ОДИН адрес без поддомена) в список не идут.
 */
final class BrandDomainsTest
{
    /**
     * @param list<array{0: string, 1: string}> $rows пары «хост, запрос»
     * @return list<array{result: SearchResult, reason: string|null}>
     */
    private function raw(array $rows, ?string $reason = null): array
    {
        $out = [];
        foreach ($rows as $i => [$host, $query]) {
            $out[] = [
                'result' => new SearchResult($query, 0, $i + 1, 'https://' . $host . '/', $host, 'T'),
                'reason' => $reason,
            ];
        }

        return $out;
    }

    /** @param list<string> $domains */
    private function sites(array $domains): array
    {
        $out = [];
        foreach ($domains as $domain) {
            $out[$domain] = new Site($domain, $domain, $domain);
        }

        return $out;
    }

    public function testDomainWithManyBrandsOnSubdomainsIsFound(): void
    {
        $raw = $this->raw([
            ['kush.net-drop.buzz', 'куш казино зеркало'],
            ['vulkan.net-drop.buzz', 'вулкан вегас казино'],
            ['kometa.net-drop.buzz', 'комета казино'],
            ['starda.net-drop.buzz', 'старда казино официальный сайт'],
            ['gizbo.net-drop.buzz', 'гизбо казино вход'],
            ['lex.net-drop.buzz', 'лекс казино'],
            ['irwin.net-drop.buzz', 'ирвин казино'],
        ]);

        $found = BrandDomains::find($raw, $this->sites(['net-drop.buzz']));
        Assert::same(['net-drop.buzz'], array_keys($found), 'домен сетки найден');
        Assert::same(7, count($found['net-drop.buzz']['brands']), 'семь разных брендов');
        Assert::same(7, $found['net-drop.buzz']['hosts'], 'семь доров');
        Assert::contains('net-drop.buzz — брендов 7', BrandDomains::text($found));
        Assert::same([['domain' => 'net-drop.buzz', 'brands' => 7, 'hosts' => 7]], BrandDomains::top($found));
    }

    public function testFiveBrandsIsNotEnough(): void
    {
        // «Более пяти» — значит от шести: ровно пять в список не идут.
        $raw = $this->raw([
            ['a.small.buzz', 'куш казино'],
            ['b.small.buzz', 'комета казино'],
            ['c.small.buzz', 'старда казино'],
            ['d.small.buzz', 'гизбо казино'],
            ['e.small.buzz', 'лекс казино'],
        ]);
        Assert::same([], BrandDomains::find($raw, $this->sites(['small.buzz'])));
    }

    public function testSameBrandInDifferentSpellingsCountsOnce(): void
    {
        // Шесть запросов, но брендов три: «Вулкан Вегас»/«Vulkan Vegas» — один бренд.
        $raw = $this->raw([
            ['a.mix.buzz', 'вулкан вегас казино'],
            ['b.mix.buzz', 'Vulkan Vegas зеркало'],
            ['c.mix.buzz', 'криптобосс казино'],
            ['d.mix.buzz', 'cryptoboss casino'],
            ['e.mix.buzz', 'мани икс казино'],
            ['f.mix.buzz', 'Money X casino'],
        ]);
        $found = BrandDomains::find($raw, $this->sites(['mix.buzz']), 4);
        Assert::same([], $found, 'три бренда в шести написаниях порога не дают');
        Assert::same(3, count(BrandDomains::find($raw, $this->sites(['mix.buzz']), 3)['mix.buzz']['brands']));
    }

    public function testPortalOnItsOwnDomainIsNotADropDomain(): void
    {
        // Сайт-обзорник ранжируется по шести брендовым запросам, но живёт на самом домене,
        // без поддоменов — это не сетка.
        $raw = $this->raw([
            ['review.ru', 'куш казино'],
            ['review.ru', 'комета казино'],
            ['review.ru', 'старда казино'],
            ['review.ru', 'гизбо казино'],
            ['review.ru', 'лекс казино'],
            ['review.ru', 'ирвин казино'],
            ['www.review.ru', 'вулкан вегас казино'],
        ]);
        Assert::same([], BrandDomains::find($raw, $this->sites(['review.ru'])), 'www — тоже не поддомен');
    }

    public function testRejectedRowsAndForeignDomainsAreIgnored(): void
    {
        $rows = [
            ['a.cut.buzz', 'куш казино'],
            ['b.cut.buzz', 'комета казино'],
            ['c.cut.buzz', 'старда казино'],
            ['d.cut.buzz', 'гизбо казино'],
            ['e.cut.buzz', 'лекс казино'],
            ['f.cut.buzz', 'ирвин казино'],
        ];
        // Те же строки, но отсеянные фильтрами — в отобранное они не попали.
        Assert::same([], BrandDomains::find($this->raw($rows, 'domain_scope'), $this->sites(['cut.buzz'])), 'срезанные строки не считаем');
        // И домен, которого нет среди отобранных сайтов, тоже не считаем.
        Assert::same([], BrandDomains::find($this->raw($rows), $this->sites(['other.buzz'])), 'чужой домен не считаем');
    }

    public function testQueriesWithoutBrandDoNotCount(): void
    {
        $raw = $this->raw([
            ['a.plain.buzz', 'пластиковые окна москва'],
            ['b.plain.buzz', 'купить окна недорого'],
            ['c.plain.buzz', 'остекление балконов цена'],
            ['d.plain.buzz', 'окна пвх установка москва'],
            ['e.plain.buzz', 'балконы под ключ стоимость'],
            ['f.plain.buzz', 'окна рехау официальный дилер москва'],
        ]);
        Assert::same([], BrandDomains::find($raw, $this->sites(['plain.buzz'])), 'бренда в запросах нет — считать нечего');
    }
}

<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Dorgen\DorgenClient;
use YandexSites\Dorgen\OwnBases;
use YandexSites\Filter\OwnSites;
use YandexSites\Support\SerpAnalysis;

final class DorgenTest
{
    /** @var list<string> */
    private array $dirs = [];

    private function dir(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-dorgen-' . uniqid();
        mkdir($dir . '/runs', 0777, true);
        $this->dirs[] = $dir;

        return $dir;
    }

    /** Клиент к фейковому API без настоящих пауз: иначе повторы ждали бы минуты. */
    private function client(int $port): DorgenClient
    {
        return new DorgenClient('test-token', "http://127.0.0.1:$port", null, static function (int $ms): void {});
    }

    public function testSplitsLongPeriodByThirtyOneDays(): void
    {
        // API не принимает период длиннее 31 дня — режем сами, границы включительно и без дыр.
        $parts = DorgenClient::splitPeriod('2026-01-01', '2026-03-05');
        Assert::same([
            ['2026-01-01', '2026-01-31'],
            ['2026-02-01', '2026-03-03'],
            ['2026-03-04', '2026-03-05'],
        ], $parts, 'куски по 31 дню подряд, без пропусков');

        Assert::same([['2026-01-01', '2026-01-10']], DorgenClient::splitPeriod('2026-01-01', '2026-01-10'), 'короткий период — один кусок');
        Assert::same([['2026-01-01', '2026-01-01']], DorgenClient::splitPeriod('2026-01-01', '2026-01-01'), 'один день');
        Assert::same([['2026-01-01', '2026-01-05']], DorgenClient::splitPeriod('2026-01-05', '2026-01-01'), 'даты наоборот — переставляем');
    }

    public function testBaseIsLastTwoLabels(): void
    {
        // Сверка идёт по БАЗЕ — последним двум меткам хоста: каждая база несёт все бренды.
        Assert::same('4916.team', DorgenClient::baseOf('leebet.4916.team'));
        Assert::same('4916.team', DorgenClient::baseOf('a.b.leebet.4916.team'));
        Assert::same('4916.team', DorgenClient::baseOf('4916.team'));
        Assert::same('4916.team', DorgenClient::baseOf('WWW.4916.TEAM'), 'регистр и www не мешают');
        Assert::same('', DorgenClient::baseOf('localhost'), 'без точки базы нет');
        Assert::same('', DorgenClient::baseOf(''));
    }

    public function testFetchesAllPagesAndKeepsOnlyNeededFields(): void
    {
        $port = FakeServer::port();
        $rows = iterator_to_array($this->client($port)->subdomains('2026-01-01', '2026-01-05'));

        Assert::same(3, count($rows), 'обе страницы прочитаны по cursor');
        Assert::same('leebet.4916.team', $rows[0]['subdomain']);
        Assert::same('4916.team', $rows[0]['content_domain_url'], 'база — последние две метки');
        Assert::same('leebet', $rows[0]['brand_label']);
        Assert::contains('2026-01-01', $rows[0]['pipeline_started']);
        Assert::same('content-leebet', $rows[0]['content_label']);
        Assert::false(array_key_exists('huge_raw_field', $rows[0]), 'сырой ответ не храним — только нужные поля');
        Assert::same('7788.team', $rows[2]['content_domain_url'], 'вторая страница');
    }

    public function testRetriesFlakyServerErrors(): void
    {
        // «/v1/subdomains случайно отвечает 500 (бывает до половины запросов)» + 429 — повторяем тот же
        // запрос с тем же cursor, а не падаем.
        @unlink(sys_get_temp_dir() . '/yandex-sites-dorgen-fails.txt');
        $port = FakeServer::port('dorgenflaky');
        $rows = iterator_to_array($this->client($port)->subdomains('2026-01-01', '2026-01-02'));
        Assert::same(3, count($rows), 'после 500 и 429 данные всё равно получены');
    }

    public function testCacheKeepsBasesAndLoadsOnlyNewDays(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir();
        $cache = OwnBases::inRuns($dir . '/runs');
        Assert::same(0, $cache->count(), 'кэша ещё нет');

        $r = $cache->refresh($this->client($port), '2026-01-01', '2026-01-05');
        Assert::same(3, $r['rows'], 'строк прочитано');
        Assert::same(2, $r['bases'], 'баз всего (три поддомена на двух базах)');
        Assert::same(2, $r['new_bases']);
        Assert::same(['4916.team' => true, '7788.team' => true], $cache->bases());
        Assert::true($cache->matches('leebet.4916.team'), 'наш поддомен');
        Assert::true($cache->matches('newbrand.4916.team'), 'любой поддомен нашей базы — наш');
        Assert::false($cache->matches('kush.stranger.top'), 'чужая база — не наш');

        // Кэш помнит период: следующая выгрузка идёт с нахлёстом в сутки, а не с начала истории.
        Assert::same('2026-01-04', $cache->nextFrom('2020-01-01'), 'догружаем только новые дни');
        $again = $cache->refresh($this->client($port), '2026-01-04', '2026-01-06');
        Assert::same(2, $again['bases'], 'повторная выгрузка не плодит базы');
        Assert::same(0, $again['new_bases']);
        Assert::same('2026-01-01', $cache->load()['date_from'], 'начало периода сохранено');
        Assert::same('2026-01-06', $cache->load()['date_to'], 'конец периода продвинулся');

        $raw = (string) file_get_contents($dir . '/runs/' . OwnBases::FILE);
        Assert::false(str_contains($raw, 'huge_raw_field'), 'сырой JSON в кэш не попадает');
        Assert::false(str_contains($raw, 'leebet.4916.team'), 'сами поддомены не храним — только базы');
    }

    public function testSerpAnalysisMarksOursByDorgenBases(): void
    {
        // Выгрузка — самый точный источник: он перебивает догадки по меткам и понятен в отчёте.
        $row = static fn (string $host): array => ['query' => 'вулкан казино', 'position' => 1, 'host' => $host,
            'url' => "https://$host/", 'title' => 'Вулкан', 'snippet' => 'казино', 'reason' => 'selected'];
        $rows = [$row('leebet.4916.team'), $row('kush.stranger.top')];

        $a = SerpAnalysis::build($rows, 10, new OwnSites([]), [], ['4916.team' => true]);
        $hosts = $a['brands'][0]['hosts'];
        Assert::true($hosts['leebet.4916.team']['own'], 'база из выгрузки — наш');
        Assert::same(SerpAnalysis::REASON_DORGEN, $hosts['leebet.4916.team']['own_reason'], 'причина названа');
        Assert::false($hosts['kush.stranger.top']['own'], 'чужая база — не наш');
        Assert::same(1, $a['own']['doors']);
        Assert::same([SerpAnalysis::REASON_DORGEN => 1], $a['own']['by_reason']);

        // Без выгрузки прежняя логика не меняется: метки и список доменов работают как работали.
        $b = SerpAnalysis::build($rows, 10, new OwnSites(['4916.team']), []);
        Assert::true($b['brands'][0]['hosts']['leebet.4916.team']['own'], 'метка по-прежнему работает');
        Assert::same('метка «4916.team»', $b['brands'][0]['hosts']['leebet.4916.team']['own_reason']);
    }

    public function testNoTokenMeansFeatureIsSimplyOff(): void
    {
        putenv(DorgenClient::TOKEN_ENV . '=');
        unset($_ENV[DorgenClient::TOKEN_ENV]);
        Assert::same(null, DorgenClient::fromEnv(), 'без ключа выгрузка просто не используется');
    }

    public function tearDownClass(): void
    {
        foreach ($this->dirs as $dir) {
            if (!is_dir($dir)) {
                continue;
            }
            $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
            foreach ($it as $item) {
                $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
            }
            @rmdir($dir);
        }
    }
}

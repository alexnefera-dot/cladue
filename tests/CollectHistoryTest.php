<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Support\CollectHistory;

/**
 * История сборов для вкладки «Статистика». Смотрим на ДОРЫ: сколько их, какая доля, сколько
 * повторов-доров и по каким зонам они разошлись (зоны считаются только по дорам).
 */
final class CollectHistoryTest
{
    private ?string $dir = null;

    private function dir(): string
    {
        if ($this->dir === null) {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-history-' . uniqid();
            mkdir($this->dir);
        }

        return $this->dir;
    }

    /** Отдельная папка под каждый тест: история дописывается в файл, соседние тесты мешать не должны. */
    private function runsDir(): string
    {
        $dir = $this->dir() . '/run-' . uniqid();
        mkdir($dir);

        return $dir;
    }

    /** @return list<Site> */
    private function sites(string ...$hosts): array
    {
        $out = [];
        foreach ($hosts as $host) {
            $parts = explode('.', $host);
            $domain = count($parts) > 2 ? implode('.', array_slice($parts, -2)) : $host;
            $site = new Site($host, $host, $domain); // key, host, регистрируемый домен
            $site->add(new SearchResult('запрос', 0, 1, 'https://' . $host . '/', $host, ''));
            $out[] = $site;
        }

        return $out;
    }

    public function testBreakdownCountsDoorsAndTheirZonesOnly(): void
    {
        $b = CollectHistory::breakdown($this->sites(
            'example.ru',          // корневой
            'www.second.ru',       // www — тот же корневой домен, не дор
            'kush.casinozsd.buzz', // поддомен — дор
            'hype.casinozsd.buzz',
            'promo.third.com',
        ));
        Assert::same(2, $b['roots'], 'корневых: example.ru и second.ru');
        Assert::same(3, $b['doors'], 'доров: kush., hype. и promo.');
        Assert::same(2, $b['zones']['buzz'] ?? 0);
        Assert::same(1, $b['zones']['com'] ?? 0);
        Assert::same(0, $b['zones']['ru'] ?? 0, 'зона корневых сайтов в статистику доров не идёт');
    }

    public function testDeduplicatedByDomainSiteIsStillADoor(): void
    {
        // Главный баг первой версии: при дедупе по домену (панель включает его по умолчанию)
        // Aggregator кладёт в Site::$host РЕГИСТРИРУЕМЫЙ домен, поэтому дор выглядел корневым —
        // в панели вышло «339 доменов, доров 0». Настоящий хост берётся из адреса выдачи.
        $site = new Site('casinozsd.buzz', 'casinozsd.buzz', 'casinozsd.buzz'); // ключ = домен
        $site->add(new SearchResult('казино', 0, 1, 'https://kush.casinozsd.buzz/', 'kush.casinozsd.buzz', 'Куш'));

        $b = CollectHistory::breakdown([$site]);
        Assert::same(1, $b['doors'], 'сайт на поддомене — дор, даже если сгруппирован по домену');
        Assert::same(0, $b['roots']);
        Assert::same(1, $b['zones']['buzz'] ?? 0);
    }

    public function testRedirectToBrandSubdomainCountsAsDoor(): void
    {
        // Сетка часто собирается по апексу, а главная редиректит на бренд-поддомен — по адресу из
        // выдачи это ещё не дор, а по конечному адресу визита уже дор.
        $site = new Site('casinozsd.buzz', 'casinozsd.buzz', 'casinozsd.buzz');
        $site->add(new SearchResult('казино', 0, 1, 'https://casinozsd.buzz/', 'casinozsd.buzz', 'Куш'));
        $site->visits = [['ok' => true, 'url' => 'https://casinozsd.buzz/', 'final_url' => 'https://kush.casinozsd.buzz/']];

        Assert::same('kush.casinozsd.buzz', $site->realHost(), 'настоящий хост — куда привёл редирект');
        Assert::same(1, CollectHistory::breakdown([$site])['doors']);
    }

    public function testBackfillLatestRecomputesDoorsFromSites(): void
    {
        // Записи старых версий: «доров 0» при непустой таблице — пересчитываем по текущему списку сайтов.
        $dir = $this->runsDir();
        $site = new Site('casinozsd.buzz', 'casinozsd.buzz', 'casinozsd.buzz');
        $site->add(new SearchResult('казино', 0, 1, 'https://kush.casinozsd.buzz/', 'kush.casinozsd.buzz', 'Куш'));
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([
            ['date' => '2026-09-15T17:48:00+00:00', 'sites' => 1, 'doors' => 0, 'roots' => 1, 'zones' => [], 'repeats' => 5],
        ]));

        $updated = CollectHistory::backfillLatest($dir, [$site]);
        Assert::true($updated !== null, 'запись пересчитана');
        Assert::same(1, $updated['doors']);
        Assert::same(1, $updated['zones']['buzz'] ?? 0);
        Assert::same(5, $updated['repeats'], 'остальные поля записи не тронуты');
        Assert::same(1, CollectHistory::load($dir)[0]['doors'], 'пересчёт сохранён на диск');
        Assert::same(null, CollectHistory::backfillLatest($dir, [$site]), 'второй раз пересчитывать нечего');
    }

    public function testBackfillLatestSkipsDifferentCollect(): void
    {
        // Число сайтов в таблице не совпало с записью — это другой сбор, не трогаем.
        $dir = $this->runsDir();
        $site = new Site('a.example.ru', 'a.example.ru', 'example.ru');
        $site->add(new SearchResult('к', 0, 1, 'https://a.example.ru/', 'a.example.ru', 'A'));
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([['date' => '2026-09-15T17:48:00+00:00', 'sites' => 42, 'doors' => 0]]));
        Assert::same(null, CollectHistory::backfillLatest($dir, [$site]));
    }

    public function testIsDoorIgnoresWww(): void
    {
        Assert::true(CollectHistory::isDoor('kush.casinozsd.buzz'));
        Assert::false(CollectHistory::isDoor('casinozsd.buzz'));
        Assert::false(CollectHistory::isDoor('www.casinozsd.buzz'), 'www — не поддомен-дор');
    }

    public function testRecordCountsDoorRepeatsSeparately(): void
    {
        $record = CollectHistory::record(
            $this->sites('a.ru', 'sub.b.com'),
            ['base_domains' => 900, 'rejected' => ['seen_before' => 4, 'tld' => 7]],
            // Повторы: два дора; www.plain.com не дор, old.ru корневой.
            // net.ru/com.ru — зоны второго уровня (kush.net.ru сам по себе корневой), поэтому берём example.ru.
            ['old.ru', 'kush.example.ru', 'hype.example.ru', 'www.plain.com'],
        );
        Assert::same(2, $record['sites']);
        Assert::same(1, $record['doors']);
        Assert::same(1, $record['roots']);
        Assert::same(4, $record['repeats'], 'повторов всего');
        Assert::same(2, $record['repeats_doors'], 'из них доров — два (www не считается)');
        Assert::same(900, $record['base_domains']);
        Assert::same(50.0, CollectHistory::percent($record['doors'], $record['sites']), 'доля доров');
        Assert::false(isset($record['queries']), 'число запросов в статистике не нужно');
        Assert::false(isset($record['filtered']), 'отсев фильтрами в статистике не нужен');
    }

    public function testAppendKeepsNewestFirstAndTotalsAggregate(): void
    {
        $dir = $this->runsDir();
        CollectHistory::append($dir, CollectHistory::record($this->sites('a.ru'), ['base_domains' => 10], ['x.old.ru']));
        CollectHistory::append($dir, CollectHistory::record($this->sites('b.com', 'x.c.com'), ['base_domains' => 12], ['old.com']));

        $records = CollectHistory::load($dir);
        Assert::same(2, count($records));
        Assert::same(2, $records[0]['sites'], 'новая запись — первой');

        $totals = CollectHistory::totals($records);
        Assert::same(2, $totals['runs']);
        Assert::same(3, $totals['sites'], 'домены складываются по всем сборам');
        Assert::same(1, $totals['doors']);
        Assert::same(1, $totals['repeats_doors'], 'повтор-дор был только в первом сборе');
        Assert::same(2, $totals['repeats']);
        Assert::same(33.3, $totals['doors_percent'], 'доля доров от всей массы');
        Assert::same(12, $totals['base_domains'], 'база — размер на момент последнего сбора, а не сумма');
        Assert::same(1, $totals['zones']['com'] ?? 0, 'зона дора x.c.com');
        Assert::same(0, $totals['zones']['ru'] ?? 0, 'корневой a.ru в зоны не попал');
    }

    public function testLoadReadsOldSubdomainsKey(): void
    {
        // Записи версии 1.10.0 звали доры «subdomains» — старая история должна читаться.
        $dir = $this->runsDir();
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([['date' => '2026-09-15T10:00:00+00:00', 'sites' => 5, 'subdomains' => 3]]));
        $records = CollectHistory::load($dir);
        Assert::same(3, $records[0]['doors'], 'старый ключ subdomains читается как doors');
    }

    public function testCsvHasHeaderAndRows(): void
    {
        $csv = CollectHistory::csv([
            CollectHistory::record($this->sites('a.ru', 'sub.b.ru'), ['base_domains' => 50], ['x.old.ru']),
        ]);
        Assert::contains('Собрано доменов', $csv);
        Assert::contains('Доров (поддоменов)', $csv);
        Assert::contains('Зоны доров', $csv);
        Assert::contains('ru: 1', $csv, 'зоны доров сложены в одну колонку');
    }

    public function testLoadOfMissingFileIsEmpty(): void
    {
        Assert::same([], CollectHistory::load($this->dir() . '/нет-такой-папки'));
    }

    public function tearDownClass(): void
    {
        if ($this->dir !== null && is_dir($this->dir)) {
            $it = new \RecursiveIteratorIterator(
                new \RecursiveDirectoryIterator($this->dir, \FilesystemIterator::SKIP_DOTS),
                \RecursiveIteratorIterator::CHILD_FIRST,
            );
            foreach ($it as $item) {
                $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
            }
            @rmdir($this->dir);
        }
    }
}

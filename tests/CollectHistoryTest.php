<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\Site;
use YandexSites\Support\CollectHistory;

/**
 * История сборов для вкладки «Статистика»: что собрано за сбор, сколько повторов, доров и по зонам.
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

    /** @return list<Site> */
    private function sites(string ...$hosts): array
    {
        $out = [];
        foreach ($hosts as $host) {
            $parts = explode('.', $host);
            $domain = count($parts) > 2 ? implode('.', array_slice($parts, -2)) : $host;
            $out[] = new Site($host, $host, $domain); // key, host, регистрируемый домен
        }

        return $out;
    }

    public function testBreakdownCountsSubdomainsAndZones(): void
    {
        $b = CollectHistory::breakdown($this->sites(
            'example.ru',
            'www.second.ru',      // www — тот же корневой домен, не дор
            'kush.casinozsd.buzz', // поддомен — дор
            'hype.casinozsd.buzz',
            'third.com',
        ));
        Assert::same(3, $b['roots'], 'корневых: example.ru, second.ru, third.com');
        Assert::same(2, $b['subdomains'], 'доров на поддоменах: kush. и hype.');
        Assert::same(2, $b['zones']['ru'] ?? 0);
        Assert::same(2, $b['zones']['buzz'] ?? 0);
        Assert::same(1, $b['zones']['com'] ?? 0);
    }

    public function testRecordTakesRepeatsFromRejections(): void
    {
        $record = CollectHistory::record(
            $this->sites('a.ru', 'sub.b.com'),
            ['queries_done' => 12, 'results' => 300, 'base_domains' => 900, 'rejected' => ['seen_before' => 40, 'tld' => 7, 'own_site' => 3]],
        );
        Assert::same(2, $record['sites']);
        Assert::same(40, $record['repeats'], 'повторы — это seen_before');
        Assert::same(10, $record['filtered'], 'остальные отсевы — отдельно от повторов');
        Assert::same(12, $record['queries']);
        Assert::same(900, $record['base_domains']);
        Assert::same(1, $record['subdomains']);
        Assert::same(1, $record['roots']);
    }

    public function testAppendKeepsNewestFirstAndTotalsAggregate(): void
    {
        $dir = $this->dir();
        CollectHistory::append($dir, CollectHistory::record($this->sites('a.ru'), ['base_domains' => 10, 'rejected' => ['seen_before' => 5]]));
        CollectHistory::append($dir, CollectHistory::record($this->sites('b.com', 'x.c.com'), ['base_domains' => 12, 'rejected' => ['seen_before' => 2]]));

        $records = CollectHistory::load($dir);
        Assert::same(2, count($records));
        Assert::same(2, $records[0]['sites'], 'новая запись — первой');

        $totals = CollectHistory::totals($records);
        Assert::same(2, $totals['runs']);
        Assert::same(3, $totals['sites'], 'домены складываются по всем сборам');
        Assert::same(7, $totals['repeats']);
        Assert::same(1, $totals['subdomains']);
        Assert::same(12, $totals['base_domains'], 'база — размер на момент последнего сбора, а не сумма');
        Assert::same(2, $totals['zones']['com'] ?? 0);
        Assert::same(1, $totals['zones']['ru'] ?? 0);
    }

    public function testCsvHasHeaderAndRows(): void
    {
        $csv = CollectHistory::csv([
            CollectHistory::record($this->sites('a.ru', 'sub.b.ru'), ['queries_done' => 3, 'base_domains' => 50, 'rejected' => ['seen_before' => 8]]),
        ]);
        Assert::contains('Собрано доменов', $csv);
        Assert::contains('Поддоменов (доры)', $csv);
        Assert::contains('ru: 2', $csv, 'зоны сложены в одну колонку');
    }

    public function testLoadOfMissingFileIsEmpty(): void
    {
        Assert::same([], CollectHistory::load($this->dir() . '/нет-такой-папки'));
    }

    public function tearDownClass(): void
    {
        if ($this->dir !== null && is_dir($this->dir)) {
            foreach (glob($this->dir . '/*') ?: [] as $file) {
                @unlink($file);
            }
            @rmdir($this->dir);
        }
    }
}

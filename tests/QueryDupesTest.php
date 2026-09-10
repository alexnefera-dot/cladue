<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\SearchResult;
use YandexSites\Output\ReportWriter;
use YandexSites\Support\QueryDupes;

final class QueryDupesTest
{
    public function testFindGroupsQueriesWithSameSiteSetIgnoringPositions(): void
    {
        // q1 и q2 — одни и те же сайты в другом порядке (и www./поддомен того же домена); q3 — другой набор;
        // q5 повторяет q3; q4 без результатов. Порядок списка решает, кто остаётся: q1 и q3.
        $rows = [
            ['q1', 'a.ru'], ['q1', 'www.b.ru'], ['q1', 'c.ru'],
            ['q2', 'c.ru'], ['q2', 'shop.a.ru'], ['q2', 'b.ru'],
            ['q3', 'a.ru'], ['q3', 'b.ru'],
            ['q5', 'b.ru'], ['q5', 'a.ru'],
            ['q4', ''],
        ];
        $found = QueryDupes::find($rows, ['q1', 'q2', 'q3', 'q4', 'q5', '# комментарий', '']);
        Assert::same(4, $found['total'], 'запросов с выдачей');
        Assert::same(['q2', 'q5'], $found['duplicates']);
        Assert::same(['q1', 'q3', 'q4'], $found['unique'], 'без результатов — не дубль, остаётся');
        Assert::same(['q4'], $found['no_results']);
        Assert::same(2, count($found['groups']));
        Assert::same(['kept' => 'q1', 'duplicates' => ['q2'], 'sites' => 3], $found['groups'][0]);
        Assert::same(['kept' => 'q3', 'duplicates' => ['q5'], 'sites' => 2], $found['groups'][1]);
        Assert::same(['total' => 4, 'duplicates' => 2, 'groups' => 2, 'no_results' => 1], QueryDupes::summary($found));

        // Без списка — порядок появления; запрос не из списка добавляется в конец.
        $found = QueryDupes::find($rows, ['q3']);
        Assert::same('q3', $found['groups'][0]['kept'], 'первый по списку остаётся');
        Assert::same(['q3', 'q1', 'q4'], $found['unique']);
        Assert::same([], QueryDupes::find([])['duplicates']);
    }

    public function testCsvRoundTripAndFiles(): void
    {
        // results.csv пишется ReportWriter (BOM, «;»): дубли считаются по нему без нового сбора.
        $dir = sys_get_temp_dir() . '/yandex-sites-qd-' . uniqid();
        mkdir($dir, 0777, true);
        $mk = static fn (string $q, int $pos, string $host): array => ['result' => new SearchResult($q, 0, $pos, "https://$host/", $host, 'Заголовок; с точкой "и кавычкой"'), 'reason' => 'selected'];
        $raw = [$mk('окна', 1, 'a.ru'), $mk('окна', 2, 'b.ru'), $mk('окна купить', 1, 'b.ru'), $mk('окна купить', 2, 'a.ru'), $mk('балконы', 1, 'c.ru')];
        (new ReportWriter(';', true))->writeRawCsv($raw, "$dir/results.csv");
        $fromCsv = QueryDupes::find(QueryDupes::csvRows("$dir/results.csv"), ['окна', 'окна купить', 'балконы', 'пусто']);
        $fromRaw = QueryDupes::find(QueryDupes::rawRows($raw), ['окна', 'окна купить', 'балконы', 'пусто']);
        Assert::same($fromRaw, $fromCsv, 'из csv — то же, что из сырых результатов');
        Assert::same(['окна купить'], $fromCsv['duplicates']);
        Assert::same(['пусто'], $fromCsv['no_results']);
        Assert::same([], iterator_to_array(QueryDupes::csvRows("$dir/nope.csv"), false), 'нет файла — нет строк');

        QueryDupes::writeFiles($dir, $fromCsv);
        Assert::same("окна\nбалконы\nпусто\n", (string) file_get_contents("$dir/" . QueryDupes::UNIQUE_FILE));
        $groups = (string) file_get_contents("$dir/" . QueryDupes::GROUPS_FILE);
        Assert::contains("оставлен: окна (сайтов в выдаче: 2)\n  дубль: окна купить", $groups);
        Assert::contains("# Без результатов в выдаче:\n  пусто", $groups);
    }
}

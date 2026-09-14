<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Search\ApiException;
use YandexSites\Search\BatchFetcherInterface;
use YandexSites\Search\Prefetcher;

final class PrefetcherTest
{
    /**
     * @param array<string, array<int, string|ApiException>> $pages
     */
    private function fetcher(array $pages, array &$calls): BatchFetcherInterface
    {
        return new class($pages, $calls) implements BatchFetcherInterface {
            public function __construct(private array $pages, private array &$calls)
            {
            }

            public function fetch(string $query, int $page): string
            {
                $this->calls[] = ['one' => "$query/$page"];
                $value = $this->pages[$query][$page] ?? new ApiException("нет ответа: $query/$page");
                if ($value instanceof ApiException) {
                    throw $value;
                }

                return $value;
            }

            public function fetchMany(array $requests, int $concurrency = 5): array
            {
                $batch = [];
                $out = [];
                foreach ($requests as $key => $req) {
                    $batch[] = $req['query'] . '/' . $req['page'];
                    $out[$key] = $this->pages[$req['query']][$req['page']] ?? new ApiException('нет ответа');
                }
                $this->calls[] = ['batch' => $batch];

                return $out;
            }
        };
    }

    public function testFetchesQueriesInBatchesAndSecondPageOnlyForFullOnes(): void
    {
        // «full…» — страница полная (нужна следующая), «short…» — последняя.
        $pages = [
            'q1' => [0 => 'full-q1-0', 1 => 'short-q1-1'],
            'q2' => [0 => 'short-q2-0'],
            'q3' => [0 => 'short-q3-0'],
        ];
        $calls = [];
        $pf = new Prefetcher($this->fetcher($pages, $calls), 2, 2, static fn (string $raw): bool => str_starts_with($raw, 'full'));
        $pf->setQueue(['q1', 'q2', 'q3']);

        Assert::same('full-q1-0', $pf->get(0, 'q1', 0));
        Assert::same([
            ['batch' => ['q1/0', 'q2/0']],  // первая страница — пачкой на оба запроса
            ['batch' => ['q1/1']],          // вторая — только там, где первая была полной
        ], $calls, 'лишних обращений к источнику нет');

        Assert::same('short-q1-1', $pf->get(0, 'q1', 1), 'вторая страница уже получена');
        Assert::same('short-q2-0', $pf->get(1, 'q2', 0), 'второй запрос пачки — без обращения к источнику');
        Assert::same(2, count($calls), 'на разбор пачки новых запросов не было');

        Assert::same('short-q3-0', $pf->get(2, 'q3', 0), 'следующая пачка');
        Assert::same(['batch' => ['q3/0']], $calls[2]);
        Assert::same(2, $pf->batch());
    }

    public function testErrorsAndPagesOutsideBatchGoThroughSingleRequests(): void
    {
        $pages = [
            'bad' => [0 => new ApiException('лимит источника')],
            'ok' => [0 => 'full-ok-0', 1 => 'short-ok-1', 2 => 'short-ok-2'],
        ];
        $calls = [];
        $pf = new Prefetcher($this->fetcher($pages, $calls), 2, 2, static fn (string $raw): bool => str_starts_with($raw, 'full'));
        $pf->setQueue(['bad', 'ok']);

        $thrown = null;
        try {
            $pf->get(0, 'bad', 0);
        } catch (ApiException $e) {
            $thrown = $e->getMessage();
        }
        Assert::same('лимит источника', $thrown, 'ошибка пачки доходит до Runner как обычно');

        // Страница за пределами пачки (pages=2, спрашиваем третью) — обычным одиночным запросом.
        Assert::same('short-ok-2', $pf->get(1, 'ok', 2));
        Assert::same(['one' => 'ok/2'], $calls[count($calls) - 1]);
    }
}

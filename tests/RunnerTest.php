<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Runner;
use YandexSites\Search\ApiException;
use YandexSites\Search\RawFetcherInterface;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Support\Logger;

final class RunnerTest
{
    /** @var array<string, string> */
    private array $fixtures = [];

    public function __construct()
    {
        $this->fixtures = [
            'ok' => (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml'),
            'empty' => (string) file_get_contents(TESTS_ROOT . '/fixtures/response_error15.xml'),
        ];
    }

    private function fetcher(array &$log): RawFetcherInterface
    {
        $fixtures = $this->fixtures;

        return new class($fixtures, $log) implements RawFetcherInterface {
            /** @param array<string, string> $fixtures */
            public function __construct(private array $fixtures, private array &$log)
            {
            }

            public function fetch(string $query, int $page): string
            {
                $this->log[] = "$query/$page";
                if (str_contains($query, 'quota')) {
                    throw ApiException::fromYandexCode(32, 'лимит');
                }
                if (str_contains($query, 'broken')) {
                    throw new ApiException('временная ошибка');
                }
                if (str_contains($query, 'nothing') || $page > 0) {
                    return $this->fixtures['empty'];
                }

                return $this->fixtures['ok'];
            }
        };
    }

    private function config(array $extra = []): Config
    {
        return new Config(array_replace_recursive([
            'api' => ['folder_id' => 'f', 'api_key' => 'k'],
            'search' => ['groups_on_page' => 3, 'pages' => 1],
            'filters' => ['exclude_domains' => ['avito.ru'], 'allowed_tlds' => []],
        ], $extra));
    }

    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    public function testCollectsAndFiltersSites(): void
    {
        $calls = [];
        $runner = new Runner($this->config(), $this->fetcher($calls), new XmlResponseParser(), $this->logger());
        $result = $runner->run(['окна', 'балконы', 'nothing here']);

        Assert::same(['окна/0', 'балконы/0', 'nothing here/0'], $calls);
        Assert::false($result->aborted);
        Assert::same([], $result->errors);
        Assert::same(3, $result->stats['queries']);
        Assert::same(3, $result->stats['queries_done']);
        Assert::same(3, $result->stats['requests']);
        Assert::same(8, $result->stats['results']);
        Assert::same(['exclude_domains' => 4], $result->stats['rejected']);
        Assert::same(2, $result->stats['sites_total']);
        Assert::same(2, $result->stats['sites_selected']);
        Assert::same(8, count($result->raw));

        $hosts = array_map(static fn ($s) => $s->host, $result->sites);
        Assert::same(['okna-moskva.ru', 'xn--80aswg.xn--p1ai'], $hosts, 'сортировка: по числу запросов, затем по позиции');
        Assert::same(2, $result->sites[0]->queryCount());
        Assert::same(['окна' => 1, 'балконы' => 1], $result->sites[0]->queries);
    }

    public function testPaginationStopsOnShortPage(): void
    {
        $calls = [];
        $runner = new Runner($this->config(['search' => ['pages' => 3, 'groups_on_page' => 3]]), $this->fetcher($calls), new XmlResponseParser(), $this->logger());
        $runner->run(['окна']);
        Assert::same(['окна/0', 'окна/1'], $calls, 'на второй странице пусто — третья не запрашивается');

        $calls = [];
        $runner = new Runner($this->config(['search' => ['pages' => 3, 'groups_on_page' => 10]]), $this->fetcher($calls), new XmlResponseParser(), $this->logger());
        $runner->run(['окна']);
        Assert::same(['окна/0'], $calls, 'групп меньше, чем запрошено — последняя страница');
    }

    public function testMinQueriesAndFatalErrors(): void
    {
        $calls = [];
        $runner = new Runner($this->config(['filters' => ['min_queries' => 2]]), $this->fetcher($calls), new XmlResponseParser(), $this->logger());
        $result = $runner->run(['окна', 'broken query', 'quota exceeded', 'never reached']);

        Assert::true($result->aborted);
        Assert::same(['окна/0', 'broken query/0', 'quota exceeded/0'], $calls);
        Assert::same(2, count($result->errors));
        Assert::contains('временная ошибка', $result->errors[0]);
        Assert::contains('32', $result->errors[1]);
        Assert::same(1, $result->stats['queries_done'], 'запрос с ошибкой не считается обработанным');
        Assert::same(2, $result->stats['sites_total']);
        Assert::same(0, $result->stats['sites_selected'], 'каждый сайт встретился только в одном запросе');
        Assert::same(2, $result->stats['rejected']['min_queries']);
    }
}

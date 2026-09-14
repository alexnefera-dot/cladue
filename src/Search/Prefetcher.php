<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Забирает выдачу ПАЧКАМИ вперёд: пока Runner разбирает один запрос, ответы следующих уже получены
 * параллельно. Логика Runner при этом не меняется — он спрашивает ответ по (запрос, страница), а
 * пачка тянется ровно тогда, когда нужного ответа ещё нет.
 *
 * Лишних обращений к источнику не делаем: страница N+1 запрашивается только для тех запросов пачки,
 * у которых страница N оказалась полной ($shouldContinue — то же правило, что и у Runner).
 */
final class Prefetcher
{
    /** @var array<string, string|ApiException> ответ или ошибка по ключу «запрос\страница» */
    private array $store = [];

    /** @var list<string> */
    private array $queries = [];

    private int $primedTo = 0;

    /**
     * @param positive-int $batch сколько запросов тянуть параллельно
     * @param positive-int $pages сколько страниц максимум у запроса
     * @param callable(string, int, string): bool $shouldContinue нужно ли тянуть следующую страницу по этому ответу
     */
    public function __construct(
        private BatchFetcherInterface $fetcher,
        private int $batch,
        private int $pages,
        private $shouldContinue,
    ) {
    }

    /**
     * @param list<string> $queries весь список запросов прогона (в порядке обработки)
     */
    public function setQueue(array $queries): void
    {
        $this->queries = array_values($queries);
        $this->primedTo = 0;
        $this->store = [];
    }

    /**
     * Ответ по запросу: из уже полученной пачки, иначе тянем следующую пачку начиная с $index.
     *
     * @throws ApiException
     */
    public function get(int $index, string $query, int $page): string
    {
        $key = $this->key($query, $page);
        if (!array_key_exists($key, $this->store) && $page === 0) {
            $this->prime($index);
        }
        if (!array_key_exists($key, $this->store)) {
            return $this->fetcher->fetch($query, $page); // страница вне пачки — обычным путём
        }
        $value = $this->store[$key];
        unset($this->store[$key]); // ответ отдан — память не держим
        if ($value instanceof ApiException) {
            throw $value;
        }

        return $value;
    }

    /** Сколько запросов тянется за раз. */
    public function batch(): int
    {
        return $this->batch;
    }

    private function prime(int $index): void
    {
        $index = max($index, $this->primedTo);
        $chunk = array_slice($this->queries, $index, $this->batch, true);
        if ($chunk === []) {
            return;
        }
        $this->primedTo = $index + count($chunk);

        $pending = $chunk;
        for ($page = 0; $page < $this->pages && $pending !== []; $page++) {
            $requests = [];
            foreach ($pending as $i => $query) {
                $requests[$i] = ['query' => $query, 'page' => $page];
            }
            $results = $this->fetcher->fetchMany($requests, $this->batch);
            $next = [];
            foreach ($pending as $i => $query) {
                $value = $results[$i] ?? new ApiException('Нет ответа');
                $this->store[$this->key($query, $page)] = $value;
                if (is_string($value) && ($this->shouldContinue)($value, $page, $query)) {
                    $next[$i] = $query;
                }
            }
            $pending = $next;
        }
    }

    private function key(string $query, int $page): string
    {
        return $query . "\t" . $page;
    }
}

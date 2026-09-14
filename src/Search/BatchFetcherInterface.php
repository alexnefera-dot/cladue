<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Источник, умеющий брать НЕСКОЛЬКО запросов выдачи разом (параллельно). Сбор большого списка ключей
 * по одному запросу за раз упирался в сеть: 3000 ключей подряд — часы ожидания. Живая выдача через
 * прокси этот интерфейс не реализует: там важен строгий порядок и паузы между заходами.
 */
interface BatchFetcherInterface extends RawFetcherInterface
{
    /**
     * @param array<array-key, array{query: string, page: int}> $requests
     * @return array<array-key, string|ApiException> ответ или ошибка по тем же ключам
     */
    public function fetchMany(array $requests, int $concurrency = 5): array;
}

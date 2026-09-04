<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Источник сырой выдачи по запросу и номеру страницы (0 — первая):
 * XML для API и XMLStock, HTML для живой выдачи.
 */
interface RawFetcherInterface
{
    /**
     * @return string сырой ответ, уже проверенный на ошибки (капча, коды ошибок API)
     *
     * @throws ApiException
     */
    public function fetch(string $query, int $page): string;
}

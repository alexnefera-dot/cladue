<?php

declare(strict_types=1);

namespace YandexSites\Search;

use YandexSites\Model\SearchPage;

/**
 * Разбор сырого ответа источника в страницу выдачи.
 */
interface ResponseParserInterface
{
    /**
     * @param int $positionOffset число результатов на предыдущих страницах (для сквозной нумерации позиций)
     *
     * @throws ApiException
     */
    public function parse(string $raw, string $query, int $page, int $positionOffset = 0): SearchPage;
}

<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Источник XML-выдачи по запросу и номеру страницы (0 — первая).
 */
interface XmlFetcherInterface
{
    /**
     * @return string XML-ответ Яндекса (без ошибок, кроме кода 15 «ничего не найдено»)
     *
     * @throws ApiException
     */
    public function fetch(string $query, int $page): string;
}

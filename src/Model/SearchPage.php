<?php

declare(strict_types=1);

namespace YandexSites\Model;

/**
 * Одна страница выдачи по запросу.
 */
final class SearchPage
{
    /**
     * @param list<SearchResult> $results
     * @param bool|null $hasMore есть ли следующая страница (null — неизвестно, решает вызывающий код)
     */
    public function __construct(
        public readonly string $query,
        public readonly int $page,
        public readonly ?int $found,
        public readonly int $groups,
        public readonly array $results,
        public readonly ?bool $hasMore = null,
    ) {
    }
}

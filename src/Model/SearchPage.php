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
     */
    public function __construct(
        public readonly string $query,
        public readonly int $page,
        public readonly ?int $found,
        public readonly int $groups,
        public readonly array $results,
    ) {
    }
}

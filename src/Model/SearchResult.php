<?php

declare(strict_types=1);

namespace YandexSites\Model;

/**
 * Один документ из поисковой выдачи.
 */
final class SearchResult
{
    public function __construct(
        public readonly string $query,
        public readonly int $page,
        public readonly int $position,
        public readonly string $url,
        public readonly string $host,
        public readonly string $title,
        public readonly string $headline = '',
        public readonly string $snippet = '',
        public readonly string $modtime = '',
    ) {
    }

    /**
     * Весь текст сниппета (заголовок + описание + пассажи) для проверки по словам.
     */
    public function text(): string
    {
        return implode(' ', array_filter([$this->title, $this->headline, $this->snippet], static fn (string $s): bool => $s !== ''));
    }
}

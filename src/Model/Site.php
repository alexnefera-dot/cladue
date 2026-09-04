<?php

declare(strict_types=1);

namespace YandexSites\Model;

use YandexSites\Filter\Domains;

/**
 * Сайт, собранный из результатов по всем запросам.
 */
final class Site
{
    public int $hits = 0;
    public ?int $bestPosition = null;
    public string $bestUrl = '';
    public string $bestTitle = '';
    public string $bestQuery = '';

    /** @var array<string, int> запрос => лучшая позиция по этому запросу */
    public array $queries = [];

    /** @var array<string, true> все найденные URL */
    public array $urls = [];

    /** @var array<string, mixed> результат проверки сайта (если включена) */
    public array $check = [];

    public function __construct(
        public readonly string $key,
        public readonly string $host,
        public readonly string $domain,
    ) {
    }

    public function add(SearchResult $result): void
    {
        $this->hits++;
        $this->urls[$result->url] = true;

        if (!isset($this->queries[$result->query]) || $result->position < $this->queries[$result->query]) {
            $this->queries[$result->query] = $result->position;
        }

        if ($this->bestPosition === null || $result->position < $this->bestPosition) {
            $this->bestPosition = $result->position;
            $this->bestUrl = $result->url;
            $this->bestTitle = $result->title;
            $this->bestQuery = $result->query;
        }
    }

    public function queryCount(): int
    {
        return count($this->queries);
    }

    /**
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        return [
            'host' => $this->host,
            'host_unicode' => Domains::toUnicode($this->host),
            'domain' => $this->domain,
            'url' => $this->bestUrl,
            'title' => $this->bestTitle,
            'best_position' => $this->bestPosition,
            'best_query' => $this->bestQuery,
            'queries_count' => $this->queryCount(),
            'hits' => $this->hits,
            'queries' => $this->queries,
            'urls' => array_keys($this->urls),
            'check' => $this->check,
        ];
    }
}

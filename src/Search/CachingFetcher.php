<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Кэширует XML-ответы на диске, чтобы повторные запуски (например, с другими
 * фильтрами) не тратили лимит API.
 */
final class CachingFetcher implements XmlFetcherInterface
{
    public int $hits = 0;
    public int $misses = 0;

    /**
     * @param array<string, mixed> $keyParts параметры поиска, влияющие на ответ (регион, группировка и т. п.)
     */
    public function __construct(
        private XmlFetcherInterface $inner,
        private string $dir,
        private int $ttl,
        private array $keyParts = [],
        private bool $offline = false,
    ) {
    }

    public function fetch(string $query, int $page): string
    {
        $file = $this->path($query, $page);
        if ($this->isFresh($file)) {
            $xml = file_get_contents($file);
            if ($xml !== false && $xml !== '') {
                $this->hits++;

                return $xml;
            }
        }

        if ($this->offline) {
            throw new ApiException(sprintf('Нет в кэше (режим offline): «%s», страница %d', $query, $page + 1));
        }

        $xml = $this->inner->fetch($query, $page);
        $this->misses++;
        $this->store($file, $xml);

        return $xml;
    }

    public function has(string $query, int $page): bool
    {
        return $this->isFresh($this->path($query, $page));
    }

    private function isFresh(string $file): bool
    {
        if (!is_file($file)) {
            return false;
        }

        return $this->ttl <= 0 || (filemtime($file) ?: 0) >= time() - $this->ttl;
    }

    private function store(string $file, string $xml): void
    {
        $dir = dirname($file);
        if (!is_dir($dir) && !@mkdir($dir, 0777, true) && !is_dir($dir)) {
            return;
        }
        @file_put_contents($file, $xml, LOCK_EX);
    }

    private function path(string $query, int $page): string
    {
        $key = sha1(json_encode([$this->keyParts, mb_strtolower(trim($query)), $page], JSON_UNESCAPED_UNICODE) ?: '');

        return $this->dir . '/' . substr($key, 0, 2) . '/' . $key . '.xml';
    }
}

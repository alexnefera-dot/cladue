<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Кэширует XML-ответы на диске, чтобы повторные запуски (например, с другими
 * фильтрами) не тратили лимит API.
 */
final class CachingFetcher implements BatchFetcherInterface
{
    public int $hits = 0;
    public int $misses = 0;

    /**
     * @param array<string, mixed> $keyParts параметры поиска, влияющие на ответ (регион, группировка и т. п.)
     */
    public function __construct(
        private RawFetcherInterface $inner,
        private string $dir,
        private int $ttl,
        private array $keyParts = [],
        private bool $offline = false,
        private string $extension = 'xml',
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

    /**
     * Пачка запросов: что есть в кэше — отдаём сразу, остальное тянем у источника параллельно.
     *
     * @param array<array-key, array{query: string, page: int}> $requests
     * @return array<array-key, string|ApiException>
     */
    public function fetchMany(array $requests, int $concurrency = 5): array
    {
        $out = [];
        $miss = [];
        foreach ($requests as $key => $req) {
            $file = $this->path((string) $req['query'], (int) $req['page']);
            $xml = $this->isFresh($file) ? file_get_contents($file) : false;
            if ($xml !== false && $xml !== '') {
                $this->hits++;
                $out[$key] = $xml;
                continue;
            }
            if ($this->offline) {
                $out[$key] = new ApiException(sprintf('Нет в кэше (режим offline): «%s», страница %d', $req['query'], (int) $req['page'] + 1));
                continue;
            }
            $miss[$key] = $req;
        }
        if ($miss !== []) {
            $fetched = $this->inner instanceof BatchFetcherInterface
                ? $this->inner->fetchMany($miss, $concurrency)
                : $this->one($miss);
            foreach ($miss as $key => $req) {
                $value = $fetched[$key] ?? new ApiException('Нет ответа');
                if (is_string($value)) {
                    $this->misses++;
                    $this->store($this->path((string) $req['query'], (int) $req['page']), $value);
                }
                $out[$key] = $value;
            }
        }

        $ordered = [];
        foreach ($requests as $key => $_) {
            $ordered[$key] = $out[$key] ?? new ApiException('Нет ответа');
        }

        return $ordered;
    }

    /**
     * @param array<array-key, array{query: string, page: int}> $requests
     * @return array<array-key, string|ApiException>
     */
    private function one(array $requests): array
    {
        $out = [];
        foreach ($requests as $key => $req) {
            try {
                $out[$key] = $this->inner->fetch((string) $req['query'], (int) $req['page']);
            } catch (ApiException $e) {
                $out[$key] = $e;
            }
        }

        return $out;
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

        return $this->dir . '/' . substr($key, 0, 2) . '/' . $key . '.' . $this->extension;
    }
}

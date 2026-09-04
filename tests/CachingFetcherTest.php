<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Search\ApiException;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\RawFetcherInterface;

final class CachingFetcherTest
{
    private function inner(int &$calls): RawFetcherInterface
    {
        return new class($calls) implements RawFetcherInterface {
            public function __construct(private int &$calls)
            {
            }

            public function fetch(string $query, int $page): string
            {
                $this->calls++;

                return "<yandexsearch><response><reqid>$query-$page-{$this->calls}</reqid></response></yandexsearch>";
            }
        };
    }

    private function dir(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-cache-' . uniqid();
        mkdir($dir);

        return $dir;
    }

    public function testHitsAndMisses(): void
    {
        $calls = 0;
        $dir = $this->dir();
        $cache = new CachingFetcher($this->inner($calls), $dir, 3600, ['region' => 213]);

        Assert::false($cache->has('окна', 0));
        $first = $cache->fetch('окна', 0);
        Assert::true($cache->has('окна', 0));
        Assert::same($first, $cache->fetch('ОКНА', 0), 'регистр запроса не влияет на ключ');
        Assert::same(1, $calls);
        Assert::same(1, $cache->hits);
        Assert::same(1, $cache->misses);

        $cache->fetch('окна', 1);
        Assert::same(2, $calls, 'другая страница — другой ключ');

        $other = new CachingFetcher($this->inner($calls), $dir, 3600, ['region' => 2]);
        $other->fetch('окна', 0);
        Assert::same(3, $calls, 'другие параметры поиска — другой ключ');
        $this->cleanup($dir);
    }

    public function testTtlAndOffline(): void
    {
        $calls = 0;
        $dir = $this->dir();
        $cache = new CachingFetcher($this->inner($calls), $dir, 10, []);
        $cache->fetch('q', 0);
        foreach (glob($dir . '/*/*.xml') ?: [] as $file) {
            touch($file, time() - 60);
        }
        Assert::false($cache->has('q', 0), 'просроченная запись не считается');
        $cache->fetch('q', 0);
        Assert::same(2, $calls);

        $forever = new CachingFetcher($this->inner($calls), $dir, 0, []);
        foreach (glob($dir . '/*/*.xml') ?: [] as $file) {
            touch($file, time() - 86400 * 365);
        }
        Assert::true($forever->has('q', 0), 'ttl=0 — бессрочно');

        $offline = new CachingFetcher($this->inner($calls), $dir, 0, [], true);
        $offline->fetch('q', 0);
        Assert::same(2, $calls);
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $offline->fetch('not cached', 0), 'offline');
        Assert::false($e->isFatal());
        $this->cleanup($dir);
    }

    private function cleanup(string $dir): void
    {
        foreach (glob($dir . '/*/*.xml') ?: [] as $file) {
            unlink($file);
        }
        foreach (glob($dir . '/*', GLOB_ONLYDIR) ?: [] as $sub) {
            rmdir($sub);
        }
        rmdir($dir);
    }
}

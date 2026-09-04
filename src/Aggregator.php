<?php

declare(strict_types=1);

namespace YandexSites;

use YandexSites\Filter\Domains;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;

/**
 * Собирает прошедшие фильтры результаты в сайты (по хосту или по домену).
 */
final class Aggregator
{
    /** @var array<string, Site> */
    private array $sites = [];

    public function __construct(
        private string $uniqueBy = 'host',
        private bool $stripWww = true,
    ) {
    }

    public function add(SearchResult $result): Site
    {
        $host = Domains::normalize($result->host !== '' ? $result->host : Domains::hostFromUrl($result->url), $this->stripWww);
        $domain = Domains::registrable($host);
        $key = $this->uniqueBy === 'domain' ? $domain : $host;

        $site = $this->sites[$key] ??= new Site($key, $this->uniqueBy === 'domain' ? $domain : $host, $domain);
        $site->add($result);

        return $site;
    }

    /**
     * @return array<string, Site>
     */
    public function sites(): array
    {
        return $this->sites;
    }
}

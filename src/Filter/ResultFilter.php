<?php

declare(strict_types=1);

namespace YandexSites\Filter;

use YandexSites\Model\SearchResult;

/**
 * Правила отбора отдельных результатов выдачи (раздел `filters` конфигурации).
 * Метод reject() возвращает код причины отклонения или null, если результат подходит.
 */
final class ResultFilter
{
    private ?int $maxPosition;
    private string $domainScope;
    private DomainMatcher $include;
    private DomainMatcher $exclude;
    /** @var list<string> */
    private array $tlds;
    private TextMatcher $urlMust;
    private TextMatcher $urlMustNot;
    private TextMatcher $titleAny;
    private TextMatcher $titleAll;
    private TextMatcher $titleNone;
    private TextMatcher $snippetAny;
    private TextMatcher $snippetNone;

    /**
     * @param array<string, mixed> $cfg
     */
    public function __construct(array $cfg)
    {
        $max = (int) ($cfg['max_position'] ?? 0);
        $this->maxPosition = $max > 0 ? $max : null;

        $scope = (string) ($cfg['domain_scope'] ?? 'all');
        $this->domainScope = in_array($scope, ['all', 'root', 'subdomain'], true) ? $scope : 'all';

        $this->include = new DomainMatcher($cfg['include_domains'] ?? []);
        $this->exclude = new DomainMatcher($cfg['exclude_domains'] ?? []);

        $this->tlds = [];
        foreach ((array) ($cfg['allowed_tlds'] ?? []) as $tld) {
            $tld = mb_strtolower(ltrim(trim((string) $tld), '.'));
            if ($tld !== '') {
                $this->tlds[] = Domains::tld('x.' . $tld);
            }
        }

        $this->urlMust = new TextMatcher($cfg['url_must_match'] ?? [], true, 'filters.url_must_match');
        $this->urlMustNot = new TextMatcher($cfg['url_must_not_match'] ?? [], true, 'filters.url_must_not_match');
        $this->titleAny = new TextMatcher($cfg['title_any'] ?? [], false, 'filters.title_any');
        $this->titleAll = new TextMatcher($cfg['title_all'] ?? [], false, 'filters.title_all');
        $this->titleNone = new TextMatcher($cfg['title_none'] ?? [], false, 'filters.title_none');
        $this->snippetAny = new TextMatcher($cfg['snippet_any'] ?? [], false, 'filters.snippet_any');
        $this->snippetNone = new TextMatcher($cfg['snippet_none'] ?? [], false, 'filters.snippet_none');
    }

    /**
     * @return string|null код причины отклонения или null, если результат подходит
     */
    public function reject(SearchResult $result): ?string
    {
        if ($this->maxPosition !== null && $result->position > $this->maxPosition) {
            return 'position';
        }

        $host = Domains::normalize($result->host !== '' ? $result->host : Domains::hostFromUrl($result->url));
        if ($host === '') {
            return 'no_host';
        }
        if (!$this->include->isEmpty() && !$this->include->matches($host)) {
            return 'include_domains';
        }
        if ($this->exclude->matches($host)) {
            return 'exclude_domains';
        }
        if ($this->tlds !== [] && !in_array(Domains::tld($host), $this->tlds, true)) {
            return 'tld';
        }
        if ($this->domainScope !== 'all') {
            $isRoot = Domains::registrable($host) === $host;
            if (($this->domainScope === 'root' && !$isRoot) || ($this->domainScope === 'subdomain' && $isRoot)) {
                return 'domain_scope';
            }
        }
        if (!$this->urlMust->isEmpty() && !$this->urlMust->matchesAll($result->url)) {
            return 'url_must_match';
        }
        if (!$this->urlMustNot->isEmpty() && $this->urlMustNot->matchesAny($result->url)) {
            return 'url_must_not_match';
        }
        if (!$this->titleAny->isEmpty() && !$this->titleAny->matchesAny($result->title)) {
            return 'title_any';
        }
        if (!$this->titleAll->isEmpty() && !$this->titleAll->matchesAll($result->title)) {
            return 'title_all';
        }
        if (!$this->titleNone->isEmpty() && $this->titleNone->matchesAny($result->title)) {
            return 'title_none';
        }

        $text = $result->text();
        if (!$this->snippetAny->isEmpty() && !$this->snippetAny->matchesAny($text)) {
            return 'snippet_any';
        }
        if (!$this->snippetNone->isEmpty() && $this->snippetNone->matchesAny($text)) {
            return 'snippet_none';
        }

        return null;
    }
}

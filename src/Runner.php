<?php

declare(strict_types=1);

namespace YandexSites;

use YandexSites\Check\SiteChecker;
use YandexSites\Filter\ResultFilter;
use YandexSites\Model\Site;
use YandexSites\Search\ApiException;
use YandexSites\Search\XmlFetcherInterface;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Support\Logger;

/**
 * Основной конвейер: запросы → выдача → фильтры → сайты → проверка → результат.
 */
final class Runner
{
    public function __construct(
        private Config $config,
        private XmlFetcherInterface $fetcher,
        private XmlResponseParser $parser,
        private Logger $log,
        private ?SiteChecker $checker = null,
    ) {
    }

    /**
     * @param list<string> $queries
     */
    public function run(array $queries): RunResult
    {
        $result = new RunResult();
        $result->stats['queries'] = count($queries);

        $filter = new ResultFilter((array) $this->config->get('filters'));
        $aggregator = new Aggregator(
            (string) $this->config->get('filters.unique_by', 'host'),
            (bool) $this->config->get('filters.strip_www', true),
        );
        $pages = max(1, (int) $this->config->get('search.pages', 1));
        $groupsOnPage = max(1, (int) $this->config->get('search.groups_on_page', 10));

        foreach ($queries as $index => $query) {
            $this->log->info(sprintf('[%d/%d] %s', $index + 1, count($queries), $query));

            for ($page = 0; $page < $pages; $page++) {
                try {
                    $xml = $this->fetcher->fetch($query, $page);
                    $result->stats['requests']++;
                    $searchPage = $this->parser->parse($xml, $query, $page);
                } catch (ApiException $e) {
                    $result->errors[] = sprintf('«%s» (стр. %d): %s', $query, $page + 1, $e->getMessage());
                    if ($e->isFatal()) {
                        $this->log->error($e->getMessage());
                        $this->log->error('Работа остановлена; результаты по уже обработанным запросам будут сохранены.');
                        $result->aborted = true;
                        break 2;
                    }
                    $this->log->warn($e->getMessage());
                    break;
                }

                $count = count($searchPage->results);
                $result->stats['results'] += $count;
                $this->log->debug(sprintf(
                    '  стр. %d: %d результатов%s',
                    $page + 1,
                    $count,
                    $searchPage->found !== null ? ', всего найдено ' . $searchPage->found : '',
                ));

                foreach ($searchPage->results as $item) {
                    $reason = $filter->reject($item);
                    $result->raw[] = ['result' => $item, 'reason' => $reason];
                    if ($reason !== null) {
                        $result->reject($reason);
                        continue;
                    }
                    $aggregator->add($item);
                }

                if ($count === 0 || $searchPage->groups < $groupsOnPage) {
                    break;
                }
            }

            $result->stats['queries_done']++;
        }

        $sites = $aggregator->sites();
        $result->stats['sites_total'] = count($sites);

        $minQueries = max(1, (int) $this->config->get('filters.min_queries', 1));
        $minHits = max(1, (int) $this->config->get('filters.min_hits', 1));
        foreach ($sites as $key => $site) {
            if ($site->queryCount() < $minQueries) {
                $result->reject('min_queries');
                unset($sites[$key]);
            } elseif ($site->hits < $minHits) {
                $result->reject('min_hits');
                unset($sites[$key]);
            }
        }

        if ($this->checker !== null && $sites !== []) {
            $this->log->info(sprintf('Проверка %d сайтов по HTTP…', count($sites)));
            $checks = $this->checker->check($sites);
            foreach ($sites as $key => $site) {
                $check = $checks[$key] ?? null;
                if ($check === null) {
                    continue;
                }
                $site->check = $check->toArray();
                if (!$check->ok) {
                    $result->reject('site_check:' . $check->reason);
                    unset($sites[$key]);
                }
            }
        }

        $sites = array_values($sites);
        usort($sites, static function (Site $a, Site $b): int {
            return [$b->queryCount(), $a->bestPosition ?? PHP_INT_MAX, $b->hits, $a->host]
                <=> [$a->queryCount(), $b->bestPosition ?? PHP_INT_MAX, $a->hits, $b->host];
        });

        $result->sites = $sites;
        $result->stats['sites_selected'] = count($sites);

        return $result;
    }
}

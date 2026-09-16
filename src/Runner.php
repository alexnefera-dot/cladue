<?php

declare(strict_types=1);

namespace YandexSites;

use YandexSites\Check\SiteChecker;
use YandexSites\Filter\Domains;
use YandexSites\Filter\ResultFilter;
use YandexSites\Model\Site;
use YandexSites\Search\ApiException;
use YandexSites\Search\BatchFetcherInterface;
use YandexSites\Search\Prefetcher;
use YandexSites\Search\RawFetcherInterface;
use YandexSites\Search\ResponseParserInterface;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\DomainLedger;
use YandexSites\Support\Logger;
use YandexSites\Visit\PageVisitor;

/**
 * Основной конвейер: запросы → выдача → фильтры → сайты → проверка → результат.
 */
final class Runner
{
    public function __construct(
        private Config $config,
        private RawFetcherInterface $fetcher,
        private ResponseParserInterface $parser,
        private Logger $log,
        private ?SiteChecker $checker = null,
        private ?PageVisitor $visitor = null,
        private mixed $onProgress = null,
        private ?DomainLedger $ledger = null,
        private bool $skipKnownDomains = false,
        private mixed $shouldStop = null,
        private mixed $onSelected = null,
    ) {
    }

    /**
     * @param array<string, mixed> $event
     */
    private function progress(array $event): void
    {
        if ($this->onProgress !== null) {
            ($this->onProgress)($event);
        }
    }

    /**
     * @param list<string> $queries
     */
    public function run(array $queries): RunResult
    {
        $result = new RunResult();
        $result->stats['queries'] = count($queries);

        $filtersCfg = (array) $this->config->get('filters');
        $filtersCfg['own_markers'] = \YandexSites\Filter\OwnSites::fromConfig($this->config)->markers();
        $filter = new ResultFilter($filtersCfg);
        /** @var array<string, true> уникальные домены и поддомены из выдачи (см. цикл по результатам) */
        $seenHosts = [];
        /**
         * То же самое, но СГРУППИРОВАННОЕ так же, как группирует Aggregator («один сайт на домен»):
         * все доры одной сетки — это один сайт, а не десять. Именно от этого числа считается, сколько
         * в выдаче доров и сколько срезали фильтры, иначе воронка не сходится (6460 адресов → 602 сайта).
         *
         * @var array<string, true>
         */
        $seenKeys = [];
        $uniqueBy = (string) $this->config->get('filters.unique_by', 'host');
        $stripWww = (bool) $this->config->get('filters.strip_www', true);
        $result->stats['unique_by'] = $uniqueBy; // как группировать выдачу в статистике сбора
        $aggregator = new Aggregator($uniqueBy, $stripWww);
        $pages = max(1, (int) $this->config->get('search.pages', 1));
        $groupsOnPage = max(1, (int) $this->config->get('search.groups_on_page', 10));
        if ((string) $this->config->get('source') === 'xmlstock' && (string) $this->config->get('xmlstock.mode', 'xml') === 'live') {
            // Живая выдача через XMLStock: на странице не больше 10 результатов независимо от groups_on_page
            $groupsOnPage = XmlStockFetcher::LIVE_PAGE_SIZE;
        }
        $maxErrors = max(0, (int) $this->config->get('search.max_consecutive_errors', 0));
        $consecutiveErrors = 0;
        // Выдачу тянем пачками параллельно: пока разбираем один запрос, ответы следующих уже получены.
        // Лишних обращений нет — следующая страница запрашивается по тому же правилу, что и ниже в цикле.
        $batch = max(1, (int) $this->config->get('search.concurrency', 1));
        $prefetch = null;
        if ($batch > 1 && count($queries) > 1 && $this->fetcher instanceof BatchFetcherInterface) {
            $prefetch = new Prefetcher($this->fetcher, $batch, $pages, function (string $raw, int $page, string $query) use ($groupsOnPage): bool {
                $parsed = $this->parser->parse($raw, $query, $page, 0);
                $lastPage = $parsed->hasMore === false
                    || ($parsed->hasMore === null && $parsed->groups < $groupsOnPage);

                return $parsed->results !== [] && !$lastPage;
            });
            $prefetch->setQueue(array_values($queries));
            $this->log->info(sprintf('Запросы к источнику идут пачками по %d параллельно', $batch));
        }
        $this->progress(['phase' => 'search', 'queries_total' => count($queries), 'queries_done' => 0]);

        foreach ($queries as $index => $query) {
            // Остановка по кнопке — между запросами: текущий запрос доводим до конца, недоделанных
            // «половинок» в выдаче не остаётся, и продолжить можно ровно со следующего запроса.
            if ($this->shouldStop !== null && ($this->shouldStop)()) {
                $result->stopped = true;
                $this->log->info(sprintf('Остановка: обработано %d из %d запросов, собранное сохраняем', $index, count($queries)));
                break;
            }
            $this->log->info(sprintf('[%d/%d] %s', $index + 1, count($queries), $query));
            $offset = 0;
            $failed = false;

            for ($page = 0; $page < $pages; $page++) {
                try {
                    $raw = $prefetch !== null ? $prefetch->get($index, $query, $page) : $this->fetcher->fetch($query, $page);
                    $result->stats['requests']++;
                    $searchPage = $this->parser->parse($raw, $query, $page, $offset);
                } catch (ApiException $e) {
                    $result->errors[] = sprintf('«%s» (стр. %d): %s', $query, $page + 1, $e->getMessage());
                    $failed = true;
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
                $offset += $count;
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
                    // Сколько РАЗНЫХ доменов и поддоменов встретилось в выдаче: результатов в разы
                    // больше (один сайт попадается в десятках запросов), и без этого числа панель
                    // сравнивала несравнимое — «29 904 результата» и «2 043 сайта после фильтров».
                    $seenHost = Domains::normalize($item->host !== '' ? $item->host : Domains::hostFromUrl($item->url), $stripWww);
                    if ($seenHost !== '') {
                        $seenHosts[$seenHost] = true;
                        // Ключ группировки — тот же, что у Aggregator: при «один сайт на домен» это
                        // регистрируемый домен, и поддомены одной сетки складываются в один сайт.
                        $seenKeys[$uniqueBy === 'domain' ? Domains::registrable($seenHost) : $seenHost] = true;
                    }
                    $this->log->debug(sprintf(
                        '  %4d. %-32s %s%s',
                        $item->position,
                        mb_substr($item->host, 0, 32),
                        mb_substr($item->title, 0, 70),
                        $reason !== null ? '  [' . $reason . ']' : '',
                    ));
                    if ($reason !== null) {
                        $result->reject($reason);
                        continue;
                    }
                    $aggregator->add($item);
                }

                $lastPage = $searchPage->hasMore === false
                    || ($searchPage->hasMore === null && $searchPage->groups < $groupsOnPage);
                if ($count === 0 || $lastPage) {
                    break;
                }
            }

            // Запрос пройден (даже если с ошибкой — иначе продолжение зациклится на нём).
            $result->processed = $index + 1;

            if ($failed) {
                $consecutiveErrors++;
                if ($maxErrors > 0 && $consecutiveErrors >= $maxErrors && !$result->aborted) {
                    $this->log->error(sprintf('%d запросов подряд завершились ошибкой — работа остановлена.', $consecutiveErrors));
                    $result->aborted = true;
                    break;
                }
                continue;
            }
            $consecutiveErrors = 0;
            $result->stats['queries_done']++;
            $this->progress([
                'phase' => 'search',
                'queries_total' => count($queries),
                'queries_done' => $index + 1,
                'current_query' => $query,
                'results' => $result->stats['results'],
                'hosts_total' => count($seenHosts),
                'unique_sites' => count($seenKeys),
                'sites_total' => count($aggregator->sites()),
                'rejected' => $result->stats['rejected'],
                'error_count' => count($result->errors),
            ]);
        }

        $sites = $aggregator->sites();
        $result->stats['hosts_total'] = count($seenHosts);
        $result->stats['unique_sites'] = count($seenKeys);
        $result->stats['sites_total'] = count($sites);
        $this->progress(['phase' => 'filter', 'hosts_total' => count($seenHosts), 'unique_sites' => count($seenKeys), 'sites_total' => count($sites)]);

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

        if ($this->ledger !== null) {
            if ($this->skipKnownDomains) {
                foreach ($sites as $key => $site) {
                    if ($this->ledger->has($site->domain)) {
                        $result->reject('seen_before');
                        // Для статистики: повтор был дором или корневым? realHost() — потому что при
                        // дедупе по домену $site->host хранит регистрируемый домен, а не хост.
                        $result->seenBefore[] = $site->realHost();
                        unset($sites[$key]);
                    }
                }
            }
            $added = $this->ledger->add(array_map(static fn (Site $s): string => $s->domain, $sites));
            $result->stats['new_domains'] = $added;
            $result->stats['base_domains'] = $this->ledger->count();
            $this->progress(['phase' => 'filter', 'sites_total' => count($sites), 'new_domains' => $added, 'base_domains' => $this->ledger->count()]);
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

        // Домены отобраны и проверены — отдаём их СРАЗУ, до прохода по сайтам со скриншотами: обход
        // сотен сайтов идёт долго, а статистика сбора (сколько доменов, сколько доров, зоны) уже готова
        // и не должна ждать его конца. Задание дописывает её в историю прямо здесь.
        if ($this->onSelected !== null) {
            ($this->onSelected)(array_values($sites), $result);
        }

        if ($this->visitor !== null && $sites !== []) {
            $this->progress(['phase' => 'visit', 'sites_selected' => count($sites)]);
            $this->visitor->visit($sites);
        }

        $sites = array_values($sites);
        usort($sites, static function (Site $a, Site $b): int {
            return [$b->queryCount(), $a->bestPosition ?? PHP_INT_MAX, $b->hits, $a->host]
                <=> [$a->queryCount(), $b->bestPosition ?? PHP_INT_MAX, $a->hits, $b->host];
        });

        $result->sites = $sites;
        $result->stats['sites_selected'] = count($sites);
        $this->progress(['phase' => 'done', 'sites_selected' => count($sites), 'sites_total' => $result->stats['sites_total']]);

        return $result;
    }
}

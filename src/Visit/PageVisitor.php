<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Filter\Domains;
use YandexSites\Filter\OwnSites;
use YandexSites\Live\Proxy;
use YandexSites\Live\ProxyPool;
use YandexSites\Live\UserAgents;
use YandexSites\Model\Site;
use YandexSites\Support\Logger;

/**
 * Заходит на отобранные сайты как посетитель из поиска (с Referer выдачи Яндекса),
 * сохраняет HTML и скриншоты. Несколько вариантов на сайт — через разные прокси
 * и User-Agent, чтобы увидеть, показывает ли сайт разным посетителям разное.
 */
final class PageVisitor
{
    /** @var list<string> */
    private array $userAgents;

    private OwnSites $ownSites;

    /**
     * @param array<string, mixed> $cfg раздел `visit` конфигурации
     */
    public function __construct(
        private array $cfg,
        private DriverInterface $driver,
        private Logger $log,
        private ?ProxyPool $proxies = null,
        private string $searchBaseUrl = 'https://yandex.ru',
        private string $region = '',
        private mixed $onProgress = null,
    ) {
        $agents = array_values(array_filter((array) ($cfg['user_agents'] ?? []), 'is_string'));
        $this->userAgents = $agents !== [] ? $agents : UserAgents::VISITORS;
        $this->ownSites = new OwnSites(array_values(array_filter((array) ($cfg['own_markers'] ?? []), 'is_string')));
    }

    public function driver(): DriverInterface
    {
        return $this->driver;
    }

    /**
     * @param array<string, Site> $sites
     */
    public function visit(array $sites): void
    {
        $maxSites = (int) ($this->cfg['max_sites'] ?? 0);
        if ($maxSites > 0) {
            $sites = array_slice($sites, 0, $maxSites, true);
        }
        if ($sites === []) {
            return;
        }

        if (!empty($this->cfg['crawl'])) {
            $this->crawl($sites);

            return;
        }

        $variants = max(1, (int) ($this->cfg['variants'] ?? 1));
        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $screenshot = (bool) ($this->cfg['screenshot'] ?? true) && $this->driver->name() === 'playwright';
        $proxies = $this->proxyList();
        $proxyIndex = 0;

        $jobs = [];
        foreach ($sites as $key => $site) {
            $url = ($this->cfg['target'] ?? 'found') === 'root' || $site->bestUrl === ''
                ? 'https://' . $site->host . '/'
                : $site->bestUrl;
            $siteDir = $dir . '/' . self::safeName($site->host);
            for ($variant = 1; $variant <= $variants; $variant++) {
                $proxy = $proxies !== [] ? $proxies[$proxyIndex++ % count($proxies)] : null;
                $jobs[] = new VisitJob(
                    id: $key . "\t" . $variant,
                    siteKey: (string) $key,
                    variant: $variant,
                    url: $url,
                    referer: $this->referer($site),
                    userAgent: $this->userAgents[($variant - 1) % count($this->userAgents)],
                    proxyUrl: $proxy?->url,
                    proxyLabel: $proxy?->label ?? 'direct',
                    htmlFile: $siteDir . '/variant-' . $variant . '.html',
                    screenshotFile: $screenshot ? $siteDir . '/variant-' . $variant . '.png' : null,
                );
            }
        }

        $this->log->info(sprintf(
            'Визиты на сайты через %s: %d страниц (%d сайтов × %d вариантов)…',
            $this->driver->name(),
            count($jobs),
            count($sites),
            $variants,
        ));

        $done = 0;
        $ok = 0;
        $total = count($jobs);
        if ($this->onProgress !== null) {
            ($this->onProgress)(['total' => $total, 'done' => 0, 'ok' => 0, 'current' => '']);
        }
        $results = $this->driver->visit($jobs, $this->driverOptions(), function (VisitJob $job, array $result) use (&$done, &$ok, $total): void {
            $done++;
            if ($result['ok'] ?? false) {
                $ok++;
            }
            if ($this->onProgress !== null) {
                ($this->onProgress)(['total' => $total, 'done' => $done, 'ok' => $ok, 'current' => $job->url]);
            }
            $this->log->debug(sprintf(
                '  [%d/%d] %s (вариант %d, %s) — %s',
                $done,
                $total,
                $job->url,
                $job->variant,
                $job->proxyLabel,
                $result['ok'] ? 'HTTP ' . ($result['status'] ?? '?') . ', ' . mb_substr((string) $result['title'], 0, 60) : 'ошибка: ' . $result['error'],
            ));
        });

        foreach ($jobs as $job) {
            $result = $results[$job->id] ?? ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
            $visit = $this->assembleVisit($job, $result);
            if ($visit['own'] ?? false) {
                $sites[$job->siteKey]->own = true;
            }
            $sites[$job->siteKey]->visits[] = $visit;
        }

        $this->logSiteSummary($sites);
    }

    /**
     * Собирает запись о визите из результата драйвера. Если задан $siteDomain и страница
     * после редиректов увела на другой сайт — визит помечается ошибкой, а файлы удаляются.
     *
     * @param array<string, mixed> $result
     * @return array<string, mixed>
     */
    private function assembleVisit(VisitJob $job, array $result, string $siteDomain = ''): array
    {
        $visit = [
            'variant' => $job->variant,
            'url' => $job->url,
            'proxy' => $job->proxyLabel,
            'user_agent' => $job->userAgent,
            'ok' => (bool) $result['ok'],
            'error' => (string) ($result['error'] ?? ''),
            'status' => $result['status'] ?? null,
            'final_url' => (string) ($result['final_url'] ?? ''),
            'title' => (string) ($result['title'] ?? ''),
            'html_file' => '',
            'screenshot_file' => '',
            'fingerprint' => '',
            'text_length' => 0,
        ];

        if ($visit['ok'] && $siteDomain !== '' && $visit['final_url'] !== '' && !SiteLinks::sameSite($siteDomain, $visit['final_url'])) {
            @unlink($job->htmlFile);
            if ($job->screenshotFile !== null) {
                @unlink($job->screenshotFile);
            }

            return array_merge($visit, ['ok' => false, 'error' => 'редирект на другой сайт: ' . $visit['final_url']]);
        }

        if ($visit['ok'] && is_file($job->htmlFile)) {
            $html = (string) file_get_contents($job->htmlFile);
            if (!$this->ownSites->isEmpty()) {
                $host = Domains::hostFromUrl($visit['final_url'] !== '' ? $visit['final_url'] : $job->url);
                if ($this->ownSites->matchesHtml($html) || $this->ownSites->matchesHost($host)) {
                    // Наш шаблон — не сохраняем и не обходим дальше.
                    @unlink($job->htmlFile);
                    if ($job->screenshotFile !== null) {
                        @unlink($job->screenshotFile);
                    }

                    return array_merge($visit, ['ok' => false, 'error' => 'исключён как наш', 'own' => true]);
                }
            }
            $fingerprint = Fingerprint::of($html);
            $visit['html_file'] = $job->htmlFile;
            $visit['fingerprint'] = $fingerprint['hash'];
            $visit['text_length'] = $fingerprint['length'];
            if ($visit['title'] === '') {
                $visit['title'] = $fingerprint['title'];
            }
            if ($job->screenshotFile !== null && is_file($job->screenshotFile)) {
                $visit['screenshot_file'] = $job->screenshotFile;
            }
        }

        return $visit;
    }

    /**
     * Обход всех страниц из шапки сайта: открывает главную, собирает ссылки меню того же
     * сайта и открывает их. Страницы с редиректом на другой сайт не сохраняются.
     *
     * @param array<string, Site> $sites
     */
    private function crawl(array $sites): void
    {
        $maxPages = max(1, (int) ($this->cfg['max_pages'] ?? 20));
        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $screenshot = (bool) ($this->cfg['screenshot'] ?? true) && $this->driver->name() === 'playwright';
        $threshold = (float) ($this->cfg['similarity'] ?? 0.9);
        $proxies = $this->proxyList();
        $proxyIndex = 0;
        $ua = $this->userAgents[0];
        $options = $this->driverOptions();

        $nextProxy = function () use ($proxies, &$proxyIndex): ?Proxy {
            return $proxies !== [] ? $proxies[$proxyIndex++ % count($proxies)] : null;
        };

        // Состояние по сайтам: тексты сохранённых страниц, занятые имена файлов, оставшиеся ссылки.
        $state = [];
        $makeJob = function (string $key, Site $site, string $url, string $referer, bool $isHome = false) use ($dir, $screenshot, $nextProxy, $ua, &$state): VisitJob {
            $name = $this->uniqueName($state[$key]['names'], $isHome ? 'main' : self::fileNameFromUrl($url));
            $prefix = $dir . '/' . self::safeName($site->host) . '/' . $name;
            $proxy = $nextProxy();

            return new VisitJob(
                id: $key . "\t" . $name,
                siteKey: $key,
                variant: count($state[$key]['names']),
                url: $url,
                referer: $referer,
                userAgent: $ua,
                proxyUrl: $proxy?->url,
                proxyLabel: $proxy?->label ?? 'direct',
                htmlFile: $prefix . '.html',
                // Скриншот делаем только для главной — по ней и смотрят сайт.
                screenshotFile: ($screenshot && $isHome) ? $prefix . '.png' : null,
            );
        };

        $done = 0;
        $ok = 0;
        $total = 0;
        $onResult = function (VisitJob $job, array $result) use (&$done, &$ok, &$total): void {
            $done++;
            if ($result['ok'] ?? false) {
                $ok++;
            }
            if ($this->onProgress !== null) {
                ($this->onProgress)(['total' => max($total, $done), 'done' => $done, 'ok' => $ok, 'current' => $job->url]);
            }
            $this->log->debug(sprintf('  [%d] %s — %s', $done, $job->url, $result['ok'] ? 'HTTP ' . ($result['status'] ?? '?') : 'ошибка: ' . $result['error']));
        };

        // Этап 1 — главные страницы
        $homeJobs = [];
        foreach ($sites as $key => $site) {
            $url = ($this->cfg['target'] ?? 'found') === 'found' && $site->bestUrl !== '' ? $site->bestUrl : 'https://' . $site->host . '/';
            // urls — уже открытые адреса (в каноничном виде), чтобы не качать одну страницу дважды.
            $state[$key] = ['names' => [], 'texts' => [], 'links' => [], 'urls' => [SiteLinks::canonical($url) => true]];
            $homeJobs[$key] = $makeJob((string) $key, $site, $url, $this->referer($site), true);
        }
        $total = count($homeJobs);
        $this->log->info(sprintf('Обход сайтов (%s): главные страницы %d…', $this->driver->name(), count($homeJobs)));
        $homeResults = $this->driver->visit(array_values($homeJobs), $options, $onResult);

        $probeJobs = [];
        foreach ($sites as $key => $site) {
            $job = $homeJobs[$key];
            $visit = $this->assembleVisit($job, $homeResults[$job->id] ?? $this->missingResult(), $site->domain);
            if ($visit['own'] ?? false) {
                // Наш шаблон — исключаем сайт целиком, страницы не обходим.
                $site->own = true;
                @rmdir($dir . '/' . self::safeName($site->host));
                $site->visits[] = $visit;
                continue;
            }
            if (($visit['ok'] ?? false) && is_file($job->htmlFile)) {
                $html = (string) file_get_contents($job->htmlFile);
                $homeText = Fingerprint::text($html);
                // Заглушку (проверка возраста, cookie-стена, «включите JS») не берём эталоном для
                // сравнения: за ней у страниц разный контент, иначе одинаковые заглушки схлопнут сайт.
                if (self::looksLikeStub($homeText)) {
                    $visit['stub'] = true;
                } else {
                    $state[$key]['texts'][] = $homeText;
                }
                // Ссылки меню без уже открытых адресов (главная и её алиасы не качаются повторно).
                $fresh = [];
                foreach (SiteLinks::fromHeader($html, $job->url, $site->domain, $maxPages - 1) as $link) {
                    $canon = SiteLinks::canonical($link);
                    if (isset($state[$key]['urls'][$canon])) {
                        continue;
                    }
                    $state[$key]['urls'][$canon] = true;
                    $fresh[] = $link;
                }
                if ($fresh !== []) {
                    $probeJobs[$key] = $makeJob((string) $key, $site, $fresh[0], $job->url);
                    $state[$key]['links'] = array_slice($fresh, 1);
                }
            }
            $site->visits[] = $visit;
        }

        // Этап 2 — пробная страница: сравниваем с главной, отсекаем одностраничники
        if ($probeJobs !== []) {
            $total += count($probeJobs);
            $this->log->info(sprintf('Обход сайтов: пробные страницы %d…', count($probeJobs)));
            $probeResults = $this->driver->visit(array_values($probeJobs), $options, $onResult);
            foreach ($probeJobs as $key => $job) {
                $site = $sites[$key];
                $visit = $this->assembleVisit($job, $probeResults[$job->id] ?? $this->missingResult(), $site->domain);
                $visit = $this->dedupVisit($visit, $job, $state[$key]['texts'], $threshold, true);
                if ($visit['duplicate'] ?? false) {
                    $state[$key]['links'] = []; // одностраничник — дальше не качаем
                }
                $site->visits[] = $visit;
            }
        }

        // Этап 3 — остальные страницы меню (сайты, где страницы различаются)
        $pageJobs = [];
        foreach ($sites as $key => $site) {
            foreach ($state[$key]['links'] as $link) {
                $pageJobs[] = $makeJob((string) $key, $site, $link, $homeJobs[$key]->url);
            }
        }
        if ($pageJobs !== []) {
            $total += count($pageJobs);
            $this->log->info(sprintf('Обход сайтов: внутренних страниц %d…', count($pageJobs)));
            $pageResults = $this->driver->visit($pageJobs, $options, $onResult);
            foreach ($pageJobs as $job) {
                $site = $sites[$job->siteKey];
                $visit = $this->assembleVisit($job, $pageResults[$job->id] ?? $this->missingResult(), $site->domain);
                $site->visits[] = $this->dedupVisit($visit, $job, $state[$job->siteKey]['texts'], $threshold, false);
            }
        }

        $this->bucketByPageCount($sites, $dir);
        $this->logSiteSummary($sites);
    }

    /**
     * @return array<string, mixed>
     */
    private function missingResult(): array
    {
        return ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
    }

    /**
     * Короткое имя файла из URL — по последнему сегменту пути: /registracia → registracia,
     * /catalog/plastikovye/ → plastikovye. Расширение (.php/.html/…) отбрасывается; типовые
     * index/default/home и пустой путь → main.
     */
    private static function fileNameFromUrl(string $url): string
    {
        $path = (string) parse_url($url, PHP_URL_PATH);
        $segments = array_values(array_filter(explode('/', $path), static fn (string $s): bool => $s !== ''));
        $name = $segments === [] ? '' : (string) end($segments);
        $name = preg_replace('~\.(php|html?|aspx?|jsp|cgi|phtml)$~iu', '', $name) ?? $name;
        if ($name === '' || in_array(mb_strtolower($name), ['index', 'default', 'home'], true)) {
            $query = (string) parse_url($url, PHP_URL_QUERY);
            $name = $query !== '' ? $query : 'main';
        }
        $name = preg_replace('~[^\p{L}\p{N}._-]+~u', '_', $name) ?? $name;
        $name = trim($name, '._-');
        $name = mb_substr($name, 0, 80);

        return $name === '' ? 'main' : $name;
    }

    /**
     * Делает имя файла уникальным в пределах сайта: main, main-2, main-3 …
     *
     * @param array<string, true> $used
     */
    private function uniqueName(array &$used, string $base): string
    {
        $base = $base === '' ? 'main' : $base;
        $candidate = $base;
        $i = 2;
        while (isset($used[$candidate])) {
            $candidate = $base . '-' . $i;
            $i++;
        }
        $used[$candidate] = true;

        return $candidate;
    }

    /**
     * Если страница сильно совпадает с уже сохранёнными — считаем дубликатом: удаляем файлы и помечаем.
     *
     * @param array<string, mixed> $visit
     * @param list<string> $texts
     * @return array<string, mixed>
     */
    private function dedupVisit(array $visit, VisitJob $job, array &$texts, float $threshold, bool $isProbe): array
    {
        if (!($visit['ok'] ?? false) || !is_file($job->htmlFile)) {
            return $visit;
        }
        $text = Fingerprint::text((string) file_get_contents($job->htmlFile));
        if (self::looksLikeStub($text)) {
            // Заглушка (проверка возраста, cookie-стена, «включите JavaScript») — это не контент
            // сайта, а барьер перед ним. Не считаем дубликатом и не берём эталоном: страница остаётся.
            return array_merge($visit, ['stub' => true]);
        }
        $best = 0.0;
        foreach ($texts as $previous) {
            $best = max($best, Fingerprint::similarity($previous, $text));
        }
        if ($best >= $threshold) {
            @unlink($job->htmlFile);
            if ($job->screenshotFile !== null) {
                @unlink($job->screenshotFile);
            }
            $reason = $isProbe
                ? sprintf('одностраничник: совпадает с главной на %d%%', (int) round($best * 100))
                : sprintf('дубликат: совпадает с уже скачанной на %d%%', (int) round($best * 100));

            return array_merge($visit, ['ok' => false, 'error' => $reason, 'html_file' => '', 'screenshot_file' => '', 'duplicate' => true]);
        }
        $texts[] = $text;

        return $visit;
    }

    /**
     * Страница-заглушка перед контентом: проверка возраста 18+, cookie-стена, «включите JavaScript».
     * У таких страниц мало текста, но одинаковый вид на всех URL — их нельзя путать с дубликатами.
     */
    private static function looksLikeStub(string $text): bool
    {
        $length = mb_strlen($text);
        if ($length < 16) {
            return true; // почти пустая страница
        }
        if ($length > 900) {
            return false; // достаточно контента — это не заглушка
        }
        $lower = mb_strtolower($text);
        $markers = [
            'возраст', 'совершеннолет', '18 лет', '18+', '21 год', '21 года', '21+', 'adult', 'age verif',
            'вам есть', 'вам уже', 'подтвердите', 'мне есть 18', 'мне уже', 'достигли', 'исполнилось',
            'включите javascript', 'enable javascript', 'requires javascript',
            'обработку cookie', 'использование cookie', 'файлы cookie', 'файлов cookie',
        ];
        foreach ($markers as $marker) {
            if (mb_strpos($lower, $marker) !== false) {
                return true;
            }
        }

        return false;
    }

    /**
     * Раскладывает папки сайтов по числу собранных страниц: pages/<N>-стр/<host>/.
     *
     * @param array<string, Site> $sites
     */
    private function bucketByPageCount(array $sites, string $dir): void
    {
        foreach ($sites as $site) {
            if ($site->own) {
                continue; // наш шаблон — папку не создаём
            }
            $count = $site->visitSummary()['ok'];
            $from = $dir . '/' . self::safeName($site->host);
            if (!is_dir($from)) {
                continue;
            }
            $bucket = $dir . '/' . $count . '-стр';
            if (!is_dir($bucket)) {
                @mkdir($bucket, 0777, true);
            }
            $to = $bucket . '/' . self::safeName($site->host);
            if ($to === $from || !@rename($from, $to)) {
                continue;
            }
            foreach ($site->visits as &$visit) {
                foreach (['html_file', 'screenshot_file'] as $field) {
                    if (($visit[$field] ?? '') !== '' && str_starts_with((string) $visit[$field], $from . '/')) {
                        $visit[$field] = $to . '/' . substr((string) $visit[$field], strlen($from) + 1);
                    }
                }
            }
            unset($visit);
        }
    }

    /**
     * Пишет в лог строку-итог по каждому сайту: сколько страниц открыто и первая ошибка.
     *
     * @param array<string, Site> $sites
     */
    private function logSiteSummary(array $sites): void
    {
        foreach ($sites as $site) {
            if ($site->own) {
                $this->log->info(sprintf('  %-38s исключён как наш', mb_substr($site->host, 0, 38)));
                continue;
            }
            $s = $site->visitSummary();
            $stubs = 0;
            foreach ($site->visits as $visit) {
                if ($visit['stub'] ?? false) {
                    $stubs++;
                }
            }
            $note = $s['error'] !== '' ? ' (' . mb_substr($s['error'], 0, 80) . ')' : '';
            if ($stubs > 0 && $stubs >= $s['ok']) {
                // Все собранные страницы — заглушка перед контентом (проверка возраста/куки).
                $note = ' ⚠ заглушка (проверка возраста/куки — контент за барьером)';
            }
            $this->log->info(sprintf(
                '  %-38s страниц: %d из %d → папка %d-стр%s',
                mb_substr($site->host, 0, 38),
                $s['ok'],
                $s['total'],
                $s['ok'],
                $note,
            ));
        }
    }

    /**
     * Прокси для визитов: 'list' — общий список по кругу (без прокси — напрямую),
     * null — напрямую, строка — один конкретный прокси.
     *
     * @return list<Proxy>
     */
    private function proxyList(): array
    {
        $setting = array_key_exists('proxy', $this->cfg) ? $this->cfg['proxy'] : 'list';
        if ($setting === null || $setting === '' || $setting === false) {
            return [];
        }
        if ($setting === 'list') {
            return array_values(array_filter($this->proxies?->all() ?? [], static fn (Proxy $p): bool => !$p->disabled));
        }

        return [Proxy::parse((string) $setting)];
    }

    private function referer(Site $site): string
    {
        $mode = (string) ($this->cfg['referer'] ?? 'serp');
        return match ($mode) {
            'serp' => $this->searchBaseUrl . '/search/?' . http_build_query(
                array_filter(['text' => $site->bestQuery !== '' ? $site->bestQuery : $site->host, 'lr' => $this->region], static fn ($v) => $v !== ''),
                '',
                '&',
                PHP_QUERY_RFC3986,
            ),
            'yandex' => $this->searchBaseUrl . '/',
            'none', '' => '',
            default => $mode,
        };
    }

    /**
     * @return array<string, mixed>
     */
    private function driverOptions(): array
    {
        return [
            'timeout' => (int) ($this->cfg['timeout'] ?? 30),
            'wait_ms' => (int) ($this->cfg['wait_ms'] ?? 0),
            'concurrency' => (int) ($this->cfg['concurrency'] ?? 2),
            'delay_ms' => (int) ($this->cfg['delay_ms'] ?? 0),
            'verify_ssl' => (bool) ($this->cfg['verify_ssl'] ?? true),
            'full_page' => (bool) ($this->cfg['full_page'] ?? false),
            'max_bytes' => (int) ($this->cfg['max_bytes'] ?? 2 * 1024 * 1024),
            'resolve' => array_values((array) ($this->cfg['resolve'] ?? [])),
            'browser_path' => $this->cfg['browser_path'] ?? null,
        ];
    }

    public static function safeName(string $host): string
    {
        $name = preg_replace('~[^a-z0-9.\-]+~i', '_', mb_strtolower($host)) ?? $host;

        return trim($name, '._-') !== '' ? trim($name, '._-') : 'site';
    }
}

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

    /** @var list<string> браузерные агенты для повторов: ими приходим, когда сайт не пустил робота */
    private array $retryAgents;

    /** Распознавать ли витрину чужих офферов вместо сайта (visit.detect_offer_walls). */
    private bool $detectOfferWalls;

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
        // Перебор агентов при повторе (visit.retry_user_agents, по умолчанию включён): пустой список
        // значит «не менять агент», иначе это браузеры из того же visit.user_agents.
        $this->retryAgents = ($cfg['retry_user_agents'] ?? true) ? UserAgents::browsersFrom($this->userAgents) : [];
        $this->detectOfferWalls = (bool) ($cfg['detect_offer_walls'] ?? true);
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
        $results = $this->runWithRetry($jobs, $this->driverOptions(), function (VisitJob $job, array $result) use (&$done, &$ok, $total): void {
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

        // Сайты, у которых так и не открылась ни одна страница, пробуем ещё раз — с другого прокси
        // и под другим браузерным агентом: часть из них отдаётся не с первого раза.
        $this->retryPreview($sites);
        $this->markMissingFiles($sites);
        $this->logSiteSummary($sites);
    }

    /**
     * Собирает запись о визите из результата драйвера. Если задан $siteDomain и страница
     * после редиректов увела на ДРУГОЙ сайт (другой регистрируемый домен) — визит помечается
     * ошибкой, а файлы удаляются. Редирект в пределах того же сайта (apex → бренд-поддомен,
     * casinozsd.buzz → kush.casinozsd.buzz) считается нормальным и страница сохраняется.
     *
     * @param array<string, mixed> $result
     * @return array<string, mixed>
     */
    /**
     * Ещё несколько заходов на ГЛАВНУЮ у сайтов, где превью так и не получилось («без превью» в
     * таблице панели). Внутри обычного визита повтор уже был (runWithRetry — другой прокси и другой
     * агент), но часть сайтов открывается не с первого раза: подвис прокси, сработал лимит, антибот
     * пустил «посетителя», но не робота. Поэтому здесь ещё `visit.preview_retries` попыток, и КАЖДАЯ —
     * с другим прокси И другим браузерным агентом, с растущим таймаутом.
     *
     * Удачный заход ЗАМЕНЯЕТ неудачный визит того же варианта, поэтому счётчик страниц не раздувается,
     * а в отчёте стоят тот прокси и агент, которые реально сработали.
     *
     * @param array<string, Site> $sites
     * @return array{attempted: int, recovered: int}
     */
    public function retryPreview(array $sites): array
    {
        $iterations = max(0, (int) ($this->cfg['preview_retries'] ?? 2));
        $targets = [];
        foreach ($sites as $key => $site) {
            // Наш шаблон и уже открытые сайты не трогаем: перепробовать нужно только пустые.
            if ($site->own || $site->visitSummary()['ok'] > 0) {
                continue;
            }
            $targets[(string) $key] = $site;
        }
        if ($iterations === 0 || $targets === []) {
            return ['attempted' => 0, 'recovered' => 0];
        }

        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $screenshot = (bool) ($this->cfg['screenshot'] ?? true) && $this->driver->name() === 'playwright';
        $proxies = $this->proxyList();
        // Ходим «обычным посетителем»: робота такие сайты как раз и не пускают.
        $agents = $this->retryAgents !== [] ? $this->retryAgents : UserAgents::BROWSERS;
        $attempted = count($targets);
        $recovered = 0;
        $proxyIndex = 0;

        for ($attempt = 1; $attempt <= $iterations && $targets !== []; $attempt++) {
            $jobs = [];
            foreach ($targets as $key => $site) {
                $url = ($this->cfg['target'] ?? 'found') === 'root' || $site->bestUrl === ''
                    ? 'https://' . $site->host . '/'
                    : $site->bestUrl;
                $siteDir = $dir . '/' . self::safeName($site->host);
                $proxy = $this->pickRetryProxy($proxies, self::lastProxyLabel($site), $proxyIndex);
                $jobs[] = new VisitJob(
                    id: (string) $key,
                    siteKey: (string) $key,
                    variant: 1,
                    url: $url,
                    referer: $this->referer($site),
                    userAgent: $agents[($attempt - 1) % count($agents)],
                    proxyUrl: $proxy?->url,
                    proxyLabel: $proxy?->label ?? 'direct',
                    htmlFile: $siteDir . '/variant-1.html',
                    screenshotFile: $screenshot ? $siteDir . '/variant-1.png' : null,
                );
            }
            $options = $this->driverOptions();
            $options['timeout'] = (int) $options['timeout'] + 20 * $attempt;
            $this->log->info(sprintf(
                'Ещё попытка открыть сайты без превью (%d из %d): %d сайтов, другой прокси и браузерный агент, таймаут %d с…',
                $attempt,
                $iterations,
                count($jobs),
                $options['timeout'],
            ));
            $total = count($jobs);
            $done = 0;
            $okNow = 0;
            $results = $this->driver->visit($jobs, $options, function (VisitJob $job, array $result) use (&$done, &$okNow, $total): void {
                $done++;
                if ($result['ok'] ?? false) {
                    $okNow++;
                }
                if ($this->onProgress !== null) {
                    ($this->onProgress)(['total' => $total, 'done' => $done, 'ok' => $okNow, 'current' => $job->url]);
                }
            });
            foreach ($jobs as $job) {
                $site = $targets[$job->siteKey] ?? null;
                if ($site === null) {
                    continue;
                }
                $result = $results[$job->id] ?? ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
                $visit = $this->assembleVisit($job, $result);
                self::replaceVisit($site, $visit);
                if ($visit['own'] ?? false) {
                    $site->own = true;
                }
                if (($visit['ok'] ?? false) || ($visit['own'] ?? false)) {
                    $recovered++;
                    unset($targets[$job->siteKey]);
                }
            }
        }
        $this->log->info(sprintf('Сайты без превью: перепробовано %d, открылось %d', $attempted, $recovered));

        return ['attempted' => $attempted, 'recovered' => $recovered];
    }

    /** Прокси последней попытки по этому сайту — чтобы следующая пошла через другой. */
    private static function lastProxyLabel(Site $site): string
    {
        $label = '';
        foreach ($site->visits as $visit) {
            $label = (string) (((array) $visit)['proxy'] ?? $label);
        }

        return $label;
    }

    /**
     * Заменяет визит того же варианта (или добавляет, если такого не было).
     *
     * @param array<string, mixed> $visit
     */
    private static function replaceVisit(Site $site, array $visit): void
    {
        foreach ($site->visits as $i => $old) {
            if ((int) (((array) $old)['variant'] ?? 0) === (int) ($visit['variant'] ?? 0)) {
                $site->visits[$i] = $visit;

                return;
            }
        }
        $site->visits[] = $visit;
    }

    private function assembleVisit(VisitJob $job, array $result, string $siteDomain = ''): array
    {
        // Стадия визита — по каталогу, куда он писался: pages/ (выгрузка/обход) или preview/ (скриншот
        // при сборе). Пишем её СРАЗУ, до любого удаления файла (наш/блок/офферная витрина/404 стирают
        // html_file), чтобы «выгружен ли сайт» определялось надёжно, а не по пути к уже удалённому файлу.
        $jobPath = str_replace('\\', '/', $job->htmlFile);
        $stage = str_contains($jobPath, '/pages/') ? 'download' : (str_contains($jobPath, '/preview/') ? 'preview' : '');
        $visit = [
            'variant' => $job->variant,
            'url' => $job->url,
            'stage' => $stage,
            // Прокси и агент ПОСЛЕДНЕЙ попытки: если страницу добыл повтор (другой прокси, браузерный
            // агент), в отчёте должен стоять он, а не отказавший первый заход.
            'proxy' => (string) ($result['retry_proxy'] ?? $job->proxyLabel),
            'user_agent' => (string) ($result['retry_user_agent'] ?? $job->userAgent),
            'ok' => (bool) $result['ok'],
            'error' => (string) ($result['error'] ?? ''),
            'status' => $result['status'] ?? null,
            'final_url' => (string) ($result['final_url'] ?? ''),
            'title' => (string) ($result['title'] ?? ''),
            'html_file' => '',
            'screenshot_file' => '',
            'fingerprint' => '',
            'text_length' => 0,
            'template' => '', // тип вёрстки по HTML (SiteTemplate): pages7 / pages12 / other
        ];

        if ($visit['ok'] && $siteDomain !== '' && $visit['final_url'] !== '' && !SiteLinks::sameSite($job->url, $visit['final_url'])) {
            @unlink($job->htmlFile);
            if ($job->screenshotFile !== null) {
                @unlink($job->screenshotFile);
            }

            return array_merge($visit, ['ok' => false, 'error' => 'редирект на другой сайт: ' . $visit['final_url']]);
        }

        if ($visit['ok'] && is_file($job->htmlFile)) {
            $html = $this->readHtml($job->htmlFile);
            if (!$this->ownSites->isEmpty()) {
                $host = Domains::hostFromUrl($visit['final_url'] !== '' ? $visit['final_url'] : $job->url);
                if ($this->ownSites->matchesHtml($html) || $this->ownSites->matchesHost($host)) {
                    // Наш шаблон — HTML не храним, но скриншот оставляем, чтобы можно было проверить глазами.
                    @unlink($job->htmlFile);
                    $shot = ($job->screenshotFile !== null && is_file($job->screenshotFile)) ? $job->screenshotFile : '';

                    return array_merge($visit, ['ok' => false, 'error' => 'исключён как наш', 'own' => true, 'screenshot_file' => $shot]);
                }
            }
            // Страница-блокировка (Cloudflare/антибот/403/429/5xx) — это не контент. Удаляем и помечаем
            // ошибкой (её потом повторяем через другой прокси), а не сохраняем как страницу сайта.
            if (self::looksLikeBlock($html, (string) $visit['title'], (int) ($visit['status'] ?? 0))) {
                @unlink($job->htmlFile);
                if ($job->screenshotFile !== null) {
                    @unlink($job->screenshotFile);
                }
                $status = (int) ($visit['status'] ?? 0);

                return array_merge($visit, ['ok' => false, 'error' => 'заблокировано (антибот/Cloudflare' . ($status > 0 ? ", HTTP $status" : '') . ')', 'blocked' => true]);
            }
            // Витрина офферов вместо сайта (клоакинг): сайт прячет себя и показывает подборку чужих
            // бонусов. Это не контент — удаляем HTML (скриншот оставляем, чтобы было видно глазами)
            // и помечаем ошибкой, которую повтор перезапросит с другого IP и под другим агентом.
            if ($this->detectOfferWalls && OfferWall::looksLike($html)) {
                @unlink($job->htmlFile);
                $shot = ($job->screenshotFile !== null && is_file($job->screenshotFile)) ? $job->screenshotFile : '';

                return array_merge($visit, [
                    'ok' => false,
                    'error' => OfferWall::LABEL . ' вместо сайта (показана витрина бонусов)',
                    'offer_wall' => true,
                    'screenshot_file' => $shot,
                ]);
            }
            // HTTP 404/410 — такой страницы на сайте нет (ссылка меню ведёт в никуда, либо это
            // динамический вход/редирект). Это не контент и НЕ дубликат: часто сервер отдаёт для
            // ненайденного пути шаблон, похожий на главную, и раньше он ошибочно попадал в «дубликаты».
            $notFound = (int) ($visit['status'] ?? 0);
            if (in_array($notFound, [404, 410], true)) {
                @unlink($job->htmlFile);
                if ($job->screenshotFile !== null) {
                    @unlink($job->screenshotFile);
                }

                return array_merge($visit, ['ok' => false, 'error' => "страница не найдена (HTTP $notFound)"]);
            }
            $fingerprint = Fingerprint::of($html);
            $visit['html_file'] = $job->htmlFile;
            $visit['fingerprint'] = $fingerprint['hash'];
            $visit['text_length'] = $fingerprint['length'];
            // Тип вёрстки (7–9 / 12–15 страниц / без категории) — по этой же странице, без лишнего чтения.
            $visit['template'] = SiteTemplate::guess($html);
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
                // Агент сайта: обычно робот Яндекса, но если главная открылась только под браузером,
                // остальные страницы сразу идут под ним — не тратим попытку на заведомый отказ.
                userAgent: $state[$key]['ua'] ?? $ua,
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
            // Кроме входного адреса помечаем и корень «/»: ссылка меню на главную не должна дать second main-2.
            $state[$key] = ['names' => [], 'texts' => [], 'links' => [], 'ua' => $ua, 'urls' => [
                SiteLinks::canonical($url) => true,
                SiteLinks::canonical($this->rootUrl($url)) => true,
            ]];
            $homeJobs[$key] = $makeJob((string) $key, $site, $url, $this->referer($site), true);
        }
        $total = count($homeJobs);
        $this->log->info(sprintf('Обход сайтов (%s): главные страницы %d…', $this->driver->name(), count($homeJobs)));
        $homeResults = $this->runWithRetry(array_values($homeJobs), $options, $onResult);

        $probeJobs = [];
        foreach ($sites as $key => $site) {
            $job = $homeJobs[$key];
            $visit = $this->assembleVisit($job, $homeResults[$job->id] ?? $this->missingResult(), $site->domain);
            if ($visit['own'] ?? false) {
                // Наш шаблон — исключаем сайт целиком, страницы не обходим; скриншот главной оставляем
                // (папка сайта уедет в «наши» при раскладке), а пустую папку без скриншота убираем.
                $site->own = true;
                if (($visit['screenshot_file'] ?? '') === '') {
                    @rmdir($dir . '/' . self::safeName($site->host));
                }
                $site->visits[] = $visit;
                continue;
            }
            if (($visit['ok'] ?? false) && is_file($job->htmlFile)) {
                // Агент, которым главная реально открылась (повтор мог смениться на браузерный) —
                // с ним идём и по остальным страницам этого сайта.
                $state[$key]['ua'] = (string) ($visit['user_agent'] ?? $state[$key]['ua']);
                $html = $this->readHtml($job->htmlFile);
                // Адрес главной ПОСЛЕ редиректов: если apex увёл на бренд-поддомен
                // (casinozsd.buzz → kush.casinozsd.buzz), меню и его ссылки живут уже на нём —
                // относительно него и разбираем ссылки, иначе они кажутся «другим поддоменом».
                $homeUrl = ((string) ($visit['final_url'] ?? '')) !== '' ? (string) $visit['final_url'] : $job->url;
                $state[$key]['urls'][SiteLinks::canonical($homeUrl)] = true;
                $state[$key]['urls'][SiteLinks::canonical($this->rootUrl($homeUrl))] = true;
                $homeText = Fingerprint::text($html);
                // Заглушку (проверка возраста, cookie-стена, «включите JS») не берём эталоном для
                // сравнения: за ней у страниц разный контент, иначе одинаковые заглушки схлопнут сайт.
                if (self::looksLikeStub($homeText)) {
                    $visit['stub'] = true;
                } else {
                    $state[$key]['texts'][] = ['text' => $homeText, 'label' => self::fileNameFromUrl($homeUrl), 'url' => $homeUrl];
                }
                // Ссылки меню без уже открытых адресов (главная и её алиасы не качаются повторно).
                // И ОДИН ФАЙЛ НА ИМЯ страницы: /vhod, /vhod.html, /vhod?ref=menu и /Vhod — это одна страница
                // «vhod», второй вариант не качаем вовсе (иначе появлялись vhod-2, registracia-2: канонические
                // ключи у них разные, а дедуп по тексту страницы-формы не ловит).
                $fresh = [];
                $takenNames = [];
                foreach (array_keys($state[$key]['names']) as $n) {
                    $takenNames[mb_strtolower((string) $n)] = true; // «main» уже занят главной
                }
                foreach (SiteLinks::fromHeader($html, $homeUrl, $site->domain, $maxPages - 1) as $link) {
                    $canon = SiteLinks::canonical($link);
                    if (isset($state[$key]['urls'][$canon])) {
                        continue;
                    }
                    $state[$key]['urls'][$canon] = true;
                    $name = mb_strtolower(self::fileNameFromUrl($link));
                    if (isset($takenNames[$name])) {
                        continue; // тот же файл под другим адресом — уже есть
                    }
                    $takenNames[$name] = true;
                    $fresh[] = $link;
                }
                if ($fresh !== []) {
                    $probeJobs[$key] = $makeJob((string) $key, $site, $fresh[0], $homeUrl);
                    $state[$key]['links'] = array_slice($fresh, 1);
                }
            }
            $site->visits[] = $visit;
        }

        // Этап 2 — пробная страница: сравниваем с главной, отсекаем одностраничники
        if ($probeJobs !== []) {
            $total += count($probeJobs);
            $this->log->info(sprintf('Обход сайтов: пробные страницы %d…', count($probeJobs)));
            $probeResults = $this->runWithRetry(array_values($probeJobs), $options, $onResult);
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
            $pageResults = $this->runWithRetry($pageJobs, $options, $onResult);
            foreach ($pageJobs as $job) {
                $site = $sites[$job->siteKey];
                $visit = $this->assembleVisit($job, $pageResults[$job->id] ?? $this->missingResult(), $site->domain);
                $site->visits[] = $this->dedupVisit($visit, $job, $state[$job->siteKey]['texts'], $threshold, false);
            }
        }

        $this->bucketByPageCount($sites, $dir);
        $this->markMissingFiles($sites);
        $this->logSiteSummary($sites);
    }

    /**
     * Докачка: перезагружает ТОЛЬКО неудачные страницы сайтов (уже скачанные не трогаем), несколько
     * итераций через РАЗНЫЕ прокси; одной из попыток пробует адрес без языкового префикса
     * (/ru/app → /app — иногда с ним 404, а без него открывается). Обновляет визиты и раскладку.
     *
     * @param array<string, Site> $sites
     * @return array{attempted: int, recovered: int} сколько страниц пробовали добрать и сколько добрали
     */
    public function retryFailed(array $sites): array
    {
        $attempted = 0;
        $recovered = 0;
        $dir = rtrim((string) ($this->cfg['dir'] ?? 'out/pages'), '/\\');
        $threshold = (float) ($this->cfg['similarity'] ?? 0.9);
        $options = $this->driverOptions();
        $proxies = $this->proxyList();
        $proxyIndex = 0;
        $iterations = max(3, (int) ($this->cfg['retries'] ?? 2) + 2);
        $baseTimeout = (int) ($options['timeout'] ?? (int) ($this->cfg['timeout'] ?? 30));
        $silent = static function (): void {};

        // Этап 1 — что именно добираем: по каждому сайту собираем «слоты» (имя файла + кандидаты
        // адреса). Сеть здесь не трогаем, поэтому это быстро даже на сотнях сайтов.
        $state = [];
        foreach ($sites as $key => $site) {
            if ($site->own) {
                continue;
            }
            $this->unbucketSite($site, $dir);
            $this->markMissingFiles([$site]); // пропавший файл — тоже «неудача»: перекачаем именно его
            $siteDir = $dir . '/' . self::safeName($site->host);

            // Занятые имена и эталонные тексты — от уже успешных страниц (их не перекачиваем).
            $usedNames = [];
            $texts = [];
            $failed = [];
            $siteUa = ''; // агент, которым страницы этого сайта уже открывались (если не робот)
            foreach ($site->visits as $i => $v) {
                if ($v['ok'] ?? false) {
                    $ok = (string) ($v['user_agent'] ?? '');
                    if ($ok !== '' && !UserAgents::isBot($ok)) {
                        $siteUa = $ok;
                    }
                    $base = pathinfo((string) ($v['html_file'] ?? ''), PATHINFO_FILENAME);
                    if ($base !== '') {
                        $usedNames[$base] = true;
                    }
                    $file = (string) ($v['html_file'] ?? '');
                    if ($file !== '' && is_file($file)) {
                        $texts[] = ['text' => Fingerprint::text($this->readHtml($file)), 'label' => $base, 'url' => (string) ($v['url'] ?? '')];
                    }
                } elseif (self::isRetryableVisit($v)) {
                    $failed[$i] = (string) ($v['url'] ?? '');
                }
            }
            $failed = array_filter($failed, static fn (string $u): bool => $u !== '');

            // По одному «слоту» на неудачную страницу: имя файла и кандидаты адреса (обычный + без locale).
            // Один файл на имя: если упавший адрес — вариант уже скачанной страницы (/vhod?ref=… рядом с vhod.html),
            // его не добираем, а помечаем дубликатом — иначе получался vhod-2.
            $slots = [];
            $takenNames = [];
            foreach (array_keys($usedNames) as $n) {
                $takenNames[mb_strtolower((string) $n)] = true;
            }
            foreach ($failed as $i => $url) {
                $base = self::fileNameFromUrl($url);
                $lower = mb_strtolower($base);
                if (isset($takenNames[$lower])) {
                    $site->visits[(int) $i] = array_merge((array) $site->visits[(int) $i], [
                        'ok' => false,
                        'duplicate' => true,
                        'error' => sprintf('дубликат: та же страница, что «%s» (другой вариант адреса)', $base),
                    ]);
                    continue;
                }
                $takenNames[$lower] = true;
                $name = $this->uniqueName($usedNames, $base);
                $slots[$i] = ['name' => $name, 'prefix' => $siteDir . '/' . $name, 'candidates' => self::retryUrlCandidates($url), 'result' => null];
            }
            // Ключевая страница, ссылки на которую в меню не нашлось: пробуем стандартный адрес
            // (/registracia, /vhod, …) — готовый контент всё равно на неё ссылается. Если такой страницы
            // нет, ответ 404 просто не сохранится и повторов не будет.
            if (!empty($this->cfg['retry_key_pages'])) {
                // Корень сайта — от уже открытой страницы (там верные схема и хост после редиректов).
                $known = (string) ($site->firstVisit()['final_url'] ?? '');
                if ($known === '') {
                    $known = (string) ($site->firstVisit()['url'] ?? ($site->bestUrl !== '' ? $site->bestUrl : 'https://' . $site->host . '/'));
                }
                $siteRoot = $this->rootUrl($known);
                foreach (KeyPages::statuses(array_map(static fn ($v): array => (array) $v, $site->visits)) as $name => $status) {
                    if ($status !== 'none' || isset($takenNames[mb_strtolower((string) $name)])) {
                        continue;
                    }
                    $takenNames[mb_strtolower((string) $name)] = true;
                    $fileName = $this->uniqueName($usedNames, (string) $name);
                    $slots['key:' . $name] = [
                        'name' => $fileName,
                        'prefix' => $siteDir . '/' . $fileName,
                        'candidates' => [KeyPages::url($siteRoot, (string) $name)],
                        'result' => null,
                        'guess' => true,
                    ];
                }
            }
            $attempted += count($slots);
            if ($slots === []) {
                if (!empty($this->cfg['crawl'])) {
                    $this->bucketByPageCount([$key => $site], $dir);
                }
                continue;
            }
            $state[$key] = ['site' => $site, 'slots' => $slots, 'texts' => $texts, 'ua' => $siteUa, 'pending' => array_keys($slots)];
        }

        // Этап 2 — попытки: ОДИН заход драйвера на все сайты сразу. Раньше каждый сайт добирался
        // отдельным заходом, а значит и отдельным запуском браузера — на сотне сайтов только запуски
        // Chromium съедали больше времени, чем сама загрузка страниц.
        for ($it = 0; $it < $iterations; $it++) {
            // Первый заход — как при обходе (робот Яндекса, другой прокси и таймаут), дальше приходим
            // браузером: если сайт закрыт именно от робота, под обычным агентом страница отдаётся.
            $ua = $it === 0 ? $this->userAgents[0] : $this->retryUserAgent($this->userAgents[0], $it);
            $asBrowser = !UserAgents::isBot($ua);
            $jobs = [];
            $jobMap = [];
            foreach ($state as $key => $st) {
                foreach ($st['pending'] as $i) {
                    $candidates = $st['slots'][$i]['candidates'];
                    $url = $candidates[$it % count($candidates)];
                    $proxy = $proxies !== [] ? $proxies[$proxyIndex++ % count($proxies)] : null;
                    // Если остальные страницы этого сайта открылись только под браузером, первым же
                    // заходом идём под ним: роботу сайт всё равно откажет.
                    $jobUa = ($it === 0 && $st['ua'] !== '') ? $st['ua'] : $ua;
                    $asBrowser = $asBrowser || !UserAgents::isBot($jobUa);
                    $job = new VisitJob(
                        id: $key . "\t" . $st['slots'][$i]['name'] . "\t" . $it,
                        siteKey: (string) $key,
                        variant: is_int($i) ? $i : count($st['site']->visits),
                        url: $url,
                        referer: $this->referer($st['site']),
                        userAgent: $jobUa,
                        proxyUrl: $proxy?->url,
                        proxyLabel: $proxy?->label ?? 'direct',
                        htmlFile: $st['slots'][$i]['prefix'] . '.html',
                        screenshotFile: null,
                    );
                    $jobs[] = $job;
                    $jobMap[$job->id] = [$key, $i];
                }
            }
            if ($jobs === []) {
                break;
            }
            $opts = $options;
            $opts['timeout'] = $baseTimeout + 15 * $it;
            $this->log->info(sprintf(
                'Докачка, попытка %d из %d: %d стр. на %d сайтах через другие прокси%s…',
                $it + 1,
                $iterations,
                count($jobs),
                count($state),
                $asBrowser ? ' под браузером' : '',
            ));
            $results = $this->driver->visit($jobs, $opts, $silent);
            foreach ($jobs as $job) {
                [$key, $i] = $jobMap[$job->id];
                $site = $state[$key]['site'];
                $visit = $this->assembleVisit($job, $results[$job->id] ?? $this->missingResult(), $site->domain);
                $guess = !empty($state[$key]['slots'][$i]['guess']);
                $state[$key]['slots'][$i]['result'] = $visit;
                if ($visit['ok'] ?? false) {
                    $done = $this->dedupVisit($visit, $job, $state[$key]['texts'], $threshold, false);
                    if ($guess) {
                        $site->visits[] = $done; // страница, которой не было в меню, — добавляем к сайту
                    } else {
                        $site->visits[(int) $i] = $done;
                    }
                    $recovered++;
                    $state[$key]['pending'] = array_values(array_diff($state[$key]['pending'], [$i]));
                } elseif ($guess && !self::isRetryableVisit($visit)) {
                    // Стандартного адреса у сайта нет (404) — больше не пробуем и в визиты не пишем.
                    $state[$key]['slots'][$i]['result'] = null;
                    $state[$key]['pending'] = array_values(array_diff($state[$key]['pending'], [$i]));
                }
            }
        }

        // Этап 3 — что не добрали: сохраняем последнюю причину и раскладываем сайты по папкам.
        foreach ($state as $key => $st) {
            foreach ($st['pending'] as $i) {
                // Неудачную догадку по стандартному адресу в визиты не пишем: сайт про эту страницу
                // ничего не сообщал, и счётчик «страниц» от неё портиться не должен.
                if (is_int($i) && $st['slots'][$i]['result'] !== null) {
                    $st['site']->visits[$i] = $st['slots'][$i]['result'];
                }
            }
            if (!empty($this->cfg['crawl'])) {
                $this->bucketByPageCount([$key => $st['site']], $dir);
            }
        }
        $this->markMissingFiles($sites);
        $this->logSiteSummary($sites);

        return ['attempted' => $attempted, 'recovered' => $recovered];
    }

    /**
     * Сколько страниц сайта открылись только под браузерным агентом: робота Яндекса сайт не пустил,
     * и страница пришла лишь на повторе. По этому числу видно сайты с «хитрым фильтром».
     *
     * @param array<int, array<string, mixed>> $visits
     */
    public static function openedAsBrowser(array $visits): int
    {
        $n = 0;
        foreach ($visits as $visit) {
            $visit = (array) $visit;
            $ua = (string) ($visit['user_agent'] ?? '');
            if (($visit['ok'] ?? false) && $ua !== '' && !UserAgents::isBot($ua)) {
                $n++;
            }
        }

        return $n;
    }

    /**
     * Показал ли сайт ТОЛЬКО витрину офферов: хотя бы одна страница распознана как подборка чужих
     * бонусов и при этом ни одна страница так и не открылась настоящей — ни с другого IP, ни под
     * другим агентом. Такие сайты панель помечает и убирает пачкой.
     *
     * @param array<int, array<string, mixed>> $visits
     */
    public static function isOfferWallSite(array $visits): bool
    {
        $walls = 0;
        foreach ($visits as $visit) {
            $visit = (array) $visit;
            if ($visit['ok'] ?? false) {
                return false; // настоящая страница всё-таки получена
            }
            if ($visit['offer_wall'] ?? false) {
                $walls++;
            }
        }

        return $walls > 0;
    }

    /**
     * Визит стоит перекачать: неуспех, но не наш/заглушка/дубликат; 404 — только если есть языковой
     * префикс (его можно убрать). Публичный и статический — по нему панель считает, у каких сайтов
     * есть что докачивать, чтобы кнопка «Докачать с ошибками» совпадала с тем, что реально чинится.
     *
     * @param array<string, mixed> $visit
     */
    public static function isRetryableVisit(array $visit): bool
    {
        if (($visit['ok'] ?? false) || ($visit['own'] ?? false) || ($visit['stub'] ?? false) || ($visit['duplicate'] ?? false)) {
            return false;
        }
        $e = mb_strtolower((string) ($visit['error'] ?? ''));
        if (str_contains($e, 'не найдена') || str_contains($e, 'http 404') || str_contains($e, 'http 410')) {
            return self::stripLocaleFromUrl((string) ($visit['url'] ?? '')) !== '';
        }

        return true;
    }

    /** Кандидаты адреса для докачки: сам адрес и он же без ведущего языкового префикса. */
    private static function retryUrlCandidates(string $url): array
    {
        $candidates = [$url];
        $stripped = self::stripLocaleFromUrl($url);
        if ($stripped !== '' && $stripped !== $url) {
            $candidates[] = $stripped;
        }

        return $candidates;
    }

    /** Убирает ведущие языковые сегменты из адреса (/ru/ru/app → /app); '' если убирать нечего. */
    private static function stripLocaleFromUrl(string $url): string
    {
        $p = parse_url($url);
        if ($p === false || !isset($p['host'])) {
            return '';
        }
        $path = $p['path'] ?? '/';
        $new = preg_replace('~^(?:/[a-z]{2}(?:-[a-z]{2})?(?=/))+~i', '', $path) ?? $path;
        if ($new === $path) {
            return '';
        }
        $new = $new === '' ? '/' : $new;
        $auth = ($p['scheme'] ?? 'https') . '://' . $p['host'] . (isset($p['port']) ? ':' . $p['port'] : '');

        return $auth . $new . (isset($p['query']) ? '?' . $p['query'] : '');
    }

    /** Возвращает папку сайта из бакета (pages/<N>-стр/<host>) обратно в pages/<host> для дозаписи. */
    private function unbucketSite(Site $site, string $dir): void
    {
        $target = $dir . '/' . self::safeName($site->host);
        // Все копии папки сайта: в бакетах (pages/<N>-стр/<host>) и уже вынутая (pages/<host>) — сливаем в одну,
        // иначе страницы, разложенные по двум бакетам после неудачного переноса, считались бы по отдельности.
        $copies = [];
        foreach (glob($dir . '/*/' . self::safeName($site->host), GLOB_ONLYDIR) ?: [] as $d) {
            if ($d !== $target) {
                $copies[] = $d;
            }
        }
        if ($copies === []) {
            return;
        }
        @mkdir($dir, 0777, true);
        foreach ($copies as $current) {
            if (!self::moveDirMerge($current, $target)) {
                continue;
            }
            foreach ($site->visits as &$v) {
                foreach (['html_file', 'screenshot_file'] as $f) {
                    $val = (string) ($v[$f] ?? '');
                    if ($val !== '' && str_starts_with($val, $current . '/')) {
                        $v[$f] = $target . '/' . substr($val, strlen($current) + 1);
                    }
                }
            }
            unset($v);
        }
    }

    /**
     * @return array<string, mixed>
     */
    private function missingResult(): array
    {
        return ['ok' => false, 'error' => 'нет результата', 'status' => null, 'final_url' => '', 'title' => ''];
    }

    /**
     * Корень сайта (scheme://host/) для адреса — чтобы пометить главную как уже открытую.
     */
    private function rootUrl(string $url): string
    {
        $parts = parse_url($url);
        $scheme = $parts['scheme'] ?? 'https';
        $host = $parts['host'] ?? '';
        $port = isset($parts['port']) ? ':' . $parts['port'] : '';

        return $scheme . '://' . $host . $port . '/';
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
     * Если страница сильно совпадает с уже сохранёнными — считаем дубликатом: удаляем файлы и помечаем,
     * указывая, С КАКОЙ страницей совпало.
     *
     * @param array<string, mixed> $visit
     * @param list<array{text: string, label: string, url: string}> $texts
     * @return array<string, mixed>
     */
    private function dedupVisit(array $visit, VisitJob $job, array &$texts, float $threshold, bool $isProbe): array
    {
        if (!($visit['ok'] ?? false) || !is_file($job->htmlFile)) {
            return $visit;
        }
        $text = Fingerprint::text($this->readHtml($job->htmlFile));
        if (self::looksLikeStub($text)) {
            // Заглушка (проверка возраста, cookie-стена, «включите JavaScript») — это не контент
            // сайта, а барьер перед ним. Не считаем дубликатом и не берём эталоном: страница остаётся.
            return array_merge($visit, ['stub' => true]);
        }
        $best = 0.0;
        $bestRef = null;
        foreach ($texts as $entry) {
            $sim = Fingerprint::similarity($entry['text'], $text);
            if ($sim > $best) {
                $best = $sim;
                $bestRef = $entry;
            }
        }
        if ($best >= $threshold) {
            @unlink($job->htmlFile);
            if ($job->screenshotFile !== null) {
                @unlink($job->screenshotFile);
            }
            // Первый эталон в списке — это главная сайта.
            $isHomeRef = $bestRef !== null && isset($texts[0]) && ($texts[0]['url'] ?? '') === ($bestRef['url'] ?? '');
            $refName = $isHomeRef ? 'главной' : '«' . ($bestRef['label'] ?? '') . '»';
            $reason = $isProbe
                ? sprintf('одностраничник: совпадает с главной на %d%%', (int) round($best * 100))
                : sprintf('дубликат: совпадает с %s на %d%%', $refName, (int) round($best * 100));

            return array_merge($visit, [
                'ok' => false,
                'error' => $reason,
                'html_file' => '',
                'screenshot_file' => '',
                'duplicate' => true,
                'duplicate_of' => $bestRef['url'] ?? '',
            ]);
        }
        $texts[] = ['text' => $text, 'label' => self::fileNameFromUrl($job->url), 'url' => $job->url];

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
            $from = $dir . '/' . self::safeName($site->host);
            if (!is_dir($from)) {
                continue;
            }
            // Наши шаблоны — в отдельную папку «наши» (только скриншот для проверки), остальные — по числу страниц.
            $bucket = $site->own ? $dir . '/наши' : $dir . '/' . $site->visitSummary()['ok'] . '-стр';
            if (!is_dir($bucket)) {
                @mkdir($bucket, 0777, true);
            }
            $to = $bucket . '/' . self::safeName($site->host);
            if ($to === $from || !self::moveDirMerge($from, $to)) {
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
     * Переносит папку сайта со слиянием: если папка назначения уже есть (осталась от прошлого прогона или
     * прежней докачки), файлы переезжают по одному, свежие перекрывают старые, пустая папка-источник
     * удаляется. Простой rename() в такой ситуации молча не срабатывал, и страницы сайта оставались
     * разложенными по двум бакетам: в таблице «9/9», а в папке — часть файлов.
     */
    private static function moveDirMerge(string $from, string $to): bool
    {
        if (!is_dir($from) || $from === $to) {
            return false;
        }
        if (!is_dir($to) && @rename($from, $to)) {
            return true;
        }
        @mkdir($to, 0777, true);
        foreach (scandir($from) ?: [] as $name) {
            if ($name === '.' || $name === '..') {
                continue;
            }
            $src = $from . '/' . $name;
            $dst = $to . '/' . $name;
            if (is_dir($src)) {
                self::moveDirMerge($src, $dst);
                continue;
            }
            if (is_file($dst)) {
                @unlink($dst); // Windows не перезаписывает rename'ом
            }
            if (!@rename($src, $dst) && @copy($src, $dst)) {
                @unlink($src);
            }
        }
        @rmdir($from);

        return !is_dir($from);
    }

    /**
     * Сверяет визиты с диском: успешный визит, чей html-файл пропал (папка не перенеслась, файл стёрли
     * руками, сбой на полпути), помечается неуспехом с понятной причиной — таблица показывает честное
     * «8/9», а докачка перекачивает именно эту страницу вместо того, чтобы верить счётчику.
     *
     * @param array<int|string, Site> $sites
     */
    private function markMissingFiles(array $sites): void
    {
        foreach ($sites as $site) {
            if ($site->own) {
                continue;
            }
            foreach ($site->visits as &$v) {
                $file = (string) ($v['html_file'] ?? '');
                if (($v['ok'] ?? false) && $file !== '' && !is_file($file)) {
                    $v['ok'] = false;
                    $v['error'] = 'файл страницы отсутствует на диске — перекачать';
                    $v['missing_file'] = true;
                }
            }
            unset($v);
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
                $shot = ($site->visits[0]['screenshot_file'] ?? '') !== '' ? ' (скриншот в папке наши)' : '';
                $this->log->info(sprintf('  %-38s исключён как наш%s', mb_substr($site->host, 0, 38), $shot));
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
        // Итог по папкам: сколько сайтов с каким числом страниц (то же покажет панель после выгрузки).
        $hist = [];
        $own = 0;
        foreach ($sites as $site) {
            if ($site->own) {
                $own++;
                continue;
            }
            $s = $site->visitSummary();
            if ($s['total'] > 0) {
                $hist[$s['ok']] = ($hist[$s['ok']] ?? 0) + 1;
            }
        }
        ksort($hist);
        $parts = [];
        foreach ($hist as $n => $count) {
            $parts[] = sprintf('%d-стр — %d', $n, $count);
        }
        if ($own > 0) {
            $parts[] = 'наши — ' . $own;
        }
        if ($parts !== []) {
            $this->log->info('Итого по папкам: ' . implode(', ', $parts));
        }
        // Итог по типу вёрстки (по HTML главной): 7–9 стр. / 12–15 стр. / без категории — то же покажет панель.
        $types = SiteTemplate::histogramText(SiteTemplate::histogram($sites));
        if ($types !== '') {
            $this->log->info('Итого по типу вёрстки: ' . $types);
        }
        // Сайты с фильтром по User-Agent: робота не пустили, страницы пришли только под браузером.
        $uaPages = 0;
        $uaSites = 0;
        foreach ($sites as $site) {
            $n = self::openedAsBrowser($site->visits);
            if ($n > 0) {
                $uaPages += $n;
                $uaSites++;
            }
        }
        if ($uaSites > 0) {
            $this->log->info(sprintf('Под браузером (робота не пустили): %d стр. на %d сайтах', $uaPages, $uaSites));
        }
    }

    /**
     * Прокси для визитов: 'list' — общий список по кругу (без прокси — напрямую),
     * null — напрямую, строка — один конкретный прокси.
     *
     * @return list<Proxy>
     */
    /**
     * Запускает задания через драйвер и повторяет неудачные из-за таймаута/сети — через ДРУГОЙ
     * прокси и с увеличенным таймаутом. Число доп. попыток — visit.retries (по умолчанию 2, 0 — без).
     *
     * @param list<VisitJob> $jobs
     * @param array<string, mixed> $options
     * @return array<string, array<string, mixed>>
     */
    private function runWithRetry(array $jobs, array $options, callable $onResult): array
    {
        $results = $this->driver->visit($jobs, $options, $onResult);
        $retries = max(0, (int) ($this->cfg['retries'] ?? 2));
        if ($retries === 0 || $jobs === []) {
            return $results;
        }
        $proxies = $this->proxyList();
        $proxyIndex = 0;
        $silent = function (VisitJob $job, array $result): void {
            $this->log->debug(sprintf('  повтор %s — %s', $job->url, ($result['ok'] ?? false) ? 'ок' : 'снова ошибка'));
        };
        for ($attempt = 1; $attempt <= $retries; $attempt++) {
            $retry = [];
            $asBrowser = false;
            foreach ($jobs as $job) {
                if ($this->isRetryable($results[$job->id] ?? [], $job)) {
                    $ua = $this->retryUserAgent($job->userAgent, $attempt);
                    $asBrowser = $asBrowser || $ua !== $job->userAgent;
                    $retry[] = $this->withRetry($job, $this->pickRetryProxy($proxies, $job->proxyLabel, $proxyIndex), $ua);
                }
            }
            if ($retry === []) {
                break;
            }
            $opts = $options;
            $opts['timeout'] = (int) ($options['timeout'] ?? (int) ($this->cfg['timeout'] ?? 30)) + 20 * $attempt;
            $this->log->info(sprintf(
                'Повтор загрузки (попытка %d из %d): %d стр. через другой прокси%s, таймаут %d с…',
                $attempt,
                $retries,
                count($retry),
                $asBrowser ? ' и под браузером (робота не пустили)' : '',
                $opts['timeout'],
            ));
            // Кто именно сходил на страницу в этот раз: прокси и агент повтора. Визит собирается по
            // ИСХОДНОМУ заданию, поэтому без этих полей в отчёте остался бы первый (отказавший) агент.
            $byId = [];
            foreach ($retry as $job) {
                $byId[$job->id] = $job;
            }
            foreach ($this->driver->visit($retry, $opts, $silent) as $id => $result) {
                $job = $byId[$id] ?? null;
                if ($job !== null) {
                    $result['retry_proxy'] = $job->proxyLabel;
                    $result['retry_user_agent'] = $job->userAgent;
                }
                $results[$id] = $result;
            }
        }

        return $results;
    }

    /**
     * Повторяем через другой прокси при любой ошибке: сетевой сбой/таймаут (сервер не ответил),
     * код блокировки (403/429/5xx) и страницу-блокировку (Cloudflare/антибот). 404 и обычный ответ — нет.
     *
     * @param array<string, mixed> $result
     */
    private function isRetryable(array $result, VisitJob $job): bool
    {
        $status = (int) ($result['status'] ?? 0);
        if (!($result['ok'] ?? false)) {
            return $status < 100 || self::isBlockStatus($status);
        }
        if (self::isBlockStatus($status)) {
            return true;
        }

        if (!is_file($job->htmlFile)) {
            return false;
        }
        $html = $this->readHtml($job->htmlFile);

        // Витрина офферов — такая же подмена страницы, как антибот-заглушка: настоящий сайт за ней
        // прячется и показывается другим посетителям, поэтому пробуем другой IP и другой агент.
        return self::looksLikeBlock($html, (string) ($result['title'] ?? ''), $status)
            || ($this->detectOfferWalls && OfferWall::looksLike($html));
    }

    /**
     * HTTP-коды, при которых помогает другой прокси/IP (блокировка, лимит, временная недоступность).
     */
    private static function isBlockStatus(int $status): bool
    {
        return in_array($status, [403, 409, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526], true);
    }

    /**
     * Похоже ли на страницу-блокировку (Cloudflare, DDoS-Guard, Incapsula, «доступ запрещён», капча).
     */
    private static function looksLikeBlock(string $html, string $title, int $status): bool
    {
        $probe = mb_strtolower(mb_substr($title . ' ' . $html, 0, 20000));
        $markers = [
            'attention required! | cloudflare', 'checking your browser before accessing', 'cf-browser-verification',
            'cf_chl_', '__cf_chl', 'challenge-platform', '/cdn-cgi/challenge', 'just a moment...', 'ray id:',
            'ddos protection by cloudflare', 'ddos-guard', 'checking if the site connection is secure',
            'enable javascript and cookies to continue', 'incapsula incident', '_incapsula_', 'imperva',
            'access to this page has been denied', 'проверка браузера', 'подождите, идёт проверка',
            'доступ ограничен', 'доступ запрещён', 'error 1020', 'error 1015', 'error 1012', 'error 1006',
            'attention required', '请稍候', 'sorry, you have been blocked',
        ];
        foreach ($markers as $marker) {
            if (mb_strpos($probe, $marker) !== false) {
                return true;
            }
        }
        // Очень короткая страница + код блокировки — тоже похоже на заглушку антибота.
        return self::isBlockStatus($status) && mb_strlen(trim(strip_tags($html))) < 200;
    }

    /**
     * Следующий прокси для повтора — по возможности отличный от текущего.
     *
     * @param list<Proxy> $proxies
     */
    private function pickRetryProxy(array $proxies, string $currentLabel, int &$index): ?Proxy
    {
        if ($proxies === []) {
            return null;
        }
        $count = count($proxies);
        for ($i = 0; $i < $count; $i++) {
            $proxy = $proxies[$index++ % $count];
            if ($proxy->label !== $currentLabel) {
                return $proxy;
            }
        }

        return $proxies[$index++ % $count]; // другого прокси нет — пробуем тем же, но с большим таймаутом
    }

    /**
     * User-Agent для повторной попытки. Часть сайтов отдаёт 403/антибот-заглушку именно роботу
     * поисковика, под которым мы ходим по умолчанию (по нему видно страницу такой, какой её получает
     * Яндекс). Поэтому повтор идёт «обычным посетителем»: номер попытки выбирает браузер из списка,
     * так что вторая попытка пробует уже другой. Выключается настройкой visit.retry_user_agents.
     */
    private function retryUserAgent(string $current, int $attempt): string
    {
        if ($this->retryAgents === []) {
            return $current;
        }
        $count = count($this->retryAgents);
        $ua = $this->retryAgents[max(0, $attempt - 1) % $count];
        if ($ua === $current && $count > 1) {
            $ua = $this->retryAgents[$attempt % $count]; // тем же агентом повторять смысла нет
        }

        return $ua;
    }

    /** Та же страница, но другим «посетителем»: другой прокси и, если включён перебор, другой агент. */
    private function withRetry(VisitJob $job, ?Proxy $proxy, string $userAgent): VisitJob
    {
        return new VisitJob(
            id: $job->id,
            siteKey: $job->siteKey,
            variant: $job->variant,
            url: $job->url,
            referer: $job->referer,
            userAgent: $userAgent,
            proxyUrl: $proxy?->url,
            proxyLabel: $proxy?->label ?? 'direct',
            htmlFile: $job->htmlFile,
            screenshotFile: $job->screenshotFile,
        );
    }

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
            'browsers' => (int) ($this->cfg['browsers'] ?? 1),
            'delay_ms' => (int) ($this->cfg['delay_ms'] ?? 0),
            'verify_ssl' => (bool) ($this->cfg['verify_ssl'] ?? true),
            'full_page' => (bool) ($this->cfg['full_page'] ?? false),
            'max_bytes' => (int) ($this->cfg['max_bytes'] ?? 2 * 1024 * 1024),
            'resolve' => array_values((array) ($this->cfg['resolve'] ?? [])),
            'browser_path' => $this->cfg['browser_path'] ?? null,
        ];
    }

    /**
     * Читает HTML страницы с ограничением по объёму (visit.max_bytes, но не меньше 1 МБ): отпечатку,
     * проверке блокировки и разбору меню больше не нужно, а гигантский файл валит PHP по памяти.
     */
    private function readHtml(string $file): string
    {
        $limit = max(1024 * 1024, (int) ($this->cfg['max_bytes'] ?? 2 * 1024 * 1024));
        $html = @file_get_contents($file, false, null, 0, $limit);

        return $html === false ? '' : $html;
    }

    public static function safeName(string $host): string
    {
        $name = preg_replace('~[^a-z0-9.\-]+~i', '_', mb_strtolower($host)) ?? $host;

        return trim($name, '._-') !== '' ? trim($name, '._-') : 'site';
    }
}

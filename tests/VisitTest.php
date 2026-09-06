<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Live\ProxyPool;
use YandexSites\Live\UserAgents;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Support\Logger;
use YandexSites\Visit\CurlDriver;
use YandexSites\Visit\Fingerprint;
use YandexSites\Visit\PageVisitor;
use YandexSites\Visit\PlaywrightDriver;
use YandexSites\Visit\VisitJob;

/**
 * Визиты на сайты через фейковый сервер: хосты направляются на него правилами resolve.
 */
final class VisitTest
{
    private const HOSTS = ['okna-moskva.ru', 'onepager.ru', 'agegate.ru', 'ourtpl.ru', 'brand-a.tpl.ru', 'brand-b.tpl.ru', 'footeronly.ru', 'variant-site.ru', 'honest-site.ru', 'dead-site.ru', 'redirect-site.ru', 'other-domain.ru', 'softsite.ru', 'duptest.ru', 'localeretry.ru', 'brandnet.ru', 'kush.brandnet.ru', 'namedup.ru'];

    private ?string $dir = null;

    private function dir(): string
    {
        if ($this->dir === null) {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-visit-' . uniqid();
            mkdir($this->dir);
        }

        return $this->dir;
    }

    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    /**
     * @return list<string>
     */
    private function resolve(int $port): array
    {
        return array_map(static fn (string $host): string => "$host:$port:127.0.0.1", self::HOSTS);
    }

    /**
     * Два User-Agent, которым фейковый сайт variant-site.ru показывает разные версии.
     *
     * @return array{0: string, 1: string}
     */
    private function differentAgents(): array
    {
        $a = 'Agent-One';
        $b = 'Agent-Two';
        while (crc32($a) % 2 === crc32($b) % 2) {
            $b .= 'x';
        }

        return [$a, $b];
    }

    public function testFingerprintIgnoresScriptsAndWhitespace(): void
    {
        $a = Fingerprint::of('<html><head><title>T</title><script>var x = 1;</script></head><body><p>Привет,   мир</p></body></html>');
        $b = Fingerprint::of("<html><head><title>T</title></head><body>\n<p>Привет, мир</p>\n</body></html>");
        Assert::same($a['hash'], $b['hash']);
        Assert::same('T', $a['title']);
        Assert::true($a['length'] > 0);
        Assert::true($a['hash'] !== Fingerprint::of('<p>Другой текст</p>')['hash']);
    }

    public function testFingerprintSimilarity(): void
    {
        Assert::same(1.0, \YandexSites\Visit\Fingerprint::similarity('окна двери', 'окна двери'), 'идентичные — 1.0');
        Assert::same(0.0, \YandexSites\Visit\Fingerprint::similarity('окна двери', 'балкон лоджия'), 'нет общих слов — 0');
        $partial = \YandexSites\Visit\Fingerprint::similarity('окна двери цены москва', 'окна двери цены питер');
        Assert::true($partial > 0.5 && $partial < 1.0, 'частичное совпадение между 0 и 1');
        $near = \YandexSites\Visit\Fingerprint::similarity('главная меню контакты каталог цены доставка', 'главная меню контакты каталог цены доставка активна');
        Assert::true($near >= 0.85, 'почти идентичные страницы — высокая похожесть');
    }

    public function testCurlDriverSavesPagesWithReferer(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir();
        [$ua1, $ua2] = $this->differentAgents();
        $jobs = [
            new VisitJob('a', 'okna-moskva.ru', 1, "http://okna-moskva.ru:$port/", 'http://yandex.test/search/?text=x', 'UA-test', null, 'direct', "$dir/okna/variant-1.html", null),
            new VisitJob('b1', 'variant-site.ru', 1, "http://variant-site.ru:$port/", '', $ua1, null, 'direct', "$dir/variant/variant-1.html", null),
            new VisitJob('b2', 'variant-site.ru', 2, "http://variant-site.ru:$port/", '', $ua2, null, 'direct', "$dir/variant/variant-2.html", null),
            new VisitJob('c', 'dead-site.ru', 1, "http://dead-site.ru:$port/", '', 'UA', null, 'direct', "$dir/dead/variant-1.html", null),
            new VisitJob('d', 'unresolvable.invalid', 1, "http://unresolvable.invalid:$port/", '', 'UA', null, 'direct', "$dir/bad/variant-1.html", null),
        ];
        $seen = [];
        $results = (new CurlDriver())->visit($jobs, ['concurrency' => 2, 'timeout' => 5, 'resolve' => $this->resolve($port)], static function (VisitJob $job) use (&$seen): void {
            $seen[] = $job->id;
        });

        Assert::same(5, count($results));
        Assert::same(5, count($seen));
        Assert::true($results['a']['ok'], $results['a']['error']);
        Assert::same(200, $results['a']['status']);
        Assert::same('okna-moskva.ru', $results['a']['title']);
        $html = (string) file_get_contents("$dir/okna/variant-1.html");
        Assert::contains('Вы пришли из поиска Яндекса', $html, 'сайт увидел Referer выдачи');
        Assert::contains('<div id="js-rendered"></div>', $html, 'без браузера JavaScript не выполняется');

        Assert::true($results['c']['ok']);
        Assert::same(404, $results['c']['status']);
        Assert::false($results['d']['ok']);
        Assert::contains('curl', $results['d']['error']);

        $fp1 = Fingerprint::of((string) file_get_contents("$dir/variant/variant-1.html"));
        $fp2 = Fingerprint::of((string) file_get_contents("$dir/variant/variant-2.html"));
        Assert::true($fp1['hash'] !== $fp2['hash'], 'разным User-Agent показаны разные версии');
        Assert::true(in_array($fp1['title'], ['Вариант A', 'Вариант B'], true));
    }

    public function testPageVisitorCollectsVariants(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir() . '/pages';
        [$ua1, $ua2] = $this->differentAgents();

        $sites = [];
        foreach (['okna-moskva.ru' => "http://okna-moskva.ru:$port/page-1/", 'variant-site.ru' => "http://variant-site.ru:$port/", 'redirect-site.ru' => "http://redirect-site.ru:$port/"] as $host => $url) {
            $site = new Site($host, $host, $host);
            $site->add(new SearchResult('пластиковые окна', 0, 3, $url, $host, 'Заголовок'));
            $sites[$host] = $site;
        }

        $visitor = new PageVisitor([
            'variants' => 2,
            'dir' => $dir,
            'target' => 'found',
            'referer' => 'serp',
            'user_agents' => [$ua1, $ua2],
            'screenshot' => false,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
        ], new CurlDriver(), $this->logger(), null, 'http://yandex.test', '213');
        $visitor->visit($sites);

        $okna = $sites['okna-moskva.ru'];
        Assert::same(2, count($okna->visits));
        Assert::true($okna->visits[0]['ok'] && $okna->visits[1]['ok']);
        Assert::same(1, $okna->variantCount(), 'одинаковая страница для обоих посетителей');
        Assert::same("http://okna-moskva.ru:$port/page-1/", $okna->visits[0]['url']);
        Assert::same($ua1, $okna->visits[0]['user_agent']);
        Assert::same($ua2, $okna->visits[1]['user_agent']);
        Assert::same('direct', $okna->visits[0]['proxy']);
        Assert::true(is_file($okna->visits[0]['html_file']));
        Assert::contains('Вы пришли из поиска Яндекса', (string) file_get_contents($okna->visits[0]['html_file']));
        Assert::same('okna-moskva.ru', $okna->firstVisit()['title']);
        Assert::same("$dir/okna-moskva.ru/variant-2.html", $okna->visits[1]['html_file']);

        Assert::same(2, $sites['variant-site.ru']->variantCount(), 'сайт показал две версии');
        Assert::contains('other-domain.ru', $sites['redirect-site.ru']->visits[0]['final_url'], 'редирект прослежен');

        $fresh = [];
        foreach (['okna-moskva.ru', 'variant-site.ru'] as $host) {
            $site = new Site($host, $host, $host);
            $site->add(new SearchResult('окна', 0, 1, "http://$host:$port/", $host, 'T'));
            $fresh[$host] = $site;
        }
        $limited = new PageVisitor(['variants' => 1, 'dir' => $dir . '/limited', 'screenshot' => false, 'timeout' => 5, 'delay_ms' => 0, 'resolve' => $this->resolve($port), 'max_sites' => 1, 'referer' => 'none', 'user_agents' => [UserAgents::BROWSERS[0]]], new CurlDriver(), $this->logger());
        $limited->visit($fresh);
        Assert::same(1, count($fresh['okna-moskva.ru']->visits), 'max_sites ограничивает число сайтов');
        Assert::same([], $fresh['variant-site.ru']->visits);
        Assert::contains('Прямой заход', (string) file_get_contents($fresh['okna-moskva.ru']->visits[0]['html_file']), 'без Referer сайт видит прямой заход');

        Assert::same('shop.okna-moskva.ru', PageVisitor::safeName('shop.Okna-Moskva.ru'));
        Assert::same('site', PageVisitor::safeName('***'));
    }

    public function testVisitsRotateThroughProxyList(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir() . '/proxied';
        $sites = [];
        foreach (['okna-moskva.ru', 'honest-site.ru'] as $host) {
            $site = new Site($host, $host, $host);
            $site->add(new SearchResult('окна', 0, 1, "http://$host:$port/", $host, 'T'));
            $sites[$host] = $site;
        }
        // Фейковый сервер отвечает и как прокси: запросы через него попадают на те же «сайты».
        $pool = ProxyPool::fromLines(["http://127.0.0.1:$port:login:secret", 'direct']);
        $visitor = new PageVisitor(['variants' => 2, 'dir' => $dir, 'screenshot' => false, 'timeout' => 5, 'delay_ms' => 0, 'resolve' => $this->resolve($port)], new CurlDriver(), $this->logger(), $pool);
        $visitor->visit($sites);

        $labels = [];
        foreach ($sites as $site) {
            foreach ($site->visits as $visit) {
                Assert::true($visit['ok'], $visit['error']);
                $labels[] = $visit['proxy'];
            }
        }
        Assert::same(["http://127.0.0.1:$port", 'direct', "http://127.0.0.1:$port", 'direct'], $labels, 'прокси чередуются по кругу от визита к визиту');

        $direct = new PageVisitor(['variants' => 1, 'dir' => $dir . '/direct', 'screenshot' => false, 'timeout' => 5, 'delay_ms' => 0, 'resolve' => $this->resolve($port), 'proxy' => null], new CurlDriver(), $this->logger(), $pool);
        $one = ['honest-site.ru' => $sites['honest-site.ru']];
        $sites['honest-site.ru']->visits = [];
        $direct->visit($one);
        Assert::same('direct', $sites['honest-site.ru']->visits[0]['proxy'], "proxy => null — без прокси даже при заданном списке");
    }

    public function testRetriesTimeoutThroughDifferentProxy(): void
    {
        // Таймаут первой попытки → повтор через другой прокси, страница всё же скачивается.
        $dir = $this->dir() . '/retry';
        $site = new Site('slow.ru', 'slow.ru', 'slow.ru');
        $site->add(new SearchResult('казино', 0, 1, 'http://slow.ru/', 'slow.ru', 'Slow'));
        $sites = ['slow.ru' => $site];

        $driver = new class implements \YandexSites\Visit\DriverInterface {
            /** @var list<string> */
            public array $proxiesSeen = [];
            public int $calls = 0;

            public function name(): string
            {
                return 'flaky';
            }

            public function visit(array $jobs, array $options, ?callable $onResult = null): array
            {
                $this->calls++;
                $out = [];
                foreach ($jobs as $job) {
                    $this->proxiesSeen[] = $job->proxyLabel;
                    if ($this->calls === 1) {
                        $out[$job->id] = ['ok' => false, 'error' => 'page.goto: Timeout 30000ms exceeded.', 'status' => null, 'final_url' => '', 'title' => ''];
                    } else {
                        @mkdir(dirname($job->htmlFile), 0777, true);
                        file_put_contents($job->htmlFile, '<html><body>OK ' . $job->url . '</body></html>');
                        $out[$job->id] = ['ok' => true, 'error' => '', 'status' => 200, 'final_url' => $job->url, 'title' => 'OK'];
                    }
                    if ($onResult !== null) {
                        $onResult($job, $out[$job->id]);
                    }
                }

                return $out;
            }
        };

        $pool = ProxyPool::fromLines(['http://10.0.0.1:1:u:p', 'http://10.0.0.2:2:u:p']);
        $visitor = new PageVisitor(['dir' => $dir, 'screenshot' => false, 'retries' => 2, 'timeout' => 5], $driver, $this->logger(), $pool);
        $visitor->visit($sites);

        Assert::true($driver->calls >= 2, 'была повторная попытка после таймаута');
        Assert::same(1, $site->visitSummary()['ok'], 'после повтора страница скачалась');
        Assert::true(count(array_unique($driver->proxiesSeen)) >= 2, 'повтор шёл через другой прокси');
    }

    public function testRetriesCloudflareBlockThroughProxy(): void
    {
        // Первый прокси упирается в Cloudflare, повтор через другой прокси даёт контент.
        $dir = $this->dir() . '/block';
        $site = new Site('cf.ru', 'cf.ru', 'cf.ru');
        $site->add(new SearchResult('q', 0, 1, 'http://cf.ru/', 'cf.ru', 'CF'));
        $sites = ['cf.ru' => $site];

        $driver = new class implements \YandexSites\Visit\DriverInterface {
            public int $calls = 0;

            public function name(): string
            {
                return 'stub';
            }

            public function visit(array $jobs, array $options, ?callable $onResult = null): array
            {
                $this->calls++;
                $out = [];
                foreach ($jobs as $job) {
                    @mkdir(dirname($job->htmlFile), 0777, true);
                    if ($this->calls === 1) {
                        file_put_contents($job->htmlFile, '<html><head><title>Just a moment...</title></head><body>Checking your browser before accessing. Ray ID: 8a</body></html>');
                        $out[$job->id] = ['ok' => true, 'error' => '', 'status' => 403, 'final_url' => $job->url, 'title' => 'Just a moment...'];
                    } else {
                        file_put_contents($job->htmlFile, '<html><body><h1>Заголовок</h1><p>реальный контент страницы тут много слов</p></body></html>');
                        $out[$job->id] = ['ok' => true, 'error' => '', 'status' => 200, 'final_url' => $job->url, 'title' => 'Контент'];
                    }
                    if ($onResult !== null) {
                        $onResult($job, $out[$job->id]);
                    }
                }

                return $out;
            }
        };

        $pool = ProxyPool::fromLines(['http://10.0.0.1:1:u:p', 'http://10.0.0.2:2:u:p']);
        $visitor = new PageVisitor(['dir' => $dir, 'screenshot' => false, 'retries' => 2, 'timeout' => 5], $driver, $this->logger(), $pool);
        $visitor->visit($sites);

        Assert::true($driver->calls >= 2, 'блокировка повторяется');
        Assert::same(1, $site->visitSummary()['ok'], 'после повтора получен контент');
        Assert::contains('реальный контент', (string) file_get_contents("$dir/cf.ru/variant-1.html"));
    }

    public function testBlockPageNotSavedAsContent(): void
    {
        // Если всё время Cloudflare — это ошибка «заблокировано», а не сохранённая страница.
        $dir = $this->dir() . '/block2';
        $site = new Site('cf2.ru', 'cf2.ru', 'cf2.ru');
        $site->add(new SearchResult('q', 0, 1, 'http://cf2.ru/', 'cf2.ru', 'CF'));
        $sites = ['cf2.ru' => $site];

        $driver = new class implements \YandexSites\Visit\DriverInterface {
            public function name(): string
            {
                return 'stub';
            }

            public function visit(array $jobs, array $options, ?callable $onResult = null): array
            {
                $out = [];
                foreach ($jobs as $job) {
                    @mkdir(dirname($job->htmlFile), 0777, true);
                    file_put_contents($job->htmlFile, '<html><head><title>Attention Required! | Cloudflare</title></head><body>Sorry, you have been blocked</body></html>');
                    $out[$job->id] = ['ok' => true, 'error' => '', 'status' => 403, 'final_url' => $job->url, 'title' => 'Attention Required! | Cloudflare'];
                    if ($onResult !== null) {
                        $onResult($job, $out[$job->id]);
                    }
                }

                return $out;
            }
        };

        $visitor = new PageVisitor(['dir' => $dir, 'screenshot' => false, 'retries' => 1, 'timeout' => 5], $driver, $this->logger());
        $visitor->visit($sites);

        Assert::same(0, $site->visitSummary()['ok'], 'блокировка не считается страницей');
        Assert::contains('заблокировано', $site->visits[0]['error']);
        Assert::false(is_file("$dir/cf2.ru/variant-1.html"), 'страница-блокировка не сохранена');
    }

    public function testDefaultVisitorIsYandexBotThenBrowser(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir() . '/bot';
        $sites = [];
        foreach (['okna-moskva.ru', 'honest-site.ru'] as $host) {
            $site = new Site($host, $host, $host);
            $site->add(new SearchResult('окна', 0, 1, "http://$host:$port/", $host, 'T'));
            $sites[$host] = $site;
        }
        $visitor = new PageVisitor(['variants' => 2, 'dir' => $dir, 'screenshot' => false, 'timeout' => 5, 'delay_ms' => 0, 'resolve' => $this->resolve($port)], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $okna = $sites['okna-moskva.ru'];
        Assert::same(UserAgents::YANDEX_BOT, $okna->visits[0]['user_agent'], 'по умолчанию первый визит — как робот Яндекса');
        Assert::same(UserAgents::BROWSERS[0], $okna->visits[1]['user_agent'], 'второй — как браузер');
        Assert::contains('Версия для поискового робота Яндекса', (string) file_get_contents($okna->visits[0]['html_file']));
        Assert::notContains('робота', (string) file_get_contents($okna->visits[1]['html_file']));
        Assert::same(2, $okna->variantCount(), 'клоакинг: роботу и посетителю показаны разные версии');
        Assert::same(1, $sites['honest-site.ru']->variantCount(), 'честный сайт показывает всем одно и то же');

        $single = new PageVisitor(['variants' => 1, 'dir' => $dir . '/single', 'screenshot' => false, 'timeout' => 5, 'delay_ms' => 0, 'resolve' => $this->resolve($port)], new CurlDriver(), $this->logger());
        $one = ['okna-moskva.ru' => (static function () use ($port): Site {
            $site = new Site('okna-moskva.ru', 'okna-moskva.ru', 'okna-moskva.ru');
            $site->add(new SearchResult('окна', 0, 1, "http://okna-moskva.ru:$port/", 'okna-moskva.ru', 'T'));

            return $site;
        })()];
        $single->visit($one);
        Assert::same(UserAgents::YANDEX_BOT, $one['okna-moskva.ru']->visits[0]['user_agent'], 'один визит — робот');
    }

    public function testCrawlOpensHeaderPagesAndSkipsOffsiteRedirects(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir() . '/crawl';
        $site = new Site('okna-moskva.ru', 'okna-moskva.ru', 'okna-moskva.ru');
        $site->add(new SearchResult('окна', 0, 1, "http://okna-moskva.ru:$port/", 'okna-moskva.ru', 'Главная'));
        $sites = ['okna-moskva.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $byUrl = [];
        foreach ($site->visits as $v) {
            $byUrl[$v['url']] = $v;
        }
        // главная + /about + /contacts + /leave (из шапки; vk.com и «/» пропущены)
        Assert::same(4, count($site->visits), 'открыты главная и три страницы из меню');
        Assert::true($byUrl["http://okna-moskva.ru:$port/"]['ok'] ?? false, 'главная открыта');
        Assert::true($byUrl["http://okna-moskva.ru:$port/about"]['ok'] ?? false, '/about открыт');
        Assert::true($byUrl["http://okna-moskva.ru:$port/contacts"]['ok'] ?? false, '/contacts открыт');
        Assert::false($byUrl["http://okna-moskva.ru:$port/leave"]['ok'] ?? true, 'редирект на другой сайт не сохраняется');
        Assert::contains('редирект на другой сайт', $byUrl["http://okna-moskva.ru:$port/leave"]['error']);
        Assert::false(str_contains(implode(' ', array_keys($byUrl)), 'vk.com'), 'внешняя ссылка не обходится');

        // файлы названы коротко по URL и разложены в папку по числу страниц (3 собранных → 3-стр)
        Assert::true(is_file("$dir/3-стр/okna-moskva.ru/main.html"), 'главная сохранена как main.html в папке 3-стр');
        Assert::true(is_file("$dir/3-стр/okna-moskva.ru/about.html"));
        Assert::true(is_file("$dir/3-стр/okna-moskva.ru/contacts.html"));
        Assert::false(is_file("$dir/3-стр/okna-moskva.ru/leave.html"), 'страница офсайт-редиректа удалена');

        $summary = $site->visitSummary();
        Assert::same(3, $summary['ok'], 'успешно собрано 3 страницы');
        Assert::same(4, $summary['total']);
    }

    public function testCrawlStopsOnOnePager(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir() . '/onepager';
        $site = new Site('onepager.ru', 'onepager.ru', 'onepager.ru');
        $site->add(new SearchResult('лендинг', 0, 1, "http://onepager.ru:$port/", 'onepager.ru', 'Лендинг'));
        $sites = ['onepager.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'similarity' => 0.9,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        // главная + одна пробная (совпала с главной) — дальше не качаем
        Assert::same(2, count($site->visits), 'скачали главную и одну пробную, остальные не качали');
        $summary = $site->visitSummary();
        Assert::same(1, $summary['ok'], 'у одностраничника одна страница');
        Assert::contains('одностраничник', $summary['error']);
        Assert::true(is_file("$dir/1-стр/onepager.ru/main.html"), 'папка 1-стр, главная — main.html');
        // остальные страницы меню не скачаны
        Assert::false(is_file("$dir/1-стр/onepager.ru/contacts.html"));
        Assert::same(0, count(glob("$dir/1-стр/onepager.ru/*.html") ?: []) - 1, 'кроме main других html нет');
    }

    public function testCrawlStaysOnSubdomainAndCollapsesLangLoop(): void
    {
        // Обходим только текущий поддомен (brand-b не трогаем); «цикл» /ru/ru/ru/promo схлопывается
        // в /ru/promo — реальная страница за циклом всё же скачивается (как promo.html).
        $port = FakeServer::port();
        $dir = $this->dir() . '/subs';
        $site = new Site('brand-a.tpl.ru', 'brand-a.tpl.ru', 'tpl.ru');
        $site->add(new SearchResult('бренд', 0, 1, "http://brand-a.tpl.ru:$port/", 'brand-a.tpl.ru', 'Бренд A'));
        $sites = ['brand-a.tpl.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $joined = implode(' ', array_map(static fn (array $v): string => (string) $v['url'], $site->visits));
        Assert::false(str_contains($joined, 'brand-b.tpl.ru'), 'на соседний поддомен не переходим');
        Assert::false(str_contains($joined, '/ru/ru'), 'цикл схлопнут — повторов /ru/ru нет');
        // главная + /bonus + промо-страница за схлопнутым циклом
        Assert::same(3, count($site->visits), 'главная и две страницы своего поддомена');
        Assert::true(is_file("$dir/3-стр/brand-a.tpl.ru/main.html"));
        Assert::true(is_file("$dir/3-стр/brand-a.tpl.ru/bonus.html"));
        Assert::true(is_file("$dir/3-стр/brand-a.tpl.ru/promo.html"), 'реальная страница за циклом скачана');
    }

    public function testCrawlFollowsRedirectToOwnBrandSubdomain(): void
    {
        // Сайт собран по регистрируемому домену (brandnet.ru), а его главная редиректит на
        // бренд-поддомен (kush.brandnet.ru). Это НЕ уход на чужой сайт: главную сохраняем и
        // обходим меню уже на поддомене (/about, /promo), а не выкидываем как «редирект на другой сайт».
        $port = FakeServer::port();
        $dir = $this->dir() . '/brandsub';
        $site = new Site('brandnet.ru', 'brandnet.ru', 'brandnet.ru');
        $site->add(new SearchResult('куш', 0, 1, "http://brandnet.ru:$port/", 'brandnet.ru', 'Куш'));
        $sites = ['brandnet.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $byUrl = [];
        foreach ($site->visits as $v) {
            $byUrl[$v['url']] = $v;
        }
        // Главная (по адресу apex) открыта и НЕ помечена уходом на другой сайт.
        $home = $byUrl["http://brandnet.ru:$port/"] ?? [];
        Assert::true($home['ok'] ?? false, 'главная сохранена, а не выброшена как офсайт-редирект');
        Assert::contains('kush.brandnet.ru', (string) ($home['final_url'] ?? ''), 'редирект на свой поддомен прослежен');
        // Меню разобрано на поддомене: /about и /promo с kush.brandnet.ru скачаны.
        Assert::true(($byUrl["http://kush.brandnet.ru:$port/about"]['ok'] ?? false), '/about на бренд-поддомене скачан');
        Assert::true(($byUrl["http://kush.brandnet.ru:$port/promo"]['ok'] ?? false), '/promo на бренд-поддомене скачан');
        Assert::same(3, $site->visitSummary()['ok'], 'собраны 3 страницы (главная + 2 из меню поддомена)');
        Assert::true(is_file("$dir/3-стр/brandnet.ru/main.html"), 'папка сайта — по собранному хосту brandnet.ru');
        Assert::true(is_file("$dir/3-стр/brandnet.ru/about.html"));
        Assert::true(is_file("$dir/3-стр/brandnet.ru/promo.html"));
    }

    public function testCrawlSavesOneFilePerPageName(): void
    {
        // /vhod, /vhod.html, /vhod?ref=menu — одна страница «vhod»; /registracia, /ru/registracia, /Registracia —
        // одна «registracia». Тексты у сервера для каждого адреса разные, так что срабатывает именно правило
        // «один файл на имя», а не дедуп по содержимому: раньше появлялись vhod-2 и registracia-2.
        $port = FakeServer::port();
        $dir = $this->dir() . '/namedup';
        $site = new Site('namedup.ru', 'namedup.ru', 'namedup.ru');
        $site->add(new SearchResult('вход', 0, 1, "http://namedup.ru:$port/", 'namedup.ru', 'Гл'));
        $sites = ['namedup.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 20,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $files = array_map('basename', glob("$dir/*/namedup.ru/*.html") ?: []);
        sort($files);
        Assert::same(['about.html', 'main.html', 'registracia.html', 'vhod.html'], $files, 'по одному файлу на имя, без -2');
        Assert::same(4, count($site->visits), 'варианты того же имени не качались вовсе');
        Assert::same(4, $site->visitSummary()['ok']);
    }

    public function testRetryFailedDoesNotCreateSecondFileForSameName(): void
    {
        // Упавший /vhod?ref=menu рядом с уже скачанным vhod.html — при докачке не добираем, помечаем дубликатом.
        $dir = $this->dir() . '/retryname';
        mkdir("$dir/dupname.ru", 0777, true);
        file_put_contents("$dir/dupname.ru/vhod.html", '<html><body><p>' . str_repeat('вход текст ', 30) . '</p></body></html>');
        $site = new Site('dupname.ru', 'dupname.ru', 'dupname.ru');
        $site->add(new SearchResult('x', 0, 1, 'http://dupname.ru/', 'dupname.ru', 'T'));
        $site->visits = [
            ['variant' => 0, 'url' => 'http://dupname.ru/vhod', 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$dir/dupname.ru/vhod.html"],
            ['variant' => 1, 'url' => 'http://dupname.ru/vhod?ref=menu', 'ok' => false, 'error' => 'curl 28: Timeout', 'status' => null, 'html_file' => ''],
        ];
        $visitor = new PageVisitor(['crawl' => true, 'dir' => $dir, 'screenshot' => false, 'timeout' => 5, 'retries' => 0], new CurlDriver(), $this->logger());
        $r = $visitor->retryFailed(['dupname.ru' => $site]);

        Assert::same(0, $r['attempted'], 'вариант уже скачанной страницы не добираем');
        Assert::true($site->visits[1]['duplicate'] ?? false, 'помечен дубликатом');
        Assert::contains('дубликат', (string) $site->visits[1]['error']);
        Assert::same(0, count(glob("$dir/*/dupname.ru/vhod-2.html") ?: []) + (int) is_file("$dir/dupname.ru/vhod-2.html"), 'vhod-2 не создан');
        Assert::true(is_file("$dir/1-стр/dupname.ru/vhod.html"), 'скачанная страница на месте');
    }

    public function testCrawlReadsFooterMenuWithoutSecondMain(): void
    {
        // Меню в подвале (не в шапке); входим по «глубокому» адресу с циклом. Ссылки за циклом
        // скачиваются (app, bonus), а ссылка на «/» не создаёт вторую главную (main-2).
        $port = FakeServer::port();
        $dir = $this->dir() . '/footer';
        $site = new Site('footeronly.ru', 'footeronly.ru', 'footeronly.ru');
        $site->add(new SearchResult('казино', 0, 1, "http://footeronly.ru:$port/RU-ru/RU-ru/RU-ru/zerkalo", 'footeronly.ru', 'Гл'));
        $sites = ['footeronly.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        // главная + app + bonus + promo (/promo и /RU-ru/promo — одна и та же страница)
        $summary = $site->visitSummary();
        Assert::same(4, $summary['ok'], 'главная и три страницы из меню');
        Assert::true(is_file("$dir/4-стр/footeronly.ru/main.html"), 'входная главная');
        Assert::true(is_file("$dir/4-стр/footeronly.ru/app.html"), 'страница из подвала');
        Assert::true(is_file("$dir/4-стр/footeronly.ru/bonus.html"), 'страница из подвала');
        Assert::true(is_file("$dir/4-стр/footeronly.ru/promo.html"), 'промо');
        Assert::false(is_file("$dir/4-стр/footeronly.ru/promo-2.html"), 'promo и /RU-ru/promo — одна страница, без promo-2');
        Assert::false(is_file("$dir/4-стр/footeronly.ru/main-2.html"), 'второй главной не бывает');
    }

    public function testOwnTemplateKeepsScreenshot(): void
    {
        // Наш шаблон исключаем, но скриншот главной оставляем (в папке «наши») — чтобы проверить глазами.
        $dir = $this->dir() . '/ownshot';
        $site = new Site('ourhost.ru', 'ourhost.ru', 'ourhost.ru');
        $site->add(new SearchResult('казино', 0, 1, 'http://ourhost.ru/', 'ourhost.ru', 'Наш'));
        $sites = ['ourhost.ru' => $site];

        $driver = new class implements \YandexSites\Visit\DriverInterface {
            public function name(): string
            {
                return 'playwright';
            }

            public function visit(array $jobs, array $options, ?callable $onResult = null): array
            {
                $out = [];
                foreach ($jobs as $job) {
                    @mkdir(dirname($job->htmlFile), 0777, true);
                    file_put_contents($job->htmlFile, '<html><head><meta name="yandex-verification" content="OWNMARK123"></head><body>наш</body></html>');
                    if ($job->screenshotFile !== null) {
                        file_put_contents($job->screenshotFile, 'PNG');
                    }
                    $out[$job->id] = ['ok' => true, 'error' => '', 'status' => 200, 'final_url' => $job->url, 'title' => 'Наш'];
                    if ($onResult !== null) {
                        $onResult($job, $out[$job->id]);
                    }
                }

                return $out;
            }
        };

        $visitor = new PageVisitor([
            'crawl' => true,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => true,
            'own_markers' => ['OWNMARK123'],
        ], $driver, $this->logger());
        $visitor->visit($sites);

        Assert::true($site->own, 'помечен как наш');
        Assert::true(is_file("$dir/наши/ourhost.ru/main.png"), 'скриншот главной сохранён в папке наши');
        Assert::false(is_file("$dir/наши/ourhost.ru/main.html"), 'HTML нашего шаблона не храним');
        Assert::true(str_ends_with((string) ($site->visits[0]['screenshot_file'] ?? ''), 'наши/ourhost.ru/main.png'), 'путь к скриншоту обновлён после раскладки');
    }

    public function testCrawlExcludesOwnTemplate(): void
    {
        // Наш шаблон опознаётся по метке в HTML — сайт исключается целиком, страницы не сохраняются.
        $port = FakeServer::port();
        $dir = $this->dir() . '/own';
        $site = new Site('ourtpl.ru', 'ourtpl.ru', 'ourtpl.ru');
        $site->add(new SearchResult('бонус', 0, 1, "http://ourtpl.ru:$port/", 'ourtpl.ru', 'Промо'));
        $sites = ['ourtpl.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'own_markers' => ['OWNMARK123'],
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        Assert::true($site->own, 'сайт помечен как наш');
        Assert::same(1, count($site->visits), 'только главная — дальше не обходим');
        Assert::true($site->visits[0]['own'] ?? false, 'визит помечен own');
        Assert::contains('исключён как наш', $site->visits[0]['error']);
        Assert::same(0, $site->visitSummary()['ok'], 'ни одной сохранённой страницы');
        Assert::false(is_dir("$dir/ourtpl.ru"), 'папка сайта не создана');
        Assert::same(0, count(glob("$dir/*-стр/ourtpl.ru") ?: []), 'в папки по числу страниц не попал');
    }

    public function testShortPageNamesFromUrl(): void
    {
        $method = new \ReflectionMethod(PageVisitor::class, 'fileNameFromUrl');
        $method->setAccessible(true);
        $name = static fn (string $url): string => (string) $method->invoke(null, $url);

        Assert::same('main', $name('http://site.ru/'), 'главная → main');
        Assert::same('registracia', $name('http://site.ru/registracia'), 'короткое имя по последнему сегменту');
        Assert::same('plastikovye', $name('http://site.ru/catalog/plastikovye/'), 'вложенный путь → последний сегмент');
        Assert::same('montazh', $name('http://site.ru/uslugi/montazh.php'), 'расширение .php отбрасывается');
        Assert::same('main', $name('http://site.ru/index.php'), 'index → main');
        Assert::same('contacts', $name('http://site.ru/contacts/#map'), 'якорь не влияет');
    }

    public function testCrawlDoesNotCollapseAgeGateStub(): void
    {
        // Сайт отдаёт одинаковую заглушку «Вам есть 18 лет?» на всех страницах (реальный контент за ней).
        // Одинаковый HTML заглушки не должен схлопнуть сайт в одностраничник/дубликаты — страницы разные.
        $port = FakeServer::port();
        $dir = $this->dir() . '/agegate';
        $site = new Site('agegate.ru', 'agegate.ru', 'agegate.ru');
        $site->add(new SearchResult('казино', 0, 1, "http://agegate.ru:$port/", 'agegate.ru', 'Казино'));
        $sites = ['agegate.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'similarity' => 0.9,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $byUrl = [];
        foreach ($site->visits as $v) {
            $byUrl[$v['url']] = $v;
        }
        // Сайт НЕ схлопнут: собраны главная и страницы из меню, редирект-ссылка отброшена как редирект.
        Assert::same(4, count($site->visits), 'обойдены главная и страницы меню, а не одна');
        $errors = implode(' ', array_map(static fn (array $v): string => (string) ($v['error'] ?? ''), $site->visits));
        Assert::false(str_contains($errors, 'одностраничник'), 'заглушка возраста — не одностраничник');
        Assert::false(str_contains($errors, 'дубликат'), 'заглушка возраста — не дубликат');
        Assert::true($byUrl["http://agegate.ru:$port/"]['stub'] ?? false, 'главная помечена как заглушка');
        Assert::true($byUrl["http://agegate.ru:$port/about"]['stub'] ?? false, 'внутренняя помечена как заглушка');

        $summary = $site->visitSummary();
        Assert::same(3, $summary['ok'], 'сохранены главная и две страницы меню');
        Assert::true(is_file("$dir/3-стр/agegate.ru/main.html"), 'страницы сохранены, а не удалены как дубли');
        Assert::true(is_file("$dir/3-стр/agegate.ru/about.html"));
        Assert::true(is_file("$dir/3-стр/agegate.ru/contacts.html"));
    }

    public function testCrawlDuplicateNamesReferencePage(): void
    {
        // Дубликат должен называть, С КАКОЙ страницей совпал: /contacts = копия /about.
        $port = FakeServer::port();
        $dir = $this->dir() . '/dup';
        $site = new Site('duptest.ru', 'duptest.ru', 'duptest.ru');
        $site->add(new SearchResult('казино', 0, 1, "http://duptest.ru:$port/", 'duptest.ru', 'Dup'));
        $sites = ['duptest.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'similarity' => 0.9,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $byUrl = [];
        foreach ($site->visits as $v) {
            $byUrl[$v['url']] = $v;
        }
        $c = $byUrl["http://duptest.ru:$port/contacts"] ?? null;
        Assert::true($c !== null, 'страница /contacts посещена');
        Assert::true($c['duplicate'] ?? false, '/contacts — дубликат');
        Assert::contains('дубликат', (string) ($c['error'] ?? ''));
        Assert::contains('about', (string) ($c['error'] ?? ''), 'в ошибке указано, с какой страницей совпало');
        Assert::same("http://duptest.ru:$port/about", (string) ($c['duplicate_of'] ?? ''), 'duplicate_of = адрес страницы-эталона');
    }

    public function testCrawl404IsNotFoundNotDuplicate(): void
    {
        // Сайт отдаёт для несуществующих путей код 404, но телом-копией главной. Такой ответ —
        // «страница не найдена», а не «дубликат»: раньше похожесть на главную помечала его дублем.
        $port = FakeServer::port();
        $dir = $this->dir() . '/soft';
        $site = new Site('softsite.ru', 'softsite.ru', 'softsite.ru');
        $site->add(new SearchResult('казино', 0, 1, "http://softsite.ru:$port/", 'softsite.ru', 'Soft'));
        $sites = ['softsite.ru' => $site];

        $visitor = new PageVisitor([
            'crawl' => true,
            'max_pages' => 10,
            'target' => 'found',
            'dir' => $dir,
            'screenshot' => false,
            'similarity' => 0.9,
            'timeout' => 5,
            'delay_ms' => 0,
            'concurrency' => 3,
            'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ], new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $byUrl = [];
        foreach ($site->visits as $v) {
            $byUrl[$v['url']] = $v;
        }
        $contacts = $byUrl["http://softsite.ru:$port/contacts"] ?? null;
        Assert::true($contacts !== null, 'путь /contacts посещён');
        Assert::false($contacts['ok'] ?? true, '/contacts — не ок (404)');
        Assert::contains('не найдена', (string) ($contacts['error'] ?? ''));
        Assert::false(str_contains((string) ($contacts['error'] ?? ''), 'дубликат'), '404 не помечается дубликатом');
        Assert::same('', (string) ($contacts['html_file'] ?? ''), 'страница 404 не сохранена как контент');
        Assert::false(is_file("$dir/softsite.ru/contacts.html"), 'файл 404 не сохранён');
    }

    public function testRetryFailedRecoversLocalePageKeepsRest(): void
    {
        // /ru/app даёт 404, а /app — 200. Докачка перекачивает ТОЛЬКО неудачную страницу и одной из
        // попыток пробует адрес без /ru, добирая её; уже успешные страницы остаются нетронутыми.
        $port = FakeServer::port();
        $dir = $this->dir() . '/localeretry';
        $site = new Site('localeretry.ru', 'localeretry.ru', 'localeretry.ru');
        $site->add(new SearchResult('казино', 0, 1, "http://localeretry.ru:$port/", 'localeretry.ru', 'LR'));
        $sites = ['localeretry.ru' => $site];

        $cfg = [
            'crawl' => true, 'max_pages' => 10, 'target' => 'found', 'dir' => $dir,
            'screenshot' => false, 'similarity' => 0.9, 'timeout' => 5, 'delay_ms' => 0,
            'concurrency' => 3, 'retries' => 0, 'resolve' => $this->resolve($port),
            'user_agents' => [UserAgents::YANDEX_BOT],
        ];
        $visitor = new PageVisitor($cfg, new CurlDriver(), $this->logger());
        $visitor->visit($sites);

        $byUrl = [];
        foreach ($site->visits as $v) {
            $byUrl[$v['url']] = $v;
        }
        Assert::true(isset($byUrl["http://localeretry.ru:$port/ru/app"]), '/ru/app посещён при обходе');
        Assert::false($byUrl["http://localeretry.ru:$port/ru/app"]['ok'] ?? true, '/ru/app — 404');
        Assert::same(2, $site->visitSummary()['ok'], 'до докачки — 2 страницы (главная и about)');

        // Докачка: /ru/app добирается через /app.
        $visitor->retryFailed($sites);
        Assert::same(3, $site->visitSummary()['ok'], 'после докачки — 3 страницы (добрали /app)');
        $urls = array_map(static fn (array $v): string => (string) $v['url'], $site->visits);
        Assert::inArray("http://localeretry.ru:$port/app", $urls, 'страница добрана по адресу без /ru');
        Assert::true(is_file("$dir/3-стр/localeretry.ru/app.html"), 'файл добранной страницы сохранён');
        Assert::true(is_file("$dir/3-стр/localeretry.ru/main.html"), 'главная не перекачивалась, осталась');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testPlaywrightDriverRendersJavascript(): void
    {
        $driver = new PlaywrightDriver();
        $probe = $driver->probe();
        if (!$probe['ok']) {
            Assert::skip('Playwright недоступен: ' . $probe['message']);
        }
        $port = FakeServer::port();
        $dir = $this->dir() . '/browser';
        $jobs = [
            new VisitJob('a', 'okna-moskva.ru', 1, "http://okna-moskva.ru:$port/", 'http://yandex.test/search/?text=x', 'Mozilla/5.0 (test)', null, 'direct', "$dir/okna/variant-1.html", "$dir/okna/variant-1.png"),
            new VisitJob('d', 'unresolvable.invalid', 1, 'http://unresolvable.invalid/', '', 'Mozilla/5.0 (test)', null, 'direct', "$dir/bad/variant-1.html", null),
        ];
        $results = $driver->visit($jobs, ['timeout' => 20, 'wait_ms' => 100, 'concurrency' => 2, 'resolve' => $this->resolve($port)]);

        Assert::true($results['a']['ok'], $results['a']['error']);
        Assert::same(200, $results['a']['status']);
        Assert::same('okna-moskva.ru', $results['a']['title']);
        Assert::contains("okna-moskva.ru:$port", $results['a']['final_url']);
        $html = (string) file_get_contents("$dir/okna/variant-1.html");
        Assert::contains('<div id="js-rendered">rendered by browser</div>', $html, 'браузер выполнил JavaScript');
        Assert::contains('Вы пришли из поиска Яндекса', $html);
        Assert::true(is_file("$dir/okna/variant-1.png") && filesize("$dir/okna/variant-1.png") > 0, 'скриншот сохранён');

        Assert::false($results['d']['ok']);
        Assert::true($results['d']['error'] !== '');
    }

    public function tearDownClass(): void
    {
        if ($this->dir !== null && is_dir($this->dir)) {
            $iterator = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($this->dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
            foreach ($iterator as $item) {
                $item->isDir() ? rmdir($item->getPathname()) : unlink($item->getPathname());
            }
            rmdir($this->dir);
        }
    }
}

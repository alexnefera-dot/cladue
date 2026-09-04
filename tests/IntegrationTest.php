<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Http\HttpClient;
use YandexSites\Model\Site;
use YandexSites\Runner;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\RestApiFetcher;
use YandexSites\Live\HtmlResponseParser;
use YandexSites\Live\LiveFetcher;
use YandexSites\Live\ProxyPool;
use YandexSites\Live\UserAgents;
use YandexSites\Search\XmlApiFetcher;
use YandexSites\Search\XmlResponseParser;
use YandexSites\Search\XmlStockFetcher;
use YandexSites\Support\Logger;

/**
 * Сквозные тесты через фейковый сервер API (tests/fake-api-server.php).
 */
final class IntegrationTest
{
    private ?string $dir = null;

    private function dir(): string
    {
        if ($this->dir === null) {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-it-' . uniqid();
            mkdir($this->dir);
        }

        return $this->dir;
    }

    private function logger(): Logger
    {
        return new Logger(Logger::QUIET, fopen('php://memory', 'w+'));
    }

    /**
     * @return array{code: int, out: string, err: string}
     */
    private function cli(array $args): array
    {
        $process = proc_open(
            array_merge([PHP_BINARY, PROJECT_ROOT . '/bin/yandex-sites.php'], $args),
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
            $this->dir(),
            ['YANDEX_FOLDER_ID' => 'folder-test', 'YANDEX_API_KEY' => 'key-test', 'PATH' => (string) getenv('PATH')],
        );
        fclose($pipes[0]);
        $out = (string) stream_get_contents($pipes[1]);
        $err = (string) stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        return ['code' => proc_close($process), 'out' => $out, 'err' => $err];
    }

    public function testCliEndToEndWithCacheAndFilters(): void
    {
        $port = FakeServer::port();
        $dir = $this->dir();
        file_put_contents($dir . '/config.php', sprintf(<<<'PHP_CFG'
            <?php
            return [
                'api' => ['rest_endpoint' => 'http://127.0.0.1:%d/v2/web/search', 'delay_ms' => 0, 'retry_delay_ms' => 1],
                'search' => ['groups_on_page' => 10, 'pages' => 2],
                'cache' => ['dir' => __DIR__ . '/cache'],
                'filters' => ['allowed_tlds' => ['ru', 'рф'], 'title_none' => ['форум']],
                'output' => ['dir' => __DIR__ . '/out'],
            ];
            PHP_CFG, $port));
        file_put_contents($dir . '/queries.txt', "пластиковые окна\nостекление балконов\n# comment\nnothing here\n");

        $run = $this->cli(['--config=' . $dir . '/config.php', '--queries=' . $dir . '/queries.txt', '--raw']);
        Assert::same(0, $run['code'], $run['err']);
        Assert::contains('Запросов обработано: 3 из 3', $run['out']);
        Assert::contains('обращений к источнику: 5 (из кэша: 0)', $run['out'], 'две страницы по 10 для двух запросов и одна для пустого');

        $domains = explode("\n", trim((string) file_get_contents($dir . '/out/domains.txt')));
        Assert::inArray('okna-moskva.ru', $domains);
        Assert::inArray('shop.okna-moskva.ru', $domains);
        Assert::inArray('xn--80aswg.xn--p1ai', $domains);
        Assert::inArray('balkon-master.ru', $domains);
        Assert::notInArray('www.avito.ru', $domains);
        Assert::notInArray('avito.ru', $domains);
        Assert::notInArray('vk.com', $domains);
        Assert::notInArray('market.yandex.ru', $domains);
        Assert::notInArray('okna-company.com', $domains, 'зона com не разрешена');
        Assert::notInArray('forum.okna-talk.ru', $domains, 'заголовок содержит «форум»');

        $json = json_decode((string) file_get_contents($dir . '/out/sites.json'), true);
        Assert::same(count($domains), count($json['sites']));
        Assert::same(2, $json['sites'][0]['queries_count'], 'сайты из обоих запросов идут первыми');
        Assert::true(is_file($dir . '/out/sites.csv'));
        $raw = (string) file_get_contents($dir . '/out/results.csv');
        Assert::contains(';exclude_domains', $raw);
        Assert::contains(';selected', $raw);

        $offline = $this->cli(['--config=' . $dir . '/config.php', '--queries=' . $dir . '/queries.txt', '--offline', '--quiet']);
        Assert::same(0, $offline['code'], $offline['err']);
        Assert::contains('обращений к источнику: 0 (из кэша: 5)', $offline['out']);

        $missing = $this->cli(['--config=' . $dir . '/config.php', '--query=новый запрос', '--offline']);
        Assert::same(0, $missing['code']);
        Assert::contains('Нет в кэше', $missing['err']);
        Assert::contains('Ошибок: 1', $missing['out']);

        $dry = $this->cli(['--config=' . $dir . '/config.php', '--query=что угодно', '--dry-run']);
        Assert::same(0, $dry['code']);
        Assert::contains('Пробный запуск', $dry['out']);

        $quota = $this->cli(['--config=' . $dir . '/config.php', '--query=окна', '--query=quota test', '--query=после', '--no-cache']);
        Assert::same(1, $quota['code']);
        Assert::contains('ошибку 32', $quota['err']);
        Assert::contains('Запросов обработано: 1 из 3', $quota['out']);

        $usage = $this->cli(['--config=' . $dir . '/config.php']);
        Assert::same(2, $usage['code']);
        Assert::contains('не задано ни одного запроса', $usage['err']);
    }

    public function testBadKeyIsFatalOnFirstRequest(): void
    {
        $port = FakeServer::port();
        $config = new Config([
            'api' => ['folder_id' => 'f', 'api_key' => 'bad-key', 'rest_endpoint' => "http://127.0.0.1:$port/v2/web/search", 'delay_ms' => 0, 'retries' => 0],
        ]);
        $runner = new Runner($config, new RestApiFetcher($config, new HttpClient(5), new XmlResponseParser(), $this->logger()), new XmlResponseParser(), $this->logger());
        $result = $runner->run(['окна', 'двери']);
        Assert::true($result->aborted);
        Assert::same(1, count($result->errors));
        Assert::contains('авторизации', $result->errors[0]);
    }

    public function testRetryAfterRateLimit(): void
    {
        $port = FakeServer::port();
        $config = new Config([
            'api' => ['folder_id' => 'f', 'api_key' => 'k', 'rest_endpoint' => "http://127.0.0.1:$port/v2/web/search", 'delay_ms' => 0, 'retries' => 2, 'retry_delay_ms' => 1],
        ]);
        $fetcher = new RestApiFetcher($config, new HttpClient(5), new XmlResponseParser(), $this->logger());
        $xml = $fetcher->fetch('ratelimit ' . uniqid(), 0);
        Assert::contains('<grouping', $xml);
    }

    public function testLegacyXmlApi(): void
    {
        $port = FakeServer::port();
        $config = new Config([
            'api' => ['version' => 'xml', 'folder_id' => 'f', 'api_key' => 'k', 'xml_endpoint' => "http://127.0.0.1:$port/search/xml", 'delay_ms' => 0, 'retries' => 0],
            'search' => ['groups_on_page' => 5],
            'filters' => ['exclude_domains' => []],
        ]);
        $fetcher = new CachingFetcher(new XmlApiFetcher($config, new HttpClient(5), new XmlResponseParser(), $this->logger()), $this->dir() . '/cache-xml', 0, ['v' => 'xml']);
        $runner = new Runner($config, $fetcher, new XmlResponseParser(), $this->logger());
        $result = $runner->run(['окна']);
        Assert::same(5, $result->stats['results']);
        Assert::same(5, $result->stats['sites_selected']);
        Assert::same(1, $fetcher->misses);

        $bad = new Config(['api' => ['version' => 'xml', 'folder_id' => 'f', 'api_key' => 'bad-key', 'xml_endpoint' => "http://127.0.0.1:$port/search/xml", 'delay_ms' => 0, 'retries' => 0]]);
        $result = (new Runner($bad, new XmlApiFetcher($bad, new HttpClient(5), new XmlResponseParser(), $this->logger()), new XmlResponseParser(), $this->logger()))->run(['окна']);
        Assert::true($result->aborted);
        Assert::contains('43', $result->errors[0]);
    }

    public function testXmlStockSource(): void
    {
        $port = FakeServer::port();
        $config = new Config([
            'source' => 'xmlstock',
            'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'user' => 'u', 'key' => 'k'],
            'api' => ['delay_ms' => 0, 'retries' => 0],
            'search' => ['groups_on_page' => 5],
            'filters' => ['exclude_domains' => []],
        ]);
        $runner = new Runner($config, new XmlStockFetcher($config, new HttpClient(5), new XmlResponseParser(), $this->logger()), new XmlResponseParser(), $this->logger());
        $result = $runner->run(['окна']);
        Assert::same(5, $result->stats['results']);
        Assert::same(5, $result->stats['sites_selected']);

        $bad = new Config(['source' => 'xmlstock', 'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'user' => 'u', 'key' => 'bad-key'], 'api' => ['delay_ms' => 0, 'retries' => 0]]);
        $result = (new Runner($bad, new XmlStockFetcher($bad, new HttpClient(5), new XmlResponseParser(), $this->logger()), new XmlResponseParser(), $this->logger()))->run(['окна']);
        Assert::true($result->aborted);
        Assert::contains('42', $result->errors[0]);
    }

    public function testLiveSearchDirect(): void
    {
        $port = FakeServer::port();
        $config = new Config([
            'source' => 'live',
            'live' => ['domain' => "http://127.0.0.1:$port", 'delay_ms' => 0, 'jitter_ms' => 0, 'min_gap_ms' => 0, 'cookies' => false, 'attempts' => 2, 'max_wait' => 0],
            'search' => ['pages' => 3],
            'filters' => ['allowed_tlds' => []],
        ]);
        $fetcher = new LiveFetcher($config, new HttpClient(5), new HtmlResponseParser(), ProxyPool::fromLines(['direct']), $this->logger());
        $result = (new Runner($config, $fetcher, new HtmlResponseParser(), $this->logger()))->run(['пластиковые окна', 'nothing here']);

        Assert::same([], $result->errors);
        Assert::same(3, $result->stats['requests'], 'две страницы выдачи и один пустой запрос; третья страница не запрашивается');
        Assert::same(16, $result->stats['results'], '10 результатов и колдунщик на первой странице, 5 на второй');
        Assert::same(4, $result->stats['rejected']['exclude_domains'], 'avito, market.yandex, vk и колдунщик yandex.ru');
        Assert::same(12, $result->stats['sites_selected']);
        Assert::same(range(1, 16), array_map(static fn ($row) => $row['result']->position, $result->raw), 'сквозная нумерация позиций');

        $captcha = new LiveFetcher($config, new HttpClient(5), new HtmlResponseParser(), ProxyPool::fromLines(['direct']), $this->logger());
        $result = (new Runner($config, $captcha, new HtmlResponseParser(), $this->logger()))->run(['captcha test']);
        Assert::true($result->aborted, 'единственный канал на паузе после капчи — остановка');
        Assert::contains('на паузе', $result->errors[0]);
    }

    public function testLiveSearchWithProxiesAndVisitsCli(): void
    {
        $captchaPort = FakeServer::port('captcha');
        $sitePort = FakeServer::port('local');
        $dir = $this->dir();
        $hosts = ['okna-moskva.ru', 'shop.okna-moskva.ru', 'xn--80aswg.xn--p1ai', 'dead-site.ru', 'redirect-site.ru', 'other-domain.ru', 'phone-site.ru', 'cp1251-site.ru', 'forum.okna-talk.ru', 'okna-piter.spb.ru', 'balkon-master.ru', 'parked-site.ru', 'okna-company.com'];
        $resolve = array_map(static fn (string $host): string => "$host:$sitePort:127.0.0.1", $hosts);
        file_put_contents($dir . '/config-live.php', '<?php return ' . var_export([
            'source' => 'live',
            'proxies' => ["http://127.0.0.1:$captchaPort:login:secret"],
            'live' => [
                'domain' => 'http://yandex.test',
                'delay_ms' => 0, 'jitter_ms' => 0, 'min_gap_ms' => 0, 'attempts' => 3,
                'captcha_cooldown' => 600, 'error_cooldown' => 60, 'cookies' => false, 'max_wait' => 0,
            ],
            'search' => ['pages' => 2],
            'cache' => ['dir' => $dir . '/cache-live'],
            'filters' => ['allowed_tlds' => ['ru', 'рф']],
            'visit' => ['driver' => 'curl', 'variants' => 2, 'dir' => $dir . '/pages', 'resolve' => $resolve, 'delay_ms' => 0, 'timeout' => 5, 'concurrency' => 4, 'screenshot' => false],
            'output' => ['dir' => $dir . '/out-live'],
        ], true) . ';');

        $run = $this->cli(['--config=' . $dir . '/config-live.php', '--query=пластиковые окна', '--query=остекление балконов', '--visit', "--proxy=http://127.0.0.1:$sitePort:login:secret"]);
        Assert::same(0, $run['code'], $run['err']);
        Assert::contains('Запросов обработано: 2 из 2', $run['out']);
        Assert::contains('Прокси:', $run['out']);
        Assert::contains("http://127.0.0.1:$captchaPort", $run['out']);
        Assert::contains('капч: 1', $run['out'], 'первый прокси получил капчу один раз и ушёл на паузу');
        Assert::contains('капчу', $run['err']);
        // 11 сайтов × 2 варианта = 22, минус 2 страницы dead-site.ru: его главная отдаёт HTTP 404 и
        // теперь помечается «не найдена», а не сохраняется как контент.
        Assert::contains('Визиты (curl): сайтов 11, страниц сохранено 20', $run['out'], '15 хостов минус 3 исключённых и 1 в зоне com; dead-site.ru (404) страниц не даёт');

        $domains = explode("
", trim((string) file_get_contents($dir . '/out-live/domains.txt')));
        Assert::inArray('okna-moskva.ru', $domains);
        Assert::notInArray('www.avito.ru', $domains);
        Assert::notInArray('okna-company.com', $domains);

        $json = json_decode((string) file_get_contents($dir . '/out-live/sites.json'), true);
        Assert::same('live', $json['meta']['source']);
        Assert::same(2, count($json['meta']['proxies']));
        $visited = array_values(array_filter($json['sites'], static fn (array $site): bool => $site['visits'] !== []));
        Assert::same(11, count($visited));
        $okna = array_values(array_filter($json['sites'], static fn (array $site): bool => $site['host'] === 'okna-moskva.ru'))[0];
        Assert::same(2, count($okna['visits']));
        Assert::true($okna['visits'][0]['ok'], $okna['visits'][0]['error']);
        Assert::true(is_file($okna['visits'][0]['html_file']));
        Assert::same(UserAgents::YANDEX_BOT, $okna['visits'][0]['user_agent'], 'первый визит — как робот Яндекса');
        Assert::true(UserAgents::isBot($okna['visits'][0]['user_agent']));
        Assert::false(UserAgents::isBot($okna['visits'][1]['user_agent']), 'второй визит — как браузер');
        Assert::contains('Версия для поискового робота Яндекса', (string) file_get_contents($okna['visits'][0]['html_file']));
        Assert::contains('Вы пришли из поиска Яндекса', (string) file_get_contents($okna['visits'][1]['html_file']));
        Assert::same(2, $okna['variants'], 'сайт показал роботу и посетителю разные версии');
        Assert::contains('сайтов с разными вариантами страницы: 7', $run['out'], 'страницы 404, «домен продаётся», телефона и cp1251 одинаковы для робота и посетителя');
        $proxies = array_unique(array_map(static fn (array $v): string => $v['proxy'], $okna['visits']));
        Assert::same(2, count($proxies), 'визиты чередуют оба прокси из общего списка');
        $redirected = array_values(array_filter($json['sites'], static fn (array $site): bool => $site['host'] === 'redirect-site.ru'))[0];
        Assert::contains('other-domain.ru', $redirected['visits'][0]['final_url']);
        Assert::contains(';page_file;page_final_url;page_title;page_variants', (string) file_get_contents($dir . '/out-live/sites.csv'));

        $check = $this->cli(['--config=' . $dir . '/config-live.php', '--check-proxies', "--proxy=http://127.0.0.1:$sitePort:login:secret", '--save-html=' . $dir . '/saved']);
        Assert::same(0, $check['code'], $check['err']);
        Assert::contains('Проверка 2 прокси', $check['out']);
        Assert::contains("http://127.0.0.1:$captchaPort", $check['out']);
        Assert::contains('КАПЧА', $check['out']);
        Assert::contains('OK — выдача получена, результатов: 11', $check['out']);
        Assert::contains('Рабочих прокси: 1 из 2', $check['out']);
        Assert::same(2, count(glob($dir . '/saved/*.html') ?: []), '--save-html сохраняет и капчу, и выдачу');

        $parse = $this->cli(['--parse-html=' . TESTS_ROOT . '/fixtures/serp.html']);
        Assert::same(0, $parse['code'], $parse['err']);
        Assert::contains('Тип страницы: serp', $parse['out']);
        Assert::contains('Результатов: 4', $parse['out']);
        Assert::contains('https://okna-moskva.ru/plastikovye-okna/', $parse['out']);
    }

    public function testSiteChecker(): void
    {
        $port = FakeServer::port();
        $sites = [];
        foreach (LocalSiteChecker::HOSTS as $host) {
            $sites[$host] = new Site($host, $host, $host);
        }
        $checker = new LocalSiteChecker([
            'concurrency' => 3,
            'timeout' => 5,
            'require_status' => [200],
            'reject_offsite_redirect' => true,
            'page_must_not_match' => ['домен продаётся'],
        ], $this->logger(), $port);
        $results = $checker->check($sites);

        Assert::same(count(LocalSiteChecker::HOSTS), count($results));
        Assert::true($results['okna-moskva.ru']->ok);
        Assert::same(200, $results['okna-moskva.ru']->status);
        Assert::same('okna-moskva.ru', $results['okna-moskva.ru']->title);
        Assert::false($results['dead-site.ru']->ok);
        Assert::same('status', $results['dead-site.ru']->reason);
        Assert::same(404, $results['dead-site.ru']->status);
        Assert::false($results['redirect-site.ru']->ok);
        Assert::same('redirect', $results['redirect-site.ru']->reason);
        Assert::contains('other-domain.ru', $results['redirect-site.ru']->finalUrl);
        Assert::true($results['other-domain.ru']->ok);
        Assert::false($results['parked-site.ru']->ok);
        Assert::same('page_must_not_match', $results['parked-site.ru']->reason);
        Assert::false($results['unresolvable.invalid']->ok);
        Assert::same('unreachable', $results['unresolvable.invalid']->reason);
        Assert::contains('curl', $results['unresolvable.invalid']->error);
        Assert::same('Сайт в кодировке windows-1251', $results['cp1251-site.ru']->title, 'кодировка перекодируется в UTF-8');

        $phone = new LocalSiteChecker(['page_must_match' => ['~\+7[\s\-(]*\d{3}~u'], 'timeout' => 5], $this->logger(), $port);
        $results = $phone->check(['phone-site.ru' => $sites['phone-site.ru'], 'cp1251-site.ru' => $sites['cp1251-site.ru'], 'okna-moskva.ru' => $sites['okna-moskva.ru']]);
        Assert::true($results['phone-site.ru']->ok);
        Assert::true($results['cp1251-site.ru']->ok, 'телефон находится и в перекодированной странице');
        Assert::same('page_must_match', $results['okna-moskva.ru']->reason);
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

<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Http\HttpClient;
use YandexSites\Model\Site;
use YandexSites\Runner;
use YandexSites\Search\CachingFetcher;
use YandexSites\Search\RestApiFetcher;
use YandexSites\Search\XmlApiFetcher;
use YandexSites\Search\XmlResponseParser;
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
        Assert::contains('обращений к API: 5 (из кэша: 0)', $run['out'], 'две страницы по 10 для двух запросов и одна для пустого');

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
        Assert::contains('обращений к API: 0 (из кэша: 5)', $offline['out']);

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

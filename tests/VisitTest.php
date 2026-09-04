<?php

declare(strict_types=1);

namespace Tests;

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
    private const HOSTS = ['okna-moskva.ru', 'variant-site.ru', 'dead-site.ru', 'redirect-site.ru', 'other-domain.ru'];

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
        $limited = new PageVisitor(['variants' => 1, 'dir' => $dir . '/limited', 'screenshot' => false, 'timeout' => 5, 'delay_ms' => 0, 'resolve' => $this->resolve($port), 'max_sites' => 1, 'referer' => 'none'], new CurlDriver(), $this->logger());
        $limited->visit($fresh);
        Assert::same(1, count($fresh['okna-moskva.ru']->visits), 'max_sites ограничивает число сайтов');
        Assert::same([], $fresh['variant-site.ru']->visits);
        Assert::contains('Прямой заход', (string) file_get_contents($fresh['okna-moskva.ru']->visits[0]['html_file']), 'без Referer сайт видит прямой заход');

        Assert::same('shop.okna-moskva.ru', PageVisitor::safeName('shop.Okna-Moskva.ru'));
        Assert::same('site', PageVisitor::safeName('***'));
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

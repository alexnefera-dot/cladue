<?php

declare(strict_types=1);

namespace Tests;

/**
 * Фоновое задание веб-интерфейса (bin/run-job.php) и HTTP-панель (bin/panel.php)
 * через фейковый XMLStock.
 */
final class PanelTest
{
    private ?string $dir = null;

    private function projectDir(int $port): string
    {
        if ($this->dir === null) {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-panel-' . uniqid();
            mkdir($this->dir . '/runs/current', 0777, true);
            file_put_contents($this->dir . '/config.php', '<?php return ' . var_export([
                'source' => 'xmlstock',
                'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'user' => 'u', 'key' => 'k'],
                'api' => ['delay_ms' => 0, 'retries' => 0],
                'search' => ['groups_on_page' => 10],
                'filters' => ['allowed_tlds' => []],
            ], true) . ';');
        }

        return $this->dir;
    }

    /**
     * @param list<string> $args
     * @return array{code: int, out: string}
     */
    private function php(array $args, string $cwd): array
    {
        $process = proc_open(
            array_merge([PHP_BINARY], $args),
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
            $pipes,
            $cwd,
            ['PATH' => (string) getenv('PATH')],
        );
        fclose($pipes[0]);
        $out = (string) stream_get_contents($pipes[1]) . (string) stream_get_contents($pipes[2]);
        fclose($pipes[1]);
        fclose($pipes[2]);

        return ['code' => proc_close($process), 'out' => $out];
    }

    public function testRunJobProducesResults(): void
    {
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $runDir = $dir . '/runs/job1';
        mkdir($runDir, 0777, true);
        file_put_contents($runDir . '/settings.json', json_encode([
            'queries' => ['пластиковые окна', 'остекление балконов'],
            'source' => 'xmlstock',
            'dedupe_domain' => true,
            'visit' => false,
            'repeat_hours' => 0,
        ]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);

        $status = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $status['state'], $run['out']);
        Assert::same('done', $status['phase']);
        Assert::true(($status['stats']['sites_selected'] ?? 0) > 0, 'сайты отобраны');
        Assert::true(count($status['sites']) > 0, 'превью сайтов есть в статусе');
        Assert::true(is_file($runDir . '/sites.json') && is_file($runDir . '/sites.csv') && is_file($runDir . '/domains.txt'));

        $sites = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        $hosts = array_map(static fn ($s) => $s['host'], $sites['sites']);
        Assert::inArray('okna-moskva.ru', $hosts);
        Assert::notInArray('www.avito.ru', $hosts, 'агрегаторы отсеиваются');
        // dedupe_domain => один сайт на домен: shop.okna-moskva.ru и okna-moskva.ru не дублируются
        $domains = array_map(static fn ($s) => $s['domain'], $sites['sites']);
        Assert::same(count($domains), count(array_unique($domains)), 'по одному сайту на домен');
    }

    public function testRunJobReportsErrorOnBadKey(): void
    {
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $runDir = $dir . '/runs/jobbad';
        mkdir($runDir, 0777, true);
        // подменяем ключ на неверный через отдельный config
        file_put_contents($runDir . '/settings.json', json_encode(['queries' => ['окна'], 'source' => 'xmlstock', 'visit' => false]));
        file_put_contents($dir . '/config.php', '<?php return ' . var_export([
            'source' => 'xmlstock',
            'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'user' => 'u', 'key' => 'bad-key'],
            'api' => ['delay_ms' => 0, 'retries' => 0],
        ], true) . ';');

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code']);
        $status = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::inArray($status['state'], ['error'], 'неверный ключ — состояние error');
        // восстановим рабочий config для других тестов
        $this->projectDirReset($port);
    }

    private function projectDirReset(int $port): void
    {
        file_put_contents($this->dir . '/config.php', '<?php return ' . var_export([
            'source' => 'xmlstock',
            'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'user' => 'u', 'key' => 'k'],
            'api' => ['delay_ms' => 0, 'retries' => 0],
            'search' => ['groups_on_page' => 10],
            'filters' => ['allowed_tlds' => []],
        ], true) . ';');
    }

    public function testPanelHttpEndToEnd(): void
    {
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $this->projectDirReset($port);

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);

        $log = sys_get_temp_dir() . '/yandex-sites-panel-http.log';
        $server = @proc_open(
            [PHP_BINARY, '-S', '127.0.0.1:' . $panelPort, '-t', $dir, PROJECT_ROOT . '/bin/panel.php'],
            [0 => ['pipe', 'r'], 1 => ['file', $log, 'a'], 2 => ['file', $log, 'a']],
            $pipes,
            $dir,
            array_merge(getenv(), ['YS_PROJECT_DIR' => $dir]),
        );
        if (!is_resource($server)) {
            Assert::skip('не удалось запустить php -S для панели');
        }
        fclose($pipes[0]);

        try {
            $base = "http://127.0.0.1:$panelPort";
            $this->waitFor($base . '/api/state', 50);

            $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
            Assert::true($state['ok']);
            Assert::true($state['has_config']);

            $this->http('POST', $base . '/api/keys', ['xmlstock_user' => '12478', 'xmlstock_key' => 'secretkey123']);
            Assert::contains('XMLSTOCK_USER=12478', (string) file_get_contents($dir . '/.env'));
            Assert::contains('XMLSTOCK_KEY=secretkey123', (string) file_get_contents($dir . '/.env'));

            $start = json_decode((string) $this->http('POST', $base . '/api/start', [
                'queries' => ['пластиковые окна', 'остекление балконов'],
                'source' => 'xmlstock',
                'dedupe_domain' => true,
                'visit' => false,
                'repeat_hours' => 0,
            ]), true);
            Assert::true($start['ok'], json_encode($start));

            $status = null;
            for ($i = 0; $i < 60; $i++) {
                $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
                $status = $state['status'] ?? null;
                if ($status !== null && in_array($status['state'] ?? '', ['done', 'error'], true)) {
                    break;
                }
                usleep(300000);
            }
            Assert::same('done', $status['state'] ?? 'нет', 'сбор через панель завершился');

            $results = json_decode((string) $this->http('GET', $base . '/api/results'), true);
            Assert::true(count($results['sites']) > 0);
            Assert::contains('Прогон', (string) $this->http('GET', $base . '/api/log'));

            $csv = $this->http('GET', $base . '/download?file=csv', null, $code);
            Assert::same(200, $code);
            Assert::contains('host;host_unicode;domain', $csv);

            $this->http('POST', $base . '/api/stop');
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    private function waitFor(string $url, int $tries): void
    {
        for ($i = 0; $i < $tries; $i++) {
            $ctx = stream_context_create(['http' => ['timeout' => 1, 'ignore_errors' => true]]);
            if (@file_get_contents($url, false, $ctx) !== false) {
                return;
            }
            usleep(100000);
        }
        Assert::skip('панель не отвечает');
    }

    /**
     * @param array<string, mixed>|null $json
     */
    private function http(string $method, string $url, ?array $json = null, ?int &$code = null): string
    {
        $opts = ['http' => ['method' => $method, 'timeout' => 10, 'ignore_errors' => true]];
        if ($json !== null) {
            $opts['http']['header'] = "Content-Type: application/json\r\n";
            $opts['http']['content'] = json_encode($json, JSON_UNESCAPED_UNICODE);
        }
        $body = @file_get_contents($url, false, stream_context_create($opts));
        $code = 0;
        foreach ($http_response_header ?? [] as $h) {
            if (preg_match('~^HTTP/\S+\s+(\d+)~', $h, $m) === 1) {
                $code = (int) $m[1];
            }
        }

        return $body === false ? '' : $body;
    }

    public function tearDownClass(): void
    {
        if ($this->dir !== null && is_dir($this->dir)) {
            $iterator = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($this->dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
            foreach ($iterator as $item) {
                $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
            }
            @rmdir($this->dir);
        }
    }
}

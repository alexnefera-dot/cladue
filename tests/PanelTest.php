<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\CollectHistory;

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
                'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'live_endpoint' => "http://127.0.0.1:$port/yandexlive/xml/", 'user' => 'u', 'key' => 'k'],
                'api' => ['delay_ms' => 0, 'retries' => 0],
                'search' => ['groups_on_page' => 15],
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
        @unlink($dir . '/runs/domains-base.txt');
        file_put_contents($runDir . '/settings.json', json_encode([
            'queries' => ['пластиковые окна', 'остекление балконов'],
            'source' => 'xmlstock',
            'top' => 0,
            'dedupe_domain' => true,
            'allowed_tlds' => [],
            'visit' => false,
            'preview_shots' => false,
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
        // Дубли запросов по выдаче: у фейкового источника набор сайтов для любого запроса один и тот же
        // (сдвиг по кругу), так что второй запрос — дубль первого; список без дублей лежит рядом с результатами.
        Assert::same(['total' => 2, 'duplicates' => 1, 'groups' => 1, 'no_results' => 0], $status['query_dupes'], 'сводка дублей в статусе');
        Assert::same("пластиковые окна\n", (string) file_get_contents($runDir . '/queries-unique.txt'), 'первый по списку остаётся');
        Assert::contains("оставлен: пластиковые окна (сайтов в выдаче: 14)\n  дубль: остекление балконов", (string) file_get_contents($runDir . '/query-dupes.txt'));

        $sites = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        $hosts = array_map(static fn ($s) => $s['host'], $sites['sites']);
        Assert::inArray('okna-moskva.ru', $hosts);
        Assert::inArray('okna-company.com', $hosts, 'пустой список зон = любые зоны (.com проходит)');
        Assert::notInArray('www.avito.ru', $hosts, 'агрегаторы отсеиваются');
        // dedupe_domain => один сайт на домен: shop.okna-moskva.ru и okna-moskva.ru не дублируются
        $domains = array_map(static fn ($s) => $s['domain'], $sites['sites']);
        Assert::same(count($domains), count(array_unique($domains)), 'по одному сайту на домен');
    }

    public function testXmlstockParamsReachRequest(): void
    {
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $this->projectDirReset($port);
        $capture = sys_get_temp_dir() . '/yandex-sites-fake-capture.json';
        @unlink($capture);
        $runDir = $dir . '/runs/xmparams';
        mkdir($runDir, 0777, true);
        // Панель шлёт xmlstock_device/xmlstock_domain/xmlstock_extra; buildOverrides должен превратить их
        // в xmlstock.device/domain/extra_params, а XmlStockFetcher — подставить в GET-запрос.
        file_put_contents($runDir . '/settings.json', json_encode([
            'queries' => ['окна __capture__'],
            'source' => 'xmlstock',
            'top' => 0,
            'visit' => false,
            'preview_shots' => false,
            'xmlstock_device' => 'mobile',
            'xmlstock_domain' => 'yandex.by',
            'xmlstock_extra' => ['within' => '77', 'sortby' => 'tm'],
        ]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        Assert::true(is_file($capture), 'фейковый XMLStock получил запрос');
        $got = json_decode((string) file_get_contents($capture), true);
        Assert::same('mobile', $got['device'] ?? null, 'device дошёл до запроса XMLStock');
        Assert::same('yandex.by', $got['domain'] ?? null, 'domain дошёл до запроса XMLStock');
        Assert::same('77', $got['within'] ?? null, 'доп. параметр within дошёл до запроса');
        Assert::same('tm', $got['sortby'] ?? null, 'доп. параметр перекрыл значение по умолчанию');
        @unlink($capture);
    }

    public function testXmlstockLiveModeUsesLiveEndpointAndPaginatesByTen(): void
    {
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $this->projectDirReset($port);
        $capture = sys_get_temp_dir() . '/yandex-sites-fake-capture.json';
        @unlink($capture);
        $runDir = $dir . '/runs/xmlive';
        mkdir($runDir, 0777, true);
        // Панель шлёт xmlstock_mode=live: запрос уходит на /yandexlive/xml/ без groupby, а «топ 25»
        // превращается в страницы по 10 (фейковый сервер отдаёт 15 результатов: 10 на первой + 5 на второй).
        file_put_contents($runDir . '/settings.json', json_encode([
            'queries' => ['окна __capture__'],
            'source' => 'xmlstock',
            'top' => 25,
            'visit' => false,
            'preview_shots' => false,
            'xmlstock_mode' => 'live',
            'xmlstock_device' => 'mobile',
        ]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        Assert::true(is_file($capture), 'фейковый XMLStock получил запрос');
        $got = json_decode((string) file_get_contents($capture), true);
        Assert::same('/yandexlive/xml/', $got['__path'] ?? null, 'запрос ушёл на адрес живой выдачи XMLStock');
        Assert::false(isset($got['groupby']), 'у живой выдачи нет groupby');
        Assert::same('mobile', $got['device'] ?? null, 'device дошёл и в живом режиме');
        Assert::same('1', $got['page'] ?? null, 'первая страница дала 10 результатов — запрошена вторая');
        $status = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $status['state'], $run['out']);
        Assert::same(2, $status['stats']['requests'] ?? 0, 'две страницы по 10: 10 + 5, третья не нужна');
        Assert::same(15, $status['stats']['results'] ?? 0, 'собраны обе страницы живой выдачи');
        @unlink($capture);
    }

    public function testLedgerSkipsAlreadyCollectedDomains(): void
    {
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $this->projectDirReset($port);
        $runDir = $dir . '/runs/ledger';
        mkdir($runDir, 0777, true);
        @unlink($dir . '/runs/domains-base.txt');
        $settings = json_encode([
            'queries' => ['пластиковые окна', 'остекление балконов'],
            'source' => 'xmlstock',
            'top' => 0,
            'dedupe_domain' => true,
            'allowed_tlds' => [],
            'skip_known' => true,
            'visit' => false,
            'preview_shots' => false,
        ]);
        file_put_contents($runDir . '/settings.json', $settings);

        $first = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $first['code'], $first['out']);
        $s1 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $s1['state']);
        $selected = $s1['stats']['sites_selected'];
        Assert::true($selected > 0, 'первый сбор отобрал сайты');
        Assert::same($selected, $s1['stats']['new_domains'], 'все домены новые в первый раз');
        Assert::true(is_file($dir . '/runs/domains-base.txt'), 'база доменов создана');

        // Повторный сбор с теми же запросами: все домены уже в базе — новых нет
        file_put_contents($runDir . '/settings.json', $settings);
        $second = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $second['code'], $second['out']);
        $s2 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $s2['state']);
        Assert::same(0, $s2['stats']['sites_selected'], 'повторный сбор ничего нового не отобрал');
        Assert::true(($s2['stats']['rejected']['seen_before'] ?? 0) > 0, 'домены отклонены как уже собранные');
        // Пустой сбор не затирает прошлый список: sites.json и таблица в статусе — от первого сбора.
        $kept = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        Assert::same($selected, count($kept['sites']), 'прошлый sites.json оставлен');
        Assert::true($s2['kept_previous'] ?? false, 'статус помечен kept_previous');
        Assert::same($selected, count($s2['sites']), 'таблица в статусе — прошлый список');
        Assert::contains('прошлый список', $s2['message']);
        Assert::true(($s2['stats']['cache_hits'] ?? 0) > 0 && ($s2['stats']['cache_misses'] ?? 0) === 0, 'повтор тех же запросов — ответы из кэша, к источнику не обращались');

        // «Свежая выдача» + без пропуска известных доменов: ответы получены заново, сайты отобраны снова.
        file_put_contents($runDir . '/settings.json', json_encode(array_merge((array) json_decode($settings, true), ['no_cache' => true, 'skip_known' => false])));
        $third = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $third['code'], $third['out']);
        $s3 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $s3['state']);
        Assert::true(($s3['stats']['cache_misses'] ?? 0) > 0 && ($s3['stats']['cache_hits'] ?? 0) === 0, 'со «свежей выдачей» кэш не используется');
        Assert::true($s3['stats']['sites_selected'] > 0, 'без пропуска известных доменов сайты отобраны снова');
    }

    public function testOwnDomainsAreSeededFromDiskAndCountedAmongRepeats(): void
    {
        // Домен, который уже есть в базе пересечений, повторный сбор даже не открывает — а «наш»
        // ставится только при визите, по меткам в HTML. Поэтому наши шаблоны, собранные раньше,
        // в статистике не всплывали: «наших» было столько, сколько нашлось свежих. Список наших
        // доменов достраивается тем, что помнит диск (таблица, убранные сайты, папки pages/наши),
        // и ручным own-domains.txt в корне проекта.
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $this->projectDirReset($port);
        $runDir = $dir . '/runs/ownseed';
        mkdir($runDir, 0777, true);
        @unlink($dir . '/runs/domains-base.txt');
        @unlink($dir . '/runs/own-domains.txt');
        @unlink($dir . '/runs/history.json');
        $settings = json_encode([
            'queries' => ['пластиковые окна', 'остекление балконов'],
            'source' => 'xmlstock',
            'top' => 0,
            'dedupe_domain' => true,
            'allowed_tlds' => [],
            'skip_known' => true,
            'visit' => false,
            'preview_shots' => false,
        ]);
        file_put_contents($runDir . '/settings.json', $settings);

        // Первый сбор: домены уходят в базу пересечений, таблица — в sites.json.
        $first = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $first['code'], $first['out']);
        $table = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        $hosts = array_map(static fn (array $row): string => (string) $row['host'], $table['sites']);
        Assert::true(count($hosts) >= 2, 'первый сбор отобрал сайты: ' . implode(', ', $hosts));

        // Так выглядит диск после прошлых сборов: один сайт помечен нашим в таблице, второй убран
        // кнопкой «Убрать наши», третий лежит папкой в раскладке, четвёртый вписан руками.
        $inTable = $hosts[0];
        $removed = $hosts[1];
        foreach ($table['sites'] as $i => $row) {
            if ($row['host'] === $inTable) {
                $table['sites'][$i]['own'] = true;
            }
        }
        file_put_contents($runDir . '/sites.json', json_encode($table));
        file_put_contents($runDir . '/removed.json', json_encode(['hosts' => [
            $removed => ['row' => ['host' => $removed, 'domain' => $removed, 'own' => true], 'status_row' => null, 'paths' => [], 'removed_at' => date(DATE_ATOM)],
        ]]));
        mkdir($runDir . '/pages/наши/folder-own.ru', 0777, true);
        file_put_contents($dir . '/own-domains.txt', "# свои домены
MANUAL-OWN.RU
мусор без точки
");

        // Повторный сбор теми же запросами: все домены — повторы, ни одного визита.
        file_put_contents($runDir . '/settings.json', $settings);
        $second = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $second['code'], $second['out']);

        $own = array_map('trim', file($dir . '/runs/own-domains.txt', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: []);
        Assert::true(in_array('manual-own.ru', $own, true), 'ручной own-domains.txt подмешан: ' . implode(', ', $own));
        Assert::true(in_array('folder-own.ru', $own, true), 'папка pages/наши подмешана: ' . implode(', ', $own));
        Assert::true(in_array($inTable, $own, true), 'строка «наш» из таблицы подмешана: ' . implode(', ', $own));
        Assert::true(in_array($removed, $own, true), 'убранный кнопкой «Убрать наши» тоже наш: ' . implode(', ', $own));
        Assert::true(!in_array('мусор без точки', $own, true), 'строка, не похожая на адрес, в список наших не идёт');

        $record = CollectHistory::load($dir . '/runs')[0];
        Assert::same(2, $record['own_repeats'], 'оба наших домена пришли повторами, открывать их не пришлось');
        Assert::same(2, $record['own'], 'в «наших» попали старые домены, а не только свежие');
        Assert::true(($record['own_known'] ?? 0) >= 4, 'в списке наших доменов видно, сколько их вообще известно');
    }

    public function testResumeCollectContinuesQueueAndMergesTable(): void
    {
        // Большой список обрабатывается частями: после остановки очередь помнит позицию, «Продолжить сбор»
        // берёт остаток запросов и ПОПОЛНЯЕТ таблицу, а с «очистить таблицу» оставляет только новую часть.
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $runDir = $dir . '/runs/resume';
        mkdir($runDir, 0777, true);
        @unlink($dir . '/runs/domains-base.txt');
        $queries = ['пластиковые окна', 'остекление балконов', 'двери входные'];
        $settings = static fn (array $extra = []): string => json_encode(array_merge([
            'queries' => $queries,
            'source' => 'xmlstock',
            'top' => 3,
            'dedupe_domain' => true,
            'allowed_tlds' => [],
            'skip_known' => false,
            'visit' => false,
            'preview_shots' => false,
        ], $extra), JSON_UNESCAPED_UNICODE);

        // Результаты прошлого прогона на диске: новый сбор их удаляет, продолжение — нет.
        mkdir($runDir . '/pages/7-стр/old.ru', 0777, true);
        mkdir($runDir . '/content/7-стр/old.ru', 0777, true);
        file_put_contents($runDir . '/pages/7-стр/old.ru/main.html', 'старая страница');
        file_put_contents($runDir . '/content/7-стр/old.ru/main.html', 'старая статья');
        file_put_contents($runDir . '/content.zip', 'PK старый архив');

        // Первая часть: сбор только по первому запросу (как будто остановили после него).
        file_put_contents($runDir . '/settings.json', $settings(['queries' => [$queries[0]]]));
        $first = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $first['code'], $first['out']);
        $s1 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same(['total' => 1, 'done' => 1, 'left' => 0], $s1['queue'], 'очередь пройдена целиком');
        Assert::false(is_dir($runDir . '/content/7-стр/old.ru'), 'новый сбор удалил прошлый контент — архив не смешается');
        Assert::false(is_dir($runDir . '/pages/7-стр/old.ru'), 'и прошлые страницы');
        Assert::false(is_file($runDir . '/content.zip'), 'и прошлый архив');
        Assert::contains('прежние страницы и контент удалены', (string) file_get_contents($runDir . '/run.log'));
        $batch1 = array_map(static fn ($s) => $s['host'], json_decode((string) file_get_contents($runDir . '/sites.json'), true)['sites']);
        Assert::true($batch1 !== [], 'первая часть собрала сайты');

        // Останов после первого запроса из трёх: очередь помнит позицию.
        file_put_contents($runDir . '/queue.json', json_encode(['queries' => $queries, 'done' => 1], JSON_UNESCAPED_UNICODE));
        file_put_contents($runDir . '/settings.json', $settings(['resume' => true]));
        mkdir($runDir . '/content/7-стр/part1.ru', 0777, true);
        file_put_contents($runDir . '/content/7-стр/part1.ru/main.html', 'статья первой части');
        $second = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $second['code'], $second['out']);
        $s2 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $s2['state'], $second['out']);
        Assert::same(['total' => 3, 'done' => 3, 'left' => 0], $s2['queue'], 'обработан остаток очереди');
        Assert::contains('продолжение с 2-го из 3', (string) file_get_contents($runDir . '/run.log'));
        Assert::true(is_file($runDir . '/content/7-стр/part1.ru/main.html'), 'продолжение сбора прошлую часть не трогает');
        $merged = array_map(static fn ($s) => $s['host'], json_decode((string) file_get_contents($runDir . '/sites.json'), true)['sites']);
        foreach ($batch1 as $host) {
            Assert::inArray($host, $merged, 'сайты первой части остались в таблице');
        }
        Assert::true(count($merged) > count($batch1), 'новая часть добавила сайты');
        Assert::same(count($merged), count(array_unique($merged)), 'без повторов');
        Assert::same(count($merged), $s2['sites_count']);

        // Повторное продолжение нечего обрабатывать — понятная ошибка, список не теряется.
        $third = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        $s3 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('error', $s3['state'], $third['out']);
        Assert::contains('уже обработаны', $s3['message']);
        Assert::same(count($merged), count(json_decode((string) file_get_contents($runDir . '/sites.json'), true)['sites']), 'sites.json не тронут');

        // «Продолжить сбор» с очисткой таблицы: в ней только новая часть (страницы на диске не трогаются).
        file_put_contents($runDir . '/queue.json', json_encode(['queries' => $queries, 'done' => 1], JSON_UNESCAPED_UNICODE));
        file_put_contents($runDir . '/settings.json', $settings(['resume' => true, 'reset_sites' => true]));
        $fourth = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $fourth['code'], $fourth['out']);
        $reset = array_map(static fn ($s) => $s['host'], json_decode((string) file_get_contents($runDir . '/sites.json'), true)['sites']);
        Assert::true(count($reset) < count($merged), 'в таблице только новая часть');
        Assert::same([], array_values(array_intersect($reset, array_diff($batch1, $reset))), 'сайты первой части в таблицу не вернулись');
    }

    public function testDownloadStageOpensCollectedSites(): void
    {
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-download-' . uniqid();
        $runDir = $dir . '/runs/dl';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [[
            'host' => 'okna-moskva.ru', 'domain' => 'okna-moskva.ru',
            'url' => "http://okna-moskva.ru:$port/page-1/", 'title' => 'T',
            'best_query' => 'окна', 'best_position' => 1, 'queries_count' => 1,
        ]]]));

        // нет собранных сайтов → ошибка
        $empty = $dir . '/runs/empty';
        mkdir($empty, 0777, true);
        file_put_contents($empty . '/settings.json', json_encode(['stage' => 'download', 'visit_driver' => 'curl']));
        $r0 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $empty . '/settings.json'], $dir);
        Assert::same('error', (json_decode((string) file_get_contents($empty . '/status.json'), true))['state']);

        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1"],
        ]));
        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        Assert::contains('Выгружено страниц: 1', $st['message']);
        Assert::contains('по страницам: 1 стр. — 1', $st['message'], 'разбивка по числу страниц в сообщении');
        // Чего не хватает: ключевые страницы, на которые ссылается контент (у тестового сайта их нет).
        Assert::same(['registracia' => 1, 'vhod' => 1, 'zerkalo' => 1, 'bonus' => 1, 'app' => 1, 'slots' => 1], $st['key_pages']);
        Assert::contains('не хватает: регистрация — 1', $st['message']);
        Assert::same(['registracia', 'vhod', 'zerkalo', 'bonus', 'app', 'slots'], $st['sites'][0]['key_missing'], 'строка таблицы знает, чего не хватает');
        Assert::same([1 => 1], $st['page_histogram'], 'гистограмма в статусе');

        $sites = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        Assert::true(($sites['sites'][0]['visits'][0]['ok'] ?? false), 'страница сайта открыта и сохранена');
        Assert::true(is_file($runDir . '/pages/okna-moskva.ru/variant-1.html'));

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testDownloadStageMarksProblemSites(): void
    {
        // «Проблемные» по выгрузке: сайт, который отдаёт только витрину чужих офферов (и браузеру тоже),
        // так и не открылся — попадает в статистику проблемных со стадией «по выгрузке».
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-prob-' . uniqid();
        $runDir = $dir . '/runs/prob';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [[
            'host' => 'alwaysoffer.ru', 'domain' => 'alwaysoffer.ru',
            'url' => "http://alwaysoffer.ru:$port/", 'title' => 'T',
            'best_query' => 'к', 'best_position' => 1, 'queries_count' => 1,
        ]]]));
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'visit_resolve' => ["alwaysoffer.ru:$port:127.0.0.1"],
        ]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        // Гистограмма проблемных в статусе: один сайт, стадия «по выгрузке», причина — витрина офферов.
        Assert::same(1, (int) ($st['problem_histogram']['sites'] ?? 0), $run['out']);
        Assert::same(1, (int) ($st['problem_histogram']['download']['offer_wall'] ?? 0), 'офферная витрина — по выгрузке');
        Assert::contains('проблемных: 1', $st['message']);
        // Строка таблицы несёт флаг «выгружен» и коды проблем — по ним рисуется вкладка «Проблемные».
        $row = $st['sites'][0];
        Assert::true($row['downloaded'] ?? false, 'сайт прошёл стадию выгрузки');
        Assert::same(['offer_wall'], $row['problems'] ?? null, 'код проблемы в строке');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testDownloadStageReportsTemplateTypes(): void
    {
        // После открытия страниц статус несёт разбивку по типу вёрстки, а строки таблицы — тип каждого сайта:
        // по нему панель оставляет в таблице только выбранные категории (7–9 / 12–15 / без категории).
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-tpl-' . uniqid();
        $runDir = $dir . '/runs/tpl';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        $rows = [];
        foreach (['tpl7.ru', 'tpl12.ru', 'okna-moskva.ru'] as $i => $host) {
            $rows[] = ['host' => $host, 'domain' => $host, 'url' => "http://$host:$port/", 'title' => 'T', 'best_query' => 'q', 'best_position' => $i + 1, 'queries_count' => 1];
        }
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => $rows]));
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'visit_resolve' => ["tpl7.ru:$port:127.0.0.1", "tpl12.ru:$port:127.0.0.1", "okna-moskva.ru:$port:127.0.0.1"],
        ]));
        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        Assert::same(['pages7' => 1, 'pages12' => 1, 'other' => 1], $st['template_histogram'], 'разбивка по типу вёрстки в статусе');
        $byHost = [];
        foreach ($st['sites'] as $row) {
            $byHost[$row['host']] = $row;
        }
        Assert::same('pages7', $byHost['tpl7.ru']['template']);
        Assert::same('12–15 стр.', $byHost['tpl12.ru']['template_label']);
        Assert::same('other', $byHost['okna-moskva.ru']['template'], 'обычный сайт — без категории');
        Assert::contains('Итого по типу вёрстки: 7–9 стр. — 1, 12–15 стр. — 1, без категории — 1', (string) file_get_contents($runDir . '/run.log'));

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testDownloadStageExcludesRemovedHosts(): void
    {
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-dlx-' . uniqid();
        $runDir = $dir . '/runs/dlx';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        // Два собранных сайта; один убран крестиком (приходит в exclude_hosts) и качаться не должен.
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            ['host' => 'okna-moskva.ru', 'domain' => 'okna-moskva.ru', 'url' => "http://okna-moskva.ru:$port/page-1/", 'title' => 'T', 'best_query' => 'окна', 'best_position' => 1, 'queries_count' => 1],
            ['host' => 'skip-me.ru', 'domain' => 'skip-me.ru', 'url' => "http://skip-me.ru:$port/page-1/", 'title' => 'T2', 'best_query' => 'окна', 'best_position' => 2, 'queries_count' => 1],
        ]]));
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'exclude_hosts' => ['skip-me.ru'],
            'visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1"],
        ]));
        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        Assert::contains('Выгружено страниц: 1', $st['message']);
        Assert::true(is_file($runDir . '/pages/okna-moskva.ru/variant-1.html'), 'оставшийся сайт выгружен');
        Assert::false(is_dir($runDir . '/pages/skip-me.ru'), 'убранный сайт не выгружался');
        $sites = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        $hosts = array_map(static fn ($s) => $s['host'], $sites['sites']);
        Assert::same(['okna-moskva.ru'], $hosts, 'в sites.json остались только оставшиеся сайты');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testDownloadStageOpensOnlyTableSites(): void
    {
        // Панель присылает only — сайты, которые сейчас в таблице. Сайт, которого в таблице нет (например, сверх
        // лимита строк), не выгружается и в итоговый sites.json не попадает; журнал говорит, что пропущено.
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-dlonly-' . uniqid();
        $runDir = $dir . '/runs/dlonly';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        $rows = [];
        foreach (['okna-moskva.ru', 'tpl7.ru', 'hidden.ru'] as $i => $host) {
            $rows[] = ['host' => $host, 'domain' => $host, 'url' => "http://$host:$port/", 'title' => 'T', 'best_query' => 'q', 'best_position' => $i + 1, 'queries_count' => 1];
        }
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => $rows]));
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'only' => ['okna-moskva.ru', 'tpl7.ru'],
            'visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1", "tpl7.ru:$port:127.0.0.1", "hidden.ru:$port:127.0.0.1"],
        ]));
        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        Assert::same(2, $st['sites_count'], 'в статусе — число сайтов списка');
        Assert::true(is_file($runDir . '/pages/okna-moskva.ru/variant-1.html') && is_file($runDir . '/pages/tpl7.ru/variant-1.html'), 'сайты из таблицы выгружены');
        Assert::false(is_dir($runDir . '/pages/hidden.ru'), 'сайт, которого нет в таблице, не выгружался');
        $hosts = array_map(static fn ($s) => $s['host'], json_decode((string) file_get_contents($runDir . '/sites.json'), true)['sites']);
        Assert::same(['okna-moskva.ru', 'tpl7.ru'], $hosts, 'sites.json — ровно список таблицы');
        Assert::contains('в таблице нет — не выгружаем (hidden.ru)', (string) file_get_contents($runDir . '/run.log'));

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testRedownloadClearsPreviousPages(): void
    {
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-redl-' . uniqid();
        $runDir = $dir . '/runs/redl';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            ['host' => 'okna-moskva.ru', 'domain' => 'okna-moskva.ru', 'url' => "http://okna-moskva.ru:$port/page-1/", 'title' => 'T', 'best_query' => 'окна', 'best_position' => 1, 'queries_count' => 1],
            ['host' => 'okna-company.com', 'domain' => 'okna-company.com', 'url' => "http://okna-company.com:$port/page-2/", 'title' => 'T2', 'best_query' => 'окна', 'best_position' => 2, 'queries_count' => 1],
        ]]));
        $settings = static fn (array $extra): string => (string) json_encode(array_merge([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1", "okna-company.com:$port:127.0.0.1"],
        ], $extra));

        // Первая выгрузка — обе страницы скачаны.
        file_put_contents($runDir . '/settings.json', $settings([]));
        $r1 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $r1['code'], $r1['out']);
        Assert::true(is_dir($runDir . '/pages/okna-moskva.ru'));
        Assert::true(is_dir($runDir . '/pages/okna-company.com'));

        // Повторная выгрузка с исключением одного сайта — папка исключённого исчезает (его пере-сбор чистый).
        file_put_contents($runDir . '/settings.json', $settings(['exclude_hosts' => ['okna-company.com']]));
        $r2 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $r2['code'], $r2['out']);
        Assert::true(is_dir($runDir . '/pages/okna-moskva.ru'), 'оставшийся сайт заново выгружен');
        Assert::false(is_dir($runDir . '/pages/okna-company.com'), 'старая папка исключённого сайта удалена при повторной выгрузке');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testRetryReDownloadsOnlyFailedKeepsRest(): void
    {
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-retry-' . uniqid();
        $runDir = $dir . '/runs/retry';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            ['host' => 'okna-moskva.ru', 'domain' => 'okna-moskva.ru', 'url' => "http://okna-moskva.ru:$port/page-1/", 'title' => 'T', 'best_query' => 'окна', 'best_position' => 1, 'queries_count' => 1],
            ['host' => 'okna-company.com', 'domain' => 'okna-company.com', 'url' => "http://okna-company.com:$port/page-2/", 'title' => 'T2', 'best_query' => 'окна', 'best_position' => 2, 'queries_count' => 1],
        ]]));
        $settings = static fn (array $extra): string => (string) json_encode(array_merge(['stage' => 'download', 'visit_driver' => 'curl'], $extra));

        // Первая выгрузка — оба сайта доступны, оба ок.
        file_put_contents($runDir . '/settings.json', $settings(['visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1", "okna-company.com:$port:127.0.0.1"]]));
        $r1 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $r1['code'], $r1['out']);
        $by1 = [];
        foreach ((json_decode((string) file_get_contents($runDir . '/sites.json'), true))['sites'] as $x) {
            $by1[$x['host']] = $x;
        }
        Assert::true($by1['okna-moskva.ru']['visits'][0]['ok'] ?? false);
        Assert::true($by1['okna-company.com']['visits'][0]['ok'] ?? false);

        // Докачиваем только okna-moskva.ru. okna-company.com в этот раз НЕ резолвится: если бы докачка
        // его тронула — он бы упал. Значит, если он остался «ок» — его результат сохранён, а не перекачан.
        file_put_contents($runDir . '/settings.json', $settings(['retry_hosts' => ['okna-moskva.ru'], 'visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1"]]));
        $r2 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $r2['code'], $r2['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $r2['out']);
        // У okna-moskva.ru все страницы уже ок — добирать нечего, и сообщение честно об этом говорит.
        Assert::contains('нечего добирать', $st['message']);
        $by2 = [];
        foreach ((json_decode((string) file_get_contents($runDir . '/sites.json'), true))['sites'] as $x) {
            $by2[$x['host']] = $x;
        }
        Assert::true($by2['okna-moskva.ru']['visits'][0]['ok'] ?? false, 'докачанный сайт снова ок');
        Assert::true($by2['okna-company.com']['visits'][0]['ok'] ?? false, 'нетронутый сайт сохранил свой результат');
        Assert::true(is_dir($runDir . '/pages/okna-moskva.ru'), 'страницы докачанного на месте');
        Assert::true(is_dir($runDir . '/pages/okna-company.com'), 'страницы нетронутого сохранены');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testRetryStageRecoversFailedCrawlPage(): void
    {
        // Обход (crawl) localeretry.ru: главная и /about открываются, а /ru/app отдаёт 404 (упал).
        // Докачка должна добрать эту страницу без языкового префикса (/app) и обновить sites.json.
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-retryc-' . uniqid();
        $runDir = $dir . '/runs/retryc';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            ['host' => 'localeretry.ru', 'domain' => 'localeretry.ru', 'url' => "http://localeretry.ru:$port/", 'title' => 'T', 'best_query' => 'к', 'best_position' => 1, 'queries_count' => 1],
        ]]));
        $settings = static fn (array $extra): string => (string) json_encode(array_merge([
            'stage' => 'download', 'visit_driver' => 'curl', 'crawl' => true, 'max_pages' => 10,
            'visit_resolve' => ["localeretry.ru:$port:127.0.0.1"],
        ], $extra));

        // Первый обход: /ru/app падает (404).
        file_put_contents($runDir . '/settings.json', $settings([]));
        $r1 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $r1['code'], $r1['out']);
        $visits1 = (json_decode((string) file_get_contents($runDir . '/sites.json'), true))['sites'][0]['visits'];
        $failed = array_values(array_filter($visits1, static fn (array $v): bool => !($v['ok'] ?? false) && str_contains((string) ($v['url'] ?? ''), '/ru/app')));
        Assert::same(1, count($failed), 'после обхода /ru/app помечен как упавший: ' . $r1['out']);
        $st1 = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same(1, (int) ($st1['sites'][0]['pages_404'] ?? -1), 'в строке сайта — число страниц с 404 (для кнопки «Убрать с 404 > N»)');
        Assert::same(2, (int) ($st1['sites'][0]['pages_ok'] ?? -1));

        // Докачка этого сайта: страница добирается без /ru → /app.
        file_put_contents($runDir . '/settings.json', $settings(['retry_hosts' => ['localeretry.ru']]));
        $r2 = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $r2['code'], $r2['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $r2['out']);
        Assert::contains('Докачано', $st['message'], $r2['out']);
        $visits2 = (json_decode((string) file_get_contents($runDir . '/sites.json'), true))['sites'][0]['visits'];
        $okCount = count(array_filter($visits2, static fn (array $v): bool => $v['ok'] ?? false));
        Assert::same(3, $okCount, 'после докачки открыты все 3 страницы (главная, about, app): ' . $r2['out']);
        Assert::true(is_file($runDir . '/pages/3-стр/localeretry.ru/app.html'), 'добранная страница /app лежит в бакете 3-стр');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testPreviewStageRetriesSitesWithoutPreview(): void
    {
        // «Перепробовать без превью»: сайт, который не пустил робота (403 + заглушка антибота),
        // открывается при повторном заходе под браузером — и в таблице перестаёт быть пустым.
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-prevretry-' . uniqid();
        $runDir = $dir . '/runs/prev';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            [
                'host' => 'botblock.ru', 'domain' => 'botblock.ru', 'url' => "http://botblock.ru:$port/",
                'title' => 'T', 'best_query' => 'к', 'best_position' => 1, 'queries_count' => 1,
                'visits' => [[
                    'variant' => 1, 'url' => "http://botblock.ru:$port/", 'ok' => false, 'proxy' => 'direct',
                    'user_agent' => 'Mozilla/5.0 (compatible; YandexBot/3.0)',
                    'error' => 'заблокировано (антибот/Cloudflare, HTTP 403)', 'status' => 403,
                    'html_file' => '', 'screenshot_file' => '',
                ]],
            ],
        ]]));
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'preview',
            'visit_driver' => 'curl',
            'only' => ['botblock.ru'],
            'visit_resolve' => ["botblock.ru:$port:127.0.0.1"],
        ]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);

        $status = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $status['state'], $run['out']);
        Assert::contains('Перепробовано сайтов без превью: 1, открылось 1', $status['message'], $run['out']);
        Assert::same(1, (int) ($status['sites'][0]['pages_ok'] ?? 0), 'в таблице сайт больше не пустой');

        $saved = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        $visits = $saved['sites'][0]['visits'];
        Assert::same(1, count($visits), 'удачный заход заменил неудачный визит');
        Assert::true($visits[0]['ok'], 'страница открыта: ' . $run['out']);
        Assert::false(str_contains((string) $visits[0]['user_agent'], 'YandexBot'), 'открылось под браузером');
        Assert::true(is_file($runDir . '/preview/botblock.ru/variant-1.html'), 'страница сохранена в preview');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testOwnMarkersFromPanelSettingsMarkSite(): void
    {
        // Метки наших шаблонов задаются В ПАНЕЛИ («Настройки» → «Метки наших шаблонов»), а не правкой
        // файла на диске: пользователь работает только через веб-интерфейс. Метка домена НАШЕГО
        // редиректора должна ловить дор по промежуточному хопу цепочки редиректов.
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-ownmark-' . uniqid();
        $runDir = $dir . '/runs/own';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            [
                'host' => 'ourdoor.ru', 'domain' => 'ourdoor.ru', 'url' => "http://ourdoor.ru:$port/",
                'title' => 'T', 'best_query' => 'к', 'best_position' => 1, 'queries_count' => 1,
            ],
        ]]));
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'preview',
            'visit_driver' => 'curl',
            'only' => ['ourdoor.ru'],
            'own_markers' => ['redir-hub.ru'], // домен нашего редиректора — промежуточный адрес
            'visit_resolve' => [
                "ourdoor.ru:$port:127.0.0.1",
                "redir-hub.ru:$port:127.0.0.1",
                "other-domain.ru:$port:127.0.0.1",
            ],
        ]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);

        $saved = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        Assert::true((bool) ($saved['sites'][0]['own'] ?? false), 'сайт помечен нашим по метке из настроек панели: ' . $run['out']);

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testDownloadHonorsRemovedJsonWithoutExcludeHosts(): void
    {
        // Сайт убран в панели (removed.json), но exclude_hosts не передан (старая вкладка, сбитый список):
        // выгрузка всё равно его не качает и не возвращает в sites.json.
        $port = FakeServer::port('local');
        $dir = sys_get_temp_dir() . '/yandex-sites-rmj-' . uniqid();
        $runDir = $dir . '/runs/rmj';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            ['host' => 'okna-moskva.ru', 'domain' => 'okna-moskva.ru', 'url' => "http://okna-moskva.ru:$port/page-1/", 'title' => 'T', 'best_query' => 'окна', 'best_position' => 1, 'queries_count' => 1],
            ['host' => 'okna-company.com', 'domain' => 'okna-company.com', 'url' => "http://okna-company.com:$port/page-2/", 'title' => 'T2', 'best_query' => 'окна', 'best_position' => 2, 'queries_count' => 1],
        ]]));
        \YandexSites\Support\RemovedSites::remove($runDir, ['okna-company.com']);
        file_put_contents($runDir . '/settings.json', json_encode([
            'stage' => 'download',
            'visit_driver' => 'curl',
            'visit_resolve' => ["okna-moskva.ru:$port:127.0.0.1", "okna-company.com:$port:127.0.0.1"],
        ]));
        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        Assert::false(is_dir($runDir . '/pages/okna-company.com'), 'убранный сайт не выгружался');
        $sites = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
        Assert::same(['okna-moskva.ru'], array_map(static fn ($s) => $s['host'], $sites['sites']), 'убранный не вернулся в sites.json');
        Assert::same(['okna-moskva.ru'], array_map(static fn ($s) => $s['host'], $st['sites']), 'и в статусе его нет');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    public function testPanelRemoveAndRestoreEndpoints(): void
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-panel-rm-' . uniqid();
        $runDir = $dir . '/runs/current';
        mkdir($runDir . '/pages/2-стр/gone.ru', 0777, true);
        file_put_contents($runDir . '/pages/2-стр/gone.ru/main.html', 'x');
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [['host' => 'gone.ru', 'domain' => 'gone.ru'], ['host' => 'stay.ru', 'domain' => 'stay.ru']]]));
        file_put_contents($runDir . '/status.json', json_encode(['state' => 'done', 'sites' => [['host' => 'gone.ru'], ['host' => 'stay.ru']]]));

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-rm.log';
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

            $r = json_decode((string) $this->http('POST', $base . '/api/remove', ['hosts' => ['gone.ru']]), true);
            Assert::true($r['ok'] ?? false, json_encode($r));
            Assert::same(1, $r['removed_total']);
            $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
            Assert::same(['gone.ru'], $state['removed'], 'сервер отдаёт список убранных');
            Assert::same(['stay.ru'], array_map(static fn ($s) => $s['host'], $state['status']['sites']), 'таблица без убранного сразу');
            Assert::false(is_dir($runDir . '/pages/2-стр/gone.ru'), 'папки убранного уехали из pages/');

            $r = json_decode((string) $this->http('POST', $base . '/api/restore', []), true);
            Assert::true($r['ok'] ?? false, json_encode($r));
            $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
            Assert::same([], $state['removed']);
            Assert::same(2, count($state['status']['sites']), 'вернуть все — строка вернулась');

            // Без status.json (обновили страницу во время выгрузки, перезапустили панель) таблица берётся из sites.json.
            @unlink($runDir . '/status.json');
            $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
            $hosts = array_map(static fn ($s) => $s['host'], $state['status']['sites']);
            sort($hosts);
            Assert::same(['gone.ru', 'stay.ru'], $hosts, 'таблица из sites.json, когда статуса нет');
            Assert::true($state['status']['sites_from_file'] ?? false);
            Assert::true(is_dir($runDir . '/pages/2-стр/gone.ru'), 'и папки вернулись');
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testCollectWritesHistoryAndStatsEndpoint(): void
    {
        // Вкладка «Статистика»: сбор дописывает строку в runs/history.json (дата, сколько доменов,
        // сколько из них доров, повторы доров, зоны доров), /api/history отдаёт её вместе с итогом,
        // /download?file=history — те же данные в CSV.
        $port = FakeServer::port();
        $dir = $this->projectDir($port);
        $this->projectDirReset($port);
        $runDir = $dir . '/runs/hist';
        mkdir($runDir, 0777, true);
        @unlink($dir . '/runs/domains-base.txt');
        @unlink($dir . '/runs/history.json');
        $settings = json_encode([
            'queries' => ['пластиковые окна', 'остекление балконов'],
            'source' => 'xmlstock',
            'top' => 0,
            'dedupe_domain' => true,
            'allowed_tlds' => [],
            'skip_known' => true,
            'visit' => false,
            'preview_shots' => false,
        ]);

        file_put_contents($runDir . '/settings.json', $settings);
        $first = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $first['code'], $first['out']);
        // Повторный сбор теми же запросами: домены уже в базе — это и есть «повторы».
        file_put_contents($runDir . '/settings.json', $settings);
        $second = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $second['code'], $second['out']);

        $records = json_decode((string) file_get_contents($dir . '/runs/history.json'), true);
        Assert::same(2, count($records), 'по записи на каждый сбор');
        Assert::true($records[1]['sites'] > 0, 'первый сбор собрал домены');
        Assert::same(0, $records[0]['sites'], 'второй сбор ничего нового не взял');
        Assert::true($records[0]['repeats'] > 0, 'и посчитал повторы');
        Assert::same($records[1]['sites'], $records[1]['roots'] + $records[1]['doors'], 'корневые + доры = все домены');
        // Дедуп по домену включён: раньше Site::$host хранил регистрируемый домен и доров выходило 0.
        Assert::true($records[1]['doors'] > 0, 'сайты на поддоменах посчитаны как доры даже при дедупе по домену');
        Assert::true($records[1]['zones'] !== [], 'зоны доров посчитаны');
        Assert::true($records[0]['repeats_doors'] <= $records[0]['repeats'], 'повторов-доров не больше, чем повторов всего');
        Assert::false(isset($records[0]['queries']), 'запросы в статистику не пишем');
        $log = (string) file_get_contents($runDir . '/run.log');
        Assert::contains('За этот сбор:', $log);
        Assert::contains('сайтов (один на домен)', $log, 'в журнале воронка целиком');
        Assert::contains('Срезано по причинам (сайтов):', $log);
        // Воронка должна СХОДИТЬСЯ: сайты выдачи = отобрано + срезанное по причинам. Это и есть ответ
        // на «куда делись домены»; отдельно проверяем, что причины названы по сайтам, а не по строкам.
        foreach ([0, 1] as $i) {
            Assert::same(
                (int) $records[$i]['unique_sites'],
                (int) $records[$i]['sites'] + \YandexSites\Support\CollectHistory::cutTotal($records[$i]['cut']),
                "воронка сходится в записи $i",
            );
        }
        Assert::true($records[1]['unique_sites'] > 0, 'сайты выдачи посчитаны');
        Assert::true($records[1]['found'] >= $records[1]['unique_sites'], 'адресов не меньше, чем сайтов после группировки');
        Assert::true($records[0]['cut']['seen_before']['sites'] > 0, 'повторный сбор срезан как «уже в базе»');
        // Доля доров считается от ВСЕЙ выдачи, а не от того, что осталось после фильтров.
        Assert::true($records[1]['found'] >= $records[1]['sites'], 'доменов в выдаче не меньше, чем отобрано');
        Assert::same($records[1]['unique_sites'], $records[1]['found_doors'] + $records[1]['found_roots'], 'доры + корневые = масса сайтов');
        Assert::true($records[1]['found_doors'] > 0, 'доры в выдаче найдены');
        // Результатов в выдаче всегда не меньше, чем разных доменов: сайт попадается в нескольких запросах.
        Assert::true($records[1]['results'] >= $records[1]['found'], 'строк выдачи не меньше, чем доменов');
        // Запись создаётся сразу после отбора доменов и в конце сбора уточняется по её id —
        // на каждый сбор всё равно ровно одна строка, без дублей.
        Assert::true(($records[0]['id'] ?? '') !== '', 'у записи есть id для уточнения в конце сбора');
        Assert::true(($records[1]['id'] ?? '') !== ($records[0]['id'] ?? ''), 'у каждого сбора свой id');
        Assert::false($records[0]['stopped'], 'итоговый флаг остановки проставлен');

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-hist.log';
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

            $hist = json_decode((string) $this->http('GET', $base . '/api/history'), true);
            Assert::true($hist['ok'] ?? false, json_encode($hist, JSON_UNESCAPED_UNICODE));
            Assert::same(2, count($hist['records']), '/api/history отдаёт обе записи');
            Assert::same(2, $hist['totals']['runs']);
            Assert::true($hist['totals']['sites'] > 0, 'итог по всем сборам посчитан');
            Assert::true(isset($hist['totals']['doors_percent']), 'доля доров в итоге');
            Assert::true($hist['totals']['repeats_doors'] <= $hist['totals']['repeats']);

            Assert::true(($hist['totals']['unique_sites'] ?? 0) > 0, 'масса сайтов в итоге');
            Assert::true(($hist['totals']['cut_total'] ?? 0) > 0, 'срезанное в итоге посчитано');
            Assert::same(
                (int) $hist['totals']['unique_sites'],
                (int) $hist['totals']['sites'] + (int) $hist['totals']['cut_total'],
                'итог по всем сборам тоже сходится',
            );

            $csv = (string) $this->http('GET', $base . '/download?file=history');
            Assert::contains('Результатов в выдаче', $csv, 'CSV истории скачивается');
            Assert::contains('Сайтов в выдаче', $csv);
            Assert::contains('Что срезано', $csv);
            Assert::contains('Доров из них', $csv);
            Assert::contains('Зоны доров', $csv);
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testPanelBackfillsTemplateTypesAndReportsVersion(): void
    {
        // После обновления скрипта прошлый сбор (визиты без поля template) получает типы вёрстки по сохранённому
        // HTML при первом же опросе — новый сбор не нужен; /api/state отдаёт версию кода для шапки панели.
        $dir = sys_get_temp_dir() . '/yandex-sites-panel-tpl-' . uniqid();
        $runDir = $dir . '/runs/current';
        mkdir($runDir . '/preview/old7.ru', 0777, true);
        mkdir($runDir . '/preview/old12.ru', 0777, true);
        file_put_contents($runDir . '/preview/old7.ru/variant-1.html', '<div class="filters-section"></div><div class="promo-text"></div><div class="tags-cloud"></div>');
        file_put_contents($runDir . '/preview/old12.ru/variant-1.html', '<div id="bonusPopup"></div><div id="winNotifications"></div><div id="reserved-aux"></div>');
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        $row = static fn (string $host): array => ['host' => $host, 'domain' => $host, 'url' => "https://$host/", 'visits' => [
            ['variant' => 1, 'url' => "https://$host/", 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$runDir/preview/$host/variant-1.html", 'screenshot_file' => ''],
        ]];
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [$row('old7.ru'), $row('old12.ru')]]));
        // Статус прошлой версии: строки таблицы без поля template.
        file_put_contents($runDir . '/status.json', json_encode(['state' => 'done', 'phase' => 'done', 'sites' => [['host' => 'old7.ru', 'pages_ok' => 1, 'pages_total' => 1], ['host' => 'old12.ru', 'pages_ok' => 1, 'pages_total' => 1]]]));

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-tpl.log';
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
            Assert::same(\YandexSites\Cli\Application::VERSION, $state['version'], 'панель отдаёт версию кода');
            Assert::same(\YandexSites\Cli\Application::VERSION_DATE, $state['version_date']);
            Assert::same($dir, $state['project_dir'], 'папка проекта для шапки панели');
            $types = [];
            foreach ($state['status']['sites'] as $r) {
                $types[$r['host']] = $r['template'];
            }
            Assert::same(['old7.ru' => 'pages7', 'old12.ru' => 'pages12'], $types, 'типы дописаны по сохранённому HTML');
            $saved = json_decode((string) file_get_contents($runDir . '/sites.json'), true);
            Assert::same('pages7', $saved['sites'][0]['visits'][0]['template'], 'типы записаны в sites.json');
            $status = json_decode((string) file_get_contents($runDir . '/status.json'), true);
            Assert::same('pages12', $status['sites'][1]['template'], 'и в status.json — следующий опрос ничего не пересобирает');
            Assert::same('done', $status['state'], 'остальной статус сохранён');
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testHistoryCountsOwnSitesForOldRecords(): void
    {
        // Наши шаблоны в статистике: признак «наш» ставится по меткам в HTML на превью-визите, поэтому
        // в записях до 1.15.0 такого числа нет. /api/history дописывает его по текущему sites.json —
        // статистика прошлого сбора показывает наши сразу после обновления, без нового сбора.
        $dir = sys_get_temp_dir() . '/yandex-sites-panel-own-' . uniqid();
        $runDir = $dir . '/runs/current';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        $row = static fn (string $host, bool $own): array => ['host' => $host, 'domain' => $host, 'url' => "https://$host/", 'own' => $own];
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            $row('chuzhoy.ru', false),
            $row('nash.ru', true),
            $row('kush.example.com', false),
            $row('esche-nash.ru', true),
        ]]));
        file_put_contents($dir . '/runs/history.json', json_encode([
            ['id' => 'old', 'date' => '2026-09-15T10:00:00+00:00', 'results' => 40, 'found' => 30, 'found_doors' => 10, 'found_roots' => 20, 'sites' => 4, 'doors' => 1, 'roots' => 3, 'zones' => ['com' => 10], 'repeats' => 0, 'repeats_doors' => 0, 'base_domains' => 4],
        ]));
        // Та же запись старой версии не знает и про воронку — зато рядом лежит results.csv того же
        // сбора (40 строк, 30 адресов): по нему панель досчитывает сайты выдачи и что срезали фильтры.
        $csv = "query;page;position;host;url;title;snippet;result\n";
        foreach (['chuzhoy.ru', 'nash.ru', 'kush.example.com', 'esche-nash.ru'] as $host) {
            for ($i = 1; $i <= 3; $i++) {
                $csv .= sprintf("окна %d;1;%d;%s;https://%s/;т;с;selected\n", $i, $i, $host, $host);
            }
        }
        for ($i = 1; $i <= 26; $i++) {
            $host = sprintf('sub%d.junk%d.ru', $i, $i);
            $csv .= sprintf("окна;1;%d;%s;https://%s/;т;с;domain_scope\n", $i, $host, $host);
            if ($i <= 2) {
                $csv .= sprintf("двери;1;%d;%s;https://%s/;т;с;domain_scope\n", $i, $host, $host);
            }
        }
        file_put_contents($runDir . '/results.csv', $csv);

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-own.log';
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

            $hist = json_decode((string) $this->http('GET', $base . '/api/history'), true);
            Assert::true($hist['ok'] ?? false, json_encode($hist, JSON_UNESCAPED_UNICODE));
            Assert::same(2, $hist['records'][0]['own'], 'наши посчитаны по sites.json');
            Assert::same(30, $hist['records'][0]['unique_sites'], 'сайты выдачи досчитаны по results.csv');
            Assert::same(26, $hist['records'][0]['cut']['domain_scope']['sites'] ?? 0, 'и видно, что срезал фильтр типа домена');
            Assert::same(
                30,
                (int) $hist['records'][0]['sites'] + \YandexSites\Support\CollectHistory::cutTotal($hist['records'][0]['cut']),
                'воронка старой записи сходится после пересчёта',
            );
            Assert::same(1, $hist['records'][0]['doors'], 'посчитанные доры не тронуты');
            // Зоны пересчитываются вместе с дорами (иначе они бы противоречили новому числу):
            // .com — это kush.example.com, .ru — 26 срезанных поддоменов.
            Assert::same(27, $hist['records'][0]['found_doors'], 'доры пересчитаны по сайтам выдачи');
            Assert::same(1, $hist['records'][0]['zones']['com'] ?? 0, 'зона дора из отобранного');
            Assert::same(26, $hist['records'][0]['zones']['ru'] ?? 0, 'зоны срезанных доров тоже в статистике');
            Assert::same(2, $hist['totals']['own'], 'наши в итоге по всем сборам');
            // Доля наших считается от ОБЩЕГО числа доров в выдаче (27), а не от четырёх отобранных сайтов.
            Assert::same(7.4, (float) $hist['totals']['own_percent'], 'доля наших — от доров выдачи');
            Assert::same(2, \YandexSites\Support\CollectHistory::load($dir . '/runs')[0]['own'], 'дописано в историю на диске');

            $csv = (string) $this->http('GET', $base . '/download?file=history');
            Assert::contains('Наших сайтов', $csv, 'наши есть и в CSV истории');
            Assert::contains('Доля наших', $csv);
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testResetBaseWipesRunFiles(): void
    {
        // «Очистить базу и файлы»: база доменов + все рабочие файлы прогона (страницы, контент, превью,
        // списки, очередь, статус). Настройки и запросы остаются, следующий сбор начинается с нуля.
        $dir = sys_get_temp_dir() . '/yandex-sites-panel-reset-' . uniqid();
        $runDir = $dir . '/runs/current';
        mkdir($runDir . '/pages/7-стр/a.ru', 0777, true);
        mkdir($runDir . '/content/7-стр/a.ru', 0777, true);
        mkdir($runDir . '/preview/a.ru', 0777, true);
        mkdir($runDir . '/removed/pages/1-стр/b.ru', 0777, true);
        file_put_contents($runDir . '/pages/7-стр/a.ru/main.html', 'x');
        file_put_contents($runDir . '/content/7-стр/a.ru/main.html', 'x');
        file_put_contents($runDir . '/preview/a.ru/variant-1.png', 'x');
        file_put_contents($runDir . '/removed/pages/1-стр/b.ru/main.html', 'x');
        foreach (['sites.json', 'sites.csv', 'domains.txt', 'results.csv', 'queue.json', 'removed.json', 'status.json', 'queries-unique.txt'] as $f) {
            file_put_contents($runDir . '/' . $f, '{}');
        }
        file_put_contents($runDir . '/settings.json', json_encode(['queries' => ['окна']], JSON_UNESCAPED_UNICODE));
        file_put_contents($dir . '/runs/domains-base.txt', "a.ru\nb.ru\n");
        // История сборов НЕ часть базы: полный сброс её не трогает, для неё отдельная кнопка.
        file_put_contents($dir . '/runs/history.json', json_encode([['date' => '2026-09-15T10:00:00+00:00', 'sites' => 5, 'doors' => 2]]));
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-reset.log';
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
            Assert::same(2, (json_decode((string) $this->http('GET', $base . '/api/state'), true))['base_domains']);

            $r = json_decode((string) $this->http('POST', $base . '/api/reset-base', []), true);
            Assert::true($r['ok'] ?? false, json_encode($r));
            Assert::same(4, $r['dirs'], 'удалены pages, content, preview, removed');
            Assert::true(($r['files'] ?? 0) >= 12, 'удалены файлы папок и списки: ' . json_encode($r));
            foreach (['pages', 'content', 'preview', 'removed'] as $sub) {
                Assert::false(is_dir($runDir . '/' . $sub), "папка $sub удалена");
            }
            foreach (['sites.json', 'results.csv', 'queue.json', 'status.json'] as $f) {
                Assert::false(is_file($runDir . '/' . $f), "файл $f удалён");
            }
            Assert::true(is_file($runDir . '/settings.json'), 'настройки и запросы на месте');
            $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
            Assert::same(0, $state['base_domains'], 'база доменов очищена');
            Assert::same(['total' => 0, 'done' => 0, 'left' => 0], $state['queue'], 'очередь запросов сброшена');
            Assert::same(0, $state['content_files']);
            Assert::true(empty($state['status']['sites']), 'таблица пуста');
            // Статистика сборов ПЕРЕЖИВАЕТ очистку базы: это летопись, её чистит своя кнопка.
            Assert::same(0, $r['history'] ?? -1, 'очистка базы записей статистики не трогает');
            Assert::true(is_file($dir . '/runs/history.json'), 'файл истории на месте');
            $hist = json_decode((string) $this->http('GET', $base . '/api/history'), true);
            Assert::same(1, count($hist['records']), 'запись сбора осталась во вкладке статистики');

            // Отдельная кнопка «очистить статистику»: база и файлы остаются, уходит только история.
            file_put_contents($dir . '/runs/history.json', json_encode([
                ['date' => '2026-09-16T10:00:00+00:00', 'sites' => 7, 'doors' => 3],
                ['date' => '2026-09-15T10:00:00+00:00', 'sites' => 5, 'doors' => 2],
            ]));
            file_put_contents($dir . '/runs/domains-base.txt', "c.ru\n");
            $rh = json_decode((string) $this->http('POST', $base . '/api/reset-history', []), true);
            Assert::true($rh['ok'] ?? false, json_encode($rh));
            Assert::same(2, $rh['records'], 'удалены обе записи');
            Assert::false(is_file($dir . '/runs/history.json'), 'история удалена');
            Assert::same(1, (json_decode((string) $this->http('GET', $base . '/api/state'), true))['base_domains'], 'база доменов не тронута');
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testContentArchiveDownload(): void

    {
        // «Скачать архив контента»: /api/state считает очищенные статьи, /download?file=content отдаёт свежий zip
        // с папками N-стр/сайт/страница.html; без контента — 404 с понятным текстом.
        $dir = sys_get_temp_dir() . '/yandex-sites-panel-zip-' . uniqid();
        $runDir = $dir . '/runs/current';
        mkdir($runDir . '/content/7-стр/a.ru', 0777, true);
        mkdir($runDir . '/content/12-стр/b.ru', 0777, true);
        file_put_contents($runDir . '/content/7-стр/a.ru/main.html', '<h2>a</h2>');
        file_put_contents($runDir . '/content/7-стр/a.ru/vhod.html', '<p>v</p>');
        file_put_contents($runDir . '/content/12-стр/b.ru/main.html', '<h2>b</h2>');
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-zip.log';
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
            Assert::same(3, $state['content_files'], 'статей на диске');
            Assert::same(2, $state['content_sites'], 'сайтов с контентом');

            $body = $this->http('GET', $base . '/download?file=content', null, $code);
            if ($code === 500) {
                Assert::skip('архив создать нечем: ' . $body);
            }
            Assert::same(200, $code, $body);
            Assert::same('PK', substr($body, 0, 2), 'ответ — zip');
            Assert::true(is_file($runDir . '/content.zip'), 'архив собран в runs/current');
            if (class_exists('ZipArchive')) {
                $zip = new \ZipArchive();
                Assert::true($zip->open($runDir . '/content.zip') === true);
                $names = [];
                for ($i = 0; $i < $zip->numFiles; $i++) {
                    $names[] = $zip->getNameIndex($i);
                }
                sort($names);
                Assert::same(['12-стр/b.ru/main.html', '7-стр/a.ru/main.html', '7-стр/a.ru/vhod.html'], $names, 'в архиве — папки N-стр/сайт/страница');
                $zip->close();
            }

            // Без контента — 404 с объяснением, а не пустой архив.
            \YandexSites\Content\SiteCleaner::rmTree($runDir . '/content');
            $body = $this->http('GET', $base . '/download?file=content', null, $code);
            Assert::same(404, $code);
            Assert::contains('Очищенного контента пока нет', $body);
            $state = json_decode((string) $this->http('GET', $base . '/api/state'), true);
            Assert::same(0, $state['content_files']);
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testQueryDupesEndpointAndDownloads(): void
    {
        // /api/query-dupes считает дубли по results.csv прошлого сбора (без нового сбора) в порядке списка из
        // settings.json, пишет queries-unique.txt / query-dupes.txt, которые отдаёт /download.
        $dir = sys_get_temp_dir() . '/yandex-sites-panel-qd-' . uniqid();
        $runDir = $dir . '/runs/current';
        mkdir($runDir, 0777, true);
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        $mk = static fn (string $q, int $pos, string $host): array => ['result' => new \YandexSites\Model\SearchResult($q, 0, $pos, "https://$host/", $host, 'T'), 'reason' => 'selected'];
        (new \YandexSites\Output\ReportWriter(';', true))->writeRawCsv([
            $mk('окна', 1, 'a.ru'), $mk('окна', 2, 'b.ru'),
            $mk('окна купить', 1, 'b.ru'), $mk('окна купить', 2, 'www.a.ru'),
            $mk('балконы', 1, 'c.ru'),
        ], $runDir . '/results.csv');
        file_put_contents($runDir . '/settings.json', json_encode(['queries' => ['окна купить', 'окна', 'балконы', 'пусто']], JSON_UNESCAPED_UNICODE));
        // Список доменов с 6+ брендами пишет сбор; здесь кладём его руками — проверяем отдачу панелью.
        file_put_contents($runDir . '/' . \YandexSites\Support\BrandDomains::FILE, \YandexSites\Support\BrandDomains::text([]));

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $panelPort = (int) substr($name, (int) strrpos($name, ':') + 1);
        $log = sys_get_temp_dir() . '/yandex-sites-panel-qd.log';
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
            Assert::true($state['has_results'], 'results.csv есть');
            Assert::true($state['results_stamp'] !== '', 'отпечаток файла результатов');

            $d = json_decode((string) $this->http('GET', $base . '/api/query-dupes'), true);
            Assert::true($d['ok'] ?? false, json_encode($d));
            Assert::same(['окна'], $d['duplicates'], 'порядок списка из settings.json: «окна купить» первым — остаётся, «окна» — дубль');
            Assert::same(['окна купить', 'балконы', 'пусто'], $d['unique']);
            Assert::same(['пусто'], $d['no_results']);
            Assert::same(['total' => 3, 'duplicates' => 1, 'groups' => 1, 'no_results' => 1], $d['summary']);
            Assert::same("окна купить\nбалконы\nпусто\n", $this->http('GET', $base . '/download?file=queries-unique'));
            // Список доменов с 6+ брендами пишется тем же сбором и отдаётся ссылкой под таблицей.
            Assert::contains('Доменов с несколькими брендами', $this->http('GET', $base . '/download?file=brand-domains'), 'список доменов с 6+ брендами скачивается');
            Assert::contains('оставлен: окна купить', $this->http('GET', $base . '/download?file=query-dupes'));

            unlink($runDir . '/results.csv');
            $d = json_decode((string) $this->http('GET', $base . '/api/query-dupes'), true);
            Assert::false($d['ok'], 'без results.csv — понятная ошибка');
            Assert::contains('сначала соберите', $d['error']);
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function testCleanStageRunsInBackgroundForKeptSitesOnly(): void
    {
        // «Очистить всё» — фоновый этап: чистит только оставленные (only минус exclude), убирает контент
        // исключённых, сохраняет таблицу и пишет прогресс/итог. Контент сайтов, которых в таблице сейчас
        // нет (обработанная ранее часть большого сбора), НЕ трогается — иначе прошлая работа пропадёт.
        $dir = sys_get_temp_dir() . '/yandex-sites-clean-' . uniqid();
        $runDir = $dir . '/runs/clean';
        $page = '<html><head><title>t</title></head><body><h1>Обзор</h1><p>Полезный текст статьи про бренд.</p><h3>Популярные запросы</h3></body></html>';
        foreach (['pages/2-стр/keep.ru' => ['main', 'about'], 'pages/1-стр/skip.ru' => ['main'], 'pages/1-стр/ex.ru' => ['main']] as $d => $names) {
            mkdir("$runDir/$d", 0777, true);
            foreach ($names as $n) {
                file_put_contents("$runDir/$d/$n.html", $page);
            }
        }
        mkdir("$runDir/content/9-стр/skip.ru", 0777, true);
        file_put_contents("$runDir/content/9-стр/skip.ru/old.html", 'очистка прошлой части сбора');
        mkdir("$runDir/content/3-стр/ex.ru", 0777, true);
        file_put_contents("$runDir/content/3-стр/ex.ru/old.html", 'очистка убранного сайта');
        file_put_contents($dir . '/config.php', '<?php return ["source"=>"xmlstock","xmlstock"=>["user"=>"u","key"=>"k"]];');
        file_put_contents($runDir . '/sites.json', json_encode(['sites' => [
            ['host' => 'keep.ru', 'domain' => 'keep.ru'], ['host' => 'skip.ru', 'domain' => 'skip.ru'], ['host' => 'ex.ru', 'domain' => 'ex.ru'],
        ]]));
        file_put_contents($runDir . '/settings.json', json_encode(['stage' => 'clean', 'only' => ['keep.ru', 'ex.ru'], 'exclude_hosts' => ['ex.ru']]));

        $run = $this->php([PROJECT_ROOT . '/bin/run-job.php', '--settings=' . $runDir . '/settings.json'], $dir);
        Assert::same(0, $run['code'], $run['out']);
        $st = json_decode((string) file_get_contents($runDir . '/status.json'), true);
        Assert::same('done', $st['state'], $run['out']);
        Assert::contains('Очищено: 1 сайтов, 2 стр.', $st['message']);
        Assert::true(is_file("$runDir/content/2-стр/keep.ru/main.html") && is_file("$runDir/content/2-стр/keep.ru/about.html"), 'оставленный сайт очищен в бакет по числу страниц');
        Assert::true(is_file("$runDir/content/9-стр/skip.ru/old.html"), 'контент сайта не из таблицы (прошлая часть сбора) остался');
        Assert::same(0, count(glob("$runDir/content/*/ex.ru") ?: []), 'контент исключённого сайта убран');
        Assert::same(1, count(glob("$runDir/content/*/skip.ru") ?: []), 'не-оставленный сайт заново не чистился');
        Assert::same(3, count($st['sites']), 'таблица после очистки на месте');
        Assert::same(1, (int) ($st['visit']['total'] ?? 0), 'прогресс считал только сайты к очистке');

        $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
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
            'xmlstock' => ['endpoint' => "http://127.0.0.1:$port/yandex/xml/", 'live_endpoint' => "http://127.0.0.1:$port/yandexlive/xml/", 'user' => 'u', 'key' => 'k'],
            'api' => ['delay_ms' => 0, 'retries' => 0],
            'search' => ['groups_on_page' => 15],
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

            $this->http('POST', $base . '/api/reset-base');
            Assert::same(0, (json_decode((string) $this->http('GET', $base . '/api/state'), true))['base_domains'], 'база доменов очищена');

            $start = json_decode((string) $this->http('POST', $base . '/api/start', [
                'queries' => ['пластиковые окна', 'остекление балконов'],
                'source' => 'xmlstock',
                'top' => 0,
                'dedupe_domain' => true,
                'visit' => false,
                'preview_shots' => false,
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

            // /api/site-pages — детали страниц сайта (раскрытие строки: какие страницы упали).
            file_put_contents($dir . '/runs/current/sites.json', json_encode(['sites' => [[
                'host' => 'kush.demo.buzz', 'domain' => 'demo.buzz', 'url' => 'http://kush.demo.buzz/',
                'visits' => [
                    ['url' => 'http://kush.demo.buzz/', 'ok' => true, 'error' => '', 'status' => 200, 'variant' => 1],
                    ['url' => 'http://kush.demo.buzz/vhod', 'ok' => false, 'error' => 'страница не найдена (HTTP 404)', 'status' => 404, 'variant' => 1],
                ],
            ]]]));
            $sp = json_decode((string) $this->http('POST', $base . '/api/site-pages', ['host' => 'kush.demo.buzz']), true);
            Assert::true($sp['ok'] ?? false, 'site-pages вернул ok');
            Assert::same(2, count($sp['pages']), 'вернулись обе страницы сайта');
            Assert::false($sp['pages'][1]['ok'], 'вторая страница — с ошибкой');
            Assert::contains('не найдена', (string) $sp['pages'][1]['error']);

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

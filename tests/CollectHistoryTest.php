<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Support\CollectHistory;

/**
 * История сборов для вкладки «Статистика». Смотрим на ДОРЫ: сколько их, какая доля, сколько
 * повторов-доров и по каким зонам они разошлись (зоны считаются только по дорам).
 */
final class CollectHistoryTest
{
    private ?string $dir = null;

    private function dir(): string
    {
        if ($this->dir === null) {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-history-' . uniqid();
            mkdir($this->dir);
        }

        return $this->dir;
    }

    /** Отдельная папка под каждый тест: история дописывается в файл, соседние тесты мешать не должны. */
    private function runsDir(): string
    {
        $dir = $this->dir() . '/run-' . uniqid();
        mkdir($dir);

        return $dir;
    }

    /** @return list<Site> */
    private function sites(string ...$hosts): array
    {
        $out = [];
        foreach ($hosts as $host) {
            $parts = explode('.', $host);
            $domain = count($parts) > 2 ? implode('.', array_slice($parts, -2)) : $host;
            $site = new Site($host, $host, $domain); // key, host, регистрируемый домен
            $site->add(new SearchResult('запрос', 0, 1, 'https://' . $host . '/', $host, ''));
            $out[] = $site;
        }

        return $out;
    }

    public function testBreakdownCountsDoorsAndTheirZonesOnly(): void
    {
        $b = CollectHistory::breakdown($this->sites(
            'example.ru',          // корневой
            'www.second.ru',       // www — тот же корневой домен, не дор
            'kush.casinozsd.buzz', // поддомен — дор
            'hype.casinozsd.buzz',
            'promo.third.com',
        ));
        Assert::same(2, $b['roots'], 'корневых: example.ru и second.ru');
        Assert::same(3, $b['doors'], 'доров: kush., hype. и promo.');
        Assert::same(2, $b['zones']['buzz'] ?? 0);
        Assert::same(1, $b['zones']['com'] ?? 0);
        Assert::same(0, $b['zones']['ru'] ?? 0, 'зона корневых сайтов в статистику доров не идёт');
    }

    public function testDeduplicatedByDomainSiteIsStillADoor(): void
    {
        // Главный баг первой версии: при дедупе по домену (панель включает его по умолчанию)
        // Aggregator кладёт в Site::$host РЕГИСТРИРУЕМЫЙ домен, поэтому дор выглядел корневым —
        // в панели вышло «339 доменов, доров 0». Настоящий хост берётся из адреса выдачи.
        $site = new Site('casinozsd.buzz', 'casinozsd.buzz', 'casinozsd.buzz'); // ключ = домен
        $site->add(new SearchResult('казино', 0, 1, 'https://kush.casinozsd.buzz/', 'kush.casinozsd.buzz', 'Куш'));

        $b = CollectHistory::breakdown([$site]);
        Assert::same(1, $b['doors'], 'сайт на поддомене — дор, даже если сгруппирован по домену');
        Assert::same(0, $b['roots']);
        Assert::same(1, $b['zones']['buzz'] ?? 0);
    }

    public function testRedirectToBrandSubdomainCountsAsDoor(): void
    {
        // Сетка часто собирается по апексу, а главная редиректит на бренд-поддомен — по адресу из
        // выдачи это ещё не дор, а по конечному адресу визита уже дор.
        $site = new Site('casinozsd.buzz', 'casinozsd.buzz', 'casinozsd.buzz');
        $site->add(new SearchResult('казино', 0, 1, 'https://casinozsd.buzz/', 'casinozsd.buzz', 'Куш'));
        $site->visits = [['ok' => true, 'url' => 'https://casinozsd.buzz/', 'final_url' => 'https://kush.casinozsd.buzz/']];

        Assert::same('kush.casinozsd.buzz', $site->realHost(), 'настоящий хост — куда привёл редирект');
        Assert::same(1, CollectHistory::breakdown([$site])['doors']);
    }

    public function testBackfillLatestRecomputesDoorsFromSites(): void
    {
        // Записи старых версий: «доров 0» при непустой таблице — пересчитываем по текущему списку сайтов.
        $dir = $this->runsDir();
        $site = new Site('casinozsd.buzz', 'casinozsd.buzz', 'casinozsd.buzz');
        $site->add(new SearchResult('казино', 0, 1, 'https://kush.casinozsd.buzz/', 'kush.casinozsd.buzz', 'Куш'));
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([
            ['date' => '2026-09-15T17:48:00+00:00', 'sites' => 1, 'doors' => 0, 'roots' => 1, 'zones' => [], 'repeats' => 5],
        ]));

        $updated = CollectHistory::backfillLatest($dir, [$site]);
        Assert::true($updated !== null, 'запись пересчитана');
        Assert::same(1, $updated['doors']);
        Assert::same(1, $updated['zones']['buzz'] ?? 0);
        Assert::same(5, $updated['repeats'], 'остальные поля записи не тронуты');
        Assert::same(1, CollectHistory::load($dir)[0]['doors'], 'пересчёт сохранён на диск');
        Assert::same(null, CollectHistory::backfillLatest($dir, [$site]), 'второй раз пересчитывать нечего');
    }

    public function testBackfillLatestSkipsDifferentCollect(): void
    {
        // Число сайтов в таблице не совпало с записью — это другой сбор, не трогаем.
        $dir = $this->runsDir();
        $site = new Site('a.example.ru', 'a.example.ru', 'example.ru');
        $site->add(new SearchResult('к', 0, 1, 'https://a.example.ru/', 'a.example.ru', 'A'));
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([['date' => '2026-09-15T17:48:00+00:00', 'sites' => 42, 'doors' => 0]]));
        Assert::same(null, CollectHistory::backfillLatest($dir, [$site]));
    }

    public function testBreakdownCountsOwnTemplates(): void
    {
        // «Наш» ставится не по картинке скриншота, а по меткам в HTML страницы (Filter\OwnSites):
        // в статистике это отдельное число и доля от отобранного.
        $sites = $this->sites('a.ru', 'b.ru', 'kush.c.ru');
        $sites[1]->own = true;

        $b = CollectHistory::breakdown($sites);
        Assert::same(1, $b['own'], 'наш шаблон посчитан');
        Assert::same(1, $b['doors'], 'наши на счёт доров не влияют');
        Assert::same(2, $b['roots']);

        $record = CollectHistory::record($sites, []);
        Assert::same(1, $record['own']);
        Assert::same(3, $record['sites']);
        Assert::same(33.3, CollectHistory::percent($record['own'], $record['sites']), 'доля наших');
    }

    public function testTotalsAndCsvCarryOwnShare(): void
    {
        $first = $this->sites('a.ru', 'b.ru');
        $first[0]->own = true;
        $second = $this->sites('c.ru', 'd.ru');

        $totals = CollectHistory::totals([
            CollectHistory::record($second, []),
            CollectHistory::record($first, []),
        ]);
        Assert::same(1, $totals['own'], 'наши складываются по всем сборам');
        Assert::same(25.0, $totals['own_percent'], 'доля наших — от отобранного за всё время');

        $csv = CollectHistory::csv([CollectHistory::record($first, [])]);
        Assert::contains('Наших сайтов', $csv);
        Assert::contains('Доля наших', $csv);
    }

    public function testBackfillLatestFillsOwnForOldRecords(): void
    {
        // Записи до 1.15.0 не знали про наши шаблоны — дописываем число по текущему sites.json,
        // не трогая уже посчитанные доры.
        $dir = $this->runsDir();
        $sites = $this->sites('kush.example.ru', 'own.example.com');
        $sites[1]->own = true;
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([
            ['date' => '2026-09-15T17:48:00+00:00', 'found' => 9, 'sites' => 2, 'doors' => 1, 'roots' => 1, 'zones' => ['ru' => 1]],
        ]));

        $updated = CollectHistory::backfillLatest($dir, $sites);
        Assert::true($updated !== null, 'запись дополнена');
        Assert::same(1, $updated['own']);
        Assert::same(1, $updated['doors'], 'посчитанные доры не тронуты');
        Assert::same(1, $updated['zones']['ru'] ?? 0, 'зоны всей выдачи не перезаписаны отобранным');
        Assert::same(1, CollectHistory::load($dir)[0]['own'], 'дописано на диск');
        Assert::same(null, CollectHistory::backfillLatest($dir, $sites), 'второй раз дописывать нечего');
    }

    public function testBackfillFunnelRecomputesFromResultsCsv(): void
    {
        // Запись версии 1.15.0: масса выдачи посчитана по АДРЕСАМ, про срезанное ничего нет.
        // В results.csv лежат те же строки выдачи с причинами — пересчитываем воронку по ним,
        // чтобы после обновления не пришлось собирать заново.
        $dir = $this->runsDir();
        $csv = $dir . '/results.csv';
        $rows = [
            ['kush.a.buzz', 1, 'selected'],
            ['hype.a.buzz', 4, 'selected'],
            ['root.ru', 2, 'domain_scope'],
            ['shop.root2.ru', 3, 'tld'],
            ['old.c.casino', 5, 'selected'],
        ];
        $out = "query;page;position;host;url;title;snippet;result\n";
        foreach ($rows as [$host, $pos, $reason]) {
            $out .= sprintf("окна;1;%d;%s;https://%s/;т;с;%s\n", $pos, $host, $host, $reason);
        }
        file_put_contents($csv, $out);
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([
            ['id' => 'old', 'date' => '2026-09-16T11:08:00+00:00', 'results' => 5, 'found' => 5, 'found_doors' => 3, 'found_roots' => 2, 'sites' => 1, 'doors' => 1, 'repeats' => 1, 'repeats_doors' => 1, 'zones' => ['buzz' => 2, 'casino' => 1]],
        ]));

        $updated = CollectHistory::backfillFunnel($dir, $csv);
        Assert::true($updated !== null, 'воронка пересчитана');
        Assert::same(4, $updated['unique_sites'], 'сайтов выдачи: a.buzz, root.ru, root2.ru, c.casino');
        Assert::same(3, $updated['found_doors'], 'доры-сайты: a.buzz, root2.ru, c.casino');
        Assert::same(1, $updated['cut']['domain_scope']['sites'] ?? 0);
        Assert::same(1, $updated['cut']['tld']['sites'] ?? 0);
        Assert::same(1, $updated['cut']['seen_before']['sites'] ?? 0, '«уже в базе» берётся из самой записи');
        Assert::same(
            $updated['unique_sites'],
            $updated['sites'] + CollectHistory::cutTotal($updated['cut']),
            'воронка сходится и после пересчёта',
        );
        Assert::same(5, $updated['found'], 'число адресов не изменилось');
        Assert::same(4, CollectHistory::load($dir)[0]['unique_sites'], 'пересчёт сохранён на диск');
        Assert::same(null, CollectHistory::backfillFunnel($dir, $csv), 'второй раз считать нечего');
    }

    public function testBackfillFunnelSkipsForeignResultsFile(): void
    {
        // Сбор шёл частями: results.csv описывает весь список запросов, а запись — только свою часть.
        // Считать по такому файлу нельзя — запись остаётся как была.
        $dir = $this->runsDir();
        $csv = $dir . '/results.csv';
        file_put_contents($csv, "query;page;position;host;url;title;snippet;result\nокна;1;1;a.ru;https://a.ru/;т;с;selected\n");
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([
            ['id' => 'old', 'date' => '2026-09-16T11:08:00+00:00', 'results' => 42, 'found' => 30, 'sites' => 5],
        ]));

        Assert::same(null, CollectHistory::backfillFunnel($dir, $csv));
        Assert::false(isset(CollectHistory::load($dir)[0]['unique_sites']), 'запись не тронута');
    }

    public function testRecordCountsBrandDomains(): void
    {
        // Домен сетки, который держит на поддоменах сайты шести разных брендов, попадает в запись
        // отдельным числом — «домены с 6+ брендами» (бренд берётся из поискового ключа).
        $raw = [];
        $brands = ['куш казино', 'комета казино', 'старда казино', 'гизбо казино', 'лекс казино', 'ирвин казино'];
        foreach ($brands as $i => $query) {
            $host = 'b' . $i . '.dropnet.buzz';
            $raw[] = ['result' => new SearchResult($query, 0, $i + 1, 'https://' . $host . '/', $host, 'T'), 'reason' => null];
        }
        $site = new Site('dropnet.buzz', 'dropnet.buzz', 'dropnet.buzz');
        $site->add(new SearchResult('куш казино', 0, 1, 'https://b0.dropnet.buzz/', 'b0.dropnet.buzz', 'T'));

        $record = CollectHistory::record([$site], ['results' => count($raw)], [], false, false, $raw);
        Assert::same(1, $record['brand_domains'], 'домен с шестью брендами посчитан');
        Assert::same('dropnet.buzz', $record['brand_domains_top'][0]['domain']);
        Assert::same(6, $record['brand_domains_top'][0]['brands']);

        $totals = CollectHistory::totals([$record, $record]);
        Assert::same(2, $totals['brand_domains'], 'в итоге складываются по сборам');
        Assert::contains('Доменов с 6+ брендами', CollectHistory::csv([$record]), 'колонка в CSV');
    }

    public function testIsDoorIgnoresWww(): void
    {
        Assert::true(CollectHistory::isDoor('kush.casinozsd.buzz'));
        Assert::false(CollectHistory::isDoor('casinozsd.buzz'));
        Assert::false(CollectHistory::isDoor('www.casinozsd.buzz'), 'www — не поддомен-дор');
    }

    public function testRecordCountsWholeSerpMassNotJustSelected(): void
    {
        // Главное для пользователя: доля доров считается от ВСЕЙ выдачи, включая домены, отсеянные
        // фильтрами («не тот тип домена» — 13250 результатов у него отсеклось), иначе в отобранном
        // доров почти 100% и цифра ничего не значит. Но масса — это САЙТЫ после группировки «один
        // сайт на домен»: kush.a.buzz и hype.a.buzz — одна сетка, один сайт, а не два.
        $raw = [];
        foreach (['kush.a.buzz', 'hype.a.buzz', 'promo.b.casino', 'plain.ru', 'www.portal.ru', 'plain.ru'] as $host) {
            $raw[] = ['result' => new SearchResult('к', 0, 1, 'https://' . $host . '/', $host, ''), 'reason' => null];
        }
        $record = CollectHistory::record($this->sites('kush.a.buzz'), ['base_domains' => 7, 'results' => 6], [], false, false, $raw);

        Assert::same(6, $record['results'], 'строк выдачи — все, включая повтор одного домена');
        Assert::same(5, $record['found'], 'разных адресов в выдаче (plain.ru дважды — один)');
        Assert::same(4, $record['unique_sites'], 'сайтов после группировки: a.buzz, b.casino, plain.ru, portal.ru');
        Assert::same(2, $record['found_doors'], 'доры-сайты: a.buzz (kush+hype) и b.casino');
        Assert::same(2, $record['found_roots'], 'корневые: plain.ru и portal.ru (www не поддомен)');
        Assert::same(50.0, CollectHistory::percent($record['found_doors'], $record['unique_sites']), 'доля доров от массы сайтов');
        Assert::same(1, $record['sites'], 'отобрано в базу — отдельное число');
        Assert::same(1, $record['zones']['buzz'] ?? 0, 'зоны — по найденным дорам-САЙТАМ');
        Assert::same(1, $record['zones']['casino'] ?? 0);
        Assert::same(0, $record['zones']['ru'] ?? 0, 'зона корневых в статистику доров не идёт');
    }

    public function testFunnelAddsUpAndNamesWhatWasCut(): void
    {
        // Ответ на вопрос «куда делись домены»: масса выдачи = отобрано + срезанное по причинам,
        // и по каждой причине видно, сколько среди срезанного доров.
        $raw = [];
        $add = static function (string $host, ?string $reason, int $position = 1) use (&$raw): void {
            $raw[] = ['result' => new SearchResult('к', 0, $position, 'https://' . $host . '/', $host, ''), 'reason' => $reason];
        };
        $add('kush.a.buzz', null);                 // отобран
        $add('hype.a.buzz', null, 5);              // тот же сайт (a.buzz), вторым адресом
        $add('root.ru', 'domain_scope');           // срезан: не тот тип домена (корневой)
        $add('shop.root2.ru', 'tld');              // срезан: зона
        $add('deep.b.casino', 'domain_scope');     // ещё один срезанный, тот же повод
        $add('old.c.casino', null);                // прошёл фильтры, но уже в базе (см. seenBefore)

        $record = CollectHistory::record(
            $this->sites('kush.a.buzz'),
            ['results' => 6, 'unique_by' => 'domain', 'rejected' => ['domain_scope' => 2, 'tld' => 1, 'seen_before' => 1]],
            ['old.c.casino'],
            false,
            false,
            $raw,
        );

        Assert::same(5, $record['unique_sites'], 'сайтов в выдаче: a.buzz, root.ru, root2.ru, b.casino, c.casino');
        Assert::same(2, $record['cut']['domain_scope']['sites'], 'не тот тип домена — два сайта');
        Assert::same(1, $record['cut']['domain_scope']['doors'], 'из них дор один (deep.b.casino)');
        Assert::same(1, $record['cut']['tld']['sites'], 'зона домена — один сайт');
        Assert::same(1, $record['cut']['seen_before']['sites'], 'уже в базе — считается по сайтам, не по строкам');
        Assert::same(1, $record['cut']['seen_before']['doors'], 'и это дор');
        Assert::same(4, CollectHistory::cutTotal($record['cut']), 'срезано всего');
        Assert::same(
            $record['unique_sites'],
            $record['sites'] + CollectHistory::cutTotal($record['cut']),
            'воронка сходится: сайтов в выдаче = отобрано + срезано',
        );
        Assert::contains('не тот тип домена — 2 (доров 1)', CollectHistory::cutText($record['cut']), 'подпись причины для журнала');
    }

    public function testGroupingFollowsUniqueBySetting(): void
    {
        // Без галочки «один сайт на домен» сайт — это адрес: тогда доры считаются по адресам.
        $raw = [];
        foreach (['kush.a.buzz', 'hype.a.buzz'] as $host) {
            $raw[] = ['result' => new SearchResult('к', 0, 1, 'https://' . $host . '/', $host, ''), 'reason' => null];
        }
        Assert::same(1, CollectHistory::breakdownRaw($raw, 'domain')['unique'], 'один сайт на домен');
        Assert::same(2, CollectHistory::breakdownRaw($raw, 'host')['unique'], 'без группировки — два сайта');
        Assert::same(2, CollectHistory::breakdownRaw($raw, 'host')['doors']);
    }

    public function testRecordWithoutRawFallsBackToSelected(): void
    {
        // Без сырых результатов (старый вызов) запись остаётся прежней: считаем по отобранному.
        $record = CollectHistory::record($this->sites('kush.a.buzz', 'plain.ru'), ['base_domains' => 3]);
        Assert::same(0, $record['found'], 'массы выдачи нет');
        Assert::same(1, $record['doors']);
        Assert::same(1, $record['zones']['buzz'] ?? 0, 'зоны взяты по отобранным дорам');
    }

    public function testRecordCountsDoorRepeatsSeparately(): void
    {
        $record = CollectHistory::record(
            $this->sites('a.ru', 'sub.b.com'),
            ['base_domains' => 900, 'rejected' => ['seen_before' => 4, 'tld' => 7]],
            // Повторы: два дора; www.plain.com не дор, old.ru корневой.
            // net.ru/com.ru — зоны второго уровня (kush.net.ru сам по себе корневой), поэтому берём example.ru.
            ['old.ru', 'kush.example.ru', 'hype.example.ru', 'www.plain.com'],
        );
        Assert::same(2, $record['sites']);
        Assert::same(1, $record['doors']);
        Assert::same(1, $record['roots']);
        Assert::same(4, $record['repeats'], 'повторов всего');
        Assert::same(2, $record['repeats_doors'], 'из них доров — два (www не считается)');
        Assert::same(900, $record['base_domains']);
        Assert::same(50.0, CollectHistory::percent($record['doors'], $record['sites']), 'доля доров');
        Assert::false(isset($record['queries']), 'число запросов в статистике не нужно');
        Assert::false(isset($record['filtered']), 'отсев фильтрами в статистике не нужен');
    }

    public function testAppendKeepsNewestFirstAndTotalsAggregate(): void
    {
        $dir = $this->runsDir();
        CollectHistory::append($dir, CollectHistory::record($this->sites('a.ru'), ['base_domains' => 10], ['x.old.ru']));
        CollectHistory::append($dir, CollectHistory::record($this->sites('b.com', 'x.c.com'), ['base_domains' => 12], ['old.com']));

        $records = CollectHistory::load($dir);
        Assert::same(2, count($records));
        Assert::same(2, $records[0]['sites'], 'новая запись — первой');

        $totals = CollectHistory::totals($records);
        Assert::same(2, $totals['runs']);
        Assert::same(3, $totals['sites'], 'домены складываются по всем сборам');
        Assert::same(1, $totals['doors']);
        Assert::same(1, $totals['repeats_doors'], 'повтор-дор был только в первом сборе');
        Assert::same(2, $totals['repeats']);
        Assert::same(33.3, $totals['doors_percent'], 'без массы выдачи доля считается от отобранного');
        Assert::same(12, $totals['base_domains'], 'база — размер на момент последнего сбора, а не сумма');
        Assert::same(1, $totals['zones']['com'] ?? 0, 'зона дора x.c.com');
        Assert::same(0, $totals['zones']['ru'] ?? 0, 'корневой a.ru в зоны не попал');
    }

    public function testTotalsMixOldAndNewRecordsWithoutBreakingPercent(): void
    {
        // В истории соседствуют записи разных версий: у старой нет ни группировки, ни разбивки отсева.
        // Итог всё равно должен сходиться и не давать «доля доров 114%» (сумма доров делилась на массу
        // только новых записей).
        $totals = CollectHistory::totals([
            ['results' => 24544, 'found' => 6460, 'unique_sites' => 2431, 'found_doors' => 1580, 'sites' => 602,
             'cut' => ['domain_scope' => ['sites' => 1002, 'doors' => 180], 'seen_before' => ['sites' => 641, 'doors' => 604]],
             'base_domains' => 2645],
            ['results' => 9000, 'found' => 3000, 'found_doors' => 1200, 'sites' => 300, 'doors' => 280, 'base_domains' => 2043],
        ]);

        Assert::same(5431, $totals['unique_sites'], 'у старой записи массой считаются адреса');
        Assert::same(2780, $totals['found_doors']);
        Assert::same(51.2, $totals['doors_percent'], 'доля доров не может быть больше 100%');
        Assert::same(902, $totals['sites']);
        Assert::same(
            $totals['unique_sites'],
            $totals['sites'] + $totals['cut_total'],
            'итог сходится: масса выдачи = отобрано + срезано',
        );
        // 2700 от старой записи (там разбивки нет вовсе) + 186 неразобранного остатка новой.
        Assert::same(2886, $totals['cut']['other']['sites'] ?? 0, 'неразобранное уходит в «прочее»');
        Assert::same(2645, $totals['base_domains'], 'база — по самой свежей записи');
    }

    public function testLoadReadsOldSubdomainsKey(): void
    {
        // Записи версии 1.10.0 звали доры «subdomains» — старая история должна читаться.
        $dir = $this->runsDir();
        file_put_contents($dir . '/' . CollectHistory::FILE, json_encode([['date' => '2026-09-15T10:00:00+00:00', 'sites' => 5, 'subdomains' => 3]]));
        $records = CollectHistory::load($dir);
        Assert::same(3, $records[0]['doors'], 'старый ключ subdomains читается как doors');
    }

    public function testCsvHasHeaderAndRows(): void
    {
        $csv = CollectHistory::csv([
            CollectHistory::record($this->sites('a.ru', 'sub.b.ru'), ['base_domains' => 50], ['x.old.ru']),
        ]);
        Assert::contains('Результатов в выдаче', $csv);
        Assert::contains('Сайтов в выдаче', $csv);
        Assert::contains('Что срезано', $csv);
        Assert::contains('Отобрано сайтов', $csv);
        Assert::contains('Зоны доров', $csv);
        Assert::contains('ru: 1', $csv, 'зоны доров сложены в одну колонку');
    }

    public function testLoadOfMissingFileIsEmpty(): void
    {
        Assert::same([], CollectHistory::load($this->dir() . '/нет-такой-папки'));
    }

    public function tearDownClass(): void
    {
        if ($this->dir !== null && is_dir($this->dir)) {
            $it = new \RecursiveIteratorIterator(
                new \RecursiveDirectoryIterator($this->dir, \FilesystemIterator::SKIP_DOTS),
                \RecursiveIteratorIterator::CHILD_FIRST,
            );
            foreach ($it as $item) {
                $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
            }
            @rmdir($this->dir);
        }
    }
}

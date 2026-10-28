<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\SerpAnalysis;
use YandexSites\Support\SerpHistory;

final class SerpHistoryTest
{
    private string $dir = '';

    private function runs(): string
    {
        if ($this->dir === '') {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-serp-history-' . uniqid();
            mkdir($this->dir, 0777, true);
        }

        return $this->dir;
    }

    public function tearDownClass(): void
    {
        if ($this->dir !== '' && is_dir($this->dir)) {
            array_map('unlink', glob($this->dir . '/*') ?: []);
            rmdir($this->dir);
        }
    }

    /**
     * @return array{query: string, position: int, host: string, url: string, title: string, snippet: string, reason: string}
     */
    private function row(string $query, int $position, string $host): array
    {
        return ['query' => $query, 'position' => $position, 'host' => $host,
            'url' => 'https://' . $host . '/', 'title' => '', 'snippet' => '', 'reason' => 'selected'];
    }

    public function testComparesNumbersOfEachBrandBetweenCollects(): void
    {
        // Между сборами раньше хранился только список сайтов бренда, и разница отвечала «появилось 3,
        // пропало 1». Решения принимают по другим числам — чем забран бренд, кто его забирает, какая у
        // нас доля; их и сравниваем.
        $runs = $this->runs();
        // БЫЛО: бренд держал чужой тематический домен, доров почти нет, нас нет.
        $before = SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'vulkan-casino.ru'),
            $this->row('вулкан казино', 2, 'obzor-kazino.ru'),
            $this->row('вулкан казино', 9, 'old.netone.ru'),
        ], 10);
        SerpHistory::record($runs, $before);

        // СТАЛО: верх забрал наш дор, доры заняли бренд.
        $own = new \YandexSites\Filter\OwnSites(['ourbase.ru']);
        $after = SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'kush.ourbase.ru'),
            $this->row('вулкан казино', 2, 'a.netone.ru'),
            $this->row('вулкан казино', 3, 'b.nettwo.ru'),
        ], 10, $own);

        $changes = SerpHistory::compare(SerpHistory::previous($runs), $after);
        $c = $changes['brands']['vulkan'] ?? null;
        Assert::true(is_array($c), 'бренд попал в изменения: ' . json_encode(array_keys($changes['brands']), JSON_UNESCAPED_UNICODE));

        Assert::same('other', $c['cap_was'], 'раньше бренд держали не доры');
        Assert::true($c['cap_changed'], 'тип захвата сменился');
        Assert::same(1, $c['cap_dir'], 'сдвиг в сторону доров');
        Assert::true($c['ds_delta'] > 50, 'доля доров выросла: ' . $c['ds_delta']);
        Assert::same('vulkan-casino.ru', $c['lead_was'], 'кто забирал бренд раньше');
        Assert::true($c['lead_changed'], 'лидер сменился');
        Assert::same(0.0, (float) $c['os_was'], 'нас раньше не было');
        Assert::true($c['os_delta'] > 0, 'наша доля выросла: ' . $c['os_delta']);
        Assert::same(1, $c['own_delta'], 'наш дор появился');

        $sum = SerpHistory::summary($changes);
        Assert::same(1, $sum['cap_changed']);
        Assert::same(1, $sum['to_doors']);
        Assert::same(0, $sum['from_doors']);
        Assert::same(1, $sum['lead_changed']);
        // РОТАЦИЯ ПО ТИПУ: бренд забирал тематический домен, стал забирать дор. Это отдельный
        // вопрос от смены хоста — лидер может смениться внутри одного типа.
        Assert::same('theme', $c['lt_was']);
        Assert::true($c['lt_changed'], 'тип лидера сменился');
        Assert::same(1, $sum['type_changed']);
        Assert::contains('сменился ТИП лидера — 1', SerpHistory::summaryText($sum));
        Assert::same(1, $sum['our_up']);
        Assert::contains('сменился лидер — 1', SerpHistory::summaryText($sum));
    }

    public function testBrandWithoutMovementIsNotListedAsChanged(): void
    {
        // Иначе фильтр «изменившиеся» показывает весь список и ничего не говорит.
        $runs = $this->runs() . '/same';
        mkdir($runs, 0777, true);
        $rows = [$this->row('лекс казино', 1, 'lex-casino.ru'), $this->row('лекс казино', 2, 'obzor-kazino.ru')];
        $analysis = SerpAnalysis::build($rows, 10);
        SerpHistory::record($runs, $analysis);
        $changes = SerpHistory::compare(SerpHistory::previous($runs), SerpAnalysis::build($rows, 10));

        Assert::same([], $changes['brands'], 'ничего не сдвинулось — изменений нет');
        Assert::same([], $changes['gone']);
        Assert::same(0, SerpHistory::summary($changes)['brands']);
        array_map('unlink', glob($runs . '/*') ?: []);
        rmdir($runs);
    }

    public function testNewAndGoneBrandsAreSeparated(): void
    {
        $runs = $this->runs() . '/newgone';
        mkdir($runs, 0777, true);
        SerpHistory::record($runs, SerpAnalysis::build([$this->row('лекс казино', 1, 'lex-casino.ru')], 10));
        $changes = SerpHistory::compare(
            SerpHistory::previous($runs),
            SerpAnalysis::build([$this->row('вулкан казино', 1, 'a.netone.ru')], 10),
        );

        Assert::true(!empty($changes['brands']['vulkan']['is_new']), 'новый бренд помечен');
        Assert::true(isset($changes['gone']['lex']), 'пропавший бренд отдельно');
        $sum = SerpHistory::summary($changes);
        Assert::same(1, $sum['new']);
        Assert::same(1, $sum['gone']);
        Assert::same(0, $sum['brands'], 'новый бренд не считается изменившимся — сравнивать не с чем');
        array_map('unlink', glob($runs . '/*') ?: []);
        rmdir($runs);
    }

    public function testResumeReplacesItsOwnRecordAndTrendKeepsCollects(): void
    {
        // Сбор частями — ОДИН сбор: продолжение переписывает свою же запись, иначе история распадается
        // на куски и «прошлый сбор» оказывается прошлой частью этого же.
        $runs = $this->runs() . '/resume';
        mkdir($runs, 0777, true);
        $first = SerpAnalysis::build([$this->row('вулкан казино', 1, 'official-vulkan.ru')], 10);
        $second = SerpAnalysis::build([$this->row('вулкан казино', 1, 'a.netone.ru')], 10);
        SerpHistory::record($runs, $first);                      // прошлый сбор
        SerpHistory::record($runs, $second);                     // новый сбор
        SerpHistory::record($runs, $second, 10, true);           // его же продолжение

        Assert::same(2, count(SerpHistory::load($runs)), 'продолжение не добавило третью запись');
        $prev = SerpHistory::previous($runs, true);
        Assert::same('official-vulkan.ru', $prev['brands']['vulkan']['lead'], 'сравниваем с прошлым сбором, а не с частью этого');

        $trend = SerpHistory::trend($runs, 'vulkan');
        Assert::same(2, count($trend), 'динамика по сборам');
        Assert::same('a.netone.ru', $trend[0]['lead'], 'сверху текущий сбор');
        Assert::same('official-vulkan.ru', $trend[1]['lead']);
        array_map('unlink', glob($runs . '/*') ?: []);
        rmdir($runs);
    }

    public function testOverviewFeedsTheChartInCollectOrder(): void
    {
        // «График доли по сборам» + «становится наших больше или нет»: сводка по строке на сбор,
        // от старых к новым — в том порядке, в каком рисуется график.
        $runs = $this->runs() . '/overview';
        mkdir($runs, 0777, true);
        $own = new \YandexSites\Filter\OwnSites(['ourbase.ru']);
        // Сбор 1: бренд держат не доры, нас нет.
        SerpHistory::record($runs, SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'official-vulkan.ru'),
            $this->row('вулкан казино', 9, 'old.netone.ru'),
        ], 10, $own));
        // Сбор 2: доры заняли бренд, и два из них наши.
        SerpHistory::record($runs, SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'kush.ourbase.ru'),
            $this->row('вулкан казино', 2, 'max.ourbase.ru'),
            $this->row('вулкан казино', 3, 'a.netone.ru'),
            $this->row('лекс казино', 1, 'lex-casino.ru'),
        ], 10, $own));

        $rows = SerpHistory::overview($runs);
        Assert::same(2, count($rows));
        Assert::true($rows[0]['at'] <= $rows[1]['at'], 'от старых к новым — как рисуется график');
        Assert::same(1, $rows[0]['brands'], 'в первом сборе один бренд');
        Assert::same(2, $rows[1]['brands']);
        Assert::true($rows[1]['ds_avg'] > $rows[0]['ds_avg'], 'доля доров выросла: ' . $rows[0]['ds_avg'] . ' → ' . $rows[1]['ds_avg']);
        Assert::same(0, $rows[0]['own_doors'], 'наших тогда не было');
        Assert::same(0, $rows[0]['own_brands']);
        Assert::same(2, $rows[1]['own_doors'], 'наших доров стало два');
        Assert::same(1, $rows[1]['own_brands'], 'но держатся они в одном бренде');
        Assert::true($rows[1]['os_avg'] > 0, 'наша доля появилась');
        array_map('unlink', glob($runs . '/*') ?: []);
        rmdir($runs);
    }

    public function testOverviewIgnoresTheNoBrandBlock(): void
    {
        // «без бренда» — остаток запросов: в среднем по брендам он сдвигал бы картину тем сильнее,
        // чем больше в списке общетематических ключей.
        $runs = $this->runs() . '/overview-nobrand';
        mkdir($runs, 0777, true);
        SerpHistory::record($runs, SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'a.netone.ru'),
            $this->row('пластиковые окна москва', 1, 'okna-msk.ru'),
        ], 10));
        $row = SerpHistory::overview($runs)[0];

        Assert::same(1, $row['brands'], 'остаток запросов брендом не считается');
        Assert::same(100.0, (float) $row['ds_avg'], 'и в среднюю долю доров не попадает');
        array_map('unlink', glob($runs . '/*') ?: []);
        rmdir($runs);
    }

    public function testSnapshotKeepsOnlyNumbersNotRows(): void
    {
        // Файл живёт рядом с историей сборов и пишется каждый сбор: строки выдачи или списки хостов
        // раздули бы его в мегабайты на первом же сборе из 3000 запросов.
        $snap = SerpHistory::snapshot(SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'a.netone.ru'),
            $this->row('вулкан казино', 2, 'obzor-kazino.ru'),
        ], 10));
        $brand = $snap['brands']['vulkan'];

        Assert::same(10, $snap['top'], 'глубина топа записана: сравнивать можно только одинаковые');
        Assert::same(['label', 'cap', 'ds', 'sites', 'doors', 'keys', 'lead', 'lt', 'ls', 'own', 'os', 'fresh', 'by'], array_keys($brand));
        Assert::same(1, (int) $brand['by']['door'], 'состав по типам — для ротации');
        Assert::notContains('вулкан казино', json_encode($snap, JSON_UNESCAPED_UNICODE), 'запросов в снимке нет');
        Assert::notContains('obzor-kazino.ru', json_encode($snap, JSON_UNESCAPED_UNICODE), 'списка хостов в снимке нет');
    }
}

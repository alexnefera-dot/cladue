<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\OwnSites;
use YandexSites\Support\SerpAnalysis;

final class SerpAnalysisTest
{
    /**
     * @return array{query: string, position: int, host: string, url: string, title: string, snippet: string, reason: string}
     */
    private function row(string $query, int $position, string $host, string $title = '', string $snippet = '', string $reason = 'selected'): array
    {
        return [
            'query' => $query, 'position' => $position, 'host' => $host,
            'url' => 'https://' . $host . '/', 'title' => $title, 'snippet' => $snippet, 'reason' => $reason,
        ];
    }

    public function testClassifiesSiteTypes(): void
    {
        // Порядок важен: поддомен известного сайта — это его страница, а не дор.
        Assert::same('social', SerpAnalysis::classify('vk.com'), 'соцсеть');
        Assert::same('social', SerpAnalysis::classify('m.vk.com'), 'поддомен соцсети — тоже соцсеть, не дор');
        Assert::same('social', SerpAnalysis::classify('dzen.ru'), 'дзен — площадка, а не сайт');
        Assert::same('known', SerpAnalysis::classify('rbc.ru'), 'СМИ');
        Assert::same('known', SerpAnalysis::classify('companies.rbc.ru'), 'поддомен известного сайта — не дор');
        Assert::same('door', SerpAnalysis::classify('kush.example-net.ru'), 'поддомен обычного домена — дор');
        Assert::same('theme', SerpAnalysis::classify('casino-x.ru'), 'тема видна в адресе');
        Assert::same('theme', SerpAnalysis::classify('best-guide.ru', 'Обзор казино', ''), 'тема видна в заголовке');
        Assert::same('theme', SerpAnalysis::classify('guide.ru', '', 'бонусы и фриспины'), 'тема видна в сниппете');
        Assert::same('other', SerpAnalysis::classify('stroyka-dom.ru', 'Ремонт квартир', 'плитка и обои'), 'не по теме');
        Assert::same('other', SerpAnalysis::classify(''), 'пустой хост');
    }

    public function testGroupsByBrandAndMarksIntersections(): void
    {
        // Блок на бренд: все его ключи со всей выдачей, повторы НЕ выбрасываются, пересечения помечены.
        $rows = [
            $this->row('вулкан казино зеркало', 1, 'kush.grid-a.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино зеркало', 2, 'vk.com', 'Группа', '', 'excluded_domain'),
            $this->row('вулкан казино бонус', 1, 'kush.grid-a.ru', 'Вулкан', 'бонус'),
            $this->row('вулкан казино бонус', 2, 'lenta.ru', 'Новость', '', 'excluded_domain'),
            $this->row('лекс казино вход', 1, 'kush.grid-a.ru', 'Лекс', 'казино'),
            $this->row('лекс казино вход', 2, 'stroyka-dom.ru', 'Ремонт', 'плитка', 'not_theme'),
            $this->row('лекс казино вход', 11, 'deep.grid-a.ru', 'За топом', ''),
        ];
        $a = SerpAnalysis::build($rows);

        Assert::same(2, count($a['brands']), 'два бренда');
        Assert::same(6, $a['results'], 'позиция 11 в топ-10 не попала');
        Assert::same(3, $a['queries']);

        $by = [];
        foreach ($a['brands'] as $b) {
            $by[$b['key']] = $b;
        }
        $vulkan = $by['vulkan'];
        Assert::same(2, $vulkan['query_count'], 'оба ключа бренда в одном блоке');
        Assert::same(3, $vulkan['sites'], 'сайты считаются по РАЗНЫМ доменам, а не по строкам');
        Assert::same(2, $vulkan['hosts']['kush.grid-a.ru']['keys'], 'дор встретился в двух ключах бренда');
        Assert::same(1, $vulkan['crossed'], 'это и есть пересечение внутри бренда');
        Assert::same(2, $vulkan['hosts']['kush.grid-a.ru']['brands'], 'тот же домен держится и на втором бренде');
        Assert::same(1, $vulkan['networked'], 'сетка: домен на нескольких брендах');
        Assert::same(1, $vulkan['counts']['door']);
        Assert::same(1, $vulkan['counts']['social']);
        Assert::same(1, $vulkan['counts']['known']);

        // Отсеянные главной строки остаются на месте вместе с причиной.
        $reasons = array_column($vulkan['queries']['вулкан казино зеркало'], 'reason');
        Assert::inArray('excluded_domain', $reasons, 'видно, что именно убрала главная');
    }

    public function testQueriesWithoutBrandGoToTheirOwnBlockLast(): void
    {
        $rows = [
            $this->row('пластиковые окна москва цена', 1, 'okna.ru', 'Окна', ''),
            $this->row('вулкан казино', 1, 'kush.grid-b.ru', 'Вулкан', 'казино'),
        ];
        $a = SerpAnalysis::build($rows);
        $last = $a['brands'][count($a['brands']) - 1];
        Assert::same('', $last['key'], 'запросы без бренда — отдельным блоком');
        Assert::same('без бренда', $last['label']);
    }

    public function testTotalsCountDistinctSitesAndCrossBrandRepeats(): void
    {
        // «Доры по всем ключам бренда — это уникальные?» Да: и внутри бренда, и в общем итоге считаем
        // РАЗНЫЕ сайты. Домен, который держится на двух брендах, в общем числе доров один, а разница
        // между суммой по брендам и общим итогом — это и есть повторы между брендами.
        $rows = [
            $this->row('вулкан казино зеркало', 1, 'kush.grid-f.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино бонус', 1, 'kush.grid-f.ru', 'Вулкан', 'бонус'),
            $this->row('вулкан казино бонус', 2, 'only-v.grid-f.ru', 'Вулкан', 'казино'),
            $this->row('лекс казино вход', 1, 'kush.grid-f.ru', 'Лекс', 'казино'),
            $this->row('лекс казино вход', 2, 'only-l.grid-f.ru', 'Лекс', 'казино'),
        ];
        $a = SerpAnalysis::build($rows);

        Assert::same(3, $a['sites'], 'разных сайтов всего три, хотя строк пять');
        Assert::same(3, $a['totals']['door'], 'доров всего по всем брендам — уникальных');
        Assert::same(4, $a['totals_sum']['door'], 'сумма по брендам больше: общий дор посчитан в обоих');
        Assert::same(1, $a['repeats']['sites'], 'один сайт держится сразу на нескольких брендах');
        Assert::same(1, $a['repeats']['by_type']['door'], 'и это дор');

        $by = [];
        foreach ($a['brands'] as $b) {
            $by[$b['key']] = $b;
        }
        Assert::same(2, $by['vulkan']['counts']['door'], 'внутри бренда — тоже разные сайты');
        Assert::same(2, $by['lex']['counts']['door']);
    }

    public function testOursOnlyByLaunchSystemList(): void
    {
        // «Наши только с базы апи должны браться, не по оферу, скрину, домену и тп»: здесь HTML нет
        // вовсе, и единственная проверка — список запущенных доменов. Ни путь в чужом адресе
        // (site.top/faro-bonus), ни похожее имя нашим сайт не делают — именно так появлялись ложные
        // пометки «исключён как наш» на чужих сайтах.
        $rows = [
            ['query' => 'вулкан казино', 'position' => 1, 'host' => 'kush.stranger.top',
                'url' => 'https://kush.stranger.top/faro-bonus', 'title' => 'Вулкан', 'snippet' => 'казино', 'reason' => 'selected'],
            $this->row('вулкан казино', 2, 'a.4916.team', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 3, 'c.stranger.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 4, 'casino-x.ru', 'Обзор', 'казино'),
        ];
        $a = SerpAnalysis::build($rows, 10, new OwnSites(['4916.team']));
        $hosts = $a['brands'][0]['hosts'];

        Assert::false($hosts['kush.stranger.top']['own'], 'чужой адрес с нашим словом в пути — не наш');
        Assert::true($hosts['a.4916.team']['own'], 'поддомен нашей базы — наш');
        Assert::false($hosts['c.stranger.ru']['own'], 'чужой дор');
        Assert::same(SerpAnalysis::REASON_DORGEN, $hosts['a.4916.team']['own_reason'], 'причина одна — список системы запусков');
        Assert::same('', $hosts['c.stranger.ru']['own_reason'], 'у чужого причины нет');
        Assert::same(1, $a['brands'][0]['own_doors'], 'наших доров у бренда');
        Assert::same(1, $a['own']['doors'], 'наших доров всего');
        Assert::same([SerpAnalysis::REASON_DORGEN => 1], $a['own']['by_reason']);
        Assert::same(3, $a['totals']['door'], 'тематический домен в доры не попал');

        // Без списка «наших» нет вовсе — ложных пометок не появляется.
        $plain = SerpAnalysis::build($rows);
        Assert::same(0, $plain['own']['doors'], 'без списка никто не помечен нашим');
    }

    public function testZoneInTheListMarksNobody(): void
    {
        // Зона не может быть базой: иначе одна запись делала нашими ВСЕ сайты зоны.
        $rows = [$this->row('вулкан казино', 1, 'stranger.net.ru', 'Вулкан', 'казино')];
        $a = SerpAnalysis::build($rows, 10, new OwnSites(['net.ru']));
        Assert::same(0, $a['own']['doors'], 'зона в списке никого не помечает');
    }

    public function testDiffShowsWhatAppearedAndDisappeared(): void
    {
        $before = SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'a.grid-c.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 2, 'b.grid-c.ru', 'Вулкан', 'казино'),
        ]);
        $index = SerpAnalysis::index($before);

        $after = SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'a.grid-c.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 2, 'c.grid-c.ru', 'Вулкан', 'казино'),
            $this->row('лекс казино', 1, 'd.grid-c.ru', 'Лекс', 'казино'),
        ]);
        $diff = SerpAnalysis::diff($index, $after);

        Assert::same(['c.grid-c.ru'], $diff['brands']['vulkan']['added_hosts'], 'новый дор бренда');
        Assert::same(['b.grid-c.ru'], $diff['brands']['vulkan']['removed_hosts'], 'пропавший дор бренда');
        Assert::same(1, $diff['brands']['vulkan']['added']['door'], 'разбивка по типу');
        Assert::same(1, $diff['brands']['vulkan']['removed']['door']);
        Assert::false($diff['brands']['vulkan']['is_new'], 'бренд был и раньше');
        Assert::true($diff['brands']['lex']['is_new'], 'бренд появился впервые');
        Assert::same(2, $diff['totals']['added'], 'итог: два новых сайта');
        Assert::same(1, $diff['totals']['removed']);

        // Бренд, который был, а в новом сборе не собрался вовсе.
        $gone = SerpAnalysis::diff($index, SerpAnalysis::build([$this->row('лекс казино', 1, 'd.grid-c.ru', 'Лекс', 'казино')]));
        Assert::true($gone['brands']['vulkan']['gone'] ?? false, 'бренд пропал из сбора целиком');
        Assert::same(2, $gone['brands']['vulkan']['removed']['total']);
    }

    public function testUnchangedBrandIsNotListedAsChanged(): void
    {
        $rows = [$this->row('вулкан казино', 1, 'a.grid-d.ru', 'Вулкан', 'казино')];
        $a = SerpAnalysis::build($rows);
        $diff = SerpAnalysis::diff(SerpAnalysis::index($a), SerpAnalysis::build($rows));
        Assert::same([], $diff['brands'], 'ничего не изменилось — в списке изменений пусто');
        Assert::same(0, $diff['totals']['added']);
    }

    public function testReadsRowsFromResultsCsv(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-serpcsv-' . uniqid() . '.csv';
        file_put_contents($file, "\xEF\xBB\xBFquery;page;position;host;url;title;snippet;result\n"
            . "вулкан казино;1;1;kush.grid-e.ru;https://kush.grid-e.ru/;Вулкан;казино онлайн;selected\n"
            . "вулкан казино;1;2;vk.com;https://vk.com/g;Группа;;excluded_domain\n");
        $rows = iterator_to_array(SerpAnalysis::csvRows($file));
        @unlink($file);

        Assert::same(2, count($rows), 'обе строки прочитаны');
        Assert::same('вулкан казино', $rows[0]['query'], 'BOM не мешает');
        Assert::same(1, $rows[0]['position']);
        Assert::same('excluded_domain', $rows[1]['reason'], 'причина отсева сохранена');
        $a = SerpAnalysis::build($rows);
        Assert::same(1, $a['brands'][0]['counts']['door']);
    }
}

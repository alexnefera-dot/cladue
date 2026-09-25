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

    public function testDoesNotCallStrangerOursBecauseOfItsUrl(): void
    {
        // Пользователь: «вижу много доров определены как наши, но у нас нет доменов .top/.click».
        // Метка сверялась и с полным АДРЕСОМ строки выдачи, поэтому любой чужой site.top/faro-bonus
        // становился нашим. При визите адрес проверять нужно (там цепочка редиректов), здесь — нет.
        $rows = [
            ['query' => 'вулкан казино', 'position' => 1, 'host' => 'kush.stranger.top',
                'url' => 'https://kush.stranger.top/faro-bonus', 'title' => 'Вулкан', 'snippet' => 'казино', 'reason' => 'selected'],
            ['query' => 'вулкан казино', 'position' => 2, 'host' => 'a.faro-hub.ru',
                'url' => 'https://a.faro-hub.ru/', 'title' => 'Вулкан', 'snippet' => 'казино', 'reason' => 'selected'],
        ];
        $a = SerpAnalysis::build($rows, 10, new OwnSites(['faro']), []);
        $hosts = $a['brands'][0]['hosts'];

        Assert::false($hosts['kush.stranger.top']['own'], 'метка в пути чужого адреса — это не наш сайт');
        Assert::true($hosts['a.faro-hub.ru']['own'], 'а в самом хосте — наш');
        Assert::same(1, $a['own']['doors'], 'наш дор ровно один');
    }

    public function testExplainsWhyADoorIsConsideredOurs(): void
    {
        // Чтобы понять, какая метка ловит лишнее, у каждого «нашего» должна быть причина.
        $rows = [
            $this->row('вулкан казино', 1, 'a.faro-hub.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 2, 'b.old-ours.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 3, 'c.stranger.top', 'Вулкан', 'казино'),
        ];
        $a = SerpAnalysis::build($rows, 10, new OwnSites(['faro']), ['old-ours.ru']);
        $hosts = $a['brands'][0]['hosts'];

        Assert::same('метка «faro»', $hosts['a.faro-hub.ru']['own_reason'], 'видно, ИМЕННО какая метка сработала');
        Assert::same(SerpAnalysis::REASON_LIST, $hosts['b.old-ours.ru']['own_reason'], 'вторая причина — список наших доменов');
        Assert::same('', $hosts['c.stranger.top']['own_reason'], 'у чужого причины нет');
        Assert::same(['метка «faro»' => 1, SerpAnalysis::REASON_LIST => 1], $a['own']['by_reason'], 'разбивка по причинам в итогах');
    }

    public function testMarksOurDoorsByMarkersAndByDomainList(): void
    {
        // Наш дор узнаётся без HTML (его здесь нет): по меткам наших шаблонов и по накопленному списку
        // наших доменов — последний важен, потому что повтор мы уже не открываем, а он наш.
        $rows = [
            $this->row('вулкан казино', 1, 'a.faro-hub.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 2, 'b.old-ours.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 3, 'c.stranger.ru', 'Вулкан', 'казино'),
            $this->row('вулкан казино', 4, 'casino-x.ru', 'Обзор', 'казино'),
        ];
        $a = SerpAnalysis::build($rows, 10, new OwnSites(['faro-hub.ru']), ['old-ours.ru']);
        $brand = $a['brands'][0];

        Assert::true($brand['hosts']['a.faro-hub.ru']['own'], 'наш по метке шаблона');
        Assert::true($brand['hosts']['b.old-ours.ru']['own'], 'наш по списку наших доменов (поддомен тоже наш)');
        Assert::false($brand['hosts']['c.stranger.ru']['own'], 'чужой дор');
        Assert::same(2, $brand['own_doors'], 'наших доров у бренда');
        Assert::same(2, $a['own']['doors'], 'наших доров всего');
        Assert::same(3, $a['totals']['door'], 'тематический домен в доры не попал');

        // Без меток и без списка «наших» нет вовсе — ложных пометок не появляется.
        $plain = SerpAnalysis::build($rows);
        Assert::same(0, $plain['own']['doors'], 'без меток никто не помечен нашим');
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

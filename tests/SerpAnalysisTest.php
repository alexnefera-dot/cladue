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

    public function testSplitsBrandsByWhoCapturesThem(): void
    {
        // Запрос пользователя: «разделив бренды на те где захват массово доры а где не доры,
        // посчитали их и где гибриды». Делим по ДОЛЕ ВИДИМОСТИ доров, а не по их числу: десять доров
        // в хвосте топа ничего не держат, а один дор на первом месте забирает треть бренда.
        $rows = [];
        // Бренд «вулкан»: весь топ — доры одной сетки.
        foreach (['вулкан казино', 'вулкан зеркало'] as $q) {
            $rows[] = $this->row($q, 1, 'a.netone.ru');
            $rows[] = $this->row($q, 2, 'b.nettwo.ru');
            $rows[] = $this->row($q, 3, 'c.netthree.ru');
        }
        // Бренд «лекс»: официальный сайт и обзорники сверху, дор один и девятым.
        foreach (['лекс казино', 'лекс зеркало'] as $q) {
            $rows[] = $this->row($q, 1, 'lex-casino.ru', 'Лекс казино — официальный сайт');
            $rows[] = $this->row($q, 2, 'obzor-kazino.ru', 'Обзор казино Лекс');
            $rows[] = $this->row($q, 3, 'vk.com');
            $rows[] = $this->row($q, 9, 'door.netfour.ru');
        }
        // Бренд «пинап»: дор забрал первое место, остальное держат не доры — это и есть гибрид.
        $rows[] = $this->row('пин ап казино', 1, 'd.netfive.ru');
        $rows[] = $this->row('пин ап казино', 2, 'pinup-official.ru', 'Пин ап казино');
        $rows[] = $this->row('пин ап казино', 3, 'obzor-kazino.ru', 'Обзор казино');
        $rows[] = $this->row('пин ап казино', 4, 'youtube.com');

        $analysis = SerpAnalysis::build($rows, 10);
        $byKey = [];
        foreach ($analysis['brands'] as $brand) {
            $byKey[$brand['key']] = $brand;
        }

        Assert::same('door', $byKey['vulkan']['capture'], 'весь топ доры — бренд забран дорами');
        Assert::same(100.0, $byKey['vulkan']['door_share'], 'других сайтов в бренде нет');
        Assert::same('забран дорами', $byKey['vulkan']['capture_label']);

        Assert::same('other', $byKey['lex']['capture'], 'дор девятым — бренд держат не доры');
        Assert::true($byKey['lex']['door_share'] < 10.0, 'доля доров: ' . $byKey['lex']['door_share']);
        Assert::same(1, $byKey['lex']['counts']['door'], 'дор в бренде есть — но он ничего не держит');

        Assert::same('mixed', $byKey['pinup']['capture'], 'дор первый, остальное чужое — гибрид');
        Assert::true(
            $byKey['pinup']['door_share'] > SerpAnalysis::CAPTURE_OTHER
            && $byKey['pinup']['door_share'] < SerpAnalysis::CAPTURE_DOOR,
            'доля доров между порогами: ' . $byKey['pinup']['door_share'],
        );

        // СЧЁТ по типам захвата: он и отвечает на «посчитали их».
        Assert::same(['door' => 1, 'mixed' => 1, 'other' => 1, 'nobrand' => 0], $analysis['capture']);
        Assert::same(3, array_sum($analysis['capture']), 'сумма сходится с числом блоков в списке');

        // ДОР ЛИ ПЕРВЫЙ — второй вопрос, и он не повторяет первый: у «лекса» дор в бренде есть, но
        // первым стоит официальный сайт, а у «пинапа» доля доров всего 39% И при этом дор первый.
        Assert::same(['door' => 1, 'mixed' => 1, 'other' => 0, 'nobrand' => 0], $analysis['capture_leader']);
        Assert::same(
            'дорами — 1 (дор первым в 1), гибрид — 1 (дор первым в 1), не дорами — 1',
            SerpAnalysis::captureText($analysis),
        );

        // Границы — в одном месте, страница и выгрузка берут их оттуда же.
        Assert::same('door', SerpAnalysis::captureOf(SerpAnalysis::CAPTURE_DOOR));
        Assert::same('mixed', SerpAnalysis::captureOf(SerpAnalysis::CAPTURE_DOOR - 0.1));
        Assert::same('mixed', SerpAnalysis::captureOf(SerpAnalysis::CAPTURE_OTHER + 0.1));
        Assert::same('other', SerpAnalysis::captureOf(SerpAnalysis::CAPTURE_OTHER));
    }

    public function testMarksBrandWhereOneDoorTakesEnough(): void
    {
        // «отметим есть ли дор который хотя бы 5% в бренде забирает» — вопроса этого в доле доров
        // НЕТ: та доля — сумма всех доров сразу, и в ней не видно ни одинокого сильного дора,
        // ни двадцати слабых в хвосте топа.
        $rows = [];
        // «вулкан»: бренд держат не доры, но один дор всё же забирает заметную долю — лезть можно.
        $rows[] = $this->row('вулкан казино', 1, 'vulkan-official.ru', 'Вулкан казино — официальный сайт');
        $rows[] = $this->row('вулкан казино', 2, 'obzor-kazino.ru', 'Обзор казино Вулкан');
        $rows[] = $this->row('вулкан казино', 3, 'otzyvy-kazino.ru', 'Отзывы о казино');
        $rows[] = $this->row('вулкан казино', 4, 'kush.ourbase.ru');
        // «лекс»: дор в бренде есть, но стоит в хвосте и не забирает ничего.
        $rows[] = $this->row('лекс казино', 1, 'lex-casino.ru', 'Лекс казино — официальный сайт');
        $rows[] = $this->row('лекс казино', 2, 'obzor-kazino.ru', 'Обзор казино Лекс');
        $rows[] = $this->row('лекс казино', 9, 'a.netone.ru');

        $analysis = SerpAnalysis::build($rows, 10, new OwnSites(['ourbase.ru']));
        $byKey = [];
        foreach ($analysis['brands'] as $brand) {
            $byKey[$brand['key']] = $brand;
        }

        // ГЛАВНЫЙ СЛУЧАЙ: по типу захвата бренд «не дорами», а дор в нём забирает — порог это ловит.
        Assert::same('other', $byKey['vulkan']['capture'], 'доля доров: ' . $byKey['vulkan']['door_share']);
        Assert::true($byKey['vulkan']['strong_door'], 'лучший дор забирает ' . $byKey['vulkan']['door_best'] . '%');
        Assert::true($byKey['vulkan']['door_best'] >= SerpAnalysis::DOOR_SHARE_MIN);
        Assert::same('kush.ourbase.ru', $byKey['vulkan']['door_best_host'], 'назван сам дор');
        Assert::true($byKey['vulkan']['door_best_own'], 'и чей он: свой дор на такой доле — уже наша позиция');
        Assert::same(1, $byKey['vulkan']['doors_strong']);

        // Дор стоит, но не забирает: отметки нет, хотя в счёте доров бренда он есть.
        Assert::same(1, $byKey['lex']['counts']['door'], 'дор в выдаче бренда стоит');
        Assert::same(false, $byKey['lex']['strong_door'], 'но забирает всего ' . $byKey['lex']['door_best'] . '%');
        Assert::true($byKey['lex']['door_best'] > 0 && $byKey['lex']['door_best'] < SerpAnalysis::DOOR_SHARE_MIN);
        Assert::same(0, $byKey['lex']['doors_strong']);

        Assert::same(['brands' => 1, 'of' => 2], $analysis['strong_doors'], 'итог по всему списку');
        Assert::contains('в 1 из 2 брендов', SerpAnalysis::strongDoorsText($analysis));
    }

    public function testHostsCsvListsEveryDistinctSiteOnceWithItsType(): void
    {
        // «дай мне кнопку выгрузить все домены чтоб я мог их отдельно анализировать, и чтоб можно
        // было выбрать тип». Разбор по брендам отвечает «кто забрал бренд»; этот файл — про сами
        // домены, поэтому строка на РАЗНЫЙ сайт, а не на пару сайт-бренд: дор одной сетки стоит в
        // нескольких брендах, и в списке он должен быть один, но с числом брендов.
        $rows = [
            $this->row('вулкан казино', 1, 'obzor-kazino.ru', 'Обзор казино Вулкан'),
            $this->row('вулкан казино', 2, 'kush.netone.ru'),
            $this->row('вулкан казино', 3, 'vk.com', 'Вулкан', '', 'excluded_domain'),
            $this->row('лекс казино', 1, 'kush.netone.ru'),
            $this->row('лекс казино', 2, 'lex-casino.ru', 'Лекс казино — обзор'),
        ];
        $analysis = SerpAnalysis::build($rows, 10);

        $all = preg_split('/\r?\n/', SerpAnalysis::hostsCsv($analysis, [], ';', false)) ?: [];
        $all = array_values(array_filter($all));
        Assert::same(5, count($all), 'шапка и по строке на каждый РАЗНЫЙ сайт');
        Assert::contains('Сайт;Домен;Тип', $all[0], 'домен рядом с сайтом — по нему группируют сетку');
        $door = '';
        foreach ($all as $line) {
            if (str_starts_with($line, 'kush.netone.ru;')) {
                $door = $line;
            }
        }
        Assert::contains('kush.netone.ru;netone.ru;"доры (поддомены)"', $door, 'тип и регистрируемый домен');
        Assert::contains(';2;"Lex, vulkan";', $door, 'один раз, но с числом брендов и их списком');
        // Строка выдачи, которую главная отсеяла, здесь всё равно есть: страница про выдачу как она есть.
        Assert::contains('vk.com', implode("\n", $all), 'отсеянные главной строки тоже в списке');

        // ВЫБОР ТИПА: в файле остаются только доры, остальных нет вовсе.
        $doors = array_values(array_filter(preg_split('/\r?\n/', SerpAnalysis::hostsCsv($analysis, ['door'], ';', false)) ?: []));
        Assert::same(2, count($doors), 'шапка и один дор');
        Assert::contains('kush.netone.ru', $doors[1]);
        Assert::notContains('obzor-kazino.ru', implode("\n", $doors), 'тематический домен отфильтрован');
    }

    public function testQueriesWithoutBrandAreCountedApart(): void
    {
        // «без бренда» — остаток запросов, а не бренд: в счёте по типам захвата он стоит отдельно,
        // иначе счёт брендов врёт на одну строку и не сходится с тем, что показано в списке.
        $rows = [
            $this->row('вулкан казино', 1, 'a.netone.ru'),
            $this->row('пластиковые окна москва', 1, 'okna-msk.ru'),
            $this->row('пластиковые окна москва', 2, 'okna-dom.ru'),
        ];

        $analysis = SerpAnalysis::build($rows, 10);

        Assert::same(['door' => 1, 'mixed' => 0, 'other' => 0, 'nobrand' => 1], $analysis['capture']);
        Assert::same(
            'дорами — 1 (дор первым в 1), гибрид — 0, не дорами — 0, без бренда — 1',
            SerpAnalysis::captureText($analysis),
        );
        Assert::same(2, count($analysis['brands']), 'блоков два: бренд и остаток');
    }

    public function testBrandsCsvCarriesTheSplitAndTheLeader(): void
    {
        // Выгрузка нужна, чтобы делить бренды самому (в Excel или скриптом), а не только фильтрами
        // страницы: одна строка на бренд, числа те же, что на экране.
        $rows = [
            $this->row('вулкан казино', 1, 'kush.ourbase.ru'),
            $this->row('вулкан казино', 2, 'other.netone.ru'),
            $this->row('вулкан зеркало', 1, 'kush.ourbase.ru'),
        ];
        $analysis = SerpAnalysis::build($rows, 10, new OwnSites(['ourbase.ru']));
        $csv = SerpAnalysis::brandsCsv($analysis, ';', false);
        $lines = array_values(array_filter(explode("
", str_replace("
", "
", $csv))));

        Assert::same(2, count($lines), 'шапка и одна строка на бренд');
        Assert::contains('Чем забран', $lines[0], 'в шапке есть колонка захвата');
        Assert::contains('Доля доров %', $lines[0]);
        Assert::contains('забран дорами', $lines[1], 'тип захвата подписан словами, а не кодом');
        Assert::contains('kush.ourbase.ru', $lines[1], 'лидер назван');
        // Десятичная запятая: с точкой Excel с русской локалью видит в колонке текст, а не число.
        Assert::contains('100,0', $lines[1], 'доля доров — числом с запятой');
        Assert::contains(';да;', $lines[1], 'лидер наш — по списку запусков');

        // РОТАЦИЯ ЗА ВСЁ ОКНО СБОРОВ — ради неё выгрузку и фильтруют: «был дор, стал тематический»
        // видно не из сравнения с прошлым сбором (там такой бренд ничем не отличается от спокойных),
        // а из всего ряда снимков, поэтому в строке и тип, и сколько сборов назад это случилось.
        Assert::contains('Сменился тип лидера', $lines[0], 'ротация с прошлого сбора');
        Assert::contains('Ротация типа за окно', $lines[0]);
        $analysis['brands'][0]['flip'] = ['from' => 'door', 'to' => 'theme', 'ago' => 3];
        $withFlip = preg_split('/\r?\n/', SerpAnalysis::brandsCsv($analysis, ';', false)) ?: [];
        Assert::contains('"доры (поддомены) → тематические домены";3', (string) ($withFlip[1] ?? ''));

        // Берёт ли место хотя бы один дор — колонками, чтобы список делился и в Excel: по сумме
        // доров («Доля доров %») этого вопроса не задать.
        Assert::contains('Дор от 5%', $lines[0]);
        Assert::contains('Доля лучшего дора %', $lines[0]);
        Assert::contains('Лучший дор', $lines[0]);
        Assert::contains(';да;80,5;kush.ourbase.ru;да;2', $lines[1], 'есть дор, его доля, он сам и сколько таких');
    }

    public function testShowsWhoTakesTheBrand(): void
    {
        // Главный вопрос пользователя к разбору: «кто в бренде победитель и забирает трафик по всем
        // основным ключам». Отвечает доля видимости — вес позиции, просуммированный по ключам бренда:
        // первый на трёх ключах должен обойти того, кто просто присутствует везде внизу.
        $now = gmmktime(12, 0, 0, 10, 27, 2026);
        $rows = [];
        foreach (['вулкан казино', 'вулкан зеркало', 'вулкан слоты'] as $q) {
            $rows[] = $this->row($q, 1, 'leader.ru');
            $rows[] = $this->row($q, 9, 'kush.ourbase.ru');
        }
        $rows[] = $this->row('вулкан казино', 2, 'second.ru');
        // Свежий дор: в выдаче страница моложе двух суток.
        $fresh = $this->row('вулкан слоты', 4, 'fresh-door.ru');
        $fresh['modtime'] = \YandexSites\Support\Freshness::stamp($now - 20 * 3600);
        $rows[] = $fresh;

        $brand = SerpAnalysis::build($rows, 10, new OwnSites(['ourbase.ru']), $now)['brands'][0];

        Assert::same('leader.ru', $brand['leader']['host'], 'победитель — тот, кто держит первые места');
        Assert::true($brand['leader']['share'] > 50.0, 'и его доля больше половины бренда: ' . $brand['leader']['share']);
        Assert::same(3, $brand['leader']['keys'], 'лидер стоит на всех трёх ключах');
        Assert::same(1, $brand['leader']['best']);
        Assert::same(3, $brand['leader']['top3']);

        // Наш сайт тоже на всех ключах, но девятым — доля должна быть кратно меньше.
        Assert::same('kush.ourbase.ru', $brand['our_best']['host'], 'наш лучший найден по списку запусков');
        Assert::true($brand['our_share'] < $brand['leader']['share'] / 5, 'присутствие внизу — это не «забирает бренд»');
        Assert::same(3, $brand['our_best']['keys'], 'ключей столько же, сколько у лидера');

        // Доска отсортирована по доле, сверху победитель; доли в сумме дают 100%.
        $shares = array_column($brand['board'], 'share');
        $sorted = $shares;
        rsort($sorted);
        Assert::same($sorted, $shares, 'доска отсортирована по доле, сверху победитель');
        Assert::same(100.0, round(array_sum($shares), 0), 'доли делят бренд целиком');

        // Свежесть: один сайт моложе двух суток, у остальных её просто нет.
        Assert::same(1, $brand['fresh_sites'], 'свежий сайт в топе ровно один');
        $byHost = [];
        foreach ($brand['board'] as $r) {
            $byHost[$r['host']] = $r;
        }
        Assert::same('20 ч назад', $byHost['fresh-door.ru']['fresh_label']);
        Assert::same(0, $byHost['fresh-door.ru']['fresh_days']);
        Assert::same('', $byHost['leader.ru']['fresh_label'], 'выдача даты не дала — ничего не выдумываем');
        Assert::same(null, $byHost['leader.ru']['fresh_days']);
    }

    public function testOurSiteCanBeTheLeader(): void
    {
        // Если бренд забираем мы — это должно быть видно сразу, без сравнения чисел глазами.
        $now = gmmktime(12, 0, 0, 10, 27, 2026);
        $rows = [$this->row('вулкан казино', 1, 'kush.ourbase.ru'), $this->row('вулкан казино', 2, 'chuzhoy.ru')];
        $brand = SerpAnalysis::build($rows, 10, new OwnSites(['ourbase.ru']), $now)['brands'][0];

        Assert::true($brand['leader']['own'], 'победитель — наш');
        Assert::same($brand['leader']['host'], $brand['our_best']['host']);
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

        Assert::same([['host' => 'c.grid-c.ru', 'type' => 'door']], $diff['brands']['vulkan']['added_hosts'], 'новый дор бренда — с типом');
        Assert::same([['host' => 'b.grid-c.ru', 'type' => 'door']], $diff['brands']['vulkan']['removed_hosts'], 'пропавший дор бренда — с типом');
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

    public function testDiffNamesTheTypeOfEachAppearedSite(): void
    {
        // Ротация видна не только по лидеру: он меняется редко, а состав топа течёт постоянно.
        // Поэтому пришедшие и ушедшие приезжают С ТИПОМ, а не просто именами.
        $prev = SerpAnalysis::index(SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'old-kazino.ru', 'Обзор казино'),
        ], 10));
        $now = SerpAnalysis::build([
            $this->row('вулкан казино', 1, 'a.netone.ru'),
            $this->row('вулкан казино', 2, 'new-kazino.ru', 'Казино обзор'),
        ], 10);

        $diff = SerpAnalysis::diff($prev, $now)['brands']['vulkan'];
        $added = [];
        foreach ($diff['added_hosts'] as $row) {
            $added[$row['host']] = $row['type'];
        }
        Assert::same('door', $added['a.netone.ru'], 'пришёл дор');
        Assert::same('theme', $added['new-kazino.ru'], 'пришёл тематический домен');
        Assert::same('old-kazino.ru', $diff['removed_hosts'][0]['host']);
        Assert::same('theme', $diff['removed_hosts'][0]['type'], 'ушёл тематический');
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
        Assert::same('', $rows[0]['modtime'], 'в сборе прошлой версии колонки свежести нет — и это не ошибка');
    }

    public function testFreshnessSurvivesTheRoundTripThroughResultsCsv(): void
    {
        // Свежесть приходит в <modtime> из Yandex.XML, разбирается у нас с самого начала — но до
        // 1.42.0 терялась перед results.csv, а разбор выдачи строится именно по этому файлу.
        $now = gmmktime(12, 0, 0, 10, 27, 2026);
        $file = sys_get_temp_dir() . '/yandex-sites-serpfresh-' . uniqid() . '.csv';
        $result = new \YandexSites\Model\SearchResult(
            query: 'вулкан казино',
            page: 0,
            position: 1,
            url: 'https://kush.grid-e.ru/',
            host: 'kush.grid-e.ru',
            title: 'Вулкан',
            headline: '',
            snippet: 'казино онлайн',
            modtime: '20261027T040000',
        );
        (new \YandexSites\Output\ReportWriter(';', true))->writeRawCsv([['result' => $result, 'reason' => null]], $file);

        $rows = iterator_to_array(SerpAnalysis::csvRows($file));
        @unlink($file);
        Assert::same('20261027T040000', $rows[0]['modtime'], 'колонка дошла до разбора');

        $brand = SerpAnalysis::build($rows, 10, null, $now)['brands'][0];
        Assert::same('8 ч назад', $brand['board'][0]['fresh_label']);
        Assert::same(1, $brand['fresh_sites']);
    }
}

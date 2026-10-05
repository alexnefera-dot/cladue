<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\OwnSites;

final class OwnSitesTest
{
    public function testMatchesHtmlBySubstring(): void
    {
        $own = new OwnSites(['oasc.team', '2b5b92eb0d01afd5', '/uploads/brands/']);
        Assert::true($own->matchesHtml('<link rel="canonical" href="https://kush.oasc.team/">'), 'домен размещения');
        Assert::true($own->matchesHtml('<meta name="yandex-verification" content="2b5b92eb0d01afd5">'), 'токен');
        Assert::true($own->matchesHtml('<img src="/uploads/brands/logo.svg">'), 'путь к ассетам');
        Assert::false($own->matchesHtml('<html><body>обычный сайт про окна</body></html>'), 'чужой сайт не наш');
    }

    public function testCaseInsensitive(): void
    {
        $own = new OwnSites(['OASC.team']);
        Assert::true($own->matchesHtml('href="https://KUSH.OASC.TEAM/zerkalo"'), 'регистр не важен');
    }

    public function testMatchesHostIncludingSubdomains(): void
    {
        $own = new OwnSites(['oasc.team', '/uploads/brands/']);
        Assert::true($own->matchesHost('oasc.team'), 'сам домен');
        Assert::true($own->matchesHost('kush.oasc.team'), 'поддомен');
        Assert::true($own->matchesHost('a.b.oasc.team'), 'глубокий поддомен');
        Assert::false($own->matchesHost('oasc.team.ru'), 'другой домен, лишь похожий');
        Assert::false($own->matchesHost('okna-moskva.ru'), 'чужой домен');
        // только доменные метки участвуют в проверке хоста
        Assert::same(['oasc.team'], $own->domainMarkers());
    }

    public function testEmptyWhenNoMarkers(): void
    {
        $own = new OwnSites(['   ', '# комментарий', '']);
        Assert::true($own->isEmpty(), 'пустые и комментарии отброшены');
        Assert::false($own->matchesHtml('что угодно oasc.team'), 'без меток ничего не наше');
    }

    public function testMatchesUrlByWordBoundaries(): void
    {
        // Метка-имя (без «/») ищется по ГРАНИЦАМ СЛОВА: короткое «faro» обязано ловить наш редиректор
        // в любом виде, но не чужой safaro.ru — ложное «наш» стоит дороже пропуска.
        $own = new OwnSites(['faro']);
        Assert::true($own->matchesUrl('http://faro.com/go/1'), 'сам домен');
        Assert::true($own->matchesUrl('https://go.faro.net/r?id=7'), 'поддомен');
        Assert::true($own->matchesUrl('https://faro-casino.ru/'), 'домен с дефисом');
        Assert::true($own->matchesUrl('https://casino-faro.ru/'), 'метка в конце имени');
        Assert::false($own->matchesUrl('https://safaro.ru/'), 'чужой домен, лишь содержащий буквы метки');
        Assert::false($own->matchesUrl('https://farolux.ru/'), 'метка склеена со следующим словом');
        Assert::false($own->matchesUrl(''), 'пустой адрес');
    }

    public function testMatchesUrlKeepsSubstringForPathMarkers(): void
    {
        // Метка-путь (с «/») — это кусок адреса, а не имя: ищем подстрокой, как и раньше.
        $own = new OwnSites(['/uploads/brands/']);
        Assert::true($own->matchesUrl('https://okna.ru/uploads/brands/logo.svg'), 'путь к ассетам');
        Assert::false($own->matchesUrl('https://okna.ru/brands/logo.svg'), 'другой путь');
    }

    public function testMatchesAnyUrlWalksRedirectChain(): void
    {
        // Наш дор уводит на свой редиректор, а тот дальше — на чужую рефку: в конечном адресе метки
        // уже нет, она только в промежуточном хопе.
        $own = new OwnSites(['sitegrator']);
        $chain = ['http://ourdoor.ru/', 'https://go.sitegrator.com/r/12', 'https://partner-casino.com/?ref=9'];
        Assert::true($own->matchesAnyUrl($chain), 'метка найдена в промежуточном адресе');
        Assert::false($own->matchesAnyUrl(['http://ourdoor.ru/', 'https://partner-casino.com/']), 'без нашего хопа — не наш');
    }

    public function testMatchesBaseFromLaunchSystem(): void
    {
        // Самый точный источник: базы из системы запусков. База — последние две метки хоста, и любой
        // поддомен на ней наш, даже тот, которого в выгрузке ещё не было.
        $own = new OwnSites([], ['4916.team', 'oasc.team']);
        Assert::false($own->isEmpty(), 'одних баз достаточно, меток можно не иметь');
        Assert::same(['4916.team', 'oasc.team'], $own->bases());

        Assert::true($own->matchesBase('leebet.4916.team'), 'поддомен нашей базы');
        Assert::true($own->matchesBase('4916.team'), 'сама база');
        Assert::true($own->matchesBase('a.b.c.4916.team'), 'глубокий поддомен');
        Assert::true($own->matchesBase('WWW.4916.TEAM'), 'регистр и www не мешают');
        Assert::false($own->matchesBase('kush.stranger.top'), 'чужая база');
        Assert::false($own->matchesBase('4916.team.stranger.top'), 'наша база внутри чужого хоста — не наш');
        Assert::false($own->matchesBase(''), 'пустой хост');

        // Карту «база => true» (её отдаёт Dorgen\OwnBases::bases()) принимаем как есть.
        Assert::true((new OwnSites([], ['4916.team' => true]))->matchesBase('kush.4916.team'));

        // Метки и базы не мешают друг другу: по базе — наш, по метке — тоже, и ни одна не ловит чужого.
        $both = new OwnSites(['sitegrator'], ['4916.team']);
        Assert::true($both->matchesBase('kush.4916.team'));
        Assert::true($both->matchesUrl('https://go.sitegrator.com/r/1'));
        Assert::false($both->matchesBase('kush.sitegrator.com'), 'метка — не база');
        Assert::false($both->matchesHost('kush.4916.team'), 'база не отсеивает на сборе: matchesHost — только метки');
    }

    public function testMatchesBaseInRedirectChain(): void
    {
        // Наш дор уводит на наш же редиректор: в конечном адресе того уже нет, он только в хопе.
        $own = new OwnSites([], ['4916.team']);
        $chain = ['http://ourdoor.top/', 'https://redir.4916.team/r/7', 'https://partner-casino.com/?ref=9'];
        Assert::true($own->matchesBaseInUrls($chain), 'база найдена в промежуточном адресе');
        Assert::true($own->matchesBaseInUrls(['ourdoor.4916.team/vhod']), 'адрес без схемы');
        Assert::false($own->matchesBaseInUrls(['http://ourdoor.top/', 'https://partner-casino.com/']), 'без нашего хопа');
        Assert::false($own->matchesBaseInUrls(['', '   ']), 'пустые адреса');
    }

    public function testFromConfigReadsBasesFromLaunchSystemCache(): void
    {
        // Кэш выгрузки читается тем же загрузчиком, что и страница разбора выдачи, — один список «наших»
        // на все экраны. Отсутствующий файл просто означает «считаем только по меткам».
        $dir = sys_get_temp_dir() . '/yandex-sites-ownbases-' . uniqid();
        mkdir($dir, 0777, true);
        $file = $dir . '/dorgen-bases.json';
        file_put_contents($file, (string) json_encode([
            'date_to' => '2026-10-04',
            'bases' => ['4916.team' => ['subdomains' => 12], '7788.team' => ['subdomains' => 3]],
        ]));

        $own = OwnSites::fromConfig(new \YandexSites\Config([
            'filters' => ['own_markers' => ['sitegrator'], 'own_bases' => ['manual.team'], 'own_bases_file' => $file],
        ]));
        Assert::same(['manual.team', '4916.team', '7788.team'], $own->bases(), 'список из конфигурации + кэш выгрузки');
        Assert::true($own->matchesBase('leebet.4916.team'));
        Assert::same(['sitegrator'], $own->markers(), 'метки не пострадали');

        $none = OwnSites::fromConfig(new \YandexSites\Config([
            'filters' => ['own_markers' => ['sitegrator'], 'own_bases_file' => $dir . '/missing.json'],
        ]));
        Assert::same([], $none->bases(), 'нет файла — нет баз, и это не ошибка');

        @unlink($file);
        @rmdir($dir);
    }

    public function testFromConfigMergesListAndFile(): void
    {
        $file = sys_get_temp_dir() . '/own-markers-' . getmypid() . '.txt';
        file_put_contents($file, "# метки\n/uploads/brands/\n\n2b5b92eb0d01afd5\n");
        $config = new \YandexSites\Config([
            'filters' => ['own_markers' => ['oasc.team'], 'own_markers_file' => $file],
        ]);
        $own = OwnSites::fromConfig($config);
        @unlink($file);

        $markers = $own->markers();
        Assert::inArray('oasc.team', $markers, 'из списка конфигурации');
        Assert::inArray('/uploads/brands/', $markers, 'из файла');
        Assert::inArray('2b5b92eb0d01afd5', $markers, 'из файла');
        Assert::same(3, count($markers), 'без дублей и пустых строк');
    }
}

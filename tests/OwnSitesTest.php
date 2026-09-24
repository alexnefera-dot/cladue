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

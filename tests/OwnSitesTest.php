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

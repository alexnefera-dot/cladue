<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Filter\OwnSites;

/**
 * «Наш» определяется ТОЛЬКО списком запущенных доменов из системы запусков.
 */
final class OwnSitesTest
{
    public function testEmptyWithoutList(): void
    {
        $own = new OwnSites([]);
        Assert::true($own->isEmpty(), 'без списка определять нечем');
        Assert::same(0, $own->count());
        Assert::false($own->matchesBase('kush.4916.team'), 'пустой список никого не помечает');
        Assert::false($own->matchesBaseInUrls(['https://kush.4916.team/']));
    }

    public function testMatchesBaseFromLaunchSystem(): void
    {
        $own = new OwnSites(['4916.team', 'oasc.team']);
        Assert::false($own->isEmpty());
        Assert::same(['4916.team', 'oasc.team'], $own->bases());
        Assert::same(2, $own->count());

        Assert::true($own->matchesBase('leebet.4916.team'), 'поддомен нашей базы');
        Assert::true($own->matchesBase('4916.team'), 'сама база');
        Assert::true($own->matchesBase('a.b.c.4916.team'), 'глубокий поддомен');
        Assert::true($own->matchesBase('WWW.4916.TEAM'), 'регистр и www не мешают');
        Assert::false($own->matchesBase('kush.stranger.top'), 'чужая база');
        Assert::false($own->matchesBase('4916.team.stranger.top'), 'наша база внутри чужого хоста — не наш');
        Assert::false($own->matchesBase(''), 'пустой хост');

        // Карту «база => true» (её отдаёт Dorgen\OwnBases::bases()) принимаем как есть.
        Assert::true((new OwnSites(['4916.team' => true]))->matchesBase('kush.4916.team'));
    }

    public function testZoneIsNeverABase(): void
    {
        // ИМЕННО ТАК и появилось ложное «наш»: прежний baseOf() брал две последние метки, и у базы в
        // зоне второго уровня (4916.net.ru) «базой» становился сам суффикс net.ru — нашими делались
        // ВСЕ сайты зоны. Зона базой быть не может ни на входе, ни при сверке.
        $own = new OwnSites(['net.ru', 'co.uk', 'ru', '']);
        Assert::true($own->isEmpty(), 'из зон список не собирается');
        Assert::false($own->matchesBase('stranger.net.ru'), 'чужой сайт в зоне не наш');

        $real = new OwnSites(['4916.net.ru']);
        Assert::same(['4916.net.ru'], $real->bases(), 'настоящая база в зоне второго уровня сохранена');
        Assert::true($real->matchesBase('leebet.4916.net.ru'), 'её поддомен — наш');
        Assert::false($real->matchesBase('stranger.net.ru'), 'а сосед по зоне — нет');
    }

    public function testMatchesBaseInRedirectChain(): void
    {
        // Наш дор уводит на наш же редиректор: в конечном адресе того уже нет, он только в хопе.
        $own = new OwnSites(['4916.team']);
        $chain = ['http://ourdoor.top/', 'https://redir.4916.team/r/7', 'https://partner-casino.com/?ref=9'];
        Assert::true($own->matchesBaseInUrls($chain), 'база найдена в промежуточном адресе');
        Assert::true($own->matchesBaseInUrls(['ourdoor.4916.team/vhod']), 'адрес без схемы');
        Assert::false($own->matchesBaseInUrls(['http://ourdoor.top/', 'https://partner-casino.com/']), 'без нашего хопа');
        Assert::false($own->matchesBaseInUrls(['', '   ']), 'пустые адреса');
    }

    public function testFromConfigReadsListAndLaunchSystemCache(): void
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-ownbases-' . uniqid();
        mkdir($dir, 0777, true);
        $file = $dir . '/dorgen-bases.json';
        file_put_contents($file, (string) json_encode([
            'date_to' => '2026-10-04',
            'bases' => ['4916.team' => ['subdomains' => 12], '7788.team' => ['subdomains' => 3]],
        ]));

        $own = OwnSites::fromConfig(new \YandexSites\Config([
            'filters' => ['own_bases' => ['manual.team'], 'own_bases_file' => $file],
        ]));
        Assert::same(['manual.team', '4916.team', '7788.team'], $own->bases(), 'список из конфигурации + кэш выгрузки');
        Assert::true($own->matchesBase('leebet.4916.team'));

        $none = OwnSites::fromConfig(new \YandexSites\Config([
            'filters' => ['own_bases' => [], 'own_bases_file' => $dir . '/missing.json'],
        ]));
        Assert::true($none->isEmpty(), 'нет файла — нет списка, и это не ошибка');

        @unlink($file);
        @rmdir($dir);
    }
}

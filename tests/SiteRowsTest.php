<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Support\SiteRows;

final class SiteRowsTest
{
    public function testPreviewCountsMissingFilesAndLoadRestoresVisits(): void
    {
        // Успешный визит, чей файл пропал с диска, — «нет файла»: строка помечена retryable, чтобы докачка его перекачала.
        $dir = sys_get_temp_dir() . '/yandex-sites-rows-' . uniqid();
        mkdir($dir, 0777, true);
        file_put_contents("$dir/vhod.html", '<p>x</p>');
        $site = new Site('rows.ru', 'rows.ru', 'rows.ru');
        $site->add(new SearchResult('q', 0, 1, 'https://rows.ru/', 'rows.ru', 'T'));
        $site->visits = [
            ['variant' => 0, 'url' => 'https://rows.ru/', 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$dir/main.html"],
            ['variant' => 1, 'url' => 'https://rows.ru/vhod', 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$dir/vhod.html"],
        ];
        $row = SiteRows::preview([$site], $dir)[0];
        Assert::same(1, $row['pages_missing'], 'один файл пропал');
        Assert::true($row['retryable'], 'пропавший файл — повод для докачки');
        Assert::same(2, $row['pages_ok']);
        Assert::same('vhod.html', $row['html'], 'ссылка на html — относительно runDir');

        // load(): визиты и признак «наш» восстанавливаются из sites.json.
        file_put_contents("$dir/sites.json", json_encode(['sites' => [['host' => 'rows.ru', 'domain' => 'rows.ru', 'own' => true, 'visits' => $site->visits]]]));
        $loaded = SiteRows::load("$dir/sites.json");
        Assert::true(isset($loaded['rows.ru']), 'сайт прочитан');
        Assert::true($loaded['rows.ru']->own && count($loaded['rows.ru']->visits) === 2, 'визиты и «наш» восстановлены');
    }
}

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
            ['variant' => 1, 'url' => 'https://rows.ru/vhod', 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$dir/vhod.html", 'template' => 'pages7'],
        ];
        $row = SiteRows::preview([$site], $dir)[0];
        Assert::same(1, $row['pages_missing'], 'один файл пропал');
        Assert::true($row['retryable'], 'пропавший файл — повод для докачки');
        Assert::same(2, $row['pages_ok']);
        Assert::same('vhod.html', $row['html'], 'ссылка на html — относительно runDir');
        Assert::same('pages7', $row['template'], 'тип вёрстки — из визитов');
        Assert::same(['registracia', 'zerkalo', 'bonus', 'app', 'slots'], $row['key_missing'], 'вход скачан, остальных ключевых страниц нет');
        Assert::same([], $row['key_failed'], 'ошибок по ключевым страницам не было');
        Assert::true(SiteRows::ROW_LIMIT >= 5000, 'таблица вмещает весь обычный сбор');
        Assert::same(0, count(SiteRows::preview([$site], $dir, 0)), 'лимит строк соблюдается');
        Assert::same('7–9 стр.', $row['template_label']);

        // load(): визиты и признак «наш» восстанавливаются из sites.json.
        file_put_contents("$dir/sites.json", json_encode(['sites' => [['host' => 'rows.ru', 'domain' => 'rows.ru', 'own' => true, 'visits' => $site->visits]]]));
        $loaded = SiteRows::load("$dir/sites.json");
        Assert::true(isset($loaded['rows.ru']), 'сайт прочитан');
        Assert::true($loaded['rows.ru']->own && count($loaded['rows.ru']->visits) === 2, 'визиты и «наш» восстановлены');
    }

    public function testPreviewEmitsDownloadedFlagAndProblemCodes(): void
    {
        // Флаг «выгружен» — по расположению файлов визитов: pages/ (обход) против preview/ (скриншот).
        // Проблемные коды считаются по строке, и стадия зависит от этого флага.
        $base = sys_get_temp_dir() . '/yandex-sites-rows-prob-' . uniqid();
        mkdir($base . '/pages/dl.ru', 0777, true);
        mkdir($base . '/preview/pv.ru', 0777, true);
        file_put_contents("$base/pages/dl.ru/main.html", '<p>home</p>');

        // Выгруженный сайт: главная открылась, вторая страница упала с чинибельной ошибкой → pages_failed.
        $dl = new Site('dl.ru', 'dl.ru', 'dl.ru');
        $dl->add(new SearchResult('q', 0, 1, 'https://dl.ru/', 'dl.ru', 'T'));
        $dl->visits = [
            ['variant' => 0, 'url' => 'https://dl.ru/', 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$base/pages/dl.ru/main.html"],
            ['variant' => 0, 'url' => 'https://dl.ru/vhod', 'ok' => false, 'error' => 'Timeout 30000 ms', 'status' => null, 'html_file' => "$base/pages/dl.ru/vhod.html"],
        ];
        // Сайт только со скриншотом (сбор): превью не получилось → no_preview, стадия «по сбору».
        $pv = new Site('pv.ru', 'pv.ru', 'pv.ru');
        $pv->add(new SearchResult('q', 0, 1, 'https://pv.ru/', 'pv.ru', 'T'));
        $pv->visits = [
            ['variant' => 0, 'url' => 'https://pv.ru/', 'ok' => false, 'error' => 'нет соединения с сайтом', 'status' => null, 'html_file' => "$base/preview/pv.ru/variant-0.html", 'screenshot_file' => ''],
        ];

        $rows = SiteRows::preview([$dl, $pv], $base);
        $byHost = [];
        foreach ($rows as $r) {
            $byHost[$r['host']] = $r;
        }
        Assert::true($byHost['dl.ru']['downloaded'], 'файлы под pages/ — сайт выгружался');
        Assert::same(['pages_failed'], $byHost['dl.ru']['problems'], 'часть страниц упала — проблема по выгрузке');
        Assert::true(!$byHost['pv.ru']['downloaded'], 'файлы под preview/ — выгрузки ещё не было');
        Assert::same(['no_preview'], $byHost['pv.ru']['problems'], 'превью не получилось — проблема по сбору');
    }

    public function testBackfillTemplatesReadsSavedHtmlAndSavesIntoSitesJson(): void
    {
        // Сбор прошлой версии: визиты без поля template. Тип дописывается по сохранённому HTML и попадает в sites.json.
        $dir = sys_get_temp_dir() . '/yandex-sites-rows-tpl-' . uniqid();
        mkdir($dir, 0777, true);
        file_put_contents("$dir/main.html", '<div class="tags-cloud"></div><div class="promo-text"></div><div class="filters-section"></div>');
        $visits = [
            ['variant' => 1, 'url' => 'https://old.ru/', 'ok' => true, 'error' => '', 'status' => 200, 'html_file' => "$dir/main.html"],
            ['variant' => 2, 'url' => 'https://old.ru/x', 'ok' => false, 'error' => 'Timeout', 'status' => null, 'html_file' => ''],
        ];
        file_put_contents("$dir/sites.json", json_encode(['stats' => ['sites_selected' => 1], 'sites' => [['host' => 'old.ru', 'domain' => 'old.ru', 'visits' => $visits]]]));
        $sites = SiteRows::load("$dir/sites.json");
        Assert::same('', SiteRows::preview($sites, $dir)[0]['template'], 'до досчёта типа нет');
        Assert::same(1, SiteRows::backfillTemplates($sites), 'дописан один успешный визит');
        Assert::same('pages7', SiteRows::preview($sites, $dir)[0]['template']);
        Assert::same(0, SiteRows::backfillTemplates($sites), 'повторно файлы не читаются');
        Assert::true(SiteRows::saveTemplates("$dir/sites.json", $sites));
        $saved = json_decode((string) file_get_contents("$dir/sites.json"), true);
        Assert::same('pages7', $saved['sites'][0]['visits'][0]['template'], 'тип записан в sites.json');
        Assert::false(array_key_exists('template', $saved['sites'][0]['visits'][1]), 'неуспешный визит не трогаем');
        Assert::same(1, $saved['stats']['sites_selected'], 'остальное содержимое файла сохранено');
    }

    public function testPageHistogramCountsSitesByOpenedPages(): void
    {
        $mk = static function (string $host, int $ok, int $total, bool $own = false): Site {
            $s = new Site($host, $host, $host);
            $s->own = $own;
            for ($i = 0; $i < $total; $i++) {
                $s->visits[] = ['variant' => $i, 'url' => "https://$host/p$i", 'ok' => $i < $ok, 'error' => $i < $ok ? '' : 'Timeout', 'status' => 200, 'html_file' => ''];
            }

            return $s;
        };
        $hist = SiteRows::pageHistogram([$mk('a.ru', 1, 1), $mk('b.ru', 9, 10), $mk('c.ru', 9, 9), $mk('d.ru', 0, 0), $mk('e.ru', 0, 1, true)]);
        Assert::same([1 => 1, 9 => 2, 'own' => 1], $hist, 'по числу открытых страниц; без визитов не считаем; наши отдельно');
        Assert::same('1 стр. — 1, 9 стр. — 2, наши — 1', SiteRows::histogramText($hist));
        Assert::same('', SiteRows::histogramText([]));
    }
}

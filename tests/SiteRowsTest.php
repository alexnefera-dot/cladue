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
        Assert::true(SiteRows::ROW_LIMIT >= 5000, 'таблица вмещает весь обычный сбор');
        Assert::same(0, count(SiteRows::preview([$site], $dir, 0)), 'лимит строк соблюдается');
        Assert::same('7–9 стр.', $row['template_label']);

        // load(): визиты и признак «наш» восстанавливаются из sites.json.
        file_put_contents("$dir/sites.json", json_encode(['sites' => [['host' => 'rows.ru', 'domain' => 'rows.ru', 'own' => true, 'visits' => $site->visits]]]));
        $loaded = SiteRows::load("$dir/sites.json");
        Assert::true(isset($loaded['rows.ru']), 'сайт прочитан');
        Assert::true($loaded['rows.ru']->own && count($loaded['rows.ru']->visits) === 2, 'визиты и «наш» восстановлены');
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

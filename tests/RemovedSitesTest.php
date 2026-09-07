<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\RemovedSites;

/**
 * Серверный список убранных сайтов: строки уходят из sites.json/status.json, папки — в removed/, и обратно.
 */
final class RemovedSitesTest
{
    private function runDir(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-removed-' . uniqid();
        foreach (['pages/3-стр/a.ru', 'preview/a.ru', 'content/2-стр/a.ru', 'pages/1-стр/b.ru'] as $d) {
            mkdir("$dir/$d", 0777, true);
            file_put_contents("$dir/$d/main.html", '<html>x</html>');
        }
        file_put_contents("$dir/sites.json", json_encode(['sites' => [
            ['host' => 'a.ru', 'domain' => 'a.ru', 'visits' => [['url' => 'http://a.ru/', 'ok' => true]]],
            ['host' => 'b.ru', 'domain' => 'b.ru', 'visits' => []],
        ]]));
        file_put_contents("$dir/status.json", json_encode(['state' => 'done', 'sites' => [
            ['host' => 'a.ru', 'pages_ok' => 3], ['host' => 'b.ru', 'pages_ok' => 1],
        ]]));

        return $dir;
    }

    public function testRemoveMovesRowsAndDirsThenRestoreBringsThemBack(): void
    {
        $dir = $this->runDir();
        Assert::same(1, RemovedSites::remove($dir, ['a.ru']));

        $sites = json_decode((string) file_get_contents("$dir/sites.json"), true);
        Assert::same(['b.ru'], array_map(static fn ($r) => $r['host'], $sites['sites']), 'строка ушла из sites.json');
        $status = json_decode((string) file_get_contents("$dir/status.json"), true);
        Assert::same(['b.ru'], array_map(static fn ($r) => $r['host'], $status['sites']), 'строка ушла из status.json — таблица обновится сразу');
        Assert::same(['a.ru'], RemovedSites::hosts($dir));
        Assert::false(is_dir("$dir/pages/3-стр/a.ru") || is_dir("$dir/preview/a.ru") || is_dir("$dir/content/2-стр/a.ru"), 'папки сайта убраны из результата');
        Assert::true(is_file("$dir/removed/pages/3-стр/a.ru/main.html") && is_dir("$dir/removed/preview/a.ru") && is_dir("$dir/removed/content/2-стр/a.ru"), 'папки переехали в removed/ с той же структурой');
        Assert::true(is_dir("$dir/pages/1-стр/b.ru"), 'чужие папки не тронуты');

        // filter() — то, чем пользуется run-job: убранный отбрасывается из списка сайтов.
        Assert::same(['b.ru'], array_keys(RemovedSites::filter($dir, ['a.ru' => 1, 'b.ru' => 2])));

        Assert::same(1, RemovedSites::restore($dir));
        $sites = json_decode((string) file_get_contents("$dir/sites.json"), true);
        $hosts = array_map(static fn ($r) => $r['host'], $sites['sites']);
        sort($hosts);
        Assert::same(['a.ru', 'b.ru'], $hosts, 'строка вернулась в sites.json');
        $status = json_decode((string) file_get_contents("$dir/status.json"), true);
        Assert::same(2, count($status['sites']), 'строка вернулась в status.json');
        Assert::true(is_file("$dir/pages/3-стр/a.ru/main.html") && is_dir("$dir/preview/a.ru"), 'папки вернулись на место');
        Assert::same([], RemovedSites::hosts($dir), 'список убранных пуст');
        Assert::false(is_file("$dir/removed.json"));
    }

    public function testSweepMovesDirsThatReappearedAndClearResets(): void
    {
        $dir = $this->runDir();
        RemovedSites::remove($dir, ['a.ru']);
        // Задание успело докачать убранный сайт — папка появилась снова; sweep уносит её.
        mkdir("$dir/pages/4-стр/a.ru", 0777, true);
        file_put_contents("$dir/pages/4-стр/a.ru/app.html", 'x');
        RemovedSites::sweep($dir);
        Assert::false(is_dir("$dir/pages/4-стр/a.ru"), 'вновь появившаяся папка убрана');
        Assert::true(is_file("$dir/removed/pages/4-стр/a.ru/app.html"));

        RemovedSites::clear($dir);
        Assert::false(is_file("$dir/removed.json") || is_dir("$dir/removed"), 'новый сбор — список и папки убранных очищены');
    }
}

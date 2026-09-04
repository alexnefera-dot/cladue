<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Output\ReportWriter;

final class ReportWriterTest
{
    public function testWritesAllFormats(): void
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-out-' . uniqid();
        $site = new Site('okna-moskva.ru', 'okna-moskva.ru', 'okna-moskva.ru');
        $r1 = new SearchResult('окна; пвх', 0, 3, 'https://okna-moskva.ru/a', 'okna-moskva.ru', 'Окна "ПВХ"', '', 'Сниппет');
        $r2 = new SearchResult('балконы', 0, 1, 'https://okna-moskva.ru/b', 'okna-moskva.ru', 'Балконы');
        $site->add($r1);
        $site->add($r2);
        $site->check = ['ok' => true, 'reason' => '', 'status' => 200, 'final_url' => 'https://okna-moskva.ru/', 'title' => 'Главная', 'error' => ''];

        $writer = new ReportWriter(';', true);
        $writer->writeCsv([$site], $dir . '/sub/sites.csv');
        $writer->writeJson([$site], $dir . '/sites.json', ['stats' => ['x' => 1]]);
        $writer->writeDomains([$site], $dir . '/domains.txt');
        $writer->writeRawCsv([['result' => $r1, 'reason' => null], ['result' => $r2, 'reason' => 'tld']], $dir . '/results.csv');

        $csv = (string) file_get_contents($dir . '/sub/sites.csv');
        Assert::true(str_starts_with($csv, "\xEF\xBB\xBF"), 'BOM для Excel');
        $lines = explode("\n", trim($csv));
        Assert::same(2, count($lines));
        Assert::contains('host;host_unicode;domain;url;title;best_position', $lines[0]);
        Assert::contains('okna-moskva.ru;okna-moskva.ru;okna-moskva.ru;https://okna-moskva.ru/b;Балконы;1;балконы;2;2;"окна; пвх (3) | балконы (1)";200;https://okna-moskva.ru/;Главная;ok', $lines[1]);

        $json = json_decode((string) file_get_contents($dir . '/sites.json'), true);
        Assert::same(1, $json['meta']['stats']['x']);
        Assert::same('okna-moskva.ru', $json['sites'][0]['host']);
        Assert::same(['окна; пвх' => 3, 'балконы' => 1], $json['sites'][0]['queries']);
        Assert::same(true, $json['sites'][0]['check']['ok']);

        Assert::same("okna-moskva.ru\n", (string) file_get_contents($dir . '/domains.txt'));

        $raw = explode("\n", trim((string) file_get_contents($dir . '/results.csv')));
        Assert::same(3, count($raw));
        Assert::contains('"окна; пвх";1;3;okna-moskva.ru;https://okna-moskva.ru/a;"Окна ""ПВХ""";"Окна ""ПВХ"" Сниппет";selected', $raw[1]);
        Assert::contains(';tld', $raw[2]);

        $writer = new ReportWriter(',', false);
        $writer->writeDomains([], $dir . '/empty.txt');
        Assert::same('', (string) file_get_contents($dir . '/empty.txt'));

        foreach (['sub/sites.csv', 'sites.json', 'domains.txt', 'results.csv', 'empty.txt'] as $file) {
            unlink($dir . '/' . $file);
        }
        rmdir($dir . '/sub');
        rmdir($dir);
    }
}

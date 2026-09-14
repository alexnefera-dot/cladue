<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Model\Site;
use YandexSites\Visit\KeyPages;

final class KeyPagesTest
{
    public function testRecognisesKeyPagesByUrlOrFileName(): void
    {
        Assert::same('registracia', KeyPages::of('https://site.ru/registracia'));
        Assert::same('registracia', KeyPages::of('registracia.html'));
        Assert::same('registracia', KeyPages::of('https://site.ru/ru/registration/'));
        Assert::same('vhod', KeyPages::of('https://site.ru/login?ref=menu'));
        Assert::same('zerkalo', KeyPages::of('zerkalo.html'));
        Assert::same('bonus', KeyPages::of('https://site.ru/bonusy'), 'бонусы — отдельная страница, не «приложение»');
        Assert::same('app', KeyPages::of('https://site.ru/prilozhenie'));
        Assert::same('slots', KeyPages::of('https://site.ru/igrovye-avtomaty'));
        Assert::same(null, KeyPages::of('https://site.ru/'), 'главная — не ключевая страница');
        Assert::same(null, KeyPages::of('main.html'));
        Assert::same(null, KeyPages::of('https://site.ru/o-kompanii'));
        Assert::same('регистрация', KeyPages::label('registracia'));
        Assert::same('https://site.ru/vhod', KeyPages::url('https://site.ru/', 'vhod'), 'адрес строится от корня сайта');
        Assert::same('http://site.ru:8080/app', KeyPages::url('http://site.ru:8080/', 'app'));
    }

    public function testStatusesSplitFailedPagesFromMissingLinks(): void
    {
        // Страница с ошибкой — «можно добрать», страницы без визита вообще — ссылки на них не нашлось.
        $visits = [
            ['ok' => true, 'url' => 'https://s.ru/', 'html_file' => '/p/s.ru/main.html'],
            ['ok' => true, 'url' => 'https://s.ru/vhod', 'html_file' => '/p/s.ru/vhod.html'],
            ['ok' => false, 'url' => 'https://s.ru/registracia', 'error' => 'таймаут', 'html_file' => ''],
        ];
        $statuses = KeyPages::statuses($visits);
        Assert::same('ok', $statuses['vhod']);
        Assert::same('failed', $statuses['registracia']);
        Assert::same('none', $statuses['zerkalo']);
        Assert::same(['registracia', 'zerkalo', 'bonus', 'app', 'slots'], KeyPages::missing($visits), 'порядок — как в списке ключевых страниц');

        // Успешный визит перебивает неудачный: страницу добрали со второй попытки.
        $statuses = KeyPages::statuses([
            ['ok' => false, 'url' => 'https://s.ru/app', 'html_file' => ''],
            ['ok' => true, 'url' => 'https://s.ru/app', 'html_file' => '/p/s.ru/app.html'],
        ]);
        Assert::same('ok', $statuses['app']);
    }

    public function testHistogramCountsSitesPerMissingPage(): void
    {
        $mk = static function (string $host, array $ok, bool $own = false, bool $noVisits = false): Site {
            $site = new Site($host, $host, $host);
            $site->own = $own;
            if (!$noVisits) {
                $site->visits[] = ['ok' => true, 'url' => "https://$host/", 'html_file' => "/p/$host/main.html"];
                foreach ($ok as $name) {
                    $site->visits[] = ['ok' => true, 'url' => "https://$host/$name", 'html_file' => "/p/$host/$name.html"];
                }
            }

            return $site;
        };
        $hist = KeyPages::histogram([
            $mk('a.ru', ['registracia', 'vhod', 'zerkalo', 'bonus', 'app', 'slots']), // всё на месте
            $mk('b.ru', ['vhod', 'zerkalo', 'bonus', 'app', 'slots']),                 // нет регистрации
            $mk('c.ru', ['zerkalo', 'bonus', 'app', 'slots']),                         // нет регистрации и входа
            $mk('own.ru', [], true),                                                   // наш — не считаем
            $mk('empty.ru', [], false, true),                                          // не выгружался — не считаем
        ]);
        Assert::same(['registracia' => 2, 'vhod' => 1], $hist);
        Assert::same('регистрация — 2, вход — 1', KeyPages::histogramText($hist));
        Assert::same('', KeyPages::histogramText([]));
    }
}

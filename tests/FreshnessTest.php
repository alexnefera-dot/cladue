<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\Freshness;

final class FreshnessTest
{
    /** «Сейчас» для всех проверок — фиксированное, иначе тест зависел бы от дня запуска. */
    private function now(): int
    {
        return gmmktime(12, 0, 0, 10, 27, 2026);
    }

    public function testParsesEveryShapeSerpGivesUs(): void
    {
        $now = $this->now();
        // Формат Yandex.XML (<modtime>) — им приходит свежесть из api и xmlstock.
        Assert::same(gmmktime(10, 15, 0, 8, 15, 2025), Freshness::parse('20250815T101500', $now));
        // ISO — на случай другого источника.
        Assert::same(gmmktime(4, 0, 0, 10, 27, 2026), Freshness::parse('2026-10-27T04:00:00+00:00', $now));
        // Относительные подписи живой выдачи.
        Assert::same($now - 8 * 3600, Freshness::parse('8 ч назад', $now));
        Assert::same($now - 5 * 3600, Freshness::parse('5 часов назад', $now));
        Assert::same($now - 32 * 60, Freshness::parse('32 мин назад', $now));
        Assert::same($now - 86400, Freshness::parse('вчера', $now));
        Assert::same($now - 3 * 86400, Freshness::parse('3 дня назад', $now));
        // Длинная основа разбирается раньше короткой, иначе «недели» читались бы как «дни».
        Assert::same($now - 14 * 86400, Freshness::parse('2 недели назад', $now), 'недели — не дни');
        // Русская дата.
        Assert::same(gmmktime(12, 0, 0, 8, 15, 2025), Freshness::parse('15 авг 2025', $now));
        // Не дата — ничего не выдумываем.
        Assert::same(null, Freshness::parse('реклама', $now));
        Assert::same(null, Freshness::parse('', $now));
    }

    public function testLabelAndDays(): void
    {
        $now = $this->now();
        Assert::same('8 ч назад', Freshness::label($now - 8 * 3600, $now));
        Assert::same('32 мин назад', Freshness::label($now - 32 * 60, $now));
        Assert::same('только что', Freshness::label($now - 5, $now));
        Assert::same('вчера', Freshness::label($now - 86400, $now));
        Assert::same('5 дн. назад', Freshness::label($now - 5 * 86400, $now));
        Assert::same('15.08.2025', Freshness::label(gmmktime(10, 0, 0, 8, 15, 2025), $now), 'старое — обычной датой');
        Assert::same('', Freshness::label(null, $now));

        Assert::same(0, Freshness::days($now - 3600, $now));
        Assert::same(3, Freshness::days($now - 3 * 86400, $now));
        Assert::same(null, Freshness::days(null, $now));
    }

    public function testOnlyShortWholeLabelsCountAsDate(): void
    {
        // Так разбор живой выдачи отличает подпись свежести от текста сниппета, где «3 дня назад»
        // может стоять посреди предложения. Проверяем ровно это: короткий узел целиком — дата.
        Assert::true(Freshness::looksLikeLabel('8 ч назад'));
        Assert::true(Freshness::looksLikeLabel('вчера'));
        Assert::true(Freshness::looksLikeLabel('15 авг 2025'));
        Assert::false(Freshness::looksLikeLabel('3 дня назад мы снизили цены на окна'), 'длинный текст — не подпись');
        Assert::false(Freshness::looksLikeLabel('Реклама'));
        Assert::false(Freshness::looksLikeLabel(''));
    }

    public function testStampRoundTrip(): void
    {
        // В results.csv свежесть хранится в формате Яндекса — и читается обратно без потерь.
        $ts = gmmktime(4, 0, 0, 10, 27, 2026);
        Assert::same('20261027T040000', Freshness::stamp($ts));
        Assert::same($ts, Freshness::parse(Freshness::stamp($ts), $this->now()));
    }
}

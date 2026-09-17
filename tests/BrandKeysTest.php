<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Content\BrandKeys;

/**
 * Бренд из поискового ключа: одно и то же название в кириллице и латинице должно давать ОДИН ключ,
 * иначе домен сетки «держит» вдвое больше брендов, чем на самом деле.
 */
final class BrandKeysTest
{
    public function testSameBrandInBothSpellingsGivesOneKey(): void
    {
        $pairs = [
            ['вулкан вегас казино официальный сайт', 'Vulkan Vegas зеркало'],
            ['криптобосс вход', 'cryptoboss casino'],
            ['мани икс играть', 'Money X официальный сайт'],
            ['драгон мани бонус', 'Dragon Money'],
            ['гет икс зеркало', 'GetX'],
            ['стейк казино', 'Stake'],
            ['раменбет', 'Ramenbet онлайн'],
        ];
        foreach ($pairs as [$ru, $en]) {
            $a = BrandKeys::of($ru);
            $b = BrandKeys::of($en);
            Assert::true($a !== '', "бренд найден в «{$ru}»");
            Assert::same($a, $b, "«{$ru}» и «{$en}» — один бренд");
        }
    }

    public function testTranslitBrandsFoldWithoutList(): void
    {
        // Бренда нет в списке пар, но кириллица — это транслит: фонетика сводит их сама.
        Assert::same(BrandKeys::of('зумбетто казино'), BrandKeys::of('zumbetto casino'), 'транслит сводится');
        Assert::same('kriptobos', BrandKeys::of('криптобосс'), 'c/k, y/i и сдвоенные буквы схлопнуты');
        Assert::same(BrandKeys::normalize('Crypto Boss'), BrandKeys::normalize('криптобосс'), 'пробел внутри названия не мешает');
    }

    public function testDigitsAreKeptInBrand(): void
    {
        // Цифры — часть названия: 1xBet, Azino777, 7K.
        Assert::same(BrandKeys::of('1xbet зеркало рабочее 2025'), BrandKeys::of('1хБет'), 'год выбрасывается, цифры бренда — нет');
        Assert::true(str_contains(BrandKeys::of('азино777 играть'), '777') || BrandKeys::of('азино777 играть') === 'azino7', 'цифры остались в ключе');
    }

    public function testGenericQueryIsNotABrand(): void
    {
        Assert::same('', BrandKeys::of('пластиковые окна москва цена'), 'обычный запрос из трёх слов — не бренд');
        Assert::same('', BrandKeys::of('казино онлайн официальный сайт'), 'одни служебные слова — не бренд');
        Assert::same('', BrandKeys::of(''), 'пустой запрос');
        Assert::same('', BrandKeys::of('играть бесплатно и без регистрации в игровые автоматы'), 'длинный общий запрос');
    }

    public function testKnownBrandWinsOverLeftoverWords(): void
    {
        // «Вулкан Вегас» — отдельный бренд, не «Вулкан» + «Вегас»: длинные названия проверяются первыми.
        Assert::same(BrandKeys::of('Vulkan Vegas'), BrandKeys::of('вулкан вегас'), 'два слова — один бренд');
        Assert::true(BrandKeys::of('вулкан вегас') !== BrandKeys::of('вулкан'), 'это разные бренды');
        // Служебные слова вокруг бренда не мешают.
        Assert::same(BrandKeys::of('комета'), BrandKeys::of('комета казино зеркало на сегодня'));
    }

    public function testLabelReturnsLatinSpelling(): void
    {
        Assert::same('Kometa', BrandKeys::label(BrandKeys::of('комета казино')), 'в списках показываем латиницу');
        Assert::same('неизвестный', BrandKeys::label('неизвестный'), 'неизвестный ключ отдаём как есть');
    }
}

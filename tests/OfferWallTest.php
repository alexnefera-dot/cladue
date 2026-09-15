<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Visit\OfferWall;

/**
 * Распознавание витрины офферов — страницы-подмены вместо настоящего сайта.
 *
 * Главное здесь — не ложные срабатывания: ошибочно выбросить настоящий сайт дороже, чем не
 * распознать очередную заглушку, поэтому отрицательных примеров больше, чем положительных.
 */
final class OfferWallTest
{
    /** Витрина со скриншота пользователя: заголовок, «В подборке 6 офферов», карточки, бегущая строка. */
    private function wall(): string
    {
        return '<html><head><title>Бонусы казино</title></head><body>'
            . '<div class="logo">ARKADA</div>'
            . '<h1>СТАРЫЕ ПРАВИЛА НОВЫЕ УСЛОВИЯ</h1>'
            . '<p>В подборке 6 офферов, все проверены. Откройте любой, чтобы увидеть полные условия.</p>'
            . '<div><span>ПЕРВЫЙ НОМЕР</span><span>Ля Casino</span><span>100% На 1-й депозит</span><span>+300 FS</span><a href="/go/1">ЗАБРАТЬ БОНУС</a></div>'
            . '<div><span>MAD</span><span>455% или 455 FS</span><a href="/go/2">ЗАБРАТЬ БОНУС</a></div>'
            . '<div><span>PINCO</span><span>БОНУС 120% + 250 FS</span><a href="/go/3">ЗАБРАТЬ БОНУС</a></div>'
            . '<div><span>SPINTO</span><span>БОНУС до 500 000 ₽ + 500 FS</span><a href="/go/4">ЗАБРАТЬ БОНУС</a></div>'
            . '<div><span>7K</span><span>300 000 ₽ 500 FS FREEBET</span><a href="/go/5">ЗАБРАТЬ БОНУС</a></div>'
            . '<div class="ticker">7K КАЗИНО CASINO — 300 000 ₽ 500 FS FREEBET · ПИНКО КАЗИНО CASINO — БОНУС 120% + 250 FS</div>'
            . '<footer>18+ Азартные игры являются развлечением. Проверяйте условия бонуса партнёра перед регистрацией.</footer>'
            . '</body></html>';
    }

    public function testRecognizesOfferWall(): void
    {
        Assert::true(OfferWall::looksLike($this->wall()), 'витрина офферов распознана');
        [$score, $strong] = OfferWall::score($this->wall());
        Assert::true($score >= OfferWall::MIN_SCORE, "сумма признаков $score");
        Assert::true($strong > 0, 'есть сильный признак');
    }

    public function testRecognizesWallWithoutOfferWord(): void
    {
        // Часть витрин обходится без слова «оффер» — их выдают повторяющиеся карточки и бегущая строка.
        $html = str_replace(
            ['В подборке 6 офферов, все проверены. Откройте любой, чтобы увидеть полные условия.', 'условия бонуса партнёра'],
            ['Лучшие бонусы этого месяца.', 'условия'],
            $this->wall(),
        );
        Assert::true(OfferWall::looksLike($html), 'витрина без слова «оффер» тоже распознана');
    }

    public function testRealSiteIsNotAWall(): void
    {
        // Настоящий сайт бренда: длинный текст, свой бренд, одна кнопка бонуса.
        $html = '<html><head><title>Аркада Казино</title></head><body><header><nav>'
            . '<a href="/vhod">Вход</a><a href="/registracia">Регистрация</a></nav></header><h1>Аркада Казино</h1>'
            . '<a href="/bonus">Забрать бонус</a><p>' . str_repeat('Аркада казино предлагает игровые автоматы и быстрые выплаты. ', 40) . '</p>'
            . '<footer>18+ Азартные игры являются развлечением.</footer></body></html>';
        Assert::false(OfferWall::looksLike($html), 'настоящий сайт не витрина');
    }

    public function testShortRealHomePageIsNotAWall(): void
    {
        // Короткая главная настоящего сайта: дисклеймер «Азартные игры являются развлечением», «18+»
        // и «на 1-й депозит» бывают и здесь — сами по себе они витрину не делают.
        $html = '<html><head><title>Аркада</title></head><body><header><nav><a href="/vhod">Вход</a>'
            . '<a href="/registracia">Регистрация</a><a href="/bonus">Бонусы</a></nav></header><h1>Аркада Казино</h1>'
            . '<p>Официальный сайт: игровые автоматы, быстрые выплаты и бонус 100% на 1-й депозит +300 FS.</p>'
            . '<a href="/bonus">Забрать бонус</a><footer>18+ Азартные игры являются развлечением.</footer></body></html>';
        Assert::false(OfferWall::looksLike($html), 'короткая главная не витрина');
    }

    public function testBonusPageWithSeveralButtonsIsNotAWall(): void
    {
        // Своя страница бонусов: несколько кнопок «Забрать бонус», но это текст про свой бренд.
        $html = '<html><head><title>Бонусы Аркада</title></head><body><h1>Бонусы</h1>'
            . '<div><span>100% на 1-й депозит</span><a href="/b1">Забрать бонус</a></div>'
            . '<div><span>Кэшбэк 10%</span><a href="/b2">Забрать бонус</a></div>'
            . '<div><span>Фриспины по средам</span><a href="/b3">Забрать бонус</a></div>'
            . '<p>' . str_repeat('Условия отыгрыша бонуса в Аркада казино описаны в правилах акции. ', 60) . '</p>'
            . '</body></html>';
        Assert::false(OfferWall::looksLike($html), 'страница бонусов своего бренда не витрина');
    }

    public function testAgeGateIsNotAWall(): void
    {
        $html = '<html><head><title>Подтвердите возраст</title></head><body><h1>Вам есть 18 лет?</h1>'
            . '<button>Да, мне есть 18</button><a href="/no">Нет</a></body></html>';
        Assert::false(OfferWall::looksLike($html), 'возрастная заглушка — не витрина (у неё свой разбор)');
    }

    public function testLongPageIsNeverAWall(): void
    {
        // Даже с формулировками витрины длинная страница витриной не считается: это уже статья.
        $html = '<html><body><p>В подборке 6 офферов. Проверяйте условия бонуса партнёра.</p><p>'
            . str_repeat('Длинный текст статьи про бонусы казино и условия их отыгрыша. ', 80) . '</p></body></html>';
        Assert::false(OfferWall::looksLike($html), 'длинная страница не витрина');
    }
}

<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Content\ContentCleaner;

final class ContentCleanerTest
{
    private function page(): string
    {
        return '<!DOCTYPE html><html><head><title>t</title><style>.x{}</style></head><body>'
            . '<header><nav><a href="/">Лого</a></nav></header>'
            . '<h1>Криптобосс — обзор 13.05.2026</h1>'
            . '<p>Обзор Cryptoboss на сайте cryptoboss.com. Регистрация: '
            . '<a href="https://cryptoboss.com/registracia">тут</a>. Дата 13.05.2026. Криптобосс топ.</p>'
            . '<h2>Слоты</h2><div class="games"><a href="/games">игры</a> много слотов тут</div>'
            . '<h2>Вывод</h2><p>Итог про STAKЕ и <a href="https://cryptoboss.ccy.casino/en/en/en/bonus">бонус</a>.</p>'
            . '<h3>Популярные запросы</h3><ul><li>крипто</li></ul>'
            . '<footer>подвал</footer><script>var x=1;</script></body></html>';
    }

    public function testExtractArticleDropsChromeAndPopular(): void
    {
        $body = (new ContentCleaner())->extractArticle($this->page());
        Assert::false(str_contains($body, '<h1'), 'заголовок h1 удалён');
        Assert::false(str_contains($body, 'Лого'), 'шапка удалена');
        Assert::false(str_contains($body, 'подвал'), 'подвал удалён');
        Assert::false(str_contains($body, 'Популярные'), 'блок «Популярные запросы» и всё после — удалено');
        Assert::false(str_contains($body, 'var x=1'), 'скрипты удалены');
        Assert::true(str_contains($body, 'Обзор Cryptoboss'), 'тело статьи осталось');
    }

    public function testStripsMediaUiModalsContactsAndTags(): void
    {
        $html = '<h1>Обзор</h1>'
            . '<p>Текст статьи про бренд.</p>'
            . '<img src="/logo.png" alt="лого">'
            . '<p>Ещё абзац <button>Играть</button> и форма <form><input></form>.</p>'
            . '<table><tr><td>Лицензия</td><td>Curacao</td></tr></table>'
            . '<blockquote>Мнение<footer>— автор, 2024</footer></blockquote>'
            . '<div class="tag-cloud"><a href="/t">слоты</a><a href="/t2">бонусы</a></div>'
            . '<div class="footer-contacts">Телефон: +7-900-000</div>'
            . '<div class="promo" role="dialog"><button>×</button>Бонус 250%</div>'
            . '<footer>Подвал сайта © 2024</footer>';
        $body = (new ContentCleaner())->extractArticle($html);
        Assert::false(str_contains($body, '<img'), 'изображения удалены');
        Assert::false(str_contains($body, '<button'), 'кнопки удалены');
        Assert::false(str_contains($body, '<form'), 'формы удалены');
        Assert::false(str_contains($body, 'role="dialog"'), 'модалки удалены');
        Assert::false(str_contains($body, 'Бонус 250%'), 'содержимое модалки удалено');
        Assert::false(str_contains($body, 'слоты') && str_contains($body, 'бонусы'), 'облако тегов удалено');
        Assert::false(str_contains($body, '+7-900-000'), 'блок контактов удалён');
        Assert::false(str_contains($body, 'Подвал сайта'), 'подвал сайта удалён');
        Assert::true(str_contains($body, 'Текст статьи'), 'тело статьи осталось');
        Assert::true(str_contains($body, '<table'), 'таблица статьи осталась');
        Assert::true(str_contains($body, '— автор, 2024'), 'подпись в цитате (footer в blockquote) осталась');
    }

    public function testRemoveSlots(): void
    {
        $cleaner = new ContentCleaner();
        $body = $cleaner->removeSlots('<p>до</p><h2>Слоты</h2><div>много слотов</div><h2>Вывод</h2><p>после</p>');
        Assert::false(str_contains($body, 'много слотов'), 'секция слотов удалена');
        Assert::true(str_contains($body, 'до') && str_contains($body, 'Вывод') && str_contains($body, 'после'), 'остальное осталось');
    }

    public function testMapLinkToAllowedPaths(): void
    {
        $c = new ContentCleaner();
        Assert::same('/registracia', $c->mapLink('https://cryptoboss.com/registracia'));
        Assert::same('/registracia', $c->mapLink('/registration'));
        Assert::same('/vhod', $c->mapLink('http://cryptoboss-site.net/login'));
        Assert::same('/vhod', $c->mapLink('/enter'));
        Assert::same('/app', $c->mapLink('https://cryptoboss.ccy.casino/en/en/en/en/bonus'));
        Assert::same('/app', $c->mapLink('/download'));
        Assert::same('/slots', $c->mapLink('//somedomain.com/games'));
        Assert::same('/slots', $c->mapLink('/igrat'));
        Assert::same('/zerkalo', $c->mapLink('/mirror'));
        Assert::same('/main', $c->mapLink('https://%domain_name%/home'));
        Assert::same('/main', $c->mapLink('/'));
        Assert::same('/vhod', $c->mapLink('https://%domain_name%/vhod'));
        Assert::same('/main', $c->mapLink('/nechto-neponyatnoe'), 'неизвестное → /main');
    }

    public function testFullCleanTemplatesEverything(): void
    {
        $out = (new ContentCleaner())->clean($this->page(), [
            'domain' => 'cryptoboss.com',
            'hosts' => ['cryptoboss.ccy.casino'],
            'brand_ru' => 'криптобосс',
            'brand_en' => 'cryptoboss',
            'extra_brands' => ['STAKE'],
        ]);

        // переменные подставлены
        Assert::true(str_contains($out, '%domain_name%'), 'домен → %domain_name%');
        Assert::true(str_contains($out, '%date%'), 'дата → %date%');
        Assert::true(str_contains($out, '%brand_name_ru%'), 'русский бренд → переменная');
        Assert::true(str_contains($out, '%brand_name_en%'), 'английский бренд → переменная');
        // ссылки относительные из списка
        Assert::true(str_contains($out, 'href="/registracia"'));
        Assert::true(str_contains($out, 'href="/app"'), 'bonus → /app');
        // ничего лишнего не осталось
        Assert::false(stripos($out, 'cryptoboss') !== false, 'старый домен/бренд en не остались');
        Assert::false(str_contains($out, 'Криптобосс'), 'старый бренд ru не остался');
        Assert::false(stripos($out, 'stak') !== false, 'сторонний бренд/опечатка (STAKЕ) заменён');
        Assert::false(str_contains($out, 'ccy.casino'), 'домен из ссылки убран');
        Assert::false(str_contains($out, '13.05.2026'), 'дата заменена');
        Assert::false(str_contains($out, 'много слотов'), 'блок слотов удалён');
        Assert::false(str_contains($out, 'Популярные'), 'блок «Популярные запросы» удалён');
        Assert::true(str_contains($out, 'Итог'), 'полезный текст остался');
    }

    public function testAutoCatchesForeignBrands(): void
    {
        // autoOptions добавляет список известных брендов → чужие бренды тоже уходят в переменные.
        $html = '<h1>Криптобосс</h1><p>Криптобосс против Вавада и Mostbet, ещё STAKЕ и play fortuna. В мире стейка вкусно.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ContentCleaner::autoOptions($html, 'cryptoboss.com'));

        Assert::false(stripos($out, 'вавада') !== false, 'чужой бренд (Вавада) заменён');
        Assert::false(stripos($out, 'mostbet') !== false, 'чужой бренд (Mostbet) заменён');
        Assert::false(stripos($out, 'stak') !== false, 'опечатка STAKЕ заменена');
        Assert::false(stripos($out, 'fortuna') !== false, 'многословный бренд заменён');
        Assert::true(str_contains($out, 'стейка'), 'слово «стейка» (не бренд) сохранено — границы слова');
        Assert::true(str_contains($out, '%brand_name_ru%') && str_contains($out, '%brand_name_en%'));
    }

    public function testNoArticleReturnsEmpty(): void
    {
        Assert::same('', (new ContentCleaner())->clean('<html><body><p>нет заголовка</p></body></html>'));
    }
}

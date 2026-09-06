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
        Assert::same('/', $c->mapLink('https://%domain_name%/home'));
        Assert::same('/', $c->mapLink('/'));
        Assert::same('/vhod', $c->mapLink('https://%domain_name%/vhod'));
        Assert::same('/', $c->mapLink('/nechto-neponyatnoe'), 'неизвестное → /');
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

    public function testMultiWordBrandReplacedWholeNotJustFirstWord(): void
    {
        // Составной бренд «Вулкан Вегас» должен уйти в переменную целиком, а не «%brand% Вегас»
        // (короткий префикс «Вулкан» не должен срабатывать раньше длинного «Вулкан Вегас»).
        $html = '<h1>Обзор</h1><p>Играть в Вулкан Вегас и в Мани Икс каждый день.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ContentCleaner::autoOptions($html, 'cryptoboss.com'));
        Assert::false(stripos($out, 'вегас') !== false, 'после замены «Вегас» не остаётся хвостом');
        Assert::false(stripos($out, 'вулкан') !== false, '«Вулкан» заменён');
        Assert::false(stripos($out, 'икс') !== false, '«Мани Икс» заменён целиком');
    }

    public function testDomainReplacementEatsSubdomain(): void
    {
        // Сайт собран по регистрируемому домену, но в тексте бренд-поддомен: заменяем ВЕСЬ хост,
        // а не только «casinozsd.buzz», иначе остаётся «kush.%domain_name%».
        $html = '<h1>Обзор</h1><p>Играйте на kush.casinozsd.buzz и на casinozsd.buzz, зеркало www.casinozsd.buzz.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ['domain' => 'casinozsd.buzz', 'hosts' => ['casinozsd.buzz']]);
        Assert::false(str_contains($out, 'kush.'), 'поддомен не остаётся хвостом перед %domain_name%');
        Assert::false(stripos($out, 'casinozsd') !== false, 'домен и его поддомены заменены');
    }

    public function testStripsCtaAndUrgencyWidgets(): void
    {
        // Кнопки-призывы и «счётчики срочности» (фейковый джекпот/таймер) — не тело статьи;
        // из-за них оставался артефакт вроде «spot-cta-number 12345».
        $html = '<h1>Обзор</h1><p>Тело статьи.</p>'
            . '<div class="spot-cta-number">12345</div>'
            . '<div class="cta-block"><span class="cta-title">Играть</span></div>'
            . '<div class="countdown">00:59</div><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html);
        Assert::false(str_contains($out, '12345'), 'число из cta-блока удалено');
        Assert::false(str_contains($out, 'cta-block'), 'cta-блок удалён');
        Assert::false(str_contains($out, '00:59'), 'таймер удалён');
        Assert::true(str_contains($out, 'Тело статьи'), 'текст статьи остался');
    }

    public function testSpacedEnglishBrandReplaced(): void
    {
        // Слитная метка бренда «cryptoboss» должна ловить и раздельное написание в тексте
        // («Crypto Boss», «Crypto-Boss»), а не только слитное.
        $html = '<h1>Обзор</h1><p>Официальный сайт Crypto Boss, вход cryptoboss, зеркало Crypto-Boss.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ['brand_en' => 'cryptoboss']);
        Assert::false(stripos($out, 'crypto') !== false, 'все написания бренда (слитно, с пробелом, с дефисом) заменены');
        Assert::true(str_contains($out, '%brand_name_en%'), 'английский бренд подставлен');

        // «Money X» (второе слово — одна заглавная буква) тоже ловится.
        $mx = (new ContentCleaner())->clean('<h1>Обзор</h1><p>Играть в Money X сегодня.</p><h3>Популярные запросы</h3>', ['brand_en' => 'moneyx']);
        Assert::true(str_contains($mx, '%brand_name_en%') && stripos($mx, 'money') === false, '«Money X» заменён');
    }

    public function testSpacedBrandDoesNotTouchLowercasePhrase(): void
    {
        // Бренд goodwin НЕ должен превратить обычную фразу «a good win» в переменную — раздельное
        // написание ловится только когда каждое слово с заглавной (имя собственное).
        $html = '<h1>Обзор</h1><p>Это был a good win для игрока. Сайт Goodwin топ.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ['brand_en' => 'goodwin']);
        Assert::true(str_contains($out, 'good win'), 'обычная фраза «good win» не тронута');
        Assert::true(str_contains($out, '%brand_name_en%'), 'слитный «Goodwin» заменён');
    }

    public function testRemovesInlineStylesEmptyWrappersAndBreakRuns(): void
    {
        // После удаления картинок/виджетов остаются пустые обёртки и инлайновые стили — они дают большие
        // промежутки в статье. В эталонных шаблонах ни того, ни другого нет.
        $html = '<h1>Обзор</h1>'
            . '<div class="row" style="margin-top:80px"><div class="col"><img src="/x.png"></div></div>'
            . '<p style="padding:40px 0">Первый абзац.</p>'
            . '<p>&nbsp;</p><div><span></span></div>'
            . '<p>Второй<br><br><br>абзац.<br></p>'
            . '<table><tr><td></td><td>ячейка</td></tr></table>'
            . '<h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html);
        Assert::false(str_contains($out, 'style='), 'инлайновые стили удалены');
        Assert::false(str_contains($out, 'class="row"'), 'пустая обёртка (после удаления картинки) удалена');
        Assert::false(preg_match('~<p>\s*(?:&nbsp;)?\s*</p>~u', $out) === 1, 'пустой абзац удалён');
        Assert::false(str_contains($out, '<span></span>'), 'пустой span удалён');
        Assert::same(0, preg_match_all('~<br\s*/?>~', $out), '<br> сняты совсем (шаг 3), слова не слиплись');
        Assert::true(str_contains($out, 'Второй') && str_contains($out, 'абзац.') && !str_contains($out, 'Второйабзац'), 'на месте <br> остался разделитель');
        Assert::true(str_contains($out, 'Первый абзац') && str_contains($out, 'Второй'), 'текст на месте');
        Assert::true(str_contains($out, '<td></td>'), 'пустая ячейка таблицы сохранена (структура таблицы не трогается)');
    }

    public function testOwnRussianBrandMatchesDeclinedForms(): void
    {
        // Свой бренд в падежах («Криптобосса», «Криптобоссе», «Криптобоссом») тоже уходит в переменную;
        // у чужих (известных) брендов склонение не включаем, чтобы «куш» не съел «кушать».
        $html = '<h1>Обзор</h1><p>Играть в Криптобосс. Бонусы Криптобосса, зеркало Криптобоссе, вход в Криптобоссом. Я хочу кушать.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ['brand_ru' => 'криптобосс', 'extra_brands' => ['куш']]);
        Assert::false(stripos($out, 'криптобосс') !== false, 'все падежные формы своего бренда заменены');
        Assert::true(str_contains($out, 'кушать'), 'слово «кушать» не тронуто (чужой бренд «куш» без склонения)');

        // Составной бренд склоняется по обоим словам: «в Вулкане Вегасе».
        $two = (new ContentCleaner())->clean('<h1>x</h1><p>В Вулкане Вегасе весело.</p><h3>Популярные запросы</h3>', ['brand_ru' => 'вулкан вегас']);
        Assert::false(stripos($two, 'вулкан') !== false || stripos($two, 'вегас') !== false, 'склонённый двусловный бренд заменён целиком');
    }

    public function testOrderedPipelineRules3To8(): void
    {
        // Правила 3–8 в порядке мануала: служебные теги снесены, контейнеры развёрнуты, em/i → текст,
        // b → strong, h1 → h2, h4–h6 → h3, атрибуты сняты (кроме href), /main → /, внешние ссылки → текст.
        $html = '<h1>Заголовок</h1>'
            . '<meta name="x" content="y"><link rel="canonical" href="https://%domain_name%/">'
            . '<section class="c" id="s"><div data-x="1"><p style="color:red" class="p">Абзац <span class="s">со <i>курсивом</i> и <b>жирным</b></span>.<br>Дальше</p></div></section><hr>'
            . '<h1>Второй h1</h1><h4>Мелкий</h4><h6>Совсем мелкий</h6>'
            . '<table><caption>Подпись</caption><thead><tr><th>А</th></tr></thead><tbody><tr><td>Б</td></tr></tbody></table>'
            . '<p><a href="/main" title="t">Главная</a> <a href="https://vk.com/x" target="_blank">ВК</a> <a href="#top">Наверх</a> <a href="mailto:a@b.c">Почта</a> <a href="/bonus">Бонус</a></p>'
            . '<h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html);
        // 3. служебное
        foreach (['<meta', '<link', '<br', '<hr', '<caption', 'Подпись'] as $bad) {
            Assert::false(str_contains($out, $bad), "служебное снесено: $bad");
        }
        // 4. контейнеры развёрнуты, содержимое на месте
        foreach (['<section', '<div', '<span', '<thead', '<tbody'] as $bad) {
            Assert::false(str_contains($out, $bad), "контейнер развёрнут: $bad");
        }
        Assert::true(str_contains($out, 'со курсивом и'), 'содержимое контейнеров осталось');
        // 5. оформление
        Assert::false(str_contains($out, '<i>') || str_contains($out, '<em>') || str_contains($out, '<b>'), 'i/em сняты, b → strong');
        Assert::true(str_contains($out, '<strong>жирным</strong>'));
        // 6. заголовки
        Assert::false(str_contains($out, '<h1') || str_contains($out, '<h4') || str_contains($out, '<h6'));
        Assert::true(str_contains($out, '<h2>Второй h1</h2>') && str_contains($out, '<h3>Мелкий</h3>') && str_contains($out, '<h3>Совсем мелкий</h3>'));
        // 7. атрибуты
        Assert::false(preg_match('~<(?!a\b)[a-z0-9]+\s+[a-z-]+=~i', $out) === 1, 'атрибуты сняты со всех тегов, кроме <a>');
        Assert::false(str_contains($out, 'title=') || str_contains($out, 'target='), 'у <a> остался только href');
        // 8. ссылки
        Assert::true(str_contains($out, '<a href="/">Главная</a>'), '/main → /');
        Assert::true(str_contains($out, '<a href="/app">Бонус</a>'), 'внутренняя ссылка приведена к пути');
        Assert::true(str_contains($out, 'ВК') && !str_contains($out, 'vk.com'), 'внешняя ссылка развёрнута в текст');
        Assert::true(str_contains($out, 'Наверх') && str_contains($out, 'Почта') && !str_contains($out, 'mailto') && !str_contains($out, '#top'), 'якорь и mailto развёрнуты в текст');
        // таблица без thead/tbody/caption, но с ячейками
        Assert::true(str_contains($out, '<table>') && str_contains($out, '<th>А</th>') && str_contains($out, '<td>Б</td>'), 'таблица цела');
    }

    public function testFaqIsSecondStreamAndBrandSubstitutedInIt(): void
    {
        // FAQ лежит ПОСЛЕ «Популярных запросов» (вне среза тела) — его надо вынуть вторым потоком и прогнать
        // подстановку и по нему: иначе имена бренда в FAQ уцелевают.
        $html = '<h1>Обзор</h1><p>Криптобосс — казино.</p><h3>Популярные запросы</h3><ul><li>x</li></ul>'
            . '<section class="faq"><h2>Вопросы</h2><details><summary>Как войти в Криптобосс?</summary><p>Через сайт Криптобосса.</p></details></section>';
        $out = (new ContentCleaner())->clean($html, ['brand_ru' => 'криптобосс']);
        Assert::true(str_contains($out, '<details>') && str_contains($out, '<summary>'), 'FAQ вынут и приклеен к телу');
        Assert::false(stripos($out, 'криптобосс') !== false, 'бренд заменён и внутри FAQ (оба потока)');
        Assert::same(3, substr_count($out, '%brand_name_ru%'), 'все три упоминания (тело + вопрос + ответ) заменены');
        Assert::false(str_contains($out, 'Популярные'), 'блок «Популярные запросы» по-прежнему отрезан');

        // FAQ только в JSON-LD (HTML-блока нет) — рендерится из разметки и тоже проходит подстановку.
        $ld = '<h1>Обзор</h1><p>Текст.</p><script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"Есть ли бонус в Криптобосс?","acceptedAnswer":{"@type":"Answer","text":"Да, Криптобосс даёт бонус."}}]}</script>';
        $o2 = (new ContentCleaner())->clean($ld, ['brand_ru' => 'криптобосс']);
        Assert::true(str_contains($o2, '<h2>Вопросы и ответы</h2>') && str_contains($o2, '<h3>'), 'FAQ из JSON-LD добавлен');
        Assert::false(stripos($o2, 'криптобосс') !== false, 'бренд заменён и в FAQ из JSON-LD');
        Assert::false(str_contains($o2, '<script'), 'сам JSON-LD в статью не попал');
    }

    public function testBrandSplitAcrossSpansIsCaughtAfterUnwrap(): void
    {
        // Бренд, разбитый на <span>ы, склеивается после развёртки — повторный проход подстановки его ловит.
        $html = '<h1>x</h1><p>Играть в <span>Крипто</span><span>босс</span> выгодно.</p><h3>Популярные запросы</h3>';
        $out = (new ContentCleaner())->clean($html, ['brand_ru' => 'криптобосс']);
        Assert::true(str_contains($out, '%brand_name_ru%') && stripos($out, 'криптобосс') === false, 'разбитый бренд заменён');
    }

    public function testNoArticleReturnsEmpty(): void
    {
        Assert::same('', (new ContentCleaner())->clean('<html><body><p>нет заголовка</p></body></html>'));
    }
}

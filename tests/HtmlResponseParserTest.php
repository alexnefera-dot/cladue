<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Live\HtmlResponseParser;
use YandexSites\Search\ApiException;

final class HtmlResponseParserTest
{
    private function fixture(string $name): string
    {
        return (string) file_get_contents(TESTS_ROOT . '/fixtures/' . $name);
    }

    public function testParsesOrganicResultsAndSkipsAds(): void
    {
        $parser = new HtmlResponseParser();
        $html = $this->fixture('serp.html');
        Assert::same(HtmlResponseParser::KIND_SERP, $parser->classify($html));

        $page = $parser->parse($html, 'окна', 0);
        Assert::same(6, $page->groups, 'все элементы serp-item, включая рекламу и блоки без ссылок');
        Assert::same(4, count($page->results), 'реклама и блок «люди ищут» пропущены');
        Assert::same([1, 2, 3, 4], array_map(static fn ($r) => $r->position, $page->results));
        Assert::same(true, $page->hasMore);
        Assert::same(24000000, $page->found);

        $first = $page->results[0];
        Assert::same('https://okna-moskva.ru/plastikovye-okna/', $first->url);
        Assert::same('okna-moskva.ru', $first->host);
        Assert::same('Пластиковые окна в Москве — купить недорого', $first->title, 'выделение <b> склеивается в текст');
        Assert::same('Производство и установка окон ПВХ. Телефон +7 (495) 123-45-67. Замер бесплатно.', $first->snippet);
        Assert::same('окна', $first->query);

        Assert::same('yandex.ru', $page->results[1]->host, 'колдунщик карт остаётся результатом (отсеивается фильтрами)');
        Assert::same('https://yandex.ru/maps/213/moscow/search/окна/', $page->results[1]->url);
        Assert::same('www.avito.ru', $page->results[2]->host);
        Assert::same('Окна — купить в Москве на Avito', $page->results[2]->title);
        Assert::same('https://xn--80aswg.xn--p1ai/okna/', $page->results[3]->url, 'ссылка через clck/jsredir разворачивается в целевой адрес');
        Assert::same('Сайт.рф — окна', $page->results[3]->title);
        Assert::same('Кириллический домен', $page->results[3]->snippet);
    }

    public function testPositionOffsetAndLastPage(): void
    {
        $parser = new HtmlResponseParser();
        $html = $this->fixture('serp.html');
        $page = $parser->parse($html, 'окна', 1, 10);
        Assert::same([11, 12, 13, 14], array_map(static fn ($r) => $r->position, $page->results));

        $noNext = str_replace(['Pager-Item_type_next', '>дальше<'], ['Pager-Item_type_prev', '>назад<'], $html);
        Assert::same(false, $parser->parse($noNext, 'окна', 1)->hasMore, 'пагинатор без ссылки «дальше»');

        $noPager = (string) preg_replace('~<div class="Pager pager">.*?</div>~s', '', $html);
        Assert::same(false, $parser->parse($noPager, 'окна', 0)->hasMore, 'нет пагинатора и меньше 10 результатов');
    }

    public function testClassifiesCaptchaEmptyAndUnknownPages(): void
    {
        $parser = new HtmlResponseParser();
        Assert::same(HtmlResponseParser::KIND_CAPTCHA, $parser->classify($this->fixture('serp_captcha.html')));
        Assert::same(HtmlResponseParser::KIND_CAPTCHA, $parser->classify('<html></html>', 'https://yandex.ru/showcaptcha?retpath=x'));
        Assert::same(HtmlResponseParser::KIND_EMPTY, $parser->classify($this->fixture('serp_empty.html')));
        Assert::same(HtmlResponseParser::KIND_UNKNOWN, $parser->classify('<html><body><p>hello</p></body></html>'));
        Assert::same(HtmlResponseParser::KIND_BLOCKED, $parser->classify('<html><body>denied</body></html>', '', 403));
        Assert::same(HtmlResponseParser::KIND_BLOCKED, $parser->classify(''));
        Assert::same(HtmlResponseParser::KIND_SERP, $parser->classify($this->fixture('serp.html') . '<!-- SmartCaptcha script mention -->'), 'упоминание капчи в коде выдачи не считается капчей');

        $empty = $parser->parse($this->fixture('serp_empty.html'), 'q', 0);
        Assert::same([], $empty->results);
        Assert::same(false, $empty->hasMore);

        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, fn () => $parser->parse($this->fixture('serp_captcha.html'), 'q', 0), 'капч');
        Assert::true($e->isRetryable());
        Assert::throws(ApiException::class, static fn () => $parser->parse('<html><body>hello</body></html>', 'q', 0), 'распознать');
    }
}

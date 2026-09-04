<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Search\ApiException;
use YandexSites\Search\XmlResponseParser;

final class XmlResponseParserTest
{
    public function testParsesDocumentsWithHighlightsAndGroups(): void
    {
        $xml = (string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml');
        $page = (new XmlResponseParser())->parse($xml, 'окна', 0);

        Assert::same(1234567, $page->found);
        Assert::same(3, $page->groups);
        Assert::same(4, count($page->results));

        $first = $page->results[0];
        Assert::same(1, $first->position);
        Assert::same('https://okna-moskva.ru/plastikovye-okna/', $first->url);
        Assert::same('okna-moskva.ru', $first->host);
        Assert::same('Пластиковые окна в Москве — купить недорого', $first->title, 'текст hlword сохраняется');
        Assert::same('Производство и установка окон ПВХ', $first->headline);
        Assert::same('Купить пластиковые окна от производителя. Телефон +7 (495) 123-45-67. … Замер бесплатно, монтаж за 1 день.', $first->snippet);
        Assert::same('20250815T101500', $first->modtime);
        Assert::same('окна', $first->query);

        Assert::same([1, 2, 3, 4], array_map(static fn ($r) => $r->position, $page->results));
        Assert::same('www.avito.ru', $page->results[1]->host);
        Assert::same('www.avito.ru', $page->results[2]->host);
        Assert::same('xn--80aswg.xn--p1ai', $page->results[3]->host, 'домен берётся из categ, если нет <domain>');
    }

    public function testNoResultsIsEmptyPage(): void
    {
        $xml = (string) file_get_contents(TESTS_ROOT . '/fixtures/response_error15.xml');
        $parser = new XmlResponseParser();
        $page = $parser->parse($xml, 'q', 0);
        Assert::same([], $page->results);
        Assert::same(0, $page->groups);
        Assert::same(['code' => 15, 'message' => 'Искомая комбинация слов нигде не встречается'], $parser->detectError($xml));
    }

    public function testErrorCodesBecomeExceptions(): void
    {
        $xml = (string) file_get_contents(TESTS_ROOT . '/fixtures/response_error55.xml');
        $parser = new XmlResponseParser();
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $parser->parse($xml, 'q', 0), '55');
        Assert::same(55, $e->getYandexCode());
        Assert::true($e->isRetryable());
        Assert::false($e->isFatal());

        $fatal = str_replace('code="55"', 'code="32"', $xml);
        /** @var ApiException $e */
        $e = Assert::throws(ApiException::class, static fn () => $parser->parse($fatal, 'q', 0));
        Assert::true($e->isFatal());
        Assert::null($parser->detectError((string) file_get_contents(TESTS_ROOT . '/fixtures/response.xml')));
    }

    public function testMalformedResponses(): void
    {
        $parser = new XmlResponseParser();
        Assert::throws(ApiException::class, static fn () => $parser->parse('<html>captcha</html>', 'q', 0), 'yandexsearch');
        Assert::throws(ApiException::class, static fn () => $parser->parse('not xml at all <', 'q', 0), 'разобрать');
        Assert::throws(ApiException::class, static fn () => $parser->parse('', 'q', 0), 'Пустой');
    }
}

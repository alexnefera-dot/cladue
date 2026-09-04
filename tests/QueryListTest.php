<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\QueryList;

final class QueryListTest
{
    public function testFromLines(): void
    {
        $queries = QueryList::fromLines(["\xEF\xBB\xBF# комментарий", '', '  окна   пвх ', 'Окна ПВХ', 'двери', '# ещё', 'двери ']);
        Assert::same(['окна пвх', 'двери'], $queries);
    }

    public function testFromFileAndMerge(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-queries-' . uniqid() . '.txt';
        file_put_contents($file, "a\nb\n\nc\n");
        Assert::same(['a', 'b', 'c'], QueryList::fromFile($file));
        Assert::same(['a', 'b', 'c', 'd'], QueryList::merge(QueryList::fromFile($file), ['B', 'd']));
        unlink($file);
        Assert::throws(\RuntimeException::class, static fn () => QueryList::fromFile($file), 'не найден');
    }
}

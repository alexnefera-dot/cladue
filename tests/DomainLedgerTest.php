<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\DomainLedger;

final class DomainLedgerTest
{
    public function testTracksAndPersistsDomains(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-ledger-' . uniqid() . '.txt';

        $ledger = new DomainLedger($file);
        Assert::same(0, $ledger->count());
        Assert::false($ledger->has('example.ru'));

        Assert::same(2, $ledger->add(['Example.ru', 'b.ru', 'example.ru ', 'b.ru']), 'дубли и регистр не считаются новыми');
        Assert::same(2, $ledger->count());
        Assert::true($ledger->has('example.ru'));
        Assert::true($ledger->has('EXAMPLE.RU'), 'проверка без учёта регистра');

        // Новый экземпляр читает сохранённое из файла
        $reloaded = new DomainLedger($file);
        Assert::same(2, $reloaded->count());
        Assert::true($reloaded->has('b.ru'));
        Assert::same(1, $reloaded->add(['b.ru', 'c.ru']), 'только c.ru новый');
        Assert::same(3, $reloaded->count());

        $reloaded->clear();
        Assert::same(0, $reloaded->count());
        Assert::same('', trim((string) file_get_contents($file)));

        unlink($file);
    }
}

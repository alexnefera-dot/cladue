<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Cli\Application;
use YandexSites\Cli\UsageException;

final class ApplicationTest
{
    public function testParseArgs(): void
    {
        $app = new Application();
        $opts = $app->parseArgs(['--queries=a.txt', '--query', 'окна', '-q', 'двери', 'b.txt', '--pages=2', '--no-cache', '-v', '--out', 'res', '--', '--weird.txt']);
        Assert::same(['a.txt'], $opts['queries']);
        Assert::same(['окна', 'двери'], $opts['query']);
        Assert::same(['b.txt', '--weird.txt'], $opts['_positional']);
        Assert::same('2', $opts['pages']);
        Assert::same(true, $opts['no-cache']);
        Assert::same(true, $opts['verbose']);
        Assert::same('res', $opts['out']);
    }

    public function testParseArgsErrors(): void
    {
        $app = new Application();
        Assert::throws(UsageException::class, static fn () => $app->parseArgs(['--unknown']), 'неизвестная опция');
        Assert::throws(UsageException::class, static fn () => $app->parseArgs(['-z']), 'неизвестная опция');
        Assert::throws(UsageException::class, static fn () => $app->parseArgs(['--pages']), 'требует значение');
        Assert::throws(UsageException::class, static fn () => $app->parseArgs(['--verbose=1']), 'не принимает значение');
    }

    public function testUsageText(): void
    {
        $usage = (new Application())->usage();
        Assert::contains('--queries=FILE', $usage);
        Assert::contains('--check-sites', $usage);
        Assert::contains('YANDEX_FOLDER_ID', $usage);
    }
}

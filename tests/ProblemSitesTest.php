<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\ProblemSites;

/**
 * «Проблемные» = сайты, которые не удалось ПОЛУЧИТЬ, с привязкой причины к стадии. Одностраничник и
 * пропуск целевой страницы проблемой не считаются — это прямое требование пользователя.
 */
final class ProblemSitesTest
{
    /** @param array<string,mixed> $row */
    private function codes(array $row): array
    {
        return ProblemSites::codes($row);
    }

    public function testOwnAndCleanSitesAreNotProblems(): void
    {
        Assert::same([], $this->codes(['own' => true, 'pages_ok' => 0, 'pages_total' => 0]), 'наш шаблон — не проблема');
        // Одностраничник после выгрузки: открылась только главная, больше страниц нет — норма.
        Assert::same([], $this->codes(['downloaded' => true, 'pages_ok' => 1, 'pages_total' => 1, 'retryable' => false]), 'одностраничник — не проблема');
        // Все страницы открылись.
        Assert::same([], $this->codes(['downloaded' => true, 'pages_ok' => 9, 'pages_total' => 9]), 'полностью выгруженный — не проблема');
        // Превью открылось.
        Assert::same([], $this->codes(['downloaded' => false, 'pages_ok' => 1, 'pages_total' => 1]), 'превью получилось — не проблема');
    }

    public function testMissingKeyPageIsNotAProblem(): void
    {
        // Нет целевой страницы (регистрация/вход/…), но всё, что есть, скачалось — это пропуск, не сбой.
        $row = ['downloaded' => true, 'pages_ok' => 7, 'pages_total' => 7, 'key_missing' => ['registracia', 'vhod'], 'retryable' => false];
        Assert::same([], $this->codes($row), 'пропуск целевой страницы — не проблема');
    }

    public function testNotFoundAndDuplicatesAreNotProblems(): void
    {
        // Часть «страниц» — это 404 и дубликаты (retryable=false): не сбой загрузки, у сайта их просто нет.
        $row = ['downloaded' => true, 'pages_ok' => 5, 'pages_total' => 9, 'retryable' => false, 'pages_404' => 4];
        Assert::same([], $this->codes($row), '404 и дубликаты проблемой не считаем');
    }

    public function testCollectStageProblems(): void
    {
        // Пытались открыть главную на превью, но не вышло.
        Assert::same(['no_preview'], $this->codes(['downloaded' => false, 'pages_ok' => 0, 'pages_total' => 1, 'page_error' => 'таймаут']), 'не открылся на превью');
        Assert::same(['no_preview'], $this->codes(['downloaded' => false, 'pages_ok' => 0, 'pages_total' => 0, 'page_error' => 'нет соединения']), 'ни одного визита с ошибкой');
        // Витрина офферов — отдельный диагноз, не дублируется как «не открылся».
        Assert::same(['offer_wall'], $this->codes(['downloaded' => false, 'offer_wall' => true, 'pages_ok' => 0, 'pages_total' => 1]), 'подборка офферов');
        Assert::same('collect', ProblemSites::stageOf('no_preview'));
        Assert::same('collect', ProblemSites::stageOf('offer_wall'));
    }

    public function testDownloadStageProblems(): void
    {
        Assert::same(['no_pages'], $this->codes(['downloaded' => true, 'pages_ok' => 0, 'pages_total' => 6, 'retryable' => true]), 'ни одной страницы не выгрузилось');
        Assert::same(['pages_failed'], $this->codes(['downloaded' => true, 'pages_ok' => 3, 'pages_total' => 6, 'retryable' => true]), 'часть упала и её можно добрать');
        Assert::same(['missing_files'], $this->codes(['downloaded' => true, 'pages_ok' => 9, 'pages_total' => 9, 'pages_missing' => 2, 'retryable' => true]), 'файлы пропали с диска');
        // Не открылось ничего И файлы пропали — обе причины.
        $both = $this->codes(['downloaded' => true, 'pages_ok' => 0, 'pages_total' => 4, 'pages_missing' => 1, 'retryable' => true]);
        Assert::true(in_array('no_pages', $both, true) && in_array('missing_files', $both, true), 'сразу две причины по выгрузке');
        Assert::same('download', ProblemSites::stageOf('no_pages'));
        Assert::same('download', ProblemSites::stageOf('pages_failed'));
    }

    public function testHistogramSectionsByDownloadedFlag(): void
    {
        $rows = [
            ['host' => 'a', 'downloaded' => false, 'pages_ok' => 0, 'pages_total' => 1, 'page_error' => 'err'], // no_preview
            ['host' => 'b', 'downloaded' => false, 'offer_wall' => true, 'pages_ok' => 0, 'pages_total' => 1], // offer_wall (по сбору)
            ['host' => 'c', 'downloaded' => true, 'offer_wall' => true, 'pages_ok' => 0, 'pages_total' => 3], // offer_wall (по выгрузке)
            ['host' => 'd', 'downloaded' => true, 'pages_ok' => 2, 'pages_total' => 5, 'retryable' => true], // pages_failed
            ['host' => 'e', 'downloaded' => true, 'pages_ok' => 9, 'pages_total' => 9], // чистый — не в счёт
        ];
        $h = ProblemSites::histogram($rows);
        Assert::same(4, $h['sites'], 'проблемных сайтов — четыре');
        Assert::same(1, $h['collect']['no_preview'] ?? 0);
        Assert::same(1, $h['collect']['offer_wall'] ?? 0);
        Assert::same(1, $h['download']['offer_wall'] ?? 0, 'выгруженная витрина офферов идёт «по выгрузке»');
        Assert::same(1, $h['download']['pages_failed'] ?? 0);
        $text = ProblemSites::histogramText($h);
        Assert::contains('по сбору', $text);
        Assert::contains('по выгрузке', $text);
        Assert::contains('часть страниц не скачалась', $text);
    }
}

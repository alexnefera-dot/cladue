<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * «Проблемные» сайты — те, которые НЕ УДАЛОСЬ ПОЛУЧИТЬ, а не те, у которых чего-то нет.
 *
 * Причина привязана к СТАДИИ, потому что после одного сбора со скриншотами про сайт ещё почти
 * ничего не известно — открылась только главная. Поэтому:
 *   • по сбору (превью): сайт не открылся вовсе, либо вместо сайта показана витрина чужих офферов;
 *   • по выгрузке (обход всех страниц): ни одна страница не выгрузилась, часть страниц упала так,
 *     что докачка может их добрать, или файл открытой страницы пропал с диска.
 *
 * Что проблемой НЕ считается (по прямой просьбе пользователя):
 *   • одностраничник — если после выгрузки открылась только главная и больше страниц у сайта нет;
 *   • пропуск целевой страницы (регистрация/вход/зеркало…): её просто нет, это не сбой загрузки;
 *   • 404 и дубликаты: это «у сайта нет такой страницы», а не «мы не смогли её взять» (для 404 в
 *     таблице есть своя кнопка «Убрать с 404 > N»).
 */
final class ProblemSites
{
    /** Причины, которые видны уже после сбора (по превью-скриншоту главной). */
    public const COLLECT = ['no_preview', 'offer_wall'];

    /** Причины, которые видны только после выгрузки страниц (обхода сайта). */
    public const DOWNLOAD = ['no_pages', 'pages_failed', 'missing_files'];

    /** @var array<string, string> код → русская подпись */
    public const LABELS = [
        'no_preview' => 'не открылся (без превью)',
        'offer_wall' => 'подборка офферов вместо сайта',
        'no_pages' => 'ни одной страницы не выгрузилось',
        'pages_failed' => 'часть страниц не скачалась',
        'missing_files' => 'нет файла на диске',
    ];

    public static function label(string $code): string
    {
        return self::LABELS[$code] ?? $code;
    }

    /**
     * Стадия причины: 'collect' (по сбору) или 'download' (по выгрузке). Для секций во вкладке место
     * сайта определяется его флагом «выгружен», а не стадией причины (offer_wall бывает на обеих).
     */
    public static function stageOf(string $code): string
    {
        return in_array($code, self::DOWNLOAD, true) ? 'download' : 'collect';
    }

    /**
     * Коды проблем одной строки таблицы (SiteRows::preview()). Пустой список — сайт не проблемный.
     *
     * @param array<string, mixed> $row
     * @return list<string>
     */
    public static function codes(array $row): array
    {
        if (!empty($row['own'])) {
            return []; // наш шаблон — вообще не выгружаем, это не проблема
        }
        // Витрина чужих офферов — отдельный, самый показательный диагноз: настоящий сайт спрятан.
        // Показываем именно так, не дублируя его как «не открылся».
        if (!empty($row['offer_wall'])) {
            return ['offer_wall'];
        }

        $downloaded = !empty($row['downloaded']);
        $ok = (int) ($row['pages_ok'] ?? 0);
        $total = (int) ($row['pages_total'] ?? 0);
        $error = (string) ($row['page_error'] ?? '');
        $missing = (int) ($row['pages_missing'] ?? 0);
        $retryable = !empty($row['retryable']);

        if (!$downloaded) {
            // По сбору: пытались открыть главную (был визит), но успеха нет.
            $triedButFailed = $total > 0 ? $ok === 0 : $error !== '';

            return $triedButFailed ? ['no_preview'] : [];
        }

        // По выгрузке.
        $out = [];
        if ($ok === 0 && ($total > 0 || $error !== '')) {
            $out[] = 'no_pages';
        } elseif ($ok > 0 && $ok < $total && $retryable) {
            // Часть страниц не открылась И это можно добрать (таймаут/блок/файл пропал) — не дубликаты
            // и не 404, которые retryable=false и проблемой не считаются.
            $out[] = 'pages_failed';
        }
        if ($missing > 0) {
            $out[] = 'missing_files';
        }

        return array_values(array_unique($out));
    }

    /**
     * Сколько проблемных сайтов по стадиям и причинам: сайт считается один раз в каждой своей причине.
     *
     * @param list<array<string, mixed>> $rows строки SiteRows::preview()
     * @return array{collect: array<string,int>, download: array<string,int>, sites: int}
     */
    public static function histogram(array $rows): array
    {
        $out = ['collect' => [], 'download' => [], 'sites' => 0];
        foreach ($rows as $row) {
            $codes = self::codes($row);
            if ($codes === []) {
                continue;
            }
            $out['sites']++;
            // Секция — по тому, дошёл ли сайт до выгрузки, а не по стадии кода: не выгруженный сайт с
            // офферной витриной должен стоять «по сбору», выгруженный — «по выгрузке».
            $section = !empty($row['downloaded']) ? 'download' : 'collect';
            foreach ($codes as $code) {
                $out[$section][$code] = ($out[$section][$code] ?? 0) + 1;
            }
        }

        return $out;
    }

    /**
     * Гистограмма текстом: «по сбору: не открылся (без превью) — 12, подборка офферов — 3; по выгрузке:
     * часть страниц не скачалась — 40». Пустая строка, если проблемных нет.
     *
     * @param array{collect: array<string,int>, download: array<string,int>, sites?: int} $hist
     */
    public static function histogramText(array $hist): string
    {
        $parts = [];
        foreach (['collect' => 'по сбору', 'download' => 'по выгрузке'] as $section => $sectionLabel) {
            $codes = $hist[$section] ?? [];
            if ($codes === []) {
                continue;
            }
            arsort($codes);
            $inner = [];
            foreach ($codes as $code => $count) {
                $inner[] = self::label((string) $code) . ' — ' . $count;
            }
            $parts[] = $sectionLabel . ': ' . implode(', ', $inner);
        }

        return implode('; ', $parts);
    }
}

<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * СВЕЖЕСТЬ документа в выдаче — та самая метка «добавлен 8 ч назад» рядом с результатом.
 *
 * Берётся из двух мест, и оба приводятся к одному виду — метке времени:
 *  - Yandex.XML (источники api и xmlstock) отдаёт поле <modtime> в своём формате 20250815T101500;
 *    оно у нас РАЗБИРАЛОСЬ с самого начала, но терялось дальше по пути и никуда не показывалось;
 *  - живая выдача (источник live) показывает ОТНОСИТЕЛЬНУЮ подпись («8 ч назад», «вчера»), и её
 *    нужно превратить в абсолютное время ПРЯМО ПРИ РАЗБОРЕ: results.csv читают через дни, и «8 ч
 *    назад», сохранённое как текст, к тому моменту означало бы совсем другой момент.
 *
 * Зачем это в разборе выдачи: дор, которому сутки от роду и который уже в топ-3, — это главный
 * признак того, что ниша крутится быстро и место в ней покупается свежими запусками, а не возрастом.
 */
final class Freshness
{
    /** До скольких суток считаем документ свежим (подсветка «свежий» в разборе). */
    public const FRESH_DAYS = 2;

    /** Месяцы в родительном падеже и сокращениях — так их пишет и Яндекс, и русские даты вообще. */
    private const MONTHS = [
        'янв' => 1, 'фев' => 2, 'мар' => 3, 'апр' => 4, 'ма' => 5, 'июн' => 6,
        'июл' => 7, 'авг' => 8, 'сен' => 9, 'окт' => 10, 'ноя' => 11, 'дек' => 12,
    ];

    /**
     * Метка времени документа или null, если строку распознать не удалось.
     *
     * $now нужен для ОТНОСИТЕЛЬНЫХ подписей: «8 ч назад» имеет смысл только относительно момента,
     * когда выдача была получена, поэтому вызывающий передаёт своё «сейчас», а не берётся time().
     */
    public static function parse(string $raw, ?int $now = null): ?int
    {
        $raw = trim(mb_strtolower($raw));
        if ($raw === '') {
            return null;
        }
        $now ??= time();

        // Формат Яндекса: 20250815T101500 (без зоны — считаем UTC, для «сколько дней назад» хватает).
        if (preg_match('~^(\d{4})(\d{2})(\d{2})t(\d{2})(\d{2})(\d{2})$~', $raw, $m) === 1) {
            return self::stampOf((int) $m[1], (int) $m[2], (int) $m[3], (int) $m[4], (int) $m[5], (int) $m[6]);
        }
        // ISO и близкие к нему: 2025-08-15T10:15:00+03:00, 2025-08-15 10:15, 2025-08-15.
        if (preg_match('~^\d{4}-\d{2}-\d{2}([t ]\d{2}:\d{2}(:\d{2})?)?~', $raw) === 1) {
            $ts = strtotime($raw);

            return $ts === false ? null : $ts;
        }
        // «сегодня» / «вчера» — без времени, берём полдень, чтобы округление «сколько дней» не врало.
        if (str_starts_with($raw, 'сегодня')) {
            return $now;
        }
        if (str_starts_with($raw, 'вчера')) {
            return $now - 86400;
        }
        // Относительные подписи выдачи: «32 мин назад», «8 ч назад», «3 дня назад», «2 нед назад».
        // Порядок важен: более длинная основа идёт раньше короткой («минут» до «мин», «недел» до «нед»),
        // иначе «2 недели назад» разберётся как два дня. Границу слова (\b) здесь не ставим — она с
        // кириллицей не работает и как раз ломала склонения («недели», «часов»).
        if (preg_match('~^(\d+)\s*(секунд|сек|минут|мин|часов|часа|час|дней|дня|день|недел|нед|месяц|мес|год|лет|ч|дн|г)~u', $raw, $m) === 1) {
            $n = (int) $m[1];
            $unit = $m[2];
            $seconds = match (true) {
                str_starts_with($unit, 'сек') => $n,
                str_starts_with($unit, 'мин') => $n * 60,
                $unit === 'ч' || str_starts_with($unit, 'час') => $n * 3600,
                str_starts_with($unit, 'нед') => $n * 7 * 86400,
                str_starts_with($unit, 'мес') => $n * 30 * 86400,
                $unit === 'г' || str_starts_with($unit, 'год') || str_starts_with($unit, 'лет') => $n * 365 * 86400,
                default => $n * 86400, // дни
            };

            return $now - $seconds;
        }
        // Русская дата: «15 авг 2025», «15 августа» (год текущий).
        if (preg_match('~^(\d{1,2})\s+([а-яё]{3,})\.?(?:\s+(\d{4}))?~u', $raw, $m) === 1) {
            $month = self::month($m[2]);
            if ($month !== null) {
                $year = isset($m[3]) && $m[3] !== '' ? (int) $m[3] : (int) gmdate('Y', $now);

                return self::stampOf($year, $month, (int) $m[1], 12, 0, 0);
            }
        }

        return null;
    }

    /** Похожа ли короткая строка на подпись свежести — чтобы не разбирать весь текст сниппета. */
    public static function looksLikeLabel(string $text): bool
    {
        $text = trim(mb_strtolower($text));

        return $text !== '' && mb_strlen($text) <= 24 && self::parse($text, 1_000_000_000) !== null;
    }

    /** Метка времени в формате Яндекса (20250815T101500) — в нём свежесть и хранится у нас. */
    public static function stamp(int $timestamp): string
    {
        return gmdate('Ymd\THis', $timestamp);
    }

    /** Сколько полных суток прошло; null — времени нет. */
    public static function days(?int $timestamp, ?int $now = null): ?int
    {
        if ($timestamp === null) {
            return null;
        }

        return (int) floor(max(0, ($now ?? time()) - $timestamp) / 86400);
    }

    /** Подпись для человека: «8 ч назад», «вчера», «3 дн. назад», «15.08.2025». */
    public static function label(?int $timestamp, ?int $now = null): string
    {
        if ($timestamp === null) {
            return '';
        }
        $now ??= time();
        $diff = $now - $timestamp;
        if ($diff < 0) {
            return 'только что';
        }
        if ($diff < 60) {
            return 'только что';
        }
        if ($diff < 3600) {
            return (int) floor($diff / 60) . ' мин назад';
        }
        if ($diff < 86400) {
            return (int) floor($diff / 3600) . ' ч назад';
        }
        $days = (int) floor($diff / 86400);
        if ($days === 1) {
            return 'вчера';
        }
        if ($days <= 30) {
            return $days . ' дн. назад';
        }

        return gmdate('d.m.Y', $timestamp);
    }

    private static function month(string $word): ?int
    {
        foreach (self::MONTHS as $prefix => $number) {
            if (str_starts_with($word, $prefix)) {
                return $number;
            }
        }

        return null;
    }

    private static function stampOf(int $y, int $mo, int $d, int $h, int $mi, int $s): ?int
    {
        if ($mo < 1 || $mo > 12 || $d < 1 || $d > 31) {
            return null;
        }

        return gmmktime($h, $mi, $s, $mo, $d, $y) ?: null;
    }
}

<?php
declare(strict_types=1);

/**
 * Внутренняя уникальность: матрица схожести страниц по шинглам.
 * Шингл — последовательность из N нормализованных слов (канонизация Бродера).
 */
final class Similarity
{
    private const SHINGLE_SIZE = 3;

    /** @return array<int,int> набор хэшей шинглов */
    public static function shingles(string $text, int $size = self::SHINGLE_SIZE): array
    {
        preg_match_all('/[\p{L}\p{Nd}]+/u', mb_strtolower($text, 'UTF-8'), $m);
        $words = array_values(array_filter($m[0], fn($w) => !StopWords::is($w)));
        $set = [];
        $n = count($words);
        for ($i = 0; $i + $size <= $n; $i++) {
            $gram = implode(' ', array_slice($words, $i, $size));
            $set[crc32($gram)] = true;
        }
        return $set;
    }

    /** сходство Жаккара, % */
    public static function jaccard(array $a, array $b): float
    {
        if (!$a || !$b) { return 0.0; }
        $inter = count(array_intersect_key($a, $b));
        $union = count($a + $b);
        return $union ? round($inter / $union * 100, 0) : 0.0;
    }

    /**
     * Матрица схожести NxN по массиву текстов.
     * @param string[] $texts
     * @return array<int,array<int,int>>
     */
    public static function matrix(array $texts): array
    {
        $shingles = array_map(fn($t) => self::shingles($t), $texts);
        $n = count($texts);
        $m = [];
        for ($i = 0; $i < $n; $i++) {
            for ($j = 0; $j < $n; $j++) {
                $m[$i][$j] = ($i === $j) ? 100 : (int) self::jaccard($shingles[$i], $shingles[$j]);
            }
        }
        return $m;
    }
}

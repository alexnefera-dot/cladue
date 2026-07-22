<?php
declare(strict_types=1);

/**
 * Детерминированный ГПСЧ (seed -> одинаковый результат).
 * Не зависит от глобального состояния PHP: xorshift32 с seed из строки.
 *
 * Ключевой метод — tri(): асимметрично-треугольная выборка по тройке
 * [p10, median, p90]. Значения ложатся В коридор корпуса (не превышают p90,
 * не проваливаются ниже p10), сгущаясь у медианы. Это и есть требование
 * «воспроизвести, а не превзойти».
 */
final class Rng
{
    private int $state;

    public function __construct(string|int $seed)
    {
        $s = is_int($seed) ? $seed : crc32($seed);
        $s &= 0xFFFFFFFF;
        if ($s === 0) { $s = 0x9E3779B9; }
        $this->state = $s;
    }

    /** xorshift32 -> uint32 */
    private function next(): int
    {
        $x = $this->state;
        $x ^= ($x << 13) & 0xFFFFFFFF;
        $x ^= ($x >> 17);
        $x ^= ($x << 5) & 0xFFFFFFFF;
        $this->state = $x & 0xFFFFFFFF;
        return $this->state;
    }

    /** float в [0,1) */
    public function float(): float
    {
        return $this->next() / 4294967296.0;
    }

    /** float в [a,b) */
    public function range(float $a, float $b): float
    {
        return $a + ($b - $a) * $this->float();
    }

    /** целое в [min,max] включительно */
    public function int(int $min, int $max): int
    {
        if ($max <= $min) { return $min; }
        return $min + (int) floor($this->float() * ($max - $min + 1));
    }

    /** true с вероятностью p */
    public function chance(float $p): bool
    {
        return $this->float() < $p;
    }

    /**
     * Асимметрично-треугольная выборка по [min, mode, max] = [p10, median, p90].
     * Держит значение в [min,max], пик у mode.
     */
    public function tri(float $min, float $mode, float $max): float
    {
        if ($max <= $min) { return $mode; }
        $mode = max($min, min($max, $mode));
        $u = $this->float();
        $fc = ($mode - $min) / ($max - $min);
        if ($u < $fc) {
            return $min + sqrt($u * ($max - $min) * ($mode - $min));
        }
        return $max - sqrt((1 - $u) * ($max - $min) * ($max - $mode));
    }

    /** то же, но округляет до int */
    public function triInt(array $triple): int
    {
        [$min, $med, $max] = $triple;
        return (int) round($this->tri((float) $min, (float) $med, (float) $max));
    }

    /**
     * Треугольная выборка по ЗАДАННОЙ позиции u∈[0,1] (инверсная CDF), без розыгрыша.
     * Нужно, чтобы стиль-профиль генерации держал сайт «на одном уровне» коридора
     * (напр. плотность цифр) одинаково на всех 7 страницах.
     */
    public function triU(float $min, float $mode, float $max, float $u): float
    {
        if ($max <= $min) { return $mode; }
        $u = max(0.0, min(1.0, $u));
        $mode = max($min, min($max, $mode));
        $fc = ($mode - $min) / ($max - $min);
        if ($u < $fc) {
            return $min + sqrt($u * ($max - $min) * ($mode - $min));
        }
        return $max - sqrt((1 - $u) * ($max - $min) * ($max - $mode));
    }

    /** случайный элемент массива */
    public function pick(array $arr): mixed
    {
        if ($arr === []) { return null; }
        $arr = array_values($arr);
        return $arr[$this->int(0, count($arr) - 1)];
    }

    /** k различных элементов (без повторов), порядок случайный */
    public function sample(array $arr, int $k): array
    {
        $arr = array_values($arr);
        $this->shuffle($arr);
        return array_slice($arr, 0, max(0, min($k, count($arr))));
    }

    /** перемешать на месте (Fisher–Yates) */
    public function shuffle(array &$arr): void
    {
        for ($i = count($arr) - 1; $i > 0; $i--) {
            $j = $this->int(0, $i);
            [$arr[$i], $arr[$j]] = [$arr[$j], $arr[$i]];
        }
    }

    /**
     * Взвешенный выбор. $weights = [key => weight]. Возвращает key.
     */
    public function weighted(array $weights): string
    {
        $total = array_sum($weights);
        if ($total <= 0) { return (string) array_key_first($weights); }
        $r = $this->float() * $total;
        $acc = 0.0;
        foreach ($weights as $key => $w) {
            $acc += $w;
            if ($r < $acc) { return (string) $key; }
        }
        return (string) array_key_last($weights);
    }
}

<?php
declare(strict_types=1);

/**
 * Граф перелинковки 7 (N) страниц: матрица связей, сироты, тупики,
 * глубина клика от первой страницы, средняя исходящая степень.
 */
final class LinkGraph
{
    /** @var string[] нормализованные url/имена страниц (индекс = номер страницы) */
    private array $keys;
    /** @var array<int,array<int,int>> матрица NxN */
    public array $matrix;

    /**
     * @param array<int,string> $pageKeys        канонические ключи страниц (url или имя файла)
     * @param array<int,list<string>> $pageLinks исходящие внутренние href каждой страницы
     */
    public function __construct(array $pageKeys, array $pageLinks)
    {
        $this->keys = array_map([self::class, 'canon'], $pageKeys);
        $n = count($pageKeys);
        $this->matrix = array_fill(0, $n, array_fill(0, $n, 0));

        foreach ($pageLinks as $i => $hrefs) {
            foreach ($hrefs as $href) {
                $j = $this->resolve($href);
                if ($j !== null && $j !== $i) {
                    $this->matrix[$i][$j] = 1;
                }
            }
        }
    }

    private static function canon(string $s): string
    {
        $s = strtolower(trim($s));
        $path = parse_url($s, PHP_URL_PATH);
        if ($path) { $s = $path; }
        $s = ltrim($s, '/');
        $s = preg_replace('/\.(html?|php)$/', '', $s) ?? $s;
        $s = rtrim($s, '/');
        return $s === '' ? 'index' : $s;
    }

    private function resolve(string $href): ?int
    {
        $c = self::canon($href);
        foreach ($this->keys as $i => $k) {
            if ($k === $c || basename($k) === basename($c)) { return $i; }
        }
        return null;
    }

    public function incoming(): array
    {
        $n = count($this->keys);
        $in = array_fill(0, $n, 0);
        foreach ($this->matrix as $i => $row) {
            foreach ($row as $j => $v) { if ($i !== $j && $v) { $in[$j]++; } }
        }
        return $in;
    }

    public function outgoing(): array
    {
        return array_map(fn($row) => array_sum($row), $this->matrix);
    }

    public function orphanPages(): int
    {
        return count(array_filter($this->incoming(), fn($x) => $x === 0));
    }

    public function deadEndPages(): int
    {
        return count(array_filter($this->outgoing(), fn($x) => $x === 0));
    }

    public function avgOutgoing(): float
    {
        $out = $this->outgoing();
        return $out ? round(array_sum($out) / count($out), 1) : 0.0;
    }

    /** макс. глубина клика от страницы 0 (BFS); недостижимые = бесконечность -> N */
    public function maxDepth(): int
    {
        $n = count($this->keys);
        if (!$n) { return 0; }
        $dist = array_fill(0, $n, PHP_INT_MAX);
        $dist[0] = 0;
        $queue = [0];
        while ($queue) {
            $cur = array_shift($queue);
            foreach ($this->matrix[$cur] as $j => $v) {
                if ($v && $dist[$j] === PHP_INT_MAX) {
                    $dist[$j] = $dist[$cur] + 1;
                    $queue[] = $j;
                }
            }
        }
        $reachable = array_filter($dist, fn($d) => $d !== PHP_INT_MAX);
        $unreached = $n - count($reachable);
        return max($reachable ? max($reachable) : 0, $unreached ? $n : 0);
    }
}

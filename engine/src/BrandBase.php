<?php
declare(strict_types=1);

/**
 * База запросов по брендам (data/brands-index.json + data/brands/*.json.gz).
 * Определяет бренд страницы по контенту и отдаёт его семантику (запросы + клики),
 * которая используется как автоматические ключи вместо ручного ввода.
 */
final class BrandBase
{
    private string $dir;
    /** @var array<int,array<string,mixed>> */
    private array $index;

    public function __construct(?string $dataDir = null)
    {
        $this->dir = $dataDir ?? (__DIR__ . '/../data');
        $file = "{$this->dir}/brands-index.json";
        $this->index = is_file($file)
            ? (json_decode((string) file_get_contents($file), true) ?: [])
            : [];
    }

    public function available(): bool { return $this->index !== []; }

    /** @return array<int,array<string,mixed>> */
    public function index(): array { return $this->index; }

    /** определить бренд по контенту: максимум вхождений маркеров бренда */
    public function detect(string $textLower): ?array
    {
        $best = null; $bestScore = 0;
        foreach ($this->index as $b) {
            $score = 0;
            foreach (($b['keys'] ?? []) as $k) {
                $k = mb_strtolower((string) $k, 'UTF-8');
                if ($k === '') { continue; }
                $score += self::countOccurrences($textLower, $k);
            }
            if ($score > $bestScore
                || ($score === $bestScore && $best !== null && $score > 0
                    && ($b['total_clicks'] ?? 0) > ($best['total_clicks'] ?? 0))) {
                $bestScore = $score; $best = $b;
            }
        }
        return $bestScore > 0 ? $best : null;
    }

    public function byName(string $name): ?array
    {
        foreach ($this->index as $b) {
            if (mb_strtolower((string) $b['name'], 'UTF-8') === mb_strtolower($name, 'UTF-8')) { return $b; }
        }
        return null;
    }

    /**
     * Загрузить запросы бренда.
     * @return array<int,array{0:string,1:int}> [[query, clicks], ...] по убыванию кликов
     */
    public function queries(string $file): array
    {
        $path = "{$this->dir}/brands/{$file}.json.gz";
        if (!is_file($path)) { return []; }
        $raw = (string) file_get_contents($path);
        $json = @gzdecode($raw);
        if ($json === false) { return []; }
        return json_decode($json, true) ?: [];
    }

    /** число вхождений подстроки на границах слов (для латиницы/кириллицы) */
    private static function countOccurrences(string $haystack, string $needle): int
    {
        $q = preg_quote($needle, '/');
        return (int) preg_match_all('/(?<![\p{L}\p{Nd}])' . $q . '(?![\p{L}\p{Nd}])/u', $haystack);
    }
}

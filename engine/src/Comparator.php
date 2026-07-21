<?php
declare(strict_types=1);

require_once __DIR__ . '/Analyzer.php';

/**
 * Сравнение двух наборов страниц (твой vs конкурент).
 * Страницы сопоставляются по определённому бренду; для каждой пары считается
 * разрыв по запросам (что закрывает один, но не другой). Метрики «рядом»
 * фронтенд строит сам по схеме, используя a.pages[] и b.pages[].
 */
final class Comparator
{
    public function __construct(private string $domain = '') {}

    /**
     * @param array<int,array<string,mixed>> $setA
     * @param array<int,array<string,mixed>> $setB
     */
    public function compare(array $setA, array $setB): array
    {
        $analyzer = new Analyzer($this->domain, null, true);   // fullQueries = true
        $a = $analyzer->run($setA);
        $b = $analyzer->run($setB);

        $brandIndexA = $this->brandIndex($a['pages']);
        $brandIndexB = $this->brandIndex($b['pages']);

        // 1) пары по общему бренду (твоя страница vs конкурент по тому же бренду)
        $pairs = [];
        foreach ($brandIndexA as $brand => $ai) {
            if (!isset($brandIndexB[$brand])) { continue; }
            $bi = $brandIndexB[$brand];
            $pairs[] = $this->makePair($brand, $ai, $bi, $a, $b);
        }
        $pairedBy = 'brand';

        // 2) если общих брендов нет — пары по типу страницы (main↔main, bonus↔bonus…)
        if (!$pairs) {
            $pairedBy = 'page';
            $bByType = [];
            foreach ($b['pages'] as $j => $p) { $bByType[$this->pageType($p)] = $j; }
            foreach ($a['pages'] as $i => $p) {
                $t = $this->pageType($p);
                if (isset($bByType[$t])) {
                    $pairs[] = $this->makePair($t, $i, $bByType[$t], $a, $b);
                }
            }
        }

        // очищаем тяжёлый foundAll из выдачи — он больше не нужен фронту
        $this->stripFoundAll($a['pages']);
        $this->stripFoundAll($b['pages']);

        return [
            'a'        => $a,
            'b'        => $b,
            'pairs'    => $pairs,
            'pairedBy' => $pairedBy,
            'onlyA' => array_values(array_diff(array_keys($brandIndexA), array_keys($brandIndexB))),
            'onlyB' => array_values(array_diff(array_keys($brandIndexB), array_keys($brandIndexA))),
        ];
    }

    private function makePair(string $label, int $ai, int $bi, array $a, array $b): array
    {
        return [
            'brand'    => $label,
            'aIndex'   => $ai,
            'bIndex'   => $bi,
            'gapBnotA' => $this->gap($b['pages'][$bi], $a['pages'][$ai]),
            'gapAnotB' => $this->gap($a['pages'][$ai], $b['pages'][$bi]),
        ];
    }

    /** тип страницы из имени/URL (main/zerkalo/vhod/…) */
    private function pageType(array $page): string
    {
        $s = strtolower(($page['name'] ?? '') . ' ' . ($page['url'] ?? ''));
        foreach (['main','zerkalo','vhod','registracia','bonus','slots','app'] as $t) {
            if (str_contains($s, $t)) { return $t; }
        }
        if (str_contains($s, '/') && preg_match('#/\s*$#', $s)) { return 'main'; }
        return $page['name'] ?? 'page';
    }

    /** бренд -> индекс первой страницы этого бренда */
    private function brandIndex(array $pages): array
    {
        $map = [];
        foreach ($pages as $i => $p) {
            $brand = $p['brand'] ?? null;
            if ($brand !== null && !isset($map[$brand])) { $map[$brand] = $i; }
        }
        return $map;
    }

    /** запросы, найденные у $src, но НЕ найденные у $other (по убыванию кликов, топ-30) */
    private function gap(array $src, array $other): array
    {
        $otherSet = [];
        foreach (($other['foundAll'] ?? []) as [$q, $c]) { $otherSet[$q] = true; }
        $gap = [];
        foreach (($src['foundAll'] ?? []) as [$q, $c]) {
            if (!isset($otherSet[$q])) { $gap[] = ['q' => $q, 'clicks' => (int) $c]; }
        }
        // foundAll уже по убыванию кликов
        return array_slice($gap, 0, 30);
    }

    private function stripFoundAll(array &$pages): void
    {
        foreach ($pages as &$p) { unset($p['foundAll']); }
    }
}

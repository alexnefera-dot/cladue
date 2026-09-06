<?php
function prose(string $h): string {
    $h = preg_replace('~<(script|style)[^>]*>.*?</\1>~is', ' ', $h);
    $h = preg_replace('~<[^>]+>~u', ' ', $h);
    $h = html_entity_decode($h, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    return preg_replace('~\s+~u', ' ', $h);
}
function shing(string $t, int $n = 5): array {
    $w = preg_split('~[^\p{L}\p{N}]+~u', mb_strtolower($t), -1, PREG_SPLIT_NO_EMPTY);
    $r = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $r[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $r;
}
$a = shing(prose(file_get_contents($argv[1])));
$b = shing(prose(file_get_contents($argv[2])));
$c = array_intersect_key($a, $b);
printf("%d из %d = %.2f%%\n", count($c), count($a), 100 * count($c) / max(1, count($a)));
foreach (array_keys($c) as $s) { echo "  $s\n"; }

<?php
require __DIR__ . '/shingle.php';
$a = shingles(chist(file_get_contents($argv[1])));
foreach (array_slice($argv, 2) as $f) {
    $b = shingles(chist(file_get_contents($f)));
    $min = min(count($a), count($b));
    printf("%-45s %.2f%%\n", $f, $min ? count(array_intersect_key($a, $b)) / $min * 100 : 0);
}

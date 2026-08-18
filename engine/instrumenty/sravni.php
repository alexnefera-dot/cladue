<?php
require __DIR__ . '/shingle.php';
[$dir, $file] = [rtrim($argv[1], '/'), $argv[2]];
$b = shingles(chist(file_get_contents($file)));
foreach (glob("$dir/*.html") as $f) {
    $a = shingles(chist(file_get_contents($f)));
    $inter = count(array_intersect_key($a, $b));
    $union = count($a) + count($b) - $inter;
    printf("%-18s %.2f%%\n", basename($f), $union ? $inter / $union * 100 : 0);
}

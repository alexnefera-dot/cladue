<?php
require __DIR__ . '/shingle.php';
[$mine, $other] = [$argv[1], $argv[2]];
$b = shingles(chist(file_get_contents($other)));
$html = file_get_contents($mine);
preg_match_all('~<(p|li|td|summary|h2|h3|blockquote)\b[^>]*>(.*?)</\1>~is', $html, $m, PREG_SET_ORDER);
foreach ($m as $blk) {
    $sh = shingles(chist($blk[0]));
    if (!$sh) { continue; }
    $hit = count(array_intersect_key($sh, $b)) / count($sh);
    if ($hit >= 0.2) {
        printf("%3d%% <%s> %s\n", $hit * 100, $blk[1],
            mb_substr(trim(preg_replace('~\s+~u', ' ', strip_tags($blk[2]))), 0, 110));
    }
}

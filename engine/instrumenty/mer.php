<?php
require_once __DIR__ . '/../src/PageMetrics.php';
$f = $argv[1];
$type = $argv[2] ?? 'main';
$raw = file_get_contents($f);
$a = new Analyzer($raw);
$v = PageMetrics::measure($a, $type, $raw, ['ru'=>'%brand_name_ru%','en'=>'%brand_name_en%']);
$p = json_decode(file_get_contents(__DIR__ . '/../data-v4/profil-avgust.json'), true)['страницы'][$type]['поля'];
foreach ($p as $k => $c) {
    $mine = $v[$k] ?? null;
    $lo = $c['полоса'][0]; $hi = $c['полоса'][1];
    $bad = is_null($mine) ? '?' : (($mine < $lo || $mine > $hi) ? '  ✗' : '');
    printf("%-20s %9s   [%s — %s]%s\n", $k, is_null($mine)?'—':(is_float($mine)?round($mine,2):$mine), $lo, $hi, $bad);
}

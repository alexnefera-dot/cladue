<?php
require_once __DIR__ . '/../src/PageMetrics.php';
// mer.php <файл> [тип] [--профиль=<файл>]
$profilFile = __DIR__ . '/../data-v4/profil-avgust.json';
$pos = [];
foreach (array_slice($argv, 1) as $a) {
    if (str_starts_with($a, '--профиль=')) { $profilFile = substr($a, strlen('--профиль=')); continue; }
    $pos[] = $a;
}
$f = $pos[0] ?? '';
$type = $pos[1] ?? 'main';
$raw = file_get_contents($f);
$an = new Analyzer($raw);
$v = PageMetrics::measure($an, $type, $raw, ['ru'=>'%brand_name_ru%','en'=>'%brand_name_en%']);
$p = json_decode((string) file_get_contents($profilFile), true)['страницы'][$type]['поля'];
foreach ($p as $k => $c) {
    $mine = $v[$k] ?? null;
    $lo = $c['полоса'][0]; $hi = $c['полоса'][1];
    $bad = is_null($mine) ? '?' : (($mine < $lo || $mine > $hi) ? '  ✗' : '');
    printf("%-20s %9s   [%s — %s]%s\n", $k, is_null($mine)?'—':(is_float($mine)?round($mine,2):$mine), $lo, $hi, $bad);
}

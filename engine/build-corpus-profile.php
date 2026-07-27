<?php
declare(strict_types=1);

/**
 * Строит profile.json (коридоры [p10,median,p90]) для АЛЬТЕРНАТИВНОГО корпуса
 * из его donors.json. Числовые параметры пересчитываются по наборам-донорам;
 * структурные поля (веса блоков, sem_clusters и т.п.) берутся из базового
 * profile.json нашего корпуса, чтобы Planner имел все нужные поля.
 *
 *   php build-corpus-profile.php <donors.json> <out-profile.json> [excl=setA,setB]
 *
 * Пример (v2 dorgen, исключая аномальный набор):
 *   php build-corpus-profile.php data-dorgen/donors.json data-dorgen/profile.json set232
 */

$donorsPath = $argv[1] ?? '';
$outPath    = $argv[2] ?? '';
$excl       = isset($argv[3]) ? array_filter(array_map('trim', explode(',', $argv[3]))) : [];
if ($donorsPath === '' || $outPath === '') {
    fwrite(STDERR, "usage: build-corpus-profile.php <donors.json> <out-profile.json> [excl=setA,setB]\n");
    exit(1);
}

$base = json_decode((string) file_get_contents(__DIR__ . '/data/profile.json'), true);
$don  = json_decode((string) file_get_contents($donorsPath), true)['sites'] ?? [];
if (!$don) { fwrite(STDERR, "нет доноров в $donorsPath\n"); exit(1); }

$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
// profile-ключ → ключ в donor-page
$MAP = [
    'words'=>'words','h2'=>'h2','sections'=>'sections','lists'=>'lists','tables'=>'tables','quotes'=>'quotes',
    'strong'=>'strong','faq'=>'faq','numbers_per100'=>'numbers_per100','adj_pct'=>'adj_pct','emoji_body'=>'emoji',
    'entities'=>'entities','first_person'=>'first_person','vy'=>'vy','imperatives'=>'imperatives',
    'nausea_acad'=>'nausea_acad','water'=>'water','brand_ru'=>'brand_ru','brand_en'=>'brand_en',
];
$pct = static function (array $a, float $p): float {
    sort($a); $n = count($a); if ($n === 0) return 0.0;
    $i = ($n - 1) * $p; $lo = (int) floor($i); $hi = (int) ceil($i);
    return $lo === $hi ? (float) $a[$lo] : round($a[$lo] + ($i - $lo) * ($a[$hi] - $a[$lo]), 2);
};

$used = 0;
foreach ($TYPES as $t) {
    foreach ($MAP as $pk => $dk) {
        $vals = [];
        foreach ($don as $name => $s) {
            if (in_array($name, $excl, true)) continue;
            $v = $s['pages'][$t][$dk] ?? null;
            if ($v !== null) $vals[] = (float) $v;
        }
        if (!$vals) continue;
        $base['types'][$t][$pk] = [$pct($vals, 0.10), $pct($vals, 0.50), $pct($vals, 0.90)];
        $used++;
    }
}
$base['_meta']['source'] = basename($donorsPath) . ($excl ? ' (исключены: ' . implode(',', $excl) . ')' : '');
file_put_contents($outPath, json_encode($base, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT));
fwrite(STDERR, "→ $outPath | пересчитано триплетов: $used, доноров: " . (count($don) - count($excl)) . "\n");

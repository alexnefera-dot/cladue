<?php
declare(strict_types=1);
/**
 * Замер набора против СТАРОЙ связки (svyazka12bezzachina), а не против донора.
 * Коридор тот же: |наше − образец| ≤ max(25% образца, 2) для счётных и 0.8 для долей.
 *
 *   php check-oldstyle.php <папка-с-генерацией> [папка-образца]
 */
require_once __DIR__ . '/src/PageMetrics.php';

$BRAND = ['ru' => '', 'en' => ''];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('~^--brand-ru=(.*)$~u', $a, $m)) { $BRAND['ru'] = $m[1]; }
    if (preg_match('~^--brand-en=(.*)$~u', $a, $m)) { $BRAND['en'] = $m[1]; }
}
$args = array_values(array_filter(array_slice($argv, 1),
    fn($a) => $a !== '--no-signals' && !str_starts_with($a, '--brand-')));
$SIGNALS = !in_array('--no-signals', $argv, true);
$DIR = $args[0] ?? '';
$REF = $args[1] ?? '/tmp/old-bez-zachina/svyazka3';
if ($DIR === '') { fwrite(STDERR, "usage: check-oldstyle.php <dir> [ref]\n"); exit(1); }

$F = PageMetrics::fields($SIGNALS);

function measureOne(Analyzer $a, string $t, string $raw): array
{
    return PageMetrics::measure($a, $t, $raw, $GLOBALS['BRAND']);
}

function off($our, $ref, bool $rate): bool
{
    return PageMetrics::off($our, $ref, $rate);
}

$a = new Analyzer();
$hit = 0; $cnt = 0; $miss = [];
echo "\n=== ЗАМЕР ПРОТИВ СТАРОЙ СВЯЗКИ ===\n";
foreach (glob("$REF/*.html") as $rf) {
    $t = pathinfo($rf, PATHINFO_FILENAME);
    if (!is_file("$DIR/$t.html")) { printf("  %-13s нет файла\n", $t); continue; }
    $R = measureOne($a, $t, (string) file_get_contents($rf));
    $O = measureOne($a, $t, (string) file_get_contents("$DIR/$t.html"));
    $h = 0; $c = 0;
    foreach ($F as $k => [$lab, $rate]) {
        $c++;
        if (off($O[$k], $R[$k], (bool) $rate)) { $miss[$lab][] = "$t {$O[$k]} vs {$R[$k]}"; }
        else { $h++; }
    }
    $hit += $h; $cnt += $c;
    printf("  %-13s %d/%d = %d%%\n", $t, $h, $c, round($h / $c * 100));
}
printf("  ИТОГО: %d/%d = %d%%\n", $hit, $cnt, $cnt ? round($hit / $cnt * 100) : 0);
if ($miss) {
    echo "\n=== ПРОМАХИ ===\n";
    uasort($miss, fn($x, $y) => count($y) <=> count($x));
    foreach ($miss as $lab => $list) {
        printf("  %-22s %d : %s\n", $lab, count($list), implode(' | ', array_slice($list, 0, 6)));
    }
}
echo "STATUS " . json_encode(['match' => $cnt ? (int) round($hit / $cnt * 100) : 0, 'hit' => $hit, 'total' => $cnt]) . "\n";

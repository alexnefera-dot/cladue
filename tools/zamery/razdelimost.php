<?php
/**
 * Разделимость двух корпусов: какие поля выдают автора.
 *
 *   php tools/zamery/razdelimost.php <чужой корпус> <наш корпус>
 *
 * Для каждого поля ищется лучший одиночный порог и считается доля страниц,
 * которые он относит верно. 50 % — монетка, поле автора не выдаёт; 100 % —
 * выдаёт всегда. Мерка приёмки при подгонке под чужое семейство: комплект не
 * принят, пока хоть одно поле сидит выше 70 %.
 *
 * На образце из 42 сайтов против нашего корпуса из 66 наборов: 64 поля,
 * девять выше 90 %, девятнадцать выше 80 %, худшее — faq_pairs 99,1 %.
 */
require_once __DIR__ . '/../../engine/src/PageMetrics.php';

$tipy = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
$a = new Analyzer();

function sobrat(string $root, array $tipy, Analyzer $a): array
{
    $out = [];
    foreach (glob("$root/*", GLOB_ONLYDIR) as $d) {
        foreach ($tipy as $t) {
            $f = "$d/$t.html";
            if (!is_file($f)) { continue; }
            $M = PageMetrics::measure($a, $t, (string) file_get_contents($f),
                ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
            foreach ($M as $k => $v) { if (is_numeric($v)) { $out[$t][$k][] = (float) $v; } }
        }
    }
    return $out;
}

if (($argv[1] ?? '') === '' || ($argv[2] ?? '') === '') {
    fwrite(STDERR, "usage: php tools/zamery/razdelimost.php <чужой корпус> <наш корпус>\n");
    exit(1);
}
$O = sobrat($argv[1], $tipy, $a);
$N = sobrat($argv[2], $tipy, $a);

// Разделимость поля — доля верных отнесений при лучшем одиночном пороге.
$itog = [];
foreach ($tipy as $t) {
    foreach (array_keys($N[$t] ?? []) as $k) {
        if (!isset($O[$t][$k])) { continue; }
        $x = $O[$t][$k];
        $y = $N[$t][$k];
        $vse = array_values(array_unique(array_merge($x, $y)));
        sort($vse);
        $best = 0.0;
        foreach ($vse as $por) {
            $ok = 0;
            foreach ($x as $v) { if ($v <= $por) { $ok++; } }
            foreach ($y as $v) { if ($v >  $por) { $ok++; } }
            $d = $ok / (count($x) + count($y));
            $best = max($best, max($d, 1 - $d));
        }
        $itog[$k][$t] = $best * 100;
    }
}
$sr = [];
foreach ($itog as $k => $po) { $sr[$k] = array_sum($po) / count($po); }
arsort($sr);

printf("%-26s %7s   %s\n", 'поле', 'среднее', 'по типам (main app bonus reg slots vhod zerk)');
foreach ($sr as $k => $v) {
    if ($v < 70) { continue; }
    $stroka = '';
    foreach ($tipy as $t) { $stroka .= sprintf('%5.0f', $itog[$k][$t] ?? 0); }
    printf("%-26s %6.1f%%   %s\n", $k, $v, $stroka);
}
printf("\nполей всего %d, разделяющих ≥90%%: %d, ≥80%%: %d, ≥70%%: %d\n",
    count($sr),
    count(array_filter($sr, static fn(float $v) => $v >= 90)),
    count(array_filter($sr, static fn(float $v) => $v >= 80)),
    count(array_filter($sr, static fn(float $v) => $v >= 70)));
exit(count(array_filter($sr, static fn(float $v) => $v >= 70)) ? 1 : 0);

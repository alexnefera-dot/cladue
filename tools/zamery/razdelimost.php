<?php
/**
 * Разделимость двух корпусов: какие поля выдают автора.
 *
 *   php tools/zamery/razdelimost.php <чужой корпус> <наш корпус>
 *
 * Для каждого поля ищется лучший одиночный порог и считается доля страниц,
 * которые он относит верно — ПО КАЖДОЙ СТОРОНЕ ОТДЕЛЬНО, со средним из двух.
 * 50 % — монетка, поле автора не выдаёт; 100 % — выдаёт всегда. Мерка приёмки
 * при подгонке под чужое семейство: комплект не принят, пока хоть одно поле
 * сидит выше 70 %.
 *
 * Считать общей долей нельзя: она упирается в размер большего корпуса. Образец
 * из 42 наборов против четырёх наших давал ровно 91,3 % на всех 64 полях сразу,
 * и это не замер, а 42/46 — доля чужих страниц среди всех.
 *
 * Корпуса разного размера мерке не мешают, но и сравнивать её числа между
 * прогонами на разных корпусах нельзя: порог подбирается на тех же страницах,
 * на которых потом и меряется, и четыре набора он подгоняет заметно легче
 * шестидесяти шести.
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
        // Доля считается ПО КАЖДОЙ СТОРОНЕ ОТДЕЛЬНО и усредняется. Прежде
        // складывались верные отнесения и делились на общее число страниц —
        // и такая доля упирается в размер большего корпуса: 42 чужих набора
        // против наших четырёх давали 91,3 % на всех 64 полях разом, потому
        // что 42/46 и есть 91,3 %. Порог, относящий вообще всё к чужим, брал
        // этот потолок, и мерка молчала о том, ради чего заведена.
        //
        // При равных корпусах обе формулы совпадают, поэтому прежние замеры
        // на 462 наших страницах против 294 чужих завышены умеренно — их
        // монетка сидела на 61 %, а не на 50 %.
        $best = 0.0;
        foreach ($vse as $por) {
            $ih = 0; $nash = 0;
            foreach ($x as $v) { if ($v <= $por) { $ih++; } }
            foreach ($y as $v) { if ($v >  $por) { $nash++; } }
            $d = ($ih / count($x) + $nash / count($y)) / 2;
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

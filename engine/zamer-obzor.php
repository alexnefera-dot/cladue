<?php
/**
 * Замер одной страницы против одного эталона — тот же цикл, что и
 * zamer-stranicy.php, но пути задаются явно: одностраничные доноры лежат
 * не в наборах, а по одному файлу на папку.
 *
 *   php engine/zamer-obzor.php <наш.html> <эталон.html> [тип] [бренд_ru] [бренд_en]
 *
 * Тип по умолчанию main: у обзора нет тематических подстраниц, и
 * on_topic_pct для него не считается — ровно как у главной в наборах.
 *
 * Бренд обязателен для честного счёта: у эталона имя написано словом, у нас
 * стоит плейсхолдер. Без пары «ru/en» счётчик видит имя только на одной
 * стороне и выдаёт разрыв в четыре поля на ровном месте.
 */
require_once __DIR__ . "/src/PageMetrics.php";

$our = $argv[1] ?? '';
$ref = $argv[2] ?? '';
$t   = $argv[3] ?? 'main';
$brand = ['ru' => $argv[4] ?? '', 'en' => $argv[5] ?? ''];
if ($our === '' || $ref === '') {
    fwrite(STDERR, "usage: zamer-obzor.php <наш.html> <эталон.html> [тип]\n");
    exit(1);
}
if (!is_file($ref)) { fwrite(STDERR, "нет эталона: $ref\n"); exit(1); }

$a = new Analyzer();
$F = PageMetrics::fields(true);
$R = PageMetrics::measure($a, $t, (string) file_get_contents($ref), $brand);
$O = PageMetrics::measure($a, $t, is_file($our) ? (string) file_get_contents($our) : '', $brand);

$h = 0; $c = 0;
foreach ($F as $k => [$lab, $rate]) {
    $c++;
    $bad = PageMetrics::off($O[$k], $R[$k], (bool) $rate);
    if (!$bad) { $h++; }
    printf("%-22s %8s %8s  %s\n", $k,
        is_float($O[$k]) ? round($O[$k], 1) : $O[$k],
        is_float($R[$k]) ? round($R[$k], 1) : $R[$k],
        $bad ? "XXXX" : "ok");
}
printf("\n%s: %d/%d = %d%%\n", basename($our, '.html'), $h, $c, (int) round($h / $c * 100));

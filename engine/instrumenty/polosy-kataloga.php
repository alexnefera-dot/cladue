<?php
/**
 * Полосы приёмки для страницы-каталога слотов.
 *
 * У двенадцати доноров NEW100 на slots лежит не витрина, а каталог из 276
 * карточек. Профильная полоса slots снята с обычных доноров и каталогу не
 * подходит: terms_total у него 489 против 108. Инструмент считает дециль
 * p10–p90 по этим двенадцати страницам — так же, как V5_GUSTYE_POLOSY
 * считались по густым наборам.
 *
 *   php engine/instrumenty/polosy-kataloga.php
 */
require_once __DIR__ . '/../src/PageMetrics.php';
$КОРПУС = __DIR__ . '/../../samples/v5-konkurent/NEW100';
$ПОЛЯ = ['paragraphs','words_per_para','para_short','para_spread','words','sections','h2',
         'nausea_acad','water','adj_pct','terms_total','anchors','fact_values'];
$дец = function (array $v, float $q) { sort($v); $n = count($v);
    $i = ($n - 1) * $q; $l = (int) floor($i); $h = (int) ceil($i);
    return $l == $h ? (float) $v[$l] : $v[$l] + ($v[$h] - $v[$l]) * ($i - $l); };

$собрано = []; $каталожные = [];
foreach (scandir($КОРПУС) as $н) {
    if ($н[0] === '.' || !is_dir("$КОРПУС/$н")) { continue; }
    $f = "$КОРПУС/$н/slots.html";
    if (!is_file($f)) { continue; }
    $raw = (string) file_get_contents($f);
    if (substr_count($raw, '<div class="card">') < 50) { continue; }   // каталог, а не обычная страница
    $каталожные[] = $н;
    $м = PageMetrics::measure(new Analyzer($raw), 'slots', $raw, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    foreach ($м as $k => $v) { if (is_numeric($v)) { $собрано[$k][] = (float) $v; } }
}
echo 'каталогов: ', count($каталожные), ' — ', implode(' ', $каталожные), "\n\n";
$строки = [];
foreach ($ПОЛЯ as $k) {
    if (!isset($собрано[$k])) { echo "нет поля $k\n"; continue; }
    $низ = $дец($собрано[$k], 0.10); $верх = $дец($собрано[$k], 0.90);
    printf("%-16s p10 %8.1f  медиана %8.1f  p90 %8.1f\n", $k, $низ, $дец($собрано[$k], 0.5), $верх);
    $строки[] = sprintf("'%s' => [%.1f, %.1f]", $k, $низ, $верх);
}
echo "\nconst V5_POLOSY_KATALOG = ['slots' => [", implode(', ', $строки), "]];\n";

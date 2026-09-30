<?php
// Сырые метрики страниц набора в json: приёмка отдаёт только промахи, а для
// замера сдвига нужны сами значения — и по полям, которые в полосу попали.
require_once __DIR__ . '/../src/PageMetrics.php';
$папка = $argv[1] ?? '';
$ТИПЫ = ['main','obzor','slots','bonus','promo','registracia','vhod','zerkalo','app','news','partnery','info'];
$из = [];
foreach ($ТИПЫ as $т) {
    $f = "$папка/$т.html";
    if (!is_file($f)) { continue; }
    $raw = (string) file_get_contents($f);
    $a = new Analyzer($raw);
    $из[$т] = PageMetrics::measure($a, $т, $raw, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
}
echo json_encode($из, JSON_UNESCAPED_UNICODE), "\n";

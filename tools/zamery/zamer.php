<?php
require_once __DIR__ . '/../../engine/src/PageMetrics.php';
$file = $argv[1]; $type = $argv[2];
$prof = json_decode((string) file_get_contents(__DIR__ . '/../../engine/data-v5/profil-v5-B.json'), true);
$a = new Analyzer();
$M = PageMetrics::measure($a, $type, (string) file_get_contents($file), ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
$ok = 0; $vsego = 0; $bad = [];
foreach ($prof['страницы'][$type]['поля'] as $k => $pp) {
    if (empty($pp['держат']) || !array_key_exists($k, $M)) { continue; }
    $vsego++;
    $pol = !empty($pp['дробное']) ? 0.8 : 2.0;
    if (abs((float) $M[$k] - (float) $pp['цель']) <= max(0.25 * abs((float) $pp['цель']), $pol)) { $ok++; }
    else { $bad[] = $k . ' ' . round((float) $M[$k], 1) . '→' . $pp['цель']; }
}
printf("%s: %d/%d = %d%%\n", $type, $ok, $vsego, $vsego ? round($ok/$vsego*100) : 0);
foreach ($bad as $b) { echo "  ✗ $b\n"; }
// полы по рынку
foreach (['terms_total' => 'термины', 'first_person' => 'лицо', 'imperatives' => 'повелительное', 'you_forms' => '«вы»', 'risk_places' => 'риск'] as $k => $imya) {
    $polR = (float) ($prof['страницы'][$type]['поля'][$k]['пол_рынка'] ?? 0);
    if ($polR && isset($M[$k]) && (float) $M[$k] < $polR) { echo "  ⌄ пол $imya: " . round((float) $M[$k],1) . " < $polR\n"; }
}

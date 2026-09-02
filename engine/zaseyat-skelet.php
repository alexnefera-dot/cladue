<?php
/**
 * Засев реестра скелета H2 главной по готовому корпусу.
 *
 * Левая часть каждого H2 главной выбирается в zadanie-v4.php по «наименее
 * занятой» из пула, а занятость берётся из engine/data-v4/maski.json,
 * ключ «занято.скелет». Реестр завели позже самого корпуса, и первые
 * комплекты в него не попали: из 25 главных там числилось 12 записей.
 *
 * Из-за этого «наименее занятая» считалась по неполным данным, и очередное
 * задание выдавало левые части, уже стоящие у соседей. На kolesnaya-1 это
 * дало скелет главной 28,6 % при потолке 25 — приёмка завернула комплект на
 * заголовках, которые сама же и назначила.
 *
 * Скрипт читает главные корпуса, сопоставляет левые части с узлами по тому же
 * пулу, что и задание, и дописывает недостающие записи. Уже учтённые пары
 * «узел + левая часть + комплект» не трогает, счётчики не задваивает.
 *
 * php engine/zaseyat-skelet.php [--корпус=samples/v5-final] [--проверка]
 */
declare(strict_types=1);

$opts = [];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('~^--([^=]+)(?:=(.*))?$~su', $a, $m)) { $opts[$m[1]] = $m[2] ?? '1'; }
}
$korpus = rtrim($opts['корпус'] ?? 'samples/v5-final', '/');
$suho   = isset($opts['проверка']);

$mf = __DIR__ . '/data-v4/maski.json';
$mk = json_decode((string) file_get_contents($mf), true);
if (!$mk) { fwrite(STDERR, "нет реестра $mf\n"); exit(1); }

// Пул левых частей берём из самого задания, чтобы источник был один.
$istochnik = file_get_contents(__DIR__ . '/zadanie-v4.php');
if (!preg_match('~\$pul = \[(.*?)\n        \];~su', $istochnik, $pm)) {
    fwrite(STDERR, "не нашёл пул левых частей в zadanie-v4.php\n"); exit(1);
}
$pul = eval('return [' . $pm[1] . '];');

// Обратная карта «левая часть → узел». Одинаковых строк в разных узлах нет.
$poUzlu = [];
foreach ($pul as $uzel => $varianty) {
    foreach ($varianty as $v) { $poUzlu[$v] = $uzel; }
}

$reestr = &$mk['занято']['скелет'];
if (!is_array($reestr)) { $reestr = []; }
$shag = (int) ($mk['занято']['скелет_шаг'] ?? 0);

$dobavleno = 0; $mimo = [];
foreach (glob("$korpus/*/main.html") as $f) {
    $imya = basename(dirname($f));
    preg_match_all('~<h2[^>]*>(.*?)</h2>~is', (string) file_get_contents($f), $hm);
    foreach ($hm[1] as $zag) {
        $t = trim(preg_replace('~\s+~u', ' ', strip_tags($zag)));
        $levaya = trim(preg_split('~\s+:\s+~u', $t, 2)[0]);
        // Бренд в левой части — украшение, в пуле его нет.
        $levaya = trim(str_replace(['%brand_name_en%', '%brand_name_ru%'], '', $levaya));
        // «Авторизация в %brand_name_en%» после вычистки бренда оставляет
        // висящий предлог — в пуле его нет.
        $levaya = trim(preg_replace('~\s+(?:в|на|у|про|для)$~u', '', $levaya));
        $uzel = $poUzlu[$levaya] ?? null;
        if ($uzel === null) { $mimo[$levaya] = ($mimo[$levaya] ?? 0) + 1; continue; }
        $z = $reestr[$uzel][$levaya] ?? ['раз' => 0, 'когда' => 0, 'кто' => []];
        $kto = (array) ($z['кто'] ?? []);
        if (in_array($imya, $kto, true)) { continue; }
        $kto[] = $imya;
        $reestr[$uzel][$levaya] = ['раз' => (int) $z['раз'] + 1, 'когда' => ++$shag, 'кто' => $kto];
        $dobavleno++;
    }
}
$mk['занято']['скелет_шаг'] = $shag;

$vsego = 0;
foreach ($reestr as $u => $v) { $vsego += count($v); }
printf("узлов в реестре %d, левых частей %d, дописано записей %d\n", count($reestr), $vsego, $dobavleno);
if ($mimo) {
    printf("вне пула (это нормально для ручных заголовков): %d разных\n", count($mimo));
    foreach (array_slice($mimo, 0, 8, true) as $l => $n) { printf("  %2d  %s\n", $n, $l); }
}
if ($suho) { echo "проверка: реестр не записан\n"; exit(0); }
file_put_contents($mf, json_encode($mk, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
echo "реестр записан\n";

<?php
declare(strict_types=1);

/**
 * Разрыв между нашим корпусом и донорским.
 *
 *   php engine/razryv.php <наш.json> <доноры.json> [--json]
 *
 * На вход — две выкладки `razbros-korpusa.php --json`.
 *
 * Приёмка сравнивает одну нашу страницу с одним эталоном и отвечает
 * «сходится ли». Здесь сравниваются два корпуса, и вопрос другой: **где
 * догонять, а где, наоборот, отпустить.** Второе не менее важно: если поле у
 * доноров гуляет втрое, а мы держим его в узкой полосе, мы тратим силы на
 * дисциплину, которой у образца нет, — и платим за неё однообразием.
 *
 * Четыре вердикта:
 *   догонять  — доноры держат, мы стоим в другом месте
 *   сходится  — доноры держат, мы попадаем в их полосу
 *   отпустить — у доноров это шум, а мы держим: лишняя дисциплина
 *   мимо      — не держит никто, мерить нечего
 */

/** Ниже этой доли попаданий в коридор корпус поле не держит. */
const DERZHIT = 70;
/** И это уже точно шум. */
const SHUM = 50;

$nash = $argv[1] ?? '';
$ih = $argv[2] ?? '';
$asJson = in_array('--json', $argv, true);
if ($nash === '' || $ih === '' || !is_file($nash) || !is_file($ih)) {
    fwrite(STDERR, "usage: php engine/razryv.php <наш.json> <доноры.json> [--json]\n");
    exit(1);
}

$a = json_decode((string) file_get_contents($nash), true)['разброс'] ?? [];
$b = json_decode((string) file_get_contents($ih), true)['разброс'] ?? [];
if (!$a || !$b) { fwrite(STDERR, "в файлах нет раздела «разброс»\n"); exit(1); }

$rows = [];
foreach ($b as $k => $vb) {
    if (!isset($a[$k])) { continue; }
    $va = $a[$k];
    $mn = (float) $va['медиана'];
    $mi = (float) $vb['медиана'];
    // Тот же коридор, что и в приёмке: четверть от цели, но не меньше пола.
    $pol = !empty($vb['дробное']) ? 0.8 : 2.0;
    $dopusk = max(0.25 * abs($mi), $pol);
    $vNorme = abs($mn - $mi) <= $dopusk;
    $dn = (int) $va['держится%'];
    $di = (int) $vb['держится%'];

    if ($di >= DERZHIT) { $verdikt = $vNorme ? 'сходится' : 'догонять'; }
    elseif ($di < SHUM && $dn >= DERZHIT) { $verdikt = 'отпустить'; }
    else { $verdikt = 'мимо'; }

    $rows[$k] = [
        'подпись' => $vb['подпись'] ?? $k,
        'наша' => $mn, 'их' => $mi,
        'допуск' => round($dopusk, 2),
        'промах' => round(abs($mn - $mi) - $dopusk, 2),
        'наш держ' => $dn, 'их держ' => $di,
        'вердикт' => $verdikt,
    ];
}

$grup = ['догонять' => [], 'отпустить' => [], 'сходится' => [], 'мимо' => []];
foreach ($rows as $k => $r) { $grup[$r['вердикт']][$k] = $r; }
uasort($grup['догонять'], fn($x, $y) => $y['промах'] <=> $x['промах']);
uasort($grup['отпустить'], fn($x, $y) => $y['наш держ'] <=> $x['наш держ']);
// «Мимо» тоже по промаху: поле может не держаться у доноров и всё равно стоять
// на другом порядке величины — brand_ru у нас 45, у них 4. Это не шум, это
// другой объект, и такое надо видеть, а не хоронить в конце списка.
uasort($grup['мимо'], fn($x, $y) => $y['промах'] <=> $x['промах']);

if ($asJson) {
    echo json_encode($grup, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}

$pad = fn($v, $w, $l = false) => $l
    ? $v . str_repeat(' ', max(0, $w - mb_strlen((string) $v)))
    : str_repeat(' ', max(0, $w - mb_strlen((string) $v))) . $v;

printf("══ %s против %s ══\n", basename($nash), basename($ih));
foreach (['догонять', 'отпустить', 'сходится', 'мимо'] as $g) {
    printf("\n%s — %d полей\n", mb_strtoupper($g), count($grup[$g]));
    if (!$grup[$g]) { continue; }
    echo $pad('поле', 20, true) . $pad('наша', 9) . $pad('их', 9) . $pad('допуск', 9)
        . $pad('промах', 9) . $pad('наш держ', 10) . $pad('их держ', 9) . "\n";
    echo str_repeat('─', 75), "\n";
    foreach ($grup[$g] as $k => $r) {
        echo $pad($k, 20, true) . $pad((string) $r['наша'], 9) . $pad((string) $r['их'], 9)
            . $pad((string) $r['допуск'], 9)
            . $pad($r['промах'] > 0 ? '+' . $r['промах'] : '—', 9)
            . $pad($r['наш держ'] . '%', 10) . $pad($r['их держ'] . '%', 9) . "\n";
    }
}
echo "\n";

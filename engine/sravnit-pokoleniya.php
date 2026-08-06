<?php
declare(strict_types=1);

/**
 * Сравнение двух поколений одной фабрики.
 *
 *   php engine/sravnit-pokoleniya.php <старая.json> <новая.json> [--json]
 *
 * На вход — две выкладки `razbros-korpusa.php --json`.
 *
 * Разброс внутри одного корпуса показывает, что фабрика держит. Но узкая
 * полоса может быть и привычкой модели: если промпт про поле молчит, модель
 * всё равно выдаёт похожие значения. Отличить настройку от привычки можно
 * только вторым выпуском: **настройка переживает смену поколения, привычку
 * правят**. Поэтому поле попадает в «стабильно» лишь когда оно и держится в
 * обоих корпусах, и медиана между ними не сдвинулась.
 *
 * Три списка на выходе:
 *   стабильно — держится в обоих и медиана на месте: настройка
 *   правили   — медиана уехала: сюда фабрика прикладывала руки
 *   шум       — не держится ни там ни там: мерить нечего
 */

$staraya = $argv[1] ?? '';
$novaya = $argv[2] ?? '';
$asJson = in_array('--json', $argv, true);
if ($staraya === '' || $novaya === '' || !is_file($staraya) || !is_file($novaya)) {
    fwrite(STDERR, "usage: php engine/sravnit-pokoleniya.php <старая.json> <новая.json> [--json]\n");
    exit(1);
}

/** Порог сдвига медианы, за которым считаем, что поле правили. */
const SDVIG_PRAVILI = 40.0;
/** Порог сдвига, внутри которого считаем медиану неподвижной. */
const SDVIG_STABILNO = 20.0;
/** Ниже этой доли попаданий в коридор поле не держится. */
const DERZHITSYA = 60;

$a = json_decode((string) file_get_contents($staraya), true)['разброс'] ?? [];
$b = json_decode((string) file_get_contents($novaya), true)['разброс'] ?? [];
if (!$a || !$b) { fwrite(STDERR, "в файлах нет раздела «разброс»\n"); exit(1); }

$rows = [];
foreach ($a as $k => $v) {
    if (!isset($b[$k])) { continue; }
    $ma = (float) $v['медиана'];
    $mb = (float) $b[$k]['медиана'];
    $baza = max(abs($ma), abs($mb));
    $rows[$k] = [
        'подпись' => $v['подпись'] ?? $k,
        'старая' => $ma, 'новая' => $mb,
        'сдвиг%' => $baza > 0 ? (int) round(($mb - $ma) / $baza * 100) : 0,
        'держится старая' => (int) $v['держится%'],
        'держится новая' => (int) $b[$k]['держится%'],
    ];
}

$stab = []; $pravili = []; $shum = [];
foreach ($rows as $k => $r) {
    $derzh = $r['держится старая'] >= DERZHITSYA && $r['держится новая'] >= DERZHITSYA;
    if (abs($r['сдвиг%']) >= SDVIG_PRAVILI) { $pravili[$k] = $r; }
    elseif ($derzh && abs($r['сдвиг%']) <= SDVIG_STABILNO) { $stab[$k] = $r; }
    elseif (!$derzh) { $shum[$k] = $r; }
}
uasort($stab, fn($x, $y) => abs($x['сдвиг%']) <=> abs($y['сдвиг%']));
uasort($pravili, fn($x, $y) => abs($y['сдвиг%']) <=> abs($x['сдвиг%']));
uasort($shum, fn($x, $y) => ($x['держится новая'] + $x['держится старая']) <=> ($y['держится новая'] + $y['держится старая']));

if ($asJson) {
    echo json_encode(['стабильно' => $stab, 'правили' => $pravili, 'шум' => $shum],
        JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}

$pad = fn($v, $w, $l = false) => $l
    ? $v . str_repeat(' ', max(0, $w - mb_strlen((string) $v)))
    : str_repeat(' ', max(0, $w - mb_strlen((string) $v))) . $v;

$pechat = function (string $zagolovok, array $list) use ($pad) {
    printf("\n%s — %d полей\n", $zagolovok, count($list));
    echo $pad('поле', 20, true) . $pad('старая', 9) . $pad('новая', 9)
        . $pad('сдвиг', 8) . $pad('держ.ст', 9) . $pad('держ.нов', 9) . "\n";
    echo str_repeat('─', 64), "\n";
    foreach ($list as $k => $r) {
        echo $pad($k, 20, true) . $pad((string) $r['старая'], 9) . $pad((string) $r['новая'], 9)
            . $pad($r['сдвиг%'] . '%', 8) . $pad($r['держится старая'] . '%', 9)
            . $pad($r['держится новая'] . '%', 9) . "\n";
    }
};

printf("══ %s → %s ══\n", basename($staraya), basename($novaya));
$pechat('СТАБИЛЬНО через поколение — настройка', $stab);
$pechat('ПРАВИЛИ между поколениями', $pravili);
$pechat('ШУМ — не держится ни там, ни там', $shum);
echo "\n";

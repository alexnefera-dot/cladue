<?php
declare(strict_types=1);

/**
 * Приёмка обзорной страницы одной командой.
 *
 *   php engine/priyomka-obzor.php <папка-версии> [--korpus=samples/v3-final/singles]
 *
 * Три шлюза подряд, потому что порознь их приходилось звать тремя разными
 * скриптами и один из трёх регулярно забывался:
 *
 *   1. параметры  — 55 полей коридора против эталона (zamer-obzor.php)
 *   2. приёмы     — 11 счётчиков устройства страницы (priyomy-obzor.php)
 *   3. уникальность — против эталона и против каждой версии корпуса (overlap.php)
 *
 * Профиль и путь к эталону берутся из engine/data-v4/obzor-profile.json.
 * Код возврата 0 — все три пройдены, 1 — хоть один нет.
 */

require_once __DIR__ . '/src/Flagi.php';

$dir = $argv[1] ?? '';
$korpus = 'samples/v3-final/singles';
[$optsO] = Flagi::razobrat($argv, 2, ['корпус']);
$korpus = $optsO['корпус'] ?? $korpus;
if ($dir === '') {
    fwrite(STDERR, "usage: php engine/priyomka-obzor.php <папка-версии> [--корпус=<путь>]\n");
    exit(1);
}
$dir = rtrim($dir, '/');
$our = $dir . '/main.html';
if (!is_file($our)) { fwrite(STDERR, "нет файла: $our\n"); exit(1); }

$root = dirname(__DIR__);
$profile = json_decode((string) file_get_contents(__DIR__ . '/data-v4/obzor-profile.json'), true);
$brand = $profile['etalon']['brend'];

// Эталон: имя файла несёт комбинирующие диакритики, поэтому ищем перебором.
$refDir = $root . '/' . $profile['etalon']['papka'];
$ref = '';
foreach (scandir($refDir) ?: [] as $f) {
    if (str_ends_with($f, '.html')) { $ref = $refDir . '/' . $f; break; }
}
if ($ref === '') { fwrite(STDERR, "эталон не найден в $refDir\n"); exit(1); }

$tmpRef = sys_get_temp_dir() . '/priyomka-etalon.html';
copy($ref, $tmpRef);
$tmpRefDir = sys_get_temp_dir() . '/priyomka-etalon-dir';
@mkdir($tmpRefDir);
copy($ref, $tmpRefDir . '/main.html');

$q = fn(string $s): string => escapeshellarg($s);
$run = function (string $cmd): array {
    exec($cmd . ' 2>&1', $out, $code);
    return [implode("\n", $out), $code];
};

$name = basename($dir);
$fail = [];

// ── 1. параметры ────────────────────────────────────────────────────
[$o] = $run(sprintf(
    'php %s %s %s main %s %s',
    $q(__DIR__ . '/zamer-obzor.php'), $q($our), $q($tmpRef),
    $q($brand['ru']), $q($brand['en'])
));
preg_match('~(\d+)/(\d+)~', $o, $m);
$params = $m ? [(int) $m[1], (int) $m[2]] : [0, 55];
$badFields = [];
foreach (explode("\n", $o) as $line) {
    if (str_ends_with(trim($line), 'XXXX')) { $badFields[] = trim(explode(' ', trim($line))[0]); }
}
if ($params[0] < $params[1]) { $fail[] = 'параметры'; }

// ── 2. приёмы ───────────────────────────────────────────────────────
[$o2] = $run(sprintf('php %s %s %s', $q(__DIR__ . '/priyomy-obzor.php'), $q($our), $q($tmpRef)));
$devOk = 0; $devAll = 0; $badDev = [];
foreach (explode("\n", $o2) as $line) {
    if (!preg_match('~\S~', $line) || str_contains($line, 'ЭТАЛОН')) { continue; }
    $devAll++;
    if (str_ends_with(trim($line), 'ok')) { $devOk++; }
    else { $badDev[] = trim(preg_replace('~\s{2,}.*~u', '', trim($line))); }
}
if ($devOk < $devAll) { $fail[] = 'приёмы'; }

// ── 3. уникальность ─────────────────────────────────────────────────
$pct = function (string $out): float {
    return preg_match('~STATUS (\{.*\})~', $out, $mm)
        ? (float) (json_decode($mm[1], true)['total'] ?? 0.0) : 0.0;
};
[$o3] = $run(sprintf('php %s %s %s 6', $q(__DIR__ . '/overlap.php'), $q($dir), $q($tmpRefDir)));
$vsRef = $pct($o3);

$worst = 0.0; $worstName = '—';
foreach (glob($root . '/' . $korpus . '/*', GLOB_ONLYDIR) ?: [] as $other) {
    if (realpath($other) === realpath($root . '/' . $dir) || realpath($other) === realpath($dir)) { continue; }
    if (!is_file($other . '/main.html')) { continue; }
    [$oo] = $run(sprintf('php %s %s %s 6', $q(__DIR__ . '/overlap.php'), $q($dir), $q($other)));
    $v = $pct($oo);
    if ($v > $worst) { $worst = $v; $worstName = basename($other); }
}
$limit = (float) ($profile['unikalnost']['porog'] ?? 6.0);
if ($vsRef >= $limit || $worst >= $limit) { $fail[] = 'уникальность'; }

// ── отчёт ───────────────────────────────────────────────────────────
printf("%s\n", $name);
printf("  параметры     %d/%d%s\n", $params[0], $params[1],
    $badFields ? '  — ' . implode(', ', $badFields) : '');
printf("  приёмы        %d/%d%s\n", $devOk, $devAll,
    $badDev ? '  — ' . implode('; ', $badDev) : '');
printf("  против эталона %.2f%%\n", $vsRef);
printf("  худшая пара    %.2f%%  (%s)\n", $worst, $worstName);
printf("  ИТОГ: %s\n", $fail ? 'НЕ ПРОЙДЕНО — ' . implode(', ', $fail) : 'пройдено');

exit($fail ? 1 : 0);

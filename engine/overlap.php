<?php
declare(strict_types=1);

/**
 * Пересечение двух наборов по шинглам — второй приёмочный шлюз рядом с замером
 * параметров. Набор может лечь в коридоры и при этом повторять исходник
 * формулировками; ловится это только так.
 *
 *   php overlap.php <папка-A> <папка-B> [n]
 *
 * n — длина шингла в словах: 4 для отчёта (чувствительнее), 6 для приёмки.
 * Порог приёмки — 6% по шести словам; свои наборы по одному донору дают 0.1–3%.
 *
 * Сравниваются одноимённые файлы (main.html с main.html) и всё вместе. Текст
 * берётся по strip_tags и нормализуется: регистр, пунктуация, плейсхолдеры
 * бренда — иначе совпадением считается вёрстка, а не слова.
 */

require_once __DIR__ . '/src/NicheLexicon.php';

$A = rtrim($argv[1] ?? '', '/');
$B = rtrim($argv[2] ?? '', '/');
$N = (int) ($argv[3] ?? 6);
if ($A === '' || $B === '' || !is_dir($A) || !is_dir($B)) {
    fwrite(STDERR, "usage: overlap.php <dir-A> <dir-B> [n=6]\n");
    exit(1);
}

function words(string $file): array
{
    $t = NicheLexicon::unplaceholder((string) file_get_contents($file));
    $t = mb_strtolower(strip_tags($t));
    $t = preg_replace('~[^\p{L}\p{N}]+~u', ' ', $t);
    return preg_split('~\s+~u', trim((string) $t), -1, PREG_SPLIT_NO_EMPTY);
}

function shingles(array $w, int $n): array
{
    $o = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $o[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $o;
}

function jaccard(array $a, array $b): float
{
    if (!$a || !$b) { return 0.0; }
    $inter = count(array_intersect_key($a, $b));
    $union = count($a + $b);
    return $union ? round($inter / $union * 100, 2) : 0.0;
}

$allA = []; $allB = []; $rows = [];
foreach (glob("$A/*.html") as $fa) {
    $page = basename($fa);
    $fb   = "$B/$page";
    $wa   = words($fa);
    $sa   = shingles($wa, $N);
    $allA += $sa;
    if (!is_file($fb)) { $rows[] = [$page, count($wa), null, null]; continue; }
    $sb = shingles(words($fb), $N);
    $allB += $sb;
    $rows[] = [$page, count($wa), jaccard($sa, $sb), count(array_intersect_key($sa, $sb))];
}
// страницы, которые есть только во втором наборе, тоже идут в общий котёл
foreach (glob("$B/*.html") as $fb) {
    if (!is_file("$A/" . basename($fb))) { $allB += shingles(words($fb), $N); }
}

printf("\n=== ПЕРЕСЕЧЕНИЕ ПО %d СЛОВАМ ===\n", $N);
printf("  A: %s\n  B: %s\n\n", $A, $B);
$worst = 0.0;
foreach ($rows as [$page, $wc, $j, $hits]) {
    if ($j === null) { printf("  %-16s %5d слов   нет пары в B\n", $page, $wc); continue; }
    $worst = max($worst, $j);
    printf("  %-16s %5d слов   %5.2f%%%s\n", $page, $wc, $j, $hits ? "   совпало шинглов: $hits" : '');
}
$total = jaccard($allA, $allB);
printf("\n  ВЕСЬ НАБОР: %.2f%%   худшая страница: %.2f%%   %s\n",
    $total, $worst, $worst <= 6 ? 'приёмка ПРОЙДЕНА (порог 6%)' : 'ПОРОГ 6% ПРЕВЫШЕН');
echo "STATUS " . json_encode(['total' => $total, 'worst' => $worst, 'pass' => $worst <= 6]) . "\n";

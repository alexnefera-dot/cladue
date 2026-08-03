<?php
declare(strict_types=1);

/**
 * Пересечение двух наборов по шинглам — второй приёмочный шлюз рядом с замером
 * параметров. Набор может лечь в коридоры и при этом повторять исходник
 * формулировками; ловится это только так.
 *
 *   php overlap.php <папка-A> <папка-B> [n]
 *   php overlap.php --vnutri <папка> [n]
 *
 * n — длина шингла в словах: 4 для отчёта (чувствительнее), 6 для приёмки.
 * Порог приёмки — 6% по шести словам; свои наборы по одному донору дают 0.1–3%.
 *
 * Сравниваются одноимённые файлы (main.html с main.html) и всё вместе. Текст
 * берётся по strip_tags и нормализуется: регистр, пунктуация, плейсхолдеры
 * бренда — иначе совпадением считается вёрстка, а не слова.
 *
 * --vnutri меряет другое: перекличку страниц ВНУТРИ одного набора — какая доля
 * фраз сателлита уже произнесена на главной. Набор из уникальных относительно
 * чужих наборов страниц спокойно пересказывает сам себя: главная рассказывает
 * историю про «я активировал четыре предложения», и та же история дословно
 * уезжает в bonus.html. У девяти образцов худшая страница набора даёт 0.0–6.5%
 * при медиане 0.8; у нас медиана 2.7 и выбросы до 15.6. Порог поставлен по
 * максимуму образца — 6.5%: жёстче нельзя, два образца из девяти сами дают 2.8
 * и 6.5. Цифра между 2 и 6.5 — не провал, но повод посмотреть, не уехал ли на
 * сателлит абзац с главной целиком. Считается вложение (доля шинглов
 * сателлита), а не Жаккар: важно, сколько СВОЕГО текста сателлит занял у
 * главной, а не симметричная близость.
 */

require_once __DIR__ . '/src/NicheLexicon.php';

$VNUTRI = ($argv[1] ?? '') === '--vnutri';
if ($VNUTRI) { array_splice($argv, 1, 1); }

$A = rtrim($argv[1] ?? '', '/');
$B = $VNUTRI ? '' : rtrim($argv[2] ?? '', '/');
$N = (int) ($argv[$VNUTRI ? 2 : 3] ?? 6);
if ($A === '' || !is_dir($A) || (!$VNUTRI && ($B === '' || !is_dir($B)))) {
    fwrite(STDERR, "usage: overlap.php <dir-A> <dir-B> [n=6]\n       overlap.php --vnutri <dir> [n=6]\n");
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

if ($VNUTRI) {
    $main = is_file("$A/main.html") ? "$A/main.html" : (glob("$A/*.html")[0] ?? '');
    if ($main === '') { fwrite(STDERR, "в $A нет html\n"); exit(1); }
    $sm = shingles(words($main), $N);
    printf("\n=== ПЕРЕКЛИЧКА ВНУТРИ НАБОРА (%d слов) ===\n  %s\n  главная: %s\n\n", $N, $A, basename($main));
    $worst = 0.0;
    foreach (glob("$A/*.html") as $f) {
        if ($f === $main) { continue; }
        $s = shingles(words($f), $N);
        $hit = count(array_intersect_key($s, $sm));
        $pct = count($s) ? round($hit / count($s) * 100, 2) : 0.0;
        $worst = max($worst, $pct);
        printf("  %-16s %5.2f%% фраз уже сказаны на главной%s\n", basename($f), $pct, $hit ? "   ($hit)" : '');
    }
    $verdict = $worst > 6.5 ? 'ПОРОГ 6.5% ПРЕВЫШЕН — набор пересказывает сам себя'
        : ($worst > 2 ? 'в пределах образца, но выше медианы 0.8% — стоит посмотреть глазами' : 'в норме образца');
    printf("\n  ХУДШАЯ СТРАНИЦА: %.2f%%   %s\n", $worst, $verdict);
    echo "STATUS " . json_encode(['worst' => $worst, 'pass' => $worst <= 6.5]) . "\n";
    exit(0);
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

<?php
declare(strict_types=1);

/**
 * Ширина словаря страницы: где сидит тошнота и чем её дешевле всего сбить.
 *
 *   php tools/zamery/slovar.php <файл|папка> [--цель=29]
 *
 * Тошнота считается как доля слов, которые в тексте уже встречались: сумма
 * частот всех значимых слов с частотой больше единицы, делённая на все слова.
 * Отсюда неочевидное следствие, ради которого замер и заведён.
 *
 * Дешевле всего править слова, встретившиеся РОВНО ДВАЖДЫ. Убрал одно из двух
 * вхождений — слово выпало из повторных целиком, и числитель упал сразу на
 * два. У слова с частотой три та же правка снимает только один. Гнаться за
 * самым частым словом бессмысленно: их единицы, а двоек на странице десятки.
 *
 * Замер нужен потому, что поле terms_total тянет в обратную сторону: оно
 * считает ВХОЖДЕНИЯ терминов, и добор повтором одного слова поднимает тошноту.
 * Образец держит и термины 22–24, и тошноту 27–29, потому что у него шире весь
 * словарь: при равной длине 341 разное значимое слово против наших 312.
 *
 * Словоформы РАЗНЫЕ: «лента» и «ленты» считаются отдельно, лемматизации нет.
 * Это рычаг — падеж и число сбивают повтор не хуже синонима.
 *
 * Токенизация взята у Parser и TextMetrics, а не своя: иначе замер спорил бы с
 * приёмкой. Плейсхолдер бренда разбирается на «brand», «name» и «en» — три
 * слова, и два из них повторные. Пятнадцать имён на странице дают под восемь
 * процентов тошноты сами по себе; у образца их столько же, поэтому разницы это
 * не создаёт, но при доводке бренда о цене стоит помнить.
 */

require_once __DIR__ . '/../../engine/src/Parser.php';
require_once __DIR__ . '/../../engine/src/StopWords.php';

const ZNACHIMOE = 3;

/** @return array{слова:list<string>,частоты:array<string,int>} */
function razobrat(string $html): array
{
    $text = Parser::fromHtml($html)->text;
    preg_match_all('/[\p{L}\p{Nd}][\p{L}\p{Nd}\-]*/u', mb_strtolower($text, 'UTF-8'), $m);
    $f = [];
    foreach ($m[0] as $w) { $f[$w] = ($f[$w] ?? 0) + 1; }
    return ['слова' => $m[0], 'частоты' => $f];
}

/** @param array<string,int> $f @return array<string,int> */
function znachimye(array $f): array
{
    $out = [];
    foreach ($f as $w => $c) {
        if (mb_strlen((string) $w, 'UTF-8') < ZNACHIMOE) { continue; }
        if (StopWords::is((string) $w)) { continue; }
        $out[(string) $w] = $c;
    }
    return $out;
}

$put = $argv[1] ?? '';
$cel = 29.0;
foreach (array_slice($argv, 2) as $a) {
    if (str_starts_with($a, '--цель=')) { $cel = (float) substr($a, strlen('--цель=')); }
}
if ($put === '' || !file_exists($put)) {
    fwrite(STDERR, "usage: php tools/zamery/slovar.php <файл|папка> [--цель=29]\n");
    exit(1);
}
$fajly = is_dir($put) ? glob(rtrim($put, '/') . '/*.html') : [$put];
sort($fajly);

foreach ($fajly as $f) {
    $r = razobrat((string) file_get_contents($f));
    $z = znachimye($r['частоты']);
    $n = count($r['слова']);
    $rep = 0;
    foreach ($z as $c) { if ($c > 1) { $rep += $c; } }
    $tosh = $n ? round($rep / $n * 100, 1) : 0.0;
    // Сколько повторных вхождений снять, чтобы дойти до цели.
    $nado = max(0, (int) ceil($rep - $cel / 100 * $n));
    $dvojki = array_keys(array_filter($z, static fn(int $c) => $c === 2));
    printf("%-14s тошнота %4.1f  слов %4d  разных значимых %3d  повторных %3d  двоек %2d\n",
        basename($f, '.html'), $tosh, $n, count($z), $rep, count($dvojki));
    if ($nado > 0) {
        printf("               до %.0f%% снять %d повторных — это %d двоек из %d\n",
            $cel, $nado, (int) ceil($nado / 2), count($dvojki));
        printf("               %s%s\n", implode(' ', array_slice($dvojki, 0, 28)),
            count($dvojki) > 28 ? ' …' : '');
    }
}

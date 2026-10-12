<?php
/**
 * Принять обложки из папки: сопоставить имена файлов с именами игр витрины,
 * обрезать в 640×480 webp и сложить под нужными слагами.
 *
 * Для случая, когда картинки добыты вручную (пресс-кит студии, сохранение из
 * браузера): складываете файлы в одну папку как есть — «Sweet Bonanza.png»,
 * «gates_of_olympus.jpg», «book-of-dead (1).webp» — а соответствие ищется по
 * нормализованному имени. Что не опознано, перечисляется, и его можно назвать
 * руками через --карта.
 *
 *   php engine/instrumenty/vzyat-oblozhki.php <папка> [--выход=dir] [--карта=файл:слаг,...]
 *
 * Выход по умолчанию — scratchpad/oblozhki-novye, НЕ рабочий каталог: перенос
 * в data-v5/oblozhki только после сверки листом (svod-oblozhek.php), иначе
 * повторится нынешняя история с чужими играми на карточках.
 */

const СЛАГИ = [
    'sweet-bonanza'       => 'Sweet Bonanza',
    'gates-of-olympus'    => 'Gates of Olympus',
    'book-of-dead'        => 'Book of Dead',
    'big-bass-bonanza'    => 'Big Bass Bonanza',
    'starburst'           => 'Starburst',
    'sugar-rush'          => 'Sugar Rush',
    'money-train-3'       => 'Money Train 3',
    'the-dog-house'       => 'The Dog House',
    'wanted-dead-or-wild' => 'Wanted Dead or a Wild',
    'starlight-princess'  => 'Starlight Princess',
    'razor-shark'         => 'Razor Shark',
    'fruit-party'         => 'Fruit Party',
];

$папка = null; $выход = __DIR__ . '/../../scratchpad/oblozhki-novye'; $карта = [];
foreach (array_slice($argv, 1) as $а) {
    if (str_starts_with($а, '--выход=')) { $выход = rtrim(substr($а, strlen('--выход=')), '/'); continue; }
    if (str_starts_with($а, '--карта=')) {
        foreach (explode(',', substr($а, strlen('--карта='))) as $пара) {
            [$ф, $с] = array_pad(explode(':', $пара, 2), 2, null);
            if ($ф && $с) { $карта[trim($ф)] = trim($с); }
        }
        continue;
    }
    if ($а[0] !== '-') { $папка = rtrim($а, '/'); }
}
if ($папка === null || !is_dir($папка)) {
    fwrite(STDERR, "usage: php engine/instrumenty/vzyat-oblozhki.php <папка> [--выход=dir] [--карта=файл:слаг,...]\n");
    exit(1);
}

/** Имя в сравнимый вид: только буквы и цифры в нижнем регистре. */
function ключ(string $с): string
{
    return preg_replace('~[^a-z0-9]+~', '', mb_strtolower($с));
}

/** Байты картинки → 640×480 webp, кадр по центру без растягивания. */
function вОбложку(string $исток, string $файл): string
{
    $src = @imagecreatefromstring((string) file_get_contents($исток));
    if (!$src) { return 'не читается как картинка'; }
    $sw = imagesx($src); $sh = imagesy($src);
    if ($sw < 240 || $sh < 180) { imagedestroy($src); return sprintf('мелкая: %d×%d', $sw, $sh); }
    $W = 640; $H = 480;
    $cw = $sw; $ch = (int) round($sw * $H / $W);
    if ($ch > $sh) { $ch = $sh; $cw = (int) round($sh * $W / $H); }
    $im = imagecreatetruecolor($W, $H);
    imagecopyresampled($im, $src, 0, 0, (int) (($sw - $cw) / 2), (int) (($sh - $ch) / 2), $W, $H, $cw, $ch);
    imagedestroy($src);
    $ок = imagewebp($im, $файл, 82);
    imagedestroy($im);
    return $ок ? '' : 'не сохраняется';
}

$поКлючу = [];
foreach (СЛАГИ as $слаг => $имя) { $поКлючу[ключ($имя)] = $слаг; $поКлючу[ключ($слаг)] = $слаг; }

if (!is_dir($выход) && !mkdir($выход, 0777, true)) { fwrite(STDERR, "не создаётся $выход\n"); exit(1); }

$файлы = glob("$папка/*.{webp,jpg,jpeg,png,gif,avif}", GLOB_BRACE) ?: [];
$взято = []; $мимо = [];
foreach ($файлы as $ф) {
    $имяФайла = basename($ф);
    $голое = preg_replace('~\s*\(\d+\)$~', '', pathinfo($имяФайла, PATHINFO_FILENAME));
    $слаг = $карта[$имяФайла] ?? $карта[$голое] ?? $поКлючу[ключ($голое)] ?? null;
    if ($слаг === null) { $мимо[] = $имяФайла; continue; }
    if (!isset(СЛАГИ[$слаг])) { $мимо[] = "$имяФайла → неизвестный слаг $слаг"; continue; }
    $беда = вОбложку($ф, "$выход/$слаг.webp");
    if ($беда !== '') { $мимо[] = "$имяФайла → $беда"; continue; }
    [$w, $h] = getimagesize("$выход/$слаг.webp");
    $взято[$слаг] = sprintf('%s → %d×%d, %d КБ', $имяФайла, $w, $h, (int) (filesize("$выход/$слаг.webp") / 1024));
}

printf("папка: %s | картинок: %d\n\n", $папка, count($файлы));
foreach (СЛАГИ as $слаг => $имя) {
    printf("%s %-22s %s\n", isset($взято[$слаг]) ? '✓' : '·', $слаг, $взято[$слаг] ?? 'нет файла');
}
if ($мимо) {
    echo "\nне опознаны (назовите через --карта=имяфайла:слаг):\n";
    foreach ($мимо as $м) { echo "  $м\n"; }
}
printf("\nвзято %d из %d → %s\n", count($взято), count(СЛАГИ), $выход);
if (count($взято) === count(СЛАГИ)) {
    echo "дальше: php engine/instrumenty/svod-oblozhek.php лист.png $выход — сверить глазом,\n";
    echo "что на каждой картинке та игра, и только после этого переносить в data-v5/oblozhki\n";
}

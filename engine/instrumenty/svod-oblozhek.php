<?php
/**
 * Контактный лист обложек: все файлы data-v5/oblozhki с подписями-именами.
 *
 * Нужен всякий раз, когда обложки меняются: проверить, что на картинке та
 * игра, чьё имя стоит в файле, может только глаз. Прошлая проверка нашла
 * десять несовпадений из двенадцати — на sweet-bonanza.webp было напечатано
 * «BOOK OF OIL» (разбор в docs/vitrina-slotov.md). Сверка глазом по этому
 * листу — условие для того, чтобы вписать имя в ОБЛОЖКИ_ПОДТВЕРЖДЕНЫ.
 *
 *   php engine/instrumenty/svod-oblozhek.php [выход.png] [каталог]
 */
$выход = $argv[1] ?? '/tmp/oblozhki.png';
$дир = rtrim($argv[2] ?? __DIR__ . '/../data-v5/oblozhki', '/');
$файлы = glob("$дир/*.{webp,jpg,jpeg,png}", GLOB_BRACE) ?: [];
sort($файлы);
if (!$файлы) { fwrite(STDERR, "нет картинок в $дир\n"); exit(1); }

$ш = 300; $в = 225; $вРяд = 4;
$ряды = (int) ceil(count($файлы) / $вРяд);
$im = imagecreatetruecolor($ш * $вРяд, $в * $ряды);
imagefill($im, 0, 0, imagecolorallocate($im, 18, 18, 24));
$подпись = imagecolorallocate($im, 255, 232, 64);
$тень = imagecolorallocate($im, 0, 0, 0);
foreach ($файлы as $i => $ф) {
    $ext = strtolower(pathinfo($ф, PATHINFO_EXTENSION));
    $src = $ext === 'webp' ? @imagecreatefromwebp($ф)
        : ($ext === 'png' ? @imagecreatefrompng($ф) : @imagecreatefromjpeg($ф));
    $x = ($i % $вРяд) * $ш; $y = intdiv($i, $вРяд) * $в;
    if ($src) {
        imagecopyresampled($im, $src, $x, $y, 0, 0, $ш, $в, imagesx($src), imagesy($src));
        imagedestroy($src);
    }
    $имя = basename($ф);
    imagestring($im, 4, $x + 7, $y + 7, $имя, $тень);
    imagestring($im, 4, $x + 6, $y + 6, $имя, $подпись);
}
imagepng($im, $выход);
printf("%d обложек → %s\n", count($файлы), $выход);
foreach ($файлы as $ф) {
    $р = @getimagesize($ф);
    printf("  %-30s %s\n", basename($ф), $р ? "{$р[0]}×{$р[1]}" : 'не читается');
}

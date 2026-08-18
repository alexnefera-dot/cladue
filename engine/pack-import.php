<?php
declare(strict_types=1);

/**
 * Сборка архива под правила импорта — с проверкой до упаковки.
 *
 *   php pack-import.php <папка-с-набором> <имя-архива> [папка-с-картинками]
 *
 * Импорт отменяется целиком, если картинку не удаётся привязать к странице, так
 * что дешевле поймать это здесь: имя файла обязано начинаться с имени своей
 * страницы (`main_img_1.webp` — только в `main.html`), файл обязан лежать в
 * `images/`, а в разметке должно стоять голое имя файла без папки.
 */

$DIR  = $argv[1] ?? '';
$NAME = $argv[2] ?? '';
$IMG  = $argv[3] ?? '';
if ($DIR === '' || $NAME === '') {
    fwrite(STDERR, "usage: pack-import.php <dir> <name> [images-dir]\n");
    exit(1);
}
if (!is_file("$DIR/main.html")) {
    fwrite(STDERR, "нет main.html — он обязателен\n");
    exit(1);
}

$errors = [];
$used   = [];
foreach (glob("$DIR/*.html") as $f) {
    $page = basename($f, '.html');
    $html = (string) file_get_contents($f);
    if (!preg_match_all('~<img[^>]+src="([^"]+)"~i', $html, $m)) { continue; }
    foreach ($m[1] as $src) {
        if (str_contains($src, '/')) {
            $errors[] = "{$page}.html: в src стоит путь «{$src}», а нужно голое имя файла";
            continue;
        }
        if (!preg_match('~^' . preg_quote($page, '~') . '_img_\d+\.[a-z0-9]+$~i', $src)) {
            $errors[] = "{$page}.html: имя «{$src}» не привязывается к странице, нужно {$page}_img_N.ext";
            continue;
        }
        $srcFile = $IMG !== '' ? "$IMG/$src" : "$DIR/images/$src";
        if (!is_file($srcFile)) {
            $errors[] = "{$page}.html: файла «{$src}» нет ни в images/, ни в переданной папке";
            continue;
        }
        $used[$src] = $srcFile;
    }
}
if ($errors) {
    echo "АРХИВ НЕ СОБРАН:\n";
    foreach ($errors as $e) { echo "  · {$e}\n"; }
    echo "STATUS " . json_encode(['ok' => false, 'errors' => count($errors)]) . "\n";
    exit(1);
}

$pack = sys_get_temp_dir() . "/pack-{$NAME}";
exec('rm -rf ' . escapeshellarg($pack));
mkdir("$pack/$NAME", 0777, true);
foreach (glob("$DIR/*.html") as $f) { copy($f, "$pack/$NAME/" . basename($f)); }
if ($used) {
    mkdir("$pack/$NAME/images", 0777, true);
    foreach ($used as $name => $srcFile) { copy($srcFile, "$pack/$NAME/images/$name"); }
}
$zip = "/tmp/{$NAME}.zip";
@unlink($zip);
exec('cd ' . escapeshellarg($pack) . ' && zip -qr ' . escapeshellarg($zip) . ' ' . escapeshellarg($NAME));

printf("→ %s\n   страниц %d, картинок %d\n", $zip, count(glob("$DIR/*.html")), count($used));
foreach ($used as $name => $_) { echo "   · images/{$name}\n"; }
echo "STATUS " . json_encode(['ok' => true, 'pages' => count(glob("$DIR/*.html")), 'images' => count($used)]) . "\n";

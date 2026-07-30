<?php
declare(strict_types=1);

/**
 * Тематическая картинка для страницы: барабаны слота с символами.
 *
 *   php make-slot-image.php <файл.webp> [тема|random] [ширина] [высота] [seed]
 *
 * Темы: fruit, egypt, space, gold. Без темы берётся случайная.
 *
 * УНИКАЛЬНОСТЬ. Каждый запуск обязан давать новую картинку, поэтому:
 *   1) seed по умолчанию берётся из random_bytes — он разный при каждом вызове;
 *   2) от seed зависит всё: тема, палитра, число и геометрия барабанов, набор и
 *      порядок символов, линия выплаты, поле бликов;
 *   3) md5 готового файла проверяется по журналу уже выданных картинок
 *      (engine/.image-ledger). Совпало — seed перебрасывается и кадр рисуется
 *      заново, до 12 попыток.
 * Seed печатается в STATUS: с ним же кадр воспроизводится байт в байт.
 */

$OUT    = $argv[1] ?? '/tmp/img/main_img_1.webp';
$THEME  = $argv[2] ?? '';
$W      = (int) ($argv[3] ?? 1200);
$H      = (int) ($argv[4] ?? 630);
$SEEDIN = $argv[5] ?? '';
$LEDGER = getenv('SLOT_IMAGE_LEDGER') ?: __DIR__ . '/.image-ledger';

$THEMES = [
    'fruit' => ['bg' => [[26, 12, 48], [86, 22, 74]],  'accent' => [255, 196, 60],  'symbols' => ['cherry', 'lemon', 'seven', 'bell', 'star']],
    'egypt' => ['bg' => [[30, 22, 10], [96, 68, 18]],  'accent' => [246, 214, 122], 'symbols' => ['pyramid', 'eye', 'scarab', 'coin', 'star']],
    'space' => ['bg' => [[8, 14, 34], [26, 48, 96]],   'accent' => [124, 214, 255], 'symbols' => ['star', 'planet', 'rocket', 'seven', 'coin']],
    'gold'  => ['bg' => [[20, 18, 14], [72, 58, 22]],  'accent' => [255, 208, 84],  'symbols' => ['seven', 'bell', 'coin', 'star', 'lemon']],
];

/** цвет двигается на ±$d, но остаётся в 0..255 */
function jitter(array $rgb, int $d): array
{
    return array_map(fn($v) => max(0, min(255, $v + mt_rand(-$d, $d))), $rgb);
}

/**
 * Акцент годится для рамки на тёмном фоне, но символ рисуется на почти белом
 * барабане: светло-жёлтый скарабей там пропадает. Поэтому яркость сбивается до
 * потолка, а оттенок остаётся прежним.
 */
function inkable(array $rgb, float $cap = 168.0): array
{
    $lum = 0.2126 * $rgb[0] + 0.7152 * $rgb[1] + 0.0722 * $rgb[2];
    if ($lum <= $cap) { return $rgb; }
    $k = $cap / $lum;
    return array_map(fn($v) => (int) max(0, min(255, $v * $k)), $rgb);
}

function roundedBox($im, int $x1, int $y1, int $x2, int $y2, int $r, int $color): void
{
    imagefilledrectangle($im, $x1 + $r, $y1, $x2 - $r, $y2, $color);
    imagefilledrectangle($im, $x1, $y1 + $r, $x2, $y2 - $r, $color);
    foreach ([[$x1 + $r, $y1 + $r], [$x2 - $r, $y1 + $r], [$x1 + $r, $y2 - $r], [$x2 - $r, $y2 - $r]] as [$cx, $cy]) {
        imagefilledellipse($im, $cx, $cy, $r * 2, $r * 2, $color);
    }
}

/** символы рисуются примитивами: это иллюстрация, а не клипарт */
function drawSymbol($im, string $kind, int $cx, int $cy, int $s, int $accent, int $dark): void
{
    // GD в PHP 8 не принимает дробные координаты, поэтому все доли размера
    // считаются заранее и целыми.
    $h = (int) ($s / 2); $q = (int) ($s / 3); $e = (int) ($s / 4); $o = (int) ($s / 6); $n = (int) ($s / 8);
    $red   = imagecolorallocate($im, 214, 58, 62);
    $green = imagecolorallocate($im, 74, 160, 84);
    $blue  = imagecolorallocate($im, 92, 152, 230);
    $white = imagecolorallocate($im, 250, 250, 252);
    imagesetthickness($im, max(2, (int) ($s / 14)));
    switch ($kind) {
        case 'cherry':
            imagefilledellipse($im, $cx - $e, $cy + $o, $h, $h, $red);
            imagefilledellipse($im, $cx + $e, $cy + $e, (int) ($s * 0.42), (int) ($s * 0.42), $red);
            imagearc($im, $cx, $cy - $q, $s, $s, 200, 340, $green);
            break;
        case 'lemon':
            imagefilledellipse($im, $cx, $cy, (int) ($s * 0.95), (int) ($s * 0.66), imagecolorallocate($im, 206, 170, 34));
            imagearc($im, $cx, $cy, (int) ($s * 0.6), (int) ($s * 0.42), 0, 360, imagecolorallocate($im, 128, 102, 18));
            break;
        case 'seven':
            imagefilledpolygon($im, [
                $cx - $q, $cy - $h, $cx + $q, $cy - $h,
                $cx + $q, $cy - $q, $cx, $cy + $h,
                $cx - $o, $cy + $h, $cx + $o, $cy - $e,
                $cx - $q, $cy - $e,
            ], $accent);
            break;
        case 'bell':
            imagefilledarc($im, $cx, $cy + $n, $s, $s, 180, 360, $accent, IMG_ARC_PIE);
            imagefilledrectangle($im, $cx - $h, $cy + $n, $cx + $h, $cy + $q, $accent);
            imagefilledellipse($im, $cx, $cy + $q + $n, (int) ($s / 4), (int) ($s / 4), $accent);
            break;
        case 'coin':
            imagefilledellipse($im, $cx, $cy, $s, $s, $accent);
            imagefilledellipse($im, $cx, $cy, (int) ($s * 0.7), (int) ($s * 0.7), imagecolorallocate($im, 214, 168, 52));
            break;
        case 'star':
            $pts = [];
            for ($i = 0; $i < 10; $i++) {
                $r = $i % 2 ? $s / 4 : $s / 2;
                $a = -M_PI / 2 + $i * M_PI / 5;
                $pts[] = (int) ($cx + $r * cos($a));
                $pts[] = (int) ($cy + $r * sin($a));
            }
            imagefilledpolygon($im, $pts, $accent);
            break;
        case 'planet':
            imagefilledellipse($im, $cx, $cy, (int) ($s * 0.7), (int) ($s * 0.7), $blue);
            imageellipse($im, $cx, $cy, $s, $q, $accent);
            break;
        case 'rocket':
            // корпус синий, а не белый: барабан светлый, белое на нём пропадает
            imagefilledpolygon($im, [$cx, $cy - $h, $cx + $e, $cy + $o, $cx - $e, $cy + $o], $blue);
            imagefilledpolygon($im, [$cx - $h, $cy + $o, $cx - $e, $cy - $n, $cx - $e, $cy + $o], $blue);
            imagefilledpolygon($im, [$cx + $h, $cy + $o, $cx + $e, $cy - $n, $cx + $e, $cy + $o], $blue);
            imagefilledellipse($im, $cx, $cy - $o, $o, $o, $white);
            imagefilledpolygon($im, [$cx - $o, $cy + $o, $cx + $o, $cy + $o, $cx, $cy + $h], $accent);
            break;
        case 'pyramid':
            imagefilledpolygon($im, [$cx, $cy - $h, $cx + $h, $cy + $q, $cx - $h, $cy + $q], $accent);
            imagefilledpolygon($im, [$cx, $cy - $h, $cx + $n, $cy + $q, $cx - $n, $cy + $q], imagecolorallocate($im, 214, 176, 88));
            break;
        case 'eye':
            imagefilledellipse($im, $cx, $cy, $s, (int) ($s * 0.62), $accent);
            imagefilledellipse($im, $cx, $cy, (int) ($s * 0.42), (int) ($s * 0.42), $white);
            imagefilledellipse($im, $cx, $cy, $q, $q, $dark);
            break;
        case 'scarab':
            imagefilledellipse($im, $cx, $cy, (int) ($s * 0.72), $s, $accent);
            imagefilledellipse($im, $cx, $cy - $q, (int) ($s * 0.44), (int) ($s * 0.44), $accent);
            imageline($im, $cx, $cy - $o, $cx, $cy + $h, $dark);
            imagearc($im, $cx, $cy - $o, $s, $s, 200, 340, $dark);
            break;
    }
}

/**
 * Один кадр по одному seed. Возвращает данные webp и описание того, что выпало.
 */
function render(array $THEMES, string $wantTheme, int $W, int $H, string $seed): array
{
    mt_srand(crc32($seed));

    $theme = isset($THEMES[$wantTheme]) ? $wantTheme : array_rand($THEMES);
    $T     = $THEMES[$theme];

    $bg0    = jitter($T['bg'][0], 12);
    $bg1    = jitter($T['bg'][1], 18);
    $accRGB = jitter($T['accent'], 22);

    $im = imagecreatetruecolor($W, $H);
    imageantialias($im, true);

    // Фон: градиент идёт сверху вниз или снизу вверх, иногда наклонными полосами.
    // Наклон рисуется удлинённым диапазоном, иначе по углам остаются чёрные клинья.
    if (mt_rand(0, 1)) { [$bg0, $bg1] = [$bg1, $bg0]; }
    $slant = mt_rand(0, 1) ? (int) ($W * (mt_rand(6, 16) / 100)) : 0;
    $from  = -abs($slant); $to = $H + abs($slant);
    for ($y = $from; $y <= $to; $y++) {
        $t = ($y - $from) / max(1, $to - $from);
        $c = imagecolorallocate($im,
            (int) ($bg0[0] + ($bg1[0] - $bg0[0]) * $t),
            (int) ($bg0[1] + ($bg1[1] - $bg0[1]) * $t),
            (int) ($bg0[2] + ($bg1[2] - $bg0[2]) * $t));
        imageline($im, 0, $y, $W, $y - $slant, $c);
    }

    $accent = imagecolorallocate($im, ...$accRGB);
    $ink    = imagecolorallocate($im, ...inkable($accRGB));
    $dark   = imagecolorallocate($im, 12, 12, 20);

    // блики фона — количество и положение свои у каждого seed
    $sparks = mt_rand(55, 145);
    for ($i = 0; $i < $sparks; $i++) {
        $r = mt_rand(1, 4);
        $g = imagecolorallocatealpha($im, 255, 255, 255, mt_rand(78, 118));
        imagefilledellipse($im, mt_rand(0, $W), mt_rand(0, $H), $r, $r, $g);
    }

    // корпус автомата
    $padX   = mt_rand(8, 13) / 100;
    $padTop = mt_rand(11, 17) / 100;
    $bodyX1 = (int) ($W * $padX);        $bodyX2 = (int) ($W * (1 - $padX));
    $bodyY1 = (int) ($H * $padTop);      $bodyY2 = (int) ($H * (1 - $padTop * 0.9));
    $radius = mt_rand(18, 40);
    roundedBox($im, $bodyX1 - 8, $bodyY1 - 8, $bodyX2 + 8, $bodyY2 + 8, $radius + 6, $accent);
    roundedBox($im, $bodyX1, $bodyY1, $bodyX2, $bodyY2, $radius,
        imagecolorallocate($im, ...jitter([24, 22, 38], 10)));

    // барабанов три или пять — как на живых автоматах
    $reels  = mt_rand(0, 1) ? 3 : 5;
    $gap    = $reels === 3 ? mt_rand(20, 34) : mt_rand(12, 20);
    $reelW  = (int) (($bodyX2 - $bodyX1 - ($reels + 1) * $gap) / $reels);
    $inset  = mt_rand(38, 56);
    $reelY1 = $bodyY1 + $inset;
    $reelY2 = $bodyY2 - $inset;
    $reelR  = mt_rand(10, 24);

    // набор символов: перемешивается и режется под число барабанов, с повтором,
    // если барабанов больше, чем символов в теме
    $pool = $T['symbols'];
    shuffle($pool);
    $syms = [];
    for ($i = 0; $i < $reels; $i++) { $syms[] = $pool[$i % count($pool)]; }

    $midY = (int) (($reelY1 + $reelY2) / 2);
    for ($i = 0; $i < $reels; $i++) {
        $x1 = $bodyX1 + $gap + $i * ($reelW + $gap);
        $x2 = $x1 + $reelW;
        roundedBox($im, $x1, $reelY1, $x2, $reelY2, $reelR,
            imagecolorallocate($im, ...jitter([244, 245, 250], 8)));
        // затемнение сверху и снизу — ощущение вращения
        $fade = mt_rand(18, 34);
        for ($k = 0; $k < $fade; $k++) {
            // alpha в GD — 0..127, поэтому затемнение идёт от почти прозрачного к пустому
            $a = imagecolorallocatealpha($im, 20, 18, 30, min(127, 100 + $k));
            imageline($im, $x1 + 6, $reelY1 + 12 + $k, $x2 - 6, $reelY1 + 12 + $k, $a);
            imageline($im, $x1 + 6, $reelY2 - 12 - $k, $x2 - 6, $reelY2 - 12 - $k, $a);
        }
        // Символ чуть гуляет по высоте — барабан как будто не дощёлкал. Размер
        // ограничен и высотой окна: у вишни и колокольчика есть вынос вверх,
        // иначе он уезжает под затемнение.
        $drift = mt_rand(-(int) (($reelY2 - $reelY1) * 0.04), (int) (($reelY2 - $reelY1) * 0.04));
        $size  = (int) min($reelW * (mt_rand(46, 60) / 100), ($reelY2 - $reelY1) * 0.42);
        drawSymbol($im, $syms[$i], (int) (($x1 + $x2) / 2), $midY + $drift, $size, $ink, $dark);
    }

    // линия выплаты: прямая, ломаная или диагональ
    imagesetthickness($im, mt_rand(3, 6));
    $pl   = imagecolorallocatealpha($im, ...array_merge($accRGB, [mt_rand(30, 55)]));
    $lx1  = $bodyX1 + 14; $lx2 = $bodyX2 - 14;
    $amp  = (int) (($reelY2 - $reelY1) * (mt_rand(8, 22) / 100));
    switch (mt_rand(0, 2)) {
        case 0:
            imageline($im, $lx1, $midY, $lx2, $midY, $pl);
            break;
        case 1:
            imageline($im, $lx1, $midY - $amp, (int) (($lx1 + $lx2) / 2), $midY + $amp, $pl);
            imageline($im, (int) (($lx1 + $lx2) / 2), $midY + $amp, $lx2, $midY - $amp, $pl);
            break;
        default:
            imageline($im, $lx1, $midY - $amp, $lx2, $midY + $amp, $pl);
    }

    ob_start();
    imagewebp($im, null, mt_rand(82, 90));
    $data = (string) ob_get_clean();
    imagedestroy($im);

    return [$data, ['theme' => $theme, 'reels' => $reels, 'symbols' => $syms, 'sparks' => $sparks]];
}

/** журнал уже выданных картинок: одна md5-строка на кадр */
$seen = is_file($LEDGER)
    ? array_flip(array_filter(array_map('trim', (array) file($LEDGER))))
    : [];

$data = null; $info = []; $seed = ''; $tries = 0;
for ($attempt = 0; $attempt < 12; $attempt++) {
    $tries = $attempt + 1;
    // Пустой seed на входе — берём случайный: два запуска подряд не совпадут.
    $seed = $attempt === 0 && $SEEDIN !== '' ? $SEEDIN : bin2hex(random_bytes(8));
    [$data, $info] = render($THEMES, $THEME, $W, $H, $seed);
    $hash = md5($data);
    if (!isset($seen[$hash])) {
        @file_put_contents($LEDGER, $hash . "\n", FILE_APPEND | LOCK_EX);
        break;
    }
    // такой кадр уже выдавали — перебрасываем seed
    $data = null;
}
if ($data === null) {
    fwrite(STDERR, "не удалось получить новый кадр за 12 попыток — проверьте {$LEDGER}\n");
    exit(1);
}

if (!is_dir(dirname($OUT))) { mkdir(dirname($OUT), 0777, true); }
file_put_contents($OUT, $data);

printf("→ %s (%s, %d барабанов: %s, %dx%d, %d байт, попыток %d)\n",
    $OUT, $info['theme'], $info['reels'], implode('/', $info['symbols']), $W, $H, strlen($data), $tries);
echo "STATUS " . json_encode([
    'file' => $OUT, 'theme' => $info['theme'], 'seed' => $seed,
    'md5' => md5($data), 'reels' => $info['reels'], 'symbols' => $info['symbols'],
], JSON_UNESCAPED_UNICODE) . "\n";

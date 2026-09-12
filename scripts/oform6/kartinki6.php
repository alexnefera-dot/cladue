<?php
// kartinki6.php — графика второй системы: дуотон-абстракция и журнальная подпись.
// php kartinki6.php <папка> --сид=N --тема=N
declare(strict_types=1);
require __DIR__ . '/temy6.php';
mb_internal_encoding('UTF-8');

const FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf';
const FR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';
const S = 2;   // рисуем крупнее и ужимаем

// страница => [метка, заголовок, подзаголовок, мотив по умолчанию]
$РАЗДЕЛЫ = [
    'main' => ['Главная', 'Официальный сайт', 'Игры, бонусы и выплаты', 'grid'],
    'obzor' => ['Обзор', 'Разбор площадки', 'Условия, лимиты, отзывы', 'arc'],
    'promo' => ['Акции', 'Промо и коды', 'Фриспины, кэшбэк, турниры', 'diagonal'],
    'news' => ['Новости', 'Что нового', 'Обновления и анонсы', 'dots'],
    'info' => ['Информация', 'Правила и лимиты', 'Лицензия, платежи, поддержка', 'arc'],
    'partnery' => ['Партнёрам', 'Партнёрская программа', 'Модели выплат и статистика', 'nodes'],
    'app' => ['Приложение', 'Мобильная версия', 'Android, iOS, установка', 'iso'],
    'bonus' => ['Бонусы', 'Бонусная программа', 'Вейджер, сроки, условия', 'waves'],
    'registracia' => ['Регистрация', 'Создание аккаунта', 'Данные, подтверждение, вход', 'frame'],
    'slots' => ['Слоты', 'Каталог игр', 'Провайдеры, RTP, демо', 'bars'],
    'vhod' => ['Вход', 'Личный кабинет', 'Логин, пароль, сессия', 'key'],
    'zerkalo' => ['Зеркало', 'Рабочий доступ', 'Тот же аккаунт и баланс', 'rings'],
    'about' => ['О нас', 'О площадке', 'Команда, принципы, лицензия', 'mesh'],
    'contacts' => ['Контакты', 'Связь и поддержка', 'Чат, почта, время ответа', 'nodes'],
    'privacy' => ['Данные', 'Конфиденциальность', 'Хранение и защита', 'frame'],
];

// ------------------------------------------------------------------ цвет
function rgbl(array $c, float $k): array { return [min(255, $c[0] * $k), min(255, $c[1] * $k), min(255, $c[2] * $k)]; }
function цв($im, array $rgb, float $op = 1.0): int {
    $f = fn($v) => (int) max(0, min(255, round($v)));
    return imagecolorallocatealpha($im, $f($rgb[0]), $f($rgb[1]), $f($rgb[2]), (int) round((1 - max(0, min(1, $op))) * 127));
}
function микс(array $a, array $b, float $t): array { return [$a[0] + ($b[0] - $a[0]) * $t, $a[1] + ($b[1] - $a[1]) * $t, $a[2] + ($b[2] - $a[2]) * $t]; }

// ------------------------------------------------------------------ мотивы
function мотив($im, string $вид, int $w, int $h, array $A, array $B, array $L, int $seed): void {
    mt_srand($seed);
    switch ($вид) {
        case 'grid':
            $шаг = (int) ($h / 7);
            for ($y = 0; $y < $h + $шаг; $y += $шаг) {
                for ($x = 0; $x < $w + $шаг; $x += $шаг) {
                    $d = 1 - min(1, hypot($x - $w * .72, $y - $h * .3) / ($w * .8));
                    $op = .04 + .30 * pow($d, 2) + mt_rand(0, 6) / 100;
                    imagefilledrectangle($im, $x + 2, $y + 2, $x + $шаг - 6, $y + $шаг - 6, цв($im, $L, $op));
                }
            }
            break;
        case 'waves':
            for ($i = 0; $i < 7; $i++) {
                $pts = []; $база = $h * (.22 + $i * .11); $амп = $h * (.16 - $i * .012); $ф = mt_rand(0, 300) / 100;
                for ($x = 0; $x <= $w; $x += 10) { $pts[] = $x; $pts[] = $база + sin($x / $w * 6.28 * (1.1 + $i * .3) + $ф) * $амп; }
                $pts[] = $w; $pts[] = $h; $pts[] = 0; $pts[] = $h;
                imagefilledpolygon($im, array_map('intval', $pts), цв($im, микс($A, $L, ($i + 1) / 7), .26 + $i * .05));
            }
            break;
        case 'iso':
            $s = (int) ($h / 8); $ряд = 0;
            for ($y = -$s; $y < $h + $s * 2; $y += $s) {
                $сдвиг = ($ряд++ % 2) ? $s : 0;
                for ($x = -$s; $x < $w + $s; $x += $s * 2) {
                    $cx = $x + $сдвиг; $cy = $y; $op = .05 + .28 * (1 - $cx / $w) + mt_rand(0, 8) / 100;
                    imagefilledpolygon($im, [(int)$cx, (int)($cy - $s * .5), (int)($cx + $s), (int)$cy, (int)$cx, (int)($cy + $s * .5), (int)($cx - $s), (int)$cy], цв($im, $L, $op));
                    imagefilledpolygon($im, [(int)$cx, (int)($cy + $s * .5), (int)($cx + $s), (int)$cy, (int)($cx + $s), (int)($cy + $s * .8), (int)$cx, (int)($cy + $s * 1.3)], цв($im, $B, .12));
                }
            }
            break;
        case 'rings':
            $cx = $w * .74; $cy = $h * .42;
            for ($r = (int) ($h * 1.0); $r > 20; $r -= (int) ($h / 22)) {
                imagesetthickness($im, 3);
                imagearc($im, (int)$cx, (int)$cy, $r * 2, $r * 2, 0, 360, цв($im, $L, .10 + .5 * (1 - $r / ($h * 1.0))));
            }
            imagesetthickness($im, 1);
            for ($i = 0; $i < 12; $i++) {
                $a = mt_rand(0, 628) / 100; $rr = mt_rand((int) ($h * .25), (int) ($h * .95));
                imagefilledellipse($im, (int) ($cx + cos($a) * $rr), (int) ($cy + sin($a) * $rr), 14, 14, цв($im, $L, .85));
            }
            break;
        case 'bars':
            $n = 22; $bw = $w / $n;
            for ($i = 0; $i < $n; $i++) {
                $hh = $h * (.12 + .78 * pow(sin(($i + mt_rand(0, 30) / 10) / $n * 3.14), 1.6));
                imagefilledrectangle($im, (int) ($i * $bw + 4), (int) ($h - $hh), (int) (($i + 1) * $bw - 6), $h, цв($im, микс($L, $B, $i / $n), .16 + .5 * ($hh / $h)));
            }
            break;
        case 'diagonal':
            $ш = (int) ($h / 9);
            for ($x = -$h; $x < $w + $h; $x += $ш * 2) {
                $op = .08 + .34 * (1 - abs(($x - $w * .5) / $w));
                imagefilledpolygon($im, [$x, 0, $x + $ш, 0, $x + $ш - $h, $h, $x - $h, $h], цв($im, $L, $op));
            }
            break;
        case 'dots':
            $шаг = (int) ($h / 16);
            for ($y = $шаг; $y < $h; $y += $шаг) for ($x = $шаг; $x < $w; $x += $шаг) {
                $d = 1 - min(1, hypot($x - $w * .78, $y - $h * .28) / ($w * .75));
                $r = max(1, $шаг * .48 * pow($d, 1.4));
                imagefilledellipse($im, $x, $y, (int) ($r * 2), (int) ($r * 2), цв($im, $L, .18 + .55 * $d));
            }
            break;
        case 'arc':
            $cx = $w * .82; $cy = $h * .95;
            for ($i = 8; $i >= 1; $i--) {
                $r = (int) ($h * .26 * $i);
                imagefilledarc($im, (int)$cx, (int)$cy, $r * 2, $r * 2, 180, 360, цв($im, микс($A, $L, $i / 9), .14 + $i * .05), IMG_ARC_PIE);
            }
            imagesetthickness($im, 6);
            for ($i = 1; $i <= 8; $i += 2) {
                $r = (int) ($h * .26 * $i);
                imagearc($im, (int)$cx, (int)$cy, $r * 2, $r * 2, 180, 360, цв($im, $L, .5));
            }
            imagesetthickness($im, 1);
            break;
        case 'nodes':
            $узлы = [];
            for ($i = 0; $i < 16; $i++) $узлы[] = [mt_rand(40, $w - 40), mt_rand(40, $h - 40)];
            imagesetthickness($im, 4);
            foreach ($узлы as $i => $u) foreach ($узлы as $j => $v) {
                if ($j <= $i) continue;
                $d = hypot($u[0] - $v[0], $u[1] - $v[1]);
                if ($d < $w * .34) imageline($im, $u[0], $u[1], $v[0], $v[1], цв($im, $L, .62 * (1 - $d / ($w * .34))));
            }
            imagesetthickness($im, 1);
            foreach ($узлы as $u) { imagefilledellipse($im, $u[0], $u[1], 26, 26, цв($im, $L, .95)); imagefilledellipse($im, $u[0], $u[1], 60, 60, цв($im, $L, .22)); }
            break;
        case 'frame':
            for ($i = 0; $i < 9; $i++) {
                $m = 20 + $i * (int) ($h / 16);
                imagesetthickness($im, 3);
                imagerectangle($im, $m, (int) ($m * .55), $w - $m, $h - (int) ($m * .55), цв($im, $L, .48 - $i * .045));
            }
            imagesetthickness($im, 1);
            break;
        case 'key':
            $cx = $w * .76; $cy = $h * .45; imagesetthickness($im, 10);
            for ($i = 0; $i < 5; $i++) imagearc($im, (int)$cx, (int)$cy, (int) ($h * (.3 + $i * .16)), (int) ($h * (.3 + $i * .16)), 30 + $i * 20, 300 + $i * 20, цв($im, $L, .5 - $i * .07));
            imagesetthickness($im, 14);
            imageline($im, (int) ($cx - $w * .42), (int) ($cy + $h * .18), (int) ($cx - $w * .06), (int) ($cy + $h * .18), цв($im, $L, .55));
            imagesetthickness($im, 1);
            break;
        default: // mesh
            imagesetthickness($im, 3);
            for ($i = 0; $i <= 12; $i++) {
                imageline($im, 0, (int) ($h * $i / 12), $w, (int) ($h * ($i + mt_rand(-2, 2)) / 12), цв($im, $L, .34));
                imageline($im, (int) ($w * $i / 12), 0, (int) ($w * ($i + mt_rand(-2, 2)) / 12), $h, цв($im, $L, .30));
            }
            imagesetthickness($im, 1);
            for ($i = 0; $i <= 12; $i += 2) for ($j = 0; $j <= 12; $j += 2)
                imagefilledellipse($im, (int) ($w * $i / 12), (int) ($h * $j / 12), 12, 12, цв($im, $L, .55));
    }
}

// ------------------------------------------------------------------ подписи
function размер(float $s, string $f, string $t): array { $b = imagettfbbox($s, 0, $f, $t); return [abs($b[4] - $b[0]), abs($b[5] - $b[1])]; }
function текст($im, float $x, float $y, float $s, array $c, string $f, string $t, float $op = 1, float $tracking = 0): void {
    if ($tracking == 0) { imagettftext($im, $s, 0, (int) $x, (int) $y, цв($im, $c, $op), $f, $t); return; }
    foreach (preg_split('//u', $t, -1, PREG_SPLIT_NO_EMPTY) as $ch) {
        imagettftext($im, $s, 0, (int) $x, (int) $y, цв($im, $c, $op), $f, $ch);
        $x += размер($s, $f, $ch)[0] + $tracking;
    }
}
function подписи($im, int $w, int $h, string $метка, string $заг, string $под, array $светлый, array $акц, bool $полоса = false): void {
    $pad = (int) ($h * ($полоса ? .22 : .12));
    // затемнение снизу — под текст
    for ($y = (int) ($h * .45); $y < $h; $y++) {
        $t = ($y - $h * .45) / ($h * .55);
        imageline($im, 0, $y, $w, $y, цв($im, [0, 0, 0], .70 * pow($t, 1.25)));
    }
    $x = $pad;
    $sМетка = $h * .042; $sЗаг = $h * ($полоса ? .16 : .115); $sПод = $h * .046;
    while ($sЗаг > 18 && размер($sЗаг, FB, $заг)[0] > $w - $pad * 2) $sЗаг -= 2;
    $yЗаг = $h - $pad - ($полоса ? 0 : $sПод * 1.9);
    // линия над заголовком
    imagefilledrectangle($im, $x, (int) ($yЗаг - $sЗаг * 1.5), $x + (int) ($w * .10), (int) ($yЗаг - $sЗаг * 1.5) + 5, цв($im, $акц, 1));
    текст($im, $x, $yЗаг - $sЗаг * 1.5 - 16, $sМетка, $светлый, FR, mb_strtoupper($метка), .85, $sМетка * .22);
    текст($im, $x, $yЗаг, $sЗаг, [255, 255, 255], FB, $заг);
    if (!$полоса) текст($im, $x, $yЗаг + $sПод * 1.75, $sПод, [255, 255, 255], FR, $под, .82);
}

// ------------------------------------------------------------------ холсты
function основа(int $w, int $h, array $т, string $вид, int $seed, float $ярче = 1.0) {
    $im = imagecreatetruecolor($w, $h); imagealphablending($im, true);
    $A = v6rgb($т['тон'], .62, min(.42, .16 * $ярче)); $B = v6rgb($т['тон2'], .58, min(.55, .34 * $ярче)); $L = v6rgb($т['тон2'], .70, .62);
    for ($y = 0; $y < $h; $y++) {   // диагональный дуотон-градиент
        $c = микс($A, $B, $y / $h);
        imageline($im, 0, $y, $w, $y, цв($im, $c));
    }
    for ($x = 0; $x < $w; $x += 2) imageline($im, $x, 0, $x + 1, $h, цв($im, rgbl($A, .8), .18 * (1 - $x / $w)));
    мотив($im, $вид, $w, $h, $A, $B, $L, $seed);
    return [$im, $L, v6rgb($т['тон'], .9, .62)];
}
function сохранить($im, int $w, int $h, string $file): void {
    $out = imagecreatetruecolor($w, $h);
    imagecopyresampled($out, $im, 0, 0, 0, 0, $w, $h, imagesx($im), imagesy($im));
    imagedestroy($im);
    // виньетка по краям
    $b = (int) ($h * .16);
    for ($i = 0; $i < $b; $i++) { $op = .32 * pow(1 - $i / $b, 2);
        imageline($out, 0, $i, $w, $i, цв($out, [0, 0, 0], $op)); imageline($out, 0, $h - 1 - $i, $w, $h - 1 - $i, цв($out, [0, 0, 0], $op)); }
    imagewebp($out, $file, 84); imagedestroy($out);
}
/** Фон под HTML-текст: та же абстракция, но без подписи (текст даёт страница). */
function фоновая(string $file, array $т, array $разд, int $seed): void {
    $w = 1200; $h = 520;
    [$im, $L, $акц] = основа($w * S, $h * S, $т, $разд[3], $seed, 1.55);
    for ($y = 0; $y < $h * S; $y++) {   // мягкое затемнение: мотив виден, текст читается
        imageline($im, 0, $y, $w * S, $y, цв($im, [0, 0, 0], .10 + .26 * ($y / ($h * S))));
    }
    сохранить($im, $w, $h, $file);
}
function ведущая(string $file, array $т, array $разд, int $seed): string {
    $w = 1200; $h = 630;
    [$im, $L, $акц] = основа($w * S, $h * S, $т, $разд[3], $seed);
    подписи($im, $w * S, $h * S, $разд[0], $разд[1], $разд[2], $L, $акц);
    сохранить($im, $w, $h, $file);
    return "{$разд[1]} — {$разд[2]}";
}
function полоса(string $file, array $т, array $разд, int $seed, string $вид): string {
    $w = 1200; $h = 240;
    [$im, $L, $акц] = основа($w * S, $h * S, $т, $вид, $seed + 77);
    подписи($im, $w * S, $h * S, $разд[0], $разд[2], '', $L, $акц, true);
    сохранить($im, $w, $h, $file);
    return "{$разд[2]} — {$разд[0]}";
}
function квадрат(string $file, array $т, array $разд, int $seed, string $вид): string {
    $w = 760; $h = 760;
    [$im, $L, $акц] = основа($w * S, $h * S, $т, $вид, $seed + 131);
    подписи($im, $w * S, $h * S, $разд[0], $разд[1], $разд[2], $L, $акц);
    сохранить($im, $w, $h, $file);
    return "{$разд[1]} — {$разд[0]}";
}

// ------------------------------------------------------------------ вставка в страницу
function ключРаздела(string $стр): array {
    global $РАЗДЕЛЫ;
    return $РАЗДЕЛЫ[$стр] ?? ['Раздел', 'Информация', 'Подробности', 'grid'];
}
function точка(string $html): int {
    $поз = 0;
    for ($i = 0; $i < 3; $i++) {   // пропускаем подряд идущие короткие вводные абзацы
        if (!preg_match('/\G\s*<p>[^<]{1,70}<\/p>\s*/u', $html, $m, 0, $поз)) break;
        $поз += strlen($m[0]);
    }
    return $поз;
}
/** Первый блок страницы: h2 + следующий абзац (для «фона», «плитки», «дуэта»). */
function первыйБлок(string $html, int $от): array {
    $p = strpos($html, '<h2', $от);
    if ($p === false || $p > $от + 800) return [$от, $от];   // заголовок далеко — блок не оборачиваем
    $e = strpos($html, '</p>', $p);
    return [$p, $e === false ? strpos($html, '</h2>', $p) + 5 : $e + 4];
}
function вставитьКартинки(string $html, string $стр, array $т, string $dir, int $seed, int &$счёт): string {
    $разд = ключРаздела($стр);
    $вед = "{$стр}_img_1.webp";
    if ($т['картинка'] === 'фон') фоновая("$dir/images/$вед", $т, $разд, $seed);
    else ведущая("$dir/images/$вед", $т, $разд, $seed);
    $alt = "{$разд[1]} — {$разд[2]}";
    $счёт = 1;
    $акц = $т['акцент']; $п2 = $т['подложка2']; $лин = $т['линия'];
    $img = fn(string $file, string $доп, string $a = '') => "<img src=\"images/$file\" alt=\"" . ($a ?: $alt) . "\" loading=\"lazy\" style=\"display:block;width:100%;$доп\">";
    $от = точка($html);
    switch ($т['картинка']) {
        case 'фон':
            [$b1, $b2] = первыйБлок($html, $от);
            if ($b1 === $b2) {   // заголовка рядом нет — ставим обычную ведущую с подписью
                ведущая("$dir/images/$вед", $т, $разд, $seed);
                return substr($html, 0, $от) . "<figure style=\"margin:0 0 26px\">" . $img($вед, "height:auto;border-radius:2px") . "</figure>\n" . substr($html, $от);
            }
            $блок = substr($html, $b1, $b2 - $b1);
            $обёртка = "<div style=\"margin:0 0 30px;padding:34px 30px;background-image:url('images/$вед');background-size:cover;background-position:center;color:#fff;border-left:5px solid $акц;border-radius:2px\">$блок</div>\n";
            return substr($html, 0, $b1) . $обёртка . substr($html, $b2);
        case 'плитка':
            $кв = "{$стр}_img_2.webp"; квадрат("$dir/images/$кв", $т, $разд, $seed, $т['мотив']); $счёт = 2;
            [$b1, $b2] = первыйБлок($html, $от);
            $блок = $b1 === $b2 ? '' : substr($html, $b1, $b2 - $b1);
            $сетка = "<div style=\"display:grid;grid-template-columns:minmax(200px,32%) 1fr;gap:26px;align-items:start;margin:0 0 28px\"><figure style=\"margin:0\">" . $img($кв, "height:auto;border-radius:2px") . "</figure><div>$блок</div></div>\n";
            return $b1 === $b2 ? substr($html, 0, $от) . $сетка . substr($html, $от)
                               : substr($html, 0, $b1) . $сетка . substr($html, $b2);
        case 'панорама':
            return substr($html, 0, $от) . "<figure style=\"margin:0 0 30px;overflow:hidden;border-radius:2px\">" . $img($вед, "max-height:230px;object-fit:cover;object-position:center 40%") . "</figure>\n" . substr($html, $от);
        case 'край':
            return substr($html, 0, $от) . "<figure style=\"margin:0 0 26px\">" . $img($вед, "height:auto;clip-path:polygon(0 0,100% 0,100% 88%,0 100%)") . "</figure>\n" . substr($html, $от);
        case 'дуэт':
            $кв = "{$стр}_img_2.webp"; квадрат("$dir/images/$кв", $т, $разд, $seed, $т['мотив']); $счёт = 2;
            return substr($html, 0, $от) . "<div style=\"display:grid;grid-template-columns:1.6fr 1fr;gap:14px;margin:0 0 28px\"><figure style=\"margin:0\">" . $img($вед, "height:100%;object-fit:cover;border-radius:2px") . "</figure><figure style=\"margin:0\">" . $img($кв, "height:100%;object-fit:cover;border-radius:2px") . "</figure></div>\n" . substr($html, $от);
        case 'врезка':
            $кв = "{$стр}_img_2.webp"; квадрат("$dir/images/$кв", $т, $разд, $seed, $т['мотив']); $счёт = 2;
            $сн = "<img src=\"images/$кв\" alt=\"$alt\" loading=\"lazy\" style=\"float:right;width:38%;max-width:330px;margin:6px 0 16px 26px;border-radius:2px\">";
            $p = strpos($html, '<p', $от);
            if ($p === false) return substr($html, 0, $от) . $сн . substr($html, $от);
            $html = substr($html, 0, $p) . $сн . substr($html, $p);
            $e = strpos($html, '</p>', $p + strlen($сн)); $e = $e === false ? false : strpos($html, '</p>', $e + 4);
            return $e === false ? $html : substr($html, 0, $e + 4) . '<div style="clear:both"></div>' . substr($html, $e + 4);
        case 'лесенка':
            return substr($html, 0, $от) . "<figure style=\"margin:0 0 34px;padding:0 0 14px 14px;border-left:3px solid $акц;border-bottom:3px solid $лин\">" . $img($вед, "height:auto;border-radius:2px;box-shadow:-14px 14px 0 $п2") . "</figure>\n" . substr($html, $от);
        default: // разделители: ведущая сверху + узкие полосы перед разделами
            $html = substr($html, 0, $от) . "<figure style=\"margin:0 0 28px\">" . $img($вед, "height:auto;border-radius:2px") . "</figure>\n" . substr($html, $от);
            $позиции = [];
            foreach (['grid', 'diagonal', 'dots'] as $i => $вид) {
                $n = 0;
                foreach (['<h2', '<h2', '<h2'] as $_) {}
                $смещ = 0; $найдено = 0;
                while (($p = strpos($html, '<h2', $смещ)) !== false) {
                    $найдено++; $смещ = $p + 3;
                    if ($найдено === 3 + $i * 3) { $позиции[$p] = $вид; break; }
                }
            }
            krsort($позиции); $k = 2;
            $вставки = [];
            foreach ($позиции as $поз => $вид) { $вставки[$поз] = $вид; }
            $файлы = [];
            foreach (array_reverse(array_keys($вставки)) as $поз) {
                $file = "{$стр}_img_{$k}.webp";
                полоса("$dir/images/$file", $т, $разд, $seed + $k * 17, $вставки[$поз]);
                $файлы[$поз] = $file; $k++;
            }
            $счёт = $k - 1;
            krsort($файлы);
            foreach ($файлы as $поз => $file) {
                $сн = "<figure style=\"margin:30px 0 26px\"><img src=\"images/$file\" alt=\"$alt\" loading=\"lazy\" style=\"display:block;width:100%;max-height:140px;object-fit:cover;border-radius:2px\"></figure>\n";
                $html = substr($html, 0, $поз) . $сн . substr($html, $поз);
            }
            return $html;
    }
}

// ------------------------------------------------------------------ CLI
if (PHP_SAPI === 'cli' && realpath($argv[0] ?? '') === __FILE__) {
    $арг = array_slice($argv, 1); $dir = rtrim(array_shift($арг) ?? '', '/');
    $seed = 1; $номер = 1;
    foreach ($арг as $a) {
        if (preg_match('/^--сид=(\d+)$/u', $a, $m)) $seed = (int) $m[1];
        if (preg_match('/^--тема=(\d+)$/u', $a, $m)) $номер = (int) $m[1];
    }
    if (!is_dir($dir)) { fwrite(STDERR, "нет папки $dir\n"); exit(2); }
    $т = v6Tema($номер);
    @mkdir("$dir/images");
    foreach (glob("$dir/*.html") as $f) {
        $стр = basename($f, '.html'); $html = file_get_contents($f);
        if (strpos($html, "{$стр}_img_1.webp") !== false) { echo "$стр: уже есть\n"; continue; }
        $счёт = 0;
        $html = вставитьКартинки($html, $стр, $т, $dir, $seed + (crc32($стр) % 997), $счёт);
        file_put_contents($f, $html);
        echo "$стр: {$т['картинка']}, картинок $счёт\n";
    }
}

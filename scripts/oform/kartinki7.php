<?php
// kartinki7.php — картинки третьей системы: та же дуотон-абстракция, но расстановка
// под размеченный контент (герой, витрина слотов, разделы, FAQ).
// php kartinki7.php <папка комплекта> --тема=N --сид=N
declare(strict_types=1);
require __DIR__ . '/../oform6/kartinki6.php';
require __DIR__ . '/temy7.php';
require __DIR__ . '/grafika7.php';

/** Палитра картинок берётся от акцента темы — графика и стили одного тона. */
function v7Граф(array $т): array { return ['тон' => $т['тон'], 'тон2' => $т['тон2']]; }

/** Баннер раздела: предметная сцена в тоне комплекта плюс журнальная подпись. */
function v7Баннер(string $file, array $т, string $стр, array $разд, int $w, int $h, int $seed, string $вид = 'ведущая'): void {
    $ярче = $вид === 'фон' ? 1.5 : 1.0;
    [$im, $свет, $акц] = g7Сцена($w, $h, $т['тон'], $т['тон2'], g7СимволРаздела($стр, $т['сюжет'] ?? 0), $seed, $ярче, $т['раскладка'] ?? 'справа');
    if ($вид === 'фон') {                       // под HTML-текст: без подписи и темнее
        for ($y = 0; $y < $h * G7; $y++) {
            imageline($im, 0, $y, $w * G7, $y, g7c($im, [0, 0, 0], .12 + .28 * ($y / ($h * G7))));
        }
    } elseif ($вид === 'полоса') {
        подписи($im, $w * G7, $h * G7, $разд[0], $разд[2], '', $свет, $акц, true);
    } else {
        подписи($im, $w * G7, $h * G7, $разд[0], $разд[1], $разд[2], $свет, $акц);
    }
    сохранить($im, $w, $h, $file);
}

/** Названия игр в карточках страницы — по ним рисуются плитки. */
function v7Игры(string $html): array {
    preg_match_all('~class="slot-name"[^>]*>\s*([^<]{2,60}?)\s*<~u', $html, $m);
    return $m[1] ?? [];
}

/** Конец блока, открытого тегом на позиции $откр (учитывает вложенность). */
function v7Конец(string $h, int $откр): int {
    if (!preg_match('~^<([a-z0-9]+)~i', substr($h, $откр, 20), $m)) return -1;
    $тег = strtolower($m[1]); $глуб = 0; $поз = $откр;
    while (preg_match('~<(/?)' . $тег . '\b[^>]*>~i', $h, $mm, PREG_OFFSET_CAPTURE, $поз)) {
        $поз = $mm[0][1] + strlen($mm[0][0]);
        $глуб += $mm[1][0] === '/' ? -1 : 1;
        if ($глуб === 0) return $поз;
    }
    return -1;
}

function v7Фигура(string $файл, string $подпись, string $класс = 'k7-fig'): string {
    $п = htmlspecialchars($подпись, ENT_QUOTES);
    return "<figure class=\"$класс\"><img src=\"images/$файл\" alt=\"$п\" loading=\"lazy\"></figure>\n";
}

/** Плитки автоматов в карточки: рисунок под название игры, не больше восьми на страницу. */
function v7Плитки(string $html, string $стр, string $dir, callable $имя, int &$счёт): string {
    if (!preg_match_all('~<div class="slot-poster">~', $html, $m, PREG_OFFSET_CAPTURE)) return $html;
    $игры = v7Игры($html);
    $вставки = [];
    foreach (array_slice($m[0], 0, 8) as $i => $поп) {
        $игра = $игры[$i] ?? ('Slot ' . ($i + 1));
        $ф = $имя();
        g7Плитка("$dir/images/$ф", $игра, 480, 300);
        $п = htmlspecialchars($игра, ENT_QUOTES);
        $вставки[] = [$поп[1], strlen($поп[0]),
                      "<div class=\"slot-poster k7-has-img\"><img src=\"images/$ф\" alt=\"$п\" loading=\"lazy\">"];
    }
    foreach (array_reverse($вставки) as [$поз, $длина, $тег]) {
        $html = substr($html, 0, $поз) . $тег . substr($html, $поз + $длина);
    }
    return $html;
}

function v7Вставить(string $html, string $стр, array $т, string $dir, int $seed, int &$счёт): string {
    $разд = ключРаздела($стр);
    $имя = function () use (&$счёт, $стр) { return sprintf('%s_img_%d.webp', $стр, ++$счёт); };

    // плитки автоматов во все карточки, какие есть на странице
    $html = v7Плитки($html, $стр, $dir, $имя, $счёт);

    $faq = ($p = stripos($html, '<div class="faq-section')) !== false ? $p : -1;
    $полоса_перед_faq = function (string $html, int $seed) use ($стр, $т, $разд, $dir, $имя, &$счёт) {
        $poz = stripos($html, '<div class="faq-section');
        if ($poz === false) return $html;
        $ф = $имя();
        v7Баннер("$dir/images/$ф", $т, $стр, $разд, 1200, 240, $seed, 'полоса');
        return substr($html, 0, $poz) . v7Фигура($ф, "{$разд[0]} — коротко о главном") . substr($html, $poz);
    };

    switch ($т['картинка']) {
        case 'фон':
            $ф = $имя();
            v7Баннер("$dir/images/$ф", $т, $стр, $разд, 1200, 520, $seed, 'фон');
            $первый = preg_match('~<section\b[^>]*>~i', $html, $m, PREG_OFFSET_CAPTURE) ? $m[0][1] : -1;
            $конец = $первый >= 0 ? v7Конец($html, $первый) : -1;
            if ($конец > 0) {
                $блок = substr($html, $первый, $конец - $первый);
                $html = substr($html, 0, $первый)
                    . "<div class=\"k7-fon\" style=\"background-image:url('images/$ф')\">\n$блок\n</div>\n"
                    . substr($html, $конец);
            } else {
                $html = "<div class=\"k7-fon\" style=\"background-image:url('images/$ф')\">\n"
                    . "<h2>{$разд[1]}</h2>\n<p>{$разд[2]}</p>\n</div>\n" . $html;
            }
            break;

        case 'полосы':
            $ф = $имя();
            v7Баннер("$dir/images/$ф", $т, $стр, $разд, 1200, 240, $seed, 'полоса');
            $html = v7Фигура($ф, "{$разд[2]} — {$разд[0]}") . $html;
            $html = $полоса_перед_faq($html, $seed + 300);
            break;

        case 'врезка':
            $ф = $имя();
            v7Баннер("$dir/images/$ф", $т, $стр, $разд, 760, 760, $seed, 'квадрат');
            $конец = 0;
            if (preg_match_all('~</section>~i', $html, $m, PREG_OFFSET_CAPTURE)) {
                $край = $faq > 0 ? $faq : strlen($html);
                foreach ($m[0] as $поп) if ($поп[1] < $край) $конец = $поп[1] + strlen($поп[0]);
            }
            if ($конец === 0 && preg_match('~</p>~i', $html, $m2, PREG_OFFSET_CAPTURE)) $конец = $m2[0][1] + strlen($m2[0][0]);
            $html = substr($html, 0, $конец) . "\n" . v7Фигура($ф, "{$разд[1]} — {$разд[0]}", 'k7-fig k7-vrezka') . substr($html, $конец);
            break;

        default:   // «шапка» и «постеры»: ведущая сверху и полоса перед вопросами
            $ф = $имя();
            v7Баннер("$dir/images/$ф", $т, $стр, $разд, 1200, 630, $seed, 'ведущая');
            $html = v7Фигура($ф, "{$разд[1]} — {$разд[2]}") . $html;
            $html = $полоса_перед_faq($html, $seed + 500);
    }
    return $html;
}

if (PHP_SAPI === 'cli' && realpath($argv[0] ?? '') === __FILE__) {
    $арг = array_slice($argv, 1); $dir = rtrim(array_shift($арг) ?? '', '/');
    $seed = 1; $номер = 1;
    foreach ($арг as $a) {
        if (preg_match('/^--сид=(\d+)$/u', $a, $m)) $seed = (int) $m[1];
        if (preg_match('/^--тема=(\d+)$/u', $a, $m)) $номер = (int) $m[1];
    }
    if (!is_dir($dir)) { fwrite(STDERR, "нет папки $dir\n"); exit(2); }
    $т = v7Tema($номер);
    @mkdir("$dir/images");
    $всего = 0;
    foreach (glob("$dir/*.html") as $f) {
        $стр = basename($f, '.html'); $html = file_get_contents($f);
        if (strpos($html, "{$стр}_img_1.webp") !== false) continue;
        $счёт = 0;
        $html = v7Вставить($html, $стр, $т, $dir, $seed + (crc32($стр) % 997), $счёт);
        file_put_contents($f, $html);
        $всего += $счёт;
    }
    echo "{$т['картинка']}: картинок $всего\n";
}

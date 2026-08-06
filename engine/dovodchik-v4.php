<?php
declare(strict_types=1);

/**
 * Доводчик: правит счётные величины, которые нельзя испортить.
 *
 *   php engine/dovodchik-v4.php <файл.html> <тип-страницы> [--сухой]
 *
 * Граница проведена по одному признаку: **трогает ли правка форму слова**.
 *
 * Можно (правится без участия смысла):
 *   эмодзи-маркер   — символ в начале первой ячейки строки таблицы или пункта
 *                     списка; ставится и снимается, соседние слова не меняются;
 *   ol / ul         — тег списка; пункты не трогаются;
 *   бренд           — плейсхолдер ВСТАВЛЯЕТСЯ рядом с опорным словом («касса
 *                     %brand%») и снимается оттуда же; существительное на
 *                     плейсхолдер не заменяется — это ломает падеж.
 *
 * Нельзя (возвращается писателю брифом):
 *   ключевая плотность — замена «машина» → «слот» ломает падеж и согласование;
 *   двоеточие в H3     — метрика считает и двоеточие, и тире, так что обмен
 *                        разделителя её не двигает: нужен новый заголовок;
 *   выделение <strong> — где ставить, решает смысл фразы, а не счётчик;
 *   объём и абзацы     — разнести абзац значит потерять отсылку «то же самое»;
 *   регистр и сленг    — реплика, севшая в служебную строку, читается как сбой.
 *
 * Всё это уже пробовалось пакетным проходом в августе: счётчики сошлись с
 * донорскими, а в тексте появились «второй регистрация» и «к лицензия». Правки
 * этого рода тут закрыты намеренно, а не по недосмотру.
 */

require_once __DIR__ . '/src/PageMetrics.php';

$args = array_values(array_filter(array_slice($argv, 1), fn($a) => $a[0] !== '-'));
$FILE = $args[0] ?? '';
$TIP  = $args[1] ?? 'main';
$DRY  = in_array('--сухой', $argv, true);
if ($FILE === '' || !is_file($FILE)) {
    fwrite(STDERR, "usage: php engine/dovodchik-v4.php <файл.html> <тип> [--сухой]\n");
    exit(1);
}

$prof = json_decode((string) file_get_contents(__DIR__ . '/data-v4/profil-avgust.json'), true);
$norma = $prof['разметка']['страницы'][$TIP] ?? null;
$html = (string) file_get_contents($FILE);
$bylo = $html;
$otchet = [];

/** Класс эмодзи: включает 2300–23FF (⏱, ⏳) — их нет в привычных диапазонах. */
const EMO = '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{2300}-\x{23FF}]';
/** Маркеры общего назначения: ставим только их, тематические пишет автор. */
const MARKERY = ['🔹', '📌', '🧾', '💳', '🎰', '🎁', '📱', '🔒', '📞', '🕒', '📊', '🗂', '⏳', '🌐'];

function schet(string $h): int { return preg_match_all('~' . EMO . '~u', $h); }

// ── 1. эмодзи ───────────────────────────────────────────────────────────────
if ($norma) {
    $e = $norma['emoji'];
    $est = schet($html);
    $niz = (int) $e['низ']; $verh = (int) $e['верх'];
    if ($est < $niz) {
        // ставим маркер в первую ячейку строк таблиц, по одному на строку
        $nuzhno = (int) round(($niz + (float) $e['медиана']) / 2) - $est;
        $i = 0;
        $html = preg_replace_callback('~<tr><td>(?!\s*' . EMO . ')~u', function ($m) use (&$nuzhno, &$i) {
            if ($nuzhno <= 0) { return $m[0]; }
            $nuzhno--;
            return '<tr><td>' . MARKERY[$i++ % count(MARKERY)] . ' ';
        }, $html);
        $otchet[] = 'эмодзи ' . $est . ' → ' . schet($html) . " (норма " . $niz . "–" . $verh . ")";
    } elseif ($est > $verh) {
        $lishnih = $est - (int) $e['медиана'];
        $html = preg_replace_callback('~<td>\s*(' . EMO . ')\s*~u', function ($m) use (&$lishnih) {
            if ($lishnih <= 0) { return $m[0]; }
            $lishnih--;
            return '<td>';
        }, $html);
        $otchet[] = 'эмодзи ' . $est . ' → ' . schet($html) . " (норма " . $niz . "–" . $verh . ")";
    }
}

// ── 2. двоеточие в H3: НЕ правим, только сообщаем ───────────────────────────
// Метрика считает разделителем и двоеточие, и тире, поэтому обмен одного на
// другое её не двигает: чтобы поднять долю, заголовок надо ПЕРЕПИСАТЬ так,
// чтобы у него появилась левая часть-ключ. Это работа писателя, не скрипта.
if ($norma) {
    $h = $norma['h3_colon_pct'];
    $d = dolyaH3($html);
    if ($d < (float) $h['низ'] || $d > (float) $h['верх']) {
        $otchet[] = 'H3 с двоеточием ' . $d . ' % — писателю (норма ' . $h['низ'] . '–' . $h['верх'] . ' %)';
    }
}

function dolyaH3(string $html): float
{
    preg_match_all('~<h3[^>]*>(.*?)</h3>~is', $html, $m);
    $v = count($m[1]); if (!$v) { return 0.0; }
    $c = 0;
    foreach ($m[1] as $x) { $t = strip_tags($x); if (mb_strpos($t, ':') !== false || mb_strpos($t, '—') !== false) { $c++; } }
    return round($c / $v * 100, 1);
}

// ── 3. ol / ul ──────────────────────────────────────────────────────────────
// Список с пунктами-глаголами — порядок действий, это <ol>. Иначе <ul>.
$cel = (float) ($prof['страницы'][$TIP]['жанр']['ol_pct'] ?? $prof['страницы'][$TIP]['поля']['ordered_pct']['цель'] ?? 25);
preg_match_all('~<(ul|ol)>(.*?)</\1>~is', $html, $sp, PREG_SET_ORDER);
$ol = 0; $vsegoSp = count($sp);
foreach ($sp as $x) { if ($x[1] === 'ol') { $ol++; } }
if ($vsegoSp) {
    $dolya = $ol / $vsegoSp * 100;
    $glagol = '~^\s*<li>\s*(?:<strong>)?[А-ЯЁ][а-яё]+(?:ть|ите|йте)\b~u';
    if ($dolya < $cel - 10) {
        foreach ($sp as $x) {
            if ($x[1] !== 'ul' || !preg_match($glagol, $x[0])) { continue; }
            $novyy = '<ol>' . $x[2] . '</ol>';
            $html = str_replace($x[0], $novyy, $html);
            $ol++;
            if ($ol / $vsegoSp * 100 >= $cel) { break; }
        }
        $otchet[] = 'нумерованных ' . round($dolya) . ' % → ' . round($ol / $vsegoSp * 100) . " % (цель $cel %)";
    }
}

// ── 4. бренд: вставка рядом с опорным словом, без замены существительного ───
$b = $prof['бренд']['латиничная']['страницы'][$TIP]['лат'] ?? null;
if ($b) {
    $est = substr_count($html, '%brand_name_en%');
    $niz = (int) $b['низ']; $verh = (int) $b['верх'];
    if ($est < $niz) {
        $nado = (int) $b['медиана'] - $est;
        // «в кассе» → «в кассе %brand_name_en%»: падеж опорного слова не трогаем
        $opora = '~\b(касс[еауы]|каталог[еауа]?|кабинет[еауа]?|площадк[еиуой]|поддержк[аеиуой])\b(?!\s*%)~u';
        $html = preg_replace_callback($opora, function ($m) use (&$nado) {
            if ($nado <= 0) { return $m[0]; }
            $nado--;
            return $m[0] . ' %brand_name_en%';
        }, $html);
        $otchet[] = 'бренд латиницей ' . $est . ' → ' . substr_count($html, '%brand_name_en%') . " (норма " . $niz . "–" . $verh . ")";
    } elseif ($est > $verh) {
        $lishnih = $est - (int) $b['медиана'];
        $html = preg_replace_callback('~\s*%brand_name_en%~u', function ($m) use (&$lishnih) {
            if ($lishnih <= 0) { return $m[0]; }
            $lishnih--;
            return '';
        }, $html);
        $otchet[] = 'бренд латиницей ' . $est . ' → ' . substr_count($html, '%brand_name_en%') . " (норма " . $niz . "–" . $verh . ")";
    }
}

if (!$otchet) { echo "доводить нечего\n"; exit(0); }
if (!$DRY && $html !== $bylo) { file_put_contents($FILE, $html); }
foreach ($otchet as $o) { echo ($DRY ? 'сухо: ' : '') . $o . "\n"; }

<?php
declare(strict_types=1);

/**
 * Два текста рядом — без разбивки на блоки и без цифр.
 *
 *   php engine/dva-v5.php <наша-папка> [донор] [--выход=reports/v5/<имя>.html]
 *
 * Отчёт `ryadom-v5.php` режет страницу на блоки и считает совпадение по
 * каждому — это для разбора. Здесь другое: просто наш текст и донорский двумя
 * колонками, подряд, чтобы прочитать глазами и увидеть жанр, а не метрику.
 *
 * Разметка снимается до читаемого: заголовки жирным, пункты списка с тире,
 * абзацы абзацами. Виджеты не выбрасываются — они часть страницы.
 */

require_once __DIR__ . '/src/V5Blocks.php';
require_once __DIR__ . '/instrumenty/shingle.php';

$позиц = array_values(array_filter(array_slice($argv, 1), fn($a) => $a[0] !== '-'));
$наш = rtrim($позиц[0] ?? '', '/');
$донорИмя = $позиц[1] ?? '';
$корпус = 'samples/v5-donors';
$выход = '';
foreach (array_slice($argv, 1) as $a) {
    if (str_starts_with($a, '--выход=')) { $выход = substr($a, strlen('--выход=')); }
    elseif (str_starts_with($a, '--корпус=')) { $корпус = rtrim(substr($a, strlen('--корпус=')), '/'); }
}
if ($наш === '' || !is_dir($наш)) {
    fwrite(STDERR, "usage: php engine/dva-v5.php <наша-папка> [донор] [--выход=…]\n"); exit(1);
}
$выход = $выход !== '' ? $выход : 'reports/v5/dva-' . basename($наш) . '.html';

// Донор по умолчанию — ближайший по шинглам: рядом с ним и смотреть интереснее.
if ($донорИмя === '') {
    $лучший = ['', -1];
    foreach (glob("$корпус/*", GLOB_ONLYDIR) ?: [] as $d) {
        $сумма = 0; $n = 0;
        foreach (V5_TYPES as $t) {
            $a = "$наш/$t.html"; $b = "$d/$t.html";
            if (!is_file($a) || !is_file($b)) { continue; }
            $x = shingles(chist((string) file_get_contents($a)));
            $y = shingles(chist((string) file_get_contents($b)));
            if (!$x || !$y) { continue; }
            $сумма += count(array_intersect_key($x, $y)) / min(count($x), count($y)) * 100;
            $n++;
        }
        if ($n && $сумма / $n > $лучший[1]) { $лучший = [basename($d), $сумма / $n]; }
    }
    $донорИмя = $лучший[0];
}

/** Страница в читаемый текст: заголовки, абзацы, пункты. */
function v5Читаемо(string $html): string
{
    $o = '';
    foreach (v5Uzly($html) as $u) {
        $строки = [];
        if (in_array($u['тег'], ['h2', 'h3'], true) && $u['класс'] === '') {
            $строки[] = ['h', v5Text($u['html'])];
        } elseif ($u['тег'] === 'p' && $u['класс'] === '') {
            $строки[] = ['p', v5Text($u['html'])];
        } elseif (in_array($u['тег'], ['ul', 'ol'], true) && $u['класс'] === '') {
            if (preg_match_all('~<li[^>]*>(.*?)</li>~s', $u['html'], $m)) {
                foreach ($m[1] as $li) { $строки[] = ['li', v5Text($li)]; }
            }
        } else {
            // виджет: заголовки внутри — заголовками, остальное — абзацами
            foreach (v5Uzly("\n" . preg_replace('~^\s+~m', '', $u['html'])) as $вн) { /* заглушка */ }
            $куски = preg_split('~(?=<h[23]\b)~', $u['html']) ?: [];
            foreach ($куски as $к) {
                if (preg_match('~^<h[23]\b[^>]*>(.*?)</h[23]>~s', $к, $m)) {
                    $строки[] = ['h', v5Text($m[1])];
                    $к = substr($к, strlen($m[0]));
                }
                $т = v5Text($к);
                if ($т !== '') { $строки[] = ['p', $т]; }
            }
        }
        foreach ($строки as [$вид, $т]) {
            if ($т === '') { continue; }
            $э = htmlspecialchars($т);
            $o .= match ($вид) {
                'h'  => "<p class=\"z\">{$э}</p>\n",
                'li' => "<p class=\"l\">— {$э}</p>\n",
                default => "<p>{$э}</p>\n",
            };
        }
    }
    return $o;
}

$тело = '';
foreach (V5_TYPES as $тип) {
    $a = "$наш/$тип.html"; $b = "$корпус/$донорИмя/$тип.html";
    if (!is_file($a) || !is_file($b)) { continue; }
    $тело .= '<h2 id="' . $тип . '">' . $тип . "</h2>\n<div class=\"para\"><div class=\"kol\">\n"
        . v5Читаемо((string) file_get_contents($a))
        . "</div>\n<div class=\"kol\">\n"
        . v5Читаемо((string) file_get_contents($b))
        . "</div></div>\n";
}

$css = <<<'CSS'
:root { --fon:#fff; --tekst:#1c1c1c; --ramka:#e4e4e4; --pod:#6f6f6f; }
@media (prefers-color-scheme: dark) {
  :root { --fon:#16181c; --tekst:#e6e6e6; --ramka:#2c3037; --pod:#9aa0a6; }
}
* { box-sizing:border-box; }
body { margin:0; padding:28px; background:var(--fon); color:var(--tekst);
  font:16px/1.65 Georgia,"Times New Roman",serif; }
h1 { font:600 20px/1.3 -apple-system,"Segoe UI",Roboto,sans-serif; margin:0 0 4px; }
h2 { font:600 14px/1.3 -apple-system,"Segoe UI",Roboto,sans-serif; text-transform:uppercase;
  letter-spacing:.08em; color:var(--pod); margin:38px 0 10px; padding-top:14px;
  border-top:1px solid var(--ramka); }
.shapka { color:var(--pod); font:14px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif; margin:0 0 8px; }
.para { display:grid; grid-template-columns:1fr 1fr; gap:34px; }
.kol { min-width:0; }
.kol p { margin:0 0 12px; }
.kol .z { font-weight:700; margin-top:20px; }
.kol .l { margin:0 0 6px; padding-left:2px; }
.imena { display:grid; grid-template-columns:1fr 1fr; gap:34px;
  font:600 13px/1.4 -apple-system,"Segoe UI",Roboto,sans-serif; color:var(--pod);
  text-transform:uppercase; letter-spacing:.06em; margin:0 0 14px; }
@media (max-width:820px) { .para, .imena { grid-template-columns:1fr; } }
CSS;

$html = "<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
    . '<meta name="viewport" content="width=device-width,initial-scale=1">'
    . '<title>Два текста: ' . htmlspecialchars(basename($наш)) . ' и ' . htmlspecialchars($донорИмя) . '</title>'
    . "<style>$css</style></head><body>"
    . '<h1>Два текста рядом</h1>'
    . '<p class="shapka">Слева наш комплект, справа донорский. Двенадцать страниц подряд, без разбора и цифр.</p>'
    . '<div class="imena"><div>' . htmlspecialchars(basename($наш)) . '</div><div>'
    . htmlspecialchars($донорИмя) . '</div></div>'
    . $тело . '</body></html>';

if (!is_dir(dirname($выход))) { mkdir(dirname($выход), 0777, true); }
file_put_contents($выход, $html);
printf("%s против %s → %s (%.0f КБ)\n", basename($наш), $донорИмя, $выход, filesize($выход) / 1024);

<?php
declare(strict_types=1);

/**
 * Снимает со страниц «хром» — строки-чипы старого меню в шапке и бейджи в
 * подвале: «🎰 Слоты · 🏆 Турниры · 🎁 Бонусы · ₿ Крипта» и «🔞 18+ 🛡 Security-стек
 * 💬 Поддержка 24/7». Это навигация и плашки, а не текст: они попали в
 * генерацию, потому что в сохранённых референсах лежали вперемешку с прозой.
 *
 *   php strip-chrome.php <папка|файл> [--dry]
 *
 * Что НЕ трогает: всё, где есть ссылки (навигация по разделам с реальными
 * href остаётся), и всё, что стоит между первым и последним заголовком —
 * то есть CTA-баннеры внутри текста, они часть жанра.
 */

$args = array_slice($argv, 1);
$dry = in_array('--dry', $args, true);
$target = '';
foreach ($args as $a) { if ($a !== '--dry') { $target = $a; } }
if ($target === '') { fwrite(STDERR, "usage: strip-chrome.php <dir|file> [--dry]\n"); exit(1); }

$EMOJI = '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}\x{20E3}]';

/** строка-чип: без ссылок, много эмодзи, короткие подписи, не предложение */
function isChipRow(string $inner, string $EMOJI): bool
{
    if (stripos($inner, '<a ') !== false) { return false; }          // есть ссылки — это навигация, оставляем
    $text = trim(preg_replace('~\s+~u', ' ', html_entity_decode(strip_tags($inner))));
    if ($text === '' || mb_strlen($text) > 260) { return false; }
    $em = preg_match_all('~' . $EMOJI . '~u', $text);
    if ($em < 3) { return false; }
    // куски: по «·» либо по самим эмодзи, если разделителя нет
    $parts = preg_split('~\s*·\s*~u', $text);
    if (count($parts) < 3) {
        $parts = array_values(array_filter(array_map('trim', preg_split('~' . $EMOJI . '~u', $text))));
    }
    if (count($parts) < 3) { return false; }
    // каждая подпись короткая и без точки — это метка, а не фраза
    foreach ($parts as $p) {
        $p = trim(preg_replace('~' . $EMOJI . '~u', '', $p));
        if ($p === '') { continue; }
        if (mb_substr_count($p, ' ') > 4 || preg_match('~[.!?]\s~u', $p)) { return false; }
    }
    return true;
}

function clean(string $html, string $EMOJI, array &$removed): string
{
    // Позицию не проверяем: такие строки стоят и в шапке, и в подвале, и между
    // разделами. Отличает их отсутствие ссылок — навигация с настоящими href
    // остаётся, как и просили.
    return (string) preg_replace_callback(
        '~<(p|div|nav|section|header|footer|ul)\b[^>]*>(.*?)</\1>~is',
        function (array $m) use ($EMOJI, &$removed) {
            if (!isChipRow($m[2], $EMOJI)) { return $m[0]; }
            $text = trim(preg_replace('~\s+~u', ' ', html_entity_decode(strip_tags($m[2]))));
            $removed[] = $text;
            // В подвальной плашке вместе с бейджами сидит дата-стамп — он нужен,
            // выбрасываем только бейджи вокруг него.
            if (preg_match('~(Последнее обновление.*)$~u', $text, $dm)) {
                return '<p>' . trim($dm[1]) . '</p>';
            }
            return '';
        },
        $html
    );
}

$files = is_dir($target) ? glob(rtrim($target, '/') . '/*.html') : [$target];
$totalRows = 0;
foreach ($files as $f) {
    $src = (string) file_get_contents($f);
    $removed = [];
    $out = clean($src, $EMOJI, $removed);
    if ($removed) {
        $totalRows += count($removed);
        printf("%-16s снято строк %d\n", basename($f), count($removed));
        foreach ($removed as $r) { echo "    · " . mb_substr($r, 0, 110) . "\n"; }
        if (!$dry) { file_put_contents($f, preg_replace('~\n{3,}~', "\n\n", $out)); }
    }
}
echo "STATUS " . json_encode(['files' => count($files), 'rows' => $totalRows, 'dry' => $dry]) . "\n";

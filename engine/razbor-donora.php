<?php
declare(strict_types=1);

/**
 * Анатомия одной чужой страницы — без сравнения с чем-либо.
 *
 *   php engine/razbor-donora.php <файл.html> [бренд_ru] [бренд_en] [--json]
 *
 * zamer-obzor.php отвечает на вопрос «сходится ли наше с чужим». Здесь другой
 * вопрос: «что чужая страница вообще делает». Разница существенная — на
 * donor-2 приёмочный шлюз из 55 полей проходился целиком на странице, где не
 * было ни одного приёма образца, потому что поля меряют плотности, а приёмы
 * живут в разметке.
 *
 * Печатает шесть блоков:
 *   1. замер 55 полей
 *   2. скелет разделов с блоком после каждого заголовка
 *   3. приёмы вёрстки
 *   4. что прячется от метрик: доля текста вне <p> и <li>
 *   5. повторы: одинаковые шапки таблиц, дублирующиеся блоки
 *   6. следы накрутки
 */

require_once __DIR__ . '/src/PageMetrics.php';

$file = $argv[1] ?? '';
$brand = ['ru' => $argv[2] ?? '', 'en' => $argv[3] ?? ''];
$asJson = in_array('--json', $argv, true);
if ($file === '' || !is_file($file)) {
    fwrite(STDERR, "usage: php engine/razbor-donora.php <файл.html> [бренд_ru] [бренд_en] [--json]\n");
    exit(1);
}

$raw = (string) file_get_contents($file);

/** Статейная часть, если страница целиком: от первого H2 до последнего </details> либо </table>. */
$body = $raw;
if (preg_match('~<h2\b~i', $raw, $m, PREG_OFFSET_CAPTURE)) {
    $start = $m[0][1];
    $endCandidates = [];
    foreach (['</details>', '</table>', '</p>'] as $tag) {
        $p = strripos($raw, $tag);
        if ($p !== false) { $endCandidates[] = $p + strlen($tag); }
    }
    $end = $endCandidates ? max($endCandidates) : strlen($raw);
    if ($end > $start) { $body = substr($raw, $start, $end - $start); }
}

$noScript = preg_replace('~(?is)<(script|style)\b.*?</\1>~', ' ', $raw);
$plain = trim(preg_replace('~\s+~u', ' ', strip_tags((string) $noScript)));
$words = preg_split('~\s+~u', $plain, -1, PREG_SPLIT_NO_EMPTY) ?: [];
$EMO = '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]';

// ── 1. замер ────────────────────────────────────────────────────────
$a = new Analyzer();
$card = PageMetrics::measure($a, 'main', $raw, $brand);
$fields = PageMetrics::fields(true);

// ── 2. скелет ───────────────────────────────────────────────────────
preg_match_all('~(?is)<(h2|h3)\b[^>]*>(.*?)</\1>~', $body, $hm, PREG_SET_ORDER | PREG_OFFSET_CAPTURE);
$skeleton = [];
foreach ($hm as $i => $h) {
    $level = strtolower($h[1][0]);
    $text = trim(preg_replace('~\s+~u', ' ', strip_tags($h[2][0])));
    $from = $h[0][1] + strlen($h[0][0]);
    $to = $hm[$i + 1][0][1] ?? strlen($body);
    $chunk = substr($body, $from, max(0, $to - $from));
    $blocks = [];
    foreach (['p' => '<p\b', 'table' => '<table\b', 'ul' => '<ul\b', 'ol' => '<ol\b',
              'details' => '<details\b', 'img' => '<img\b', 'div' => '<div\b'] as $n => $re) {
        $c = preg_match_all('~(?i)' . $re . '~', $chunk);
        if ($c) { $blocks[$n] = $c; }
    }
    $skeleton[] = ['уровень' => $level, 'заголовок' => $text, 'блоки' => $blocks];
}

// ── 3. приёмы ───────────────────────────────────────────────────────
$slotCards = preg_match_all(
    '~(?is)<(div|li|td)\b[^>]*>\s*(?:<[^>]+>\s*)*<b>[^<]{2,40}</b>.{0,140}?(RTP|Jackpot|Джекпот)~u', $body
);
$reviews = preg_match_all('~(?is)<b>[А-ЯЁ][а-яё]{2,}(?:,\s*\d{2})?</b>.{0,260}?[★☆]~u', $body);
preg_match_all('~(?is)<table\b.*?</table>~', $body, $tm);
$headers = [];
foreach ($tm[0] as $t) {
    preg_match_all('~(?is)<th\b[^>]*>(.*?)</th>~', $t, $th);
    $headers[] = mb_strtolower(implode('|', array_map(fn($x) => trim(strip_tags($x)), $th[1] ?? [])));
}
$headsText = implode("\n", array_column($skeleton, 'заголовок'));
$priyomy = [
    'карточек автоматов' => $slotCards,
    'отзывов со звёздами' => $reviews,
    'звёзд ★☆' => preg_match_all('~[★☆]~u', $plain),
    'плашек' => preg_match_all('~(?is)class="[^"]*(pill|badge|chip|tag|label)[^"]*"~', $body),
    'таблиц' => count($tm[0]),
    'разных шапок' => count(array_unique(array_filter($headers))),
    'эмодзи всего' => preg_match_all('~' . $EMO . '~u', $plain),
    'эмодзи в заголовках' => preg_match_all('~' . $EMO . '~u', $headsText),
    'картинок' => preg_match_all('~(?i)<img\b~', $body),
    'аккордеонов details' => preg_match_all('~(?i)<details\b~', $body),
];

// ── 4. что прячется от метрик ───────────────────────────────────────
$inProse = 0;
foreach (['~(?is)<p\b[^>]*>(.*?)</p>~', '~(?is)<li\b[^>]*>(.*?)</li>~'] as $re) {
    if (preg_match_all($re, $body, $pm)) {
        foreach ($pm[1] as $x) {
            $inProse += count(preg_split('~\s+~u', trim(strip_tags($x)), -1, PREG_SPLIT_NO_EMPTY) ?: []);
        }
    }
}
$bodyPlain = trim(preg_replace('~\s+~u', ' ', strip_tags($body)));
$bodyWords = count(preg_split('~\s+~u', $bodyPlain, -1, PREG_SPLIT_NO_EMPTY) ?: []);
$hidden = $bodyWords - $inProse;

// ── 5. повторы ──────────────────────────────────────────────────────
$dupHeaders = [];
foreach (array_count_values(array_filter($headers)) as $h => $n) {
    if ($n > 1) { $dupHeaders[] = "$n× " . mb_substr($h, 0, 50); }
}
preg_match_all('~(?is)<p\b[^>]*>(.*?)</p>~', $body, $pm);
$paras = array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []);
$dupParas = 0;
foreach (array_count_values(array_filter($paras)) as $n) { if ($n > 1) { $dupParas += $n - 1; } }

// ── 6. следы накрутки ───────────────────────────────────────────────
$brandRe = '';
if ($brand['ru'] !== '') { $brandRe = '~' . preg_quote($brand['ru'], '~') . '|' . preg_quote($brand['en'], '~') . '~ui'; }
$brandTotal = $brandRe ? preg_match_all($brandRe, $plain) : 0;
$third = mb_substr($plain, 0, (int) (mb_strlen($plain) / 3));
$brandFirst = $brandRe ? preg_match_all($brandRe, $third) : 0;
$anchorHits = 0;
foreach (PageMetrics::ANCHORS as $re) { $anchorHits += preg_match_all($re, $plain); }
$cssWords = 0;
if (preg_match_all('~(?is)<style\b[^>]*>(.*?)</style>~', $raw, $sm)) {
    foreach ($sm[1] as $x) { $cssWords += count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY) ?: []); }
}
$sledy = [
    'слов всего (без script/style)' => count($words),
    'слов в статейной части' => $bodyWords,
    'слов вне <p> и <li>' => $hidden,
    'доля текста вне прозы, %' => $bodyWords ? round($hidden / $bodyWords * 100, 1) : 0,
    'слов внутри <style>' => $cssWords,
    'бренд всего' => $brandTotal,
    'бренд в первой трети' => $brandFirst,
    'бренд в первой трети, %' => $brandTotal ? round($brandFirst / $brandTotal * 100, 1) : 0,
    'опорных формул' => $anchorHits,
    'формул на 1000 слов' => count($words) ? round($anchorHits / count($words) * 1000, 1) : 0,
    'ссылок <a>' => preg_match_all('~(?i)<a\b~', $body),
    'schema.org разметки' => preg_match_all('~(?i)itemtype="[^"]*schema\.org~', $raw),
    'повторов шапок таблиц' => $dupHeaders ? implode(', ', $dupHeaders) : '—',
    'дословных повторов абзацев' => $dupParas,
];

// ── вывод ───────────────────────────────────────────────────────────
if ($asJson) {
    echo json_encode(
        ['файл' => basename($file), 'замер' => $card, 'скелет' => $skeleton,
         'приёмы' => $priyomy, 'следы' => $sledy],
        JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT
    ), "\n";
    exit(0);
}

echo "══ " . basename($file) . " ══\n\n";

echo "── замер ──\n";
foreach ($fields as $k => $meta) {
    if (array_key_exists($k, $card)) { printf("  %-22s %s\n", $k, (string) $card[$k]); }
}

echo "\n── скелет ──\n";
foreach ($skeleton as $s) {
    $b = [];
    foreach ($s['блоки'] as $n => $c) { $b[] = "$n×$c"; }
    printf("  %-4s %-52s %s\n", strtoupper($s['уровень']),
        mb_substr($s['заголовок'], 0, 52), implode(' ', $b));
}

echo "\n── приёмы ──\n";
foreach ($priyomy as $k => $v) { printf("  %-24s %s\n", $k, (string) $v); }

echo "\n── следы ──\n";
foreach ($sledy as $k => $v) { printf("  %-30s %s\n", $k, (string) $v); }
echo "\n";

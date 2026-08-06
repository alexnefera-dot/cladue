<?php
declare(strict_types=1);

/**
 * Приёмка страницы по августовскому профилю.
 *
 *   php engine/priyomka-v4.php <папка-версии> [--korpus=samples/v4-final]
 *
 * Отличий от priyomka-obzor.php три, и каждое выведено из разбора корпуса.
 *
 * 1. Требуются НЕ все 55 полей, а только двадцать четыре, которые доноры
 *    держат. Остальные тридцать один у них гуляют вдвое-втрое, и держать их в
 *    узкой полосе значит платить за чужую дисциплину однообразием.
 *
 * 2. Проверяются приёмы жанра, которых поля не видят: зачин из трёх частей,
 *    порядок финала, формула заголовка «ключ : хвост», уникальные шапки
 *    таблиц, механизм маски, доля вопросов про сбой.
 *
 * 3. Уникальность считается не только по шинглам. Шингл из шести слов не
 *    проходит через трёхсловный заголовок, и повтор скелета остаётся невидим:
 *    в нашем прежнем корпусе так совпали восемь H2 у десяти версий подряд.
 *    Поэтому заголовки сверяются отдельно и дословно.
 *
 * Код возврата 0 — пройдены все три шлюза.
 */

require_once __DIR__ . '/src/PageMetrics.php';

$dir = $argv[1] ?? '';
$korpus = 'samples/v4-final';
foreach (array_slice($argv, 2) as $a) {
    if (str_starts_with($a, '--korpus=')) { $korpus = substr($a, 9); }
}
if ($dir === '') {
    fwrite(STDERR, "usage: php engine/priyomka-v4.php <папка-версии> [--korpus=<путь>]\n");
    exit(1);
}
$dir = rtrim($dir, '/');
$file = $dir . '/main.html';
if (!is_file($file)) { fwrite(STDERR, "нет файла: $file\n"); exit(1); }

$root = dirname(__DIR__);
$profil = json_decode((string) file_get_contents(__DIR__ . '/data-v4/profil-avgust.json'), true);
if (!$profil) { fwrite(STDERR, "нет профиля engine/data-v4/profil-avgust.json\n"); exit(1); }

$raw = (string) file_get_contents($file);
/** У доноров попадается голая «<» в тексте; strip_tags глотает от неё до «>». */
$html = preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $raw);

function chist(string $h): string
{
    $h = preg_replace('~(?is)<(script|style)\b.*?</\1>~', ' ', $h);
    $h = preg_replace('~<[a-zA-Z/!][^>]*>~', ' ', (string) $h);
    return html_entity_decode((string) $h, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}
function slv(string $t): array
{
    preg_match_all('~[\p{L}\p{N}]+~u', $t, $m);
    return $m[0];
}
function zagolovki(string $h): array
{
    preg_match_all('~(?is)<(h2|h3)[^>]*>(.*?)</\1>~', $h, $m, PREG_SET_ORDER);
    $out = [];
    foreach ($m as $x) {
        $t = trim(preg_replace('~\s+~u', ' ', chist($x[2])));
        if ($t !== '') { $out[] = ['ур' => strtolower($x[1]), 'текст' => $t]; }
    }
    return $out;
}

$pad = fn($v, $w, $l = false) => $l
    ? $v . str_repeat(' ', max(0, $w - mb_strlen((string) $v)))
    : str_repeat(' ', max(0, $w - mb_strlen((string) $v))) . $v;

$provaly = [];

// ── 1. параметры ────────────────────────────────────────────────────
$a = new Analyzer();
$card = PageMetrics::measure($a, 'main', $html, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
$parOk = 0; $parVsego = 0; $parBad = [];
foreach ($profil['поля'] as $k => $p) {
    if (!$p['держат'] || !array_key_exists($k, $card)) { continue; }
    $parVsego++;
    $nash = (float) $card[$k];
    $cel = (float) $p['цель'];
    $pol = $p['дробное'] ? 0.8 : 2.0;
    if (abs($nash - $cel) <= max(0.25 * abs($cel), $pol)) { $parOk++; }
    else { $parBad[] = "$k " . $nash . '→' . $cel; }
}
if ($parOk < $parVsego) { $provaly[] = 'параметры'; }

// ── 2. приёмы ───────────────────────────────────────────────────────
$hs = zagolovki($html);
$h2 = array_values(array_filter($hs, fn($x) => $x['ур'] === 'h2'));
$lead = preg_split('~(?i)<h2\b~', $html, 2)[0];
$leadText = chist($lead);
$leadLow = mb_strtolower($leadText);
$tekst = chist($html);
$slov = count(slv($tekst));

/** Таблицы: шапка либо в <th>, либо первой строкой. */
preg_match_all('~(?is)<table\b.*?</table>~', $html, $tm);
$shapki = [];
$kolonki = [];
foreach ($tm[0] as $tab) {
    preg_match_all('~(?is)<th\b[^>]*>(.*?)</th>~', $tab, $th);
    $head = array_map(fn($x) => mb_strtolower(trim(preg_replace('~\s+~u', ' ', strip_tags($x)))), $th[1]);
    if (!$head && preg_match('~(?is)<tr\b[^>]*>(.*?)</tr>~', $tab, $tr)) {
        preg_match_all('~(?is)<td\b[^>]*>(.*?)</td>~', $tr[1], $td);
        $head = array_map(fn($x) => mb_strtolower(trim(preg_replace('~\s+~u', ' ', strip_tags($x)))), $td[1]);
    }
    if ($head) { $shapki[] = implode('|', $head); $kolonki[] = count($head); }
}

// Дефис в «чек‑лист» у доноров неразрывный (U+2011) — обычный класс его не ловит.
$finalKlass = '~плюс|минус|итог|вердикт|чек[-\x{2011}\s]?лист|заключ|отзыв|финал~iu';
$posledniy = $h2 ? end($h2)['текст'] : '';
$predposledniy = count($h2) > 1 ? $h2[count($h2) - 2]['текст'] : '';

$srazd = 0;
foreach ($h2 as $x) { if (preg_match('~^(.{4,60}?)\s*[:—–-]\s+(.+)$~u', $x['текст'])) { $srazd++; } }

$voprosy = [];
if (preg_match_all('~(?is)<summary[^>]*>(.*?)</summary>~', $html, $vm)) {
    foreach ($vm[1] as $t) {
        $t = trim(preg_replace('~\s+~u', ' ', chist($t)));
        if (mb_strlen($t) >= 8) { $voprosy[] = $t; }
    }
}
$sboy = count(array_filter($voprosy, fn($t) => preg_match(
    '~не (?:прих|приш|начисл|работ|отобра|груз|заход|получ|срабат|актив|подтвер|прошёл|уда)'
    . '|заблок|ошибк|отказ|завис|сброс|пропал|потерял|застрял|задерж|не могу|отклон|сгорел|исчез~iu', $t)));

$sravneniy = preg_match_all('~(?<![\p{L}])(?:это|—)\s+(?:как|это)\s~u', mb_strtolower($tekst));

$ssylkiVProze = 0; $ssylokVsego = preg_match_all('~(?is)<a\s[^>]*href="/[a-z]*"~', $html);
if (preg_match_all('~(?is)<(p|li)\b[^>]*>(.*?)</\1>~', $html, $bm, PREG_SET_ORDER)) {
    foreach ($bm as $b) { $ssylkiVProze += preg_match_all('~(?is)<a\s[^>]*href="/[a-z]*"~', $b[2]); }
}

$pasport = 0;
foreach (['~официальн~u', '~регистрац~u', '~зеркал~u'] as $re) { if (preg_match($re, $leadLow)) { $pasport++; } }

$priyomy = [
    'зачин: слов' => [count(slv($leadText)), '137–221',
        count(slv($leadText)) >= 137 && count(slv($leadText)) <= 221],
    'зачин: сайт+регистрация+зеркало' => [$pasport . '/3', '3/3', $pasport === 3],
    'зачин: список-оглавление' => [preg_match('~(?i)<(ul|ol)\b~', $lead) ? 'есть' : 'нет', 'есть',
        (bool) preg_match('~(?i)<(ul|ol)\b~', $lead)],
    'зачин: таблица-паспорт' => [preg_match('~(?i)<table\b~', $lead) ? 'есть' : 'нет', 'есть',
        (bool) preg_match('~(?i)<table\b~', $lead)],
    'финал: последний H2' => [mb_substr($posledniy, 0, 22), 'итог/плюсы/отзывы',
        (bool) preg_match($finalKlass, $posledniy)],
    'финал: предпоследний H2' => [mb_substr($predposledniy, 0, 22), 'FAQ или итог',
        (bool) preg_match('~вопрос|faq|ответ|итог|вердикт|отзыв~iu', $predposledniy)],
    'заголовок «ключ : хвост»' => [$h2 ? round($srazd / count($h2) * 100) . '%' : '0%', '≥45%',
        $h2 && $srazd / count($h2) >= 0.45],
    'таблиц' => [count($tm[0]), '12–20', count($tm[0]) >= 12 && count($tm[0]) <= 20],
    'шапки уникальны' => [$shapki ? round(count(array_unique($shapki)) / count($shapki) * 100) . '%' : '—',
        '100%', $shapki && count(array_unique($shapki)) === count($shapki)],
    'колонок в таблице' => [$kolonki ? round(array_sum($kolonki) / count($kolonki), 1) : 0, '≈3',
        $kolonki && abs(array_sum($kolonki) / count($kolonki) - 3) <= 0.8],
    'пар «вопрос-ответ»' => [count($voprosy), '9–14', count($voprosy) >= 9 && count($voprosy) <= 14],
    // Медиана по корпусу 20%, первый квартиль 13 — берём порог между ними.
    'вопросов про сбой' => [$voprosy ? round($sboy / count($voprosy) * 100) . '%' : '0%', '≥15%',
        $voprosy && $sboy / count($voprosy) >= 0.15],
    'сравнений «X это как Y»' => [$sravneniy, '≥20', $sravneniy >= 20],
    'внутренних ссылок' => [$ssylokVsego, '≥15', $ssylokVsego >= 15],
    'ссылок внутри прозы' => [$ssylokVsego ? round($ssylkiVProze / $ssylokVsego * 100) . '%' : '0%', '≥85%',
        $ssylokVsego && $ssylkiVProze / $ssylokVsego >= 0.85],
];
$prOk = count(array_filter($priyomy, fn($x) => $x[2]));
if ($prOk < count($priyomy)) { $provaly[] = 'приёмы'; }

// ── 3. уникальность ─────────────────────────────────────────────────
$shingle = function (string $t, int $n = 6): array {
    $t = mb_strtolower(preg_replace('~%[a-z_]+%~u', ' бренд ', $t));
    $w = slv($t);
    $s = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $s[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $s;
};
$nashShingle = $shingle($tekst);
$nashZag = [];
foreach ($hs as $x) { $nashZag[mb_strtolower($x['текст'])] = 1; }

$hudshaya = 0.0; $hudshiy = '—'; $povtorZag = []; $sosed = '—';
$put = is_dir($korpus) ? $korpus : $root . '/' . $korpus;
foreach (glob(rtrim($put, '/') . '/*', GLOB_ONLYDIR) ?: [] as $other) {
    if (!is_file("$other/main.html")) { continue; }
    if (realpath($other) === realpath($dir)) { continue; }
    $ot = chist(preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', (string) file_get_contents("$other/main.html")));
    $os = $shingle($ot);
    $min = min(count($nashShingle), count($os));
    if ($min) {
        $v = count(array_intersect_key($nashShingle, $os)) / $min * 100;
        if ($v > $hudshaya) { $hudshaya = $v; $hudshiy = basename($other); }
    }
    foreach (zagolovki((string) file_get_contents("$other/main.html")) as $z) {
        $k = mb_strtolower($z['текст']);
        if (isset($nashZag[$k])) { $povtorZag[$k] = basename($other); }
    }
}
$porog = (float) ($profil['уникальность']['шинглы']['порог_pct'] ?? 6.0);
if ($hudshaya >= $porog || $povtorZag) { $provaly[] = 'уникальность'; }

// ── отчёт ───────────────────────────────────────────────────────────
printf("%s\n\n", basename($dir));

printf("── параметры %d/%d ──\n", $parOk, $parVsego);
if ($parBad) { foreach ($parBad as $b) { echo "  ✗ $b\n"; } }

printf("\n── приёмы %d/%d ──\n", $prOk, count($priyomy));
foreach ($priyomy as $n => [$est, $nado, $ok]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 30, true) . $pad((string) $est, 12) . '   нужно ' . $nado . "\n";
}

printf("\n── уникальность ──\n");
printf("  худшая пара по шинглам   %.2f%%  (%s), порог %.0f%%\n", $hudshaya, $hudshiy, $porog);
printf("  дословных повторов заголовков  %d%s\n", count($povtorZag),
    $povtorZag ? '  ✗ ' . implode('; ', array_map(
        fn($k, $v) => mb_substr($k, 0, 40) . " [$v]", array_keys($povtorZag), $povtorZag)) : '');

printf("\nИТОГ: %s\n", $provaly ? 'НЕ ПРОЙДЕНО — ' . implode(', ', $provaly) : 'пройдено');
exit($provaly ? 1 : 0);

<?php
declare(strict_types=1);

/**
 * Приёмка страницы по августовскому профилю.
 *
 *   php engine/priyomka-v4.php <папка-версии> [--korpus=samples/v4-final] [--профиль=<файл>]
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
 * 3. Отдельный шлюз — техническая мерка (SeoMetrics). PageMetrics не смотрит на
 *    blockquote, курсив, уровни заголовков, nofollow и внешние ссылки. Двадцать
 *    восемь проходов разбора их пропустили, а цитата стоит у 36 донорских сайтов
 *    из 36 — девять штук на главной и ровно одна на каждой внутренней.
 *
 * 4. Уникальность считается не только по шинглам. Шингл из шести слов не
 *    проходит через трёхсловный заголовок, и повтор скелета остаётся невидим:
 *    в нашем прежнем корпусе так совпали восемь H2 у десяти версий подряд.
 *    Поэтому заголовки сверяются отдельно и дословно.
 *
 * Код возврата 0 — пройдены все три шлюза.
 */

require_once __DIR__ . '/src/Flagi.php';
require_once __DIR__ . '/src/PageMetrics.php';
require_once __DIR__ . '/src/SeoMetrics.php';

$dir = $argv[1] ?? '';
$korpus = 'samples/v4-final';
$profilFile = __DIR__ . '/data-v4/profil-avgust.json';
[$opts] = Flagi::razobrat($argv, 2, ['корпус', 'профиль']);
$korpus = $opts['корпус'] ?? $korpus;
$profilFile = $opts['профиль'] ?? $profilFile;
if ($dir === '') {
    fwrite(STDERR, "usage: php engine/priyomka-v4.php <папка-версии> [--корпус=<путь>] [--профиль=<файл>]\n");
    exit(1);
}
$dir = rtrim($dir, '/');
$file = $dir . '/main.html';
if (!is_file($file)) { fwrite(STDERR, "нет файла: $file\n"); exit(1); }

$root = dirname(__DIR__);
$profil = is_file($profilFile) ? json_decode((string) file_get_contents($profilFile), true) : null;
if (!$profil) { fwrite(STDERR, "нет профиля $profilFile\n"); exit(1); }

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
    'зачин: слов' => (function (int $n) use ($profil) {
        $b = $profil['структура']['зачин']['полоса'] ?? [137, 221];
        return [$n, $b[0] . '–' . $b[1], $n >= $b[0] && $n <= $b[1]];
    })(count(slv($leadText))),
    'зачин: сайт+регистрация+зеркало' => [$pasport . '/3', '3/3', $pasport === 3],
    'зачин: список-оглавление' => [preg_match('~(?i)<(ul|ol)\b~', $lead) ? 'есть' : 'нет', 'есть',
        (bool) preg_match('~(?i)<(ul|ol)\b~', $lead)],
    'зачин: таблица-паспорт' => [preg_match('~(?i)<table\b~', $lead) ? 'есть' : 'нет', 'есть',
        (bool) preg_match('~(?i)<table\b~', $lead)],
    // Порядок финала перевернулся между поколениями: в августе последним стоял
    // блок «плюсы и минусы» (20 главных из 50), в новом корпусе — FAQ (26 из 38).
    'финал: последний H2' => [mb_substr($posledniy, 0, 22),
        $profil['структура']['финал']['последний_подпись'] ?? 'итог/плюсы/отзывы',
        (bool) preg_match($profil['структура']['финал']['последний_регулярка'] ?? $finalKlass, $posledniy)],
    'финал: предпоследний H2' => [mb_substr($predposledniy, 0, 22),
        $profil['структура']['финал']['предпоследний_подпись'] ?? 'FAQ или итог',
        (bool) preg_match($profil['структура']['финал']['предпоследний_регулярка']
            ?? '~вопрос|faq|ответ|итог|вердикт|отзыв~iu', $predposledniy)],
    'заголовок «ключ : хвост»' => [$h2 ? round($srazd / count($h2) * 100) . '%' : '0%', '≥45%',
        $h2 && $srazd / count($h2) >= 0.45],
    'таблиц' => (function (int $n) use ($profil) {
        $b = $profil['жанр_главной']['таблиц'] ?? [12, 20];
        return [$n, $b[0] . '–' . $b[1], $n >= $b[0] && $n <= $b[1]];
    })(count($tm[0])),
    'шапки уникальны' => [$shapki ? round(count(array_unique($shapki)) / count($shapki) * 100) . '%' : '—',
        '100%', $shapki && count(array_unique($shapki)) === count($shapki)],
    'колонок в таблице' => [$kolonki ? round(array_sum($kolonki) / count($kolonki), 1) : 0, '≈3',
        $kolonki && abs(array_sum($kolonki) / count($kolonki) - 3) <= 0.8],
    // Полосы жанра берутся из профиля: у августовской прозы пар «вопрос-ответ»
    // на главной 9–14 и сравнений 11–22, у нового корпуса — 1–11 и 1–10.
    'пар «вопрос-ответ»' => (function (int $n) use ($profil) {
        $b = $profil['жанр_главной']['пар_вопрос_ответ'] ?? [9, 14];
        return [$n, $b[0] . '–' . $b[1], $n >= $b[0] && $n <= $b[1]];
    })(count($voprosy)),
    // Медиана по корпусу 20%, первый квартиль 13 — берём порог между ними.
    'вопросов про сбой' => [$voprosy ? round($sboy / count($voprosy) * 100) . '%' : '0%', '≥15%',
        $voprosy && $sboy / count($voprosy) >= 0.15],
    'сравнений «X это как Y»' => (function (int $n) use ($profil) {
        $b = $profil['жанр_главной']['сравнений'] ?? null;
        return $b ? [$n, $b[0] . '–' . $b[1], $n >= $b[0] && $n <= $b[1]] : [$n, '≥20', $n >= 20];
    })($sravneniy),
    'внутренних ссылок' => [$ssylokVsego, '≥15', $ssylokVsego >= 15],
    'ссылок внутри прозы' => [$ssylokVsego ? round($ssylkiVProze / $ssylokVsego * 100) . '%' : '0%', '≥85%',
        $ssylokVsego && $ssylkiVProze / $ssylokVsego >= 0.85],
];
$prOk = count(array_filter($priyomy, fn($x) => $x[2]));
if ($prOk < count($priyomy)) { $provaly[] = 'приёмы'; }

// ── 3. техническая мерка ────────────────────────────────────────────
$dom = (function (string $frag): ?DOMDocument {
    $d = new DOMDocument();
    $prev = libxml_use_internal_errors(true);
    $ok = $d->loadHTML('<?xml encoding="utf-8"?><html><body>' . $frag . '</body></html>',
        LIBXML_NOWARNING | LIBXML_NOERROR);
    libxml_clear_errors();
    libxml_use_internal_errors($prev);
    return $ok ? $d : null;
})($html);
$seo = new SeoMetrics($dom, $html);

$citat = $seo->quoteCount();
$vnesh = count($seo->links('', '/main')['external']);
$nofollow = 0;
foreach (['internal', 'external'] as $vid) {
    foreach ($seo->links('', '/main')[$vid] as $it) { if ($it['nofollow']) { $nofollow++; } }
}
$spamKey = '';
foreach (['казино', 'бонус', 'зеркало', 'слот', 'регистрация'] as $kk) {
    if ($seo->strongKeywordSpam($kk)) { $spamKey = $kk; break; }
}

$tehnika = [
    'H1 в фрагменте' => [$seo->headingCount(1), '0', $seo->headingCount(1) === 0],
    'H4 и ниже' => [$seo->headingCount(4), '0', $seo->headingCount(4) === 0],
    'иерархия заголовков' => [$seo->headingHierarchyOk() ? 'цела' : 'пропуск уровня', 'цела',
        $seo->headingHierarchyOk()],
    'цитат blockquote' => (function (int $n) use ($profil) {
        // Полоса из профиля: август держал 7–12 цитат на главной, новый корпус — 2–7.
        $b = $profil['семерка']['цитата_blockquote']['полоса_на_главной'] ?? [7, 12];
        return [$n, $b[0] . '–' . $b[1], $n >= $b[0] && $n <= $b[1]];
    })($citat),
    'текст/код' => [$seo->textHtmlRatio() . '%', '70–90%',
        $seo->textHtmlRatio() >= 70 && $seo->textHtmlRatio() <= 90],
    'nofollow' => [$nofollow, '0', $nofollow === 0],
    'внешних ссылок' => [$vnesh, '0–1', $vnesh <= 1],
    'переспам выделением' => [$spamKey === '' ? 'нет' : $spamKey, 'нет', $spamKey === ''],
    'картинок' => [$seo->imgCount(), '0', $seo->imgCount() === 0],
];
$tehOk = count(array_filter($tehnika, fn($x) => $x[2]));
if ($tehOk < count($tehnika)) { $provaly[] = 'техника'; }

// ── 4. уникальность ─────────────────────────────────────────────────
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

$hudshaya = 0.0; $hudshiy = '—'; $povtorZag = []; $sosed = '—'; $hudshieShingle = [];
$put = is_dir($korpus) ? $korpus : $root . '/' . $korpus;
foreach (glob(rtrim($put, '/') . '/*', GLOB_ONLYDIR) ?: [] as $other) {
    if (!is_file("$other/main.html")) { continue; }
    if (realpath($other) === realpath($dir)) { continue; }
    $ot = chist(preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', (string) file_get_contents("$other/main.html")));
    $os = $shingle($ot);
    $min = min(count($nashShingle), count($os));
    if ($min) {
        $v = count(array_intersect_key($nashShingle, $os)) / $min * 100;
        if ($v > $hudshaya) { $hudshaya = $v; $hudshiy = basename($other); $hudshieShingle = $os; }
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

printf("\n── техника %d/%d ──\n", $tehOk, count($tehnika));
foreach ($tehnika as $n => [$est, $nado, $ok]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 30, true) . $pad((string) $est, 12) . '   нужно ' . $nado . "\n";
}

// Формат строк тут тот же, что у параметров и приёмов: «✗ имя  значение  нужно X».
// Замер генератора вычитывает промахи именно по нему, и пока уникальность
// печаталась своим видом, провал по ней до брифа писателя не доходил — правка
// уходила в следующий круг вслепую.
printf("\n── уникальность ──\n");
echo '  ' . ($hudshaya < $porog ? '·' : '✗') . ' ' . $pad('худшая пара по шинглам', 30, true)
    . $pad(sprintf('%.2f%%', $hudshaya), 12) . '   нужно <' . rtrim(rtrim(sprintf('%.2f', $porog), '0'), '.') . '%'
    . '   с ' . $hudshiy . "\n";
echo '  ' . ($povtorZag ? '✗' : '·') . ' ' . $pad('дословных повторов заголовков', 30, true)
    . $pad((string) count($povtorZag), 12) . "   нужно 0\n";
foreach ($povtorZag as $k => $v) {
    echo '      · ' . mb_substr($k, 0, 60) . "  [$v]\n";
}

// ГДЕ именно совпало, а не только сколько.
//
// Процент сам по себе писателю бесполезен: он говорит, что страницу надо
// переписывать, и молчит о том, какую её часть. На живых прогонах это стоило
// по два-три круга вслепую — переписывали абзацы, а совпадали таблицы и
// вопросы FAQ. Здесь печатаются блоки, у которых больше половины шинглов
// нашлись у соседа: ровно их и надо переписать, остальное трогать незачем.
if ($hudshaya >= $porog && $hudshieShingle) {
    $bloki = [];
    if (preg_match_all('~<(p|li|td|summary|blockquote)\b[^>]*>(.*?)</\1>~is', $html, $bm, PREG_SET_ORDER)) {
        foreach ($bm as $b) {
            $t = chist($b[2]);
            $sh = $shingle($t);
            if (count($sh) < 3) { continue; }
            $dolya = count(array_intersect_key($sh, $hudshieShingle)) / count($sh);
            if ($dolya > 0.5) { $bloki[] = [$dolya, $b[1], $t]; }
        }
    }
    usort($bloki, fn($a, $b) => $b[0] <=> $a[0]);
    if ($bloki) {
        echo "      где совпало (доля шинглов блока, найденных у соседа):\n";
        foreach (array_slice($bloki, 0, 12) as [$d, $tag, $t]) {
            printf("      · %3d%% <%s> %s\n", (int) round($d * 100), $tag, mb_substr($t, 0, 70));
        }
    }
}

printf("\nИТОГ: %s\n", $provaly ? 'НЕ ПРОЙДЕНО — ' . implode(', ', $provaly) : 'пройдено');
exit($provaly ? 1 : 0);

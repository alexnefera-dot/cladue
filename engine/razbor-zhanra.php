<?php
declare(strict_types=1);

/**
 * Разбор жанра корпуса: не «сколько чего», а «как оно сделано».
 *
 *   php engine/razbor-zhanra.php <папка> [--школа=проза|конструктор] [--json]
 *
 * razbros-korpusa.php показывает, какие из 55 полей фабрика держит. Этого мало:
 * поле «слов в абзаце» может держаться, а абзац при этом устроен иначе. Здесь
 * разбирается то, что полями не меряется, — и разбирается ТОЛЬКО на корпусе,
 * потому что на одной странице любая находка неотличима от случайности.
 *
 * Четырнадцать разделов:
 *   1. зачин           — из чего собран первый экран
 *   2. финал           — чем страницу закрывают
 *   3. заголовок       — формула «ключ : хвост» и доля голого ключа
 *   4. внутренняя      — каркас страницы второго уровня
 *   5. словарь фактов  — сколько разных чисел фабрика вообще знает
 *   6. частотность     — какое слово в тексте самое частое и где стоит ключ
 *   7. ритм            — распределение длин абзаца и предложения
 *   8. абзац           — чем открывается и сцеплен ли с соседним
 *   9. морфология      — какая глагольная форма несёт текст
 *  10. таблица         — что в колонках и какая ячейка
 *  11. анкор           — как ссылка встроена во фразу
 *  12. FAQ             — что именно закрывают вопросы
 *  13. оценка          — карта критериев и отзывы со звёздами
 *  14. тон             — чего в тексте больше, обещания или предупреждения
 *  15. каннибализация  — пересекается ли главная со своими же страницами
 */

const PAGES_Z = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
const BLOCK_TAIL_Z = '~(block|section|dashboard|hero|pillars|quotes-list|strip|panel|widget|banner|card)$~';

$root = $argv[1] ?? '';
$shkola = '';
$asJson = in_array('--json', $argv, true);
foreach (array_slice($argv, 2) as $a) {
    if (str_starts_with($a, '--школа=')) { $shkola = substr($a, strlen('--школа=')); }
}
if ($root === '' || !is_dir($root)) {
    fwrite(STDERR, "usage: php engine/razbor-zhanra.php <папка> [--школа=проза|конструктор] [--json]\n");
    exit(1);
}

/** strip_tags глотает всё от голой «<» до следующего «>» — у доноров так теряется до 80% страницы. */
function chisto(string $h): string
{
    $h = preg_replace('~(?is)<(script|style)\b.*?</\1>~', ' ', $h);
    $h = preg_replace('~<[a-zA-Z/!][^>]*>~', ' ', (string) $h);
    return html_entity_decode((string) $h, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}
function slova(string $t): array
{
    preg_match_all('~[\p{L}\p{N}]+~u', $t, $m);
    return $m[0];
}
function med(array $v)
{
    if (!$v) { return 0; }
    sort($v);
    return $v[intdiv(count($v), 2)];
}
function kvartil(array $v, float $q)
{
    if (!$v) { return 0; }
    sort($v);
    return $v[(int) (count($v) * $q)];
}

// ── отбор сайтов ────────────────────────────────────────────────────
$dirs = [];
foreach (glob(rtrim($root, '/') . '/*', GLOB_ONLYDIR) ?: [] as $d) {
    $b = [];
    foreach (glob("$d/*.html") ?: [] as $f) {
        preg_match_all('~<(?:section|div|article|aside)\s+class="([a-z][a-z0-9_-]*)((?:\s+[a-z0-9_-]+)*)"~i',
            (string) file_get_contents($f), $m, PREG_SET_ORDER);
        foreach ($m as $x) {
            if (preg_match(BLOCK_TAIL_Z, $x[1]) || str_contains($x[2], 'variant-')) { $b[$x[1]] = 1; }
        }
    }
    $sh = count($b) >= 5 ? 'конструктор' : 'проза';
    if ($shkola === '' || $sh === $shkola) { $dirs[] = $d; }
}
if (!$dirs) { fwrite(STDERR, "нечего разбирать\n"); exit(1); }
$N = count($dirs);

$out = ['сайтов' => $N];

// ── 1. зачин ────────────────────────────────────────────────────────
$zachin = ['слов' => [], 'офиц+рег+зерк' => 0, 'список-оглавление' => 0, 'таблица-паспорт' => 0, 'первое лицо' => 0];
foreach ($dirs as $d) {
    $h = (string) file_get_contents("$d/main.html");
    $lead = preg_split('~(?i)<h2\b~', $h, 2)[0];
    $t = chisto($lead);
    $zachin['слов'][] = count(slova($t));
    $lt = mb_strtolower($t);
    $hits = 0;
    foreach (['~официальн~u', '~регистрац~u', '~зеркал~u'] as $re) { if (preg_match($re, $lt)) { $hits++; } }
    if ($hits === 3) { $zachin['офиц+рег+зерк']++; }
    if (preg_match('~(?i)<(ul|ol)\b~', $lead)
        || preg_match('~[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}][^\x{1F000}-\x{1FAFF}]{5,60}[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}]~u', $t)) {
        $zachin['список-оглавление']++;
    }
    if (preg_match('~(?i)<table\b~', $lead)) { $zachin['таблица-паспорт']++; }
    if (preg_match('~(?<![\p{L}])(я|мне|мой|меня)(?![\p{L}])~u', $lt)) { $zachin['первое лицо']++; }
}
$out['зачин'] = [
    'слов медиана' => med($zachin['слов']), 'слов q1' => kvartil($zachin['слов'], .25),
    'слов q3' => kvartil($zachin['слов'], .75),
    'официальный+регистрация+зеркало' => $zachin['офиц+рег+зерк'] . "/$N",
    'список-оглавление' => $zachin['список-оглавление'] . "/$N",
    'таблица-паспорт' => $zachin['таблица-паспорт'] . "/$N",
    'от первого лица' => $zachin['первое лицо'] . "/$N",
];

// ── 2. финал ────────────────────────────────────────────────────────
$finalKlass = [
    'плюсы и минусы' => '~плюс|минус~iu',
    'итог / вердикт / чек-лист' => '~итог|вердикт|чек[-\s]?лист|заключ|финал|сухой остаток|послесловие|общий балл|рекомендац~iu',
    'отзывы' => '~отзыв|комментар~iu',
    'FAQ' => '~вопрос|faq|ответ~iu',
];
$posle = []; $fin = array_fill_keys(array_keys($finalKlass), 0); $predfin = $fin;
foreach ($dirs as $d) {
    $h = (string) file_get_contents("$d/main.html");
    preg_match_all('~(?is)<h2[^>]*>(.*?)</h2>~', $h, $m);
    $hs = array_values(array_filter(array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', chisto($x))), $m[1])));
    if (!$hs) { continue; }
    foreach ($finalKlass as $n => $re) {
        if (preg_match($re, end($hs))) { $fin[$n]++; }
        if (count($hs) > 1 && preg_match($re, $hs[count($hs) - 2])) { $predfin[$n]++; }
    }
    $p = strrpos($h, '<h2');
    if ($p !== false) { $posle[] = count(slova(chisto(substr($h, $p)))); }
}
$out['финал'] = ['слов после последнего H2, медиана' => med($posle)];
foreach ($fin as $n => $c) { $out['финал']["последний H2 — $n"] = $c . "/$N"; }
foreach ($predfin as $n => $c) { $out['финал']["предпоследний H2 — $n"] = $c . "/$N"; }

// ── 3. заголовок ────────────────────────────────────────────────────
$hAll = []; $hRazd = 0; $hGoly = 0; $hLen = []; $levo = [];
foreach ($dirs as $d) {
    foreach (glob("$d/*.html") ?: [] as $f) {
        preg_match_all('~(?is)<(h2|h3)[^>]*>(.*?)</\1>~', (string) file_get_contents($f), $m, PREG_SET_ORDER);
        foreach ($m as $x) {
            $t = trim(preg_replace('~\s+~u', ' ', chisto($x[2])));
            $t = trim(preg_replace('~%brand_name_[a-z]+%~u', 'Б', $t));
            if ($t === '') { continue; }
            $hAll[mb_strtolower($t)][basename($d)] = 1;
            $hLen[] = count(slova($t));
            if (preg_match('~^(.{4,60}?)\s*[:—–-]\s+(.+)$~u', $t, $p)) {
                $hRazd++;
                $levo[mb_strtolower(trim($p[1]))][basename($d)] = 1;
            }
            if (preg_match('~^[а-яё]~u', mb_substr($t, 0, 1))) { $hGoly++; }
        }
    }
}
$vsegoH = array_sum(array_map('count', $hAll));
$povtor = array_filter($hAll, fn($x) => count($x) > 1);
$levoPovtor = array_filter($levo, fn($x) => count($x) > 2);
arsort($levoPovtor);
$out['заголовок'] = [
    'всего' => $vsegoH, 'разных' => count($hAll),
    'слов медиана' => med($hLen),
    'с разделителем «ключ : хвост»' => round($hRazd / max(1, $vsegoH) * 100) . '%',
    'начинается со строчной (голый ключ)' => round($hGoly / max(1, $vsegoH) * 100, 1) . '%',
    'дословных повторов между сайтами' => count($povtor),
    'общих левых частей (у 3+ сайтов)' => count($levoPovtor),
    'частые левые части' => array_slice(array_map(fn($x) => count($x), $levoPovtor), 0, 12, true),
];

// ── 4. внутренняя страница ──────────────────────────────────────────
$vn = ['страниц' => 0, 'ровно 2 H2' => 0, 'последний H2 — FAQ' => 0];
$vnH3 = []; $roli = ['определение' => 0, 'инструкция' => 0, 'таблица' => 0, 'риски' => 0, 'итог' => 0];
$roliRe = [
    'определение' => '~^что такое|что это|зачем нужн|коротко о|кратко о~iu',
    'инструкция' => '~^как |пошагов|инструкц|шаг \d|порядок|алгоритм|чек[-\s]?лист~iu',
    'таблица' => '~^таблиц|сводн|сравнен~iu',
    'риски' => '~безопасн|риск|ошибк|проблем|мошен|осторож|внимани~iu',
    'итог' => '~итог|вывод|финал|совет|напомин|резюме~iu',
];
foreach ($dirs as $d) {
    foreach (PAGES_Z as $p) {
        if ($p === 'main' || !is_file("$d/$p.html")) { continue; }
        $h = (string) file_get_contents("$d/$p.html");
        $vn['страниц']++;
        preg_match_all('~(?is)<h2[^>]*>(.*?)</h2>~', $h, $m);
        $hs = array_values(array_filter(array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $m[1])));
        if (count($hs) === 2) { $vn['ровно 2 H2']++; }
        if ($hs && preg_match('~вопрос|faq|ответ~iu', end($hs))) { $vn['последний H2 — FAQ']++; }
        preg_match_all('~(?is)<h3[^>]*>(.*?)</h3>~', $h, $m3);
        $h3 = array_values(array_filter(array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $m3[1])));
        $vnH3[] = count($h3);
        foreach ($roliRe as $n => $re) {
            if (array_filter($h3, fn($x) => preg_match($re, $x))) { $roli[$n]++; }
        }
    }
}
$vsegoVn = max(1, $vn['страниц']);
$out['внутренняя'] = [
    'страниц' => $vn['страниц'],
    'ровно 2 H2' => round($vn['ровно 2 H2'] / $vsegoVn * 100) . '%',
    'последний H2 — FAQ' => round($vn['последний H2 — FAQ'] / $vsegoVn * 100) . '%',
    'H3 медиана' => med($vnH3),
    'роли H3' => array_map(fn($c) => round($c / $vsegoVn * 100) . '%', $roli),
];

// ── 5. словарь фактов ───────────────────────────────────────────────
$rtp = []; $bonus = [];
foreach ($dirs as $d) {
    foreach (glob("$d/*.html") ?: [] as $f) {
        $t = chisto((string) file_get_contents($f));
        if (preg_match_all('~(?:rtp|отдач\w*)\D{0,25}?(\d{2}[.,]\d{1,2})~iu', $t, $m)) {
            foreach ($m[1] as $v) { $k = str_replace(',', '.', $v); $rtp[$k] = ($rtp[$k] ?? 0) + 1; }
        }
        if (preg_match_all('~(\d{2,3})\s*%\s*(?:до|бонус)~iu', $t, $m)) {
            foreach ($m[1] as $v) { $bonus[$v] = ($bonus[$v] ?? 0) + 1; }
        }
    }
}
arsort($rtp); arsort($bonus);
$out['словарь фактов'] = [
    'разных значений RTP на весь корпус' => count($rtp),
    'RTP' => array_slice($rtp, 0, 8, true),
    'разных процентов бонуса' => count($bonus),
    'бонус' => array_slice($bonus, 0, 8, true),
];

// ── 4. частотность ──────────────────────────────────────────────────
$topWord = []; $rangi = [];
$keys = ['казино', 'бонус', 'зеркал', 'слот', 'регистрац', 'лиценз'];
foreach ($dirs as $d) {
    $t = mb_strtolower(chisto((string) file_get_contents("$d/main.html")));
    $t = preg_replace('~%brand_name_[a-z]+%~u', ' бренд ', $t);
    preg_match_all('~[\p{L}]{3,}~u', $t, $m);
    $f = array_count_values($m[0]);
    arsort($f);
    $topWord[key($f)] = ($topWord[key($f)] ?? 0) + 1;
    $rank = array_flip(array_keys($f));
    foreach ($keys as $k) {
        $best = PHP_INT_MAX; $c = 0;
        foreach ($f as $w => $n) { if (mb_strpos($w, $k) === 0) { $c += $n; $best = min($best, $rank[$w] + 1); } }
        if ($best !== PHP_INT_MAX) { $rangi[$k][] = $best; }
    }
}
arsort($topWord);
$out['частотность'] = [
    'самое частое слово сайта' => $topWord,
    'ранг ключа (медиана по сайтам)' => array_map(fn($v) => med($v), $rangi),
];

// ── 5. ритм ─────────────────────────────────────────────────────────
$pL = []; $sL = [];
foreach ($dirs as $d) {
    preg_match_all('~(?is)<p\b[^>]*>(.*?)</p>~', (string) file_get_contents("$d/main.html"), $m);
    foreach ($m[1] as $x) {
        $t = trim(preg_replace('~\s+~u', ' ', chisto($x)));
        if ($t === '') { continue; }
        $n = count(slova($t));
        if (!$n) { continue; }
        $pL[] = $n;
        foreach (preg_split('~(?<=[.!?…])\s+~u', $t) as $s) {
            $k = count(slova($s));
            if ($k) { $sL[] = $k; }
        }
    }
}
$dolya = function (array $v, int $lo, ?int $hi) {
    $c = count(array_filter($v, fn($x) => $x > $lo && ($hi === null || $x <= $hi)));
    return round($c / max(1, count($v)) * 100, 1);
};
$out['ритм'] = [
    'абзацев' => count($pL), 'слов в абзаце медиана' => med($pL),
    'абзацы ≤10 слов %' => $dolya($pL, 0, 10), '10–30 %' => $dolya($pL, 10, 30),
    '30–60 %' => $dolya($pL, 30, 60), '>60 %' => $dolya($pL, 60, null),
    'предложений' => count($sL), 'слов в предложении медиана' => med($sL),
    'предложения ≤5 слов %' => $dolya($sL, 0, 5), '5–15 %' => $dolya($sL, 5, 15),
    '15–30 %' => $dolya($sL, 15, 30), '>30 %' => $dolya($sL, 30, null),
];

// ── 8. абзац ────────────────────────────────────────────────────────
// Связки в начале абзаца — маркер «сочинения»: у доноров их почти нет,
// абзац стоит сам по себе и открывается субъектом, условием или ответом.
$pFirst = []; $pStrong = 0; $pAll = 0;
$svyazkaRe = '~^(но|однако|зато|поэтому|итак|значит|кроме|более|также|далее|затем|потом|впрочем|наконец)$~u';
$svyazok = 0;
foreach ($dirs as $d) {
    foreach (glob("$d/*.html") ?: [] as $f) {
        if (!preg_match_all('~(?is)<p\b[^>]*>(.*?)</p>~', (string) file_get_contents($f), $m)) { continue; }
        foreach ($m[1] as $x) {
            $t = trim(preg_replace('~\s+~u', ' ', chisto($x)));
            if (mb_strlen($t) < 20) { continue; }
            $pAll++;
            if (preg_match('~^\s*<strong~i', trim($x))) { $pStrong++; }
            if (preg_match('~^[«"\p{Pd}\s]*([\p{L}]+)~u', $t, $w)) {
                $lw = mb_strtolower($w[1]);
                $pFirst[$lw] = ($pFirst[$lw] ?? 0) + 1;
                if (preg_match($svyazkaRe, $lw)) { $svyazok++; }
            }
        }
    }
}
arsort($pFirst);
$out['абзац'] = [
    'абзацев' => $pAll,
    'открыт <strong>' => round($pStrong / max(1, $pAll) * 100, 1) . '%',
    'открыт связкой (но/однако/поэтому…)' => round($svyazok / max(1, $pAll) * 100, 1) . '%',
    'первое слово' => array_map(fn($c) => round($c / max(1, $pAll) * 100, 1) . '%', array_slice($pFirst, 0, 8, true)),
];

// ── 9. морфология ───────────────────────────────────────────────────
$morf = [
    'инфинитив' => '~(?<![\p{L}])[а-яё]{3,}(?:ть|ти)(?![\p{L}])~u',
    'прошедшее' => '~(?<![\p{L}])[а-яё]{3,}(?:ал|ил|ел|ыл|ла|ло|ли)(?![\p{L}])~u',
    'повелительное' => '~(?<![\p{L}])[а-яё]{3,}(?:йте|ите)(?![\p{L}])~u',
    'страдательное' => '~(?<![\p{L}])[а-яё]{3,}(?:ется|ются)(?![\p{L}])~u',
    'условие «если»' => '~(?<![\p{L}])если(?![\p{L}])~u',
    'модальное «можно/нужно»' => '~(?<![\p{L}])(?:можно|нужно|стоит|следует|надо|придётся)(?![\p{L}])~u',
    'уступка «но/однако»' => '~(?<![\p{L}])(?:но|однако|зато|хотя)(?![\p{L}])~u',
    'причина «потому что»' => '~потому что|так как|поскольку~u',
    'вводное «например»' => '~например|к примеру|скажем~u',
];
$mres = array_fill_keys(array_keys($morf), 0); $mslov = 0;
foreach ($dirs as $d) {
    $t = '';
    foreach (glob("$d/*.html") ?: [] as $f) { $t .= ' ' . mb_strtolower(chisto((string) file_get_contents($f))); }
    $mslov += count(slova($t));
    foreach ($morf as $k => $re) { $mres[$k] += preg_match_all($re, $t); }
}
$out['морфология'] = ['слов' => $mslov]
    + array_map(fn($v) => round($v / max(1, $mslov) * 100, 2), $mres);

// ── 10. таблица ─────────────────────────────────────────────────────
$kol = []; $yach = []; $yachNum = 0; $yachAll = 0;
foreach ($dirs as $d) {
    foreach (glob("$d/*.html") ?: [] as $f) {
        preg_match_all('~(?is)<table\b.*?</table>~', (string) file_get_contents($f), $tm);
        foreach ($tm[0] as $tab) {
            preg_match_all('~(?is)<th\b[^>]*>(.*?)</th>~', $tab, $th);
            $head = array_map(fn($x) => mb_strtolower(trim(preg_replace('~\s+~u', ' ', strip_tags($x)))), $th[1]);
            if (!$head && preg_match('~(?is)<tr\b[^>]*>(.*?)</tr>~', $tab, $tr)) {
                preg_match_all('~(?is)<td\b[^>]*>(.*?)</td>~', $tr[1], $td);
                $head = array_map(fn($x) => mb_strtolower(trim(preg_replace('~\s+~u', ' ', strip_tags($x)))), $td[1]);
            }
            foreach ($head as $i => $hh) { if ($hh !== '') { $kol[$i][$hh] = ($kol[$i][$hh] ?? 0) + 1; } }
            preg_match_all('~(?is)<td\b[^>]*>(.*?)</td>~', $tab, $tdm);
            foreach ($tdm[1] as $c) {
                $c = trim(preg_replace('~\s+~u', ' ', chisto($c)));
                if ($c === '') { continue; }
                $yachAll++;
                $yach[] = count(slova($c));
                if (preg_match('~\d~u', $c)) { $yachNum++; }
            }
        }
    }
}
$out['таблица'] = ['ячеек' => $yachAll, 'слов в ячейке медиана' => med($yach),
    'ячеек с цифрой' => round($yachNum / max(1, $yachAll) * 100) . '%'];
foreach ([0, 1, 2] as $i) {
    if (!isset($kol[$i])) { continue; }
    arsort($kol[$i]);
    $out['таблица']['колонка ' . ($i + 1) . ' (разных ' . count($kol[$i]) . ')'] = array_slice($kol[$i], 0, 6, true);
}

// ── 11. анкор ───────────────────────────────────────────────────────
$ank = []; $vFraze = 0; $ssylok = 0; $aLen = [];
foreach ($dirs as $d) {
    foreach (glob("$d/*.html") ?: [] as $f) {
        $h = (string) file_get_contents($f);
        $ssylok += preg_match_all('~(?is)<a\s[^>]*href="/[a-z]*"~', $h);
        if (!preg_match_all('~(?is)<(p|li)\b[^>]*>(.*?)</\1>~', $h, $bm, PREG_SET_ORDER)) { continue; }
        foreach ($bm as $b) {
            if (!preg_match_all('~(?is)<a\s[^>]*href="/[a-z]*"[^>]*>(.*?)</a>~', $b[2], $am)) { continue; }
            foreach ($am[1] as $x) {
                $t = trim(preg_replace('~\s+~u', ' ', strip_tags($x)));
                if ($t === '') { continue; }
                $vFraze++;
                $ank[mb_strtolower($t)] = ($ank[mb_strtolower($t)] ?? 0) + 1;
                $aLen[] = count(slova($t));
            }
        }
    }
}
$odin = count(array_filter($ank, fn($x) => $x === 1));
$out['анкор'] = [
    'внутренних ссылок' => $ssylok,
    'внутри <p> и <li>' => round($vFraze / max(1, $ssylok) * 100) . '%',
    'слов в анкоре медиана' => med($aLen),
    'разных анкоров' => count($ank),
    'одиночек' => round($odin / max(1, count($ank)) * 100) . '%',
];

// ── 12. FAQ ─────────────────────────────────────────────────────────
$q = [];
foreach ($dirs as $d) {
    foreach (glob("$d/*.html") ?: [] as $f) {
        // <summary itemprop="name"> ловится обоими выражениями, поэтому берём только summary,
        // а Question учитываем лишь там, где summary нет вовсе.
        $h = (string) file_get_contents($f);
        preg_match_all('~(?is)<summary[^>]*>(.*?)</summary>~', $h, $m1);
        $src = $m1[1];
        if (!$src) {
            preg_match_all('~(?is)itemtype="https://schema\.org/Question".*?itemprop="name"[^>]*>(.*?)<~s', $h, $m2);
            $src = $m2[1];
        }
        foreach ($src as $t) {
            $t = trim(preg_replace('~\s+~u', ' ', chisto($t)));
            if (mb_strlen($t) < 8) { continue; }
            $q[] = $t;
        }
    }
}
$klass = [
    'сбой / отказ' => '~не (?:прих|приш|начисл|работ|отобра|груз|заход|получ|срабат|актив|подтвер|прошёл|прошел|уда)|заблок|ошибк|отказ|завис|сброс|пропал|потерял|застрял|задерж|не могу|отклон|сгорел|исчез~iu',
    'инструкция «как»' => '~^(?:как|каким образом|где|куда)\b~iu',
    'разрешение «можно ли»' => '~^(?:можно ли|могу ли|можно|разрешено)~iu',
    'объяснение «почему»' => '~^(?:почему|что такое|чем отлич|зачем)~iu',
    'безопасность' => '~безопас|мошен|фишинг|скам|развод|защит|kyc|верифик|документ~iu',
];
$fq = ['вопросов' => count($q), 'на сайт' => round(count($q) / $N, 1), 'слов медиана' => med(array_map(fn($x) => count(slova($x)), $q))];
foreach ($klass as $n => $re) {
    $fq[$n] = round(count(array_filter($q, fn($t) => preg_match($re, $t))) / max(1, count($q)) * 100) . '%';
}
$fq['с цифрой'] = round(count(array_filter($q, fn($t) => preg_match('~\d~u', $t))) / max(1, count($q)) * 100) . '%';
$out['FAQ'] = $fq;

// ── 7. оценка ───────────────────────────────────────────────────────
$kart = 0; $ball = []; $krit = []; $zvezdy = []; $otzyv = 0;
foreach ($dirs as $d) {
    $had = false;
    foreach (glob("$d/*.html") ?: [] as $f) {
        $h = (string) file_get_contents($f);
        if (preg_match_all('~(?is)score-label"[^>]*>\s*(.*?)\s*</p>\s*<p class="[a-z-]*score-val">\s*(.*?)\s*</p>~', $h, $m, PREG_SET_ORDER)) {
            $had = true;
            foreach ($m as $x) {
                $krit[] = trim(preg_replace('~\s+~u', ' ', strip_tags($x[1])));
                $ball[] = (float) str_replace(',', '.', $x[2]);
            }
        }
        if (preg_match_all('~(?is)</time>\s*/\s*<span>\s*(\d)\s*</span>~', $h, $z)) {
            foreach ($z[1] as $v) { $zvezdy[$v] = ($zvezdy[$v] ?? 0) + 1; $otzyv++; }
        }
    }
    if ($had) { $kart++; }
}
$core = ['каталог' => 0, 'бонус' => 0, 'касс' => 0, 'поддержк' => 0, 'безопасн' => 0, 'мобайл|мобил' => 0];
foreach ($core as $c => $_) { $core[$c] = count(array_filter($krit, fn($x) => preg_match("~$c~iu", $x))); }
ksort($zvezdy);
$out['оценка'] = [
    'сайтов с оценочной картой' => $kart . "/$N",
    'критериев' => count($krit), 'шестёрка' => $core,
    'балл медиана' => $ball ? med($ball) : 0, 'балл мин' => $ball ? min($ball) : 0, 'балл макс' => $ball ? max($ball) : 0,
    'отзывов со звёздами' => $otzyv, 'распределение звёзд' => $zvezdy,
];

// ── 8. тон ──────────────────────────────────────────────────────────
$ton = ['обещание' => 0, 'предупреждение' => 0, 'призыв ты' => 0, 'призыв вы' => 0];
foreach ($dirs as $d) {
    $a = '';
    foreach (glob("$d/*.html") ?: [] as $f) { $a .= ' ' . (string) file_get_contents($f); }
    $ton['обещание'] += preg_match_all('~выигра|заработа|поднять|сорвать куш|джекпот~iu', $a);
    $ton['предупреждение'] += preg_match_all('~риск|проигр|зависим|ответственн|не играй|18\+|лимит~iu', $a);
    $ton['призыв ты'] += preg_match_all('~зарегистрируй|регистрируйся|жми|нажми|переходи|заходи|качай|скачай|попробуй|проверь~iu', $a);
    $ton['призыв вы'] += preg_match_all('~зарегистрируйтесь|нажмите|перейдите|проверьте|попробуйте|скачайте|убедитесь|обратите~iu', $a);
}
$out['тон'] = [
    'обещание выигрыша' => $ton['обещание'], 'предупреждение о риске' => $ton['предупреждение'],
    'предупреждение : обещание' => round($ton['предупреждение'] / max(1, $ton['обещание']), 1) . ' : 1',
    'призывов на сайт' => round(($ton['призыв ты'] + $ton['призыв вы']) / $N, 1),
];

// ── 15. регистр ─────────────────────────────────────────────────────
// Маска сайта строится формулой «X — это Y», где Y берётся из мира метафоры:
// «лицензия — это пламя», «лицензия — это семена», «документ — это капля в гроте».
// Считаем и сам механизм, и общий сленговый фон, который у масок сквозной.
$sleng = ['кайф', 'кринж', 'база', 'душно', 'изи', 'движ', 'мем', 'фарт', 'флекс', 'залип',
    'вайб', 'хайп', 'краш', 'скилл', 'топчик', 'рофл', 'чилл', 'лут', 'пруф'];
$slCnt = array_fill_keys($sleng, 0); $slSites = array_fill_keys($sleng, 0);
$slSlov = 0; $sravnenij = 0;
foreach ($dirs as $d) {
    $t = '';
    foreach (glob("$d/*.html") ?: [] as $f) { $t .= ' ' . mb_strtolower(chisto((string) file_get_contents($f))); }
    $slSlov += count(slova($t));
    $sravnenij += preg_match_all('~(?<![\p{L}])(?:это|—)\s+(?:как|это)\s~u', $t);
    foreach ($sleng as $w) {
        $c = preg_match_all('~(?<![\p{L}])' . $w . '~u', $t);
        $slCnt[$w] += $c;
        if ($c) { $slSites[$w]++; }
    }
}
arsort($slCnt);
$out['регистр'] = [
    'сленга всего' => array_sum($slCnt),
    'на 100 слов' => round(array_sum($slCnt) / max(1, $slSlov) * 100, 2),
    'сравнений «X это как Y» на сайт' => round($sravnenij / $N, 1),
];
$chastye = [];
foreach (array_slice(array_keys(array_filter($slCnt)), 0, 8) as $w) { $chastye[$w] = $slSites[$w] . "/$N"; }
$out['регистр']['частые'] = $chastye;

// ── 16. граф перелинковки ───────────────────────────────────────────
// Матрица «страница → страница» по всему корпусу: видно и плотность сетки,
// и страницы-сироты, на которые не ссылается вообще никто.
$uzly = PAGES_Z;
$mat = array_fill(0, count($uzly), array_fill(0, count($uzly), 0));
$ishod = array_fill(0, count($uzly), 0);
$sajtov = 0;
foreach ($dirs as $d) {
    $sajtov++;
    foreach ($uzly as $i => $p) {
        if (!is_file("$d/$p.html")) { continue; }
        preg_match_all('~<a\s[^>]*href="(/[a-z]*)"~i', (string) file_get_contents("$d/$p.html"), $m);
        $ishod[$i] += count($m[1]);
        $est = [];
        foreach ($m[1] as $href) {
            $c = trim($href, '/');
            if ($c === '') { $c = 'main'; }
            $j = array_search($c, $uzly, true);
            if ($j !== false && $j !== $i) { $est[$j] = 1; }
        }
        foreach (array_keys($est) as $j) { $mat[$i][$j]++; }
    }
}
$vhod = array_fill(0, count($uzly), 0);
foreach ($mat as $i => $row) { foreach ($row as $j => $v) { $vhod[$j] += $v; } }
$out['граф'] = ['ссылок со страницы' => [], 'страниц ссылается на неё (из 6)' => []];
foreach ($uzly as $i => $p) {
    $out['граф']['ссылок со страницы'][$p] = round($ishod[$i] / max(1, $sajtov), 1);
    $vh = count(array_filter($mat, fn($row) => ($row[$i] ?? 0) > 0));
    $out['граф']['страниц ссылается на неё (из 6)'][$p] = $vh;
}
$siroty = [];
foreach ($uzly as $i => $p) { if ($vhod[$i] === 0) { $siroty[] = $p; } }
$out['граф']['сироты'] = $siroty ? implode(', ', $siroty) : '—';

// ── 17. каннибализация ──────────────────────────────────────────────
// Все семь страниц пишут об одном казино и покрывают пересекающиеся темы.
// Если главная переиспользует свои же формулировки — это видно здесь.
$shing = function (string $t): array {
    $t = mb_strtolower(preg_replace('~%[a-z_]+%~u', ' бренд ', $t));
    $w = slova($t);
    $s = [];
    for ($i = 0; $i + 6 <= count($w); $i++) { $s[implode(' ', array_slice($w, $i, 6))] = 1; }
    return $s;
};
$mVn = []; $vnVn = [];
foreach ($dirs as $d) {
    if (!is_file("$d/main.html")) { continue; }
    $sets = ['main' => $shing(chisto((string) file_get_contents("$d/main.html")))];
    foreach (PAGES_Z as $p) {
        if ($p === 'main' || !is_file("$d/$p.html")) { continue; }
        $sets[$p] = $shing(chisto((string) file_get_contents("$d/$p.html")));
    }
    $names = array_keys($sets);
    for ($i = 0; $i < count($names); $i++) {
        for ($j = $i + 1; $j < count($names); $j++) {
            $a = $sets[$names[$i]]; $b = $sets[$names[$j]];
            $min = min(count($a), count($b));
            if (!$min) { continue; }
            $v = count(array_intersect_key($a, $b)) / $min * 100;
            if ($names[$i] === 'main') { $mVn[] = $v; } else { $vnVn[] = $v; }
        }
    }
}
$out['каннибализация'] = [
    'главная ↔ внутренние, среднее' => $mVn ? round(array_sum($mVn) / count($mVn), 2) . '%' : '—',
    'главная ↔ внутренние, макс' => $mVn ? round(max($mVn), 2) . '%' : '—',
    'внутренние между собой, среднее' => $vnVn ? round(array_sum($vnVn) / count($vnVn), 2) . '%' : '—',
    'внутренние между собой, макс' => $vnVn ? round(max($vnVn), 2) . '%' : '—',
];

// ── вывод ───────────────────────────────────────────────────────────
if ($asJson) {
    echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}
printf("══ %s%s: %d сайтов ══\n", basename(rtrim($root, '/')), $shkola ? " · $shkola" : '', $N);
foreach ($out as $razdel => $v) {
    if (!is_array($v)) { continue; }
    echo "\n── $razdel ──\n";
    foreach ($v as $k => $x) {
        if (is_array($x)) {
            $s = [];
            foreach ($x as $kk => $vv) { $s[] = $kk . '×' . $vv; }
            $x = implode('  ', $s);
        }
        $pad = str_repeat(' ', max(0, 36 - mb_strlen((string) $k)));
        echo "  $k$pad$x\n";
    }
}
echo "\n";

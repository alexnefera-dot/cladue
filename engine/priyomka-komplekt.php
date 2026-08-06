<?php
declare(strict_types=1);

/**
 * Приёмка семистраничного комплекта.
 *
 *   php engine/priyomka-komplekt.php <папка-комплекта> [--korpus=samples/v4-final]
 *
 * priyomka-v4.php проверяет одну главную. Донорская единица — не страница, а
 * комплект из семи, и половина правил живёт МЕЖДУ страницами, а не внутри:
 *
 *   — первый H2 внутренней страницы это срез темы, и 216 срезов из 216 у
 *     доноров уникальны; внутри одного комплекта повтор недопустим тем более;
 *   — главная не переиспользует свои же формулировки: пересечение с каждой
 *     внутренней 0,18 % в среднем при максимуме 2,29;
 *   — /bonus не получает ни одной входящей ссылки ни у одного из 50 доноров;
 *   — проза почти не возвращает ссылку на главную: 0–11 %.
 *
 * У каждого типа страницы своя мерка: главная держит 24 поля из 55, внутренние
 * по 30–35 — они короче и однообразнее, и требовать от них главную нельзя.
 *
 * Отдельная проверка — СМЕЩЕНИЕ по отпущенным полям. Разброс у донора не даёт
 * права систематически сидеть ниже его медианы: у него значения гуляют вокруг
 * центра, а комплект, который по всем семи страницам лежит под ним, — это уже
 * не разброс, а смещение. Первый наш комплект так и прошёл: объём 75 % от
 * донорского, ссылки 38 %, и ни один шлюз этого не увидел, потому что words и
 * ссылки были записаны в «отпустить».
 *
 * Порог по параметрам — доля, а не «все до одного». Каждое поле по отдельности
 * держат 70–90 % доноров, но тридцать полей разом — это произведение
 * вероятностей, и его не берёт НИ ОДИН донорский комплект: медиана 90–94 %,
 * девятый дециль 96–97 %, ста процентов нет ни у кого. Порог 95 % ставит нас
 * выше девяти десятых корпуса и при этом остаётся достижимым.
 *
 * Код возврата 0 — комплект принят целиком.
 */

require_once __DIR__ . '/src/PageMetrics.php';
require_once __DIR__ . '/src/SeoMetrics.php';

const PAGES_K = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
/** Доля удержанных полей, ниже которой страница не принимается. */
const PORog_POLEY = 95.0;

$dir = rtrim($argv[1] ?? '', '/');
$korpus = 'samples/v4-final';
foreach (array_slice($argv, 2) as $a) {
    if (str_starts_with($a, '--korpus=')) { $korpus = substr($a, 9); }
}
if ($dir === '' || !is_dir($dir)) {
    fwrite(STDERR, "usage: php engine/priyomka-komplekt.php <папка-комплекта> [--korpus=<путь>]\n");
    exit(1);
}
$profil = json_decode((string) file_get_contents(__DIR__ . '/data-v4/profil-avgust.json'), true);
if (!isset($profil['страницы'])) { fwrite(STDERR, "в профиле нет раздела «страницы»\n"); exit(1); }

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
function zag(string $h, string $lvl): array
{
    preg_match_all('~(?is)<' . $lvl . '[^>]*>(.*?)</' . $lvl . '>~', $h, $m);
    $out = [];
    foreach ($m[1] as $x) {
        $t = trim(preg_replace('~\s+~u', ' ', chist($x)));
        if ($t !== '') { $out[] = $t; }
    }
    return $out;
}
function shingle(string $t, int $n = 6): array
{
    $t = mb_strtolower(preg_replace('~%[a-z_]+%~u', ' бренд ', $t));
    $w = slv($t);
    $s = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $s[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $s;
}
function peresech(array $a, array $b): float
{
    $min = min(count($a), count($b));
    return $min ? count(array_intersect_key($a, $b)) / $min * 100 : 0.0;
}
$pad = fn($v, $w, $l = false) => $l
    ? $v . str_repeat(' ', max(0, $w - mb_strlen((string) $v)))
    : str_repeat(' ', max(0, $w - mb_strlen((string) $v))) . $v;

// ── чтение комплекта ────────────────────────────────────────────────
$stranicy = [];
$net = [];
foreach (PAGES_K as $p) {
    $f = "$dir/$p.html";
    if (!is_file($f)) { $net[] = $p; continue; }
    $raw = (string) file_get_contents($f);
    $stranicy[$p] = preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $raw);
}
if ($net) { fwrite(STDERR, 'нет страниц: ' . implode(', ', $net) . "\n"); exit(1); }

$provaly = [];
$a = new Analyzer();
$otchet = [];

// ── 1. каждая страница по своей мерке ───────────────────────────────
foreach (PAGES_K as $p) {
    $html = $stranicy[$p];
    $card = PageMetrics::measure($a, $p, $html, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $ok = 0; $vsego = 0; $bad = [];
    foreach ($profil['страницы'][$p]['поля'] as $k => $pp) {
        if (!$pp['держат'] || !array_key_exists($k, $card)) { continue; }
        $vsego++;
        $pol = $pp['дробное'] ? 0.8 : 2.0;
        if (abs((float) $card[$k] - (float) $pp['цель']) <= max(0.25 * abs((float) $pp['цель']), $pol)) { $ok++; }
        else { $bad[] = $k . ' ' . $card[$k] . '→' . $pp['цель']; }
    }
    $dolya = $vsego ? $ok / $vsego * 100 : 100.0;
    $otchet[$p] = ['поля' => [$ok, $vsego], 'доля' => $dolya, 'промахи' => $bad];
    if ($dolya < PORog_POLEY) { $provaly["параметры:$p"] = 1; }
}

// ── 2. каркас внутренней страницы ───────────────────────────────────
$vnutr = [];
foreach (PAGES_K as $p) {
    if ($p === 'main') { continue; }
    $html = $stranicy[$p];
    $h2 = zag($html, 'h2');
    $h3 = zag($html, 'h3');
    $cit = preg_match_all('~(?i)<blockquote~', $html);
    $prov = [
        'H2 = 2' => count($h2) === 2,
        'последний H2 — FAQ' => $h2 && (bool) preg_match('~вопрос|faq|ответ~iu', end($h2)),
        'H3 2–10' => count($h3) >= 2 && count($h3) <= 10,
        'цитата 1–4' => $cit >= 1 && $cit <= 4,
    ];
    $vnutr[$p] = ['первый H2' => $h2[0] ?? '—', 'проверки' => $prov,
        'ок' => count(array_filter($prov)), 'всего' => count($prov)];
    if (count(array_filter($prov)) < count($prov)) { $provaly["каркас:$p"] = 1; }
}

// ── 3. срезы тем: внутри комплекта и против корпуса ──────────────────
$srezy = [];
foreach ($vnutr as $p => $v) { $srezy[$p] = mb_strtolower($v['первый H2']); }
$dubliVnutri = count($srezy) - count(array_unique($srezy));

$root = dirname(__DIR__);
$put = is_dir($korpus) ? $korpus : $root . '/' . $korpus;
$sovpavshie = [];
$hudshayaPara = 0.0; $hudshiy = '—';
$nashSh = [];
foreach (PAGES_K as $p) { $nashSh[$p] = shingle(chist($stranicy[$p])); }

foreach (glob(rtrim($put, '/') . '/*', GLOB_ONLYDIR) ?: [] as $other) {
    if (realpath($other) === realpath($dir)) { continue; }
    foreach (PAGES_K as $p) {
        $f = "$other/$p.html";
        if (!is_file($f)) { continue; }
        $oh = preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', (string) file_get_contents($f));
        $v = peresech($nashSh[$p], shingle(chist($oh)));
        if ($v > $hudshayaPara) { $hudshayaPara = $v; $hudshiy = basename($other) . "/$p"; }
        if ($p !== 'main') {
            $ih = zag($oh, 'h2');
            if ($ih && isset($srezy[$p]) && mb_strtolower($ih[0]) === $srezy[$p]) {
                $sovpavshie[] = basename($other) . "/$p";
            }
        }
    }
}
$porog = (float) ($profil['уникальность']['шинглы']['порог_pct'] ?? 6.0);
if ($dubliVnutri || $sovpavshie || $hudshayaPara >= $porog) { $provaly['уникальность'] = 1; }

// ── 4. каннибализация внутри комплекта ──────────────────────────────
$mVn = []; $vnVn = [];
$imena = PAGES_K;
for ($i = 0; $i < count($imena); $i++) {
    for ($j = $i + 1; $j < count($imena); $j++) {
        $v = peresech($nashSh[$imena[$i]], $nashSh[$imena[$j]]);
        if ($imena[$i] === 'main') { $mVn[] = $v; } else { $vnVn[] = $v; }
    }
}
$kanMax = max(max($mVn), max($vnVn));
if ($kanMax > 3.0) { $provaly['каннибализация'] = 1; }

// ── 4б. смещение по отпущенным полям ────────────────────────────────
// Отпущенное поле обязано гулять ВОКРУГ донорской медианы. Считаем сумму по
// комплекту и сравниваем с суммой донорских медиан: ниже 85 % — смещение.
$smeshenie = [];
foreach (['words' => 'объём', 'terms_total' => 'профильных терминов',
         'brand_en' => 'бренд латиницей', 'brand_ru' => 'бренд кириллицей'] as $pole => $imya) {
    $nashSum = 0; $ihSum = 0;
    foreach (PAGES_K as $p) {
        $c = PageMetrics::measure($a, $p, $stranicy[$p], ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
        $nashSum += (float) ($c[$pole] ?? 0);
        $ihSum += (float) ($profil['страницы'][$p]['поля'][$pole]['цель'] ?? 0);
    }
    $dolya = $ihSum ? $nashSum / $ihSum * 100 : 100;
    $smeshenie[$imya] = [round($nashSum) . ' из ' . round($ihSum), '≥85%', $dolya >= 85, round($dolya)];
}

// ── 5. граф перелинковки ────────────────────────────────────────────
$ishod = [];
foreach (PAGES_K as $p) {
    preg_match_all('~<a\s[^>]*href="(/[a-z]*)"~i', $stranicy[$p], $m);
    $ishod[$p] = $m[1];
}
$vhodBonus = 0;
foreach ($ishod as $lst) { foreach ($lst as $h) { if (trim($h, '/') === 'bonus') { $vhodBonus++; } } }
$sGlavnoy = [];
foreach ($ishod['main'] as $h) { $c = trim($h, '/'); if ($c !== '' && $c !== 'bonus') { $sGlavnoy[$c] = 1; } }
$nazadNaGlavnuyu = 0;
foreach (PAGES_K as $p) {
    if ($p === 'main') { continue; }
    foreach ($ishod[$p] as $h) { if (trim($h, '/') === '') { $nazadNaGlavnuyu++; break; } }
}
$ssylokVsego = 0;
foreach (PAGES_K as $p) { $ssylokVsego += count($ishod[$p]); }
$ssylokCel = 0;
foreach (PAGES_K as $p) { $ssylokCel += (int) ($profil['страницы'][$p]['жанр']['ссылок'] ?? 50); }
$smeshenie['внутренних ссылок'] = [$ssylokVsego . ' из ' . $ssylokCel, '≥85%',
    $ssylokVsego / max(1, $ssylokCel) * 100 >= 85, round($ssylokVsego / max(1, $ssylokCel) * 100)];

$graf = [
    'ссылок с главной' => [count($ishod['main']), '40–60', count($ishod['main']) >= 40 && count($ishod['main']) <= 60],
    'главная ведёт на типов' => [count($sGlavnoy), '≥4', count($sGlavnoy) >= 4],
    'входящих на /bonus' => [$vhodBonus, '0', $vhodBonus === 0],
    'внутренних, ведущих назад' => [$nazadNaGlavnuyu, '0–2', $nazadNaGlavnuyu <= 2],
];
foreach (PAGES_K as $p) {
    if ($p === 'main') { continue; }
    $graf["ссылок с /$p"] = [count($ishod[$p]), '3–11',
        count($ishod[$p]) >= 3 && count($ishod[$p]) <= 11];
}
$grafOk = count(array_filter($graf, fn($x) => $x[2]));
if ($grafOk < count($graf)) { $provaly['граф'] = 1; }

// ── 6. техника по всем страницам ────────────────────────────────────
$teh = ['H1' => 0, 'H4' => 0, 'иерархия' => 0, 'картинок' => 0, 'nofollow' => 0, 'внешних' => 0];
foreach (PAGES_K as $p) {
    $d = new DOMDocument();
    $prev = libxml_use_internal_errors(true);
    $d->loadHTML('<?xml encoding="utf-8"?><html><body>' . $stranicy[$p] . '</body></html>',
        LIBXML_NOWARNING | LIBXML_NOERROR);
    libxml_clear_errors();
    libxml_use_internal_errors($prev);
    $seo = new SeoMetrics($d, $stranicy[$p]);
    $teh['H1'] += $seo->headingCount(1);
    $teh['H4'] += $seo->headingCount(4);
    if (!$seo->headingHierarchyOk()) { $teh['иерархия']++; }
    $teh['картинок'] += $seo->imgCount();
    $l = $seo->links('', "/$p");
    $teh['внешних'] += count($l['external']);
    foreach (['internal', 'external'] as $vid) {
        foreach ($l[$vid] as $it) { if ($it['nofollow']) { $teh['nofollow']++; } }
    }
}
$tehOk = ($teh['H1'] === 0) + ($teh['H4'] === 0) + ($teh['иерархия'] === 0)
    + ($teh['картинок'] === 0) + ($teh['nofollow'] === 0) + ($teh['внешних'] <= 3);
if ($tehOk < 6) { $provaly['техника'] = 1; }

// ── отчёт ───────────────────────────────────────────────────────────
printf("%s — комплект из %d страниц\n\n", basename($dir), count(PAGES_K));

echo "── параметры по типам ──\n";
foreach (PAGES_K as $p) {
    [$ok, $vs] = $otchet[$p]['поля'];
    $d = $otchet[$p]['доля'];
    echo '  ' . ($d >= PORog_POLEY ? '·' : '✗') . ' ' . $pad($p, 13, true)
        . $pad("$ok/$vs", 8) . $pad(round($d) . '%', 6)
        . ($otchet[$p]['промахи'] ? '  — ' . implode(', ', array_slice($otchet[$p]['промахи'], 0, 4)) : '')
        . "\n";
}

echo "\n── каркас внутренних ──\n";
foreach ($vnutr as $p => $v) {
    $bad = array_keys(array_filter($v['проверки'], fn($x) => !$x));
    echo '  ' . ($v['ок'] === $v['всего'] ? '·' : '✗') . ' ' . $pad($p, 13, true)
        . $pad($v['ок'] . '/' . $v['всего'], 6) . '  ' . mb_substr($v['первый H2'], 0, 46)
        . ($bad ? '   ✗ ' . implode(', ', $bad) : '') . "\n";
}

foreach ($smeshenie as $x) { if (!$x[2]) { $provaly['смещение'] = 1; } }

echo "\n── смещение по отпущенным полям ──\n";
foreach ($smeshenie as $n => [$est, $nado, $ok, $pct]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 24, true) . $pad($est, 16)
        . $pad($pct . '%', 7) . '   нужно ' . $nado . "\n";
}

echo "\n── граф перелинковки ──\n";
foreach ($graf as $n => [$est, $nado, $ok]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 28, true) . $pad((string) $est, 6) . '   нужно ' . $nado . "\n";
}

echo "\n── техника по всем семи ──\n";
printf("  %sH1 %d · H4 %d · сбоев иерархии %d · картинок %d · nofollow %d · внешних ссылок %d\n",
    $tehOk === 6 ? '· ' : '✗ ', $teh['H1'], $teh['H4'], $teh['иерархия'],
    $teh['картинок'], $teh['nofollow'], $teh['внешних']);

echo "\n── уникальность ──\n";
printf("  срезы тем внутри комплекта: %s\n", $dubliVnutri ? "✗ $dubliVnutri повтора" : 'все разные');
printf("  срезы совпали с корпусом:   %s\n", $sovpavshie ? '✗ ' . implode(', ', $sovpavshie) : 'нет');
printf("  худшая пара по шинглам:     %.2f%%  (%s), порог %.0f%%\n", $hudshayaPara, $hudshiy, $porog);
printf("  каннибализация внутри:      %.2f%%  (потолок 3%%)\n", $kanMax);

printf("\nИТОГ: %s\n", $provaly ? 'НЕ ПРОЙДЕНО — ' . implode(', ', array_keys($provaly)) : 'комплект принят');
exit($provaly ? 1 : 0);

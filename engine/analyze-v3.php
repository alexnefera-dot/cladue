<?php
declare(strict_types=1);

/**
 * Глубокий разбор корпуса v3 по всем параметрам, которыми мы мерили v1/v2:
 * структура, стилистика, семантические кластеры, перелинковка, E-E-A-T,
 * коридоры [p10, медиана, p90] и сопоставление с корпусом v2.
 *
 *   php analyze-v3.php [out.html]
 *
 * Читает engine/data-v3/donors.json (профиль) и samples/v3-reference (тексты —
 * нужны для анкоров, графа ссылок и авторского блока). Корпус v2 не трогает:
 * data-dorgen/donors.json открывается только на чтение, для колонки сравнения.
 */

require_once __DIR__ . '/src/Analyzer.php';

/** Слаги в ссылках короче имён файлов: /registr → registracia.htm */
const ALIASES = ['registr' => 'registracia', 'index' => 'main', 'reg' => 'registracia',
                 'login' => 'vhod', 'mirror' => 'zerkalo', 'partner' => 'partnery'];

$OUT  = $argv[1] ?? '';
$ROOT = __DIR__ . '/../samples/v3-reference';
$V3   = json_decode((string) file_get_contents(__DIR__ . '/data-v3/donors.json'), true)['sites'] ?? [];
$V2   = json_decode((string) file_get_contents(__DIR__ . '/data-dorgen/donors.json'), true)['sites'] ?? [];
if (!$V3) { fwrite(STDERR, "нет data-v3/donors.json — сначала extract-donors-v3.php\n"); exit(1); }

$FIELDS = [
    'words'          => ['Объём слов', 0],
    'h2'             => ['H2', 0],
    'sections'       => ['Разделы H2+H3', 0],
    'lists'          => ['Списки', 0],
    'tables'         => ['Таблицы', 0],
    'quotes'         => ['Цитаты', 0],
    'strong'         => ['<strong>', 0],
    'faq'            => ['FAQ', 0],
    'emoji'          => ['Эмодзи', 0],
    'entities'       => ['Сущности', 0],
    'first_person'   => ['«я»', 0],
    'vy'             => ['«вы»', 0],
    'imperatives'    => ['Императивы', 0],
    'numbers_per100' => ['Цифры/100', 1],
    'adj_pct'        => ['Прилаг%', 1],
    'nausea_acad'    => ['Тошнота', 1],
    'water'          => ['Водность%', 1],
    'brand_ru'       => ['Бренд RU', 0],
    'brand_en'       => ['Бренд EN', 0],
];

/** [p10, медиана, p90] — та же мерка коридора, что в build-corpus-profile.php */
function corridor(array $v): array
{
    if (!$v) { return [0, 0, 0]; }
    sort($v);
    $at = function (float $q) use ($v) {
        $i = (int) round($q * (count($v) - 1));
        return $v[max(0, min(count($v) - 1, $i))];
    };
    return [$at(0.10), $at(0.50), $at(0.90)];
}
function fmt($x): string { return is_float($x) ? rtrim(rtrim(number_format($x, 1, '.', ''), '0'), '.') : (string) $x; }

// ── A. Состав ──────────────────────────────────────────────────────────────
$singles = []; $bundles = [];
foreach ($V3 as $n => $s) { if ($s['shape']['single']) { $singles[$n] = $s; } else { $bundles[$n] = $s; } }

echo "\n=== A. СОСТАВ КОРПУСА v3 ===\n";
foreach ($V3 as $n => $s) {
    printf("  %-4s %-2d стр  %-26s бренд %s / %s\n", $n, $s['shape']['page_count'],
        implode(',', array_slice($s['shape']['types'], 0, 4)) . (count($s['shape']['types']) > 4 ? '…' : ''),
        $s['brand']['ru'] ?: '—', $s['brand']['en'] ?: '—');
}
printf("  одностраничников %d, связок %d\n", count($singles), count($bundles));

// ── B. Коридоры: одностраничники против связки ─────────────────────────────
$colS = []; $colB = []; $colV2 = [];
foreach ($singles as $s) { foreach ($s['pages'] as $p) { foreach ($FIELDS as $k => $_) { $colS[$k][] = $p[$k]; } } }
foreach ($bundles as $s) { foreach ($s['pages'] as $p) { foreach ($FIELDS as $k => $_) { $colB[$k][] = $p[$k]; } } }
foreach ($V2 as $s) { foreach ($s['pages'] as $p) { foreach ($FIELDS as $k => $_) { if (isset($p[$k])) { $colV2[$k][] = $p[$k]; } } } }

echo "\n=== B. КОРИДОРЫ [p10 · медиана · p90] ===\n";
printf("  %-16s %-22s %-22s %-22s\n", 'параметр', 'одностраничники (6)', 'связка 12 стр', 'корпус v2 (63 стр)');
foreach ($FIELDS as $k => [$lab, $rate]) {
    $a = corridor($colS[$k] ?? []); $b = corridor($colB[$k] ?? []); $c = corridor($colV2[$k] ?? []);
    printf("  %-16s %-22s %-22s %-22s\n", $lab,
        fmt($a[0]) . ' · ' . fmt($a[1]) . ' · ' . fmt($a[2]),
        fmt($b[0]) . ' · ' . fmt($b[1]) . ' · ' . fmt($b[2]),
        fmt($c[0]) . ' · ' . fmt($c[1]) . ' · ' . fmt($c[2]));
}

// ── C. Семантические кластеры ──────────────────────────────────────────────
echo "\n=== C. СЕМАНТИЧЕСКИЕ КЛАСТЕРЫ (плотность на 100 слов, медиана по набору) ===\n";
$clusters = array_keys(Intent::THEMES);
printf("  %-6s", 'набор'); foreach ($clusters as $c) { printf("%-9s", mb_substr($c, 0, 8)); } echo "\n";
foreach ($V3 as $n => $s) {
    printf("  %-6s", $n);
    foreach ($clusters as $c) {
        $v = array_column(array_column($s['pages'], 'sem'), $c);
        $m = corridor($v)[1];
        printf("%-9s", fmt($m));
    }
    echo "\n";
}

// ── D. Перелинковка связки ─────────────────────────────────────────────────
echo "\n=== D. ПЕРЕЛИНКОВКА (только связки) ===\n";
foreach ($bundles as $n => $s) {
    $dir = "$ROOT/$n";
    $types = $s['shape']['types'];
    $files = [];
    foreach (array_merge(glob("$dir/*.htm") ?: [], glob("$dir/*.html") ?: []) as $f) {
        $files[mb_strtolower(pathinfo($f, PATHINFO_FILENAME))] = $f;
    }
    $edges = []; $anchors = [];
    foreach ($types as $t) {
        if (!isset($files[$t])) { continue; }
        $raw = (string) file_get_contents($files[$t]);
        if (preg_match_all('#<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>#is', $raw, $mm, PREG_SET_ORDER)) {
            foreach ($mm as $m) {
                // Ссылки в сохранённых страницах — абсолютные URL, поэтому берём
                // именно path. Без этого корень сайта разбирается как имя файла
                // («buzz» от домена), и у главной выходит ноль входящих —
                // связка ложно выглядит без хаба.
                $path = trim((string) parse_url(trim($m[1]), PHP_URL_PATH), '/');
                $slug = $path === '' ? 'main' : mb_strtolower(basename($path));
                $slug = ALIASES[$slug] ?? $slug;
                if ($slug === $t || !isset($files[$slug])) { continue; }
                $edges[$t][$slug] = ($edges[$t][$slug] ?? 0) + 1;
                $anchors[$t][] = mb_strtolower(trim(strip_tags($m[2])));
            }
        }
    }
    printf("  набор %s\n", $n);
    printf("    %-13s %-7s %-7s %-9s %s\n", 'страница', 'ссылок', 'целей', 'уник.анк', 'топ-анкор');
    foreach ($types as $t) {
        $a = $anchors[$t] ?? [];
        if (!$a) { continue; }
        $ph = array_count_values($a); arsort($ph);
        $top = array_key_first($ph);
        printf("    %-13s %-7d %-7d %-9s %s\n", $t, count($a), count($edges[$t] ?? []),
            round(count($ph) / max(1, count($a)) * 100) . '%',
            mb_substr((string) $top, 0, 34) . ' ×' . $ph[$top]);
    }
    // достижимость: есть ли страница, на которую никто не ссылается
    $inbound = array_fill_keys($types, 0);
    foreach ($edges as $from => $to) { foreach ($to as $tt => $c) { $inbound[$tt] = ($inbound[$tt] ?? 0) + $c; } }
    $orphans = array_keys(array_filter($inbound, fn($x) => $x === 0));
    printf("    входящих нет у: %s\n", $orphans ? implode(', ', $orphans) : '— (все достижимы)');
}

// ── E. Авторский блок (E-E-A-T) ────────────────────────────────────────────
echo "\n=== E. АВТОРСКИЙ БЛОК (E-E-A-T) ===\n";
$reAuthor = '~(автор[аы]?\s*[:—-]|эксперт\s|редакци[яию]|проверил|обновлено\s+редакцией|стаж|опыт\s+\d+\s+лет|аналитик)~ui';
foreach ($V3 as $n => $s) {
    $dir = "$ROOT/$n";
    $files = array_merge(glob("$dir/*.htm") ?: [], glob("$dir/*.html") ?: []);
    $hits = [];
    foreach ($files as $f) {
        $txt = Parser::fromHtml((string) file_get_contents($f))->text;
        if (preg_match($reAuthor, $txt, $m, PREG_OFFSET_CAPTURE)) {
            $posPct = (int) round($m[0][1] / max(1, strlen($txt)) * 100);
            $hits[] = pathinfo($f, PATHINFO_FILENAME) === '' ? '?' : (mb_strlen(pathinfo($f, PATHINFO_FILENAME)) > 14 ? 'main' : pathinfo($f, PATHINFO_FILENAME)) . " ({$posPct}%)";
        }
    }
    printf("  %-4s %s\n", $n, $hits ? implode(', ', array_slice($hits, 0, 6)) . (count($hits) > 6 ? '…' : '') : '— нет');
}

// ── F. Чем v3 отличается от v2 ─────────────────────────────────────────────
echo "\n=== F. МЕДИАНЫ: v3 против v2 ===\n";
printf("  %-16s %-10s %-10s %-10s %s\n", 'параметр', 'одностр.', 'связка', 'v2', 'вывод');
foreach ($FIELDS as $k => [$lab, $rate]) {
    $s = corridor($colS[$k] ?? [])[1]; $b = corridor($colB[$k] ?? [])[1]; $v = corridor($colV2[$k] ?? [])[1];
    // Бренд в v2 считался по плейсхолдерам (в реальных страницах их нет), в v3 —
    // по настоящему имени. Сравнивать эти две колонки нельзя.
    if ($k === 'brand_ru' || $k === 'brand_en') {
        printf("  %-16s %-10s %-10s %-10s %s\n", $lab, fmt($s), fmt($b), '—', 'с v2 несравнимо (там считались плейсхолдеры)');
        continue;
    }
    if ($b == 0 && $v == 0) { $note = ''; }
    elseif ($b == 0)        { $note = 'в связке НЕТ ВОВСЕ (в v2 медиана ' . fmt($v) . ')'; }
    elseif ($v == 0)        { $note = 'в v2 не было вовсе'; }
    else {
        $r = max($b, $v) / min($b, $v);
        $note = $r >= 1.5 ? (($b > $v ? 'связка ВЫШЕ v2' : 'связка НИЖЕ v2') . ' в ' . fmt(round($r, 1)) . '×') : '';
    }
    printf("  %-16s %-10s %-10s %-10s %s\n", $lab, fmt($s), fmt($b), fmt($v), $note);
}

echo "\nSTATUS " . json_encode(['sets' => count($V3), 'singles' => count($singles), 'bundles' => count($bundles)]) . "\n";
if ($OUT === '') { exit(0); }

// ── HTML ───────────────────────────────────────────────────────────────────
$HOW = [
    'words'          => ['Объём слов', 'Слова текста без разметки, скриптов и стилей.'],
    'h2'             => ['H2', 'Число заголовков второго уровня.'],
    'sections'       => ['Разделы H2+H3', 'H2 плюс H3 — сколько всего смысловых блоков на странице.'],
    'lists'          => ['Списки', 'Число блоков ul и ol.'],
    'tables'         => ['Таблицы', 'Число блоков table.'],
    'quotes'         => ['Цитаты', 'Блоки blockquote — отзывы и врезки.'],
    'strong'         => ['&lt;strong&gt;', 'Число выделений жирным в тексте.'],
    'faq'            => ['FAQ', 'Вопросы, опознанные как FAQ: заголовок или жирная строка, оканчивающаяся вопросительным знаком.'],
    'emoji'          => ['Эмодзи', 'Эмодзи в теле текста; навигация и меню не в счёт.'],
    'entities'       => ['Сущности', 'Число КАТЕГОРИЙ именованных данных: лицензия, провайдеры, платежи, крипта, RTP, джекпот, поддержка и ещё шесть. Считаются категории, а не отдельные имена — два провайдера это одна сущность.'],
    'first_person'   => ['«я»', 'Слова я, мне, мой, меня и формы.'],
    'vy'             => ['«вы»', 'Слова вы, вас, вам, ваш и формы.'],
    'imperatives'    => ['Императивы', 'Побудительные глаголы: жми, забирай, проверь, открой — CTA в теле текста.'],
    'numbers_per100' => ['Цифры/100', 'Сколько чисел ЦИФРАМИ приходится на сто слов. Числа словами не считаются.'],
    'adj_pct'        => ['Прилаг%', 'Доля прилагательных от всех слов.'],
    'nausea_acad'    => ['Тошнота', 'Академическая тошнота: насколько часто повторяются самые частые слова. Высокая — норма для SEO-текста ниши.'],
    'water'          => ['Водность%', 'Доля стоп-слов, вводных и связок. Низкая — телеграфный стиль, высокая — рассуждение.'],
    'brand_ru'       => ['Бренд RU', 'Вхождений кириллического написания имени бренда.'],
    'brand_en'       => ['Бренд EN', 'Вхождений латинского написания имени бренда.'],
];

/** строка таблицы: значения по страницам + коридор набора */
function rowFor(array $pages, string $k, array $order): string {
    $out = '';
    foreach ($order as $t) { $out .= '<td>' . fmt($pages[$t][$k]) . '</td>'; }
    return $out;
}

$css = "<style>
body{font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1400px;margin:0 auto;padding:24px;color:#1a1a1a;background:#fafafa}
h1{font-size:24px}h2{font-size:20px;margin-top:38px;border-bottom:2px solid #2563eb;padding-bottom:6px}
h3{font-size:16px;margin-top:24px;color:#333}
table{border-collapse:collapse;width:100%;margin:12px 0;background:#fff;font-size:12.5px}
th,td{border:1px solid #e3e3e3;padding:5px 7px;text-align:center;white-space:nowrap}
th{background:#f0f4ff;font-weight:600}th.l,td.l{text-align:left;white-space:normal}
.hd{font-weight:700;background:#fafbff}.cor{background:#f4f7ff;font-weight:700}
.na{color:#999}.note{background:#fff;border-left:3px solid #2563eb;padding:10px 16px;margin:12px 0}
.warn{background:#fff8e6;border-left:3px solid #e0a800;padding:10px 16px;margin:12px 0}
.gloss td{text-align:left;white-space:normal;font-size:13px}
.zero{background:#fdecea;color:#c5221f;font-weight:700}
.hi{background:#e8f7ec}
tr:hover td{background:#f7f9ff}
</style>";

$H = "<meta charset='utf-8'><title>Корпус v3 — разбор</title>$css
<h1>Корпус v3 — разбор по нашим параметрам</h1>
<p class='note'>Каждое число — замер нашего <code>Analyzer</code> по одной странице: тот же код, которым мерились корпуса v1 и v2.
В корпусе <b>18 страниц</b>: шесть одностраничников и связка из двенадцати. Разбираются они отдельно, потому что сравнивать
страницу, которая несёт весь сайт, со страницей внутри связки — некорректно.</p>";

// ── 0. Глоссарий ───────────────────────────────────────────────────────────
$H .= "<h2>0. Что означает каждый параметр</h2><table class='gloss'><tr><th class='l' style='width:150px'>Параметр</th><th class='l'>Как считается</th></tr>";
foreach ($HOW as $k => [$lab, $desc]) { $H .= "<tr><td class='l hd'>$lab</td><td class='l'>" . $desc . "</td></tr>"; }
$H .= "</table><p class='note'>Коридор <b>[p10 · медиана · p90]</b> — десятый процентиль, медиана и девяностый по всем страницам группы: между p10 и p90 лежат 80% значений. Это та же мерка, которой задаются цели генератора.</p>";

// ── 1. Связка: 12 страниц ──────────────────────────────────────────────────
foreach ($bundles as $bn => $bs) {
    $order = array_keys($bs['pages']);
    $H .= "<h2>1. Связка «{$bn}» — двенадцать страниц</h2>";
    $H .= "<p class='note'>Строка — параметр, колонка — страница. Последняя колонка — коридор по этим двенадцати страницам. Красным отмечены нули там, где параметра нет вовсе.</p>";
    $H .= "<table><tr><th class='l'>Параметр</th>";
    foreach ($order as $t) { $H .= "<th>$t</th>"; }
    $H .= "<th class='cor'>коридор</th></tr>";
    foreach ($HOW as $k => [$lab, $_]) {
        $vals = array_column($bs['pages'], $k);
        $c = corridor($vals);
        $allZero = (max($vals) == 0);
        $H .= "<tr><td class='l hd'>$lab</td>";
        foreach ($order as $t) {
            $v = $bs['pages'][$t][$k];
            $cls = $allZero ? 'zero' : '';
            $H .= "<td class='$cls'>" . fmt($v) . "</td>";
        }
        $H .= "<td class='cor'>" . fmt($c[0]) . " · " . fmt($c[1]) . " · " . fmt($c[2]) . "</td></tr>";
    }
    $H .= "</table>";

    // семантика по страницам
    $H .= "<h3>Семантические кластеры связки (плотность на 100 слов)</h3><table><tr><th class='l'>Кластер</th>";
    foreach ($order as $t) { $H .= "<th>$t</th>"; }
    $H .= "<th class='cor'>медиана</th></tr>";
    foreach ($clusters as $cl) {
        $vals = array_column(array_column($bs['pages'], 'sem'), $cl);
        $H .= "<tr><td class='l hd'>$cl</td>";
        foreach ($order as $t) { $H .= "<td>" . fmt($bs['pages'][$t]['sem'][$cl]) . "</td>"; }
        $H .= "<td class='cor'>" . fmt(corridor($vals)[1]) . "</td></tr>";
    }
    $H .= "</table>";
}

// ── 2. Одностраничники ─────────────────────────────────────────────────────
$sOrder = array_keys($singles);
$H .= "<h2>2. Шесть одностраничников</h2>";
$H .= "<p class='note'>Здесь колонка — весь набор: у каждого ровно одна страница, которая несёт весь сайт целиком.</p>";
$H .= "<table><tr><th class='l'>Параметр</th>";
foreach ($sOrder as $n) { $H .= "<th>" . $n . '<br><small>' . htmlspecialchars($singles[$n]['brand']['ru'] ?: '—') . "</small></th>"; }
$H .= "<th class='cor'>коридор</th></tr>";
foreach ($HOW as $k => [$lab, $_]) {
    $vals = [];
    foreach ($sOrder as $n) { $vals[] = $singles[$n]['pages']['main'][$k]; }
    $c = corridor($vals);
    $H .= "<tr><td class='l hd'>$lab</td>";
    foreach ($vals as $v) { $H .= "<td>" . fmt($v) . "</td>"; }
    $H .= "<td class='cor'>" . fmt($c[0]) . " · " . fmt($c[1]) . " · " . fmt($c[2]) . "</td></tr>";
}
$H .= "</table>";

$H .= "<h3>Семантические кластеры одностраничников</h3><table><tr><th class='l'>Кластер</th>";
foreach ($sOrder as $n) { $H .= "<th>$n</th>"; }
$H .= "</tr>";
foreach ($clusters as $cl) {
    $H .= "<tr><td class='l hd'>$cl</td>";
    foreach ($sOrder as $n) { $H .= "<td>" . fmt($singles[$n]['pages']['main']['sem'][$cl]) . "</td>"; }
    $H .= "</tr>";
}
$H .= "</table>";

// ── 3. Сравнение групп ─────────────────────────────────────────────────────
$H .= "<h2>3. Одностраничник против страницы связки против корпуса v2</h2>";
$H .= "<p class='note'>Медианы. Колонка v2 — прошлый корпус, для понимания, насколько v3 другой. Она справочная: корпус v2 не менялся.</p>";
$H .= "<table><tr><th class='l'>Параметр</th><th>Одностраничники</th><th>Страница связки</th><th class='na'>Корпус v2</th><th class='l'>Вывод</th></tr>";
foreach ($HOW as $k => [$lab, $_]) {
    $s = corridor($colS[$k] ?? [])[1]; $b = corridor($colB[$k] ?? [])[1]; $v = corridor($colV2[$k] ?? [])[1];
    if ($k === 'brand_ru' || $k === 'brand_en') {
        $H .= "<tr><td class='l hd'>$lab</td><td>" . fmt($s) . "</td><td>" . fmt($b) . "</td><td class='na'>—</td>"
           . "<td class='l'>с v2 несравнимо: там считались плейсхолдеры, которых в реальных страницах нет</td></tr>";
        continue;
    }
    if ($b == 0 && $v == 0)      { $note = ''; }
    elseif ($b == 0)             { $note = 'в связке НЕТ ВОВСЕ, в v2 медиана ' . fmt($v); }
    elseif ($v == 0)             { $note = 'в v2 не было вовсе'; }
    else {
        $r = max($b, $v) / min($b, $v);
        $note = $r >= 1.5 ? (($b > $v ? 'связка выше v2' : 'связка ниже v2') . ' в ' . fmt(round($r, 1)) . '×') : '';
    }
    $H .= "<tr><td class='l hd'>$lab</td><td>" . fmt($s) . "</td><td>" . fmt($b) . "</td><td class='na'>" . fmt($v) . "</td><td class='l'>$note</td></tr>";
}
$H .= "</table>";

// ── 4. Линковка: матрица 12×12 ─────────────────────────────────────────────
foreach ($bundles as $bn => $bs) {
    $order = array_keys($bs['pages']);
    $dir = "$ROOT/$bn";
    $files = [];
    foreach (array_merge(glob("$dir/*.htm") ?: [], glob("$dir/*.html") ?: []) as $f) {
        $files[mb_strtolower(pathinfo($f, PATHINFO_FILENAME))] = $f;
    }
    $E = []; $anch = [];
    foreach ($order as $t) {
        if (!isset($files[$t])) { continue; }
        $raw = (string) file_get_contents($files[$t]);
        if (preg_match_all('#<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>#is', $raw, $mm, PREG_SET_ORDER)) {
            foreach ($mm as $m) {
                $path = trim((string) parse_url(trim($m[1]), PHP_URL_PATH), '/');
                $slug = $path === '' ? 'main' : mb_strtolower(basename($path));
                $slug = ALIASES[$slug] ?? $slug;
                if ($slug === $t || !isset($files[$slug])) { continue; }
                $E[$t][$slug] = ($E[$t][$slug] ?? 0) + 1;
                $anch[$t][] = mb_strtolower(trim(strip_tags($m[2])));
            }
        }
    }
    $H .= "<h2>4. Перелинковка связки «{$bn}» — кто на кого ссылается</h2>";
    $H .= "<p class='note'>Строка — откуда, колонка — куда, число — сколько ссылок. Заполненная матрица без пустых клеток означает полную сетку: каждая страница ссылается на все остальные.</p>";
    $H .= "<table><tr><th class='l'>откуда \\ куда</th>";
    foreach ($order as $t) { $H .= "<th>$t</th>"; }
    $H .= "<th class='cor'>всего</th></tr>";
    foreach ($order as $from) {
        $H .= "<tr><td class='l hd'>$from</td>";
        $sum = 0;
        foreach ($order as $to) {
            if ($from === $to) { $H .= "<td class='na'>—</td>"; continue; }
            $c = $E[$from][$to] ?? 0; $sum += $c;
            $H .= "<td class='" . ($c ? 'hi' : 'zero') . "'>" . ($c ?: 0) . "</td>";
        }
        $H .= "<td class='cor'>$sum</td></tr>";
    }
    $H .= "<tr><td class='l hd'>входящих</td>";
    foreach ($order as $to) {
        $in = 0; foreach ($order as $from) { $in += $E[$from][$to] ?? 0; }
        $H .= "<td class='cor'>$in</td>";
    }
    $H .= "<td class='cor'></td></tr></table>";

    $H .= "<h3>Анкоры</h3><table><tr><th class='l'>Страница</th><th>Ссылок</th><th>Целей</th><th>Уникальных анкоров</th><th class='l'>Самый частый анкор</th></tr>";
    foreach ($order as $t) {
        $a = $anch[$t] ?? []; if (!$a) { continue; }
        $ph = array_count_values($a); arsort($ph); $top = array_key_first($ph);
        $H .= "<tr><td class='l hd'>$t</td><td>" . count($a) . "</td><td>" . count($E[$t] ?? []) . "</td>"
            . "<td>" . round(count($ph) / max(1, count($a)) * 100) . "%</td>"
            . "<td class='l'>" . htmlspecialchars((string) $top) . " ×" . $ph[$top] . "</td></tr>";
    }
    $H .= "</table>";
}

// ── 5. Авторский блок ──────────────────────────────────────────────────────
$H .= "<h2>5. Авторский блок (E-E-A-T)</h2>";
$H .= "<p class='warn'>Это <b>формальный</b> признак: поиск слов «автор», «эксперт», «редакция», «проверил», «стаж». Он даёт ложные срабатывания и требует проверки чтением — в корпусе v2 именно чтение поправило классификатор на трёх донорах из девяти.</p>";
$H .= "<table><tr><th class='l'>Набор</th><th class='l'>Где найдено (в скобках — глубина страницы)</th></tr>";
foreach ($V3 as $n => $s) {
    $dir = "$ROOT/$n";
    $hits = [];
    foreach (array_merge(glob("$dir/*.htm") ?: [], glob("$dir/*.html") ?: []) as $f) {
        $stem = pathinfo($f, PATHINFO_FILENAME);
        $nm = mb_strlen($stem) > 14 ? 'main' : $stem;
        if ($nm === 'sitemap') { continue; }
        $txt = Parser::fromHtml((string) file_get_contents($f))->text;
        if (preg_match($reAuthor, $txt, $m, PREG_OFFSET_CAPTURE)) {
            $hits[] = $nm . ' (' . (int) round($m[0][1] / max(1, strlen($txt)) * 100) . '%)';
        }
    }
    $H .= "<tr><td class='l hd'>$n</td><td class='l'>" . ($hits ? implode(', ', $hits) : '<span class=na>не найдено</span>') . "</td></tr>";
}
$H .= "</table>";

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");

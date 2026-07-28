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
$H = "<meta charset='utf-8'><title>Корпус v3 — глубокий разбор</title><style>
body{font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1180px;margin:0 auto;padding:24px;color:#1a1a1a;background:#fafafa}
h1{font-size:23px}h2{font-size:19px;margin-top:34px;border-bottom:2px solid #2563eb;padding-bottom:6px}
table{border-collapse:collapse;width:100%;margin:10px 0;background:#fff;font-size:13px}
th,td{border:1px solid #e3e3e3;padding:5px 8px;text-align:center}th{background:#f0f4ff;font-weight:600}
td.l,th.l{text-align:left}.hd{font-weight:700}.na{color:#999}
.note{background:#fff;border-left:3px solid #2563eb;padding:8px 14px;margin:10px 0}
.hi{background:#fff4e5}.lo{background:#eef4ff}</style>
<h1>Корпус v3 — глубокий разбор по нашим параметрам</h1>
<p class='note'>Семь наборов: шесть одностраничников и одна связка на двенадцать страниц. Коридор — [p10 · медиана · p90]. Колонка v2 приведена только для сопоставления, корпус v2 не изменялся.</p>";

$H .= "<h2>A. Состав</h2><table><tr><th class='l'>Набор</th><th>Страниц</th><th class='l'>Типы</th><th class='l'>Бренд</th></tr>";
foreach ($V3 as $n => $s) {
    $H .= "<tr><td class='l hd'>$n</td><td>{$s['shape']['page_count']}</td><td class='l'>"
        . htmlspecialchars(implode(', ', $s['shape']['types'])) . "</td><td class='l'>"
        . htmlspecialchars(($s['brand']['ru'] ?: '—') . ' / ' . ($s['brand']['en'] ?: '—')) . "</td></tr>";
}
$H .= "</table>";

$H .= "<h2>B. Полная матрица параметров</h2><table><tr><th class='l'>Набор / страница</th>";
foreach ($FIELDS as [$lab, $_]) { $H .= "<th>" . htmlspecialchars($lab) . "</th>"; }
$H .= "</tr>";
foreach ($V3 as $n => $s) {
    foreach ($s['pages'] as $t => $p) {
        $H .= "<tr><td class='l hd'>$n / $t</td>";
        foreach ($FIELDS as $k => $_) { $H .= "<td>" . fmt($p[$k]) . "</td>"; }
        $H .= "</tr>";
    }
}
$H .= "</table>";

$H .= "<h2>C. Коридоры</h2><table><tr><th class='l'>Параметр</th><th>Одностраничники</th><th>Связка (12 стр)</th><th>Корпус v2</th></tr>";
foreach ($FIELDS as $k => [$lab, $_]) {
    $a = corridor($colS[$k] ?? []); $b = corridor($colB[$k] ?? []); $c = corridor($colV2[$k] ?? []);
    $H .= "<tr><td class='l hd'>" . htmlspecialchars($lab) . "</td>"
        . "<td>" . fmt($a[0]) . " · <b>" . fmt($a[1]) . "</b> · " . fmt($a[2]) . "</td>"
        . "<td>" . fmt($b[0]) . " · <b>" . fmt($b[1]) . "</b> · " . fmt($b[2]) . "</td>"
        . "<td class='na'>" . fmt($c[0]) . " · " . fmt($c[1]) . " · " . fmt($c[2]) . "</td></tr>";
}
$H .= "</table>";

$H .= "<h2>D. Семантические кластеры (плотность на 100 слов)</h2><table><tr><th class='l'>Набор</th>";
foreach ($clusters as $c) { $H .= "<th>" . htmlspecialchars($c) . "</th>"; }
$H .= "</tr>";
foreach ($V3 as $n => $s) {
    $H .= "<tr><td class='l hd'>$n</td>";
    foreach ($clusters as $c) {
        $v = array_column(array_column($s['pages'], 'sem'), $c);
        $H .= "<td>" . fmt(corridor($v)[1]) . "</td>";
    }
    $H .= "</tr>";
}
$H .= "</table>";

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");

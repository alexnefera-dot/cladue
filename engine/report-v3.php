<?php
declare(strict_types=1);

/**
 * Постраничный отчёт по корпусу v3: карточка на каждую страницу — параметры,
 * семантика, исходящие ссылки и то, что дало ЧТЕНИЕ текста. Плюс сводные
 * матрицы и глоссарий.
 *
 *   php report-v3.php <out.html>
 *
 * Смысл отдельного файла: analyze-v3.php отвечает на вопрос «какие у корпуса
 * коридоры», а этот — на вопрос «что представляет собой каждая страница».
 */

require_once __DIR__ . '/src/Analyzer.php';

const RALIAS = ['registr' => 'registracia', 'index' => 'main', 'reg' => 'registracia',
                'login' => 'vhod', 'mirror' => 'zerkalo', 'partner' => 'partnery'];

$OUT  = $argv[1] ?? '';
if ($OUT === '') { fwrite(STDERR, "usage: report-v3.php <out.html>\n"); exit(1); }
$ROOT = __DIR__ . '/../samples/v3-reference';
$V3   = json_decode((string) file_get_contents(__DIR__ . '/data-v3/donors.json'), true)['sites'] ?? [];
if (!$V3) { fwrite(STDERR, "нет data-v3/donors.json\n"); exit(1); }

$P = [
    'words'          => ['Объём слов', 'Слова текста без разметки, скриптов и стилей.'],
    'h2'             => ['H2', 'Заголовки второго уровня.'],
    'sections'       => ['Разделы H2+H3', 'Сколько всего смысловых блоков.'],
    'lists'          => ['Списки', 'Блоки ul и ol.'],
    'tables'         => ['Таблицы', 'Блоки table.'],
    'quotes'         => ['Цитаты', 'Блоки blockquote. Считается разметка, а не жанр: у набора 6 это максимы, а не отзывы.'],
    'strong'         => ['strong', 'Выделения жирным.'],
    'faq'            => ['FAQ', 'Вопросы: заголовок или жирная строка, оканчивающаяся вопросительным знаком.'],
    'emoji'          => ['Эмодзи', 'Эмодзи в теле текста.'],
    'entities'       => ['Сущности', 'Число КАТЕГОРИЙ именованных данных (лицензия, провайдеры, платежи, крипта, RTP, джекпот, поддержка…), а не отдельных имён: два провайдера — одна сущность.'],
    'first_person'   => ['«я»', 'я, мне, мой, меня и формы — только единственное число.'],
    'we'             => ['«мы»', 'мы, нас, нам, наш и формы. Отдельная ось: в v1/v2 её не считали, и текст от лица службы читался как безличный.'],
    'vy'             => ['«вы»', 'вы, вас, вам, ваш и формы.'],
    'imperatives'    => ['Императивы', 'Побудительные глаголы в теле: жми, забирай, проверь, откройте.'],
    'numbers_per100' => ['Цифры/100', 'Чисел ЦИФРАМИ на сто слов. Числа словами не считаются.'],
    'adj_pct'        => ['Прилаг%', 'Доля прилагательных.'],
    'nausea_acad'    => ['Тошнота', 'Академическая тошнота: как часто повторяются самые частые слова. Высокая — норма ниши.'],
    'water'          => ['Водность%', 'Доля стоп-слов, вводных и связок. Низкая — телеграфный стиль.'],
    'intlinks'       => ['Ссылок внутри', 'Ссылки на другие страницы своего набора.'],
    'brand_ru'       => ['Бренд RU', 'Вхождения кириллического имени бренда — своего для каждой страницы.'],
    'brand_en'       => ['Бренд EN', 'Вхождения латинского имени.'],
];

function fmt($x): string { return is_float($x) ? rtrim(rtrim(number_format($x, 1, '.', ''), '0'), '.') : (string) $x; }
function corridor(array $v): array {
    if (!$v) { return [0, 0, 0]; }
    sort($v);
    $at = fn(float $q) => $v[max(0, min(count($v) - 1, (int) round($q * (count($v) - 1))))];
    return [$at(0.10), $at(0.50), $at(0.90)];
}
function esc($s): string { return htmlspecialchars((string) ($s ?? ''), ENT_QUOTES, 'UTF-8'); }

/** исходящие ссылки страницы, разложенные по целям */
function outLinks(string $file, string $self, array $known): array {
    $raw = (string) file_get_contents($file);
    $by = [];
    if (preg_match_all('#<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>#is', $raw, $mm, PREG_SET_ORDER)) {
        foreach ($mm as $m) {
            $path = trim((string) parse_url(trim($m[1]), PHP_URL_PATH), '/');
            $slug = $path === '' ? 'main' : mb_strtolower(basename($path));
            $slug = RALIAS[$slug] ?? $slug;
            if ($slug === $self || !isset($known[$slug])) { continue; }
            $by[$slug][] = mb_strtolower(trim(strip_tags($m[2])));
        }
    }
    return $by;
}

$css = "<style>
body{font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1180px;margin:0 auto;padding:24px 20px 80px;color:#16181d;background:#f7f8fa}
h1{font-size:25px;margin-bottom:4px}h2{font-size:20px;margin-top:42px;border-bottom:2px solid #2563eb;padding-bottom:6px}
h3{font-size:17px;margin:26px 0 8px}
table{border-collapse:collapse;width:100%;margin:10px 0;background:#fff;font-size:12.5px}
th,td{border:1px solid #e4e6ea;padding:5px 7px;text-align:center;white-space:nowrap}
th{background:#eef3ff;font-weight:600}th.l,td.l{text-align:left;white-space:normal}
.hd{font-weight:700;background:#fbfcff}.cor{background:#eef3ff;font-weight:700}
.na{color:#9aa0a6}.note{background:#fff;border-left:3px solid #2563eb;padding:10px 16px;margin:12px 0}
.warn{background:#fff8e6;border-left:3px solid #e0a800;padding:10px 16px;margin:12px 0}
.gloss td{text-align:left;white-space:normal;font-size:13px}
.card{background:#fff;border:1px solid #e4e6ea;border-radius:9px;padding:16px 18px;margin:16px 0}
.card h3{margin-top:0;display:flex;align-items:baseline;gap:10px}
.tag{font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:11px;background:#eef3ff;color:#2451c4;white-space:nowrap}
.tag.w{background:#fff1e0;color:#a35a00}
.kv{display:grid;grid-template-columns:repeat(auto-fill,minmax(126px,1fr));gap:5px;margin:10px 0}
.kv div{background:#f7f8fa;border-radius:5px;padding:5px 8px;font-size:12.5px}
.kv b{display:block;font-size:15px}
.kv small{color:#6b7075}
.read{background:#f4f7ff;border-left:3px solid #7aa0f5;padding:9px 14px;margin:10px 0;font-size:14px}
.lnk{font-size:12.5px;color:#4a5058;margin-top:8px}
.zero{background:#fdecea;color:#c5221f;font-weight:700}
.hi{background:#eaf7ee}
ul.d{margin:6px 0 0 18px;font-size:14px}ul.d li{margin:3px 0}
</style>";

$H = "<meta charset='utf-8'><title>Корпус v3 — разбор по страницам</title>$css
<h1>Корпус v3 — разбор каждой страницы</h1>
<p class='note'>Числа — замер нашего <code>Analyzer</code>, тем же кодом, что мерил корпуса v1 и v2.
Синие врезки — то, что дало <b>чтение текста</b>; они главнее чисел. В корпусе v2 формальный классификатор
ошибся на трёх донорах из девяти, а здесь формальный поиск авторского блока дал пять ложных срабатываний из пяти.</p>";

// ── глоссарий ──────────────────────────────────────────────────────────────
$H .= "<h2>Что означает каждый параметр</h2><table class='gloss'><tr><th class='l' style='width:140px'>Параметр</th><th class='l'>Как считается</th></tr>";
foreach ($P as [$lab, $desc]) { $H .= "<tr><td class='l hd'>" . esc($lab) . "</td><td class='l'>" . esc($desc) . "</td></tr>"; }
$H .= "</table>";

// ── разбор по наборам ──────────────────────────────────────────────────────
foreach ($V3 as $n => $s) {
    $r = $s['read'] ?? [];
    $isBundle = !$s['shape']['single'];
    $H .= "<h2>Набор {$n} — " . esc($r['voice'] ?? '?') . ", " . ($isBundle ? "связка из " . count($s['pages']) . " страниц" : "одностраничник") . "</h2>";

    $H .= "<div class='read'><b>Жанр:</b> " . esc($r['genre'] ?? '—') . "<br>"
        . "<b>Регистр:</b> " . esc($r['register'] ?? '—') . " · <b>Голос:</b> " . esc($r['voice'] ?? '—')
        . " · <b>Авторский блок:</b> " . (isset($r['author_block']) ? ($r['author_block'] ? 'есть' : 'нет') : '—');
    if (!empty($r['author_note'])) { $H .= "<br><b>Про автора:</b> " . esc($r['author_note']); }
    $H .= "</div>";

    if (!empty($r['devices'])) {
        $H .= "<b>Приёмы, которые повторяются:</b><ul class='d'>";
        foreach ($r['devices'] as $d) { $H .= "<li>" . esc($d) . "</li>"; }
        $H .= "</ul>";
    }
    foreach (['numbers' => 'Как устроены числа', 'faq_position' => 'Где стоит FAQ',
              'emoji_placement' => 'Где стоят эмодзи', 'page_roles' => 'Как делятся роли',
              'frame' => 'Каркас страницы', 'block' => 'Формула блока', 'artifacts' => 'Артефакты генерации'] as $k => $lab) {
        if (!empty($r[$k])) { $H .= "<p class='note'><b>{$lab}.</b> " . esc($r[$k]) . "</p>"; }
    }
    if (!empty($r['no'])) {
        $H .= "<p class='warn'><b>Чего в этом наборе нет:</b> " . esc(implode(' · ', $r['no'])) . "</p>";
    }

    // карта файлов набора — для разбора ссылок
    $dir = "$ROOT/$n";
    $files = [];
    foreach (array_merge(glob("$dir/*.htm") ?: [], glob("$dir/*.html") ?: []) as $f) {
        $stem = mb_strtolower(pathinfo($f, PATHINFO_FILENAME));
        $files[mb_strlen($stem) > 14 ? 'main' : $stem] = $f;
    }

    // ── карточка на страницу ──
    $H .= "<h3>Страницы</h3>";
    foreach ($s['pages'] as $t => $p) {
        $tags = [];
        if (!empty($p['foreign'])) { $tags[] = "<span class='tag w'>другой сайт: бренд " . esc($p['brand_own']['ru'] ?: '?') . "</span>"; }
        $tags[] = "<span class='tag'>" . fmt($p['words']) . " слов</span>";
        $tags[] = "<span class='tag'>" . fmt($p['sections']) . " разделов</span>";
        if ($isBundle) { $tags[] = "<span class='tag'>" . fmt($p['intlinks']) . " ссылок</span>"; }

        $H .= "<div class='card'><h3>" . esc($t) . " " . implode(' ', $tags) . "</h3>";
        if (!empty($r['pages'][$t])) { $H .= "<div class='read'>" . esc($r['pages'][$t]) . "</div>"; }

        $H .= "<div class='kv'>";
        foreach ($P as $k => [$lab, $_]) {
            if ($k === 'words' || $k === 'sections') { continue; }
            if (!$isBundle && $k === 'intlinks') { continue; }
            $H .= "<div><small>" . esc($lab) . "</small><b>" . fmt($p[$k] ?? 0) . "</b></div>";
        }
        $H .= "</div>";

        // семантика страницы — только заметные кластеры
        $sem = $p['sem'] ?? [];
        arsort($sem);
        $top = array_slice($sem, 0, 5, true);
        $semStr = [];
        foreach ($top as $ck => $cv) { if ($cv > 0) { $semStr[] = esc($ck) . ' ' . fmt($cv); } }
        if ($semStr) { $H .= "<div class='lnk'><b>Семантика (топ-5, на 100 слов):</b> " . implode(' · ', $semStr) . "</div>"; }

        if ($isBundle && isset($files[$t])) {
            $by = outLinks($files[$t], $t, $files);
            if ($by) {
                $parts = [];
                foreach ($by as $to => $anc) { $parts[] = esc($to) . '×' . count($anc); }
                $all = array_merge(...array_values($by));
                $ph = array_count_values($all); arsort($ph);
                $H .= "<div class='lnk'><b>Ссылается на:</b> " . implode(', ', $parts)
                    . "<br><b>Самый частый анкор:</b> «" . esc((string) array_key_first($ph)) . "» ×" . reset($ph)
                    . " · уникальных анкоров " . round(count($ph) / max(1, count($all)) * 100) . "%</div>";
            }
        }
        $H .= "</div>";
    }

    // ── сводная матрица набора ──
    if ($isBundle) {
        $order = array_keys($s['pages']);
        $H .= "<h3>Сводная матрица набора {$n}</h3>";
        $H .= "<table><tr><th class='l'>Параметр</th>";
        foreach ($order as $t) { $H .= "<th>" . esc($t) . "</th>"; }
        $H .= "<th class='cor'>коридор</th></tr>";
        foreach ($P as $k => [$lab, $_]) {
            $vals = array_map(fn($x) => $x[$k] ?? 0, $s['pages']);
            $c = corridor(array_values($vals));
            $allZero = (max($vals) == 0);
            $H .= "<tr><td class='l hd'>" . esc($lab) . "</td>";
            foreach ($order as $t) { $H .= "<td class='" . ($allZero ? 'zero' : '') . "'>" . fmt($s['pages'][$t][$k] ?? 0) . "</td>"; }
            $H .= "<td class='cor'>" . fmt($c[0]) . " · " . fmt($c[1]) . " · " . fmt($c[2]) . "</td></tr>";
        }
        $H .= "</table>";

        // матрица ссылок
        $H .= "<h3>Кто на кого ссылается</h3><p class='note'>Строка — откуда, колонка — куда. Заполненная матрица без пустых клеток = полная сетка.</p>";
        $H .= "<table><tr><th class='l'>откуда \\ куда</th>";
        foreach ($order as $t) { $H .= "<th>" . esc($t) . "</th>"; }
        $H .= "<th class='cor'>всего</th></tr>";
        $inb = array_fill_keys($order, 0);
        foreach ($order as $from) {
            $by = isset($files[$from]) ? outLinks($files[$from], $from, $files) : [];
            $H .= "<tr><td class='l hd'>" . esc($from) . "</td>";
            $sum = 0;
            foreach ($order as $to) {
                if ($from === $to) { $H .= "<td class='na'>—</td>"; continue; }
                $c = isset($by[$to]) ? count($by[$to]) : 0;
                $sum += $c; $inb[$to] += $c;
                $H .= "<td class='" . ($c ? 'hi' : 'zero') . "'>{$c}</td>";
            }
            $H .= "<td class='cor'>{$sum}</td></tr>";
        }
        $H .= "<tr><td class='l hd'>входящих</td>";
        foreach ($order as $to) { $H .= "<td class='cor'>{$inb[$to]}</td>"; }
        $H .= "<td class='cor'></td></tr></table>";
    }
}

// ── одностраничники рядом ──────────────────────────────────────────────────
$sOrder = [];
foreach ($V3 as $n => $s) { if ($s['shape']['single']) { $sOrder[] = $n; } }
if ($sOrder) {
    $H .= "<h2>Шесть одностраничников рядом</h2>";
    $H .= "<table><tr><th class='l'>Параметр</th>";
    foreach ($sOrder as $n) { $H .= "<th>" . esc($n) . "<br><small>" . esc($V3[$n]['brand']['ru'] ?: '—') . "</small></th>"; }
    $H .= "<th class='cor'>коридор</th></tr>";
    foreach ($P as $k => [$lab, $_]) {
        if ($k === 'intlinks') { continue; }
        $vals = [];
        foreach ($sOrder as $n) { $vals[] = $V3[$n]['pages']['main'][$k] ?? 0; }
        $c = corridor($vals);
        $H .= "<tr><td class='l hd'>" . esc($lab) . "</td>";
        foreach ($vals as $v) { $H .= "<td>" . fmt($v) . "</td>"; }
        $H .= "<td class='cor'>" . fmt($c[0]) . " · " . fmt($c[1]) . " · " . fmt($c[2]) . "</td></tr>";
    }
    $H .= "</table>";
}

file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");
echo "STATUS " . json_encode(['sets' => count($V3)]) . "\n";

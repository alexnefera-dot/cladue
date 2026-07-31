<?php
declare(strict_types=1);

/**
 * Сравнение сгенерированного набора с донором корпуса v3.
 *
 *   php compare-v3.php <папка> <донор> --corpus=v3-single|v3-bundle [out.html]
 *
 * Отличия от compare-vs-donor.php (корпуса v1/v2): состав страниц берётся из
 * донора, а не из списка семи типов; для одностраничников параметры
 * перелинковки исключаются из зачёта — у них ссылок нет вовсе, и требовать их
 * значило бы записывать донору промах на ровном месте.
 */

require_once __DIR__ . '/src/Analyzer.php';

// Список имён — тот же, что у экстрактора: мерка обеих сторон обязана совпадать.
const FIRST_NAMES = 'Александр|Алексей|Анатолий|Андрей|Антон|Артём|Артем|Артур|Борис|Вадим|Валентин|Валерий|Василий|Виктор|Виталий|Владимир|Владислав|Вячеслав|Геннадий|Георгий|Григорий|Данил|Даниил|Денис|Дмитрий|Евгений|Егор|Иван|Игорь|Илья|Кирилл|Константин|Леонид|Максим|Марат|Марк|Михаил|Никита|Николай|Олег|Павел|Пётр|Петр|Роман|Руслан|Сергей|Станислав|Степан|Тимур|Фёдор|Федор|Эдуард|Юрий|Ярослав|Алина|Алла|Анастасия|Анна|Валентина|Валерия|Вера|Вероника|Виктория|Галина|Дарья|Диана|Екатерина|Елена|Елизавета|Жанна|Инна|Ирина|Кристина|Ксения|Лариса|Любовь|Людмила|Марина|Мария|Надежда|Наталья|Оксана|Ольга|Полина|Светлана|София|Тамара|Татьяна|Юлия|Яна';
require_once __DIR__ . '/src/NicheLexicon.php';

$pos = []; $CORPUS = 'v3-single';
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--corpus=(.*)$/', $a, $m)) { $CORPUS = $m[1]; } else { $pos[] = $a; }
}
$DIR = $pos[0] ?? ''; $DONOR = $pos[1] ?? ''; $OUT = $pos[2] ?? '';
if ($DIR === '' || $DONOR === '') {
    fwrite(STDERR, "usage: compare-v3.php <dir> <donor> [--corpus=v3-single|v3-bundle] [out.html]\n");
    exit(1);
}
$dataDir = __DIR__ . '/' . ($CORPUS === 'v3-bundle' ? 'data-v3-bundle' : 'data-v3-single');
$sites = json_decode((string) file_get_contents($dataDir . '/donors.json'), true)['sites'] ?? [];
if (!isset($sites[$DONOR])) { fwrite(STDERR, "донор '$DONOR' не найден в $dataDir\n"); exit(1); }
$D = $sites[$DONOR]['pages'];
$profile = json_decode((string) file_get_contents($dataDir . '/profile.json'), true);
$pagesCfg = $profile['pages'] ?? [];
$isSingle = !empty($sites[$DONOR]['shape']['single']);

$FIELDS = [
    'words' => ['Объём слов', 0], 'h2' => ['H2', 0], 'sections' => ['Разделы', 0],
    'lists' => ['Списки', 0], 'tables' => ['Таблицы', 0], 'quotes' => ['Цитаты', 0],
    'strong' => ['strong', 0], 'faq' => ['FAQ', 0], 'emoji' => ['Эмодзи', 0],
    'entities' => ['Сущности', 0], 'first_person' => ['«я»', 0], 'we' => ['«мы»', 0],
    'vy' => ['«вы»', 0], 'imperatives' => ['Императивы', 0],
    'numbers_per100' => ['Цифры/100', 1], 'adj_pct' => ['Прилаг%', 1],
    'nausea_acad' => ['Тошнота', 1], 'water' => ['Водность%', 1],
    'brand_ru' => ['Бренд RU', 0], 'brand_en' => ['Бренд EN', 0],
    // Экстрактор снимает эту долю с доноров давно, а в зачёт она не входила —
    // и связка проходила замер целиком, поставив бренд в 82% заголовков там,
    // где донор держит 13%. Сумма упоминаний при этом сходилась.
    'head_brand_pct' => ['Бренд в заголовках %', 1],
    // Опорный приём этого жанра — микро-кейс с именем. Корпус считает имена
    // давно, в зачёт они не входили: связка проходила замер целиком, имея одно
    // имя на главной там, где у донора двадцать одно.
    'names' => ['Имён в тексте', 0],
    // Четыре параметра, которых счётный замер не видел: он сходился сам с собой,
    // пока обе стороны считались одним неверным правилом. Абзацы ловят дробление
    // текста на строки, поимённые студии и тайтлы — профильность, которой в
    // генерации не было вовсе при совпавшем счёте «сущностей».
    'paragraphs' => ['Абзацев', 0], 'words_per_para' => ['Слов/абзац', 1],
    'providers_named' => ['Студий поимённо', 0], 'games_named' => ['Игр поимённо', 0],
    // Профильная лексика целиком: сумма нишевых терминов в прозе. Состав
    // отдельных терминов задаётся промптом, а этот параметр держит саму
    // насыщенность — по ней связка отставала на пятую часть при совпадении
    // всех прочих счётчиков.
    'terms_total' => ['Профильных терминов', 0],
];
// Ссылки идут в зачёт только у связок.
if (!$isSingle) { $FIELDS['intlinks'] = ['Ссылок внутри', 0]; }

/** в коридоре донора, если |наш−донор| <= max(25% донора, floor) */
function offx($our, $don, bool $rate = false): bool
{
    if ($don === null) { return false; }
    $d = abs($our - $don);
    return $d > max(0.25 * max(abs($don), 1), $rate ? 0.8 : 2.0);
}

$a = new Analyzer();
$brand = $sites[$DONOR]['brand'] ?? ['ru' => '', 'en' => ''];

function measure(Analyzer $a, string $t, string $raw, array $pagesCfg, array $brand): array
{
    // Замер идёт по копии без плейсхолдеров: иначе одно имя бренда считается
    // тремя словами и раздувает объём против донора.
    $norm = NicheLexicon::unplaceholder($raw);
    $r = $a->run([['name' => $t, 'url' => "/$t", 'html' => $norm, 'keyword' => '', 'lsi' => []]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    $txt = strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $norm));
    // Бренд в генерации — плейсхолдеры, в доноре — настоящее имя. Считаем и то
    // и другое: иначе замер даёт ложные нули на всю связку.
    $brRu = substr_count($raw, '%brand_name_ru%') ?: ($brand['ru'] ? mb_substr_count($txt, $brand['ru']) : 0);
    $brEn = substr_count($raw, '%brand_name_en%') ?: ($brand['en'] ? mb_substr_count($txt, $brand['en']) : 0);
    // Абзацы: короткие обрывки (< 40 символов) — это подписи и строки-чипы,
    // а не абзацы; порог тот же, что в экстракторе.
    // Абзацы берём из исходника: порог «длиннее 40 символов» отсекает подписи и
    // строки-чипы, а замена плейсхолдера на короткое имя сдвигала бы этот порог.
    // Слова же считаем по нормализованному тексту — там имя бренда одно слово.
    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $paras = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
    $paras = array_map([NicheLexicon::class, 'unplaceholder'], $paras);
    // ссылки на другие страницы набора
    $intl = 0;
    if (preg_match_all('#<a[^>]+href="([^"]+)"#i', $raw, $hm)) {
        $paths = [];
        foreach ($pagesCfg as $pt => $c) { $paths[rtrim($c['path'] ?? "/$pt", '/') ?: '/'] = $pt; }
        foreach ($hm[1] as $h) {
            $path = rtrim((string) parse_url(trim($h), PHP_URL_PATH), '/') ?: '/';
            $tt = $paths[$path] ?? null;
            if ($tt !== null && $tt !== $t) { $intl++; }
        }
    }
    return [
        'words' => (int) $m['words_total'], 'h2' => (int) $m['h2_count'],
        'sections' => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)),
        'lists' => (int) $m['list_count'], 'tables' => (int) ($m['table_count'] ?? 0),
        'quotes' => (int) ($m['quote_count'] ?? 0), 'strong' => (int) $m['strong_count'],
        'faq' => (int) $s['faq_questions'], 'emoji' => (int) $s['emoji'],
        'entities' => (int) $s['entities_count'], 'first_person' => (int) $s['first_person'],
        'we' => preg_match_all('~\b(мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|наших|нашим|нашими)\b~u', mb_strtolower($txt)),
        'vy' => (int) $s['second_person'], 'imperatives' => (int) $s['imperatives'],
        'numbers_per100' => round((float) $s['numbers_per_100w'], 1),
        'adj_pct' => round((float) $s['adj_pct'], 1),
        'nausea_acad' => round((float) $m['nausea_academic'], 1),
        'water' => round((float) $m['water_percent'], 1),
        'brand_ru' => $brRu, 'brand_en' => $brEn, 'intlinks' => $intl,
        'names' => preg_match_all('~\b(' . FIRST_NAMES . ')\b~u', $txt),
        // Доля заголовков с именем — считается по сырому html, как в экстракторе:
        // и по плейсхолдеру у нас, и по настоящему имени у донора.
        'head_brand_pct' => (function () use ($raw, $brand) {
            preg_match_all('~<h[23][^>]*>(.*?)</h[23]>~is', preg_replace('~<script\b.*?</script>~is', '', $raw), $hm);
            if (!$hm[1]) { return 0; }
            $re = '~%brand_name_(?:ru|en)%'
                . ($brand['ru'] ? '|' . preg_quote($brand['ru'], '~') : '')
                . ($brand['en'] ? '|' . preg_quote($brand['en'], '~') : '') . '~ui';
            $with = 0;
            foreach ($hm[1] as $x) { if (preg_match($re, strip_tags($x))) { $with++; } }
            return round($with / count($hm[1]) * 100, 1);
        })(),
        // Те же выражения, что в extract-donors-v3.php: обе стороны обязаны
        // считаться одним правилом, иначе замер снова сойдётся сам с собой.
        'providers_named' => NicheLexicon::countProviders(NicheLexicon::prose($norm)),
        'terms_total' => NicheLexicon::termsTotal(NicheLexicon::prose($norm)),
        'games_named' => NicheLexicon::countGames(NicheLexicon::prose($norm)),
        'paragraphs' => count($paras),
        'words_per_para' => $paras ? round(array_sum(array_map(
            fn($p) => count(preg_split('~\s+~u', $p, -1, PREG_SPLIT_NO_EMPTY)), $paras)) / count($paras), 1) : 0,
    ];
}

$meas = [];
foreach (array_keys($D) as $t) {
    foreach (["$DIR/$t.html", "$DIR/$t.htm"] as $f) {
        if (is_file($f)) { $meas[$t] = measure($a, $t, (string) file_get_contents($f), $pagesCfg, $brand); break; }
    }
    if (!isset($meas[$t])) { fwrite(STDERR, "нет файла для '$t' в $DIR\n"); }
}
if (!$meas) { fwrite(STDERR, "не найдено ни одной страницы\n"); exit(1); }

$totHit = 0; $totCnt = 0; $pageStat = []; $miss = [];
echo "\n=== СРАВНЕНИЕ с донором {$DONOR} (корпус {$CORPUS}) ===\n";
foreach ($meas as $t => $mm) {
    $hit = 0; $cnt = 0;
    foreach ($FIELDS as $k => [$lab, $rate]) {
        $dv = $D[$t][$k] ?? null;
        if ($dv === null) { continue; }
        $ok = !offx($mm[$k], $dv, (bool) $rate);
        $hit += $ok ? 1 : 0; $cnt++;
        if (!$ok) { $miss[$k][] = "$t " . $mm[$k] . " vs " . $dv; }
    }
    $totHit += $hit; $totCnt += $cnt;
    $pageStat[$t] = [$hit, $cnt];
    printf("  %-13s %d/%d = %d%%\n", $t, $hit, $cnt, $cnt ? round($hit / $cnt * 100) : 0);
}
$match = $totCnt ? (int) round($totHit / $totCnt * 100) : 0;
printf("  ИТОГО: %d/%d = %d%%\n", $totHit, $totCnt, $match);

if ($miss) {
    echo "\n=== ПРОМАХИ ПО ПАРАМЕТРАМ ===\n";
    uasort($miss, fn($x, $y) => count($y) <=> count($x));
    foreach ($miss as $k => $list) {
        printf("  %-15s %d : %s\n", $FIELDS[$k][0], count($list), implode(' | ', array_slice($list, 0, 6)));
    }
}
echo "STATUS " . json_encode(['match' => $match, 'hit' => $totHit, 'total' => $totCnt]) . "\n";

if ($OUT === '') { exit(0); }
$H = "<meta charset='utf-8'><title>Клон vs {$DONOR}</title><style>
body{font:15px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;max-width:1200px;margin:0 auto;padding:24px;background:#f7f8fa}
table{border-collapse:collapse;width:100%;background:#fff;font-size:12.5px}
th,td{border:1px solid #e4e6ea;padding:5px 8px;text-align:center}th{background:#eef3ff}
td.l,th.l{text-align:left}.ok{background:#e8f7ec;color:#137333}.bad{background:#fdecea;color:#c5221f}
.note{background:#fff;border-left:3px solid #2563eb;padding:9px 15px;margin:10px 0}</style>
<h1>Генерация vs донор <code>{$DONOR}</code> — {$match}%</h1>
<p class='note'>Зелёное — параметр в коридоре донора (допуск 25% или пол в 2 единицы / 0.8 для долей)."
   . ($isSingle ? " Параметры перелинковки исключены: у одностраничников ссылок нет." : "") . "</p><table><tr><th class='l'>Параметр</th>";
foreach (array_keys($meas) as $t) { $H .= "<th>" . htmlspecialchars($t) . "</th>"; }
$H .= "</tr>";
foreach ($FIELDS as $k => [$lab, $rate]) {
    $H .= "<tr><td class='l'><b>" . htmlspecialchars($lab) . "</b></td>";
    foreach ($meas as $t => $mm) {
        $dv = $D[$t][$k] ?? null;
        if ($dv === null) { $H .= "<td>—</td>"; continue; }
        $ok = !offx($mm[$k], $dv, (bool) $rate);
        $H .= "<td class='" . ($ok ? 'ok' : 'bad') . "'>" . $mm[$k] . "<br><small>ориг " . $dv . "</small></td>";
    }
    $H .= "</tr>";
}
$H .= "<tr><td class='l'><b>Совпадение</b></td>";
foreach ($pageStat as [$h, $c]) { $H .= "<td><b>" . ($c ? round($h / $c * 100) : 0) . "%</b></td>"; }
$H .= "</tr></table>";
file_put_contents($OUT, $H);
fwrite(STDERR, "→ $OUT\n");

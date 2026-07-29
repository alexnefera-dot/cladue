<?php
declare(strict_types=1);

/**
 * Брифы на правку: по странице — что мимо коридора и какие профильные термины
 * недобраны или перебраны. Нужен потому, что сводка промахов по параметрам
 * говорит «сколько», а правящему нужно «где и на сколько».
 *
 *   php brief-v3.php <папка> <донор> [--corpus=v3-bundle] [--out=папка]
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

$pos = []; $CORPUS = 'v3-bundle'; $OUTDIR = '';
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--corpus=(.*)$/', $a, $m))    { $CORPUS = $m[1]; }
    elseif (preg_match('/^--out=(.*)$/', $a, $m))   { $OUTDIR = $m[1]; }
    else { $pos[] = $a; }
}
[$DIR, $DONOR] = [$pos[0] ?? '', $pos[1] ?? ''];
if ($DIR === '' || $DONOR === '') {
    fwrite(STDERR, "usage: brief-v3.php <dir> <donor> [--corpus=…] [--out=dir]\n");
    exit(1);
}

$dataDir = __DIR__ . '/' . ($CORPUS === 'v3-bundle' ? 'data-v3-bundle' : 'data-v3-single');
$site = json_decode((string) file_get_contents($dataDir . '/donors.json'), true)['sites'][$DONOR] ?? null;
if ($site === null) { fwrite(STDERR, "донор '$DONOR' не найден\n"); exit(1); }
$D = $site['pages'];
$pagesCfg = json_decode((string) file_get_contents($dataDir . '/profile.json'), true)['pages'] ?? [];

// Словарь профильной лексики — из NicheLexicon, один на весь движок.
const NICHE_TERMS = NicheLexicon::TERMS;

$F = [
    'words' => ['объём слов', 0], 'h2' => ['H2', 0], 'sections' => ['разделов H2+H3', 0],
    'lists' => ['списков', 0], 'strong' => ['strong', 0], 'faq' => ['вопросительных знаков', 0],
    'emoji' => ['эмодзи', 0], 'entities' => ['категорий сущностей', 0],
    'first_person' => ['«я»', 0], 'we' => ['«мы»', 0], 'vy' => ['«вы»', 0],
    'imperatives' => ['императивов на -ЙТЕ/-ИТЕ', 0], 'numbers_per100' => ['цифр на 100 слов', 1],
    'adj_pct' => ['прилагательных %', 1], 'nausea_acad' => ['тошнота %', 1], 'water' => ['водность %', 1],
    'brand_ru' => ['бренд кириллицей', 0], 'brand_en' => ['бренд латиницей', 0],
    'paragraphs' => ['абзацев', 0], 'words_per_para' => ['слов в абзаце', 1],
    'providers_named' => ['названий студий в прозе', 0], 'games_named' => ['названий игр в прозе', 0],
    'terms_total' => ['профильных терминов всего', 0],
    'intlinks' => ['ссылок внутри', 0],
];

function offx($our, $don, bool $rate = false): bool
{
    if ($don === null) { return false; }
    return abs($our - $don) > max(0.25 * max(abs($don), 1), $rate ? 0.8 : 2.0);
}

$a = new Analyzer();
$brand = $site['brand'] ?? ['ru' => '', 'en' => ''];
$made = 0;
foreach (array_keys($D) as $t) {
    $file = null;
    foreach (["$DIR/$t.html", "$DIR/$t.htm"] as $f) { if (is_file($f)) { $file = $f; break; } }
    if ($file === null) { continue; }
    $raw = (string) file_get_contents($file);
    $r = $a->run([['name' => $t, 'url' => "/$t", 'html' => $raw, 'keyword' => '', 'lsi' => []]]);
    $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
    $txt = strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $raw));
    $prose = NicheLexicon::prose($raw);
    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $paras = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
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
    $our = [
        'words' => (int) $m['words_total'], 'h2' => (int) $m['h2_count'],
        'sections' => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)), 'lists' => (int) $m['list_count'],
        'strong' => (int) $m['strong_count'], 'faq' => (int) $s['faq_questions'],
        'emoji' => (int) $s['emoji'], 'entities' => (int) $s['entities_count'],
        'first_person' => (int) $s['first_person'],
        'we' => preg_match_all('~\b(мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|наших|нашим|нашими)\b~u', mb_strtolower($txt)),
        'vy' => (int) $s['second_person'], 'imperatives' => (int) $s['imperatives'],
        'numbers_per100' => round((float) $s['numbers_per_100w'], 1), 'adj_pct' => round((float) $s['adj_pct'], 1),
        'nausea_acad' => round((float) $m['nausea_academic'], 1), 'water' => round((float) $m['water_percent'], 1),
        'brand_ru' => substr_count($raw, '%brand_name_ru%'), 'brand_en' => substr_count($raw, '%brand_name_en%'),
        'paragraphs' => count($paras),
        'words_per_para' => $paras ? round(array_sum(array_map(
            fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)), $paras)) / count($paras), 1) : 0,
        'providers_named' => NicheLexicon::countProviders($prose),
        'games_named' => NicheLexicon::countGames($prose),
        'terms_total' => NicheLexicon::termsTotal($prose),
        'intlinks' => $intl,
    ];

    $lines = ["# Правка страницы {$t}.html", '', 'Коридор: |наше − донор| ≤ max(25% донора, 2) для счётных и 0.8 для долей.', ''];
    $bad = [];
    foreach ($F as $k => [$lab, $rate]) {
        $dv = $D[$t][$k] ?? null;
        if ($dv === null || !isset($our[$k])) { continue; }
        if (offx($our[$k], $dv, (bool) $rate)) {
            $dir = $our[$k] > $dv ? 'убрать' : 'добавить';
            $bad[] = "- **{$lab}**: у нас {$our[$k]}, у донора {$dv} → {$dir} (разница " . round(abs($our[$k] - $dv), 1) . ')';
        }
    }
    $lines[] = $bad ? "## Мимо коридора\n" . implode("\n", $bad) : '## Мимо коридора — нет';
    $lines[] = '';

    // Профильные термины: чего не хватает и чего лишнего
    $dt = $D[$t]['terms'] ?? [];
    $up = []; $down = [];
    foreach (NICHE_TERMS as $lab => $re) {
        $ourC = preg_match_all($re, $prose);
        $donC = (int) ($dt[$lab] ?? 0);
        if ($donC >= 4 && $ourC < $donC * 0.65) { $up[] = "- **{$lab}**: у нас {$ourC}, у донора {$donC} → нужно ещё ~" . max(1, (int) round($donC * 0.85 - $ourC)); }
        if ($ourC >= 5 && $donC < $ourC * 0.5)  { $down[] = "- **{$lab}**: у нас {$ourC}, у донора {$donC} → сократить примерно вдвое"; }
    }
    $lines[] = '## Профильные термины (считаются в абзацах и пунктах списков)';
    $lines[] = $up ? "### Недобор — дописать\n" . implode("\n", $up) : '### Недобора нет';
    $lines[] = '';
    $lines[] = $down ? "### Перебор — сократить\n" . implode("\n", $down) : '### Перебора нет';
    $lines[] = '';
    $lines[] = 'Правь только это. Остальные параметры в коридоре — не сбей их: объём, число абзацев, ссылки и вопросительные знаки трогать нельзя.';

    $out = ($OUTDIR ?: $DIR) . "/brief-{$t}.md";
    file_put_contents($out, implode("\n", $lines) . "\n");
    printf("→ %s (%d мимо, %d недобор, %d перебор)\n", basename($out), count($bad), count($up), count($down));
    $made++;
}
echo "STATUS " . json_encode(['briefs' => $made]) . "\n";

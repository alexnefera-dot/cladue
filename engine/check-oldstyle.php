<?php
declare(strict_types=1);
/**
 * Замер набора против СТАРОЙ связки (svyazka12bezzachina), а не против донора.
 * Коридор тот же: |наше − образец| ≤ max(25% образца, 2) для счётных и 0.8 для долей.
 *
 *   php check-oldstyle.php <папка-с-генерацией> [папка-образца]
 */
require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

$args = array_values(array_filter(array_slice($argv, 1), fn($a) => $a !== '--no-signals'));
$SIGNALS = !in_array('--no-signals', $argv, true);
$DIR = $args[0] ?? '';
$REF = $args[1] ?? '/tmp/old-bez-zachina/svyazka3';
if ($DIR === '') { fwrite(STDERR, "usage: check-oldstyle.php <dir> [ref]\n"); exit(1); }

$F = [
    'words' => ['объём слов', 0], 'h2' => ['H2', 0], 'sections' => ['разделов H2+H3', 0],
    'lists' => ['списков', 0], 'strong' => ['strong', 0], 'faq' => ['вопросительных знаков', 0],
    'emoji' => ['эмодзи', 0], 'first_person' => ['«я»', 0], 'vy' => ['«вы»', 0],
    'imperatives' => ['императивов', 0], 'numbers_per100' => ['цифр на 100 слов', 1],
    'adj_pct' => ['прилагательных %', 1], 'nausea_acad' => ['тошнота %', 1], 'water' => ['водность %', 1],
    'brand_ru' => ['бренд кириллицей', 0], 'brand_en' => ['бренд латиницей', 0],
    'paragraphs' => ['абзацев', 0], 'words_per_para' => ['слов в абзаце', 1],
    'games_named' => ['названий игр', 0], 'providers_named' => ['названий студий', 0],
    'terms_total' => ['профильных терминов', 0],
    // Сигналы, найденные разбором двух удачных наборов: при совпадении всех
    // привычных параметров расходились именно они.
    'h3_per_h2'  => ['H3 на один H2', 1],
    'h2_len'     => ['слов в заголовке', 1],
    'h2_quest'   => ['заголовков-вопросов %', 1],
    'cta'        => ['прямых призывов', 0],
    'honest'     => ['мест с минусом или риском', 0],
];
if (!$SIGNALS) {
    foreach (['h3_per_h2', 'h2_len', 'h2_quest', 'cta', 'honest'] as $k) { unset($F[$k]); }
}

function measureOne(Analyzer $a, string $t, string $raw): array
{
    $norm = NicheLexicon::unplaceholder($raw);
    $r = $a->run([['name' => $t, 'url' => "/$t", 'html' => $norm, 'keyword' => '', 'lsi' => []]]);
    $m = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];
    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $ps = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
    $wp = 0;
    foreach ($ps as $x) { $wp += count(preg_split('~\s+~u', NicheLexicon::unplaceholder($x), -1, PREG_SPLIT_NO_EMPTY)); }
    $prose = NicheLexicon::prose($norm);
    $flat = trim(preg_replace('~\s+~u', ' ', strip_tags($norm)));
    $hs = [];
    if (preg_match_all('~<h2[^>]*>(.*?)</h2>~is', $norm, $hm)) {
        foreach ($hm[1] as $h) {
            $x = trim(preg_replace('~\s+~u', ' ', strip_tags($h)));
            if ($x !== '') { $hs[] = $x; }
        }
    }
    $h3n = preg_match_all('~<h3[^>]*>~i', $norm);
    return [
        'h3_per_h2' => $hs ? round($h3n / count($hs), 1) : 0,
        'h2_len' => $hs ? round(array_sum(array_map(fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)), $hs)) / count($hs), 1) : 0,
        'h2_quest' => $hs ? round(count(array_filter($hs, fn($x) => mb_strpos($x, '?') !== false)) / count($hs) * 100, 1) : 0,
        'cta' => preg_match_all('~\b(зарегистрируйся|играй|жми|получи|забери|активируй|скачай|попробуй|переходи|успей)\b~ui', $flat),
        'honest' => preg_match_all('~\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле|важно понимать)\b~ui', $flat),
        'words' => (int) $m['words_total'], 'h2' => (int) $m['h2_count'],
        'sections' => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)),
        'lists' => (int) $m['list_count'], 'strong' => (int) $m['strong_count'],
        'faq' => (int) $s['faq_questions'], 'emoji' => (int) $s['emoji'],
        'first_person' => (int) $s['first_person'], 'vy' => (int) $s['second_person'],
        'imperatives' => (int) $s['imperatives'],
        'numbers_per100' => round((float) $s['numbers_per_100w'], 1),
        'adj_pct' => round((float) $s['adj_pct'], 1),
        'nausea_acad' => round((float) $m['nausea_academic'], 1),
        'water' => round((float) $m['water_percent'], 1),
        'brand_ru' => substr_count($raw, '%brand_name_ru%'),
        'brand_en' => substr_count($raw, '%brand_name_en%'),
        'paragraphs' => count($ps),
        'words_per_para' => $ps ? round($wp / count($ps), 1) : 0,
        'games_named' => NicheLexicon::countGames($prose),
        'providers_named' => NicheLexicon::countProviders($prose),
        'terms_total' => NicheLexicon::termsTotal($prose),
        'terms' => NicheLexicon::termCounts($prose),
    ];
}
function off($our, $ref, bool $rate): bool
{
    return abs($our - $ref) > max(0.25 * max(abs($ref), 1), $rate ? 0.8 : 2.0);
}

$a = new Analyzer();
$hit = 0; $cnt = 0; $miss = [];
echo "\n=== ЗАМЕР ПРОТИВ СТАРОЙ СВЯЗКИ ===\n";
foreach (glob("$REF/*.html") as $rf) {
    $t = pathinfo($rf, PATHINFO_FILENAME);
    if (!is_file("$DIR/$t.html")) { printf("  %-13s нет файла\n", $t); continue; }
    $R = measureOne($a, $t, (string) file_get_contents($rf));
    $O = measureOne($a, $t, (string) file_get_contents("$DIR/$t.html"));
    $h = 0; $c = 0;
    foreach ($F as $k => [$lab, $rate]) {
        $c++;
        if (off($O[$k], $R[$k], (bool) $rate)) { $miss[$lab][] = "$t {$O[$k]} vs {$R[$k]}"; }
        else { $h++; }
    }
    $hit += $h; $cnt += $c;
    printf("  %-13s %d/%d = %d%%\n", $t, $h, $c, round($h / $c * 100));
}
printf("  ИТОГО: %d/%d = %d%%\n", $hit, $cnt, $cnt ? round($hit / $cnt * 100) : 0);
if ($miss) {
    echo "\n=== ПРОМАХИ ===\n";
    uasort($miss, fn($x, $y) => count($y) <=> count($x));
    foreach ($miss as $lab => $list) {
        printf("  %-22s %d : %s\n", $lab, count($list), implode(' | ', array_slice($list, 0, 6)));
    }
}
echo "STATUS " . json_encode(['match' => $cnt ? (int) round($hit / $cnt * 100) : 0, 'hit' => $hit, 'total' => $cnt]) . "\n";

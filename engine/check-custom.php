<?php
declare(strict_types=1);

/**
 * Замер набора против КАСТОМНОГО профиля — целей из targets.json, а не против
 * страниц образца. Отличие от check-oldstyle.php: там сравниваются два текста,
 * здесь текст сравнивается с проектным решением.
 *
 *   php check-custom.php <папка-с-генерацией> <targets.json>
 *
 * Два сигнала односторонние: голых цифр — не больше цели, названных минусов —
 * не меньше. Остальное — обычный коридор 25%.
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

$DIR = $argv[1] ?? '';
$TGT = $argv[2] ?? '/tmp/cards-custom/targets.json';
if ($DIR === '' || !is_file($TGT)) {
    fwrite(STDERR, "usage: check-custom.php <dir> <targets.json>\n");
    exit(1);
}
$T = json_decode((string) file_get_contents($TGT), true);

const RE_CTA   = '~\b(зарегистрируйся|играй|жми|получи|забери|активируй|скачай|попробуй|переходи|успей)\b~ui';
const RE_MINUS = '~\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле|важно понимать)\b~ui';
const RE_FACT  = '~\d[\d\s]*\s*(?:₽|руб|%|мин\b|час\w*|дн\w+|сут\w+|мб|гб|x\d)~ui';

function measure(Analyzer $an, string $file): array
{
    $raw  = (string) file_get_contents($file);
    $norm = NicheLexicon::unplaceholder($raw);
    $r    = $an->run([['name' => 'p', 'url' => '/p', 'html' => $norm, 'keyword' => '', 'lsi' => []]]);
    $m    = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];
    $flat = trim(preg_replace('~\s+~u', ' ', strip_tags($norm)));

    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $ps = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
    $wp = 0;
    foreach ($ps as $x) { $wp += count(preg_split('~\s+~u', NicheLexicon::unplaceholder($x), -1, PREG_SPLIT_NO_EMPTY)); }

    $hs = [];
    if (preg_match_all('~<h2[^>]*>(.*?)</h2>~is', $norm, $hm)) {
        foreach ($hm[1] as $h) {
            $x = trim(preg_replace('~\s+~u', ' ', strip_tags($h)));
            if ($x !== '') { $hs[] = $x; }
        }
    }
    $h3 = preg_match_all('~<h3[^>]*>~i', $norm);

    return [
        'words' => (int) $m['words_total'], 'h2' => count($hs),
        'sections' => count($hs) + $h3,
        'lists' => (int) $m['list_count'], 'strong' => (int) $m['strong_count'],
        'faq' => (int) $s['faq_questions'], 'emoji' => (int) $s['emoji'],
        'paragraphs' => count($ps), 'words_per_para' => $ps ? round($wp / count($ps), 1) : 0,
        'adj_pct' => round((float) $s['adj_pct'], 1),
        'nausea_acad' => round((float) $m['nausea_academic'], 1),
        'water' => round((float) $m['water_percent'], 1),
        'imperatives' => (int) $s['imperatives'],
        'terms_total' => NicheLexicon::termsTotal(NicheLexicon::prose($norm)),
        'brand_total' => substr_count($raw, '%brand_name_ru%') + substr_count($raw, '%brand_name_en%'),
        'facts' => preg_match_all(RE_FACT, $flat),
        'minus' => preg_match_all(RE_MINUS, $flat),
        'cta' => preg_match_all(RE_CTA, $flat),
        'h3_per_h2' => $hs ? round($h3 / count($hs), 1) : 0,
        'h2_words' => $hs ? round(array_sum(array_map(fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)), $hs)) / count($hs), 1) : 0,
        'h2_quest' => $hs ? round(count(array_filter($hs, fn($x) => mb_strpos($x, '?') !== false)) / count($hs) * 100, 1) : 0,
    ];
}

$FIELDS = [
    'words' => ['объём слов', 0], 'h2' => ['H2', 0], 'sections' => ['разделов H2+H3', 0],
    'lists' => ['списков', 0], 'strong' => ['strong', 0], 'faq' => ['вопросительных знаков', 0],
    'emoji' => ['эмодзи', 0], 'paragraphs' => ['абзацев', 0], 'words_per_para' => ['слов в абзаце', 1],
    'adj_pct' => ['прилагательных %', 1], 'nausea_acad' => ['тошнота %', 1], 'water' => ['водность %', 1],
    'imperatives' => ['императивов', 0], 'terms_total' => ['профильных терминов', 0],
    'brand_total' => ['бренд-вставок', 0],
    'h3_per_h2' => ['H3 на один H2', 1], 'h2_words' => ['слов в заголовке', 1],
];

$an = new Analyzer();
$hit = 0; $cnt = 0; $miss = [];
echo "\n=== ЗАМЕР ПРОТИВ КАСТОМНОГО ПРОФИЛЯ ===\n";
foreach ($T as $type => $tg) {
    $f = "$DIR/$type.html";
    if (!is_file($f)) { printf("  %-13s нет файла\n", $type); continue; }
    $o = measure($an, $f);
    $h = 0; $c = 0;
    foreach ($FIELDS as $k => [$lab, $rate]) {
        $want = $tg[$k] ?? null;
        if ($want === null) { continue; }
        $c++;
        $ok = abs($o[$k] - $want) <= max(0.25 * max(abs($want), 1), $rate ? 0.8 : 2.0);
        if ($ok) { $h++; } else { $miss[$lab][] = "$type {$o[$k]} vs {$want}"; }
    }
    // Цифры и минусы — цели ДВУСТОРОННИЕ: уйти сильно ниже так же плохо, как
    // выше. Призывы и вопросы в заголовках остаются потолком.
    foreach ([
        ['голых цифр',  $o['facts'], $tg['facts_max'], 'both'],
        ['минусов',     $o['minus'], $tg['minus_min'], 'both'],
        ['призывов',    $o['cta'],   0,                'max'],
        ['вопросов в заголовках %', $o['h2_quest'], 0, 'max'],
    ] as [$lab, $val, $lim, $dir]) {
        $c++;
        if ($dir === 'both') {
            $ok = abs($val - $lim) <= max(0.25 * max($lim, 1), 2);
            $want = "{$lim} ±25%";
        } else {
            $ok = $val <= $lim * 1.15 + 1;
            $want = "≤{$lim}";
        }
        if ($ok) { $h++; } else { $miss[$lab][] = "$type {$val} против {$want}"; }
    }
    $hit += $h; $cnt += $c;
    printf("  %-13s %d/%d = %d%%\n", $type, $h, $c, round($h / $c * 100));
}
printf("  ИТОГО: %d/%d = %d%%\n", $hit, $cnt, $cnt ? round($hit / $cnt * 100) : 0);
if ($miss) {
    echo "\n=== ПРОМАХИ ===\n";
    uasort($miss, fn($x, $y) => count($y) <=> count($x));
    foreach ($miss as $lab => $list) {
        printf("  %-24s %d : %s\n", $lab, count($list), implode(' | ', array_slice($list, 0, 5)));
    }
}
echo "STATUS " . json_encode(['match' => $cnt ? (int) round($hit / $cnt * 100) : 0, 'hit' => $hit, 'total' => $cnt]) . "\n";

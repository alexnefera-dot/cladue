<?php
declare(strict_types=1);

/**
 * Проверка тест-генераций на «попадание в корпус» (не превзойти!).
 * Гоняет сгенерённые HTML-страницы через движок v2 и сверяет ключевые метрики
 * с коридорами profile.json [p10..p90].
 *
 * Использование:
 *   php verify.php <папка с *.html>   (имя файла = тип: main.html, zerkalo.html, …)
 *   php verify.php --file=path.html --type=main
 *
 * Легенда: ✓ в коридоре · ~ рядом (±20%) · ↑ выше p90 (перебор) · ↓ ниже p10 · ✗ мимо
 */

require_once __DIR__ . '/src/Analyzer.php';

$profile = json_decode((string) file_get_contents(__DIR__ . '/data/profile.json'), true)['types'];

$args = array_slice($argv, 1);
$files = []; // [type => path]
$single = ['file' => '', 'type' => ''];
$dir = '';
foreach ($args as $a) {
    if (str_starts_with($a, '--')) {
        [$k, $v] = array_pad(explode('=', substr($a, 2), 2), 2, '');
        if (array_key_exists($k, $single)) { $single[$k] = $v; }
    } elseif ($dir === '') { $dir = $a; }
}
if ($single['file'] !== '') {
    $files[$single['type'] ?: 'main'] = $single['file'];
} elseif ($dir !== '') {
    foreach (glob(rtrim($dir, '/') . '/*.html') ?: [] as $p) {
        $base = strtolower(pathinfo($p, PATHINFO_FILENAME));
        foreach (array_keys($profile) as $type) {
            if (str_contains($base, $type)) { $files[$type] = $p; break; }
        }
    }
}
if ($files === []) {
    fwrite(STDERR, "Не найдено HTML для проверки. Укажи папку или --file/--type.\n");
    exit(1);
}

// метрика => [путь к значению, ключ профиля, «не превышать?»]
$METRICS = [
    ['Слов',            fn($m,$s) => $m['words_total'],                 'words',          true],
    ['Уник. слов %',    fn($m,$s) => pct($m['words_unique_ratio']),      'uniq_pct',       false],
    ['Ср. длина предл', fn($m,$s) => $m['sentence_avg_len'],             'sent_len',       false],
    ['Абзацев',         fn($m,$s) => $m['paragraphs_total'],             'paragraphs',     true],
    ['H2',              fn($m,$s) => $m['h2_count'],                     'h2',             true],
    ['Списков',         fn($m,$s) => $m['list_count'],                   'lists',          true],
    ['strong',          fn($m,$s) => $m['strong_count'],                 'strong',         true],
    ['Тошнота класс.',  fn($m,$s) => $m['nausea_classic'],              'nausea_classic', true],
    ['Тошнота акад. %', fn($m,$s) => $m['nausea_academic'],             'nausea_acad',    true],
    ['Водность %',      fn($m,$s) => $m['water_percent'],               'water',          true],
    ['Индекс Флеша',    fn($m,$s) => $m['flesch_reading_ease'],         'flesch',         false],
    ['Числа/100 слов',  fn($m,$s) => $s['numbers_per_100w'],            'numbers_per100', true],
    ['Прилаг. %',       fn($m,$s) => $s['adj_pct'],                     'adj_pct',        false],
    ['Пассив %',        fn($m,$s) => $s['passive_pct'],                 'passive_pct',    true],
    ['Первое лицо',     fn($m,$s) => $s['first_person'],               'first_person',   false],
    ['«вы»',            fn($m,$s) => $s['second_person'],              'vy',             false],
    ['Императивы',      fn($m,$s) => $s['imperatives'],                'imperatives',    false],
    ['Эмодзи (тело)',   fn($m,$s) => $s['emoji'],                      'emoji_body',     true],
    ['Сущностей',       fn($m,$s) => $s['entities_count'],             'entities',       false],
    ['FAQ вопросов',    fn($m,$s) => $s['faq_questions'],              'faq',            false],
];

function pct(float $v): float { return $v <= 1.0 ? round($v * 100, 1) : round($v, 1); }

function verdict(float $val, array $triple, bool $noExceed): string
{
    [$p10, , $p90] = $triple;
    $lo = min($p10, $p90); $hi = max($p10, $p90);
    if ($val >= $lo && $val <= $hi) { return '✓'; }
    if ($val > $hi) { return ($val <= $hi * 1.2) ? '~↑' : ($noExceed ? '↑' : '~↑'); }
    return ($val >= $lo * 0.8) ? '~↓' : '↓';
}

$analyzer = new Analyzer();
$allPass = 0; $allTot = 0;

foreach ($files as $type => $path) {
    $html = (string) file_get_contents($path);
    $res = $analyzer->run([[ 'name' => $type, 'url' => $type . '.html', 'html' => $html, 'keyword' => '', 'lsi' => [] ]]);
    $page = $res['pages'][0];
    $m = $page['metrics'];
    $s = $page['stylistics'];
    $P = $profile[$type];

    echo "\n═══ " . strtoupper($type) . "  ($path)\n";
    printf("%-18s %10s   %-22s %s\n", 'Метрика', 'Значение', 'Коридор [p10..p90]', '');
    echo str_repeat('─', 62) . "\n";
    $pass = 0; $tot = 0;
    foreach ($METRICS as [$label, $get, $key, $noExceed]) {
        if (!isset($P[$key])) { continue; }
        $val = (float) $get($m, $s);
        $triple = $P[$key];
        $v = verdict($val, $triple, $noExceed);
        $tot++;
        if ($v === '✓') { $pass++; }
        printf("%-18s %10s   [%s .. %s] med %s  %s\n",
            $label, rtrim(rtrim(number_format($val, 2, '.', ''), '0'), '.'),
            $triple[0], $triple[2], $triple[1], $v);
    }
    $allPass += $pass; $allTot += $tot;
    printf("── попадание: %d/%d (%d%%)\n", $pass, $tot, (int) round($pass / max(1, $tot) * 100));
}

printf("\n════ ИТОГО по набору: %d/%d метрик в коридоре (%d%%)\n", $allPass, $allTot, (int) round($allPass / max(1, $allTot) * 100));

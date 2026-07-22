<?php
declare(strict_types=1);

/**
 * Снимает ПЕР-САЙТОВЫЕ профили с корпуса 50 сайтов → data/donors.json.
 * Каждый сайт-донор = его собственные измеренные значения по 7 типам страниц +
 * выведенный стиль (первое лицо / «вы» / эмодзи). Генератор в донор-режиме
 * целится в конкретный сайт, а не в общее распределение корпуса.
 *
 *   php extract-donors.php <папка с 50 сайтами> [out.json]
 * Папка: <корень>/<имя_сайта>/<тип>.html (7 типов на сайт).
 */

require_once __DIR__ . '/src/Analyzer.php';

$root = $argv[1] ?? '';
$out  = $argv[2] ?? (__DIR__ . '/data/donors.json');
if ($root === '' || !is_dir($root)) {
    fwrite(STDERR, "Укажи папку с сайтами корпуса.\n"); exit(1);
}
$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];
$a = new Analyzer();

$sites = [];
foreach (glob(rtrim($root,'/') . '/*', GLOB_ONLYDIR) as $dir) {
    $name = basename($dir);
    if (str_starts_with($name, '__')) continue;
    $have = 0; $pages = [];
    $fp=[]; $vy=[]; $emo=0;
    foreach ($TYPES as $t) {
        $f = "$dir/$t.html";
        if (!is_file($f)) continue;
        $r = $a->run([[ 'name'=>$t,'url'=>"$t.html",'html'=>file_get_contents($f),'keyword'=>'','lsi'=>[] ]]);
        $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
        $have++;
        $pages[$t] = [
            'words'          => $m['words_total'],
            'h2'             => $m['h2_count'],
            'sections'       => $m['h2_count'] + ($m['h3_count'] ?? 0),
            'lists'          => $m['list_count'],
            'tables'         => $m['table_count'] ?? 0,
            'quotes'         => $m['quote_count'] ?? 0,
            'strong'         => $m['strong_count'],
            'faq'            => $s['faq_questions'],
            'numbers_per100' => round((float)$s['numbers_per_100w'],1),
            'adj_pct'        => round((float)$s['adj_pct'],1),
            'emoji'          => $s['emoji'],
            'entities'       => $s['entities_count'],
            'first_person'   => $s['first_person'],
            'vy'             => $s['second_person'],
            'imperatives'    => $s['imperatives'],
            'nausea_acad'    => round((float)$m['nausea_academic'],1),
            'water'          => round((float)$m['water_percent'],1),
        ];
        $fp[] = $s['first_person']; $vy[] = $s['second_person'];
        if ($t === 'main') $emo = $s['emoji'];
    }
    if ($have < 5) continue; // неполные сайты пропускаем
    $avg = fn($arr) => $arr ? array_sum($arr)/count($arr) : 0;
    $sites[$name] = [
        'pages' => $pages,
        'style' => [
            'first_person' => $avg($fp) >= 10,
            'vy'           => $avg($vy) >= 3,
            'emoji_site'   => $emo >= 3,
            'fp_avg'       => round($avg($fp),1),
            'vy_avg'       => round($avg($vy),1),
        ],
    ];
}

// таблица-код требует table_count в metrics; если его нет — добираем через SeoMetrics
file_put_contents($out, json_encode([
    '_meta' => ['purpose' => 'Пер-сайтовые профили корпуса. Донор-режим генератора целится в конкретный сайт.', 'count' => count($sites)],
    'sites' => $sites,
], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
fwrite(STDERR, "→ $out: доноров " . count($sites) . "\n");

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

/**
 * Классификатор регистра письма по лексическим сигналам сайта.
 * Нормируем на 1000 слов и решаем по приоритету: слэнг → дерзкий/разговорный,
 * иначе первое лицо → экспертный, «ты» → разговорный, восклицания → рекламный,
 * «вы» → деловой, иначе → нейтральный.
 */
function classifyRegister(array $r): string
{
    $w = max(1, (int) $r['words']);
    $k = 1000.0 / $w;
    $slang = $r['slang'] * $k;
    $excl  = $r['excl'] * $k;
    $ty    = $r['ty'] * $k;
    $vy    = $r['vy'] * $k;
    $fp    = $r['fp'] * $k;

    if ($slang >= 1.2) { return $excl >= 3 ? 'derzkiy' : 'razgovorny'; }
    if ($fp >= 12 && $fp > $vy) { return 'expert'; }
    if ($ty >= 4 && $ty > $vy) { return $excl >= 3 ? 'derzkiy' : 'razgovorny'; }
    if ($excl >= 5) { return 'reklamny'; }
    if ($vy >= 4) { return 'delovoy'; }
    return 'neutral';
}

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
    $reg = ['ty'=>0,'vy'=>0,'excl'=>0,'slang'=>0,'fp'=>0,'words'=>0,'emoji'=>0]; // сигналы регистра
    foreach ($TYPES as $t) {
        $f = "$dir/$t.html";
        if (!is_file($f)) continue;
        $rawHtml = file_get_contents($f);
        $r = $a->run([[ 'name'=>$t,'url'=>"$t.html",'html'=>$rawHtml,'keyword'=>'','lsi'=>[] ]]);
        $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
        $have++;
        // лексические сигналы регистра из текста страницы
        $txt = mb_strtolower(strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is',' ',$rawHtml)));
        $reg['ty']   += preg_match_all('/\b(ты|тебе|тебя|тво(й|я|ё|и|его|ей)|тобой)\b/u', $txt);
        $reg['vy']   += preg_match_all('/\b(вы|вас|вам|ваш(а|е|и|его|ей)?)\b/u', $txt);
        $reg['excl'] += mb_substr_count($txt, '!');
        $reg['slang']+= preg_match_all('/\b(бро|бабк\w+|кэш\b|вайб\w*|погнали|врыв\w+|дерзай|тупи\w*|качай|фартов\w+|куш|профит|хардкор\w*|движ\w+)\b/u', $txt);
        $reg['fp']   += (int)$s['first_person'];
        $reg['emoji']+= (int)$s['emoji'];
        $reg['words']+= (int)$m['words_total'];
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
            'register'     => classifyRegister($reg),
        ],
    ];
}

// таблица-код требует table_count в metrics; если его нет — добираем через SeoMetrics
file_put_contents($out, json_encode([
    '_meta' => ['purpose' => 'Пер-сайтовые профили корпуса. Донор-режим генератора целится в конкретный сайт.', 'count' => count($sites)],
    'sites' => $sites,
], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
fwrite(STDERR, "→ $out: доноров " . count($sites) . "\n");

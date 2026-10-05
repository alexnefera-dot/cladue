<?php
// Водность по зонам страницы: где именно наш текст мокрее их текста.
// Вода — доля стоп-слов (TextMetrics::water), та же мера, что в PageMetrics.
require_once __DIR__ . '/../src/PageMetrics.php';
$ГУСТ = glob('/tmp/claude-0/-home-user-cladue/ea580ece-89cc-5463-b9fe-78c4a0a08b0d/scratchpad/new100-gustye/*');
$ТИПЫ = ['bonus','registracia','vhod','app','zerkalo','main'];
$зоны = function (string $f): array {
    $h = preg_replace('~<(script|style)\b.*?</\1>~is', ' ', (string) file_get_contents($f));
    $чисто = fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x)));
    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $h, $mp);
    preg_match_all('~<li\b[^>]*>(.*?)</li>~is', $h, $ml);
    preg_match_all('~<h[23]\b[^>]*>(.*?)</h[23]>~is', $h, $mh);
    // FAQ: ответы внутри блока вопросов
    preg_match_all('~<p class="faq-answer"[^>]*>(.*?)</p>~is', $h, $mf);
    if (!$mf[1]) { preg_match_all('~itemprop="text"[^>]*>(.*?)</~is', $h, $mf); }
    $faqТексты = array_map($чисто, $mf[1] ?? []);
    $абз = array_map($чисто, $mp[1] ?? []);
    // абзацы, не входящие в FAQ
    $абзБезFaq = array_values(array_filter($абз, fn($t) => !in_array($t, $faqТексты, true)));
    // зачин — первый абзац до первого h2
    $доH2 = mb_strpos($h, '<h2');
    $зачин = [];
    if ($доH2 !== false) {
        preg_match_all('~<p\b[^>]*>(.*?)</p>~is', mb_substr($h, 0, $доH2), $mz);
        $зачин = array_map($чисто, $mz[1] ?? []);
    }
    $тело = array_values(array_filter($абзБезFaq, fn($t) => !in_array($t, $зачин, true)));
    return ['зачин' => $зачин, 'абзацы тела' => $тело, 'пункты' => array_map($чисто, $ml[1] ?? []),
            'ответы FAQ' => $faqТексты, 'заголовки' => array_map($чисто, $mh[1] ?? [])];
};
$вода = function (array $куски): array {
    $t = trim(implode(' ', $куски));
    if ($t === '') { return [0.0, 0]; }
    $м = new TextMetrics($t);
    return [$м->water(), $м->wordCount()];
};
$мед = function (array $v) { if (!$v) { return 0.0; } sort($v); return $v[intdiv(count($v), 2)]; };
printf("%-12s %-14s %8s %8s %8s %8s\n", 'тип', 'зона', 'наша', 'их мед', 'слов', 'их слов');
foreach ($ТИПЫ as $т) {
    $н = $зоны("samples/v5-final/nabor-751/$т.html");
    $их = [];
    foreach ($ГУСТ as $d) {
        $f = "$d/$т.html"; if (!is_file($f)) { continue; }
        foreach ($зоны($f) as $з => $к) { [$w, $n] = $вода($к); $их[$з]['в'][] = $w; $их[$з]['с'][] = $n; }
    }
    foreach ($н as $з => $к) {
        [$w, $n] = $вода($к);
        printf("%-12s %-14s %8.1f %8.1f %8d %8d\n", $т, $з, $w,
            $мед($их[$з]['в'] ?? []), $n, $мед($их[$з]['с'] ?? []));
    }
    echo "\n";
}

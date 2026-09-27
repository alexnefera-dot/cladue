<?php
/** Длины абзаца и число фраз в абзаце по типам страниц набора, в JSON. */
$папка = $argv[1] ?? '';
$итог = [];
foreach (glob("$папка/*.html") as $f) {
    $тип = basename($f, '.html');
    $html = (string) file_get_contents($f);
    $html = preg_replace('~(?is)<(script|style|svg)\b.*?</\1>~', ' ', $html);
    if (!preg_match_all('~<p\b[^>]*>(.*?)</p>~su', $html, $м)) { continue; }
    $длины = []; $фразы = [];
    foreach ($м[1] as $тело) {
        $чисто = trim(preg_replace('~\s+~u', ' ', strip_tags($тело)));
        if ($чисто === '') { continue; }
        $длины[] = count(preg_split('~\s+~u', $чисто));
        $фразы[] = max(1, preg_match_all('~[.!?…]+(?=\s|$)~u', $чисто));
    }
    if (!$длины) { continue; }
    $итог[$тип] = ['абзацев' => count($длины),
        'слов_абз' => round(array_sum($длины) / count($длины), 1),
        'фраз_абз' => round(array_sum($фразы) / count($фразы), 2)];
}
echo json_encode($итог, JSON_UNESCAPED_UNICODE);

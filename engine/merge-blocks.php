<?php
declare(strict_types=1);

/**
 * Склейка блоков, реализованных по промптам из split-page.php, в одну страницу.
 *
 *   php merge-blocks.php <dir> <type> [out.html]
 *
 * Ищет <dir>/<type>-1.html … -N.html, склеивает по порядку, подчищает стыки:
 * лишние обёртки/markdown-заборы, дубли дата-стампа, лишние JSON-LD (оставляем
 * последний), пустые строки на швах. По умолчанию пишет <dir>/<type>.html.
 */

$dir  = $argv[1] ?? '';
$type = $argv[2] ?? 'main';
$out  = $argv[3] ?? '';
if ($dir === '' || !is_dir($dir)) { fwrite(STDERR, "usage: merge-blocks.php <dir> <type> [out.html]\n"); exit(1); }
if ($out === '') { $out = "$dir/$type.html"; }

$parts = [];
for ($i = 1; $i <= 20; $i++) {
    $f = "$dir/$type-$i.html";
    if (!is_file($f)) { if ($i === 1) continue; break; }
    $parts[] = (string) file_get_contents($f);
}
if (!$parts) { fwrite(STDERR, "нет блоков $type-1.html… в $dir\n"); exit(1); }

$clean = static function (string $h): string {
    $h = preg_replace('~^\s*```(?:html)?\s*~i', '', $h);      // markdown-заборы
    $h = preg_replace('~\s*```\s*$~', '', $h);
    $h = preg_replace('~</?(?:html|head|body)[^>]*>~i', '', $h); // случайные обёртки
    return trim($h);
};
$parts = array_map($clean, $parts);

// JSON-LD: оставляем только последний (в последнем блоке)
$last = count($parts) - 1;
foreach ($parts as $i => &$p) {
    if ($i !== $last) { $p = preg_replace('~<script[^>]*application/ld\+json[^>]*>.*?</script>~is', '', $p); }
}
unset($p);

// дата-стамп: только один, в последнем блоке
$stampRx = '~<p[^>]*>\s*(?:<em>)?\s*Последнее обновление:.*?</p>\s*~isu';
$stamps = 0;
foreach ($parts as $i => &$p) {
    if (preg_match_all($stampRx, $p, $m)) {
        foreach ($m[0] as $hit) { $stamps++; if ($i !== $last || $stamps > 1) { $p = str_replace($hit, '', $p); } }
    }
}
unset($p);

$html = trim(preg_replace("~\n{3,}~", "\n\n", implode("\n\n", array_filter(array_map('trim', $parts)))));
file_put_contents($out, $html . "\n");

$words = count(preg_split('~\s+~u', trim(strip_tags(preg_replace('~<script.*?</script>~su', ' ', $html))), -1, PREG_SPLIT_NO_EMPTY));
$h2 = preg_match_all('~<h2\b~i', $html);
$ld = preg_match_all('~application/ld\+json~i', $html);
fwrite(STDERR, "→ $out | блоков " . count($parts) . " | ~$words слов | H2 $h2 | JSON-LD $ld\n");
echo "STATUS " . json_encode(['blocks' => count($parts), 'words' => $words, 'jsonld' => $ld]) . "\n";

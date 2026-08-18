<?php
// шинглы страницы против одного файла и локатор совпавших блоков
function chist(string $h): string {
    $h = preg_replace('~<(script|style)\b.*?</\1>~is', ' ', $h);
    $h = preg_replace('~%[a-z_]+%~u', ' бренд ', $h);
    $h = preg_replace('~<[^>]+>~', ' ', $h);
    $h = mb_strtolower(html_entity_decode($h, ENT_QUOTES, 'UTF-8'));
    $h = preg_replace('~[^а-яёa-z0-9 ]+~u', ' ', $h);
    return trim(preg_replace('~\s+~u', ' ', $h));
}
function shingles(string $t, int $n = 6): array {
    $w = preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY);
    $o = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $o[md5(implode(' ', array_slice($w, $i, $n)))] = 1; }
    return $o;
}

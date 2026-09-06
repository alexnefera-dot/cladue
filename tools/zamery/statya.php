<?php
$dir = $argv[1];
$imya = basename($dir);
$out = $argv[2];
$titles = ['main'=>'Главная страница','app'=>'Мобильное приложение','bonus'=>'Бонусы и промокоды',
 'registracia'=>'Регистрация','slots'=>'Игровые автоматы','vhod'=>'Вход в личный кабинет','zerkalo'=>'Зеркало сайта'];
$L = [];
$L[] = "# $imya — готовая статья";
$L[] = '';
$L[] = 'Семь страниц комплекта, порядок публикации сверху вниз. Имя площадки стоит';
$L[] = 'плейсхолдерами `%brand_name_en%` и `%brand_name_ru%` — подставляется при вёрстке.';
$L[] = 'Ссылки в тексте ведут на соседние страницы комплекта.';
$L[] = '';
foreach ($titles as $t => $zag) {
    $f = "$dir/$t.html";
    if (!is_file($f)) { continue; }
    $h = (string) file_get_contents($f);
    $L[] = '';
    $L[] = '---';
    $L[] = '';
    $L[] = "# $zag";
    $L[] = '';
    // FAQ
    $h = preg_replace('~<details[^>]*>\s*<summary[^>]*>(.*?)</summary>.*?<div itemprop="text"><p>(.*?)</p></div>.*?</details>~is',
        "\n@@Q@@\\1\n@@A@@\\2\n", $h);
    $h = preg_replace('~</?(div|details)[^>]*>~i', '', $h);
    // блоки
    $h = preg_replace('~<h2[^>]*>(.*?)</h2>~is', "\n\n## \\1\n", $h);
    $h = preg_replace('~<h3[^>]*>(.*?)</h3>~is', "\n\n### \\1\n", $h);
    $h = preg_replace('~<blockquote[^>]*>(.*?)</blockquote>~is', "\n\n> \\1\n", $h);
    $h = preg_replace('~<li[^>]*>(.*?)</li>~is', "- \\1\n", $h);
    $h = preg_replace('~</?(ul|ol)[^>]*>~i', "\n", $h);
    // таблицы
    $h = preg_replace_callback('~<table[^>]*>(.*?)</table>~is', function ($m) {
        $rows = [];
        preg_match_all('~<tr[^>]*>(.*?)</tr>~is', $m[1], $rm);
        foreach ($rm[1] as $i => $r) {
            preg_match_all('~<t[hd][^>]*>(.*?)</t[hd]>~is', $r, $cm);
            $cells = array_map(fn($c) => trim(preg_replace('~\s+~u', ' ', $c)), $cm[1]);
            $rows[] = '| ' . implode(' | ', $cells) . ' |';
            if ($i === 0) { $rows[] = '|' . str_repeat('---|', count($cells)); }
        }
        return "\n\n" . implode("\n", $rows) . "\n";
    }, $h);
    $h = preg_replace('~<p[^>]*>(.*?)</p>~is', "\n\\1\n", $h);
    // разметка внутри строки
    $h = preg_replace('~<strong[^>]*>(.*?)</strong>~is', '**\\1**', $h);
    $h = preg_replace('~<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>~is', '[\\2](\\1)', $h);
    $h = preg_replace('~<[^>]+>~', '', $h);
    $h = html_entity_decode($h, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    // FAQ: вопрос жирным, ответ обычной строкой
    $h = preg_replace('~^@@Q@@(.*)$~mu', '**\\1**', $h);
    $h = str_replace('@@A@@', '', $h);
    $lines = preg_split('~\n~', $h);
    $prev = '';
    foreach ($lines as $ln) {
        $ln = rtrim($ln);
        if (trim($ln) === '') { if ($prev !== '') { $L[] = ''; $prev = ''; } continue; }
        $L[] = $ln; $prev = $ln;
    }
}
file_put_contents($out, implode("\n", $L) . "\n");
echo "готово: $out\n";

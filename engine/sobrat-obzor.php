<?php
declare(strict_types=1);

/**
 * Сборка обзорной страницы из прозы и спецификации.
 *
 *   php engine/sobrat-obzor.php <проза.html> <вариант.json> <куда/main.html>
 *
 * Проза пишется руками и содержит только текст и заголовки; там, где должен
 * встать приём вёрстки, ставится маркер:
 *
 *   <!--SLOTS-->    двенадцать карточек автоматов тремя полками
 *   <!--REVS-->     шесть отзывов с именем, стажем и звёздами
 *   <!--TBL0-->     первая тройка таблиц по валютам (₽/$/€)
 *   <!--TBL1-->     вторая тройка таблиц
 *   <!--BADGES-->   шесть плашек набора
 *
 * Всё остальное берётся из вариантa: числа, названия автоматов, имена
 * отзывов, префикс имён классов и таблица стилей. Разделение сделано затем,
 * что приёмы у всех версий одинаковы по количеству и различны по содержимому,
 * а руками они собираются с ошибками.
 *
 * Стили дописываются В КОНЕЦ файла: PageMetrics вырезает только <script>, и
 * блок <style> сверху сдвигает окно зачина — opener_key падает в ноль.
 */

$prose = $argv[1] ?? '';
$specPath = $argv[2] ?? '';
$out = $argv[3] ?? '';
if ($prose === '' || $specPath === '' || $out === '') {
    fwrite(STDERR, "usage: php engine/sobrat-obzor.php <проза.html> <вариант.json> <куда/main.html>\n");
    exit(1);
}
foreach ([$prose, $specPath] as $f) {
    if (!is_file($f)) { fwrite(STDERR, "нет файла: $f\n"); exit(1); }
}

$spec = json_decode((string) file_get_contents($specPath), true);
if (!is_array($spec)) { fwrite(STDERR, "битый json: $specPath\n"); exit(1); }
$P = $spec['prefiks'] ?? 'ob';
$img = $spec['kartinka'] ?? '';   // пусто — обложка текстовая, как у эталона

/** Таблица: шапка одна на тройку, тело меняется по валюте. */
$table = function (array $head, array $rows) use ($P): string {
    $th = '';
    foreach ($head as $h) { $th .= '<th>' . $h . '</th>'; }
    $tr = '';
    foreach ($rows as $row) {
        $td = '';
        foreach ($row as $c) { $td .= '<td>' . $c . '</td>'; }
        $tr .= '<tr>' . $td . "</tr>\n";
    }
    return '<div class="' . $P . '-grid"><table>' . "\n<tbody><tr>" . $th . "</tr>\n" . $tr . "</tbody></table></div>";
};

$switch = function (array $labels) use ($P): string {
    $s = '<div class="' . $P . '-tabs">';
    foreach ($labels as $i => $l) { $s .= '<span' . ($i === 0 ? ' class="on"' : '') . '>' . $l . '</span>'; }
    return $s . "</div>\n";
};

$troika = function (array $block) use ($table, $switch): string {
    return $switch(['₽', '$', '€']) . implode("\n", array_map(
        fn($rows) => $table($block['shapka'], $rows), $block['telo']
    ));
};

// ── карточки автоматов ──────────────────────────────────────────────
$slots = $switch($spec['sloty']['vkladki']);
foreach ($spec['sloty']['polki'] as $polka) {
    $slots .= "\n" . '<div class="' . $P . '-shelf">';
    foreach ($polka as $c) {
        $cover = $img !== ''
            ? '<img class="' . $P . '-cover" src="' . $img . '" alt="Барабаны автомата '
              . $c['imya'] . ' в каталоге %brand_name_ru%" width="960" height="600" loading="lazy">'
            : '<div class="' . $P . '-cover">' . $c['kod'] . '</div>';
        $slots .= "\n  " . '<div class="' . $P . '-tile">' . $cover
            . '<div class="' . $P . '-note"><b>' . $c['imya'] . '</b><br><small>'
            . $c['studiya'] . ' · <span class="' . $P . '-pct">' . $c['znachenie']
            . '</span></small></div></div>';
    }
    $slots .= "\n</div>";
}

// ── отзывы ──────────────────────────────────────────────────────────
$revs = '<div class="' . $P . '-voices">';
foreach ($spec['otzyvy'] as $r) {
    $revs .= "\n  " . '<div class="' . $P . '-voice"><div class="' . $P . '-head">'
        . '<span class="' . $P . '-ini">' . $r['bukva'] . '</span><div><b>' . $r['imya']
        . '</b><br><small>' . $r['stazh'] . '</small></div></div>'
        . '<div class="' . $P . '-score">' . $r['zvyozdy'] . "</div>\n  <p>" . $r['tekst'] . '</p></div>';
}
$revs .= "\n</div>";

// ── плашки ──────────────────────────────────────────────────────────
$badges = '<div class="' . $P . '-perks">';
foreach ($spec['plashki'] as $b) { $badges .= '<span class="' . $P . '-perk">' . $b . '</span>'; }
$badges .= '</div>';

// ── подстановка ─────────────────────────────────────────────────────
$html = (string) file_get_contents($prose);
$parts = [
    '<!--SLOTS-->'  => $slots,
    '<!--REVS-->'   => $revs,
    '<!--BADGES-->' => $badges,
    '<!--TBL0-->'   => $troika($spec['tablicy'][0]),
    '<!--TBL1-->'   => $troika($spec['tablicy'][1]),
];
foreach ($parts as $marker => $value) {
    if (substr_count($html, $marker) !== 1) {
        fwrite(STDERR, "маркер $marker встречается " . substr_count($html, $marker) . " раз, нужен один\n");
        exit(1);
    }
    $html = str_replace($marker, $value, $html);
}

// ── стили сжимаем и дописываем в конец ──────────────────────────────
$css = $spec['stili'] ?? '';
if ($css !== '' && is_file($css)) { $css = (string) file_get_contents($css); }
$css = preg_replace('~/\*.*?\*/~s', '', $css);
$css = preg_replace('~\s+~', ' ', (string) $css);
$css = preg_replace('~\s*([{}:;,>])\s*~', '$1', (string) $css);
$css = str_replace(';}', '}', (string) $css);
$html = rtrim($html) . "\n\n<style>" . trim((string) $css) . "</style>\n";

@mkdir(dirname($out), 0777, true);
file_put_contents($out, $html);
printf("собрано: %s (%d символов, CSS %d)\n", $out, mb_strlen($html), mb_strlen((string) $css));

<?php
declare(strict_types=1);

/**
 * Проставляет внутреннюю перелинковку и переводит бренд в переменные —
 * как это делает корпус на главной-хабе: ключевые фразы становятся анкорами
 * на другие страницы связки (с повторами и весами), бренд → плейсхолдеры.
 * Трогаем только абзацы и списки (<p>/<li>), не заголовки/таблицы/скрипты.
 *
 *   php inject-links.php <in.html> <out.html> [brand_ru] [brand_en] [domain]
 * Веса ссылок задаются $CAPS (близко к target_weights корпуса).
 */

[$_, $in, $out] = array_pad($argv, 3, null);
$brRu = $argv[3] ?? 'Cosmospin'; $brEn = $argv[4] ?? 'Cosmospin'; $dom = $argv[5] ?? null;
$maxTotal = isset($argv[6]) ? (int)$argv[6] : PHP_INT_MAX; // общий потолок ссылок на страницу (цель донора)
if (!$in || !is_file($in)) { fwrite(STDERR, "нет входного файла\n"); exit(1); }
$html = (string) file_get_contents($in);

// бренд → переменные (латиница обычно не склоняется; кириллицу ловим с основой)
if ($brEn) $html = str_replace($brEn, '%brand_name_en%', $html);
if ($brRu && $brRu !== $brEn) {
    // кириллический бренд со склонениями: <Осн>а/е/ом/у...
    $stem = preg_replace('/(ь|й)$/u', '', $brRu);
    $html = preg_replace('/\b'.preg_quote($stem,'/').'[а-яё]{0,3}/u', '%brand_name_ru%', $html);
}
if ($dom) $html = str_replace($dom, '%domain_name%', $html);

// анкоры: ключевой паттерн → [путь, макс. повторов]  (веса ≈ корпус: app/zerkalo/vhod/registr выше)
$CAPS = [
    ['~(приложени[а-яё]*|apk|android|андроид)~ui', '/app', 9],
    ['~(зеркал[а-яё]*)~ui',                         '/zerkalo', 8],
    ['~(вход[а-яё]*|войти|авторизац[а-яё]*)~ui',    '/vhod', 7],
    ['~(регистрац[а-яё]*)~ui',                      '/registracia', 7],
    ['~(слот[а-яё]*)~ui',                           '/slots', 7],
    ['~(бонус[а-яё]*)~ui',                          '/bonus', 2],
];
// не ставим ссылку на саму себя (self-link не считается перелинковкой)
$selfMap = ['zerkalo'=>'/zerkalo','vhod'=>'/vhod','registracia'=>'/registracia','slots'=>'/slots','bonus'=>'/bonus','app'=>'/app'];
$self = $selfMap[preg_replace('/\.html$/','',basename((string)$in))] ?? null;
if ($self !== null) $CAPS = array_values(array_filter($CAPS, fn($r) => $r[1] !== $self));
$used = array_fill(0, count($CAPS), 0);

$lines = explode("\n", $html);
foreach ($lines as &$ln) {
    $t = ltrim($ln);
    if (!(str_starts_with($t, '<p>') || str_starts_with($t, '<li>'))) continue; // только тело
    if (str_contains($ln, '<a ')) continue;                                       // уже есть ссылка
    foreach ($CAPS as $i => $rule) {
        if (array_sum($used) >= $maxTotal) break 2;                               // достигли цели донора
        if ($used[$i] >= $rule[2]) continue;
        [$re, $path] = $rule;
        // не оборачиваем внутри %...% плейсхолдеров
        $ln = preg_replace_callback($re, function ($m) use (&$used, $i, $rule, $path, $maxTotal) {
            if ($used[$i] >= $rule[2] || array_sum($used) >= $maxTotal) return $m[0];
            $used[$i]++;
            return '<a href="'.$path.'">'.$m[0].'</a>';
        }, $ln, 1);
    }
}
unset($ln);

file_put_contents($out, implode("\n", $lines));
$tot = array_sum($used);
fwrite(STDERR, "→ $out | ссылок: $tot (".implode('/', $used).") бренд→переменные\n");

<?php
declare(strict_types=1);

/**
 * Кто держит тошноту: слова с частотой больше единицы, по счёту самого движка.
 *
 *   php engine/instrumenty/toshnota.php <файл.html> [сколько]
 *
 * Приёмка называет число, но не говорит, какое слово его сделало. Без этого
 * правка идёт наугад: заменяешь синоним, а поле стоит на месте. Здесь тот же
 * contentFreq(), что и в TextMetrics, поэтому список совпадает с расчётом.
 *
 * Снимается вклад так: убрать ОДНО вхождение слова с частотой 2 снимает из
 * числителя сразу два — пара перестаёт быть повтором.
 */

require_once __DIR__ . '/../src/Analyzer.php';
require_once __DIR__ . '/../src/Parser.php';
require_once __DIR__ . '/../src/TextMetrics.php';

$file = $argv[1] ?? '';
$skolko = (int) ($argv[2] ?? 25);
if ($file === '' || !is_file($file)) {
    fwrite(STDERR, "usage: php engine/instrumenty/toshnota.php <файл.html> [сколько]\n");
    exit(1);
}
$html = (string) file_get_contents($file);
$a = new Analyzer();
$r = $a->run([['name' => 'x', 'url' => '/x', 'html' => $html, 'keyword' => '', 'lsi' => []]]);
$m = $r['pages'][0]['metrics'];

$parser = Parser::fromHtml($html);
$tm = new TextMetrics($parser->text);
$cf = [];
foreach ((new ReflectionClass($tm))->getMethod('contentFreq')->invoke($tm) as $w => $c) {
    if ($c > 1) { $cf[$w] = $c; }
}
arsort($cf);
$vsego = (int) ($m['words_total'] ?? 0);
$chislitel = array_sum($cf);
printf("%s\n  слов %d, повторов в числителе %d, тошнота %.1f %%\n\n", basename($file), $vsego, $chislitel, $m['nausea_academic']);
printf("  %-22s %5s %8s\n", 'слово', 'раз', 'вклад');
$i = 0;
foreach ($cf as $w => $c) {
    if ($i++ >= $skolko) { break; }
    printf("  %-22s %5d %7.1f %%\n", $w, $c, $c / $vsego * 100);
}
$cel = (float) ($argv[3] ?? 21.9);
printf("\n  чтобы уйти на %.1f %%, из числителя надо снять %d\n", $cel, max(0, (int) ceil($chislitel - $cel / 100 * $vsego)));

// Пары дешевле всего: убрать одно вхождение слова с частотой 2 снимает из
// числителя сразу два, потому что пара перестаёт быть повтором.
$pary = array_keys(array_filter($cf, fn($c) => $c === 2));
printf("\n  слов ровно по два (%d, каждая правка снимает 2):\n  %s\n", count($pary), implode(', ', $pary));

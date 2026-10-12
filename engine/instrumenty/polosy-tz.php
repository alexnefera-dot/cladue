<?php
/**
 * Профиль корпуса ТЗ: наша мерка по эталонным наборам новой семьи блоков.
 *
 * В репозитории этой семьи два набора — samples/v3-reference/7 (13 страниц,
 * все 19 блоков) и samples/dorgen-reference/set232 (7 страниц, 13 блоков).
 * Двух наборов на полосу не хватает: полоса из пары образцов — это точка с
 * разбросом, а не населённость. Инструмент поэтому печатает ЗНАЧЕНИЯ, а не
 * полосы, и ставит рядом нашу текущую цель и нашу выдачу — чтобы было видно,
 * какие поля двигает новая мебель.
 *
 *   php engine/instrumenty/polosy-tz.php [--типы=main,slots]
 */
require_once __DIR__ . '/../src/PageMetrics.php';
$корень = dirname(__DIR__, 2);
$ПОЛЯ = ['words','paragraphs','words_per_para','para_short','para_spread','sections','h2','h3',
         'anchors','nausea_acad','water','adj_pct','terms_total','fact_values','emoji','numbers_per100'];
$ТИПЫ = ['main','bonus','info','news','obzor','partnery','promo','registracia','slots','vhod','zerkalo','app'];
foreach (array_slice($argv, 1) as $а) {
    if (str_starts_with($а, '--типы=')) { $ТИПЫ = array_filter(explode(',', substr($а, strlen('--типы=')))); }
}

/** Метрики одной папки: тип → поле → значение. */
function померить(string $папка, array $типы, array $поля): array
{
    $итог = [];
    foreach ($типы as $т) {
        foreach ([".htm", ".html"] as $р) {
            $ф = "$папка/$т$р";
            if (!is_file($ф)) { continue; }
            $raw = (string) file_get_contents($ф);
            $м = PageMetrics::measure(new Analyzer($raw), $т, $raw,
                ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
            foreach ($поля as $k) { if (isset($м[$k]) && is_numeric($м[$k])) { $итог[$т][$k] = (float) $м[$k]; } }
            break;
        }
    }
    return $итог;
}

$эталон1 = померить("$корень/samples/v3-reference/7", $ТИПЫ, $ПОЛЯ);
$эталон2 = померить("$корень/samples/dorgen-reference/set232", $ТИПЫ, $ПОЛЯ);
$наши = [];
foreach ([823, 824, 825, 826, 827] as $н) {
    $наши[] = померить("$корень/samples/v5-final/nabor-$н", $ТИПЫ, $ПОЛЯ);
}
$профиль = json_decode((string) file_get_contents("$корень/engine/data-v5/profil-v5.json"), true);

function медиана(array $v): float { sort($v); $n = count($v); return $n ? ($n % 2 ? $v[intdiv($n,2)] : ($v[$n/2-1] + $v[$n/2]) / 2) : 0.0; }

foreach ($ТИПЫ as $т) {
    if (!isset($эталон1[$т]) && !isset($эталон2[$т])) { continue; }
    printf("\n=== %s\n%-16s %10s %10s %10s %12s\n", $т, 'поле', 'эталон-7', 'set232', 'мы (мед)', 'наша цель');
    foreach ($ПОЛЯ as $k) {
        $э1 = $эталон1[$т][$k] ?? null; $э2 = $эталон2[$т][$k] ?? null;
        $н = []; foreach ($наши as $набор) { if (isset($набор[$т][$k])) { $н[] = $набор[$т][$k]; } }
        if ($э1 === null && $э2 === null && !$н) { continue; }
        $ц = $профиль['страницы'][$т]['поля'][$k]['цель'] ?? null;
        printf("%-16s %10s %10s %10s %12s\n", $k,
            $э1 === null ? '—' : round($э1, 1), $э2 === null ? '—' : round($э2, 1),
            $н ? round(медиана($н), 1) : '—', $ц === null ? '—' : round((float) $ц, 1));
    }
}

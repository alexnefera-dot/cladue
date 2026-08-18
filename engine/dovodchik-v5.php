<?php
declare(strict_types=1);

/**
 * Доводчик v5: правит счётные величины, которые нельзя испортить.
 *
 *   php engine/dovodchik-v5.php <файл.html> <тип>   [--сухой]
 *   php engine/dovodchik-v5.php <папка-набора>      [--сухой]
 *
 * Граница та же, что у семистраничного доводчика: **трогает ли правка форму
 * слова**. Если да — правка закрыта, поле уходит в бриф писателю.
 *
 * Можно:
 *   эмодзи-маркер   — символ в начале пункта списка; ставится и снимается,
 *                     соседние слова не меняются;
 *   ol / ul         — тег списка, пункты не трогаются;
 *   пары FAQ        — блок «вопрос-ответ» целиком, из пула хвостов своего типа;
 *   разные значения — «RTP 97,2%» → «RTP 96,8%»: меняются только цифры, и
 *                     только на значение, уже встречающееся на этой странице.
 *                     Так `fact_values` (число РАЗНЫХ дробных процентов) идёт
 *                     вниз, а плотность цифр остаётся прежней.
 *
 * Нельзя (возвращается брифом):
 *   imperatives, anchors, on_topic_pct — это выбор слов, а не счёт;
 *   numbers_per100                     — убрать цифру значит переписать фразу;
 *   anchor_once_pct                    — сведение меток ломает падежи
 *                                        (проверено на `svedi.py` в v4);
 *   strong, words, paragraphs          — решает смысл фразы, а не счётчик.
 *
 * Правки идут только по прозе: то, что лежит внутри виджетов с классами,
 * доводчик не трогает — там разметка донорская и её ломать нечем.
 */

require_once __DIR__ . '/src/V5Blocks.php';
require_once __DIR__ . '/src/PageMetrics.php';

$сухой = in_array('--сухой', $argv, true);
$позиц = array_values(array_filter(array_slice($argv, 1), fn($a) => $a[0] !== '-'));
$цель  = $позиц[0] ?? '';
if ($цель === '') {
    fwrite(STDERR, "usage: php engine/dovodchik-v5.php <файл.html> <тип> | <папка> [--сухой]\n");
    exit(1);
}

$профиль = json_decode((string) file_get_contents(__DIR__ . '/data-v5/profil-v5.json'), true);
$пулы    = json_decode((string) file_get_contents(__DIR__ . '/data-v5/pools.json'), true);
if (!$профиль || !$пулы) { fwrite(STDERR, "нет выкладок в data-v5\n"); exit(1); }

/** Узлы прозы: то, что лежит на нулевой колонке без класса. */
function v5ПрозаУзлы(string $html): array
{
    return array_values(array_filter(v5Uzly($html),
        fn($u) => $u['класс'] === '' && in_array($u['тег'], ['h2', 'h3', 'p', 'ul', 'ol'], true)));
}

function v5Коридор(array $п): array
{
    $пол = $п['дробное'] ? 0.8 : 2.0;
    $д = max(0.25 * abs((float) $п['цель']), $пол);
    return [(float) $п['цель'] - $д, (float) $п['цель'] + $д];
}

/** ── правка 1: эмодзи-маркеры в пунктах списков ────────────────────── */
function v5ПравкаЭмодзи(string $html, int $надо, array $банкЭмодзи): array
{
    $эмо = '~[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]~u';
    $сделано = 0;
    if ($надо < 0) {
        // снимаем маркеры с начала пунктов, пока не выберем нужное число
        $html = preg_replace_callback('~(<li>\s*)(' . substr($эмо, 1, -2) . ')\s*~u',
            function ($m) use (&$надо, &$сделано) {
                if ($надо >= 0) { return $m[0]; }
                $надо++; $сделано++;
                return $m[1];
            }, $html);
        return [$html, $сделано];
    }
    if ($надо > 0 && $банкЭмодзи) {
        $i = 0;
        $html = preg_replace_callback('~(<li>\s*)(?!' . substr($эмо, 1, -2) . ')~u',
            function ($m) use (&$надо, &$сделано, $банкЭмодзи, &$i) {
                if ($надо <= 0) { return $m[0]; }
                $надо--; $сделано++;
                return $m[1] . $банкЭмодзи[$i++ % count($банкЭмодзи)] . ' ';
            }, $html);
    }
    return [$html, $сделано];
}

/** ── правка 2: доля нумерованных списков ───────────────────────────── */
function v5ПравкаСписков(string $html, float $цельДоля): array
{
    $ul = preg_match_all('~^<ul>~m', $html);
    $ol = preg_match_all('~^<ol>~m', $html);
    $всего = $ul + $ol;
    if ($всего === 0) { return [$html, 0]; }
    $надо = (int) round($всего * $цельДоля / 100) - $ol;
    $сделано = 0;
    if ($надо > 0) {
        $html = preg_replace_callback('~^<ul>(.*?)^</ul>~ms', function ($m) use (&$надо, &$сделано) {
            if ($надо <= 0) { return $m[0]; }
            $надо--; $сделано++;
            return '<ol>' . $m[1] . '</ol>';
        }, $html);
    } elseif ($надо < 0) {
        $html = preg_replace_callback('~^<ol>(.*?)^</ol>~ms', function ($m) use (&$надо, &$сделано) {
            if ($надо >= 0) { return $m[0]; }
            $надо++; $сделано++;
            return '<ul>' . $m[1] . '</ul>';
        }, $html);
    }
    return [$html, $сделано];
}

/** ── правка 3: число РАЗНЫХ дробных процентов ──────────────────────── */
function v5ПравкаЗначений(string $html, int $цель): array
{
    preg_match_all('~\d{1,3}[.,]\d\s*%~u', $html, $m);
    if (!$m[0]) { return [$html, 0]; }
    $счёт = array_count_values($m[0]);
    arsort($счёт);
    $разных = count($счёт);
    if ($разных <= $цель) { return [$html, 0]; }
    $оставить = array_slice(array_keys($счёт), 0, max(1, $цель));
    $убрать = array_slice(array_keys($счёт), max(1, $цель));
    $сделано = 0;
    foreach ($убрать as $i => $плохое) {
        $замена = $оставить[$i % count($оставить)];
        $было = $html;
        $html = str_replace($плохое, $замена, $html);
        if ($html !== $было) { $сделано++; }
    }
    return [$html, $сделано];
}

/**
 * Пара из пула приходит трафаретом, с прорезями. Вставлять её как есть нельзя:
 * в выдачу уезжает «Реально ли {ИМЯ} выиграл(а) {СУММА}?». Значения берутся из
 * паспорта набора, если он рядом, иначе из банков корпуса.
 */
function v5Заполнить(string $t, array $паспорт, array $банки): string
{
    return v5Zapolnit($t, function (string $ключ) use ($паспорт, $банки) {
        if ($ключ === 'СЛОТОВ' || $ключ === 'ПРОВАЙДЕРОВ') { return $паспорт['каталог'][$ключ] ?? '1 000'; }
        if ($ключ === 'ВЕЙДЖЕР' && isset($паспорт['вейджер'])) { return $паспорт['вейджер']; }
        if ($ключ === 'ИМЯ' && !empty($паспорт['герои']['м'])) {
            return $паспорт['герои']['м'][array_rand($паспорт['герои']['м'])];
        }
        if ($ключ === 'ИМЯЖ' && !empty($паспорт['герои']['ж'])) {
            return $паспорт['герои']['ж'][array_rand($паспорт['герои']['ж'])];
        }
        $b = array_keys($банки[$ключ] ?? []);
        return $b ? $b[array_rand($b)] : '';
    });
}

/** ── правка 4: число пар «вопрос-ответ» ────────────────────────────── */
function v5ПравкаFaq(string $html, int $надо, array $пулFaq): array
{
    if ($надо === 0) { return [$html, 0]; }
    if (!preg_match('~(<div class="faq-list">)(.*?)(\n\s*</div>)~s', $html, $m, PREG_OFFSET_CAPTURE)) {
        return [$html, 0];
    }
    preg_match_all('~^(\s*)<div class="faq-item[^"]*"(.*?)^\1</div>\n~ms', $html, $блоки, PREG_SET_ORDER);
    if (!$блоки) { return [$html, 0]; }
    $сделано = 0;
    if ($надо < 0) {
        // лишние пары снимаются с конца — первая помечена «open», её трогать нельзя
        for ($i = count($блоки) - 1; $i > 0 && $надо < 0; $i--, $надо++) {
            $html = str_replace($блоки[$i][0], '', $html);
            $сделано++;
        }
        return [$html, $сделано];
    }
    $образец = $блоки[count($блоки) - 1][0];
    $взятые = array_map(fn($x) => $x['в'], $пулFaq);
    for ($i = 0; $i < $надо && $i < count($пулFaq); $i++) {
        $пара = $пулFaq[$i];
        $новый = preg_replace('~(<h3 class="faq-question" itemprop="name">\s*).*?(\s*</h3>)~s',
            '$1' . str_replace('$', '\\$', $пара['в']) . '$2', $образец);
        $новый = preg_replace('~(<div itemprop="text">\s*).*?(\s*</div>)~s',
            '$1' . str_replace('$', '\\$', $пара['о']) . '$2', $новый);
        if (str_contains($html, $новый)) { continue; }
        $html = str_replace($образец, $образец . $новый, $html);
        $сделано++;
    }
    return [$html, $сделано];
}

// ── прогон ──────────────────────────────────────────────────────────
$файлы = [];
if (is_dir($цель)) {
    foreach (V5_TYPES as $t) { if (is_file("$цель/$t.html")) { $файлы[$t] = "$цель/$t.html"; } }
} else {
    $файлы[$позиц[1] ?? 'main'] = $цель;
}
if (!$файлы) { fwrite(STDERR, "нечего править\n"); exit(1); }

$паспортНабора = is_dir($цель) && is_file("$цель/nabor.json")
    ? (json_decode((string) file_get_contents("$цель/nabor.json"), true) ?: []) : [];

$a = new Analyzer();
$банкЭмодзи = array_slice(array_keys($пулы['общие']['эмодзи'] ?? []), 0, 12);
$бриф = [];
printf("══ доводчик v5%s ══\n\n", $сухой ? ' (сухой прогон)' : '');
printf("%-13s %-16s %8s %8s %8s  %s\n", 'страница', 'поле', 'было', 'цель', 'стало', 'правка');
echo str_repeat('─', 78), "\n";

foreach ($файлы as $тип => $f) {
    $html = (string) file_get_contents($f);
    $поля = $профиль['страницы'][$тип]['поля'] ?? [];
    $замер = fn(string $h) => PageMetrics::measure($a, $тип,
        preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $h), ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $до = $замер($html);

    // 1. эмодзи
    if (isset($поля['emoji']) && $поля['emoji']['держат']) {
        [$низ, $верх] = v5Коридор($поля['emoji']);
        $есть = (int) $до['emoji'];
        if ($есть < $низ || $есть > $верх) {
            $надо = (int) round($поля['emoji']['цель']) - $есть;
            [$новый, $n] = v5ПравкаЭмодзи($html, $надо, $банкЭмодзи);
            if ($n) { $html = $новый; }
            $стало = $замер($html)['emoji'];
            printf("%-13s %-16s %8s %8s %8s  %s\n", $тип, 'emoji', $есть,
                $поля['emoji']['цель'], $стало, $n ? "маркеров: $n" : 'нечего править');
        }
    }
    // 2. ol/ul
    if (isset($поля['ordered_pct']) && $поля['ordered_pct']['держат']) {
        [$низ, $верх] = v5Коридор($поля['ordered_pct']);
        $есть = (float) $до['ordered_pct'];
        if ($есть < $низ || $есть > $верх) {
            [$новый, $n] = v5ПравкаСписков($html, (float) $поля['ordered_pct']['цель']);
            if ($n) { $html = $новый; }
            printf("%-13s %-16s %8s %8s %8s  %s\n", $тип, 'ordered_pct', round($есть, 1),
                $поля['ordered_pct']['цель'], round($замер($html)['ordered_pct'], 1),
                $n ? "списков: $n" : 'нечего править');
        }
    }
    // 3. разные значения с процентом
    if (isset($поля['fact_values']) && $поля['fact_values']['держат']) {
        [$низ, $верх] = v5Коридор($поля['fact_values']);
        $есть = (int) $до['fact_values'];
        if ($есть > $верх) {
            [$новый, $n] = v5ПравкаЗначений($html, (int) round($поля['fact_values']['цель']));
            if ($n) { $html = $новый; }
            printf("%-13s %-16s %8s %8s %8s  %s\n", $тип, 'fact_values', $есть,
                $поля['fact_values']['цель'], $замер($html)['fact_values'], "значений сведено: $n");
        }
    }
    // 4. пары FAQ
    if (isset($поля['faq_pairs']) && $поля['faq_pairs']['держат']) {
        [$низ, $верх] = v5Коридор($поля['faq_pairs']);
        $есть = (int) $до['faq_pairs'];
        if ($есть < $низ || $есть > $верх) {
            $надо = (int) round($поля['faq_pairs']['цель']) - $есть;
            $пул = $пулы['хвосты'][$тип]['faq'] ?? [];
            shuffle($пул);
            $пул = array_map(fn($x) => [
                'в' => v5Заполнить($x['в'], $паспортНабора, $пулы['общие']['банки']),
                'о' => v5Заполнить($x['о'], $паспортНабора, $пулы['общие']['банки']),
            ], $пул);
            [$новый, $n] = v5ПравкаFaq($html, $надо, $пул);
            if ($n) { $html = $новый; }
            printf("%-13s %-16s %8s %8s %8s  %s\n", $тип, 'faq_pairs', $есть,
                $поля['faq_pairs']['цель'], $замер($html)['faq_pairs'], "пар: $n");
        }
    }

    if (!$сухой) { file_put_contents($f, $html); }

    // что осталось — в бриф
    $после = $замер($html);
    foreach ($поля as $k => $п) {
        if (!$п['держат'] || !isset($после[$k]) || !is_numeric($после[$k])) { continue; }
        [$низ, $верх] = v5Коридор($п);
        if ((float) $после[$k] >= $низ && (float) $после[$k] <= $верх) { continue; }
        $бриф[$тип][] = sprintf('%s %s→%s', $k,
            is_float($после[$k]) ? round((float) $после[$k], 1) : $после[$k], $п['цель']);
    }
}

if ($бриф) {
    echo "\n── бриф писателю: счётчиком не берётся ──\n";
    foreach ($бриф as $тип => $список) {
        printf("%-13s %s\n", $тип, implode(', ', array_slice($список, 0, 8)));
    }
}

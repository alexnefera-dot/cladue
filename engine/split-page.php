<?php
declare(strict_types=1);

/**
 * Блочная сборка длинной страницы: режет спеку на N блоков по секциям и пишет
 * отдельный промпт на каждый блок. Смысл — реалайзер стабильно держит цели на
 * коротком выходе (400–900 слов), а на 3000+ «плавает»: замеры показали разброс
 * главной 63–84% при ОДНОМ И ТОМ ЖЕ промпте. Блоки возвращают её в стабильную зону.
 *
 *   php split-page.php <spec-main.json> <out-dir> [--blocks=3]
 *
 * Пишет <out-dir>/prompt-main-1.md … -N.md. Счётные цели (H2, списки, таблицы,
 * цитаты, strong, ссылки, бренд, эмодзи, «вы»/«я», императивы, слова) делятся
 * пропорционально числу секций блока; плотностные (цифры/100, прилаг%, тошнота)
 * НЕ делятся. Опенер — только в первом блоке, FAQ + дата-стамп + JSON-LD — только
 * в последнем. Каждый блок получает список тем соседей, чтобы не дублировать.
 * Склейка — engine/merge-blocks.php.
 */

require_once __DIR__ . '/src/Generator/PromptBuilder.php';

$args = array_slice($argv, 1);
$specFile = ''; $outDir = ''; $blocks = 3;
foreach ($args as $a) {
    if (preg_match('/^--blocks=(\d+)$/', $a, $m)) { $blocks = max(2, (int) $m[1]); }
    elseif ($specFile === '') { $specFile = $a; }
    elseif ($outDir === '') { $outDir = $a; }
}
if ($specFile === '' || $outDir === '' || !is_file($specFile)) {
    fwrite(STDERR, "usage: split-page.php <spec.json> <out-dir> [--blocks=3]\n"); exit(1);
}
$spec = json_decode((string) file_get_contents($specFile), true);
if (!is_array($spec) || empty($spec['sections'])) { fwrite(STDERR, "плохая спека\n"); exit(1); }
@mkdir($outDir, 0777, true);

$type = $spec['type'] ?? 'main';
$sections = $spec['sections'];
// опенер — отдельная «секция-инструкция», в дележе не участвует
$opener = null;
foreach ($sections as $i => $s) { if (($s['role'] ?? '') === 'opener') { $opener = $s; unset($sections[$i]); break; } }
$sections = array_values($sections);
$total = count($sections);
if ($total < $blocks) { $blocks = max(2, $total); }

// ── распределение секций по блокам (ровными долями) ────────────────────────
$chunks = []; $per = (int) ceil($total / $blocks);
for ($b = 0; $b < $blocks; $b++) {
    $slice = array_slice($sections, $b * $per, $per);
    if ($slice) $chunks[] = $slice;
}
$blocks = count($chunks);

// ── деление целей ──────────────────────────────────────────────────────────
$COUNTED = ['words','h2','sections_total','lists','tables','quotes','strong','emoji_body',
            'brand_ru','brand_en','imperatives','vy','first_person','entities'];
$builder = new PromptBuilder();
$links = $spec['links'] ?? [];
$linkPer = $links ? (int) ceil(count($links) / $blocks) : 0;

$written = [];
foreach ($chunks as $bi => $chunk) {
    $share = count($chunk) / $total;               // доля блока
    $sub = $spec;
    $sub['sections'] = $chunk;
    // опенер — только в первый блок
    if ($bi === 0 && $opener !== null) { array_unshift($sub['sections'], $opener); }
    $sub['with_opener'] = ($bi === 0) ? ($spec['with_opener'] ?? false) : false;
    // Авторский блок стоит в начале страницы (в референсах позиция 3–9%),
    // значит в блочной сборке — только в ПЕРВОМ блоке.
    $sub['author_block'] = ($bi === 0) ? !empty($spec['author_block']) : false;

    // Цели ВСЕЙ страницы — до деления. Формулировки, которые зависят от того,
    // много параметра или мало («почти нет — это потолок»), должны решать по
    // странице, а не по куску: цель «8 обращений» после деления на три блока
    // превращалась в «~2», попадала под низкий порог и реалайзер её глушил.
    $sub['page_targets'] = $spec['targets'];

    // счётные цели — пропорционально; плотностные оставляем как есть
    foreach ($COUNTED as $k) {
        if (!isset($spec['targets'][$k])) continue;
        $v = $spec['targets'][$k];
        // сущности — это КАТЕГОРИИ, дробить нельзя: даём общий кап каждому блоку
        $sub['targets'][$k] = ($k === 'entities') ? $v : max(0, (int) round($v * $share));
    }
    // FAQ — целиком в последний блок
    $sub['targets']['faq_count'] = ($bi === $blocks - 1) ? ($spec['targets']['faq_count'] ?? 0) : 0;
    // Плотность цифр: блок не видит чисел соседей и тратит свой бюджет целиком,
    // поэтому на склейке они суммируются в перебор (замер: 4.8 при цели 2.9).
    // Компенсируем занижением цели для блоков.
    if (isset($sub['targets']['numbers_per100'])) {
        $sub['targets']['numbers_per100'] = round((float) $sub['targets']['numbers_per100'] * 0.7, 1);
    }
    // ссылки — свой ломоть
    $sub['links'] = $linkPer ? array_slice($links, $bi * $linkPer, $linkPer) : [];

    $prompt = $builder->build($sub);

    // ── блочная шапка: что это за кусок, чего НЕ делать ────────────────────
    $others = [];
    foreach ($chunks as $oi => $och) {
        if ($oi === $bi) continue;
        $t = [];
        foreach (array_slice($och, 0, 4) as $s) { $t[] = $s['topic'] ?? ($s['theme'] ?? ''); }
        $others[] = '  · блок ' . ($oi + 1) . ': ' . implode('; ', array_filter($t));
    }
    $head = [];
    $head[] = "# БЛОК " . ($bi + 1) . " из {$blocks} — фрагмент страницы «{$type}»";
    $head[] = "";
    $head[] = "Ты пишешь ТОЛЬКО этот фрагмент. Он будет склеен с остальными в одну страницу.";
    $head[] = "- Выдай ЧИСТЫЙ HTML-фрагмент: " . ($bi === 0
        ? "начало страницы" . (($sub['with_opener'] ?? false) ? " (с опенером)" : " (БЕЗ опенера — первым идёт содержательный абзац/H2)")
        : "продолжение страницы — начинай СРАЗУ с <h2>, без вступлений типа «итак» и без повторного представления бренда");
    $head[] = ($bi === $blocks - 1)
        ? "- Это ПОСЛЕДНИЙ блок: в нём FAQ-блок (если цель >0), дата-стамп «Последнее обновление: …» и финальный <script type=\"application/ld+json\">."
        : "- Это НЕ последний блок: НЕ пиши FAQ, НЕ ставь дата-стамп и НЕ добавляй JSON-LD — они будут в последнем блоке.";
    $head[] = "- Все цели ниже — ЦЕЛИ ЭТОГО БЛОКА (уже поделены на части). Соблюдай их для своего фрагмента.";
    if ($others) {
        $head[] = "- Соседние блоки пишут другие темы — НЕ дублируй их, не повторяй те же факты и заголовки:";
        $head = array_merge($head, $others);
    }
    $head[] = "";
    $head[] = "---";
    $head[] = "";

    $file = "$outDir/prompt-{$type}-" . ($bi + 1) . ".md";
    file_put_contents($file, implode("\n", $head) . $prompt);
    $written[] = basename($file) . " (секций " . count($chunk) . ", слов ~" . ($sub['targets']['words'] ?? '?') . ")";
}

fwrite(STDERR, "→ $outDir: блоков {$blocks}\n");
foreach ($written as $w) fwrite(STDERR, "   $w\n");
echo "STATUS " . json_encode(['blocks' => $blocks, 'type' => $type]) . "\n";

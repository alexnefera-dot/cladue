<?php
declare(strict_types=1);

/**
 * Карточки для КАСТОМНОГО профиля: не клон одного образца, а сборка из
 * нескольких по решению редактора.
 *
 *   php custom-card.php <куда> <дир-А> <дир-Б> [вес-А=0.5]
 *
 * Числовые параметры каждой страницы берутся смесью двух образцов с заданным
 * весом, а четыре сигнала (плотность цифр, призывы, названные минусы, глубина
 * подразделов) выставляются по верхней границе того, что показали удачные
 * наборы — их и проверяет `check-oldstyle.php --custom`.
 *
 * Смешивать вслепую нельзя: у образцов разный голос, и среднее между дневником
 * от «я» и циничным эссе на «ты» — это текст без голоса. Голос выбирается
 * решением и записывается в карточку отдельной строкой.
 */

require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

/**
 * Голоса. Профиль задаёт форму и сигналы, но голос — отдельное решение: у
 * четырёх вариантов одна числовая цель и разное авторство, чтобы проверить,
 * держатся ли сигналы независимо от жанра.
 */
const VOICES = [
    'praktik' => [
        'Автор-практик от «я»',
        ['- Пишет **автор-практик от «я»**: сам заводил аккаунт, сам выводил деньги, сам попадал впросак.',
         '- Манера трезвая, без рекламы: где обычный текст обещает, этот объясняет механику и говорит, где игрок теряет.',
         '- К читателю на «вы», но редко — вместо обращения вывод из собственного опыта.'],
    ],
    'obzor' => [
        'Обозреватель-испытатель, безлично',
        ['- Пишет **сторонний обозреватель**, безлично: «проверка показала», «в тестовом заходе», «по открытым данным».',
         '- Ни «я», ни «мы»: субъекта нет вовсе, есть наблюдение и вывод из него.',
         '- Тон ровный, аналитический; оценка выводится из фактов, а не заявляется.'],
    ],
    'esse' => [
        'Циничное эссе на «ты»',
        ['- Пишет **эссеист на «ты»**: разговор с читателем как с приятелем, который сейчас потеряет деньги.',
         '- Каждый раздел держится на своей развёрнутой метафоре, сквозные рефрены повторяются по тексту.',
         '- Никакой рекламы: жанр антипродающий, ирония вместо обещаний.'],
    ],
    'support' => [
        'Отчёт службы поддержки на «мы»',
        ['- Пишет **служба поддержки от корпоративного «мы»**: «мы принимаем заявки», «мы проверяем документы».',
         '- Ни «я», ни личных историй: говорит организация, а не человек.',
         '- Тон служебный и спокойный; там, где правила невыгодны игроку, они названы прямо, без смягчения.'],
    ],
];

$OUT   = $argv[1] ?? '/tmp/cards-custom';
$A     = $argv[2] ?? (__DIR__ . '/../samples/dorgen-reference/set199');
$B     = $argv[3] ?? (__DIR__ . '/../samples/dorgen-reference/set240');
$WA    = (float) ($argv[4] ?? 0.5);
$VOICE = $argv[5] ?? 'praktik';
if (!isset(VOICES[$VOICE])) { fwrite(STDERR, "голос '$VOICE' неизвестен: " . implode(', ', array_keys(VOICES)) . "\n"); exit(1); }
@mkdir($OUT, 0777, true);

/**
 * Сигналы. Числа — середина коридора удачных наборов, а не его край: первый
 * кастом целился в край и ушёл за него (14 цифр против 31–73 у образцов,
 * 100 минусов против 45–76), то есть стал строже собственного образца.
 */
const SIGNAL = [
    'facts_per10k'  => 45,    // 199 → 46, 240 → 31, донор 2 → 73
    'cta_per10k'    => 0,     // у всех трёх около нуля
    'minus_per10k'  => 65,    // 199 → 63, 240 → 76, донор 2 → 45
    'h3_per_h2'     => 3.3,   // 199 → 3.6, 240 → 3.3, донор 2 → 2.5
    'h2_quest_pct'  => 0,
    'h2_words'      => 9,
    'h2_colon_pct'  => 85,
    'brand_per10k'  => 70,    // 199 → 55, 240 → 70, донор 2 → 108
];

function measurePage(Analyzer $an, string $file): array
{
    $raw  = NicheLexicon::unplaceholder((string) file_get_contents($file));
    $r    = $an->run([['name' => 'p', 'url' => '/p', 'html' => $raw, 'keyword' => '', 'lsi' => []]]);
    $m    = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];
    $flat = trim(preg_replace('~\s+~u', ' ', strip_tags($raw)));
    $wc   = max(1, count(preg_split('~\s+~u', $flat, -1, PREG_SPLIT_NO_EMPTY)));

    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $ps = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
    $wp = 0;
    foreach ($ps as $x) { $wp += count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)); }

    $prose = NicheLexicon::prose($raw);
    return [
        'words'      => $wc,
        'h2'         => (int) $m['h2_count'],
        'sections'   => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)),
        'lists'      => (int) $m['list_count'],
        'strong'     => (int) $m['strong_count'],
        'faq'        => (int) $s['faq_questions'],
        'emoji'      => (int) $s['emoji'],
        'paragraphs' => count($ps),
        'wpp'        => $ps ? round($wp / count($ps), 1) : 0,
        'adj'        => round((float) $s['adj_pct'], 1),
        'nausea'     => round((float) $m['nausea_academic'], 1),
        'water'      => round((float) $m['water_percent'], 1),
        'imper'      => (int) $s['imperatives'],
        'terms'      => NicheLexicon::termCounts($prose),
        'terms_total'=> NicheLexicon::termsTotal($prose),
    ];
}

function blend(array $a, array $b, float $wa): array
{
    $out = [];
    foreach ($a as $k => $v) {
        if ($k === 'terms') {
            $t = [];
            foreach (array_unique(array_merge(array_keys($v), array_keys($b[$k] ?? []))) as $lab) {
                $t[$lab] = (int) round($wa * ($v[$lab] ?? 0) + (1 - $wa) * (($b[$k][$lab] ?? 0)));
            }
            arsort($t);
            $out[$k] = array_filter($t);
            continue;
        }
        $bv = $b[$k] ?? $v;
        $out[$k] = is_float($v) || is_float($bv)
            ? round($wa * $v + (1 - $wa) * $bv, 1)
            : (int) round($wa * $v + (1 - $wa) * $bv);
    }
    return $out;
}

$an = new Analyzer();
$pages = [];
foreach (glob("$A/*.html") as $f) { $pages[basename($f, '.html')]['a'] = $f; }
foreach (glob("$B/*.html") as $f) { $pages[basename($f, '.html')]['b'] = $f; }

$made = 0;
$targets = [];   // те же цели машиночитаемо — по ним меряет check-custom.php
foreach ($pages as $type => $src) {
    if (!isset($src['a'], $src['b'])) { continue; }
    $mix = blend(measurePage($an, $src['a']), measurePage($an, $src['b']), $WA);

    $facts  = (int) round($mix['words'] / 10000 * SIGNAL['facts_per10k']);
    $minus  = (int) round($mix['words'] / 10000 * SIGNAL['minus_per10k']);
    $brand  = (int) round($mix['words'] / 10000 * SIGNAL['brand_per10k']);
    $h3     = (int) round($mix['h2'] * SIGNAL['h3_per_h2']);

    $L = [];
    $L[] = "# Карточка стиля для {$type}.html — КАСТОМНЫЙ профиль";
    $L[] = '';
    $L[] = 'Это не клон одного образца. Числовая форма собрана из двух удачных наборов,';
    $L[] = 'а четыре сигнала выставлены по тому, что у удачных наборов оказалось общим.';
    $L[] = 'Эти числа ПЕРЕКРЫВАЮТ соответствующие строки промпта.';
    $L[] = '';
    $L[] = '## Голос — решение, а не смесь: ' . VOICES[$VOICE][0];
    foreach (VOICES[$VOICE][1] as $line) { $L[] = $line; }
    $L[] = '';
    $L[] = '## Форма (смесь двух образцов)';
    $L[] = "- Объём: **~{$mix['words']} слов** (±10%).";
    $L[] = "- Абзацев: **~{$mix['paragraphs']}**, в среднем по **~{$mix['wpp']} слов**.";
    $L[] = "- H2 — **{$mix['h2']}**, подзаголовков H3 — **~{$h3}** (это ~" . SIGNAL['h3_per_h2'] . " на каждый H2).";
    $L[] = "- Списков **~{$mix['lists']}**, strong **~{$mix['strong']}**, эмодзи **~{$mix['emoji']}**, вопросительных знаков **~{$mix['faq']}**.";
    $L[] = "- Прилагательных **~{$mix['adj']}%**, тошнота **~{$mix['nausea']}%**, водность **~{$mix['water']}%**, императивов **~{$mix['imper']}**.";
    $L[] = "- Бренд: **~{$brand}** вставок плейсхолдерами (кириллица и латиница вместе), из них заметная часть — в заголовках.";
    $L[] = '';
    $L[] = '## Четыре сигнала — главное в этом профиле';
    // Цель ДВУСТОРОННЯЯ: первый кастом получил «не больше N» и ушёл вдвое ниже
    // образцов — то есть стал строже того, что мы воспроизводим.
    $L[] = "- **Голых чисел с единицами — около {$facts}** (коридор " . (int) round($facts * 0.75) . "–" . (int) round($facts * 1.25) . "): «500 ₽», «96%», «за 15 минут». Цифра живёт внутри объяснения, а не строкой спецификации. Ниже коридора уходить НЕЛЬЗЯ: у образцов цифры есть, просто они не сбиты в сводку.";
    $L[] = '- **Прямых призывов — ноль.** Ни «жми», ни «забери», ни «играй», ни «скачай», ни «успей». Страница объясняет, а не продаёт.';
    $L[] = "- **Мест, где прямо назван минус или риск, — около {$minus}** (коридор " . (int) round($minus * 0.75) . "–" . (int) round($minus * 1.25) . "): «минус», «ловушка», «не стоит», «проиграть», «потерять», «осторожно». Это сквозной приём, но и перебор вреден: текст не должен отговаривать от площадки, он должен быть трезвым.";
    $L[] = "- **Заголовок — длинный, ~" . SIGNAL['h2_words'] . " слов, в " . SIGNAL['h2_colon_pct'] . "% случаев с двоеточием или тире**: слева запрос, справа обещание угла. Вопросительных заголовков — **ноль**.";
    $L[] = '';
    $L[] = '## Словарь: состав профильных терминов';
    $tt = [];
    foreach (array_slice($mix['terms'], 0, 14, true) as $lab => $c) { $tt[] = "{$lab} — ~{$c}"; }
    $L[] = '- ' . implode('; ', $tt) . '.';
    $L[] = "- Всего профильных терминов на странице: **~{$mix['terms_total']}**.";
    $L[] = '';
    $L[] = '## Из промпта — без изменений';
    $L[] = '- Состав разделов, фактура, перелинковка, разрешённые и запрещённые категории сущностей.';

    $targets[$type] = [
        'words' => $mix['words'], 'h2' => $mix['h2'], 'sections' => $mix['h2'] + $h3,
        'lists' => $mix['lists'], 'strong' => $mix['strong'], 'faq' => $mix['faq'],
        'emoji' => $mix['emoji'], 'paragraphs' => $mix['paragraphs'], 'words_per_para' => $mix['wpp'],
        'adj_pct' => $mix['adj'], 'nausea_acad' => $mix['nausea'], 'water' => $mix['water'],
        'imperatives' => $mix['imper'], 'terms_total' => $mix['terms_total'], 'terms' => $mix['terms'],
        'brand_total' => $brand, 'facts_max' => $facts, 'minus_min' => $minus,
        'h3_per_h2' => SIGNAL['h3_per_h2'], 'h2_words' => SIGNAL['h2_words'],
        'h2_quest_pct' => SIGNAL['h2_quest_pct'], 'cta' => SIGNAL['cta_per10k'],
        'voice' => VOICES[$VOICE][0],
    ];
    file_put_contents("$OUT/style-{$type}.md", implode("\n", $L) . "\n");
    printf("%-14s слов %5d, абзацев %3d, H2 %2d, цифр ≤%3d, минусов ≥%3d, бренд ~%3d\n",
        $type, $mix['words'], $mix['paragraphs'], $mix['h2'], $facts, $minus, $brand);
    $made++;
}
file_put_contents("$OUT/targets.json", json_encode($targets, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
echo "→ $OUT\nSTATUS " . json_encode(['cards' => $made]) . "\n";

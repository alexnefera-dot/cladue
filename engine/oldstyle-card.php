<?php
declare(strict_types=1);
/**
 * Карточка стиля образца: постранично снимаем то, чем он отличается от
 * донорского профиля, и пишем markdown-карточку рядом с промптом. Движок не
 * трогаем — карточка просто перекрывает часть целей промпта для реалайзера.
 *
 *   php oldstyle-card.php <папка-со-старым-набором> <куда-положить-карточки>
 */
require_once __DIR__ . '/src/Analyzer.php';
require_once __DIR__ . '/src/NicheLexicon.php';

$SRC = $argv[1] ?? '/tmp/old-bez-zachina/svyazka3';
$OUT = $argv[2] ?? '/tmp/oldstyle-cards';
@mkdir($OUT, 0777, true);

$a = new Analyzer();
foreach (glob("$SRC/*.html") as $f) {
    $t = pathinfo($f, PATHINFO_FILENAME);
    $raw = (string) file_get_contents($f);
    $norm = NicheLexicon::unplaceholder($raw);
    $r = $a->run([['name' => $t, 'url' => "/$t", 'html' => $norm, 'keyword' => '', 'lsi' => []]]);
    $m = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];

    preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
    $ps = array_values(array_filter(
        array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
        fn($x) => mb_strlen($x) > 40
    ));
    $wp = 0;
    foreach ($ps as $x) { $wp += count(preg_split('~\s+~u', NicheLexicon::unplaceholder($x), -1, PREG_SPLIT_NO_EMPTY)); }

    $prose  = NicheLexicon::prose($norm);
    $terms  = NicheLexicon::termCounts($prose);
    arsort($terms);
    $top    = array_slice($terms, 0, 14, true);
    $ld     = preg_match_all('~ld\+json~i', $raw);

    // Начало страницы: старый набор открывается списком-паспортом, а не абзацем
    $opensWithList = (bool) preg_match('~^\s*<ul~i', $raw);
    $firstBlock = mb_substr(trim(preg_replace('~\s+~u', ' ', strip_tags(mb_substr($raw, 0, 700)))), 0, 260);

    $L = [];
    $L[] = "# Карточка стиля для {$t}.html — цель НЕ донор, а образец";
    $L[] = '';
    $L[] = 'Эти числа ПЕРЕКРЫВАЮТ соответствующие строки промпта. Всё остальное в промпте';
    $L[] = '(структура разделов, фактура, перелинковка, запрещённые сущности) остаётся в силе.';
    $L[] = '';
    $L[] = '## Что берём от образца';
    $L[] = "- Объём: **~{$m['words_total']} слов** (±10%).";
    // Ритм описываем по замеру, а не утверждением: у одного образца абзац в две
    // фразы, у другого — на пятьдесят слов, и подсказка «дроби мельче» во втором
    // случае уводила бы от цели.
    $avg = $ps ? round($wp / count($ps), 1) : 0;
    $rhythm = $avg < 24
        ? 'Ритм ДРОБНЫЙ: абзац в две-три фразы, а не развёрнутая мысль.'
        : ($avg > 40
            ? 'Ритм КРУПНЫЙ: абзац — развёрнутая мысль на несколько предложений, с пояснением и связкой. Не руби его на строки.'
            : 'Ритм средний: абзац в три-четыре фразы.');
    $L[] = "- Абзацев: **~" . count($ps) . "**, в среднем по **~{$avg} слов**. {$rhythm}";
    $L[] = "- H2 **{$m['h2_count']}**, разделов H2+H3 **" . ($m['h2_count'] + ($m['h3_count'] ?? 0)) . "**, списков **{$m['list_count']}**, strong **{$m['strong_count']}**.";
    $L[] = "- Эмодзи **{$s['emoji']}**, вопросительных знаков **{$s['faq_questions']}**, цифр на 100 слов **" . round((float) $s['numbers_per_100w'], 1) . "**.";
    $L[] = "- Прилагательных **" . round((float) $s['adj_pct'], 1) . "%**, водность **" . round((float) $m['water_percent'], 1) . "%**, тошнота **" . round((float) $m['nausea_academic'], 1) . "%**.";
    $L[] = "- «я» **{$s['first_person']}**, «вы» **{$s['second_person']}**, императивов **{$s['imperatives']}**.";
    $L[] = "- Бренд: кириллицей **" . substr_count($raw, '%brand_name_ru%') . "**, латиницей **" . substr_count($raw, '%brand_name_en%') . "**.";
    $L[] = "- Названий игр в прозе **" . NicheLexicon::countGames($prose) . "**, названий студий **" . NicheLexicon::countProviders($prose) . "**. В этом стиле их НАЗЫВАЮТ прямо в тексте.";
    $L[] = "- Блоков JSON-LD в конце страницы: **{$ld}** (как в образце; тип схемы бери тот же, что стоит в образце).";
    $L[] = $opensWithList
        ? "- НАЧАЛО СТРАНИЦЫ: список-паспорт `<ul>` с фактами (год, каталог, отдача, лицензия) ДО первого заголовка — именно так открывается старый набор."
        : "- НАЧАЛО СТРАНИЦЫ: сразу заголовок H2, без списка-паспорта.";
    $L[] = "  Первые строки образца для примера ритма: «{$firstBlock}…»";
    $L[] = '';
    $L[] = '## Словарь: как говорит старый набор';
    $tt = [];
    foreach ($top as $lab => $c) { $tt[] = "{$lab} — ~{$c}"; }
    $L[] = '- Профильные термины и их счёт в прозе: ' . implode('; ', $tt) . '.';
    $L[] = '- Держи ИМЕННО этот состав слов: где у образца «отдача», не пиши «RTP», и наоборот. Счёт выше — это и есть словарь образца.';
    $L[] = "- Всего профильных терминов на странице: **~" . array_sum($terms) . "**.";
    $L[] = '';
    $L[] = '## Что берём из промпта без изменений';
    $L[] = '- Ссылки: ровно те анкоры, пути и их количество, что в блоке перелинковки промпта.';
    $L[] = '- Состав разделов, фактура, разрешённые и запрещённые категории сущностей, плейсхолдеры бренда.';

    file_put_contents("$OUT/style-{$t}.md", implode("\n", $L) . "\n");
    printf("%-14s абзацев %3d по %4.1f слов, терминов %3d, игр %2d, студий %2d\n",
        $t, count($ps), $ps ? $wp / count($ps) : 0, array_sum($terms),
        NicheLexicon::countGames($prose), NicheLexicon::countProviders($prose));
}
echo "→ $OUT\n";

<?php
declare(strict_types=1);

/**
 * Строит ДВА профиля корпуса v3 из data-v3/donors.json:
 *
 *   data-v3/profile-single.json  — одностраничники (6 доноров, один тип «main»)
 *   data-v3/profile-bundle.json  — связка (12 типов страниц)
 *
 * Разводятся они потому, что это разные продукты: из 21 параметра шесть имеют
 * НЕПЕРЕСЕКАЮЩИЕСЯ коридоры (объём, таблицы, «вы», императивы, внутренние
 * ссылки, вставки бренда). Общий профиль усреднил бы их в несуществующую
 * середину. Остальные пятнадцать совпадают — поэтому движок остаётся один,
 * разными будут только планировщик и профиль.
 *
 *   php build-profile-v3.php
 *
 * Структурные поля (веса блоков, пулы секций, семантика) берутся из базового
 * data/profile.json — Planner ожидает их наличия.
 */

$DIR    = __DIR__ . '/data-v3';
$donors = json_decode((string) file_get_contents("$DIR/donors.json"), true)['sites'] ?? [];
$base   = json_decode((string) file_get_contents(__DIR__ . '/data/profile.json'), true);
if (!$donors) { fwrite(STDERR, "нет data-v3/donors.json\n"); exit(1); }

/** ключ профиля → ключ в замере страницы */
$MAP = [
    'words' => 'words', 'h2' => 'h2', 'sections' => 'sections', 'lists' => 'lists',
    'tables' => 'tables', 'quotes' => 'quotes', 'strong' => 'strong', 'faq' => 'faq',
    'nausea_acad' => 'nausea_acad', 'water' => 'water', 'numbers_per100' => 'numbers_per100',
    'adj_pct' => 'adj_pct', 'first_person' => 'first_person', 'vy' => 'vy',
    'imperatives' => 'imperatives', 'emoji_body' => 'emoji', 'entities' => 'entities',
    'we' => 'we', 'names' => 'names', 'head_brand_pct' => 'head_brand_pct',
    'paragraphs' => 'paragraphs', 'words_per_para' => 'words_per_para',
    'providers_named' => 'providers_named', 'games_named' => 'games_named',
    'brand_ru' => 'brand_ru', 'brand_en' => 'brand_en',
];

function corridor(array $v): array
{
    if (!$v) { return [0, 0, 0]; }
    sort($v);
    $at = fn(float $q) => $v[max(0, min(count($v) - 1, (int) round($q * (count($v) - 1))))];
    return [round((float) $at(0.10), 1), round((float) $at(0.50), 1), round((float) $at(0.90), 1)];
}

/** заполняет тип профиля коридорами по набору страниц + структурой из базы */
function buildType(array $pages, array $baseType, array $MAP): array
{
    $t = $baseType;
    foreach ($MAP as $pk => $dk) {
        $vals = [];
        foreach ($pages as $p) { if (isset($p[$dk])) { $vals[] = $p[$dk]; } }
        if ($vals) { $t[$pk] = corridor($vals); }
    }
    // доля страниц с обращением/первым лицом — Planner берёт их как вероятности
    $n = max(1, count($pages));
    $t['p_vy'] = round(count(array_filter($pages, fn($p) => ($p['vy'] ?? 0) >= 3)) / $n, 2);
    $t['p_first_person'] = round(count(array_filter($pages, fn($p) => ($p['first_person'] ?? 0) >= 3)) / $n, 2);
    // семантика — медиана плотности кластера по этим страницам
    $sem = [];
    foreach ($pages as $p) { foreach (($p['sem'] ?? []) as $ck => $cv) { $sem[$ck][] = $cv; } }
    foreach ($sem as $ck => $vals) { $t['sem_clusters'][$ck] = corridor($vals)[1]; }
    return $t;
}

// ── одностраничники ────────────────────────────────────────────────────────
$singlePages = [];
foreach ($donors as $n => $s) {
    if (!empty($s['shape']['single'])) { $singlePages[] = reset($s['pages']); }
}
$single = $base;
$single['_meta'] = [
    'source'  => 'data-v3/donors.json — одностраничники',
    'donors'  => count($singlePages),
    'note'    => 'Один тип страницы. Перелинковки нет вовсе: у всех доноров внутренних ссылок ноль, поэтому цели по ссылкам к этому профилю неприменимы.',
];
$single['types'] = ['main' => buildType($singlePages, $base['types']['main'], $MAP)];
$single['types']['main']['intlinks'] = [0, 0, 0];
// Реестр страниц: одна страница несёт весь сайт, поэтому ей разрешены ВСЕ
// категории сущностей — сужать нечем и не для кого.
$single['pages'] = ['main' => [
    'path'         => '/',
    'entity_cats'  => ['providers_count','payout_rate','licenses','crypto','payments','jackpot','currencies','platforms'],
    'emoji'        => true,
    'author_block' => true,
    'role'         => 'standalone',
]];

// ── связка ─────────────────────────────────────────────────────────────────
$bundleName = null;
foreach ($donors as $n => $s) { if (empty($s['shape']['single'])) { $bundleName = $n; break; } }
$bundle = $base;
$bundle['types'] = [];
if ($bundleName !== null) {
    $b = $donors[$bundleName];
    foreach ($b['pages'] as $t => $p) {
        // База даёт структурные поля; для типов, которых в старом корпусе не
        // было (obzor, promo, news, info, partnery), берём каркас от main.
        $baseType = $base['types'][$t] ?? $base['types']['main'];
        $bundle['types'][$t] = buildType([$p], $baseType, $MAP);
        $bundle['types'][$t]['intlinks'] = [$p['intlinks'], $p['intlinks'], $p['intlinks']];
    }
    // Реестр страниц связки. Пути — реальные слаги сайта (у регистрации он
    // короче имени файла). Категории сущностей — по теме страницы; чтение
    // показало, что шесть новых типов это та же рамка с другим словарём,
    // поэтому категории им назначаются по той же логике, что привычным.
    $CATS = [
        'main'        => ['providers_count','payout_rate','licenses','crypto','payments','jackpot','currencies','platforms'],
        'obzor'       => ['providers_count','payout_rate','licenses','payments','jackpot'],
        'slots'       => ['providers_count','payout_rate','jackpot'],
        'bonus'       => ['licenses'],
        'promo'       => ['licenses'],
        'registracia' => ['licenses'],
        'vhod'        => [],
        'zerkalo'     => ['licenses'],
        'app'         => ['platforms'],
        'news'        => ['providers_count','jackpot'],
        'info'        => ['licenses','payments'],
        'partnery'    => ['payments','currencies'],
    ];
    // Пути ГЕНЕРАЦИИ обязаны совпадать с именами наших страниц. У сайта-донора
    // регистрация лежит на /registr, и раньше этот слаг попадал в ссылки — сто
    // с лишним битых href на набор, потому что файл называется registracia.html.
    // Короткий слаг донора нужен только при ЧТЕНИИ его графа (карта синонимов
    // в extract-donors-v3.php и analyze-v3.php), в генерацию он не идёт.
    $PATHS = [];
    $bundle['pages'] = [];
    foreach ($b['pages'] as $t => $p) {
        $bundle['pages'][$t] = [
            'path'         => $PATHS[$t] ?? ($t === 'main' ? '/' : "/$t"),
            'entity_cats'  => $CATS[$t] ?? ['licenses'],
            // Эмодзи есть на КАЖДОЙ странице связки (34–75), а не только на
            // главной, как было в корпусах v1/v2.
            'emoji'        => ($p['emoji'] ?? 0) > 0,
            // Авторского блока нет нигде: формальный детектор давал ложные
            // срабатывания на сюжетные слова и на скрытые JSON-LD болванки.
            'author_block' => false,
            'role'         => $t === 'main' ? 'hub' : 'leaf',
        ];
    }

    $allPages = array_values($b['pages']);
    $bundle['_meta'] = [
        'source' => 'data-v3/donors.json — связка ' . $bundleName,
        'donors' => 1,
        'pages'  => count($b['pages']),
        'note'   => 'ДОНОР ОДИН. Коридор каждого типа — это одно значение одной страницы, а не разброс между сайтами; коридор по набору целиком дан в set_corridor и отражает разброс ВНУТРИ сайта. Пока не добавлены другие связки, генератор по этому профилю клонирует один шаблон.',
        'set_corridor' => array_map(
            fn($dk) => corridor(array_map(fn($p) => $p[$dk] ?? 0, $allPages)),
            $MAP
        ),
        'link_graph' => 'полная сетка: каждая страница ссылается на все остальные, ' . corridor(array_map(fn($p) => $p['intlinks'] ?? 0, $allPages))[1] . ' ссылок на страницу',
    ];
}

file_put_contents("$DIR/profile-single.json", json_encode($single, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
file_put_contents("$DIR/profile-bundle.json", json_encode($bundle, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

// ── два каталога корпуса ───────────────────────────────────────────────────
// Движок понимает корпус как каталог с profile.json, donors.json и pools/.
// Значит «два генератора» — это два каталога, а не два движка: generate.php
// работает с ними без единой новой строки.
$mk = function (string $dir, array $profile, array $sites) {
    @mkdir("$dir/pools", 0777, true);
    file_put_contents("$dir/profile.json", json_encode($profile, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    file_put_contents("$dir/donors.json", json_encode(['sites' => $sites], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    // Пулы (секции, заголовки, анкоры) пока общие с корпусом v2 — своих у v3
    // нет, а Planner без них не соберётся.
    $pools = json_decode((string) file_get_contents(__DIR__ . '/data-dorgen/pools/pools.json'), true);
    // А вот веса перелинковки переписываем под состав корпуса. У v2 они
    // описывают звезду из семи страниц; связка v3 — полная сетка из
    // двенадцати, где каждая страница ссылается на все остальные. Со старыми
    // весами пять новых типов не были бы целью ни разу.
    // Инвариант «0 чужих брендов» пришёл из корпусов v1/v2 и для v3 неверен:
    // референс связки называет провайдеров и слоты свободно — 25 и 58 упоминаний
    // на набор, тогда как генерация давала ноль и ноль. Реалайзеры честно
    // обобщали имена, потому что инвариант так велел. Запрещены только чужие
    // казино-операторы, а не студии и тайтлы.
    $inv = $pools['style']['invariants'] ?? [];
    foreach ($inv as $i => $v) {
        if (mb_stripos($v, 'чужих брендов') !== false) {
            $inv[$i] = 'названия игр, студий-провайдеров, платёжных систем и лицензиаров — НУЖНЫ, они часть фактуры; запрещены только имена чужих казино-операторов';
        }
    }
    $pools['style']['invariants'] = $inv;

    $types = array_keys($profile['types'] ?? []);
    if (count($types) > 1) {
        $pools['interlinking']['target_weights'] = array_fill_keys($types, 1);
        $pools['interlinking']['_note'] = 'Полная сетка: равные веса по всем ' . count($types)
            . ' страницам, число ссылок берётся из донора постранично.';
    }
    file_put_contents("$dir/pools/pools.json", json_encode($pools, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
};

// Профиль, снятый чтением, кладём в style — оттуда его берут Planner и
// PromptBuilder. Без этого генератор видит донора «нейтрально-справочным»
// вместо, скажем, лабораторного протокола замера.
$withStyle = function (array $sites): array {
    foreach ($sites as $n => &$s) {
        $r = $s['read'] ?? [];
        $s['style']['genre']        = $r['genre'] ?? null;
        $s['style']['voice']        = $r['voice'] ?? null;
        $s['style']['register_read'] = $r['register'] ?? null;
        $s['style']['author_block'] = !empty($r['author_block']);
        $s['style']['devices']      = $r['devices'] ?? [];
        $s['style']['numbers_note'] = $r['numbers'] ?? null;
        $s['style']['avoid']        = $r['no'] ?? [];
        if (!empty($r['emoji_placement'])) { $s['style']['emoji_placement'] = $r['emoji_placement']; }
        if (!empty($r['frame'])) { $s['style']['frame'] = $r['frame']; }
        if (!empty($r['block'])) { $s['style']['block_formula'] = $r['block']; }
    }
    unset($s);
    return $sites;
};

$singleSites = $withStyle(array_filter($donors, fn($s) => !empty($s['shape']['single'])));
$bundleSites = $withStyle(array_filter($donors, fn($s) => empty($s['shape']['single'])));
$mk(__DIR__ . '/data-v3-single', $single, $singleSites);
$mk(__DIR__ . '/data-v3-bundle', $bundle, $bundleSites);

fwrite(STDERR, "→ data-v3-single/  типов 1,  доноров " . count($singleSites) . "\n");
fwrite(STDERR, "→ data-v3-bundle/  типов " . count($bundle['types']) . ", доноров " . count($bundleSites) . "\n");
echo "STATUS " . json_encode(['single_donors' => count($singleSites), 'bundle_types' => count($bundle['types'])]) . "\n";

<?php
declare(strict_types=1);

/**
 * Снимает профили с корпуса v3 → data-v3/donors.json.
 *
 * Отличие от extract-donors.php (корпус v1/v2): там связка — ЖЁСТКО семь типов
 * страниц с известными именами. Здесь размер набора произвольный: в корпусе
 * есть одностраничники и связка на 13 страниц, причём шести типов (obzor, promo,
 * news, info, partnery, sitemap) движок раньше не видел. Поэтому:
 *   · состав набора и типы страниц ОТКРЫВАЮТСЯ из имён файлов, а не задаются списком;
 *   · внутренние ссылки считаются относительно СОБСТВЕННОГО состава набора;
 *   · бренд ищется в тексте (это реальные страницы, плейсхолдеров в них нет).
 *
 *   php extract-donors-v3.php <корень корпуса> [out.json]
 * Корень: <корень>/<набор>/<страница>.htm|html
 */

require_once __DIR__ . '/src/Analyzer.php';

/** Слаги в ссылках короче имён файлов: /registr → registracia.htm */
const LINK_ALIASES = ['registr' => 'registracia', 'index' => 'main', 'reg' => 'registracia',
                      'login' => 'vhod', 'mirror' => 'zerkalo', 'partner' => 'partnery'];

$ROOT = $argv[1] ?? '';
$OUT  = $argv[2] ?? (__DIR__ . '/data-v3/donors.json');
if ($ROOT === '' || !is_dir($ROOT)) {
    fwrite(STDERR, "usage: extract-donors-v3.php <корень корпуса> [out.json]\n");
    exit(1);
}

/** Тип страницы из имени файла. Длинное имя (сохранённая страница) → main. */
function pageType(string $file): string
{
    $stem = pathinfo($file, PATHINFO_FILENAME);
    $slug = mb_strtolower($stem);
    $known = ['main','index','vhod','zerkalo','registracia','bonus','slots','app',
              'obzor','promo','news','info','partnery','sitemap'];
    foreach ($known as $k) { if ($slug === $k) { return $k === 'index' ? 'main' : $k; } }
    return 'main';   // одностраничник: имя файла — заголовок страницы
}

/**
 * Бренд набора: кириллическое и латинское написание. Берём из <title> кандидатов
 * и оставляем те, что реально повторяются в теле — так отсекаются слова заголовка,
 * которые брендом не являются («казино», «официальный», «Casino»).
 */
function detectBrand(string $html, string $text): array
{
    $title = '';
    if (preg_match('~<title[^>]*>(.*?)</title>~is', $html, $m)) { $title = html_entity_decode($m[1]); }
    $stop = ['казино','онлайн','официальный','сайт','вход','зеркало','бонус','бонусы','обзор',
             'регистрация','игровые','автоматы','клуб','кабинет','личный','рабочее','промокод',
             'выплаты','вывод','кэшбэк','депозит','играть','live','casino','online','official'];
    $pick = function (string $one, string $pair) use ($title, $text, $stop): string {
        // Два независимых прохода: одиночные имена (в том числе слитно-составные —
        // КриптоБосс, CryptoBoss) и пары слов (Драгон Мани, Dragon Money). Одним
        // жадным выражением не обойтись: оно склеивает бренд с соседним словом
        // заголовка и обрубает составную часть.
        $cand = [];
        foreach ([$one, $pair] as $re) {
            if (!preg_match_all($re, $title, $mm)) { continue; }
            foreach ($mm[0] as $w) { $cand[$w] = true; }
        }
        if (!$cand) { return ''; }
        $hits = [];
        foreach (array_keys($cand) as $w) {
            $parts = preg_split('~\s+~u', mb_strtolower($w));
            if (array_intersect($parts, $stop)) { continue; }
            $n = mb_substr_count($text, $w);
            if ($n >= 3) { $hits[$w] = $n; }
        }
        if (!$hits) { return ''; }
        arsort($hits);
        $best = array_key_first($hits);
        // «Money» встречается чаще, чем «Dragon Money», просто потому что входит
        // в него. Если более длинный кандидат содержит победителя и почти не
        // уступает по частоте — бренд именно он.
        foreach ($hits as $w => $n) {
            if ($w !== $best && mb_strpos($w, $best) !== false && $n >= 0.6 * $hits[$best]) {
                $best = $w;
            }
        }
        return $best;
    };
    // Аббревиатуры из одних прописных (USDT, TON) под шаблоны не подходят
    // намеренно — иначе они перебивают настоящий бренд по частоте.
    return [
        'ru' => $pick('~[А-ЯЁ][а-яё]{2,}(?:[А-ЯЁ][а-яё]+)*~u',
                      '~[А-ЯЁ][а-яё]{2,}(?:[А-ЯЁ][а-яё]+)*\s[А-ЯЁ][а-яё]{2,}(?:[А-ЯЁ][а-яё]+)*~u'),
        'en' => $pick('~[A-Z][a-z]{2,}(?:[A-Z][a-z]+)*~u',
                      '~[A-Z][a-z]{2,}(?:[A-Z][a-z]+)*\s[A-Z][a-z]{2,}(?:[A-Z][a-z]+)*~u'),
    ];
}

$a = new Analyzer();
$sets = [];

foreach (glob($ROOT . '/*', GLOB_ONLYDIR) as $dir) {
    $name = basename($dir);
    if ($name === '__MACOSX') { continue; }
    $files = array_merge(glob("$dir/*.html") ?: [], glob("$dir/*.htm") ?: []);
    if (!$files) { continue; }

    // состав набора — сначала узнаём типы, потом считаем по ним ссылки
    $types = [];
    foreach ($files as $f) { $types[pageType($f)] = $f; }
    // Карта сайта — не контентная страница: 12 900 слов сплошными ссылками,
    // 0 заголовков, водность 0.1%, тошнота 99%. В профиле она бы перекосила
    // любой коридор, поэтому в состав набора не входит (ссылки на неё считаются).
    $linkable = $types;
    unset($types['sitemap']);

    $pages = []; $fp = []; $vy = []; $emoMain = 0; $brand = ['ru'=>'','en'=>''];
    foreach ($types as $t => $f) {
        $raw = (string) file_get_contents($f);
        $r = $a->run([['name'=>$t,'url'=>"/$t",'html'=>$raw,'keyword'=>'','lsi'=>[]]]);
        $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
        $txt = strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $raw));

        // Заголовки страниц набора неравноценны: на одной есть оба написания, на
        // другой только кириллица. Добираем недостающее написание по следующим,
        // а не фиксируем всё по первой попавшейся странице.
        if ($brand['ru'] === '' || $brand['en'] === '') {
            $d = detectBrand($raw, $txt);
            if ($brand['ru'] === '') { $brand['ru'] = $d['ru']; }
            if ($brand['en'] === '') { $brand['en'] = $d['en']; }
        }

        // ссылки на ДРУГИЕ страницы этого же набора — состав известен из файлов
        $intlinks = 0;
        if (preg_match_all('#<a[^>]+href="([^"]+)"#i', $raw, $hm)) {
            foreach ($hm[1] as $href) {
                // Ссылки абсолютные — разбираем именно path, иначе корень сайта
                // читается как имя файла и ссылки на главную теряются.
                $path = trim((string) parse_url(trim($href), PHP_URL_PATH), '/');
                $slug = $path === '' ? 'main' : mb_strtolower(basename($path));
                $slug = LINK_ALIASES[$slug] ?? $slug;
                if ($slug === $t) { continue; }
                if (isset($linkable[$slug])) { $intlinks++; }
            }
        }

        $wc  = max(1, (int) $m['words_total']);
        $low = mb_strtolower($txt);
        $sem = [];
        foreach (Intent::THEMES as $ck => $def) {
            $cc = 0;
            foreach ($def['triggers'] as $tr) { $cc += mb_substr_count($low, $tr); }
            $sem[$ck] = round($cc / $wc * 100, 1);
        }

        $pages[$t] = [
            'words'          => (int) $m['words_total'],
            'h2'             => (int) $m['h2_count'],
            'sections'       => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)),
            'lists'          => (int) $m['list_count'],
            'tables'         => (int) ($m['table_count'] ?? 0),
            'quotes'         => (int) ($m['quote_count'] ?? 0),
            'strong'         => (int) $m['strong_count'],
            'faq'            => (int) $s['faq_questions'],
            'numbers_per100' => round((float) $s['numbers_per_100w'], 1),
            'adj_pct'        => round((float) $s['adj_pct'], 1),
            'emoji'          => (int) $s['emoji'],
            'entities'       => (int) $s['entities_count'],
            'first_person'   => (int) $s['first_person'],
            'vy'             => (int) $s['second_person'],
            'imperatives'    => (int) $s['imperatives'],
            'nausea_acad'    => round((float) $m['nausea_academic'], 1),
            'water'          => round((float) $m['water_percent'], 1),
            'intlinks'       => $intlinks,
            'brand_ru'       => $brand['ru'] !== '' ? mb_substr_count($txt, $brand['ru']) : 0,
            'brand_en'       => $brand['en'] !== '' ? mb_substr_count($txt, $brand['en']) : 0,
            'sem'            => $sem,
        ];
        $fp[] = (int) $s['first_person'];
        $vy[] = (int) $s['second_person'];
        if ($t === 'main') { $emoMain = (int) $s['emoji']; }
    }

    $avg = fn(array $x) => $x ? array_sum($x) / count($x) : 0;
    $sets[$name] = [
        'pages' => $pages,
        'shape' => [
            'page_count' => count($pages),
            'types'      => array_keys($pages),
            'single'     => count($pages) === 1,
        ],
        'brand' => $brand,
        'style' => [
            'first_person' => $avg($fp) >= 10,
            'vy'           => $avg($vy) >= 3,
            'emoji_site'   => $emoMain >= 3,
            'fp_avg'       => round($avg($fp), 1),
            'vy_avg'       => round($avg($vy), 1),
        ],
    ];
    fwrite(STDERR, sprintf("  %-4s страниц %-3d бренд %s / %s\n",
        $name, count($pages), $brand['ru'] ?: '—', $brand['en'] ?: '—'));
}

@mkdir(dirname($OUT), 0777, true);
file_put_contents($OUT, json_encode(['sites' => $sets], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
fwrite(STDERR, "→ " . $OUT . "\n");
echo "STATUS " . json_encode(['sets' => count($sets)]) . "\n";

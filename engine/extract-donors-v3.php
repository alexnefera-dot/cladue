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

/**
 * Личные имена героев. Отдельный параметр, потому что ни один из прежних его не
 * ловит: у референса связки 105 имён на двенадцать страниц, у генерации выходило
 * 33 при полном совпадении по всем измеряемым полям. Приём жанра — микро-кейс с
 * НАЗВАННЫМ героем — терялся молча.
 */
const FIRST_NAMES = 'Александр|Алексей|Анатолий|Андрей|Антон|Артём|Артем|Артур|Борис|Вадим|Валентин|Валерий|Василий|Виктор|Виталий|Владимир|Владислав|Вячеслав|Геннадий|Георгий|Григорий|Данил|Даниил|Денис|Дмитрий|Евгений|Егор|Иван|Игорь|Илья|Кирилл|Константин|Леонид|Максим|Марат|Марк|Михаил|Никита|Николай|Олег|Павел|Пётр|Петр|Роман|Руслан|Сергей|Станислав|Степан|Тимур|Фёдор|Федор|Эдуард|Юрий|Ярослав|Алина|Алла|Анастасия|Анна|Валентина|Валерия|Вера|Вероника|Виктория|Галина|Дарья|Диана|Екатерина|Елена|Елизавета|Жанна|Инна|Ирина|Кристина|Ксения|Лариса|Любовь|Людмила|Марина|Мария|Надежда|Наталья|Оксана|Ольга|Полина|Светлана|София|Тамара|Татьяна|Юлия|Яна';

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
    $out = [
        'ru' => $pick('~[А-ЯЁ][а-яё]{2,}(?:[А-ЯЁ][а-яё]+)*~u',
                      '~[А-ЯЁ][а-яё]{2,}(?:[А-ЯЁ][а-яё]+)*\s[А-ЯЁ][а-яё]{2,}(?:[А-ЯЁ][а-яё]+)*~u'),
        'en' => $pick('~[A-Z][a-z]{2,}(?:[A-Z][a-z]+)*~u',
                      '~[A-Z][a-z]{2,}(?:[A-Z][a-z]+)*\s[A-Z][a-z]{2,}(?:[A-Z][a-z]+)*~u'),
    ];
    // Запасной проход для имён, не похожих на слово: «1ГО», «1GO», аббревиатуры
    // из прописных. Шаблоны выше их не ловят, а бренд бывает именно таким.
    if ($out['ru'] === '' || $out['en'] === '') {
        foreach (preg_split('~[^\p{L}\p{N}]+~u', $title, -1, PREG_SPLIT_NO_EMPTY) as $tok) {
            if (mb_strlen($tok) < 2 || in_array(mb_strtolower($tok), $stop, true)) { continue; }
            if (mb_substr_count($text, $tok) < 5) { continue; }
            $isRu = (bool) preg_match('~[А-ЯЁа-яё]~u', $tok);
            $key  = $isRu ? 'ru' : 'en';
            if ($out[$key] === '') { $out[$key] = $tok; }
        }
    }
    return $out;
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

    // Одна страница связки 7 принадлежит другому сайту (1GO вместо Пинап). Как
    // донор структуры и стиля она полноценна: бренд у нас переменная и всё равно
    // подменяется. Поэтому страница остаётся в профиле — просто её вставки
    // считаются по её собственному имени бренда (см. постраничный детект ниже).
    $foreign = [];
    $hostOf = [];
    foreach ($linkable as $t => $f) {
        if (preg_match_all('#href="(https?://[^/"]+)#i', (string) file_get_contents($f), $hm)) {
            $cnt = array_count_values($hm[1]);
            arsort($cnt);
            $hostOf[$t] = ['top' => array_key_first($cnt), 'n' => reset($cnt), 'all' => array_sum($cnt)];
        }
    }
    if (count($hostOf) > 2) {
        $tops = array_count_values(array_column($hostOf, 'top'));
        arsort($tops);
        $setHost = array_key_first($tops);
        foreach ($hostOf as $t => $h) {
            if ($h['top'] !== $setHost && $h['n'] >= 0.8 * $h['all']) { $foreign[] = $t; }
        }
    }

    $pages = []; $fp = []; $vy = []; $emoMain = 0; $brand = ['ru'=>'','en'=>''];
    foreach ($types as $t => $f) {
        $raw = (string) file_get_contents($f);
        $r = $a->run([['name'=>$t,'url'=>"/$t",'html'=>$raw,'keyword'=>'','lsi'=>[]]]);
        $p = $r['pages'][0]; $m = $p['metrics']; $s = $p['stylistics'];
        $txt = strip_tags(preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $raw));

        // Бренд ищем на КАЖДОЙ странице: в связке 7 одна страница принадлежит
        // другому сайту, и по имени набора её вставки считались бы нулями.
        // Найденное на странице имя главнее набора; недостающее написание
        // добираем по остальным страницам.
        $own = detectBrand($raw, $txt);
        if ($brand['ru'] === '') { $brand['ru'] = $own['ru']; }
        if ($brand['en'] === '') { $brand['en'] = $own['en']; }
        $pageBrand = ['ru' => $own['ru'] ?: $brand['ru'], 'en' => $own['en'] ?: $brand['en']];

        // Ссылки на другие страницы набора — но ТОЛЬКО ТЕКСТОВЫЕ, внутри абзацев.
        // Референсы — сохранённые страницы, и меню с подвалом дублируются на
        // каждой: из 1739 ссылок связки в прозе лежит 371, остальные 1368 —
        // навигация. Считая всё подряд, мы ставили генерации цель в четыре раза
        // выше реальной, и она набивала прозу ссылками.
        $prose = '';
        if (preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm)) { $prose = implode(' ', $pm[1]); }
        $intlinks = 0;
        if (preg_match_all('#<a[^>]+href="([^"]+)"#i', $prose, $hm)) {
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
            // Сами категории, а не только их число. Без списка промпт говорил
            // «не более трёх категорий», реалайзер брал лицензию, провайдеров и
            // RTP — а у референса горят крипта, поддержка и лимиты. Совпало
            // количество, не совпало ни одно имя.
            'entity_list'    => array_values($s['entities'] ?? []),
            'names'          => preg_match_all('~\b(' . FIRST_NAMES . ')\b~u', $txt),
            // Доля заголовков с именем бренда. Референсы держат её очень высоко
            // (у части доноров 90–100%), генерация давала 3–19%: ключ уходил из
            // заголовков в тело, и структура расходилась при совпадении цифр.
            'head_brand_pct' => (function () use ($raw, $pageBrand) {
                preg_match_all('~<h[23][^>]*>(.*?)</h[23]>~is', $raw, $hm);
                $hs = array_map(fn($x) => strip_tags($x), $hm[1]);
                if (!$hs) { return 0; }
                $n = 0;
                foreach ($hs as $h) {
                    if (($pageBrand['ru'] !== '' && mb_stripos($h, $pageBrand['ru']) !== false)
                        || ($pageBrand['en'] !== '' && stripos($h, $pageBrand['en']) !== false)) { $n++; }
                }
                return (int) round($n / count($hs) * 100);
            })(),
            'heading_samples' => (function () use ($raw) {
                preg_match_all('~<h[23][^>]*>(.*?)</h[23]>~is', $raw, $hm);
                $hs = array_values(array_filter(array_map(
                    fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $hm[1])));
                return array_slice($hs, 0, 8);
            })(),
            'first_person'   => (int) $s['first_person'],
            // Корпоративное «мы» — отдельная ось, которой в профиле v1/v2 не было:
            // там first_person считал только единственное число. В этом корпусе
            // набор 6 даёт «я» 0 при «мы» 45 — по старому полю он читается как
            // безличный, хотя написан от лица службы. Считаем здесь, а не в
            // src/Stylistics.php, чтобы не сдвинуть замеры корпуса v2.
            'we'             => preg_match_all('~\b(мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|наших|нашим|нашими)\b~u', mb_strtolower($txt)),
            'vy'             => (int) $s['second_person'],
            'imperatives'    => (int) $s['imperatives'],
            'nausea_acad'    => round((float) $m['nausea_academic'], 1),
            'water'          => round((float) $m['water_percent'], 1),
            'intlinks'       => $intlinks,
            'brand_ru'       => $pageBrand['ru'] !== '' ? mb_substr_count($txt, $pageBrand['ru']) : 0,
            'brand_en'       => $pageBrand['en'] !== '' ? mb_substr_count($txt, $pageBrand['en']) : 0,
            'brand_own'      => $pageBrand,
            'foreign'        => in_array($t, $foreign, true),
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

// Профиль, снятый ЧТЕНИЕМ, имеет приоритет над формальными признаками: в корпусе
// v2 классификатор ошибся на трёх донорах из девяти, а здесь формальный поиск
// авторского блока дал пять ложных срабатываний из пяти на связке 7.
$readFile = __DIR__ . '/data-v3/profile-read.json';
if (is_file($readFile)) {
    $read = json_decode((string) file_get_contents($readFile), true) ?: [];
    foreach ($sets as $n => &$s) {
        if (isset($read[$n])) { $s['read'] = $read[$n]; }
    }
    unset($s);
    fwrite(STDERR, "  профиль чтения подмешан для " . count(array_intersect(array_keys($sets), array_keys($read))) . " наборов\n");
}

@mkdir(dirname($OUT), 0777, true);
file_put_contents($OUT, json_encode(['sites' => $sets], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
fwrite(STDERR, "→ " . $OUT . "\n");
echo "STATUS " . json_encode(['sets' => count($sets)]) . "\n";

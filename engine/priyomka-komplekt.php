<?php
declare(strict_types=1);

/**
 * Приёмка семистраничного комплекта.
 *
 *   php engine/priyomka-komplekt.php <папка-комплекта> [--korpus=samples/v4-final] [--профиль=<файл>]
 *
 * priyomka-v4.php проверяет одну главную. Донорская единица — не страница, а
 * комплект из семи, и половина правил живёт МЕЖДУ страницами, а не внутри:
 *
 *   — первый H2 внутренней страницы это срез темы, и 216 срезов из 216 у
 *     доноров уникальны; внутри одного комплекта повтор недопустим тем более;
 *   — главная не переиспользует свои же формулировки: пересечение с каждой
 *     внутренней 0,18 % в среднем при максимуме 2,29;
 *   — /bonus не получает ни одной входящей ссылки ни у одного из 50 доноров;
 *   — проза почти не возвращает ссылку на главную: 0–11 %.
 *
 * У каждого типа страницы своя мерка: главная держит 24 поля из 55, внутренние
 * по 30–35 — они короче и однообразнее, и требовать от них главную нельзя.
 *
 * Отдельная проверка — СМЕЩЕНИЕ по отпущенным полям. Разброс у донора не даёт
 * права систематически сидеть ниже его медианы: у него значения гуляют вокруг
 * центра, а комплект, который по всем семи страницам лежит под ним, — это уже
 * не разброс, а смещение. Первый наш комплект так и прошёл: объём 75 % от
 * донорского, ссылки 38 %, и ни один шлюз этого не увидел, потому что words и
 * ссылки были записаны в «отпустить».
 *
 * Порог по параметрам — доля, а не «все до одного». Каждое поле по отдельности
 * держат 70–90 % доноров, но тридцать полей разом — это произведение
 * вероятностей, и его не берёт НИ ОДИН донорский комплект: медиана 90–94 %,
 * девятый дециль 96–97 %, ста процентов нет ни у кого. Порог 95 % ставит нас
 * выше девяти десятых корпуса и при этом остаётся достижимым.
 *
 * Код возврата 0 — комплект принят целиком.
 */

require_once __DIR__ . '/src/Flagi.php';
require_once __DIR__ . '/src/PageMetrics.php';
require_once __DIR__ . '/src/SeoMetrics.php';
require_once __DIR__ . '/src/Soglasovanie.php';

const PAGES_K = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
/** Доля удержанных полей, ниже которой страница не принимается. */
const PORog_POLEY = 95.0;

$dir = rtrim($argv[1] ?? '', '/');
$korpus = 'samples/v5-final';
$profilFile = __DIR__ . '/data-v5/profil-v5.json';
[$opts] = Flagi::razobrat($argv, 2, ['корпус', 'профиль']);
$korpus = $opts['корпус'] ?? $korpus;
$profilFile = $opts['профиль'] ?? $profilFile;
if ($dir === '' || !is_dir($dir)) {
    fwrite(STDERR, "usage: php engine/priyomka-komplekt.php <папка-комплекта> [--корпус=<путь>] [--профиль=<файл>]\n");
    exit(1);
}
$profil = is_file($profilFile) ? json_decode((string) file_get_contents($profilFile), true) : null;
if (!$profil) { fwrite(STDERR, "нет профиля $profilFile\n"); exit(1); }
if (!isset($profil['страницы'])) { fwrite(STDERR, "в профиле нет раздела «страницы»\n"); exit(1); }

function chist(string $h): string
{
    $h = preg_replace('~(?is)<(script|style)\b.*?</\1>~', ' ', $h);
    $h = preg_replace('~<[a-zA-Z/!][^>]*>~', ' ', (string) $h);
    return html_entity_decode((string) $h, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}
function slv(string $t): array
{
    preg_match_all('~[\p{L}\p{N}]+~u', $t, $m);
    return $m[0];
}
function zag(string $h, string $lvl): array
{
    preg_match_all('~(?is)<' . $lvl . '[^>]*>(.*?)</' . $lvl . '>~', $h, $m);
    $out = [];
    foreach ($m[1] as $x) {
        $t = trim(preg_replace('~\s+~u', ' ', chist($x)));
        if ($t !== '') { $out[] = $t; }
    }
    return $out;
}
function shingle(string $t, int $n = 6): array
{
    $t = mb_strtolower(preg_replace('~%[a-z_]+%~u', ' бренд ', $t));
    $w = slv($t);
    $s = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $s[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $s;
}
function peresech(array $a, array $b): float
{
    $min = min(count($a), count($b));
    return $min ? count(array_intersect_key($a, $b)) / $min * 100 : 0.0;
}
$pad = fn($v, $w, $l = false) => $l
    ? $v . str_repeat(' ', max(0, $w - mb_strlen((string) $v)))
    : str_repeat(' ', max(0, $w - mb_strlen((string) $v))) . $v;

// ── чтение комплекта ────────────────────────────────────────────────
$stranicy = [];
$net = [];
foreach (PAGES_K as $p) {
    $f = "$dir/$p.html";
    if (!is_file($f)) { $net[] = $p; continue; }
    $raw = (string) file_get_contents($f);
    $stranicy[$p] = preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', $raw);
}
if ($net) { fwrite(STDERR, 'нет страниц: ' . implode(', ', $net) . "\n"); exit(1); }

$provaly = [];
$a = new Analyzer();
$otchet = [];
// Поля с односторонним полом: ключ метрики → как назвать провал в итоге.
const POLY = [
    'terms_total'  => 'термины',
    'first_person' => 'лицо',
    'imperatives'  => 'повелительное',
    'vy'           => '«вы»',
    'honest'       => 'риск',
    'para_one_sent_pct' => 'абзац-фраза',
];
$poly = [];

// ── 1. каждая страница по своей мерке ───────────────────────────────
foreach (PAGES_K as $p) {
    $html = $stranicy[$p];
    $card = PageMetrics::measure($a, $p, $html, ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $ok = 0; $vsego = 0; $bad = [];
    foreach ($profil['страницы'][$p]['поля'] as $k => $pp) {
        if (!$pp['держат'] || !array_key_exists($k, $card)) { continue; }
        $vsego++;
        $pol = $pp['дробное'] ? 0.8 : 2.0;
        if (abs((float) $card[$k] - (float) $pp['цель']) <= max(0.25 * abs((float) $pp['цель']), $pol)) { $ok++; }
        else { $bad[] = $k . ' ' . $card[$k] . '→' . $pp['цель']; }
    }
    // Полы по рынку — односторонние проверки, и они нужны отдельно от
    // коридора. Разброс рынка по этим полям широкий, симметричный коридор
    // был бы враньём; но промах у нас всегда в одну сторону — вниз.
    //
    // Термины: у рынка медиана 55 на главной, у нас была 19.
    // Первое лицо: «я»-группа у рынка 16–22 на 1000 слов, у нас была 0,85.
    // Повелительное и «вы»: 0 против 13–19 и 0 против 6. Общий запрет на
    //   «прямой призыв» был написан против «ты»-форм (зарегистрируйся, жми),
    //   а вычистил заодно и вежливое «проверьте, откройте, сверьте», которым
    //   рынок пользуется свободно.
    // Места с риском: 0 против 6–12 у рынка на главной. Страница, которая не
    //   называет ни одного минуса, читается рекламой, а не разбором.
    // Абзац в одно предложение: у рынка это 38 % абзацев главной и 50–69 %
    //   внутренней, у нас 24–32 % везде. Рынок ставит каждую мысль отдельным
    //   абзацем, мы пакуем три-четыре коротких предложения в один блок.
    // Свои имена переменных: $ok и $pol заняты счётчиком коридора выше, и
    // общий цикл по полам их затирал — доля по полям падала до 1 из 25.
    foreach (POLY as $klyuch => $imya) {
        $polRynka = (float) ($profil['страницы'][$p]['поля'][$klyuch]['пол_рынка'] ?? 0);
        $nashe = (float) ($card[$klyuch] ?? 0);
        $polOk = $polRynka === 0.0 || $nashe >= $polRynka;
        $poly[$imya][$p] = [$nashe, $polRynka, $polOk];
        if (!$polOk) { $provaly[$imya] = 1; }
    }

    $dolya = $vsego ? $ok / $vsego * 100 : 100.0;
    $otchet[$p] = ['поля' => [$ok, $vsego], 'доля' => $dolya, 'промахи' => $bad];
    if ($dolya < PORog_POLEY) { $provaly["параметры:$p"] = 1; }
}

// ── 2. каркас внутренней страницы ───────────────────────────────────
$vnutr = [];
foreach (PAGES_K as $p) {
    if ($p === 'main') { continue; }
    $html = $stranicy[$p];
    $h2 = zag($html, 'h2');
    $h3 = zag($html, 'h3');
    $cit = preg_match_all('~(?i)<blockquote~', $html);
    $prov = [
        'H2 = 2' => count($h2) === 2,
        'последний H2 — FAQ' => $h2 && (bool) preg_match('~вопрос|faq|ответ~iu', end($h2)),
        'H3 2–10' => count($h3) >= 2 && count($h3) <= 10,
        'цитата 1–4' => $cit >= 1 && $cit <= 4,
    ];
    $vnutr[$p] = ['первый H2' => $h2[0] ?? '—', 'проверки' => $prov,
        'ок' => count(array_filter($prov)), 'всего' => count($prov)];
    if (count(array_filter($prov)) < count($prov)) { $provaly["каркас:$p"] = 1; }
}

// ── 3б. скелет главной: левые части H2 против корпуса ────────────────
//
// У пятидесяти конкурентских комплектов средний коэффициент Жаккара по левым
// частям H2 главной — 0,7–2,2 %, максимум по паре 40 %. У наших пяти он был
// 36,8 % в среднем и 81,8 % на худшей паре: восемь заголовков стояли у трёх
// комплектов и более. Потолок 25 % на пару оставляет место случайному
// совпадению одного-двух узлов и заворачивает общий скелет.
const POTOLOK_SKELETA = 25.0;
$levye = static function (string $html): array {
    $out = [];
    foreach (zag($html, 'h2') as $t) {
        $t = preg_replace('~%[a-z_]+%~u', ' ', $t);
        $l = preg_split('~\s*[:—–|]\s*~u', $t)[0] ?? $t;
        $l = trim(preg_replace('~\s+~u', ' ', mb_strtolower(preg_replace('~[^\p{L}\s]~u', ' ', $l))));
        if ($l !== '') { $out[$l] = 1; }
    }
    return $out;
};
$nashSkelet = $levye($stranicy['main']);

// ── 3а. хвосты внутренних: шесть закрытий обязаны быть разными ───────
//
// Разбор пятидесяти конкурентских комплектов дал ноль процентов пересечения
// между хвостами шести внутренних страниц одного сайта — у всех двадцати пяти
// сайтов выборки. У нас один и тот же абзац-концовка стоял в тридцати
// страницах из тридцати и давал основную долю пересечения между комплектами:
// до 4,35 % при пороге 3,5 %. Потолок в 12 % отделяет общий оборот жанра
// («ставка уменьшает счёт») от переписанного под копирку абзаца.
const POTOLOK_HVOSTOV = 12.0;
$hvosty = [];
foreach (PAGES_K as $hp) {
    if ($hp === 'main') { continue; }
    $hdo = explode('<details', $stranicy[$hp])[0];
    preg_match_all('~(?is)<p[^>]*>(.*?)</p>~', $hdo, $mh);
    $hvosty[$hp] = $mh[1] ? shingle(chist((string) end($mh[1])), 5) : [];
}
$hvostMax = 0.0; $hvostPara = '—';
$hk = array_keys($hvosty);
for ($hi = 0; $hi < count($hk); $hi++) {
    for ($hj = $hi + 1; $hj < count($hk); $hj++) {
        $ha = $hvosty[$hk[$hi]]; $hb = $hvosty[$hk[$hj]];
        if (min(count($ha), count($hb)) < 3) { continue; }
        $hv = peresech($ha, $hb);
        if ($hv > $hvostMax) { $hvostMax = $hv; $hvostPara = $hk[$hi] . '↔' . $hk[$hj]; }
    }
}
if ($hvostMax > POTOLOK_HVOSTOV) { $provaly['хвосты'] = 1; }

// ── 3. срезы тем: внутри комплекта и против корпуса ──────────────────
$srezy = [];
foreach ($vnutr as $p => $v) { $srezy[$p] = mb_strtolower($v['первый H2']); }
$dubliVnutri = count($srezy) - count(array_unique($srezy));

$root = dirname(__DIR__);
$put = is_dir($korpus) ? $korpus : $root . '/' . $korpus;
$sovpavshie = [];
$hudshayaPara = 0.0; $hudshiy = '—';
$skeletMax = 0.0; $skeletKto = '—';
$nashSh = [];
foreach (PAGES_K as $p) { $nashSh[$p] = shingle(chist($stranicy[$p])); }

foreach (glob(rtrim($put, '/') . '/*', GLOB_ONLYDIR) ?: [] as $other) {
    if (realpath($other) === realpath($dir)) { continue; }
    foreach (PAGES_K as $p) {
        $f = "$other/$p.html";
        if (!is_file($f)) { continue; }
        $oh = preg_replace('~<(?![a-zA-Z/!?])~', '&lt;', (string) file_get_contents($f));
        $v = peresech($nashSh[$p], shingle(chist($oh)));
        if ($v > $hudshayaPara) { $hudshayaPara = $v; $hudshiy = basename($other) . "/$p"; }
        if ($p === 'main' && $nashSkelet) {
            $chuzhSkelet = $levye($oh);
            $obshih = count(array_intersect_key($nashSkelet, $chuzhSkelet));
            $vsego = count($nashSkelet + $chuzhSkelet);
            $j = $vsego ? $obshih / $vsego * 100 : 0.0;
            if ($j > $skeletMax) { $skeletMax = $j; $skeletKto = basename($other); }
        }
        if ($p !== 'main') {
            $ih = zag($oh, 'h2');
            if ($ih && isset($srezy[$p]) && mb_strtolower($ih[0]) === $srezy[$p]) {
                $sovpavshie[] = basename($other) . "/$p";
            }
        }
    }
}
$porog = (float) ($profil['уникальность']['шинглы']['порог_pct'] ?? 6.0);
if ($dubliVnutri || $sovpavshie || $hudshayaPara >= $porog) { $provaly['уникальность'] = 1; }
if ($skeletMax > POTOLOK_SKELETA) { $provaly['скелет'] = 1; }

// ── 4. каннибализация внутри комплекта ──────────────────────────────
$mVn = []; $vnVn = [];
$imena = PAGES_K;
for ($i = 0; $i < count($imena); $i++) {
    for ($j = $i + 1; $j < count($imena); $j++) {
        $v = peresech($nashSh[$imena[$i]], $nashSh[$imena[$j]]);
        if ($imena[$i] === 'main') { $mVn[] = $v; } else { $vnVn[] = $v; }
    }
}
$kanMax = max(max($mVn), max($vnVn));
if ($kanMax > 3.0) { $provaly['каннибализация'] = 1; }

// ── 4в. шаблонность каркаса: один скелет на все внутренние ──────────
//
// Это нашёл читатель, а не счётчик. Гонясь за полями, комплект можно построить
// так, что все шесть внутренних страниц идут одним скелетом: «Определение: …»,
// «Порядок …», таблица, «Риски: …», «Итог: …». Каждое поле по отдельности в
// коридоре, а тридцать H3 набора начинаются с семи слов на всех.
//
// Считаем долю H3, чьё первое слово повторяется на другой странице комплекта.
// У 38 доноров это 25–52 % (медиана 38, максимум 85). Порог — 60 %: выше уже
// не разброс жанра, а один шаблон, размноженный шесть раз.
$roliSlova = [];
foreach (PAGES_K as $pp) {
    if ($pp === 'main') { continue; }
    foreach (zag($stranicy[$pp], 'h3') as $t) {
        $w = preg_split('~[^\p{L}]+~u', mb_strtolower($t), -1, PREG_SPLIT_NO_EMPTY);
        if ($w) { $roliSlova[] = $w[0]; }
    }
}
$shablon = 0.0;
if ($roliSlova) {
    $povtor = 0;
    foreach (array_count_values($roliSlova) as $n) { if ($n > 1) { $povtor += $n; } }
    $shablon = round($povtor / count($roliSlova) * 100, 1);
    if ($shablon > 60.0) { $provaly['шаблонность'] = 1; }
}

// ── 4б. смещение по отпущенным полям ────────────────────────────────
// Отпущенное поле обязано гулять ВОКРУГ донорской медианы. Считаем сумму по
// комплекту и сравниваем с суммой донорских медиан: ниже 85 % — смещение.
$smeshenie = [];
foreach (['words' => 'объём', 'terms_total' => 'профильных терминов'] as $pole => $imya) {
    $nashSum = 0; $ihSum = 0;
    foreach (PAGES_K as $p) {
        $c = PageMetrics::measure($a, $p, $stranicy[$p], ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
        $nashSum += (float) ($c[$pole] ?? 0);
        $ihSum += (float) ($profil['страницы'][$p]['поля'][$pole]['цель'] ?? 0);
    }
    $dolya = $ihSum ? $nashSum / $ihSum * 100 : 100;
    $smeshenie[$imya] = [round($nashSum) . ' из ' . round($ihSum), '≥85%', $dolya >= 85, round($dolya)];
}

// ── 4в. школа написания бренда ──────────────────────────────────────
// Корпус делится надвое: 36 сайтов пишут бренд латиницей (кириллица — редкое
// вкрапление, почти всегда на главной), 14 — только кириллицей. Комплект
// обязан держаться одной школы и попадать в её коридор постранично.
$brend = [];
$sумLat = 0; $sумCyr = 0;
$zamer = [];
foreach (PAGES_K as $p) {
    $c = PageMetrics::measure($a, $p, $stranicy[$p], ['ru' => '%brand_name_ru%', 'en' => '%brand_name_en%']);
    $zamer[$p] = ['лат' => (int) $c['brand_en'], 'кир' => (int) $c['brand_ru']];
    $sумLat += $zamer[$p]['лат']; $sумCyr += $zamer[$p]['кир'];
}
$shkola = $sумLat > 0 ? 'латиничная' : 'кириллическая';
$norma = $profil['бренд'][$shkola] ?? null;
$brend['школа'] = [$shkola, 'одна на комплект', true];
if ($norma) {
    foreach (PAGES_K as $p) {
        foreach (['лат', 'кир'] as $pismo) {
            $n = $norma['страницы'][$p][$pismo];
            $niz = (int) $n['низ']; $verh = (int) $n['верх'];
            // нижнюю границу не поднимаем выше нуля там, где у большинства доноров ноль
            $ok = $zamer[$p][$pismo] >= $niz && $zamer[$p][$pismo] <= max($verh, $niz);
            $brend[$p . ' · ' . $pismo] = [$zamer[$p][$pismo], $niz . '–' . $verh, $ok];
        }
    }
    foreach (['лат' => $sумLat, 'кир' => $sумCyr] as $pismo => $s) {
        $n = $norma['сумма'][$pismo];
        $brend['сумма · ' . $pismo] = [$s, $n['низ'] . '–' . $n['верх'],
            $s >= (int) $n['низ'] && $s <= (int) $n['верх']];
    }
}
$brendOk = count(array_filter($brend, fn($x) => $x[2]));
if ($brendOk < count($brend)) { $provaly['бренд'] = 1; }

// ── 4г. разметка: выделение, двоеточие в H3, эмодзи ─────────────────
// Три приёма, которых не было ни в одной нашей версии. Все три лежали в
// «отпустить»: разброс широкий, поле держит меньше 70 % корпуса. Но нулей у
// доноров почти нет — приём есть у всех, меняется только доза.
$razmetka = [];
$normaR = $profil['разметка']['страницы'] ?? [];
foreach (PAGES_K as $p) {
    if (!isset($normaR[$p])) { continue; }
    $html = $stranicy[$p];
    $st = substr_count($html, '<strong');
    preg_match_all('~<h3[^>]*>(.*?)</h3>~is', $html, $hm);
    $h3n = 0; $h3c = 0;
    foreach ($hm[1] as $x) {
        $t = trim(strip_tags($x));
        if ($t === '') { continue; }
        $h3n++;
        if (mb_strpos($t, ':') !== false || mb_strpos($t, '—') !== false) { $h3c++; }
    }
    $h3p = $h3n ? round($h3c / $h3n * 100) : 0;
    $em = preg_match_all('~[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{2300}-\x{23FF}]~u', $html);

    $n = $normaR[$p];
    // коридор — межквартильный размах донора, расширенный на floor
    $vil = function (float $v, array $q, float $pol) {
        return $v >= (float) $q['низ'] - $pol && $v <= (float) $q['верх'] + $pol;
    };
    $razmetka["$p · выделений"] = [$st, $n['strong']['низ'] . '–' . $n['strong']['верх'],
        $vil((float) $st, $n['strong'], 3)];
    $razmetka["$p · H3 с двоеточием"] = [$h3p . '%', $n['h3_colon_pct']['низ'] . '–' . $n['h3_colon_pct']['верх'] . '%',
        $vil((float) $h3p, $n['h3_colon_pct'], 15)];
    $razmetka["$p · эмодзи"] = [$em, $n['emoji']['низ'] . '–' . $n['emoji']['верх'],
        $vil((float) $em, $n['emoji'], 5)];
}
$razmOk = count(array_filter($razmetka, fn($x) => $x[2]));
// доля, а не «все до одного»: у донора это поле само гуляет
if ($razmetka && $razmOk / count($razmetka) < 0.8) { $provaly['разметка'] = 1; }

// ── 5. граф перелинковки ────────────────────────────────────────────
$ishod = [];
foreach (PAGES_K as $p) {
    // Хвост после пути ссылку не отменяет: «/registracia/», «/vhod#kod» и
    // «/slots?tab=new» — это те же внутренние переходы, а прежняя строгая
    // форма их не видела и заносила страницу в нулевые.
    preg_match_all('~<a\s[^>]*href="(/[a-z-]*)/?(?:[#?][^"]*)?"~i', $stranicy[$p], $m);
    $ishod[$p] = $m[1];
}
$vhodBonus = 0;
foreach ($ishod as $lst) { foreach ($lst as $h) { if (trim($h, '/') === 'bonus') { $vhodBonus++; } } }
$sGlavnoy = [];
foreach ($ishod['main'] as $h) { $c = trim($h, '/'); if ($c !== '' && $c !== 'bonus') { $sGlavnoy[$c] = 1; } }
$nazadNaGlavnuyu = 0;
foreach (PAGES_K as $p) {
    if ($p === 'main') { continue; }
    foreach ($ishod[$p] as $h) { if (trim($h, '/') === '') { $nazadNaGlavnuyu++; break; } }
}
$ssylokVsego = 0;
foreach (PAGES_K as $p) { $ssylokVsego += count($ishod[$p]); }
$ssylokCel = 0;
foreach (PAGES_K as $p) { $ssylokCel += (int) ($profil['страницы'][$p]['жанр']['ссылок'] ?? 50); }
$smeshenie['внутренних ссылок'] = [$ssylokVsego . ' из ' . $ssylokCel, '≥85%',
    $ssylokVsego / max(1, $ssylokCel) * 100 >= 85, round($ssylokVsego / max(1, $ssylokCel) * 100)];

$graf = [
    'ссылок с главной' => (function (int $n) use ($profil) {
        // Полоса берётся из профиля: в августе доноры ставили с главной 40–60
        // ссылок, в новом корпусе — 26–42, и зашитая в код вилка забракует всё.
        $g = $profil['граф']['ссылок_с_главной'] ?? ['низ' => 40, 'верх' => 60];
        $niz = (int) $g['низ']; $verh = (int) $g['верх'];
        return [$n, $niz . '–' . $verh, $n >= $niz && $n <= $verh];
    })(count($ishod['main'])),
    'главная ведёт на типов' => [count($sGlavnoy), '≥4', count($sGlavnoy) >= 4],
    'входящих на /bonus' => [$vhodBonus, '0', $vhodBonus === 0],
    'внутренних, ведущих назад' => [$nazadNaGlavnuyu, '0–2', $nazadNaGlavnuyu <= 2],
];
foreach (PAGES_K as $p) {
    if ($p === 'main') { continue; }
    $graf["ссылок с /$p"] = [count($ishod[$p]), '3–11',
        count($ishod[$p]) >= 3 && count($ishod[$p]) <= 11];
}
$grafOk = count(array_filter($graf, fn($x) => $x[2]));
if ($grafOk < count($graf)) { $provaly['граф'] = 1; }

// ── 6. техника по всем страницам ────────────────────────────────────
$teh = ['H1' => 0, 'H4' => 0, 'иерархия' => 0, 'картинок' => 0, 'nofollow' => 0, 'внешних' => 0];
foreach (PAGES_K as $p) {
    $d = new DOMDocument();
    $prev = libxml_use_internal_errors(true);
    $d->loadHTML('<?xml encoding="utf-8"?><html><body>' . $stranicy[$p] . '</body></html>',
        LIBXML_NOWARNING | LIBXML_NOERROR);
    libxml_clear_errors();
    libxml_use_internal_errors($prev);
    $seo = new SeoMetrics($d, $stranicy[$p]);
    $teh['H1'] += $seo->headingCount(1);
    $teh['H4'] += $seo->headingCount(4);
    if (!$seo->headingHierarchyOk()) { $teh['иерархия']++; }
    $teh['картинок'] += $seo->imgCount();
    $l = $seo->links('', "/$p");
    $teh['внешних'] += count($l['external']);
    foreach (['internal', 'external'] as $vid) {
        foreach ($l[$vid] as $it) { if ($it['nofollow']) { $teh['nofollow']++; } }
    }
}
$tehOk = ($teh['H1'] === 0) + ($teh['H4'] === 0) + ($teh['иерархия'] === 0)
    + ($teh['картинок'] === 0) + ($teh['nofollow'] === 0) + ($teh['внешних'] <= 3);
if ($tehOk < 6) { $provaly['техника'] = 1; }

// ── отчёт ───────────────────────────────────────────────────────────
printf("%s — комплект из %d страниц\n\n", basename($dir), count(PAGES_K));

echo "── параметры по типам ──\n";
foreach (PAGES_K as $p) {
    [$ok, $vs] = $otchet[$p]['поля'];
    $d = $otchet[$p]['доля'];
    echo '  ' . ($d >= PORog_POLEY ? '·' : '✗') . ' ' . $pad($p, 13, true)
        . $pad("$ok/$vs", 8) . $pad(round($d) . '%', 6)
        . ($otchet[$p]['промахи'] ? '  — ' . implode(', ', array_slice($otchet[$p]['промахи'], 0, 4)) : '')
        . "\n";
}

echo "\n── каркас внутренних ──\n";
foreach ($vnutr as $p => $v) {
    $bad = array_keys(array_filter($v['проверки'], fn($x) => !$x));
    echo '  ' . ($v['ок'] === $v['всего'] ? '·' : '✗') . ' ' . $pad($p, 13, true)
        . $pad($v['ок'] . '/' . $v['всего'], 6) . '  ' . mb_substr($v['первый H2'], 0, 46)
        . ($bad ? '   ✗ ' . implode(', ', $bad) : '') . "\n";
}

foreach ($smeshenie as $x) { if (!$x[2]) { $provaly['смещение'] = 1; } }

echo "\n── полы по рынку ──\n";
echo '  ' . $pad('', 14, true);
foreach (POLY as $imya) { echo $pad($imya, 15, true); }
echo "\n";
foreach (PAGES_K as $p) {
    echo '  ' . $pad($p, 14, true);
    foreach (POLY as $imya) {
        [$nash, $pol, $ok] = $poly[$imya][$p];
        $vid = $pol == (int) $pol && $nash == (int) $nash
            ? sprintf('%s %d/%d', $ok ? '·' : '✗', (int) $nash, (int) $pol)
            : sprintf('%s %.0f/%.0f', $ok ? '·' : '✗', $nash, $pol);
        echo $pad($vid, 15, true);
    }
    echo "\n";
}

echo "\n── смещение по отпущенным полям ──\n";
foreach ($smeshenie as $n => [$est, $nado, $ok, $pct]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 24, true) . $pad($est, 16)
        . $pad($pct . '%', 7) . '   нужно ' . $nado . "\n";
}

echo "\n── бренд: школа написания ──\n";
foreach ($brend as $n => [$est, $nado, $ok]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 24, true) . $pad((string) $est, 8)
        . '   норма ' . $nado . "\n";
}

echo "\n── разметка: выделение, H3, эмодзи ──\n";
foreach ($razmetka as $n => [$est, $nado, $ok]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 26, true) . $pad((string) $est, 7)
        . '   норма ' . $nado . "\n";
}

echo "\n── граф перелинковки ──\n";
foreach ($graf as $n => [$est, $nado, $ok]) {
    echo '  ' . ($ok ? '·' : '✗') . ' ' . $pad($n, 28, true) . $pad((string) $est, 6) . '   нужно ' . $nado . "\n";
}

echo "\n── техника по всем семи ──\n";
printf("  %sH1 %d · H4 %d · сбоев иерархии %d · картинок %d · nofollow %d · внешних ссылок %d\n",
    $tehOk === 6 ? '· ' : '✗ ', $teh['H1'], $teh['H4'], $teh['иерархия'],
    $teh['картинок'], $teh['nofollow'], $teh['внешних']);

echo "\n── уникальность ──\n";
printf("  срезы тем внутри комплекта: %s\n", $dubliVnutri ? "✗ $dubliVnutri повтора" : 'все разные');
printf("  срезы совпали с корпусом:   %s\n", $sovpavshie ? '✗ ' . implode(', ', $sovpavshie) : 'нет');
printf("  худшая пара по шинглам:     %.2f%%  (%s), порог %s%%\n", $hudshayaPara, $hudshiy,
    rtrim(rtrim(sprintf('%.2f', $porog), '0'), '.'));
printf("  каннибализация внутри:      %.2f%%  (потолок 3%%)\n", $kanMax);
printf("  %s скелет H2 главной:         %.1f%%  (%s), потолок %s%%\n",
    $skeletMax > POTOLOK_SKELETA ? '✗' : ' ', $skeletMax, $skeletKto,
    rtrim(rtrim(sprintf('%.1f', POTOLOK_SKELETA), '0'), '.'));
printf("  %s пересечение хвостов:       %.1f%%  (%s), потолок %s%%\n",
    $hvostMax > POTOLOK_HVOSTOV ? '✗' : ' ', $hvostMax, $hvostPara,
    rtrim(rtrim(sprintf('%.1f', POTOLOK_HVOSTOV), '0'), '.'));
printf("  повтор роли в H3:           %.1f%%  (потолок 60%%, у доноров 25-52%%)\n", $shablon);

// Согласование по всем семи. Числовые меры на разъехавшемся тексте не
// портятся, а часто улучшаются: слепая замена синонимов сбивает и тошноту, и
// шинглы. Единственная проверка комплекта, которая смотрит на связность речи.
echo "\n── согласование ──\n";
$sryvyVsego = 0;
foreach (PAGES_K as $p) {
    $sr = Soglasovanie::proverit($stranicy[$p]);
    $sryvyVsego += count($sr);
    if (!$sr) { continue; }
    printf("  ✗ %s — %d\n", $p, count($sr));
    foreach (array_slice($sr, 0, 6) as $s) {
        printf("      · %-9s «%s»  в <%s>\n", $s['вид'], $s['текст'], $s['где']);
    }
}
if ($sryvyVsego === 0) { echo "  · срывов нет ни на одной из семи\n"; }
else { $provaly['согласование'] = 1; }

printf("\nИТОГ: %s\n", $provaly ? 'НЕ ПРОЙДЕНО — ' . implode(', ', array_keys($provaly)) : 'комплект принят');
exit($provaly ? 1 : 0);

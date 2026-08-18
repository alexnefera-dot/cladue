<?php
declare(strict_types=1);

/**
 * Технический разбор корпуса через SeoMetrics.
 *
 *   php engine/seo-korpusa.php <папка> [--школа=проза|конструктор] [--json]
 *
 * Я сначала списал SeoMetrics со счетёта: у донорских фрагментов нет <head>,
 * значит нечего мерить. Это было неверно. Без <head> отпадают четыре поля —
 * title, description, lang, viewport, — а остальные считаются по разметке и
 * дают то, чего не видит ни один из прежних инструментов:
 *
 *   — соотношение текст/код в байтах;
 *   — целостность иерархии заголовков (пропуск уровня H2 → H4);
 *   — nofollow и внешние ссылки, которые я до сих пор не считал вовсе;
 *   — переспам выделением: доля <strong>, внутри которых стоит ключ;
 *   — em, blockquote, video, alt у картинок.
 */

require_once __DIR__ . '/src/SeoMetrics.php';

const PAGES_S = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
const BLOCK_TAIL_S = '~(block|section|dashboard|hero|pillars|quotes-list|strip|panel|widget|banner|card)$~';
/** Ключи, по которым проверяется переспам выделением. */
const KEYS_S = ['казино', 'бонус', 'зеркало', 'слот', 'регистрация'];

$root = $argv[1] ?? '';
$shkola = '';
$asJson = in_array('--json', $argv, true);
foreach (array_slice($argv, 2) as $a) {
    if (str_starts_with($a, '--школа=')) { $shkola = substr($a, strlen('--школа=')); }
}
if ($root === '' || !is_dir($root)) {
    fwrite(STDERR, "usage: php engine/seo-korpusa.php <папка> [--школа=…] [--json]\n");
    exit(1);
}

/**
 * Фрагмент без <html> DOMDocument разбирает, но чтобы iterate по //h2 работал
 * одинаково, оборачиваем в минимальный документ и глушим предупреждения о
 * нестандартных тегах вроде <details>.
 */
function dom(string $fragment): ?DOMDocument
{
    $d = new DOMDocument();
    $prev = libxml_use_internal_errors(true);
    $ok = $d->loadHTML('<?xml encoding="utf-8"?><html><body>' . $fragment . '</body></html>',
        LIBXML_NOWARNING | LIBXML_NOERROR);
    libxml_clear_errors();
    libxml_use_internal_errors($prev);
    return $ok ? $d : null;
}

function med(array $v)
{
    if (!$v) { return 0; }
    sort($v);
    return $v[intdiv(count($v), 2)];
}

// ── отбор ───────────────────────────────────────────────────────────
$dirs = [];
foreach (glob(rtrim($root, '/') . '/*', GLOB_ONLYDIR) ?: [] as $d) {
    if (!is_file("$d/main.html")) { continue; }
    $b = [];
    foreach (glob("$d/*.html") ?: [] as $f) {
        preg_match_all('~<(?:section|div|article|aside)\s+class="([a-z][a-z0-9_-]*)((?:\s+[a-z0-9_-]+)*)"~i',
            (string) file_get_contents($f), $m, PREG_SET_ORDER);
        foreach ($m as $x) {
            if (preg_match(BLOCK_TAIL_S, $x[1]) || str_contains($x[2], 'variant-')) { $b[$x[1]] = 1; }
        }
    }
    $sh = count($b) >= 5 ? 'конструктор' : 'проза';
    if ($shkola === '' || $sh === $shkola) { $dirs[] = $d; }
}
if (!$dirs) { fwrite(STDERR, "нечего мерить\n"); exit(1); }

// ── обход ───────────────────────────────────────────────────────────
$poStr = [];      // [страница][поле][] = значение
$ierarhiya = ['ок' => 0, 'сбой' => 0];
$propuski = [];   // какие переходы уровней ломают иерархию
$vneshnie = [];   // хосты внешних ссылок
$nofollow = 0; $vsegoSsylok = 0;
$spam = array_fill_keys(KEYS_S, 0);
$sSpamom = 0; $stranic = 0;
$altPusto = 0; $imgVsego = 0;

foreach ($dirs as $dir) {
    foreach (PAGES_S as $p) {
        $f = "$dir/$p.html";
        if (!is_file($f)) { continue; }
        $raw = (string) file_get_contents($f);
        $d = dom($raw);
        $seo = new SeoMetrics($d, $raw);
        $stranic++;

        $poStr[$p]['текст/код %'][] = $seo->textHtmlRatio();
        $poStr[$p]['H2'][] = $seo->headingCount(2);
        $poStr[$p]['H3'][] = $seo->headingCount(3);
        $poStr[$p]['H1'][] = $seo->headingCount(1);
        $poStr[$p]['H4'][] = $seo->headingCount(4);
        $poStr[$p]['списков'][] = $seo->listCount();
        $poStr[$p]['strong+b'][] = $seo->strongCount();
        $poStr[$p]['em+i'][] = $seo->emCount();
        $poStr[$p]['таблиц'][] = $seo->tableCount();
        $poStr[$p]['цитат'][] = $seo->quoteCount();
        $poStr[$p]['видео'][] = $seo->videoCount();
        $poStr[$p]['картинок'][] = $seo->imgCount();
        $poStr[$p]['насыщенность'][] = $seo->mediaRichness();
        $poStr[$p]['schema'][] = $seo->hasSchema() ? 1 : 0;

        if ($seo->headingHierarchyOk()) { $ierarhiya['ок']++; }
        else {
            $ierarhiya['сбой']++;
            // Ищем конкретный прыжок, чтобы не гадать.
            preg_match_all('~<h([1-6])\b~i', $raw, $hm);
            $prev = 0;
            foreach ($hm[1] as $lvl) {
                $lvl = (int) $lvl;
                if ($prev && $lvl > $prev + 1) { $propuski["H$prev → H$lvl"] = ($propuski["H$prev → H$lvl"] ?? 0) + 1; }
                $prev = $lvl;
            }
        }

        $imgVsego += $seo->imgCount();
        if ($seo->imgCount()) { $altPusto += (int) round((100 - $seo->imgAltFilledPercent()) / 100 * $seo->imgCount()); }

        $l = $seo->links('', "/$p");
        foreach (['internal', 'external'] as $vid) {
            foreach ($l[$vid] as $it) {
                $vsegoSsylok++;
                if ($it['nofollow']) { $nofollow++; }
                if ($vid === 'external') {
                    $host = parse_url($it['href'], PHP_URL_HOST) ?: $it['href'];
                    $vneshnie[$host] = ($vneshnie[$host] ?? 0) + 1;
                }
            }
        }
        $poStr[$p]['внутренних ссылок'][] = count($l['internal']);
        $poStr[$p]['внешних ссылок'][] = count($l['external']);

        $bylSpam = false;
        foreach (KEYS_S as $k) {
            if ($seo->strongKeywordSpam($k)) { $spam[$k]++; $bylSpam = true; }
        }
        if ($bylSpam) { $sSpamom++; }
    }
}

// ── сводка ──────────────────────────────────────────────────────────
$svod = [];
foreach ($poStr as $p => $f) {
    foreach ($f as $k => $v) { $svod[$p][$k] = med($v); }
}
arsort($vneshnie);

$out = [
    'корпус' => basename(rtrim($root, '/')),
    'школа' => $shkola ?: 'все',
    'сайтов' => count($dirs), 'страниц' => $stranic,
    'по страницам' => $svod,
    'иерархия заголовков' => [
        'без пропусков' => $ierarhiya['ок'] . '/' . $stranic,
        'с пропуском уровня' => $ierarhiya['сбой'] . '/' . $stranic,
        'какие прыжки' => $propuski,
    ],
    'ссылки' => [
        'всего' => $vsegoSsylok,
        'nofollow' => $nofollow,
        'внешних хостов' => count($vneshnie),
        'топ внешних' => array_slice($vneshnie, 0, 12, true),
    ],
    'картинки' => ['всего' => $imgVsego, 'без alt' => $altPusto],
    'переспам выделением' => ['страниц' => $sSpamom . '/' . $stranic, 'по ключам' => $spam],
];

if ($asJson) {
    echo json_encode($out, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}

$pad = fn($v, $w, $l = false) => $l
    ? $v . str_repeat(' ', max(0, $w - mb_strlen((string) $v)))
    : str_repeat(' ', max(0, $w - mb_strlen((string) $v))) . $v;

printf("══ %s%s: %d сайтов, %d страниц ══\n\n", $out['корпус'],
    $shkola ? " · $shkola" : '', count($dirs), $stranic);

$cols = ['текст/код %', 'H1', 'H2', 'H3', 'H4', 'списков', 'strong+b', 'em+i',
    'таблиц', 'цитат', 'видео', 'картинок', 'насыщенность', 'schema',
    'внутренних ссылок', 'внешних ссылок'];
echo "── медианы по типам страниц ──\n";
echo '  ' . $pad('страница', 13, true);
foreach ($cols as $c) { echo $pad(mb_substr($c, 0, 9), 11); }
echo "\n";
foreach (PAGES_S as $p) {
    if (!isset($svod[$p])) { continue; }
    echo '  ' . $pad($p, 13, true);
    foreach ($cols as $c) { echo $pad((string) ($svod[$p][$c] ?? 0), 11); }
    echo "\n";
}

echo "\n── иерархия заголовков ──\n";
printf("  без пропусков %s, с пропуском уровня %s\n",
    $out['иерархия заголовков']['без пропусков'], $out['иерархия заголовков']['с пропуском уровня']);
foreach ($propuski as $k => $v) { printf("    %-12s %d страниц\n", $k, $v); }

echo "\n── ссылки ──\n";
printf("  всего %d, nofollow %d, внешних хостов %d\n", $vsegoSsylok, $nofollow, count($vneshnie));
foreach (array_slice($vneshnie, 0, 12, true) as $h => $n) { printf("    %-34s %d\n", mb_substr($h, 0, 34), $n); }

echo "\n── картинки ──\n";
printf("  всего %d, без alt %d\n", $imgVsego, $altPusto);

echo "\n── переспам выделением (>30%% strong с ключом) ──\n";
printf("  страниц %s\n", $out['переспам выделением']['страниц']);
foreach ($spam as $k => $v) { printf("    %-12s %d\n", $k, $v); }
echo "\n";

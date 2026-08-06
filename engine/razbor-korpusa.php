<?php
declare(strict_types=1);

/**
 * Разбор целого корпуса доноров: N сайтов × M страниц.
 *
 *   php engine/razbor-korpusa.php <папка-корпуса> [--json] [--pары]
 *
 * razbor-donora.php отвечает на вопрос «что делает одна чужая страница».
 * Здесь вопрос другой: «что делает фабрика, которая напекла пятьдесят таких
 * комплектов». Одна страница не показывает ни библиотеки блоков, ни того, что
 * в ней случайное, а что постоянное — это видно только на пересечении.
 *
 * Печатает семь блоков:
 *   1. инвентарь — объём и разметка по типам страниц (медианы)
 *   2. школы — деление корпуса по устройству, а не по тексту
 *   3. библиотека блоков — какие виджеты есть и на каких страницах стоят
 *   4. schema.org — вся микроразметка корпуса
 *   5. сетка ссылок — куда и сколько ведут внутренние ссылки, анкоры
 *   6. подстановки — плейсхолдеры движка публикации
 *   7. уникальность — пересечение по шинглам между сайтами (с --пары)
 */

const PAGES = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];

/** Виджеты именуются по базовому классу; отбор по суффиксу, чтобы не тащить внутренние обёртки. */
const BLOCK_TAIL = '~(block|section|dashboard|hero|pillars|quotes-list|strip|panel|widget|banner|card)$~';

const EMOJI = '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{2190}-\x{21FF}\x{25A0}-\x{25FF}]';

$root = $argv[1] ?? '';
$asJson = in_array('--json', $argv, true);
$withPairs = in_array('--пары', $argv, true) || in_array('--pairs', $argv, true);
if ($root === '' || !is_dir($root)) {
    fwrite(STDERR, "usage: php engine/razbor-korpusa.php <папка-корпуса> [--json] [--пары]\n");
    exit(1);
}

/**
 * strip_tags() спотыкается о голый «<» в тексте и глотает всё до следующего «>»:
 * у одного донора так пропало 46 КБ из 58. Режем только то, что похоже на тег.
 */
function tekst(string $html): string
{
    $h = preg_replace('~(?is)<(script|style)\b.*?</\1>~', ' ', $html);
    $h = preg_replace('~<[a-zA-Z/!][^>]*>~', ' ', (string) $h);
    return html_entity_decode((string) $h, ENT_QUOTES | ENT_HTML5, 'UTF-8');
}

function slov(string $t): int
{
    return preg_match_all('~[\p{L}\p{N}]+~u', $t);
}

function shingly(string $t, int $n = 6): array
{
    $t = mb_strtolower(preg_replace('~%[a-z_]+%~u', ' бренд ', $t));
    preg_match_all('~[\p{L}\p{N}]+~u', $t, $m);
    $w = $m[0];
    $s = [];
    for ($i = 0; $i + $n <= count($w); $i++) { $s[implode(' ', array_slice($w, $i, $n))] = 1; }
    return $s;
}

function mediana(array $v): float
{
    if (!$v) { return 0.0; }
    sort($v);
    return (float) $v[(int) (count($v) / 2)];
}

// ── обход ───────────────────────────────────────────────────────────
$sites = [];
$inventar = [];   // [страница][поле][] = значение
$biblioteka = []; // [блок][страница] = сколько
$blokiSajta = []; // [сайт][блок] = сколько
$schema = [];
$ankory = [];
$adresa = [];
$podstanovki = [];
$varianty = [];
$emodzi = [];
$shingle = [];    // [сайт][страница] = набор

foreach (glob(rtrim($root, '/') . '/*', GLOB_ONLYDIR) ?: [] as $dir) {
    $site = basename($dir);
    $sites[] = $site;
    foreach (glob("$dir/*.html") ?: [] as $file) {
        $page = basename($file, '.html');
        $h = (string) file_get_contents($file);
        $t = tekst($h);

        $inventar[$page]['байт'][] = strlen($h);
        $inventar[$page]['слов'][] = slov($t);
        foreach (['h2', 'h3', 'p', 'li', 'table', 'tr', 'details', 'strong', 'em', 'img', 'a'] as $tag) {
            $inventar[$page][$tag][] = preg_match_all('~(?i)<' . $tag . '\b~', $h);
        }
        $inventar[$page]['schema'][] = preg_match_all('~itemtype="[^"]*schema~', $h);
        $inventar[$page]['эмодзи'][] = preg_match_all('~' . EMOJI . '~u', $h);
        $inventar[$page]['style'][] = preg_match_all('~(?i)<style\b~', $h);
        $inventar[$page]['script'][] = preg_match_all('~(?i)<script\b~', $h);
        $lt = mb_strtolower($t);
        $inventar[$page]['я'][] = preg_match_all(
            '~(?<![\p{L}])(я|мне|меня|мой|моя|моё|мои|моего|моей|мною)(?![\p{L}])~u', $lt
        );

        // блоки
        preg_match_all(
            '~<(?:section|div|article|aside)\s+class="([a-z][a-z0-9_-]*)((?:\s+[a-z0-9_-]+)*)"~i',
            $h, $bm, PREG_SET_ORDER
        );
        foreach ($bm as $x) {
            $base = $x[1];
            $mods = trim($x[2]);
            $isVariant = str_contains($mods, 'variant-');
            if (!preg_match(BLOCK_TAIL, $base) && !$isVariant) { continue; }
            $biblioteka[$base][$page] = ($biblioteka[$base][$page] ?? 0) + 1;
            $blokiSajta[$site][$base] = ($blokiSajta[$site][$base] ?? 0) + 1;
            if ($isVariant && preg_match('~variant-(v\d+)~', $mods, $vm)) {
                $varianty[$base][$vm[1]] = ($varianty[$base][$vm[1]] ?? 0) + 1;
            }
        }

        foreach (preg_match_all('~schema\.org/([A-Za-z]+)~', $h, $sm) ? $sm[1] : [] as $s) {
            $schema[$s] = ($schema[$s] ?? 0) + 1;
        }
        foreach (preg_match_all('~%[a-z_]+%~', $h, $pm) ? $pm[0] : [] as $p) {
            $podstanovki[$p] = ($podstanovki[$p] ?? 0) + 1;
        }
        foreach (preg_match_all('~' . EMOJI . '~u', $h, $em) ? $em[0] : [] as $e) {
            $emodzi[$e] = ($emodzi[$e] ?? 0) + 1;
        }
        if (preg_match_all('~<a\s[^>]*href="([^"]*)"[^>]*>(.*?)</a>~is', $h, $am, PREG_SET_ORDER)) {
            foreach ($am as $x) {
                $adresa[$x[1]] = ($adresa[$x[1]] ?? 0) + 1;
                if ($x[1] === '' || $x[1][0] !== '/') { continue; }
                $an = trim(preg_replace('~\s+~u', ' ', strip_tags($x[2])));
                if ($an !== '') { $ankory[$an] = ($ankory[$an] ?? 0) + 1; }
            }
        }

        if ($withPairs) { $shingle[$page][$site] = shingly($t); }
    }
}

// ── школы: сайт с виджетной библиотекой против сайта с прозой ────────
$shkoly = ['конструктор' => [], 'проза' => []];
foreach ($sites as $s) {
    $n = count($blokiSajta[$s] ?? []);
    $shkoly[$n >= 5 ? 'конструктор' : 'проза'][] = $s;
}

// ── уникальность ────────────────────────────────────────────────────
$pary = [];
if ($withPairs) {
    foreach ($shingle as $page => $sets) {
        $names = array_keys($sets);
        $vals = [];
        $top = [0.0, '—', '—'];
        for ($i = 0; $i < count($names); $i++) {
            for ($j = $i + 1; $j < count($names); $j++) {
                $a = $sets[$names[$i]];
                $b = $sets[$names[$j]];
                $min = min(count($a), count($b));
                if (!$min) { continue; }
                $v = count(array_intersect_key($a, $b)) / $min * 100;
                $vals[] = $v;
                if ($v > $top[0]) { $top = [$v, $names[$i], $names[$j]]; }
            }
        }
        $pary[$page] = [
            'пар' => count($vals),
            'среднее' => $vals ? round(array_sum($vals) / count($vals), 2) : 0,
            'медиана' => round(mediana($vals), 2),
            'макс' => round($top[0], 2),
            'худшая пара' => $top[1] . ' ↔ ' . $top[2],
        ];
    }
}

// ── вывод ───────────────────────────────────────────────────────────
$svod = [];
foreach ($inventar as $page => $f) {
    foreach ($f as $k => $v) { $svod[$page][$k] = mediana($v); }
    $svod[$page]['страниц'] = count($f['байт']);
}

arsort($schema);
arsort($podstanovki);
arsort($adresa);
arsort($ankory);
arsort($emodzi);
uasort($biblioteka, fn($a, $b) => array_sum($b) <=> array_sum($a));

if ($asJson) {
    echo json_encode([
        'корпус' => basename(rtrim($root, '/')),
        'сайтов' => count($sites),
        'сайты' => $sites,
        'инвентарь' => $svod,
        'школы' => $shkoly,
        'библиотека' => $biblioteka,
        'варианты' => $varianty,
        'блоков у сайта' => array_map('count', $blokiSajta),
        'schema' => $schema,
        'адреса' => array_slice($adresa, 0, 40, true),
        'анкоры' => array_slice($ankory, 0, 60, true),
        'подстановки' => $podstanovki,
        'эмодзи' => array_slice($emodzi, 0, 40, true),
        'пары' => $pary,
    ], JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}

/** printf считает байты, а в шапках кириллица — колонки разъезжаются. */
$stolb = function (string $s, int $w, bool $left = false): string {
    $pad = str_repeat(' ', max(0, $w - mb_strlen($s)));
    return $left ? $s . $pad : $pad . $s;
};

printf("══ %s: %d сайтов, %d страниц ══\n\n", basename(rtrim($root, '/')), count($sites),
    array_sum(array_map(fn($p) => $p['страниц'], $svod)));

echo "── инвентарь (медианы) ──\n";
$cols = ['байт', 'слов', 'h2', 'h3', 'p', 'li', 'table', 'details', 'strong', 'img', 'a', 'schema', 'эмодзи', 'style', 'script', 'я'];
echo '  ' . $stolb('страница', 13, true);
foreach ($cols as $c) { echo $stolb($c, 8); }
echo "\n";
foreach (PAGES as $p) {
    if (!isset($svod[$p])) { continue; }
    echo '  ' . $stolb($p, 13, true);
    foreach ($cols as $c) { echo $stolb((string) (int) ($svod[$p][$c] ?? 0), 8); }
    echo "\n";
}

echo "\n── школы ──\n";
foreach ($shkoly as $name => $list) {
    echo '  ' . $stolb($name, 13, true) . sprintf(" %2d: %s\n", count($list), implode(', ', $list));
}

echo "\n── библиотека блоков ──\n";
echo '  ' . $stolb('блок', 24, true) . $stolb('всего', 5) . "  по страницам\n";
foreach ($biblioteka as $b => $pp) {
    $s = [];
    foreach (PAGES as $p) { if (isset($pp[$p])) { $s[] = $p . '×' . $pp[$p]; } }
    $v = '';
    if (isset($varianty[$b])) {
        ksort($varianty[$b]);
        foreach ($varianty[$b] as $k => $n) { $v .= ' ' . $k . '×' . $n; }
        $v = '   варианты:' . $v;
    }
    echo '  ' . $stolb($b, 24, true) . $stolb((string) array_sum($pp), 5)
        . '  ' . implode(' ', $s) . $v . "\n";
}

echo "\n── schema.org ──\n";
foreach ($schema as $k => $v) { printf("  %-28s %5d\n", $k, $v); }

echo "\n── сетка ссылок ──\n";
$vnutr = array_filter($adresa, fn($k) => $k !== '' && $k[0] === '/', ARRAY_FILTER_USE_KEY);
printf("  внутренних всего %d, разных адресов %d, разных анкоров %d\n",
    array_sum($vnutr), count($vnutr), count($ankory));
$odinochki = count(array_filter($ankory, fn($x) => $x === 1));
printf("  анкоров-одиночек %d (%.0f%%)\n", $odinochki, $ankory ? $odinochki / count($ankory) * 100 : 0);
foreach (array_slice($vnutr, 0, 10, true) as $k => $v) { printf("    %-20s %5d\n", $k, $v); }
echo "  топ анкоров:\n";
foreach (array_slice($ankory, 0, 12, true) as $k => $v) { printf("    %5d  %s\n", $v, mb_substr($k, 0, 50)); }

echo "\n── подстановки ──\n";
foreach ($podstanovki as $k => $v) { printf("  %-20s %5d\n", $k, $v); }

echo "\n── эмодзи ──\n  ";
$i = 0;
foreach ($emodzi as $e => $n) { echo $e . '×' . $n . '  '; if (++$i >= 20) { break; } }
echo "\n";

if ($pary) {
    echo "\n── уникальность между сайтами (шингл 6) ──\n";
    echo '  ' . $stolb('страница', 14, true) . $stolb('среднее', 8) . $stolb('медиана', 8)
        . $stolb('макс', 8) . "  худшая пара\n";
    foreach (PAGES as $p) {
        if (!isset($pary[$p])) { continue; }
        echo '  ' . $stolb($p, 14, true)
            . sprintf("%7.2f%%%7.2f%%%7.2f%%  %s\n", $pary[$p]['среднее'],
                $pary[$p]['медиана'], $pary[$p]['макс'], $pary[$p]['худшая пара']);
    }
}
echo "\n";

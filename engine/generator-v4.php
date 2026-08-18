<?php
declare(strict_types=1);

/**
 * Генератор семистраничного комплекта: задание → написание → замер → правка.
 *
 *   php engine/generator-v4.php --комплект=kran-1 [--маска=портовый кран]
 *        [--выход=samples/v5-final] [--попыток=3] [--модель=claude-opus-5]
 *        [--только=main,slots] [--сухой] [--профиль=engine/data-v5/profil-v5.json]
 *
 * Один прогон делает то же, что человек делал руками всю эту ветку, но по
 * порядку и с проверкой на каждом шаге:
 *
 *   1. zadanie-v4.php   — семь промптов из профиля: цели, каркас, разметка,
 *                         школа бренда, граф, занятые срезы соседей;
 *   2. realize.php      — один вызов модели на страницу;
 *   3. dovodchik-v4.php — механическая доводка ЧЕТЫРЁХ счётных величин;
 *   4. priyomka-v4      — замер страницы против профиля;
 *   5. бриф на правку   — что мимо и на сколько, обратно писателю (mode=fix);
 *   6. priyomka-комплект— межстраничные правила: срезы, шинглы, граф, смещение.
 *
 * Ключевое правило, купленное дорого. Правка НЕ ходит регулярками по тексту.
 * Пакетный проход, который менял синонимы на ключи, разносил абзацы и вставлял
 * реплики по позиции, довёл счётчики до донорских и испортил текст: «второй
 * регистрация», «к лицензия», «Откройте профиль и указать ящик», отсылка без
 * антецедента. Шлюзы этого не увидели — они считают, а не читают. Поэтому всё,
 * что требует согласования слов, возвращается писателю брифом, а скрипт трогает
 * только то, что грамматику сломать не может.
 *
 * --сухой: пройти весь цикл без вызовов модели. Промпты собираются, замер идёт
 * по уже лежащим файлам. Нужен, чтобы проверять сам конвейер без расхода токенов.
 */

const PAGES_G = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];

$opts = [];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('~^--([^=]+)=(.*)$~su', $a, $m)) { $opts[$m[1]] = $m[2]; }
    elseif (preg_match('~^--(.+)$~su', $a, $m)) { $opts[$m[1]] = true; }
}
$IMYA    = $opts['комплект'] ?? '';
$MASKA   = $opts['маска'] ?? '';
$VYHOD   = rtrim($opts['выход'] ?? 'samples/v4-final', '/');
$POPYTOK = (int) ($opts['попыток'] ?? 3);
$MODEL   = $opts['модель'] ?? 'claude-opus-5';
$SUHOY   = isset($opts['сухой']);
// Профиль поколения прокидывается во ВСЕ шаги разом: задание, реалайзер,
// доводчик и обе приёмки. Разные профили на разных шагах — это комплект,
// который пишется по одному поколению, а принимается по другому.
$PROFIL  = $opts['профиль'] ?? '';
$P       = $PROFIL !== '' ? ' --профиль=' . escapeshellarg($PROFIL) : '';
// Уникальность сверяется с тем корпусом, в который комплект и пишется. Без
// этого приёмка внутри генератора брала корпус по умолчанию и ловила повтор
// заголовка с чужим поколением.
$K       = ' --korpus=' . escapeshellarg($VYHOD);
$TOLKO   = isset($opts['только']) ? explode(',', (string) $opts['только']) : PAGES_G;
if ($IMYA === '' && $MASKA === '') {
    fwrite(STDERR, "usage: php engine/generator-v4.php --комплект=<имя> [--маска=…] [--сухой]\n");
    exit(1);
}

$root = dirname(__DIR__);
chdir($root);
$TMP = "tmp/gen-" . ($IMYA !== '' ? $IMYA : 'auto');
@mkdir($TMP, 0777, true);

function shag(string $s): void { echo "\n\033[1m── $s\033[0m\n"; }
function stroka(string $s): void { echo "   $s\n"; }

// ── 1. задание ──────────────────────────────────────────────────────────────
shag('задание');
$cmd = sprintf('php %s/engine/zadanie-v4.php --выход=%s --корпус=%s',
    escapeshellarg($root), escapeshellarg($TMP), escapeshellarg($VYHOD));
if ($MASKA !== '') { $cmd .= ' --маска=' . escapeshellarg($MASKA); }
if ($IMYA !== '')  { $cmd .= ' --комплект=' . escapeshellarg($IMYA); }
$cmd .= $P;
exec($cmd . ' 2>&1', $vyv, $rc);
foreach ($vyv as $l) { stroka($l); }
if ($rc !== 0) { fwrite(STDERR, "задание не собралось\n"); exit(1); }

$karta = json_decode((string) file_get_contents("$TMP/karta.json"), true);
$IMYA = $karta['комплект'];
$DIR = "$VYHOD/$IMYA";
@mkdir($DIR, 0777, true);

// ── 2–5. страницы: написать, довести, замерить, поправить ───────────────────
$itog = [];
foreach (PAGES_G as $p) {
    if (!in_array($p, $TOLKO, true)) { continue; }
    shag("страница $p");
    $out = "$DIR/$p.html";
    $prompt = "$TMP/prompt-$p.md";

    for ($n = 1; $n <= $POPYTOK; $n++) {
        // ── написание ───────────────────────────────────────────────────────
        if (!$SUHOY) {
            $rez = "$TMP/$p-попытка-$n.html";
            $c = sprintf('php %s/engine/realize.php --prompt=%s --out=%s --model=%s --max-tokens=32000',
                escapeshellarg($root), escapeshellarg($prompt), escapeshellarg($rez), escapeshellarg($MODEL));
            $c .= $P;
            if ($n > 1) { $c .= ' --mode=fix'; }
            exec($c . ' 2>&1', $rv, $rc2);
            if ($rc2 !== 0) { stroka('модель не ответила: ' . implode(' ', array_slice($rv, -2))); break; }
            copy($rez, $out);
        } elseif (!is_file($out)) {
            stroka('сухой прогон: файла нет, пропускаю');
            break;
        }

        // ── механическая доводка четырёх счётных величин ────────────────────
        exec(sprintf('php %s/engine/dovodchik-v4.php %s %s%s 2>&1',
            escapeshellarg($root), escapeshellarg($out), escapeshellarg($p), $P), $dv);
        // Строки с пометкой «писателю» — это то, что механикой не берётся:
        // доля с двоеточием в H3, число списков, выделения. Раньше они только
        // печатались и до брифа не доходили, так что писатель узнавал о них
        // ниоткуда и не правил их вовсе.
        $pisatelyu = [];
        foreach ($dv as $l) {
            if (trim($l) === '') { continue; }
            stroka('доводчик: ' . $l);
            if (mb_strpos($l, 'писателю') !== false) { $pisatelyu[] = trim($l); }
        }
        $dv = [];

        // ── замер ───────────────────────────────────────────────────────────
        $promahi = array_merge(zamer($root, $DIR, $p, $P, $K), $pisatelyu);
        if (!$promahi) { stroka("попытка $n — принято"); $itog[$p] = 'принято'; break; }

        stroka("попытка $n — мимо: " . implode(', ', array_slice($promahi, 0, 4))
            . (count($promahi) > 4 ? ' …' : ''));
        $itog[$p] = 'мимо: ' . implode(', ', $promahi);

        if ($SUHOY) { break; }   // файл не менялся — повтор ничего не даст
        if ($n < $POPYTOK) {
            file_put_contents($prompt . '.fix', brief($prompt, $out, $promahi));
            $prompt = $prompt . '.fix';
        }
    }
}

// ── 6. приёмка комплекта ────────────────────────────────────────────────────
shag('приёмка комплекта');
exec(sprintf('php %s/engine/priyomka-komplekt.php %s%s%s 2>&1',
    escapeshellarg($root), escapeshellarg($DIR), $K, $P), $kv, $krc);
$hvost = [];
foreach ($kv as $l) { if (preg_match('~✗|ИТОГ~u', $l)) { $hvost[] = trim($l); } }
foreach ($hvost as $l) { stroka($l); }

// ── 7. занять маску и срезы, если комплект принят ───────────────────────────
if ($krc === 0 && !$SUHOY) {
    $mf = __DIR__ . '/data-v4/maski.json';
    $mk = json_decode((string) file_get_contents($mf), true);
    if (!in_array($karta['маска'], $mk['занято']['маски'], true)) {
        $mk['занято']['маски'][] = $karta['маска'];
    }
    foreach ($karta['срезы'] as $p2 => $srez) {
        if (!in_array($srez, $mk['занято']['срезы'][$p2] ?? [], true)) {
            $mk['занято']['срезы'][$p2][] = $srez;
        }
        $mk['срезы_запас'][$p2] = array_values(array_filter(
            $mk['срезы_запас'][$p2] ?? [], fn($x) => $x !== $srez));
    }
    file_put_contents($mf, json_encode($mk, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    stroka('маска и срезы отмечены занятыми');
}

shag('итог');
foreach ($itog as $p => $s) { printf("   %-12s %s\n", $p, mb_substr($s, 0, 70)); }
printf("\n   комплект: %s\n", $krc === 0 ? "\033[32mпринят\033[0m" : "\033[31mне принят\033[0m");
printf("   папка:    %s\n   промпты:  %s\n", $DIR, $TMP);
exit($krc === 0 ? 0 : 1);


/**
 * Замер страницы: список промахов «поле было→нужно». Пусто — принято.
 *
 * Профиль передаётся параметром, а не через глобальную: в функции она не
 * видна, и обе приёмки молча меряли по августовским полосам, пока комплект
 * писался по новым.
 */
function zamer(string $root, string $dir, string $p, string $prof = '', string $korp = ''): array
{
    $bad = [];
    if ($p === 'main') {
        exec(sprintf('php %s/engine/priyomka-v4.php %s%s%s 2>&1',
            escapeshellarg($root), escapeshellarg($dir), $korp, $prof), $v);
        foreach ($v as $l) {
            if (preg_match('~^\s*✗\s+(.+?)\s{2,}(\S+)\s+нужно\s+(\S+)~u', $l, $m)) {
                $bad[] = trim($m[1]) . ' ' . $m[2] . '→' . $m[3];
            } elseif (preg_match('~^\s*✗\s+(\S+)\s+([\d.]+)→([\d.]+)~u', $l, $m)) {
                $bad[] = "$m[1] $m[2]→$m[3]";
            }
        }
    }
    return array_merge($bad, razmetkaPromahi($root, $dir, $p, $prof, $korp));
}

/** Бриф на правку: что мимо, на сколько и чего трогать нельзя. */
function brief(string $ishodnyy, string $htmlFile, array $promahi): string
{
    $prompt = (string) file_get_contents(preg_replace('~\.fix$~', '', $ishodnyy));
    $html = (string) file_get_contents($htmlFile);
    $spisok = '';
    foreach ($promahi as $m) { $spisok .= "  — $m\n"; }
    return <<<TXT
# Правка страницы

Ниже — текущий HTML и список полей, которые вышли за коридор. Перепиши те места,
где это исправляется СМЫСЛОМ: добавь или убери абзац, пункт, выделение,
заголовок, вопрос FAQ. Верни страницу целиком.

Чего делать нельзя:
  — менять слова на ключи заменой по строке: ломается падеж;
  — разносить абзац на два, если второй теряет отсылку к первому;
  — вставлять реплики и присказки в служебные строки («Ниже десять вопросов…»);
  — трогать то, что уже в норме.

## Мимо коридора
{$spisok}
## Исходное задание
{$prompt}

## Текущий HTML
{$html}
TXT;
}

/**
 * Промахи страницы по приёмке комплекта: и держимые поля, и разметка.
 *
 * Разметка живёт в межстраничном шлюзе, но чинить её надо на странице, пока
 * писатель ещё держит её в руках, — иначе правка приедет в самом конце, когда
 * возвращаться к тексту дороже.
 */
function razmetkaPromahi(string $root, string $dir, string $p, string $prof = '', string $korp = ''): array
{
    static $kesh = [];
    $klyuch = $dir . '|' . $prof . '|' . $korp;
    if (!isset($kesh[$klyuch])) {
        exec(sprintf('php %s/engine/priyomka-komplekt.php %s%s%s 2>&1',
            escapeshellarg($root), escapeshellarg($dir), $korp, $prof), $v);
        $kesh[$klyuch] = $v;
    }
    $bad = [];
    foreach ($kesh[$klyuch] as $l) {
        // строка параметров типа: «✗ slots 28/30 93% — поле a→b, поле c→d»
        if (preg_match('~^\s*✗\s+' . preg_quote($p, '~') . '\s+\d+/\d+\s+\d+%\s*—\s*(.+)$~u', $l, $m)) {
            foreach (explode(',', $m[1]) as $x) { $bad[] = trim($x); }
        }
        // строка разметки: «✗ slots · выделений 0 норма 5–18»
        if (preg_match('~^\s*✗\s+' . preg_quote($p, '~') . '\s+·\s+(.+?)\s{2,}(\S+)\s+норма\s+(\S+)~u', $l, $m)) {
            $bad[] = trim($m[1]) . ' ' . $m[2] . ' → норма ' . $m[3];
        }
    }
    return $bad;
}

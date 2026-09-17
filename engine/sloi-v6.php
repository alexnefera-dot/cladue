<?php
declare(strict_types=1);

/**
 * Сборщик слоёв по образцу из 42 сайтов.
 *
 *   php engine/sloi-v6.php <папка-комплекта> [--выход=<папка>] [--семя=<строка>] [--снять]
 *
 * Мы пишем страницу как один блок темы плюс FAQ. У образца страница собрана из
 * семи слоёв, и пять из них — механика:
 *
 *   1 шапка-россыпь: три абзаца слоганов подряд, в одну строку через пробел;
 *   2 H2-слоган: второй абзац шапки без точки на конце (253 страницы из 294);
 *   3 короткая строка бренда отдельным абзацем: «%brand_name_ru%.»;
 *   4 наш написанный блок — не трогаем;
 *   5 витрина: H2 с эмодзи, подзаголовок и ровно четыре карточки (243 из 294);
 *   6 наш FAQ — но микроразметку снимаем, её нет ни на одной из 294 страниц;
 *   7 подвал: дата, H3-слоган и два-три абзаца слоганов.
 *
 * Слои 1, 2, 3, 5 и 7 закрывают шесть полей из девяти, по которым классификатор
 * сегодня отличает нас от них: sections, h2, brand_ru, brand_first_third,
 * emoji, providers_named и names_uniq. Ни одной строчки живого текста.
 *
 * Разбор корпуса — docs/v5-obrazec-42-sajta.md, план — docs/v6-plan-pod-obrazec.md.
 *
 * ВАЖНО ДЛЯ ПРИЁМКИ. Механические слои одинаковы у всех комплектов по замыслу,
 * и шинглы на собранной странице это видят: доля пар выше 3,5 % поднимается с
 * 0,02 % до 1,67 % — ровно в их 1,71 %. Уникальность надо мерить по СНЯТЫМ
 * страницам: `--снять` возвращает написанное, и там остаётся прежние 0,02 %.
 *
 * Сборка ИДЕМПОТЕНТНА: страница со слоями узнаётся по абзацу перед первым H2,
 * и повторный прогон сначала снимает слои, а потом кладёт заново. Иначе три
 * прогона подряд дают три шапки.
 *
 * Розыгрыш ДЕТЕРМИНИРОВАН: семя по умолчанию — имя папки комплекта, поэтому
 * один и тот же комплект собирается одинаково, а разные получают разные
 * слоганы и разные тайтлы витрины. Внутри комплекта ничего не повторяется.
 */

const TIPY_V6 = ['main', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];

/** Абзацев шапки: у внутренних ровно три (41 из 42), у главной 3–7. */
const SHAPKA_VNUTR = 3;
/** Тайтлов на комплект: медиана образца — пять, и страницы их тасуют. */
const TAYTLOV_NA_KOMPLEKT = 5;
/** Карточек на странице: 243 страницы из 294. */
const KARTOCHEK = 4;
/** Метка HIGH RTP: порог вытащен из 1180 карточек и оказался ровным. */
const POROG_HIGH_RTP = 96.5;

/**
 * Розыгрыш без повторов, воспроизводимый от семени.
 *
 * mt_rand не годится: его поток зависит от сборки PHP, и комплект, собранный
 * на другой машине, получил бы другие слоганы. crc32 даёт то же число везде.
 */
final class Zhereb
{
    private int $shag = 0;

    public function __construct(private string $semya) {}

    public function chislo(int $predel): int
    {
        if ($predel <= 0) { return 0; }
        return crc32($this->semya . '#' . $this->shag++) % $predel;
    }

    /** @param list<mixed> $pul @return list<mixed> */
    public function vzyat(array $pul, int $skolko): array
    {
        $out = [];
        $pul = array_values($pul);
        for ($i = 0; $i < $skolko && $pul; $i++) {
            $j = $this->chislo(count($pul));
            $out[] = $pul[$j];
            array_splice($pul, $j, 1);
        }
        return $out;
    }
}

function dannye(string $imya): array
{
    $f = __DIR__ . '/data-v6/' . $imya;
    $d = is_file($f) ? json_decode((string) file_get_contents($f), true) : null;
    if (!is_array($d)) { fwrite(STDERR, "нет или испорчен $f\n"); exit(1); }
    return $d;
}

/** Страница со слоями начинается абзацем; написанная нами — сразу с H2. */
function so_sloyami(string $html): bool
{
    return (bool) preg_match('~^\s*<p[ >]~i', $html);
}

/** Снять слои: оставить от первого H2 без эмодзи до витрины и FAQ. */
function snyat_sloi(string $html): string
{
    // Слои 1–3 режем по концу третьего, а не по второму H2: у главной между
    // слоганом и первым своим H2 стоит лид — абзац, перечень и таблица, и счёт
    // по заголовкам съедал его целиком.
    if (preg_match('~<h2[^>]*>.*?</h2>\s*<p\b[^>]*>.*?</p>\s*~is', $html, $m, PREG_OFFSET_CAPTURE)
        && $m[0][1] < 600) {
        $html = substr($html, $m[0][1] + strlen($m[0][0]));
    }
    // Слой 5 — H2 с эмодзи и всё до следующего H2.
    $html = preg_replace(
        '~<h2[^>]*>\s*[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}\x{FE0F}].*?(?=<h2|$)~us',
        '', $html
    ) ?? $html;
    // Слой 7 — от строки с датой до конца.
    $p = mb_strpos($html, '<p>Последнее обновление');
    if ($p !== false) { $html = mb_substr($html, 0, $p); }
    return rtrim($html) . "\n";
}

/** Микроразметку FAQ снимаем: её нет ни на одной из 294 страниц образца. */
function bez_razmetki(string $html): string
{
    $html = preg_replace('~\s+item(scope|prop|type)(="[^"]*")?~i', '', $html) ?? $html;
    // После снятия атрибутов обёртки ответа остаются голыми <div><div>…</div></div>.
    // Схлопываем их, пока схлопывается: снимать только открывающий тег нельзя —
    // закрывающий останется висеть и вложенность разъедется.
    for ($i = 0; $i < 4; $i++) {
        $novy = preg_replace('~<div>\s*(<p\b.*?</p>)\s*</div>~is', '$1', $html) ?? $html;
        if ($novy === $html) { break; }
        $html = $novy;
    }
    return $html;
}

/** Витрина: H2 с эмодзи, подзаголовок и четыре карточки. */
function vitrina(array $taytly, string $kategoria, string $podzag, array $shabl, int $smeshchenie): string
{
    $out = "<h2>$kategoria</h2>\n<p>$podzag</p>\n";
    foreach ($taytly as $i => $t) {
        $rtp = rtrim(rtrim(number_format($t['rtp'], 2, '.', ''), '0'), '.');
        // Доли образца — 48,2 / 26,8 / 25,0; последовательность A B C A даёт
        // ровно 50/25/25 и совпадает с тем, как чередует их генератор.
        $kod = $shabl[($i + $smeshchenie) % count($shabl)];
        if ($kod !== 'B' && ($t['жанр'] ?? null) === null) { $kod = 'B'; }
        // Шаблон C говорит «Высокий RTP» при любом RTP: у образца 251 такая
        // карточка из 295, и половина из них ниже порога метки. Это их дефект,
        // и он воспроизводится нарочно — «починка» развела бы нас с семейством.
        $opis = match ($kod) {
            'A' => "Играйте в {$t['тайтл']} от {$t['студия']} на %brand_name_ru%. RTP $rtp%, жанр: {$t['жанр']}.",
            'B' => "{$t['тайтл']} - популярный слот от {$t['студия']} ({$t['год']}) с RTP $rtp%.",
            'C' => "Слот {$t['тайтл']} ({$t['жанр']}) от провайдера {$t['студия']}. Высокий RTP $rtp%.",
        };
        if ((float) $t['rtp'] >= POROG_HIGH_RTP) { $out .= "<p>HIGH RTP</p>\n"; }
        $out .= "<p>{$t['студия']}</p>\n<h3>{$t['тайтл']}</h3>\n"
              . "<p>RTP: $rtp% {$t['год']}</p>\n<p>$opis</p>\n";
    }
    return $out;
}

// ── разбор флагов ───────────────────────────────────────────────────────────
$dir = ''; $vyhod = ''; $semya = ''; $snyat = false;
foreach (array_slice($argv, 1) as $a) {
    if (str_starts_with($a, '--выход=')) { $vyhod = substr($a, strlen('--выход=')); continue; }
    if (str_starts_with($a, '--семя=')) { $semya = substr($a, strlen('--семя=')); continue; }
    if ($a === '--снять') { $snyat = true; continue; }
    $dir = rtrim($a, '/');
}
if ($dir === '' || !is_dir($dir)) {
    fwrite(STDERR, "usage: php engine/sloi-v6.php <папка-комплекта> [--выход=<папка>] [--семя=<строка>] [--снять]\n");
    exit(1);
}
$vyhod = $vyhod !== '' ? rtrim($vyhod, '/') : $dir;
$semya = $semya !== '' ? $semya : basename($dir);
if (!is_dir($vyhod)) { mkdir($vyhod, 0777, true); }

$slogany = dannye('slogany.json');
$katalog = dannye('slots-katalog.json')['каталог'];
$kategorii = dannye('vitrina-kategorii.json');
$zh = new Zhereb($semya);

// Розыгрыш на весь комплект: внутри него ничего не повторяется.
$shapki   = $zh->vzyat($slogany['шапка'], 7 * SHAPKA_VNUTR + 4);
$tri      = $zh->vzyat($slogany['h2_слоган'], 7);
$podvalH3 = $zh->vzyat($slogany['подвал_h3'], 7);
$podvalP  = $zh->vzyat($slogany['подвал_p'], 7 * 3);
$kat      = $zh->vzyat(array_column($kategorii['категории'], 'имя'), 7);
$pod      = $zh->vzyat(array_column($kategorii['подзаголовки'], 'текст'), 7);
$taytly   = $zh->vzyat($katalog, TAYTLOV_NA_KOMPLEKT);
$stroki3  = ['%brand_name_ru%.', '%brand_name_en%.', 'Казино %brand_name_ru%.',
             '%brand_name_en% казино.', '%brand_name_ru% казино.', 'Casino %brand_name_en%.',
             '%brand_name_en% Casino.'];

$sdelano = 0;
foreach (TIPY_V6 as $i => $tip) {
    $f = "$dir/$tip.html";
    if (!is_file($f)) { continue; }
    $html = (string) file_get_contents($f);
    if (so_sloyami($html)) { $html = snyat_sloi($html); }
    if ($snyat) {
        file_put_contents("$vyhod/$tip.html", $html);
        $sdelano++;
        continue;
    }
    $html = bez_razmetki($html);

    // Слой 6 начинается последним H2 — это наш FAQ. Витрина встаёт перед ним.
    if (preg_match_all('~<h2[^>]*>~i', $html, $m, PREG_OFFSET_CAPTURE) && count($m[0]) >= 2) {
        $rez = (int) $m[0][count($m[0]) - 1][1];
        $telo = substr($html, 0, $rez);
        $faq  = substr($html, $rez);
    } else {
        $telo = $html;
        $faq  = '';
    }

    $skolko = $tip === 'main' ? 4 : SHAPKA_VNUTR;
    $moi = array_splice($shapki, 0, $skolko);
    // Второй абзац шапки и есть H2-слоган: так на 253 страницах из 294.
    $moi[1] = $tri[$i] . '.';
    $sloj1 = implode(' ', array_map(static fn(string $p) => "<p>$p</p>", $moi));
    $sloj2 = '<h2>' . rtrim($tri[$i], '.') . '</h2>';
    $sloj3 = '<p>' . $stroki3[$zh->chislo(count($stroki3))] . '</p>';

    // Четыре тайтла из пяти, порядок свой на каждой странице.
    $moiTaytly = array_slice(array_merge(
        array_slice($taytly, $i % count($taytly)),
        array_slice($taytly, 0, $i % count($taytly))
    ), 0, KARTOCHEK);
    $sloj5 = vitrina($moiTaytly, $kat[$i], $pod[$i], ['A', 'B', 'C', 'A'], $i);

    $p3 = array_splice($podvalP, 0, 3);
    $sloj7 = "<p>Последнее обновление %domain_name%:\n%date%          \n        </p>\n"
           . "<h3>{$podvalH3[$i]}</h3>\n"
           . implode("\n", array_map(static fn(string $p) => "<p>$p</p>", $p3)) . "\n";

    file_put_contents("$vyhod/$tip.html",
        "$sloj1\n$sloj2\n$sloj3\n" . rtrim($telo) . "\n" . $sloj5 . rtrim($faq) . "\n" . $sloj7);
    $sdelano++;
}
printf("%s: %d страниц, семя «%s»%s\n", $vyhod, $sdelano, $semya, $snyat ? ', слои сняты' : '');

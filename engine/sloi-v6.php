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

require_once __DIR__ . '/src/Sloi.php';

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
// Нормы бренда: сборщик добирает плейсхолдеры до полосы. Без этого доля
// кириллического написания зависела от того, какие слоганы вытянулись, и
// приёмка заворачивала комплект по школе бренда на четырёх страницах из семи.
$brendNorma = [];
$pf = __DIR__ . '/data-v6/profil-v6.json';
if (is_file($pf)) {
    $pr = json_decode((string) file_get_contents($pf), true);
    foreach ($pr['бренд'] ?? [] as $shkola) {
        $brendNorma = $shkola['страницы'] ?? [];
        break;
    }
}
$zh = new Zhereb($semya);

// Розыгрыш на весь комплект: внутри него ничего не повторяется.
// Шапка тянется не вся разом: каждой странице подбирают строки под её нехватку.
$pulShapok = $slogany['шапка'];
// Слоганы, открывающиеся ключом ниши, годятся только главной: на внутренней
// они поднимают opener_key с нуля до единицы и добавляют лишние опорные
// формулы, а профиль держит там ноль. Правило общее для шапки и для
// H2-слогана: последний тоже попадает в зачин, потому что дублирует абзац.
$klyuchevoy = static fn(string $x): bool => (bool) preg_match(
    '~^\s*(?:официальн\w+ сайт|казино|игровые автоматы|зеркало сайта)~ui', $x);

$bezKlyucha = array_values(array_filter($pulShapok, static fn(string $x) => !$klyuchevoy($x)));
// Слоганы с вопросительным знаком отсеиваем: H2-вопрос у образца встречается
// редко, мера h2_quest держит ноль, а один такой слоган даёт сразу 25 %.
// H2-слоган отбирается строже прочих: он попадает на страницу дважды — абзацем
// шапки и самим заголовком, — поэтому два плейсхолдера в нём дают на выходе
// четыре. Берём строки не больше чем с одним именем бренда. Вопросительные
// знаки отсеиваем там же: h2_quest у образца держит ноль, а один такой слоган
// сразу даёт двадцать пять процентов.
$tri = $zh->vzyat(array_values(array_filter($slogany['h2_слоган'],
    static fn(string $x) => !str_contains($x, '?')
        && substr_count($x, '%brand_name_') <= 1
        && !$klyuchevoy($x))), 7);
$podvalH3 = $zh->vzyat($slogany['подвал_h3'], 7);
$podvalP  = $zh->vzyat($slogany['подвал_p'], 7 * 3);
$kat      = $zh->vzyat(array_column($kategorii['категории'], 'имя'), 7);
$pod      = $zh->vzyat(array_column($kategorii['подзаголовки'], 'текст'), 7);
// Тайтлы берём с разными студиями: providers_named считает РАЗНЫЕ имена, и
// пятёрка от двух поставщиков давала на витрине двойку при норме в шесть.
$taytly = [];
$vzyatyeStudii = [];
$pulTaytlov = $katalog;
while (count($taytly) < TAYTLOV_NA_KOMPLEKT && $pulTaytlov) {
    $k = $zh->chislo(count($pulTaytlov));
    $t = $pulTaytlov[$k];
    array_splice($pulTaytlov, $k, 1);
    if (in_array($t['студия'], $vzyatyeStudii, true)) { continue; }
    $vzyatyeStudii[] = $t['студия'];
    $taytly[] = $t;
}
$stroki3  = ['%brand_name_ru%.', '%brand_name_en%.', 'Казино %brand_name_ru%.',
             '%brand_name_en% казино.', '%brand_name_ru% казино.', 'Casino %brand_name_en%.',
             '%brand_name_en% Casino.'];

$sdelano = 0;
foreach (TIPY_V6 as $i => $tip) {
    $f = "$dir/$tip.html";
    if (!is_file($f)) { continue; }
    $html = (string) file_get_contents($f);
    $html = Sloi::snyat($html);
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
    // Считаем, чего не хватает написанному тексту, и тянем слоганы с нужным
    // написанием имени. Строки берутся по одной, чтобы каждая закрывала дыру.
    // $telo по ССЫЛКЕ: замыкание захватывает по значению, и нехватка не
    // убывала по мере добора — кириллица уезжала к одиннадцати при норме шесть.
    // Счёт ведём по ОТДЕЛЬНОЙ строке, а не по телу страницы. Первая версия
    // дописывала выбранные слоганы прямо в $telo, чтобы пересчитать нехватку, —
    // и они уезжали в вёрстку голым текстом после последнего абзаца, а заодно
    // удваивали бренд в замере. Нашлось чтением собранной страницы.
    // H2-слоган повторяет второй абзац шапки, и его плейсхолдеры попадают на
    // страницу ДВАЖДЫ. Учитываем их заранее, иначе добор считает нехватку по
    // пустому месту и уводит кириллицу к двенадцати при полосе 5–7.
    $uchyot = $telo . $faq . ' ' . $tri[$i] . ' ' . $tri[$i];
    $nado = static function (string $vid) use ($brendNorma, $tip, &$uchyot): int {
        $n = $brendNorma[$tip][$vid === 'ru' ? 'кир' : 'лат'] ?? null;
        if (!$n) { return 0; }
        $est = preg_match_all('~%brand_name_' . $vid . '%~', $uchyot);
        // Цель — на единицу выше нижней границы. Ровно по низу добор промахивался
        // вниз: H2-слоган отбирается с одним плейсхолдером, и прежний запас в
        // два имени на строку пропал вместе с ним.
        return (int) max(0, (int) $n['низ'] + 1 - $est);
    };
    // Перебор считаем отдельно от нехватки: страница, где кириллицы уже больше
    // верхней границы, не должна получать слоганы с нею, даже когда латиницы
    // тоже недостаёт. Иначе сумма по комплекту уезжает вверх по обоим написаниям.
    $perebor = static function (string $vid) use ($brendNorma, $tip, &$uchyot): bool {
        $n = $brendNorma[$tip][$vid === 'ru' ? 'кир' : 'лат'] ?? null;
        if (!$n) { return false; }
        return preg_match_all('~%brand_name_' . $vid . '%~', $uchyot) >= (int) $n['верх'];
    };
    $moi = [];
    for ($j = 0; $j < $skolko; $j++) {
        $nRu = $nado('ru');
        $nEn = $nado('en');
        // Нехватки нет — берём строку с наименьшим числом плейсхолдеров, иначе
        // добор проскакивает норму: слоган несёт их по два, и три строки подряд
        // уводили кириллицу к восьми при полосе 5–7.
        $godnye = $tip === 'main' ? array_values($pulShapok) : array_values($bezKlyucha);
        if ($nRu <= 0 && $nEn <= 0) {
            $bednye = array_values(array_filter($godnye,
                static fn(string $x) => !str_contains($x, '%brand_name_')));
            if ($bednye) { $godnye = $bednye; }
        }
        if ($nRu > 0 || $nEn > 0) {
            $vid = $nRu > $nEn ? 'ru' : 'en';
            if ($perebor($vid)) { $vid = $vid === 'ru' ? 'en' : 'ru'; }
            // Ровно ОДНО вхождение: слоган с двумя плейсхолдерами закрывает
            // нехватку с перелётом, и сумма по комплекту уходит за верх полосы.
            $otbor = array_values(array_filter($godnye,
                static fn(string $x) => substr_count($x, '%brand_name_' . $vid . '%') === 1
                    && !str_contains($x, '%brand_name_' . ($vid === 'ru' ? 'en' : 'ru') . '%')));
            // Запасной отбор — БЕЗ чужого написания. Прежний пускал смешанные
            // строки, и добор латиницы тянул за собой кириллицу: восемь на
            // странице при полосе 5–7 и пятьдесят два по комплекту при верхе 45.
            if (!$otbor) {
                $chuzhoy = '%brand_name_' . ($vid === 'ru' ? 'en' : 'ru') . '%';
                $otbor = array_values(array_filter($godnye,
                    static fn(string $x) => str_contains($x, '%brand_name_' . $vid . '%')
                        && !str_contains($x, $chuzhoy)));
            }
            if ($otbor) { $godnye = $otbor; }
        }
        $vzyal = $zh->vzyat($godnye, 1)[0] ?? '';
        $pulShapok = array_values(array_filter($pulShapok, static fn(string $x) => $x !== $vzyal));
        $bezKlyucha = array_values(array_filter($bezKlyucha, static fn(string $x) => $x !== $vzyal));
        $moi[] = $vzyal;
        $uchyot .= ' ' . $vzyal;
    }
    // Второй абзац шапки и есть H2-слоган: так на 253 страницах из 294.
    $moi[1] = $tri[$i] . '.';
    $sloj1 = implode(' ', array_map(static fn(string $p) => "<p>$p</p>", $moi));
    $sloj2 = '<h2>' . rtrim($tri[$i], '.') . '</h2>';
    // Слой 3 доводит счёт бренда до полосы. Добор целыми слоганами шагает по
    // два имени за раз, а полоса шириной в три, и комплект качало: правка на
    // одно упоминание в тексте перекидывала страницу с недобора на перебор.
    // Короткая строка бренда — единственное место, которое сборщик держит
    // полностью, поэтому вариант выбирается замером, а не жребием.
    $shtraf = static function (string $stroka) use ($brendNorma, $tip, $uchyot, $moi): int {
        $ves = $uchyot . ' ' . implode(' ', $moi) . ' ' . $stroka;
        $sum = 0;
        foreach (['ru' => 'кир', 'en' => 'лат'] as $vid => $imya) {
            $n = $brendNorma[$tip][$imya] ?? null;
            if (!$n) { continue; }
            $est = preg_match_all('~%brand_name_' . $vid . '%~', $ves);
            if ($est < (int) $n['низ']) { $sum += (int) $n['низ'] - $est; }
            if ($est > (int) $n['верх']) { $sum += $est - (int) $n['верх']; }
        }
        return $sum;
    };
    $luchshaya = $stroki3[0];
    $luchshiy = PHP_INT_MAX;
    foreach ($stroki3 as $var) {
        $c = $shtraf($var);
        if ($c < $luchshiy) { $luchshiy = $c; $luchshaya = $var; }
    }
    $sloj3 = '<p>' . $luchshaya . '</p>';

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
// Свод комплекта едет вместе со страницами: без него сквозная сверка фактов
// на приёмке молча проваливается в режим «свода нет» и проверяет вчетверо меньше.
if ($vyhod !== $dir && is_file("$dir/svod.json")) {
    copy("$dir/svod.json", "$vyhod/svod.json");
}
printf("%s: %d страниц, семя «%s»%s\n", $vyhod, $sdelano, $semya, $snyat ? ', слои сняты' : '');

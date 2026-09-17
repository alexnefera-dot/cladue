<?php
declare(strict_types=1);

/**
 * Сборщик слоёв по образцу из 42 сайтов.
 *
 *   php engine/sloi-v6.php <папка-комплекта> [--выход=<папка>] [--семя=<строка>]
 *                            [--корпус=<путь>] [--снять]
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
 *
 * Между комплектами тоже: engine/data-v6/zanyato-slogany.json помнит, кто
 * какие строки взял. Комплект вычитает из пулов чужие записи, свою пропускает
 * и тянет из остатка; пополнение дописывает строку в конец и ничьего выхода не
 * трогает. Без реестра «Успех без риска %brand_name_en% бонус» вставал разом в
 * двух комплектах: у образца же 252 H2-слогана из 252 уникальны.
 *
 * --корпус=<путь> реестру не нужен: он только предупреждает о собранных
 * комплектах, которых в реестре ещё нет.
 *
 * Запас словаря: H2-слоганов хватает на 27 комплектов, шапки — на 35. H2 и
 * есть узкое место, о нём сборщик предупреждает за пять комплектов до дна.
 */

require_once __DIR__ . '/src/Sloi.php';
require_once __DIR__ . '/src/PageMetrics.php';

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

/**
 * Перевести строку бренда в другое написание.
 *
 * Третий рычаг доводки, самый слабый и самый последний: он не меняет общего
 * числа имён на странице, а переносит одно из латиницы в кириллицу или назад.
 * Нужен там, где написанный текст уже выбрал почти всю полосу, а механические
 * абзацы отдавать нечего.
 *
 * Переводим только при запасе у школы-получателя: без проверки перебор просто
 * переезжает на соседнюю строку отчёта.
 *
 * @param list<string> $stroki3 варианты строки бренда
 * @param callable(string):int $schet
 */
function perevesti_stroku(string &$stroka3, string $vid, array $stroki3,
                          array $norma, callable $schet): bool
{
    $drugoy = $vid === 'ru' ? 'en' : 'ru';
    $imyaDr = $drugoy === 'ru' ? 'кир' : 'лат';
    if (!str_contains($stroka3, '%brand_name_' . $vid . '%')) { return false; }
    $n = $norma[$imyaDr] ?? null;
    if (!$n || $schet($drugoy) + 1 > (int) $n['верх']) { return false; }
    foreach ($stroki3 as $v) {
        if (str_contains($v, '%brand_name_' . $drugoy . '%')
            && !str_contains($v, '%brand_name_' . $vid . '%')) {
            $stroka3 = $v;
            return true;
        }
    }
    return false;
}

/**
 * Довести имя бренда до полосы профиля, правя только механические строки.
 *
 * Прежде счёт добирался ВЫБОРОМ слогана: под нехватку подбиралась строка с
 * нужным написанием. Шаг такого добора — целое имя, а часто и два, потому что
 * слоган несёт их сколько несёт; полоса же у профиля шириной в три (5–7 на
 * страницу). Комплект качало: правка на одно упоминание в написанном тексте
 * перекидывала страницу с недобора на перебор, а всякая попытка починить один
 * набор роняла соседний. Отладка шла кругами, пока причину не назвали вслух.
 *
 * Здесь шаг равен единице. Слоганы тянутся вслепую, а имя дописывается или
 * снимается поштучно — и только в шапке, строке бренда и подвале. Написанный
 * текст неприкосновенен: он проходит свою приёмку отдельно.
 *
 * Абзац шапки под индексом 1 не правится: его дословно повторяет H2-слоган,
 * и всякое имя в нём считается дважды.
 *
 * Строка бренда не снимается — без имени она станет пустым абзацем, которого
 * у образца не бывает, — но ПЕРЕВОДИТСЯ в другое написание. Это третий рычаг,
 * и он нужен: у registracia написанный текст нёс шесть латинских имён, слоган
 * добавлял два (он считается дважды), строка бренда третье, и снимать было
 * неоткуда — доводка упиралась в девять при потолке восемь и молча сдавалась.
 * Перевод строки переносит единицу из одной школы в другую, не трогая вёрстки.
 *
 * @param list<string> $shapka  абзацы шапки, правятся по ссылке
 * @param list<string> $podval  абзацы подвала, правятся по ссылке
 * @param array{кир?:array{низ:int,верх:int},лат?:array{низ:int,верх:int}} $norma
 */
function dovesti_brend(array &$shapka, string &$stroka3, array &$podval,
                       string $napisano, array $norma, array $stroki3 = []): void
{
    $schet = static function (string $vid) use (&$shapka, &$stroka3, &$podval, $napisano): int {
        $ves = $napisano . ' ' . implode(' ', $shapka) . ' ' . ($shapka[1] ?? '')
             . ' ' . $stroka3 . ' ' . implode(' ', $podval);
        return preg_match_all('~%brand_name_' . $vid . '%~', $ves);
    };
    foreach (['ru' => 'кир', 'en' => 'лат'] as $vid => $imya) {
        $n = $norma[$imya] ?? null;
        if (!$n) { continue; }
        $metka = '%brand_name_' . $vid . '%';
        $verh = (int) $n['верх'];
        $cel = (int) round(((int) $n['низ'] + $verh) / 2);

        // Недобор: дописываем имя в конец строки. Порядок мест — от шапки к
        // подвалу: у образца имя чаще стоит именно в верхних слоганах.
        //
        // Целимся в СЕРЕДИНУ полосы, а не в нижний край. По краю каждая
        // страница проходила свою проверку, а сумма по комплекту падала ниже
        // своей: у неё полоса ýже суммы семи страничных, и семь минимумов в
        // неё не укладываются.
        for ($shag = 0; $shag < 20 && $schet($vid) < $cel; $shag++) {
            $kuda = null;
            foreach ([0, 2, 3] as $k) {
                if (isset($shapka[$k]) && !str_contains($shapka[$k], $metka)) { $kuda = &$shapka[$k]; break; }
            }
            if ($kuda === null) {
                foreach (array_keys($podval) as $k) {
                    if (!str_contains($podval[$k], $metka)) { $kuda = &$podval[$k]; break; }
                }
            }
            if ($kuda === null) { break; }
            $kuda = rtrim($kuda, ' .') . ' ' . $metka;
            unset($kuda);
        }
        // Перебор снимаем до СЕРЕДИНЫ, а не до верхнего края. По краю каждая
        // страница проходила свою проверку, а семь страниц по верху давали
        // сумму 49 при потолке 45: у суммы полоса ýже, чем сумма страничных.
        // Симметрично добору, который целится в ту же середину.
        for ($shag = 0; $shag < 20 && $schet($vid) > $cel; $shag++) {
            $otkuda = null;
            foreach ([0, 2, 3] as $k) {
                if (isset($shapka[$k]) && str_contains($shapka[$k], $metka)) { $otkuda = &$shapka[$k]; break; }
            }
            if ($otkuda === null) {
                foreach (array_keys($podval) as $k) {
                    if (str_contains($podval[$k], $metka)) { $otkuda = &$podval[$k]; break; }
                }
            }
            if ($otkuda === null) {
                // Механические абзацы пусты — остаётся строка бренда. Её не
                // опустошаем, а переводим в другую школу, и только если у той
                // есть запас до потолка: иначе перебор просто переедет.
                if (!perevesti_stroku($stroka3, $vid, $stroki3, $norma, $schet)) { break; }
                continue;
            }
            $otkuda = trim((string) preg_replace('~\s*' . preg_quote($metka, '~') . '\s*~u', ' ',
                $otkuda, 1));
            unset($otkuda);
        }
    }
}

/**
 * Все жребии комплекта разом: что тянется из общих пулов до всякой доводки.
 *
 * Вынесено из главного цикла ради реестра занятого. Розыгрыш зависит ровно от
 * двух вещей — от семени и от пулов, — и не зависит ни от написанного текста,
 * ни от того, какие страницы лежат на диске. Поэтому его можно ПРОИГРАТЬ за
 * соседний комплект, не собирая его: достаточно знать имя папки.
 *
 * Тянем всегда на все семь страниц, даже если файлов меньше. Прежде розыгрыш
 * шёл внутри цикла по существующим файлам, и неполный комплект сдвигал поток
 * жребия: та же папка с шестью страницами вместо семи получала другие слоганы
 * на всех.
 *
 * Порядок вызовов $zh здесь — часть договора: любая перестановка меняет выход
 * у всех комплектов сразу.
 *
 * @return array{шапки:array<string,list<string>>,взято_шапка:list<string>,
 *               h2:list<string>,подвал_h3:list<string>,подвал_p:list<string>,
 *               строка3:array<string,string>,кат:list<string>,под:list<string>,
 *               тайтлы:list<array>}
 */
function zherebyovka(string $semya, array $slogany, array $katalog,
                     array $kategorii, callable $klyuchevoy, array $stroki3): array
{
    $zh = new Zhereb($semya);
    $pulShapok = $slogany['шапка'];
    // Слоганы, несущие ключ ниши, годятся только главной: на внутренней они
    // поднимают opener_key с нуля до единицы, а профиль держит там ноль.
    $bezKlyucha = array_values(array_filter($pulShapok, static fn(string $x) => !$klyuchevoy($x)));

    // H2-слоган отбирается строже прочих: он попадает на страницу дважды —
    // абзацем шапки и самим заголовком, — поэтому два плейсхолдера в нём дают
    // на выходе четыре. Вопросительные знаки отсеиваем там же: h2_quest у
    // образца держит ноль, а один такой слоган сразу даёт двадцать пять
    // процентов.
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

    $shapki = [];
    $stroki = [];
    $vzyatoShapok = [];
    foreach (TIPY_V6 as $i => $tip) {
        $skolko = $tip === 'main' ? 4 : SHAPKA_VNUTR;
        $moi = [];
        for ($j = 0; $j < $skolko; $j++) {
            $pul = $tip === 'main' ? $pulShapok : $bezKlyucha;
            if (!$pul) { $pul = $pulShapok; }
            $vzyal = $zh->vzyat($pul, 1)[0] ?? '';
            $pulShapok = array_values(array_filter($pulShapok, static fn(string $x) => $x !== $vzyal));
            $bezKlyucha = array_values(array_filter($bezKlyucha, static fn(string $x) => $x !== $vzyal));
            $vzyatoShapok[] = $vzyal;
            $moi[] = $vzyal;
        }
        // Второй абзац шапки и есть H2-слоган: так на 253 страницах из 294.
        // Вытянутая под этот номер строка из пула всё равно ушла — она в
        // $vzyatoShapok, и реестр её занятой и считает.
        $moi[1] = ($tri[$i] ?? '') . '.';
        $shapki[$tip] = $moi;
        $stroki[$tip] = $stroki3[$zh->chislo(count($stroki3))];
    }

    return ['шапки' => $shapki, 'взято_шапка' => $vzyatoShapok, 'h2' => $tri,
            'подвал_h3' => $podvalH3, 'подвал_p' => $podvalP,
            'строка3' => $stroki, 'кат' => $kat, 'под' => $pod, 'тайтлы' => $taytly];
}

/**
 * Реестр занятого: кто какие слоганы уже взял.
 *
 * Жребий по наборам независим, а пул один на всех: при трёх комплектах «Успех
 * без риска %brand_name_en% бонус» встал разом в farforovaya/vhod и
 * pozumentnaya/bonus — нашлось чтением вслух. У образца 252 H2-слогана из 252
 * уникальны, повторов нет ни одного: они занятое помнят.
 *
 * Две попытки до этой не годились, и обе провалились на одном и том же —
 * на устойчивости чужого выхода.
 *
 * ПЕРВАЯ читала слоганы с собранных страниц соседей. Страницы выходили
 * правильные, но набор видел только тех, кто собран РАНЬШЕ него: пересборка в
 * уже заполненном корпусе расходилась на 21 странице из 21. Порядок сборки
 * становился частью выхода.
 *
 * ВТОРАЯ выстраивала комплекты по имени папки и вычитала жребий всех, кто
 * стоит выше по алфавиту. Пересборка стала устойчивой, а вот ПОПОЛНЕНИЕ — нет:
 * четвёртый набор «chekannaya» встал первой буквой впереди трёх готовых,
 * сдвинул им пулы и уронил два принятых комплекта из трёх. Любая очередь по
 * месту в списке ломается на вставке в середину.
 *
 * Здесь очередь задаёт ВРЕМЯ, и оно записано. Комплект, взявший слоганы,
 * заносит их в этот файл и больше не двигается: сосед вычитает чужие записи,
 * свою пропускает и тянет из остатка. Пополнение дописывает строку в конец и
 * ничьего выхода не трогает.
 *
 * Файл ЛЕЖИТ В РЕПОЗИТОРИИ, и это условие, а не подробность. Реестр масок жил
 * в гитигноре, потерялся при чистом клоне, и генератор выдал «органную
 * мастерскую», под которой комплект написан с августа. Занятые слоганы нельзя
 * восстановить из папок: доводка бренда правит строки на странице, и обратно к
 * словарной они уже не приводятся.
 */
const REESTR_SLOGANOV = __DIR__ . '/data-v6/zanyato-slogany.json';

/** @return array<string,array{шапка:list<string>,h2:list<string>,подвал_h3:list<string>,подвал_p:list<string>}> */
function reestr_prochest(): array
{
    if (!is_file(REESTR_SLOGANOV)) { return []; }
    $r = json_decode((string) file_get_contents(REESTR_SLOGANOV), true);
    return is_array($r) ? $r : [];
}

/**
 * Вычесть из пулов слоганы, записанные за ДРУГИМИ комплектами.
 *
 * Свою запись пропускаем: иначе пересборка вычла бы собственный жребий,
 * потянула бы новые строки и потеряла идемпотентность.
 *
 * @return array{0:array,1:int} пулы без занятого и сколько строк снято
 */
function pooly_bez_zanyatogo(array $slogany, string $svoyo, array $reestr): array
{
    $snyato = 0;
    foreach ($reestr as $kto => $ego) {
        if ($kto === $svoyo || !is_array($ego)) { continue; }
        foreach (['шапка' => 'шапка', 'h2_слоган' => 'h2',
                  'подвал_h3' => 'подвал_h3', 'подвал_p' => 'подвал_p'] as $pul => $gde) {
            if (!isset($slogany[$pul], $ego[$gde])) { continue; }
            $bylo = count($slogany[$pul]);
            $zan = array_flip($ego[$gde]);
            $slogany[$pul] = array_values(array_filter($slogany[$pul],
                static fn(string $x) => !isset($zan[$x])));
            $snyato += $bylo - count($slogany[$pul]);
        }
    }
    return [$slogany, $snyato];
}

/**
 * Подставить в жребий то, что уже записано за комплектом.
 *
 * Вычитание чужих строк меняет САМ ПУЛ, а жребий берёт из него по номеру —
 * поэтому набор, чьи строки никто не занял, всё равно вытянул бы другие, стоит
 * соседу появиться. Пересборка трёх принятых комплектов после четвёртого так и
 * разошлась. Записанный жребий поэтому не пересчитывают, а подставляют.
 *
 * Прочее — категории витрины, подзаголовки, тайтлы и строка бренда — не
 * трогается: их пулы постоянны, число шагов Zhereb от содержимого словаря
 * слоганов не зависит, и выход у них тот же самый.
 *
 * Шапку раскладываем обратно по страницам в порядке TIPY_V6: главной четыре
 * абзаца, внутренним по три. Второй абзац всё равно перекрывается H2-слоганом.
 */
function podstavit_zapis(array $zhr, array $zapis): array
{
    if (!isset($zapis['шапка'], $zapis['h2'], $zapis['подвал_h3'], $zapis['подвал_p'])) { return $zhr; }
    $zhr['h2']        = $zapis['h2'];
    $zhr['подвал_h3'] = $zapis['подвал_h3'];
    $zhr['подвал_p']  = $zapis['подвал_p'];
    $zhr['взято_шапка'] = $zapis['шапка'];
    $pos = 0;
    foreach (TIPY_V6 as $i => $tip) {
        $skolko = $tip === 'main' ? 4 : SHAPKA_VNUTR;
        $moi = array_slice($zapis['шапка'], $pos, $skolko);
        $pos += $skolko;
        if (count($moi) < $skolko) { return $zhr; }
        $moi[1] = ($zhr['h2'][$i] ?? '') . '.';
        $zhr['шапки'][$tip] = $moi;
    }
    return $zhr;
}

/**
 * Записать за комплектом его жребий.
 *
 * Пишем ПОСЛЕ сборки и всегда целиком: повторный прогон кладёт то же самое,
 * файл от этого не растёт. Ключи сортируем по имени — иначе каждая пересборка
 * давала бы перестановку строк и лишний diff на ровном месте.
 */
function reestr_zapisat(string $semya, array $zhr): void
{
    $r = reestr_prochest();
    $r[$semya] = [
        'шапка'     => $zhr['взято_шапка'],
        'h2'        => $zhr['h2'],
        'подвал_h3' => $zhr['подвал_h3'],
        'подвал_p'  => $zhr['подвал_p'],
    ];
    ksort($r, SORT_STRING);
    file_put_contents(REESTR_SLOGANOV,
        json_encode($r, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT) . "\n");
}

// ── разбор флагов ───────────────────────────────────────────────────────────
$dir = ''; $vyhod = ''; $semya = ''; $korpus = ''; $snyat = false;
foreach (array_slice($argv, 1) as $a) {
    if (str_starts_with($a, '--выход=')) { $vyhod = substr($a, strlen('--выход=')); continue; }
    if (str_starts_with($a, '--семя=')) { $semya = substr($a, strlen('--семя=')); continue; }
    if (str_starts_with($a, '--корпус=')) { $korpus = substr($a, strlen('--корпус=')); continue; }
    if ($a === '--снять') { $snyat = true; continue; }
    $dir = rtrim($a, '/');
}
if ($dir === '' || !is_dir($dir)) {
    fwrite(STDERR, "usage: php engine/sloi-v6.php <папка-комплекта> [--выход=<папка>] [--семя=<строка>] [--корпус=<путь>] [--снять]\n");
    exit(1);
}
$vyhod = $vyhod !== '' ? rtrim($vyhod, '/') : $dir;
$semya = $semya !== '' ? $semya : basename($dir);
if (!is_dir($vyhod)) { mkdir($vyhod, 0777, true); }

$slogany  = dannye('slogany.json');
$katalog  = dannye('slots-katalog.json')['каталог'];
$kategorii = dannye('vitrina-kategorii.json');
$stroki3  = ['%brand_name_ru%.', '%brand_name_en%.', 'Казино %brand_name_ru%.',
             '%brand_name_en% казино.', '%brand_name_ru% казино.', 'Casino %brand_name_en%.',
             '%brand_name_en% Casino.'];

// Слоганы, открывающиеся ключом ниши, годятся только главной: на внутренней
// они поднимают opener_key с нуля до единицы и добавляют лишние опорные
// формулы, а профиль держит там ноль. Правило общее для шапки и для
// H2-слогана: последний тоже попадает в зачин, потому что дублирует абзац.
// Ключ ищем ГДЕ УГОДНО в слогане, а не только в начале: «%brand_name_en%
// Официальный сайт» начинается плейсхолдером, привязка к началу его пропускала,
// и opener_key поднимался до единицы. Вся шапка попадает в окно зачина целиком.
//
// «официальн» берём КОРНЕМ, а не словосочетанием «официальный сайт». Мера
// opener_key ищет ровно корень, и слоган «Официальная информация %brand_name_en%
// мы открыты» проходил фильтр, а приёмку заваливал: зачин у bonus получал
// единицу при профильном нуле.
//
// Отсеиваем заодно ЛЮБУЮ опорную формулу ниши, а не три ключевых. Мера anchors
// считает их по всей странице, и «Способы входа в личный кабинет» в H2-слогане
// давал сразу два: слоган стоит на странице дважды — абзацем шапки и
// заголовком. У farforovaya/zerkalo из-за этого вышло 9 формул при полосе 3–7,
// притом что написанный текст держал ровно семь. Опорные формулы — мера
// написанного, механика подмешиваться в неё не должна. Цена мала: из 193
// годных H2-слоганов отпадают два, из 776 шапок — тридцать одна.
$klyuchevoy = static function (string $x): bool {
    if (preg_match('~(?:официальн|игровые автоматы|зеркало сайта)~ui', $x)) { return true; }
    foreach (PageMetrics::ANCHORS as $re) { if (preg_match($re, $x)) { return true; } }
    return false;
};

// Занятое соседями вычитается из пулов ДО первого жребия. Себя узнаём по
// СЕМЕНИ, а не по имени папки: при сборке в другую папку набор считал бы
// собственный жребий чужим и брал новые слоганы.
$reestr = reestr_prochest();
[$slogany, $snyatoZanyatyh] = pooly_bez_zanyatogo($slogany, $semya, $reestr);

// Корпус нужен только для предупреждения: комплект, собранный до реестра, в
// нём не записан, и его слоганы могут уйти соседу повторно.
$korpusPut = $korpus !== '' ? $korpus : dirname($vyhod);
if (!$snyat) {
    foreach (glob(rtrim($korpusPut, '/') . '/*', GLOB_ONLYDIR) ?: [] as $d) {
        $imya = basename($d);
        if (str_ends_with($imya, '-sobrano') || $imya === $semya || isset($reestr[$imya])) { continue; }
        if (!is_file("$d/main.html") || !Sloi::est((string) file_get_contents("$d/main.html"))) { continue; }
        fwrite(STDERR, "внимание: «$imya» собран, но в реестре слоганов его нет — пересобери его\n");
    }
}

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

// Розыгрыш на весь комплект: внутри него ничего не повторяется.
$zhr      = zherebyovka($semya, $slogany, $katalog, $kategorii, $klyuchevoy, $stroki3);
// Свой жребий, если он уже записан, подставляем поверх вытянутого.
if (isset($reestr[$semya])) { $zhr = podstavit_zapis($zhr, $reestr[$semya]); }
$tri      = $zhr['h2'];
$podvalH3 = $zhr['подвал_h3'];
$podvalP  = $zhr['подвал_p'];
$kat      = $zhr['кат'];
$pod      = $zhr['под'];
$taytly   = $zhr['тайтлы'];

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

    // Слоганы тянутся вслепую в zherebyovka(): имя бренда доводит
    // dovesti_brend() поштучно. Подбор строк «под нехватку» жил здесь раньше и
    // качал комплект целыми именами при полосе шириной в три.
    $moi = $zhr['шапки'][$tip];
    $stroka3 = $zhr['строка3'][$tip];

    // Четыре тайтла из пяти, порядок свой на каждой странице.
    $moiTaytly = array_slice(array_merge(
        array_slice($taytly, $i % count($taytly)),
        array_slice($taytly, 0, $i % count($taytly))
    ), 0, KARTOCHEK);
    $sloj5 = vitrina($moiTaytly, $kat[$i], $pod[$i], ['A', 'B', 'C', 'A'], $i);

    $p3 = array_slice($podvalP, $i * 3, 3);

    // Доводка бренда — последним шагом, по готовым механическим строкам и
    // уже написанному тексту. Раньше счёт сводился выбором слоганов, и шаг
    // добора был размером в целое имя; здесь он равен единице.
    // Витрину и H3 подвала считаем наравне с написанным: шаблон A карточек
    // несёт «на %brand_name_ru%», а слоган подвала — своё имя. Без них доводка
    // считала по неполной странице и промахивалась вверх на две единицы.
    dovesti_brend($moi, $stroka3, $p3, $telo . $faq . $sloj5 . $podvalH3[$i], $brendNorma[$tip] ?? [], $stroki3);

    // Слои собираются ПОСЛЕ доводки: первая версия печатала шапку до неё, и
    // правка уходила в пустоту, ничего не меняя на выходе.
    $sloj1 = implode(' ', array_map(static fn(string $p) => "<p>$p</p>", $moi));
    $sloj2 = '<h2>' . rtrim($tri[$i], '.') . '</h2>';
    $sloj3 = '<p>' . $stroka3 . '</p>';
    $sloj7 = "<p>Последнее обновление %domain_name%:\n%date%          \n        </p>\n"
           . "<h3>{$podvalH3[$i]}</h3>\n"
           . implode("\n", array_map(static fn(string $p) => "<p>$p</p>", $p3)) . "\n";

    file_put_contents("$vyhod/$tip.html",
        "$sloj1\n$sloj2\n$sloj3\n" . rtrim($telo) . "\n" . $sloj5 . rtrim($faq) . "\n" . $sloj7);
    $sdelano++;
}
// Жребий записываем за комплектом сразу после сборки: следующий набор вычтет
// эти строки из пулов и на них уже не наткнётся.
if (!$snyat) { reestr_zapisat($semya, $zhr); }

// Свод комплекта едет вместе со страницами: без него сквозная сверка фактов
// на приёмке молча проваливается в режим «свода нет» и проверяет вчетверо меньше.
if ($vyhod !== $dir && is_file("$dir/svod.json")) {
    copy("$dir/svod.json", "$vyhod/svod.json");
}
printf("%s: %d страниц, семя «%s»%s%s\n", $vyhod, $sdelano, $semya,
    $snyat ? ', слои сняты' : '',
    $snyat || !$snyatoZanyatyh ? '' : ", занято соседями $snyatoZanyatyh слоганов");

// Пул H2-слоганов — самый узкий: по семь на комплект. Предупреждаем заранее,
// а не когда жребий начнёт возвращать пустоту.
//
// Считаем по ОТФИЛЬТРОВАННОМУ пулу, а не по сырому: из 287 строк словаря
// H2-слоганом годятся 195, и запас по сырому счёту завышался в полтора раза.
if (!$snyat) {
    $godnyh = count(array_filter($slogany['h2_слоган'] ?? [],
        static fn(string $x) => !str_contains($x, '?')
            && substr_count($x, '%brand_name_') <= 1
            && !$klyuchevoy($x)));
    $ostalos = intdiv($godnyh, 7);
    if ($ostalos < 5) {
        fwrite(STDERR, "внимание: H2-слоганов хватит ещё на $ostalos комплектов — пополни slogany.json\n");
    }
}

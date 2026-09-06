<?php
declare(strict_types=1);

require_once __DIR__ . '/Chislitelnye.php';

/**
 * Сквозная сверка фактов по всем семи страницам.
 *
 * Постраничные меры и согласование смотрят внутрь одной страницы. Дефект,
 * которого они не видят по устройству, — факт, согласованный внутри страницы
 * и разошедшийся между страницами. Он лезет ровно там, где комплект пишется
 * страницами-сценами: каждая сцена доказывает своё и подтягивает общий факт
 * под себя. Живые примеры из rogozhnaya-masterskaya-1, все найдены глазами:
 *
 *   — главная: настольные игры «гостю открыты целиком», при том что гостю там
 *     же обещано 4 400 машин из 6 200, а /slots пишет «скрыты все 760»;
 *   — главная: счёт заведён руками за девяносто секунд, /registracia: тот же
 *     счёт открыт через внешний профиль за восемь секунд;
 *   — почта правится «прямо в кабинете за полминуты» и «только оператором, до
 *     четырёх суток» — на двух соседних страницах;
 *   — «семь суток простоя» в заголовке и «четыре дня» в первой же строке под ним.
 *
 * Три проверки, от точной к дешёвой:
 *
 *   1. СВОД. Комплект объявляет свои величины в svod.json, и всякая фраза,
 *      где стоит опорное слово величины и число в её единице, обязана нести
 *      объявленное значение. Единственная проверка, которая ловит расхождение
 *      смысла, а не формы, — и единственная, которой нужен свод. Без файла
 *      она молча пропускается: у старых комплектов свода нет.
 *   2. СЧЁТ ПРОТИВ ПЕРЕЧНЯ. «Пять настроек, которые это чинят» над списком из
 *      четырёх пунктов. Считается механически и без свода.
 *   3. СТРОКИ ТАБЛИЦ. Одно и то же имя строки в таблицах двух страниц с
 *      разными числами. Именно так вылезли настольные игры.
 */
final class Skvoznye
{
    /** Единица → её поверхностные формы. Ключ канонический. */
    private const EDINICY = [
        'час'      => ['час', 'часа', 'часов', 'часу', 'часам'],
        'сутки'    => ['сутки', 'суток', 'суткам', 'день', 'дня', 'дней', 'дню'],
        'минута'   => ['минута', 'минуты', 'минут', 'минуте'],
        'секунда'  => ['секунда', 'секунды', 'секунд'],
        'неделя'   => ['неделя', 'недели', 'недель'],
        'месяц'    => ['месяц', 'месяца', 'месяцев'],
        'год'      => ['год', 'года', 'лет'],
        '₽'        => ['₽', 'рубль', 'рубля', 'рублей'],
        '%'        => ['%', 'процент', 'процента', 'процентов'],
        'штука'    => ['штук', 'штуки', 'штука', 'позиций', 'позиции', 'позиция',
                       'машин', 'машины', 'машина', 'тайтлов', 'тайтла', 'столов', 'стола'],
        'строка'   => ['строк', 'строки', 'строка', 'строке', 'строку'],
        'графа'    => ['граф', 'графы', 'графа', 'графу', 'поле', 'поля', 'полей'],
        'студия'   => ['студий', 'студии', 'студия'],
        'документ' => ['документ', 'документа', 'документов'],
        'МБ'       => ['МБ', 'мегабайт', 'мегабайта', 'мегабайтов'],
        'круг'     => ['кругов', 'круга', 'круг', 'спин', 'спина', 'спинов',
                       'вращений', 'вращения', 'вращение'],
        'заявка'   => ['заявок', 'заявки', 'заявка'],
        'провал'   => ['провалов', 'провала', 'провал'],
        'кратность' => [],
    ];

    /**
     * Фразы страницы: строка таблицы — целиком, остальное — по предложениям.
     *
     * @return list<array{где:string,текст:string}>
     */
    public static function frazy(string $html): array
    {
        $out = [];
        if (preg_match_all('~(?is)<tr[^>]*>(.*?)</tr>~', $html, $m)) {
            foreach ($m[1] as $tr) {
                $t = self::plain(preg_replace('~(?is)</t[dh]>~', ' · ', $tr) ?? '');
                if ($t !== '') { $out[] = ['где' => 'таблица', 'текст' => $t]; }
            }
        }
        $bez = preg_replace('~(?is)<table.*?</table>~', ' ', $html) ?? '';
        preg_match_all('~(?is)<(h2|h3|p|li|summary)[^>]*>(.*?)</\1>~', $bez, $m2, PREG_SET_ORDER);
        foreach ($m2 as $b) {
            foreach (self::predlozheniya(self::plain($b[2])) as $s) {
                $out[] = ['где' => mb_strtolower($b[1]), 'текст' => $s];
            }
        }
        return $out;
    }

    /**
     * Числа с единицами внутри фразы.
     *
     * @return list<array{значение:float,единица:string,кусок:string}>
     */
    public static function chisla(string $fraza, bool $bezEdinic = false): array
    {
        $ch = '(?:' . Chislitelnye::shablonCifr() . '|' . Chislitelnye::shablon() . ')';
        $out = [];

        // Кратность пишется знаком впереди: «×35».
        if (preg_match_all('~×[\s\x{00A0}]*(' . Chislitelnye::shablonCifr() . ')~u', $fraza, $m)) {
            foreach ($m[1] as $x) {
                $out[] = ['значение' => Chislitelnye::razobratCifry($x),
                          'единица' => 'кратность', 'кусок' => '×' . $x];
            }
        }
        // Полчаса и полминуты — половина единицы, а не числительное.
        $pol = Chislitelnye::shablonPolovin();
        if ($pol !== '' && preg_match_all('~\b(' . $pol . ')\b~u', $fraza, $m)) {
            foreach ($m[1] as $x) {
                [$v, $ed] = Chislitelnye::polovina($x);
                $out[] = ['значение' => $v, 'единица' => $ed, 'кусок' => $x];
            }
        }
        foreach (self::EDINICY as $kanon => $formy) {
            if (!$formy) { continue; }
            usort($formy, static fn(string $a, string $b) => mb_strlen($b) <=> mb_strlen($a));
            $alt = implode('|', array_map('preg_quote', $formy));
            $re = '~(' . $ch . ')[\s\x{00A0}]*(?:' . $alt . ')(?![\p{L}])~ui';
            if (!preg_match_all($re, $fraza, $m, PREG_SET_ORDER)) { continue; }
            foreach ($m as $x) {
                $v = self::vChislo($x[1]);
                if ($v === null) { continue; }
                $out[] = ['значение' => $v, 'единица' => $kanon, 'кусок' => trim($x[0])];
            }
        }
        if ($bezEdinic) {
            // Голые числа: «0 из 760» в таблице, «из четырнадцати» в прозе.
            if (preg_match_all('~(?<![\d,.])(' . Chislitelnye::shablonCifr() . ')~u', $fraza, $m)) {
                foreach ($m[1] as $x) {
                    $out[] = ['значение' => Chislitelnye::razobratCifry($x),
                              'единица' => '—', 'кусок' => $x];
                }
            }
            if (preg_match_all('~(' . Chislitelnye::shablon() . ')~ui', $fraza, $m)) {
                foreach ($m[1] as $x) {
                    $v = Chislitelnye::razobrat($x);
                    if ($v === null) { continue; }
                    $out[] = ['значение' => $v, 'единица' => '—', 'кусок' => $x];
                }
            }
        }
        return $out;
    }

    /**
     * Проверка по своду: объявленная величина против всего написанного.
     *
     * @param array<string,string> $stranicy тип → html
     * @param array<string,array{значение:float|int,единица:string,слова:list<string>}> $svod
     * @return list<array{вид:string,где:string,ярлык:string,ждали:float,нашли:float,фраза:string}>
     */
    public static function poSvodu(array $stranicy, array $svod): array
    {
        $out = [];
        foreach ($stranicy as $tip => $html) {
            foreach (self::frazy($html) as $f) {
                $nizh = mb_strtolower($f['текст']);
                foreach ($svod as $yarlyk => $fakt) {
                    $est = false;
                    foreach ($fakt['слова'] as $slovo) {
                        if (mb_strpos($nizh, mb_strtolower($slovo)) !== false) { $est = true; break; }
                    }
                    if (!$est) { continue; }
                    foreach ($fakt['нельзя'] ?? [] as $zapret) {
                        if (mb_strpos($nizh, mb_strtolower($zapret)) === false) { continue; }
                        $out[] = ['вид' => 'запрет', 'где' => $tip, 'ярлык' => $yarlyk,
                                  'ждали' => 0.0, 'нашли' => 0.0,
                                  'фраза' => $f['текст'], 'запрет' => $zapret];
                    }
                    if (!isset($fakt['единица'])) { continue; }
                    // Объявленное значение засчитывается, где бы во фразе оно ни
                    // стояло: «семь суток из четырнадцати отпущенных» несёт и
                    // срок, и остаток, и единица есть только у первого числа.
                    $nashli = [];
                    foreach (self::chisla($f['текст'], true) as $c) {
                        if (abs($c['значение'] - (float) $fakt['значение']) < 0.001) { continue 2; }
                        if ($c['единица'] === $fakt['единица']) { $nashli[] = $c; }
                    }
                    if (!$nashli) { continue; }
                    $out[] = ['вид' => 'свод', 'где' => $tip, 'ярлык' => $yarlyk,
                              'ждали' => (float) $fakt['значение'],
                              'нашли' => $nashli[0]['значение'], 'фраза' => $f['текст']];
                }
            }
        }
        return $out;
    }

    /**
     * Счёт против перечня: «Пять настроек» над списком из четырёх пунктов.
     *
     * @return list<array{вид:string,где:string,объявлено:int,в перечне:int,фраза:string}>
     */
    public static function schyotPerechnya(array $stranicy): array
    {
        $ch = '(?:' . Chislitelnye::shablonCifr() . '|' . Chislitelnye::shablon() . ')';
        $edinicy = [];
        foreach (self::EDINICY as $formy) { $edinicy = array_merge($edinicy, $formy); }
        $out = [];
        foreach ($stranicy as $tip => $html) {
            $bloki = self::bloki($html);
            foreach ($bloki as $i => $b) {
                if (!in_array($b['тег'], ['h2', 'h3', 'p'], true)) { continue; }
                $sled = $bloki[$i + 1] ?? null;
                if (!$sled || !in_array($sled['тег'], ['ul', 'ol'], true)) { continue; }
                $zag = self::plain($b['нутро']);
                // Счёт объявляет заголовок или подводка с двоеточием. Число в
                // середине живой фразы к длине перечня отношения не имеет.
                if ($b['тег'] === 'p' && !str_ends_with($zag, ':')) { continue; }
                $punktov = preg_match_all('~(?is)<li[^>]*>~', $sled['нутро']);
                // Число в придаточном («при двух совпадениях») не считает
                // перечень: берём только то, что стоит в самом объявлении.
                $chast = mb_strpos($zag, ':') !== false
                    ? mb_substr($zag, mb_strpos($zag, ':') + 1)
                    : (mb_strpos($zag, ',') !== false ? mb_substr($zag, 0, mb_strpos($zag, ',')) : $zag);
                if (!preg_match('~(?:^|[^\p{L}])(?<!при )(?<!из )(?<!за )(?<!после )('
                    . $ch . ')[\s\x{00A0}]+(\p{L}+)~ui', $chast, $g)) { continue; }
                $n = self::vChislo($g[1]);
                if ($n === null || $n < 2 || $n > 12 || fmod($n, 1.0) !== 0.0) { continue; }
                // Единица времени, денег или счёта — это величина, а не длина перечня.
                if (in_array(mb_strtolower($g[2]), $edinicy, true)) { continue; }
                if ((int) $n === $punktov) { continue; }
                $out[] = ['вид' => 'перечень', 'где' => $tip, 'объявлено' => (int) $n,
                          'в перечне' => $punktov, 'фраза' => $zag];
            }
        }
        return $out;
    }

    /**
     * Блоки страницы подряд, без вложенности: тег и нутро.
     *
     * @return list<array{тег:string,нутро:string}>
     */
    private static function bloki(string $html): array
    {
        preg_match_all(
            '~(?is)<(h2|h3|p|ul|ol|table|blockquote|details)\b[^>]*>(.*?)</\1>~',
            $html, $m, PREG_SET_ORDER
        );
        $out = [];
        foreach ($m as $x) { $out[] = ['тег' => mb_strtolower($x[1]), 'нутро' => $x[2]]; }
        return $out;
    }

    private static function vChislo(string $s): ?float
    {
        return preg_match('~\d~', $s)
            ? Chislitelnye::razobratCifry($s)
            : Chislitelnye::razobrat($s);
    }

    private static function plain(string $h): string
    {
        $t = html_entity_decode(strip_tags($h), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        return trim((string) preg_replace('~[\s\x{00A0}]+~u', ' ', $t));
    }

    private static function predlozheniya(string $t): array
    {
        $ch = preg_split('~(?<=[.!?…])\s+~u', $t) ?: [];
        return array_values(array_filter(array_map('trim', $ch), static fn(string $s) => $s !== ''));
    }

}

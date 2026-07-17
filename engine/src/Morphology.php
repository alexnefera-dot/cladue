<?php
declare(strict_types=1);

/**
 * Морфология для русского на базе алгоритма Портера-Снежка (Snowball RU).
 * Приводит словоформы к единой основе, что позволяет корректно сопоставлять
 * ключи и LSI по морфологии — как это делает Яндекс.
 *
 * Алгоритм: http://snowball.tartarus.org/algorithms/russian/stemmer.html
 */
final class Morphology
{
    private const VOWELS = ['а','е','и','о','у','ы','э','ю','я'];

    private const PERFECTIVE_GERUND_1 = ['вшись','вши','в'];                 // после а/я
    private const PERFECTIVE_GERUND_2 = ['ившись','ывшись','ивши','ывши','ив','ыв'];
    private const ADJECTIVE = ['ими','ыми','его','ого','ему','ому','их','ых','ее','ие','ые','ое',
                               'ей','ий','ый','ой','ем','им','ым','ом','ую','юю','ая','яя','ою','ею'];
    private const PARTICIPLE_1 = ['ющ','ем','нн','вш','щ'];                   // после а/я
    private const PARTICIPLE_2 = ['ивш','ывш','ующ'];
    private const REFLEXIVE = ['ся','сь'];
    private const VERB_1 = ['ешь','нно','ете','йте','ла','на','ли','ем','ло','но','ет','ют','ны','ть','й','л','н'];
    private const VERB_2 = ['ейте','уйте','ила','ыла','ена','ите','или','ыли','ило','ыло','ено','ят','ует',
                            'уют','ены','ить','ыть','ишь','ей','уй','ил','ыл','им','ым','ен','ят','ит','ыт','ую','ю'];
    private const NOUN = ['иями','ями','ами','ией','иям','ием','иях','ев','ов','ие','ье','еи','ии','ей','ой',
                          'ий','ям','ем','ам','ом','ах','ях','ия','ья','ию','ью','а','е','и','й','о','у','ы','ь','ю','я'];
    private const DERIVATIONAL = ['ость','ост'];
    private const SUPERLATIVE = ['ейше','ейш'];

    /** @var array<string,string> */
    private static array $cache = [];

    public static function stem(string $word): string
    {
        $word = str_replace('ё', 'е', mb_strtolower($word, 'UTF-8'));
        if (isset(self::$cache[$word])) { return self::$cache[$word]; }
        if (mb_strlen($word, 'UTF-8') < 3 || !self::hasVowel($word)) {
            return self::$cache[$word] = $word;
        }
        $chars = self::split($word);

        // границы регионов RV, R2
        $rv = self::rvStart($chars);
        $r2 = self::r2Start($chars);

        // ---- Шаг 1 ----
        if (!self::removeInRegion($chars, $rv, self::PERFECTIVE_GERUND_2)) {
            if (!self::removeAfterAYA($chars, $rv, self::PERFECTIVE_GERUND_1)) {
                // reflexive
                self::removeInRegion($chars, $rv, self::REFLEXIVE);
                // adjectival / verb / noun (первый сработавший)
                if (self::removeAdjectival($chars, $rv)) {
                    // done
                } elseif (self::removeInRegion($chars, $rv, self::VERB_2)
                       || self::removeAfterAYA($chars, $rv, self::VERB_1)) {
                    // done
                } else {
                    self::removeInRegion($chars, $rv, self::NOUN);
                }
            }
        }

        // ---- Шаг 2: убрать конечное и в RV ----
        self::removeInRegion($chars, $rv, ['и']);

        // ---- Шаг 3: деривация в R2 ----
        self::removeInRegion($chars, $r2, self::DERIVATIONAL);

        // ---- Шаг 4 ----
        $n = count($chars);
        if ($n >= 2 && $chars[$n - 1] === 'н' && $chars[$n - 2] === 'н') {
            array_pop($chars); // нн -> н
        } else {
            if (self::removeInRegion($chars, $rv, self::SUPERLATIVE)) {
                $n = count($chars);
                if ($n >= 2 && $chars[$n - 1] === 'н' && $chars[$n - 2] === 'н') { array_pop($chars); }
            }
            $n = count($chars);
            if ($n && $chars[$n - 1] === 'ь' && $rv <= $n - 1) { array_pop($chars); }
        }

        return self::$cache[$word] = implode('', $chars);
    }

    /** @return string[] */
    private static function split(string $w): array
    {
        return preg_split('//u', $w, -1, PREG_SPLIT_NO_EMPTY) ?: [];
    }

    private static function hasVowel(string $w): bool
    {
        foreach (self::VOWELS as $v) {
            if (mb_strpos($w, $v, 0, 'UTF-8') !== false) { return true; }
        }
        return false;
    }

    private static function isVowel(string $ch): bool
    {
        return in_array($ch, self::VOWELS, true);
    }

    /** RV: позиция после первого гласного */
    private static function rvStart(array $chars): int
    {
        foreach ($chars as $i => $ch) {
            if (self::isVowel($ch)) { return $i + 1; }
        }
        return count($chars);
    }

    /** R1 после первого «гласный+согласный», R2 — то же внутри R1 */
    private static function r2Start(array $chars): int
    {
        $r1 = self::regionAfter($chars, 0);
        return self::regionAfter($chars, $r1);
    }

    private static function regionAfter(array $chars, int $from): int
    {
        $n = count($chars);
        $i = $from;
        while ($i + 1 < $n) {
            if (self::isVowel($chars[$i]) && !self::isVowel($chars[$i + 1])) {
                return $i + 2;
            }
            $i++;
        }
        return $n;
    }

    /** снять самое длинное окончание из списка, если оно целиком в регионе [start..] */
    private static function removeInRegion(array &$chars, int $start, array $endings): bool
    {
        $n = count($chars);
        foreach ($endings as $end) {
            $elen = mb_strlen($end, 'UTF-8');
            if ($n - $elen < $start) { continue; }
            if (implode('', array_slice($chars, $n - $elen)) === $end) {
                array_splice($chars, $n - $elen);
                return true;
            }
        }
        return false;
    }

    /** окончание засчитывается только если ему предшествует а или я (в RV) */
    private static function removeAfterAYA(array &$chars, int $start, array $endings): bool
    {
        $n = count($chars);
        foreach ($endings as $end) {
            $elen = mb_strlen($end, 'UTF-8');
            $pos = $n - $elen;
            if ($pos - 1 < $start) { continue; }
            if (implode('', array_slice($chars, $pos)) !== $end) { continue; }
            $prev = $chars[$pos - 1] ?? '';
            if ($prev === 'а' || $prev === 'я') {
                array_splice($chars, $pos);
                return true;
            }
        }
        return false;
    }

    private static function removeAdjectival(array &$chars, int $rv): bool
    {
        if (!self::removeInRegion($chars, $rv, self::ADJECTIVE)) { return false; }
        // опциональное причастие перед прилагательным
        if (!self::removeAfterAYA($chars, $rv, self::PARTICIPLE_1)) {
            self::removeInRegion($chars, $rv, self::PARTICIPLE_2);
        }
        return true;
    }

    /** основа каждого слова фразы */
    public static function stemPhrase(string $phrase): array
    {
        preg_match_all('/[\p{L}\p{Nd}]+/u', mb_strtolower($phrase, 'UTF-8'), $m);
        return array_map([self::class, 'stem'], $m[0]);
    }

    /** присутствуют ли ВСЕ слова ключа в тексте (не обязательно подряд) */
    public static function allWordsInText(string $phrase, array $textStems): bool
    {
        return self::allStemsInSet(self::stemPhrase($phrase), array_flip($textStems));
    }

    /**
     * Быстрый вариант: набор основ текста передаётся уже как хэш-множество
     * (array_flip). Используется при сопоставлении тысяч запросов бренда.
     * @param string[] $needStems
     * @param array<string,int> $stemSet
     */
    public static function allStemsInSet(array $needStems, array $stemSet): bool
    {
        if (!$needStems) { return false; }
        foreach ($needStems as $stem) {
            if (!isset($stemSet[$stem])) { return false; }
        }
        return true;
    }

    /** встречается ли фраза (по основам слов, подряд) в тексте */
    public static function phraseInText(string $phrase, array $textStems): bool
    {
        $need = self::stemPhrase($phrase);
        if (!$need) { return false; }
        $nlen = count($need);
        $tlen = count($textStems);
        for ($i = 0; $i + $nlen <= $tlen; $i++) {
            if (array_slice($textStems, $i, $nlen) === $need) { return true; }
        }
        return false;
    }
}

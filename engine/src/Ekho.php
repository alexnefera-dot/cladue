<?php
declare(strict_types=1);

/**
 * Ответ FAQ, пересказывающий абзац тела той же страницы.
 *
 * Нашлось сплошным чтением партии, а не мерами. Короткие абзацы в одно
 * предложение, которые ставились ради пола «абзац-фраза», собирались из
 * готовых ответов FAQ этой же страницы:
 *
 *   тело:  «Срок до 30 дней — по моему запросу пришло на четвёртый.»
 *   ответ: «Заявленный срок — тридцать дней, по моему запросу пришло на
 *           четвёртый. Ждать месяц приходится редко.»
 *
 * Числа при этом улучшались: доля абзацев в одно предложение росла, объём
 * рос, шинглы не страдали — фраза-то внутри страницы, а межстраничная
 * уникальность считается между страницами. Заикание видел только человек.
 *
 * Порог взят из рынка и он жёсткий: у 50 доноров ноль таких ответов на 1992.
 * Ноль на двух тысячах — это не везение, а правило жанра. Чужой FAQ отвечает
 * на то, чего в теле нет вовсе: про VPN со сменой адреса каждые пять минут,
 * про ERC-20 вместо BEP-20, про турнир на бонусные деньги. Он дополняет
 * страницу, а не подводит ей итог.
 */
final class Ekho
{
    /** Доля общих слов, начиная с которой ответ считается пересказом. */
    private const PORog = 70.0;

    /** Абзацы короче этого в сравнение не идут: там и совпадать нечему. */
    private const MIN_DLINA = 40;

    /** Слова короче этого не различают тексты. */
    private const MIN_SLOVO = 5;

    /**
     * @return list<array{ответ:string,тело:string,доля:float}>
     */
    public static function proverit(string $html): array
    {
        $telo = (string) preg_replace('~(?is)<details.*?</details>~', '', $html);
        $abzacy = [];
        foreach (self::uzly($telo) as $t) {
            $s = self::slova($t);
            if ($s) { $abzacy[] = [$t, $s]; }
        }
        if (!$abzacy) { return []; }

        $out = [];
        foreach (self::otvety($html) as $otvet) {
            $so = self::slova($otvet);
            if (!$so) { continue; }
            foreach ($abzacy as [$tekst, $sa]) {
                $dolya = count(array_intersect($so, $sa)) / min(count($so), count($sa)) * 100;
                if ($dolya >= self::PORog) {
                    $out[] = ['ответ' => $otvet, 'тело' => $tekst, 'доля' => round($dolya, 1)];
                    continue 2;
                }
            }
        }
        return $out;
    }

    /** @return list<string> */
    private static function uzly(string $html): array
    {
        $out = [];
        if (!preg_match_all('~(?is)<(p|li)[^>]*>(.*?)</\1>~', $html, $m, PREG_SET_ORDER)) {
            return $out;
        }
        foreach ($m as $x) {
            $t = self::chisto($x[2]);
            if (mb_strlen($t) > self::MIN_DLINA) { $out[] = $t; }
        }
        return $out;
    }

    /** @return list<string> */
    private static function otvety(string $html): array
    {
        $out = [];
        if (!preg_match_all('~(?is)<div itemprop="text"[^>]*>(.*?)</div>~', $html, $m)) {
            return $out;
        }
        foreach ($m[1] as $x) {
            $t = self::chisto($x);
            if (mb_strlen($t) > self::MIN_DLINA) { $out[] = $t; }
        }
        return $out;
    }

    private static function chisto(string $x): string
    {
        $t = html_entity_decode(strip_tags($x), ENT_QUOTES, 'UTF-8');
        return trim((string) preg_replace('~\s+~u', ' ', $t));
    }

    /** @return list<string> уникальные значимые слова в нижнем регистре */
    private static function slova(string $t): array
    {
        preg_match_all('~[\p{L}]{' . self::MIN_SLOVO . ',}~u', $t, $m);
        return array_values(array_unique(array_map(
            static fn(string $w): string => mb_strtolower($w),
            $m[0]
        )));
    }
}

<?php
declare(strict_types=1);

/**
 * Поимённая профильная лексика: студии-провайдеры и названия игр.
 *
 * Списки берутся из пулов корпуса, а не пишутся в коде. Причина: пул — это то
 * же самое, что генератор предлагает реалайзеру в промпте, и мерка обязана
 * совпадать с предложением. Хардкод из двух десятков тайтлов давал ложный
 * промах на своей же генерации: страница называла «San Quentin» и «Hall of
 * Gods», а счётчик их не знал и писал ноль там, где названий было двенадцать.
 *
 * К пулам добавляются тайтлы, встреченные в референсах и отсутствующие в пуле —
 * иначе донору занижался бы счёт по той же причине.
 */
final class NicheLexicon
{
    /** Тайтлы из референсов v3, которых нет в пулах. */
    private const EXTRA_GAMES = [
        'Razor Shark', "Jammin' Jars", 'Elvis Frog in Vegas', 'Cash Elevator',
        'Deadwood', 'Extra Chilli', 'Mega Moolah', 'San Quentin', 'Hall of Gods',
        'Fire in the Hole', 'Le Bandit', 'Le Pharaoh', 'Tome of Madness',
        'Dead or Alive', 'Immortal Romance', 'Twin Spin', 'Space Wars',
        'Book of Ra', 'Crazy Monkey', 'Fruit Cocktail', 'Resident',
    ];
    private const EXTRA_PROVIDERS = [
        'Igrosoft', 'Novomatic', 'Amatic', 'Endorphina', 'Tom Horn', 'Kalamba',
        'Mascot', 'Onlyplay', 'Belatra', 'Gamzix', 'Fugaso', 'ELK',
    ];


    /**
     * Профильная лексика ниши. Кластеры семантики отвечают на «о чём страница»,
     * этот словарь — на «какими словами»: два текста с одинаковой плотностью
     * кластера «слоты» могут не совпасть ни одним нишевым термином.
     */
    public const TERMS = [
        'RTP'              => '~\bRTP\b~ui',
        'отдача/выплаты'   => '~отдач\w*|выплат\w*~ui',
        'вейджер/отыгрыш'  => '~вейджер\w*|отыгрыш\w*|wager~ui',
        'волатильность'    => '~волатильн\w*~ui',
        'дисперсия'        => '~дисперси\w*~ui',
        'фриспины'         => '~фриспин\w*|free ?spin\w*~ui',
        'бонусный раунд'   => '~бонусн\w+ раунд\w*~ui',
        'множитель'        => '~множител\w*|мультипликатор\w*~ui',
        'скаттер/вайлд'    => '~скаттер\w*|scatter|вайлд\w*|wild~ui',
        'катушки/линии'    => '~катушк\w*|барабан\w*|лини\w+ выплат~ui',
        'механики'         => '~megaways|мегавейз\w*|hold ?(?:and|&) ?win|cluster ?pays|каскадн\w*~ui',
        'джекпот'          => '~джекпот\w*|jackpot~ui',
        'кэшбэк'           => '~кэшбэк\w*|кешбэк\w*|cashback~ui',
        'лимит'            => '~лимит\w*~ui',
        'верификация/KYC'  => '~верификаци\w*|KYC|AML~ui',
        'лицензия'         => '~лицензи\w*~ui',
        'провайдер/студия' => '~провайдер\w*~ui',
        'депозит'          => '~депозит\w*~ui',
        'ставка/спин'      => '~ставк\w*|спин\w*|вращени\w*~ui',
        'демо-режим'       => '~демо[- ]?(?:режим\w*|верси\w*)|демка\w*~ui',
        'турнир'           => '~турнир\w*|лидербор\w*~ui',
        'вывод средств'    => '~вывод\w*|снятие~ui',
        'зеркало/домен'    => '~зеркал\w*|домен\w*|VPN|прокси~ui',
        'промокод'         => '~промокод\w*|бонус[- ]?код\w*~ui',
    ];


    /**
     * Проза страницы: абзацы и содержательные пункты списков.
     *
     * Плитки каталога, шапка и подвал сохранённой страницы — не текст, но и
     * выбросить списки целиком нельзя: в этом жанре буллеты несут факты. Пункт
     * считается навигацией, если он короткий и держит ссылку — это подпись
     * меню, а не мысль.
     */
    public static function prose(string $raw): string
    {
        $parts = [];
        if (preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm)) {
            foreach ($pm[1] as $x) { $parts[] = $x; }
        }
        if (preg_match_all('~<li\b[^>]*>(.*?)</li>~is', $raw, $lm)) {
            foreach ($lm[1] as $x) {
                $plain = trim(preg_replace('~\s+~u', ' ', strip_tags($x)));
                $isNav = mb_stripos($x, '<a ') !== false && mb_strlen($plain) < 60;
                if (!$isNav && $plain !== '') { $parts[] = $x; }
            }
        }
        $flat = array_map(fn($x) => preg_replace('~<[^>]+>~', ' ', $x), $parts);
        return preg_replace('~\s+~u', ' ', implode(' ', $flat));
    }

    /** @return array<string,int> счёт по каждому термину, нули опущены */
    public static function termCounts(string $text): array
    {
        $out = [];
        foreach (self::TERMS as $lab => $re) {
            $c = preg_match_all($re, $text);
            if ($c > 0) { $out[$lab] = $c; }
        }
        return $out;
    }

    public static function termsTotal(string $text): int
    {
        return array_sum(self::termCounts($text));
    }

    private static array $cache = [];

    /** @return array{0:string,1:string} регулярки [провайдеры, игры] */
    public static function patterns(?string $dataDir = null): array
    {
        $dir = $dataDir ?? (__DIR__ . '/../data');
        if (isset(self::$cache[$dir])) { return self::$cache[$dir]; }

        $ent = [];
        $file = $dir . '/pools/pools.json';
        if (is_file($file)) {
            $ent = json_decode((string) file_get_contents($file), true)['entities'] ?? [];
        }
        $games = array_merge(
            $ent['games_slots'] ?? [], $ent['games_crash'] ?? [], $ent['games_live'] ?? [],
            self::EXTRA_GAMES
        );
        $prov = array_merge($ent['providers'] ?? [], self::EXTRA_PROVIDERS);

        return self::$cache[$dir] = [self::alt($prov), self::alt($games)];
    }

    /** Одно из названий, длинные раньше коротких — «Sweet Bonanza 1000» не должен съедаться «Sweet Bonanza». */
    private static function alt(array $names): string
    {
        $names = array_values(array_unique(array_filter(array_map('trim', $names))));
        usort($names, fn($a, $b) => mb_strlen($b) <=> mb_strlen($a));
        $parts = [];
        foreach ($names as $n) {
            // Пробелы — любой пробельный, чтобы перенос строки в разметке не ломал счёт.
            $parts[] = str_replace('\ ', '\s+', preg_quote($n, '~'));
        }
        return '~(?<![\w-])(' . implode('|', $parts) . ')(?![\w-])~ui';
    }

    public static function countProviders(string $text, ?string $dataDir = null): int
    {
        [$p] = self::patterns($dataDir);
        return preg_match_all($p, $text);
    }

    public static function countGames(string $text, ?string $dataDir = null): int
    {
        [, $g] = self::patterns($dataDir);
        return preg_match_all($g, $text);
    }
}

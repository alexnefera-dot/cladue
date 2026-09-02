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
    /**
     * Маски привязаны к границе слова. Без `\b` они ловят термин внутри чужого
     * слова, и хуже всего — внутри ДРУГОГО термина: «фриспины» попадали разом
     * в «фриспины» и в «ставка/спин», то есть один и тот же спин считался
     * дважды. Заодно уходили «возвращения» в «вращение» и «заставку» в
     * «ставку». «Автоспин» после привязки нужно назвать отдельно: границы
     * внутри слова нет.
     */
    public const TERMS = [
        'RTP'              => '~\bRTP\b~ui',
        'отдача/выплаты'   => '~\bотдач\w*|\bвыплат\w*~ui',
        'вейджер/отыгрыш'  => '~\bвейджер\w*|\bотыгрыш\w*|\bwager~ui',
        'волатильность'    => '~\bволатильн\w*~ui',
        'дисперсия'        => '~\bдисперси\w*~ui',
        'фриспины'         => '~\bфриспин\w*|\bfree ?spin\w*~ui',
        'бонусный раунд'   => '~\bбонусн\w+ раунд\w*~ui',
        'множитель'        => '~\bмножител\w*|\bмультипликатор\w*~ui',
        'скаттер/вайлд'    => '~\bскаттер\w*|\bscatter|\bвайлд\w*|\bwild~ui',
        'катушки/линии'    => '~\bкатушк\w*|\bбарабан\w*|\bлини\w+ выплат~ui',
        'механики'         => '~\bmegaways|\bмегавейз\w*|\bhold ?(?:and|&) ?win|\bcluster ?pays|\bкаскадн\w*~ui',
        'джекпот'          => '~\bджекпот\w*|\bjackpot~ui',
        'кэшбэк'           => '~\bкэшбэк\w*|\bкешбэк\w*|\bcashback~ui',
        'лимит'            => '~\bлимит\w*~ui',
        'верификация/KYC'  => '~\bверификаци\w*|\bKYC\b|\bAML\b~ui',
        'лицензия'         => '~\bлицензи\w*~ui',
        'провайдер/студия' => '~\bпровайдер\w*~ui',
        'депозит'          => '~\bдепозит\w*~ui',
        'ставка/спин'      => '~\bставк\w*|\bспин\w*|\bавтоспин\w*|\bвращени\w*~ui',
        'демо-режим'       => '~\bдемо[- ]?(?:режим\w*|верси\w*)|\bдемка\w*~ui',
        'турнир'           => '~\bтурнир\w*|\bлидербор\w*~ui',
        'вывод средств'    => '~\bвывод\w*|\bснятие~ui',
        'зеркало/домен'    => '~\bзеркал\w*|\bдомен\w*|\bVPN\b|\bпрокси~ui',
        'промокод'         => '~\bпромокод\w*|\bбонус[- ]?код\w*~ui',
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


    /**
     * Плейсхолдеры бренда — один токен, а не три.
     *
     * `%brand_name_ru%` разбирается счётчиком слов на «brand», «name», «ru», и
     * тридцать вставок дают под сотню лишних слов там, где у донора стоит одно
     * имя. На объём это давало нам +2-3% на каждой странице, а заодно сдвигало
     * среднюю длину абзаца и все доли, у которых слова в знаменателе.
     */
    public static function unplaceholder(string $raw): string
    {
        $map = [
            '%brand_name_ru%' => 'Бренд',
            '%brand_name_en%' => 'Brand',
            '%domain_name%'   => 'brand.win',
            '%date%'          => 'июль',
        ];
        $out = str_replace(array_keys($map), array_values($map), $raw);
        return preg_replace('~%[a-z_]+%~', 'значение', $out);
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

    /** @return array{games: string[], providers: string[]} разные названия в нижнем регистре */
    public static function names(string $text, ?string $dataDir = null): array
    {
        [$p, $g] = self::patterns($dataDir);
        $out = ['games' => [], 'providers' => []];
        foreach (['providers' => $p, 'games' => $g] as $k => $re) {
            if (!preg_match_all($re, $text, $m)) { continue; }
            $seen = [];
            foreach ($m[1] as $x) { $seen[mb_strtolower(preg_replace('~\s+~u', ' ', $x))] = 1; }
            $out[$k] = array_keys($seen);
        }
        return $out;
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

    /**
     * РАЗНЫХ названий, а не упоминаний. Счёт упоминаний ничего не говорит о том,
     * один это «Sweet Bonanza» шесть раз или шесть разных игр по разу, — а
     * образец делает именно первое: 4–7 игр на весь набор, каждая по два-три
     * раза, читатель успевает их запомнить.
     */
    public static function uniqNames(string $text, ?string $dataDir = null): int
    {
        [$p, $g] = self::patterns($dataDir);
        $seen = [];
        foreach ([$p, $g] as $re) {
            if (preg_match_all($re, $text, $m)) {
                foreach ($m[1] as $x) { $seen[mb_strtolower(preg_replace('~\s+~u', ' ', $x))] = 1; }
            }
        }
        return count($seen);
    }
}

<?php

declare(strict_types=1);

namespace YandexSites\Content;

/**
 * Бренд из ПОИСКОВОГО КЛЮЧА и сведение его написаний к одному ключу.
 *
 * Нужно для учёта доменов, которые держат МНОГО БРЕНДОВ (Support\BrandDomains): домен сетки держит
 * на своих поддоменах
 * сайты РАЗНЫХ брендов, и понять это можно только по запросам, которыми их нашли. Один бренд
 * пишется по-разному — «Вулкан Вегас», «Vulkan Vegas», «вулкан-вегас», — поэтому написание
 * приводится к канону в два шага:
 *
 *  1. ПАРЫ (PAIRS + файл brand-pairs.txt): латинское и кириллическое написание одного бренда. Нужны
 *     там, где кириллица — это ПЕРЕВОД, а не транслит: «Money X» / «Мани Икс», «Dragon Money» /
 *     «Драгон Мани», «Lex» / «Лекс». Канон пары — нормализованное латинское написание.
 *  2. ФОНЕТИКА (`normalize()`): транслит кириллицы + c/q→k, y→i, w→v и схлопывание сдвоенных букв.
 *     Так «криптобосс» и «cryptoboss» дают один ключ `kriptobos` без всякого списка. На списке из
 *     166 пар фонетика сама сводит 97; остальные держатся парами.
 *
 * Бренд из ключа: сначала ищем известный бренд среди слов запроса (по 3, 2 и 1 слову подряд —
 * бренды бывают из нескольких слов), иначе выбрасываем служебные слова («казино», «зеркало»,
 * «официальный сайт», год) и берём остаток, если он похож на название: в запросе есть слово темы
 * и осталось не больше двух слов. Три слова и больше — это описание, а не брендовый ключ.
 */
final class BrandKeys
{
    /** Файл с дополнительными парами: строка «латиница» и следом строка «кириллица» (не коммитится). */
    public const FILE = 'brand-pairs.txt';

    /** Сколько слов подряд проверяем как название бренда. */
    private const MAX_WORDS = 3;

    /** @var array<string, string> латинское написание => кириллическое */
    public const PAIRS = [
        'Ramenbet' => 'Раменбет',
        'AdmiralX' => 'Адмирал Х',
        'Kometa' => 'Комета',
        'Gizbo' => 'Гизбо',
        '7K' => '7К',
        '1xSlots' => '1хСлотс',
        'Aurora Casino' => 'Аврора Казино',
        'Unlim Casino' => 'Анлим Казино',
        'Azino777' => 'Азино777',
        'Vulkan Platinum' => 'Вулкан Платинум',
        'Vodka' => 'Водка',
        'Drip' => 'Дрип',
        'Lev' => 'Лев',
        'Money X' => 'Мани Икс',
        'New Retro' => 'Нью Ретро',
        'Starda' => 'Старда',
        'Champion Slots' => 'Чемпион Слотс',
        'Lex' => 'Лекс',
        'Dragon Money' => 'Драгон Мани',
        'Booi' => 'Буи',
        'R7' => 'Р7',
        'Vovan' => 'Вован',
        'Jetton' => 'Джеттон',
        'CryptoBoss' => 'КриптоБосс',
        'Stake' => 'Стейк',
        'UP-X' => 'Ап-Икс',
        'GetX' => 'Гет Икс',
        'ClubNika' => 'Клубника',
        'Sykaaa' => 'Сукааа',
        'Onion' => 'Онион',
        'Hype' => 'Хайп',
        'Zooma' => 'Зума',
        'MostBet Bookmaker' => 'МостБет Букмекер',
        '1Go' => '1Гоу',
        'Play Fortuna' => 'Плей Фортуна',
        'Pinco' => 'Пинко',
        'Slotozal' => 'Слотозал',
        'Vavada' => 'Вавада',
        'Riobet' => 'Риобет',
        'Arkada' => 'Аркада',
        'Irwin' => 'Ирвин',
        'Eldorado' => 'Эльдорадо',
        'Cat' => 'Кэт',
        'Kush' => 'Куш',
        'Motor' => 'Мотор',
        'Mellstroy' => 'Меллстрой',
        '1win' => '1вин',
        'Bitzamo' => 'Битзамо',
        'Bitz' => 'Битц',
        'BitStarz' => 'БитСтарз',
        'Banda' => 'Банда',
        'Baboss' => 'Бабосс',
        'Avocado' => 'Авокадо',
        'AUF' => 'АУФ',
        '888starz' => '888старз',
        '888' => '888',
        '1xbet' => '1хбет',
        'Flagman' => 'Флагман',
        'Enomo' => 'Эномо',
        'Daddy' => 'Дэдди',
        'Gama' => 'Гама',
        'Friends' => 'Френдс',
        'Fontan' => 'Фонтан',
        'Casino X' => 'Казино Икс',
        'Cactus' => 'Кактус',
        'Brillx' => 'Бриллкс',
        'Bounty' => 'Баунти',
        'Bonsai' => 'Бонсай',
        'Bollywood' => 'Болливуд',
        'Lucky Bird' => 'Лаки Бёрд',
        'Leon' => 'Леон',
        'Legzo' => 'Легзо',
        'Leebet' => 'Либет',
        'Kraken' => 'Кракен',
        'Kent' => 'Кент',
        'Jozz' => 'Джозз',
        'Joycasino' => 'Джойказино',
        'Izzi' => 'Иззи',
        'Honey Money' => 'Хани Мани',
        'Goodwin' => 'Гудвин',
        'Gold' => 'Голд',
        'Vulkan Prestige' => 'Вулкан Престиж',
        'Vulkan Mega' => 'Вулкан Мега',
        'Vulkan Vegas' => 'Вулкан Вегас',
        'Vulkan 24' => 'Вулкан 24',
        'Volna' => 'Волна',
        'Why' => 'Вай',
        'Vivaro' => 'Виваро',
        'Vibe' => 'Вайб',
        'Vegasy' => 'Вегаси',
        'Twin' => 'Твин',
        'Turbo' => 'Турбо',
        'Trix' => 'Трикс',
        'Spin City' => 'Спин Сити',
        'Sol' => 'Сол',
        'Shot' => 'Шот',
        'Pin Up' => 'Пин Ап',
        'Nomad' => 'Номад',
        'Monro' => 'Монро',
        'Maxbetslots' => 'Максбетслотс',
        'Everum' => 'Эверум',
        'Fresh' => 'Фреш',
        'Selector' => 'Селектор',
        'Rox' => 'Рокс',
        'Pokerdom' => 'Покердом',
        'Olimp' => 'Олимп',
        'Melbet' => 'Мелбет',
        'Lootrun' => 'Лутран',
        'Club Vulkan' => 'Клуб Вулкан',
        'Vulkan Stars' => 'Вулкан Старс',
        'Vulkan Russia' => 'Вулкан Россия',
        'Atom' => 'Атом',
        'Azino888' => 'Азино888',
        'Beef' => 'Биф',
        'Betera' => 'Бетера',
        'Betwinner' => 'Бетвиннер',
        'Bigsbet' => 'Бигсбет',
        'Blitzred' => 'Блицред',
        'Boost' => 'Буст',
        'Casino7' => 'Казино7',
        'Casinora' => 'Казинора',
        'Crystalslot' => 'Кристалслот',
        'Dbbet' => 'Дббет',
        'Ezcash' => 'Изкэш',
        'Fairspin' => 'Фейрспин',
        'Fonbet' => 'Фонбет',
        'Fraga' => 'Фрага',
        'Frank' => 'Франк',
        'Goldfishka' => 'Голдфишка',
        'Grizzly' => 'Гризли',
        'Jackpoker' => 'Джекпокер',
        'Jet' => 'Джет',
        'Kilogram' => 'Килограм',
        'Laki' => 'Лаки',
        'Lilbet' => 'Лилбет',
        'Loft' => 'Лофт',
        'Luckybear' => 'Лакибир',
        'Luckyduck' => 'Лакидак',
        'Lukkly' => 'Лаккли',
        'Mad' => 'Мэд',
        'Marathon' => 'Марафон',
        'Martin' => 'Мартин',
        'Maxline' => 'Макслайн',
        'Mers' => 'Мерс',
        'Million' => 'Миллион',
        'Onlybets' => 'Онлибетс',
        'Pari' => 'Пари',
        'Parimatch' => 'Париматч',
        'Pokerok' => 'Покерок',
        'Shuffle' => 'Шаффл',
        'Slotgames' => 'Слотгеймс',
        'Slott' => 'Слотт',
        'Spacewin' => 'Спейсвин',
        'Spinbetter' => 'Спинбеттер',
        'Spinto' => 'Спинто',
        'Onetap' => 'Уантап',
        'Sweet' => 'Свит',
        'Tippy' => 'Типпи',
        'Tonplay' => 'Тонплей',
        'Volta' => 'Вольта',
        'Weiss' => 'Вайсс',
        'Win777' => 'Вин777',
        'Winity' => 'Винити',
        'Winline' => 'Винлайн',
        'Eva' => 'Ева',
        'Fenix' => 'Феникс',
    ];

    /**
     * Слова ТЕМЫ: по ним видно, что это вообще брендовый ключ казино, а не обычный запрос.
     * Сравнение по НАЧАЛУ слова, поэтому «казино», «слоты», «автоматами», «зеркала» ловятся разом.
     */
    private const THEME = [
        'казино', 'слот', 'автомат', 'ставк', 'зеркал', 'бонус', 'промокод', 'фриспин', 'кэшбэк',
        'кешбэк', 'депозит', 'бездеп', 'гэмбл', 'игров', 'вейджер', 'букмекер',
    ];

    /** Латинские слова темы (сравнение точное: «bet» — тема, «betera» — уже бренд). */
    private const THEME_EN = ['casino', 'kazino', 'slots', 'slot', 'bet', 'bets', 'betting', 'gambling'];

    /** Служебные слова: бывают в любом ключе и брендом не являются (тоже по началу слова). */
    private const FILLER = [
        'официальн', 'оффициальн', 'офицальн', 'регистрац', 'зарегистр', 'бесплатн', 'мобильн',
        'актуальн', 'рабоч', 'приложени', 'отзыв', 'скачат', 'скачив', 'вывод', 'пополн', 'лицензи',
        'играт', 'выигр', 'демо', 'лучш', 'личн', 'кабинет',
    ];

    /** Служебные слова целиком — короткие, по началу слова их сравнивать нельзя. */
    private const FILLER_EXACT = [
        'сайт', 'site', 'online', 'онлайн', 'игры', 'игра', 'деньги', 'денег', 'рубли', 'сегодня',
        'сейчас', 'тут', 'здесь', 'ещё', 'еще', 'все', 'всё', 'на', 'в', 'и', 'с', 'у', 'о', 'для',
        'без', 'как', 'где', 'что', 'это', 'от', 'до', 'по', 'за', 'россия', 'рф', 'ru', 'com',
        'www', 'app', 'login', 'mirror', 'bonus', 'play', 'вход', 'войти', 'топ', 'новое', 'новый',
    ];

    /**
     * Канонический ключ бренда по поисковому запросу; '' — бренда в запросе не видно.
     */
    public static function of(string $query): string
    {
        $words = self::words($query);
        if ($words === []) {
            return '';
        }
        // Известный бренд: сначала самые длинные названия («Вулкан Вегас» важнее «Вулкана»).
        $aliases = self::aliases();
        for ($len = self::MAX_WORDS; $len >= 1; $len--) {
            for ($i = 0; $i + $len <= count($words); $i++) {
                $key = self::normalize(implode('', array_slice($words, $i, $len)));
                if ($key !== '' && isset($aliases[$key])) {
                    return $aliases[$key];
                }
            }
        }
        // Неизвестный бренд: остаток запроса без служебных слов. Берём его, только если в запросе
        // ЕСТЬ слово темы («казино», «зеркало», «слоты») — без него это обычный запрос, а не
        // брендовый ключ, и «пластиковые окна москва» брендом не станут.
        if (!self::hasTheme($words)) {
            return '';
        }
        $rest = [];
        foreach ($words as $word) {
            if (!self::isStop($word) && mb_strlen($word) >= 3) {
                $rest[] = $word;
            }
        }
        if ($rest === [] || count($rest) > 2) {
            return ''; // три слова и больше — это описание, а не название бренда
        }

        return self::normalize(implode('', $rest));
    }

    /**
     * Нормализованное написание: транслит кириллицы, только буквы и цифры, c/q→k, y→i, w→v,
     * сдвоенные буквы схлопнуты. Цифры сохраняются — они часть названия (1xBet, Azino777, 7K).
     */
    public static function normalize(string $name): string
    {
        $map = [
            'а' => 'a', 'б' => 'b', 'в' => 'v', 'г' => 'g', 'д' => 'd', 'е' => 'e', 'ё' => 'e',
            'ж' => 'zh', 'з' => 'z', 'и' => 'i', 'й' => 'i', 'к' => 'k', 'л' => 'l', 'м' => 'm',
            'н' => 'n', 'о' => 'o', 'п' => 'p', 'р' => 'r', 'с' => 's', 'т' => 't', 'у' => 'u',
            'ф' => 'f', 'х' => 'h', 'ц' => 'c', 'ч' => 'ch', 'ш' => 'sh', 'щ' => 'sch', 'ъ' => '',
            'ы' => 'i', 'ь' => '', 'э' => 'e', 'ю' => 'yu', 'я' => 'ya',
        ];
        $text = strtr(mb_strtolower(trim($name)), $map);
        $text = (string) preg_replace('~[^a-z0-9]~u', '', $text);
        $text = strtr($text, ['c' => 'k', 'q' => 'k', 'y' => 'i', 'w' => 'v']);

        return (string) preg_replace('~(.)\1+~u', '$1', $text);
    }

    /**
     * Все известные написания => канонический ключ бренда (читается один раз за процесс).
     *
     * @return array<string, string>
     */
    public static function aliases(): array
    {
        static $cache = null;
        if ($cache !== null) {
            return $cache;
        }
        $cache = [];
        foreach (self::pairs() as $en => $ru) {
            $key = self::normalize((string) $en);
            if ($key === '') {
                continue;
            }
            $cache[$key] = $key;
            $ruKey = self::normalize((string) $ru);
            if ($ruKey !== '') {
                $cache[$ruKey] = $key;
            }
        }

        return $cache;
    }

    /**
     * Человеческое название бренда по ключу (латинское написание) — для списков в панели.
     */
    public static function label(string $key): string
    {
        static $labels = null;
        if ($labels === null) {
            $labels = [];
            foreach (self::pairs() as $en => $ru) {
                $labels[self::normalize((string) $en)] = (string) $en;
            }
        }

        return $labels[$key] ?? $key;
    }

    /**
     * Встроенные пары + пары из brand-pairs.txt рядом с проектом (строка латиницей, строка кириллицей).
     *
     * @return array<string, string>
     */
    private static function pairs(): array
    {
        static $pairs = null;
        if ($pairs !== null) {
            return $pairs;
        }
        $pairs = self::PAIRS;
        foreach ([getcwd() . '/' . self::FILE, dirname(__DIR__, 2) . '/' . self::FILE] as $file) {
            if (!is_file($file)) {
                continue;
            }
            $lines = [];
            foreach (preg_split('~\R~u', (string) file_get_contents($file)) ?: [] as $line) {
                $line = trim($line);
                if ($line !== '' && !str_starts_with($line, '#')) {
                    $lines[] = $line;
                }
            }
            for ($i = 0; $i + 1 < count($lines); $i += 2) {
                $pairs[$lines[$i]] = $lines[$i + 1];
            }
            break;
        }

        return $pairs;
    }

    /**
     * Слова запроса: буквы и цифры, в нижнем регистре.
     *
     * @return list<string>
     */
    private static function words(string $query): array
    {
        $parts = preg_split('~[^\p{L}\p{N}]+~u', mb_strtolower(trim($query)), -1, PREG_SPLIT_NO_EMPTY);

        return array_values($parts ?: []);
    }

    /** Служебное слово темы или год — брендом не считается. */
    private static function isStop(string $word): bool
    {
        if (in_array($word, self::FILLER_EXACT, true) || in_array($word, self::THEME_EN, true)) {
            return true;
        }
        foreach ([...self::THEME, ...self::FILLER] as $stem) {
            if (str_starts_with($word, $stem)) {
                return true;
            }
        }

        return preg_match('~^(19|20)\d{2}$~', $word) === 1;
    }

    /**
     * Есть ли в запросе слово темы — признак того, что это вообще брендовый ключ казино.
     *
     * @param list<string> $words
     */
    private static function hasTheme(array $words): bool
    {
        foreach ($words as $word) {
            if (in_array($word, self::THEME_EN, true)) {
                return true;
            }
            foreach (self::THEME as $stem) {
                if (str_starts_with($word, $stem)) {
                    return true;
                }
            }
        }

        return false;
    }
}

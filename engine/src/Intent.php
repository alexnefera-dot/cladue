<?php
declare(strict_types=1);

/**
 * Классификатор интента поисковых запросов — определяет, «на что ориентирован»
 * текст: на какие смысловые кластеры запросов он отвечает.
 * Запросы короткие, поэтому сопоставление идёт по подстрокам-основам.
 * Порядок тем = приоритет (первое совпадение выигрывает).
 */
final class Intent
{
    /** @var array<string,array{label:string,triggers:string[]}> */
    public const THEMES = [
        'bonus'    => ['label' => 'Бонусы / промокоды', 'triggers' => ['бонус','промокод','promokod','promo','фриспин','freespin','фрибет','бездеп','подарок','акци','кэшбэк','cashback']],
        'app'      => ['label' => 'Приложение / скачать', 'triggers' => ['скача','приложен','apk','андроид','android','ios','айфон','мобильн','app','apk']],
        'money'    => ['label' => 'Деньги / вывод', 'triggers' => ['вывод','депозит','пополн','деньги','вейджер','отыгрыш','минимальн','налог']],
        'registr'  => ['label' => 'Регистрация / кабинет', 'triggers' => ['регистрац','кабинет','аккаунт','профиль','верификац']],
        'access'   => ['label' => 'Доступ / зеркало', 'triggers' => ['зеркал','вход','войти','рабоч','доступ','обход','блокиров','ссылк']],
        'official' => ['label' => 'Офиц. сайт', 'triggers' => ['официальн','сайт','online','онлайн','com','ru']],
        'betting'  => ['label' => 'Ставки / спорт', 'triggers' => ['ставк','спорт','линия','коэффициент','экспресс','матч','футбол','букмекер','бк']],
        'games'    => ['label' => 'Игры / казино', 'triggers' => ['слот','автомат','игр','казино','casino','демо','рулетк','покер','crash','краш','aviator','авиатор','джекпот']],
        'support'  => ['label' => 'Поддержка / отзывы', 'triggers' => ['отзыв','поддержк','служба','жалоб','развод','мошенник','лохотрон','честн']],
    ];

    /**
     * Тема запроса или 'brand' (запрос состоит только из маркеров бренда) / 'other'.
     * @param string[] $brandKeys маркеры бренда (латиница + кириллица), напр. ['1win','1вин']
     */
    public static function classify(string $query, array $brandKeys = []): string
    {
        $q = mb_strtolower(trim($query), 'UTF-8');
        // чистый бренд: все токены запроса — маркеры бренда
        if ($brandKeys) {
            $keySet = array_flip(array_map(fn($k) => mb_strtolower((string) $k, 'UTF-8'), $brandKeys));
            $qTokens = preg_split('/\s+/u', $q) ?: [];
            $onlyBrand = $qTokens !== [];
            foreach ($qTokens as $t) {
                if (!isset($keySet[$t])) { $onlyBrand = false; break; }
            }
            if ($onlyBrand) { return 'brand'; }
        }
        foreach (self::THEMES as $key => $def) {
            foreach ($def['triggers'] as $tr) {
                if (mb_strpos($q, $tr, 0, 'UTF-8') !== false) { return $key; }
            }
        }
        return 'other';
    }

    /** транслит-хинт из имени файла/URL -> тема (когда контент не дал сигнала) */
    private const HINTS = [
        'access'  => ['zerkalo','zerkala','vhod','vxod','login','dostup','mirror'],
        'registr' => ['registr','reg','signup','account'],
        'bonus'   => ['bonus','promo','promokod','freespin','cashback'],
        'app'     => ['app','skachat','download','mobile','apk','android','ios'],
        'games'   => ['slot','game','casino','igr','ruletka','poker'],
        'betting' => ['stavk','bet','sport','line'],
        'money'   => ['vyvod','deposit','popoln','money'],
        'official'=> ['main','index','home','official'],
    ];

    /**
     * Доминирующая тема текста: тема с наибольшим числом срабатываний триггеров.
     * Если контент не дал сигнала — пробуем хинт из имени/URL.
     */
    public static function dominant(string $text, array $brandKeys = [], string $hint = ''): string
    {
        // 1) явный хинт из имени/URL (страница названа по назначению) — приоритет
        $h = mb_strtolower($hint, 'UTF-8');
        foreach (self::HINTS as $theme => $words) {
            foreach ($words as $w) {
                if (mb_strpos($h, $w, 0, 'UTF-8') !== false) { return $theme; }
            }
        }
        // 2) иначе — доминирующая тема по контенту
        $t = mb_strtolower($text, 'UTF-8');
        $best = 'other'; $bestN = 0;
        foreach (self::THEMES as $key => $def) {
            $n = 0;
            foreach ($def['triggers'] as $tr) { $n += substr_count($t, $tr); }
            if ($n > $bestN) { $bestN = $n; $best = $key; }
        }
        return $best;
    }

    /**
     * Профиль ориентации: распределение кликов покрытых запросов по темам.
     * @param array<int,array{0:string,1:int}> $foundQueries [[query, clicks], ...]
     * @param string[] $brandKeys маркеры бренда
     * @return array<string,array{clicks:int,share:float,label:string}>
     */
    public static function profile(array $foundQueries, array $brandKeys = []): array
    {
        $byTheme = [];
        $total = 0;
        foreach ($foundQueries as [$q, $clicks]) {
            $clicks = (int) $clicks;
            $theme = self::classify((string) $q, $brandKeys);
            $byTheme[$theme] = ($byTheme[$theme] ?? 0) + $clicks;
            $total += $clicks;
        }
        arsort($byTheme);
        $out = [];
        foreach ($byTheme as $theme => $clicks) {
            $out[$theme] = [
                'clicks' => $clicks,
                'share'  => $total ? round($clicks / $total * 100, 1) : 0.0,
                'label'  => $theme === 'brand' ? 'Брендовые' : ($theme === 'other' ? 'Прочее' : self::THEMES[$theme]['label']),
            ];
        }
        return $out;
    }
}

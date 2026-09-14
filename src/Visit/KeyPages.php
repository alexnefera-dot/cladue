<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Model\Site;

/**
 * Ключевые страницы шаблона: регистрация, вход, зеркало, бонусы, приложение, слоты. Именно на них
 * ссылается готовый контент, поэтому пропущенная страница — это «ссылка в никуда» в статье.
 *
 * Страница может не попасть в выгрузку по двум причинам: ссылку на неё не нашли в меню (в отчёте
 * «нет ссылки») или страница не открылась (таймаут, блок, 404 — «не скачалась», её можно добрать).
 * Отчёт показывает и то, и другое, чтобы сайт можно было либо докачать, либо убрать до выгрузки.
 */
final class KeyPages
{
    /**
     * Ключ → подпись и слова, по которым узнаём страницу в адресе (порядок важен: сначала более
     * узкие разделы, иначе «бонусы» уедут в «приложение»).
     *
     * @var array<string, array{label: string, words: list<string>}>
     */
    public const PAGES = [
        'registracia' => ['label' => 'регистрация', 'words' => ['registracia', 'registration', 'registr', 'register', 'signup', 'регистрац']],
        'vhod' => ['label' => 'вход', 'words' => ['vhod', 'login', 'signin', 'enter', 'vxod', 'vojti', 'войти', 'вход', 'авторизац']],
        'zerkalo' => ['label' => 'зеркало', 'words' => ['zerkalo', 'mirror', 'зеркало']],
        'bonus' => ['label' => 'бонусы', 'words' => ['bonus', 'бонус', 'promo', 'акци']],
        'app' => ['label' => 'приложение', 'words' => ['app', 'application', 'download', 'apk', 'prilozhenie', 'приложение', 'скачать']],
        'slots' => ['label' => 'слоты', 'words' => ['slots', 'slot', 'games', 'game', 'igry', 'igrov', 'igrat', 'avtomat', 'play', 'играть', 'игры', 'автомат']],
    ];

    /** Ключевая страница по адресу или имени файла; null — обычная страница. */
    public static function of(string $urlOrFile): ?string
    {
        $path = $urlOrFile;
        if (preg_match('~^[a-z][a-z0-9+.\-]*://~i', $urlOrFile) === 1) {
            $path = (string) parse_url($urlOrFile, PHP_URL_PATH);
        }
        $path = explode('?', $path)[0];
        $segments = array_values(array_filter(explode('/', $path), static fn (string $s): bool => trim($s) !== ''));
        if ($segments === []) {
            return null;
        }
        $last = (string) end($segments);
        $last = preg_replace('~\.(html?|php|phtml|aspx?)$~i', '', $last) ?? $last;
        $key = mb_strtolower((string) preg_replace('~[^\p{L}\p{N}]+~u', '', $last));
        if ($key === '') {
            return null;
        }
        foreach (self::PAGES as $name => $page) {
            foreach ($page['words'] as $word) {
                if (str_contains($key, $word)) {
                    return $name;
                }
            }
        }

        return null;
    }

    public static function label(string $name): string
    {
        return self::PAGES[$name]['label'] ?? $name;
    }

    /**
     * Стандартный адрес ключевой страницы — по нему её можно добрать, если ссылки в меню не нашлось.
     * Корень берём у самого сайта (схема и порт как у уже открытых страниц), а не «https://host».
     */
    public static function url(string $rootUrl, string $name): string
    {
        return rtrim($rootUrl, '/') . '/' . $name;
    }

    /**
     * Состояние ключевых страниц сайта: ok — скачана, failed — ссылка была, но страница не открылась
     * (можно добрать), none — ссылки на неё не нашли.
     *
     * @param list<array<string, mixed>> $visits
     * @return array<string, string>
     */
    public static function statuses(array $visits): array
    {
        $out = array_fill_keys(array_keys(self::PAGES), 'none');
        foreach ($visits as $visit) {
            $visit = (array) $visit;
            $file = (string) ($visit['html_file'] ?? '');
            $name = self::of($file !== '' ? basename($file) : (string) ($visit['url'] ?? ''));
            if ($name === null) {
                continue;
            }
            if ($visit['ok'] ?? false) {
                $out[$name] = 'ok';
            } elseif ($out[$name] !== 'ok') {
                $out[$name] = 'failed';
            }
        }

        return $out;
    }

    /**
     * Каких ключевых страниц у сайта нет (в порядке PAGES).
     *
     * @param list<array<string, mixed>> $visits
     * @return list<string>
     */
    public static function missing(array $visits): array
    {
        $missing = [];
        foreach (self::statuses($visits) as $name => $status) {
            if ($status !== 'ok') {
                $missing[] = $name;
            }
        }

        return $missing;
    }

    /**
     * Сколько сайтов недосчитались каждой ключевой страницы: ['registracia' => 213, 'vhod' => 115, …].
     * Наши шаблоны и сайты, которые вообще не открывались, не считаются.
     *
     * @param array<int|string, Site> $sites
     * @return array<string, int>
     */
    public static function histogram(array $sites): array
    {
        $hist = array_fill_keys(array_keys(self::PAGES), 0);
        foreach ($sites as $site) {
            if ($site->own || $site->visits === []) {
                continue;
            }
            foreach (self::missing(array_map(static fn ($v): array => (array) $v, $site->visits)) as $name) {
                $hist[$name]++;
            }
        }

        return array_filter($hist, static fn (int $n): bool => $n > 0);
    }

    /** «регистрация — 213, вход — 115»; '' — если всё на месте. */
    public static function histogramText(array $hist): string
    {
        arsort($hist);
        $parts = [];
        foreach ($hist as $name => $count) {
            $parts[] = self::label((string) $name) . ' — ' . $count;
        }

        return implode(', ', $parts);
    }
}

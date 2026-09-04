<?php

declare(strict_types=1);

namespace YandexSites\Content;

/**
 * Подготовка контента для шаблона: из скачанной HTML-страницы оставляет только тело статьи
 * (после </h1> и до блока «Популярные запросы»), удаляет блок слотов, приводит ссылки к
 * шести относительным путям и подставляет переменные вместо домена, даты и названий бренда.
 *
 * Всё по ручному мануалу подготовки контента; замены бренда устойчивы к регистру и к смешению
 * латиницы/кириллицы в похожих буквах (STAKE / STAKЕ).
 */
final class ContentCleaner
{
    /** Единственно допустимые относительные ссылки в готовой статье. */
    public const ALLOWED_LINKS = ['/vhod', '/registracia', '/main', '/app', '/slots', '/zerkalo'];

    /**
     * Ключевые слова путь → варианты (в нормализованном виде, без разделителей и регистра).
     * Порядок важен: более специфичные разделы раньше.
     *
     * @var array<string, list<string>>
     */
    private const LINK_RULES = [
        '/registracia' => ['registracia', 'registration', 'registr', 'register', 'signup', 'регистрац'],
        '/vhod' => ['vhod', 'login', 'signin', 'enter', 'vxod', 'vojti', 'войти', 'вход', 'авторизац'],
        '/zerkalo' => ['zerkalo', 'mirror', 'зеркало'],
        '/app' => ['app', 'application', 'download', 'bonus', 'apk', 'prilozhenie', 'приложение', 'скачать'],
        '/slots' => ['slots', 'slot', 'games', 'game', 'igry', 'igrat', 'play', 'играть', 'игры', 'игровые', 'автоматы'],
        '/main' => ['main', 'home', 'index', 'glavnaya', 'главная'],
    ];

    /** Похожие буквы латиница↔кириллица (в нижнем регистре) — для устойчивого поиска бренда. */
    private const HOMOGLYPHS = [
        'a' => 'aа', 'e' => 'eе', 'o' => 'oо', 'c' => 'cс', 'p' => 'pр', 'x' => 'xх',
        'y' => 'yу', 'k' => 'kк', 'm' => 'mм', 't' => 'tт', 'h' => 'hн', 'b' => 'bв',
    ];

    /**
     * Полная очистка страницы. Возвращает тело статьи или '' — если статья не найдена (нет <h1>).
     *
     * @param array{domain?: string, hosts?: list<string>, brand_ru?: string, brand_en?: string, extra_brands?: list<string>, remove_slots?: bool} $opt
     */
    public function clean(string $html, array $opt = []): string
    {
        $body = $this->extractArticle($html);
        if ($body === '') {
            return '';
        }
        if ($opt['remove_slots'] ?? true) {
            $body = $this->removeSlots($body);
        }
        $body = $this->normalizeLinks($body);
        $body = $this->applyReplacements($body, $opt);

        return trim($body);
    }

    /**
     * Тело статьи: всё после первого </h1> и до заголовка «Популярные запросы»; без служебных тегов.
     */
    public function extractArticle(string $html): string
    {
        if (preg_match('~</h1\s*>~i', $html, $m, PREG_OFFSET_CAPTURE) !== 1) {
            return '';
        }
        $body = substr($html, $m[0][1] + strlen($m[0][0]));

        // Обрезаем от заголовка, который вводит «Популярные запросы».
        if (preg_match('~Популярн\w*\s+запрос~iu', $body, $mm, PREG_OFFSET_CAPTURE) === 1) {
            $before = substr($body, 0, $mm[0][1]);
            if (preg_match_all('~<h[1-6]\b~i', $before, $hm, PREG_OFFSET_CAPTURE) > 0) {
                $body = substr($body, 0, (int) end($hm[0])[1]);
            } else {
                $body = $before;
            }
        }

        // Убираем служебные блоки и обвязку.
        $body = preg_replace('~<(script|style|noscript|template|svg|header|footer|form)\b[^>]*>.*?</\1>~isu', '', $body) ?? $body;
        $body = preg_replace('~</?(?:body|html|main|article|section)\b[^>]*>~i', '', $body) ?? $body;

        return trim($body);
    }

    /**
     * Удаляет секцию слотов/игр: заголовок про слоты и содержимое до следующего заголовка.
     */
    public function removeSlots(string $html): string
    {
        return preg_replace(
            '~<h[1-6][^>]*>(?:(?!</h[1-6]>).)*?(?:слот|игровы|игры|автомат|slots?|games?)(?:(?!</h[1-6]>).)*?</h[1-6]\s*>.*?(?=<h[1-6]\b|$)~isu',
            '',
            $html,
        ) ?? $html;
    }

    /**
     * Приводит все ссылки <a href> к одному из шести относительных путей по смыслу.
     */
    public function normalizeLinks(string $html): string
    {
        return preg_replace_callback(
            '~(<a\b[^>]*?\shref\s*=\s*)(["\'])(.*?)\2~is',
            fn (array $m): string => $m[1] . $m[2] . $this->mapLink($m[3]) . $m[2],
            $html,
        ) ?? $html;
    }

    /**
     * Одна ссылка → относительный путь из списка допустимых (по последнему сегменту и смыслу).
     */
    public function mapLink(string $href): string
    {
        $href = trim(html_entity_decode($href, ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        $path = $href;
        if (str_starts_with($href, '//')) {
            $href = 'https:' . $href;
        }
        if (preg_match('~^[a-z][a-z0-9+.\-]*:~i', $href) === 1) {
            $path = (string) parse_url($href, PHP_URL_PATH);
        } elseif (($q = strpos($path, '?')) !== false) {
            $path = substr($path, 0, $q);
        }
        $segments = array_values(array_filter(explode('/', $path), static fn (string $s): bool => trim($s) !== ''));
        $last = $segments === [] ? '' : (string) end($segments);
        $last = preg_replace('~\.(html?|php|phtml|aspx?)$~i', '', $last) ?? $last;
        $key = mb_strtolower(preg_replace('~[^\p{L}\p{N}]+~u', '', $last) ?? $last);

        foreach (self::LINK_RULES as $target => $words) {
            foreach ($words as $word) {
                if ($key !== '' && str_contains($key, $word)) {
                    return $target;
                }
            }
        }
        if (in_array('/' . $key, self::ALLOWED_LINKS, true)) {
            return '/' . $key;
        }

        return '/main';
    }

    /**
     * Замены домена, даты и бренда на переменные шаблона.
     *
     * @param array{domain?: string, hosts?: list<string>, brand_ru?: string, brand_en?: string, extra_brands?: list<string>} $opt
     */
    public function applyReplacements(string $html, array $opt): string
    {
        // Дата дд.мм.гггг → %date%
        $html = preg_replace('~\b\d{1,2}\.\d{1,2}\.\d{4}\b~u', '%date%', $html) ?? $html;

        // Домены (сначала — иначе бренд «съест» часть домена) → %domain_name%
        $domains = array_merge([(string) ($opt['domain'] ?? '')], (array) ($opt['hosts'] ?? []));
        $domains = array_values(array_unique(array_filter(array_map('trim', $domains), static fn (string $d): bool => $d !== '')));
        usort($domains, static fn (string $a, string $b): int => mb_strlen($b) <=> mb_strlen($a));
        foreach ($domains as $domain) {
            $html = preg_replace('~(?:www\.)?' . preg_quote($domain, '~') . '~iu', '%domain_name%', $html) ?? $html;
        }

        // Бренд: русский, английский и дополнительные (опечатки/сторонние) — устойчиво к регистру и гомоглифам
        if (($opt['brand_ru'] ?? '') !== '') {
            $html = $this->replaceBrand($html, (string) $opt['brand_ru'], '%brand_name_ru%');
        }
        if (($opt['brand_en'] ?? '') !== '') {
            $html = $this->replaceBrand($html, (string) $opt['brand_en'], '%brand_name_en%');
        }
        foreach ($opt['extra_brands'] ?? [] as $brand) {
            $brand = trim((string) $brand);
            if ($brand !== '') {
                $html = $this->replaceBrand($html, $brand, $this->hasCyrillic($brand) ? '%brand_name_ru%' : '%brand_name_en%');
            }
        }

        return $html;
    }

    private function replaceBrand(string $html, string $brand, string $variable): string
    {
        $pattern = $this->homoglyphPattern($brand);
        if ($pattern === '') {
            return $html;
        }

        return preg_replace('~' . $pattern . '~iu', $variable, $html) ?? $html;
    }

    /**
     * Регэксп по названию бренда: каждая похожая буква — класс из латиницы и кириллицы (STAKE ≡ STAKЕ).
     */
    private function homoglyphPattern(string $brand): string
    {
        $out = '';
        foreach (preg_split('~~u', mb_strtolower($brand), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
            $out .= isset(self::HOMOGLYPHS[$ch]) ? '[' . self::HOMOGLYPHS[$ch] . ']' : preg_quote($ch, '~');
        }

        return $out;
    }

    private function hasCyrillic(string $text): bool
    {
        return preg_match('~\p{Cyrillic}~u', $text) === 1;
    }
}

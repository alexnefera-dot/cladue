<?php

declare(strict_types=1);

namespace YandexSites\Content;

use YandexSites\Filter\Domains;

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
     * Собирает опции для clean() с автоопределением бренда по странице и домену — чтобы можно было
     * просто нажать «Очистить» без ручного ввода. Непустые $override перекрывают автозначения.
     * $moreHtml — остальные страницы сайта: бренд ищется по ним тоже, если главная оказалась
     * заглушкой/редиректом.
     *
     * @param array<string, mixed> $override
     * @param list<string> $moreHtml
     * @return array<string, mixed>
     */
    public static function autoOptions(string $html, string $host, array $override = [], array $moreHtml = []): array
    {
        $brand = (new BrandDetector())->detect($html, $host, $moreHtml);
        $hosts = $host !== '' ? array_values(array_unique([$host, Domains::registrable(Domains::normalize($host))])) : [];
        $opts = [
            'domain' => $host,
            'hosts' => $hosts,
            'brand_en' => $brand['en'],
            'brand_ru' => $brand['ru'],
            // Посторонние бренды ловятся автоматически по списку известных (+ файл brands.txt).
            'extra_brands' => KnownBrands::all(),
        ];
        foreach ($override as $key => $value) {
            if ($key === 'extra_brands') {
                $opts['extra_brands'] = array_values(array_unique(array_merge($opts['extra_brands'], (array) $value)));
            } elseif ($value !== '' && $value !== null && $value !== []) {
                $opts[$key] = $value;
            }
        }

        return $opts;
    }

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

        // Комментарии (Яндекс.Метрика, Google Analytics и т.п.).
        $body = preg_replace('~<!--.*?-->~s', '', $body) ?? $body;
        // Через DOM убираем всё, что не относится к статье: изображения и медиа, интерактив (кнопки,
        // формы), модалки/поповеры, подвал сайта, контакты, облако тегов, «поделиться», куки-плашки.
        $body = $this->stripNonArticle($body);

        return trim($body);
    }

    /** Классы/id (по токенам), которые выкидываем как не-статью: контакты, облако тегов, соцсети и т.п. */
    private const JUNK_TOKENS = [
        'tag', 'tags', 'tagcloud', 'tags-list', 'taglist', 'contact', 'contacts', 'contatti',
        'social', 'socials', 'share', 'sharing', 'popup', 'modal', 'overlay', 'backdrop',
        'cookie', 'cookies', 'subscribe', 'newsletter', 'breadcrumb', 'breadcrumbs', 'sidebar',
        'banner', 'advert', 'ads', 'promo-modal', 'age', 'agegate',
        // Кнопки-призывы и «счётчики срочности» (фейковый джекпот/таймер) — не тело статьи;
        // из-за них после очистки оставались артефакты вроде «spot-cta-number 12345».
        'cta', 'countdown', 'timer', 'ticker',
    ];

    /**
     * Убирает из фрагмента статьи не-контент: медиа, интерактив, модалки, подвал, контакты, теги.
     * DOM (а не регэкспы) — потому что модалки/блоки бывают с вложенными div, которые регэксп не осилит.
     */
    private function stripNonArticle(string $fragment): string
    {
        $fragment = trim($fragment);
        if ($fragment === '') {
            return '';
        }
        $doc = new \DOMDocument();
        $prev = libxml_use_internal_errors(true);
        $loaded = $doc->loadHTML('<?xml encoding="UTF-8"?><div id="ys-root">' . $fragment . '</div>', LIBXML_NOWARNING | LIBXML_NOERROR);
        libxml_clear_errors();
        libxml_use_internal_errors($prev);
        $root = $doc->getElementById('ys-root');
        if (!$loaded || $root === null) {
            return $fragment;
        }
        $xp = new \DOMXPath($doc);
        $remove = [];
        // Медиа, интерактив, служебные и медиа-теги.
        foreach ($xp->query('//script|//style|//noscript|//template|//svg|//header|//form|//button|//input|//select|//textarea|//label|//iframe|//img|//picture|//figure|//video|//audio|//canvas|//object|//embed|//map|//source|//address|//dialog') as $n) {
            $remove[] = $n;
        }
        // Подвал сайта — но подпись внутри цитаты (<blockquote><footer>) оставляем.
        foreach ($xp->query('//footer[not(ancestor::blockquote)]') as $n) {
            $remove[] = $n;
        }
        // Модалки/поповеры.
        foreach ($xp->query('//*[@role="dialog" or @aria-modal="true"]') as $n) {
            $remove[] = $n;
        }
        // Контакты, облако тегов, соцсети и пр. — по токенам класса/id.
        foreach ($xp->query('//*[@class or @id]') as $n) {
            if (!$n instanceof \DOMElement) {
                continue;
            }
            $tokens = preg_split('~[\s_\-]+~u', mb_strtolower($n->getAttribute('class') . ' ' . $n->getAttribute('id'))) ?: [];
            if (array_intersect($tokens, self::JUNK_TOKENS) !== []) {
                $remove[] = $n;
            }
        }
        foreach ($remove as $n) {
            $n->parentNode?->removeChild($n);
        }
        $out = '';
        foreach (iterator_to_array($root->childNodes) as $child) {
            $out .= $doc->saveHTML($child);
        }

        return $out;
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

        // Домены (сначала — иначе бренд «съест» часть домена) → %domain_name%.
        // Съедаем и поддомен целиком: kush.casinozsd.buzz → %domain_name%, а не «kush.%domain_name%».
        $domains = array_merge([(string) ($opt['domain'] ?? '')], (array) ($opt['hosts'] ?? []));
        $domains = array_values(array_unique(array_filter(array_map('trim', $domains), static fn (string $d): bool => $d !== '')));
        usort($domains, static fn (string $a, string $b): int => mb_strlen($b) <=> mb_strlen($a));
        foreach ($domains as $domain) {
            $html = preg_replace('~(?<![a-z0-9.\-])(?:[a-z0-9\-]+\.)*' . preg_quote($domain, '~') . '~iu', '%domain_name%', $html) ?? $html;
        }

        // Бренд: русский, английский и дополнительные (опечатки/сторонние) — устойчиво к регистру и гомоглифам.
        // Параллельно копим латинские слитные бренды, чтобы одним проходом поймать и раздельное написание
        // («cryptoboss» → «Crypto Boss», «vulkanvegas» → «Vulkan Vegas», «moneyx» → «Money X»).
        $spaced = [];
        if (($opt['brand_ru'] ?? '') !== '') {
            $html = $this->replaceBrand($html, (string) $opt['brand_ru'], '%brand_name_ru%');
        }
        if (($opt['brand_en'] ?? '') !== '') {
            $b = (string) $opt['brand_en'];
            $html = $this->replaceBrand($html, $b, '%brand_name_en%');
            $this->addSpacedTarget($spaced, $b, '%brand_name_en%');
        }
        // Сначала длинные названия, потом короткие: иначе «вулкан» съест первое слово «вулкан вегас»
        // и оставит «вегас» (составной бренд должен подставиться раньше своего однословного префикса).
        $extra = array_values(array_filter(array_map('trim', array_map('strval', $opt['extra_brands'] ?? [])), static fn (string $b): bool => $b !== ''));
        usort($extra, static fn (string $a, string $b): int => mb_strlen($b) <=> mb_strlen($a));
        foreach ($extra as $brand) {
            $var = $this->hasCyrillic($brand) ? '%brand_name_ru%' : '%brand_name_en%';
            $html = $this->replaceBrand($html, $brand, $var);
            $this->addSpacedTarget($spaced, $brand, $var);
        }
        if ($spaced !== []) {
            $html = $this->replaceSpacedBrands($html, $spaced);
        }

        return $html;
    }

    private function replaceBrand(string $html, string $brand, string $variable): string
    {
        $pattern = $this->homoglyphPattern($brand);
        if ($pattern === '') {
            return $html;
        }

        // Границы слова, чтобы не задевать бренд внутри других слов (stake ≠ mistaken).
        return preg_replace('~(?<![\p{L}\p{N}])(?:' . $pattern . ')(?![\p{L}\p{N}])~iu', $variable, $html) ?? $html;
    }

    /**
     * Добавляет слитный латинский бренд (≥6 букв) в набор для поиска раздельного написания:
     * склейка(fold) → переменная. Короткие и кириллические не берём (риск ложных совпадений / fold лоссовый).
     *
     * @param array<string, string> $targets
     */
    private function addSpacedTarget(array &$targets, string $brand, string $variable): void
    {
        if (str_contains($brand, ' ') || $this->hasCyrillic($brand)) {
            return;
        }
        $fold = $this->foldBrand($brand);
        if (mb_strlen($fold) >= 6) {
            $targets[$fold] = $variable;
        }
    }

    /**
     * Ловит РАЗДЕЛЬНОЕ написание слитных брендов: метка домена «cryptoboss» → «Crypto Boss»,
     * «vulkanvegas» → «Vulkan Vegas», «moneyx» → «Money X». Чтобы не задеть обычные словосочетания
     * («good win» для бренда goodwin), требуем, чтобы КАЖДОЕ слово начиналось с ЗАГЛАВНОЙ (бренд —
     * имя собственное), а склейка слов (гомоглиф-нормализованная) в точности совпадала с брендом.
     * Один проход по тексту на все бренды сразу.
     *
     * @param array<string, string> $targets склейка(fold) → переменная
     */
    private function replaceSpacedBrands(string $html, array $targets): string
    {
        return preg_replace_callback(
            '~(?<![\p{L}\p{N}])(\p{Lu}[\p{L}\p{N}]*(?:[ \x{00A0}\-]\p{Lu}[\p{L}\p{N}]*){1,2})(?![\p{L}\p{N}])~u',
            fn (array $m): string => $targets[$this->foldBrand($m[1])] ?? $m[1],
            $html,
        ) ?? $html;
    }

    /** Нормализует бренд для сравнения: нижний регистр, кириллические двойники → латиница, без не-букв. */
    private function foldBrand(string $text): string
    {
        $text = mb_strtolower($text);
        $map = [];
        foreach (self::HOMOGLYPHS as $latin => $set) {
            foreach (preg_split('~~u', $set, -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
                if ($ch !== $latin) {
                    $map[$ch] = $latin;
                }
            }
        }

        return (string) preg_replace('~[^a-z0-9]~u', '', strtr($text, $map));
    }

    /**
     * Регэксп по названию бренда: каждая похожая буква — класс из латиницы и кириллицы (STAKE ≡ STAKЕ),
     * пробел — любой пробельный промежуток (play fortuna ≡ play&nbsp;fortuna).
     */
    private function homoglyphPattern(string $brand): string
    {
        $out = '';
        foreach (preg_split('~~u', mb_strtolower(trim($brand)), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
            if (trim($ch) === '') {
                $out .= '\s+';
            } elseif (isset(self::HOMOGLYPHS[$ch])) {
                $out .= '[' . self::HOMOGLYPHS[$ch] . ']';
            } else {
                $out .= preg_quote($ch, '~');
            }
        }

        return $out;
    }

    private function hasCyrillic(string $text): bool
    {
        return preg_match('~\p{Cyrillic}~u', $text) === 1;
    }
}

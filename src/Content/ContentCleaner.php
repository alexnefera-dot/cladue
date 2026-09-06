<?php

declare(strict_types=1);

namespace YandexSites\Content;

use YandexSites\Filter\Domains;

/**
 * Подготовка контента для шаблона — по ручному мануалу и СТРОГО в его порядке (половина ошибок
 * берётся из перестановки шагов):
 *
 *  1. Тело статьи: после первого </h1> и до «Популярные запросы»; FAQ — вторым потоком (если блок
 *     вопросов-ответов не попал в срез или есть только в JSON-LD, он вынимается и приклеивается);
 *     без мусора (картинки/медиа, интерактив, модалки, подвал сайта, меню, контакты, облако тегов,
 *     CTA-виджеты) и без секции слотов.
 *  2. Подстановка бренда/домена/даты — по ВСЕМУ: и по телу, и по FAQ.
 *  3. Снести служебное: script, style, meta, link, noscript, img, hr, br, caption.
 *  4. Развернуть контейнеры (снять тег, оставить содержимое): div, section, article, aside, footer,
 *     header, span, thead, tbody, tfoot, figure, small, q, abbr, time, cite, code, kbd, samp, var,
 *     sup, sub, u, s, mark, ins, del, dfn.
 *  5. Оформление: em/i → обычный текст, b → strong.
 *  6. Заголовки: h1 → h2, затем h4/h5/h6 → h3.
 *  7. Снять атрибуты со всех тегов, кроме href у <a>.
 *  8. Ссылки: внутренние → один из путей (/vhod, /registracia, /, /app, /slots, /zerkalo), «/main» → «/»;
 *     внешние — развернуть в текст.
 *
 * Замены бренда устойчивы к регистру, к смешению латиницы/кириллицы в похожих буквах (STAKE / STAKЕ),
 * к падежам своего русского бренда и к раздельному написанию слитной метки (cryptoboss → Crypto Boss).
 */
final class ContentCleaner
{
    /** Единственно допустимые относительные ссылки в готовой статье (главная — «/», а не «/main»). */
    public const ALLOWED_LINKS = ['/vhod', '/registracia', '/', '/app', '/slots', '/zerkalo'];

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
        '/' => ['main', 'home', 'index', 'glavnaya', 'главная'],
    ];

    /** Похожие буквы латиница↔кириллица (в нижнем регистре) — для устойчивого поиска бренда. */
    private const HOMOGLYPHS = [
        'a' => 'aа', 'e' => 'eе', 'o' => 'oо', 'c' => 'cс', 'p' => 'pр', 'x' => 'xх',
        'y' => 'yу', 'k' => 'kк', 'm' => 'mм', 't' => 'tт', 'h' => 'hн', 'b' => 'bв',
    ];

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

    /** Шаг 3: служебные теги — удалить вместе с содержимым (figcaption — подпись к уже удалённой картинке). */
    private const SERVICE_TAGS = ['script', 'style', 'meta', 'link', 'noscript', 'img', 'hr', 'br', 'caption', 'figcaption'];

    /**
     * Шаг 4: блочные контейнеры — развернуть. На их границах ставим перевод строки, иначе текст соседних
     * блоков склеивается в одно слово («Криптобосс» + «лучшее» → «Криптобосслучшее»).
     */
    private const BLOCK_UNWRAP = ['div', 'section', 'article', 'aside', 'footer', 'header', 'main', 'thead', 'tbody', 'tfoot', 'figure'];

    /** Шаг 4: строчные контейнеры — развернуть без разделителей (иначе разорвём слово: Крип<span>то</span>босс). */
    private const INLINE_UNWRAP = ['span', 'small', 'q', 'abbr', 'time', 'cite', 'code', 'kbd', 'samp', 'var', 'sup', 'sub', 'u', 's', 'mark', 'ins', 'del', 'dfn'];

    /** Теги, которые убираем, если они остались пустыми (структуру таблиц не трогаем). */
    private const PRUNE_TAGS = [
        'div', 'p', 'span', 'section', 'article', 'aside', 'main', 'nav', 'ul', 'ol', 'li', 'dl', 'dt', 'dd',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'strong', 'em', 'b', 'i', 'u', 'small', 'a', 'sup', 'sub',
        'details', 'summary', 'pre', 'footer', 'header', 'figure',
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
     * Полная очистка страницы — шаги 1…8 в порядке мануала. Возвращает тело статьи или '' — если статья
     * не найдена (нет <h1>).
     *
     * @param array{domain?: string, hosts?: list<string>, brand_ru?: string, brand_en?: string, extra_brands?: list<string>, remove_slots?: bool} $opt
     */
    public function clean(string $html, array $opt = []): string
    {
        // 1. Тело + FAQ, без мусора и без слотов.
        $body = $this->extractArticle($html);
        if ($body === '') {
            return '';
        }
        if ($opt['remove_slots'] ?? true) {
            $body = $this->removeSlots($body);
        }
        // 2. Подстановка — по всему (тело и FAQ вместе), ДО развёртки и снятия атрибутов: домен в href
        //    становится %domain_name%, и шаг 8 по нему отличает свою ссылку от внешней.
        $body = $this->applyReplacements($body, $opt);
        // 3–8. Служебные теги, развёртка контейнеров, оформление, заголовки, атрибуты, ссылки.
        $body = $this->normalizeMarkup($body);
        // Страховка: после развёртки <span>ов бренд, разбитый на куски, склеивается — ловим и его.
        // Повторный проход идемпотентен (переменные бренд не содержат).
        $body = $this->applyReplacements($body, $opt);

        return trim($body);
    }

    /**
     * Шаг 1. Тело статьи: всё после первого </h1> и до заголовка «Популярные запросы» + FAQ вторым
     * потоком; без служебных тегов и мусорных блоков.
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

        // FAQ — второй поток: если блок вопросов-ответов не попал в срез (лежит после «Популярных запросов»
        // или есть только в JSON-LD), вынимаем его отдельно и приклеиваем — подстановка пройдёт и по нему.
        $body .= $this->extractFaq($html, $body);

        // Комментарии (Яндекс.Метрика, Google Analytics и т.п.).
        $body = preg_replace('~<!--.*?-->~s', '', $body) ?? $body;
        // Через DOM убираем всё, что не относится к статье: медиа, интерактив, модалки, подвал сайта,
        // меню, контакты, облако тегов, «поделиться», куки-плашки, CTA-виджеты.
        $body = $this->stripNonArticle($body);

        return trim($body);
    }

    /**
     * FAQ, не попавший в срез тела: HTML-блок (itemtype FAQPage, class/id с «faq», <details>) где-то ещё
     * на странице, а если его нет — из JSON-LD FAQPage. '' — если FAQ уже в теле или его нет вовсе.
     */
    private function extractFaq(string $html, string $body): string
    {
        $marker = '~<details\b|<summary\b|(?:class|id)=["\'][^"\']*faq[^"\']*["\']|schema\.org/FAQPage~iu';
        if (preg_match($marker, $body) === 1) {
            return ''; // FAQ уже внутри тела — второй раз не нужен
        }
        if (preg_match($marker, $html) === 1) {
            $doc = $this->loadDocument($html);
            if ($doc !== null) {
                $xp = new \DOMXPath($doc);
                $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
                $found = $xp->query("//*[contains(@itemtype,'FAQPage') or contains({$lc('class')},'faq') or contains({$lc('id')},'faq')] | //details");
                $parts = [];
                foreach ($found ?: [] as $n) {
                    if (!$n instanceof \DOMElement) {
                        continue;
                    }
                    // Берём только верхние совпадения: вложенные (faq-item внутри faq) входят в родителя.
                    $inside = false;
                    for ($p = $n->parentNode; $p instanceof \DOMElement; $p = $p->parentNode) {
                        foreach ($found as $other) {
                            if ($other->isSameNode($p)) {
                                $inside = true;
                                break 2;
                            }
                        }
                    }
                    if (!$inside) {
                        $parts[] = $doc->saveHTML($n);
                    }
                }
                if ($parts !== []) {
                    return "\n" . implode("\n", $parts);
                }
            }
        }

        return $this->faqFromJsonLd($html);
    }

    /** FAQ из JSON-LD (schema.org/FAQPage → mainEntity[Question/acceptedAnswer]) в виде h2 + h3/p. */
    private function faqFromJsonLd(string $html): string
    {
        if (preg_match_all('~<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>~is', $html, $sm) === 0) {
            return '';
        }
        foreach ($sm[1] as $json) {
            $data = json_decode(trim($json), true);
            if (!is_array($data)) {
                continue;
            }
            $items = [];
            $walk = static function ($node) use (&$walk, &$items): void {
                if (!is_array($node)) {
                    return;
                }
                if (($node['@type'] ?? '') === 'FAQPage' && isset($node['mainEntity'])) {
                    foreach ((array) $node['mainEntity'] as $q) {
                        $name = trim((string) ($q['name'] ?? ''));
                        $answer = $q['acceptedAnswer'] ?? [];
                        $text = trim((string) (is_array($answer) ? ($answer['text'] ?? '') : ''));
                        if ($name !== '' && $text !== '') {
                            $items[] = [$name, $text];
                        }
                    }
                    return;
                }
                foreach ($node as $child) {
                    $walk($child);
                }
            };
            $walk($data);
            if ($items !== []) {
                $out = "\n<h2>Вопросы и ответы</h2>";
                foreach ($items as [$name, $text]) {
                    $out .= "\n<h3>" . htmlspecialchars($name, ENT_QUOTES | ENT_HTML5, 'UTF-8') . '</h3>'
                        . (preg_match('~<[a-z]~i', $text) === 1 ? "\n" . $text : "\n<p>" . htmlspecialchars($text, ENT_QUOTES | ENT_HTML5, 'UTF-8') . '</p>');
                }

                return $out;
            }
        }

        return '';
    }

    /**
     * Шаг 1 (мусор). Убирает из фрагмента не-контент: медиа, интерактив, модалки, подвал сайта, меню,
     * контакты, теги. DOM (а не регэкспы) — потому что модалки/блоки бывают с вложенными div.
     */
    private function stripNonArticle(string $fragment): string
    {
        [$doc, $root] = $this->loadFragment($fragment);
        if ($doc === null || $root === null) {
            return trim($fragment);
        }
        $xp = new \DOMXPath($doc);
        $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
        $inFaq = "ancestor::details or ancestor::summary or ancestor::*[contains({$lc('class')},'faq') or contains({$lc('id')},'faq')]";
        $remove = [];
        // Медиа и интерактив, меню, контакты-адрес, диалоги.
        foreach ($xp->query('.//script|.//style|.//noscript|.//template|.//svg|.//form|.//input|.//select|.//textarea|.//label|.//iframe|.//img|.//picture|.//video|.//audio|.//canvas|.//object|.//embed|.//map|.//source|.//address|.//dialog|.//nav', $root) as $n) {
            $remove[] = $n;
        }
        // Кнопки — интерактив, но кнопка-вопрос внутри FAQ несёт текст: её разворачиваем, а не удаляем.
        foreach ($xp->query(".//button[not($inFaq)]", $root) as $n) {
            $remove[] = $n;
        }
        // Подвал сайта — но подпись внутри цитаты (<blockquote><footer>) оставляем.
        foreach ($xp->query('.//footer[not(ancestor::blockquote)]', $root) as $n) {
            $remove[] = $n;
        }
        // Модалки/поповеры.
        foreach ($xp->query('.//*[@role="dialog" or @aria-modal="true"]', $root) as $n) {
            $remove[] = $n;
        }
        // Контакты, облако тегов, соцсети и пр. — по токенам класса/id.
        foreach ($xp->query('.//*[@class or @id]', $root) as $n) {
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
        foreach (iterator_to_array($xp->query(".//button[$inFaq]", $root) ?: []) as $n) {
            $this->unwrap($n, false);
        }

        return $this->serialize($doc, $root);
    }

    /**
     * Шаги 3–8 в порядке мануала: служебные теги → развёртка контейнеров → оформление → заголовки →
     * атрибуты → ссылки; в конце — пустые элементы.
     */
    private function normalizeMarkup(string $fragment): string
    {
        [$doc, $root] = $this->loadFragment($fragment);
        if ($doc === null || $root === null) {
            return trim($fragment);
        }
        $xp = new \DOMXPath($doc);
        $query = static fn (array $tags): string => implode('|', array_map(static fn (string $t): string => './/' . $t, $tags));

        // 3. Служебное — снести с содержимым; br/hr — на перевод строки, иначе «Второй<br>абзац» слипнется.
        foreach (iterator_to_array($xp->query($query(self::SERVICE_TAGS), $root) ?: []) as $n) {
            if ($n instanceof \DOMElement && in_array(strtolower($n->tagName), ['br', 'hr'], true) && $n->parentNode !== null) {
                $n->parentNode->replaceChild($doc->createTextNode("\n"), $n);
                continue;
            }
            $n->parentNode?->removeChild($n);
        }
        // 4. Развернуть контейнеры: блочные — с переводом строки на границах, строчные — впритык.
        foreach (iterator_to_array($xp->query($query(self::BLOCK_UNWRAP), $root) ?: []) as $n) {
            $this->unwrap($n, true);
        }
        foreach (iterator_to_array($xp->query($query(self::INLINE_UNWRAP), $root) ?: []) as $n) {
            $this->unwrap($n, false);
        }
        // 5. Оформление: em/i → обычный текст, b → strong.
        foreach (iterator_to_array($xp->query('.//em|.//i', $root) ?: []) as $n) {
            $this->unwrap($n, false);
        }
        foreach (iterator_to_array($xp->query('.//b', $root) ?: []) as $n) {
            $this->rename($doc, $n, 'strong');
        }
        // 6. Заголовки: h1 → h2, затем h4/h5/h6 → h3.
        foreach (iterator_to_array($xp->query('.//h1', $root) ?: []) as $n) {
            $this->rename($doc, $n, 'h2');
        }
        foreach (iterator_to_array($xp->query('.//h4|.//h5|.//h6', $root) ?: []) as $n) {
            $this->rename($doc, $n, 'h3');
        }
        // 7. Снять атрибуты со всех тегов, кроме href у <a>.
        foreach (iterator_to_array($xp->query('.//*[@*]', $root) ?: []) as $n) {
            if (!$n instanceof \DOMElement || $n->isSameNode($root)) {
                continue;
            }
            $names = [];
            foreach ($n->attributes as $attr) {
                $names[] = $attr->nodeName;
            }
            foreach ($names as $name) {
                if (!(strtolower($n->tagName) === 'a' && strtolower($name) === 'href')) {
                    $n->removeAttribute($name);
                }
            }
        }
        // 8. Ссылки: внешние и служебные (#, mailto:, tel:, javascript:) — развернуть в текст,
        //    внутренние — к одному из допустимых путей (главная — «/»).
        foreach (iterator_to_array($xp->query('.//a', $root) ?: []) as $a) {
            if (!$a instanceof \DOMElement) {
                continue;
            }
            $href = $a->hasAttribute('href') ? $a->getAttribute('href') : '';
            if ($this->isExternalOrJunkLink($href)) {
                $this->unwrap($a, false);
                continue;
            }
            $a->setAttribute('href', $this->mapLink($href));
        }
        // Пустые элементы, оставшиеся после всего (пустой <p>, <a> вокруг удалённой картинки).
        $this->pruneEmpty($xp, $root);

        return $this->serialize($doc, $root);
    }

    /** Шаг 8: внешняя ли ссылка (не свой домен — к этому шагу свой уже подставлен как %domain_name%) или служебная. */
    private function isExternalOrJunkLink(string $href): bool
    {
        $href = trim(html_entity_decode($href, ENT_QUOTES | ENT_HTML5, 'UTF-8'));
        if ($href === '' || str_starts_with($href, '#')) {
            return true;
        }
        if (preg_match('~^(?:mailto|tel|sms|javascript|data|blob|ftp|skype|viber|whatsapp|tg):~i', $href) === 1) {
            return true;
        }
        if (str_starts_with($href, '//')) {
            $href = 'https:' . $href;
        }
        if (preg_match('~^[a-z][a-z0-9+.\-]*://([^/?#]*)~i', $href, $m) === 1) {
            return !str_contains(mb_strtolower($m[1]), '%domain_name%');
        }

        return false; // относительная — внутренняя
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
     * Одна внутренняя ссылка → относительный путь из списка допустимых (по последнему сегменту и смыслу);
     * неизвестное и главная → «/».
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
        if ($key !== '' && in_array('/' . $key, self::ALLOWED_LINKS, true)) {
            return '/' . $key;
        }

        return '/';
    }

    /**
     * Шаг 2. Замены домена, даты и бренда на переменные шаблона.
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
            // Свой русский бренд — с учётом падежей («Криптобосса», «Криптобоссе»), иначе часть упоминаний
            // оставалась незаменённой. Для чужих (известных) брендов склонение не включаем: у коротких
            // слов это даёт ложные совпадения (стейк → «стейка» — еда, а не бренд).
            $html = $this->replaceBrand($html, (string) $opt['brand_ru'], '%brand_name_ru%', true);
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

    /**
     * Падежные окончания русского бренда («Криптобосса», «Криптобоссе», «в Вулкане Вегасе»): без них
     * склонённые формы оставались в тексте. Только явный список окончаний, а не «любые 3 буквы» —
     * иначе «куш» + «ать» съело бы «кушать».
     */
    private const RU_ENDINGS = '(?:ами|ями|ом|ем|ём|ой|ей|ою|ею|ов|ев|ёв|ам|ям|ах|ях|а|я|у|ю|е|ё|ы|и|о)?';

    private function replaceBrand(string $html, string $brand, string $variable, bool $declension = false): string
    {
        $pattern = $this->homoglyphPattern($brand, $declension);
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
    private function homoglyphPattern(string $brand, bool $declension = false): string
    {
        $out = '';
        foreach (preg_split('~~u', mb_strtolower(trim($brand)), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
            if (trim($ch) === '') {
                // Окончание — у каждого слова составного бренда («в Вулкане Вегасе»), перед пробелом.
                $out .= ($declension ? self::RU_ENDINGS : '') . '\s+';
            } elseif (isset(self::HOMOGLYPHS[$ch])) {
                $out .= '[' . self::HOMOGLYPHS[$ch] . ']';
            } else {
                $out .= preg_quote($ch, '~');
            }
        }

        return $out === '' ? '' : $out . ($declension ? self::RU_ENDINGS : '');
    }

    private function hasCyrillic(string $text): bool
    {
        return preg_match('~\p{Cyrillic}~u', $text) === 1;
    }

    // ---- DOM-помощники -------------------------------------------------------------------------

    /** Загружает фрагмент в обёртку <div id="ys-root">; [doc, root] или [null, null], если не разобралось. */
    private function loadFragment(string $fragment): array
    {
        $fragment = trim($fragment);
        if ($fragment === '') {
            return [null, null];
        }
        $doc = $this->loadDocument('<div id="ys-root">' . $fragment . '</div>');
        $root = $doc?->getElementById('ys-root');

        return $root === null ? [null, null] : [$doc, $root];
    }

    private function loadDocument(string $html): ?\DOMDocument
    {
        $doc = new \DOMDocument();
        $prev = libxml_use_internal_errors(true);
        $loaded = $doc->loadHTML('<?xml encoding="UTF-8"?>' . $html, LIBXML_NOWARNING | LIBXML_NOERROR);
        libxml_clear_errors();
        libxml_use_internal_errors($prev);

        return $loaded ? $doc : null;
    }

    private function serialize(\DOMDocument $doc, \DOMElement $root): string
    {
        $out = '';
        foreach (iterator_to_array($root->childNodes) as $child) {
            $out .= $doc->saveHTML($child);
        }

        return $out;
    }

    /** Снимает тег, оставляя содержимое; для блочных — с переводами строки на границах, чтобы текст не слипался. */
    private function unwrap(\DOMNode $n, bool $block): void
    {
        $parent = $n->parentNode;
        if ($parent === null) {
            return;
        }
        $doc = $n->ownerDocument;
        if ($block && $doc !== null) {
            $parent->insertBefore($doc->createTextNode("\n"), $n);
        }
        while ($n->firstChild !== null) {
            $parent->insertBefore($n->firstChild, $n);
        }
        if ($block && $doc !== null) {
            $parent->insertBefore($doc->createTextNode("\n"), $n);
        }
        $parent->removeChild($n);
    }

    /** Меняет тег элемента (b → strong, h1 → h2), сохраняя содержимое; атрибуты не переносятся (шаг 7 снимает всё). */
    private function rename(\DOMDocument $doc, \DOMNode $n, string $tag): void
    {
        if ($n->parentNode === null) {
            return;
        }
        $new = $doc->createElement($tag);
        while ($n->firstChild !== null) {
            $new->appendChild($n->firstChild);
        }
        $n->parentNode->replaceChild($new, $n);
    }

    /**
     * Удаляет пустые элементы (без текста и без потомков) снизу вверх, пока что-то удаляется:
     * <div><div></div></div> → ничего. &nbsp; считается пустотой.
     */
    private function pruneEmpty(\DOMXPath $xp, \DOMElement $root): void
    {
        $tags = implode('|', array_map(static fn (string $t): string => 'self::' . $t, self::PRUNE_TAGS));
        do {
            $removed = 0;
            $nodes = iterator_to_array($xp->query('.//*[' . $tags . ']', $root) ?: []);
            foreach (array_reverse($nodes) as $n) {
                if (!$n instanceof \DOMElement || $n->parentNode === null) {
                    continue;
                }
                $hasElementChild = false;
                foreach ($n->childNodes as $c) {
                    if ($c instanceof \DOMElement) {
                        $hasElementChild = true;
                        break;
                    }
                }
                $text = str_replace("\u{00A0}", ' ', $n->textContent);
                if (!$hasElementChild && trim($text) === '') {
                    $n->parentNode->removeChild($n);
                    $removed++;
                }
            }
        } while ($removed > 0);
    }
}

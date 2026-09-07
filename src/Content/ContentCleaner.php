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
        // Виджеты и каркас, встречающиеся в контентном блоке: герой-баннер, джекпоты и «последние выплаты»,
        // каталог слотов, плавающие плашки/уведомления, «похожие разделы», меню и облака ключевых слов.
        'hero', 'jackpot', 'jackpots', 'payout', 'payouts', 'dashboard', 'widget', 'widgets', 'toast', 'toasts',
        'notification', 'notifications', 'floating', 'related', 'action', 'skip', 'topbar', 'navbar', 'menu',
        'sitenav', 'mainnav', 'keyword', 'keywords', 'cloud', 'winners',
        // Панель фильтров каталога игр («Все игры», «Провайдеры» с выпадающими списками).
        'filter', 'filters', 'dropdown',
    ];

    /** Карточка игры/слота: gamecard, slot-card, game-tile… — каталог, а не текст статьи. */
    private const CARD_TOKENS = ['gamecard', 'gamecards', 'slotcard', 'slotcards'];
    private const CARD_GENERIC = ['card', 'cards', 'tile', 'tiles'];
    private const CARD_SUBJECT = ['slot', 'slots', 'game', 'games'];

    /** Шапка сайта без тега <header>: блок с такими токенами класса/id вне main/article и без h1 внутри. */
    private const HEADER_TOKENS = ['header', 'logo'];

    /** Плашки-«бейджи» (жанры, метки): разворачиваем с пробелом, иначе соседние слова слипаются («TouchКаскады»). */
    private const CHIP_TOKENS = ['badge', 'badges', 'chip', 'chips', 'pill', 'pills', 'label', 'labels', 'feature', 'features'];

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
        // Каталоги слотов (карточки игр) по умолчанию ОСТАЮТСЯ — это контент; режем только шапку и подвал.
        // Удаление включается настройкой remove_slots (галочка в панели, --remove-slots в консоли).
        if ($opt['remove_slots'] ?? false) {
            $body = $this->removeSlots($body);
        }
        // 2. Подстановка — по всему (тело и FAQ вместе), ДО развёртки и снятия атрибутов: домен в href
        //    становится %domain_name%, и шаг 8 по нему отличает свою ссылку от внешней.
        $body = $this->applyReplacements($body, $opt);
        // 3–8. Служебные теги, развёртка контейнеров, оформление, заголовки, атрибуты, ссылки.
        $body = $this->normalizeMarkup($body);
        // Развёртка вложенных div оставляет пачки пустых строк — схлопываем до одной.
        $body = preg_replace('~[ \t]*\n[ \t]*(?:\n[ \t]*)+~u', "\n", $body) ?? $body;
        // Страховка: после развёртки <span>ов бренд, разбитый на куски, склеивается — ловим и его.
        // Повторный проход идемпотентен (переменные бренд не содержат).
        $body = $this->applyReplacements($body, $opt);

        return trim($body);
    }

    /** Заголовок «Популярные запросы» (мануал): отсюда и до конца — не статья. */
    private const END_ALWAYS = '~^\W*популярн\w*\s+запрос~iu';

    /**
     * Заголовок блока о сайте («О компании», «О портале», «Контакты», «Реквизиты»…): отсюда и до конца режем,
     * только если дальше идут реквизиты сайта (телефон, e-mail, лицензия, ©), а не продолжение статьи.
     */
    private const END_ABOUT = '~^\W*(?:о\s+(?:компании|портале|нас|проекте|сайте)|юридическ\w*\s+адрес|реквизиты|контакт\w*|about\s+(?:us|company)|contacts?)\b~iu';

    /** Признаки реквизитов сайта: телефон, e-mail, © / «все права», номер лицензии, юридический адрес. */
    private const CONTACT_SIGNS = '~\+\d[\d\s()\-]{7,}\d|\b8[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b|[\w.\-]+@[\w\-]+(?:\.[\w\-]+)+|©|\(c\)|все права защищ|лицензи\w*\s*(?:№|#|номер|no\.?)|реквизит|юридическ\w*\s+адрес|оператор:~iu';

    /** Заголовок облака запросов/тегов: сам заголовок и ссылочный блок за ним — не статья (а текст после них — статья). */
    private const CLOUD_HEADING = '~^\W*(?:похожие|популярные|связанные|ключевые|другие|рекомендуемые)\s+(?:запросы|поиски|темы|слова|запросов|статьи|материалы)|^\W*(?:теги|метки|tags|keywords|облако\s+тегов)\W*$~iu';

    /** Без h1 страница считается статьёй, только если текста в контентном блоке не меньше стольких символов. */
    private const MIN_ARTICLE_CHARS = 300;

    /**
     * Шаг 1. Тело статьи = контентный блок страницы (<main>, иначе всё тело) без каркаса сайта: шапка, меню,
     * подвал, попапы, виджеты, облака тегов, медиа и интерактив удаляются целиком. Начало — после первого h1,
     * если перед ним нет текста статьи (h1 — шапка статьи); если текст есть (h1 стоит посреди контента),
     * берём с начала блока, и h1 остаётся (шаг 6 сделает из него h2). Конец — «Популярные запросы» (всегда)
     * или блок «О компании» с реквизитами. FAQ, оказавшийся вне среза, приклеивается вторым потоком.
     */
    public function extractArticle(string $html): string
    {
        $doc = $this->loadDocument($html);
        $body = $doc?->getElementsByTagName('body')->item(0);
        if ($doc === null || !$body instanceof \DOMElement) {
            return '';
        }
        $xp = new \DOMXPath($doc);
        // Комментарии (Яндекс.Метрика, Google Analytics и т.п.).
        foreach (iterator_to_array($xp->query('//comment()') ?: []) as $c) {
            $c->parentNode?->removeChild($c);
        }
        // FAQ запоминаем до вырезаний: что не попадёт в срез, приклеим вторым потоком.
        $faqNodes = $this->faqNodes($xp);
        // Каркас сайта и всё, что не статья.
        $this->stripNonArticleIn($xp, $body);

        $root = $this->contentRoot($xp, $body);
        $root->setAttribute('data-ys-root', '1');
        $h1 = $xp->query('.//h1', $root)?->item(0);
        if ($h1 instanceof \DOMElement) {
            if (!$this->hasArticleTextBefore($xp, $h1)) {
                $this->cutBefore($h1, $root);
                $h1->parentNode?->removeChild($h1);
            }
        } elseif (mb_strlen($this->textOf($root)) < self::MIN_ARTICLE_CHARS) {
            return '';
        }
        $this->cutAtEndMarker($xp, $root);
        $this->removeLinkClouds($xp, $root);
        $root->removeAttribute('data-ys-root');

        $out = trim($this->serialize($doc, $root));
        // FAQ — второй поток: блоки вне среза (после «Популярных запросов», вне <main>) приклеиваем, чтобы
        // подстановка бренда прошла и по ним; если HTML-блока нет вовсе — рендерим из JSON-LD.
        foreach ($faqNodes as $n) {
            if (!$this->isInside($n, $root)) {
                $out .= "\n" . $doc->saveHTML($n);
            }
        }
        if ($faqNodes === []) {
            $out .= $this->faqFromJsonLd($html);
        }

        return trim($out);
    }

    /**
     * Верхние FAQ-блоки страницы (itemtype FAQPage, class/id с «faq», <details>); вложенные (faq-item внутри
     * faq) входят в родителя.
     *
     * @return list<\DOMElement>
     */
    private function faqNodes(\DOMXPath $xp): array
    {
        $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
        $found = iterator_to_array($xp->query("//*[contains(@itemtype,'FAQPage') or contains({$lc('class')},'faq') or contains({$lc('id')},'faq')] | //details") ?: []);
        $top = [];
        foreach ($found as $n) {
            if (!$n instanceof \DOMElement) {
                continue;
            }
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
                $top[] = $n;
            }
        }

        return $top;
    }

    /** Контентный блок: <main> (или role=main) с наибольшим текстом, если в нём хотя бы 40% текста страницы; иначе всё тело. */
    private function contentRoot(\DOMXPath $xp, \DOMElement $body): \DOMElement
    {
        $best = null;
        $bestLen = 0;
        foreach ($xp->query('.//main|.//*[@role="main"]', $body) ?: [] as $n) {
            if (!$n instanceof \DOMElement) {
                continue;
            }
            $len = mb_strlen($this->textOf($n));
            if ($len > $bestLen) {
                $best = $n;
                $bestLen = $len;
            }
        }
        if ($best !== null && $bestLen >= 0.4 * mb_strlen($this->textOf($body))) {
            return $best;
        }

        return $body;
    }

    /** Есть ли перед h1 текст статьи (абзац от 40 символов или суммарно от 150): тогда h1 — не шапка, а середина контента. */
    private function hasArticleTextBefore(\DOMXPath $xp, \DOMElement $h1): bool
    {
        $chars = 0;
        foreach ($xp->query('preceding::text()[ancestor::*[@data-ys-root]]', $h1) ?: [] as $t) {
            $chars += mb_strlen(trim($t->textContent));
        }
        if ($chars >= 150) {
            return true;
        }
        foreach ($xp->query('preceding::*[self::p or self::li][ancestor::*[@data-ys-root]]', $h1) ?: [] as $p) {
            if (mb_strlen($this->textOf($p)) >= 40) {
                return true;
            }
        }

        return false;
    }

    /**
     * Конец статьи: «Популярные запросы» — всегда; «О компании»/«Контакты» и т.п. — только если остаток похож на
     * реквизиты сайта (телефон, e-mail, лицензия, ©) и не длиннее 600–1500 символов. Раздел «О портале …»
     * посреди статьи без реквизитов остаётся.
     */
    private function cutAtEndMarker(\DOMXPath $xp, \DOMElement $root): void
    {
        $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
        $inFaq = "ancestor::details or ancestor::*[contains({$lc('class')},'faq') or contains({$lc('id')},'faq')]";
        $total = mb_strlen($this->textOf($root));
        $nodes = $xp->query(".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6 or self::p or self::div or self::strong or self::b or self::dt][not($inFaq)]", $root);
        foreach (iterator_to_array($nodes ?: []) as $n) {
            if (!$n instanceof \DOMElement) {
                continue;
            }
            $text = $this->textOf($n);
            if (preg_match('~^h[1-6]$~', $n->tagName) !== 1 && mb_strlen($text) > 40) {
                continue;
            }
            if (preg_match(self::END_ALWAYS, $text) === 1) {
                $this->cutAfter($n, $root);

                return;
            }
            if (preg_match(self::END_ABOUT, $text) !== 1) {
                continue;
            }
            $rest = $this->textAfter($xp, $n);
            $len = mb_strlen($rest);
            if (preg_match(self::CONTACT_SIGNS, $rest) === 1 && $len <= max(600, min(1500, (int) ($total * 0.35)))) {
                $this->cutAfter($n, $root);

                return;
            }
        }
    }

    /** Текст узла и всего, что после него внутри контентного блока. */
    private function textAfter(\DOMXPath $xp, \DOMElement $n): string
    {
        $text = $this->textOf($n);
        foreach ($xp->query('following::text()[ancestor::*[@data-ys-root]]', $n) ?: [] as $t) {
            $text .= ' ' . trim($t->textContent);
        }

        return $text;
    }

    /** Удаляет всё до узла внутри $root (сам узел остаётся). */
    private function cutBefore(\DOMNode $node, \DOMElement $root): void
    {
        for ($n = $node; $n !== null && !$n->isSameNode($root); $n = $n->parentNode) {
            while ($n->previousSibling !== null && $n->parentNode !== null) {
                $n->parentNode->removeChild($n->previousSibling);
            }
        }
    }

    /** Удаляет узел и всё после него внутри $root. */
    private function cutAfter(\DOMNode $node, \DOMElement $root): void
    {
        for ($n = $node; $n !== null && !$n->isSameNode($root); $n = $n->parentNode) {
            while ($n->nextSibling !== null && $n->parentNode !== null) {
                $n->parentNode->removeChild($n->nextSibling);
            }
        }
        $node->parentNode?->removeChild($node);
    }

    /**
     * Облака запросов/тегов и меню: заголовок вроде «Похожие запросы»/«Ключевые темы» вместе с ссылочным блоком
     * за ним, а также любой блок, где почти всё — ссылки (от 8 ссылок и ≥ 80% текста в них). Статья после
     * такого блока остаётся.
     */
    private function removeLinkClouds(\DOMXPath $xp, \DOMElement $root): void
    {
        $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
        $inFaq = "ancestor::details or ancestor::*[contains({$lc('class')},'faq') or contains({$lc('id')},'faq')]";
        $headings = $xp->query(".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6 or self::p or self::div or self::strong or self::b][not($inFaq)]", $root);
        foreach (iterator_to_array($headings ?: []) as $n) {
            if (!$n instanceof \DOMElement || !$this->isInside($n, $root)) {
                continue;
            }
            $text = $this->textOf($n);
            if (mb_strlen($text) > 40 || preg_match(self::CLOUD_HEADING, $text) !== 1) {
                continue;
            }
            $next = $n->nextSibling;
            while ($next !== null && !$next instanceof \DOMElement && trim($next->textContent) === '') {
                $next = $next->nextSibling;
            }
            if ($next instanceof \DOMElement && $this->isLinkDense($xp, $next, 4, 0.7)) {
                $next->parentNode?->removeChild($next);
            }
            $n->parentNode?->removeChild($n);
        }
        $blocks = $xp->query(".//*[self::div or self::section or self::ul or self::ol or self::p][not($inFaq)]", $root);
        foreach (iterator_to_array($blocks ?: []) as $n) {
            if ($n instanceof \DOMElement && $this->isInside($n, $root) && $this->isLinkDense($xp, $n, 8, 0.8)) {
                $n->parentNode?->removeChild($n);
            }
        }
    }

    /** Блок почти целиком из ссылок: не меньше $minLinks ссылок и не меньше $minRatio его текста внутри них. */
    private function isLinkDense(\DOMXPath $xp, \DOMElement $el, int $minLinks, float $minRatio): bool
    {
        $links = $xp->query('.//a', $el);
        if ($links === false || $links->length < $minLinks) {
            return false;
        }
        $all = mb_strlen($this->textOf($el));
        if ($all === 0) {
            return false;
        }
        $inLinks = 0;
        foreach ($links as $a) {
            $inLinks += mb_strlen($this->textOf($a));
        }

        return $inLinks / $all >= $minRatio;
    }

    /** Узел всё ещё внутри $root (не вырезан вместе с предком)? */
    private function isInside(\DOMNode $n, \DOMElement $root): bool
    {
        for ($p = $n; $p !== null; $p = $p->parentNode) {
            if ($p->isSameNode($root)) {
                return true;
            }
        }

        return false;
    }

    /** Текст узла с схлопнутыми пробелами. */
    private function textOf(\DOMNode $n): string
    {
        return trim(preg_replace('~\s+~u', ' ', $n->textContent) ?? $n->textContent);
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
     * Шаг 1 (мусор). Убирает всё, что не статья: каркас сайта (шапка, меню, подвал, боковые колонки, попапы),
     * медиа, интерактив, контакты, облака тегов, виджеты (джекпоты, «последние выплаты», таймеры, CTA).
     * DOM (а не регэкспы) — потому что блоки бывают с вложенными div.
     */
    private function stripNonArticleIn(\DOMXPath $xp, \DOMElement $root): void
    {
        $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
        $inFaq = "ancestor::details or ancestor::summary or ancestor::*[contains({$lc('class')},'faq') or contains({$lc('id')},'faq')]";
        $remove = [];
        // Каркас сайта: шапка (не внутри main/article — там это шапка статьи с h1), меню, боковые колонки,
        // подвал (кроме подписи в цитате: <blockquote><footer>), диалоги и служебные роли.
        // <aside> внутри статьи (main/article/itemtype Article — врезка «Поддержка 24/7») — часть контента, остаётся.
        foreach ($xp->query('.//header[not(ancestor::main) and not(ancestor::article)]|.//nav|.//aside[not(ancestor::main) and not(ancestor::article) and not(ancestor::*[contains(@itemtype,"Article")])]|.//footer[not(ancestor::blockquote)]|.//dialog', $root) ?: [] as $n) {
            $remove[] = $n;
        }
        foreach ($xp->query('.//*[@role="banner" or @role="navigation" or @role="complementary" or @role="contentinfo" or @role="dialog" or @role="alertdialog" or @aria-modal="true"]', $root) ?: [] as $n) {
            $remove[] = $n;
        }
        // Шапка без тега <header>: блок с классом header/logo вне main/article, в котором нет h1.
        foreach ($xp->query('.//*[@class or @id][not(ancestor::main) and not(ancestor::article) and not(.//h1)]', $root) ?: [] as $n) {
            if ($n instanceof \DOMElement && array_intersect($this->tokens($n), self::HEADER_TOKENS) !== []) {
                $remove[] = $n;
            }
        }
        // Медиа, интерактив, адрес.
        foreach ($xp->query('.//script|.//style|.//noscript|.//template|.//svg|.//form|.//input|.//select|.//textarea|.//iframe|.//img|.//picture|.//video|.//audio|.//canvas|.//object|.//embed|.//map|.//source|.//address', $root) ?: [] as $n) {
            $remove[] = $n;
        }
        // Кнопки и подписи полей — интерактив; но внутри FAQ они несут вопрос: их разворачиваем, а не удаляем.
        foreach ($xp->query(".//button[not($inFaq)]|.//label[not($inFaq)]", $root) ?: [] as $n) {
            $remove[] = $n;
        }
        // Контакты, облако тегов, соцсети, виджеты и пр. — по токенам класса/id.
        foreach ($xp->query('.//*[@class or @id]', $root) ?: [] as $n) {
            if (!$n instanceof \DOMElement) {
                continue;
            }
            if (array_intersect($this->tokens($n), self::JUNK_TOKENS) !== []) {
                $remove[] = $n;
            }
        }
        foreach ($remove as $n) {
            $n->parentNode?->removeChild($n);
        }
        // Кнопка/подпись внутри FAQ — это вопрос: делаем из неё h3 (как из JSON-LD); прочие — в текст.
        foreach (iterator_to_array($xp->query(".//button[$inFaq]|.//label[$inFaq]", $root) ?: []) as $n) {
            if ($n instanceof \DOMElement && $n->ownerDocument !== null && $this->looksLikeQuestion($n)) {
                $this->rename($n->ownerDocument, $n, 'h3');
            } else {
                $this->unwrap($n, false);
            }
        }
    }

    /** Токены класса и id элемента (в нижнем регистре, разбитые по пробелам, «-» и «_»). */
    private function tokens(\DOMElement $n): array
    {
        return preg_split('~[\s_\-]+~u', mb_strtolower($n->getAttribute('class') . ' ' . $n->getAttribute('id'))) ?: [];
    }

    /** Кнопка-вопрос FAQ: текст с «?» или класс/id/aria вроде question/faq/accordion/toggle. */
    private function looksLikeQuestion(\DOMElement $n): bool
    {
        $text = $this->textOf($n);
        if (mb_strlen($text) < 4 || mb_strlen($text) > 200) {
            return false;
        }
        $attrs = mb_strtolower($n->getAttribute('class') . ' ' . $n->getAttribute('id') . ' ' . $n->getAttribute('aria-controls'));

        return str_ends_with($text, '?') || preg_match('~question|faq|accordion|toggle|collapse|summary|title~', $attrs) === 1;
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
            // Плашки-«бейджи» стоят вплотную друг к другу: без пробела соседние слова слипнутся («TouchКаскады»).
            $chip = $n instanceof \DOMElement && array_intersect($this->tokens($n), self::CHIP_TOKENS) !== [];
            $this->unwrap($n, false, $chip ? ' ' : '');
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
        // Заголовки без переносов строк и отступов внутри: «<h4>\n  Infectus\n</h4>» → «<h3>Infectus</h3>».
        foreach (iterator_to_array($xp->query('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6', $root) ?: []) as $n) {
            foreach ([$n->firstChild, $n->lastChild] as $edge) {
                if ($edge instanceof \DOMText) {
                    $edge->nodeValue = $edge->isSameNode($n->firstChild) ? ltrim($edge->nodeValue ?? '') : rtrim($edge->nodeValue ?? '');
                }
            }
            if ($n->firstChild instanceof \DOMText && $n->firstChild->isSameNode($n->lastChild)) {
                $n->firstChild->nodeValue = trim($n->firstChild->nodeValue ?? '');
            }
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
        // Осиротевшие значки верхнего уровня (эмодзи-иконки из развёрнутых карточек) — без букв и цифр — убираем.
        foreach (iterator_to_array($root->childNodes) as $c) {
            if ($c instanceof \DOMText && trim($c->textContent) !== '' && preg_match('~[\p{L}\p{N}]~u', $c->textContent) !== 1) {
                $c->nodeValue = "\n";
            }
        }
        // Заголовок, под которым ничего не осталось (каталог слотов вырезан, а его h2 — нет), — убираем.
        $this->pruneOrphanHeadings($xp, $root);
        // «Голый» текст верхнего уровня (после развёртки div) — в <p>: на выходе только семантические теги.
        $this->wrapLooseText($doc, $root);

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
     * Удаляет каталоги слотов/игр, оставляя текст статьи вокруг них:
     *  1) сетки карточек игр (gamecard, slot-card, game-tile…) — сетка целиком вместе с обёрткой-виджетом
     *     («🎡 Рулетка онлайн» + подпись «Крупные ставки»), а одиночные карточки — поштучно;
     *  2) секцию с заголовком про слоты/игры/автоматы (целыми словами: «выигрыш» — не «игры») до следующего
     *     заголовка того же/старшего уровня — только если в ней нет текста статьи (меньше двух абзацев от
     *     120 символов, абзацем считается и div) и это не FAQ/вопрос.
     * Раздел «Слоты с высоким RTP» с прозой на странице про слоты и FAQ «Какие шансы выиграть в слоты?» остаются.
     */
    public function removeSlots(string $html): string
    {
        [$doc, $root] = $this->loadFragment($html);
        if ($doc === null || $root === null) {
            return $html;
        }
        $xp = new \DOMXPath($doc);
        // 1. Карточки → их сетки (родитель с двумя и более карточками) → обёртка виджета.
        $grids = [];
        $single = [];
        foreach (iterator_to_array($xp->query('.//*[@class or @id]', $root) ?: []) as $e) {
            if (!$e instanceof \DOMElement || !$this->isCard($e)) {
                continue;
            }
            $parent = $e->parentNode;
            if ($parent instanceof \DOMElement && !$parent->isSameNode($root)) {
                $grids[spl_object_id($parent)] = [$parent, ($grids[spl_object_id($parent)][1] ?? 0) + 1];
            } else {
                $single[] = $e;
            }
        }
        foreach ($grids as [$grid, $count]) {
            if (!$this->isInside($grid, $root)) {
                continue;
            }
            if ($count >= 2) {
                $this->removeCardGrid($grid, $root);
            } else {
                foreach (iterator_to_array($xp->query('./*[@class or @id]', $grid) ?: []) as $e) {
                    if ($e instanceof \DOMElement && $this->isCard($e)) {
                        $grid->removeChild($e);
                    }
                }
            }
        }
        foreach ($single as $e) {
            if ($this->isInside($e, $root)) {
                $e->parentNode?->removeChild($e);
            }
        }
        // 2. Секции с заголовком про слоты/игры без текста статьи.
        $lc = static fn (string $attr): string => "translate(@$attr,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')";
        $inFaq = "ancestor::details or ancestor::*[contains({$lc('class')},'faq') or contains({$lc('id')},'faq') or contains(@itemtype,'FAQPage')]";
        foreach (iterator_to_array($xp->query(".//*[self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6][not($inFaq)]", $root) ?: []) as $h) {
            if (!$h instanceof \DOMElement || !$this->isInside($h, $root)) {
                continue;
            }
            $title = $this->textOf($h);
            if (str_ends_with($title, '?') || preg_match('~(?<!\p{L})(?:слот\w*|игров\w*|игр[аыеу]|автомат\w*|slots?|games?)(?!\p{L})~iu', $title) !== 1) {
                continue;
            }
            $level = (int) substr($h->tagName, 1);
            $section = [$h];
            for ($n = $h->nextSibling; $n !== null; $n = $n->nextSibling) {
                if ($n instanceof \DOMElement && preg_match('~^h([1-6])$~i', $n->tagName, $m) === 1 && (int) $m[1] <= $level) {
                    break;
                }
                $section[] = $n;
            }
            if ($this->proseCount($xp, $section) >= 2) {
                continue; // текст статьи про слоты, а не каталог
            }
            foreach ($section as $n) {
                $n->parentNode?->removeChild($n);
            }
        }

        return $this->serialize($doc, $root);
    }

    /**
     * Убирает сетку карточек и «шапку» виджета перед ней: короткие соседи (подпись) вплоть до заголовка;
     * длинный блок перед сеткой — это уже статья, её не трогаем. Если обёртка сетки после этого почти пуста
     * (< 120 символов, заголовок без текста) — убираем и её.
     */
    private function removeCardGrid(\DOMElement $grid, \DOMElement $root): void
    {
        $parent = $grid->parentNode;
        $shell = [];
        $heading = false;
        for ($s = $grid->previousSibling; $s !== null; $s = $s->previousSibling) {
            if ($s instanceof \DOMText) {
                if (mb_strlen(trim($s->textContent)) >= 120) {
                    break;
                }
                $shell[] = $s;
                continue;
            }
            if (!$s instanceof \DOMElement) {
                continue;
            }
            if (preg_match('~^h[1-6]$~i', $s->tagName) === 1) {
                $shell[] = $s;
                $heading = true;
                break;
            }
            if (mb_strlen($this->textOf($s)) >= 120 || $s->getElementsByTagName('*')->length > 20) {
                break;
            }
            $shell[] = $s;
        }
        $grid->parentNode?->removeChild($grid);
        if ($heading) {
            foreach ($shell as $s) {
                $s->parentNode?->removeChild($s);
            }
        }
        if ($parent instanceof \DOMElement && !$parent->isSameNode($root) && mb_strlen($this->textOf($parent)) < 120) {
            $hasHeading = false;
            foreach ($parent->getElementsByTagName('*') as $e) {
                if (preg_match('~^h[1-6]$~i', $e->tagName) === 1) {
                    $hasHeading = true;
                    break;
                }
            }
            if ($hasHeading || trim($this->textOf($parent)) === '') {
                $parent->parentNode?->removeChild($parent);
            }
        }
    }

    /**
     * Сколько в узлах «абзацев статьи»: листовых блоков (p, li, dd, blockquote, div, summary) с текстом от 120
     * символов; блок с таким же длинным дочерним блоком не считается (чтобы не считать обёртку дважды).
     *
     * @param list<\DOMNode> $nodes
     */
    private function proseCount(\DOMXPath $xp, array $nodes): int
    {
        $prose = 0;
        foreach ($nodes as $n) {
            if (!$n instanceof \DOMElement) {
                continue;
            }
            foreach ($xp->query('descendant-or-self::*[self::p or self::li or self::dd or self::blockquote or self::div or self::summary]', $n) ?: [] as $b) {
                if (!$b instanceof \DOMElement || mb_strlen($this->textOf($b)) < 120) {
                    continue;
                }
                $longChild = false;
                foreach ($b->childNodes as $c) {
                    if ($c instanceof \DOMElement && mb_strlen($this->textOf($c)) >= 120) {
                        $longChild = true;
                        break;
                    }
                }
                if (!$longChild) {
                    $prose++;
                }
            }
        }

        return $prose;
    }

    /**
     * Карточка игры: класс gamecard/slot-card/game-tile и т.п. (card/tile вместе со slot/game) — и при этом
     * маленький блок (до 400 символов, без h1/h2): секция «Полезно знать о слотах» с классами
     * slots-thematic glass-card — не карточка.
     */
    private function isCard(\DOMElement $e): bool
    {
        $tokens = $this->tokens($e);
        $classy = array_intersect($tokens, self::CARD_TOKENS) !== []
            || (array_intersect($tokens, self::CARD_GENERIC) !== [] && array_intersect($tokens, self::CARD_SUBJECT) !== []);
        if (!$classy || mb_strlen($this->textOf($e)) > 400) {
            return false;
        }
        foreach ($e->getElementsByTagName('*') as $child) {
            if (in_array(strtolower($child->tagName), ['h1', 'h2'], true)) {
                return false;
            }
        }

        return true;
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

        // Границы слова, чтобы не задевать бренд внутри других слов (stake ≠ mistaken); цифры справа допустимы —
        // промокод «Grizzly30» тоже несёт бренд.
        return preg_replace('~(?<![\p{L}\p{N}])(?:' . $pattern . ')(?!\p{L})~iu', $variable, $html) ?? $html;
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

    /**
     * Снимает тег, оставляя содержимое; для блочных — с переводами строки на границах, чтобы текст не слипался;
     * $sep — разделитель для строчных (пробел для плашек).
     */
    private function unwrap(\DOMNode $n, bool $block, string $sep = ''): void
    {
        $parent = $n->parentNode;
        if ($parent === null) {
            return;
        }
        $doc = $n->ownerDocument;
        $sep = $block ? "\n" : $sep;
        // Разделитель не дублируем, если сосед уже кончается/начинается пробелом («Touch  Каскады»).
        $prev = $n->previousSibling;
        if ($sep !== '' && $doc !== null && !($prev instanceof \DOMText && preg_match('~\s$~u', $prev->textContent) === 1)) {
            $parent->insertBefore($doc->createTextNode($sep), $n);
        }
        while ($n->firstChild !== null) {
            $parent->insertBefore($n->firstChild, $n);
        }
        $next = $n->nextSibling;
        if ($sep !== '' && $doc !== null && !($next instanceof \DOMText && preg_match('~^\s~u', $next->textContent) === 1)) {
            $parent->insertBefore($doc->createTextNode($sep), $n);
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

    /** Заголовок, за которым сразу заголовок старшего уровня (h3 перед h2) или конец блока, — без содержимого; убираем. */
    private function pruneOrphanHeadings(\DOMXPath $xp, \DOMElement $root): void
    {
        do {
            $removed = 0;
            foreach (iterator_to_array($xp->query('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6', $root) ?: []) as $h) {
                if (!$h instanceof \DOMElement || $h->parentNode === null) {
                    continue;
                }
                $level = (int) substr($h->tagName, 1);
                $next = $h->nextSibling;
                while ($next instanceof \DOMText && trim($next->textContent) === '') {
                    $next = $next->nextSibling;
                }
                $orphan = $next === null
                    || ($next instanceof \DOMElement && preg_match('~^h([1-6])$~i', $next->tagName, $m) === 1 && (int) $m[1] < $level);
                if ($orphan) {
                    $h->parentNode->removeChild($h);
                    $removed++;
                }
            }
        } while ($removed > 0);
    }

    /**
     * Оборачивает в <p> «голые» куски верхнего уровня: текст и строчные теги подряд между блоками. Пустая строка
     * (перевод строки от развёрнутого div или <br>) разделяет абзацы.
     */
    private function wrapLooseText(\DOMDocument $doc, \DOMElement $root): void
    {
        $inline = ['a', 'strong', 'em', 'b', 'i', 'span', 'sup', 'sub', 'u', 's', 'mark', 'small', 'code', 'abbr', 'time', 'cite', 'q'];
        $run = [];
        $flush = static function () use (&$run, $doc, $root): void {
            // Хвостовые пробелы абзаца — не в <p>.
            while ($run !== [] && end($run) instanceof \DOMText && trim(end($run)->textContent) === '') {
                array_pop($run);
            }
            $hasText = false;
            foreach ($run as $node) {
                if (trim($node->textContent) !== '') {
                    $hasText = true;
                    break;
                }
            }
            if ($hasText) {
                $p = $doc->createElement('p');
                $root->insertBefore($p, $run[0]);
                foreach ($run as $node) {
                    $p->appendChild($node);
                }
            }
            $run = [];
        };
        foreach (iterator_to_array($root->childNodes) as $c) {
            if ($c instanceof \DOMText && trim($c->textContent) === '') {
                if (str_contains($c->textContent, "\n")) {
                    $flush(); // граница блока
                } elseif ($run !== []) {
                    $run[] = $c; // пробел между строчными элементами внутри абзаца
                }
                continue;
            }
            if ($c instanceof \DOMText || ($c instanceof \DOMElement && in_array(strtolower($c->tagName), $inline, true))) {
                $run[] = $c;
            } else {
                $flush();
            }
        }
        $flush();
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

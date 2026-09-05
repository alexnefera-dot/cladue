<?php

declare(strict_types=1);

/*
 * Фейковые сервисы для тестов и пробного запуска без ключей:
 *
 *   php -S 127.0.0.1:8089 tests/fake-api-server.php
 *
 * Маршруты:
 *   POST /v2/web/search    — Yandex Search API v2 (JSON с rawData в base64)
 *   GET  /search/xml       — Yandex Search API v1 (XML напрямую)
 *   GET  /yandex/xml/      — XMLStock (XML в формате Яндекс.XML)
 *   GET  /search/?text=…   — страница выдачи в вёрстке yandex.ru (для source = live)
 *   GET  /showcaptcha      — страница капчи
 *   любой другой путь      — «сайт», выбирается по заголовку Host; страница зависит от Referer,
 *                            хост variant-site.ru показывает разные версии разным User-Agent
 *
 * Переменная окружения FAKE_MODE: ok (по умолчанию), captcha (выдача всегда отдаёт капчу), error (HTTP 503).
 * Специальные слова в запросе: nothing — ничего не найдено, quota — ошибка 32,
 * ratelimit — первый раз ошибка 55, captcha — капча в живой выдаче. Ключ с bad-key — недействительный.
 */

const POOL = [
    ['okna-moskva.ru', 'Пластиковые окна в Москве — купить недорого', 'Производство и установка окон ПВХ. Телефон +7 (495) 123-45-67'],
    ['www.avito.ru', 'Окна — купить на Avito', 'Объявления о продаже окон'],
    ['market.yandex.ru', 'Окна на Яндекс Маркете', 'Сравнить цены на окна'],
    ['shop.okna-moskva.ru', 'Интернет-магазин окон', 'Каталог окон и дверей'],
    ['xn--80aswg.xn--p1ai', 'Сайт.рф — окна и балконы', 'Кириллический домен'],
    ['okna-company.com', 'Windows company', 'International window manufacturer'],
    ['vk.com', 'Окна | ВКонтакте', 'Сообщество про окна'],
    ['dead-site.ru', 'Недоступный сайт', 'Сайт не отвечает'],
    ['redirect-site.ru', 'Переехавший сайт', 'Сайт переехал на другой домен'],
    ['phone-site.ru', 'Сайт с телефоном', 'Звоните нам'],
    ['cp1251-site.ru', 'Сайт в кодировке windows-1251', 'Старый сайт'],
    ['forum.okna-talk.ru', 'Форум об окнах — отзывы', 'Обсуждение окон и монтажников'],
    ['okna-piter.spb.ru', 'Окна в Петербурге', 'Установка окон в СПб'],
    ['balkon-master.ru', 'Остекление балконов — цена', 'Остекление и отделка балконов'],
    ['parked-site.ru', 'Домен продаётся', 'Этот домен продаётся'],
];

/**
 * Адрес страницы сайта: в режиме local — на этот же сервер по http (для тестов визитов).
 */
function siteUrl(string $host, int $position): string
{
    if ((getenv('FAKE_MODE') ?: 'ok') === 'local') {
        return 'http://' . $host . ':' . ($_SERVER['SERVER_PORT'] ?? '80') . '/page-' . $position . '/';
    }

    return 'https://' . $host . '/page-' . $position . '/';
}

/**
 * @return list<array{0: string, 1: string, 2: string}>
 */
function rotatedPool(string $query): array
{
    $pool = POOL;
    $shift = crc32(mb_strtolower($query)) % count($pool);

    return array_merge(array_slice($pool, $shift), array_slice($pool, 0, $shift));
}

function fakeXml(string $query, int $page, int $groupsOnPage): string
{
    $q = mb_strtolower($query);
    $requestXml = sprintf(
        '<request><query>%s</query><page>%d</page><groupings><groupby attr="d" mode="deep" groups-on-page="%d" docs-in-group="1" curcateg="-1"/></groupings></request>',
        htmlspecialchars($query, ENT_XML1),
        $page,
        $groupsOnPage,
    );
    $head = '<?xml version="1.0" encoding="utf-8"?><yandexsearch version="1.0">' . $requestXml . '<response date="20260904T120000">';

    if (str_contains($q, 'nothing')) {
        return $head . '<error code="15">Искомая комбинация слов нигде не встречается</error></response></yandexsearch>';
    }
    if (str_contains($q, 'quota')) {
        return $head . '<error code="32">Исчерпан лимит запросов</error></response></yandexsearch>';
    }
    if (str_contains($q, 'ratelimit')) {
        $marker = sys_get_temp_dir() . '/yandex-sites-fake-' . md5($q);
        if (!is_file($marker)) {
            touch($marker);

            return $head . '<error code="55">Превышена частота запросов</error></response></yandexsearch>';
        }
        unlink($marker);
    }

    $slice = array_slice(rotatedPool($query), $page * $groupsOnPage, $groupsOnPage);
    $groups = '';
    foreach ($slice as $i => [$host, $title, $passage]) {
        $position = $page * $groupsOnPage + $i + 1;
        $url = siteUrl($host, $position);
        $groups .= sprintf(
            '<group><categ attr="d" name="%1$s"/><doccount>1</doccount><relevance/>'
            . '<doc id="doc%2$d"><relevance/><url>%3$s</url><domain>%1$s</domain><title>%4$s</title>'
            . '<headline>%5$s</headline><modtime>20260101T000000</modtime><passages><passage>%5$s</passage></passages>'
            . '<mime-type>text/html</mime-type></doc></group>',
            htmlspecialchars($host, ENT_XML1),
            $position,
            htmlspecialchars($url, ENT_XML1),
            str_replace('окна', '<hlword>окна</hlword>', htmlspecialchars($title, ENT_XML1)),
            htmlspecialchars($passage, ENT_XML1),
        );
    }

    return $head
        . sprintf('<reqid>fake-%s</reqid><found priority="all">%d</found><found-human>Нашлось %d ответов</found-human>', md5($q), count(POOL), count(POOL))
        . sprintf('<results><grouping attr="d" mode="deep" groups-on-page="%d" docs-in-group="1" curcateg="-1">', $groupsOnPage)
        . $groups
        . '</grouping></results></response></yandexsearch>';
}

/**
 * Страница выдачи в вёрстке, близкой к yandex.ru: 10 результатов на странице,
 * рекламный блок и колдунщик карт на первой странице, пагинация.
 */
function fakeSerpHtml(string $query, int $page, string $lr): string
{
    $perPage = 10;
    $pool = rotatedPool($query);
    $slice = array_slice($pool, $page * $perPage, $perPage);
    $hasMore = count($pool) > ($page + 1) * $perPage;
    $q = htmlspecialchars($query);
    $items = '';

    if ($page === 0) {
        $items .= <<<HTML
        <li class="serp-item serp-item_card serp-adv-item desktop-card" data-cid="0">
          <div class="Organic organic Organic_type_ad">
            <div class="Organic-Header">
              <a class="Link Link_theme_normal OrganicTitle-Link organic__url link" href="https://yabs.yandex.ru/count/WZ0ejI_zO3m0000?ad=1" target="_blank"><h2 class="OrganicTitle-LinkText"><span>Окна ПВХ со скидкой 40% — от производителя</span></h2></a>
              <div class="Organic-Subtitle"><span class="Organic-SubtitleLabel label">Реклама</span></div>
            </div>
          </div>
        </li>

        HTML;
    }

    foreach ($slice as $i => [$host, $title, $passage]) {
        $position = $page * $perPage + $i + 1;
        $url = siteUrl($host, $position);
        $titleHtml = str_replace('окна', '<b>окна</b>', htmlspecialchars($title));
        $passageHtml = htmlspecialchars($passage);
        $items .= <<<HTML
        <li class="serp-item serp-item_card desktop-card" data-cid="{$position}">
          <div class="Organic organic Typo Typo_text_m Typo_line_m">
            <div class="Organic-Header organic__header">
              <a class="Link Link_theme_normal OrganicTitle-Link organic__url link" href="{$url}" target="_blank" rel="noopener">
                <h2 class="OrganicTitle-LinkText organic__title"><span>{$titleHtml}</span></h2>
              </a>
              <div class="Path Organic-Path path organic__path">
                <a class="Link Link_theme_outer Path-Item path__item" href="{$url}" target="_blank"><b>{$host}</b>›page-{$position}</a>
              </div>
            </div>
            <div class="Organic-ContentWrapper organic__content-wrapper">
              <div class="TextContainer OrganicText organic__text text-container Typo Typo_text_m Typo_line_m">
                <span class="OrganicTextContentSpan">{$passageHtml}</span>
              </div>
            </div>
          </div>
        </li>

        HTML;
        if ($page === 0 && $i === 1) {
            $items .= <<<HTML
        <li class="serp-item serp-item_card desktop-card" data-cid="wizard">
          <div class="Organic organic Organic_type_maps">
            <div class="Organic-Header">
              <a class="Link OrganicTitle-Link" href="https://yandex.ru/maps/213/moscow/search/{$q}/"><h2 class="OrganicTitle-LinkText"><span>{$q} — на карте Москвы</span></h2></a>
            </div>
          </div>
        </li>

        HTML;
        }
    }

    $pager = '<div class="Pager pager">';
    if ($page > 0) {
        $pager .= sprintf('<a class="Link Pager-Item Pager-Item_type_prev" href="/search/?text=%s&amp;p=%d">назад</a>', rawurlencode($query), $page - 1);
    }
    if ($hasMore) {
        $pager .= sprintf('<a class="Link Pager-Item Pager-Item_type_next" href="/search/?text=%s&amp;p=%d">дальше</a>', rawurlencode($query), $page + 1);
    }
    $pager .= '</div>';

    return <<<HTML
    <!DOCTYPE html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>{$q} — Яндекс: нашлось 15 результатов</title></head>
    <body class="b-page">
    <div class="main__content">
    <form class="search3" action="/search/"><input name="text" value="{$q}"><input type="hidden" name="lr" value="{$lr}"></form>
    <div class="serp-adv__found">Нашлось 15 результатов</div>
    <ul class="serp-list serp-list_left_yes">
    {$items}</ul>
    {$pager}
    </div>
    </body>
    </html>
    HTML;
}

function captchaHtml(): string
{
    return <<<'HTML'
    <!DOCTYPE html>
    <html lang="ru">
    <head><meta charset="utf-8"><title>Ой!</title></head>
    <body>
    <div class="CheckboxCaptcha" data-testid="checkbox-captcha">
      <form method="POST" action="/checkcaptcha?key=fake">
        <div class="CheckboxCaptcha-Anchor">Подтвердите, что запросы отправляли вы, а не робот</div>
        <input type="submit" value="Я не робот">
      </form>
    </div>
    </body>
    </html>
    HTML;
}

$uri = (string) (parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$auth = (string) ($_SERVER['HTTP_AUTHORIZATION'] ?? '');
$mode = (string) (getenv('FAKE_MODE') ?: 'ok');

if ($uri === '/v2/web/search' && $method === 'POST') {
    header('Content-Type: application/json');
    if (preg_match('~^(Api-Key|Bearer) \S+$~', $auth) !== 1 || str_contains($auth, 'bad-key')) {
        http_response_code(401);
        echo json_encode(['code' => 16, 'message' => 'Unauthenticated: invalid API key']);

        return;
    }
    $body = json_decode((string) file_get_contents('php://input'), true);
    if (!is_array($body) || !isset($body['query']['queryText']) || !isset($body['folderId'])) {
        http_response_code(400);
        echo json_encode(['code' => 3, 'message' => 'Invalid request: query.queryText and folderId are required']);

        return;
    }
    $xml = fakeXml((string) $body['query']['queryText'], (int) ($body['query']['page'] ?? 0), (int) ($body['groupSpec']['groupsOnPage'] ?? 10));
    echo json_encode(['rawData' => base64_encode($xml)]);

    return;
}

if ($uri === '/search/xml') {
    header('Content-Type: text/xml; charset=utf-8');
    $apiKey = (string) ($_GET['apikey'] ?? '');
    if (($apiKey === '' && !str_starts_with($auth, 'Bearer ')) || str_contains($apiKey, 'bad-key')) {
        echo '<?xml version="1.0" encoding="utf-8"?><yandexsearch version="1.0"><response date="20260904T120000"><error code="43">Ключ не найден</error></response></yandexsearch>';

        return;
    }
    $groupsOnPage = 10;
    if (preg_match('/groups-on-page=(\d+)/', (string) ($_GET['groupby'] ?? ''), $m) === 1) {
        $groupsOnPage = (int) $m[1];
    }
    echo fakeXml((string) ($_GET['query'] ?? ''), (int) ($_GET['page'] ?? 0), $groupsOnPage);

    return;
}

if ($uri === '/yandex/xml/' || $uri === '/yandex/xml') {
    header('Content-Type: text/xml; charset=utf-8');
    $key = (string) ($_GET['key'] ?? '');
    // Тестовый крючок: по запросу с маркером __capture__ записываем принятые GET-параметры в файл,
    // чтобы тест мог проверить, что device/domain/доп. параметры XMLStock дошли до запроса.
    if (str_contains((string) ($_GET['query'] ?? ''), '__capture__')) {
        @file_put_contents(sys_get_temp_dir() . '/yandex-sites-fake-capture.json', json_encode($_GET));
    }
    if (($_GET['user'] ?? '') === '' || $key === '' || str_contains($key, 'bad-key')) {
        echo '<?xml version="1.0" encoding="utf-8"?><yandexsearch version="1.0"><response date="20260904T120000"><error code="42">Invalid user or key</error></response></yandexsearch>';

        return;
    }
    $groupsOnPage = 10;
    if (preg_match('/groups-on-page=(\d+)/', (string) ($_GET['groupby'] ?? ''), $m) === 1) {
        $groupsOnPage = (int) $m[1];
    }
    echo fakeXml((string) ($_GET['query'] ?? ''), (int) ($_GET['page'] ?? 0), $groupsOnPage);

    return;
}

if ($uri === '/showcaptcha') {
    header('Content-Type: text/html; charset=utf-8');
    echo captchaHtml();

    return;
}

if ($uri === '/search/' || $uri === '/search') {
    $query = (string) ($_GET['text'] ?? '');
    if ($mode === 'error') {
        http_response_code(503);
        header('Content-Type: text/html; charset=utf-8');
        echo '<html><head><title>503</title></head><body>Service unavailable</body></html>';

        return;
    }
    if ($mode === 'captcha' || str_contains(mb_strtolower($query), 'captcha')) {
        header('Location: /showcaptcha?retpath=' . rawurlencode((string) ($_SERVER['REQUEST_URI'] ?? '/search/')), true, 302);

        return;
    }
    header('Content-Type: text/html; charset=utf-8');
    if (str_contains(mb_strtolower($query), 'nothing')) {
        echo '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>' . htmlspecialchars($query) . ' — Яндекс</title></head><body><div class="misspell"><div class="misspell__message">По вашему запросу ничего не нашлось.</div></div><ul class="serp-list"></ul></body></html>';

        return;
    }
    echo fakeSerpHtml($query, (int) ($_GET['p'] ?? 0), (string) ($_GET['lr'] ?? ''));

    return;
}

// «Сайты» для проверки SiteChecker и визитов: выбираются по заголовку Host.
$host = strtolower((string) explode(':', (string) ($_SERVER['HTTP_HOST'] ?? ''), 2)[0]);
$port = (string) ($_SERVER['SERVER_PORT'] ?? '80');
$referer = (string) ($_SERVER['HTTP_REFERER'] ?? '');
$userAgent = (string) ($_SERVER['HTTP_USER_AGENT'] ?? '');
$visitor = str_contains($referer, 'yandex') ? 'Вы пришли из поиска Яндекса — специальное предложение' : 'Прямой заход';
if (stripos($userAgent, 'yandexbot') !== false) {
    $visitor = 'Версия для поискового робота Яндекса';
}
// Ссылка из шапки, уводящая на другой сайт (для проверки пропуска редиректов при обходе).
if ($uri === '/leave') {
    http_response_code(302);
    header('Location: http://other-domain.ru:' . $port . '/');

    return;
}
// Шапка сайта с внутренними ссылками, внешней и уводящей на другой сайт.
$navHtml = '<header class="site-header"><nav class="main-menu">'
    . '<a href="/">Главная</a>'
    . '<a href="/about">О компании</a>'
    . '<a href="/contacts">Контакты</a>'
    . '<a href="/leave">Партнёр</a>'
    . '<a href="https://vk.com/' . htmlspecialchars($host) . '">ВКонтакте</a>'
    . '</nav></header>';
header('Content-Type: text/html; charset=utf-8');
switch ($host) {
    case 'dead-site.ru':
        http_response_code(404);
        echo '<html><head><title>404</title></head><body>Not found</body></html>';

        return;
    case 'redirect-site.ru':
        http_response_code(302);
        header('Location: http://other-domain.ru:' . $port . '/');

        return;
    case 'brandnet.ru':
        // apex редиректит на бренд-поддомен ТОГО ЖЕ сайта (kush.brandnet.ru) — это не уход
        // на чужой сайт: страницу надо сохранить, а меню разобрать относительно поддомена.
        http_response_code(302);
        header('Location: http://kush.brandnet.ru:' . $port . '/');

        return;
    case 'kush.brandnet.ru':
        // Реальный сайт бренда: главная + уникальные /about и /promo (для дедупа тексты разные).
        $bnWords = [];
        for ($bn = 0; $bn < 40; $bn++) {
            $bnWords[] = 'bn' . substr(md5($uri), 0, 8) . $bn;
        }
        $bnH1 = $uri === '/promo' ? 'Промо' : ($uri === '/about' ? 'О нас' : 'Куш Казино');
        echo '<html><head><title>' . $bnH1 . '</title></head><body>'
            . '<header><nav class="main-menu"><a href="/">Главная</a><a href="/about">О нас</a><a href="/promo">Промо</a></nav></header>'
            . '<h1>' . $bnH1 . '</h1><p class="content">' . implode(' ', $bnWords) . '</p></body></html>';

        return;
    case 'phone-site.ru':
        echo '<html><head><title>Сайт с телефоном</title></head><body><p>Звоните: +7 (495) 123-45-67</p><a href="mailto:info@phone-site.ru">Почта</a></body></html>';

        return;
    case 'cp1251-site.ru':
        header('Content-Type: text/html; charset=windows-1251');
        echo mb_convert_encoding('<html><head><title>Сайт в кодировке windows-1251</title></head><body><p>Телефон: +7 (812) 765-43-21</p></body></html>', 'Windows-1251', 'UTF-8');

        return;
    case 'parked-site.ru':
        echo '<html><head><title>Домен продаётся</title></head><body><h1>Домен продаётся</h1></body></html>';

        return;
    case 'honest-site.ru':
        echo '<html><head><title>Честный сайт</title></head><body><p>Одна и та же страница для всех посетителей</p></body></html>';

        return;
    case 'localeretry.ru':
        // /ru/app отдаёт 404 (адрес с языковым префиксом), а /app — 200. Докачка должна попробовать
        // адрес без /ru и добрать страницу. Остальные страницы уникальны (для дедупа).
        if ($uri === '/ru/app') {
            http_response_code(404);
            echo '<html><head><title>404</title></head><body>Not found</body></html>';

            return;
        }
        $lrWords = [];
        for ($lr = 0; $lr < 40; $lr++) {
            $lrWords[] = 'lr' . substr(md5($uri), 0, 8) . $lr;
        }
        $lrH1 = $uri === '/app' ? 'Приложение' : ($uri === '/about' ? 'О нас' : 'Главная');
        echo '<html><head><title>' . $lrH1 . '</title></head><body>'
            . '<header><nav class="main-menu"><a href="/">Главная</a><a href="/about">О нас</a><a href="/ru/app">Приложение</a></nav></header>'
            . '<h1>' . $lrH1 . '</h1><p class="content">' . implode(' ', $lrWords) . '</p></body></html>';

        return;
    case 'duptest.ru':
        // /contacts отдаёт (200) то же тело, что и /about — это дубликат именно страницы about,
        // остальные страницы уникальны. Проверяем, что в ошибке указано, с какой страницей совпало.
        $bodyKey = $uri === '/contacts' ? '/about' : $uri;
        $words = [];
        for ($i = 0; $i < 40; $i++) {
            $words[] = 'w' . substr(md5($bodyKey), 0, 8) . $i;
        }
        $h1 = $bodyKey === '/about' ? 'О нас' : (($bodyKey === '/' || $bodyKey === '') ? 'Главная' : 'Страница ' . $bodyKey);
        echo '<html><head><title>' . htmlspecialchars($h1) . '</title></head><body>' . $navHtml
            . '<h1>' . htmlspecialchars($h1) . '</h1><p class="content">' . implode(' ', $words) . '</p></body></html>';

        return;
    case 'softsite.ru':
        // Мягкий 404: несуществующий путь отдаётся с кодом 404, но телом-копией главной (шаблон
        // сайта). Раньше такой ответ ошибочно считался «дубликатом», а не «страница не найдена».
        if ($uri === '/' || $uri === '' || $uri === '/about') {
            $h1 = $uri === '/about' ? 'О нас' : 'Главная softsite';
            $body = $uri === '/about' ? 'текст про компанию ' : 'домашний текст ';
            echo '<html><head><title>' . $h1 . '</title></head><body>' . $navHtml
                . '<h1>' . $h1 . '</h1><p class="content">' . str_repeat($body, 30) . '</p></body></html>';
        } else {
            http_response_code(404);
            echo '<html><head><title>Главная softsite</title></head><body>' . $navHtml
                . '<h1>Главная softsite</h1><p class="content">' . str_repeat('домашний текст ', 30) . '</p></body></html>';
        }

        return;
    case 'variant-site.ru':
        $variant = crc32($userAgent) % 2 === 0 ? 'A' : 'B';
        echo '<html><head><title>Вариант ' . $variant . '</title></head><body><h1>Страница варианта ' . $variant . '</h1><p>' . htmlspecialchars($visitor) . '</p></body></html>';

        return;
    case 'brand-a.tpl.ru':
        // Меню ведёт на свой поддомен (/bonus), на СОСЕДНИЙ поддомен (другой бренд) и реальную
        // страницу за «циклом» переключателя языка (/ru/ru/ru/promo → схлопнётся в /ru/promo).
        $words = [];
        for ($i = 0; $i < 30; $i++) {
            $words[] = 'w' . substr(md5($uri), 0, 8) . $i;
        }
        echo '<html><head><title>Бренд A</title></head><body><header><nav>'
            . '<a href="/">Главная</a>'
            . '<a href="/bonus">Бонус</a>'
            . '<a href="https://brand-b.tpl.ru/page">Другой бренд</a>'
            . '<a href="/ru/ru/ru/ru/promo">Промо за циклом</a>'
            . '</nav></header><h1>Бренд A</h1><p class="c">' . implode(' ', $words) . '</p></body></html>';

        return;
    case 'footeronly.ru':
        // Меню ТОЛЬКО в подвале; ссылки за «циклом» /RU-ru/…; есть ссылка на «/» (не должна дать main-2).
        $words = [];
        for ($i = 0; $i < 30; $i++) {
            $words[] = 'w' . substr(md5($uri), 0, 8) . $i;
        }
        echo '<html><head><title>Подвальное меню</title></head><body>'
            . '<header><nav><a href="/promo">Промо</a></nav></header>'
            . '<h1>Главная</h1><p class="c">' . implode(' ', $words) . '</p>'
            . '<footer><div class="footer-menu"><nav class="footer-nav-links">'
            . '<a href="/">Главная</a>'
            . '<a href="/RU-ru/RU-ru/RU-ru/app">Приложение</a>'
            . '<a href="/RU-ru/RU-ru/RU-ru/bonus">Бонус</a>'
            . '<a href="/RU-ru/RU-ru/RU-ru/promo">Промо (тот же, с языком)</a>'
            . '</nav></div></footer></body></html>';

        return;
    case 'ourtpl.ru':
        // Наш шаблон: устойчивая метка в <head> (токен верификации) при меняющемся теле (QR).
        echo '<html><head><title>Промо-шаблон</title>'
            . '<meta name="yandex-verification" content="OWNMARK123">'
            . '</head><body>' . $navHtml
            . '<h1>Бонусы</h1><p class="qr">' . md5((string) mt_rand()) . '</p></body></html>';

        return;
    case 'agegate.ru':
        // Заглушка проверки возраста 18+ — одинаковая на всех путях (реальный контент за ней).
        // Шапка с меню присутствует, поэтому ссылки на внутренние страницы всё равно собираются.
        echo '<html><head><title>Подтвердите возраст</title></head><body>'
            . $navHtml
            . '<div class="age-gate"><h1>Вам есть 18 лет?</h1>'
            . '<button type="button">Да, мне есть 18</button> <a href="/no">Нет</a></div>'
            . '</body></html>';

        return;
    default:
        // Тело страницы зависит от пути (у одностраничника onepager.ru — одинаковое для всех путей),
        // чтобы можно было отличать одинаковые страницы от разных.
        $key = $host === 'onepager.ru' ? 'one' : $uri;
        $words = [];
        for ($i = 0; $i < 40; $i++) {
            $words[] = 'kw' . substr(md5($key), 0, 8) . $i;
        }
        echo '<html><head><title>' . htmlspecialchars($host) . '</title></head><body>'
            . $navHtml
            . '<h1>Добро пожаловать на ' . htmlspecialchars($host) . '</h1>'
            . '<p class="visitor">' . htmlspecialchars($visitor) . '</p>'
            . '<p class="content">' . implode(' ', $words) . '</p>'
            . '<div id="js-rendered"></div>'
            . '<script>document.getElementById("js-rendered").textContent = "rendered by browser";</script>'
            . '</body></html>';
}

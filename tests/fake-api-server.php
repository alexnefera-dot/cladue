<?php

declare(strict_types=1);

/*
 * Фейковый Yandex Search API для тестов и пробного запуска без ключа:
 *
 *   php -S 127.0.0.1:8089 tests/fake-api-server.php
 *
 * Эмулирует:
 *   POST /v2/web/search  — API v2 (JSON с rawData в base64)
 *   GET  /search/xml     — API v1 (XML напрямую)
 *   любой другой путь    — «сайт» по заголовку Host (для проверки SiteChecker)
 *
 * Специальные слова в запросе: nothing — ошибка 15 (ничего не найдено),
 * quota — ошибка 32 (лимит исчерпан), ratelimit — первый раз ошибка 55, затем результаты.
 * Ключ, содержащий bad-key, считается недействительным.
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

    $pool = POOL;
    $shift = crc32($q) % count($pool);
    $pool = array_merge(array_slice($pool, $shift), array_slice($pool, 0, $shift));
    $slice = array_slice($pool, $page * $groupsOnPage, $groupsOnPage);

    $groups = '';
    foreach ($slice as $i => [$host, $title, $passage]) {
        $position = $page * $groupsOnPage + $i + 1;
        $url = 'https://' . $host . '/page-' . $position . '/';
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

$uri = (string) (parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?: '/');
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$auth = (string) ($_SERVER['HTTP_AUTHORIZATION'] ?? '');

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

// «Сайты» для проверки SiteChecker: выбираются по заголовку Host.
$host = strtolower((string) explode(':', (string) ($_SERVER['HTTP_HOST'] ?? ''), 2)[0]);
$port = (string) ($_SERVER['SERVER_PORT'] ?? '80');
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
    default:
        echo '<html><head><title>' . htmlspecialchars($host) . '</title></head><body><h1>Добро пожаловать на ' . htmlspecialchars($host) . '</h1></body></html>';
}

<?php

declare(strict_types=1);

namespace YandexSites\Live;

/**
 * User-Agent, которыми представляется скрипт.
 *
 *  - YANDEX_BOT — робот Яндекса; используется по умолчанию для визитов на сайты
 *    и HTTP-проверки, чтобы видеть страницы такими, какими сайт отдаёт их поисковику;
 *  - BROWSERS — распространённые настольные браузеры; используются для запросов
 *    к странице выдачи (робот Яндекса выдачу не получит) и для дополнительных
 *    вариантов визита, чтобы сравнить версию для робота с версией для посетителя;
 *  - VISITORS — список для визитов: сначала робот, затем браузеры (по одному на вариант).
 */
final class UserAgents
{
    public const YANDEX_BOT = 'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)';

    public const BROWSERS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    ];

    public const VISITORS = [self::YANDEX_BOT, ...self::BROWSERS];

    public static function isBot(string $userAgent): bool
    {
        return stripos($userAgent, 'yandexbot') !== false;
    }
}

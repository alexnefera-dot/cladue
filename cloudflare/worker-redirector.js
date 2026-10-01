/**
 * Cloudflare Worker редиректора — один на все домены.
 *
 * Код не знает, на каком домене он стоит и куда ведёт: домен-источник берётся
 * из самого запроса, домен-назначение — из переменной TARGET в настройках
 * воркера. Поэтому один и тот же скрипт вешается маршрутами сразу на все наши
 * домены, включая текущий рабочий, и при переезде правится одно значение.
 *
 * НАСТРОЙКА (делается один раз):
 *   1. Workers & Pages → воркер → Settings → Variables and Secrets →
 *      добавить переменную  TARGET = sitegrator-red1.top  (текущий рабочий домен).
 *   2. Settings → Domains & Routes → маршрут /go/* на каждый ОТСЛУЖИВШИЙ домен:
 *        sitegrator.com/go/*
 *      На рабочий домен маршрут не вешаем: воркер его всё равно пропускает, но
 *      каждый живой клик стал бы лишним вызовом воркера и лишним подзапросом
 *      к origin. Маршрут на него добавляется в момент, когда он становится
 *      отслужившим.
 *      Маршрут именно /go/* : панель, API и приём постбеков через воркер идти
 *      не должны — постбеки редиректить нельзя, многие отправители не идут
 *      по 302, и платить за них вызовами воркера тоже незачем.
 *
 * ПЕРЕЕЗД НА НОВЫЙ ДОМЕН — две операции в одном экране:
 *   1. TARGET = новый домен.
 *   2. Маршрут /go/* на домен, который только что перестал быть рабочим.
 * Порядок между ними не важен и гонки не создаёт: пока маршрута нет, домен
 * работает как обычный трекер, а пока он равен TARGET — воркер его пропускает.
 *
 * Что делает на запросе /go/:
 *   — слаг кампании и все параметры сохраняются: /go/faro?s=x.team/ru уходит
 *     тем же адресом на TARGET. Без слага клики всех кампаний схлопнулись бы
 *     в одну и статистика перестала бы что-либо значить;
 *   — добавляется метка _src с доменом, на который пришёл запрос. По ней в
 *     панели видно, сколько трафика ещё держится на каждом старом домене, и
 *     когда его можно гасить;
 *   — роботы Яндекса и Гугла (мобильные и десктопные) редирект не получают:
 *     им отдаётся домен, на который они пришли, как есть. Ссылка /go/ стоит
 *     в теле проиндексированных страниц, и для робота 302 на другой домен —
 *     внешний редирект прямо со страницы. Человеку он нужен, роботу нет.
 */

// Запасное значение на случай, если переменную не завели. Держать его
// в актуальном состоянии не нужно — достаточно, чтобы воркер не ушёл в никуда.
const TARGET_FALLBACK = 'sitegrator-red1.top';

// Проверка нарочно узкая. Ловить просто слово «yandex» нельзя: мобильное
// приложение Яндекса у живого человека шлёт UA с YandexSearch — такой посетитель
// остался бы на старом домене и потерялся бы из статистики нового.
const SEARCH_BOTS = /(yandex\.com\/bots|yandex(bot|mobilebot|images|imageresizer|video|media|blogs|news|direct|directdyn|market|pagechecker|webmaster|metrika|calendar|sitelinks|adnet|favicons|renderresourcesbot|screenshotbot|turbo|verticals|accessibilitybot|ontodb|vertis)\b|googlebot|adsbot-google|mediapartners-google|apis-google|feedfetcher-google|storebot-google|googleother|google-inspectiontool|google-extended|google-read-aloud|google-site-verification|google-safety)/i;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith('/go/')) {
      return fetch(request);           // всё остальное — как было
    }

    // пробелы и случайный https:// в значении переменной не должны ломать редирект
    const target = String((env && env.TARGET) || TARGET_FALLBACK)
      .trim().replace(/^https?:\/\//i, '').replace(/\/.*$/, '').toLowerCase();

    // домен уже рабочий — уводить некуда. Это же защищает от петли и позволяет
    // держать маршрут воркера на всех доменах сразу, не разбирая, какой текущий.
    if (!target || url.hostname.toLowerCase() === target) {
      return fetch(request);
    }

    // робота поисковика не уводим на другой домен
    if (SEARCH_BOTS.test(request.headers.get('user-agent') || '')) {
      return fetch(request);
    }

    const to = new URL(url);
    to.hostname = target;
    to.searchParams.set('_src', url.hostname);
    return Response.redirect(to.toString(), 302);
  },
};

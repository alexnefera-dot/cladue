/* Смена домена в реф-ссылках САЙТОВ + разбор чужих доменов — spin-engine.top
 *
 * Запускать в консоли на странице со списком сайтов:
 *   https://spin-engine.top/sites     (если такая есть — возьмёт все сразу)
 *   https://spin-engine.top/domains   (возьмёт то, что на странице)
 *
 * Делает две вещи за один проход:
 *   1. меняет домен OLD на NEW, остальная часть ссылки остаётся как была;
 *   2. считает все остальные домены, которые встретились в рефках, и выписывает,
 *      у каких сайтов они стоят — по ним потом видно, что ещё осталось перевести.
 *
 * Сначала DRY = true — ничего не сохраняет, только показывает.
 */
(async () => {
  const OLD   = 'sitegrator-red1.top';
  const NEW   = 'sitegoratorr2.top';
  const DRY   = true;    // <-- false, когда проверишь вывод
  const PAUSE = 250;

  const log = (...a) => console.log('%c[сайты]', 'color:#4338ca;font-weight:bold', ...a);

  const grab = (html) => {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const links = [...doc.querySelectorAll('a[href*="/sites/view/"], a[href*="/sites/edit/"]')];
    return [...new Set(links
      .map(a => (a.getAttribute('href') || '').match(/\/sites\/(?:view|edit)\/(\d+)/)?.[1])
      .filter(Boolean))];
  };

  // хост из ссылки, без схемы и www
  const hostOf = (u) => {
    const m = String(u).trim().replace(/^https?:\/\//i, '').split(/[\/?#]/)[0];
    return m.replace(/^www\./i, '').toLowerCase();
  };

  // --- Собираем id. Сначала общий список, потом текущая страница, потом живой DOM.
  let ids = [];
  for (const src of ['/sites', location.pathname + location.search]) {
    try {
      const html = await (await fetch(src, { credentials: 'same-origin' })).text();
      const found = grab(html);
      if (found.length > ids.length) { ids = found; log(`из ${src}: ${found.length}`); }
    } catch (e) { /* страницы может не быть — это нормально */ }
  }
  ids = [...new Set([...ids, ...grab(document.documentElement.outerHTML)])];

  log('всего сайтов:', ids.length, DRY ? '· режим проверки' : '· БОЕВОЙ РЕЖИМ');
  if (!ids.length) return console.error('ничего не нашлось — открой список сайтов и запусти снова');

  let changed = 0, already = 0, empty = 0, failed = 0;
  const others = new Map();   // чужой домен -> [{id, ref}]

  for (const [i, id] of ids.entries()) {
    const nom = `${i + 1}/${ids.length} id=${id}`;
    try {
      const url  = `/sites/edit/${id}`;
      const html = await (await fetch(url, { credentials: 'same-origin' })).text();
      const doc  = new DOMParser().parseFromString(html, 'text/html');
      const fld  = doc.querySelector('[name="ref_link"]');
      if (!fld) { failed++; log(`${nom} — поля ref_link нет`); continue; }

      const was  = (fld.value ?? fld.textContent ?? '').trim();
      const host = hostOf(was);

      if (was === '') { empty++; log(`${nom} — пусто`); continue; }

      if (host !== OLD.toLowerCase()) {
        if (host === NEW.toLowerCase()) { already++; }
        else {
          // Чужой домен — не трогаем: вдруг это другой трекер или другая связка.
          // Просто записываем, чтобы потом было видно, что ещё не переведено.
          if (!others.has(host)) others.set(host, []);
          others.get(host).push({ id, ref: was });
        }
        continue;
      }

      const now  = was.split(OLD).join(NEW);
      const form = fld.closest('form');
      if (!form) { failed++; log(`${nom} — форма не найдена`); continue; }

      if (DRY) { changed++; log(`${nom} — БУДЕТ: ${was}  →  ${now}`); }
      else {
        // Отправляем форму целиком, подменив одно поле: так уезжают обратно
        // и csrf-токен, и все прочие значения — иначе админка их затрёт.
        fld.value = now; fld.textContent = now;
        const fd = new FormData(form);
        fd.set('ref_link', now);
        const res = await fetch(form.getAttribute('action') || url, {
          method: (form.getAttribute('method') || 'post').toUpperCase(),
          body: fd, credentials: 'same-origin',
        });
        if (res.ok) { changed++; log(`${nom} — сохранено: ${now}`); }
        else        { failed++;  log(`${nom} — ошибка HTTP ${res.status}`); }
      }
    } catch (e) { failed++; log(`${nom} — сбой: ${e.message}`); }
    // Пропущенные сайты в лог не пишутся, и при уже переведённом списке скрипт
    // молчит минутами — со стороны выглядит как зависший. Поэтому отметка о ходе.
    if ((i + 1) % 25 === 0) log(`пройдено ${i + 1} из ${ids.length}`);
    await new Promise(r => setTimeout(r, PAUSE));
  }

  // ---- отчёт по чужим доменам ----
  const rows = [...others.entries()].sort((a, b) => b[1].length - a[1].length);
  const tsv  = rows.flatMap(([host, list]) => list.map(x => [host, x.id, x.ref].join('\t'))).join('\n');

  window.__sites = { others: Object.fromEntries(rows), tsv };

  if (rows.length) {
    console.log('\n===== сайты с ДРУГИМИ доменами в рефке =====');
    for (const [host, list] of rows) console.log(`${host} — ${list.length}: id ${list.map(x => x.id).join(', ')}`);
    console.log('\n----- подробно (домен / id / ссылка) -----\n' + tsv + '\n');
    if (navigator.clipboard && document.hasFocus()) {
      navigator.clipboard.writeText(tsv)
        .then(() => log('список чужих скопирован в буфер'))
        .catch(() => log('в буфер не легло — забери из вывода или: copy(__sites.tsv)'));
    } else {
      log('буфер недоступен — скопировать: copy(__sites.tsv)');
    }
  }

  log(`ГОТОВО. ${DRY ? 'будет изменено' : 'изменено'}: ${changed}, уже на ${NEW}: ${already}, ` +
      `с чужими доменами: ${rows.reduce((n, r) => n + r[1].length, 0)} (доменов: ${rows.length}), ` +
      `пусто: ${empty}, ошибок: ${failed}`);
})();

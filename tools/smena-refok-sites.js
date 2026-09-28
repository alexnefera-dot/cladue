/* Смена домена в реф-ссылках САЙТОВ — spin-engine.top
 *
 * Запускать в консоли на странице со списком сайтов:
 *   https://spin-engine.top/sites     (если такая есть — возьмёт все сразу)
 *   https://spin-engine.top/domains   (возьмёт то, что на странице)
 *
 * Сначала DRY = true — только показывает, что изменится.
 * Меняется ТОЛЬКО домен, остальная часть ссылки остаётся.
 */
(async () => {
  const OLD   = 'sitegrator.com';
  const NEW   = 'sitegrator-red1.top';
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

  // --- Собираем id. Сначала пробуем общий список, потом текущую страницу.
  let ids = [];
  for (const src of ['/sites', location.pathname + location.search]) {
    try {
      const html = await (await fetch(src, { credentials: 'same-origin' })).text();
      const found = grab(html);
      if (found.length > ids.length) { ids = found; log(`из ${src}: ${found.length}`); }
    } catch (e) { /* страницы может не быть — это нормально */ }
  }
  // плюс то, что уже отрисовано в живом DOM (DataTables прячет остальные страницы)
  ids = [...new Set([...ids, ...grab(document.documentElement.outerHTML)])];

  log('всего сайтов:', ids.length, DRY ? '· режим проверки' : '· БОЕВОЙ РЕЖИМ');
  if (!ids.length) return console.error('ничего не нашлось — открой список сайтов и запусти снова');

  let changed = 0, skipped = 0, failed = 0;

  for (const [i, id] of ids.entries()) {
    const nom = `${i + 1}/${ids.length} id=${id}`;
    try {
      const url  = `/sites/edit/${id}`;
      const html = await (await fetch(url, { credentials: 'same-origin' })).text();
      const doc  = new DOMParser().parseFromString(html, 'text/html');
      const fld  = doc.querySelector('[name="ref_link"]');
      if (!fld) { failed++; log(`${nom} — поля ref_link нет`); continue; }

      const was = (fld.value ?? fld.textContent ?? '').trim();
      if (!was.includes(OLD)) { skipped++; log(`${nom} — пропуск: ${was || '(пусто)'}`); continue; }

      const now  = was.split(OLD).join(NEW);
      const form = fld.closest('form');
      if (!form) { failed++; log(`${nom} — форма не найдена`); continue; }

      if (DRY) { changed++; log(`${nom} — БУДЕТ: ${was}  →  ${now}`); }
      else {
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
    await new Promise(r => setTimeout(r, PAUSE));
  }

  log(`ГОТОВО. ${DRY ? 'будет изменено' : 'изменено'}: ${changed}, пропущено: ${skipped}, ошибок: ${failed}`);
})();

/* Смена домена в реф-ссылках брендов — dorgen-engine.com/brands
 *
 * Запускать в консоли браузера НА СТРАНИЦЕ https://dorgen-engine.com/brands
 * (DevTools: ⌥⌘I -> вкладка Console).
 *
 * Сначала прогон вхолостую: DRY = true — ничего не сохраняется, только список
 * того, что изменится. Убедился — меняешь на false и запускаешь снова.
 *
 * Меняется ТОЛЬКО домен, остальная часть ссылки остаётся как есть.
 * Бренды, где старого домена нет, пропускаются.
 */
(async () => {
  const OLD   = 'sitegrator.com';
  const NEW   = 'sitegrator-red1.top';
  const DRY   = true;    // <-- false, когда проверишь вывод
  const PAUSE = 250;     // мс между брендами, чтобы не долбить сервер

  const log = (...a) => console.log('%c[рефки]', 'color:#4338ca;font-weight:bold', ...a);

  // --- 1. Список брендов берём из исходного HTML страницы.
  // В живом DOM видна только текущая страница DataTables, а в отданном
  // сервером HTML лежат все строки сразу.
  let ids;
  try {
    const html = await (await fetch('/brands', { credentials: 'same-origin' })).text();
    const doc  = new DOMParser().parseFromString(html, 'text/html');
    ids = [...new Set([...doc.querySelectorAll('a[href*="/brands/edit/"]')]
      .map(a => (a.getAttribute('href') || '').match(/\/brands\/edit\/(\d+)/)?.[1])
      .filter(Boolean))];
  } catch (e) {
    return console.error('не удалось получить список брендов:', e.message);
  }

  log('найдено брендов:', ids.length, DRY ? '· режим проверки, сохранений не будет' : '· БОЕВОЙ РЕЖИМ');
  if (!ids.length) return console.error('список пуст — открой https://dorgen-engine.com/brands и запусти снова');

  let changed = 0, skipped = 0, failed = 0;

  for (const [i, id] of ids.entries()) {
    const nom = `${i + 1}/${ids.length} id=${id}`;
    try {
      const url  = `/brands/edit/${id}`;
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
    await new Promise(r => setTimeout(r, PAUSE));
  }

  log(`ГОТОВО. ${DRY ? 'будет изменено' : 'изменено'}: ${changed}, пропущено: ${skipped}, ошибок: ${failed}`);
})();

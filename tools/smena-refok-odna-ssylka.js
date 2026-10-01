/* Замена реф-ссылок всех брендов на одну ссылку — dorgen-engine.com/brands
 *
 * Меняется ВСЯ строка целиком, независимо от того, что в ней было: наша рефка,
 * чужая, с параметрами или пустая. Исключений нет.
 *
 * Запускать в консоли на https://dorgen-engine.com/brands
 * (для других панелей — на их /brands, скрипт тот же).
 *
 * СНАЧАЛА DRY = true — ничего не сохраняет, показывает «было → станет».
 *
 * Замена односторонняя: прежние ссылки нигде, кроме отчёта, не остаются.
 * Отчёт печатается и копируется в буфер — сохрани его, вернуть можно только
 * по нему.
 */
(async () => {

  const LINK  = 'https://combospark.top/aey3zq5oyv';   // что ставим во все бренды
  const DRY   = true;    // <-- false, когда проверишь вывод
  const PAUSE = 250;     // мс между брендами, чтобы не долбить сервер

  const log = (...a) => console.log('%c[рефки]', 'color:#4338ca;font-weight:bold', ...a);

  // --- Список брендов берём из исходного HTML страницы: в живом DOM видна
  // только текущая страница DataTables, а в отданном сервером HTML — все строки.
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

  log('брендов:', ids.length, '· ставим:', LINK,
      DRY ? '· РЕЖИМ ПРОВЕРКИ, сохранений не будет' : '· БОЕВОЙ РЕЖИМ');
  if (!ids.length) return console.error('список пуст — открой /brands и запусти снова');

  let changed = 0, same = 0, failed = 0;
  const report = [];

  for (const [i, id] of ids.entries()) {
    const nom = `${i + 1}/${ids.length} id=${id}`;
    try {
      const url  = `/brands/edit/${id}`;
      const html = await (await fetch(url, { credentials: 'same-origin' })).text();
      const doc  = new DOMParser().parseFromString(html, 'text/html');
      const fld  = doc.querySelector('[name="ref_link"]');
      if (!fld) { failed++; log(`${nom} — поля ref_link нет`); continue; }

      const was = (fld.value ?? fld.textContent ?? '').trim();
      if (was === LINK) { same++; log(`${nom} — уже стоит, пропуск`); continue; }

      const form = fld.closest('form');
      if (!form) { failed++; log(`${nom} — форма не найдена`); continue; }

      report.push([id, was]);

      if (DRY) { changed++; log(`${nom} — БУДЕТ: ${was || '(пусто)'}  →  ${LINK}`); }
      else {
        // Отправляем форму целиком, подменив одно поле: так уезжают обратно
        // и csrf-токен, и все прочие значения — иначе админка их затрёт.
        fld.value = LINK; fld.textContent = LINK;
        const fd = new FormData(form);
        fd.set('ref_link', LINK);
        const res = await fetch(form.getAttribute('action') || url, {
          method: (form.getAttribute('method') || 'post').toUpperCase(),
          body: fd, credentials: 'same-origin',
        });
        if (res.ok) { changed++; log(`${nom} — сохранено`); }
        else        { failed++;  log(`${nom} — ошибка HTTP ${res.status}`); }
      }
    } catch (e) { failed++; log(`${nom} — сбой: ${e.message}`); }
    await new Promise(r => setTimeout(r, PAUSE));
  }

  // Отчёт — единственный след прежних ссылок.
  window.__refki = report;
  const tsv = report.map(r => r.join('\t')).join('\n');
  console.log('\n===== что было (id / прежняя ссылка) =====\n' + tsv + '\n');
  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv)
      .then(() => log('отчёт скопирован в буфер'))
      .catch(() => log('отчёт не скопировался — забери из вывода или: copy(__refki.map(r=>r.join("\\t")).join("\\n"))'));
  }
  log(`ГОТОВО. ${DRY ? 'будет изменено' : 'изменено'}: ${changed}, уже стояло: ${same}, ошибок: ${failed}`);
  if (!DRY && changed) log('СОХРАНИ ОТЧЁТ: прежние ссылки есть только в нём.');
})();

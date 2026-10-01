/* Сбор доменов и отмена ожидающих запусков — dorgen-engine.com/yandex-webmaster?tab=pending
 *
 * Сначала переписывает все строки автоочереди (контент-домен + аккаунт + id),
 * и только потом отменяет их по одной. Сбор идёт первым шагом намеренно:
 * после отмены строка исчезает, и восстановить список будет уже неоткуда.
 *
 * Отмена идёт отправкой той же скрытой формы, которую дёргает кнопка
 * «Отменить», поэтому окно подтверждения не появляется и страница не
 * перезагружается — цикл не прерывается.
 *
 * Запускать в консоли на https://dorgen-engine.com/yandex-webmaster?tab=pending
 *
 * СНАЧАЛА DRY = true — ничего не отменяет, только собирает и кладёт список
 * доменов в буфер обмена. Проверяешь список — потом false.
 */
(async () => {

  const DRY   = true;    // <-- false, когда проверишь список
  const PAUSE = 400;     // пауза между отменами, мс

  const log = (...a) => console.log('%c[автоочередь]', 'color:#b45309;font-weight:bold', ...a);

  // Строки берём из свежезагруженной копии страницы: так в список попадут все,
  // а не только отрисованная страница таблицы.
  const collect = (doc) => {
    const out = [];
    for (const form of doc.querySelectorAll('form[action*="/cancel-schedule/"]')) {
      const row    = form.closest('tr');
      const action = form.getAttribute('action') || '';
      const id     = action.match(/cancel-schedule\/(\d+)/)?.[1] || '';
      if (!row || !id) continue;

      const link   = row.querySelector('a[href*="/yandex-webmaster/view/"]');
      const domain = (link?.textContent || '').trim();
      const cells  = [...row.querySelectorAll('td')].map(td => td.textContent.trim());
      const acc    = cells.find(t => t.includes('@')) || '';

      out.push({ id, domain, acc, action, form });
    }
    return out;
  };

  let items = [];
  try {
    const html = await (await fetch(location.pathname + location.search, { credentials: 'same-origin' })).text();
    items = collect(new DOMParser().parseFromString(html, 'text/html'));
    log('со страницы получено строк:', items.length);
  } catch (e) {
    log('страницу перезапросить не вышло, беру из открытой:', e.message);
  }
  // то, что уже отрисовано в браузере, — на случай если список подгружается скриптом
  const live = collect(document);
  for (const it of live) if (!items.some(x => x.id === it.id)) items.push(it);

  if (!items.length) return console.error('ожидающих запусков не нашлось — открой вкладку «Ожидающие» и запусти снова');

  // ---- список собран, фиксируем его до любых отмен ----
  const domains = [...new Set(items.map(i => i.domain).filter(Boolean))];
  const tsv     = items.map(i => [i.domain, i.acc, i.id].join('\t')).join('\n');

  window.__ocheredi = { items: items.map(({ form, ...rest }) => rest), domains };
  console.log('\n===== домены (для списка в другие скрипты) =====\n' + domains.join('\n') + '\n');
  console.log('===== подробно (домен / аккаунт / id) =====\n' + tsv + '\n');

  // Буфер обмена — не на критическом пути. Из консоли браузер часто отказывает
  // (вкладка не в фокусе), и если этого дождаться, отмены просто не начнутся.
  // Поэтому не ждём и гасим отказ на месте; список всё равно выведен выше.
  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(domains.join('\n'))
      .then(() => log('домены скопированы в буфер'))
      .catch(() => log('в буфер не легло — скопируй из вывода выше или командой: copy(__ocheredi.domains.join("\\n"))'));
  } else {
    log('буфер недоступен (вкладка не в фокусе) — скопировать можно командой: copy(__ocheredi.domains.join("\\n"))');
  }
  log(`строк: ${items.length}, уникальных доменов: ${domains.length}`);

  if (DRY) {
    log('РЕЖИМ ПРОВЕРКИ: ничего не отменено. Сверь список и поставь DRY = false.');
    return;
  }

  // ---- и только теперь отменяем ----
  let done = 0, failed = 0;
  for (const [i, it] of items.entries()) {
    const nom = `${i + 1}/${items.length} ${it.domain || 'id=' + it.id}`;
    try {
      const res = await fetch(it.action, {
        method: (it.form.getAttribute('method') || 'post').toUpperCase(),
        body: new FormData(it.form),          // в форме лежит CSRF-токен
        credentials: 'same-origin',
      });
      if (res.ok) { done++; log(`${nom} — отменено`); }
      else {
        failed++;
        // первый отказ разбираем подробно: по коду и началу ответа сразу видно,
        // что именно не так — права, токен или форма
        const body = await res.text().catch(() => '');
        log(`${nom} — ошибка HTTP ${res.status}`, failed === 1 ? body.slice(0, 300) : '');
      }
    } catch (e) { failed++; log(`${nom} — сбой: ${e.message}`); }
    await new Promise(r => setTimeout(r, PAUSE));
  }

  // сверяем: сколько ожидающих осталось на самом деле
  let left = '?';
  try {
    const html = await (await fetch(location.pathname + location.search, { credentials: 'same-origin' })).text();
    left = collect(new DOMParser().parseFromString(html, 'text/html')).length;
  } catch (e) { /* не критично */ }

  log(`ГОТОВО. отменено: ${done}, ошибок: ${failed}, осталось ожидающих: ${left}`);
  log("домены — в window.__ocheredi.domains, скопировать: copy(__ocheredi.domains.join(\"\\n\"))");
})();

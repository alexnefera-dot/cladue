/* Инвентарь сайтов: бренд, лейбл и реф-ссылка — spin-engine.top
 *
 * Только читает, ничего не меняет. Проходит по всем сайтам из списка и
 * собирает id, бренд, лейбл (колонка Label) и ссылку, которая на сайте стоит.
 * В конце — сводка по доменам рефок: сколько сайтов на каком домене.
 *
 * Запускать в консоли на https://spin-engine.top/sites
 *
 * Результат: таблица в консоли, TSV в буфере обмена и в window.__inv.
 */
(async () => {

  const PAUSE = 150;   // пауза между сайтами, мс

  const log = (...a) => console.log('%c[инвентарь]', 'color:#0f766e;font-weight:bold', ...a);
  const parse = (html) => new DOMParser().parseFromString(html, 'text/html');

  const idOf = (a) => (a.getAttribute('href') || '').match(/\/sites\/(?:view|edit)\/(\d+)/)?.[1];

  /**
   * Разбор списка сайтов. Колонки ищем по заголовкам, а не по номеру: порядок
   * столбцов в админке меняется, а подписи — нет. Лейбл берём из колонки Label,
   * бренд — из Brand.
   */
  const rowsFrom = (doc) => {
    const out = {};
    for (const table of doc.querySelectorAll('table')) {
      const heads = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim().toLowerCase());
      const iLabel = heads.findIndex(t => /^(label|лейбл|метка)$/.test(t));
      const iBrand = heads.findIndex(t => /^(brand|бренд)$/.test(t));

      for (const tr of table.querySelectorAll('tbody tr')) {
        const link = tr.querySelector('a[href*="/sites/view/"], a[href*="/sites/edit/"]');
        const id   = link ? idOf(link) : null;
        if (!id) continue;
        const cells = [...tr.querySelectorAll('td')].map(td => td.textContent.trim());
        const label = iLabel >= 0 ? (cells[iLabel] || '') : '';
        const brand = iBrand >= 0 ? (cells[iBrand] || '') : '';
        // запасной вариант: подпись вида Имя_1 или домен в любой ячейке
        const guess = cells.find(t => /^[\w.-]+_\d+$/.test(t)) || cells.find(t => /^[\w.-]+\.[a-z]{2,}$/i.test(t)) || '';
        out[id] = { brand, label: label || guess };
      }
    }
    return out;
  };

  // --- список сайтов: из отданного сервером HTML и из того, что уже на странице
  let info = {};
  for (const src of ['/sites', location.pathname + location.search]) {
    try {
      const doc = parse(await (await fetch(src, { credentials: 'same-origin' })).text());
      Object.assign(info, rowsFrom(doc));
    } catch (e) { /* страницы может не быть */ }
  }
  Object.assign(info, rowsFrom(parse(document.documentElement.outerHTML)));

  const ids = Object.keys(info);
  log('сайтов:', ids.length);
  if (!ids.length) return console.error('ничего не нашлось — открой список сайтов и запусти снова');

  const hostOf = (u) => String(u).trim().replace(/^https?:\/\//i, '').split(/[\/?#]/)[0].replace(/^www\./i, '').toLowerCase();

  const rows = [];
  let failed = 0;

  for (const [i, id] of ids.entries()) {
    try {
      const doc = parse(await (await fetch(`/sites/edit/${id}`, { credentials: 'same-origin' })).text());
      const fld = doc.querySelector('[name="ref_link"]');
      const ref = fld ? (fld.value ?? fld.textContent ?? '').trim() : '';

      let { brand, label } = info[id];
      // если в списке лейбла не было — пробуем поля формы
      if (!label) {
        for (const n of ['label', 'name', 'title', 'url', 'site', 'domain']) {
          const f = doc.querySelector(`[name="${n}"]`);
          const v = f ? (f.value ?? f.textContent ?? '').trim() : '';
          if (v) { label = v; break; }
        }
      }

      rows.push({ id, brand, label, ref, host: ref ? hostOf(ref) : '' });
      if ((i + 1) % 25 === 0) log(`пройдено ${i + 1} из ${ids.length}`);
    } catch (e) {
      failed++;
      rows.push({ id, brand: info[id].brand, label: info[id].label, ref: '', host: 'ОШИБКА' });
    }
    await new Promise(r => setTimeout(r, PAUSE));
  }

  // --- сводка по доменам рефок
  const byHost = new Map();
  for (const r of rows) {
    const k = r.host || '(пусто)';
    byHost.set(k, (byHost.get(k) || 0) + 1);
  }

  const tsv = rows.map(r => [r.id, r.brand, r.label, r.ref].join('\t')).join('\n');
  window.__inv = { rows, tsv };

  console.log('\n===== id / бренд / лейбл / рефка =====\n' + tsv + '\n');
  console.log('===== по доменам рефок =====');
  for (const [host, n] of [...byHost.entries()].sort((a, b) => b[1] - a[1])) console.log(`${host} — ${n}`);

  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv)
      .then(() => log('скопировано в буфер'))
      .catch(() => log('в буфер не легло — забери из вывода или: copy(__inv.tsv)'));
  } else {
    log('буфер недоступен (вкладка не в фокусе) — скопировать: copy(__inv.tsv)');
  }

  const noLabel = rows.filter(r => !r.label).length;
  const noRef   = rows.filter(r => !r.ref).length;
  log(`ГОТОВО. сайтов: ${rows.length}, без лейбла: ${noLabel}, без рефки: ${noRef}, ошибок: ${failed}`);
})();

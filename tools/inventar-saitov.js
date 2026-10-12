/* Инвентарь сайтов: адрес + реф-ссылка — spin-engine.top
 *
 * Только читает, ничего не меняет. Проходит по всем сайтам и собирает
 * id, адрес сайта и ссылку, которая на нём стоит. В конце — сводка по доменам
 * рефок: сколько сайтов на каком домене.
 *
 * Запускать в консоли на https://spin-engine.top/sites
 * (или на /domains — тогда возьмёт то, что есть на странице).
 *
 * Результат: таблица в консоли, TSV в буфере обмена и в window.__inv.
 */
(async () => {

  const PAUSE = 150;   // пауза между сайтами, мс

  const log = (...a) => console.log('%c[инвентарь]', 'color:#0f766e;font-weight:bold', ...a);

  const parse = (html) => new DOMParser().parseFromString(html, 'text/html');

  const idsFrom = (doc) => [...new Set([...doc.querySelectorAll('a[href*="/sites/view/"], a[href*="/sites/edit/"]')]
    .map(a => (a.getAttribute('href') || '').match(/\/sites\/(?:view|edit)\/(\d+)/)?.[1])
    .filter(Boolean))];

  // Адрес сайта в списке обычно стоит отдельной колонкой рядом со ссылкой на
  // правку. Забираем его заранее: в форме редактирования поле может называться
  // как угодно, а тут это просто текст строки.
  const namesFrom = (doc) => {
    const map = {};
    for (const a of doc.querySelectorAll('a[href*="/sites/view/"], a[href*="/sites/edit/"]')) {
      const id = (a.getAttribute('href') || '').match(/\/sites\/(?:view|edit)\/(\d+)/)?.[1];
      if (!id) continue;
      const row = a.closest('tr');
      if (!row) continue;
      const cells = [...row.querySelectorAll('td')].map(td => td.textContent.trim());
      // ячейка, похожая на домен: есть точка и нет пробелов
      const host = cells.find(t => /^[\w.-]+\.[a-z]{2,}$/i.test(t));
      if (host && !map[id]) map[id] = host;
    }
    return map;
  };

  // --- собираем id и адреса из списка
  let ids = [], names = {};
  for (const src of ['/sites', location.pathname + location.search]) {
    try {
      const doc = parse(await (await fetch(src, { credentials: 'same-origin' })).text());
      const found = idsFrom(doc);
      if (found.length > ids.length) { ids = found; log(`из ${src}: ${found.length}`); }
      Object.assign(names, namesFrom(doc));
    } catch (e) { /* страницы может не быть */ }
  }
  const live = parse(document.documentElement.outerHTML);
  ids = [...new Set([...ids, ...idsFrom(live)])];
  Object.assign(names, namesFrom(live));

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

      // адрес сайта: из списка, а если там не нашёлся — из полей формы
      let site = names[id] || '';
      if (!site) {
        for (const n of ['url', 'site', 'domain', 'subdomain', 'host', 'name', 'title']) {
          const f = doc.querySelector(`[name="${n}"]`);
          const v = f ? (f.value ?? f.textContent ?? '').trim() : '';
          if (v && /\./.test(v)) { site = v.replace(/^https?:\/\//i, '').split('/')[0]; break; }
        }
      }

      rows.push({ id, site, ref, host: ref ? hostOf(ref) : '' });
      if ((i + 1) % 25 === 0) log(`обработано ${i + 1}/${ids.length}`);
    } catch (e) {
      failed++;
      rows.push({ id, site: names[id] || '', ref: '', host: 'ОШИБКА' });
    }
    await new Promise(r => setTimeout(r, PAUSE));
  }

  // --- сводка по доменам рефок
  const byHost = new Map();
  for (const r of rows) {
    const k = r.host || '(пусто)';
    byHost.set(k, (byHost.get(k) || 0) + 1);
  }

  const tsv = rows.map(r => [r.id, r.site, r.ref].join('\t')).join('\n');
  window.__inv = { rows, tsv };

  console.log('\n===== id / сайт / рефка =====\n' + tsv + '\n');
  console.log('===== по доменам рефок =====');
  for (const [host, n] of [...byHost.entries()].sort((a, b) => b[1] - a[1])) console.log(`${host} — ${n}`);

  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv)
      .then(() => log('скопировано в буфер'))
      .catch(() => log('в буфер не легло — забери из вывода или: copy(__inv.tsv)'));
  } else {
    log('буфер недоступен (вкладка не в фокусе) — скопировать: copy(__inv.tsv)');
  }

  const noSite = rows.filter(r => !r.site).length;
  const noRef  = rows.filter(r => !r.ref).length;
  log(`ГОТОВО. сайтов: ${rows.length}, без адреса: ${noSite}, без рефки: ${noRef}, ошибок: ${failed}`);
})();

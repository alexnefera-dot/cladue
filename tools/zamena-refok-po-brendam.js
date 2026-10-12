/* Перевод сайтов на наш домен с подбором кампании по бренду — spin-engine.top
 *
 * Берёт все сайты, у которых рефка ведёт НЕ на наш домен, и ставит им
 * https://НАШ_ДОМЕН/go/СЛАГ, где слаг подбирается по бренду сайта.
 *
 * Откуда берётся слаг, по порядку:
 *   1. CAMPAIGNS — выгрузка кампаний из панели (Настройки → «Выгрузить все
 *      рефки (CSV)»). Совпадение по НАЗВАНИЮ кампании с названием бренда.
 *      Это главный источник: там ровно то, что есть в базе трекера.
 *   2. MAP — ручные соответствия ниже. Нужны там, где название кампании в
 *      панели не совпадает с брендом (Lucky Bird → spin_engine_crossbrand).
 *   3. FALLBACK — для брендов, под которые кампании нет вовсе.
 *
 * Запускать в консоли на https://spin-engine.top/sites
 * Сначала DRY = true: покажет, кому что достанется, и отдельно — бренды,
 * ушедшие на FALLBACK. Их стоит глазами проверить ДО боевого прогона.
 */
(async () => {

  const HOST     = 'sitegoratorr2.top';          // наш текущий домен
  const FALLBACK = 'dorgen_engine';              // когда кампании под бренд нет
  const DRY      = true;   // <-- false, когда проверишь вывод
  const PAUSE    = 200;

  // Выгрузка кампаний из панели: Настройки → «Выгрузить все рефки (CSV)».
  // Вставить целиком вместе с шапкой. Пусто — работаем только по MAP.
  const CAMPAIGNS = `
slug,name,ref_link
`;

  // Ручные соответствия «бренд → слаг». Берут верх над совпадением по названию.
  const MAP = {
    '1Go':                '1go_engine',
    '7K':                 '7k_engine',
    'AdmiralX':           'admiralx_engine',
    'Arkada':             'arkada_engine',
    'Aurora Casino':      'aurora_engine',
    'Booi':               'booi_engine',
    'Champion Slots':     'championslots_engine',
    'ClubNika':           'clubnika_engine',
    'CryptoBoss':         'cryptoboss_engine',
    'CryptobossTemplate': 'cryptoboss_engine',
    'Drip':               'drip_engine',
    'GetX':               'getx_engine',
    'Gizbo':              'gizbo_engine',
    'Hype':               'hype_engine',
    'Kometa':             'kometa_engine',
    'Kush':               'kush_engine',
    'Lucky Bird':         'spin_engine_crossbrand',
    'Money X':            'money_x_engine',
    'New Retro':          'newretro_engine',
    'Onion':              'onino_engine',
    'Play Fortuna':       'playfortuna_engine',
    'R7':                 'r7_engine',
    'Ramenbet':           'ramenbet_engine1',
    'Starda':             'starda_engine',
    'Unlim Casino':       'unlim_engine',
    'Vodka':              'vodka_engine',
    'Vovan':              'vovan_engine',
    'Zooma':              'zooma_engine',
  };

  const log = (...a) => console.log('%c[бренды]', 'color:#7c2d12;font-weight:bold', ...a);
  const parse = (html) => new DOMParser().parseFromString(html, 'text/html');
  const norm = (s) => String(s).toLowerCase().replace(/[\s_\-.]+/g, '');
  const hostOf = (u) => String(u).trim().replace(/^https?:\/\//i, '').split(/[\/?#]/)[0].replace(/^www\./i, '').toLowerCase();

  // --- кампании из выгрузки: название -> слаг, и набор известных слагов
  const byName = new Map(), slugs = new Set();
  for (const line of CAMPAIGNS.trim().split(/[\r\n]+/)) {
    const s = line.trim();
    if (!s || /^slug\s*[,;\t]/i.test(s)) continue;
    const f = s.split(/[,;\t]/).map(x => x.trim().replace(/^"|"$/g, ''));
    if (!f[0]) continue;
    slugs.add(f[0]);
    if (f[1]) byName.set(norm(f[1]), f[0]);
  }
  log(CAMPAIGNS.trim().split('\n').length > 1 ? `кампаний в выгрузке: ${slugs.size}` : 'выгрузка кампаний пуста — работаем только по MAP');

  // --- список сайтов: id, бренд
  const idOf = (a) => (a.getAttribute('href') || '').match(/\/sites\/(?:view|edit)\/(\d+)/)?.[1];
  const rowsFrom = (doc) => {
    const out = {};
    for (const table of doc.querySelectorAll('table')) {
      const heads  = [...table.querySelectorAll('thead th')].map(th => th.textContent.trim().toLowerCase());
      const iBrand = heads.findIndex(t => /^(brand|бренд)$/.test(t));
      const iLabel = heads.findIndex(t => /^(label|лейбл|метка)$/.test(t));
      for (const tr of table.querySelectorAll('tbody tr')) {
        const link = tr.querySelector('a[href*="/sites/view/"], a[href*="/sites/edit/"]');
        const id = link ? idOf(link) : null;
        if (!id) continue;
        const cells = [...tr.querySelectorAll('td')].map(td => td.textContent.trim());
        out[id] = { brand: iBrand >= 0 ? (cells[iBrand] || '') : '', label: iLabel >= 0 ? (cells[iLabel] || '') : '' };
      }
    }
    return out;
  };

  let info = {};
  for (const src of ['/sites', location.pathname + location.search]) {
    try { Object.assign(info, rowsFrom(parse(await (await fetch(src, { credentials: 'same-origin' })).text()))); }
    catch (e) { /* страницы может не быть */ }
  }
  Object.assign(info, rowsFrom(parse(document.documentElement.outerHTML)));

  const ids = Object.keys(info);
  log('сайтов:', ids.length, DRY ? '· РЕЖИМ ПРОВЕРКИ' : '· БОЕВОЙ РЕЖИМ');
  if (!ids.length) return console.error('ничего не нашлось — открой список сайтов и запусти снова');

  // слаг для бренда: ручная карта → совпадение по названию кампании → запасной
  const slugFor = (brand) => {
    if (MAP[brand]) return { slug: MAP[brand], how: 'карта' };
    const byN = byName.get(norm(brand));
    if (byN) return { slug: byN, how: 'по названию' };
    return { slug: FALLBACK, how: 'ЗАПАСНОЙ' };
  };

  let changed = 0, already = 0, failed = 0, empty = 0;
  const plan = [], fallbackBrands = new Map(), unknownSlugs = new Set();

  for (const [i, id] of ids.entries()) {
    const { brand, label } = info[id];
    const nom = `${i + 1}/${ids.length} id=${id} ${label || brand}`;
    try {
      const url = `/sites/edit/${id}`;
      const doc = parse(await (await fetch(url, { credentials: 'same-origin' })).text());
      const fld = doc.querySelector('[name="ref_link"]');
      if (!fld) { failed++; log(`${nom} — поля ref_link нет`); continue; }

      const was = (fld.value ?? fld.textContent ?? '').trim();
      if (was && hostOf(was) === HOST) { already++; continue; }     // уже наш — не трогаем
      if (!brand) { empty++; log(`${nom} — бренд не определён, пропуск`); continue; }

      const { slug, how } = slugFor(brand);
      if (how === 'ЗАПАСНОЙ') fallbackBrands.set(brand, (fallbackBrands.get(brand) || 0) + 1);
      // Слаг, которого нет в выгрузке, — это 404 на рефке. Лучше запасной.
      if (slugs.size && !slugs.has(slug)) { unknownSlugs.add(slug + ' (бренд ' + brand + ')'); }

      const now = `https://${HOST}/go/${slug}`;
      plan.push([id, brand, label, was, now, how]);

      if (DRY) { changed++; log(`${nom} — ${brand} → ${slug} [${how}]`); }
      else {
        const form = fld.closest('form');
        if (!form) { failed++; log(`${nom} — форма не найдена`); continue; }
        fld.value = now; fld.textContent = now;
        const fd = new FormData(form);
        fd.set('ref_link', now);
        const res = await fetch(form.getAttribute('action') || url, {
          method: (form.getAttribute('method') || 'post').toUpperCase(),
          body: fd, credentials: 'same-origin',
        });
        if (res.ok) { changed++; log(`${nom} — ${slug} [${how}]`); }
        else        { failed++;  log(`${nom} — ошибка HTTP ${res.status}`); }
      }
    } catch (e) { failed++; log(`${nom} — сбой: ${e.message}`); }

    if ((i + 1) % 25 === 0) log(`пройдено ${i + 1} из ${ids.length}`);
    await new Promise(r => setTimeout(r, PAUSE));
  }

  const tsv = plan.map(r => r.join('\t')).join('\n');
  window.__plan = { plan, tsv };
  console.log('\n===== план (id / бренд / лейбл / было / станет / источник слага) =====\n' + tsv + '\n');

  if (fallbackBrands.size) {
    console.log('===== бренды без своей кампании → ' + FALLBACK + ' =====');
    for (const [b, n] of [...fallbackBrands.entries()].sort((a, c) => c[1] - a[1])) console.log(`${b} — ${n} сайтов`);
    console.log('');
  }
  if (unknownSlugs.size) {
    console.log('!! слаги, которых нет в выгрузке кампаний (рефка отдаст 404):');
    for (const s of unknownSlugs) console.log('   ' + s);
    console.log('');
  }

  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv).then(() => log('план скопирован в буфер')).catch(() => log('в буфер не легло — copy(__plan.tsv)'));
  }
  log(`ГОТОВО. ${DRY ? 'будет изменено' : 'изменено'}: ${changed}, уже на ${HOST}: ${already}, ` +
      `без бренда: ${empty}, ошибок: ${failed}, на запасной слаг: ${[...fallbackBrands.values()].reduce((a, b) => a + b, 0)}`);
  if (!DRY && changed) log('СОХРАНИ ПЛАН: прежние ссылки есть только в нём.');
})();

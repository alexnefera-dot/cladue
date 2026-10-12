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
1go_engine,1GO_engine,https://sitegoratorr2.top/go/1go_engine
1xslots_engine,1xSlots_engine,https://sitegoratorr2.top/go/1xslots_engine
7k_engine,7k_engine,https://sitegoratorr2.top/go/7k_engine
7k_engine_test,"7k_engine (test)",https://sitegoratorr2.top/go/7k_engine_test
admiralx_engine,AdmiralX_engine,https://sitegoratorr2.top/go/admiralx_engine
admiralx_engine_9_12,"AdmiralX_engine 9.12",https://sitegoratorr2.top/go/admiralx_engine_9_12
admiralx_engine_new,AdmiralX_engine_new,https://sitegoratorr2.top/go/admiralx_engine_new
admiralx_engine1,AdmiralX_engine1,https://sitegoratorr2.top/go/admiralx_engine1
admiralx_engine12,AdmiralX_engine12,https://sitegoratorr2.top/go/admiralx_engine12
admiralx_engine13,AdmiralX_engine13,https://sitegoratorr2.top/go/admiralx_engine13
admiralx_engine14,AdmiralX_engine14,https://sitegoratorr2.top/go/admiralx_engine14
admiralx_engine2,AdmiralX_engine2,https://sitegoratorr2.top/go/admiralx_engine2
admiralx_engine6,AdmiralX_engine6,https://sitegoratorr2.top/go/admiralx_engine6
admiralx_engine7,AdmiralX_engine7,https://sitegoratorr2.top/go/admiralx_engine7
admiralx_engine8,AdmiralX_engine8,https://sitegoratorr2.top/go/admiralx_engine8
admiralx_engine9,AdmiralX_engine9,https://sitegoratorr2.top/go/admiralx_engine9
apex_engine,Apex_engine,https://sitegoratorr2.top/go/apex_engine
arkada_engine,Arkada_engine,https://sitegoratorr2.top/go/arkada_engine
aurora_engine,Aurora_engine,https://sitegoratorr2.top/go/aurora_engine
aurora_engine2,Aurora_engine2,https://sitegoratorr2.top/go/aurora_engine2
aurora_engine3,Aurora_engine3,https://sitegoratorr2.top/go/aurora_engine3
aurora_engine5,Aurora_engine5,https://sitegoratorr2.top/go/aurora_engine5
azino_engine,Azino_engine,https://sitegoratorr2.top/go/azino_engine
banda_engine,Banda_engine,https://sitegoratorr2.top/go/banda_engine
bollywod_engine,Bollywod_engine,https://sitegoratorr2.top/go/bollywod_engine
booi_engine,Booi_engine,https://sitegoratorr2.top/go/booi_engine
cat_engine,Cat_engine,https://sitegoratorr2.top/go/cat_engine
championslots_engine,ChampionSlots_engine,https://sitegoratorr2.top/go/championslots_engine
clubnika_engine,Clubnika_engine,https://sitegoratorr2.top/go/clubnika_engine
cryptoboss_engine,Cryptoboss_engine,https://sitegoratorr2.top/go/cryptoboss_engine
cryptoboss_engine_buzz,Cryptoboss_engine_buzz,https://sitegoratorr2.top/go/cryptoboss_engine_buzz
cryptoboss_engine1,Cryptoboss_engine1,https://sitegoratorr2.top/go/cryptoboss_engine1
cryptoboss_engine10,Cryptoboss_engine10,https://sitegoratorr2.top/go/cryptoboss_engine10
cryptoboss_engine11,Cryptoboss_engine11,https://sitegoratorr2.top/go/cryptoboss_engine11
cryptoboss_engine12,Cryptoboss_engine12,https://sitegoratorr2.top/go/cryptoboss_engine12
cryptoboss_engine13,Cryptoboss_engine13,https://sitegoratorr2.top/go/cryptoboss_engine13
cryptoboss_engine14,Cryptoboss_engine14,https://sitegoratorr2.top/go/cryptoboss_engine14
cryptoboss_engine15,Cryptoboss_engine15,https://sitegoratorr2.top/go/cryptoboss_engine15
cryptoboss_engine2,Cryptoboss_engine2,https://sitegoratorr2.top/go/cryptoboss_engine2
cryptoboss_engine3,Cryptoboss_engine3,https://sitegoratorr2.top/go/cryptoboss_engine3
cryptoboss_engine5,Cryptoboss_engine5,https://sitegoratorr2.top/go/cryptoboss_engine5
cryptoboss_engine6,Cryptoboss_engine6,https://sitegoratorr2.top/go/cryptoboss_engine6
cryptoboss_engine7,Cryptoboss_engine7,https://sitegoratorr2.top/go/cryptoboss_engine7
cryptoboss_engine8,Cryptoboss_engine8,https://sitegoratorr2.top/go/cryptoboss_engine8
cryptoboss_engine9,Cryptoboss_engine9,https://sitegoratorr2.top/go/cryptoboss_engine9
dorgen_engine,Dorgen_engine,https://sitegoratorr2.top/go/dorgen_engine
dorgne_fenix,"Dorgne Fenix",https://sitegoratorr2.top/go/dorgne_fenix
dragonmoney_engine,DragonMoney_engine,https://sitegoratorr2.top/go/dragonmoney_engine
drip_engine,Drip_engine,https://sitegoratorr2.top/go/drip_engine
eldorado_engine,Eldorado_engine,https://sitegoratorr2.top/go/eldorado_engine
eva_engine,Eva_engine,https://sitegoratorr2.top/go/eva_engine
faro_engine,Faro_engine,https://sitegoratorr2.top/go/faro_engine
fenix_engine,Fenix_engine,https://sitegoratorr2.top/go/fenix_engine
getx_engine,Getx_engine,https://sitegoratorr2.top/go/getx_engine
gizbo_engine,Gizbo_engine,https://sitegoratorr2.top/go/gizbo_engine
gold_engine,Gold_engine,https://sitegoratorr2.top/go/gold_engine
hype_engine,Hype_engine,https://sitegoratorr2.top/go/hype_engine
irwin_engine,Irwin_engine,https://sitegoratorr2.top/go/irwin_engine
jetton_engine,Jetton_engine,https://sitegoratorr2.top/go/jetton_engine
joycasino_engine,Joycasino_engine,https://sitegoratorr2.top/go/joycasino_engine
jozz_engine,Jozz_engine,https://sitegoratorr2.top/go/jozz_engine
kometa_engine,Kometa_engine,https://sitegoratorr2.top/go/kometa_engine
kush_engine,Kush_engine,https://sitegoratorr2.top/go/kush_engine
leebet,Leebet_engine,https://sitegoratorr2.top/go/leebet
lev_engine,Lev_engine,https://sitegoratorr2.top/go/lev_engine
lex_engine,Lex_engine,https://sitegoratorr2.top/go/lex_engine
mellstroy_engine,Mellstroy_engine,https://sitegoratorr2.top/go/mellstroy_engine
money_x_engine,"Money X_engine",https://sitegoratorr2.top/go/money_x_engine
mostbet_engine,Mostbet_engine,https://sitegoratorr2.top/go/mostbet_engine
motor_engine,Motor_engine,https://sitegoratorr2.top/go/motor_engine
newretro_engine,NewRetro_engine,https://sitegoratorr2.top/go/newretro_engine
nomad_engine,Nomad_engine,https://sitegoratorr2.top/go/nomad_engine
onino_engine,Onino_engine,https://sitegoratorr2.top/go/onino_engine
pinco_engine,Pinco_engine,https://sitegoratorr2.top/go/pinco_engine
pinup_engine,Pinup_engine,https://sitegoratorr2.top/go/pinup_engine
playfortuna_engine,PlayFortuna_engine,https://sitegoratorr2.top/go/playfortuna_engine
r7_engine,R7_engine,https://sitegoratorr2.top/go/r7_engine
ramenbet_engine_buzz,Ramenbet_engine_buzz,https://sitegoratorr2.top/go/ramenbet_engine_buzz
ramenbet_engine1,Ramenbet_engine1,https://sitegoratorr2.top/go/ramenbet_engine1
ramenbet_engine10,Ramenbet_engine10,https://sitegoratorr2.top/go/ramenbet_engine10
ramenbet_engine11,Ramenbet_engine11,https://sitegoratorr2.top/go/ramenbet_engine11
ramenbet_engine2,Ramenbet_engine2,https://sitegoratorr2.top/go/ramenbet_engine2
ramenbet_engine3,Ramenbet_engine3,https://sitegoratorr2.top/go/ramenbet_engine3
ramenbet_engine3_2,Ramenbet_engine3,https://sitegoratorr2.top/go/ramenbet_engine3_2
ramenbet_engine4,Ramenbet_engine4,https://sitegoratorr2.top/go/ramenbet_engine4
ramenbet_engine5,Ramenbet_engine5,https://sitegoratorr2.top/go/ramenbet_engine5
ramenbet_engine6,Ramenbet_engine6,https://sitegoratorr2.top/go/ramenbet_engine6
ramenbet_engine7,Ramenbet_engine7,https://sitegoratorr2.top/go/ramenbet_engine7
ramenbet_engine8,Ramenbet_engine8,https://sitegoratorr2.top/go/ramenbet_engine8
ramenbet_engine9,Ramenbet_engine9,https://sitegoratorr2.top/go/ramenbet_engine9
riobet_engine,Riobet_engine,https://sitegoratorr2.top/go/riobet_engine
slotzal_engine,Slotzal_engine,https://sitegoratorr2.top/go/slotzal_engine
spin_engine_crossbrand,Spin_engine_crossbrand,https://sitegoratorr2.top/go/spin_engine_crossbrand
stake_engine,Stake_engine,https://sitegoratorr2.top/go/stake_engine
starda_engine,Starda_engine,https://sitegoratorr2.top/go/starda_engine
sykaa_engine,Sykaa_engine,https://sitegoratorr2.top/go/sykaa_engine
unlim_engine,Unlim_engine,https://sitegoratorr2.top/go/unlim_engine
unlim_engine2,Unlim_engine2,https://sitegoratorr2.top/go/unlim_engine2
unlim_engine4,Unlim_engine4,https://sitegoratorr2.top/go/unlim_engine4
unlim_engine5,Unlim_engine5,https://sitegoratorr2.top/go/unlim_engine5
upx_engine,UPX_engine,https://sitegoratorr2.top/go/upx_engine
vavada_engine,Vavada_engine,https://sitegoratorr2.top/go/vavada_engine
velora_engine,Velora_engine,https://sitegoratorr2.top/go/velora_engine
vodka_engine,Vodka_engine,https://sitegoratorr2.top/go/vodka_engine
vovan_engine,Vovan_engine,https://sitegoratorr2.top/go/vovan_engine
vovan_engine1,Vovan_engine1,https://sitegoratorr2.top/go/vovan_engine1
vovan_engine2,Vovan_engine2,https://sitegoratorr2.top/go/vovan_engine2
vovan_engine3,Vovan_engine3,https://sitegoratorr2.top/go/vovan_engine3
vovan_engine4,Vovan_engine4,https://sitegoratorr2.top/go/vovan_engine4
vulcan_engine,Vulcan_engine,https://sitegoratorr2.top/go/vulcan_engine
zooma_engine,Zooma_engine,https://sitegoratorr2.top/go/zooma_engine
zooma_engine2,Zooma_engine2,https://sitegoratorr2.top/go/zooma_engine2
`;

  // Ручные соответствия «бренд → слаг». Берут верх над совпадением по названию.
  const MAP = {
    '1Go':                '1go_engine',
    '1xSlots':            '1xslots_engine',
    '7K':                 '7k_engine',
    'AdmiralX':           'admiralx_engine',
    'Arkada':             'arkada_engine',
    'Aurora Casino':      'aurora_engine',
    'Azino777':           'azino_engine',          // кампания называется Azino_engine
    'Booi':               'booi_engine',
    'Cat':                'cat_engine',
    'Champion Slots':     'championslots_engine',
    'ClubNika':           'clubnika_engine',
    'CryptoBoss':         'cryptoboss_engine',
    'CryptobossTemplate': 'cryptoboss_engine',
    'Dragon Money':       'dragonmoney_engine',
    'Drip':               'drip_engine',
    'Eldorado':           'eldorado_engine',
    'Eva':                'eva_engine',
    'GetX':               'getx_engine',
    'Gizbo':              'gizbo_engine',
    'Hype':               'hype_engine',
    'Irwin':              'irwin_engine',
    'Jetton':             'jetton_engine',
    'Kometa':             'kometa_engine',
    'Kush':               'kush_engine',
    'Lev':                'lev_engine',
    'Lex':                'lex_engine',
    'Lucky Bird':         'spin_engine_crossbrand', // своей кампании нет, льём на кроссбренд
    'Mellstroy':          'mellstroy_engine',
    'Money X':            'money_x_engine',
    'MostBet Bookmaker':  'mostbet_engine',
    'Motor':              'motor_engine',
    'New Retro':          'newretro_engine',
    'Onion':              'onino_engine',          // в панели кампания названа Onino
    'Pinco':              'pinco_engine',
    'Play Fortuna':       'playfortuna_engine',
    'R7':                 'r7_engine',
    'Ramenbet':           'ramenbet_engine1',      // простого ramenbet_engine в базе нет
    'Riobet':             'riobet_engine',
    'Slotozal':           'slotzal_engine',        // кампания названа Slotzal
    'Stake':              'stake_engine',
    'Starda':             'starda_engine',
    'Sykaaa':             'sykaa_engine',          // кампания названа Sykaa
    'UP-X':               'upx_engine',
    'Unlim Casino':       'unlim_engine',
    'Vavada':             'vavada_engine',
    'Vodka':              'vodka_engine',
    'Vovan':              'vovan_engine',
    'Vulkan Platinum':    'vulcan_engine',         // кампания названа Vulcan
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

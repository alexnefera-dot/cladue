/* Замена рефок брендов на ПРЯМЫЕ ссылки офферов — dorgen-engine.com/brands
 *
 * Сейчас в брендах стоит наша рефка вида https://домен/go/СЛАГ. Скрипт берёт
 * из неё слаг, находит по нему прямой адрес оффера и ставит его вместо рефки.
 *
 * Адреса офферов НЕ придумываются и не берутся из памяти: их надо выгрузить
 * из панели трекера — Настройки → «Выгрузить офферы (CSV)» — и вставить
 * содержимое файла в OFFERS ниже. Так в брендах окажется ровно то, что сейчас
 * в базе, а не то, что было когда-то.
 *
 * Запускать в консоли на https://dorgen-engine.com/brands
 * (для двух других панелей — на их /brands, скрипт тот же).
 *
 * СНАЧАЛА DRY = true — ничего не сохраняет, показывает «было → станет».
 *
 * ВАЖНО, ЧТО ТЕРЯЕТСЯ. После замены переходы идут мимо трекера: кликов в
 * панели по таким сайтам не будет совсем. Конверсии продолжат приходить
 * постбеком, но без привязки к сайту. У кампаний с несколькими офферами
 * ротация исчезнет — прямая ссылка может быть только одна; в выгрузке видно,
 * у каких кампаний офферов больше одного.
 */
(async () => {

  // Сюда — содержимое CSV из панели (можно целиком, вместе с шапкой).
  const OFFERS = `
slug,name,offer_url,offers_count,all_offers
`;

  const DRY   = true;    // <-- false, когда проверишь вывод
  const PAUSE = 250;     // мс между брендами, чтобы не долбить сервер

  // Метка для привязки конверсий. Пусто — ссылка ставится как есть.
  // '{slug}' подставляет слаг кампании, '{brand}' — имя бренда.
  // Включать только после проверки, как движок склеивает параметры: он
  // дописывает к рефке свой ?s=..., и если делает это вслепую, ссылка с
  // параметром сломается. Проверяется одним сайтом, см. переписку.
  const MARK = '';       // например: 'clickid=b_{slug}'

  const log = (...a) => console.log('%c[прямые рефки]', 'color:#047857;font-weight:bold', ...a);

  // --- разбор выгрузки: в строке нас интересуют слаг и первый http-адрес
  const map = new Map();
  for (const line of OFFERS.trim().split(/[\r\n]+/)) {
    const s = line.trim();
    if (!s || /^slug\s*[,;\t]/i.test(s)) continue;         // шапка CSV
    const slug = (s.split(/[,;\t]/)[0] || '').trim().replace(/^"|"$/g, '');
    const url  = (s.match(/https?:\/\/[^\s",;]+/) || [])[0];
    if (slug && url) map.set(slug.toLowerCase(), url);
  }
  if (!map.size) return console.error('OFFERS пуст — вставь CSV из панели (Настройки → Выгрузить офферы)');
  log('офферов в выгрузке:', map.size);

  // --- список брендов: из исходного HTML, а не из DOM (DataTables показывает одну страницу)
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

  log('брендов:', ids.length, DRY ? '· РЕЖИМ ПРОВЕРКИ' : '· БОЕВОЙ РЕЖИМ');
  if (!ids.length) return console.error('список пуст — открой /brands и запусти снова');

  let changed = 0, skipped = 0, noOffer = 0, failed = 0;
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

      // слаг кампании берём из нашей же рефки
      const slug = (was.match(/\/go\/([\w.\-]+)/) || [])[1];
      if (!slug) { skipped++; log(`${nom} — не наша рефка, пропуск: ${was || '(пусто)'}`); continue; }

      let now = map.get(slug.toLowerCase());
      if (!now) { noOffer++; log(`${nom} — слага «${slug}» нет в выгрузке, пропуск`); continue; }

      if (MARK) {
        const brand = (doc.querySelector('[name="name"]')?.value || '').trim();
        const mark  = MARK.replace('{slug}', slug)
                          .replace('{brand}', brand.toLowerCase().replace(/[^\w]+/g, '_'));
        now += (now.includes('?') ? '&' : '?') + mark;
      }

      if (was === now) { skipped++; log(`${nom} — уже стоит нужная ссылка`); continue; }

      const form = fld.closest('form');
      if (!form) { failed++; log(`${nom} — форма не найдена`); continue; }

      report.push([id, slug, was, now]);

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

  // Отчёт — единственный путь назад: после замены слаг из рефки пропадает,
  // и повторный запуск уже не поймёт, какая кампания где была.
  window.__refki = report;
  const tsv = report.map(r => r.join('\t')).join('\n');
  console.log('\n===== отчёт (id / слаг / было / станет) =====\n' + tsv + '\n');
  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv)
      .then(() => log('отчёт скопирован в буфер'))
      .catch(() => log('отчёт не скопировался — забери из вывода или: copy(__refki.map(r=>r.join("\\t")).join("\\n"))'));
  }
  log(`ГОТОВО. ${DRY ? 'будет изменено' : 'изменено'}: ${changed}, пропущено: ${skipped}, без оффера: ${noOffer}, ошибок: ${failed}`);
  if (!DRY && changed) log('СОХРАНИ ОТЧЁТ: вернуть рефки обратно можно только по нему.');
})();

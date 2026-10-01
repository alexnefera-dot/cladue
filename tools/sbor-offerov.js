/* Сбор «слаг → прямая ссылка оффера» из панели трекера
 *
 * Запускать в консоли НА СТРАНИЦЕ КАМПАНИЙ панели (stats.php, вкладка
 * «Кампании»). Ничего не меняет — только читает то, что уже на экране.
 *
 * Результат — строки вида  слаг⇥ссылка  — выводится в консоль, кладётся в
 * буфер обмена и остаётся в window.__offers. Их вставляют в OFFERS скрипта
 * smena-refok-pryamye.js, который проставит эти ссылки в бренды дор-движка.
 *
 * Сервер трогать не нужно: данные берутся со страницы, а страница их берёт
 * из базы — то есть это и есть актуальные офферы, а не копия из памяти.
 */
(async () => {

  const log = (...a) => console.log('%c[офферы]', 'color:#7c3aed;font-weight:bold', ...a);

  // В каждой строке кампании: слаг в <code>, офферы в <textarea name="offer_url">.
  // Несколько строк в поле = ротация, вес после «|».
  const areas = [...document.querySelectorAll('textarea[name="offer_url"]')];
  if (!areas.length) {
    return console.error('на странице нет кампаний — открой панель, вкладка «Кампании», и запусти снова');
  }

  const rows = [], many = [], empty = [];

  for (const ta of areas) {
    const tr   = ta.closest('tr');
    const slug = (tr?.querySelector('code')?.textContent || '').trim();
    if (!slug) continue;

    // «url|вес» в каждой строке; берём самый весомый, при равных — первый
    const list = (ta.value || '').split(/[\r\n]+/)
      .map(s => s.trim())
      .filter(s => s && s[0] !== '#')
      .map(s => {
        const m = s.match(/^(.*?)\s*\|\s*(\d+)\s*$/);
        return m ? [m[1].trim(), Math.max(1, +m[2])] : [s, 1];
      })
      .filter(o => /^https?:\/\//i.test(o[0]));

    if (!list.length) { empty.push(slug); continue; }

    let top = list[0];
    for (const o of list) if (o[1] > top[1]) top = o;

    rows.push([slug, top[0]]);
    if (list.length > 1) many.push(`${slug} (${list.length})`);
  }

  const tsv = rows.map(r => r.join('\t')).join('\n');
  window.__offers = rows;
  console.log('\n===== для вставки в OFFERS =====\n' + tsv + '\n');

  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv)
      .then(() => log('скопировано в буфер'))
      .catch(() => log('в буфер не легло — забери из вывода или: copy(__offers.map(r=>r.join("\\t")).join("\\n"))'));
  } else {
    log('буфер недоступен (вкладка не в фокусе) — скопировать: copy(__offers.map(r=>r.join("\\t")).join("\\n"))');
  }

  log(`кампаний: ${rows.length}`);
  // Прямая ссылка может быть только одна, поэтому у таких кампаний ротация
  // после замены исчезнет. Это надо видеть ДО замены, а не узнать потом.
  if (many.length)  log(`!! с ротацией (останется только самый весомый оффер): ${many.join(', ')}`);
  if (empty.length) log(`!! без ссылки, пропущены: ${empty.join(', ')}`);
})();

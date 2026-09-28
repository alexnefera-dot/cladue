/* Сбор названий контента по списку доменов — dorgen-engine.com/domains
 *
 * Переключает домен в фильтре сверху, ждёт подгрузки таблицы и забирает
 * название ПЕРВОГО сайта (колонка Site ID). Вручную вводить и стирать
 * крестиком ничего не надо.
 *
 * Запускать в консоли на https://dorgen-engine.com/domains
 * Список доменов — в DOMAINS ниже, по одному в строке.
 */
(async () => {

  const DOMAINS = `
2573.team
x7x3.team
8788.team
`;

  const PAUSE   = 400;    // пауза между доменами, мс
  const TIMEOUT = 15000;  // сколько ждать подгрузку таблицы

  const log  = (...a) => console.log('%c[сбор]', 'color:#4338ca;font-weight:bold', ...a);
  const list = DOMAINS.trim().split(/[\s,;]+/).map(s => s.trim().toLowerCase()).filter(Boolean);

  // --- находим выпадающий список. Select2 рисует свою обёртку,
  // но под ней остаётся обычный <select>, ему и выставляем значение.
  const sel = document.querySelector('select#content-domain-filter')
           || [...document.querySelectorAll('select')].find(s => /content.?domain/i.test(s.id + ' ' + s.name))
           || document.querySelector('select');
  if (!sel) return console.error('не нашёл выпадающий список доменов — открой /domains');

  const options = [...sel.options].map(o => ({ value: o.value, text: (o.textContent || '').trim() }));
  log('доменов в списке:', options.length - 1, '· запрошено:', list.length);

  const $ = window.jQuery || window.$;
  const firstCell = () => document.querySelector('a[href*="/sites/view/"]');

  const results = [];
  let notFound = 0, empty = 0;

  for (const [i, dom] of list.entries()) {
    const nom = `${i + 1}/${list.length} ${dom}`;

    // ищем опцию, начинающуюся с этого домена: в тексте ещё идёт « — дата»
    const opt = options.find(o => o.text.toLowerCase().split(/[\s—-]/)[0] === dom)
             || options.find(o => o.text.toLowerCase().startsWith(dom));
    if (!opt) { notFound++; results.push([dom, '', 'НЕТ В СПИСКЕ']); log(`${nom} — нет в списке`); continue; }

    const before = firstCell()?.textContent?.trim() ?? null;

    // Select2 слушает jQuery-событие change, поэтому дёргаем через jQuery,
    // а без него — нативным событием.
    if ($) $(sel).val(opt.value).trigger('change');
    else { sel.value = opt.value; sel.dispatchEvent(new Event('change', { bubbles: true })); }

    // ждём, пока таблица перерисуется
    const t0 = Date.now();
    let cell = null;
    while (Date.now() - t0 < TIMEOUT) {
      await new Promise(r => setTimeout(r, 120));
      cell = firstCell();
      const now = cell?.textContent?.trim() ?? null;
      if (now !== before) break;
    }

    const label = firstCell()?.textContent?.trim() || '';
    const row   = firstCell()?.closest('tr');
    const url   = row ? ([...row.querySelectorAll('td')].map(td => td.textContent.trim())
                    .find(t => /\./.test(t) && !t.startsWith('content-')) || '') : '';

    if (!label) { empty++; results.push([dom, '', 'ПУСТО']); log(`${nom} — сайтов нет`); continue; }
    results.push([dom, label, url]);
    log(`${nom} — ${label}`);
    await new Promise(r => setTimeout(r, PAUSE));
  }

  const tsv = results.map(r => r.join('\t')).join('\n');
  console.log('\n===== для вставки в таблицу (домен / контент / url) =====\n' + tsv + '\n');
  try { await navigator.clipboard.writeText(tsv); log('скопировано в буфер'); }
  catch (e) { log('в буфер не скопировалось — выдели вывод выше вручную'); }
  log(`ГОТОВО. собрано: ${results.length - notFound - empty}, нет в списке: ${notFound}, без сайтов: ${empty}`);
  window.__sbor = results;
})();

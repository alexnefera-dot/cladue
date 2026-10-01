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
0796.team 1154.team 1441.team 1754.team 4250.team 5957.team 6650.team
7606.team 7754.team 8726.team 9287.team 9944.team azjo.team f5v7.team
kzbc.team l9l9.team qovi.team sbjy.team tnes.team udqe.team ugpr.team
k7l4.team 0029.team 0077.team 0231.team 0378.team 0988.team 1529.team
1895.team 2247.team 2278.team 2829.team 2867.team 3355.team 3968.team
4342.team 4478.team 4658.team 4791.team 5401.team 5606.team 5776.team
5980.team 6249.team 6327.team 6342.team 7041.team 7496.team 9368.team
9674.team 9806.team h4u5.team hils.team ijlp.team jfsf.team kjzq.team
l2z9.team qjbs.team rghe.team utwe.team xtve.team yheh.team v3v6.team
w2b7.team wgwi.team wjfb.team yrlw.team zlhz.team 0550.team
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
  // Буфер — не на критическом пути: из консоли браузер часто отказывает
  // (вкладка не в фокусе), а с паузой на исключениях в DevTools ожидание
  // такого отказа останавливает выполнение. Список всё равно выведен выше.
  if (navigator.clipboard && document.hasFocus()) {
    navigator.clipboard.writeText(tsv)
      .then(() => log('скопировано в буфер'))
      .catch(() => log('в буфер не легло — забери из вывода или: copy(__sbor.map(r=>r.join("\\t")).join("\\n"))'));
  } else {
    log('буфер недоступен (вкладка не в фокусе) — скопировать: copy(__sbor.map(r=>r.join("\\t")).join("\\n"))');
  }
  log(`ГОТОВО. собрано: ${results.length - notFound - empty}, нет в списке: ${notFound}, без сайтов: ${empty}`);
  window.__sbor = results;
})();

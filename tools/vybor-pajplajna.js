/* Массовый выбор контент-доменов и аккаунтов — Яндекс.Вебмастер, «Запустить пайплайн»
 *
 * Отмечает в поле «Контент-домен» нужные домены, а в поле «Аккаунт» — столько
 * аккаунтов, сколько получилось доменов: один аккаунт на один домен.
 *
 * Кнопку «Запустить пайплайн» скрипт НЕ нажимает: он только заполняет поля,
 * дальше смотришь счётчик «Выбрано аккаунтов … доменов …» и пары под ним,
 * и запускаешь сам.
 *
 * Запускать в консоли на странице пайплайна.
 *
 * Про порядок: аккаунты взаимозаменяемы, поэтому переставлять опции, как на
 * массовом создании сайтов, здесь не нужно — важно только, чтобы аккаунтов было
 * столько же, сколько доменов.
 */
(async () => {

  // Список доменов, которые надо отметить. Пусто — отметить все доступные.
  const LIST = `
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

  const DOMAINS  = 0;   // сколько доменов отметить, если LIST пуст; 0 — все доступные
  const ACCOUNTS = 0;   // сколько аккаунтов отметить; 0 — столько же, сколько доменов
  const ADD      = false;  // true — добавить к тому, что уже выбрано, не сбрасывая

  const log = (...a) => console.log('%c[пайплайн]', 'color:#1d4ed8;font-weight:bold', ...a);

  // Под каждым Select2 лежит обычный <select multiple> — работаем с ним,
  // а Select2 сам перерисует поле, когда получит событие change.
  const pick = (id, re) => document.querySelector('select#' + id)
    || [...document.querySelectorAll('select')].find(s => re.test(s.id + ' ' + s.name));

  const selDom = pick('pipeline-domains',  /domain|домен/i);
  const selAcc = pick('pipeline-accounts', /account|аккаунт/i);
  if (!selDom || !selAcc) return console.error('не нашёл списки доменов/аккаунтов — открой страницу запуска пайплайна');

  const $ = window.jQuery || window.$;
  const free = (sel) => [...sel.options].filter(o => o.value !== '' && !o.disabled);

  // Select2 слушает jQuery-событие change; без jQuery шлём нативное — его
  // обработчики страницы тоже видят.
  const apply = (sel, values) => {
    if ($ && $.fn && $.fn.select2) $(sel).val(values).trigger('change');
    else {
      const set = new Set(values);
      for (const o of sel.options) o.selected = set.has(o.value);
      if ($) $(sel).trigger('change');
      else sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
  };

  const domsAll = free(selDom);
  const accsAll = free(selAcc);
  if (!domsAll.length) return console.error('в списке доменов пусто — открой список, чтобы он подгрузился, и запусти снова');

  const already = (sel) => [...sel.selectedOptions].map(o => o.value);

  const keepD = ADD ? already(selDom) : [];

  // В подписи домена после имени идёт « — сайты 29/09/2026 01:18», поэтому
  // сравниваем только первое слово.
  const headOf = (o) => (o.textContent || '').trim().toLowerCase().split(/[\s—–-]/)[0];

  const wanted = LIST.trim().split(/[\s,;]+/).map(s => s.trim().toLowerCase()).filter(Boolean);
  let picked, missing = [];

  if (wanted.length) {
    picked = [];
    for (const dom of wanted) {
      const o = domsAll.find(o => headOf(o) === dom);
      if (o) picked.push(o); else missing.push(dom);
    }
    log('в списке на странице:', domsAll.length, '· запрошено:', wanted.length, '· нашлось:', picked.length);
  } else {
    const wantD = DOMAINS > 0 ? DOMAINS : domsAll.length;
    picked = domsAll.slice(0, wantD);
    log('список не задан — берём доступные:', picked.length, 'из', domsAll.length);
  }

  const domVals = [...new Set([...keepD,
    ...picked.filter(o => !keepD.includes(o.value)).map(o => o.value)])];

  apply(selDom, domVals);
  await new Promise(r => setTimeout(r, 300));

  const keepA = ADD ? already(selAcc) : [];
  // сколько аккаунтов добрать: ACCOUNTS штук, а при 0 — ровно под число доменов
  const addA  = ACCOUNTS > 0 ? ACCOUNTS : Math.max(0, domVals.length - keepA.length);
  const accVals = [...new Set([...keepA,
    ...accsAll.filter(o => !keepA.includes(o.value)).slice(0, addA).map(o => o.value)])];

  apply(selAcc, accVals);
  await new Promise(r => setTimeout(r, 300));

  log(`доменов отмечено: ${domVals.length} из ${domsAll.length}`);
  // Домены, которых нет в списке на странице, — это не мелочь: поле показывает
  // только те, где сайты есть, пайплайн не запускался и нет отложенного старта.
  // Значит по ним генерация ещё идёт или пайплайн уже стоит в очереди.
  if (missing.length) log(`!! нет в списке на странице (${missing.length}): ${missing.join(', ')}`);
  log(`аккаунтов отмечено: ${accVals.length} из ${accsAll.length} (хотели ${keepA.length + addA})`);
  if (accVals.length < domVals.length)
    log(`!! аккаунтов меньше, чем доменов, на ${domVals.length - accVals.length}. Лишние домены останутся без пары — убери их или дождись свободных аккаунтов.`);

  const counts = document.querySelector('#pipeline-counts');
  if (counts) log('счётчик на странице:', counts.textContent.trim());
  log('поля заполнены. Кнопку «Запустить пайплайн» жми сам — скрипт её не трогает.');
})();

/* Массовый выбор контент-доменов и аккаунтов — Яндекс.Вебмастер, «Запустить пайплайн»
 *
 * Отмечает в поле «Контент-домен» все доступные домены, а в поле «Аккаунт» —
 * столько аккаунтов, сколько нужно (по умолчанию — ровно столько же, сколько
 * доменов: один аккаунт на один домен, пары идут по порядку списков).
 *
 * Кнопку «Запустить пайплайн» скрипт НЕ нажимает: он только заполняет поля,
 * дальше смотришь счётчик «Выбрано аккаунтов … доменов …» и пары под ним,
 * и запускаешь сам.
 *
 * Запускать в консоли на странице пайплайна.
 */
(async () => {

  const DOMAINS  = 0;   // сколько доменов отметить; 0 — все доступные
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
  const wantD = DOMAINS > 0 ? DOMAINS : domsAll.length;
  const domVals = [...new Set([...keepD,
    ...domsAll.filter(o => !keepD.includes(o.value)).slice(0, wantD).map(o => o.value)])];

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
  log(`аккаунтов отмечено: ${accVals.length} из ${accsAll.length} (хотели ${keepA.length + addA})`);
  if (accVals.length < domVals.length)
    log(`!! аккаунтов меньше, чем доменов, на ${domVals.length - accVals.length}. Лишние домены останутся без пары — убери их или дождись свободных аккаунтов.`);

  const counts = document.querySelector('#pipeline-counts');
  if (counts) log('счётчик на странице:', counts.textContent.trim());
  log('поля заполнены. Кнопку «Запустить пайплайн» жми сам — скрипт её не трогает.');
})();

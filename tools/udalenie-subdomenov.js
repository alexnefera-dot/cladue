/* Удаление всех сабдоменов по списку доменов — dorgen-engine.com/content-domains
 *
 * Порядок как вручную: в поле поиска вводится домен, из найденной строки
 * берётся кнопка «Удалить все сабдомены» и отправляется её форма.
 * Окно confirm не появляется — форма уходит напрямую (fetch), поэтому
 * страница не перезагружается и цикл не прерывается.
 *
 * Запускать в консоли на https://dorgen-engine.com/content-domains
 *
 * СНАЧАЛА DRY = true — ничего не удаляет, только показывает, что нашёл:
 * домен, id, сколько сабдоменов уйдёт. Проверяешь список — потом false.
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

  const DRY     = true;    // <-- false, когда проверишь вывод
  const FROM    = 1;       // с какого домена начать (нумерация с 1)
  const TO      = 0;       // по какой включительно; 0 — до конца списка
  const PAUSE   = 600;     // пауза между доменами, мс — не долбим сервер
  const TIMEOUT = 15000;   // сколько ждать перерисовку таблицы

  const log  = (...a) => console.log('%c[сабдомены]', 'color:#b91c1c;font-weight:bold', ...a);
  // FROM/TO те же, что в скрипте создания сайтов: удаляем и пересоздаём одну и ту
  // же пачку, чтобы сайты не лежали дольше, чем идёт генерация этой пачки.
  const all  = DOMAINS.trim().split(/[\s,;]+/).map(s => s.trim().toLowerCase()).filter(Boolean);
  const list = all.slice(FROM - 1, TO > 0 ? TO : all.length);

  const table = document.querySelector('#content-domains-table')
             || document.querySelector('table.dataTable')
             || document.querySelector('table');
  if (!table) return console.error('не нашёл таблицу — открой /content-domains');

  const search = document.querySelector('#content-domains-table_filter input')
              || document.querySelector('.dataTables_filter input')
              || document.querySelector('input[type="search"]');
  if (!search) return console.error('не нашёл поле поиска — открой /content-domains');

  const rows     = () => [...table.querySelectorAll('tbody tr')];
  const snapshot = () => rows().map(r => r.textContent.trim()).join('|');

  // Вводим домен в поиск так, как это делает человек: DataTables слушает input/keyup.
  const filter = async (dom) => {
    const before = snapshot();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(search, dom);
    for (const ev of ['input', 'keyup', 'change'])
      search.dispatchEvent(new Event(ev, { bubbles: true }));

    const t0 = Date.now();
    while (Date.now() - t0 < TIMEOUT) {
      await new Promise(r => setTimeout(r, 120));
      const now = snapshot();
      if (now !== before && !/загруж|loading|processing/i.test(now)) return true;
    }
    return snapshot() !== before;
  };

  // Из строки достаём кнопку удаления и ЕЁ форму: в onclick указано имя
  // скрытой формы (document.post_xxx.submit()), по нему и берём.
  const findDelete = (row) => {
    const a = [...row.querySelectorAll('a,button')]
      .find(el => /удалить все саб/i.test(el.textContent || '')
               || /delete-all-subdomains/.test(el.getAttribute('onclick') || ''));
    if (!a) return null;

    const oc   = a.getAttribute('onclick') || '';
    const name = oc.match(/document\.([A-Za-z0-9_]+)\s*\.\s*submit/)?.[1];
    const form = (name && (document.forms[name] || document.querySelector(`form[name="${name}"]`)))
              || row.querySelector('form[action*="delete-all-subdomains"]');
    if (!form) return null;

    const action = form.getAttribute('action') || '';
    return {
      form,
      action,
      id:  action.match(/delete-all-subdomains\/(\d+)/)?.[1] || '',
      msg: a.dataset.confirmMessage || a.getAttribute('data-confirm-message') || '',
    };
  };

  log('доменов в списке:', all.length, '· в работе:', list.length,
      `(${FROM}..${TO > 0 ? TO : all.length})`,
      DRY ? '· РЕЖИМ ПРОВЕРКИ (ничего не удаляется)' : '· БОЕВОЙ РЕЖИМ — УДАЛЯЕТ');

  let done = 0, zero = 0, notFound = 0, failed = 0, subs = 0;
  const plan = [];

  for (const [i, dom] of list.entries()) {
    const nom = `${FROM + i}/${all.length} ${dom}`;
    try {
      await filter(dom);

      // строка, у которой ячейка равна домену точь-в-точь: у коротких имён
      // (r6n.team) поиск может зацепить чужие строки.
      const row = rows().find(r => [...r.querySelectorAll('td')]
        .some(td => td.textContent.trim().toLowerCase() === dom));
      if (!row) { notFound++; log(`${nom} — не найден`); continue; }

      const del = findDelete(row);
      if (!del) { failed++; log(`${nom} — кнопки удаления в строке нет`); continue; }

      // Подстраховка: в тексте подтверждения сервер сам пишет домен и число.
      // Если там не наш домен — строка чужая, не трогаем.
      if (del.msg && !del.msg.toLowerCase().includes(dom)) {
        failed++; log(`${nom} — чужая строка (${del.msg}), пропуск`); continue;
      }

      const cnt = Number(del.msg.match(/\((\d+)\)/)?.[1]
                  ?? [...row.querySelectorAll('td')].map(td => td.textContent.trim())
                       .filter(t => /^\d+$/.test(t)).pop() ?? 0);

      if (cnt === 0) { zero++; log(`${nom} — сабдоменов нет, пропуск`); continue; }

      plan.push([dom, del.id, cnt]);

      if (DRY) {
        subs += cnt;
        log(`${nom} — id=${del.id}, БУДЕТ УДАЛЕНО сабдоменов: ${cnt}`);
      } else {
        // форма скрытая, в ней лежит CSRF-токен — отправляем её целиком
        const res = await fetch(del.action, {
          method: (del.form.getAttribute('method') || 'post').toUpperCase(),
          body: new FormData(del.form),
          credentials: 'same-origin',
        });
        if (res.ok) { done++; subs += cnt; log(`${nom} — удалено сабдоменов: ${cnt}`); }
        else       { failed++; log(`${nom} — ошибка HTTP ${res.status}`); }
      }
    } catch (e) { failed++; log(`${nom} — сбой: ${e.message}`); }

    await new Promise(r => setTimeout(r, PAUSE));
  }

  // очищаем поиск, чтобы таблица вернулась в обычный вид
  await filter('');

  window.__plan = plan;
  console.log('\n===== список (домен / id / сабдоменов) =====\n'
    + plan.map(r => r.join('\t')).join('\n') + '\n');
  log(DRY
    ? `ПРОВЕРКА. под удаление попадает доменов: ${plan.length}, сабдоменов: ${subs}; пустых: ${zero}, не найдено: ${notFound}, проблемных: ${failed}`
    : `ГОТОВО. очищено доменов: ${done}, сабдоменов: ${subs}; пустых: ${zero}, не найдено: ${notFound}, ошибок: ${failed}`);
})();

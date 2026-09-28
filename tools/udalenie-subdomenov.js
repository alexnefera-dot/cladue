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
8788.team d6e9.team 9530.team 1609.team gkyh.team z0e1.team zhjs.team
9024.team 9132.team 5246.team 6957.team 4559.team 8958.team 9298.team
enmu.team okev.team 7932.team 2573.team senu.team q6f1.team elmu.team
2651.team v1a1.team 0769.team x4g1.team 8289.team 3061.team foal.team
j2q5.team 3964.team 4020.team ocnk.team 2499.team wgjh.team fzie.team
5605.team 0640.team 9773.team 7001.team 9724.team 1308.team x4m8.team
t6h8.team krla.team 6108.team n3y6.team 3424.team o3d3.team 8189.team
5383.team e1g4.team 0810.team 8882.team agvl.team 2065.team bitr.team
5833.team bxul.team oxkn.team h2s2.team 7638.team 1260.team zrwd.team
m4f6.team 3102.team 3071.team 0361.team vxoq.team 6381.team e4g4.team
kcoi.team dtkx.team 0756.team jazg.team xvtj.team b8s6.team 9009.team
bvrl.team 0146.team 9399.team nvcl.team q9o7.team rjsi.team jlrl.team
2683.team 7618.team 0517.team 5221.team akwh.team 7380.team mrwy.team
cyrq.team bxgr.team cdfb.team u0x1.team 7094.team pypp.team 9201.team
r6n.team 8403.team xhza.team 5028.team 9164.team 6966.team v1l0.team
d5e.team c0o.team airk.team j9o.team e7p3.team jmeb.team 9069.team
6467.team w4k.team 9446.team 9687.team 8089.team s7e.team 8785.team
kcvt.team 7462.team 6581.team 4934.team y1k.team zwpw.team 6000.team
b8w.team 8215.team z5m.team 4974.team m1y.team 6648.team hzyb.team
8650.team davv.team
`;

  const DRY     = true;    // <-- false, когда проверишь вывод
  const PAUSE   = 600;     // пауза между доменами, мс — не долбим сервер
  const TIMEOUT = 15000;   // сколько ждать перерисовку таблицы

  const log  = (...a) => console.log('%c[сабдомены]', 'color:#b91c1c;font-weight:bold', ...a);
  const list = DOMAINS.trim().split(/[\s,;]+/).map(s => s.trim().toLowerCase()).filter(Boolean);

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

  log('доменов в списке:', list.length, DRY ? '· РЕЖИМ ПРОВЕРКИ (ничего не удаляется)' : '· БОЕВОЙ РЕЖИМ — УДАЛЯЕТ');

  let done = 0, zero = 0, notFound = 0, failed = 0, subs = 0;
  const plan = [];

  for (const [i, dom] of list.entries()) {
    const nom = `${i + 1}/${list.length} ${dom}`;
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

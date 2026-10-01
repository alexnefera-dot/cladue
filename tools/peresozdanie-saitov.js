/* Повторное создание сайтов по парам «домен — контент» — dorgen-engine.com/contents
 *
 * Порядок как вручную: в поиск вводится название контента, в найденной строке
 * жмётся «Создать сайты», на открывшейся странице выбирается базовый домен
 * из списка и жмётся «Создать сайты для всех брендов».
 *
 * Страница создания не открывается в браузере: она запрашивается фоном, из неё
 * берётся настоящая форма (вместе с CSRF-токеном) и отправляется с нужным
 * доменом. Поэтому окно confirm не всплывает и цикл не прерывается переходом.
 *
 * Запускать в консоли на https://dorgen-engine.com/contents
 *
 * СНАЧАЛА DRY = true — ничего не создаёт: находит контент, открывает страницу
 * создания и проверяет, что нужный домен в списке есть. Проверяешь вывод —
 * потом false.
 *
 * Генерация тяжёлая (на каждый контент — сайты по всем брендам), поэтому
 * запросы идут строго по одному с паузой. Гнать 135 штук подряд не обязательно:
 * FROM/TO режут список на части — сначала 1..5, посмотрел результат, потом дальше.
 */
(async () => {

  // домен и название контента через пробел, по паре в строке
  const PAIRS = `
0796.team content-2026-09-30-pul2-oform_38
1154.team content-2026-09-30-pul2-oform_39
1441.team content-2026-09-30-pul2-oform_21
1754.team content-2026-09-30-pul2-oform_22
4250.team content-2026-09-30-pul1-oform_17
5957.team content-2026-09-30-pul2-oform_24
6650.team content-2026-09-30-pul2-oform_40
7606.team nabory-717-718-720-obychnye_1
7754.team content-2026-09-30-pul1-oform_19
8726.team content-2026-09-30-pul2-oform_41
9287.team nabory-717-718-720-obychnye_2
9944.team content-2026-09-30-pul1-oform_20
azjo.team content-2026-09-30-pul2-oform_36
f5v7.team content-2026-09-30-12str-oform_1
kzbc.team content-2026-09-30-pul2-oform_26
l9l9.team content-2026-09-30-pul2-oform_23
qovi.team content-2026-09-30-pul2-oform_42
sbjy.team content-2026-09-30-pul2-oform_37
tnes.team content-2026-09-30-pul1-oform_18
udqe.team nabory-717-718-720-obychnye_3
ugpr.team content-2026-09-30-pul2-oform_27
k7l4.team content-2026-09-30-pul1-oform_16
0029.team content-2026-09-30-pul2-oform_15
0077.team content-2026-09-30-vtoroy-7str-oform_25
0231.team content-2026-09-30-pul2-oform_16
0378.team content-2026-09-30-vtoroy-7str-oform_17
0988.team content-2026-09-30-pul2-oform_13
1529.team content-2026-09-30-pul2-oform_20
1895.team content-2026-09-30-vtoroy-7str-oform_22
2247.team content-2026-09-30-vtoroy-7str-oform_20
2278.team content-2026-09-30-vtoroy-12str-oform_8
2829.team content-2026-09-30-pul2-oform_19
2867.team content-2026-09-30-pul2-oform_30
3355.team content-2026-09-30-pul1-oform_11
3968.team content-2026-09-30-vtoroy-7str-oform_23
4342.team content-2026-09-30-vtoroy-7str-oform_26
4478.team content-2026-09-30-vtoroy-12str-oform_6
4658.team content-2026-09-30-vtoroy-12str-oform_2
4791.team content-2026-09-30-pul1-oform_15
5401.team content-2026-09-30-vtoroy-7str-oform_27
5606.team content-2026-09-30-vtoroy-7str-oform_19
5776.team content-2026-09-30-pul1-oform_12
5980.team content-2026-09-30-pul2-oform_31
6249.team content-2026-09-30-vtoroy-12str-oform_5
6327.team content-2026-09-30-pul2-oform_18
6342.team content-2026-09-30-vtoroy-7str-oform_16
7041.team content-2026-09-30-pul2-oform_33
7496.team content-2026-09-30-vtoroy-12str-oform_3
9368.team content-2026-09-30-pul2-oform_29
9674.team content-2026-09-30-pul2-oform_28
9806.team content-2026-09-30-vtoroy-12str-oform_7
h4u5.team content-2026-09-30-pul2-oform_34
hils.team content-2026-09-30-vtoroy-12str-oform_4
ijlp.team content-2026-09-30-pul2-oform_35
jfsf.team content-2026-09-30-pul2-oform_17
kjzq.team content-2026-09-30-vtoroy-12str-oform_1
l2z9.team content-2026-09-30-vtoroy-7str-oform_18
qjbs.team content-2026-09-30-vtoroy-7str-oform_21
rghe.team content-2026-09-30-pul1-oform_13
utwe.team content-2026-09-30-pul1-oform_14
xtve.team content-2026-09-30-vtoroy-7str-oform_24
yheh.team content-2026-09-30-pul2-oform_14
v3v6.team content-2026-09-30-pul1-oform_23
w2b7.team content-2026-09-30-pul1-oform_37
wgwi.team content-2026-09-30-12str-oform_7
wjfb.team content-2026-09-30-pul1-oform_31
yrlw.team content-2026-09-30-pul1-oform_28
zlhz.team content-2026-09-30-12str-oform_4
0550.team content-2026-09-30-12str-oform_2
`;

  const DRY     = true;    // <-- false, когда проверишь вывод
  const FROM    = 1;       // с какой пары начать (нумерация с 1)
  const TO      = 0;       // по какую включительно; 0 — до конца списка
  const PAUSE   = 5000;    // пауза между запусками генерации, мс
  const TIMEOUT = 15000;   // сколько ждать перерисовку таблицы

  const log  = (...a) => console.log('%c[сайты]', 'color:#047857;font-weight:bold', ...a);

  const all = PAIRS.trim().split('\n').map(s => s.trim()).filter(Boolean).map(s => {
    const p = s.split(/[\s,;]+/);
    return { dom: (p[0] || '').toLowerCase(), label: p[1] || '' };
  }).filter(p => p.dom && p.label);

  const list = all.slice(FROM - 1, TO > 0 ? TO : all.length);

  const table = document.querySelector('#contents-table')
             || document.querySelector('table.dataTable')
             || document.querySelector('table');
  const search = document.querySelector('#contents-table_filter input')
              || document.querySelector('.dataTables_filter input')
              || document.querySelector('input[type="search"]');
  if (!table || !search) return console.error('не нашёл таблицу контента — открой /contents');

  const rows     = () => [...table.querySelectorAll('tbody tr')];
  const snapshot = () => rows().map(r => r.textContent.trim()).join('|');

  const filter = async (q) => {
    const before = snapshot();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(search, q);
    for (const ev of ['input', 'keyup', 'change'])
      search.dispatchEvent(new Event(ev, { bubbles: true }));
    const t0 = Date.now();
    while (Date.now() - t0 < TIMEOUT) {
      await new Promise(r => setTimeout(r, 120));
      if (snapshot() !== before) return true;
    }
    return false;
  };

  log('пар в списке:', all.length, '· в работе:', list.length,
      `(${FROM}..${TO > 0 ? TO : all.length})`,
      DRY ? '· РЕЖИМ ПРОВЕРКИ (ничего не создаётся)' : '· БОЕВОЙ РЕЖИМ — ЗАПУСКАЕТ ГЕНЕРАЦИЮ');

  let done = 0, noContent = 0, noDomain = 0, failed = 0;
  const report = [];

  for (const [i, { dom, label } ] of list.entries()) {
    const nom = `${FROM + i}/${all.length} ${label} → ${dom}`;
    try {
      await filter(label);

      // строка с точным совпадением метки: у меток вида ..._1 поиск цепляет
      // и _10, _11 и так далее
      const row = rows().find(r => [...r.querySelectorAll('td')]
        .some(td => td.textContent.trim() === label));
      if (!row) { noContent++; report.push([label, dom, '', 'КОНТЕНТА НЕТ']); log(`${nom} — контент не найден`); continue; }

      const link = row.querySelector('a[href*="/create-from-content/"]');
      const cid  = (link?.getAttribute('href') || '').match(/create-from-content\/(\d+)/)?.[1];
      if (!cid) { failed++; report.push([label, dom, '', 'НЕТ КНОПКИ']); log(`${nom} — кнопки «Создать сайты» в строке нет`); continue; }

      // страница создания — забираем фоном, вместе с формой и списком доменов
      const url  = `/contents/create-from-content/${cid}`;
      const html = await (await fetch(url, { credentials: 'same-origin' })).text();
      const doc  = new DOMParser().parseFromString(html, 'text/html');

      // под красивым Select2 лежит обычный <select> со всеми доменами —
      // сначала ищем его по id, потом просто по всем спискам на странице
      const selects = [
        ...doc.querySelectorAll('select#content-domain-id'),
        ...doc.querySelectorAll('select'),
      ];
      let sel = null, opt = null;
      for (const s of selects) {
        const o = [...s.options].find(o =>
          (o.textContent || '').trim().toLowerCase() === dom ||
          (o.value || '').trim().toLowerCase() === dom);
        if (o) { sel = s; opt = o; break; }
      }
      if (!opt) {
        const cnt = [...doc.querySelectorAll('select option')].length;
        noDomain++; report.push([label, dom, cid, 'ДОМЕНА НЕТ В СПИСКЕ']);
        log(`${nom} — домена нет в списке базовых (id=${cid}, вариантов в списке: ${cnt})`);
        continue;
      }

      const form = sel.closest('form');
      if (!form) { failed++; report.push([label, dom, cid, 'НЕТ ФОРМЫ']); log(`${nom} — форма вокруг списка доменов не найдена`); continue; }
      const action = form.getAttribute('action') || url;

      if (DRY) {
        done++; report.push([label, dom, cid, 'ок']);
        log(`${nom} — id=${cid}, домен в списке есть (${sel.name}=${opt.value}), форма: ${action}`);
      } else {
        const fd = new FormData(form);
        fd.set(sel.name, opt.value);
        // некоторые формы ждут имя нажатой кнопки — FormData её не берёт
        const btn = form.querySelector('[type="submit"][name]');
        if (btn) fd.set(btn.getAttribute('name'), btn.getAttribute('value') || '');

        const res  = await fetch(action, {
          method: (form.getAttribute('method') || 'post').toUpperCase(),
          body: fd, credentials: 'same-origin',
        });
        const body = res.ok ? await res.text() : '';
        const gen  = body.match(/генерац[^#\d]{0,16}#?\s*(\d+)/i)?.[1] || '';

        if (res.ok) { done++; report.push([label, dom, cid, 'запущено' + (gen ? ' #' + gen : '')]); log(`${nom} — запущено${gen ? ', генерация #' + gen : ''}`); }
        else        { failed++; report.push([label, dom, cid, 'HTTP ' + res.status]); log(`${nom} — ошибка HTTP ${res.status}`); }
      }
    } catch (e) { failed++; report.push([label, dom, '', 'сбой: ' + e.message]); log(`${nom} — сбой: ${e.message}`); }

    await new Promise(r => setTimeout(r, PAUSE));
  }

  await filter('');

  window.__report = report;
  console.log('\n===== отчёт (контент / домен / id / результат) =====\n'
    + report.map(r => r.join('\t')).join('\n') + '\n');
  log(DRY
    ? `ПРОВЕРКА. готово к запуску: ${done}, контент не найден: ${noContent}, домена нет: ${noDomain}, проблемных: ${failed}`
    : `ГОТОВО. запущено генераций: ${done}, контент не найден: ${noContent}, домена нет: ${noDomain}, ошибок: ${failed}`);
})();

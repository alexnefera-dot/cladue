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
8788.team content-2026-09-28-7str-oform_38
d6e9.team content-2026-09-28-7str-oform_39
9530.team content-2026-09-28-7str-oform_40
1609.team content-2026-09-28-7str-oform_41
gkyh.team content-2026-09-28-7str-oform_42
z0e1.team content-2026-09-28-7str-oform_43
zhjs.team content-2026-09-28-7str-oform_44
9024.team content-2026-09-28-7str-oform_45
9132.team content-2026-09-28-7str-oform_46
5246.team content-2026-09-28-7str-oform_47
6957.team content-2026-09-28-7str-oform_48
4559.team content-2026-09-28-7str-oform_49
8958.team content-2026-09-28-7str-oform_50
9298.team content-2026-09-28-7str-oform_1
enmu.team content-2026-09-28-7str-oform_2
okev.team content-2026-09-28-7str-oform_3
7932.team content-2026-09-28-7str-oform_4
2573.team content-2026-09-28-7str-oform_5
senu.team content-2026-09-28-7str-oform_6
q6f1.team content-2026-09-28-7str-oform_7
elmu.team content-2026-09-28-7str-oform_8
2651.team content-2026-09-28-7str-oform_9
v1a1.team content-2026-09-28-7str-oform_10
0769.team content-2026-09-28-7str-oform_11
x4g1.team content-2026-09-28-7str-oform_12
8289.team content-2026-09-28-7str-oform_13
3061.team content-2026-09-28-7str-oform_14
foal.team content-2026-09-28-7str-oform_15
j2q5.team content-2026-09-28-7str-oform_16
3964.team content-2026-09-27-пул2-oform_1
4020.team content-2026-09-27-пул2-oform_2
ocnk.team content-2026-09-27-пул2-oform_3
2499.team content-2026-09-27-пул2-oform_4
wgjh.team content-2026-09-27-пул2-oform_5
fzie.team content-2026-09-27-пул2-oform_6
5605.team content-2026-09-27-пул2-oform_7
0640.team content-2026-09-27-пул2-oform_8
9773.team content-2026-09-27-пул2-oform_9
7001.team content-2026-09-27-пул2-oform_10
9724.team content-2026-09-27-пул2-oform_11
1308.team content-2026-09-27-пул2-oform_12
x4m8.team content-2026-09-27-пул2-oform_13
t6h8.team content-2026-09-27-пул2-oform_14
krla.team content-2026-09-27-пул2-oform_15
6108.team content-2026-09-27-пул2-oform_16
n3y6.team content-2026-09-27-пул2-oform_17
3424.team content-2026-09-27-пул2-oform_18
o3d3.team content-2026-09-27-пул2-oform_19
8189.team content-2026-09-27-пул2-oform_20
5383.team content-2026-09-27-пул2-oform_21
e1g4.team content-2026-09-14b-7str-oform-1_22
0810.team NEW100-оформлено_6
8882.team NEW100-оформлено_14
agvl.team NEW100-оформлено_25
2065.team NEW100-оформлено_40
bitr.team content-2026-09-23-7str-6-oform_18
5833.team content-2026-09-21b-7str-2_29
bxul.team content-2026-09-21b-7str-2_26
oxkn.team content-2026-09-21b-12str_1
h2s2.team content-2026-09-25-пул5-oform_36
7638.team content-2026-09-17-7str-oform-1_7
1260.team content-2026-09-21b-12str_8
zrwd.team content-2026-09-23-7str-5-oform_44
m4f6.team content-2026-09-25-пул5-oform_27
3102.team content-2026-09-14b-7str-oform-1_23
3071.team content-2026-09-17-7str-oform-1_12
0361.team NEW100-оформлено_43
vxoq.team NEW100-оформлено_46
6381.team content-2026-09-21-7str-oform-3_40
e4g4.team content-2026-09-21-7str-oform-3_44
kcoi.team NEW100-оформлено_41
dtkx.team NEW100-оформлено_6
0756.team NEW100-оформлено_25
jazg.team NEW100-оформлено_38
xvtj.team NEW100-оформлено_40
b8s6.team content-2026-09-21b-7str-2_29
9009.team content-2026-09-21b-7str-2_26
bvrl.team content-2026-09-21b-12str_1
0146.team content-2026-09-25-пул5-oform_36
9399.team content-2026-09-17-7str-oform-1_7
nvcl.team content-2026-09-21b-12str_8
q9o7.team content-2026-09-23-7str-5-oform_44
rjsi.team content-2026-09-25-пул5-oform_27
jlrl.team content-2026-09-14b-7str-oform-1_23
2683.team content-2026-09-17-7str-oform-1_12
7618.team NEW100-оформлено_43
0517.team NEW100-оформлено_46
5221.team content-2026-09-21-7str-oform-3_40
akwh.team content-2026-09-21-7str-oform-3_44
7380.team NEW100-оформлено_41
mrwy.team content-2026-09-25-пул3-oform_10
cyrq.team content-2026-09-25-пул3-oform_12
bxgr.team content-2026-09-25-пул3-oform_13
cdfb.team content-2026-09-25-пул3-oform_15
u0x1.team content-2026-09-25-пул3-oform_16
7094.team content-2026-09-25-пул3-oform_19
pypp.team content-2026-09-25-пул3-oform_23
9201.team content-2026-09-25-пул3-oform_24
r6n.team content-2026-09-25-пул3-oform_25
8403.team content-2026-09-25-пул3-oform_27
xhza.team content-2026-09-25-пул3-oform_28
5028.team content-2026-09-25-пул3-oform_29
9164.team content-2026-09-25-пул3-oform_30
6966.team content-2026-09-25-пул3-oform_32
v1l0.team content-2026-09-25-пул3-oform_33
d5e.team content-2026-09-25-пул3-oform_34
c0o.team content-2026-09-25-пул3-oform_37
airk.team content-2026-09-25-пул3-oform_38
j9o.team content-2026-09-25-пул3-oform_39
e7p3.team content-2026-09-25-пул3-oform_40
jmeb.team content-2026-09-25-пул3-oform_41
9069.team content-2026-09-25-пул3-oform_45
6467.team content-2026-09-25-пул3-oform_46
w4k.team content-2026-09-25-пул3-oform_47
9446.team content-2026-09-25-пул3-oform_48
9687.team content-2026-09-25-пул3-oform_49
8089.team content-2026-09-25-пул3-oform_50
s7e.team content-2026-09-25-пул4-oform_1
8785.team content-2026-09-25-пул4-oform_2
kcvt.team partiya-698-702_2
7462.team partiya-698-702_3
6581.team partiya-698-702_4
4934.team content-2026-09-26-12str-oform_2
y1k.team content-2026-09-26-12str-oform_3
zwpw.team content-2026-09-26-12str-oform_5
6000.team content-2026-09-26-12str-oform_7
b8w.team content-2026-09-26-12str-oform_8
8215.team content-2026-09-26-12str-oform_10
z5m.team content-2026-09-26-12str-oform_12
4974.team content-2026-09-26-пул1-oform_1
m1y.team content-2026-09-26-пул1-oform_4
6648.team content-2026-09-26-пул1-oform_5
hzyb.team content-2026-09-26-пул1-oform_6
8650.team content-2026-09-26-пул1-oform_8
davv.team content-2026-09-26-пул1-oform_14
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

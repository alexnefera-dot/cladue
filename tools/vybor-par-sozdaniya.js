/* Выбор пар «контент → домен» на массовом создании сайтов — dorgen-engine.com
 *
 * Запускать в консоли на странице «Множественное создание сайтов из контента»,
 * вкладка «Выбрать пары».
 *
 * Скрипт только ЗАПОЛНЯЕТ оба поля. Кнопку «Создать сайты» не трогает —
 * нажимаешь сам, посмотрев «Превью пар».
 *
 * ПРО ПОРЯДОК. Страница собирает пары «по порядку списков», а порядок берётся
 * не из того, как кликали, а из порядка опций внутри самого списка. Контенты и
 * домены отсортированы каждый по своей дате, то есть независимо друг от друга —
 * если просто отметить нужное, пары перемешаются и сайты встанут не на свои
 * домены. Поэтому скрипт переставляет выбранные опции в начало обоих списков
 * ровно в том порядке, в каком идут наши пары: тогда первый контент встречает
 * первый домен. Это обязательно проверить глазами в «Превью пар» перед запуском.
 */
(async () => {

  // домен и метка контента через пробел, по паре в строке (как в сборе контентов)
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

  const log = (...a) => console.log('%c[пары]', 'color:#1d4ed8;font-weight:bold', ...a);

  const pairs = PAIRS.trim().split('\n').map(s => s.trim()).filter(Boolean).map(s => {
    const p = s.split(/[\s,;]+/);
    return { dom: (p[0] || '').toLowerCase(), label: p[1] || '' };
  }).filter(p => p.dom && p.label);
  if (!pairs.length) return console.error('PAIRS пуст — вставь строки «домен контент»');

  // Под Select2 лежат обычные <select multiple> — работаем с ними.
  const pick = (id, re) => document.querySelector('select#' + id)
    || [...document.querySelectorAll('select[multiple]')].find(s => re.test(s.id + ' ' + s.name));

  const selC = pick('bulk-contents', /content_ids|contents/i);
  const selD = pick('bulk-domains',  /content_domain_ids|domains/i);
  if (!selC || !selD) return console.error('не нашёл списки контентов/доменов — открой вкладку «Выбрать пары»');

  // В подписи контента после метки идёт « · id 4741 · создан …» — сравниваем
  // только первую часть, иначе точного совпадения не будет никогда.
  const headOf = (o) => (o.textContent || '').split('·')[0].trim();

  const optsC = [...selC.options];
  const optsD = [...selD.options];
  log('в списке контентов:', optsC.length, '· доменов:', optsD.length);

  const ok = [], missC = [], missD = [];
  for (const { dom, label } of pairs) {
    const oc = optsC.find(o => headOf(o) === label);
    const od = optsD.find(o => (o.textContent || '').trim().toLowerCase() === dom);
    if (!oc) { missC.push(label); continue; }
    if (!od) { missD.push(dom);   continue; }
    ok.push({ dom, label, oc, od });
  }

  if (!ok.length) {
    console.error('ни одной пары не нашлось в списках');
    if (missC.length) log('контентов нет в списке:', missC.join(', '));
    if (missD.length) log('доменов нет в списке:', missD.join(', '));
    return;
  }

  // Переставляем выбранные опции в начало обоих списков, в порядке наших пар.
  ok.forEach(({ oc, od }, i) => {
    selC.insertBefore(oc, selC.options[i] || null);
    selD.insertBefore(od, selD.options[i] || null);
  });

  // Отмечаем только наши, остальное снимаем.
  const setC = new Set(ok.map(x => x.oc));
  const setD = new Set(ok.map(x => x.od));
  for (const o of selC.options) o.selected = setC.has(o);
  for (const o of selD.options) o.selected = setD.has(o);

  // Select2 слушает jQuery-событие change; без jQuery шлём нативное —
  // обработчики страницы (счётчик и превью) видят и его.
  const $ = window.jQuery || window.$;
  if ($) { $(selC).trigger('change'); $(selD).trigger('change'); }
  else {
    selC.dispatchEvent(new Event('change', { bubbles: true }));
    selD.dispatchEvent(new Event('change', { bubbles: true }));
  }

  await new Promise(r => setTimeout(r, 400));

  console.log('\n===== пары в том порядке, в каком их соберёт страница =====\n'
    + ok.map((x, i) => `${i + 1}. ${x.label}  →  ${x.dom}`).join('\n') + '\n');

  log(`выбрано пар: ${ok.length} из ${pairs.length}`);
  if (missC.length) log(`!! контентов нет в списке (${missC.length}): ${missC.join(', ')}`);
  if (missD.length) log(`!! доменов нет в списке (${missD.length}): ${missD.join(', ')}`);

  const counts = document.querySelector('#bulk-counts, #pipeline-counts, .text-muted');
  if (counts) log('счётчик на странице:', counts.textContent.trim());
  log('СВЕРЬ «Превью пар» с выводом выше и жми «Создать сайты» сам — скрипт кнопку не трогает.');
})();

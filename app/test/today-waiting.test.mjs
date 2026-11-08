import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// Верхняя полка главной — ручной список «Ожидает решения»: туда переносят из просроченного то,
// что актуально сейчас. Проверяем, что списки не смешиваются и перенос есть в обе стороны.

const SRC = fileURLToPath(new URL('../public/today.js', import.meta.url));

function loadToday(data) {
  const ctx = {
    document: { querySelectorAll: () => [], getElementById: () => null, addEventListener() {}, createElement: () => ({}) },
    console, localStorage: { getItem: () => null, setItem() {} },
    fetch: async () => ({ json: async () => ({}) }),
    alert() {}, confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout, Date, showScreen() {},
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'today.js' });
  ctx.__d = data;                                        // tdData объявлен через let — только присваиванием
  vm.runInContext('tdData = __d; window.tdWeek = [];', ctx);
  return ctx;
}

const DATA = {
  waiting: [{ id: 7, title: 'Решить с растаможкой', kind: 'decision' }],
  obWaiting: [{ id: 3, name: 'Страховка', amount: 400, currency: '€', next_date: '2026-08-01' }],
  overdue: [{ id: 5, title: 'Оплатить штраф', kind: 'task', due_date: '2026-08-01' }],
  obOverdue: [], dueToday: [], obToday: [],
};

test('доска: наверху «Ожидает решения», а не всё просроченное', () => {
  const html = loadToday(DATA).tdWeekBoard(false);
  const shelf = html.slice(html.indexOf('tdover'), html.indexOf('tdnow'));
  assert.ok(shelf.includes('Ожидает решения · 2'), 'полка не та или считает не то');
  assert.ok(shelf.includes('Решить с растаможкой') && shelf.includes('Страховка'), 'задача или платёж не попали');
  assert.ok(!shelf.includes('Оплатить штраф'), 'просроченное лезет наверх само — а его выносят руками');
});

test('доска: из ожидания можно вернуть строку обратно', () => {
  const html = loadToday(DATA).tdWeekBoard(false);
  assert.ok(html.includes('data-tdwait="task:7:0"'), 'нет возврата задачи');
  assert.ok(html.includes('data-tdwait="ob:3:0"'), 'нет возврата платежа');
});

test('строка просроченного получает кнопку переноса в ожидание', () => {
  const ctx = loadToday(DATA);
  const line = ctx.taskLine(DATA.overdue[0], false, 'in');
  assert.ok(line.includes('data-tdwait="task:5:1"'), 'нет кнопки «вынести в ожидание»');
  assert.ok(ctx.obLine({ id: 9, name: 'Налог', amount: 100 }, 'in').includes('data-tdwait="ob:9:1"'),
    'у платежа нет кнопки переноса');
  assert.ok(!ctx.taskLine(DATA.overdue[0], false).includes('data-tdwait'),
    'без явного режима кнопки переноса быть не должно');
});

test('на десктопе просроченное осталось на экране — из него и переносят', () => {
  const ctx = loadToday({ ...DATA,
    obOverdue: [{ id: 9, name: 'Налог', amount: 100, currency: '€', next_date: '2026-08-10', overdue_days: 20 }],
    routines: [], progress: { total: 1, typed: 1 },
    weekGoals: { done: 0, total: 0 }, inbox: 0, activityMonth: null, checkin: null, events: [], week: [],
    zones: { paymentsWeek: 0, debtsOverdue: 0, practicesToday: 0 },
    people: { birthdays: [], overdueContacts: [] } });
  const node = { addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
    dataset: {}, style: {}, innerHTML: '', value: '', focus() {}, replaceWith() {} };
  ctx.document.getElementById = () => node;
  vm.runInContext('window.tdRestData = { today: tdData.date, ideas: [], log: [] }; window.tdSpheres = [];', ctx);
  ctx.renderToday();
  const html = node.innerHTML;
  assert.ok(html.includes('Просрочено'), 'на десктопе просроченное пропало с экрана');
  assert.ok(html.includes('data-tdwait="task:5:1"') && html.includes('data-tdwait="ob:9:1"'),
    'из просроченного нечем перенести в ожидание');
  assert.ok(html.includes('data-tdwait="task:7:0"'), 'из ожидания нечем вернуть обратно');
});

test('недели на главной нет вовсе: ни блока, ни счётчика, ни данных о ней', () => {
  const full = { ...DATA, obOverdue: [], routines: [], progress: { total: 1, typed: 1 },
    weekGoals: { done: 0, total: 0 }, inbox: 0, activityMonth: null, checkin: null, events: [], week: [],
    zones: { paymentsWeek: 0, debtsOverdue: 0, practicesToday: 0 },
    people: { birthdays: [], overdueContacts: [] } };
  const screen = (mobile) => {
    const ctx = loadToday(full);
    ctx.matchMedia = () => ({ matches: mobile });
    const node = { addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
      dataset: {}, style: {}, innerHTML: '', value: '', focus() {}, replaceWith() {} };
    ctx.document.getElementById = () => node;
    vm.runInContext('window.tdRestData = { today: tdData.date, ideas: [], log: [] }; window.tdSpheres = [];', ctx);
    ctx.renderToday();
    return node.innerHTML;
  };
  for (const [where, html] of [['десктоп', screen(false)], ['телефон', screen(true)]]) {
    assert.ok(!html.includes('Движение недели'), `блок остался на «${where}»`);
    assert.ok(!html.includes('шага(ов)'), `разбивка по категориям осталась на «${where}»`);
    assert.ok(!html.includes('за неделю'), `счётчик недели остался на «${where}» — в шапке или чипом`);
  }
});

test('отмеченные 🎓 навыки видны на главной — и на десктопе, и на телефоне', () => {
  const sph = [
    { id: 1, name: 'Здоровье', milestones: [
      { id: 11, title: 'Подтягиваться 20 раз', progress: 4, skill: 1, skill_by: '2027-04' },
      { id: 12, title: 'Просто веха', progress: 2, skill: 0 }] },
    { id: 2, name: 'Работа', milestones: [
      { id: 21, title: 'Английский C1', progress: 3, skill: 1, skill_by: '2027-01' },
      { id: 22, title: 'Уже умею', progress: 10, skill: 1, skill_by: '2026-12' },
      { id: 23, title: 'Монтаж', progress: 0, skill: 1, skill_by: '' },
      { id: 24, title: 'Студия', progress: 1, skill: 1, skill_by: '2027-09' }] },
  ];
  const screen = mobile => {
    const ctx = loadToday({ ...DATA, obOverdue: [], routines: [], progress: { total: 1, typed: 1 },
      weekGoals: { done: 0, total: 0 }, inbox: 0, activityMonth: null,
      checkin: null, events: [], week: [], zones: { paymentsWeek: 0, debtsOverdue: 0, practicesToday: 0 },
      people: { birthdays: [], overdueContacts: [] } });
    ctx.matchMedia = () => ({ matches: mobile });
    const node = { addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
      dataset: {}, style: {}, innerHTML: '', value: '', focus() {}, replaceWith() {} };
    ctx.document.getElementById = () => node;
    ctx.__sph = sph;
    vm.runInContext('window.tdRestData = { today: tdData.date, ideas: [], log: [] }; window.tdSpheres = __sph;', ctx);
    ctx.renderToday();
    return node.innerHTML;
  };
  for (const [where, html] of [['десктоп', screen(false)], ['телефон', screen(true)]]) {
    assert.match(html, /🎓 Навыки за год · 4/, `на «${where}» нет блока навыков или счёт не тот`);
    assert.ok(html.includes('Английский C1') && html.includes('Подтягиваться 20 раз'),
      `на «${where}» не видно ближайших навыков`);
    assert.ok(!html.includes('Уже умею'), `на «${where}» напоминаем про навык, который уже есть`);
    assert.ok(!html.includes('Просто веха'), `на «${where}» в навыки попала неотмеченная веха`);
    assert.ok(!html.includes('Монтаж'), `на «${where}» показано больше трёх — главная не лента`);
    assert.match(html, /и ещё 1 — вся лента в сферах/, `на «${where}» не сказано, что навыков больше`);
    assert.match(html, /янв 2027/, `на «${where}» не видно срока навыка`);
    // место тоже часть ответа: навыки — итог внизу, а не первое, что видишь утром.
    // Сравниваем с длиной экрана: заголовки у двух вёрсток разные, а «внизу» — общее
    assert.ok(html.indexOf('Навыки за год') > html.length * 0.6,
      `на «${where}» навыки стоят в верхней части экрана, а не внизу`);
  }
});

test('первого числа на главной висит «отложить», пока не отложил', () => {
  const due = [{ id: 1, name: 'Фан-кар', target: 15000, saved: 3200, pct_min: 5, pct_max: 5, incomeMonth: 6000, incomeYm: '2026-09' },
    { id: 2, name: 'EXUS', target: null, saved: 12000, pct_min: 10, pct_max: 30, incomeMonth: 6000, incomeYm: '2026-09' }];
  const html = loadToday({ ...DATA, saveDue: due }).tdWeekBoard(false).replace(/\u00a0/g, ' ');
  assert.ok(html.includes('Отложить в этом месяце'), 'напоминания нет');
  assert.ok(html.includes('5% дохода') && html.includes('10–30% дохода'), 'проценты целей не показаны');
  assert.ok(html.includes('· 300 €') && html.includes('600–1 800 €'), 'суммы от дохода не посчитаны');
  assert.ok(html.includes('доход за сентябрь'), 'не названо, за какой месяц считается процент');
  assert.ok(html.includes('data-savedue="1"') && html.includes('data-savedue="2"'), 'нечем отметить');
  assert.ok(!loadToday(DATA).tdWeekBoard(false).includes('Отложить в этом месяце'),
    'когда класть нечего, блок не должен занимать место');
});

test('пустое ожидание — полки нет вовсе', () => {
  const html = loadToday({ ...DATA, waiting: [], obWaiting: [] }).tdWeekBoard(false);
  assert.ok(!html.includes('tdover'), 'пустая полка занимает место зря');
});

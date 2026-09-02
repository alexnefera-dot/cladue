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
  obOverdue: [], dueToday: [], obToday: [], movement: { total: 0 },
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
    routines: [], progress: { total: 1, typed: 1 }, movement: { total: 0, top: [] },
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

test('пустое ожидание — полки нет вовсе', () => {
  const html = loadToday({ ...DATA, waiting: [], obWaiting: [] }).tdWeekBoard(false);
  assert.ok(!html.includes('tdover'), 'пустая полка занимает место зря');
});

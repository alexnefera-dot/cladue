import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, seedFin, ensurePortfolio, ensureRates } from '../db.js';
import { seedDemo } from '../seed.js';
import { seedPages } from '../notes.js';
import { seedPeople } from '../life.js';
import { buildToday } from '../today.js';
import * as cal from '../cal.js';
import * as fin from '../fin.js';
import * as core from '../core.js';

function fullDb() {
  const db = createDb(':memory:');
  seed(db); seedFin(db); ensurePortfolio(db); ensureRates(db);
  seedPages(db); seedPeople(db); seedDemo(db);
  return db;
}

test('демо-сид: все разделы наполнены, повторный запуск не дублирует', () => {
  const db = fullDb();
  seedDemo(db);   // идемпотентность
  const c = q => db.prepare(q).get().c;
  assert.ok(c('SELECT count(*) AS c FROM nodes WHERE is_category = 0') >= 25, 'записи в Целях');
  assert.equal(c(`SELECT count(*) AS c FROM nodes WHERE title LIKE 'Закрыть налоги%'`), 1, 'без дублей');
  assert.equal(c('SELECT count(*) AS c FROM routines'), 5);
  assert.equal(c('SELECT count(*) AS c FROM events'), 5);
  assert.ok(c('SELECT count(*) AS c FROM transactions') >= 15, 'текущий + прошлый месяц');
  assert.equal(c('SELECT count(*) AS c FROM debts'), 3);
  assert.equal(c('SELECT count(*) AS c FROM macro_notes'), 1);
  assert.equal(c('SELECT count(*) AS c FROM people'), 5);
  assert.ok(c('SELECT count(*) AS c FROM pages') >= 11);
  assert.ok(c(`SELECT count(*) AS c FROM steps WHERE title LIKE '%(пример)%'`) >= 3, 'шаги портфеля');
  assert.ok(c(`SELECT count(*) AS c FROM obligations WHERE name LIKE '%(пример)%'`) >= 4, 'обязательства');
  assert.ok(c(`SELECT count(*) AS c FROM portfolio_items WHERE name LIKE '%(пример)%'`) >= 3, 'демо-раздел портфеля');
});

test('демо-сид оживляет дашборд: просрочка, неделя, рутины, движение, долги', () => {
  const db = fullDb();
  const t = buildToday(db);
  assert.ok(t.overdue.length >= 1, 'есть просроченная задача');
  assert.ok(t.week.length >= 3, 'неделя наполнена (задачи+платежи+события)');
  assert.ok(t.routines.length === 5 && t.routines.some(r => r.streak > 0), 'рутины со стриком');
  assert.ok(t.movement.total >= 1, 'движение недели не пустое');
  assert.ok(t.debtsOverdue.length >= 1, 'просроченный долг виден');
  assert.equal(t.activityMonth, '🎾 Июнь — падл');
  assert.ok(t.people.birthdays.length >= 1 && t.people.overdueContacts.length >= 1);
});

test('демо-сид: блокировки и связи работают, задачник наполнен', () => {
  const db = fullDb();
  const nodes = core.listTree(db).nodes;
  const customs = nodes.find(n => n.title.includes('Растаможка'));
  assert.equal(customs.blocked, true, 'растаможка ждёт решение о резидентстве');
  const half = nodes.find(n => n.title.includes('Наталье'));
  assert.equal(half.blocked, true, 'решение ждёт консультацию');
  const actionable = nodes.filter(n => !n.is_category
    && ['task', 'decision'].includes(n.kind) && !['done', 'accepted'].includes(n.status));
  assert.ok(actionable.length >= 8, 'задачник есть чем наполнить');
  // расходы месяца сгруппированы
  const tx = fin.txMonth(db, new Date().toISOString().slice(0, 7));
  assert.ok(tx.expense > 0 && tx.income > 0 && tx.categories.length >= 4);
  // календарь текущего месяца не пуст
  const month = cal.calendar(db, new Date().toISOString().slice(0, 7));
  assert.ok(month.items.length >= 4);
});

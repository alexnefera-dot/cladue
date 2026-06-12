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
  assert.equal(c('SELECT count(*) AS c FROM events'), 7);
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

test('демо-сид: сегодня, трекинг, прогнозы и имущество живые', () => {
  const db = fullDb();
  seedDemo(db);   // идемпотентность новых под-сидов
  const today = new Date().toISOString().slice(0, 10);
  const t = buildToday(db);
  assert.ok(t.dueToday.length >= 2, 'есть задачи со сроком сегодня');
  assert.ok(t.dueToday.some(x => x.repeat === 'monthly'), 'повтор 🔁 в сегодняшних');
  assert.ok(t.events.some(e => e.date === today), 'событие сегодня');
  // вопрос с ответом и лог хода
  const q = db.prepare(`SELECT * FROM nodes WHERE kind = 'question' AND answer != ''`).get();
  assert.ok(q?.answer.includes('подушка'), 'вопрос с зафиксированным ответом');
  const lawyer = db.prepare(`SELECT id FROM nodes WHERE title LIKE 'Позвонить юристу%'`).get();
  assert.equal(core.listNodeLog(db, lawyer.id).length, 2, 'лог задачи наполнен');
  // трекинг: чек-ины (сегодня свободен) и метрики с историей
  const c = q2 => db.prepare(q2).get().c;
  assert.ok(c('SELECT count(*) AS c FROM checkins') === 10, 'история чек-инов');
  assert.equal(db.prepare('SELECT count(*) AS c FROM checkins WHERE date = ?').get(today).c, 0, 'сегодня не занят');
  assert.equal(c('SELECT count(*) AS c FROM metrics'), 12, '3 числовых примера + 9 колонок дневника');
  assert.equal(c(`SELECT count(*) AS c FROM metrics WHERE type = 'bool'`), 9, 'колонки из гугл-таблицы');
  assert.ok(c('SELECT count(*) AS c FROM metric_log') >= 12, 'история метрик');
  // прогнозы: калибровка считается
  const f = fin.forecasts(db);
  assert.equal(f.rows.length, 4);
  assert.equal(f.resolvedCount, 2);
  assert.ok(Math.abs(f.calibration - 45) < 0.01, '100 − (30+80)/2 = 45');
  // имущество: 3 объекта, 6 правил, налог в платежах недели
  const props = fin.listProperties(db);
  assert.equal(props.length, 3);
  assert.equal(props.reduce((s, p) => s + p.rules.length, 0), 6);
  assert.ok(t.zones.paymentsWeek >= 1, 'регламент в платежах недели');
  // снапшоты: прошлые точки для дельты
  assert.ok(c('SELECT count(*) AS c FROM snapshots') >= 2, 'история нетворса');
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, ensurePortfolio, ensureRates } from '../db.js';
import { buildToday } from '../today.js';
import * as core from '../core.js';
import * as fin from '../fin.js';

const iso = d => d.toISOString().slice(0, 10);
const today = iso(new Date());
const plusDays = n => iso(new Date(Date.now() + n * 864e5));

function freshDb() {
  const db = createDb(':memory:');
  seed(db); ensurePortfolio(db); ensureRates(db);
  return db;
}
const inboxOf = db => core.listCategories(db).find(c => c.title.includes('Инбокс'));

test('сегодня: просрочка, задачи дня и неделя разделены корректно', () => {
  const db = freshDb();
  const inbox = inboxOf(db);
  const mk = (title, due) => {
    const n = core.addChild(db, inbox.id, title);
    core.updateNode(db, n.id, { kind: 'task', due_date: due });
    return n;
  };
  mk('Старая', '2020-01-01');
  mk('Сегодняшняя', today);
  mk('Через 3 дня', plusDays(3));
  mk('Через месяц', plusDays(30));
  const done = mk('Закрытая старая', '2020-02-02');
  core.toggleNode(db, done.id);

  const t = buildToday(db);
  assert.deepEqual(t.overdue.map(x => x.title), ['Старая'], 'закрытые не в просрочке');
  assert.deepEqual(t.dueToday.map(x => x.title), ['Сегодняшняя']);
  assert.ok(t.week.some(x => x.title === 'Через 3 дня'));
  assert.ok(!t.week.some(x => x.title === 'Через месяц'), 'дальше недели не показываем');
  assert.ok(!t.week.some(x => x.title === 'Сегодняшняя'), 'сегодняшнее не дублируется в неделе');
});

test('сегодня: платежи недели и просроченные долги попадают на дашборд', () => {
  const db = freshDb();
  fin.addObligation(db, { name: 'Кредит', amount: 380, period: 'monthly', next_date: plusDays(2) });
  fin.addDebt(db, { name: 'Дима', amount: 60, direction: 'owed_to_me', due_date: '2020-01-01' });
  const start = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Start'`).get();
  fin.patchItem(db, start.id, { is_loan: 1, loan_due: '2020-01-01' });

  const t = buildToday(db);
  assert.ok(t.week.some(x => x.type === 'money' && x.title === 'Кредит'));
  assert.equal(t.debtsOverdue.length, 2, 'ручной долг + займ из портфеля');
  assert.ok(t.debtsOverdue.some(x => x.name.includes('займ из портфеля')));
});

test('сегодня: прогресс разбора, инбокс и сделанное за неделю', () => {
  const db = freshDb();
  const inbox = inboxOf(db);
  const a = core.addChild(db, inbox.id, 'А');
  core.addChild(db, inbox.id, 'Б');
  core.updateNode(db, a.id, { kind: 'task' });
  core.toggleNode(db, a.id);
  const t = buildToday(db);
  assert.equal(t.inbox, 2);
  assert.equal(t.progress.total, 2);
  assert.equal(t.progress.typed, 1);
  assert.equal(t.movement.total, 1);
  assert.equal(t.inboxId, inbox.id);
});

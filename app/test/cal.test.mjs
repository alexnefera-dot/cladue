import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, ensureRates } from '../db.js';
import * as cal from '../cal.js';
import * as fin from '../fin.js';
import * as core from '../core.js';

function freshDb() { const db = createDb(':memory:'); seed(db); ensureRates(db); return db; }
const items = (db, ym, type) => cal.calendar(db, ym).items.filter(i => !type || i.type === type);

test('календарь собирает задачи со сроком в месяце', () => {
  const db = freshDb();
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  const n = core.addChild(db, inbox.id, 'Продать X5');
  core.updateNode(db, n.id, { kind: 'task', due_date: '2026-08-15' });
  const aug = items(db, '2026-08', 'task');
  assert.equal(aug.length, 1);
  assert.equal(aug[0].title, 'Продать X5');
  assert.equal(items(db, '2026-07', 'task').length, 0);
});

test('ежемесячное обязательство разворачивается в каждый месяц, дата платежа сохраняет день', () => {
  const db = freshDb();
  fin.addObligation(db, { name: 'Кредит', amount: 380, period: 'monthly', next_date: '2026-06-13' });
  assert.equal(items(db, '2026-06', 'money')[0].date, '2026-06-13');
  assert.equal(items(db, '2026-09', 'money')[0].date, '2026-09-13');
  fin.addObligation(db, { name: 'Разовый', amount: 1, period: 'once', next_date: '2026-07-01' });
  assert.equal(items(db, '2026-08', 'money').filter(i => i.title === 'Разовый').length, 0, 'разовое не повторяется');
});

test('ДР: годовое событие видно каждый год', () => {
  const db = freshDb();
  cal.addEvent(db, { title: '🎂 ДР мамы', date: '2026-06-19', recur: 'yearly' });
  assert.equal(items(db, '2026-06', 'event')[0].date, '2026-06-19');
  assert.equal(items(db, '2027-06', 'event')[0].date, '2027-06-19');
  assert.equal(items(db, '2026-07', 'event').length, 0);
});

test('шаги портфеля с датой попадают в ленту; события удаляются', () => {
  const db = freshDb();
  fin.addStep(db, { kind: 'buy', title: 'Золото', amount: 4200, planned_date: '2026-06-17' });
  const st = items(db, '2026-06', 'step');
  assert.equal(st.length, 1);
  assert.match(st[0].title, /^Купить: Золото/);
  cal.addEvent(db, { title: 'Встреча', date: '2026-06-20' });
  const ev = items(db, '2026-06', 'event')[0];
  cal.delEvent(db, ev.id);
  assert.equal(items(db, '2026-06', 'event').length, 0);
});

test('лента отсортирована по дате', () => {
  const db = freshDb();
  cal.addEvent(db, { title: 'B', date: '2026-06-20' });
  cal.addEvent(db, { title: 'A', date: '2026-06-05' });
  const all = cal.calendar(db, '2026-06').items;
  assert.ok(all[0].date <= all[all.length - 1].date);
  assert.equal(all[0].title, 'A');
});

test('дедупликация: шаг с задачей виден в календаре один раз — как задача', () => {
  const db = freshDb();
  fin.addStep(db, { kind: 'buy', title: 'Золото', planned_date: '2026-06-17' });
  const st = db.prepare(`SELECT * FROM steps WHERE title = 'Золото'`).get();
  // до привязки: в календаре один шаг, задач нет
  assert.equal(items(db, '2026-06', 'step').length, 1);
  assert.equal(items(db, '2026-06', 'task').length, 0);
  fin.stepToTask(db, st.id);
  // после: одна задача, шаг скрыт
  assert.equal(items(db, '2026-06', 'task').length, 1);
  assert.equal(items(db, '2026-06', 'step').length, 0);
  assert.equal(cal.calendar(db, '2026-06').items.filter(i => i.title.includes('Золото')).length, 1, 'ровно одна запись');
});

test('идемпотентность: повторное «→ задача» не плодит копий', () => {
  const db = freshDb();
  fin.addStep(db, { kind: 'buy', title: 'Облигации', planned_date: '2026-07-01' });
  const st = db.prepare(`SELECT * FROM steps WHERE title = 'Облигации'`).get();
  const t1 = fin.stepToTask(db, st.id);
  const t2 = fin.stepToTask(db, st.id);
  assert.equal(t1.id, t2.id, 'вторая попытка возвращает ту же задачу');
  assert.ok(t2.already);
  const count = db.prepare(`SELECT count(*) AS c FROM nodes WHERE title LIKE '%Облигации%' AND kind = 'task'`).get().c;
  assert.equal(count, 1);
});

test('синк статусов: задача ↔ шаг в обе стороны; удаление задачи отвязывает шаг', () => {
  const db = freshDb();
  fin.addStep(db, { kind: 'sell', title: 'BTC часть', planned_date: '2026-07-10' });
  const st = db.prepare(`SELECT * FROM steps WHERE title = 'BTC часть'`).get();
  const task = fin.stepToTask(db, st.id);
  core.toggleNode(db, task.id);   // задача done
  assert.equal(db.prepare('SELECT status FROM steps WHERE id = ?').get(st.id).status, 'done', 'шаг исполнен вслед за задачей');
  fin.patchStep(db, st.id, { status: 'planned' });  // шаг снова в план
  assert.equal(core.getNode(db, task.id).status, 'todo', 'задача открылась вслед за шагом');
  core.deleteNode(db, task.id);
  assert.equal(db.prepare('SELECT task_id FROM steps WHERE id = ?').get(st.id).task_id, null, 'связь очищена');
  assert.equal(items(db, '2026-07', 'step').length, 1, 'шаг снова виден в календаре сам');
});

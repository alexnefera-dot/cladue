import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, seedFin } from '../db.js';
import * as fin from '../fin.js';
import * as core from '../core.js';

function freshDb() { const db = createDb(':memory:'); seed(db); seedFin(db); return db; }

test('listFin: суммы, доли и отклонения считаются', () => {
  const db = freshDb();
  const d = fin.listFin(db);
  assert.ok(d.accounts.length >= 3);
  assert.ok(d.summary.portfolioTotal > 0);
  const etf = d.classes.find(c => c.name.includes('ETF'));
  assert.ok(Math.abs(etf.share - etf.value / d.summary.portfolioTotal * 100) < 0.01);
  assert.ok(Math.abs(etf.deviation - (etf.share - etf.target_pct)) < 0.01);
  assert.ok(d.summary.fit > 0 && d.summary.fit <= 100);
});

test('счёт: обновление баланса трогает дату, stale считается', () => {
  const db = freshDb();
  const stale = fin.listFin(db).accounts.find(a => a.name.includes('Вклад'));
  assert.ok(stale.stale_days >= 29, 'вклад месяц не обновлялся');
  fin.patchAccount(db, stale.id, { balance: 12500 });
  const after = fin.listFin(db).accounts.find(a => a.id === stale.id);
  assert.equal(after.balance, 12500);
  assert.equal(after.stale_days, 0, 'дата обновления сброшена');
});

test('обязательство: «оплачено» сдвигает дату на период, разовое закрывается', () => {
  const db = freshDb();
  fin.addObligation(db, { name: 'Тест-мес', amount: 100, period: 'monthly', next_date: '2026-01-31' });
  fin.addObligation(db, { name: 'Тест-раз', amount: 500, period: 'once', next_date: '2026-07-01' });
  const d = fin.listFin(db);
  const m = d.obligations.find(o => o.name === 'Тест-мес');
  const o1 = d.obligations.find(o => o.name === 'Тест-раз');
  assert.equal(fin.payObligation(db, m.id).next_date, '2026-02-28', 'конец месяца учтён');
  assert.equal(fin.payObligation(db, o1.id).next_date, null, 'разовое закрыто');
});

test('addMonths: границы месяцев', () => {
  assert.equal(fin.addMonths('2026-01-31', 1), '2026-02-28');
  assert.equal(fin.addMonths('2026-12-15', 1), '2027-01-15');
  assert.equal(fin.addMonths('2026-06-30', 12), '2027-06-30');
});

test('шаг → задача в категории «Финансы» со сроком и заметкой', () => {
  const db = freshDb();
  fin.addStep(db, { kind: 'buy', title: 'Золото ETF', amount: 420000, planned_date: '2026-06-17' });
  const st = fin.listFin(db).steps.find(s => s.title === 'Золото ETF');
  const node = fin.stepToTask(db, st.id);
  assert.match(node.title, /^Купить: Золото ETF/);
  assert.equal(node.kind, 'task');
  assert.equal(node.due_date, '2026-06-17');
  assert.match(node.note, /из плана шагов/);
  const finCat = core.listCategories(db).find(c => c.title === 'Финансы' && !c.parent_id);
  assert.equal(node.parent_id, finCat.id);
});

test('радар задачи видит платежи в окне ±60 дней (возврат из бэклога)', () => {
  const db = freshDb();
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  const n = core.addChild(db, inbox.id, 'Продать машину');
  core.updateNode(db, n.id, { kind: 'task', due_date: '2026-08-31' });
  fin.addObligation(db, { name: 'Налоги за 2025', amount: 90000, period: 'once', next_date: '2026-08-15' });
  fin.addObligation(db, { name: 'Далёкий платёж', amount: 1, period: 'once', next_date: '2027-06-01' });
  const s = core.suggestForNode(db, n.id);
  const names = s.context.payments.map(p => p.name);
  assert.ok(names.includes('Налоги за 2025'), 'близкий платёж виден');
  assert.ok(!names.includes('Далёкий платёж'), 'далёкий не виден');
});

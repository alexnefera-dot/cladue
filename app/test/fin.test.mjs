import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, seedFin, ensurePortfolio, ensureRates } from '../db.js';
import * as fin from '../fin.js';
import * as core from '../core.js';

function freshDb() {
  const db = createDb(':memory:');
  seed(db); seedFin(db); ensurePortfolio(db); ensureRates(db);
  return db;
}

test('портфель: дерево блоков, суммы разделов и блоков из активов', () => {
  const db = freshDb();
  const d = fin.listFin(db);
  assert.equal(d.portfolio.length, 4, '4 блока');
  const frozen = d.portfolio.find(b => b.name.includes('Замороженный'));
  const re = frozen.children.find(c => c.name === 'Недвижимость');
  assert.equal(re.value, 400000, 'Start 100k + Belgravia 300k');
  assert.equal(frozen.value, 475000, 'недвижимость + пассивы');
  assert.equal(d.summary.portfolioTotal, 475000);
});

test('прирост: считается только по активам с ценой покупки', () => {
  const db = freshDb();
  const d0 = fin.listFin(db);
  assert.equal(d0.summary.growth, null, 'без цен покупки прироста нет');
  const start = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Start'`).get();
  fin.patchItem(db, start.id, { buy_value: 80000 });
  const d1 = fin.listFin(db);
  assert.equal(d1.summary.growth.invested, 80000);
  assert.equal(d1.summary.growth.current, 100000, 'текущая только по активам с покупкой');
  assert.equal(d1.summary.growth.abs, 20000);
  assert.ok(Math.abs(d1.summary.growth.pct - 25) < 0.01);
});

test('целевой портфель: target на любом уровне, у блока — свой или сумма детей', () => {
  const db = freshDb();
  const frozen = db.prepare(`SELECT id FROM portfolio_items WHERE name LIKE 'Заморож%'`).get();
  const re = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Недвижимость'`).get();
  fin.patchItem(db, re.id, { target_value: 350000 });
  let tree = fin.portfolioTree(db);
  let fz = tree.find(b => b.id === frozen.id);
  assert.equal(fz.target, 350000, 'цель блока = сумма целей детей');
  fin.patchItem(db, frozen.id, { target_value: 0 });
  tree = fin.portfolioTree(db);
  fz = tree.find(b => b.id === frozen.id);
  assert.equal(fz.target, 0, 'своя цель блока перекрывает детей');
});

test('узлы портфеля: добавление, переименование, каскадное удаление', () => {
  const db = freshDb();
  const growth = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Блок роста'`).get();
  fin.addItem(db, { parent_id: growth.id, name: 'Крипто', kind: 'section' });
  const sec = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Крипто'`).get();
  fin.addItem(db, { parent_id: sec.id, name: 'BTC', kind: 'asset', value: 10000, buy_value: 6000 });
  fin.patchItem(db, sec.id, { name: 'Криптовалюты' });
  let tree = fin.portfolioTree(db);
  const g = tree.find(b => b.id === growth.id);
  assert.equal(g.children[0].name, 'Криптовалюты');
  assert.equal(g.value, 10000);
  fin.delItem(db, sec.id);
  assert.equal(db.prepare(`SELECT count(*) AS c FROM portfolio_items WHERE name = 'BTC'`).get().c, 0, 'актив удалился каскадом');
});

test('курсы: строки созданы, ручной ввод работает', () => {
  const db = freshDb();
  const rates = db.prepare('SELECT * FROM rates').all();
  assert.equal(rates.length, 4);
  const r = fin.rateSet(db, 'BTCUSD', 62734);
  assert.equal(r.price, 62734);
  assert.ok(r.updated_at);
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

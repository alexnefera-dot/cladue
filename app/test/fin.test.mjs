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

test('бивалютный портфель: $ конвертируется в € по курсу, итог в обеих валютах', () => {
  const db = freshDb();
  fin.rateSet(db, 'EURUSD', 1.25);              // 1 € = 1.25 $
  const growth = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Блок роста'`).get();
  fin.addItem(db, { parent_id: growth.id, name: 'IB', kind: 'section' });
  const sec = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'IB'`).get();
  fin.addItem(db, { parent_id: sec.id, name: 'SGOV', kind: 'asset', value: 125, currency: '$', buy_value: 100 });
  const d = fin.listFin(db);
  const g = d.portfolio.find(b => b.id === growth.id);
  assert.equal(g.eur, 100, '125$ / 1.25 = 100€');
  assert.equal(d.summary.portfolioTotal, 475000 + 100, 'итог в €');
  assert.ok(Math.abs(d.summary.portfolioTotalUsd - (475100 * 1.25)) < 0.01, 'итог в $');
  assert.equal(g.invested, 80, 'покупка 100$ = 80€');
  const asset = g.children[0].children[0];
  assert.equal(asset.value, 125, 'у актива — родное значение в его валюте');
  assert.equal(asset.currency, '$');
});

test('курсы: строки созданы, ручной ввод работает', () => {
  const db = freshDb();
  const rates = db.prepare('SELECT * FROM rates').all();
  assert.equal(rates.length, 6, 'золото, EURUSD, BTC + SCHD/IVV/VHT');
  assert.ok(!rates.some(r => r.symbol === '^SPX'), '^SPX заменён на ETF');
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

test('транзакции: месяц фильтруется, категории суммируются', () => {
  const db = freshDb();
  fin.addTx(db, { date: '2026-06-05', amount: 50, category: 'еда' });
  fin.addTx(db, { date: '2026-06-10', amount: 30, category: 'еда' });
  fin.addTx(db, { date: '2026-06-12', amount: 200, category: 'авто' });
  fin.addTx(db, { date: '2026-06-15', amount: 1000, direction: 'income', category: 'зарплата' });
  fin.addTx(db, { date: '2026-07-01', amount: 99, category: 'еда' });
  const t = fin.txMonth(db, '2026-06');
  assert.equal(t.rows.length, 4);
  assert.equal(t.expense, 280);
  assert.equal(t.income, 1000);
  assert.deepEqual(t.categories[0], ['авто', 200]);
  assert.deepEqual(t.categories[1], ['еда', 80]);
});

test('Monefy CSV: точка-с-запятой, даты DD/MM/YYYY, минус = расход', () => {
  const db = freshDb();
  const csv = [
    'date;account;category;amount;currency;converted amount;currency;description',
    '13/06/2026;Cash;Еда;-12,50;EUR;-12,50;EUR;обед',
    '14/06/2026;Card;Зарплата;2000;EUR;2000;EUR;',
    '15.06.2026;Card;Авто;-45;USD;-41;EUR;бензин',
  ].join('\n');
  const n = fin.importMonefy(db, csv);
  assert.equal(n, 3);
  const t = fin.txMonth(db, '2026-06');
  assert.equal(t.expense, 12.5 + 45);
  assert.equal(t.income, 2000);
  const gas = t.rows.find(r => r.note === 'бензин');
  assert.equal(gas.currency, '$');
  assert.equal(gas.date, '2026-06-15');
  assert.ok(t.rows.every(r => r.source === 'monefy'));
});

test('займы: актив со значком 🤝 зеркалится в дебиторку, отдельно не считается', () => {
  const db = freshDb();
  const start = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Start'`).get();
  fin.patchItem(db, start.id, { is_loan: 1, loan_due: '2020-01-01' });
  const d = fin.listFin(db);
  const l = d.loans.find(x => x.id === start.id);
  assert.ok(l, 'займ виден в дебиторке');
  assert.match(l.path, /Замороженный/);
  assert.ok(l.overdue_days > 1000, 'просрочка считается');
  assert.equal(d.summary.portfolioTotal, 475000, 'итог портфеля не меняется — займ уже в нём');
  const ym = new Date().toISOString().slice(0, 7);
  fin.patchItem(db, start.id, { is_loan: 0 });            // вернули — просто снимаем значок
  assert.equal(fin.listFin(db).loans.length, 0);
  assert.equal(fin.txMonth(db, ym).rows.length, 0, 'никаких автодоходов не создаётся');
});

test('типы активов: аллокация по типам в €', () => {
  const db = freshDb();
  const start = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Start'`).get();
  const belg = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Belgravia'`).get();
  const x5 = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'X5' AND kind = 'asset'`).get();
  fin.patchItem(db, start.id, { asset_type: 'недвижка' });
  fin.patchItem(db, belg.id, { asset_type: 'недвижка' });
  fin.patchItem(db, x5.id, { asset_type: 'авто' });
  const d = fin.listFin(db);
  const types = Object.fromEntries(d.byType);
  assert.equal(types['недвижка'], 400000);
  assert.equal(types['авто'], 45000);
  assert.ok(types['без типа'] >= 30000, 'непомеченные собраны в «без типа»');
});

test('FIRE: прогресс и прогноз года', () => {
  const db = freshDb();   // портфель из сида: 475 000 €
  fin.setSetting(db, 'fire_target', '950000');
  fin.setSetting(db, 'fire_return_pct', '0');
  fin.setSetting(db, 'fire_monthly_savings', '10000');
  const f = fin.fireCalc(db, 475000);
  assert.ok(Math.abs(f.progressPct - 50) < 0.01);
  assert.ok(f.months >= 47 && f.months <= 48, '475k / 10k в мес ≈ 47.5 мес');
  fin.setSetting(db, 'fire_monthly_savings', '0');
  assert.equal(fin.fireCalc(db, 475000).months, null, 'без пополнений и доходности — недостижимо');
  assert.equal(fin.fireCalc(db, 1000000).months, 0, 'капитал уже больше цели');
});

test('макро: тезисы копятся историей, последний — первым', () => {
  const db = freshDb();
  fin.addMacro(db, { date: '2026-05-28', phase: 'пик', thesis: 'жду коррекции' });
  fin.addMacro(db, { date: '2026-06-10', phase: 'сжатие', thesis: 'кэш наращиваю' });
  const m = fin.listFin(db).macro;
  assert.equal(m.length, 2);
  assert.equal(m[0].phase, 'сжатие');
  fin.delMacro(db, m[1].id);
  assert.equal(fin.listFin(db).macro.length, 1);
});

test('долги: ручные с направлением, не смешиваются с портфелем', () => {
  const db = freshDb();
  fin.addDebt(db, { name: 'Дима за падл', amount: 60, direction: 'owed_to_me', due_date: '2020-01-01' });
  fin.addDebt(db, { name: 'Я брату', amount: 500, direction: 'i_owe', currency: '$' });
  const d = fin.listFin(db);
  assert.equal(d.debts.length, 2);
  const mine = d.debts.find(x => x.direction === 'owed_to_me');
  assert.ok(mine.overdue_days > 1000, 'просрочка считается');
  assert.equal(d.summary.portfolioTotal, 475000, 'долги не трогают портфель');
  fin.patchDebt(db, mine.id, { direction: 'i_owe' });
  assert.equal(fin.listFin(db).debts.filter(x => x.direction === 'i_owe').length, 2);
  fin.delDebt(db, mine.id);
  assert.equal(fin.listFin(db).debts.length, 1);
});

test('автоцена: qty × курс тикера, валюта $ и пересчёт в €', () => {
  const db = freshDb();
  fin.rateSet(db, 'BTCUSD', 60000);
  fin.rateSet(db, 'EURUSD', 1.2);
  const growth = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Блок роста'`).get();
  fin.addItem(db, { parent_id: growth.id, name: 'Крипта', kind: 'section' });
  const sec = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Крипта'`).get();
  fin.addItem(db, { parent_id: sec.id, name: 'BTC', kind: 'asset' });
  const btc = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'BTC'`).get();
  fin.patchItem(db, btc.id, { qty: 0.5, rate_symbol: 'BTCUSD' });
  const d = fin.listFin(db);
  const g = d.portfolio.find(b => b.id === growth.id);
  const asset = g.children[0].children[0];
  assert.equal(asset.value, 30000, '0.5 × 60000 $');
  assert.equal(asset.currency, '$');
  assert.ok(asset.auto);
  assert.equal(g.eur, 25000, '30000$ / 1.2');
  fin.rateSet(db, 'BTCUSD', 70000);
  const after = fin.portfolioTree(db).find(b => b.id === growth.id).eur;
  assert.ok(Math.abs(after - 35000 / 1.2) < 0.01, 'курс вырос — стоимость пересчиталась сама');
});

test('снапшоты: один в день, дельта считается', () => {
  const db = freshDb();
  fin.recordSnapshot(db);
  fin.recordSnapshot(db);   // второй раз в тот же день — игнор
  assert.equal(db.prepare('SELECT count(*) AS c FROM snapshots').get().c, 1);
  db.prepare(`INSERT INTO snapshots(date, portfolio_eur) VALUES('2020-01-01', 400000)`).run();
  const d = fin.listFin(db);
  assert.equal(d.snapshotDelta.since, '2020-01-01');
  assert.equal(d.snapshotDelta.abs, 75000);
});

test('прогнозы: добавление, резолв, калибровка', () => {
  const db = freshDb();
  fin.addForecast(db, { statement: 'Коррекция S&P до конца года', confidence: 70, due_date: '2026-12-31' });
  fin.addForecast(db, { statement: 'BTC > 100k', confidence: 90 });
  fin.addForecast(db, { statement: 'Ставку снизят', confidence: 60 });
  let f = fin.forecasts(db);
  assert.equal(f.rows.length, 3);
  assert.equal(f.calibration, null, 'без проверенных калибровки нет');
  const a = f.rows.find(r => r.statement.includes('Коррекция'));
  const b = f.rows.find(r => r.statement.includes('BTC'));
  fin.resolveForecast(db, a.id, true);    // 70% и сбылось → ошибка 30
  fin.resolveForecast(db, b.id, false);   // 90% и нет → ошибка 90
  f = fin.forecasts(db);
  assert.equal(f.resolvedCount, 2);
  assert.ok(Math.abs(f.calibration - 40) < 0.01, '100 - (30+90)/2 = 40');
  assert.equal(fin.addForecast(db, { statement: 'x', confidence: 250 }) ?? true, true);
  assert.ok(fin.forecasts(db).rows.every(r => r.confidence <= 99), 'уверенность зажата');
});

test('имущество: объект, регламент с префиксом, ✓ сдвигает дату, видно в радаре', () => {
  const db = freshDb();
  fin.addProperty(db, { name: 'X5', category: 'авто' });
  const prop = fin.listProperties(db)[0];
  fin.addRule(db, prop.id, { name: 'страховка', amount: 240, period: 'yearly', next_date: '2026-07-10' });
  fin.addRule(db, prop.id, { name: 'ТО', period: 'yearly' });
  const withRules = fin.listProperties(db)[0];
  assert.equal(withRules.rules.length, 2);
  const ins = withRules.rules.find(r => r.name.includes('страховка'));
  assert.equal(ins.name, 'X5: страховка', 'имя с префиксом объекта');
  // «оплачено» сдвигает на год
  assert.equal(fin.payObligation(db, ins.id).next_date, '2027-07-10');
  // регламент виден в радаре задач как платёж
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  const n = core.addChild(db, inbox.id, 'Продать X5');
  core.updateNode(db, n.id, { kind: 'task', due_date: '2027-08-01' });
  const names = core.suggestForNode(db, n.id).context.payments.map(p => p.name);
  assert.ok(names.includes('X5: страховка'));
  // удаление объекта чистит регламент
  fin.delProperty(db, prop.id);
  assert.equal(fin.listProperties(db).length, 0);
  assert.equal(db.prepare('SELECT count(*) AS c FROM obligations WHERE property_id IS NOT NULL').get().c, 0);
});

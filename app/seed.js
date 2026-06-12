// Демо-наполнение всех разделов. Льётся и в непустую базу (поверх данных пользователя),
// но один раз: каждый под-сид проверяет наличие своих записей с пометкой «(пример)».
import * as core from './core.js';
import * as fin from './fin.js';
import * as life from './life.js';
import * as cal from './cal.js';
import { addPage, listPages } from './notes.js';

const iso = d => d.toISOString().slice(0, 10);
const rel = n => iso(new Date(Date.now() + n * 864e5));

function cat(db, title, parentTitle = null) {
  const rows = db.prepare('SELECT id, parent_id FROM nodes WHERE is_category = 1 AND title = ?').all(title);
  if (!parentTitle) return rows.find(r => !r.parent_id)?.id ?? rows[0]?.id;
  const parent = db.prepare('SELECT id FROM nodes WHERE is_category = 1 AND title = ? AND parent_id IS NULL').get(parentTitle)
    ?? db.prepare('SELECT id FROM nodes WHERE is_category = 1 AND title = ?').get(parentTitle);
  return rows.find(r => r.parent_id === parent?.id)?.id;
}

export function seedDemo(db) {
  seedNodes(db);
  seedRoutines(db);
  seedEvents(db);
  seedTx(db);
  seedDebts(db);
  seedStepsObls(db);
  seedPortfolioExtra(db);
  seedPagesExtra(db);
  seedMacroFire(db);
  seedNodesToday(db);
  seedEventsToday(db);
  seedCheckins(db);
  seedMetrics(db);
  seedForecasts(db);
  seedProperties(db);
  seedSnapshotPast(db);
  seedDiary(db);
}

// ===== Цели: ~25 записей с типами, сроками, связями и парой-дублем =====
function seedNodes(db) {
  if (db.prepare(`SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND title LIKE '%(пример)%'`).get().c > 0) return;
  const mk = (parentId, title, fields = {}) => {
    const n = core.addChild(db, parentId, title);
    if (Object.keys(fields).length) core.updateNode(db, n.id, fields);
    return n.id;
  };
  const inbox = cat(db, '📥 Инбокс');
  mk(inbox, 'Разобрать выписку брокера (пример)');
  mk(inbox, 'Идея: вечер без экранов раз в неделю (пример)');
  mk(inbox, 'Август продать х5? (пример)');             // пара-дубль для теста объединения
  mk(inbox, 'Спросить Игоря про рынок авто (пример)');

  // Финансы
  mk(cat(db, 'Налоги', 'Финансы'), 'Закрыть налоги за 2025 (пример)',
    { kind: 'task', priority: 'P0', due_date: rel(5) });
  mk(cat(db, 'Активы', 'Финансы'), 'Ребаланс: докупить облигации (пример)',
    { kind: 'task', priority: 'P1', due_date: rel(12) });
  mk(cat(db, 'Платежи', 'Финансы'), 'Продлить страховку авто (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(-1) });          // просрочена
  const doneId = mk(cat(db, 'Балансы', 'Финансы'), 'Обновить балансы счетов (пример)', { kind: 'task' });
  core.toggleNode(db, doneId);
  mk(cat(db, 'Траты', 'Финансы'), 'Спланировать бюджет отпуска (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(25) });

  // Легализация
  const vnzh = cat(db, 'ВНЖ', 'Легализация');
  const dResid = mk(vnzh, 'Резидентство SK? (пример)', { kind: 'decision' });
  mk(vnzh, 'Узнать сроки ВНЖ — Наталья ~январь (пример)', { kind: 'task', priority: 'P2', due_date: rel(45) });
  const customs = mk(vnzh, 'Растаможка/замена МХ5 (пример)', { kind: 'task', priority: 'P3' });
  core.addLink(db, dResid, customs, 'blocks');

  // Жизнь
  const fam = cat(db, 'Семья', 'Жизнь');
  const consult = mk(fam, 'Консультация по договору (пример)', { kind: 'task', priority: 'P1', due_date: rel(9) });
  const dHalf = mk(fam, 'Половину от продажи — Наталье? (пример)', { kind: 'decision' });
  core.addLink(db, consult, dHalf, 'blocks');
  mk(fam, 'Продать Х5 до росписи (пример)');             // вторая половина пары-дубля
  mk(cat(db, 'Здоровье', 'Жизнь'), 'Записаться к стоматологу (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(3) });
  mk(cat(db, 'Развитие', 'Жизнь'), 'Курс испанского — выбрать школу (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(15) });
  mk(cat(db, 'Отдых', 'Жизнь'), 'Уикенд в горах в июле (пример)', { kind: 'idea' });
  mk(cat(db, 'Отдых', 'Жизнь'), 'Забронировать отпуск на август (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(20) });

  // Работа
  mk(cat(db, 'Проекты', 'Работа'), 'План квартала команде (пример)',
    { kind: 'task', priority: 'P1', due_date: rel(2) });
  mk(cat(db, 'Рост', 'Работа'), 'Запросить повышение грейда (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(30) });
  mk(cat(db, 'Рост', 'Работа'), 'Менять ли стек на следующий год? (пример)', { kind: 'decision' });

  // История и расчёты
  mk(cat(db, 'Налоговые расчёты', 'История и расчёты'), 'Посчитать налог с продажи Х5 (пример)',
    { kind: 'task', priority: 'P1', due_date: rel(8) });
  mk(cat(db, 'История', 'История и расчёты'), 'Заархивировать документы 2024 (пример)',
    { kind: 'task', priority: 'P3' });

  // Тревоги и глобальное
  mk(cat(db, 'Налоги', 'Тревоги'), 'Боюсь ошибиться с налоговым резидентством (пример)', { kind: 'worry' });
  mk(cat(db, 'Брокеры', 'Тревоги'), 'А вдруг брокер заморозит вывод (пример)', { kind: 'worry' });
  const glob = cat(db, 'Глобальные цели');
  const sea = mk(glob, 'Жить у моря, работать на себя (пример)');
  mk(sea, 'Декомпозировать цель по годам (пример)', { kind: 'task', priority: 'P2' });
  mk(glob, 'Капитал 950k € к 2030 (пример)', { kind: 'task', priority: 'P1' });
  mk(glob, 'НЕ СПЕШИМ до 2028 — про МХ5 (пример)', { kind: 'principle' });
}

function seedRoutines(db) {
  if (db.prepare(`SELECT count(*) AS c FROM routines WHERE name LIKE '%(пример)%'`).get().c > 0) return;
  life.addRoutine(db, { name: 'Таблетка (пример)', slot: 'утро', time: '08:00' });
  life.addRoutine(db, { name: 'Чтение 20 стр (пример)', slot: 'день' });
  life.addRoutine(db, { name: 'Отжимания 3×15 (пример)', slot: 'вечер' });
  life.addRoutine(db, { name: 'Миноксидил (пример)', slot: 'вечер', time: '21:00' });
  life.addRoutine(db, { name: 'Планирование дня (пример)', slot: 'утро', time: '08:30' });
  const tabl = db.prepare(`SELECT id FROM routines WHERE name LIKE 'Таблетка%(пример)%'`).get().id;
  const mino = db.prepare(`SELECT id FROM routines WHERE name LIKE 'Миноксидил%(пример)%'`).get().id;
  for (const d of [rel(-1), rel(-2), rel(-3), rel(-4)])
    db.prepare('INSERT OR IGNORE INTO routine_log(routine_id, date) VALUES(?,?)').run(tabl, d);
  db.prepare('INSERT OR IGNORE INTO routine_log(routine_id, date) VALUES(?,?)').run(mino, rel(-1));
}

function seedEvents(db) {
  if (db.prepare(`SELECT count(*) AS c FROM events WHERE title LIKE '%(пример)%'`).get().c > 0) return;
  cal.addEvent(db, { title: 'Созвон с бухгалтером (пример)', date: rel(1), time: '14:00' });
  cal.addEvent(db, { title: 'Стоматолог (пример)', date: rel(2), time: '11:00' });
  cal.addEvent(db, { title: 'Встреча с юристом (пример)', date: rel(4), time: '11:00' });
  cal.addEvent(db, { title: 'Падл-турнир (пример)', date: rel(9) });
  cal.addEvent(db, { title: 'Ревью месяца (пример)', date: rel(13), recur: 'monthly' });
}

function seedTx(db) {
  if (db.prepare(`SELECT count(*) AS c FROM transactions WHERE note LIKE '%(пример)%'`).get().c > 0) return;
  const monthStart = iso(new Date()).slice(0, 8) + '01';
  const day = n => { const d = rel(-n); return d < monthStart ? monthStart : d; };
  const rows = [
    [0, 'еда', 14, 'кофе и ланч'], [1, 'еда', 12.5, 'обед'], [2, 'еда', 38, 'продукты'],
    [3, 'авто', 45, 'бензин'], [4, 'развлечения', 25, 'падл-корт'], [5, 'быт', 19, 'химия'],
    [6, 'еда', 22, 'ужин'], [7, 'подписки', 9.99, 'iCloud'], [8, 'авто', 120, 'мойка+мелочи'],
    [9, 'развлечения', 30, 'кино'], [10, 'здоровье', 60, 'стоматолог консультация'],
  ];
  for (const [n, category, amount, note] of rows)
    fin.addTx(db, { date: day(n), category, amount, note: note + ' (пример)' });
  fin.addTx(db, { date: day(8), direction: 'income', category: 'зарплата', amount: 4200, note: 'аванс (пример)' });
  // прошлый месяц — для навигации ‹ ›
  const prevEnd = iso(new Date(Date.parse(monthStart) - 864e5));
  const pm = prevEnd.slice(0, 8);
  for (const [d, category, amount, note] of [
    ['05', 'еда', 310, 'продукты за месяц'], ['10', 'авто', 95, 'бензин'],
    ['15', 'развлечения', 80, 'ресторан'], ['20', 'быт', 45, 'хозтовары'],
    ['25', 'подписки', 9.99, 'iCloud'],
  ]) fin.addTx(db, { date: pm + d, category, amount, note: note + ' (пример)' });
  fin.addTx(db, { date: pm + '08', direction: 'income', category: 'зарплата', amount: 4200, note: 'зарплата (пример)' });
}

function seedDebts(db) {
  if (db.prepare(`SELECT count(*) AS c FROM debts WHERE name LIKE '%(пример)%'`).get().c > 0) return;
  fin.addDebt(db, { name: 'Дима за падл-корты (пример)', amount: 60, direction: 'owed_to_me', due_date: rel(-9) });
  fin.addDebt(db, { name: 'Брату за билеты (пример)', amount: 500, currency: '$', direction: 'i_owe', due_date: rel(20) });
  fin.addDebt(db, { name: 'Аванс подрядчику вернуть (пример)', amount: 300, direction: 'owed_to_me', due_date: rel(14) });
}

function seedStepsObls(db) {
  if (db.prepare(`SELECT count(*) AS c FROM steps WHERE title LIKE 'Золото ETF%'`).get().c === 0) {
    fin.addStep(db, { kind: 'buy', title: 'Золото ETF (пример)', amount: 5000, planned_date: rel(6) });
    fin.addStep(db, { kind: 'sell', title: 'Часть BTC (пример)', amount: 3000, planned_date: rel(18), condition: 'BTC > $120k' });
    fin.addStep(db, { kind: 'transfer', title: 'Пополнить брокера (пример)', amount: 2000, condition: 'после зарплаты' });
  }
  if (db.prepare(`SELECT count(*) AS c FROM obligations WHERE name LIKE 'Интернет%'`).get().c === 0) {
    fin.addObligation(db, { name: 'Интернет (пример)', amount: 35, period: 'monthly', next_date: rel(7) });
    fin.addObligation(db, { name: 'Spotify (пример)', amount: 9.99, period: 'monthly', next_date: rel(3), kind: 'subscription' });
    fin.addObligation(db, { name: 'Страховка квартиры (пример)', amount: 240, period: 'yearly', next_date: rel(40) });
    fin.addObligation(db, { name: 'Крупная трата: новая камера (пример)', amount: 1800, period: 'once', next_date: rel(50) });
  }
}

// Демо-раздел в портфеле: отдельной веткой, удаляется одним крестиком
function seedPortfolioExtra(db) {
  if (db.prepare(`SELECT count(*) AS c FROM portfolio_items WHERE name LIKE '%(пример)%'`).get().c > 0) return;
  const dev = db.prepare(`SELECT id FROM portfolio_items WHERE kind = 'block' AND name LIKE 'Блок развития%'`).get();
  if (!dev) return;
  fin.addItem(db, { parent_id: dev.id, name: 'Демо-раздел (пример)', kind: 'section' });
  const sec = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'Демо-раздел (пример)'`).get();
  fin.addItem(db, { parent_id: sec.id, name: 'SGOV (пример)', kind: 'asset', value: 1250, currency: '$', buy_value: 1000, asset_type: 'облигации' });
  fin.addItem(db, { parent_id: sec.id, name: 'PAXG (пример)', kind: 'asset', currency: '$', asset_type: 'золото' });
  const paxg = db.prepare(`SELECT id FROM portfolio_items WHERE name = 'PAXG (пример)'`).get();
  fin.patchItem(db, paxg.id, { qty: 1, rate_symbol: 'XAUUSD' });   // автоцена от курса золота
}

function seedPagesExtra(db) {
  if (listPages(db).some(p => p.title.includes('Книги и конспекты'))) return;
  const books = addPage(db, { title: 'Книги и конспекты (пример)', content:
`# Полка

## Читаю
- Психология денег — Морган Хаузел

## Хочу прочитать
- [ ] Атомные привычки
- [ ] Чёрный лебедь

> Правило: один конспект на книгу, страницей ниже.
` });
  addPage(db, { parent_id: books.id, title: 'Психология денег — конспект (пример)', content:
`## Главное

1. Богатство — это то, что не видно: непотраченные деньги
2. Хвост распределения решает всё — давай сложному проценту время
3. **Запас прочности** важнее оптимизации доходности

Связки: [[Капитал 950k € к 2030 (пример)]]
` });
  addPage(db, { title: 'Идеи путешествий (пример)', content:
`# Куда хочется

- [ ] Доломиты — треккинг
- [x] Лиссабон
- [ ] Япония весной

Ближайшее: [[Уикенд в горах в июле (пример)]]
` });
}

// ===== Сегодняшний срез: задачи на сегодня, повторы 🔁, вопрос с ответом, лог хода =====
function seedNodesToday(db) {
  if (db.prepare(`SELECT count(*) AS c FROM nodes WHERE title LIKE 'Оплатить интернет и подписки%'`).get().c > 0) return;
  const mk = (parentId, title, fields = {}) => {
    const n = core.addChild(db, parentId, title);
    if (Object.keys(fields).length) core.updateNode(db, n.id, fields);
    return n.id;
  };
  // задачи со сроком СЕГОДНЯ — оживляют блок «Задачи на сегодня»
  mk(cat(db, 'Платежи', 'Финансы'), 'Оплатить интернет и подписки (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(0), repeat: 'monthly' });   // 🔁 закрыл — сдвинется на месяц
  const lawyer = mk(cat(db, 'ВНЖ', 'Легализация'), 'Позвонить юристу — пакет документов ВНЖ (пример)',
    { kind: 'task', priority: 'P1', due_date: rel(0) });
  core.addNodeLog(db, lawyer, 'оставил голосовое, ждёт ответа от канцелярии', rel(-7));
  core.addNodeLog(db, lawyer, 'юрист: пакет реально собрать к январю, нужен апостиль', rel(-2));
  // повтор еженедельный
  mk(cat(db, 'Отдых', 'Жизнь'), 'Падл — два корта на вечер (пример)',
    { kind: 'task', priority: 'P3', due_date: rel(2), repeat: 'weekly' });
  // вопрос с зафиксированным ответом — поле «ответ» в карточке
  mk(cat(db, 'Балансы', 'Тревоги'), 'Сколько держать в кэше? (пример)', {
    kind: 'question',
    answer: 'Решил: подушка 6 мес расходов + кэш под докупки лесенкой. Не размещать подушку в крипте.',
  });
}

function seedEventsToday(db) {
  if (db.prepare(`SELECT count(*) AS c FROM events WHERE title LIKE 'Падл-корт%'`).get().c > 0) return;
  cal.addEvent(db, { title: 'Падл-корт (пример)', date: rel(0), time: '19:00' });
  cal.addEvent(db, { title: 'Завтрак с Натальей (пример)', date: rel(0), time: '09:30' });
}

// ===== Трекинг: история чек-инов (сегодня оставляем пустым — для живой отметки) =====
function seedCheckins(db) {
  if (db.prepare('SELECT count(*) AS c FROM checkins').get().c > 0) return;
  const days = [
    [-1, 3, 'падл + закрыл два дела'], [-2, 2, ''], [-3, 1, 'разнесло тревогой по налогам'],
    [-4, 2, ''], [-5, 3, 'созвон с Натальей, ясность по срокам'], [-6, 2, ''],
    [-7, 3, 'выходной без ноутбука'], [-8, 2, ''], [-9, 2, ''], [-10, 3, ''],
  ];
  for (const [n, mood, note] of days) life.setCheckin(db, mood, note, rel(n));
}

function seedMetrics(db) {
  if (db.prepare('SELECT count(*) AS c FROM metrics').get().c > 0) return;
  life.addMetric(db, { name: 'Вес (пример)', unit: 'кг' });
  life.addMetric(db, { name: 'Падл (пример)', unit: 'ч/нед' });
  life.addMetric(db, { name: 'Испанский (пример)', unit: 'мин' });
  const id = n => db.prepare('SELECT id FROM metrics WHERE name = ?').get(n).id;
  const w = id('Вес (пример)');
  for (const [n, v] of [[-13, 84.6], [-11, 84.4], [-9, 84.5], [-7, 84.1], [-5, 84.0], [-3, 83.9], [-1, 83.8]])
    life.setMetricValue(db, w, v, rel(n));
  const p = id('Падл (пример)');
  for (const [n, v] of [[-12, 1.5], [-5, 3], [-1, 1.5]]) life.setMetricValue(db, p, v, rel(n));
  const e = id('Испанский (пример)');
  for (const [n, v] of [[-4, 30], [-2, 25], [-1, 20]]) life.setMetricValue(db, e, v, rel(n));
}

// ===== Дневник: колонки-отметки из гугл-таблицы пользователя (его реальный список) =====
function seedDiary(db) {
  // «Подъем не в 10» исключён по просьбе пользователя — вычищаем и из старых баз
  const old = db.prepare(`SELECT id FROM metrics WHERE name = 'Подъем не в 10'`).get();
  if (old) {
    db.prepare('DELETE FROM metric_log WHERE metric_id = ?').run(old.id);
    db.prepare('DELETE FROM metrics WHERE id = ?').run(old.id);
  }
  if (db.prepare(`SELECT count(*) AS c FROM metrics WHERE name = 'Ютуб при работе'`).get().c > 0) return;
  for (const name of ['Ютуб при работе', 'Тревога (не в 20:00)', 'Инвестиции в будние',
    'Майндсет урок', 'Книга', 'Недвижка / Авто', 'Психолог', 'Падл'])
    life.addMetric(db, { name, type: 'bool' });
}

// ===== Прогнозы: два открытых + два проверенных (чтобы калибровка считалась) =====
function seedForecasts(db) {
  if (db.prepare('SELECT count(*) AS c FROM forecasts').get().c > 0) return;
  const yearEnd = new Date().getFullYear() + '-12-31';
  fin.addForecast(db, { statement: 'S&P: коррекция ≥10% до конца года (пример)', confidence: 65, due_date: yearEnd });
  fin.addForecast(db, { statement: 'BTC выше $150k (пример)', confidence: 55, due_date: rel(180) });
  fin.addForecast(db, { statement: 'ЕЦБ снизит ставку ещё раз летом (пример)', confidence: 70 });
  fin.addForecast(db, { statement: 'EUR/USD уйдёт ниже 1.05 весной (пример)', confidence: 80 });
  const byStmt = s => db.prepare('SELECT id FROM forecasts WHERE statement LIKE ?').get(s + '%').id;
  fin.resolveForecast(db, byStmt('ЕЦБ снизит ставку'), true);     // ошибка 30
  fin.resolveForecast(db, byStmt('EUR/USD уйдёт ниже'), false);   // ошибка 80 → калибровка 45
}

// ===== Имущество: объекты с регламентами (правила сразу видны в календаре и радаре платежей) =====
function seedProperties(db) {
  if (db.prepare('SELECT count(*) AS c FROM properties').get().c > 0) return;
  fin.addProperty(db, { name: 'X5 (пример)', category: 'авто' });
  fin.addProperty(db, { name: 'Квартира (пример)', category: 'недвижимость' });
  fin.addProperty(db, { name: 'MacBook (пример)', category: 'техника' });
  const byName = n => db.prepare('SELECT id FROM properties WHERE name = ?').get(n).id;
  const x5 = byName('X5 (пример)');
  fin.addRule(db, x5, { name: 'страховка', amount: 240, period: 'yearly', next_date: rel(35) });
  fin.addRule(db, x5, { name: 'ТО', amount: 350, period: 'yearly', next_date: rel(80) });
  fin.addRule(db, x5, { name: 'дорожный налог', amount: 120, period: 'yearly', next_date: rel(6) });  // попадёт в «платежи недели»
  const flat = byName('Квартира (пример)');
  fin.addRule(db, flat, { name: 'страховка жилья', amount: 180, period: 'yearly', next_date: rel(140) });
  fin.addRule(db, flat, { name: 'обслуживание кондиционера', amount: 90, period: 'yearly', next_date: rel(60) });
  fin.addRule(db, byName('MacBook (пример)'), { name: 'AppleCare', amount: 99, period: 'yearly', next_date: rel(200) });
}

// ===== История нетворса: пара прошлых точек, чтобы Δ к прошлому снимку была живой =====
function seedSnapshotPast(db) {
  if (db.prepare('SELECT count(*) AS c FROM snapshots').get().c > 1) return;
  const total = fin.portfolioTree(db).reduce((s, b) => s + b.eur, 0);
  if (!total) return;
  const ins = db.prepare('INSERT OR IGNORE INTO snapshots(date, portfolio_eur) VALUES(?,?)');
  ins.run(rel(-30), Math.round(total * 0.94));
  ins.run(rel(-7), Math.round(total * 0.985));
}

function seedMacroFire(db) {
  if (db.prepare(`SELECT count(*) AS c FROM macro_notes`).get().c === 0)
    fin.addMacro(db, { phase: 'пик', thesis: 'Жду коррекции: кэш наращиваю, докупки лесенкой (пример)' });
  if (fin.getSetting(db, 'fire_target') == null) {
    fin.setSetting(db, 'fire_target', '950000');
    fin.setSetting(db, 'fire_return_pct', '5');
    fin.setSetting(db, 'fire_monthly_savings', '3000');
  }
  if (fin.getSetting(db, 'activity_month') == null)
    fin.setSetting(db, 'activity_month', '🎾 Июнь — падл');
}

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

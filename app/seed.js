// Демо-наполнение всех разделов. Каждый под-сид срабатывает только если раздел пуст,
// поэтому реальные данные пользователя никогда не перетираются.
import * as core from './core.js';
import * as fin from './fin.js';
import * as life from './life.js';
import * as cal from './cal.js';

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
  seedMacroFire(db);
}

// ===== Цели: типизированные записи со сроками и связями =====
function seedNodes(db) {
  if (db.prepare('SELECT count(*) AS c FROM nodes WHERE is_category = 0').get().c > 0) return;
  const mk = (parentId, title, fields = {}) => {
    const n = core.addChild(db, parentId, title);
    if (Object.keys(fields).length) core.updateNode(db, n.id, fields);
    return n.id;
  };
  // Инбокс — неразобранное
  const inbox = cat(db, '📥 Инбокс');
  mk(inbox, 'Разобрать выписку брокера (пример)');
  mk(inbox, 'Идея: вечер без экранов раз в неделю (пример)');

  // Финансы
  mk(cat(db, 'Налоги', 'Финансы'), 'Закрыть налоги за 2025 (пример)',
    { kind: 'task', priority: 'P0', due_date: rel(5) });
  mk(cat(db, 'Активы', 'Финансы'), 'Ребаланс: докупить облигации (пример)',
    { kind: 'task', priority: 'P1', due_date: rel(12) });
  mk(cat(db, 'Платежи', 'Финансы'), 'Продлить страховку авто (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(-1) });          // просрочена — для дашборда
  const doneId = mk(cat(db, 'Балансы', 'Финансы'), 'Обновить балансы счетов (пример)', { kind: 'task' });
  core.toggleNode(db, doneId);                                      // сделано — для «движения недели»

  // Легализация: решение блокирует задачу
  const vnzh = cat(db, 'ВНЖ', 'Легализация');
  const dResid = mk(vnzh, 'Резидентство SK? (пример)', { kind: 'decision' });
  mk(vnzh, 'Узнать сроки ВНЖ — Наталья ~январь (пример)', { kind: 'task', priority: 'P2', due_date: rel(45) });
  const customs = mk(vnzh, 'Растаможка/замена МХ5 (пример)', { kind: 'task', priority: 'P3' });
  core.addLink(db, dResid, customs, 'blocks');

  // Жизнь: поперечная связь семья → финансовое решение
  const fam = cat(db, 'Семья', 'Жизнь');
  const consult = mk(fam, 'Консультация по договору (пример)', { kind: 'task', priority: 'P1', due_date: rel(9) });
  const dHalf = mk(fam, 'Половину от продажи — Наталье? (пример)', { kind: 'decision' });
  core.addLink(db, consult, dHalf, 'blocks');
  mk(cat(db, 'Здоровье', 'Жизнь'), 'Записаться к стоматологу (пример)',
    { kind: 'task', priority: 'P2', due_date: rel(3) });
  mk(cat(db, 'Отдых', 'Жизнь'), 'Уикенд в горах в июле (пример)', { kind: 'idea' });

  // Работа
  mk(cat(db, 'Проекты', 'Работа'), 'План квартала команде (пример)',
    { kind: 'task', priority: 'P1', due_date: rel(2) });

  // Тревоги и глобальное
  mk(cat(db, 'Налоги', 'Тревоги'), 'Боюсь ошибиться с налоговым резидентством (пример)', { kind: 'worry' });
  const glob = cat(db, 'Глобальные цели');
  mk(glob, 'Жить у моря, работать на себя (пример)');
  mk(glob, 'НЕ СПЕШИМ до 2028 — про МХ5 (пример)', { kind: 'principle' });
}

// ===== Рутины со временем и историей для стриков =====
function seedRoutines(db) {
  if (db.prepare('SELECT count(*) AS c FROM routines').get().c > 0) return;
  life.addRoutine(db, { name: 'Таблетка (пример)', slot: 'утро', time: '08:00' });
  life.addRoutine(db, { name: 'Чтение 20 стр (пример)', slot: 'день' });
  life.addRoutine(db, { name: 'Отжимания 3×15 (пример)', slot: 'вечер' });
  life.addRoutine(db, { name: 'Миноксидил (пример)', slot: 'вечер', time: '21:00' });
  const tabl = db.prepare(`SELECT id FROM routines WHERE name LIKE 'Таблетка%'`).get().id;
  const mino = db.prepare(`SELECT id FROM routines WHERE name LIKE 'Миноксидил%'`).get().id;
  for (const d of [rel(-1), rel(-2), rel(-3)])
    db.prepare('INSERT OR IGNORE INTO routine_log(routine_id, date) VALUES(?,?)').run(tabl, d);
  db.prepare('INSERT OR IGNORE INTO routine_log(routine_id, date) VALUES(?,?)').run(mino, rel(-1));
}

// ===== События календаря =====
function seedEvents(db) {
  if (db.prepare('SELECT count(*) AS c FROM events').get().c > 0) return;
  cal.addEvent(db, { title: 'Созвон с бухгалтером (пример)', date: rel(1), time: '14:00' });
  cal.addEvent(db, { title: 'Встреча с юристом (пример)', date: rel(4), time: '11:00' });
  cal.addEvent(db, { title: 'Падл-турнир (пример)', date: rel(9) });
}

// ===== Расходы/доходы текущего месяца =====
function seedTx(db) {
  if (db.prepare('SELECT count(*) AS c FROM transactions').get().c > 0) return;
  const monthStart = iso(new Date()).slice(0, 8) + '01';
  const day = n => { const d = rel(-n); return d < monthStart ? monthStart : d; };
  const rows = [
    [1, 'еда', 12.5, 'обед'], [2, 'еда', 38, 'продукты'], [3, 'авто', 45, 'бензин'],
    [4, 'развлечения', 25, 'падл-корт'], [5, 'быт', 19, 'химия'], [6, 'еда', 22, 'ужин'],
    [7, 'подписки', 9.99, 'iCloud'], [8, 'авто', 120, 'мойка+мелочи'], [9, 'развлечения', 30, 'кино'],
  ];
  for (const [n, category, amount, note] of rows)
    fin.addTx(db, { date: day(n), category, amount, note: note + ' (пример)' });
  fin.addTx(db, { date: day(8), direction: 'income', category: 'зарплата', amount: 4200, note: 'аванс (пример)' });
}

// ===== Долги =====
function seedDebts(db) {
  if (db.prepare('SELECT count(*) AS c FROM debts').get().c > 0) return;
  fin.addDebt(db, { name: 'Дима за падл-корты (пример)', amount: 60, direction: 'owed_to_me', due_date: rel(-9) });
  fin.addDebt(db, { name: 'Брату за билеты (пример)', amount: 500, currency: '$', direction: 'i_owe', due_date: rel(20) });
}

// ===== Макро и FIRE =====
function seedMacroFire(db) {
  if (db.prepare('SELECT count(*) AS c FROM macro_notes').get().c === 0)
    fin.addMacro(db, { phase: 'пик', thesis: 'Жду коррекции: кэш наращиваю, докупки лесенкой (пример)' });
  if (fin.getSetting(db, 'fire_target') == null) {
    fin.setSetting(db, 'fire_target', '950000');
    fin.setSetting(db, 'fire_return_pct', '5');
    fin.setSetting(db, 'fire_monthly_savings', '3000');
  }
  if (fin.getSetting(db, 'activity_month') == null)
    fin.setSetting(db, 'activity_month', '🎾 Июнь — падл');
}

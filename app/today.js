import { calendar } from './cal.js';
import { listFin } from './fin.js';

const iso = d => d.toISOString().slice(0, 10);

export function buildToday(db) {
  const today = iso(new Date());
  const weekEnd = iso(new Date(Date.now() + 7 * 864e5));

  // задачи из роадмапа
  const taskRows = st => db.prepare(`
    SELECT id, title, kind, priority, due_date FROM nodes
    WHERE kind IN ('task','decision') AND status IN ('todo','open') AND ${st}
    ORDER BY priority IS NULL, priority, due_date`).all(today);
  const overdue = taskRows(`due_date < ?`);
  const dueToday = taskRows(`due_date = ?`);

  // лента недели: текущий + следующий месяц, отфильтрованные по диапазону
  const ym = today.slice(0, 7);
  const [y, m] = ym.split('-').map(Number);
  const nextYm = new Date(Date.UTC(y, m, 1)).toISOString().slice(0, 7);
  const seen = new Set();
  const week = [...calendar(db, ym).items, ...calendar(db, nextYm).items]
    .filter(i => i.date > today && i.date <= weekEnd && !i.done)
    .filter(i => { const k = i.type + ':' + i.id + ':' + i.date; return !seen.has(k) && seen.add(k); });

  const fin = listFin(db);
  const debtsOverdue = [
    ...fin.debts.filter(d => d.overdue_days > 0),
    ...fin.loans.filter(l => l.overdue_days > 0)
      .map(l => ({ id: 'loan' + l.id, name: l.name + ' (займ из портфеля)', amount: l.value,
                   currency: l.currency, direction: 'owed_to_me', overdue_days: l.overdue_days })),
  ];

  const doneWeek = db.prepare(`
    SELECT count(*) AS c FROM nodes
    WHERE status IN ('done','accepted') AND updated_at >= datetime('now','-7 days')`).get().c;
  const real = db.prepare('SELECT count(*) AS c FROM nodes WHERE is_category = 0').get().c;
  const typed = db.prepare('SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND kind IS NOT NULL').get().c;
  const inboxCat = db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%Инбокс%'`).get();
  const inbox = inboxCat
    ? db.prepare('SELECT count(*) AS c FROM nodes WHERE parent_id = ?').get(inboxCat.id).c : 0;

  return {
    date: today,
    overdue, dueToday, week, debtsOverdue, doneWeek,
    inboxId: inboxCat?.id ?? null, inbox,
    progress: { typed, total: real },
    fire: fin.fire?.target ? { pct: fin.fire.progressPct } : null,
    portfolioDelta: fin.snapshotDelta,
  };
}

import { calendar } from './cal.js';
import { listFin, getSetting } from './fin.js';
import { listRoutines, listPeople, sortRoutines } from './life.js';

const iso = d => d.toISOString().slice(0, 10);

// «Движение недели»: закрытое за 7 дней, сгруппированное по корневым категориям
function movement(db) {
  const nodes = db.prepare('SELECT id, parent_id, title, is_category FROM nodes').all();
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const rootOf = n => {
    let cur = n;
    while (cur.parent_id && byId[cur.parent_id]) {
      const p = byId[cur.parent_id];
      if (p.is_category && !p.parent_id) return p.title;
      cur = p;
    }
    return cur.is_category ? cur.title : 'прочее';
  };
  const done = db.prepare(`
    SELECT id FROM nodes WHERE is_category = 0
      AND status IN ('done','accepted') AND updated_at >= datetime('now','-7 days')`).all();
  const byCat = {};
  for (const d of done) byCat[rootOf(byId[d.id])] = (byCat[rootOf(byId[d.id])] ?? 0) + 1;
  return {
    total: done.length,
    top: Object.entries(byCat).sort((a, b) => b[1] - a[1]).slice(0, 3),
  };
}

export function buildToday(db) {
  const today = iso(new Date());
  const tomorrow = iso(new Date(Date.now() + 864e5));
  const weekEnd = iso(new Date(Date.now() + 7 * 864e5));

  const taskRows = st => db.prepare(`
    SELECT id, title, kind, priority, due_date FROM nodes
    WHERE kind IN ('task','decision') AND status IN ('todo','open') AND ${st}
    ORDER BY priority IS NULL, priority, due_date`).all(today);
  const overdue = taskRows(`due_date < ?`);
  const dueToday = taskRows(`due_date = ?`);

  // лента: текущий + следующий месяц
  const ym = today.slice(0, 7);
  const [y, m] = ym.split('-').map(Number);
  const nextYm = new Date(Date.UTC(y, m, 1)).toISOString().slice(0, 7);
  const seen = new Set();
  const all = [...calendar(db, ym).items, ...calendar(db, nextYm).items]
    .filter(i => { const k = i.type + ':' + i.id + ':' + i.date; return !seen.has(k) && seen.add(k); });

  const week = all.filter(i => i.date > today && i.date <= weekEnd && !i.done);
  const events = all.filter(i => i.type === 'event' && (i.date === today || i.date === tomorrow));
  const payments7 = all.filter(i => i.type === 'money' && i.date >= today && i.date <= weekEnd);

  const fin = listFin(db);
  const debtsOverdue = [
    ...fin.debts.filter(d => d.overdue_days > 0),
    ...fin.loans.filter(l => l.overdue_days > 0)
      .map(l => ({ id: 'loan' + l.id, name: l.name + ' (займ из портфеля)', amount: l.value,
                   currency: l.currency, direction: 'owed_to_me', overdue_days: l.overdue_days })),
  ];

  const people = listPeople(db);
  const real = db.prepare('SELECT count(*) AS c FROM nodes WHERE is_category = 0').get().c;
  const typed = db.prepare('SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND kind IS NOT NULL').get().c;
  const inboxCat = db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%Инбокс%'`).get();
  const inbox = inboxCat
    ? db.prepare('SELECT count(*) AS c FROM nodes WHERE parent_id = ?').get(inboxCat.id).c : 0;

  return {
    date: today,
    activityMonth: getSetting(db, 'activity_month', null),
    routines: sortRoutines(listRoutines(db)),
    overdue, dueToday, week, events,
    zones: { paymentsWeek: payments7.length, debtsOverdue: debtsOverdue.length },
    people: {
      birthdays: people.filter(p => p.days_to_birthday != null && p.days_to_birthday <= 30)
        .sort((a, b) => a.days_to_birthday - b.days_to_birthday).slice(0, 5),
      overdueContacts: people.filter(p => p.overdue_contact > 0)
        .sort((a, b) => b.overdue_contact - a.overdue_contact).slice(0, 5),
    },
    movement: movement(db),
    debtsOverdue,
    inboxId: inboxCat?.id ?? null, inbox,
    progress: { typed, total: real },
  };
}

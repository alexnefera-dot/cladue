import { addMonths } from './fin.js';
import { birthdays } from './life.js';

// ===== События =====
export function addEvent(db, b) {
  db.prepare('INSERT INTO events(title, date, time, recur, note) VALUES(?,?,?,?,?)')
    .run(b.title, b.date, b.time ?? null, b.recur ?? 'none', b.note ?? '');
}
export function patchEvent(db, id, b) {
  for (const k of ['title', 'date', 'time', 'recur', 'note'])
    if (k in b) db.prepare(`UPDATE events SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delEvent(db, id) { db.prepare('DELETE FROM events WHERE id = ?').run(id); }

// Закрыть/открыть конкретную дату события («выполнено»), не удаляя само событие.
export function toggleEventDone(db, id, date) {
  const has = db.prepare('SELECT 1 FROM event_done WHERE event_id = ? AND date = ?').get(id, date);
  if (has) db.prepare('DELETE FROM event_done WHERE event_id = ? AND date = ?').run(id, date);
  else db.prepare('INSERT OR IGNORE INTO event_done(event_id, date) VALUES(?,?)').run(id, date);
  return { done: !has };
}

// Повторы в диапазоне [first..last]
function occurrences(startDate, recur, first, last) {
  if (!startDate) return [];
  if (recur === 'none' || !recur) return startDate >= first && startDate <= last ? [startDate] : [];
  const out = [];
  let d = startDate;
  // отматываем максимум на 50 лет вперёд от стартовой даты
  for (let i = 0; i < 2700 && d <= last; i++) {
    if (d >= first) out.push(d);
    d = recur === 'weekly'
      ? new Date(Date.parse(d) + 7 * 864e5).toISOString().slice(0, 10)
      : addMonths(d, recur === 'yearly' ? 12 : 1);
  }
  return out;
}

// Единая лента месяца: задачи + шаги + обязательства + события
export function calendar(db, ym) {
  if (!/^\d{4}-\d{2}$/.test(ym)) throw new Error('month format: YYYY-MM');
  const [y, m] = ym.split('-').map(Number);
  const first = `${ym}-01`;
  const last = `${ym}-${String(new Date(Date.UTC(y, m, 0)).getUTCDate()).padStart(2, '0')}`;
  const items = [];

  for (const t of db.prepare(`
    SELECT id, title, kind, status, priority, due_date, due_time FROM nodes
    WHERE due_date BETWEEN ? AND ? AND kind IN ('task','decision')`).all(first, last))
    items.push({ date: t.due_date, type: 'task', id: t.id, title: t.title,
                 done: ['done', 'accepted'].includes(t.status), kind: t.kind, priority: t.priority, time: t.due_time });

  // шаги с привязанной задачей в календарь не попадают — их представляет сама задача
  for (const s of db.prepare(`SELECT * FROM steps WHERE planned_date BETWEEN ? AND ? AND task_id IS NULL`).all(first, last))
    items.push({ date: s.planned_date, type: 'step', id: s.id,
                 title: ({ buy: 'Купить', sell: 'Продать', transfer: 'Перевод' }[s.kind] ?? s.kind) + ': ' + s.title,
                 done: s.status === 'done', amount: s.amount });

  for (const o of db.prepare(`SELECT * FROM obligations WHERE next_date IS NOT NULL`).all())
    for (const d of occurrences(o.next_date, o.period === 'once' ? 'none' : o.period, first, last))
      items.push({ date: d, type: 'money', id: o.id, title: o.name, amount: o.amount,
                   currency: o.currency, okind: o.kind });

  const eventDone = new Set(db.prepare('SELECT event_id, date FROM event_done').all().map(r => r.event_id + ':' + r.date));
  for (const e of db.prepare('SELECT * FROM events').all())
    for (const d of occurrences(e.date, e.recur, first, last))
      items.push({ date: d, type: 'event', id: e.id, title: e.title, time: e.time, recur: e.recur,
                   done: eventDone.has(e.id + ':' + d) });

  // практики в календарь не проецируются (по решению пользователя):
  // они живут в Психологии и на дашборде «Сегодня»

  // дни рождения людей — каждый год, удаляются только в разделе «Люди»
  for (const p of birthdays(db)) {
    const d = `${ym}-${p.mmdd.slice(3)}`;
    if (p.mmdd.slice(0, 2) === ym.slice(5) && d >= first && d <= last)
      items.push({ date: d, type: 'event', id: 'p' + p.id, title: '🎂 ' + p.name, recur: 'yearly', bday: true });
  }

  items.sort((a, b) => a.date < b.date ? -1 : a.date > b.date ? 1 : (a.time ?? '') < (b.time ?? '') ? -1 : 1);
  return { month: ym, first, last, items };
}

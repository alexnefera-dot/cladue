const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;   // локальная дата: сутки переключаются в твою полночь, не по UTC
const today = () => iso(new Date());

// ===== Рутины =====
export function listRoutines(db) {
  const t = today();
  const doneToday = new Set(db.prepare('SELECT routine_id FROM routine_log WHERE date = ?').all(t).map(r => r.routine_id));
  return db.prepare('SELECT * FROM routines ORDER BY ord, id').all()
    .map(r => ({ ...r, done: doneToday.has(r.id), streak: routineStreak(db, r.id) }));
}

export function routineStreak(db, id) {
  const dates = new Set(db.prepare('SELECT date FROM routine_log WHERE routine_id = ?').all(id).map(r => r.date));
  let streak = 0;
  let d = new Date();
  if (!dates.has(iso(d))) d = new Date(Date.now() - 864e5); // сегодня ещё не отмечено — считаем от вчера
  while (dates.has(iso(d)) && streak < 3650) { streak++; d = new Date(d.getTime() - 864e5); }
  return streak;
}

export function addRoutine(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM routines').get().o;
  db.prepare('INSERT INTO routines(name, slot, time, ord, note) VALUES(?,?,?,?,?)')
    .run(b.name, b.slot ?? 'утро', b.time ?? null, ord, b.note ?? '');
}
export function patchRoutine(db, id, b) {
  for (const k of ['name', 'slot', 'time', 'note'])
    if (k in b) db.prepare(`UPDATE routines SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delRoutine(db, id) { db.prepare('DELETE FROM routines WHERE id = ?').run(id); }

// чек на сегодня (повторный клик снимает); пропуск не висит долгом
export function toggleRoutineToday(db, id) {
  const t = today();
  const has = db.prepare('SELECT 1 AS x FROM routine_log WHERE routine_id = ? AND date = ?').get(id, t);
  if (has) db.prepare('DELETE FROM routine_log WHERE routine_id = ? AND date = ?').run(id, t);
  else db.prepare('INSERT INTO routine_log(routine_id, date) VALUES(?,?)').run(id, t);
  return !has;
}

// Приоритет на дашборде: невыполненные раньше выполненных; с временем — раньше и по времени;
// без времени — по слоту (утро → день → вечер). Просроченное время помечается due=true.
const SLOT_ORD = { 'утро': 0, 'день': 1, 'вечер': 2 };

export function sortRoutines(rows, now = new Date()) {
  const hhmm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  return rows
    .map(r => ({ ...r, due: !r.done && !!r.time && r.time <= hhmm }))
    .sort((a, b) => {
      if (a.done !== b.done) return a.done ? 1 : -1;
      if (!!a.time !== !!b.time) return a.time ? -1 : 1;
      if (a.time && b.time && a.time !== b.time) return a.time < b.time ? -1 : 1;
      return (SLOT_ORD[a.slot] ?? 9) - (SLOT_ORD[b.slot] ?? 9) || a.ord - b.ord;
    });
}

// ===== Люди =====
const mmdd = b => {
  const m = String(b ?? '').match(/(\d{2})-(\d{2})$/);
  return m ? `${m[1]}-${m[2]}` : null;
};

export function daysToBirthday(birthday, now = new Date()) {
  const md = mmdd(birthday);
  if (!md) return null;
  const [m, d] = md.split('-').map(Number);
  const y = now.getFullYear();
  let next = new Date(Date.UTC(y, m - 1, d));
  const t = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
  if (next < t) next = new Date(Date.UTC(y + 1, m - 1, d));
  return Math.round((next - t) / 864e5);
}

export function listPeople(db) {
  const t = today();
  // связи с задачами: записи, в названии которых упоминается имя (как в радаре)
  const nodes = db.prepare(`SELECT id, title FROM nodes WHERE is_category = 0 AND status IS NOT 'done'`).all();
  const normName = s => s.toLowerCase();
  return db.prepare('SELECT * FROM people ORDER BY name').all().map(p => ({
    ...p,
    days_to_birthday: daysToBirthday(p.birthday),
    overdue_contact: p.rhythm_days && p.last_contact
      ? Math.max(0, Math.floor((Date.parse(t) - Date.parse(p.last_contact)) / 864e5) - p.rhythm_days)
      : (p.rhythm_days && !p.last_contact ? 1 : null),  // ритм задан, контакта не было — пора
    since_contact: p.last_contact ? Math.floor((Date.parse(t) - Date.parse(p.last_contact)) / 864e5) : null,
    tasks: nodes.filter(n => normName(n.title).includes(normName(p.name))).slice(0, 3),
    logs: db.prepare('SELECT date, note FROM contact_log WHERE person_id = ? ORDER BY date DESC, id DESC LIMIT 3').all(p.id),
  }));
}

export function addPerson(db, b) {
  db.prepare('INSERT INTO people(name, birthday, rhythm_days, last_contact, note) VALUES(?,?,?,?,?)')
    .run(b.name, b.birthday ?? null, b.rhythm_days ?? null, b.last_contact ?? null, b.note ?? '');
}
export function patchPerson(db, id, b) {
  for (const k of ['name', 'birthday', 'rhythm_days', 'last_contact', 'tags', 'note'])
    if (k in b) db.prepare(`UPDATE people SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delPerson(db, id) { db.prepare('DELETE FROM people WHERE id = ?').run(id); }
export function contacted(db, id, note) {
  db.prepare('UPDATE people SET last_contact = ? WHERE id = ?').run(today(), id);
  if (note?.trim())
    db.prepare('INSERT INTO contact_log(person_id, note) VALUES(?,?)').run(id, note.trim());
}

// 5 тестовых людей с датами относительно сегодня (льётся и поверх своих, но один раз)
export function seedPeople(db) {
  if (db.prepare(`SELECT count(*) AS c FROM people WHERE name LIKE '%(пример)%'`).get().c > 0) return;
  const rel = n => iso(new Date(Date.now() + n * 864e5));
  const bd = n => rel(n).slice(5);   // MM-DD через n дней
  const add = (name, b) => {
    db.prepare('INSERT INTO people(name, birthday, rhythm_days, last_contact, tags) VALUES(?,?,?,?,?)')
      .run(name, b.birthday ?? null, b.rhythm ?? null, b.last ?? null, b.tags ?? '');
    return db.prepare('SELECT last_insert_rowid() AS id').get().id;
  };
  add('Мама (пример)', { birthday: bd(9), rhythm: 7, last: rel(-2), tags: 'семья' });
  add('Наталья (пример)', { birthday: bd(3), rhythm: 7, last: rel(-1), tags: 'семья, переезд' });
  add('Игорь (пример)', { birthday: bd(21), tags: 'авто-рынок' });
  const dima = add('Дима (пример)', { birthday: bd(120), rhythm: 30, last: rel(-42), tags: 'падл, авто-рынок' });
  db.prepare('INSERT INTO contact_log(person_id, date, note) VALUES(?,?,?)')
    .run(dima, rel(-42), 'советовал смотреть рынок осенью');
  add('Бабушка (пример)', { birthday: bd(-40), rhythm: 14, last: rel(-21), tags: 'семья' });
}

// ДР для проекции в календарь: [{name, mmdd}]
export function birthdays(db) {
  return db.prepare('SELECT id, name, birthday FROM people WHERE birthday IS NOT NULL').all()
    .map(p => ({ id: p.id, name: p.name, mmdd: mmdd(p.birthday) }))
    .filter(p => p.mmdd);
}

// ===== Чек-ин дня =====
export function setCheckin(db, mood, note = '', date = today()) {
  const m = Math.max(1, Math.min(3, Math.round(+mood)));
  db.prepare(`INSERT INTO checkins(date, mood, note) VALUES(?,?,?)
    ON CONFLICT(date) DO UPDATE SET mood = excluded.mood, note = excluded.note`).run(date, m, note);
}
export function checkins(db, days = 30) {
  return db.prepare(`SELECT * FROM checkins WHERE date >= date('now','localtime', ?) ORDER BY date DESC`)
    .all(`-${days} days`);
}

// ===== Свои метрики =====
export function addMetric(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM metrics').get().o;
  db.prepare('INSERT INTO metrics(name, type, unit, ord, polarity) VALUES(?,?,?,?,?)')
    .run(b.name, b.type ?? 'number', b.unit ?? '', ord, b.polarity ?? 'plus');
}
export function patchMetric(db, id, b) {
  for (const k of ['name', 'type', 'unit', 'polarity'])
    if (k in b) db.prepare(`UPDATE metrics SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delMetric(db, id) { db.prepare('DELETE FROM metrics WHERE id = ?').run(id); }

export function setMetricValue(db, id, value, date = today()) {
  db.prepare(`INSERT INTO metric_log(metric_id, date, value) VALUES(?,?,?)
    ON CONFLICT(metric_id, date) DO UPDATE SET value = excluded.value`).run(id, date, +value);
}

export function listMetrics(db, days = 14) {
  const t = today();
  return db.prepare('SELECT * FROM metrics ORDER BY ord, id').all().map(mt => {
    const hist = db.prepare(`
      SELECT date, value FROM metric_log WHERE metric_id = ? AND date >= date('now','localtime', ?)
      ORDER BY date`).all(mt.id, `-${days} days`);
    return {
      ...mt,
      today: hist.find(h => h.date === t)?.value ?? null,
      history: hist,
      total: db.prepare('SELECT count(*) AS c FROM metric_log WHERE metric_id = ?').get(mt.id).c,
    };
  });
}

// ===== Тепловая карта рутин: выполнено/всего по дням =====
export function routineHeatmap(db, days = 112) {
  const total = db.prepare('SELECT count(*) AS c FROM routines').get().c;
  const rows = db.prepare(`
    SELECT date, count(*) AS done FROM routine_log
    WHERE date >= date('now','localtime', ?) GROUP BY date`).all(`-${days} days`);
  const byDate = Object.fromEntries(rows.map(r => [r.date, r.done]));
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = iso(new Date(Date.now() - i * 864e5));
    out.push({ date: d, done: byDate[d] ?? 0, total });
  }
  return out;
}

// ===== Итоги по месяцам: краткая статистика для динамики (текущий — первым) =====
export function monthlyStats(db, months = 6) {
  const defs = db.prepare('SELECT id, name, type, unit, polarity FROM metrics ORDER BY ord, id').all();
  const now = new Date();
  const out = [];
  for (let i = 0; i < months; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const metrics = defs.map(mt => ({
      id: mt.id, name: mt.name, type: mt.type, unit: mt.unit, polarity: mt.polarity,
      // отметки — сколько раз за месяц; числа — среднее за месяц
      value: mt.type === 'bool'
        ? db.prepare(`SELECT count(*) AS v FROM metric_log WHERE metric_id = ? AND value > 0 AND substr(date,1,7) = ?`).get(mt.id, ym).v || null
        : db.prepare(`SELECT ROUND(AVG(value),1) AS v FROM metric_log WHERE metric_id = ? AND substr(date,1,7) = ?`).get(mt.id, ym).v,
    }));
    const mood = db.prepare(`SELECT ROUND(AVG(mood),1) AS v FROM checkins WHERE substr(date,1,7) = ?`).get(ym).v;
    const tasksDone = db.prepare(`SELECT count(*) AS c FROM nodes
      WHERE is_category = 0 AND status IN ('done','accepted') AND substr(updated_at,1,7) = ?`).get(ym).c;
    const routinesDone = db.prepare(`SELECT count(*) AS c FROM routine_log WHERE substr(date,1,7) = ?`).get(ym).c;
    const empty = mood == null && !tasksDone && !routinesDone && metrics.every(m => m.value == null);
    if (i === 0 || !empty) out.push({ ym, metrics, mood, tasksDone, routinesDone });
  }
  return out;
}

// ===== Импорт старого трекинга (xlsx пользователя, разово; данные в import/track2026.json) =====
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const normName = s => String(s).toLowerCase().replace(/\s+/g, '');

export function importOldTracking(db) {
  if (db.prepare(`SELECT value FROM settings WHERE key = 'track_import_v1'`).get()?.value === '1') return;
  let payload;
  try {
    payload = JSON.parse(readFileSync(fileURLToPath(new URL('./import/track2026.json', import.meta.url)), 'utf8'));
  } catch { return; }   // файла нет — нечего импортировать
  // колонки: совпадение по имени без пробелов, недостающие создаются отметками
  const byNorm = {};
  for (const m of db.prepare('SELECT id, name FROM metrics').all()) byNorm[normName(m.name)] = m.id;
  for (const name of payload.columns) {
    if (byNorm[normName(name)]) continue;
    addMetric(db, { name, type: 'bool' });
    byNorm[normName(name)] = db.prepare('SELECT id FROM metrics WHERE name = ?').get(name).id;
  }
  const ins = db.prepare(`INSERT INTO metric_log(metric_id, date, value) VALUES(?,?,1)
    ON CONFLICT(metric_id, date) DO NOTHING`);
  let n = 0;
  for (const [name, date] of payload.marks) {
    const id = byNorm[normName(name)];
    if (id) { ins.run(id, date); n++; }
  }
  // известные регрессы пользователя — красные ✗, а не зелёные ✓
  db.prepare(`UPDATE metrics SET polarity = 'minus' WHERE name IN
    ('Ютуб при работе', 'Тревога (не в 20:00)', 'Тревога(не в 20:00)',
     'Приоритеная задача не выбрана', 'Подъем не в 10')`).run();
  db.prepare(`INSERT INTO settings(key, value) VALUES('track_import_v1','1')
    ON CONFLICT(key) DO UPDATE SET value = '1'`).run();
  return { imported: n, months: payload.months };
}

// перестановка колонок дневника (drag&drop заголовков)
export function reorderMetric(db, id, refId, where = 'after') {
  if (id === refId) return;
  const all = db.prepare('SELECT id FROM metrics ORDER BY ord, id').all().map(r => r.id).filter(x => x !== id);
  const at = all.indexOf(refId);
  if (at === -1) throw new Error('сосед не найден');
  all.splice(at + (where === 'after' ? 1 : 0), 0, id);
  const up = db.prepare('UPDATE metrics SET ord = ? WHERE id = ?');
  all.forEach((mid, i) => up.run(i + 1, mid));
}

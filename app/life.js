const iso = d => d.toISOString().slice(0, 10);
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

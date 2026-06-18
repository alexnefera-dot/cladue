// Планировщик напоминаний: единая лента для нативных уведомлений (Mac/iPhone).
// Детерминированно собирает из данных: рутины с временем, платежи, события, ДР.
// Каждому — категория (своя озвучка в нативной оболочке) и ключ дедупликации.
import { listRoutines } from './life.js';
import { birthdays } from './life.js';

const pad = n => String(n).padStart(2, '0');
const localIso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;

export function upcomingNotifications(db, now = new Date()) {
  const today = localIso(now);
  const hhmm = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const out = [];
  const add = (category, key, title, body, at) =>
    out.push({ category, key: `${today}:${key}`, title, body, at });

  // рутины с фиксированным временем — в свой час
  for (const r of listRoutines(db))
    if (r.time && !r.done && r.time <= hhmm)
      add('routine', `routine:${r.id}`, '⏰ ' + r.name, `Рутина на ${r.time}${r.streak ? ` · стрик ${r.streak} 🔥` : ''}`, r.time);

  // платежи: за remind_days до next_date (и в сам день)
  for (const o of db.prepare('SELECT * FROM obligations WHERE next_date IS NOT NULL').all()) {
    const days = Math.ceil((Date.parse(o.next_date) - Date.parse(today)) / 864e5);
    if (days >= 0 && days <= (o.remind_days ?? 5))
      add('money', `money:${o.id}`, '◈ ' + o.name,
        days === 0 ? `Платёж сегодня · ${o.amount} ${o.currency}` : `Платёж через ${days} дн · ${o.amount} ${o.currency}`, null);
  }

  // события сегодня со временем — за час и в момент
  for (const e of db.prepare(`SELECT * FROM events WHERE date = ? OR recur != 'none'`).all(today)) {
    // повторяющиеся: совпадение дня недели/числа проверяет календарь; здесь только точная дата
    if (e.date === today && e.time && e.time <= hhmm)
      add('event', `event:${e.id}`, '▦ ' + e.title, `Событие в ${e.time}`, e.time);
  }

  // дни рождения сегодня
  for (const p of birthdays(db))
    if (p.mmdd === today.slice(5))
      add('people', `bday:${p.id}`, '🎂 ' + p.name, 'День рождения сегодня — поздравь!', null);

  return out;
}

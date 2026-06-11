import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, ensurePortfolio, ensureRates } from '../db.js';
import * as life from '../life.js';
import * as cal from '../cal.js';
import { buildToday } from '../today.js';
import * as core from '../core.js';

const iso = d => d.toISOString().slice(0, 10);
function freshDb() {
  const db = createDb(':memory:');
  seed(db); ensurePortfolio(db); ensureRates(db);
  return db;
}

test('рутины: чек на сегодня, повторный клик снимает, стрик считается', () => {
  const db = freshDb();
  life.addRoutine(db, { name: 'Таблетка', slot: 'утро' });
  const r = life.listRoutines(db)[0];
  assert.equal(r.done, false);
  assert.equal(life.toggleRoutineToday(db, r.id), true);
  // вчера и позавчера тоже отмечены — стрик 3
  db.prepare('INSERT INTO routine_log(routine_id, date) VALUES(?,?)').run(r.id, iso(new Date(Date.now() - 864e5)));
  db.prepare('INSERT INTO routine_log(routine_id, date) VALUES(?,?)').run(r.id, iso(new Date(Date.now() - 2 * 864e5)));
  assert.equal(life.listRoutines(db)[0].streak, 3);
  assert.equal(life.toggleRoutineToday(db, r.id), false, 'повторный клик снял отметку');
  assert.equal(life.listRoutines(db)[0].streak, 2, 'сегодня не отмечено — стрик от вчера');
});

test('люди: дни до ДР и просроченный контакт-ритм', () => {
  const db = freshDb();
  const in10 = new Date(Date.now() + 10 * 864e5);
  const bd = `${String(in10.getMonth() + 1).padStart(2, '0')}-${String(in10.getDate()).padStart(2, '0')}`;
  life.addPerson(db, { name: 'Мама', birthday: bd, rhythm_days: 7, last_contact: iso(new Date(Date.now() - 20 * 864e5)) });
  life.addPerson(db, { name: 'Дима', rhythm_days: 30, last_contact: iso(new Date()) });
  const [dima, mama] = [life.listPeople(db).find(p => p.name === 'Дима'), life.listPeople(db).find(p => p.name === 'Мама')];
  assert.equal(mama.days_to_birthday, 10);
  assert.equal(mama.overdue_contact, 13, '20 дней молчания при ритме 7');
  assert.equal(dima.overdue_contact, 0, 'связались сегодня');
  life.contacted(db, mama.id);
  assert.equal(life.listPeople(db).find(p => p.name === 'Мама').overdue_contact, 0);
});

test('ДР людей проецируются в календарь каждый год, без кнопки удаления события', () => {
  const db = freshDb();
  life.addPerson(db, { name: 'Мама', birthday: '1965-06-19' });
  const june26 = cal.calendar(db, '2026-06').items.filter(i => i.bday);
  const june27 = cal.calendar(db, '2027-06').items.filter(i => i.bday);
  assert.equal(june26.length, 1);
  assert.match(june26[0].title, /🎂 Мама/);
  assert.equal(june26[0].date, '2026-06-19');
  assert.equal(june27.length, 1, 'и в следующем году');
  assert.equal(cal.calendar(db, '2026-07').items.filter(i => i.bday).length, 0);
});

test('дашборд: рутины, люди, зоны и движение недели на месте; FIRE/портфеля нет', () => {
  const db = freshDb();
  life.addRoutine(db, { name: 'Отжимания', slot: 'вечер' });
  life.addPerson(db, { name: 'Дима', rhythm_days: 7, last_contact: '2020-01-01' });
  const fin2 = core.listCategories(db).find(c => c.title === 'Финансы' && !c.parent_id);
  const n = core.addChild(db, fin2.id, 'Готово на этой неделе');
  core.updateNode(db, n.id, { kind: 'task' });
  core.toggleNode(db, n.id);

  const t = buildToday(db);
  assert.equal(t.routines.length, 1);
  assert.equal(t.people.overdueContacts[0].name, 'Дима');
  assert.ok('paymentsWeek' in t.zones);
  assert.equal(t.movement.total, 1);
  assert.deepEqual(t.movement.top[0], ['Финансы', 1], 'движение сгруппировано по корневой категории');
  assert.ok(!('fire' in t), 'FIRE с дашборда убран');
  assert.ok(!('portfolioDelta' in t), 'портфель с дашборда убран');
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, ensurePortfolio, ensureRates } from '../db.js';
import * as life from '../life.js';
import * as cal from '../cal.js';
import { buildToday } from '../today.js';
import * as core from '../core.js';

const iso = d => d.toISOString().slice(0, 10);
const inboxOf = db => core.listCategories(db).find(c => c.title.includes('Инбокс'));
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

test('рутины: время хранится, дашборд сортирует по приоритету времени', () => {
  const db = freshDb();
  life.addRoutine(db, { name: 'Чтение', slot: 'вечер' });
  life.addRoutine(db, { name: 'Зарядка', slot: 'утро' });
  life.addRoutine(db, { name: 'Таблетка', slot: 'утро', time: '08:00' });
  life.addRoutine(db, { name: 'Миноксидил', slot: 'вечер', time: '21:00' });
  const tabl = life.listRoutines(db).find(r => r.name === 'Таблетка');
  life.toggleRoutineToday(db, tabl.id); // выполнена — уходит вниз

  const now = new Date(); now.setHours(12, 0);
  const sorted = life.sortRoutines(life.listRoutines(db), now);
  assert.deepEqual(sorted.map(r => r.name),
    ['Миноксидил', 'Зарядка', 'Чтение', 'Таблетка'],
    'время → слоты → выполненные в конец');
  assert.equal(sorted.find(r => r.name === 'Миноксидил').due, false, '21:00 ещё не пора в полдень');
  const evening = new Date(); evening.setHours(22, 0);
  assert.equal(life.sortRoutines(life.listRoutines(db), evening).find(r => r.name === 'Миноксидил').due,
    true, 'после 21:00 — пора');
  life.patchRoutine(db, tabl.id, { time: '07:30' });
  assert.equal(life.listRoutines(db).find(r => r.name === 'Таблетка').time, '07:30');
});

test('сид людей: 5 человек, просрочка и связи с задачами работают', () => {
  const db = freshDb();
  life.seedPeople(db);
  life.seedPeople(db);   // повторно — не дублирует
  const people = life.listPeople(db);
  assert.equal(people.length, 5);
  const dima = people.find(p => p.name.includes('Дима'));
  assert.ok(dima.overdue_contact > 0, 'Дима просрочен (42 дня при ритме 30)');
  assert.equal(dima.logs.length, 1, 'есть запись после встречи');
  const mama = people.find(p => p.name.includes('Мама'));
  assert.equal(mama.days_to_birthday, 9);
  assert.equal(mama.overdue_contact, 0);
  // связь с задачей по упоминанию имени
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  core.addChild(db, inbox.id, 'Написать Дима (пример) за условия и рынок');
  const dima2 = life.listPeople(db).find(p => p.name.includes('Дима'));
  assert.equal(dima2.tasks.length, 1);
  // «связались» с заметкой пишет лог и сбрасывает просрочку
  life.contacted(db, dima.id, 'обсудили продажу');
  const after = life.listPeople(db).find(p => p.name.includes('Дима'));
  assert.equal(after.overdue_contact, 0);
  assert.equal(after.logs[0].note, 'обсудили продажу');
});

test('чек-ин: upsert за день, история, зажим 1..3', () => {
  const db = freshDb();
  life.setCheckin(db, 2, 'обычный день');
  life.setCheckin(db, 3, 'разогнался');     // перезапись сегодня
  life.setCheckin(db, 9, '', iso(new Date(Date.now() - 864e5)));
  const rows = life.checkins(db);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].mood, 3);
  assert.equal(rows[0].note, 'разогнался');
  assert.equal(rows[1].mood, 3, 'зажат в 1..3');
});

test('метрики: создание, значение за день перезаписывается, история и типы', () => {
  const db = freshDb();
  life.addMetric(db, { name: 'Кофе', type: 'number', unit: 'чашек' });
  life.addMetric(db, { name: 'Падл', type: 'bool' });
  const [coffee, padel] = life.listMetrics(db);
  life.setMetricValue(db, coffee.id, 2);
  life.setMetricValue(db, coffee.id, 3);                                   // upsert
  life.setMetricValue(db, coffee.id, 1, iso(new Date(Date.now() - 864e5)));
  life.setMetricValue(db, padel.id, 1);
  const after = life.listMetrics(db);
  const c = after.find(x => x.id === coffee.id);
  assert.equal(c.today, 3);
  assert.equal(c.total, 2);
  assert.deepEqual(c.history.map(h => h.value), [1, 3]);
  assert.equal(after.find(x => x.id === padel.id).today, 1);
  life.delMetric(db, coffee.id);
  assert.equal(life.listMetrics(db).length, 1);
});

test('тепловая карта рутин: считает выполнено/всего по дням', () => {
  const db = freshDb();
  life.addRoutine(db, { name: 'А' });
  life.addRoutine(db, { name: 'Б' });
  const [a, b] = life.listRoutines(db);
  life.toggleRoutineToday(db, a.id);
  life.toggleRoutineToday(db, b.id);
  db.prepare('INSERT INTO routine_log(routine_id, date) VALUES(?,?)').run(a.id, iso(new Date(Date.now() - 864e5)));
  const heat = life.routineHeatmap(db, 7);
  assert.equal(heat.length, 7);
  assert.equal(heat.at(-1).done, 2, 'сегодня обе');
  assert.equal(heat.at(-2).done, 1, 'вчера одна');
  assert.equal(heat.at(-1).total, 2);
});

test('итоги по месяцам: отметки считаются, числа усредняются, настроение и рутины входят', () => {
  const db = freshDb();
  life.addMetric(db, { name: 'Книга', type: 'bool' });
  life.addMetric(db, { name: 'Вес', type: 'number', unit: 'кг' });
  const [book, weight] = db.prepare('SELECT id FROM metrics ORDER BY id').all().map(r => r.id);
  const today = new Date();
  const d = n => iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - n));
  life.setMetricValue(db, book, 1, d(0));
  life.setMetricValue(db, book, 1, d(1));
  life.setMetricValue(db, book, 0, d(2));          // снятая отметка не считается
  life.setMetricValue(db, weight, 84, d(1));
  life.setMetricValue(db, weight, 82, d(0));
  life.setCheckin(db, 3, '', d(0));
  life.setCheckin(db, 1, '', d(1));
  life.addRoutine(db, { name: 'А' });
  life.toggleRoutineToday(db, life.listRoutines(db)[0].id);
  const stats = life.monthlyStats(db, 2);
  const cur = stats[0];
  // все значения могли уехать в прошлый месяц только на стыке — тогда смотрим его
  const mo = cur.metrics.some(m => m.value != null) ? cur : stats[1];
  assert.equal(mo.metrics.find(m => m.name === 'Книга').value >= 1, true, 'отметки за месяц');
  assert.ok(mo.metrics.find(m => m.name === 'Вес').value >= 82, 'среднее число');
  assert.ok(mo.mood >= 1 && mo.mood <= 3, 'среднее настроение');
  assert.ok(stats.reduce((s, x) => s + x.routinesDone, 0) >= 1, 'рутины в итогах');
});

test('дашборд: недельные цели и чек-ин в payload', () => {
  const db = freshDb();
  const inbox = inboxOf(db);
  const mk = (t, due) => { const n = core.addChild(db, inbox.id, t); core.updateNode(db, n.id, { kind: 'task', due_date: due }); return n; };
  const monday = iso(new Date(Date.now() - ((new Date().getDay() + 6) % 7) * 864e5));
  mk('На этой неделе 1', monday);
  const d2 = mk('На этой неделе 2', iso(new Date(Date.parse(monday) + 4 * 864e5)));
  core.toggleNode(db, d2.id);
  mk('Через месяц', iso(new Date(Date.now() + 30 * 864e5)));
  life.setCheckin(db, 3, 'хороший');
  const t = buildToday(db);
  assert.equal(t.weekGoals.total, 2);
  assert.equal(t.weekGoals.done, 1);
  assert.equal(t.checkin.mood, 3);
});

test('импорт старого трекинга: колонки создаются, история ложится, повторно не льётся', () => {
  const db = freshDb();
  const r = life.importOldTracking(db);
  assert.ok(r.imported >= 200, 'отметки из xlsx: ' + r.imported);
  const names = db.prepare('SELECT name FROM metrics').all().map(x => x.name);
  for (const n of ['Зал', 'Переезд', 'Решение сложных задач жизни', 'Приоритеная задача не выбрана'])
    assert.ok(names.includes(n), 'новая колонка: ' + n);
  assert.ok(!names.includes('Подъем не в 10'), 'исключённая колонка не вернулась');
  const total = db.prepare('SELECT count(*) AS c FROM metric_log').get().c;
  assert.equal(life.importOldTracking(db), undefined, 'флаг стоит — повтор не льёт');
  assert.equal(db.prepare('SELECT count(*) AS c FROM metric_log').get().c, total);
  // история видна в итогах месяцев (январь не пустой)
  const stats = life.monthlyStats(db, 12);
  const jan = stats.find(s => s.ym.endsWith('-01'));
  assert.ok(jan && jan.metrics.some(m => m.value >= 1), 'январь в итогах');
});

test('колонки дневника переставляются drag&drop', () => {
  const db = freshDb();
  life.addMetric(db, { name: 'А', type: 'bool' });
  life.addMetric(db, { name: 'Б', type: 'bool' });
  life.addMetric(db, { name: 'В', type: 'bool' });
  const id = n => db.prepare('SELECT id FROM metrics WHERE name = ?').get(n).id;
  const order = () => db.prepare('SELECT name FROM metrics ORDER BY ord, id').all().map(r => r.name).join('');
  life.reorderMetric(db, id('В'), id('А'), 'before');
  assert.equal(order(), 'ВАБ');
  life.reorderMetric(db, id('А'), id('Б'), 'after');
  assert.equal(order(), 'ВБА');
});

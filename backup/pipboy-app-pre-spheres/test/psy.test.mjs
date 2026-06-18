import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed } from '../db.js';
import * as psy from '../psy.js';
import * as cal from '../cal.js';
import * as core from '../core.js';

const iso = d => d.toISOString().slice(0, 10);
function freshDb() { const db = createDb(':memory:'); seed(db); return db; }

test('расписание: daily, workdays и дни недели', () => {
  assert.equal(psy.occursOn('daily', '2026-06-14'), true);          // вс
  assert.equal(psy.occursOn('workdays', '2026-06-12'), true);       // пт
  assert.equal(psy.occursOn('workdays', '2026-06-13'), false);      // сб
  assert.equal(psy.occursOn('2,4', '2026-06-11'), true);            // чт
  assert.equal(psy.occursOn('2,4', '2026-06-10'), false);           // ср
  assert.equal(psy.occursOn('', '2026-06-11'), false);
});

test('практика: лог, runs, стрик по occurrence-датам', () => {
  const db = freshDb();
  psy.addPractice(db, { name: 'Тревоги', kind: 'schedule', days: 'daily', time: '19:00' });
  const p = psy.listPractices(db)[0];
  assert.equal(p.today, true);
  assert.equal(p.done, false);
  // вчера и позавчера выполнено
  psy.logPractice(db, p.id, { date: iso(new Date(Date.now() - 864e5)), note: 'ок' });
  psy.logPractice(db, p.id, { date: iso(new Date(Date.now() - 2 * 864e5)) });
  let row = psy.listPractices(db)[0];
  assert.equal(row.runs, 2);
  assert.equal(row.streak, 2, 'сегодня не отмечено — стрик от вчера');
  psy.logPractice(db, p.id, { note: 'сегодня тоже' });
  row = psy.listPractices(db)[0];
  assert.equal(row.done, true);
  assert.equal(row.streak, 3);
});

test('техника: ответы по шагам сохраняются в журнал', () => {
  const db = freshDb();
  psy.addPractice(db, { name: '7 шагов', kind: 'technique', steps: ['Чувство?', 'Намерение?'] });
  const p = psy.listPractices(db)[0];
  assert.deepEqual(p.steps, ['Чувство?', 'Намерение?']);
  psy.logPractice(db, p.id, { answers: ['тревога перед сделкой', 'хочу безопасности'] });
  const logs = psy.practiceLogs(db, p.id);
  assert.equal(logs.length, 1);
  assert.equal(logs[0].answers[1], 'хочу безопасности');
});

test('колесо: замер, перезапись в тот же день, дельта к прошлому', () => {
  const db = freshDb();
  psy.ensureWheel(db);
  const w0 = psy.wheel(db);
  assert.equal(w0.areas.length, 10);
  const [a1, a2] = w0.areas;
  psy.saveWheel(db, { [a1.id]: 6, [a2.id]: 7 }, '2026-05-01');
  psy.saveWheel(db, { [a1.id]: 5, [a2.id]: 8 });
  psy.saveWheel(db, { [a1.id]: 4 });                 // перезапись сегодня
  const w = psy.wheel(db);
  assert.equal(w.latest.scores[a1.id], 4);
  assert.equal(w.prev.scores[a1.id], 6);
  assert.equal(w.dates.length, 2, 'два замера, не три');
  psy.saveWheel(db, { [a1.id]: 99 });
  assert.equal(psy.wheel(db).latest.scores[a1.id], 10, 'оценка зажата в 1..10');
});

test('практики НЕ захламляют календарь, но дни считаются для психологии и дашборда', () => {
  const db = freshDb();
  psy.addPractice(db, { name: 'Тревоги', kind: 'schedule', days: '2,4', time: '19:00' });
  const p = psy.listPractices(db)[0];
  // в календаре практик нет — по решению пользователя
  assert.equal(cal.calendar(db, '2026-06').items.filter(i => i.type === 'practice').length, 0);
  // но occurrences живы: вт/чт июня для раздела психологии и плитки «Сегодня»
  const june = psy.monthOccurrences(db, '2026-06', '2026-06-01', '2026-06-30');
  assert.ok(june.length >= 8, 'все вт и чт июня');
  assert.ok(june.every(i => ['2', '4'].includes(String(((new Date(i.date + 'T00:00:00').getDay() + 6) % 7) + 1))));
  psy.logPractice(db, p.id, { date: '2026-06-11' });   // чт
  const done = psy.monthOccurrences(db, '2026-06', '2026-06-01', '2026-06-30')
    .find(i => i.date === '2026-06-11');
  assert.equal(done.done, true);
});

test('рабочий лог и принятые решения', () => {
  const db = freshDb();
  psy.addWork(db, 'закрыл вопрос с подрядчиком');
  assert.equal(psy.workLog(db)[0].note, 'закрыл вопрос с подрядчиком');
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  const d = core.addChild(db, inbox.id, 'Едем в город Б?');
  core.updateNode(db, d.id, { kind: 'decision' });
  core.updateNode(db, d.id, { status: 'accepted', answer: 'Да, город Б — пересмотр через 3 мес' });
  const acc = psy.acceptedDecisions(db);
  assert.equal(acc.length, 1);
  assert.match(acc[0].answer, /город Б/);
});

test('пароль раздела: установка, проверка, смена; без пароля — открыт', () => {
  const db = freshDb();
  assert.equal(psy.psyHasPass(db), false);
  assert.equal(psy.checkPsyPass(db, 'что угодно'), true, 'без пароля пускает');
  psy.setPsyPass(db, 'секрет');
  assert.equal(psy.psyHasPass(db), true);
  assert.equal(psy.checkPsyPass(db, 'не тот'), false);
  assert.equal(psy.checkPsyPass(db, 'секрет'), true);
  psy.setPsyPass(db, '');                              // снять
  assert.equal(psy.psyHasPass(db), false);
});

test('сид психологии: практики/колесо/лог, идемпотентно', () => {
  const db = freshDb();
  psy.seedPsy(db);
  psy.seedPsy(db);
  assert.equal(db.prepare(`SELECT count(*) AS c FROM practices WHERE name LIKE '%(пример)%'`).get().c, 5);
  const w = psy.wheel(db);
  assert.ok(w.latest && w.prev, 'два замера колеса');
  assert.ok(psy.workLog(db).length >= 2);
  const tech = psy.listPractices(db).find(p => p.kind === 'technique');
  assert.equal(tech.steps.length, 7, '7 шагов позитивного намерения');
});

test('движение сектора: идеал, следующий уровень и шаг сохраняются', () => {
  const db = freshDb();
  psy.ensureWheel(db);
  const a = psy.wheel(db).areas.find(x => x.name === 'Здоровье и спорт');
  assert.equal(a.step, '', 'поля движения пустые по умолчанию');
  psy.patchArea(db, a.id, { ideal: 'сон 7+, спорт 3р/нед', next_desc: 'зал 2р/нед', step: 'записаться в зал' });
  const after = psy.wheel(db).areas.find(x => x.id === a.id);
  assert.equal(after.ideal, 'сон 7+, спорт 3р/нед');
  assert.equal(after.next_desc, 'зал 2р/нед');
  assert.equal(after.step, 'записаться в зал');
});

test('сектора пользователя: 10 штук на русском; старый дефолт заменяется', () => {
  const db = freshDb();
  // имитируем базу со старым набором
  ['Здоровье', 'Финансы', 'Карьера', 'Отношения', 'Окружение', 'Развитие', 'Отдых', 'Смысл']
    .forEach((n, i) => db.prepare('INSERT INTO wheel_areas(name, ord) VALUES(?,?)').run(n, i + 1));
  psy.ensureWheel(db);
  const names = psy.wheel(db).areas.map(a => a.name);
  assert.equal(names.length, 10);
  assert.deepEqual(names, ['Работа', 'Семья и дети', 'Партнёр', 'Саморазвитие и обучение', 'Здоровье и спорт',
    'Социализация', 'Дом', 'Деньги и инвестиции', 'Отдых и хобби', 'Перспективы будущего']);
  psy.ensureWheel(db);   // повторно — не трогает
  assert.equal(psy.wheel(db).areas.length, 10);
});

test('общий замок разделов: включение, проверка, смена, снятие', () => {
  const db = freshDb();
  assert.equal(psy.lockEnabled(db), false);
  assert.equal(psy.checkLockPass(db, 'что угодно'), true, 'без пароля всё открыто');
  psy.setLockPass(db, 'секрет');
  assert.equal(psy.lockEnabled(db), true);
  assert.equal(psy.checkLockPass(db, 'секрет'), true);
  assert.equal(psy.checkLockPass(db, 'не тот'), false);
  psy.setLockPass(db, '');   // снятие
  assert.equal(psy.lockEnabled(db), false);
});

test('позитивное намерение: техника создаётся один раз, случай ложится в журнал с ответами', () => {
  const db = freshDb();
  psy.ensurePositiveIntent(db);
  psy.ensurePositiveIntent(db);   // идемпотентность
  const pi = psy.listPractices(db).filter(p => p.name === 'Позитивное намерение');
  assert.equal(pi.length, 1);
  assert.equal(pi[0].kind, 'technique');
  assert.equal(pi[0].steps.length, 7, 'семь вопросов');
  // пройденный случай: ответы по вопросам
  psy.logPractice(db, pi[0].id, { answers: ['сорвался на звонке', 'крик', 'желание быть услышанным', 'пауза и вопрос', 'пауза', 'никому', 'завтра на созвоне'], note: 'кейс №1' });
  const log = psy.practiceLogs(db, pi[0].id)[0];
  assert.equal(log.answers.length, 7);
  assert.equal(log.note, 'кейс №1');
  // пользователь удалил технику — каркас не пересоздаёт (флаг)
  psy.delPractice(db, pi[0].id);
  psy.ensurePositiveIntent(db);
  assert.equal(psy.listPractices(db).filter(p => p.name === 'Позитивное намерение').length, 0);
});

test('шаг колеса → задача в схожей категории, идемпотентно', () => {
  const db = freshDb();
  psy.ensureWheel(db);
  const health = db.prepare(`SELECT id FROM wheel_areas WHERE name = 'Здоровье и спорт'`).get();
  assert.throws(() => psy.wheelStepToTask(db, health.id), /нет шага/);
  psy.patchArea(db, health.id, { step: 'записаться в зал до пятницы' });
  const r1 = psy.wheelStepToTask(db, health.id);
  assert.equal(r1.existed, false);
  assert.equal(r1.category.includes('Здоровье'), true, 'легло в Жизнь → Здоровье');
  assert.equal(r1.node.kind, 'task');
  assert.match(r1.node.note, /сектор «Здоровье и спорт»/);
  // повторный клик не плодит дубль
  const r2 = psy.wheelStepToTask(db, health.id);
  assert.equal(r2.existed, true);
  assert.equal(r2.node.id, r1.node.id);
  // сектор без явного маппинга → Инбокс не падает
  const social = db.prepare(`SELECT id FROM wheel_areas WHERE name = 'Социализация'`).get();
  psy.patchArea(db, social.id, { step: 'позвать пацанов на падл' });
  const r3 = psy.wheelStepToTask(db, social.id);
  assert.ok(r3.category.length > 0);
});

test('смена шага колеса обновляет открытую задачу сектора', () => {
  const db = freshDb();
  psy.ensureWheel(db);
  const h = db.prepare(`SELECT id FROM wheel_areas WHERE name = 'Здоровье и спорт'`).get();
  psy.patchArea(db, h.id, { step: 'записаться в зал' });
  const t = psy.wheelStepToTask(db, h.id).node;
  psy.patchArea(db, h.id, { step: 'зал 2 раза в неделю' });
  const after = db.prepare('SELECT * FROM nodes WHERE id = ?').get(t.id);
  assert.equal(after.title, 'зал 2 раза в неделю', 'задача переименована вслед за шагом');
  // закрытую задачу не трогаем
  db.prepare(`UPDATE nodes SET status = 'done' WHERE id = ?`).run(t.id);
  psy.patchArea(db, h.id, { step: 'новый шаг' });
  assert.equal(db.prepare('SELECT title FROM nodes WHERE id = ?').get(t.id).title, 'зал 2 раза в неделю');
});

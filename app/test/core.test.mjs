import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, norm } from '../db.js';
import * as core from '../core.js';

function freshDb() { const db = createDb(':memory:'); seed(db); return db; }
const byTitle = (db, part) =>
  core.listState(db).tasks.find(t => t.title.includes(part));

test('нормализация гомоглифов: х5 (кириллица) == x5 (латиница)', () => {
  assert.equal(norm('х5'), 'x5');
  assert.equal(norm('X5'), 'x5');
  assert.equal(norm('Продать х5'), norm('Продать x5'));
});

test('seed: данные загружены, статусы корректны', () => {
  const db = freshDb();
  const s = core.listState(db);
  assert.equal(s.goals.length, 3);
  assert.ok(s.tasks.length >= 14);
  assert.equal(byTitle(db, 'Резидентство SK').status, 'open');
});

test('блокировка: «Растаможка MX5» заблокирована открытым решением «Резидентство SK?»', () => {
  const db = freshDb();
  assert.equal(byTitle(db, 'Растаможка').blocked, true);
});

test('принятие решения снимает блокировку', () => {
  const db = freshDb();
  core.toggleTask(db, byTitle(db, 'Резидентство SK').id);   // open -> accepted
  assert.equal(byTitle(db, 'Растаможка').blocked, false);
});

test('поперечная связь: «Половину Наталье?» ждёт консультацию из ветки Семья', () => {
  const db = freshDb();
  const half = byTitle(db, 'Половину от продажи');
  assert.equal(half.blocked, true);
  core.toggleTask(db, byTitle(db, 'Консультация по договору').id); // done
  assert.equal(byTitle(db, 'Половину от продажи').blocked, false);
});

test('радар «Продать X5»: окно времени ловит налоги и транш', () => {
  const db = freshDb();
  const r = core.radar(db, byTitle(db, 'Продать X5').id);
  const titles = r.timeWindow.map(t => t.title).join('|');
  assert.match(titles, /налоги/i);
  assert.match(titles, /Транш/);
});

test('радар «Продать X5»: упоминания находят правило 10k и решение про Наталью', () => {
  const db = freshDb();
  const r = core.radar(db, byTitle(db, 'Продать X5').id);
  const titles = r.mentions.map(t => t.title).join('|');
  assert.match(titles, /10k|легализация/i);
  assert.match(titles, /Наталье/);
});

test('радар: принципы ветки видны («НЕ СПЕШИМ до 2028»)', () => {
  const db = freshDb();
  const r = core.radar(db, byTitle(db, 'Изучить').id);
  assert.match(r.principles.map(p => p.title).join('|'), /НЕ СПЕШИМ/);
});

test('поиск: кириллическое «х5» находит латинское «X5»', () => {
  const db = freshDb();
  const res = core.search(db, 'х5');
  assert.ok(res.some(t => t.title.includes('X5')));
});

test('создание задачи + защита от циклов в зависимостях', () => {
  const db = freshDb();
  const a = core.createTask(db, { title: 'A', goal_id: 1 });
  const b = core.createTask(db, { title: 'B', goal_id: 1 });
  core.addDep(db, a.id, b.id, 'blocks');
  assert.throws(() => core.addDep(db, b.id, a.id, 'blocks'), /cycle/);
  assert.throws(() => core.addDep(db, a.id, a.id), /self/);
});

test('toggle задачи: todo -> done -> todo', () => {
  const db = freshDb();
  const t = core.createTask(db, { title: 'Тест', goal_id: 1 });
  assert.equal(core.toggleTask(db, t.id).status, 'done');
  assert.equal(core.toggleTask(db, t.id).status, 'todo');
});

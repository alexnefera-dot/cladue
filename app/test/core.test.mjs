import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, norm } from '../db.js';
import * as core from '../core.js';

function freshDb() { const db = createDb(':memory:'); seed(db); return db; }
const byTitle = (db, part) =>
  core.listTree(db).nodes.find(n => n.title.includes(part));

test('нормализация гомоглифов: х5 == x5', () => {
  assert.equal(norm('х5'), 'x5');
  assert.equal(norm('X5'), 'x5');
  assert.equal(norm('Продать х5'), norm('Продать x5'));
});

test('сид: структура пользователя дословно, НИЧЕГО не типизировано и не связано', () => {
  const db = freshDb();
  const s = core.listTree(db);
  assert.ok(s.nodes.length >= 28);
  assert.ok(s.nodes.every(n => n.kind === null), 'все kind = NULL');
  assert.ok(s.nodes.every(n => n.priority === null), 'все priority = NULL');
  assert.ok(s.nodes.every(n => !n.blocked), 'ничего не заблокировано');
  assert.equal(s.links.length, 0, 'ноль связей');
});

test('сид: вложенность и порядок сохранены (Авто → Х5 → 4 строки в исходном порядке)', () => {
  const db = freshDb();
  const x5 = byTitle(db, 'Х5');
  const kids = core.listTree(db).nodes
    .filter(n => n.parent_id === x5.id)
    .sort((a, b) => a.ord - b.ord)
    .map(n => n.title);
  assert.equal(kids.length, 4);
  assert.match(kids[0], /Август продать/);
  assert.match(kids[3], /половину Наталье/);
});

test('подсказка типа: предлагает, но не сохраняет', () => {
  const db = freshDb();
  const n = byTitle(db, 'Август продать');
  const s = core.suggestForNode(db, n.id);
  assert.equal(s.kind, 'question');           // «…х5?» — вопрос на конце
  assert.equal(core.suggestKind('Стоит ли положить половину Наталье на счет ?'), 'decision');
  assert.equal(core.suggestKind('НЕ СПЕШИМ до 2028'), 'principle');
  assert.equal(core.suggestKind('Понять, когда будет внж у Натальи'), 'task');
  assert.equal(byTitle(db, 'Август продать').kind, null, 'в базе ничего не изменилось');
});

test('подсказка срока из текста: «Август…» и «до 2028»', () => {
  const now = new Date('2026-06-10');
  assert.equal(core.suggestDate('Август продать х5?', now).date, '2026-08-31');
  assert.equal(core.suggestDate('НЕ СПЕШИМ до 2028', now).date, '2027-12-31');
  assert.equal(core.suggestDate('просто строка', now), null);
});

test('принятие типа пользователем выставляет стартовый статус', () => {
  const db = freshDb();
  const n = byTitle(db, 'Август продать');
  core.updateNode(db, n.id, { kind: 'task' });
  assert.equal(core.getNode(db, n.id).status, 'todo');
  core.updateNode(db, n.id, { kind: 'decision' });
  assert.equal(core.getNode(db, n.id).status, 'open');
});

test('предложения связей: «Август продать х5?» находит «Продать х5 до надо» из Семьи', () => {
  const db = freshDb();
  const s = core.suggestForNode(db, byTitle(db, 'Август продать').id);
  const titles = s.links.map(l => l.node.title).join('|');
  assert.match(titles, /Продать х5 до надо/);
  assert.ok(s.links.every(l => l.reason.startsWith('совпадение')), 'у каждого предложения есть причина');
});

test('предложения не включают родителей/детей и уже отклонённое', () => {
  const db = freshDb();
  const n = byTitle(db, 'Август продать');
  const s1 = core.suggestForNode(db, n.id);
  assert.ok(!s1.links.some(l => l.node.title === 'Х5'), 'родитель не предлагается');
  const target = s1.links.find(l => /до надо/.test(l.node.title));
  core.dismissPair(db, n.id, target.node.id);
  const s2 = core.suggestForNode(db, n.id);
  assert.ok(!s2.links.some(l => l.node.id === target.node.id), 'отклонённое скрыто');
});

test('блокировка появляется ТОЛЬКО после подтверждения связи пользователем', () => {
  const db = freshDb();
  const sell = byTitle(db, 'Август продать');
  const consult = byTitle(db, 'Консультация за договор');
  assert.equal(sell.blocked, false);
  core.updateNode(db, consult.id, { kind: 'task' });
  core.addLink(db, consult.id, sell.id, 'blocks');      // пользователь подтвердил
  assert.equal(byTitle(db, 'Август продать').blocked, true);
  core.toggleNode(db, consult.id);                      // консультация done
  assert.equal(byTitle(db, 'Август продать').blocked, false);
});

test('циклы и self-link запрещены', () => {
  const db = freshDb();
  const a = core.addChild(db, null, 'A');
  const b = core.addChild(db, null, 'B');
  core.addLink(db, a.id, b.id, 'blocks');
  assert.throws(() => core.addLink(db, b.id, a.id, 'blocks'), /cycle/);
  assert.throws(() => core.addLink(db, a.id, a.id), /self/);
});

test('toggle работает только для типизированных задач/решений', () => {
  const db = freshDb();
  const plain = byTitle(db, 'Поездки');
  core.toggleNode(db, plain.id);
  assert.equal(core.getNode(db, plain.id).status, null, 'нетипизированная строка не трогается');
});

test('поиск: кириллица находит, дети добавляются в конец', () => {
  const db = freshDb();
  assert.ok(core.search(db, 'х5').length >= 2);
  const x5 = byTitle(db, 'Х5');
  const added = core.addChild(db, x5.id, 'Новая строка');
  const kids = core.listTree(db).nodes.filter(n => n.parent_id === x5.id).sort((a, b) => a.ord - b.ord);
  assert.equal(kids.at(-1).id, added.id);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed } from '../db.js';
import * as notes from '../notes.js';
import * as core from '../core.js';

function freshDb() { const db = createDb(':memory:'); seed(db); return db; }

test('страницы: дерево, правка, перемещение, каскадное удаление с чисткой поиска', () => {
  const db = freshDb();
  const root = notes.addPage(db, { title: 'База знаний' });
  const child = notes.addPage(db, { title: 'Инвестиции', parent_id: root.id, content: 'про облигации' });
  notes.addPage(db, { title: 'Шпаргалка', parent_id: child.id });
  assert.equal(notes.listPages(db).length, 3);
  notes.patchPage(db, child.id, { content: 'теперь про крипту' });
  assert.ok(notes.searchPages(db, 'крипту').some(p => p.id === child.id));
  assert.ok(!notes.searchPages(db, 'облигации').length, 'старый текст из индекса ушёл');
  assert.throws(() => notes.movePage(db, root.id, child.id), /descendant/);
  const other = notes.addPage(db, { title: 'Другая' });
  notes.movePage(db, child.id, other.id);
  assert.equal(notes.getPage(db, child.id).parent_id, other.id);
  assert.equal(notes.delPage(db, other.id), 3, 'другая + инвестиции + шпаргалка');
  assert.equal(notes.searchPages(db, 'крипту').length, 0);
});

test('бэклинки: страницы с [[Заголовком]] находятся, регистр не важен', () => {
  const db = freshDb();
  const target = notes.addPage(db, { title: 'План переезда' });
  notes.addPage(db, { title: 'Дневник', content: 'думал про [[план переезда]] и бюджет' });
  notes.addPage(db, { title: 'Прочее', content: 'без ссылок' });
  const back = notes.backlinks(db, target.id);
  assert.equal(back.length, 1);
  assert.equal(back[0].title, 'Дневник');
});

test('вики-резолв: страница приоритетнее записи, иначе запись из Задач, иначе null', () => {
  const db = freshDb();
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  core.addChild(db, inbox.id, 'Продать X5');
  assert.equal(notes.resolveWiki(db, 'Продать X5').type, 'node');
  const pg = notes.addPage(db, { title: 'Продать X5' });
  assert.deepEqual(notes.resolveWiki(db, 'продать x5'), { type: 'page', id: pg.id });
  assert.equal(notes.resolveWiki(db, 'Несуществующее'), null);
});

test('план задачи: идемпотентно, лежит в «Планы задач», с шаблоном', () => {
  const db = freshDb();
  const inbox = core.listCategories(db).find(c => c.title.includes('Инбокс'));
  const n = core.addChild(db, inbox.id, 'Подать на визу');
  core.updateNode(db, n.id, { kind: 'task', note: 'до росписи' });
  const p1 = notes.planPage(db, n.id);
  const p2 = notes.planPage(db, n.id);
  assert.equal(p1.id, p2.id, 'повторный вызов возвращает ту же страницу');
  assert.equal(p1.node_id, n.id);
  assert.match(p1.content, /# План: Подать на визу/);
  assert.match(p1.content, /до росписи/);
  const root = notes.listPages(db).find(p => p.title === 'Планы задач');
  assert.equal(p1.parent_id, root.id);
});

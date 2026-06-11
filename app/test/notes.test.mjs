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

test('пароль: шифрование, неверный пароль, поиск, пересохранение и снятие', () => {
  const db = freshDb();
  const pg = notes.addPage(db, { title: 'Секрет', content: 'тайный текст про крипту' });
  assert.ok(notes.searchPages(db, 'тайный').length, 'до пароля ищется');
  notes.lockPage(db, pg.id, 'qwerty');
  const row = db.prepare('SELECT * FROM pages WHERE id = ?').get(pg.id);
  assert.equal(row.locked, 1);
  assert.equal(row.content, '', 'открытого текста в базе нет');
  assert.ok(!row.enc.includes('тайный'), 'шифротекст не содержит исходник');
  assert.equal(notes.searchPages(db, 'тайный').length, 0, 'из поиска ушла');
  assert.throws(() => notes.unlockPage(db, pg.id, 'wrong'), /неверный пароль/);
  assert.equal(notes.unlockPage(db, pg.id, 'qwerty').content, 'тайный текст про крипту');
  assert.throws(() => notes.patchPage(db, pg.id, { content: 'x' }), /под паролем/);
  notes.lockPage(db, pg.id, 'qwerty', 'обновлённый секрет');  // сейв в закрытую
  assert.equal(notes.unlockPage(db, pg.id, 'qwerty').content, 'обновлённый секрет');
  notes.unlockPage(db, pg.id, 'qwerty', true);                 // снять пароль
  const open = db.prepare('SELECT * FROM pages WHERE id = ?').get(pg.id);
  assert.equal(open.locked, 0);
  assert.equal(open.content, 'обновлённый секрет');
  assert.ok(notes.searchPages(db, 'обновлённый').length, 'после снятия снова в поиске');
});

test('демо-страницы: сидятся один раз, приватная под паролем 1234', () => {
  const db = freshDb();
  notes.seedPages(db);
  notes.seedPages(db);
  const pages = notes.listPages(db);
  assert.ok(pages.some(p => p.title.includes('План переезда')));
  assert.ok(pages.some(p => p.title === 'Сравнение городов'));
  const secret = pages.find(p => p.locked);
  assert.ok(secret, 'есть страница под паролем');
  assert.match(notes.unlockPage(db, secret.id, '1234').content, /зашифровано/);
  assert.equal(pages.filter(p => p.title === 'Журнал решений').length, 1, 'без дублей');
});

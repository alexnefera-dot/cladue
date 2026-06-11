import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createDb, seed } from '../db.js';
import * as core from '../core.js';
import * as notes from '../notes.js';
import * as fin from '../fin.js';
import { exportAll, backupDb } from '../export.js';

function freshDb() { const db = createDb(':memory:'); seed(db); return db; }
const inboxOf = db => core.listCategories(db).find(c => c.title.includes('Инбокс'));

test('корзина: восстановление поддерева со связями, шагом и занятыми id', () => {
  const db = freshDb();
  const inbox = inboxOf(db);
  const parent = core.addChild(db, inbox.id, 'Продать X5');
  core.updateNode(db, parent.id, { kind: 'task', due_date: '2026-08-31', priority: 'P1' });
  const child = core.addChild(db, parent.id, 'Написать автобизнесменам');
  const other = core.addChild(db, inbox.id, 'Налоги');
  core.updateNode(db, other.id, { kind: 'task' });
  core.addLink(db, other.id, parent.id, 'blocks');           // внешняя связь
  fin.addStep(db, { kind: 'sell', title: 'X5 шаг' });
  const step = db.prepare(`SELECT id FROM steps WHERE title = 'X5 шаг'`).get();
  db.prepare('UPDATE steps SET task_id = ? WHERE id = ?').run(parent.id, step.id);

  const { trash_id } = core.deleteNode(db, parent.id);
  assert.ok(!core.listTree(db).nodes.some(n => n.title === 'Продать X5'));
  // занимаем освободившиеся id новыми записями
  core.addChild(db, inbox.id, 'Новая 1');
  core.addChild(db, inbox.id, 'Новая 2');

  const payload = JSON.parse(db.prepare('SELECT payload FROM trash WHERE id = ?').get(trash_id).payload);
  const newId = core.restoreNodes(db, payload);
  const tree = core.listTree(db).nodes;
  const restored = tree.find(n => n.id === newId);
  assert.equal(restored.title, 'Продать X5');
  assert.equal(restored.kind, 'task');
  assert.equal(restored.priority, 'P1');
  assert.equal(restored.parent_id, inbox.id, 'вернулся в исходного родителя');
  assert.ok(tree.some(n => n.title === 'Написать автобизнесменам' && n.parent_id === newId), 'ребёнок внутри');
  assert.equal(restored.blocked, true, 'внешняя связь-блокер восстановлена');
  assert.equal(db.prepare('SELECT task_id FROM steps WHERE id = ?').get(step.id).task_id, newId, 'шаг снова привязан');
  assert.ok(core.search(db, 'автобизнесменам').length, 'поиск снова видит');
});

test('корзина: страницы восстанавливаются, шифрованные остаются шифрованными', () => {
  const db = freshDb();
  const pg = notes.addPage(db, { title: 'Секрет', content: 'тайна' });
  notes.lockPage(db, pg.id, 'pw');
  const child = notes.addPage(db, { title: 'Открытая', parent_id: null, content: 'текст про крипту' });
  const { trash_id } = notes.delPage(db, pg.id);
  const payload = JSON.parse(db.prepare('SELECT payload FROM trash WHERE id = ?').get(trash_id).payload);
  const newId = notes.restorePages(db, payload);
  const restored = db.prepare('SELECT * FROM pages WHERE id = ?').get(newId);
  assert.equal(restored.locked, 1);
  assert.ok(restored.enc, 'шифротекст сохранён');
  assert.equal(notes.unlockPage(db, newId, 'pw').content, 'тайна');
  assert.equal(notes.searchPages(db, 'тайна').length, 0, 'закрытая в поиск не вернулась');
  assert.ok(notes.searchPages(db, 'крипту').length, 'остальной индекс цел');
});

test('экспорт: data.json, goals.md, страницы и финансы на месте; шифрованное не в открытую', () => {
  const db = freshDb();
  const inbox = inboxOf(db);
  const n = core.addChild(db, inbox.id, 'Закрыть налоги');
  core.updateNode(db, n.id, { kind: 'task', priority: 'P0', due_date: '2026-08-15' });
  const pg = notes.addPage(db, { title: 'Секрет', content: 'сверхтайна' });
  notes.lockPage(db, pg.id, 'pw');
  notes.addPage(db, { title: 'Обычная', content: '# Привет' });
  fin.addDebt(db, { name: 'Дима', amount: 60, direction: 'owed_to_me' });

  const root = mkdtempSync(join(tmpdir(), 'pipboy-'));
  const { dir, files } = exportAll(db, root);
  assert.ok(files.includes('data.json') && files.includes('goals.md') && files.includes('finance.md'));
  const goals = readFileSync(join(dir, 'goals.md'), 'utf8');
  assert.match(goals, /\[ \] P0 Закрыть налоги 📅 2026-08-15/);
  const finMd = readFileSync(join(dir, 'finance.md'), 'utf8');
  assert.match(finMd, /мне должны: Дима — 60/);
  const secretFile = files.find(f => f.includes('Секрет'));
  const secretMd = readFileSync(join(dir, secretFile), 'utf8');
  assert.ok(!secretMd.includes('сверхтайна'), 'тайна не утекла в markdown');
  assert.match(secretMd, /зашифровано/);
  const dump = JSON.parse(readFileSync(join(dir, 'data.json'), 'utf8'));
  assert.ok(dump.pages.find(p => p.title === 'Секрет').enc, 'шифротекст в дампе есть (для восстановления)');
  assert.ok(dump.nodes.length > 0 && dump.debts.length === 1);
});

test('бэкап: копия создаётся, :memory: отказывает честно', () => {
  const root = mkdtempSync(join(tmpdir(), 'pipboy-'));
  const dbFile = join(root, 'data.db');
  writeFileSync(dbFile, 'fake-db-bytes');
  const f = backupDb(dbFile, root);
  assert.ok(existsSync(f));
  assert.equal(readFileSync(f, 'utf8'), 'fake-db-bytes');
  assert.equal(backupDb(':memory:', root), null);
});

test('фронт: скрипты не конфликтуют top-level идентификаторами (общий scope браузера)', () => {
  const pub = join(import.meta.dirname, '..', 'public');
  const files = ['app.js', 'fin.js', 'cal.js', 'life.js', 'notes.js', 'psy.js', 'track.js', 'today.js'];
  const seen = {};
  for (const f of files) {
    const src = readFileSync(join(pub, f), 'utf8');
    for (const m of src.matchAll(/^(?:const|let|class)\s+([A-Za-z_$][\w$]*)/gm)) {
      assert.ok(!seen[m[1]], `«${m[1]}» объявлен и в ${seen[m[1]]}, и в ${f} — второй скрипт упадёт целиком`);
      seen[m[1]] = f;
    }
  }
});

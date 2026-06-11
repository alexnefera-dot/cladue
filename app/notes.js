import { norm, tokens } from './db.js';

export function listPages(db) {
  return db.prepare('SELECT id, parent_id, ord, title, node_id, updated_at FROM pages ORDER BY parent_id NULLS FIRST, ord, id').all();
}

export function getPage(db, id) {
  return db.prepare('SELECT * FROM pages WHERE id = ?').get(id);
}

export function addPage(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?').get(b.parent_id ?? null).o;
  db.prepare('INSERT INTO pages(parent_id, ord, title, content, node_id) VALUES(?,?,?,?,?)')
    .run(b.parent_id ?? null, ord, b.title, b.content ?? '', b.node_id ?? null);
  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  db.prepare('INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)')
    .run(id, norm(b.title), norm(b.content ?? ''));
  return getPage(db, id);
}

export function patchPage(db, id, b) {
  for (const k of ['title', 'content'])
    if (k in b) db.prepare(`UPDATE pages SET ${k} = ?, updated_at = datetime('now') WHERE id = ?`).run(b[k], id);
  if ('title' in b || 'content' in b) {
    const p = getPage(db, id);
    db.prepare('UPDATE page_fts SET title_norm = ?, content_norm = ? WHERE rowid = ?')
      .run(norm(p.title), norm(p.content), id);
  }
  return getPage(db, id);
}

export function movePage(db, id, parent_id) {
  if (id === parent_id) throw new Error('self-parent');
  if (parent_id != null) {
    const desc = db.prepare(`
      WITH RECURSIVE r(x) AS (
        SELECT id FROM pages WHERE parent_id = ?
        UNION SELECT p.id FROM pages p JOIN r ON p.parent_id = r.x
      ) SELECT 1 AS hit FROM r WHERE x = ? LIMIT 1`).get(id, parent_id);
    if (desc) throw new Error('cannot move into own descendant');
  }
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?').get(parent_id).o;
  db.prepare(`UPDATE pages SET parent_id = ?, ord = ? WHERE id = ?`).run(parent_id, ord, id);
  return getPage(db, id);
}

export function delPage(db, id) {
  const ids = db.prepare(`
    WITH RECURSIVE r(x) AS (
      SELECT ? UNION SELECT p.id FROM pages p JOIN r ON p.parent_id = r.x
    ) SELECT x FROM r`).all(id).map(r => r.x);
  for (const x of ids) db.prepare('DELETE FROM page_fts WHERE rowid = ?').run(x);
  db.prepare('DELETE FROM pages WHERE id = ?').run(id);
  return ids.length;
}

// Бэклинки: страницы, в тексте которых есть [[Заголовок этой страницы]].
// Регистронезависимо в JS: lower() SQLite не понижает кириллицу.
export function backlinks(db, id) {
  const p = getPage(db, id);
  if (!p) return [];
  const needle = ('[[' + p.title + ']]').toLowerCase();
  return db.prepare('SELECT id, title, content FROM pages WHERE id != ?').all(id)
    .filter(x => x.content.toLowerCase().includes(needle))
    .map(({ id, title }) => ({ id, title }));
}

// [[Имя]] → страница (приоритет) или запись из Задач
export function resolveWiki(db, name) {
  const target = norm(name);
  const page = db.prepare('SELECT id, title FROM pages').all()
    .find(p => norm(p.title) === target);
  if (page) return { type: 'page', id: page.id };
  const node = db.prepare('SELECT id, title FROM nodes WHERE is_category = 0').all()
    .find(n => norm(n.title) === target);
  if (node) return { type: 'node', id: node.id };
  return null;
}

export function searchPages(db, q) {
  const toks = tokens(q);
  if (!toks.length) return [];
  const match = toks.map(x => `"${x.replaceAll('"', '')}"*`).join(' ');
  return db.prepare(`
    SELECT p.id, p.title FROM page_fts JOIN pages p ON p.id = page_fts.rowid
    WHERE page_fts MATCH ? ORDER BY bm25(page_fts) LIMIT 10`).all(match);
}

// «План» записи: найти или создать привязанную страницу (идемпотентно)
export function planPage(db, nodeId) {
  const existing = db.prepare('SELECT * FROM pages WHERE node_id = ?').get(nodeId);
  if (existing) return existing;
  const node = db.prepare('SELECT * FROM nodes WHERE id = ?').get(nodeId);
  if (!node) throw new Error('node not found');
  let root = db.prepare(`SELECT id FROM pages WHERE title = 'Планы задач' AND parent_id IS NULL`).get();
  if (!root) root = addPage(db, { title: 'Планы задач' });
  return addPage(db, {
    parent_id: root.id, node_id: nodeId, title: node.title,
    content: `# План: ${node.title}\n\nКонтекст: ${node.note || '—'}\n\n## Рассуждение\n\n- \n\n## Шаги\n\n- [ ] \n`,
  });
}

import { norm, tokens, insertNode } from './db.js';

export function getNode(db, id) {
  return db.prepare('SELECT * FROM nodes WHERE id = ?').get(id);
}

const PATCHABLE = ['title', 'note', 'kind', 'status', 'priority', 'due_date', 'answer'];

export function updateNode(db, id, fields) {
  const keys = Object.keys(fields).filter(k => PATCHABLE.includes(k));
  if (keys.length) {
    // принятие типа выставляет стартовый статус
    if (keys.includes('kind') && !('status' in fields)) {
      fields.status = fields.kind === 'decision' ? 'open'
                    : fields.kind === 'task' ? 'todo' : null;
      keys.push('status');
    }
    const sets = keys.map(k => `${k} = ?`).join(', ');
    db.prepare(`UPDATE nodes SET ${sets}, updated_at = datetime('now') WHERE id = ?`)
      .run(...keys.map(k => fields[k]), id);
    if (keys.includes('title') || keys.includes('note')) {
      const t = getNode(db, id);
      db.prepare('UPDATE node_fts SET title_norm = ?, note_norm = ? WHERE rowid = ?')
        .run(norm(t.title), norm(t.note), id);
    }
  }
  return getNode(db, id);
}

export function toggleNode(db, id) {
  const t = getNode(db, id);
  if (!t || !['task', 'decision'].includes(t.kind ?? '')) return t;
  const next = t.kind === 'decision'
    ? (t.status === 'open' ? 'accepted' : 'open')
    : (t.status === 'done' ? 'todo' : 'done');
  const res = updateNode(db, id, { status: next });
  // если задача создана из шага портфеля — шаг следует за ней
  db.prepare('UPDATE steps SET status = ? WHERE task_id = ?')
    .run(next === 'done' ? 'done' : 'planned', id);
  return res;
}

export function addChild(db, parent_id, title, is_category = 0) {
  const id = insertNode(db, parent_id ?? null, title, { is_category });
  return getNode(db, id);
}

// ===== Импорт вставленного блока: разбор вложенности по отступам =====
export function parseOutline(text) {
  const lines = String(text).replace(/\r/g, '').split('\n');
  const out = [];
  for (const raw of lines) {
    if (!raw.trim()) continue;
    const indentMatch = raw.match(/^[\t ]*/)[0];
    const indent = indentMatch.replace(/\t/g, '    ').length;
    // срезаем маркеры списков и нумерацию: «1.», «2)», «-», «•», «◦», «▪»
    const title = raw.trim().replace(/^(?:\d+[.)]|[-*•◦▪‣o])\s+/u, '').trim();
    if (title) out.push({ indent, title });
  }
  // нормализуем отступы в уровни
  const levels = [...new Set(out.map(l => l.indent))].sort((a, b) => a - b);
  return out.map(l => ({ level: levels.indexOf(l.indent), title: l.title }));
}

export function importBlock(db, parent_id, text) {
  const rows = parseOutline(text);
  const stack = [{ level: -1, id: parent_id ?? null }];
  let count = 0;
  for (const r of rows) {
    while (stack.length > 1 && stack.at(-1).level >= r.level) stack.pop();
    const id = insertNode(db, stack.at(-1).id, r.title);
    stack.push({ level: r.level, id });
    count++;
  }
  return count;
}

// ===== Перемещение узла (раскидывание по категориям) =====
export function moveNode(db, id, new_parent_id) {
  if (id === new_parent_id) throw new Error('self-parent');
  if (new_parent_id != null) {
    const desc = db.prepare(`
      WITH RECURSIVE r(x) AS (
        SELECT id FROM nodes WHERE parent_id = ?
        UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x
      ) SELECT 1 AS hit FROM r WHERE x = ? LIMIT 1`).get(id, new_parent_id);
    if (desc) throw new Error('cannot move into own descendant');
  }
  const ord = db.prepare('SELECT COALESCE(MAX(ord), 0) + 1 AS o FROM nodes WHERE parent_id IS ?')
    .get(new_parent_id).o;
  db.prepare(`UPDATE nodes SET parent_id = ?, ord = ?, updated_at = datetime('now') WHERE id = ?`)
    .run(new_parent_id, ord, id);
  return getNode(db, id);
}

// ===== Удаление узла со всем поддеревом (и чистка поискового индекса) =====
export function deleteNode(db, id) {
  const ids = db.prepare(`
    WITH RECURSIVE r(x) AS (
      SELECT ? UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x
    ) SELECT x FROM r`).all(id).map(r => r.x);
  for (const x of ids) {
    db.prepare('DELETE FROM node_fts WHERE rowid = ?').run(x);
    db.prepare('UPDATE steps SET task_id = NULL WHERE task_id = ?').run(x); // отвязать шаги
  }
  db.prepare('DELETE FROM nodes WHERE id = ?').run(id);   // дети — каскадом
  return ids.length;
}

// ===== Объединение дублей: dup вливается в keep =====
export function mergeNodes(db, keepId, dupId) {
  if (keepId === dupId) throw new Error('same node');
  const keep = getNode(db, keepId), dup = getNode(db, dupId);
  if (!keep || !dup) throw new Error('not found');

  // дети дубля переезжают (в конец)
  for (const ch of db.prepare('SELECT id FROM nodes WHERE parent_id = ? ORDER BY ord').all(dupId)) {
    const ord = db.prepare('SELECT COALESCE(MAX(ord), 0) + 1 AS o FROM nodes WHERE parent_id IS ?').get(keepId).o;
    db.prepare('UPDATE nodes SET parent_id = ?, ord = ? WHERE id = ?').run(keepId, ord, ch.id);
  }
  // связи перекидываются (без self-link и дублей)
  for (const l of db.prepare('SELECT * FROM links WHERE from_id = ? OR to_id = ?').all(dupId, dupId)) {
    const from = l.from_id === dupId ? keepId : l.from_id;
    const to = l.to_id === dupId ? keepId : l.to_id;
    db.prepare('DELETE FROM links WHERE id = ?').run(l.id);
    if (from !== to)
      db.prepare('INSERT OR IGNORE INTO links(from_id, to_id, type) VALUES(?,?,?)').run(from, to, l.type);
  }
  // свойства: берём более строгий срок, более высокий приоритет, тип — если у keep не было
  const fields = {};
  if (dup.due_date && (!keep.due_date || dup.due_date < keep.due_date)) fields.due_date = dup.due_date;
  if (dup.priority && (!keep.priority || dup.priority < keep.priority)) fields.priority = dup.priority;
  if (!keep.kind && dup.kind) { fields.kind = dup.kind; fields.status = dup.status; }
  fields.note = [keep.note, `[объединено] ${dup.title}`, dup.note].filter(Boolean).join('\n');
  updateNode(db, keepId, fields);

  db.prepare('DELETE FROM node_fts WHERE rowid = ?').run(dupId);
  db.prepare('DELETE FROM nodes WHERE id = ?').run(dupId);
  return getNode(db, keepId);
}

export function subtreeCount(db, id) {
  return db.prepare(`
    WITH RECURSIVE r(x) AS (
      SELECT ? UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x
    ) SELECT count(*) AS c FROM r`).get(id).c - 1;
}

export function listCategories(db) {
  return db.prepare('SELECT * FROM nodes WHERE is_category = 1 ORDER BY parent_id NULLS FIRST, ord').all();
}

// ===== Связи (только подтверждённые пользователем) =====
export function addLink(db, from_id, to_id, type = 'related') {
  if (from_id === to_id) throw new Error('self-link');
  if (type === 'blocks' && reaches(db, to_id, from_id)) throw new Error('cycle');
  db.prepare('INSERT OR IGNORE INTO links(from_id, to_id, type) VALUES(?,?,?)')
    .run(from_id, to_id, type);
}

export function removeLink(db, id) {
  db.prepare('DELETE FROM links WHERE id = ?').run(id);
}

export function dismissPair(db, a, b) {
  const [x, y] = a < b ? [a, b] : [b, a];
  db.prepare('INSERT OR IGNORE INTO dismissed(a, b) VALUES(?,?)').run(x, y);
}

function reaches(db, from, to) {
  const row = db.prepare(`
    WITH RECURSIVE r(id) AS (
      SELECT to_id FROM links WHERE from_id = ? AND type = 'blocks'
      UNION SELECT l.to_id FROM links l JOIN r ON l.from_id = r.id AND l.type = 'blocks'
    ) SELECT 1 AS hit FROM r WHERE id = ? LIMIT 1`).get(from, to);
  return !!row;
}

// Узел заблокирован, если его блокирует незакрытый узел (подтверждённая связь)
export function blockedSet(db) {
  const rows = db.prepare(`
    SELECT DISTINCT l.to_id AS id FROM links l
    JOIN nodes p ON p.id = l.from_id
    WHERE l.type = 'blocks'
      AND NOT (p.status IN ('done','accepted'))`).all();
  return new Set(rows.map(r => r.id));
}

export function listTree(db) {
  const blocked = blockedSet(db);
  return {
    nodes: db.prepare('SELECT * FROM nodes ORDER BY parent_id NULLS FIRST, ord').all()
      .map(t => ({ ...t, blocked: blocked.has(t.id) })),
    links: db.prepare('SELECT * FROM links').all(),
  };
}

// ===== Подсказки (ничего не сохраняют — только предлагают) =====

const VERBS = /^(понять|продать|купить|найти|находим|написать|посмотреть|посмотрим|использовать|сделать|назначить|подумать|сформулирую|формулирую|изучить|закрыть|общаемся|ведем|ведём|завести|положить|оплатить|проверить|узнать|записаться|выбрать|решить)/i;
const DECIS = /^(стоит ли|как мы|что лучше|или\b)/i;
const WORRY = /(боюсь|страшно|тревож|переживаю|волнуюсь|а вдруг|а если)/i;

export function suggestKind(title) {
  const t = title.trim();
  if (WORRY.test(t)) return 'worry';
  if (DECIS.test(t)) return 'decision';
  if (/\?\s*$/.test(t)) return 'question';
  const letters = t.replace(/[^а-яёa-z]/gi, '');
  const upper = t.replace(/[^А-ЯЁA-Z]/g, '');
  if (letters.length >= 5 && upper.length / letters.length > 0.7) return 'principle';
  if (VERBS.test(t)) return 'task';
  return null;
}

const MONTHS = { 'январ':1,'феврал':2,'март':3,'апрел':4,'ма[йя]':5,'июн':6,
                 'июл':7,'август':8,'сентябр':9,'октябр':10,'ноябр':11,'декабр':12 };

export function suggestDate(title, now = new Date()) {
  const t = title.toLowerCase();
  const until = t.match(/до\s+(20\d\d)/);
  if (until) return { date: `${+until[1] - 1}-12-31`, reason: `в тексте: «до ${until[1]}»` };
  for (const [pat, m] of Object.entries(MONTHS)) {
    // \b не работает с кириллицей — граница слова вручную
    if (new RegExp(`(?:^|[^а-яёa-z])(?:${pat})`).test(t)) {
      let y = now.getFullYear();
      if (m < now.getMonth() + 1) y += 1;
      const last = new Date(y, m, 0).getDate();
      return { date: `${y}-${String(m).padStart(2, '0')}-${last}`,
               reason: `в тексте найден месяц` };
    }
  }
  return null;
}

export function ancestorIds(db, id) {
  const out = [];
  let cur = getNode(db, id);
  while (cur?.parent_id) { out.push(cur.parent_id); cur = getNode(db, cur.parent_id); }
  return out;
}

function descendantIds(db, id) {
  return db.prepare(`
    WITH RECURSIVE r(id) AS (
      SELECT id FROM nodes WHERE parent_id = ?
      UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.id
    ) SELECT id FROM r`).all(id).map(r => r.id);
}

// Предложения для узла: тип, дата, связи-кандидаты с причиной
export function suggestForNode(db, id) {
  const t = getNode(db, id);
  if (!t) return null;

  const family = new Set([id, ...ancestorIds(db, id), ...descendantIds(db, id)]);
  const linked = new Set(db.prepare(
    'SELECT from_id AS x FROM links WHERE to_id = ? UNION SELECT to_id FROM links WHERE from_id = ?')
    .all(id, id).map(r => r.x));
  const dism = new Set(db.prepare('SELECT a, b FROM dismissed').all()
    .flatMap(r => (r.a === id || r.b === id) ? [r.a === id ? r.b : r.a] : []));

  const myToks = tokens(t.title + ' ' + t.note);
  let candidates = [];
  if (myToks.length) {
    const q = myToks.map(x => `"${x.replaceAll('"', '')}"`).join(' OR ');
    candidates = db.prepare(`
      SELECT n.*, bm25(node_fts) AS rank FROM node_fts
      JOIN nodes n ON n.id = node_fts.rowid
      WHERE node_fts MATCH ? ORDER BY rank LIMIT 20`).all(q)
      .filter(c => !family.has(c.id) && !linked.has(c.id) && !dism.has(c.id))
      .map(c => {
        const common = tokens(c.title + ' ' + c.note).filter(x => myToks.includes(x));
        // показываем слова в исходном виде, а не нормализованные
        const raw = (t.title + ' ' + t.note).toLowerCase().split(/[^a-zа-яё0-9]+/u).filter(Boolean);
        const disp = [...new Set(raw.filter(w => common.includes(norm(w))))];
        return { node: c, reason: 'совпадение: ' + (disp.length ? disp : common).slice(0, 4).join(', '), kind: 'mention' };
      })
      .filter(c => c.reason.length > 12);
  }

  // близость по датам (если у обоих стоят сроки)
  if (t.due_date) {
    const near = db.prepare(`
      SELECT * FROM nodes WHERE due_date IS NOT NULL AND id != ?
        AND abs(julianday(due_date) - julianday(?)) <= 60`).all(id, t.due_date)
      .filter(c => !family.has(c.id) && !linked.has(c.id) && !dism.has(c.id))
      .map(c => ({ node: c, reason: `дата рядом: ${c.due_date}`, kind: 'time' }));
    candidates.push(...near);
  }

  const seen = new Set();
  candidates = candidates.filter(c => !seen.has(c.node.id) && seen.add(c.node.id)).slice(0, 8);

  // Контекст ветки (информационно, не связи): принципы и открытые решения
  // Ветка = поддерево верхнего не-категорийного предка
  let branchRoot = t;
  while (branchRoot.parent_id) {
    const p = getNode(db, branchRoot.parent_id);
    if (!p || p.is_category) break;
    branchRoot = p;
  }
  const branchIds = new Set([branchRoot.id, ...descendantIds(db, branchRoot.id)]);
  branchIds.delete(id);
  const inBranch = rows => rows.filter(r => branchIds.has(r.id));
  const context = {
    principles: inBranch(db.prepare(`SELECT * FROM nodes WHERE kind = 'principle'`).all()),
    decisions: inBranch(db.prepare(`SELECT * FROM nodes WHERE kind = 'decision' AND status = 'open'`).all()),
    // финансовые платежи рядом по времени (окно ±60 дней от срока записи)
    payments: t.due_date ? db.prepare(`
      SELECT * FROM obligations WHERE next_date IS NOT NULL
        AND abs(julianday(next_date) - julianday(?)) <= 60 ORDER BY next_date`).all(t.due_date) : [],
  };

  return {
    node: t,
    kind: t.kind ? null : suggestKind(t.title),
    date: t.due_date ? null : suggestDate(t.title),
    links: candidates,
    context,
    confirmed: db.prepare(`
      SELECT l.id AS link_id, l.type, l.from_id, l.to_id, n.title, n.status, n.kind AS nkind
      FROM links l JOIN nodes n ON n.id = CASE WHEN l.from_id = ? THEN l.to_id ELSE l.from_id END
      WHERE l.from_id = ? OR l.to_id = ?`).all(id, id, id),
  };
}

export function search(db, q) {
  const toks = tokens(q);
  if (!toks.length) return [];
  const match = toks.map(x => `"${x.replaceAll('"', '')}"*`).join(' ');
  return db.prepare(`
    SELECT n.* FROM node_fts JOIN nodes n ON n.id = node_fts.rowid
    WHERE node_fts MATCH ? ORDER BY bm25(node_fts) LIMIT 20`).all(match);
}

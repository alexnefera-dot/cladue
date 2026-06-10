import { norm, tokens } from './db.js';

export function createTask(db, o) {
  db.prepare(`INSERT INTO tasks(title, note, kind, status, priority, due_date, parent_id, goal_id)
    VALUES(?,?,?,?,?,?,?,?)`)
    .run(o.title, o.note ?? '', o.kind ?? 'task',
         o.kind === 'decision' ? 'open' : 'todo',
         o.priority ?? null, o.due_date ?? null, o.parent_id ?? null, o.goal_id ?? null);
  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  db.prepare('INSERT INTO task_fts(rowid, title_norm, note_norm) VALUES(?,?,?)')
    .run(id, norm(o.title), norm(o.note ?? ''));
  return getTask(db, id);
}

export function getTask(db, id) {
  return db.prepare('SELECT * FROM tasks WHERE id = ?').get(id);
}

const PATCHABLE = ['title', 'note', 'status', 'priority', 'due_date', 'goal_id', 'parent_id'];

export function updateTask(db, id, fields) {
  const keys = Object.keys(fields).filter(k => PATCHABLE.includes(k));
  if (!keys.length) return getTask(db, id);
  const sets = keys.map(k => `${k} = ?`).join(', ');
  db.prepare(`UPDATE tasks SET ${sets}, updated_at = datetime('now') WHERE id = ?`)
    .run(...keys.map(k => fields[k]), id);
  if (keys.includes('title') || keys.includes('note')) {
    const t = getTask(db, id);
    db.prepare('UPDATE task_fts SET title_norm = ?, note_norm = ? WHERE rowid = ?')
      .run(norm(t.title), norm(t.note), id);
  }
  return getTask(db, id);
}

export function toggleTask(db, id) {
  const t = getTask(db, id);
  if (!t) return null;
  const next = t.kind === 'decision'
    ? (t.status === 'open' ? 'accepted' : 'open')
    : (t.status === 'done' ? 'todo' : 'done');
  return updateTask(db, id, { status: next });
}

export function addDep(db, predecessor_id, successor_id, type = 'blocks') {
  if (predecessor_id === successor_id) throw new Error('self-dependency');
  if (reaches(db, successor_id, predecessor_id)) throw new Error('cycle');
  db.prepare('INSERT OR IGNORE INTO deps(predecessor_id, successor_id, type) VALUES(?,?,?)')
    .run(predecessor_id, successor_id, type);
}

function reaches(db, from, to) {
  const row = db.prepare(`
    WITH RECURSIVE r(id) AS (
      SELECT successor_id FROM deps WHERE predecessor_id = ?
      UNION SELECT d.successor_id FROM deps d JOIN r ON d.predecessor_id = r.id
    ) SELECT 1 AS hit FROM r WHERE id = ? LIMIT 1`).get(from, to);
  return !!row;
}

// Задача заблокирована, если есть незакрытый предшественник (blocks/decision)
export function blockedSet(db) {
  const rows = db.prepare(`
    SELECT DISTINCT d.successor_id AS id FROM deps d
    JOIN tasks p ON p.id = d.predecessor_id
    WHERE d.type IN ('blocks','decision')
      AND ((p.kind = 'decision' AND p.status != 'accepted')
        OR (p.kind != 'decision' AND p.status != 'done'))`).all();
  return new Set(rows.map(r => r.id));
}

export function listState(db) {
  const blocked = blockedSet(db);
  return {
    goals: db.prepare('SELECT * FROM goals ORDER BY priority, id').all(),
    tasks: db.prepare('SELECT * FROM tasks ORDER BY id').all()
      .map(t => ({ ...t, blocked: blocked.has(t.id) })),
    deps: db.prepare('SELECT * FROM deps').all(),
  };
}

// ===== Радар блокеров =====
export function radar(db, id) {
  const t = getTask(db, id);
  if (!t) return null;

  const blockers = db.prepare(`
    SELECT p.*, d.type AS dep_type FROM deps d JOIN tasks p ON p.id = d.predecessor_id
    WHERE d.successor_id = ?
      AND ((p.kind = 'decision' AND p.status != 'accepted')
        OR (p.kind != 'decision' AND p.status != 'done'))`).all(id);

  const blocks = db.prepare(`
    SELECT s.*, d.type AS dep_type FROM deps d JOIN tasks s ON s.id = d.successor_id
    WHERE d.predecessor_id = ?`).all(id);

  // Упоминания: FTS по значимым словам названия+заметки (гомоглифы нормализованы)
  let mentions = [];
  const toks = tokens(t.title + ' ' + t.note);
  if (toks.length) {
    const q = toks.map(x => `"${x.replaceAll('"', '')}"`).join(' OR ');
    mentions = db.prepare(`
      SELECT tk.*, bm25(task_fts) AS rank FROM task_fts
      JOIN tasks tk ON tk.id = task_fts.rowid
      WHERE task_fts MATCH ? AND tk.id != ? AND tk.parent_id IS NOT ?
      ORDER BY rank LIMIT 8`).all(q, id, id)
      .filter(m => m.id !== t.parent_id);
  }

  // Окно времени ±60 дней
  let timeWindow = [];
  if (t.due_date) {
    timeWindow = db.prepare(`
      SELECT * FROM tasks
      WHERE due_date IS NOT NULL AND id != ? AND status NOT IN ('done','accepted')
        AND abs(julianday(due_date) - julianday(?)) <= 60
      ORDER BY due_date LIMIT 8`).all(id, t.due_date);
  }

  // Открытые решения той же цели (не связанные напрямую — те уже в blockers)
  const decisions = db.prepare(`
    SELECT * FROM tasks WHERE kind = 'decision' AND status = 'open'
      AND goal_id IS ? AND id != ?
      AND id NOT IN (SELECT predecessor_id FROM deps WHERE successor_id = ?)`)
    .all(t.goal_id, id, id);

  // Принципы ветки (та же цель)
  const principles = db.prepare(`
    SELECT * FROM tasks WHERE kind = 'principle' AND goal_id IS ? AND id != ?`)
    .all(t.goal_id, id);

  return { task: t, blockers, blocks, mentions, timeWindow, decisions, principles };
}

export function search(db, q) {
  const toks = tokens(q);
  if (!toks.length) return [];
  const match = toks.map(x => `"${x.replaceAll('"', '')}"*`).join(' ');
  return db.prepare(`
    SELECT tk.* FROM task_fts JOIN tasks tk ON tk.id = task_fts.rowid
    WHERE task_fts MATCH ? ORDER BY bm25(task_fts) LIMIT 20`).all(match);
}

import { DatabaseSync } from 'node:sqlite';

// Гомоглифы: кириллица ↔ латиница, чтобы «х5» находило «X5»
const HOMO = { 'а':'a','е':'e','о':'o','с':'c','р':'p','х':'x','у':'y','к':'k','в':'b','м':'m','т':'t' };
export function norm(s) {
  return String(s).toLowerCase().replace(/[аеосрхукмвт]/g, ch => HOMO[ch] ?? ch);
}

const STOP = new Set(['и','в','на','с','по','за','до','от','для','не','что','как','это','или',
  'у','мы','я','к','о','же','бы','из','со','свой','наш','еще','ещё','при','то','ли',
  'the','to','of','and','a','in','is','for','on']);

export function tokens(s) {
  return [...new Set(norm(s).split(/[^a-z0-9а-яё]+/u).filter(t => t.length >= 2 && !STOP.has(t)))];
}

export function createDb(path = ':memory:') {
  const db = new DatabaseSync(path);
  db.exec(`
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS goals(
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      kind TEXT NOT NULL DEFAULT 'regular',   -- global|direction|energy|regular
      parent_id INTEGER REFERENCES goals(id),
      priority TEXT                            -- P1..P5 из жизненного списка
    );
    CREATE TABLE IF NOT EXISTS tasks(
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      kind TEXT NOT NULL DEFAULT 'task',       -- task|decision|question|principle|idea
      status TEXT NOT NULL DEFAULT 'todo',     -- task: todo|done · decision: open|accepted
      priority TEXT,                           -- P0..P3
      due_date TEXT,
      parent_id INTEGER REFERENCES tasks(id),
      goal_id INTEGER REFERENCES goals(id),
      source_line TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS deps(
      id INTEGER PRIMARY KEY,
      predecessor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      successor_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
      type TEXT NOT NULL DEFAULT 'blocks',     -- blocks|decision|complements
      UNIQUE(predecessor_id, successor_id, type)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS task_fts USING fts5(title_norm, note_norm);
  `);
  return db;
}

export function seed(db) {
  const g = (title, priority, kind = 'regular') => {
    db.prepare('INSERT INTO goals(title, priority, kind) VALUES(?,?,?)').run(title, priority, kind);
    return db.prepare('SELECT last_insert_rowid() AS id').get().id;
  };
  const t = (o) => {
    db.prepare(`INSERT INTO tasks(title, note, kind, status, priority, due_date, parent_id, goal_id, source_line)
      VALUES(?,?,?,?,?,?,?,?,?)`)
      .run(o.title, o.note ?? '', o.kind ?? 'task', o.status ?? (o.kind === 'decision' ? 'open' : 'todo'),
           o.priority ?? null, o.due ?? null, o.parent ?? null, o.goal ?? null, o.src ?? null);
    const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
    db.prepare('INSERT INTO task_fts(rowid, title_norm, note_norm) VALUES(?,?,?)')
      .run(id, norm(o.title), norm(o.note ?? ''));
    return id;
  };
  const dep = (pre, suc, type = 'blocks') =>
    db.prepare('INSERT INTO deps(predecessor_id, successor_id, type) VALUES(?,?,?)').run(pre, suc, type);

  const gAuto = g('Авто', 'P4');
  const gHealth = g('Здоровье / Стабильно', 'P5');
  const gFin = g('Финансы (тест)', 'P2');

  // — Авто → SK
  const tVnzh = t({ goal: gAuto, title: 'Узнать сроки ВНЖ (Наталья ~январь; мой — ?)', priority: 'P2', due: '2027-01-15', src: 'Авто→SK→1' });
  const dResid = t({ goal: gAuto, kind: 'decision', title: 'Резидентство SK?', note: 'Зависит от ВНЖ', src: 'Авто→SK' });
  const dBuySK = t({ goal: gAuto, kind: 'decision', title: 'Покупка авто в SK: бюджет и цель', src: 'Авто→SK→2' });
  t({ goal: gAuto, kind: 'question', parent: dBuySK, title: 'Использовать баланс e46 или заводить деньги?', src: 'Авто→SK→3' });
  dep(dResid, dBuySK, 'decision');

  // — Авто → X5
  const tSellX5 = t({ goal: gAuto, title: 'Продать X5', priority: 'P1', due: '2026-08-31',
    note: 'Дедлайн ужесточён: до росписи (контекст Семья). Налоги и транш — см. радар.', src: 'Авто→X5→1' });
  t({ goal: gAuto, parent: tSellX5, title: 'Написать автобизнесменам: условия и рынок', priority: 'P2', src: 'Авто→X5→2' });
  t({ goal: gAuto, kind: 'principle', title: '10k с продажи X5 → резерв «легализация MX5»', src: 'Авто→X5→3' });
  const dHalf = t({ goal: gAuto, kind: 'decision', title: 'Половину от продажи X5 — Наталье?', src: 'Авто→X5→4' });

  // — Авто → MX5
  t({ goal: gAuto, title: 'Изучить: сколько можно ездить на MX5 по закону', priority: 'P3', src: 'Авто→MX5→1' });
  t({ goal: gAuto, kind: 'principle', title: 'MX5: НЕ СПЕШИМ до 2028', src: 'Авто→MX5→2' });
  const tCustoms = t({ goal: gAuto, title: 'Растаможка/замена MX5 на местный аналог', priority: 'P3', src: 'Авто→MX5→3' });
  dep(dResid, tCustoms, 'decision');

  // — Здоровье → Семья
  const tContract = t({ goal: gHealth, title: 'Консультация по договору (накопления / подарки / наследство)', priority: 'P1', due: '2026-07-10', src: 'Семья→2' });
  dep(tContract, dHalf, 'blocks');
  t({ goal: gHealth, title: 'Назначать даты заранее (ежемесячно)', priority: 'P2', src: 'Семья→3' });
  t({ goal: gHealth, kind: 'idea', title: 'Продумать, как провести дату и что видеть', src: 'Семья→3' });

  // — Финансы (для окна времени радара)
  t({ goal: gFin, title: 'Закрыть налоги за 2025', priority: 'P0', due: '2026-08-15', src: 'Финансы' });
  t({ goal: gFin, title: 'Транш за квартиру', priority: 'P1', due: '2026-09-05', src: 'Финансы' });
}

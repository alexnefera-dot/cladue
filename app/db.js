import { DatabaseSync } from 'node:sqlite';

// Гомоглифы: кириллица ↔ латиница, чтобы «х5» находило «X5»
const HOMO = { 'а':'a','е':'e','о':'o','с':'c','р':'p','х':'x','у':'y','к':'k','в':'b','м':'m','т':'t' };
export function norm(s) {
  return String(s).toLowerCase().replace(/[аеосрхукмвт]/g, ch => HOMO[ch] ?? ch);
}

const STOP = new Set(['и','в','на','с','по','за','до','от','для','не','что','как','это','или',
  'у','мы','я','к','о','же','бы','из','со','свой','наш','еще','ещё','при','то','ли','если',
  'есть','будет','надо','чтоб','чтобы','когда','раз','the','to','of','and','a','in','is']);

export function tokens(s) {
  return [...new Set(norm(s).split(/[^a-z0-9а-яё]+/u).filter(t => t.length >= 2 && !STOP.has(t)))];
}

export function createDb(path = ':memory:') {
  const db = new DatabaseSync(path);
  db.exec(`
    PRAGMA foreign_keys = ON;
    -- Узел аутлайна. is_category=1 — узел твоей рубрикации (Финансы, Жизнь…)
    CREATE TABLE IF NOT EXISTS nodes(
      id INTEGER PRIMARY KEY,
      parent_id INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
      ord INTEGER NOT NULL,
      title TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      is_category INTEGER NOT NULL DEFAULT 0,
      kind TEXT,                               -- NULL|task|decision|question|principle|idea|worry
      status TEXT,
      priority TEXT,
      due_date TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS links(
      id INTEGER PRIMARY KEY,
      from_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
      to_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
      type TEXT NOT NULL DEFAULT 'related',
      UNIQUE(from_id, to_id, type)
    );
    CREATE TABLE IF NOT EXISTS dismissed(
      a INTEGER NOT NULL,
      b INTEGER NOT NULL,
      UNIQUE(a, b)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(title_norm, note_norm);
  `);
  // миграция существующих баз
  const cols = db.prepare('PRAGMA table_info(nodes)').all().map(c => c.name);
  if (!cols.includes('answer')) db.exec('ALTER TABLE nodes ADD COLUMN answer TEXT');
  return db;
}

export function insertNode(db, parent_id, title, { note = '', is_category = 0 } = {}) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord), 0) + 1 AS o FROM nodes WHERE parent_id IS ?')
    .get(parent_id).o;
  db.prepare('INSERT INTO nodes(parent_id, ord, title, note, is_category) VALUES(?,?,?,?,?)')
    .run(parent_id, ord, title, note, is_category);
  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  db.prepare('INSERT INTO node_fts(rowid, title_norm, note_norm) VALUES(?,?,?)')
    .run(id, norm(title), norm(note));
  return id;
}

// Категории пользователя — его рубрикация жизни. Внутрь он раскидывает импорт.
export function seed(db) {
  const cat = (parent, title) => insertNode(db, parent, title, { is_category: 1 });

  cat(null, '📥 Инбокс');

  const fin = cat(null, 'Финансы');
  for (const c of ['Налоги', 'Платежи', 'Балансы', 'Траты', 'Активы', 'Пассивы']) cat(fin, c);

  const leg = cat(null, 'Легализация');
  cat(leg, 'ВНЖ');

  const work = cat(null, 'Работа');
  for (const c of ['Рост', 'Проекты']) cat(work, c);

  const life = cat(null, 'Жизнь');
  for (const c of ['Семья', 'Развитие', 'Здоровье', 'Отдых']) cat(life, c);

  const hist = cat(null, 'История и расчёты');
  for (const c of ['Налоговые расчёты', 'История']) cat(hist, c);

  const fears = cat(null, 'Страхи / Вопросы');
  const trev = cat(fears, 'Тревоги');
  for (const c of ['Налоги', 'Покупки', 'ВНЖ', 'Балансы', 'Брокеры', 'Семья', 'Работа', 'Принятые'])
    cat(trev, c);

  cat(null, 'Глобальные цели');
}

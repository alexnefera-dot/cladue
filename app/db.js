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

    -- ===== Финансы (этап 2) =====
    CREATE TABLE IF NOT EXISTS accounts(
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      type TEXT NOT NULL DEFAULT 'bank',       -- bank|broker|cash|crypto|deposit|safe
      currency TEXT NOT NULL DEFAULT '₽',
      balance REAL NOT NULL DEFAULT 0,
      balance_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS portfolio_classes(
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      value REAL NOT NULL DEFAULT 0,           -- текущая стоимость (вручную, v1)
      target_pct REAL NOT NULL DEFAULT 0,      -- целевая доля %
      ord INTEGER NOT NULL DEFAULT 0,
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS steps(           -- план шагов: покупки/продажи/переводы
      id INTEGER PRIMARY KEY,
      kind TEXT NOT NULL DEFAULT 'buy',        -- buy|sell|transfer
      title TEXT NOT NULL,
      amount REAL,
      planned_date TEXT,
      condition TEXT NOT NULL DEFAULT '',      -- «после зарплаты», «BTC > 120k»
      status TEXT NOT NULL DEFAULT 'planned',  -- planned|done
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS obligations(     -- обязательства и подписки
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      amount REAL NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT '₽',
      period TEXT NOT NULL DEFAULT 'monthly',  -- monthly|yearly|once
      next_date TEXT,
      remind_days INTEGER NOT NULL DEFAULT 5,
      kind TEXT NOT NULL DEFAULT 'liability',  -- liability|subscription
      note TEXT NOT NULL DEFAULT ''
    );
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

// Тестовое наполнение финансов (легко удалить из интерфейса)
export function seedFin(db) {
  const acc = db.prepare('INSERT INTO accounts(name, type, currency, balance, balance_updated_at) VALUES(?,?,?,?,?)');
  acc.run('Брокер А (пример)', 'broker', '₽', 5030000, new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10));
  acc.run('Карта банк (пример)', 'bank', '₽', 312300, new Date().toISOString().slice(0, 10));
  acc.run('Вклад $ (пример)', 'deposit', '$', 12000, new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10));

  const cls = db.prepare('INSERT INTO portfolio_classes(name, value, target_pct, ord) VALUES(?,?,?,?)');
  cls.run('ETF акции (пример)', 3950000, 50, 1);
  cls.run('Облигации (пример)', 2100000, 30, 2);
  cls.run('BTC (пример)', 980000, 10, 3);
  cls.run('Кэш (пример)', 1382300, 10, 4);

  db.prepare(`INSERT INTO steps(kind, title, amount, planned_date, condition) VALUES
    ('buy', 'Докупить облигации (пример)', 300000, NULL, 'после зарплаты'),
    ('sell', 'Продать часть BTC (пример)', 150000, NULL, 'BTC > $120k')`).run();

  const today = new Date();
  const iso = d => d.toISOString().slice(0, 10);
  const obl = db.prepare('INSERT INTO obligations(name, amount, period, next_date, remind_days, kind) VALUES(?,?,?,?,?,?)');
  obl.run('Кредит авто (пример)', 38000, 'monthly', iso(new Date(today.getTime() + 3 * 864e5)), 5, 'liability');
  obl.run('Аренда ячейки (пример)', 12000, 'yearly', iso(new Date(today.getTime() + 20 * 864e5)), 7, 'liability');
  obl.run('iCloud+ (пример)', 999, 'monthly', iso(new Date(today.getTime() + 1 * 864e5)), 2, 'subscription');
}

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
      currency TEXT NOT NULL DEFAULT '€',
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
      currency TEXT NOT NULL DEFAULT '€',
      period TEXT NOT NULL DEFAULT 'monthly',  -- monthly|yearly|once
      next_date TEXT,
      remind_days INTEGER NOT NULL DEFAULT 5,
      kind TEXT NOT NULL DEFAULT 'liability',  -- liability|subscription
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS portfolio_items( -- блоки → разделы → активы
      id INTEGER PRIMARY KEY,
      parent_id INTEGER REFERENCES portfolio_items(id) ON DELETE CASCADE,
      ord INTEGER NOT NULL DEFAULT 0,
      name TEXT NOT NULL,
      kind TEXT NOT NULL DEFAULT 'asset',      -- block|section|asset
      buy_value REAL,                          -- цена покупки (опционально)
      value REAL,                              -- текущая стоимость
      target_value REAL,                       -- целевой портфель (отдельная ось)
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS rates(           -- курсы: авто (stooq) или вручную
      symbol TEXT PRIMARY KEY,
      label TEXT,
      price REAL,
      change_pct REAL,
      updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS events(          -- свои события: ДР, встречи, напоминания
      id INTEGER PRIMARY KEY,
      title TEXT NOT NULL,
      date TEXT NOT NULL,                      -- первая дата
      time TEXT,                               -- HH:MM, опционально
      recur TEXT NOT NULL DEFAULT 'none',      -- none|monthly|yearly
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS transactions(    -- расходы/доходы (вручную или Monefy)
      id INTEGER PRIMARY KEY,
      date TEXT NOT NULL,
      amount REAL NOT NULL,                    -- всегда положительное
      currency TEXT NOT NULL DEFAULT '€',
      direction TEXT NOT NULL DEFAULT 'expense', -- expense|income
      category TEXT NOT NULL DEFAULT 'прочее',
      note TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL DEFAULT 'manual'    -- manual|monefy
    );
    CREATE TABLE IF NOT EXISTS receivables(     -- дебиторка: невыплаченные доходы
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      amount REAL NOT NULL,
      currency TEXT NOT NULL DEFAULT '€',
      expected_date TEXT,
      status TEXT NOT NULL DEFAULT 'waiting',  -- waiting|received
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT
    );
    CREATE TABLE IF NOT EXISTS macro_notes(     -- макро-тезисы с историей
      id INTEGER PRIMARY KEY,
      date TEXT NOT NULL DEFAULT (date('now')),
      phase TEXT NOT NULL DEFAULT '',          -- рост|пик|сжатие|дно
      thesis TEXT NOT NULL DEFAULT ''
    );
  `);
  // миграция существующих баз
  const cols = db.prepare('PRAGMA table_info(nodes)').all().map(c => c.name);
  if (!cols.includes('answer')) db.exec('ALTER TABLE nodes ADD COLUMN answer TEXT');
  // рубли убраны: всё в € (доллар — по желанию на конкретной записи)
  db.exec(`UPDATE accounts SET currency = '€' WHERE currency = '₽'`);
  db.exec(`UPDATE obligations SET currency = '€' WHERE currency = '₽'`);
  // бивалютный портфель: у актива своя валюта € или $
  const pcols = db.prepare('PRAGMA table_info(portfolio_items)').all().map(c => c.name);
  if (!pcols.includes('currency')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN currency TEXT NOT NULL DEFAULT '€'`);
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
  acc.run('Брокер А (пример)', 'broker', '€', 50300, new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10));
  acc.run('Карта банк (пример)', 'bank', '€', 3120, new Date().toISOString().slice(0, 10));
  acc.run('Вклад $ (пример)', 'deposit', '$', 12000, new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10));

  db.prepare(`INSERT INTO steps(kind, title, amount, planned_date, condition) VALUES
    ('buy', 'Докупить облигации (пример)', 30000, NULL, 'после зарплаты'),
    ('sell', 'Продать часть BTC (пример)', 15000, NULL, 'BTC > $120k')`).run();

  const today = new Date();
  const iso = d => d.toISOString().slice(0, 10);
  const obl = db.prepare('INSERT INTO obligations(name, amount, currency, period, next_date, remind_days, kind) VALUES(?,?,?,?,?,?,?)');
  obl.run('Кредит авто (пример)', 380, '€', 'monthly', iso(new Date(today.getTime() + 3 * 864e5)), 5, 'liability');
  obl.run('Аренда ячейки (пример)', 120, '€', 'yearly', iso(new Date(today.getTime() + 20 * 864e5)), 7, 'liability');
  obl.run('iCloud+ (пример)', 9.99, '€', 'monthly', iso(new Date(today.getTime() + 1 * 864e5)), 2, 'subscription');
}

// Каркас портфеля: 4 блока + пример из заметок пользователя
export function ensurePortfolio(db) {
  if (db.prepare('SELECT count(*) AS c FROM portfolio_items').get().c > 0) return;
  const ins = (parent, name, kind, vals = {}) => {
    const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_items WHERE parent_id IS ?').get(parent).o;
    db.prepare('INSERT INTO portfolio_items(parent_id, ord, name, kind, buy_value, value, target_value) VALUES(?,?,?,?,?,?,?)')
      .run(parent, ord, name, kind, vals.buy ?? null, vals.value ?? null, vals.target ?? null);
    return db.prepare('SELECT last_insert_rowid() AS id').get().id;
  };
  ins(null, 'Блок защиты', 'block');
  ins(null, 'Блок роста', 'block');
  ins(null, 'Блок развития', 'block');
  const frozen = ins(null, 'Замороженный капитал', 'block');
  const re = ins(frozen, 'Недвижимость', 'section');
  ins(re, 'Start', 'asset', { value: 100000 });
  ins(re, 'Belgravia', 'asset', { value: 300000 });
  const pas = ins(frozen, 'Пассивы', 'section');
  ins(pas, 'X5', 'asset', { value: 45000 });
  ins(pas, 'MX5', 'asset', { value: 30000 });
}

// Строки курсов, чтобы их можно было править вручную даже без сети
export function ensureRates(db) {
  const defs = [['XAUUSD', 'Золото'], ['EURUSD', 'EUR/USD'], ['BTCUSD', 'BTC'], ['^SPX', 'S&P 500']];
  for (const [sym, label] of defs)
    db.prepare('INSERT OR IGNORE INTO rates(symbol, label) VALUES(?,?)').run(sym, label);
}

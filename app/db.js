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
    CREATE TABLE IF NOT EXISTS event_done(      -- закрытые («выполнено») даты событий — повтор НЕ удаляется
      event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
      date TEXT NOT NULL,
      UNIQUE(event_id, date)
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
    CREATE TABLE IF NOT EXISTS passive_income( -- пассивный доход: аренда, депозиты, дивиденды
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      amount REAL NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT '€',
      period TEXT NOT NULL DEFAULT 'monthly',  -- monthly|yearly|once
      next_date TEXT,
      note TEXT NOT NULL DEFAULT '',
      principal REAL NOT NULL DEFAULT 0,        -- сумма инвестиции/депозита
      rate REAL NOT NULL DEFAULT 0,             -- % доходности
      rate_period TEXT NOT NULL DEFAULT 'yearly', -- период ставки: yearly|monthly
      asset_type TEXT NOT NULL DEFAULT ''       -- тип актива (депозит, аренда, дивиденды…)
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
    CREATE TABLE IF NOT EXISTS debts(           -- долги: мои и мне, вне портфеля
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      amount REAL NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT '€',
      direction TEXT NOT NULL DEFAULT 'owed_to_me', -- owed_to_me|i_owe
      due_date TEXT,
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS snapshots(       -- история нетворса, раз в день
      date TEXT PRIMARY KEY,
      portfolio_eur REAL
    );
    CREATE TABLE IF NOT EXISTS routines(        -- рутины: отдельно от задач, без чувства вины
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      slot TEXT NOT NULL DEFAULT 'утро',       -- утро|день|вечер
      ord INTEGER NOT NULL DEFAULT 0,
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS routine_log(     -- отметки по дням
      routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
      date TEXT NOT NULL,
      UNIQUE(routine_id, date)
    );
    CREATE TABLE IF NOT EXISTS people(          -- люди: ДР и контакт-ритм
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      birthday TEXT,                           -- YYYY-MM-DD или MM-DD
      rhythm_days INTEGER,                     -- желаемая частота контакта
      last_contact TEXT,
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS contact_log(     -- записи после встреч/созвонов
      id INTEGER PRIMARY KEY,
      person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
      date TEXT NOT NULL DEFAULT (date('now')),
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS pages(           -- Инфо: страницы-заметки (наш Notion)
      id INTEGER PRIMARY KEY,
      parent_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
      ord INTEGER NOT NULL DEFAULT 0,
      title TEXT NOT NULL,
      content TEXT NOT NULL DEFAULT '',        -- markdown + [[вики-ссылки]]
      node_id INTEGER,                         -- «План» задачи: страница привязана к записи
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS page_revisions(
      id INTEGER PRIMARY KEY,
      page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
      content TEXT NOT NULL,
      saved_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(title_norm, content_norm);
    CREATE TABLE IF NOT EXISTS attachments(    -- вложения страниц Инфо: картинки/PDF (base64, хранится в зашифрованной базе)
      id INTEGER PRIMARY KEY,
      page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
      name TEXT NOT NULL DEFAULT '',
      mime TEXT NOT NULL DEFAULT 'application/octet-stream',
      data TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    -- ===== Психология (этап 4) =====
    CREATE TABLE IF NOT EXISTS practices(
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      kind TEXT NOT NULL DEFAULT 'schedule',   -- schedule|technique|checklist
      days TEXT NOT NULL DEFAULT '',           -- daily|workdays|csv дней недели (пн=1)
      time TEXT,                               -- HH:MM для расписания
      steps TEXT NOT NULL DEFAULT '[]',        -- JSON: шаги техники / пункты чеклиста
      note TEXT NOT NULL DEFAULT '',
      category TEXT NOT NULL DEFAULT '',        -- обучение|мотивация|убеждения|опыт|сценарии|разное
      ord INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS practice_log(
      id INTEGER PRIMARY KEY,
      practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
      date TEXT NOT NULL DEFAULT (date('now')),
      note TEXT NOT NULL DEFAULT '',
      answers TEXT NOT NULL DEFAULT '[]'       -- JSON: ответы по шагам
    );
    CREATE TABLE IF NOT EXISTS wheel_areas(
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      ord INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS wheel_scores(
      id INTEGER PRIMARY KEY,
      date TEXT NOT NULL,
      area_id INTEGER NOT NULL REFERENCES wheel_areas(id) ON DELETE CASCADE,
      score INTEGER NOT NULL,
      UNIQUE(date, area_id)
    );
    CREATE TABLE IF NOT EXISTS work_log(
      id INTEGER PRIMARY KEY,
      date TEXT NOT NULL DEFAULT (date('now')),
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS forecasts(       -- журнал прогнозов: тренировка калибровки
      id INTEGER PRIMARY KEY,
      statement TEXT NOT NULL,
      confidence INTEGER NOT NULL,             -- уверенность, %
      due_date TEXT,
      outcome INTEGER,                         -- NULL ждём · 1 сбылось · 0 нет
      created_at TEXT NOT NULL DEFAULT (date('now')),
      resolved_at TEXT
    );
    CREATE TABLE IF NOT EXISTS properties(      -- имущество: авто, недвижимость, техника
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      category TEXT NOT NULL DEFAULT 'прочее', -- авто|недвижимость|техника|прочее
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS checkins(        -- чек-ин дня: 10 секунд, без фанатизма
      date TEXT PRIMARY KEY,
      mood INTEGER NOT NULL,                   -- 1 плохой · 2 нормальный · 3 хороший
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS metrics(         -- свои метрики: кофе, падл-часы, страницы…
      id INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      type TEXT NOT NULL DEFAULT 'number',     -- number|bool|scale (1..10)
      unit TEXT NOT NULL DEFAULT '',
      ord INTEGER NOT NULL DEFAULT 0,
      polarity TEXT NOT NULL DEFAULT 'plus',   -- plus|minus (рост = плохо)
      target REAL                              -- целевое значение (KPI)
    );
    CREATE TABLE IF NOT EXISTS metric_log(
      metric_id INTEGER NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
      date TEXT NOT NULL,
      value REAL NOT NULL,
      UNIQUE(metric_id, date)
    );
    CREATE TABLE IF NOT EXISTS node_log(        -- «Лог» задачи: датированные записи хода
      id INTEGER PRIMARY KEY,
      node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
      date TEXT NOT NULL DEFAULT (date('now')),
      note TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS trash(           -- корзина: удалённые поддеревья для восстановления
      id INTEGER PRIMARY KEY,
      kind TEXT NOT NULL,                      -- nodes|pages
      label TEXT NOT NULL,
      payload TEXT NOT NULL,                   -- JSON со строками и связями
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
  `);
  // миграция существующих баз
  const cols = db.prepare('PRAGMA table_info(nodes)').all().map(c => c.name);
  if (!cols.includes('answer')) db.exec('ALTER TABLE nodes ADD COLUMN answer TEXT');
  if (!cols.includes('repeat')) db.exec('ALTER TABLE nodes ADD COLUMN repeat TEXT'); // weekly|monthly|yearly
  if (!cols.includes('due_time')) db.exec('ALTER TABLE nodes ADD COLUMN due_time TEXT'); // время задачи HH:MM для пуша
  // рубли убраны: всё в € (доллар — по желанию на конкретной записи)
  db.exec(`UPDATE accounts SET currency = '€' WHERE currency = '₽'`);
  db.exec(`UPDATE obligations SET currency = '€' WHERE currency = '₽'`);
  // бивалютный портфель: у актива своя валюта € или $
  const pcols = db.prepare('PRAGMA table_info(portfolio_items)').all().map(c => c.name);
  if (!pcols.includes('currency')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN currency TEXT NOT NULL DEFAULT '€'`);
  // займы: актив с флагом 🤝 зеркалится в раздел «Дебиторка»
  if (!pcols.includes('is_loan')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN is_loan INTEGER NOT NULL DEFAULT 0`);
  if (!pcols.includes('loan_due')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN loan_due TEXT`);
  // тип актива: крипто|кеш|баланс|недвижка|авто|акции|золото|облигации
  if (!pcols.includes('asset_type')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN asset_type TEXT`);
  // автоцена: количество × курс (BTCUSD/XAUUSD/^SPX из полосы курсов)
  if (!pcols.includes('qty')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN qty REAL`);
  if (!pcols.includes('rate_symbol')) db.exec(`ALTER TABLE portfolio_items ADD COLUMN rate_symbol TEXT`);
  // связь шага портфеля с задачей: дедупликация в календаре и синк статусов
  const scols = db.prepare('PRAGMA table_info(steps)').all().map(c => c.name);
  if (!scols.includes('task_id')) db.exec(`ALTER TABLE steps ADD COLUMN task_id INTEGER`);
  // регламент имущества хранится как обязательство, привязанное к объекту
  const ocols = db.prepare('PRAGMA table_info(obligations)').all().map(c => c.name);
  if (!ocols.includes('property_id')) db.exec(`ALTER TABLE obligations ADD COLUMN property_id INTEGER`);
  // пассивный доход: тело инвестиции/депозита + ставка доходности (доход считается из них)
  const inccols = db.prepare('PRAGMA table_info(passive_income)').all().map(c => c.name);
  if (!inccols.includes('principal')) db.exec(`ALTER TABLE passive_income ADD COLUMN principal REAL NOT NULL DEFAULT 0`);
  if (!inccols.includes('rate')) db.exec(`ALTER TABLE passive_income ADD COLUMN rate REAL NOT NULL DEFAULT 0`);
  if (!inccols.includes('rate_period')) db.exec(`ALTER TABLE passive_income ADD COLUMN rate_period TEXT NOT NULL DEFAULT 'yearly'`);
  if (!inccols.includes('asset_type')) db.exec(`ALTER TABLE passive_income ADD COLUMN asset_type TEXT NOT NULL DEFAULT ''`);
  // планируемые рутины: хочу внести, но ещё не в расписании
  const rpl = db.prepare('PRAGMA table_info(routines)').all().map(c => c.name);
  if (!rpl.includes('planned')) db.exec(`ALTER TABLE routines ADD COLUMN planned INTEGER NOT NULL DEFAULT 0`);
  // фиксированное время рутины (HH:MM) — для сортировки и напоминаний
  const rcols = db.prepare('PRAGMA table_info(routines)').all().map(c => c.name);
  if (!rcols.includes('time')) db.exec(`ALTER TABLE routines ADD COLUMN time TEXT`);
  // полярность метрики дневника: plus — прогресс (зелёная ✓), minus — регресс (красный ✗)
  const mcols = db.prepare('PRAGMA table_info(metrics)').all().map(c => c.name);
  if (!mcols.includes('polarity')) {
    db.exec(`ALTER TABLE metrics ADD COLUMN polarity TEXT NOT NULL DEFAULT 'plus'`);
    db.prepare(`UPDATE metrics SET polarity = 'minus' WHERE name IN
      ('Ютуб при работе', 'Тревога (не в 20:00)', 'Тревога(не в 20:00)',
       'Приоритеная задача не выбрана', 'Подъем не в 10')`).run();
  }
  // целевое значение метрики (KPI). Без неё buildSpheres падал «no such column: target» → сферы ломались
  if (!mcols.includes('target')) db.exec(`ALTER TABLE metrics ADD COLUMN target REAL`);
  // категория практики: обучение/мотивация/убеждения/опыт/сценарии/разное
  const prc = db.prepare('PRAGMA table_info(practices)').all().map(c => c.name);
  if (!prc.includes('category')) db.exec(`ALTER TABLE practices ADD COLUMN category TEXT NOT NULL DEFAULT ''`);
  // чипы интересов у людей
  const ppl = db.prepare('PRAGMA table_info(people)').all().map(c => c.name);
  if (!ppl.includes('tags')) db.exec(`ALTER TABLE people ADD COLUMN tags TEXT NOT NULL DEFAULT ''`);
  // страницы под паролем: содержимое шифруется aes-256-gcm
  const pgc = db.prepare('PRAGMA table_info(pages)').all().map(c => c.name);
  if (!pgc.includes('locked')) db.exec(`ALTER TABLE pages ADD COLUMN locked INTEGER NOT NULL DEFAULT 0`);
  if (!pgc.includes('enc')) db.exec(`ALTER TABLE pages ADD COLUMN enc TEXT`);
  // колесо ради движения: идеал (10), следующий уровень и шаг по каждому сектору
  const wac = db.prepare('PRAGMA table_info(wheel_areas)').all().map(c => c.name);
  if (!wac.includes('ideal')) db.exec(`ALTER TABLE wheel_areas ADD COLUMN ideal TEXT NOT NULL DEFAULT ''`);
  if (!wac.includes('current_desc')) db.exec(`ALTER TABLE wheel_areas ADD COLUMN current_desc TEXT NOT NULL DEFAULT ''`);
  if (!wac.includes('next_desc')) db.exec(`ALTER TABLE wheel_areas ADD COLUMN next_desc TEXT NOT NULL DEFAULT ''`);
  if (!wac.includes('step')) db.exec(`ALTER TABLE wheel_areas ADD COLUMN step TEXT NOT NULL DEFAULT ''`);
  // Сферы (гибрид): тег area_id — категории Целей привязываются авто, остальное вручную.
  for (const tbl of ['nodes', 'routines', 'metrics', 'practices', 'obligations', 'people', 'pages', 'events', 'debts', 'steps']) {
    const c = db.prepare(`PRAGMA table_info(${tbl})`).all().map(x => x.name);
    if (!c.includes('area_id')) db.exec(`ALTER TABLE ${tbl} ADD COLUMN area_id INTEGER REFERENCES wheel_areas(id) ON DELETE SET NULL`);
  }
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

// Структура «Энергия жизни»: желания/впечатления — анти-шаблон. Это каркас, не демо.
export function ensureEnergy(db) {
  let energy = db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND parent_id IS NULL AND title LIKE '%Энергия жизни%'`).get()?.id;
  if (!energy) energy = insertNode(db, null, '⚡ Энергия жизни', { is_category: 1 });
  if (!db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND parent_id = ? AND title LIKE '%Банк впечатлений%'`).get(energy))
    insertNode(db, energy, 'Банк впечатлений', { is_category: 1 });
}

// Строки курсов, чтобы их можно было править вручную даже без сети
export function ensureRates(db) {
  // ^SPX заменён на ETF пользователя: SCHD / IVV / VHT
  db.prepare(`UPDATE portfolio_items SET rate_symbol = NULL WHERE rate_symbol = '^SPX'`).run();
  db.prepare(`DELETE FROM rates WHERE symbol = '^SPX'`).run();
  const defs = [['XAUUSD', 'Золото'], ['EURUSD', 'EUR/USD'], ['BTCUSD', 'BTC'],
    ['SCHD', 'SCHD'], ['IVV', 'IVV'], ['VHT', 'VHT']];
  for (const [sym, label] of defs)
    db.prepare('INSERT OR IGNORE INTO rates(symbol, label) VALUES(?,?)').run(sym, label);
}

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
    -- Узел аутлайна: структура пользователя первична. kind=NULL — обычная строка.
    CREATE TABLE IF NOT EXISTS nodes(
      id INTEGER PRIMARY KEY,
      parent_id INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
      ord INTEGER NOT NULL,                    -- порядок среди соседей, как в источнике
      title TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      kind TEXT,                               -- NULL|task|decision|question|principle|idea
      status TEXT,                             -- task: todo|done · decision: open|accepted
      priority TEXT,                           -- ставит только пользователь
      due_date TEXT,                           -- ставит только пользователь (можно из подсказки)
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    -- Связи: существуют только подтверждённые пользователем
    CREATE TABLE IF NOT EXISTS links(
      id INTEGER PRIMARY KEY,
      from_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
      to_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
      type TEXT NOT NULL DEFAULT 'related',    -- related|blocks (from блокирует to)
      UNIQUE(from_id, to_id, type)
    );
    -- Отклонённые предложения: больше не предлагать эту пару
    CREATE TABLE IF NOT EXISTS dismissed(
      a INTEGER NOT NULL,
      b INTEGER NOT NULL,
      UNIQUE(a, b)
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(title_norm, note_norm);
  `);
  return db;
}

export function insertNode(db, parent_id, title, note = '') {
  const ord = db.prepare('SELECT COALESCE(MAX(ord), 0) + 1 AS o FROM nodes WHERE parent_id IS ?')
    .get(parent_id).o;
  db.prepare('INSERT INTO nodes(parent_id, ord, title, note) VALUES(?,?,?,?)')
    .run(parent_id, ord, title, note);
  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  db.prepare('INSERT INTO node_fts(rowid, title_norm, note_norm) VALUES(?,?,?)')
    .run(id, norm(title), norm(note));
  return id;
}

// Список пользователя — ДОСЛОВНО, с его вложенностью и порядком.
// Никаких типов, приоритетов и связей: всё это система только предлагает.
export function seed(db) {
  const n = (parent, title) => insertNode(db, parent, title);

  const p4 = n(null, 'P4 — (блок выше, на скрине виден частично)');
  n(p4, 'Wise - 29 - ?');
  const mat = n(p4, 'Мать');
  n(mat, 'IB - SGOV/XEON - 50 - 2%');
  const avto = n(p4, 'Авто');
  const sk = n(avto, 'SK');
  n(sk, 'Понять, когда будет внж у Натальи - примерно январь, и у меня');
  n(sk, 'Как мы покупаем в SK? Бюджет? Цель? Что?');
  n(sk, 'Использовать баланс е46, завести деньги?');
  const x5 = n(avto, 'Х5');
  n(x5, 'Август продать х5?');
  n(x5, 'Находим автобизнесменов, написать за условия и рынок');
  n(x5, '10к с продажи откладываем на легализацию своего авто');
  n(x5, 'Стоит ли положить половину Наталье на счет ?');
  const mx5 = n(avto, 'МХ5');
  n(mx5, 'Посмотрим по закону сколько можно ездить и что делать если нельзя');
  n(mx5, 'НЕ СПЕШИМ до 2028');
  n(mx5, 'Если резидент SK, ищем опцию растаможить или поменять на аналог местный');

  const p5 = n(null, 'P5 — ЗДОРОВЬЕ / СТАБИЛЬНО');
  const fam = n(p5, 'Семья');
  n(fam, 'Формулирую, что для меня идеальные отношения, чтоб я был доволен нашим браком полностью.');
  const dog = n(fam, 'Консультация за договор');
  const vop = n(dog, 'Вопросы');
  n(vop, 'Общаемся по договору влияет ли он на покупку / есть ли нюансы накопленных или подарков и наследств');
  const dates = n(fam, 'Даты каждого');
  n(dates, 'Желательно назначить заранее, если ничем не мешает');
  n(dates, 'Подумать как бы я хотел провести дату и что видеть?');
  const dorospisi = n(fam, 'Сделать до росписи');
  n(dorospisi, 'Продать х5 до надо');
  const razv = n(p5, 'Развитие');
  const psy = n(razv, 'Психолог');
  n(psy, '1 раз в неделю');
  n(psy, '2 раза в неделю личные проработки');
  n(psy, 'Ведем дневники тревог');
  n(razv, 'Поездки');
}

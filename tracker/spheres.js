// Сферы жизни = секторы Колеса (wheel_areas) + всё, что к ним привязано.
// Гибрид-тег area_id: категории Целей привязываются и тащат свои задачи (авто),
// рутины/метрики/практики/обязательства привязываются вручную.
// Отдельного хранилища нет — всё поверх реальных таблиц Pipboy.

import { routineStreak } from './life.js';
import { practiceStreak } from './psy.js';
import { getSetting, setSetting } from './fin.js';
import { norm } from './db.js';

// Дефолтная привязка целых секций к сфере: вся секция течёт в свою сферу сама.
// (Цели — авто по категориям; Люди/Трекинг/Психология — по дефолту секции; Инфо/Рутины — вручную.)
export function getDefaults(db) {
  try { return JSON.parse(getSetting(db, 'sphere_defaults', '{}')) || {}; } catch { return {}; }
}
export function setDefault(db, kind, areaId) {
  const d = getDefaults(db);
  if (areaId == null) delete d[kind]; else d[kind] = areaId;
  setSetting(db, 'sphere_defaults', JSON.stringify(d));
  return d;
}
// Авто-разложить верхние категории Целей по сферам с совпадающим именем (нормализованно).
export function autoMapCategories(db) {
  const areas = db.prepare('SELECT id, name FROM wheel_areas').all().map(a => ({ id: a.id, n: norm(a.name) }));
  const cats = db.prepare('SELECT id, title FROM nodes WHERE is_category = 1 AND parent_id IS NULL AND area_id IS NULL').all();
  let mapped = 0;
  for (const c of cats) {
    const cn = norm(c.title);
    const hit = areas.find(a => a.n && (cn.includes(a.n) || a.n.includes(cn)));
    if (hit) { db.prepare('UPDATE nodes SET area_id = ? WHERE id = ?').run(hit.id, c.id); mapped++; }
  }
  return { mapped };
}

// Автоматизм: каждую секцию направить в подходящую сферу ПО СМЫСЛУ (без ручных тумблеров).
const AUTO_KEYS = {
  person: ['социал', 'отнош', 'друз', 'общени', 'семь', 'партн'],
  metric: ['развит', 'обучен', 'рост', 'прогресс'],
  practice: ['развит', 'обучен', 'психолог', 'осознан', 'менталь', 'смысл', 'перспектив'],
  obligation: ['деньг', 'финанс', 'инвест', 'капитал', 'быт', 'дом'],
};
export function autoConfig(db, force = false) {
  const areas = db.prepare('SELECT id, name FROM wheel_areas ORDER BY ord, id').all().map(a => ({ id: a.id, n: a.name.toLowerCase(), name: a.name }));
  const d = getDefaults(db); const report = {};
  for (const [kind, keys] of Object.entries(AUTO_KEYS)) {
    if (!force && d[kind] != null) { report[kind] = areas.find(a => a.id === d[kind])?.name ?? '(задано)'; continue; }
    let hit = null;                                   // приоритет — по порядку ключей (точный смысл раньше запасного)
    for (const k of keys) { hit = areas.find(a => a.n.includes(k)); if (hit) break; }
    if (hit) { d[kind] = hit.id; report[kind] = hit.name; } else report[kind] = null;
  }
  setSetting(db, 'sphere_defaults', JSON.stringify(d));
  const cat = autoMapCategories(db);
  return { defaults: report, categoriesMapped: cat.mapped };
}

const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const TODAY = () => iso(new Date());

// Сфера узла = area_id ближайшего предка (включая себя), у кого он задан.
function nodeAreaResolver(db) {
  const rows = db.prepare('SELECT id, parent_id, area_id FROM nodes').all();
  const byId = new Map(rows.map(r => [r.id, r]));
  const memo = new Map();
  return function resolve(id) {
    if (memo.has(id)) return memo.get(id);
    const chain = [];
    let cur = byId.get(id), area = null;
    while (cur) { chain.push(cur.id); if (cur.area_id != null) { area = cur.area_id; break; } cur = cur.parent_id != null ? byId.get(cur.parent_id) : null; }
    for (const c of chain) memo.set(c, area);
    return area;
  };
}

function metricBlock(db, m) {
  const rows = db.prepare('SELECT date, value FROM metric_log WHERE metric_id = ? ORDER BY date DESC LIMIT 7').all(m.id).reverse();
  return { id: m.id, name: m.name, unit: m.unit, type: m.type,
    v: rows.length ? rows[rows.length - 1].value : null, s: rows.map(r => r.value) };
}

export function buildSpheres(db) {
  const areas = db.prepare('SELECT * FROM wheel_areas ORDER BY ord, id').all();
  const resolve = nodeAreaResolver(db);
  const todayIso = TODAY();
  const d14 = new Date(); d14.setDate(d14.getDate() - 13); const since14 = iso(d14);

  // все задачи (для доли выполненного) + открытые (для показа)
  const allTasks = db.prepare(
    `SELECT id, title, status, due_date, priority, area_id, note FROM nodes WHERE is_category = 0`
  ).all();
  const belongs = (t, a) => resolve(t.id) === a.id || (t.note || '').includes(`сектор «${a.name}»`);
  const defaults = getDefaults(db);
  // строка WHERE: своя привязка ИЛИ (если секция по умолчанию ведёт в эту сферу) ничейные
  const whereFor = (kind, areaId) =>
    defaults[kind] === areaId ? '(area_id = ? OR area_id IS NULL)' : 'area_id = ?';

  return areas.map(a => {
    const sc = db.prepare('SELECT date, score FROM wheel_scores WHERE area_id = ? ORDER BY date DESC LIMIT 8').all(a.id);

    // задачи сферы: все (для прогресса) и открытые (для показа)
    const areaTasks = allTasks.filter(t => belongs(t, a));
    const tasksTotal = areaTasks.length;
    const tasksDone = areaTasks.filter(t => t.status === 'done').length;
    const tasks = areaTasks.filter(t => t.status !== 'done').slice(0, 10)
      .map(t => ({ id: t.id, title: t.title, done: false, due: t.due_date || null, priority: t.priority || null }));

    // рутины (ручной тег)
    const routines = db.prepare('SELECT id, name FROM routines WHERE area_id = ? ORDER BY ord, id').all(a.id).map(r => ({
      id: r.id, name: r.name, streak: routineStreak(db, r.id),
      doneToday: !!db.prepare('SELECT 1 FROM routine_log WHERE routine_id = ? AND date = ?').get(r.id, todayIso),
    }));

    // метрики (трекинг) — авто, если секция по умолчанию ведёт в эту сферу
    const tracking = db.prepare(`SELECT id, name, unit, type FROM metrics WHERE ${whereFor('metric', a.id)} ORDER BY ord, id`).all(a.id).map(m => metricBlock(db, m));

    // практики (психология) — авто по дефолту секции
    const practices = db.prepare(`SELECT * FROM practices WHERE ${whereFor('practice', a.id)} ORDER BY ord, id`).all(a.id).map(p => ({
      id: p.id, name: p.name, streak: practiceStreak(db, p),
    }));

    // люди (социализация) — авто по дефолту секции
    const people = db.prepare(`SELECT id, name, rhythm_days, last_contact FROM people WHERE ${whereFor('person', a.id)} ORDER BY id`).all(a.id).map(p => ({
      id: p.id, name: p.name, rhythm: p.rhythm_days || null, last: p.last_contact || null,
    }));

    // финансы — обязательства/подписки сферы (ручной тег)
    const fin = db.prepare('SELECT id, name, amount, currency, period, next_date FROM obligations WHERE area_id = ? ORDER BY id').all(a.id);

    // ===== живой прогресс из реальных данных (без ручного ведения) =====
    const rIds = routines.map(r => r.id);
    let adherence = null;
    if (rIds.length) {
      const marks = db.prepare(
        `SELECT count(*) AS c FROM routine_log WHERE date >= ? AND routine_id IN (${rIds.map(() => '?').join(',')})`
      ).get(since14, ...rIds).c;
      adherence = Math.min(1, marks / (rIds.length * 14));
    }
    const trends = tracking.filter(m => m.s.length >= 2)
      .map(m => ({ name: m.name, dir: Math.sign((m.s.at(-1) ?? 0) - (m.s[0] ?? 0)) }));
    const signals = [];
    if (tasksTotal) signals.push(tasksDone / tasksTotal);
    if (adherence != null) signals.push(adherence);
    const momentum = signals.length ? Math.round(signals.reduce((x, y) => x + y, 0) / signals.length * 10) : null;
    const progress = { tasksDone, tasksTotal, adherence, trends, momentum };

    return {
      id: a.id, name: a.name,
      ideal: a.ideal || '', current_desc: a.current_desc || '', next_desc: a.next_desc || '', step: a.step || '',
      score: sc[0]?.score ?? null, prev: sc[1]?.score ?? null, history: sc.map(s => s.score).reverse(),
      tasks, routines, tracking, practices, people, fin, progress,
    };
  });
}

// Все категории целей (дерево) с текущей привязкой — для экрана «Цели → сферы».
export function categories(db) {
  return db.prepare('SELECT id, title, parent_id, area_id FROM nodes WHERE is_category = 1 ORDER BY ord, id').all();
}

// Привязать/отвязать элемент к сфере. kind: routine|metric|practice|obligation|category|person
const TBL = { routine: 'routines', metric: 'metrics', practice: 'practices', obligation: 'obligations', category: 'nodes', person: 'people' };
export function assign(db, kind, id, areaId) {
  const t = TBL[kind];
  if (!t) throw new Error('unknown kind');
  db.prepare(`UPDATE ${t} SET area_id = ? WHERE id = ?`).run(areaId ?? null, id);
  return { ok: true };
}

// Что можно привязать + сферы + текущие дефолты секций (для авто-панели).
export function pool(db) {
  return {
    areas: db.prepare('SELECT id, name FROM wheel_areas ORDER BY ord, id').all(),
    defaults: getDefaults(db),
    routines: db.prepare('SELECT id, name, area_id FROM routines ORDER BY ord, id').all(),
    metrics: db.prepare('SELECT id, name, area_id FROM metrics ORDER BY ord, id').all(),
    practices: db.prepare('SELECT id, name, area_id FROM practices ORDER BY ord, id').all(),
    obligations: db.prepare('SELECT id, name, area_id FROM obligations ORDER BY id').all(),
    people: db.prepare('SELECT id, name, area_id FROM people ORDER BY id').all(),
    categories: db.prepare(`SELECT id, title, area_id FROM nodes WHERE is_category = 1 AND parent_id IS NULL ORDER BY ord, id`).all(),
  };
}

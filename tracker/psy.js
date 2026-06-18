import crypto from 'node:crypto';
import { getSetting, setSetting } from './fin.js';

const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;   // локальная дата
const today = () => iso(new Date());

// ===== Расписание практик =====
// пн=1 … вс=7
export function occursOn(days, dateIso) {
  if (!days) return false;
  const wd = ((new Date(dateIso + 'T00:00:00').getDay() + 6) % 7) + 1;
  if (days === 'daily') return true;
  if (days === 'workdays') return wd <= 5;
  return days.split(',').map(s => s.trim()).includes(String(wd));
}

export function listPractices(db) {
  const t = today();
  const logsToday = new Set(db.prepare('SELECT practice_id FROM practice_log WHERE date = ?').all(t).map(r => r.practice_id));
  return db.prepare('SELECT * FROM practices ORDER BY ord, id').all().map(p => ({
    ...p,
    steps: JSON.parse(p.steps),
    today: occursOn(p.days, t),
    done: logsToday.has(p.id),
    runs: db.prepare('SELECT count(*) AS c FROM practice_log WHERE practice_id = ?').get(p.id).c,
    streak: practiceStreak(db, p),
  }));
}

// стрик по датам, когда практика должна была случиться
export function practiceStreak(db, p) {
  if (!p.days) return 0;
  const dates = new Set(db.prepare('SELECT date FROM practice_log WHERE practice_id = ?').all(p.id).map(r => r.date));
  let streak = 0, d = new Date();
  // если сегодня occurrence, но ещё не отмечено — начинаем со вчера
  if (occursOn(p.days, iso(d)) && !dates.has(iso(d))) d = new Date(d.getTime() - 864e5);
  for (let i = 0; i < 365; i++) {
    const day = iso(d);
    if (occursOn(p.days, day)) {
      if (!dates.has(day)) break;
      streak++;
    }
    d = new Date(d.getTime() - 864e5);
  }
  return streak;
}

export function addPractice(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM practices').get().o;
  db.prepare('INSERT INTO practices(name, kind, days, time, steps, note, ord) VALUES(?,?,?,?,?,?,?)')
    .run(b.name, b.kind ?? 'schedule', b.days ?? '', b.time ?? null,
         JSON.stringify(b.steps ?? []), b.note ?? '', ord);
}
export function patchPractice(db, id, b) {
  for (const k of ['name', 'kind', 'days', 'time', 'note'])
    if (k in b) db.prepare(`UPDATE practices SET ${k} = ? WHERE id = ?`).run(b[k], id);
  if ('steps' in b) db.prepare('UPDATE practices SET steps = ? WHERE id = ?').run(JSON.stringify(b.steps), id);
}
export function delPractice(db, id) { db.prepare('DELETE FROM practices WHERE id = ?').run(id); }

export function logPractice(db, id, b = {}) {
  db.prepare('INSERT INTO practice_log(practice_id, date, note, answers) VALUES(?,?,?,?)')
    .run(id, b.date ?? today(), b.note ?? '', JSON.stringify(b.answers ?? []));
}
export function practiceLogs(db, id, limit = 5) {
  return db.prepare('SELECT * FROM practice_log WHERE practice_id = ? ORDER BY date DESC, id DESC LIMIT ?')
    .all(id, limit).map(l => ({ ...l, answers: JSON.parse(l.answers) }));
}

// проекция в календарь: даты месяца, когда практика по расписанию
export function monthOccurrences(db, ym, first, last) {
  const items = [];
  const logs = db.prepare('SELECT practice_id, date FROM practice_log WHERE date BETWEEN ? AND ?').all(first, last);
  const logged = new Set(logs.map(l => l.practice_id + ':' + l.date));
  for (const p of db.prepare(`SELECT * FROM practices WHERE days != ''`).all()) {
    for (let day = 1; day <= 31; day++) {
      const date = `${ym}-${String(day).padStart(2, '0')}`;
      if (date < first || date > last) continue;
      if (occursOn(p.days, date))
        items.push({ date, type: 'practice', id: p.id, title: p.name, time: p.time,
                     done: logged.has(p.id + ':' + date) });
    }
  }
  return items;
}

// ===== Колесо развития =====
const WHEEL_NAMES = ['Работа', 'Семья и дети', 'Партнёр', 'Саморазвитие и обучение', 'Здоровье и спорт',
  'Социализация', 'Дом', 'Деньги и инвестиции', 'Отдых и хобби', 'Перспективы будущего'];
const WHEEL_OLD = ['Здоровье', 'Финансы', 'Карьера', 'Отношения', 'Окружение', 'Развитие', 'Отдых', 'Смысл'];

export function ensureWheel(db) {
  const existing = db.prepare('SELECT name FROM wheel_areas ORDER BY ord').all().map(r => r.name);
  // старый дефолтный набор заменяем на сектора пользователя (замеры по нему уходят каскадом)
  if (existing.length && existing.join('|') === WHEEL_OLD.join('|'))
    db.prepare('DELETE FROM wheel_areas').run();
  if (db.prepare('SELECT count(*) AS c FROM wheel_areas').get().c > 0) return;
  WHEEL_NAMES.forEach((n, i) => db.prepare('INSERT INTO wheel_areas(name, ord) VALUES(?,?)').run(n, i + 1));
}

export function wheel(db) {
  const areas = db.prepare('SELECT * FROM wheel_areas ORDER BY ord, id').all();
  const dates = db.prepare('SELECT DISTINCT date FROM wheel_scores ORDER BY date DESC').all().map(r => r.date);
  const scoresFor = date => Object.fromEntries(
    db.prepare('SELECT area_id, score FROM wheel_scores WHERE date = ?').all(date).map(r => [r.area_id, r.score]));
  return {
    areas, dates,
    latest: dates[0] ? { date: dates[0], scores: scoresFor(dates[0]) } : null,
    prev: dates[1] ? { date: dates[1], scores: scoresFor(dates[1]) } : null,
  };
}

// поля движения сектора: идеал («что такое 10»), следующий уровень, шаг
export function patchArea(db, id, b) {
  for (const k of ['name', 'ideal', 'current_desc', 'next_desc', 'step'])
    if (k in b) db.prepare(`UPDATE wheel_areas SET ${k} = ? WHERE id = ?`).run(b[k], id);
  // шаг изменился — открытая задача этого сектора переименовывается следом
  // (срок/приоритет/отметки не трогаем; видно везде: Цели, Задачник, календарь)
  if ('step' in b && b.step?.trim()) {
    const area = db.prepare('SELECT name FROM wheel_areas WHERE id = ?').get(id);
    const tasks = db.prepare(`SELECT id FROM nodes WHERE is_category = 0
      AND note LIKE ? AND (status IS NULL OR status != 'done')`).all(`%сектор «${area.name}»%`);
    for (const t of tasks) updateNode(db, t.id, { title: b.step.trim() });
  }
}

// замер: оценки по областям на дату (повторный ввод в тот же день перезаписывает)
export function saveWheel(db, scores, date = today()) {
  for (const [areaId, score] of Object.entries(scores)) {
    const s = Math.max(1, Math.min(10, Math.round(+score)));
    db.prepare(`INSERT INTO wheel_scores(date, area_id, score) VALUES(?,?,?)
      ON CONFLICT(date, area_id) DO UPDATE SET score = excluded.score`).run(date, +areaId, s);
  }
}

// ===== Рабочий лог =====
export function addWork(db, note, date = today()) {
  db.prepare('INSERT INTO work_log(date, note) VALUES(?,?)').run(date, note);
}
export function delWork(db, id) { db.prepare('DELETE FROM work_log WHERE id = ?').run(id); }
export function workLog(db, limit = 20) {
  return db.prepare('SELECT * FROM work_log ORDER BY date DESC, id DESC LIMIT ?').all(limit);
}

// ===== Принятые решения (из Целей) =====
export function acceptedDecisions(db) {
  return db.prepare(`
    SELECT id, title, answer, updated_at FROM nodes
    WHERE kind = 'decision' AND status = 'accepted'
    ORDER BY updated_at DESC LIMIT 30`).all();
}

// ===== Пароль раздела (UI-замок прототипа; шифрование зоны — в нативной версии) =====
const hash = s => crypto.createHash('sha256').update('pipboy:' + s).digest('hex');
export function setPsyPass(db, password) { setSetting(db, 'psy_pass_hash', password ? hash(password) : ''); }
export function checkPsyPass(db, password) {
  const h = getSetting(db, 'psy_pass_hash', '');
  return !h || h === hash(password ?? '');
}
export function psyHasPass(db) { return !!getSetting(db, 'psy_pass_hash', ''); }

// ===== Общий замок разделов (Цели/Финансы/Инфо/Психология) — тот же честный UI-замок
export function setLockPass(db, password) { setSetting(db, 'lock_pw_hash', password ? hash(password) : ''); }
export function lockEnabled(db) { return !!getSetting(db, 'lock_pw_hash', ''); }
export function checkLockPass(db, password) {
  const h = getSetting(db, 'lock_pw_hash', '');
  return !h || h === hash(password ?? '');
}

// ===== Шаг сектора колеса → задача в Целях (в схожую категорию, иначе в Инбокс) =====
import { listCategories, addChild, updateNode } from './core.js';

const AREA_CAT = {   // сектор → ключевое слово категории пользователя
  'Работа': 'Работа', 'Семья и дети': 'Семья', 'Партнёр': 'Семья',
  'Саморазвитие и обучение': 'Развитие', 'Здоровье и спорт': 'Здоровье',
  'Социализация': 'Жизнь', 'Дом': 'Жизнь', 'Деньги и инвестиции': 'Финансы',
  'Отдых и хобби': 'Отдых', 'Перспективы будущего': 'Глобальные',
};

export function wheelStepToTask(db, areaId) {
  const area = db.prepare('SELECT * FROM wheel_areas WHERE id = ?').get(areaId);
  if (!area) throw new Error('сектор не найден');
  if (!area.step?.trim()) throw new Error('у сектора нет шага — сначала задай его');
  const cats = listCategories(db);
  const key = AREA_CAT[area.name];
  const target = (key && cats.find(c => c.title.includes(key)))
    ?? cats.find(c => c.title.includes('Инбокс'));
  // идемпотентно: открытая задача с этим шагом уже есть — возвращаем её
  const dup = db.prepare(`SELECT id FROM nodes WHERE is_category = 0 AND title = ?
    AND parent_id = ? AND (status IS NULL OR status != 'done')`).get(area.step.trim(), target.id);
  if (dup) return { node: db.prepare('SELECT * FROM nodes WHERE id = ?').get(dup.id), category: target.title, existed: true };
  const node = addChild(db, target.id, area.step.trim());
  updateNode(db, node.id, { kind: 'task', priority: 'P2',
    note: `шаг колеса · сектор «${area.name}»` });
  return { node: db.prepare('SELECT * FROM nodes WHERE id = ?').get(node.id), category: target.title, existed: false };
}

// ===== Техника «Позитивное намерение» — каркас пользователя (не демо, создаётся один раз) =====
export const POSITIVE_INTENT_STEPS = [
  'Ситуация: что произошло, что я сделал/почувствовал?',
  'Какое поведение или реакцию хочу изменить?',
  'Какое позитивное намерение стоит за этим поведением? (что оно для меня делает)',
  'Какими ещё способами можно удовлетворить это намерение?',
  'Выбираю лучший способ — какой и почему?',
  'Проверка экологичности: кому/чему это может навредить?',
  'Якорь: когда и где применю новый способ впервые?',
];
export function ensurePositiveIntent(db) {
  if (getSetting(db, 'pi_v1', '') === '1') return;
  if (!db.prepare(`SELECT id FROM practices WHERE name LIKE 'Позитивное намерение%' AND name NOT LIKE '%(пример)%'`).get())
    addPractice(db, { name: 'Позитивное намерение', kind: 'technique', steps: POSITIVE_INTENT_STEPS,
      note: 'за нежелательным поведением стоит позитивное намерение — найди его и дай ему лучший способ' });
  setSetting(db, 'pi_v1', '1');
}

// ===== Демо =====
export function seedPsy(db) {
  ensureWheel(db);
  if (db.prepare(`SELECT count(*) AS c FROM practices WHERE name LIKE '%(пример)%'`).get().c === 0) {
    addPractice(db, { name: 'Тревоги по расписанию (пример)', kind: 'schedule', days: '2,4', time: '19:00',
      note: 'выписываю тревоги в отведённый слот, вне слота — откладываю' });
    addPractice(db, { name: 'Позитивное намерение — 7 шагов (пример)', kind: 'technique', steps: [
      'Что я чувствую прямо сейчас?', 'Какое поведение хочу изменить?',
      'Какое позитивное намерение стоит за этим поведением?', 'Какие ещё способы удовлетворить это намерение?',
      'Выбираю лучший способ', 'Проверяю экологичность: кому это может навредить?', 'Якорю: когда применю впервые?'] });
    addPractice(db, { name: 'Выбор инвестиций — чеклист (пример)', kind: 'checklist', steps: [
      'Это решение из плана, а не из эмоций?', 'Понимаю, что покупаю и зачем?',
      'Размер позиции ≤ лимита на класс?', 'Что сделаю, если упадёт на 30%?', 'Сверился с макро-тезисом?'] });
    addPractice(db, { name: 'Психолог (пример)', kind: 'schedule', days: '5', time: '18:00' });
    addPractice(db, { name: 'Падл (пример)', kind: 'schedule', days: '2,6' });
    const trev = db.prepare(`SELECT id FROM practices WHERE name LIKE 'Тревоги%'`).get().id;
    logPractice(db, trev, { date: iso(new Date(Date.now() - 2 * 864e5)), note: 'выписал 4 тревоги, 2 закрыл сразу' });
  }
  if (db.prepare('SELECT count(*) AS c FROM wheel_scores').get().c === 0) {
    const areas = db.prepare('SELECT id, name FROM wheel_areas ORDER BY ord').all();
    const prev = { 'Работа': 7, 'Семья и дети': 6, 'Партнёр': 7, 'Саморазвитие и обучение': 8, 'Здоровье и спорт': 6,
      'Социализация': 5, 'Дом': 6, 'Деньги и инвестиции': 7, 'Отдых и хобби': 4, 'Перспективы будущего': 6 };
    const cur = { 'Работа': 7, 'Семья и дети': 6, 'Партнёр': 7, 'Саморазвитие и обучение': 8, 'Здоровье и спорт': 5,
      'Социализация': 6, 'Дом': 6, 'Деньги и инвестиции': 8, 'Отдых и хобби': 4, 'Перспективы будущего': 7 };
    const monthAgo = iso(new Date(Date.now() - 30 * 864e5));
    saveWheel(db, Object.fromEntries(areas.map(a => [a.id, prev[a.name] ?? 5])), monthAgo);
    saveWheel(db, Object.fromEntries(areas.map(a => [a.id, cur[a.name] ?? 5])), today());
  }
  if (db.prepare('SELECT count(*) AS c FROM work_log').get().c === 0) {
    addWork(db, 'Закрыл вопрос с подрядчиком, два созвона (пример)', iso(new Date(Date.now() - 864e5)));
    addWork(db, 'Подготовил план квартала команде (пример)');
  }
  // движение по секторам: пара примеров, если поля пустые
  if (!db.prepare(`SELECT count(*) AS c FROM wheel_areas WHERE step != ''`).get().c) {
    const byName = n => db.prepare('SELECT id FROM wheel_areas WHERE name = ?').get(n)?.id;
    const h = byName('Здоровье и спорт');
    if (h) patchArea(db, h, { ideal: 'энергия весь день, сон 7+, спорт 3р/нед, чекапы раз в год',
      next_desc: 'вернулся в зал 2р/нед, сон стабильно до 23:30', step: 'записаться в зал до пятницы (пример)' });
    const o = byName('Отдых и хобби');
    if (o) patchArea(db, o, { ideal: 'отпуск 3р/год без ноутбука, выходные без работы',
      next_desc: 'один полностью свободный выходной в неделю', step: 'заблокировать субботу в календаре (пример)' });
  }
}

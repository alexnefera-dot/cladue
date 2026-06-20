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
export function practiceLogs(db, id, limit = 200) {
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
  'Поведение / убеждение. Что делаю, что не делаю, какой результат, что думаю?',
  'Принятие. Есть причины, разрешаю это. Это сейчас лучший способ. Разрешаю себе понять и найти лучший способ.',
  'Позитивное намерение. Чтобы что получить? От чего защититься? Какие ситуации, чувства, ощущения?',
  'Что в результате? Насколько поведение/убеждение из п.1 помогает реализации позитивного намерения из п.3 (1–10)?',
  'Побочные эффекты? Какую цену я плачу? Какие нежелательные эффекты получаю от убеждения/поведения из п.1? Что теряю?',
  'Альтернативное поведение/мышление. Какое мышление и поведение поможет реализовать позитивное намерение (п.3) с меньшими побочными эффектами и большей эффективностью? Чему научиться, какой опыт получить?',
  'Конкретные действия. Какой первый шаг я выбираю (эксперимент)?',
];
// Техника-практика, создаваемая один раз (флаг). Если практика уже есть, но шаги пустые
// (создана раньше без них) — дозаполняем, чтобы журнал показывал колонки по шагам.
function seedTechnique(db, flag, name, steps, note) {
  const existing = db.prepare(`SELECT id, steps FROM practices WHERE name LIKE ? AND name NOT LIKE '%(пример)%'`).get(name + '%');
  if (existing) {
    if (!existing.steps || existing.steps === '[]') db.prepare('UPDATE practices SET steps = ? WHERE id = ?').run(JSON.stringify(steps), existing.id);
  } else if (getSetting(db, flag, '') !== '1') {
    addPractice(db, { name, kind: 'technique', steps, note });
  }
  setSetting(db, flag, '1');
}
export function ensurePositiveIntent(db) {
  const note = 'за поведением/убеждением стоит позитивное намерение — найди его, оцени цену и подбери более эффективную альтернативу';
  const existing = db.prepare(`SELECT id FROM practices WHERE name LIKE 'Позитивное намерение%' AND name NOT LIKE '%(пример)%'`).get();
  if (existing) {
    // v3: обновляем формулировку шагов один раз даже у уже созданной практики
    if (getSetting(db, 'pi_steps_v3', '') !== '1')
      db.prepare('UPDATE practices SET steps = ? WHERE id = ?').run(JSON.stringify(POSITIVE_INTENT_STEPS), existing.id);
  } else if (getSetting(db, 'pi_v1', '') !== '1') {
    addPractice(db, { name: 'Позитивное намерение', kind: 'technique', steps: POSITIVE_INTENT_STEPS, note });
  }
  setSetting(db, 'pi_v1', '1');
  setSetting(db, 'pi_steps_v3', '1');
}

// ===== Техника «Тестирование мыслей» (когнитивная реструктуризация, КПТ) — создаётся один раз =====
export const THOUGHT_TESTING_STEPS = [
  '🧠 Мысли. Какая у меня есть мысль о себе, людях или мире? (насколько верю в неё, 1–100?)',
  '❤️ Чувства. Что я чувствую в ответ на эту мысль? (сила чувств, 1–100?)',
  '➕ Аргументы «За». Что говорит в пользу полезности и/или реалистичности этой мысли?',
  '➖ Аргументы «Против». Что говорит о её вредности и/или нереалистичности? И что опровергает аргументы «за»?',
  '🔄 Реалистичные и полезные мысли. Как может быть по-другому? Какие более реалистичные и полезные мысли можно выбрать теперь — под мои цели?',
  '✅ Результат. Насколько теперь верю в изначальную мысль (1–100)? Какой силы первые эмоции?',
];
export function ensureThoughtTesting(db) {
  seedTechnique(db, 'tt_v1', 'Тестирование мыслей', THOUGHT_TESTING_STEPS,
    'когнитивная реструктуризация: проверяю мысль на реалистичность и пользу, выбираю более полезную');
}

// ===== Техника «Дневник мыслей» (CBT thought record) — журнал случаев таблицей =====
export const THOUGHT_DIARY_STEPS = [
  'Ситуация (что произошло / происходит?)',
  '«Мысли» (что думаю о себе, ситуации, мире, людях?)',
  'Эмоции 1–100 (что чувствую и насколько сильно? напр. «Беспокойство (90)»)',
  'Поведение (что хочу делать? что делаю?)',
];
export function ensureThoughtDiary(db) {
  seedTechnique(db, 'td_v1', 'Дневник мыслей', THOUGHT_DIARY_STEPS,
    'ловлю случай: ситуация → мысли → эмоции (1–100) → поведение. Журнал копится таблицей для пересмотра');
}

// ===== Техника «Дневник Опыта» — разбор случая, где себя остановил =====
export const EXPERIENCE_DIARY_STEPS = [
  'Ситуация. Что было? Что сделал / не сделал?',
  'Чувства. Что я там чувствовал? (1–100)',
  'Мысли. Какими мыслями себя остановил?',
  'Принятие и разрешение. Есть причины — какие?',
  'Планирование. Как хочу поступить в следующий раз? Как думать, говорить, действовать?',
];
export function ensureExperienceDiary(db) {
  seedTechnique(db, 'exp_v1', 'Дневник Опыта', EXPERIENCE_DIARY_STEPS,
    'разбираю случай, где себя остановил: ситуация → чувства → мысли → принятие → план на будущее');
}

// ===== Техника «Дневник Побед» — закрепляю успех и новые выводы =====
export const WINS_DIARY_STEPS = [
  'Ситуация. Какая ситуация? Что я сделал и как?',
  'Что в результате? Какие реакции, факты?',
  'Что чувствовал? (1–100)',
  'Какие новые выводы выбираю сделать о себе, людях, мире, возможностях, силе, безопасности — и о чём напоминать себе в следующих подобных ситуациях?',
];
export function ensureWinsDiary(db) {
  seedTechnique(db, 'win_v1', 'Дневник Побед', WINS_DIARY_STEPS,
    'закрепляю успех: ситуация → результат → чувства → новые выводы о себе и мире');
}

// ===== Разобранные случаи в журнал «Дневника мыслей» (внесено один раз) =====
export const THOUGHT_DIARY_ENTRIES = [
  ['19:00 Собираюсь решить задачи, хвосты где есть сложные решения',
   'Нужно чуть позже, собраться силами, возможно сейчас ещё можно не париться и потом подумаю (50)',
   'Беспокойство (90)',
   'Откладываю и не сажусь за задачу, нахожу причины не успевать. Нужно расписать текущее видение, там где сомневаюсь — указать, пересмотреть через какое время и почему.'],
  ['18:00 Планирую разговор с Серым по переводам',
   'Сейчас уже поздно, выходной, не хочу беспокоить, надо просчитать всё (90)',
   'Сомнение (100)',
   'Надо посчитать спокойно, спланировать удобный для двоих день и свои ожидания. Ставлю задачу в неудобный момент, не подумав, что хочу получить точно и устроит ли меня какой из вариантов.'],
];
export function seedThoughtDiaryEntries(db) {
  if (getSetting(db, 'td_seed_v1', '') === '1') return;
  const p = db.prepare(`SELECT id FROM practices WHERE name LIKE 'Дневник мыслей%' AND name NOT LIKE '%(пример)%'`).get();
  if (!p) return;   // практики ещё нет — попробуем при следующем запуске
  if (db.prepare('SELECT count(*) AS c FROM practice_log WHERE practice_id = ?').get(p.id).c === 0)
    for (const answers of THOUGHT_DIARY_ENTRIES) logPractice(db, p.id, { answers });
  setSetting(db, 'td_seed_v1', '1');
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

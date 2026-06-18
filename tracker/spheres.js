// Сферы жизни = секторы Колеса (wheel_areas) + история оценок + привязанные задачи.
// Строится ПОВЕРХ существующих данных Pipboy — отдельного хранилища нет, всё реальное:
//   ideal       — «10», к чему идём
//   score       — где сейчас (последняя оценка колеса), history — динамика
//   step        — следующий шаг (он же связан с задачей сектора)
//   tasks       — открытые задачи сектора (по конвенции note LIKE '%сектор «имя»%')
// Дальше сюда же подтянем рутины/трекинг/практики через тег сферы (v0.2).

export function buildSpheres(db) {
  const areas = db.prepare('SELECT * FROM wheel_areas ORDER BY ord, id').all();
  return areas.map(a => {
    const sc = db.prepare(
      'SELECT date, score FROM wheel_scores WHERE area_id = ? ORDER BY date DESC LIMIT 8'
    ).all(a.id);
    const tasks = db.prepare(
      `SELECT id, title, status, due_date, priority FROM nodes
       WHERE is_category = 0 AND note LIKE ?
       ORDER BY (status = 'done'), COALESCE(due_date, '9999-99-99')`
    ).all(`%сектор «${a.name}»%`);
    return {
      id: a.id,
      name: a.name,
      ideal: a.ideal || '',
      current_desc: a.current_desc || '',
      next_desc: a.next_desc || '',
      step: a.step || '',
      score: sc[0]?.score ?? null,
      prev: sc[1]?.score ?? null,
      history: sc.map(s => s.score).reverse(),
      tasks: tasks.map(t => ({
        id: t.id, title: t.title, done: t.status === 'done',
        due: t.due_date || null, priority: t.priority || null,
      })),
    };
  });
}

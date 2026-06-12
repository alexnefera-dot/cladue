// Ревизия наполнения: где пусто, что протухло, что не настроено.
// Детерминированные проверки по базе — никакого ИИ, только счётчики и пороги.
import { getSetting } from './fin.js';

export function audit(db) {
  const c = q => db.prepare(q).get().c;
  const out = [];
  const add = (section, status, item, hint = '') => out.push({ section, status, item, hint });
  const today = new Date().toISOString().slice(0, 10);

  // Цели
  const untyped = c(`SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND kind IS NULL`);
  const real = c(`SELECT count(*) AS c FROM nodes WHERE is_category = 0`);
  if (!real) add('Цели', 'warn', 'записей нет вообще', 'вставь свои списки в поле импорта');
  else if (untyped > real * 0.5) add('Цели', 'warn', `разобрано мало: без типа ${untyped} из ${real}`, 'пройдись по инбоксу, прими предложения типов');
  else add('Цели', 'ok', `записей ${real}, без типа ${untyped}`);
  const inbox = db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%Инбокс%'`).get();
  const inboxN = inbox ? c(`SELECT count(*) AS c FROM nodes WHERE parent_id = ${inbox.id}`) : 0;
  if (inboxN > 15) add('Цели', 'warn', `инбокс распух: ${inboxN}`, 'воскресный разбор');
  const p01NoDate = c(`SELECT count(*) AS c FROM nodes WHERE kind = 'task' AND priority IN ('P0','P1')
    AND due_date IS NULL AND status IS NOT 'done'`);
  if (p01NoDate) add('Цели', 'warn', `важных задач без срока: ${p01NoDate}`, 'P0/P1 без даты не попадут в неделю');
  const weekGoals = c(`SELECT count(*) AS c FROM nodes WHERE kind IN ('task','decision')
    AND due_date BETWEEN date('now','weekday 1','-7 days') AND date('now','weekday 0')`);
  if (!weekGoals) add('Цели', 'warn', 'нет задач со сроком на этой неделе', 'поставь 3–5 — оживут недельные цели');

  // Финансы
  const accounts = c('SELECT count(*) AS c FROM accounts');
  if (!accounts) add('Финансы', 'warn', 'счета не заведены');
  else {
    const stale = c(`SELECT count(*) AS c FROM accounts WHERE julianday('now') - julianday(balance_updated_at) > 14`);
    add('Финансы', stale ? 'warn' : 'ok', stale ? `балансы протухли (>14 дн): ${stale} из ${accounts}` : `счета: ${accounts}, балансы свежие`);
  }
  const assets = c(`SELECT count(*) AS c FROM portfolio_items WHERE kind = 'asset'`);
  const noBuy = c(`SELECT count(*) AS c FROM portfolio_items WHERE kind = 'asset' AND buy_value IS NULL AND value IS NOT NULL`);
  if (!assets) add('Финансы', 'warn', 'в портфеле нет активов');
  else if (noBuy) add('Финансы', 'warn', `активов без цены покупки: ${noBuy} из ${assets}`, 'прирост у них считается нулевым');
  else add('Финансы', 'ok', `активы: ${assets}, цены покупки заданы`);
  if (!c(`SELECT count(*) AS c FROM portfolio_items WHERE target_value IS NOT NULL`))
    add('Финансы', 'warn', 'целевой портфель пуст', 'вкладка «Целевой портфель» — задай доли');
  if (!c(`SELECT count(*) AS c FROM portfolio_items WHERE kind = 'asset' AND asset_type IS NOT NULL`))
    add('Финансы', 'warn', 'у активов нет типов', '⊙ у строки — аллокация по типам оживёт');
  if (!c('SELECT count(*) AS c FROM obligations')) add('Финансы', 'warn', 'нет обязательств/подписок', 'радар платежей пуст');
  if (!c('SELECT count(*) AS c FROM properties')) add('Финансы', 'warn', 'имущество не заведено', 'X5/квартира с регламентами');
  if (!c(`SELECT count(*) AS c FROM transactions WHERE date >= date('now','-30 days')`))
    add('Финансы', 'warn', 'расходов за 30 дней нет', 'вноси вручную или кинь Monefy CSV');
  if (getSetting(db, 'fire_target') == null) add('Финансы', 'warn', 'FIRE не настроен', 'цель/доходность/взнос');
  if (!c('SELECT count(*) AS c FROM forecasts')) add('Финансы', 'warn', 'журнал прогнозов пуст', 'калибровка не считается');
  if (!c('SELECT count(*) AS c FROM rates WHERE price IS NOT NULL')) add('Финансы', 'warn', 'курсы не загружены', '⟳ в финансах');

  // Календарь и люди
  if (!c(`SELECT count(*) AS c FROM events WHERE date >= '${today}' OR recur != 'none'`))
    add('Календарь', 'warn', 'нет будущих событий', 'курсы/встречи с повтором');
  const people = c('SELECT count(*) AS c FROM people');
  if (!people) add('Люди', 'warn', 'людей нет', 'ДР и контакт-ритм близких');
  else {
    const noBd = c('SELECT count(*) AS c FROM people WHERE birthday IS NULL');
    add('Люди', noBd ? 'warn' : 'ok', noBd ? `без даты рождения: ${noBd} из ${people}` : `люди: ${people}, ДР заполнены`);
  }

  // Рутины, трекинг, психология
  if (!c('SELECT count(*) AS c FROM routines')) add('Рутины', 'warn', 'рутины не заведены');
  else if (!c(`SELECT count(*) AS c FROM routine_log WHERE date >= date('now','-3 days')`))
    add('Рутины', 'warn', 'нет отметок за 3 дня', 'отмечай на «Сегодня»');
  else add('Рутины', 'ok', 'отметки идут');
  if (!c(`SELECT count(*) AS c FROM checkins WHERE date >= date('now','-7 days')`))
    add('Трекинг', 'warn', 'чек-инов за неделю нет', '10 секунд на «Сегодня»');
  if (!c(`SELECT count(*) AS c FROM metric_log WHERE date >= date('now','-7 days')`))
    add('Трекинг', 'warn', 'дневник за неделю пуст', 'клик по ячейке за день');
  if (!c('SELECT count(*) AS c FROM wheel_scores')) add('Психология', 'warn', 'колесо без замеров', 'первый реальный замер');
  else add('Психология', 'ok', 'замеры колеса есть');
  if (!c(`SELECT count(*) AS c FROM wheel_areas WHERE step != ''`))
    add('Психология', 'warn', 'нет шагов по секторам', 'таблица движения под колесом');
  if (!c(`SELECT count(*) AS c FROM practice_log WHERE date >= date('now','-14 days')`))
    add('Психология', 'warn', 'практики 2 недели не проходились');

  // Инфо
  const emptyPages = db.prepare(`SELECT count(*) AS c FROM pages WHERE locked = 0 AND trim(content) = ''`).get().c;
  if (emptyPages) add('Инфо', 'warn', `пустых страниц: ${emptyPages}`, 'наполни или удали');

  // Система
  if (getSetting(db, 'lock_pw_hash', '') === '') add('Система', 'warn', 'замок разделов не включён', 'Настройки → 🔒');
  if (db.prepare(`SELECT value FROM settings WHERE key = 'demo_wiped'`).get()?.value !== '1')
    add('Система', 'warn', 'демо-данные не зачищены', 'Настройки → 🧹');
  return out;
}

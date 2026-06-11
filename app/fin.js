import { addChild, updateNode } from './core.js';

const today = () => new Date().toISOString().slice(0, 10);

export function listFin(db) {
  const accounts = db.prepare('SELECT * FROM accounts ORDER BY id').all()
    .map(a => ({ ...a, stale_days: Math.floor((Date.parse(today()) - Date.parse(a.balance_updated_at.slice(0, 10))) / 864e5) }));
  const classes = db.prepare('SELECT * FROM portfolio_classes ORDER BY ord, id').all();
  const totalPort = classes.reduce((s, c) => s + c.value, 0);
  const withShares = classes.map(c => {
    const share = totalPort ? c.value / totalPort * 100 : 0;
    return { ...c, share, deviation: share - c.target_pct };
  });
  // соответствие целевому: 100% минус половина суммы модулей отклонений
  const fit = totalPort
    ? Math.max(0, 100 - withShares.reduce((s, c) => s + Math.abs(c.deviation), 0) / 2)
    : null;
  const steps = db.prepare(`SELECT * FROM steps ORDER BY status = 'done', planned_date IS NULL, planned_date, id`).all();
  const obligations = db.prepare('SELECT * FROM obligations ORDER BY next_date IS NULL, next_date').all()
    .map(o => ({ ...o, days_left: o.next_date ? Math.ceil((Date.parse(o.next_date) - Date.parse(today())) / 864e5) : null }));
  return {
    accounts, classes: withShares, steps, obligations,
    summary: {
      accountsTotal: accounts.reduce((s, a) => s + (a.currency === '₽' ? a.balance : 0), 0),
      portfolioTotal: totalPort,
      fit,
      monthlyObligations: obligations.filter(o => o.period === 'monthly').reduce((s, o) => s + o.amount, 0),
      upcoming: obligations.filter(o => o.days_left != null && o.days_left <= 30),
    },
  };
}

// ===== Счета =====
export function addAccount(db, b) {
  db.prepare('INSERT INTO accounts(name, type, currency, balance) VALUES(?,?,?,?)')
    .run(b.name, b.type ?? 'bank', b.currency ?? '₽', b.balance ?? 0);
}
export function patchAccount(db, id, b) {
  if ('balance' in b)
    db.prepare(`UPDATE accounts SET balance = ?, balance_updated_at = datetime('now') WHERE id = ?`).run(b.balance, id);
  for (const k of ['name', 'type', 'currency', 'note'])
    if (k in b) db.prepare(`UPDATE accounts SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delAccount(db, id) { db.prepare('DELETE FROM accounts WHERE id = ?').run(id); }

// ===== Классы портфеля =====
export function addClass(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_classes').get().o;
  db.prepare('INSERT INTO portfolio_classes(name, value, target_pct, ord) VALUES(?,?,?,?)')
    .run(b.name, b.value ?? 0, b.target_pct ?? 0, ord);
}
export function patchClass(db, id, b) {
  for (const k of ['name', 'value', 'target_pct', 'note'])
    if (k in b) db.prepare(`UPDATE portfolio_classes SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delClass(db, id) { db.prepare('DELETE FROM portfolio_classes WHERE id = ?').run(id); }

// ===== План шагов =====
export function addStep(db, b) {
  db.prepare('INSERT INTO steps(kind, title, amount, planned_date, condition, note) VALUES(?,?,?,?,?,?)')
    .run(b.kind ?? 'buy', b.title, b.amount ?? null, b.planned_date ?? null, b.condition ?? '', b.note ?? '');
}
export function patchStep(db, id, b) {
  for (const k of ['kind', 'title', 'amount', 'planned_date', 'condition', 'status', 'note'])
    if (k in b) db.prepare(`UPDATE steps SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delStep(db, id) { db.prepare('DELETE FROM steps WHERE id = ?').run(id); }

// Шаг → задача в категории «Финансы» (интеграция с разделом списка)
export function stepToTask(db, id) {
  const s = db.prepare('SELECT * FROM steps WHERE id = ?').get(id);
  if (!s) throw new Error('step not found');
  const fin = db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND title = 'Финансы' AND parent_id IS NULL`).get();
  const KIND = { buy: 'Купить', sell: 'Продать', transfer: 'Перевести' };
  const node = addChild(db, fin?.id ?? null, `${KIND[s.kind] ?? s.kind}: ${s.title}`);
  return updateNode(db, node.id, {
    kind: 'task',
    due_date: s.planned_date ?? null,
    note: ['из плана шагов портфеля', s.amount ? `сумма: ${s.amount}` : '', s.condition ? `условие: ${s.condition}` : '']
      .filter(Boolean).join(' · '),
  });
}

// ===== Обязательства =====
export function addObligation(db, b) {
  db.prepare('INSERT INTO obligations(name, amount, currency, period, next_date, remind_days, kind, note) VALUES(?,?,?,?,?,?,?,?)')
    .run(b.name, b.amount ?? 0, b.currency ?? '₽', b.period ?? 'monthly',
         b.next_date ?? null, b.remind_days ?? 5, b.kind ?? 'liability', b.note ?? '');
}
export function patchObligation(db, id, b) {
  for (const k of ['name', 'amount', 'currency', 'period', 'next_date', 'remind_days', 'kind', 'note'])
    if (k in b) db.prepare(`UPDATE obligations SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delObligation(db, id) { db.prepare('DELETE FROM obligations WHERE id = ?').run(id); }

export function addMonths(iso, months) {
  const d = new Date(iso + 'T00:00:00Z');
  const day = d.getUTCDate();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + months);
  const last = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0)).getUTCDate();
  d.setUTCDate(Math.min(day, last));
  return d.toISOString().slice(0, 10);
}

// «оплачено»: сдвигает дату на период; разовое — закрывается
export function payObligation(db, id) {
  const o = db.prepare('SELECT * FROM obligations WHERE id = ?').get(id);
  if (!o || !o.next_date) return o;
  const next = o.period === 'monthly' ? addMonths(o.next_date, 1)
             : o.period === 'yearly' ? addMonths(o.next_date, 12)
             : null;
  db.prepare('UPDATE obligations SET next_date = ? WHERE id = ?').run(next, id);
  return db.prepare('SELECT * FROM obligations WHERE id = ?').get(id);
}

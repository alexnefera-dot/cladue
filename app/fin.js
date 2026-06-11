import { addChild, updateNode } from './core.js';

const today = () => new Date().toISOString().slice(0, 10);

// Курс EURUSD: долларов за 1 евро (из полосы курсов; дефолт, если не загружен)
export function eurUsdRate(db) {
  return db.prepare(`SELECT price FROM rates WHERE symbol = 'EURUSD'`).get()?.price || 1.08;
}

// Дерево портфеля. Активы — в своей валюте (€/$), агрегаты — в € по курсу.
// value: у листа — родное значение; у раздела/блока — сумма в €.
export function portfolioTree(db) {
  const rate = eurUsdRate(db);
  const toEur = (v, cur) => v == null ? null : (cur === '$' ? v / rate : v);
  const rows = db.prepare('SELECT * FROM portfolio_items ORDER BY parent_id NULLS FIRST, ord, id').all();
  const byP = {};
  rows.forEach(r => (byP[r.parent_id ?? 'root'] ??= []).push(r));
  const calc = r => {
    const children = (byP[r.id] ?? []).map(calc);
    const isLeaf = r.kind === 'asset' || !children.length;
    const eur = isLeaf ? (toEur(r.value, r.currency) ?? 0) : children.reduce((s, k) => s + k.eur, 0);
    // прирост честный: считаем только пары, где задана цена покупки (в €)
    const invested = isLeaf ? toEur(r.buy_value, r.currency)
      : children.some(k => k.invested != null) ? children.reduce((s, k) => s + (k.invested ?? 0), 0) : null;
    const investedCur = isLeaf ? (r.buy_value != null ? (toEur(r.value, r.currency) ?? 0) : null)
      : children.some(k => k.investedCur != null) ? children.reduce((s, k) => s + (k.investedCur ?? 0), 0) : null;
    const target = r.target_value != null ? r.target_value
      : children.some(k => k.target != null) ? children.reduce((s, k) => s + (k.target ?? 0), 0) : null;
    return { ...r, children, eur, value: isLeaf ? r.value : eur, invested, investedCur, target };
  };
  return (byP['root'] ?? []).map(calc);
}

export function listFin(db) {
  const accounts = db.prepare('SELECT * FROM accounts ORDER BY id').all()
    .map(a => ({ ...a, stale_days: Math.floor((Date.parse(today()) - Date.parse(a.balance_updated_at.slice(0, 10))) / 864e5) }));
  const portfolio = portfolioTree(db);
  const rate = eurUsdRate(db);
  const portfolioTotal = portfolio.reduce((s, b) => s + b.eur, 0);          // в €
  const portfolioTotalUsd = portfolioTotal * rate;                          // в $
  const invested = portfolio.reduce((s, b) => s + (b.invested ?? 0), 0);
  const investedCur = portfolio.reduce((s, b) => s + (b.investedCur ?? 0), 0);
  const steps = db.prepare(`SELECT * FROM steps ORDER BY status = 'done', planned_date IS NULL, planned_date, id`).all();
  const obligations = db.prepare('SELECT * FROM obligations ORDER BY next_date IS NULL, next_date').all()
    .map(o => ({ ...o, days_left: o.next_date ? Math.ceil((Date.parse(o.next_date) - Date.parse(today())) / 864e5) : null }));
  // счета: итог по каждой валюте отдельно
  const byCur = {};
  for (const a of accounts) byCur[a.currency] = (byCur[a.currency] ?? 0) + a.balance;
  return {
    accounts, portfolio, steps, obligations,
    rates: db.prepare('SELECT * FROM rates').all(),
    summary: {
      accountsByCurrency: byCur,
      portfolioTotal,
      portfolioTotalUsd,
      rate,
      growth: invested ? { invested, current: investedCur, abs: investedCur - invested, pct: (investedCur - invested) / invested * 100 } : null,
      monthlyObligations: obligations.filter(o => o.period === 'monthly').reduce((s, o) => s + o.amount, 0),
      upcoming: obligations.filter(o => o.days_left != null && o.days_left <= 30),
    },
  };
}

// ===== Узлы портфеля =====
export function addItem(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_items WHERE parent_id IS ?').get(b.parent_id ?? null).o;
  db.prepare('INSERT INTO portfolio_items(parent_id, ord, name, kind, buy_value, value, target_value, currency) VALUES(?,?,?,?,?,?,?,?)')
    .run(b.parent_id ?? null, ord, b.name, b.kind ?? 'asset', b.buy_value ?? null, b.value ?? null, b.target_value ?? null, b.currency ?? '€');
}
export function patchItem(db, id, b) {
  for (const k of ['name', 'buy_value', 'value', 'target_value', 'currency', 'note'])
    if (k in b) db.prepare(`UPDATE portfolio_items SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delItem(db, id) { db.prepare('DELETE FROM portfolio_items WHERE id = ?').run(id); }

// ===== Курсы (stooq, без ключей; вручную — всегда можно) =====
const RATE_LABELS = { 'XAUUSD': 'Золото', 'EURUSD': 'EUR/USD', 'BTCUSD': 'BTC', '^SPX': 'S&P 500' };

export async function ratesRefresh(db) {
  const url = 'https://stooq.com/q/l/?s=xauusd,eurusd,btcusd,%5Espx&f=sd2t2ohlcv&h&e=csv';
  const res = await fetch(url, {
    signal: AbortSignal.timeout(8000),
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' },
  });
  if (!res.ok) throw new Error('stooq: ' + res.status);
  const text = await res.text();
  for (const line of text.trim().split('\n').slice(1)) {
    const parts = line.split(',');
    const sym = (parts[0] ?? '').toUpperCase();
    const open = parseFloat(parts[3]), close = parseFloat(parts[6]);
    if (!isFinite(close)) continue;
    db.prepare(`INSERT INTO rates(symbol, label, price, change_pct, updated_at)
      VALUES(?,?,?,?,datetime('now'))
      ON CONFLICT(symbol) DO UPDATE SET price = excluded.price, change_pct = excluded.change_pct, updated_at = excluded.updated_at`)
      .run(sym, RATE_LABELS[sym] ?? sym, close, isFinite(open) && open ? (close - open) / open * 100 : null);
  }
  return db.prepare('SELECT * FROM rates').all();
}

export function rateSet(db, symbol, price) {
  db.prepare(`UPDATE rates SET price = ?, change_pct = NULL, updated_at = datetime('now') WHERE symbol = ?`)
    .run(price, symbol);
  return db.prepare('SELECT * FROM rates WHERE symbol = ?').get(symbol);
}

// ===== Счета =====
export function addAccount(db, b) {
  db.prepare('INSERT INTO accounts(name, type, currency, balance) VALUES(?,?,?,?)')
    .run(b.name, b.type ?? 'bank', b.currency ?? '€', b.balance ?? 0);
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
    .run(b.name, b.amount ?? 0, b.currency ?? '€', b.period ?? 'monthly',
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

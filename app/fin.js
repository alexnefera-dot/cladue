import { addChild, updateNode } from './core.js';

// локальная дата (не UTC): сутки переключаются в полночь пользователя
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

// Курс EURUSD: долларов за 1 евро (из полосы курсов; дефолт, если не загружен)
export function eurUsdRate(db) {
  return db.prepare(`SELECT price FROM rates WHERE symbol = 'EURUSD'`).get()?.price || 1.08;
}

// Дерево портфеля. Активы — в своей валюте (€/$), агрегаты — в € по курсу.
// value: у листа — родное значение; у раздела/блока — сумма в €.
export function portfolioTree(db) {
  const rate = eurUsdRate(db);
  const toEur = (v, cur) => v == null ? null : (cur === '$' ? v / rate : v);
  const prices = Object.fromEntries(db.prepare('SELECT symbol, price FROM rates').all().map(r => [r.symbol, r.price]));
  const rows = db.prepare('SELECT * FROM portfolio_items ORDER BY parent_id NULLS FIRST, ord, id').all()
    .map(r => {
      // автоцена: qty × курс тикера (курсы в $)
      if (r.rate_symbol && r.qty != null) {
        if (prices[r.rate_symbol])
          return { ...r, value: r.qty * prices[r.rate_symbol], currency: '$', auto: true };
        return { ...r, no_rate: true };   // тикер задан, курс ещё не загружен — видно в UI
      }
      return r;
    });
  const byP = {};
  rows.forEach(r => (byP[r.parent_id ?? 'root'] ??= []).push(r));
  const calc = r => {
    const children = (byP[r.id] ?? []).map(calc);
    const isLeaf = r.kind === 'asset' || !children.length;
    const eur = isLeaf ? (toEur(r.value, r.currency) ?? 0) : children.reduce((s, k) => s + k.eur, 0);
    // валютный разрез категории: сколько лежит в $ и в € (в родных валютах)
    const usdPart = isLeaf ? (r.currency === '$' ? (r.value ?? 0) : 0) : children.reduce((s, k) => s + k.usdPart, 0);
    const eurPart = isLeaf ? (r.currency !== '$' ? (r.value ?? 0) : 0) : children.reduce((s, k) => s + k.eurPart, 0);
    // прирост: цена покупки не задана — приравнивается к текущей (вклад в % нулевой)
    const buyEff = r.buy_value ?? r.value;
    const invested = isLeaf ? (buyEff != null ? (toEur(buyEff, r.currency) ?? 0) : null)
      : children.some(k => k.invested != null) ? children.reduce((s, k) => s + (k.invested ?? 0), 0) : null;
    const investedCur = isLeaf ? (r.value != null ? (toEur(r.value, r.currency) ?? 0) : null)
      : children.some(k => k.investedCur != null) ? children.reduce((s, k) => s + (k.investedCur ?? 0), 0) : null;
    const target = r.target_value != null ? r.target_value
      : children.some(k => k.target != null) ? children.reduce((s, k) => s + (k.target ?? 0), 0) : null;
    return { ...r, children, eur, usdPart, eurPart, value: isLeaf ? r.value : eur, invested, investedCur, target };
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
  // займы: зеркало активов портфеля с флагом is_loan (ничего не считаем отдельно)
  const loans = [];
  const walkLoan = (n, path) => {
    if (n.is_loan && (n.kind === 'asset' || !n.children.length))
      loans.push({ id: n.id, name: n.name, value: n.value, currency: n.currency ?? '€', loan_due: n.loan_due,
        path: path.join(' → '),
        overdue_days: n.loan_due ? Math.floor((Date.parse(today()) - Date.parse(n.loan_due)) / 864e5) : null });
    n.children.forEach(c => walkLoan(c, [...path, n.name]));
  };
  portfolio.forEach(b => walkLoan(b, []));
  // аллокация по типам активов (поверх блоков), в € + разрез по блокам-категориям
  const byType = {};
  const byTypeBlocks = {};   // тип → { блок: € }
  const walkType = (n, root) => {
    if (n.kind === 'asset' || !n.children.length) {
      if (n.eur) {
        const t = n.asset_type ?? 'без типа';
        byType[t] = (byType[t] ?? 0) + n.eur;
        (byTypeBlocks[t] ??= {})[root.name] = ((byTypeBlocks[t] ?? {})[root.name] ?? 0) + n.eur;
      }
    }
    n.children.forEach(c => walkType(c, root));
  };
  portfolio.forEach(b => walkType(b, b));
  const blockEur = Object.fromEntries(portfolio.map(b => [b.name, b.eur]));
  const debts = db.prepare('SELECT * FROM debts ORDER BY due_date IS NULL, due_date').all()
    .map(d => ({ ...d, overdue_days: d.due_date
      ? Math.floor((Date.parse(today()) - Date.parse(d.due_date)) / 864e5) : null }));
  const snaps = db.prepare('SELECT * FROM snapshots ORDER BY date DESC LIMIT 2').all();
  return {
    accounts, portfolio, steps, obligations, loans, debts,
    snapshotDelta: snaps.length === 2 ? { since: snaps[1].date, abs: snaps[0].portfolio_eur - snaps[1].portfolio_eur } : null,
    byType: Object.entries(byType).sort((a, b) => b[1] - a[1]),
    byTypeBlocks, blockEur,
    tx: txMonth(db, today().slice(0, 7)),
    forecasts: forecasts(db),
    properties: listProperties(db),
    fire: fireCalc(db, portfolioTotal),
    income: listIncome(db),
    budget: parseFloat(getSetting(db, 'monthly_budget', '')) || null,   // базовый минимум месяца
    macro: db.prepare('SELECT * FROM macro_notes ORDER BY date DESC, id DESC').all(),
    rates: db.prepare('SELECT * FROM rates').all(),
    summary: {
      accountsByCurrency: byCur,
      portfolioTotal,
      portfolioTotalUsd,
      rate,
      growth: invested ? { invested, current: investedCur, abs: investedCur - invested, pct: (investedCur - invested) / invested * 100 } : null,
      monthlyObligations: obligations.filter(o => o.period === 'monthly').reduce((s, o) => s + o.amount, 0),
      // пассивный доход в месяц: ежемесячные + годовые/12 (в их валютах суммируем по-простому в €-эквиваленте)
      monthlyIncome: listIncome(db).reduce((s, i) => {
        const eur = i.currency === '$' ? i.amount / rate : i.amount;
        return s + (i.period === 'monthly' ? eur : i.period === 'yearly' ? eur / 12 : 0);
      }, 0),
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
  for (const k of ['name', 'buy_value', 'value', 'target_value', 'currency', 'is_loan', 'loan_due', 'asset_type', 'qty', 'rate_symbol', 'note'])
    if (k in b) db.prepare(`UPDATE portfolio_items SET ${k} = ? WHERE id = ?`).run(b[k], id);
}

// ===== Пассивный доход: аренда, депозиты, дивиденды =====
export function addIncome(db, b) {
  db.prepare('INSERT INTO passive_income(name, amount, currency, period, next_date, note) VALUES(?,?,?,?,?,?)')
    .run(b.name, b.amount ?? 0, b.currency ?? '€', b.period ?? 'monthly', b.next_date ?? null, b.note ?? '');
}
export function patchIncome(db, id, b) {
  for (const k of ['name', 'amount', 'currency', 'period', 'next_date', 'note'])
    if (k in b) db.prepare(`UPDATE passive_income SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delIncome(db, id) { db.prepare('DELETE FROM passive_income WHERE id = ?').run(id); }
export function listIncome(db) {
  return db.prepare('SELECT * FROM passive_income ORDER BY period, id').all();
}

// ===== Долги (мои и мне; плановые из портфеля — отдельно, через 🤝) =====
export function addDebt(db, b) {
  db.prepare('INSERT INTO debts(name, amount, currency, direction, due_date, note) VALUES(?,?,?,?,?,?)')
    .run(b.name, b.amount ?? 0, b.currency ?? '€', b.direction ?? 'owed_to_me', b.due_date ?? null, b.note ?? '');
}
export function patchDebt(db, id, b) {
  for (const k of ['name', 'amount', 'currency', 'direction', 'due_date', 'note'])
    if (k in b) db.prepare(`UPDATE debts SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delDebt(db, id) { db.prepare('DELETE FROM debts WHERE id = ?').run(id); }

// ===== История нетворса: один снапшот в день =====
export function recordSnapshot(db) {
  const total = portfolioTree(db).reduce((s, b) => s + b.eur, 0);
  db.prepare('INSERT OR IGNORE INTO snapshots(date, portfolio_eur) VALUES(?,?)').run(today(), total);
}
// ===== Перемещение в портфеле: вложить / поставить рядом (drag&drop) =====
function assertNoCycle(db, id, parentId) {
  if (parentId == null) return;
  if (id === parentId) throw new Error('сам в себя нельзя');
  const desc = db.prepare(`
    WITH RECURSIVE r(x) AS (
      SELECT id FROM portfolio_items WHERE parent_id = ?
      UNION SELECT p.id FROM portfolio_items p JOIN r ON p.parent_id = r.x
    ) SELECT 1 AS hit FROM r WHERE x = ? LIMIT 1`).get(id, parentId);
  if (desc) throw new Error('нельзя внутрь собственной ветки');
}

export function moveItem(db, id, parentId) {
  const target = parentId == null ? null : db.prepare('SELECT * FROM portfolio_items WHERE id = ?').get(parentId);
  if (parentId != null && !target) throw new Error('цель не найдена');
  if (target?.kind === 'asset') throw new Error('внутрь актива нельзя — кинь на раздел или рядом');
  assertNoCycle(db, id, parentId);
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_items WHERE parent_id IS ?').get(parentId).o;
  db.prepare('UPDATE portfolio_items SET parent_id = ?, ord = ? WHERE id = ?').run(parentId, ord, id);
}

export function reorderItem(db, id, refId, where = 'after') {
  if (id === refId) throw new Error('self');
  const ref = db.prepare('SELECT id, parent_id FROM portfolio_items WHERE id = ?').get(refId);
  if (!ref) throw new Error('сосед не найден');
  assertNoCycle(db, id, ref.parent_id);
  const siblings = db.prepare('SELECT id FROM portfolio_items WHERE parent_id IS ? ORDER BY ord, id')
    .all(ref.parent_id).map(r => r.id).filter(x => x !== id);
  siblings.splice(siblings.indexOf(refId) + (where === 'after' ? 1 : 0), 0, id);
  db.prepare('UPDATE portfolio_items SET parent_id = ? WHERE id = ?').run(ref.parent_id, id);
  const up = db.prepare('UPDATE portfolio_items SET ord = ? WHERE id = ?');
  siblings.forEach((sid, i) => up.run(i + 1, sid));
}

export function delItem(db, id) { db.prepare('DELETE FROM portfolio_items WHERE id = ?').run(id); }

// ===== Курсы: публичные источники без ключей, с фолбэками. Наружу уходят только тикеры. =====
const RATE_LABELS = { 'XAUUSD': 'Золото', 'EURUSD': 'EUR/USD', 'BTCUSD': 'BTC',
  'SCHD': 'SCHD', 'IVV': 'IVV', 'VHT': 'VHT' };

async function jget(url) {
  const r = await fetch(url, {
    signal: AbortSignal.timeout(8000),
    headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)', 'Accept': 'application/json,text/csv,*/*' },
  });
  if (!r.ok) throw new Error(new URL(url).host + ': ' + r.status);
  return r;
}

async function stooqOne(sym) {
  const text = await (await jget(`https://stooq.com/q/l/?s=${sym}&f=sd2t2ohlcv&h&e=csv`)).text();
  const close = parseFloat(text.trim().split('\n')[1]?.split(',')[6]);
  if (!isFinite(close)) throw new Error('stooq: пусто');
  return close;
}

// порядок = приоритет; первый сработавший побеждает
const RATE_SOURCES = {
  'EURUSD': [
    async () => (await (await jget('https://api.frankfurter.app/latest?from=EUR&to=USD')).json()).rates.USD,
    async () => (await (await jget('https://open.er-api.com/v6/latest/EUR')).json()).rates.USD,
    () => stooqOne('eurusd'),
  ],
  'BTCUSD': [
    async () => parseFloat((await (await jget('https://api.coinbase.com/v2/prices/BTC-USD/spot')).json()).data.amount),
    async () => (await (await jget('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd')).json()).bitcoin.usd,
    () => stooqOne('btcusd'),
  ],
  'XAUUSD': [   // PAXG = токенизированная унция золота, честный прокси спота
    async () => (await (await jget('https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd')).json())['pax-gold'].usd,
    () => stooqOne('xauusd'),
  ],
  // американские ETF: Yahoo → stooq (тикер.us)
  ...Object.fromEntries(['SCHD', 'IVV', 'VHT'].map(sym => [sym, [
    async () => (await (await jget(`https://query1.finance.yahoo.com/v8/finance/chart/${sym}?range=1d&interval=1d`)).json()).chart.result[0].meta.regularMarketPrice,
    () => stooqOne(sym.toLowerCase() + '.us'),
  ]])),
};

export async function ratesRefresh(db) {
  const errors = [];
  for (const [sym, sources] of Object.entries(RATE_SOURCES)) {
    let price = null;
    for (const fn of sources) {
      try { price = await fn(); if (isFinite(price) && price > 0) break; price = null; }
      catch (e) { errors.push(`${sym}: ${e.message}`); }
    }
    if (price == null) continue;
    const prev = db.prepare('SELECT price FROM rates WHERE symbol = ?').get(sym)?.price;
    const chg = prev ? (price - prev) / prev * 100 : null;
    db.prepare(`INSERT INTO rates(symbol, label, price, change_pct, updated_at)
      VALUES(?,?,?,?,datetime('now'))
      ON CONFLICT(symbol) DO UPDATE SET price = excluded.price, change_pct = excluded.change_pct, updated_at = excluded.updated_at`)
      .run(sym, RATE_LABELS[sym] ?? sym, price, chg);
  }
  const rates = db.prepare('SELECT * FROM rates').all();
  if (rates.every(r => r.price == null)) throw new Error('ни один источник не ответил: ' + errors.join('; '));
  return { rates, errors };
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
  // синк с привязанной задачей: исполнен шаг ↔ закрыта задача
  if ('status' in b) {
    const s = db.prepare('SELECT task_id FROM steps WHERE id = ?').get(id);
    if (s?.task_id)
      db.prepare(`UPDATE nodes SET status = ?, updated_at = datetime('now') WHERE id = ? AND kind = 'task'`)
        .run(b.status === 'done' ? 'done' : 'todo', s.task_id);
  }
}
export function delStep(db, id) { db.prepare('DELETE FROM steps WHERE id = ?').run(id); }

// Шаг → задача в категории «Финансы». Идемпотентно: повторный вызов вернёт существующую.
export function stepToTask(db, id) {
  const s = db.prepare('SELECT * FROM steps WHERE id = ?').get(id);
  if (!s) throw new Error('step not found');
  if (s.task_id) {
    const existing = db.prepare('SELECT * FROM nodes WHERE id = ?').get(s.task_id);
    if (existing) return { ...existing, already: true };
  }
  const fin = db.prepare(`SELECT id FROM nodes WHERE is_category = 1 AND title = 'Финансы' AND parent_id IS NULL`).get();
  const KIND = { buy: 'Купить', sell: 'Продать', transfer: 'Перевести' };
  const node = addChild(db, fin?.id ?? null, `${KIND[s.kind] ?? s.kind}: ${s.title}`);
  const updated = updateNode(db, node.id, {
    kind: 'task',
    due_date: s.planned_date ?? null,
    note: ['из плана шагов портфеля', s.amount ? `сумма: ${s.amount}` : '', s.condition ? `условие: ${s.condition}` : '']
      .filter(Boolean).join(' · '),
  });
  db.prepare('UPDATE steps SET task_id = ? WHERE id = ?').run(node.id, id);
  return updated;
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

// ===== Расходы/доходы =====
export function addTx(db, b) {
  db.prepare('INSERT INTO transactions(date, amount, currency, direction, category, note, source) VALUES(?,?,?,?,?,?,?)')
    .run(b.date ?? today(), Math.abs(b.amount ?? 0), b.currency ?? '€',
         b.direction ?? 'expense', b.category?.trim() || 'прочее', b.note ?? '', b.source ?? 'manual');
}
export function patchTx(db, id, b) {
  for (const k of ['date', 'amount', 'currency', 'direction', 'category', 'note'])
    if (k in b) db.prepare(`UPDATE transactions SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delTx(db, id) { db.prepare('DELETE FROM transactions WHERE id = ?').run(id); }

export function txMonth(db, ym) {
  const rows = db.prepare(`SELECT * FROM transactions WHERE date LIKE ? ORDER BY date DESC, id DESC`).all(ym + '%');
  const sum = dir => rows.filter(t => t.direction === dir).reduce((s, t) => s + t.amount, 0);
  const byCat = {};
  for (const t of rows.filter(t => t.direction === 'expense'))
    byCat[t.category] = (byCat[t.category] ?? 0) + t.amount;
  return {
    month: ym, rows,
    expense: sum('expense'), income: sum('income'),
    categories: Object.entries(byCat).sort((a, b) => b[1] - a[1]),
  };
}

// Импорт Monefy CSV: разделитель и колонки определяются по заголовку
export function importMonefy(db, csv) {
  const lines = String(csv).replace(/\r/g, '').split('\n').filter(l => l.trim());
  if (lines.length < 2) return 0;
  const delim = (lines[0].match(/;/g) ?? []).length >= (lines[0].match(/,/g) ?? []).length ? ';' : ',';
  const split = l => l.split(delim).map(c => c.replace(/^"|"$/g, '').trim());
  const head = split(lines[0]).map(h => h.toLowerCase());
  const col = (...names) => head.findIndex(h => names.some(n => h.includes(n)));
  const iDate = col('date', 'дата'), iAmount = col('amount', 'сумма'),
        iCat = col('category', 'категория'), iCur = col('currency', 'валюта'),
        iNote = col('description', 'note', 'описание');
  if (iDate < 0 || iAmount < 0) throw new Error('не нашёл колонки date/amount в заголовке CSV');
  let count = 0;
  for (const line of lines.slice(1)) {
    const c = split(line);
    const rawAmount = parseFloat((c[iAmount] ?? '').replace(/\s/g, '').replace(',', '.'));
    const date = parseAnyDate(c[iDate]);
    if (!date || isNaN(rawAmount)) continue;
    addTx(db, {
      date,
      amount: Math.abs(rawAmount),
      direction: rawAmount < 0 ? 'expense' : 'income',
      category: iCat >= 0 && c[iCat] ? c[iCat] : 'прочее',
      currency: iCur >= 0 && c[iCur] ? normCur(c[iCur]) : '€',
      note: iNote >= 0 ? (c[iNote] ?? '') : '',
      source: 'monefy',
    });
    count++;
  }
  return count;
}

function normCur(c) {
  const u = c.toUpperCase();
  if (u.includes('USD') || u === '$') return '$';
  return '€';
}

export function parseAnyDate(s) {
  s = String(s ?? '').trim();
  let m;
  if ((m = s.match(/^(\d{4})-(\d{2})-(\d{2})/))) return `${m[1]}-${m[2]}-${m[3]}`;
  if ((m = s.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})/)))
    return `${m[3]}-${String(m[2]).padStart(2, '0')}-${String(m[1]).padStart(2, '0')}`;
  return null;
}

// ===== FIRE =====
export function getSetting(db, key, fallback = null) {
  return db.prepare('SELECT value FROM settings WHERE key = ?').get(key)?.value ?? fallback;
}
export function setSetting(db, key, value) {
  db.prepare('INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value')
    .run(key, String(value));
}

export function fireCalc(db, capital) {
  const target = parseFloat(getSetting(db, 'fire_target', '0')) || 0;
  const annual = parseFloat(getSetting(db, 'fire_return_pct', '5')) || 0;
  const monthly = parseFloat(getSetting(db, 'fire_monthly_savings', '0')) || 0;
  if (!target) return { target: 0 };
  const r = Math.pow(1 + annual / 100, 1 / 12) - 1;
  let cap = capital, months = 0;
  while (cap < target && months < 1200) { cap = cap * (1 + r) + monthly; months++; }
  return {
    target, annual, monthly,
    progressPct: Math.min(100, capital / target * 100),
    months: months >= 1200 ? null : months,
    reachedYear: months >= 1200 ? null : new Date().getFullYear() + Math.floor((new Date().getMonth() + months) / 12),
  };
}

// ===== Макро =====
export function addMacro(db, b) {
  db.prepare('INSERT INTO macro_notes(date, phase, thesis) VALUES(?,?,?)')
    .run(b.date ?? today(), b.phase ?? '', b.thesis ?? '');
}
export function delMacro(db, id) { db.prepare('DELETE FROM macro_notes WHERE id = ?').run(id); }

// ===== Журнал прогнозов: «думаю, X случится — уверен на N%» → проверка → калибровка =====
export function addForecast(db, b) {
  const conf = Math.max(1, Math.min(99, Math.round(+b.confidence || 50)));
  db.prepare('INSERT INTO forecasts(statement, confidence, due_date) VALUES(?,?,?)')
    .run(b.statement, conf, b.due_date ?? null);
}
export function resolveForecast(db, id, outcome) {
  db.prepare(`UPDATE forecasts SET outcome = ?, resolved_at = date('now') WHERE id = ?`)
    .run(outcome ? 1 : 0, id);
}
export function delForecast(db, id) { db.prepare('DELETE FROM forecasts WHERE id = ?').run(id); }

export function forecasts(db) {
  const rows = db.prepare('SELECT * FROM forecasts ORDER BY outcome IS NOT NULL, due_date IS NULL, due_date, id DESC').all();
  const resolved = rows.filter(r => r.outcome != null);
  // калибровка: 100 − средняя ошибка |уверенность − исход·100|
  const calibration = resolved.length
    ? 100 - resolved.reduce((s, r) => s + Math.abs(r.confidence - r.outcome * 100), 0) / resolved.length
    : null;
  return { rows, calibration, resolvedCount: resolved.length };
}

// ===== Имущество и регламенты (правило = обязательство с property_id) =====
export function addProperty(db, b) {
  db.prepare('INSERT INTO properties(name, category, note) VALUES(?,?,?)')
    .run(b.name, b.category ?? 'прочее', b.note ?? '');
}
export function patchProperty(db, id, b) {
  for (const k of ['name', 'category', 'note'])
    if (k in b) db.prepare(`UPDATE properties SET ${k} = ? WHERE id = ?`).run(b[k], id);
}
export function delProperty(db, id) {
  db.prepare('DELETE FROM obligations WHERE property_id = ?').run(id);
  db.prepare('DELETE FROM properties WHERE id = ?').run(id);
}

export function listProperties(db) {
  const today = new Date().toISOString().slice(0, 10);
  return db.prepare('SELECT * FROM properties ORDER BY category, name').all().map(p => ({
    ...p,
    rules: db.prepare('SELECT * FROM obligations WHERE property_id = ? ORDER BY next_date IS NULL, next_date').all(p.id)
      .map(o => ({ ...o, days_left: o.next_date ? Math.ceil((Date.parse(o.next_date) - Date.parse(today)) / 864e5) : null })),
  }));
}

// правило регламента: имя автоматически префиксуется объектом (видно в календаре/радаре)
export function addRule(db, propertyId, b) {
  const prop = db.prepare('SELECT * FROM properties WHERE id = ?').get(propertyId);
  if (!prop) throw new Error('объект не найден');
  db.prepare(`INSERT INTO obligations(name, amount, currency, period, next_date, remind_days, kind, property_id)
    VALUES(?,?,?,?,?,?,'liability',?)`)
    .run(`${prop.name}: ${b.name}`, b.amount ?? 0, b.currency ?? '€', b.period ?? 'yearly',
         b.next_date ?? null, b.remind_days ?? 7, propertyId);
}

/* Финансы: курсы · портфель (автоцена qty×курс) · счета · расходы · долги · планы · FIRE · макро */
let finData = null;
let finTab = 'fact';        // факт | целевой (портфель)
let finSection = 'all';     // подвкладка раздела
let finTxMonth = new Date().toISOString().slice(0, 7);
let showMonefy = false;

const finApi = {
  list: () => fetch('/api/fin').then(r => r.json()),
  add: (ent, b) => fetch(`/api/fin/${ent}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  patch: (ent, id, b) => fetch(`/api/fin/${ent}/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  del: (ent, id) => fetch(`/api/fin/${ent}/${id}`, { method: 'DELETE' }),
  pay: id => fetch(`/api/fin/obligations/${id}/pay`, { method: 'POST' }),
  toTask: id => fetch(`/api/fin/steps/${id}/task`, { method: 'POST' }).then(r => r.json()),
  txMonth: ym => fetch('/api/fin/tx?month=' + ym).then(r => r.json()),
  monefy: csv => fetch('/api/fin/monefy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ csv }) }).then(r => r.json()),
  fire: b => fetch('/api/fin/fire', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  macroAdd: b => fetch('/api/fin/macro', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  macroDel: id => fetch('/api/fin/macro/' + id, { method: 'DELETE' }),
  ratesRefresh: () => fetch('/api/rates/refresh', { method: 'POST' }).then(r => r.json()),
  rateSet: (sym, price) => fetch('/api/rates/' + encodeURIComponent(sym), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ price }) }),
};

const fmt = n => n == null ? '—' : Math.round(n).toLocaleString('ru-RU');
const fmtE = n => n == null ? '—' : fmt(n) + ' €';
const fesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const parseNum = s => {
  let t = String(s).trim().toLowerCase().replace(/\s/g, '').replace(',', '.');
  let mul = 1;
  if (t.endsWith('k')) { mul = 1e3; t = t.slice(0, -1); }
  if (t.endsWith('m')) { mul = 1e6; t = t.slice(0, -1); }
  const v = parseFloat(t);
  return isNaN(v) ? null : v * mul;
};
const ACCT = { bank: 'банк', broker: 'брокер', cash: 'кэш', crypto: 'крипто', deposit: 'вклад', safe: 'ячейка' };
const ATYPES = ['крипто', 'кеш', 'баланс', 'недвижка', 'авто', 'акции', 'золото', 'облигации'];
const RSYMS = ['BTCUSD', 'XAUUSD', '^SPX'];
const STEPK = { buy: ['купить', 'ok'], sell: ['продать', 'p1'], transfer: ['перевод', 'p2'] };
const PERIOD = { monthly: 'мес', yearly: 'год', once: 'разово' };
const RATE_FMT = { 'XAUUSD': v => '$' + fmt(v), 'EURUSD': v => v?.toFixed(4), 'BTCUSD': v => '$' + fmt(v), '^SPX': v => fmt(v) };

window.loadFin = async function () {
  finData = await finApi.list();
  if (finTxMonth !== new Date().toISOString().slice(0, 7))
    finData.tx = await finApi.txMonth(finTxMonth);
  renderFin();
};

// ===== Портфель: строки таблицы =====
function portRows(it, depth) {
  const target = finTab === 'target';
  const editable = it.kind === 'asset' || !it.children.length;
  const rowCls = it.kind === 'block' ? 'pblock' : it.kind === 'section' ? 'psection' : '';
  let cells;
  if (target) {
    cells = `<td class="r num muted">${fmtE(it.eur)}</td>
      <td class="r num ed acc" data-fe="items:${it.id}:target_value:num" title="клик — целевая сумма">${it.target != null ? fmtE(it.target) : '—'}</td>
      <td class="r">${it.target != null ? `<span class="pill ${it.eur - it.target >= 0 ? 'ok' : 'p1'}">Δ ${fmt(it.eur - it.target)}</span>` : ''}</td>`;
  } else {
    const g = it.invested != null && it.invested ? (it.investedCur - it.invested) / it.invested * 100 : null;
    const cur = it.currency ?? '€';
    const valueCell = it.auto
      ? `<td class="r num acc" title="авто: ${it.qty} × курс ${it.rate_symbol}">⚡ ${fmt(it.value)} $</td>`
      : editable
        ? `<td class="r num acc"><span class="pill btn" data-fcur="${it.id}:${cur}" title="сменить валюту">${cur}</span>
            <span class="ed" data-fe="items:${it.id}:value:num" title="текущая стоимость (клик)">${it.value != null ? fmt(it.value) : '—'}</span></td>`
        : `<td class="r num acc">${fmtE(it.eur)}</td>`;
    cells = `<td class="r num muted ${editable ? 'ed' : ''}" ${editable ? `data-fe="items:${it.id}:buy_value:num" title="цена покупки (клик)"` : ''}>${editable ? (it.buy_value != null ? fmt(it.buy_value) : '—') : (it.invested != null ? fmt(it.invested) : '')}</td>
      <td class="r num">${g != null ? `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>` : ''}</td>
      ${valueCell}`;
  }
  return `<tr class="${rowCls}">
    <td style="padding-left:${8 + depth * 22}px">
      <span class="ed" data-fe="items:${it.id}:name:text" title="клик — переименовать">${fesc(it.name)}</span>
      ${editable && it.asset_type ? `<span class="pill" data-ftype="${it.id}" title="тип актива — клик">${fesc(it.asset_type)}</span>` : ''}
      ${it.rate_symbol ? `<span class="pill btn" data-fqty="${it.id}" title="количество — клик">${it.qty ?? '?'} × ${fesc(it.rate_symbol)}</span>` : ''}
      ${it.is_loan ? '<span class="pill p2">🤝 займ</span>' : ''}
    </td>
    ${cells}
    <td class="r" style="width:96px;white-space:nowrap">
      ${!target && it.kind === 'block' ? `<span class="rowbtn" data-fadd="section:${it.id}" title="добавить раздел">＋</span>` : ''}
      ${!target && it.kind === 'section' ? `<span class="rowbtn" data-fadd="asset:${it.id}" title="добавить актив">＋</span>` : ''}
      ${!target && editable && !it.asset_type ? `<span class="rowbtn" data-ftype="${it.id}" title="задать тип актива">⊙</span>` : ''}
      ${!target && editable ? `<span class="rowbtn" data-frate="${it.id}" title="${it.rate_symbol ? 'автоцена: сменить/убрать тикер' : 'автоцена по курсу (BTC/золото/S&P)'}">⚡</span>` : ''}
      ${!target && editable ? `<span class="rowbtn" data-loanflag="${it.id}:${it.is_loan ? 1 : 0}" title="${it.is_loan ? 'убрать значок займа' : 'пометить как займ'}">🤝</span>` : ''}
      ${!target ? `<span class="rowbtn del" data-findel="items:${it.id}">✕</span>` : ''}
    </td>
  </tr>` + it.children.map(c => portRows(c, depth + 1)).join('');
}

// ===== Секции =====
function secPortfolio(d, s) {
  return `
  <div class="sec">Портфель · блоки → разделы → активы · всё правится кликом</div>
  <div class="viewtabs">
    <span class="pill btn ${finTab === 'fact' ? 'ok' : ''}" data-fintab="fact">Факт</span>
    <span class="pill btn ${finTab === 'target' ? 'ok' : ''}" data-fintab="target">Целевой портфель</span>
  </div>
  <div class="card">
    <table class="fintable porttable">
      ${finTab === 'target'
        ? '<tr><th>Название</th><th class="r">Факт</th><th class="r">Цель</th><th class="r">Δ</th><th></th></tr>'
        : '<tr><th>Название</th><th class="r">Покупка</th><th class="r">Прирост</th><th class="r">Текущая</th><th></th></tr>'}
      ${d.portfolio.map(b => portRows(b, 0)).join('')}
    </table>
    ${finTab === 'target' ? '<div class="empty" style="padding-top:8px">Целевые суммы ставь на любом уровне. Δ — факт минус цель.</div>' : ''}
  </div>
  ${finTab === 'fact' && d.byType.length ? `
  <div class="card">
    <div class="meta" style="margin-bottom:6px">АЛЛОКАЦИЯ ПО ТИПАМ АКТИВОВ (⊙ у строки — задать тип)</div>
    ${d.byType.map(([t, v]) => `
      <div class="kv"><span>${fesc(t)}</span><b class="num">${fmt(v)} € · ${(v / s.portfolioTotal * 100).toFixed(1)}%</b></div>
      <div class="bar" style="margin:2px 0 6px"><i style="width:${v / d.byType[0][1] * 100}%"></i></div>`).join('')}
  </div>` : ''}`;
}

function secAccounts(d) {
  return `
  <div class="sec">Счета · название и баланс правятся кликом</div>
  <div class="card">
    ${d.accounts.map(a => `
      <div class="task">
        <span class="pill">${ACCT[a.type] ?? a.type}</span>
        <span class="t ed" data-fe="accounts:${a.id}:name:text">${fesc(a.name)}</span>
        ${a.stale_days > 21 ? `<span class="meta amber">⚠ ${a.stale_days} дн.</span>` : `<span class="meta">обн. ${a.balance_updated_at.slice(0, 10)}</span>`}
        <span class="ed num" data-fe="accounts:${a.id}:balance:num">${fmt(a.balance)} ${fesc(a.currency)}</span>
        <span class="rowbtn del" data-findel="accounts:${a.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <input id="accName" placeholder="новый счёт: название">
      <select id="accType">${Object.entries(ACCT).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
      <select id="accCur"><option>€</option><option>$</option></select>
      <input id="accBal" placeholder="баланс" style="width:110px">
      <span class="pill btn ok" id="accAdd">＋</span>
    </div>
  </div>`;
}

function renderTx(tx) {
  const maxCat = tx.categories[0]?.[1] ?? 1;
  return `
  <div class="sec">Расходы и доходы</div>
  <div class="card">
    <div class="task" style="border-bottom:1px solid var(--line)">
      <span class="pill btn" id="txPrev">‹</span>
      <b class="num" style="min-width:70px;text-align:center">${tx.month}</b>
      <span class="pill btn" id="txNext">›</span>
      <span class="meta">расход: <b class="down">${fmt(tx.expense)} €</b> · доход: <b class="up">${fmt(tx.income)} €</b> · итого: ${fmt(tx.income - tx.expense)} €</span>
      <span class="pill btn" id="monefyToggle" style="margin-left:auto">⤓ Monefy CSV</span>
    </div>
    ${showMonefy ? `
      <div style="padding:8px 0">
        <textarea id="monefyCsv" rows="6" style="width:100%;border:1px solid var(--line);border-radius:8px;padding:8px;font:12px var(--mono)" placeholder="Вставь CSV-экспорт Monefy (с заголовком). Разделитель ; или , — определю. Минус = расход."></textarea>
        <div class="btnrow" style="margin-top:6px"><span class="pill btn ok" id="monefyGo">Импортировать</span></div>
      </div>` : ''}
    ${tx.categories.length ? `<div style="padding:8px 0 4px">` + tx.categories.slice(0, 6).map(([cat, sum]) => `
      <div class="kv"><span>${fesc(cat)}</span><b class="num">${fmt(sum)} €</b></div>
      <div class="bar" style="margin:2px 0 6px"><i style="width:${sum / maxCat * 100}%"></i></div>`).join('') + '</div>' : ''}
    ${tx.rows.slice(0, 15).map(t => `
      <div class="task">
        <span class="meta num">${t.date.slice(5)}</span>
        <span class="pill ${t.direction === 'income' ? 'ok' : 'p1'}">${t.direction === 'income' ? 'доход' : 'расход'}</span>
        <span class="ed meta" data-fe="tx:${t.id}:category:text">${fesc(t.category)}</span>
        <span class="t ed" data-fe="tx:${t.id}:note:text">${fesc(t.note) || '—'}</span>
        ${t.source === 'monefy' ? '<span class="meta">monefy</span>' : ''}
        <span class="ed num" data-fe="tx:${t.id}:amount:num">${fmt(t.amount)} ${fesc(t.currency)}</span>
        <span class="rowbtn del" data-findel="tx:${t.id}">✕</span>
      </div>`).join('')}
    ${tx.rows.length > 15 ? `<div class="empty">…и ещё ${tx.rows.length - 15} за месяц</div>` : ''}
    <div class="task finadd">
      <input id="txDate" value="${new Date().toISOString().slice(0, 10)}" style="width:105px">
      <select id="txDir"><option value="expense">расход</option><option value="income">доход</option></select>
      <input id="txCat" placeholder="категория" style="width:120px">
      <input id="txAmount" placeholder="сумма" style="width:90px">
      <input id="txNote" placeholder="заметка">
      <span class="pill btn ok" id="txAdd">＋</span>
    </div>
  </div>`;
}

// Долги: ручные (мои и мне) + плановые из портфеля (значок 🤝)
function secDebts(d) {
  return `
  <div class="sec">Долги</div>
  <div class="card">
    ${d.debts.map(x => `
      <div class="task">
        <span class="pill ${x.direction === 'i_owe' ? 'p0' : 'ok'}" data-ddir="${x.id}:${x.direction}" title="клик — поменять направление" style="cursor:pointer">${x.direction === 'i_owe' ? 'я должен' : 'мне должны'}</span>
        <span class="t ed" data-fe="debts:${x.id}:name:text">${fesc(x.name)}</span>
        <span class="ed meta ${x.overdue_days > 0 ? 'amber' : ''}" data-fe="debts:${x.id}:due_date:date">${x.due_date ?? '+срок'}${x.overdue_days > 0 ? ` · просрочен ${x.overdue_days} дн ⚠` : ''}</span>
        <span class="pill btn" data-dcur="${x.id}:${x.currency}" title="сменить валюту">${fesc(x.currency)}</span>
        <span class="ed num" data-fe="debts:${x.id}:amount:num">${fmt(x.amount)}</span>
        <span class="rowbtn del" data-findel="debts:${x.id}">✕</span>
      </div>`).join('') || '<div class="empty">долгов нет</div>'}
    <div class="task finadd">
      <select id="dbDir"><option value="owed_to_me">мне должны</option><option value="i_owe">я должен</option></select>
      <input id="dbName" placeholder="кто и за что">
      <input id="dbAmount" placeholder="сумма" style="width:90px">
      <select id="dbCur"><option>€</option><option>$</option></select>
      <input id="dbDate" placeholder="срок" style="width:105px">
      <span class="pill btn ok" id="dbAdd">＋</span>
    </div>
    ${d.loans.length ? `<div class="meta" style="margin:10px 0 4px">ПЛАНОВЫЕ · ЗАЙМЫ ИЗ ПОРТФЕЛЯ (🤝)</div>` +
      d.loans.map(l => `
      <div class="task">
        <span class="pill p2">🤝</span>
        <span class="t ed" data-fe="items:${l.id}:name:text">${fesc(l.name)}</span>
        <span class="meta">${fesc(l.path)}</span>
        <span class="ed meta ${l.overdue_days > 0 ? 'amber' : ''}" data-fe="items:${l.id}:loan_due:date">${l.loan_due ?? '+дата возврата'}${l.overdue_days > 0 ? ` · просрочен ${l.overdue_days} дн ⚠` : ''}</span>
        <span class="num">${l.value != null ? fmt(l.value) : '—'} ${fesc(l.currency)}</span>
        <span class="pill btn" data-loanflag="${l.id}:1" title="вернули — убрать значок">✓ закрыт</span>
      </div>`).join('') : ''}
  </div>`;
}

function secPlans(d) {
  return `
  <div class="sec">План шагов · покупки / продажи</div>
  <div class="card">
    ${d.steps.map(st => {
      const [kl, kc] = STEPK[st.kind] ?? [st.kind, ''];
      const done = st.status === 'done';
      return `<div class="task">
        <span class="cb ${done ? 'done' : ''}" data-stepdone="${st.id}"></span>
        <span class="pill ${kc}">${kl}</span>
        <span class="t ${done ? 'done' : 'ed'}" ${done ? '' : `data-fe="steps:${st.id}:title:text"`}>${fesc(st.title)}</span>
        <span class="ed meta num" data-fe="steps:${st.id}:amount:num">${st.amount ? fmt(st.amount) : '+сумма'}</span>
        <span class="ed meta" data-fe="steps:${st.id}:planned_date:date">${st.planned_date ?? '+дата'}</span>
        <span class="ed meta" data-fe="steps:${st.id}:condition:text">${st.condition ? 'усл: ' + fesc(st.condition) : '+условие'}</span>
        ${!done ? `<span class="pill btn" data-steptask="${st.id}">→ задача</span>` : ''}
        <span class="rowbtn del" data-findel="steps:${st.id}">✕</span>
      </div>`;
    }).join('') || '<div class="empty">шагов нет</div>'}
    <div class="task finadd">
      <select id="stKind"><option value="buy">купить</option><option value="sell">продать</option><option value="transfer">перевод</option></select>
      <input id="stTitle" placeholder="что и зачем">
      <span class="pill btn ok" id="stAdd">＋</span>
    </div>
  </div>

  <div class="sec">Обязательства, подписки и плановые траты · «✓» = оплачено</div>
  <div class="card">
    ${d.obligations.map(o => `
      <div class="task">
        <span class="pill ${o.kind === 'subscription' ? 'p2' : 'p1'}">${o.kind === 'subscription' ? 'подписка' : o.period === 'once' ? 'трата' : 'пассив'}</span>
        <span class="t ed" data-fe="obligations:${o.id}:name:text">${fesc(o.name)}</span>
        <span class="ed meta num" data-fe="obligations:${o.id}:amount:num">${fmt(o.amount)} ${fesc(o.currency)} / ${PERIOD[o.period]}</span>
        ${o.next_date
          ? `<span class="ed meta ${o.days_left <= o.remind_days ? 'amber' : ''}" data-fe="obligations:${o.id}:next_date:date">${o.next_date} (${o.days_left} дн.)</span>
             <span class="pill btn ok" data-oblpay="${o.id}">✓</span>`
          : `<span class="ed meta" data-fe="obligations:${o.id}:next_date:date">+дата</span>`}
        <span class="rowbtn del" data-findel="obligations:${o.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <select id="obKind"><option value="liability">пассив</option><option value="subscription">подписка</option></select>
      <input id="obName" placeholder="название (кредит, аренда, разовая крупная трата…)">
      <input id="obAmount" placeholder="сумма" style="width:90px">
      <select id="obPeriod"><option value="monthly">мес</option><option value="yearly">год</option><option value="once">разово</option></select>
      <input id="obDate" placeholder="след. дата" style="width:105px">
      <span class="pill btn ok" id="obAdd">＋</span>
    </div>
    <div class="empty">Крупная плановая трата = «разово» с датой: попадёт в календарь и в радар задач.</div>
  </div>`;
}

function secFire(d, s) {
  return `
  <div class="sec">FIRE · Макро</div>
  <div class="fingrid" style="grid-template-columns:1fr 1fr">
    <div class="card">
      <div class="meta">FIRE · ЦЕЛЕВОЙ КАПИТАЛ</div>
      ${d.fire.target ? `
        <div class="bignum">${d.fire.progressPct.toFixed(1)}%</div>
        <div class="bar"><i style="width:${d.fire.progressPct}%"></i></div>
        <div class="kv" style="margin-top:6px">Цель <b class="ed num" data-fireset="fire_target">${fmt(d.fire.target)} €</b></div>
        <div class="kv">Доходность, %/год <b class="ed num" data-fireset="fire_return_pct">${d.fire.annual}</b></div>
        <div class="kv">Пополнение, €/мес <b class="ed num" data-fireset="fire_monthly_savings">${fmt(d.fire.monthly)}</b></div>
        <div class="meta" style="margin-top:6px">${d.fire.months != null
          ? (d.fire.months === 0 ? '🎉 цель достигнута' : `прогноз: ~${d.fire.reachedYear} год (через ${Math.round(d.fire.months / 12 * 10) / 10} лет)`)
          : 'при таких параметрах цель не достигается'}</div>`
      : `<div class="muted" style="margin:8px 0">Задай цель — посчитаю прогресс от портфеля (${fmt(s.portfolioTotal)} €) и год достижения.</div>
        <div class="btnrow"><span class="pill btn ok ed" data-fireset="fire_target">задать цель, €</span></div>`}
    </div>
    <div class="card">
      <div class="meta">МАКРО · МОЙ ТЕЗИС</div>
      ${d.macro.length ? `
        <div style="font-weight:600;margin:6px 0">${fesc(d.macro[0].phase)} <span class="meta">· ${d.macro[0].date}</span></div>
        <div style="font-size:12.5px;margin-bottom:8px">${fesc(d.macro[0].thesis)}</div>`
      : '<div class="muted" style="margin:8px 0">В какой фазе цикла мы? Запиши тезис — останется в истории.</div>'}
      <div class="task finadd">
        <select id="mcPhase"><option>рост</option><option>пик</option><option>сжатие</option><option>дно</option></select>
        <input id="mcThesis" placeholder="тезис: что жду и что делаю…">
        <span class="pill btn ok" id="mcAdd">＋</span>
      </div>
      ${d.macro.length > 1 ? `<div class="meta" style="margin-top:6px">история:</div>` +
        d.macro.slice(1, 4).map(mn => `<div class="kv"><span>${mn.date} · ${fesc(mn.phase)} — ${fesc(mn.thesis.slice(0, 60))}</span><span class="rowbtn del" style="opacity:1" data-mcdel="${mn.id}">✕</span></div>`).join('') : ''}
    </div>
  </div>`;
}

function renderFin() {
  const d = finData, s = d.summary;
  const accStr = Object.entries(s.accountsByCurrency).map(([c, v]) => `${fmt(v)} ${c}`).join(' · ') || '—';
  const head = `
  <div class="ratesbar">
    ${d.rates.map(r => `<span class="ratepill">
      <b>${fesc(r.label)}</b>
      <span class="ed num" data-rate="${fesc(r.symbol)}" title="клик — ввести вручную">${r.price != null ? (RATE_FMT[r.symbol] ?? fmt)(r.price) : '—'}</span>
      ${r.change_pct != null ? `<span class="${r.change_pct >= 0 ? 'up' : 'down'}">${r.change_pct >= 0 ? '▲' : '▼'}${Math.abs(r.change_pct).toFixed(2)}%</span>` : ''}
    </span>`).join('')}
    <span class="pill btn" id="ratesRefresh">↻ обновить</span>
    <span class="meta">${d.rates[0]?.updated_at ? 'обн. ' + d.rates[0].updated_at.slice(0, 16).replace('T', ' ') : 'курсы не загружались'}</span>
  </div>
  <div class="fingrid">
    <div class="card"><div class="meta">СЧЕТА</div>
      <div class="bignum" style="font-size:16px">${accStr}</div>
      <div class="meta">${d.accounts.length} счетов</div></div>
    <div class="card"><div class="meta">ПОРТФЕЛЬ · ФАКТ</div>
      <div class="bignum">${fmtE(s.portfolioTotal)} <span style="font-size:14px;color:var(--muted)">· ${fmt(s.portfolioTotalUsd)} $</span></div>
      <div class="meta">курс ${s.rate?.toFixed(4)}${d.snapshotDelta ? ` · с ${d.snapshotDelta.since}: ${d.snapshotDelta.abs >= 0 ? '+' : ''}${fmt(d.snapshotDelta.abs)} €` : ''}${s.growth ? ` · прирост: ${s.growth.abs >= 0 ? '+' : ''}${fmt(s.growth.abs)} € (${s.growth.pct.toFixed(1)}%)` : ''}</div></div>
    <div class="card"><div class="meta">ОБЯЗАТЕЛЬСТВА / МЕС</div>
      <div class="bignum">${fmt(s.monthlyObligations)} €</div>
      <div class="meta">${s.upcoming.length ? `ближайшие 30 дней: ${s.upcoming.length}` : 'на месяц тихо'}</div></div>
  </div>
  <div class="viewtabs">
    ${[['all', 'Всё'], ['port', 'Портфель'], ['acc', 'Счета'], ['flow', 'Расходы'], ['debts', 'Долги'], ['plans', 'Планы'], ['fire', 'FIRE·Макро']]
      .map(([k, l]) => `<span class="pill btn ${finSection === k ? 'ok' : ''}" data-fsec="${k}">${l}</span>`).join(' ')}
  </div>`;

  const show = k => finSection === 'all' || finSection === k;
  document.getElementById('screen-fin').innerHTML = head
    + (show('port') ? secPortfolio(d, s) : '')
    + (show('acc') ? secAccounts(d) : '')
    + (show('flow') ? renderTx(d.tx) : '')
    + (show('debts') ? secDebts(d) : '')
    + (show('plans') ? secPlans(d) : '')
    + (show('fire') ? secFire(d, s) : '')
    + `<div class="footer-hint">Бивалютно: € и $ по курсу EURUSD. ⚡ — автоцена «количество × курс» (BTC, золото, S&P). Ввод понимает «100k», «1.2m», даты — и 01.07.2026. Платежи и траты видны в календаре и радаре задач.</div>`;
  bindFin();
}

function inlineVal(el, type, onSave) {
  const input = document.createElement('input');
  input.className = 'inlineedit';
  input.style.maxWidth = type === 'text' ? '220px' : '120px';
  input.placeholder = el.textContent.trim();
  if (type === 'text') input.value = el.textContent.trim().replace(/^(усл: |\+.*)/, '');
  el.replaceWith(input);
  input.focus(); if (type === 'text') input.select();
  let done = false;
  const save = async () => {
    if (done) return; done = true;
    const raw = input.value.trim();
    if (raw) {
      let v = raw;
      if (type === 'num') { v = parseNum(raw); if (v == null) { window.loadFin(); return; } }
      if (type === 'date') {
        let mm;
        if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) v = raw;
        else if ((mm = raw.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})$/)))
          v = `${mm[3]}-${mm[2].padStart(2, '0')}-${mm[1].padStart(2, '0')}`;
        else { alert('Дата: 2026-07-01 или 01.07.2026'); window.loadFin(); return; }
      }
      await onSave(v);
    }
    window.loadFin();
  };
  input.addEventListener('click', ev => ev.stopPropagation());
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') save();
    if (ev.key === 'Escape') { done = true; window.loadFin(); }
  });
  input.addEventListener('blur', save);
}

function bindFin() {
  const $ = id => document.getElementById(id);
  document.querySelectorAll('[data-fsec]').forEach(el =>
    el.addEventListener('click', () => { finSection = el.dataset.fsec; renderFin(); }));
  document.querySelectorAll('[data-fe]').forEach(el =>
    el.addEventListener('click', () => {
      const [ent, id, field, type] = el.dataset.fe.split(':');
      inlineVal(el, type, v => finApi.patch(ent, +id, { [field]: v }));
    }));
  document.querySelectorAll('[data-rate]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', v => finApi.rateSet(el.dataset.rate, v))));
  document.querySelectorAll('[data-fintab]').forEach(el =>
    el.addEventListener('click', () => { finTab = el.dataset.fintab; renderFin(); }));
  document.querySelectorAll('[data-fcur]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.fcur.split(':');
      await finApi.patch('items', +id, { currency: cur === '€' ? '$' : '€' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-fadd]').forEach(el =>
    el.addEventListener('click', async () => {
      const [kind, pid] = el.dataset.fadd.split(':');
      const name = prompt(kind === 'section' ? 'Название раздела:' : 'Название актива:');
      if (name?.trim()) { await finApi.add('items', { parent_id: +pid, name: name.trim(), kind }); window.loadFin(); }
    }));
  document.querySelectorAll('[data-findel]').forEach(el =>
    el.addEventListener('click', async () => {
      const [ent, id] = el.dataset.findel.split(':');
      if (confirm('Удалить запись (с вложенными, если есть)?')) { await finApi.del(ent, +id); window.loadFin(); }
    }));
  document.querySelectorAll('[data-stepdone]').forEach(el =>
    el.addEventListener('click', async () => {
      const st = finData.steps.find(x => x.id === +el.dataset.stepdone);
      await finApi.patch('steps', st.id, { status: st.status === 'done' ? 'planned' : 'done' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-steptask]').forEach(el =>
    el.addEventListener('click', async () => {
      const r = await finApi.toTask(+el.dataset.steptask);
      alert(r.error ? r.error : `Задача создана в категории «Финансы»: ${r.title}`);
    }));
  document.querySelectorAll('[data-oblpay]').forEach(el =>
    el.addEventListener('click', async () => { await finApi.pay(+el.dataset.oblpay); window.loadFin(); }));
  // займы, типы, автоцена
  document.querySelectorAll('[data-loanflag]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.loanflag.split(':');
      await finApi.patch('items', +id, { is_loan: cur === '1' ? 0 : 1 });
      window.loadFin();
    }));
  document.querySelectorAll('[data-ftype]').forEach(el =>
    el.addEventListener('click', () => {
      const id = +el.dataset.ftype;
      const sel = document.createElement('select');
      sel.innerHTML = '<option value="">— тип актива —</option>'
        + ATYPES.map(t => `<option>${t}</option>`).join('') + '<option value="__none">убрать тип</option>';
      el.replaceWith(sel);
      sel.focus();
      sel.addEventListener('change', async () => {
        await finApi.patch('items', id, { asset_type: sel.value === '__none' ? null : (sel.value || null) });
        window.loadFin();
      });
      sel.addEventListener('blur', () => window.loadFin());
    }));
  document.querySelectorAll('[data-fqty]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', v => finApi.patch('items', +el.dataset.fqty, { qty: v }))));
  document.querySelectorAll('[data-frate]').forEach(el =>
    el.addEventListener('click', () => {
      const id = +el.dataset.frate;
      const sel = document.createElement('select');
      sel.innerHTML = '<option value="">— тикер автоцены —</option>'
        + RSYMS.map(t => `<option>${t}</option>`).join('') + '<option value="__none">убрать автоцену</option>';
      el.replaceWith(sel);
      sel.focus();
      sel.addEventListener('change', async () => {
        if (sel.value === '__none') await finApi.patch('items', id, { rate_symbol: null, qty: null });
        else if (sel.value) {
          const q = parseNum(prompt(`Количество (${sel.value}):`) ?? '');
          await finApi.patch('items', id, { rate_symbol: sel.value, qty: q });
        }
        window.loadFin();
      });
      sel.addEventListener('blur', () => window.loadFin());
    }));
  // долги
  document.querySelectorAll('[data-ddir]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, dir] = el.dataset.ddir.split(':');
      await finApi.patch('debts', +id, { direction: dir === 'i_owe' ? 'owed_to_me' : 'i_owe' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-dcur]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.dcur.split(':');
      await finApi.patch('debts', +id, { currency: cur === '€' ? '$' : '€' });
      window.loadFin();
    }));
  $('dbAdd')?.addEventListener('click', async () => {
    if (!$('dbName').value.trim()) return;
    await finApi.add('debts', { name: $('dbName').value.trim(), direction: $('dbDir').value,
      amount: parseNum($('dbAmount').value) ?? 0, currency: $('dbCur').value,
      due_date: /^\d{4}-\d{2}-\d{2}$/.test($('dbDate').value) ? $('dbDate').value : null });
    window.loadFin();
  });
  // расходы
  const shiftYm = (ym, dd) => { const [y, m] = ym.split('-').map(Number); return new Date(Date.UTC(y, m - 1 + dd, 1)).toISOString().slice(0, 7); };
  $('txPrev')?.addEventListener('click', () => { finTxMonth = shiftYm(finTxMonth, -1); window.loadFin(); });
  $('txNext')?.addEventListener('click', () => { finTxMonth = shiftYm(finTxMonth, 1); window.loadFin(); });
  $('monefyToggle')?.addEventListener('click', () => { showMonefy = !showMonefy; renderFin(); });
  $('monefyGo')?.addEventListener('click', async () => {
    const csv = $('monefyCsv').value;
    if (!csv.trim()) return;
    const r = await finApi.monefy(csv);
    alert(r.error ? r.error : `Импортировано транзакций: ${r.imported}`);
    showMonefy = false;
    window.loadFin();
  });
  $('txAdd')?.addEventListener('click', async () => {
    const amount = parseNum($('txAmount').value);
    if (amount == null) return;
    await finApi.add('tx', { date: /^\d{4}-\d{2}-\d{2}$/.test($('txDate').value) ? $('txDate').value : undefined,
      direction: $('txDir').value, category: $('txCat').value.trim() || 'прочее',
      amount, note: $('txNote').value.trim() });
    window.loadFin();
  });
  // FIRE и макро
  document.querySelectorAll('[data-fireset]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', async v => { await finApi.fire({ [el.dataset.fireset]: v }); })));
  $('mcAdd')?.addEventListener('click', async () => {
    if (!$('mcThesis').value.trim()) return;
    await finApi.macroAdd({ phase: $('mcPhase').value, thesis: $('mcThesis').value.trim() });
    window.loadFin();
  });
  document.querySelectorAll('[data-mcdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить запись из истории тезисов?')) { await finApi.macroDel(+el.dataset.mcdel); window.loadFin(); }
    }));
  // прочее
  $('ratesRefresh')?.addEventListener('click', async () => {
    $('ratesRefresh').textContent = '…';
    const r = await finApi.ratesRefresh();
    if (r.error) alert(r.error);
    window.loadFin();
  });
  $('accAdd')?.addEventListener('click', async () => {
    if (!$('accName').value.trim()) return;
    await finApi.add('accounts', { name: $('accName').value.trim(), type: $('accType').value,
      currency: $('accCur').value, balance: parseNum($('accBal').value) ?? 0 });
    window.loadFin();
  });
  $('stAdd')?.addEventListener('click', async () => {
    if (!$('stTitle').value.trim()) return;
    await finApi.add('steps', { kind: $('stKind').value, title: $('stTitle').value.trim() });
    window.loadFin();
  });
  $('obAdd')?.addEventListener('click', async () => {
    if (!$('obName').value.trim()) return;
    await finApi.add('obligations', { kind: $('obKind').value, name: $('obName').value.trim(),
      amount: parseNum($('obAmount').value) ?? 0, period: $('obPeriod').value, currency: '€',
      next_date: /^\d{4}-\d{2}-\d{2}$/.test($('obDate').value) ? $('obDate').value : null });
    window.loadFin();
  });
}

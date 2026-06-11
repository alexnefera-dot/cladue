/* Финансы: курсы · портфель · счета · шаги · обязательства · расходы · дебиторка · FIRE · макро */
let finData = null;
let finTab = 'fact';   // fact | target
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
  received: id => fetch(`/api/fin/receivables/${id}/received`, { method: 'POST' }),
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
const STEPK = { buy: ['купить', 'ok'], sell: ['продать', 'p1'], transfer: ['перевод', 'p2'] };
const PERIOD = { monthly: 'мес', yearly: 'год', once: 'разово' };
const RATE_FMT = { 'XAUUSD': v => '$' + fmt(v), 'EURUSD': v => v?.toFixed(4), 'BTCUSD': v => '$' + fmt(v), '^SPX': v => fmt(v) };

window.loadFin = async function () {
  finData = await finApi.list();
  if (finTxMonth !== new Date().toISOString().slice(0, 7))
    finData.tx = await finApi.txMonth(finTxMonth);
  renderFin();
};

function portRows(it, depth) {
  const target = finTab === 'target';
  // редактируемы: активы и любые узлы без детей (новый пустой раздел можно оценить сразу)
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
    cells = editable
      ? `<td class="r num muted ${editable ? 'ed' : ''}" data-fe="items:${it.id}:buy_value:num" title="цена покупки (клик)">${it.buy_value != null ? fmt(it.buy_value) : '—'}</td>
        <td class="r num">${g != null ? `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>` : ''}</td>
        <td class="r num acc"><span class="pill btn" data-fcur="${it.id}:${cur}" title="сменить валюту">${cur}</span>
          <span class="ed" data-fe="items:${it.id}:value:num" title="текущая стоимость (клик)">${it.value != null ? fmt(it.value) : '—'}</span></td>`
      : `<td class="r num muted">${it.invested != null ? fmt(it.invested) : ''}</td>
        <td class="r num">${g != null ? `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>` : ''}</td>
        <td class="r num acc">${fmtE(it.eur)}</td>`;
  }
  return `<tr class="${rowCls}">
    <td style="padding-left:${8 + depth * 22}px"><span class="ed" data-fe="items:${it.id}:name:text" title="клик — переименовать">${fesc(it.name)}</span></td>
    ${cells}
    <td class="r" style="width:56px;white-space:nowrap">
      ${!target && it.kind === 'block' ? `<span class="rowbtn" data-fadd="section:${it.id}" title="добавить раздел">＋</span>` : ''}
      ${!target && it.kind === 'section' ? `<span class="rowbtn" data-fadd="asset:${it.id}" title="добавить актив">＋</span>` : ''}
      ${!target ? `<span class="rowbtn del" data-findel="items:${it.id}">✕</span>` : ''}
    </td>
  </tr>` + it.children.map(c => portRows(c, depth + 1)).join('');
}

function renderFin() {
  const d = finData, s = d.summary;
  const accStr = Object.entries(s.accountsByCurrency).map(([c, v]) => `${fmt(v)} ${c}`).join(' · ') || '—';
  document.getElementById('screen-fin').innerHTML = `
  <div class="ratesbar">
    ${d.rates.map(r => `<span class="ratepill">
      <b>${fesc(r.label)}</b>
      <span class="balance num" data-rate="${fesc(r.symbol)}" title="клик — ввести вручную">${r.price != null ? (RATE_FMT[r.symbol] ?? fmt)(r.price) : '—'}</span>
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
      <div class="meta">курс ${s.rate?.toFixed(4)} · ${s.growth ? `прирост: ${s.growth.abs >= 0 ? '+' : ''}${fmt(s.growth.abs)} € (${s.growth.pct.toFixed(1)}%)` : 'задай цены покупки — посчитаю прирост'}</div></div>
    <div class="card"><div class="meta">ОБЯЗАТЕЛЬСТВА / МЕС</div>
      <div class="bignum">${fmt(s.monthlyObligations)} €</div>
      <div class="meta">${s.upcoming.length ? `ближайшие 30 дней: ${s.upcoming.length}` : 'на месяц тихо'}</div></div>
  </div>

  <div class="sec">Портфель · блоки → разделы → активы · все значения и названия правятся кликом</div>
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
    ${finTab === 'target' ? '<div class="empty" style="padding-top:8px">Целевые суммы ставь на любом уровне: блок целиком или конкретный раздел. Δ — факт минус цель.</div>' : ''}
  </div>

  <div class="sec">Счета · название и баланс правятся кликом</div>
  <div class="card">
    ${d.accounts.map(a => `
      <div class="task">
        <span class="pill">${ACCT[a.type] ?? a.type}</span>
        <span class="t balance" data-fe="accounts:${a.id}:name:text">${fesc(a.name)}</span>
        ${a.stale_days > 21 ? `<span class="meta amber">⚠ ${a.stale_days} дн.</span>` : `<span class="meta">обн. ${a.balance_updated_at.slice(0, 10)}</span>`}
        <span class="balance num" data-fe="accounts:${a.id}:balance:num">${fmt(a.balance)} ${fesc(a.currency)}</span>
        <span class="rowbtn del" data-findel="accounts:${a.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <input id="accName" placeholder="новый счёт: название">
      <select id="accType">${Object.entries(ACCT).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
      <input id="accCur" value="€" style="width:42px">
      <input id="accBal" placeholder="баланс" style="width:110px">
      <span class="pill btn ok" id="accAdd">＋</span>
    </div>
  </div>

  <div class="sec">План шагов · всё правится кликом</div>
  <div class="card">
    ${d.steps.map(st => {
      const [kl, kc] = STEPK[st.kind] ?? [st.kind, ''];
      const done = st.status === 'done';
      return `<div class="task">
        <span class="cb ${done ? 'done' : ''}" data-stepdone="${st.id}"></span>
        <span class="pill ${kc}">${kl}</span>
        <span class="t ${done ? 'done' : 'balance'}" ${done ? '' : `data-fe="steps:${st.id}:title:text"`}>${fesc(st.title)}</span>
        <span class="balance meta num" data-fe="steps:${st.id}:amount:num">${st.amount ? fmt(st.amount) : '+сумма'}</span>
        <span class="balance meta" data-fe="steps:${st.id}:planned_date:date">${st.planned_date ?? '+дата'}</span>
        <span class="balance meta" data-fe="steps:${st.id}:condition:text">${st.condition ? 'усл: ' + fesc(st.condition) : '+условие'}</span>
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

  <div class="sec">Обязательства и подписки · «✓» = оплачено</div>
  <div class="card">
    ${d.obligations.map(o => `
      <div class="task">
        <span class="pill ${o.kind === 'subscription' ? 'p2' : 'p1'}">${o.kind === 'subscription' ? 'подписка' : 'пассив'}</span>
        <span class="t balance" data-fe="obligations:${o.id}:name:text">${fesc(o.name)}</span>
        <span class="balance meta num" data-fe="obligations:${o.id}:amount:num">${fmt(o.amount)} ${fesc(o.currency)} / ${PERIOD[o.period]}</span>
        ${o.next_date
          ? `<span class="balance meta ${o.days_left <= o.remind_days ? 'amber' : ''}" data-fe="obligations:${o.id}:next_date:date">${o.next_date} (${o.days_left} дн.)</span>
             <span class="pill btn ok" data-oblpay="${o.id}">✓</span>`
          : `<span class="balance meta" data-fe="obligations:${o.id}:next_date:date">+дата</span>`}
        <span class="rowbtn del" data-findel="obligations:${o.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <select id="obKind"><option value="liability">пассив</option><option value="subscription">подписка</option></select>
      <input id="obName" placeholder="название">
      <input id="obAmount" placeholder="сумма" style="width:90px">
      <select id="obPeriod"><option value="monthly">мес</option><option value="yearly">год</option><option value="once">разово</option></select>
      <input id="obDate" placeholder="след. дата" style="width:105px">
      <span class="pill btn ok" id="obAdd">＋</span>
    </div>
  </div>
  ${renderTx(d.tx)}
  ${renderReceivables(d.receivables)}

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
          : 'при таких параметрах цель не достигается — подкрути доходность или пополнение'}</div>`
      : `<div class="muted" style="margin:8px 0">Задай цель — посчитаю прогресс от портфеля (${fmt(s.portfolioTotal)} €) и год достижения.</div>
        <div class="btnrow"><span class="pill btn ok ed" data-fireset="fire_target">задать цель, €</span></div>`}
    </div>
    <div class="card">
      <div class="meta">МАКРО · МОЙ ТЕЗИС</div>
      ${d.macro.length ? `
        <div style="font-weight:600;margin:6px 0">${fesc(d.macro[0].phase)} <span class="meta">· ${d.macro[0].date}</span></div>
        <div style="font-size:12.5px;margin-bottom:8px">${fesc(d.macro[0].thesis)}</div>`
      : '<div class="muted" style="margin:8px 0">В какой фазе цикла мы? Запиши тезис — он останется в истории.</div>'}
      <div class="task finadd">
        <select id="mcPhase"><option>рост</option><option>пик</option><option>сжатие</option><option>дно</option></select>
        <input id="mcThesis" placeholder="тезис: что жду и что делаю…">
        <span class="pill btn ok" id="mcAdd">＋</span>
      </div>
      ${d.macro.length > 1 ? `<div class="meta" style="margin-top:6px">история:</div>` +
        d.macro.slice(1, 4).map(mn => `<div class="kv"><span>${mn.date} · ${fesc(mn.phase)} — ${fesc(mn.thesis.slice(0, 60))}</span><span class="rowbtn del" style="opacity:1" data-mcdel="${mn.id}">✕</span></div>`).join('') : ''}
    </div>
  </div>

  <div class="footer-hint">Портфель бивалютный: у актива валюта € или $ (клик по значку у суммы — сменить), итоги в обеих валютах по курсу EURUSD. Ввод понимает «100k», «1.2m». Платежи видны в радаре задач (±60 дней).</div>`;
  bindFin();
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
        <textarea id="monefyCsv" rows="6" style="width:100%;border:1px solid var(--line);border-radius:8px;padding:8px;font:12px var(--mono)" placeholder="Вставь содержимое CSV-экспорта Monefy (с заголовком). Разделитель ; или , — определю сам. Минус = расход."></textarea>
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

function renderReceivables(recs) {
  return `
  <div class="sec">Дебиторка · мне должны</div>
  <div class="card">
    ${recs.map(r => `
      <div class="task" style="${r.status === 'received' ? 'opacity:.5' : ''}">
        <span class="t ed" data-fe="receivables:${r.id}:name:text">${fesc(r.name)}</span>
        <span class="ed num" data-fe="receivables:${r.id}:amount:num">${fmt(r.amount)} ${fesc(r.currency)}</span>
        ${r.status === 'received'
          ? '<span class="pill ok">получено ✓</span>'
          : `<span class="ed meta ${r.overdue_days > 0 ? 'amber' : ''}" data-fe="receivables:${r.id}:expected_date:date">${r.expected_date ?? '+дата'}${r.overdue_days > 0 ? ` · просрочен ${r.overdue_days} дн ⚠` : ''}</span>
             <span class="pill btn ok" data-recok="${r.id}" title="получено — создам доход">✓ получено</span>`}
        <span class="rowbtn del" data-findel="receivables:${r.id}">✕</span>
      </div>`).join('') || '<div class="empty">никто не должен — красота</div>'}
    <div class="task finadd">
      <input id="recName" placeholder="кто и за что должен">
      <input id="recAmount" placeholder="сумма" style="width:90px">
      <input id="recDate" placeholder="ждём до…" style="width:105px">
      <span class="pill btn ok" id="recAdd">＋</span>
    </div>
  </div>`;
}

function inlineVal(el, type, onSave) {
  const input = document.createElement('input');
  input.className = 'inlineedit';
  input.style.maxWidth = type === 'text' ? '220px' : '120px';
  input.placeholder = el.textContent.trim();
  if (type === 'text') input.value = el.textContent.trim().replace(/^(усл: |купл\. |\+.*)/, '');
  el.replaceWith(input);
  input.focus(); if (type === 'text') input.select();
  let done = false;
  const save = async () => {
    if (done) return; done = true;
    const raw = input.value.trim();
    if (raw) {
      let v = raw;
      if (type === 'num') { v = parseNum(raw); if (v == null) { window.loadFin(); return; } }
      if (type === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(raw)) { window.loadFin(); return; }
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
  document.querySelectorAll('[data-fe]').forEach(el =>
    el.addEventListener('click', () => {
      const [ent, id, field, type] = el.dataset.fe.split(':');
      inlineVal(el, type, v => finApi.patch(ent, +id, { [field]: v }));
    }));
  document.querySelectorAll('[data-fcur]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.fcur.split(':');
      await finApi.patch('items', +id, { currency: cur === '€' ? '$' : '€' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-rate]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', v => finApi.rateSet(el.dataset.rate, v))));
  document.querySelectorAll('[data-fintab]').forEach(el =>
    el.addEventListener('click', () => { finTab = el.dataset.fintab; renderFin(); }));
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

  // расходы
  const shiftYm = (ym, d) => { const [y, m] = ym.split('-').map(Number); return new Date(Date.UTC(y, m - 1 + d, 1)).toISOString().slice(0, 7); };
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
  // дебиторка
  document.querySelectorAll('[data-recok]').forEach(el =>
    el.addEventListener('click', async () => { await finApi.received(+el.dataset.recok); window.loadFin(); }));
  $('recAdd')?.addEventListener('click', async () => {
    if (!$('recName').value.trim()) return;
    await finApi.add('receivables', { name: $('recName').value.trim(), amount: parseNum($('recAmount').value) ?? 0,
      expected_date: /^\d{4}-\d{2}-\d{2}$/.test($('recDate').value) ? $('recDate').value : null });
    window.loadFin();
  });
  // FIRE
  document.querySelectorAll('[data-fireset]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', async v => { await finApi.fire({ [el.dataset.fireset]: v }); })));
  // макро
  $('mcAdd')?.addEventListener('click', async () => {
    if (!$('mcThesis').value.trim()) return;
    await finApi.macroAdd({ phase: $('mcPhase').value, thesis: $('mcThesis').value.trim() });
    window.loadFin();
  });
  document.querySelectorAll('[data-mcdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить запись из истории тезисов?')) { await finApi.macroDel(+el.dataset.mcdel); window.loadFin(); }
    }));

  $('ratesRefresh')?.addEventListener('click', async () => {
    $('ratesRefresh').textContent = '…';
    const r = await finApi.ratesRefresh();
    if (r.error) alert(r.error);
    window.loadFin();
  });
  $('accAdd')?.addEventListener('click', async () => {
    if (!$('accName').value.trim()) return;
    await finApi.add('accounts', { name: $('accName').value.trim(), type: $('accType').value,
      currency: $('accCur').value || '€', balance: parseNum($('accBal').value) ?? 0 });
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

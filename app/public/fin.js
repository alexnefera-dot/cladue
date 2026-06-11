/* Финансы: курсы · портфель (блоки→разделы→активы, факт/целевой) · счета · шаги · обязательства */
let finData = null;
let finTab = 'fact';   // fact | target

const finApi = {
  list: () => fetch('/api/fin').then(r => r.json()),
  add: (ent, b) => fetch(`/api/fin/${ent}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  patch: (ent, id, b) => fetch(`/api/fin/${ent}/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  del: (ent, id) => fetch(`/api/fin/${ent}/${id}`, { method: 'DELETE' }),
  pay: id => fetch(`/api/fin/obligations/${id}/pay`, { method: 'POST' }),
  toTask: id => fetch(`/api/fin/steps/${id}/task`, { method: 'POST' }).then(r => r.json()),
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
  renderFin();
};

function portRows(it, depth) {
  const target = finTab === 'target';
  // редактируемы: активы и любые узлы без детей (новый пустой раздел можно оценить сразу)
  const editable = it.kind === 'asset' || !it.children.length;
  const rowCls = it.kind === 'block' ? 'pblock' : it.kind === 'section' ? 'psection' : '';
  let cells;
  if (target) {
    cells = `<td class="r num muted">${fmtE(it.value)}</td>
      <td class="r num ed acc" data-fe="items:${it.id}:target_value:num" title="клик — целевая сумма">${it.target != null ? fmtE(it.target) : '—'}</td>
      <td class="r">${it.target != null ? `<span class="pill ${it.value - it.target >= 0 ? 'ok' : 'p1'}">Δ ${fmt(it.value - it.target)}</span>` : ''}</td>`;
  } else {
    const g = it.invested != null && it.invested ? (it.investedCur - it.invested) / it.invested * 100 : null;
    cells = `<td class="r num muted ${editable ? 'ed' : ''}" ${editable ? `data-fe="items:${it.id}:buy_value:num" title="цена покупки (клик)"` : ''}>
        ${editable ? (it.buy_value != null ? fmt(it.buy_value) : '—') : (it.invested != null ? fmt(it.invested) : '')}</td>
      <td class="r num">${g != null ? `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>` : ''}</td>
      <td class="r num acc ${editable ? 'ed' : ''}" ${editable ? `data-fe="items:${it.id}:value:num" title="текущая стоимость (клик)"` : ''}>${fmtE(it.value)}</td>`;
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
      <div class="bignum">${fmtE(s.portfolioTotal)}</div>
      <div class="meta">${s.growth ? `прирост от покупки: ${s.growth.abs >= 0 ? '+' : ''}${fmt(s.growth.abs)} € (${s.growth.pct.toFixed(1)}%)` : 'задай цены покупки активам — посчитаю прирост'}</div></div>
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
  <div class="footer-hint">Валюта страницы — €. Суммы можно вводить как «100k» или «1.2m». Платежи отсюда видны в радаре задач (±60 дней). Курсы: stooq.com, наружу уходят только тикеры; можно ввести вручную кликом.</div>`;
  bindFin();
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

/* Финансы: счета · портфель · план шагов · обязательства */
let finData = null;

const finApi = {
  list: () => fetch('/api/fin').then(r => r.json()),
  add: (ent, b) => fetch(`/api/fin/${ent}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  patch: (ent, id, b) => fetch(`/api/fin/${ent}/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  del: (ent, id) => fetch(`/api/fin/${ent}/${id}`, { method: 'DELETE' }),
  pay: id => fetch(`/api/fin/obligations/${id}/pay`, { method: 'POST' }),
  toTask: id => fetch(`/api/fin/steps/${id}/task`, { method: 'POST' }).then(r => r.json()),
};

const fmt = n => n == null ? '—' : Math.round(n).toLocaleString('ru-RU');
const fesc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ACCT = { bank: 'банк', broker: 'брокер', cash: 'кэш', crypto: 'крипто', deposit: 'вклад', safe: 'ячейка' };
const STEPK = { buy: ['купить', 'ok'], sell: ['продать', 'p1'], transfer: ['перевод', 'p2'] };
const PERIOD = { monthly: 'мес', yearly: 'год', once: 'разово' };

window.loadFin = async function () {
  finData = await finApi.list();
  renderFin();
};

function renderFin() {
  const d = finData, s = d.summary;
  document.getElementById('screen-fin').innerHTML = `
  <div class="hint">Прототип: суммы лежат локально в data.db на твоём Маке. В нативной версии этот раздел будет приватной зоной с повторным паролем.</div>

  <div class="fingrid">
    <div class="card"><div class="meta">СЧЕТА ИТОГО (₽)</div>
      <div class="bignum">${fmt(s.accountsTotal)} ₽</div>
      <div class="meta">${d.accounts.length} счетов · валютные не суммируются</div></div>
    <div class="card"><div class="meta">ПОРТФЕЛЬ</div>
      <div class="bignum">${fmt(s.portfolioTotal)} ₽</div>
      <div class="meta">${s.fit != null ? `соответствие целевому: ${s.fit.toFixed(0)}%` : 'добавь классы'}</div>
      ${s.fit != null ? `<div class="bar"><i style="width:${s.fit}%"></i></div>` : ''}</div>
    <div class="card"><div class="meta">ОБЯЗАТЕЛЬСТВА / МЕС</div>
      <div class="bignum">${fmt(s.monthlyObligations)} ₽</div>
      <div class="meta">${s.upcoming.length ? `ближайшие 30 дней: ${s.upcoming.length} платежей` : 'на месяц вперёд тихо'}</div></div>
  </div>

  <div class="sec">Счета · клик по балансу — обновить</div>
  <div class="card">
    ${d.accounts.map(a => `
      <div class="task">
        <span class="pill">${ACCT[a.type] ?? a.type}</span>
        <span class="t">${fesc(a.name)}</span>
        ${a.stale_days > 21 ? `<span class="meta amber">⚠ ${a.stale_days} дн. не обновлялся</span>` : `<span class="meta">обн. ${a.balance_updated_at.slice(0, 10)}</span>`}
        <span class="balance num" data-balacc="${a.id}" title="клик — изменить">${fmt(a.balance)} ${fesc(a.currency)}</span>
        <span class="rowbtn del" data-findel="accounts:${a.id}" title="удалить">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <input id="accName" placeholder="новый счёт: название">
      <select id="accType">${Object.entries(ACCT).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
      <input id="accCur" value="₽" style="width:42px">
      <input id="accBal" placeholder="баланс" style="width:110px">
      <span class="pill btn ok" id="accAdd">＋</span>
    </div>
  </div>

  <div class="sec">Портфель: текущий → целевой · клики по числам — правка</div>
  <div class="card">
    <table class="fintable">
      <tr><th>Класс</th><th class="r">Стоимость</th><th class="r">Доля</th><th class="r">Цель %</th><th class="r">Откл.</th><th></th></tr>
      ${d.classes.map(c => `
        <tr>
          <td>${fesc(c.name)}</td>
          <td class="r num" data-clsval="${c.id}" title="клик — изменить">${fmt(c.value)}</td>
          <td class="r num">${c.share.toFixed(1)}%</td>
          <td class="r num" data-clstgt="${c.id}" title="клик — изменить">${c.target_pct}%</td>
          <td class="r num ${Math.abs(c.deviation) > 3 ? 'amber' : ''}">${c.deviation > 0 ? '+' : ''}${c.deviation.toFixed(1)}%</td>
          <td class="r"><span class="rowbtn del" data-findel="classes:${c.id}">✕</span></td>
        </tr>`).join('')}
    </table>
    <div class="task finadd">
      <input id="clsName" placeholder="новый класс: название">
      <input id="clsVal" placeholder="стоимость" style="width:110px">
      <input id="clsTgt" placeholder="цель %" style="width:70px">
      <span class="pill btn ok" id="clsAdd">＋</span>
    </div>
  </div>

  <div class="sec">План шагов · покупки / продажи</div>
  <div class="card">
    ${d.steps.map(st => {
      const [kl, kc] = STEPK[st.kind] ?? [st.kind, ''];
      const done = st.status === 'done';
      return `<div class="task ${done ? '' : ''}">
        <span class="cb ${done ? 'done' : ''}" data-stepdone="${st.id}"></span>
        <span class="pill ${kc}">${kl}</span>
        <span class="t ${done ? 'done' : ''}">${fesc(st.title)}</span>
        ${st.amount ? `<span class="meta num">${fmt(st.amount)}</span>` : ''}
        ${st.planned_date ? `<span class="meta">${st.planned_date}</span>` : ''}
        ${st.condition ? `<span class="meta">усл: ${fesc(st.condition)}</span>` : ''}
        ${!done ? `<span class="pill btn" data-steptask="${st.id}" title="создать задачу в списке">→ задача</span>` : ''}
        <span class="rowbtn del" data-findel="steps:${st.id}">✕</span>
      </div>`;
    }).join('') || '<div class="empty">шагов нет</div>'}
    <div class="task finadd">
      <select id="stKind"><option value="buy">купить</option><option value="sell">продать</option><option value="transfer">перевод</option></select>
      <input id="stTitle" placeholder="что и зачем">
      <input id="stAmount" placeholder="сумма" style="width:100px">
      <input id="stDate" placeholder="2026-08-31" style="width:105px">
      <input id="stCond" placeholder="условие (опц.)" style="width:140px">
      <span class="pill btn ok" id="stAdd">＋</span>
    </div>
  </div>

  <div class="sec">Обязательства и подписки · «✓» = оплачено, дата сдвинется на период</div>
  <div class="card">
    ${d.obligations.map(o => `
      <div class="task">
        <span class="pill ${o.kind === 'subscription' ? 'p2' : 'p1'}">${o.kind === 'subscription' ? 'подписка' : 'пассив'}</span>
        <span class="t">${fesc(o.name)}</span>
        <span class="meta num">${fmt(o.amount)} ${fesc(o.currency)} / ${PERIOD[o.period]}</span>
        ${o.next_date
          ? `<span class="meta ${o.days_left <= o.remind_days ? 'amber' : ''}">${o.next_date}${o.days_left != null ? ` (через ${o.days_left} дн.)` : ''}</span>
             <span class="pill btn ok" data-oblpay="${o.id}" title="оплачено — сдвинуть дату">✓</span>`
          : '<span class="meta">закрыто</span>'}
        <span class="rowbtn del" data-findel="obligations:${o.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <select id="obKind"><option value="liability">пассив</option><option value="subscription">подписка</option></select>
      <input id="obName" placeholder="название (кредит, аренда, iCloud…)">
      <input id="obAmount" placeholder="сумма" style="width:90px">
      <select id="obPeriod"><option value="monthly">мес</option><option value="yearly">год</option><option value="once">разово</option></select>
      <input id="obDate" placeholder="след. дата" style="width:105px">
      <span class="pill btn ok" id="obAdd">＋</span>
    </div>
  </div>
  <div class="footer-hint">Эти платежи автоматически видны в радаре задач: открой запись со сроком — блок «◈ Платежи рядом по времени».</div>`;
  bindFin();
}

function inlineNum(el, onSave) {
  const input = document.createElement('input');
  input.className = 'inlineedit';
  input.style.maxWidth = '120px';
  input.value = '';
  input.placeholder = el.textContent.trim();
  el.replaceWith(input);
  input.focus();
  let done = false;
  const save = async () => {
    if (done) return; done = true;
    const v = parseFloat(input.value.replace(/\s/g, '').replace(',', '.'));
    if (!isNaN(v)) await onSave(v);
    window.loadFin();
  };
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') save();
    if (ev.key === 'Escape') { done = true; window.loadFin(); }
  });
  input.addEventListener('blur', save);
}

function bindFin() {
  const $ = id => document.getElementById(id);
  document.querySelectorAll('[data-balacc]').forEach(el =>
    el.addEventListener('click', () => inlineNum(el, v => finApi.patch('accounts', +el.dataset.balacc, { balance: v }))));
  document.querySelectorAll('[data-clsval]').forEach(el =>
    el.addEventListener('click', () => inlineNum(el, v => finApi.patch('classes', +el.dataset.clsval, { value: v }))));
  document.querySelectorAll('[data-clstgt]').forEach(el =>
    el.addEventListener('click', () => inlineNum(el, v => finApi.patch('classes', +el.dataset.clstgt, { target_pct: v }))));
  document.querySelectorAll('[data-findel]').forEach(el =>
    el.addEventListener('click', async () => {
      const [ent, id] = el.dataset.findel.split(':');
      if (confirm('Удалить запись?')) { await finApi.del(ent, +id); window.loadFin(); }
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

  $('accAdd')?.addEventListener('click', async () => {
    if (!$('accName').value.trim()) return;
    await finApi.add('accounts', { name: $('accName').value.trim(), type: $('accType').value,
      currency: $('accCur').value || '₽', balance: parseFloat($('accBal').value.replace(/\s/g, '')) || 0 });
    window.loadFin();
  });
  $('clsAdd')?.addEventListener('click', async () => {
    if (!$('clsName').value.trim()) return;
    await finApi.add('classes', { name: $('clsName').value.trim(),
      value: parseFloat($('clsVal').value.replace(/\s/g, '')) || 0, target_pct: parseFloat($('clsTgt').value) || 0 });
    window.loadFin();
  });
  $('stAdd')?.addEventListener('click', async () => {
    if (!$('stTitle').value.trim()) return;
    await finApi.add('steps', { kind: $('stKind').value, title: $('stTitle').value.trim(),
      amount: parseFloat($('stAmount').value.replace(/\s/g, '')) || null,
      planned_date: /^\d{4}-\d{2}-\d{2}$/.test($('stDate').value) ? $('stDate').value : null,
      condition: $('stCond').value.trim() });
    window.loadFin();
  });
  $('obAdd')?.addEventListener('click', async () => {
    if (!$('obName').value.trim()) return;
    await finApi.add('obligations', { kind: $('obKind').value, name: $('obName').value.trim(),
      amount: parseFloat($('obAmount').value.replace(/\s/g, '')) || 0, period: $('obPeriod').value,
      next_date: /^\d{4}-\d{2}-\d{2}$/.test($('obDate').value) ? $('obDate').value : null });
    window.loadFin();
  });
}

/* «Сегодня» — главный дашборд: просрочка · задачи дня · неделя · долги · прогресс */
let tdData = null;

const tdApi = {
  get: () => fetch('/api/today').then(r => r.json()),
  toggle: id => fetch(`/api/nodes/${id}/toggle`, { method: 'POST' }),
  pay: id => fetch(`/api/fin/obligations/${id}/pay`, { method: 'POST' }),
  add: b => fetch('/api/nodes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
};

const tesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tfmt = n => n == null ? '' : Math.round(n).toLocaleString('ru-RU');
const WD = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const MON = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

window.loadToday = async function () {
  tdData = await tdApi.get();
  renderToday();
};

function taskLine(t) {
  return `<div class="task">
    <span class="cb ${t.kind === 'decision' ? 'dec' : ''}" data-tdtoggle="${t.id}"></span>
    ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
    ${t.kind === 'decision' ? '<span class="pill dec">решение</span>' : ''}
    <span class="t" data-tdopen="${t.id}" style="cursor:pointer" title="открыть карточку">${tesc(t.title)}</span>
    <span class="meta">${t.due_date ?? ''}</span>
  </div>`;
}

function renderToday() {
  const d = tdData;
  const dt = new Date(d.date + 'T00:00:00');
  const pct = d.progress.total ? Math.round(d.progress.typed / d.progress.total * 100) : 0;

  document.getElementById('screen-today').innerHTML = `
  <h2 style="margin-bottom:2px">Сегодня</h2>
  <div class="muted" style="margin-bottom:14px">${WD[dt.getDay()]}, ${dt.getDate()} ${MON[dt.getMonth()]} ·
    просрочено: ${d.overdue.length} · на сегодня: ${d.dueToday.length} · сделано за неделю: ${d.doneWeek} 👏</div>

  <div class="addbar" style="margin:0 0 14px">
    <input id="tdQuick" placeholder="＋ Быстрый ввод в Инбокс (Enter) — мысль, задача, что угодно; разберёшь потом">
  </div>

  <div class="fingrid">
    <div class="card"><div class="meta">РАЗБОР СПИСКА</div>
      <div class="bignum">${pct}%</div>
      <div class="bar"><i style="width:${pct}%"></i></div>
      <div class="meta">${d.progress.typed} из ${d.progress.total} · в инбоксе: ${d.inbox}</div></div>
    <div class="card"><div class="meta">ПОРТФЕЛЬ</div>
      <div class="bignum">${d.portfolioDelta ? (d.portfolioDelta.abs >= 0 ? '+' : '') + tfmt(d.portfolioDelta.abs) + ' €' : '—'}</div>
      <div class="meta">${d.portfolioDelta ? 'с ' + d.portfolioDelta.since : 'движение появится со второго дня'}</div></div>
    <div class="card"><div class="meta">FIRE</div>
      <div class="bignum">${d.fire ? d.fire.pct.toFixed(1) + '%' : '—'}</div>
      ${d.fire ? `<div class="bar"><i style="width:${d.fire.pct}%"></i></div>` : '<div class="meta">цель не задана (Финансы → FIRE)</div>'}</div>
  </div>

  ${d.overdue.length ? `<div class="sec" style="color:var(--red)">⚠ Просрочено</div>
  <div class="card">${d.overdue.map(taskLine).join('')}</div>` : ''}

  <div class="sec">Задачи на сегодня</div>
  <div class="card">${d.dueToday.map(taskLine).join('') ||
    '<div class="empty">на сегодня сроков нет — загляни в «Сроки» в Задачах или поставь дедлайны</div>'}</div>

  <div class="sec">Ближайшие 7 дней</div>
  <div class="card">
    ${d.week.map(it => `
      <div class="task">
        <span class="meta num" style="min-width:46px">${it.date.slice(5)}</span>
        <span class="pill ${it.type === 'money' ? 'p1' : it.type === 'task' ? 'ok' : it.type === 'step' ? 'p2' : ''}">${
          { task: 'задача', money: it.okind === 'subscription' ? 'подписка' : 'платёж', step: 'шаг', event: 'событие' }[it.type]}</span>
        <span class="t" ${it.type === 'task' ? `data-tdopen="${it.id}" style="cursor:pointer"` : ''}>${tesc(it.title)}</span>
        ${it.amount ? `<span class="meta num">${tfmt(it.amount)} ${tesc(it.currency ?? '€')}</span>` : ''}
        ${it.type === 'money' ? `<span class="pill btn ok" data-tdpay="${it.id}" title="оплачено">✓</span>` : ''}
      </div>`).join('') || '<div class="empty">неделя свободна</div>'}
  </div>

  ${d.debtsOverdue.length ? `<div class="sec" style="color:var(--amber)">Долги · просрочено</div>
  <div class="card">${d.debtsOverdue.map(x => `
    <div class="task">
      <span class="pill ${x.direction === 'i_owe' ? 'p0' : 'ok'}">${x.direction === 'i_owe' ? 'я должен' : 'мне должны'}</span>
      <span class="t">${tesc(x.name)}</span>
      <span class="meta num">${tfmt(x.amount)} ${tesc(x.currency)}</span>
      <span class="meta amber">${x.overdue_days} дн ⚠</span>
    </div>`).join('')}</div>` : ''}

  <div class="footer-hint">Отметка задачи здесь синхронизируется со списком, шагами портфеля и календарём. Платёж «✓» сдвигается на период.</div>`;

  bindToday();
}

function bindToday() {
  document.querySelectorAll('#screen-today [data-tdtoggle]').forEach(el =>
    el.addEventListener('click', async e => { e.stopPropagation(); await tdApi.toggle(+el.dataset.tdtoggle); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdpay]').forEach(el =>
    el.addEventListener('click', async e => { e.stopPropagation(); await tdApi.pay(+el.dataset.tdpay); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdopen]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.tdopen)));
  document.getElementById('tdQuick')?.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !e.target.value.trim()) return;
    await tdApi.add({ title: e.target.value.trim(), parent_id: tdData.inboxId });
    e.target.value = '';
    window.loadToday();
  });
}

// «Сегодня» — стартовый экран
showScreen('today');

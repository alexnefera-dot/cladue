/* Календарь: единая лента — задачи · платежи · шаги · события */
const calIso = (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);   // локальная дата, не UTC
let calMonth = calIso(new Date()).slice(0, 7);
let calData = null;

const calApi = {
  month: ym => fetch('/api/calendar?month=' + ym).then(r => r.json()),
  addEvent: b => fetch('/api/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  delEvent: id => fetch('/api/events/' + id, { method: 'DELETE' }),
  toggleNode: id => fetch(`/api/nodes/${id}/toggle`, { method: 'POST' }),
  payObl: id => fetch(`/api/fin/obligations/${id}/pay`, { method: 'POST' }),
};

const cesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const cfmt = n => n == null ? '' : Math.round(n).toLocaleString('ru-RU');
const MONTHS_RU = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
const TYPE_CLS = { task: 'ev-task', money: 'ev-money', step: 'ev-step', event: 'ev-cal', practice: 'ev-psy' };

window.loadCal = async function () {
  calData = await calApi.month(calMonth);
  renderCal();
  window.pbSyncAllReminders?.();   // события могли измениться — пересобрать пуши
};

function shiftMonth(ym, d) {
  const [y, m] = ym.split('-').map(Number);
  const nd = new Date(Date.UTC(y, m - 1 + d, 1));
  return nd.toISOString().slice(0, 7);
}

function renderCal() {
  const [y, m] = calMonth.split('-').map(Number);
  const daysIn = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const firstDow = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7; // пн=0
  const today = calIso(new Date());
  const byDate = {};
  for (const it of calData.items) (byDate[it.date] ??= []).push(it);

  let cells = '';
  for (let i = 0; i < firstDow; i++) cells += '<div class="d dim"></div>';
  for (let day = 1; day <= daysIn; day++) {
    const date = `${calMonth}-${String(day).padStart(2, '0')}`;
    const items = byDate[date] ?? [];
    cells += `<div class="d ${date === today ? 'today' : ''}" data-date="${date}">
      <div class="n">${day}</div>
      ${items.slice(0, 4).map(it => {
        // перетаскивается то, у чего есть одна своя дата; повторы/ДР/практики — нет
        const draggable = it.type === 'task' || it.type === 'step'
          || (it.type === 'money') || (it.type === 'event' && it.recur === 'none' && !it.bday);
        return `
        <div class="ev ${TYPE_CLS[it.type]} ${it.done ? 'evdone' : ''}" ${it.type === 'task' ? `data-nid="${it.id}"` : ''}
          ${draggable ? `draggable="true" data-calmv="${it.type}:${it.id}"` : ''}
          title="${cesc(it.title)}${draggable ? ' · тащи на другой день — срок изменится везде' : ''}">
          ${it.time ? it.time + ' ' : ''}${cesc(it.title)}${it.amount ? ' · ' + cfmt(it.amount) : ''}</div>`;
      }).join('')}
      ${items.length > 4 ? `<div class="ev">+${items.length - 4} ещё…</div>` : ''}
    </div>`;
  }

  // повестка: ближайшие 2 недели от сегодня (внутри месяца)
  const horizon = calData.items.filter(it => it.date >= today).slice(0, 25);

  document.getElementById('screen-cal').innerHTML = `
  <div class="calhead">
    <span class="pill btn" id="calPrev">‹</span>
    <b style="min-width:150px;text-align:center">${MONTHS_RU[m - 1]} ${y}</b>
    <span class="pill btn" id="calNext">›</span>
    <span class="pill btn" id="calToday">сегодня</span>
    <span class="meta">лента: дедлайны задач · платежи · шаги портфеля · события</span>
  </div>
  <div class="cal">
    ${['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС'].map(d => `<div class="h">${d}</div>`).join('')}
    ${cells}
  </div>

  <div class="sec">＋ Событие (ДР, встреча, напоминание)</div>
  <div class="card"><div class="task finadd">
    <input id="evTitle" placeholder="название (🎂 ДР мамы, созвон…)">
    <input id="evDate" placeholder="2026-06-19" style="width:110px">
    <input id="evTime" placeholder="чч:мм" style="width:70px">
    <select id="evRecur"><option value="none">однократно</option><option value="weekly">каждую неделю</option><option value="monthly">каждый месяц</option><option value="yearly">каждый год</option></select>
    <span class="pill btn ok" id="evAdd">＋</span>
  </div></div>

  <div class="sec">Повестка · ближайшее</div>
  <div class="card">
    ${horizon.map(it => `
      <div class="task">
        <span class="meta num" style="min-width:78px">${it.date.slice(5)}${it.time ? ' ' + it.time : ''}</span>
        ${it.type === 'task' ? `<span class="cb ${it.done ? 'done' : ''}" data-caltoggle="${it.id}"></span>` : ''}
        <span class="pill ${it.type === 'money' ? 'p1' : it.type === 'task' ? 'ok' : it.type === 'step' ? 'p2' : ''}">${
          { task: it.kind === 'decision' ? 'решение' : 'задача', money: it.okind === 'subscription' ? 'подписка' : 'платёж', step: 'шаг', event: it.recur === 'yearly' ? '🎂/год' : 'событие', practice: '◎ практика' }[it.type]}</span>
        <span class="t ${it.done ? 'done' : ''}" ${it.type === 'task' ? `data-nid="${it.id}" style="cursor:pointer" title="открыть карточку"` : ''}>${cesc(it.title)}</span>
        ${it.amount ? `<span class="meta num">${cfmt(it.amount)} ${cesc(it.currency ?? '€')}</span>` : ''}
        ${it.type === 'money' ? `<span class="pill btn ok" data-calpay="${it.id}" title="оплачено">✓</span>` : ''}
        ${it.type === 'event' && !it.bday ? `<span class="rowbtn del" data-evdel="${it.id}">✕</span>` : ''}
      </div>`).join('') || '<div class="empty">впереди пусто — добавь событие или поставь сроки задачам</div>'}
  </div>
  <div class="footer-hint">Клик по задаче — её карточка в списке. «✓» у задачи в повестке — выполнено (отметка уйдёт в список и цель). Платёж «✓» — сдвинуть на период.</div>`;
  bindCal();
}

function bindCal() {
  const $ = id => document.getElementById(id);
  // DnD: перетащил на день — дата меняется в первоисточнике (задача/шаг/платёж/событие)
  let calDrag = null;
  document.querySelectorAll('#screen-cal [data-calmv]').forEach(el => {
    el.addEventListener('dragstart', e => { calDrag = el.dataset.calmv; e.stopPropagation(); });
  });
  document.querySelectorAll('#screen-cal .cal .d[data-date]').forEach(cell => {
    cell.addEventListener('dragover', e => { if (calDrag) { e.preventDefault(); cell.classList.add('dropinto'); } });
    cell.addEventListener('dragleave', () => cell.classList.remove('dropinto'));
    cell.addEventListener('drop', async e => {
      e.preventDefault();
      cell.classList.remove('dropinto');
      if (!calDrag) return;
      const [type, id] = calDrag.split(':');
      calDrag = null;
      const date = cell.dataset.date;
      const req = {
        task: [`/api/nodes/${id}`, { due_date: date }, 'PATCH'],
        event: [`/api/events/${id}`, { date }, 'PATCH'],
        step: [`/api/fin/steps/${id}`, { planned_date: date }, 'PATCH'],
        money: [`/api/fin/obligations/${id}`, { next_date: date }, 'PATCH'],
      }[type];
      const r = await fetch(req[0], { method: req[2], headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req[1]) }).then(x => x.json()).catch(() => ({}));
      if (r?.error) alert(r.error);
      window.loadCal();
    });
  });
  $('calPrev').addEventListener('click', () => { calMonth = shiftMonth(calMonth, -1); window.loadCal(); });
  $('calNext').addEventListener('click', () => { calMonth = shiftMonth(calMonth, 1); window.loadCal(); });
  $('calToday').addEventListener('click', () => { calMonth = calIso(new Date()).slice(0, 7); window.loadCal(); });
  $('evAdd').addEventListener('click', async () => {
    const title = $('evTitle').value.trim(), date = $('evDate').value.trim();
    if (!title || !/^\d{4}-\d{2}-\d{2}$/.test(date)) { alert('Нужны название и дата в формате 2026-06-19'); return; }
    const r = await calApi.addEvent({ title, date, time: $('evTime').value.trim() || null, recur: $('evRecur').value });
    if (r.error) alert(r.error);
    window.loadCal();
  });
  document.querySelectorAll('#screen-cal [data-caltoggle]').forEach(el =>
    el.addEventListener('click', async e => { e.stopPropagation(); await calApi.toggleNode(+el.dataset.caltoggle); window.loadCal(); }));
  document.querySelectorAll('#screen-cal [data-calpay]').forEach(el =>
    el.addEventListener('click', async e => { e.stopPropagation(); await calApi.payObl(+el.dataset.calpay); window.loadCal(); }));
  document.querySelectorAll('#screen-cal [data-evdel]').forEach(el =>
    el.addEventListener('click', async e => {
      e.stopPropagation();
      if (confirm('Удалить событие?')) { await calApi.delEvent(+el.dataset.evdel); window.loadCal(); }
    }));
  document.querySelectorAll('#screen-cal [data-nid]').forEach(el =>
    el.addEventListener('click', e => { e.stopPropagation(); window.openNode(+el.dataset.nid); }));
  document.querySelectorAll('#screen-cal .d[data-date]').forEach(el =>
    el.addEventListener('dblclick', () => {
      $('evDate').value = el.dataset.date;
      $('evTitle').focus();
    }));
}

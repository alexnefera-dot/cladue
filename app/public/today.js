/* «Сегодня» — по макету: месяц активности · рутины · задачи дня · события · люди · зоны · движение */
let tdData = null;

const tdApi = {
  get: () => fetch('/api/today').then(r => r.json()),
  toggle: id => fetch(`/api/nodes/${id}/toggle`, { method: 'POST' }),
  routineCheck: id => fetch(`/api/routines/${id}/check`, { method: 'POST' }),
  contacted: id => fetch(`/api/people/${id}/contacted`, { method: 'POST' }),
  add: b => fetch('/api/nodes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  setSetting: (key, value) => fetch('/api/setting', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key, value }) }),
  setCheckin: (mood, note) => fetch('/api/track/checkin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mood, note }) }),
};

const tesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
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
    <span class="t" data-tdopen="${t.id}" style="cursor:pointer">${tesc(t.title)}</span>
    ${t.repeat ? '<span class="meta">🔁</span>' : ''}
    <span class="meta">${t.due_date ?? ''}</span>
  </div>`;
}

// pre-flight для P0/P1 (данные приоритета — в today payload)
window.preflightTodayOk = async function (id) {
  const all = [...(tdData?.overdue ?? []), ...(tdData?.dueToday ?? [])];
  const t = all.find(x => x.id === id);
  if (!t || t.kind !== 'task' || !['P0', 'P1'].includes(t.priority)) return true;
  const s = await fetch('/api/suggest/' + id).then(r => r.json()).catch(() => null);
  if (!s) return true;
  const lines = [
    ...(s.blockers ?? []).map(b => `⛔ ${b.title}`),
    ...(s.context?.decisions ?? []).map(d => `◆ ${d.title}`),
    ...(s.context?.payments ?? []).map(o => `◈ ${o.name} (${o.next_date})`),
  ];
  return !lines.length || confirm(`🛫 Pre-flight «${t.title}»:\n\n${lines.join('\n')}\n\nВсё учтено — закрываем?`);
};

function renderToday() {
  const d = tdData;
  const dt = new Date(d.date + 'T00:00:00');
  const pct = d.progress.total ? Math.round(d.progress.typed / d.progress.total * 100) : 0;
  const rDone = d.routines.filter(r => r.done).length;

  document.getElementById('screen-today').innerHTML = `
  <h2 style="margin-bottom:2px">Сегодня</h2>
  <div class="muted" style="margin-bottom:14px">${WD[dt.getDay()]}, ${dt.getDate()} ${MON[dt.getMonth()]} ·
    просрочено: ${d.overdue.length} · сделано за неделю: ${d.movement.total} 👏</div>

  <div class="addbar" style="margin:0 0 6px">
    <input id="tdQuick" placeholder="＋ Быстрый ввод в Инбокс (Enter) — мысль, задача, что угодно; разберёшь потом">
    <span class="pill btn" id="tdRoll" title="рулетка спонтанности: случайная идея из твоих же списков">🎲</span>
  </div>
  <div id="tdRollBox" style="margin:0 0 14px"></div>

  <div class="fingrid" style="grid-template-columns:repeat(4,1fr)">
    <div class="card"><div class="meta">МЕСЯЦ АКТИВНОСТИ</div>
      <div class="bignum" style="font-size:16px"><span class="ed" id="tdActivity" title="клик — задать тему месяца">${d.activityMonth ? tesc(d.activityMonth) : '＋ задать тему'}</span></div>
      <div class="meta">разбор: ${pct}% · инбокс: ${d.inbox}</div></div>
    <div class="card"><div class="meta">НЕДЕЛЬНЫЕ ЦЕЛИ</div>
      <div class="bignum">${d.weekGoals.done} / ${d.weekGoals.total}</div>
      <div class="bar"><i style="width:${d.weekGoals.total ? d.weekGoals.done / d.weekGoals.total * 100 : 0}%"></i></div>
      <div class="meta">задачи со сроком на этой неделе</div></div>
    <div class="card"><div class="meta">ЧЕК-ИН ДНЯ</div>
      ${d.checkin
        ? `<div class="bignum">${['', '😞', '😐', '🙂'][d.checkin.mood]}</div>
           <div class="meta">${tesc(d.checkin.note) || 'отмечено'} · <span class="ed" id="tdCheckinRedo">изменить</span></div>`
        : `<div class="btnrow" style="margin:6px 0">
             <span class="pill btn" data-tdmood="1" style="font-size:16px">😞</span>
             <span class="pill btn" data-tdmood="2" style="font-size:16px">😐</span>
             <span class="pill btn" data-tdmood="3" style="font-size:16px">🙂</span></div>
           <div class="meta">какой день? 10 секунд · 📊 Трекинг</div>`}</div>
    <div class="card"><div class="meta">РУТИНЫ · ${rDone}/${d.routines.length} · по времени</div>
      ${d.routines.slice(0, 5).map(r => `
        <div class="task" style="padding:4px 0">
          <span class="cb ${r.done ? 'done' : ''}" data-tdroutine="${r.id}"></span>
          ${r.time ? `<span class="meta num ${r.due ? 'amber' : ''}">${r.time}</span>` : ''}
          <span class="t ${r.done ? 'done' : ''}">${tesc(r.name)}</span>
          ${r.due ? '<span class="pill p1">пора!</span>' : ''}
          ${r.streak ? `<span class="meta">🔥 ${r.streak}</span>` : ''}
        </div>`).join('') || '<div class="empty">добавь рутины в разделе ↻</div>'}
      ${d.routines.length > 5 ? `<div class="meta" style="cursor:pointer" data-tdgoto="routines">все ${d.routines.length} →</div>` : ''}</div>
  </div>

  ${d.overdue.length ? `<div class="sec" style="color:var(--red)">⚠ Просрочено</div>
  <div class="card">${d.overdue.map(taskLine).join('')}</div>` : ''}

  <div class="sec">Задачи на сегодня</div>
  <div class="card">${d.dueToday.map(taskLine).join('') ||
    '<div class="empty">сроков на сегодня нет — поставь дедлайны в Задачах</div>'}</div>

  <div class="fingrid" style="grid-template-columns:1fr 1fr">
    <div>
      <div class="sec" style="margin-top:0">События · сегодня и завтра</div>
      <div class="card">
        ${d.events.map(e => `<div class="task">
          <span class="meta num">${e.date === d.date ? 'сегодня' : 'завтра'}${e.time ? ' ' + e.time : ''}</span>
          <span class="t">${tesc(e.title)}</span>
          ${typeof e.id === 'number' ? `<span class="pill btn ok" data-tdevent="${e.id}" data-recur="${e.recur ?? 'none'}" title="прошёл — закрыть">✓</span>` : ''}</div>`).join('') || '<div class="empty">тихо</div>'}
      </div>
      <div class="sec">Люди</div>
      <div class="card">
        ${d.people.birthdays.map(p => `<div class="task">
          <span class="t">🎂 ${tesc(p.name)}</span>
          <span class="meta ${p.days_to_birthday <= 7 ? 'amber' : ''}">${p.days_to_birthday === 0 ? 'СЕГОДНЯ!' : 'через ' + p.days_to_birthday + ' дн'}</span></div>`).join('')}
        ${d.people.overdueContacts.map(p => `<div class="task">
          <span class="t amber">☎ ${tesc(p.name)} — пора связаться</span>
          <span class="meta">молчим ${p.since_contact ?? '∞'} дн</span>
          <span class="pill btn ok" data-tdcontact="${p.id}">связались ✓</span></div>`).join('')}
        ${!d.people.birthdays.length && !d.people.overdueContacts.length
          ? '<div class="empty">ДР и созвоны под контролем · добавить людей — раздел ☻</div>' : ''}
      </div>
    </div>
    <div>
      <div class="sec" style="margin-top:0">Приватные зоны</div>
      <div class="lockcard" data-tdgoto="fin" style="cursor:pointer">🔒 <div><b>Финансы:</b> платежей на неделе: ${d.zones.paymentsWeek}${d.zones.debtsOverdue ? ` · просроченных долгов: ${d.zones.debtsOverdue}` : ''}<br>
        <span class="meta">суммы скрыты · клик — открыть раздел (в нативной версии — по паролю)</span></div></div>
      <div class="lockcard" data-tdgoto="psy" style="margin-top:10px;cursor:pointer">🔒 <div><b>Психология:</b> практик сегодня: ${d.zones.practicesToday ?? 0}<br>
        <span class="meta">детали скрыты · клик — открыть раздел</span></div></div>
      <div class="sec">▲ Движение недели</div>
      <div class="card">
        ${d.movement.top.map(([cat, n]) => `<div class="task">
          <span class="pill ok">⚑ ${tesc(cat)}</span>
          <span class="t">${n} ${n === 1 ? 'шаг' : 'шага(ов)'} за неделю</span></div>`).join('')}
        <div class="task"><span class="pill ok">👏</span>
          <span class="t"><b>${d.movement.total ? d.movement.total + ' действий за неделю — ты двигаешься' : 'неделя только начинается'}</b></span></div>
      </div>
    </div>
  </div>
  <div class="footer-hint">Отметки синхронизируются со списком, шагами и календарём. Рутины: пропуск не висит долгом — день закрылся и всё.</div>`;

  bindToday();
}

function bindToday() {
  document.querySelectorAll('#screen-today [data-tdtoggle]').forEach(el =>
    el.addEventListener('click', async e => {
      e.stopPropagation();
      if (window.preflightTodayOk && !await window.preflightTodayOk(+el.dataset.tdtoggle)) return;
      await tdApi.toggle(+el.dataset.tdtoggle);
      window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-tdroutine]').forEach(el =>
    el.addEventListener('click', async () => { await tdApi.routineCheck(+el.dataset.tdroutine); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdcontact]').forEach(el =>
    el.addEventListener('click', async () => { await tdApi.contacted(+el.dataset.tdcontact); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdevent]').forEach(el =>
    el.addEventListener('click', async () => {
      const recur = el.dataset.recur;   // повторяющееся удалит все будущие — спросим
      if (recur && recur !== 'none' && !confirm('Это повторяющееся событие. Удалить его совсем?')) return;
      await fetch('/api/events/' + el.dataset.tdevent, { method: 'DELETE' });
      window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-tdopen]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.tdopen)));
  document.querySelectorAll('#screen-today [data-tdgoto]').forEach(el =>
    el.addEventListener('click', () => showScreen(el.dataset.tdgoto)));
  document.querySelectorAll('#screen-today [data-tdmood]').forEach(el =>
    el.addEventListener('click', async () => {
      const note = prompt('Заметка к дню (опционально):') ?? '';
      await tdApi.setCheckin(+el.dataset.tdmood, note);
      window.loadToday();
    }));
  document.getElementById('tdCheckinRedo')?.addEventListener('click', async () => {
    const mood = prompt('День: 1 — плохой, 2 — нормальный, 3 — хороший');
    if (!['1', '2', '3'].includes(mood?.trim())) return;
    await tdApi.setCheckin(+mood, prompt('Заметка (опционально):') ?? '');
    window.loadToday();
  });
  document.getElementById('tdActivity')?.addEventListener('click', async () => {
    const v = prompt('Тема месяца (например: 🎾 Июнь — падл):', tdData.activityMonth ?? '');
    if (v != null) { await tdApi.setSetting('activity_month', v.trim()); window.loadToday(); }
  });
  document.getElementById('tdRoll')?.addEventListener('click', rollIdea);
  document.getElementById('tdQuick')?.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !e.target.value.trim()) return;
    await tdApi.add({ title: e.target.value.trim(), parent_id: tdData.inboxId });
    e.target.value = '';
    window.loadToday();
  });
}

// ===== Рулетка спонтанности: случайная идея из своих списков против шаблонных выходных =====
async function rollIdea() {
  const box = document.getElementById('tdRollBox');
  const { idea } = await fetch('/api/roulette').then(r => r.json());
  if (!idea) {
    box.innerHTML = `<div class="suggest">🎲 Живых идей нет — кидай хотелки в <b>⚡ Энергия жизни → Банк впечатлений</b>
      (тип «идея»), и рулетке будет что доставать.</div>`;
    return;
  }
  box.innerHTML = `<div class="suggest">🎲 А как насчёт: <b>${tesc(idea.title)}</b>
    <span class="meta">${tesc(idea.path)}${idea.days ? ` · лежит ${idea.days} дн` : ' · свежая'}</span>
    <span class="btnrow" style="display:inline-flex;margin-left:8px">
      <span class="pill btn ok" id="tdRollTake">беру на выходные</span>
      <span class="pill btn" id="tdRollAgain">ещё 🎲</span>
      <span class="pill btn" id="tdRollClose">✕</span>
    </span></div>`;
  document.getElementById('tdRollAgain').addEventListener('click', rollIdea);
  document.getElementById('tdRollClose').addEventListener('click', () => { box.innerHTML = ''; });
  document.getElementById('tdRollTake').addEventListener('click', async () => {
    const now = new Date();
    const sat = (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)(new Date(Date.now() + ((6 - now.getDay() + 7) % 7) * 864e5));
    await fetch('/api/nodes/' + idea.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'task', due_date: sat }) });
    box.innerHTML = `<div class="suggest">🎉 «${tesc(idea.title)}» запланировано на субботу ${sat.slice(8)}.${sat.slice(5, 7)} — увидишь в задачах и календаре.</div>`;
    window.loadToday && setTimeout(() => { document.getElementById('tdRollBox') && window.loadToday(); }, 1600);
  });
}

// «Сегодня» — стартовый экран
showScreen('today');

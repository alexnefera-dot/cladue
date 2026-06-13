/* Рутины и Люди — отдельные экраны */
const lfApi = {
  routines: () => fetch('/api/routines').then(r => r.json()),
  rAdd: b => fetch('/api/routines', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  rPatch: (id, b) => fetch('/api/routines/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  rDel: id => fetch('/api/routines/' + id, { method: 'DELETE' }),
  rCheck: id => fetch(`/api/routines/${id}/check`, { method: 'POST' }),
  people: () => fetch('/api/people').then(r => r.json()),
  pAdd: b => fetch('/api/people', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  pPatch: (id, b) => fetch('/api/people/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  pDel: id => fetch('/api/people/' + id, { method: 'DELETE' }),
  pContact: id => fetch(`/api/people/${id}/contacted`, { method: 'POST' }),
};
const lesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SLOTS = ['утро', 'день', 'вечер'];

// ===== Рутины =====
window.loadRoutines = async function () {
  const rows = await lfApi.routines();
  const planned = await fetch('/api/routines/planned').then(r => r.json()).catch(() => []);
  document.getElementById('screen-routines').innerHTML = `
  <h2 style="margin-bottom:2px">Рутины</h2>
  <div class="muted" style="margin-bottom:14px">микро-действия отдельно от задач · пропуск не висит долгом · сегодня: ${rows.filter(r => r.done).length}/${rows.length}</div>
  <div class="fingrid">
    ${SLOTS.map(slot => `
      <div class="card"><div class="meta">${slot.toUpperCase()}</div>
        ${rows.filter(r => r.slot === slot).map(r => `
          <div class="task">
            <span class="cb ${r.done ? 'done' : ''}" data-lfcheck="${r.id}"></span>
            <span class="t ${r.done ? 'done' : ''} ed" data-lfren="${r.id}" title="клик — переименовать">${lesc(r.name)}</span>
            <span class="ed meta num" data-lftime="${r.id}" title="фикс. время — напоминание (клик)">${r.time ? '⏰ ' + r.time : '+время'}</span>
            ${r.streak ? `<span class="meta">🔥 ${r.streak}</span>` : ''}
            <span class="rowbtn del" data-lfdel="${r.id}">✕</span>
          </div>`).join('') || '<div class="empty">пусто</div>'}
      </div>`).join('')}
  </div>
  <div class="card"><div class="task finadd">
    <input id="rtName" placeholder="новая рутина: таблетка, миноксидил, отжимания 3×15…">
    <select id="rtSlot">${SLOTS.map(s => `<option>${s}</option>`).join('')}</select>
    <input id="rtTime" placeholder="чч:мм (опц.)" style="width:95px">
    <span class="pill btn ok" id="rtAdd">＋</span>
  </div></div>
  <div class="card"><div class="meta">ПЛАНИРУЕМЫЕ · хочу внести, но ещё не в расписании</div>
    ${planned.map(r => `
      <div class="task">
        <span class="t ed" data-lfplren="${r.id}" title="клик — переименовать">${lesc(r.name)}</span>
        <span class="pill btn ok" data-lfplgo="${r.id}" title="перенести в расписание">→ в расписание</span>
        <span class="rowbtn del" data-lfpldel="${r.id}">✕</span>
      </div>`).join('') || '<div class="empty">пусто — кидай сюда идеи рутин, до которых пока не дошли руки</div>'}
    <div class="task finadd">
      <input id="rtPlanName" placeholder="планируемая рутина: медитация, растяжка, испанский утром…">
      <span class="pill btn ok" id="rtPlanAdd">＋</span>
    </div>
  </div>
  <div class="card"><div class="task" style="border:0">
    <span class="pill btn ${localStorage.rtNotifyOn === '1' ? 'ok' : ''}" id="rtNotify">🔔 напоминания в браузере: ${localStorage.rtNotifyOn === '1' ? 'вкл' : 'выкл'}</span>
    <span class="meta">рутина с ⏰ временем пришлёт уведомление, пока приложение открыто · в мобильной версии будут системные пуши</span>
  </div></div>
  <div class="footer-hint">Стрик 🔥 — подряд отмеченные дни. Тепловая карта и привязка к практикам — этап 4.</div>`;

  document.querySelectorAll('#screen-routines [data-lfcheck]').forEach(el =>
    el.addEventListener('click', async () => { await lfApi.rCheck(+el.dataset.lfcheck); window.loadRoutines(); }));
  document.querySelectorAll('#screen-routines [data-lfren]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Название рутины:', el.textContent.trim());
      if (v?.trim()) { await lfApi.rPatch(+el.dataset.lfren, { name: v.trim() }); window.loadRoutines(); }
    }));
  document.querySelectorAll('#screen-routines [data-lfdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить рутину (с историей отметок)?')) { await lfApi.rDel(+el.dataset.lfdel); window.loadRoutines(); }
    }));
  document.querySelectorAll('#screen-routines [data-lftime]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Фиксированное время (чч:мм, пусто — убрать):', el.textContent.replace('⏰', '').trim());
      if (v == null) return;
      const t = v.trim();
      if (t && !/^([01]?\d|2[0-3]):[0-5]\d$/.test(t)) { alert('Формат: 07:30'); return; }
      await lfApi.rPatch(+el.dataset.lftime, { time: t ? t.padStart(5, '0') : null });
      window.loadRoutines();
    }));
  document.getElementById('rtNotify')?.addEventListener('click', async () => {
    if (localStorage.rtNotifyOn === '1') { localStorage.rtNotifyOn = '0'; window.loadRoutines(); return; }
    const perm = await Notification.requestPermission();
    if (perm !== 'granted') { alert('Браузер не дал разрешение на уведомления'); return; }
    localStorage.rtNotifyOn = '1';
    window.loadRoutines();
  });
  // планируемые: добавить / активировать / переименовать / удалить
  document.getElementById('rtPlanAdd')?.addEventListener('click', async () => {
    const name = document.getElementById('rtPlanName').value.trim();
    if (!name) return;
    await lfApi.rAdd({ name, planned: true });
    window.loadRoutines();
  });
  document.querySelectorAll('#screen-routines [data-lfplgo]').forEach(el =>
    el.addEventListener('click', async () => {
      const slot = prompt('Слот: утро / день / вечер', 'утро');
      if (slot == null) return;
      const t = prompt('Фиксированное время чч:мм (пусто — без времени):') ?? '';
      await lfApi.rPatch(+el.dataset.lfplgo, {
        planned: 0,
        slot: ['утро', 'день', 'вечер'].includes(slot.trim()) ? slot.trim() : 'утро',
        time: /^([01]?\d|2[0-3]):[0-5]\d$/.test(t.trim()) ? t.trim().padStart(5, '0') : null,
      });
      window.loadRoutines();
    }));
  document.querySelectorAll('#screen-routines [data-lfplren]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Название:', el.textContent.trim());
      if (v?.trim()) { await lfApi.rPatch(+el.dataset.lfplren, { name: v.trim() }); window.loadRoutines(); }
    }));
  document.querySelectorAll('#screen-routines [data-lfpldel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить планируемую рутину?')) { await lfApi.rDel(+el.dataset.lfpldel); window.loadRoutines(); }
    }));
  document.getElementById('rtAdd')?.addEventListener('click', async () => {
    const name = document.getElementById('rtName').value.trim();
    if (!name) return;
    const t = document.getElementById('rtTime').value.trim();
    await lfApi.rAdd({ name, slot: document.getElementById('rtSlot').value,
      time: /^([01]?\d|2[0-3]):[0-5]\d$/.test(t) ? t.padStart(5, '0') : null });
    window.loadRoutines();
  });
};

// ===== Напоминания: пока вкладка открыта, рутина с ⏰ шлёт браузерное уведомление.
// То же поле time станет источником системных пушей в мобильной версии.
async function routineReminderTick() {
  if (localStorage.rtNotifyOn !== '1' || typeof Notification === 'undefined'
      || Notification.permission !== 'granted') return;
  const now = new Date();
  const hhmm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  const key = 'rtNotified:' + (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)(now);
  const notified = new Set(JSON.parse(localStorage.getItem(key) ?? '[]'));
  let rows;
  try { rows = await lfApi.routines(); } catch { return; }
  for (const r of rows) {
    if (!r.time || r.done || notified.has(r.id) || r.time > hhmm) continue;
    new Notification('⏰ ' + r.name, { body: `Рутина на ${r.time} — пора. Стрик: ${r.streak} 🔥`, tag: 'routine-' + r.id });
    notified.add(r.id);
  }
  localStorage.setItem(key, JSON.stringify([...notified]));
}
setInterval(routineReminderTick, 30000);
routineReminderTick();

// ===== Люди =====
window.loadPeople = async function () {
  const rows = await lfApi.people();
  const soon = rows.filter(p => p.days_to_birthday != null && p.days_to_birthday <= 30)
    .sort((a, b) => a.days_to_birthday - b.days_to_birthday);
  const overdue = rows.filter(p => p.overdue_contact > 0)
    .sort((a, b) => b.overdue_contact - a.overdue_contact);

  const card = p => `
    <div class="card">
      <div class="task" style="border-bottom:1px solid var(--line)">
        <span class="t ed" data-lfpname="${p.id}" style="font-weight:600">${lesc(p.name)}</span>
        <span class="pill btn ok" data-lfpc="${p.id}" title="отметить контакт (можно с заметкой)">☎ связались</span>
        <span class="rowbtn del" data-lfpdel="${p.id}">✕</span>
      </div>
      <div class="kv">Ритм <b class="ed" data-lfprh="${p.id}">${p.rhythm_days ? 'раз в ' + p.rhythm_days + ' дн' : '—'}</b></div>
      <div class="kv">Последний контакт <b class="${p.overdue_contact > 0 ? 'amber' : ''}">${p.last_contact ?? 'не было'}${p.since_contact != null ? ' (' + p.since_contact + ' дн)' : ''}${p.overdue_contact > 0 ? ' ⚠' : ''}</b></div>
      <div class="kv">ДР <b class="ed" data-lfpbd="${p.id}">${p.birthday ?? '—'}${p.days_to_birthday != null ? ' · через ' + p.days_to_birthday + ' дн' : ''}</b></div>
      <div style="margin:6px 0 2px"><span class="ed meta" data-lfptags="${p.id}" title="интересы/чипы — клик">${
        p.tags ? p.tags.split(',').map(t => `<span class="chip">${lesc(t.trim())}</span>`).join('') : '+чипы'}</span></div>
      ${p.tasks.length ? `<div class="meta" style="margin-top:6px">СВЯЗИ С ЗАДАЧАМИ</div>` +
        p.tasks.map(t => `<div class="ritem" data-lfopen="${t.id}"><div class="rt">${lesc(t.title)}</div></div>`).join('') : ''}
      ${p.logs.length ? `<div class="meta" style="margin-top:6px">ПОСЛЕ ВСТРЕЧ</div>` +
        p.logs.map(l => `<div class="kv"><span>${l.date}</span><b style="text-align:right">${lesc(l.note)}</b></div>`).join('') : ''}
    </div>`;

  document.getElementById('screen-people').innerHTML = `
  <h2 style="margin-bottom:2px">Люди</h2>
  <div class="muted" style="margin-bottom:14px">ДР попадают в календарь и на дашборд · связи с задачами — по упоминанию имени</div>
  <div class="fingrid" style="grid-template-columns:1fr 1fr">
    <div class="card"><div class="meta">🎂 СКОРО</div>
      ${soon.map(p => `<div class="task"><span class="t">${lesc(p.name)}</span>
        <span class="meta ${p.days_to_birthday <= 7 ? 'amber' : ''}">${p.days_to_birthday === 0 ? 'СЕГОДНЯ!' : 'через ' + p.days_to_birthday + ' дн'}</span></div>`).join('')
        || '<div class="empty">в ближайший месяц ДР нет</div>'}
    </div>
    <div class="card"><div class="meta">☎ КОНТАКТ-РИТМ · ПРОСРОЧЕНО</div>
      ${overdue.map(p => `<div class="task"><span class="t amber">${lesc(p.name)}</span>
        <span class="meta">молчим ${p.since_contact ?? '∞'} дн</span>
        <span class="pill btn ok" data-lfpc="${p.id}">☎</span></div>`).join('')
        || '<div class="empty">все созвоны в норме</div>'}
    </div>
  </div>
  <div class="sec">Все люди</div>
  <div class="fingrid" style="grid-template-columns:1fr 1fr">${rows.map(card).join('')}</div>
  <div class="card"><div class="task finadd">
    <input id="ppName" placeholder="имя (Мама, Дима…)">
    <input id="ppBd" placeholder="ДР: 06-19" style="width:110px">
    <input id="ppRh" placeholder="ритм, дн" style="width:80px">
    <input id="ppTags" placeholder="чипы: падл, авто" style="width:160px">
    <span class="pill btn ok" id="ppAdd">＋</span>
  </div></div>`;

  const reload = window.loadPeople;
  document.querySelectorAll('#screen-people [data-lfopen]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.lfopen)));
  document.querySelectorAll('#screen-people [data-lfpc]').forEach(el =>
    el.addEventListener('click', async () => {
      const note = prompt('Заметка о контакте (опционально):') ?? '';
      await fetch(`/api/people/${el.dataset.lfpc}/contacted`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note }) });
      reload();
    }));
  document.querySelectorAll('#screen-people [data-lfpdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить человека (с логом встреч)?')) { await lfApi.pDel(+el.dataset.lfpdel); reload(); }
    }));
  document.querySelectorAll('#screen-people [data-lfpname]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Имя:', el.textContent.trim());
      if (v?.trim()) { await lfApi.pPatch(+el.dataset.lfpname, { name: v.trim() }); reload(); }
    }));
  document.querySelectorAll('#screen-people [data-lfptags]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Чипы через запятую (падл, авто-рынок…):');
      if (v == null) return;
      await lfApi.pPatch(+el.dataset.lfptags, { tags: v.trim() });
      reload();
    }));
  document.querySelectorAll('#screen-people [data-lfpbd]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('День рождения (2026-06-19, 06-19 или пусто — убрать):');
      if (v == null) return;
      const t = v.trim();
      if (t && !/^(\d{4}-)?\d{2}-\d{2}$/.test(t)) { alert('Формат: 2026-06-19 или 06-19'); return; }
      await lfApi.pPatch(+el.dataset.lfpbd, { birthday: t || null });
      reload();
    }));
  document.querySelectorAll('#screen-people [data-lfprh]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Связываться раз в сколько дней? (пусто — убрать)');
      if (v == null) return;
      const n = parseInt(v, 10);
      await lfApi.pPatch(+el.dataset.lfprh, { rhythm_days: isNaN(n) ? null : n });
      reload();
    }));
  document.getElementById('ppAdd')?.addEventListener('click', async () => {
    const name = document.getElementById('ppName').value.trim();
    if (!name) return;
    const bd = document.getElementById('ppBd').value.trim();
    const rh = parseInt(document.getElementById('ppRh').value, 10);
    await lfApi.pAdd({ name, birthday: /^(\d{4}-)?\d{2}-\d{2}$/.test(bd) ? bd : null,
      rhythm_days: isNaN(rh) ? null : rh, tags: document.getElementById('ppTags').value.trim() });
    window.loadPeople();
  });
};


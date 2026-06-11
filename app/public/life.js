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
  const key = 'rtNotified:' + now.toISOString().slice(0, 10);
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
  document.getElementById('screen-people').innerHTML = `
  <h2 style="margin-bottom:2px">Люди</h2>
  <div class="muted" style="margin-bottom:14px">ДР попадают в календарь и на дашборд · контакт-ритм напоминает связаться</div>
  <div class="card">
    ${rows.map(p => `
      <div class="task">
        <span class="t ed" data-lfpname="${p.id}" title="клик — переименовать">${lesc(p.name)}</span>
        <span class="ed meta" data-lfpbd="${p.id}" title="ДР: 2026-06-19 или 06-19">🎂 ${p.birthday ?? '+ДР'}${p.days_to_birthday != null ? ` (через ${p.days_to_birthday} дн)` : ''}</span>
        <span class="ed meta" data-lfprh="${p.id}" title="раз в сколько дней связываться">ритм: ${p.rhythm_days ? 'раз в ' + p.rhythm_days + ' дн' : '—'}</span>
        <span class="meta ${p.overdue_contact > 0 ? 'amber' : ''}">${p.last_contact ? 'контакт ' + p.last_contact : 'контактов не было'}${p.overdue_contact > 0 ? ' ⚠ пора' : ''}</span>
        <span class="pill btn ok" data-lfpc="${p.id}" title="отметить контакт сегодня">☎ связались</span>
        <span class="rowbtn del" data-lfpdel="${p.id}">✕</span>
      </div>`).join('') || '<div class="empty">добавь близких — и система напомнит про ДР и созвоны</div>'}
    <div class="task finadd">
      <input id="ppName" placeholder="имя (Мама, Дима…)">
      <input id="ppBd" placeholder="ДР: 06-19" style="width:110px">
      <input id="ppRh" placeholder="ритм, дн" style="width:80px">
      <span class="pill btn ok" id="ppAdd">＋</span>
    </div>
  </div>
  <div class="footer-hint">Заметки о людях, лог идей подарков и связи с задачами — этап 4.</div>`;

  const reload = window.loadPeople;
  document.querySelectorAll('#screen-people [data-lfpc]').forEach(el =>
    el.addEventListener('click', async () => { await lfApi.pContact(+el.dataset.lfpc); reload(); }));
  document.querySelectorAll('#screen-people [data-lfpdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить человека?')) { await lfApi.pDel(+el.dataset.lfpdel); reload(); }
    }));
  document.querySelectorAll('#screen-people [data-lfpname]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Имя:', el.textContent.trim());
      if (v?.trim()) { await lfApi.pPatch(+el.dataset.lfpname, { name: v.trim() }); reload(); }
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
      rhythm_days: isNaN(rh) ? null : rh });
    window.loadPeople();
  });
};

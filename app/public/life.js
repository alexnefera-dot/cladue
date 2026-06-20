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
const lesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SLOTS = ['утро', 'день', 'вечер'];
const DOW = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];   // ISO Пн=1..Вс=7
// дни недели рутины: '' / 'daily' = каждый день; 'workdays' = Пн–Пт; CSV '1,3,5'
window.rtDaySet = days => {
  if (!days || days === 'daily') return new Set();          // пусто = каждый день
  if (days === 'workdays') return new Set([1, 2, 3, 4, 5]);
  return new Set(String(days).split(',').map(s => +s.trim()).filter(n => n >= 1 && n <= 7));
};
window.rtActiveToday = (days, now = new Date()) => {
  const set = window.rtDaySet(days);
  if (!set.size) return true;                                // каждый день
  return set.has((now.getDay() + 6) % 7 + 1);               // JS Вс=0 → ISO
};
window.rtDaysShort = days => {
  const set = window.rtDaySet(days);
  if (!set.size) return '';                                  // каждый день — без метки
  if (set.size === 5 && [1, 2, 3, 4, 5].every(d => set.has(d))) return 'Пн–Пт';
  return [...set].sort((a, b) => a - b).map(d => DOW[d - 1]).join(' ');
};
(() => { if (document.getElementById('rt-days-style')) return;
  const st = document.createElement('style'); st.id = 'rt-days-style';
  st.textContent = '.rtdays{display:flex;gap:3px;align-items:center;flex-wrap:wrap;margin-top:3px}'
    + '.rtd{font:600 10px var(--mono);color:var(--muted);background:var(--bg2);border:1px solid var(--line);border-radius:5px;padding:2px 5px;cursor:pointer;user-select:none}'
    + '.rtd.on{background:var(--green);color:#fff;border-color:var(--green)}'
    + '.rtd-lbl{font-size:11px;color:var(--muted);margin-left:3px}'
    + '.task.rt-off{opacity:.5}';
  document.head.appendChild(st); })();

// ===== Рутины =====
window.loadRoutines = async function () {
  const rows = await lfApi.routines();
  pbSyncReminders(rows);
  const active = rows.filter(r => !r.archived), arch = rows.filter(r => r.archived);
  const planned = await fetch('/api/routines/planned').then(r => r.json()).catch(() => []);
  document.getElementById('screen-routines').innerHTML = `
  <h2 style="margin-bottom:2px">Рутины</h2>
  <div class="muted" style="margin-bottom:14px">микро-действия отдельно от задач · пропуск не висит долгом · сегодня: ${active.filter(r => window.rtActiveToday(r.days) && r.done).length}/${active.filter(r => window.rtActiveToday(r.days)).length}</div>
  <div class="fingrid">
    ${SLOTS.map(slot => `
      <div class="card"><div class="meta">${slot.toUpperCase()}</div>
        ${active.filter(r => r.slot === slot).map(r => {
          const off = !window.rtActiveToday(r.days), dlbl = window.rtDaysShort(r.days);
          return `
          <div class="task${off ? ' rt-off' : ''}">
            <span class="cb ${r.done ? 'done' : ''}" data-lfcheck="${r.id}"></span>
            <span class="t ${r.done ? 'done' : ''} ed" data-lfren="${r.id}" title="клик — переименовать">${lesc(r.name)}</span>
            <span class="ed meta num" data-lftime="${r.id}" title="фикс. время — напоминание (клик)">${r.time ? '⏰ ' + r.time : '+время'}</span>
            ${dlbl ? `<span class="meta" title="дни недели задаются при создании">${dlbl}</span>` : ''}
            ${r.streak ? `<span class="meta">🔥 ${r.streak}</span>` : ''}
            <span class="rowbtn" data-lfarch="${r.id}" title="в архив (история сохранится)">📦</span>
            <span class="rowbtn del" data-lfdel="${r.id}">✕</span>
          </div>`; }).join('') || '<div class="empty">пусто</div>'}
      </div>`).join('')}
  </div>
  <div class="card">
    <div class="task finadd">
      <input id="rtName" placeholder="новая рутина: таблетка, миноксидил, отжимания 3×15…">
      <select id="rtSlot">${SLOTS.map(s => `<option>${s}</option>`).join('')}</select>
      <input id="rtTime" placeholder="чч:мм (опц.)" style="width:95px">
      <span class="pill btn ok" id="rtAdd">＋</span>
    </div>
    <div class="rtdays" id="rtNewDays" style="margin-top:8px">${DOW.map((d, i) => `<span class="rtd" data-nd="${i + 1}">${d}</span>`).join('')}<span class="rtd-lbl">дни недели · не выбрано = каждый день</span></div>
  </div>
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
  ${arch.length ? `<div class="card"><div class="meta">📦 АРХИВ · ${arch.length} · не считаются, но история сохранена</div>
    ${arch.map(r => `<div class="task rt-off">
      <span class="t">${lesc(r.name)}</span>${window.rtDaysShort(r.days) ? `<span class="meta">${window.rtDaysShort(r.days)}</span>` : ''}
      <span class="pill btn ok" data-lfunarch="${r.id}" title="вернуть в активные">♻ вернуть</span>
      <span class="rowbtn del" data-lfdel="${r.id}" title="удалить навсегда">✕</span>
    </div>`).join('')}</div>` : ''}
  <div class="card"><div class="task" style="border:0">
    <span class="pill btn ${localStorage.rtNotifyOn === '1' ? 'ok' : ''}" id="rtNotify">🔔 ${pbReminderBridge ? 'системные напоминания' : 'напоминания в браузере'}: ${localStorage.rtNotifyOn === '1' ? 'вкл' : 'выкл'}</span>
    <span class="meta">${pbReminderBridge ? 'рутины с ⏰ и события календаря со временем шлют системный пуш по времени — даже если окно закрыто' : 'рутина с ⏰ временем пришлёт уведомление, пока приложение открыто · в приложении будут системные пуши'}</span>
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
  document.querySelectorAll('#screen-routines [data-lfarch]').forEach(el =>
    el.addEventListener('click', async () => { await lfApi.rPatch(+el.dataset.lfarch, { archived: 1 }); window.loadRoutines(); }));
  document.querySelectorAll('#screen-routines [data-lfunarch]').forEach(el =>
    el.addEventListener('click', async () => { await lfApi.rPatch(+el.dataset.lfunarch, { archived: 0 }); window.loadRoutines(); }));
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
    if (pbReminderBridge) {
      // Нативное приложение само спросит разрешение на уведомления при первом расписании.
      localStorage.rtNotifyOn = '1';
    } else {
      if (typeof Notification === 'undefined') { alert('Уведомления здесь не поддерживаются'); return; }
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') { alert('Браузер не дал разрешение на уведомления'); return; }
      localStorage.rtNotifyOn = '1';
    }
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
  // выбор дней недели в форме создания (локальное состояние, без запроса)
  document.querySelectorAll('#rtNewDays .rtd').forEach(el => el.addEventListener('click', () => el.classList.toggle('on')));
  document.getElementById('rtAdd')?.addEventListener('click', async () => {
    const name = document.getElementById('rtName').value.trim();
    if (!name) return;
    const t = document.getElementById('rtTime').value.trim();
    const sel = [...document.querySelectorAll('#rtNewDays .rtd.on')].map(x => +x.dataset.nd);
    const days = (sel.length === 0 || sel.length === 7) ? '' : sel.sort((a, b) => a - b).join(',');
    await lfApi.rAdd({ name, slot: document.getElementById('rtSlot').value,
      time: /^([01]?\d|2[0-3]):[0-5]\d$/.test(t) ? t.padStart(5, '0') : null, days });
    window.loadRoutines();
  });
};

// ===== Напоминания о рутинах =====
// В нативном приложении (WKWebView) Web Notifications не работают — расписание
// уходит в системный планировщик macOS/iOS через мост window.webkit. В обычном
// браузере остаётся фолбэк: пока вкладка открыта, рутина с ⏰ шлёт уведомление.
const pbReminderBridge = window.webkit?.messageHandlers?.pipboyReminders || null;

// Единое расписание напоминаний → нативный планировщик: рутины (ежедневно в ⏰)
// и события календаря (в их дату/время). Идемпотентно — заменяет прежние.
window.pbSyncAllReminders = async function () {
  if (!pbReminderBridge) return;
  if (localStorage.rtNotifyOn == null) localStorage.rtNotifyOn = '1';   // в нативе по умолчанию вкл
  if (localStorage.rtNotifyOn !== '1') { try { pbReminderBridge.postMessage({ enabled: false, items: [] }); } catch {} return; }
  const items = [];
  try {
    for (const r of await lfApi.routines()) if (r.time && !r.archived) {
      const [h, m] = r.time.split(':').map(Number);
      const base = { id: 'routine-' + r.id, title: '⏰ ' + r.name, body: `Рутина на ${r.time} — пора`, hour: h, minute: m };
      const set = window.rtDaySet(r.days);
      if (!set.size) items.push({ ...base, daily: true });               // каждый день
      else items.push({ ...base, weekdays: [...set] });                  // только выбранные дни
    }
  } catch {}
  try {
    const now = new Date();
    const ym = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const next = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    const seen = new Set();
    for (const mo of [ym(now), ym(next)]) {
      const cal = await fetch('/api/calendar?month=' + mo).then(r => r.json()).catch(() => ({}));
      for (const i of (cal.items || [])) {
        if (i.done || !i.time || (i.type !== 'event' && i.type !== 'task')) continue;
        const key = i.type + ':' + i.id + ':' + i.date; if (seen.has(key)) continue; seen.add(key);
        const [y, mm, d] = String(i.date).split('-').map(Number);
        const [h, min] = i.time.split(':').map(Number);
        const task = i.type === 'task';
        items.push({ id: (task ? 'event-task-' : 'event-') + i.id + '-' + i.date,
          title: (task ? '✓ ' : '📅 ') + i.title, body: `${task ? 'Задача' : 'Событие'} в ${i.time}`,
          year: y, month: mm, day: d, hour: h, minute: min });
      }
    }
  } catch {}
  try {   // практики психологии: по дням недели в своё время
    const psy = await fetch('/api/psy').then(r => r.json()).catch(() => ({}));
    for (const p of (psy.practices || [])) {
      if (!p.time || !p.days) continue;
      const [h, min] = p.time.split(':').map(Number);
      let wds;
      if (p.days === 'daily') wds = [1, 2, 3, 4, 5, 6, 7];
      else if (p.days === 'workdays') wds = [1, 2, 3, 4, 5];
      else wds = String(p.days).split(',').map(s => Number(s.trim())).filter(n => n >= 1 && n <= 7);
      if (wds.length) items.push({ id: 'practice-' + p.id, title: '◎ ' + p.name, body: `Практика в ${p.time}`, weekdays: wds, hour: h, minute: min });
    }
  } catch {}
  try { pbReminderBridge.postMessage({ enabled: true, items }); } catch {}
};
function pbSyncReminders() { window.pbSyncAllReminders(); }   // совместимость со старыми вызовами

async function routineReminderTick() {
  if (pbReminderBridge) return; // нативный планировщик уже всё расписал, тик не нужен
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
if (pbReminderBridge) window.pbSyncAllReminders();   // первичная синхронизация при загрузке

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
    <input id="ppBd" type="date" title="день рождения" style="width:150px">
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
      const cur = el.textContent.trim().split(' ·')[0];
      const v = await window.pickDate(cur, { title: 'День рождения' });
      if (v === undefined) return;
      await lfApi.pPatch(+el.dataset.lfpbd, { birthday: v || null });
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


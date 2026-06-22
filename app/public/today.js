/* «Сегодня» — по макету: месяц активности · рутины · задачи дня · события · люди · зоны · движение */
let tdData = null;

// Активна ли рутина сегодня по расписанию дней (ISO Пн=1..Вс=7; пусто/daily = каждый день).
// Самодостаточно — не зависит от загрузки life.js, иначе фильтр дней мог отключаться и показывать ВСЕ рутины.
function tdRoutineToday(days) {
  if (window.rtActiveToday) return window.rtActiveToday(days);
  if (!days || days === 'daily') return true;
  const set = days === 'workdays' ? new Set([1, 2, 3, 4, 5])
    : new Set(String(days).split(',').map(s => +s.trim()).filter(n => n >= 1 && n <= 7));
  if (!set.size) return true;
  return set.has((new Date().getDay() + 6) % 7 + 1);
}

const tdApi = {
  get: () => fetch('/api/today').then(r => r.json()),
  toggle: id => fetch(`/api/nodes/${id}/toggle`, { method: 'POST' }),
  routineCheck: id => fetch(`/api/routines/${id}/check`, { method: 'POST' }),
  contacted: id => fetch(`/api/people/${id}/contacted`, { method: 'POST' }),
  add: b => fetch('/api/nodes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  setSetting: (key, value) => fetch('/api/setting', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key, value }) }),
  setCheckin: (mood, note) => fetch('/api/track/checkin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mood, note }) }),
  practiceLog: id => fetch(`/api/psy/practices/${id}/log`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: '' }) }),
  metricVal: (id, value) => fetch(`/api/track/metrics/${id}/value`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value }) }),
};

const tesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const WD = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const MON = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

const TDSPH_COL = ['#1e9e57', '#c43f3f', '#a87708', '#6b4fb5', '#2a76b5', '#364656'];
window.loadToday = async function () {
  let d, sph = [], rest = [], psy = {}, finx = {};
  [d, sph, rest, psy, finx] = await Promise.all([
    tdApi.get().catch(e => ({ error: String(e) })),
    fetch('/api/spheres').then(r => r.json()).then(x => Array.isArray(x) ? x : []).catch(() => []),
    fetch('/api/rest').then(r => r.json()).then(x => Array.isArray(x) ? x : []).catch(() => []),
    fetch('/api/psy').then(r => r.json()).catch(() => ({})),
    fetch('/api/fin').then(r => r.json()).catch(() => ({})),
  ]);
  window.tdSpheres = sph; window.tdRestList = rest;
  window.tdPracticeList = Array.isArray(psy.practices) ? psy.practices : [];
  window.tdFin = finx || {};
  const el = document.getElementById('screen-today');
  // не белый экран: если /api/today не отдал нормальные данные — показываем причину
  if (!d || d.error || !d.progress || !Array.isArray(d.routines)) {
    if (el) el.innerHTML = `<h2 style="margin-bottom:8px">Сегодня</h2>
      <div class="card" style="color:var(--red)">Не удалось загрузить «Сегодня».<br>
      <span class="meta">${tesc(d && d.error ? d.error : 'нет данных от /api/today')}</span></div>`;
    return;
  }
  tdData = d;
  try { renderToday(); }
  catch (e) {
    if (el) el.innerHTML = `<h2 style="margin-bottom:8px">Сегодня</h2>
      <div class="card" style="color:var(--red)">Ошибка отрисовки: <span class="meta">${tesc(String(e && e.message || e))}</span></div>`;
  }
};
// блок «Кайф и восстановление»: способы отдохнуть по контексту дня + глобальные
function tdRest() {
  const all = Array.isArray(window.tdRestList) ? window.tdRestList : [];
  const wkEnd = [0, 6].includes(new Date().getDay());
  const ctx = wkEnd ? 'weekend' : 'weekday', ctxLabel = wkEnd ? 'выходные' : 'будни';
  const todayList = all.filter(r => r.scope === ctx), globalList = all.filter(r => r.scope === 'global');
  const row = r => `<div class="task"><span class="t">${tesc(r.text)}</span><span class="rowbtn del" data-restdel="${r.id}">✕</span></div>`;
  return `<div class="sec">🌿 Кайф и восстановление · ${ctxLabel} <span class="muted" style="font-weight:400">· не пропускай отдых</span></div>
    <div class="card">
      ${todayList.length ? todayList.map(row).join('') : `<div class="empty">добавь, чем восстановишься в ${ctxLabel} ↓</div>`}
      ${globalList.length ? `<div class="meta" style="margin-top:8px">🌍 Глобально · отпуск/поездки</div>${globalList.map(row).join('')}` : ''}
      <div class="task finadd" style="margin-top:6px">
        <input id="tdRestInput" placeholder="＋ способ отдохнуть / кайфануть">
        <select id="tdRestScope"><option value="weekday"${ctx === 'weekday' ? ' selected' : ''}>будни</option><option value="weekend"${ctx === 'weekend' ? ' selected' : ''}>выходные</option><option value="global">глобально</option></select>
        <span class="pill btn ok" id="tdRestAdd">＋</span>
      </div>
      ${todayList.length ? `<div style="margin-top:6px"><span class="pill btn" id="tdRestRoll">🎲 выбери и отдохни сейчас</span></div>` : ''}
    </div>`;
}
// эмодзи-иконка сферы по названию (автоподбор по ключевым словам)
function sphEmoji(name) {
  const n = (name || '').toLowerCase();
  const map = [
    [/здоров|спорт|тел[оа]|фитнес|трениров|питани|диет/, '💪'],
    [/финанс|деньг|капитал|инвест|бюджет|доход|богат/, '💰'],
    [/семь|дет[ие]|родител|жен[аы]|муж|брак/, '👨‍👩‍👧'],
    [/социал|друз|общени|связи|нетворк/, '👥'],
    [/дом|быт|жиль|квартир|ремонт|уют/, '🏠'],
    [/психолог|майндсет|ментал|эмоци|тревог|осознан|медитац/, '🧠'],
    [/работ|карьер|бизнес|дел[оа]|проект|професс/, '💼'],
    [/будущ|перспектив|план|мечт|визи|стратег/, '🔭'],
    [/отдых|хобби|кайф|развлеч|досуг|восстанов/, '🌴'],
    [/развит|обучен|учеб|знани|образ|навык|курс|рост/, '📚'],
    [/духов|смысл|вера|ценност/, '🕊️'],
    [/отношен|любов|партн[её]р|пара|романт/, '❤️'],
    [/путешеств|поездк|стран/, '✈️'],
    [/творч|искусств|музык|креатив/, '🎨'],
  ];
  for (const [re, e] of map) if (re.test(n)) return e;
  return null;
}
// иконка сферы: эмодзи на лёгком цветном фоне; если название не распознано — буква. Без оценок (не накручивать себя)
function tdSphIcon(name, col, size = 36) {
  const e = sphEmoji(name);
  if (e) return `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${col}22;display:flex;align-items:center;justify-content:center;font-size:${Math.round(size * 0.5)}px;flex:0 0 auto">${e}</div>`;
  const ch = (name || '?').trim().charAt(0).toUpperCase();
  return `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${col};color:#fff;display:flex;align-items:center;justify-content:center;font:700 ${Math.round(size * 0.42)}px var(--mono);flex:0 0 auto">${tesc(ch)}</div>`;
}
// Фокус дня: по одной сфере — иконка слева, название + шаг справа. Клик — внутрь сферы.
function tdSphStrip() {
  const list = (Array.isArray(window.tdSpheres) ? window.tdSpheres : []).slice();   // все сферы в своём порядке (ord)
  if (!list.length) return '';
  ensureTdSphStyle();
  return `<div class="sec" style="margin-top:0">🎯 Фокус дня · по сферам</div>
    <div class="card">${list.map((s, i) => `<div class="tdfoc" data-sphopen="${s.id}">
      ${tdSphIcon(s.name, TDSPH_COL[i % TDSPH_COL.length])}
      <div class="tdfoc-txt">
        <div class="tdfoc-n">${tesc(s.name)}</div>
        <div class="tdfoc-s">${s.step ? tesc(s.step) : '<span class="muted">шаг не задан — открой сферу</span>'}</div>
      </div>
      <span class="tdfoc-arr">›</span></div>`).join('')}</div>`;
}
function ensureTdSphStyle() {
  if (document.getElementById('tdsph-style')) return;
  const st = document.createElement('style'); st.id = 'tdsph-style';
  st.textContent = `.tdsph{display:flex;gap:9px;overflow-x:auto;padding-bottom:6px;margin-bottom:16px}
    .tdsph::-webkit-scrollbar{display:none}
    .tdsph-c{flex:0 0 auto;width:185px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 12px;box-shadow:var(--shadow-sm);cursor:pointer;transition:.12s}
    .tdsph-c:hover{border-color:var(--green-dim);transform:translateY(-1px)}
    .tdsph-top{display:flex;align-items:center;gap:8px}.tdsph-s{width:28px;height:28px;border-radius:8px;color:#fff;font:700 13px var(--mono);display:flex;align-items:center;justify-content:center;flex:0 0 auto}
    .tdsph-n{font-weight:700;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .tdsph-x{font-size:12px;color:var(--muted);margin-top:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .tdsph-bar{height:5px;border-radius:99px;background:var(--bg2);overflow:hidden;margin-top:7px}.tdsph-bar i{display:block;height:100%}
    .tdsph-m{font:600 10.5px var(--mono);color:var(--green);margin-top:4px}
    .tdfoc{display:flex;align-items:center;gap:12px;padding:10px 4px;border-top:1px solid var(--bg2);cursor:pointer}
    .tdfoc:first-child{border-top:0}
    .tdfoc-txt{flex:1;min-width:0}
    .tdfoc-n{font-size:14.5px;font-weight:700;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .tdfoc-s{font-size:12.5px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .tdfoc-arr{color:var(--muted);font-size:20px;flex:0 0 auto;line-height:1}
    @media(max-width:768px){.tdsph-c{width:158px;padding:9px 10px}.tdsph-n{font-size:12.5px}}`;
  document.head.appendChild(st);
}

// Практики дня (психология) — прямо на главной с отметкой (раньше было под замком 🔒).
function tdPractices() {
  const all = Array.isArray(window.tdPracticeList) ? window.tdPracticeList : [];
  const today = all.filter(p => p.today && !p.archived);
  if (!today.length) return '';
  const done = today.filter(p => p.done).length;
  return `<div class="sec">🧠 Практики сегодня · ${done}/${today.length}</div>
    <div class="card">${today.map(p => `<div class="task">
      <span class="cb ${p.done ? 'done' : ''}"${p.done ? '' : ` data-tdpractice="${p.id}"`}></span>
      ${p.time ? `<span class="meta num">${tesc(p.time)}</span>` : ''}
      <span class="t ${p.done ? 'done' : ''}" data-tdgoto="psy" style="cursor:pointer" title="открыть в Психологии">${tesc(p.name)}</span>
      ${p.streak ? `<span class="meta">🔥 ${p.streak}</span>` : ''}
    </div>`).join('')}</div>`;
}

// Финансы на главной: платежи недели + просроченные долги (с суммами). Клик → раздел Финансы.
function tdFinance() {
  const f = window.tdFin || {};
  const money = (n, c) => n == null ? '' : Math.round(Number(n) || 0).toLocaleString('ru-RU') + (c || '€');
  const obs = Array.isArray(f.obligations) ? f.obligations : [];
  const debts = Array.isArray(f.debts) ? f.debts : [];
  const week = obs.filter(o => o.days_left != null && o.days_left >= 0 && o.days_left <= 7);
  const overdue = debts.filter(x => (x.overdue_days ?? 0) > 0);
  const rowsW = week.map(o => `<div class="task" data-tdgoto="fin" style="cursor:pointer">
      <span class="t">${tesc(o.name)}</span>
      <span class="meta num">${money(o.amount, o.currency)}</span>
      <span class="meta ${o.days_left <= 2 ? 'amber' : ''}">${o.days_left === 0 ? 'сегодня' : o.days_left + 'д'}</span></div>`).join('');
  const rowsD = overdue.map(x => `<div class="task" data-tdgoto="fin" style="cursor:pointer">
      <span class="t amber">${tesc(x.name)}</span>
      <span class="meta num">${money(x.amount, x.currency)}</span>
      <span class="meta">просрочка ${x.overdue_days}д</span></div>`).join('');
  const body = (week.length || overdue.length)
    ? (week.length ? `<div class="meta" style="margin-bottom:4px">Платежи на неделе</div>${rowsW}` : '')
      + (overdue.length ? `<div class="meta" style="margin:6px 0 4px;color:var(--red)">Просроченные долги</div>${rowsD}` : '')
    : '<div class="empty" data-tdgoto="fin" style="cursor:pointer">платежей и долгов на неделе нет · открыть раздел →</div>';
  return `<div class="sec" data-tdgoto="fin" style="margin-top:0;cursor:pointer">💰 Финансы · неделя <span class="muted" style="font-weight:400">· весь раздел →</span></div>
    <div class="card">${body}</div>`;
}

// Оценить сегодня: метрики-оценки к внесению — дневные каждый день, недельные в воскресенье.
// Результат пишется в метрику (mVal без даты → ключ периода), итоги месяца видны в Трекинге/отчётах.
function tdMetricsDue() {
  const spheres = Array.isArray(window.tdSpheres) ? window.tdSpheres : [];
  const isSunday = new Date().getDay() === 0;
  const seen = new Set(), due = [];
  spheres.forEach(s => (s.tracking || []).forEach(m => {
    if (seen.has(m.id)) return;
    seen.add(m.id);
    if (m.computed) return;                              // авто-счётчики не оцениваются вручную
    if (m.cur !== null && m.cur !== undefined) return;   // уже оценено за текущий период
    if (m.cadence === 'daily') due.push({ id: m.id, name: m.name, type: m.type, period: 'день' });
    else if (m.cadence === 'weekly' && isSunday) due.push({ id: m.id, name: m.name, type: m.type, period: 'неделя' });
  }));
  if (!due.length) return '';
  return `<div class="sec">📊 Оценить сегодня · ${due.length}</div>
    <div class="card">${due.map(m => `<div class="task">
      <span class="t">${tesc(m.name)} <span class="meta">· ${m.period}</span></span>
      ${m.type === 'bool'
        ? `<span class="pill btn" data-tdmcheck="${m.id}">отметить ✓</span>`
        : `<span class="pill btn ok" data-tdmval="${m.id}" data-scale="${m.type === 'scale' ? '1' : '0'}">оценить</span>`}
    </div>`).join('')}</div>`;
}

function taskLine(t) {
  return `<div class="task">
    <span class="cb ${t.kind === 'decision' ? 'dec' : ''}" data-tdtoggle="${t.id}"></span>
    ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
    ${t.kind === 'decision' ? '<span class="pill dec">решение</span>' : ''}
    <span class="t" data-tdopen="${t.id}" style="cursor:pointer">${tesc(t.title)}</span>
    ${t.repeat ? '<span class="meta">🔁</span>' : ''}
    <span class="meta ed" data-tddate="${t.id}" data-tdtime="${t.due_time ?? ''}" title="изменить срок и время">${t.due_date ? t.due_date + (t.due_time ? ' · ' + t.due_time : '') : '＋ срок'}</span>
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

const tdIsMobile = () => window.matchMedia('(max-width: 768px)').matches;

function renderToday() {
  if (tdIsMobile()) return renderTodayMobile();
  const d = tdData;
  const dt = new Date(d.date + 'T00:00:00');
  const pct = d.progress.total ? Math.round(d.progress.typed / d.progress.total * 100) : 0;
  const rts = d.routines.filter(r => !r.archived && tdRoutineToday(r.days));   // только активные рутины на сегодня
  const rDone = rts.filter(r => r.done).length;

  document.getElementById('screen-today').innerHTML = `
  <h2 style="margin-bottom:2px">Сегодня</h2>
  <div class="muted" style="margin-bottom:14px">${WD[dt.getDay()]}, ${dt.getDate()} ${MON[dt.getMonth()]} ·
    просрочено: ${d.overdue.length} · сделано за неделю: ${d.movement.total} 👏</div>

  ${tdSphStrip()}
  ${tdRest()}

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
    <div class="card"><div class="meta">РУТИНЫ · ${rDone}/${rts.length} · по времени</div>
      ${rts.slice(0, 5).map(r => `
        <div class="task" style="padding:4px 0">
          <span class="cb ${r.done ? 'done' : ''}" data-tdroutine="${r.id}"></span>
          ${r.time ? `<span class="meta num ${r.due ? 'amber' : ''}">${r.time}</span>` : ''}
          <span class="t ${r.done ? 'done' : ''}">${tesc(r.name)}</span>
          ${r.due ? '<span class="pill p1">пора!</span>' : ''}
          ${r.streak ? `<span class="meta">🔥 ${r.streak}</span>` : ''}
        </div>`).join('') || '<div class="empty">добавь рутины в разделе ↻</div>'}
      ${rts.length > 5 ? `<div class="meta" style="cursor:pointer" data-tdgoto="routines">все ${rts.length} →</div>` : ''}</div>
  </div>

  ${d.overdue.length ? `<div class="sec" style="color:var(--red)">⚠ Просрочено</div>
  <div class="card">${d.overdue.map(taskLine).join('')}</div>` : ''}

  <div class="sec">Задачи на сегодня</div>
  <div class="card">${d.dueToday.map(taskLine).join('') ||
    '<div class="empty">сроков на сегодня нет — поставь дедлайны в Задачах</div>'}</div>

  ${tdMetricsDue()}
  ${tdPractices()}

  <div class="fingrid" style="grid-template-columns:1fr 1fr">
    <div>
      <div class="sec" style="margin-top:0">События · сегодня и завтра</div>
      <div class="card">
        ${d.events.map(e => `<div class="task">
          <span class="meta num">${e.date === d.date ? 'сегодня' : 'завтра'}${e.time ? ' ' + e.time : ''}</span>
          <span class="t">${tesc(e.title)}</span>
          ${typeof e.id === 'number' ? `<span class="pill btn ok" data-tdevent="${e.id}" data-date="${e.date}" title="прошёл — закрыть (повтор не удаляется)">✓</span>` : ''}</div>`).join('') || '<div class="empty">тихо</div>'}
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
      ${tdFinance()}
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

// ===== Мобильный дашборд: одна колонка, по приоритету действий, крупные тач-таргеты =====
function renderTodayMobile() {
  const d = tdData;
  const dt = new Date(d.date + 'T00:00:00');
  const pct = d.progress.total ? Math.round(d.progress.typed / d.progress.total * 100) : 0;
  const rts = d.routines.filter(r => !r.archived && tdRoutineToday(r.days));   // только активные рутины на сегодня
  const rDone = rts.filter(r => r.done).length;
  const moods = ['', '😞', '😐', '🙂'];

  // компактная строка-задача для телефона (крупная зона тапа)
  const mTask = t => `<div class="task">
    <span class="cb ${t.kind === 'decision' ? 'dec' : ''}" data-tdtoggle="${t.id}"></span>
    ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
    <span class="t" data-tdopen="${t.id}">${tesc(t.title)}</span>
    ${t.repeat ? '<span class="meta">🔁</span>' : ''}
    <span class="meta ed" data-tddate="${t.id}" data-tdtime="${t.due_time ?? ''}" title="изменить срок и время">${t.due_date ? t.due_date + (t.due_time ? ' · ' + t.due_time : '') : '＋ срок'}</span>
  </div>`;

  const checkin = d.checkin
    ? `<div class="tdcheck done" id="tdCheckinRedo">
         <span class="tdc-mood">${moods[d.checkin.mood]}</span>
         <span class="tdc-txt">${tesc(d.checkin.note) || 'день отмечен'}</span>
         <span class="meta">изменить</span></div>`
    : `<div class="tdcheck">
         <span class="tdc-q">Как день?</span>
         <span class="tdc-moods">
           <span class="pill btn" data-tdmood="1">😞</span>
           <span class="pill btn" data-tdmood="2">😐</span>
           <span class="pill btn" data-tdmood="3">🙂</span></span></div>`;

  document.getElementById('screen-today').innerHTML = `
  <h2 style="margin-bottom:2px">Сегодня</h2>
  <div class="muted" style="margin-bottom:12px">${WD[dt.getDay()]}, ${dt.getDate()} ${MON[dt.getMonth()]}</div>

  ${tdSphStrip()}
  ${tdRest()}

  <div class="tdchips">
    <div class="tdchip ${d.overdue.length ? 'red' : ''}"><b>${d.dueToday.length + d.overdue.length}</b><span>дел${d.overdue.length ? ` · ${d.overdue.length} просроч.` : ''}</span></div>
    <div class="tdchip"><b>${rDone}/${d.routines.length}</b><span>рутины</span></div>
    <div class="tdchip"><b>${d.movement.total}</b><span>за неделю 👏</span></div>
  </div>

  ${checkin}

  <div class="addbar" style="margin:14px 0 6px">
    <input id="tdQuick" placeholder="＋ Быстро в Инбокс — мысль, задача, что угодно">
    <span class="pill btn" id="tdRoll" title="случайная идея из твоих списков">🎲 идея</span>
  </div>
  <div id="tdRollBox" style="margin:0 0 8px"></div>

  ${d.overdue.length ? `<div class="sec" style="color:var(--red)">⚠ Просрочено</div>
  <div class="card">${d.overdue.map(mTask).join('')}</div>` : ''}

  <div class="sec">Задачи на сегодня</div>
  <div class="card">${d.dueToday.map(mTask).join('') ||
    '<div class="empty">сроков на сегодня нет</div>'}</div>

  <div class="sec">Рутины · ${rDone}/${rts.length}</div>
  <div class="card">
    ${rts.slice(0, 6).map(r => `
      <div class="task">
        <span class="cb ${r.done ? 'done' : ''}" data-tdroutine="${r.id}"></span>
        ${r.time ? `<span class="meta num ${r.due ? 'amber' : ''}">${r.time}</span>` : ''}
        <span class="t ${r.done ? 'done' : ''}">${tesc(r.name)}</span>
        ${r.due ? '<span class="pill p1">пора!</span>' : ''}
        ${r.streak ? `<span class="meta">🔥 ${r.streak}</span>` : ''}
      </div>`).join('') || '<div class="empty">добавь рутины в разделе ↻</div>'}
    ${rts.length > 6 ? `<div class="meta" style="cursor:pointer;padding-top:6px" data-tdgoto="routines">все ${rts.length} →</div>` : ''}</div>

  ${tdMetricsDue()}
  ${tdPractices()}

  ${d.events.length ? `<div class="sec">События · сегодня и завтра</div>
  <div class="card">
    ${d.events.map(e => `<div class="task">
      <span class="meta num">${e.date === d.date ? 'сегодня' : 'завтра'}${e.time ? ' ' + e.time : ''}</span>
      <span class="t">${tesc(e.title)}</span>
      ${typeof e.id === 'number' ? `<span class="pill btn ok" data-tdevent="${e.id}" data-date="${e.date}" title="прошёл — закрыть">✓</span>` : ''}</div>`).join('')}
  </div>` : ''}

  ${(d.people.birthdays.length || d.people.overdueContacts.length) ? `<div class="sec">Люди</div>
  <div class="card">
    ${d.people.birthdays.map(p => `<div class="task">
      <span class="t">🎂 ${tesc(p.name)}</span>
      <span class="meta ${p.days_to_birthday <= 7 ? 'amber' : ''}">${p.days_to_birthday === 0 ? 'СЕГОДНЯ!' : 'через ' + p.days_to_birthday + ' дн'}</span></div>`).join('')}
    ${d.people.overdueContacts.map(p => `<div class="task">
      <span class="t amber">☎ ${tesc(p.name)}</span>
      <span class="pill btn ok" data-tdcontact="${p.id}">связались ✓</span></div>`).join('')}
  </div>` : ''}

  ${tdFinance()}

  <div class="sec">Фокус месяца · цели недели</div>
  <div class="card">
    <div class="task"><span class="t"><span class="ed" id="tdActivity" title="тема месяца">${d.activityMonth ? tesc(d.activityMonth) : '＋ задать тему месяца'}</span></span></div>
    <div class="task"><span class="t">Недельные цели</span><span class="meta num">${d.weekGoals.done} / ${d.weekGoals.total}</span></div>
    <div class="bar"><i style="width:${d.weekGoals.total ? d.weekGoals.done / d.weekGoals.total * 100 : 0}%"></i></div>
    <div class="meta" style="margin-top:6px">разобрано: ${pct}% · инбокс: ${d.inbox}</div>
  </div>

  ${d.movement.top.length ? `<div class="sec">▲ Движение недели</div>
  <div class="card">
    ${d.movement.top.map(([cat, n]) => `<div class="task">
      <span class="pill ok">⚑ ${tesc(cat)}</span>
      <span class="t">${n} ${n === 1 ? 'шаг' : 'шага(ов)'}</span></div>`).join('')}
  </div>` : ''}`;

  bindToday();
}

function bindToday() {
  document.querySelectorAll('#screen-today [data-sphopen]').forEach(el =>
    el.addEventListener('click', () => window.openSphere?.(+el.dataset.sphopen)));
  // отдых/восстановление
  const restAdd = async () => {
    const inp = document.getElementById('tdRestInput'); const text = inp?.value.trim(); if (!text) return;
    await fetch('/api/rest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, scope: document.getElementById('tdRestScope').value }) });
    window.loadToday();
  };
  document.getElementById('tdRestAdd')?.addEventListener('click', restAdd);
  document.getElementById('tdRestInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') restAdd(); });
  document.querySelectorAll('#screen-today [data-restdel]').forEach(el =>
    el.addEventListener('click', async () => { await fetch('/api/rest/' + el.dataset.restdel, { method: 'DELETE' }); window.loadToday(); }));
  document.getElementById('tdRestRoll')?.addEventListener('click', () => {
    const wkEnd = [0, 6].includes(new Date().getDay());
    const list = (Array.isArray(window.tdRestList) ? window.tdRestList : []).filter(r => r.scope === (wkEnd ? 'weekend' : 'weekday'));
    if (list.length) alert('🌿 Сегодня восстановись так:\n\n' + list[Math.floor(Math.random() * list.length)].text);
  });
  document.querySelectorAll('#screen-today [data-tdtoggle]').forEach(el =>
    el.addEventListener('click', async e => {
      e.stopPropagation();
      if (window.preflightTodayOk && !await window.preflightTodayOk(+el.dataset.tdtoggle)) return;
      await tdApi.toggle(+el.dataset.tdtoggle);
      window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-tdroutine]').forEach(el =>
    el.addEventListener('click', async () => { await tdApi.routineCheck(+el.dataset.tdroutine); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdpractice]').forEach(el =>
    el.addEventListener('click', async () => { await tdApi.practiceLog(+el.dataset.tdpractice); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdmval]').forEach(el =>
    el.addEventListener('click', async () => {
      const scale = el.dataset.scale === '1';
      const v = prompt(scale ? 'Оценка 1–10:' : 'Значение:'); if (v == null) return;
      let n = parseFloat(String(v).replace(',', '.')); if (isNaN(n)) return;
      if (scale) n = Math.max(1, Math.min(10, Math.round(n)));
      await tdApi.metricVal(+el.dataset.tdmval, n); window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-tdmcheck]').forEach(el =>
    el.addEventListener('click', async () => { await tdApi.metricVal(+el.dataset.tdmcheck, 1); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdcontact]').forEach(el =>
    el.addEventListener('click', async () => { await tdApi.contacted(+el.dataset.tdcontact); window.loadToday(); }));
  document.querySelectorAll('#screen-today [data-tdevent]').forEach(el =>
    el.addEventListener('click', async () => {   // закрыть дату как «выполнено», событие/повтор остаётся
      await fetch('/api/events/' + el.dataset.tdevent + '/done', { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date: el.dataset.date }) });
      window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-tdopen]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.tdopen)));
  document.querySelectorAll('#screen-today [data-tddate]').forEach(el =>
    el.addEventListener('click', async e => {
      e.stopPropagation();
      const cur = (el.textContent.trim().match(/^\d{4}-\d{2}-\d{2}/) || [null])[0];
      const curTime = /^\d{2}:\d{2}$/.test(el.dataset.tdtime || '') ? el.dataset.tdtime : '';
      const v = await window.pickDate(cur, { title: 'Срок и время задачи', withTime: true, time: curTime });
      if (v === undefined) return;   // отмена — ничего не меняем
      const body = { due_date: v.date || null, due_time: v.date ? (v.time || null) : null };  // время без даты не имеет смысла
      await fetch('/api/nodes/' + el.dataset.tddate, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      window.loadToday();
    }));
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
// после перезагрузки фронта (новый фронт по Wi-Fi / рестарт WebView) возвращаемся на тот
// же экран, где был, — синхрон не должен «скидывать на главную»
try {
  const s = sessionStorage.pbScreen;
  if (s && s !== 'today' && typeof SCREENS !== 'undefined' && s in SCREENS) showScreen(s);
} catch {}

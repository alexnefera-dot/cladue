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
// метка типа записи в списках дня (task/без типа — без метки, это обычная задача)
const TD_KIND_LABEL = { decision: 'решение', question: 'вопрос', idea: 'идея', worry: 'тревога', principle: 'принцип' };
window.loadToday = async function () {
  let d, sph = [], rest = [], psy = {}, finx = {};
  [d, sph, rest, psy, finx] = await Promise.all([
    tdApi.get().catch(e => ({ error: String(e) })),
    fetch('/api/spheres').then(r => r.json()).then(x => Array.isArray(x) ? x : []).catch(() => []),
    fetch('/api/rest').then(r => r.json()).then(x => (x && x.ideas) ? x : { ideas: Array.isArray(x) ? x : [], log: [] }).catch(() => ({ ideas: [], log: [] })),
    fetch('/api/psy').then(r => r.json()).catch(() => ({})),
    fetch('/api/fin').then(r => r.json()).catch(() => ({})),
  ]);
  // План недели берём из той же ленты, что календарь. Неделя может лечь на два месяца —
  // тогда тянем оба и склеиваем, иначе половина дней окажется пустой.
  const wkStart = tdWeekStart();
  const months = [...new Set([0, 6].map(k => {
    const x = new Date(wkStart); x.setDate(x.getDate() + k); return tdIso(x).slice(0, 7);
  }))];
  window.tdWeek = (await Promise.all(months.map(m =>
    fetch('/api/calendar?month=' + m).then(r => r.json()).then(x => x.items || []).catch(() => []))))
    .flat();
  window.tdSpheres = sph; window.tdRestData = rest; window.tdRestList = rest.ideas;
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
// Блок «Кайф»: не список, а три вещи — что сделать сегодня, чем давно не занимался
// и сколько раз отдыхал на неделе. Виды нужны, чтобы видеть перекос: «восстановиться»
// набирается само, а «играть» без напоминания не случается никогда.
const REST_KINDS = [
  ['play', '🧒', 'играть'], ['restore', '😴', 'восстановиться'], ['people', '👥', 'люди'],
  ['create', '🎨', 'творить'], ['trip', '🌍', 'вылазка'],
];
const REST_GOAL = { weekday: 3, weekend: 2 };   // мягкая цель на неделю: не сгорает, не штрафует
const restKind = k => REST_KINDS.find(x => x[0] === k) || REST_KINDS[1];

function tdRest() {
  const data = window.tdRestData || { ideas: [], log: [] };
  const all = data.ideas || [], log = data.log || [];
  const today = data.today || tdIso(new Date());
  const wkEnd = [0, 6].includes(new Date().getDay());
  const ctx = wkEnd ? 'weekend' : 'weekday', ctxLabel = wkEnd ? 'выходные' : 'будни';
  const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 864e5);

  // сколько дней молчит каждый вид: пустой сегмент и есть сигнал про перекос
  const byKind = {};
  REST_KINDS.forEach(([k]) => byKind[k] = { n: 0, last: null });
  log.forEach(l => { const b = byKind[l.kind]; if (!b) return; b.n++; if (!b.last || l.date > b.last) b.last = l.date; });
  const silent = REST_KINDS
    .map(([k, ico, name]) => ({ k, ico, name, since: byKind[k].last ? days(byKind[k].last, today) : 99 }))
    .sort((a, b) => b.since - a.since)[0];

  // подбор на сегодня: сначала то, чего давно не было; в будни — что покороче
  const pool = all.filter(r => r.scope === ctx || r.scope === 'global');
  const score = r => (r.last_at ? days(r.last_at, today) : 60)
    - (ctx === 'weekday' && (r.mins || 0) > 60 ? 20 : 0);   // длинное в будни отодвигаем
  const sorted = pool.slice().sort((a, b) => score(b) - score(a));
  const pick = [];
  const fromSilent = sorted.find(r => r.kind === silent.k && silent.since > 3);
  if (fromSilent) pick.push(fromSilent);
  sorted.forEach(r => { if (pick.length < 3 && !pick.includes(r)) pick.push(r); });

  // неделя: точки по дням, цель мягкая — просто видно, сколько было
  const wk = tdWeekStart(), dots = [];
  let doneWeek = 0;
  for (let i = 0; i < 7; i++) {
    const d = new Date(wk); d.setDate(wk.getDate() + i);
    const iso = tdIso(d), was = log.some(l => l.date === iso);
    if (was) doneWeek++;
    dots.push(`<i class="restdot${was ? ' on' : ''}${iso === today ? ' now' : ''}" title="${iso}"></i>`);
  }
  const goal = REST_GOAL.weekday + REST_GOAL.weekend;
  const quiet = log.length && days(log[log.length - 1].date, today) >= 3 ? days(log[log.length - 1].date, today) : 0;

  const card = r => {
    const [, ico, name] = restKind(r.kind);
    const ago = r.last_at ? (r.last_at === today ? 'сегодня' : `${days(r.last_at, today)} дн. назад`) : 'ни разу';
    return `<div class="restcard${r.done_today ? ' done' : ''}">
      <div class="restt">${ico} ${tesc(r.text)}</div>
      <div class="meta">${name}${r.mins ? ` · ${r.mins} мин` : ''} · ${ago}</div>
      <span class="pill btn ${r.done_today ? 'ok' : ''}" data-restdone="${r.id}">${r.done_today ? '✓ отдохнул' : '✓ сделал'}</span>
    </div>`;
  };
  const row = r => `<div class="task">
    <span class="pill btn" data-restkind="${r.id}:${r.kind || 'restore'}" title="вид отдыха — клик">${restKind(r.kind)[1]} ${restKind(r.kind)[2]}</span>
    <span class="t">${tesc(r.text)}</span>
    <span class="pill btn" data-restscope="${r.id}:${r.scope}" title="когда — клик">${r.scope === 'global' ? 'глобально' : r.scope === 'weekend' ? 'выходные' : 'будни'}</span>
    <span class="rowbtn del" data-restdel="${r.id}">✕</span></div>`;

  return `<div class="sec">🌿 Кайф · ${ctxLabel} <span class="muted" style="font-weight:400">· отдых не догоняют, его планируют</span></div>
    <div class="card">
      ${quiet ? `<div class="restquiet">${quiet} дн. без отдыха — возьми самое короткое</div>` : ''}
      <div class="restcards">${pick.length ? pick.map(card).join('')
        : `<div class="empty">добавь, чем восстановишься в ${ctxLabel} ↓</div>`}</div>
      <div class="restbal">
        ${REST_KINDS.map(([k, ico, name]) => {
          const b = byKind[k], since = b.last ? days(b.last, today) : null;
          return `<span class="restseg${b.n ? '' : ' zero'}" title="${name}: ${b.n} раз за 14 дней${since != null ? `, последний ${since} дн. назад` : ', ни разу'}">
            ${ico} <b>${b.n}</b></span>`;
        }).join('')}
        <span class="meta" style="margin-left:auto">${silent.since > 3 ? `${silent.ico} ${silent.name} — ${silent.since > 90 ? 'ни разу' : silent.since + ' дн. молчит'}` : 'виды в балансе'}</span>
      </div>
      <div class="restweek"><span class="meta">неделя</span>${dots.join('')}
        <span class="meta">${doneWeek} из ${goal}${doneWeek >= goal ? ' · норма' : ''}</span></div>
      <details class="restpool">
        <summary class="meta">все идеи · ${all.length}</summary>
        ${all.map(row).join('') || '<div class="empty">пусто</div>'}
        <div class="task finadd" style="margin-top:6px">
          <input id="tdRestInput" placeholder="＋ способ отдохнуть / кайфануть">
          <select id="tdRestKind">${REST_KINDS.map(([k, ico, name]) => `<option value="${k}">${ico} ${name}</option>`).join('')}</select>
          <input id="tdRestMins" placeholder="мин" style="width:60px">
          <select id="tdRestScope"><option value="weekday"${ctx === 'weekday' ? ' selected' : ''}>будни</option><option value="weekend"${ctx === 'weekend' ? ' selected' : ''}>выходные</option><option value="global">глобально</option></select>
          <span class="pill btn ok" id="tdRestAdd">＋</span>
        </div>
      </details>
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
// Фокус дня: активные вехи («путь к 10») из всех сфер — что добиваем. Клик — внутрь сферы.
function tdSphStrip() {
  const spheres = Array.isArray(window.tdSpheres) ? window.tdSpheres : [];
  const items = [];
  let hasOpen = false;
  spheres.forEach((s, i) => (s.milestones || []).forEach(m => {
    const p = Math.max(0, Math.min(10, m.progress ?? 0));
    if (p >= 10) return;   // закрытые вехи не показываем
    hasOpen = true;
    if (!m.pinned) return;   // на главной — только закреплённые ⭐
    items.push({ mid: m.id, sid: s.id, sphere: s.name, col: TDSPH_COL[i % TDSPH_COL.length], title: m.title, p });
  }));
  ensureTdSphStyle();
  if (!items.length) return hasOpen
    ? `<div class="sec" style="margin-top:0">🗺 Фокус дня · вехи</div><div class="card"><div class="empty">закрепи вехи ⭐ в сферах — появятся здесь</div></div>`
    : '';
  // ручной порядок «фокуса» (настройка focus_order) — перетаскиванием; вехи вне списка уходят в конец
  const order = String(tdData?.focusOrder || '').split(',').filter(Boolean).map(Number);
  if (order.length) items.sort((a, b) => (order.indexOf(a.mid) + 1 || 1e9) - (order.indexOf(b.mid) + 1 || 1e9));
  return `<div class="sec" style="margin-top:0">🗺 Фокус дня · вехи (путь к 10) <span class="hintstar">тащи, чтобы расставить</span></div>
    <div class="card">${items.map(m => `<div class="tdfoc" draggable="true" data-mid="${m.mid}" data-sphopen="${m.sid}">
      ${tdSphIcon(m.sphere, m.col, 30)}
      <div class="tdfoc-txt">
        <div class="tdfoc-n">${m.title ? tesc(m.title) : '<span class="muted">без названия</span>'}</div>
        <div class="tdfoc-s">${tesc(m.sphere)} · ${m.p}/10</div>
      </div>
      <span class="tdfoc-bar"><i style="width:${m.p * 10}%;background:${m.col}"></i></span>
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
    .tdfoc-bar{width:48px;height:5px;border-radius:99px;background:var(--bg2);overflow:hidden;flex:0 0 auto}.tdfoc-bar i{display:block;height:100%}
    .tdfoc-arr{color:var(--muted);font-size:20px;flex:0 0 auto;line-height:1}
    .tdfoc[draggable=true]{cursor:grab}
    .tdfoc.dropbefore{box-shadow:inset 0 2px 0 var(--green)}.tdfoc.dropafter{box-shadow:inset 0 -2px 0 var(--green)}
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
  spheres.forEach((s, si) => (s.tracking || []).forEach(m => {
    if (!m.own) return;                                  // только метрики, ЯВНО привязанные к сфере (не общие, подтянутые по дефолту секции)
    if (seen.has(m.id)) return;
    seen.add(m.id);
    if (m.computed) return;                              // авто-счётчики не оцениваются вручную
    if (m.cur !== null && m.cur !== undefined) return;   // уже оценено за текущий период
    const meta = { id: m.id, name: m.name, type: m.type, sphere: s.name, col: TDSPH_COL[si % TDSPH_COL.length] };
    if (m.cadence === 'daily') due.push({ ...meta, period: 'день' });
    else if (m.cadence === 'weekly' && isSunday) due.push({ ...meta, period: 'неделя' });
  }));
  if (!due.length) return '';
  return `<div class="sec">📊 Оценить сегодня · ${due.length}</div>
    <div class="card">${due.map(m => `<div class="task" style="gap:10px">
      ${tdSphIcon(m.sphere, m.col, 24)}
      <span class="t">${tesc(m.name)} <span class="meta">· ${tesc(m.sphere)} · ${m.period}</span></span>
      ${m.type === 'bool'
        ? `<span class="pill btn" data-tdmcheck="${m.id}">отметить ✓</span>`
        : `<span class="pill btn ok" data-tdmval="${m.id}" data-scale="${m.type === 'scale' ? '1' : '0'}">оценить</span>`}
    </div>`).join('')}</div>`;
}

function taskLine(t, hideDate) {
  return `<div class="task">
    <span class="cb ${t.kind === 'decision' ? 'dec' : ''}" data-tdtoggle="${t.id}"></span>
    ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
    ${TD_KIND_LABEL[t.kind] ? `<span class="pill ${t.kind === 'decision' ? 'dec' : ''}">${TD_KIND_LABEL[t.kind]}</span>` : ''}
    <span class="t" data-tdopen="${t.id}" style="cursor:pointer">${tesc(t.title)}</span>
    ${t.repeat ? '<span class="meta">🔁</span>' : ''}
    ${hideDate ? (t.due_time ? `<span class="meta">${tesc(t.due_time)}</span>` : '')
      : `<span class="meta ed" data-tddate="${t.id}" data-tdtime="${t.due_time ?? ''}" title="изменить срок и время">${t.due_date ? t.due_date + (t.due_time ? ' · ' + t.due_time : '') : '＋ срок'}</span>`}
  </div>`;
}

// обязательство (платёж) — наравне с задачей: «оплатить» двигает дату на следующий период
function obLine(o) {
  const amt = Math.round(Number(o.amount) || 0).toLocaleString('ru-RU');
  return `<div class="task">
    <span class="pill p2" title="финансовое обязательство">◈ платёж</span>
    <span class="t" data-tdopen-ob="${o.id}" style="cursor:pointer">${tesc(o.name)}</span>
    <span class="meta num">${amt} ${tesc(o.currency || '€')}</span>
    ${o.overdue_days ? `<span class="meta" style="color:var(--red)">просрочено ${o.overdue_days}д</span>` : ''}
    <span class="meta ed" data-obdate="${o.id}" data-obtime="${o.due_time ?? ''}" title="изменить дату и время">${o.next_date || '＋ дата'}${o.due_time ? ' · ' + o.due_time : ''}</span>
    <span class="pill btn ok" data-obpay="${o.id}" title="оплачено — сдвинуть на следующий период">оплатить ✓</span>
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

const tdIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const tdWeekStart = () => {   // неделя с понедельника
  const d = new Date(); const sh = (d.getDay() + 6) % 7;
  d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - sh); return d;
};
const TD_WD = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
const TD_TYPE = { task: 'ev-task', money: 'ev-money', step: 'ev-step', event: 'ev-cal', practice: 'ev-psy' };

// Единый блок: просроченное сверху без дат, сегодня — широкой панелью с полными строками,
// остальные дни недели — компактной полосой. Дела тащатся между днями и в сегодня.
function tdWeekBoard(compact) {
  const d = tdData || {};
  const items = window.tdWeek || [];
  const start = tdWeekStart(), today = tdIso(new Date());
  const byDate = {};
  items.forEach(it => (byDate[it.date] ||= []).push(it));
  const days = Array.from({ length: 7 }, (_, i) => { const x = new Date(start); x.setDate(x.getDate() + i); return x; });
  const rest = compact ? days : days.filter(x => tdIso(x) !== today);   // на узком экране сегодня остаётся в полосе
  const busiest = Math.max(1, ...rest.map(x => (byDate[tdIso(x)] || []).length));

  const over = d.overdue || [], obOver = d.obOverdue || [];
  // задачи и платежи сегодня берём из своих списков — там полные поля; шаги и события добираем из ленты
  const extra = (byDate[today] || []).filter(it => it.type !== 'task' && it.type !== 'money');
  const nToday = (d.dueToday || []).length + (d.obToday || []).length + extra.length;
  const dt = new Date();

  const chip = it => {
    const drag = it.type === 'task' || it.type === 'step' || it.type === 'money'
      || (it.type === 'event' && it.recur === 'none' && !it.bday);
    return `<div class="tdwev ${TD_TYPE[it.type] || ''}${it.done ? ' evdone' : ''}"
      ${drag ? `draggable="true" data-tdmv="${it.type}:${it.id}"` : ''}
      ${it.type === 'task' ? `data-nid="${it.id}"` : ''}
      title="${tesc(it.title)}${drag ? ' · тащи на другой день' : ''}">
      ${it.time ? `<b>${it.time}</b> ` : ''}${tesc(it.title)}</div>`;
  };

  if (compact) return `
  <div class="sec">План недели · тащи дело на другой день</div>
  <div class="tdweek">
    ${rest.map(x => {
      const date = tdIso(x), list = byDate[date] || [], past = date < today;
      return `<div class="tdwday${date === today ? ' now' : ''}${past ? ' past' : ''}" data-tdday="${date}">
        <div class="tdwhead"><span class="tdwd">${TD_WD[(x.getDay() + 6) % 7]}</span>
          <span class="tdwn">${x.getDate()}</span>
          ${list.length ? `<span class="tdwcount">${list.length}</span>` : ''}</div>
        <div class="tdwload"><i style="width:${(list.length / busiest * 100).toFixed(0)}%"></i></div>
        <div class="tdwlist">${list.map(chip).join('') || '<div class="tdwempty">—</div>'}</div>
      </div>`;
    }).join('')}
  </div>`;

  return `
  <div class="sec">План недели · тащи дело на другой день</div>
  <div class="tdboard">
    ${over.length || obOver.length ? `<div class="tdover" data-tdday="${today}">
      <div class="tdoverhead">⚠ Просрочено · ${over.length + obOver.length}</div>
      ${over.map(t => taskLine(t, true)).join('')}${obOver.map(obLine).join('')}
    </div>` : ''}

    <div class="tdnow${nToday ? '' : ' quiet'}" data-tdday="${today}">
      <div class="tdnowhead">
        <span class="tdnowd">Сегодня</span>
        <span class="meta">${TD_WD[(dt.getDay() + 6) % 7]}, ${dt.getDate()} ${MON[dt.getMonth()]}</span>
        <span class="meta" style="margin-left:auto">${nToday ? nToday + ' дел' : 'свободно'}</span>
      </div>
      ${(d.dueToday || []).map(t => taskLine(t, true)).join('')}
      ${(d.obToday || []).map(obLine).join('')}
      ${extra.map(chip).join('')}
      ${nToday ? '' : '<div class="empty">сроков на сегодня нет — поставь дедлайны или перетащи дело сюда</div>'}
    </div>

    <div class="tdweek">
      ${rest.map(x => {
        const date = tdIso(x), list = byDate[date] || [], past = date < today;
        return `<div class="tdwday${past ? ' past' : ''}" data-tdday="${date}">
          <div class="tdwhead">
            <span class="tdwd">${TD_WD[(x.getDay() + 6) % 7]}</span>
            <span class="tdwn">${x.getDate()}</span>
            ${list.length ? `<span class="tdwcount">${list.length}</span>` : ''}
          </div>
          <div class="tdwload"><i style="width:${(list.length / busiest * 100).toFixed(0)}%"></i></div>
          <div class="tdwlist">${list.map(chip).join('') || '<div class="tdwempty">—</div>'}</div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}

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
  ${tdWeekBoard()}

  <div class="addbar" style="margin:0 0 6px">
    <input id="tdQuick" placeholder="＋ Новая задача или мысль — Enter без срока в Инбокс, или укажи дату ниже">
    <span class="pill btn" id="tdRoll" title="рулетка спонтанности: случайная идея из твоих же списков">🎲</span>
  </div>
  <div class="addbar tdwhen" style="margin:0 0 6px">
    <input type="date" id="tdQuickDate" title="дата (пусто — задача уйдёт в Инбокс)">
    <input type="time" id="tdQuickTime" title="время (учитывается только с датой)">
    <span class="pill btn ok" id="tdQuickAdd" title="создать задачу">＋ добавить</span>
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
    ${TD_KIND_LABEL[t.kind] ? `<span class="pill ${t.kind === 'decision' ? 'dec' : ''}">${TD_KIND_LABEL[t.kind]}</span>` : ''}
    <span class="t" data-tdopen="${t.id}">${tesc(t.title)}</span>
    ${t.repeat ? '<span class="meta">🔁</span>' : ''}
    ${hideDate ? (t.due_time ? `<span class="meta">${tesc(t.due_time)}</span>` : '')
      : `<span class="meta ed" data-tddate="${t.id}" data-tdtime="${t.due_time ?? ''}" title="изменить срок и время">${t.due_date ? t.due_date + (t.due_time ? ' · ' + t.due_time : '') : '＋ срок'}</span>`}
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
  ${tdWeekBoard(true)}

  <div class="tdchips">
    <div class="tdchip ${d.overdue.length || (d.obOverdue || []).length ? 'red' : ''}"><b>${d.dueToday.length + d.overdue.length + (d.obToday || []).length + (d.obOverdue || []).length}</b><span>дел${d.overdue.length + (d.obOverdue || []).length ? ` · ${d.overdue.length + (d.obOverdue || []).length} просроч.` : ''}</span></div>
    <div class="tdchip"><b>${rDone}/${d.routines.length}</b><span>рутины</span></div>
    <div class="tdchip"><b>${d.movement.total}</b><span>за неделю 👏</span></div>
  </div>

  ${checkin}

  <div class="addbar" style="margin:14px 0 6px">
    <input id="tdQuick" placeholder="＋ Задача или мысль — Enter без срока в Инбокс">
    <span class="pill btn" id="tdRoll" title="случайная идея из твоих списков">🎲</span>
  </div>
  <div class="addbar tdwhen" style="margin:0 0 6px">
    <input type="date" id="tdQuickDate" title="дата (пусто — задача уйдёт в Инбокс)">
    <input type="time" id="tdQuickTime" title="время (учитывается только с датой)">
    <span class="pill btn ok" id="tdQuickAdd" title="создать задачу">＋ добавить</span>
  </div>
  <div id="tdRollBox" style="margin:0 0 8px"></div>

  ${d.overdue.length || (d.obOverdue || []).length ? `<div class="sec" style="color:var(--red)">⚠ Просрочено</div>
  <div class="card">${d.overdue.map(mTask).join('')}${(d.obOverdue || []).map(obLine).join('')}</div>` : ''}

  <div class="sec">Задачи на сегодня</div>
  <div class="card">${(d.dueToday.map(mTask).join('') + (d.obToday || []).map(obLine).join('')) ||
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

// Перетаскивание дел между днями недели: дата меняется в первоисточнике —
// в задаче, шаге, платеже или событии, как и в календаре.
function bindTdWeek() {
  let drag = null;
  const clear = () => document.querySelectorAll('#screen-today .tdwday.dropinto')
    .forEach(x => x.classList.remove('dropinto'));
  document.querySelectorAll('#screen-today [data-tdmv]').forEach(el =>
    el.addEventListener('dragstart', e => { drag = el.dataset.tdmv; e.stopPropagation(); }));
  document.querySelectorAll('#screen-today .tdwday[data-tdday]').forEach(cell => {
    cell.addEventListener('dragover', e => { if (drag) { e.preventDefault(); cell.classList.add('dropinto'); } });
    cell.addEventListener('dragleave', () => cell.classList.remove('dropinto'));
    cell.addEventListener('drop', async e => {
      e.preventDefault(); clear();
      if (!drag) return;
      const [type, id] = drag.split(':'); drag = null;
      const date = cell.dataset.tdday;
      const req = {
        task: [`/api/nodes/${id}`, { due_date: date }],
        event: [`/api/events/${id}`, { date }],
        step: [`/api/fin/steps/${id}`, { planned_date: date }],
        money: [`/api/fin/obligations/${id}`, { next_date: date }],
      }[type];
      if (!req) return;
      const r = await fetch(req[0], { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req[1]) }).then(x => x.json()).catch(() => ({}));
      if (r?.error) alert(r.error);
      window.loadToday();
    });
    cell.addEventListener('dragend', clear);
  });
}

function bindToday() {
  bindTdWeek();
  document.querySelectorAll('#screen-today [data-sphopen]').forEach(el =>
    el.addEventListener('click', () => window.openSphere?.(+el.dataset.sphopen)));
  // Фокус дня: drag&drop вех для ручного приоритета (порядок сохраняется в настройке focus_order — синхронится между устройствами)
  let tdDragM = null;
  document.querySelectorAll('#screen-today .tdfoc[data-mid]').forEach(el => {
    el.addEventListener('dragstart', e => { tdDragM = +el.dataset.mid; e.dataTransfer.effectAllowed = 'move'; });
    el.addEventListener('dragover', e => {
      if (tdDragM == null || +el.dataset.mid === tdDragM) return;
      e.preventDefault();
      const r = el.getBoundingClientRect(), after = (e.clientY - r.top) / r.height > 0.5;
      el.classList.remove('dropbefore', 'dropafter'); el.classList.add(after ? 'dropafter' : 'dropbefore');
    });
    el.addEventListener('dragleave', () => el.classList.remove('dropbefore', 'dropafter'));
    el.addEventListener('drop', async e => {
      e.preventDefault();
      const after = el.classList.contains('dropafter'), target = +el.dataset.mid;
      el.classList.remove('dropbefore', 'dropafter');
      if (tdDragM == null || tdDragM === target) { tdDragM = null; return; }
      const ids = [...document.querySelectorAll('#screen-today .tdfoc[data-mid]')].map(x => +x.dataset.mid).filter(id => id !== tdDragM);
      ids.splice(ids.indexOf(target) + (after ? 1 : 0), 0, tdDragM);
      tdDragM = null;
      await tdApi.setSetting('focus_order', ids.join(','));
      window.loadToday();
    });
    el.addEventListener('dragend', () => { el.classList.remove('dropbefore', 'dropafter'); tdDragM = null; });
  });
  // отдых/восстановление
  const restAdd = async () => {
    const inp = document.getElementById('tdRestInput'); const text = inp?.value.trim(); if (!text) return;
    const mins = parseInt(document.getElementById('tdRestMins')?.value, 10);
    await fetch('/api/rest', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, scope: document.getElementById('tdRestScope').value,
        kind: document.getElementById('tdRestKind')?.value || 'restore',
        mins: Number.isFinite(mins) ? mins : null }) });
    window.loadToday();
  };
  document.getElementById('tdRestAdd')?.addEventListener('click', restAdd);
  document.getElementById('tdRestInput')?.addEventListener('keydown', e => { if (e.key === 'Enter') restAdd(); });
  document.querySelectorAll('#screen-today [data-restdel]').forEach(el =>
    el.addEventListener('click', async () => { await fetch('/api/rest/' + el.dataset.restdel, { method: 'DELETE' }); window.loadToday(); }));
  const restPatch = async (id, body) => {
    await fetch('/api/rest/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    window.loadToday();
  };
  document.querySelectorAll('#screen-today [data-restkind]').forEach(el =>
    el.addEventListener('click', () => {
      const [id, kind] = el.dataset.restkind.split(':');
      const i = REST_KINDS.findIndex(k => k[0] === kind);
      restPatch(id, { kind: REST_KINDS[(i + 1) % REST_KINDS.length][0] });
    }));
  document.querySelectorAll('#screen-today [data-restscope]').forEach(el =>
    el.addEventListener('click', () => {
      const [id, scope] = el.dataset.restscope.split(':');
      const next = { weekday: 'weekend', weekend: 'global', global: 'weekday' }[scope] || 'weekday';
      restPatch(id, { scope: next });
    }));
  document.querySelectorAll('#screen-today [data-restdone]').forEach(el =>
    el.addEventListener('click', async () => {
      await fetch('/api/rest/' + el.dataset.restdone + '/done', { method: 'POST' });
      window.loadToday();
    }));
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
  document.querySelectorAll('#screen-today [data-obpay]').forEach(el =>
    el.addEventListener('click', async () => {   // оплачено — сдвинуть дату на следующий период (или снять, если разовое)
      await fetch('/api/fin/obligations/' + el.dataset.obpay + '/pay', { method: 'POST' });
      window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-obdate]').forEach(el =>
    el.addEventListener('click', async e => {
      e.stopPropagation();
      const cur = (el.textContent.trim().match(/^\d{4}-\d{2}-\d{2}/) || [null])[0];
      const curTime = /^\d{2}:\d{2}$/.test(el.dataset.obtime || '') ? el.dataset.obtime : '';
      const v = await window.pickDate(cur, { title: 'Дата и время платежа', withTime: true, time: curTime });
      if (v === undefined) return;
      const body = { next_date: v.date || null, due_time: v.date ? (v.time || null) : null };  // время без даты не имеет смысла
      await fetch('/api/fin/obligations/' + el.dataset.obdate, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      window.loadToday();
    }));
  document.querySelectorAll('#screen-today [data-tdopen-ob]').forEach(el =>
    el.addEventListener('click', () => showScreen('fin')));
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
  // быстрый ввод: Enter или кнопка ＋. Указана дата → задача со сроком (видна в «Задачи на сегодня»/календаре); пусто → в Инбокс
  const tdQuickCreate = async () => {
    const inp = document.getElementById('tdQuick'); const title = inp?.value.trim(); if (!title) return;
    const date = document.getElementById('tdQuickDate')?.value || '';
    const time = document.getElementById('tdQuickTime')?.value || '';
    const node = await tdApi.add({ title, parent_id: tdData.inboxId }).then(r => r.json()).catch(() => null);
    if (date && node && node.id) {   // время без даты не имеет смысла → шлём срок только при выбранной дате
      await fetch('/api/nodes/' + node.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'task', due_date: date, due_time: time || null }) });
    }
    window.loadToday();
  };
  document.getElementById('tdQuick')?.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target.value.trim()) tdQuickCreate(); });
  document.getElementById('tdQuickAdd')?.addEventListener('click', tdQuickCreate);
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

/* Сферы — экран поверх реальных данных Pipboy.
   Сфера = сектор Колеса. Привязка у источника (экран «🏷 привязка»): тег на
   категории Целей / странице Инфо / рутине, вложенные наследуют; Психология/
   Трекинг/Финансы/Люди — по дефолту секции (авто). area_id через /api/spheres/assign. */

let sphData = null, sphPool = null, sphOpen = null, sphTag = false, sphTagData = null;
const sesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SPH_COL = ['#1e9e57', '#c43f3f', '#a87708', '#6b4fb5', '#2a76b5', '#364656'];
const SPH_KIND = { task: ['задача', 'ok'], decision: ['решение', 'dec'], question: ['вопрос', 'p2'], principle: ['принцип', 'p1'], idea: ['идея', ''], worry: ['тревога', 'p0'] };
const colOf = i => SPH_COL[i % SPH_COL.length];
// дни от сегодня до даты ISO (yyyy-mm-dd); null если не дата
const sphDaysTo = iso => { if (!iso) return null; const d = new Date(iso + 'T00:00:00'); return isNaN(d) ? null : Math.round((d - new Date(new Date().toDateString())) / 864e5); };
// бейдж дедлайна: просрочено / горит (≤3д) / скоро (≤14д); иначе просто дата
function sphDue(iso) {
  const days = sphDaysTo(iso);
  if (days == null) return iso ? `<span class="meta">${sesc(iso)}</span>` : '';
  if (days < 0) return `<span class="sphb fire">просрочено ${-days}д</span>`;
  if (days === 0) return `<span class="sphb fire">сегодня</span>`;
  if (days <= 3) return `<span class="sphb fire">${days}д</span>`;
  if (days <= 14) return `<span class="sphb soon">${sesc(iso)} · ${days}д</span>`;
  return `<span class="meta">${sesc(iso)}</span>`;
}
// статус контакта по ритму: пора / скоро / норм
function sphContact(p) {
  const since = sphDaysTo(p.last) != null ? -sphDaysTo(p.last) : null;   // дней назад
  if (!p.rhythm) return p.last ? `<span class="meta">${since}д назад</span>` : '<span class="meta">нет контакта</span>';
  if (since == null) return `<span class="sphb soon">ритм ${p.rhythm}д · нет контакта</span>`;
  const over = since - p.rhythm;
  if (over >= 0) return `<span class="sphb fire">пора · ${since}д назад</span>`;
  if (over >= -2) return `<span class="sphb soon">скоро · ${since}/${p.rhythm}д</span>`;
  return `<span class="meta">${since}д назад · ритм ${p.rhythm}д</span>`;
}

const sphApi = {
  load: () => fetch('/api/spheres').then(r => r.json()),
  pool: () => fetch('/api/spheres/pool').then(r => r.json()),
  tagpool: () => fetch('/api/spheres/tagpool').then(r => r.json()),
  assign: (kind, id, areaId) => fetch('/api/spheres/assign', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, id, areaId }) }),
  score: (id, n) => fetch('/api/psy/wheel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scores: { [id]: n } }) }),
  patch: (id, b) => fetch('/api/psy/areas/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  stepTask: id => fetch('/api/psy/areas/' + id + '/task', { method: 'POST' }),
  toggle: id => fetch('/api/nodes/' + id + '/toggle', { method: 'POST' }),
  setDef: (kind, areaId) => fetch('/api/spheres/default', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, areaId }) }),
  msAdd: (areaId, level, title) => fetch('/api/spheres/milestone', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ areaId, level, title }) }),
  msPatch: (id, b) => fetch('/api/spheres/milestone/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  msDel: id => fetch('/api/spheres/milestone/' + id, { method: 'DELETE' }),
  // метрики: ввод значения (без date → сервер сам берёт ключ периода) и создание (вернёт {id})
  mVal: (id, value, date) => fetch('/api/track/metrics/' + id + '/value', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(date ? { value, date } : { value }) }),
  mAdd: b => fetch('/api/track/metrics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  mDel: id => fetch('/api/track/metrics/' + id, { method: 'DELETE' }),
  // FAQ сферы: вопрос→ответ
  qAdd: (areaId, question, answer) => fetch('/api/spheres/question', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ areaId, question, answer }) }).then(r => r.json()),
  qPatch: (id, b) => fetch('/api/spheres/question/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  qDel: id => fetch('/api/spheres/question/' + id, { method: 'DELETE' }),
  qReorder: (id, ref, where) => fetch('/api/spheres/question/' + id + '/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ref, where }) }),
  // создание задачи (вернёт ноду с id) — для «вопрос → задача»
  nodeAdd: b => fetch('/api/nodes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
};

function sphRing(score, col, size = 48) {
  const r = size / 2 - 4, C = 2 * Math.PI * r, sc = score ?? 0;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#eef0f4" stroke-width="5"/><circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${col}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${C * sc / 10} ${C}" transform="rotate(-90 ${size / 2} ${size / 2})"/><text x="${size / 2}" y="${size / 2 + 5}" text-anchor="middle" style="font:700 ${size * .32}px var(--mono);fill:var(--text)">${score ?? '–'}</text></svg>`;
}
function sphSpark(vals, w = 74, h = 18) {
  if (!vals || vals.length < 2) return '<span class="muted" style="font-size:11px">мало данных</span>';
  const p = 2, mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const pts = vals.map((v, i) => [p + i * (w - 2 * p) / (vals.length - 1), h - p - ((v - mn) / rng) * (h - 2 * p)]);
  return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline fill="none" stroke="#5cb585" stroke-width="1.6" points="${pts.map(p => p.join(',')).join(' ')}"/><circle cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="2.2" fill="#1e9e57"/></svg>`;
}

window.loadSpheres = async function () {
  ensureSphStyle();
  // два эндпоинта независимо: падение пула (селекторы сфер) не должно убивать обзор сфер
  let pErr = '';
  try { sphData = await sphApi.load(); } catch (e) { sphData = { error: 'сеть: ' + (e && e.message || e) }; }
  try { sphPool = await sphApi.pool(); } catch (e) { sphPool = null; pErr = String(e && e.message || e); }
  if (sphPool?.areas?.length) { window.SPH_AREAS = sphPool.areas; window.refreshSphSelects?.(); }
  if (!Array.isArray(sphData)) {   // бэкенд вернул ошибку вместо списка — показываем настоящую причину
    const msg = (sphData && sphData.error) ? sphData.error : (pErr || 'не удалось загрузить сферы');
    document.getElementById('screen-spheres').innerHTML =
      `<h2>Сферы жизни</h2><div class="card" style="margin-top:12px"><div class="muted">Не удалось собрать сферы: ${sesc(String(msg))}</div></div>`;
    return;
  }
  try { renderSpheres(); }
  catch (e) {   // ошибка отрисовки не должна оставлять белый экран — показываем причину
    document.getElementById('screen-spheres').innerHTML =
      `<h2>Сферы жизни</h2><div class="card" style="margin-top:12px"><div class="muted">Сферы не отрисовались: ${sesc(String(e && e.message || e))}</div></div>`;
  }
};
// открыть конкретную сферу из «Сегодня» (полоса сфер) — без отдельной загрузки
window.openSphere = function (id) { sphOpen = id; showScreen('spheres'); };

// ---- Инлайн-привязка к сфере прямо в Целях/Инфо: общий <select> + делегированный обработчик ----
(() => { const st = document.createElement('style'); st.textContent =
  '.sphsel{font:11px var(--sans);border:1px solid var(--line);border-radius:6px;padding:2px 4px;background:var(--bg);color:var(--muted);max-width:140px;flex:0 0 auto}.sphsel:focus{outline:none;border-color:var(--green-dim)}';
  document.head.appendChild(st); })();
window.SPH_AREAS = [];
const sphOptions = areaId => `<option value="">· сфера</option>` +
  (window.SPH_AREAS || []).map(a => `<option value="${a.id}"${String(areaId ?? '') === String(a.id) ? ' selected' : ''}>${String(a.name).replace(/[<>&"]/g, '')}</option>`).join('');
window.sphSelHtml = (kind, id, areaId) =>
  `<select class="sphsel" data-sphsel="${kind}:${id}" data-area="${areaId ?? ''}" title="сфера жизни" onclick="event.stopPropagation()">${sphOptions(areaId)}</select>`;
// Дозаполнить уже отрисованные выпадашки (список сфер мог прийти позже их рендера)
window.refreshSphSelects = () => document.querySelectorAll('select.sphsel').forEach(sel => {
  const a = sel.dataset.area; sel.innerHTML = sphOptions(a === '' || a == null ? null : +a);
});
// Список сфер грузим лениво и с повтором: первый запрос мог уйти ДО разблокировки замка (401),
// тогда window.SPH_AREAS навсегда оставался пустым и в Целях/Инфо нечего было выбрать.
let sphAreasLoading = false;
window.ensureSphAreas = async force => {
  if ((window.SPH_AREAS.length && !force) || sphAreasLoading) return;
  sphAreasLoading = true;
  try {
    const p = await fetch('/api/spheres/pool').then(r => r.ok ? r.json() : null);
    if (p && Array.isArray(p.areas) && p.areas.length) { window.SPH_AREAS = p.areas; window.refreshSphSelects(); }
  } catch {}
  sphAreasLoading = false;
};
window.ensureSphAreas();
// Инлайн-выпадашки в Целях/Инфо могут появиться раньше, чем загрузились сферы — дозаполняем.
new MutationObserver(muts => {
  if (window.SPH_AREAS.length) return;   // уже есть — sphSelHtml отрисует сам
  for (const m of muts) for (const n of m.addedNodes) {
    if (n.nodeType === 1 && (n.matches?.('select.sphsel') || n.querySelector?.('select.sphsel'))) { window.ensureSphAreas(); return; }
  }
}).observe(document.body, { childList: true, subtree: true });
document.addEventListener('change', async e => {
  const sel = e.target.closest && e.target.closest('.sphsel'); if (!sel) return;
  const [kind, id] = sel.dataset.sphsel.split(':');
  sel.dataset.area = sel.value;   // запомнить выбор, чтобы пережить дозаполнение/ре-рендер
  await fetch('/api/spheres/assign', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, id: +id, areaId: sel.value ? +sel.value : null }) });
});

function renderSpheres() {
  const el = document.getElementById('screen-spheres');
  if (sphTag) { el.innerHTML = sphTagHub(); bindTagHub(); return; }
  if (sphOpen == null) { el.innerHTML = sphOverview(); bindOverview(); return; }
  const s = sphData.find(x => x.id === sphOpen);
  if (!s) { sphOpen = null; return renderSpheres(); }
  el.innerHTML = sphDetail(s, sphData.indexOf(s));
  bindDetail(s);
}

function sphOverview() {
  const scored = sphData.filter(s => s.score != null);
  const avg = scored.length ? (scored.reduce((a, s) => a + s.score, 0) / scored.length).toFixed(1) : '–';
  return `<h2 style="margin-bottom:2px">Сферы жизни</h2>
    <div class="muted" style="margin-bottom:8px">средний баланс ${avg}/10 · 10 = куда идём, оценка = где сейчас, шаг = что делаем. Всё на реальных данных.</div>
    <div class="card" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px">
      <span class="pill btn" id="sphTagBtn">🏷 привязка</span></div>
    <div class="sph-ov">${sphData.map((s, i) => {
      const links = s.routines.length + s.tracking.length + s.practices.length + s.fin.length + s.tasks.length;
      return `<div class="sph-card" data-open="${s.id}">
        <div class="sph-ct">${sphRing(s.score, colOf(i), 40)}<div class="sph-cn">${(typeof sphEmoji === 'function' && sphEmoji(s.name)) ? sphEmoji(s.name) + ' ' : ''}${sesc(s.name)}</div><div class="sph-cs" style="color:${colOf(i)}">${s.score ?? '–'}</div></div>
        <div class="sph-ideal">🎯 ${s.ideal ? sesc(s.ideal) : '<span class="muted">задать «10» — клик внутрь</span>'}</div>
        <div class="sph-step">→ ${s.step ? '<b>' + sesc(s.step) + '</b>' : '<span class="muted">нет шага</span>'}</div>
        <div class="sph-meta">🎯 ${s.tasks.filter(t => !t.cat).length} · ↻ ${s.routines.length} · 📊 ${s.tracking.length} · 🧠 ${s.practices.length} · 💰 ${s.fin.length}</div>
      </div>`;
    }).join('')}</div>`;
}
function bindOverview() {
  document.querySelectorAll('#screen-spheres [data-open]').forEach(c => c.onclick = () => { sphOpen = +c.dataset.open; renderSpheres(); });
  document.getElementById('sphTagBtn')?.addEventListener('click', async () => {
    sphTagData = await sphApi.tagpool(); sphTag = true; renderSpheres();
  });
}

// Хаб привязки: тегируем у источника. Дерево (категории целей, страницы Инфо) —
// тег наследуется вложенными; рутины — плоский список. Выпадашка = выбор сферы.
function tagTree(rows, kind, areas) {
  const byP = {}; rows.forEach(c => (byP[c.parent_id ?? 'root'] ??= []).push(c));
  const nameKey = rows[0] && 'title' in rows[0] ? 'title' : 'name';
  let out = '';
  const walk = (c, depth) => {
    out += `<div class="catrow" style="padding-left:${depth * 16}px">
      <span class="catt ${c.area_id != null ? 'on' : ''}">${depth ? '↳ ' : ''}${sesc(c[nameKey])}</span>
      <select data-tag="${kind}:${c.id}"><option value="">— наследует/нет</option>
        ${areas.map(a => `<option value="${a.id}" ${c.area_id === a.id ? 'selected' : ''}>${sesc(a.name)}</option>`).join('')}</select></div>`;
    (byP[c.id] || []).forEach(k => walk(k, depth + 1));
  };
  (byP['root'] || []).forEach(c => walk(c, 0));
  return out || '<div class="empty">пусто</div>';
}
function tagFlat(rows, kind, areas) {
  return rows.map(c => `<div class="catrow">
    <span class="catt ${c.area_id != null ? 'on' : ''}">${sesc(c.name)}</span>
    <select data-tag="${kind}:${c.id}"><option value="">— не задано</option>
      ${areas.map(a => `<option value="${a.id}" ${c.area_id === a.id ? 'selected' : ''}>${sesc(a.name)}</option>`).join('')}</select></div>`).join('') || '<div class="empty">пусто</div>';
}
function sphTagHub() {
  const t = sphTagData || {}, areas = t.areas || [];
  const dd = sphPool?.defaults || {};
  return `<div class="sph-crumb"><a id="sphBackTag">← Сферы</a> · <span class="pill btn" id="sphAutomapTag">🪄 авто по именам</span></div>
    <h2 style="margin-bottom:2px">Привязка к сферам</h2>
    <div class="muted" style="margin-bottom:6px">Тегируешь у источника, вложенные <b>наследуют</b> (можно переопределить). Названия/структуру не трогаем.</div>
    <div class="sec" style="margin-top:0">⚡ Секции целиком → сфера</div>
    <div class="card"><div class="muted" style="font-size:12px;margin-bottom:6px">Куда по умолчанию попадают Люди / Трекинг / Психология / Финансы. <b>Психология = практики (майндсет)</b> — выбери здесь свою сферу.</div>
      ${[['person', '☻ Люди'], ['metric', '📊 Трекинг'], ['practice', '🧠 Психология · практики'], ['obligation', '💰 Финансы']].map(([kind, label]) => `<div class="catrow">
        <span class="catt ${dd[kind] != null ? 'on' : ''}">${label}</span>
        <select data-secdef="${kind}"><option value="">— не задано</option>${areas.map(a => `<option value="${a.id}" ${dd[kind] === a.id ? 'selected' : ''}>${sesc(a.name)}</option>`).join('')}</select></div>`).join('')}</div>
    <div class="sec">🎯 Цели · категории (разделы и подразделы)</div>
    <div class="card">${tagTree(t.categories || [], 'category', areas)}</div>
    <div class="sec">📒 Инфо · страницы и разделы</div>
    <div class="card">${tagTree(t.pages || [], 'page', areas)}</div>
    <div class="sec">↻ Рутины · по одной (бывают разные)</div>
    <div class="card">${tagFlat(t.routines || [], 'routine', areas)}</div>
    <div class="sec">📅 События · по одному</div>
    <div class="card">${tagFlat(t.events || [], 'event', areas)}</div>
    <div class="sec">💰 Долги · по умолчанию → деньги, можно переопределить</div>
    <div class="card">${tagFlat(t.debts || [], 'debt', areas)}</div>
    <div class="sec">🪜 План шагов</div>
    <div class="card">${tagFlat(t.steps || [], 'step', areas)}</div>`;
}
function bindTagHub() {
  document.getElementById('sphBackTag').onclick = () => { sphTag = false; renderSpheres(); };
  document.getElementById('sphAutomapTag').onclick = async () => {
    const r = await fetch('/api/spheres/automap', { method: 'POST' }).then(x => x.json());
    alert(`Разложено категорий целей по именам сфер: ${r.mapped}`);
    sphTagData = await sphApi.tagpool(); renderSpheres();
  };
  document.querySelectorAll('#screen-spheres [data-tag]').forEach(sel => sel.onchange = async () => {
    const [kind, id] = sel.dataset.tag.split(':');
    await sphApi.assign(kind, +id, sel.value ? +sel.value : null);
    sphTagData = await sphApi.tagpool(); sphData = await sphApi.load(); renderSpheres();
  });
  // секция целиком → сфера (Психология=практики/майндсет, Трекинг, Люди, Финансы)
  document.querySelectorAll('#screen-spheres [data-secdef]').forEach(sel => sel.onchange = async () => {
    await sphApi.setDef(sel.dataset.secdef, sel.value ? +sel.value : null);
    [sphPool, sphData] = await Promise.all([sphApi.pool(), sphApi.load()]);
    renderSpheres();
  });
}

function block(label, jump, inner) {
  return `<div class="sec">${label} <span class="muted" style="font-weight:400">· ${jump}</span></div><div class="card">${inner}</div>`;
}

// строка пула рутины/практики: имя + прогресс-бар % за месяц + подпись «мес/год»
function sphPoolRow(it) {
  const mp = Math.max(0, Math.min(100, it.monthPct ?? 0)), yp = Math.max(0, Math.min(100, it.yearPct ?? 0));
  return `<div class="sphpool">
    <span class="sphpool-n">${sesc(it.name)}${it.doneToday ? ' <span class="sphpool-today">сегодня ✓</span>' : ''}${it.streak ? ` <span class="sphpool-st">🔥${it.streak}</span>` : ''}</span>
    <span class="sphpool-bar" title="месяц ${mp}% · год ${yp}%"><b style="width:${yp}%"></b><i style="width:${mp}%"></i></span>
    <span class="sphpool-p">${mp}<small>%мес</small> · ${yp}<small>%год</small></span>
  </div>`;
}
// трекинг-метрика пулом: ввод значения за текущий период прямо тут.
// bool → галочка «выполнил»; number/scale → клик-ввод; счётчик (computed) → read-only авто.
const CAD_TAG = { daily: 'день', weekly: 'неделя', monthly: 'месяц' };
function sphTrackPool(m) {
  const neg = m.polarity === 'minus';
  const s = Array.isArray(m.s) ? m.s : [];
  const trend = s.length >= 2 ? (s[s.length - 1] - s[0]) : 0;
  const good = neg ? trend < 0 : trend > 0;               // для негатива «вниз» — хорошо
  const arrow = trend === 0 ? '·' : (trend > 0 ? '▲' : '▼');
  const tcls = trend === 0 ? '' : (good ? 'up' : 'down');
  const computed = !!m.computed, cad = CAD_TAG[m.cadence] || 'день';
  const cur = (m.cur === null || m.cur === undefined) ? null : m.cur;
  const pct = (m.target != null && m.target && m.v != null) ? Math.round(m.v / m.target * 100) : null;
  const bar = pct != null
    ? `<span class="sphpool-bar ${neg ? 'neg' : ''}"><i style="width:${Math.max(0, Math.min(100, pct))}%"></i></span>`
    : `<span class="sphpool-spark">${s.length > 1 ? sphSpark(s, 84, 14) : '<span class="muted" style="font-size:11px">нет данных</span>'}</span>`;
  let ctl;
  if (computed) {
    ctl = `<span class="sphpool-p"><span class="sphtrend ${tcls}">${arrow}</span> ${m.v ?? 0}<small> авто</small></span>`;
  } else if (m.type === 'bool') {
    const on = cur != null && cur > 0;
    ctl = `<span class="pill btn ${on ? 'ok' : ''}" data-sphmcheck="${m.id}:${on ? 1 : 0}" title="отметить за ${cad}">${on ? 'выполнил ✓' : 'отметить'}</span>`;
  } else {
    ctl = `<span class="sphpool-p" data-sphmval="${m.id}" style="cursor:pointer" title="ввести за ${cad}"><span class="sphtrend ${tcls}">${arrow}</span> ${cur ?? (m.v ?? '–')}<small>${sesc(m.unit)}</small>${pct != null ? ` · ${pct}%` : ''} ✎</span>`;
  }
  return `<div class="sphpool ${neg ? 'neg' : ''}">
    <span class="sphpool-n">${sesc(m.name)} <span class="sphpool-st">${cad}</span>${computed ? ' <span class="sphpool-st">счётчик</span>' : ''}${neg ? ' <span class="sphpool-neg">негатив</span>' : ''}</span>
    ${bar}
    ${ctl}
    <span class="rowbtn del" data-sphmdel="${m.id}:${sesc(m.name)}" title="удалить метрику со всеми записями">✕</span>
  </div>`;
}
// универсальная KPI-плитка: иконка+имя, крупное значение, опц. полоса %, подпись
function sphTile(icon, name, big, sub, pct, cls = '') {
  const bar = pct != null ? `<div class="sphk-bar"><i style="width:${Math.max(0, Math.min(100, pct))}%"></i></div>` : '';
  return `<div class="sphk"><div class="sphk-n">${icon} ${sesc(name)}</div><div class="sphk-v">${big}</div>${bar}${sub ? `<div class="sphk-p ${cls}">${sub}</div>` : ''}</div>`;
}
// KPI-плитка метрики: % к цели (или спарклайн, если цели нет)
function sphKpiTile(m) {
  const pct = (m.target != null && m.target && m.v != null) ? Math.round(m.v / m.target * 100) : null;
  const sub = pct != null
    ? `<div class="sphk-bar"><i style="width:${Math.max(0, Math.min(100, pct))}%"></i></div><div class="sphk-p">${pct}% → ${m.target}${sesc(m.unit)}</div>`
    : `<div class="sphk-p">${m.s && m.s.length > 1 ? sphSpark(m.s, 72, 16) : '<span class="muted">задай цель 🎯</span>'}</div>`;
  return `<div class="sphk"><div class="sphk-n">📊 ${sesc(m.name)}</div><div class="sphk-v">${m.v ?? '–'}<small>${sesc(m.unit)}</small></div>${sub}</div>`;
}
// финансовые авто-сигналы (только денежная сфера) — из реальных чисел Финансов
function sphFinTiles(f) {
  const money = n => n == null ? '–' : Math.round(n).toLocaleString('ru-RU');
  const t = [];
  t.push(sphTile('💰', f.fireTarget ? 'Капитал → FIRE' : 'Капитал', `€${money(f.capital)}`,
    f.fireTarget ? `${(f.firePct ?? 0).toFixed(0)}% от €${money(f.fireTarget)}` : '', f.fireTarget ? f.firePct : null));
  if (f.yieldPct != null) t.push(sphTile('📈', 'Доходность', `${f.yieldPct >= 0 ? '+' : ''}${f.yieldPct.toFixed(1)}%`, 'на вложенное', null, f.yieldPct >= 0 ? 'up' : 'down'));
  if (f.firePct != null) t.push(sphTile('🔥', 'FIRE прогресс', `${f.firePct.toFixed(0)}<small>%</small>`, f.fireYear ? `к ~${f.fireYear}` : '', f.firePct));
  t.push(sphTile('💸', 'Расход / бюджет', `€${money(f.expense)}`, f.budget ? `из €${money(f.budget)}` : '', f.budget ? Math.round(f.expense / f.budget * 100) : null));
  if (f.income) t.push(sphTile('🪙', 'Пассивный доход', `€${money(f.income)}`, 'в месяц'));
  return t.join('');
}
// движковые авто-сигналы для ЛЮБОЙ сферы — из того, что и так считается
function sphEngineTiles(s) {
  const pr = s.progress || {}, t = [];
  if (pr.tasksTotal) { const p = Math.round(pr.tasksDone / pr.tasksTotal * 100); t.push(sphTile('🎯', 'Задачи', `${p}<small>%</small>`, `${pr.tasksDone}/${pr.tasksTotal}`, p)); }
  if (typeof pr.adherence === 'number') { const p = Math.round(pr.adherence * 100); t.push(sphTile('↻', 'Рутины · 2 нед', `${p}<small>%</small>`, 'дисциплина', p)); }
  // психология / майндсет: дисциплина практик за 7 дней (из недельных полос)
  if (s.practices && s.practices.length) {
    const hits = s.practices.reduce((a, p) => a + (p.wk || []).reduce((x, d) => x + (d ? 1 : 0), 0), 0);
    const max = s.practices.length * 7, p = max ? Math.round(hits / max * 100) : 0;
    t.push(sphTile('🧠', 'Практики · 7 дн', `${p}<small>%</small>`, 'майндсет', p));
  }
  return t.join('');
}
// «Путь к 10»: каждая веха — самостоятельная цель со своим прогрессом 0→10.
// Жмёшь +1 при действии по ней; на 10 закрывается (зачёркивается). Создавать можно сколько угодно.
function sphRoadmap(s) {
  const ms = (s.milestones || []).slice();   // в порядке добавления
  const done = ms.filter(m => (m.progress ?? 0) >= 10).length;
  const rows = ms.map(m => {
    const p = Math.max(0, Math.min(10, m.progress ?? 0)), isDone = p >= 10;
    return `<div class="sph-rm ${isDone ? 'done' : ''}">
      <span class="sph-rk">${p}/10</span>
      <span class="pbar2 sph-rmbar"><i style="width:${p * 10}%"></i></span>
      <span class="sph-rt" data-msedit="${m.id}" title="клик — переименовать">${m.title ? sesc(m.title) : '<span class="muted">без названия</span>'}</span>
      <span class="rowbtn" data-mspin="${m.id}:${m.pinned ? 1 : 0}" title="${m.pinned ? 'закреплена на «Сегодня» — снять' : 'закрепить на «Сегодня»'}" style="${m.pinned ? 'color:var(--amber);opacity:1' : ''}">${m.pinned ? '★' : '☆'}</span>
      ${isDone ? '<span style="color:var(--green-dim);font-size:12px">✓ закрыта</span>'
        : `<span class="pill btn ok" data-msinc="${m.id}:${p}" title="+1 к прогрессу">+1</span>`}
      ${p > 0 ? `<span class="rowbtn" data-msdec="${m.id}:${p}" title="−1">−</span>` : ''}
      <span class="rowbtn del" data-msdel="${m.id}">✕</span>
    </div>`;
  }).join('');
  const head = ms.length ? `<div class="task" style="border:0;padding:2px 0"><span class="t muted" style="font-size:12px">закрыто ${done}/${ms.length} вех</span></div>` : '';
  return block('🗺 Путь к 10 · вехи-цели', 'каждая со своим прогрессом',
    head + (rows || '<div class="empty">добавь цели-вехи маршрута ↓</div>')
    + `<div class="task finadd"><input class="sphmsadd" data-msadd="${s.id}" placeholder="＋ веха-цель: «накопить €500к», «выучить C2»… · Enter"></div>`);
}

// FAQ сферы: вопрос→ответ (сворачивается); из вопроса — «→ задача» / «→ метрика».
function sphFaq(s) {
  const qs = s.questions || [];
  const rows = qs.map((q, i) => {
    const ans = q.answer ? sesc(q.answer).replace(/\n/g, '<br>') : '<span class="muted">нет ответа — клик, чтобы добавить</span>';
    const taskBadge = q.node_id
      ? `<span class="pill btn ${q.node_status === 'done' ? 'ok' : 'p2'}" data-qopen="${q.node_id}" title="открыть задачу">${q.node_status === 'done' ? '✓ задача' : '🎯 задача'}</span>`
      : `<span class="rowbtn" data-qtask="${q.id}" title="сделать задачу из вопроса">→ задача</span>`;
    const metricBadge = q.metric_id
      ? '<span class="pill">📊 метрика</span>'
      : `<span class="rowbtn" data-qmetric="${q.id}" title="сделать метрику из вопроса">→ метрика</span>`;
    return `<div class="sph-faq" draggable="true" data-qid="${q.id}">
      <div class="sph-faqq"><span class="sph-faqnum" title="перетащи, чтобы переместить">⠿ ${i + 1}.</span><span class="sph-faqt" data-qedit="${q.id}" title="клик — изменить вопрос">${q.question ? sesc(q.question) : '<span class="muted">без вопроса</span>'}</span>
        ${taskBadge}${metricBadge}<span class="rowbtn del" data-qdel="${q.id}">✕</span></div>
      <div class="sph-faqa" data-qans="${q.id}" title="клик — изменить ответ">${ans}</div>
    </div>`;
  }).join('');
  return block('🧩 Вопросы сферы', 'рефлексия → действие',
    (rows || '<div class="empty">сформулируй ключевые вопросы сферы ↓</div>')
    + `<div class="task finadd"><input class="sphqadd" data-qadd="${s.id}" placeholder="＋ вопрос сферы… · Enter"></div>`);
}

function sphDetail(s, i) {
  const col = colOf(i);
  let h = `<div class="sph-crumb"><a id="sphBack">← Сферы</a></div>
    <div class="sph-hero">
      <div class="sph-hs">${sphRing(s.score, col, 70)}<div style="margin-top:4px">${sphSpark(s.history)}</div></div>
      <div class="sph-hi"><h2 style="margin:0 0 2px">${sesc(s.name)}</h2>
        <div class="muted" style="font-size:12px">путь к 10 · ступень за ступенью (клик по строке — правка)</div></div>
    </div>
    <div class="sph-track"><div class="sph-rail"></div><div class="sph-fill" style="width:${(s.score ?? 0) * 10}%;background:${col}"></div>
      <div class="sph-you" style="left:${(s.score ?? 0) * 10}%">${s.score ?? '–'}</div><span class="sph-z">0</span><span class="sph-t10">10 ✦</span></div>
    <div class="card sph-ladder">
      <div class="sph-rung" data-edit="ideal"><span class="sph-rl">🎯 10 — идеал</span><span class="sph-rv">${s.ideal ? sesc(s.ideal) : '<span class="muted">каким будет «10» (клик)</span>'}</span></div>
      <div class="sph-rung" data-edit="current_desc"><span class="sph-rl">📍 сейчас (${s.score ?? '?'})</span><span class="sph-rv">${s.current_desc ? sesc(s.current_desc) : '<span class="muted">почему такая оценка (клик)</span>'}</span></div>
      <div class="sph-rung" data-edit="next_desc"><span class="sph-rl">⬆️ +1 — что хотим</span><span class="sph-rv">${s.next_desc ? sesc(s.next_desc) : '<span class="muted">как выглядит следующая ступень (клик)</span>'}</span></div>
      <div class="sph-rung step" data-edit="step"><span class="sph-rl">👉 шаг к +1</span><span class="sph-rv">${s.step ? '<b>' + sesc(s.step) + '</b>' : '<span class="muted">конкретный шаг (клик)</span>'}</span></div>
    </div>
    <div style="margin:7px 0 2px"><span class="pill btn" id="sphStepTask">＋ шаг в задачи</span> <span class="muted" style="font-size:12px">шаги для +1 ведёшь задачами и трекингом ниже ↓</span></div>`;

  // 🔑 Ключевые сигналы: финансы (авто, деньги) + движок (моментум/задачи/рутины) + метрики с целями
  let kpi = '';
  if (s.finance) kpi += sphFinTiles(s.finance);
  kpi += sphEngineTiles(s);
  // в шапке — только метрики С ЦЕЛЬЮ (краткий итог), остальной трекинг остаётся блоком ниже
  const kpiMetrics = (s.tracking || []).filter(m => m.target != null && m.target);
  if (kpiMetrics.length) kpi += kpiMetrics.map(sphKpiTile).join('');
  if (kpi) h += `<div class="sec">🔑 Ключевые сигналы <span class="muted" style="font-weight:400">· авто из данных${kpiMetrics.length ? ' + цели метрик' : ''}</span></div><div class="card"><div class="sphkpi">${kpi}</div></div>`;
  // путь к 10 — дорожная карта вехами (редактируется прямо тут)
  h += sphRoadmap(s);
  h += sphFaq(s);

  // задачи сферы — с вложенностью, как в Целях; сворачиваемые (по умолчанию свёрнуто),
  // состояние сохраняется; работаем прямо тут (Сферы = рабочий раздел)
  const rootCat = (s.tasks.find(t => t.cat && t.depth === 0) || {}).id;
  const T = s.tasks;
  const expanded = new Set(JSON.parse(localStorage.sphFold || '[]'));
  const hasKids = new Set();
  for (let i = 0; i < T.length; i++) if (T[i + 1] && T[i + 1].depth > T[i].depth) hasKids.add(T[i].id);   // ЛЮБОЙ узел с детьми
  let rows = '', hide = Infinity;
  for (const t of T) {
    if (t.depth > hide) continue;          // внутри свёрнутой ветки — пропускаем
    hide = Infinity;
    const kids = hasKids.has(t.id), col = kids && !expanded.has(t.id);
    const caret = kids ? `<span class="caret" data-sphfold="${t.id}">${col ? '▸' : '▾'}</span>` : '<span class="caret"></span>';
    if (t.cat) {
      rows += `<div class="task sphcat" style="padding-left:${t.depth * 16}px">
        ${caret}<b class="t">${sesc(t.title)}</b>
        <span class="rowbtn" data-addtask="${t.id}" title="задача сюда">＋</span>
        <span class="rowbtn" data-addcat="${t.id}" title="подкатегория">⊞</span></div>`;
    } else {
      // формат как в Целях: каретка (если есть подпункты), маркер по типу, приоритет, заголовок + заметка
      const done = t.status === 'done' || t.status === 'accepted';
      const [kl, kc] = t.kind ? (SPH_KIND[t.kind] ?? [t.kind, '']) : [null, null];
      const marker = !t.kind ? '<span class="bullet">•</span>'
        : (t.kind === 'task' || t.kind === 'decision') ? `<span class="cb ${t.kind === 'decision' ? 'dec' : ''} ${done ? 'done' : ''}" data-tog="${t.id}"></span>`
          : `<span class="pill ${kc}">${kl}</span>`;
      rows += `<div class="task" style="padding-left:${t.depth * 16}px">${caret}${marker}
        ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
        ${(t.kind === 'task' || t.kind === 'decision') ? `<span class="pill ${kc}">${kl}</span>` : ''}
        <span class="t ${done ? 'done' : ''}" data-tnode="${t.id}">${sesc(t.title)}${t.note ? `<div class="noteblock">${sesc(t.note)}</div>` : ''}</span>
        ${t.answer ? `<span class="meta">→ ${sesc(t.answer)}</span>` : ''}
        ${t.due ? sphDue(t.due) : ''}
        <span class="rowbtn" data-pri="${t.id}:${t.priority || ''}" title="приоритет">⚑</span>
        <span class="rowbtn" data-due="${t.id}" title="срок">📅</span>
        <span class="rowbtn del" data-del="${t.id}" title="удалить">✕</span></div>`;
    }
    if (col) hide = t.depth;          // свёрнут (категория ИЛИ пункт с подпунктами) — прячем потомков
  }
  h += block('🎯 Задачи сферы', 'Цели', rows
    + (rootCat
      ? `<div class="task finadd"><input class="sphadd" data-addroot="${rootCat}" placeholder="＋ задача в сферу (Enter)"></div>`
      : '<div class="empty">привяжи категорию целей в Целях — и заводи задачи прямо тут</div>'));

  // рутины — пул с прогресс-баром (% месяц/год), не числом
  if (s.routines.length) h += block('↻ Рутины · пул', 'Рутины', s.routines.map(sphPoolRow).join(''));
  // трекинг — пул (как рутины); негативные метрики красным, рост = плохо
  h += block('📊 Трекинг · пул', 'Трекинг',
    (s.tracking.length ? s.tracking.map(sphTrackPool).join('') : '<div class="empty">пока нет метрик ↓</div>')
    + `<div class="task finadd"><input class="sphmadd" data-sphmadd="${s.id}" placeholder="＋ метрика: «вес», «оценка тревоги»… · Enter"></div>`);
  // практики — пул с прогресс-баром (% месяц/год)
  if (s.practices.length) h += block('🧠 Практики · пул', 'Психология', s.practices.map(sphPoolRow).join(''));
  // люди (социализация)
  if (s.people && s.people.length) h += block('☻ Люди', 'Люди', s.people.map(p => `
    <div class="task"><span class="t">${sesc(p.name)}</span>${sphContact(p)}</div>`).join(''));
  // (финансовые числа теперь в шапке «🔑 Ключевые сигналы» — авто из Финансов)
  // платежи — делим по периодам с суммами (статистика «что платить мес/год/разово»)
  if (s.fin.length) {
    const money = n => Math.round(n).toLocaleString('ru-RU');
    const grp = { monthly: ['Ежемесячно', []], yearly: ['Ежегодно', []], once: ['Разово', []] };
    for (const f of s.fin) (grp[f.period] || (grp[f.period] = [f.period, []]))[1].push(f);
    let html = '';
    for (const [per, [label, items]] of Object.entries(grp)) {
      if (!items.length) continue;
      const sum = items.reduce((x, f) => x + (f.amount || 0), 0);
      html += `<div class="task sphcat"><b class="t">${label}</b><span class="meta num">Σ ${money(sum)} €</span></div>`
        + items.map(f => `<div class="task" style="padding-left:16px"><span class="t">${sesc(f.name)}</span>${sphDue(f.next_date)}<span class="meta num">${f.amount} ${sesc(f.currency)}</span></div>`).join('');
    }
    h += block('💰 Платежи · по периодам', 'Финансы', html);
  }
  // долги
  if (s.debts && s.debts.length) h += block('🤝 Долги', 'Финансы', s.debts.map(x => `
    <div class="task"><span class="pill ${x.direction === 'i_owe' ? 'p0' : 'ok'}">${x.direction === 'i_owe' ? 'я должен' : 'мне должны'}</span>
      <span class="t">${sesc(x.name)}</span>${sphDue(x.due_date)}<span class="meta num">${x.amount} ${sesc(x.currency)}</span></div>`).join(''));
  // план шагов
  if (s.steps && s.steps.length) h += block('🪜 План шагов', 'Финансы', s.steps.map(st => `
    <div class="task"><span class="pill ${st.kind === 'sell' ? 'p1' : 'ok'}">${({ buy: 'купить', sell: 'продать', transfer: 'перевод' })[st.kind] || st.kind}</span>
      <span class="t">${sesc(st.title)}</span>${sphDue(st.planned_date)}${st.amount ? `<span class="meta num">${st.amount}</span>` : ''}</div>`).join(''));
  // события
  if (s.events && s.events.length) h += block('📅 События сферы', 'Календарь', s.events.map(e => `
    <div class="task"><span class="t">${sesc(e.title)}${e.time ? ` <span class="meta">${e.time}</span>` : ''}</span>${sphDue(e.date)}</div>`).join(''));
  // инфо — кликабельно, открывает нужную страницу в Инфо
  if (s.info && s.info.length) h += block('📒 Инфо сферы', 'Инфо', s.info.map(p => `
    <div class="task"><span class="t" data-page="${p.id}" style="cursor:pointer">📄 ${sesc(p.title)}</span></div>`).join(''));

  // ревизия
  h += `<div class="sec">🪞 Ревизия · оценка сферы</div><div class="card">
    <div class="muted" style="font-size:13px;margin-bottom:4px">Где сектор сейчас? Оценка пишется в Колесо.</div>
    <div class="sph-scoreset" id="sphScore"></div></div>`;
  return h;
}

function bindDetail(s) {
  document.getElementById('sphBack').onclick = () => { sphOpen = null; renderSpheres(); };
  // оценка → Колесо
  const sc = document.getElementById('sphScore'); let cur = s.score ?? 0;
  sc.innerHTML = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(i => `<b class="${i <= cur ? 'on' : ''}" data-s="${i}">${i}</b>`).join('');
  sc.onclick = async e => { const b = e.target.closest('b'); if (!b) return; await sphApi.score(s.id, +b.dataset.s); window.loadSpheres(); };
  // правка полей сектора → wheel_areas
  document.querySelectorAll('#screen-spheres [data-edit]').forEach(el => el.onclick = async () => {
    const f = el.dataset.edit;
    const labels = { ideal: 'Идеал (каким будет «10»):', current_desc: 'Где сейчас — почему такая оценка:', next_desc: 'Что хотим сделать для +1 (следующий уровень):', step: 'Конкретный шаг к +1:' };
    const v = prompt(labels[f], s[f] || '');
    if (v != null) { await sphApi.patch(s.id, { [f]: v.trim() }); window.loadSpheres(); }
  });
  document.querySelectorAll('#screen-spheres [data-tog]').forEach(c => c.onclick = async () => { await sphApi.toggle(+c.dataset.tog); window.loadSpheres(); });
  // вехи «пути к 10»
  document.querySelectorAll('#screen-spheres [data-msedit]').forEach(el => el.onclick = async () => {
    const v = prompt('Текст вехи:', el.textContent.trim()); if (v == null) return;
    await sphApi.msPatch(+el.dataset.msedit, { title: v.trim() }); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-msdel]').forEach(el => el.onclick = async () => {
    if (confirm('Удалить веху?')) { await sphApi.msDel(+el.dataset.msdel); window.loadSpheres(); }
  });
  // +1 / −1 к прогрессу вехи (0→10; на 10 закрывается)
  document.querySelectorAll('#screen-spheres [data-msinc]').forEach(el => el.onclick = async () => {
    const [id, p] = el.dataset.msinc.split(':'); await sphApi.msPatch(+id, { progress: Math.min(10, +p + 1) }); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-msdec]').forEach(el => el.onclick = async () => {
    const [id, p] = el.dataset.msdec.split(':'); await sphApi.msPatch(+id, { progress: Math.max(0, +p - 1) }); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-mspin]').forEach(el => el.onclick = async () => {
    const [id, pin] = el.dataset.mspin.split(':'); await sphApi.msPatch(+id, { pinned: pin === '1' ? 0 : 1 }); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-msadd]').forEach(el => el.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !el.value.trim()) return;
    await sphApi.msAdd(+el.dataset.msadd, 5, el.value.trim());   // level не используется в прогресс-логике; прогресс стартует с 0
    window.loadSpheres();
  }));
  // ===== метрики прямо в сфере: галочка / ввод значения / создание =====
  document.querySelectorAll('#screen-spheres [data-sphmcheck]').forEach(el => el.onclick = async () => {
    const [id, cur] = el.dataset.sphmcheck.split(':');
    await sphApi.mVal(+id, cur === '1' ? 0 : 1);   // без date → сервер берёт ключ периода метрики
    window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-sphmval]').forEach(el => el.onclick = async () => {
    const v = prompt('Значение за период:'); if (v == null) return;
    const n = parseFloat(String(v).replace(',', '.')); if (isNaN(n)) return;
    await sphApi.mVal(+el.dataset.sphmval, n); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-sphmadd]').forEach(el => el.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !el.value.trim()) return;
    const name = el.value.trim();
    const t = prompt('Тип метрики: 1 — оценка 1–10, 2 — число, 3 — галочка, 4 — счётчик', '1'); if (t == null) return;
    const cad = ({ '1': 'daily', '2': 'weekly', '3': 'monthly' })[prompt('Частота: 1 — день, 2 — неделя (вс), 3 — месяц', '1')] || 'daily';
    const body = { name, cadence: cad };
    if (t === '4') {   // авто-счётчик: источник + период (по умолчанию месяц)
      body.type = 'number';
      body.source = ({ '1': 'milestones', '2': 'practices', '3': 'tasks', '4': 'routines' })[prompt('Считать: 1 — закрытые вехи, 2 — практики, 3 — задачи, 4 — рутины', '1')] || 'milestones';
      if (cad === 'daily') body.cadence = 'monthly';
    } else if (t === '3') { body.type = 'bool'; }
    else { body.type = t === '2' ? 'number' : 'scale'; if (body.type === 'number') body.unit = (prompt('Единица (кг, €, шт…):') || '').trim(); }
    const r = await sphApi.mAdd(body);
    if (r && r.id) await sphApi.assign('metric', r.id, +el.dataset.sphmadd);
    window.loadSpheres();
  }));
  document.querySelectorAll('#screen-spheres [data-sphmdel]').forEach(el => el.addEventListener('click', async () => {
    const [id, name] = el.dataset.sphmdel.split(':');
    if (!confirm(`Удалить метрику «${name}» вместе со всеми записями? Она исчезнет и из Трекера.`)) return;
    await sphApi.mDel(+id);
    window.loadSpheres();
  }));
  // ===== FAQ сферы: CRUD + «→ задача» / «→ метрика» =====
  document.querySelectorAll('#screen-spheres [data-qadd]').forEach(el => el.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !el.value.trim()) return;
    await sphApi.qAdd(+el.dataset.qadd, el.value.trim(), ''); window.loadSpheres();
  }));
  document.querySelectorAll('#screen-spheres [data-qedit]').forEach(el => el.onclick = async () => {
    const cur = el.textContent.trim(); const v = prompt('Вопрос:', cur === 'без вопроса' ? '' : cur); if (v == null) return;
    await sphApi.qPatch(+el.dataset.qedit, { question: v }); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-qans]').forEach(el => el.onclick = async () => {
    const q = (s.questions || []).find(x => x.id === +el.dataset.qans);
    const v = prompt('Ответ:', q && q.answer ? q.answer : ''); if (v == null) return;
    await sphApi.qPatch(+el.dataset.qans, { answer: v }); window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-qdel]').forEach(el => el.onclick = async () => {
    if (confirm('Удалить вопрос?')) { await sphApi.qDel(+el.dataset.qdel); window.loadSpheres(); }
  });
  // FAQ-вопросы: перетаскивание (drag&drop) для смены порядка
  let sphDragQ = null;
  document.querySelectorAll('#screen-spheres .sph-faq[data-qid]').forEach(el => {
    el.addEventListener('dragstart', e => { sphDragQ = +el.dataset.qid; e.dataTransfer.effectAllowed = 'move'; });
    el.addEventListener('dragover', e => {
      if (sphDragQ == null || +el.dataset.qid === sphDragQ) return;
      e.preventDefault();
      const r = el.getBoundingClientRect(), after = (e.clientY - r.top) / r.height > 0.5;
      el.classList.remove('dropbefore', 'dropafter'); el.classList.add(after ? 'dropafter' : 'dropbefore');
    });
    el.addEventListener('dragleave', () => el.classList.remove('dropbefore', 'dropafter'));
    el.addEventListener('drop', async e => {
      e.preventDefault();
      const after = el.classList.contains('dropafter'), target = +el.dataset.qid;
      el.classList.remove('dropbefore', 'dropafter');
      if (sphDragQ != null && sphDragQ !== target) { await sphApi.qReorder(sphDragQ, target, after ? 'after' : 'before'); window.loadSpheres(); }
      sphDragQ = null;
    });
    el.addEventListener('dragend', () => { el.classList.remove('dropbefore', 'dropafter'); sphDragQ = null; });
  });
  document.querySelectorAll('#screen-spheres [data-qopen]').forEach(el => el.onclick = () => { if (window.openNode) window.openNode(+el.dataset.qopen); });
  document.querySelectorAll('#screen-spheres [data-qtask]').forEach(el => el.onclick = async () => {
    const qid = +el.dataset.qtask, q = (s.questions || []).find(x => x.id === qid);
    const title = prompt('Задача из вопроса:', q ? q.question : ''); if (!title || !title.trim()) return;
    const n = await sphApi.nodeAdd({ title: title.trim() });
    if (n && n.id) {
      await fetch('/api/nodes/' + n.id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'task' }) });
      await sphApi.assign('category', n.id, s.id);   // area_id ставится только через assign (не PATCH)
      await sphApi.qPatch(qid, { node_id: n.id });
    }
    window.loadSpheres();
  });
  document.querySelectorAll('#screen-spheres [data-qmetric]').forEach(el => el.onclick = async () => {
    const qid = +el.dataset.qmetric, q = (s.questions || []).find(x => x.id === qid);
    const name = prompt('Метрика из вопроса:', q ? q.question : ''); if (!name || !name.trim()) return;
    const t = prompt('Тип: 1 — оценка 1–10, 2 — число, 3 — галочка', '1'); if (t == null) return;
    const cad = ({ '1': 'daily', '2': 'weekly', '3': 'monthly' })[prompt('Частота: 1 — день, 2 — неделя, 3 — месяц', '1')] || 'daily';
    const r = await sphApi.mAdd({ name: name.trim(), cadence: cad, type: t === '3' ? 'bool' : (t === '2' ? 'number' : 'scale') });
    if (r && r.id) { await sphApi.assign('metric', r.id, s.id); await sphApi.qPatch(qid, { metric_id: r.id }); }
    window.loadSpheres();
  });
  // клик по задаче — открыть в Целях (полная карточка: текст/заметки/связи)
  document.querySelectorAll('#screen-spheres [data-tnode]').forEach(el => el.onclick = () => { if (window.openNode) window.openNode(+el.dataset.tnode); });
  // клик по странице инфо — открыть нужную заметку в разделе Инфо
  document.querySelectorAll('#screen-spheres [data-page]').forEach(el => el.onclick = () => { if (window.openPage) window.openPage(+el.dataset.page); });
  // ===== работа с задачами прямо в сфере (через node-API Целей) =====
  const node = (id, m, b) => fetch('/api/nodes' + (id ? '/' + id : ''), { method: m, headers: { 'Content-Type': 'application/json' }, body: b ? JSON.stringify(b) : undefined });
  const reload = () => window.loadSpheres();
  document.querySelectorAll('#screen-spheres [data-del]').forEach(el => el.onclick = async () => {
    if (confirm('Удалить задачу? (уедет в корзину Целей)')) { await node(el.dataset.del, 'DELETE'); reload(); }
  });
  document.querySelectorAll('#screen-spheres [data-pri]').forEach(el => el.onclick = async () => {
    const [id, cur] = el.dataset.pri.split(':'); const order = ['', 'P0', 'P1', 'P2'];
    await node(id, 'PATCH', { priority: order[(order.indexOf(cur) + 1) % order.length] || null }); reload();
  });
  document.querySelectorAll('#screen-spheres [data-due]').forEach(el => el.onclick = async () => {
    const v = await window.pickDate(null, { title: 'Срок задачи' });
    if (v === undefined) return;                  // отмена
    await node(el.dataset.due, 'PATCH', { due_date: v || null }); reload();   // null — убрать
  });
  document.querySelectorAll('#screen-spheres [data-addtask]').forEach(el => el.onclick = async () => {
    const t = prompt('Новая задача:'); if (!t?.trim()) return;
    await node('', 'POST', { title: t.trim(), parent_id: +el.dataset.addtask }); reload();
  });
  document.querySelectorAll('#screen-spheres [data-addcat]').forEach(el => el.onclick = async () => {
    const t = prompt('Новая подкатегория:'); if (!t?.trim()) return;
    await node('', 'POST', { title: t.trim(), parent_id: +el.dataset.addcat, is_category: 1 }); reload();
  });
  document.querySelectorAll('#screen-spheres [data-addroot]').forEach(inp => inp.addEventListener('keydown', async e => {
    if (e.key === 'Enter' && inp.value.trim()) { await node('', 'POST', { title: inp.value.trim(), parent_id: +inp.dataset.addroot }); inp.value = ''; reload(); }
  }));
  // сворачивание категорий (по умолчанию свёрнуто, состояние в localStorage)
  document.querySelectorAll('#screen-spheres [data-sphfold]').forEach(el => el.onclick = () => {
    const ex = new Set(JSON.parse(localStorage.sphFold || '[]')); const id = +el.dataset.sphfold;
    ex.has(id) ? ex.delete(id) : ex.add(id);
    localStorage.sphFold = JSON.stringify([...ex]);
    renderSpheres();   // мгновенно, без запроса
  });
  document.getElementById('sphStepTask').onclick = async () => {
    if (!s.step?.trim()) { alert('Сначала задай шаг (клик по «следующий шаг»).'); return; }
    const r = await sphApi.stepTask(s.id).then(x => x.json()).catch(() => ({ error: 'ошибка' }));
    if (r.error) alert(r.error); else window.loadSpheres();
  };
}

function ensureSphStyle() {
  if (document.getElementById('sph-style')) return;
  const css = `
    .sph-ov{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}
    .sph-card{background:var(--panel);border:1px solid var(--line);border-radius:13px;box-shadow:var(--shadow-sm);padding:13px 15px;cursor:pointer;transition:.12s}
    .sph-card:hover{border-color:var(--green-dim);transform:translateY(-1px)}
    .sph-ct{display:flex;align-items:center;gap:10px}.sph-cn{font-weight:700;flex:1}.sph-cs{font:700 18px var(--mono)}
    .sph-ideal{font-size:12.5px;color:var(--muted);margin-top:8px}.sph-step{font-size:12.5px;margin-top:5px}.sph-step b{color:var(--amber)}
    .sph-meta{margin-top:8px;font:600 11px var(--mono);color:var(--muted)}
    .sph-crumb{font-size:12px;color:var(--muted);margin-bottom:10px;display:flex;align-items:center;gap:10px}.sph-crumb a{color:var(--green);cursor:pointer}
    .sph-hero{display:flex;gap:18px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-sm);padding:16px 18px}
    .sph-hi{flex:1;min-width:0}.sph-hs{text-align:center;flex:0 0 auto}
    .sph-ladder{margin-top:12px;padding:2px 14px}
    .sph-rung{display:flex;gap:12px;align-items:baseline;padding:9px 0;border-top:1px solid var(--bg2);cursor:text}.sph-rung:first-child{border-top:0}
    .sph-rl{flex:0 0 116px;font:600 11px var(--mono);color:var(--muted)}
    .sph-rv{flex:1;min-width:0;font-size:13.5px;line-height:1.45}
    .sph-rung.step{background:rgba(168,119,8,.07);border-radius:9px;margin:2px -8px 0;padding:10px 8px}.sph-rung.step .sph-rl{color:var(--amber)}.sph-rung.step .sph-rv b{color:var(--amber)}
    .sph-track{position:relative;height:32px;margin:14px 0 2px}.sph-rail{position:absolute;top:13px;left:0;right:0;height:7px;border-radius:99px;background:var(--bg2)}
    .sph-fill{position:absolute;top:13px;left:0;height:7px;border-radius:99px}
    .sph-you{position:absolute;top:-4px;transform:translateX(-50%);font:700 12px var(--mono);color:var(--green)}.sph-you::after{content:"▼";display:block;text-align:center;font-size:10px}
    .sph-z,.sph-t10{position:absolute;top:23px;font:600 9px var(--mono);color:var(--muted)}.sph-z{left:0}.sph-t10{right:0}
    .sph-scoreset{display:flex;gap:5px;flex-wrap:wrap}.sph-scoreset b{width:30px;height:30px;border-radius:8px;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font:600 13px var(--mono);cursor:pointer;color:var(--muted)}.sph-scoreset b.on{background:var(--green);color:#fff;border-color:var(--green)}
    .sph-conn{border:1px solid var(--green-dim)}
    .sph-cg{margin-bottom:9px}.sph-cgl{font:600 10px var(--mono);letter-spacing:.6px;color:var(--nav);text-transform:uppercase;margin-bottom:5px}
    .sph-pi{display:inline-flex;align-items:center;font-size:12.5px;background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:4px 9px;margin:0 5px 5px 0;cursor:pointer}
    .sph-pi:hover{border-color:var(--green-dim)}.sph-pi.on{background:var(--green-soft);border-color:var(--green-dim);color:var(--green)}
    .sph-mom{display:flex;align-items:center;gap:14px;padding-bottom:9px;margin-bottom:6px;border-bottom:1px solid var(--bg2)}
    .sph-momn{font:700 30px var(--mono);color:var(--green);line-height:1}.sph-momn small{font-size:14px;color:var(--muted)}
    .sph-momt{font-size:12.5px;color:var(--muted)}
    .pbar2{flex:1;max-width:160px;height:7px;border-radius:99px;background:var(--bg2);overflow:hidden;margin:0 6px}.pbar2 i{display:block;height:100%;background:var(--green-dim)}
    .sphwk{display:flex;gap:3px;margin-top:4px}.sphwk i{width:11px;height:11px;border-radius:3px;background:var(--bg2)}.sphwk i.on{background:var(--green-dim)}.sphwk i.miss{background:rgba(196,63,63,.18)}
    .sphpool{display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid var(--bg2)}.sphpool:first-child{border-top:0}
    .sphpool .rowbtn{opacity:0}.sphpool:hover .rowbtn{opacity:1}
    .sphpool-n{flex:1;min-width:0;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .sphpool-today{font:600 10px var(--mono);color:var(--green)}
    .sphpool-st{font:600 10px var(--mono);color:var(--amber)}
    .sphpool-neg{font:600 9px var(--mono);color:var(--red);background:rgba(196,63,63,.12);border-radius:20px;padding:1px 6px}
    .sphpool-bar{position:relative;flex:0 0 84px;height:7px;border-radius:99px;background:var(--bg2);overflow:hidden}
    .sphpool-bar b,.sphpool-bar i{position:absolute;left:0;top:0;height:100%;border-radius:99px}
    .sphpool-bar b{background:var(--green-dim);opacity:.28}.sphpool-bar i{background:var(--green-dim)}
    .sphpool-bar.neg i{background:var(--red)}
    .sphpool-spark{flex:0 0 84px;display:flex;justify-content:flex-end}
    .sphpool.neg .sphpool-n{color:var(--red)}
    .sphtrend{font-size:10px}.sphtrend.up{color:var(--green)}.sphtrend.down{color:var(--red)}
    .sphpool-p{font:600 11px var(--mono);color:var(--muted);white-space:nowrap}.sphpool-p small{font-size:9px;opacity:.65}
    .sphb{font:600 10px var(--mono);border-radius:20px;padding:2px 8px;white-space:nowrap}.sphb.fire{background:rgba(196,63,63,.12);color:var(--red)}.sphb.soon{background:rgba(168,119,8,.14);color:var(--amber)}
    .tgt{font-size:11px;color:var(--amber);margin-top:2px}
    .strk{color:var(--amber)!important;font-weight:600}
    .sphkpi{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin:12px 0 4px}
    .sphk{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:9px 11px;box-shadow:var(--shadow-sm)}
    .sphk-n{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .sphk-v{font:700 19px var(--mono);line-height:1.1;margin:2px 0}.sphk-v small{font-size:11px;color:var(--muted);margin-left:2px}
    .sphk-bar{height:5px;border-radius:99px;background:var(--bg2);overflow:hidden;margin-top:4px}.sphk-bar i{display:block;height:100%;background:var(--green-dim)}
    .sphk-p{font:600 10px var(--mono);color:var(--muted);margin-top:4px}.sphk-p.up{color:var(--green)}.sphk-p.down{color:var(--red)}
    .sph-rm{display:flex;gap:9px;align-items:center;padding:6px 0;border-top:1px solid var(--bg2);font-size:13.5px}.sph-rm:first-child{border-top:0}
    .sph-rk{font:700 10px var(--mono);color:var(--muted);width:38px;flex:0 0 auto}
    .sph-rt{flex:1;min-width:0;cursor:text}.sph-rm.done .sph-rt{color:var(--muted);text-decoration:line-through}
    .sph-rm.here{background:rgba(168,119,8,.08);border-radius:8px;margin:0 -8px;padding:6px 8px}.sph-rm.here .sph-rt{font-weight:700}
    .sph-rm .rowbtn{opacity:.55}.sph-rm:hover .rowbtn{opacity:1}   /* ✕ вехи всегда видна (строка не .task — иначе удалить нельзя) */
    .sph-rmbar{width:56px;flex:0 0 auto}
    .sph-faq{padding:8px 0;border-top:1px solid var(--bg2);cursor:grab}.sph-faq:first-child{border-top:0}
    .sph-faq.dropbefore{box-shadow:inset 0 2px 0 var(--green)}.sph-faq.dropafter{box-shadow:inset 0 -2px 0 var(--green)}
    .sph-faqq{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
    .sph-faqnum{font:700 12px var(--mono);color:var(--muted);flex:0 0 auto}
    .sph-faqt{flex:1;min-width:120px;font-weight:600;font-size:13.5px;cursor:text}
    .sph-faqa{margin-top:4px;font-size:13px;color:var(--muted);cursor:text;white-space:pre-wrap}
    .sph-faq .rowbtn{opacity:.6}.sph-faq:hover .rowbtn{opacity:1}
    .catrow{display:flex;align-items:center;gap:10px;padding:5px 0;border-top:1px solid var(--bg2)}.catrow:first-child{border-top:0}
    .catt{flex:1;min-width:0;font-size:13.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.catt.on{font-weight:700;color:var(--green)}
    .catrow select{flex:0 0 auto;max-width:190px;border:1px solid var(--line);border-radius:8px;padding:5px 8px;font:12.5px var(--sans);background:var(--bg)}
    .task.sphcat{border-top:0;padding-top:9px}.task.sphcat b{font-size:13px;color:var(--nav)}
    #screen-spheres [data-tnode]{cursor:pointer}#screen-spheres [data-tnode]:hover{color:var(--green)}
    [data-edit]{cursor:text}
    @media(max-width:768px){
      .sph-ov{grid-template-columns:1fr}
      .sph-hero{flex-direction:column;text-align:center;gap:10px;padding:14px}
      .sph-mom{flex-direction:column;align-items:flex-start;gap:6px}
      .sph-scoreset b{width:28px;height:28px}
      .sph-pi{font-size:13px;padding:6px 11px}
      .sph-rung{flex-direction:column;gap:2px;padding:8px 0}.sph-rl{flex-basis:auto}
      .pbar2{max-width:none}
    }`;
  const st = document.createElement('style'); st.id = 'sph-style'; st.textContent = css;
  document.head.appendChild(st);
}

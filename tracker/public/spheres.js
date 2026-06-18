/* Сферы — экран поверх реальных данных Pipboy.
   Сфера = сектор Колеса. Привязка у источника (экран «🏷 привязка»): тег на
   категории Целей / странице Инфо / рутине, вложенные наследуют; Психология/
   Трекинг/Финансы/Люди — по дефолту секции (авто). area_id через /api/spheres/assign. */

let sphData = null, sphPool = null, sphOpen = null, sphTag = false, sphTagData = null;
const sesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SPH_COL = ['#1e9e57', '#c43f3f', '#a87708', '#6b4fb5', '#2a76b5', '#364656'];
const SPH_KIND = { task: ['задача', 'ok'], decision: ['решение', 'dec'], question: ['вопрос', 'p2'], principle: ['принцип', 'p1'], idea: ['идея', ''], worry: ['тревога', 'p0'] };
const colOf = i => SPH_COL[i % SPH_COL.length];

const sphApi = {
  load: () => fetch('/api/spheres').then(r => r.json()),
  pool: () => fetch('/api/spheres/pool').then(r => r.json()),
  tagpool: () => fetch('/api/spheres/tagpool').then(r => r.json()),
  assign: (kind, id, areaId) => fetch('/api/spheres/assign', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, id, areaId }) }),
  score: (id, n) => fetch('/api/psy/wheel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scores: { [id]: n } }) }),
  patch: (id, b) => fetch('/api/psy/areas/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  stepTask: id => fetch('/api/psy/areas/' + id + '/task', { method: 'POST' }),
  toggle: id => fetch('/api/nodes/' + id + '/toggle', { method: 'POST' }),
};

function sphRing(score, col, size = 48) {
  const r = size / 2 - 4, C = 2 * Math.PI * r, sc = score ?? 0;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#eef0f4" stroke-width="5"/><circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${col}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${C * sc / 10} ${C}" transform="rotate(-90 ${size / 2} ${size / 2})"/><text x="${size / 2}" y="${size / 2 + 5}" text-anchor="middle" style="font:700 ${size * .32}px var(--mono);fill:var(--text)">${score ?? '–'}</text></svg>`;
}
function sphSpark(vals, w = 74, h = 18) {
  if (!vals || vals.length < 2) return '<span class="muted" style="font-size:11px">мало данных</span>';
  const p = 2, mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const pts = vals.map((v, i) => [p + i * (w - 2 * p) / (vals.length - 1), h - p - ((v - mn) / rng) * (h - 2 * p)]);
  return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline fill="none" stroke="#5cb585" stroke-width="1.6" points="${pts.map(p => p.join(',')).join(' ')}"/></svg>`;
}

window.loadSpheres = async function () {
  ensureSphStyle();
  [sphData, sphPool] = await Promise.all([sphApi.load(), sphApi.pool()]);
  renderSpheres();
};
// открыть конкретную сферу из «Сегодня» (полоса сфер) — без отдельной загрузки
window.openSphere = function (id) { sphOpen = id; showScreen('spheres'); };

// ---- Инлайн-привязка к сфере прямо в Целях/Инфо: общий <select> + делегированный обработчик ----
(() => { const st = document.createElement('style'); st.textContent =
  '.sphsel{font:11px var(--sans);border:1px solid var(--line);border-radius:6px;padding:2px 4px;background:var(--bg);color:var(--muted);max-width:140px;flex:0 0 auto}.sphsel:focus{outline:none;border-color:var(--green-dim)}';
  document.head.appendChild(st); })();
window.SPH_AREAS = [];
fetch('/api/spheres/pool').then(r => r.json()).then(p => { window.SPH_AREAS = p.areas || []; }).catch(() => {});
window.sphSelHtml = (kind, id, areaId) => `<select class="sphsel" data-sphsel="${kind}:${id}" title="сфера жизни" onclick="event.stopPropagation()">
  <option value="">· сфера</option>${(window.SPH_AREAS || []).map(a => `<option value="${a.id}"${areaId === a.id ? ' selected' : ''}>${String(a.name).replace(/[<>&"]/g, '')}</option>`).join('')}</select>`;
document.addEventListener('change', async e => {
  const sel = e.target.closest && e.target.closest('.sphsel'); if (!sel) return;
  const [kind, id] = sel.dataset.sphsel.split(':');
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
  const an = id => (sphPool?.areas || []).find(a => a.id === id)?.name;
  const d = sphPool?.defaults || {};
  const route = [['Люди', d.person], ['Трекинг', d.metric], ['Психология', d.practice], ['Финансы', d.obligation]]
    .map(([l, id]) => `${l}→<b>${an(id) || '—'}</b>`).join(' · ');
  return `<h2 style="margin-bottom:2px">Сферы жизни</h2>
    <div class="muted" style="margin-bottom:8px">средний баланс ${avg}/10 · 10 = куда идём, оценка = где сейчас, шаг = что делаем. Всё на реальных данных.</div>
    <div class="card" style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px">
      <span class="pill btn ok" id="sphAuto">🪄 авто-настроить</span>
      <span class="pill btn" id="sphTagBtn">🏷 привязка</span>
      <span class="muted" style="font-size:12px">секции сами: ${route} · цели/инфо/рутины — в «привязке»</span></div>
    <div class="sph-ov">${sphData.map((s, i) => {
      const links = s.routines.length + s.tracking.length + s.practices.length + s.fin.length + s.tasks.length;
      return `<div class="sph-card" data-open="${s.id}">
        <div class="sph-ct">${sphRing(s.score, colOf(i), 40)}<div class="sph-cn">${sesc(s.name)}</div><div class="sph-cs" style="color:${colOf(i)}">${s.score ?? '–'}</div></div>
        <div class="sph-ideal">🎯 ${s.ideal ? sesc(s.ideal) : '<span class="muted">задать «10» — клик внутрь</span>'}</div>
        <div class="sph-step">→ ${s.step ? '<b>' + sesc(s.step) + '</b>' : '<span class="muted">нет шага</span>'}</div>
        <div class="sph-meta">🎯 ${s.tasks.filter(t => !t.cat).length} · ↻ ${s.routines.length} · 📊 ${s.tracking.length} · 🧠 ${s.practices.length} · 💰 ${s.fin.length}</div>
      </div>`;
    }).join('')}</div>`;
}
function bindOverview() {
  document.querySelectorAll('#screen-spheres [data-open]').forEach(c => c.onclick = () => { sphOpen = +c.dataset.open; renderSpheres(); });
  document.getElementById('sphAuto')?.addEventListener('click', async () => {
    const r = await fetch('/api/spheres/auto', { method: 'POST' }).then(x => x.json());
    const lines = Object.entries(r.defaults).map(([k, v]) => `${({ person: 'Люди', metric: 'Трекинг', practice: 'Психология', obligation: 'Финансы' })[k]} → ${v || 'нет подходящей сферы'}`);
    alert(`Авто-настройка связей:\n\n${lines.join('\n')}\n\nКатегорий целей разложено: ${r.categoriesMapped}`);
    window.loadSpheres();
  });
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
  const dn = id => (areas.find(a => a.id === id) || {}).name;
  const dd = sphPool?.defaults || {};
  return `<div class="sph-crumb"><a id="sphBackTag">← Сферы</a> · <span class="pill btn" id="sphAutomapTag">🪄 авто по именам</span></div>
    <h2 style="margin-bottom:2px">Привязка к сферам</h2>
    <div class="muted" style="margin-bottom:6px">Тегируешь у источника, вложенные <b>наследуют</b> (можно переопределить). Названия/структуру не трогаем.</div>
    <div class="card" style="font-size:12.5px;color:var(--muted);margin-bottom:12px">⚡ По умолчанию (авто): Люди→<b>${dn(dd.person) || '—'}</b> · Трекинг→<b>${dn(dd.metric) || '—'}</b> · Психология→<b>${dn(dd.practice) || '—'}</b> · Финансы→<b>${dn(dd.obligation) || '—'}</b> — отдельно тегать не нужно.</div>
    <div class="sec" style="margin-top:0">🎯 Цели · категории (разделы и подразделы)</div>
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
}

function block(label, jump, inner) {
  return `<div class="sec">${label} <span class="muted" style="font-weight:400">· ${jump}</span></div><div class="card">${inner}</div>`;
}

function sphDetail(s, i) {
  const col = colOf(i);
  let h = `<div class="sph-crumb"><a id="sphBack">← Сферы</a></div>
    <div class="sph-hero">
      <div class="sph-hs">${sphRing(s.score, col, 70)}<div style="margin-top:4px">${sphSpark(s.history)}</div></div>
      <div class="sph-hi"><h2 style="margin:0 0 4px">${sesc(s.name)}</h2>
        <div class="sph-dest" data-edit="ideal">🎯 <b>10 = ${s.ideal ? sesc(s.ideal) : 'задать цель (клик)'}</b></div></div>
    </div>
    <div class="sph-track"><div class="sph-rail"></div><div class="sph-fill" style="width:${(s.score ?? 0) * 10}%;background:${col}"></div>
      <div class="sph-you" style="left:${(s.score ?? 0) * 10}%">${s.score ?? '–'}</div><span class="sph-z">0</span><span class="sph-t10">10 ✦</span></div>
    <div class="muted" style="font-size:12.5px;margin-top:4px" data-edit="current_desc">где сейчас: ${s.current_desc ? sesc(s.current_desc) : '<span class="muted">описать (клик)</span>'}</div>
    <div class="sph-step-box"><span class="sph-l">СЛЕДУЮЩИЙ ШАГ</span><b data-edit="step">${s.step ? sesc(s.step) : 'задать шаг (клик)'}</b>
      ${s.next_desc ? `<div class="muted" style="font-size:12.5px;margin-top:3px" data-edit="next_desc">${sesc(s.next_desc)}</div>` : ''}
      <div style="margin-top:7px"><span class="pill btn" id="sphStepTask">＋ шаг в задачи</span></div></div>`;

  // живой прогресс из данных (без дублей с блоками ниже)
  const pr = s.progress || {};
  const parts = [];
  if (pr.tasksTotal) parts.push(`<div class="task"><span class="t">Задачи</span><span class="pbar2"><i style="width:${Math.round(pr.tasksDone / pr.tasksTotal * 100)}%"></i></span><span class="meta num">${pr.tasksDone}/${pr.tasksTotal}</span></div>`);
  if (s.routines.length) { const rd = s.routines.filter(r => r.doneToday).length;
    parts.push(`<div class="task"><span class="t">Рутины сегодня</span><span class="pbar2"><i style="width:${Math.round(rd / s.routines.length * 100)}%"></i></span><span class="meta num">${rd}/${s.routines.length}</span></div>`); }
  h += `<div class="sec">📈 Прогресс по данным <span class="muted" style="font-weight:400">· считается сам</span></div><div class="card">
    ${pr.momentum != null
      ? `<div class="sph-mom"><div class="sph-momn">${pr.momentum}<small>/10</small></div>
           <div class="sph-momt">движение по данным (задачи + дисциплина рутин за 2 нед)<br>
             <span class="pill btn ok" id="sphApplyMom">поставить как оценку сферы</span></div></div>`
      : ''}
    ${parts.join('') || '<div class="empty">привяжи задачи (категорию) и рутины через «🔗 связи» — посчитаю прогресс сам, без ручного ведения</div>'}</div>`;

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
        ${t.due ? `<span class="meta">${t.due}</span>` : ''}
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

  // рутины
  if (s.routines.length) h += block('↻ Рутины', 'Рутины', s.routines.map(r => `
    <div class="task"><span class="cb ${r.doneToday ? 'done' : ''}"></span><span class="t">${sesc(r.name)}</span><span class="meta">🔥 ${r.streak}</span></div>`).join(''));
  // трекинг
  if (s.tracking.length) h += block('📊 Трекинг · 7 дней', 'Трекинг', s.tracking.map(m => `
    <div class="task"><span class="t">${sesc(m.name)}</span>${sphSpark(m.s)}<span class="meta num">${m.v ?? '–'} ${sesc(m.unit)}</span></div>`).join(''));
  // практики
  if (s.practices.length) h += block('🧠 Практики', 'Психология', s.practices.map(p => `
    <div class="task"><span class="t">${sesc(p.name)}</span><span class="meta">🔥 ${p.streak}</span></div>`).join(''));
  // люди (социализация)
  if (s.people && s.people.length) h += block('☻ Люди', 'Люди', s.people.map(p => `
    <div class="task"><span class="t">${sesc(p.name)}</span><span class="meta">${p.rhythm ? 'ритм ' + p.rhythm + 'д' : ''}${p.last ? ' · посл. ' + p.last : ''}</span></div>`).join(''));
  // финансовые показатели (числа, только в денежной сфере) — FIRE без суммы
  if (s.finance) { const f = s.finance, money = n => n == null ? '—' : Math.round(n).toLocaleString('ru-RU');
    h += block('📈 Финансовые показатели', 'Финансы', `
      ${f.firePct != null ? `<div class="task"><span class="t">FIRE · прогресс</span><span class="pbar2"><i style="width:${Math.min(100, f.firePct)}%"></i></span><span class="meta num">${f.firePct.toFixed(1)}%</span></div>` : ''}
      <div class="task"><span class="t">Расход за месяц</span><span class="meta num">${money(f.expense)} €${f.budget ? ' / ' + money(f.budget) : ''}</span></div>
      <div class="task"><span class="t">Пассивный доход/мес</span><span class="meta num">${money(f.income)} €</span></div>`);
  }
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
        + items.map(f => `<div class="task" style="padding-left:16px"><span class="t">${sesc(f.name)}</span>${f.next_date ? `<span class="meta">${f.next_date}</span>` : ''}<span class="meta num">${f.amount} ${sesc(f.currency)}</span></div>`).join('');
    }
    h += block('💰 Платежи · по периодам', 'Финансы', html);
  }
  // долги
  if (s.debts && s.debts.length) h += block('🤝 Долги', 'Финансы', s.debts.map(x => `
    <div class="task"><span class="pill ${x.direction === 'i_owe' ? 'p0' : 'ok'}">${x.direction === 'i_owe' ? 'я должен' : 'мне должны'}</span>
      <span class="t">${sesc(x.name)}</span>${x.due_date ? `<span class="meta">${x.due_date}</span>` : ''}<span class="meta num">${x.amount} ${sesc(x.currency)}</span></div>`).join(''));
  // план шагов
  if (s.steps && s.steps.length) h += block('🪜 План шагов', 'Финансы', s.steps.map(st => `
    <div class="task"><span class="pill ${st.kind === 'sell' ? 'p1' : 'ok'}">${({ buy: 'купить', sell: 'продать', transfer: 'перевод' })[st.kind] || st.kind}</span>
      <span class="t">${sesc(st.title)}</span>${st.planned_date ? `<span class="meta">${st.planned_date}</span>` : ''}${st.amount ? `<span class="meta num">${st.amount}</span>` : ''}</div>`).join(''));
  // события
  if (s.events && s.events.length) h += block('📅 События сферы', 'Календарь', s.events.map(e => `
    <div class="task"><span class="meta num">${e.date}${e.time ? ' ' + e.time : ''}</span><span class="t">${sesc(e.title)}</span></div>`).join(''));
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
    const labels = { ideal: 'Цель (10 = …):', step: 'Следующий шаг:', current_desc: 'Где сейчас (описание):', next_desc: 'Что для шага надо:' };
    const v = prompt(labels[f], s[f] || '');
    if (v != null) { await sphApi.patch(s.id, { [f]: v.trim() }); window.loadSpheres(); }
  });
  document.querySelectorAll('#screen-spheres [data-tog]').forEach(c => c.onclick = async () => { await sphApi.toggle(+c.dataset.tog); window.loadSpheres(); });
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
    const v = prompt('Срок (ГГГГ-ММ-ДД, пусто — убрать):'); if (v === null) return;
    await node(el.dataset.due, 'PATCH', { due_date: v.trim() || null }); reload();
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
  document.getElementById('sphApplyMom')?.addEventListener('click', async () => {
    if (s.progress?.momentum != null) { await sphApi.score(s.id, s.progress.momentum); window.loadSpheres(); }
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
    .sph-dest{background:var(--green-soft);border:1px solid var(--green-dim);border-radius:10px;padding:8px 12px;font-size:14px;cursor:text}.sph-dest b{color:var(--green)}
    .sph-track{position:relative;height:32px;margin:14px 0 2px}.sph-rail{position:absolute;top:13px;left:0;right:0;height:7px;border-radius:99px;background:var(--bg2)}
    .sph-fill{position:absolute;top:13px;left:0;height:7px;border-radius:99px}
    .sph-you{position:absolute;top:-4px;transform:translateX(-50%);font:700 12px var(--mono);color:var(--green)}.sph-you::after{content:"▼";display:block;text-align:center;font-size:10px}
    .sph-z,.sph-t10{position:absolute;top:23px;font:600 9px var(--mono);color:var(--muted)}.sph-z{left:0}.sph-t10{right:0}
    .sph-step-box{background:rgba(168,119,8,.08);border-radius:10px;padding:11px 14px;margin-top:12px}.sph-step-box .sph-l{font:600 9px var(--mono);letter-spacing:.6px;color:var(--amber);display:block;margin-bottom:1px}.sph-step-box b{font-size:15px;cursor:text}
    .sph-scoreset{display:flex;gap:5px;flex-wrap:wrap}.sph-scoreset b{width:30px;height:30px;border-radius:8px;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font:600 13px var(--mono);cursor:pointer;color:var(--muted)}.sph-scoreset b.on{background:var(--green);color:#fff;border-color:var(--green)}
    .sph-conn{border:1px solid var(--green-dim)}
    .sph-cg{margin-bottom:9px}.sph-cgl{font:600 10px var(--mono);letter-spacing:.6px;color:var(--nav);text-transform:uppercase;margin-bottom:5px}
    .sph-pi{display:inline-flex;align-items:center;font-size:12.5px;background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:4px 9px;margin:0 5px 5px 0;cursor:pointer}
    .sph-pi:hover{border-color:var(--green-dim)}.sph-pi.on{background:var(--green-soft);border-color:var(--green-dim);color:var(--green)}
    .sph-mom{display:flex;align-items:center;gap:14px;padding-bottom:9px;margin-bottom:6px;border-bottom:1px solid var(--bg2)}
    .sph-momn{font:700 30px var(--mono);color:var(--green);line-height:1}.sph-momn small{font-size:14px;color:var(--muted)}
    .sph-momt{font-size:12.5px;color:var(--muted)}
    .pbar2{flex:1;max-width:160px;height:7px;border-radius:99px;background:var(--bg2);overflow:hidden;margin:0 6px}.pbar2 i{display:block;height:100%;background:var(--green-dim)}
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
      .sph-dest{font-size:13.5px}
      .pbar2{max-width:none}
    }`;
  const st = document.createElement('style'); st.id = 'sph-style'; st.textContent = css;
  document.head.appendChild(st);
}

/* Сферы — экран поверх реальных данных Pipboy.
   Сфера = сектор Колеса. Гибрид-тег: категории Целей тащат задачи (авто),
   рутины/метрики/практики/финансы привязываются вручную («🔗 связи»).
   Правки идут в настоящие данные (Колесо, задачи, area_id через /api/spheres/assign). */

let sphData = null, sphPool = null, sphOpen = null, sphEditConn = false;
const sesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SPH_COL = ['#1e9e57', '#c43f3f', '#a87708', '#6b4fb5', '#2a76b5', '#364656'];
const colOf = i => SPH_COL[i % SPH_COL.length];

const sphApi = {
  load: () => fetch('/api/spheres').then(r => r.json()),
  pool: () => fetch('/api/spheres/pool').then(r => r.json()),
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
window.openSphere = function (id) { sphOpen = id; sphEditConn = false; showScreen('spheres'); };

function renderSpheres() {
  const el = document.getElementById('screen-spheres');
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
    <div class="card" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px">
      <span class="pill btn ok" id="sphAuto">🪄 авто-настроить связи</span>
      <span class="muted" style="font-size:12px">секции сами в свои сферы: ${route} · цели — по категориям</span></div>
    <div class="sph-ov">${sphData.map((s, i) => {
      const links = s.routines.length + s.tracking.length + s.practices.length + s.fin.length + s.tasks.length;
      return `<div class="sph-card" data-open="${s.id}">
        <div class="sph-ct">${sphRing(s.score, colOf(i), 40)}<div class="sph-cn">${sesc(s.name)}</div><div class="sph-cs" style="color:${colOf(i)}">${s.score ?? '–'}</div></div>
        <div class="sph-ideal">🎯 ${s.ideal ? sesc(s.ideal) : '<span class="muted">задать «10» — клик внутрь</span>'}</div>
        <div class="sph-step">→ ${s.step ? '<b>' + sesc(s.step) + '</b>' : '<span class="muted">нет шага</span>'}</div>
        <div class="sph-meta">🎯 ${s.tasks.length} · ↻ ${s.routines.length} · 📊 ${s.tracking.length} · 🧠 ${s.practices.length} · 💰 ${s.fin.length}</div>
      </div>`;
    }).join('')}</div>`;
}
function bindOverview() {
  document.querySelectorAll('#screen-spheres [data-open]').forEach(c => c.onclick = () => { sphOpen = +c.dataset.open; sphEditConn = false; renderSpheres(); });
  document.getElementById('sphAuto')?.addEventListener('click', async () => {
    const r = await fetch('/api/spheres/auto', { method: 'POST' }).then(x => x.json());
    const lines = Object.entries(r.defaults).map(([k, v]) => `${({ person: 'Люди', metric: 'Трекинг', practice: 'Психология', obligation: 'Финансы' })[k]} → ${v || 'нет подходящей сферы'}`);
    alert(`Авто-настройка связей:\n\n${lines.join('\n')}\n\nКатегорий целей разложено: ${r.categoriesMapped}`);
    window.loadSpheres();
  });
}

function block(label, jump, inner) {
  return `<div class="sec">${label} <span class="muted" style="font-weight:400">· ${jump}</span></div><div class="card">${inner}</div>`;
}

function sphDetail(s, i) {
  const col = colOf(i);
  let h = `<div class="sph-crumb"><a id="sphBack">← Сферы</a> · <span class="pill btn" id="sphConnBtn">🔗 связи</span></div>
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

  if (sphEditConn) h += sphConnEditor(s);

  // живой прогресс из данных
  const pr = s.progress || {};
  const parts = [];
  if (pr.tasksTotal) parts.push(`<div class="task"><span class="t">Задачи выполнено</span><span class="pbar2"><i style="width:${Math.round(pr.tasksDone / pr.tasksTotal * 100)}%"></i></span><span class="meta num">${pr.tasksDone}/${pr.tasksTotal}</span></div>`);
  if (pr.adherence != null) parts.push(`<div class="task"><span class="t">Дисциплина рутин · 14 дн</span><span class="pbar2"><i style="width:${Math.round(pr.adherence * 100)}%"></i></span><span class="meta num">${Math.round(pr.adherence * 100)}%</span></div>`);
  if (pr.trends && pr.trends.length) parts.push(`<div class="task"><span class="t">Тренд метрик</span><span class="meta">${pr.trends.map(t => `${sesc(t.name)} ${t.dir > 0 ? '↗' : t.dir < 0 ? '↘' : '→'}`).join(' · ')}</span></div>`);
  h += `<div class="sec">📈 Прогресс по данным <span class="muted" style="font-weight:400">· считается сам</span></div><div class="card">
    ${pr.momentum != null
      ? `<div class="sph-mom"><div class="sph-momn">${pr.momentum}<small>/10</small></div>
           <div class="sph-momt">движение по реальным данным (задачи + рутины)<br>
             <span class="pill btn ok" id="sphApplyMom">поставить как оценку сферы</span></div></div>`
      : ''}
    ${parts.join('') || '<div class="empty">привяжи задачи (категорию) и рутины через «🔗 связи» — посчитаю прогресс сам, без ручного ведения</div>'}</div>`;

  // задачи
  h += block('🎯 Задачи сектора', 'Цели', s.tasks.length ? s.tasks.map(t => `
    <div class="task"><span class="cb ${t.done ? 'done' : ''}" data-tog="${t.id}"></span>
      ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
      <span class="t ${t.done ? 'done' : ''}">${sesc(t.title)}</span>${t.due ? `<span class="meta">${t.due}</span>` : ''}</div>`).join('')
    : '<div class="empty">нет задач — привяжи категорию целей в «🔗 связи» или нажми «＋ шаг в задачи»</div>');

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
  // финансы
  if (s.fin.length) h += block('💰 Финансы сферы', 'Финансы', s.fin.map(f => `
    <div class="task"><span class="t">${sesc(f.name)}</span><span class="meta num">${f.amount} ${sesc(f.currency)} / ${sesc(f.period)}</span></div>`).join(''));

  // ревизия
  h += `<div class="sec">🪞 Ревизия · оценка сферы</div><div class="card">
    <div class="muted" style="font-size:13px;margin-bottom:4px">Где сектор сейчас? Оценка пишется в Колесо.</div>
    <div class="sph-scoreset" id="sphScore"></div></div>`;
  return h;
}

function sphConnEditor(s) {
  if (!sphPool) return `<div class="card"><div class="muted">загрузка связей…</div></div>`;
  const grp = (kind, label, items, nameKey) => {
    const mine = items.filter(x => x.area_id === s.id), free = items.filter(x => x.area_id == null), other = items.filter(x => x.area_id != null && x.area_id !== s.id);
    return `<div class="sph-cg"><div class="sph-cgl">${label}</div>
      ${mine.map(x => `<span class="sph-pi on" data-as="${kind}:${x.id}:0">✓ ${sesc(x[nameKey])}</span>`).join('')}
      ${free.map(x => `<span class="sph-pi" data-as="${kind}:${x.id}:${s.id}">＋ ${sesc(x[nameKey])}</span>`).join('')}
      ${other.length ? `<span class="muted" style="font-size:11px">· занято в др. сферах: ${other.length}</span>` : ''}
      ${!items.length ? '<span class="muted" style="font-size:12px">пусто</span>' : ''}</div>`;
  };
  const def = sphPool.defaults || {};
  const defT = (kind, label) => { const on = def[kind] === s.id; return `<span class="sph-pi ${on ? 'on' : ''}" data-def="${kind}:${on ? '' : s.id}">${on ? '✓ ' : '＋ '}${label}</span>`; };
  return `<div class="card sph-conn"><div class="sec" style="margin-top:0">🔗 Связи сферы · что входит сюда</div>
    <div class="sph-cg"><div class="sph-cgl">⚡ Вся секция по умолчанию → в эту сферу</div>
      ${defT('person', 'Люди')}${defT('metric', 'Трекинг')}${defT('practice', 'Психология')}
      <div class="muted" style="font-size:11px;margin-top:3px">включил — вся секция течёт сюда сама (отдельные элементы можно перетегать ниже)</div></div>
    <div class="sph-cg"><div class="sph-cgl">🎯 Цели</div>
      <span class="sph-pi" id="sphAutomap">↪ разложить категории по сферам (по именам)</span></div>
    ${grp('category', '🎯 Категории целей (авто-задачи)', sphPool.categories, 'title')}
    <div class="muted" style="font-size:11px;margin:2px 0 8px">Инфо и рутины — вручную:</div>
    ${grp('routine', '↻ Рутины', sphPool.routines, 'name')}
    ${grp('metric', '📊 Метрики (если не вся секция)', sphPool.metrics, 'name')}
    ${grp('practice', '🧠 Практики (если не вся секция)', sphPool.practices, 'name')}
    ${grp('person', '☻ Люди (если не вся секция)', sphPool.people, 'name')}
    ${grp('obligation', '💰 Обязательства/подписки', sphPool.obligations, 'name')}
  </div>`;
}

function bindDetail(s) {
  document.getElementById('sphBack').onclick = () => { sphOpen = null; sphEditConn = false; renderSpheres(); };
  document.getElementById('sphConnBtn').onclick = async () => {
    sphEditConn = !sphEditConn;
    if (sphEditConn && !sphPool) sphPool = await sphApi.pool();
    renderSpheres();
  };
  // привязать/отвязать отдельный элемент
  document.querySelectorAll('#screen-spheres [data-as]').forEach(el => el.onclick = async () => {
    const [kind, id, area] = el.dataset.as.split(':');
    await sphApi.assign(kind, +id, +area || null);
    sphPool = await sphApi.pool(); sphData = await sphApi.load(); renderSpheres();
  });
  // вся секция по умолчанию → эта сфера (или выключить)
  document.querySelectorAll('#screen-spheres [data-def]').forEach(el => el.onclick = async () => {
    const [kind, area] = el.dataset.def.split(':');
    await fetch('/api/spheres/default', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, areaId: area ? +area : null }) });
    sphPool = await sphApi.pool(); sphData = await sphApi.load(); renderSpheres();
  });
  document.getElementById('sphAutomap')?.addEventListener('click', async () => {
    const r = await fetch('/api/spheres/automap', { method: 'POST' }).then(x => x.json());
    alert(`Сопоставлено категорий по именам сфер: ${r.mapped}`);
    sphPool = await sphApi.pool(); sphData = await sphApi.load(); renderSpheres();
  });
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

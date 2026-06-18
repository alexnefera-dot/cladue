/* Сферы — экран поверх реальных секторов Колеса (/api/spheres).
   Правки идут в настоящие данные: оценка → /api/psy/wheel, поля сектора →
   /api/psy/areas/:id, задачи → /api/nodes/:id/toggle. Отдельного хранилища нет. */

let sphData = null, sphOpen = null;
const sesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const SPH_COL = ['#1e9e57', '#c43f3f', '#a87708', '#6b4fb5', '#2a76b5', '#364656', '#1e9e57', '#c43f3f'];
const colOf = i => SPH_COL[i % SPH_COL.length];

const sphApi = {
  load: () => fetch('/api/spheres').then(r => r.json()),
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
  if (!vals || vals.length < 2) return '';
  const p = 2, mn = Math.min(...vals), mx = Math.max(...vals), rng = (mx - mn) || 1;
  const pts = vals.map((v, i) => [p + i * (w - 2 * p) / (vals.length - 1), h - p - ((v - mn) / rng) * (h - 2 * p)]);
  return `<svg width="${w}" height="${h}" style="vertical-align:middle"><polyline fill="none" stroke="#5cb585" stroke-width="1.6" points="${pts.map(p => p.join(',')).join(' ')}"/></svg>`;
}

window.loadSpheres = async function () {
  ensureSphStyle();
  sphData = await sphApi.load();
  renderSpheres();
};

function renderSpheres() {
  const el = document.getElementById('screen-spheres');
  if (sphOpen == null) { el.innerHTML = sphOverview(); bindOverview(); }
  else {
    const s = sphData.find(x => x.id === sphOpen);
    if (!s) { sphOpen = null; return renderSpheres(); }
    el.innerHTML = sphDetail(s, sphData.indexOf(s));
    bindDetail(s);
  }
}

function sphOverview() {
  const scored = sphData.filter(s => s.score != null);
  const avg = scored.length ? (scored.reduce((a, s) => a + s.score, 0) / scored.length).toFixed(1) : '–';
  return `<h2 style="margin-bottom:2px">Сферы жизни</h2>
    <div class="muted" style="margin-bottom:14px">средний баланс ${avg}/10 · сектора Колеса как трассы: 10 = куда идём, оценка = где сейчас, шаг = что делаем. Данные реальные.</div>
    <div class="sph-ov">${sphData.map((s, i) => `
      <div class="sph-card" data-open="${s.id}">
        <div class="sph-ct">${sphRing(s.score, colOf(i), 40)}<div class="sph-cn">${sesc(s.name)}</div><div class="sph-cs" style="color:${colOf(i)}">${s.score ?? '–'}</div></div>
        <div class="sph-ideal">🎯 ${s.ideal ? sesc(s.ideal) : '<span class="muted">задать «10» — клик внутрь</span>'}</div>
        <div class="sph-step">→ ${s.step ? '<b>' + sesc(s.step) + '</b>' : '<span class="muted">нет шага</span>'}</div>
        ${s.tasks.length ? `<div class="sph-tags">${s.tasks.slice(0, 3).map(t => `<span class="sph-tag ${t.done ? 'done' : ''}">${t.done ? '✓' : '•'} ${sesc(t.title)}</span>`).join('')}</div>` : ''}
      </div>`).join('')}</div>`;
}
function bindOverview() {
  document.querySelectorAll('#screen-spheres [data-open]').forEach(c => c.onclick = () => { sphOpen = +c.dataset.open; renderSpheres(); });
}

function sphDetail(s, i) {
  const col = colOf(i);
  return `<div class="sph-crumb"><a id="sphBack">← Сферы</a></div>
    <div class="sph-hero">
      <div class="sph-hs">${sphRing(s.score, col, 70)}<div style="margin-top:4px">${sphSpark(s.history)}</div></div>
      <div class="sph-hi"><h2 style="margin:0 0 4px">${sesc(s.name)}</h2>
        <div class="sph-dest" data-edit="ideal">🎯 <b>10 = ${s.ideal ? sesc(s.ideal) : 'задать цель (клик)'}</b></div>
      </div>
    </div>
    <div class="sph-track"><div class="sph-rail"></div><div class="sph-fill" style="width:${(s.score ?? 0) * 10}%;background:${col}"></div>
      <div class="sph-you" style="left:${(s.score ?? 0) * 10}%">${s.score ?? '–'}</div><span class="sph-z">0</span><span class="sph-t10">10 ✦</span></div>
    <div class="muted" style="font-size:12.5px;margin-top:4px" data-edit="current_desc">где сейчас: ${s.current_desc ? sesc(s.current_desc) : '<span class="muted">описать (клик)</span>'}</div>
    <div class="sph-step-box"><span class="sph-l">СЛЕДУЮЩИЙ ШАГ</span>
      <b data-edit="step">${s.step ? sesc(s.step) : 'задать шаг (клик)'}</b>
      ${s.next_desc ? `<div class="muted" style="font-size:12.5px;margin-top:3px" data-edit="next_desc">${sesc(s.next_desc)}</div>` : ''}
      <div style="margin-top:7px"><span class="pill btn" id="sphStepTask">＋ шаг в задачи</span></div>
    </div>

    <div class="sec">🎯 Задачи сектора <span class="muted" style="font-weight:400">· из Целей</span></div>
    <div class="card">${s.tasks.length ? s.tasks.map(t => `
      <div class="task"><span class="cb ${t.done ? 'done' : ''}" data-tog="${t.id}"></span>
        ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
        <span class="t ${t.done ? 'done' : ''}">${sesc(t.title)}</span>
        ${t.due ? `<span class="meta">${t.due}</span>` : ''}</div>`).join('')
      : '<div class="empty">задач сектора нет — нажми «＋ шаг в задачи» или заведи в Целях</div>'}</div>

    <div class="sec">🪞 Ревизия · оценка сферы</div>
    <div class="card"><div class="muted" style="font-size:13px;margin-bottom:4px">Где сектор сейчас? Оценка пишется в Колесо.</div>
      <div class="sph-scoreset" id="sphScore"></div></div>

    <div class="sec">🔗 Связи с разделами</div>
    <div class="card"><div class="muted" style="font-size:13px">Здесь подтянутся рутины, трекинг, практики и финансы этой сферы — добавим тег «сфера» к элементам в v0.2. Сейчас живьём: цель (10), оценка с историей, шаг и задачи сектора — всё из реальных данных Pipboy.</div></div>`;
}

function bindDetail(s) {
  document.getElementById('sphBack').onclick = () => { sphOpen = null; renderSpheres(); };
  // оценка → реальное Колесо
  const sc = document.getElementById('sphScore'); let cur = s.score ?? 0;
  sc.innerHTML = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(i => `<b class="${i <= cur ? 'on' : ''}" data-s="${i}">${i}</b>`).join('');
  sc.onclick = async e => { const b = e.target.closest('b'); if (!b) return; await sphApi.score(s.id, +b.dataset.s); window.loadSpheres(); };
  // редактирование полей сектора → реальный wheel_areas
  document.querySelectorAll('#screen-spheres [data-edit]').forEach(el => el.onclick = async () => {
    const f = el.dataset.edit;
    const labels = { ideal: 'Цель (10 = …):', step: 'Следующий шаг:', current_desc: 'Где сейчас (описание):', next_desc: 'Что для шага надо:' };
    const v = prompt(labels[f], s[f] || '');
    if (v != null) { await sphApi.patch(s.id, { [f]: v.trim() }); window.loadSpheres(); }
  });
  // отметить задачу
  document.querySelectorAll('#screen-spheres [data-tog]').forEach(c => c.onclick = async () => { await sphApi.toggle(+c.dataset.tog); window.loadSpheres(); });
  // шаг → задача
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
    .sph-tags{margin-top:8px;display:flex;flex-wrap:wrap;gap:5px}.sph-tag{font-size:11px;background:var(--bg2);border:1px solid var(--line);border-radius:6px;padding:2px 7px}.sph-tag.done{color:var(--muted);text-decoration:line-through}
    .sph-crumb{font-size:12px;color:var(--muted);margin-bottom:10px}.sph-crumb a{color:var(--green);cursor:pointer}
    .sph-hero{display:flex;gap:18px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow-sm);padding:16px 18px}
    .sph-hi{flex:1;min-width:0}.sph-hs{text-align:center;flex:0 0 auto}
    .sph-dest{background:var(--green-soft);border:1px solid var(--green-dim);border-radius:10px;padding:8px 12px;font-size:14px;cursor:text}.sph-dest b{color:var(--green)}
    .sph-track{position:relative;height:32px;margin:14px 0 2px}.sph-rail{position:absolute;top:13px;left:0;right:0;height:7px;border-radius:99px;background:var(--bg2)}
    .sph-fill{position:absolute;top:13px;left:0;height:7px;border-radius:99px}
    .sph-you{position:absolute;top:-4px;transform:translateX(-50%);font:700 12px var(--mono);color:var(--green)}.sph-you::after{content:"▼";display:block;text-align:center;font-size:10px}
    .sph-z,.sph-t10{position:absolute;top:23px;font:600 9px var(--mono);color:var(--muted)}.sph-z{left:0}.sph-t10{right:0}
    .sph-step-box{background:rgba(168,119,8,.08);border-radius:10px;padding:11px 14px;margin-top:12px}.sph-step-box .sph-l{font:600 9px var(--mono);letter-spacing:.6px;color:var(--amber);display:block;margin-bottom:1px}.sph-step-box b{font-size:15px;cursor:text}
    .sph-scoreset{display:flex;gap:5px;flex-wrap:wrap}.sph-scoreset b{width:30px;height:30px;border-radius:8px;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font:600 13px var(--mono);cursor:pointer;color:var(--muted)}.sph-scoreset b.on{background:var(--green);color:#fff;border-color:var(--green)}
    [data-edit]{cursor:text}`;
  const st = document.createElement('style'); st.id = 'sph-style'; st.textContent = css;
  document.head.appendChild(st);
}

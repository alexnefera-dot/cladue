let state = null, selected = null;
const collapsed = new Set();

const KIND = { task: ['задача','ok'], decision: ['решение','dec'], question: ['вопрос','p2'],
               principle: ['принцип','p1'], idea: ['идея',''] };

const api = {
  tree: () => fetch('/api/tree').then(r => r.json()),
  suggest: id => fetch('/api/suggest/' + id).then(r => r.json()),
  patch: (id, b) => fetch('/api/nodes/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  toggle: id => fetch(`/api/nodes/${id}/toggle`, { method: 'POST' }).then(r => r.json()),
  add: b => fetch('/api/nodes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  link: b => fetch('/api/links', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  unlink: id => fetch('/api/links/' + id, { method: 'DELETE' }),
  dismiss: (a, b) => fetch('/api/dismiss', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ a, b }) }),
  search: q => fetch('/api/search?q=' + encodeURIComponent(q)).then(r => r.json()),
};

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

async function load() {
  state = await api.tree();
  renderBoard();
  renderStatus();
  if (selected) showCard(selected);
}

function renderStatus() {
  const typed = state.nodes.filter(n => n.kind).length;
  const blocked = state.nodes.filter(n => n.blocked).length;
  document.getElementById('statusbar').textContent =
    `строк: ${state.nodes.length} · типизировано: ${typed} · связей: ${state.links.length} · заблокировано: ${blocked}`;
}

function nodeRow(n, depth, idx) {
  const kids = byParent[n.id]?.length ?? 0;
  const [kl, kc] = n.kind ? (KIND[n.kind] ?? [n.kind, '']) : [null, null];
  const done = n.status === 'done' || n.status === 'accepted';
  const caret = kids
    ? `<span class="caret" data-fold="${n.id}">${collapsed.has(n.id) ? '▸' : '▾'}</span>`
    : '<span class="caret"></span>';
  const marker = !n.kind
    ? `<span class="bullet">${idx}.</span>`
    : (n.kind === 'task' || n.kind === 'decision')
      ? `<span class="cb ${n.kind === 'decision' ? 'dec' : ''} ${done ? 'done' : ''}" data-toggle="${n.id}"></span>`
      : `<span class="pill ${kc}">${kl}</span>`;
  return `<div class="task ${n.blocked ? 'blocked' : ''} ${selected === n.id ? 'sel' : ''}"
      data-id="${n.id}" style="padding-left:${6 + depth * 24}px">
    ${caret}${marker}
    ${n.priority ? `<span class="pill ${n.priority}">${n.priority}</span>` : ''}
    ${n.kind === 'task' || n.kind === 'decision' ? `<span class="pill ${kc}">${kl}</span>` : ''}
    <span class="t ${done ? 'done' : ''} ${depth === 0 ? 'top' : ''}">${esc(n.title)}</span>
    ${n.blocked ? '<span class="meta">⛔</span>' : ''}
    ${n.due_date ? `<span class="meta">${n.due_date}</span>` : ''}
  </div>`;
}

let byParent = {};
function renderBoard() {
  byParent = {};
  for (const n of state.nodes) (byParent[n.parent_id ?? 'root'] ??= []).push(n);
  const walk = (n, depth, idx) =>
    nodeRow(n, depth, idx) +
    (collapsed.has(n.id) ? '' : (byParent[n.id] ?? []).map((c, i) => walk(c, depth + 1, i + 1)).join(''));
  document.getElementById('board').innerHTML =
    `<div class="card">${(byParent['root'] ?? []).map((n, i) => walk(n, 0, i + 1)).join('')}</div>`;
}

function pathOf(id) {
  const map = Object.fromEntries(state.nodes.map(n => [n.id, n]));
  const out = [];
  let cur = map[id]?.parent_id;
  while (cur) { out.unshift(map[cur].title); cur = map[cur].parent_id; }
  return out.join(' → ');
}

const LINKLABEL = { related: '⛓ связано', blocks: '⛔ блокирует' };

async function showCard(id) {
  selected = id;
  renderBoard();
  const s = await api.suggest(id);
  const n = s.node;
  const kindBtns = ['task', 'decision', 'question', 'principle', 'idea']
    .map(k => `<span class="pill btn ${n.kind === k ? 'ok' : ''} ${s.kind === k ? 'pulse' : ''}"
       data-setkind="${k}">${KIND[k][0]}${s.kind === k ? ' ★' : ''}</span>`).join(' ');
  const prioBtns = ['P0', 'P1', 'P2', 'P3']
    .map(p => `<span class="pill btn ${p} ${n.priority === p ? 'ok' : ''}" data-setprio="${p}">${p}</span>`).join(' ');

  document.getElementById('insp').innerHTML = `
    <h3>Оригинал</h3>
    <div class="title">${esc(n.title)}</div>
    <div class="muted" style="margin-bottom:8px">${esc(pathOf(id) || 'корень списка')}</div>

    <h3>Тип <span class="hintstar">★ — подсказка, решаешь ты</span></h3>
    <div class="btnrow">${kindBtns} ${n.kind ? `<span class="pill btn" data-setkind="">сбросить</span>` : ''}</div>

    ${n.kind === 'task' || n.kind === 'decision' ? `
      <h3>Статус</h3>
      <span class="pill btn ok" data-toggle="${n.id}">${
        n.kind === 'decision'
          ? (n.status === 'open' ? '✓ принять решение' : '↺ снова открыть')
          : (n.status === 'done' ? '↺ вернуть в работу' : '✓ выполнено')}</span>` : ''}

    <h3>Приоритет</h3>
    <div class="btnrow">${prioBtns} ${n.priority ? `<span class="pill btn" data-setprio="">сбросить</span>` : ''}</div>

    <h3>Срок</h3>
    <div class="kv"><span>${n.due_date ?? 'не задан'}</span>
      ${n.due_date ? `<span class="pill btn" data-setdate="">убрать</span>` : ''}</div>
    ${s.date ? `<div class="suggest">💡 ${esc(s.date.reason)} →
      <span class="pill btn ok" data-setdate="${s.date.date}">поставить ${s.date.date}</span></div>` : ''}
    <input id="dateInput" placeholder="или вручную: 2026-08-31" value="">

    ${s.confirmed.length ? `<h3>Связи (подтверждённые)</h3>` + s.confirmed.map(l => `
      <div class="ritem"><div class="rt">${LINKLABEL[l.type] ?? l.type}${l.from_id === id && l.type === 'blocks' ? ' →' : l.type === 'blocks' ? ' ←' : ''} ${esc(l.title)}</div>
      <div class="rm"><span class="pill btn" data-unlink="${l.link_id}">✕ убрать связь</span></div></div>`).join('') : ''}

    <h3>📡 Предложения связей <span class="hintstar">система только предлагает</span></h3>
    ${s.links.length ? s.links.map(c => `
      <div class="ritem">
        <div class="rt">${esc(c.node.title)}</div>
        <div class="rm">${esc(pathOf(c.node.id))} · ${esc(c.reason)}</div>
        <div class="rm btnrow">
          <span class="pill btn ok" data-acc="${c.node.id}" data-type="related">⛓ связать</span>
          <span class="pill btn" data-acc="${c.node.id}" data-type="blocked-by">⛔ это блокер</span>
          <span class="pill btn" data-acc="${c.node.id}" data-type="blocks">→ я блокирую</span>
          <span class="pill btn" data-dis="${c.node.id}">✕ скрыть</span>
        </div>
      </div>`).join('')
    : '<div class="muted">кандидатов не найдено</div>'}
  `;

  document.getElementById('dateInput').addEventListener('keydown', async e => {
    if (e.key === 'Enter' && /^\d{4}-\d{2}-\d{2}$/.test(e.target.value)) {
      await api.patch(id, { due_date: e.target.value });
      await load();
    }
  });
}

document.addEventListener('click', async e => {
  const el = e.target;
  const id = selected;
  if (el.dataset.fold) {
    const f = +el.dataset.fold;
    collapsed.has(f) ? collapsed.delete(f) : collapsed.add(f);
    renderBoard(); return;
  }
  if (el.dataset.toggle) { e.stopPropagation(); await api.toggle(+el.dataset.toggle); await load(); return; }
  if ('setkind' in el.dataset) { await api.patch(id, { kind: el.dataset.setkind || null }); await load(); return; }
  if ('setprio' in el.dataset) { await api.patch(id, { priority: el.dataset.setprio || null }); await load(); return; }
  if ('setdate' in el.dataset) { await api.patch(id, { due_date: el.dataset.setdate || null }); await load(); return; }
  if (el.dataset.unlink) { await api.unlink(+el.dataset.unlink); await load(); return; }
  if (el.dataset.acc) {
    const other = +el.dataset.acc, type = el.dataset.type;
    if (type === 'blocked-by') await api.link({ from_id: other, to_id: id, type: 'blocks' });
    else if (type === 'blocks') await api.link({ from_id: id, to_id: other, type: 'blocks' });
    else await api.link({ from_id: id, to_id: other, type: 'related' });
    await load(); return;
  }
  if (el.dataset.dis) { await api.dismiss(id, +el.dataset.dis); await load(); return; }
  const row = el.closest('[data-id]');
  if (row) showCard(+row.dataset.id);
});

document.getElementById('addTitle').addEventListener('keydown', async e => {
  if (e.key !== 'Enter' || !e.target.value.trim()) return;
  await api.add({ title: e.target.value.trim(), parent_id: selected ?? null });
  e.target.value = '';
  await load();
});

let st;
document.getElementById('searchbox').addEventListener('input', e => {
  clearTimeout(st);
  st = setTimeout(async () => {
    const q = e.target.value.trim();
    const box = document.getElementById('searchres');
    if (!q) { box.innerHTML = ''; return; }
    const res = await api.search(q);
    box.innerHTML = res.map(t => `<div data-id="${t.id}">${esc(t.title)}</div>`).join('') || '<div>ничего</div>';
  }, 200);
});

load();

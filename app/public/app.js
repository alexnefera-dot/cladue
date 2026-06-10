let state = null, selected = null;

const KIND = { task: ['задача',''], decision: ['решение','dec'], question: ['вопрос','p2'],
               principle: ['принцип','p1'], idea: ['идея',''] };
const DEP = { blocks: 'блокирует', decision: 'зависит от решения', complements: 'дополняет' };

const api = {
  state: () => fetch('/api/state').then(r => r.json()),
  radar: id => fetch('/api/radar/' + id).then(r => r.json()),
  toggle: id => fetch(`/api/tasks/${id}/toggle`, { method: 'POST' }).then(r => r.json()),
  create: b => fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  search: q => fetch('/api/search?q=' + encodeURIComponent(q)).then(r => r.json()),
};

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

async function load() {
  state = await api.state();
  renderBoard();
  renderStatus();
  if (selected) showRadar(selected);
}

function renderStatus() {
  const open = state.tasks.filter(t => t.kind === 'decision' && t.status === 'open').length;
  const todo = state.tasks.filter(t => t.kind === 'task' && t.status === 'todo').length;
  const blocked = state.tasks.filter(t => t.blocked).length;
  document.getElementById('statusbar').textContent =
    `задач: ${todo} · решений открыто: ${open} · заблокировано: ${blocked}`;
}

function taskRow(t, depth = 0) {
  const [kindLabel, kindCls] = KIND[t.kind] ?? [t.kind, ''];
  const done = t.status === 'done' || t.status === 'accepted';
  const cb = t.kind === 'principle' || t.kind === 'idea' || t.kind === 'question'
    ? `<span class="pill ${kindCls}">${kindLabel}</span>`
    : `<span class="cb ${t.kind === 'decision' ? 'dec' : ''} ${done ? 'done' : ''}" data-toggle="${t.id}"></span>`;
  return `<div class="task ${t.blocked ? 'blocked' : ''} ${selected === t.id ? 'sel' : ''}" data-id="${t.id}" style="padding-left:${4 + depth * 26}px">
    ${cb}
    ${t.priority ? `<span class="pill ${t.priority}">${t.priority}</span>` : ''}
    ${t.kind === 'decision' ? `<span class="pill dec">решение</span>` : ''}
    <span class="t ${done ? 'done' : ''}">${esc(t.title)}</span>
    ${t.blocked ? '<span class="meta">⛔</span>' : ''}
    ${t.due_date ? `<span class="meta">${t.due_date}</span>` : ''}
  </div>`;
}

function renderBoard() {
  const byParent = {};
  for (const t of state.tasks) (byParent[t.parent_id ?? 'root'] ??= []).push(t);
  const tree = (t, depth) => taskRow(t, depth) + (byParent[t.id] ?? []).map(c => tree(c, depth + 1)).join('');
  document.getElementById('board').innerHTML = state.goals.map(g => {
    const roots = (byParent['root'] ?? []).filter(t => t.goal_id === g.id);
    return `<div class="sec">⚑ ${esc(g.title)}<span class="pr">· ${g.priority ?? ''}</span></div>
      <div class="card">${roots.map(t => tree(t, 0)).join('') || '<div class="empty">пусто</div>'}</div>`;
  }).join('');
  const sel = document.getElementById('addGoal');
  if (!sel.options.length)
    sel.innerHTML = state.goals.map(g => `<option value="${g.id}">${esc(g.title)}</option>`).join('');
}

function rItem(t, extra = '', warn = false) {
  return `<div class="ritem ${warn ? 'warn' : ''}" data-id="${t.id}">
    <div class="rt">${esc(t.title)}</div>
    <div class="rm">${extra}${t.due_date ? ' · ' + t.due_date : ''}${t.status === 'done' || t.status === 'accepted' ? ' · ✓' : ''}</div>
  </div>`;
}

async function showRadar(id) {
  selected = id;
  renderBoard();
  const r = await api.radar(id);
  const t = r.task;
  const sec = (title, items, fmt) => items.length
    ? `<h3>${title}</h3>` + items.map(fmt).join('')
    : '';
  document.getElementById('insp').innerHTML = `
    <h3>${KIND[t.kind]?.[0] ?? t.kind} · ${t.status}</h3>
    <div class="title">${esc(t.title)}</div>
    ${t.note ? `<div class="muted" style="margin-bottom:6px">${esc(t.note)}</div>` : ''}
    <div class="kv">Срок <b>${t.due_date ?? '—'}</b></div>
    <div class="kv">Приоритет <b>${t.priority ?? '—'}</b></div>
    <div class="kv">Источник <b>${esc(t.source_line ?? '—')}</b></div>
    <div style="margin:10px 0">
      ${t.kind === 'decision'
        ? `<span class="pill btn ok" data-toggle="${t.id}">${t.status === 'open' ? '✓ Принять решение' : '↺ Снова открыть'}</span>`
        : `<span class="pill btn ok" data-toggle="${t.id}">${t.status === 'done' ? '↺ Вернуть' : '✓ Выполнено'}</span>`}
    </div>
    ${sec('⛔ Блокируют эту задачу', r.blockers, b => rItem(b, DEP[b.dep_type] ?? b.dep_type, true))}
    ${sec('→ Эта запись блокирует', r.blocks, b => rItem(b, DEP[b.dep_type] ?? b.dep_type))}
    ${sec('📡 Упоминания в других ветках', r.mentions, m => rItem(m, m.source_line ?? ''))}
    ${sec('🕒 Окно времени ±60 дней', r.timeWindow, w => rItem(w, 'дедлайн рядом', true))}
    ${sec('◆ Открытые решения рядом', r.decisions, d => rItem(d, 'решение открыто', true))}
    ${sec('◇ Принципы ветки', r.principles, p => rItem(p, 'принцип'))}
    ${!r.blockers.length && !r.mentions.length && !r.timeWindow.length && !r.decisions.length
      ? '<h3>Радар</h3><div class="muted">Чисто — блокеров не найдено</div>' : ''}
  `;
}

document.addEventListener('click', async e => {
  const tg = e.target.closest('[data-toggle]');
  if (tg) { e.stopPropagation(); await api.toggle(+tg.dataset.toggle); await load(); return; }
  const row = e.target.closest('[data-id]');
  if (row) showRadar(+row.dataset.id);
});

document.getElementById('addTitle').addEventListener('keydown', async e => {
  if (e.key !== 'Enter') return;
  let title = e.target.value.trim();
  if (!title) return;
  const pm = title.match(/\bp([0-3])\b/i);
  const dm = title.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  if (pm) title = title.replace(pm[0], '').trim();
  if (dm) title = title.replace(dm[0], '').trim();
  await api.create({
    title,
    kind: document.getElementById('addKind').value,
    goal_id: +document.getElementById('addGoal').value,
    priority: pm ? 'P' + pm[1] : null,
    due_date: dm ? dm[1] : null,
  });
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

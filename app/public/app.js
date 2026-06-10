let state = null;
let selected = null;            // строка, чья карточка открыта
let picked = new Set();         // мультивыбор
let visibleOrder = [];          // порядок видимых строк (для Shift-выбора)
const collapsed = new Set();

const KIND = { task: ['задача','ok'], decision: ['решение','dec'], question: ['вопрос','p2'],
               principle: ['принцип','p1'], idea: ['идея',''], worry: ['тревога','p0'] };
const LINKLABEL = { related: '⛓ связано', blocks: '⛔ блокирует' };

const api = {
  tree: () => fetch('/api/tree').then(r => r.json()),
  suggest: id => fetch('/api/suggest/' + id).then(r => r.json()),
  patch: (id, b) => fetch('/api/nodes/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  toggle: id => fetch(`/api/nodes/${id}/toggle`, { method: 'POST' }).then(r => r.json()),
  add: b => fetch('/api/nodes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  move: (id, parent_id) => fetch(`/api/nodes/${id}/move`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ parent_id }) }).then(r => r.json()),
  import: b => fetch('/api/import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  link: b => fetch('/api/links', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  del: id => fetch('/api/nodes/' + id, { method: 'DELETE' }).then(r => r.json()),
  unlink: id => fetch('/api/links/' + id, { method: 'DELETE' }),
  dismiss: (a, b) => fetch('/api/dismiss', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ a, b }) }),
  search: q => fetch('/api/search?q=' + encodeURIComponent(q)).then(r => r.json()),
};

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

async function load() {
  state = await api.tree();
  renderBoard();
  renderStatus();
  if (selected) showCard(selected, { silent: true });
}

let byParent = {};

function countItems(catId) {
  let c = 0;
  const walk = id => (byParent[id] ?? []).forEach(k => { if (!k.is_category) c++; walk(k.id); });
  walk(catId);
  return c ? c + ' зап.' : 'пусто';
}

function renderStatus() {
  const real = state.nodes.filter(n => !n.is_category);
  const typed = real.filter(n => n.kind).length;
  const blocked = real.filter(n => n.blocked).length;
  const inboxId = state.nodes.find(n => n.is_category && n.title.includes('Инбокс'))?.id;
  const inbox = inboxId ? state.nodes.filter(n => n.parent_id === inboxId).length : 0;
  document.getElementById('statusbar').textContent =
    `записей: ${real.length} · типизировано: ${typed} · связей: ${state.links.length} · заблокировано: ${blocked} · в инбоксе: ${inbox}`;
}

function nodeRow(n, depth, idx) {
  const kids = byParent[n.id]?.length ?? 0;
  const done = n.status === 'done' || n.status === 'accepted';
  const caret = kids
    ? `<span class="caret" data-fold="${n.id}">${collapsed.has(n.id) ? '▸' : '▾'}</span>`
    : '<span class="caret"></span>';
  const isPicked = picked.has(n.id);
  if (n.is_category) {
    return `<div class="task cat ${isPicked ? 'sel' : ''}" data-id="${n.id}" style="padding-left:${6 + depth * 24}px">
      ${caret}<span class="folder">▣</span><span class="t top">${esc(n.title)}</span>
      <span class="meta">${countItems(n.id)}</span></div>`;
  }
  const [kl, kc] = n.kind ? (KIND[n.kind] ?? [n.kind, '']) : [null, null];
  const marker = !n.kind
    ? `<span class="bullet">${idx}.</span>`
    : (n.kind === 'task' || n.kind === 'decision')
      ? `<span class="cb ${n.kind === 'decision' ? 'dec' : ''} ${done ? 'done' : ''}" data-toggle="${n.id}"></span>`
      : `<span class="pill ${kc}">${kl}</span>`;
  return `<div class="task ${n.blocked ? 'blocked' : ''} ${isPicked ? 'sel' : ''}" draggable="true"
      data-id="${n.id}" style="padding-left:${6 + depth * 24}px">
    ${caret}${marker}
    ${n.priority ? `<span class="pill ${n.priority}">${n.priority}</span>` : ''}
    ${(n.kind === 'task' || n.kind === 'decision') ? `<span class="pill ${kc}">${kl}</span>` : ''}
    <span class="t ${done ? 'done' : ''}">${esc(n.title)}</span>
    ${n.blocked ? '<span class="meta">⛔</span>' : ''}
    ${n.due_date ? `<span class="meta">${n.due_date}</span>` : ''}
  </div>`;
}

function renderBoard() {
  byParent = {};
  for (const n of state.nodes) (byParent[n.parent_id ?? 'root'] ??= []).push(n);
  visibleOrder = [];
  const walk = (n, depth, idx) => {
    visibleOrder.push(n.id);
    return nodeRow(n, depth, idx) +
      (collapsed.has(n.id) ? '' : (byParent[n.id] ?? []).map((c, i) => walk(c, depth + 1, i + 1)).join(''));
  };
  document.getElementById('board').innerHTML =
    `<div class="card">${(byParent['root'] ?? []).map((n, i) => walk(n, 0, i + 1)).join('')}</div>`;
  renderBulkbar();
}

function renderBulkbar() {
  const bar = document.getElementById('bulkbar');
  if (picked.size <= 1) { bar.style.display = 'none'; return; }
  bar.style.display = 'flex';
  document.getElementById('bulkCount').textContent = `выбрано: ${picked.size}`;
  const sel = document.getElementById('bulkTarget');
  if (!sel.options.length) sel.innerHTML = `<option value="">— куда —</option>` + catOptions(null);
}

function catOptions(currentParent) {
  const walk = (pid, depth) => (byParent[pid] ?? [])
    .filter(n => n.is_category)
    .map(n => `<option value="${n.id}" ${n.id === currentParent ? 'selected' : ''}>${' '.repeat(depth * 3)}${esc(n.title)}</option>`
         + walk(n.id, depth + 1)).join('');
  return walk('root', 0);
}

function pathOf(id) {
  const map = Object.fromEntries(state.nodes.map(n => [n.id, n]));
  const out = [];
  let cur = map[id]?.parent_id;
  while (cur) { out.unshift(map[cur].title); cur = map[cur].parent_id; }
  return out.join(' → ');
}

async function showCard(id, { silent = false } = {}) {
  selected = id;
  if (!silent) { picked = new Set([id]); }
  renderBoard();
  const s = await api.suggest(id);
  if (!s || s.error) return;
  const n = s.node;

  if (n.is_category) {
    document.getElementById('insp').innerHTML = `
      <h3>Категория</h3>
      <div class="title">${esc(n.title)}</div>
      <div class="muted">${esc(pathOf(id) || 'верхний уровень')}</div>
      <div class="muted" style="margin-top:8px">Внутри: ${countItems(id)}.
        Строка внизу добавит запись сюда; перетаскивай строки прямо на категорию.</div>`;
    return;
  }

  const kindBtns = ['task', 'decision', 'question', 'principle', 'idea', 'worry']
    .map(k => `<span class="pill btn ${n.kind === k ? 'ok' : ''} ${s.kind === k ? 'pulse' : ''}"
       data-setkind="${k}">${KIND[k][0]}${s.kind === k ? ' ★' : ''}</span>`).join(' ');
  const prioBtns = ['P0', 'P1', 'P2', 'P3']
    .map(p => `<span class="pill btn ${p} ${n.priority === p ? 'ok' : ''}" data-setprio="${p}">${p}</span>`).join(' ');

  const subCount = (() => { let c = 0; const w = x => (byParent[x] ?? []).forEach(k => { c++; w(k.id); }); w(id); return c; })();

  document.getElementById('insp').innerHTML = `
    <h3>Оригинал <span class="hintstar">двойной клик по строке — правка текста</span></h3>
    <div class="title">${esc(n.title)}</div>
    <div class="muted" style="margin-bottom:8px">${esc(pathOf(id) || 'корень')}</div>

    <h3>Заметка / рассуждение</h3>
    <textarea id="noteEdit" rows="3" placeholder="мысли, контекст, почему…">${esc(n.note)}</textarea>
    <div class="btnrow"><span class="pill btn ok" id="noteSave">сохранить заметку</span></div>

    <h3>Раскидать: переместить в…</h3>
    <select id="moveSel" class="movesel">
      <option value="">— выбери категорию —</option>
      ${catOptions(n.parent_id)}
    </select>
    <div class="muted" style="font-size:11px">вложить в другую запись — перетащи строку в дереве</div>

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

    <h3>Опасная зона</h3>
    <span class="pill btn danger" data-del="${n.id}">🗑 удалить${subCount ? ` (и ${subCount} вложенных)` : ''}</span>
  `;

  document.getElementById('noteSave')?.addEventListener('click', async () => {
    await api.patch(id, { note: document.getElementById('noteEdit').value.trim() });
    await load();
  });
  document.getElementById('moveSel')?.addEventListener('change', async e => {
    if (!e.target.value) return;
    const r = await api.move(id, +e.target.value);
    if (r.error) alert(r.error);
    await load();
  });
  document.getElementById('dateInput')?.addEventListener('keydown', async e => {
    if (e.key === 'Enter' && /^\d{4}-\d{2}-\d{2}$/.test(e.target.value)) {
      await api.patch(id, { due_date: e.target.value });
      await load();
    }
  });
}

// ===== Клики: выбор, мультивыбор, действия =====
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
  if (el.dataset.del) {
    const did = +el.dataset.del;
    const n = state.nodes.find(x => x.id === did);
    if (confirm(`Удалить «${n?.title}»${el.textContent.includes('вложенных') ? ' со всеми вложенными' : ''}? Отменить нельзя.`)) {
      await api.del(did);
      selected = null; picked.delete(did);
      document.getElementById('insp').innerHTML = '<h3>Карточка узла</h3><div class="muted">Удалено.</div>';
      await load();
    }
    return;
  }

  const row = el.closest('.task[data-id]');
  if (!row) return;
  const rid = +row.dataset.id;
  if (e.metaKey || e.ctrlKey) {                       // ⌘-клик: добавить/убрать из выбора
    picked.has(rid) ? picked.delete(rid) : picked.add(rid);
    selected = rid;
    renderBoard(); return;
  }
  if (e.shiftKey && selected) {                       // Shift-клик: диапазон
    const a = visibleOrder.indexOf(selected), b = visibleOrder.indexOf(rid);
    if (a !== -1 && b !== -1) {
      picked = new Set(visibleOrder.slice(Math.min(a, b), Math.max(a, b) + 1));
      renderBoard(); return;
    }
  }
  showCard(rid);
});

// ===== Двойной клик: правка текста на месте =====
document.addEventListener('dblclick', e => {
  const row = e.target.closest('.task[data-id]');
  if (!row) return;
  const id = +row.dataset.id;
  const n = state.nodes.find(x => x.id === id);
  const t = row.querySelector('.t');
  if (!t || row.querySelector('.inlineedit')) return;
  const input = document.createElement('input');
  input.className = 'inlineedit';
  input.value = n.title;
  t.replaceWith(input);
  input.focus(); input.select();
  let saved = false;
  const save = async () => {
    if (saved) return; saved = true;
    const v = input.value.trim();
    if (v && v !== n.title) await api.patch(id, { title: v });
    await load();
  };
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') save();
    if (ev.key === 'Escape') { saved = true; load(); }
  });
  input.addEventListener('blur', save);
});

// ===== Drag & drop: вложенность любого в любое =====
let draggedId = null;
document.addEventListener('dragstart', e => {
  const row = e.target.closest('.task[data-id]');
  if (!row) return;
  draggedId = +row.dataset.id;
  if (!picked.has(draggedId)) { picked = new Set([draggedId]); renderBoard(); }
  e.dataTransfer.effectAllowed = 'move';
});
document.addEventListener('dragover', e => {
  const row = e.target.closest('.task[data-id]');
  if (!row || picked.has(+row.dataset.id)) return;
  e.preventDefault();
  row.classList.add('dropinto');
});
document.addEventListener('dragleave', e => {
  e.target.closest('.task[data-id]')?.classList.remove('dropinto');
});
document.addEventListener('drop', async e => {
  const row = e.target.closest('.task[data-id]');
  document.querySelectorAll('.dropinto').forEach(x => x.classList.remove('dropinto'));
  if (!row || draggedId == null) return;
  e.preventDefault();
  const target = +row.dataset.id;
  const ids = picked.has(draggedId) ? [...picked] : [draggedId];
  for (const mid of ids) {
    if (mid === target) continue;
    const r = await api.move(mid, target);
    if (r.error) { alert(`«${state.nodes.find(n => n.id === mid)?.title}»: ${r.error}`); }
  }
  collapsed.delete(target);
  draggedId = null;
  await load();
});
document.addEventListener('dragend', () => {
  document.querySelectorAll('.dropinto').forEach(x => x.classList.remove('dropinto'));
  draggedId = null;
});

// ===== Массовое перемещение =====
document.getElementById('bulkGo').addEventListener('click', async () => {
  const target = +document.getElementById('bulkTarget').value;
  if (!target) return;
  for (const mid of picked) {
    if (mid === target) continue;
    const r = await api.move(mid, target);
    if (r.error) alert(r.error);
  }
  picked = new Set();
  await load();
});
document.getElementById('bulkDel').addEventListener('click', async () => {
  if (!confirm(`Удалить ${picked.size} выбранных записей (с их вложенными)? Отменить нельзя.`)) return;
  for (const mid of picked) await api.del(mid);
  picked = new Set(); selected = null;
  await load();
});
document.getElementById('bulkClear').addEventListener('click', () => {
  picked = selected ? new Set([selected]) : new Set();
  renderBoard();
});

// ===== Добавление строки (вставка нескольких строк = импорт) =====
document.getElementById('addTitle').addEventListener('paste', async e => {
  const text = e.clipboardData.getData('text');
  if (!text.includes('\n')) return;
  e.preventDefault();
  const inbox = state.nodes.find(n => n.is_category && n.title.includes('Инбокс'));
  const target = selected ?? inbox?.id ?? null;
  const r = await api.import({ parent_id: target, text });
  if (target) collapsed.delete(target);
  e.target.value = '';
  await load();
  document.getElementById('statusbar').textContent += ` · ⤓ импортировано: ${r.imported}`;
});
document.getElementById('addTitle').addEventListener('keydown', async e => {
  if (e.key !== 'Enter' || !e.target.value.trim()) return;
  await api.add({ title: e.target.value.trim(), parent_id: selected ?? null });
  if (selected) collapsed.delete(selected);
  e.target.value = '';
  await load();
});

// ===== Импорт =====
document.getElementById('importBtn').addEventListener('click', () => {
  const panel = document.getElementById('importPanel');
  const show = panel.style.display === 'none';
  panel.style.display = show ? 'block' : 'none';
  if (show) {
    const sel = document.getElementById('importTarget');
    sel.innerHTML = catOptions(null);
    const inbox = state.nodes.find(n => n.is_category && n.title.includes('Инбокс'));
    if (inbox) sel.value = inbox.id;
    document.getElementById('importText').focus();
  }
});
document.getElementById('importClose').addEventListener('click', () => {
  document.getElementById('importPanel').style.display = 'none';
});
document.getElementById('importGo').addEventListener('click', async () => {
  const text = document.getElementById('importText').value;
  if (!text.trim()) return;
  const target = +document.getElementById('importTarget').value || null;
  const r = await api.import({ parent_id: target, text });
  document.getElementById('importText').value = '';
  document.getElementById('importPanel').style.display = 'none';
  if (target) collapsed.delete(target);
  await load();
  document.getElementById('statusbar').textContent += ` · ⤓ импортировано: ${r.imported}`;
});

// ===== Поиск =====
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

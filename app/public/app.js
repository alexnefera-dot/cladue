let state = null;
let selected = null;            // строка, чья карточка открыта
let picked = new Set();         // мультивыбор
let visibleOrder = [];          // порядок видимых строк (для Shift-выбора)
let view = 'tree';              // tree | tasker
let taskerView = 'prio';        // prio | dates | groups
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
  merge: b => fetch('/api/merge', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
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
  const pct = real.length ? Math.round(typed / real.length * 100) : 0;
  document.getElementById('statusbar').textContent =
    `разобрано: ${typed} из ${real.length} (${pct}%) · связей: ${state.links.length} · заблокировано: ${blocked} · в инбоксе: ${inbox}`;
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
      <span class="meta">${countItems(n.id)}</span>
      <span class="rowbtn" data-addchild="${n.id}" title="добавить внутрь">＋</span></div>`;
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
    ${n.repeat ? '<span class="meta" title="повторяющаяся">🔁</span>' : ''}
    ${n.due_date ? `<span class="meta">${n.due_date}</span>` : ''}
    <span class="rowbtn" data-addchild="${n.id}" title="добавить вложенную">＋</span>
    <span class="rowbtn del" data-delrow="${n.id}" title="удалить">✕</span>
  </div>`;
}

function renderBoard() {
  byParent = {};
  for (const n of state.nodes) (byParent[n.parent_id ?? 'root'] ??= []).push(n);
  document.querySelectorAll('#viewtabs [data-vw]').forEach(t =>
    t.classList.toggle('ok', t.dataset.vw === view));
  if (view === 'tasker') {
    const groups = taskerView === 'prio' ? prioGroups()
      : taskerView === 'dates' ? dateGroups() : catGroups();
    return renderFlat(groups, `
      <div class="viewtabs" style="margin-bottom:8px">
        <span class="pill btn ${taskerView === 'prio' ? 'ok' : ''}" data-tvw="prio">Приоритеты</span>
        <span class="pill btn ${taskerView === 'dates' ? 'ok' : ''}" data-tvw="dates">Сроки</span>
        <span class="pill btn ${taskerView === 'groups' ? 'ok' : ''}" data-tvw="groups">Группы</span>
      </div>`);
  }
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

// ===== Плоские виды поверх категорий =====
function actionable() {  // типизированные задачи и решения, не закрытые
  return state.nodes.filter(n => !n.is_category
    && (n.kind === 'task' || n.kind === 'decision')
    && !['done', 'accepted'].includes(n.status));
}

function prioGroups() {
  const g = { P0: [], P1: [], P2: [], P3: [], 'без приоритета': [] };
  for (const n of actionable()) (g[n.priority ?? 'без приоритета'] ?? g['без приоритета']).push(n);
  return Object.entries(g);
}

function dateGroups() {
  const today = new Date().toISOString().slice(0, 10);
  const week = new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10);
  const g = { '⚠ просрочено': [], 'сегодня': [], 'эта неделя': [], 'позже': [], 'без срока': [] };
  for (const n of actionable()) {
    if (!n.due_date) g['без срока'].push(n);
    else if (n.due_date < today) g['⚠ просрочено'].push(n);
    else if (n.due_date === today) g['сегодня'].push(n);
    else if (n.due_date <= week) g['эта неделя'].push(n);
    else g['позже'].push(n);
  }
  for (const k of Object.keys(g)) g[k].sort((a, b) => (a.due_date ?? '9') < (b.due_date ?? '9') ? -1 : 1);
  return Object.entries(g);
}

// Группы задачника = корневые категории дерева
function catGroups() {
  const map = Object.fromEntries(state.nodes.map(n => [n.id, n]));
  const rootOf = n => {
    let cur = n;
    while (cur.parent_id && map[cur.parent_id]) {
      const p = map[cur.parent_id];
      if (p.is_category && !p.parent_id) return p.title;
      cur = p;
    }
    return cur.is_category ? cur.title : 'без группы';
  };
  const g = {};
  for (const n of actionable()) (g[rootOf(n)] ??= []).push(n);
  return Object.entries(g).sort((a, b) => b[1].length - a[1].length);
}

function renderFlat(groups, headerHtml = '') {
  visibleOrder = [];
  document.getElementById('board').innerHTML = headerHtml + groups
    .filter(([, items]) => items.length)
    .map(([name, items]) => `<div class="sec">${name} · ${items.length}</div><div class="card">` +
      items.map(n => {
        visibleOrder.push(n.id);
        const done = n.status === 'done' || n.status === 'accepted';
        const [kl, kc] = KIND[n.kind];
        return `<div class="task ${n.blocked ? 'blocked' : ''} ${picked.has(n.id) ? 'sel' : ''}" data-id="${n.id}">
          <span class="cb ${n.kind === 'decision' ? 'dec' : ''} ${done ? 'done' : ''}" data-toggle="${n.id}"></span>
          ${n.priority ? `<span class="pill ${n.priority}">${n.priority}</span>` : ''}
          <span class="pill ${kc}">${kl}</span>
          <span class="t">${esc(n.title)}</span>
          ${n.blocked ? '<span class="meta">⛔</span>' : ''}
          <span class="meta">${esc(pathOf(n.id))}</span>
          ${n.due_date ? `<span class="meta">${n.due_date}</span>` : ''}
        </div>`;
      }).join('') + '</div>').join('')
    || '<div class="card"><div class="empty">Нет типизированных задач/решений — типизируй записи в дереве, и они появятся здесь</div></div>';
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
  if (!silent) { picked = new Set([id]); document.getElementById('insp').classList.add('open'); }
  renderBoard();
  const [s, nodeLog] = await Promise.all([
    api.suggest(id),
    fetch(`/api/nodes/${id}/log`).then(r => r.json()).catch(() => []),
  ]);
  if (!s || s.error) return;
  const n = s.node;

  if (n.is_category) {
    document.getElementById('insp').innerHTML = `
      <span class="insp-close">✕</span>
      <h3>Категория</h3>
      <div class="title">${esc(n.title)}</div>
      <div class="muted">${esc(pathOf(id) || 'верхний уровень')}</div>
      <div class="muted" style="margin-top:8px">Внутри: ${countItems(id)}. Перетаскивай строки прямо на категорию.</div>
      <div class="btnrow" style="margin-top:10px">
        <span class="pill btn ok" data-addsubcat="${n.id}">＋ подкатегория</span>
        <span class="pill btn danger" data-delrow="${n.id}">🗑 удалить категорию</span>
      </div>`;
    return;
  }

  const kindBtns = ['task', 'decision', 'question', 'principle', 'idea', 'worry']
    .map(k => `<span class="pill btn ${n.kind === k ? 'ok' : ''} ${s.kind === k ? 'pulse' : ''}"
       data-setkind="${k}">${KIND[k][0]}${s.kind === k ? ' ★' : ''}</span>`).join(' ');
  const prioBtns = ['P0', 'P1', 'P2', 'P3']
    .map(p => `<span class="pill btn ${p} ${n.priority === p ? 'ok' : ''}" data-setprio="${p}">${p}</span>`).join(' ');

  const subCount = (() => { let c = 0; const w = x => (byParent[x] ?? []).forEach(k => { c++; w(k.id); }); w(id); return c; })();

  document.getElementById('insp').innerHTML = `
    <span class="insp-close">✕</span>
    <h3>Оригинал</h3>
    <div class="title">${esc(n.title)}</div>
    <div class="muted" style="margin-bottom:4px">${esc(pathOf(id) || 'корень')}</div>
    <div class="btnrow">
      <span class="pill btn" data-editrow="${n.id}">✎ править текст</span>
      <span class="pill btn ok" data-planpage="${n.id}">📝 план</span>
    </div>

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

    ${n.kind === 'decision' ? `
      <h3>Что решено</h3>
      <textarea id="answerEdit" rows="2" placeholder="формулировка решения — останется в истории…">${esc(n.answer ?? '')}</textarea>
      <div class="btnrow"><span class="pill btn ok" id="answerSave">сохранить решение</span></div>` : ''}

    ${n.kind === 'task' ? `
      <h3>Повтор</h3>
      <div class="btnrow">${[['', 'нет'], ['weekly', 'неделя'], ['monthly', 'месяц'], ['yearly', 'год']]
        .map(([v, l]) => `<span class="pill btn ${(n.repeat ?? '') === v ? 'ok' : ''}" data-setrepeat="${v}">${l}</span>`).join('')}</div>
      ${n.repeat && !n.due_date ? '<div class="meta amber">для повтора нужен срок</div>' : ''}

      <h3>Лог хода</h3>
      ${nodeLog.map(l => `<div class="kv"><span>${l.date.slice(5)}</span>
        <b style="text-align:right">${esc(l.note)} <span class="rowbtn del" style="opacity:1" data-dellog="${l.id}">✕</span></b></div>`).join('')
        || '<div class="muted" style="font-size:11.5px">записей нет</div>'}
      <input id="logInput" placeholder="запись хода… (Enter)" style="width:100%;border:1px solid var(--line);border-radius:7px;padding:6px 8px;font:12px var(--sans);margin-top:4px;background:var(--panel)">` : ''}

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
          <span class="pill btn" data-merge="${c.node.id}">⥂ объединить</span>
          <span class="pill btn" data-dis="${c.node.id}">✕ скрыть</span>
        </div>
      </div>`).join('')
    : '<div class="muted">кандидатов не найдено</div>'}

    ${s.context?.principles.length ? `<h3>◇ Принципы ветки <span class="hintstar">информационно</span></h3>` +
      s.context.principles.map(p => `<div class="ritem" data-id="${p.id}"><div class="rt">${esc(p.title)}</div>
        <div class="rm">${esc(pathOf(p.id))}</div></div>`).join('') : ''}
    ${s.context?.decisions.length ? `<h3>◆ Открытые решения рядом</h3>` +
      s.context.decisions.map(d => `<div class="ritem warn" data-id="${d.id}"><div class="rt">${esc(d.title)}</div>
        <div class="rm">${esc(pathOf(d.id))} · решение открыто</div></div>`).join('') : ''}
    ${s.context?.payments?.length ? `<h3>◈ Платежи рядом по времени <span class="hintstar">из Финансов, ±60 дн.</span></h3>` +
      s.context.payments.map(o => `<div class="ritem warn"><div class="rt">${esc(o.name)}</div>
        <div class="rm">${o.next_date} · ${Math.round(o.amount).toLocaleString('ru-RU')} ${esc(o.currency)}</div></div>`).join('') : ''}

    <h3>Опасная зона</h3>
    <span class="pill btn danger" data-del="${n.id}">🗑 удалить${subCount ? ` (и ${subCount} вложенных)` : ''}</span>
  `;

  document.getElementById('answerSave')?.addEventListener('click', async () => {
    await api.patch(id, { answer: document.getElementById('answerEdit').value.trim() || null });
    await load();
  });
  document.getElementById('noteSave')?.addEventListener('click', async () => {
    await api.patch(id, { note: document.getElementById('noteEdit').value.trim() });
    await load();
  });
  document.getElementById('logInput')?.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !e.target.value.trim()) return;
    await fetch(`/api/nodes/${id}/log`, { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: e.target.value.trim() }) });
    showCard(id, { silent: true });
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
  if (el.dataset.toggle) {
    e.stopPropagation();
    if (!await window.preflightOk(+el.dataset.toggle)) return;
    await api.toggle(+el.dataset.toggle);
    await load();
    return;
  }
  if ('setrepeat' in el.dataset) { await api.patch(id, { repeat: el.dataset.setrepeat || null }); await load(); return; }
  if (el.dataset.dellog) {
    await fetch('/api/nodelog/' + el.dataset.dellog, { method: 'DELETE' });
    showCard(id, { silent: true });
    return;
  }
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
  if (el.dataset.editrow) { startInlineEdit(+el.dataset.editrow); return; }
  if (el.dataset.planpage) {
    const r = await fetch(`/api/nodes/${el.dataset.planpage}/plan`, { method: 'POST' }).then(x => x.json());
    if (r.error) alert(r.error); else window.openPage(r.id);
    return;
  }
  if (el.dataset.addchild) { addChildInput(+el.dataset.addchild); return; }
  if (el.dataset.vw) { view = el.dataset.vw; renderBoard(); return; }
  if (el.dataset.tvw) { taskerView = el.dataset.tvw; renderBoard(); return; }
  if (el.dataset.addsubcat) {
    const name = prompt('Название подкатегории:');
    if (name?.trim()) { await api.add({ title: name.trim(), parent_id: +el.dataset.addsubcat, is_category: 1 }); await load(); }
    return;
  }
  if (el.id === 'addCatBtn') {
    const name = prompt('Название новой категории (верхний уровень):');
    if (name?.trim()) { await api.add({ title: name.trim(), parent_id: null, is_category: 1 }); await load(); }
    return;
  }
  if (el.dataset.merge) {
    const other = +el.dataset.merge;
    const o = state.nodes.find(x => x.id === other);
    if (confirm(`Объединить «${o?.title}» с текущей записью?\nВложенные и связи переедут сюда, дубль удалится, дедлайн возьмём более ранний.`)) {
      const r = await api.merge({ keep_id: id, dup_id: other });
      if (r.error) alert(r.error);
      await load();
    }
    return;
  }
  if (el.dataset.delrow) {
    const did = +el.dataset.delrow;
    const n = state.nodes.find(x => x.id === did);
    let cnt = 0; const w = x => (byParent[x] ?? []).forEach(k => { cnt++; w(k.id); }); w(did);
    if (confirm(`Удалить «${n?.title}»${cnt ? ` и ${cnt} вложенных` : ''}?`)) {
      await api.del(did);
      if (selected === did) selected = null;
      picked.delete(did);
      await load();
    }
    return;
  }
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

  const row = el.closest('[data-id]');
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
  // двойной клик определяем вручную: одиночный клик перерисовывает дерево,
  // и нативный dblclick до подменённого DOM-элемента не доходит
  const now = Date.now();
  if (lastClick.id === rid && now - lastClick.t < 450) {
    lastClick = { id: null, t: 0 };
    startInlineEdit(rid);
    return;
  }
  lastClick = { id: rid, t: now };
  showCard(rid);
});

let lastClick = { id: null, t: 0 };

// «＋»: поле новой строки прямо под родителем; Enter — сохранить и добавить ещё
function addChildInput(pid) {
  collapsed.delete(pid);
  renderBoard();
  const row = document.querySelector(`.task[data-id="${pid}"]`);
  if (!row) return;
  const div = document.createElement('div');
  div.className = 'task';
  div.style.paddingLeft = ((parseInt(row.style.paddingLeft) || 6) + 24) + 'px';
  div.innerHTML = '<span class="caret"></span><span class="bullet">＋</span>';
  const input = document.createElement('input');
  input.className = 'inlineedit';
  input.placeholder = 'новая строка… (Enter — сохранить и ещё одну, Esc — закончить)';
  div.appendChild(input);
  row.after(div);
  input.focus();
  let done = false;
  const save = async (andNext) => {
    if (done) return; done = true;
    const v = input.value.trim();
    if (v) {
      await api.add({ title: v, parent_id: pid });
      await load();
      if (andNext) addChildInput(pid);
    } else div.remove();
  };
  input.addEventListener('click', ev => ev.stopPropagation());
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') save(true);
    if (ev.key === 'Escape') { done = true; div.remove(); }
  });
  input.addEventListener('blur', () => save(false));
}

function startInlineEdit(id) {
  const row = document.querySelector(`.task[data-id="${id}"]`);
  const n = state.nodes.find(x => x.id === id);
  const t = row?.querySelector('.t');
  if (!n || !t || row.querySelector('.inlineedit')) return;
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
  input.addEventListener('click', ev => ev.stopPropagation());
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') save();
    if (ev.key === 'Escape') { saved = true; load(); }
  });
  input.addEventListener('blur', save);
}

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


// ===== Переключение экранов =====
const SCREENS = { today: 'loadToday', list: null, fin: 'loadFin', cal: 'loadCal', people: 'loadPeople', routines: 'loadRoutines', notes: 'loadNotes', psy: 'loadPsy', track: 'loadTrack', settings: 'loadSettings' };
window.showScreen = function (scr) {
  document.querySelectorAll('.side .item').forEach(i =>
    i.classList.toggle('active', i.dataset.screen === scr));
  for (const key of Object.keys(SCREENS))
    document.getElementById('screen-' + key).style.display = key === scr ? 'block' : 'none';
  // правая панель (карточка записи) имеет смысл только в Задачах
  const insp = document.querySelector('.insp');
  insp.style.display = scr === 'list' ? 'block' : 'none';
  insp.classList.remove('open');   // телефон: оверлей закрывается при смене экрана
  if (SCREENS[scr] && window[SCREENS[scr]]) window[SCREENS[scr]]();
};
// телефон: ✕ в карточке закрывает оверлей
document.getElementById('insp').addEventListener('click', e => {
  if (e.target.classList.contains('insp-close')) document.getElementById('insp').classList.remove('open');
});
// PWA: установка на хоумскрин (iPhone: Поделиться → На экран «Домой»)
if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
document.querySelectorAll('.side .item[data-screen]').forEach(el =>
  el.addEventListener('click', () => showScreen(el.dataset.screen)));
// открыть карточку записи из другого экрана (календарь и т.п.)
window.openNode = function (id) { showScreen('list'); showCard(id); };

// ===== Pre-flight: перед закрытием важной задачи (P0/P1) показываем блокеры =====
window.preflightOk = async function (id) {
  const n = state?.nodes.find(x => x.id === id);
  if (!n || n.kind !== 'task' || n.status === 'done' || !['P0', 'P1'].includes(n.priority)) return true;
  const s = await fetch('/api/suggest/' + id).then(r => r.json()).catch(() => null);
  if (!s) return true;
  const lines = [
    ...(s.blockers ?? []).map(b => `⛔ блокирует: ${b.title}`),
    ...(s.context?.decisions ?? []).map(d => `◆ решение открыто: ${d.title}`),
    ...(s.context?.payments ?? []).map(o => `◈ платёж рядом: ${o.name} (${o.next_date})`),
    ...(s.context?.principles ?? []).map(p => `◇ принцип: ${p.title}`),
  ];
  if (!lines.length) return true;
  return confirm(`🛫 Pre-flight «${n.title}» — перед закрытием проверь:\n\n${lines.join('\n')}\n\nВсё учтено — закрываем?`);
};

// ===== Настройки: корзина, экспорт, бэкап =====
window.loadSettings = async function () {
  const [rows, info] = await Promise.all([
    fetch('/api/trash').then(x => x.json()),
    fetch('/api/info').then(x => x.json()).catch(() => ({})),
  ]);
  document.getElementById('screen-settings').innerHTML = `
  <h2 style="margin-bottom:2px">Настройки</h2>
  <div class="muted" style="margin-bottom:14px">данные принадлежат тебе: корзина, экспорт в открытые форматы, бэкапы базы</div>
  <div class="fingrid">
    <div class="card"><div class="meta">🗑 КОРЗИНА</div>
      ${rows.map(t => `
        <div class="task">
          <span class="t">${esc(t.label)}</span>
          <span class="meta">${t.created_at.slice(5, 16).replace('T', ' ')}</span>
          <span class="pill btn ok" data-trrestore="${t.id}" title="восстановить">↩</span>
          <span class="pill btn danger" data-trpurge="${t.id}" title="удалить безвозвратно">✕</span>
        </div>`).join('') || '<div class="empty">пусто · удалённое хранится 30 дней</div>'}
    </div>
    <div class="card"><div class="meta">⤓ ЭКСПОРТ</div>
      <div class="task" style="border:0">
        <span class="pill btn ok" id="exportBtn">экспортировать MD/JSON</span>
        <span class="meta">полный дамп: data.json + цели/страницы/финансы/люди в markdown — никакого лока на платформе</span>
      </div>
    </div>
    <div class="card"><div class="meta">🗄 БЭКАП БАЗЫ</div>
      <div class="task" style="border:0">
        <span class="pill btn ok" id="backupBtn">сделать бэкап сейчас</span>
        <span class="meta">хранится 20 последних · авто-бэкап раз в день при запуске</span>
      </div>
    </div>
    <div class="card"><div class="meta">🧹 ТЕСТОВЫЕ ДАННЫЕ</div>
      <div class="task" style="border:0">
        ${info.demoWiped
          ? '<span class="meta">демо удалено — система работает только на твоих данных</span>'
          : `<span class="pill btn danger" id="wipeBtn">удалить все демо-данные</span>
             <span class="meta">уберёт всё с пометкой «(пример)» и тестовые наполнения; категории, блоки портфеля и колонки дневника останутся. Назад не вернутся.</span>`}
      </div>
    </div>
    <div class="card"><div class="meta">📱 С ТЕЛЕФОНА</div>
      ${info.lan
        ? `<div class="kv">Адрес в домашней сети <b class="num">${esc(info.lan)}</b></div>
           <div class="meta" style="margin-top:6px">открой в Safari на iPhone (тот же Wi-Fi, Mac включён) →
           Поделиться → «На экран “Домой”» — будет как приложение. Данные не покидают Mac.</div>`
        : '<div class="empty">сеть не найдена — проверь Wi-Fi</div>'}
    </div>
  </div>`;

  const box = document.getElementById('screen-settings');
  box.querySelector('#exportBtn').addEventListener('click', async () => {
    const r = await fetch('/api/export', { method: 'POST' }).then(x => x.json());
    alert(r.error ? r.error : `Экспортировано ${r.files.length} файлов:\n${r.dir}\n\n(папка открыта в Finder)`);
  });
  box.querySelector('#wipeBtn')?.addEventListener('click', async () => {
    if (!confirm('Удалить ВСЕ тестовые данные?\n\nУйдёт всё с пометкой «(пример)», тестовые страницы Инфо, история чек-инов и замеры колеса. Твои категории, блоки портфеля и колонки дневника останутся.\n\nВернуть будет нельзя.')) return;
    const r = await fetch('/api/demo/wipe', { method: 'POST' }).then(x => x.json());
    alert(`Готово: удалено ${r.deleted} записей. Система чистая — наполняем твоим.`);
    location.reload();
  });
  box.querySelector('#backupBtn').addEventListener('click', async () => {
    const r = await fetch('/api/backup', { method: 'POST' }).then(x => x.json());
    alert(r.error ? r.error : `Бэкап создан:\n${r.file}\n\nХранится 20 последних; авто-бэкап — раз в день при запуске.`);
  });
  box.querySelectorAll('[data-trrestore]').forEach(el =>
    el.addEventListener('click', async () => {
      const r = await fetch(`/api/trash/${el.dataset.trrestore}/restore`, { method: 'POST' }).then(x => x.json());
      if (r.kind === 'pages') window.openPage?.(r.restored);
      else { await load(); if (r.restored) window.openNode?.(r.restored); }
    }));
  box.querySelectorAll('[data-trpurge]').forEach(el =>
    el.addEventListener('click', async () => {
      if (!confirm('Удалить из корзины безвозвратно?')) return;
      await fetch('/api/trash/' + el.dataset.trpurge, { method: 'DELETE' });
      window.loadSettings();
    }));
};

// ===== Поиск =====
let st;
document.getElementById('searchbox').addEventListener('input', e => {
  clearTimeout(st);
  st = setTimeout(async () => {
    const q = e.target.value.trim();
    const box = document.getElementById('searchres');
    if (!q) { box.innerHTML = ''; return; }
    const [res, pages] = await Promise.all([
      api.search(q),
      fetch('/api/pages/search?q=' + encodeURIComponent(q)).then(r => r.json()).catch(() => []),
    ]);
    box.innerHTML = res.map(t => `<div data-id="${t.id}">☑ ${esc(t.title)}</div>`).join('')
      + pages.map(p => `<div data-page="${p.id}">▤ ${esc(p.title)}</div>`).join('')
      || '<div>ничего</div>';
    box.querySelectorAll('[data-page]').forEach(el =>
      el.addEventListener('click', () => window.openPage(+el.dataset.page)));
  }, 200);
});

load();

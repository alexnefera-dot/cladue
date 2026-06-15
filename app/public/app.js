// API-ключ замка: добавляется ко всем запросам; без него сервер отвечает 401
{
  const origFetch = window.fetch.bind(window);
  const native = location.protocol === 'pipboy:';   // нативная оболочка (WKURLSchemeHandler)
  window.fetch = (url, opts = {}) => {
    if (String(url).startsWith('/api/')) {
      if (localStorage.pbKey) opts.headers = { ...(opts.headers ?? {}), 'X-Pipboy-Key': localStorage.pbKey };
      // WKURLSchemeHandler не отдаёт тело POST/PATCH — дублируем его в заголовок (ASCII-safe).
      if (native && typeof opts.body === 'string') {
        opts.headers = { ...(opts.headers ?? {}), 'X-Pipboy-Body': encodeURIComponent(opts.body) };
      }
    }
    return origFetch(url, opts);
  };
}

let state = null;
let selected = null;            // строка, чья карточка открыта
let picked = new Set();         // мультивыбор
let visibleOrder = [];          // порядок видимых строк (для Shift-выбора)
let view = 'tree';              // tree | tasker
let taskerView = 'prio';        // prio | dates | groups
// свёрнутость дерева Целей: переживает перезапуск; при первом запуске всё свёрнуто
const collapsed = new Set(JSON.parse(localStorage.goalsFold ?? 'null') ?? []);
let foldInit = localStorage.goalsFold != null;
const saveFold = () => localStorage.goalsFold = JSON.stringify([...collapsed]);

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
  reorder: (id, ref_id, where) => fetch(`/api/nodes/${id}/reorder`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ref_id, where }) }).then(r => r.json()),
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
  if (!foldInit) {   // первый запуск: всё свёрнуто — видна только структура
    const hasKids = new Set(state.nodes.map(n => n.parent_id).filter(Boolean));
    state.nodes.forEach(n => { if (hasKids.has(n.id)) collapsed.add(n.id); });
    foldInit = true;
  }
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
    `разобрано: ${typed} из ${real.length} (${pct}%) · связей: ${state.links.length} · заблокировано: ${blocked} · в инбоксе: ${inbox}`
    + (window.pbVersion ? ` · ${window.pbVersion}` : '');
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
    <span class="t ${done ? 'done' : ''}">${esc(n.title)}${n.note ? `<div class="noteblock">${esc(n.note)}</div>` : ''}</span>
    ${n.blocked ? '<span class="meta">⛔</span>' : ''}
    ${n.repeat ? '<span class="meta" title="повторяющаяся">🔁</span>' : ''}
    ${n.due_date ? `<span class="meta">${n.due_date}</span>` : ''}
    <span class="rowbtn" data-addchild="${n.id}" title="добавить вложенную">＋</span>
    <span class="rowbtn del" data-delrow="${n.id}" title="удалить">✕</span>
  </div>`;
}

function renderBoard() {
  saveFold();
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
  const locIso = (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
  const today = locIso(new Date());
  const week = locIso(new Date(Date.now() + 7 * 864e5));
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
  if (window.isLocked?.('list')) return;   // закрытая зона не светит карточку
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
    <div class="kv"><span>${n.due_date ?? 'не задан'}${n.due_time ? ' в ' + n.due_time : ''}</span>
      ${n.due_date ? `<span class="pill btn" data-setdate="">убрать</span>` : ''}</div>
    ${s.date ? `<div class="suggest">💡 ${esc(s.date.reason)} →
      <span class="pill btn ok" data-setdate="${s.date.date}">поставить ${s.date.date}</span></div>` : ''}
    <input id="dateInput" placeholder="или вручную: 2026-08-31" value="">
    ${n.due_date ? `<input id="timeInput" placeholder="время для пуша: 14:30 (Enter · пусто — убрать)" value="${n.due_time ?? ''}" style="margin-top:4px">` : ''}

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
  document.getElementById('timeInput')?.addEventListener('keydown', async e => {
    if (e.key !== 'Enter') return;
    const v = e.target.value.trim();
    if (v === '') { await api.patch(id, { due_time: null }); await load(); return; }
    if (/^([01]?\d|2[0-3]):[0-5]\d$/.test(v)) { await api.patch(id, { due_time: v.padStart(5, '0') }); await load(); }
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
  const input = document.createElement('textarea');
  input.className = 'inlineedit';
  input.rows = 1;
  // правится запись целиком: первая строка — заголовок, остальное — блок текста
  input.value = n.title + (n.note ? '\n' + n.note : '');
  input.title = 'Enter — новая строка · ⌘/Ctrl+Enter — сохранить · клик мимо — сохранить';
  t.replaceWith(input);
  const grow = () => { input.style.height = 'auto'; input.style.height = (input.scrollHeight + 2) + 'px'; };
  input.addEventListener('input', grow);
  input.focus();
  input.setSelectionRange(n.title.length, n.title.length);
  grow();
  let saved = false;
  const save = async () => {
    if (saved) return; saved = true;
    const lines = input.value.replace(/\s+$/, '').split('\n');
    const title = lines[0].trim();
    const note = lines.slice(1).join('\n').trim();
    if (title && (title !== n.title || note !== (n.note ?? '')))
      await api.patch(id, { title, note });
    await load();
  };
  input.addEventListener('click', ev => ev.stopPropagation());
  input.addEventListener('keydown', ev => {
    // привычный Enter сохраняет, пока запись однострочная; в блоке Enter — новая строка
    if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey || (!ev.shiftKey && !input.value.includes('\n')))) {
      ev.preventDefault(); save();
    }
    if (ev.key === 'Escape') { saved = true; load(); }
  });
  input.addEventListener('blur', save);
}

// ===== Drag & drop: середина строки — вложить, верхний/нижний край — поставить выше/ниже =====
let draggedId = null;
const dropClear = () => document.querySelectorAll('.dropinto,.dropbefore,.dropafter')
  .forEach(x => x.classList.remove('dropinto', 'dropbefore', 'dropafter'));
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
  const r = row.getBoundingClientRect();
  const y = (e.clientY - r.top) / r.height;
  row.classList.remove('dropinto', 'dropbefore', 'dropafter');
  row.classList.add(y < 0.3 ? 'dropbefore' : y > 0.7 ? 'dropafter' : 'dropinto');
});
document.addEventListener('dragleave', e => {
  e.target.closest('.task[data-id]')?.classList.remove('dropinto', 'dropbefore', 'dropafter');
});
document.addEventListener('drop', async e => {
  const row = e.target.closest('.task[data-id]');
  const zone = row?.classList.contains('dropbefore') ? 'before'
    : row?.classList.contains('dropafter') ? 'after' : 'into';
  dropClear();
  if (!row || draggedId == null) return;
  e.preventDefault();
  const target = +row.dataset.id;
  let ids = picked.has(draggedId) ? [...picked] : [draggedId];
  if (zone === 'after') ids = ids.reverse();   // чтобы порядок выбранных сохранился
  for (const mid of ids) {
    if (mid === target) continue;
    const r = zone === 'into' ? await api.move(mid, target) : await api.reorder(mid, target, zone);
    if (r.error) { alert(`«${state.nodes.find(n => n.id === mid)?.title}»: ${r.error}`); }
  }
  if (zone === 'into') collapsed.delete(target);
  draggedId = null;
  await load();
});
document.addEventListener('dragend', dropClear);

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

// ===== Добавление: поле многострочное. Enter — отправить, Shift+Enter — новая строка.
// Несколько строк: Enter разбивает на записи (вложенность по отступам),
// ⌘/Ctrl+Enter или кнопка «одной записью» — первая строка заголовок, остальное блок-заметка.
const addT = document.getElementById('addTitle');
const growAdd = () => { addT.style.height = 'auto'; addT.style.height = Math.min(addT.scrollHeight + 2, 240) + 'px'; };

// раскрыть путь до записи, проскроллить и подсветить — ничего не «исчезает»
function revealNode(id) {
  let n = state.nodes.find(x => x.id === id);
  while (n && n.parent_id != null) {
    collapsed.delete(n.parent_id);
    n = state.nodes.find(x => x.id === n.parent_id);
  }
  renderBoard();
  const row = document.querySelector(`.task[data-id="${id}"]`);
  if (row) {
    row.scrollIntoView({ block: 'center', behavior: 'smooth' });
    row.classList.add('flash');
    setTimeout(() => row.classList.remove('flash'), 1400);
  }
}

async function submitAdd(asBlock) {
  const text = addT.value.replace(/\s+$/, '');
  if (!text.trim()) return;
  const inbox = state.nodes.find(n => n.is_category && n.title.includes('Инбокс'));
  const lines = text.split('\n');
  let created = null, target = null;
  if (lines.length > 1 && asBlock) {
    // одна запись: заголовок + блок текста в заметке
    created = await api.add({ title: lines[0].trim(), parent_id: selected ?? null });
    await api.patch(created.id, { note: lines.slice(1).join('\n').trim() });
  } else if (lines.length > 1) {
    target = selected ?? inbox?.id ?? null;
    const r = await api.import({ parent_id: target, text });
    document.getElementById('statusbar').textContent += ` · ⤓ импортировано: ${r.imported}`;
  } else {
    created = await api.add({ title: text.trim(), parent_id: selected ?? null });
  }
  addT.value = '';
  document.getElementById('addModeBar')?.remove();
  growAdd();
  await load();
  if (created) revealNode(created.id);
  else if (target) { collapsed.delete(target); renderBoard(); }
}

addT.addEventListener('input', () => {
  growAdd();
  // подсказка режимов появляется, когда строк несколько
  const multi = addT.value.includes('\n');
  let bar = document.getElementById('addModeBar');
  if (multi && !bar) {
    bar = document.createElement('div');
    bar.id = 'addModeBar';
    bar.className = 'btnrow';
    bar.style.margin = '-6px 0 10px';
    bar.innerHTML = `
      <span class="pill btn ok" id="amSplit" title="Enter">⤓ разбить на записи (вложенность по отступам)</span>
      <span class="pill btn" id="amBlock" title="⌘+Enter">▤ одной записью: заголовок + блок текста</span>`;
    addT.closest('.addbar').after(bar);
    bar.querySelector('#amSplit').addEventListener('click', () => submitAdd(false));
    bar.querySelector('#amBlock').addEventListener('click', () => submitAdd(true));
  }
  if (!multi && bar) bar.remove();
});
addT.addEventListener('keydown', e => {
  if (e.key !== 'Enter' || e.shiftKey) return;
  e.preventDefault();
  submitAdd(e.metaKey || e.ctrlKey);
});


// ===== Замок разделов: Цели/Финансы/Инфо/Психология по умолчанию закрыты =====
// Честный UI-замок прототипа (как у Психологии); настоящие шифрованные зоны — нативная фаза.
const LOCKED_SCREENS = new Set(['list', 'fin', 'notes', 'psy']);
// В нативном приложении (Mac/iPhone) веб-замок разделов не нужен и вреден:
// настоящий гейт — Touch ID / Face ID при запуске (AuthGate), а при бездействии
// всё блокируется системно. Поэтому в нативе разделы открыты сразу и не зависят
// от ответа /api/lock. Веб-замок остаётся только для браузерного прототипа.
const inNativeApp = !!(window.webkit && window.webkit.messageHandlers);
let lockOn = !inNativeApp;    // в браузере до ответа сервера считаем, что закрыто
let currentScr = 'today';
if (inNativeApp) sessionStorage.pbUnlocked = '1';
// нативный лаунчер Mac разблокировал замок и передал ключ через ?key=… —
// принимаем его и не показываем веб-замок повторно
try {
  const u = new URL(location.href);
  const k = u.searchParams.get('key');
  if (k) {
    localStorage.pbKey = k;
    sessionStorage.pbUnlocked = '1';
    u.searchParams.delete('key');
    history.replaceState(null, '', u.pathname + (u.search || ''));
  }
} catch { /* нет location/history (тестовая среда) — пропускаем */ }
if (!inNativeApp) fetch('/api/lock').then(r => r.json()).then(i => {
  lockOn = i.enabled;
  if (i.localUnlock) sessionStorage.pbUnlocked = '1';   // ты за своим Mac — секции открыты
  refreshLockBadges();
  if (document.getElementById('lockpane').style.display !== 'none' && !window.isLocked(currentScr))
    showScreen(currentScr);
}).catch(() => {});
fetch('/api/info').then(r => r.json()).then(i => { window.pbVersion = i.version; }).catch(() => {});
window.isLocked = scr => LOCKED_SCREENS.has(scr) && lockOn && sessionStorage.pbUnlocked !== '1';
// статус нативного Wi-Fi синхрона приходит из Swift (evaluateJavaScript) → в карточку настроек
window.pbSync = msg => { const e = document.getElementById('syncStatus'); if (e) e.textContent = msg; };
window.lockNow = () => { sessionStorage.removeItem('pbUnlocked'); showScreen('today'); };

// замочки у закрытых разделов: 🔒 вместо иконки, после разблокировки — родная иконка
function refreshLockBadges() {
  document.querySelectorAll('.side .item[data-screen]').forEach(el => {
    const scr = el.dataset.screen;
    if (!LOCKED_SCREENS.has(scr)) return;
    const ni = el.querySelector('.ni');
    if (ni) ni.textContent = lockOn && window.isLocked(scr) ? '🔒' : el.dataset.ico;
  });
}

// группа «Ещё» (Люди, Рутины): свёрнута по умолчанию, состояние запоминается
{
  const box = () => document.getElementById('navMoreBox');
  const caret = () => document.getElementById('navMoreCaret');
  const setOpen = open => {
    box().style.display = open ? 'block' : 'none';
    caret().textContent = open ? '▾' : '▸';
    localStorage.navMore = open ? '1' : '0';
  };
  setOpen(localStorage.navMore === '1');
  document.getElementById('navMore').addEventListener('click', () =>
    setOpen(box().style.display === 'none'));
}

const wbB64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
const wbUn = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
// В нативном приложении (WKWebView) WebAuthn-палец не работает — палец там на
// уровне macOS при запуске (AuthGate), а на loopback разделы и так авто-открыты.
const isNativeApp = () => !!(window.webkit && window.webkit.messageHandlers);
const touchAvail = () => !isNativeApp() && !!(window.PublicKeyCredential && window.isSecureContext);
async function touchIdRegister() {
  const cred = await navigator.credentials.create({ publicKey: {
    rp: { name: 'Pipboy' },
    user: { id: crypto.getRandomValues(new Uint8Array(16)), name: 'pipboy', displayName: 'Pipboy' },
    challenge: crypto.getRandomValues(new Uint8Array(32)),
    pubKeyCredParams: [{ type: 'public-key', alg: -7 }, { type: 'public-key', alg: -257 }],
    authenticatorSelection: { authenticatorAttachment: 'platform', userVerification: 'required' },
    timeout: 60000,
  } });
  localStorage.pbTouchId = wbB64(cred.rawId);
}
async function touchIdUnlock() {
  await navigator.credentials.get({ publicKey: {
    challenge: crypto.getRandomValues(new Uint8Array(32)),
    allowCredentials: [{ type: 'public-key', id: wbUn(localStorage.pbTouchId) }],
    userVerification: 'required', timeout: 60000,
  } });
  return true;
}

function renderLockPane(scr) {
  const pane = document.getElementById('lockpane');
  pane.innerHTML = `
  <div style="max-width:430px;margin:9vh auto 0;text-align:center">
    <div style="font-size:44px;margin-bottom:6px">🔒</div>
    <h2>Раздел под замком</h2>
    <div class="muted" style="margin:6px 0 16px">Цели, Финансы, Инфо и Психология закрыты по умолчанию</div>
    <div class="task finadd" style="border:0;justify-content:center">
      <input id="lockPw" type="password" placeholder="пароль" style="flex:1;max-width:240px">
      <span class="pill btn ok" id="lockGo">открыть</span>
      ${touchAvail() && localStorage.pbTouchId && localStorage.pbKey ? '<span class="pill btn" id="lockTouch">👆 Touch ID</span>' : ''}
    </div>
    <div class="meta" style="margin-top:12px">на телефоне — по паролю; Face ID будет в нативной версии</div>
  </div>`;
  const done = () => { sessionStorage.pbUnlocked = '1'; showScreen(scr); };
  const go = async () => {
    const r = await fetch('/api/lock/unlock', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: document.getElementById('lockPw').value }) });
    if (!r.ok) { alert('Неверный пароль'); return; }
    const j = await r.json();
    if (j.key) localStorage.pbKey = j.key;   // ключ API на это устройство
    done();
  };
  document.getElementById('lockGo').addEventListener('click', go);
  document.getElementById('lockPw').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
  document.getElementById('lockTouch')?.addEventListener('click', async () => {
    try { await touchIdUnlock(); done(); } catch { /* отменил — остаётся пароль */ }
  });
  document.getElementById('lockPw').focus();
}

// ===== Переключение экранов =====
const SCREENS = { today: 'loadToday', list: null, fin: 'loadFin', cal: 'loadCal', people: 'loadPeople', routines: 'loadRoutines', notes: 'loadNotes', psy: 'loadPsy', track: 'loadTrack', settings: 'loadSettings' };
window.showScreen = function (scr) {
  // незаконченная правка в Инфо дозаписывается при уходе с экрана
  if (scr !== 'notes' && window.ntFlush) { const f = window.ntFlush; window.ntFlush = null; f(); }
  currentScr = scr;
  const locked = window.isLocked(scr);
  document.querySelectorAll('.side .item').forEach(i =>
    i.classList.toggle('active', i.dataset.screen === scr));
  if (scr === 'people' || scr === 'routines') {
    document.getElementById('navMoreBox').style.display = 'block';
    document.getElementById('navMoreCaret').textContent = '▾';
    localStorage.navMore = '1';
  }
  for (const key of Object.keys(SCREENS))
    document.getElementById('screen-' + key).style.display = (!locked && key === scr) ? 'block' : 'none';
  document.getElementById('lockpane').style.display = locked ? 'block' : 'none';
  if (locked) renderLockPane(scr);
  // правая панель (карточка записи) имеет смысл только в Задачах
  const insp = document.querySelector('.insp');
  insp.style.display = (!locked && scr === 'list') ? 'block' : 'none';
  insp.classList.remove('open');   // телефон: оверлей закрывается при смене экрана
  refreshLockBadges();
  if (!locked && SCREENS[scr] && window[SCREENS[scr]]) window[SCREENS[scr]]();
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
    <div class="card"><div class="meta">🗑 КОРЗИНА
      ${rows.length ? '<span class="pill btn danger" id="trashClear" style="float:right">✕ очистить корзину</span>' : ''}</div>
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
      <div class="task" style="border:0">
        <span class="meta">внешняя папка (доп. копия):</span>
        <span class="ed meta" id="backupDir" title="клик — задать путь (внешний диск/облачная папка НЕ рекомендуется)">＋ путь</span>
      </div>
    </div>
    <div class="card"><div class="meta">🔒 ЗАМОК РАЗДЕЛОВ · Цели / Финансы / Инфо / Психология</div>
      <div class="task" style="border:0;flex-wrap:wrap">
        ${lockOn
          ? `<span class="pill ok">замок включён</span>
             <span class="pill btn" id="lkChange">сменить пароль</span>
             <span class="pill btn" id="lkNow">🔒 заблокировать сейчас</span>
             <span class="pill btn danger" id="lkOff">снять замок</span>`
          : `<span class="pill btn ok" id="lkSet">задать пароль — включить замок</span>`}
        ${touchAvail()
          ? (localStorage.pbTouchId
            ? '<span class="pill ok">👆 Touch ID включён</span><span class="pill btn" id="lkTouchOff">убрать Touch ID</span>'
            : (lockOn ? '<span class="pill btn" id="lkTouchOn">👆 включить Touch ID</span>' : ''))
          : ''}
      </div>
      <div class="meta">${isNativeApp()
        ? 'на Mac: вход по пальцу при запуске разблокирует всё · через 10 минут простоя разделы закрываются сами — снова по пальцу'
        : 'по умолчанию разделы закрыты в каждой новой сессии · на Mac открываются по пальцу, на телефоне — пароль · настоящее шифрование зон — нативная фаза'}</div>
    </div>
    <div class="card"><div class="meta">🔔 УВЕДОМЛЕНИЯ</div>
      <div class="task" style="border:0">
        <span class="pill btn ${localStorage.rtNotifyOn !== '0' ? 'ok' : ''}" id="notifToggle">${localStorage.rtNotifyOn !== '0' ? 'включены' : 'выключены'}</span>
        <span class="meta">рутины с ⏰ и события календаря со временем шлют системный пуш по времени · разрешение спрашивает macOS</span>
      </div>
    </div>
    ${inNativeApp ? `
    <div class="card"><div class="meta">📡 СИНХРОНИЗАЦИЯ ПО WI-FI · Mac ↔ iPhone</div>
      <div class="task" style="border:0;flex-wrap:wrap">
        <span class="pill btn ok" id="syncHost">раздать данные (источник)</span>
        <span class="pill btn" id="syncRecv">получить данные (приёмник)</span>
        <span class="pill btn danger" id="syncStop">стоп</span>
      </div>
      <div class="meta" id="syncStatus">оба устройства в одной Wi-Fi · на источнике жми «раздать», на приёмнике «получить» · сверь код на обоих</div>
      <div class="meta">приёмник ПОЛНОСТЬЮ заменяет свои данные данными источника · ничего не уходит в облако</div>
    </div>` : ''}
    <div class="card"><div class="meta">🧭 РЕВИЗИЯ НАПОЛНЕНИЯ</div>
      <div class="task" style="border:0">
        <span class="pill btn ok" id="auditBtn">проверить, где пусто</span>
        <span class="meta">детерминированные проверки по базе: пустые разделы, протухшие балансы, задачи без сроков</span>
      </div>
      <div id="auditBox"></div>
    </div>
  </div>`;

  const box = document.getElementById('screen-settings');
  box.querySelector('#exportBtn').addEventListener('click', async () => {
    const r = await fetch('/api/export', { method: 'POST' }).then(x => x.json());
    alert(r.error ? r.error : `Экспортировано ${r.files.length} файлов:\n${r.dir}\n\n(папка открыта в Finder)`);
  });
  const lockPass = (old, password) => fetch('/api/lock/pass', { method: 'POST',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ old, password }) });
  box.querySelector('#lkSet')?.addEventListener('click', async () => {
    const pw = prompt('Пароль замка (для всех четырёх разделов):');
    if (!pw?.trim()) return;
    if (prompt('Повтори пароль:') !== pw) { alert('Пароли не совпали'); return; }
    await lockPass('', pw.trim());
    lockOn = true;
    const u = await fetch('/api/lock/unlock', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw.trim() }) }).then(x => x.json()).catch(() => ({}));
    if (u.key) localStorage.pbKey = u.key;     // API-ключ: без него запросы получат 401
    sessionStorage.removeItem('pbUnlocked');   // закрываем сразу — вместо контента будет заглушка
    refreshLockBadges();
    alert('Замок включён: Цели, Финансы, Инфо и Психология закрыты. Открываются паролем' + (touchAvail() ? ' или Touch ID (включи здесь же).' : '.'));
    window.loadSettings();
  });
  box.querySelector('#lkChange')?.addEventListener('click', async () => {
    const old = prompt('Текущий пароль:');
    if (old == null) return;
    const pw = prompt('Новый пароль:');
    if (!pw?.trim()) return;
    const r = await lockPass(old, pw.trim());
    if (r.ok) {
      const u = await fetch('/api/lock/unlock', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw.trim() }) }).then(x => x.json()).catch(() => ({}));
      if (u.key) localStorage.pbKey = u.key;
    }
    alert(r.ok ? 'Пароль сменён' : 'Неверный текущий пароль');
  });
  box.querySelector('#lkOff')?.addEventListener('click', async () => {
    const old = prompt('Пароль (подтверждение снятия замка):');
    if (old == null) return;
    const r = await lockPass(old, '');
    if (!r.ok) { alert('Неверный пароль'); return; }
    lockOn = false;
    delete localStorage.pbTouchId;
    delete localStorage.pbKey;
    window.loadSettings();
  });
  box.querySelector('#lkNow')?.addEventListener('click', () => window.lockNow());
  box.querySelector('#lkTouchOn')?.addEventListener('click', async () => {
    const pw = prompt('Пароль замка (подтверждение):');
    const ok = await fetch('/api/lock/unlock', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw ?? '' }) });
    if (!ok.ok) { alert('Неверный пароль'); return; }
    try { await touchIdRegister(); alert('Touch ID включён для этого устройства'); window.loadSettings(); }
    catch (e) { alert('Не получилось: ' + e.message); }
  });
  box.querySelector('#lkTouchOff')?.addEventListener('click', () => {
    delete localStorage.pbTouchId;
    window.loadSettings();
  });
  box.querySelector('#notifToggle')?.addEventListener('click', () => {
    localStorage.rtNotifyOn = (localStorage.rtNotifyOn !== '0') ? '0' : '1';
    window.pbSyncAllReminders?.();
    window.loadSettings();
  });
  // синхрон по Wi-Fi (только в нативном приложении): веб → нативный мост pipboySync
  const syncBridge = window.webkit?.messageHandlers?.pipboySync;
  if (syncBridge) {
    box.querySelector('#syncHost')?.addEventListener('click', () => syncBridge.postMessage({ action: 'host' }));
    box.querySelector('#syncRecv')?.addEventListener('click', () => {
      if (confirm('Приёмник ПОЛНОСТЬЮ заменит свои данные данными источника. Продолжить?'))
        syncBridge.postMessage({ action: 'receive' });
    });
    box.querySelector('#syncStop')?.addEventListener('click', () => syncBridge.postMessage({ action: 'stop' }));
  }
  box.querySelector('#auditBtn')?.addEventListener('click', async () => {
    const rows = await fetch('/api/audit').then(x => x.json());
    const warns = rows.filter(r => r.status === 'warn');
    const oks = rows.filter(r => r.status === 'ok');
    box.querySelector('#auditBox').innerHTML =
      (warns.length ? warns.map(r => `<div class="task" style="padding:4px 0">
          <span class="pill p1">${esc(r.section)}</span><span class="t">${esc(r.item)}</span>
          <span class="meta">${esc(r.hint)}</span></div>`).join('')
        : '<div class="empty">пробелов не найдено — всё наполнено 👏</div>')
      + (oks.length ? `<div class="meta" style="margin-top:8px">в порядке: ${oks.map(r => `${r.section} (${r.item})`).join(' · ')}</div>` : '');
  });
  box.querySelector('#trashClear')?.addEventListener('click', async () => {
    if (!confirm(`Очистить корзину безвозвратно? Записей: ${rows.length}.`)) return;
    await fetch('/api/trash/clear', { method: 'POST' });
    window.loadSettings();
  });
  fetch('/api/fin').then(x => x.json()).then(() => {}).catch(() => {});
  // путь внешнего бэкапа
  const bd = box.querySelector('#backupDir');
  if (bd) {
    fetch('/api/info').then(x => x.json()).catch(() => ({}));
    bd.textContent = localStorage.backupDirShown ?? '＋ путь';
    bd.addEventListener('click', async () => {
      const v = prompt('Папка для дополнительной копии бэкапа (например /Volumes/Backup/pipboy):', localStorage.backupDirShown ?? '');
      if (v == null) return;
      await fetch('/api/setting', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'backup_dir', value: v.trim() }) });
      localStorage.backupDirShown = v.trim();
      window.loadSettings();
    });
  }
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

// ===== Глобальные клавиши ежедневного пользования =====
// q — быстрый ввод в Инбокс с любого экрана; / — фокус в поиск (вне полей ввода)
document.addEventListener('keydown', e => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.target.closest('input,textarea,select,[contenteditable]')) return;
  if (e.key === '/') { e.preventDefault(); document.getElementById('searchbox').focus(); return; }
  if (e.key !== 'q' && e.key !== 'й') return;
  e.preventDefault();
  if (document.getElementById('qcap')) return;
  const box = document.createElement('div');
  box.id = 'qcap';
  box.innerHTML = `<input id="qcapIn" placeholder="в Инбокс… (Enter — добавить, Esc — закрыть)">`;
  document.body.appendChild(box);
  const inp = box.querySelector('input');
  inp.focus();
  const close = () => box.remove();
  inp.addEventListener('keydown', async ev => {
    if (ev.key === 'Escape') return close();
    if (ev.key !== 'Enter' || !inp.value.trim()) return;
    await api.add({ title: inp.value.trim(), parent_id: null });
    const sb = document.getElementById('statusbar');
    if (sb) sb.textContent = `✓ в Инбокс: «${inp.value.trim().slice(0, 40)}»`;
    close();
    if (currentScr === 'list') load();
    if (currentScr === 'today') window.loadToday?.();
  });
  inp.addEventListener('blur', close);
});

// ===== Поиск =====
let st;
document.getElementById('searchbox').addEventListener('input', e => {
  clearTimeout(st);
  st = setTimeout(async () => {
    const q = e.target.value.trim();
    const box = document.getElementById('searchres');
    if (!q) { box.innerHTML = ''; return; }
    if (window.isLocked?.('list')) { box.innerHTML = '<div>🔒 поиск идёт по закрытым разделам — открой замок</div>'; return; }
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

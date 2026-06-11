/* Инфо: страницы-заметки — дерево, markdown, [[вики-ссылки]], бэклинки */
let ntPages = [], ntSel = null, ntEditing = false;
const ntFold = new Set();

const ntApi = {
  list: () => fetch('/api/pages').then(r => r.json()),
  get: id => fetch('/api/pages/' + id).then(r => r.json()),
  add: b => fetch('/api/pages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  patch: (id, b) => fetch('/api/pages/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  del: id => fetch('/api/pages/' + id, { method: 'DELETE' }),
  move: (id, parent_id) => fetch(`/api/pages/${id}/move`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ parent_id }) }).then(r => r.json()),
  backlinks: id => fetch(`/api/pages/${id}/backlinks`).then(r => r.json()),
  wiki: name => fetch('/api/wiki?name=' + encodeURIComponent(name)).then(r => r.json()),
};

const nesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ===== Мини-markdown: заголовки, списки, чекбоксы, цитаты, код, жирный/курсив, [[вики]] =====
function mdRender(src) {
  const inline = s => s
    .replace(/\[\[([^\]]+)\]\]/g, (_, n) => `<a class="wiki" data-wiki="${nesc(n)}">${nesc(n)}</a>`)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, '$1<i>$2</i>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank">$1</a>');
  const lines = nesc(src).split('\n');
  let out = '', list = null, code = false;
  const closeList = () => { if (list) { out += `</${list}>`; list = null; } };
  for (const raw of lines) {
    if (raw.trim().startsWith('```')) { closeList(); code = !code; out += code ? '<pre>' : '</pre>'; continue; }
    if (code) { out += raw + '\n'; continue; }
    const l = raw.trimEnd();
    let m;
    if ((m = l.match(/^(#{1,3})\s+(.*)/))) { closeList(); out += `<h${m[1].length + 1}>${inline(m[2])}</h${m[1].length + 1}>`; }
    else if ((m = l.match(/^\s*[-*]\s+\[( |x)\]\s+(.*)/i))) {
      if (list !== 'ul') { closeList(); out += '<ul>'; list = 'ul'; }
      out += `<li class="chk">${m[1].trim() ? '☑' : '☐'} ${m[1].trim() ? '<s>' + inline(m[2]) + '</s>' : inline(m[2])}</li>`;
    }
    else if ((m = l.match(/^\s*[-*]\s+(.*)/))) {
      if (list !== 'ul') { closeList(); out += '<ul>'; list = 'ul'; }
      out += `<li>${inline(m[1])}</li>`;
    }
    else if ((m = l.match(/^\s*\d+[.)]\s+(.*)/))) {
      if (list !== 'ol') { closeList(); out += '<ol>'; list = 'ol'; }
      out += `<li>${inline(m[1])}</li>`;
    }
    else if ((m = l.match(/^>\s?(.*)/))) { closeList(); out += `<blockquote>${inline(m[1])}</blockquote>`; }
    else if (!l.trim()) { closeList(); out += '<div class="mdgap"></div>'; }
    else { closeList(); out += `<p>${inline(l)}</p>`; }
  }
  closeList();
  if (code) out += '</pre>';
  return out;
}

window.loadNotes = async function (openId) {
  ntPages = await ntApi.list();
  if (openId) { ntSel = openId; ntEditing = false; }
  if (ntSel && !ntPages.some(p => p.id === ntSel)) ntSel = null;
  renderNotes();
};
window.openPage = id => { showScreen('notes'); window.loadNotes(id); };

function ntTree() {
  const byP = {};
  ntPages.forEach(p => (byP[p.parent_id ?? 'root'] ??= []).push(p));
  const walk = (p, depth) => {
    const kids = byP[p.id] ?? [];
    return `<div class="ntitem ${ntSel === p.id ? 'active' : ''}" data-ntopen="${p.id}" style="padding-left:${8 + depth * 14}px">
      ${kids.length ? `<span class="caret" data-ntfold="${p.id}">${ntFold.has(p.id) ? '▸' : '▾'}</span>` : '<span class="caret"></span>'}
      ${p.node_id ? '☑ ' : ''}${nesc(p.title)}</div>`
      + (ntFold.has(p.id) ? '' : kids.map(k => walk(k, depth + 1)).join(''));
  };
  return (byP['root'] ?? []).map(p => walk(p, 0)).join('');
}

async function renderNotes() {
  const page = ntSel ? await ntApi.get(ntSel) : null;
  const back = page ? await ntApi.backlinks(page.id) : [];
  document.getElementById('screen-notes').innerHTML = `
  <div class="notes-wrap">
    <div class="notes-tree">
      ${ntTree() || '<div class="empty">страниц нет</div>'}
      <div class="ntitem" style="color:var(--green)" id="ntAddRoot">＋ Новая страница</div>
    </div>
    <div class="editor">
      ${!page ? `<div class="muted">Выбери страницу слева или создай новую.<br><br>
          Подсказки: <b>[[Название]]</b> — ссылка на страницу или запись из Задач;
          markdown: # заголовок, - список, - [ ] чеклист, **жирный**, > цитата.<br>
          Вставь сюда любой текст из Notion — он уже markdown.</div>`
      : ntEditing ? `
        <input id="ntTitle" class="nttitle" value="${nesc(page.title)}">
        <textarea id="ntBody" class="ntbody">${nesc(page.content)}</textarea>
        <div class="btnrow" style="margin-top:8px">
          <span class="pill btn ok" id="ntSave">сохранить (⌘Enter)</span>
          <span class="pill btn" id="ntCancel">отмена (Esc)</span>
        </div>`
      : `
        <div class="row" style="display:flex;align-items:center;gap:8px">
          <h1 style="flex:1;margin:0">${nesc(page.title)}</h1>
          ${page.node_id ? `<span class="pill ok btn" data-ntnode="${page.node_id}">☑ к записи</span>` : ''}
          <span class="pill btn ok" id="ntEdit">✎ редактировать</span>
          <span class="pill btn" id="ntAddChild">＋ подстраница</span>
          <span class="pill btn danger" id="ntDel">🗑</span>
        </div>
        <div class="meta" style="margin:4px 0 14px">обновлено ${page.updated_at.slice(0, 16).replace('T', ' ')}</div>
        <div class="mdview">${page.content.trim() ? mdRender(page.content) : '<span class="muted">пусто — нажми ✎</span>'}</div>
        ${back.length ? `<div class="sec" style="margin-top:22px">↩ Бэклинки — ссылаются сюда</div>
          ${back.map(b => `<div class="ritem" data-ntopen="${b.id}"><div class="rt">${nesc(b.title)}</div></div>`).join('')}` : ''}`}
    </div>
  </div>`;
  bindNotes(page);
}

function bindNotes(page) {
  const $ = id => document.getElementById(id);
  document.querySelectorAll('#screen-notes [data-ntfold]').forEach(el =>
    el.addEventListener('click', e => {
      e.stopPropagation();
      const id = +el.dataset.ntfold;
      ntFold.has(id) ? ntFold.delete(id) : ntFold.add(id);
      renderNotes();
    }));
  document.querySelectorAll('#screen-notes [data-ntopen]').forEach(el =>
    el.addEventListener('click', () => { ntSel = +el.dataset.ntopen; ntEditing = false; renderNotes(); }));
  document.querySelectorAll('#screen-notes [data-ntnode]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.ntnode)));
  document.querySelectorAll('#screen-notes [data-wiki]').forEach(el =>
    el.addEventListener('click', async () => {
      const name = el.dataset.wiki;
      const r = await ntApi.wiki(name);
      if (r.type === 'page') { ntSel = r.id; ntEditing = false; renderNotes(); }
      else if (r.type === 'node') window.openNode(r.id);
      else if (confirm(`Страницы «${name}» нет. Создать?`)) {
        const p = await ntApi.add({ title: name, parent_id: ntSel });
        ntSel = p.id; renderNotes();
      }
    }));
  $('ntAddRoot')?.addEventListener('click', async () => {
    const t = prompt('Название страницы:');
    if (t?.trim()) { const p = await ntApi.add({ title: t.trim() }); window.loadNotes(p.id); }
  });
  $('ntAddChild')?.addEventListener('click', async () => {
    const t = prompt('Название подстраницы:');
    if (t?.trim()) { const p = await ntApi.add({ title: t.trim(), parent_id: ntSel }); window.loadNotes(p.id); }
  });
  $('ntEdit')?.addEventListener('click', () => { ntEditing = true; renderNotes(); });
  $('ntDel')?.addEventListener('click', async () => {
    const kids = ntPages.filter(p => p.parent_id === ntSel).length;
    if (confirm(`Удалить страницу «${page.title}»${kids ? ' с подстраницами' : ''}?`)) {
      await ntApi.del(ntSel);
      ntSel = null;
      window.loadNotes();
    }
  });
  const save = async () => {
    await ntApi.patch(ntSel, { title: $('ntTitle').value.trim() || page.title, content: $('ntBody').value });
    ntEditing = false;
    window.loadNotes(ntSel);
  };
  $('ntSave')?.addEventListener('click', save);
  $('ntCancel')?.addEventListener('click', () => { ntEditing = false; renderNotes(); });
  $('ntBody')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save();
    if (e.key === 'Escape') { ntEditing = false; renderNotes(); }
  });
  $('ntBody')?.focus();
}

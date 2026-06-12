/* Инфо: страницы-заметки — дерево, визуальный редактор (WYSIWYG ↔ markdown), [[вики]], бэклинки */
let ntPages = [], ntSel = null, ntEditing = false, ntMode = 'rich'; // rich | md
let ntAutoT = null;   // таймер автосейва (общий — гасится при каждом рендере)
const ntFold = new Set();
const ntPw = {};      // пароли открытых в этой сессии страниц
const ntCache = {};   // расшифрованное содержимое

const ntApi = {
  list: () => fetch('/api/pages').then(r => r.json()),
  get: id => fetch('/api/pages/' + id).then(r => r.json()),
  add: b => fetch('/api/pages', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  patch: (id, b) => fetch('/api/pages/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  del: id => fetch('/api/pages/' + id, { method: 'DELETE' }),
  backlinks: id => fetch(`/api/pages/${id}/backlinks`).then(r => r.json()),
  wiki: name => fetch('/api/wiki?name=' + encodeURIComponent(name)).then(r => r.json()),
  lock: (id, b) => fetch(`/api/pages/${id}/lock`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  unlock: (id, b) => fetch(`/api/pages/${id}/unlock`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
};

const nesc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ===== markdown → HTML =====
function mdRender(src) {
  const inline = s => s
    .replace(/\[\[([^\]]+)\]\]/g, (_, n) => `<a class="wiki" data-wiki="${nesc(n)}">${nesc(n)}</a>`)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, '$1<i>$2</i>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank">$1</a>');
  const lines = nesc(src).split('\n');
  let out = '', code = false, tbl = false;
  const lst = [];   // стек открытых списков: {type, ind}
  const closeList = () => { while (lst.length) out += `</${lst.pop().type}>`; };
  const closeTbl = () => { if (tbl) { out += '</table>'; tbl = false; } };
  for (const raw of lines) {
    if (raw.trim().startsWith('```')) { closeList(); closeTbl(); code = !code; out += code ? '<pre>' : '</pre>'; continue; }
    if (code) { out += raw + '\n'; continue; }
    const l = raw.trimEnd();
    let m;
    // таблица: | ячейка | ячейка |
    if (/^\s*\|.*\|\s*$/.test(l)) {
      const cells = l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      if (cells.every(c => /^:?-{2,}:?$/.test(c))) continue;   // разделительная строка
      closeList();
      const head = !tbl;
      if (!tbl) { out += '<table class="mdtable">'; tbl = true; }
      out += '<tr>' + cells.map(c => head ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`).join('') + '</tr>';
      continue;
    }
    closeTbl();
    if ((m = l.match(/^(#{1,3})\s+(.*)/))) { closeList(); out += `<h${m[1].length + 1}>${inline(m[2])}</h${m[1].length + 1}>`; }
    else if ((m = l.match(/^(\s*)(?:[-*]|(\d+)[.)])\s+(.*)$/))) {
      // список с вложенностью: 2 пробела отступа = уровень
      const ind = Math.floor(m[1].replace(/\t/g, '  ').length / 2);
      const type = m[2] != null ? 'ol' : 'ul';
      while (lst.length && lst.at(-1).ind > ind) out += `</${lst.pop().type}>`;
      if (lst.length && lst.at(-1).ind === ind && lst.at(-1).type !== type) out += `</${lst.pop().type}>`;
      if (!lst.length || lst.at(-1).ind < ind) { out += `<${type}>`; lst.push({ type, ind }); }
      const chk = m[3].match(/^\[( |x)\]\s+(.*)$/i);
      out += `<li>${chk ? (chk[1].trim() ? '☑ <s>' + inline(chk[2]) + '</s>' : '☐ ' + inline(chk[2])) : inline(m[3])}</li>`;
    }
    else if ((m = l.match(/^>\s?(.*)/))) { closeList(); out += `<blockquote>${inline(m[1])}</blockquote>`; }
    else if (!l.trim()) { closeList(); out += '<div class="mdgap"><br></div>'; }
    else { closeList(); out += `<p>${inline(l)}</p>`; }
  }
  closeList();
  closeTbl();
  if (code) out += '</pre>';
  return out;
}

// ===== HTML (из contenteditable) → markdown =====
function htmlToMd(root) {
  const inline = node => {
    let s = '';
    for (const n of node.childNodes) {
      if (n.nodeType === 3) { s += n.textContent; continue; }
      const tag = n.tagName;
      if (tag === 'BR') s += '\n';
      else if (tag === 'B' || tag === 'STRONG') s += '**' + inline(n) + '**';
      else if (tag === 'I' || tag === 'EM') s += '*' + inline(n) + '*';
      else if (tag === 'S' || tag === 'STRIKE' || tag === 'DEL') s += inline(n);
      else if (tag === 'CODE') s += '`' + inline(n) + '`';
      else if (tag === 'A') s += n.dataset?.wiki ? `[[${n.dataset.wiki}]]` : (n.getAttribute('href') ?? inline(n));
      else s += inline(n);
    }
    return s;
  };
  // список (с подсписками): UL/OL внутри li или соседом в родительском списке
  const listMd = (n, depth = 0) => {
    const ordered = n.tagName === 'OL';
    const parts = [];
    let i = 0;
    for (const ch of n.children) {
      if (ch.tagName === 'UL' || ch.tagName === 'OL') { parts.push(listMd(ch, depth + 1)); continue; }
      if (ch.tagName !== 'LI') continue;
      i++;
      const subs = [...ch.children].filter(c => c.tagName === 'UL' || c.tagName === 'OL');
      const own = inline({ childNodes: [...ch.childNodes].filter(c => !subs.includes(c)) }).trim();
      const marker = ordered ? `${i}. ` : '- ';
      const pad = '  '.repeat(depth);
      parts.push(own.startsWith('☑') ? pad + marker + '[x] ' + own.replace(/^☑\s*/, '')
        : own.startsWith('☐') ? pad + marker + '[ ] ' + own.replace(/^☐\s*/, '')
        : pad + marker + own);
      for (const s of subs) parts.push(listMd(s, depth + 1));
    }
    return parts.join('\n');
  };
  let out = [];
  for (const n of root.childNodes) {
    if (n.nodeType === 3) { if (n.textContent.trim()) out.push(n.textContent.trim()); continue; }
    const tag = n.tagName;
    if (tag === 'H1' || tag === 'H2') out.push('# ' + inline(n).trim());
    else if (tag === 'H3') out.push('## ' + inline(n).trim());
    else if (tag === 'H4') out.push('### ' + inline(n).trim());
    else if (tag === 'UL' || tag === 'OL') out.push(listMd(n));
    else if (tag === 'BLOCKQUOTE') out.push(inline(n).trim().split('\n').map(l => '> ' + l).join('\n'));
    else if (tag === 'PRE') out.push('```\n' + n.textContent.replace(/\n$/, '') + '\n```');
    else if (tag === 'TABLE') {
      const trs = [...n.querySelectorAll('tr')];
      const row = tr => '| ' + [...tr.children]
        .map(td => inline(td).trim().replace(/\|/g, '\\|').replace(/\n+/g, ' ')).join(' | ') + ' |';
      if (trs.length) {
        const lines = [row(trs[0]), '| ' + [...trs[0].children].map(() => '---').join(' | ') + ' |',
          ...trs.slice(1).map(row)];
        out.push(lines.join('\n'));
      }
    }
    else if (n.classList?.contains('mdgap')) out.push('');
    else if (n.querySelector?.('ul,ol,table,h1,h2,h3,h4,blockquote,pre')) {
      // браузер завернул блоки в DIV/P — разбираем содержимое рекурсивно, списки не плющим
      out.push(htmlToMd(n).trim());
    }
    else {
      const t = inline(n).trim();
      out.push(t); // P/DIV и неизвестные теги — как текст
    }
  }
  // схлопываем тройные пустые строки
  return out.join('\n\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

window.loadNotes = async function (openId) {
  await flushNotes();   // незаконченная правка не теряется при любом переходе
  ntPages = await ntApi.list();
  if (openId) { ntSel = openId; ntEditing = false; }
  if (ntSel && !ntPages.some(p => p.id === ntSel)) ntSel = null;
  renderNotes();
};
window.openPage = id => { showScreen('notes'); window.loadNotes(id); };

// автосохранение: если редактор открыт с правками — дописываем перед уходом
async function flushNotes() {
  const f = window.ntFlush;
  window.ntFlush = null;
  if (f) await f();
}

function ntTree() {
  const byP = {};
  ntPages.forEach(p => (byP[p.parent_id ?? 'root'] ??= []).push(p));
  const walk = (p, depth) => {
    const kids = byP[p.id] ?? [];
    return `<div class="ntitem ${ntSel === p.id ? 'active' : ''}" data-ntopen="${p.id}" draggable="true" style="padding-left:${8 + depth * 14}px">
      ${kids.length ? `<span class="caret" data-ntfold="${p.id}">${ntFold.has(p.id) ? '▸' : '▾'}</span>` : '<span class="caret"></span>'}
      ${p.locked ? '🔒 ' : ''}${p.node_id ? '☑ ' : ''}${nesc(p.title)}</div>`
      + (ntFold.has(p.id) ? '' : kids.map(k => walk(k, depth + 1)).join(''));
  };
  return (byP['root'] ?? []).map(p => walk(p, 0)).join('');
}

const TOOLBAR = [
  ['h2', 'Заголовок', () => document.execCommand('formatBlock', false, 'h2')],
  ['h3', 'Подзаголовок', () => document.execCommand('formatBlock', false, 'h3')],
  ['¶', 'обычный текст', () => document.execCommand('formatBlock', false, 'p')],
  ['B', 'жирный (⌘B)', () => document.execCommand('bold')],
  ['I', 'курсив (⌘I)', () => document.execCommand('italic')],
  ['•', 'список', () => document.execCommand('insertUnorderedList')],
  ['1.', 'нумерованный', () => document.execCommand('insertOrderedList')],
  ['☐', 'чеклист', () => { document.execCommand('insertUnorderedList'); document.execCommand('insertText', false, '☐ '); }],
  ['❝', 'цитата', () => document.execCommand('formatBlock', false, 'blockquote')],
  ['</>', 'блок кода', () => document.execCommand('formatBlock', false, 'pre')],
  ['[[ ]]', 'вики-ссылка', () => {
    const name = prompt('Ссылка на страницу или запись (название):');
    if (name?.trim()) document.execCommand('insertHTML', false,
      `<a class="wiki" data-wiki="${nesc(name.trim())}">${nesc(name.trim())}</a>&nbsp;`);
  }],
];

async function renderNotes() {
  clearTimeout(ntAutoT);   // правка ушла из DOM — хвостовой автосейв не нужен
  const page = ntSel ? await ntApi.get(ntSel) : null;
  const needPw = page?.locked && ntCache[page.id] == null;
  const content = page ? (page.locked ? (ntCache[page.id] ?? '') : page.content) : '';
  const back = page && !ntEditing && !needPw ? await ntApi.backlinks(page.id) : [];
  document.getElementById('screen-notes').innerHTML = `
  <div class="notes-wrap">
    <div class="notes-tree">
      ${ntTree() || '<div class="empty">страниц нет</div>'}
      <div class="ntitem" style="color:var(--green)" id="ntAddRoot">＋ Новая страница</div>
    </div>
    <div class="editor">
      ${!page ? `<div class="muted">Выбери страницу слева или создай новую.<br><br>
          В редакторе — панель оформления как в Ворде; <b>[[Название]]</b> — ссылка на страницу или запись.
          Вставка текста из Notion работает в режиме «</> markdown».</div>`
      : needPw ? `
        <h1 style="margin-bottom:10px">🔒 ${nesc(page.title)}</h1>
        <div class="muted" style="margin-bottom:10px">Страница под паролем — содержимое зашифровано.</div>
        <div class="task finadd" style="max-width:380px">
          <input id="ntPwIn" type="password" placeholder="пароль" style="flex:1">
          <span class="pill btn ok" id="ntPwGo">открыть</span>
        </div>
        <div class="btnrow" style="margin-top:10px"><span class="pill btn danger" id="ntPwRemove">🔓 снять пароль…</span></div>`
      : ntEditing ? `
        <input id="ntTitle" class="nttitle" value="${nesc(page.title)}">
        ${ntMode === 'rich' ? `
          <div class="nttoolbar">
            ${TOOLBAR.map(([label, hint], i) => `<span class="pill btn ntb" data-ntb="${i}" title="${hint}">${nesc(label)}</span>`).join('')}
            <span class="pill btn" id="ntModeMd" title="редактировать как markdown" style="margin-left:auto">&lt;/&gt; markdown</span>
          </div>
          <div id="ntRich" class="mdview richedit" contenteditable="true" spellcheck="false">${mdRender(content)}</div>`
        : `
          <div class="nttoolbar">
            <span class="meta">markdown-режим: # заголовок · - список · - [ ] чеклист · > цитата · [[ссылка]]</span>
            <span class="pill btn" id="ntModeRich" style="margin-left:auto">Aa визуальный</span>
          </div>
          <textarea id="ntBody" class="ntbody">${nesc(content)}</textarea>`}
        <div class="btnrow" style="margin-top:8px">
          <span class="pill btn ok" id="ntSave">сохранить (⌘Enter)</span>
          <span class="pill btn" id="ntCancel">отмена (Esc)</span>
        </div>`
      : `
        <div class="row" style="display:flex;align-items:center;gap:8px">
          <h1 style="flex:1;margin:0">${nesc(page.title)}</h1>
          ${page.node_id ? `<span class="pill ok btn" data-ntnode="${page.node_id}">☑ к записи</span>` : ''}
          <span class="pill btn ok" id="ntEdit">✎ редактировать</span>
          <span class="pill btn" id="ntHist" title="прошлые версии страницы">⏪ история</span>
          ${page.locked ? '<span class="pill btn" id="ntLockBtn">🔓 снять пароль</span>' : ''}
          <span class="pill btn" id="ntAddChild">＋ подстраница</span>
          <span class="pill btn danger" id="ntDel">🗑</span>
        </div>
        <div class="meta" style="margin:4px 0 14px">обновлено ${page.updated_at.slice(0, 16).replace('T', ' ')}</div>
        <div id="ntHistBox"></div>
        <div class="mdview" id="ntView" title="клик по тексту — редактировать">${content.trim() ? mdRender(content) : '<span class="muted">пусто — кликни сюда и пиши</span>'}</div>
        ${back.length ? `<div class="sec" style="margin-top:22px">↩ Бэклинки — ссылаются сюда</div>
          ${back.map(b => `<div class="ritem" data-ntopen="${b.id}"><div class="rt">${nesc(b.title)}</div></div>`).join('')}` : ''}`}
    </div>
  </div>`;
  bindNotes(page);
}

// DnD дерева страниц: середина — вложить, края — поставить выше/ниже
let ntDrag = null;
function bindNtDnd() {
  const clear = () => document.querySelectorAll('.ntitem.dropinto,.ntitem.dropbefore,.ntitem.dropafter')
    .forEach(x => x.classList.remove('dropinto', 'dropbefore', 'dropafter'));
  document.querySelectorAll('.notes-tree .ntitem[data-ntopen]').forEach(el => {
    el.addEventListener('dragstart', () => { ntDrag = +el.dataset.ntopen; });
    el.addEventListener('dragover', e => {
      if (ntDrag == null || +el.dataset.ntopen === ntDrag) return;
      e.preventDefault();
      const r = el.getBoundingClientRect();
      const y = (e.clientY - r.top) / r.height;
      el.classList.remove('dropinto', 'dropbefore', 'dropafter');
      el.classList.add(y < 0.3 ? 'dropbefore' : y > 0.7 ? 'dropafter' : 'dropinto');
    });
    el.addEventListener('dragleave', () => el.classList.remove('dropinto', 'dropbefore', 'dropafter'));
    el.addEventListener('drop', async e => {
      e.preventDefault();
      const zone = el.classList.contains('dropbefore') ? 'before'
        : el.classList.contains('dropafter') ? 'after' : 'into';
      clear();
      if (ntDrag == null) return;
      await flushNotes();
      const tid = +el.dataset.ntopen;
      const url = zone === 'into'
        ? [`/api/pages/${ntDrag}/move`, { parent_id: tid }]
        : [`/api/pages/${ntDrag}/reorder`, { ref_id: tid, where: zone }];
      const r = await fetch(url[0], { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(url[1]) }).then(x => x.json());
      if (r.error) alert(r.error);
      ntDrag = null;
      window.loadNotes();
    });
    el.addEventListener('dragend', clear);
  });
}

function bindNotes(page) {
  const $ = id => document.getElementById(id);
  bindNtDnd();
  document.querySelectorAll('#screen-notes [data-ntfold]').forEach(el =>
    el.addEventListener('click', e => {
      e.stopPropagation();
      const id = +el.dataset.ntfold;
      ntFold.has(id) ? ntFold.delete(id) : ntFold.add(id);
      renderNotes();
    }));
  document.querySelectorAll('#screen-notes [data-ntopen]').forEach(el =>
    el.addEventListener('click', async () => { await flushNotes(); ntSel = +el.dataset.ntopen; ntEditing = false; renderNotes(); }));
  document.querySelectorAll('#screen-notes [data-ntnode]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.ntnode)));
  if (!ntEditing)
    document.querySelectorAll('#screen-notes [data-wiki]').forEach(el =>
      el.addEventListener('click', async () => {
        const name = el.dataset.wiki;
        const r = await ntApi.wiki(name);
        if (r.type === 'page') { ntSel = r.id; renderNotes(); }
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
  $('ntHist')?.addEventListener('click', async () => {
    const box = $('ntHistBox');
    if (box.innerHTML) { box.innerHTML = ''; return; }
    const revs = await fetch(`/api/pages/${ntSel}/revisions`).then(r => r.json());
    box.innerHTML = revs.map(r => `
      <div class="ritem"><div class="rt">${r.saved_at.slice(0, 16).replace('T', ' ')} · ${r.len} симв.</div>
        <div class="rm">${nesc(r.preview)}… <span class="pill btn ok" data-ntrev="${r.id}">восстановить</span></div></div>`).join('')
      || '<div class="empty">версий пока нет — они копятся при правках (не чаще раза в 10 минут)</div>';
    box.querySelectorAll('[data-ntrev]').forEach(el =>
      el.addEventListener('click', async () => {
        if (!confirm('Вернуть эту версию? Текущий текст уйдёт в историю.')) return;
        const r = await fetch(`/api/pages/${ntSel}/revisions/${el.dataset.ntrev}/restore`, { method: 'POST' }).then(x => x.json());
        if (r.error) { alert(r.error); return; }
        window.loadNotes(ntSel);
      }));
  });
  // клик по тексту страницы — сразу в редактор (ссылки продолжают работать)
  $('ntView')?.addEventListener('click', e => {
    if (e.target.closest('a')) return;
    ntEditing = true; renderNotes();
  });
  $('ntDel')?.addEventListener('click', async () => {
    const kids = ntPages.filter(p => p.parent_id === ntSel).length;
    if (confirm(`Удалить страницу «${page.title}»${kids ? ' с подстраницами' : ''}?`)) {
      await ntApi.del(ntSel);
      ntSel = null;
      window.loadNotes();
    }
  });

  // редактор
  document.querySelectorAll('#screen-notes [data-ntb]').forEach(el => {
    el.addEventListener('mousedown', e => e.preventDefault()); // не терять выделение
    el.addEventListener('click', () => { TOOLBAR[+el.dataset.ntb][2](); $('ntRich')?.focus(); });
  });
  const currentMd = () => {
    if (ntMode !== 'rich') return $('ntBody').value;
    const md = htmlToMd($('ntRich'));
    // страховка: если конвертация дала пустоту, а текст в редакторе есть — берём как есть
    if (!md.trim() && $('ntRich')?.innerText.trim()) return $('ntRich').innerText;
    return md;
  };
  $('ntModeMd')?.addEventListener('click', () => {
    page.content = htmlToMd($('ntRich'));   // переносим правки между режимами
    ntMode = 'md'; renderNotes();
  });
  $('ntModeRich')?.addEventListener('click', () => {
    page.content = $('ntBody').value;
    ntMode = 'rich'; renderNotes();
  });
  const saveData = async (isAuto = false) => {
    const title = $('ntTitle')?.value.trim() || page.title;
    const md = currentMd();
    // предохранитель: текст резко сократился — автосейв молчать не имеет права
    const oldLen = ((page.locked ? ntCache[ntSel] : page.content) ?? '').trim().length;
    const newLen = md.trim().length;
    if (oldLen > 200 && newLen < oldLen * 0.3) {
      if (isAuto) {
        const sb = document.getElementById('statusbar');
        if (sb) sb.textContent = `⚠ автосейв пропущен: текст сократился ${oldLen} → ${newLen} симв. — сохрани кнопкой или отмени`;
        return false;
      }
      if (!confirm(`Текст стал сильно короче (${oldLen} → ${newLen} симв.). Точно сохранить?\n\nЕсли это ошибка — «Отмена», прежние версии есть в «истории».`)) return false;
    }
    try {
      if (page.locked) {
        const r = await ntApi.lock(ntSel, { password: ntPw[ntSel], content: md });
        if (r.error) { alert('Не сохранилось: ' + r.error); return false; }
        ntCache[ntSel] = md;
        await ntApi.patch(ntSel, { title });
      } else {
        const r = await ntApi.patch(ntSel, { title, content: md });
        if (r?.error) { alert('Не сохранилось: ' + r.error); return false; }
      }
      const sb = document.getElementById('statusbar');
      if (sb) sb.textContent = `✓ Инфо сохранено ${new Date().toTimeString().slice(0, 8)} · ${md.trim().length} симв. (стр. ${ntSel})`;
      return true;
    } catch (e) {
      alert('Не сохранилось: ' + e.message);
      return false;
    }
  };
  // пока редактор открыт, правки можно дописать при любом уходе со страницы
  window.ntFlush = (ntEditing && page && !(page.locked && ntCache[page.id] == null)) ? saveData : null;
  // автосохранение: 1.5 сек тишины при наборе; вставка из буфера пишется сразу
  for (const id of ['ntBody', 'ntRich']) {
    $(id)?.addEventListener('input', () => {
      clearTimeout(ntAutoT);
      ntAutoT = setTimeout(() => saveData(true), 1500);
    });
    $(id)?.addEventListener('paste', () => {
      clearTimeout(ntAutoT);
      ntAutoT = setTimeout(() => saveData(true), 250);   // даём DOM принять вставку — и пишем
    });
  }
  // умная вставка в визуальный редактор: Notion кладёт таблицы как текст с табами,
  // а текст — как markdown; превращаем в нормальные таблицы/списки на лету
  $('ntRich')?.addEventListener('paste', e => {
    const html = e.clipboardData.getData('text/html');
    const text = e.clipboardData.getData('text/plain').replace(/\r/g, '');
    // HTML-разметка (Notion, сайты, Word, заметки): нормализуем через наш конвертер —
    // заголовки/списки/таблицы/жирный остаются, мусорные стили выбрасываются
    if (html && /<(table|h[1-6]|ul|ol|li|b|strong|i|em|blockquote|pre|p|br)[\s>/]/i.test(html)) {
      e.preventDefault();
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      tmp.querySelectorAll('script,style,meta,link,head,title').forEach(x => x.remove());
      const md = htmlToMd(tmp);
      document.execCommand('insertHTML', false, md.trim() ? mdRender(md) : nesc(text));
      return;
    }
    const rows = text.split('\n').filter(l => l.trim());
    if (rows.length > 1 && rows.every(r => r.includes('\t'))) {
      // таб-таблица (Notion/Excel) → таблица
      e.preventDefault();
      const md = ['| ' + rows[0].split('\t').join(' | ') + ' |',
        '| ' + rows[0].split('\t').map(() => '---').join(' | ') + ' |',
        ...rows.slice(1).map(r => '| ' + r.split('\t').join(' | ') + ' |')].join('\n');
      document.execCommand('insertHTML', false, mdRender(md));
      return;
    }
    // markdown-текст (заголовки/списки/чеклисты/жирный) → оформленный вид
    if (!html && /^(#{1,3}|[-*]|\d+[.)])\s|\*\*|\[\[|^\|.*\|/m.test(text)) {
      e.preventDefault();
      document.execCommand('insertHTML', false, mdRender(text));
    }
  });
  const save = async () => {
    clearTimeout(ntAutoT);
    if (!await saveData()) return;   // ошибка показана — правки не выбрасываем
    window.ntFlush = null;
    ntEditing = false;
    window.loadNotes(ntSel);
  };
  $('ntSave')?.addEventListener('click', save);
  $('ntCancel')?.addEventListener('click', () => { clearTimeout(ntAutoT); window.ntFlush = null; ntEditing = false; renderNotes(); });
  for (const id of ['ntBody', 'ntRich'])
    $(id)?.addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
      if (e.key === 'Escape') { clearTimeout(ntAutoT); window.ntFlush = null; ntEditing = false; renderNotes(); }
    });
  ($('ntRich') ?? $('ntBody'))?.focus();

  // ===== пароль =====
  const tryUnlock = async (remove) => {
    const pw = remove
      ? (ntPw[ntSel] ?? prompt('Пароль страницы:'))
      : $('ntPwIn')?.value;
    if (!pw) return;
    const r = await ntApi.unlock(ntSel, { password: pw, remove });
    if (r.error) { alert(r.error); return; }
    if (remove) { delete ntPw[ntSel]; delete ntCache[ntSel]; window.loadNotes(ntSel); return; }
    ntPw[ntSel] = pw;
    ntCache[ntSel] = r.content;
    renderNotes();
  };
  $('ntPwGo')?.addEventListener('click', () => tryUnlock(false));
  $('ntPwIn')?.addEventListener('keydown', e => { if (e.key === 'Enter') tryUnlock(false); });
  $('ntPwIn')?.focus();
  $('ntPwRemove')?.addEventListener('click', async () => {
    if (confirm('Снять пароль? Текст снова будет храниться открыто и попадёт в поиск.')) tryUnlock(true);
  });
  $('ntLockBtn')?.addEventListener('click', async () => {
    if (page.locked) {
      if (confirm('Снять пароль с этой страницы?')) {
        const pw = ntPw[ntSel] ?? prompt('Пароль страницы:');
        if (!pw) return;
        const r = await ntApi.unlock(ntSel, { password: pw, remove: true });
        if (r.error) { alert(r.error); return; }
        delete ntPw[ntSel]; delete ntCache[ntSel];
        window.loadNotes(ntSel);
      }
    }
    // пароли на отдельные страницы убраны: раздел Инфо и так под общим замком
  });
}

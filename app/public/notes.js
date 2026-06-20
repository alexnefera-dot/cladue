/* Инфо: страницы-заметки — дерево, визуальный редактор (WYSIWYG ↔ markdown), [[вики]], бэклинки */
let ntPages = [], ntSel = null, ntEditing = false, ntMode = 'rich'; // rich | md
let ntAutoT = null;   // таймер автосейва (общий — гасится при каждом рендере)
let ntSavedRange = null;   // последняя позиция курсора в #ntRich — чтобы вставлять файл/картинку туда, а не в конец
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

const nesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ===== markdown → HTML =====
function mdRender(src) {
  const inline = s => s
    .replace(/!\[([^\]]*)\]\((\/api\/attachments\/\d+|https?:[^)\s]+)\)/g, '<img src="$2" alt="$1" class="mdimg">')
    .replace(/\[\[([^\]]+)\]\]/g, (_, n) => `<a class="wiki" data-wiki="${nesc(n)}">${nesc(n)}</a>`)
    .replace(/\[([^\]]+)\]\((\/api\/attachments\/\d+|https?:[^)\s]+)\)/g, (_, t, u) =>
      u.startsWith('/api/') ? `<a href="${u}" class="attlink">${t}</a>` : `<a href="${u}" target="_blank">${t}</a>`)
    .replace(/~~([^~\n]+)~~/g, '<s>$1</s>')
    .replace(/&lt;u&gt;([^&]*?)&lt;\/u&gt;/g, '<u>$1</u>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|\W)\*([^*\n]+)\*(?=\W|$)/g, '$1<i>$2</i>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/(?<!["'=\]])(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank">$1</a>');
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
  // оформление часто приходит инлайн-стилем (font-weight/italic у span), а не тегами <b>/<i>
  // (так копирует WebKit, Google Docs, Word). Сохраняем жирный/курсив/подчёркивание и из стилей.
  const styleWrap = (n, inner) => {
    if (!inner.trim() || !n.style) return inner;
    const fw = n.style.fontWeight || '', fs = n.style.fontStyle || '';
    const td = (n.style.textDecorationLine || n.style.textDecoration || '');
    if (fs === 'italic' || fs === 'oblique') inner = '*' + inner + '*';
    if (fw === 'bold' || fw === 'bolder' || parseInt(fw, 10) >= 600) inner = '**' + inner + '**';
    if (td.includes('line-through')) inner = '~~' + inner + '~~';
    if (td.includes('underline')) inner = '<u>' + inner + '</u>';
    return inner;
  };
  const inline = node => {
    let s = '';
    for (const n of node.childNodes) {
      if (n.nodeType === 3) { s += n.textContent; continue; }
      const tag = n.tagName;
      if (tag === 'BR') s += '\n';
      else if (tag === 'IMG') { const src = n.getAttribute('src') || ''; if (!/^\s*(javascript|vbscript):/i.test(src)) s += `![${n.getAttribute('alt') || ''}](${src})`; }
      else if (tag === 'B' || tag === 'STRONG') s += '**' + inline(n) + '**';
      else if (tag === 'I' || tag === 'EM') s += '*' + inline(n) + '*';
      else if (tag === 'S' || tag === 'STRIKE' || tag === 'DEL') s += '~~' + inline(n) + '~~';
      else if (tag === 'U') s += '<u>' + inline(n) + '</u>';
      else if (tag === 'CODE') s += '`' + inline(n) + '`';
      else if (tag === 'A') {
        let href = n.getAttribute('href');
        if (href && /^\s*(javascript|data|vbscript):/i.test(href)) href = null;   // не тащим опасные схемы в markdown
        const txt = inline(n).trim();
        s += n.dataset?.wiki ? `[[${n.dataset.wiki}]]`
          : href && txt && txt !== href ? `[${txt}](${href})`
          : (href ?? txt);
      }
      else s += styleWrap(n, inline(n));   // span/div со стилем bold/italic — сохраняем оформление
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
      let own = inline({ childNodes: [...ch.childNodes].filter(c => !subs.includes(c)) }).trim();
      own = own.replace(/^(☑\s*)~~(.*)~~$/, '$1$2');   // зачёркнутость чеклиста — из [x], не из ~~
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
    if (tag === 'IMG') { const src = n.getAttribute('src') || ''; if (!/^\s*(javascript|vbscript):/i.test(src)) out.push(`![${n.getAttribute('alt') || ''}](${src})`); }
    else if (tag === 'H1' || tag === 'H2') out.push('# ' + inline(n).trim());
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
      const t = styleWrap(n, inline(n).trim());   // P/DIV/SPAN: текст + сохраняем bold/italic из стиля
      out.push(t);
    }
  }
  // схлопываем тройные пустые строки
  return out.join('\n\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

// ===== Буфер обмена → markdown (общая логика для вставки в редактор и в просмотр) =====
function clipboardToMd(html, text) {
  // любой HTML с разметкой пробуем превратить в markdown (оформление часто в span/div со стилем,
  // а не в тегах <b>/<i> — тогда старое условие его не ловило и стирало жирный/курсив)
  if (html && /<(span|div|font|a|table|h[1-6]|ul|ol|li|b|strong|i|em|u|s|blockquote|pre|p|br)[\s>/]/i.test(html)) {
    try {
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      tmp.querySelectorAll('script,style,meta,link,head,title').forEach(x => x.remove());
      const md = htmlToMd(tmp).trim();
      if (md) return md;
    } catch { /* падаем на текст */ }
  }
  const t = (text ?? '').replace(/\r/g, '');
  const rows = t.split('\n').filter(l => l.trim());
  if (rows.length > 1 && rows.every(r => r.includes('\t')))
    return ['| ' + rows[0].split('\t').join(' | ') + ' |',
      '| ' + rows[0].split('\t').map(() => '---').join(' | ') + ' |',
      ...rows.slice(1).map(r => '| ' + r.split('\t').join(' | ') + ' |')].join('\n');
  return t;
}

// ===== Хранение страницы как HTML (а не markdown) — нативное редактирование списков/отступов =====
// Маркер в начале content помечает HTML-страницы. Без маркера — легаси-markdown (рендерим как раньше).
const HTML_MARK = '<!--pbhtml-->';
const isHtmlContent = c => typeof c === 'string' && c.startsWith(HTML_MARK);
// чистим вставленный/сохраняемый HTML: убираем скрипты и опасные атрибуты, оформление оставляем
function sanitizeHtml(html) {
  const tmp = document.createElement('div');
  tmp.innerHTML = html || '';
  tmp.querySelectorAll('script,style,meta,link,head,title,iframe,object,embed,noscript').forEach(x => x.remove());
  tmp.querySelectorAll('*').forEach(el => {
    for (const a of [...el.attributes]) {
      const n = a.name.toLowerCase();
      if (n.startsWith('on')) el.removeAttribute(a.name);                                   // onclick и т.п.
      else if ((n === 'href' || n === 'src') && /^\s*(javascript|vbscript):/i.test(a.value)) el.removeAttribute(a.name);
      else if (n === 'href' && /^\s*data:/i.test(a.value)) el.removeAttribute(a.name);      // data: только для картинок (src)
    }
  });
  return tmp.innerHTML;
}
// content → HTML для contenteditable (легаси-markdown рендерим, HTML отдаём как есть)
function contentToHtml(content) {
  return isHtmlContent(content) ? sanitizeHtml(content.slice(HTML_MARK.length)) : mdRender(content || '');
}
// content → markdown для режима «</> markdown»
function contentToMd(content) {
  if (!isHtmlContent(content)) return content || '';
  const tmp = document.createElement('div'); tmp.innerHTML = content.slice(HTML_MARK.length);
  return htmlToMd(tmp);
}

// вставка HTML в позицию курсора contenteditable — надёжнее execCommand (Safari)
function ntInsertHtml(htmlStr) {
  const rich = document.getElementById('ntRich');
  if (!rich) return false;
  rich.focus();
  const sel = window.getSelection();
  let range = sel.rangeCount ? sel.getRangeAt(0) : null;
  if (!range || !rich.contains(range.commonAncestorContainer)) {
    // выделение потерялось (клик по 📎/панели) — берём последнюю позицию курсора в тексте
    range = (ntSavedRange && rich.contains(ntSavedRange.commonAncestorContainer)) ? ntSavedRange.cloneRange() : null;
  }
  if (!range) {
    range = document.createRange();
    range.selectNodeContents(rich);
    range.collapse(false);
  }
  range.deleteContents();
  const frag = range.createContextualFragment(htmlStr);
  const last = frag.lastChild;
  range.insertNode(frag);
  if (last) {
    range.setStartAfter(last);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
  }
  return true;
}

// вставка прямо в ПРОСМОТР страницы: дописываем в конец без открытия редактора
document.addEventListener('paste', async e => {
  if (document.getElementById('screen-notes')?.style.display === 'none') return;
  if (ntEditing || !ntSel) return;
  if (e.target.closest('input,textarea,[contenteditable]')) return;
  const page = ntPages.find(p => p.id === ntSel);
  if (!page || page.locked) return;
  e.preventDefault();
  const md = clipboardToMd(e.clipboardData.getData('text/html'), e.clipboardData.getData('text/plain'));
  if (!md.trim()) return;
  const cur = await ntApi.get(ntSel);
  await ntApi.patch(ntSel, { content: (cur.content?.trim() ? cur.content.replace(/\s+$/, '') + '\n\n' : '') + md });
  const sb = document.getElementById('statusbar');
  if (sb) sb.textContent = `✓ вставлено в конец страницы · ${md.trim().length} симв.`;
  window.loadNotes(ntSel);
});

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
    return `<div class="ntitem ${ntSel === p.id ? 'active' : ''} ${kids.length ? 'ntparent' : ''}" data-ntopen="${p.id}" draggable="true" style="padding-left:${8 + depth * 14}px">
      ${kids.length ? `<span class="caret" data-ntfold="${p.id}">${ntFold.has(p.id) ? '▸' : '▾'}</span>` : '<span class="caret"></span>'}
      ${p.locked ? '🔒 ' : ''}${p.node_id ? '☑ ' : ''}${nesc(p.title)}</div>`
      + (ntFold.has(p.id) ? '' : kids.map(k => walk(k, depth + 1)).join(''));
  };
  return (byP['root'] ?? []).map(p => walk(p, 0)).join('');
}

const ntMobile = () => window.matchMedia('(max-width: 768px)').matches;

// плоский список страниц с глубиной — для выпадающего выбора на телефоне
function ntFlat() {
  const byP = {};
  ntPages.forEach(p => (byP[p.parent_id ?? 'root'] ??= []).push(p));
  const out = [];
  const walk = (p, depth) => { out.push({ ...p, depth }); (byP[p.id] ?? []).forEach(k => walk(k, depth + 1)); };
  (byP['root'] ?? []).forEach(p => walk(p, 0));
  return out;
}

// телефон: разделы — выпадающим списком, редактор на весь экран
function ntPickerMobile() {
  const flat = ntFlat();
  const opts = flat.map(p => `<option value="${p.id}"${ntSel === p.id ? ' selected' : ''}>${'　'.repeat(p.depth)}${p.locked ? '🔒 ' : ''}${nesc(p.title)}</option>`).join('');
  return `<div class="ntpick">
    <select id="ntPick" class="ntpicksel">${flat.length ? opts : '<option value="">страниц нет</option>'}</select>
    <span class="pill btn ok" id="ntAddRoot" title="новая страница">＋ стр.</span>
  </div>`;
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
  ntEditing = !!(page && !needPw);   // страница всегда в редактируемом режиме
  const back = page && !needPw ? await ntApi.backlinks(page.id) : [];
  document.getElementById('screen-notes').innerHTML = `
  <div class="notes-wrap">
    ${ntMobile() ? ntPickerMobile() : `<div class="notes-tree">
      ${ntTree() || '<div class="empty">страниц нет</div>'}
      <div class="ntitem" style="color:var(--green)" id="ntAddRoot">＋ Новая страница</div>
    </div>`}
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
      : `
        <div class="row" style="display:flex;align-items:center;gap:8px">
          <input id="ntTitle" class="nttitle" value="${nesc(page.title)}" style="flex:1;margin:0">
          ${window.sphSelHtml ? window.sphSelHtml('page', page.id, page.area_id) : ''}
          ${page.node_id ? `<span class="pill ok btn" data-ntnode="${page.node_id}">☑ к записи</span>` : ''}
          <span class="pill btn" id="ntHist" title="прошлые версии — восстановить любую">⏪ история</span>
          ${page.locked ? '<span class="pill btn" id="ntLockBtn">🔓 снять пароль</span>' : ''}
          <span class="pill btn" id="ntAddChild">＋ подстраница</span>
          <span class="pill btn danger" id="ntDel">🗑</span>
        </div>
        <div class="meta" style="margin:4px 0 10px">обновлено ${page.updated_at.slice(0, 16).replace('T', ' ')} · сохраняется само · ⌘Z — откат · <b style="color:var(--green)">ред.v3 ✦</b></div>
        <div id="ntHistBox"></div>
        ${ntMode === 'rich' ? `
          <div class="nttoolbar">
            ${TOOLBAR.map(([label, hint], i) => `<span class="pill btn ntb" data-ntb="${i}" title="${hint}">${nesc(label)}</span>`).join('')}
            <label class="pill btn ntb" title="вставить картинку или PDF" style="cursor:pointer">📎 файл<input type="file" id="ntFile" accept="image/*,application/pdf" style="position:absolute;width:1px;height:1px;opacity:0;overflow:hidden;pointer-events:none"></label>
            <span class="pill btn" id="ntModeMd" title="редактировать как markdown" style="margin-left:auto">&lt;/&gt; markdown</span>
          </div>
          <div id="ntRich" class="mdview richedit" contenteditable="true" spellcheck="false" data-ph="пиши здесь — сохранится само">${contentToHtml(content)}</div>`
        : `
          <div class="nttoolbar">
            <span class="meta">markdown-режим: # заголовок · - список · - [ ] чеклист · > цитата · [[ссылка]]</span>
            <label class="pill btn ntb" title="вставить картинку или PDF" style="cursor:pointer">📎 файл<input type="file" id="ntFile" accept="image/*,application/pdf" style="position:absolute;width:1px;height:1px;opacity:0;overflow:hidden;pointer-events:none"></label>
            <span class="pill btn" id="ntModeRich" style="margin-left:auto">Aa визуальный</span>
          </div>
          <textarea id="ntBody" class="ntbody">${nesc(contentToMd(content))}</textarea>`}
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
  $('ntPick')?.addEventListener('change', async e => {   // телефон: выбор раздела из списка
    await flushNotes(); ntSel = +e.target.value || null; ntEditing = false; renderNotes();
  });
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
  // содержимое для сохранения: rich → HTML (с маркером), md → чистый markdown
  const currentMd = () => ntMode === 'rich' ? HTML_MARK + sanitizeHtml($('ntRich').innerHTML) : $('ntBody').value;
  $('ntModeMd')?.addEventListener('click', () => {
    page.content = HTML_MARK + sanitizeHtml($('ntRich').innerHTML);   // переносим правки между режимами
    ntMode = 'md'; renderNotes();
  });
  $('ntModeRich')?.addEventListener('click', () => {
    page.content = $('ntBody').value;   // markdown без маркера → отрисуется в HTML
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
  // панель оформления: скрыта, пока не кликнул в текст; дальше остаётся (класс не снимаем),
  // чтобы клики по самой панели (📎 и т.п.) её не сворачивали и контент не прыгал
  const editorEl = document.querySelector('#screen-notes .editor');
  for (const id of ['ntBody', 'ntRich'])
    $(id)?.addEventListener('focus', () => editorEl?.classList.add('nt-on'));
  // запоминаем позицию курсора в тексте — чтобы файл/картинка вставлялись туда, куда ты ткнул
  ntSavedRange = null;
  const saveRange = () => {
    const s = window.getSelection();
    if (s.rangeCount && $('ntRich')?.contains(s.getRangeAt(0).commonAncestorContainer)) ntSavedRange = s.getRangeAt(0).cloneRange();
  };
  $('ntRich')?.addEventListener('keyup', saveRange);
  $('ntRich')?.addEventListener('mouseup', saveRange);
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
  // вставка: картинку из буфера грузим вложением; HTML вставляем нативно (списки/жирный/курсив
  // сохраняются), очистив опасное; простой текст вставляет сам браузер
  $('ntRich')?.addEventListener('paste', e => {
    const imgFile = [...(e.clipboardData.files || [])].find(f => f.type.startsWith('image/'));
    if (imgFile) { e.preventDefault(); uploadAttachment(imgFile); return; }
    const html = e.clipboardData.getData('text/html');
    if (html && html.trim()) {
      e.preventDefault();
      const clean = sanitizeHtml(html);
      if (!document.execCommand('insertHTML', false, clean)) ntInsertHtml(clean);
      clearTimeout(ntAutoT);
      ntAutoT = setTimeout(() => saveData(true), 250);
    }
  });
  // Tab/Shift+Tab — вложенность списка (и отступ абзаца), как в Notes
  $('ntRich')?.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    e.preventDefault();
    document.execCommand(e.shiftKey ? 'outdent' : 'indent');
    clearTimeout(ntAutoT);
    ntAutoT = setTimeout(() => saveData(true), 800);
  });

  // ===== Вложения: картинки/PDF — кнопка 📎, drag&drop, вставка из буфера =====
  const uploadAttachment = async (file) => {
    if (!file || !ntSel) return;
    const MAXMB = 25;
    if (file.size > MAXMB * 1024 * 1024) { alert(`Файл больше ${MAXMB} МБ — слишком крупный для базы.`); return; }
    const sb = document.getElementById('statusbar');
    if (sb) sb.textContent = `⏳ загружаю ${file.name}…`;
    try {
      const data = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(String(r.result).split(',')[1] || '');
        r.onerror = () => rej(new Error('чтение файла'));
        r.readAsDataURL(file);
      });
      const meta = await fetch(`/api/pages/${ntSel}/attachments`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: file.name, mime: file.type || 'application/octet-stream', data }) }).then(r => r.json());
      if (!meta || meta.error || !meta.url) { alert('Не загрузилось: ' + (meta?.error || 'ошибка')); return; }
      const isImg = (file.type || '').startsWith('image/');
      if (ntMode === 'rich') {
        ntInsertHtml(isImg ? `<img src="${meta.url}" alt="${nesc(file.name)}" class="mdimg">`
          : `<a href="${meta.url}" class="attlink">📎 ${nesc(file.name)}</a>&nbsp;`);
      } else {
        const ta = $('ntBody');
        const ins = isImg ? `\n![${file.name}](${meta.url})\n` : `\n[📎 ${file.name}](${meta.url})\n`;
        const at = ta.selectionStart ?? ta.value.length;
        ta.value = ta.value.slice(0, at) + ins + ta.value.slice(at);
      }
      if (sb) sb.textContent = `✓ вставлено: ${file.name}`;
      clearTimeout(ntAutoT);
      ntAutoT = setTimeout(() => saveData(true), 250);
    } catch (err) {
      alert('Не загрузилось: ' + err.message);
    }
  };
  // 📎 файл — <label> открывает пикер нативно (программный .click() по скрытому input WKWebView блокирует)
  $('ntFile')?.addEventListener('change', e => { uploadAttachment(e.target.files[0]); e.target.value = ''; });
  // перетащил файл в редактор — грузим
  $('ntRich')?.addEventListener('dragover', e => { if (e.dataTransfer?.types?.includes('Files')) e.preventDefault(); });
  $('ntRich')?.addEventListener('drop', e => {
    const f = [...(e.dataTransfer?.files || [])].find(x => x.type.startsWith('image/') || x.type === 'application/pdf');
    if (f) { e.preventDefault(); uploadAttachment(f); }
  });
  // клик по вложению-ссылке (PDF) — открыть в новой вкладке, не редактируем
  $('ntRich')?.addEventListener('click', e => {
    const a = e.target.closest('a.attlink');
    if (!a) return;
    e.preventDefault();
    window.open(a.getAttribute('href'), '_blank');
  });
  // заголовок сохраняется сам, ⌘Enter — сохранить немедленно
  $('ntTitle')?.addEventListener('input', () => {
    clearTimeout(ntAutoT);
    ntAutoT = setTimeout(() => saveData(true), 1500);
  });
  for (const id of ['ntBody', 'ntRich', 'ntTitle'])
    $(id)?.addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); clearTimeout(ntAutoT); saveData(false); }
    });

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

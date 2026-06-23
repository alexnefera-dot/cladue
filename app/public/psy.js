/* Психология: практики · колесо · рабочий лог · принятые решения. UI-замок по паролю. */
let psyData = null, psyTab = 'practices', psyUnlocked = false, psyOpenLogs = null;

const psyApi = {
  get: () => fetch('/api/psy').then(r => r.json()),
  unlock: pw => fetch('/api/psy/unlock', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: pw }) }).then(r => r.json()),
  setPass: b => fetch('/api/psy/pass', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }).then(r => r.json()),
  pAdd: b => fetch('/api/psy/practices', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  pPatch: (id, b) => fetch('/api/psy/practices/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  pDel: id => fetch('/api/psy/practices/' + id, { method: 'DELETE' }),
  pLog: (id, b) => fetch(`/api/psy/practices/${id}/log`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  pLogs: id => fetch(`/api/psy/practices/${id}/logs`).then(r => r.json()),
  wheelSave: scores => fetch('/api/psy/wheel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scores }) }).then(r => r.json()),
  workAdd: note => fetch('/api/psy/worklog', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note }) }),
  workDel: id => fetch('/api/psy/worklog/' + id, { method: 'DELETE' }),
};

const pesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const KINDP = { schedule: ['расписание', 'ok'], technique: ['техника', 'p2'], checklist: ['чеклист', 'p1'] };
const PSY_CATS = ['обучение', 'мотивация', 'убеждения', 'опыт', 'сценарии', 'разное'];
const psyCatOf = p => PSY_CATS.includes(p.category) ? p.category : 'разное';
const DAYSL = { daily: 'каждый день', workdays: 'раб. дни' };
const PSY_WD = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
const daysLabel = d => !d ? 'без расписания' : (DAYSL[d] ?? d.split(',').map(x => PSY_WD[+x - 1]).join('/'));

window.loadPsy = async function () {
  psyData = await psyApi.get();
  renderPsy();
  window.pbSyncAllReminders?.();   // практики могли измениться — пересобрать пуши
};

function radarSvg(wheelData) {
  const { areas, latest, prev } = wheelData;
  const n = areas.length || 8;
  const W = 560, H = 460, cx = W / 2, cy = H / 2, R = 150;
  const pt = (i, val) => {
    const a = -Math.PI / 2 + i * 2 * Math.PI / n;
    const r = R * val / 10;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const ring = v => areas.map((_, i) => pt(i, v).map(x => x.toFixed(1)).join(',')).join(' ');
  const poly = scores => areas.map((a, i) => pt(i, scores?.[a.id] ?? 0).map(x => x.toFixed(1)).join(',')).join(' ');
  // подписи: выравнивание по стороне, чтобы длинные названия не резались
  const labels = areas.map((a, i) => {
    const ang = -Math.PI / 2 + i * 2 * Math.PI / n;
    const lx = cx + (R + 16) * Math.cos(ang);
    const ly = cy + (R + 16) * Math.sin(ang);
    const c = Math.cos(ang), s = Math.sin(ang);
    const anchor = c > 0.35 ? 'start' : c < -0.35 ? 'end' : 'middle';
    const dy = s > 0.35 ? 12 : s < -0.35 ? -4 : 4;
    const score = latest?.scores?.[a.id];
    return `<text x="${lx.toFixed(0)}" y="${(ly + dy).toFixed(0)}" text-anchor="${anchor}">${pesc(a.name)}${score ? ' · ' + score : ''}</text>`;
  }).join('');
  return `<svg width="100%" viewBox="0 0 ${W} ${H}" style="max-width:${W}px">
    <g stroke="#dde2e8" fill="none">
      ${[10, 6.6, 3.3].map(v => `<polygon points="${ring(v)}"/>`).join('')}
      ${areas.map((_, i) => { const [x, y] = pt(i, 10); return `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}"/>`; }).join('')}
    </g>
    ${prev ? `<polygon points="${poly(prev.scores)}" fill="none" stroke="#9aa7b3" stroke-width="1.5" stroke-dasharray="4 4"/>` : ''}
    ${latest ? `<polygon points="${poly(latest.scores)}" fill="rgba(30,158,87,.15)" stroke="#1e9e57" stroke-width="2"/>` : ''}
    ${labels}
  </svg>`;
}

function practiceCard(p) {
  const [kl, kc] = KINDP[p.kind] ?? [p.kind, ''];
  return `
  <div class="card">
    <div class="task" style="border-bottom:1px solid var(--line)">
      <span class="pill ${kc}">${kl}</span>
      <span class="t ed" data-psren="${p.id}" style="font-weight:600">${pesc(p.name)}</span>
      ${p.today && !p.done ? '<span class="pill p1">сегодня</span>' : ''}
      ${p.done ? '<span class="pill ok">✓ сегодня</span>' : ''}
      <span class="rowbtn" data-psarch="${p.id}" title="в архив (история сохранится)">📦</span>
      <span class="rowbtn del" data-psdel="${p.id}">✕</span>
    </div>
    <div class="kv">Расписание <b class="ed" data-psdays="${p.id}">${daysLabel(p.days)}${p.time ? ' · ' + p.time : ''}</b></div>
    <div class="kv">Категория <select class="pscatsel" data-pscat="${p.id}">${PSY_CATS.map(c => `<option${psyCatOf(p) === c ? ' selected' : ''}>${c}</option>`).join('')}</select></div>
    <div class="kv">Выполнений <b>${p.runs}${p.streak ? ' · 🔥 ' + p.streak : ''}</b></div>
    ${p.note ? `<div class="meta" style="margin:4px 0">${pesc(p.note)}</div>` : ''}
    <div class="btnrow" style="margin-top:6px">
      ${p.kind === 'schedule'
        ? `<span class="pill btn ok" data-psdo="${p.id}">✓ выполнено (с заметкой)</span>`
        : `<span class="pill btn ok" data-psrun="${p.id}">▶ пройти ${p.kind === 'technique' ? 'технику' : 'чеклист'}</span>`}
      <span class="pill btn" data-pslogs="${p.id}">журнал</span>
      ${p.kind === 'technique' ? `<span class="pill btn ${p.continuous ? 'ok' : ''}" data-psdiary="${p.id}:${p.continuous ? 1 : 0}" title="дневник — продолжать последнюю запись; иначе каждый раз чисто">📔 ${p.continuous ? 'дневник' : 'сделать дневником'}</span>` : ''}
    </div>
    ${psyOpenLogs?.id === p.id ? `<div style="margin-top:8px">
      ${p.kind === 'technique'
        ? (psyOpenLogs.rows.length
            ? `<div class="task" style="padding:0 0 6px"><span class="meta">журнал · ${psyOpenLogs.rows.length} зап.</span>
                 <span class="pill btn" data-psexpand="${p.id}" style="margin-left:auto" title="открыть на весь экран">⛶ развернуть</span></div>
               ${journalTable(p, psyOpenLogs.rows)}`
            : '<div class="empty">журнал пуст — пройди технику, каждый случай ляжет сюда строкой таблицы</div>')
        : (psyOpenLogs.rows.map(l => `<div class="ritem"><div class="rt">${l.date}${l.note ? ' — ' + pesc(l.note) : ''}</div>
            ${l.answers.length ? `<div class="rm">${l.answers.map((a, i) => a ? `${i + 1}. ${pesc(a)}` : '').filter(Boolean).join('<br>')}</div>` : ''}</div>`).join('')
            || '<div class="empty">журнал пуст</div>')}
    </div>` : ''}
  </div>`;
}

// Журнал техники таблицей: строка — случай (дата), колонки — шаги. Наглядно для пересмотра.
// Колонки берём по числу ответов (и по шагам, если они заданы) — журнал виден даже без steps.
function journalTable(p, rows, big = false) {
  if (!rows.length) return '<div class="empty">журнал пуст</div>';
  const steps = Array.isArray(p.steps) ? p.steps : [];
  const ncol = Math.max(steps.length, ...rows.map(l => (Array.isArray(l.answers) ? l.answers.length : 0)));
  if (!ncol) return '<div class="empty">в записях нет ответов</div>';
  // объёмные дневники (много шагов) — вертикально: вопрос → ответ, а не узкой таблицей
  if (ncol > 6) {
    return rows.map(l => `<div class="jvent">
      <div class="jvdate">${l.date}${l.note ? ' · ' + pesc(l.note) : ''}</div>
      ${Array.from({ length: ncol }, (_, i) => (l.answers?.[i] ?? '').toString().trim()
        ? `<div class="jvq">${pesc(steps[i] ?? ('Шаг ' + (i + 1)))}</div><div class="jva">${pesc(l.answers[i]).replace(/\n/g, '<br>')}</div>` : '').join('')}
    </div>`).join('');
  }
  const heads = Array.from({ length: ncol }, (_, i) => `<th>${pesc(steps[i] ?? ('Шаг ' + (i + 1)))}</th>`).join('');
  const body = rows.map(l => {
    const cells = Array.from({ length: ncol }, (_, i) => `<td>${pesc(l.answers?.[i] ?? '') || '—'}</td>`).join('');
    return `<tr><td class="jdate">${l.date}${l.note ? `<div class="jnote">${pesc(l.note)}</div>` : ''}</td>${cells}</tr>`;
  }).join('');
  return `<div class="jrnl-wrap${big ? ' big' : ''}"><table class="jrnl">
    <thead><tr><th>Дата</th>${heads}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// Открыть журнал на весь экран — удобно пересматривать большую таблицу.
function openJournalModal(p, rows) {
  document.querySelectorAll('.jov').forEach(o => o.remove());   // не стопать оверлеи
  const ov = document.createElement('div');
  ov.className = 'jov';
  ov.innerHTML = `<div class="jbox">
    <div class="jhead"><b>${pesc(p.name)} · журнал (${rows.length})</b>
      <span class="pill btn" data-jclose>✕ закрыть</span></div>
    ${journalTable(p, rows, true)}</div>`;
  document.body.appendChild(ov);
  const close = () => { ov.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = e => { if (e.key === 'Escape') close(); };
  ov.addEventListener('click', e => { if (e.target === ov || e.target.closest('[data-jclose]')) close(); });
  document.addEventListener('keydown', onKey);
}

function runPanel(p) {
  const last = Array.isArray(p._last) ? p._last : [];
  const editing = last.some(a => a);   // есть сегодняшняя запись → правим её, иначе пишем новую за сегодня
  const longForm = p.kind === 'technique' && p.steps.length > 6;   // объёмные дневники — крупные поля
  return `
  <div class="card runcard${longForm ? ' runlong' : ''}" style="border-color:var(--green-dim)">
    <div class="meta">${p.kind === 'technique' ? 'ТЕХНИКА · отвечай по шагам' + (editing ? ' · правишь текущую запись' : ' · новая запись') : 'ЧЕКЛИСТ · пройди перед действием'} — ${pesc(p.name)}</div>
    ${p.steps.map((s, i) => p.kind === 'technique'
      ? `<div class="psrow"><label class="pslbl">${i + 1}. ${pesc(s)}</label>
          <textarea class="psans" data-i="${i}" rows="${longForm ? 4 : 2}" placeholder="ответ…">${pesc(last[i] ?? '')}</textarea></div>`
      : `<div class="task"><span class="cb pschk" data-i="${i}"></span><span class="t">${pesc(s)}</span></div>`).join('')}
    <div class="btnrow" style="margin-top:8px">
      <span class="pill btn ok" id="psRunSave">завершить и записать в журнал</span>
      <span class="pill btn" id="psRunCancel">отмена</span>
    </div>
  </div>`;
}

let psyRun = null;   // практика, которую проходим

function renderPsy() {
  const d = psyData;
  const el = document.getElementById('screen-psy');
  if (d.hasPass && !psyUnlocked) {
    el.innerHTML = `
    <h2 style="margin-bottom:10px">🔒 Психология</h2>
    <div class="muted" style="margin-bottom:10px">Раздел под паролем (UI-замок прототипа; в нативной версии зона будет зашифрована).</div>
    <div class="task finadd" style="max-width:380px">
      <input id="psPwIn" type="password" placeholder="пароль раздела" style="flex:1">
      <span class="pill btn ok" id="psPwGo">открыть</span>
    </div>`;
    const go = async () => {
      const r = await psyApi.unlock(document.getElementById('psPwIn').value);
      if (r.error) { alert(r.error); return; }
      psyUnlocked = true;
      renderPsy();
    };
    document.getElementById('psPwGo').addEventListener('click', go);
    document.getElementById('psPwIn').addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    document.getElementById('psPwIn').focus();
    return;
  }

  const tabs = [['practices', 'Практики'], ['wheel', 'Колесо'], ['work', 'Рабочий лог'], ['decisions', 'Принятые']];
  let bodyHtml = '';
  if (psyTab === 'practices') {
    const activeP = d.practices.filter(p => !p.archived), archP = d.practices.filter(p => p.archived);
    const today = activeP.filter(p => p.today && !p.done);
    bodyHtml = `
    ${psyRun ? runPanel(psyRun) : ''}
    ${today.length ? `<div class="sec" style="margin-top:0">Сегодня по расписанию</div>
      <div class="card">${today.map(p => `<div class="task">
        <span class="cb" data-psdo="${p.id}"></span>
        ${p.time ? `<span class="meta num">${p.time}</span>` : ''}
        <span class="t">${pesc(p.name)}</span>
        ${p.streak ? `<span class="meta">🔥 ${p.streak}</span>` : ''}</div>`).join('')}</div>` : ''}
    <div class="sec">Все практики · по категориям · ＋ создать внизу</div>
    ${PSY_CATS.map(cat => {
      const list = activeP.filter(p => psyCatOf(p) === cat);
      if (!list.length) return '';
      return `<div class="psgrp">${cat}</div>
        <div class="fingrid" style="grid-template-columns:1fr 1fr">${list.map(practiceCard).join('')}</div>`;
    }).join('')}
    ${archP.length ? `<div class="sec">📦 Архив · ${archP.length} · не считаются, история сохранена</div>
      <div class="card">${archP.map(p => `<div class="task">
        <span class="t">${pesc(p.name)}</span><span class="meta">${daysLabel(p.days)}</span>
        <span class="pill btn ok" data-psunarch="${p.id}">♻ вернуть</span>
        <span class="rowbtn del" data-psdel="${p.id}">✕</span></div>`).join('')}</div>` : ''}
    <div class="card"><div class="task finadd">
      <select id="psKind"><option value="schedule">расписание</option><option value="technique">техника</option><option value="checklist">чеклист</option></select>
      <input id="psName" placeholder="название практики">
      <input id="psDays" placeholder="дни: 2,4 / workdays / daily" style="width:170px">
      <input id="psTime" placeholder="чч:мм" style="width:80px">
      <span class="pill btn ok" id="psAdd">＋</span>
    </div>
    <div class="empty">Для техники/чеклиста шаги добавишь после создания — кнопкой «шаги» в карточке (клик по названию — переименовать).</div></div>`;
  } else if (psyTab === 'wheel') {
    const w = d.wheel;
    bodyHtml = `
    <div class="fingrid" style="grid-template-columns:1fr 1fr">
      <div class="card" style="display:flex;justify-content:center">${radarSvg(w)}</div>
      <div class="card">
        <div class="meta">НОВЫЙ ЗАМЕР (1–10) · сохранится на сегодня${w.latest ? ` · прошлый: ${w.latest.date}` : ''}</div>
        ${w.areas.map(a => {
          const cur = w.latest?.scores?.[a.id] ?? 5;
          const prev = w.prev?.scores?.[a.id];
          const delta = prev != null && w.latest ? (w.latest.scores[a.id] ?? 0) - prev : null;
          return `<div class="kv"><span>${pesc(a.name)}${delta ? ` <b class="${delta > 0 ? 'up' : 'down'}">${delta > 0 ? '▲' : '▼'}${Math.abs(delta)}</b>` : ''}</span>
            <input type="number" min="1" max="10" value="${cur}" class="pswheel" data-area="${a.id}"
              style="width:56px;border:1px solid var(--line);border-radius:7px;padding:4px 6px;text-align:right"></div>`;
        }).join('')}
        <div class="btnrow" style="margin-top:8px"><span class="pill btn ok" id="psWheelSave">сохранить замер</span></div>
        <div class="meta" style="margin-top:6px">Пунктир на радаре — предыдущий замер. История: ${w.dates.join(' · ') || 'пока нет'}</div>
      </div>
    </div>
    <div class="sec">Движение по секторам · все ячейки правятся кликом <span class="pill btn" id="psAreaAdd" style="float:right" title="новый сектор Колеса = новая сфера">➕ сектор</span></div>
    ${w.areas.map((a, ai, arr) => {
      const cur = w.latest?.scores?.[a.id] ?? null;
      const next = cur != null ? Math.min(10, cur + 1) : '+1';
      const move = `<span style="float:right;font-weight:400;display:inline-flex;gap:9px;align-items:center">${ai > 0 ? `<span data-aremove="${a.id}:${arr[ai - 1].id}:before" title="выше" style="cursor:pointer;color:var(--muted)">↑</span>` : ''}${ai < arr.length - 1 ? `<span data-aremove="${a.id}:${arr[ai + 1].id}:after" title="ниже" style="cursor:pointer;color:var(--muted)">↓</span>` : ''}<span data-aredel="${a.id}" title="удалить сектор" style="cursor:pointer;color:var(--muted)">🗑</span></span>`;
      if (window.matchMedia('(max-width: 768px)').matches) return `
      <div class="card secmob">
        <div class="secmob-h"><span class="ed" data-aredit="${a.id}:name">${pesc(a.name)}</span> <b class="num">${cur ?? '—'}${cur != null ? ' → ' + next : ''}</b>${move}</div>
        <div class="secmob-r"><span class="meta">сейчас (${cur ?? '?'})</span><div class="ed" data-aredit="${a.id}:current_desc">${pesc(a.current_desc) || '＋ опиши текущее состояние'}</div></div>
        <div class="secmob-r"><span class="meta">идеал (10)</span><div class="ed" data-aredit="${a.id}:ideal">${pesc(a.ideal) || '—'}</div></div>
        <div class="secmob-r"><span class="meta">+1 — что хотим</span><div class="ed" data-aredit="${a.id}:next_desc">${pesc(a.next_desc) || '—'}</div></div>
        <div class="secmob-r"><span class="meta">шаг к +1</span><div class="ed" data-aredit="${a.id}:step" style="${a.step ? 'color:var(--green);font-weight:600' : ''}">${pesc(a.step) || '＋ задать шаг'}</div></div>
      </div>`;
      return `
      <div class="card">
        <table class="fintable" style="table-layout:fixed">
          <tr>
            <th style="width:120px"><span class="ed" data-aredit="${a.id}:name">${pesc(a.name)}</span> · уровень ${move}</th>
            <th>${cur ?? '?'} — сейчас: что есть</th>
            <th>10 — идеал</th>
            <th>${next} — +1: что хотим</th>
            <th>Шаг к +1</th>
          </tr>
          <tr>
            <td class="num" style="font-size:18px;font-weight:700">${cur ?? '—'}${cur != null ? ' → ' + next : ''}</td>
            <td class="ed" data-aredit="${a.id}:current_desc">${pesc(a.current_desc) || '＋ опиши текущее состояние'}</td>
            <td class="ed" data-aredit="${a.id}:ideal">${pesc(a.ideal) || '—'}</td>
            <td class="ed" data-aredit="${a.id}:next_desc">${pesc(a.next_desc) || '—'}</td>
            <td><span class="ed" data-aredit="${a.id}:step" style="${a.step ? 'color:var(--green);font-weight:600' : ''}">${pesc(a.step) || '＋ задать шаг'}</span></td>
          </tr>
        </table>
      </div>`;
    }).join('')}
    <div class="footer-hint">Логика движения: оценил текущий уровень → описал, как выглядит «10» → как выглядит следующая ступень (+1) → один конкретный шаг к ней. Шаг сделан — обнови замер и поставь следующий.</div>`;
  } else if (psyTab === 'work') {
    bodyHtml = `
    <div class="card"><div class="task finadd">
      <input id="psWork" placeholder="что сделал по работе — короткой строкой (Enter)">
      <span class="pill btn ok" id="psWorkAdd">＋</span>
    </div></div>
    <div class="card">${d.worklog.map(w => `
      <div class="task"><span class="meta num">${w.date.slice(5)}</span><span class="t">${pesc(w.note)}</span>
      <span class="rowbtn del" data-pswdel="${w.id}">✕</span></div>`).join('')
      || '<div class="empty">пусто — фиксируй сделанное, пригодится на ревью</div>'}</div>`;
  } else {
    bodyHtml = `
    <div class="card">${d.decisions.map(x => `
      <div class="ritem" data-psnode="${x.id}">
        <div class="rt">◆ ${pesc(x.title)}</div>
        <div class="rm">${x.updated_at.slice(0, 10)}${x.answer ? ' — ' + pesc(x.answer) : ' (без формулировки)'}</div>
      </div>`).join('') || '<div class="empty">принятых решений пока нет — принимай их в Целях, формулировка сохранится здесь</div>'}
    <div class="empty">Это журнал твоих решений из Целей: что решил и когда. Кликни — откроется запись.</div></div>`;
  }

  el.innerHTML = `
  <h2 style="margin-bottom:2px">Психология</h2>
  <div class="muted" style="margin-bottom:12px">практики · колесо развития · рабочий лог · принятые решения
    <span class="pill btn" id="psPassBtn" style="margin-left:8px">${d.hasPass ? '🔒 сменить/убрать пароль' : '🔒 задать пароль раздела'}</span></div>
  <div class="viewtabs">${tabs.map(([k, l]) => `<span class="pill btn ${psyTab === k ? 'ok' : ''}" data-pstab="${k}">${l}</span>`).join('')}</div>
  ${bodyHtml}`;
  bindPsy();
}

function bindPsy() {
  const $ = id => document.getElementById(id);
  document.querySelectorAll('#screen-psy [data-pstab]').forEach(el =>
    el.addEventListener('click', () => { psyTab = el.dataset.pstab; psyOpenLogs = null; psyRun = null; renderPsy(); }));
  document.querySelectorAll('#screen-psy [data-psnode]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.psnode)));
  document.querySelectorAll('#screen-psy [data-psdo]').forEach(el =>
    el.addEventListener('click', async () => {
      const note = prompt('Заметка к выполнению (опционально):') ?? '';
      await psyApi.pLog(+el.dataset.psdo, { note });
      window.loadPsy();
    }));
  document.querySelectorAll('#screen-psy [data-psrun]').forEach(el =>
    el.addEventListener('click', async () => {
      const p = psyData.practices.find(x => x.id === +el.dataset.psrun);
      // ТОЛЬКО дневник (флаг continuous) продолжает текущую (последнюю) запись и правит её;
      // все остальные практики — всегда чистые поля, ничего не подтягиваем (новый прогон)
      p._last = []; p._editDate = null;
      if (p?.kind === 'technique' && p.continuous) {
        try {
          const logs = await psyApi.pLogs(p.id);
          const src = (logs || [])[0] || null;
          p._last = src && Array.isArray(src.answers) ? src.answers : [];
          p._editDate = src ? String(src.date).slice(0, 10) : null;
        } catch { p._last = []; p._editDate = null; }
      }
      psyRun = p;
      renderPsy();
      document.querySelector('.psans')?.focus();
    }));
  document.querySelectorAll('#screen-psy [data-psdiary]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.psdiary.split(':');
      await psyApi.pPatch(+id, { continuous: cur === '1' ? 0 : 1 });   // переключить «дневник»
      window.loadPsy();
    }));
  document.querySelectorAll('#screen-psy [data-pslogs]').forEach(el =>
    el.addEventListener('click', async () => {
      const id = +el.dataset.pslogs;
      psyOpenLogs = psyOpenLogs?.id === id ? null : { id, rows: await psyApi.pLogs(id) };
      renderPsy();
    }));
  document.querySelectorAll('#screen-psy [data-psexpand]').forEach(el =>
    el.addEventListener('click', () => {
      const p = psyData.practices.find(x => x.id === +el.dataset.psexpand);
      if (p && psyOpenLogs?.id === p.id) openJournalModal(p, psyOpenLogs.rows);
    }));
  document.querySelectorAll('#screen-psy [data-psren]').forEach(el =>
    el.addEventListener('click', async () => {
      const p = psyData.practices.find(x => x.id === +el.dataset.psren);
      const v = prompt('Название (или: название | шаг1 ; шаг2 ; шаг3 — чтобы задать шаги):', p.name);
      if (v == null) return;
      const [name, stepsRaw] = v.split('|');
      const b = { name: (name ?? '').trim() || p.name };
      if (stepsRaw != null) b.steps = stepsRaw.split(';').map(s => s.trim()).filter(Boolean);
      await psyApi.pPatch(p.id, b);
      window.loadPsy();
    }));
  document.querySelectorAll('#screen-psy [data-psdays]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Дни: 2,4 (вт/чт) · workdays · daily · пусто — без расписания. Время через @: 2,4@19:00');
      if (v == null) return;
      const [days, time] = v.split('@').map(s => s.trim());
      await psyApi.pPatch(+el.dataset.psdays, { days: days ?? '', time: time || null });
      window.loadPsy();
    }));
  document.querySelectorAll('#screen-psy [data-pscat]').forEach(el =>
    el.addEventListener('change', async () => {
      await psyApi.pPatch(+el.dataset.pscat, { category: el.value });
      window.loadPsy();
    }));
  document.querySelectorAll('#screen-psy [data-psdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить практику с журналом?')) { await psyApi.pDel(+el.dataset.psdel); window.loadPsy(); }
    }));
  document.querySelectorAll('#screen-psy [data-psarch]').forEach(el =>
    el.addEventListener('click', async () => { await psyApi.pPatch(+el.dataset.psarch, { archived: 1 }); window.loadPsy(); }));
  document.querySelectorAll('#screen-psy [data-psunarch]').forEach(el =>
    el.addEventListener('click', async () => { await psyApi.pPatch(+el.dataset.psunarch, { archived: 0 }); window.loadPsy(); }));
  document.querySelectorAll('#screen-psy [data-pswdel]').forEach(el =>
    el.addEventListener('click', async () => { await psyApi.workDel(+el.dataset.pswdel); window.loadPsy(); }));

  $('psAdd')?.addEventListener('click', async () => {
    const name = $('psName').value.trim();
    if (!name) return;
    await psyApi.pAdd({ name, kind: $('psKind').value, days: $('psDays').value.trim(),
      time: /^([01]?\d|2[0-3]):[0-5]\d$/.test($('psTime').value.trim()) ? $('psTime').value.trim().padStart(5, '0') : null });
    window.loadPsy();
  });
  $('psRunSave')?.addEventListener('click', async () => {
    let answers = [], note = '';
    if (psyRun.kind === 'technique')
      answers = [...document.querySelectorAll('.psans')].map(i => i.value.trim());
    else {
      const checked = [...document.querySelectorAll('.pschk')].filter(c => c.classList.contains('done')).length;
      note = `пройдено ${checked}/${psyRun.steps.length}`;
    }
    await psyApi.pLog(psyRun.id, psyRun._editDate ? { answers, note, date: psyRun._editDate } : { answers, note });
    psyRun = null;
    window.loadPsy();
  });
  $('psRunCancel')?.addEventListener('click', () => { psyRun = null; renderPsy(); });
  document.querySelectorAll('.pschk').forEach(el =>
    el.addEventListener('click', () => el.classList.toggle('done')));
  document.querySelectorAll('#screen-psy [data-aredit]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, field] = el.dataset.aredit.split(':');
      const label = { name: 'Название сектора (обновится и в Сферах):', current_desc: 'Что есть сейчас — почему такая оценка?', ideal: 'Как выглядит «10» в этом секторе?', next_desc: 'Что хотим сделать для +1 (следующий уровень)?', step: 'Конкретный шаг к +1:' }[field];
      const v = prompt(label, el.textContent.trim().replace('＋ задать шаг', '').replace('＋ опиши текущее состояние', '').replace('—', ''));
      if (v == null) return;
      await fetch('/api/psy/areas/' + id, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [field]: v.trim() }) });
      window.SPH_AREAS = [];                 // любое изменение сектора подтянется в Сферы/выпадашки
      window.ensureSphAreas?.(true);
      window.loadPsy();
    }));
  $('psAreaAdd')?.addEventListener('click', async () => {
    const name = prompt('Название нового сектора Колеса (станет новой сферой):');
    if (name == null || !name.trim()) return;
    await fetch('/api/psy/areas', { method: 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name.trim() }) });
    window.SPH_AREAS = [];                 // список сфер изменился — пересоберём при следующем заходе
    window.ensureSphAreas?.(true);
    window.loadPsy();
  });
  document.querySelectorAll('#screen-psy [data-aredel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (!confirm('Удалить сектор? Его замеры Колеса удалятся, а привязки целей/инфо к этой сфере просто сбросятся.')) return;
      await fetch('/api/psy/areas/' + el.dataset.aredel, { method: 'DELETE' });
      window.SPH_AREAS = [];
      window.ensureSphAreas?.(true);
      window.loadPsy();
    }));
  // ↑/↓ — порядок секторов Колеса (он же порядок сфер)
  document.querySelectorAll('#screen-psy [data-aremove]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, ref, where] = el.dataset.aremove.split(':');
      await fetch(`/api/psy/areas/${id}/reorder`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ref: +ref, where }) });
      window.SPH_AREAS = [];
      window.ensureSphAreas?.(true);
      window.loadPsy();
    }));
  $('psWheelSave')?.addEventListener('click', async () => {
    const scores = {};
    document.querySelectorAll('.pswheel').forEach(i => scores[i.dataset.area] = +i.value);
    await psyApi.wheelSave(scores);
    window.loadPsy();
  });
  const workAdd = async () => {
    const v = $('psWork').value.trim();
    if (!v) return;
    await psyApi.workAdd(v);
    window.loadPsy();
  };
  $('psWorkAdd')?.addEventListener('click', workAdd);
  $('psWork')?.addEventListener('keydown', e => { if (e.key === 'Enter') workAdd(); });
  $('psPassBtn')?.addEventListener('click', async () => {
    const old = psyData.hasPass ? prompt('Текущий пароль:') : null;
    if (psyData.hasPass && old == null) return;
    const pw = prompt('Новый пароль (пусто — убрать замок):');
    if (pw == null) return;
    const r = await psyApi.setPass({ old, password: pw.trim() });
    if (r.error) { alert(r.error); return; }
    psyUnlocked = true;
    window.loadPsy();
  });
}

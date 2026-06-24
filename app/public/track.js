/* Трекинг: чек-ин дня · свои метрики · тепловая карта рутин. Без фанатизма: пропуски — норма. */
let trData = null;

const trApi = {
  get: () => fetch('/api/track').then(r => r.json()),
  checkin: (mood, note) => fetch('/api/track/checkin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mood, note }) }),
  mAdd: b => fetch('/api/track/metrics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  mDel: id => fetch('/api/track/metrics/' + id, { method: 'DELETE' }),
  mRen: (id, b) => fetch('/api/track/metrics/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  mVal: (id, value, date) => fetch(`/api/track/metrics/${id}/value`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value, date }) }),
  mLogs: id => fetch(`/api/track/metrics/${id}/logs`).then(r => r.json()),
  mDelVal: (id, date) => fetch(`/api/track/metrics/${id}/value`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ op: 'del', date }) }).then(r => r.json()),
  mClear: id => fetch(`/api/track/metrics/${id}/value`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ op: 'clear' }) }).then(r => r.json()),
};

const tresc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MOOD = ['', '😞', '😐', '🙂'];

window.loadTrack = async function () {
  trData = await trApi.get();
  renderTrack();
};

// просмотр и чистка записей метрики (дата + значение) — модалка
async function trShowLogs(id, name) {
  let logs = [];
  try { logs = await trApi.mLogs(id); } catch {}
  const rows = (logs || []).map(l => `<div class="task" style="padding:5px 0">
    <span class="t">${tresc(l.date)}</span>
    <span class="meta num" style="flex:0 0 auto">${l.value}</span>
    <span class="rowbtn del" data-trdval="${id}:${tresc(l.date)}" title="удалить запись">✕</span></div>`).join('') || '<div class="empty">записей нет</div>';
  document.getElementById('trLogsOv')?.remove();
  const ov = document.createElement('div');
  ov.id = 'trLogsOv';
  ov.style.cssText = 'position:fixed;inset:0;background:rgba(18,28,45,.5);z-index:95;display:flex;align-items:center;justify-content:center;padding:24px';
  ov.innerHTML = `<div style="background:var(--panel);border-radius:14px;max-width:440px;width:100%;max-height:82vh;overflow:auto;padding:16px;box-shadow:var(--shadow-md)" onclick="event.stopPropagation()">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
      <b style="flex:1;font-size:14px">${tresc(name)} · ${(logs || []).length} зап.</b>
      ${(logs || []).length ? '<span class="pill btn danger" id="trClearAll">очистить все</span>' : ''}
      <span class="pill btn" id="trLogsClose">✕ закрыть</span></div>
    ${rows}</div>`;
  document.body.appendChild(ov);
  ov.addEventListener('click', () => ov.remove());
  document.getElementById('trLogsClose').onclick = () => ov.remove();
  const clr = document.getElementById('trClearAll');
  if (clr) clr.onclick = async () => { if (confirm('Удалить ВСЕ записи этой метрики?')) { await trApi.mClear(id); ov.remove(); window.loadTrack(); } };
  ov.querySelectorAll('[data-trdval]').forEach(el => el.onclick = async () => {
    const i = el.dataset.trdval.indexOf(':'), mid = el.dataset.trdval.slice(0, i), date = el.dataset.trdval.slice(i + 1);
    await trApi.mDelVal(+mid, date); window.loadTrack(); trShowLogs(id, name);
  });
}

function sparkBars(history, type) {
  if (!history.length) return '<span class="meta">нет данных</span>';
  const max = Math.max(...history.map(h => h.value), 1);
  return `<span class="sparkrow">${history.map(h => {
    const hgt = type === 'bool' ? (h.value ? 100 : 15) : Math.max(10, h.value / max * 100);
    return `<i title="${h.date}: ${h.value}" style="height:${hgt}%"></i>`;
  }).join('')}</span>`;
}

function renderTrack() {
  const d = trData;
  const today = (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)(new Date());
  const todayCheckin = d.checkins.find(c => c.date === today);
  const avg7 = d.checkins.filter(c => c.date >= (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)(new Date(Date.now() - 7 * 864e5)));

  document.getElementById('screen-track').innerHTML = `
  <h2 style="margin-bottom:2px">Трекинг и отчёты</h2>
  <div class="muted" style="margin-bottom:14px">кастомный и без фанатизма: трекай только то, что сам создал; пропуски — норма</div>

  <div class="fingrid" style="grid-template-columns:1fr 2fr">
    <div class="card">
      <div class="meta">ЧЕК-ИН ДНЯ</div>
      <div class="btnrow" style="margin:8px 0">
        ${[1, 2, 3].map(m2 => `<span class="pill btn ${todayCheckin?.mood === m2 ? 'ok' : ''}" data-trmood="${m2}" style="font-size:18px">${MOOD[m2]}</span>`).join('')}
      </div>
      ${todayCheckin?.note ? `<div class="meta">${tresc(todayCheckin.note)}</div>` : ''}
      <div class="meta" style="margin-top:8px">последние 30 дней (среднее за неделю: ${avg7.length ? (avg7.reduce((s, c) => s + c.mood, 0) / avg7.length).toFixed(1) : '—'}/3)</div>
      <div style="font-size:15px;letter-spacing:2px;margin-top:4px">${
        d.checkins.slice(0, 30).reverse().map(c => `<span title="${c.date}${c.note ? ': ' + tresc(c.note) : ''}">${MOOD[c.mood]}</span>`).join('') || '<span class="meta">пока пусто</span>'}</div>
    </div>
    <div class="card" style="overflow-x:auto">
      <div class="meta">ИТОГИ ПО МЕСЯЦАМ · отметки — сколько раз, числа — среднее</div>
      ${monthTable(d.monthly)}
    </div>
  </div>

  <div class="sec">Дневник · как твоя таблица: строка — день, колонка — что отмечаешь</div>
  <div class="card" style="overflow-x:auto">
    ${diaryGrid(d)}
    <div class="task finadd" style="margin-top:8px">
      <input id="trName" placeholder="новая колонка (Подъём не в 10, Книга, Падл…)">
      <select id="trType"><option value="bool">отметка ✓</option><option value="number">число</option><option value="scale">шкала 1–10</option></select>
      <select id="trPol"><option value="plus">📈 прогресс</option><option value="minus">📉 регресс</option></select>
      <input id="trUnit" placeholder="ед. (опц.)" style="width:90px">
      <span class="pill btn ok" id="trAdd">＋ колонка</span>
    </div>
  </div>

  ${d.metrics.some(mt => mt.type !== 'bool') ? `
  <div class="sec">Динамика чисел · 14 дней</div>
  <div class="card">
    ${d.metrics.filter(mt => mt.type !== 'bool').map(mt => `
      <div class="task">
        <span class="t">${tresc(mt.name)}</span>
        <span class="pill">${mt.type === 'scale' ? '1–10' : 'число'}${mt.unit ? ' · ' + tresc(mt.unit) : ''}</span>
        ${sparkBars(mt.history, mt.type)}
        <span class="meta" data-trlogs="${mt.id}" title="показать и почистить записи" style="cursor:pointer">внёс ${mt.total} раз ›</span>
      </div>`).join('')}
  </div>` : ''}
  <div class="footer-hint">Клик по ячейке — отметка/значение за тот день (можно задним числом). Клик по заголовку — переименовать, ✕ — удалить колонку с историей.</div>
  <div id="trackReports" style="margin-top:18px"></div>`;
  bindTrack();
  window.loadReports?.();   // отчёты встроены прямо под трекингом (объединены в один раздел)
}

// итоги по месяцам: динамика одной строкой на месяц
function monthTable(monthly) {
  if (!monthly?.length) return '<div class="empty">появится с первыми отметками</div>';
  const MONL = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const label = ym => `${MONL[+ym.slice(5) - 1]} ${ym.slice(2, 4)}`;
  const cols = monthly[0].metrics;   // набор колонок одинаков для всех месяцев
  return `<table class="diary" style="margin-top:6px">
    <tr><th style="text-align:left">Месяц</th>
      ${cols.map(c => `<th class="${c.polarity === 'minus' ? 'badname' : ''}">${tresc(c.name)}${c.type !== 'bool' && c.unit ? `<br><span class="meta">${tresc(c.unit)}</span>` : ''}</th>`).join('')}
      <th>🙂 ср.</th><th>☑ задач</th><th>↻ рутин</th></tr>
    ${monthly.map((mo, i) => `<tr class="${i === 0 ? 'todayrow' : ''}">
      <td class="num">${i === 0 ? '<b>' + label(mo.ym) + '</b>' : label(mo.ym)}</td>
      ${mo.metrics.map(c => `<td class="${c.type === 'bool' && c.value ? (c.polarity === 'minus' ? 'bad' : 'on') : 'num'}">${c.value ?? ''}</td>`).join('')}
      <td class="num">${mo.mood ?? ''}</td><td class="num">${mo.tasksDone || ''}</td><td class="num">${mo.routinesDone || ''}</td>
    </tr>`).join('')}
  </table>`;
}

// сетка «дата × колонки» как в гугл-таблице: последние 14 дней, сегодня сверху
// телефон: метрики строками, последние 7 дней — ячейками (data-trcell те же — биндинги работают)
function diaryMobile(d) {
  const iso = n => (x => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`)(new Date(Date.now() - n * 864e5));
  const days = Array.from({ length: 7 }, (_, n) => iso(n));
  const val = Object.fromEntries(d.metrics.map(mt => [mt.id, Object.fromEntries(mt.history.map(h => [h.date, h.value]))]));
  return d.metrics.map(mt => {
    const bad = mt.polarity === 'minus';
    const cells = days.map((date, i) => {
      const v = val[mt.id][date];
      const dd = i === 0 ? 'сег' : String(new Date(date + 'T00:00:00').getDate());
      const inner = `<i class="md">${dd}</i><b class="mv">${mt.type === 'bool' ? (v ? (bad ? '✗' : '✓') : '·') : (v ?? '·')}</b>`;
      const cls = mt.type === 'bool' ? (v ? (bad ? 'bad' : 'on') : '') : 'num';
      return `<span class="mcell ${cls}${i === 0 ? ' today' : ''}" data-trcell="${mt.id}:${date}:${mt.type === 'bool' ? 'bool:' + (v ? 1 : 0) : 'num:' + (v ?? '')}">${inner}</span>`;
    }).join('');
    return `<div class="card mrow">
      <div class="mrow-h"><span class="ed ${bad ? 'badname' : ''}" data-trren="${mt.id}" title="переименовать">${tresc(mt.name)}</span>${mt.unit ? ` <span class="meta">${tresc(mt.unit)}</span>` : ''}
        <span class="rowbtn" data-trtgt="${mt.id}:${mt.target ?? ''}" title="цель метрики">🎯${mt.target != null ? ' ' + mt.target : ''}</span>
        <span class="rowbtn" data-trpol="${mt.id}:${mt.polarity ?? 'plus'}" title="прогресс/регресс" style="margin-left:auto">${bad ? '📉' : '📈'}</span>
        <span class="rowbtn del" data-trdel="${mt.id}">✕</span></div>
      <div class="mcells">${cells}</div>
    </div>`;
  }).join('');
}

function diaryGrid(d) {
  if (!d.metrics.length) return '<div class="empty">добавь первую колонку — и отмечай день кликом</div>';
  if (window.matchMedia('(max-width: 768px)').matches) return diaryMobile(d);
  const iso = n => (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)(new Date(Date.now() - n * 864e5));
  const WDS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
  const days = Array.from({ length: 14 }, (_, n) => iso(n));
  const val = Object.fromEntries(d.metrics.map(mt => [mt.id, Object.fromEntries(mt.history.map(h => [h.date, h.value]))]));
  const cell = (mt, date) => {
    const v = val[mt.id][date];
    const bad = mt.polarity === 'minus';
    if (mt.type === 'bool')
      return `<td class="cell ${v ? (bad ? 'bad' : 'on') : ''}" data-trcell="${mt.id}:${date}:bool:${v ? 1 : 0}">${v ? (bad ? '✗' : '✓') : ''}</td>`;
    return `<td class="cell num" data-trcell="${mt.id}:${date}:num:${v ?? ''}">${v ?? ''}</td>`;
  };
  return `<table class="diary">
    <tr><th style="text-align:left">Дата</th>${d.metrics.map(mt => `
      <th draggable="true" data-mcol="${mt.id}" title="тащи — поменять порядок · регресс/прогресс переключается в карточке колонки"><span class="ed ${mt.polarity === 'minus' ? 'badname' : ''}" data-trren="${mt.id}" title="клик — переименовать">${tresc(mt.name)}</span>${mt.unit ? `<br><span class="meta">${tresc(mt.unit)}</span>` : ''}
      <span class="rowbtn" data-trpol="${mt.id}:${mt.polarity ?? 'plus'}" title="${mt.polarity === 'minus' ? 'это регресс — клик: сделать прогрессом' : 'это прогресс — клик: сделать регрессом'}">${mt.polarity === 'minus' ? '📉' : '📈'}</span>
      <span class="rowbtn" data-trtgt="${mt.id}:${mt.target ?? ''}" title="цель метрики">🎯${mt.target != null ? ' ' + mt.target : ''}</span>
      <span class="rowbtn del" data-trdel="${mt.id}">✕</span></th>`).join('')}</tr>
    ${days.map(date => {
      const dt = new Date(date + 'T00:00:00');
      return `<tr class="${date === days[0] ? 'todayrow' : ''}">
        <td class="num">${date === days[0] ? '<b>сегодня</b>' : `${String(dt.getDate()).padStart(2, '0')}.${String(dt.getMonth() + 1).padStart(2, '0')} ${WDS[dt.getDay()]}`}</td>
        ${d.metrics.map(mt => cell(mt, date)).join('')}</tr>`;
    }).join('')}
  </table>`;
}

let trColDrag = null;
function bindTrackDnd() {
  const clear = () => document.querySelectorAll('.diary th.dropbefore,.diary th.dropafter')
    .forEach(x => x.classList.remove('dropbefore', 'dropafter'));
  document.querySelectorAll('#screen-track .diary th[data-mcol]').forEach(th => {
    th.addEventListener('dragstart', () => { trColDrag = +th.dataset.mcol; });
    th.addEventListener('dragover', e => {
      if (trColDrag == null || +th.dataset.mcol === trColDrag) return;
      e.preventDefault();
      const r = th.getBoundingClientRect();
      th.classList.remove('dropbefore', 'dropafter');
      th.classList.add((e.clientX - r.left) / r.width < 0.5 ? 'dropbefore' : 'dropafter');
    });
    th.addEventListener('dragleave', () => th.classList.remove('dropbefore', 'dropafter'));
    th.addEventListener('drop', async e => {
      e.preventDefault();
      const where = th.classList.contains('dropbefore') ? 'before' : 'after';
      clear();
      if (trColDrag == null) return;
      await fetch(`/api/track/metrics/${trColDrag}/reorder`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ref_id: +th.dataset.mcol, where }) });
      trColDrag = null;
      window.loadTrack();
    });
    th.addEventListener('dragend', clear);
  });
}

function bindTrack() {
  bindTrackDnd();
  const $ = id => document.getElementById(id);
  document.querySelectorAll('#screen-track [data-trlogs]').forEach(el =>
    el.addEventListener('click', () => {
      const mt = (trData.metrics || []).find(x => x.id === +el.dataset.trlogs);
      trShowLogs(+el.dataset.trlogs, mt ? mt.name : 'метрика');
    }));
  document.querySelectorAll('#screen-track [data-trmood]').forEach(el =>
    el.addEventListener('click', async () => {
      const note = prompt('Заметка к дню (опционально):') ?? '';
      await trApi.checkin(+el.dataset.trmood, note);
      window.loadTrack();
    }));
  document.querySelectorAll('#screen-track [data-trcell]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, date, type, cur] = el.dataset.trcell.split(':');
      if (type === 'bool') {
        await trApi.mVal(+id, cur === '1' ? 0 : 1, date);
      } else {
        const v = prompt(`Значение за ${date}:`, cur);
        if (v == null || v.trim() === '' || isNaN(parseFloat(v.replace(',', '.')))) return;
        await trApi.mVal(+id, parseFloat(v.replace(',', '.')), date);
      }
      window.loadTrack();
    }));
  document.querySelectorAll('#screen-track [data-trpol]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.trpol.split(':');
      await trApi.mRen(+id, { polarity: cur === 'minus' ? 'plus' : 'minus' });
      window.loadTrack();
    }));
  document.querySelectorAll('#screen-track [data-trtgt]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.trtgt.split(':');
      const v = prompt('Цель метрики (число; пусто — убрать):', cur);
      if (v === null) return;
      const t = v.trim().replace(',', '.');
      await trApi.mRen(+id, { target: t === '' ? null : parseFloat(t) });
      window.loadTrack();
    }));
  document.querySelectorAll('#screen-track [data-trren]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Название метрики:', el.textContent.trim());
      if (v?.trim()) { await trApi.mRen(+el.dataset.trren, { name: v.trim() }); window.loadTrack(); }
    }));
  document.querySelectorAll('#screen-track [data-trdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить метрику со всей историей?')) { await trApi.mDel(+el.dataset.trdel); window.loadTrack(); }
    }));
  $('trAdd')?.addEventListener('click', async () => {
    const name = $('trName').value.trim();
    if (!name) return;
    await trApi.mAdd({ name, type: $('trType').value, unit: $('trUnit').value.trim(), polarity: $('trPol').value });
    window.loadTrack();
  });
}

/* Трекинг: чек-ин дня · свои метрики · тепловая карта рутин. Без фанатизма: пропуски — норма. */
let trData = null;

const trApi = {
  get: () => fetch('/api/track').then(r => r.json()),
  checkin: (mood, note) => fetch('/api/track/checkin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mood, note }) }),
  mAdd: b => fetch('/api/track/metrics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  mDel: id => fetch('/api/track/metrics/' + id, { method: 'DELETE' }),
  mRen: (id, b) => fetch('/api/track/metrics/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  mVal: (id, value, date) => fetch(`/api/track/metrics/${id}/value`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value, date }) }),
};

const tresc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const MOOD = ['', '😞', '😐', '🙂'];

window.loadTrack = async function () {
  trData = await trApi.get();
  renderTrack();
};

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
  const today = new Date().toISOString().slice(0, 10);
  const todayCheckin = d.checkins.find(c => c.date === today);
  const heat = d.heatmap;
  const avg7 = d.checkins.filter(c => c.date >= new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10));

  document.getElementById('screen-track').innerHTML = `
  <h2 style="margin-bottom:2px">Трекинг</h2>
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
    <div class="card">
      <div class="meta">РУТИНЫ · ТЕПЛОВАЯ КАРТА 16 НЕДЕЛЬ (выполнено из ${heat[heat.length - 1]?.total ?? 0})</div>
      <div class="hm" style="margin-top:8px">${heat.map(h => {
        const ratio = h.total ? h.done / h.total : 0;
        const cls = !h.done ? '' : ratio < 0.4 ? 'l1' : ratio < 0.8 ? 'l2' : 'l3';
        return `<i class="${cls}" title="${h.date}: ${h.done}/${h.total}"></i>`;
      }).join('')}</div>
    </div>
  </div>

  <div class="sec">Дневник · как твоя таблица: строка — день, колонка — что отмечаешь</div>
  <div class="card" style="overflow-x:auto">
    ${diaryGrid(d)}
    <div class="task finadd" style="margin-top:8px">
      <input id="trName" placeholder="новая колонка (Подъём не в 10, Книга, Падл…)">
      <select id="trType"><option value="bool">отметка ✓</option><option value="number">число</option><option value="scale">шкала 1–10</option></select>
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
        <span class="meta">${mt.total} зап.</span>
      </div>`).join('')}
  </div>` : ''}
  <div class="footer-hint">Клик по ячейке — отметка/значение за тот день (можно задним числом). Клик по заголовку — переименовать, ✕ — удалить колонку с историей.</div>`;
  bindTrack();
}

// сетка «дата × колонки» как в гугл-таблице: последние 14 дней, сегодня сверху
function diaryGrid(d) {
  if (!d.metrics.length) return '<div class="empty">добавь первую колонку — и отмечай день кликом</div>';
  const iso = n => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);
  const WDS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
  const days = Array.from({ length: 14 }, (_, n) => iso(n));
  const val = Object.fromEntries(d.metrics.map(mt => [mt.id, Object.fromEntries(mt.history.map(h => [h.date, h.value]))]));
  const cell = (mt, date) => {
    const v = val[mt.id][date];
    if (mt.type === 'bool')
      return `<td class="cell ${v ? 'on' : ''}" data-trcell="${mt.id}:${date}:bool:${v ? 1 : 0}">${v ? '✓' : ''}</td>`;
    return `<td class="cell num" data-trcell="${mt.id}:${date}:num:${v ?? ''}">${v ?? ''}</td>`;
  };
  return `<table class="diary">
    <tr><th style="text-align:left">Дата</th>${d.metrics.map(mt => `
      <th><span class="ed" data-trren="${mt.id}" title="клик — переименовать">${tresc(mt.name)}</span>${mt.unit ? `<br><span class="meta">${tresc(mt.unit)}</span>` : ''}
      <span class="rowbtn del" data-trdel="${mt.id}">✕</span></th>`).join('')}</tr>
    ${days.map(date => {
      const dt = new Date(date + 'T00:00:00');
      return `<tr class="${date === days[0] ? 'todayrow' : ''}">
        <td class="num">${date === days[0] ? '<b>сегодня</b>' : `${String(dt.getDate()).padStart(2, '0')}.${String(dt.getMonth() + 1).padStart(2, '0')} ${WDS[dt.getDay()]}`}</td>
        ${d.metrics.map(mt => cell(mt, date)).join('')}</tr>`;
    }).join('')}
  </table>`;
}

function bindTrack() {
  const $ = id => document.getElementById(id);
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
    await trApi.mAdd({ name, type: $('trType').value, unit: $('trUnit').value.trim() });
    window.loadTrack();
  });
}

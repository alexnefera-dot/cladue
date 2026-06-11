/* Трекинг: чек-ин дня · свои метрики · тепловая карта рутин. Без фанатизма: пропуски — норма. */
let trData = null;

const trApi = {
  get: () => fetch('/api/track').then(r => r.json()),
  checkin: (mood, note) => fetch('/api/track/checkin', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mood, note }) }),
  mAdd: b => fetch('/api/track/metrics', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  mDel: id => fetch('/api/track/metrics/' + id, { method: 'DELETE' }),
  mRen: (id, b) => fetch('/api/track/metrics/' + id, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  mVal: (id, value) => fetch(`/api/track/metrics/${id}/value`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ value }) }),
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

  <div class="sec">Мои метрики · значение за сегодня правится кликом</div>
  <div class="card">
    ${d.metrics.map(mt => `
      <div class="task">
        <span class="t ed" data-trren="${mt.id}" title="клик — переименовать">${tresc(mt.name)}</span>
        <span class="pill">${{ number: 'число', bool: 'да/нет', scale: '1–10' }[mt.type]}${mt.unit ? ' · ' + tresc(mt.unit) : ''}</span>
        ${sparkBars(mt.history, mt.type)}
        ${mt.type === 'bool'
          ? `<span class="cb ${mt.today ? 'done' : ''}" data-trbool="${mt.id}:${mt.today ? 1 : 0}"></span>`
          : `<span class="ed num" data-trval="${mt.id}" title="значение за сегодня">${mt.today ?? '—'}</span>`}
        <span class="meta">${mt.total} зап.</span>
        <span class="rowbtn del" data-trdel="${mt.id}">✕</span>
      </div>`).join('') || '<div class="empty">создай первую метрику: кофе, падл-часы, страницы, вес…</div>'}
    <div class="task finadd">
      <input id="trName" placeholder="новая метрика (кофе, падл-часы, страницы…)">
      <select id="trType"><option value="number">число</option><option value="bool">да/нет</option><option value="scale">шкала 1–10</option></select>
      <input id="trUnit" placeholder="ед. (опц.)" style="width:90px">
      <span class="pill btn ok" id="trAdd">＋</span>
    </div>
  </div>
  <div class="footer-hint">Спарклайн — последние 14 дней. Корреляции по накопленному — добавим, когда будет 2–3 недели данных.</div>`;
  bindTrack();
}

function bindTrack() {
  const $ = id => document.getElementById(id);
  document.querySelectorAll('#screen-track [data-trmood]').forEach(el =>
    el.addEventListener('click', async () => {
      const note = prompt('Заметка к дню (опционально):') ?? '';
      await trApi.checkin(+el.dataset.trmood, note);
      window.loadTrack();
    }));
  document.querySelectorAll('#screen-track [data-trval]').forEach(el =>
    el.addEventListener('click', async () => {
      const v = prompt('Значение за сегодня:', el.textContent.trim().replace('—', ''));
      if (v == null || v.trim() === '' || isNaN(parseFloat(v.replace(',', '.')))) return;
      await trApi.mVal(+el.dataset.trval, parseFloat(v.replace(',', '.')));
      window.loadTrack();
    }));
  document.querySelectorAll('#screen-track [data-trbool]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.trbool.split(':');
      await trApi.mVal(+id, cur === '1' ? 0 : 1);
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

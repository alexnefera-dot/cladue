/* Отчёты — сводка по сферам, динамика оценок, итоги по метрикам.
   Только чтение; механика считается на сервере (закрытые вехи/задачи/практики/рутины).
   Использует общие хелперы из spheres.js: sesc, colOf, SPH_COL. */

let rpPeriod = 'month';

const rpApi = {
  spheres: p => fetch('/api/reports/spheres?period=' + p).then(r => r.json()),
  dynamics: m => fetch('/api/reports/dynamics?months=' + m).then(r => r.json()),
  load: () => fetch('/api/spheres').then(r => r.json()),
};

function ensureRpStyle() {
  if (document.getElementById('rp-style')) return;
  const st = document.createElement('style'); st.id = 'rp-style';
  st.textContent = `
    .rptab{width:100%;border-collapse:collapse;font-size:13px}
    .rptab th{text-align:right;font:600 11px var(--mono);color:var(--muted);padding:4px 6px;border-bottom:1px solid var(--line)}
    .rptab th:first-child{text-align:left}
    .rptab td{text-align:right;padding:5px 6px;border-top:1px solid var(--bg2)}
    .rptab td:first-child{text-align:left}
    .rplegend{display:flex;flex-wrap:wrap;gap:4px 14px;margin-top:8px;font-size:12px}
    .rplegend span.it{display:inline-flex;align-items:center;gap:5px}
    .rplegend i{width:10px;height:10px;border-radius:2px;display:inline-block}`;
  document.head.appendChild(st);
}

// multi-series линейный график: одна цветная линия на сферу (значения 0..maxY)
function lineChartSvg(labels, series, opts = {}) {
  const w = opts.w || 720, h = opts.h || 230, padL = 26, padB = 20, padT = 10, padR = 8, maxY = opts.maxY || 10;
  const n = labels.length;
  if (!n) return '<div class="muted">нет данных по оценкам — ставь оценки сфер в Психологии</div>';
  const x = i => padL + (n === 1 ? (w - padL - padR) / 2 : i * (w - padL - padR) / (n - 1));
  const y = v => padT + (1 - v / maxY) * (h - padT - padB);
  let grid = '';
  for (const gv of [0, maxY / 2, maxY]) {
    grid += `<line x1="${padL}" y1="${y(gv).toFixed(1)}" x2="${w - padR}" y2="${y(gv).toFixed(1)}" stroke="var(--line)" stroke-width="1"/>`
      + `<text x="2" y="${(y(gv) + 3).toFixed(1)}" style="font:10px var(--mono);fill:var(--muted)">${gv}</text>`;
  }
  let xlabels = '';
  labels.forEach((lb, i) => { if (n <= 8 || i % 2 === 0) xlabels += `<text x="${x(i).toFixed(1)}" y="${h - 5}" text-anchor="middle" style="font:9px var(--mono);fill:var(--muted)">${sesc(String(lb).slice(5))}</text>`; });
  let lines = '', legend = '';
  (series || []).forEach((ser, si) => {
    const col = colOf(si);
    const pts = (ser.values || []).map((v, i) => (v == null) ? null : [x(i), y(Math.max(0, Math.min(maxY, +v)))]).filter(Boolean);
    if (pts.length) lines += `<polyline fill="none" stroke="${col}" stroke-width="2" points="${pts.map(p => p.map(c => c.toFixed(1)).join(',')).join(' ')}"/>`
      + pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.4" fill="${col}"/>`).join('');
    legend += `<span class="it"><i style="background:${col}"></i>${sesc(ser.name)}</span>`;
  });
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto">${grid}${xlabels}${lines}</svg><div class="rplegend">${legend}</div>`;
}

window.loadReports = async function () {
  ensureRpStyle();
  const el = document.getElementById('screen-reports');
  if (!el) return;
  el.innerHTML = '<div class="muted" style="padding:16px">Загружаю отчёты…</div>';
  let rep, dyn, spheres;
  try { [rep, dyn, spheres] = await Promise.all([rpApi.spheres(rpPeriod), rpApi.dynamics(12), rpApi.load()]); }
  catch (e) { el.innerHTML = '<div class="muted" style="padding:16px">Не удалось загрузить отчёты.</div>'; return; }

  let h = `<div class="sec">📈 Отчёты <span class="muted" style="font-weight:400">· период:
    <span class="pill btn ${rpPeriod === 'week' ? 'ok' : ''}" data-rpp="week">неделя</span>
    <span class="pill btn ${rpPeriod === 'month' ? 'ok' : ''}" data-rpp="month">месяц</span></span></div>`;

  // 1) Сводка по всем сферам (механика за период)
  const rows = (rep.rows || []).map(r => `<tr>
    <td>${sesc(r.name)}</td><td>${r.routines}</td><td>${r.practices}</td><td>${r.milestones}</td><td>${r.tasks}</td>
    <td><b>${r.routines + r.practices + r.milestones + r.tasks}</b></td></tr>`).join('');
  h += `<div class="card"><div class="muted" style="font-size:12px;margin-bottom:6px">Закрыто за ${rpPeriod === 'week' ? 'неделю' : 'месяц'} · ${sesc(rep.from)} — ${sesc(rep.to)}</div>
    <table class="rptab"><thead><tr><th>Сфера</th><th>Рутины</th><th>Практики</th><th>Вехи</th><th>Задачи</th><th>Σ</th></tr></thead>
    <tbody>${rows || '<tr><td colspan="6" class="muted">нет данных</td></tr>'}</tbody></table></div>`;

  // 2) Динамика оценок по сферам (по месяцам)
  h += `<div class="sec">📉 Динамика оценок · ${(dyn.labels || []).length} мес</div>
    <div class="card">${lineChartSvg(dyn.labels || [], dyn.series || [], { maxY: 10 })}</div>`;

  // 3) Итоги по метрикам — текущий период (из сфер)
  let mh = '';
  (spheres || []).forEach(s => {
    const ms = s.tracking || [];
    if (!ms.length) return;
    const items = ms.map(m => {
      const cur = (m.cur == null) ? '–' : m.cur;
      const tag = ({ daily: 'день', weekly: 'нед', monthly: 'мес' })[m.cadence] || 'день';
      return `<div class="sphpool"><span class="sphpool-n">${sesc(m.name)} <span class="sphpool-st">${tag}</span>${m.computed ? ' <span class="sphpool-st">счётчик</span>' : ''}</span>
        <span class="sphpool-p">${cur}<small>${sesc(m.unit || '')}</small></span></div>`;
    }).join('');
    mh += `<div style="margin-bottom:8px"><b style="font-size:13px">${sesc(s.name)}</b>${items}</div>`;
  });
  h += `<div class="sec">📊 Метрики · текущий период</div><div class="card">${mh || '<div class="muted">метрик пока нет</div>'}</div>`;

  el.innerHTML = h;
  document.querySelectorAll('#screen-reports [data-rpp]').forEach(b => b.onclick = () => { rpPeriod = b.dataset.rpp; window.loadReports(); });
};

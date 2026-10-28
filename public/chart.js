/**
 * ГРАФИКИ ПО СБОРАМ — общий код главной панели («Статистика») и разбора выдачи (/serp).
 *
 * Отдельным файлом, а не копией в каждой странице: страниц две, график один, и разъехавшиеся
 * копии — вопрос времени. Всё внутри IIFE: у обеих страниц есть свой `esc`, и второе объявление
 * того же имени в глобальной области — это SyntaxError, который кладёт страницу целиком.
 * Стили инжектятся отсюда же, чтобы подключение было одной строкой; цвета берутся из переменных
 * страницы, которые есть в обеих.
 */
(function(){
  const style = document.createElement('style');
  style.textContent = `
  :root{ --c-door:#4338ca; --c-our:#0d9488; --c-grid:#e5e7eb; }
  @media (prefers-color-scheme: dark){ :root{ --c-door:#6366f1; --c-our:#11a899; --c-grid:#2a323d; } }
  .charts{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));margin-top:10px}
  .chart{border:1px solid var(--line);border-radius:10px;padding:10px 12px 6px;background:var(--card)}
  .chart .ct{font-size:12px;font-weight:600;margin-bottom:2px}
  .chart .cs{font-size:11px;color:var(--muted);margin-bottom:6px;min-height:30px}
  .chart svg{display:block;width:100%;height:auto;overflow:visible}
  .chart .grid{stroke:var(--c-grid);stroke-width:1}
  .chart .axis{fill:var(--muted);font-size:10px}
  .chart .ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
  .chart .dot{stroke:var(--card);stroke-width:2}
  .chart .last{fill:var(--ink);font-size:11px;font-weight:700}
  .chart .hv .cr,.chart .hv .tp{opacity:0;transition:opacity .08s}
  .chart .hv:hover .cr,.chart .hv:hover .tp{opacity:1}
  .chart .cr{stroke:var(--muted);stroke-width:1;stroke-dasharray:3 3}
  .chart .tp rect{fill:var(--card);stroke:var(--line)}
  .chart .tp text{fill:var(--ink);font-size:11px}
  .chart .tp text.m{fill:var(--muted)}
  .spark{display:block;vertical-align:-3px}
`;
  document.head.appendChild(style);

  const esc = t => String(t == null ? '' : t)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');

  /**
   * ГРАФИК ОДНОЙ ВЕЛИЧИНЫ ПО СБОРАМ. Намеренно по одной линии на график, а рядом — вторая такая же:
   * доля доров 34% и наша доля 0.6% на одной оси дали бы прямую по нулю вместо динамики. Ось всегда
   * от нуля — у доли и у счёта обрезанное основание врёт о размере изменения.
   *
   * @param labels подписи сборов, от старых к новым
   * @param values значения (null — бренда в том сборе не было, линия разрывается)
   */
  function chartHtml(title, sub, labels, values, color, unit){
    const n = values.length;
    if(n < 2) return `<div class="chart"><div class="ct">${esc(title)}</div>
      <div class="cs">График появится после второго сбора</div></div>`;
    const W = 300, H = 120, pl = 30, pr = 16, pt = 10, pb = 18;
    const plotW = W - pl - pr, plotH = H - pt - pb;
    const real = values.filter(v => v !== null && v !== undefined);
    const sc = scaleOf(Math.max(...real, 0), unit);
    const x = i => pl + (n === 1 ? plotW / 2 : i * plotW / (n - 1));
    const y = v => pt + (1 - v / sc.top) * plotH;
    const fmt = v => (unit === '%' ? (Math.round(v * 10) / 10) + '%' : String(Math.round(v)));
  
    let grid = '';
    for(let g = 0; g <= sc.n; g++){
      const v = sc.step * g, yy = y(v);
      grid += `<line class="grid" x1="${pl}" x2="${W - pr}" y1="${yy}" y2="${yy}"></line>`
        + `<text class="axis" x="${pl - 5}" y="${yy + 3}" text-anchor="end">${esc(fmt(v))}</text>`;
    }
    // Подписи сборов — РОВНО по краям и между ними: раньше бралось «каждое N-е плюс обязательно
    // последнее», и предпоследняя подпись налезала на последнюю.
    const steps = Math.min(n, 4);
    const marks = new Set();
    for(let k = 0; k < steps; k++) marks.add(Math.round(k * (n - 1) / (steps - 1)));
    let xs = '';
    [...marks].forEach(i => {
      xs += `<text class="axis" x="${x(i)}" y="${H - 4}" text-anchor="${i === 0 ? 'start' : (i === n - 1 ? 'end' : 'middle')}">${esc(labels[i])}</text>`;
    });
  
    // Линия рвётся на пропусках: сбор, в котором бренда не было, — это не ноль.
    let d = '', pen = false;
    values.forEach((v, i) => { if(v === null || v === undefined){ pen = false; return; } d += `${pen ? 'L' : 'M'}${x(i)} ${y(v)} `; pen = true; });
    const dots = n <= 20 ? values.map((v, i) => v === null || v === undefined ? ''
      : `<circle class="dot" cx="${x(i)}" cy="${y(v)}" r="3.5" fill="${color}"></circle>`).join('') : '';
  
    // Последнее значение подписано прямо на графике — его и смотрят в первую очередь.
    let lastI = -1;
    for(let i = n - 1; i >= 0; i--){ if(values[i] !== null && values[i] !== undefined){ lastI = i; break; } }
    const lastLabel = lastI >= 0
      ? `<text class="last" x="${Math.min(W - 2, x(lastI) + 6)}" y="${Math.max(pt + 8, y(values[lastI]) - 6)}" text-anchor="${lastI === n - 1 ? 'end' : 'start'}">${esc(fmt(values[lastI]))}</text>` : '';
  
    // Наведение: прозрачная колонка на каждый сбор, в ней — пунктир и подсказка.
    const slot = plotW / Math.max(1, n - 1);
    const hover = values.map((v, i) => {
      const cx = x(i), left = cx > W / 2;
      const tw = 104, th = 32, tx = left ? cx - tw - 6 : cx + 6, ty = pt + 2;
      const val = v === null || v === undefined ? 'нет в сборе' : fmt(v);
      return `<g class="hv"><rect x="${cx - slot / 2}" y="${pt}" width="${slot}" height="${plotH}" fill="transparent"></rect>
        <line class="cr" x1="${cx}" x2="${cx}" y1="${pt}" y2="${pt + plotH}"></line>
        <g class="tp" transform="translate(${tx},${ty})"><rect x="0" y="0" width="${tw}" height="${th}" rx="6"></rect>
          <text class="m" x="7" y="13">${esc(labels[i])}</text><text x="7" y="26">${esc(val)}</text></g></g>`;
    }).join('');
  
    return `<div class="chart"><div class="ct">${esc(title)}</div><div class="cs">${esc(sub)}</div>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">
        ${grid}${xs}<path class="ln" d="${d.trim()}" stroke="${color}"></path>${dots}${lastLabel}${hover}
      </svg></div>`;
  }
  
  /**
   * Шкала с КРУГЛЫМИ делениями: от нуля до ближайшего круглого числа выше максимума, 2–5 интервалов.
   * Без этого деления получались вида «41.3%», а на счётах пропадала двойка — верх делился на четыре
   * и округлялся при выводе.
   */
  function scaleOf(max, unit){
    const target = Math.max(max * 1.12, unit === '%' ? 4 : 2);
    const cand = [];
    for(let e = -1; e <= 6; e++){ const m = Math.pow(10, e); [1, 2, 2.5, 5].forEach(b => cand.push(b * m)); }
    // У счёта (сайты, доры) дробного шага быть не может: «2.5 дора» — не деление.
    const steps = (unit === '%' ? cand : cand.filter(v => Number.isInteger(v))).sort((a, b) => a - b);
    for(const step of steps){
      const n = Math.ceil(target / step);
      // Доля выше 100% не бывает: с запасом сверху шкала уезжала на «125%», и линия у 91%
      // выглядела как половина графика.
      if(unit === '%' && step * n > 100 && max <= 100) return {step: 25, n: 4, top: 100};
      if(n >= 2 && n <= 5) return {step, n, top: step * n};
    }
    return {step: target / 4, n: 4, top: target};
  }
  
  /** Короткая подпись сбора для оси: «28.10». */
  function collectLabel(at){
    const d = at ? new Date(at) : null;
    return d && !isNaN(d) ? d.toLocaleDateString('ru-RU', {day:'2-digit', month:'2-digit'}) : '—';
  }

  /**
   * СПАРКЛАЙН — форма ряда без осей и подписей, размером со строку таблицы: нужен там, где число
   * уже написано рядом, а узнать надо «растёт или падает», не раскрывая бренд.
   *
   * Шкала от НУЛЯ до максимума ряда: ряд 60→70 и правда почти ровный относительно своей величины,
   * а наша доля в 1% при чужих 70% должна выглядеть прижатой к низу — это и есть ответ.
   */
  function sparkHtml(values, color, title){
    const pts = (values || []).filter(v => v !== null && v !== undefined);
    if(pts.length < 2) return '';
    const W = 62, H = 16, pad = 2;
    const top = Math.max(...pts, 0.0001);
    const n = values.length;
    const x = i => pad + i * (W - pad * 2) / (n - 1);
    const y = v => H - pad - (v / top) * (H - pad * 2);
    let d = '', pen = false, last = -1;
    values.forEach((v, i) => {
      if(v === null || v === undefined){ pen = false; return; }
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)} `;
      pen = true; last = i;
    });
    const dot = last >= 0 ? `<circle cx="${x(last).toFixed(1)}" cy="${y(values[last]).toFixed(1)}" r="2" fill="${color}"></circle>` : '';
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img"`
      + `${title ? ` aria-label="${esc(title)}"` : ''}><title>${esc(title || '')}</title>`
      + `<path d="${d.trim()}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"></path>${dot}</svg>`;
  }

  window.chartHtml = chartHtml;
  window.sparkHtml = sparkHtml;
  window.collectLabel = collectLabel;
})();

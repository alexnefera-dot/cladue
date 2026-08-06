/* Финансы: курсы · портфель (автоцена qty×курс) · счета · расходы · долги · планы · FIRE · макро */
let finData = null;
// вкладок «Факт»/«Целевой» больше нет: дерево одно, экран один
let finSection = 'all';     // подвкладка раздела
const finIso = (d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);   // локальная дата
let finTxMonth = finIso(new Date()).slice(0, 7);
let showMonefy = false;
let finHide = true;        // каждый заход начинается со скрытых значений — открываются только глазками
let finShown = new Set();  // точечно раскрытые разделы (до общего скрытия/перезагрузки)

const finApi = {
  list: () => fetch('/api/fin').then(r => r.json()),
  add: (ent, b) => fetch(`/api/fin/${ent}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  patch: (ent, id, b) => fetch(`/api/fin/${ent}/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  del: (ent, id) => fetch(`/api/fin/${ent}/${id}`, { method: 'DELETE' }),
  pay: id => fetch(`/api/fin/obligations/${id}/pay`, { method: 'POST' }),
  toTask: id => fetch(`/api/fin/steps/${id}/task`, { method: 'POST' }).then(r => r.json()),
  txMonth: ym => fetch('/api/fin/tx?month=' + ym).then(r => r.json()),
  monefy: csv => fetch('/api/fin/monefy', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ csv }) }).then(r => r.json()),
  fire: b => fetch('/api/fin/fire', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  macroAdd: b => fetch('/api/fin/macro', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }),
  macroDel: id => fetch('/api/fin/macro/' + id, { method: 'DELETE' }),
  ratesRefresh: () => fetch('/api/rates/refresh', { method: 'POST' }).then(r => r.json()),
  rateSet: (sym, price) => fetch('/api/rates/' + encodeURIComponent(sym), { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ price }) }),
};

const fmt = n => n == null ? '—' : Math.round(n).toLocaleString('ru-RU');
const fmtE = n => n == null ? '—' : fmt(n) + ' €';
const fesc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const parseNum = s => {
  let t = String(s).trim().toLowerCase().replace(/\s/g, '').replace(',', '.');
  let mul = 1;
  if (t.endsWith('k')) { mul = 1e3; t = t.slice(0, -1); }
  if (t.endsWith('m')) { mul = 1e6; t = t.slice(0, -1); }
  const v = parseFloat(t);
  return isNaN(v) ? null : v * mul;
};
const ACCT = { bank: 'банк', broker: 'брокер', cash: 'кэш', crypto: 'крипто', deposit: 'вклад', safe: 'ячейка' };
const ATYPES = ['крипто', 'кеш', 'баланс', 'баланс не мой', 'недвижка EU', 'недвижка UA', 'авто', 'акции', 'золото', 'облигации'];
const REGIONS = ['SK', 'UA', 'AU', 'EU', 'WEB', 'USA', 'UAE', 'PT'];   // регион инвестиции
const RSYMS = ['BTCUSD', 'XAUUSD', 'SCHD', 'IVV', 'VHT'];
const STEPK = { buy: ['купить', 'ok'], sell: ['продать', 'p1'], transfer: ['перевод', 'p2'] };
const PERIOD = { monthly: 'мес', yearly: 'год', once: 'разово' };
const RATE_FMT = { 'XAUUSD': v => '$' + fmt(v), 'EURUSD': v => v?.toFixed(4), 'BTCUSD': v => '$' + fmt(v),
  'SCHD': v => '$' + fmt(v), 'IVV': v => '$' + fmt(v), 'VHT': v => '$' + fmt(v) };

window.loadFin = async function () {
  const el = document.getElementById('screen-fin');
  try {
    finData = await finApi.list();
    if (!finData || finData.error || !Array.isArray(finData.portfolio)) {   // бэкенд отдал ошибку — показываем причину, не белый экран
      if (el) el.innerHTML = `<h2>Финансы</h2><div class="card" style="color:var(--red);margin-top:12px">Не удалось загрузить финансы: <span class="meta">${fesc(String((finData && finData.error) || 'нет данных'))}</span></div>`;
      return;
    }
    if (finTxMonth !== finIso(new Date()).slice(0, 7)) finData.tx = await finApi.txMonth(finTxMonth);
    renderFin();
  } catch (e) {
    if (el) el.innerHTML = `<h2>Финансы</h2><div class="card" style="color:var(--red);margin-top:12px">Ошибка отрисовки: <span class="meta">${fesc(String(e && e.message || e))}</span></div>`;
  }
};

// ===== Портфель: строки таблицы =====
// свёрнутые узлы — переживают перерисовку и перезапуск
const portFold = new Set(JSON.parse(localStorage.portFold ?? '[]'));
let tgtMove = null;   // {from, to, amount} — раскрытая форма переноса; null = закрыта, нигде не показывается
const savePortFold = () => localStorage.portFold = JSON.stringify([...portFold]);

function portRows(it, depth, ctx) {
  const target = true;   // экран один
  const pfx = 'tgt';
  const editable = it.kind === 'asset' || !it.children.length;
  const rowCls = it.kind === 'block' ? 'pblock' : it.kind === 'section' ? 'psection' : '';
  const folded = portFold.has(it.id);
  let cells;
  {
    // целевой: Цель · Ребаланс (конкретные связки откуда→куда прямо в строке) · Доля
    const path = (ctx?.path || '') + '/' + (it.name || '').trim().toLowerCase();
    const cur = it.currency ?? '€';
    // Бэкенд применяет перелив к value сразу при создании связки — в базе лежит состояние ПОСЛЕ
    // перестановок. Поэтому: «Сейчас» = старт (value − транзакции, его и правим руками),
    // «Стало» = что вышло после всех транзакций «в» и «из» (то, что в базе).
    // переносы — чистое наложение: «Сейчас» хранится как есть, «Стало» = «Сейчас» + переносы
    const net = ctx?.netByPath?.[path] || 0;
    const netCur = cur === '$' ? net * (ctx?.rate || 1.08) : net;   // в валюте позиции (у автоцены она '$')
    // «Сейчас» несёт три вещи: сумму, долю и — если есть переносы — во что она превратится
    const shareTot = ctx?.total > 0 && it.eur > 0 ? it.eur / ctx.total * 100 : null;
    const shareCat = ctx?.blockEur > 0 && it.eur > 0 ? it.eur / ctx.blockEur * 100 : null;
    const shareSub = shareTot == null ? '' :
      `<span class="sub" title="доля от всего портфеля / внутри своего блока">${shareTot.toFixed(1)}%${shareCat != null ? ` / ${shareCat.toFixed(1)}%` : ''}</span>`;
    const nowCell = it.auto
      ? `<td class="r num now sep" title="авто: ${it.qty} × курс ${fesc(it.rate_symbol)}">⚡ ${fmt(it.value)} $${shareSub}</td>`
      : editable
        ? `<td class="r num now sep"><span class="pill btn" data-fcur="${it.id}:${cur}" title="сменить валюту">${cur}</span> <span class="ed" data-fe="tgt:${it.id}:value:num" title="сколько размещено сейчас (клик)">${it.value != null ? fmt(it.value) : '—'}</span>${shareSub}</td>`
        : `<td class="r num now sep">${fmtE(it.eur)}${shareSub}</td>`;
    // «Станет» — только когда переносы запланированы; иначе колонка молчит, а не повторяет «Сейчас»
    const becameCell = `<td class="r num">${net === 0 ? '<span class="dash">—</span>'
      : `<span class="${net > 0 ? 'up' : 'down'}" title="сейчас ${editable ? fmt(it.value || 0) : fmtE(it.eur)} ${net > 0 ? '+' : '−'} ${fmt(Math.abs(editable ? netCur : net))} переносами">→ ${editable ? fmt((it.value || 0) + netCur) : fmtE((it.eur || 0) + net)}</span>`}</td>`;
    // покупка и прирост — из прежней вкладки «Факт», они не дублируются нигде больше
    const g = it.invested != null && it.invested && !(editable && it.buy_value == null)
      ? (it.investedCur - it.invested) / it.invested * 100 : null;
    const buyCell = `<td class="r num muted ${editable ? 'ed' : ''}" ${editable ? `data-fe="tgt:${it.id}:buy_value:num" title="цена покупки в валюте позиции (${fesc(cur)}) · не задана — равна текущей"` : ''}>${editable ? (it.buy_value != null ? fmt(it.buy_value) + ' ' + fesc(cur) : (it.value != null ? '≈ ' + fmt(it.value) + ' ' + fesc(cur) : '—')) : (it.invested != null ? fmt(it.invested) + ' €' : '')}</td>`;
    const gainCell = `<td class="r num">${g != null ? `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>` : ''}</td>`;
    // Цель: одно поле задано, второе выведено. Клик по любому из них закрепляет именно его.
    const capT = ctx?.total || 0;
    const planPctShown = it.planPin === 'pct' ? it.target_pct
      : (it.planEur != null && capT > 0 ? it.planEur / capT * 100 : null);
    const planEurShown = it.planPin === 'eur' ? it.target_value : (it.planEur != null ? it.planEur : null);
    const pctCell = `<span class="ed${it.planPin === 'pct' ? ' pinned' : ' derived'}" data-fe="tgt:${it.id}:target_pct:num" title="цель долей (клик закрепит её)">${planPctShown != null ? planPctShown.toFixed(1) + '%' : '—'}</span>`;
    const eurCell = `<span class="ed${it.planPin === 'eur' ? ' pinned' : ' derived'}" data-fe="tgt:${it.id}:target_value:num" title="цель суммой (клик закрепит её)">${planEurShown != null ? fmt(planEurShown) : '—'}</span>`;
    const planDiff = it.planPin && it.planKids && Math.abs((it.planEur || 0) - it.planKids) >= 1
      ? `<div class="meta" title="своя цель расходится с суммой целей внутри">по позициям ${fmtE(it.planKids)}</div>` : '';
    const planCell = `<td class="r num goal sep">${eurCell}<span class="sub">${pctCell}</span>${planDiff}</td>`;
    // Отклонение = «Стало» − «Цель»: положительное — перевес, отрицательное — недобор
    const becameEur = (it.eur || 0) + net;
    const dev = it.planEur != null && it.planEur > 0 ? becameEur - it.planEur : null;
    const devPP = dev != null && ctx?.total > 0 ? dev / ctx.total * 100 : null;
    const devCell = `<td class="r num">${dev == null ? '' : Math.abs(dev) < 1
      ? '<span class="up">✓ в цели</span>'
      : `<span class="${dev > 0 ? 'dev-over' : 'dev-under'}">${dev > 0 ? '+' : '−'}${fmtE(Math.abs(dev))}<span class="meta devpp">${devPP > 0 ? '+' : '−'}${Math.abs(devPP).toFixed(1)} п.п.</span></span>`}</td>`;
    const links = [
      ...(ctx?.movesBySrc?.[path] || []).map(mv => `<div class="meta"><span class="down">→ отдать ${fmt(mv.amount)} ${fesc(mv.cur)}</span> в «${fesc(mv.toName)}» <span class="rowbtn del" data-movedel="${mv.id}" title="убрать связку">✕</span></div>`),
      ...(ctx?.movesByDst?.[path] || []).map(mv => `<div class="meta"><span class="up">← добрать ${fmt(mv.amount)} ${fesc(mv.cur)}</span> из «${fesc(mv.fromName)}»</div>`),
    ].join('');
    const moveOpen = tgtMove?.from === it.id;
    const moveBtn = editable ? `<span class="rowbtn${moveOpen ? ' on' : ''}" data-tgtmove="${it.id}" title="переложить в другую позицию">↦ переложить</span>` : '';
    cells = `${buyCell}${gainCell}${nowCell}${becameCell}${planCell}${devCell}
      <td class="sep" style="text-align:left">${links}${moveBtn}</td>`;
  }
  return `<tr class="${rowCls}" draggable="true" data-pid="${it.id}">
    <td class="pname" style="--d:${depth}">
      ${it.children.length ? `<span class="caret" data-pfold="${it.id}" title="${folded ? 'развернуть' : 'свернуть'}">${folded ? '▸' : '▾'}</span>` : ''}
      <span class="ed" data-fe="${pfx}:${it.id}:name:text" title="клик — переименовать">${fesc(it.name)}</span>
      ${folded ? `<span class="meta">· ${it.children.length} внутри</span>` : ''}
      ${editable && it.asset_type ? `<span class="pill" data-ftype="${it.id}" title="тип актива — клик">${fesc(it.asset_type)}</span>` : ''}
      ${editable && it.region ? `<span class="pill p2" data-fregion="${it.id}" title="регион инвестиции — клик">${fesc(it.region)}</span>` : ''}
      ${it.rate_symbol ? `<span class="pill btn" data-fqty="${it.id}" title="количество — клик">${it.qty ?? '?'} × ${fesc(it.rate_symbol)}</span>` : ''}
      ${it.no_rate ? '<span class="pill p1" title="курс тикера ещё не загружен — обнови курсы (⟳ вверху)">нет курса</span>' : ''}
      ${!target && it.is_loan ? '<span class="pill p2">🤝 займ</span>' : ''}
    </td>
    ${cells}
    <td class="r" style="width:96px;white-space:nowrap">
      ${it.kind === 'block' ? `<span class="rowbtn" data-${target ? 'tgtadd' : 'fadd'}="section:${it.id}" title="добавить раздел">＋</span>` : ''}
      ${it.kind === 'section' ? `<span class="rowbtn" data-${target ? 'tgtadd' : 'fadd'}="asset:${it.id}" title="добавить актив">＋</span>` : ''}
      ${editable && !it.asset_type ? `<span class="rowbtn" data-ftype="${it.id}" title="задать тип актива">⊙</span>` : ''}
      ${editable && !it.region ? `<span class="rowbtn" data-fregion="${it.id}" title="задать регион (SK/UA/AU/EU/WEB)">🌍</span>` : ''}
      ${editable ? `<span class="rowbtn" data-frate="${it.id}" title="${it.rate_symbol ? 'автоцена: сменить/убрать тикер' : 'автоцена по курсу (BTC, золото, SCHD/IVV/VHT)'}">⚡</span>` : ''}
      ${!target && editable ? `<span class="rowbtn" data-loanflag="${it.id}:${it.is_loan ? 1 : 0}" title="${it.is_loan ? 'убрать значок займа' : 'пометить как займ'}">🤝</span>` : ''}
      <span class="rowbtn del" data-findel="${pfx}:${it.id}">✕</span>
    </td>
  </tr>` + (target && tgtMove?.from === it.id ? tgtMoveForm(it, ctx) : '')
    + (folded ? '' : it.children.map(c => portRows(c, depth + 1, { total: ctx?.total, planTotal: ctx?.planTotal, parentEur: it.eur, blockEur: depth === 0 ? it.eur : ctx?.blockEur, blockTarget: depth === 0 ? it.planEur : ctx?.blockTarget, tgt: target, tree: ctx?.tree, movesBySrc: ctx?.movesBySrc, movesByDst: ctx?.movesByDst, netByPath: ctx?.netByPath, rate: ctx?.rate, path: (ctx?.path || '') + '/' + (it.name || '').trim().toLowerCase() })).join(''));
}

const finIsMobile = () => window.matchMedia('(max-width: 768px)').matches;

// телефон: строка финансов двухстрочной карточкой — имя и сумма сверху, метки/кнопки снизу.
// Внутренние span'ы (с data-fe / data-*) переезжают как есть, поэтому биндинги не трогаем.
function fRow({ lead = '', name, amount = '', meta = '', actions = '', cls = '' }) {
  return `<div class="frow ${cls}">
    <div class="fr-top">${lead}<span class="fr-name${cls.includes('done') ? ' done' : ''}">${name}</span>${amount ? `<span class="fr-amt">${amount}</span>` : ''}</div>
    ${meta || actions ? `<div class="fr-bot">${meta}${actions ? `<span class="fr-act">${actions}</span>` : ''}</div>` : ''}
  </div>`;
}

// телефон: портфель карточками в столбик вместо широкой таблицы (data-* те же — биндинги работают)
// Форма переноса: раскрывается строкой под позицией и больше нигде не появляется.
// Считает последствия для обеих сторон до того, как перенос создан.
function tgtMoveForm(from, ctx) {
  const cap = ctx?.total || 0;
  const rate = ctx?.rate || 1.08;
  const eurOf = (n) => n.eur || 0;
  const planOf = (n) => n.planEur || 0;
  const devOf = (n, extra = 0) => planOf(n) > 0 ? (eurOf(n) + extra) - planOf(n) : null;
  const pp = (v) => cap > 0 ? v / cap * 100 : 0;

  // куда можно переложить — листья целевого, кроме этой; сверху те, кому недостаёт больше
  const leaves = [];
  const walk = (ns, pre) => (ns || []).forEach(n => {
    const kids = n.children || [];
    if ((n.kind === 'asset' || !kids.length) && n.id !== from.id) {
      leaves.push({ n, label: pre ? `${pre} · ${n.name}` : n.name, need: Math.max(0, planOf(n) - eurOf(n)) });
    }
    walk(kids, pre || n.name);
  });
  walk(ctx?.tree || [], '');
  leaves.sort((a, b) => b.need - a.need);

  const to = leaves.find(l => l.n.id === tgtMove.to) || leaves[0];
  const amt = tgtMove.amount;
  const surplus = Math.max(0, eurOf(from) - planOf(from));
  const need = to ? to.need : 0;
  const curF = from.currency ?? '€';

  const prev = (n, delta) => {
    const d0 = devOf(n), d1 = devOf(n, delta);
    const cls = (v) => v == null ? '' : Math.abs(pp(v)) < 0.05 ? 'ok-dev' : v > 0 ? 'dev-over' : 'dev-under';
    return `<span class="mono">${fesc(n.name)}</span>
      <span class="num">${fmt(eurOf(n))} <i class="arr">→</i> ${fmt(eurOf(n) + delta)} €</span>
      <span class="num">${d0 == null ? '<span class="meta">цель не задана</span>'
        : `<span class="${cls(d0)}">${d0 >= 0 ? '+' : '−'}${Math.abs(pp(d0)).toFixed(1)}</span> <i class="arr">→</i> <span class="${cls(d1)}">${d1 >= 0 ? '+' : '−'}${Math.abs(pp(d1)).toFixed(1)} п.п.</span>`}</span>`;
  };

  return `<tr class="tgtform-row"><td class="formcell" colspan="8"><div class="tgtform">
    <div class="frow"><span class="flab">Куда</span>
      <select class="fbox" id="tgtMoveTo">${leaves.map(l =>
        `<option value="${l.n.id}"${to && l.n.id === to.n.id ? ' selected' : ''}>${fesc(l.label)}${l.need > 0 ? ` — не хватает ${fmt(l.need)}` : ''}</option>`).join('')}</select>
      <span class="fhint">${need > 0 ? `<span class="dev-under">не хватает ${fmt(need)} €</span>` : '<span class="meta">эта позиция уже в цели</span>'} · список отсортирован по недобору</span>
    </div>
    <div class="frow"><span class="flab">Сколько</span>
      <input class="fbox amt" id="tgtMoveAmt" inputmode="decimal" value="${amt ?? ''}" placeholder="0"> 
      <span class="fhint">
        ${surplus > 0 ? `<span class="quick" data-mvq="${Math.round(surplus)}">всё, что сверх · ${fmt(surplus)}</span>` : ''}
        ${need > 0 ? `<span class="quick" data-mvq="${Math.round(need)}">сколько не хватает · ${fmt(need)}</span>` : ''}
        <span class="meta">${fesc(curF)}</span>
      </span>
    </div>
    ${amt > 0 && to ? `<div class="mvprev">
      <span class="pv-h">станет после переноса</span>
      ${prev(from, -(curF === '$' ? amt / rate : amt))}
      ${prev(to.n, (curF === '$' ? amt / rate : amt))}
    </div>` : ''}
    <div class="frow"><span class="flab"></span>
      <span><span class="pill btn ok" id="tgtMoveGo">переложить</span> <span class="pill btn" id="tgtMoveCancel">отмена</span></span>
      <span class="fhint">создастся обычная перестановка — её видно в строке и можно удалить</span>
    </div>
  </div></td></tr>`;
}

function portCard(it, depth, ctx) {
  const target = true;   // экран один
  const pfx = 'tgt';
  const editable = it.kind === 'asset' || !it.children.length;
  const folded = portFold.has(it.id);
  const cur = it.currency ?? '€';
  const val = editable
    ? `<span class="ed num" data-fe="${pfx}:${it.id}:value:num">${it.value != null ? fmt(it.value) : '—'}</span> <span class="meta">${cur}</span>`
    : `<span class="num">${fmtE(it.eur)}</span>`;
  const g = (!target && it.invested != null && it.invested && !(editable && it.buy_value == null)) ? (it.investedCur - it.invested) / it.invested * 100 : null;
  const pTot = !target && ctx?.total > 0 && it.eur > 0 ? it.eur / ctx.total * 100 : null;
  const pCat = !target && ctx?.blockEur > 0 && it.eur > 0 ? it.eur / ctx.blockEur * 100 : null;   // внутри своего блока
  let meta;
  if (target) {
    const path = (ctx?.path || '') + '/' + (it.name || '').trim().toLowerCase();
    const planCat = ctx?.blockTarget > 0 && it.planEur > 0 ? it.planEur / ctx.blockTarget * 100 : null;   // доля плана внутри блока
    const planPct = ctx?.planTotal > 0 && it.planEur > 0 ? it.planEur / ctx.planTotal * 100 : null;
    // «Сейчас» показано крупным числом как есть; «стало» = плюс переносы
    const net = ctx?.netByPath?.[path] || 0;
    const netCur = cur === '$' ? net * (ctx?.rate || 1.08) : net;   // в валюте позиции
    const becameStr = net === 0 ? ''
      : `<span class="${net > 0 ? 'up' : 'down'}">стало ${editable ? fmt((it.value || 0) + netCur) + ' ' + fesc(cur) : fmtE((it.eur || 0) + net)}</span>`;
    const gap = (it.planEur != null && it.planEur > 0) ? ((it.eur || 0) + net) - it.planEur : null;   // стало − цель, в €
    const capT = ctx?.total || 0;
    const pPct = it.planPin === 'pct' ? it.target_pct : (it.planEur != null && capT > 0 ? it.planEur / capT * 100 : null);
    const pEur = it.planPin === 'eur' ? it.target_value : it.planEur;
    const planStr = `<span class="meta">цель: <span class="ed${it.planPin === 'pct' ? ' pinned' : ''}" data-fe="tgt:${it.id}:target_pct:num" title="цель долей (клик закрепит её)">${pPct != null ? pPct.toFixed(1) : '—'}%</span> / <span class="ed${it.planPin === 'eur' ? ' pinned' : ''}" data-fe="tgt:${it.id}:target_value:num" title="цель суммой (клик закрепит её)">${pEur != null ? fmt(pEur) : '—'}</span> ${fesc(cur)}</span>`;
    const gapStr = gap == null ? '' : Math.abs(gap) < 1 ? '<span class="up">✓ в цели</span>'
      : gap > 0 ? `<span class="dev-over">перевес ${fmtE(gap)}</span>` : `<span class="dev-under">недобор ${fmtE(-gap)}</span>`;
    const links = [
      ...(ctx?.movesBySrc?.[path] || []).map(mv => `<span class="meta"><span class="down">→ отдать ${fmt(mv.amount)} ${fesc(mv.cur)}</span> в «${fesc(mv.toName)}» <span class="rowbtn del" data-movedel="${mv.id}" title="убрать связку">✕</span></span>`),
      ...(ctx?.movesByDst?.[path] || []).map(mv => `<span class="meta"><span class="up">← добрать ${fmt(mv.amount)} ${fesc(mv.cur)}</span> из «${fesc(mv.fromName)}»</span>`),
    ].join(' ');
    const shareStr = (planPct == null && planCat == null) ? '' : `<span class="meta" title="доля плана: от своего блока / от всего целевого">доля ${planCat != null ? `<b>${planCat.toFixed(1)}% кат.</b>` : ''}${planPct != null ? ` ${planPct.toFixed(1)}% общ.` : ''}</span>`;
    meta = `${becameStr} ${planStr} ${gapStr}${links ? '<br>' + links : ''} ${shareStr}`;
  } else {
    meta = `${g != null ? `<span class="${g >= 0 ? 'up' : 'down'}">${g >= 0 ? '+' : ''}${g.toFixed(1)}%</span>` : ''}
       ${pCat != null ? `<span class="meta" title="доля внутри своего блока"><b>${pCat.toFixed(1)}% кат.</b></span>` : ''}
       ${pTot != null ? `<span class="meta" title="доля от всего портфеля">${pTot.toFixed(1)}%${pCat != null ? ' общ.' : ' портфеля'}</span>` : ''}
       ${it.is_loan ? '<span class="pill p2">🤝</span>' : ''}
       ${it.rate_symbol ? `<span class="pill btn" data-fqty="${it.id}">${it.qty ?? '?'}×${fesc(it.rate_symbol)}</span>` : ''}`;
  }
  const addPfx = target ? 'tgtadd' : 'fadd';
  const actions = `
    ${it.kind === 'block' ? `<span class="rowbtn" data-${addPfx}="section:${it.id}">＋ раздел</span>` : ''}
    ${it.kind === 'section' ? `<span class="rowbtn" data-${addPfx}="asset:${it.id}">＋ актив</span>` : ''}
    ${editable ? `<span class="rowbtn" data-frate="${it.id}" title="автоцена">⚡</span>` : ''}
    ${editable ? `<span class="rowbtn" data-fregion="${it.id}" title="регион инвестиции (SK/UA/AU/EU/WEB)">🌍${it.region ? ' ' + fesc(it.region) : ''}</span>` : ''}
    <span class="rowbtn del" data-findel="${pfx}:${it.id}">✕</span>`;
  return `<div class="pcard ${it.kind}" style="--d:${depth}" data-pid="${it.id}">
    <div class="pc-top">
      ${it.children.length ? `<span class="caret" data-pfold="${it.id}">${folded ? '▸' : '▾'}</span>` : '<span class="caret"></span>'}
      <span class="ed pc-name" data-fe="${pfx}:${it.id}:name:text">${fesc(it.name)}</span>
      <span class="pc-val">${val}</span>
    </div>
    <div class="pc-meta">${meta}${folded ? `<span class="meta">· ${it.children.length} внутри</span>` : ''}<span class="pc-actions">${actions}</span></div>
  </div>` + (folded ? '' : it.children.map(c => portCard(c, depth + 1, { total: ctx?.total, planTotal: ctx?.planTotal, parentEur: it.eur, blockEur: depth === 0 ? it.eur : ctx?.blockEur, blockTarget: depth === 0 ? it.planEur : ctx?.blockTarget, tgt: target, tree: ctx?.tree, movesBySrc: ctx?.movesBySrc, movesByDst: ctx?.movesByDst, netByPath: ctx?.netByPath, rate: ctx?.rate, path: (ctx?.path || '') + '/' + (it.name || '').trim().toLowerCase() })).join(''));
}

// диаграмма аллокации: доли с процентами внутри, каждая своим цветом
const PIE_COLORS = ['#1e9e57', '#2a76b5', '#a87708', '#7a4fc0', '#c43f3f',
  '#0e8f8f', '#b5519c', '#6b8e23', '#d2691e', '#5b6b7c'];

function allocPie(byType, total) {
  const R = 86, C = 110;
  let a0 = -Math.PI / 2;
  const slices = byType.map(([name, v], i) => {
    const frac = v / total;
    const a1 = a0 + frac * 2 * Math.PI;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p = a => [C + R * Math.cos(a), C + R * Math.sin(a)];
    const [x0, y0] = p(a0), [x1, y1] = p(a1);
    const mid = (a0 + a1) / 2;
    const [lx, ly] = [C + R * 0.62 * Math.cos(mid), C + R * 0.62 * Math.sin(mid)];
    const path = frac > 0.999
      ? `<circle cx="${C}" cy="${C}" r="${R}" fill="${PIE_COLORS[i % PIE_COLORS.length]}"/>`
      : `<path d="M${C},${C} L${x0.toFixed(1)},${y0.toFixed(1)} A${R},${R} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z"
          fill="${PIE_COLORS[i % PIE_COLORS.length]}"/>`;
    const label = frac >= 0.055
      ? `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle" dominant-baseline="middle"
          fill="#fff" font-size="13" font-weight="700">${(frac * 100).toFixed(frac < 0.1 ? 1 : 0)}%</text>` : '';
    a0 = a1;
    return path + label;
  }).join('');
  return `<svg viewBox="0 0 220 220" width="220" height="220" style="flex:0 0 auto">${slices}</svg>`;
}

// ===== Секции =====
// доход в месяц в своей валюте: из тела×ставки, если заданы; иначе из фиксированной суммы
function incMonthly(i) {
  if ((i.principal ?? 0) > 0 && (i.rate ?? 0) > 0) {
    const per = i.principal * i.rate / 100;
    return i.rate_period === 'monthly' ? per : per / 12;
  }
  return i.period === 'monthly' ? i.amount : i.period === 'yearly' ? i.amount / 12 : 0;
}
const RATEPER = { yearly: 'год', monthly: 'мес' };
const ASSET_TYPES = ['депозит', 'аренда', 'дивиденды', 'облигации', 'кэшбэк', 'роялти', 'прочее'];

// пассивный доход — всегда открыт, скрытие портфеля его не прячет
function secIncome(d, s) {
  return `
  <div class="sec">Пассивный доход</div>
  <div class="card">
    <div class="meta" style="margin-bottom:6px">💸 ПАССИВНЫЙ ДОХОД · ~${fmt(s.monthlyIncome)} € / мес</div>
    ${d.income.map(i => {
      const calc = (i.principal ?? 0) > 0 && (i.rate ?? 0) > 0;   // считаем из тела×ставки
      return `
      <div class="task">
        <span class="t ed" data-fe="income:${i.id}:name:text">${fesc(i.name)}</span>
        <span class="pill btn" data-inctype="${i.id}" title="тип актива — клик">${fesc(i.asset_type) || '＋ тип'}</span>
        ${calc ? `
        <span class="ed meta num" data-fe="income:${i.id}:principal:num" title="тело инвестиции/депозита">${fmt(i.principal)}</span>
        <span class="pill btn" data-inccur="${i.id}:${i.currency}" title="сменить валюту">${fesc(i.currency)}</span>
        <span class="ed meta num" data-fe="income:${i.id}:rate:num" title="% доходности">${(+i.rate).toLocaleString('ru-RU')}%</span>
        <span class="pill btn" data-incrper="${i.id}:${i.rate_period}" title="период ставки — клик">/${RATEPER[i.rate_period] ?? 'год'}</span>
        <span class="num acc" title="расчётный доход">= ${fmt(incMonthly(i))} ${fesc(i.currency)}/мес</span>`
        : `
        <span class="pill btn" data-incper="${i.id}:${i.period}" title="период — клик">${PERIOD[i.period] ?? i.period}</span>
        <span class="pill btn" data-inccur="${i.id}:${i.currency}" title="сменить валюту">${fesc(i.currency)}</span>
        <span class="ed num acc" data-fe="income:${i.id}:amount:num" title="фикс. сумма">${fmt(i.amount)}</span>`}
        ${i.next_date ? `<span class="ed meta num" data-fe="income:${i.id}:next_date:date" title="следующее поступление">${i.next_date}</span>`
          : `<span class="ed meta" data-fe="income:${i.id}:next_date:date" title="дата следующего поступления">＋ дата</span>`}
        <span class="rowbtn del" data-findel="income:${i.id}">✕</span>
      </div>`;
    }).join('') || '<div class="empty">депозиты, аренда, дивиденды — тело инвестиции и % доходности → доход в месяц</div>'}
    <div class="task finadd">
      <input id="incName" placeholder="источник: депозит Тинькофф, аренда…">
      <select id="incType">${ASSET_TYPES.map(t => `<option>${t}</option>`).join('')}</select>
      <input id="incPrincipal" placeholder="сумма вложения" style="width:120px">
      <select id="incCur"><option>€</option><option>$</option></select>
      <input id="incRate" placeholder="% дох." style="width:70px">
      <select id="incRatePer"><option value="yearly">% в год</option><option value="monthly">% в мес</option></select>
      <span class="pill btn ok" id="incAdd">＋</span>
    </div>
    <div class="meta" style="margin-top:4px;opacity:.7">Доход считается: сумма × % (нормируется в месяц). Для фикс. поступления оставь % пустым и впиши сумму после добавления.</div>
  </div>`;
}



function secPortfolio(d, s) {
  const tgt = true;   // единый экран портфеля: и стоимость, и цели в одной таблице
  const tree = tgt ? (d.targetPortfolio || []) : (d.portfolio || []);
  const rootTotal = tgt ? tree.reduce((a, b) => a + (b.eur || 0), 0) : s.portfolioTotal;   // сейчас размещено в целевом
  // Цель узла задаётся долей ИЛИ суммой: закреплено то поле, что заполнено, второе выводится.
  // Если своей цели нет — берём сумму вложенных. Бэкенд (calcNode) для узлов с детьми всегда
  // отдаёт сумму и собственное target_value игнорирует, поэтому считаем здесь.
  if (tgt) {
    const rateP = s.rate || d.rate || 1.08;
    const setPlan = n => {
      const kids = n.children || [];
      kids.forEach(setPlan);
      // доля считается от всего размещённого в целевом — от того же тотала, что и «Сейчас %»
      const own = n.target_pct != null ? n.target_pct / 100 * rootTotal
        : n.target_value != null ? ((n.currency ?? '€') === '$' ? n.target_value / rateP : n.target_value)
        : null;
      const kidsSum = kids.reduce((a, c) => a + (c.planEur || 0), 0);
      n.planKids = kids.length ? kidsSum : null;   // сумма по вложенным — для подсказки о расхождении
      n.planEur = own != null ? own : (kids.length ? (kidsSum || null) : null);
      n.planPin = n.target_pct != null ? 'pct' : n.target_value != null ? 'eur' : null;   // что закреплено
    };
    tree.forEach(setPlan);
  }
  const planTotal = tgt ? tree.reduce((a, b) => a + (b.planEur || 0), 0) : 0;   // сумма планов верхнего уровня
  // Мониторинг по категориям: у каждой — сколько есть сейчас и сколько нужно по цели.
  // Тип живёт на листьях, поэтому и «сейчас», и «цель» собираем по ним же.
  const catNow = {}, catPlan = {};
  if (tgt) {
    let leafPlan = 0;
    const walkCat = n => {
      const kids = n.children || [];
      if (n.kind === 'asset' || !kids.length) {
        const ty = n.asset_type || 'без типа';
        catNow[ty] = (catNow[ty] || 0) + (n.eur || 0);
        const pv = n.planEur || 0;
        if (pv > 0) { catPlan[ty] = (catPlan[ty] || 0) + pv; leafPlan += pv; }
      }
      kids.forEach(walkCat);
    };
    tree.forEach(walkCat);
    if (planTotal - leafPlan > 1) catPlan['не расписано'] = planTotal - leafPlan;
  }
  // строки мониторинга: сортируем по величине отклонения — сверху то, что дальше от цели
  const catRows = [...new Set([...Object.keys(catNow), ...Object.keys(catPlan)])]
    .map(ty => {
      const now = catNow[ty] || 0, plan = catPlan[ty] || 0;
      const nowP = rootTotal > 0 ? now / rootTotal * 100 : 0;
      const planP = rootTotal > 0 ? plan / rootTotal * 100 : 0;
      return { ty, now, plan, nowP, planP, dev: now - plan, devP: nowP - planP };
    })
    .filter(r => r.now > 0 || r.plan > 0)
    .sort((a, b) => Math.abs(b.devP) - Math.abs(a.devP));
  const catMaxP = Math.max(1, ...catRows.map(r => Math.max(r.nowP, r.planP)));
  const rctx = { total: rootTotal, planTotal, parentEur: rootTotal, tgt, tree, path: '' };
  if (tgt) {   // ручные связки ребаланса (из target_moves): сопоставляем id позиций с путём/именем
    const byId = {};
    const mapIds = (ns, pre) => (ns || []).forEach(n => { const p = pre + '/' + (n.name || '').trim().toLowerCase(); byId[n.id] = { path: p, name: n.name, cur: n.currency ?? '€' }; mapIds(n.children, p); });
    mapIds(tree, '');
    const rate = s.rate || d.rate || 1.08;   // курс лежит в summary (s.rate), не в d
    rctx.rate = rate;                        // нужен строкам: суммы показываем в валюте позиции
    const inCur = (eur, cur) => cur === '$' ? eur * rate : eur;   // amount хранится в €, показываем в валюте стороны
    rctx.movesBySrc = {}; rctx.movesByDst = {}; rctx.netByPath = {};
    // чистая дельта транзакций в € — узлу и всем его предкам (пути = префиксы), чтобы «Сейчас»
    // и «Стало» сходились и на разделах/блоках, а не только на листьях
    const addNet = (path, delta) => {
      let p = '';
      for (const seg of path.split('/').filter(Boolean)) { p += '/' + seg; rctx.netByPath[p] = (rctx.netByPath[p] || 0) + delta; }
    };
    (d.targetMoves || []).forEach(mv => {
      const a = byId[mv.from_id], b = byId[mv.to_id]; if (!a || !b) return;
      (rctx.movesBySrc[a.path] ||= []).push({ id: mv.id, amount: inCur(mv.amount, a.cur), cur: a.cur, toName: b.name });
      (rctx.movesByDst[b.path] ||= []).push({ id: mv.id, amount: inCur(mv.amount, b.cur), cur: b.cur, fromName: a.name });
      addNet(a.path, -mv.amount); addNet(b.path, mv.amount);   // mv.amount хранится в €
    });
  }
  // Сверка со старым деревом. Первая версия слияния создавала позиции, чей путь не совпал,
  // из-за чего у переименованных появлялись двойники и сумма росла. Карточка показывает, где именно.
  let mergeDiag = '';
  const legacy = d.legacyPortfolio || [];
  if (legacy.length) {
    const pathsOf = (ns, pre, acc) => (ns || []).forEach(n => {
      const p = pre + '/' + (n.name || '').trim().toLowerCase();
      const kids = n.children || [];
      if (n.kind === 'asset' || !kids.length) acc[p] = (acc[p] || 0) + (n.eur || 0);
      pathsOf(kids, p, acc);
    });
    const oldP = {}, newP = {};
    pathsOf(legacy, '', oldP); pathsOf(tree, '', newP);
    const oldTotal = legacy.reduce((a, b) => a + (b.eur || 0), 0);
    const diff = rootTotal - oldTotal;
    if (Math.abs(diff) > 1) {
      // позиции без пары в старом дереве — среди них и переименованные оригиналы, и планируемые
      const orphans = Object.entries(newP).filter(([p, v]) => oldP[p] == null && v > 0).sort((a, b) => b[1] - a[1]);
      const added = Object.entries(newP).filter(([p]) => oldP[p] != null);
      mergeDiag = `<div class="card" style="border-color:var(--amber)">
        <div class="kv" style="font-weight:700;flex-wrap:wrap;gap:8px">
          <span>Сверка со старым деревом: было <b class="num">${fmt(oldTotal)} €</b> · стало <b class="num">${fmt(rootTotal)} €</b></span>
          <span class="pill p1">${diff > 0 ? '+' : '−'}${fmt(Math.abs(diff))} €</span>
        </div>
        <div class="meta" style="margin-top:6px">Слияние создавало позиции, чей путь не совпал. Ниже — позиции, которых нет в старом дереве: среди них переименованные оригиналы (их двойник появился заново — лишний надо удалить) и те, что ты планировал сам.</div>
        ${orphans.length ? `<div style="margin-top:8px">${orphans.slice(0, 20).map(([p, v]) =>
          `<div class="kv"><span class="mono">${fesc(p)}</span><b class="num">${fmt(v)} €</b></div>`).join('')}
          ${orphans.length > 20 ? `<div class="meta">…и ещё ${orphans.length - 20}</div>` : ''}</div>`
          : '<div class="meta" style="margin-top:8px">Позиций без пары нет — расхождение в суммах, а не в структуре.</div>'}
        <div class="meta" style="margin-top:8px">Совпало со старым деревом: ${added.length} позиц. · карточка исчезнет, когда суммы сойдутся.</div>
      </div>`;
    }
  }
  return `
${mergeDiag}
  <div class="sec">Портфель · блоки → разделы → активы · всё правится кликом</div>
  <div class="viewtabs">
    <span class="pill btn" id="pfoldAll" style="margin-left:auto">${portFold.size ? '▾ развернуть всё' : '▸ свернуть всё'}</span>
  </div>
  ${tgt ? `<div class="card"><div class="kv" style="font-weight:700;padding:2px 0;flex-wrap:wrap;gap:8px">
      <span>Капитал: есть <b class="num">${fmt(s.portfolioTotal)} €</b>${planTotal > 0 ? ` · план <b class="num">${fmt(planTotal)} €</b>` : ''} · размещено <b class="num">${fmt(rootTotal)} €</b></span>
      ${planTotal > 0 ? `<span class="pill ${Math.abs(planTotal - rootTotal) < 1 ? 'ok' : planTotal > rootTotal ? 'p1' : ''}" title="разница между «Сейчас» (размещено) и планом целевого">${Math.abs(planTotal - rootTotal) < 1 ? '✓ сейчас = плану' : planTotal > rootTotal ? `до плана +${fmt(planTotal - rootTotal)} €` : `сверх плана ${fmt(rootTotal - planTotal)} €`}</span>` : ''}
    </div></div>` : ''}
  <div class="card">
    ${finIsMobile()
      ? `<div class="pcards">${tree.map(b => portCard(b, 0, rctx)).join('') || '<div class="empty">пусто</div>'}</div>`
      : `<table class="fintable porttable">
      <tr><th>Название</th>
        <th class="r" style="width:96px" title="цена покупки в валюте позиции">Покупка</th>
        <th class="r" style="width:66px">Прирост</th>
        <th class="r sep" style="width:116px" title="сколько размещено; под суммой — доля">Сейчас</th>
        <th class="r" style="width:104px" title="сейчас плюс запланированные переносы">Станет</th>
        <th class="r sep" style="width:126px" title="доля или сумма — заполненное закреплено, второе выводится">Цель</th>
        <th class="r" style="width:118px" title="станет − цель">Отклонение</th>
        <th class="sep" style="width:180px">Перестановки</th><th style="width:92px"></th></tr>
      ${tree.map(b => portRows(b, 0, rctx)).join('') || '<tr><td colspan="8"><div class="empty">пусто</div></td></tr>'}
    </table>`}
    ${tgt ? `<div class="task finadd" style="margin-top:6px"><input id="tgt_block" placeholder="новый блок целевого" style="flex:1"><span class="pill btn ok" data-tgtadd="block:">＋ блок</span></div>`
      : `<div class="task finadd" style="margin-top:6px"><input id="fact_block" placeholder="новый блок портфеля (Крипта, Бизнес…)" style="flex:1"><span class="pill btn ok" data-fadd="block:">＋ блок</span></div>`}
  </div>
  ${!tgt && (d.byType.length || (d.byRegion || []).length) ? `
  <div class="fingrid" style="grid-template-columns:1fr 1fr">
    ${d.byType.length ? `<div class="card">
      <div class="meta" style="margin-bottom:6px">ПО ТИПАМ АКТИВОВ (⊙ у строки — задать тип)</div>
      <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:6px 0">
        ${allocPie(d.byType, s.portfolioTotal)}
        <div style="flex:1;min-width:170px">
          ${d.byType.map(([t, v], i) => `
            <div class="kv"><span><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${PIE_COLORS[i % PIE_COLORS.length]};margin-right:7px"></i>${fesc(t)}</span>
              <b class="num">${fmt(v)} € · ${(v / s.portfolioTotal * 100).toFixed(1)}%</b></div>`).join('')}
        </div>
      </div>
    </div>` : ''}
    ${(d.byRegion || []).length ? `<div class="card">
      <div class="meta" style="margin-bottom:6px">ПО РЕГИОНАМ (🌍 у строки — SK/UA/AU/EU/WEB)</div>
      <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:6px 0">
        ${allocPie(d.byRegion, s.portfolioTotal)}
        <div style="flex:1;min-width:170px">
          ${d.byRegion.map(([t, v], i) => `
            <div class="kv"><span><i style="display:inline-block;width:10px;height:10px;border-radius:3px;background:${PIE_COLORS[i % PIE_COLORS.length]};margin-right:7px"></i>${fesc(t)}</span>
              <b class="num">${fmt(v)} € · ${(v / s.portfolioTotal * 100).toFixed(1)}%</b></div>`).join('')}
        </div>
      </div>
    </div>` : ''}
  </div>` : ''}
  ${tgt && catRows.length ? `
  <div class="card">
    <div class="meta" style="margin-bottom:8px">МОНИТОРИНГ · СЕЙЧАС ПРОТИВ ЦЕЛИ (⊙ у строки — задать категорию)</div>
    <div class="tgtmon">
      <div class="tgtdonut">${catDonut(catRows, rootTotal)}</div>
      <div class="barswrap"><div class="bars">
        <div class="bgrp"><span></span><span></span><i>сейчас</i><i>цель</i><i>отклонение</i></div>
        <div class="bhead"><span>категория</span><span>сейчас против цели</span>
          <span>€</span><span>%</span><span>€</span><span>%</span><span>€</span><span>п.п.</span></div>
        ${catRows.map(r => {
          const f = Math.min(r.nowP, r.planP) / catMaxP * 100;
          const over = r.nowP > r.planP ? (r.nowP - r.planP) / catMaxP * 100 : 0;
          const under = r.planP > r.nowP ? (r.planP - r.nowP) / catMaxP * 100 : 0;
          const tick = r.planP / catMaxP * 100;
          const cls = Math.abs(r.devP) < 0.05 ? 'ok-dev' : r.dev > 0 ? 'dev-over' : 'dev-under';
          return `<div class="brow" data-cat="${fesc(r.ty)}">
            <span class="blab">${fesc(r.ty)}</span>
            <span class="btrack">${f > 0 ? `<i class="bfill" style="width:${f.toFixed(1)}%"></i>` : ''}${
              over ? `<i class="bover" style="left:${f.toFixed(1)}%;width:${over.toFixed(1)}%"></i>` : ''}${
              under ? `<i class="bunder" style="left:${f.toFixed(1)}%;width:${under.toFixed(1)}%"></i>` : ''}<i class="btick" style="left:${tick.toFixed(1)}%"></i></span>
            <span class="v">${fmt(r.now)}</span><span class="v meta">${r.nowP.toFixed(1)}%</span>
            <span class="v">${r.plan ? fmt(r.plan) : '—'}</span><span class="v meta">${r.plan ? r.planP.toFixed(1) + '%' : '—'}</span>
            <span class="v ${cls}">${r.dev >= 0 ? '+' : '−'}${fmt(Math.abs(r.dev))}</span>
            <span class="v ${cls}">${r.devP >= 0 ? '+' : '−'}${Math.abs(r.devP).toFixed(1)}</span>
          </div>`;
        }).join('')}
      </div></div>
    </div>
  </div>` : ''}`;
}

// Бублик состава «сейчас»: доли подписаны на секторах, в центре — размещённый капитал.
// Мелкие сектора не подписываем — подписи наезжают, они читаются в строках справа.
function catDonut(rows, total) {
  const CX = 84, CY = 84, RO = 72, RI = 46, LR = (RO + RI) / 2;
  const pt = (r, a) => { const t = a * Math.PI / 180; return `${(CX + r * Math.cos(t)).toFixed(2)} ${(CY + r * Math.sin(t)).toFixed(2)}`; };
  const vis = rows.filter(r => r.now > 0 && total > 0).sort((a, b) => b.now - a.now);
  let ang = -90, out = '', labels = '';
  vis.forEach((r, i) => {
    const pct = r.now / total * 100, sweep = pct * 3.6, a0 = ang, a1 = ang + sweep;
    const big = sweep > 180 ? 1 : 0;
    out += `<path class="sl" data-cat="${fesc(r.ty)}" fill="${PIE_COLORS[i % PIE_COLORS.length]}" `
      + `d="M ${pt(RO, a0)} A ${RO} ${RO} 0 ${big} 1 ${pt(RO, a1)} L ${pt(RI, a1)} A ${RI} ${RI} 0 ${big} 0 ${pt(RI, a0)} Z">`
      + `<title>${fesc(r.ty)} — ${fmt(r.now)} € · ${pct.toFixed(1)}%</title></path>`;
    if (pct >= 5) {
      const m = (a0 + a1) / 2 * Math.PI / 180;
      labels += `<text class="pl" x="${(CX + LR * Math.cos(m)).toFixed(1)}" y="${(CY + LR * Math.sin(m)).toFixed(1)}">${pct.toFixed(0)}%</text>`;
    }
    ang = a1;
  });
  return `<svg viewBox="0 0 168 168" width="168" height="168" role="img" aria-label="состав целевого портфеля">
    ${out}${labels}
    <text class="ct-v" x="84" y="82">${fmt(total)}</text>
    <text class="ct-k" x="84" y="97">размещено, €</text>
  </svg>`;
}


function secAccounts(d) {
  return `
  <div class="sec">Счета · название и баланс правятся кликом</div>
  <div class="card">
    ${d.accounts.map(a => finIsMobile() ? fRow({
        lead: `<span class="pill">${ACCT[a.type] ?? a.type}</span>`,
        name: `<span class="ed" data-fe="accounts:${a.id}:name:text">${fesc(a.name)}</span>`,
        amount: `<span class="ed" data-fe="accounts:${a.id}:balance:num">${fmt(a.balance)} ${fesc(a.currency)}</span>`,
        meta: `<span class="ed meta" data-fe="accounts:${a.id}:note:text" title="пометка">${a.note ? '💬 ' + fesc(a.note) : '＋ пометка'}</span>`
          + (a.stale_days > 21 ? `<span class="meta amber">⚠ ${a.stale_days} дн.</span>` : `<span class="meta">обн. ${a.balance_updated_at.slice(0, 10)}</span>`),
        actions: `<span class="rowbtn del" data-findel="accounts:${a.id}">✕</span>`,
      }) : `
      <div class="task">
        <span class="pill">${ACCT[a.type] ?? a.type}</span>
        <span class="t ed" data-fe="accounts:${a.id}:name:text">${fesc(a.name)}</span>
        <span class="ed meta" data-fe="accounts:${a.id}:note:text" style="flex:1" title="пометка: сохраняем, тратим, подушка…">${a.note ? '💬 ' + fesc(a.note) : '＋ пометка'}</span>
        ${a.stale_days > 21 ? `<span class="meta amber">⚠ ${a.stale_days} дн.</span>` : `<span class="meta">обн. ${a.balance_updated_at.slice(0, 10)}</span>`}
        <span class="ed num" data-fe="accounts:${a.id}:balance:num">${fmt(a.balance)} ${fesc(a.currency)}</span>
        <span class="rowbtn del" data-findel="accounts:${a.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <input id="accName" placeholder="новый счёт: название">
      <select id="accType">${Object.entries(ACCT).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select>
      <select id="accCur"><option>€</option><option>$</option></select>
      <input id="accBal" placeholder="баланс" style="width:110px">
      <span class="pill btn ok" id="accAdd">＋</span>
    </div>
  </div>`;
}

// Расходы (фикс сумма/мес) + доход по месяцам с источниками, сводка по кварталам, годовой = сумма кварталов.
function renderBudget(items, rates) {
  items = Array.isArray(items) ? items : [];
  const rate = (Array.isArray(rates) ? rates.find(r => r.symbol === 'EURUSD')?.price : 0) || 1.08;
  const eur = i => (i.currency === '$' ? (+i.amount || 0) / rate : (+i.amount || 0));   // всё сводим в €
  const m = v => fmt(v) + ' €';
  const curSel = id => `<select id="${id}"><option value="€">€</option><option value="$">$</option></select>`;

  // РАСХОДЫ — фиксированная сумма в месяц
  const exp = items.filter(i => i.direction !== 'income').sort((a, b) => eur(b) - eur(a));
  const expMonth = exp.reduce((s, i) => s + eur(i), 0);
  const expRow = i => `
    <div class="task">
      <span class="t ed" data-fe="budget:${i.id}:name:text">${fesc(i.name) || '—'}</span>
      <span class="ed num down" data-fe="budget:${i.id}:amount:num">${fmt(i.amount)} ${fesc(i.currency)}</span>
      <span class="rowbtn del" data-findel="budget:${i.id}">✕</span>
    </div>`;

  // ДОХОД — сгруппирован по месяцам (видно итог месяца + источники), сводка по кварталам
  const inc = items.filter(i => i.direction === 'income');
  const byMonth = {};
  inc.forEach(i => { (byMonth[i.month || '—'] ??= []).push(i); });
  const monthKeys = Object.keys(byMonth).sort().reverse();
  const monthSum = mo => byMonth[mo].reduce((s, i) => s + eur(i), 0);
  const qOf = mo => { const p = String(mo).split('-'); return p[1] ? `${p[0]}·Q${Math.ceil(+p[1] / 3)}` : '—'; };
  const byQ = {};
  monthKeys.forEach(mo => { const q = qOf(mo); byQ[q] = (byQ[q] || 0) + monthSum(mo); });
  const qKeys = Object.keys(byQ).sort();
  const nQ = qKeys.length || 1;
  const incYear = inc.reduce((s, i) => s + eur(i), 0);              // годовой = сумма всех введённых
  const incQAvg = incYear / nQ;                                     // средний доход за квартал
  const lastQ = qKeys[qKeys.length - 1];                            // самый свежий квартал (qKeys по возрастанию)
  const incMonth = (lastQ ? byQ[lastQ] : incQAvg) / 3;              // средний доход в месяц — по последнему кварталу
  const incForecast = lastQ ? byQ[lastQ] * 4 : incYear;            // прогноз года: ПОСЛЕДНИЙ квартал × 4 (не среднее — доход падает)
  const bal = incMonth - expMonth;

  return `
  <div class="sec">Расходы и доходы</div>
  <div class="card">
    <div class="kv" style="padding:6px 0;border-bottom:1px solid var(--line)">
      <span class="meta">в месяц (средн.)</span>
      <span>расход <b class="down">${m(expMonth)}</b> · доход <b class="up">${m(incMonth)}</b> · баланс <b class="${bal >= 0 ? 'up' : 'down'}">${bal >= 0 ? '+' : ''}${m(bal)}</b></span>
    </div>
    <div class="kv" style="padding:4px 0;border-bottom:1px solid var(--line)">
      <span class="meta">в год</span>
      <span class="meta">расход <b class="down">${m(expMonth * 12)}</b> · доход факт <b class="up">${m(incYear)}</b> · прогноз <b class="up">${m(incForecast)}</b></span>
    </div>

    <div class="meta" style="margin:8px 0 2px">РАСХОДЫ · ${m(expMonth)} / мес · ${m(expMonth * 12)} / год</div>
    ${exp.map(expRow).join('') || '<div class="empty">добавь статьи расходов ↓</div>'}
    <div class="task finadd">
      <input id="bud_exp_name" placeholder="статья расхода">
      <input id="bud_exp_amt" placeholder="сумма/мес" style="width:90px">
      ${curSel('bud_exp_cur')}
      <span class="pill btn ok" data-budadd="expense">＋</span>
    </div>

    <div class="meta" style="margin:12px 0 2px">ДОХОД · факт ${m(incYear)} · прогноз года ${m(incForecast)} (посл. кв.${lastQ ? ' ' + m(byQ[lastQ]) : ''} ×4) · ${m(incMonth)}/мес</div>
    ${qKeys.length ? `<div class="btnrow" style="margin:2px 0 6px">${qKeys.slice().reverse().map(q => `<span class="pill ok">${q}: ${m(byQ[q])}</span>`).join('')}</div>` : ''}
    ${monthKeys.length ? monthKeys.map(mo => `
      <div class="kv" style="margin-top:6px;font-weight:700"><span>${fesc(mo)} <span class="meta" style="font-weight:400">${qOf(mo)}</span></span><span class="num up">${m(monthSum(mo))}</span></div>
      ${byMonth[mo].map(i => `
        <div class="task" style="padding-left:12px">
          <span class="t ed" data-fe="budget:${i.id}:name:text">${fesc(i.name) || 'доход'}</span>
          <span class="ed num up" data-fe="budget:${i.id}:amount:num">${fmt(i.amount)} ${fesc(i.currency)}</span>
          <span class="rowbtn del" data-findel="budget:${i.id}">✕</span>
        </div>`).join('')}
    `).join('') : '<div class="empty">внеси доход по месяцам ↓ — посчитаю кварталы и год</div>'}
    <div class="task finadd" style="margin-top:6px">
      <input id="bud_inc_month" placeholder="ГГГГ-ММ" value="${finIso(new Date()).slice(0, 7)}" style="width:90px">
      <input id="bud_inc_name" placeholder="источник" style="width:110px">
      <input id="bud_inc_amt" placeholder="сумма" style="width:80px">
      ${curSel('bud_inc_cur')}
      <span class="pill btn ok" data-budadd="income">＋</span>
    </div>
  </div>`;
}

function renderTx(tx, budget) {
  const maxCat = tx.categories[0]?.[1] ?? 1;
  // базовый минимум месяца: уложились или перерасход
  const isCurrent = tx.month === finIso(new Date()).slice(0, 7);
  const over = budget ? tx.expense - budget : 0;
  const pct = budget ? Math.min(100, tx.expense / budget * 100) : 0;
  const budgetBar = `
    <div style="padding:8px 0;border-bottom:1px solid var(--line)">
      <div class="kv"><span>БАЗОВЫЙ МИНИМУМ / МЕС
        <b class="ed num" id="txBudget" title="клик — задать базовый минимум">${budget ? fmt(budget) + ' €' : '＋ задать'}</b></span>
        ${budget ? `<b class="num ${over > 0 ? 'down' : 'up'}">${over > 0
          ? `перерасход +${fmt(over)} €${isCurrent ? '' : ' ✗'}`
          : (isCurrent ? `остаток ${fmt(-over)} €` : `уложились ✓ (+${fmt(-over)} € в запасе)`)}</b>` : ''}
      </div>
      ${budget ? `<div class="bar" style="margin-top:4px"><i style="width:${pct}%;${over > 0 ? 'background:var(--red)' : ''}"></i></div>` : ''}
    </div>`;
  return `
  <div class="sec">Расходы и доходы</div>
  <div class="card">
    <div class="task" style="border-bottom:1px solid var(--line)">
      <span class="pill btn" id="txPrev">‹</span>
      <b class="num" style="min-width:70px;text-align:center">${tx.month}</b>
      <span class="pill btn" id="txNext">›</span>
      <span class="meta">расход: <b class="down">${fmt(tx.expense)} €</b> · доход: <b class="up">${fmt(tx.income)} €</b> · итого: ${fmt(tx.income - tx.expense)} €</span>
      <span class="pill btn" id="monefyToggle" style="margin-left:auto">⤓ Monefy CSV</span>
    </div>
    ${budgetBar}
    ${showMonefy ? `
      <div style="padding:8px 0">
        <textarea id="monefyCsv" rows="6" style="width:100%;border:1px solid var(--line);border-radius:8px;padding:8px;font:12px var(--mono)" placeholder="Вставь CSV-экспорт Monefy (с заголовком). Разделитель ; или , — определю. Минус = расход."></textarea>
        <div class="btnrow" style="margin-top:6px"><span class="pill btn ok" id="monefyGo">Импортировать</span></div>
      </div>` : ''}
    ${tx.categories.length ? `<div style="padding:8px 0 4px">` + tx.categories.slice(0, 6).map(([cat, sum]) => `
      <div class="kv"><span>${fesc(cat)}</span><b class="num">${fmt(sum)} €</b></div>
      <div class="bar" style="margin:2px 0 6px"><i style="width:${sum / maxCat * 100}%"></i></div>`).join('') + '</div>' : ''}
    ${tx.rows.slice(0, 15).map(t => finIsMobile() ? fRow({
        cls: t.direction === 'income' ? 'up' : '',
        lead: `<span class="pill ${t.direction === 'income' ? 'ok' : 'p1'}">${t.direction === 'income' ? 'доход' : 'расход'}</span>`,
        name: `<span class="ed" data-fe="tx:${t.id}:note:text">${fesc(t.note) || '—'}</span>`,
        amount: `<span class="ed ${t.direction === 'income' ? 'up' : 'down'}" data-fe="tx:${t.id}:amount:num">${fmt(t.amount)} ${fesc(t.currency)}</span>`,
        meta: `<span class="meta num">${t.date.slice(5)}</span>`
          + `<span class="ed meta" data-fe="tx:${t.id}:category:text">${fesc(t.category)}</span>`
          + (t.source === 'monefy' ? '<span class="meta">monefy</span>' : ''),
        actions: `<span class="rowbtn del" data-findel="tx:${t.id}">✕</span>`,
      }) : `
      <div class="task">
        <span class="meta num">${t.date.slice(5)}</span>
        <span class="pill ${t.direction === 'income' ? 'ok' : 'p1'}">${t.direction === 'income' ? 'доход' : 'расход'}</span>
        <span class="ed meta" data-fe="tx:${t.id}:category:text">${fesc(t.category)}</span>
        <span class="t ed" data-fe="tx:${t.id}:note:text">${fesc(t.note) || '—'}</span>
        ${t.source === 'monefy' ? '<span class="meta">monefy</span>' : ''}
        <span class="ed num" data-fe="tx:${t.id}:amount:num">${fmt(t.amount)} ${fesc(t.currency)}</span>
        <span class="rowbtn del" data-findel="tx:${t.id}">✕</span>
      </div>`).join('')}
    ${tx.rows.length > 15 ? `<div class="empty">…и ещё ${tx.rows.length - 15} за месяц</div>` : ''}
    <div class="task finadd">
      <input id="txDate" value="${finIso(new Date())}" style="width:105px">
      <select id="txDir"><option value="expense">расход</option><option value="income">доход</option></select>
      <input id="txCat" placeholder="категория" style="width:120px">
      <input id="txAmount" placeholder="сумма" style="width:90px">
      <input id="txNote" placeholder="заметка">
      <span class="pill btn ok" id="txAdd">＋</span>
    </div>
  </div>`;
}

// Долги: ручные (мои и мне) + плановые из портфеля (значок 🤝)
function secDebts(d) {
  return `
  <div class="sec">Долги</div>
  <div class="card">
    ${d.debts.map(x => finIsMobile() ? fRow({
        lead: `<span class="pill ${x.direction === 'i_owe' ? 'p0' : 'ok'}" data-ddir="${x.id}:${x.direction}" title="клик — поменять направление" style="cursor:pointer">${x.direction === 'i_owe' ? 'я должен' : 'мне должны'}</span>`,
        name: `<span class="ed" data-fe="debts:${x.id}:name:text">${fesc(x.name)}</span>`,
        amount: `<span class="ed" data-fe="debts:${x.id}:amount:num">${fmt(x.amount)}</span>`,
        meta: `<span class="ed meta ${x.overdue_days > 0 ? 'amber' : ''}" data-fe="debts:${x.id}:due_date:date">${x.due_date ?? '+срок'}${x.overdue_days > 0 ? ` · просрочен ${x.overdue_days} дн ⚠` : ''}</span>`
          + `<span class="pill btn" data-dcur="${x.id}:${x.currency}" title="сменить валюту">${fesc(x.currency)}</span>`,
        actions: `<span class="rowbtn del" data-findel="debts:${x.id}">✕</span>`,
      }) : `
      <div class="task">
        <span class="pill ${x.direction === 'i_owe' ? 'p0' : 'ok'}" data-ddir="${x.id}:${x.direction}" title="клик — поменять направление" style="cursor:pointer">${x.direction === 'i_owe' ? 'я должен' : 'мне должны'}</span>
        <span class="t ed" data-fe="debts:${x.id}:name:text">${fesc(x.name)}</span>
        <span class="ed meta ${x.overdue_days > 0 ? 'amber' : ''}" data-fe="debts:${x.id}:due_date:date">${x.due_date ?? '+срок'}${x.overdue_days > 0 ? ` · просрочен ${x.overdue_days} дн ⚠` : ''}</span>
        <span class="pill btn" data-dcur="${x.id}:${x.currency}" title="сменить валюту">${fesc(x.currency)}</span>
        <span class="ed num" data-fe="debts:${x.id}:amount:num">${fmt(x.amount)}</span>
        <span class="rowbtn del" data-findel="debts:${x.id}">✕</span>
      </div>`).join('') || '<div class="empty">долгов нет</div>'}
    <div class="task finadd">
      <select id="dbDir"><option value="owed_to_me">мне должны</option><option value="i_owe">я должен</option></select>
      <input id="dbName" placeholder="кто и за что">
      <input id="dbAmount" placeholder="сумма" style="width:90px">
      <select id="dbCur"><option>€</option><option>$</option></select>
      <input id="dbDate" type="date" title="срок" style="width:150px">
      <span class="pill btn ok" id="dbAdd">＋</span>
    </div>
    ${d.loans.length ? `<div class="meta" style="margin:10px 0 4px">ПЛАНОВЫЕ · ЗАЙМЫ ИЗ ПОРТФЕЛЯ (🤝)</div>` +
      d.loans.map(l => `
      <div class="task">
        <span class="pill p2">🤝</span>
        <span class="t ed" data-fe="items:${l.id}:name:text">${fesc(l.name)}</span>
        <span class="meta">${fesc(l.path)}</span>
        <span class="ed meta ${l.overdue_days > 0 ? 'amber' : ''}" data-fe="items:${l.id}:loan_due:date">${l.loan_due ?? '+дата возврата'}${l.overdue_days > 0 ? ` · просрочен ${l.overdue_days} дн ⚠` : ''}</span>
        <span class="num">${l.value != null ? fmt(l.value) : '—'} ${fesc(l.currency)}</span>
        <span class="pill btn" data-loanflag="${l.id}:1" title="вернули — убрать значок">✓ закрыт</span>
      </div>`).join('') : ''}
  </div>`;
}

function secPlans(d) {
  return `
  <div class="sec">План шагов · покупки / продажи</div>
  <div class="card">
    ${d.steps.map(st => {
      const [kl, kc] = STEPK[st.kind] ?? [st.kind, ''];
      const done = st.status === 'done';
      const stepAct = (st.task_id
        ? `<span class="pill ok btn" data-stepopen="${st.task_id}" title="открыть задачу">↗ в задачах</span>`
        : !done ? `<span class="pill btn" data-steptask="${st.id}" title="внести в общий список задач">→ задача</span>` : '');
      if (finIsMobile()) return fRow({
        cls: done ? 'done' : '',
        lead: `<span class="cb ${done ? 'done' : ''}" data-stepdone="${st.id}"></span><span class="pill ${kc}">${kl}</span>`,
        name: `<span class="${done ? 'done' : 'ed'}" ${done ? '' : `data-fe="steps:${st.id}:title:text"`}>${fesc(st.title)}</span>`,
        amount: `<span class="ed" data-fe="steps:${st.id}:amount:num">${st.amount ? fmt(st.amount) : '+сумма'}</span>`,
        meta: `<span class="ed meta" data-fe="steps:${st.id}:planned_date:date">${st.planned_date ?? '+дата'}</span>`
          + `<span class="ed meta" data-fe="steps:${st.id}:condition:text">${st.condition ? 'усл: ' + fesc(st.condition) : '+условие'}</span>`,
        actions: stepAct + `<span class="rowbtn del" data-findel="steps:${st.id}">✕</span>`,
      });
      return `<div class="task">
        <span class="cb ${done ? 'done' : ''}" data-stepdone="${st.id}"></span>
        <span class="pill ${kc}">${kl}</span>
        <span class="t ${done ? 'done' : 'ed'}" ${done ? '' : `data-fe="steps:${st.id}:title:text"`}>${fesc(st.title)}</span>
        <span class="ed meta num" data-fe="steps:${st.id}:amount:num">${st.amount ? fmt(st.amount) : '+сумма'}</span>
        <span class="ed meta" data-fe="steps:${st.id}:planned_date:date">${st.planned_date ?? '+дата'}</span>
        <span class="ed meta" data-fe="steps:${st.id}:condition:text">${st.condition ? 'усл: ' + fesc(st.condition) : '+условие'}</span>
        ${st.task_id
          ? `<span class="pill ok btn" data-stepopen="${st.task_id}" title="открыть задачу">↗ в задачах</span>`
          : !done ? `<span class="pill btn" data-steptask="${st.id}" title="внести в общий список задач">→ задача</span>` : ''}
        <span class="rowbtn del" data-findel="steps:${st.id}">✕</span>
      </div>`;
    }).join('') || '<div class="empty">шагов нет</div>'}
    <div class="task finadd">
      <select id="stKind"><option value="buy">купить</option><option value="sell">продать</option><option value="transfer">перевод</option></select>
      <input id="stTitle" placeholder="что и зачем">
      <span class="pill btn ok" id="stAdd">＋</span>
    </div>
  </div>

  <div class="sec">Обязательства, подписки и плановые траты · «✓» = оплачено</div>
  <div class="card">
    ${(() => {
      const rate = (d.rates.find(r => r.symbol === 'EURUSD')?.price) || 1.08;
      const toEur = o => (o.currency === '$' ? (o.amount || 0) / rate : (o.amount || 0));   // суммы в €
      const bp = { monthly: 0, yearly: 0, once: 0 };
      (d.obligations || []).forEach(o => { if (bp[o.period] != null) bp[o.period] += toEur(o); });
      const yr = bp.monthly * 12 + bp.yearly + bp.once;   // всего затрат за год
      return `<div class="task" style="flex-wrap:wrap;gap:14px;border-bottom:1px solid var(--line);padding-bottom:9px;margin-bottom:7px">
        <span class="meta">в мес: <b class="num">${finHide ? '—' : fmt(bp.monthly) + ' €'}</b></span>
        <span class="meta">в год: <b class="num">${finHide ? '—' : fmt(bp.yearly) + ' €'}</b></span>
        <span class="meta">разовые: <b class="num">${finHide ? '—' : fmt(bp.once) + ' €'}</b></span>
        <span class="meta" style="margin-left:auto">всего затрат за год: <b class="num">${finHide ? '—' : fmt(yr) + ' €'}</b></span>
      </div>`;
    })()}
    ${d.obligations.map(o => finIsMobile() ? fRow({
        lead: `<span class="pill ${o.kind === 'subscription' ? 'p2' : 'p1'}">${o.kind === 'subscription' ? 'подписка' : o.period === 'once' ? 'трата' : 'пассив'}</span>`,
        name: `<span class="ed" data-fe="obligations:${o.id}:name:text">${fesc(o.name)}</span>`,
        amount: `<span class="ed" data-fe="obligations:${o.id}:amount:num">${fmt(o.amount)} ${fesc(o.currency)}</span>`,
        meta: `<span class="meta">/ ${PERIOD[o.period]}</span>`
          + (o.next_date
            ? `<span class="ed meta ${o.days_left <= o.remind_days ? 'amber' : ''}" data-obldt="${o.id}" data-obltime="${o.due_time ?? ''}">${o.next_date}${o.due_time ? ' · ' + o.due_time : ''} (${o.days_left} дн.)</span>`
            : `<span class="ed meta" data-obldt="${o.id}" data-obltime="">+дата</span>`),
        actions: (o.next_date ? `<span class="pill btn ok" data-oblpay="${o.id}">✓</span>` : '')
          + `<span class="rowbtn del" data-findel="obligations:${o.id}">✕</span>`,
      }) : `
      <div class="task">
        <span class="pill ${o.kind === 'subscription' ? 'p2' : 'p1'}">${o.kind === 'subscription' ? 'подписка' : o.period === 'once' ? 'трата' : 'пассив'}</span>
        <span class="t ed" data-fe="obligations:${o.id}:name:text">${fesc(o.name)}</span>
        <span class="ed meta num" data-fe="obligations:${o.id}:amount:num">${fmt(o.amount)} ${fesc(o.currency)} / ${PERIOD[o.period]}</span>
        ${o.next_date
          ? `<span class="ed meta ${o.days_left <= o.remind_days ? 'amber' : ''}" data-obldt="${o.id}" data-obltime="${o.due_time ?? ''}" title="дата и время — клик">${o.next_date}${o.due_time ? ' · ' + o.due_time : ''} (${o.days_left} дн.)</span>
             <span class="pill btn ok" data-oblpay="${o.id}">✓</span>`
          : `<span class="ed meta" data-obldt="${o.id}" data-obltime="" title="дата и время — клик">+дата</span>`}
        <span class="rowbtn del" data-findel="obligations:${o.id}">✕</span>
      </div>`).join('')}
    <div class="task finadd">
      <select id="obKind"><option value="liability">пассив</option><option value="subscription">подписка</option></select>
      <input id="obName" placeholder="название (кредит, аренда, разовая крупная трата…)">
      <input id="obAmount" placeholder="сумма" style="width:90px">
      <select id="obPeriod"><option value="monthly">мес</option><option value="yearly">год</option><option value="once">разово</option></select>
      <input id="obDate" type="date" title="след. дата" style="width:150px">
      <span class="pill btn ok" id="obAdd">＋</span>
    </div>
    <div class="empty">Крупная плановая трата = «разово» с датой: попадёт в календарь и в радар задач.</div>
  </div>`;
}

// Имущество: карточки по категориям, внутри — регламент (правила = обязательства)
function secProps(d) {
  const cats = {};
  for (const p of d.properties) (cats[p.category] ??= []).push(p);
  const CAT_ICO = { 'авто': '🚗', 'недвижимость': '🏠', 'техника': '💻', 'прочее': '📦' };
  return `
  <div class="sec">Имущество · регламенты по категориям · «✓» = сделано, дата сдвинется</div>
  ${Object.entries(cats).map(([cat, props]) => `
    <div class="meta" style="margin:8px 0 4px">${CAT_ICO[cat] ?? '📦'} ${fesc(cat).toUpperCase()}</div>
    <div class="fingrid" style="grid-template-columns:1fr 1fr">
      ${props.map(p => `
      <div class="card">
        <div class="task" style="border-bottom:1px solid var(--line)">
          <span class="t ed" data-fe="properties:${p.id}:name:text" style="font-weight:600">${fesc(p.name)}</span>
          <span class="rowbtn del" data-propdel="${p.id}">✕</span>
        </div>
        ${p.rules.map(r => `
          <div class="task">
            <span class="t">${fesc(r.name.replace(p.name + ': ', ''))}</span>
            <span class="meta num">${fmt(r.amount)} ${fesc(r.currency)} / ${PERIOD[r.period]}</span>
            ${r.next_date
              ? `<span class="meta ${r.days_left <= r.remind_days ? 'amber' : ''}">${r.next_date} (${r.days_left} дн)</span>
                 <span class="pill btn ok" data-oblpay="${r.id}">✓</span>`
              : '<span class="meta">—</span>'}
            <span class="rowbtn del" data-findel="obligations:${r.id}">✕</span>
          </div>`).join('') || '<div class="empty">регламента нет</div>'}
        <div class="task finadd">
          <input data-rulename="${p.id}" placeholder="ТО, страховка, счётчики…">
          <input data-ruleamount="${p.id}" placeholder="€" style="width:60px">
          <select data-ruleperiod="${p.id}"><option value="yearly">год</option><option value="monthly">мес</option><option value="once">разово</option></select>
          <input data-ruledate="${p.id}" type="date" title="дата" style="width:150px">
          <span class="pill btn ok" data-ruleadd="${p.id}">＋</span>
        </div>
      </div>`).join('')}
    </div>`).join('') || '<div class="card"><div class="empty">объектов нет</div></div>'}
  <div class="card"><div class="task finadd">
    <input id="prName" placeholder="новый объект: X5, квартира №2, MacBook…">
    <select id="prCat"><option>авто</option><option>недвижимость</option><option>техника</option><option>прочее</option></select>
    <span class="pill btn ok" id="prAdd">＋</span>
  </div>
  <div class="empty">Регламентные даты попадают в календарь и радар задач как платежи.</div></div>`;
}

function secFire(d, s) {
  return `
  <div class="sec">FIRE · Макро</div>
  <div class="fingrid" style="grid-template-columns:1fr 1fr">
    <div class="card">
      <div class="meta">FIRE · ЦЕЛЕВОЙ КАПИТАЛ</div>
      ${d.fire.target ? `
        <div class="bignum">${d.fire.progressPct.toFixed(1)}%</div>
        <div class="bar"><i style="width:${d.fire.progressPct}%"></i></div>
        <div class="kv" style="margin-top:6px">Цель <b class="ed num" data-fireset="fire_target">${fmt(d.fire.target)} €</b></div>
        <div class="kv">Доходность, %/год <b class="ed num" data-fireset="fire_return_pct">${d.fire.annual}</b></div>
        <div class="kv">Пополнение, €/мес <b class="ed num" data-fireset="fire_monthly_savings">${fmt(d.fire.monthly)}</b></div>
        <div class="meta" style="margin-top:6px">${d.fire.months != null
          ? (d.fire.months === 0 ? '🎉 цель достигнута' : `прогноз: ~${d.fire.reachedYear} год (через ${Math.round(d.fire.months / 12 * 10) / 10} лет)`)
          : 'при таких параметрах цель не достигается'}</div>`
      : `<div class="muted" style="margin:8px 0">Задай цель — посчитаю прогресс от портфеля (${fmt(s.portfolioTotal)} €) и год достижения.</div>
        <div class="btnrow"><span class="pill btn ok ed" data-fireset="fire_target">задать цель, €</span></div>`}
    </div>
    <div class="card">
      <div class="meta">МАКРО · МОЙ ТЕЗИС</div>
      ${d.macro.length ? `
        <div style="font-weight:600;margin:6px 0">${fesc(d.macro[0].phase)} <span class="meta">· ${d.macro[0].date}</span></div>
        <div style="font-size:12.5px;margin-bottom:8px">${fesc(d.macro[0].thesis)}</div>`
      : '<div class="muted" style="margin:8px 0">В какой фазе цикла мы? Запиши тезис — останется в истории.</div>'}
      <div class="task finadd">
        <select id="mcPhase"><option>рост</option><option>пик</option><option>сжатие</option><option>дно</option></select>
        <input id="mcThesis" placeholder="тезис: что жду и что делаю…">
        <span class="pill btn ok" id="mcAdd">＋</span>
      </div>
      ${d.macro.length > 1 ? `<div class="meta" style="margin-top:6px">история:</div>` +
        d.macro.slice(1, 4).map(mn => `<div class="kv"><span>${mn.date} · ${fesc(mn.phase)} — ${fesc(mn.thesis.slice(0, 60))}</span><span class="rowbtn del" style="opacity:1" data-mcdel="${mn.id}">✕</span></div>`).join('') : ''}

      <div class="meta" style="margin-top:12px">🎯 ПРОГНОЗЫ · ${d.forecasts.calibration != null
        ? `калибровка ${d.forecasts.calibration.toFixed(0)}% · проверено ${d.forecasts.resolvedCount}`
        : 'проверенных пока нет'}</div>
      ${d.forecasts.rows.slice(0, 6).map(f => `
        <div class="task" style="${f.outcome != null ? 'opacity:.55' : ''}">
          <span class="pill ${f.outcome === 1 ? 'ok' : f.outcome === 0 ? 'p0' : 'p2'}">${f.outcome === 1 ? '✓ сбылось' : f.outcome === 0 ? '✗ нет' : f.confidence + '%'}</span>
          <span class="t" style="font-size:12.5px">${fesc(f.statement)}</span>
          ${f.due_date ? `<span class="meta">${f.due_date}</span>` : ''}
          ${f.outcome == null ? `
            <span class="pill btn ok" data-fcres="${f.id}:1" title="сбылось">✓</span>
            <span class="pill btn" data-fcres="${f.id}:0" title="не сбылось">✗</span>` : ''}
          <span class="rowbtn del" data-fcdel="${f.id}">✕</span>
        </div>`).join('')}
      <div class="task finadd">
        <input id="fcText" placeholder="прогноз: «коррекция S&P до конца года»…">
        <input id="fcConf" placeholder="%" style="width:55px">
        <input id="fcDue" type="date" title="срок" style="width:150px">
        <span class="pill btn ok" id="fcAdd">＋</span>
      </div>
    </div>
  </div>`;
}

function renderFin() {
  const d = finData, s = d.summary;
  const hide = finHide;
  // точечное раскрытие: кнопка в свёрнутой карточке открывает только её раздел
  const hidden = key => hide && !finShown.has(key);
  const accStr = hidden('acc') ? '—'
    : Object.entries(s.accountsByCurrency).map(([c, v]) => `${fmt(v)} ${c}`).join(' · ') || '—';
  const head = `
  <div class="ratesbar">
    ${d.rates.map(r => `<span class="ratepill">
      <b>${fesc(r.label)}</b>
      <span class="ed num" data-rate="${fesc(r.symbol)}" title="клик — ввести вручную">${r.price != null ? (RATE_FMT[r.symbol] ?? fmt)(r.price) : '—'}</span>
      ${r.change_pct != null ? `<span class="${r.change_pct >= 0 ? 'up' : 'down'}">${r.change_pct >= 0 ? '▲' : '▼'}${Math.abs(r.change_pct).toFixed(2)}%</span>` : ''}
    </span>`).join('')}
    <span class="pill btn" id="ratesRefresh">↻ обновить</span>
    <span class="pill btn" id="finEye" style="margin-left:auto" title="${hide ? 'показать значения' : 'скрыть значения'}">${hide ? '<s>👁</s> показать' : '👁 скрыть'}</span>
    <span class="meta">${d.rates[0]?.updated_at ? 'обн. ' + d.rates[0].updated_at.slice(0, 16).replace('T', ' ') : 'курсы не загружались'}</span>
  </div>
  <div class="fingrid">
    <div class="card"><div class="meta">СЧЕТА</div>
      <div class="bignum" style="font-size:16px">${accStr}</div>
      <div class="meta">${d.accounts.length} счетов</div></div>
    <div class="card"><div class="meta">ПОРТФЕЛЬ · ФАКТ</div>
      <div class="bignum">${hidden('port') ? '—' : `${fmtE(s.portfolioTotal)} <span style="font-size:14px;color:var(--muted)">· ${fmt(s.portfolioTotalUsd)} $</span>`}</div>
      <div class="meta">${hidden('port') ? 'значения скрыты — 👁 наверху'
        : (s.growth ? `прирост: ${s.growth.abs >= 0 ? '+' : ''}${fmt(s.growth.abs)} € (${s.growth.pct.toFixed(1)}%)` : '')}</div></div>
    ${(() => {
      const usd = (d.portfolio || []).reduce((a, b) => a + (b.usdPart || 0), 0);   // все позиции в $
      const eur = (d.portfolio || []).reduce((a, b) => a + (b.eurPart || 0), 0);   // все позиции в €
      const tot = s.portfolioTotal || 0, pe = tot > 0 ? Math.round(eur / tot * 100) : 0;   // €-часть от портфеля; $-часть = остаток
      return `<div class="card"><div class="meta">ПОЗИЦИИ · USD / EUR</div>
      <div class="bignum">${hidden('port') ? '—' : `${fmt(usd)} $ <span style="font-size:14px;color:var(--muted)">· ${fmt(eur)} €</span>`}</div>
      <div class="meta">${hidden('port') ? 'значения скрыты — 👁 наверху' : `$ ${tot > 0 ? 100 - pe : 0}% · € ${pe}% от портфеля`}</div></div>`;
    })()}
  </div>
  <div class="viewtabs">
    ${[['all', 'Всё'], ['port', 'Портфель'], ['acc', 'Счета'], ['flow', 'Расходы'], ['debts', 'Долги'], ['plans', 'Планы'], ['prop', 'Имущество'], ['fire', 'FIRE·Макро']]
      .map(([k, l]) => `<span class="pill btn ${finSection === k ? 'ok' : ''}" data-fsec="${k}">${l}</span>`).join(' ')}
  </div>`;

  // в скрытом режиме портфель и счета свёрнуты целиком; кнопка открывает только свой раздел
  const veiled = (name, key) => `
  <div class="sec">${name}</div>
  <div class="card"><div class="task" style="border:0">
    <span class="t muted">свёрнуто — значения скрыты</span>
    <span class="pill btn ok" data-fshow="${key}"><s>👁</s> показать ${name.toLowerCase()}</span>
  </div></div>`;

  const show = k => finSection === 'all' || finSection === k;
  document.getElementById('screen-fin').innerHTML = head
    + (show('port') ? (hidden('port') ? veiled('Портфель', 'port') : secPortfolio(d, s)) : '')
    + (show('port') ? secIncome(d, s) : '')
    + (show('acc') ? (hidden('acc') ? veiled('Счета', 'acc') : secAccounts(d)) : '')
    + (show('flow') ? renderBudget(d.budgetItems, d.rates) : '')
    + (show('debts') ? secDebts(d) : '')
    + (show('plans') ? secPlans(d) : '')
    + (show('prop') ? secProps(d) : '')
    + (show('fire') ? (hidden('fire') ? veiled('FIRE · Макро', 'fire') : secFire(d, s)) : '')
    + `<div class="footer-hint">Бивалютно: € и $ по курсу EURUSD. ⚡ — автоцена «количество × курс» (BTC, золото, SCHD/IVV/VHT). Ввод понимает «100k», «1.2m», даты — и 01.07.2026. Платежи и траты видны в календаре и радаре задач.</div>`;
  bindFin();
}

function inlineVal(el, type, onSave) {
  const input = document.createElement('input');
  input.className = 'inlineedit';
  input.style.maxWidth = type === 'text' ? '220px' : (type === 'date' ? '150px' : '120px');
  input.placeholder = el.textContent.trim();
  if (type === 'text') input.value = el.textContent.trim().replace(/^(усл: |\+.*)/, '');
  if (type === 'date') { input.type = 'date'; const c = el.textContent.trim(); if (/^\d{4}-\d{2}-\d{2}$/.test(c)) input.value = c; }
  el.replaceWith(input);
  input.focus(); if (type === 'text') input.select();
  let done = false;
  const save = async () => {
    if (done) return; done = true;
    const raw = input.value.trim();
    if (raw) {
      let v = raw;
      if (type === 'num') { v = parseNum(raw); if (v == null) { window.loadFin(); return; } }
      if (type === 'date') {
        let mm;
        if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) v = raw;
        else if ((mm = raw.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})$/)))
          v = `${mm[3]}-${mm[2].padStart(2, '0')}-${mm[1].padStart(2, '0')}`;
        else { alert('Дата: 2026-07-01 или 01.07.2026'); window.loadFin(); return; }
      }
      await onSave(v);
    }
    window.loadFin();
  };
  input.addEventListener('click', ev => ev.stopPropagation());
  input.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') save();
    if (ev.key === 'Escape') { done = true; window.loadFin(); }
  });
  input.addEventListener('blur', save);
}

function bindFin() {
  const $ = id => document.getElementById(id);
  document.querySelectorAll('[data-fsec]').forEach(el =>
    el.addEventListener('click', () => { finSection = el.dataset.fsec; renderFin(); }));
  document.querySelectorAll('[data-fe]').forEach(el =>
    el.addEventListener('click', () => {
      const [ent, id, field, type] = el.dataset.fe.split(':');
      // цель хранится в одном из двух полей: заполненное и есть закреплённое, второе гасим
      const twin = ent === 'tgt' && field === 'target_pct' ? 'target_value'
        : ent === 'tgt' && field === 'target_value' ? 'target_pct' : null;
      inlineVal(el, type, v => finApi.patch(ent, +id, twin ? { [field]: v, [twin]: null } : { [field]: v }));
    }));
  document.querySelectorAll('[data-rate]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', v => finApi.rateSet(el.dataset.rate, v))));
  $('finEye')?.addEventListener('click', () => {
    finHide = !finHide;
    finShown.clear();   // верхний глаз управляет всем сразу; на диск выбор не пишем
    renderFin();
  });
  document.querySelectorAll('[data-fshow]').forEach(el =>
    el.addEventListener('click', () => { finShown.add(el.dataset.fshow); renderFin(); }));
  document.querySelectorAll('[data-pfold]').forEach(el =>
    el.addEventListener('click', e => {
      e.stopPropagation();
      const id = +el.dataset.pfold;
      portFold.has(id) ? portFold.delete(id) : portFold.add(id);
      savePortFold(); renderFin();
    }));
  // DnD портфеля: середина — вложить, края — поставить выше/ниже
  let pDrag = null;
  const pClear = () => document.querySelectorAll('.porttable tr.dropinto,.porttable tr.dropbefore,.porttable tr.dropafter')
    .forEach(x => x.classList.remove('dropinto', 'dropbefore', 'dropafter'));
  document.querySelectorAll('.porttable tr[data-pid]').forEach(tr => {
    tr.addEventListener('dragstart', () => { pDrag = +tr.dataset.pid; });
    tr.addEventListener('dragover', e => {
      if (pDrag == null || +tr.dataset.pid === pDrag) return;
      e.preventDefault();
      const r = tr.getBoundingClientRect();
      const y = (e.clientY - r.top) / r.height;
      tr.classList.remove('dropinto', 'dropbefore', 'dropafter');
      tr.classList.add(y < 0.3 ? 'dropbefore' : y > 0.7 ? 'dropafter' : 'dropinto');
    });
    tr.addEventListener('dragleave', () => tr.classList.remove('dropinto', 'dropbefore', 'dropafter'));
    tr.addEventListener('drop', async e => {
      e.preventDefault();
      const zone = tr.classList.contains('dropbefore') ? 'before'
        : tr.classList.contains('dropafter') ? 'after' : 'into';
      pClear();
      if (pDrag == null) return;
      const ent = 'tgt';   // дерево одно
      const url = zone === 'into'
        ? [`/api/fin/${ent}/${pDrag}/move`, { parent_id: +tr.dataset.pid }]
        : [`/api/fin/${ent}/${pDrag}/reorder`, { ref_id: +tr.dataset.pid, where: zone }];
      const r = await fetch(url[0], { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(url[1]) }).then(x => x.json());
      if (r.error) alert(r.error);
      pDrag = null;
      window.loadFin();
    });
    tr.addEventListener('dragend', pClear);
  });
  // пассивный доход: период/валюта/добавление
  document.querySelectorAll('[data-incper]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.incper.split(':');
      const next = { monthly: 'yearly', yearly: 'once', once: 'monthly' }[cur];
      await finApi.patch('income', +id, { period: next });
      window.loadFin();
    }));
  document.querySelectorAll('[data-inccur]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.inccur.split(':');
      await finApi.patch('income', +id, { currency: cur === '€' ? '$' : '€' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-incrper]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, rp] = el.dataset.incrper.split(':');
      await finApi.patch('income', +id, { rate_period: rp === 'monthly' ? 'yearly' : 'monthly' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-inctype]').forEach(el =>
    el.addEventListener('click', async () => {
      const cur = el.textContent.replace('＋ тип', '').trim();
      const next = ASSET_TYPES[(ASSET_TYPES.indexOf(cur) + 1) % ASSET_TYPES.length];
      await finApi.patch('income', +el.dataset.inctype, { asset_type: next });
      window.loadFin();
    }));
  $('incAdd')?.addEventListener('click', async () => {
    const name = $('incName').value.trim();
    if (!name) return;
    const principal = parseNum($('incPrincipal').value) ?? 0;
    const rate = parseNum($('incRate').value) ?? 0;
    await finApi.add('income', { name, asset_type: $('incType').value,
      principal, rate, rate_period: $('incRatePer').value,
      currency: $('incCur').value, period: 'monthly', amount: 0 });
    window.loadFin();
  });
  $('pfoldAll')?.addEventListener('click', () => {
    if (portFold.size) portFold.clear();
    else {
      const walk = it => { if (it.children.length) { portFold.add(it.id); it.children.forEach(walk); } };
      finData.portfolio.forEach(walk);
    }
    savePortFold(); renderFin();
  });
  document.querySelectorAll('[data-fcur]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.fcur.split(':');
      const ent = 'tgt';   // дерево одно
      await finApi.patch(ent, +id, { currency: cur === '€' ? '$' : '€' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-fadd]').forEach(el =>
    el.addEventListener('click', async () => {
      const [kind, pid] = el.dataset.fadd.split(':');
      // блок верхнего уровня берём из поля, вложенные — промптом; parent_id пустой → null (корень), а не 0
      const name = kind === 'block' ? document.getElementById('fact_block')?.value.trim()
        : prompt(kind === 'section' ? 'Название раздела:' : 'Название актива:');
      if (name?.trim()) { await finApi.add('items', { parent_id: pid ? +pid : null, name: name.trim(), kind }); window.loadFin(); }
    }));
  document.querySelectorAll('[data-budadd]').forEach(el =>
    el.addEventListener('click', async () => {
      const dir = el.dataset.budadd;
      if (dir === 'income') {
        const amt = parseNum(document.getElementById('bud_inc_amt')?.value);
        if (amt == null) return;
        await finApi.add('budget', {
          name: document.getElementById('bud_inc_name')?.value.trim() || 'доход',
          amount: amt, direction: 'income',
          currency: document.getElementById('bud_inc_cur')?.value || '€',
          month: document.getElementById('bud_inc_month')?.value.trim() || '',
        });
      } else {
        const name = document.getElementById('bud_exp_name')?.value.trim();
        if (!name) return;
        await finApi.add('budget', {
          name, amount: parseNum(document.getElementById('bud_exp_amt')?.value) ?? 0,
          direction: 'expense', currency: document.getElementById('bud_exp_cur')?.value || '€',
        });
      }
      window.loadFin();
    }));
  document.querySelectorAll('[data-tgtadd]').forEach(el =>
    el.addEventListener('click', async () => {
      const [kind, pid] = el.dataset.tgtadd.split(':');
      const name = kind === 'block' ? document.getElementById('tgt_block')?.value.trim()
        : prompt(kind === 'section' ? 'Название раздела:' : 'Название актива:');
      if (!name || !name.trim()) return;
      await finApi.add('tgt', { kind, parent_id: pid ? +pid : null, name: name.trim() });
      window.loadFin();
    }));
  // «↦ переложить» раскрывает форму строкой под позицией; повторный клик закрывает
  // наведение связывает сектор бублика и строку мониторинга — цвет перестаёт быть единственной нитью
  document.querySelectorAll('[data-cat]').forEach(el => {
    const mark = on => document.querySelectorAll('[data-cat]').forEach(x => {
      if (x.dataset.cat === el.dataset.cat) x.classList.toggle('hi', on);
    });
    el.addEventListener('mouseenter', () => mark(true));
    el.addEventListener('mouseleave', () => mark(false));
  });
  document.querySelectorAll('[data-tgtmove]').forEach(el =>
    el.addEventListener('click', () => {
      const id = +el.dataset.tgtmove;
      tgtMove = tgtMove?.from === id ? null : { from: id, to: null, amount: null };
      renderFin();
    }));
  const mvRerender = (focusAmt) => {
    renderFin();
    if (!focusAmt) return;
    const a = document.getElementById('tgtMoveAmt');
    if (a) { a.focus(); a.setSelectionRange(a.value.length, a.value.length); }   // перерисовка не должна выбивать курсор
  };
  document.getElementById('tgtMoveTo')?.addEventListener('change', e => { tgtMove.to = +e.target.value; renderFin(); });
  document.getElementById('tgtMoveAmt')?.addEventListener('input', e => { tgtMove.amount = parseNum(e.target.value); mvRerender(true); });
  document.querySelectorAll('[data-mvq]').forEach(el =>
    el.addEventListener('click', () => { tgtMove.amount = +el.dataset.mvq; mvRerender(true); }));
  document.getElementById('tgtMoveCancel')?.addEventListener('click', () => { tgtMove = null; renderFin(); });
  document.getElementById('tgtMoveGo')?.addEventListener('click', async () => {
    const to = tgtMove.to ?? +document.getElementById('tgtMoveTo')?.value;
    if (!to || !(tgtMove.amount > 0)) return;
    await finApi.add('move', { from_id: tgtMove.from, to_id: to, amount: tgtMove.amount });
    tgtMove = null;
    window.loadFin();
  });
  document.querySelectorAll('[data-movedel]').forEach(el =>
    el.addEventListener('click', async () => { await finApi.del('move', +el.dataset.movedel); window.loadFin(); }));
  document.querySelectorAll('[data-findel]').forEach(el =>
    el.addEventListener('click', async () => {
      const [ent, id] = el.dataset.findel.split(':');
      if (confirm('Удалить запись (с вложенными, если есть)?')) { await finApi.del(ent, +id); window.loadFin(); }
    }));
  document.querySelectorAll('[data-stepdone]').forEach(el =>
    el.addEventListener('click', async () => {
      const st = finData.steps.find(x => x.id === +el.dataset.stepdone);
      await finApi.patch('steps', st.id, { status: st.status === 'done' ? 'planned' : 'done' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-steptask]').forEach(el =>
    el.addEventListener('click', async () => {
      const r = await finApi.toTask(+el.dataset.steptask);
      if (r.error) alert(r.error);
      window.loadFin();
    }));
  document.querySelectorAll('[data-stepopen]').forEach(el =>
    el.addEventListener('click', () => window.openNode(+el.dataset.stepopen)));
  document.querySelectorAll('[data-oblpay]').forEach(el =>
    el.addEventListener('click', async () => { await finApi.pay(+el.dataset.oblpay); window.loadFin(); }));
  document.querySelectorAll('[data-obldt]').forEach(el =>
    el.addEventListener('click', async e => {   // дата + время платежа (как срок задачи)
      e.stopPropagation();
      const cur = (el.textContent.trim().match(/^\d{4}-\d{2}-\d{2}/) || [null])[0];
      const curTime = /^\d{2}:\d{2}$/.test(el.dataset.obltime || '') ? el.dataset.obltime : '';
      const v = await window.pickDate(cur, { title: 'Дата и время платежа', withTime: true, time: curTime });
      if (v === undefined) return;
      await fetch('/api/fin/obligations/' + el.dataset.obldt, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ next_date: v.date || null, due_time: v.date ? (v.time || null) : null }) });
      window.loadFin();
    }));
  // займы, типы, автоцена
  document.querySelectorAll('[data-loanflag]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.loanflag.split(':');
      await finApi.patch('items', +id, { is_loan: cur === '1' ? 0 : 1 });
      window.loadFin();
    }));
  document.querySelectorAll('[data-ftype]').forEach(el =>
    el.addEventListener('click', () => {
      const id = +el.dataset.ftype;
      const ent = 'tgt';   // дерево одно
      const sel = document.createElement('select');
      sel.innerHTML = '<option value="">— тип актива —</option>'
        + ATYPES.map(t => `<option>${t}</option>`).join('') + '<option value="__none">убрать тип</option>';
      el.replaceWith(sel);
      sel.focus();
      sel.addEventListener('change', async () => {
        await finApi.patch(ent, id, { asset_type: sel.value === '__none' ? null : (sel.value || null) });
        window.loadFin();
      });
      sel.addEventListener('blur', () => window.loadFin());
    }));
  document.querySelectorAll('[data-fregion]').forEach(el =>
    el.addEventListener('click', () => {
      const id = +el.dataset.fregion;
      const ent = 'tgt';   // дерево одно
      const sel = document.createElement('select');
      sel.innerHTML = '<option value="">— регион —</option>'
        + REGIONS.map(r => `<option>${r}</option>`).join('') + '<option value="__none">убрать</option>';
      el.replaceWith(sel);
      sel.focus();
      sel.addEventListener('change', async () => {
        await finApi.patch(ent, id, { region: sel.value === '__none' ? null : (sel.value || null) });
        window.loadFin();
      });
      sel.addEventListener('blur', () => window.loadFin());
    }));
  const finEnt = () => 'tgt';   // дерево одно
  document.querySelectorAll('[data-fqty]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', v => finApi.patch(finEnt(), +el.dataset.fqty, { qty: v }))));
  document.querySelectorAll('[data-frate]').forEach(el =>
    el.addEventListener('click', () => {
      const id = +el.dataset.frate;
      const sel = document.createElement('select');
      sel.innerHTML = '<option value="">— тикер автоцены —</option>'
        + RSYMS.map(t => `<option>${t}</option>`).join('') + '<option value="__none">убрать автоцену</option>';
      el.replaceWith(sel);
      sel.focus();
      sel.addEventListener('change', async () => {
        if (sel.value === '__none') await finApi.patch(finEnt(), id, { rate_symbol: null, qty: null });
        else if (sel.value) {
          const q = parseNum(prompt(`Количество (${sel.value}):`) ?? '');
          await finApi.patch(finEnt(), id, { rate_symbol: sel.value, qty: q });
          // курса ещё нет — подтягиваем сразу, чтобы автоцена посчиталась
          const known = finData.rates.find(r => r.symbol === sel.value)?.price;
          if (!known) await finApi.ratesRefresh().catch(() => {});
        }
        window.loadFin();
      });
      sel.addEventListener('blur', () => window.loadFin());
    }));
  // долги
  document.querySelectorAll('[data-ddir]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, dir] = el.dataset.ddir.split(':');
      await finApi.patch('debts', +id, { direction: dir === 'i_owe' ? 'owed_to_me' : 'i_owe' });
      window.loadFin();
    }));
  document.querySelectorAll('[data-dcur]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, cur] = el.dataset.dcur.split(':');
      await finApi.patch('debts', +id, { currency: cur === '€' ? '$' : '€' });
      window.loadFin();
    }));
  $('dbAdd')?.addEventListener('click', async () => {
    if (!$('dbName').value.trim()) return;
    await finApi.add('debts', { name: $('dbName').value.trim(), direction: $('dbDir').value,
      amount: parseNum($('dbAmount').value) ?? 0, currency: $('dbCur').value,
      due_date: /^\d{4}-\d{2}-\d{2}$/.test($('dbDate').value) ? $('dbDate').value : null });
    window.loadFin();
  });
  // расходы
  const shiftYm = (ym, dd) => { const [y, m] = ym.split('-').map(Number); return new Date(Date.UTC(y, m - 1 + dd, 1)).toISOString().slice(0, 7); };
  $('txPrev')?.addEventListener('click', () => { finTxMonth = shiftYm(finTxMonth, -1); window.loadFin(); });
  $('txNext')?.addEventListener('click', () => { finTxMonth = shiftYm(finTxMonth, 1); window.loadFin(); });
  $('monefyToggle')?.addEventListener('click', () => { showMonefy = !showMonefy; renderFin(); });
  $('txBudget')?.addEventListener('click', async () => {
    const v = prompt('Базовый минимум на месяц, € (еда, быт, обязательные траты):', finData.budget ?? '');
    if (v == null) return;
    const n = parseNum(v);
    await fetch('/api/setting', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'monthly_budget', value: n ?? '' }) });
    window.loadFin();
  });
  $('monefyGo')?.addEventListener('click', async () => {
    const csv = $('monefyCsv').value;
    if (!csv.trim()) return;
    const r = await finApi.monefy(csv);
    alert(r.error ? r.error : `Импортировано транзакций: ${r.imported}`);
    showMonefy = false;
    window.loadFin();
  });
  $('txAdd')?.addEventListener('click', async () => {
    const amount = parseNum($('txAmount').value);
    if (amount == null) return;
    await finApi.add('tx', { date: /^\d{4}-\d{2}-\d{2}$/.test($('txDate').value) ? $('txDate').value : undefined,
      direction: $('txDir').value, category: $('txCat').value.trim() || 'прочее',
      amount, note: $('txNote').value.trim() });
    window.loadFin();
  });
  // прогнозы
  document.querySelectorAll('[data-fcres]').forEach(el =>
    el.addEventListener('click', async () => {
      const [id, out] = el.dataset.fcres.split(':');
      await fetch(`/api/fin/forecasts/${id}/resolve`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ outcome: out === '1' }) });
      window.loadFin();
    }));
  document.querySelectorAll('[data-fcdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить прогноз?')) {
        await fetch('/api/fin/forecasts/' + el.dataset.fcdel, { method: 'DELETE' });
        window.loadFin();
      }
    }));
  $('fcAdd')?.addEventListener('click', async () => {
    const statement = $('fcText').value.trim();
    if (!statement) return;
    await fetch('/api/fin/forecasts', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ statement, confidence: parseInt($('fcConf').value, 10) || 50,
        due_date: /^\d{4}-\d{2}-\d{2}$/.test($('fcDue').value) ? $('fcDue').value : null }) });
    window.loadFin();
  });
  // имущество
  $('prAdd')?.addEventListener('click', async () => {
    const name = $('prName').value.trim();
    if (!name) return;
    await fetch('/api/fin/properties', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, category: $('prCat').value }) });
    window.loadFin();
  });
  document.querySelectorAll('[data-propdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить объект со всем регламентом?')) {
        await fetch('/api/fin/properties/' + el.dataset.propdel, { method: 'DELETE' });
        window.loadFin();
      }
    }));
  document.querySelectorAll('[data-ruleadd]').forEach(el =>
    el.addEventListener('click', async () => {
      const pid = el.dataset.ruleadd;
      const q = sel => document.querySelector(`[data-rule${sel}="${pid}"]`).value.trim();
      const name = q('name');
      if (!name) return;
      await fetch(`/api/fin/properties/${pid}/rules`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, amount: parseNum(q('amount')) ?? 0, period: q('period'),
          next_date: /^\d{4}-\d{2}-\d{2}$/.test(q('date')) ? q('date') : null }) });
      window.loadFin();
    }));
  // FIRE и макро
  document.querySelectorAll('[data-fireset]').forEach(el =>
    el.addEventListener('click', () => inlineVal(el, 'num', async v => { await finApi.fire({ [el.dataset.fireset]: v }); })));
  $('mcAdd')?.addEventListener('click', async () => {
    if (!$('mcThesis').value.trim()) return;
    await finApi.macroAdd({ phase: $('mcPhase').value, thesis: $('mcThesis').value.trim() });
    window.loadFin();
  });
  document.querySelectorAll('[data-mcdel]').forEach(el =>
    el.addEventListener('click', async () => {
      if (confirm('Удалить запись из истории тезисов?')) { await finApi.macroDel(+el.dataset.mcdel); window.loadFin(); }
    }));
  // прочее
  $('ratesRefresh')?.addEventListener('click', async () => {
    $('ratesRefresh').textContent = '…';
    const r = await finApi.ratesRefresh();
    if (r.error) alert(r.error);
    else if (r.errors?.length && r.rates?.some(x => x.price == null))
      alert('Часть курсов не обновилась:\n' + r.errors.join('\n'));
    window.loadFin();
  });
  $('accAdd')?.addEventListener('click', async () => {
    if (!$('accName').value.trim()) return;
    await finApi.add('accounts', { name: $('accName').value.trim(), type: $('accType').value,
      currency: $('accCur').value, balance: parseNum($('accBal').value) ?? 0 });
    window.loadFin();
  });
  $('stAdd')?.addEventListener('click', async () => {
    if (!$('stTitle').value.trim()) return;
    await finApi.add('steps', { kind: $('stKind').value, title: $('stTitle').value.trim() });
    window.loadFin();
  });
  $('obAdd')?.addEventListener('click', async () => {
    if (!$('obName').value.trim()) return;
    await finApi.add('obligations', { kind: $('obKind').value, name: $('obName').value.trim(),
      amount: parseNum($('obAmount').value) ?? 0, period: $('obPeriod').value, currency: '€',
      next_date: /^\d{4}-\d{2}-\d{2}$/.test($('obDate').value) ? $('obDate').value : null });
    window.loadFin();
  });
}

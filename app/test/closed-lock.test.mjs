import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// 🔒 Закрытая позиция: добирать нечего, поэтому её цель равна текущей сумме и идёт за ней —
// у ⚡-позиций (ETF, BTC, золото) пересчитывается вместе с курсом. Отклонение всегда ноль,
// а цель нельзя править ни суммой, ни долей: она не задаётся, а берётся.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));

function loadFin(mobile) {
  const calls = [], alerts = [];
  let hooks = [], list = { targetPortfolio: [] };
  const ctx = {
    document: { querySelectorAll: sel => hooks.filter(h => sel.includes(Object.keys(h.dataset)[0])),
      getElementById: () => null, addEventListener() {},
      createElement: () => ({ addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
        dataset: {}, style: {}, innerHTML: '', value: '', focus() {}, replaceWith() {} }) },
    console, localStorage: {},
    fetch: async (url, opt) => { calls.push({ method: opt?.method || 'GET', url, body: opt?.body });
      return { ok: true, status: 200, json: async () => list }; },
    alert: m => alerts.push(m), confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: !!mobile }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx; ctx.loadFin = () => {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  // клик по замку в живой разметке; afterPatch — что отдаст бэкенд при перечитывании
  const clickLock = async (html, afterPatch) => {
    if (afterPatch) list = afterPatch;
    const fclosed = (html.match(/data-fclosed="([^"]+)"/) || [])[1];
    assert.ok(fclosed, 'в строке нет замка');
    const el = { dataset: { fclosed }, addEventListener(ev, fn) { el['_' + ev] = fn; } };
    hooks = [el];
    ctx.bindFin();
    await el._click();
    return { patch: calls.find(c => c.method === 'PATCH'), alerts };
  };
  return { ctx, clickLock, calls, alerts };
}

// ⚡-позиция: сумма приходит из «количество × курс», поэтому в разных отрисовках она разная
const etf = (eur, o = {}) => ({ id: 3, name: 'EXUS', kind: 'asset', children: [], currency: '$',
  value: eur * 1.08, eur, auto: true, qty: 10, rate_symbol: 'IVV', target_value: 300, ...o });
const data = nodes => ({
  summary: { portfolioTotal: 1000, rate: 1.08 }, portfolio: [], targetMoves: [],
  targetPortfolio: [{ id: 1, name: 'Рост', kind: 'block', side: 'act',
    eur: nodes.reduce((a, n) => a + n.eur, 0), children: nodes }],
  targetByType: [], targetByTypeBlocks: {}, byType: [], byRegion: [], byTypeBlocks: {}, byRegionBlocks: {},
  blockEur: {}, rates: [], saveGoals: [], historyRows: [], history: [],
});
const rowOf = (html, name) => html.split('<tr ').slice(1).map(r => r.split('</tr>')[0])
  .find(r => new RegExp(`:name:text"[^>]*>${name}</span>`).test(r)) || '';
const cells = row => row.split('<td').map(c => c.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').replace(/ /g, ' ').trim());

test('закрытая позиция: цель равна текущей сумме, а не вписанной когда-то', () => {
  const d = data([etf(1000)]);                       // вписана цель 300 $, но позиция закрыта
  const open = rowOf(loadFin().ctx.secPortfolio(d, d.summary), 'EXUS');
  assert.match(cells(open)[6], /300/, 'у открытой позиции цель должна остаться своей');

  const dc = data([etf(1000, { closed: 1 })]);
  const row = rowOf(loadFin().ctx.secPortfolio(dc, dc.summary), 'EXUS');
  assert.match(cells(row)[6], /🔒 1 080/, 'цель закрытой позиции должна равняться её сумме (1 000 € = 1 080 $)');
  assert.match(cells(row)[7], /✓ в цели/, 'у закрытой позиции не бывает отклонения');
});

test('цель закрытой ⚡-позиции идёт за курсом', () => {
  const grew = data([etf(1300, { closed: 1 })]);     // курс вырос — сумма пришла другая
  const row = rowOf(loadFin().ctx.secPortfolio(grew, grew.summary), 'EXUS');
  assert.match(cells(row)[6], /🔒 1 404/, 'цель не пересчиталась вместе с суммой');
  assert.match(cells(row)[7], /✓ в цели/, 'после переоценки появилось отклонение');
});

test('закрытую цель нечем править — она берётся, а не задаётся', () => {
  const dc = data([etf(1000, { closed: 1 })]);
  const row = rowOf(loadFin().ctx.secPortfolio(dc, dc.summary), 'EXUS');
  assert.ok(!row.includes('target_value:num'), 'цель закрытой позиции осталась редактируемой суммой');
  assert.ok(!row.includes('data-fgoalpct'), 'цель закрытой позиции осталась редактируемой долей');
  assert.match(row, /позиция закрыта: цель равна текущей сумме/, 'не сказано, почему не правится');
});

test('закрытый блок снимает вопрос целиком — вложенные цели не в счёт', () => {
  const d = data([etf(1000), { id: 4, name: 'Кэш', kind: 'asset', children: [], currency: '€',
    value: 200, eur: 200, target_value: 500 }]);
  d.targetPortfolio[0].closed = 1;                   // блок 1 200 €, внутри целей на 778 € (300 $ + 500 €)
  const html = loadFin().ctx.secPortfolio(d, d.summary);
  assert.match(cells(rowOf(html, 'Рост'))[6], /🔒 1 200/, 'цель закрытого блока — его текущая сумма');
  assert.match(cells(rowOf(html, 'Рост'))[7], /✓ в цели/, 'у закрытого блока отклонение должно быть нулём');
  // цель части считается по той же сумме — она стоит в строке над таблицей
  assert.match((html.match(/<div class="capline">[\s\S]*?<\/div>/) || [''])[0].replace(/\u00a0/g, ' '),
    /цель.*1 200 €/, 'цель части не сошлась с закрытым блоком');
  // внутри целей на 778 € — молча расходиться с ними нельзя
  assert.match(cells(rowOf(html, 'Рост'))[6].replace(/\u00a0/g, ' '), /внутри целей 778 €/,
    'не видно, что цели внутри остались своими');
});

test('замок есть у каждой строки — и на телефоне тоже', () => {
  const d = data([etf(1000), { id: 5, name: 'Акции', kind: 'section', currency: '€', eur: 400,
    children: [{ id: 6, name: 'VHT', kind: 'asset', children: [], currency: '€', value: 400, eur: 400 }] }]);
  const html = loadFin().ctx.secPortfolio(d, d.summary);
  ['Рост', 'Акции', 'EXUS', 'VHT'].forEach(n =>
    assert.ok(rowOf(html, n).includes('data-fclosed'), `у «${n}» нет замка, а цель задать можно`));
  const card = loadFin(true).ctx.secPortfolio(d, d.summary).split('<div class="pcard').find(c => c.includes('EXUS'));
  assert.ok(card.includes('data-fclosed'), 'на телефоне замка нет');
});

test('замок переключается в обе стороны', async () => {
  const dc = data([etf(1000)]);
  const f = loadFin();
  const { patch } = await f.clickLock(rowOf(f.ctx.secPortfolio(dc, dc.summary), 'EXUS'),
    { targetPortfolio: [{ id: 3, name: 'EXUS', children: [], closed: 1 }] });
  assert.equal(patch.url, '/api/fin/tgt/3');
  assert.deepEqual(JSON.parse(patch.body), { closed: 1 });
  assert.deepEqual(f.alerts, [], 'записалось, а мы ругаемся');

  const locked = data([etf(1000, { closed: 1 })]);
  const g = loadFin();
  const back = await g.clickLock(rowOf(g.ctx.secPortfolio(locked, locked.summary), 'EXUS'),
    { targetPortfolio: [{ id: 3, name: 'EXUS', children: [], closed: 0 }] });
  assert.deepEqual(JSON.parse(back.patch.body), { closed: 0 }, 'замок не снимается');
});

test('если сборка не знает про замок — говорим вслух, а не делаем вид', async () => {
  const dc = data([etf(1000)]);
  const f = loadFin();
  // старый бэкенд: patchCols не знает колонку closed, отвечает 200, в базе по-прежнему 0
  const { alerts } = await f.clickLock(rowOf(f.ctx.secPortfolio(dc, dc.summary), 'EXUS'),
    { targetPortfolio: [{ id: 3, name: 'EXUS', children: [], closed: 0 }] });
  assert.match(alerts[0] || '', /замок на позиции/, 'кнопка не сработала, а пользователю ничего не сказали');
  assert.match(alerts[0], /Xcode/, 'не названо, что лечится пересборкой');
});

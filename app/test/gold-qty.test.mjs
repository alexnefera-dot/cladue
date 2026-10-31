import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// Золото: курс XAUUSD котируется за тройскую унцию, а на руках оно в граммах. Количество
// по-прежнему хранится в унциях (бэкенд считает qty × курс и про единицы не знает),
// но вписывать и читать его можно в граммах.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));
const OZ = 31.1034768;

function loadFin() {
  const made = [], calls = [], alerts = [];
  let hooks = [];
  const node = () => { const n = { addEventListener(ev, fn) { n['_' + ev] = fn; }, appendChild() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '',
    textContent: '', focus() {}, select() {}, replaceWith() {} }; made.push(n); return n; };
  const ctx = {
    document: { querySelectorAll: sel => hooks.filter(h => sel.includes(Object.keys(h.dataset)[0])),
      getElementById: () => null, addEventListener() {}, createElement: node },
    console, localStorage: {},
    fetch: async (url, opt) => { calls.push({ method: opt?.method || 'GET', url, body: opt?.body });
      return { ok: true, status: 200, json: async () => ({ rates: [] }) }; },
    alert: m => alerts.push(m), confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx; ctx.loadFin = () => {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  // курс нужен подсказке: цена грамма считается из цены унции
  vm.runInContext('finData = { rates: [{ symbol: "XAUUSD", label: "Золото", price: 4000 }] }', ctx);
  const q = expr => vm.runInContext(expr, ctx);
  // вписать значение в живое поле: поднимаем элемент из разметки и прогоняем через обработчик
  const typeInto = async (html, attr, text) => {
    const dataset = { [attr]: (html.match(new RegExp(`data-${attr}="([^"]+)"`)) || [])[1] };
    assert.ok(dataset[attr], `в разметке нет data-${attr}`);
    const el = { dataset, textContent: '50 г × XAUUSD', addEventListener(ev, fn) { el['_' + ev] = fn; }, replaceWith() {} };
    if (html.includes('data-hint=')) el.dataset.hint = (html.match(/data-hint="([^"]+)"/) || [])[1];
    hooks = [el];
    ctx.bindFin();
    el._click();
    const input = made.at(-1);
    input.value = text;
    input._keydown({ key: 'Enter' });
    await new Promise(r => setTimeout(r, 0));
    return { patch: calls.find(c => c.method === 'PATCH'), input, alerts };
  };
  return { ctx, q, typeInto, calls, alerts, made };
}

const gold = (qty) => ({ id: 3, name: 'Монеты', kind: 'asset', children: [], currency: '$',
  value: qty * 4000, eur: qty * 4000 / 1.08, rate_symbol: 'XAUUSD', qty, auto: true });

test('количество золота понимается и в граммах, и в унциях', () => {
  const { q } = loadFin();
  const oz = g => Math.round(g / OZ * 1e6) / 1e6;
  assert.equal(q('parseQty("50 г", "XAUUSD")'), oz(50), '«50 г» не перевелись в унции');
  assert.equal(q('parseQty("50", "XAUUSD")'), oz(50), 'без единицы у золота считаем граммы');
  assert.equal(q('parseQty("50 g", "XAUUSD")'), oz(50), 'латинские граммы не поняты');
  assert.equal(q('parseQty("31,1 грамма", "XAUUSD")'), oz(31.1), 'запятая или словоформа не поняты');
  assert.equal(q('parseQty("1.6 oz", "XAUUSD")'), 1.6, 'унции не поняты');
  assert.equal(q('parseQty("2 унции", "XAUUSD")'), 2, 'унции по-русски не поняты');
  assert.equal(q('parseQty("1 кг", "XAUUSD")'), oz(1000), 'слиток в килограммах не понят');
  assert.equal(q('parseQty("", "XAUUSD")'), null, 'пустое не должно становиться нулём');
  assert.equal(q('parseQty("много", "XAUUSD")'), null, 'непонятное лучше отвергнуть, чем угадать');
  assert.equal(q('parseQty("пол кило", "XAUUSD")'), null, 'килограммы не заявлены — не угадываем');
  // у остальных тикеров количество как было — штуки, с k/m
  assert.equal(q('parseQty("10", "IVV")'), 10);
  assert.equal(q('parseQty("1.5k", "IVV")'), 1500, 'прежний разбор чисел сломался');
});

test('в строке золото показано граммами, а унции и цена грамма — в подсказке', () => {
  const ctx = loadFin().ctx;
  const row = ctx.portRows(gold(1.607536), 1, { total: 10000, rate: 1.08 });
  assert.match(row, /50 г × XAUUSD/, 'количество золота показано не в граммах');
  assert.match(row, /1\.607536 oz/, 'в подсказке нет унций');
  assert.match(row, /128[.,]\d+ \$ за грамм/, 'не посчитана цена грамма (4 000 $ за унцию)');
  assert.match(row, /клик — вписать «50 г» или «1\.6 oz»/, 'не сказано, что можно вписать граммы');
  assert.match(row, /авто: 50 г × курс XAUUSD \(1\.607536 oz\)/, 'в «Сейчас» автоцена тоже должна быть в граммах');
});

test('вписанные граммы уходят на бэкенд унциями', async () => {
  const f = loadFin();
  const row = f.ctx.portRows(gold(1), 1, {});
  const { patch, input } = await f.typeInto(row, 'fqty', '50 г');
  assert.equal(patch.url, '/api/fin/tgt/3');
  assert.deepEqual(JSON.parse(patch.body), { qty: Math.round(50 / OZ * 1e6) / 1e6 },
    'в базу должно лечь количество в унициях — иначе бэкенд умножит граммы на цену унции');
  assert.equal(input.value, '50 г', 'поле не должно подставлять в ввод текст пилюли');
  assert.equal(input.placeholder, '50 г или 1.6 oz', 'подсказка в пустом поле не та');
});

test('непонятное количество не пишем, а говорим об этом', async () => {
  const f = loadFin();
  const { patch, alerts } = await f.typeInto(f.ctx.portRows(gold(1), 1, {}), 'fqty', 'щепотка');
  assert.equal(patch, undefined, 'записали непонятное количество');
  assert.match(alerts[0] || '', /«50 г» или «1\.6 oz»/, 'не подсказали, как писать');
});

test('у обычного тикера количество осталось числом штук', async () => {
  const f = loadFin();
  const ivv = { id: 7, name: 'IVV', kind: 'asset', children: [], currency: '$', value: 5000,
    eur: 4600, rate_symbol: 'IVV', qty: 10, auto: true };
  const row = f.ctx.portRows(ivv, 1, {});
  assert.match(row, /10 × IVV/, 'штуки не должны превращаться в граммы');
  const { patch } = await f.typeInto(row, 'fqty', '12');
  assert.deepEqual(JSON.parse(patch.body), { qty: 12 });
});

test('выбор ⚡ у золота спрашивает граммы и сразу переводит в унции', async () => {
  const f = loadFin();
  let asked = '';
  f.ctx.prompt = m => { asked = m; return '100 г'; };
  const row = f.ctx.portRows({ id: 9, name: 'Слиток', kind: 'asset', children: [], currency: '€', value: 0, eur: 0 }, 1, {});
  const el = { dataset: { frate: (row.match(/data-frate="(\d+)"/) || [])[1] },
    addEventListener(ev, fn) { el['_' + ev] = fn; }, replaceWith() {} };
  vm.runInContext('window.__hook = null', f.ctx);
  f.ctx.document.querySelectorAll = sel => sel.includes('frate') ? [el] : [];
  f.ctx.bindFin();
  el._click();
  const sel = f.made.at(-1);
  sel.value = 'XAUUSD';
  await sel._change();
  assert.match(asked, /«50 г» или «1\.6 oz»/, 'при выборе золота не предложено вписать граммы');
  const patch = f.calls.find(c => c.method === 'PATCH');
  assert.deepEqual(JSON.parse(patch.body),
    { rate_symbol: 'XAUUSD', qty: Math.round(100 / OZ * 1e6) / 1e6 }, 'граммы не перевелись в унции');
});

test('в полосе курсов видно, что золото — за унцию, и сколько стоит грамм', () => {
  const f = loadFin();
  const node = { addEventListener() {}, appendChild() {}, replaceWith() {}, focus() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '' };
  f.ctx.document.getElementById = () => node;
  f.ctx.__d = { accounts: [], budgetItems: [], portfolio: [], targetPortfolio: [],
    rates: [{ symbol: 'XAUUSD', label: 'Золото', price: 4000 }],
    summary: { rate: 1.08, portfolioTotal: 0, accountsByCurrency: { '€': 0 } } };
  vm.runInContext('finSection = "__none__"; finData = __d; finBuild = null', f.ctx);   // нужна только шапка
  f.ctx.renderFin();
  const html = node.innerHTML.replace(/ /g, ' ');
  assert.match(html, /\/oz/, 'в полосе не сказано, что курс за тройскую унцию');
  assert.match(html, /128[.,]\d+ \$ за грамм/, 'нет цены грамма — её считают в уме при покупке');
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// Проценты в строках портфеля: «процент от чего» должно читаться однозначно.
// Рамки две — внутри своего раздела (прямого родителя) и внутри своей части портфеля.
// Прежде вторым числом стояла доля от блока верхнего уровня: для актива внутри раздела
// это был процент от чужой суммы, и понять его было нельзя.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));

function loadFin(mobile) {
  const made = [], calls = [], alerts = [];
  let hooks = [];
  const node = () => { const n = { addEventListener(ev, fn) { n['_' + ev] = fn; }, appendChild() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '',
    textContent: '', focus() {}, select() {}, replaceWith() {} }; made.push(n); return n; };
  const ctx = {
    document: { querySelectorAll: sel => hooks.filter(h => ('[data-' + Object.keys(h.dataset)[0].toLowerCase() + ']') === sel.toLowerCase()),
      getElementById: () => null, addEventListener() {}, createElement: node },
    console, localStorage: {},
    fetch: async (url, opt) => { calls.push({ method: opt?.method || 'GET', url, body: opt?.body }); return { ok: true, status: 200, json: async () => ({}) }; },
    alert: m => alerts.push(m), confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: !!mobile }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  ctx.loadFin = () => {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  // клик по доле: поднимаем из разметки живой элемент, биндим обработчики и вписываем значение
  ctx.typeShare = async (html, name, text) => {
    const row = rowOf(html, name);
    const dataset = { fgoalpct: (row.match(/data-fgoalpct="([^"]+)"/) || [])[1] };
    assert.ok(dataset.fgoalpct, `у «${name}» нет поля доли в целях`);
    const el = { dataset, textContent: '33.3%', addEventListener(ev, fn) { el['_' + ev] = fn; }, replaceWith() {} };
    hooks = [el];
    ctx.bindFin();
    el._click();
    const input = made.at(-1);
    input.value = text;
    input._keydown({ key: 'Enter' });
    await new Promise(r => setTimeout(r, 0));
    return { patch: calls.find(c => c.method === 'PATCH'), alerts };
  };
  return ctx;
}

const asset = (id, name, value, target) => ({ id, name, kind: 'asset', children: [],
  value, eur: value, currency: '€', target_value: target });

// Инвестиции 1000 €: блок «Рост» 800 (раздел «Акции» 600 = A 450 + B 150) и блок «Крипта» 200.
// Цели: A 500, B 100, BTC 900 — раздел 600, часть 1 500. Целей намеренно больше, чем лежит:
// на этом и ломались проценты цели, когда считались от суммы части сейчас.
const DATA = {
  summary: { portfolioTotal: 1000, portfolioTotalUsd: 1080, rate: 1.08 },
  portfolio: [], targetMoves: [],
  targetPortfolio: [
    { id: 1, name: 'Рост', kind: 'block', side: 'act', eur: 800, children: [
      { id: 2, name: 'Акции', kind: 'section', eur: 600, currency: '€', children: [
        asset(3, 'Актив A', 450, 500), asset(4, 'Актив B', 150, 100)] }] },
    { id: 5, name: 'Крипта', kind: 'block', side: 'act', eur: 200, children: [asset(6, 'BTC', 200, 900)] },
    { id: 7, name: 'Вещи', kind: 'block', side: 'use', eur: 300, children: [asset(8, 'Машина', 300, 300)] },
  ],
  targetByType: [], targetByTypeBlocks: {}, byType: [], byRegion: [], byTypeBlocks: {}, byRegionBlocks: {},
  blockEur: {}, rates: [{ symbol: 'IVV', price: 500 }], saveGoals: [], historyRows: [], history: [],
};

// строку ищем по имени в её собственной ячейке: «BTC» встречается и в подсказке у ⚡ чужих строк
const rowOf = (html, name) => html.split('<tr ').slice(1).map(r => r.split('</tr>')[0])
  .find(r => new RegExp(`:name:text"[^>]*>${name}</span>`).test(r)) || '';
const subs = row => [...row.matchAll(/<span class="sub"[^>]*>([\s\S]*?)<\/span>\s*<\/td>|<span class="sub">([\s\S]*?)<\/span>/g)]
  .map(m => (m[1] ?? m[2]).replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').replace(/ /g, ' ').trim());
const nums = row => subs(row).map(s => (s.match(/[\d.]+%/g) || []).join(' / '));

test('доля актива считается внутри своего раздела, потом внутри части', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  const row = rowOf(html, 'Актив A');
  assert.ok(row, 'строка актива не отрисовалась');
  // 450 из раздела 600 = 75%, 450 из части 1000 = 45%. Доля от блока (56.3%) тут не при чём.
  assert.equal(nums(row)[0], '75.0% / 45.0%', 'доля суммы считается не от раздела и не от части');
  assert.ok(!nums(row)[0].includes('56.3'), 'вернулась доля от блока верхнего уровня');
});

test('раздел считается внутри своего блока, блок — внутри своей части', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.equal(nums(rowOf(html, 'Акции'))[0], '75.0% / 60.0%', 'раздел: 600 из блока 800 и из части 1000');
  // у блока прямой родитель — сама часть, второе число повторяло бы первое
  assert.equal(nums(rowOf(html, 'Рост'))[0], '80.0%', 'у блока должна остаться одна доля — от части');
});

test('доли цели живут в тех же рамках, что и доли суммы, но считаются от целей', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  // цель A 500: 83.3% цели раздела (600) и 33.3% всех целей части (1 500).
  // от суммы части сейчас (1 000) вышло бы 50% — и по столбцу набралось бы 150%.
  assert.equal(nums(rowOf(html, 'Актив A'))[1], '83.3% / 33.3%', 'доли цели считаются не от целей');
  assert.equal(nums(rowOf(html, 'Акции'))[1], '100.0% / 40.0%', 'цель раздела: вся цель блока и 40% целей части');
});

test('по столбцу «Цель» доли сходятся в 100% — это целевая структура', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  const part = ['Актив A', 'Актив B', 'BTC']
    .map(n => +nums(rowOf(html, n))[1].split(' / ').pop().replace('%', ''));
  assert.ok(Math.abs(part.reduce((a, b) => a + b, 0) - 100) < 0.2,
    `доли целей листьев части дают ${part.join('+')} вместо 100%`);
});

test('в подсказке названы и рамка, и сумма, от которой считается процент', () => {
  const row = rowOf(loadFin().secPortfolio(DATA, DATA.summary), 'Актив A').replace(/\u00a0/g, ' ');
  assert.match(row, /title="доля в «Акции» — 600 € \/ доля в части «ИНВЕСТИЦИИ» — 1 000 €"/, 'рамки доли не названы суммами');
  assert.match(row, /title="доля в цели в «Акции» — 600 €"/, 'доля цели внутри раздела без суммы');
  assert.match(row, /доля в сумме целей в части «ИНВЕСТИЦИИ» — 1 500 €/, 'не названа сумма целей части');
});

test('рамка совпала с частью — одно число вместо двух одинаковых', () => {
  // Инвестиции = один блок = один раздел: раздел и часть это одна и та же сумма,
  // два процента подряд были бы одинаковыми — именно это и читалось как «странный процент».
  const one = { ...DATA, targetPortfolio: [
    { id: 1, name: 'Рост', kind: 'block', side: 'act', eur: 1000, children: [
      { id: 2, name: 'Акции', kind: 'section', eur: 1000, currency: '€', children: [
        asset(3, 'Актив A', 450, 500), asset(4, 'Актив B', 550, 500)] }] }] };
  const html = loadFin().secPortfolio(one, one.summary);
  assert.equal(nums(rowOf(html, 'Акции'))[0], '100.0%', 'раздел на всю часть дал два числа');
  assert.equal(nums(rowOf(html, 'Актив A'))[0], '45.0%', 'у актива рамки совпали, а чисел два');
  // а цель раздела (1 000 €) равна сумме части — её доля тоже одна
  assert.equal(nums(rowOf(html, 'Актив A'))[1], '50.0%', 'доля цели продублирована');
});

test('доли своей части, а не общего капитала: вещи считаются от вещей', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  // «Машина» — единственное в своей части: 100% её, хотя от капитала это 30%.
  // Рамки раздела и части здесь совпали, поэтому число одно.
  assert.equal(nums(rowOf(html, 'Машина'))[0], '100.0%', 'часть «вещи» считается от чужого тотала');
  assert.match(rowOf(html, 'Машина'), /доля в части «ПОЛЬЗОВАТЕЛЬСКИЕ АКТИВЫ»/, 'не названа своя часть');
});

test('без разбивки на части рамка верхнего уровня — весь портфель', () => {
  const one = { ...DATA, targetPortfolio: DATA.targetPortfolio.filter(n => n.side === 'act') };
  const html = loadFin().secPortfolio(one, one.summary);
  assert.match(rowOf(html, 'Актив A').replace(/\u00a0/g, ' '),
    /доля в «Акции» — 600 € \/ доля в портфеле — 1 000 €/, 'рамка без частей названа неверно');
});

test('вписанная доля в целях даёт ровно её: цель пересчитывается суммой', async () => {
  const ctx = loadFin();
  const html = ctx.secPortfolio(DATA, DATA.summary);
  // остальные цели части без A — 1 000 € (B 100 + BTC 900). Чтобы доля вышла 40%,
  // цель A должна стать 1 000 × 0.4/0.6 = 666.67 €, и тогда 666.67/1 666.67 = 40%.
  const { patch } = await ctx.typeShare(html, 'Актив A', '40');
  assert.equal(patch.url, '/api/fin/tgt/3');
  assert.deepEqual(JSON.parse(patch.body), { target_pct: null, target_value: 666.67 },
    'доля переведена в сумму неточно — показанный процент разойдётся с вписанным');
});

test('первая цель в части считается от суммы части сейчас', async () => {
  const ctx = loadFin();
  const bare = { ...DATA, targetPortfolio: [
    { id: 1, name: 'Рост', kind: 'block', side: 'act', eur: 1000, children: [
      { id: 2, name: 'Акции', kind: 'section', eur: 1000, currency: '€', children: [
        { id: 3, name: 'Актив A', kind: 'asset', children: [], value: 450, eur: 450, currency: '€' }] }] }] };
  const { patch } = await ctx.typeShare(ctx.secPortfolio(bare, bare.summary), 'Актив A', '30');
  assert.deepEqual(JSON.parse(patch.body), { target_pct: null, target_value: 300 },
    'делиться не с кем — ждём 30% от суммы части (1 000 €)');
});

test('100% в долю целей не пускаем — это «убери цели у остальных»', async () => {
  const ctx = loadFin();
  const { patch, alerts } = await ctx.typeShare(ctx.secPortfolio(DATA, DATA.summary), 'Актив A', '100');
  assert.equal(patch, undefined, 'записали невозможную долю');
  assert.match(alerts[0] || '', /убери цели у остальных/, 'молча ничего не сделали');
});

test('у раздела с целями внутри доля не правится — её складывают вложенные', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(!rowOf(html, 'Акции').includes('data-fgoalpct'),
    'клик по доле раздела записал бы цель, которую бэкенд всё равно игнорирует');
  assert.match(rowOf(html, 'Акции'), /цель складывается из вложенных/, 'не сказано, почему не правится');
});

// «Распределение»: полоски «сейчас/цель» всегда считались каждая от своей суммы, а числа
// в списке справа — обе от суммы сейчас. Один и тот же блок показывал два разных процента.
const brow = (html, cat) => (html.match(new RegExp(`<div class="brow"[^>]*data-cat="${cat}"[\\s\\S]*?</div>`)) || [''])[0];
const vals = row => [...row.matchAll(/<span class="v[^"]*">([^<]*)<\/span>/g)]
  .map(m => m[1].replace(/ /g, ' ').trim());
const segPct = (html, cat) => ((html.match(new RegExp(`<i class="seg" data-cat="${cat}"[^>]*title="[^"]*цель[^"]*· ([\\d.]+)%`)) || [])[1]);

test('распределение: доля цели считается от суммы целей — как в полоске', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  const [nowEur, nowPct, planEur, planPct, , devPP] = vals(brow(html, 'Рост'));
  assert.equal(nowEur, '800');
  assert.equal(nowPct, '80.0%', 'доля сейчас — от суммы сейчас');
  assert.equal(planEur, '600');
  assert.equal(planPct, '40.0%', 'доля цели считается не от суммы целей (1 500 €)');
  assert.equal(segPct(html, 'Рост'), '40.0', 'полоска и список снова показывают разное');
  assert.equal(devPP, '+40.0', 'п.п. должны быть перекосом структуры: 80% сейчас против 40% в целях');
});

test('«% капитала» в шапке части: только когда капитал из двух частей', () => {
  const head = (html, title) => html.split('<tr class="parthead').slice(1)
    .map(r => r.split('</td>')[0].replace(/\u00a0/g, ' ')).find(r => r.includes(title)) || '';
  // резерва нет — у инвестиций всегда выходило «100% капитала»: число ни о чём
  const one = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(!head(one, 'ИНВЕСТИЦИИ').includes('капитала'), 'в шапке осталось бессмысленное 100%');

  // появился резерв 500 € — доля части снова что-то значит
  const two = { ...DATA, targetPortfolio: [...DATA.targetPortfolio,
    { id: 9, name: 'Подушка', kind: 'block', side: 'safe', eur: 500,
      children: [{ id: 10, name: 'Кэш', kind: 'asset', children: [], value: 500, eur: 500, currency: '€' }] }] };
  const html = loadFin().secPortfolio(two, two.summary);
  assert.match(head(html, 'ИНВЕСТИЦИИ'), /67% капитала/, 'инвестиции — 1 000 из 1 500 капитала');
  assert.match(head(html, 'РЕЗЕРВ'), /33% капитала/, 'резерв — 500 из 1 500');
  assert.match(head(html, 'ИНВЕСТИЦИИ'), /инвестиции \+ резерв = 1 500 €/, 'не названо, что считается капиталом');
  assert.ok(!head(html, 'ПОЛЬЗОВАТЕЛЬСКИЕ').includes('капитала'), 'вещи не в капитале, а доля показана');
});

test('телефон: карточки рисуются и считают доли в тех же рамках', () => {
  // у телефонной вёрстки не было ни одного теста — она успела сломаться совсем
  // (обращение к цели до её объявления), и портфель на телефоне не открывался вовсе.
  const html = loadFin(true).secPortfolio(DATA, DATA.summary);
  const card = html.split('<div class="pcard').find(c => c.includes('Актив A'));
  assert.ok(card, 'карточка актива не отрисовалась');
  const txt = card.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ');
  assert.match(txt, /доля 75.0% \/ 45.0%/, 'доли суммы на телефоне считаются иначе, чем в таблице');
  assert.match(txt, /в цели в «Акции» 83.3%/, 'нет доли цели внутри раздела');
  assert.match(txt, /цель: 33.3%/, 'доля цели в части не та же, что в таблице');
  assert.ok(card.includes('data-fgoalpct'), 'на телефоне долю цели нечем вписать');
});

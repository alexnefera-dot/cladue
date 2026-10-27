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

function loadFin() {
  const ctx = {
    document: { querySelectorAll: () => [], getElementById: () => null, addEventListener() {},
      createElement: () => ({ addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
        dataset: {}, style: {}, innerHTML: '', value: '' }) },
    console, localStorage: {}, fetch: async () => ({ ok: true, json: async () => ({}) }),
    alert() {}, confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  return ctx;
}

const asset = (id, name, value, target) => ({ id, name, kind: 'asset', children: [],
  value, eur: value, currency: '€', target_value: target });

// Инвестиции 1000 €: блок «Рост» 800 (раздел «Акции» 600 = A 450 + B 150) и блок «Крипта» 200.
// Цели: A 500, B 100, Крипта 400 — раздел 600, часть 1000.
const DATA = {
  summary: { portfolioTotal: 1000, portfolioTotalUsd: 1080, rate: 1.08 },
  portfolio: [], targetMoves: [],
  targetPortfolio: [
    { id: 1, name: 'Рост', kind: 'block', side: 'act', eur: 800, children: [
      { id: 2, name: 'Акции', kind: 'section', eur: 600, currency: '€', children: [
        asset(3, 'Актив A', 450, 500), asset(4, 'Актив B', 150, 100)] }] },
    { id: 5, name: 'Крипта', kind: 'block', side: 'act', eur: 200, children: [asset(6, 'BTC', 200, 400)] },
    { id: 7, name: 'Вещи', kind: 'block', side: 'use', eur: 300, children: [asset(8, 'Машина', 300, 300)] },
  ],
  targetByType: [], targetByTypeBlocks: {}, byType: [], byRegion: [], byTypeBlocks: {}, byRegionBlocks: {},
  blockEur: {}, rates: [{ symbol: 'IVV', price: 500 }], saveGoals: [], historyRows: [], history: [],
};

// доли строки: содержимое <span class="sub"> в колонке «Сейчас» / «Цель»
const rowOf = (html, name) => (html.match(new RegExp(`<tr class="[^"]*" draggable[^>]*>(?:(?!</tr>)[\\s\\S])*?${name}[\\s\\S]*?</tr>`)) || [''])[0];
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

test('доли цели живут в тех же рамках, что и доли суммы', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  // цель A 500: 83.3% цели раздела (600) и 50.0% цели части (1000)
  assert.equal(nums(rowOf(html, 'Актив A'))[1], '83.3% / 50.0%', 'доли цели считаются от чужих сумм');
  assert.equal(nums(rowOf(html, 'Акции'))[1], '100.0% / 60.0%', 'цель раздела: вся цель блока и 60% цели части');
});

test('в подсказке названо, от чего процент', () => {
  const row = rowOf(loadFin().secPortfolio(DATA, DATA.summary), 'Актив A');
  assert.match(row, /title="доля в «Акции» \/ доля в части «ИНВЕСТИЦИИ»"/, 'рамки доли не названы');
  assert.match(row, /title="цель долей в части «ИНВЕСТИЦИИ» \(клик закрепит её\)"/,
    'непонятно, в каких рамках задаётся кликом процент цели');
});

test('доли своей части, а не общего капитала: вещи считаются от вещей', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  // «Машина» — единственное в своей части, значит 100% её, хотя от капитала это 30%
  assert.equal(nums(rowOf(html, 'Машина'))[0], '100.0% / 100.0%', 'часть «вещи» считается от чужого тотала');
  assert.match(rowOf(html, 'Машина'), /доля в части «ПОЛЬЗОВАТЕЛЬСКИЕ АКТИВЫ»/, 'не названа своя часть');
});

test('без разбивки на части рамка верхнего уровня — весь портфель', () => {
  const one = { ...DATA, targetPortfolio: DATA.targetPortfolio.filter(n => n.side === 'act') };
  const html = loadFin().secPortfolio(one, one.summary);
  assert.match(rowOf(html, 'Актив A'), /доля в «Акции» \/ доля в портфеле/, 'рамка без частей названа неверно');
});

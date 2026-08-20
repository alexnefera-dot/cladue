import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// public/fin.js — браузерный скрипт, он не импортируется и не покрыт остальными тестами.
// Здесь он выполняется в песочнице с заглушками DOM и отрисовывается на обеих вкладках:
// это ловит ReferenceError/TypeError в шаблонах, которые `node --check` пропускает,
// потому что синтаксически файл остаётся корректным.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));

function loadFin() {
  const el = () => ({ addEventListener() {}, appendChild() {}, replaceWith() {}, focus() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '' });
  const ctx = {
    document: { querySelectorAll: () => [], getElementById: () => null, createElement: el, addEventListener() {} },
    console, localStorage: { getItem: () => null, setItem() {} },
    fetch: async () => ({ json: async () => ({}) }),
    alert() {}, confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  return ctx;
}

const leaf = (id, name, o = {}) => ({
  id, name, kind: 'asset', children: [],
  value: o.value ?? 100, eur: o.eur ?? 100, target: o.target ?? 100, target_value: o.target_value ?? 100,
  currency: o.cur ?? '€', asset_type: o.ty ?? 'акции', ...o,
});

// целевой намеренно с «сложными» местами: свой план у раздела, $-позиция, автоцена и перенос между листьями
const DATA = {
  summary: { portfolioTotal: 1000, portfolioTotalUsd: 1080, rate: 1.08 },
  portfolio: [{ id: 1, name: 'Блок', kind: 'block', value: 100, eur: 100,
    children: [leaf(2, 'SCHD'), leaf(3, 'Квартира', { ty: 'недвижка UA' })] }],
  targetPortfolio: [{ id: 10, name: 'Блок', kind: 'block', value: 300, eur: 300, target: 300,
    children: [{ id: 11, name: 'Раздел', kind: 'section', currency: '€', target_value: 500, children: [
      leaf(12, 'SCHD'),
      leaf(13, 'BTC', { cur: '$', ty: 'крипто' }),
      leaf(14, 'ETF', { cur: '$', auto: true, qty: 10, rate_symbol: 'IVV' }),
    ] }] }],
  targetMoves: [{ id: 1, from_id: 12, to_id: 13, amount: 50 }],
  targetByType: [['акции', 100]], targetByTypeBlocks: { 'акции': { 'Блок': 100 } },
  byType: [['акции', 100]], byRegion: [], byTypeBlocks: {}, byRegionBlocks: {}, blockEur: {},
  rates: [{ symbol: 'IVV', price: 500 }],
};

test('портфель отрисовывается без ошибок', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.equal(typeof html, 'string');
  assert.ok(html.length > 500, 'разметка не пустая');
});

test('экран один: вкладок «Факт»/«Целевой» нет', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(!html.includes('data-fintab'), 'переключатель вкладок остался');
  assert.ok(!/>Факт</.test(html), 'вкладка «Факт» осталась');
});

test('строки совпадают с шапкой по числу колонок', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  const head = html.match(/<tr><th>Название<\/th>[\s\S]*?<\/tr>/)[0];
  const cols = (head.match(/<th/g) || []).length;
  const rows = [...html.matchAll(/<tr class="[^"]*" draggable[\s\S]*?<\/tr>/g)];
  assert.ok(rows.length > 0, 'строк нет');
  for (const [r] of rows) assert.equal((r.match(/<td/g) || []).length, cols, 'строка не совпала с шапкой');
});

test('целевой: колонки и блок мониторинга на месте', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  for (const part of ['Покупка', 'Прирост', 'Сейчас', 'Станет', 'Цель', 'Отклонение', 'Перестановки',
                      'stackwrap', 'stacklab', 'btrack', 'btick', 'data-cat']) {
    assert.ok(html.includes(part), `в целевом нет «${part}»`);
  }
});

test('форма переноса появляется только по клику и нигде больше', () => {
  const ctx = loadFin();
  assert.ok(!ctx.secPortfolio(DATA, DATA.summary).includes('tgtform'), 'форма видна без клика');
  vm.runInContext('tgtMove = { from: 12, to: null, amount: null }', ctx);
  const open = ctx.secPortfolio(DATA, DATA.summary);
  assert.ok(open.includes('tgtform'), 'форма не раскрылась');
  assert.equal((open.match(/class="tgtform-row"/g) || []).length, 1, 'форма должна быть ровно одна');
});

// Правки Swift доезжают только пересборкой в Xcode, фронт обновляется сам — предупреждение
// в шапке единственный способ увидеть, что бэкенд ещё старый (иначе правки молча не работают).
function renderHead(ctx, version) {
  const node = { addEventListener() {}, appendChild() {}, replaceWith() {}, focus() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '' };
  ctx.document.getElementById = () => node;
  // finData/finBuild объявлены через let — в песочнице это не свойства глобала, только присваиванием
  ctx.__data = { ...DATA, accounts: [], budgetItems: [],
    summary: { ...DATA.summary, accountsByCurrency: { '€': 100 } } };
  ctx.__build = version;
  vm.runInContext('finSection = "__none__"; finData = __data; finBuild = __build', ctx);   // разделы не рисуем — нужна только шапка
  ctx.renderFin();
  return node.innerHTML;
}

test('старая сборка приложения: в шапке предупреждение о пересборке', () => {
  const ctx = loadFin();
  const html = renderHead(ctx, { platform: 'Mac', buildDate: '2026-07-01 10:00' });
  assert.ok(html.includes('staleapp'), 'нет предупреждения про старую сборку');
  assert.ok(html.includes('2026-07-01'), 'не видно, какая сборка стоит');
});

test('свежая сборка и node-прототип: предупреждения нет', () => {
  assert.ok(!renderHead(loadFin(), { platform: 'Mac', buildDate: '2999-01-01 10:00' }).includes('staleapp'));
  assert.ok(!renderHead(loadFin(), null).includes('staleapp'), 'без /api/version предупреждения быть не должно');
});

test('цель: закреплено то поле, что заполнено', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(html.includes('target_pct'), 'нет поля доли');
  assert.ok(html.includes('ed pinned'), 'закреплённое поле не помечено');
});

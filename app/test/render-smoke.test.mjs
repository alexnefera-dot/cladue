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

// две части: активы 300 € и пассивы 100 € — доли внутри части должны считаться от неё,
// а не от общего капитала (иначе машина показала бы 25%, а не 100%)
const SPLIT = {
  ...DATA, targetMoves: [],
  targetPortfolio: [
    { id: 10, name: 'Работает', kind: 'block', eur: 300, children: [leaf(12, 'SCHD', { value: 300, eur: 300, target_value: 300 })] },
    { id: 20, name: 'Имущество', kind: 'block', passive: 1, eur: 100,
      children: [leaf(21, 'Машина', { value: 100, eur: 100, target_value: 100 })] },
  ],
};
// текст строки над таблицей без тегов: числа разбиты <b>, а разряды — неразрывным пробелом
const capLine = html => ((html.match(/<div class="capline">[\s\S]*?<\/div>/) || [''])[0])
  .replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').replace(/ /g, ' ').trim();
const rowOf = (html, name) => (html.match(new RegExp(`<tr class="[^"]*" draggable[\\s\\S]*?${name}[\\s\\S]*?</tr>`)) || [''])[0];

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

test('две части: шапки «АКТИВЫ»/«ПАССИВЫ» со своими итогами', () => {
  const html = loadFin().secPortfolio(SPLIT, SPLIT.summary);
  assert.ok(html.includes('parthead'), 'шапок частей нет');
  assert.ok(/>АКТИВЫ\s/.test(html) && /ПАССИВЫ/.test(html), 'части не подписаны');
  const head = html.match(/<tr><th>Название<\/th>[\s\S]*?<\/tr>/)[0];
  const cols = (head.match(/<th/g) || []).length;
  for (const [r] of html.matchAll(/<tr class="parthead">[\s\S]*?<\/tr>/g))
    assert.equal((r.match(/<td/g) || []).length, cols, 'шапка части не совпала с сеткой колонок');
});

test('над таблицей — тонкая строка: расхождение с целевым, без дубля общей суммы', () => {
  const html = loadFin().secPortfolio(SPLIT, SPLIT.summary);
  const line = capLine(html);
  assert.ok(line, 'строки над таблицей нет');
  assert.ok(!html.includes('ОБЩИЙ КАПИТАЛ') && !html.includes('capsum'), 'плашка капитала осталась');
  assert.ok(line.includes('цель 400 €') && line.includes('✓ сейчас = плану'), 'цель и расхождение не выведены');
});

test('трата вычитается из активов, а не из всего капитала', () => {
  const spend = { ...SPLIT, targetMoves: [{ id: 1, from_id: 12, to_id: null, amount: 50, to_note: 'айфон' }] };
  const line = capLine(loadFin().secPortfolio(spend, spend.summary));
  assert.ok(line.includes('на траты') && line.includes('50 €'), 'трата не показана');
  assert.ok(line.includes('от активов останется') && line.includes('250 €'),
    'остаток должен быть 300 − 50 по активам, а не 400 − 50 по всему капиталу');
});

test('две части: доли и цели считаются внутри своей части', () => {
  const html = loadFin().secPortfolio(SPLIT, SPLIT.summary);
  const car = rowOf(html, 'Машина');
  assert.ok(car, 'строки пассива нет');
  assert.ok(car.includes('100.0%'), 'доля пассива должна считаться от пассивов');
  assert.ok(!car.includes('25.0%'), 'доля посчиталась от общего капитала, а не от своей части');
  assert.ok(car.includes('✓ в цели'), 'цель пассива 100 при 100 € — отклонения быть не должно');
});

test('две части: цель долей берётся от своей части, а не от общего капитала', () => {
  const pct = { ...SPLIT, targetPortfolio: [SPLIT.targetPortfolio[0],
    { ...SPLIT.targetPortfolio[1], children: [leaf(21, 'Машина', { value: 100, eur: 100, target_value: null, target_pct: 50 })] }] };
  const car = rowOf(loadFin().secPortfolio(pct, pct.summary), 'Машина');
  assert.ok(car.includes('>50<'), 'цель 50% от пассивов (100 €) должна дать 50 €, а не 200 от общих 400');
  assert.ok(/dev-over[^>]*>\+50/.test(car), 'отклонение +50 € (100 при цели 50) не посчиталось');
});

test('ничего не помечено — экран прежний, без шапок частей', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(!html.includes('parthead'), 'части появились там, где их не просили');
  assert.ok(!html.includes('capsplit'), 'разбивка капитала показана без пассивов');
});

// вещь живёт позицией в пассивах, её содержание — в Расходах; связывает их метка в строке
const UPKEEP = {
  ...SPLIT, rates: [{ symbol: 'EURUSD', price: 1.08 }], accounts: [], budgetItems: [],
  obligations: [
    { id: 1, item_id: 21, name: 'Машина: страховка', amount: 1200, currency: '€', period: 'yearly', next_date: null, remind_days: 7, kind: 'liability' },
    { id: 2, item_id: 21, name: 'Машина: ТО', amount: 60, currency: '€', period: 'monthly', next_date: null, remind_days: 7, kind: 'liability' },
    { id: 3, item_id: null, name: 'Netflix', amount: 15, currency: '€', period: 'monthly', next_date: null, remind_days: 5, kind: 'subscription' },
  ],
};

test('содержание имущества: сгруппировано по вещи и посчитано в месяц', () => {
  const html = loadFin().secSpending(UPKEEP).replace(/ /g, ' ');   // fmt разделяет разряды неразрывным пробелом
  assert.ok(html.includes('СОДЕРЖАНИЕ ИМУЩЕСТВА'), 'группы содержания нет');
  assert.ok(html.includes('160 / мес') && html.includes('1 920 / год'), '1200/год + 60/мес = 160 €/мес не посчитались');
  assert.ok(html.includes('data-ruleadd="21"'), 'регламент нельзя добавить к позиции');
  assert.ok(html.includes('ОСТАЛЬНОЕ') && html.includes('Netflix'), 'обязательства без вещи потерялись');
});

test('содержание видно в строке позиции портфеля', () => {
  const html = loadFin().secPortfolio(UPKEEP, UPKEEP.summary);
  assert.match(html, /🔧 160 €\/мес/, 'в строке вещи нет метки содержания');
});

test('содержание не пропадает, когда позицию из портфеля удалили', () => {
  const orphan = { ...UPKEEP, propNames: [{ id: 7, name: 'BMW X5' }],
    obligations: [{ id: 9, item_id: 999, property_id: 7, name: 'BMW X5: ТО', amount: 50, currency: '€', period: 'monthly', next_date: null, remind_days: 7, kind: 'liability' }] };
  const html = loadFin().secSpending(orphan);
  assert.ok(html.includes('СОДЕРЖАНИЕ ИМУЩЕСТВА'), 'группа исчезла вместе с позицией');
  assert.ok(html.includes('BMW X5') && html.includes('вещи нет в портфеле'), 'вещь не подписана');
});

test('история капитала: две линии и «заработано»', () => {
  const rows = [
    { date: '2026-01-31', portfolio_eur: 300, active_eur: 250, passive_eur: 50, invested_eur: 240 },
    { date: '2026-02-28', portfolio_eur: 340, active_eur: 290, passive_eur: 50, invested_eur: 250 },
  ];
  const html = loadFin().capHistory(rows, 'act').replace(/ /g, ' ');
  assert.ok(html.includes('sp-val') && html.includes('sp-inv'), 'нарисована не та пара линий');
  assert.ok(html.includes('внесено') && html.includes('250 €'), 'внесённое не выведено');
  assert.ok(html.includes('+40 €'), 'заработанное 290 − 250 не посчиталось');
});

test('история: одного снимка мало — говорим об этом, а не рисуем пустой график', () => {
  const html = loadFin().capHistory([{ date: '2026-02-28', portfolio_eur: 340 }], 'all');
  assert.ok(!html.includes('<svg'), 'график нарисован по одной точке');
  assert.ok(html.includes('снимок пишется раз в день'), 'нет объяснения, почему пусто');
});

test('цель: закреплено то поле, что заполнено', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(html.includes('target_pct'), 'нет поля доли');
  assert.ok(html.includes('ed pinned'), 'закреплённое поле не помечено');
});

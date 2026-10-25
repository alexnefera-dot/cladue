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
  .replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').replace(/\u00a0/g, ' ').trim();
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

test('две части: шапки «ИНВЕСТИЦИИ»/«ПОЛЬЗОВАТЕЛЬСКИЕ» со своими итогами', () => {
  const html = loadFin().secPortfolio(SPLIT, SPLIT.summary);
  assert.ok(html.includes('parthead'), 'шапок частей нет');
  assert.ok(/ИНВЕСТИЦИИ/.test(html) && /ПОЛЬЗОВАТЕЛЬСКИЕ АКТИВЫ/.test(html), 'части не подписаны');
  const head = html.match(/<tr><th>Название<\/th>[\s\S]*?<\/tr>/)[0];
  const cols = (head.match(/<th/g) || []).length;
  for (const [r] of html.matchAll(/<tr class="parthead[^"]*">[\s\S]*?<\/tr>/g))
    assert.equal((r.match(/<td/g) || []).length, cols, 'шапка части не совпала с сеткой колонок');
});

test('над таблицей — тонкая строка: расхождение с целевым, без дубля общей суммы', () => {
  const html = loadFin().secPortfolio(SPLIT, SPLIT.summary);
  const line = capLine(html);
  assert.ok(line, 'строки над таблицей нет');
  assert.ok(!html.includes('ОБЩИЙ КАПИТАЛ') && !html.includes('capsum'), 'плашка капитала осталась');
  assert.ok(line.includes('цель 300 €') && line.includes('✓ сейчас = плану'),
    'цель капитала — только инвестиции, пользовательские активы в неё не входят');
});

test('трата вычитается из активов, а не из всего капитала', () => {
  const spend = { ...SPLIT, targetMoves: [{ id: 1, from_id: 12, to_id: null, amount: 50, to_note: 'айфон' }] };
  const line = capLine(loadFin().secPortfolio(spend, spend.summary));
  assert.ok(line.includes('на траты') && line.includes('50 €'), 'трата не показана');
  assert.ok(line.includes('от активов останется') && line.includes('250 €'),
    'остаток должен быть 300 − 50 по активам, а не 400 − 50 по всему капиталу');
});

test('пять частей: капитал — инвестиции и резерв; остальное фиксируется внизу', () => {
  const five = { ...SPLIT, targetPortfolio: [
    SPLIT.targetPortfolio[0],
    { id: 15, name: 'Запас', kind: 'block', side: 'safe', eur: 50,
      children: [leaf(16, 'Кэш', { value: 50, eur: 50, target_value: 50 })] },
    { ...SPLIT.targetPortfolio[1], side: 'pas' },
    { id: 25, name: 'Недвижка', kind: 'block', side: 'frozen', eur: 400,
      children: [leaf(26, 'Квартира UA', { value: 400, eur: 400, target_value: 400 })] },
    { id: 30, name: 'Долги', kind: 'block', side: 'debt', eur: 250,
      children: [leaf(31, 'Кредит', { value: 250, eur: 250, target_value: 250 })] }] };
  const html = loadFin().secPortfolio(five, five.summary).replace(/\u00a0/g, ' ');
  const heads = [...html.matchAll(/<tr class="parthead[^"]*">[\s\S]*?<\/tr>/g)].map(m => m[0]);
  assert.equal(heads.length, 5, 'частей должно быть пять');
  assert.ok(heads[1].includes('РЕЗЕРВ') && heads[1].includes('% капитала'), 'резерв — часть капитала');
  for (const i of [2, 3, 4]) {
    assert.ok(heads[i].includes('partoff'), 'вещи, заморозка и долги должны быть отбиты от капитала');
    assert.ok(!heads[i].includes('% капитала'), 'у частей вне капитала не должно быть его доли');
  }
  assert.ok(heads[3].includes('ЗАМОРОЖЕННЫЕ АКТИВЫ') && heads[4].includes('ОБЯЗАТЕЛЬСТВА'), 'части не на своих местах');
  assert.ok(capLine(html).includes('цель 350 €'), 'цель капитала: 300 инвестиций + 50 резерва');
  const all = (html.match(/<tr class="partall">[\s\S]*?<\/tr>/) || [''])[0];
  assert.ok(all.includes('600 €'), 'сводка всего: 350 + 100 + 400 − 250');
  assert.ok(all.includes('648 $'), 'в сводке нет доллара по курсу 1.08');
  assert.ok(!all.includes('капитал 350'), 'расшифровка повторяет таблицу — её быть не должно');
  assert.ok(html.includes('data-fside="25:frozen"') && html.includes('data-fside="30:debt"'), 'переключателей частей нет');
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

test('обязательства — свой список, без групп по позициям портфеля', () => {
  const html = loadFin().secSpending(UPKEEP).replace(/\u00a0/g, ' ');
  assert.ok(!html.includes('СОДЕРЖАНИЕ ИМУЩЕСТВА'), 'группировка по вещам портфеля вернулась');
  for (const o of UPKEEP.obligations)
    assert.ok(html.includes(`obligations:${o.id}:name:text`), `обязательство «${o.name}» пропало из списка`);
  assert.ok(html.includes('Подписки') && html.includes('Регулярные платежи'),
    'обязательства должны делиться по типам платежа');
  assert.ok(html.includes('всего затрат за год'), 'итог по обязательствам потерялся');
});

test('содержание живёт только в расходах, в строке портфеля его нет', () => {
  const html = loadFin().secPortfolio(UPKEEP, UPKEEP.summary);
  assert.ok(!html.includes('🔧'), 'метка содержания вернулась в строку портфеля');
});

test('история капитала: две линии и «заработано»', () => {
  const rows = [
    { date: '2026-01-31', portfolio_eur: 300, active_eur: 250, passive_eur: 50, invested_eur: 240 },
    { date: '2026-02-28', portfolio_eur: 340, active_eur: 290, passive_eur: 50, invested_eur: 250 },
  ];
  const html = loadFin().capHistory(rows, 'act').replace(/\u00a0/g, ' ');
  assert.ok(html.includes('sp-val') && html.includes('sp-inv'), 'нарисована не та пара линий');
  assert.ok(html.includes('внесено') && html.includes('250 €'), 'внесённое не выведено');
  assert.ok(html.includes('+40 €'), 'заработанное 290 − 250 не посчиталось');
});

test('история: одного снимка мало — говорим об этом, а не рисуем пустой график', () => {
  const html = loadFin().capHistory([{ date: '2026-02-28', portfolio_eur: 340 }], 'all');
  assert.ok(!html.includes('<svg'), 'график нарисован по одной точке');
  assert.ok(html.includes('снимок пишется раз в день'), 'нет объяснения, почему пусто');
});

test('сведение капитала: только отмеченные 🎓, гео берётся из общей таблицы', () => {
  const ctx = loadFin();
  const tree = [{ id: 10, name: 'Рост', kind: 'block', eur: 229000, children: [
    leaf(12, 'SCHD', { eur: 120000, digest: 1, region: 'EU' }),
    leaf(13, 'Квартира', { eur: 80000, digest: 1, region: 'UA' }),
    leaf(14, 'Депозит', { eur: 20000, digest: 1, region: 'EU' }),
    leaf(15, 'BTC', { eur: 9000, digest: 1 }),
    leaf(16, 'Мимо', { eur: 500000 }),
  ] }];
  const html = ctx.secDigest(tree).replace(/\u00a0/g, ' ');
  assert.ok(!html.includes('Мимо'), 'в свод попала неотмеченная позиция');
  assert.ok(html.includes('140 000 €') && html.includes('80 000 €'), 'EU 120+20 и UA 80 не сложились');
  assert.ok(html.includes('85.7%'), 'доля внутри своей географии не посчиталась');
  assert.ok(html.includes('52.4%'), 'доля от всего свода не посчиталась');
  assert.ok(html.includes('Без региона') && html.includes('задай 🌍'), 'позиция без гео потерялась');
  assert.ok(!html.includes('Вход'), 'колонка входа не нужна там, где нет ⚡-позиций');
  assert.equal(ctx.secDigest([{ id: 1, name: 'Блок', kind: 'block', eur: 0, children: [leaf(2, 'X')] }]), '',
    'без отметок блока быть не должно');
});

test('свод: у ⚡ идёт цена входа, своя сумма живёт до правки главной', () => {
  const ctx = loadFin();
  const mk = extra => [{ id: 10, name: 'Рост', kind: 'block', eur: 0, children: [
    leaf(12, 'IVV', { value: 20000, eur: 20000, invested: 18000, buy_value: 18000, rate_symbol: 'IVV', qty: 4, digest: 1, region: 'EU', ...extra }) ] }];
  const plain = ctx.secDigest(mk({})).replace(/\u00a0/g, ' ');
  assert.ok(plain.includes('>вход<'), 'не помечено, что это вход');
  const seen = plain.replace(/<[^>]+>/g, ' ');   // текущая сумма остаётся в подсказке, но не на экране
  assert.ok(seen.includes('18 000'), 'у ⚡-позиции должна стоять цена входа');
  assert.ok(!seen.includes('20 000'), 'текущая сумма у ⚡-позиции в своде не нужна');

  // без ⚡ берётся текущая сумма
  const plainNoRate = ctx.secDigest([{ id: 10, name: 'Рост', kind: 'block', eur: 0, children: [
    leaf(12, 'Квартира', { value: 80000, eur: 80000, invested: 60000, buy_value: 60000, digest: 1, region: 'UA' }) ] }])
    .replace(/\u00a0/g, ' ');
  assert.ok(plainNoRate.replace(/<[^>]+>/g, ' ').includes('80 000') && !plainNoRate.includes('60 000'),
    'у позиции без ⚡ в своде должна стоять текущая сумма');

  // правка действует: база совпала с «Сейчас»
  const own = ctx.secDigest(mk({ digest_value: 25000, digest_base: 20000 })).replace(/\u00a0/g, ' ');
  assert.ok(own.includes('25 000') && own.includes('dgown'), 'своя сумма не подхватилась');
  assert.ok(own.includes('data-dgclr'), 'нет способа вернуть сумму из главной');

  // «Сейчас» изменилось — правка больше не действует
  const stale = ctx.secDigest(mk({ value: 21000, eur: 21000, invested: 19000, buy_value: 19000,
    digest_value: 25000, digest_base: 20000 })).replace(/\u00a0/g, ' ');
  assert.ok(stale.replace(/<[^>]+>/g, ' ').includes('19 000') && !stale.includes('25 000'),
    'после правки главной свод должен вернуться к своей цифре');
});

test('шапка: в капитале нет заморозки и семейного, но всего они видны', () => {
  const ctx = loadFin();
  const blk = (id, name, side, eur, usd) => ({ id, name, kind: 'block', side, eur,
    usdPart: usd || 0, eurPart: usd ? 0 : eur, children: [leaf(id + 1, name + '·1', { value: eur, eur })] });
  const d = { ...DATA, accounts: [], budgetItems: [], obligations: [],
    targetPortfolio: [blk(10, 'Рост', 'act', 300, 108), blk(20, 'Вещи', 'pas', 100),
      blk(25, 'Недвижка', 'frozen', 400), blk(30, 'Долги', 'debt', 250)],
    summary: { ...DATA.summary, rate: 1.08, portfolioTotal: 1050, accountsByCurrency: {} } };
  const node = { addEventListener() {}, appendChild() {}, replaceWith() {}, focus() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '' };
  ctx.document.getElementById = () => node;
  ctx.__d = d;
  vm.runInContext('finSection = "__none__"; finHide = false; finData = __d; finBuild = null', ctx);
  ctx.renderFin();
  const html = node.innerHTML.replace(/\u00a0/g, ' ');
  const big = (html.match(/КАПИТАЛ<\/div>\s*<div class="bignum">([\s\S]*?)<\/div>/) || [])[1] || '';
  assert.ok(big.includes('300 €'), 'капитал — только инвестиции и резерв');
  assert.ok(!big.includes('1 050'), 'в крупном числе шапки сумма со всем подряд');
  assert.ok(html.includes('вне капитала 500 €') && html.includes('долги −250 €') && html.includes('всего 550 €'),
    'не видно, что стоит вне капитала, сколько долгов и сколько всего');
  assert.ok(html.includes('108 $'), 'валютный разрез должен считаться по капиталу');
});

test('счета: карточка сверху и итог в разделе считают одно и то же', () => {
  const ctx = loadFin();
  const accounts = [
    { id: 1, name: 'Брокер', type: 'broker', currency: '€', balance: 50300, balance_updated_at: '2026-08-01', stale_days: 2 },
    { id: 2, name: 'Кэш', type: 'cash', currency: '$', balance: 1080, balance_updated_at: null, stale_days: 0 },
  ];
  const d = { ...DATA, accounts, budgetItems: [], obligations: [],
    summary: { ...DATA.summary, rate: 1.08, accountsByCurrency: { '€': 999999 } } };   // сводка с бэкенда намеренно врёт
  const node = { addEventListener() {}, appendChild() {}, replaceWith() {}, focus() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '' };
  ctx.document.getElementById = () => node;
  ctx.__d = d;
  vm.runInContext('finSection = "acc"; finHide = false; finData = __d; finBuild = null', ctx);
  ctx.renderFin();
  const html = node.innerHTML.replace(/\u00a0/g, ' ');
  assert.ok(!html.includes('999 999'), 'карточка сверху всё ещё берёт сводку с бэкенда');
  assert.equal((html.match(/50 300 € · 1 080 \$/g) || []).length, 2, 'карточка и итог раздела должны показывать одно');
  assert.ok(html.includes('обн. —'), 'счёт без даты обновления не должен ронять раздел');
  assert.ok(html.includes('бэкенд считает иначе'), 'расхождение со сводкой должно быть названо числом');
});

test('история: свои группы и пункты, исключённая группа мимо итога', () => {
  const ctx = loadFin();
  const rows = [
    { id: 1, parent_id: null, name: '2024 · продажи', ord: 1 },
    { id: 2, parent_id: 1, name: 'Авто', amount: 12000, currency: '€' },
    { id: 3, parent_id: 1, name: 'Бонус', amount: 5400, currency: '$' },
    { id: 4, parent_id: null, name: 'Идеи', ord: 2, excluded: 1 },
    { id: 5, parent_id: 4, name: 'Квартира', amount: 60000, currency: '€' },
  ];
  const html = ctx.secHistory(rows, 1.08).replace(/\u00a0/g, ' ');
  assert.ok(html.includes('17 000 €'), 'группа не сложила 12 000 € и 5 400 $ по курсу');
  assert.ok(!html.includes('не в итоге') && !html.includes('мимо итога'), 'подписей у исключённой группы быть не должно');
  assert.ok(!html.includes('77 000'), 'исключённая группа всё ещё попадает в итог');
  assert.ok(html.indexOf('Идеи') < html.indexOf('2024 · продажи'), 'исключённая группа должна стоять наверху');
  assert.ok(html.includes('hcut'), 'нет черты между исключёнными и считаемыми');
  assert.ok(!/\d%/.test(html), 'процентов в этом блоке быть не должно');
  assert.ok(html.includes('data-hadd="1"') && html.includes('data-hadd=""'),
    'должны быть и добавление пункта в группу, и добавление группы');
  assert.equal((html.match(/draggable="true"/g) || []).length, 5, 'перетаскиваться должны все строки');
  assert.ok(ctx.secHistory([], 1.08).includes('групп пока нет'), 'пустой блок ничего не объясняет');
});

test('история: своя сумма группы в ходу, пока внутри пусто', () => {
  const ctx = loadFin();
  const html = ctx.secHistory([
    { id: 1, parent_id: null, name: 'Просто сумма', amount: 5000, currency: '€', ord: 1 },
    { id: 2, parent_id: null, name: 'С пунктами', amount: 999, currency: '€', ord: 2 },
    { id: 3, parent_id: 2, name: 'Пункт', amount: 1200, currency: '€' },
  ], 1.08).replace(/\u00a0/g, ' ');
  assert.ok(html.includes('data-fe="hist:1:amount:num"'), 'сумму пустой группы нельзя ни увидеть, ни поправить');
  assert.ok(html.includes('>5 000<'), 'введённая сумма группы потерялась');
  assert.ok(html.includes('1 200 €') && !html.includes('999'), 'у группы с пунктами считаем по пунктам');
  assert.ok(html.includes('6 200 €'), 'итог: 5 000 своей суммой + 1 200 по пунктам');
});

test('история: подпункт вычитается из пункта и из группы', () => {
  const ctx = loadFin();
  const html = ctx.secHistory([
    { id: 1, parent_id: null, name: 'Бюджет', ord: 1 },
    { id: 2, parent_id: 1, name: 'Ремонт', amount: 12000, currency: '€' },
    { id: 3, parent_id: 2, name: 'Окна', amount: 3000, currency: '€' },
    { id: 4, parent_id: 2, name: 'Двери', amount: 1000, currency: '€' },
    { id: 5, parent_id: 1, name: 'Мебель', amount: 5000, currency: '€' },
  ], 1.08).replace(/\u00a0/g, ' ');
  assert.ok(html.includes('осталось 8 000 €'), '12 000 − 3 000 − 1 000 не посчиталось');
  assert.ok(html.includes('− 3 000 €') && html.includes('dgsub'), 'подпункт не показан вычитанием');
  const totals = [...html.matchAll(/13 000 €/g)];
  assert.equal(totals.length, 2, 'группа и общий итог должны быть 8 000 + 5 000');
  assert.ok(html.includes('data-hsub="2"'), 'у пункта нет кнопки добавить подпункт');
  assert.ok(html.includes('data-hlvl="2"'), 'подпункт не помечен уровнем для перетаскивания');
});

test('расходы и доходы — два блока, оба свёрнуты, итоги видны в заголовке', () => {
  const items = [
    { id: 1, direction: 'expense', name: 'Аренда', amount: 900, currency: '€' },
    { id: 2, direction: 'expense', name: 'Еда', amount: 400, currency: '€' },
    { id: 3, direction: 'income', name: 'Зарплата', amount: 5000, currency: '€', month: '2026-09' },
  ];
  const html = loadFin().renderBudget(items, [{ symbol: 'EURUSD', price: 1.08 }]).replace(/\u00a0/g, ' ');
  const secs = [...html.matchAll(/<div class="sec">([\s\S]*?)<\/div>/g)]
    .map(m => m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
  assert.equal(secs.length, 3, 'баланс, расходы и доходы — три отдельных блока');
  assert.ok(secs[0].startsWith('Баланс') && secs[1].startsWith('Расходы') && secs[2].startsWith('Доходы'), 'блоки не те');
  assert.ok(secs[1].includes('1 300 €') && secs[1].includes('2 статей'), 'в заголовке расходов нет итога');
  assert.ok(secs[2].includes('5 000 €'), 'в заголовке доходов нет итога');
  // числа заголовка живут в .pr — свёртка прячет именно их
  for (const sec of [secs[0], secs[1], secs[2]]) assert.ok(sec.length, 'пустой заголовок');
  assert.equal((html.match(/<span class="pr">/g) || []).length, 3, 'итоги в заголовках должны быть в .pr, иначе их не скрыть');
});

test('цели накопления: прогресс, сумма от дохода и отметка за месяц', () => {
  const ctx = loadFin();
  const html = ctx.secSaveGoals([
    { id: 1, name: 'Фан-кар', note: '370Z · M2', target: 15000, pct_min: 5, pct_max: 5,
      saved: 3200, thisMonth: 0, incomeMonth: 6000, incomeYm: '2026-09', log: [{ id: 9, date: '2026-09-01', amount: 300 }] },
    { id: 2, name: 'EXUS', target: null, pct_min: 10, pct_max: 30,
      saved: 12000, thisMonth: 800, incomeMonth: 6000, incomeYm: '2026-09', log: [] },
  ]).replace(/\u00a0/g, ' ');
  assert.ok(html.includes('3 200 €') && html.includes('из 15 000 €'), 'накопленное и цель не выведены');
  assert.ok(html.includes('width:21.3%'), 'прогресс 3200 из 15000 не посчитался');
  assert.ok(html.includes('5% дохода за сентябрь · это 300 €'), 'сумма взноса от дохода прошлого месяца не посчитана');
  assert.ok(html.includes('10–30% дохода за сентябрь · это 600–1 800 €'), 'вилка процентов не раскрыта в суммы');
  assert.ok(html.includes('data-saveput="1"'), 'нечем отложить по невыполненной цели');
  assert.ok(html.includes('✓ в этом месяце 800 €') && !html.includes('data-saveput="2"'),
    'по выполненной за месяц цели кнопка не должна предлагаться');
  assert.ok(html.includes('data-savedel="9"'), 'взнос нельзя убрать');
  assert.equal(ctx.secSaveGoals([]), '', 'без целей блока быть не должно');
});

test('цели накопления: без дохода за месяц сумма не выдумывается', () => {
  const html = loadFin().secSaveGoals([{ id: 1, name: 'Фан-кар', target: 15000, pct_min: 5, pct_max: 5,
    saved: 0, thisMonth: 0, incomeMonth: 0, incomeYm: '2026-09', log: [] }]);
  assert.ok(html.includes('внеси доход за этот месяц'), 'надо сказать, почему суммы нет');
  assert.ok(html.includes('за сентябрь'), 'не названо, за какой месяц считаем');
  assert.ok(!html.includes('это 0 €'), 'нулевая подсказка хуже, чем её отсутствие');
});

test('цель: закреплено то поле, что заполнено', () => {
  const html = loadFin().secPortfolio(DATA, DATA.summary);
  assert.ok(html.includes('target_pct'), 'нет поля доли');
  assert.ok(html.includes('ed pinned'), 'закреплённое поле не помечено');
});

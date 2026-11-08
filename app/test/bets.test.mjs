import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// «Ставки на рост»: не прогноз про рынок, а собственные действия с потенциалом.
// Главное в блоке — три числа сверху (потолок, взвешенно, в месяц) и честная статистика
// по закрытым: через год по ней видно, сколько ожиданий вообще сбывается.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));

function loadFin() {
  const calls = [], alerts = [], prompts = [];
  let hooks = [];
  const made = [];
  const node = () => { const n = { addEventListener(ev, fn) { n['_' + ev] = fn; }, appendChild() {},
    classList: { add() {}, remove() {} }, dataset: {}, style: {}, innerHTML: '', value: '',
    textContent: '', focus() {}, select() {}, replaceWith() {} }; made.push(n); return n; };
  const ctx = {
    document: { querySelectorAll: sel => hooks.filter(h => sel.includes(Object.keys(h.dataset)[0])),
      getElementById: id => ctx.__byId?.[id] ?? null, addEventListener() {}, createElement: node },
    console, localStorage: {},
    fetch: async (url, o) => { calls.push({ method: o?.method || 'GET', url, body: o?.body && JSON.parse(o.body) });
      return { ok: true, status: 200, json: async () => ({}) }; },
    alert: m => alerts.push(String(m)), confirm: () => true,
    prompt: m => { prompts.push(m); return ctx.__answer; },
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx; ctx.loadFin = () => {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  // кнопку поднимаем из настоящей разметки и прогоняем через настоящий bindFin
  const click = async (html, attr) => {
    const v = (html.match(new RegExp(`data-${attr}="([^"]+)"`)) || [])[1];
    assert.ok(v, `в разметке нет data-${attr}`);
    const el = { dataset: { [attr]: v }, addEventListener(ev, fn) { el['_' + ev] = fn; } };
    hooks = [el];
    ctx.bindFin();
    await el._click();
    return calls.filter(c => c.method !== 'GET').at(-1);
  };
  return { ctx, click, calls, alerts, prompts };
}

const bet = (id, o = {}) => ({ id, title: 'Ставка ' + id, kind: 'invest', thesis: '', stake: 0,
  currency: '€', upside: 0, monthly: 0, confidence: 50, horizon: null, status: 'open', actual: null, ...o });
const DATA = bets => ({
  summary: { portfolioTotal: 100000, rate: 1.08 }, rate: 1.08, bets,
  targetPortfolio: [{ id: 1, name: 'Рост', kind: 'block', side: 'act', eur: 100000, children: [] }],
  portfolio: [],
});

test('сверху — потолок, взвешенная прибавка и доля к капиталу', () => {
  const html = loadFin().ctx.secBets(DATA([
    bet(1, { upside: 30000, confidence: 80, stake: 12000 }),
    bet(2, { upside: 20000, confidence: 10 }),
  ]), { rate: 1.08 }).replace(/ /g, ' ');
  assert.match(html, /потолок[\s\S]*?50 000 €/, 'потолок считается не как сумма всех ставок');
  assert.match(html, /взвешенно[\s\S]*?26 000 €/, 'взвешенная прибавка считается без уверенности');
  assert.match(html, /к капиталу \+26%/, 'не видно, насколько это меняет капитал');
  assert.match(html, /на кону[\s\S]*?12 000 €/, 'не видно, чем рискую');
});

test('ставка на 100k с верой 10% не равна ставке на 10k с верой 100%', () => {
  const ctx = loadFin().ctx;
  const risky = ctx.secBets(DATA([bet(1, { upside: 100000, confidence: 10 })]), { rate: 1.08 });
  const sure = ctx.secBets(DATA([bet(2, { upside: 10000, confidence: 100 })]), { rate: 1.08 });
  const w = h => (h.replace(/ /g, ' ').match(/взвешенно[\s\S]*?([\d ]+) €/) || [])[1].trim();
  assert.equal(w(risky), '10 000');
  assert.equal(w(sure), '10 000', 'взвешенная прибавка должна сравнивать их на равных');
  assert.match(risky.replace(/ /g, ' '), /потолок[\s\S]*?100 000 €/, 'потолок обязан остаться разным');
});

test('доход в месяц считается отдельно от разовой суммы', () => {
  const html = loadFin().ctx.secBets(DATA([bet(1, { monthly: 1000, confidence: 60 })]), { rate: 1.08 })
    .replace(/ /g, ' ');
  assert.match(html, /в месяц[\s\S]*?600 €/, 'ежемесячная прибавка не взвешена или потеряна');
  const once = (html.match(/взвешенно[\s\S]*?([\d ]+) €/) || [])[1].trim();
  assert.equal(once, '0', 'месячный доход попал в разовую прибавку');
});

test('$-ставка приводится к евро, а не складывается как есть', () => {
  const html = loadFin().ctx.secBets(DATA([bet(1, { upside: 10800, currency: '$', confidence: 100 })]),
    { rate: 1.08 }).replace(/ /g, ' ');
  assert.match(html, /взвешенно[\s\S]*?10 000 €/, 'доллары сложены с евро по номиналу');
});

test('закрытые ставки дают честную статистику ожиданий', () => {
  const html = loadFin().ctx.secBets(DATA([
    bet(1, { upside: 30000, status: 'won', actual: 12000 }),
    bet(2, { upside: 10000, status: 'lost', actual: 0 }),
    bet(3, { upside: 5000 }),
  ]), { rate: 1.08 }).replace(/ /g, ' ');
  assert.match(html, /проверено 2 · сыграло 1/, 'не видно, сколько ставок вообще проверено');
  assert.match(html, /ждал 40 000 € → вышло 12 000 €/, 'нет сверки ожиданий с фактом');
  assert.match(html, /✓ сыграла · 12 000 €/, 'у сыгравшей не показан фактический результат');
  assert.ok(!/взвешенно[\s\S]*?22 500 €/.test(html), 'закрытые ставки всё ещё обещают прибавку');
});

test('закрытие спрашивает, сколько принесла на самом деле', async () => {
  const f = loadFin();
  f.ctx.__answer = '12 000';
  const html = f.ctx.secBets(DATA([bet(7, { upside: 30000 })]), { rate: 1.08 });
  const patch = await f.click(html, 'betwon');
  assert.equal(patch.url, '/api/fin/bets/7');
  assert.deepEqual(patch.body, { status: 'won', actual: 12000 }, 'факт не записан или не разобран');
  assert.match(f.prompts[0] || '', /принесла на самом деле/, 'закрыли, не спросив результат');
});

test('не сыграла — пишем ноль, а не удаляем ставку', async () => {
  const f = loadFin();
  const patch = await f.click(f.ctx.secBets(DATA([bet(7)]), { rate: 1.08 }), 'betlost');
  assert.deepEqual(patch.body, { status: 'lost', actual: 0 });
  assert.equal(patch.method, 'PATCH', 'проигравшая ставка должна остаться в истории');
});

test('пустой блок объясняет, что сюда писать', () => {
  const html = loadFin().ctx.secBets(DATA([]), { rate: 1.08 });
  assert.match(html, /что ты уже сделал, от чего ждёшь прироста/, 'пустой блок молчит');
  assert.match(html, /это не прогноз про рынок/, 'не отделено от прогнозов — а это разные вещи');
});

test('новую ставку нельзя завести без названия', async () => {
  const f = loadFin();
  f.ctx.__byId = { betTitle: { value: '  ' }, betUp: { value: '30k' }, betConf: { value: '70' },
    betWhen: { value: '2027-03' }, betAdd: { addEventListener(ev, fn) { f.ctx.__byId.betAdd['_' + ev] = fn; } } };
  f.ctx.secBets(DATA([]), { rate: 1.08 });
  f.ctx.bindFin();
  await f.ctx.__byId.betAdd._click();
  assert.equal(f.calls.filter(c => c.method === 'POST').length, 0, 'завели безымянную ставку');
  assert.match(f.alerts[0] || '', /Назови ставку/);

  f.ctx.__byId.betTitle.value = 'Доля в студии';
  await f.ctx.__byId.betAdd._click();
  const post = f.calls.find(c => c.method === 'POST');
  assert.deepEqual(post.body,
    { title: 'Доля в студии', upside: 30000, currency: '€', confidence: 70, horizon: '2027-03' },
    'сокращения вроде 30k или месяц не разобраны');
});

test('открытые ставки идут по сроку, без срока — в конец', () => {
  const html = loadFin().ctx.secBets(DATA([
    bet(1, { horizon: null }), bet(2, { horizon: '2027-12' }), bet(3, { horizon: '2027-03' }),
  ]), { rate: 1.08 });
  const months = [...html.matchAll(/class="meta betmon">([^<]+)</g)].map(m => m[1]);
  assert.deepEqual(months, ['мар 2027', 'дек 2027', 'без срока'],
    'порядок зависит от того, как отдал бэкенд, а должен быть по сроку');
});

test('валюту ставки видно и можно переключить', async () => {
  const f = loadFin();
  const html = f.ctx.secBets(DATA([bet(4, { currency: '$', upside: 10800 })]), { rate: 1.08 });
  assert.match(html, /data-betcur="4:\$"/, 'валюту ставки нечем переключить');
  const patch = await f.click(html, 'betcur');
  assert.deepEqual(patch.body, { currency: '€' }, '$ не переключается в €');

  const back = loadFin();
  const eurHtml = back.ctx.secBets(DATA([bet(5)]), { rate: 1.08 });
  assert.deepEqual((await back.click(eurHtml, 'betcur')).body, { currency: '$' }, '€ не переключается в $');
});

test('новую ставку можно завести сразу в долларах', async () => {
  const f = loadFin();
  f.ctx.__byId = { betTitle: { value: 'Доля в студии' }, betUp: { value: '30k' }, betConf: { value: '70' },
    betWhen: { value: '' }, betCur: { value: '$' },
    betAdd: { addEventListener(ev, fn) { f.ctx.__byId.betAdd['_' + ev] = fn; } } };
  f.ctx.secBets(DATA([]), { rate: 1.08 });
  f.ctx.bindFin();
  await f.ctx.__byId.betAdd._click();
  const post = f.calls.find(c => c.method === 'POST');
  assert.equal(post.body.currency, '$', 'выбранная валюта потерялась при создании');

  f.ctx.__byId.betCur.value = '€';
  await f.ctx.__byId.betAdd._click();
  assert.equal(f.calls.filter(c => c.method === 'POST').at(-1).body.currency, '€');
});

// Продажа имущества не создаёт новых денег: она превращает замороженное в рабочее.
// Поэтому высвобождение считается отдельно от прироста — иначе «+120 000» врало бы.
test('высвобождение капитала — отдельное число, не прирост', () => {
  const html = loadFin().ctx.secBets(DATA([
    bet(1, { title: 'Продать квартиру', kind: 'sale', frees: 120000, upside: 8000, confidence: 100 }),
  ]), { rate: 1.08 }).replace(/ /g, ' ');
  assert.match(html, /высвободит[\s\S]*?120 000 €/, 'высвобождение не посчитано');
  const grow = (html.match(/взвешенно[\s\S]*?([\d ]+) €/) || [])[1].trim();
  assert.equal(grow, '8 000', 'цена продажи попала в прирост — капитал бы вырос дважды');
  assert.match(html, /data-fe="bets:1:frees:num"/, 'высвобождение нечем вписать в строке');
});

test('высвобождение взвешивается верой, как и остальное', () => {
  const html = loadFin().ctx.secBets(DATA([bet(1, { frees: 100000, confidence: 50 })]), { rate: 1.08 })
    .replace(/ /g, ' ');
  assert.match(html, /высвободит[\s\S]*?50 000 €/, 'неуверенная продажа обещает всю сумму');
});

test('нечего высвобождать — числа в сводке нет', () => {
  // слово есть и в подсказке строки, поэтому смотрим именно сводку сверху
  const line = h => (h.match(/<div class="capline betline">[\s\S]*?<\/div>/) || [''])[0];
  assert.ok(!line(loadFin().ctx.secBets(DATA([bet(1, { upside: 5000 })]), { rate: 1.08 })).includes('высвободит'),
    'пустое число занимает место в сводке');
  assert.ok(line(loadFin().ctx.secBets(DATA([bet(1, { frees: 9000, confidence: 100 })]), { rate: 1.08 })).includes('высвободит'),
    'есть что высвободить, а в сводке не показано');
});

// Риск-менеджмент: из «на кону / теряю / вера» считается порог безубыточности и
// ожидаемая ценность. Главное — поймать самообман: веры меньше, чем нужно ставке.
test('порог безубыточности и ожидаемая ценность считаются по ставке', () => {
  const ctx = loadFin().ctx;
  // приз 30k, потеря 10k → порог 25%; вера 40% → ожидаемо 30×0.4 − 10×0.6 = +6 000
  const good = ctx.secBets(DATA([bet(1, { upside: 30000, downside: 10000, confidence: 40 })]), { rate: 1.08 })
    .replace(/ /g, ' ');
  assert.match(good, /нужно ≥25% · ожидаемо \+6 000 €/, 'порог или ожидаемая ценность посчитаны неверно');
  assert.match(good, /betev up/, 'ставка в плюс не отмечена как плюс');

  // та же ставка с верой 10% → ожидаемо 3 000 − 9 000 = −6 000, то есть против тебя
  const bad = ctx.secBets(DATA([bet(2, { upside: 30000, downside: 10000, confidence: 10 })]), { rate: 1.08 })
    .replace(/ /g, ' ');
  assert.match(bad, /нужно ≥25% · ожидаемо −6 000 €/, 'минусовая ставка показана как плюсовая');
  assert.match(bad, /betev down/, 'ставка против тебя не отмечена');
});

test('без названной потери вердикта нет — считать нечего', () => {
  const html = loadFin().ctx.secBets(DATA([bet(1, { upside: 30000, confidence: 40 })]), { rate: 1.08 });
  assert.ok(!html.includes('нужно ≥'), 'порог выдуман там, где потеря не названа');
  assert.match(html, /data-fe="bets:1:downside:num"/, 'потерю нечем вписать');
});

test('сводка показывает ожидаемую потерю и долю капитала на кону', () => {
  const html = loadFin().ctx.secBets(DATA([
    bet(1, { stake: 25000, downside: 10000, confidence: 60, upside: 20000 }),
  ]), { rate: 1.08 }).replace(/ /g, ' ');
  assert.match(html, /риск[\s\S]*?−4 000 €/, 'ожидаемая потеря не посчитана (10 000 × 40%)');
  assert.match(html, /на кону[\s\S]*?25 000 €[\s\S]*?25% капитала/, 'не видно, какая доля капитала завязана');
});

test('нечего терять — строки риска в сводке нет', () => {
  const line = h => (h.match(/<div class="capline betline">[\s\S]*?<\/div>/) || [''])[0];
  assert.ok(!line(loadFin().ctx.secBets(DATA([bet(1, { upside: 5000 })]), { rate: 1.08 })).includes('риск'),
    'пустой риск занимает место');
});

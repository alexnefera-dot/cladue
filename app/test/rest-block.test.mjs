import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// public/today.js — браузерный скрипт. Блок «Кайф» считает молчащий вид, подбор на сегодня
// и точки недели, поэтому его логику гоняем в песочнице, а не проверяем глазами.

const SRC = fileURLToPath(new URL('../public/today.js', import.meta.url));

function loadToday() {
  const ctx = {
    document: { querySelectorAll: () => [], getElementById: () => null, addEventListener() {}, createElement: () => ({}) },
    console, localStorage: { getItem: () => null, setItem() {} },
    fetch: async () => ({ json: async () => ({}) }),
    alert() {}, confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout, Date, showScreen() {},
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'today.js' });
  return ctx;
}

// «сегодня» берём настоящее: подбор и точки недели считаются от текущей даты
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const ago = n => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d); };
const isWeekend = [0, 6].includes(new Date().getDay());
const scopeToday = isWeekend ? 'weekend' : 'weekday';

const DATA = {
  today: iso(new Date()),
  ideas: [
    { id: 1, text: 'Полежать в тишине', scope: scopeToday, kind: 'restore', mins: 20, last_at: ago(1), done_today: 0 },
    { id: 2, text: 'Собрать лего', scope: scopeToday, kind: 'play', mins: 30, last_at: null, done_today: 0 },
    { id: 3, text: 'Позвонить другу', scope: 'global', kind: 'people', mins: 30, last_at: ago(2), done_today: 1 },
  ],
  log: [{ date: ago(2), kind: 'people' }, { date: ago(1), kind: 'restore' }],
};

const strip = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

test('кайф: первым идёт вид, который дольше всех молчит', () => {
  const ctx = loadToday();
  ctx.window.tdRestData = DATA;
  const html = ctx.tdRest();
  const cards = [...html.matchAll(/class="restt">([^<]*)</g)].map(m => m[1].trim());
  assert.ok(cards.length >= 2, 'карточек на сегодня нет');
  assert.match(cards[0], /Собрать лего/, 'наверх должно попасть «играть» — его ни разу не было');
});

test('кайф: отметка за сегодня видна, полоска считает виды за 14 дней', () => {
  const ctx = loadToday();
  ctx.window.tdRestData = DATA;
  const html = ctx.tdRest();
  assert.ok(html.includes('✓ отдохнул'), 'сделанное сегодня не помечено');
  assert.ok(html.includes('data-restdone="2"'), 'нет кнопки отметки');
  const bal = strip((html.match(/<div class="restbal">[\s\S]*?<\/div>/) || [''])[0]);
  assert.match(bal, /🧒\s*0/, 'молчащий вид должен показывать 0');
  assert.match(bal, /👥\s*1/, 'по «людям» за 14 дней ровно одна отметка');
  assert.ok(html.includes('restseg zero'), 'пустой вид не выделен');
});

test('кайф: отметить и удалить можно любую идею из списка, не только предложенную', () => {
  const ctx = loadToday();
  ctx.window.tdRestData = DATA;
  const pool = (ctx.tdRest().match(/<details class="restpool">[\s\S]*<\/details>/) || [''])[0];
  for (const r of DATA.ideas) {
    assert.ok(pool.includes(`data-restdone="${r.id}"`), `в списке нет отметки для «${r.text}»`);
    assert.ok(pool.includes(`data-restdel="${r.id}"`), `в списке нет удаления для «${r.text}»`);
  }
  assert.ok(pool.includes('✓ сегодня'), 'сделанное сегодня не отмечено в списке');
});

test('кайф: без идей блок не падает и зовёт добавить', () => {
  const ctx = loadToday();
  ctx.window.tdRestData = { today: iso(new Date()), ideas: [], log: [] };
  const html = ctx.tdRest();
  assert.ok(html.includes('добавь, чем восстановишься'), 'пустой блок ничего не объясняет');
  assert.ok(html.includes('tdRestKind'), 'нет выбора вида отдыха при добавлении');
});

test('кайф: три дня тишины — блок говорит об этом', () => {
  const ctx = loadToday();
  ctx.window.tdRestData = { ...DATA, log: [{ date: ago(4), kind: 'restore' }] };
  assert.ok(ctx.tdRest().includes('дн. без отдыха'), 'молчание больше трёх дней не замечено');
});

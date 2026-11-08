import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// «Навыки за год»: вехи сфер, отмеченные 🎓, собираются со всех сфер в одну ленту по месяцам.
// Проверяем сбор и порядок, горизонт года, отметку и срок в строке вехи.

const SRC = fileURLToPath(new URL('../public/spheres.js', import.meta.url));

function loadSph(areas) {
  const calls = [];
  const el = () => ({ addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
    dataset: {}, style: {}, innerHTML: '', value: '', querySelectorAll: () => [], onclick: null });
  const ctx = {
    document: { getElementById: () => el(), querySelector: () => el(), querySelectorAll: () => [],
      createElement: el, addEventListener() {}, head: el(), body: el() },   // стили вешаются в head при загрузке
    console, localStorage: {},
    fetch: async (url, o) => { calls.push({ method: o?.method || 'GET', url, body: o?.body && JSON.parse(o.body) });
      return { ok: true, json: async () => ({}) }; },
    alert() {}, confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout, Date,
    MutationObserver: class { observe() {} disconnect() {} },   // экран следит за своей разметкой
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'spheres.js' });
  ctx.__a = areas;
  vm.runInContext('sphData = __a', ctx);          // sphData объявлена через let — только присваиванием
  return ctx;
}

const ym = add => {              // месяц относительно сегодняшнего, «YYYY-MM»
  const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() + add);
  return d.toISOString().slice(0, 7);
};
const ms = (id, title, o = {}) => ({ id, title, progress: 0, pinned: 0, skill: 1, skill_by: '', ...o });
const AREAS = [
  { id: 1, name: 'Здоровье', score: 7, ideal: '', step: '', routines: [], tracking: [], practices: [], fin: [], tasks: [],
    milestones: [ms(11, 'Подтягиваться 20 раз', { skill_by: ym(5), progress: 4 }),
      ms(12, 'Просто веха', { skill: 0 })] },
  { id: 2, name: 'Работа', score: 5, ideal: '', step: '', routines: [], tracking: [], practices: [], fin: [], tasks: [],
    milestones: [ms(21, 'Английский C1', { skill_by: ym(2), progress: 10 }),
      ms(22, 'Своя студия', { skill_by: ym(20) }),
      ms(23, 'Монтаж видео')] },
];

test('в ленту попадают только отмеченные 🎓 вехи', () => {
  const sk = loadSph(AREAS).sphSkills();
  // массив приходит из песочницы: строгое сравнение сверяет и прототип, поэтому переносим к себе
  assert.deepEqual(Array.from(sk, s => s.title),
    ['Английский C1', 'Подтягиваться 20 раз', 'Своя студия', 'Монтаж видео'],
    'не те вехи или не тот порядок: ближний срок первым, без срока — в конец');
  assert.equal(sk[0].area, 'Работа', 'навык не знает своей сферы');
  assert.equal(sk[1].p, 4, 'потерян прогресс вехи');
});

test('заголовок считает навыки в пределах года, а не все подряд', () => {
  const html = loadSph(AREAS).sphSkillsBlock();
  assert.match(html, /НАВЫКИ ЗА ГОД · 2 шт/, 'в «за год» попали те, что дальше года, или без срока');
  assert.match(html, /1 уже есть/, 'не видно, сколько навыков уже закрыто');
});

test('лента сгруппирована по месяцам, дальнее и бессрочное — отдельно', () => {
  const html = loadSph(AREAS).sphSkillsBlock();
  const groups = [...html.matchAll(/class="sph-skmon">([^<]+)</g)].map(m => m[1]);
  assert.equal(groups.length, 4, 'групп не столько, сколько разных сроков');
  assert.equal(groups[2], 'дальше года', 'веха за горизонтом года не отделена');
  assert.equal(groups[3], 'без срока', 'бессрочное не в конце');
  assert.match(html, /class="sph-skrow done"[^>]*data-skopen="21"/, 'закрытый навык не помечен');
});

test('пустая лента не рисует пустой карточки', () => {
  const none = AREAS.map(a => ({ ...a, milestones: a.milestones.map(m => ({ ...m, skill: 0 })) }));
  assert.equal(loadSph(none).sphSkillsBlock(), '', 'блок висит, когда отмечать ещё нечего');
});

test('в строке вехи есть 🎓, а у отмеченной — ещё и срок', () => {
  const ctx = loadSph(AREAS);
  const html = ctx.sphRoadmap(AREAS[0]);
  assert.match(html, /data-msskill="11:1"/, 'нечем снять отметку навыка');
  assert.match(html, /data-msskill="12:0"/, 'нечем отметить обычную веху как навык');
  assert.match(html, /data-msby="11:/, 'у навыка нельзя задать месяц');
  assert.ok(!/data-msby="12:/.test(html), 'срок предлагается там, где навык не отмечен');
});

test('месяц пишется словами, мусор — «без срока»', () => {
  const ctx = loadSph(AREAS);
  assert.equal(ctx.sphMonth('2027-03'), 'мар 2027');
  assert.equal(ctx.sphMonth(''), 'без срока');
  assert.equal(ctx.sphMonth('завтра'), 'без срока', 'непонятный срок притворился датой');
});

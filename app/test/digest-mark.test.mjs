import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// 🎓 «в сведение капитала» — отметка-переключатель. Снять её можно было только в строке
// портфеля, а если блок свёрнут или позиция спрятана под родителем — не добраться вовсе.
// Проверяем, что снять отметку можно прямо в своде и что молчаливый отказ бэкенда виден.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));

function loadFin({ afterPatch } = {}) {
  const calls = [], alerts = [];
  let els = [];
  const ctx = {
    document: {
      querySelectorAll: sel => sel === '[data-fdig]' ? els : [],
      getElementById: () => null, addEventListener() {},
      createElement: () => ({ addEventListener() {}, appendChild() {}, classList: { add() {}, remove() {} },
        dataset: {}, style: {}, innerHTML: '', value: '', focus() {}, replaceWith() {} }),
    },
    console, localStorage: { getItem: () => null, setItem() {} },
    fetch: async (url, opt) => {
      calls.push({ method: opt?.method || 'GET', url, body: opt?.body });
      return { ok: true, status: 200, json: async () => afterPatch ? afterPatch(calls) : {} };
    },
    alert: m => alerts.push(m), confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  ctx.loadFin = () => {};
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  // кнопки берём из настоящей разметки: так тест ловит и сам маркер, и обработчик
  const bindFrom = html => {
    els = [...html.matchAll(/data-fdig="([^"]+)"/g)]
      .map(m => ({ dataset: { fdig: m[1] }, addEventListener(ev, fn) { this['_' + ev] = fn; } }));
    ctx.bindFin();
    return els;
  };
  return { ctx, calls, alerts, bindFrom };
}

const marked = (o = {}) => ({ id: 7, name: 'Квартира', kind: 'asset', children: [], value: 90000,
  eur: 90000, currency: '€', region: 'UA', digest: 1, ...o });

test('свод: у каждой позиции есть чем снять 🎓', () => {
  const { ctx } = loadFin();
  const html = ctx.secDigest([marked(), marked({ id: 8, name: 'Кэш', region: 'EU' })]);
  assert.ok(html.includes('data-fdig="7:1"') && html.includes('data-fdig="8:1"'),
    'из свода нечем убрать позицию — отметку пришлось бы искать в портфеле');
});

test('снятие 🎓 уходит на бэкенд как сброс флага', async () => {
  const f = loadFin();
  const els = f.bindFrom(f.ctx.secDigest([marked()]));
  await els[0]._click();
  const patch = f.calls.find(c => c.method === 'PATCH');
  assert.equal(patch.url, '/api/fin/tgt/7');
  assert.deepEqual(JSON.parse(patch.body), { digest: 0 }, 'ушло не снятие отметки');
});

test('отметка в портфеле ставится и снимается одной кнопкой', async () => {
  const f = loadFin();
  const off = f.bindFrom(f.ctx.portRows(marked({ digest: 0 }), 1, {}));
  await off[0]._click();
  assert.deepEqual(JSON.parse(f.calls.find(c => c.method === 'PATCH').body), { digest: 1 },
    'без отметки кнопка должна её ставить');

  const g = loadFin();
  const on = g.bindFrom(g.ctx.portRows(marked(), 1, {}));
  await on[0]._click();
  assert.deepEqual(JSON.parse(g.calls.find(c => c.method === 'PATCH').body), { digest: 0 },
    'с отметкой кнопка должна её снимать');
});

test('если сборка молча отбросила флаг — говорим это вслух', async () => {
  // старый бэкенд: patchCols не знает колонку digest, отвечает 200, в базе всё по-прежнему
  const f = loadFin({ afterPatch: () => ({ targetPortfolio: [{ id: 1, name: 'Блок', children: [marked()] }] }) });
  const els = f.bindFrom(f.ctx.secDigest([marked()]));
  await els[0]._click();
  assert.equal(f.alerts.length, 1, 'кнопка не сработала, а пользователю ничего не сказали');
  assert.match(f.alerts[0], /не снялась/);
  assert.match(f.alerts[0], /Xcode/, 'не названо, что лечится пересборкой');

  // свежий бэкенд: флаг снят — молчим
  const okRun = loadFin({ afterPatch: () => ({ targetPortfolio: [{ id: 1, name: 'Блок', children: [marked({ digest: 0 })] }] }) });
  const e2 = okRun.bindFrom(okRun.ctx.secDigest([marked()]));
  await e2[0]._click();
  assert.deepEqual(okRun.alerts, [], 'запись прошла, а мы всё равно ругаемся');
});

test('NEED_BUILD не отстаёт от правок Swift — иначе предупреждение о сборке молчит', () => {
  let swiftDate;
  try {
    swiftDate = execFileSync('git', ['log', '-1', '--format=%ad', '--date=short', '--', 'native/Pipboy'],
      { cwd: fileURLToPath(new URL('../..', import.meta.url)), encoding: 'utf8' }).trim();
  } catch { return; }                        // не репозиторий — проверять нечего
  if (!swiftDate) return;
  const need = (readFileSync(SRC, 'utf8').match(/NEED_BUILD = '([\d-]+)'/) || [])[1];
  assert.ok(need >= swiftDate,
    `NEED_BUILD ${need} старее последней правки Swift (${swiftDate}): устаревшая сборка не будет отмечена`);
});

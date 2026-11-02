import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// Блок «Google Tasks» в настройках: задачи с датой уезжают в Google настоящими задачами.
// Проверяем разметку, что кнопки шлют ровно то, что обещают, что на сборке без выгрузки
// блока нет вовсе (а не мёртвая кнопка) и что выгрузка догоняется сама.

const SRC = fileURLToPath(new URL('../public/app.js', import.meta.url));

function loadApp(opt = {}) {
  const calls = [], alerts = [];
  const el = () => ({ addEventListener() {}, appendChild() {}, replaceWith() {}, focus() {}, select() {},
    classList: { add() {}, remove() {}, contains: () => false, toggle() {} }, dataset: {}, style: {},
    innerHTML: '', value: '', textContent: '', querySelector: () => null, querySelectorAll: () => [],
    children: [], remove() {}, insertAdjacentHTML() {}, setAttribute() {}, getAttribute: () => null });
  const ctx = {
    document: { getElementById: () => el(), querySelector: () => el(), querySelectorAll: () => [],
      createElement: el, addEventListener() {}, body: el(), head: el(), documentElement: el() },
    console, localStorage: {}, sessionStorage: {},
    fetch: async (url, o) => {
      calls.push({ method: o?.method || 'GET', url, body: o?.body && JSON.parse(o.body) });
      const u = String(url);
      // старая сборка отвечает на незнакомый путь 500 с валидным JSON — это не «нет доступа»
      const body = u.startsWith('/api/trash') ? []
        : (u.startsWith('/api/calsync') && opt.oldBuild) ? { error: 'Unsupported(path: "/api/calsync")' }
        : { nodes: [], links: [], added: 2, updated: 1, removed: 0, total: 3, errors: [] };
      return { ok: !(u.startsWith('/api/calsync') && opt.oldBuild), status: 200, text: async () => '',
        json: async () => body };
    },
    alert: m => alerts.push(String(m)), confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout, setInterval: () => 0, clearInterval() {},
    requestAnimationFrame: () => 0, location: { protocol: 'http:', hash: '' },
    navigator: { userAgent: 'node' }, CSS: { escape: s => s },
  };
  if (opt.native) ctx.webkit = { messageHandlers: {} };   // внутри приложения, а не в браузере
  ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'app.js' });
  ctx.loadSettings = () => {};                        // а обработчикам перерисовку не даём
  const mk = () => { const n = { dataset: {}, addEventListener(ev, fn) { n['_' + ev] = fn; } }; return n; };
  // на старте app.js сам пингует /api/calsync/run — нас интересует последний запрос, а не он
  const post = () => calls.filter(c => c.method === 'POST' && /\/api\/(calsync|gtasks)/.test(String(c.url))).at(-1);
  return { ctx, calls, alerts, post };
}

const ON = {
  access: 'granted', on: true, calendar: 'c1',
  kinds: { tasks: true, obligations: false, birthdays: true },
  last: '2026-11-02 10:00 · +3 ~1 −0',
  calendars: [{ id: 'c1', title: 'Pipboy', source: 'alex@gmail.com', google: true },
    { id: 'c2', title: 'Домашний', source: 'iCloud', google: false }],
};

const GT_ON = { client: '123-abc.apps.googleusercontent.com', linked: true, on: true, list: 'L1',
  lists: [{ id: 'L1', title: 'Мои задачи' }, { id: 'L2', title: 'Работа' }], last: '2026-11-02 12:00 · +4 ~0 ✓1 −0' };

test('на старте выгрузка догоняется сама, без кнопок', () => {
  const app = loadApp();
  const pings = app.calls.filter(c => c.method === 'POST' && c.url === '/api/gtasks/run');
  assert.equal(pings.length, 1, 'при запуске не догоняем то, что менялось мимо приложения');
});

test('вернулся в приложение — догоняем, но не чаще раза в 10 минут', () => {
  const app = loadApp();
  const ping = () => app.calls.filter(c => c.method === 'POST' && c.url === '/api/gtasks/run').length;
  app.ctx.pingExports();                       // сразу после старта — рано, пропускаем
  assert.equal(ping(), 1, 'дёргаем выгрузку на каждый возврат в окно');
  vm.runInContext('syncPing.at = Date.now() - 11 * 60 * 1000', app.ctx);   // const — только так
  app.ctx.pingExports();
  assert.equal(ping(), 2, 'через десять минут догнать уже надо');
});

test('выключил выгрузку — предложили убрать выгруженные задачи', async () => {
  const g = loadApp();
  g.ctx.confirm = () => true;
  const node = { dataset: {}, addEventListener(ev, fn) { node['_' + ev] = fn; } };
  const box = { querySelector: sel => (sel === '#gtOn' ? node : null), querySelectorAll: () => [] };
  vm.runInContext('bindGTasks(__box, __gt)', Object.assign(g.ctx, { __box: box, __gt: GT_ON }));
  await node._click();
  assert.equal(g.post().url, '/api/gtasks/purge', 'задачи остались в Google после выключения');
});

// В списке — календари системного Календаря. Пока гугл-аккаунт не добавлен в macOS,
// гугловых там нет, и по названию «Домашний · iCloud» об этом не догадаться.
const ICLOUD = [{ id: 'c1', title: 'Домашний', source: 'iCloud', google: false },
  { id: 'c2', title: 'Рабочий', source: 'iCloud', google: false }];

test('Google Tasks: без связи — Client ID и как его получить', () => {
  const html = loadApp().ctx.gTasksCard({ client: '', linked: false, lists: [] });
  assert.match(html, /id="gtClient"/, 'некуда вписать Client ID');
  assert.match(html, /Google Tasks API/, 'не сказано, какой API включать');
  assert.match(html, /Bundle ID <b>com.pipboy.app<\/b>/, 'не назван Bundle ID для клиента');
  assert.match(html, /каждые 7 дней/, 'не предупредили про режим Testing');
  assert.ok(!html.includes('gtRun'), 'предлагаем выгружать до подключения');
});

test('Google Tasks: после связи — список задач и состояние', () => {
  const html = loadApp().ctx.gTasksCard(GT_ON);
  assert.match(html, /<option value="L1" selected>Мои задачи</, 'выбранный список не отмечен');
  assert.match(html, /выгрузка включена/, 'состояние выгрузки не видно');
  assert.match(html, /последний прогон: 2026-11-02 12:00/, 'нет итога прошлого прогона');
  assert.match(html, /только дата/, 'не предупредили, что времени у задач Google нет');
});

test('Google Tasks: блока нет на сборке без него', () => {
  assert.equal(loadApp().ctx.gTasksCard(null), '', 'показали блок там, где маршрута нет');
});

test('Google Tasks: итог прогона читается человеком', () => {
  const r = s => loadApp().ctx.gtReport(s);
  assert.match(r({ total: 0, added: 0, updated: 0, closed: 0, removed: 0 }), /Выгружать нечего/);
  assert.match(r({ total: 5, added: 0, updated: 0, closed: 0, removed: 0 }), /Всё уже в Google: задач 5/);
  assert.match(r({ total: 5, added: 4, updated: 0, closed: 1, removed: 0 }),
    /добавлено 4, изменено 0, закрыто 1, удалено 0/, 'не видно, что именно уехало');
  assert.match(r({ error: 'список задач не выбран' }), /список задач не выбран/);
});

test('итог прогона показывает и то, что приехало из Google', () => {
  const r = s => loadApp().ctx.gtReport(s);
  assert.match(r({ total: 4, added: 0, updated: 0, closed: 0, removed: 0, backClosed: 2, backMoved: 1 }),
    /Из Google принято: закрыто 2, перенесено 1/, 'обратные правки не показаны');
  // закрытие в Google при пустой выгрузке — не «выгружать нечего», а настоящая работа
  assert.match(r({ total: 0, added: 0, updated: 0, closed: 0, removed: 0, backClosed: 1, backMoved: 0 }),
    /Из Google принято: закрыто 1/, 'приём из Google потерялся за «нечего выгружать»');
  assert.ok(!r({ total: 3, added: 1, updated: 0, closed: 0, removed: 0 }).includes('Из Google'),
    'пишем про приём, когда ничего не приехало');
});

test('в блоке сказано, что синхрон двусторонний и кто главный', () => {
  const html = loadApp().ctx.gTasksCard(GT_ON);
  assert.match(html, /закрыл задачу в Google — закроется\s+и здесь/, 'не сказано про закрытие из Google');
  assert.match(html, /перенёс там дату — переедет и здесь/, 'не сказано про перенос даты');
  assert.match(html, /Pipboy — база планирования/, 'не названо, чья дата главнее при споре');
});

test('в блоке сказано, что удалённая в Google задача вернётся', () => {
  const html = loadApp().ctx.gTasksCard(GT_ON);
  assert.match(html, /Удалил задачу в Google — она вернётся/, 'молчим про то, что удаление не считается');
  assert.match(html, /закрывать надо\s+галочкой/, 'не сказано, как закрыть правильно');
});

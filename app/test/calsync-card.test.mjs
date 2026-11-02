import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// Блок «Календарь» в настройках: выгрузка задач, платежей и дней рождения в системный
// Календарь (а оттуда в Google). Проверяем разметку и то, что кнопки шлют ровно то,
// что обещают, — и что на сборке без выгрузки блока нет вовсе, а не мёртвая кнопка.

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
  const screen = el();
  screen.querySelector = () => el();   // настройки вешают обработчики на свои кнопки — отдаём заглушки
  ctx.document.getElementById = id => (id === 'screen-settings' ? screen : el());
  ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'app.js' });
  const renderSettings = ctx.loadSettings;            // настоящая отрисовка — для сквозной проверки
  ctx.loadSettings = () => {};                        // а обработчикам перерисовку не даём
  const card = state => vm.runInContext('calSyncCard(__cs)', Object.assign(ctx, { __cs: state }));
  // живые кнопки блока: поднимаем из разметки и отдаём обработчикам, как это делает экран
  const bind = state => {
    const nodes = {};
    const html = card(state);
    [...html.matchAll(/id="(cs[A-Za-z]+)"/g)].forEach(m => { nodes['#' + m[1]] = mk(); });
    const kinds = [...html.matchAll(/data-cskind="([a-z]+)"/g)].map(m => {
      const n = mk(); n.dataset.cskind = m[1]; return n;
    });
    const box = { querySelector: sel => nodes[sel] || null, querySelectorAll: () => kinds };
    vm.runInContext('bindCalSync(__box, __cs)', Object.assign(ctx, { __box: box, __cs: state }));
    return { nodes, kinds };
  };
  const mk = () => { const n = { dataset: {}, addEventListener(ev, fn) { n['_' + ev] = fn; } }; return n; };
  // на старте app.js сам пингует /api/calsync/run — нас интересует последний запрос, а не он
  const post = () => calls.filter(c => c.method === 'POST' && String(c.url).includes('/api/calsync')).at(-1);
  return { ctx, card, bind, calls, alerts, post, screen, renderSettings };
}

const ON = {
  access: 'granted', on: true, calendar: 'c1',
  kinds: { tasks: true, obligations: false, birthdays: true },
  last: '2026-11-02 10:00 · +3 ~1 −0',
  calendars: [{ id: 'c1', title: 'Pipboy', source: 'alex@gmail.com', google: true },
    { id: 'c2', title: 'Домашний', source: 'iCloud', google: false }],
};

test('блок показывает выбранный календарь и что именно выгружается', () => {
  const html = loadApp().card(ON);
  assert.match(html, /<option value="c1" selected>Pipboy · alex@gmail.com ☁</, 'выбранный календарь не отмечен');
  assert.match(html, /<option value="c2"[^>]*>Домашний · iCloud</, 'второй календарь не предложен');
  assert.match(html, /class="pill btn ok" data-cskind="tasks"/, 'включённый вид не подсвечен');
  assert.match(html, /class="pill btn " data-cskind="obligations"/, 'выключенный вид выглядит включённым');
  assert.match(html, /последний прогон: 2026-11-02 10:00/, 'не видно, когда выгружалось в последний раз');
  assert.match(html, /односторонне/, 'не сказано, что обратно из Google ничего не приедет');
});

test('без доступа к Календарю — только кнопка разрешения, без тумблеров', () => {
  const html = loadApp().card({ access: 'notDetermined', calendars: [] });
  assert.match(html, /id="csAccess"/, 'нечем выдать доступ');
  assert.ok(!html.includes('data-cskind'), 'предлагаем выгружать, когда доступа ещё нет');
  const denied = loadApp().card({ access: 'denied', calendars: [] });
  assert.match(denied, /Системных настройках/, 'при запрете не сказано, где его снять');
});

test('нет выгрузки: в браузере тихо, в приложении — причина и что делать', () => {
  assert.equal(loadApp().card(null), '', 'в браузере, где календаря нет, показали блок');
  const inApp = loadApp({ native: true }).card(null);
  assert.match(inApp, /пересобери\s+приложение в Xcode/, 'в приложении блок пропал молча');
  assert.ok(!inApp.includes('csAccess'), 'предлагаем кнопку доступа, которой в сборке ещё нет');
});

test('ответ старой сборки не читается как «доступ не выдан»', async () => {
  // 500 с {error} раньше принимался за состояние: рисовалась кнопка доступа, а она отправляла
  // в системные настройки, где Pipboy и не может появиться — тупик
  const app = loadApp({ native: true, oldBuild: true });
  await app.renderSettings().catch(() => {});   // экран вешает обработчики на свои кнопки — нам важна разметка
  const html = app.screen.innerHTML;
  assert.match(html, /пересобери\s+приложение в Xcode/, 'не сказано, почему выгрузки нет');
  assert.ok(!html.includes('разрешить доступ к Календарю'),
    'кнопка доступа на сборке без выгрузки — тупик: в настройках системы Pipboy не появится');
});

test('тумблер вида шлёт именно своё переключение', async () => {
  const app = loadApp();
  const { kinds } = app.bind(ON);
  const tasks = kinds.find(k => k.dataset.cskind === 'tasks');
  await tasks._click();
  assert.deepEqual(app.post(), { method: 'POST', url: '/api/calsync/settings', body: { kinds: { tasks: 0 } } },
    'включённые задачи должны выключаться, и только они');
});

test('выгрузку не включить, пока не выбран календарь', async () => {
  const app = loadApp();
  const { nodes } = app.bind({ ...ON, on: false, calendar: null });
  await nodes['#csOn']._click();
  assert.equal(app.post().url, '/api/calsync/run', 'включили выгрузку некуда');   // только стартовый пинг
  assert.match(app.alerts[0] || '', /выбери календарь/, 'молча ничего не сделали');

  const ok = loadApp();
  await ok.bind({ ...ON, on: false }).nodes['#csOn']._click();
  assert.deepEqual(ok.post().body, { on: 1 }, 'с выбранным календарём включение не ушло');
});

test('кнопка «выгрузить сейчас» показывает, что уехало', async () => {
  const app = loadApp();
  await app.bind(ON).nodes['#csRun']._click();
  assert.equal(app.post().url, '/api/calsync/run');
  assert.match(app.alerts[0] || '', /добавлено 2, изменено 1, убрано 0/, 'итог прогона не показан');
});

test('смена календаря в списке сохраняется сразу', async () => {
  const app = loadApp();
  const { nodes } = app.bind(ON);
  await nodes['#csCal']._change({ target: { value: 'c2' } });
  assert.deepEqual(app.post().body, { calendar: 'c2' }, 'выбор календаря не сохранился');
});

test('на старте выгрузка догоняется сама, без кнопок', () => {
  const app = loadApp();
  const pings = app.calls.filter(c => c.method === 'POST' && c.url === '/api/calsync/run');
  assert.equal(pings.length, 1, 'при запуске не догоняем то, что менялось при закрытом приложении');
});

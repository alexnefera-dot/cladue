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
  const post = () => calls.filter(c => c.method === 'POST' && /\/api\/(calsync|gtasks)/.test(String(c.url))).at(-1);
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
  assert.ok(!app.calls.some(c => String(c.url).includes('/settings')), 'включили выгрузку некуда');
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

test('на старте обе выгрузки догоняются сами, без кнопок', () => {
  const app = loadApp();
  const ping = u => app.calls.filter(c => c.method === 'POST' && c.url === u).length;
  assert.equal(ping('/api/calsync/run'), 1, 'при запуске не догоняем календарь');
  assert.equal(ping('/api/gtasks/run'), 1, 'при запуске не догоняем Google Tasks');
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

test('выключил выгрузку — предлагаем убрать выгруженное', async () => {
  // Отдельной красной кнопки для чистки нет: она нужна ровно в этот момент, а потом
  // только мозолит глаза. Выключили и согласились — убираем своё из календаря.
  const app = loadApp();
  app.ctx.confirm = () => true;
  await app.bind(ON).nodes['#csOn']._click();
  assert.equal(app.post().url, '/api/calsync/purge', 'выключили, а выгруженное осталось висеть');

  // отказался — ничего не трогаем
  const keep = loadApp();
  keep.ctx.confirm = () => false;
  await keep.bind(ON).nodes['#csOn']._click();
  assert.equal(keep.post().url, '/api/calsync/settings', 'убрали события, хотя человек отказался');

  // включение чистку не предлагает вовсе
  const on = loadApp();
  on.ctx.confirm = () => true;
  await on.bind({ ...ON, on: false }).nodes['#csOn']._click();
  assert.equal(on.post().url, '/api/calsync/settings', 'при включении предложили что-то удалить');
});

test('то же у Google Tasks: выключил — предложили убрать задачи', async () => {
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

test('гугл-календаря в системе нет — говорим, как его туда добавить', () => {
  const html = loadApp().card({ ...ON, calendar: null, calendars: ICLOUD });
  assert.match(html, /Интернет-аккаунты → Google/, 'не сказано, откуда возьмётся гугл-календарь');
  assert.match(html, /в iCloud писать тоже можно/i, 'не сказано, что выбор iCloud — рабочий вариант');
});

test('выбран не гугловый календарь — предупреждаем, что в Google не уедет', () => {
  const warn = loadApp().card({ ...ON, calendar: 'c1', calendars: ICLOUD });
  assert.match(warn, /выбран «Домашний» · iCloud/, 'не названо, что именно выбрано');
  assert.match(warn, /в Google не попадут/, 'молча пишем мимо Google');

  const google = loadApp().card(ON);   // в ON выбран гугловый c1
  assert.ok(!google.includes('в Google не попадут'), 'ругаемся на правильный выбор');
  assert.ok(!google.includes('Интернет-аккаунты → Google'), 'учим добавлять аккаунт, который уже есть');
});

test('аккаунт виден, а писать некуда — это другой случай, чем «аккаунта нет»', () => {
  // гугл добавлен в систему, но из него доступны только календари для чтения
  const seen = loadApp().card({ ...ON, calendar: null, calendars: ICLOUD,
    sources: ['iCloud', 'alexnefera@gmail.com'] });
  assert.match(seen, /аккаунт «alexnefera@gmail.com» системный Календарь уже видит/,
    'советуем добавлять аккаунт, который уже добавлен');
  assert.match(seen, /перезапусти Pipboy/, 'не сказано, что список обновится после перезапуска');
  assert.ok(!seen.includes('Интернет-аккаунты → Google'), 'две взаимоисключающие подсказки сразу');

  // аккаунта нет вовсе — старая подсказка, плюс видно, что Календарь вообще знает
  const none = loadApp().card({ ...ON, calendar: null, calendars: ICLOUD, sources: ['iCloud'] });
  assert.match(none, /Интернет-аккаунты → Google/, 'не сказано, как добавить аккаунт');
  assert.match(none, /сейчас Календарь видит: iCloud/, 'не видно, какие аккаунты есть на самом деле');
});

// Итог прогона — единственное, по чему видно, что произошло: пустой календарь сам
// не расскажет, нечего было выгружать, всё уже лежало или сервер не принял.
test('итог прогона различает «нечего», «всё уже там» и обычную выгрузку', () => {
  const r = s => loadApp().ctx.csReport(s);
  const nothing = r({ added: 0, updated: 0, removed: 0, total: 0, found: { tasks: 0, obligations: 0, birthdays: 0 } });
  assert.match(nothing, /Выгружать нечего/, 'пустой прогон не объяснён');
  assert.match(nothing, /задач с датой: 0, платежей: 0, дней рождения: 0/, 'не видно, чего именно не нашлось');

  const same = r({ added: 0, updated: 0, removed: 0, total: 7, calendar: 'Pipboy', source: 'alex@gmail.com',
    found: { tasks: 5, obligations: 2, birthdays: 0 } });
  assert.match(same, /Всё уже на месте в «Pipboy» · alex@gmail.com/, 'не сказано, где именно всё лежит');
  assert.match(same, /включена галочкой в приложении Календарь/, 'не подсказано, почему событий не видно');

  const done = r({ added: 5, updated: 1, removed: 0, total: 6, calendar: 'Pipboy', source: 'alex@gmail.com',
    found: { tasks: 4, obligations: 2, birthdays: 0 } });
  assert.match(done, /В «Pipboy» · alex@gmail.com: добавлено 5, изменено 1, убрано 0/, 'не видно, что уехало');
  assert.match(done, /в течение минуты/, 'не сказано, что в Google не мгновенно');

  assert.match(r({ error: 'календарь не выбран или больше не существует' }), /не выбран/, 'ошибка проглочена');
  assert.match(r({ added: 1, updated: 0, removed: 0, total: 1, found: {}, errors: ['Налог: отказ'] }),
    /Не получилось:\nНалог: отказ/, 'отказы сервера не показаны');
});

// ===== Google Tasks: настоящие задачи с галочкой =====
const GT_ON = { client: '123-abc.apps.googleusercontent.com', linked: true, on: true, list: 'L1',
  lists: [{ id: 'L1', title: 'Мои задачи' }, { id: 'L2', title: 'Работа' }], last: '2026-11-02 12:00 · +4 ~0 ✓1 −0' };

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
  assert.match(html, /не дублируются событиями/, 'не сказано, что задачи не уедут дважды');
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

// Интеграционный тест HTTP-поверхности: создание/правка/удаление/сохранение
// по всем разделам — ровно те запросы, что дёргают и веб, и нативное окно (WKWebView).
// Поднимает настоящий server.js в дочернем процессе и бьёт по нему через fetch.
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { rmSync } from 'node:fs';

const here = dirname(fileURLToPath(import.meta.url));
const serverJs = join(here, '..', 'server.js');
const PORT = 7766;
const H = `http://127.0.0.1:${PORT}`;
const DB = join(tmpdir(), `crud-http-${process.pid}.db`);

let srv;

const J = (u, m = 'GET', b) =>
  fetch(H + u, { method: m, headers: { 'Content-Type': 'application/json' }, body: b ? JSON.stringify(b) : undefined });
const j = async (u, m, b) => { const r = await J(u, m, b); return r.ok ? r.json().catch(() => ({})) : { _status: r.status }; };
const tree = () => j('/api/tree');

before(async () => {
  srv = spawn(process.execPath, [serverJs], {
    env: { ...process.env, PORT: String(PORT), PIPBOY_DB: DB },
    stdio: 'ignore',
  });
  // ждём готовности сервера
  for (let i = 0; i < 80; i++) {
    try { const r = await fetch(H + '/api/tree'); if (r.ok) return; } catch {}
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('server did not start');
});

after(() => {
  if (srv) srv.kill('SIGTERM');
  for (const ext of ['', '-shm', '-wal']) { try { rmSync(DB + ext); } catch {} }
});

test('Цели: создать / переименовать / тип / срок / заметка-блок / подзадача / удалить', async () => {
  const t0 = await tree();
  const inbox = t0.nodes.find(n => n.is_category && n.title.includes('Инбокс'));
  const created = await j('/api/nodes', 'POST', { title: 'CRUD-тест задача', parent_id: inbox.id });
  assert.ok(created.id, 'создание узла вернуло id');
  const patched = await j('/api/nodes/' + created.id, 'PATCH', { kind: 'task', priority: 'P1', due_date: '2026-08-01', title: 'CRUD-тест переим' });
  assert.equal(patched.title, 'CRUD-тест переим');
  assert.equal(patched.kind, 'task');
  assert.equal(patched.due_date, '2026-08-01');
  const note = await j('/api/nodes/' + created.id, 'PATCH', { note: 'строка1\nстрока2' });
  assert.ok(note.note.includes('строка2'), 'заметка-блок сохранилась');
  const tog = await j('/api/nodes/' + created.id + '/toggle', 'POST');
  assert.equal(tog.status, 'done', 'отметка выполнено');
  const child = await j('/api/nodes', 'POST', { title: 'подзадача', parent_id: created.id });
  await j('/api/nodes/' + child.id + '/reorder', 'POST', { ref_id: created.id, where: 'before' });
  const del = await j('/api/nodes/' + created.id, 'DELETE');
  assert.ok(del.count >= 1, 'удаление в корзину (с потомком)');
});

test('Рутины: создать / время / слот / переименовать / планируемые / удалить', async () => {
  await j('/api/routines', 'POST', { name: 'CRUD-рутина', slot: 'утро' });
  const r = (await j('/api/routines')).find(x => x.name === 'CRUD-рутина');
  assert.ok(r, 'рутина создалась');
  await j('/api/routines/' + r.id, 'PATCH', { time: '07:30', slot: 'вечер', name: 'CRUD-переим' });
  const after = (await j('/api/routines')).find(x => x.id === r.id);
  assert.equal(after.time, '07:30');
  assert.equal(after.slot, 'вечер');
  assert.equal(after.name, 'CRUD-переим');
  await j('/api/routines', 'POST', { name: 'планируемая', planned: true });
  assert.ok((await j('/api/routines/planned')).some(x => x.name === 'планируемая'), 'планируемая в своём списке');
  assert.ok(!(await j('/api/routines')).some(x => x.name === 'планируемая'), 'планируемая не в активных');
  await j('/api/routines/' + r.id, 'DELETE');
  assert.ok(!(await j('/api/routines')).some(x => x.id === r.id), 'рутина удалена');
});

test('Люди: создать / правка ДР·ритм / контакт / удалить', async () => {
  await j('/api/people', 'POST', { name: 'CRUD-чел', birthday: '06-20', rhythm_days: 14 });
  const p = (await j('/api/people')).find(x => x.name === 'CRUD-чел');
  assert.ok(p && p.days_to_birthday != null, 'человек создан с ДР');
  await j('/api/people/' + p.id, 'PATCH', { rhythm_days: 7, tags: 'падл' });
  const after = (await j('/api/people')).find(x => x.id === p.id);
  assert.equal(after.rhythm_days, 7);
  assert.equal(after.tags, 'падл');
  await j('/api/people/' + p.id + '/contacted', 'POST', { note: 'созвон' });
  assert.equal((await j('/api/people')).find(x => x.id === p.id).overdue_contact, 0, 'контакт сбросил просрочку');
  await j('/api/people/' + p.id, 'DELETE');
  assert.ok(!(await j('/api/people')).some(x => x.id === p.id), 'человек удалён');
});

test('Финансы: счёт / портфель / пассив / обязательство / долг / транзакция / бюджет', async () => {
  await j('/api/fin/accounts', 'POST', { name: 'CRUD-счёт', balance: 1000, currency: '€' });
  let f = await j('/api/fin');
  const acc = f.accounts.find(a => a.name === 'CRUD-счёт');
  assert.ok(acc, 'счёт создан');
  await j('/api/fin/accounts/' + acc.id, 'PATCH', { balance: 1500, note: 'подушка' });
  f = await j('/api/fin');
  assert.equal(f.accounts.find(a => a.id === acc.id).balance, 1500, 'баланс счёта сохранён');
  assert.equal(f.accounts.find(a => a.id === acc.id).note, 'подушка', 'пометка счёта сохранена');
  await j('/api/fin/accounts/' + acc.id, 'DELETE');
  assert.ok(!(await j('/api/fin')).accounts.some(a => a.id === acc.id), 'счёт удалён');
  // портфель: блок→секция→актив + правка + каскадное удаление
  const block = (await j('/api/fin')).portfolio[0];
  await j('/api/fin/items', 'POST', { parent_id: block.id, name: 'CRUD-секц', kind: 'section' });
  const sec = (await j('/api/fin')).portfolio[0].children.find(c => c.name === 'CRUD-секц');
  assert.ok(sec, 'секция портфеля создана');
  await j('/api/fin/items', 'POST', { parent_id: sec.id, name: 'CRUD-актив', kind: 'asset', value: 500, currency: '€' });
  const asset = (await j('/api/fin')).portfolio[0].children.find(c => c.name === 'CRUD-секц').children[0];
  assert.ok(asset && asset.value === 500, 'актив создан со стоимостью');
  await j('/api/fin/items/' + asset.id, 'PATCH', { value: 750, buy_value: 600 });
  await j('/api/fin/items/' + sec.id, 'DELETE');
  // пассивный доход
  await j('/api/fin/income', 'POST', { name: 'CRUD-аренда', amount: 1200, period: 'monthly' });
  const inc = (await j('/api/fin')).income.find(i => i.name === 'CRUD-аренда');
  assert.ok(inc, 'пассивный доход создан');
  await j('/api/fin/income/' + inc.id, 'PATCH', { amount: 1300, period: 'yearly' });
  assert.equal((await j('/api/fin')).income.find(i => i.id === inc.id).amount, 1300, 'доход отредактирован');
  await j('/api/fin/income/' + inc.id, 'DELETE');
  assert.ok(!(await j('/api/fin')).income.some(i => i.id === inc.id), 'доход удалён');
  // обязательство
  await j('/api/fin/obligations', 'POST', { name: 'CRUD-подписка', amount: 10, period: 'monthly', next_date: '2026-07-01' });
  const obl = (await j('/api/fin')).obligations.find(o => o.name === 'CRUD-подписка');
  assert.ok(obl, 'обязательство создано');
  const paid = await j('/api/fin/obligations/' + obl.id + '/pay', 'POST');
  assert.equal(paid.next_date, '2026-08-01', 'оплата сдвинула дату на месяц');
  await j('/api/fin/obligations/' + obl.id, 'DELETE');
  // долг
  await j('/api/fin/debts', 'POST', { name: 'CRUD-долг', amount: 60, direction: 'owed_to_me', due_date: '2026-07-15' });
  const debt = (await j('/api/fin')).debts.find(d => d.name === 'CRUD-долг');
  assert.ok(debt, 'долг создан');
  await j('/api/fin/debts/' + debt.id, 'PATCH', { amount: 80 });
  assert.equal((await j('/api/fin')).debts.find(d => d.id === debt.id).amount, 80, 'долг отредактирован');
  await j('/api/fin/debts/' + debt.id, 'DELETE');
  // транзакция
  await j('/api/fin/tx', 'POST', { date: '2026-06-13', amount: 25, category: 'еда', direction: 'expense' });
  const tx = await j('/api/fin/tx?month=2026-06');
  assert.ok(tx.rows.some(t => t.amount === 25 && t.category === 'еда'), 'транзакция создалась');
  // бюджет
  await j('/api/setting', 'POST', { key: 'monthly_budget', value: 1500 });
  assert.equal((await j('/api/fin')).budget, 1500, 'базовый минимум сохранён');
});

test('Календарь: создать / правка / перенос (DnD-дата) / удалить', async () => {
  await j('/api/events', 'POST', { title: 'CRUD-событие', date: '2026-06-20', time: '14:00', recur: 'none' });
  const ev = (await j('/api/calendar?month=2026-06')).items.find(i => i.title === 'CRUD-событие');
  assert.ok(ev, 'событие создано');
  await j('/api/events/' + ev.id, 'PATCH', { date: '2026-06-25' });
  assert.ok((await j('/api/calendar?month=2026-06')).items.some(i => i.title === 'CRUD-событие' && i.date === '2026-06-25'), 'событие перенесено (DnD-дата)');
  await j('/api/events/' + ev.id, 'DELETE');
  assert.ok(!(await j('/api/calendar?month=2026-06')).items.some(i => i.title === 'CRUD-событие'), 'событие удалено');
});

test('Инфо: создать / сохранить / история версий / вложить (DnD) / удалить', async () => {
  const pg = await j('/api/pages', 'POST', { title: 'CRUD-страница' });
  assert.ok(pg.id, 'страница создана');
  await j('/api/pages/' + pg.id, 'PATCH', { content: '# Заголовок\n- пункт 1\n- пункт 2' });
  const got = await j('/api/pages/' + pg.id);
  assert.ok(got.content.includes('пункт 2'), 'содержимое сохранено');
  await j('/api/pages/' + pg.id, 'PATCH', { content: '# Изменено' });
  assert.ok((await j('/api/pages/' + pg.id + '/revisions')).length >= 1, 'история версий пишется');
  const sub = await j('/api/pages', 'POST', { title: 'CRUD-подстраница' });
  await j('/api/pages/' + sub.id + '/move', 'POST', { parent_id: pg.id });
  assert.equal((await j('/api/pages')).find(p => p.id === sub.id).parent_id, pg.id, 'подстраница вложена (DnD)');
  await j('/api/pages/' + pg.id, 'DELETE');
  assert.ok(!(await j('/api/pages')).some(p => p.id === pg.id), 'страница удалена');
});

test('Психология: практика / колесо / шаг→задача / рабочий лог', async () => {
  await j('/api/psy/practices', 'POST', { name: 'CRUD-практика', kind: 'schedule', days: '2,4' });
  const pr = (await j('/api/psy')).practices.find(p => p.name === 'CRUD-практика');
  assert.ok(pr, 'практика создана');
  await j('/api/psy/practices/' + pr.id + '/log', 'POST', { note: 'сделал' });
  await j('/api/psy/practices/' + pr.id, 'DELETE');
  assert.ok(!(await j('/api/psy')).practices.some(p => p.id === pr.id), 'практика удалена');
  const area = (await j('/api/psy')).wheel.areas[0];
  await j('/api/psy/areas/' + area.id, 'PATCH', { step: 'CRUD-шаг', current_desc: 'сейчас так' });
  const wt = await j('/api/psy/areas/' + area.id + '/task', 'POST');
  assert.ok(wt.node && wt.node.kind === 'task', 'шаг сектора → задача в целях');
  await j('/api/psy/worklog', 'POST', { note: 'CRUD-работа' });
  assert.ok((await j('/api/psy')).worklog.some(w => w.note === 'CRUD-работа'), 'рабочий лог записан');
});

test('Трекинг: метрика / значение / полярность / переименовать / чек-ин / удалить', async () => {
  await j('/api/track/metrics', 'POST', { name: 'CRUD-метрика', type: 'bool', polarity: 'minus' });
  const m = (await j('/api/track')).metrics.find(x => x.name === 'CRUD-метрика');
  assert.ok(m && m.polarity === 'minus', 'метрика создана как регресс');
  await j('/api/track/metrics/' + m.id + '/value', 'POST', { value: 1, date: '2026-06-13' });
  assert.ok((await j('/api/track')).metrics.find(x => x.id === m.id).history.some(h => h.date === '2026-06-13'), 'отметка за день сохранена');
  await j('/api/track/metrics/' + m.id, 'PATCH', { name: 'CRUD-переим', polarity: 'plus' });
  assert.equal((await j('/api/track')).metrics.find(x => x.id === m.id).name, 'CRUD-переим', 'метрика переименована');
  await j('/api/track/checkin', 'POST', { mood: 3, note: 'хороший день' });
  assert.ok((await j('/api/track')).checkins.some(c => c.note === 'хороший день'), 'чек-ин сохранён');
  await j('/api/track/metrics/' + m.id, 'DELETE');
  assert.ok(!(await j('/api/track')).metrics.some(x => x.id === m.id), 'метрика удалена');
});

test('Корзина: попадание / восстановление / очистка', async () => {
  const n = await j('/api/nodes', 'POST', { title: 'для корзины' });
  await j('/api/nodes/' + n.id, 'DELETE');
  assert.ok((await j('/api/trash')).length >= 1, 'удалённое в корзине');
  const cleared = await j('/api/trash/clear', 'POST');
  assert.ok(cleared.cleared >= 1, 'очистка корзины работает');
  assert.equal((await j('/api/trash')).length, 0, 'корзина пуста после очистки');
});

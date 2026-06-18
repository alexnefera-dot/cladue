import http from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createDb, seed, seedFin, ensurePortfolio, ensureRates, ensureEnergy } from './db.js';
import * as core from './core.js';
import * as fin from './fin.js';
import * as cal from './cal.js';
import { buildToday } from './today.js';
import * as life from './life.js';
import * as notes from './notes.js';
import { seedDemo, wipeDemo, demoWiped } from './seed.js';
import * as psy from './psy.js';
import * as spheres from './spheres.js';
import { exportAll, backupDb, lastBackupDate } from './export.js';
import { audit } from './audit.js';
import { upcomingNotifications } from './notify.js';
import { execFile } from 'node:child_process';
import os from 'node:os';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
// версия = короткий хэш коммита: видно в шапке, помогает понять «обновился ли я»
let VERSION = 'dev';
execFile('git', ['log', '-1', '--format=%h · %ad', '--date=format:%d.%m %H:%M'], { cwd: ROOT },
  (e, out) => { if (!e && out.trim()) VERSION = out.trim(); });
const DB_PATH = process.env.PIPBOY_DB ?? join(ROOT, 'data.db');
const PORT = Number(process.env.PORT ?? 7777);

const fresh = DB_PATH === ':memory:' || !existsSync(DB_PATH);
const db = createDb(DB_PATH);
if (fresh) { seed(db); console.log('БД создана: категории готовы, вставляй блоки через «⤓ Импорт» →', DB_PATH); }
ensurePortfolio(db);
ensureRates(db);
psy.ensureWheel(db);      // секторы колеса — это структура, не демо
psy.ensurePositiveIntent(db); // техника «Позитивное намерение» с 7 вопросами
ensureEnergy(db);         // ⚡ Энергия жизни + Банк впечатлений — тоже структура
notes.ensureInfoTree(db); // ветки Инфо: Finance / Mindset / Fun / Work / Health
{ // старый трекинг из гугл-таблицы: колонки + история отметок, разово
  const imp = life.importOldTracking(db);
  if (imp) {
    console.log(`Импорт старого трекинга: отметок=${imp.imported}`);
    if (imp.months?.length)   // заметки листа «Month» — страницей в Инфо
      notes.addPage(db, { title: 'Трекинг — заметки месяцев', content:
        imp.months.map(([mon, txt]) => `## ${mon}\n\n${txt}`).join('\n\n') });
  }
}
if (!demoWiped(db)) {     // после «удалить демо-данные» сиды не доливаются никогда
  if (db.prepare('SELECT count(*) AS c FROM accounts').get().c === 0) {
    seedFin(db);
    console.log('Финансы наполнены примерами (всё с пометкой «пример» — удаляй и заводи своё)');
  }
  notes.seedPages(db);    // демо-страницы Инфо
  life.seedPeople(db);    // 5 тестовых людей
  seedDemo(db);           // демо-данные по всем разделам
  psy.seedPsy(db);        // практики, колесо, рабочий лог
}
notes.pruneTrash(db);     // корзина: чистим старше 30 дней
// авто-бэкап: не чаще раза в день
if (DB_PATH !== ':memory:' && lastBackupDate(ROOT) !== (() => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; })()) {
  const f = backupDb(DB_PATH, ROOT, fin.getSetting(db, 'backup_dir', '') || null);
  if (f) console.log('Авто-бэкап базы:', f);
}
{
  const c = q => db.prepare(q).get().c;
  console.log(`Наполнение: записи=${c('SELECT count(*) AS c FROM nodes WHERE is_category=0')}`
    + ` · страницы=${c('SELECT count(*) AS c FROM pages')}`
    + ` · люди=${c('SELECT count(*) AS c FROM people')}`
    + ` · рутины=${c('SELECT count(*) AS c FROM routines')}`
    + ` · события=${c('SELECT count(*) AS c FROM events')}`
    + ` · транзакции=${c('SELECT count(*) AS c FROM transactions')}`);
}
fin.recordSnapshot(db);   // история нетворса: один замер в день

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.json': 'application/json' };

// адрес в домашней сети — открыть с телефона; данные при этом не покидают Mac
function lanUrl() {
  for (const list of Object.values(os.networkInterfaces()))
    for (const i of list ?? [])
      if (i.family === 'IPv4' && !i.internal) return `http://${i.address}:${PORT}`;
  return null;
}

function json(res, code, data) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(data));
}

async function body(req) {
  let raw = '';
  for await (const c of req) raw += c;
  return raw ? JSON.parse(raw) : {};
}

// ===== Защита API: замок действует и на уровне HTTP, не только в UI.
// Без ключа кто угодно в той же Wi-Fi-сети мог читать базу напрямую через API.
const API_OPEN = new Set(['/api/lock', '/api/lock/unlock', '/api/info']);
function apiAuthorized(req, p) {
  if (!p.startsWith('/api/')) return true;          // статика открыта
  if (API_OPEN.has(p)) return true;                 // вход в замок и версия
  // ты физически за этим Mac (вход в систему/Touch ID пройдены) — локальные
  // запросы всегда с полным доступом. Ключ-пароль нужен только удалённым
  // устройствам (телефон, чужой Wi-Fi) — против перехвата в сети.
  const ra = req.socket.remoteAddress ?? '';
  if (ra === '127.0.0.1' || ra === '::1' || ra === '::ffff:127.0.0.1') return true;
  if (!psy.lockEnabled(db)) return true;            // замок выключен — открыто и для сети
  const key = req.headers['x-pipboy-key'];
  return !!key && key === (db.prepare(`SELECT value FROM settings WHERE key = 'lock_pw_hash'`).get()?.value ?? '');
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  try {
    let m;
    if (!apiAuthorized(req, p)) return json(res, 401, { error: 'заперто — введи пароль замка' });
    if (p === '/api/tree' && req.method === 'GET') return json(res, 200, core.listTree(db));
    if (p === '/api/info' && req.method === 'GET')
      return json(res, 200, { lan: lanUrl(), demoWiped: demoWiped(db), version: VERSION });
    if (p === '/api/demo/wipe' && req.method === 'POST') return json(res, 200, wipeDemo(db));
    if (p === '/api/audit' && req.method === 'GET') return json(res, 200, audit(db));
    if (p === '/api/notify/upcoming' && req.method === 'GET') return json(res, 200, upcomingNotifications(db));
    if (p === '/api/roulette' && req.method === 'GET') return json(res, 200, { idea: core.rollIdea(db) });
    if (p === '/api/nodes' && req.method === 'POST') {
      const b = await body(req);
      if (!b.title?.trim()) return json(res, 400, { error: 'title required' });
      // ручной ввод типизируется автоматически («?» → вопрос); категории и импорт — нет
      return json(res, 201, b.is_category
        ? core.addChild(db, b.parent_id ?? null, b.title.trim(), 1)
        : core.addChildAuto(db, b.parent_id ?? null, b.title.trim()));
    }
    if ((m = p.match(/^\/api\/nodes\/(\d+)\/reorder$/)) && req.method === 'POST') {
      const b = await body(req);
      try { return json(res, 200, core.reorderNode(db, +m[1], +b.ref_id, b.where === 'before' ? 'before' : 'after')); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/nodes\/(\d+)\/log$/))) {
      if (req.method === 'GET') return json(res, 200, core.listNodeLog(db, +m[1]));
      if (req.method === 'POST') {
        const b = await body(req);
        if (!b.note?.trim()) return json(res, 400, { error: 'note required' });
        core.addNodeLog(db, +m[1], b.note.trim());
        return json(res, 201, { ok: true });
      }
    }
    if ((m = p.match(/^\/api\/nodelog\/(\d+)$/)) && req.method === 'DELETE') {
      core.delNodeLog(db, +m[1]);
      return json(res, 200, { ok: true });
    }
    if (p === '/api/merge' && req.method === 'POST') {
      const b = await body(req);
      try { return json(res, 200, core.mergeNodes(db, b.keep_id, b.dup_id)); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/nodes\/(\d+)$/)) && req.method === 'PATCH')
      return json(res, 200, core.updateNode(db, +m[1], await body(req)));
    if ((m = p.match(/^\/api\/nodes\/(\d+)\/toggle$/)) && req.method === 'POST')
      return json(res, 200, core.toggleNode(db, +m[1]));
    if ((m = p.match(/^\/api\/suggest\/(\d+)$/)) && req.method === 'GET') {
      const r = core.suggestForNode(db, +m[1]);
      return r ? json(res, 200, r) : json(res, 404, { error: 'not found' });
    }
    if (p === '/api/import' && req.method === 'POST') {
      const b = await body(req);
      if (!b.text?.trim()) return json(res, 400, { error: 'text required' });
      const count = core.importBlock(db, b.parent_id ?? null, b.text);
      return json(res, 201, { imported: count });
    }
    if ((m = p.match(/^\/api\/nodes\/(\d+)$/)) && req.method === 'DELETE')
      return json(res, 200, core.deleteNode(db, +m[1]));   // {count, trash_id}
    if ((m = p.match(/^\/api\/nodes\/(\d+)\/move$/)) && req.method === 'POST') {
      const b = await body(req);
      try { return json(res, 200, core.moveNode(db, +m[1], b.parent_id ?? null)); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if (p === '/api/categories' && req.method === 'GET')
      return json(res, 200, core.listCategories(db));
    if (p === '/api/links' && req.method === 'POST') {
      const b = await body(req);
      try { core.addLink(db, b.from_id, b.to_id, b.type ?? 'related'); }
      catch (e) { return json(res, 400, { error: e.message }); }
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/links\/(\d+)$/)) && req.method === 'DELETE') {
      core.removeLink(db, +m[1]);
      return json(res, 200, { ok: true });
    }
    if (p === '/api/dismiss' && req.method === 'POST') {
      const b = await body(req);
      core.dismissPair(db, b.a, b.b);
      return json(res, 200, { ok: true });
    }
    if (p === '/api/search' && req.method === 'GET')
      return json(res, 200, core.search(db, url.searchParams.get('q') ?? ''));

    if (p === '/api/today' && req.method === 'GET') return json(res, 200, buildToday(db));

    // ===== Рутины и Люди =====
    if (p === '/api/routines' && req.method === 'GET') return json(res, 200, life.listRoutines(db));
    if (p === '/api/routines/planned' && req.method === 'GET') return json(res, 200, life.plannedRoutines(db));
    if (p === '/api/routines' && req.method === 'POST') {
      const b = await body(req);
      if (!b.name?.trim()) return json(res, 400, { error: 'name required' });
      life.addRoutine(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/routines\/(\d+)\/check$/)) && req.method === 'POST')
      return json(res, 200, { done: life.toggleRoutineToday(db, +m[1]) });
    if ((m = p.match(/^\/api\/routines\/(\d+)$/))) {
      if (req.method === 'PATCH') { life.patchRoutine(db, +m[1], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { life.delRoutine(db, +m[1]); return json(res, 200, { ok: true }); }
    }
    if (p === '/api/people' && req.method === 'GET') return json(res, 200, life.listPeople(db));
    if (p === '/api/people' && req.method === 'POST') {
      const b = await body(req);
      if (!b.name?.trim()) return json(res, 400, { error: 'name required' });
      life.addPerson(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/people\/(\d+)\/contacted$/)) && req.method === 'POST') {
      const b = await body(req);
      life.contacted(db, +m[1], b.note);
      return json(res, 200, { ok: true });
    }
    if ((m = p.match(/^\/api\/people\/(\d+)$/))) {
      if (req.method === 'PATCH') { life.patchPerson(db, +m[1], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { life.delPerson(db, +m[1]); return json(res, 200, { ok: true }); }
    }
    // ===== Инфо: страницы =====
    if ((m = p.match(/^\/api\/pages\/(\d+)\/reorder$/)) && req.method === 'POST') {
      const b = await body(req);
      try { notes.reorderPage(db, +m[1], +b.ref_id, b.where === 'before' ? 'before' : 'after'); return json(res, 200, { ok: true }); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/pages\/(\d+)\/revisions$/)) && req.method === 'GET')
      return json(res, 200, notes.pageRevisions(db, +m[1]));
    if ((m = p.match(/^\/api\/pages\/(\d+)\/revisions\/(\d+)\/restore$/)) && req.method === 'POST') {
      try { return json(res, 200, notes.restoreRevision(db, +m[1], +m[2])); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if (p === '/api/pages' && req.method === 'GET') return json(res, 200, notes.listPages(db));
    if (p === '/api/pages' && req.method === 'POST') {
      const b = await body(req);
      if (!b.title?.trim()) return json(res, 400, { error: 'title required' });
      return json(res, 201, notes.addPage(db, b));
    }
    if (p === '/api/pages/search' && req.method === 'GET')
      return json(res, 200, notes.searchPages(db, url.searchParams.get('q') ?? ''));
    if (p === '/api/wiki' && req.method === 'GET')
      return json(res, 200, notes.resolveWiki(db, url.searchParams.get('name') ?? '') ?? {});
    if ((m = p.match(/^\/api\/pages\/(\d+)\/backlinks$/)) && req.method === 'GET')
      return json(res, 200, notes.backlinks(db, +m[1]));
    if ((m = p.match(/^\/api\/pages\/(\d+)\/move$/)) && req.method === 'POST') {
      const b = await body(req);
      try { return json(res, 200, notes.movePage(db, +m[1], b.parent_id ?? null)); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/pages\/(\d+)\/lock$/)) && req.method === 'POST') {
      const b = await body(req);
      try { const { enc, ...pg } = notes.lockPage(db, +m[1], b.password, b.content); return json(res, 200, pg); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/pages\/(\d+)\/unlock$/)) && req.method === 'POST') {
      const b = await body(req);
      try { return json(res, 200, notes.unlockPage(db, +m[1], b.password, !!b.remove)); }
      catch (e) { return json(res, 403, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/pages\/(\d+)$/))) {
      if (req.method === 'GET') {
        const pg = notes.getPage(db, +m[1]);
        if (!pg) return json(res, 404, { error: 'not found' });
        const { enc, ...rest } = pg;   // шифротекст наружу не отдаём
        return json(res, 200, rest);
      }
      if (req.method === 'PATCH') {
        try { return json(res, 200, notes.patchPage(db, +m[1], await body(req))); }
        catch (e) { return json(res, 400, { error: e.message }); }
      }
      if (req.method === 'DELETE') return json(res, 200, notes.delPage(db, +m[1]));   // {count, trash_id}
    }
    if ((m = p.match(/^\/api\/nodes\/(\d+)\/plan$/)) && req.method === 'POST') {
      try { return json(res, 201, notes.planPage(db, +m[1])); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }

    // ===== Психология =====
    if (p === '/api/psy' && req.method === 'GET')
      return json(res, 200, {
        practices: psy.listPractices(db),
        wheel: psy.wheel(db),
        worklog: psy.workLog(db),
        decisions: psy.acceptedDecisions(db),
        hasPass: psy.psyHasPass(db),
      });
    // ===== Общий замок разделов: Цели/Финансы/Инфо/Психология =====
    if (p === '/api/lock' && req.method === 'GET') {
      const ra = req.socket.remoteAddress ?? '';
      const local = ra === '127.0.0.1' || ra === '::1' || ra === '::ffff:127.0.0.1';
      // ты физически за этим Mac (вход + Touch ID пройдены) — секции открыты сразу.
      // Пароль секций требуется только удалённым устройствам (телефон).
      return json(res, 200, { enabled: psy.lockEnabled(db), localUnlock: local });
    }
    if (p === '/api/lock/unlock' && req.method === 'POST') {
      const b = await body(req);
      return psy.checkLockPass(db, b.password)
        ? json(res, 200, { ok: true,
            key: db.prepare(`SELECT value FROM settings WHERE key = 'lock_pw_hash'`).get()?.value ?? '' })
        : json(res, 403, { error: 'неверный пароль' });
    }
    if (p === '/api/lock/pass' && req.method === 'POST') {
      const b = await body(req);
      if (psy.lockEnabled(db) && !psy.checkLockPass(db, b.old ?? '')) return json(res, 403, { error: 'неверный текущий пароль' });
      psy.setLockPass(db, b.password ?? '');
      return json(res, 200, { ok: true });
    }
    if (p === '/api/psy/unlock' && req.method === 'POST') {
      const b = await body(req);
      return psy.checkPsyPass(db, b.password)
        ? json(res, 200, { ok: true })
        : json(res, 403, { error: 'неверный пароль' });
    }
    if (p === '/api/psy/pass' && req.method === 'POST') {
      const b = await body(req);
      if (psy.psyHasPass(db) && !psy.checkPsyPass(db, b.old ?? '')) return json(res, 403, { error: 'неверный текущий пароль' });
      psy.setPsyPass(db, b.password ?? '');
      return json(res, 200, { ok: true });
    }
    if (p === '/api/psy/practices' && req.method === 'POST') {
      const b = await body(req);
      if (!b.name?.trim()) return json(res, 400, { error: 'name required' });
      psy.addPractice(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/psy\/practices\/(\d+)\/log$/)) && req.method === 'POST') {
      psy.logPractice(db, +m[1], await body(req));
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/psy\/practices\/(\d+)\/logs$/)) && req.method === 'GET')
      return json(res, 200, psy.practiceLogs(db, +m[1]));
    if ((m = p.match(/^\/api\/psy\/practices\/(\d+)$/))) {
      if (req.method === 'PATCH') { psy.patchPractice(db, +m[1], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { psy.delPractice(db, +m[1]); return json(res, 200, { ok: true }); }
    }
    if (p === '/api/spheres' && req.method === 'GET') return json(res, 200, spheres.buildSpheres(db));
    if (p === '/api/psy/wheel' && req.method === 'POST') {
      const b = await body(req);
      psy.saveWheel(db, b.scores ?? {});
      return json(res, 200, psy.wheel(db));
    }
    if ((m = p.match(/^\/api\/psy\/areas\/(\d+)\/task$/)) && req.method === 'POST') {
      try { return json(res, 201, psy.wheelStepToTask(db, +m[1])); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/psy\/areas\/(\d+)$/)) && req.method === 'PATCH') {
      psy.patchArea(db, +m[1], await body(req));
      return json(res, 200, { ok: true });
    }
    if (p === '/api/psy/worklog' && req.method === 'POST') {
      const b = await body(req);
      if (!b.note?.trim()) return json(res, 400, { error: 'note required' });
      psy.addWork(db, b.note.trim());
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/psy\/worklog\/(\d+)$/)) && req.method === 'DELETE') {
      psy.delWork(db, +m[1]);
      return json(res, 200, { ok: true });
    }

    // ===== Экспорт, бэкап, корзина =====
    if (p === '/api/export' && req.method === 'POST') {
      const r = exportAll(db, ROOT);
      execFile('open', [r.dir], () => {});   // на macOS откроет папку в Finder
      return json(res, 200, r);
    }
    if (p === '/api/backup' && req.method === 'POST') {
      const f = backupDb(DB_PATH, ROOT, fin.getSetting(db, 'backup_dir', '') || null);
      return f ? json(res, 200, { file: f }) : json(res, 400, { error: 'база в памяти — бэкапить нечего' });
    }
    if (p === '/api/trash' && req.method === 'GET') return json(res, 200, notes.listTrash(db));
    if (p === '/api/trash/clear' && req.method === 'POST')
      return json(res, 200, { cleared: db.prepare('DELETE FROM trash').run().changes });
    if ((m = p.match(/^\/api\/trash\/(\d+)\/restore$/)) && req.method === 'POST') {
      const row = db.prepare('SELECT * FROM trash WHERE id = ?').get(+m[1]);
      if (!row) return json(res, 404, { error: 'not found' });
      const payload = JSON.parse(row.payload);
      const newId = row.kind === 'pages'
        ? notes.restorePages(db, payload)
        : core.restoreNodes(db, payload);
      notes.purgeTrash(db, row.id);
      return json(res, 200, { restored: newId, kind: row.kind });
    }
    if ((m = p.match(/^\/api\/trash\/(\d+)$/)) && req.method === 'DELETE') {
      notes.purgeTrash(db, +m[1]);
      return json(res, 200, { ok: true });
    }

    // ===== Трекинг: чек-ин и метрики =====
    if (p === '/api/track' && req.method === 'GET')
      return json(res, 200, {
        checkins: life.checkins(db),
        metrics: life.listMetrics(db),
        monthly: life.monthlyStats(db),
      });
    if (p === '/api/track/checkin' && req.method === 'POST') {
      const b = await body(req);
      life.setCheckin(db, b.mood, b.note ?? '');
      return json(res, 200, { ok: true });
    }
    if (p === '/api/track/metrics' && req.method === 'POST') {
      const b = await body(req);
      if (!b.name?.trim()) return json(res, 400, { error: 'name required' });
      life.addMetric(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/track\/metrics\/(\d+)\/reorder$/)) && req.method === 'POST') {
      const b = await body(req);
      try { life.reorderMetric(db, +m[1], +b.ref_id, b.where === 'before' ? 'before' : 'after'); return json(res, 200, { ok: true }); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/track\/metrics\/(\d+)\/value$/)) && req.method === 'POST') {
      const b = await body(req);
      life.setMetricValue(db, +m[1], b.value, b.date);
      return json(res, 200, { ok: true });
    }
    if ((m = p.match(/^\/api\/track\/metrics\/(\d+)$/))) {
      if (req.method === 'PATCH') { life.patchMetric(db, +m[1], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { life.delMetric(db, +m[1]); return json(res, 200, { ok: true }); }
    }

    if (p === '/api/setting' && req.method === 'POST') {
      const b = await body(req);
      if (!['activity_month', 'monthly_budget', 'backup_dir'].includes(b.key)) return json(res, 400, { error: 'unknown key' });
      fin.setSetting(db, b.key, b.value ?? '');
      return json(res, 200, { ok: true });
    }
    // ===== Календарь =====
    if (p === '/api/calendar' && req.method === 'GET') {
      try { return json(res, 200, cal.calendar(db, url.searchParams.get('month') ?? new Date().toISOString().slice(0, 7))); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if (p === '/api/events' && req.method === 'POST') {
      const b = await body(req);
      if (!b.title?.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(b.date ?? '')) return json(res, 400, { error: 'title и date обязательны' });
      cal.addEvent(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/events\/(\d+)\/done$/)) && req.method === 'POST') {
      const b = await body(req);
      return json(res, 200, cal.toggleEventDone(db, +m[1], b.date));
    }
    if ((m = p.match(/^\/api\/events\/(\d+)$/))) {
      if (req.method === 'PATCH') { cal.patchEvent(db, +m[1], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { cal.delEvent(db, +m[1]); return json(res, 200, { ok: true }); }
    }

    // ===== Финансы =====
    if (p === '/api/fin' && req.method === 'GET') return json(res, 200, fin.listFin(db));
    if (p === '/api/rates/refresh' && req.method === 'POST') {
      try { return json(res, 200, await fin.ratesRefresh(db)); }
      catch (e) { return json(res, 502, { error: 'не удалось получить курсы: ' + e.message }); }
    }
    if ((m = p.match(/^\/api\/rates\/([^/]+)$/)) && req.method === 'PATCH') {
      const b = await body(req);
      return json(res, 200, fin.rateSet(db, decodeURIComponent(m[1]), b.price));
    }
    if (p === '/api/fin/tx' && req.method === 'GET')
      return json(res, 200, fin.txMonth(db, url.searchParams.get('month') ?? new Date().toISOString().slice(0, 7)));
    if (p === '/api/fin/monefy' && req.method === 'POST') {
      const b = await body(req);
      try { return json(res, 201, { imported: fin.importMonefy(db, b.csv ?? '') }); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if (p === '/api/fin/fire' && req.method === 'POST') {
      const b = await body(req);
      for (const k of ['fire_target', 'fire_return_pct', 'fire_monthly_savings'])
        if (k in b) fin.setSetting(db, k, b[k]);
      return json(res, 200, { ok: true });
    }
    if (p === '/api/fin/forecasts' && req.method === 'POST') {
      const b = await body(req);
      if (!b.statement?.trim()) return json(res, 400, { error: 'statement required' });
      fin.addForecast(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/fin\/forecasts\/(\d+)\/resolve$/)) && req.method === 'POST') {
      const b = await body(req);
      fin.resolveForecast(db, +m[1], !!b.outcome);
      return json(res, 200, { ok: true });
    }
    if ((m = p.match(/^\/api\/fin\/forecasts\/(\d+)$/)) && req.method === 'DELETE') {
      fin.delForecast(db, +m[1]);
      return json(res, 200, { ok: true });
    }
    if (p === '/api/fin/properties' && req.method === 'POST') {
      const b = await body(req);
      if (!b.name?.trim()) return json(res, 400, { error: 'name required' });
      fin.addProperty(db, b);
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/fin\/properties\/(\d+)\/rules$/)) && req.method === 'POST') {
      const b = await body(req);
      if (!b.name?.trim()) return json(res, 400, { error: 'name required' });
      try { fin.addRule(db, +m[1], b); return json(res, 201, { ok: true }); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/fin\/properties\/(\d+)$/))) {
      if (req.method === 'PATCH') { fin.patchProperty(db, +m[1], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { fin.delProperty(db, +m[1]); return json(res, 200, { ok: true }); }
    }
    if (p === '/api/fin/macro' && req.method === 'POST') {
      fin.addMacro(db, await body(req));
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/fin\/macro\/(\d+)$/)) && req.method === 'DELETE') {
      fin.delMacro(db, +m[1]);
      return json(res, 200, { ok: true });
    }
    if ((m = p.match(/^\/api\/fin\/items\/(\d+)\/move$/)) && req.method === 'POST') {
      const b = await body(req);
      try { fin.moveItem(db, +m[1], b.parent_id ?? null); return json(res, 200, { ok: true }); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    if ((m = p.match(/^\/api\/fin\/items\/(\d+)\/reorder$/)) && req.method === 'POST') {
      const b = await body(req);
      try { fin.reorderItem(db, +m[1], +b.ref_id, b.where === 'before' ? 'before' : 'after'); return json(res, 200, { ok: true }); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }
    const finMap = {
      accounts: ['addAccount', 'patchAccount', 'delAccount'],
      classes: ['addClass', 'patchClass', 'delClass'],
      steps: ['addStep', 'patchStep', 'delStep'],
      obligations: ['addObligation', 'patchObligation', 'delObligation'],
      items: ['addItem', 'patchItem', 'delItem'],
      tx: ['addTx', 'patchTx', 'delTx'],
      debts: ['addDebt', 'patchDebt', 'delDebt'],
      income: ['addIncome', 'patchIncome', 'delIncome'],
    };
    if ((m = p.match(/^\/api\/fin\/(accounts|classes|steps|obligations|items|tx|debts|income)(?:\/(\d+))?$/))) {
      const [addF, patchF, delF] = finMap[m[1]];
      if (req.method === 'POST' && !m[2]) { fin[addF](db, await body(req)); return json(res, 201, { ok: true }); }
      if (req.method === 'PATCH' && m[2]) { fin[patchF](db, +m[2], await body(req)); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE' && m[2]) { fin[delF](db, +m[2]); return json(res, 200, { ok: true }); }
    }
    if ((m = p.match(/^\/api\/fin\/obligations\/(\d+)\/pay$/)) && req.method === 'POST')
      return json(res, 200, fin.payObligation(db, +m[1]));
    if ((m = p.match(/^\/api\/fin\/steps\/(\d+)\/task$/)) && req.method === 'POST') {
      try { return json(res, 201, fin.stepToTask(db, +m[1])); }
      catch (e) { return json(res, 400, { error: e.message }); }
    }

    const file = p === '/' ? 'index.html' : p.slice(1);
    const full = join(ROOT, 'public', file);
    if (!full.startsWith(join(ROOT, 'public')) || !existsSync(full))
      return json(res, 404, { error: 'not found' });
    res.writeHead(200, {
      'Content-Type': MIME[extname(full)] ?? 'application/octet-stream',
      // локальный сервер: кэш запрещён, чтобы обновления подхватывались без ⌘⇧R
      'Cache-Control': 'no-store',
    });
    res.end(readFileSync(full));
  } catch (e) {
    json(res, 500, { error: e.message });
  }
});

server.listen(PORT, () => console.log(`Pipboy прототип: http://localhost:${PORT}`
  + (lanUrl() ? ` · с телефона (тот же Wi-Fi): ${lanUrl()}` : '')));

// ===== Авто-курсы: бережно к источникам — обновляем не чаще раза в 4 часа,
// проверяем раз в 30 минут (ручная кнопка в Финансах работает как раньше)
const RATES_TTL = 4 * 3600e3;
async function autoRates() {
  const last = db.prepare('SELECT MAX(updated_at) AS u FROM rates WHERE price IS NOT NULL').get().u;
  const age = last ? Date.now() - Date.parse(last.replace(' ', 'T') + 'Z') : Infinity;
  if (age < RATES_TTL) return;
  try {
    const r = await fin.ratesRefresh(db);
    console.log('Курсы обновлены автоматически' + (r.errors.length ? ` (часть источников молчит: ${r.errors.length})` : ''));
  } catch (e) { console.log('Авто-курсы не получились (обновишь кнопкой):', e.message); }
}
autoRates();
setInterval(autoRates, 30 * 60e3).unref();

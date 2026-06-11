import http from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createDb, seed, seedFin, ensurePortfolio, ensureRates } from './db.js';
import * as core from './core.js';
import * as fin from './fin.js';
import * as cal from './cal.js';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const DB_PATH = process.env.PIPBOY_DB ?? join(ROOT, 'data.db');
const PORT = Number(process.env.PORT ?? 7777);

const fresh = DB_PATH === ':memory:' || !existsSync(DB_PATH);
const db = createDb(DB_PATH);
if (fresh) { seed(db); console.log('БД создана: категории готовы, вставляй блоки через «⤓ Импорт» →', DB_PATH); }
if (db.prepare('SELECT count(*) AS c FROM accounts').get().c === 0) {
  seedFin(db);
  console.log('Финансы наполнены примерами (всё с пометкой «пример» — удаляй и заводи своё)');
}
ensurePortfolio(db);
ensureRates(db);

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };

function json(res, code, data) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(data));
}

async function body(req) {
  let raw = '';
  for await (const c of req) raw += c;
  return raw ? JSON.parse(raw) : {};
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  const p = url.pathname;
  try {
    let m;
    if (p === '/api/tree' && req.method === 'GET') return json(res, 200, core.listTree(db));
    if (p === '/api/nodes' && req.method === 'POST') {
      const b = await body(req);
      if (!b.title?.trim()) return json(res, 400, { error: 'title required' });
      return json(res, 201, core.addChild(db, b.parent_id ?? null, b.title.trim(), b.is_category ? 1 : 0));
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
      return json(res, 200, { deleted: core.deleteNode(db, +m[1]) });
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
    if ((m = p.match(/^\/api\/fin\/receivables\/(\d+)\/received$/)) && req.method === 'POST')
      return json(res, 200, fin.receiveReceivable(db, +m[1]));
    if (p === '/api/fin/fire' && req.method === 'POST') {
      const b = await body(req);
      for (const k of ['fire_target', 'fire_return_pct', 'fire_monthly_savings'])
        if (k in b) fin.setSetting(db, k, b[k]);
      return json(res, 200, { ok: true });
    }
    if (p === '/api/fin/macro' && req.method === 'POST') {
      fin.addMacro(db, await body(req));
      return json(res, 201, { ok: true });
    }
    if ((m = p.match(/^\/api\/fin\/macro\/(\d+)$/)) && req.method === 'DELETE') {
      fin.delMacro(db, +m[1]);
      return json(res, 200, { ok: true });
    }
    const finMap = {
      accounts: ['addAccount', 'patchAccount', 'delAccount'],
      classes: ['addClass', 'patchClass', 'delClass'],
      steps: ['addStep', 'patchStep', 'delStep'],
      obligations: ['addObligation', 'patchObligation', 'delObligation'],
      items: ['addItem', 'patchItem', 'delItem'],
      tx: ['addTx', 'patchTx', 'delTx'],
      receivables: ['addReceivable', 'patchReceivable', 'delReceivable'],
    };
    if ((m = p.match(/^\/api\/fin\/(accounts|classes|steps|obligations|items|tx|receivables)(?:\/(\d+))?$/))) {
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
    res.writeHead(200, { 'Content-Type': MIME[extname(full)] ?? 'application/octet-stream' });
    res.end(readFileSync(full));
  } catch (e) {
    json(res, 500, { error: e.message });
  }
});

server.listen(PORT, () => console.log(`Pipboy прототип: http://localhost:${PORT}`));

import http from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { join, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createDb, seed } from './db.js';
import * as core from './core.js';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const DB_PATH = process.env.PIPBOY_DB ?? join(ROOT, 'data.db');
const PORT = Number(process.env.PORT ?? 7777);

const fresh = DB_PATH === ':memory:' || !existsSync(DB_PATH);
const db = createDb(DB_PATH);
if (fresh) { seed(db); console.log('БД создана: категории готовы, вставляй блоки через «⤓ Импорт» →', DB_PATH); }

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
      return json(res, 201, core.addChild(db, b.parent_id ?? null, b.title.trim()));
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

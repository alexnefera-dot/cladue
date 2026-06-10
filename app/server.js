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
if (fresh) { seed(db); console.log('БД создана и наполнена тестовыми данными:', DB_PATH); }

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
    if (p === '/api/state' && req.method === 'GET') return json(res, 200, core.listState(db));
    if (p === '/api/tasks' && req.method === 'POST') {
      const b = await body(req);
      if (!b.title?.trim()) return json(res, 400, { error: 'title required' });
      return json(res, 201, core.createTask(db, b));
    }
    let m;
    if ((m = p.match(/^\/api\/tasks\/(\d+)$/)) && req.method === 'PATCH')
      return json(res, 200, core.updateTask(db, +m[1], await body(req)));
    if ((m = p.match(/^\/api\/tasks\/(\d+)\/toggle$/)) && req.method === 'POST')
      return json(res, 200, core.toggleTask(db, +m[1]));
    if ((m = p.match(/^\/api\/radar\/(\d+)$/)) && req.method === 'GET') {
      const r = core.radar(db, +m[1]);
      return r ? json(res, 200, r) : json(res, 404, { error: 'not found' });
    }
    if (p === '/api/deps' && req.method === 'POST') {
      const b = await body(req);
      try { core.addDep(db, b.predecessor_id, b.successor_id, b.type ?? 'blocks'); }
      catch (e) { return json(res, 400, { error: e.message }); }
      return json(res, 201, { ok: true });
    }
    if (p === '/api/search' && req.method === 'GET')
      return json(res, 200, core.search(db, url.searchParams.get('q') ?? ''));

    // static
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

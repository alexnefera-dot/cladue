// Импорт реальных данных из экспорта Pipboy (data.json) в plaintext-базу трекера.
// Нативное приложение: Настройки → Экспортировать → ~/Downloads/cladue/app/export/<...>/data.json
//
//   node import-real.js /путь/к/data.json [target.db]   (по умолчанию real.db)
//   PIPBOY_DB=real.db PIPBOY_NOSEED=1 node server.js
//
// Берём только таблицы и колонки, которые есть в схеме трекера (лишнее из нативной
// схемы игнорируем). Существующие строки целевых таблиц замещаются.

import { createDb } from './db.js';
import { readFileSync } from 'node:fs';

const jsonPath = process.argv[2];
const dbPath = process.argv[3] || 'real.db';
if (!jsonPath) {
  console.error('Использование: node import-real.js /путь/к/data.json [target.db]');
  process.exit(1);
}

let dump;
try { dump = JSON.parse(readFileSync(jsonPath, 'utf8')); }
catch (e) { console.error('Не прочитать data.json:', e.message); process.exit(1); }

const db = createDb(dbPath);   // схема + миграции (area_id и пр.)
const tablesInDb = new Set(db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(r => r.name));

db.exec('PRAGMA foreign_keys = OFF');
let total = 0, skipped = [];
for (const [t, rows] of Object.entries(dump)) {
  if (!tablesInDb.has(t)) { if (Array.isArray(rows) && rows.length) skipped.push(t); continue; }
  if (!Array.isArray(rows) || !rows.length) continue;
  const cols = new Set(db.prepare(`PRAGMA table_info(${t})`).all().map(c => c.name));
  db.prepare(`DELETE FROM ${t}`).run();
  let n = 0;
  for (const row of rows) {
    const keys = Object.keys(row).filter(k => cols.has(k));
    if (!keys.length) continue;
    const sql = `INSERT OR REPLACE INTO ${t}(${keys.map(k => `"${k}"`).join(',')}) VALUES(${keys.map(() => '?').join(',')})`;
    const vals = keys.map(k => {
      const v = row[k];
      if (v === undefined) return null;
      if (typeof v === 'boolean') return v ? 1 : 0;
      if (v !== null && typeof v === 'object') return JSON.stringify(v);
      return v;
    });
    try { db.prepare(sql).run(...vals); n++; } catch { /* битую строку пропускаем */ }
  }
  console.log(`  ${t}: ${n}`);
  total += n;
}
db.exec('PRAGMA foreign_keys = ON');

console.log(`\nИмпортировано строк: ${total} → ${dbPath}`);
if (skipped.length) console.log(`Пропущены таблицы (нет в трекере): ${skipped.join(', ')}`);
console.log(`\nЗапуск на этих данных:\n  PIPBOY_DB=${dbPath} PIPBOY_NOSEED=1 node server.js`);
console.log('Логи отметок (стрики/история) в экспорт пока не попадают — стрики будут с нуля.');

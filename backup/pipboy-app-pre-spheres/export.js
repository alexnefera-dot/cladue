// Экспорт всего в Markdown + JSON и бэкапы базы. Принцип ТЗ: не лочимся даже на самих себя.
import { mkdirSync, writeFileSync, copyFileSync, existsSync, readdirSync, unlinkSync } from 'node:fs';
import { join } from 'node:path';

const stamp = () => new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
const safe = s => String(s).replace(/[\\/:*?"<>|]/g, '_').slice(0, 60);

const TABLES = ['nodes', 'links', 'pages', 'people', 'contact_log', 'routines', 'routine_log',
  'practices', 'practice_log', 'wheel_areas', 'wheel_scores', 'work_log', 'accounts',
  'portfolio_items', 'steps', 'obligations', 'transactions', 'debts', 'macro_notes',
  'events', 'settings', 'snapshots', 'rates', 'trash'];

export function exportAll(db, rootDir) {
  const dir = join(rootDir, 'export', stamp());
  mkdirSync(join(dir, 'pages'), { recursive: true });
  const files = [];
  const put = (name, text) => { writeFileSync(join(dir, name), text); files.push(name); };

  // полный дамп — источник истины для восстановления/миграции
  const dump = {};
  for (const t of TABLES) {
    try { dump[t] = db.prepare(`SELECT * FROM ${t}`).all(); } catch { /* таблицы может не быть */ }
  }
  put('data.json', JSON.stringify(dump, null, 1));

  // Цели: дерево с типами/статусами/сроками
  const nodes = db.prepare('SELECT * FROM nodes ORDER BY parent_id NULLS FIRST, ord, id').all();
  const byP = {};
  nodes.forEach(n => (byP[n.parent_id ?? 'root'] ??= []).push(n));
  const KIND = { task: 'задача', decision: 'решение', question: 'вопрос', principle: 'принцип', idea: 'идея', worry: 'тревога' };
  const line = n => {
    if (n.is_category) return `## ${n.title}`;
    const bits = [];
    if (n.kind === 'task') bits.push(n.status === 'done' ? '[x]' : '[ ]');
    else if (n.kind) bits.push(`(${KIND[n.kind]}${n.kind === 'decision' && n.status === 'accepted' ? ' ✓' : ''})`);
    if (n.priority) bits.push(n.priority);
    bits.push(n.title);
    if (n.due_date) bits.push(`📅 ${n.due_date}`);
    if (n.answer) bits.push(`→ ${n.answer}`);
    if (n.note) bits.push(`// ${n.note}`);
    return `- ${bits.join(' ')}`;
  };
  const walkN = (n, depth) => '  '.repeat(n.is_category ? 0 : depth) + line(n) + '\n'
    + (byP[n.id] ?? []).map(c => walkN(c, n.is_category ? 0 : depth + 1)).join('');
  put('goals.md', '# Цели\n\n' + (byP['root'] ?? []).map(n => walkN(n, 0)).join('\n'));

  // Инфо: каждая страница отдельным файлом
  for (const p of db.prepare('SELECT * FROM pages ORDER BY id').all()) {
    const name = `pages/${safe(p.title)}-${p.id}.md`;
    writeFileSync(join(dir, name), p.locked
      ? `# ${p.title}\n\n> Содержимое зашифровано паролем. Шифротекст — в data.json (pages.enc).\n`
      : `# ${p.title}\n\n${p.content}`);
    files.push(name);
  }

  // Финансы
  const fmt = n => n == null ? '—' : Math.round(n).toLocaleString('ru-RU');
  const items = db.prepare('SELECT * FROM portfolio_items ORDER BY parent_id NULLS FIRST, ord').all();
  const byPi = {};
  items.forEach(i => (byPi[i.parent_id ?? 'root'] ??= []).push(i));
  const walkP = (i, d) => `${'  '.repeat(d)}- ${i.name}${i.value != null ? `: ${fmt(i.value)} ${i.currency ?? '€'}` : ''}`
    + `${i.buy_value != null ? ` (покупка ${fmt(i.buy_value)})` : ''}${i.is_loan ? ' 🤝займ' : ''}${i.asset_type ? ` [${i.asset_type}]` : ''}\n`
    + (byPi[i.id] ?? []).map(c => walkP(c, d + 1)).join('');
  put('finance.md', '# Финансы\n\n## Портфель\n\n' + (byPi['root'] ?? []).map(i => walkP(i, 0)).join('')
    + '\n## Счета\n\n' + db.prepare('SELECT * FROM accounts').all()
      .map(a => `- ${a.name}: ${fmt(a.balance)} ${a.currency} (обн. ${a.balance_updated_at?.slice(0, 10)})`).join('\n')
    + '\n\n## Обязательства\n\n' + db.prepare('SELECT * FROM obligations').all()
      .map(o => `- ${o.name}: ${fmt(o.amount)} ${o.currency} / ${o.period}${o.next_date ? `, след. ${o.next_date}` : ''}`).join('\n')
    + '\n\n## Долги\n\n' + db.prepare('SELECT * FROM debts').all()
      .map(d => `- ${d.direction === 'i_owe' ? 'я должен' : 'мне должны'}: ${d.name} — ${fmt(d.amount)} ${d.currency}${d.due_date ? `, срок ${d.due_date}` : ''}`).join('\n')
    + '\n\n## Шаги\n\n' + db.prepare('SELECT * FROM steps').all()
      .map(s => `- [${s.status === 'done' ? 'x' : ' '}] ${s.kind}: ${s.title}${s.amount ? ` ${fmt(s.amount)}` : ''}${s.planned_date ? ` 📅${s.planned_date}` : ''}${s.condition ? ` (${s.condition})` : ''}`).join('\n')
    + '\n');

  // Люди, рутины, психология, события — кратко
  put('people.md', '# Люди\n\n' + db.prepare('SELECT * FROM people').all()
    .map(p => `- ${p.name}${p.birthday ? ` 🎂${p.birthday}` : ''}${p.rhythm_days ? ` · ритм ${p.rhythm_days} дн` : ''}${p.last_contact ? ` · контакт ${p.last_contact}` : ''}${p.tags ? ` · ${p.tags}` : ''}`).join('\n') + '\n');
  put('routines.md', '# Рутины\n\n' + db.prepare('SELECT * FROM routines ORDER BY ord').all()
    .map(r => `- ${r.name} (${r.slot}${r.time ? ', ⏰' + r.time : ''})`).join('\n') + '\n');
  put('psychology.md', '# Психология\n\n## Практики\n\n' + db.prepare('SELECT * FROM practices ORDER BY ord').all()
    .map(p => `- ${p.name} [${p.kind}]${p.days ? ` · ${p.days}${p.time ? ' ' + p.time : ''}` : ''}`).join('\n')
    + '\n\n## Колесо (последний замер)\n\n' + db.prepare(`
      SELECT a.name, s.score FROM wheel_scores s JOIN wheel_areas a ON a.id = s.area_id
      WHERE s.date = (SELECT MAX(date) FROM wheel_scores) ORDER BY a.ord`).all()
      .map(r => `- ${r.name}: ${r.score}`).join('\n')
    + '\n\n## Рабочий лог\n\n' + db.prepare('SELECT * FROM work_log ORDER BY date DESC LIMIT 50').all()
      .map(w => `- ${w.date}: ${w.note}`).join('\n') + '\n');
  put('calendar.md', '# События\n\n' + db.prepare('SELECT * FROM events ORDER BY date').all()
    .map(e => `- ${e.date}${e.time ? ' ' + e.time : ''}: ${e.title}${e.recur !== 'none' ? ` (повтор: ${e.recur})` : ''}`).join('\n') + '\n');

  return { dir, files };
}

// Бэкап файла базы; держим последние 20
export function backupDb(dbPath, rootDir, externalDir = null) {
  if (!dbPath || dbPath === ':memory:' || !existsSync(dbPath)) return null;
  const dir = join(rootDir, 'backups');
  mkdirSync(dir, { recursive: true });
  const file = join(dir, `data-${stamp()}.db`);
  copyFileSync(dbPath, file);
  const all = readdirSync(dir).filter(f => f.endsWith('.db')).sort();
  for (const f of all.slice(0, Math.max(0, all.length - 20))) unlinkSync(join(dir, f));
  // внешняя папка (Time Machine, внешний диск): диск умер — бэкап выжил
  if (externalDir) {
    try {
      mkdirSync(externalDir, { recursive: true });
      copyFileSync(dbPath, join(externalDir, `pipboy-${stamp()}.db`));
    } catch { /* папка недоступна (диск не подключён) — локальный бэкап всё равно есть */ }
  }
  return file;
}

export function lastBackupDate(rootDir) {
  const dir = join(rootDir, 'backups');
  if (!existsSync(dir)) return null;
  const all = readdirSync(dir).filter(f => f.endsWith('.db')).sort();
  return all.at(-1)?.slice(5, 15) ?? null;   // data-YYYY-MM-DD...
}

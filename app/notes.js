import crypto from 'node:crypto';
import { norm, tokens } from './db.js';

// ===== Шифрование содержимого страницы (aes-256-gcm, ключ из пароля через scrypt) =====
function encrypt(password, text) {
  const salt = crypto.randomBytes(16);
  const key = crypto.scryptSync(password, salt, 32);
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv('aes-256-gcm', key, iv);
  const data = Buffer.concat([c.update(text, 'utf8'), c.final()]);
  return JSON.stringify({ s: salt.toString('base64'), i: iv.toString('base64'),
    t: c.getAuthTag().toString('base64'), d: data.toString('base64') });
}
function decrypt(password, encStr) {
  const { s, i, t, d } = JSON.parse(encStr);
  const key = crypto.scryptSync(password, Buffer.from(s, 'base64'), 32);
  const dec = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(i, 'base64'));
  dec.setAuthTag(Buffer.from(t, 'base64'));
  try { return Buffer.concat([dec.update(Buffer.from(d, 'base64')), dec.final()]).toString('utf8'); }
  catch { throw new Error('неверный пароль'); }
}

export function listPages(db) {
  return db.prepare('SELECT id, parent_id, ord, title, node_id, locked, updated_at FROM pages ORDER BY parent_id NULLS FIRST, ord, id').all();
}

// Демо-страницы из макета — потрогать редактор, ссылки и пароль (удаляемо).
// Льётся и поверх своих страниц, но один раз (метка — «План переезда»).
// ===== Каркас веток Инфо (структура пользователя, не демо; создаётся один раз) =====
export function ensureInfoTree(db) {
  if (db.prepare(`SELECT value FROM settings WHERE key = 'info_tree_v1'`).get()?.value === '1') return;
  const mk = (title, parent_id = null) => addPage(db, { title, parent_id }).id;
  const fin = mk('Finance');
  for (const t of ['Macro', 'ETF/BTC/GOLD', 'Property', 'Passives']) mk(t, fin);
  const ms = mk('Mindset');
  for (const t of ['Books', 'Регламент 2026', 'Курс', 'Инсайты и установки', 'Глобальный план']) mk(t, ms);
  mk('Cars', mk('Fun'));
  mk('Work');
  mk('Health');
  db.prepare(`INSERT INTO settings(key, value) VALUES('info_tree_v1','1')
    ON CONFLICT(key) DO UPDATE SET value = '1'`).run();
}

export function seedPages(db) {
  if (db.prepare(`SELECT count(*) AS c FROM pages WHERE title LIKE '%План переезда%'`).get().c > 0) return;
  const princ = addPage(db, { title: '📌 Принципы', content:
`# Мои принципы

> Решения принимаю на холодную голову, пересматриваю по расписанию, а не по панике.

- **НЕ СПЕШИМ до 2028** — принцип ветки МХ5
- 10к с продажи откладываем на легализацию своего авто
- Сначала консультация — потом крупные переводы
- Раз в месяц — ревью портфеля, раз в неделю — разбор инбокса
` });
  const kb = addPage(db, { title: 'База знаний', content: 'Корневая страница. Подстраницы — слева в дереве.\n' });
  const inv = addPage(db, { parent_id: kb.id, title: 'Инвестиции', content:
`# Конспект: структура портфеля

Портфель делим на четыре блока:

1. Блок защиты — кэш, облигации, золото
2. Блок роста — ETF акций, S&P 500
3. Блок развития — крипта, эксперименты
4. Замороженный капитал — недвижимость, авто

Связанные задачи: [[Продать X5]]

## Правила ребаланса

- [ ] раз в квартал сверяю факт с целевым
- [ ] отклонение больше 5% — план шагов
- [x] завёл целевой портфель
` });
  addPage(db, { parent_id: inv.id, title: 'Облигации: шпаргалка', content:
`## Что смотрю перед покупкой

1. Дюрация против моего горизонта
2. Купон: фикс или флоатер
3. Налоговый режим

> Доходность к погашению важнее купона.

\`YTM\` считаю в таблице, пример формулы: \`=YIELD(...)\`
` });
  const move = addPage(db, { title: '✈️ План переезда', content:
`# План переезда

> 💡 Связано с задачей [[Продать X5]] и страницей [[Сравнение городов]]

Критерий — баланс стоимости жизни и качества среды.

## Решения

> Решение от 02.06: склоняюсь к варианту Б, пересмотр через 3 месяца.

## Чеклист документов

- [x] загранпаспорта
- [x] справки с работы
- [x] переводы документов
- [ ] апостили
- [ ] страховка
` });
  addPage(db, { parent_id: move.id, title: 'Сравнение городов', content:
`## Критерии

1. Аренда и быт
2. Комьюнити и спорт (падл!)
3. Логистика перелётов
4. Налоговый режим

**Вывод пока:** вариант Б впереди по 3 из 4.
` });
  addPage(db, { title: 'Журнал решений', content:
`# Журнал решений

Шаблон записи:

## ДАТА — Решение
- Контекст:
- Варианты:
- Выбрал и почему:
- Проверить через: 3 месяца
` });
  // приватная страница под паролем для теста: пароль 1234
  const secret = addPage(db, { title: '🔒 Приватное (пример, пароль 1234)', content:
'Это содержимое зашифровано. Сними пароль или поменяй текст — всё через кнопки на странице.\n' });
  lockPage(db, secret.id, '1234');
}

export function getPage(db, id) {
  return db.prepare('SELECT * FROM pages WHERE id = ?').get(id);
}

export function addPage(db, b) {
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?').get(b.parent_id ?? null).o;
  db.prepare('INSERT INTO pages(parent_id, ord, title, content, node_id) VALUES(?,?,?,?,?)')
    .run(b.parent_id ?? null, ord, b.title, b.content ?? '', b.node_id ?? null);
  const id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  db.prepare('INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)')
    .run(id, norm(b.title), norm(b.content ?? ''));
  return getPage(db, id);
}

export function patchPage(db, id, b) {
  const before = getPage(db, id);
  if (before?.locked && 'content' in b) throw new Error('страница под паролем — сохраняй через lock');
  for (const k of ['title', 'content'])
    if (k in b) db.prepare(`UPDATE pages SET ${k} = ?, updated_at = datetime('now') WHERE id = ?`).run(b[k], id);
  if (('title' in b || 'content' in b) && !before?.locked) {
    const p = getPage(db, id);
    db.prepare('UPDATE page_fts SET title_norm = ?, content_norm = ? WHERE rowid = ?')
      .run(norm(p.title), norm(p.content), id);
  }
  return getPage(db, id);
}

// Закрыть паролем (или пересохранить уже закрытую). Из поиска страница уходит.
export function lockPage(db, id, password, newContent) {
  const p = getPage(db, id);
  if (!p) throw new Error('not found');
  if (!password) throw new Error('пустой пароль');
  let content;
  if (p.locked) {
    const old = decrypt(password, p.enc);     // проверка пароля
    content = newContent ?? old;
  } else content = newContent ?? p.content;
  db.prepare(`UPDATE pages SET enc = ?, locked = 1, content = '', updated_at = datetime('now') WHERE id = ?`)
    .run(encrypt(password, content), id);
  db.prepare('DELETE FROM page_fts WHERE rowid = ?').run(id);
  return getPage(db, id);
}

// Открыть по паролю; remove=true — снять пароль насовсем (текст обратно в открытое хранение)
export function unlockPage(db, id, password, remove = false) {
  const p = getPage(db, id);
  if (!p?.locked) throw new Error('страница не под паролем');
  const content = decrypt(password, p.enc);
  if (remove) {
    db.prepare(`UPDATE pages SET enc = NULL, locked = 0, content = ?, updated_at = datetime('now') WHERE id = ?`)
      .run(content, id);
    db.prepare('INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)')
      .run(id, norm(p.title), norm(content));
  }
  return { content };
}

export function movePage(db, id, parent_id) {
  if (id === parent_id) throw new Error('self-parent');
  if (parent_id != null) {
    const desc = db.prepare(`
      WITH RECURSIVE r(x) AS (
        SELECT id FROM pages WHERE parent_id = ?
        UNION SELECT p.id FROM pages p JOIN r ON p.parent_id = r.x
      ) SELECT 1 AS hit FROM r WHERE x = ? LIMIT 1`).get(id, parent_id);
    if (desc) throw new Error('cannot move into own descendant');
  }
  const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?').get(parent_id).o;
  db.prepare(`UPDATE pages SET parent_id = ?, ord = ? WHERE id = ?`).run(parent_id, ord, id);
  return getPage(db, id);
}

export function delPage(db, id) {
  const root = getPage(db, id);
  if (!root) return { count: 0, trash_id: null };
  const rows = db.prepare(`
    WITH RECURSIVE r(x, depth) AS (
      SELECT ?, 0 UNION ALL
      SELECT p.id, r.depth + 1 FROM pages p JOIN r ON p.parent_id = r.x
    ) SELECT p.*, r.depth AS _depth FROM r JOIN pages p ON p.id = r.x ORDER BY r.depth, p.ord`).all(id);
  db.prepare('INSERT INTO trash(kind, label, payload) VALUES(?,?,?)').run(
    'pages', '▤ ' + root.title + (rows.length > 1 ? ` (+${rows.length - 1} подстр.)` : ''),
    JSON.stringify({ rows }));
  const trash_id = db.prepare('SELECT last_insert_rowid() AS id').get().id;
  for (const r of rows) db.prepare('DELETE FROM page_fts WHERE rowid = ?').run(r.id);
  db.prepare('DELETE FROM pages WHERE id = ?').run(id);
  return { count: rows.length, trash_id };
}

// Восстановление страниц (шифрованные возвращаются как были, в индекс не попадают)
export function restorePages(db, payload) {
  const map = {};
  for (const r of payload.rows) {
    let parent = map[r.parent_id] ?? null;
    if (parent == null && r.parent_id != null)
      parent = getPage(db, r.parent_id) ? r.parent_id : null;
    const ord = db.prepare('SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?').get(parent).o;
    db.prepare('INSERT INTO pages(parent_id, ord, title, content, node_id, locked, enc) VALUES(?,?,?,?,?,?,?)')
      .run(parent, ord, r.title, r.content, r.node_id ?? null, r.locked ?? 0, r.enc ?? null);
    const newId = db.prepare('SELECT last_insert_rowid() AS id').get().id;
    map[r.id] = newId;
    if (!r.locked)
      db.prepare('INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)')
        .run(newId, norm(r.title), norm(r.content));
  }
  return map[payload.rows[0]?.id] ?? null;
}

export function listTrash(db) {
  return db.prepare('SELECT id, kind, label, created_at FROM trash ORDER BY id DESC LIMIT 30').all();
}
export function purgeTrash(db, id) { db.prepare('DELETE FROM trash WHERE id = ?').run(id); }
export function pruneTrash(db, days = 30) {
  db.prepare(`DELETE FROM trash WHERE created_at < datetime('now', ?)`).run(`-${days} days`);
}

// Бэклинки: страницы, в тексте которых есть [[Заголовок этой страницы]].
// Регистронезависимо в JS: lower() SQLite не понижает кириллицу.
export function backlinks(db, id) {
  const p = getPage(db, id);
  if (!p) return [];
  const needle = ('[[' + p.title + ']]').toLowerCase();
  return db.prepare('SELECT id, title, content FROM pages WHERE id != ?').all(id)
    .filter(x => x.content.toLowerCase().includes(needle))
    .map(({ id, title }) => ({ id, title }));
}

// [[Имя]] → страница (приоритет) или запись из Задач
export function resolveWiki(db, name) {
  const target = norm(name);
  const page = db.prepare('SELECT id, title FROM pages').all()
    .find(p => norm(p.title) === target);
  if (page) return { type: 'page', id: page.id };
  const node = db.prepare('SELECT id, title FROM nodes WHERE is_category = 0').all()
    .find(n => norm(n.title) === target);
  if (node) return { type: 'node', id: node.id };
  return null;
}

export function searchPages(db, q) {
  const toks = tokens(q);
  if (!toks.length) return [];
  const match = toks.map(x => `"${x.replaceAll('"', '')}"*`).join(' ');
  return db.prepare(`
    SELECT p.id, p.title FROM page_fts JOIN pages p ON p.id = page_fts.rowid
    WHERE page_fts MATCH ? ORDER BY bm25(page_fts) LIMIT 10`).all(match);
}

// «План» записи: найти или создать привязанную страницу (идемпотентно)
export function planPage(db, nodeId) {
  const existing = db.prepare('SELECT * FROM pages WHERE node_id = ?').get(nodeId);
  if (existing) return existing;
  const node = db.prepare('SELECT * FROM nodes WHERE id = ?').get(nodeId);
  if (!node) throw new Error('node not found');
  let root = db.prepare(`SELECT id FROM pages WHERE title = 'Планы задач' AND parent_id IS NULL`).get();
  if (!root) root = addPage(db, { title: 'Планы задач' });
  return addPage(db, {
    parent_id: root.id, node_id: nodeId, title: node.title,
    content: `# План: ${node.title}\n\nКонтекст: ${node.note || '—'}\n\n## Рассуждение\n\n- \n\n## Шаги\n\n- [ ] \n`,
  });
}

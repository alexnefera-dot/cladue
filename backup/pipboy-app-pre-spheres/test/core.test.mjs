import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDb, seed, norm } from '../db.js';
import * as core from '../core.js';

function freshDb() { const db = createDb(':memory:'); seed(db); return db; }
const byTitle = (db, part) =>
  core.listTree(db).nodes.find(n => n.title.includes(part));
const catByTitle = (db, part) =>
  core.listCategories(db).find(n => n.title.includes(part));

// Реальный блок пользователя — как он вставит его в поле импорта
const BLOCK = `5. Авто
    1. SK
        1. Понять, когда будет внж у Натальи - примерно январь, и у меня
        2. Как мы покупаем в SK? Бюджет? Цель? Что?
    2. Х5
        1. Август продать х5?
        2. 10к с продажи откладываем на легализацию своего авто
        3. Стоит ли положить половину Наталье на счет ?
    3. МХ5
        1. НЕ СПЕШИМ до 2028`;

const BLOCK2 = `Семья
    - Консультация за договор
    - Сделать до росписи
        - Продать х5 до надо`;

test('сид: только категории пользователя, ноль записей и связей', () => {
  const db = freshDb();
  const s = core.listTree(db);
  assert.ok(s.nodes.every(n => n.is_category === 1), 'в сиде только категории');
  assert.equal(s.links.length, 0);
  for (const c of ['Инбокс', 'Финансы', 'Налоги', 'Балансы', 'Легализация', 'ВНЖ',
                   'Работа', 'Жизнь', 'История и расчёты', 'Тревоги', 'Глобальные цели'])
    assert.ok(catByTitle(db, c), `категория «${c}» есть`);
  const trev = catByTitle(db, 'Тревоги');
  const sub = s.nodes.filter(n => n.parent_id === trev.id).map(n => n.title);
  assert.equal(sub.length, 8, 'у Тревог 8 подкатегорий');
  assert.ok(sub.includes('Принятые'));
});

test('parseOutline: уровни по отступам, маркеры срезаются', () => {
  const rows = core.parseOutline(BLOCK);
  assert.equal(rows[0].title, 'Авто');
  assert.equal(rows[0].level, 0);
  assert.equal(rows[1].title, 'SK');
  assert.equal(rows[1].level, 1);
  assert.equal(rows[2].level, 2);
  assert.match(rows[2].title, /^Понять/);
  const dash = core.parseOutline(BLOCK2);
  assert.equal(dash[1].title, 'Консультация за договор');
  assert.equal(dash[3].title, 'Продать х5 до надо');
  assert.equal(dash[3].level, 2);
});

test('importBlock: блок ложится в категорию с вложенностью и порядком', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  const n = core.importBlock(db, inbox.id, BLOCK);
  assert.equal(n, 10);
  const avto = byTitle(db, 'Авто');
  assert.equal(avto.parent_id, inbox.id);
  const x5 = byTitle(db, 'Х5');
  const kids = core.listTree(db).nodes.filter(k => k.parent_id === x5.id).sort((a, b) => a.ord - b.ord);
  assert.equal(kids.length, 3);
  assert.match(kids[0].title, /Август/);
  assert.ok(kids.every(k => k.kind === null), 'импорт ничего не типизирует');
});

test('перемещение: запись уходит в категорию, в потомка — нельзя', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  const sellX5 = byTitle(db, 'Август продать');
  const nalogi = core.listCategories(db)
    .find(c => c.title === 'Налоги' && core.getNode(db, c.parent_id).title === 'Финансы');
  core.moveNode(db, sellX5.id, nalogi.id);
  assert.equal(core.getNode(db, sellX5.id).parent_id, nalogi.id);
  const avto = byTitle(db, 'Авто');
  const x5 = byTitle(db, 'Х5');
  assert.throws(() => core.moveNode(db, avto.id, x5.id), /descendant/);
});

test('подсказки: тип (включая тревогу) и срок — только предлагаются', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  assert.equal(core.suggestKind('Стоит ли положить половину Наталье на счет ?'), 'decision');
  assert.equal(core.suggestKind('НЕ СПЕШИМ до 2028'), 'principle');
  assert.equal(core.suggestKind('боюсь что налоги посчитают не так'), 'worry');
  const now = new Date('2026-06-10');
  assert.equal(core.suggestDate('Август продать х5?', now).date, '2026-08-31');
  assert.equal(core.suggestDate('НЕ СПЕШИМ до 2028', now).date, '2027-12-31');
  assert.ok(core.listTree(db).nodes.filter(n => !n.is_category).every(n => !n.kind));
});

test('предложения связей между импортированными блоками: х5 ↔ «Продать х5 до надо»', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  const sem = core.listCategories(db)
    .find(c => c.title === 'Семья' && core.getNode(db, c.parent_id).title === 'Жизнь');
  core.importBlock(db, sem.id, BLOCK2);
  const s = core.suggestForNode(db, byTitle(db, 'Август продать').id);
  assert.match(s.links.map(l => l.node.title).join('|'), /Продать х5 до надо/);
});

test('блокировка только после подтверждения; категории не считаются записями', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  core.importBlock(db, inbox.id, BLOCK2);
  const sell = byTitle(db, 'Август продать');
  const consult = byTitle(db, 'Консультация за договор');
  assert.equal(sell.blocked, false);
  core.updateNode(db, consult.id, { kind: 'task' });
  core.addLink(db, consult.id, sell.id, 'blocks');
  assert.equal(byTitle(db, 'Август продать').blocked, true);
  core.toggleNode(db, consult.id);
  assert.equal(byTitle(db, 'Август продать').blocked, false);
});

test('вложенность любого в любое: вопрос внутрь задачи и наоборот', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  const task = byTitle(db, 'Консультация') ?? core.addChild(db, inbox.id, 'Консультация за договор');
  const q = core.addChild(db, inbox.id, 'Влияет ли договор на накопления?');
  core.updateNode(db, task.id, { kind: 'task' });
  core.updateNode(db, q.id, { kind: 'question' });
  core.moveNode(db, q.id, task.id);                       // вопрос внутрь задачи
  assert.equal(core.getNode(db, q.id).parent_id, task.id);
  const t2 = core.addChild(db, q.id, 'Сходить к юристу');  // задача внутрь вопроса
  core.updateNode(db, t2.id, { kind: 'task' });
  assert.equal(core.getNode(db, t2.id).parent_id, q.id);
});

test('удаление: поддерево уходит целиком и пропадает из поиска', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  const x5 = byTitle(db, 'Х5');
  const before = core.listTree(db).nodes.length;
  const { count: deleted, trash_id } = core.deleteNode(db, x5.id);
  assert.equal(deleted, 4, 'Х5 + 3 ребёнка');
  assert.ok(trash_id, 'удалённое попало в корзину');
  assert.equal(core.listTree(db).nodes.length, before - 4);
  assert.ok(!byTitle(db, 'Август продать'), 'детей больше нет');
  assert.equal(core.search(db, 'х5').length, 0, 'поисковый индекс почищен');
});

test('редактирование: новый текст ищется, старый — нет', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  const n = byTitle(db, 'Понять, когда будет внж');
  core.updateNode(db, n.id, { title: 'Уточнить сроки ВНЖ в консульстве', note: 'записаться на приём' });
  assert.ok(core.search(db, 'консульстве').some(x => x.id === n.id));
  assert.ok(core.search(db, 'приём').some(x => x.id === n.id), 'заметка тоже ищется');
  assert.ok(!core.search(db, 'понять').some(x => x.id === n.id));
});

test('объединение дублей: дети и связи переезжают, дедлайн строже, дубль исчезает', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  core.importBlock(db, inbox.id, 'Продать х5 до надо\n    уточнить дату росписи');
  const keep = byTitle(db, 'Август продать');
  const dup = byTitle(db, 'Продать х5 до надо');
  core.updateNode(db, keep.id, { kind: 'task', due_date: '2026-08-31' });
  core.updateNode(db, dup.id, { kind: 'task', due_date: '2026-07-20', priority: 'P0' });
  const other = core.addChild(db, inbox.id, 'Налоги закрыть');
  core.updateNode(db, other.id, { kind: 'task' });
  core.addLink(db, other.id, dup.id, 'blocks');
  const merged = core.mergeNodes(db, keep.id, dup.id);
  assert.equal(merged.due_date, '2026-07-20', 'взят более ранний срок');
  assert.equal(merged.priority, 'P0');
  assert.match(merged.note, /объединено/);
  assert.ok(!byTitle(db, 'до надо'), 'дубль удалён');
  assert.ok(byTitle(db, 'уточнить дату росписи').parent_id === keep.id, 'ребёнок переехал');
  assert.equal(byTitle(db, 'Август продать').blocked, true, 'связь-блокер перешла');
  assert.equal(core.search(db, 'надо').filter(n => n.id === dup.id).length, 0);
});

test('контекст ветки: принципы и открытые решения видны информационно', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  core.updateNode(db, byTitle(db, 'НЕ СПЕШИМ').id, { kind: 'principle' });
  core.updateNode(db, byTitle(db, 'половину Наталье').id, { kind: 'decision' });
  const s = core.suggestForNode(db, byTitle(db, 'Август продать').id);
  assert.match(s.context.principles.map(p => p.title).join('|'), /НЕ СПЕШИМ/);
  assert.match(s.context.decisions.map(d => d.title).join('|'), /Наталье/);
});

test('ответ решения сохраняется; категории создаются через addChild', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  core.importBlock(db, inbox.id, BLOCK);
  const d = byTitle(db, 'половину Наталье');
  core.updateNode(db, d.id, { kind: 'decision' });
  core.updateNode(db, d.id, { answer: 'Да, после консультации по договору', status: 'accepted' });
  assert.equal(core.getNode(db, d.id).answer, 'Да, после консультации по договору');
  const cat = core.addChild(db, null, 'Спорт', 1);
  assert.equal(cat.is_category, 1);
  assert.ok(core.listCategories(db).some(c => c.title === 'Спорт'));
});

test('поиск с гомоглифами работает по импортированному', () => {
  const db = freshDb();
  core.importBlock(db, catByTitle(db, 'Инбокс').id, BLOCK);
  assert.equal(norm('х5'), 'x5');
  assert.ok(core.search(db, 'x5').some(n => n.title.includes('х5')));
});

test('повторяющаяся задача: при выполнении срок сдвигается, в лог пишется запись', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  const n = core.addChild(db, inbox.id, 'Назначать даты заранее');
  core.updateNode(db, n.id, { kind: 'task', due_date: '2026-06-15', repeat: 'monthly' });
  const r1 = core.toggleNode(db, n.id);
  assert.equal(r1.repeated, true);
  assert.equal(r1.status, 'todo', 'не закрылась');
  assert.equal(r1.due_date, '2026-07-15', 'срок уехал на месяц');
  assert.match(core.listNodeLog(db, n.id)[0].note, /выполнено/);
  core.updateNode(db, n.id, { due_date: '2026-01-31', repeat: 'weekly' });
  assert.equal(core.toggleNode(db, n.id).due_date, '2026-02-07', 'неделя');
  core.updateNode(db, n.id, { repeat: null });
  assert.equal(core.toggleNode(db, n.id).status, 'done', 'без повтора закрывается как обычно');
});

test('лог задачи: добавление, список по убыванию, удаление', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  const n = core.addChild(db, inbox.id, 'Виза');
  core.addNodeLog(db, n.id, 'справки готовы', '2026-06-08');
  core.addNodeLog(db, n.id, 'запись на 11:30');
  const log = core.listNodeLog(db, n.id);
  assert.equal(log.length, 2);
  assert.equal(log[0].note, 'запись на 11:30', 'свежие сверху');
  core.delNodeLog(db, log[1].id);
  assert.equal(core.listNodeLog(db, n.id).length, 1);
});

test('авто-типизация при ручном добавлении; импорт не типизирует', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  assert.equal(core.addChildAuto(db, inbox.id, 'Продать гараж до осени?').kind, 'question');
  assert.equal(core.addChildAuto(db, inbox.id, 'Стоит ли менять брокера').kind, 'decision');
  assert.equal(core.addChildAuto(db, inbox.id, 'НЕ ПАНИКОВАТЬ').kind, 'principle');
  assert.equal(core.addChildAuto(db, inbox.id, 'Понять сроки ВНЖ').kind, 'task');
  assert.equal(core.addChildAuto(db, inbox.id, 'мысли о лете').kind, null, 'непонятное остаётся строкой');
  core.importBlock(db, inbox.id, 'Август продать х5?\n    Стоит ли половину Наталье?');
  const imported = core.listTree(db).nodes.filter(n => n.title.includes('х5') || n.title.includes('Наталье'));
  assert.ok(imported.every(n => n.kind === null), 'импорт сохраняет строки нетронутыми');
});

test('рулетка спонтанности: только живые идеи без срока, с путём и возрастом', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  assert.equal(core.rollIdea(db), null, 'без идей — пусто');
  const n = core.addChild(db, inbox.id, 'Картинг с пацанами');
  core.updateNode(db, n.id, { kind: 'idea' });
  const r = core.rollIdea(db);
  assert.equal(r.id, n.id);
  assert.ok(r.path.includes('Инбокс'), 'путь до идеи');
  assert.equal(r.days, 0, 'свежая');
  // взятая на дату идея из рулетки уходит
  core.updateNode(db, n.id, { due_date: '2026-08-01' });
  assert.equal(core.rollIdea(db), null, 'запланированная не выпадает');
  // задачи не выпадают
  const t = core.addChild(db, inbox.id, 'Просто задача');
  core.updateNode(db, t.id, { kind: 'task' });
  assert.equal(core.rollIdea(db), null);
});

test('создание: распознанная дата ставится сразу (тип + срок)', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  const n = core.addChildAuto(db, inbox.id, 'Продать X5 в августе');
  assert.equal(n.kind, 'task');
  assert.match(n.due_date ?? '', /-08-31$/, 'август → конец августа');
  const q = core.addChildAuto(db, inbox.id, 'Стоит ли менять резину?');
  assert.ok(!q.due_date, 'без месяца в тексте срока нет');
});

test('порядок: запись ставится выше/ниже соседа, циклы запрещены', () => {
  const db = freshDb();
  const inbox = catByTitle(db, 'Инбокс');
  const a = core.addChild(db, inbox.id, 'А');
  const b = core.addChild(db, inbox.id, 'Б');
  const c = core.addChild(db, inbox.id, 'В');
  const order = () => core.listTree(db).nodes
    .filter(n => n.parent_id === inbox.id).map(n => n.title).join('');
  assert.equal(order(), 'АБВ');
  core.reorderNode(db, c.id, a.id, 'before');
  assert.equal(order(), 'ВАБ');
  core.reorderNode(db, a.id, b.id, 'after');
  assert.equal(order(), 'ВБА');
  // перенос из другой ветки: встаёт рядом с соседом, а не в конец
  const other = catByTitle(db, 'Налоги');
  const x = core.addChild(db, other.id, 'Х');
  core.reorderNode(db, x.id, b.id, 'before');
  assert.equal(order(), 'ВХБА');
  // нельзя поставить родителя рядом с собственным потомком
  const child = core.addChild(db, a.id, 'внутри А');
  assert.throws(() => core.reorderNode(db, a.id, child.id, 'after'), /descendant/);
});

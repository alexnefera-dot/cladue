import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

// Сворачивание блоков Финансов. Проверяется не отрисовка, а поведение на живом дереве:
// все блоки должны вести себя одинаково, кнопка блока открывать только его, кнопка в шапке —
// все сразу, и повторные нажатия не должны плодить обёртки.

const SRC = fileURLToPath(new URL('../public/fin.js', import.meta.url));

const mk = (cls = '', text = '') => {
  const n = {
    className: cls, textContent: text, dataset: {}, children: [], innerHTML: '', hidden: false,
    classList: { _s: new Set(cls.split(' ').filter(Boolean)), add(c) { this._s.add(c); }, contains(c) { return this._s.has(c); } },
    after(x) { const p = n._parent; p.children.splice(p.children.indexOf(n) + 1, 0, x); x._parent = p; },
    appendChild(x) { n.children.push(x); x._parent = n; },
    remove() { const p = n._parent; if (p) p.children.splice(p.children.indexOf(n), 1); },
    querySelector(sel) { return n.children.find(c => ('.' + c.className).includes(sel)) || null; },
    querySelectorAll(sel) { return n.children.filter(c => ('.' + c.className).includes(sel)); },
    addEventListener(ev, fn) { n['_' + ev] = fn; },
  };
  return n;
};

const TITLES = ['Портфель · блоки', 'Распределение', 'Цели накопления', 'Сведение капитала',
  'История', 'Пассивный доход', 'Счета', 'Баланс месяца', 'Расходы', 'Доходы',
  'Обязательства и подписки', 'Долги', 'План шагов', 'FIRE · Макро'];

function screen(store = {}) {
  const root = mk();
  TITLES.forEach(t => {
    const sec = mk('sec', t);
    sec.appendChild(mk('pr', '1 234 €'));           // итог в заголовке — его тоже прячем
    root.appendChild(sec);
    root.appendChild(mk('card', 'данные ' + t));
  });
  root.querySelectorAll = sel => {
    const out = [];
    const walk = n => n.children.forEach(c => { if (('.' + c.className).includes(sel.replace('#screen-fin ', ''))) out.push(c); walk(c); });
    walk(root);
    return out;
  };
  const ctx = {
    document: { querySelectorAll: s => root.querySelectorAll(s), getElementById: () => root, createElement: () => mk(), addEventListener() {} },
    console, localStorage: store, fetch: async () => ({ json: async () => ({}) }),
    alert() {}, confirm: () => false, prompt: () => null,
    matchMedia: () => ({ matches: false }), setTimeout, clearTimeout,
  };
  ctx.window = ctx; ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(readFileSync(SRC, 'utf8'), ctx, { filename: 'fin.js' });
  const secs = () => root.children.filter(c => c.classList.contains('sec'));
  const state = () => secs().map(sec => {
    const wrap = root.children[root.children.indexOf(sec) + 1];
    return {
      title: sec.textContent,
      folded: wrap.children.find(c => c.className.includes('foldbody')).hidden,
      stub: !!wrap.children.find(c => c.className.includes('foldstub')),
      numbersHidden: sec.children.find(c => c.className === 'pr').hidden,
      canHide: !!sec.querySelector('.foldhide'),
    };
  });
  const press = i => {
    const sec = secs()[i];
    const wrap = root.children[root.children.indexOf(sec) + 1];
    (wrap.children.find(c => c.className.includes('foldstub')) || sec.querySelector('.foldhide'))._click();
  };
  const wraps = () => root.children.filter(c => c.className.includes('foldwrap')).length;
  return { ctx, state, press, wraps, store };
}

test('свёртка: по умолчанию свёрнуты все блоки, и все одинаково', () => {
  const s = screen();
  s.ctx.finFoldSections();
  const st = s.state();
  assert.equal(st.length, TITLES.length, 'какой-то блок не попал под механизм');
  for (const r of st) {
    assert.ok(r.folded, `«${r.title}» открыт, хотя по умолчанию всё свёрнуто`);
    assert.ok(r.stub, `у «${r.title}» нет кнопки «показать»`);
    assert.ok(r.numbersHidden, `«${r.title}» прячет данные, но не числа в заголовке`);
    assert.ok(!r.canHide, `у свёрнутого «${r.title}» зачем-то есть «× скрыть»`);
  }
});

test('свёртка: кнопка блока открывает только его', () => {
  const s = screen();
  s.ctx.finFoldSections();
  s.press(2);
  const open = s.state().filter(r => !r.folded);
  assert.equal(open.length, 1, 'открылся не один блок');
  assert.equal(open[0].title, TITLES[2], 'открылся не тот блок');
  assert.ok(!open[0].numbersHidden && open[0].canHide, 'у открытого блока нет чисел или «× скрыть»');
});

test('свёртка: кнопка в шапке открывает и закрывает всё, не плодя обёрток', () => {
  const s = screen();
  s.ctx.finFoldSections();
  const wrapsAfterBuild = s.wraps();
  s.ctx.finFoldSections(true);
  assert.equal(s.state().filter(r => r.folded).length, 0, 'после «все блоки» что-то осталось свёрнутым');
  s.ctx.finFoldSections(false);
  assert.equal(s.state().filter(r => !r.folded).length, 0, 'повторное нажатие не свернуло всё');
  assert.equal(s.wraps(), wrapsAfterBuild, 'повторные вызовы удвоили обёртки — разметка поехала');
});

test('свёртка: выбор блока переживает перерисовку', () => {
  const store = {};
  const s = screen(store);
  s.ctx.finFoldSections();
  s.press(5);
  assert.ok(!s.state()[5].folded, 'блок не открылся');

  const again = screen(store);          // та же память — как после перерисовки экрана
  again.ctx.finFoldSections();
  const st = again.state();
  assert.ok(!st[5].folded, 'открытый блок снова свернулся после перерисовки');
  assert.equal(st.filter(r => !r.folded).length, 1, 'вместе с ним открылось что-то ещё');
});

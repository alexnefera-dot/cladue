// Какие селекторы со страницы нужны: ответ отдаётся списком, сам CSS не трогаем.
//
// Текст правил берёт вызывающая сторона из исходников: CSSOM теряет сокращения
// с var() внутри (`background: linear-gradient(..., var(--gold))` читается пустым),
// и собранный из него файл делает текст невидимым.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [файл, вход, выход] = process.argv.slice(2);
  const селекторы = JSON.parse(fs.readFileSync(вход, 'utf8'));
  const исходник = fs.readFileSync(файл, 'utf8');
  const известные = new Set();
  for (const m of исходник.matchAll(/class="([^"]*)"/g)) {
    for (const к of m[1].split(/\s+/)) if (к) известные.add(к);
  }
  for (const m of исходник.matchAll(/(?:'([^'\n]{2,60})'|"([^"\n]{2,60})")/g)) {
    const s = m[1] || m[2];
    if (/^[A-Za-z][\w-]*$/.test(s)) известные.add(s);
  }
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1400, height: 950 } });
  await p.goto('file://' + файл);
  await p.waitForTimeout(900);
  const нужные = await p.evaluate(([список, классы]) => {
    const набор = new Set(классы);
    return список.filter((sel) => {
      // состояния (:hover, ::before) проверке мешают — элемент за ними тот же
      const чистый = sel.replace(/::?[a-z-]+(\([^)]*\))?/gi, '').trim() || '*';
      try { if (document.querySelector(чистый) !== null) return true; } catch (e) { return true; }
      // классы, которые навешивают скрипты (активная вкладка, показанная кнопка),
      // в живом документе не видны — ищем их в исходнике страницы
      const вСелекторе = [...sel.matchAll(/\.([A-Za-z][\w-]*)/g)].map((m) => m[1]);
      return вСелекторе.length > 0 && вСелекторе.every((к) => набор.has(к));
    });
  }, [селекторы, [...известные]]);
  fs.writeFileSync(выход, JSON.stringify(нужные));
  console.log('селекторов: ' + селекторы.length + ', нужных: ' + нужные.length);
  await b.close();
})();

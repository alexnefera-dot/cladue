// Проверка оформленных комплектов на читаемость: открывает каждую страницу в браузере,
// для каждого текстового узла берёт вычисленный цвет и первый непрозрачный фон
// выше по дереву и считает контраст по WCAG. Ниже 3.5 — в отчёт.
// Запуск: NODE_PATH=/opt/node22/lib/node_modules node scripts/oform/контраст.js <папка> [сколько]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');

(async () => {
  const корень = process.argv[2], предел = Number(process.argv[3] || 1e9);
  const комплекты = fs.readdirSync(корень).filter(d => fs.statSync(path.join(корень, d)).isDirectory()).slice(0, предел);
  const браузер = await chromium.launch();
  const стр = await браузер.newPage();
  const плохо = [];
  for (const к of комплекты) {
    const страницы = fs.readdirSync(path.join(корень, к)).filter(f => f.endsWith('.html')).sort();
    for (const имяСтр of страницы) {
    const файл = path.join(корень, к, имяСтр);
    await стр.goto('file://' + файл, { waitUntil: 'load' });
    const беда = await стр.evaluate(() => {
      const яр = c => { const f = x => (x /= 255) <= 0.03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4;
        return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
      const разбор = s => { const m = s.match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
        return m ? [ +m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4] ] : null; };
      const итог = [];
      for (const el of document.querySelectorAll('p,li,td,th,h1,h2,h3,h4,span,a,div,summary,figcaption')) {
        const свой = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 12);
        if (!свой) continue;
        const st = getComputedStyle(el);
        const цв = разбор(st.color); if (!цв) continue;
        let у = el, фон = null, картинка = false;
        while (у) {
          const s = getComputedStyle(у);
          if (s.backgroundImage && s.backgroundImage !== 'none') { картинка = true; break; }
          const b = разбор(s.backgroundColor);
          if (b && b[3] > 0.5) { фон = b; break; }
          у = у.parentElement;
        }
        if (картинка || !фон) continue;
        const l1 = яр(цв), l2 = яр(фон);
        const k = (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05);
        if (k < 3.5) итог.push({ тег: el.tagName, k: +k.toFixed(2), цвет: st.color, фон: `rgb(${фон[0]},${фон[1]},${фон[2]})`,
                                 класс: (el.className || '').toString().slice(0, 40), текст: el.textContent.trim().slice(0, 40) });
      }
      return итог;
    });
    if (беда.length) плохо.push({ комплект: к + '/' + имяСтр, сколько: беда.length, примеры: беда.slice(0, 3) });
    }
  }
  await браузер.close();
  console.log(JSON.stringify({ комплектов: комплекты.length, плохих: плохо.length, список: плохо.slice(0, 12) }, null, 1));
})();

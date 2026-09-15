// Проверка вёрстки: текст, который не влезает в свою коробку и налезает на соседей.
// Ловит схлопнутые колонки (1fr в узкой сетке), длинные слова без переноса, обрезанные подписи.
// Запуск: NODE_PATH=/opt/node22/lib/node_modules node scripts/oform/верстка.js <папка> [сколько]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');

(async () => {
  const корень = process.argv[2], предел = Number(process.argv[3] || 1e9);
  const комплекты = fs.readdirSync(корень).filter(d => fs.statSync(path.join(корень, d)).isDirectory()).slice(0, предел);
  const браузер = await chromium.launch();
  const стр = await браузер.newPage({ viewport: { width: 1100, height: 900 } });
  const плохо = [];
  for (const к of комплекты) {
    for (const f of fs.readdirSync(path.join(корень, к)).filter(x => x.endsWith('.html')).sort()) {
      await стр.goto('file://' + path.join(корень, к, f), { waitUntil: 'load' });
      const беда = await стр.evaluate(() => {
        const итог = [];
        for (const el of document.querySelectorAll('h1,h2,h3,h4,p,li,td,th,span,a,div,summary,figcaption')) {
          if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1)) continue;
          const s = getComputedStyle(el);
          if (s.display === 'none' || s.visibility === 'hidden' || s.position === 'absolute') continue;
          const b = el.getBoundingClientRect();
          if (b.height < 2) continue;
          const тесно = b.width < 24 && el.textContent.trim().length > 3;
          const вылез = s.overflowX === 'visible' && el.scrollWidth > el.clientWidth + 4 && el.clientWidth > 0;
          if (тесно || вылез) итог.push({
            узел: el.tagName + '.' + (el.className || '').toString().split(' ')[0],
            ширина: Math.round(b.width), нужно: el.scrollWidth,
            причина: тесно ? 'коробка схлопнулась' : 'текст шире коробки',
            текст: el.textContent.trim().slice(0, 34) });
        }
        return итог;
      });
      if (беда.length) плохо.push({ страница: к + '/' + f, сколько: беда.length, примеры: беда.slice(0, 3) });
    }
  }
  await браузер.close();
  console.log(JSON.stringify({ комплектов: комплекты.length, страницСБедой: плохо.length, список: плохо.slice(0, 10) }, null, 1));
})();

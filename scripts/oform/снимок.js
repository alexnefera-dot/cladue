// снимок.js <файл.html> <выход.png> [ширина] [фон]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [файл, выход, ширина = '1100', фон = '#ffffff'] = process.argv.slice(2);
  const фрагмент = fs.readFileSync(файл, 'utf8').replace(/ loading="lazy"/g, '');
  const dir = path.dirname(path.resolve(файл));
  const html = `<!doctype html><meta charset="utf-8"><body style="margin:0;background:${фон};padding:24px;font-family:system-ui">${фрагмент}</body>`;
  fs.writeFileSync(path.join(dir, '__снимок.html'), html);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +ширина, height: 1200 }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.join(dir, '__снимок.html'));
  await p.waitForTimeout(250);
  await p.screenshot({ path: выход, fullPage: true });
  await b.close();
  fs.unlinkSync(path.join(dir, '__снимок.html'));
})();

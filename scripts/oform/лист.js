// лист.js <папка выдачи> <выход.png> <фон> <шаг>
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [корень, выход, фон = '#ffffff', шаг = '5'] = process.argv.slice(2);
  const сайты = fs.readdirSync(корень).filter(n => fs.existsSync(path.join(корень, n, 'main.html')))
                  .filter((_, i) => i % +шаг === 0).slice(0, 12);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 900, height: 1000 } });
  const части = [];
  for (const s of сайты) {
    const ф = fs.readFileSync(path.join(корень, s, 'main.html'), 'utf8').replace(/ loading="lazy"/g, '');
    const html = `<!doctype html><meta charset="utf-8"><body style="margin:0;background:${фон};padding:18px;font-family:system-ui">${ф}</body>`;
    const tmp = path.join(корень, s, '__лист.html');
    fs.writeFileSync(tmp, html);
    await p.goto('file://' + tmp);
    await p.waitForTimeout(180);
    const файл = path.join(корень, s, '__лист.png');
    await p.screenshot({ path: файл, clip: { x: 0, y: 0, width: 900, height: 1000 } });
    части.push([s, файл]);
    fs.unlinkSync(tmp);
  }
  await b.close();
  fs.writeFileSync(выход + '.txt', части.map(([s, f]) => s + '\t' + f).join('\n'));
})();

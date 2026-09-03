const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1500,height:1350}});
const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));
await p.goto('file://'+process.argv[2]);await p.waitForTimeout(600);
for(const t of ['days','cards','how','q']){await p.click(`#nav button[data-t="${t}"]`);await p.waitForTimeout(220);}
await p.click('#nav button[data-t="days"]');await p.waitForTimeout(350);
await p.screenshot({path:process.argv[3]+'/w1.png'});
await p.click('#nav button[data-t="how"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/w2.png'});
await p.click('#nav button[data-t="q"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/w3.png'});
console.log(errs.length?errs.join('\n'):'JS-ошибок нет');await b.close();})();

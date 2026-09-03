const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1560,height:1300}});
const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));
await p.goto('file://'+process.argv[2]);await p.waitForTimeout(600);
for(const t of ['doms','cuts','vs']){await p.click(`#nav button[data-t="${t}"]`);await p.waitForTimeout(200);}
await p.click('#nav button[data-t="doms"]');await p.waitForTimeout(300);
await p.screenshot({path:process.argv[3]+'/m1.png'});
await p.click('#nav button[data-t="vs"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/m2.png'});
await p.click('#nav button[data-t="cuts"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/m3.png'});
console.log(errs.length?errs.join('\n'):'JS-ошибок нет');await b.close();})();

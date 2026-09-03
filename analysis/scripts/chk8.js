const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1560,height:1400}});
const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));
await p.goto('file://'+process.argv[2]);await p.waitForTimeout(700);
for(const t of ['cuts','doms','pools','brands','keys']){await p.click(`#nav button[data-t="${t}"]`);await p.waitForTimeout(200);}
await p.click('#nav button[data-t="cuts"]');await p.waitForTimeout(400);
await p.screenshot({path:process.argv[3]+'/c1.png'});
await p.click('#nav button[data-t="pools"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/c2.png'});
await p.click('#nav button[data-t="doms"]');await p.selectOption('#dt','vs');await p.waitForTimeout(400);
await p.screenshot({path:process.argv[3]+'/c3.png'});
console.log(errs.length?errs.join('\n'):'JS-ошибок нет');await b.close();})();

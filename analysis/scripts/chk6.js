const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1500,height:1250}});
const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));
await p.goto('file://'+process.argv[2]);await p.waitForTimeout(600);
for(const s of ['0','1','2','last'])for(const t of ['doms','pools','brands','keys']){
  await p.click(`#sw button[data-v="${s}"]`);await p.click(`#nav button[data-t="${t}"]`);await p.waitForTimeout(120);}
await p.click('#sw button[data-v="last"]');await p.click('#nav button[data-t="doms"]');await p.waitForTimeout(300);
await p.screenshot({path:process.argv[3]+'/d1.png'});
const m=await p.$('.more'); if(m){await m.click();await p.waitForTimeout(200);}
await p.click('#nav button[data-t="pools"]');await p.waitForTimeout(250);await p.screenshot({path:process.argv[3]+'/d2.png'});
await p.click('#nav button[data-t="brands"]');await p.waitForTimeout(250);await p.screenshot({path:process.argv[3]+'/d3.png'});
console.log(errs.length?errs.join('\n'):'JS-ошибок нет');await b.close();})();

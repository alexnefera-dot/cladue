const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1500,height:1250}});
const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));
await p.goto('file://'+process.argv[2]);await p.waitForTimeout(600);
for(const s of ['0','1','2','last'])for(const t of ['all','vs','v']){
  await p.click(`#sw button[data-v="${s}"]`);await p.selectOption('#dt',t);await p.waitForTimeout(120);}
await p.click('#sw button[data-v="last"]');await p.selectOption('#dt','vs');await p.waitForTimeout(350);
await p.screenshot({path:process.argv[3]+'/v1.png'});
await p.selectOption('#dt','v');await p.selectOption('#df','hit');await p.waitForTimeout(300);
await p.screenshot({path:process.argv[3]+'/v2.png'});
for(const t of ['pools','brands','keys']){await p.click(`#nav button[data-t="${t}"]`);await p.waitForTimeout(150);}
console.log(errs.length?errs.join('\n'):'JS-ошибок нет');await b.close();})();

const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1500,height:1100}});
const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));p.on('console',m=>{if(m.type()==='error')errs.push('CONSOLE '+m.text())});
await p.goto('file://'+process.argv[2]);await p.waitForTimeout(700);
const tabs=['pools','doms','brands','keys','nest'];
for(const s of ['0','1','2','last']){
  await p.click(`#sw button[data-v="${s}"]`);await p.waitForTimeout(200);
  for(const t of tabs){await p.click(`#nav button[data-t="${t}"]`);await p.waitForTimeout(150);
    const n=await p.$$eval('#main table tr',r=>r.length);
    if(s==='last')console.log('slot',s,'tab',t,'строк',n);}
}
await p.click('#sw button[data-v="last"]');await p.click('#nav button[data-t="pools"]');await p.waitForTimeout(300);
await p.screenshot({path:process.argv[3]+'/s1.png',fullPage:false});
await p.click('#nav button[data-t="doms"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/s2.png'});
await p.click('#nav button[data-t="brands"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/s3.png'});
await p.click('#nav button[data-t="keys"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/s4.png'});
await p.click('#nav button[data-t="nest"]');await p.waitForTimeout(300);await p.screenshot({path:process.argv[3]+'/s5.png'});
console.log(errs.length?errs.join('\n'):'JS-ошибок нет');await b.close();})();

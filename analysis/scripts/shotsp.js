const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1180,height:1100},deviceScaleFactor:1.5});
const errs=[];p.on('pageerror',e=>errs.push(String(e)));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
await p.goto('file://'+process.cwd()+'/spec.html');await p.waitForTimeout(600);
const h=await p.evaluate(()=>document.documentElement.scrollHeight);
console.log('height',h);
for(let i=0;i<6;i++){await p.evaluate(y=>window.scrollTo(0,y),i*1050);await p.waitForTimeout(200);await p.screenshot({path:'sp'+i+'.png'});}
console.log('ERRORS:',errs.length?errs:'none');await b.close();})();

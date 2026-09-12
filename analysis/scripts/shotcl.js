const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch({executablePath:'/opt/pw-browsers/chromium'});
const p=await b.newPage({viewport:{width:1100,height:1050},deviceScaleFactor:1.4});
const errs=[];p.on('pageerror',e=>errs.push(String(e)));
await p.goto('file://'+process.cwd()+'/collect.html');await p.waitForTimeout(600);
console.log('height',await p.evaluate(()=>document.documentElement.scrollHeight));
for(let i=0;i<3;i++){await p.evaluate(y=>window.scrollTo(0,y),i*980);await p.waitForTimeout(200);await p.screenshot({path:'cl'+i+'.png'});}
console.log('ERRORS:',errs.length?errs:'none');await b.close();})();

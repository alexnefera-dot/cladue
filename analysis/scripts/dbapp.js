const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const NUM=n=>n.toLocaleString('ru-RU');
const EXC=new Set(['5374.team','2535.team']);
const DOMS=Object.entries(D).map(([d,v])=>{
  const bs=Object.entries(v.b).map(([b,x])=>({b,...x}));
  return {d,...v,bs,
    nb10:bs.filter(x=>x.t10>0).length, nb30:bs.filter(x=>x.t30>0).length, nb100:bs.length,
    k3:bs.reduce((a,x)=>a+x.t3,0), k10:bs.reduce((a,x)=>a+x.t10,0),
    k30:bs.reduce((a,x)=>a+x.t30,0), k100:bs.reduce((a,x)=>a+x.t100,0),
    vch:bs.filter(x=>x.t10>0&&x.tier==='ВЧ').length, sch:bs.filter(x=>x.t10>0&&x.tier==='СЧ').length};
});
const BR={};
DOMS.forEach(o=>o.bs.forEach(x=>{
  (BR[x.b]=BR[x.b]||{b:x.b,tier:x.tier,vol:x.vol,rows:[]}).rows.push({d:o.d,...x,group:o.group,lab:o.lab,coh:o.coh,zone:o.zone});
}));
const BRANDS=Object.values(BR).map(o=>{
  o.rows.sort((a,b)=>b.t10-a.t10||b.t30-a.t30||a.best-b.best);
  o.nd10=o.rows.filter(r=>r.t10>0).length; o.nd30=o.rows.filter(r=>r.t30>0).length; o.nd=o.rows.length;
  o.top=o.rows[0]; o.bestpos=Math.min(...o.rows.map(r=>r.best));
  o.nkeys=Math.max(...o.rows.map(r=>r.t100));
  return o;
});
const TORD={'ВЧ':0,'СЧ':1,'НЧ':2};
BRANDS.sort((a,b)=>TORD[a.tier]-TORD[b.tier]||b.vol-a.vol||a.b.localeCompare(b.b));
DOMS.sort((a,b)=>b.k10-a.k10||b.k30-a.k30);
const COHS=[...new Set(DOMS.map(o=>o.coh))];
const st={q:'',coh:'',team:false,strong:false};

const tg=t=>`<span class="tr tr-${t}">${t}</span>`;
const keyChips=ks=>ks.slice(0,14).map(([p,q])=>
  `<span class="kq ${p<=3?'p3':(p<=10?'p10':(p<=30?'p30':''))}"><b>${p}</b> ${E(q)}</span>`).join('')
  +(ks.length>14?`<span class="more">+${ks.length-14}</span>`:'');

function domRows(){
  const q=st.q.toLowerCase();
  let L=DOMS.filter(o=>{
    if(st.coh&&o.coh!==st.coh)return false;
    if(st.team&&o.zone!=='.team')return false;
    if(st.strong&&o.k10===0)return false;
    if(!q)return true;
    return o.d.includes(q)||o.group.toLowerCase().includes(q)||o.bs.some(x=>x.b.includes(q));
  });
  document.getElementById('cnt').textContent=`${L.length} доменов`;
  return L.map((o,i)=>`<tr class="clk" data-i="${i}">
    <td class="l"><b class="dm">${E(o.d)}</b>${EXC.has(o.d)?' <span class="tag ex">исключён</span>':''}
      <div class="mut sm">${E(o.group)}</div></td>
    <td class="l sm">${E(o.zone)}</td>
    <td class="l sm">${E(o.src)}<div class="mut">${[o.dates,o.img,o.acc].filter(x=>x&&x!=='—').map(E).join(' · ')||'&nbsp;'}</div></td>
    <td class="l sm mut">${E(o.lab)}</td>
    <td class="${o.nb10?'good':'mut'}"><b>${o.nb10}</b></td><td>${o.nb30}</td><td>${o.nb100}</td>
    <td>${o.k3}</td><td class="${o.k10?'good':'mut'}"><b>${o.k10}</b></td><td>${o.k30}</td><td>${o.k100}</td>
    <td>${o.vch?`<span class="tr tr-ВЧ">${o.vch}</span>`:'<span class="mut">0</span>'}</td>
    <td>${o.sch?`<span class="tr tr-СЧ">${o.sch}</span>`:'<span class="mut">0</span>'}</td>
    <td class="l sm">${o.bs.filter(x=>x.t10>0).sort((a,b)=>a.best-b.best).slice(0,6)
       .map(x=>`<span class="bch t-${x.tier}">${E(x.b)} <b>${x.best}</b></span>`).join('')||'<span class="mut">—</span>'}</td>
  </tr><tr class="det" hidden><td colspan="14"><div class="inner">${domDetail(o)}</div></td></tr>`).join('');
}
function domDetail(o){
  const bs=o.bs.slice().sort((a,b)=>b.t10-a.t10||a.best-b.best||TORD[a.tier]-TORD[b.tier]);
  return `<h4>${E(o.d)} · ${E(o.group)} · съём ${E(o.lab)} · ${bs.length} брендов в ТОП-100</h4>
  <div class="meta">${[['группа',o.group],['лист',o.sheet.trim()],['автор',o.src],['страниц',o.pages],
    ['даты',o.dates],['картинки/стиль',o.img],['аккаунты',o.acc],['id',o.ids],['контент создан',o.made],
    ['когорта',o.coh],['тест',o.test!=='—'?o.test+' · '+o.arm:'—']]
    .filter(x=>x[1]&&x[1]!=='—'&&x[1]!=='?').map(([k,v])=>
    `<div><span class="mk">${k}</span><span class="mv">${E(v)}</span></div>`).join('')}</div>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Тир</th><th class="l">Частотность</th>
   <th>Лучшая</th><th>Т3</th><th>Т10</th><th>Т30</th><th>Т100</th><th class="l">Ключи и позиции</th>
   </tr></thead><tbody>${bs.map(x=>`<tr>
   <td class="l"><b>${E(x.b)}</b></td><td>${tg(x.tier)}</td><td class="l mono sm">${NUM(x.vol)}</td>
   <td class="${x.best<=3?'good':(x.best<=10?'ok':'')}"><b>${x.best}</b></td>
   <td>${x.t3}</td><td class="${x.t10?'good':'mut'}">${x.t10}</td><td>${x.t30}</td><td>${x.t100}</td>
   <td class="l">${keyChips(x.keys)}</td></tr>`).join('')}</tbody></table></div>`;
}
function brRows(){
  const q=st.q.toLowerCase();
  let L=BRANDS.filter(o=>{
    if(!q)return true;
    return o.b.includes(q)||o.rows.some(r=>r.d.includes(q));
  }).map(o=>{
    let rows=o.rows.filter(r=>(!st.coh||r.coh===st.coh)&&(!st.team||r.zone==='.team'));
    return {...o,rows};
  }).filter(o=>o.rows.length&&(!st.strong||o.rows.some(r=>r.t10>0)));
  document.getElementById('cnt2').textContent=`${L.length} брендов`;
  return L.map((o,i)=>{const top=o.rows[0];
   return `<tr class="clk" data-i="${i}">
    <td class="l"><b class="dm">${E(o.b)}</b></td><td>${tg(o.tier)}</td><td class="l mono sm">${NUM(o.vol)}</td>
    <td class="${o.rows.filter(r=>r.t10>0).length?'good':'mut'}"><b>${o.rows.filter(r=>r.t10>0).length}</b></td>
    <td>${o.rows.filter(r=>r.t30>0).length}</td><td>${o.rows.length}</td>
    <td class="${top.best<=3?'good':(top.best<=10?'ok':'')}"><b>${Math.min(...o.rows.map(r=>r.best))}</b></td>
    <td class="l"><b class="dm">${E(top.d)}</b>${EXC.has(top.d)?' <span class="tag ex">искл.</span>':''}
      <div class="mut sm">${E(top.group)}</div></td>
    <td>${top.t3}</td><td>${top.t10}</td><td>${top.t30}</td>
    <td class="l sm">${top.keys.filter(k=>k[0]<=10).slice(0,5).map(([p,q])=>
      `<span class="kq ${p<=3?'p3':'p10'}"><b>${p}</b> ${E(q)}</span>`).join('')||'<span class="mut">—</span>'}</td>
   </tr><tr class="det" hidden><td colspan="12"><div class="inner">${brDetail(o)}</div></td></tr>`}).join('');
}
function brDetail(o){
  return `<h4>${E(o.b)} · ${tg(o.tier)} · ${NUM(o.vol)} · ${o.rows.length} доменов в ТОП-100</h4>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Группа</th><th class="l">Съём</th>
  <th>Лучшая</th><th>Т3</th><th>Т10</th><th>Т30</th><th>Т100</th><th class="l">Ключи и позиции</th>
  </tr></thead><tbody>${o.rows.map(r=>`<tr>
  <td class="l"><b class="dm">${E(r.d)}</b>${EXC.has(r.d)?' <span class="tag ex">искл.</span>':''}</td>
  <td class="l sm">${E(r.group)}</td><td class="l sm mut">${E(r.lab)}</td>
  <td class="${r.best<=3?'good':(r.best<=10?'ok':'')}"><b>${r.best}</b></td>
  <td>${r.t3}</td><td class="${r.t10?'good':'mut'}">${r.t10}</td><td>${r.t30}</td><td>${r.t100}</td>
  <td class="l">${keyChips(r.keys)}</td></tr>`).join('')}</tbody></table></div>`;
}
function render(){
  document.getElementById('dbody').innerHTML=domRows();
  document.getElementById('bbody').innerHTML=brRows();
}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
const qi=document.getElementById('q');
qi.oninput=()=>{st.q=qi.value.trim();render()};
const cs=document.getElementById('coh');
cs.innerHTML='<option value="">все когорты</option>'+COHS.map(c=>`<option value="${E(c)}">${E(c)}</option>`).join('');
cs.onchange=()=>{st.coh=cs.value;render()};
document.getElementById('team').onchange=e=>{st.team=e.target.checked;render()};
document.getElementById('strong').onchange=e=>{st.strong=e.target.checked;render()};
document.addEventListener('click',e=>{
  const tr=e.target.closest('tr.clk'); if(!tr)return;
  const d=tr.nextElementSibling; if(d&&d.classList.contains('det')) d.hidden=!d.hidden;});
render();

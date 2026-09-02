const D=window.DATA, QD=D.qd, PD=D.pd;
const mkUrl=r=>'https://'+(r.sub?r.sub+'.':'')+r.dom+(r.pg==='/'?'':r.pg)+'/ru'.repeat(r.d||0);
const med=a=>{const x=[...a].sort((p,q)=>p-q);return x.length?x[Math.floor(x.length/2)]:null;};
const ACT=D.pools.filter(p=>!p.excl);
const nf=(x,d=0)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const kfmt=v=>!v?'—':v>=1e6?nf(v/1e6,1)+' млн':v>=1e3?Math.round(v/1e3)+' тыс':v;
const cls=p=>p<=3?'good':p<=10?'now':p<=30?'':'mut';
const pl=(n,a,b,c)=>{const x=Math.abs(n)%100,y=x%10;
  return n+' '+(x>10&&x<20?c:y===1?a:y>1&&y<5?b:c);};
const pgName=p=>p==='/'?'главная':p;

/* ── выбор съёма ─────────────────────────────────────────── */
let SLOT='last';
const snapOf=p=>{
  if(SLOT==='last') return {s:p.snaps[p.snaps.length-1],cl:false,i:p.snaps.length-1};
  const i=Math.min(SLOT,p.snaps.length-1);
  return {s:p.snaps[i],cl:i!==SLOT,i};
};
const prevOf=p=>{const {i}=snapOf(p); return i>0?p.snaps[i-1]:null;};

function buildSwitch(){
  const el=document.getElementById('sw'), opts=[];
  for(let i=0;i<D.nsnap;i++) opts.push([i,['Первый','Второй','Третий'][i]+' замер']);
  opts.push(['last','Самый свежий']);
  el.innerHTML=opts.map(([v,l])=>`<button data-v="${v}" aria-pressed="${String(v)===String(SLOT)}">${l}</button>`).join('');
  el.querySelectorAll('button').forEach(b=>b.onclick=()=>{
    SLOT=b.dataset.v==='last'?'last':+b.dataset.v;
    el.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.v)===String(SLOT)));
    renderAll();});
}

/* ── описание группы обычными словами ────────────────────── */
function gDesc(p){
  const a=[];
  a.push(p.pages==='не прислано'?'страниц неизвестно':p.pages+' страниц');
  if(p.dates==='без дат') a.push('без дат в тексте');
  else if(p.dates==='с датами') a.push('с датами в тексте');
  else a.push('про даты не сказали');
  a.push('зона '+p.zone);
  a.push(p.cap==='потолок 20'?'вложенность ограничена двадцатью':'вложенность не ограничена');
  return a.join(', ');
}

/* ── строки ключей выбранного съёма ───────────────────────── */
function rowsOf(p){
  const {s}=snapOf(p);
  return s.rows.map(r=>({q:QD[r[0]][0],b:QD[r[0]][1],t:QD[r[0]][2],v:QD[r[0]][3],
    dom:p.doms[r[1]],pool:p,p:r[2],d:r[3]<0?null:r[3],pg:PD[r[4]],sub:D.sd[r[5]]||''}));
}
function allRows(){return D.pools.flatMap(p=>p.excl?[]:rowsOf(p));}

/* ── 1. ДОМЕНЫ ───────────────────────────────────────────── */
let open1=new Set(), dFilter='all', dTier='all';
function tDoms(){
  const TF={all:null,vs:['ВЧ','СЧ'],v:['ВЧ']}[dTier];
  const tname={all:'',vs:' — считаются только ВЧ и СЧ ключи',v:' — считаются только ВЧ ключи'}[dTier];
  let h=`<div class="blk"><h2>Каждый домен по отдельности</h2>
  <p class="note">Домены сгруппированы по тому, каким запуском они ушли. Внутри карточки — что домен реально даёт:
  по каким брендам стоит в десятке, какими страницами и на какой глубине адреса.
  Числа — на том замере, который выбран сверху.</p>
  <div class="brow"><span class="mk">какие ключи считать</span>
    <select id="dt">
      <option value="all"${dTier==='all'?' selected':''}>все ключи</option>
      <option value="vs"${dTier==='vs'?' selected':''}>только ВЧ и СЧ — жирный спрос</option>
      <option value="v"${dTier==='v'?' selected':''}>только ВЧ</option>
    </select>
    <span class="mk">показать</span>
    <select id="df">
      <option value="all"${dFilter==='all'?' selected':''}>все домены</option>
      <option value="hit"${dFilter==='hit'?' selected':''}>только те, что есть в десятке</option>
      <option value="miss"${dFilter==='miss'?' selected':''}>только пустые</option>
    </select>
    ${TF?`<span class="bch warnc">ВЧ — спрос больше миллиона в месяц, СЧ — от семисот тысяч. Это ключи, которые приносят деньги.</span>`:''}
  </div>`;

  for(const p of D.pools){
    const {s:snap,cl}=snapOf(p), pr=prevOf(p), n=p.doms.length;
    let R=rowsOf(p); if(TF) R=R.filter(r=>TF.includes(r.t));
    let PR=null;
    if(pr){PR=pr.rows.map(r=>({t:QD[r[0]][2],dom:p.doms[r[1]],p:r[2]}));
           if(TF) PR=PR.filter(r=>TF.includes(r.t));}
    const st={};
    for(const d of p.doms){
      const mine=R.filter(r=>r.dom===d), deps=mine.map(r=>r.d).filter(x=>x!=null);
      const bk=mine.length?mine.reduce((a,b)=>b.p<a.p?b:a):null;
      st[d]={t10:mine.filter(r=>r.p<=10).length,t30:mine.filter(r=>r.p<=30).length,
             t100:mine.length,best:bk?bk.p:null,bu:bk?mkUrl(bk):null,
             dmin:deps.length?Math.min(...deps):null,dmax:deps.length?Math.max(...deps):null,
             dmed:med(deps),mine};
    }
    const hit=p.doms.filter(d=>st[d].t10>0).length;
    let ds=[...p.doms].sort((a,b)=>st[b].t10-st[a].t10||st[b].t100-st[a].t100);
    if(dFilter==='hit') ds=ds.filter(d=>st[d].t10>0);
    if(dFilter==='miss') ds=ds.filter(d=>st[d].t10===0);
    h+=`<div class="gsec"><div class="ghead">
      <h3>${esc(p.name.split(' · ')[0])}${p.excl?' <span class="tag ex">не отдельный запуск</span>':''}</h3>
      <p class="gd">${esc(gDesc(p))}</p>
      <p class="gd2">Запущен ${esc(p.ltx)}. ${pl(n,'домен','домена','доменов')}, на этом замере им
        ${pl(Math.round(snap.age),'час','часа','часов')}.
        Замер ${esc(snap.lab)}${cl?' — у этой группы замеров меньше, показан самый свежий':''}.
        В десятку попал${hit===1?'':'и'} ${pl(hit,'домен','домена','доменов')} из ${n}${esc(tname)}.</p>
      </div><div class="cards">`;
    if(!ds.length) h+='<p class="note">Под этот фильтр здесь ничего не попало.</p>';
    for(const d of ds){
      const x=st[d], mine=x.mine;
      const top=mine.filter(r=>r.p<=10).sort((a,b)=>a.p-b.p);
      const brs=new Map(); for(const r of top) if(r.b) brs.set(r.b,(brs.get(r.b)||0)+1);
      const pgs=new Map(); for(const r of mine){let e=pgs.get(r.pg)||[0,0];e[0]++;if(r.p<=10)e[1]++;pgs.set(r.pg,e);}
      const dlt=PR?x.t10-PR.filter(r=>r.dom===d&&r.p<=10).length:null;
      const oid=p.id+'|'+d, isOpen=open1.has(oid), show=isOpen?top:top.slice(0,6);
      h+=`<div class="dcard${x.t10?'':' empty'}">
        <div class="dh"><span class="dn">${esc(d)}</span>
          ${x.t10?`<span class="pill p-t">в десятке ${x.t10}</span>`:'<span class="pill p-no">в десятке пусто</span>'}
          ${dlt!=null&&dlt!==0?`<span class="pill ${dlt>0?'p-up':'p-dn'}">${dlt>0?'+':''}${dlt} к прошлому замеру</span>`:''}
        </div>
        <div class="dstats">
          <div><span class="sv ${x.t10?'now':'mut'}">${x.t10}</span><span class="sl">ключей в десятке</span></div>
          <div><span class="sv">${x.t30}</span><span class="sl">в тридцатке</span></div>
          <div><span class="sv">${x.t100}</span><span class="sl">всего найдено</span></div>
          <div><span class="sv ${x.best?cls(x.best):'mut'}">${x.best??'—'}</span><span class="sl">лучшая позиция</span></div>
        </div>`;
      if(!mine.length){h+=`<p class="dnote">${TF?'По ключам этого спроса домен не нашёлся вообще.':'Домен не нашёлся ни по одному ключу.'}</p></div>`;continue;}
      h+=`<div class="drow"><span class="mk">бренды в десятке</span>
        <span class="dv">${brs.size?(()=>{const bs=[...brs.entries()].sort((a,b)=>b[1]-a[1]);
          return bs.slice(0,12).map(([b,c])=>`<span class="bch">${esc(b)} <b>${c}</b></span>`).join('')
            +(bs.length>12?`<span class="bch mut">и ещё ${bs.length-12}</span>`:'');})()
          :'<span class="mut">ни одного</span>'}</span></div>`;
      if(top.length) h+=`<div class="klist">${show.map(r=>
        `<div class="kr"><span class="kp ${cls(r.p)}">${r.p}</span><span class="kq2">${esc(r.q)}</span>
         <span class="kb">${esc(r.b||'—')}</span><span class="tr tr-${r.t||'нет'}">${r.t||'—'}</span>
         <span class="kpg">${esc(pgName(r.pg))}</span></div>`).join('')}
        ${top.length>6?`<button class="more" data-o="${esc(oid)}">${isOpen?'свернуть':'показать все '+top.length}</button>`:''}</div>`;
      h+=`<div class="drow"><span class="mk">страницы, которые нашлись</span><span class="dv">${
        [...pgs.entries()].sort((a,b)=>b[1][0]-a[1][0]).slice(0,6)
        .map(([k,e])=>`<span class="bch">${esc(pgName(k))} <b>${e[0]}</b>${e[1]?` <span class="now">из них в десятке ${e[1]}</span>`:''}</span>`).join('')}</span></div>`;
      h+=`<div class="drow"><span class="mk">глубина адреса</span><span class="dv">
        ${x.dmin==null?'<span class="mut">нет данных</span>':
          `от ${x.dmin} до ${x.dmax} повторов <code>/ru</code>, чаще всего ${x.dmed}`}
        ${x.bu?`<div class="uex" title="${esc(x.bu)}">${esc(x.bu)}</div>`:''}</span></div>`;
      h+='</div>';
    }
    h+='</div></div>';
  }
  return h+'</div>';
}

/* ── 2. ГРУППЫ ───────────────────────────────────────────── */
function tPools(){
  let h=`<div class="blk"><h2>Группы запуска рядом</h2>
  <p class="note">Одна строка — одна группа на выбранном замере. Последняя колонка важнее средней:
  если убрать самый сильный домен и результат обваливается, значит вся группа держится на одном домене
  и сравнивать её с другими нельзя.</p>
  <div class="tw"><table><thead><tr>
    <th class="l">Группа</th><th class="l">Чем отличается</th><th>Доменов</th>
    <th>Из них попали в десятку</th><th>Ключей в десятке</th><th>На один домен</th>
    <th>Без самого сильного домена</th><th>Всего найдено ключей</th></tr></thead><tbody>`;
  for(const p of D.pools){
    const {s}=snapOf(p), n=p.doms.length;
    h+=`<tr${p.excl?' class="tr-bad"':''}>
      <td class="l"><b>${esc(p.name.split(' · ')[0])}</b>${p.excl?' <span class="tag ex">не в счёт</span>':''}
        <div class="sm mut">запущен ${esc(p.ltx)} · замер ${esc(s.lab)}</div></td>
      <td class="l sm">${esc(gDesc(p))}</td>
      <td>${n}</td>
      <td>${s.tot.hit} <span class="mut sm">(${Math.round(100*s.tot.hit/n)}%)</span></td>
      <td class="${s.tot.t10?'now':'mut'}"><b>${s.tot.t10}</b></td>
      <td><b>${nf(s.tot.t10/n,1)}</b></td>
      <td class="${s.tot.nolead!=null&&s.tot.nolead<s.tot.t10/n*0.6?'bad':''}">${nf(s.tot.nolead,1)}</td>
      <td>${s.tot.t100}</td></tr>`;
  }
  h+='</tbody></table></div></div>';

  h+=`<div class="blk"><h2>Как менялось от замера к замеру</h2>
  <p class="note">Сколько ключей группы стояло в десятке на каждом замере и сколько часов домену было в этот момент.
  Видно главное: на первом замере группы стоят почти вровень, а расходятся только к третьему.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th>`;
  for(let i=0;i<D.nsnap;i++) h+=`<th>${['Первый','Второй','Третий'][i]} замер</th>`;
  h+='</tr></thead><tbody>';
  for(const p of D.pools){
    const {i:sel}=snapOf(p);
    h+=`<tr><td class="l">${esc(p.name.split(' · ')[0])}</td>`;
    for(let i=0;i<D.nsnap;i++){const s=p.snaps[i];
      h+=s?`<td${i===sel?' class="now"':''}><b>${s.tot.t10}</b> <span class="mut sm">в десятке</span>
        <div class="sm mut">${s.lab} · домену ${nf(s.age,0)} ч</div></td>`:'<td class="mut">замера не было</td>';}
    h+='</tr>';
  }
  h+='</tbody></table></div></div>';

  h+=`<div class="blk"><h2>Глубина адреса по группам</h2>
  <p class="note">Сколько раз <code>/ru</code> повторяется в адресе страницы, которая нашлась в поиске.
  У групп с ограничением потолок стоит на двадцати — по колонке «максимум» видно, упёрлись они в него или нет.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Ограничение</th>`;
  const B=[[0,0,'адрес чистый'],[1,5,'1–5'],[6,10,'6–10'],[11,15,'11–15'],[16,20,'16–20'],[21,40,'21–40'],[41,999,'41 и больше']];
  h+=B.map(b=>`<th>${b[2]}</th>`).join('')+'<th>Чаще всего</th><th>Максимум</th></tr></thead><tbody>';
  for(const p of D.pools){
    const {s}=snapOf(p), ds=s.rows.map(r=>r[3]).filter(x=>x>=0);
    h+=`<tr><td class="l">${esc(p.name.split(' · ')[0])}</td><td class="l sm">${p.cap==='потолок 20'?'до 20':'нет'}</td>`;
    for(const b of B){const c=ds.filter(x=>x>=b[0]&&x<=b[1]).length;
      h+=`<td class="${c?'':'mut'}">${c?c+'<div class="sm mut">'+Math.round(100*c/ds.length)+'%</div>':'·'}</td>`;}
    h+=`<td>${s.tot.dmed??'—'}</td><td class="now">${s.tot.dmax??'—'}</td></tr>`;
  }
  return h+'</tbody></table></div></div>';
}

/* ── 3. БРЕНДЫ ───────────────────────────────────────────── */
let bTier='';
function tBrands(){
  const rows=allRows().filter(r=>r.b);
  const agg=new Map();
  for(const r of rows){
    let e=agg.get(r.b); if(!e){e={b:r.b,t:r.t,v:r.v,t10:0,t30:0,t100:0,doms:new Set(),best:999};agg.set(r.b,e);}
    if(r.p<=10){e.t10++;e.doms.add(r.dom);} if(r.p<=30)e.t30++; e.t100++;
    if(r.p<e.best)e.best=r.p;
  }
  let list=[...agg.values()].filter(e=>!bTier||e.t===bTier).sort((a,b)=>b.t10-a.t10||b.t30-a.t30||b.v-a.v);
  const tt={};
  for(const e of agg.values()){const k=e.t||'—';tt[k]=tt[k]||{t10:0,t100:0,n:0,hit:0};
    tt[k].t10+=e.t10;tt[k].t100+=e.t100;tt[k].n++;if(e.t10)tt[k].hit++;}
  let h=`<div class="blk"><h2>По каким брендам мы стоим</h2>
  <p class="note">Считаются все группы последних запусков вместе, на выбранном замере.
  ВЧ — бренд, который ищут больше миллиона раз в месяц, СЧ — от семисот тысяч до миллиона, НЧ — реже.
  Деньги приносят в основном ВЧ и СЧ, поэтому смотреть надо на них, а не на общее число ключей.</p>
  <div class="tiles">`;
  for(const t of ['ВЧ','СЧ','НЧ']){const e=tt[t]||{t10:0,t100:0,n:0,hit:0};
    h+=`<div class="tile${t==='ВЧ'?' a':''}"><div class="k">${t} — всего ${pl(e.n,'бренд','бренда','брендов')}</div>
      <div class="v">${e.hit}</div><div class="c">из них есть хоть один ключ в десятке<br>ключей в десятке: ${e.t10}, найдено всего: ${e.t100}</div></div>`;}
  h+=`</div>
  <div class="brow"><span class="mk">показать</span>
    <select id="bt"><option value="">все бренды</option>${['ВЧ','СЧ','НЧ'].map(t=>`<option value="${t}"${bTier===t?' selected':''}>только ${t}</option>`).join('')}</select></div>
  <div class="tw"><table class="big"><thead><tr><th class="l">Бренд</th><th class="l">Спрос</th><th>Запросов в месяц</th>
    <th>Ключей в десятке</th><th>В тридцатке</th><th>Найдено всего</th><th>Лучшая позиция</th>
    <th class="l">На каких доменах стоит в десятке</th></tr></thead><tbody>`;
  for(const e of list){
    h+=`<tr${e.t10?'':' class="tr-bad"'}><td class="l"><b>${esc(e.b)}</b></td>
      <td class="l"><span class="tr tr-${e.t||'нет'}">${e.t||'—'}</span></td>
      <td>${kfmt(e.v)}</td>
      <td class="${e.t10?'now':'mut'}"><b>${e.t10}</b></td><td>${e.t30}</td><td>${e.t100}</td>
      <td class="${e.best<999?cls(e.best):'mut'}">${e.best<999?e.best:'—'}</td>
      <td class="l sm">${e.doms.size?[...e.doms].map(d=>`<span class="bch">${esc(d)}</span>`).join(''):'<span class="mut">нигде</span>'}</td></tr>`;}
  return h+'</tbody></table></div></div>';
}

/* ── 4. КЛЮЧИ ────────────────────────────────────────────── */
let kPool='',kTier='',kTop='10',kQ='';
function tKeys(){
  let rows=kPool?D.pools.filter(p=>p.id===kPool).flatMap(rowsOf):allRows();
  if(kTier) rows=rows.filter(r=>r.t===kTier);
  if(kTop!=='all') rows=rows.filter(r=>r.p<=+kTop);
  if(kQ){const s=kQ.toLowerCase();rows=rows.filter(r=>r.q.toLowerCase().includes(s)||(r.b||'').toLowerCase().includes(s)||r.dom.includes(s));}
  rows.sort((a,b)=>a.p-b.p||b.v-a.v);
  const shown=rows.slice(0,600);
  let h=`<div class="blk"><h2>Все ключи списком</h2>
  <p class="note">Один ключ на одном домене. Ищите по слову в ключе, по бренду или по домену.</p>
  <div class="brow">
    <select id="kp"><option value="">все группы</option>${D.pools.map(p=>`<option value="${p.id}"${kPool===p.id?' selected':''}>${esc(p.name.split(' · ')[0])}</option>`).join('')}</select>
    <select id="kt"><option value="">любой спрос</option>${['ВЧ','СЧ','НЧ'].map(t=>`<option value="${t}"${kTier===t?' selected':''}>только ${t}</option>`).join('')}</select>
    <select id="kn">${[['3','в тройке'],['10','в десятке'],['30','в тридцатке'],['all','всё, что нашлось']].map(([v,l])=>`<option value="${v}"${kTop===v?' selected':''}>${l}</option>`).join('')}</select>
    <input id="kq" placeholder="ключ, бренд или домен" value="${esc(kQ)}">
    <span class="bch">строк <b>${rows.length}</b>${rows.length>600?' <span class="mut">показаны первые 600</span>':''}</span>
  </div>
  <div class="tw"><table class="big"><thead><tr><th>Позиция</th><th class="l">Ключ</th><th class="l">Бренд</th>
    <th class="l">Спрос</th><th>Запросов в месяц</th><th class="l">Домен</th><th class="l">Группа</th>
    <th>Повторов /ru</th><th class="l">Какая страница</th></tr></thead><tbody>`;
  for(const r of shown)
    h+=`<tr><td class="${cls(r.p)}"><b>${r.p}</b></td><td class="l">${esc(r.q)}</td>
      <td class="l">${esc(r.b||'—')}</td><td class="l"><span class="tr tr-${r.t||'нет'}">${r.t||'—'}</span></td>
      <td>${kfmt(r.v)}</td><td class="l mono">${esc(r.dom)}</td>
      <td class="l sm">${esc(r.pool.name.split(' · ')[0])}</td>
      <td>${r.d??'—'}</td><td class="l sm">${esc(pgName(r.pg))}</td></tr>`;
  return h+'</tbody></table></div></div>';
}

/* ── рендер ──────────────────────────────────────────────── */
const TABS=[['doms','Домены',tDoms],['pools','Группы запуска',tPools],
            ['brands','Бренды',tBrands],['keys','Все ключи',tKeys]];
let TAB='doms';
function renderAll(){
  document.getElementById('main').innerHTML=TABS.find(t=>t[0]===TAB)[2]();
  const bind=(id,fn)=>{const e=document.getElementById(id);if(e)e.onchange=fn;};
  bind('df',e=>{dFilter=e.target.value;renderAll();});
  bind('dt',e=>{dTier=e.target.value;renderAll();});
  bind('bt',e=>{bTier=e.target.value;renderAll();});
  bind('kp',e=>{kPool=e.target.value;renderAll();});
  bind('kt',e=>{kTier=e.target.value;renderAll();});
  bind('kn',e=>{kTop=e.target.value;renderAll();});
  document.querySelectorAll('.more').forEach(b=>b.onclick=()=>{
    const o=b.dataset.o; open1.has(o)?open1.delete(o):open1.add(o);
    const y=window.scrollY; renderAll(); window.scrollTo(0,y);});
  const q=document.getElementById('kq');
  if(q) q.oninput=e=>{kQ=e.target.value;const pos=e.target.selectionStart;renderAll();
    const n=document.getElementById('kq');n.focus();n.setSelectionRange(pos,pos);};
}
document.getElementById('nav').innerHTML=TABS.map(([id,l])=>
  `<button data-t="${id}" aria-selected="${id===TAB}">${l}</button>`).join('');
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{
  TAB=b.dataset.t;
  document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===TAB));
  renderAll();window.scrollTo(0,0);});
buildSwitch();renderAll();

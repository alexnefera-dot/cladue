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
const sname=p=>p.name.replace(/ · 02\.09$/,'');

/* ── выбор съёма ─────────────────────────────────────────── */
const snapOf=p=>({s:p.snaps[0],cl:false,i:0});
const prevOf=()=>null;

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
  let h=`<div class="blk"><h2>Каждый из 67 доменов</h2>
  <p class="note">Домены сгруппированы по тому, каким запуском они ушли. Внутри карточки — что домен реально даёт:
  по каким брендам стоит в десятке, какими страницами и на какой глубине адреса.
  Все числа — с замера 3 сентября 12:03, доменам на нём около двадцати часов.</p>
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
      <h3>${esc(sname(p))}${p.excl?' <span class="tag ex">не отдельный запуск</span>':''}</h3>
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
          ${snap.dom[d].reg?`<span class="pill p-money">${pl(snap.dom[d].reg,'регистрация','регистрации','регистраций')}${snap.dom[d].dep?', депозит':''}</span>`:''}
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
  let h=`<div class="blk"><h2>Девять веток рядом</h2>
  <p class="note">Одна строка — одна ветка запуска 2 сентября. Последняя колонка важнее средней:
  если убрать самый сильный домен и результат обваливается, значит вся группа держится на одном домене
  и сравнивать её с другими нельзя.</p>
  <div class="tw"><table><thead><tr>
    <th class="l">Группа</th><th class="l">Чем отличается</th><th>Доменов</th>
    <th>Из них попали в десятку</th><th>Ключей в десятке</th><th>На один домен</th>
    <th>Без самого сильного домена</th><th>Всего найдено ключей</th>
    <th>Регистраций</th><th>Доменов с деньгами</th></tr></thead><tbody>`;
  for(const p of D.pools){
    const {s}=snapOf(p), n=p.doms.length;
    h+=`<tr${p.excl?' class="tr-bad"':''}>
      <td class="l"><b>${esc(sname(p))}</b>${p.excl?' <span class="tag ex">не в счёт</span>':''}
        <div class="sm mut">запущен ${esc(p.ltx)} · замер ${esc(s.lab)}</div></td>
      <td class="l sm">${esc(gDesc(p))}</td>
      <td>${n}</td>
      <td>${s.tot.hit} <span class="mut sm">(${Math.round(100*s.tot.hit/n)}%)</span></td>
      <td class="${s.tot.t10?'now':'mut'}"><b>${s.tot.t10}</b></td>
      <td><b>${nf(s.tot.t10/n,1)}</b></td>
      <td class="${s.tot.nolead!=null&&s.tot.nolead<s.tot.t10/n*0.6?'bad':''}">${nf(s.tot.nolead,1)}</td>
      <td>${s.tot.t100}</td>
      <td class="${s.tot.reg?'good':'mut'}"><b>${s.tot.reg||0}</b>${s.tot.dep?`<div class="sm good">депозитов ${s.tot.dep}</div>`:''}</td>
      <td class="${s.tot.whit?'good':'mut'}">${s.tot.whit||0} <span class="sm mut">из ${n}</span></td></tr>`;
  }
  h+='</tbody></table></div></div>';

  h+=`<div class="blk"><h2>Деньги по веткам</h2>
  <p class="note">Домен зарабатывает около шести суток, и три четверти регистраций приходят в первые
  двое. Этим доменам двадцать часов — окно закрыто примерно на восемнадцать процентов, поэтому
  разница в одну-две регистрации между ветками пока ничего не значит.</p>
  <div class="tw"><table><thead><tr><th class="l">Ветка</th><th>Доменов</th><th>Регистраций</th>
    <th>Депозитов</th><th>Доменов с деньгами</th><th>Ключей в десятке на домен</th></tr></thead><tbody>`;
  for(const p of D.pools){const s2=p.snaps[0],n=p.doms.length;
    h+=`<tr${s2.tot.reg?'':' class="tr-bad"'}><td class="l">${esc(p.name)}</td><td>${n}</td>
      <td class="${s2.tot.reg?'good':'mut'}"><b>${s2.tot.reg||0}</b></td>
      <td class="${s2.tot.dep?'good':'mut'}">${s2.tot.dep||'·'}</td>
      <td>${s2.tot.whit||0} <span class="sm mut">из ${n}</span></td>
      <td>${nf(s2.tot.t10/n,2)}</td></tr>`;}
  h+='</tbody></table></div></div>';

  h+=`<div class="blk"><h2>Глубина адреса по группам</h2>
  <p class="note">Сколько раз <code>/ru</code> повторяется в адресе страницы, которая нашлась в поиске.
  У групп с ограничением потолок стоит на двадцати — по колонке «максимум» видно, упёрлись они в него или нет.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Ограничение</th>`;
  const B=[[0,0,'адрес чистый'],[1,5,'1–5'],[6,10,'6–10'],[11,15,'11–15'],[16,20,'16–20'],[21,40,'21–40'],[41,999,'41 и больше']];
  h+=B.map(b=>`<th>${b[2]}</th>`).join('')+'<th>Чаще всего</th><th>Максимум</th></tr></thead><tbody>';
  for(const p of D.pools){
    const {s}=snapOf(p), ds=s.rows.map(r=>r[3]).filter(x=>x>=0);
    h+=`<tr><td class="l">${esc(sname(p))}</td><td class="l sm">${p.cap==='потолок 20'?'до 20':'нет'}</td>`;
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
  <p class="note">Считаются все девять веток вместе.
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
    <select id="kp"><option value="">все группы</option>${D.pools.map(p=>`<option value="${p.id}"${kPool===p.id?' selected':''}>${esc(sname(p))}</option>`).join('')}</select>
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
      <td class="l sm">${esc(sname(r.pool))}</td>
      <td>${r.d??'—'}</td><td class="l sm">${esc(pgName(r.pg))}</td></tr>`;
  return h+'</tbody></table></div></div>';
}


/* ── 5. СРАВНЕНИЯ ────────────────────────────────────────── */
const lastOf=id=>{const p=D.pools.find(x=>x.id===id);return p?{p,s:p.snaps[p.snaps.length-1]}:null;};
function armStat(sel,tf){
  let n=0,t10=[],t100=0,reg=0;
  for(const [id,zone] of sel){
    const o=lastOf(id); if(!o) continue;
    const doms=o.p.doms.filter(d=>!zone||d.endsWith(zone));
    const idx=new Map(o.p.doms.map((d,i)=>[d,i]));
    for(const d of doms){
      const rows=o.s.rows.filter(r=>r[1]===idx.get(d)&&(!tf||tf.includes(QD[r[0]][2])));
      n++; t10.push(rows.filter(r=>r[2]<=10).length); t100+=rows.length;
      reg+=o.s.dom[d].reg||0;
    }
  }
  const sum=t10.reduce((a,b)=>a+b,0);
  return {n,t10:sum,per:n?sum/n:0,hit:t10.filter(x=>x>0).length,t100,reg,
          med:n?[...t10].sort((a,b)=>a-b)[Math.floor(n/2)]:0};
}
const CUTS=[
 {g:'Даты в тексте',
  note:'Все четыре среза на возрасте около двадцати часов. Первый и второй чистые полностью: совпадают семейство контента, зона, число страниц и час запуска — различаются только даты.',
  rows:[
   ['7 страниц · NEW50 · .team', 'чисто', [['n1_7nd',null]], [['n1_7wd',null]]],
   ['12 страниц · NEW50_2 · .lol', 'чисто', [['n2_12nd','.lol']], [['n2_12wd','.lol']]],
   ['12 страниц · NEW50_2 · .team', 'перекос по размеру', [['n2_12nd','.team']], [['n2_12wd','.team']]],
   ['7 страниц · .team · семейства разные', 'разное семейство', [['n1_7nd',null]], [['n2_7wd',null]]],
  ], a:'Без дат', b:'С датами'},
 {g:'Число страниц',
  note:'Оба среза чистые: совпадает семейство, зона, даты и час — различается только число страниц.',
  rows:[
   ['NEW50_2 · с датами · .team','чисто',[['n2_12wd','.team']],[['n2_7wd',null]]],
   ['NEW50 · с датами · .team','чисто',[['n1_12wd',null]],[['n1_7wd',null]]],
  ], a:'12 страниц', b:'7 страниц'},
 {g:'Зона домена',
  note:'Наборы разложены три на три внутри одной группы — это чистая пара. Двенадцатистраничная ветка даёт обратный результат, и это главное наблюдение дня по зонам.',
  rows:[
   ['Наборы 294303 (3 на 3)','чисто',[['nb294303','.team']],[['nb294303','.lol']]],
   ['Наборы 274283 (3 на 3)','чисто',[['nb274283','.team']],[['nb274283','.lol']]],
   ['Наборы вместе (6 на 6)','чисто',[['nb294303','.team'],['nb274283','.team']],[['nb294303','.lol'],['nb274283','.lol']]],
   ['12 страниц с датами NEW50_2','перекос 14 против 3',[['n2_12wd','.team']],[['n2_12wd','.lol']]],
  ], a:'.team', b:'.lol'},
 {g:'День запуска',
  note:'Один и тот же контент, запущенный с разницей в сутки. Обе половинки сравниваются на возрасте около двадцати часов, только домены .team, чтобы зона не мешала.',
  rows:[
   ['12 страниц с датами NEW50','чисто',[['p12wt','.team']],[['n1_12wd',null]]],
   ['7 страниц с датами NEW50','чисто',[['p7wt','.team']],[['n1_7wd',null]]],
  ], a:'Запуск 01.09', b:'Запуск 02.09'},
];
function tCuts(){
  let h=`<div class="blk"><h2>Что с чем сравнивали</h2>
  <p class="note">Все девять веток запущены в один час и сняты одним замером, поэтому они в одном возрасте
  и их можно ставить рядом без оговорок.
  Метка «чисто» означает, что у двух сторон совпадает всё, кроме проверяемого признака.
  «Перекос» — что сторон сильно разного размера и величине разницы верить нельзя, только знаку.</p>`;
  for(const c of CUTS){
    h+=`<h3 class="vt">${esc(c.g)}</h3><p class="note">${esc(c.note)}</p>
    <div class="tw"><table><thead><tr><th class="l">Срез</th><th class="l">Качество</th>
      <th colspan="3">${esc(c.a)}</th><th colspan="3">${esc(c.b)}</th><th class="l">Кто впереди</th></tr>
      <tr><th></th><th></th><th>дом.</th><th>в десятке на домен</th><th>зашло</th>
      <th>дом.</th><th>в десятке на домен</th><th>зашло</th><th></th></tr></thead><tbody>`;
    for(const [nm,q,sa,sb] of c.rows){
      const A=armStat(sa,null),B=armStat(sb,null);
      const w=A.per>B.per?c.a:B.per>A.per?c.b:'ничья';
      const k=A.per&&B.per?(Math.max(A.per,B.per)/Math.min(A.per,B.per)):null;
      h+=`<tr><td class="l">${esc(nm)}</td>
        <td class="l"><span class="tag${q==='чисто'?' ok':''}">${esc(q)}</span></td>
        <td>${A.n}</td><td class="${A.per>B.per?'now':''}"><b>${nf(A.per,2)}</b></td><td class="sm">${A.hit}/${A.n}</td>
        <td>${B.n}</td><td class="${B.per>A.per?'now':''}"><b>${nf(B.per,2)}</b></td><td class="sm">${B.hit}/${B.n}</td>
        <td class="l"><b>${esc(w)}</b>${k&&k>1.15?` <span class="mut sm">в ${nf(k,1)} раза</span>`:''}</td></tr>`;
    }
    h+='</tbody></table></div>';
    // тот же срез по ВЧ/СЧ
    h+=`<div class="tw" style="margin-top:8px"><table><thead><tr><th class="l">Тот же срез, только ВЧ и СЧ ключи</th>
      <th>${esc(c.a)}</th><th>зашло</th><th>${esc(c.b)}</th><th>зашло</th><th class="l">Кто впереди</th></tr></thead><tbody>`;
    for(const [nm,q,sa,sb] of c.rows){
      const A=armStat(sa,['ВЧ','СЧ']),B=armStat(sb,['ВЧ','СЧ']);
      const w=A.per>B.per?c.a:B.per>A.per?c.b:'ничья';
      h+=`<tr><td class="l sm">${esc(nm)}</td>
        <td class="${A.per>B.per?'now':''}">${nf(A.per,2)}</td><td class="sm">${A.hit}/${A.n}</td>
        <td class="${B.per>A.per?'now':''}">${nf(B.per,2)}</td><td class="sm">${B.hit}/${B.n}</td>
        <td class="l sm">${esc(w)}</td></tr>`;
    }
    h+='</tbody></table></div>';
  }
  h+=`<div class="blk" style="margin-top:26px"><h2>День запуска: один контент, две партии</h2>
  <p class="note">Две ветки 2 сентября — это вторые половины групп, чьи первые половины ушли в работу
  1 сентября. Обе половины сравниваются на возрасте около двадцати часов, только домены <code>.team</code>,
  чтобы зона не мешала. Если бы день запуска влиял, половины разошлись бы.</p>
  <div class="tw"><table><thead><tr><th class="l">Контент</th>
    <th>Запуск 01.09</th><th>зашло</th><th>Запуск 02.09</th><th>зашло</th><th class="l">Вывод</th></tr></thead><tbody>`;
  for(const c of D.dayCut)
    h+=`<tr><td class="l">${esc(c.name)}</td>
      <td>${nf(c.a,2)}</td><td class="sm">${c.ah}/${c.an}</td>
      <td>${nf(c.b,2)}</td><td class="sm">${c.bh}/${c.bn}</td>
      <td class="l sm">${esc(c.v)}</td></tr>`;
  h+=`</tbody></table></div>
  <p class="verd">Двенадцатистраничная пара совпала до цифры, семистраничная разошлась по всем ключам,
  но в обратную сторону по дорогим. Систематического эффекта дня запуска нет — партии разных суток
  можно складывать в одно сравнение, если выравнивать их по возрасту домена.</p></div>`;

  h+=`<div class="blk"><h2>Деньги пока ничего не говорят</h2>
  <p class="note">Четыре регистрации на 67 доменов на возрасте двадцати часов. Разница между ветками
  в одну-две регистрации — это шум, а не сигнал: окно закрыто примерно на восемнадцать процентов.</p>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Ветка</th>
    <th class="l">Бренд</th><th>Ключей в десятке</th><th>Лучшая позиция</th></tr></thead><tbody>`;
  for(const p of D.pools){const s2=p.snaps[0];
    for(const d of p.doms){const x=s2.dom[d]; if(!x.reg) continue;
      h+=`<tr><td class="l mono"><b>${esc(d)}</b></td><td class="l sm">${esc(p.name)}</td>
        <td class="l">${(x.brreg||[]).map(([b,n])=>`<span class="bch">${esc(b)}${n>1?' ×'+n:''}</span>`).join('')}</td>
        <td class="${x.t10?'now':'mut'}">${x.t10}</td><td class="${x.best?cls(x.best):'mut'}">${x.best??'—'}</td></tr>`;}}
  h+=`</tbody></table></div>
  <p class="verd">Лучшая по позициям ветка (12 страниц без дат, 11,83 ключа в десятке на домен) дала
  одну регистрацию, а середняк (7 страниц с датами, 5,33) — две. На четырёх событиях это ничего
  не доказывает ни в одну сторону: смотреть надо будет 8 сентября, когда окно закроется.</p></div></div>`;
  return h;
}

/* ── рендер ──────────────────────────────────────────────── */
const TABS=[['doms','Домены',tDoms],['pools','Группы запуска',tPools],['cuts','Сравнения',tCuts],
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
renderAll();

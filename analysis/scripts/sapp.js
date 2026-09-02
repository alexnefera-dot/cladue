const D=window.DATA;
const QD=D.qd, PD=D.pd;
const ACT=D.pools.filter(p=>!p.excl);
const nf=(x,d=0)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const kfmt=v=>!v?'—':v>=1e6?nf(v/1e6,1)+' млн':v>=1e3?Math.round(v/1e3)+' тыс':v;
const cls=p=>p<=3?'good':p<=10?'now':p<=30?'':'mut';

/* ── выбор съёма ─────────────────────────────────────────── */
let SLOT='last';
const snapOf=p=>{
  if(SLOT==='last') return {s:p.snaps[p.snaps.length-1],cl:false,i:p.snaps.length-1};
  const i=Math.min(SLOT,p.snaps.length-1);
  return {s:p.snaps[i],cl:i!==SLOT,i};
};
const prevOf=p=>{const {i}=snapOf(p); return i>0?p.snaps[i-1]:null;};

function buildSwitch(){
  const el=document.getElementById('sw');
  const opts=[];
  for(let i=0;i<D.nsnap;i++) opts.push([i, i===0?'1-й съём':(i+1)+'-й съём']);
  opts.push(['last','Последний']);
  el.innerHTML=opts.map(([v,l])=>
    `<button data-v="${v}" aria-pressed="${String(v)===String(SLOT)}">${l}</button>`).join('');
  el.querySelectorAll('button').forEach(b=>b.onclick=()=>{
    SLOT=b.dataset.v==='last'?'last':+b.dataset.v;
    el.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.v)===String(SLOT)));
    renderAll();
  });
}
function snapLine(){
  return ACT.map(p=>{const {s,cl}=snapOf(p);
    return `<span class="bch"${cl?' title="у пула меньше съёмов — показан последний"':''}>${esc(p.name.split(' · ')[0])}: <b>${s.lab}</b> <span class="mut">+${nf(s.age,1)}ч</span>${cl?' <span class="mut">·посл.</span>':''}</span>`;
  }).join('');
}

/* ── строки ключей выбранного съёма ───────────────────────── */
function keyRows(){
  const out=[];
  for(const p of D.pools){
    const {s}=snapOf(p);
    for(const r of s.rows){
      const m=QD[r[0]];
      out.push({q:m[0],b:m[1],t:m[2],v:m[3],dom:p.doms[r[1]],pool:p,p:r[2],
                d:r[3]<0?null:r[3],pg:PD[r[4]]});
    }
  }
  return out;
}

/* ── 1. ПУЛЫ ─────────────────────────────────────────────── */
function tPools(){
  let h=`<div class="blk"><h2>Пулы последних запусков</h2>
  <p class="note">Каждая строка — один пул на выбранном съёме. «Заход» — доля доменов пула,
  у которых хотя бы один ключ в ТОП-10. «Без лидера» — среднее Т10 на домен без самого сильного домена:
  если оно сильно ниже среднего, весь пул держится на одном домене и вывод по нему делать нельзя.</p>
  <div class="brow"><span class="mk">съёмы</span>${snapLine()}</div>
  <div class="tw"><table class="big"><thead><tr>
  <th class="l">Пул</th><th class="l">Зона</th><th>Стр.</th><th class="l">Даты</th>
  <th class="l">Запуск</th><th>Возраст</th><th>Дом.</th>
  <th>Т3</th><th>Т10</th><th>Т30</th><th>Сотня</th>
  <th>Т10/дом</th><th>Медиана</th><th>Без лидера</th><th>Заход</th>
  <th>Влож. мед</th><th>макс</th></tr></thead><tbody>`;
  for(const p of D.pools){
    const {s,cl}=snapOf(p), pr=prevOf(p), n=p.doms.length;
    const dlt=pr?s.tot.t10-pr.tot.t10:null;
    h+=`<tr${p.excl?' class="tr-bad"':''}><td class="l"><b>${esc(p.name)}</b>${p.excl?' <span class="tag ex">не в итогах</span>':''}
      <div class="sm mut">${esc(p.ids)} · ${esc(p.plat)} · ${esc(p.cap)}</div></td>
      <td class="l mono">${esc(p.zone)}</td><td>${esc(p.pages)}</td><td class="l">${esc(p.dates)}</td>
      <td class="l sm">${esc(p.ltx)}</td>
      <td>${nf(s.age,1)}ч${cl?'<div class="sm mut">посл. съём</div>':''}</td><td>${n}</td>
      <td>${s.tot.t3}</td><td class="now">${s.tot.t10}${dlt!=null?` <span class="sm ${dlt>0?'good':dlt<0?'bad':'mut'}">${dlt>0?'+':''}${dlt}</span>`:''}</td>
      <td>${s.tot.t30}</td><td>${s.tot.t100}</td>
      <td><b>${nf(s.tot.t10/n,2)}</b></td><td>${nf(s.tot.med,1)}</td>
      <td>${nf(s.tot.nolead,2)}</td>
      <td>${Math.round(100*s.tot.hit/n)}%<div class="sm mut">${s.tot.hit}/${n}</div></td>
      <td>${s.tot.dmed??'—'}</td><td>${s.tot.dmax??'—'}</td></tr>`;
  }
  h+='</tbody></table></div></div>';

  h+='<div class="blk"><h2>Динамика по съёмам</h2><p class="note">Т10 всего пула на каждом съёме, с возрастом домена в часах. Столбец выбранного съёма подсвечен.</p><div class="tw"><table><thead><tr><th class="l">Пул</th>';
  for(let i=0;i<D.nsnap;i++) h+=`<th>${i+1}-й съём</th>`;
  h+='</tr></thead><tbody>';
  for(const p of D.pools){
    const {i:sel}=snapOf(p);
    h+=`<tr><td class="l">${esc(p.name)}</td>`;
    for(let i=0;i<D.nsnap;i++){
      const s=p.snaps[i];
      h+=s?`<td${i===sel?' class="now"':''}><b>${s.tot.t10}</b> <span class="mut sm">Т10</span>
        <div class="sm mut">${s.lab} · +${nf(s.age,1)}ч · сотня ${s.tot.t100}</div></td>`
        :'<td class="mut">—</td>';
    }
    h+='</tr>';
  }
  h+='</tbody></table></div></div>';

  h+='<div class="blk"><h2>Пулы подробно</h2><div class="grid2">';
  for(const p of D.pools){
    const {s}=snapOf(p), n=p.doms.length;
    h+=`<div class="gcard"><div class="gh"><h3>${esc(p.name)}</h3>
      <div class="gt"><span class="tag">${esc(p.cap)}</span>${p.excl?'<span class="tag ex">не в итогах</span>':''}</div></div>
      <div class="meta">
        <div><span class="mk">Запуск</span><span class="mv">${esc(p.ltx)}</span></div>
        <div><span class="mk">Съём</span><span class="mv">${s.lab} · +${nf(s.age,1)}ч</span></div>
        <div><span class="mk">Доменов</span><span class="mv">${n}</span></div>
        <div><span class="mk">Страниц</span><span class="mv">${esc(p.pages)}</span></div>
        <div><span class="mk">Даты</span><span class="mv">${esc(p.dates)}</span></div>
        <div><span class="mk">Т10 / дом</span><span class="mv">${nf(s.tot.t10/n,2)}</span></div>
      </div>
      <p class="note">${esc(p.note)}</p>
      <div class="brow"><span class="mk">бренды в Т10</span>${
        s.br.filter(b=>b[1]>0).slice(0,10).map(b=>`<span class="bch">${esc(b[0])} <b>${b[1]}</b></span>`).join('')
        ||'<span class="bch mut">ни одного</span>'}</div>
      <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т3</th><th>Т10</th><th>Т30</th><th>Сотня</th>
        <th>Лучш.</th><th>Влож.</th><th>Стр.</th></tr></thead><tbody>`;
    const ds=[...p.doms].sort((a,b)=>s.dom[b].t10-s.dom[a].t10||s.dom[b].t100-s.dom[a].t100);
    for(const d of ds){const x=s.dom[d];
      h+=`<tr${x.t100===0?' class="tr-bad"':''}><td class="l mono">${esc(d)}</td>
        <td>${x.t3||'<span class="mut">0</span>'}</td>
        <td class="${x.t10?'now':'mut'}">${x.t10}</td><td>${x.t30}</td><td>${x.t100}</td>
        <td class="${x.best?cls(x.best):'mut'}">${x.best??'—'}</td>
        <td class="sm">${x.dmin==null?'—':x.dmin+'–'+x.dmax+' <span class="mut">мед '+x.dmed+'</span>'}</td>
        <td>${x.npg||'—'}</td></tr>`;}
    h+='</tbody></table></div></div>';
  }
  return h+'</div></div>';
}

/* ── 2. ДОМЕНЫ ───────────────────────────────────────────── */
let dSort='t10', dPool='';
function tDoms(){
  let rows=[];
  for(const p of D.pools){
    if(p.excl&&dPool!==p.id) continue;
    if(dPool&&dPool!==p.id) continue;
    const {s}=snapOf(p), pr=prevOf(p);
    for(const d of p.doms){const x=s.dom[d];
      rows.push({d,p,x,dlt:pr?x.t10-pr.dom[d].t10:null,lab:s.lab,age:s.age,
        br:s.br.filter(b=>b[1]>0)});}
  }
  const K={t10:r=>-r.x.t10,t100:r=>-r.x.t100,best:r=>r.x.best??999,dom:r=>r.d,dep:r=>-(r.x.dmax??-1)};
  rows.sort((a,b)=>{const f=K[dSort];const x=f(a),y=f(b);return x<y?-1:x>y?1:0;});
  let h=`<div class="blk"><h2>Домены на выбранном съёме</h2>
  <p class="note">Все домены последних запусков. «Влож.» — разброс вложенности <code>/ru</code> у ранжирующихся URL этого домена: минимум–максимум и медиана. «Стр.» — сколько разных страниц домена вообще получили позиции.</p>
  <div class="brow"><span class="mk">пул</span>
    <select id="dp"><option value="">все</option>${D.pools.map(p=>`<option value="${p.id}"${dPool===p.id?' selected':''}>${esc(p.name)}</option>`).join('')}</select>
    <span class="mk">сортировка</span>
    <select id="ds">${[['t10','по Т10'],['t100','по сотне'],['best','по лучшей позиции'],['dep','по вложенности'],['dom','по имени']].map(([v,l])=>`<option value="${v}"${dSort===v?' selected':''}>${l}</option>`).join('')}</select>
  </div>
  <div class="tw"><table class="big"><thead><tr><th class="l">Домен</th><th class="l">Пул</th><th class="l">Съём</th>
  <th>Возр.</th><th>Т3</th><th>Т10</th><th>Δ</th><th>Т30</th><th>Сотня</th><th>Лучш.</th>
  <th class="l">Вложенность</th><th>Стр.</th><th>Подд.</th></tr></thead><tbody>`;
  for(const r of rows){const x=r.x;
    h+=`<tr${x.t100===0?' class="tr-bad"':''}><td class="l mono"><b>${esc(r.d)}</b></td>
    <td class="l sm">${esc(r.p.name.split(' · ')[0])}<div class="mut">${esc(r.p.zone)} · ${esc(r.p.pages)} стр · ${esc(r.p.dates)}</div></td>
    <td class="l sm mono">${r.lab}</td><td>${nf(r.age,1)}ч</td>
    <td>${x.t3||'<span class="mut">0</span>'}</td><td class="${x.t10?'now':'mut'}"><b>${x.t10}</b></td>
    <td class="sm ${r.dlt>0?'good':r.dlt<0?'bad':'mut'}">${r.dlt==null?'—':(r.dlt>0?'+':'')+r.dlt}</td>
    <td>${x.t30}</td><td>${x.t100}</td><td class="${x.best?cls(x.best):'mut'}">${x.best??'—'}</td>
    <td class="l sm">${x.dmin==null?'—':`${x.dmin} – ${x.dmax} <span class="mut">мед ${x.dmed}</span>`}</td>
    <td>${x.npg||'—'}</td><td>${x.nsub||'—'}</td></tr>`;}
  h+='</tbody></table></div></div>';
  return h;
}

/* ── 3. БРЕНДЫ ───────────────────────────────────────────── */
let bTier='';
function tBrands(){
  const rows=keyRows().filter(r=>r.b&&!r.pool.excl);
  const agg=new Map();
  for(const r of rows){
    let e=agg.get(r.b); if(!e){e={b:r.b,t:r.t,v:r.v,t3:0,t10:0,t30:0,t100:0,doms:new Set(),pools:new Map()};agg.set(r.b,e);}
    if(r.p<=3)e.t3++; if(r.p<=10){e.t10++;e.doms.add(r.dom);e.pools.set(r.pool.id,(e.pools.get(r.pool.id)||0)+1);}
    if(r.p<=30)e.t30++; e.t100++;
  }
  let list=[...agg.values()].filter(e=>!bTier||e.t===bTier).sort((a,b)=>b.t10-a.t10||b.t30-a.t30||b.v-a.v);
  const tt={};
  for(const e of agg.values()){const k=e.t||'—';tt[k]=tt[k]||{t10:0,t100:0,n:0};tt[k].t10+=e.t10;tt[k].t100+=e.t100;tt[k].n++;}
  let h=`<div class="blk"><h2>Бренды на выбранном съёме</h2>
  <p class="note">Сколько ключей каждого бренда стоят в ТОП-10 / ТОП-30 / сотне по всем пулам последних запусков (пул apex/banda исключён — там другое ядро). Тир: ВЧ ≥ 1 млн кликов/мес, СЧ 700 тыс – 1 млн, остальное НЧ.</p>
  <div class="tiles">`;
  for(const t of ['ВЧ','СЧ','НЧ']){const e=tt[t]||{t10:0,t100:0,n:0};
    h+=`<div class="tile${t==='ВЧ'?' a':''}"><div class="k">${t} — брендов ${e.n}</div>
      <div class="v">${e.t10}</div><div class="c">ключей в Т10 · сотня ${e.t100}</div></div>`;}
  h+=`</div>
  <div class="brow"><span class="mk">тир</span>
    <select id="bt"><option value="">все</option>${['ВЧ','СЧ','НЧ'].map(t=>`<option value="${t}"${bTier===t?' selected':''}>${t}</option>`).join('')}</select></div>
  <div class="tw"><table class="big"><thead><tr><th class="l">Бренд</th><th class="l">Тир</th><th>Частотность</th>
  <th>Т3</th><th>Т10</th><th>Т30</th><th>Сотня</th><th>Доменов в Т10</th><th class="l">Пулы, давшие Т10</th></tr></thead><tbody>`;
  for(const e of list){
    h+=`<tr><td class="l"><b>${esc(e.b)}</b></td><td class="l"><span class="tr tr-${e.t||'нет'}">${e.t||'—'}</span></td>
    <td>${kfmt(e.v)}</td><td>${e.t3||'<span class="mut">0</span>'}</td>
    <td class="${e.t10?'now':'mut'}"><b>${e.t10}</b></td><td>${e.t30}</td><td>${e.t100}</td>
    <td>${e.doms.size||'<span class="mut">0</span>'}</td>
    <td class="l sm">${[...e.pools.entries()].sort((a,b)=>b[1]-a[1]).map(([id,n])=>{
      const p=D.pools.find(x=>x.id===id);return `<span class="bch">${esc(p.name.split(' · ')[0])} <b>${n}</b></span>`;}).join('')||'<span class="mut">—</span>'}</td></tr>`;}
  h+='</tbody></table></div></div>';

  const top=list.slice(0,25);
  h+=`<div class="blk"><h2>Бренд × пул — ключи в ТОП-10</h2>
  <p class="note">Топ-25 брендов по Т10. Видно, добирается ли бренд одним пулом или всеми сразу.</p>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th class="l">Тир</th>${
    ACT.map(p=>`<th>${esc(p.name.split(' · ')[0])}</th>`).join('')}<th>Всего</th></tr></thead><tbody>`;
  for(const e of top){
    h+=`<tr><td class="l">${esc(e.b)}</td><td class="l"><span class="tr tr-${e.t||'нет'}">${e.t||'—'}</span></td>`;
    for(const p of ACT){const n=e.pools.get(p.id)||0;h+=`<td class="${n?'now':'mut'}">${n||'·'}</td>`;}
    h+=`<td><b>${e.t10}</b></td></tr>`;}
  return h+'</tbody></table></div></div>';
}

/* ── 4. КЛЮЧИ ────────────────────────────────────────────── */
let kPool='',kTier='',kTop='10',kQ='';
function tKeys(){
  let rows=keyRows();
  if(kPool) rows=rows.filter(r=>r.pool.id===kPool); else rows=rows.filter(r=>!r.pool.excl);
  if(kTier) rows=rows.filter(r=>r.t===kTier);
  if(kTop!=='all') rows=rows.filter(r=>r.p<=+kTop);
  if(kQ){const s=kQ.toLowerCase();rows=rows.filter(r=>r.q.toLowerCase().includes(s)||(r.b||'').toLowerCase().includes(s)||r.dom.includes(s));}
  rows.sort((a,b)=>a.p-b.p||b.v-a.v);
  const shown=rows.slice(0,700);
  let h=`<div class="blk"><h2>Ключи на выбранном съёме</h2>
  <p class="note">Каждая строка — один ключ на одном домене. «Влож.» — сколько раз <code>/ru</code> повторяется в ранжирующемся URL, «Страница» — что именно ранжируется без учёта <code>/ru</code>.</p>
  <div class="brow">
    <span class="mk">пул</span><select id="kp"><option value="">все (без apex)</option>${D.pools.map(p=>`<option value="${p.id}"${kPool===p.id?' selected':''}>${esc(p.name)}</option>`).join('')}</select>
    <span class="mk">тир</span><select id="kt"><option value="">все</option>${['ВЧ','СЧ','НЧ'].map(t=>`<option value="${t}"${kTier===t?' selected':''}>${t}</option>`).join('')}</select>
    <span class="mk">срез</span><select id="kn">${[['3','ТОП-3'],['10','ТОП-10'],['30','ТОП-30'],['all','вся сотня']].map(([v,l])=>`<option value="${v}"${kTop===v?' selected':''}>${l}</option>`).join('')}</select>
    <input id="kq" placeholder="ключ, бренд или домен" value="${esc(kQ)}">
    <span class="bch">строк <b>${rows.length}</b>${rows.length>700?' <span class="mut">показано 700</span>':''}</span>
  </div>
  <div class="tw"><table class="big"><thead><tr><th>Поз.</th><th class="l">Ключ</th><th class="l">Бренд</th><th class="l">Тир</th>
  <th>Частотн.</th><th class="l">Домен</th><th class="l">Пул</th><th>Влож.</th><th class="l">Страница</th></tr></thead><tbody>`;
  for(const r of shown){
    h+=`<tr><td class="${cls(r.p)}"><b>${r.p}</b></td><td class="l">${esc(r.q)}</td>
    <td class="l">${esc(r.b||'—')}</td><td class="l"><span class="tr tr-${r.t||'нет'}">${r.t||'—'}</span></td>
    <td>${kfmt(r.v)}</td><td class="l mono">${esc(r.dom)}</td>
    <td class="l sm">${esc(r.pool.name.split(' · ')[0])}</td>
    <td>${r.d??'—'}</td><td class="l mono sm"><span class="url" title="${esc(r.pg)}">${esc(r.pg)}</span></td></tr>`;}
  return h+'</tbody></table></div></div>';
}

/* ── 5. ВЛОЖЕННОСТЬ И СТРАНИЦЫ ───────────────────────────── */
function tNest(){
  const B=[[0,0],[1,5],[6,10],[11,15],[16,20],[21,40],[41,999]];
  const lbl=b=>b[0]===0?'0 (чистый)':b[1]===999?'41+':`${b[0]}–${b[1]}`;
  let h=`<div class="blk"><h2>Вложенность на выбранном съёме</h2>
  <p class="note">Распределение ранжирующихся URL по глубине <code>/ru</code>. У пулов 01.09 стоит потолок 20 — видно, упёрлись они в него или нет.</p>
  <div class="tw"><table><thead><tr><th class="l">Пул</th><th class="l">Съём</th>${B.map(b=>`<th>${lbl(b)}</th>`).join('')}<th>Медиана</th><th>Макс</th></tr></thead><tbody>`;
  for(const p of D.pools){
    const {s}=snapOf(p);
    const ds=s.rows.map(r=>r[3]).filter(x=>x>=0);
    h+=`<tr><td class="l">${esc(p.name)}</td><td class="l sm mono">${s.lab}</td>`;
    for(const b of B){const n=ds.filter(x=>x>=b[0]&&x<=b[1]).length;
      h+=`<td class="${n?'':'mut'}">${n?n+'<div class="sm mut">'+Math.round(100*n/ds.length)+'%</div>':'·'}</td>`;}
    h+=`<td>${s.tot.dmed??'—'}</td><td class="now">${s.tot.dmax??'—'}</td></tr>`;
  }
  h+='</tbody></table></div></div>';

  h+=`<div class="blk"><h2>Вложенность против позиции</h2>
  <p class="note">Медиана позиции и доля ТОП-10 по корзинам глубины, по всем пулам сразу. Это срез, а не причинность: глубина растёт со временем, поэтому корзины не равны по возрасту.</p>
  <div class="tw"><table><thead><tr><th class="l">Глубина</th><th>Ключей</th><th>Медиана позиции</th><th>В Т10</th><th>Доля Т10</th></tr></thead><tbody>`;
  const all=keyRows().filter(r=>!r.pool.excl&&r.d!=null);
  for(const b of B){
    const g=all.filter(r=>r.d>=b[0]&&r.d<=b[1]);
    if(!g.length){h+=`<tr><td class="l">${lbl(b)}</td><td class="mut">0</td><td class="mut">—</td><td class="mut">—</td><td class="mut">—</td></tr>`;continue;}
    const ps=g.map(r=>r.p).sort((a,b2)=>a-b2), md=ps[Math.floor(ps.length/2)];
    const t10=g.filter(r=>r.p<=10).length;
    h+=`<tr><td class="l">${lbl(b)}</td><td>${g.length}</td><td>${md}</td><td class="${t10?'now':'mut'}">${t10}</td>
      <td>${nf(100*t10/g.length,1)}%</td></tr>`;
  }
  h+='</tbody></table></div></div>';

  h+=`<div class="blk"><h2>Какие страницы ранжируются</h2>
  <p class="note">Путь URL без повторов <code>/ru</code>. Показывает, тянет ли пул только главную или внутренние страницы тоже.</p>
  <div class="tw"><table><thead><tr><th class="l">Пул</th><th class="l">Страница</th><th>Ключей</th><th>В Т10</th><th>Доменов</th></tr></thead><tbody>`;
  for(const p of D.pools){
    if(p.excl) continue;
    const {s}=snapOf(p), m=new Map();
    for(const r of s.rows){const k=PD[r[4]];let e=m.get(k);if(!e){e={n:0,t10:0,d:new Set()};m.set(k,e);}
      e.n++;if(r[2]<=10)e.t10++;e.d.add(r[1]);}
    const ls=[...m.entries()].sort((a,b)=>b[1].n-a[1].n);
    let first=true;
    for(const [pg,e] of ls){
      h+=`<tr><td class="l">${first?esc(p.name):''}</td><td class="l mono sm">${esc(pg)}</td>
        <td>${e.n}</td><td class="${e.t10?'now':'mut'}">${e.t10}</td><td>${e.d.size}</td></tr>`;
      first=false;}
    if(!ls.length) h+=`<tr><td class="l">${esc(p.name)}</td><td class="l mut" colspan="4">позиций нет</td></tr>`;
  }
  return h+'</tbody></table></div></div>';
}

/* ── рендер ──────────────────────────────────────────────── */
const TABS=[['pools','Пулы',tPools],['doms','Домены',tDoms],['brands','Бренды',tBrands],
            ['keys','Ключи',tKeys],['nest','Вложенность и страницы',tNest]];
let TAB='pools';
function renderAll(){
  document.getElementById('main').innerHTML=TABS.find(t=>t[0]===TAB)[2]();
  const bind=(id,fn)=>{const e=document.getElementById(id);if(e)e.onchange=fn;};
  bind('dp',e=>{dPool=e.target.value;renderAll();});
  bind('ds',e=>{dSort=e.target.value;renderAll();});
  bind('bt',e=>{bTier=e.target.value;renderAll();});
  bind('kp',e=>{kPool=e.target.value;renderAll();});
  bind('kt',e=>{kTier=e.target.value;renderAll();});
  bind('kn',e=>{kTop=e.target.value;renderAll();});
  const q=document.getElementById('kq');
  if(q){q.oninput=e=>{kQ=e.target.value;const pos=e.target.selectionStart;renderAll();
    const n=document.getElementById('kq');n.focus();n.setSelectionRange(pos,pos);};}
}
document.getElementById('nav').innerHTML=TABS.map(([id,l])=>
  `<button data-t="${id}" aria-selected="${id===TAB}">${l}</button>`).join('');
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{
  TAB=b.dataset.t;
  document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===TAB));
  renderAll();window.scrollTo(0,0);});
buildSwitch();renderAll();

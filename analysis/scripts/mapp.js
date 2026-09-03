const D=window.DATA, R=D.rows;
const nf=(x,d=0)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pl=(n,a,b,c)=>{const x=Math.abs(n)%100,y=x%10;return n+' '+(x>10&&x<20?c:y===1?a:y>1&&y<5?b:c);};
const cls=p=>p==null?'mut':p<=3?'good':p<=10?'now':p<=30?'':'mut';

/* ── 1. ДОМЕНЫ ───────────────────────────────────────────── */
let sort='reg', only='all';
function tDoms(){
  let rows=[...R];
  if(only==='dep') rows=rows.filter(r=>r.dep>0);
  if(only==='new') rows=rows.filter(r=>['31.08','01.09','02.09','27.08'].includes(String(r.day)));
  const K={reg:r=>[-r.reg,-r.dep],dep:r=>[-r.dep,-r.reg],t10:r=>[-(r.t10??-1)],
           day:r=>[String(r.day)],dom:r=>[r.dom]};
  rows.sort((a,b)=>{const x=K[sort](a),y=K[sort](b);
    for(let i=0;i<x.length;i++){if(x[i]<y[i])return -1;if(x[i]>y[i])return 1;}return 0;});
  let h=`<div class="blk"><h2>Домены, которые принесли деньги</h2>
  <p class="note">Пятьдесят девять доменов за 27 августа — 3 сентября. Для каждого — его группа контента,
  день запуска и позиции на последнем известном замере. В последней колонке — бренды, по которым пришли
  регистрации, и в скобках позиция этого бренда на этом же домене: <b>«нет позиции»</b> значит, что
  по отслеживаемым ключам бренда домен не находится нигде в сотне.</p>
  <div class="brow">
    <span class="mk">показать</span>
    <select id="of"><option value="all"${only==='all'?' selected':''}>все домены</option>
      <option value="dep"${only==='dep'?' selected':''}>только с депозитами</option>
      <option value="new"${only==='new'?' selected':''}>только свежие запуски (с 27.08)</option></select>
    <span class="mk">сортировка</span>
    <select id="so">${[['reg','по регистрациям'],['dep','по депозитам'],['t10','по позициям в десятке'],
      ['day','по дню запуска'],['dom','по имени']].map(([v,l])=>`<option value="${v}"${sort===v?' selected':''}>${l}</option>`).join('')}</select>
    <span class="bch">строк <b>${rows.length}</b></span>
  </div>
  <div class="tw"><table class="big"><thead><tr>
    <th class="l">Домен</th><th>Рег.</th><th>Деп.</th><th class="l">Группа контента</th>
    <th class="l">Конфигурация</th><th class="l">Запуск</th>
    <th>В тройке</th><th>В десятке</th><th>Всего найдено</th><th>Лучшая</th>
    <th class="l">Бренды, по которым пришли деньги</th></tr></thead><tbody>`;
  for(const r of rows){
    const bad=!r.known||r.nopos;
    h+=`<tr${r.dep?' class="hasdep"':''}><td class="l mono"><b>${esc(r.dom)}</b></td>
      <td class="good"><b>${r.reg}</b></td>
      <td class="${r.dep?'good':'mut'}">${r.dep||'·'}</td>
      <td class="l sm">${r.known?esc(r.group):'<span class="mut">не опознан</span>'}</td>
      <td class="l sm mut">${r.known?esc(r.cfg):'—'}</td>
      <td class="l sm">${r.known?esc(String(r.day)):'<span class="mut">?</span>'}</td>
      <td class="${r.t3?'good':'mut'}">${bad?'<span class="mut">нет замеров</span>':(r.t3||0)}</td>
      <td class="${r.t10?'now':'mut'}">${bad?'':(r.t10||0)}</td>
      <td>${bad?'':(r.t100||0)}</td>
      <td class="${cls(r.best)}">${bad?'':(r.best??'—')}</td>
      <td class="l sm">${r.subs.map(([b,n])=>{const p=r.brpos?r.brpos[b]:null;
        const ok=p!=null&&p<999;
        return `<span class="bch ${ok?'ok':'no'}">${esc(b)}${n>1?' ×'+n:''} <b>${ok?'поз '+p:(bad?'?':'нет позиции')}</b></span>`;}).join('')}</td></tr>`;
  }
  return h+'</tbody></table></div></div>';
}

/* ── 2. РАЗРЕЗЫ ──────────────────────────────────────────── */
function agg(key){
  const m=new Map();
  for(const r of R){const k=r.known?String(r[key]):'— не опознано —';
    let e=m.get(k);if(!e){e={k,reg:0,dep:0,doms:new Set()};m.set(k,e);}
    e.reg+=r.reg;e.dep+=r.dep;e.doms.add(r.dom);}
  return [...m.values()].sort((a,b)=>b.reg-a.reg);
}
function tCuts(){
  let h=`<div class="blk"><h2>Откуда пришли деньги</h2>
  <p class="note">Здесь считаются только регистрации и депозиты из этой выгрузки. Число доменов — это
  домены, которые дали хотя бы одно событие, а не размер группы, поэтому «регистраций на домен»
  тут не считается: без знаменателя это была бы неправда.</p>
  <div class="tiles">
    <div class="tile a"><div class="k">Всего регистраций</div><div class="v">${D.reg}</div>
      <div class="c">на ${pl(D.ndom,'домене','доменах','доменах')} за неделю</div></div>
    <div class="tile g"><div class="k">Депозитов</div><div class="v">${D.dep}</div>
      <div class="c">на ${pl(D.ndep,'домене','доменах','доменах')}</div></div>
    <div class="tile"><div class="k">Опознано доменов</div><div class="v">${D.nknown}</div>
      <div class="c">из ${D.ndom} — у остальных группа неизвестна</div></div>
    <div class="tile b"><div class="k">Регистраций с брендов<br>вне отслеживаемого ядра</div><div class="v">${D.outcore}</div>
      <div class="c">эти бренды мы вообще не мониторим по позициям</div></div>
  </div>`;
  for(const [key,title,note] of [
    ['day','По дню запуска домена','Домены живут около шести суток, поэтому свежие дни здесь недобрали просто по возрасту.'],
    ['group','По группе контента','Одна группа — один контент и один день. Числа маленькие: это событийная выгрузка, а не сравнение конфигураций.'],
    ['zone','По зоне домена','']]){
    h+=`<h3 class="vt">${title}</h3>${note?`<p class="note">${note}</p>`:''}
    <div class="tw"><table><thead><tr><th class="l">${key==='day'?'День запуска':key==='group'?'Группа':'Зона'}</th>
      <th>Регистраций</th><th>Депозитов</th><th>Доменов с событиями</th></tr></thead><tbody>`;
    for(const e of agg(key))
      h+=`<tr><td class="l">${esc(e.k)}</td><td class="good"><b>${e.reg}</b></td>
        <td class="${e.dep?'good':'mut'}">${e.dep||'·'}</td><td>${e.doms.size}</td></tr>`;
    h+='</tbody></table></div>';
  }
  h+=`<h3 class="vt">По странам</h3>
  <p class="note">Больше половины регистраций приходит не из России, при том что весь трафик по рефереру яндексовый.</p>
  <div class="tw"><table><thead><tr><th class="l">Страна</th><th>Регистраций</th><th>Доля</th></tr></thead><tbody>`;
  for(const [g,n] of D.geo) h+=`<tr><td class="l">${esc(g)}</td><td><b>${n}</b></td>
    <td>${nf(100*n/D.reg,0)}%</td></tr>`;
  h+='</tbody></table></div>';
  h+=`<h3 class="vt">По брендам</h3>
  <p class="note">Бренд — это поддомен, на котором произошла регистрация. Тир взят из отслеживаемого ядра;
  «нет в ядре» значит, что позиции этого бренда мы вообще не меряем.</p>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th class="l">Спрос</th>
    <th>Регистраций</th><th>Доменов</th></tr></thead><tbody>`;
  for(const b of D.brands) h+=`<tr${b.t==='нет в ядре'?' class="tr-bad"':''}><td class="l"><b>${esc(b.b)}</b></td>
    <td class="l"><span class="tr tr-${b.t==='нет в ядре'?'нет':b.t}">${esc(b.t)}</span></td>
    <td class="good"><b>${b.n}</b></td><td>${b.d}</td></tr>`;
  return h+'</tbody></table></div></div>';
}

/* ── 3. ПОЗИЦИИ ПРОТИВ ДЕНЕГ ─────────────────────────────── */
function tVs(){
  return `<div class="blk"><h2>Позиции почти не объясняют деньги</h2>
  <p class="note">Для каждой регистрации я посмотрел, стоит ли этот домен хоть на какой-то позиции
  по тому бренду, на котором произошла регистрация.</p>
  <div class="tiles">
    <div class="tile g"><div class="k">Бренд стоит в сотне<br>на этом домене</div><div class="v">${D.vs.hit}</div>
      <div class="c">медиана позиции ${D.vs.med}, из них ${D.vs.t10} в десятке</div></div>
    <div class="tile b"><div class="k">У бренда нет позиции<br>на этом домене</div><div class="v">${D.vs.miss}</div>
      <div class="c">домен не находится нигде в сотне по ключам этого бренда</div></div>
    <div class="tile b"><div class="k">Бренда вообще нет<br>в отслеживаемом ядре</div><div class="v">${D.outcore}</div>
      <div class="c">позиции по нему никогда не мерились</div></div>
  </div>
  <p class="verd">Только <b>${D.vs.hit}</b> ${D.vs.hit===1?'регистрация пришла':'регистраций пришли'} с бренда,
  по которому домен реально стоит. Ещё <b>${D.vs.miss}</b> — с брендов, которые мы меряем, но домен по ним
  не находится, и <b>${D.outcore}</b> — с брендов, которых нет в ядре вообще.</p>
  <div class="grid2" style="margin-top:16px">
    <div class="card"><h3>Что это значит на практике</h3>
    <p>Счётчик «ключей в десятке» и счётчик регистраций смотрят на разные части сайта. Домен получает
    деньги с брендов, по которым мы его позиции не видим — либо потому, что эти бренды не заведены
    в ядро, либо потому, что трафик идёт по ключам, которых в ядре нет.</p>
    <p>Поэтому выбирать конфигурацию только по числу ключей в десятке рискованно: этот показатель
    измеряет охват по ядру, а не заработок.</p></div>
    <div class="card warn-c"><h3>Чего эта таблица НЕ говорит</h3>
    <p>Она не говорит, что позиции не нужны. Регистрация приходит с поисковой выдачи — значит позиция
    была, просто по ключу вне ядра.</p>
    <p>Правильный вывод: <b>ядро из ${D.nkeys} ключей покрывает не тот спрос, который приносит деньги</b>.
    Стоит завести в мониторинг те ${D.noutbrands} брендов, что платят, но не отслеживаются —
    тогда связь позиций и денег станет видна.</p></div>
  </div></div>`;
}

const TABS=[['doms','Домены с деньгами',tDoms],['cuts','Разрезы',tCuts],['vs','Позиции против денег',tVs]];
let TAB='doms';
function renderAll(){
  document.getElementById('main').innerHTML=TABS.find(t=>t[0]===TAB)[2]();
  const bind=(id,fn)=>{const e=document.getElementById(id);if(e)e.onchange=fn;};
  bind('of',e=>{only=e.target.value;renderAll();});
  bind('so',e=>{sort=e.target.value;renderAll();});
}
document.getElementById('nav').innerHTML=TABS.map(([id,l])=>
  `<button data-t="${id}" aria-selected="${id===TAB}">${l}</button>`).join('');
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{
  TAB=b.dataset.t;
  document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===TAB));
  renderAll();window.scrollTo(0,0);});
renderAll();

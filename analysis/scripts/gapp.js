const D=window.DATA, R=D.rows;
const nf=(x,d=0)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pl=(n,a,b,c)=>{const x=Math.abs(n)%100,y=x%10;return n+' '+(x>10&&x<20?c:y===1?a:y>1&&y<5?b:c);};
const QT={'закрыто':['ok','окно закрыто'],'открыто':['warn2','ещё копится'],
          'усечено':['bad2','данные обрезаны'],'нет дня':['bad2','дня нет']};
const SRCN={'готовый пак':'пак','генератор':'генератор','наборы':'наборы','выдача':'выдача','не указано':'—'};

let fDay='all', fMoney='all', fWin='all', fPg='all', open=new Set(), sortK='r';

function pass(r){
  if(fDay!=='all'&&r.day!==fDay) return false;
  if(fMoney==='money'&&!r.r) return false;
  if(fMoney==='dep'&&!r.dep) return false;
  if(fMoney==='zero'&&r.r) return false;
  if(fWin!=='all'&&r.q!==fWin) return false;
  if(fPg!=='all'&&String(r.pg)!==fPg) return false;
  return true;
}
const SORT={r:(a,b)=>b.r-a.r||b.share-a.share,
            share:(a,b)=>b.share-a.share||b.r-a.r,
            dep:(a,b)=>b.dep-a.dep||b.r-a.r,
            n:(a,b)=>b.n-a.n,
            day:(a,b)=>(a.day<b.day?1:-1)};

function domList(r){
  const win=r.doms.filter(d=>d.r||d.p), lose=r.doms.filter(d=>!d.r&&!d.p);
  return `<tr class="det"><td colspan="9"><div class="dbox">
   ${win.length?`<div class="dsec"><div class="dh">Дали деньги — ${pl(win.length,'домен','домена','доменов')}</div>
   <table class="inner"><tbody>`+win.map(d=>`<tr>
     <td class="l"><code>${esc(d.d)}</code></td>
     <td class="num">${d.r?`<span class="good">${d.r} рег</span>`:''}</td>
     <td class="num">${d.p?`<span class="gold">${d.p} деп</span>`:''}</td>
     <td class="num mut">${d.t10!=null?d.t10+' в Т10':''}</td>
     <td class="l">${d.br.map(b=>`<span class="bch sm">${esc(b[0])}${b[1]>1?` <b>×${b[1]}</b>`:''}</span>`).join('')}</td>
   </tr>`).join('')+`</tbody></table></div>`:''}
   ${lose.length?`<div class="dsec"><div class="dh">Без денег — ${pl(lose.length,'домен','домена','доменов')}</div>
     <div class="flat">${lose.map(d=>`<span class="bch sm">${esc(d.d)}${
       d.t10!=null&&d.t10>0?` <b>${d.t10}</b>`:''}</span>`).join('')}</div>
     ${lose.some(d=>d.t10!=null&&d.t10>0)?`<div class="note sm2">Число рядом с доменом — сколько его ключей стоит в первой десятке. Домены с позициями, но без регистраций — это те, где трафик есть, а денег нет.</div>`:''}
   </div>`:''}
  </div></td></tr>`;
}

function tGroups(){
  const rows=R.filter(pass).sort(SORT[sortK]);
  const sn=rows.reduce((a,r)=>a+r.n,0), sr=rows.reduce((a,r)=>a+r.r,0),
        sw=rows.reduce((a,r)=>a+r.w,0), sd=rows.reduce((a,r)=>a+r.dep,0);
  const days=[...new Set(R.map(r=>r.day))].sort().reverse();
  const pgs=[...new Set(R.map(r=>r.pg).filter(Boolean))].sort((a,b)=>a-b);
  return `<div class="blk">
  <h2>Каждая группа запуска и что она дала</h2>
  <p class="note">Одна строка — одна ветка одного дня. «С деньгами» — сколько доменов группы
  дали хотя бы одну регистрацию, из всех запущенных в ней. Нажмите на строку,
  чтобы увидеть поимённо, какие домены сработали и по каким брендам.</p>

  <div class="ctl">
    <label>день <select id="f-day">${['all',...days].map(d=>
      `<option value="${d}"${fDay===d?' selected':''}>${d==='all'?'все дни':d==='?'?'без дня':d}</option>`).join('')}</select></label>
    <label>показывать <select id="f-money">
      <option value="all"${fMoney==='all'?' selected':''}>все группы</option>
      <option value="money"${fMoney==='money'?' selected':''}>только с регистрациями</option>
      <option value="dep"${fMoney==='dep'?' selected':''}>только с депозитами</option>
      <option value="zero"${fMoney==='zero'?' selected':''}>только пустые</option></select></label>
    <label>окно <select id="f-win">
      <option value="all"${fWin==='all'?' selected':''}>любое</option>
      <option value="закрыто"${fWin==='закрыто'?' selected':''}>только закрытые</option>
      <option value="открыто"${fWin==='открыто'?' selected':''}>ещё копятся</option></select></label>
    <label>страниц <select id="f-pg">${['all',...pgs].map(p=>
      `<option value="${p}"${fPg===String(p)?' selected':''}>${p==='all'?'любое':p}</option>`).join('')}</select></label>
    <label>сортировка <select id="f-sort">
      <option value="r"${sortK==='r'?' selected':''}>по регистрациям</option>
      <option value="share"${sortK==='share'?' selected':''}>по доле сработавших</option>
      <option value="dep"${sortK==='dep'?' selected':''}>по депозитам</option>
      <option value="n"${sortK==='n'?' selected':''}>по размеру группы</option>
      <option value="day"${sortK==='day'?' selected':''}>по дате запуска</option></select></label>
  </div>
  ${rows.some(r=>r.day==='?')?`<p class="note">Строка «Списка запуска не присылали» стоит
   на 100 % не потому, что группа удачная: она собрана из доменов, которые нашлись
   в выгрузке конверсий. Доменов без денег в ней по определению нет, сравнивать её
   с остальными нельзя.</p>`:''}
  <p class="note">Показано ${pl(rows.length,'группа','группы','групп')}: ${sn} доменов,
  ${sw} с регистрациями, ${sr} регистраций, ${sd} депозитов.</p>

  <div class="tw"><table class="big"><thead><tr>
    <th class="l">День</th><th class="l">Группа</th><th>Доменов</th><th>С деньгами</th>
    <th>Доля</th><th>Регистраций</th><th>Депозитов</th><th class="l">Ключей в Т10</th>
    <th class="l">Окно</th></tr></thead><tbody>`
  +rows.map((r,i)=>{
    const key=r.day+'|'+r.g, isOpen=open.has(key);
    const [cl,txt]=QT[r.q]||['','—'];
    return `<tr class="grow${isOpen?' sel':''}${r.r?'':' dim'}" data-k="${esc(key)}" tabindex="0">
      <td class="l mono">${esc(r.day)}</td>
      <td class="l"><span class="gname">${esc(r.g)}</span>
        ${r.day==='?'?'<span class="tag bad2">отбор по результату</span>':''}
        ${r.pg?`<span class="tag">${r.pg} стр</span>`:''}
        ${r.dt?`<span class="tag">${esc(r.dt)}</span>`:''}
        <span class="tag">${esc(SRCN[r.src]||r.src)}</span>
        ${r.zones.slice(0,2).map(z=>`<span class="bch sm">${esc(z[0])} ${z[1]}</span>`).join('')}</td>
      <td>${r.n}</td>
      <td>${r.w||'<span class="mut">0</span>'}</td>
      <td class="${r.share>=30?'good':r.share?'':'mut'}"><b>${nf(r.share,0)}%</b></td>
      <td class="${r.r?'good':'mut'}"><b>${r.r||0}</b></td>
      <td class="${r.dep?'gold':'mut'}"><b>${r.dep||0}</b></td>
      <td class="l mono mut">${r.t10!=null?nf(r.t10,1):'—'}</td>
      <td class="l"><span class="tag ${cl}">${txt}</span>${
        r.q==='открыто'?`<div class="note sm2">прошло ${r.pct}%</div>`:''}</td>
    </tr>`+(isOpen?domList(r):'');
  }).join('')
  +`</tbody></table></div></div>`;
}

/* ── свод по признакам ── */
function agg(rows,f){
  const m={};
  rows.forEach(r=>{const k=f(r); if(k==null)return;
    (m[k]=m[k]||{n:0,w:0,r:0,dep:0,g:0});
    m[k].n+=r.n; m[k].w+=r.w; m[k].r+=r.r; m[k].dep+=r.dep; m[k].g++;});
  return Object.entries(m).sort((a,b)=>b[1].n-a[1].n);
}
function barTable(title,list,note){
  const mx=Math.max(...list.map(x=>100*x[1].w/x[1].n))||1;
  return `<h3 class="vt">${title}</h3>
  ${note?`<p class="note">${note}</p>`:''}
  <div class="bars">`+list.map(([k,v])=>{
    const pc=100*v.w/v.n;
    return `<div class="brow2"><span class="blab">${esc(k)}</span>
      <span class="btrack"><span class="bfill" style="width:${Math.max(2,100*pc/mx)}%"></span></span>
      <span class="bval">${nf(pc,1)}%</span></div>
      <div class="note sm2" style="margin:-2px 0 5px 92px">${v.w} из ${v.n} доменов
       в ${pl(v.g,'группе','группах','группах')} · ${pl(v.r,'регистрация','регистрации','регистраций')}
       ${v.dep?`· ${pl(v.dep,'депозит','депозита','депозитов')}`:''}</div>`;
  }).join('')+`</div>`;
}
function tSum(){
  const closed=R.filter(r=>r.q==='закрыто');
  const trunc=R.filter(r=>r.q==='усечено');
  const pgC=agg(closed,r=>r.pg?r.pg+' страниц':null);
  const pgT=agg(trunc,r=>r.pg?r.pg+' страниц':null);
  const get=(l,k)=>{const e=l.find(x=>x[0]===k); return e?e[1]:{n:0,w:0,r:0,dep:0,g:0};};
  const c12=get(pgC,'12 страниц'), c7=get(pgC,'7 страниц');
  const t12=get(pgT,'12 страниц'), t7=get(pgT,'7 страниц');
  return `<div class="blk"><h2>Свод: что общего у групп, которые дают деньги</h2>
  <p class="note">Только группы с закрытым окном — ${pl(closed.length,'группа','группы','групп')},
  ${closed.reduce((a,r)=>a+r.n,0)} доменов. Открытые и обрезанные дни исключены:
  у них доля заведомо занижена, и подмешивать их сюда нельзя.</p>

  <div class="card"><h3>Страницы: вопрос закрыт</h3>
  <p>Выгрузка конверсий от 11 сентября начинается 12 августа — на девять дней
  раньше всех прежних. Усечение слева, которое портило этот разрез,
  исчезло, и вместе с ним выросла выборка: закрытых окон стало тринадцать дней
  вместо семи.</p>
  <p>На чистых закрытых окнах: <b>12 страниц — 28,9 % (39 из 135),
  7 страниц — 13,8 % (13 из 94)</b>. Точный тест Фишера даёт <b>p = 0,0065</b>.</p>
  <p><b>Разница не объясняется днём запуска.</b> Внутри каждого из семи дней,
  где обе ветки запускались вместе, двенадцать страниц выигрывают в шести из семи.
  Тест Мантеля-Хензеля с контролем на день: <b>z = 2,38, p = 0,017</b>.</p>
  <p>Путь этого вывода стоит помнить: 2,9 σ на грязных данных → 0,45 после
  чистки от усечения → 0,067 со свежими наборами → <b>0,0065</b> на полной истории.
  Первая цифра была завышена ошибкой счёта, вторая и третья честно показывали,
  что данных не хватает. Хватило их только сейчас.</p></div>

  ${barTable('Число страниц',pgC,
    'Одиннадцать страниц держатся вровень с двенадцатью, но их всего 35 доменов — '+
    'погрешность ±7,8 пункта, отличить от двенадцати нечем.')}
  ${barTable('Даты в имени',agg(closed,r=>r.dt))}
  ${barTable('Откуда контент',agg(closed,r=>r.src==='не указано'?null:r.src),
    'Наш генератор против готового пака против наборов.')}
  ${barTable('Доменная зона (по преобладающей в группе)',agg(closed,r=>r.zones[0]?r.zones[0][0]:null))}
  <p class="verd">Подтверждённых рычагов теперь два: <b>число страниц</b>
  (12 против 7, p = 0,0065 с контролем на день) и <b>класс бренда</b>
  (ВЧ даёт на порядок больше регистраций на ключ в первой десятке, чем НЧ).
  Даты проверены на 251 домене с закрытым окном и мертвы:
  22,6 % без дат против 24,3 % с датами, p = 0,65. Зона и источник контента
  по-прежнему не установлены — их выборки перекошены по возрасту.</p></div>`;
}

function tTop(){
  const win=R.filter(r=>r.r>0&&r.q==='закрыто'&&r.n>=5).sort((a,b)=>b.share-a.share).slice(0,12);
  const zero=R.filter(r=>r.r===0&&r.q==='закрыто'&&r.n>=5).sort((a,b)=>b.n-a.n);
  const orph=R.find(r=>r.day==='?');
  return `<div class="blk"><h2>Лучшие и пустые</h2>
  <p class="note">Только закрытые окна и группы от пяти доменов — на группе из одного-двух
  доменов доля ничего не значит.</p>
  <h3 class="vt">Двенадцать групп с самой высокой долей сработавших доменов</h3>
  <div class="tw"><table><thead><tr><th class="l">День</th><th class="l">Группа</th>
    <th>Доменов</th><th>С деньгами</th><th>Доля</th><th>Рег</th><th>Деп</th></tr></thead><tbody>`
  +win.map(r=>`<tr><td class="l mono">${esc(r.day)}</td><td class="l">${esc(r.g)}</td>
     <td>${r.n}</td><td>${r.w}</td><td class="good"><b>${nf(r.share,0)}%</b></td>
     <td>${r.r}</td><td class="${r.dep?'gold':'mut'}">${r.dep||0}</td></tr>`).join('')
  +`</tbody></table></div>
  <p class="verd">Все группы наверху — мелкие, от пяти до семнадцати доменов.
  При таком размере одна-две удачи двигают долю на десятки пунктов, поэтому
  порядок в этой таблице читать как рейтинг нельзя. Она нужна для другого:
  посмотреть, нет ли наверху одной и той же конфигурации. Её там нет —
  наверху вперемешку и пак, и генератор, и наборы.</p>

  <h3 class="vt">Группы с закрытым окном, которые не дали ни одной регистрации</h3>
  <p class="note">${pl(zero.length,'группа','группы','групп')},
   ${zero.reduce((a,r)=>a+r.n,0)} доменов вхолостую.</p>
  <div class="tw"><table><thead><tr><th class="l">День</th><th class="l">Группа</th>
    <th>Доменов</th><th class="l">Ключей в Т10</th><th class="l">Зоны</th></tr></thead><tbody>`
  +zero.map(r=>`<tr><td class="l mono">${esc(r.day)}</td><td class="l">${esc(r.g)}</td>
     <td>${r.n}</td><td class="l mono mut">${r.t10!=null?nf(r.t10,1):'—'}</td>
     <td class="l">${r.zones.map(z=>`<span class="bch sm">${esc(z[0])} ${z[1]}</span>`).join('')}</td></tr>`).join('')
  +`</tbody></table></div>
  <p class="verd">Обратите внимание на колонку с ключами в первой десятке:
  среди пустых групп есть такие, где позиции нормальные. Значит дело не в том,
  что домен не встал в выдачу, — он встал, но по брендам, которые не конвертят.</p>

  ${orph?`<h3 class="vt">Дыра в учёте</h3>
  <div class="card warn-c"><p><b>${orph.n} доменов</b> дали
  <b>${pl(orph.r,'регистрацию','регистрации','регистраций')}</b>
  и ${pl(orph.dep,'депозит','депозита','депозитов')}, но списков их запуска мне не присылали.
  Ни дня, ни группы, ни конфигурации.</p>
  <p>Это ${nf(100*orph.r/D.tot.r,0)} % всех регистраций за историю, которые не участвуют
  ни в одном сравнении. Пока эти списки не появятся, любой вывод про конфигурации
  строится на оставшихся ${nf(100-100*orph.r/D.tot.r,0)} %.</p>
  <div class="flat" style="margin-top:8px">${orph.doms.map(d=>
    `<span class="bch sm">${esc(d.d)}${d.r?` <b>${d.r}</b>`:''}</span>`).join('')}</div></div>`:''}
  </div>`;
}

const TABS=[['g','Все группы',tGroups],['top','Лучшие и пустые',tTop],['sum','Свод по признакам',tSum]];
let TAB='g';
function render(){
  document.getElementById('main').innerHTML=TABS.find(t=>t[0]===TAB)[2]();
  const bind=(id,fn)=>{const e=document.getElementById(id); if(e)e.onchange=()=>{fn(e.value);render();};};
  bind('f-day',v=>fDay=v); bind('f-money',v=>fMoney=v); bind('f-win',v=>fWin=v);
  bind('f-pg',v=>fPg=v); bind('f-sort',v=>sortK=v);
  document.querySelectorAll('tr.grow').forEach(tr=>{
    const go=()=>{const k=tr.dataset.k; open.has(k)?open.delete(k):open.add(k); render();};
    tr.onclick=go;
    tr.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go();}};
  });
  document.querySelectorAll('#nav button').forEach(b=>b.setAttribute('aria-selected',b.dataset.t===TAB));
}
document.getElementById('nav').innerHTML=TABS.map(([id,l])=>
  `<button data-t="${id}" role="tab" aria-selected="${id===TAB}">${l}</button>`).join('');
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{TAB=b.dataset.t; open.clear(); render();});
render();

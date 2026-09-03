const D=window.DATA;
const nf=(x,d=0)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pl=(n,a,b,c)=>{const x=Math.abs(n)%100,y=x%10;return n+' '+(x>10&&x<20?c:y===1?a:y>1&&y<5?b:c);};
const QN={'ok':'полное','усечено':'обрезано слева','окно открыто':'ещё копится'};

/* меры окна: значение всегда подписано числом, цвет — не единственный носитель */
const meter=(pct,cl)=>`<div class="meter" role="img" aria-label="${pct}% окна">
  <div class="mfill${cl?' done':''}" style="width:${pct}%"></div></div>`;

/* ── 1. ДНИ ЗАПУСКА ──────────────────────────────────────── */
let showq='all';
function tDays(){
  const rows=D.days.filter(d=>showq==='all'||d.q===showq);
  let h=`<div class="blk"><h2>Все дни запуска</h2>
  <p class="note">Домен зарабатывает около шести суток, и три четверти денег приходят в первые двое.
  Колонка «окно» показывает, какая доля этого срока уже прошла: пока она не заполнена,
  доля доменов с деньгами будет расти, и сравнивать такой день с закрытыми нельзя.
  Колонка «данные» отмечает дни, у которых часть жизни не попала в выгрузку конверсий —
  она начинается 21 августа.</p>
  <div class="brow"><span class="mk">показать</span>
    <select id="qf">
      <option value="all"${showq==='all'?' selected':''}>все дни</option>
      <option value="ok"${showq==='ok'?' selected':''}>только пригодные для сравнения</option>
      <option value="окно открыто"${showq==='окно открыто'?' selected':''}>только с открытым окном</option>
      <option value="усечено"${showq==='усечено'?' selected':''}>только с обрезанными данными</option>
    </select></div>
  <div class="tw"><table class="big"><thead><tr>
    <th class="l">День запуска</th><th>Доменов</th><th>Групп</th>
    <th class="l">Окно</th><th class="l">Данные</th>
    <th>С деньгами</th><th>Доля</th><th>Отклонение</th>
    <th>Регистраций</th><th>Депозитов</th><th>Рег/дом</th><th>Прогноз</th><th>Т10/дом</th>
  </tr></thead><tbody>`;
  for(const d of rows){
    const closed=d.age>=6;
    h+=`<tr class="q-${d.q==='ok'?'ok':d.q==='усечено'?'cut':'open'}">
      <td class="l"><b class="dday">${esc(d.day)}</b><div class="sm mut">${pl(d.age,'сутки','суток','суток')} назад</div></td>
      <td>${d.n}</td><td>${d.groups.length}</td>
      <td class="l">${meter(d.pct,closed)}<div class="sm mut">${closed?'закрыто':`${d.pct}% из 100`}</div></td>
      <td class="l sm">${d.q==='ok'?'<span class="tag ok">полное</span>'
        :d.q==='усечено'?`<span class="tag bad2">нет первых ${pl(d.lost,'суток','суток','суток')}</span>
           <div class="mut">это ~${d.lostpct}% заработка</div>`
        :'<span class="tag warn2">ещё копится</span>'}</td>
      <td>${d.w}</td>
      <td class="${d.q==='ok'?'now':'mut'}"><b>${nf(d.share,1)}%</b></td>
      <td class="sm ${d.q!=='ok'?'mut':Math.abs(d.z)>=2?'warn':''}">${d.q==='ok'?(d.z>0?'+':'')+nf(d.z,1)+' σ':'—'}</td>
      <td>${d.r}</td><td class="${d.dep?'good':'mut'}">${d.dep||'·'}</td>
      <td><b>${nf(d.rpd,2)}</b></td>
      <td class="${d.proj?'warn':'mut'}">${d.proj?nf(d.proj,2):'—'}</td>
      <td class="${d.t10==null?'mut':''}">${d.t10==null?'нет замеров':nf(d.t10,1)}</td></tr>`;
  }
  h+='</tbody></table></div>';
  h+=`<p class="verd">Колонка «прогноз» — это регистрации на домен, поделённые на пройденную долю окна.
  Грубая оценка того, куда день придёт к закрытию, и только для дней с открытым окном.
  На возрасте одних суток она умножает на пять с половиной, поэтому у 2 сентября ей верить нельзя.</p>`;

  if(D.gap.length) h+=`<div class="blk"><h3 class="vt">Дни без запусков</h3>
    <p class="note">В эти дни ничего не запускали, поэтому в таблице их нет.
    Конверсии в них приходили — но с доменов, запущенных раньше.</p>
    <div class="brow">${D.gap.map(g=>`<span class="bch">${esc(g)}</span>`).join('')}</div></div>`;
  return h+'</div>';
}

/* ── 2. ДНИ ПОДРОБНО ─────────────────────────────────────── */
function tCards(){
  let h=`<div class="blk"><h2>Что запускали в каждый день</h2>
  <p class="note">Группы внутри дня. «Т10 на домен» — ключей в десятке на последнем известном замере;
  у архивных групп это замер их собственной эпохи, а не сегодняшний.</p><div class="grid2">`;
  for(const d of D.days){
    const closed=d.age>=6;
    h+=`<div class="gcard"><div class="gh"><h3>${esc(d.day)}</h3>
      <div class="gt">
        <span class="tag${d.q==='ok'?' ok':d.q==='усечено'?' bad2':' warn2'}">${esc(QN[d.q])}</span>
        <span class="tag">${pl(d.n,'домен','домена','доменов')}</span></div></div>
      <div class="meta">
        <div><span class="mk">Окно</span><span class="mv">${closed?'закрыто':d.pct+'%'}</span></div>
        <div><span class="mk">С деньгами</span><span class="mv">${d.w} из ${d.n}</span></div>
        <div><span class="mk">Регистраций</span><span class="mv">${d.r}</span></div>
        <div><span class="mk">На домен</span><span class="mv">${nf(d.rpd,2)}</span></div>
      </div>
      <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Дом.</th>
        <th>С деньгами</th><th>Рег.</th><th>Т10/дом</th></tr></thead><tbody>`;
    for(const g of d.groups)
      h+=`<tr${g.r?'':' class="tr-bad"'}><td class="l sm">${esc(g.g)}</td><td>${g.n}</td>
        <td class="${g.w?'good':'mut'}">${g.w}</td><td class="${g.r?'good':'mut'}"><b>${g.r}</b></td>
        <td class="${g.t10==null?'mut':''}">${g.t10==null?'—':nf(g.t10,1)}</td></tr>`;
    h+='</tbody></table></div></div>';
  }
  return h+'</div></div>';
}

/* ── 3. КАК ПРИХОДЯТ ДЕНЬГИ ──────────────────────────────── */
function bars(items,label,val,unit){
  const mx=Math.max(...items.map(val));
  return `<div class="bars">${items.map(x=>{
    const v=val(x),w=100*v/mx;
    return `<div class="brow2" title="${esc(label(x))}: ${v} ${unit}">
      <span class="blab">${esc(label(x))}</span>
      <span class="btrack"><span class="bfill" style="width:${w}%"></span></span>
      <span class="bval">${v}</span></div>`;}).join('')}</div>`;
}
function tHow(){
  const mx=D.arr.reduce((a,b)=>b.n>a.n?b:a);
  return `<div class="blk"><h2>Когда приходят регистрации</h2>
  <p class="note">По календарным дням, все домены вместе. Регистрации шли во все
  ${pl(D.arr.length,'день','дня','дней')} периода без единого пустого — это и есть ответ на вопрос
  про удачные даты: их нет, поток ровный.</p>
  <h3 class="vt">Регистраций в сутки</h3>
  ${bars(D.arr,x=>x.d,x=>x.n,'рег.')}
  <p class="verd">Единственный заметный пик — ${esc(mx.d)} с ${mx.n} регистрациями.
  Он приходится на вторые сутки жизни крупной партии 21–22 августа, то есть объясняется
  возрастом доменов, а не самой датой.</p></div>

  <div class="blk"><h2>На каких сутках жизни домена</h2>
  <p class="note">Возраст домена в момент регистрации. Считаются только домены, у которых известен день запуска.</p>
  ${bars(D.age,x=>x.d+' сут.',x=>x.n,'рег.')}
  <h3 class="vt">Накопительная кривая, по которой считается окно</h3>
  <div class="tw"><table><thead><tr><th class="l">Прошло суток</th>
    ${D.curve.map((_,i)=>`<th>${i}</th>`).join('')}</tr></thead>
    <tbody><tr><td class="l">Накоплено заработка</td>
    ${D.curve.map(c=>`<td>${c}%</td>`).join('')}</tr></tbody></table></div>
  <p class="verd">Отсюда правило: домену меньше двух суток — сравнивать его по деньгам
  с кем угодно бессмысленно, у него на руках меньше половины будущего результата.</p></div>`;
}

/* ── 4. ЧТО МОЖНО СРАВНИВАТЬ ─────────────────────────────── */
function tQ(){
  const ok=D.days.filter(d=>d.q==='ok'&&d.n>=20);
  const cut=D.days.filter(d=>d.q==='усечено');
  const open=D.days.filter(d=>d.q==='окно открыто');
  return `<div class="blk"><h2>Какие дни вообще можно ставить рядом</h2>
  <div class="tiles">
    <div class="tile g"><div class="k">Пригодны для сравнения</div><div class="v">${ok.length}</div>
      <div class="c">${ok.map(d=>d.day).join(', ')} — окно закрыто, данные полные, доменов хватает</div></div>
    <div class="tile b"><div class="k">Данные обрезаны слева</div><div class="v">${cut.length}</div>
      <div class="c">${cut.map(d=>d.day).join(', ')} — выгрузка начинается 21.08, их лучшие дни в неё не попали</div></div>
    <div class="tile a"><div class="k">Окно ещё копится</div><div class="v">${open.length}</div>
      <div class="c">${open.map(d=>d.day).join(', ')} — доля вырастет, итог будет виден 6–8 сентября</div></div>
  </div>
  <h3 class="vt">Проверка: разброс между пригодными днями</h3>
  <div class="tw"><table><thead><tr><th class="l">День</th><th>Доменов</th><th>С деньгами</th>
    <th>Доля</th><th>Отклонение от базовой</th></tr></thead><tbody>`
  +ok.map(d=>`<tr><td class="l">${esc(d.day)}</td><td>${d.n}</td><td>${d.w}</td>
      <td><b>${nf(d.share,1)}%</b></td>
      <td class="${Math.abs(d.z)>=2?'warn':'mut'}">${(d.z>0?'+':'')+nf(d.z,1)} σ</td></tr>`).join('')
  +`</tbody></table></div>
  <p class="verd">Базовая доля по всем пригодным дням — <b>${nf(D.sim.base,1)}%</b>.
  Размах между лучшим и худшим днём <b>${nf(D.sim.obs,1)} пункта</b>.
  Двадцать тысяч случайных прогонов при этих размерах групп дают такой размах или больше
  в <b>${nf(D.sim.p,0)}% случаев</b> — то есть это обычная случайность,
  а не разница между днями. Удачных дат нет.</p>

  <div class="grid2" style="margin-top:16px">
    <div class="card warn-c"><h3>Две ловушки, на которых я уже споткнулся</h3>
    <p><b>Обрезка слева.</b> У доменов, запущенных 19 и 20 августа, первые сутки жизни
    не попали в выгрузку — а это от 18 до 49 процентов их заработка. Их 5,0 % и 12,6 %
    измеряют полноту данных, а не качество запуска.</p>
    <p><b>Отбор по результату.</b> В первой версии 27 августа стояло 8 из 8 = 100 %,
    потому что в карту попали только те домены, которых я нашёл в списке с конверсиями.
    С полным списком из реестра — 31 домен и 25,8 %, то есть ровно средний день.</p></div>
    <div class="card"><h3>Что делать с этим дальше</h3>
    <p>Дни 31 августа, 1 и 2 сентября закроют окна 6, 7 и 8 сентября. После этого
    пригодных для сравнения дней станет восемь вместо пяти, и выборка вырастет
    со 197 доменов до 314.</p>
    <p>Только тогда имеет смысл возвращаться к вопросу про конфигурации: на нынешних
    объёмах разница между днями и между большинством признаков неотличима от шума.</p></div>
  </div></div>`;
}

const TABS=[['days','Дни запуска',tDays],['cards','Дни подробно',tCards],
            ['how','Когда приходят деньги',tHow],['q','Что можно сравнивать',tQ]];
let TAB='days';
function renderAll(){
  document.getElementById('main').innerHTML=TABS.find(t=>t[0]===TAB)[2]();
  const e=document.getElementById('qf');
  if(e) e.onchange=x=>{showq=x.target.value;renderAll();};
}
document.getElementById('nav').innerHTML=TABS.map(([id,l])=>
  `<button data-t="${id}" aria-selected="${id===TAB}">${l}</button>`).join('');
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{
  TAB=b.dataset.t;
  document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===TAB));
  renderAll();window.scrollTo(0,0);});
renderAll();

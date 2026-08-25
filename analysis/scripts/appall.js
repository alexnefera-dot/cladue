const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), f2=(x)=>x.toFixed(2).replace('.',',');
const pc=(x)=>Math.round(x*100)+'%';
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':(v>=1e3?(v/1e3).toFixed(1).replace('.',',')+'k':Math.round(v)));
const pos=(p)=>p==null?'<span class="mut">—</span>':`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;
const zn=(z)=>`<span class="zone ${z==='.team'?'zt':''}">${esc(z)}</span>`;
const hist=(h)=>h.map(x=>x==null?'<span class="mut">—</span>':
  `<span class="${x<=3?'good':x<=10?'':'mut'}">${x}</span>`).join('<span class="mut"> › </span>');
function spark(s){const mx=Math.max(...s,0.01);
  return '<span class="spark" title="'+s.map(v=>f1(v)).join(' → ')+'">'+s.map((v,i)=>
    '<i class="'+(i===s.length-1?'hi':'')+'" style="height:'+Math.max(2,Math.round(v/mx*22))+'px"></i>').join('')+'</span>';}
const DM=D.doms, L=D.labs;

/* ---------------- обзор ---------------- */
function grow(g){
  return `<tr><td class="l id">${esc(g.name)}</td><td class="l mut">${esc(g.cfg)}</td>
    <td>${g.ntm}${g.n!==g.ntm?`<span class="mut"> / ${g.n}</span>`:''}</td>
    <td class="l num">${g.ser.map(f1).join(' › ')}</td>
    <td><b>${f2(g.t10)}</b></td><td>${g.med}</td><td>${f2(g.wo)}</td>
    <td class="${g.lead>=.5?'warn':''}">${pc(g.lead)}</td>
    <td class="l num mut">${g.vals.join(', ')}</td>
    <td class="${g.vch?'good':'mut'}">${g.vch}</td><td class="${g.sch?'good':'mut'}">${g.sch}</td>
    <td class="${g.t3?'good':'mut'}">${g.t3}</td><td class="mut">${g.t30}</td>
    <td class="mut">${g.t100}</td><td>${g.brands}</td>
    <td class="${g.z100?'bad':'mut'}">${g.z100}</td></tr>`;}
const HEAD=`<thead><tr><th class="l">Группа</th><th class="l">Что это</th><th>Дом .team</th>
  <th class="l">Т10/дом по съёмам</th><th>Т10/дом</th><th>Мед</th><th>Без лид.</th>
  <th>Доля лид.</th><th class="l">Значения</th><th>ВЧ</th><th>СЧ</th><th>ТОП-3</th><th>Т30</th>
  <th>Т100</th><th>Брендов</th><th>Нет Т100</th></tr></thead>`;

function tabOverview(){
  const T=(rows)=>`<div class="tw"><table>${HEAD}<tbody>${rows.map(grow).join('')}</tbody></table></div>`;
  const [ci,cn]=[D.img[1],D.img[0]], [dw,dn]=[D.dat[1],D.dat[0]], [ac,an]=[D.aut[0],D.aut[1]];
  const ctrl=D.groups[0];
  return `<div class="blk"><h2>Главное: выдача не просела</h2>
  <p class="note">Контрольная группа — контенты <b>NEW50_5_7pages_nodate_21.08</b>,
  тот же прогон генерации, что у ветки, запущенной 22.08. Изменилась только дата
  запуска. Если бы рынок ослаб, эти домены дали бы уровень 24.08.</p>
  <div class="cards">
    <div class="card ok"><h3>Контроль: ${f2(ctrl.t10)} ключа на домен за ~6 часов</h3>
      <p>Значения по девяти .team: <span class="num">${ctrl.vals.join(', ')}</span>.
      Лидер <span class="num">2424.team</span> — <b>108 ключей в ТОП-10</b>,
      27 в ТОП-3, 22 дорогих.</p>
      <p>Историческая вилка формата «12 стр + даты» на 9-10 часах — <b>11,7…26,4</b>.
      Контроль на шести часах уже <b>${f2(ctrl.t10)}</b>.</p></div>
    <div class="card err"><h3>Запуск 24.08 на том же возрасте давал 0,0-1,3</h3>
      <p>Первый съём 24.08: картинки 1,32, без картинок 0,63,
      старые аккаунты 0,00, новые 0,10 — на шести часах жизни.</p>
      <p><b>Значит дело было в партиях контента, а не в рынке.</b> Вопрос,
      висевший со вчера, закрыт.</p></div>
    <div class="card"><h3>Чем это подтверждается</h3>
      <p>Второй контроль — <span class="num">NEW33_12pages_withdate</span> —
      дал ${f2(D.groups[2].t10)} на шести часах. Слабее вилки, но втрое выше 24.08.</p>
      <p>И конверсии: восемь регистраций за сутки 25.08 пришли с доменов
      21-22.08, то есть прежние запуски живы и приносят.</p></div>
  </div></div>

  <div class="blk"><h2>Тест A: даты против без дат — пятый заход, первый чистый</h2>
  <p class="note">Обе ветки из одного прогона: id 938-953 сплошным блоком,
  создание в 16:04 и 16:05, по 8 доменов .team на сторону. Двигается только
  наличие дат. Четыре прошлых захода разваливались на разных партиях или возрасте.</p>
  ${T(D.dat)}
  <div class="cards" style="margin-top:14px">
    <div class="card ok"><h3>Без дат впереди вдвое по всем мерам</h3>
      <p>Среднее <span class="big">${f2(dn.t10)}</span> против ${f2(dw.t10)},
      «без лидера» <b>${f2(dn.wo)}</b> против ${f2(dw.wo)},
      медиана ${dn.med} против ${dw.med}, ТОП-3 <b>${dn.t3}</b> против ${dw.t3}.</p>
      <p class="mut">«Без лидера» вдвое выше — растёт вся ветка, а не один домен.</p></div>
    <div class="card"><h3>Сходится с прошлым чистым замером</h3>
      <p>23.08, другой контент, другой прогон, тот же формат:
      без дат <b>35,0</b> против 25,8 с датами.</p>
      <p>Два независимых чистых сравнения дали один ответ.
      <b>Даты не помогают.</b></p></div>
    <div class="card err"><h3>Оговорка про дорогие ключи</h3>
      <p>ВЧ почти поровну — ${dw.vch} у датированной против ${dn.vch}.
      Разрыв идёт по НЧ и СЧ, не по самым дорогим брендам.</p></div>
  </div></div>

  <div class="blk"><h2>Тест B: картинки, накопление за два дня</h2>
  <p class="note">Только .team, только наш генератор. День 1 — 9 против 9,
  день 2 — 5 против 8. День 2 собран менее чисто: ветки вышли из разных прогонов
  с разрывом в 27 минут.</p>
  ${T(D.img)}
  <div class="cards" style="margin-top:14px">
    <div class="card ok"><h3>Без картинок впереди оба дня подряд</h3>
      <p>День 1: 8,37 против 3,95. День 2: ${f2(cn.t10)} против ${f2(ci.t10)}.
      Накопленно <b>${f2(cn.t10)} против ${f2(ci.t10)}</b>,
      «без лидера» ${f2(cn.wo)} против ${f2(ci.wo)}.</p>
      <p>Дорогие ключи <b>${cn.vch+cn.sch}</b> против ${ci.vch+ci.sch},
      ТОП-3 <b>${cn.t3}</b> против ${ci.t3}.</p></div>
    <div class="card"><h3>Но первый съём 24.08 говорил обратное</h3>
      <p>На шести часах картинки вели вдвое — 2,78 против 1,22. Развернулось
      к восемнадцати часам и с тех пор держится.</p>
      <p class="mut">Похоже, картинки дают более быстрый старт и более низкий потолок.
      Проверяется третьим днём.</p></div>
    <div class="card err"><h3>Считать рано</h3>
      <p>24 против 27 доменов. По расчёту мощности двукратная разница
      читается на 25 регистрациях на ветку — по конверсиям мы пока
      набрали одну.</p>
      <p>По позициям разрыв устойчив два дня, но день 2 собран из разных прогонов.</p></div>
  </div></div>

  <div class="blk"><h2>Тест C: старые аккаунты против новых</h2>
  ${T([D.groups[6],D.groups[5]])}
  <p class="note" style="margin-top:10px">Среднее в пользу новых (8,40 против 6,00),
  но «без лидера» <b>4,33 против 4,22</b> — на типичном домене ничья, весь отрыв
  даёт <span class="num">nchg.team</span> с 45 ключами. Единственное чистое отличие —
  скорость входа в индекс: на первом съёме у старых был 81 ключ в сотне против 37
  и два пустых домена против четырёх. Возраст аккаунта даёт фору на старте,
  а не более высокий потолок.</p></div>

  <div class="blk"><h2>Чужой контент против нашего генератора</h2>
  <p class="note">Один съём 25.08 23:21, один возраст, все домены .team.
  Чужой — NEW33 обе ветки плюс контроль на контентах 21.08. Наш — Generator день 2.</p>
  ${T(D.aut)}
  <div class="cards" style="margin-top:14px">
    <div class="card ok"><h3>Чужой контент выигрывает втрое</h3>
      <p>${f2(ac.t10)} против ${f2(an.t10)} на домен, «без лидера»
      <b>${f2(ac.wo)}</b> против ${f2(an.wo)} — <b>втрое</b>.
      ТОП-3 ${ac.t3} против ${an.t3}, дорогих ${ac.vch+ac.sch} против ${an.vch+an.sch}.</p></div>
    <div class="card"><h3>Это меняет приоритет</h3>
      <p>Раньше по накопленному авторы были неразличимы: 20,1 против 20,4 Т10/дом.
      Здесь, на одном возрасте и одном съёме, разрыв трёхкратный.</p>
      <p class="mut">Одни сутки, 25 против 13 доменов. Но направление сильное.</p></div>
    <div class="card err"><h3>Оговорка</h3>
      <p>Форматы разные: у чужого 12 и 7 страниц, у нашего 11.
      Объём страниц по прошлым данным на позиции почти не влиял,
      но полностью исключить его нельзя.</p></div>
  </div></div>

  <div class="blk"><h2>Все девять веток</h2>
  ${T(D.groups)}</div>`;
}

/* ---------------- все домены ---------------- */
function rowDom(d,i){
  return `<tr class="clk dr" data-i="${i}" data-g="${esc(d.g)}" data-a="${esc(d.arm)}"
      data-z="${esc(d.zone)}" data-h="${d.vch+d.sch>0?1:0}">
    <td class="l id">${esc(d.d)}</td><td class="l">${zn(d.zone)}</td>
    <td class="l mut">${esc(d.g)}</td><td class="l mut">${esc(d.arm)}</td>
    <td class="l num mut">${d.tr.join(' › ')}</td>
    <td><b>${d.t10}</b></td><td>${d.t30}</td>
    <td class="${d.t100===0?'bad':''}">${d.t100}</td>
    <td class="${d.t3?'good':'mut'}">${d.t3}</td>
    <td class="${d.vch?'good':'mut'}">${d.vch}</td>
    <td class="${d.sch?'good':'mut'}">${d.sch}</td>
    <td class="mut">${d.nch}</td><td>${d.nb}</td><td>${pos(d.best)}</td></tr>
    <tr class="det" hidden><td colspan="14"><div class="inner"></div></td></tr>`;
}
function tabAll(){
  const opt=(a)=>a.map(x=>`<option>${esc(x)}</option>`).join('');
  return `<div class="blk"><h2>Все ${DM.length} доменов</h2>
  <p class="note">Строка раскрывается — бренды домена и все его ключи в ТОП-10
  с позициями по обоим съёмам.</p>
  <div class="filters">
    <label>Группа <select id="fg"><option>все</option>${opt([...new Set(DM.map(d=>d.g))])}</select></label>
    <label>Ветка <select id="fa"><option>все</option>${opt([...new Set(DM.map(d=>d.arm))])}</select></label>
    <label>Зона <select id="fz"><option>все</option>${opt([...new Set(DM.map(d=>d.zone))])}</select></label>
    <label><input type="checkbox" id="fh"> только с дорогими</label>
    <span class="mut" id="fcount"></span>
  </div>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Зона</th>
  <th class="l">Группа</th><th class="l">Ветка</th><th class="l">Т10 по съёмам</th>
  <th>Т10</th><th>Т30</th><th>Т100</th><th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>НЧ</th>
  <th>Брендов</th><th>Лучш.</th></tr></thead>
  <tbody id="allbody">${DM.map(rowDom).join('')}</tbody></table></div></div>`;
}
function wireFilters(){
  const g=document.getElementById('fg'),a=document.getElementById('fa'),
        z=document.getElementById('fz'),h=document.getElementById('fh'),
        c=document.getElementById('fcount');
  if(!g) return;
  const apply=()=>{let n=0;
    document.querySelectorAll('#allbody tr.dr').forEach(tr=>{
      const ok=(g.value==='все'||tr.dataset.g===g.value)&&(a.value==='все'||tr.dataset.a===a.value)
        &&(z.value==='все'||tr.dataset.z===z.value)&&(!h.checked||tr.dataset.h==='1');
      tr.hidden=!ok; tr.nextElementSibling.hidden=true; if(ok)n++;});
    c.textContent=n+' из '+DM.length;};
  [g,a,z,h].forEach(e=>e.onchange=apply); apply();
}

/* ---------------- лидеры ---------------- */
function tabLead(){
  const T=DM.filter(d=>d.t10>0).slice(0,14);
  return `<div class="blk"><h2>Лидеры: ${T.length} доменов с результатом</h2>
  <p class="note">Отсортировано по ключам в ТОП-10 на последнем съёме.
  ${DM.filter(d=>d.t10===0).length} доменов из ${DM.length} пока без единого ключа в десятке.</p>
  ${T.map(d=>`<div class="lead">
    <div class="lh"><span class="id big">${esc(d.d)}</span> ${zn(d.zone)}
      <span class="tag">${esc(d.g)}</span>
      <span class="tag ${d.arm==='с картинками'?'t-ВЧ':''}">${esc(d.arm)}</span>
      <span class="mut">Т10 <b class="num">${d.tr.join(' › ')}</b> ·
      Т30 ${d.t30} · Т100 ${d.t100} · ТОП-3 ${d.t3} · брендов ${d.nb} ·
      лучшая ${pos(d.best)}</span></div>
    <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
    <th>Лучшая</th><th>Ключей</th><th>ТОП-3</th></tr></thead><tbody>
    ${d.brands.slice(0,10).map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td>
      <td>${tg(b.t)}</td><td>${pos(b.best)}</td><td>${b.n}</td>
      <td class="${b.t3?'good':'mut'}">${b.t3}</td></tr>`).join('')}
    ${d.brands.length>10?`<tr><td class="l mut" colspan="6">… и ещё ${d.brands.length-10} брендов</td></tr>`:''}
    </tbody></table></div>
    <div class="leadkeys"><button class="more" data-lead="${esc(d.d)}">Показать все ${d.keys.length} ключей</button>
      <div class="box" hidden></div></div>
  </div>`).join('')}</div>`;
}
function wireLead(){
  document.querySelectorAll('button.more[data-lead]').forEach(b=>{b.onclick=()=>{
    const box=b.nextElementSibling; box.hidden=!box.hidden;
    b.textContent=box.hidden?'Показать все ключи':'Скрыть ключи';
    if(box.dataset.done) return; box.dataset.done=1;
    const d=DM.find(x=>x.d===b.dataset.lead);
    box.innerHTML=`<div class="tw"><table><thead><tr><th class="l">Ключ</th><th class="l">Бренд</th>
      <th class="l">Тип</th><th>Тир</th><th>Объём</th><th class="l">Позиции ${L.join(' › ')}</th>
      </tr></thead><tbody>`+
      d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
        <td class="l mut">${esc(k.c)}</td><td>${tg(k.t)}</td><td>${kf(k.v)}</td>
        <td class="l num">${hist(k.h)}</td></tr>`).join('')+`</tbody></table></div>`;};});
}

/* ---------------- бренды ---------------- */
function tabBrands(){
  const B=D.brands;
  return `<div class="blk"><h2>${B.length} брендов в ТОП-10</h2>
  <p class="note">Строка раскрывается — все домены, которые стоят по бренду.
  «Лучшая» — минимальная позиция по бренду среди всех 42 доменов.</p>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
  <th>Ключей</th><th>Доменов</th><th>Лучшая</th><th class="l">Лидер</th>
  </tr></thead><tbody>
  ${B.map((b,i)=>`<tr class="clk" data-b="${i}"><td class="l id">${esc(b.b)}</td>
    <td>${kf(b.v)}</td><td>${tg(b.t)}</td><td><b>${b.keys}</b></td>
    <td>${b.doms.length}</td><td>${pos(b.best)}</td>
    <td class="l"><span class="num">${esc(b.doms[0].d)}</span>
      <span class="mut"> · ${esc(b.doms[0].arm)}</span></td></tr>
    <tr class="det" hidden><td colspan="7"><div class="inner"></div></td></tr>`).join('')}
  </tbody></table></div></div>`;
}

/* ---------------- типы запросов ---------------- */
function tabCats(){
  const C=D.cats, tot=C.reduce((a,b)=>a+b.n,0);
  return `<div class="blk"><h2>Типы запросов в ТОП-10</h2>
  <p class="note">${tot} ключей на 42 доменах. Классификация по первому совпадению.</p>
  <div class="tw" style="max-width:560px"><table><thead><tr><th class="l">Тип</th>
  <th>Ключей</th><th>Доля</th></tr></thead><tbody>
  ${C.map(c=>`<tr><td class="l">${esc(c.c)}</td><td><b>${c.n}</b></td>
    <td class="mut">${Math.round(100*c.n/tot)}%</td></tr>`).join('')}
  </tbody></table></div></div>`;
}

function fill(){
  document.querySelectorAll('tr.clk[data-i]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1; const d=DM[+tr.dataset.i];
    let h=`<div><h4>${esc(d.d)} · ${esc(d.g)} · ${esc(d.arm)}</h4></div>`;
    if(d.brands.length) h+=`<div><h4>Бренды в ТОП-10 — ${d.brands.length}</h4><div class="tw"><table>
      <thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th><th>Лучшая</th><th>Ключей</th>
      <th>ТОП-3</th></tr></thead><tbody>`+
      d.brands.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
        <td>${pos(b.best)}</td><td>${b.n}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td></tr>`).join('')+
      `</tbody></table></div></div>`;
    if(d.keys.length) h+=`<div><h4>Ключи в ТОП-10 — ${d.keys.length} · позиции по съёмам
      (${L.join(', ')})</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th class="l">Тип</th><th>Тир</th>
      <th>Объём</th><th class="l">Позиции</th></tr></thead><tbody>`+
      d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
        <td class="l mut">${esc(k.c)}</td><td>${tg(k.t)}</td><td>${kf(k.v)}</td>
        <td class="l num">${hist(k.h)}</td></tr>`).join('')+`</tbody></table></div></div>`;
    else h+=`<div><h4>Ни одного ключа в ТОП-10 · в сотне ${d.t100}</h4></div>`;
    slot.innerHTML=h;};});
  document.querySelectorAll('tr.clk[data-b]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1; const b=D.brands[+tr.dataset.b];
    slot.innerHTML=`<div><h4>${esc(b.b)} — ${b.keys} ключей на ${b.doms.length} доменах</h4>
      <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Группа</th>
      <th class="l">Ветка</th><th>Лучшая</th><th>Ключей</th><th>ТОП-3</th></tr></thead><tbody>`+
      b.doms.map(x=>`<tr><td class="l id">${esc(x.d)}</td><td class="l mut">${esc(x.g)}</td>
        <td class="l mut">${esc(x.arm)}</td><td>${pos(x.best)}</td><td>${x.n}</td>
        <td class="${x.t3?'good':'mut'}">${x.t3}</td></tr>`).join('')+
      `</tbody></table></div></div>`;};});
  wireFilters(); wireLead();
}

const TABS=[["Обзор",tabOverview],["Все домены",tabAll],["Лидеры",tabLead],
  ["Бренды и ключи",tabBrands],["Типы запросов",tabCats]];
const nav=document.getElementById('nav'), main=document.getElementById('main');
TABS.forEach(([name],i)=>{const b=document.createElement('button');
  b.textContent=name; b.setAttribute('role','tab'); b.setAttribute('aria-selected',i===0);
  b.onclick=()=>show(i); nav.appendChild(b);
  const s=document.createElement('section'); s.hidden=i!==0; main.appendChild(s);});
function show(i){
  [...nav.children].forEach((b,j)=>b.setAttribute('aria-selected',i===j));
  [...main.children].forEach((s,j)=>{s.hidden=i!==j;
    if(i===j&&!s.dataset.done){s.dataset.done=1;s.innerHTML=TABS[j][1]();fill();}});
  window.scrollTo({top:0,behavior:'instant'});}
main.insertAdjacentHTML('beforeend','<div class="foot">'+D.tot.doms+' доменов · '+
  D.tot.t10+' ключей в ТОП-10 · '+D.tot.t3+' в ТОП-3 · '+D.tot.hs+' дорогих · '+
  D.tot.brands+' брендов · съёмы '+L.join(' и ')+' · ядро 1570 ключей, '+
  'ВЧ ≥ 1 млн, СЧ 700k–1 млн, бренды vovan и pari исключены</div>');
show(0);

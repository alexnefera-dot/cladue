const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), pc=(x)=>Math.round(x*100)+'%';
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':(v>=1e3?(v/1e3).toFixed(1).replace('.',',')+'k':Math.round(v)));
const ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"];
const T=(d)=>d.endsWith(".team");
const arrow=(a,b)=>b>a?'<span class="good">↑</span>':(b<a?'<span class="bad">↓</span>':'<span class="mut">=</span>');
const pos=(p)=>`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;

function agg(g,p){const ds=g.doms.filter(d=>p?p(d.d):true),n=ds.length;
  const S=(k)=>ds.reduce((a,d)=>a+d[k],0);
  return {n,a:S('t10a')/n,b:S('t10b')/n,t3:S('t3'),vch:S('vch'),sch:S('sch'),nch:S('nch'),
    up:ds.filter(d=>d.t10b>d.t10a).length,dn:ds.filter(d=>d.t10b<d.t10a).length,
    zero:ds.filter(d=>d.t10b===0).length,
    brands:new Set(ds.flatMap(d=>d.brands.map(b=>b.b))).size,
    hb:new Set(ds.flatMap(d=>d.brands.filter(b=>b.t!=='НЧ').map(b=>b.b))).size};}

/* ---------- обзор ---------- */
function tabAll(){
  let rows='';
  ORD.forEach(sn=>{const g=D.groups[sn],m=g.meta,s=agg(g),st=agg(g,T);
    rows+=`<tr><td class="l id">${m[0]}</td><td class="l mut">${m[1]}</td>
      <td class="l">${m[2]}</td><td>${s.n}</td>
      <td class="mut">${f1(s.a)}</td><td><b>${f1(s.b)}</b> ${arrow(s.a,s.b)}</td>
      <td>${f1(st.b)}</td><td>${s.t3}</td>
      <td class="${s.vch?'good':'mut'}">${s.vch}</td>
      <td class="${s.sch?'good':'mut'}">${s.sch}</td>
      <td class="mut">${s.nch}</td><td>${s.brands}</td>
      <td class="${s.hb?'good':'mut'}">${s.hb}</td>
      <td class="${s.zero===s.n?'bad':''}">${s.zero}/${s.n}</td></tr>`;});
  return `<div class="blk"><h2>Все шесть групп · только ТОП-10</h2>
  <p class="note">Т10/дом — ключей в ТОП-10 на домен. «.team» — то же по .team-подмножеству.
  «Пустых» — доменов без единого ключа в ТОП-10.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Лист</th>
  <th class="l">Конфигурация</th><th>Дом</th><th>Т10 з1</th><th>Т10 з2</th><th>.team</th>
  <th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>НЧ</th><th>Брендов</th><th>ВЧ/СЧ</th>
  <th>Пустых</th></tr></thead><tbody>${rows}</tbody></table></div></div>

  <div class="blk"><h2>Расслоение по ТОП-10</h2>
  <div class="cards">
    <div class="card ok"><h3>Generator_11page — весь ТОП-10 теста</h3>
      <p><span class="big">18 ВЧ</span> и <span class="big">13 СЧ</span> ключей.
      У пяти остальных групп вместе — 2 ВЧ и 1 СЧ.</p>
      <p>25 ключей в ТОП-3, 72 бренда, ни одного пустого домена.</p></div>
    <div class="card"><h3>7page_yandex — берёт, но пока мелочь</h3>
      <p>10 ключей в ТОП-3 и 46 брендов, однако из дорогих — только 2 ВЧ и 1 СЧ.
      Дорогие бренды по архиву приходят второй волной.</p></div>
    <div class="card err"><h3>Четыре группы без единого дорогого ключа</h3>
      <p>Generator_11page_2, Generator_v5, Generator_v4_2, generator v4 —
      <b>ноль ВЧ и ноль СЧ в ТОП-10</b> на 25 доменов.</p>
      <p>У generator v4 в ТОП-10 нет вообще ничего: 10 доменов, 0 ключей.</p></div>
  </div></div>`;
}

/* ---------- бренды ---------- */
function tabBrands(){
  const B=D.brands;
  const hi=B.filter(b=>b.t!=='НЧ');
  let rows=B.map((b,i)=>`<tr class="clk" data-b="${i}">
    <td class="l ${b.t!=='НЧ'?'id':''}">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
    <td><b>${b.n}</b></td><td>${pos(b.best)}</td>
    <td class="${b.t3?'good':'mut'}">${b.t3}</td><td>${b.nd}</td>
    <td class="l mut">${b.groups.join(', ')}</td>
    <td class="l mut">${Object.entries(b.cats).sort((x,y)=>y[1]-x[1]).map(([k,v])=>k+' ×'+v).join(', ')}</td>
  </tr><tr class="det" hidden><td colspan="9"><div class="inner"></div></td></tr>`).join('');
  return `<div class="blk"><h2>Какие ключи взял каждый бренд</h2>
  <p class="note">Все ${D.tot.t10} ключей в ТОП-10 на замере 2, сгруппированные по бренду.
  Клик по строке — конкретные запросы с позициями и доменами.</p>
  <div class="tiles">
    <div class="tile"><div class="k">Брендов в ТОП-10</div><div class="v">${B.length}</div>
      <div class="c">из 157 в справочнике</div></div>
    <div class="tile a"><div class="k">Ключей в ТОП-10</div><div class="v">${D.tot.t10}</div>
      <div class="c">из ${D.tot.ranked} ранжирующихся</div></div>
    <div class="tile g"><div class="k">В ТОП-3</div><div class="v">${D.tot.t3}</div>
      <div class="c">${pc(D.tot.t3/D.tot.t10)} от ТОП-10</div></div>
    <div class="tile"><div class="k">Дорогих брендов</div><div class="v">${hi.length}</div>
      <div class="c">ВЧ и СЧ, ${hi.reduce((a,b)=>a+b.n,0)} ключей</div></div>
  </div>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
  <th>Ключей Т10</th><th>Лучшая</th><th>ТОП-3</th><th>Доменов</th><th class="l">Группы</th>
  <th class="l">Типы запросов</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

/* ---------- типы запросов ---------- */
function tabCats(){
  const C=D.cats.filter(c=>c.all>0);
  const rows=C.map((c,i)=>`<tr class="clk" data-c="${i}">
    <td class="l ${c.t10>20?'id':''}">${esc(c.c)}</td>
    <td><b>${c.t10}</b></td><td>${pc(c.t10/D.tot.t10)}</td>
    <td class="${c.t3?'good':'mut'}">${c.t3}</td><td class="mut">${c.all}</td>
    <td class="${c.conv>=.18?'good':c.conv<=.08?'bad':''}"><b>${pc(c.conv)}</b></td>
  </tr><tr class="det" hidden><td colspan="6"><div class="inner"></div></td></tr>`).join('');
  const tierRow=(t)=>{const d=D.bytier[t];
    const e=Object.entries(d.cats).sort((a,b)=>b[1]-a[1]);
    return `<tr><td class="l">${tg(t)}</td><td><b>${d.n}</b></td>
      <td class="l">${e.map(([k,v])=>`${esc(k)} <b>×${v}</b>`).join(' · ')}</td></tr>`;};
  const grRow=(name)=>{const d=D.bygroup[name];
    const e=Object.entries(d.cats).sort((a,b)=>b[1]-a[1]);
    return `<tr><td class="l id">${esc(name)}</td><td><b>${d.n}</b></td>
      <td class="l">${d.n?e.map(([k,v])=>`${esc(k)} <b>×${v}</b>`).join(' · '):'<span class="mut">нет ключей в ТОП-10</span>'}</td></tr>`;};
  return `<div class="blk"><h2>Что за запросы вообще заходят</h2>
  <p class="note">Каждый ключ отнесён к одному типу по первому совпавшему признаку:
  зеркало → вход → регистрация → офиц. сайт → бонус → играть → приложение → отзывы →
  «бренд + казино» → «бренд без добавок». «Ранжируется» — ключ, по которому домен виден
  в выдаче хоть на какой позиции. Клик по строке — примеры.</p>
  <div class="tw"><table><thead><tr><th class="l">Тип запроса</th><th>В ТОП-10</th>
  <th>Доля Т10</th><th>ТОП-3</th><th>Ранжируется</th><th>Доходит до Т10</th>
  </tr></thead><tbody>${rows}</tbody></table></div></div>

  <div class="blk"><h2>Три вывода</h2>
  <div class="cards">
    <div class="card acc"><h3>«Бренд + казино» — основной паттерн</h3>
      <p><span class="big">57 %</span> всего ТОП-10 — 139 ключей из 243.</p>
      <p>Это запросы вида <span class="num">casino blitzred</span>,
      <span class="num">казино анлим</span>, <span class="num">онлибетс casino</span>.
      Слово «казино» рядом с брендом — самая частая форма, которую сайты берут.</p></div>
    <div class="card err"><h3>Голый бренд не берётся</h3>
      <p><span class="big">5 %</span> против 19 % у «бренд + казино».</p>
      <p>172 таких запроса ранжируются, в ТОП-10 доходят 9. По самому названию бренда
      выдачу держит сам бренд — туда не пробиться.</p></div>
    <div class="card ok"><h3>Зеркало конвертит лучше всех</h3>
      <p><span class="big">21 %</span> — выше, чем у любого другого типа.</p>
      <p>Плюс «регистрация» 19 %, «офиц. сайт» 18 %. Это транзакционные добавки,
      где официальный сайт бренда слабее.</p></div>
  </div></div>

  <div class="blk"><h2>Дорогие бренды берутся только двумя формами</h2>
  <p class="note">Разбивка ТОП-10 по тирам. У СЧ вообще нет ничего, кроме «бренд + казино»
  и «официальный сайт».</p>
  <div class="tw"><table><thead><tr><th class="l">Тир</th><th>Ключей Т10</th>
  <th class="l">Типы запросов</th></tr></thead><tbody>
  ${tierRow('ВЧ')}${tierRow('СЧ')}${tierRow('НЧ')}</tbody></table></div>
  <p class="note" style="margin-top:10px">У ВЧ 12 из 20 ключей — «бренд + казино»,
  ещё 3 — «официальный сайт». У СЧ это 11 и 3, и больше ничего.
  Зеркала, регистрации и входы работают почти только на НЧ-брендах.</p></div>

  <div class="blk"><h2>Типы запросов по группам</h2>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Ключей Т10</th>
  <th class="l">Типы запросов</th></tr></thead><tbody>
  ${ORD.map(sn=>grRow(D.groups[sn].meta[0])).join('')}</tbody></table></div>
  <p class="note" style="margin-top:10px">Профиль типов у Generator_11page и 7page_yandex
  примерно одинаковый — обе берут в основном «бренд + казино». Разница между группами
  в объёме, а не в том, какие запросы им поддаются.</p></div>`;
}

/* ---------- группа ---------- */
function tabG(sn){
  const g=D.groups[sn],m=g.meta,s=agg(g),st=agg(g,T);
  const V={
   "группа 3":{c:"ok",h:"Единственная группа с дорогими ключами в ТОП-10",
     p:["18 ВЧ и 13 СЧ ключей. У пяти остальных групп вместе — 2 ВЧ и 1 СЧ.",
        "25 ключей в ТОП-3, среди них onlybets на первом месте, volta на втором, vulkan mega на третьем.",
        "Из дорогих взяты flagman (2,0M) на 5-й позиции, leebet (1,0M) на 5-й, sweet (1,2M) на 6-й, kent (8,0M) на 7-й, motor (3,8M) на 10-й.",
        "Ни одного пустого домена. Но 2 из 5 просели по общему охвату — весь прирост дают 1085.team и bdwn.team."],
     v:"Ведёт тест с большим отрывом. Оговорка прежняя: это одна партия из пяти доменов, а её же формат во второй партии дал ноль дорогих ключей."},
   "группа 1":{c:"ok",h:"Берёт широко, но пока мелкие бренды",
     p:["10 ключей в ТОП-3 и 46 брендов — второй результат теста.",
        "Дорогих всего 3 ключа: 2 ВЧ и 1 СЧ. Основная масса — НЧ-бренды.",
        "По .team против generator v4 разрыв кратный при точно совпадающих зонах и съёмах в одну минуту. Это самое чистое сравнение теста.",
        "Три домена в экзотических зонах (.quest, .bond, .buzz) не взяли в ТОП-10 ничего."],
     v:"Контент из выдачи работает. По архиву дорогие бренды приходят второй волной, так что 3 дорогих ключа на замере 2 — это не потолок."},
   "группа 4":{c:"",h:"Ноль дорогих ключей при том же формате, что у лидера",
     p:["Ни одного ВЧ или СЧ ключа в ТОП-10 на пять доменов.",
        "Есть охват по НЧ и 2 ключа в ТОП-3, но дорогие бренды не тронуты вообще.",
        "Возраст как объяснение отпадает: на замере 2 партия старше, чем Generator_11page была на замере 1, и всё равно пустая по дорогим."],
     v:"Разрыв с Generator_11page даёт партия контента, а не формат. Значит объём страниц этим тестом не измеряется."},
   "группа 5":{c:"",h:"Ноль дорогих ключей",
     p:["ВЧ и СЧ в ТОП-10 нет. 3 ключа в ТОП-3, все по НЧ-брендам.",
        "Версия v5 и шаблон Theme2 не дали ничего, что отличало бы группу от Generator_v4_2."],
     v:"В полосе, которую архив относит к провальной. Различать v5 и v4_2 не на чем."},
   "группа 6":{c:"",h:"Ноль дорогих ключей, но ни один домен не просел",
     p:["ВЧ и СЧ в ТОП-10 нет. 2 ключа в ТОП-3.",
        "Единственная группа, где по ТОП-10 не откатился ни один домен."],
     v:"Отличие от Generator_v5 в пределах шума. Пара v5/Theme2 против v4_2/Theme1 не разделила ни версию, ни шаблон."},
   "группа 2":{c:"err",h:"В ТОП-10 нет ничего",
     p:["Десять доменов, <b>ноль ключей в ТОП-10</b> на всю группу. Ни одного бренда, ни одного ключа в ТОП-3.",
        "На замере 1 в ТОП-10 тоже было пусто. По общему охвату группа просела: 1,5 → 0,5 ключа в ТОП-30 на домен.",
        "Домены в экзотических зонах — im8tq.icu, dwb7.top, 1908xc.buzz — не взяли вообще ничего ни на одном замере."],
     v:"Архивное правило «просел после пика» даёт медиану финала 0 и результат лишь у 11 % доменов. Списывать."}
  }[sn];
  const rows=g.doms.map((d,i)=>`<tr class="clk" data-sn="${sn}" data-i="${i}">
    <td class="l ${T(d.d)?'id':'mut'}">${esc(d.d)}</td>
    <td class="mut">${d.t10a}</td><td><b>${d.t10b}</b> ${arrow(d.t10a,d.t10b)}</td>
    <td class="${d.t3?'good':'mut'}">${d.t3}</td>
    <td class="${d.vch?'good':'mut'}">${d.vch}</td>
    <td class="${d.sch?'good':'mut'}">${d.sch}</td>
    <td class="mut">${d.nch}</td><td>${d.brands.length}</td><td class="mut">${d.t30}</td></tr>
    <tr class="det" hidden><td colspan="9"><div class="inner"></div></td></tr>`).join('');
  return `<div class="blk"><h2>${esc(m[0])}</h2>
  <p class="note">${esc(m[2])} · версия ${esc(m[3])} · шаблон ${esc(m[4])} ·
  лист «${esc(sn)}» · замеры ${g.labels.join(' и ')}</p>
  <div class="tiles">
    <div class="tile"><div class="k">Доменов</div><div class="v">${s.n}</div>
      <div class="c">${st.n} в зоне .team</div></div>
    <div class="tile a"><div class="k">Т10 на домен</div><div class="v">${f1(s.b)}</div>
      <div class="c">было ${f1(s.a)} на замере 1</div></div>
    <div class="tile ${s.vch+s.sch?'g':'b'}"><div class="k">ВЧ+СЧ в ТОП-10</div>
      <div class="v">${s.vch+s.sch}</div><div class="c">${s.vch} ВЧ · ${s.sch} СЧ</div></div>
    <div class="tile ${s.t3?'g':''}"><div class="k">Ключей в ТОП-3</div><div class="v">${s.t3}</div>
      <div class="c">из ${s.vch+s.sch+s.nch} в ТОП-10</div></div>
    <div class="tile"><div class="k">Брендов</div><div class="v">${s.brands}</div>
      <div class="c">${s.hb} дорогих</div></div>
    <div class="tile ${s.zero===s.n?'b':''}"><div class="k">Пустых доменов</div>
      <div class="v">${s.zero}/${s.n}</div><div class="c">без ключей в ТОП-10</div></div>
  </div>
  <div class="card ${V.c}"><h3>${V.h}</h3>${V.p.map(x=>`<p>${x}</p>`).join('')}
    <p style="margin-top:12px;color:var(--tx)"><b>Вывод.</b> ${V.v}</p></div></div>

  <div class="blk"><h2>Домены</h2>
  <p class="note">Клик по строке — бренды и конкретные ключи домена в ТОП-10.
  Колонка Т30 дана справочно, для сопоставления с прежним отчётом.</p>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т10 з1</th><th>Т10 з2</th>
  <th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>НЧ</th><th>Брендов</th><th>Т30</th>
  </tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function fill(){
  document.querySelectorAll('tr.clk[data-sn]').forEach(tr=>{
    tr.onclick=()=>{
      const det=tr.nextElementSibling; det.hidden=!det.hidden;
      const slot=det.querySelector('.inner');
      if(det.hidden||slot.dataset.done) return;
      slot.dataset.done=1;
      const d=D.groups[tr.dataset.sn].doms[+tr.dataset.i];
      if(!d.keys.length){slot.innerHTML='<h4>Ни одного ключа в ТОП-10</h4>';return;}
      slot.innerHTML=`<div><h4>Бренды в ТОП-10 — ${d.brands.length}</h4><div class="tw"><table>
        <thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th><th>Лучшая</th>
        <th>Ключей</th><th>ТОП-3</th><th class="l">Типы запросов</th></tr></thead><tbody>`+
        d.brands.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
          <td>${pos(b.best)}</td><td>${b.n}</td>
          <td class="${b.t3?'good':'mut'}">${b.t3}</td>
          <td class="l mut">${Object.entries(b.cats).sort((x,y)=>y[1]-x[1]).map(([k,v])=>k+' ×'+v).join(', ')}</td>
        </tr>`).join('')+`</tbody></table></div></div>
        <div><h4>Ключи в ТОП-10 — ${d.keys.length}</h4><div class="tw"><table>
        <thead><tr><th class="l">Ключ</th><th class="l">Бренд</th><th class="l">Тип</th>
        <th>Тир</th><th>Объём</th><th>Замер 1</th><th>Замер 2</th></tr></thead><tbody>`+
        d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
          <td class="l mut">${esc(k.c)}</td><td>${tg(k.t)}</td><td>${kf(k.v)}</td>
          <td class="mut">${k.p1===null?'—':k.p1}</td><td>${pos(k.p2)}</td></tr>`).join('')+
        `</tbody></table></div></div>`;
    };
  });
  document.querySelectorAll('tr.clk[data-b]').forEach(tr=>{
    tr.onclick=()=>{
      const det=tr.nextElementSibling; det.hidden=!det.hidden;
      const slot=det.querySelector('.inner');
      if(det.hidden||slot.dataset.done) return;
      slot.dataset.done=1;
      const b=D.brands[+tr.dataset.b];
      slot.innerHTML=`<div><h4>${esc(b.b)} — ${b.n} ключей в ТОП-10</h4><div class="tw"><table>
        <thead><tr><th class="l">Ключ</th><th class="l">Тип запроса</th><th>Замер 1</th>
        <th>Замер 2</th><th class="l">Домен</th><th class="l">Группа</th></tr></thead><tbody>`+
        b.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.c)}</td>
          <td class="mut">${k.p1===null?'—':k.p1}</td><td>${pos(k.p)}</td>
          <td class="l num">${esc(k.d)}</td><td class="l mut">${esc(k.g)}</td></tr>`).join('')+
        `</tbody></table></div></div>`;
    };
  });
  document.querySelectorAll('tr.clk[data-c]').forEach(tr=>{
    tr.onclick=()=>{
      const det=tr.nextElementSibling; det.hidden=!det.hidden;
      const slot=det.querySelector('.inner');
      if(det.hidden||slot.dataset.done) return;
      slot.dataset.done=1;
      const c=D.cats[+tr.dataset.c];
      if(!c.ex.length){slot.innerHTML='<h4>Ни одного ключа этого типа в ТОП-10</h4>';return;}
      slot.innerHTML=`<div><h4>Примеры — «${esc(c.c)}»</h4><div class="tw"><table>
        <thead><tr><th class="l">Ключ</th><th class="l">Бренд</th><th>Позиция</th>
        </tr></thead><tbody>`+
        c.ex.map(e=>`<tr><td class="l">${esc(e.q)}</td><td class="l mut">${esc(e.b)}</td>
          <td>${pos(e.p)}</td></tr>`).join('')+`</tbody></table></div></div>`;
    };
  });
}

const TABS=[["Обзор",tabAll],["Бренды и ключи",tabBrands],["Типы запросов",tabCats]]
  .concat(ORD.map(sn=>[D.groups[sn].meta[0],()=>tabG(sn)]));
const nav=document.getElementById('nav'), main=document.getElementById('main');
TABS.forEach(([name],i)=>{
  const b=document.createElement('button');
  b.textContent=name; b.setAttribute('role','tab'); b.setAttribute('aria-selected',i===0);
  b.onclick=()=>show(i); nav.appendChild(b);
  const s=document.createElement('section'); s.hidden=i!==0; main.appendChild(s);
});
function show(i){
  [...nav.children].forEach((b,j)=>b.setAttribute('aria-selected',i===j));
  [...main.children].forEach((s,j)=>{
    s.hidden=i!==j;
    if(i===j&&!s.dataset.done){s.dataset.done=1;s.innerHTML=TABS[j][1]();fill();}
  });
  window.scrollTo({top:0,behavior:'instant'});
}
main.insertAdjacentHTML('beforeend','<div class="foot">Запуск 20.08.2026 · '+
  'замер 1 в 01:29–01:41, замер 2 в 10:08–10:09 · 40 доменов, 6 групп · '+
  'всё считано по ТОП-10 · ядро 1570 ключей, ВЧ ≥ 1 млн, СЧ 700k–1 млн, '+
  'бренды vovan и pari исключены</div>');
show(0);

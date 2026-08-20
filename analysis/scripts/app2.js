const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), pc=(x)=>Math.round(x*100)+'%';
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':(v>=1e3?(v/1e3).toFixed(1).replace('.',',')+'k':Math.round(v)));
const ORD=["группа 3","группа 1","группа 4","группа 5","группа 6","группа 2"];
const T=(d)=>d.endsWith(".team");
const pill=(v,hi,lo)=>`<span class="pill ${v>=hi?'p-ok':v<=lo?'p-no':'p-mid'}">${pc(v)}</span>`;
const arrow=(a,b)=>b>a?'<span class="good">↑</span>':(b<a?'<span class="bad">↓</span>':'<span class="mut">=</span>');

function agg(g,p){const ds=g.doms.filter(d=>p?p(d.d):true),n=ds.length;
  const S=(k)=>ds.reduce((a,d)=>a+d[k],0);
  return {n,a:S('t30a')/n,b:S('t30b')/n,t100:S('t100b')/n,vch:S('vch10'),sch:S('sch10'),
    t3:S('t3'),t10:S('t10'),
    up:ds.filter(d=>d.t30b>d.t30a).length,dn:ds.filter(d=>d.t30b<d.t30a).length,
    kill:ds.filter(d=>d.t30b<=2).length,
    brands:new Set(ds.flatMap(d=>d.brands.map(b=>b.b))).size,
    hb:new Set(ds.flatMap(d=>d.brands.filter(b=>b.t!=='НЧ').map(b=>b.b)))};}

/* ---------- обзор ---------- */
function tabAll(){
  let rows='';
  ORD.forEach(sn=>{const g=D[sn],m=g.meta,s=agg(g),st=agg(g,T);
    rows+=`<tr><td class="l id">${m[0]}</td><td class="l mut">${m[1]}</td>
      <td class="l">${m[2]}</td><td>${s.n}</td>
      <td class="mut">${f1(s.a)}</td><td><b>${f1(s.b)}</b> ${arrow(s.a,s.b)}</td>
      <td>${f1(st.b)}</td>
      <td class="${s.vch?'good':'mut'}">${s.vch}</td>
      <td class="${s.sch?'good':'mut'}">${s.sch}</td>
      <td>${s.t3}</td><td>${s.brands}</td>
      <td class="${s.hb.size?'good':'mut'}">${s.hb.size}</td>
      <td class="${s.kill===s.n?'bad':''}">${s.kill}/${s.n}</td></tr>`;});
  return `<div class="blk"><h2>Все шесть групп на замере 2</h2>
  <p class="note">Т30/дом — ключей в ТОП-30 на домен. «.team» — то же по .team-подмножеству,
  так зоны не искажают сравнение. «Под отсев» — доменов с ≤2 ключами в Т30:
  по архиву 89 % из них остаются в нуле.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Лист</th>
  <th class="l">Конфигурация</th><th>Дом</th><th>Т30 з1</th><th>Т30 з2</th><th>.team</th>
  <th>ВЧ Т10</th><th>СЧ Т10</th><th>Т3</th><th>Брендов</th><th>ВЧ/СЧ брендов</th>
  <th>Под отсев</th></tr></thead><tbody>${rows}</tbody></table></div></div>

  <div class="blk"><h2>Расслоение произошло</h2>
  <div class="cards">
    <div class="card ok"><h3>Две группы работают</h3>
      <p><b>Generator_11page</b> — 54,0 Т30/дом, 18 ВЧ и 13 СЧ в ТОП-10, 18 дорогих брендов.
      Единственная, кто вышел на ВЧ.</p>
      <p><b>7page_yandex</b> — 21,7 по .team, 8 дорогих брендов, но ВЧ пока только 2 ключа.</p></div>
    <div class="card"><h3>Три держатся на нуле</h3>
      <p><b>Generator_11page_2</b> (9,0), <b>Generator_v5</b> (3,4), <b>Generator_v4_2</b> (3,0).
      Растут, но ни одного ВЧ или СЧ ключа в ТОП-10 на всю тройку.</p>
      <p>По архиву запуски с таким Т30 на первых замерах заканчивались провалом
      в 6 случаях из 6.</p></div>
    <div class="card err"><h3>Одна умерла</h3>
      <p><b>generator v4</b> — 1,5 → 0,5. Все 10 доменов под отсев, 6 просели,
      4 бренда в Т30 на всю группу, ни одного ключа в ТОП-3.</p>
      <p>Единственная группа с отрицательной динамикой.</p></div>
  </div></div>

  <div class="blk"><h2>Что это значит для теста</h2>
  <ul class="cl">
    <li><b>Источник контента — единственный подтверждённый фактор.</b> 7page_yandex против
      generator v4 по .team: 21,7 против 0,7. Зоны у групп совпадают точно, съёмы в одну минуту —
      поправок не нужно. Разрыв вырос с 6,5 раза на замере 1 до 31 раза.</li>
    <li><b>Объём страниц не измерен.</b> Generator_11page (54,0) и Generator_11page_2 (11,2) —
      один формат, одна зона, разброс в 5 раз. Возраст исключён: на замере 2 вторая партия
      старше, чем первая была на замере 1, и всё равно ниже.</li>
    <li><b>Версия и шаблон без сигнала.</b> v5 — 3,4, v4_2 — 3,2, v4 — 0,7. Все три в полосе,
      которую архив относит к провальной, различать там нечего.</li>
    <li><b>Дорогие бренды пошли только у одной группы.</b> 31 ВЧ+СЧ ключ в ТОП-10 у
      Generator_11page против 3 у 7page_yandex и нуля у всех остальных.</li>
  </ul></div>`;
}

/* ---------- группа ---------- */
function tabG(sn){
  const g=D[sn],m=g.meta,s=agg(g),st=agg(g,T);
  const V={
   "группа 3":{c:"ok",h:"Единственная группа, вышедшая на дорогие бренды",
     p:["18 ВЧ и 13 СЧ ключей в ТОП-10, 25 ключей в ТОП-3, 18 дорогих брендов из 72. У остальных пяти групп вместе — 3 ВЧ+СЧ ключа.",
        "Уровень 48,8 на замере 1 выше любого запуска архива на той же стадии: рекордом было 28,6 у D252, который дошёл до 4,68.",
        "Настораживает: 2 домена из 5 просели (gkrd 35→29, mpdg 29→23). Весь прирост группы дают 1085.team (59→87) и bdwn.team (76→78)."],
     v:"Ведёт тест с большим отрывом. Но это одна партия из пяти доменов, и её же формат во второй партии дал в 5 раз меньше."},
   "группа 1":{c:"ok",h:"Вторая по силе, и самое надёжное сравнение теста",
     p:["По .team 21,7 Т30/дом против 0,7 у generator v4 — разрыв в 31 раз при точно совпадающем составе зон и съёмах в одну минуту. Поправок не требуется.",
        "Дорогих брендов 8, но ВЧ в ТОП-10 пока только 2 ключа. По архиву это норма второго замера: дорогие бренды приходят второй волной.",
        "Внутри группы резкое расслоение: 2691.team вырос 33→67, hlwm.team упал 20→5. Все три домена под отсев — экзотические зоны."],
     v:"Контент из выдачи работает. Главный результат теста на сегодня, и он получен на самом чистом сравнении."},
   "группа 4":{c:"",h:"Тот же формат, что у лидера, результат в 5 раз ниже",
     p:["Растёт быстрее всех в относительном выражении: 4,0 → 9,0, то есть больше чем вдвое. Но стартовала почти с нуля.",
        "22 бренда в Т30 и ни одного ВЧ или СЧ. Ни одного ключа в ТОП-10 по дорогим брендам.",
        "Возраст как объяснение отпадает: на замере 2 эта партия старше (≈11,5 ч), чем Generator_11page была на замере 1 (≈8,6 ч), и всё равно ниже в 5,4 раза."],
     v:"Живая, но пустая по дорогим брендам. Разрыв с Generator_11page даёт партия контента, а не формат — значит объём страниц этим тестом не измеряется."},
   "группа 5":{c:"",h:"В полосе, которую архив относит к провальной",
     p:["3,4 Т30/дом по .team. Провальные запуски архива имели 3,0–8,4 уже на первом замере, успешные — 12,8–28,6.",
        "Ноль ВЧ и СЧ в ТОП-10, 10 брендов в Т30 на всю группу, все низкочастотные.",
        "3 домена из 5 под отсев. Динамика формально положительная (3 растут, 1 просел), но с уровня, который ни к чему не ведёт."],
     v:"Версия v5 и шаблон Theme2 не дали ничего, что отличало бы группу от v4_2. Различать нечего — обе в одной полосе."},
   "группа 6":{c:"",h:"Чуть живее по динамике, тот же уровень по существу",
     p:["Единственная группа, где не просел ни один домен. 3 растут, 2 стоят.",
        "Два дорогих бренда в Т30 — clubnika и laki, оба вне ТОП-10. У Generator_v5 и таких нет.",
        "Но уровень тот же: 3,2 Т30/дом по .team против 3,4 у Generator_v5. 3 домена из 5 под отсев."],
     v:"Отличие от Generator_v5 в пределах шума. Пара v5/Theme2 против v4_2/Theme1 не разделила ни версию, ни шаблон."},
   "группа 2":{c:"err",h:"Списывать",
     p:["Единственная группа с отрицательной динамикой: 1,5 → 0,5. Шесть доменов просели, вырос один.",
        "Все 10 доменов под отсев. По архиву ≤2 ключа в Т30 на замере 2 означает, что 89 % останутся в нуле.",
        "4 бренда в Т30 на всю группу из десяти доменов, ни одного ключа в ТОП-3, ни одного дорогого бренда.",
        "Домены в экзотических зонах — im8tq.icu, dwb7.top, 1908xc.buzz — не взяли вообще ничего ни на одном замере."],
     v:"Архивное правило «просел после пика» даёт медиану финала 0 и результат лишь у 11 % доменов. Ждать здесь нечего."}
  }[sn];
  let rows='';
  g.doms.forEach((d,i)=>{
    rows+=`<tr class="clk" data-sn="${sn}" data-i="${i}">
      <td class="l ${T(d.d)?'id':'mut'}">${esc(d.d)}</td>
      <td class="mut">${d.t30a}</td><td><b>${d.t30b}</b> ${arrow(d.t30a,d.t30b)}</td>
      <td>${d.t100b}</td><td>${d.t3}</td><td>${d.t10}</td>
      <td class="${d.vch10?'good':'mut'}">${d.vch10}</td>
      <td class="${d.sch10?'good':'mut'}">${d.sch10}</td>
      <td class="mut">${d.nch10}</td><td>${d.brands.length}</td>
      <td class="${d.t30b<=2?'bad':''}">${d.t30b<=2?'да':'—'}</td></tr>
      <tr class="det" hidden><td colspan="11"><div class="inner"></div></td></tr>`;});
  return `<div class="blk"><h2>${esc(m[0])}</h2>
  <p class="note">${esc(m[2])} · версия ${esc(m[3])} · шаблон ${esc(m[4])} ·
  лист выгрузки «${esc(sn)}» · замеры ${g.labels.join(' и ')}</p>
  <div class="tiles">
    <div class="tile"><div class="k">Доменов</div><div class="v">${s.n}</div>
      <div class="c">${st.n} в зоне .team</div></div>
    <div class="tile a"><div class="k">Т30 на домен</div><div class="v">${f1(s.b)}</div>
      <div class="c">было ${f1(s.a)} на замере 1</div></div>
    <div class="tile ${s.vch+s.sch?'g':'b'}"><div class="k">ВЧ+СЧ в ТОП-10</div>
      <div class="v">${s.vch+s.sch}</div><div class="c">${s.vch} ВЧ · ${s.sch} СЧ</div></div>
    <div class="tile"><div class="k">Брендов в Т30</div><div class="v">${s.brands}</div>
      <div class="c">${s.hb.size} дорогих</div></div>
    <div class="tile"><div class="k">Растёт</div><div class="v">${s.up}/${s.n}</div>
      <div class="c">просело ${s.dn}</div></div>
    <div class="tile ${s.kill===s.n?'b':''}"><div class="k">Под отсев</div>
      <div class="v">${s.kill}/${s.n}</div><div class="c">≤2 ключа в Т30</div></div>
  </div>
  <div class="card ${V.c}"><h3>${V.h}</h3>${V.p.map(x=>`<p>${x}</p>`).join('')}
    <p style="margin-top:12px;color:var(--tx)"><b>Вывод.</b> ${V.v}</p></div></div>

  <div class="blk"><h2>Домены</h2>
  <p class="note">Клик по строке — бренды и ключи домена. Т30 показан на обоих замерах,
  остальные колонки — на замере 2.</p>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т30 з1</th><th>Т30 з2</th>
  <th>Т100</th><th>ТОП-3</th><th>ТОП-10</th><th>ВЧ Т10</th><th>СЧ Т10</th><th>НЧ Т10</th>
  <th>Брендов</th><th>Отсев</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function fill(){
  document.querySelectorAll('tr.clk[data-sn]').forEach(tr=>{
    tr.onclick=()=>{
      const det=tr.nextElementSibling; det.hidden=!det.hidden;
      const slot=det.querySelector('.inner');
      if(det.hidden||slot.dataset.done) return;
      slot.dataset.done=1;
      const d=D[tr.dataset.sn].doms[+tr.dataset.i];
      let h='';
      if(d.brands.length){
        h+=`<div><h4>Бренды в ТОП-30 — ${d.brands.length}</h4><div class="tw"><table><thead><tr>
          <th class="l">Бренд</th><th>Объём</th><th>Тир</th><th>Лучшая</th><th>Ключей Т30</th>
          <th>Т10</th><th>Т3</th></tr></thead><tbody>`+
          d.brands.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td>
            <td><span class="tag t-${b.t}">${b.t}</span></td>
            <td class="${b.best<=3?'good':b.best<=10?'':'mut'}"><b>${b.best}</b></td>
            <td>${b.n}</td><td class="${b.t10?'good':'mut'}">${b.t10}</td>
            <td class="${b.t3?'good':'mut'}">${b.t3}</td></tr>`).join('')+
          `</tbody></table></div></div>`;
      } else h+='<div><h4>Ни одного бренда в ТОП-30</h4></div>';
      if(d.keys.length){
        h+=`<div><h4>Ключи в ТОП-50 — ${d.keys.length} из ${d.nkeys} ранжирующихся</h4>
          <div class="tw"><table><thead><tr><th class="l">Ключ</th><th class="l">Бренд</th>
          <th>Тир</th><th>Объём</th><th>Замер 1</th><th>Замер 2</th></tr></thead><tbody>`+
          d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
            <td><span class="tag t-${k.t}">${k.t}</span></td><td>${kf(k.v)}</td>
            <td class="mut">${k.p1===null?'—':k.p1}</td>
            <td class="${k.p2===null?'bad':k.p2<=3?'good':k.p2<=10?'':'mut'}">
              <b>${k.p2===null?'ушёл':k.p2}</b></td></tr>`).join('')+
          `</tbody></table></div></div>`;
      }
      slot.innerHTML=h;
    };
  });
}

const TABS=[["Обзор",tabAll]].concat(ORD.map(sn=>[D[sn].meta[0],()=>tabG(sn)]));
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
  'ядро 1570 ключей, ВЧ ≥ 1 млн, СЧ 700k–1 млн, бренды vovan и pari исключены</div>');
show(0);

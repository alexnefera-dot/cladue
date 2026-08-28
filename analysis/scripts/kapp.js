const N=x=>Number(x).toLocaleString('ru-RU');
const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const sg=x=>x>0?'+'+x:''+x;
const dcls=x=>x<0?'good':(x>0?'bad':'mut');
const tg=t=>t?`<span class="tr tr-${t}">${t}</span>`:'';
const T=D.tot;

/* ---------- ограничение ---------- */
const secC=`<div class="blk">
 <h2>Ограничение вложенности: что показал последний съём</h2>
 <p class="note">Сравниваю позицию каждого ключа на съёме <b>${E(D.last)}</b> с предыдущим
 <b>${E(D.prev)}</b>. Ключ попадает в строку «адрес сменился», если Яндекс на этих двух съёмах
 показал по нему <i>разные</i> адреса — с разным числом повторов <code>/ru</code>.
 Зелёное — вверх, красное — вниз.</p>
 <div class="tiles">
   ${D.cmp.map(c=>`<div class="tile ${c.ch.med<0?'g':'b'}">
     <div class="k">${E(c.k)} · адрес сменился</div>
     <div class="v">${sg(c.ch.med)}</div>
     <div class="c">${c.ch.n} ключей · ${c.ch.up} вверх, ${c.ch.dn} вниз</div></div>
    <div class="tile ${c.sm.med<0?'g':'b'}">
     <div class="k">${E(c.k)} · адрес тот же</div>
     <div class="v">${sg(c.sm.med)}</div>
     <div class="c">${c.sm.n} ключей · ${c.sm.up} вверх, ${c.sm.dn} вниз</div></div>`).join('')}
 </div>
 <div class="grid2">
  <div class="card warn-c"><h3>Ограничение картину не меняет</h3>
  <p>На <b>ограниченном пуле</b> ключи со сменившимся адресом ушли вверх на 18 позиций,
  ключи с прежним адресом просели на 24. На <b>неограниченном</b> — вверх на 10 и вниз на 6.
  Направление одно и то же.</p>
  <p>Разница между пулами в другом: на ограниченном адрес сменился у <b>8 ключей из 38</b>
  (21 %), на неограниченном — у <b>57 из 104</b> (55 %). Там, где путь может расти
  бесконечно, Яндекс переключает адрес втрое чаще.</p>
  <p class="verd">Значит рост позиции связан не с глубиной адреса, а с тем,
  что Яндекс переобошёл страницу и сменил ранжирующий адрес. Ограничение до 20
  этому не мешает — просто переключений становится меньше.</p></div>
  <div class="card"><h3>Что считаем ограниченным пулом</h3>
  <p>По данным съёма ограничение стоит на двух группах 27 августа:
  <code>7page партия 1</code> (id 1004-1013) и <code>Generator_11page_old</code>
  (id 1014-1023) — у всех 20 доменов максимум ровно <b>20</b> повторов, ни одного адреса выше.</p>
  <p>Неограниченная — <code>7page партия 2</code>: 11 доменов, максимум доходит до
  <b>50</b> повторов, у <code>1893.team</code> выше двадцати уже 171 адрес из 229.</p>
  </div>
 </div>
 ${D.cmp.map(c=>`<h3 class="vt" style="margin-top:20px">${E(c.k)} — все ключи, у которых сменился адрес</h3>
  <p class="note">${E(c.sub)}</p>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th class="l">Запрос</th>
   <th class="l">Домен</th><th>Было</th><th>Стало</th><th>Δ</th><th>/ru было</th><th>/ru стало</th>
   </tr></thead><tbody>
   ${c.items.map(x=>`<tr><td class="l"><b class="dm">${E(x.b)}</b> ${tg(x.t)}</td>
     <td class="l sm">${E(x.q)}</td><td class="l mono sm">${E(x.dom)}</td>
     <td class="mut">${x.p0}</td><td class="${x.p1<=10?'good':''}"><b>${x.p1}</b></td>
     <td class="${dcls(x.p1-x.p0)}"><b>${sg(x.p1-x.p0)}</b></td>
     <td class="mut">${x.d0}</td><td>${x.d1}</td></tr>`).join('')}
  </tbody></table></div>`).join('')}
</div>`;

/* ---------- бренды ---------- */
const secB=`<div class="blk">
 <h2>Бренды: где мы стоим на ${E(D.last)}</h2>
 <p class="note">${T.brands} брендов, ${N(T.rows)} строк «ключ × домен» за два последних съёма.
 Сейчас в выдаче ${N(T.now)} строк: ${T.new} появились с прошлого съёма, ${T.gone} выпали.
 Колонки «ограниченный» и «свободный» показывают лучшую позицию бренда отдельно
 в пуле с потолком 20 и в пуле без потолка. Строка раскрывается до всех ключей.</p>
 <div class="tw"><table class="big"><thead><tr>
   <th class="l">Бренд</th><th>Частотность</th><th>В десятке</th><th>В тройке</th>
   <th>Ключей сейчас</th><th>Пришло</th><th>Выпало</th><th>Медиана Δ</th>
   <th>Лучшая</th><th class="l">Держит</th><th>Огранич.</th><th>Свободный</th>
   </tr></thead><tbody>
   ${D.br.filter(b=>b.now).map(b=>`<tr class="clk">
     <td class="l"><b class="dm">${E(b.b)}</b> ${tg(b.t)}</td>
     <td class="mono sm">${b.vol?N(b.vol):'—'}</td>
     <td class="${b.t10>=5?'good':(b.t10?'':'mut')}"><b>${b.t10||'—'}</b></td>
     <td class="${b.t3?'good':'mut'}">${b.t3||'—'}</td>
     <td>${b.now}</td><td class="${b.new?'good':'mut'}">${b.new||'—'}</td>
     <td class="${b.gone?'bad':'mut'}">${b.gone||'—'}</td>
     <td class="${b.med==null?'mut':dcls(b.med)}">${b.med==null?'—':sg(b.med)}</td>
     <td class="${b.best<=10?'good':''}"><b>${b.best??'—'}</b></td>
     <td class="l mono sm">${E(b.bdom||'—')}</td>
     <td class="${b.capbest!=null&&b.capbest<=10?'good':'mut'}">${b.capbest??'—'}</td>
     <td class="${b.uncbest!=null&&b.uncbest<=10?'good':'mut'}">${b.uncbest??'—'}</td>
   </tr><tr class="det" hidden><td colspan="12"><div class="inner">
     <h4>${E(b.b)} — все ключи по этому бренду</h4>
     <div class="tw"><table><thead><tr><th class="l">Запрос</th><th class="l">Домен</th>
      <th class="l">Пул</th><th>Потолок</th><th>Было</th><th>Стало</th><th>Δ</th>
      <th>/ru было</th><th>/ru стало</th><th class="l">Адрес сейчас</th></tr></thead><tbody>
      ${b.keys.map(k=>`<tr>
        <td class="l sm">${E(k.q)}</td><td class="l mono sm">${E(k.dom)}</td>
        <td class="l sm">${E(k.grp)}</td>
        <td class="sm ${k.cap?'':'warn'}">${k.cap?'≤20':'нет'}</td>
        <td class="mut">${k.p0??'—'}</td>
        <td class="${k.p1==null?'bad':(k.p1<=10?'good':'')}"><b>${k.p1??'выпал'}</b></td>
        <td class="${k.p0&&k.p1?dcls(k.p1-k.p0):'mut'}">${k.p0&&k.p1?sg(k.p1-k.p0):'—'}</td>
        <td class="mut">${k.d0??'—'}</td>
        <td class="${k.d1!=null&&k.d0!=null&&k.d1!==k.d0?'now':''}">${k.d1??'—'}</td>
        <td class="l sm mono"><span class="url">${E((k.u||'—').replace('https://',''))}</span></td>
      </tr>`).join('')}
     </tbody></table></div>
   </div></td></tr>`).join('')}
 </tbody></table></div>
</div>`;

/* ---------- партии ---------- */
const A=D.arms, A1=A[0], A2=A[1], A3=A[2];
const allb=[...new Set(A.flatMap(a=>Object.keys(a.brands)))]
  .sort((x,y)=>Math.min(...A.map(a=>a.brands[x]?a.brands[x][0]:999))-Math.min(...A.map(a=>a.brands[y]?a.brands[y][0]:999)));
const secA=`<div class="blk">
 <h2>Две партии 7page: один формат, один вечер, разный результат</h2>
 <p class="note">Обе выложены 27 августа, обе — семистраничный контент. Разного в них два:
 набор текстов и потолок вложенности. У <b>партии 1</b> адреса обрезаны на 20 повторах
 <code>/ru</code>, у <b>партии 2</b> потолка нет. Третьей строкой — <b>Generator_11page_old</b>
 того же вечера, тоже с потолком 20: он нужен, чтобы отличить влияние потолка от влияния текстов.</p>
 <div class="tiles">
  ${A.map(a=>`<div class="tile ${a.nm.includes('партия 2')?'g':'b'}">
    <div class="k">${E(a.nm)}</div>
    <div class="v">${a.snaps[3].t10}</div>
    <div class="c">запросов в десятке · ${a.n} доменов · ${a.cap?'потолок 20':'без потолка'}</div></div>`).join('')}
  <div class="tile a"><div class="k">Разрыв партия 2 / партия 1</div>
    <div class="v">20×</div><div class="c">без домена-лидера всё равно 17×</div></div>
 </div>
 <h3 class="vt">Как расходились по съёмам</h3>
 <p class="note">Первые три съёма партии шли вровень. Разрыв открылся на четвёртом —
 между полуночью и обедом 28 августа.</p>
 <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Что это</th><th>Потолок</th><th>Дом.</th>
  ${D.labs.map(l=>`<th>${E(l)}</th>`).join('')}
  <th>Т3</th><th>Т30</th><th>Т100</th><th>Т10 на домен</th><th>Без лидера</th><th>Брендов в Т10</th>
  <th>/ru макс</th><th>/ru медиана</th></tr></thead><tbody>
  ${A.map(a=>`<tr><td class="l"><b>${E(a.nm)}</b></td><td class="l sm" style="min-width:190px">${E(a.cfg)}</td>
   <td class="sm ${a.cap?'':'warn'}">${a.cap?'≤20':'нет'}</td><td>${a.n}</td>
   ${a.snaps.map((s,i)=>`<td class="${i===3?(s.t10>=100?'good':'mut'):''}"><b>${s?s.t10:'—'}</b></td>`).join('')}
   <td>${a.snaps[3].t3}</td><td>${a.snaps[3].t30}</td><td>${a.snaps[3].t100}</td>
   <td class="${a.snaps[3].per_dom>=5?'good':''}"><b>${a.snaps[3].per_dom}</b></td>
   <td class="${a.snaps[3].nolead>=5?'good':''}"><b>${a.snaps[3].nolead}</b></td>
   <td>${a.snaps[3].brands}</td><td class="mut">${a.snaps[3].dmax}</td><td class="mut">${a.snaps[3].dmed}</td>
  </tr>`).join('')}
 </tbody></table></div>
 <p class="note" style="margin-top:8px">Колонки со временем — запросов в первой десятке на каждом съёме.</p>
 <div class="grid2" style="margin-top:18px">
  <div class="card acc"><h3>Разница не в одном удачном домене</h3>
  <p>У партии 2 <code>1893.team</code> собрал 87 запросов из 143 — но и без него остаётся
  <b>56 запросов на 10 доменах</b>. Партия 1 на десяти доменах собрала <b>7</b>.</p>
  <p>Доменов с пятью и более запросами в десятке: у партии 2 — <b>пять</b>
  (<code>1893.team</code> 87, <code>fkxb.team</code> 25, <code>cnwv.team</code> 9,
  <code>dprz.team</code> 9, <code>hjsf.team</code> 6). У партии 1 — <b>ни одного</b>,
  максимум 4 у <code>2084.team</code>.</p>
  <p class="verd">Это не разброс одного домена. Вся партия 2 работает,
  вся партия 1 стоит.</p></div>
  <div class="card warn-c"><h3>Потолок под подозрением, но не доказан</h3>
  <p>Обе группы с потолком 20 к обеду просели или встали: партия 1 — 11 → 7,
  Generator_11page_old — 17 → 14. Единственная группа без потолка выросла 16 → 143.</p>
  <p>Разделить «дело в потолке» и «дело в текстах» на этих данных нельзя: у нас две
  ограниченные группы против одной свободной, и тексты у всех разные.</p>
  <p class="verd">Механизм при этом сходится: по ключам видно, что вверх идут те,
  у кого Яндекс сменил ранжирующий адрес. На ограниченных пулах адрес сменился
  у 21 % ключей, на свободном — у 55 %. Меньше вариантов адреса — меньше переключений
  — меньше рывков вверх.</p></div>
 </div>
 <h3 class="vt" style="margin-top:20px">Трафик и деньги</h3>
 <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Доменов</th>
  <th>Страниц-поддоменов</th><th>На домен</th><th>Заходов</th><th>Посетителей</th>
  <th>Регистраций</th><th>Депозитов</th></tr></thead><tbody>
  ${A.map(a=>`<tr><td class="l"><b>${E(a.nm)}</b></td><td>${a.n}</td>
   <td class="${a.sub>1000?'good':'mut'}"><b>${N(a.sub)}</b></td><td>${Math.round(a.sub/a.n)}</td>
   <td class="mono">${N(a.hits)}</td><td class="mono">${N(a.uniq)}</td>
   <td class="${a.reg?'good':'mut'}"><b>${a.reg||'—'}</b></td>
   <td class="${a.dep?'good':'mut'}">${a.dep||'—'}</td></tr>`).join('')}
 </tbody></table></div>
 <div class="card warn-c" style="margin-top:14px"><h3>Что стоит проверить на своей стороне</h3>
 <p>У всех одиннадцати доменов партии 2 живёт <b>123–141 страница-поддомен</b>.
 У всех десяти доменов партии 1 — <b>15–36</b>. Диапазоны не пересекаются ни в одной точке,
 при том что группы выложены в один вечер одним форматом.</p>
 <p>Полностью объяснить это трафиком нельзя, но и опровергнуть тоже: заходов на поддомен
 у обеих групп одинаково (4,8 против 4,7), так что часть разрыва — просто меньше визитов.</p>
 <p class="verd">Проверьте, сколько брендовых поддоменов вообще развернулось на партии 1.
 Если там физически меньше страниц, то дело не в потолке и не в текстах, а в сборке —
 и это объясняет всё остальное разом.</p></div>
 <h3 class="vt" style="margin-top:20px">Бренды в первой десятке: кто у кого</h3>
 <p class="note">Лучшая позиция бренда в каждой группе на съёме ${E(D.last)}.
 Партия 1 держит в десятке <b>5 брендов</b>, партия 2 — <b>52</b>. Общих всего три.</p>
 <div class="tw"><table><thead><tr><th class="l">Бренд</th>
  ${A.map(a=>`<th class="l">${E(a.nm)}</th>`).join('')}</tr></thead><tbody>
  ${allb.map(b=>`<tr><td class="l"><b class="dm">${E(b)}</b></td>
   ${A.map(a=>{const v=a.brands[b];
     return `<td class="l">${v?`<span class="${v[0]<=3?'good':''}"><b>${v[0]}</b></span> <span class="mut sm mono">${E(v[1])}</span>`:'<span class="mut">—</span>'}</td>`;}).join('')}
  </tr>`).join('')}
 </tbody></table></div>
 <h3 class="vt" style="margin-top:20px">По доменам на ${E(D.last)}</h3>
 ${A.map(a=>`<h4 class="sm" style="margin:14px 0 6px;font-family:var(--cond);font-size:14px">${E(a.nm)} ${a.cap?'· потолок 20':'· без потолка'}</h4>
 <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т3</th><th>Т10</th><th>Т30</th><th>Т100</th>
  <th>Брендов в Т10</th><th>Лучшая</th><th>Поддоменов</th><th>Посетителей</th><th>Рег.</th><th>Деп.</th>
  </tr></thead><tbody>
  ${a.dom.map(d=>`<tr><td class="l mono">${E(d.d)}</td>
   <td class="${d.t3?'good':'mut'}">${d.t3||'—'}</td>
   <td class="${d.t10>=5?'good':(d.t10?'':'mut')}"><b>${d.t10||'—'}</b></td>
   <td>${d.t30||'—'}</td><td>${d.t100||'—'}</td><td>${d.nb||'—'}</td>
   <td class="${d.best&&d.best<=3?'good':''}">${d.best??'—'}</td>
   <td class="mono">${d.sub||'—'}</td><td class="mono">${N(d.uniq)}</td>
   <td class="${d.reg?'good':'mut'}">${d.reg||'—'}</td>
   <td class="${d.dep?'good':'mut'}">${d.dep||'—'}</td></tr>`).join('')}
 </tbody></table></div>`).join('')}
</div>`;

const SEC={a:secA,c:secC,b:secB};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}
document.addEventListener('click',e=>{const tr=e.target.closest('tr.clk'); if(!tr)return;
  const d=tr.nextElementSibling; if(d&&d.classList.contains('det')) d.hidden=!d.hidden;});

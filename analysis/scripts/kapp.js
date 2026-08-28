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

const SEC={c:secC,b:secB};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}
document.addEventListener('click',e=>{const tr=e.target.closest('tr.clk'); if(!tr)return;
  const d=tr.nextElementSibling; if(d&&d.classList.contains('det')) d.hidden=!d.hidden;});

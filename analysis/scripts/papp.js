const N=x=>Number(x).toLocaleString('ru-RU');
const f=(x,d=1)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const E=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const sg=x=>x==null?'—':(x>0?'+'+x:''+x);
const tg=t=>t?`<span class="tr tr-${t}">${t}</span>`:'';
const P=D.pools, R=D.rows;
const A=P[0], B=P[1];          // .com (потолок) и .net (без потолка)
const bar=(v,max,cls='')=>`<span class="bar ${cls}"><i style="width:${max?Math.round(100*v/max):0}%"></i></span>`;

/* ---------- пулы ---------- */
const dmax=Math.max(...P.flatMap(p=>p.dom.map(d=>d.tl[d.tl.length-1].t100)));
const secP=`<div class="blk">
 <h2>Два пула, одна ночь, разная вложенность</h2>
 <p class="note">Оба выложены 31 августа. Различаются потолком повторов <code>/ru</code>
 в адресе — и, к сожалению, платформой: это мешает списать разницу на один только потолок.
 Съёмы идут по одному ядру в 1 049 ключей.</p>
 <div class="tiles">
  ${P.filter(p=>!p.name.includes('apex')).map(p=>{const t=p.tot[p.tot.length-1];
   return `<div class="tile ${p.cap==='без потолка'?'g':'b'}">
    <div class="k">${E(p.name)}</div><div class="v">${t.t10}</div>
    <div class="c">запросов в десятке · ${p.n} доменов · ${E(p.cap)}</div></div>`}).join('')}
  <div class="tile a"><div class="k">Разрыв без потолка / с потолком</div>
   <div class="v">${f(B.tot[B.tot.length-1].t10/A.tot[A.tot.length-1].t10,1)}×</div>
   <div class="c">и это при том, что свободный пул моложе на 3–6 часов</div></div>
 </div>
 <div class="tw"><table><thead><tr><th class="l">Пул</th><th class="l">Платформа</th>
  <th class="l">Вложенность</th><th class="l">Выложен</th><th>Стр.</th><th>Дом.</th>
  <th class="l">Т10 по съёмам</th><th>Т3</th><th>Т30</th><th>В сотне</th><th>/ru мед.</th><th>/ru макс</th><th>Глубже 20</th>
  </tr></thead><tbody>
  ${P.map(p=>{const t=p.tot[p.tot.length-1];
   return `<tr><td class="l"><b>${E(p.name)}</b></td><td class="l sm">${E(p.plat)}</td>
   <td class="l sm ${p.cap==='без потолка'?'warn':''}">${E(p.cap)}</td>
   <td class="l sm">${E(p.ld)}</td><td class="sm">${E(p.pages)}</td><td>${p.n}</td>
   <td class="l sm">${p.tot.map(s=>`<span class="bch">${E(s.lab.slice(6))} <b>${s.t10}</b></span>`).join('')}</td>
   <td>${t.t3}</td><td>${t.t30}</td>
   <td class="${t.t100>=1000?'good':''}"><b>${N(t.t100)}</b></td>
   <td>${p.dmed}</td><td class="${p.dmax>20?'warn':''}">${p.dmax}</td>
   <td class="${p.dover>40?'warn':'mut'}">${p.dover}%</td></tr>`}).join('')}
 </tbody></table></div>
 <h3 class="sh">Домены</h3>
 <p class="note">Полоса — сколько ключей домен держит в сотне на последнем съёме.
 Строка раскрывается: страницы, поддомены и бренды этого домена.</p>
 <div class="tw"><table class="big"><thead><tr><th class="l">Домен</th><th class="l">Пул</th>
  ${A.labs.map(l=>`<th>${E(l.slice(6))}</th>`).join('')}
  <th class="l">В сотне сейчас</th><th>Т3</th><th>Т30</th><th>Лучшая</th>
  <th>Поддоменов</th><th>/ru мед.</th><th>/ru макс</th><th>Глубже 20</th>
  </tr></thead><tbody>
  ${P.filter(p=>!p.name.includes('apex')).flatMap(p=>p.dom
    .sort((x,y)=>y.tl[y.tl.length-1].t100-x.tl[x.tl.length-1].t100)
    .map(d=>{const t=d.tl[d.tl.length-1];
    return `<tr class="clk">
     <td class="l"><b class="dm">${E(d.d)}</b></td>
     <td class="l sm ${p.cap==='без потолка'?'warn':'mut'}">${E(p.cap)}</td>
     ${A.labs.map(l=>{const s=d.tl.find(x=>x.lab===l);
       return `<td class="${s&&s.t10>=30?'good':(s&&s.t10===0?'bad':'')}">${s?s.t10:'—'}</td>`}).join('')}
     <td class="l">${bar(t.t100,dmax,p.cap==='без потолка'?'g':'b')}<span class="mono sm">${t.t100}</span></td>
     <td>${t.t3}</td><td>${t.t30}</td>
     <td class="${d.best&&d.best<=3?'good':''}">${d.best??'—'}</td>
     <td class="mono sm">${d.nsub}</td><td>${d.dmed}</td>
     <td class="${d.dmax>20?'warn':''}">${d.dmax}</td>
     <td class="${d.dover>40?'warn':'mut'}">${d.dover}%</td>
    </tr><tr class="det" hidden><td colspan="13"><div class="inner">
      <h4>${E(d.d)}</h4>
      <p><b>Страницы, которыми ранжируется:</b>
       ${d.pages.map(([pg,c])=>`<span class="bch">${E(pg)} <b>${c}</b></span>`).join('')}</p>
      <p><b>Бренды в первой десятке:</b>
       ${d.brands.length?d.brands.map(([b,c])=>`<span class="bch">${E(b)} <b>${c}</b></span>`).join(''):'<span class="mut">нет</span>'}</p>
      <p class="mut sm">Поддоменов с позициями: ${d.nsub}. Вложенность: медиана ${d.dmed},
       максимум ${d.dmax}, глубже двадцати ${d.dover}% адресов.</p>
    </div></td></tr>`})).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:18px">
  <div class="card acc"><h3>Свободный пул впереди вдвое и при этом моложе</h3>
  <p><code>.com</code> выложен 31.08 в 16:39 — на последнем съёме ему 17 ч 44 мин.
  <code>.net</code> отсутствовал в индексе в 21:00 и появился к 00:14, значит выложен
  между 19:30 и 22:45 — ему <b>11,6–14,9 часа</b>.</p>
  <p>Младше на 3–6 часов, а в десятке <b>274 против 135</b>, в тройке
  <b>83 против 29</b>, в сотне <b>1 142 против 432</b>.</p>
  <p class="cl">По одинаковому возрасту разрыв не меньше: <code>.com</code>
  на отметке ~13 часов держал 122–135 запросов в десятке.</p></div>
  <div class="card warn-c"><h3>Охват ограниченного пула осыпается</h3>
  <p>Ключей в сотне: <code>.com</code> — 776 → 671 → <b>432</b>,
  <code>.net</code> — 0 → 362 → <b>1 142</b>.</p>
  <p>За последние десять часов у <code>.com</code> выжило
  <b>${Math.round(100*A.eff.keep/A.eff.was)}%</b> ключей,
  у <code>.net</code> — <b>${Math.round(100*B.eff.keep/B.eff.was)}%</b>.</p>
  <p class="cl">Десятка у <code>.com</code> ещё растёт, но широта уходит:
  домен держится за меньшее число запросов.</p></div>
 </div>
</div>`;

/* ---------- вложенность ---------- */
const dh=(p)=>{const m=Math.max(...p.dhist.map(x=>x[1]));
 return p.dhist.map(([lo,c],i)=>{const lab=['0 (чистый)','1–5','6–10','11–20','21–30','31–40','41+'][i];
 return `<tr><td class="l">${lab}</td><td class="mono">${c}</td>
  <td class="l">${bar(c,m,p.cap==='без потолка'?'g':'b')}</td></tr>`}).join('')};
const secD=`<div class="blk">
 <h2>Вложенность: сколько раз <code>/ru</code> повторяется в адресе</h2>
 <p class="note">Считаю по адресам, которыми домены реально ранжируются на съёме
 ${E(A.labs[A.labs.length-1])}. Потолок стоит на пути, а не на странице: <code>/app/ru/ru/…</code>
 и <code>/ru/ru/…</code> считаются одинаково.</p>
 <div class="grid2">
  ${P.filter(p=>!p.name.includes('apex')).map(p=>`<div class="card">
   <h3>${E(p.name)} · ${E(p.cap)}</h3>
   <div class="tw"><table><thead><tr><th class="l">Повторов /ru</th><th>Адресов</th>
    <th class="l">Доля</th></tr></thead><tbody>${dh(p)}</tbody></table></div>
   <p class="mut sm" style="margin-top:8px">Медиана ${p.dmed}, максимум ${p.dmax},
    глубже двадцати — ${p.dover}% адресов.</p></div>`).join('')}
 </div>
 <h3 class="sh">Что даёт смена адреса</h3>
 <p class="note">Пары «ключ + домен», живые на двух последних съёмах. «Адрес сменился» —
 Яндекс показал по ключу адрес с другим числом повторов. Минус означает движение вверх.</p>
 <div class="tw"><table><thead><tr><th class="l">Пул</th><th>Пар всего</th>
  <th>Адрес сменился</th><th>Доля</th><th>Медиана Δ</th>
  <th>Адрес тот же</th><th>Медиана Δ</th></tr></thead><tbody>
  ${P.filter(p=>p.eff).map(p=>`<tr><td class="l"><b>${E(p.name)}</b></td>
   <td>${p.eff.ch+p.eff.sm}</td><td class="good"><b>${p.eff.ch}</b></td>
   <td class="${(p.eff.ch/(p.eff.ch+p.eff.sm))>=0.6?'good':'mut'}"><b>${Math.round(100*p.eff.ch/(p.eff.ch+p.eff.sm))}%</b></td>
   <td class="${p.eff.chmed<-5?'good':''}"><b>${sg(p.eff.chmed)}</b></td>
   <td class="mut">${p.eff.sm}</td>
   <td class="${p.eff.smmed>5?'bad':'mut'}">${sg(p.eff.smmed)}</td></tr>`).join('')}
 </tbody></table></div>
 <p class="verd">Потолок вдвое режет частоту переключений — <b>38 %</b> против <b>74 %</b>, —
 а на свободном пуле каждое переключение стоит <b>двадцати позиций вверх</b>.
 Ключ, у которого адрес не сменился, проседает на обоих пулах.</p>
 <div class="card warn-c" style="margin-top:14px"><h3>Где граница опасности</h3>
 <p>У <code>.net</code> за четырнадцать часов уже <b>${B.dover}%</b> адресов глубже двадцати,
 максимум <b>${B.dmax}</b>. Домены <code>2535.team</code> и <code>5374.team</code>,
 которые полностью выпали из индекса 28 августа, имели медиану 90 и 81 при максимуме 255.</p>
 <p class="cl">Тем же темпом <code>.net</code> дойдёт до их зоны за двое-трое суток.
 Разумнее не снимать потолок совсем, а поднять его до 40–50 — тогда мы узнаем
 и границу, и её цену.</p></div>
</div>`;

/* ---------- страницы ---------- */
const allpg=[...new Set(P.flatMap(p=>p.pgtop.map(x=>x[0])))];
const secPg=`<div class="blk">
 <h2>Страницы: чем именно домен ранжируется</h2>
 <p class="note">Путь адреса без повторов <code>/ru</code>. Корень — это главная страница
 брендового поддомена, остальное — внутренние страницы, которые делает генератор.</p>
 <div class="tw"><table><thead><tr><th class="l">Страница</th>
  ${P.map(p=>`<th>${E(p.name.split(' · ')[1]||p.name.slice(0,16))}</th>`).join('')}
  <th class="l">Доля у свободного пула</th></tr></thead><tbody>
  ${allpg.map(pg=>{const vals=P.map(p=>(p.pgtop.find(x=>x[0]===pg)||[0,0])[1]);
   const tot=B.pgtop.reduce((a,x)=>a+x[1],0);
   const v=(B.pgtop.find(x=>x[0]===pg)||[0,0])[1];
   return `<tr><td class="l"><code>${E(pg)}</code></td>
    ${vals.map(v2=>`<td class="${v2?'':'mut'}">${v2||'—'}</td>`).join('')}
    <td class="l">${bar(v,tot,'g')}<span class="mono sm">${Math.round(100*v/tot)}%</span></td></tr>`}).join('')}
 </tbody></table></div>
 <p class="verd">Три четверти позиций домены держат <b>главной страницей брендового
 поддомена</b>. Из внутренних работает почти только <code>/app</code> — страница
 скачивания приложения. <code>/zerkalo</code>, <code>/registracia</code>,
 <code>/vhod</code>, <code>/bonus</code> дают единицы позиций на весь пул.</p>
 <p class="note">Это стоит проверить на деньгах: если внутренние страницы почти
 не ранжируются, генерация их в нынешнем объёме — трата, а не вклад.</p>
</div>`;

/* ---------- бренды ---------- */
const bmap={};
for(const p of P){for(const [b,c] of p.brands){bmap[b]=bmap[b]||{}; bmap[b][p.name]=c;}}
const brRows=R.filter(r=>r.p<=15&&r.b);
const byBrand={};
for(const r of brRows){const k=r.b; byBrand[k]=byBrand[k]||{b:k,t:r.t,vol:r.vol,pools:{},best:999,doms:new Set(),keys:new Set()};
 const x=byBrand[k]; x.pools[r.cap]=(x.pools[r.cap]||0)+1; x.best=Math.min(x.best,r.p);
 x.doms.add(r.dom); x.keys.add(r.q);}
const BR=Object.values(byBrand).map(x=>({...x,nd:x.doms.size,nk:x.keys.size}))
  .sort((a,b)=>b.nk-a.nk);
const secB=`<div class="blk">
 <h2>Бренды в ТОП-15</h2>
 <p class="note">${BR.length} брендов держатся в первой пятнадцатке на съёме
 ${E(A.labs[A.labs.length-1])}. Колонки «с потолком» и «без потолка» — сколько запросов
 по бренду занято каждым пулом. Сначала — высоко- и среднечастотные,
 они приносят в девять раз больше регистраций на ключ.</p>
 <h3 class="vt">Высоко- и среднечастотные</h3>
 <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Частотность</th>
  <th>Запросов в ТОП-15</th><th>Доменов</th><th>Лучшая</th>
  <th>С потолком</th><th>Без потолка</th></tr></thead><tbody>
  ${BR.filter(x=>x.t==='ВЧ'||x.t==='СЧ').map(x=>`<tr>
   <td class="l"><b class="dm">${E(x.b)}</b> ${tg(x.t)}</td>
   <td class="mono sm">${x.vol?N(x.vol):'—'}</td>
   <td class="${x.nk>=4?'good':''}"><b>${x.nk}</b></td><td>${x.nd}</td>
   <td class="${x.best<=3?'good':''}">${x.best}</td>
   <td class="${x.pools['потолок 20']?'good':'mut'}">${x.pools['потолок 20']||'—'}</td>
   <td class="${x.pools['без потолка']?'good':'mut'}">${x.pools['без потолка']||'—'}</td></tr>`).join('')}
 </tbody></table></div>
 <h3 class="vt" style="margin-top:18px">Низкочастотные</h3>
 <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Частотность</th>
  <th>Запросов в ТОП-15</th><th>Доменов</th><th>Лучшая</th>
  <th>С потолком</th><th>Без потолка</th></tr></thead><tbody>
  ${BR.filter(x=>x.t!=='ВЧ'&&x.t!=='СЧ').map(x=>`<tr><td class="l"><b class="dm">${E(x.b)}</b> ${tg(x.t)}</td>
   <td class="mono sm">${x.vol?N(x.vol):'—'}</td>
   <td class="${x.nk>=6?'good':''}"><b>${x.nk}</b></td><td>${x.nd}</td>
   <td class="${x.best<=3?'good':''}">${x.best}</td>
   <td class="${x.pools['потолок 20']?'':'mut'}">${x.pools['потолок 20']||'—'}</td>
   <td class="${x.pools['без потолка']?'good':'mut'}">${x.pools['без потолка']||'—'}</td></tr>`).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:16px">
  ${P.filter(p=>!p.name.includes('apex')).map(p=>{const t=p.tier,t10=p.tier10;
   const tot=Object.values(t).reduce((a,b)=>a+b,0);
   return `<div class="card"><h3>${E(p.name)} — по частотности</h3>
   <div class="tw"><table><thead><tr><th class="l">Тир</th><th>В сотне</th><th>Доля</th>
    <th>В десятке</th></tr></thead><tbody>
    ${['ВЧ','СЧ','НЧ'].map(k=>`<tr><td class="l">${tg(k)}</td><td>${t[k]||0}</td>
     <td>${tot?Math.round(100*(t[k]||0)/tot):0}%</td>
     <td class="good"><b>${t10[k]||0}</b></td></tr>`).join('')}
   </tbody></table></div></div>`}).join('')}
 </div>
</div>`;

/* ---------- ключи ---------- */
const secK=`<div class="blk">
 <h2>Все ключи с позициями</h2>
 <p class="note">${N(R.length)} строк «ключ × домен» на последнем съёме каждого пула.
 По умолчанию показаны только <b>ТОП-15</b> и только <b>высоко- и среднечастотные</b>
 ключи — то, что имеет смысл разбирать. Фильтры снимаются селектами.
 Поиск идёт по ключу, бренду, домену, поддомену и странице, сортировка — по клику на заголовок.</p>
 <div class="ctl">
  <input id="q" type="search" placeholder="ключ, бренд, домен, /app…" autocomplete="off">
  <select id="pool"><option value="">все пулы</option>
   ${P.map(p=>`<option>${E(p.name)}</option>`).join('')}</select>
  <select id="tier"><option value="ВС" selected>только ВЧ и СЧ</option>
   <option value="">любая частотность</option>
   <option>ВЧ</option><option>СЧ</option><option>НЧ</option></select>
  <select id="top"><option value="15" selected>только ТОП-15</option>
   <option value="3">только ТОП-3</option><option value="10">только ТОП-10</option>
   <option value="30">только ТОП-30</option><option value="">любая позиция</option></select>
  <span id="cnt" class="mut sm"></span>
 </div>
 <div class="tw"><table id="kt" class="big"><thead><tr>
  <th class="l" data-s="q">Ключ</th><th class="l" data-s="b">Бренд</th><th data-s="t">Тир</th>
  <th data-s="vol">Частотность</th><th data-s="p">Позиция</th><th class="l" data-s="dom">Домен</th>
  <th class="l" data-s="sub">Поддомен</th><th class="l" data-s="page">Страница</th>
  <th data-s="d">/ru</th><th class="l">Пул</th></tr></thead><tbody></tbody></table></div>
</div>`;

/* ---------- заход ---------- */
const EN=D.entry, H=D.hist, HT=D.htot;
const secE=`<div class="blk">
 <h2>Процент захода на позиции</h2>
 <p class="note">Две разные вещи, и их важно не путать. <b>Заход по доменам</b> —
 какая доля доменов пула вообще попала в выдачу. <b>Захват ядра</b> — какую долю
 из ${N(EN[0].core)} отслеживаемых ключей пул занял хотя бы одним доменом.
 Первая цифра быстро упирается в сто процентов и почти ничего не различает,
 вторая различает всё.</p>
 <div class="tw"><table><thead><tr><th class="l">Пул</th><th class="l">Вложенность</th>
  <th>Доменов</th><th>Ядро</th>
  ${['Т3','Т10','Т30','сотня'].map(l=>`<th>${l}<div class="mut sm">доменов зашли</div></th>`).join('')}
  ${['Т3','Т10','Т30','сотня'].map(l=>`<th>${l}<div class="mut sm">ядра занято</div></th>`).join('')}
  </tr></thead><tbody>
  ${EN.map(e=>`<tr><td class="l"><b>${E(e.pool)}</b></td>
   <td class="l sm ${e.cap==='без потолка'?'warn':'mut'}">${E(e.cap)}</td>
   <td>${e.n}</td><td class="mono sm">${N(e.core)}</td>
   ${e.bands.map(b=>`<td class="${b.dsh>=90?'good':(b.dsh<50?'bad':'')}">
     <b>${b.dsh}%</b><div class="mut sm">${b.dm}/${e.n}</div></td>`).join('')}
   ${e.bands.map(b=>`<td class="${b.ksh>=18?'good':(b.ksh<3?'mut':'')}">
     <b>${f(b.ksh,1)}%</b><div class="mut sm">${b.keys}</div></td>`).join('')}
  </tr>`).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:16px">
  <div class="card acc"><h3>По доменам разницы почти нет</h3>
  <p>В сотню зашли <b>все</b> домены обоих пулов. В десятку — 8 из 9 у пула
  с потолком и 10 из 10 без потолка.</p>
  <p class="cl">Метрика «сколько доменов вообще ранжируется» на живых пулах
  бесполезна: она почти всегда близка к ста процентам. Сравнивать пулы по ней нельзя.</p></div>
  <div class="card acc"><h3>По ядру разница двукратная</h3>
  <p>Пул без потолка занял <b>41,4 %</b> ядра против <b>23,2 %</b> у ограниченного.
  В первой десятке — <b>18,0 %</b> против <b>10,7 %</b>, в тройке
  <b>6,3 %</b> против <b>2,7 %</b>.</p>
  <p class="cl">Это тот же двукратный разрыв, что и по абсолютным числам,
  но выраженный в доле ядра — сравнимо между пулами любого размера.</p></div>
 </div>
 <h3 class="sh">Полоса позиций × частотность — где на самом деле разница</h3>
 <p class="note">Сколько ключей ядра пул занял в каждой полосе, с разбивкой по частотности.
 В ядре ${D.tiersz['ВЧ']} высокочастотных ключей, ${D.tiersz['СЧ']} среднечастотных
 и ${D.tiersz['НЧ']} низкочастотных.</p>
 <div class="tw"><table><thead><tr><th class="l">Полоса</th><th class="l">Частотность</th>
  ${D.mat.map(m=>`<th>${E(m.pool.split(' · ')[1]||m.pool)}<div class="mut sm">${E(m.cap)}</div></th>`).join('')}
  <th class="l">Разница</th></tr></thead><tbody>
  ${D.bands.flatMap(bn=>[['vch','ВЧ',D.tiersz['ВЧ']],['sch','СЧ',D.tiersz['СЧ']],['nch','НЧ',D.tiersz['НЧ']]]
    .map(([k,lab,tot],i)=>{const vals=D.mat.map(m=>m.cells[bn][k]);
     const dif=vals[1]-vals[0];
     return `<tr${i===0?' class="p2"':''}>
      <td class="l ${i===0?'':'mut sm'}">${i===0?'<b>ТОП-'+bn+'</b>':''}</td>
      <td class="l">${tg(lab)} <span class="mut sm">из ${tot}</span></td>
      ${vals.map(v=>`<td class="${v>0?'':'mut'}"><b>${v}</b></td>`).join('')}
      <td class="l"><span class="${dif>5?'good':(dif<-2?'bad':'mut')}">${sg(dif)}</span></td></tr>`}))
    .join('')}
 </tbody></table></div>
 <p class="verd">В верхних полосах по <b>ВЧ и СЧ</b> пулы равны, а в тройке ограниченный
 даже впереди: <b>6 ВЧ и 2 СЧ против нуля</b>. На ТОП-15 — ровно поровну,
 <b>25 ВЧ и 11 СЧ у обоих</b>. Весь двукратный отрыв свободного пула
 создаётся <b>низкочастоткой</b>: 189 против 103 в ТОП-15 и 333 против 185 в сотне.</p>
 <p class="note">Это меняет смысл вывода про потолок. Свободная вложенность даёт
 больше <i>объёма</i>, но объём этот низкочастотный — а по недельным данным
 сто ключей в десятке по низкочастотному бренду приносят 2,3 регистрации против
 20,4 у высокочастотного. Если считать по деньгам, а не по числу позиций,
 преимущество свободного пула пока не подтверждается.</p>
 <h3 class="sh">Сколько ядра берёт отдельный домен</h3>
 <p class="note">Доля из ${N(EN[0].core)} ключей, которую домен держит сам по себе.</p>
 <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Пул</th>
  <th>В сотне</th><th>Доля ядра</th><th class="l"></th>
  <th>В десятке</th><th>Доля ядра</th></tr></thead><tbody>
  ${EN.filter(e=>!e.pool.includes('apex')).flatMap(e=>e.doms.map(d=>`<tr>
   <td class="l mono">${E(d.d)}</td>
   <td class="l sm ${e.cap==='без потолка'?'warn':'mut'}">${E(e.cap)}</td>
   <td>${d.t100}</td><td class="${d.sh100>=10?'good':''}"><b>${f(d.sh100,1)}%</b></td>
   <td class="l">${bar(d.sh100,22,e.cap==='без потолка'?'g':'b')}</td>
   <td>${d.t10}</td><td class="${d.sh10>=3?'good':'mut'}">${f(d.sh10,1)}%</td></tr>`)).join('')}
 </tbody></table></div>
 <h3 class="sh">Для фона: заход на позиции по всему архиву</h3>
 <p class="note">Доля доменов группы, у которых есть хотя бы один ключ в десятке
 и хотя бы одна позиция вообще, на последнем съёме каждой группы.
 Всего ${HT.n} доменов в ${H.length} группах.</p>
 <div class="tiles">
  <div class="tile g"><div class="k">Доменов с любой позицией</div><div class="v">${HT.sh100}%</div>
   <div class="c">${HT.t100} из ${HT.n}</div></div>
  <div class="tile g"><div class="k">Доменов с ключом в десятке</div><div class="v">${HT.sh10}%</div>
   <div class="c">${HT.t10} из ${HT.n}</div></div>
  <div class="tile b"><div class="k">Доменов с регистрацией</div><div class="v">27%</div>
   <div class="c">51 из 188 с закрытым окном</div></div>
 </div>
 <p class="verd">Вот главное, что даёт этот разрез: <b>позиции получают почти все,
 деньги — четверть</b>. 93 % доменов имеют позиции, 67 % стоят в первой десятке,
 но регистрацию приносят только 27 %. Узкое место не в том, чтобы попасть в выдачу,
 а в том, чтобы попасть туда по запросам, на которые кликают и по которым регистрируются.</p>
 <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Доменов</th>
  <th>С ключом в Т10</th><th>Доля</th><th>С любой позицией</th><th>Доля</th>
  </tr></thead><tbody>
  ${H.map(x=>`<tr><td class="l">${E(x.g)}</td><td>${x.n}</td>
   <td class="good"><b>${x.t10}</b></td>
   <td class="${x.sh10>=80?'good':(x.sh10<40?'bad':'')}"><b>${x.sh10}%</b></td>
   <td>${x.t100}</td>
   <td class="${x.sh100>=95?'good':(x.sh100<80?'bad':'mut')}">${x.sh100}%</td></tr>`).join('')}
 </tbody></table></div>
</div>`;

const SEC={p:secP,e:secE,d:secD,pg:secPg,b:secB,k:secK};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}
document.addEventListener('click',e=>{const tr=e.target.closest('tr.clk'); if(!tr)return;
  const d=tr.nextElementSibling; if(d&&d.classList.contains('det')) d.hidden=!d.hidden;});

/* таблица ключей: фильтр + сортировка */
let sortKey='p',sortDir=1;
function draw(){
  const q=(document.getElementById('q').value||'').toLowerCase().trim();
  const pool=document.getElementById('pool').value, tier=document.getElementById('tier').value;
  const top=document.getElementById('top').value;
  const tok=tier==='ВС'?(t=>t==='ВЧ'||t==='СЧ'):(t=>!tier||t===tier);
  let rows=R.filter(r=>(!pool||r.pool===pool)&&tok(r.t)&&(!top||r.p<=+top)&&
    (!q||[r.q,r.b,r.dom,r.sub,r.page].some(v=>String(v||'').toLowerCase().includes(q))));
  rows.sort((a,b)=>{const x=a[sortKey],y=b[sortKey];
    if(x==null)return 1; if(y==null)return -1;
    return (typeof x==='number'?x-y:String(x).localeCompare(String(y)))*sortDir;});
  document.getElementById('cnt').textContent=`${N(rows.length)} строк`;
  const lim=rows.slice(0,1200);
  document.querySelector('#kt tbody').innerHTML=lim.map(r=>`<tr>
   <td class="l sm">${E(r.q)}</td><td class="l"><b class="dm">${E(r.b||'—')}</b></td>
   <td>${tg(r.t)}</td><td class="mono sm">${r.vol?N(r.vol):'—'}</td>
   <td class="${r.p<=3?'good':(r.p<=10?'ok':'')}"><b>${r.p}</b></td>
   <td class="l mono sm">${E(r.dom)}</td><td class="l sm">${E(r.sub||'—')}</td>
   <td class="l sm"><code>${E(r.page||'—')}</code></td>
   <td class="${r.d>20?'warn':'mut'}">${r.d??'—'}</td>
   <td class="l sm ${r.cap==='без потолка'?'warn':'mut'}">${E(r.cap)}</td></tr>`).join('')
   +(rows.length>1200?`<tr><td colspan="10" class="l mut sm">показаны первые 1 200 строк из ${N(rows.length)} — уточните фильтр</td></tr>`:'');
}
['q','pool','tier','top'].forEach(id=>{const el=document.getElementById(id);
  if(el) el.addEventListener('input',draw);});
document.querySelectorAll('#kt thead th[data-s]').forEach(th=>{th.style.cursor='pointer';
  th.onclick=()=>{const k=th.dataset.s; sortDir=(sortKey===k)?-sortDir:1; sortKey=k; draw();};});
draw();

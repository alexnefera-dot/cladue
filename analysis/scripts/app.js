const $=(h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content};
const f2=(x)=>x.toFixed(2).replace('.',','), f1=(x)=>x.toFixed(1).replace('.',','), pc=(x)=>Math.round(x*100)+'%';
const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const kfmt=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':Math.round(v/1e3)+'k';

function spark(series){
  const mx=Math.max(...series,0.01);
  return '<span class="spark" title="'+series.join(' → ')+'">'+series.map((v,i)=>
    '<i class="'+(i===series.length-1?'hi':'')+'" style="height:'+
    Math.max(2,Math.round(v/mx*22))+'px"></i>').join('')+'</span>';
}
function pill(v,hi,lo){return '<span class="pill '+(v>=hi?'p-ok':v<=lo?'p-no':'p-mid')+'">'+pc(v)+'</span>'}

/* ---------- tab: итог ---------- */
function tabItog(){
  const L=D.launches, tot=L.reduce((a,x)=>a+x.n,0), hs=L.reduce((a,x)=>a+x.hs,0);
  const ent=L.reduce((a,x)=>a+x.ent*x.n,0)/tot;
  return `
  <div class="tiles">
    <div class="tile"><div class="k">Доменов</div><div class="v">${tot}</div><div class="c">33 запуска, D231–D274</div></div>
    <div class="tile a"><div class="k">ВЧ+СЧ в ТОП-10</div><div class="v">${hs}</div><div class="c">${f2(hs/tot)} на домен</div></div>
    <div class="tile"><div class="k">Зашло</div><div class="v">${pc(ent)}</div><div class="c">взяли ≥1 ВЧ/СЧ в ТОП-10</div></div>
    <div class="tile g"><div class="k">Лучший запуск</div><div class="v">8,17</div><div class="c">D273 · 12page+даты</div></div>
    <div class="tile"><div class="k">Прогноз с замера 2</div><div class="v">0,81</div><div class="c">корреляция Т30 → финал</div></div>
  </div>

  <div class="blk"><h2>Что изменилось против старого чата</h2>
  <p class="note">Рейтинг в переносе был посчитан непоследовательно: часть строк сходится с единым
  правилом точно (D273, D248, D269, D253), часть — нет. Ни один порог СЧ не воспроизводит таблицу
  целиком, значит строки считались в разное время разными способами. Ниже — пересчёт по одному правилу.</p>
  <div class="cards">
    <div class="card err"><h3>D249 недооценён почти в полтора раза</h3>
      <p><span class="big">7,88</span> <span class="mut">вместо 5,27 ВЧ+СЧ на домен</span></p>
      <p>Это не третье место, а второе — вплотную к D273. И у D249 26 доменов против 12,
      то есть результат надёжнее.</p></div>
    <div class="card err"><h3>«.buzz ≈ 0 % по ВЧ» — неверно</h3>
      <p><span class="big">0,83</span> <span class="mut">ВЧ на домен против 1,15 у .team</span></p>
      <p>.buzz слабее .team, но не мёртв: 21 % доменов берут ВЧ. Зона отстаёт примерно в 2,5 раза
      по ВЧ+СЧ, а не в бесконечность.</p></div>
    <div class="card err"><h3>«casino в имени = хуже» — шум</h3>
      <p><span class="big">4 : 4</span> <span class="mut">запуска за и против</span></p>
      <p>С контролем по запуску направление переворачивается ровно пополам. Сигнала нет —
      это была разница между партиями, а не между именами.</p></div>
    <div class="card ok"><h3>Отсев надо вести по Т30, не по ВЧ/СЧ</h3>
      <p><span class="big">0,81</span> <span class="mut">против 0,64</span></p>
      <p>Т30 на замере 2 предсказывает финал заметно лучше. D273 на замере 2 имел
      1 ВЧ-ключ на 12 доменов — по ВЧ его бы списали, по Т30 видно было сразу.</p></div>
  </div></div>

  <div class="blk"><h2>Подтвердилось</h2>
  <ul class="cl">
    <li><b>.team — главный фактор.</b> 1,70 ВЧ+СЧ на домен против 1,00 у .buzz и 0,43 у .casino.
      Внутри запусков, где есть обе зоны, .team выигрывает в 4 случаях из 5.</li>
    <li><b>Заточка под бренд не работает.</b> 124 домена в форматах «под бренд» дают 0,20–0,77 на домен
      против 3,6–8,2 у остальных.</li>
    <li><b>«Просел после пика» — приговор.</b> 173 домена, медиана финала 0, хоть какой-то результат
      у 11 %. Против 52 % у растущих.</li>
    <li><b>Чем дороже бренд, тем хуже берётся.</b> Монотонно: 24 ключа в ТОП-10 на бренд в диапазоне
      700k–1M, 16,5 при 1–2M, 10,8 при 2–5M, 3,7 при 5–10M, 0,3 свыше 10M.</li>
    <li><b>Рост скачками.</b> D273: 0,11 → 0,20 → 8,17. Судить о запуске раньше 3–4 замера нельзя.</li>
  </ul></div>

  <div class="blk"><h2>Дедупликация листов</h2>
  <p class="note">Проверены все 33 файла. Подтверждены четыре известных случая (D251, D252, D265, D266)
  и найдены четыре новых, которые раньше считались как отдельные замеры.</p>
  <div class="tw"><table><thead><tr><th class="l">Файл</th><th class="l">Проблема</th><th>Листов</th><th>Замеров</th></tr></thead>
  <tbody>
    <tr><td class="l id">D233</td><td class="l">Sheet5 дублирует предыдущий</td><td>5</td><td>4</td></tr>
    <tr><td class="l id">D241</td><td class="l">Sheet4 и Sheet11 дублируют</td><td>11</td><td>9</td></tr>
    <tr><td class="l id">D245</td><td class="l">Sheet6 дублирует</td><td>7</td><td>6</td></tr>
    <tr><td class="l id">D267</td><td class="l">Sheet5 дублирует</td><td>6</td><td>5</td></tr>
    <tr><td class="l mut">D251</td><td class="l mut">Sheet2 дубль, Sheet4 пустой — известно</td><td>4</td><td>2</td></tr>
    <tr><td class="l mut">D252</td><td class="l mut">Sheet6 дубль — известно</td><td>5</td><td>4</td></tr>
    <tr><td class="l mut">D265</td><td class="l mut">Sheet3 дубль — известно</td><td>3</td><td>2</td></tr>
    <tr><td class="l mut">D266</td><td class="l mut">Sheet2 дубль — известно</td><td>3</td><td>2</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Отдельно: у <b class="id">D273</b> Sheet1 содержит 91 строку вместо 1570 —
  это компактный формат выгрузки, где перечислены только ранжирующиеся ключи. Данные полные,
  замер засчитан.</p></div>`;
}

/* ---------- tab: запуски ---------- */
function tabRun(){
  let rows=D.launches.map((L,i)=>`
    <tr class="clk" data-i="${i}">
      <td class="l id">${L.id}</td><td class="l">${esc(L.fmt)}</td>
      <td>${L.n}</td><td>${L.meas}</td>
      <td>${spark(L.series)}</td>
      <td><b>${f2(L.hsd)}</b></td><td>${L.hs}</td>
      <td>${pill(L.ent,.5,.2)}</td>
      <td>${f1(L.t30d)}</td>
      <td class="${L.grow>=.6?'good':L.grow<=.2?'bad':''}">${pc(L.grow)}</td>
      <td class="${L.drop>=.6?'bad':''}">${pc(L.drop)}</td>
    </tr><tr class="det" hidden><td colspan="11"><div class="inner" data-slot="${i}"></div></td></tr>`).join('');
  return `<div class="blk"><h2>Рейтинг запусков</h2>
  <p class="note">Последний замер каждого запуска. «Растёт» — доля доменов, у которых Т30 на финале
  не ниже 95 % своего пика; «Просел» — ниже 80 % пика. Столбик — траектория ВЧ+СЧ на домен по замерам.
  Клик по строке раскрывает домены.</p>
  <div class="tw"><table><thead><tr>
    <th class="l">Запуск</th><th class="l">Формат</th><th>Дом</th><th>Зам</th><th>Динамика</th>
    <th>ВЧ+СЧ/дом</th><th>ВЧ+СЧ</th><th>Зашло</th><th>Т30/дом</th><th>Растёт</th><th>Просел</th>
  </tr></thead><tbody id="runbody">${rows}</tbody></table></div></div>`;
}
function fillRun(){
  document.querySelectorAll('#runbody tr.clk').forEach(tr=>{
    tr.onclick=()=>{
      const det=tr.nextElementSibling, i=+tr.dataset.i;
      det.hidden=!det.hidden;
      const slot=det.querySelector('[data-slot]');
      if(!det.hidden && !slot.dataset.done){
        slot.dataset.done=1;
        const L=D.launches[i];
        slot.innerHTML='<h4>Домены — ВЧ / СЧ / НЧ в ТОП-10, всего в ТОП-30</h4><div class="chips">'+
          L.doms.map(d=>{const p=D.perdom[d]||{vch:0,sch:0,nch:0,t30:0};
            const cls=p.vch>0?'v':p.sch>0?'s':'';
            return '<span class="chip '+cls+'">'+esc(d)+' <b>'+p.vch+'/'+p.sch+'/'+p.nch+'</b> ·'+p.t30+'</span>';
          }).join('')+'</div>';
      }
    };
  });
}

/* ---------- tab: возраст ---------- */
function tabAge(){
  const at=(L,m)=>L.series.length>=m?L.series[m-1]:null;
  let blocks='';
  [2,3,4,5].forEach(m=>{
    const rows=D.launches.filter(L=>at(L,m)!==null&&L.n>=7)
      .map(L=>({L,v:at(L,m)})).sort((a,b)=>b.v-a.v);
    blocks+=`<div class="blk"><h2>Замер ${m}</h2>
      <div class="tw"><table><thead><tr><th class="l">Запуск</th><th class="l">Формат</th>
      <th>Дом</th><th>ВЧ+СЧ/дом</th><th>Т30/дом</th><th>Финал</th></tr></thead><tbody>`+
      rows.map(({L,v})=>`<tr><td class="l id">${L.id}</td><td class="l">${esc(L.fmt)}</td>
        <td>${L.n}</td><td><b>${f2(v)}</b></td><td>${f1(L.t30series[m-1]||0)}</td>
        <td class="mut">${f2(L.hsd)}</td></tr>`).join('')+`</tbody></table></div></div>`;
  });
  return `<div class="blk"><h2>Сравнение на одинаковом возрасте</h2>
  <p class="note">Рейтинг по последнему замеру нечестен: у D249 шесть замеров, у D273 — три.
  Здесь запуски сопоставлены на одном номере замера, только партии от 7 доменов.</p>
  <div class="cards">
    <div class="card acc"><h3>D273 выигрывает честно</h3>
      <p>На замере 3: <span class="big">8,17</span> против 3,31 у D249 и 3,17 у D258.
      Отрыв в 2,5 раза при равном возрасте.</p></div>
    <div class="card"><h3>Но на замере 2 он был предпоследним</h3>
      <p><span class="big">0,20</span> — ниже, чем у «под бренд» D267 (0,80). Весь результат
      появился одним скачком между вторым и третьим замером.</p></div>
    <div class="card"><h3>D249 продолжал расти</h3>
      <p>2,65 → 3,31 → 3,50 → 5,04 → <span class="big">7,88</span>. К шестому замеру он почти догнал
      D273. Сколько дал бы D273 на шестом — неизвестно, замеров нет.</p></div>
  </div></div>`+blocks;
}

/* ---------- tab: форматы ---------- */
function tabFmt(){
  const agg=(m)=>{const o={};D.launches.forEach(L=>{
    if(L.fmt==='—')return; const idx=m==='fin'?L.series.length-1:m-1;
    if(idx<0||idx>=L.series.length)return;
    const a=o[L.fmt]||(o[L.fmt]={n:0,hs:0});
    a.n+=L.n; a.hs+=L.series[idx]*L.n;});
    return Object.entries(o).map(([k,v])=>({k,n:v.n,d:v.hs/v.n})).sort((a,b)=>b.d-a.d)};
  const t=(rows)=>`<div class="tw"><table><thead><tr><th class="l">Формат</th><th>Доменов</th>
    <th>ВЧ+СЧ/дом</th></tr></thead><tbody>`+rows.map(r=>
    `<tr><td class="l">${esc(r.k)}</td><td>${r.n}</td><td><b>${f2(r.d)}</b></td></tr>`).join('')+
    `</tbody></table></div>`;
  return `<div class="blk"><h2>Форматы на последнем замере</h2>
  <p class="note">Возраст запусков разный — таблица показывает потолок формата, не скорость.</p>
  ${t(agg('fin'))}</div>
  <div class="blk"><h2>Те же форматы на замере 2</h2>
  <p class="note">Единый возраст. Порядок другой: 12page+даты уходит вниз, потому что его рывок
  ещё не случился, а «предметные» и 7page+даты стартуют быстро.</p>
  ${t(agg(2))}</div>
  <div class="blk"><h2>Как это читать</h2>
  <ul class="cl">
    <li><b>Заточка под бренд — закрыто.</b> 12page под бренд 0,77 и 7page под бренд 0,20 на финале,
      на 124 доменах. Это худшие форматы архива при самой большой выборке.</li>
    <li><b>nu 6page — самый проверенный рабочий формат.</b> 92 домена, 3,62 на финале.
      Выборка вчетверо больше, чем у 12page+даты, и результат стабилен по четырём запускам.</li>
    <li><b>12page+даты пока лидер, но n=12 и один запуск.</b> Весь вывод держится
      на одной партии и одном домене-чемпионе внутри неё. Нужен повтор.</li>
    <li><b>7page+даты — 38 доменов, 3,61 уже на замере 2.</b> Самый быстрый старт архива.
      Если добавит на 3–4 замере, это лучший кандидат на объём.</li>
  </ul></div>`;
}

/* ---------- tab: зоны ---------- */
function tabZone(){
  const Z=[[".team",433,498,333,1.15,.28],[".buzz",24,20,11,0.83,.21],
           [".casino",38,7,13,0.18,.08],[".beer",4,0,2,0.00,.00]];
  return `<div class="blk"><h2>Зоны по всему архиву</h2>
  <p class="note">Последний замер каждого запуска, накрученные домены исключены.</p>
  <div class="tw"><table><thead><tr><th class="l">Зона</th><th>Доменов</th><th>ВЧ Т10</th>
  <th>СЧ Т10</th><th>ВЧ/дом</th><th>Есть ВЧ</th></tr></thead><tbody>`+
  Z.map(z=>`<tr><td class="l id">${z[0]}</td><td>${z[1]}</td><td>${z[2]}</td><td>${z[3]}</td>
    <td><b>${f2(z[4])}</b></td><td>${pill(z[5],.25,.1)}</td></tr>`).join('')+
  `</tbody></table></div></div>
  <div class="blk"><h2>С контролем по запуску</h2>
  <p class="note">Голая таблица зон обманывает: 10 из 24 доменов .buzz сидят в D249 — лучшем
  nu-запуске. Ниже сравнение только внутри запусков, где присутствуют обе зоны.</p>
  <div class="tw"><table><thead><tr><th class="l">Запуск</th><th>.buzz</th><th>ВЧ+СЧ/дом</th>
  <th>.team</th><th>ВЧ+СЧ/дом</th></tr></thead><tbody>
    <tr><td class="l id">D241</td><td>2</td><td>0,00</td><td>10</td><td>0,50</td></tr>
    <tr><td class="l id">D249</td><td>10</td><td>2,40</td><td>15</td><td>12,07</td></tr>
    <tr><td class="l id">D255</td><td>5</td><td>0,80</td><td>19</td><td>1,84</td></tr>
    <tr><td class="l id">D265</td><td>3</td><td>1,00</td><td>13</td><td>2,69</td></tr>
    <tr><td class="l id">D266</td><td>2</td><td>0,00</td><td>12</td><td>0,00</td></tr>
    <tr class="tot"><td class="l">Итого</td><td>22</td><td>1,41</td><td>69</td><td>3,71</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">.team выигрывает в 4 запусках из 5, в пятом ничья по нулям.
  Отставание .buzz — <b>в 2,6 раза</b>, а не «ноль». Для теста зон это важно: .buzz-домен
  в новых группах не обязан дать ноль, он просто слабее, и на 2 доменах разницу не поймать.</p></div>
  <div class="blk"><h2>Имя домена</h2>
  <p class="note">Проверка вывода «casino в имени = хуже». Сравнение внутри запусков,
  где есть и те и другие.</p>
  <div class="tw"><table><thead><tr><th class="l">Запуск</th><th>с casino</th><th>ВЧ+СЧ/дом</th>
  <th>без</th><th>ВЧ+СЧ/дом</th><th class="l">Кто лучше</th></tr></thead><tbody>
    <tr><td class="l id">D241</td><td>3</td><td>1,67</td><td>9</td><td>0,00</td><td class="l good">casino</td></tr>
    <tr><td class="l id">D243</td><td>6</td><td>1,83</td><td>3</td><td>0,67</td><td class="l good">casino</td></tr>
    <tr><td class="l id">D246</td><td>5</td><td>1,40</td><td>7</td><td>0,14</td><td class="l good">casino</td></tr>
    <tr><td class="l id">D248</td><td>5</td><td>0,80</td><td>17</td><td>2,00</td><td class="l bad">без</td></tr>
    <tr><td class="l id">D249</td><td>13</td><td>4,54</td><td>12</td><td>12,17</td><td class="l bad">без</td></tr>
    <tr><td class="l id">D251</td><td>2</td><td>1,50</td><td>8</td><td>0,25</td><td class="l good">casino</td></tr>
    <tr><td class="l id">D252</td><td>5</td><td>2,00</td><td>14</td><td>5,64</td><td class="l bad">без</td></tr>
    <tr><td class="l id">D255</td><td>6</td><td>0,67</td><td>18</td><td>1,94</td><td class="l bad">без</td></tr>
    <tr class="tot"><td class="l">Итого</td><td>45</td><td>2,29</td><td>88</td><td>3,40</td><td class="l">4 : 4</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Ровно пополам. Общий перевес «без casino» целиком создаёт
  один домен — 8264.team из D249 с 48 ВЧ-ключами. Убери его, и разница исчезает.
  <b>Сигнала нет, вывод из старого чата снимается.</b></p></div>`;
}

/* ---------- tab: отсев ---------- */
function tabCut(){
  return `<div class="blk"><h2>Что предсказывает результат</h2>
  <p class="note">360 доменов из запусков с тремя и более замерами.</p>
  <div class="tiles">
    <div class="tile a"><div class="k">Т30 на замере 2</div><div class="v">0,81</div><div class="c">корреляция с финалом</div></div>
    <div class="tile"><div class="k">ВЧ+СЧ на замере 2</div><div class="v">0,64</div><div class="c">заметно слабее</div></div>
    <div class="tile b"><div class="k">≤2 в Т30 на замере 2</div><div class="v">89%</div><div class="c">останутся в нуле (n=89)</div></div>
    <div class="tile g"><div class="k">Есть ВЧ/СЧ на замере 2</div><div class="v">79%</div><div class="c">дойдут до результата (n=68)</div></div>
    <div class="tile"><div class="k">Ноль ВЧ/СЧ на замере 2</div><div class="v">20%</div><div class="c">всё равно выстрелят (n=292)</div></div>
  </div></div>

  <div class="blk"><h2>Главная поправка: считайте Т30, а не ВЧ</h2>
  <p class="note">D273 на замере 2 имел один ВЧ-ключ на всю партию из 12 доменов — по ВЧ-метрике
  это провал. Но Т30 у будущего чемпиона уже был 84. Через один замер партия дала 8,17 на домен.</p>
  <div class="tw"><table><thead><tr><th class="l">Домен D273</th><th>Т30 на зам. 2</th>
  <th>ВЧ+СЧ на зам. 2</th><th>Т30 финал</th><th>ВЧ+СЧ финал</th></tr></thead><tbody>
    <tr><td class="l id">rtnm.team</td><td>84</td><td>1</td><td>300</td><td class="good"><b>55</b></td></tr>
    <tr><td class="l">c7v.team</td><td>0</td><td>0</td><td>58</td><td class="good">11</td></tr>
    <tr><td class="l">xzdg.team</td><td>35</td><td>1</td><td>68</td><td class="good">8</td></tr>
    <tr><td class="l">9364.team</td><td>11</td><td>0</td><td>90</td><td class="good">7</td></tr>
    <tr><td class="l">2607.team</td><td>10</td><td>0</td><td>151</td><td class="good">6</td></tr>
    <tr><td class="l">qsvb.team</td><td>46</td><td>0</td><td>77</td><td>3</td></tr>
    <tr><td class="l">vwkp.team</td><td>17</td><td>0</td><td>71</td><td>3</td></tr>
    <tr><td class="l">w6nd.team</td><td>0</td><td>0</td><td>29</td><td>3</td></tr>
    <tr><td class="l">z8kr.team</td><td>0</td><td>0</td><td>22</td><td>1</td></tr>
    <tr><td class="l">h4p.team</td><td>1</td><td>0</td><td>33</td><td>1</td></tr>
    <tr><td class="l mut">8271.team</td><td>14</td><td>0</td><td>19</td><td class="mut">0</td></tr>
    <tr><td class="l mut">t3mb.team</td><td>0</td><td>0</td><td>16</td><td class="mut">0</td></tr>
  </tbody></table></div></div>

  <div class="blk"><h2>Цена отсева</h2>
  <p class="note">Правило «≤2 ключа в Т30 на замере 2 — списываем» срабатывает на 89 доменах.
  Из них 10 всё-таки дали результат — это 11 % потерь.</p>
  <div class="cards">
    <div class="card ok"><h3>Правило безопасно для чемпионов</h3>
      <p>Ни один домен с финалом выше 5 ВЧ+СЧ под отсев не попадает. Максимальная потеря —
      4 ключа (casino83n.buzz из D255).</p></div>
    <div class="card err"><h3>Но не применяйте его к ВЧ</h3>
      <p>Правило «нет ВЧ/СЧ на замере 2 — списываем» убило бы 292 домена, из которых
      <span class="big">20 %</span> дают результат, включая всю партию D273.</p></div>
  </div></div>

  <div class="blk"><h2>«Просел после пика»</h2>
  <p class="note">Т30 на финале ниже 80 % от собственного пика.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Доменов</th><th>Медиана финала</th>
  <th>Среднее</th><th>С результатом</th></tr></thead><tbody>
    <tr><td class="l">Просел после пика</td><td>173</td><td>0,0</td><td>0,19</td><td>${pill(.11,.4,.2)}</td></tr>
    <tr><td class="l">Растёт до конца</td><td>168</td><td>1,0</td><td>3,46</td><td>${pill(.52,.4,.2)}</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Подтверждено полностью. Доля растущих внутри партии —
  лучший индикатор её качества: D273 — 100 %, D249 — 77 %, D252 — 79 % против D267 — 6 %,
  D262 — 10 %, D268 — 14 %.</p></div>`;
}

/* ---------- tab: бренды ---------- */
function tabBrand(){
  const B=D.brands.filter(b=>b.v>=700000).slice(0,40);
  const tier=(t)=>`<span class="tag t-${t==='ВЧ'?'vch':t==='СЧ'?'sch':'nch'}">${t}</span>`;
  return `<div class="blk"><h2>Чем дороже бренд, тем хуже берётся</h2>
  <p class="note">Зависимость строго монотонная — это самый устойчивый паттерн архива.</p>
  <div class="tw"><table><thead><tr><th class="l">Объём бренда</th><th>Брендов</th>
  <th>Взято хотя бы раз</th><th>Ключей в Т10</th><th>На бренд</th></tr></thead><tbody>
    <tr><td class="l">700k – 1M (СЧ)</td><td>15</td><td>80%</td><td>360</td><td><b>24,0</b></td></tr>
    <tr><td class="l">1 – 2M</td><td>17</td><td>71%</td><td>280</td><td><b>16,5</b></td></tr>
    <tr><td class="l">2 – 5M</td><td>20</td><td>85%</td><td>217</td><td><b>10,8</b></td></tr>
    <tr><td class="l">5 – 10M</td><td>7</td><td>86%</td><td>26</td><td><b>3,7</b></td></tr>
    <tr><td class="l">свыше 10M</td><td>6</td><td>33%</td><td>2</td><td><b>0,3</b></td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Практический вывод: ядро результата дают бренды 700k–2M.
  Топовые (vodka, leon, arkada, pin up, kent) не берутся почти никогда — 2 ключа на 6 брендов
  по всему архиву.</p></div>
  <div class="blk"><h2>Какие бренды берутся лучше всего</h2>
  <p class="note">Считаны только ВЧ и СЧ бренды, последний замер каждого запуска.</p>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
  <th>Т3</th><th>Т10</th><th>Т30</th><th>Доменов</th></tr></thead><tbody>`+
  B.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kfmt(b.v)}</td><td>${tier(b.t)}</td>
    <td class="${b.t3>0?'good':'mut'}">${b.t3}</td><td><b>${b.t10}</b></td><td>${b.t30}</td>
    <td class="mut">${b.d}</td></tr>`).join('')+`</tbody></table></div></div>`;
}

/* ---------- tab: чемпионы ---------- */
function tabChamp(){
  const top=Object.entries(D.perdom).sort((a,b)=>(b[1].vch+b[1].sch)-(a[1].vch+a[1].sch)).slice(0,25);
  const fmt=(id)=>{const L=D.launches.find(x=>x.id===id);return L?L.fmt:'—'};
  return `<div class="blk"><h2>Топ-25 доменов архива</h2>
  <p class="note">Последний замер. Клик — бренды, которые домен держит в ТОП-30.</p>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Запуск</th>
  <th class="l">Формат</th><th>ВЧ Т10</th><th>СЧ Т10</th><th>НЧ Т10</th><th>Всего Т30</th>
  </tr></thead><tbody id="chbody">`+
  top.map(([d,p],i)=>`<tr class="clk" data-d="${esc(d)}"><td class="l id">${esc(d)}</td>
    <td class="l">${p.L}</td><td class="l mut">${esc(fmt(p.L))}</td>
    <td><b>${p.vch}</b></td><td>${p.sch}</td><td class="mut">${p.nch}</td><td>${p.t30}</td></tr>
    <tr class="det" hidden><td colspan="7"><div class="inner"></div></td></tr>`).join('')+
  `</tbody></table></div></div>`;
}
function fillChamp(){
  document.querySelectorAll('#chbody tr.clk').forEach(tr=>{
    tr.onclick=()=>{
      const det=tr.nextElementSibling; det.hidden=!det.hidden;
      const slot=det.querySelector('.inner');
      if(!det.hidden && !slot.dataset.done){
        slot.dataset.done=1;
        const dd=D.domdet[tr.dataset.d];
        if(!dd){slot.innerHTML='<h4>нет данных</h4>';return}
        slot.innerHTML='<h4>Бренды в ТОП-30 — лучшая позиция и число ключей</h4><div class="chips">'+
          dd.brands.map(b=>{const c=b[2]==='ВЧ'?'v':b[2]==='СЧ'?'s':'';
            return '<span class="chip '+c+'">'+esc(b[0])+' <b>#'+b[3]+'</b> ×'+b[4]+
              ' <span style="opacity:.6">'+kfmt(b[1])+'</span></span>'}).join('')+'</div>';
      }
    };
  });
}

/* ---------- tab: новые группы ---------- */
function tabNew(){
  return `<div class="blk"><h2>Пять групп на подходе</h2>
  <p class="note">Позиций ещё нет. Ниже — что тест сможет показать, а что нет, посчитанное
  на архиве до того, как придут данные.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Стр</th>
  <th class="l">Источник</th><th class="l">Версия</th><th class="l">Шаблон</th>
  <th>Дом</th><th>.team</th><th>.buzz</th><th class="l">прочие</th></tr></thead><tbody>
    <tr><td class="l id">Группа 1</td><td>7</td><td class="l">сайты из выдачи</td>
      <td class="l mut">—</td><td class="l mut">не указан</td>
      <td>10</td><td>6</td><td>2</td><td class="l mut">.quest .bond</td></tr>
    <tr><td class="l id">Группа 2</td><td>7</td><td class="l">генератор</td>
      <td class="l">v4</td><td class="l mut">не указан</td>
      <td>10</td><td>6</td><td>2</td><td class="l mut">.icu .top</td></tr>
    <tr><td class="l id">Группа 3</td><td>11</td><td class="l">генератор</td>
      <td class="l warn">?</td><td class="l mut">не указан</td>
      <td>5</td><td>5</td><td>0</td><td class="l mut">—</td></tr>
    <tr><td class="l id">Группа 4</td><td>11</td><td class="l">генератор #2</td>
      <td class="l warn">?</td><td class="l mut">не указан</td>
      <td>5</td><td>4</td><td>0</td><td class="l mut">.cyou</td></tr>
    <tr><td class="l id">Группа 5</td><td>7</td><td class="l">генератор</td>
      <td class="l">v5</td><td class="l"><b>Theme2</b></td>
      <td>5</td><td>5</td><td>0</td><td class="l mut">—</td></tr>
    <tr class="tot"><td class="l">Итого</td><td>—</td><td class="l">35 доменов</td>
      <td class="l">—</td><td class="l">—</td>
      <td>35</td><td>26</td><td>4</td><td class="l">5 экзотических</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">С Группой 5 в тесте меняются уже четыре переменные:
  источник контента, объём страниц, версия генератора и шаблон сайта. Развести их все
  на 35 доменах не выйдет — ниже то, что развести можно.</p></div>

  <div class="blk"><h2>Что тест покажет</h2>
  <div class="cards">
    <div class="card ok"><h3>Источник контента — чисто</h3>
      <p>Группа 1 против Группы 2 при равных 7 страницах: по 6 .team, по 2 .buzz,
      по 2 экзотических зоны в каждой. Состав совпадает точно.</p>
      <p class="mut">Единственное сравнение теста, где поправок не нужно.
      Считать полными группами, 10 против 10.</p></div>
    <div class="card acc"><h3>Объём страниц — считать по .team</h3>
      <p>9 доменов .team из групп 3+4 против 6 доменов .team из группы 2.
      Полными группами нельзя: 11-страничные группы почти целиком .team,
      группа 2 — только на 6 из 10.</p>
      <p class="mut">7 страниц: 6204, b2kn, m2wf, n4kd, r7mc, b8t<br>
      11 страниц: 4392, 1085, mpdg, gkrd, bdwn, j8vp, 3019, 2470, jkzq</p></div>
    <div class="card err"><h3>Версия генератора — загрязнено шаблоном</h3>
      <p>Группа 5 (v5, 5 доменов) против .team-части группы 2 (v4, 6 доменов).
      Но у группы 5 явно стоит Theme2, а у группы 2 шаблон неизвестен.</p>
      <p>Если шаблоны разные, сравнение измеряет <b>версию плюс шаблон</b>,
      и разделить вклад будет нечем.</p></div>
  </div></div>

  <div class="blk"><h2>Что нужно уточнить до замеров</h2>
  <ul class="cl">
    <li><b>Какой шаблон у групп 1–4?</b> Самый важный вопрос. Если не Theme2,
      Группа 5 не сравнивается напрямую ни с чем — в ней меняются сразу две переменные,
      и любой её результат будет необъяснимым.</li>
    <li><b>Какая версия генератора у групп 3 и 4?</b> Контенты группы 4 и группы 5 созданы
      в одну минуту (22:39 и 22:40), группы 3 — в 16:56. Если 11-страничные тоже v5,
      объём страниц можно сравнивать внутри одной версии — это заметно чище.</li>
    <li><b>Generator_11page и Generator_11page_2 — один генератор с одними настройками?</b>
      Если да, группы 3 и 4 пулятся в 10 доменов. Если нет, обе остаются по 5,
      где вывод сделать нельзя.</li>
  </ul></div>

  <div class="blk"><h2>Чего тест не покажет</h2>
  <ul class="cl">
    <li><b>Величину разницы.</b> На группах по 5 доменов шанс поймать чемпиона около 20 %,
      на 9–10 — около 40 %. Один такой домен сдвигает среднее на +5–7, поэтому результат
      будет «лучше / хуже / не видно», без числа.</li>
    <li><b>Разницу между группами 3 и 4.</b> По 5 доменов; расхождение между ними
      не будет означать, что один набор контентов лучше другого.</li>
    <li><b>Работу экзотических зон.</b> Пять зон по одному домену. .cyou в архиве
      не встречается ни разу — истории нет вообще. Смотреть Т30, а не факт входа в ТОП-10.</li>
    <li><b>Ничего раньше третьего замера.</b> D273 на замере 2 стоял на 0,20 — предпоследним
      в архиве. Через замер стал первым с 8,17.</li>
  </ul></div>

  <div class="blk"><h2>Как считать, когда придут позиции</h2>
  <ul class="cl">
    <li><b>Гр.1 vs Гр.2</b> — полными группами, 10 против 10. Основной результат теста.</li>
    <li><b>Гр.2(.team) vs Гр.3+4(.team)</b> — 6 против 9. Объём страниц.</li>
    <li><b>Гр.2(.team) vs Гр.5</b> — 6 против 5. Версия генератора, с оговоркой про шаблон.</li>
    <li><b>На замере 2 смотреть Т30 на домен, а не ВЧ.</b> Порог интереса — от 15 Т30
      на домен в среднем по группе; ниже 7 партия почти наверняка пустая.</li>
    <li><b>Снять минимум 4 замера.</b> Три — тот минимум, на котором виден рывок.</li>
  </ul></div>`;
}

/* ---------- shell ---------- */
const TABS=[["Итог",tabItog,null],["Запуски",tabRun,fillRun],["Возраст",tabAge,null],
  ["Форматы",tabFmt,null],["Зоны и имена",tabZone,null],["Отсев",tabCut,null],
  ["Бренды",tabBrand,null],["Чемпионы",tabChamp,fillChamp],["Новые группы",tabNew,null]];
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
    if(i===j && !s.dataset.done){s.dataset.done=1;s.innerHTML=TABS[j][1]();if(TABS[j][2])TABS[j][2]();}
  });
  window.scrollTo({top:0,behavior:'instant'});
}
main.insertAdjacentHTML('beforeend',
  '<div class="foot wrap" style="padding-left:0;padding-right:0">Пересчёт архива D231–D274 · '+
  'единое правило: последний замер, ВЧ ≥ 1M, СЧ 700k–1M, исключены накрученные домены и бренды '+
  'vovan / pari · 572 домена, 33 запуска, 276 093 ключа в справочнике брендов</div>');
show(0);

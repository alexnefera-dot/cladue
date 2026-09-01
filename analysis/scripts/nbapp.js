const N=x=>Number(x).toLocaleString('ru-RU');
const f=(x,d=1)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const E=s=>String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const sg=x=>x==null?'—':(x>0?'+'+x:''+x);
const bar=(v,max,cls='')=>`<span class="bar ${cls}"><i style="width:${max?Math.round(100*Math.abs(v)/max):0}%"></i></span>`;
const GN=['URL тот же','URL сменился, глубже','URL сменился, мельче','URL сменился, глубина та же'];
const T=D.total, M=D.meta;

const secA=`<div class="blk">
 <h2>Ответ: да, но только при заметном приросте — и не «переобход», а именно глубина</h2>
 <p class="note">Считаю по всем парам соседних съёмов, где ключ жив в обоих:
 ${N(M.n)} пар «ключ × домен × переход», ${M.doms} доменов, ${M.pools.length} пулов,
 ${M.pairs.length} переходов между съёмами с 27 августа по 1 сентября.
 Минус означает движение вверх.</p>
 <div class="tiles">
  <div class="tile g"><div class="k">Адрес стал глубже</div>
   <div class="v">${sg(T['URL сменился, глубже'].med)}</div>
   <div class="c">${T['URL сменился, глубже'].n} ключей · вверх ${T['URL сменился, глубже'].shup}%</div></div>
  <div class="tile b"><div class="k">Адрес стал мельче</div>
   <div class="v">${sg(T['URL сменился, мельче'].med)}</div>
   <div class="c">${T['URL сменился, мельче'].n} ключей · вверх ${T['URL сменился, мельче'].shup}%</div></div>
  <div class="tile b"><div class="k">Адрес не менялся</div>
   <div class="v">${sg(T['URL тот же'].med)}</div>
   <div class="c">${N(T['URL тот же'].n)} ключей · вверх ${T['URL тот же'].shup}%</div></div>
  <div class="tile a"><div class="k">Выигрыш глубины после контролей</div>
   <div class="v">${sg(D.paired['глубже против URL тот же'].diff)}</div>
   <div class="c">внутри домена, съёма и полосы старта</div></div>
 </div>
 <div class="tw"><table><thead><tr><th class="l">Что произошло с адресом</th><th>Ключей</th>
  <th>Медиана Δ позиции</th><th>Среднее Δ</th><th>Ушли вверх</th><th>Ушли вниз</th><th>Доля вверх</th>
  </tr></thead><tbody>
  ${GN.filter(g=>T[g].n).map(g=>`<tr><td class="l"><b>${E(g)}</b></td>
   <td>${N(T[g].n)}</td>
   <td class="${T[g].med<-3?'good':(T[g].med>0?'bad':'mut')}"><b>${sg(T[g].med)}</b></td>
   <td class="${T[g].mean<-3?'good':(T[g].mean>0?'bad':'mut')}">${sg(T[g].mean)}</td>
   <td class="good">${T[g].up}</td><td class="mut">${T[g].dn}</td>
   <td class="${T[g].shup>=60?'good':(T[g].shup<40?'bad':'')}"><b>${T[g].shup}%</b></td></tr>`).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:16px">
  <div class="card acc"><h3>Почему это не просто «переобход»</h3>
  <p>Раньше я не мог отделить «Яндекс переобошёл страницу и поэтому она подскочила»
  от «адрес стал глубже и поэтому подскочил». Теперь отделяется — сравнением двух
  видов переобхода.</p>
  <p><b>Оба случая — смена адреса.</b> Но у ставших <b>глубже</b> медиана
  ${sg(T['URL сменился, глубже'].med)} и ${T['URL сменился, глубже'].shup}% вверх,
  а у ставших <b>мельче</b> — ${sg(T['URL сменился, мельче'].med)} и
  ${T['URL сменился, мельче'].shup}% вверх, то есть ровно как у ключей,
  где адрес вообще не менялся.</p>
  <p class="cl">Переобход сам по себе позиции не даёт. Даёт именно направление:
  глубже — вверх, мельче — никуда.</p></div>
  <div class="card warn-c"><h3>Чего проверить не удалось</h3>
  <p>Случай «адрес сменился, а глубина осталась той же» встретился
  <b>${T['URL сменился, глубина та же'].n} раз из ${N(M.n)}</b>. Смена адреса
  и смена глубины на наших доменах почти всегда идут вместе.</p>
  <p class="cl">Поэтому идеального разделения нет: сравнение «глубже против мельче»
  — лучшее, что дают данные. Оно сильное, но это не эксперимент,
  а наблюдение за тем, что Яндекс сделал сам.</p></div>
 </div>
</div>`;

const mx=Math.max(...D.magorder.map(m=>Math.abs(D.mag[m].med||0)));
const secB=`<div class="blk">
 <h2>Порог: прирост меньше шести повторов не даёт ничего</h2>
 <p class="note">Только ключи, у которых адрес сменился. Разбивка по величине прироста.</p>
 <div class="tw"><table><thead><tr><th class="l">Насколько изменилась глубина</th><th>Ключей</th>
  <th>Медиана Δ</th><th class="l">Величина</th><th>Среднее Δ</th><th>Доля вверх</th>
  </tr></thead><tbody>
  ${D.magorder.map(m=>{const s=D.mag[m]; if(!s.n) return '';
   return `<tr><td class="l"><b>${E(m)}</b></td><td>${s.n}</td>
    <td class="${s.med<-5?'good':(s.med>0?'bad':'mut')}"><b>${sg(s.med)}</b></td>
    <td class="l">${bar(s.med,mx,s.med<0?'g':'b')}</td>
    <td class="${s.mean<-5?'good':'mut'}">${sg(s.mean)}</td>
    <td class="${s.shup>=65?'good':(s.shup<50?'bad':'')}"><b>${s.shup}%</b></td></tr>`}).join('')}
 </tbody></table></div>
 <p class="verd">Порог виден чётко: прирост <b>+1…+5</b> даёт медиану 0 и ровно половину
 вверх — это шум. С <b>+6</b> начинается эффект: медиана −14 и 73% вверх.
 Дальше он не растёт — у прироста «+16 и больше» медиана −11, то есть не сильнее,
 чем у +6…+15.</p>
 <h3 class="sh">С поправкой на стартовую позицию</h3>
 <p class="note">Возврат к среднему мог бы объяснить всё: ключ на 80-м месте может
 только расти. Проверяю внутри каждой полосы старта.</p>
 <div class="tw"><table><thead><tr><th class="l">Стартовая полоса</th>
  ${D.magorder.map(m=>`<th>${E(m)}</th>`).join('')}</tr></thead><tbody>
  ${['1–10','11–30','31–60','61–100'].map(b=>`<tr><td class="l"><b>${b}</b></td>
   ${D.magorder.map(m=>{const s=D.cross[m][b];
     return `<td class="${!s.n?'mut':(s.med<-5?'good':(s.med>2?'bad':''))}">
      ${s.n?`<b>${sg(s.med)}</b><div class="mut sm">n=${s.n}</div>`:'—'}</td>`}).join('')}
  </tr>`).join('')}
 </tbody></table></div>
 <p class="verd">Эффект держится в полосах <b>31–60</b> и <b>61–100</b> и исчезает
 в первой десятке — там расти почти некуда. При этом ключи с прежним адресом
 в тех же полосах не растут, а проседают, так что возвратом к среднему
 разницу не объяснить.</p>
</div>`;

const wd=D.withindom, lv=D.lvorder;
const wmax=Math.max(...lv.slice(1).map(b=>Math.abs((wd[b]||{}).diff||0)));
const secC=`<div class="blk">
 <h2>Уровень глубины: где адрес стоит лучше всего</h2>
 <p class="note">Это уже не про изменение, а про сам уровень. Первая таблица — по всем
 доменам сразу, вторая — внутри каждого домена отдельно, чтобы качество домена
 не искажало картину.</p>
 <div class="grid2">
  <div class="card"><h3>По всем доменам</h3>
  <div class="tw"><table><thead><tr><th class="l">Повторов /ru</th><th>Адресов</th>
   <th>Медиана позиции</th><th>Доля в десятке</th></tr></thead><tbody>
   ${lv.map(b=>{const s=D.level[b]; if(!s) return '';
    return `<tr><td class="l"><b>${b}</b></td><td>${s.n}</td>
     <td class="${s.med<=25?'good':(s.med>=60?'bad':'')}"><b>${f(s.med,0)}</b></td>
     <td class="${s.t10>=30?'good':(s.t10<10?'bad':'')}">${s.t10}%</td></tr>`}).join('')}
  </tbody></table></div></div>
  <div class="card"><h3>Внутри домена, относительно его же чистых адресов</h3>
  <div class="tw"><table><thead><tr><th class="l">Повторов /ru</th><th>Доменов·съёмов</th>
   <th>Разница медиан</th><th class="l"></th></tr></thead><tbody>
   ${lv.slice(1).map(b=>{const s=wd[b]; if(!s) return '';
    return `<tr><td class="l"><b>${b}</b></td><td>${s.n}</td>
     <td class="${s.diff<-10?'good':(s.diff>-5?'mut':'')}"><b>${sg(s.diff)}</b></td>
     <td class="l">${bar(s.diff,wmax,s.diff<0?'g':'b')}</td></tr>`}).join('')}
  </tbody></table></div></div>
 </div>
 <p class="verd">Чистый адрес — худшее место: медиана 69 и <b>один процент</b> в десятке.
 Адреса с 1–5 повторами почти так же плохи (медиана 68). С шести повторов позиция
 резко улучшается и держит плато примерно до сорока. Внутри одного домена глубокие
 адреса стоят на <b>20 позиций выше</b> его же чистых.</p>
 <p class="note">Оговорка к этому разрезу: глубина накапливается со временем, а вместе
 с ней растёт и проиндексированность домена. Часть разницы между «чистый» и «глубокий»
 — это разница между «страница только появилась» и «страница живёт в индексе давно».
 Сравнение внутри домена частично это снимает, но не полностью.</p>
</div>`;

const secD_=`<div class="blk">
 <h2>Работает одинаково с потолком и без</h2>
 <p class="note">Пулы с ограничением вложенности до 20 против пулов без ограничения.</p>
 <div class="tw"><table><thead><tr><th class="l">Пулы</th><th class="l">Что с адресом</th>
  <th>Ключей</th><th>Медиана Δ</th><th>Доля вверх</th></tr></thead><tbody>
  ${Object.entries(D.bycap).map(([c,gs])=>GN.filter(g=>gs[g].n).map((g,i)=>`<tr${i===0?' class="p2"':''}>
   <td class="l">${i===0?`<b>${E(c)}</b>`:''}</td><td class="l">${E(g)}</td>
   <td>${N(gs[g].n)}</td>
   <td class="${gs[g].med<-3?'good':(gs[g].med>0?'bad':'mut')}"><b>${sg(gs[g].med)}</b></td>
   <td class="${gs[g].shup>=60?'good':(gs[g].shup<40?'bad':'')}">${gs[g].shup}%</td></tr>`).join('')).join('')}
 </tbody></table></div>
 <p class="verd">Механизм один и тот же: на ограниченных пулах прирост глубины даёт
 −7, на свободных −9. Потолок не ломает эффект — он ограничивает, сколько раз
 этот эффект может сработать.</p>
 <h3 class="sh">Что из этого следует</h3>
 <div class="grid2">
  <div class="card acc"><h3>1. Потолок ниже шести бессмыслен</h3>
  <p>Прирост на 1–5 повторов не двигает позицию вообще. Значит потолок вроде 3 или 5
  просто выключает механизм.</p>
  <p class="cl">Рабочий диапазон начинается с шести.</p></div>
  <div class="card acc"><h3>2. Выше сорока смысла тоже нет</h3>
  <p>Медиана позиции на 26–40 повторах — 17, на 41 и больше — 19, то есть плато.
  Внутри домена выигрыш на 41+ падает до −2,6 против −20 на 6–25.</p>
  <p class="cl">Разумный потолок — <b>25–40</b>. Это и оставляет механизм рабочим,
  и не пускает домены в зону, где умерли <code>2535.team</code> и <code>5374.team</code>
  с медианой 90.</p></div>
  <div class="card warn-c"><h3>3. Это наблюдение, а не эксперимент</h3>
  <p>Глубину меняем не мы — её меняет Яндекс, выбирая, каким адресом ранжировать.
  Мы видим корреляцию между «стал глубже» и «поднялся», а не доказанную причину.</p>
  <p class="cl">Проверить можно только так: взять пул и принудительно закрыть в robots
  или редиректом всё глубже шести повторов, а на парном пуле оставить как есть.</p></div>
  <div class="card"><h3>4. Позиции — не деньги</h3>
  <p>Весь этот эффект измерен в позициях. По разбору пулов 31 августа видно,
  что прирост позиций от свободной вложенности почти весь низкочастотный,
  а по конверсиям низкочастотка даёт 2,3 регистрации на сто ключей против 20,4
  у высокочастотки.</p>
  <p class="cl">Так что «глубже = выше» верно, но из него ещё не следует
  «глубже = больше денег». Это закроется конверсиями к 6 сентября.</p></div>
 </div>
</div>`;

const SEC={a:secA,b:secB,c:secC,d:secD_};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}

const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), f2=(x)=>x.toFixed(2).replace('.',',');
const pc=(x)=>Math.round(x*100)+'%';
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':(v>=1e3?(v/1e3).toFixed(1).replace('.',',')+'k':Math.round(v)));
const O=D.order, GR=D.groups;
const pos=(p)=>`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;
function spark(s){const mx=Math.max(...s,0.01);
  return '<span class="spark" title="'+s.map(x=>f1(x)).join(' → ')+'">'+s.map((v,i)=>
    '<i class="'+(i===s.length-1?'hi':'')+'" style="height:'+Math.max(2,Math.round(v/mx*22))+'px"></i>').join('')+'</span>';}

function overview(){
  const row=(sn)=>{const g=GR[sn];
    return `<tr><td class="l id">${esc(g.name)}</td><td class="l">${esc(g.cfg)}</td>
      <td class="mut">${g.wave}</td><td>${g.n}</td><td>${spark(g.ser)}</td>
      <td><b>${f1(g.t10)}</b></td><td>${g.med}</td><td>${f1(g.wo)}</td>
      <td class="${g.leadshare>=.6?'warn':''}">${pc(g.leadshare)}</td>
      <td class="${g.vch?'good':'mut'}">${g.vch}</td><td class="${g.sch?'good':'mut'}">${g.sch}</td>
      <td>${g.t3}</td><td>${g.brands}</td>
      <td class="${g.z100?'bad':'mut'}">${g.z100}</td></tr>`;};
  return `<div class="blk"><h2>Все 13 групп на последнем замере</h2>
  <p class="note">Т10/дом, медиана и «без лидера» — по .team-подмножеству. «Доля лидера» —
  какую часть всех ключей группы держит её лучший домен: выше 60 % означает, что результат
  группы это результат одного сайта. Столбик — траектория по замерам.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Конфигурация</th>
  <th class="l">Волна</th><th>Дом</th><th>Динамика</th><th>Т10/дом</th><th>Медиана</th>
  <th>Без лидера</th><th>Доля лидера</th><th>ВЧ</th><th>СЧ</th><th>ТОП-3</th><th>Брендов</th>
  <th>Нет в Т100</th></tr></thead><tbody>${O.map(row).join('')}</tbody></table></div></div>

  <div class="blk"><h2>Что изменилось за день</h2>
  <div class="cards">
    <div class="card ok"><h3>Generator_11page взорвалась</h3>
      <p>32 → 29 → <span class="big">60</span> ключей в ТОП-10 на домен.
      25 ВЧ, 19 СЧ, 56 в ТОП-3.</p>
      <p>Работают <b>все пять доменов</b>: 102, 85, 61, 28, 24. Лидер держит только 34 %
      ключей — это сила партии, а не одного сайта.</p></div>
    <div class="card err"><h3>generator v4 умерла окончательно</h3>
      <p>0,7 → 0 → <span class="big">0</span>. Ни одного ключа в ТОП-10 на десяти доменах,
      и два домена выпали даже из ТОП-100.</p></div>
    <div class="card ok"><h3>Имена и наборы вышли из нуля</h3>
      <p>Вечером у наборов было 5 доменов из 5 без единого ключа в ТОП-100. Сейчас
      у всех пяти по 39–85 ключей.</p>
      <p>Гипотеза об индексации подтвердилась — хорошо, что не списали.</p></div>
  </div></div>

  <div class="blk"><h2>Главное предупреждение: почти всё держится на одиночках</h2>
  <p class="note">Доля лидера показывает, насколько результат группы — это результат
  одного домена.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Значения по доменам (.team)</th>
  <th>Доля лидера</th><th class="l">Как читать</th></tr></thead><tbody>
    <tr><td class="l id">12pages_withdate · Theme1</td><td class="l num">113, 14, 10, 5, 5, 0, 0</td>
      <td class="bad"><b>77 %</b></td><td class="l">Результат группы = 1908.team</td></tr>
    <tr><td class="l id">12pages_nodate</td><td class="l num">33, 14, 9, 4, 3</td>
      <td class="warn"><b>52 %</b></td><td class="l">Половина на 5390.team</td></tr>
    <tr><td class="l id">7page_yandex</td><td class="l num">64, 36, 8, 4, 1, 0</td>
      <td class="warn"><b>57 %</b></td><td class="l">Больше половины на одном домене</td></tr>
    <tr><td class="l id">12pages_withdate · Theme2</td><td class="l num">25, 10, 8, 7, 5, 2, 0</td>
      <td>44 %</td><td class="l">Распределено ровнее</td></tr>
    <tr><td class="l id">Generator_11page</td><td class="l num">102, 85, 61, 28, 24</td>
      <td class="good"><b>34 %</b></td><td class="l">Работают все пять — настоящая партия</td></tr>
  </tbody></table></div></div>`;
}

function wave(w,title,note,extra){
  let h=`<div class="blk"><h2>${title}</h2><p class="note">${note}</p></div>`;
  O.filter(sn=>GR[sn].wave===w).forEach(sn=>{const g=GR[sn];
    h+=`<div class="blk"><h2>${esc(g.name)}</h2>
      <p class="note">${esc(g.cfg)} · ${g.n} доменов · замеры ${g.labels.join(', ')}</p>
      <div class="tiles">
        <div class="tile a"><div class="k">Т10 на домен</div><div class="v">${f1(g.t10)}</div>
          <div class="c">по .team, n=${g.ntm}</div></div>
        <div class="tile"><div class="k">Медиана</div><div class="v">${g.med}</div>
          <div class="c">без лидера ${f1(g.wo)}</div></div>
        <div class="tile ${g.vch+g.sch?'g':'b'}"><div class="k">ВЧ+СЧ в ТОП-10</div>
          <div class="v">${g.vch+g.sch}</div><div class="c">${g.vch} ВЧ · ${g.sch} СЧ</div></div>
        <div class="tile ${g.t3?'g':''}"><div class="k">ТОП-3</div><div class="v">${g.t3}</div>
          <div class="c">${g.brands} брендов, ${g.hb} дорогих</div></div>
        <div class="tile ${g.leadshare>=.6?'b':''}"><div class="k">Доля лидера</div>
          <div class="v">${pc(g.leadshare)}</div><div class="c">ключей у лучшего домена</div></div>
        <div class="tile ${g.z100?'b':''}"><div class="k">Нет в Т100</div>
          <div class="v">${g.z100}/${g.n}</div><div class="c">было ${g.z100a} на первом замере</div></div>
      </div>
      <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Динамика Т10</th>
      <th>Т10</th><th>Т30</th><th>Т100</th><th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>НЧ</th>
      <th>Брендов</th></tr></thead><tbody>`+
      g.doms.map((d,i)=>`<tr class="clk" data-g="${sn}" data-i="${i}">
        <td class="l ${d.d.endsWith('.team')?'id':'mut'}">${esc(d.d)}</td>
        <td class="l mut num">${d.tr.join(' → ')}</td>
        <td><b>${d.t10}</b></td><td>${d.t30}</td>
        <td class="${d.t100===0?'bad':''}">${d.t100}</td>
        <td class="${d.t3?'good':'mut'}">${d.t3}</td>
        <td class="${d.vch?'good':'mut'}">${d.vch}</td>
        <td class="${d.sch?'good':'mut'}">${d.sch}</td>
        <td class="mut">${d.nch}</td><td>${d.brands.length}</td></tr>
        <tr class="det" hidden><td colspan="10"><div class="inner"></div></td></tr>`).join('')+
      `</tbody></table></div></div>`;});
  return h+(extra||'');
}

const DAY_EXTRA=`
  <div class="blk"><h2>Даты: устойчивые меры теперь против дат</h2>
  <p class="note">Вечером казалось наоборот. За пять часов картина перевернулась.</p>
  <div class="tw"><table><thead><tr><th class="l">Сторона</th><th>n</th>
  <th class="l">Было в 17:34</th><th class="l">Стало в 22:29</th><th>Среднее</th>
  <th>Медиана</th><th>Без лидера</th><th>ВЧ</th><th>СЧ</th></tr></thead><tbody>
    <tr><td class="l id">12 стр с датами</td><td>7</td>
      <td class="l mut num">37, 8, 5, 5, 2, 1, 0</td>
      <td class="l num">113, 14, 10, 5, 5, 0, 0</td>
      <td>21,0</td><td>5</td><td>5,7</td><td class="good">15</td><td class="good">8</td></tr>
    <tr><td class="l id">12 стр без дат</td><td>5</td>
      <td class="l mut num">9, 4, 2, 2, 1</td>
      <td class="l num">33, 14, 9, 4, 3</td>
      <td>12,6</td><td class="good"><b>9</b></td><td class="good"><b>7,5</b></td>
      <td class="mut">0</td><td>1</td></tr>
  </tbody></table></div>
  <div class="cards" style="margin-top:14px">
    <div class="card err"><h3>По охвату впереди «без дат»</h3>
      <p>Медиана <span class="big">9</span> против 5, без лидера 7,5 против 5,7.
      Обе устойчивые меры в пользу отсутствия дат.</p></div>
    <div class="card"><h3>По дорогим брендам впереди «с датами»</h3>
      <p>15 ВЧ и 8 СЧ против нуля и одного. Но <b>все 15 ВЧ сидят в одном домене</b>
      1908.team — это не про даты, а про один сайт.</p></div>
    <div class="card acc"><h3>Что это значит</h3>
      <p>Эффекта дат на этих выборках не видно ни в одну сторону. Разброс между доменами
      внутри каждой стороны больше разницы между сторонами.</p></div>
  </div></div>

  <div class="blk"><h2>Шаблон: по-прежнему не разделился</h2>
  <div class="tw"><table><thead><tr><th class="l">Сторона</th><th>n</th>
  <th class="l">Значения по доменам</th><th>Среднее</th><th>Медиана</th><th>Без лидера</th>
  <th>ВЧ</th></tr></thead><tbody>
    <tr><td class="l id">Theme1</td><td>7</td><td class="l num">113, 14, 10, 5, 5, 0, 0</td>
      <td>21,0</td><td>5</td><td>5,7</td><td class="good">15</td></tr>
    <tr><td class="l id">Theme2</td><td>7</td><td class="l num">25, 10, 8, 7, 5, 2, 0</td>
      <td>8,1</td><td class="good"><b>7</b></td><td>5,3</td><td class="mut">0</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">«Без лидера» 5,7 и 5,3 — практически равны,
  медиана у Theme2 даже выше. Все 15 ВЧ у Theme1 — в 1908.team. Вывод не изменился:
  <b>шаблон на семи доменах на сторону не измеряется.</b></p></div>

  <div class="blk"><h2>Имена и наборы: индексация подтвердилась</h2>
  <div class="tw"><table><thead><tr><th class="l">Группа</th>
  <th class="l">Ключей в ТОП-100 в 17:34</th><th class="l">В 22:29</th>
  <th>Т10 сейчас</th></tr></thead><tbody>
    <tr><td class="l id">nabor28gotovyi · наборы</td><td class="l num bad">0, 0, 0, 0, 0</td>
      <td class="l num good">85, 73, 56, 46, 39</td><td>1,2</td></tr>
    <tr><td class="l id">kostoreznaya1 · имена</td><td class="l num bad">4, 1, 0, 0, 0</td>
      <td class="l num good">45, 18, 12, 9, 3</td><td>1,4</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Пять часов назад обе группы выглядели полностью
  мёртвыми. Сейчас все десять доменов в индексе. <b>Списывать их вечером было бы ошибкой.</b>
  Уровень пока низкий (1,2 и 1,4 ключа в ТОП-10 на домен), но группы младше остальных
  примерно на шесть часов — судить всё ещё рано.</p></div>`;

const GEN_EXTRA=`
  <div class="blk"><h2>Судить рано — группе 23 минуты</h2>
  <div class="cards">
    <div class="card"><h3>Возраст</h3>
      <p>Запуск создан в 22:06, съём в 22:29. <span class="big">23</span> минуты.</p>
      <p>Для сравнения: у 12-страничных групп на первом замере было около шести часов,
      и они уже держали 3,6–8,3 ключа в ТОП-10 на домен.</p></div>
    <div class="card"><h3>Индексация идёт</h3>
      <p>20 доменов из 50 пока без единого ключа в ТОП-100, у остальных 30 — от 1 до 33.
      Это нормальная картина для только что поднятых сайтов.</p></div>
    <div class="card acc"><h3>Чем ценна</h3>
      <p>50 доменов в одной зоне .team — самая большая партия за всё время наблюдений.
      На такой выборке чемпион (раз на 15–30 доменов) должен попасться 2–3 раза,
      и среднее наконец перестанет зависеть от одного сайта.</p></div>
  </div></div>`;

function tabBrands(){
  const B=D.brands, hi=B.filter(b=>b.t!=='НЧ');
  const rows=B.slice(0,120).map((b,i)=>`<tr class="clk" data-b="${i}">
    <td class="l ${b.t!=='НЧ'?'id':''}">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
    <td><b>${b.n}</b></td><td>${pos(b.best)}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td>
    <td>${b.nd}</td><td class="l mut">${b.groups.slice(0,3).join(', ')}${b.groups.length>3?' +'+(b.groups.length-3):''}</td>
    <td class="l mut">${Object.entries(b.cats).sort((x,y)=>y[1]-x[1]).slice(0,3).map(([k,v])=>k+' ×'+v).join(', ')}</td>
  </tr><tr class="det" hidden><td colspan="9"><div class="inner"></div></td></tr>`).join('');
  return `<div class="blk"><h2>Какие ключи взял каждый бренд</h2>
  <p class="note">Все ${D.tot.t10} ключей в ТОП-10 на последнем замере каждой группы.
  Клик по строке — конкретные запросы с позициями, доменами и группами.
  Показаны первые 120 брендов из ${B.length}.</p>
  <div class="tiles">
    <div class="tile"><div class="k">Брендов</div><div class="v">${B.length}</div>
      <div class="c">из 157 в справочнике</div></div>
    <div class="tile a"><div class="k">Ключей в ТОП-10</div><div class="v">${D.tot.t10}</div>
      <div class="c">по ${D.tot.doms} доменам</div></div>
    <div class="tile g"><div class="k">В ТОП-3</div><div class="v">${D.tot.t3}</div>
      <div class="c">${pc(D.tot.t3/D.tot.t10)} от ТОП-10</div></div>
    <div class="tile"><div class="k">Дорогих брендов</div><div class="v">${hi.length}</div>
      <div class="c">ВЧ и СЧ, ${hi.reduce((a,b)=>a+b.n,0)} ключей</div></div>
  </div>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
  <th>Ключей</th><th>Лучшая</th><th>ТОП-3</th><th>Доменов</th><th class="l">Группы</th>
  <th class="l">Типы запросов</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function tabCats(){
  const C=D.cats, tot=D.tot.t10;
  const rows=C.map((c,i)=>`<tr class="clk" data-c="${i}">
    <td class="l ${c.t10>50?'id':''}">${esc(c.c)}</td><td><b>${c.t10}</b></td>
    <td>${pc(c.t10/tot)}</td><td class="${c.t3?'good':'mut'}">${c.t3}</td>
  </tr><tr class="det" hidden><td colspan="4"><div class="inner"></div></td></tr>`).join('');
  const top=C[0], bare=C.find(x=>x.c==='бренд без добавок')||{t10:0};
  return `<div class="blk"><h2>Что за запросы заходят</h2>
  <p class="note">Каждый ключ отнесён к одному типу по первому совпавшему признаку:
  зеркало → вход → регистрация → офиц. сайт → бонус → играть → приложение → отзывы →
  «бренд + казино» → «бренд без добавок». Клик по строке — примеры.</p>
  <div class="tw"><table><thead><tr><th class="l">Тип запроса</th><th>В ТОП-10</th>
  <th>Доля</th><th>ТОП-3</th></tr></thead><tbody>${rows}</tbody></table></div>
  <p class="note" style="margin-top:10px">Картина та же, что была на 40 доменах:
  «${esc(top.c)}» держит ${pc(top.t10/tot)} всего ТОП-10, а голое название бренда —
  ${pc(bare.t10/tot)}. Выдачу по самому бренду держит сам бренд.</p></div>`;
}

function fill(){
  document.querySelectorAll('tr.clk[data-g]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1;
    const d=GR[tr.dataset.g].doms[+tr.dataset.i];
    if(!d.keys.length){slot.innerHTML='<h4>Ни одного ключа в ТОП-10</h4>';return;}
    slot.innerHTML=`<div><h4>Бренды в ТОП-10 — ${d.brands.length}</h4><div class="tw"><table>
      <thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th><th>Лучшая</th><th>Ключей</th>
      <th>ТОП-3</th></tr></thead><tbody>`+
      d.brands.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
        <td>${pos(b.best)}</td><td>${b.n}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td></tr>`).join('')+
      `</tbody></table></div></div>
      <div><h4>Ключи в ТОП-10 — ${d.keys.length}</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th class="l">Тип</th><th>Тир</th>
      <th>Объём</th><th>Поз.</th></tr></thead><tbody>`+
      d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
        <td class="l mut">${esc(k.c)}</td><td>${tg(k.t)}</td><td>${kf(k.v)}</td>
        <td>${pos(k.p)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
  document.querySelectorAll('tr.clk[data-b]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1;
    const b=D.brands[+tr.dataset.b];
    slot.innerHTML=`<div><h4>${esc(b.b)} — ${b.keys.length} ключей в ТОП-10</h4>
      <div class="tw"><table><thead><tr><th class="l">Ключ</th><th class="l">Тип</th>
      <th>Поз.</th><th class="l">Домен</th><th class="l">Группа</th></tr></thead><tbody>`+
      b.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.c)}</td>
        <td>${pos(k.p)}</td><td class="l num">${esc(k.d)}</td>
        <td class="l mut">${esc(k.g)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
  document.querySelectorAll('tr.clk[data-c]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1;
    const c=D.cats[+tr.dataset.c];
    slot.innerHTML=`<div><h4>Примеры — «${esc(c.c)}»</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th>Позиция</th></tr></thead><tbody>`+
      c.ex.map(e=>`<tr><td class="l">${esc(e.q)}</td><td class="l mut">${esc(e.b)}</td>
        <td>${pos(e.p)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
}

const TABS=[
  ["Обзор",overview],
  ["Ночные · 3 замера",()=>wave("ночь","Ночной запуск · 01:21–01:31",
     "Три замера: 01:29–01:41, 10:08–10:09 и 22:29–22:30. Клик по домену — бренды и ключи.")],
  ["Дневные · 2 замера",()=>wave("день","Дневной запуск · 17:21–17:22",
     "Два замера: 17:34–17:35 и 22:29. Клик по домену — бренды и ключи.",DAY_EXTRA)],
  ["Generation 50",()=>wave("вечер","Generation 50 · запуск 22:06",
     "Один замер в 22:29 — через 23 минуты после запуска.",GEN_EXTRA)],
  ["Бренды и ключи",tabBrands],
  ["Типы запросов",tabCats]];
const nav=document.getElementById('nav'), main=document.getElementById('main');
TABS.forEach(([name],i)=>{
  const b=document.createElement('button');
  b.textContent=name; b.setAttribute('role','tab'); b.setAttribute('aria-selected',i===0);
  b.onclick=()=>show(i); nav.appendChild(b);
  const s=document.createElement('section'); s.hidden=i!==0; main.appendChild(s);});
function show(i){
  [...nav.children].forEach((b,j)=>b.setAttribute('aria-selected',i===j));
  [...main.children].forEach((s,j)=>{s.hidden=i!==j;
    if(i===j&&!s.dataset.done){s.dataset.done=1;s.innerHTML=TABS[j][1]();fill();}});
  window.scrollTo({top:0,behavior:'instant'});}
main.insertAdjacentHTML('beforeend','<div class="foot">20.08.2026 · '+D.tot.groups+
  ' групп, '+D.tot.doms+' доменов · замеры 01:29–01:41, 10:08–10:09, 17:34–17:35 и 22:29–22:30 · '+
  'всё считано по ТОП-10 · ядро 1570 ключей, ВЧ ≥ 1 млн, СЧ 700k–1 млн, '+
  'бренды vovan и pari исключены</div>');
show(0);

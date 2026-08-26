const f=(x,d=2)=>Number(x).toFixed(d).replace('.',',');
const i=x=>String(x);
const G=D.g, by=k=>G.filter(g=>g.test===k), one=n=>G.find(g=>g.name===n);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const ratio=(a,b)=>{if(!b&&!a)return '—';if(!b)return 'только у одной';return f(a/b,2)+'×';};

/* ---------- общая таблица ---------- */
function overview(){
  const rows=G.map(g=>`<tr class="clk" data-k="${esc(g.name)}">
    <td class="l"><b>${esc(g.name)}</b><div class="mut sm">${esc(g.cfg)}</div></td>
    <td>${g.ntm}</td><td class="${g.mean>=3?'good':g.mean<1?'bad':''}">${f(g.mean)}</td>
    <td>${f(g.med,1)}</td><td class="${g.wo>=3?'good':g.wo<1?'bad':''}">${f(g.wo)}</td>
    <td>${g.t3}</td><td>${g.t30}</td><td>${g.t100}</td><td>${g.vch+g.sch}</td>
    <td class="l mono sm">${g.vals.join(', ')}</td></tr>
    <tr class="det" hidden><td colspan="10"><div class="inner">${domTable(g)}</div></td></tr>`).join('');
  return `<div class="tw"><table><thead><tr>
    <th class="l">Ветка</th><th>.team</th><th>Т10/дом</th><th>Медиана</th><th>Без лидера</th>
    <th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ+СЧ</th><th class="l">Ключей в Т10 по доменам</th>
    </tr></thead><tbody>${rows}</tbody></table></div>`;
}
function domTable(g){
  const rows=g.doms.map(d=>`<tr><td class="l">${esc(d.d)}${d.tm?'':' <span class="tag t-НЧ">не .team</span>'}</td>
    <td>${d.t3}</td><td class="${d.t10?'good':'mut'}">${d.t10}</td><td>${d.t30}</td><td>${d.t100}</td>
    <td>${d.vch}</td><td>${d.sch}</td><td>${d.nb}</td>
    <td class="l sm">${d.keys.slice(0,6).map(k=>`<span class="kq">${esc(k.q)} <b>${k.p}</b></span>`).join(' ')||'<span class="mut">—</span>'}</td></tr>`).join('');
  return `<h4>${esc(g.name)}${g.arm&&g.test==='G'?' · '+esc(g.arm):''} · снимок ${esc(g.lab)} · ${esc(g.cfg)}</h4>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т3</th><th>Т10</th><th>Т30</th><th>Т100</th>
  <th>ВЧ</th><th>СЧ</th><th>Брендов</th><th class="l">Лучшие ключи в Т10</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

/* ---------- тест G ---------- */
function testG(){
  const A=one('ТЕСТ G · A'),A2=one('ТЕСТ G · A2'),B=one('ТЕСТ G · B'),B2=one('ТЕСТ G · B2'),
        C=one('ТЕСТ G · C'),C2=one('ТЕСТ G · C2');
  const pool=(x,y)=>({mean:(x.vals.concat(y.vals).reduce((a,b)=>a+b,0))/(x.ntm+y.ntm),
                      t30:x.t30+y.t30,t100:x.t100+y.t100,n:x.ntm+y.ntm});
  const pA=pool(A,A2),pB=pool(B,B2),pC=pool(C,C2);
  const conf=[['A · старый стиль',A,A2,pA],['B · новый, без картинок',B,B2,pB],['C · новый + картинки',C,C2,pC]];
  return `
  <div class="blk">
    <h2>Тест G — три конфигурации генератора, каждая в двух партиях</h2>
    <p class="note">Единственный тест за всё наблюдение, где каждая конфигурация запущена дважды.
    Повтор нужен был ровно для одного: узнать, что больше — разница между конфигурациями
    или разброс между партиями одной и той же конфигурации. Ответ получен.</p>
    <div class="tiles">
      <div class="tile a"><div class="k">A против A2</div><div class="v">15×</div><div class="c">одна конфигурация, две партии</div></div>
      <div class="tile"><div class="k">A против B+C</div><div class="v">${f(pA.mean/((pB.mean+pC.mean)/2||0.001),1)}×</div><div class="c">между конфигурациями</div></div>
      <div class="tile b"><div class="k">Ветки на нуле</div><div class="v">4 из 6</div><div class="c">без лидера ровно 0,00</div></div>
      <div class="tile"><div class="k">Домены</div><div class="v">30</div><div class="c">по 5 на партию, все .team</div></div>
    </div>
    <div class="card acc" style="margin-bottom:22px">
      <h3>Что показал повтор</h3>
      <p>Партия <b>A</b> дала 6,00 ключей в ТОП-10 на домен. Партия <b>A2</b> — та же конфигурация,
      те же пять доменов по объёму — дала <b>0,40</b>. Разрыв внутри одной конфигурации
      <b class="warn">15×</b>, перестановочный тест по доменам p&nbsp;=&nbsp;0,012.</p>
      <p>Разрыв между конфигурациями меньше: A против B+C даёт 3,20 против 0,25, p&nbsp;=&nbsp;0,002 —
      но весь этот перевес держится на одной партии A. Вторая партия той же конфигурации
      (0,40) от веток B и C <b>неотличима</b>.</p>
      <p class="cl">Вывод: на этих объёмах конфигурация генератора не определяет результат — определяет партия.
      Если бы «старый стиль» был лучше сам по себе, поднялись бы обе его партии. Поднялась одна.</p>
    </div>
    <h3 class="sh">Партия 1 против партии 2 внутри каждой конфигурации</h3>
    <div class="tw"><table><thead><tr><th class="l">Конфигурация</th><th>Партия 1</th><th>Партия 2</th>
    <th>Разрыв</th><th>Пул, 10 дом.</th><th>Т30 пул</th><th>Т100 пул</th></tr></thead><tbody>
    ${conf.map(([n,x,y,p])=>`<tr><td class="l"><b>${esc(n)}</b></td>
      <td class="${x.mean>1?'good':''}">${f(x.mean)}</td><td class="${y.mean>1?'good':''}">${f(y.mean)}</td>
      <td class="${x.mean/Math.max(y.mean,0.001)>3||y.mean/Math.max(x.mean,0.001)>3?'warn':'mut'}">${ratio(Math.max(x.mean,y.mean),Math.min(x.mean,y.mean))}</td>
      <td><b>${f(p.mean)}</b></td><td>${p.t30}</td><td>${p.t100}</td></tr>`).join('')}
    </tbody></table></div>
    <p class="note" style="margin-top:12px">Разрыв внутри A (15×) больше, чем разрыв между лучшей и худшей
    конфигурацией по пулам (${f(pA.mean/Math.max(pC.mean,0.001),0)}×). Пока это так, сравнивать A, B и C между собой бессмысленно.</p>
    <h3 class="sh">Все шесть партий по доменам</h3>
    ${[A,A2,B,B2,C,C2].map(g=>`<div class="mini">${domTable(g)}</div>`).join('')}
  </div>`;
}

/* ---------- парные тесты ---------- */
function pairBlock(title,note,a,b,extra){
  const cmp=(k,int)=>{const x=a[k],y=b[k];
    const w=x>y?'a':(y>x?'b':'-');
    return `<tr><td class="l">${LBL[k]}</td>
      <td class="${w==='a'?'good':''}">${int?i(x):f(x)}</td>
      <td class="${w==='b'?'good':''}">${int?i(y):f(y)}</td>
      <td class="mut">${w==='-'?'вровень':ratio(Math.max(x,y),Math.min(x,y))+' за «'+(w==='a'?a.arm:b.arm)+'»'}</td></tr>`;};
  return `<div class="blk"><h2>${esc(title)}</h2><p class="note">${note}</p>
  <div class="tw"><table><thead><tr><th class="l">Показатель</th>
    <th>${esc(a.arm)}<div class="mut sm">${a.ntm} дом.</div></th>
    <th>${esc(b.arm)}<div class="mut sm">${b.ntm} дом.</div></th><th class="l">Кто выше</th></tr></thead><tbody>
    ${cmp('mean')}${cmp('wo')}${cmp('med')}${cmp('t3',1)}${cmp('t30',1)}${cmp('t100',1)}${cmp('vs',1)}
  </tbody></table></div>
  ${extra?`<div class="card" style="margin-top:18px">${extra}</div>`:''}
  <div class="mini">${domTable(a)}</div><div class="mini">${domTable(b)}</div></div>`;
}
const LBL={mean:'Ключей в ТОП-10 на домен',wo:'То же, без лидера',med:'Медиана по доменам',
  t3:'Ключей в ТОП-3, всего',t30:'Ключей в ТОП-30, всего',t100:'Ключей в ТОП-100, всего',vs:'ВЧ+СЧ в ТОП-10'};
G.forEach(g=>g.vs=g.vch+g.sch);

/* ---------- сборка ---------- */
const SEC={
 over:`<div class="blk"><h2>Все одиннадцать веток</h2>
   <p class="note">Один съём, 26.08 23:54–23:57. Все листы сняты в одно окно — сравнение между ветками
   не искажено временем съёма. Только <code>.team</code>. Строка раскрывается по клику.</p>
   ${overview()}
   <div class="card" style="margin-top:22px"><h3>Что видно сразу</h3>
   <p>Чужой контент держит уровень 3,7–5,0 ключа в ТОП-10 на домен во всех четырёх ветках.
   Генератор даёт 1,23 в среднем по своим 30 доменам, и почти весь этот результат —
   одна партия из шести.</p>
   <p>Контрольная группа на нуле: пять доменов из семи не имеют вообще ни одного ключа в ТОП-100.
   Это не слабый результат, это отсутствие индексации — разбор ниже.</p></div></div>`,
 g:testG(),
 f:pairBlock('Тест F — даты при включённых картинках',
   'Семейство NEW33, чужой контент, 12 страниц, картинки в обеих ветках. Прогоны разведены одной-четырьмя минутами — конструкция чистая. Это независимое повторение теста A, который до сих пор был единственной сошедшейся находкой.',
   one('ТЕСТ F · без дат'),one('ТЕСТ F · с датами'),
   `<h3>Направление то же, величина меньше</h3>
    <p>«Без дат» впереди по обоим измерениям, но всего в 1,16× по среднему и 1,05× без лидера —
    против 2,9× и 3,9× в тесте A на предыдущей паре. На счётчике ТОП-10 разница почти исчезла.</p>
    <p>Зато она сохранилась на качестве позиций: <b>ТОП-3 — 24 против 10</b> (2,4×),
    <b>ВЧ+СЧ в ТОП-10 — 13 против 2</b> (6,5×). То есть «без дат» заходит на те же объёмы,
    но выше и по более дорогим брендам.</p>
    <p class="cl">Читать как подтверждение направления, но не величины. Одного съёма мало:
    в тесте A разрыв рос от съёма к съёму, здесь пока только первая точка.</p>`),
 e:pairBlock('Тест E — картинки в чужом контенте',
   'Семейство NEW17, три минуты между прогонами, у каждого домена свой текст с обеих сторон. Самая чистая пара за всё наблюдение по конструкции.',
   one('ТЕСТ E · без картинок'),one('ТЕСТ E · с картинками'),
   `<h3>Перевес у картинок, но внутри шума</h3>
    <p>С картинками выше по среднему (1,12×) и заметнее без лидера (1,67×), по ТОП-30 — 2,4×.
    При этом ТОП-3 у ветки без картинок даже больше (11 против 9), и держат его два домена.</p>
    <p>При 6 и 9 доменах на ветку читаются различия примерно от 2×. Здесь ни одно из измерений
    туда не дотягивает, кроме ТОП-30.</p>
    <p class="cl">Шестой заход на вопрос картинок и снова без вердикта — но впервые
    конструкция такая, что второй съём сможет дать ответ. Ждём 12-часовую точку.</p>`),
 ctrl:(()=>{const c=one('КОНТРОЛЬ');return `<div class="blk">
   <h2>Контроль — третья дата запуска прогона 21.08</h2>
   <p class="note">Контенты <code>NEW50_5_7pages_nodate_21.08 _18…_24</code>, id 808-814, созданы 21.08 в 13:29 —
   та же минута и тот же прогон генерации, что у ветки, запущенной 25.08.</p>
   <div class="tiles">
     <div class="tile b"><div class="k">Ключей в ТОП-10</div><div class="v">0</div><div class="c">на всех семи доменах</div></div>
     <div class="tile b"><div class="k">Доменов без единого ключа</div><div class="v">5 из 7</div><div class="c">пусто даже в ТОП-100</div></div>
     <div class="tile"><div class="k">Всего ключей в Т100</div><div class="v">9</div><div class="c">против 964 у запуска 25.08</div></div>
     <div class="tile"><div class="k">Запуск 25.08 на 6 часах</div><div class="v">22,62</div><div class="c">тот же прогон контента</div></div>
   </div>
   <div class="card acc"><h3>Это почти наверняка ранний съём, а не провал</h3>
   <p>Пять доменов из семи не имеют <b>ни одного</b> ключа в ТОП-100. Провалившийся запуск
   выглядит иначе: домены присутствуют в выдаче, но низко. Здесь их в выдаче нет вообще —
   так выглядит группа, которую ещё не проиндексировали.</p>
   <p>Остальные десять листов того же файла сняты полностью и данными покрыты
   (проверка по четвертям ядра пройдена), так что обрезанной выгрузки здесь нет —
   краулер отработал, находить было нечего.</p>
   <p class="cl">Вывод по контролю отложен до второго съёма. Если и на 12 часах будет ноль —
   тогда это результат, и он означает, что прогон 21.08 исчерпан.</p></div>
   <div class="mini">${domTable(c)}</div></div>`})(),
 read:`<div class="blk"><h2>Как это читать</h2>
   <div class="grid2">
   <div class="card"><h3>Что в расчёте</h3>
   <p>Только домены <code>.team</code>. Бренды <code>vovan</code> и <code>pari</code> вне ядра.
   Домены <code>5374.team</code> и <code>2535.team</code> исключены по договорённости —
   в сегодняшних группах их нет.</p>
   <p>Метрика — число ключей ядра, где домен стоит в ТОП-10. «Без лидера» — среднее по ветке
   без самого сильного домена: показывает, тянет ветка массой или одним выстрелом.</p></div>
   <div class="card"><h3>Проверка выгрузки</h3>
   <p>На каждом листе один снимок; второй блок — «Среднее по съёмам», это не съём и в расчёт не идёт.</p>
   <p>Все одиннадцать листов проверены на обрыв краулинга: данные лежат во всех четырёх
   четвертях ядра из 1570 ключей. Обрезанных выгрузок в файле нет.</p></div>
   <div class="card warn-c"><h3>Главное ограничение — не прислано время выкладки</h3>
   <p>Возраст групп на момент съёма неизвестен и почти наверняка разный: контенты NEW33 созданы
   25.08 в 18:30, NEW17 — 26.08 в 14:06, у групп генератора время не присылалось вовсе.</p>
   <p>Поэтому <b>сравнивать ветки внутри пары можно</b> — обе половины пары запущены вместе.
   А сравнивать чужой контент с генератором или контроль с чем угодно — <b>нельзя</b>,
   пока не известно, кто на сколько старше.</p></div>
   <div class="card"><h3>Что даст второй съём</h3>
   <p>Тест E — направление по картинкам, если разрыв дорастёт до 2×.<br>
   Тест F — растёт ли разрыв по датам, как он рос в тесте A.<br>
   Тест G — держится ли партия A или садится, как остальные пять.<br>
   Контроль — индексация или пустота.</p></div>
   </div></div>`
};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}
document.addEventListener('click',e=>{const tr=e.target.closest('tr.clk'); if(!tr)return;
  const d=tr.nextElementSibling; if(d&&d.classList.contains('det')) d.hidden=!d.hidden;});

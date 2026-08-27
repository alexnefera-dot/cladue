const f=(x,d=2)=>Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const R=(a,b)=>{if(!b&&!a)return '—';if(!b)return 'только у одной';return f(a/b,2)+'×';};
const G=D.g, one=n=>G.find(g=>g.name===n);
const S1=g=>g.snaps[0], S2=g=>g.snaps[1];
const arrow=(a,b)=>b>a?'<span class="good">↑</span>':(b<a?'<span class="bad">↓</span>':'<span class="mut">→</span>');

function domTable(g,i){
  const s=g.snaps[i], o=g.snaps[1-i];
  const rows=s.doms.map(d=>{const was=o.per10[d.d];
    return `<tr><td class="l">${esc(d.d)}${d.tm?'':' <span class="tag t-НЧ">не .team</span>'}</td>
    <td class="mut">${was}</td><td class="${d.t10?'good':'mut'}">${d.t10}</td>
    <td>${d.t3}</td><td>${d.t30}</td><td>${d.t100}</td><td>${d.vch}</td><td>${d.sch}</td><td>${d.nb}</td>
    <td class="l sm">${d.keys.slice(0,6).map(k=>`<span class="kq">${esc(k.q)} <b>${k.p}</b></span>`).join(' ')||'<span class="mut">—</span>'}</td></tr>`}).join('');
  return `<h4>${esc(g.name)}${g.test==='G'?' · '+esc(g.arm):''} · съём 2, ${esc(s.lab)} · ${esc(g.cfg)}</h4>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т10 съём 1</th><th>Т10 съём 2</th>
  <th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ</th><th>СЧ</th><th>Брендов</th><th class="l">Лучшие ключи в Т10</th></tr></thead>
  <tbody>${rows}</tbody></table></div>`;
}

function overview(){
  const rows=G.map(g=>{const a=S1(g),b=S2(g);
    return `<tr class="clk">
    <td class="l"><b>${esc(g.name)}</b><div class="mut sm">${esc(g.cfg)}</div></td>
    <td>${b.ntm}</td>
    <td class="mut">${f(a.mean)}</td><td class="${b.mean>=5?'good':b.mean<1?'bad':''}"><b>${f(b.mean)}</b></td><td>${arrow(a.mean,b.mean)}</td>
    <td class="mut">${f(a.wo)}</td><td class="${b.wo>=4?'good':b.wo<1?'bad':''}"><b>${f(b.wo)}</b></td>
    <td>${a.t3}→${b.t3}</td><td>${a.t30}→${b.t30}</td><td>${a.t100}→${b.t100}</td><td>${a.vch+a.sch}→${b.vch+b.sch}</td>
    <td class="l mono sm">${b.vals.join(', ')}</td></tr>
    <tr class="det" hidden><td colspan="12"><div class="inner">${domTable(g,1)}</div></td></tr>`}).join('');
  return `<div class="tw"><table><thead>
    <tr><th class="l" rowspan="2">Ветка</th><th rowspan="2">.team</th><th colspan="3">Т10 на домен</th>
    <th colspan="2">Без лидера</th><th rowspan="2">Т3</th><th rowspan="2">Т30</th><th rowspan="2">Т100</th>
    <th rowspan="2">ВЧ+СЧ</th><th class="l" rowspan="2">Ключей в Т10, съём 2</th></tr>
    <tr><th>съём 1</th><th>съём 2</th><th></th><th>съём 1</th><th>съём 2</th></tr>
    </thead><tbody>${rows}</tbody></table></div>`;
}

function testG(){
  const N=['ТЕСТ G · A','ТЕСТ G · A2','ТЕСТ G · B','ТЕСТ G · B2','ТЕСТ G · C','ТЕСТ G · C2'].map(one);
  const [A,A2,B,B2,C,C2]=N;
  const pool=(x,y,i)=>{const v=x.snaps[i].vals.concat(y.snaps[i].vals);return v.reduce((a,b)=>a+b,0)/v.length;};
  const conf=[['A · старый стиль',A,A2],['B · новый, без картинок',B,B2],['C · новый + картинки',C,C2]];
  return `<div class="blk">
  <h2>Тест G — повтор партий, вторая точка</h2>
  <p class="note">Три конфигурации генератора, каждая в двух независимых партиях. Съём 1 показал,
  что разрыв внутри конфигурации сопоставим с разрывом между конфигурациями. Съём 2 показывает больше:
  порядок партий внутри конфигурации <b>переворачивается</b> за двенадцать часов.</p>
  <div class="tiles">
    <div class="tile b"><div class="k">C против C2</div><div class="v">↔</div><div class="c">съём 1: 0,40 / 0,00 · съём 2: 1,00 / 3,20 — порядок сменился</div></div>
    <div class="tile b"><div class="k">B против B2</div><div class="v">↔</div><div class="c">съём 1: 0,40 / 0,20 · съём 2: 0,20 / 0,80 — тоже сменился</div></div>
    <div class="tile a"><div class="k">A против A2</div><div class="v">6,5×</div><div class="c">разрыв внутри одной конфигурации на съёме 2</div></div>
    <div class="tile"><div class="k">Пулы, 10 доменов</div><div class="v">6,0 / 2,1 / 0,5</div><div class="c">A · C · B</div></div>
  </div>
  <div class="card acc" style="margin-bottom:22px">
    <h3>Что добавил второй съём</h3>
    <p>Формально порядок конфигураций теперь A&nbsp;›&nbsp;C&nbsp;›&nbsp;B: пулы по 10 доменов —
    6,00, 2,10 и 0,50. Но статистика разделяет только крайние: A против B p&nbsp;=&nbsp;0,008,
    A против C p&nbsp;=&nbsp;0,15, C против B p&nbsp;=&nbsp;0,07.</p>
    <p>И весь перевес A по-прежнему держит одна партия: <b>A даёт 10,40, A2 — 1,60</b>.
    Партия A2 ниже пула конфигурации C. Второй месяц подряд одно и то же:
    поднимается партия, не настройка.</p>
    <p>Новое и решающее: <b>у двух конфигураций из трёх партии поменялись местами за 12 часов.</b>
    На съёме 1 C была впереди C2 (0,40 против 0,00), на съёме 2 — позади (1,00 против 3,20).
    То же у B и B2. Значит и порядок партий внутри конфигурации нестабилен во времени.</p>
    <p class="cl">Вывод не изменился, а укрепился: на пяти доменах партия шумит сильнее,
    чем различаются конфигурации. Чтобы сравнивать A, B и C, нужно не по две партии,
    а по пять-шесть — либо судить их по конверсиям, а не по позициям.</p>
  </div>
  <h3 class="sh">Партия 1 против партии 2 — оба съёма</h3>
  <div class="tw"><table><thead><tr><th class="l">Конфигурация</th>
    <th>П1 съём 1</th><th>П2 съём 1</th><th>П1 съём 2</th><th>П2 съём 2</th>
    <th>Порядок</th><th>Пул съём 1</th><th>Пул съём 2</th></tr></thead><tbody>
  ${conf.map(([n,x,y])=>{
    const a1=S1(x).mean,b1=S1(y).mean,a2=S2(x).mean,b2=S2(y).mean;
    const flip=((a1-b1)>0)!==((a2-b2)>0)&&(a1-b1)!==0&&(a2-b2)!==0;
    return `<tr><td class="l"><b>${esc(n)}</b></td>
    <td class="mut">${f(a1)}</td><td class="mut">${f(b1)}</td>
    <td class="${a2>b2?'good':''}">${f(a2)}</td><td class="${b2>a2?'good':''}">${f(b2)}</td>
    <td class="${flip?'bad':'mut'}">${flip?'перевернулся':'сохранился'}</td>
    <td class="mut">${f(pool(x,y,0))}</td><td><b>${f(pool(x,y,1))}</b></td></tr>`}).join('')}
  </tbody></table></div>
  <h3 class="sh">Все шесть партий по доменам, съём 2</h3>
  ${N.map(g=>`<div class="mini">${domTable(g,1)}</div>`).join('')}
  </div>`;
}

const LBL={mean:'Ключей в ТОП-10 на домен',wo:'То же, без лидера',med:'Медиана по доменам',
  t3:'Ключей в ТОП-3',t30:'Ключей в ТОП-30',t100:'Ключей в ТОП-100',vs:'ВЧ+СЧ в ТОП-10'};
G.forEach(g=>g.snaps.forEach(s=>s.vs=s.vch+s.sch));

function pairBlock(title,note,a,b,extra){
  const row=(k,int)=>{const A1=S1(a)[k],B1=S1(b)[k],A2=S2(a)[k],B2=S2(b)[k];
    const w1=A1>B1?'a':(B1>A1?'b':'-'), w2=A2>B2?'a':(B2>A2?'b':'-');
    const fm=x=>int?String(x):f(x);
    return `<tr><td class="l">${LBL[k]}</td>
      <td class="${w1==='a'?'good':'mut'}">${fm(A1)}</td><td class="${w1==='b'?'good':'mut'}">${fm(B1)}</td>
      <td class="sm ${w1==='-'?'mut':''}">${w1==='-'?'вровень':R(Math.max(A1,B1),Math.min(A1,B1))+' · '+(w1==='a'?a.arm:b.arm)}</td>
      <td class="${w2==='a'?'good':''}"><b>${fm(A2)}</b></td><td class="${w2==='b'?'good':''}"><b>${fm(B2)}</b></td>
      <td class="sm ${w2==='-'?'mut':''}">${w2==='-'?'вровень':R(Math.max(A2,B2),Math.min(A2,B2))+' · '+(w2==='a'?a.arm:b.arm)}</td>
      <td class="${w1===w2?'good':'bad'} sm">${w1===w2?'совпало':'перевернулось'}</td></tr>`;};
  return `<div class="blk"><h2>${esc(title)}</h2><p class="note">${note}</p>
  <div class="tw"><table><thead>
  <tr><th class="l" rowspan="2">Показатель</th><th colspan="3">Съём 1 · 26.08 23:5x</th>
      <th colspan="3">Съём 2 · 27.08 12:1x</th><th rowspan="2">Направление</th></tr>
  <tr><th>${esc(a.arm)}</th><th>${esc(b.arm)}</th><th class="l">Кто выше</th>
      <th>${esc(a.arm)}</th><th>${esc(b.arm)}</th><th class="l">Кто выше</th></tr></thead><tbody>
  ${row('mean')}${row('wo')}${row('med')}${row('t3',1)}${row('t30',1)}${row('t100',1)}${row('vs',1)}
  </tbody></table></div>
  ${extra?`<div class="card" style="margin-top:18px">${extra}</div>`:''}
  <div class="mini">${domTable(a,1)}</div><div class="mini">${domTable(b,1)}</div></div>`;
}

const ctrl=one('КОНТРОЛЬ');
const SEC={
 over:`<div class="blk"><h2>Все ветки на обоих съёмах</h2>
   <p class="note">Съём 1 — 26.08 23:54–23:57, съём 2 — 27.08 12:16–12:18, разрыв около 12,5 часа.
   Все двадцать два снимка полные: данные во всех четырёх четвертях ядра из 1570 ключей.
   Только <code>.team</code>. Строка раскрывается по клику.</p>
   ${overview()}
   <div class="grid2" style="margin-top:22px">
   <div class="card"><h3>Выросли почти все</h3>
   <p>Десять веток из одиннадцати прибавили за 12 часов, единственное исключение —
   <b>B</b> (0,40&nbsp;→&nbsp;0,20). Контроль вышел из нуля: 0,00&nbsp;→&nbsp;4,71.</p>
   <p>При этом ТОП-100 у старых веток падает, а ТОП-10 растёт — то самое уплотнение
   верха с осыпанием хвоста, что видели на прошлой неделе. У свежепроиндексированных
   веток растёт и то и другое.</p></div>
   <div class="card"><h3>Чужой контент против генератора</h3>
   <p>По 46 доменам чужого контента — 7,89 ключа в ТОП-10 на домен, по 30 доменам
   генератора — 2,87. Разрыв 2,8×, p&nbsp;=&nbsp;0,004.</p>
   <p class="cl">В вывод это не идёт: возраст групп разный и неизвестен —
   контенты NEW33 созданы 25.08, NEW17 и генератор 26.08, время выкладки не присылалось.</p></div>
   </div></div>`,
 g:testG(),
 f:pairBlock('Тест F — даты при включённых картинках',
   'Семейство NEW33, чужой контент, 12 страниц, картинки в обеих ветках, прогоны разведены одной-четырьмя минутами. Независимое повторение теста A.',
   one('ТЕСТ F · без дат'),one('ТЕСТ F · с датами'),
   `<h3>Разрыв растёт — как рос в тесте A</h3>
    <p>На съёме 1 «без дат» было впереди едва заметно (1,16× по среднему, 1,05× без лидера).
    За двенадцать часов ветка прибавила почти вдвое — 5,00&nbsp;→&nbsp;9,20 — а ветка с датами
    только 4,31&nbsp;→&nbsp;5,25. Разрыв стал <b>1,75× по среднему и 1,56× без лидера</b>.</p>
    <p>На качестве позиций он ещё крупнее: <b>ТОП-3 — 38 против 8</b> (4,75×),
    <b>ВЧ+СЧ в ТОП-10 — 24 против 8</b> (3×).</p>
    <p>Перестановочный тест по доменам: p&nbsp;=&nbsp;0,35 на первом съёме,
    <b>p&nbsp;=&nbsp;0,10</b> на втором. Порога 0,05 нет, но траектория та же,
    что в тесте A, где разрыв тоже рос от съёма к съёму.</p>
    <p class="cl">Направление совпало по всем семи показателям на обоих съёмах.
    Это второе независимое подтверждение находки «без дат сильнее» — теперь при картинках.</p>`),
 e:pairBlock('Тест E — картинки в чужом контенте',
   'Семейство NEW17, три минуты между прогонами, у каждого домена свой текст. Самая чистая пара по конструкции за всё наблюдение.',
   one('ТЕСТ E · без картинок'),one('ТЕСТ E · с картинками'),
   `<h3>Впервые за шесть заходов направление не перевернулось</h3>
    <p>Картинки впереди на обоих съёмах и по среднему, и без лидера. Прежние четыре захода
    теста B меняли знак на каждом съёме — здесь знак устоял.</p>
    <p>Но величину нужно читать осторожно. Среднее 12,00 против 5,50 выглядит как 2,2×,
    и держит его <b>один домен</b>: <code>1520.team</code> прошёл 13&nbsp;→&nbsp;65.
    Без лидера разрыв куда скромнее — 5,38 против 3,40, то есть 1,58×,
    и он даже чуть сузился против съёма 1 (1,67×).</p>
    <p>Перестановочный тест: p&nbsp;=&nbsp;0,48 и p&nbsp;=&nbsp;0,32. При 6 и 9 доменах
    на ветку различия меньше двукратных здесь неразличимы.</p>
    <p class="cl">Итог: направление устойчиво впервые, величина — нет.
    Вопрос картинок решать по конверсиям либо повторять тест на 20+ доменах на ветку.</p>`),
 ctrl:`<div class="blk">
   <h2>Контроль — прогон 21.08 на третьей дате</h2>
   <p class="note">Контенты <code>NEW50_5_7pages_nodate_21.08 _18…_24</code>, id 808-814, созданы 21.08 в 13:29 —
   тот же прогон, что у ветки <code>_7…_17</code>, запущенной 25.08.</p>
   <div class="tiles">
     <div class="tile g"><div class="k">Съём 1 → съём 2</div><div class="v">0 → 4,71</div><div class="c">группа проиндексировалась</div></div>
     <div class="tile b"><div class="k">Запуск 25.08, тот же прогон</div><div class="v">22,62</div><div class="c">на шести часах</div></div>
     <div class="tile b"><div class="k">Отставание</div><div class="v">4,8×</div><div class="c">третья дата против второй</div></div>
     <div class="tile"><div class="k">ВЧ+СЧ в ТОП-10</div><div class="v">0</div><div class="c">против 28 у запуска 25.08</div></div>
   </div>
   <div class="card acc"><h3>Диагноз со съёма 1 подтвердился, но ответ на главный вопрос отрицательный</h3>
   <p>На первом съёме пять доменов из семи не имели ни одного ключа даже в ТОП-100,
   и я отложил вывод, предположив отсутствие индексации. Так и оказалось:
   за двенадцать часов ТОП-100 вырос с 9 до 234, ТОП-3 — с 0 до 11, брендов — с 0 до 14.
   Группа живая.</p>
   <p>Но уровень другой. Тот же прогон генерации, запущенный 25.08, дал <b>22,62</b>
   ключа в ТОП-10 на домен уже на шести часах и 19,00 на девятнадцати.
   Здесь на двенадцати часах — <b>4,71</b>, без лидера 2,67, и ни одного ВЧ или СЧ бренда
   в ТОП-10 против 28 у запуска 25.08.</p>
   <p class="cl">Это ответ на вопрос, открытый с 24.08: <b>прогон 21.08 на новой дате
   не воспроизвёлся.</b> Значит «прогон генерации» — не устойчивая единица:
   разные тексты одного прогона, запущенные в разные дни, дают результаты,
   отличающиеся в пять раз. Сравнивать группы, разнесённые по датам,
   на этом основании нельзя.</p></div>
   <div class="mini">${domTable(ctrl,1)}</div></div>`,
 read:`<div class="blk"><h2>Как это читать</h2>
   <div class="grid2">
   <div class="card"><h3>Что в расчёте</h3>
   <p>Только домены <code>.team</code>. Бренды <code>vovan</code> и <code>pari</code> вне ядра.
   Метрика — число ключей ядра, где домен стоит в ТОП-10.</p>
   <p>«Без лидера» — среднее по ветке без самого сильного домена. На малых ветках это
   главное измерение: одно попадание вроде <code>1520.team</code> с 65 ключами
   двигает среднее вдвое, а массу ветки — нет.</p></div>
   <div class="card"><h3>Проверка выгрузки</h3>
   <p>На каждом листе три блока: два снимка и «Среднее по съёмам» — последнее не съём
   и в расчёт не идёт.</p>
   <p>Все 22 снимка проверены на обрыв краулинга: данные лежат во всех четырёх
   четвертях ядра. Обрезанных выгрузок в файле нет.</p></div>
   <div class="card warn-c"><h3>Время выкладки по-прежнему не прислано</h3>
   <p>Возраст веток на момент съёма неизвестен и разный: контенты NEW33 созданы 25.08 в 18:30,
   NEW17 — 26.08 в 14:06, у групп генератора время не присылалось вовсе,
   контроль вообще проиндексировался только между съёмами.</p>
   <p>Поэтому сравнения <b>внутри пары</b> — тесты E, F, G — корректны: обе половины
   запущены вместе. Сравнения <b>между семействами</b> — нет.</p></div>
   <div class="card"><h3>Что осталось открытым</h3>
   <p><b>Тест E:</b> нужен третий съём или 20+ доменов на ветку.<br>
   <b>Тест F:</b> третий съём покажет, дорастёт ли разрыв до порога, как в тесте A.<br>
   <b>Тест G:</b> двух партий мало — нужно пять-шесть, либо судить по конверсиям.<br>
   <b>Контроль:</b> вопрос закрыт, ответ отрицательный.</p></div>
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

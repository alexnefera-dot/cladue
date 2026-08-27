const f=(x,d=2)=>Number(x).toFixed(d).replace('.',',');
const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const G=D.g, S=n=>G.find(g=>g.sheet===n);
const ar=(a,b)=>b>a?'<span class="good">↑</span>':(b<a?'<span class="bad">↓</span>':'<span class="mut">→</span>');
const su=(u,r)=>{if(!u)return '';const m=u.match(/^https?:\/\/([^/]+)(.*)$/);if(!m)return E(u);
  return r>1?`<span class="host">${E(m[1])}</span><span class="ruwarn">/ru ×${r}</span>`
            :`<span class="host">${E(m[1])}</span><span class="path">${E(m[2])||'/'}</span>`;};
const tri=(v,int)=>v.map((x,i)=>`<span class="${i<v.length-1?'mut':(x?'':'bad')}">${int?x:f(x)}</span>`).join('<span class="ar">→</span>');

function domTable(g){
  const L=g.snaps.length, s=g.snaps[L-1];
  const hist=d=>g.snaps.map(x=>(x.doms.find(r=>r.d===d)||{t10:0}).t10);
  const h100=d=>g.snaps.map(x=>(x.doms.find(r=>r.d===d)||{t100:0}).t100);
  return `<div class="tw"><table><thead><tr><th class="l">Домен</th>
   <th class="l">Т10 по съёмам</th><th class="l">Т100 по съёмам</th><th>Т3</th><th>Т30</th><th>Брендов</th>
   <th>Лучшая</th><th>Макс /ru</th><th class="l">Ключи в ТОП-30 и страница</th></tr></thead><tbody>
   ${s.doms.map(r=>`<tr>
     <td class="l"><b class="dm">${E(r.d)}</b></td>
     <td class="l mono">${tri(hist(r.d),1)}</td><td class="l mono">${tri(h100(r.d),1)}</td>
     <td>${r.t3}</td><td>${r.t30}</td><td>${r.nb}</td>
     <td class="${r.best&&r.best<=10?'ok':'mut'}">${r.best??'—'}</td>
     <td class="${r.rumax>15?'bad':(r.rumax>1?'warn':'good')}">${r.rumax}</td>
     <td class="l sm">${r.keys.filter(k=>k.p<=30).slice(0,5).map(k=>
       `<div class="kl"><b class="${k.p<=3?'p3':(k.p<=10?'p10':'p30')}">${k.p}</b> <span class="q">${E(k.q)}</span>
        <span class="br t-${k.t}">${E(k.b)}</span> ${su(k.u,k.ru)}</div>`).join('')||'<span class="mut">—</span>'}</td>
   </tr>`).join('')}</tbody></table></div>`;
}
function card(g){
  return `<div class="gcard"><div class="gh"><h3>${E(g.name)}</h3><span class="mut sm">${E(g.cfg)}</span></div>
   <div class="meta">
     <div><span class="mk">контент создан</span><span class="mv">${E(g.made)}</span></div>
     <div><span class="mk">возраст по съёмам</span><span class="mv">${E(g.ages)}</span></div>
     <div><span class="mk">ядро</span><span class="mv">${g.core}</span></div>
     <div><span class="mk">доменов</span><span class="mv">${g.snaps[0].n}</span></div></div>
   <div class="tw"><table><thead><tr><th class="l">Съём</th><th>Т10/дом</th><th>Медиана</th><th>Без лидера</th>
     <th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ</th><th>СЧ</th><th>Брендов</th>
     <th>URL</th><th>Грязных</th><th>Мед /ru</th><th>Макс</th><th class="l">Ключей в Т10 по доменам</th></tr></thead><tbody>
     ${g.snaps.map(x=>`<tr><td class="l">${E(x.lab)}</td>
       <td class="${x.mean>=1?'good':(x.mean?'':'bad')}"><b>${f(x.mean)}</b></td><td>${f(x.med,1)}</td><td>${f(x.wo)}</td>
       <td>${x.t3}</td><td>${x.t30}</td><td class="${x.t100?'':'bad'}">${x.t100}</td><td>${x.vch}</td><td>${x.sch}</td><td>${x.nb}</td>
       <td>${x.nurl}</td><td class="${x.nurl&&x.dirty/x.nurl>0.5?'bad':(x.dirty?'warn':'good')}">${x.nurl?Math.round(100*x.dirty/x.nurl)+'%':'—'}</td>
       <td class="${x.rumed>5?'bad':'good'}">${x.rumed}</td>
       <td class="${x.rumax>15?'bad':(x.rumax?'warn':'good')}">${x.rumax}</td>
       <td class="l mono sm">${x.vals.join(', ')}</td></tr>`).join('')}
   </tbody></table></div>${domTable(g)}</div>`;
}
const secD=`<div class="blk">
 <h2>2535.team и 5374.team выпали из выдачи полностью</h2>
 <div class="tiles">
  <div class="tile b"><div class="k">2535.team · ключей в Т100</div><div class="v">121 → 107 → 0</div><div class="c">за 6 ч 44 мин</div></div>
  <div class="tile b"><div class="k">5374.team · ключей в Т100</div><div class="v">130 → 66 → 0</div><div class="c">за 6 ч 25 мин</div></div>
  <div class="tile"><div class="k">Проверка выгрузки</div><div class="v">пройдена</div><div class="c">1570 строк просмотрено, ноль позиций</div></div>
  <div class="tile a"><div class="k">Их глубина /ru</div><div class="v">90 и 81</div><div class="c">100% адресов с 16+ повторами</div></div>
 </div>
 <div class="card warn-c" style="margin-bottom:18px"><h3>Это не обрыв выгрузки</h3>
 <p>На съёме 28.08 00:30 у обоих доменов <b>ноль позиций на всех 1570 ключах</b> — не «мало»,
 а полное отсутствие. Все четверти ядра пусты. Остальные листы того же файла, снятые
 в ту же минуту, данными заполнены: у <code>7page_27.08</code> 286 строк с позициями,
 у накрутки 49. Краулер отработал — находить было нечего.</p>
 <p>Траектория падения: <code>2535</code> — 121 → 107 → <b>0</b>, <code>5374</code> — 131 → 66 → <b>0</b>.
 То есть это не мгновенный обвал, а спуск за две ступени и обрыв.</p></div>
 <div class="grid2">
 <div class="card acc"><h3>Что их объединяет</h3>
 <p>Это <b>ровно те два домена, у которых бесконечные пути раздулись сильнее всего</b>:
 медиана повторов <code>/ru</code> 90 и 81, максимум 255 у обоих, и <b>100% и 91% адресов
 в категории «16+ повторов»</b>. Ни у одного другого домена базы такого нет.</p>
 <p>Они же — самые старые из наблюдаемых: <code>2535</code> запущен 25.08,
 <code>5374</code> — 25.08 на контенте от 21.08. У них было больше всего времени
 на расползание.</p></div>
 <div class="card"><h3>Но связь пока не доказана</h3>
 <p>Доменов всего два, и оба были исключены из расчётов ещё 26 августа — по твоей просьбе,
 без объяснения причины. Если исключение было связано с тем, что с ними уже
 что-то происходило, то последовательность «раздулись → выпали» может быть
 совпадением или общим следствием третьей причины.</p>
 <p class="cl">Что решает вопрос: домены накрутки (<code>gjtz</code>, <code>2679</code>)
 живут с медианой 20 и держатся. Новые группы 27.08 сейчас на медиане 3-5 и растут
 по 20 пунктов в сутки. Если через день-два они пойдут тем же путём —
 связь подтвердится. Пока это гипотеза.</p></div>
 </div>
 ${[S('2535.team'),S('5374.team')].map(card).join('')}
</div>`;
const secU=`<div class="blk">
 <h2>Накопление ускоряется, но потери позиций не подтвердились</h2>
 <div class="tw"><table><thead><tr><th class="l">Запуск</th><th class="l">Съём</th><th>URL</th>
  <th>0-1</th><th>2-5</th><th>6-15</th><th>16+</th><th>Доля грязных</th><th>Медиана</th><th>Максимум</th></tr></thead><tbody>
  ${['7page_27.08','Generator_11page_old_27.08','Накрутка leebet banda','1 сайт на тест'].map(k=>{const g=S(k);
   return g.snaps.filter(s=>s.nurl).map((s,i)=>`<tr><td class="l">${i?'':`<b>${E(g.name)}</b>`}</td>
    <td class="l sm">${E(s.lab)}</td><td>${s.nurl}</td>
    <td class="good">${s.buck['0-1']||0}</td><td>${s.buck['2-5']||0}</td>
    <td class="${s.buck['6-15']?'warn':'mut'}">${s.buck['6-15']||0}</td>
    <td class="${s.buck['16+']?'bad':'mut'}">${s.buck['16+']||0}</td>
    <td class="${s.dirty/s.nurl>0.5?'bad':'warn'}"><b>${Math.round(100*s.dirty/s.nurl)}%</b></td>
    <td class="${s.rumed>5?'bad':'good'}">${s.rumed}</td>
    <td class="${s.rumax>15?'bad':'warn'}">${s.rumax}</td></tr>`).join('')}).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:18px">
 <div class="card warn-c"><h3>Скорость расползания растёт</h3>
 <p><code>7page</code>: доля адресов с повторами <b>35% → 38% → 52%</b>, максимум <b>5 → 26 → 49</b>,
 адресов с 16+ повторами <b>0 → 15 → 136</b>.</p>
 <p><code>Generator_11page_old</code>: <b>13% → 32% → 62%</b>, максимум <b>4 → 18 → 20</b>,
 16+ повторов <b>0 → 7 → 53</b>.</p>
 <p class="cl">За семь часов от чистых адресов до большинства грязных.
 Если экстраполировать, через двое суток эти домены придут туда же,
 где сейчас 2535 и 5374 — медиана 80-90.</p></div>
 <div class="card"><h3>Поправка: вчерашний вывод про потерю позиций не подтвердился</h3>
 <p>Вчера на данных второго съёма я показал, что чистые адреса стоят на 66,8,
 а грязные на 72,7 — разрыв 5,9 позиции, p&nbsp;=&nbsp;0,004. <b>На третьем съёме
 этого нет:</b> 67,9 против 67,5, разрыв −0,4, p&nbsp;=&nbsp;0,59.</p>
 <div class="tw"><table><thead><tr><th class="l">Глубина /ru</th><th>URL</th><th>Медиана</th>
   <th>Средняя</th><th>В Т30</th><th>В Т10</th></tr></thead><tbody>
   ${D.dep.map(d=>`<tr><td class="l">${E(d.lab)}</td><td>${d.n}</td><td>${d.med}</td>
    <td>${f(d.mean,1)}</td><td>${d.t30} <span class="mut">(${Math.round(100*d.t30/d.n)}%)</span></td>
    <td>${d.t10}</td></tr>`).join('')}</tbody></table></div>
 <p style="margin-top:10px">На парах внутри домена и бренда разрыв тоже усох:
 медиана потери была 12,5 позиции при 14 случаях из 21, стала <b>5,0 при 21 из 37</b>.</p>
 <p class="cl">Правильная формулировка: <b>накопление путей — факт</b>,
 а <b>цена в позициях на отдельном ключе — нет</b>. Опасность не в том, что грязный
 адрес стоит ниже, а в том, что домен размывается на бесконечное число дублей.
 Чем это кончается — видно на 2535 и 5374.</p></div>
 </div>
</div>`;
const secN=`<div class="blk">
 <h2>Запуски 27.08 — третий съём, обе группы растут</h2>
 <div class="tiles">
  <div class="tile g"><div class="k">7page · Т10 на домен</div><div class="v">0,48 → 0,33 → 1,29</div><div class="c">без лидера 0,95</div></div>
  <div class="tile g"><div class="k">11page_old · Т10 на домен</div><div class="v">0,00 → 0,40 → 1,70</div><div class="c">без лидера 1,44</div></div>
  <div class="tile a"><div class="k">11page обгоняет 7page</div><div class="v">1,7 против 1,3</div><div class="c">и по без-лидера 1,44 против 0,95</div></div>
  <div class="tile"><div class="k">Партии 7page</div><div class="v">1,45 / 1,10</div><div class="c">разрыв 1,3× — в пределах шума</div></div>
 </div>
 <div class="card acc" style="margin-bottom:18px"><h3>Обе группы вышли на рабочий уровень</h3>
 <p>За семь часов <code>7page</code> прошёл 0,48 → 0,33 → <b>1,29</b> ключа в ТОП-10 на домен,
 ТОП-30 — 20 → 35 → <b>100</b>, ТОП-100 — 54 → 344 → <b>662</b>.
 <code>Generator_11page_old</code> — 0,00 → 0,40 → <b>1,70</b>, ТОП-100 15 → 139 → 223.</p>
 <p><b>11-страничная группа обгоняет 7-страничную</b> и по среднему (1,70 против 1,29),
 и по без-лидера (1,44 против 0,95) — при том что она на час моложе.
 Это согласуется с историческим правилом «больше страниц лучше», но на одной паре
 и одном съёме вывода не делаю.</p>
 <p class="cl">Разрыв между партиями 7page: был 3,6×, потом исчез, теперь 1,3×
 (1,45 против 1,10). Три съёма — три разных ответа. Ровно то, ради чего
 нужны повторы: на десяти доменах партия не измеряется.</p></div>
 ${[S('7page|п1'),S('7page|п2'),S('7page_27.08'),S('Generator_11page_old_27.08')].filter(Boolean).map(card).join('')}
</div>`;
const secK=`<div class="blk">
 <h2>Накрутка и o0c.team</h2>
 <div class="grid2" style="margin-bottom:18px">
 <div class="card acc"><h3>Накрутка: откат остановился</h3>
 <p><code>2679.team</code> по ТОП-10: <b>29 → 20 → 25</b>. Вчерашний откат не продолжился,
 уровень стабилизировался примерно на четверти ниже пика. ТОП-3 держится на 5,
 брендов в десятке 9, ВЧ+СЧ выросли до 17.</p>
 <p><code>gjtz.team</code>, который два съёма не отзывался, <b>наконец сдвинулся</b>:
 ТОП-10 2 → 2 → <b>5</b>, появился первый ТОП-3, брендов в десятке 1 → 4.
 При этом ТОП-100 продолжает падать: 31 → 15 → 10.</p>
 <p class="cl">То есть на gjtz картина обратная 2679: ядро сжимается, но то,
 что осталось, поднимается выше. Третий съём меняет вчерашний вывод «не отзывается»
 на «отзывается медленнее и по-другому».</p></div>
 <div class="card"><h3>o0c.team держится</h3>
 <p>Шестой съём, возраст 8 часов 23 минуты: ТОП-100 38 → <b>32</b>, ТОП-30 2 → 2,
 и появился <b>первый ключ в ТОП-10</b> (позиция 9).</p>
 <p>Напомню измерение: четыре съёма до 1,5 часов — полный ноль, на 5,6 часах — 38 ключей.
 Окно входа в индекс между 1,5 и 5,6 часами, дальше уровень держится.</p>
 <p class="cl">Максимум повторов <code>/ru</code> у него 20 и не растёт между
 двумя последними съёмами — единственный домен, где расползание пока встало.</p></div>
 </div>
 ${[S('Накрутка leebet banda'),S('1 сайт на тест')].map(card).join('')}
</div>`;
const SEC={d:secD,u:secU,n:secN,k:secK};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}

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

const secN=`<div class="blk">
 <h2>Четвёртый съём — один домен вытянул всё, остальное сжимается</h2>
 <div class="tiles">
  <div class="tile a"><div class="k">1893.team · ТОП-10</div><div class="v">0 → 0 → 8 → 87</div><div class="c">15 в ТОП-3, 229 ключей в сотне, 38 брендов</div></div>
  <div class="tile"><div class="k">7page · Т10 на домен</div><div class="v">1,29 → 7,14</div><div class="c">без лидера всего 3,15</div></div>
  <div class="tile b"><div class="k">7page · партия 1</div><div class="v">1,10 → 0,70</div><div class="c">Т100 230 → 121, пошла вниз</div></div>
  <div class="tile b"><div class="k">Generator_11page_old</div><div class="v">1,70 → 1,40</div><div class="c">Т100 223 → 83, пик пройден</div></div>
 </div>
 <div class="card acc" style="margin-bottom:18px"><h3>Весь рост — это один домен из двадцати одного</h3>
 <p><code>1893.team</code> прошёл по ТОП-10 путь <b>0 → 0 → 8 → 87</b> и вытащил среднее по группе
 с 1,29 до 7,14. Значения по доменам на съёме 4: <b>87</b>, 25, 9, 9, 6, 4, 3, 2, 2, 1, 1, 1 и девять нулей.
 Без лидера группа даёт 3,15 — тоже рост, но втрое скромнее.</p>
 <p><b>Партия 2 против партии 1: 13,00 против 0,70.</b> Разрыв 18,6×, и он почти целиком
 сидит в одном домене: без лидера 5,60 против 0,33. При этом <b>партия 1 не выросла, а упала</b> —
 Т100 с 230 до 121, Т10 с 1,10 до 0,70.</p>
 <p class="cl">За четыре съёма разрыв между партиями 7page был 3,6× → исчез → 1,3× → 18,6×.
 Четыре съёма — четыре разных ответа. Это не тест конфигурации, это наблюдение
 за тем, как один домен из двадцати одного выстрелил, а остальные двадцать нет.
 Ровно архивное правило: успех — связка «текст + домен + момент», а не свойство формата.</p></div>
 <div class="card warn-c" style="margin-bottom:18px"><h3>Всё остальное сжимается</h3>
 <p>Из 21 домена 7page у <b>четырнадцати ТОП-100 упал</b> между третьим и четвёртым съёмом:
 <code>2084</code> 50 → 19, <code>glhd</code> 44 → 15, <code>2745</code> 43 → 10,
 <code>7186</code> 34 → 7, <code>1524</code> 23 → 9.</p>
 <p><code>Generator_11page_old</code> прошёл пик и пошёл вниз по всем показателям:
 Т10/дом 1,70 → 1,40, без лидера 1,44 → 0,78, ТОП-30 29 → 18, ТОП-100 223 → 83.
 У семи доменов из десяти ТОП-100 сократился.</p>
 <p><code>o0c.team</code>: ТОП-100 38 → 32 → <b>9</b>. Тоже вниз.</p></div>
 ${[S('7page|п1'),S('7page|п2'),S('7page_27.08'),S('Generator_11page_old_27.08')].filter(Boolean).map(card).join('')}
</div>`;
const secU=`<div class="blk">
 <h2>Расползание ускорилось, но гипотеза «дубли топят позиции» опровергнута</h2>
 <div class="tiles">
  <div class="tile b"><div class="k">7page · доля грязных</div><div class="v">52% → 87%</div><div class="c">за 12 часов</div></div>
  <div class="tile b"><div class="k">7page · медиана /ru</div><div class="v">3 → 24</div><div class="c">у 2535 перед смертью было 90</div></div>
  <div class="tile b"><div class="k">Адресов с 16+ повторами</div><div class="v">136 → 481</div><div class="c">из 637 всего</div></div>
  <div class="tile g"><div class="k">Позиции глубоких адресов</div><div class="v">лучше</div><div class="c">медиана 58 против 70 у чистых</div></div>
 </div>
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
 <div class="card warn-c"><h3>Скорость выросла ещё раз</h3>
 <p><code>7page</code>: доля грязных адресов <b>35% → 38% → 52% → 87%</b>,
 медиана повторов <b>0 → 0 → 3 → 24</b>, адресов с 16+ повторами <b>0 → 15 → 136 → 481</b>.</p>
 <p><code>Generator_11page_old</code>: <b>13% → 32% → 62% → 80%</b>, медиана <b>0 → 0 → 5 → 16</b>.</p>
 <p class="cl">За девятнадцать часов домены прошли от чистых адресов до медианы 24.
 У <code>2535.team</code> перед выпадением из индекса было 90. Если темп сохранится,
 эти домены придут туда за двое-трое суток.</p></div>
 <div class="card"><h3>Но глубина пути позиций не отнимает — наоборот</h3>
 <div class="tw"><table><thead><tr><th class="l">Глубина /ru</th><th>URL</th><th>Медиана</th>
   <th>Средняя</th><th>Т30</th><th>Т10</th><th>Т3</th></tr></thead><tbody>
   ${D.dep.map(d=>`<tr><td class="l">${E(d.lab)}</td><td>${d.n}</td>
    <td class="${d.lab.includes('16+')?'good':''}">${d.med}</td><td>${f(d.mean,1)}</td>
    <td>${d.t30}</td><td>${d.t10}</td><td>${d.t3}</td></tr>`).join('')}</tbody></table></div>
 <p style="margin-top:10px">На четвёртом съёме адреса с <b>16+ повторами стоят лучше чистых</b>:
 медиана 58 против 70, в ТОП-10 147 против 2, в ТОП-3 29 против нуля.</p>
 <p>Причина простая — это адреса <code>1893.team</code>, домена, который выстрелил.
 Его ключи в ТОП-3 стоят на путях <code>/ru×6</code>, <code>/ru×28</code>, <code>/ru×45</code>.
 Глубина здесь просто маркер «домен старше и расползся», а не причина позиции.</p>
 <p class="cl">Снимаю гипотезу целиком. За три съёма она дала p&nbsp;=&nbsp;0,004,
 потом p&nbsp;=&nbsp;0,59, теперь обратный знак. <b>Связи между глубиной пути
 и позицией отдельного ключа нет</b> — есть только сильная связь глубины с возрастом домена.
 Что остаётся в силе: расползание реально и быстро, и два самых расползшихся домена мертвы.</p></div>
 </div>
</div>`;
const secD=`<div class="blk">
 <h2>2535.team и 5374.team — второй съём подряд в нуле</h2>
 <div class="tiles">
  <div class="tile b"><div class="k">2535.team</div><div class="v">121 → 107 → 0 → 0</div><div class="c">ключей в ТОП-100</div></div>
  <div class="tile b"><div class="k">5374.team</div><div class="v">130 → 66 → 0 → 0</div><div class="c">ключей в ТОП-100</div></div>
  <div class="tile"><div class="k">Проверка</div><div class="v">пройдена</div><div class="c">1570 строк, все четверти пусты</div></div>
  <div class="tile"><div class="k">Прошло с обнуления</div><div class="v">12 часов</div><div class="c">восстановления нет</div></div>
 </div>
 <div class="card acc"><h3>Разовый сбой исключён</h3>
 <p>Второй съём подряд — ноль позиций на всех 1570 ключах у обоих доменов.
 В том же файле <code>7page</code> отдал 637 адресов, накрутка — 71.
 Выгрузка в порядке, домены мертвы.</p>
 <p>Напомню, что их объединяет: медиана повторов <code>/ru</code> <b>90 и 81</b>,
 максимум <b>255</b>, 100% и 92% адресов в категории «16+». Больше ни у кого такого нет —
 ближайший сейчас <code>7page</code> с медианой 24.</p>
 <p class="cl">Причинную связь по-прежнему считаю недоказанной: доменов два,
 и оба исключены из расчётов с 26 августа без объяснения причины.
 Но проверка идёт сама собой — <code>7page</code> и <code>Generator_11page_old</code>
 движутся к тем же значениям. Если они выпадут при медиане 80-90, вопрос закрыт.</p></div>
 ${[S('2535.team'),S('5374.team')].map(card).join('')}
</div>`;
const secK=`<div class="blk">
 <h2>Накрутка и o0c.team</h2>
 <div class="grid2" style="margin-bottom:18px">
 <div class="card"><h3>Накрутка сходит</h3>
 <p><code>2679.team</code> по ТОП-10: <b>29 → 20 → 25 → 21</b>, по ТОП-3 <b>13 → 5 → 5 → 2</b>.
 Верх осыпается, при этом ТОП-100 растёт: 48 → 28 → 39 → <b>60</b>. Ключи не уходят,
 они опускаются.</p>
 <p><code>gjtz.team</code>: ТОП-10 <b>2 → 2 → 5 → 0</b>. Вчерашний всплеск не удержался,
 домен вернулся в ноль по десятке, ТОП-100 держится на 11.</p>
 <p class="cl">Итог по накрутке за четыре съёма: эффект есть в первые часы,
 держится примерно сутки на уровне ниже пика, потом верх осыпается.
 Разовая накрутка позицию не закрепляет.</p></div>
 <div class="card"><h3>o0c.team пошёл вниз</h3>
 <p>Семь съёмов: ноль до 1,5 часов, 38 ключей на 5,6 часах, 32 на 8,4 часах,
 <b>9 на 20,6 часах</b>. Единственный ключ в ТОП-10 пропал.</p>
 <p class="cl">То есть сайт вошёл в индекс, продержался около суток и осыпался.
 Для одиночного домена без поддержки это нормальная траектория — но она показывает,
 что съём на 6 и 12 часов ловит пик, а не устойчивый уровень.</p></div>
 </div>
 ${[S('Накрутка leebet banda'),S('1 сайт на тест')].map(card).join('')}
</div>`;

const SEC={n:secN,u:secU,d:secD,k:secK};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}

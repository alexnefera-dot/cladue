const f=(x,d=2)=>Number(x).toFixed(d).replace('.',',');
const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const G=D.g, S=n=>G.find(g=>g.sheet===n);
const ar=(a,b)=>b>a?'<span class="good">↑</span>':(b<a?'<span class="bad">↓</span>':'<span class="mut">→</span>');
const su=(u,r)=>{if(!u)return '';const m=u.match(/^https?:\/\/([^/]+)(.*)$/);if(!m)return E(u);
  return r>1?`<span class="host">${E(m[1])}</span><span class="ruwarn">/ru ×${r}</span>`
            :`<span class="host">${E(m[1])}</span><span class="path">${E(m[2])||'/'}</span>`;};
const pair=(a,b,int)=>`<span class="mut">${int?a:f(a)}</span> ${ar(a,b)} <b class="${b>a?'good':(b<a?'bad':'')}">${int?b:f(b)}</b>`;

function domTable(g){
  const s1=g.snaps[0], s2=g.snaps[g.snaps.length-1];
  const m1=Object.fromEntries(s1.doms.map(r=>[r.d,r]));
  return `<div class="tw"><table><thead><tr><th class="l">Домен</th>
   <th>Т10</th><th>Т30</th><th>Т100</th><th>Т3</th><th>Брендов</th><th>Лучшая</th><th>Макс /ru</th>
   <th class="l">Ключи в ТОП-30 и страница</th></tr></thead><tbody>
   ${s2.doms.map(r=>{const o=m1[r.d]||{t10:0,t30:0,t100:0};return `<tr>
     <td class="l"><b class="dm">${E(r.d)}</b></td>
     <td>${pair(o.t10,r.t10,1)}</td><td>${pair(o.t30,r.t30,1)}</td><td>${pair(o.t100,r.t100,1)}</td>
     <td>${r.t3}</td><td>${r.nb}</td>
     <td class="${r.best&&r.best<=10?'ok':'mut'}">${r.best??'—'}</td>
     <td class="${r.rumax>5?'bad':(r.rumax?'warn':'good')}">${r.rumax}</td>
     <td class="l sm">${r.keys.filter(k=>k.p<=30).slice(0,5).map(k=>
       `<div class="kl"><b class="${k.p<=3?'p3':(k.p<=10?'p10':'p30')}">${k.p}</b> <span class="q">${E(k.q)}</span>
        <span class="br t-${k.t}">${E(k.b)}</span> ${su(k.u,k.ru)}</div>`).join('')||'<span class="mut">—</span>'}</td>
   </tr>`}).join('')}</tbody></table></div>`;
}
function card(g){
  return `<div class="gcard"><div class="gh"><h3>${E(g.name)}</h3><span class="mut sm">${E(g.cfg)}</span></div>
   <div class="meta">
     <div><span class="mk">контент создан</span><span class="mv">${E(g.made)}</span></div>
     <div><span class="mk">возраст</span><span class="mv">${E(g.ages)}</span></div>
     <div><span class="mk">ядро</span><span class="mv">${g.core}</span></div>
     <div><span class="mk">доменов</span><span class="mv">${g.snaps[0].n}</span></div></div>
   <div class="tw"><table><thead><tr><th class="l">Съём</th><th>Т10/дом</th><th>Медиана</th><th>Без лидера</th>
     <th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ</th><th>СЧ</th><th>Брендов</th>
     <th>URL</th><th>Мед. /ru</th><th>Макс</th><th class="l">Ключей в Т10 по доменам</th></tr></thead><tbody>
     ${g.snaps.map(x=>`<tr><td class="l">${E(x.lab)}</td>
       <td class="${x.mean>=1?'good':(x.mean?'':'bad')}"><b>${f(x.mean)}</b></td><td>${f(x.med,1)}</td><td>${f(x.wo)}</td>
       <td>${x.t3}</td><td>${x.t30}</td><td>${x.t100}</td><td>${x.vch}</td><td>${x.sch}</td><td>${x.nb}</td>
       <td>${x.nurl}</td><td class="${x.rumed>5?'bad':'good'}">${x.rumed}</td>
       <td class="${x.rumax>5?'bad':(x.rumax?'warn':'good')}">${x.rumax}</td>
       <td class="l mono sm">${x.vals.join(', ')}</td></tr>`).join('')}
   </tbody></table></div>${domTable(g)}</div>`;
}
const secN=`<div class="blk">
 <h2>Запуски 27.08 — второй съём</h2>
 <p class="note">Оба сняты по урезанному ядру 1049 ключей. Между съёмами ≈2 часа 15 минут.</p>
 <div class="tiles">
  <div class="tile g"><div class="k">7page · ТОП-100</div><div class="v">54 → 344</div><div class="c">домены вошли в индекс массово</div></div>
  <div class="tile b"><div class="k">7page · Т10 на домен</div><div class="v">0,48 → 0,33</div><div class="c">верх при этом просел</div></div>
  <div class="tile g"><div class="k">11page_old · ТОП-100</div><div class="v">15 → 139</div><div class="c">вышел из нуля: 0,00 → 0,40</div></div>
  <div class="tile"><div class="k">партии 7page</div><div class="v">схлопнулись</div><div class="c">0,73 / 0,20 → 0,36 / 0,30</div></div>
 </div>
 <div class="card acc" style="margin-bottom:20px"><h3>Индексация пошла, верх — нет</h3>
 <p>За два с небольшим часа <code>7page_27.08</code> вырос по ТОП-100 в <b>6,4 раза</b> (54 → 344),
 по ТОП-30 — с 20 до 35. Но ключей в ТОП-10 стало <b>меньше</b>: 0,48 → 0,33 на домен.
 То же у <code>Generator_11page_old</code>: ТОП-100 с 15 до 139, ТОП-30 с 3 до 26,
 при этом Т10 вырос всего с 0,00 до 0,40.</p>
 <p>Это нормальная механика первых часов — домены сначала попадают в сотню широким фронтом,
 верх формируется позже. Но у 7page верх именно <b>просел</b>, а не остался на месте,
 и ниже видно, почему.</p>
 <p class="cl">Разрыв между двумя партиями 7page, который на первом съёме был 3,6×
 (0,73 против 0,20), <b>исчез</b>: 0,36 против 0,30. Первый съём был шумом на пяти ключах.
 Это ровно та ловушка, о которой мы говорили весь месяц.</p></div>
 ${[S('7page_27.08|п1'),S('7page_27.08|п2'),S('7page_27.08'),S('Generator_11page_old_27.08')].filter(Boolean).map(card).join('')}
</div>`;
const acc=D.acc, dep=D.dep;
const secU=`<div class="blk">
 <h2>Ответ по бесконечным URL: пути накапливаются</h2>
 <p class="note">Вчера было два объяснения — либо в новом генераторе починено, либо пути копятся со временем.
 Второй съём отвечает однозначно.</p>
 <div class="tiles">
  <div class="tile b"><div class="k">7page · максимум /ru</div><div class="v">5 → 26</div><div class="c">за 2 часа 15 минут</div></div>
  <div class="tile b"><div class="k">11page_old · максимум</div><div class="v">4 → 18</div><div class="c">за 2 часа 15 минут</div></div>
  <div class="tile b"><div class="k">Адресов с 16+ повторами</div><div class="v">0 → 22</div><div class="c">категории не было вообще</div></div>
  <div class="tile a"><div class="k">Цена глубины</div><div class="v">−12,5</div><div class="c">медиана потери позиций на паре</div></div>
 </div>
 <div class="tw"><table><thead><tr><th class="l">Запуск</th><th class="l">Съём</th><th>URL</th>
  <th>0-1</th><th>2-5</th><th>6-15</th><th>16+</th><th>Медиана</th><th>Максимум</th></tr></thead><tbody>
  ${G.filter(g=>!g.sheet.includes('|')&&g.snaps.some(s=>s.nurl)).map(g=>g.snaps.filter(s=>s.nurl).map((s,i)=>
    `<tr><td class="l">${i?'':`<b>${E(g.name)}</b>`}</td><td class="l sm">${E(s.lab)}</td><td>${s.nurl}</td>
     <td class="good">${s.buck['0-1']||0}</td><td>${s.buck['2-5']||0}</td>
     <td class="${s.buck['6-15']?'warn':'mut'}">${s.buck['6-15']||0}</td>
     <td class="${s.buck['16+']?'bad':'mut'}">${s.buck['16+']||0}</td>
     <td class="${s.rumed>5?'bad':'good'}">${s.rumed}</td>
     <td class="${s.rumax>5?'bad':(s.rumax?'warn':'good')}">${s.rumax}</td></tr>`).join('')).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:18px">
 <div class="card warn-c"><h3>Одни и те же страницы уходят вглубь</h3>
 <p>Сравнение по совпадающим парам «домен + ключ» между двумя съёмами:
 у <code>7page</code> из 27 общих пар <b>5 стали глубже, ни одна не стала чище</b>.
 У остальных листов — либо без изменений, либо тоже только вглубь.</p>
 ${acc.filter(a=>a.sheet.startsWith('7page')&&a.ex.length).map(a=>a.ex.slice(0,3).map(e=>
   `<p class="urlex"><b>${E(e.d)}</b> · «${E(e.q)}» · позиция <b class="${e.p2>e.p1?'bad':'good'}">${e.p1} → ${e.p2}</b><br>
    было: ${E(e.u1).slice(0,60)} <span class="mut">(/ru ×${e.ru1})</span><br>
    стало: ${E(e.u2).slice(0,60)} <span class="ruwarn">/ru ×${e.ru2}</span></p>`).join('')).join('')}
 <p class="cl">Категории «16+ повторов» на первом съёме не было ни одной,
 на втором — 15 адресов у 7page и 7 у 11page_old. За два часа.</p></div>
 <div class="card"><h3>Глубина стоит позиций</h3>
 <div class="tw"><table><thead><tr><th class="l">Глубина /ru</th><th>URL</th><th>Медиана позиции</th>
  <th>Средняя</th><th>В ТОП-30</th></tr></thead><tbody>
  ${dep.map(d=>`<tr><td class="l">${E(d.lab)}</td><td>${d.n}</td><td class="${d.lab.includes('чистый')?'good':''}">${d.med}</td>
   <td>${f(d.mean,1)}</td><td>${d.t30}</td></tr>`).join('')}</tbody></table></div>
 <p style="margin-top:10px">Чистые адреса стоят в среднем на <b>66,8</b>, адреса с повторами — на <b>72,7</b>.
 Разрыв 5,9 позиции, перестановочный тест <b>p = 0,004</b>.</p>
 <p>Ещё жёстче на парах: там, где у одного домена по одному бренду есть и чистый адрес,
 и адрес с повторами, глубокий проигрывает в <b>14 случаях из 21</b>,
 медиана потери — <b>12,5 позиции</b>.</p>
 <p class="cl">Самый наглядный случай: <code>casinora.dprz.team/</code> стоял на <b>6-й</b>,
 через два часа тот же контент отдался как <code>/ru/ru/ru/ru/ru</code> и упал на <b>83-ю</b>.</p></div>
 </div>
 <div class="card acc" style="margin-top:14px"><h3>Что с этим делать</h3>
 <p>Проблема не в контенте и не в формате — в генераторе, который отдаёт 200 по любому
 количеству повторов <code>/ru</code>. Пока это так, каждый домен со временем расплывается
 на бесконечное число дублей, и часть ключей уходит на дубль вместо канонической страницы.</p>
 <p>Минимум: отдавать 404 или 301 на канонический адрес при втором и последующих
 <code>/ru</code> в пути. Это ровно та причина, по которой у <code>2535.team</code>
 медиана 90 повторов, а максимум 255 — домену двое суток, и он расползался всё это время.</p></div>
</div>`;
const secK=`<div class="blk">
 <h2>Накрутка откатилась, оба исключённых домена падают</h2>
 <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Съёмы</th>
  <th>Т3</th><th>Т10</th><th>Т30</th><th>Т100</th><th>Брендов в Т10</th></tr></thead><tbody>
  ${['Накрутка leebet banda','2535.team','5374.team'].flatMap(sh=>{const g=S(sh);
    return g.snaps[0].doms.map(r0=>{const r=g.snaps[1].doms.find(x=>x.d===r0.d);
    return `<tr><td class="l"><b class="dm">${E(r0.d)}</b><div class="mut sm">${E(g.cfg)}</div></td>
      <td class="l sm mut">${E(g.snaps[0].lab)} → ${E(g.snaps[1].lab)}</td>
      <td>${pair(r0.t3,r.t3,1)}</td><td>${pair(r0.t10,r.t10,1)}</td>
      <td>${pair(r0.t30,r.t30,1)}</td><td>${pair(r0.t100,r.t100,1)}</td>
      <td>${pair(r0.nb,r.nb,1)}</td></tr>`})}).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:18px">
 <div class="card acc"><h3>Накрутка держалась шесть часов и осыпалась за три</h3>
 <p><code>2679.team</code> в 18:23 показал ТОП-3 = 13 и ТОП-10 = 29 — я вчера писал,
 что накрутка сработала. Через <b>3 часа 23 минуты</b>: ТОП-3 = <b>5</b>, ТОП-10 = <b>20</b>,
 ТОП-100 с 48 до 28, брендов в десятке с 10 до 7.</p>
 <p><code>gjtz.team</code> как не отзывался, так и не отзывается: ТОП-10 держится на 2,
 ТОП-100 с 31 до 15.</p>
 <p class="cl">Вывод по накрутке меняю: эффект был, но <b>нестойкий</b>.
 Судить по одному съёму нельзя — на 2679 пик пришёлся ровно на первый замер.
 Нужен съём завтра, чтобы понять, где встанет уровень.</p></div>
 <div class="card"><h3>2535 и 5374 идут вниз оба</h3>
 <p><code>2535.team</code>: ТОП-3 с 28 до 18, ТОП-10 с 59 до 49, ТОП-100 с 121 до 107.
 Вчерашний рекорд базы сдувается.</p>
 <p><code>5374.team</code>: ТОП-3 с 6 до 3, ТОП-10 с 24 до 12, ТОП-100 <b>с 130 до 66</b> —
 половина ядра выпала из сотни за четыре часа.</p>
 <p class="cl">У обоих медиана повторов <code>/ru</code> — 90 и 81, максимум 255.
 Это те самые домены, которые расползлись сильнее всех, и они же сейчас теряют быстрее всех.
 Совпадение или причина — покажет третий съём.</p></div>
 </div>
 ${[S('Накрутка leebet banda'),S('2535.team'),S('5374.team')].map(card).join('')}
</div>`;
const o=S('1 сайт на тест');
const secT=`<div class="blk">
 <h2>o0c.team — сайт вошёл в индекс между 1,5 и 5,6 часами</h2>
 <div class="tw"><table><thead><tr><th class="l">Съём</th><th>Возраст</th><th>Т10</th><th>Т30</th><th>Т100</th>
  <th>URL</th><th>Макс /ru</th></tr></thead><tbody>
  ${o.snaps.map((s,i)=>`<tr><td class="l">${E(s.lab)}</td>
   <td class="mut sm">${['8 мин','41 мин','1 ч 11 мин','1 ч 32 мин','5 ч 39 мин'][i]}</td>
   <td class="${s.mean?'good':'mut'}">${f(s.mean,0)}</td><td>${s.t30}</td>
   <td class="${s.t100?'good':'mut'}"><b>${s.t100}</b></td><td>${s.nurl}</td>
   <td class="${s.rumax>5?'bad':(s.rumax?'warn':'good')}">${s.rumax}</td></tr>`).join('')}
 </tbody></table></div>
 <div class="card acc" style="margin-top:16px"><h3>Первое прямое измерение времени индексации</h3>
 <p>Четыре съёма подряд — 8 минут, 41 минута, 1 ч 11 мин, 1 ч 32 мин — <b>полный ноль</b>.
 Пятый, через <b>5 часов 39 минут</b>, — 38 ключей в ТОП-100 и 2 в ТОП-30.</p>
 <p>Значит окно входа в индекс лежит между полутора и пятью с половиной часами.
 Раньше шести часов снимать бессмысленно — это подтверждает выбранный график 6 и 12 часов.</p>
 <p class="cl">И сразу же: у свежего домена в первом же непустом съёме <b>максимум 20 повторов</b>
 <code>/ru</code>. То есть пути начинают копиться с самого начала, ещё до появления позиций.</p></div>
 ${card(o)}
</div>`;
const SEC={n:secN,u:secU,k:secK,t:secT};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}

const f=(x,d=2)=>Number(x).toFixed(d).replace('.',',');
const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const G=D.g, S=n=>G.find(g=>g.sheet===n||g.name===n);
const arrow=(a,b)=>b>a?'<span class="good">↑</span>':(b<a?'<span class="bad">↓</span>':'<span class="mut">→</span>');
const shortU=u=>{if(!u)return '';const m=u.match(/^https?:\/\/([^/]+)(.*)$/);if(!m)return E(u);
  const p=m[2],n=(p.match(/\/ru(?=\/|$)/g)||[]).length;
  return n>1?`<span class="host">${E(m[1])}</span><span class="ruwarn">/ru ×${n}</span>`
            :`<span class="host">${E(m[1])}</span><span class="path">${E(p)||'/'}</span>`;};

function domTable(g,s){
  return `<div class="tw"><table><thead><tr><th class="l">Домен</th><th>Т3</th><th>Т10</th><th>Т30</th>
   <th>Т100</th><th>ВЧ</th><th>СЧ</th><th>Брендов</th><th>Лучшая</th>
   <th class="l">Ключи в ТОП-10 и страница, которая ранжируется</th></tr></thead><tbody>
   ${s.doms.map(r=>`<tr>
     <td class="l"><b class="dm">${E(r.d)}</b></td>
     <td>${r.t3}</td><td class="${r.t10?'good':'mut'}"><b>${r.t10}</b></td><td>${r.t30}</td><td>${r.t100}</td>
     <td>${r.vch}</td><td>${r.sch}</td><td>${r.nb}</td>
     <td class="${r.best&&r.best<=3?'good':(r.best&&r.best<=10?'ok':'mut')}">${r.best??'—'}</td>
     <td class="l sm">${r.keys.filter(k=>k.p<=10).slice(0,6).map(k=>
       `<div class="kl"><b class="${k.p<=3?'p3':'p10'}">${k.p}</b> <span class="q">${E(k.q)}</span>
        <span class="br t-${k.t}">${E(k.b)}</span> ${shortU(k.u)}</div>`).join('')||'<span class="mut">—</span>'}</td>
   </tr>`).join('')}</tbody></table></div>`;
}
function card(g){
  const s=g.snaps[g.snaps.length-1];
  return `<div class="gcard"><div class="gh"><h3>${E(g.name)}</h3>
   <span class="mut sm">${E(g.cfg)}</span></div>
   <div class="meta">
     <div><span class="mk">контент создан</span><span class="mv">${E(g.made)}</span></div>
     <div><span class="mk">возраст на съёме</span><span class="mv">${E(g.age)}</span></div>
     <div><span class="mk">ядро</span><span class="mv">${g.core} ключей</span></div>
     <div><span class="mk">доменов</span><span class="mv">${s.n}</span></div>
     <div><span class="mk">съёмов</span><span class="mv">${g.snaps.length}</span></div>
   </div>
   <div class="tw"><table><thead><tr><th class="l">Съём</th><th>Т10/дом</th><th>Медиана</th><th>Без лидера</th>
     <th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ</th><th>СЧ</th><th class="l">Ключей в Т10 по доменам</th></tr></thead><tbody>
     ${g.snaps.map(x=>`<tr><td class="l">${E(x.lab)}</td>
       <td class="${x.mean>=1?'good':'bad'}"><b>${f(x.mean)}</b></td><td>${f(x.med,1)}</td><td>${f(x.wo)}</td>
       <td>${x.t3}</td><td>${x.t30}</td><td>${x.t100}</td><td>${x.vch}</td><td>${x.sch}</td>
       <td class="l mono sm">${x.vals.join(', ')}</td></tr>`).join('')}
   </tbody></table></div>
   ${s.nurl?`<div class="ruline">URL: ${s.nurl} шт · повторов <code>/ru/</code> — медиана <b class="${s.rumed>5?'bad':'good'}">${s.rumed}</b>, максимум <b class="${s.rumax>5?'bad':'good'}">${s.rumax}</b> · чистых адресов ${s.ruclean} из ${s.nurl}</div>`:''}
   ${domTable(g,s)}</div>`;
}
const secNew=`<div class="blk">
 <h2>Запуски 27 августа — первый съём</h2>
 <p class="note">Оба съёма сделаны по <b>урезанному ядру в 1049 ключей</b> — тому, что мы отобрали сегодня
 (ранжировался в 5+ съёмах, минус цифровой и домен-мусор). Числа не сопоставимы напрямую
 с историей на 1570 ключах.</p>
 <div class="tiles">
   <div class="tile"><div class="k">7page_27.08</div><div class="v">0,48</div><div class="c">Т10 на домен, 21 домен, возраст ≈2 часа</div></div>
   <div class="tile b"><div class="k">Generator_11page_old</div><div class="v">0,00</div><div class="c">ни одного ключа в ТОП-10, возраст ≈1 ч 10 мин</div></div>
   <div class="tile a"><div class="k">партия 2 против партии 1</div><div class="v">3,6×</div><div class="c">0,73 против 0,20 внутри 7page</div></div>
   <div class="tile g"><div class="k">URL новых сборок</div><div class="v">чистые</div><div class="c">медиана повторов /ru — 0</div></div>
 </div>
 <div class="card warn-c" style="margin-bottom:20px"><h3>Возраст слишком мал для вердикта</h3>
 <p>7page снят через ≈2 часа после создания контента, 11page_old — через ≈1 час 10 минут.
 По истории на таком возрасте нормальные значения 0–1 ключа на домен: например
 <code>NEW50_5_7pages_nodate</code> дала 0,50 на двух часах, <code>Generation 50</code> — 0,02.
 Нули у 11-страничной группы <b>не признак провала</b>, а признак того, что съём ранний.</p>
 <p class="cl">Единственное, что уже читается — <b>разрыв между двумя партиями 7page</b>:
 0,73 против 0,20 при одинаковом формате и получасовой разнице в генерации.
 Партия 2 дала 16 ключей в ТОП-30 против 4 у партии 1.</p></div>
 ${[S('split:партия 1 · 7page_N_1 · id 1004-1013'),S('split:партия 2 · 7page_N · id не присланы')].filter(Boolean).map(card).join('')}
 ${card(S('7page_27.08'))}
 ${card(S('Generator_11page_old_27.08'))}
</div>`;
const C=D.cmp, cm=d=>C.find(x=>x.d===d);
const cmpRow=x=>`<tr><td class="l"><b class="dm">${E(x.d)}</b><div class="mut sm">${E(x.group)}</div></td>
  <td class="l sm mut">${E(x.oldlab)} → ${E(x.newlab)}</td>
  ${['t3','t10','t30','t100'].map(k=>`<td><span class="mut">${x.old[k]}</span> ${arrow(x.old[k],x.new[k])} <b class="${x.new[k]>x.old[k]?'good':(x.new[k]<x.old[k]?'bad':'')}">${x.new[k]}</b></td>`).join('')}</tr>`;
const secNak=`<div class="blk">
 <h2>Накрутка leebet / banda и пересъём исключённых доменов</h2>
 <p class="note">Все четыре сняты по полному ядру 1570 ключей.</p>
 <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Съёмы</th>
   <th>Т3</th><th>Т10</th><th>Т30</th><th>Т100</th></tr></thead><tbody>
   ${['2679.team','gjtz.team','2535.team','5374.team'].map(d=>cmpRow(cm(d))).join('')}</tbody></table></div>
 <div class="grid2" style="margin-top:18px">
 <div class="card acc"><h3>Накрутка сработала на одном домене из двух</h3>
 <p><b>2679.team</b> за шесть часов: ТОП-3 с <b>0 до 13</b>, ТОП-10 с 14 до <b>29</b>.
 Целевой бренд <code>banda</code> вырос с 2 до <b>7</b> ключей в десятке, к нему подтянулись
 <code>marathon</code> 2→6, <code>spinto</code> 1→5, <code>bitz</code> 1→3.
 Девять ВЧ и пять СЧ брендов в ТОП-10.</p>
 <p><b>gjtz.team</b> за те же шесть часов: ТОП-10 с 4 до <b>2</b>, ТОП-100 с 37 до 31.
 Целевой <code>leebet</code> — с 3 до 2 ключей. Эффекта нет, скорее откат.</p>
 <p class="cl">Разница между доменами: у 2679 в ТОП-10 десять разных брендов,
 у gjtz — только <code>leebet</code>. Домен, у которого уже была широкая база,
 отозвался на накрутку; узкий — нет.</p></div>
 <div class="card"><h3>Исключённые домены разошлись в разные стороны</h3>
 <p><b>2535.team</b> за сутки: ТОП-3 с 3 до <b>28</b>, ТОП-10 с 26 до <b>59</b>.
 Это лучший результат домена за всё наблюдение.</p>
 <p><b>5374.team</b> за те же сутки: ТОП-3 с 15 до <b>6</b>, ТОП-10 с 50 до <b>24</b> — падение вдвое.
 При этом ТОП-100 держится: 126 → 130.</p>
 <p class="cl">Оба по-прежнему исключены из расчётов по групповым метрикам.
 Возвращать или нет — вопрос открытый, но 2535 сейчас сильнейший домен базы.</p></div>
 </div>
 ${card(S('Накрутка leebet banda'))}
 ${card(S('2535.team'))}
 ${card(S('5374.team'))}
</div>`;
const secURL=`<div class="blk">
 <h2>URL: бесконечные пути <code>/ru/ru/ru/…</code></h2>
 <p class="note">Новый формат выгрузки впервые показывает, <b>какой страницей</b> домен ранжируется.
 Это сразу вскрыло структурную проблему старых сборок.</p>
 <div class="tw"><table><thead><tr><th class="l">Запуск</th><th>URL в съёме</th>
   <th>Медиана повторов /ru</th><th>Максимум</th><th>Чистых адресов</th></tr></thead><tbody>
   ${G.filter(g=>g.snaps[g.snaps.length-1].nurl).map(g=>{const s=g.snaps[g.snaps.length-1];
     return `<tr><td class="l"><b>${E(g.name)}</b><div class="mut sm">${E(g.cfg)}</div></td>
     <td>${s.nurl}</td><td class="${s.rumed>5?'bad':'good'}"><b>${s.rumed}</b></td>
     <td class="${s.rumax>5?'bad':'good'}">${s.rumax}</td>
     <td>${s.ruclean} <span class="mut">(${Math.round(100*s.ruclean/s.nurl)}%)</span></td></tr>`}).join('')}
 </tbody></table></div>
 <div class="grid2" style="margin-top:18px">
 <div class="card warn-c"><h3>Старые сборки генерируют бесконечные адреса</h3>
 <p>У <code>2535.team</code> медиана — <b>90 повторов</b> <code>/ru</code> в адресе,
 у <code>5374.team</code> — <b>81</b>, максимум у обоих <b>255</b>. Пример:</p>
 <p class="urlex">https://cryptoboss.2535.team<span class="ruwarn">/ru ×255</span></p>
 <p>Из 399 адресов во всей выгрузке <b>340 (85%)</b> содержат повтор <code>/ru</code>.
 Один и тот же контент доступен по бесконечному числу адресов — классическая ловушка
 для краулера и размытие сигнала между дублями.</p></div>
 <div class="card"><h3>В новых сборках 27.08 этого нет</h3>
 <p>У <code>7page_27.08</code> и <code>Generator_11page_old_27.08</code> медиана повторов — <b>0</b>,
 максимум 4-5. Адреса нормальные:</p>
 <p class="urlex">https://kilogram.dprz.team<span class="path">/registracia</span> — позиция 1<br>
 https://casinora.cnwv.team<span class="path">/</span> — позиция 5<br>
 https://bitstarz.bmtq.team<span class="path">/registracia</span> — позиция 14</p>
 <p class="cl">То есть проблема либо уже починена в новом генераторе, либо копится со временем
 и на возрасте в час ещё не проявилась. Проверить это можно на втором съёме
 сегодняшних групп — если медиана вырастет, значит пути накапливаются.</p></div>
 </div>
 <div class="card" style="margin-top:14px"><h3>Структура: бренд на поддомене</h3>
 <p>Все 399 адресов — на поддоменах вида <code>бренд.домен.team</code>:
 <code>banda.2679.team</code>, <code>kilogram.dprz.team</code>, <code>leebet.gjtz.team</code>,
 <code>casinora.cnwv.team</code>. Один домен обслуживает десятки брендов, каждый на своём поддомене.</p>
 <p>Связи между глубиной пути и позицией не видно: медиана повторов у ключей в ТОП-3 — 46,
 у ключей на 31-100 — 26. Глубина скорее свойство домена, чем причина позиции.</p></div>
</div>`;
const secTest=`<div class="blk">
 <h2>«1 сайт на тест» — o0c.team</h2>
 <p class="note">Отдельный лист с четырьмя съёмами за 1 час 24 минуты и колонкой URL на каждый съём —
 задумано как наблюдение за тем, какой страницей домен ранжируется и как она меняется.</p>
 <div class="card warn-c"><h3>Все четыре съёма пустые</h3>
 <p>Домен создан 27.08 в 16:07, съёмы в 16:15, 16:48, 17:18 и 17:39 — то есть
 <b>через 8 минут, 41 минуту, 1 час 11 минут и 1 час 32 минуты</b> после создания.
 Ни одной позиции в первой сотне ни на одном из 1570 ключей.</p>
 <p>Это ожидаемо: самый ранний результат в истории наблюдения — <code>Generation 50</code>
 с 0,02 ключа на домен на съёме через несколько часов. За полтора часа сайт
 просто не успевает попасть в индекс.</p>
 <p class="cl">Конструкция листа полезная — колонка URL по съёмам покажет смену
 ранжирующейся страницы. Но снимать его имеет смысл начиная часов с шести,
 иначе все ячейки будут пустыми.</p></div>
</div>`;
const SEC={n:secNew,k:secNak,u:secURL,t:secTest};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}

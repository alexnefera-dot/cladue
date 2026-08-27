const f=(x,d=2)=>Number(x).toFixed(d).replace('.',',');
const E=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const G=D.g, S=n=>G.find(g=>g.name===n), byT=(t,c)=>G.filter(g=>g.test===t&&(!c||g.coh===c));
const R=(a,b)=>(!b&&!a)?'—':(!b?'—':f(a/b,2)+'×');
const last=g=>g.snaps[g.good.length?g.good[g.good.length-1]:g.snaps.length-1];
const at=(g,i)=>g.snaps[i];

/* конфигурация группы одной строкой */
function cfgRow(g){
  const it=[['автор',g.src],['страниц',g.pages],['даты',g.dates],['картинки/стиль',g.img],
            ['аккаунты',g.acc],['id',g.ids],['контент создан',g.made],['доменов .team',g.ntm+' из '+g.ndom]];
  return `<div class="meta">${it.filter(x=>x[1]&&x[1]!=='—').map(([k,v])=>
    `<div><span class="mk">${k}</span><span class="mv">${E(v)}</span></div>`).join('')}</div>`;
}
/* таблица съёмов группы */
function snapTable(g){
  return `<div class="tw"><table><thead><tr><th class="l">Съём</th><th>Т10/дом</th><th>Медиана</th>
   <th>Без лидера</th><th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ</th><th>СЧ</th><th class="l">Ключей в Т10 по доменам</th></tr></thead><tbody>
   ${g.snaps.map(s=>`<tr class="${s.trunc?'tr-bad':''}">
     <td class="l">${E(s.lab)}${s.trunc?' <span class="pill p-no">выгрузка обрезана</span>':''}</td>
     <td class="${s.trunc?'mut':(s.mean>=5?'good':'')}"><b>${f(s.mean)}</b></td><td>${f(s.med,1)}</td>
     <td class="${s.trunc?'mut':''}">${f(s.wo)}</td><td>${s.t3}</td><td>${s.t30}</td><td>${s.t100}</td>
     <td>${s.vch}</td><td>${s.sch}</td><td class="l mono sm">${s.vals.join(', ')}</td></tr>`).join('')}
   </tbody></table></div>`;
}
/* таблица доменов группы */
function domTable(g){
  const L=g.snaps.length;
  return `<div class="tw"><table><thead><tr><th class="l">Домен</th>
   <th class="l">Т10 по съёмам</th><th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ</th><th>СЧ</th><th>Брендов</th>
   <th class="l">Ключи в ТОП-10 (позиция)</th></tr></thead><tbody>
   ${g.doms.map(d=>`<tr>
     <td class="l">${E(d.d)}${d.tm?'':' <span class="tag">не .team</span>'}${d.excl?' <span class="tag ex">исключён</span>':''}</td>
     <td class="l mono">${d.tr.map((v,i)=>`<span class="${g.snaps[i].trunc?'mut':(i===L-1?'now':'')}">${v}</span>`).join('<span class="ar">→</span>')}</td>
     <td>${d.t3}</td><td>${d.t30}</td><td>${d.t100}</td><td>${d.vch}</td><td>${d.sch}</td><td>${d.nb}</td>
     <td class="l sm">${(d.keys||[]).map(k=>`<span class="kq"><span class="t-${k.t}">${E(k.q)}</span> <b>${k.p}</b></span>`).join(' ')||'<span class="mut">—</span>'}</td>
   </tr>`).join('')}</tbody></table></div>`;
}
function brandRow(g){
  const s=last(g); if(!s.topb||!s.topb.length) return '';
  return `<div class="brow"><span class="mk">бренды в ТОП-10 (${s.nbrands} всего)</span>
    ${s.topb.map(([b,n])=>`<span class="bch">${E(b)} <b>${n}</b></span>`).join('')}</div>`;
}
function card(g){
  return `<div class="gcard"><div class="gh">
    <h3>${E(g.name)}</h3>
    <div class="gt">${g.test!=='—'?`<span class="pill p-t">${E(g.test)} · ${E(g.arm)}</span>`:''}
      <span class="mut sm">лист «${E(g.sheet.trim())}»</span></div></div>
    ${cfgRow(g)}${snapTable(g)}${brandRow(g)}${domTable(g)}</div>`;
}

/* --- сравнение двух веток по всем съёмам --- */
function versus(title,sub,A,B,note){
  const n=Math.min(A.snaps.length,B.snaps.length);
  const rows=[];
  for(let i=0;i<n;i++){
    const a=A.snaps[i],b=B.snaps[i],bad=a.trunc||b.trunc;
    const w=k=>a[k]>b[k]?'a':(b[k]>a[k]?'b':'-');
    rows.push(`<tr class="${bad?'tr-bad':''}">
      <td class="l">${E(a.lab)}${bad?' <span class="pill p-no">обрезан</span>':''}</td>
      <td class="${!bad&&w('mean')==='a'?'good':''}">${f(a.mean)}</td>
      <td class="${!bad&&w('mean')==='b'?'good':''}">${f(b.mean)}</td>
      <td class="sm ${bad?'mut':''}">${bad?'—':(w('mean')==='-'?'вровень':R(Math.max(a.mean,b.mean),Math.min(a.mean,b.mean))+' · '+(w('mean')==='a'?A.armS:B.armS))}</td>
      <td class="${!bad&&w('wo')==='a'?'good':''}">${f(a.wo)}</td>
      <td class="${!bad&&w('wo')==='b'?'good':''}">${f(b.wo)}</td>
      <td class="sm ${bad?'mut':''}">${bad?'—':(w('wo')==='-'?'вровень':R(Math.max(a.wo,b.wo),Math.min(a.wo,b.wo))+' · '+(w('wo')==='a'?A.armS:B.armS))}</td>
      <td>${a.t3} / ${b.t3}</td><td>${a.vch+a.sch} / ${b.vch+b.sch}</td></tr>`);
  }
  return `<div class="blk"><h3 class="vt">${E(title)}</h3><p class="note">${sub}</p>
   <div class="vsnames"><span class="vn a">${E(A.name)}</span><span class="vs">против</span><span class="vn b">${E(B.name)}</span></div>
   <div class="tw"><table><thead>
   <tr><th class="l" rowspan="2">Съём</th><th colspan="3">Т10 на домен</th><th colspan="3">Без лидера</th>
       <th rowspan="2">Т3</th><th rowspan="2">ВЧ+СЧ</th></tr>
   <tr><th>${E(A.armS)}</th><th>${E(B.armS)}</th><th class="l">Кто выше</th>
       <th>${E(A.armS)}</th><th>${E(B.armS)}</th><th class="l">Кто выше</th></tr></thead>
   <tbody>${rows.join('')}</tbody></table></div>
   ${note?`<p class="verd">${note}</p>`:''}</div>`;
}
const shortArm=s=>s.replace(/ · .*/,'');
G.forEach(g=>g.armS=shortArm(g.arm));

/* ---------------- секции ---------------- */
const COH=S=>G.filter(g=>g.coh===S);

const secNow=`<div class="blk">
 <h2>Съём 27.08 12:16–12:18 — одиннадцать групп, вторая точка</h2>
 <p class="note">Файл <code>launches_20260827_122127.xlsx</code>. Первый съём — 26.08 23:54–23:57,
 второй — 27.08 12:16–12:18, между ними 12,5 часа. Все 22 снимка полные.
 В расчёте только <code>.team</code>, бренды <code>vovan</code> и <code>pari</code> вне ядра.</p>
 <div class="tw"><table class="big"><thead><tr>
   <th class="l">Группа</th><th class="l">Автор / конфигурация</th><th>.team</th>
   <th>26.08 23:5x</th><th>27.08 12:1x</th><th></th><th>Без лид. с1</th><th>Без лид. с2</th>
   <th>Т3</th><th>Т30</th><th>Т100</th><th>ВЧ+СЧ</th></tr></thead><tbody>
 ${COH('26-27.08').map(g=>{const a=g.snaps[0],b=g.snaps[1];
   return `<tr><td class="l"><b>${E(g.name)}</b><div class="mut sm">${E(g.test)} · ${E(g.arm)}</div></td>
   <td class="l sm">${E(g.src)}<div class="mut">${[g.dates,g.img].filter(x=>x&&x!=='—').map(E).join(' · ')}</div></td>
   <td>${g.ntm}</td><td class="mut">${f(a.mean)}</td><td class="${b.mean>=5?'good':(b.mean<1?'bad':'')}"><b>${f(b.mean)}</b></td>
   <td>${b.mean>a.mean?'<span class="good">↑</span>':(b.mean<a.mean?'<span class="bad">↓</span>':'<span class="mut">→</span>')}</td>
   <td class="mut">${f(a.wo)}</td><td><b>${f(b.wo)}</b></td>
   <td>${a.t3}→${b.t3}</td><td>${a.t30}→${b.t30}</td><td>${a.t100}→${b.t100}</td><td>${a.vch+a.sch}→${b.vch+b.sch}</td></tr>`}).join('')}
 </tbody></table></div></div>
 <div class="blk"><h2>Каждая группа полностью</h2>
 ${COH('26-27.08').map(card).join('')}</div>`;

const secQ=`
${versus('Даты · заход 5 — без картинок','Семейство NEW33, 12 страниц, чужой контент. Прогоны разведены одной минутой: id 938-945 создан 25.08 в 16:04, id 946-953 — в 16:05.',
  S('NEW33_12pages_nodate_25.08'),S('NEW33_12pages_withdate_25.08'),
  '<b>Без дат впереди на обоих полных съёмах и по обоим измерениям.</b> На финальном съёме 25,75 против 8,88 (2,9×), без лидера 18,57 против 4,71 (3,9×). Ветка с датами за 13 часов не сдвинулась вообще: 8,88 → 8,88.')}
${versus('Даты · заход 6 — при включённых картинках','Тот же прогон, семейство NEW33, но картинки в обеих ветках. id 954-969 создан 25.08 в 18:26-18:30, id 970-986 — в 18:30-18:31.',
  S('NEW33_12pages_nodate+img_25.08'),S('NEW33_12pages_withdate+img_25.08'),
  '<b>Направление то же, разрыв растёт.</b> Съём 1 — 1,16× и 1,05×, съём 2 — 1,75× и 1,56×. ТОП-3: 38 против 8. Перестановочный тест по доменам: p = 0,35 → <b>p = 0,10</b>. Две независимые пары в одном семействе указывают в одну сторону.')}
${versus('Картинки · наш генератор, день 1 (24.08)','Generator_11page, 11 страниц. Два прогона в каждой ветке: 14:38/16:58 и 14:39/16:57.',
  S('Generator_11page_img_24.08'),S('Generator_11page_NOimg_24.08'),
  'Съём 1 за картинки (2,78 против 1,22), съём 2 против них (3,11 против 6,89). <b>Перевернулось за 13 часов.</b>')}
${versus('Картинки · наш генератор, день 2 (25.08)','Generator_11page, 11 страниц. id 933-937 создан 25.08 в 14:49, id 890-899 — в 14:22.',
  S('Generator_11page_img_25.08'),S('Generator_11page_NOimg_25.08'),
  'Съём 1 против картинок (3,00 против 4,86), финальный съём за них (8,80 против 3,14). <b>Перевернулось снова, в обратную сторону.</b>')}
${versus('Картинки · чужой контент (NEW17, 26.08)','Три минуты между прогонами: id 987-993 создан 26.08 в 14:06, id 994-1002 — в 14:09-14:10. Самая чистая пара за всё наблюдение.',
  S('NEW17_img_withdate_26.08'),S('NEW17_NOimg_withdate_26.08'),
  '<b>Впервые направление не перевернулось:</b> картинки впереди на обоих съёмах и по обоим измерениям. Но 12,00 против 5,50 держит один домен — <code>1520.team</code> прошёл 13 → 65. Без лидера 5,38 против 3,40, то есть 1,58×, p = 0,32. При 6 и 9 доменах различия меньше двукратных неразличимы.')}
${versus('Картинки · наш генератор, новый стиль (26.08)','Внутри теста G: конфигурация B против C, обе — новый стиль, различие только в картинках. По две партии на конфигурацию.',
  S('Generator_C_novyy_img (nabor-165…169)'),S('Generator_B_novyy_bez_img (nabor-160…164)'),
  'Партии 1: съём 1 вровень (0,40 / 0,40), съём 2 за картинки (1,00 против 0,20). Пулы по 10 доменов: C = 2,10, B = 0,50, p = 0,07. Пятый заход, и снова ниже порога.')}
${versus('Аккаунты · вебмастера, 24.08','20 наборов, разбиты на два блока по 10. Блок 1 — старые аккаунты, блок 2 — новые, начиная с 1329.',
  S('Вебмастера, блок 1 — СТАРЫЕ аккаунты'),S('Вебмастера, блок 2 — НОВЫЕ аккаунты'),
  'Съём 1 обе ветки в нуле. Съём 2 — новые впереди: 8,40 против 6,00 по среднему. Одна точка, вердикта нет.')}
${versus('Аккаунты · вебмастера, 25-26.08','Повтор на наборах nabor-149…153 (старые) и nabor-144…148 (новые), по 5 доменов.',
  S('Старые аккаунты (nabor-149…153)'),S('Новые аккаунты (nabor-144…148)'),
  'Съём 1 за старые (2,80 против 2,20), финальный за новые (1,60 против 3,20). <b>Перевернулось.</b> Вместе с 24.08: три съёма, два указывают на новые аккаунты, один на старые. Ни одного вердикта.')}
${versus('Стиль генератора · старый против нового (26.08)','Тест G, конфигурация A против B. Каждая в двух партиях по 5 доменов.',
  S('Generator_A_staryy_stil (nabor-155…159)'),S('Generator_B_novyy_bez_img (nabor-160…164)'),
  'Партия A обходит B на обоих съёмах: 6,00 / 0,40 и 10,40 / 0,20. Но вторая партия того же старого стиля, A2, даёт 1,60 — ниже пула конфигурации C. <b>Перевес держит одна партия из двух.</b>')}
<div class="blk"><h3 class="vt">Повтор партий — что показал тест G</h3>
<p class="note">Первый тест за всё наблюдение, где каждая конфигурация запущена дважды. Повтор вводился ровно ради одного вопроса: что больше — разница между конфигурациями или разброс между партиями одной и той же конфигурации.</p>
<div class="tw"><table><thead><tr><th class="l">Конфигурация</th><th class="l">Партия</th>
<th>26.08 23:5x</th><th>27.08 12:1x</th><th>Без лидера с2</th><th>Т30 с2</th><th>Т100 с2</th></tr></thead><tbody>
${[['A · старый стиль','Generator_A_staryy_stil (nabor-155…159)','Generator_A2_staryy_stil (nabor-170…174)'],
   ['B · новый, без картинок','Generator_B_novyy_bez_img (nabor-160…164)','Generator_B2_novyy_bez_img (nabor-175…179)'],
   ['C · новый + картинки','Generator_C_novyy_img (nabor-165…169)','Generator_C2_novyy_img (nabor-180…184)']].map(([n,p1,p2])=>{
  const x=S(p1),y=S(p2);
  const flip=((x.snaps[0].mean-y.snaps[0].mean)>0)!==((x.snaps[1].mean-y.snaps[1].mean)>0)
             &&x.snaps[0].mean!==y.snaps[0].mean&&x.snaps[1].mean!==y.snaps[1].mean;
  return [x,y].map((g,j)=>`<tr class="${j?'p2':''}">${j?'':`<td class="l" rowspan="2"><b>${E(n)}</b>${flip?'<div class="pill p-no" style="margin-top:4px">порядок перевернулся</div>':''}</td>`}
    <td class="l mono sm">${E(g.ids)}</td><td class="mut">${f(g.snaps[0].mean)}</td>
    <td class="${g.snaps[1].mean>=3?'good':''}"><b>${f(g.snaps[1].mean)}</b></td>
    <td>${f(g.snaps[1].wo)}</td><td>${g.snaps[1].t30}</td><td>${g.snaps[1].t100}</td></tr>`).join('')}).join('')}
</tbody></table></div>
<p class="verd">Пулы по 10 доменов на съёме 2: <b>A = 6,00 · C = 2,10 · B = 0,50</b>. Статистика разделяет только крайние: A против B p&nbsp;=&nbsp;0,008, A против C p&nbsp;=&nbsp;0,15, C против B p&nbsp;=&nbsp;0,07. При этом <b>у двух конфигураций из трёх партии поменялись местами за 12 часов</b>, а весь перевес A держит одна партия. На пяти доменах партия шумит сильнее, чем различаются конфигурации.</p></div>
<div class="blk"><h3 class="vt">Контроль — один прогон генерации 21.08 13:29 на трёх датах запуска</h3>
<p class="note">Контенты <code>NEW50_5_7pages_nodate_21.08</code>, все созданы 21.08 в 13:29 одним прогоном, разложены по трём запускам.</p>
<div class="tw"><table><thead><tr><th class="l">Контенты</th><th class="l">id</th><th class="l">Запуск</th>
<th>.team</th><th class="l">Т10/дом по съёмам</th><th>Лучший</th><th>Без лидера</th><th>ВЧ+СЧ</th></tr></thead><tbody>
${[['_1…_6','NEW50_5_7pages_nodate_21.08 _1…_6','22.08 23:04'],
   ['_7…_17','NEW50_5_7pages_nodate_21.08 _7…_17','25.08'],
   ['_18…_24','КОНТРОЛЬ NEW50_5_7pages_nodate_21.08 _18…_24','26.08']].map(([lab,nm,when])=>{
  const g=S(nm); const gi=g.good; const best=Math.max(...gi.map(i=>g.snaps[i].mean));
  const bs=g.snaps[gi[gi.length-1]];
  return `<tr><td class="l"><b>${E(lab)}</b></td><td class="l mono sm">${E(g.ids)}</td><td class="l sm">${E(when)}</td>
  <td>${g.ntm}</td><td class="l mono">${g.snaps.map((s,i)=>`<span class="${s.trunc?'mut strike':''}">${f(s.mean)}</span>`).join('<span class="ar">→</span>')}</td>
  <td class="${best>=15?'good':(best<6?'bad':'')}"><b>${f(best)}</b></td><td>${f(bs.wo)}</td><td>${bs.vch+bs.sch}</td></tr>`}).join('')}
</tbody></table></div>
<p class="verd">Первый запуск ушёл в экзотические зоны — ни одного <code>.team</code>, с остальными несравним.
Второй дал <b>22,62</b> на шести часах и 28 ВЧ+СЧ брендов в ТОП-10. Третий на двенадцати часах — <b>4,71</b>,
без лидера 2,67, ВЧ+СЧ <b>ноль</b>. Отставание 4,8×.
<b>Один и тот же прогон генерации на новой дате не воспроизвёлся</b> — значит «прогон» не является
устойчивой единицей, и сравнивать группы, разнесённые по датам, на этом основании нельзя.</p></div>`;

const secAll=`<div class="blk"><h2>Все 42 группы за всё наблюдение</h2>
 <p class="note">Каждая группа под своим названием, со всеми съёмами. Перечёркнутые значения — снимки,
 где выгрузка оборвалась (23.08 23:28–23:29 и 26.08 11:14–11:15); они в выводы не идут.
 Т10/дом считается по <code>.team</code>; если <code>.team</code> в группе нет, по всем её доменам.</p>
 <div class="tw"><table class="big"><thead><tr>
  <th class="l">Группа</th><th class="l">Автор</th><th class="l">Стр.</th><th class="l">Даты</th>
  <th class="l">Картинки / стиль</th><th class="l">Аккаунты</th><th class="l">id</th><th class="l">Создан</th>
  <th>n</th><th class="l">Т10 на домен по съёмам</th><th>Лучший</th></tr></thead><tbody>
 ${['26-27.08','25-26.08','24-25.08','архив'].map(c=>
  `<tr class="cohh"><td colspan="11" class="l">${c==='архив'?'Архив · 19–23.08':'Когорта '+c}</td></tr>`+
  COH(c).map(g=>{const best=Math.max(...g.good.map(i=>g.snaps[i].mean));
  return `<tr><td class="l"><b>${E(g.name)}</b>${g.test!=='—'?`<div class="mut sm">${E(g.test)} · ${E(g.arm)}</div>`:''}</td>
   <td class="l sm">${E(g.src)}</td><td class="sm">${E(g.pages)}</td><td class="l sm">${E(g.dates)}</td>
   <td class="l sm">${E(g.img)}</td><td class="l sm">${E(g.acc)}</td><td class="l mono sm">${E(g.ids)}</td>
   <td class="l sm">${E(g.made)}</td><td>${g.ntm}</td>
   <td class="l mono sm">${g.snaps.map(s=>`<span class="${s.trunc?'mut strike':''}" title="${E(s.lab)}">${f(s.mean)}</span>`).join('<span class="ar">→</span>')}</td>
   <td class="${best>=15?'good':(best<2?'bad':'')}"><b>${f(best)}</b></td></tr>`}).join('')).join('')}
 </tbody></table></div>
 <p class="note" style="margin-top:12px">Наведи на значение — покажет метку съёма.</p></div>`;

const secDom=`<div class="blk"><h2>Все домены когорты 26–27.08</h2>
 <p class="note">85 доменов, запущенных 26.08, с траекторией по двум съёмам и ключами, по которым
 домен стоит в ТОП-10. Цвет ключа — тир бренда: <span class="t-ВЧ">ВЧ</span>,
 <span class="t-СЧ">СЧ</span>, <span class="t-НЧ">НЧ</span>.</p>
 ${COH('26-27.08').map(g=>`<div class="gcard"><div class="gh"><h3>${E(g.name)}</h3>
   <div class="gt"><span class="pill p-t">${E(g.test)} · ${E(g.arm)}</span></div></div>${domTable(g)}</div>`).join('')}</div>`;

const secM=`<div class="blk"><h2>Метод</h2><div class="grid2">
 <div class="card"><h3>Что считается</h3>
 <p>Ядро — 1570 ключей. Метрика «Т10/дом» — сколько ключей ядра домен держит в ТОП-10, усреднённое по доменам ветки.</p>
 <p>«Без лидера» — то же среднее без самого сильного домена ветки. На малых ветках это главное измерение:
 одно попадание вроде <code>1520.team</code> с 65 ключами двигает среднее вдвое, а массу ветки — нет.</p>
 <p>Только <code>.team</code>. Бренды <code>vovan</code> и <code>pari</code> вне ядра.
 Домены <code>5374.team</code> и <code>2535.team</code> исключены по договорённости.</p></div>
 <div class="card"><h3>Обрезанные выгрузки</h3>
 <p>Признак: данные лежат сплошным префиксом, последняя четверть ядра пуста. Такой снимок выглядит
 как обвал, хотя выжившие ключи стоят на местах.</p>
 <p>Найдено 12 таких снимков в двух выгрузках — 23.08 23:28–23:29 и 26.08 11:14–11:15.
 Все перечёркнуты и исключены из выводов.</p></div>
 <div class="card warn-c"><h3>Что мешает сравнивать</h3>
 <p><b>Время выкладки не присылалось ни по одной группе.</b> Известно только время создания контента.
 Поэтому корректны сравнения <b>внутри пары</b> — обе ветки запущены вместе. Сравнения между
 семействами и между датами — нет.</p>
 <p>По этой же причине разрыв «чужой контент 7,89 против генератора 2,87 на домен, p = 0,004»
 в выводы не вынесен, хотя оба съёма сделаны в одно окно.</p></div>
 <div class="card"><h3>Что открыто</h3>
 <p><b>Даты:</b> два независимых захода подряд за «без дат», оба растут. Третий съём по NEW33+img
 покажет, дорастёт ли до порога.<br>
 <b>Картинки:</b> шесть заходов, направление устоялось впервые. Нужны 20+ доменов на ветку.<br>
 <b>Аккаунты:</b> три съёма, направление меняется. Вердикта нет.<br>
 <b>Стиль генератора:</b> двух партий мало, нужно пять-шесть.<br>
 <b>Контроль прогона:</b> закрыт, ответ отрицательный.</p></div>
</div></div>`;

const SEC={now:secNow,q:secQ,all:secAll,dom:secDom,m:secM};
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('nav button').forEach(x=>x.setAttribute('aria-selected',x===b));
  document.querySelectorAll('main section').forEach(s=>s.hidden=s.id!==b.dataset.s);
  window.scrollTo({top:0,behavior:'instant'});
});
for(const k in SEC){const el=document.getElementById(k); if(el) el.innerHTML=SEC[k];}

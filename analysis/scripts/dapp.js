const D=window.DATA;
const nf=(x,d=0)=>x==null?'—':Number(x).toFixed(d).replace('.',',');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pl=(n,a,b,c)=>{const x=Math.abs(n)%100,y=x%10;return n+' '+(x>10&&x<20?c:y===1?a:y>1&&y<5?b:c);};
const QN={'ok':'полное','усечено':'обрезано слева','окно открыто':'ещё копится'};
const SN={'готовый пак':'пак','генератор':'генератор','наборы':'наборы',
          'сайты из выдачи':'выдача','не указано':'не указано'};
const chips=(arr,map,lim=4)=>{
  const top=arr.slice(0,lim), rest=arr.slice(lim);
  return top.map(x=>`<span class="bch sm">${esc(map?map[x.k]||x.k:x.k)} <b>${x.n}</b>${
    x.r?` <span class="good">рег ${x.r}</span>`:''}</span>`).join('')
    +(rest.length?`<span class="bch sm mut" title="${esc(rest.map(x=>x.k+' '+x.n).join(', '))}">и ещё ${
      rest.length} по ${rest.reduce((a,b)=>a+b.n,0)===rest.length?'одному':'мелочи'}</span>`:'');};

/* меры окна: значение всегда подписано числом, цвет — не единственный носитель */
const meter=(pct,cl)=>`<div class="meter" role="img" aria-label="${pct}% окна">
  <div class="mfill${cl?' done':''}" style="width:${pct}%"></div></div>`;

/* ── 1. ДНИ ЗАПУСКА ──────────────────────────────────────── */
let showq='all';
function tDays(){
  const rows=D.days.filter(d=>showq==='all'||d.q===showq);
  let h=`<div class="blk"><h2>Все дни запуска</h2>
  <p class="note">Домен зарабатывает около шести суток, и три четверти денег приходят в первые двое.
  Колонка «окно» показывает, какая доля этого срока уже прошла: пока она не заполнена,
  доля доменов с деньгами будет расти, и сравнивать такой день с закрытыми нельзя.
  Колонка «данные» отмечает дни, у которых часть жизни не попала в выгрузку конверсий —
  она начинается 21 августа.</p>
  <div class="brow"><span class="mk">показать</span>
    <select id="qf">
      <option value="all"${showq==='all'?' selected':''}>все дни</option>
      <option value="ok"${showq==='ok'?' selected':''}>только пригодные для сравнения</option>
      <option value="окно открыто"${showq==='окно открыто'?' selected':''}>только с открытым окном</option>
      <option value="усечено"${showq==='усечено'?' selected':''}>только с обрезанными данными</option>
    </select></div>
  <div class="tw"><table class="big"><thead><tr>
    <th class="l">День запуска</th><th>Доменов</th><th>Групп</th>
    <th class="l">Окно</th><th class="l">Данные</th><th class="l">Контент</th><th class="l">Зоны</th>
    <th>С деньгами</th><th>Доля</th><th>Отклонение</th>
    <th>Регистраций</th><th>Депозитов</th><th>Рег/дом</th><th>Прогноз</th><th>Т10/дом</th>
  </tr></thead><tbody>`;
  for(const d of rows){
    const closed=d.age>=6;
    h+=`<tr class="q-${d.q==='ok'?'ok':d.q==='усечено'?'cut':'open'}">
      <td class="l"><b class="dday">${esc(d.day)}</b><div class="sm mut">${pl(d.age,'сутки','суток','суток')} назад</div></td>
      <td>${d.n}</td><td>${d.groups.length}</td>
      <td class="l">${meter(d.pct,closed)}<div class="sm mut">${closed?'закрыто':`${d.pct}% из 100`}</div></td>
      <td class="l sm">${d.q==='ok'?'<span class="tag ok">полное</span>'
        :d.q==='усечено'?`<span class="tag bad2">нет первых ${pl(d.lost,'суток','суток','суток')}</span>
           <div class="mut">это ~${d.lostpct}% заработка</div>`
        :'<span class="tag warn2">ещё копится</span>'}</td>
      <td class="l sm">${chips(d.src,SN)}</td>
      <td class="l sm">${chips(d.zone)}</td>
      <td>${d.w}</td>
      <td class="${d.q==='ok'?'now':'mut'}"><b>${nf(d.share,1)}%</b></td>
      <td class="sm ${d.q!=='ok'?'mut':Math.abs(d.z)>=2?'warn':''}">${d.q==='ok'?(d.z>0?'+':'')+nf(d.z,1)+' σ':'—'}</td>
      <td>${d.r}</td><td class="${d.dep?'good':'mut'}">${d.dep||'·'}</td>
      <td><b>${nf(d.rpd,2)}</b></td>
      <td class="${d.proj?'warn':'mut'}">${d.proj?nf(d.proj,2):'—'}</td>
      <td class="${d.t10==null?'mut':''}">${d.t10==null?'нет замеров':nf(d.t10,1)}</td></tr>`;
  }
  h+='</tbody></table></div>';
  h+=`<p class="verd">Колонка «прогноз» — это регистрации на домен, поделённые на пройденную долю окна.
  Грубая оценка того, куда день придёт к закрытию, и только для дней с открытым окном.
  На возрасте одних суток она умножает на пять с половиной, поэтому у 2 сентября ей верить нельзя.</p>`;

  const sumtab=(key,title,note,map)=>{
    let t=`<div class="blk"><h3 class="vt">${title}</h3><p class="note">${note}</p>
    <div class="tw"><table><thead><tr><th class="l">${key==='src'?'Источник контента':'Зона'}</th>
      <th>Доменов всего</th><th>С деньгами</th><th>Регистраций</th><th>Депозитов</th>
      <th>Доменов с закрытым окном</th><th>Из них с деньгами</th><th>Доля</th>
      </tr></thead><tbody>`;
    for(const x of D.sum[key]){
      if(x.n<5&&!x.r) continue;
      t+=`<tr${x.cn?'':' class="tr-bad"'}><td class="l"><b>${esc(map?map[x.k]||x.k:x.k)}</b></td>
        <td>${x.n}</td><td>${x.w}</td><td class="${x.r?'good':'mut'}"><b>${x.r}</b></td>
        <td class="${x.dep?'good':'mut'}">${x.dep||'·'}</td>
        <td>${x.cn||'<span class="mut">—</span>'}</td><td>${x.cn?x.cw:''}</td>
        <td class="${x.cn>=20?'now':'mut'}">${x.cn?nf(100*x.cw/x.cn,0)+'%':'нет закрытых'}</td></tr>`;}
    const tail=D.sum[key].filter(x=>x.n<5&&!x.r);
    if(tail.length) t+=`<tr><td class="l mut" colspan="8">плюс ${tail.length} по одному-двум доменам без денег: ${
      tail.map(x=>esc(x.k)).join(', ')}</td></tr>`;
    return t+'</tbody></table></div></div>';};
  h+=sumtab('src','Чего запускали больше — генератора или готовых паков',
    'Сложено по всем дням. Колонка «доля» считается только по доменам, у которых окно уже закрылось, иначе свежие партии тянут её вниз.',SN);
  h+=sumtab('zone','Какие доменные зоны шли в запуск',
    'Тот же принцип: доля — только по закрытым окнам.');
  if(D.gap.length) h+=`<div class="blk"><h3 class="vt">Дни без запусков</h3>
    <p class="note">В эти дни ничего не запускали, поэтому в таблице их нет.
    Конверсии в них приходили — но с доменов, запущенных раньше.</p>
    <div class="brow">${D.gap.map(g=>`<span class="bch">${esc(g)}</span>`).join('')}</div></div>`;
  return h+'</div>';
}

/* ── 2. ДНИ ПОДРОБНО ─────────────────────────────────────── */
function tCards(){
  let h=`<div class="blk"><h2>Что запускали в каждый день</h2>
  <p class="note">Группы внутри дня. «Т10 на домен» — ключей в десятке на последнем известном замере;
  у архивных групп это замер их собственной эпохи, а не сегодняшний.</p><div class="grid2">`;
  for(const d of D.days){
    const closed=d.age>=6;
    h+=`<div class="gcard"><div class="gh"><h3>${esc(d.day)}</h3>
      <div class="gt">
        <span class="tag${d.q==='ok'?' ok':d.q==='усечено'?' bad2':' warn2'}">${esc(QN[d.q])}</span>
        <span class="tag">${pl(d.n,'домен','домена','доменов')}</span></div></div>
      <div class="meta">
        <div><span class="mk">Окно</span><span class="mv">${closed?'закрыто':d.pct+'%'}</span></div>
        <div><span class="mk">С деньгами</span><span class="mv">${d.w} из ${d.n}</span></div>
        <div><span class="mk">Регистраций</span><span class="mv">${d.r}</span></div>
        <div><span class="mk">На домен</span><span class="mv">${nf(d.rpd,2)}</span></div>
      </div>
      <div class="tw"><table><thead><tr><th class="l">Группа</th><th>Дом.</th>
        <th>С деньгами</th><th>Рег.</th><th>Т10/дом</th></tr></thead><tbody>`;
    for(const g of d.groups)
      h+=`<tr${g.r?'':' class="tr-bad"'}><td class="l sm">${esc(g.g)}</td><td>${g.n}</td>
        <td class="${g.w?'good':'mut'}">${g.w}</td><td class="${g.r?'good':'mut'}"><b>${g.r}</b></td>
        <td class="${g.t10==null?'mut':''}">${g.t10==null?'—':nf(g.t10,1)}</td></tr>`;
    h+='</tbody></table></div></div>';
  }
  return h+'</div></div>';
}

/* ── 3. КАК ПРИХОДЯТ ДЕНЬГИ ──────────────────────────────── */
function bars(items,label,val,unit){
  const mx=Math.max(...items.map(val));
  return `<div class="bars">${items.map(x=>{
    const v=val(x),w=100*v/mx;
    return `<div class="brow2" title="${esc(label(x))}: ${v} ${unit}">
      <span class="blab">${esc(label(x))}</span>
      <span class="btrack"><span class="bfill" style="width:${w}%"></span></span>
      <span class="bval">${v}</span></div>`;}).join('')}</div>`;
}
function tHow(){
  const mx=D.arr.reduce((a,b)=>b.n>a.n?b:a);
  return `<div class="blk"><h2>Когда приходят регистрации</h2>
  <p class="note">По календарным дням, все домены вместе. Регистрации шли во все
  ${pl(D.arr.length,'день','дня','дней')} периода без единого пустого — это и есть ответ на вопрос
  про удачные даты: их нет, поток ровный.</p>
  <h3 class="vt">Регистраций в сутки</h3>
  ${bars(D.arr,x=>x.d,x=>x.n,'рег.')}
  <p class="verd">Единственный заметный пик — ${esc(mx.d)} с ${mx.n} регистрациями.
  Он приходится на вторые сутки жизни крупной партии 21–22 августа, то есть объясняется
  возрастом доменов, а не самой датой.</p></div>

  <div class="blk"><h2>На каких сутках жизни домена</h2>
  <p class="note">Возраст домена в момент регистрации. Считаются только домены, у которых известен день запуска.</p>
  ${bars(D.age,x=>x.d+' сут.',x=>x.n,'рег.')}
  <h3 class="vt">Накопительная кривая, по которой считается окно</h3>
  <div class="tw"><table><thead><tr><th class="l">Прошло суток</th>
    ${D.curve.map((_,i)=>`<th>${i}</th>`).join('')}</tr></thead>
    <tbody><tr><td class="l">Накоплено заработка</td>
    ${D.curve.map(c=>`<td>${c}%</td>`).join('')}</tr></tbody></table></div>
  <p class="verd">Отсюда правило: домену меньше двух суток — сравнивать его по деньгам
  с кем угодно бессмысленно, у него на руках меньше половины будущего результата.</p></div>`;
}

/* ── 4. ЧТО МОЖНО СРАВНИВАТЬ ─────────────────────────────── */
function tQ(){
  const ok=D.days.filter(d=>d.q==='ok'&&d.n>=20);
  const cut=D.days.filter(d=>d.q==='усечено');
  const open=D.days.filter(d=>d.q==='окно открыто');
  return `<div class="blk"><h2>Какие дни вообще можно ставить рядом</h2>
  <div class="tiles">
    <div class="tile g"><div class="k">Пригодны для сравнения</div><div class="v">${ok.length}</div>
      <div class="c">${ok.map(d=>d.day).join(', ')} — окно закрыто, данные полные, доменов хватает</div></div>
    <div class="tile b"><div class="k">Данные обрезаны слева</div><div class="v">${cut.length}</div>
      <div class="c">${cut.map(d=>d.day).join(', ')} — выгрузка начинается 21.08, их лучшие дни в неё не попали</div></div>
    <div class="tile a"><div class="k">Окно ещё копится</div><div class="v">${open.length}</div>
      <div class="c">${open.map(d=>d.day).join(', ')} — доля вырастет, итог будет виден 6–8 сентября</div></div>
  </div>
  <h3 class="vt">Проверка: разброс между пригодными днями</h3>
  <div class="tw"><table><thead><tr><th class="l">День</th><th>Доменов</th><th>С деньгами</th>
    <th>Доля</th><th>Отклонение от базовой</th></tr></thead><tbody>`
  +ok.map(d=>`<tr><td class="l">${esc(d.day)}</td><td>${d.n}</td><td>${d.w}</td>
      <td><b>${nf(d.share,1)}%</b></td>
      <td class="${Math.abs(d.z)>=2?'warn':'mut'}">${(d.z>0?'+':'')+nf(d.z,1)} σ</td></tr>`).join('')
  +`</tbody></table></div>
  <p class="verd">Базовая доля по всем пригодным дням — <b>${nf(D.sim.base,1)}%</b>.
  Размах между лучшим и худшим днём <b>${nf(D.sim.obs,1)} пункта</b>, и двадцать тысяч
  случайных прогонов дают такой размах лишь в <b>${nf(D.sim.p,2)}% случаев</b>.
  Дни действительно различаются — но не как календарь. Наверху стоит
  <b>31 августа</b> с экспериментальной конфигурацией на dorgen.net без потолка
  вложенности; внизу — дни, где преобладали семистраничные партии, а семь страниц
  теперь доказанно хуже двенадцати (p = 0,0065). Различаются конфигурации,
  которые в эти дни запускались, а не сами даты.</p>
  <div class="grid2" style="margin-top:16px">
    <div class="card warn-c"><h3>Две ловушки, на которых я уже споткнулся</h3>
    <p><b>Обрезка слева.</b> У доменов, запущенных 19 и 20 августа, первые сутки жизни
    не попали в выгрузку — а это от 18 до 49 процентов их заработка. Их 5,0 % и 12,6 %
    измеряют полноту данных, а не качество запуска.</p>
    <p><b>Отбор по результату.</b> В первой версии 27 августа стояло 8 из 8 = 100 %,
    потому что в карту попали только те домены, которых я нашёл в списке с конверсиями.
    С полным списком из реестра — 31 домен и 25,8 %, то есть ровно средний день.</p></div>
    <div class="card"><h3>Что изменилось к 7 сентября</h3>
    <p>Окна 31 августа и 1 сентября закрылись, как и было обещано. Пригодных для сравнения
    дней стало ${ok.length} вместо пяти. 2 сентября закроется завтра, дальше по одному дню
    в сутки — к 13 сентября закроются все запуски по 7 сентября включительно.</p>
    <p>Выгрузка от 11 сентября начинается 12 августа и сняла усечение слева:
    дни 19 и 20 августа стали пригодными, пригодных дней теперь тринадцать
    вместо семи, а регистраций в разборе — 403 вместо 253.</p>
    <p>Главное следствие не про дни, а про страницы: на этой выборке
    12 страниц дают 28,9 % против 13,8 % у семи, p = 0,0065, и разница
    держится внутри каждого дня. Вопрос закрыт.</p></div>
  </div></div>`;
}

/* ── 5. НОВАЯ ВЫГРУЗКА КОНВЕРСИЙ ─────────────────────────── */
function tFresh(){
  const F=D.fresh;
  const withDay=F.rows.filter(r=>r.day), noDay=F.rows.filter(r=>!r.day);
  const maxLag=Math.max(...F.lag.b.map(x=>x[1]));
  const pg={}; F.fam.forEach(f=>{const k=f.p;(pg[k]=pg[k]||[0,0,0]);pg[k][0]+=f.n;pg[k][1]+=f.w;pg[k][2]+=f.r;});
  const dt={}; F.fam.forEach(f=>{const k=f.dt;(dt[k]=dt[k]||[0,0,0]);dt[k][0]+=f.n;dt[k][1]+=f.w;dt[k][2]+=f.r;});
  const DTN={nodate:'без дат',withdate:'с датами'};
  const pair=(o,names)=>`<div class="bars">`+Object.keys(o).map(k=>{
    const [n,w]=o[k], pc=100*w/n, mx=Math.max(...Object.values(o).map(v=>100*v[1]/v[0]))||1;
    return `<div class="brow2"><span class="blab">${esc(names?names[k]||k:k)}</span>
      <span class="btrack"><span class="bfill" style="width:${Math.max(2,100*pc/mx)}%"></span></span>
      <span class="bval">${nf(pc,1)}%</span></div>
      <div class="note" style="margin:-2px 0 4px 84px">${w} из ${n} доменов дали регистрацию</div>`;
  }).join('')+`</div>`;

  return `<div class="blk"><h2>Новая выгрузка: 5–7 сентября</h2>
  <p class="note">Свежие ${F.n} событий. Важно: они приходят не только на домены,
  запущенные в эти дни, — в выгрузке есть хвосты запусков от 24 августа.
  Ниже всё разложено по <b>дню запуска домена</b>, а не по дню события.</p>
  <div class="tiles">
    <div class="tile"><div class="k">Событий в выгрузке</div><div class="v">${F.n}</div>
      <div class="c">${F.days.map(d=>d[0].slice(8)+'.'+d[0].slice(5,7)+' — '+d[1]).join(', ')}</div></div>
    <div class="tile g"><div class="k">Регистраций</div><div class="v">${F.reg}</div>
      <div class="c">на ${pl(withDay.length,'домене','доменах','доменах')} из реестра</div></div>
    <div class="tile a"><div class="k">Депозитов</div><div class="v">${F.dep}</div>
      <div class="c">лучшая доля деп/рег за всю историю наблюдений</div></div>
  </div>

  <h3 class="vt">Впервые: домен с двумя депозитами</h3>
  <div class="card"><p>За всю историю ни один домен не давал больше одного депозита —
  четыре прошлых «дубля» оказались одним и тем же событием, попавшим в две выгрузки.
  Здесь дубля нет: <b>gwrl.casino</b> дал депозит 3 сентября по бренду <b>1go</b>
  и второй 6 сентября по бренду <b>spinto</b>. Разные бренды, разные сутки, разные выгрузки.</p>
  <p class="note">Домен запущен 1 сентября в ветке NEW50_12pages_withdate, зона <code>.casino</code>.
  Четыре регистрации, два депозита — единственный такой случай на ${F.deps.length} доменов с депозитами за всю историю.</p></div>

  <h3 class="vt">Сколько проходит между регистрацией и депозитом</h3>
  <div class="bars">`
  +F.lag.b.map(b=>`<div class="brow2"><span class="blab">${esc(b[0])}</span>
     <span class="btrack"><span class="bfill" style="width:${b[1]?Math.max(2,100*b[1]/maxLag):0}%"></span></span>
     <span class="bval">${b[1]}</span></div>`).join('')
  +`</div>
  <p class="verd">Медиана — <b>${nf(F.lag.med,1)} часа</b>. Двадцать пять депозитов из ${F.lag.n}
  приходят в первые шесть часов после регистрации: человек регистрируется и платит за один заход.
  Но хвост есть — максимум <b>${F.lag.mx} часов</b>, то есть трое суток.
  Значит окно в шесть суток закрывает регистрации, а депозиты по ним могут долетать и позже.
  ${F.lag.orphan?`Ещё один депозит пришёл вообще без регистрации в наших данных.`:''}</p>

  <h3 class="vt">Проверка правила «12 страниц лучше 7» на свежих запусках</h3>
  <p class="note">Ветки NEW20, NEW21 и NEW20_3, запущенные 4, 5 и 6 сентября.
  Один контент, одинаковый возраст в обеих половинах, ровно по 30 доменов с каждой стороны.
  Это первая проверка правила <b>вперёд</b>, а не по уже собранным данным.</p>
  ${pair(pg)}
  <p class="verd">Направление то же, что и в истории: <b>16,7 % против 3,3 %</b>,
  точный тест Фишера <b>p = ${nf(F.fisher,2)}</b>. По одному этому набору вывод бы не устоял.
  <b>Важная поправка.</b> Исторический разрыв «27,7 % против 12,0 %», который я раньше
  называл подтверждением, оказался завышен: в него попали домены с обрезанными данными
  за 19–20 августа, и семистраничных среди них непропорционально много. На чистых
  закрытых окнах история даёт 28,2 % против 22,2 % (p = 0,45), а вместе с этим набором —
  25,2 % против 16,1 % (p = 0,088). Направление устойчиво, но порога не достигает:
  двенадцать страниц остаются лучшим кандидатом, а не доказанным рычагом.
  Окна ещё открыты, к 12 сентября цифры вырастут в обеих половинах.</p>

  <h3 class="vt">Та же выборка, но по датам в имени</h3>
  ${pair(dt,DTN)}
  <p class="verd">Ровно то, чего и ждали: даты по-прежнему ничего не значат для денег.
  Разрыв в 2 пункта при таких объёмах — это шум.</p>

  <h3 class="vt">Все домены новой выгрузки</h3>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Рег</th><th>Деп</th>
    <th class="l">День запуска</th><th class="l">Группа</th><th class="l">Бренды</th></tr></thead><tbody>`
  +F.rows.map(r=>`<tr${r.p?' class="q-open"':''}><td class="l"><code>${esc(r.d)}</code></td>
     <td>${r.r||'—'}</td><td>${r.p?`<b class="good">${r.p}</b>`:'—'}</td>
     <td class="l dday">${r.day?esc(r.day):'<span class="mut">не в реестре</span>'}</td>
     <td class="l">${r.g?esc(r.g):'<span class="mut">списка не было</span>'}</td>
     <td class="l">${r.br.map(b=>`<span class="bch sm">${esc(b[0])}${b[1]>1?` <b>×${b[1]}</b>`:''}</span>`).join('')}</td></tr>`).join('')
  +`</tbody></table></div>
  ${noDay.length?`<p class="note">${pl(noDay.length,'домен','домена','доменов')} —
   <code>${noDay.map(r=>esc(r.d)).join('</code>, <code>')}</code> — дали регистрации,
   но их списков запуска мне не присылали. Ни дня, ни группы, ни конфигурации по ним нет.</p>`:''}
  ${F.skipped.length?`<p class="note">Выброшено из разбора: ${F.skipped.map(
    x=>`<code>${esc(x[0])}</code> (${x[1]})</code>`).join(', ')} — это события без нашего домена
    в адресе, они ни к какому запуску не привязываются.</p>`:''}
  </div>`;
}

const TABS=[['days','Дни запуска',tDays],['cards','Дни подробно',tCards],
            ['how','Когда приходят деньги',tHow],['q','Что можно сравнивать',tQ],
            ['fresh','Новая выгрузка',tFresh]];
let TAB='days';
function renderAll(){
  document.getElementById('main').innerHTML=TABS.find(t=>t[0]===TAB)[2]();
  const e=document.getElementById('qf');
  if(e) e.onchange=x=>{showq=x.target.value;renderAll();};
}
document.getElementById('nav').innerHTML=TABS.map(([id,l])=>
  `<button data-t="${id}" aria-selected="${id===TAB}">${l}</button>`).join('');
document.querySelectorAll('#nav button').forEach(b=>b.onclick=()=>{
  TAB=b.dataset.t;
  document.querySelectorAll('#nav button').forEach(x=>x.setAttribute('aria-selected',x.dataset.t===TAB));
  renderAll();window.scrollTo(0,0);});
renderAll();

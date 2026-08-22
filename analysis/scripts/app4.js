const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), pc=(x)=>Math.round(x*100)+'%';
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':(v>=1e3?(v/1e3).toFixed(1).replace('.',',')+'k':Math.round(v)));
const O=D.order, GR=D.groups, DM=D.doms;
const pos=(p)=>p==null?'<span class="mut">—</span>':`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;
const zn=(z)=>`<span class="zone ${z==='.team'?'zt':''}">${esc(z)}</span>`;
const hist=(h)=>h.map(x=>x==null?'<span class="mut">—</span>':
  `<span class="${x<=3?'good':x<=10?'':'mut'}">${x}</span>`).join('<span class="mut"> › </span>');
function spark(s){const mx=Math.max(...s,0.01);
  return '<span class="spark" title="'+s.join(' → ')+'">'+s.map((v,i)=>
    '<i class="'+(i===s.length-1?'hi':'')+'" style="height:'+Math.max(2,Math.round(v/mx*22))+'px"></i>').join('')+'</span>';}

/* ---------------- обзор ---------------- */
function tabOverview(){
  const row=(sn)=>{const g=GR[sn];
    return `<tr><td class="l id">${esc(g.name)}</td><td class="l">${esc(g.pages)}</td>
      <td class="l mut">${esc(g.src)}</td><td class="l mut">${esc(g.theme)}</td>
      <td class="l mut">${g.labels[g.labels.length-1]}</td><td>${g.n}</td>
      <td>${spark(g.ser)}</td><td><b>${f1(g.t10)}</b></td><td>${g.med}</td><td>${f1(g.wo)}</td>
      <td class="${g.leadshare>=.6?'warn':''}">${pc(g.leadshare)}</td>
      <td class="l mut num">${g.serhs.join(' › ')}</td>
      <td class="${g.vch+g.sch?'good':'mut'}"><b>${g.vch+g.sch}</b></td>
      <td>${g.t3}</td><td>${g.brands}</td>
      <td class="${g.z100?'bad':'mut'}">${g.z100}</td></tr>`;};
  return `<div class="blk"><h2>13 групп · сводка</h2>
  <p class="note">Т10/дом, медиана и «без лидера» — по .team-подмножеству. «Доля лидера» —
  какую часть ключей группы держит её лучший домен. Столбик — динамика Т10 по замерам.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Страниц</th>
  <th class="l">Источник</th><th class="l">Шаблон</th><th class="l">Посл. замер</th><th>Дом</th>
  <th>Т10 дин.</th><th>Т10/дом</th><th>Мед</th><th>Без лид.</th><th>Доля лид.</th>
  <th class="l">ВЧ+СЧ дин.</th><th>ВЧ+СЧ</th><th>ТОП-3</th><th>Брендов</th><th>Нет Т100</th>
  </tr></thead><tbody>${O.map(row).join('')}</tbody></table></div></div>

  <div class="blk"><h2>Пришла вторая волна: дорогие бренды</h2>
  <p class="note">На замере 12:06 у трёх групп охват в ТОП-10 упал, а число ВЧ и СЧ выросло.
  Архивный паттерн «дорогие бренды приходят второй волной» в чистом виде.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Т10/дом</th>
  <th class="l">ВЧ+СЧ</th></tr></thead><tbody>
    <tr><td class="l id">nabor28gotovyi</td><td class="l num">13,4 → <b class="bad">9,4</b></td>
      <td class="l num">2 → <b class="good">12</b></td></tr>
    <tr><td class="l id">12pages_withdate · Theme2</td><td class="l num">11,7 → <b class="bad">8,6</b></td>
      <td class="l num">13 → <b class="good">14</b></td></tr>
    <tr><td class="l id">Generation 50</td><td class="l num">0,7 → <b class="good">1,3</b></td>
      <td class="l num">2 → <b class="good">11</b></td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px"><b>На этой стадии общий счёт ТОП-10 — плохая метрика.</b>
  Падение охвата при росте дорогих ключей означает переход на более ценные запросы,
  а не ослабление группы.</p></div>

  <div class="blk"><h2>Смотрите «без лидера», а не среднее</h2>
  <p class="note">Порядок групп по среднему и по устойчивой мере расходится.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th>
  <th class="l">Значения по доменам (.team)</th><th>Среднее</th><th>Медиана</th>
  <th>Без лидера</th><th>Доля лидера</th></tr></thead><tbody>`+
  O.filter(sn=>GR[sn].vals.length>2).sort((a,b)=>GR[b].wo-GR[a].wo).slice(0,8).map(sn=>{
    const g=GR[sn];
    return `<tr><td class="l id">${esc(g.name)}</td>
      <td class="l num">${g.vals.join(', ')}</td><td>${f1(g.t10)}</td><td>${g.med}</td>
      <td class="${g.wo>=8?'good':''}"><b>${f1(g.wo)}</b></td>
      <td class="${g.leadshare>=.6?'bad':'good'}">${pc(g.leadshare)}</td></tr>`;}).join('')+
  `</tbody></table></div>
  <p class="note" style="margin-top:10px">12pages_withdate · Theme1 второй по среднему
  и заметно ниже по «без лидера»: <span class="num">1908.team</span> держит 130 из 167
  ключей группы и все её ВЧ. На группах в 5–10 доменов среднее меряет удачу с чемпионом.</p></div>`;
}

/* ---------------- все домены ---------------- */
function tabAll(){
  const zones=[...new Set(DM.map(d=>d.zone))];
  const waves=[...new Set(DM.map(d=>d.wave))];
  return `<div class="blk"><h2>Все ${D.tot.doms} доменов</h2>
  <p class="note">Отсортированы по силе: сначала домены с дорогими ключами.
  «Динамика» — ключей в ТОП-10 по каждому замеру. Клик по строке — бренды и все ключи
  с историей позиций.</p>
  <div class="filters">
    <label>Группа
      <select id="fg"><option value="">все</option>
      ${O.map(sn=>`<option value="${esc(sn)}">${esc(GR[sn].name)}</option>`).join('')}</select></label>
    <label>Зона
      <select id="fz"><option value="">все</option>
      ${zones.map(z=>`<option value="${esc(z)}">${esc(z)}</option>`).join('')}</select></label>
    <label>Волна
      <select id="fw"><option value="">все</option>
      ${waves.map(w=>`<option value="${esc(w)}">${esc(w)}</option>`).join('')}</select></label>
    <label><input type="checkbox" id="fh"> только с ВЧ/СЧ</label>
    <span class="cnt" id="cnt"></span>
  </div>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Зона</th>
  <th class="l">Группа</th><th class="l">Страниц</th><th class="l">Шаблон</th>
  <th class="l">Контент</th><th class="l">Динамика Т10</th><th>Т10</th><th>Т30</th><th>Т100</th>
  <th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>НЧ</th><th>Брендов</th><th>Лучш.</th>
  </tr></thead><tbody id="allbody">${DM.map(rowDom).join('')}</tbody></table></div></div>`;
}
function rowDom(d,i){
  return `<tr class="clk dr" data-i="${i}" data-g="${esc(d.g)}" data-z="${esc(d.zone)}"
      data-w="${esc(d.wave)}" data-h="${d.vch+d.sch>0?1:0}">
    <td class="l id">${esc(d.d)}</td><td class="l">${zn(d.zone)}</td>
    <td class="l mut">${esc(d.gname)}</td><td class="l mut">${esc(d.pages)}</td>
    <td class="l mut">${esc(d.theme)}</td>
    <td class="l mut">${d.cont?esc(d.cont):'<span class="dim">по группе</span>'}</td>
    <td class="l mut num">${d.tr.join(' › ')}</td>
    <td><b>${d.t10}</b></td><td>${d.t30}</td>
    <td class="${d.t100===0?'bad':''}">${d.t100}</td>
    <td class="${d.t3?'good':'mut'}">${d.t3}</td>
    <td class="${d.vch?'good':'mut'}">${d.vch}</td>
    <td class="${d.sch?'good':'mut'}">${d.sch}</td>
    <td class="mut">${d.nch}</td><td>${d.nb}</td><td>${pos(d.best)}</td></tr>
    <tr class="det" hidden><td colspan="16"><div class="inner"></div></td></tr>`;
}
function wireFilters(){
  const fg=document.getElementById('fg'),fz=document.getElementById('fz'),
        fw=document.getElementById('fw'),fh=document.getElementById('fh'),
        cnt=document.getElementById('cnt');
  if(!fg) return;
  const apply=()=>{let n=0;
    document.querySelectorAll('#allbody tr.dr').forEach(tr=>{
      const ok=(!fg.value||tr.dataset.g===fg.value)&&(!fz.value||tr.dataset.z===fz.value)&&
               (!fw.value||tr.dataset.w===fw.value)&&(!fh.checked||tr.dataset.h==='1');
      tr.hidden=!ok; tr.nextElementSibling.hidden=true;
      if(ok)n++;});
    cnt.textContent=n+' из '+D.tot.doms;};
  [fg,fz,fw].forEach(el=>el.onchange=apply); fh.onchange=apply; apply();
}

/* ---------------- лидеры ---------------- */
function tabLead(){
  const L=DM.filter(d=>d.vch+d.sch>0||d.t10>=8).slice(0,30);
  const card=(d)=>`<div class="lead">
    <div class="lh"><span class="ld">${esc(d.d)}</span>${zn(d.zone)}
      <span class="lg">${esc(d.gname)}</span></div>
    <div class="lm">
      <div><span class="k">ТОП-10</span><span class="v">${d.t10}</span></div>
      <div><span class="k">ТОП-3</span><span class="v ${d.t3?'good':''}">${d.t3}</span></div>
      <div><span class="k">ВЧ</span><span class="v ${d.vch?'good':''}">${d.vch}</span></div>
      <div><span class="k">СЧ</span><span class="v ${d.sch?'good':''}">${d.sch}</span></div>
      <div><span class="k">Брендов</span><span class="v">${d.nb}</span></div>
      <div><span class="k">Лучшая</span><span class="v">${d.best??'—'}</span></div>
    </div>
    <table class="lt"><tbody>
      <tr><td class="l dim">Контент</td><td class="l">${d.cont?'<b class="id">'+esc(d.cont)+'</b>':
        '<span class="mut">'+esc(GR[d.g].cont)+'</span> <span class="dim">— привязка к домену не задана</span>'}</td></tr>
      <tr><td class="l dim">Конфигурация</td><td class="l">${esc(d.fmt)}${
        d.theme&&d.theme!=='—'&&d.theme!=='?'?' · шаблон '+esc(d.theme):''}</td></tr>
      <tr><td class="l dim">Динамика ТОП-10</td><td class="l num">${d.tr.join(' › ')}
        <span class="dim">(${d.labels.join(', ')})</span></td></tr>
      <tr><td class="l dim">ТОП-30 / ТОП-100</td><td class="l num">${d.tr30.join(' › ')} &nbsp;·&nbsp; ${d.tr100.join(' › ')}</td></tr>
      <tr><td class="l dim">Дорогие бренды</td><td class="l">${
        d.brands.filter(b=>b.t!=='НЧ').length?
        d.brands.filter(b=>b.t!=='НЧ').map(b=>`<span class="chip ${b.t==='ВЧ'?'v':'s'}">${esc(b.b)} <b>#${b.best}</b> ${kf(b.v)}</span>`).join(' '):
        '<span class="mut">нет</span>'}</td></tr>
    </tbody></table>
    <button class="more" data-lead="${esc(d.d)}">показать все ключи (${d.keys.filter(k=>k.p).length})</button>
    <div class="leadkeys" hidden></div></div>`;
  return `<div class="blk"><h2>Домены-лидеры</h2>
  <p class="note">${L.length} доменов, взявших хотя бы один дорогой ключ или 8+ ключей в ТОП-10.
  Контент указан точно там, где привязка домен↔контент задавалась явно —
  это группы «имена» и «наборы». Для остальных показан набор контентов группы.</p>
  <div class="leads">${L.map(card).join('')}</div></div>`;
}
function wireLead(){
  document.querySelectorAll('button.more').forEach(b=>{b.onclick=()=>{
    const box=b.nextElementSibling; box.hidden=!box.hidden;
    b.textContent=box.hidden?b.textContent.replace('скрыть','показать все'):b.textContent.replace('показать все','скрыть');
    if(box.dataset.done) return; box.dataset.done=1;
    const d=DM.find(x=>x.d===b.dataset.lead);
    box.innerHTML=`<div class="tw"><table><thead><tr><th class="l">Ключ</th>
      <th class="l">Бренд</th><th class="l">Тип</th><th>Тир</th><th>Объём</th>
      <th class="l">Позиции по замерам</th></tr></thead><tbody>`+
      d.keys.filter(k=>k.p).map(k=>`<tr><td class="l">${esc(k.q)}</td>
        <td class="l mut">${esc(k.b)}</td><td class="l mut">${esc(k.c)}</td>
        <td>${tg(k.t)}</td><td>${kf(k.v)}</td>
        <td class="l num">${hist(k.h)}</td></tr>`).join('')+`</tbody></table></div>`;};});
}

/* ---------------- зоны ---------------- */
function tabZones(){
  const Z=D.zones;
  const rows=Z.map(z=>`<tr><td class="l">${zn(z.z)}</td><td>${z.n}</td>
    <td><b>${f1(z.t10/z.n)}</b></td><td>${z.t10}</td>
    <td class="${z.hs?'good':'mut'}">${z.hs}</td><td>${z.t3}</td>
    <td>${pc(z.ent/z.n)}</td></tr>`).join('');
  const nt=Z.filter(z=>z.z!=='.team');
  const ntn=nt.reduce((a,z)=>a+z.n,0), ntk=nt.reduce((a,z)=>a+z.t10,0);
  const t=Z.find(z=>z.z==='.team');
  return `<div class="blk"><h2>Доменные зоны</h2>
  <p class="note">Все ${D.tot.doms} доменов на последнем замере своей группы. Ниже — контролируемый тест зон и общая картина.</p>
  <div class="tw"><table><thead><tr><th class="l">Зона</th><th>Доменов</th>
  <th>Т10/дом</th><th>Ключей Т10</th><th>ВЧ+СЧ</th><th>ТОП-3</th><th>Есть Т10</th>
  </tr></thead><tbody>${rows}
  <tr class="tot"><td class="l">Все кроме .team</td><td>${ntn}</td>
    <td><b>${f1(ntk/ntn)}</b></td><td>${ntk}</td>
    <td class="mut">${nt.reduce((a,z)=>a+z.hs,0)}</td>
    <td>${nt.reduce((a,z)=>a+z.t3,0)}</td>
    <td>${pc(nt.reduce((a,z)=>a+z.ent,0)/ntn)}</td></tr>
  </tbody></table></div></div>

  <div class="blk"><h2>Контролируемый тест: .team против .lol на одном контенте</h2>
  <p class="note">Группа nabor-53: десять контентов, пять на .team и пять на .lol,
  привязка 1:1, запуск в одну минуту. Единственное отличие между половинами — зона.
  Первый и пока единственный чистый зоновый тест за всё наблюдение. Два замера.</p>
  <div class="tw"><table><thead><tr><th class="l">Половина</th><th class="l">Замер</th>
  <th class="l">Значения по доменам</th><th>Среднее</th><th>Медиана</th><th>Без лидера</th>
  <th>ВЧ</th><th>СЧ</th><th>ТОП-3</th></tr></thead><tbody>
    <tr><td class="l id" rowspan="2">.team</td><td class="l mut">22.08 01:24</td>
      <td class="l num mut">43, 20, 5, 2, 0</td><td class="mut">14,0</td><td class="mut">5</td>
      <td class="mut">6,8</td><td class="mut">10</td><td class="mut">1</td><td class="mut">24</td></tr>
    <tr><td class="l">22.08 11:19</td><td class="l num">39, 37, 7, 3, 1</td>
      <td><b>17,4</b></td><td>7</td><td><b>12,0</b></td>
      <td class="good"><b>11</b></td><td class="good">6</td><td>18</td></tr>
    <tr><td class="l id" rowspan="2">.lol</td><td class="l mut">22.08 01:24</td>
      <td class="l num mut">6, 6, 3, 1, 0</td><td class="mut">3,2</td><td class="mut">3</td>
      <td class="mut">2,5</td><td class="mut">0</td><td class="mut">0</td><td class="mut">8</td></tr>
    <tr><td class="l">22.08 11:19</td><td class="l num">14, 8, 6, 3, 0</td>
      <td>6,2</td><td>6</td><td>4,3</td>
      <td class="good">2</td><td class="good">2</td><td>9</td></tr>
  </tbody></table></div>
  <div class="cards" style="margin-top:14px">
    <div class="card ok"><h3>.team сильнее, но .lol ожил</h3>
      <p>«Без лидера» <span class="big">12,0</span> против 4,3 — .team почти втрое выше
      на типичном домене.</p>
      <p>Но медианы <b>7 против 6</b> практически сравнялись, и .lol впервые взял
      дорогие ключи: 2 ВЧ и 2 СЧ там, где на первом замере был ноль.</p></div>
    <div class="card"><h3>Дорогие ключи: 17 против 4</h3>
      <p>Разрыв сократился с 11:0 до 17:4. .lol отстаёт, но уже не пустой.</p></div>
    <div class="card err"><h3>Оговорка та же</h3>
      <p>Пять доменов на сторону. У .team два чемпиона (39 и 37), у .lol один (14) —
      средние держатся на них.</p></div>
  </div></div>

  <div class="blk"><h2>Generation 50 выпадает из индекса</h2>
  <p class="note">Единственная группа с отрицательной динамикой по всем уровням сразу.</p>
  <div class="tw"><table><thead><tr><th class="l">Замер</th><th>Т10/дом</th><th>Т30/дом</th>
  <th>Т100/дом</th><th>Нет в Т100</th><th>ВЧ+СЧ</th></tr></thead><tbody>
    <tr><td class="l mut">20.08 22:29</td><td>0,0</td><td>0,4</td><td>3,1</td>
      <td class="mut">20/50</td><td class="mut">0</td></tr>
    <tr><td class="l mut">21.08 02:00</td><td>0,7</td><td>2,1</td><td><b>17,7</b></td>
      <td class="good">2/50</td><td>2</td></tr>
    <tr><td class="l mut">21.08 12:06</td><td><b>1,3</b></td><td><b>2,5</b></td><td>12,9</td>
      <td class="good">3/50</td><td class="good"><b>11</b></td></tr>
    <tr><td class="l">22.08 11:19</td><td class="bad">0,9</td><td class="bad">1,7</td>
      <td class="bad">4,1</td><td class="bad"><b>17/50</b></td><td>10</td></tr>
  </tbody></table></div>
  <div class="cards" style="margin-top:14px">
    <div class="card err"><h3>14 доменов выпали из ТОП-100 целиком</h3>
      <p>Между 12:06 и 11:19 доменов без единого ключа в сотне стало
      <span class="big">17</span> вместо 3.</p>
      <p>Это не «просел после пика» — при обычном проседании домен теряет верхние
      позиции, но остаётся в сотне. Здесь он исчезает из выдачи.</p></div>
    <div class="card"><h3>Спад начался раньше</h3>
      <p>Т100 на домен: 3,1 → 17,7 → 12,9 → 4,1. Пик пройден ещё на замере 02:00,
      к 12:06 охват уже падал, а к утру обвалился.</p></div>
    <div class="card"><h3>Что это может быть</h3>
      <p>Массовое одновременное выпадение всей партии — это поведение фильтра
      на партию, а не сумма отдельных неудач. 50 доменов одной зоны, поднятые
      в один момент.</p>
      <p class="mut">Проверяемо следующим замером: если вернутся — был сбой съёма,
      если нет — партия под санкцией.</p></div>
  </div></div>

  <div class="blk"><h2>Что видно по всем зонам</h2>
  ${(()=>{const bz=Z.find(z=>z.z==='.buzz'), lo=Z.find(z=>z.z==='.lol'), ca=Z.find(z=>z.z==='.casino');
    const dead=Z.filter(z=>z.n===1&&z.t10===0);
    const ones=Z.filter(z=>z.n===1&&z.t10>0);
    return `<div class="cards">
    <div class="card ok"><h3>.lol вчетверо лучше .buzz</h3>
      <p><span class="big">${f1(lo.t10/lo.n)}</span> ключей на домен против
      ${f1(bz.t10/bz.n)} у .buzz, на выборках ${lo.n} и ${bz.n} доменов.</p>
      <p>Есть хоть один ключ в ТОП-10: ${lo.ent} из ${lo.n} против ${bz.ent} из ${bz.n}.
      ТОП-3: ${lo.t3} против ${bz.t3}. Дорогих: ${lo.hs} против ${bz.hs}.</p>
      <p class="mut">.buzz можно закрывать. .lol — рабочая альтернатива, слабее .team.</p></div>
    <div class="card"><h3>.casino держится третий замер</h3>
      <p><span class="big">${f1(ca.t10/ca.n)}</span> ключей на домен на ${ca.n} доменах,
      ${ca.hs} дорогих, у всех трёх есть результат.</p>
      <p>В архиве зона давала 0,43 ВЧ+СЧ на домен и проигрывала .team в 5 запусках из 7.
      <span class="mut">Три домена — по-прежнему сигнал, но устойчивый.</span></p></div>
    <div class="card"><h3>Одиночки: три из шестнадцати ожили</h3>
      <p>${ones.map(z=>`<span class="num">${esc(z.z)}</span> ${z.t10}`).join(', ')} —
      ключей в ТОП-10 на одном домене.</p>
      <p>Остальные ${dead.length} зон по одному домену дали ноль:
      ${dead.map(z=>esc(z.z)).join(', ')}.</p></div>
  </div>`;})()}
  <p class="note" style="margin-top:14px">Порядок зон по силе:
  <b>.team → .lol → .buzz</b>. Кандидаты на проверку — .casino (3 домена, держится),
  .online и .shop (по одному домену, но с результатом). Остальное — ноль.</p></div>`;
}

function tabBrands(){
  const B=D.brands, hi=B.filter(b=>b.t!=='НЧ');
  const rows=B.map((b,i)=>`<tr class="clk" data-b="${i}">
    <td class="l ${b.t!=='НЧ'?'id':''}">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
    <td><b>${b.n}</b></td><td>${pos(b.best)}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td>
    <td>${b.nd}</td><td class="l mut">${b.groups.slice(0,2).join(', ')}${b.groups.length>2?' +'+(b.groups.length-2):''}</td>
    <td class="l mut">${Object.entries(b.cats).sort((x,y)=>y[1]-x[1]).slice(0,3).map(([k,v])=>k+' ×'+v).join(', ')}</td>
  </tr><tr class="det" hidden><td colspan="9"><div class="inner"></div></td></tr>`).join('');
  return `<div class="blk"><h2>Какие ключи взял каждый бренд</h2>
  <p class="note">Все ${D.tot.t10} ключей в ТОП-10. Клик по бренду — запросы с историей позиций,
  доменом и группой.</p>
  <div class="tiles">
    <div class="tile"><div class="k">Брендов</div><div class="v">${B.length}</div>
      <div class="c">из 157 в справочнике</div></div>
    <div class="tile a"><div class="k">Ключей в ТОП-10</div><div class="v">${D.tot.t10}</div>
      <div class="c">по ${D.tot.doms} доменам</div></div>
    <div class="tile g"><div class="k">В ТОП-3</div><div class="v">${D.tot.t3}</div>
      <div class="c">${pc(D.tot.t3/D.tot.t10)} от ТОП-10</div></div>
    <div class="tile"><div class="k">Дорогих брендов</div><div class="v">${hi.length}</div>
      <div class="c">${hi.reduce((a,b)=>a+b.n,0)} ключей</div></div>
  </div>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
  <th>Ключей</th><th>Лучш.</th><th>ТОП-3</th><th>Дом</th><th class="l">Группы</th>
  <th class="l">Типы запросов</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

/* ---------------- типы запросов ---------------- */
function tabCats(){
  const C=D.cats, tot=D.tot.t10;
  const rows=C.map((c,i)=>`<tr class="clk" data-c="${i}">
    <td class="l ${c.t10>tot*0.15?'id':''}">${esc(c.c)}</td><td><b>${c.t10}</b></td>
    <td>${pc(c.t10/tot)}</td><td class="${c.t3?'good':'mut'}">${c.t3}</td>
  </tr><tr class="det" hidden><td colspan="4"><div class="inner"></div></td></tr>`).join('');
  return `<div class="blk"><h2>Что за запросы заходят</h2>
  <p class="note">Тип определяется по первому совпавшему признаку: зеркало → вход →
  регистрация → офиц. сайт → бонус → играть → приложение → отзывы → «бренд + казино» →
  «бренд без добавок». Клик — примеры.</p>
  <div class="tw"><table><thead><tr><th class="l">Тип запроса</th><th>В ТОП-10</th>
  <th>Доля</th><th>ТОП-3</th></tr></thead><tbody>${rows}</tbody></table></div>
  <p class="note" style="margin-top:10px">«Бренд + казино» держит ${pc(C[0].t10/tot)} всего
  ТОП-10. Голое название бренда почти не берётся — выдачу по нему держит сам бренд.</p></div>`;
}

/* ---------------- раскрытия ---------------- */
function fill(){
  document.querySelectorAll('tr.clk[data-i]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1; const d=DM[+tr.dataset.i];
    const ks=d.keys.filter(k=>k.p);
    let h=`<div><h4>${esc(d.d)} · ${esc(d.gname)} · ${esc(d.fmt)}${
      d.cont?' · контент <b class="id">'+esc(d.cont)+'</b>':''}</h4></div>`;
    if(d.brands.length) h+=`<div><h4>Бренды в ТОП-10 — ${d.brands.length}</h4><div class="tw"><table>
      <thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th><th>Лучшая</th><th>Ключей</th>
      <th>ТОП-3</th></tr></thead><tbody>`+
      d.brands.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
        <td>${pos(b.best)}</td><td>${b.n}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td></tr>`).join('')+
      `</tbody></table></div></div>`;
    if(ks.length) h+=`<div><h4>Ключи в ТОП-10 — ${ks.length} · позиции по замерам
      (${d.labels.join(', ')})</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th class="l">Тип</th><th>Тир</th>
      <th>Объём</th><th class="l">Позиции</th></tr></thead><tbody>`+
      ks.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
        <td class="l mut">${esc(k.c)}</td><td>${tg(k.t)}</td><td>${kf(k.v)}</td>
        <td class="l num">${hist(k.h)}</td></tr>`).join('')+`</tbody></table></div></div>`;
    else h+='<div><h4>Ни одного ключа в ТОП-10</h4></div>';
    slot.innerHTML=h;};});
  document.querySelectorAll('tr.clk[data-b]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1; const b=D.brands[+tr.dataset.b];
    slot.innerHTML=`<div><h4>${esc(b.b)} — ${b.keys.length} ключей в ТОП-10</h4>
      <div class="tw"><table><thead><tr><th class="l">Ключ</th><th class="l">Тип</th>
      <th class="l">Позиции по замерам</th><th class="l">Домен</th><th class="l">Группа</th>
      </tr></thead><tbody>`+
      b.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.c)}</td>
        <td class="l num">${hist(k.h)}</td><td class="l num">${esc(k.d)}</td>
        <td class="l mut">${esc(k.g)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
  document.querySelectorAll('tr.clk[data-c]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1; const c=D.cats[+tr.dataset.c];
    slot.innerHTML=`<div><h4>Примеры — «${esc(c.c)}»</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th>Позиция</th></tr></thead><tbody>`+
      c.ex.map(e=>`<tr><td class="l">${esc(e.q)}</td><td class="l mut">${esc(e.b)}</td>
        <td>${pos(e.p)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
  wireFilters(); wireLead();
}

const TABS=[["Обзор",tabOverview],["Все домены",tabAll],["Лидеры",tabLead],
  ["Зоны",tabZones],["Бренды и ключи",tabBrands],["Типы запросов",tabCats]];
const nav=document.getElementById('nav'), main=document.getElementById('main');
TABS.forEach(([name],i)=>{const b=document.createElement('button');
  b.textContent=name; b.setAttribute('role','tab'); b.setAttribute('aria-selected',i===0);
  b.onclick=()=>show(i); nav.appendChild(b);
  const s=document.createElement('section'); s.hidden=i!==0; main.appendChild(s);});
function show(i){
  [...nav.children].forEach((b,j)=>b.setAttribute('aria-selected',i===j));
  [...main.children].forEach((s,j)=>{s.hidden=i!==j;
    if(i===j&&!s.dataset.done){s.dataset.done=1;s.innerHTML=TABS[j][1]();fill();}});
  window.scrollTo({top:0,behavior:'instant'});}
main.insertAdjacentHTML('beforeend','<div class="foot">'+D.tot.groups+' групп · '+D.tot.doms+
  ' доменов · '+D.tot.t10+' ключей в ТОП-10 · '+D.tot.brands+' брендов · '+
  'последний съём 21.08 в 12:06, кроме 12pages_withdate · Theme1 (02:00) и ночных групп (20.08 22:29) · '+
  'ядро 1570 ключей, ВЧ ≥ 1 млн, СЧ 700k–1 млн, бренды vovan и pari исключены</div>');
show(0);

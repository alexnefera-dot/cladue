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
  return `<div class="blk"><h2>${D.tot.groups} групп · сводка</h2>
  <p class="note">Т10/дом, медиана и «без лидера» — по .team-подмножеству. «Доля лидера» —
  какую часть ключей группы держит её лучший домен. Столбик — динамика Т10 по замерам.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Страниц</th>
  <th class="l">Источник</th><th class="l">Шаблон</th><th class="l">Посл. замер</th><th>Дом</th>
  <th>Т10 дин.</th><th>Т10/дом</th><th>Мед</th><th>Без лид.</th><th>Доля лид.</th>
  <th class="l">ВЧ+СЧ дин.</th><th>ВЧ+СЧ</th><th>ТОП-3</th><th>Брендов</th><th>Нет Т100</th>
  </tr></thead><tbody>${O.map(row).join('')}</tbody></table></div></div>

  <div class="blk"><h2>Выгрузка 23.08 23:30 — съём не закончился</h2>
  <p class="note">Файл выгружен в 23:30:16, снимок помечен 23:28–23:29. Проверка
  1571 ключа не успела пройти: данные есть только по первым строкам ядра,
  дальше пусто. В основной отчёт эта выгрузка <b>не включена</b> —
  все цифры выше по-прежнему на полном замере 23.08 10:55–10:56.</p>
  <div class="tw"><table><thead><tr><th class="l">Лист</th><th>Ядро</th>
  <th>Последняя строка с данными</th><th>Покрытие</th>
  <th>Ключей с позицией</th></tr></thead><tbody>
    <tr><td class="l id">NEW50_5_12pages_nodate</td><td>1571</td><td>530</td>
      <td class="bad">34%</td><td>131</td></tr>
    <tr><td class="l id">Generator_11page_img</td><td>1571</td><td>526</td>
      <td class="bad">33%</td><td>45</td></tr>
    <tr><td class="l id">NEW50_5_7pages_nodate</td><td>1571</td><td>523</td>
      <td class="bad">33%</td><td>14</td></tr>
    <tr><td class="l id">NEW50_5_12pages_withdate</td><td>1571</td><td>447</td>
      <td class="bad">28%</td><td>76</td></tr>
    <tr><td class="l id">NEW50_5_7pages_withdate</td><td>1571</td><td>389</td>
      <td class="bad">25%</td><td>78</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Проверка: у <span class="num">3096.team</span>
  из 311 ключей осталось 95, но <b>48 из них на прежних позициях</b>
  (медианный сдвиг −1, то есть чуть выше), а 263 просто без данных.
  Провалившийся сайт тянет ключи вниз — здесь они не опустились, а не проверены.</p>

  <h3 style="margin-top:20px;font-family:var(--cond);font-size:17px">Срез по общей части ядра: провала нет</h3>
  <p class="note">Если сравнивать оба замера только по тем ключам, что успели
  провериться, картина обратная — все группы держатся или растут.</p>
  <div class="tw"><table><thead><tr><th class="l">Ветка</th><th>Срез ядра</th>
  <th class="l">Т10/дом .team 10:55 › 23:29</th><th class="l">Значения</th>
  <th class="l">ВЧ+СЧ</th><th class="l">ТОП-3</th></tr></thead><tbody>
    <tr><td class="l id">12 стр без дат</td><td>530</td>
      <td class="l num">9,5 › <b class="good">12,5</b></td>
      <td class="l num">25, 12, 1, 0 › 35, 13, 2, 0</td>
      <td class="l num">15 › <b class="good">28</b></td><td class="l num">16 › 18</td></tr>
    <tr><td class="l id">12 стр + даты</td><td>447</td>
      <td class="l num">4,6 › <b class="good">5,4</b></td>
      <td class="l num">15, 7, 1, 0, 0 › 20, 7, 0, 0, 0</td>
      <td class="l num">3 › 4</td><td class="l num">6 › <b class="good">11</b></td></tr>
    <tr><td class="l id">7 стр + даты</td><td>389</td>
      <td class="l num">3,0 › <b class="good">3,5</b></td>
      <td class="l num">9, 3, 0, 0 › 13, 1, 0, 0</td>
      <td class="l num">8 › 8</td><td class="l num">1 › 0</td></tr>
    <tr><td class="l id">11 стр + картинки</td><td>526</td>
      <td class="l num">2,6 › <b>2,6</b></td>
      <td class="l num">4, 3, 3, 3, 0 › 5, 3, 3, 2, 0</td>
      <td class="l num">5 › 4</td><td class="l num">6 › 7</td></tr>
    <tr><td class="l id">7 стр без дат</td><td>523</td>
      <td class="l num">0 › 0</td>
      <td class="l mut">нет доменов .team; ldtq.click 6 › 4 ключа</td>
      <td class="l num">0 › 0</td><td class="l num">4 › 0</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">На общей части ядра <b>12 стр без дат</b>
  за 12 часов удвоили дорогие ключи (15 › 28) и остаются впереди датированной
  ветки вчетверо по ВЧ+СЧ. Вывод утреннего замера держится.
  <b>Нужна повторная выгрузка после того, как съём закончится.</b></p></div>

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

  <div class="blk"><h2>Серия NEW50_5: матрица объём × даты</h2>
  <p class="note">Четыре ветки из одного прогона генерации 21.08 в 13:29–13:30.
  Датированные запущены 22.08 в 01:18, недатированные — 22.08 в 23:04–23:05.
  Замер 23.08 в 10:55–10:56 снял все четыре ветки в пределах одной минуты.</p>
  <div class="tw"><table><thead><tr><th class="l">Ветка</th><th>.team</th>
  <th class="l">Т10/дом по замерам</th><th class="l">Значения (посл. замер)</th>
  <th>Медиана</th><th>Без лидера</th><th>ВЧ+СЧ</th><th>ТОП-3</th></tr></thead><tbody>
    <tr><td class="l id">12 стр + даты</td><td>5</td><td class="l num">10,0 › 26,4 › <b>25,8</b></td>
      <td class="l num">71, 54, 4, 0, 0</td><td>4</td><td class="good"><b>14,5</b></td>
      <td>19</td><td>28</td></tr>
    <tr><td class="l id">12 стр без дат</td><td>4</td><td class="l num">16,3 › <b>35,0</b></td>
      <td class="l num">100, 35, 4, 1</td><td class="good"><b>19,5</b></td><td>13,3</td>
      <td class="good"><b>25</b></td><td class="good"><b>54</b></td></tr>
    <tr><td class="l id">7 стр + даты</td><td>4</td><td class="l num">8,8 › 28,0 › <b>27,8</b></td>
      <td class="l num">80, 31, 0, 0</td><td>15,5</td><td>10,3</td><td>29</td><td>29</td></tr>
    <tr><td class="l id">7 стр без дат</td><td class="bad">0</td><td class="l num">0,5 › <b>5,3</b></td>
      <td class="l mut">27, 3, 1, 1, 0, 0 — все зоны экзотические</td>
      <td class="mut">—</td><td class="mut">—</td><td class="mut">0</td><td>11</td></tr>
  </tbody></table></div>
  <div class="cards" style="margin-top:14px">
    <div class="card"><h3>Даты при 12 страницах: наконец чистое сравнение</h3>
      <p>Контент обеих веток сгенерирован в одну минуту, замер снят с разницей в минуту.
      Недатированная ветка при этом <b>моложе</b> — 12 часов жизни против 34 —
      и на втором замере против третьего.</p>
      <p>И всё равно впереди: среднее <b>35,0 против 25,8</b>, медиана
      <b>19,5 против 4,0</b>, ВЧ <b>14 против 4</b>, ТОП-3 <b>54 против 28</b>.</p>
      <p class="mut">Но «без лидера» — паритет: 13,3 против 14,5. Весь отрыв держит
      один домен <span class="num">3096.team</span> со 100 ключами.
      В ветках 4 и 5 доменов .team — это направление, а не доказательство.</p></div>
    <div class="card"><h3>Датированная ветка встала, недатированная растёт</h3>
      <p>12 стр + даты за сутки: 26,4 → 25,8. Внутри — расхождение:
      1947.team 53 › 71, а blsr.team 64 › 54, vfkd.team 11 › 4, 2214.team 4 › 0.</p>
      <p>12 стр без дат за 10 часов выросли <b>все четыре</b>:
      48 › 100, 16 › 35, 1 › 4, 0 › 1.</p></div>
    <div class="card"><h3>Объём страниц при датах: разницы нет</h3>
      <p>12 стр — 25,8, 7 стр — 27,8. Устойчивые меры расходятся в разные стороны:
      медиана 4 против 15,5 в пользу семи, «без лидера» 14,5 против 10,3 в пользу двенадцати.</p>
      <p class="mut">Два замера подряд дают один и тот же ответ: на 4–5 доменах
      объём страниц не виден.</p></div>
    <div class="card"><h3>Экзотическая ветка ожила</h3>
      <p><span class="num">ldtq.click</span> за 10 часов: <b>3 › 27</b> ключей в ТОП-10,
      44 в ТОП-30, 107 в сотне, <b>10 в ТОП-3</b> по 10 брендам.</p>
      <p>Остальные пятеро: .live 3, .fun 1, .lol 1, .work 0, .space 0.
      Экзотика может выстрелить, но это один домен из шести.</p></div>
    <div class="card err"><h3>Взаимодействие всё ещё не считается</h3>
      <p>У ветки «7 страниц без дат» <b>ноль доменов .team</b> — сравнивать её с
      «7 стр + даты» по общей метрике нельзя.</p>
      <p>Матрица собрана, но из четырёх сравнений считаются два.</p></div>
  </div></div>

  <div class="blk"><h2>Картинки: второй замер, снова внутри разброса</h2>
  <p class="note">Это ровно то, о чём предупреждалось при регистрации группы.</p>
  <div class="tw"><table><thead><tr><th class="l">Партия 11 страниц</th><th>.team</th>
  <th class="l">Т10/дом по замерам</th><th class="l">Значения (посл.)</th>
  <th>Без лидера</th><th>ВЧ+СЧ</th><th>ТОП-3</th></tr></thead><tbody>
    <tr><td class="l mut">Generator_11page (20.08)</td><td>5</td>
      <td class="l num mut">32,0 › 29,2 › 60,0</td>
      <td class="l num mut">102, 85, 61, 28, 24</td><td class="mut">49,5</td>
      <td class="mut">44</td><td class="mut">56</td></tr>
    <tr><td class="l mut">Generator_11page_2 (20.08)</td><td>4</td>
      <td class="l num mut">3,0 › 4,0 › 9,8</td>
      <td class="l num mut">15, 13, 10, 1</td><td class="mut">8,0</td>
      <td class="mut">1</td><td class="mut">4</td></tr>
    <tr><td class="l mut">Generator_11page_21.08</td><td>8</td>
      <td class="l num mut">5,5 › 4,5</td>
      <td class="l num mut">14, 6, 6, 4, 2, 2, 1, 1</td><td class="mut">3,1</td>
      <td class="mut">9</td><td class="mut">13</td></tr>
    <tr><td class="l id">Generator_11page_img (22.08)</td><td>5</td>
      <td class="l num">4,8 › <b>13,6</b></td>
      <td class="l num">39, 14, 9, 4, 2</td><td>7,3</td>
      <td>5</td><td><b>21</b></td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Вторые замеры базового формата без картинок:
  <b>29,2 · 4,0 · 4,5</b>. Группа с картинками дала <b>13,6</b> — снова внутри разброса,
  выше двух партий из трёх. Первые замеры вели себя так же: 3,0 · 5,5 · 32,0 против 4,8.</p>
  <p class="note">Дорогие ключи не подтвердились: на первом замере было 6 ВЧ+СЧ,
  на втором <b>5</b> — то, что при регистрации отмечалось как «слабый плюс»,
  за сутки сошло на нет. Зато ТОП-3 вырос до 21 на пяти доменах.</p>
  <p class="note"><b>Чтобы измерить картинки, нужна пара img против no-img из одного
  прогона генерации</b> — схема, которая сработала с шаблонами.</p></div>

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

/* ---------------- конверсии ---------------- */
function tabConv(){
  const C=D.conv, f2=(x)=>x.toFixed(2).replace('.',',');
  const gr=C.groups.map(g=>`<tr><td class="l id">${esc(g.g)}</td><td class="l mut">${esc(g.pages)}</td>
    <td>${g.n}</td><td class="mut">${f1(g.days)}</td><td>${g.nd}</td>
    <td class="${g.reg?'good':'mut'}"><b>${g.reg}</b></td>
    <td class="${g.dep?'good':'mut'}">${g.dep}</td>
    <td class="num"><b>${f2(g.rpd)}</b></td><td class="mut">${g.t10}</td>
    <td class="num mut">${g.r100==null?'—':f1(g.r100)}</td></tr>`).join('');
  const fm=C.fmt.map(x=>`<tr><td class="l id">${esc(x.b)}</td><td>${x.n}</td>
    <td class="mut">${f1(x.dd)}</td><td><b>${x.reg}</b></td><td class="mut">${x.dep}</td>
    <td class="num"><b>${f2(x.rpd)}</b></td><td class="mut">${x.t10}</td>
    <td class="num">${f1(x.r100)}</td></tr>`).join('');
  const kn=C.doms.filter(d=>d.known).slice(0,26).map(d=>`<tr><td class="l id">${esc(d.d)}</td>
    <td>${zn(d.zone)}</td><td class="l mut">${esc(d.g||'—')}</td>
    <td><b>${d.reg}</b></td><td class="${d.dep?'good':'mut'}">${d.dep}</td>
    <td class="mut">${d.t10==null?'—':d.t10}</td><td class="mut">${d.t3==null?'—':d.t3}</td>
    <td class="l mut">${d.brands.map(b=>esc(b[0])+(b[1]>1?'×'+b[1]:'')).join(', ')}</td></tr>`).join('');
  const un=C.doms.filter(d=>!d.known).slice(0,24).map(d=>`<tr><td class="l id">${esc(d.d)}</td>
    <td>${zn(d.zone)}</td><td><b>${d.reg}</b></td>
    <td class="${d.dep?'good':'mut'}">${d.dep}</td>
    <td class="l mut">${d.brands.map(b=>esc(b[0])+(b[1]>1?'×'+b[1]:'')).join(', ')}</td></tr>`).join('');
  const bl=C.brands.map(b=>`<tr><td class="l id">${esc(b.b||'—')}</td><td>${b.reg}</td>
    <td class="${b.dep?'good':'mut'}">${b.dep}</td></tr>`).join('');
  const zl=C.zones.map(z=>`<tr><td class="l">${zn(z.z)}</td><td>${z.reg}</td>
    <td class="${z.dep?'good':'mut'}">${z.dep}</td></tr>`).join('');
  const B=C.buck, bsum=Object.values(B).reduce((a,b)=>a+b,0);
  const bk=['ТОП-3','ТОП-10','ТОП-30','ТОП-100','не ранжировался','бренда нет в ядре']
    .filter(k=>B[k]).map(k=>`<tr><td class="l ${k.indexOf('ТОП')===0?'':'bad'}">${k}</td>
      <td><b>${B[k]}</b></td><td class="mut">${Math.round(100*B[k]/bsum)}%</td></tr>`).join('');
  return `<div class="blk"><h2>Конверсии: ${C.tot.reg} рег и ${C.tot.dep} деп, ${C.period}</h2>
  <p class="note">${C.tot.ev} событий с привязкой к домену на ${C.tot.doms} доменах
  (${C.skipped} записи без домена — хост в отчёте равен поисковику — отброшены).
  Из них <b>${C.new.ev}</b> событий на ${C.new.doms} доменах из реестра групп и
  <b>${C.old.ev}</b> на ${C.old.doms} доменах прошлых запусков.
  Депозит приходит в тот же час, что и регистрация (медианный лаг 1 минута),
  так что доля депозитов не занижена возрастом запуска.</p>
  <div class="cards">
    <div class="card ok"><h3>Новые запуски: ${C.new.reg} рег, ${C.new.dep} деп</h3>
      <p>Доля депозитов <span class="big">${f1(100*C.new.dep/C.new.reg)}%</span></p></div>
    <div class="card"><h3>Прошлые запуски: ${C.old.reg} рег, ${C.old.dep} деп</h3>
      <p>Доля депозитов <span class="big">${f1(100*C.old.dep/C.old.reg)}%</span>
      <span class="mut">— в шесть раз выше при сопоставимом числе регистраций</span></p></div>
  </div></div>

  <div class="blk"><h2>Формат страниц: 12 против 7</h2>
  <p class="note">Нормировка на домен·день — сколько регистраций даёт один домен за сутки жизни.
  Правая пара колонок нормирует уже на видимость: регистраций на 100 ключей в ТОП-10.</p>
  <div class="tw"><table><thead><tr><th class="l">Формат</th><th>Дом</th><th>Дом·дней</th>
  <th>Рег</th><th>Деп</th><th>Рег/дом/день</th><th>Т10</th><th>Рег/100 Т10</th>
  </tr></thead><tbody>${fm}</tbody></table></div>
  <div class="cards" style="margin-top:14px">
    <div class="card ok"><h3>На домен 12 страниц бьют 7 в шесть раз</h3>
      <p>0,20 против 0,03 регистрации на домен в сутки. Если бы ставка была общей,
      на семистраничных ожидалось бы 22 регистрации — наблюдалось 7.
      <b>P(X≤7) = 0,0002.</b> На одних .team то же самое: 0,24 против 0,04, P = 0,0006.</p>
      <p class="mut">По позициям объём страниц не разделялся ни разу. По конверсиям — разделился.</p></div>
    <div class="card err"><h3>Но это в основном видимость, а не конверсия</h3>
      <p>На 100 ключей в ТОП-10: 12 страниц — 4,0 регистрации, 11 страниц — 3,1,
      7 страниц — 2,3. Разрыв падает с 6× до 1,7×, и на 32 против 7 регистраций
      такая разница уже не значима.</p>
      <p><b>Двенадцать страниц выигрывают тем, что лучше стоят, а не тем,
      что лучше конвертят.</b></p></div>
  </div></div>

  <div class="blk"><h2>Группы по конверсии</h2>
  <p class="note">Отсортировано по регистрациям на домен в сутки. Столбец «дней» —
  сколько прожила группа к 24.08 12:15. На группу приходится от 0 до 8 регистраций,
  поэтому порядок внутри верхней половины — шум.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Страниц</th>
  <th>Дом</th><th>Дней</th><th>С конв.</th><th>Рег</th><th>Деп</th>
  <th>Рег/дом/день</th><th>Т10</th><th>Рег/100 Т10</th></tr></thead><tbody>${gr}</tbody></table></div></div>

  <div class="blk"><h2>Конверсии приходят не с тех ключей, которые мы меряем</h2>
  <p class="note">Для каждой конверсии на домене из реестра взята лучшая позиция
  <b>этого бренда на этом домене</b> за всё наблюдение, по всем замерам, во всём
  диапазоне ТОП-1…100.</p>
  <div class="tw" style="max-width:520px"><table><thead><tr>
  <th class="l">Где стоял бренд</th><th>Конверсий</th><th>Доля</th></tr></thead>
  <tbody>${bk}</tbody></table></div>
  <p class="note" style="margin-top:10px">Две трети конверсий приходят с брендов,
  по которым домен <b>ни разу не попадал даже в сотню</b>. Из них
  <b>${B['бренда нет в ядре']}</b> — по брендам, которых вообще нет в ядре
  из 1571 ключа: <span class="num">${C.nob.map(x=>esc(x[0])+(x[1]>1?'×'+x[1]:'')).join(', ')}</span>.
  Ещё <b>${B['не ранжировался']}</b> — по брендам, которые в ядре есть, но
  домен по ним не ранжировался: <span class="num">${C.nor.slice(0,12).map(x=>esc(x[0])+(x[1]>1?'×'+x[1]:'')).join(', ')}</span>.
  И то и другое означает одно: трафик пришёл с запросов, которых ядро не покрывает.</p>
  <p class="note"><b>Что это значит для отчёта.</b> Всё, что меряется по ядру —
  Т10/дом, ВЧ+СЧ, ТОП-3 — описывает витрину, а не поток. Показательна
  <span class="num">Generation 50</span>: 43 ключа в ТОП-10 на 50 доменов,
  почти ноль по нашим меркам, и при этом 6 регистраций — 14 на 100 ключей,
  худшая видимость и лучшая отдача с неё во всём наборе.</p></div>

  <div class="blk"><h2>Домены из реестра с конверсиями</h2>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Зона</th><th class="l">Группа</th>
  <th>Рег</th><th>Деп</th><th>Т10</th><th>ТОП-3</th><th class="l">Бренды</th>
  </tr></thead><tbody>${kn}</tbody></table></div></div>

  <div class="blk"><h2>Домены прошлых запусков</h2>
  <p class="note">Контент этих доменов в реестре не заведён — сопоставить с конфигурацией нельзя.
  Здесь они как ориентир по отдаче.</p>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Зона</th><th>Рег</th><th>Деп</th>
  <th class="l">Бренды</th></tr></thead><tbody>${un}</tbody></table></div></div>

  <div class="blk"><h2>Бренды и зоны</h2>
  <div class="cards2">
    <div><h3 style="font-family:var(--cond);font-size:16px;margin-bottom:8px">Бренды</h3>
    <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Рег</th><th>Деп</th>
    </tr></thead><tbody>${bl}</tbody></table></div></div>
    <div><h3 style="font-family:var(--cond);font-size:16px;margin-bottom:8px">Зоны</h3>
    <div class="tw"><table><thead><tr><th class="l">Зона</th><th>Рег</th><th>Деп</th>
    </tr></thead><tbody>${zl}</tbody></table></div></div>
  </div></div>`;
}

const TABS=[["Обзор",tabOverview],["Все домены",tabAll],["Лидеры",tabLead],
  ["Зоны",tabZones],["Бренды и ключи",tabBrands],["Типы запросов",tabCats],["Конверсии",tabConv]];
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

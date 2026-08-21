const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), f2=(x)=>x.toFixed(2).replace('.',',');
const pc=(x)=>Math.round(x*100)+'%';
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':(v>=1e3?(v/1e3).toFixed(1).replace('.',',')+'k':Math.round(v)));
const O=D.order, GR=D.groups;
const pos=(p)=>`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;
function spark(s){const mx=Math.max(...s,0.01);
  return '<span class="spark" title="'+s.map(x=>f1(x)).join(' → ')+'">'+s.map((v,i)=>
    '<i class="'+(i===s.length-1?'hi':'')+'" style="height:'+Math.max(2,Math.round(v/mx*22))+'px"></i>').join('')+'</span>';}

function overview(){
  const row=(sn)=>{const g=GR[sn];
    return `<tr><td class="l id">${esc(g.name)}</td><td class="l">${esc(g.cfg)}</td>
      <td class="l mut">${g.labels[g.labels.length-1]}</td><td>${g.n}</td><td>${spark(g.ser)}</td>
      <td><b>${f1(g.t10)}</b></td><td>${g.med}</td><td>${f1(g.wo)}</td>
      <td class="${g.leadshare>=.6?'warn':''}">${pc(g.leadshare)}</td>
      <td class="l mut num">${g.serhs.join(' → ')}</td>
      <td class="${g.vch+g.sch?'good':'mut'}"><b>${g.vch+g.sch}</b></td>
      <td>${g.t3}</td><td>${g.brands}</td>
      <td class="${g.z100?'bad':'mut'}">${g.z100}</td></tr>`;};
  return `<div class="blk"><h2>Все 13 групп на последнем замере</h2>
  <p class="note">Т10/дом, медиана и «без лидера» — по .team-подмножеству. «Доля лидера» —
  какую часть всех ключей группы держит её лучший домен: выше 60 % означает, что результат
  группы это результат одного сайта. Столбик — траектория по замерам.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Конфигурация</th>
  <th class="l">Последний замер</th><th>Дом</th><th>Т10 динамика</th><th>Т10/дом</th>
  <th>Медиана</th><th>Без лидера</th><th>Доля лидера</th><th>ВЧ+СЧ динамика</th><th>ВЧ+СЧ</th>
  <th>ТОП-3</th><th>Брендов</th><th>Нет в Т100</th></tr></thead><tbody>${O.map(row).join('')}</tbody></table></div></div>

  <div class="blk"><h2>Пришла вторая волна: дорогие бренды</h2>
  <p class="note">На замере 12:06 у трёх групп сразу общий охват в ТОП-10 <b>упал</b>,
  а число ВЧ и СЧ ключей <b>выросло</b>. Это ровно тот архивный паттерн — дорогие бренды
  приходят второй волной, вытесняя НЧ.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Т10/дом</th>
  <th class="l">ВЧ+СЧ в ТОП-10</th></tr></thead><tbody>
    <tr><td class="l id">nabor28gotovyi · наборы</td>
      <td class="l num">13,4 → <b class="bad">9,4</b></td>
      <td class="l num">2 → <b class="good">12</b></td></tr>
    <tr><td class="l id">12pages_withdate · Theme2</td>
      <td class="l num">11,7 → <b class="bad">8,6</b></td>
      <td class="l num">13 → <b class="good">14</b></td></tr>
    <tr><td class="l id">Generation 50</td>
      <td class="l num">0,7 → <b class="good">1,3</b></td>
      <td class="l num">2 → <b class="good">11</b></td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px"><b>Практический вывод: на этой стадии общий счёт
  ТОП-10 — плохая метрика.</b> Падение охвата при росте дорогих ключей означает,
  что группа не слабеет, а переходит на более ценные запросы. Смотреть ВЧ+СЧ.</p></div>

  <div class="blk"><h2>Остальное за сутки</h2>
  <div class="cards">
    <div class="card ok"><h3>Generator_11page держит первое место</h3>
      <p>60 ключей на домен, 44 ВЧ+СЧ, 56 в ТОП-3. Работают все пять доменов,
      доля лидера 34 %.</p>
      <p class="mut">Последний съём 20.08 22:29 — новее по этой группе нет.</p></div>
    <div class="card ok"><h3>Наборы: из полного нуля в рабочую группу</h3>
      <p>0 → 1,2 → 13,4 → 9,4 по охвату и 0 → 0 → 2 → <span class="big">12</span>
      по дорогим ключам.</p>
      <p>Вечером 20-го у всех пяти доменов был ноль по ТОП-100. Архивный прецедент
      «наборы слабые» не подтвердился.</p></div>
    <div class="card err"><h3>Данные неполные по Theme1</h3>
      <p>У 12pages_withdate · Theme1 замера 12:06 <b>нет</b> — последний 02:00.
      Сравнивать его с Theme2 напрямую сейчас нельзя, только на одинаковом
      номере замера.</p></div>
  </div></div>

  <div class="blk"><h2>Главное предупреждение: смотрите «без лидера», а не среднее</h2>
  <p class="note">Доля лидера показывает, насколько результат группы — это результат одного
  домена. Порядок групп по среднему и по устойчивой мере расходится.</p>
  <div class="tw"><table><thead><tr><th class="l">Группа</th>
  <th class="l">Значения по доменам (.team)</th><th>Среднее</th><th>Медиана</th>
  <th>Без лидера</th><th>Доля лидера</th></tr></thead><tbody>
    <tr><td class="l id">Generator_11page</td><td class="l num">102, 85, 61, 28, 24</td>
      <td>60,0</td><td>61</td><td class="good"><b>49,5</b></td><td class="good">34 %</td></tr>
    <tr><td class="l id">12pages_withdate · Theme1</td><td class="l num">130, 13, 10, 9, 3, 1, 1</td>
      <td>23,9</td><td>9</td><td>6,2</td><td class="bad"><b>78 %</b></td></tr>
    <tr><td class="l id">7page_yandex</td><td class="l num">64, 36, 8, 4, 1, 0</td>
      <td>18,8</td><td>6</td><td>9,8</td><td class="warn">57 %</td></tr>
    <tr><td class="l id">nabor28gotovyi · наборы</td><td class="l num">21, 18, 11, 9, 8</td>
      <td>13,4</td><td>11</td><td class="good"><b>11,5</b></td><td class="good">31 %</td></tr>
    <tr><td class="l id">12pages_withdate · Theme2</td><td class="l num">32, 23, 9, 8, 7, 2, 1</td>
      <td>11,7</td><td>8</td><td class="good">8,3</td><td class="good">39 %</td></tr>
    <tr><td class="l id">12pages_nodate</td><td class="l num">27, 9, 6, 5, 3</td>
      <td>10,0</td><td>6</td><td>5,8</td><td class="warn">54 %</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">По среднему 12pages_withdate · Theme1 идёт вторым,
  по «без лидера» — <b>пятым</b>. Все 27 его ВЧ-ключей сидят в одном домене
  <span class="num">1908.team</span>, который держит 130 из 167 ключей группы.
  Наборы и Theme2 при вдвое меньшем среднем дают вдвое больше на типичный домен.</p></div>`;
}

function wave(w,title,note,extra){
  let h=`<div class="blk"><h2>${title}</h2><p class="note">${note}</p></div>`;
  O.filter(sn=>GR[sn].wave===w).forEach(sn=>{const g=GR[sn];
    h+=`<div class="blk"><h2>${esc(g.name)}</h2>
      <p class="note">${esc(g.cfg)} · ${g.n} доменов · замеры ${g.labels.join(', ')}</p>
      <div class="tiles">
        <div class="tile a"><div class="k">Т10 на домен</div><div class="v">${f1(g.t10)}</div>
          <div class="c">по .team, n=${g.ntm}</div></div>
        <div class="tile"><div class="k">Медиана</div><div class="v">${g.med}</div>
          <div class="c">без лидера ${f1(g.wo)}</div></div>
        <div class="tile ${g.vch+g.sch?'g':'b'}"><div class="k">ВЧ+СЧ в ТОП-10</div>
          <div class="v">${g.vch+g.sch}</div><div class="c">${g.vch} ВЧ · ${g.sch} СЧ</div></div>
        <div class="tile ${g.t3?'g':''}"><div class="k">ТОП-3</div><div class="v">${g.t3}</div>
          <div class="c">${g.brands} брендов, ${g.hb} дорогих</div></div>
        <div class="tile ${g.leadshare>=.6?'b':''}"><div class="k">Доля лидера</div>
          <div class="v">${pc(g.leadshare)}</div><div class="c">ключей у лучшего домена</div></div>
        <div class="tile ${g.z100?'b':''}"><div class="k">Нет в Т100</div>
          <div class="v">${g.z100}/${g.n}</div><div class="c">было ${g.z100a} на первом замере</div></div>
      </div>
      <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Динамика Т10</th>
      <th>Т10</th><th>Т30</th><th>Т100</th><th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>НЧ</th>
      <th>Брендов</th></tr></thead><tbody>`+
      g.doms.map((d,i)=>`<tr class="clk" data-g="${sn}" data-i="${i}">
        <td class="l ${d.d.endsWith('.team')?'id':'mut'}">${esc(d.d)}</td>
        <td class="l mut num">${d.tr.join(' → ')}</td>
        <td><b>${d.t10}</b></td><td>${d.t30}</td>
        <td class="${d.t100===0?'bad':''}">${d.t100}</td>
        <td class="${d.t3?'good':'mut'}">${d.t3}</td>
        <td class="${d.vch?'good':'mut'}">${d.vch}</td>
        <td class="${d.sch?'good':'mut'}">${d.sch}</td>
        <td class="mut">${d.nch}</td><td>${d.brands.length}</td></tr>
        <tr class="det" hidden><td colspan="10"><div class="inner"></div></td></tr>`).join('')+
      `</tbody></table></div></div>`;});
  return h+(extra||'');
}

const DAY_EXTRA=`
  <div class="blk"><h2>Рассинхрон замеров</h2>
  <p class="note">У 12pages_withdate · Theme1 нет съёма 12:06 — последний 02:00.
  У остальных дневных групп по четыре замера. Поэтому все сравнения ниже сделаны
  <b>на одинаковом номере замера</b> (третьем), а не на последнем.</p></div>

  <div class="blk"><h2>Даты: эффекта нет</h2>
  <div class="tw"><table><thead><tr><th class="l">Сторона</th><th>n</th>
  <th class="l">Т10/дом по замерам</th><th class="l">ВЧ+СЧ по замерам</th>
  <th>Медиана з3</th><th>Без лидера з3</th></tr></thead><tbody>
    <tr><td class="l id">12 стр с датами · Theme1</td><td>7</td>
      <td class="l num">8,3 → 21,0 → 23,9</td><td class="l num">8 → 23 → 34</td>
      <td>9</td><td>6,2</td></tr>
    <tr><td class="l id">12 стр с датами · Theme2</td><td>7</td>
      <td class="l num">4,4 → 8,1 → 11,7 → 8,6</td><td class="l num">6 → 3 → 13 → 14</td>
      <td>8</td><td class="good"><b>8,3</b></td></tr>
    <tr><td class="l id">12 стр без дат · Theme1</td><td>5</td>
      <td class="l num">3,6 → 12,6 → 10,0 → 15,0</td><td class="l num">0 → 1 → 3 → 4</td>
      <td>6</td><td>5,8</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">На третьем замере «без лидера»: с датами 6,2 и 8,3,
  без дат 5,8. Разброс <b>между двумя половинами одной партии с датами</b> больше,
  чем разница между «с датами» и «без дат». По дорогим ключам с датами впереди
  (34 и 14 против 4), но у Theme1 все они в одном домене. <b>Эффекта дат нет</b>,
  разница между доменами перекрывает разницу между форматами.</p></div>

  <div class="blk"><h2>Шаблон: на третьем замере Theme2 ровнее</h2>
  <div class="tw"><table><thead><tr><th class="l">Сторона</th><th>n</th>
  <th class="l">Значения по доменам (замер 3)</th><th>Среднее</th><th>Медиана</th>
  <th>Без лидера</th><th>Доля лидера</th><th>ВЧ+СЧ</th></tr></thead><tbody>
    <tr><td class="l id">Theme1</td><td>7</td><td class="l num">130, 13, 10, 9, 3, 1, 1</td>
      <td>23,9</td><td class="good">9</td><td>6,2</td><td class="bad">78 %</td>
      <td class="good">34</td></tr>
    <tr><td class="l id">Theme2</td><td>7</td><td class="l num">32, 23, 9, 8, 7, 2, 1</td>
      <td>11,7</td><td>8</td><td class="good"><b>8,3</b></td><td class="good">39 %</td>
      <td>13</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Среднее у Theme1 вдвое выше, но
  <span class="num">1908.team</span> держит 130 из 167 ключей группы и все её ВЧ.
  На типичный домен Theme2 даёт больше и распределён вдвое ровнее.
  <b>На семи доменах на сторону шаблон не измеряется</b> — но перевес Theme1
  целиком на одном сайте.</p></div>

  <div class="blk"><h2>Наборы: вторая волна в чистом виде</h2>
  <div class="tw"><table><thead><tr><th class="l">Домен</th><th class="l">Т10 по замерам</th>
  <th>ВЧ</th><th>СЧ</th><th>ТОП-3</th><th>Т30</th><th>Брендов</th></tr></thead><tbody>
    <tr><td class="l id">g2k.team</td><td class="l num">0 → 1 → 18 → 16</td>
      <td class="good">2</td><td>0</td><td class="good">5</td><td>37</td><td>9</td></tr>
    <tr><td class="l id">1596.team</td><td class="l num">0 → 2 → 9 → 10</td>
      <td class="good">2</td><td class="good">1</td><td class="good">3</td><td>29</td><td>5</td></tr>
    <tr><td class="l id">h5r.team</td><td class="l num">0 → 1 → 8 → 9</td>
      <td class="good">3</td><td class="good">1</td><td>0</td><td>18</td><td>7</td></tr>
    <tr><td class="l id">1739.team</td><td class="l num">0 → 0 → 11 → 7</td>
      <td class="good">1</td><td class="good">2</td><td>1</td><td>15</td><td>6</td></tr>
    <tr><td class="l id">f7n.team</td><td class="l num">0 → 2 → 21 → 5</td>
      <td>0</td><td>0</td><td>1</td><td>8</td><td>5</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">Общий охват просел с 13,4 до 9,4, но дорогих ключей
  стало <b>вдвое-вшестеро больше</b>: с 2 до 12. Четыре домена из пяти взяли ВЧ или СЧ.
  Это не ослабление группы, а переход на более ценные запросы.</p></div>

  <div class="blk"><h2>Индексация: как это выглядело</h2>
  <div class="tw"><table><thead><tr><th class="l">Группа</th><th class="l">Т10 по замерам</th>
  <th class="l">ВЧ+СЧ по замерам</th></tr></thead><tbody>
    <tr><td class="l id">nabor28gotovyi</td><td class="l num">0 → 1,2 → 13,4 → 9,4</td>
      <td class="l num">0 → 0 → 2 → <b class="good">12</b></td></tr>
    <tr><td class="l id">kostoreznaya1</td><td class="l num">0,2 → 1,4 → 2,8 → 1,2</td>
      <td class="l num">0 → 0 → 1 → 1</td></tr>
  </tbody></table></div>
  <p class="note" style="margin-top:10px">В 17:34 у наборов было пять доменов из пяти
  с нулём по всему ТОП-100, и обычное правило отсева велело бы их списать. Сутки спустя
  это рабочая группа с 12 дорогими ключами. <b>Ноль в ТОП-100 по всему ядру означает,
  что сайт не в индексе, а не что контент не работает.</b> Имена так и не поднялись —
  им стоит дать ещё сутки.</p></div>`;

const GEN_EXTRA=`
  <div class="blk"><h2>Пошла: дорогие ключи появились</h2>
  <div class="cards">
    <div class="card ok"><h3>ВЧ+СЧ выросли в пять раз</h3>
      <p>0 → 2 → <span class="big">11</span> за три замера. Плюс 18 ключей в ТОП-3.</p>
      <p>Индексация практически завершена: доменов без ключей в ТОП-100
      было 20 из 50, стало 3.</p></div>
    <div class="card"><h3>Но охват пока низкий</h3>
      <p>21 домен из 50 имеет хоть один ключ в ТОП-10, среднее 1,3, медиана 0.
      Лидеры: 3961.team — 13 ключей и 7 в ТОП-3, xdkr.team — 11, 6158.team — 9 и 4 ВЧ.</p>
      <p class="mut">Наборы прошли путь 0 → 1,2 → 13,4 за девять часов, так что
      следующие замеры решающие.</p></div>
    <div class="card acc"><h3>Чем ценна</h3>
      <p>50 доменов в одной зоне — самая большая партия наблюдений. Доля лидера 11 %,
      то есть результат уже сейчас не зависит от одного сайта, в отличие от всех
      остальных групп.</p>
      <p><b>Контенты и привязку по-прежнему не присылали</b> — без них группа покажет
      уровень партии, но не скажет, какой формат сработал.</p></div>
  </div></div>`;

function tabBrands(){
  const B=D.brands, hi=B.filter(b=>b.t!=='НЧ');
  const rows=B.slice(0,120).map((b,i)=>`<tr class="clk" data-b="${i}">
    <td class="l ${b.t!=='НЧ'?'id':''}">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
    <td><b>${b.n}</b></td><td>${pos(b.best)}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td>
    <td>${b.nd}</td><td class="l mut">${b.groups.slice(0,3).join(', ')}${b.groups.length>3?' +'+(b.groups.length-3):''}</td>
    <td class="l mut">${Object.entries(b.cats).sort((x,y)=>y[1]-x[1]).slice(0,3).map(([k,v])=>k+' ×'+v).join(', ')}</td>
  </tr><tr class="det" hidden><td colspan="9"><div class="inner"></div></td></tr>`).join('');
  return `<div class="blk"><h2>Какие ключи взял каждый бренд</h2>
  <p class="note">Все ${D.tot.t10} ключей в ТОП-10 на последнем замере каждой группы.
  Клик по строке — конкретные запросы с позициями, доменами и группами.
  Показаны первые 120 брендов из ${B.length}.</p>
  <div class="tiles">
    <div class="tile"><div class="k">Брендов</div><div class="v">${B.length}</div>
      <div class="c">из 157 в справочнике</div></div>
    <div class="tile a"><div class="k">Ключей в ТОП-10</div><div class="v">${D.tot.t10}</div>
      <div class="c">по ${D.tot.doms} доменам</div></div>
    <div class="tile g"><div class="k">В ТОП-3</div><div class="v">${D.tot.t3}</div>
      <div class="c">${pc(D.tot.t3/D.tot.t10)} от ТОП-10</div></div>
    <div class="tile"><div class="k">Дорогих брендов</div><div class="v">${hi.length}</div>
      <div class="c">ВЧ и СЧ, ${hi.reduce((a,b)=>a+b.n,0)} ключей</div></div>
  </div>
  <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th>
  <th>Ключей</th><th>Лучшая</th><th>ТОП-3</th><th>Доменов</th><th class="l">Группы</th>
  <th class="l">Типы запросов</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

function tabCats(){
  const C=D.cats, tot=D.tot.t10;
  const rows=C.map((c,i)=>`<tr class="clk" data-c="${i}">
    <td class="l ${c.t10>50?'id':''}">${esc(c.c)}</td><td><b>${c.t10}</b></td>
    <td>${pc(c.t10/tot)}</td><td class="${c.t3?'good':'mut'}">${c.t3}</td>
  </tr><tr class="det" hidden><td colspan="4"><div class="inner"></div></td></tr>`).join('');
  const top=C[0], bare=C.find(x=>x.c==='бренд без добавок')||{t10:0};
  return `<div class="blk"><h2>Что за запросы заходят</h2>
  <p class="note">Каждый ключ отнесён к одному типу по первому совпавшему признаку:
  зеркало → вход → регистрация → офиц. сайт → бонус → играть → приложение → отзывы →
  «бренд + казино» → «бренд без добавок». Клик по строке — примеры.</p>
  <div class="tw"><table><thead><tr><th class="l">Тип запроса</th><th>В ТОП-10</th>
  <th>Доля</th><th>ТОП-3</th></tr></thead><tbody>${rows}</tbody></table></div>
  <p class="note" style="margin-top:10px">Картина та же, что была на 40 доменах:
  «${esc(top.c)}» держит ${pc(top.t10/tot)} всего ТОП-10, а голое название бренда —
  ${pc(bare.t10/tot)}. Выдачу по самому бренду держит сам бренд.</p></div>`;
}

function fill(){
  document.querySelectorAll('tr.clk[data-g]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1;
    const d=GR[tr.dataset.g].doms[+tr.dataset.i];
    if(!d.keys.length){slot.innerHTML='<h4>Ни одного ключа в ТОП-10</h4>';return;}
    slot.innerHTML=`<div><h4>Бренды в ТОП-10 — ${d.brands.length}</h4><div class="tw"><table>
      <thead><tr><th class="l">Бренд</th><th>Объём</th><th>Тир</th><th>Лучшая</th><th>Ключей</th>
      <th>ТОП-3</th></tr></thead><tbody>`+
      d.brands.map(b=>`<tr><td class="l">${esc(b.b)}</td><td>${kf(b.v)}</td><td>${tg(b.t)}</td>
        <td>${pos(b.best)}</td><td>${b.n}</td><td class="${b.t3?'good':'mut'}">${b.t3}</td></tr>`).join('')+
      `</tbody></table></div></div>
      <div><h4>Ключи в ТОП-10 — ${d.keys.length}</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th class="l">Тип</th><th>Тир</th>
      <th>Объём</th><th>Поз.</th></tr></thead><tbody>`+
      d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
        <td class="l mut">${esc(k.c)}</td><td>${tg(k.t)}</td><td>${kf(k.v)}</td>
        <td>${pos(k.p)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
  document.querySelectorAll('tr.clk[data-b]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1;
    const b=D.brands[+tr.dataset.b];
    slot.innerHTML=`<div><h4>${esc(b.b)} — ${b.keys.length} ключей в ТОП-10</h4>
      <div class="tw"><table><thead><tr><th class="l">Ключ</th><th class="l">Тип</th>
      <th>Поз.</th><th class="l">Домен</th><th class="l">Группа</th></tr></thead><tbody>`+
      b.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.c)}</td>
        <td>${pos(k.p)}</td><td class="l num">${esc(k.d)}</td>
        <td class="l mut">${esc(k.g)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
  document.querySelectorAll('tr.clk[data-c]').forEach(tr=>{tr.onclick=()=>{
    const det=tr.nextElementSibling; det.hidden=!det.hidden;
    const slot=det.querySelector('.inner'); if(det.hidden||slot.dataset.done) return;
    slot.dataset.done=1;
    const c=D.cats[+tr.dataset.c];
    slot.innerHTML=`<div><h4>Примеры — «${esc(c.c)}»</h4><div class="tw"><table><thead><tr>
      <th class="l">Ключ</th><th class="l">Бренд</th><th>Позиция</th></tr></thead><tbody>`+
      c.ex.map(e=>`<tr><td class="l">${esc(e.q)}</td><td class="l mut">${esc(e.b)}</td>
        <td>${pos(e.p)}</td></tr>`).join('')+`</tbody></table></div></div>`;};});
}

const TABS=[
  ["Обзор",overview],
  ["Ночные · 3 замера",()=>wave("ночь","Ночной запуск · 01:21–01:31",
     "Три замера: 01:29–01:41, 10:08–10:09 и 22:29–22:30. Клик по домену — бренды и ключи.")],
  ["Дневные · 4 замера",()=>wave("день","Дневной запуск · 17:21–17:22",
     "До четырёх замеров: 17:34–17:35, 22:29, 21.08 02:00 и 21.08 12:06. У Theme1 последнего съёма нет. Клик по домену — бренды и ключи.",DAY_EXTRA)],
  ["Generation 50",()=>wave("вечер","Generation 50 · запуск 22:06",
     "Три замера: 22:29, 21.08 02:00 и 21.08 12:06.",GEN_EXTRA)],
  ["Бренды и ключи",tabBrands],
  ["Типы запросов",tabCats]];
const nav=document.getElementById('nav'), main=document.getElementById('main');
TABS.forEach(([name],i)=>{
  const b=document.createElement('button');
  b.textContent=name; b.setAttribute('role','tab'); b.setAttribute('aria-selected',i===0);
  b.onclick=()=>show(i); nav.appendChild(b);
  const s=document.createElement('section'); s.hidden=i!==0; main.appendChild(s);});
function show(i){
  [...nav.children].forEach((b,j)=>b.setAttribute('aria-selected',i===j));
  [...main.children].forEach((s,j)=>{s.hidden=i!==j;
    if(i===j&&!s.dataset.done){s.dataset.done=1;s.innerHTML=TABS[j][1]();fill();}});
  window.scrollTo({top:0,behavior:'instant'});}
main.insertAdjacentHTML('beforeend','<div class="foot">20.08.2026 · '+D.tot.groups+
  ' групп, '+D.tot.doms+' доменов · замеры 01:29–01:41, 10:08–10:09, 17:34–17:35 и 22:29–22:30 · '+
  'всё считано по ТОП-10 · ядро 1570 ключей, ВЧ ≥ 1 млн, СЧ 700k–1 млн, '+
  'бренды vovan и pari исключены</div>');
show(0);

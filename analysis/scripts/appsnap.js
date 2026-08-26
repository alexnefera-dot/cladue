const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), f2=(x)=>x.toFixed(2).replace('.',',');
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':Math.round(v));
const pos=(p)=>`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;
const zn=(z)=>`<span class="zone ${z==='.team'?'zt':''}">${esc(z)}</span>`;
const dl=(a,b)=>{const d=b-a; return d>0?`<span class="good">+${f1(d)}</span>`:(d<0?`<span class="bad">${f1(d)}</span>`:'<span class="mut">0</span>');};


const ratio=(x,y)=>y>0?(x/y>=1?f1(x/y)+'×':'0,'+Math.round(100*x/y)+'×'):'—';
function cmpRow(nm,A,B,an,bn,int){
  const w = A>B?'a':(B>A?'b':'');
  const fm=(x)=>int?String(Math.round(x)):f2(x);
  let note;
  if(A===B) note='<span class="mut">поровну</span>';
  else if(Math.min(A,B)===0) note=`<span class="mut">только у</span> «${esc(A>B?an:bn)}»`;
  else note=`${A>B?ratio(A,B):ratio(B,A)} <span class="mut">за</span> «${esc(A>B?an:bn)}»`;
  return `<tr><td class="l mut">${nm}</td>
    <td class="num ${w==='a'?'good':''}"><b>${fm(A)}</b></td>
    <td class="num ${w==='b'?'good':''}"><b>${fm(B)}</b></td>
    <td class="num">${note}</td></tr>`;
}
function pairBlock(p){
  const an=p.a.split('· ')[1], bn=p.b.split('· ')[1];
  const s1=p.s1, sl=p.sl;
  const w1m=s1.a.mean>s1.b.mean?an:bn, w1w=s1.a.wo>s1.b.wo?an:bn;
  const w2m=sl.a2.mean>sl.b2.mean?an:bn, w2w=sl.a2.wo>sl.b2.wo?an:bn;
  const agree1=w1m===w1w, agree2=w2m===w2w, same=w1m===w2m&&w1w===w2w&&agree1&&agree2;
  return `<div class="verd">
    <h3>${esc(p.title)}</h3>
    <p class="note">${esc(p.note)}</p>
    <div class="two2">
      <div class="vcol">
        <div class="vh">Съём 1 — <b>${esc(p.s1.a.n?'':'')}${esc(D.g.find(g=>g.name===p.a).labs[0])}</b>
          <span class="ok2">полное ядро</span></div>
        <div class="tw"><table><thead><tr><th class="l">Метрика</th>
          <th>${esc(an)}</th><th>${esc(bn)}</th><th class="l">Перевес</th></tr></thead><tbody>
          ${cmpRow('Т10/дом с лидером',s1.a.mean,s1.b.mean,an,bn)}
          ${cmpRow('Т10/дом без лидера',s1.a.wo,s1.b.wo,an,bn)}
          ${cmpRow('Медиана',s1.a.med,s1.b.med,an,bn)}
          ${cmpRow('ТОП-3',s1.a.t3,s1.b.t3,an,bn,1)}
          ${cmpRow('ВЧ + СЧ',s1.a.vch+s1.a.sch,s1.b.vch+s1.b.sch,an,bn,1)}
        </tbody></table></div>
        <p class="vsum ${agree1?'ok':'warnv'}">${agree1
          ? `Обе меры за <b>«${esc(w1m)}»</b>.`
          : `Меры расходятся: среднее за <b>«${esc(w1m)}»</b>, без лидера за <b>«${esc(w1w)}»</b>.`}</p>
      </div>
      <div class="vcol">
        <div class="vh">Съём 2 — <b>${esc(D.g.find(g=>g.name===p.a).labs[1])}</b>
          <span class="ok2">полное ядро</span></div>
        <div class="tw"><table><thead><tr><th class="l">Метрика</th>
          <th>${esc(an)}</th><th>${esc(bn)}</th><th class="l">Перевес</th></tr></thead><tbody>
          ${cmpRow('Т10/дом с лидером',sl.a2.mean,sl.b2.mean,an,bn)}
          ${cmpRow('Т10/дом без лидера',sl.a2.wo,sl.b2.wo,an,bn)}
          ${cmpRow('Медиана',sl.a2.med,sl.b2.med,an,bn)}
          ${cmpRow('ТОП-3',sl.a2.t3,sl.b2.t3,an,bn,1)}
          ${cmpRow('ВЧ + СЧ',sl.a2.vch+sl.a2.sch,sl.b2.vch+sl.b2.sch,an,bn,1)}
        </tbody></table></div>
        <p class="vsum ${agree2?'ok':'warnv'}">${agree2
          ? `Обе меры за <b>«${esc(w2m)}»</b>.`
          : `Меры расходятся: среднее за <b>«${esc(w2m)}»</b>, без лидера за <b>«${esc(w2w)}»</b>.`}</p>
      </div>
    </div>
    <p class="vfin ${same?'ok':'bad2'}">${same
      ? `<b>Оба съёма согласны:</b> «${esc(w2m)}» впереди и по среднему, и без лидера.`
      : `<b>Съёмы не согласны.</b> На первом впереди «${esc(w1m)}», на втором «${esc(w2m)}». Вывода нет.`}
      <span class="mut"> Динамика на срезе: «${esc(an)}» ${f2(sl.a1.mean)} → ${f2(sl.a2.mean)}
      (без лидера ${f2(sl.a1.wo)} → ${f2(sl.a2.wo)}), «${esc(bn)}» ${f2(sl.b1.mean)} → ${f2(sl.b2.mean)}
      (без лидера ${f2(sl.b1.wo)} → ${f2(sl.b2.wo)}).</span></p>
  </div>`;
}

const metrics=(a)=>`<div class="tw"><table class="mt"><tbody>
  <tr><td class="l">Т10/дом <b>с лидером</b></td><td class="num big">${f2(a.mean)}</td></tr>
  <tr><td class="l">Т10/дом <b>без лидера</b></td><td class="num big">${f2(a.wo)}</td></tr>
  <tr><td class="l">Медиана</td><td class="num">${f1(a.med)}</td></tr>
  <tr><td class="l">Значения по доменам</td><td class="num l">${a.vals.join(', ')}</td></tr>
  <tr><td class="l">ТОП-3</td><td class="num">${a.t3}</td></tr>
  <tr><td class="l">Т30 / Т100</td><td class="num">${a.t30} / ${a.t100}</td></tr>
  <tr><td class="l">ВЧ / СЧ</td><td class="num ${a.vch+a.sch?'good':'mut'}">${a.vch} / ${a.sch}</td></tr>
</tbody></table></div>`;

function snapBlock(g,s,i){
  const trunc = false;
  return `<div class="snap${trunc?' tr':''}">
    <div class="sh"><span class="lab">Снимок ${esc(s.lab)}</span>
      ${trunc?`<span class="warn2">обрезан — ${Math.round(100*g.cov/g.core)}% ядра (${g.cov} из ${g.core})</span>`
             :`<span class="ok2">полный</span>`}</div>
    <div class="two">
      <div>${metrics(s.agg)}</div>
      <div>
        <h4>Бренды в ТОП-10 — ${s.nbrands}</h4>
        <p class="chips">${s.brands.map(([b,n])=>`<span class="chip">${esc(b)}<i>${n}</i></span>`).join('')}</p>
        ${s.hi.length?`<h4>Дорогие ключи — ${s.nhi}</h4>
        <div class="tw"><table><thead><tr><th class="l">Бренд</th><th>Тир</th><th>Объём</th>
          <th>Лучшая</th><th class="l">Где</th><th>Ключей</th></tr></thead><tbody>
          ${s.hi.map(h=>`<tr><td class="l id">${esc(h.b)}</td><td>${tg(h.t)}</td>
            <td class="mut">${kf(h.v)}</td><td>${pos(h.best)}</td>
            <td class="l num mut">${esc(h.dom)}</td><td>${h.n}</td></tr>`).join('')}
        </tbody></table></div>`:'<h4 class="mut">Дорогих ключей нет</h4>'}
      </div>
    </div>
    <h4>Домены</h4>
    <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Зона</th><th>Т10</th><th>Т30</th>
      <th>Т100</th><th>ТОП-3</th><th>ВЧ</th><th>СЧ</th><th>Брендов</th>
      <th class="l">Бренды в ТОП-10</th></tr></thead><tbody>
      ${s.doms.map(d=>`<tr class="${d.excl?'ex':''}"><td class="l id">${esc(d.d)}${d.excl?'<span class="mut"> · исключён</span>':''}</td>
        <td>${zn(d.zone)}</td><td><b>${d.t10}</b></td><td>${d.t30}</td>
        <td class="${d.t100?'':'bad'}">${d.t100}</td>
        <td class="${d.t3?'good':'mut'}">${d.t3}</td>
        <td class="${d.vch?'good':'mut'}">${d.vch}</td><td class="${d.sch?'good':'mut'}">${d.sch}</td>
        <td class="mut">${d.nb}</td>
        <td class="l mut">${d.brands.map(esc).join(', ')||'—'}</td></tr>`).join('')}
    </tbody></table></div>
    ${s.doms.filter(d=>d.keys.length&&!d.excl).slice(0,3).map(d=>`
      <h4>${esc(d.d)} — верхние ключи</h4>
      <div class="tw"><table><thead><tr><th class="l">Ключ</th><th class="l">Бренд</th>
        <th>Тир</th><th>Позиция</th></tr></thead><tbody>
        ${d.keys.map(k=>`<tr><td class="l">${esc(k.q)}</td><td class="l mut">${esc(k.b)}</td>
          <td>${tg(k.t)}</td><td>${pos(k.p)}</td></tr>`).join('')}
      </tbody></table></div>`).join('')}
  </div>`;
}

function groupBlock(g,gi){
  const [a,b]=g.slice;
  return `<section class="blk" id="g${gi}">
    <h2>${esc(g.name)}</h2>
    <p class="note"><span class="sheetname">${esc(g.sheet)}</span> · ${esc(g.cfg)} ·
    ${g.ndom} доменов${g.nexcl?` (${g.nexcl} исключён)`:''} ·
    снимки <b>${g.labs.map(esc).join('</b> и <b>')}</b></p>
    ${g.snaps.map((s,i)=>snapBlock(g,s,i)).join('')}
    <div class="cmp">
      <h3>Динамика между снимками</h3>
      <p class="note">Оба снимка полные, ядро одинаковое. Только .team.
      ${g.skipped.length?`Обрезанный снимок ${g.skipped.map(esc).join(', ')} пропущен.`:''}</p>
      <div class="tw"><table><thead><tr><th class="l">Метрика</th>
        <th>${esc(g.labs[0])}</th><th>${esc(g.labs[1])}</th><th>Δ</th></tr></thead><tbody>
        <tr><td class="l">Т10 на домен</td><td class="num"><b>${f2(a.mean)}</b></td>
          <td class="num"><b>${f2(b.mean)}</b></td><td>${dl(a.mean,b.mean)}</td></tr>
        <tr><td class="l">Медиана</td><td class="num">${f1(a.med)}</td>
          <td class="num">${f1(b.med)}</td><td>${dl(a.med,b.med)}</td></tr>
        <tr><td class="l">Без лидера</td><td class="num">${f2(a.wo)}</td>
          <td class="num">${f2(b.wo)}</td><td>${dl(a.wo,b.wo)}</td></tr>
        <tr><td class="l">ТОП-3</td><td class="num">${a.t3}</td><td class="num">${b.t3}</td>
          <td>${dl(a.t3,b.t3)}</td></tr>
        <tr><td class="l">Т30</td><td class="num">${a.t30}</td><td class="num">${b.t30}</td>
          <td>${dl(a.t30,b.t30)}</td></tr>
        <tr><td class="l">Т100</td><td class="num">${a.t100}</td><td class="num">${b.t100}</td>
          <td>${dl(a.t100,b.t100)}</td></tr>
        <tr><td class="l">ВЧ + СЧ</td><td class="num">${a.vch+a.sch}</td>
          <td class="num">${b.vch+b.sch}</td><td>${dl(a.vch+a.sch,b.vch+b.sch)}</td></tr>
        <tr><td class="l">Значения</td><td class="num l">${a.vals.join(', ')}</td>
          <td class="num l">${b.vals.join(', ')}</td><td class="mut">—</td></tr>
      </tbody></table></div>
      <h4>По доменам</h4>
      <div class="tw"><table><thead><tr><th class="l">Домен</th><th>Зона</th>
        <th>Т10 ${esc(g.labs[0])}</th><th>Т10 ${esc(g.labs[1])}</th><th>Δ</th>
        <th>Т30</th><th>Т30</th></tr></thead><tbody>
        ${g.sldoms.map(d=>`<tr><td class="l id">${esc(d.d)}</td><td>${zn(d.zone)}</td>
          <td>${d.a[0]}</td><td><b>${d.a[1]}</b></td><td>${dl(d.a[0],d.a[1])}</td>
          <td class="mut">${d.b[0]}</td><td class="mut">${d.b[1]}</td></tr>`).join('')}
      </tbody></table></div>
    </div>
  </section>`;
}
const C=D.ctrl;
const main=document.getElementById('main');
main.innerHTML=`<div class="blk"><h2>Как читать</h2>
  <p class="note">В выгрузке по три снимка на лист. Средний, от 26.08 11:14–11:15,
  <b>обрезан</b> — проверка не успела пройти, данные покрывали 60–70% ядра.
  Он пропущен. Показаны два <b>полных</b> снимка: 25.08 около 23:20 (возраст ~6 часов)
  и 26.08 около 12:30 (возраст ~19 часов).</p>
  <p class="note">Каждый тест показан двумя мерами. <b>С лидером</b> — обычное среднее,
  его тянет вверх один сильный домен. <b>Без лидера</b> — среднее по остальным,
  показывает типичный домен ветки. Все метрики по .team. Домены
  ${D.excl.map(x=>`<span class="num">${esc(x)}</span>`).join(' и ')} исключены.</p></div>`
  + `<div class="blk"><h2>Выводы по обоим съёмам</h2>
      <p class="note">Вывод считается устойчивым, только если обе меры и оба съёма
      указывают в одну сторону. Оба снимка полные, сравнение прямое.</p>
      ${D.pairs.map(pairBlock).join('')}
      <div class="verd">
        <h3>Контроль — просела ли выдача</h3>
        <p class="note">Контенты 21.08 на новых доменах: прогон генерации тот же, что
        у ветки, запущенной 22.08, двигается только дата запуска.</p>
        <div class="tw" style="max-width:640px"><table><thead><tr><th class="l">Метрика</th>
          <th>Съём 1 (полный)</th><th>Съём 2 (срез)</th></tr></thead><tbody>
          <tr><td class="l mut">Т10/дом с лидером</td><td class="num"><b>${f2(C.s1.mean)}</b></td>
            <td class="num"><b>${f2(C.sl2.mean)}</b></td></tr>
          <tr><td class="l mut">Т10/дом без лидера</td><td class="num"><b>${f2(C.s1.wo)}</b></td>
            <td class="num"><b>${f2(C.sl2.wo)}</b></td></tr>
          <tr><td class="l mut">ТОП-3</td><td class="num">${C.s1.t3}</td><td class="num">${C.sl2.t3}</td></tr>
          <tr><td class="l mut">ВЧ + СЧ</td><td class="num">${C.s1.vch+C.s1.sch}</td>
            <td class="num">${C.sl2.vch+C.sl2.sch}</td></tr>
        </tbody></table></div>
        <p class="vfin ok"><b>Выдача в порядке.</b> ${f2(C.s1.mean)} ключа на домен на шести часах
        при исторической вилке формата «12 стр + даты» <b>11,7…26,4</b> на девяти-десяти часах.
        Партии 24.08 на том же возрасте давали 0,0-1,3. На срезе группа ещё и растёт:
        ${f2(C.sl1.mean)} → ${f2(C.sl2.mean)} с лидером, ${f2(C.sl1.wo)} → ${f2(C.sl2.wo)} без лидера.</p>
      </div></div>`
  + D.g.map(groupBlock).join('');
document.getElementById('nav').innerHTML=D.g.map((g,i)=>
  `<a href="#g${i}">${esc(g.name)}</a>`).join('');

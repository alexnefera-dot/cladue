const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const f1=(x)=>x.toFixed(1).replace('.',','), f2=(x)=>x.toFixed(2).replace('.',',');
const kf=(v)=>v>=1e6?(v/1e6).toFixed(1).replace('.',',')+'M':(v>=1e4?Math.round(v/1e3)+'k':Math.round(v));
const pos=(p)=>`<span class="${p<=3?'good':p<=10?'':'mut'}"><b>${p}</b></span>`;
const tg=(t)=>`<span class="tag t-${t}">${t}</span>`;
const zn=(z)=>`<span class="zone ${z==='.team'?'zt':''}">${esc(z)}</span>`;
const dl=(a,b)=>{const d=b-a; return d>0?`<span class="good">+${f1(d)}</span>`:(d<0?`<span class="bad">${f1(d)}</span>`:'<span class="mut">0</span>');};

const metrics=(a)=>`<div class="tw"><table class="mt"><tbody>
  <tr><td class="l">Т10 на домен</td><td class="num big">${f2(a.mean)}</td></tr>
  <tr><td class="l">Медиана</td><td class="num">${f1(a.med)}</td></tr>
  <tr><td class="l">Без лидера</td><td class="num">${f2(a.wo)}</td></tr>
  <tr><td class="l">Значения по доменам</td><td class="num l">${a.vals.join(', ')}</td></tr>
  <tr><td class="l">ТОП-3</td><td class="num">${a.t3}</td></tr>
  <tr><td class="l">Т30 / Т100</td><td class="num">${a.t30} / ${a.t100}</td></tr>
  <tr><td class="l">ВЧ / СЧ</td><td class="num ${a.vch+a.sch?'good':'mut'}">${a.vch} / ${a.sch}</td></tr>
</tbody></table></div>`;

function snapBlock(g,s,i){
  const trunc = i>0 && g.cov<g.core;
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
    <p class="note">${esc(g.cfg)} · ${g.ndom} доменов${g.nexcl?` (${g.nexcl} исключён)`:''} ·
    снимки <b>${g.labs.map(esc).join('</b> и <b>')}</b></p>
    ${g.snaps.map((s,i)=>snapBlock(g,s,i)).join('')}
    <div class="cmp">
      <h3>Сравнение на общем срезе — первые ${g.cov} ключей</h3>
      <p class="note">Второй снимок покрывает ${Math.round(100*g.cov/g.core)}% ядра, поэтому
      оба снимка пересчитаны на одном наборе ключей. Только .team.</p>
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
      <h4>По доменам на срезе</h4>
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
const main=document.getElementById('main');
main.innerHTML=`<div class="blk"><h2>Как читать</h2>
  <p class="note">Каждый лист показан двумя снимками подряд, как в выгрузке.
  <b>Второй снимок обрезан</b> — проверка не успела пройти до конца, данные покрывают
  60–70% ядра, четвёртая четверть пуста на всех листах. Поэтому полные цифры второго
  снимка сравнивать с первым нельзя: внизу каждой группы есть блок
  «сравнение на общем срезе», где оба снимка пересчитаны на одинаковом наборе ключей.
  Все метрики — по .team. Домены ${D.excl.map(x=>`<span class="num">${esc(x)}</span>`).join(' и ')}
  исключены из расчётов.</p></div>`
  + D.g.map(groupBlock).join('');
document.getElementById('nav').innerHTML=D.g.map((g,i)=>
  `<a href="#g${i}">${esc(g.name)}</a>`).join('');

const esc=(s)=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const kf=(v)=>v==null?'—':(v>=1e6?(v/1e6).toFixed(1).replace('.',',')+' млн':Math.round(v/1e3)+' тыс.');
const cls=(p)=>p<=10?'hot':p<=30?'warn':'deep';
const pcls=(p)=>p<=10?'p-hot':p<=30?'p-warn':'p-deep';
const B=D.brands;
const hit=B.filter(b=>b.hits>0), empty=B.filter(b=>b.hits===0);

document.getElementById('facts').innerHTML=[
  ['2 940','проверок: 70 ключей × 42 домена',''],
  [String(D.hits),'позиций найдено',''],
  ['0','ключей в ТОП-10','q'],
  ['23','лучшая позиция во всём срезе',''],
  [String(D.withpos)+' / 42','доменов хоть с одной позицией',''],
  [String(empty.length)+' / 7','брендов без единой позиции','q'],
].map(([v,l,q])=>`<div class="fact"><div class="v ${q}">${v}</div><div class="l">${l}</div></div>`).join('');

const gauge=(p)=>`<div class="gauge"><div class="z10"></div><div class="z30"></div>
  <div class="pip ${cls(p)}" style="left:calc(${p}% - 1.5px)"></div></div>`;
const scale=`<div class="scale"><div class="dim" style="font-size:10.5px">ключ</div>
  <div class="dim" style="font-size:10.5px;text-align:right">поз.</div>
  <div class="marks"><span style="left:1%">1</span><span style="left:10%">10</span>
  <span style="left:30%">30</span><span style="left:60%">60</span>
  <span style="left:97%">100</span></div></div>`;

const domBlock=(d,i)=>`<div class="dgroup">
  <div class="dtitle"><span class="rank">${i===0?'★':'&nbsp;'}</span>
    <span class="dom">${esc(d.d)}</span>
    <span class="tag">${esc(d.grp)}</span>
    <span class="tag ${d.arm==='с картинками'?'img':''}">${esc(d.arm)}</span>
    <span class="mut" style="font-size:12.5px">лучшая <b class="num">${d.best}</b> · ключей ${d.n}</span>
  </div>
  ${d.keys.map(k=>`<div class="krow"><div class="kq">${esc(k.q)}</div>
    <div class="kp ${pcls(k.p)}">${k.p}</div>${gauge(k.p)}</div>`).join('')}
</div>`;

document.getElementById('main').innerHTML=`
<section>
  <h2>Сводка по брендам</h2>
  <p class="sub">Отсортировано по объёму рынка. Столбец «лучший сайт» — домен
  с наименьшей позицией; в скобках — сколько ключей бренда он держит.</p>
  <div class="tw"><table><thead><tr>
    <th class="l">Бренд</th><th>Кликов/мес</th><th>Ключей</th><th>Позиций</th>
    <th>Доменов</th><th class="l">Лучший сайт</th><th>Лучшая поз.</th>
  </tr></thead><tbody>
  ${B.map(b=>{const w=b.doms[0];
    return `<tr>
      <td class="l brand">${esc(b.b)}</td>
      <td class="num mut">${kf(b.vol)}</td>
      <td class="mut">${b.nk}</td>
      <td class="${b.hits?'':'zero'}"><b>${b.hits}</b></td>
      <td class="mut">${b.ndom}</td>
      <td class="l">${w?`<span class="dom">${esc(w.d)}</span>
        <span class="mut num" style="font-size:12px"> (${w.n})</span>`
        :'<span class="zero">никто</span>'}</td>
      <td class="num ${w?pcls(w.best):'zero'}"><b>${w?w.best:'—'}</b></td>
    </tr>`;}).join('')}
  </tbody></table></div>
  <div class="note" style="margin-top:16px"><b>Два самых дорогих бренда пустые.</b>
  По pinco (12,5 млн кликов/мес) и banda (2,8 млн) ни один из 42 доменов
  не попал даже в сотню. Позиции есть только у брендов помельче — и это ожидаемо:
  на дистанции в несколько часов дорогие запросы приходят последними.</div>
  <div class="note"><b>Ни одного ключа в ТОП-10.</b> Весь срез лежит в диапазоне 23–100,
  медиана 84. Шкала на карточках ниже показывает глубину: засечки стоят на 10 и 30,
  и почти все отметки — правее второй.</div>
</section>

${hit.map(b=>`<section>
  <div class="bcard">
    <div class="bhead">
      <span class="bname">${esc(b.b)}</span>
      <span class="bvol">${b.vol?kf(b.vol)+' кликов/мес':'нет в мастер-ядре, объём неизвестен'} · ${b.nk} ключей в наборе</span>
      <span class="bwin">лучший сайт<br><b>${esc(b.doms[0].d)}</b> · позиция <b>${b.doms[0].best}</b></span>
    </div>
    <div class="bbody">
      ${scale}
      ${b.doms.map(domBlock).join('')}
      ${b.dead.length?`<div class="deadkeys">
        <div class="lbl">без единой позиции — ${b.dead.length} из ${b.nk}</div>
        <div class="list">${b.dead.map(esc).join(' · ')}</div></div>`:''}
    </div>
  </div>
</section>`).join('')}

<section>
  <h2>Бренды без единой позиции</h2>
  <p class="sub">Ни один из 42 доменов не вернул позицию в пределах сотни.</p>
  ${empty.map(b=>`<div class="bcard empty" style="margin-bottom:12px">
    <div class="bhead"><span class="bname">${esc(b.b)}</span>
      <span class="bvol">${b.vol?kf(b.vol)+' кликов/мес':'объём неизвестен'} · ${b.nk} ключей</span>
      <span class="bwin zero">0 позиций из ${b.nk*42} проверок</span></div>
    <div class="bbody"><div class="deadkeys" style="margin-top:0;border-top:0;padding-top:8px">
      <div class="list">${b.allkeys.map(esc).join(' · ')}</div></div></div>
  </div>`).join('')}
</section>`;

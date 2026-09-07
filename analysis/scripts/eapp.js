const D=window.DATA;
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const dm=t=>t.slice(8,10)+'.'+t.slice(5,7)+' '+t.slice(11,16);
const TY={reg:['рега','good'],dep:['деп','gold']};

function cutBlock(c){
  const mx=Math.max(...c.rows.map(r=>r.r+r.d))||1;
  return `<div class="cut"><h3>${esc(c.label)}</h3>
  <table class="ct"><tbody>`+c.rows.map(r=>{
    const tot=r.r+r.d;
    return `<tr>
      <td class="l k" title="${esc(r.k)}">${esc(r.k)}</td>
      <td class="bar"><span class="bt"><span class="bf" style="width:${100*r.r/mx}%"></span>
        <span class="bf dep" style="width:${100*r.d/mx}%"></span></span></td>
      <td class="n">${r.r?`<b>${r.r}</b><span class="u"> рег</span>`:'<span class="mut">—</span>'}</td>
      <td class="n">${r.d?`<b class="gold">${r.d}</b><span class="u"> деп</span>`:''}</td>
      <td class="n mut">${r.n} дом.</td></tr>`;
  }).join('')+`</tbody></table></div>`;
}

document.getElementById('main').innerHTML=`
<div class="blk">
  <div class="tiles">
    <div class="tile"><div class="k">Строк в файле</div><div class="v">${D.n}</div>
      <div class="c">${D.skip.length} без нашего домена в адресе — отброшены</div></div>
    <div class="tile g"><div class="k">Регистраций</div><div class="v">${D.reg}</div>
      <div class="c">на ${D.doms} доменах</div></div>
    <div class="tile a"><div class="k">Депозитов</div><div class="v">${D.dep}</div>
      <div class="c">${D.days.map(d=>d.slice(8)+'.'+d.slice(5,7)).join(' · ')}</div></div>
  </div>
</div>

<div class="blk"><h2>Три разреза, о которых спрашивали</h2>
<div class="lg"><span><i style="background:var(--teal)"></i>регистрации</span>
<span><i style="background:var(--gold)"></i>депозиты</span>
<span class="mut">длина полосы — число событий, справа те же числа цифрами</span></div>
<div class="cuts">${D.cuts.slice(0,3).map(cutBlock).join('')}</div></div>

<div class="blk"><h2>То же самое по конфигурации</h2>
<div class="cuts">${D.cuts.slice(3,6).map(cutBlock).join('')}</div></div>

<div class="blk"><h2>Бренды и гео</h2>
<div class="cuts two">${D.cuts.slice(6).map(cutBlock).join('')}</div></div>

<div class="blk"><h2>Все ${D.reg+D.dep} событий</h2>
<div class="tw"><table class="big"><thead><tr>
  <th class="l">Когда</th><th class="l">Что</th><th class="l">Домен</th><th class="l">Зона</th>
  <th class="l">Бренд</th><th class="l">Гео</th><th class="l">Группа контента</th>
  <th class="l">Страниц</th><th class="l">Даты</th><th class="l">День запуска</th>
</tr></thead><tbody>`
+D.ev.map(e=>{const [tn,tc]=TY[e.type]||[e.type,''];
  return `<tr class="${e.type==='dep'?'dep':''}">
  <td class="l mono nw">${dm(e.t)}</td>
  <td class="l"><span class="tag ${tc==='gold'?'gd':'ok'}">${tn}</span></td>
  <td class="l"><code>${esc(e.dom)}</code></td>
  <td class="l mono mut">${esc(e.zone)}</td>
  <td class="l">${esc(e.br)||'<span class="mut">—</span>'}</td>
  <td class="l nw">${esc(e.geo)}</td>
  <td class="l">${e.g?esc(e.g):'<span class="bad">списка не было</span>'}</td>
  <td class="l mono">${e.pg||'<span class="mut">—</span>'}</td>
  <td class="l mut">${e.dt||'—'}</td>
  <td class="l mono">${e.day||'<span class="bad">?</span>'}</td></tr>`;}).join('')
+`</tbody></table></div>
<p class="note">Отброшено ${D.skip.length}: ${D.skip.map(s=>
  `<code>${esc(s.dom)}</code> (${s.eng}, ${esc(s.type)})`).join(', ')} —
  в поле адреса нет нашего домена, привязать не к чему.</p></div>`;

#!/usr/bin/env python3
"""Сборка html-отчёта по выдаче: типы, разбор доров, сравнение двух съёмов.

    python3 -I scripts/otchet_vydacha.py <tipy.json> <dory.json> <выход.html> [sravnenie.json]
"""
import json
import sys

tipy = json.load(open(sys.argv[1], encoding='utf-8'))
dory = json.load(open(sys.argv[2], encoding='utf-8'))
VYHOD = sys.argv[3]
srav = json.load(open(sys.argv[4], encoding='utf-8')) if len(sys.argv) > 4 else None

SHABLON = r'''<title>Анатомия выдачи</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* Раскладка: одна колонка до 1120px, липкая шапка с переключателем листов,
   секции из заголовка, полосовой диаграммы и таблицы. */
:root{
  --bg:#f6f6f3; --surface:#ffffff; --surface-2:#fbfbf9;
  --ink:#15161a; --ink-2:#585b64; --ink-3:#8b8e96;
  --line:#e4e4df; --line-2:#efefea;
  --accent:#2a78d6; --accent-soft:#dce8f8; --nash:#eb6834; --nash-soft:#fbe3d8;
  --shrift:"IBM Plex Sans",system-ui,-apple-system,Segoe UI,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#131416; --surface:#1b1c1f; --surface-2:#202126;
  --ink:#f0efec; --ink-2:#a9abb2; --ink-3:#7c7f87;
  --line:#2b2c31; --line-2:#242529;
  --accent:#3987e5; --accent-soft:#1e3350; --nash:#d95926; --nash-soft:#422216;
  color-scheme:dark;
}}
:root[data-theme="dark"]{
  --bg:#131416; --surface:#1b1c1f; --surface-2:#202126;
  --ink:#f0efec; --ink-2:#a9abb2; --ink-3:#7c7f87;
  --line:#2b2c31; --line-2:#242529;
  --accent:#3987e5; --accent-soft:#1e3350; --nash:#d95926; --nash-soft:#422216;
  color-scheme:dark;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--shrift);margin:0;
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);
  z-index:10;background:var(--surface)}
.obolochka{max-width:1120px;margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 64px}
header.shapka{position:sticky;top:env(safe-area-inset-top,0px);z-index:9;background:var(--surface);
  border-bottom:1px solid var(--line)}
.shapka-vnutri{max-width:1120px;margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:14px 0}
h1{font-size:19px;font-weight:600;margin:0;letter-spacing:-.01em}
.podzag{color:var(--ink-2);font-size:13px;margin-top:3px}
.listy{display:flex;gap:4px;margin-top:12px}
.listy button{appearance:none;background:none;border:0;border-bottom:2px solid transparent;
  color:var(--ink-2);font:inherit;font-size:14px;font-weight:500;padding:8px 12px;cursor:pointer}
.listy button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--accent)}
.listy button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px;border-radius:4px}
h2{font-size:17px;font-weight:600;margin:0 0 4px;letter-spacing:-.01em;text-wrap:balance}
h2 .nomer{font-family:var(--mono);font-size:12px;color:var(--ink-3);margin-right:8px;font-weight:500}
.vvod{color:var(--ink-2);font-size:14px;max-width:68ch;margin:0 0 16px}
section{margin-top:34px}
.plitki{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0 0}
.plitka{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:13px 14px}
.plitka .ch{font-family:var(--mono);font-size:24px;font-weight:600;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;display:block}
.plitka .pd{color:var(--ink-2);font-size:12px;margin-top:3px}
.plitka.vydel .ch{color:var(--nash)}
.karta{background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.polosy{padding:6px 0}
.ryad{display:grid;grid-template-columns:minmax(118px,26%) 1fr auto;gap:12px;align-items:center;
  padding:7px 16px}
.ryad:hover{background:var(--surface-2)}
.ryad .nazv{font-size:13.5px;min-width:0;overflow-wrap:anywhere}
.ryad .zhelob{background:var(--line-2);border-radius:4px;height:11px;min-width:0;position:relative}
.ryad .fill{background:var(--accent);height:100%;border-radius:0 4px 4px 0;display:block}
.ryad.nash .fill{background:var(--nash)}
.ryad .chis{font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums;
  color:var(--ink-2);white-space:nowrap}
.ryad .chis b{color:var(--ink);font-weight:600}
.tablica-obertka{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:right;padding:9px 12px;border-bottom:1px solid var(--line-2);white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal;min-width:160px}
thead th{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3);
  font-weight:600;background:var(--surface-2);position:sticky;top:0}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
td.num,th.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
td .dol{color:var(--ink-3);font-size:12px;margin-left:6px}
.primery{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);
  padding:0 16px 10px;overflow-wrap:anywhere}
.vyvod{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:0 10px 10px 0;padding:14px 16px;margin-top:18px}
.vyvod h3{font-size:13px;margin:0 0 8px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.vyvod ul{margin:0;padding-left:18px}
.vyvod li{margin:6px 0;font-size:14px;color:var(--ink-2)}
.vyvod li b{color:var(--ink);font-weight:600}
.dve{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:700px){.dve{grid-template-columns:1fr}
  .ryad{grid-template-columns:minmax(96px,38%) 1fr auto;gap:8px;padding:7px 12px}}
.legenda{display:flex;gap:16px;align-items:center;font-size:12.5px;color:var(--ink-2);
  padding:10px 16px 0}
.tochka{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;
  vertical-align:middle}
footer{margin-top:40px;color:var(--ink-3);font-size:12px;border-top:1px solid var(--line);
  padding-top:14px}
footer code{font-family:var(--mono);font-size:11.5px}
[hidden]{display:none!important}
</style>

<header class="shapka">
  <div class="shapka-vnutri">
    <h1>Анатомия выдачи</h1>
    <div class="podzag">Два съёма 16.11.2026 · <span id="shapka-chisla"></span></div>
    <div class="listy" role="tablist">
      <button role="tab" id="t1" aria-controls="list1" aria-selected="true">Типы сайтов</button>
      <button role="tab" id="t2" aria-controls="list2" aria-selected="false">Разбор доров</button>
      <button role="tab" id="t3" aria-controls="list3" aria-selected="false">Сравнение съёмов</button>
    </div>
  </div>
</header>

<div class="obolochka">
  <div id="list1" role="tabpanel" aria-labelledby="t1"></div>
  <div id="list2" role="tabpanel" aria-labelledby="t2" hidden></div>
  <div id="list3" role="tabpanel" aria-labelledby="t3" hidden></div>
  <footer>
    Источник — две выгрузки всех сайтов выдачи за 16.11.2026 по одним и тем же 166 брендам.
    Листы «Типы сайтов» и «Разбор доров» построены на съёме A. Тип считается заново по правилам
    <code>analysis/scripts/serp_tipy.py</code>: в исходной выгрузке дором считался любой поддомен,
    туда попадали <code>m.sports.ru</code> и <code>play.google.com</code>.
    Доля строк и топ-3 — от всех строк выдачи и всех мест в топ-3 в съёме.
  </footer>
</div>

<script id="dannye" type="application/json">__DANNYE__</script>
<script>
const D = JSON.parse(document.getElementById('dannye').textContent);
const ch = n => n.toLocaleString('ru-RU');
const pr = n => n.toLocaleString('ru-RU', {minimumFractionDigits:1, maximumFractionDigits:1}) + '%';

function polosy(dannye, opts = {}) {
  const max = opts.shkala || Math.max(...dannye.map(x => x.dolya));
  return `<div class="karta"><div class="polosy">` + dannye.map(x => `
    <div class="ryad${x.nash ? ' nash' : ''}">
      <div class="nazv">${x.imya}</div>
      <div class="zhelob"><span class="fill" style="width:${(x.dolya / max * 100).toFixed(1)}%"></span></div>
      <div class="chis"><b>${pr(x.dolya)}</b> · ${ch(x.n)}${opts.edinica ? ' ' + opts.edinica : ''}</div>
    </div>`).join('') + `</div></div>`;
}

/* ЛИСТ 1 — типы сайтов */
const t = D.tipy;
document.getElementById('shapka-chisla').textContent =
  `${ch(t.vsego_sajtov)} сайтов · ${ch(t.vsego_strok)} строк выдачи · ${ch(t.vsego_top3)} мест в топ-3`;

document.getElementById('list1').innerHTML = `
<section>
  <h2>Что стоит в выдаче</h2>
  <p class="vvod">Каждый сайт съёма отнесён к одному типу. Доля считается тремя способами:
     от числа сайтов, от строк выдачи (сколько раз сайт показался) и от мест в топ-3 —
     сайтов может быть много, а мест мало.</p>
  <div class="plitki">
    <div class="plitka"><span class="ch">${ch(t.vsego_sajtov)}</span><div class="pd">сайтов в выдаче</div></div>
    <div class="plitka"><span class="ch">${ch(t.vsego_strok)}</span><div class="pd">строк выдачи</div></div>
    <div class="plitka"><span class="ch">${ch(t.vsego_top3)}</span><div class="pd">мест в топ-3</div></div>
    <div class="plitka"><span class="ch">${t.tipy.length}</span><div class="pd">типов сайтов</div></div>
  </div>
</section>

<section>
  <h2><span class="nomer">01</span>Доля каждого типа по числу сайтов</h2>
  ${polosy(t.tipy.map(x => ({imya: x.imya, n: x.n, dolya: x.dolya})), {edinica: 'сайтов'})}
</section>

<section>
  <h2><span class="nomer">02</span>Сайты, показы и топ-3 рядом</h2>
  <p class="vvod">Три доли у одного типа расходятся — это и есть главное:
     кого много, тот не обязательно занимает места.</p>
  <div class="karta tablica-obertka">
    <table>
      <thead><tr><th>Тип</th><th class="num">Сайтов</th><th class="num">%</th>
        <th class="num">Строк</th><th class="num">%</th><th class="num">Топ-3</th><th class="num">%</th></tr></thead>
      <tbody>${t.tipy.map(x => `<tr>
        <td>${x.imya}</td>
        <td class="num">${ch(x.n)}</td><td class="num">${pr(x.dolya)}</td>
        <td class="num">${ch(x.strok)}</td><td class="num">${pr(x.dolya_strok)}</td>
        <td class="num">${ch(x.top3)}</td><td class="num">${pr(x.dolya_top3)}</td></tr>`).join('')}
      </tbody>
    </table>
  </div>
</section>

<section>
  <h2><span class="nomer">03</span>Примеры по типам</h2>
  <div class="karta">${t.tipy.map(x => `
    <div class="ryad" style="grid-template-columns:minmax(118px,26%) 1fr">
      <div class="nazv">${x.imya}</div>
      <div class="chis" style="font-family:var(--mono);font-size:11.5px;color:var(--ink-3);white-space:normal;text-align:left;overflow-wrap:anywhere">${x.primery.join(' · ')}</div>
    </div>`).join('')}</div>
</section>

<div class="vyvod">
  <h3>Что из этого следует</h3>
  <ul>
    <li><b>Доров больше всех, а мест у них меньше всех.</b> ${pr(t.tipy[0].dolya)} сайтов выдачи — доры,
        но мест в топ-3 у них только ${pr(t.tipy[0].dolya_top3)}. На один дор приходится
        ${(t.tipy[0].top3 / t.tipy[0].n).toFixed(2)} места в топ-3.</li>
    <li><b>Топ-3 держат брендовые домены.</b> ${pr(t.tipy[1].dolya)} сайтов и ${pr(t.tipy[1].dolya_top3)} мест
        в топ-3 — это зеркала и клоны, названные именем бренда. На сайт приходится
        ${(t.tipy[1].top3 / t.tipy[1].n).toFixed(2)} места.</li>
    <li><b>Порталы и соцсети берут объёмом показов, а не числом сайтов.</b>
        Порталы и рейтинги — это ${pr(t.tipy.find(x=>x.imya.startsWith('порталы')).dolya)} сайтов,
        но ${pr(t.tipy.find(x=>x.imya.startsWith('порталы')).dolya_strok)} строк выдачи;
        соцсети — ${pr(t.tipy.find(x=>x.imya.startsWith('соцсети')).dolya)} сайтов и
        ${pr(t.tipy.find(x=>x.imya.startsWith('соцсети')).dolya_strok)} строк.</li>
  </ul>
</div>`;

/* ЛИСТ 2 — разбор доров */
const d = D.dory;
const prim = (karta) => Object.entries(karta);
document.getElementById('list2').innerHTML = `
<section>
  <h2>Доры крупным планом</h2>
  <p class="vvod">Дор здесь — поддомен на чужой базе: <span style="font-family:var(--mono)">бренд.база.зона</span>.
     Таких ${ch(d.vsego_dorov)} из ${ch(d.vsego_sajtov)} сайтов съёма. Всё дальше — доли от этого числа.</p>
  <div class="plitki">
    <div class="plitka"><span class="ch">${ch(d.vsego_dorov)}</span><div class="pd">доров, ${pr(d.dolya_ot_vydachi)} выдачи</div></div>
    <div class="plitka"><span class="ch">${ch(d.bazy)}</span><div class="pd">баз под ними</div></div>
    <div class="plitka"><span class="ch">${d.na_bazu}</span><div class="pd">дора на базу в среднем</div></div>
    <div class="plitka"><span class="ch">${ch(d.top3)}</span><div class="pd">мест в топ-3, ${(d.top3 / d.vsego_dorov).toFixed(2)} на дор</div></div>
    <div class="plitka vydel"><span class="ch">${ch(d.nashi.find(x => x.imya === 'наши').n)}</span><div class="pd">наших доров, ${pr(d.nashi.find(x => x.imya === 'наши').dolya)}</div></div>
  </div>
</section>

<section>
  <h2><span class="nomer">01</span>Доменные зоны</h2>
  <p class="vvod">Всего ${d.zony_vse} зон. Две зоны забирают
     ${pr(d.zony[0].dolya + d.zony[1].dolya)} всех доров.</p>
  ${polosy(d.zony, {edinica: 'доров'})}
  <div class="karta tablica-obertka" style="margin-top:12px">
    <table>
      <thead><tr><th>Зона</th><th class="num">Доров</th><th class="num">% доров</th>
        <th class="num">Строк</th><th class="num">Топ-3</th><th class="num">Топ-3 на дор</th><th>Примеры</th></tr></thead>
      <tbody>${d.zony_kachestvo.map(x => `<tr>
        <td class="num">.${x.imya}</td><td class="num">${ch(x.n)}</td><td class="num">${pr(x.dolya)}</td>
        <td class="num">${ch(x.strok)}</td><td class="num">${ch(x.top3)}</td>
        <td class="num"><b>${x.top3_na_sajt.toFixed(2)}</b></td>
        <td style="text-align:left;white-space:normal;font-family:var(--mono);font-size:11px;color:var(--ink-3);overflow-wrap:anywhere">${(d.primery_zona[x.imya] || []).slice(0,2).join(' · ')}</td></tr>`).join('')}
      </tbody>
    </table>
  </div>
</section>

<section>
  <h2><span class="nomer">02</span>Стиль имени базы</h2>
  <p class="vvod">Как назван домен, на котором живёт дор. Девять из десяти баз названы механически:
     слово «казино» с цифрами, короткий набор букв, цифры.</p>
  ${polosy(d.stili, {edinica: 'доров'})}
  <div class="karta tablica-obertka" style="margin-top:12px">
    <table>
      <thead><tr><th>Стиль</th><th class="num">Доров</th><th class="num">%</th><th>Примеры</th></tr></thead>
      <tbody>${d.stili.map(x => `<tr>
        <td>${x.imya}</td><td class="num">${ch(x.n)}</td><td class="num">${pr(x.dolya)}</td>
        <td style="text-align:left;white-space:normal;font-family:var(--mono);font-size:11px;color:var(--ink-3);overflow-wrap:anywhere">${(d.primery_stil[x.imya] || []).slice(0,3).join(' · ')}</td></tr>`).join('')}
      </tbody>
    </table>
  </div>
</section>

<section>
  <h2><span class="nomer">03</span>Метка поддомена и чьи доры</h2>
  <div class="dve">
    <div>
      <p class="vvod">Левая часть адреса — почти всегда ровно имя бренда, без приставок.</p>
      ${polosy(d.metki, {edinica: 'доров'})}
    </div>
    <div>
      <p class="vvod">Наши доры в съёме видно, но их доля в выдаче мала.</p>
      ${polosy(d.nashi.map(x => ({...x, nash: x.imya === 'наши'})), {edinica: 'доров'})}
      <div class="legenda"><span><span class="tochka" style="background:var(--nash)"></span>наши</span>
        <span><span class="tochka" style="background:var(--accent)"></span>чужие</span></div>
    </div>
  </div>
</section>

<section>
  <h2><span class="nomer">04</span>Под какие бренды делают доры</h2>
  <p class="vvod">Всего доры встречаются в выдаче ${ch(d.brendov_vsego)} брендов. Топ-25 по числу доров,
     доля — от всех упоминаний брендов у доров.</p>
  ${polosy(d.brendy, {edinica: 'доров'})}
</section>

<section>
  <h2><span class="nomer">05</span>Где доры держат выдачу, а где их выдавили</h2>
  <p class="vvod">Доля строк выдачи бренда, занятых дорами. Считано по сайтам ровно с одним брендом —
     у них показы относятся к этому бренду без дележа; взяты бренды от 10 строк,
     таких ${ch(d.brendov_s_dolyami)}.</p>
  <div class="dve">
    <div>
      <div class="legenda" style="padding-left:0"><b style="color:var(--ink)">Выдача из доров</b></div>
      ${polosy(d.brend_dory_mnogo.map(x => ({imya: x.imya, n: x.dory, dolya: x.dolya})), {edinica: 'строк', shkala: 100})}
    </div>
    <div>
      <div class="legenda" style="padding-left:0"><b style="color:var(--ink)">Доров почти нет</b></div>
      ${polosy(d.brend_dory_malo.slice().reverse().map(x => ({imya: x.imya, n: x.dory, dolya: x.dolya})), {edinica: 'строк', shkala: 100})}
    </div>
  </div>
</section>

<section>
  <h2><span class="nomer">06</span>Сколько доров на одной базе</h2>
  <p class="vvod">В съёме видно ${ch(d.bazy)} баз. Доля — от числа баз. Это видимая часть:
     на базе может стоять больше доров, просто в выдачу попали не все.</p>
  ${polosy(d.raspred_baz, {edinica: 'баз'})}
  <div class="karta tablica-obertka" style="margin-top:12px">
    <table>
      <thead><tr><th>База с наибольшим числом доров</th><th class="num">Доров</th><th class="num">% всех доров</th></tr></thead>
      <tbody>${d.top_bazy.map(x => `<tr><td class="num" style="font-size:12.5px">${x.imya}</td>
        <td class="num">${ch(x.n)}</td><td class="num">${pr(x.dolya)}</td></tr>`).join('')}</tbody>
    </table>
  </div>
</section>

<div class="vyvod">
  <h3>Что из этого следует</h3>
  <ul>
    <li><b>Зона решает.</b> ${pr(d.zony[0].dolya + d.zony[1].dolya)} доров сидят в .${d.zony[0].imya} и .${d.zony[1].imya},
        но по местам в топ-3 на дор лучшая зона — .${d.zony_kachestvo.slice().sort((a,b)=>b.top3_na_sajt-a.top3_na_sajt)[0].imya}
        (${d.zony_kachestvo.slice().sort((a,b)=>b.top3_na_sajt-a.top3_na_sajt)[0].top3_na_sajt.toFixed(2)} против
        ${d.zony_kachestvo[0].top3_na_sajt.toFixed(2)} у .${d.zony_kachestvo[0].imya}).</li>
    <li><b>Имя базы ничего не маскирует.</b> ${pr(d.stili.filter(x => /казино|цифр|букв/.test(x.imya)).reduce((s,x)=>s+x.dolya,0))}
        баз названы механически — «казино» с цифрами, цифры, наборы букв.</li>
    <li><b>Поддомен — это прямо имя бренда.</b> ${pr(d.metki[0].dolya)} доров названы точно именем бренда,
        ещё ${pr(d.metki[1].dolya)} — бренд с приставкой или цифрами.</li>
    <li><b>Сетки размазаны тонко.</b> ${pr(d.raspred_baz[0].dolya)} баз дают в выдачу всего один дор;
        на крупнейшую базу <span style="font-family:var(--mono)">${d.top_bazy[0].imya}</span>
        приходится ${ch(d.top_bazy[0].n)} дора — ${pr(d.top_bazy[0].dolya)} всех.</li>
  </ul>
</div>`;

/* ЛИСТ 3 — сравнение съёмов */
const v = D.srav;
if (v) document.getElementById('list3').innerHTML = `
<section>
  <h2>Два съёма одного дня</h2>
  <p class="vvod">Те же 166 брендов, тот же день. Объём выдачи совпал почти точь-в-точь,
     а состав сайтов — нет. Разница между съёмами и есть мера того, насколько выдача текучая.</p>
  <div class="plitki">
    <div class="plitka"><span class="ch">${ch(v.a.sajtov)} / ${ch(v.b.sajtov)}</span><div class="pd">сайтов, съём A / B</div></div>
    <div class="plitka"><span class="ch">${ch(v.a.strok)} / ${ch(v.b.strok)}</span><div class="pd">строк выдачи</div></div>
    <div class="plitka"><span class="ch">${ch(v.a.top3)} / ${ch(v.b.top3)}</span><div class="pd">мест в топ-3</div></div>
    <div class="plitka"><span class="ch">${pr(v.dolya_obshih_a)}</span><div class="pd">сайтов A дожили до B (${ch(v.obshih)})</div></div>
    <div class="plitka vydel"><span class="ch">${ch(v.tolko_a)} / ${ch(v.tolko_b)}</span><div class="pd">только в A / только в B</div></div>
  </div>
</section>

<section>
  <h2><span class="nomer">01</span>Структура не шевельнулась</h2>
  <p class="vvod">Доли типов в двух съёмах совпадают с точностью до долей процента —
     при том, что каждый четвёртый сайт сменился.</p>
  <div class="karta tablica-obertka">
    <table>
      <thead><tr><th>Тип</th><th class="num">Сайтов A</th><th class="num">Сайтов B</th>
        <th class="num">% в A</th><th class="num">% в B</th>
        <th class="num">Осталось</th><th class="num">Удержание</th></tr></thead>
      <tbody>${v.tipy.map(x => `<tr>
        <td>${x.imya}</td><td class="num">${ch(x.a)}</td><td class="num">${ch(x.b)}</td>
        <td class="num">${pr(x.dolya_a)}</td><td class="num">${pr(x.dolya_b)}</td>
        <td class="num">${ch(x.ostalos)}</td><td class="num"><b>${pr(x.uderzhanie)}</b></td></tr>`).join('')}
      </tbody>
    </table>
  </div>
</section>

<section>
  <h2><span class="nomer">02</span>Кто держится, а кого вымывает</h2>
  <p class="vvod">Доля сайтов съёма A, которые нашлись и в съёме B. Шкала 0–100%.</p>
  ${polosy(v.tipy.slice().sort((a,b) => b.uderzhanie - a.uderzhanie)
      .map(x => ({imya: x.imya, n: x.ostalos, dolya: x.uderzhanie})), {edinica: 'сайтов', shkala: 100})}
</section>

<section>
  <h2><span class="nomer">03</span>Места в топ-3 держатся хуже всего у доров</h2>
  <p class="vvod">Из ${ch(v.top3_a)} сайтов, стоявших в топ-3 в съёме A, место сохранили
     ${ch(v.top3_derzhit)} — ${pr(v.top3_dolya)}. По типам, шкала 0–100%.</p>
  ${polosy(v.top3_po_tipu.map(x => ({imya: x.imya, n: x.derzhit, dolya: x.dolya})),
      {edinica: 'сайтов', shkala: 100})}
</section>

<section>
  <h2><span class="nomer">04</span>Зоны доров: доля держится, сайты меняются</h2>
  <div class="karta tablica-obertka">
    <table>
      <thead><tr><th>Зона</th><th class="num">Доров A</th><th class="num">Доров B</th>
        <th class="num">% в A</th><th class="num">% в B</th><th class="num">Удержание</th></tr></thead>
      <tbody>${v.zony.map(x => `<tr>
        <td class="num">.${x.imya}</td><td class="num">${ch(x.a)}</td><td class="num">${ch(x.b)}</td>
        <td class="num">${pr(x.dolya_a)}</td><td class="num">${pr(x.dolya_b)}</td>
        <td class="num"><b>${pr(x.uderzhanie)}</b></td></tr>`).join('')}
      </tbody>
    </table>
  </div>
</section>

<section>
  <h2><span class="nomer">05</span>Наши сайты в этих съёмах</h2>
  <p class="vvod">Наших доров в A ${ch(v.nashi_a)}, в B ${ch(v.nashi_b)}, в обоих ${ch(v.nashi_ostalis)} —
     удержание ${pr(100 * v.nashi_ostalis / v.nashi_a)}. Это ниже, чем у чужих доров
     (${pr(v.tipy.find(x => x.imya.startsWith('доры')).uderzhanie)}).</p>
  <div class="dve">
    <div class="karta"><div class="legenda"><b style="color:var(--ink)">Выпали из B — ${ch(v.nashi_ushli.length)}</b></div>
      <div class="primery">${v.nashi_ushli.join(' · ')}</div></div>
    <div class="karta"><div class="legenda"><b style="color:var(--ink)">Появились в B — ${ch(v.nashi_novye.length)}</b></div>
      <div class="primery">${v.nashi_novye.join(' · ')}</div></div>
  </div>
</section>

<section>
  <h2><span class="nomer">06</span>Доля доров по брендам совпала</h2>
  <p class="vvod">По ${ch(v.brendov)} брендам доля строк выдачи, занятых дорами:
     корреляция между съёмами ${v.korrelyaciya}, средняя ${pr(v.sredn_dolya_a)} против ${pr(v.sredn_dolya_b)},
     средний сдвиг ${v.sredn_sdvig} процентных пункта. Ниже — бренды с самыми большими сдвигами.</p>
  <div class="karta tablica-obertka">
    <table>
      <thead><tr><th>Бренд</th><th class="num">Доля доров, A</th><th class="num">Доля доров, B</th><th class="num">Сдвиг</th></tr></thead>
      <tbody>${v.sdvigi.map(x => `<tr><td>${x.imya}</td>
        <td class="num">${pr(x.a)}</td><td class="num">${pr(x.b)}</td>
        <td class="num"><b style="color:${x.raznica > 0 ? 'var(--nash)' : 'var(--accent)'}">${x.raznica > 0 ? '+' : ''}${x.raznica.toLocaleString('ru-RU', {minimumFractionDigits:1, maximumFractionDigits:1})}</b></td></tr>`).join('')}
      </tbody>
    </table>
  </div>
</section>

<div class="vyvod">
  <h3>Что из этого следует</h3>
  <ul>
    <li><b>Выдача не меняется — меняются сайты в ней.</b> Между двумя съёмами одного дня сменился
        каждый четвёртый сайт (${ch(v.tolko_a)} ушли, ${ch(v.tolko_b)} пришли), а доли типов
        остались те же с точностью до 0,2 п.п.</li>
    <li><b>Вымывает именно доры.</b> Удержание у доров ${pr(v.tipy.find(x => x.imya.startsWith('доры')).uderzhanie)},
        у брендовых доменов ${pr(v.tipy.find(x => x.imya.startsWith('брендовые')).uderzhanie)},
        у соцсетей и площадок рунета — под 100%.</li>
    <li><b>Место в топ-3 у дора — расходник.</b> Из доров, стоявших в топ-3, место сохранили
        ${pr(v.top3_po_tipu[v.top3_po_tipu.length - 1].dolya)}, у брендовых доменов —
        ${pr(v.top3_po_tipu.find(x => x.imya.startsWith('брендовые')).dolya)}.</li>
    <li><b>Наши ротируются сильнее чужих.</b> ${ch(v.nashi_ushli.length)} наших сайтов выпали,
        ${ch(v.nashi_novye.length)} появились; в обоих съёмах только ${ch(v.nashi_ostalis)} из ${ch(v.nashi_a)}.</li>
  </ul>
</div>`;

/* переключение листов */
const knopki = [...document.querySelectorAll('.listy button')];
knopki.forEach(k => k.addEventListener('click', () => {
  knopki.forEach(d2 => {
    const vybran = d2 === k;
    d2.setAttribute('aria-selected', String(vybran));
    document.getElementById(d2.getAttribute('aria-controls')).hidden = !vybran;
  });
  try { localStorage.setItem('list', k.id); } catch (e) {}
  window.scrollTo({top: 0});
}));
try { const s = localStorage.getItem('list');
  if (s === 't2' || s === 't3') document.getElementById(s).click(); } catch (e) {}
</script>
'''

dannye = json.dumps({'tipy': tipy, 'dory': dory, 'srav': srav}, ensure_ascii=False)
open(VYHOD, 'w', encoding='utf-8').write(SHABLON.replace('__DANNYE__', dannye))
print(f'-> {VYHOD}')

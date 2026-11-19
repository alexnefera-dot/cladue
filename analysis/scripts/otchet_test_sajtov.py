#!/usr/bin/env python3
"""Html-отчёт по тесту сайтов: что взяли, что получили.

    python3 -I scripts/otchet_test_sajtov.py <otchet_test.json> <выход.html>
"""
import json
import sys

D = json.load(open(sys.argv[1], encoding='utf-8'))
VYHOD = sys.argv[2]

SHABLON = r'''<title>Тест сайтов, ноябрь</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* Раскладка: одна колонка до 1100px, секции из заголовка, плиток и полных таблиц. */
:root{
  --bg:#f6f6f3; --surface:#ffffff; --surface-2:#fbfbf9;
  --ink:#15161a; --ink-2:#585b64; --ink-3:#8b8e96;
  --line:#e4e4df; --line-2:#efefea;
  --accent:#2a78d6; --nash:#eb6834; --good:#1baf7a;
  --shrift:"IBM Plex Sans",system-ui,-apple-system,Segoe UI,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#131416; --surface:#1b1c1f; --surface-2:#202126;
  --ink:#f0efec; --ink-2:#a9abb2; --ink-3:#7c7f87;
  --line:#2b2c31; --line-2:#242529;
  --accent:#3987e5; --nash:#d95926; --good:#199e70; color-scheme:dark;
}}
:root[data-theme="dark"]{
  --bg:#131416; --surface:#1b1c1f; --surface-2:#202126;
  --ink:#f0efec; --ink-2:#a9abb2; --ink-3:#7c7f87;
  --line:#2b2c31; --line-2:#242529;
  --accent:#3987e5; --nash:#d95926; --good:#199e70; color-scheme:dark;
}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--shrift);margin:0;
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);
  z-index:10;background:var(--surface)}
.obolochka{max-width:1100px;margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0 64px}
header.shapka{background:var(--surface);border-bottom:1px solid var(--line)}
.shapka-vnutri{max-width:1100px;margin:0 auto;
  padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:18px}
h1{font-size:21px;font-weight:600;margin:0;letter-spacing:-.01em}
.podzag{color:var(--ink-2);font-size:13.5px;margin-top:4px}
h2{font-size:17px;font-weight:600;margin:0 0 4px;letter-spacing:-.01em;text-wrap:balance}
h2 .nomer{font-family:var(--mono);font-size:12px;color:var(--ink-3);margin-right:8px;font-weight:500}
.vvod{color:var(--ink-2);font-size:14px;max-width:70ch;margin:0 0 16px}
section{margin-top:34px}
.plitki{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px;margin:18px 0 0}
.plitka{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:13px 14px}
.plitka .ch{font-family:var(--mono);font-size:25px;font-weight:600;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums;display:block}
.plitka .pd{color:var(--ink-2);font-size:12px;margin-top:3px}
.plitka.a .ch{color:var(--accent)} .plitka.n .ch{color:var(--nash)}
.karta{background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.tablica-obertka{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:right;padding:8px 11px;border-bottom:1px solid var(--line-2);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3);
  font-weight:600;background:var(--surface-2);position:sticky;top:0}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--surface-2)}
tbody tr.itogo{background:var(--surface-2);font-weight:600}
td.num,th.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
td.sait{font-family:var(--mono);font-size:12.5px}
td.daty{text-align:left;white-space:normal;font-size:12px;color:var(--ink-2);min-width:230px}
.tochka{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}
.polosy{padding:6px 0}
.ryad{display:grid;grid-template-columns:minmax(80px,16%) 1fr auto;gap:12px;align-items:center;padding:6px 16px}
.ryad .zhelob{background:var(--line-2);border-radius:4px;height:11px;min-width:0;display:flex}
.ryad .fill{height:100%;border-radius:0 4px 4px 0}
.ryad .chis{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);white-space:nowrap}
.ryad .chis b{color:var(--ink)}
.vyvod{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:0 10px 10px 0;padding:14px 16px;margin-top:18px}
.vyvod h3{font-size:13px;margin:0 0 8px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3)}
.vyvod ul{margin:0;padding-left:18px}
.vyvod li{margin:7px 0;font-size:14px;color:var(--ink-2)}
.vyvod li b{color:var(--ink);font-weight:600}
.legenda{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--ink-2);padding:10px 16px 0}
footer{margin-top:40px;color:var(--ink-3);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
@media(max-width:700px){.ryad{grid-template-columns:minmax(64px,26%) 1fr auto;gap:8px;padding:6px 12px}}
</style>

<header class="shapka"><div class="shapka-vnutri">
  <h1>Тест сайтов, ноябрь</h1>
  <div class="podzag" id="podzag"></div>
</div></header>
<div class="obolochka"><div id="telo"></div>
<footer>
  Конверсии по поддоменам взяты из трекера напрямую, окно 10–19.11; конверсии до 10.11
  показаны отдельно и в зачёт теста не идут. По чужим доменам трекер данных не отдаёт —
  там цифры из отчёта исполнителей. Повторная конверсия — любая, кроме первой по сайту.
</footer></div>

<script id="dannye" type="application/json">__DANNYE__</script>
<script>
const D = JSON.parse(document.getElementById('dannye').textContent);
const ch = n => n.toLocaleString('ru-RU');
const pr = n => n.toLocaleString('ru-RU',{minimumFractionDigits:1,maximumFractionDigits:1}) + '%';
const den = d => d.slice(8,10) + '.' + d.slice(5,7);
const sv = D.svod_vse, sp = D.svod_pod, sd = D.svod_dom;

document.getElementById('podzag').textContent =
  `Окно ${den(D.okno.start)}–${den(D.okno.konec)}, ${D.okno.dney} дней · взято ${ch(sv.vzyato)} сайтов · `
  + `${ch(sv.reg)} регистраций и ${ch(sv.fd)} депозитов`;

function stroki(karta, zagolovok) {
  const sp2 = Object.entries(karta).sort((a,b) =>
    b[1].vsego - a[1].vsego || a[1].postavlen.localeCompare(b[1].postavlen) || a[0].localeCompare(b[0]));
  const it = sp2.reduce((s,[,o]) => ({reg:s.reg+o.reg, fd:s.fd+o.fd, povtor:s.povtor+o.povtor}),
    {reg:0,fd:0,povtor:0});
  return `<div class="karta tablica-obertka"><table>
    <thead><tr><th>Сайт</th><th class="num">Поставлен</th><th class="num">Дней в работе</th>
      <th class="num">Рег</th><th class="num">ФД</th><th class="num">Всего</th>
      <th class="num">Повторных</th><th>Даты конверсий</th><th>Было до теста</th></tr></thead>
    <tbody>${sp2.map(([s,o]) => `<tr>
      <td class="sait">${s}</td>
      <td class="num">${den(o.postavlen)}</td><td class="num">${ch(o.dney)}</td>
      <td class="num">${o.reg ? '<b>' + ch(o.reg) + '</b>' : '—'}</td>
      <td class="num">${o.fd ? '<b style="color:var(--nash)">' + ch(o.fd) + '</b>' : '—'}</td>
      <td class="num">${o.vsego || '—'}</td>
      <td class="num">${o.povtor ? ch(o.povtor) : '—'}</td>
      <td class="daty">${Object.entries(o.dni).map(([d,c]) =>
        den(d) + ' — ' + [c.reg ? c.reg + ' рег' : '', c.fd ? c.fd + ' фд' : '']
          .filter(Boolean).join(', ')).join(' · ') || '—'}</td>
      <td class="daty">${Object.keys(o.do_testa).length
        ? Object.entries(o.do_testa).map(([k,v]) => v + ' ' + (k === 'reg' ? 'рег' : 'фд')).join(', ')
        : '—'}</td></tr>`).join('')}
      <tr class="itogo"><td>${zagolovok}: ${ch(sp2.length)}</td><td></td><td></td>
        <td class="num">${ch(it.reg)}</td><td class="num">${ch(it.fd)}</td>
        <td class="num">${ch(it.reg + it.fd)}</td><td class="num">${ch(it.povtor)}</td>
        <td></td><td></td></tr>
    </tbody></table></div>`;
}

const maxд = Math.max(...Object.values(D.po_dnyam).map(v => Math.max(v.postavleno, v.reg + v.fd)));

document.getElementById('telo').innerHTML = `
<section>
  <h2>Что получилось</h2>
  <p class="vvod">Тест шёл ${D.okno.dney} дней: первые домены поставлены ${den(D.okno.start)},
     последние данные по конверсиям — ${den(D.okno.konec)}. Считаются только конверсии
     с ${den('2026-11-10')}, когда пошли первые поддомены; всё, что было раньше, вынесено
     в отдельную колонку и в зачёт не идёт.</p>
  <div class="plitki">
    <div class="plitka"><span class="ch">${ch(sv.vzyato)}</span><div class="pd">сайтов взято в работу</div></div>
    <div class="plitka a"><span class="ch">${ch(sv.s_konv)}</span><div class="pd">дали конверсию — ${pr(sv.uspeh)}</div></div>
    <div class="plitka n"><span class="ch">${ch(sv.s_povtor)}</span><div class="pd">дали повторную — ${pr(sv.uspeh_povtor)}</div></div>
    <div class="plitka"><span class="ch">${ch(sv.reg)}</span><div class="pd">регистраций</div></div>
    <div class="plitka"><span class="ch">${ch(sv.fd)}</span><div class="pd">депозитов</div></div>
    <div class="plitka"><span class="ch">${ch(sv.povtor)}</span><div class="pd">повторных конверсий</div></div>
  </div>
</section>

<section>
  <h2><span class="nomer">01</span>Поддомены против доменов</h2>
  <p class="vvod">Успешность считается двумя способами: доля сайтов, давших хотя бы одну
     конверсию, и доля сайтов, у которых конверсия повторилась. Второе показательнее —
     одиночная конверсия на сайте может быть случайной.</p>
  <div class="karta tablica-obertka"><table>
    <thead><tr><th>Тип</th><th class="num">Взято</th><th class="num">С конверсией</th>
      <th class="num">Успешность</th><th class="num">С повторной</th><th class="num">Успешность по повторным</th>
      <th class="num">Рег</th><th class="num">ФД</th><th class="num">Конверсий всего</th>
      <th class="num">Повторных</th><th class="num">Конверсий на сайт</th></tr></thead>
    <tbody>
      ${[['Поддомены (наши доры)', sp], ['Домены (брендовые)', sd]].map(([imya, s]) => `<tr>
        <td>${imya}</td><td class="num">${ch(s.vzyato)}</td><td class="num">${ch(s.s_konv)}</td>
        <td class="num"><b>${pr(s.uspeh)}</b></td><td class="num">${ch(s.s_povtor)}</td>
        <td class="num"><b style="color:var(--nash)">${pr(s.uspeh_povtor)}</b></td>
        <td class="num">${ch(s.reg)}</td><td class="num">${ch(s.fd)}</td>
        <td class="num">${ch(s.reg + s.fd)}</td><td class="num">${ch(s.povtor)}</td>
        <td class="num">${((s.reg + s.fd) / s.vzyato).toFixed(2)}</td></tr>`).join('')}
      <tr class="itogo"><td>Всего</td><td class="num">${ch(sv.vzyato)}</td>
        <td class="num">${ch(sv.s_konv)}</td><td class="num">${pr(sv.uspeh)}</td>
        <td class="num">${ch(sv.s_povtor)}</td><td class="num">${pr(sv.uspeh_povtor)}</td>
        <td class="num">${ch(sv.reg)}</td><td class="num">${ch(sv.fd)}</td>
        <td class="num">${ch(sv.reg + sv.fd)}</td><td class="num">${ch(sv.povtor)}</td>
        <td class="num">${((sv.reg + sv.fd) / sv.vzyato).toFixed(2)}</td></tr>
    </tbody></table></div>
</section>

<section>
  <h2><span class="nomer">02</span>По дням: сколько ставили и сколько получали</h2>
  <div class="karta"><div class="legenda">
    <span><span class="tochka" style="background:var(--ink-3)"></span>поставлено сайтов</span>
    <span><span class="tochka" style="background:var(--accent)"></span>регистрации</span>
    <span><span class="tochka" style="background:var(--nash)"></span>депозиты</span>
  </div><div class="polosy">
    ${Object.entries(D.po_dnyam).map(([d,v]) => `
      <div class="ryad"><div class="nazv">${den(d)}</div>
        <div class="zhelob">
          <span class="fill" style="width:${v.postavleno / maxд * 50}%;background:var(--ink-3)"></span>
          <span class="fill" style="width:${v.reg / maxд * 50}%;background:var(--accent);border-radius:0"></span>
          <span class="fill" style="width:${v.fd / maxд * 50}%;background:var(--nash)"></span>
        </div>
        <div class="chis">поставлено <b>${ch(v.postavleno)}</b> · рег <b>${ch(v.reg)}</b> · фд <b>${ch(v.fd)}</b></div>
      </div>`).join('')}
  </div></div>
</section>

<section>
  <h2><span class="nomer">03</span>Все поддомены — ${ch(sp.vzyato)} штук</h2>
  <p class="vvod">Полный список без сокращений, отсортирован по числу конверсий.</p>
  ${stroki(D.pod, 'Поддомены')}
</section>

<section>
  <h2><span class="nomer">04</span>Все домены — ${ch(sd.vzyato)} штук</h2>
  <p class="vvod">Конверсии известны только по тем доменам, что попали в отчёт исполнителей;
     трекер по чужим доменам данных не отдаёт.</p>
  ${stroki(D.dom, 'Домены')}
</section>

<section>
  <h2><span class="nomer">05</span>По брендам</h2>
  <p class="vvod">Сколько сайтов каждого бренда взяли и что они дали. Видно, где
     распыляли силы на один бренд.</p>
  <div class="karta tablica-obertka"><table>
    <thead><tr><th>Бренд</th><th class="num">Доменов</th><th class="num">Поддоменов</th>
      <th class="num">Всего сайтов</th><th class="num">Рег</th><th class="num">ФД</th></tr></thead>
    <tbody>${Object.entries(D.brendy).map(([b,v]) => `<tr>
      <td>${b}</td><td class="num">${v.dom || '—'}</td><td class="num">${v.pod || '—'}</td>
      <td class="num"><b>${ch(v.dom + v.pod)}</b></td>
      <td class="num">${v.reg || '—'}</td><td class="num">${v.fd || '—'}</td></tr>`).join('')}
    </tbody></table></div>
</section>

<div class="vyvod">
  <h3>Итог</h3>
  <ul>
    <li><b>Взято ${ch(sv.vzyato)} сайтов за ${D.okno.dney} дней, конверсию дали ${ch(sv.s_konv)} — ${pr(sv.uspeh)}.</b>
        Повторилась конверсия у ${ch(sv.s_povtor)} сайтов, это ${pr(sv.uspeh_povtor)} от всего взятого.
        Суммарно ${ch(sv.reg)} регистраций и ${ch(sv.fd)} депозитов.</li>
    <li><b>Поддомены сработали в четыре раза лучше доменов.</b>
        ${pr(sp.uspeh)} поддоменов дали конверсию против ${pr(sd.uspeh)} доменов;
        по повторным ${pr(sp.uspeh_povtor)} против ${pr(sd.uspeh_povtor)}.
        На один поддомен приходится ${((sp.reg + sp.fd) / sp.vzyato).toFixed(2)} конверсии,
        на домен — ${((sd.reg + sd.fd) / sd.vzyato).toFixed(2)}.</li>
    <li><b>Преобладали поддомены:</b> ${ch(sp.vzyato)} из ${ch(sv.vzyato)}
        (${pr(100 * sp.vzyato / sv.vzyato)}), и они же дали
        ${pr(100 * (sp.reg + sp.fd) / (sv.reg + sv.fd))} всех конверсий.</li>
    <li><b>Результат держится на нескольких сайтах.</b> Больше всего дал
        ${Object.entries(D.pod).sort((a,b) => b[1].vsego - a[1].vsego)[0][0]} —
        ${ch(Object.entries(D.pod).sort((a,b) => b[1].vsego - a[1].vsego)[0][1].vsego)} конверсий,
        это ${pr(100 * Object.entries(D.pod).sort((a,b) => b[1].vsego - a[1].vsego)[0][1].vsego / (sv.reg + sv.fd))}
        всего результата теста.</li>
    <li><b>Депозиты редки:</b> ${ch(sv.fd)} на ${ch(sv.reg)} регистраций, то есть
        ${pr(100 * sv.fd / sv.reg)} от числа регистраций.</li>
  </ul>
</div>`;
</script>
'''
open(VYHOD, 'w', encoding='utf-8').write(
    SHABLON.replace('__DANNYE__', json.dumps(D, ensure_ascii=False)))
print(f'-> {VYHOD}')

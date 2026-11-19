#!/usr/bin/env python3
"""Html-отчёт по тесту сайтов: что взяли, что получили.

    python3 -I scripts/otchet_test_sajtov.py <otchet_test.json> <выход.html>
"""
import json
import sys

D = json.load(open(sys.argv[1], encoding='utf-8'))
VYHOD = sys.argv[2]

SHABLON = r'''<title>Крутка ПФ, ноябрь</title>
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
  <h1>Крутка ПФ, ноябрь</h1>
  <div class="podzag" id="podzag"></div>
</div></header>
<div class="obolochka"><div id="telo"></div>
<footer>
  Методика: сайт попадал в работу после того, как давал конверсию сам — эта конверсия
  здесь названа триггером и в результат не засчитывается. Результатом считается только то,
  что пришло строго позже даты передачи. Конверсии по поддоменам взяты из трекера напрямую,
  по чужим доменам трекер данных не отдаёт — там цифры из отчёта исполнителей.
</footer></div>

<script id="dannye" type="application/json">__DANNYE__</script>
<script>
const D = JSON.parse(document.getElementById('dannye').textContent);
const ch = n => n.toLocaleString('ru-RU');
const pr = n => n.toLocaleString('ru-RU',{minimumFractionDigits:1,maximumFractionDigits:1}) + '%';
const den = d => d.slice(8,10) + '.' + d.slice(5,7);
const sv = D.svod_vse, sp = D.svod_pod, sd = D.svod_dom;

document.getElementById('podzag').textContent =
  `Окно ${den(D.okno.start)}–${den(D.okno.konec)}, ${D.okno.dney} дней · передано ${ch(sv.vzyato)} сайтов · `
  + `после передачи ${ch(sv.reg_posle)} регистраций и ${ch(sv.fd_posle)} депозита`;

function sob(c) {
  return [c.reg ? c.reg + ' рег' : '', c.fd ? c.fd + ' фд' : ''].filter(Boolean).join(', ');
}
function stroki(karta, zagolovok, chuzhie) {
  const sp2 = Object.entries(karta).sort((a,b) =>
    (b[1].reg_posle + b[1].fd_posle) - (a[1].reg_posle + a[1].fd_posle)
    || a[1].peredan.localeCompare(b[1].peredan) || a[0].localeCompare(b[0]));
  const it = sp2.reduce((s,[,o]) => ({rp:s.rp+o.reg_posle, fp:s.fp+o.fd_posle,
    rd:s.rd+o.reg_do, fd:s.fd+o.fd_do}), {rp:0,fp:0,rd:0,fd:0});
  return `<div class="karta tablica-obertka"><table>
    <thead><tr><th>Сайт</th><th class="num">Передан</th><th class="num">Триггер</th>
      <th>Что было триггером</th><th class="num">Дней после передачи</th>
      <th class="num">Рег после</th><th class="num">ФД после</th>
      <th>Даты конверсий после передачи</th>
      <th class="num">Темп до</th><th class="num">Темп после</th></tr></thead>
    <tbody>${sp2.map(([s,o]) => {
      const n = o.reg_posle + o.fd_posle;
      return `<tr${n ? ' style="background:var(--surface-2)"' : ''}>
      <td class="sait">${s}</td>
      <td class="num">${den(o.peredan)}</td>
      <td class="num">${o.trigger ? den(o.trigger)
        : (chuzhie ? '<span style="color:var(--ink-3)">нет данных</span>'
                   : '<b style="color:var(--nash)">нет</b>')}</td>
      <td style="text-align:left;font-size:12.5px;color:var(--ink-2)">${sob(o.trigger_sob) || '—'}</td>
      <td class="num">${ch(o.dney_posle)}</td>
      <td class="num">${o.reg_posle ? '<b>' + ch(o.reg_posle) + '</b>' : '—'}</td>
      <td class="num">${o.fd_posle ? '<b style="color:var(--nash)">' + ch(o.fd_posle) + '</b>' : '—'}</td>
      <td class="daty">${Object.entries(o.posle).map(([d,c]) => den(d) + ' — ' + sob(c)).join(' · ') || '—'}</td>
      <td class="num">${o.temp_do !== null && o.temp_do !== undefined ? o.temp_do.toLocaleString('ru-RU') : '—'}</td>
      <td class="num">${o.temp_posle ? o.temp_posle.toLocaleString('ru-RU') : '—'}</td></tr>`;}).join('')}
      <tr class="itogo"><td>${zagolovok}: ${ch(sp2.length)}</td><td></td><td></td>
        <td>триггеров: ${ch(it.rd)} рег, ${ch(it.fd)} фд</td><td></td>
        <td class="num">${ch(it.rp)}</td><td class="num">${ch(it.fp)}</td><td></td><td></td><td></td></tr>
    </tbody></table></div>`;
}

const maxд = Math.max(...Object.values(D.po_dnyam).map(v => Math.max(v.peredano, v.reg + v.fd)));

document.getElementById('telo').innerHTML = `
<section>
  <h2>Что получилось</h2>
  <p class="vvod">Сайт ставился на крутку после того, как сам давал конверсию — она здесь
     названа <b>триггером</b> и в результат не идёт. Результат крутки — только конверсии
     строго после даты передачи. Поэтому цифры ниже меньше, чем общее число конверсий
     по этим сайтам: большая часть приходится на день передачи и раньше.</p>
  <div class="plitki">
    <div class="plitka"><span class="ch">${ch(sv.vzyato)}</span><div class="pd">сайтов передано в работу</div></div>
    <div class="plitka a"><span class="ch">${ch(sv.srabotali)}</span><div class="pd">дали конверсию после передачи — ${pr(sv.uspeh)}</div></div>
    <div class="plitka"><span class="ch">${ch(sv.reg_posle)}</span><div class="pd">регистраций после передачи</div></div>
    <div class="plitka n"><span class="ch">${ch(sv.fd_posle)}</span><div class="pd">депозитов после передачи</div></div>
    <div class="plitka"><span class="ch">${ch(sv.reg_do + sv.fd_do)}</span><div class="pd">конверсий-триггеров, в результат не идут</div></div>
    <div class="plitka"><span class="ch">${D.okno.dney}</span><div class="pd">дней работы, ${den(D.okno.start)}–${den(D.okno.konec)}</div></div>
  </div>
</section>

<section>
  <h2><span class="nomer">01</span>Поддомены против доменов</h2>
  <div class="karta tablica-obertka"><table>
    <thead><tr><th>Тип</th><th class="num">Передано</th><th class="num">Сработали после передачи</th>
      <th class="num">Успешность</th><th class="num">Рег после</th><th class="num">ФД после</th>
      <th class="num">Конверсий после на сайт</th><th class="num">Было до передачи</th></tr></thead>
    <tbody>
      ${[['Поддомены (наши доры)', sp], ['Домены (брендовые)', sd]].map(([imya, s]) => `<tr>
        <td>${imya}</td><td class="num">${ch(s.vzyato)}</td><td class="num">${ch(s.srabotali)}</td>
        <td class="num"><b>${pr(s.uspeh)}</b></td>
        <td class="num">${ch(s.reg_posle)}</td>
        <td class="num">${s.fd_posle ? '<b style="color:var(--nash)">' + ch(s.fd_posle) + '</b>' : '0'}</td>
        <td class="num">${((s.reg_posle + s.fd_posle) / s.vzyato).toFixed(2)}</td>
        <td class="num">${ch(s.reg_do)} рег, ${ch(s.fd_do)} фд</td></tr>`).join('')}
      <tr class="itogo"><td>Всего</td><td class="num">${ch(sv.vzyato)}</td>
        <td class="num">${ch(sv.srabotali)}</td><td class="num">${pr(sv.uspeh)}</td>
        <td class="num">${ch(sv.reg_posle)}</td><td class="num">${ch(sv.fd_posle)}</td>
        <td class="num">${((sv.reg_posle + sv.fd_posle) / sv.vzyato).toFixed(2)}</td>
        <td class="num">${ch(sv.reg_do)} рег, ${ch(sv.fd_do)} фд</td></tr>
    </tbody></table></div>
  <p class="vvod" style="margin-top:12px">Ни один поддомен не дал депозита после передачи —
     все ${ch(sp.fd_do)} депозита по поддоменам были до постановки на крутку. Оба депозита
     после передачи пришли с одного домена.</p>
</section>

<section>
  <h2><span class="nomer">02</span>По дням: передавали и получали</h2>
  <div class="karta"><div class="legenda">
    <span><span class="tochka" style="background:var(--ink-3)"></span>передано сайтов</span>
    <span><span class="tochka" style="background:var(--accent)"></span>регистрации после передачи</span>
    <span><span class="tochka" style="background:var(--nash)"></span>депозиты после передачи</span>
  </div><div class="polosy">
    ${Object.entries(D.po_dnyam).map(([d,v]) => `
      <div class="ryad"><div class="nazv">${den(d)}</div>
        <div class="zhelob">
          <span class="fill" style="width:${v.peredano / maxд * 60}%;background:var(--ink-3)"></span>
          <span class="fill" style="width:${v.reg / maxд * 60}%;background:var(--accent);border-radius:0"></span>
          <span class="fill" style="width:${v.fd / maxд * 60}%;background:var(--nash)"></span>
        </div>
        <div class="chis">передано <b>${ch(v.peredano)}</b> · рег <b>${ch(v.reg)}</b> · фд <b>${ch(v.fd)}</b></div>
      </div>`).join('')}
  </div></div>
</section>

<section>
  <h2><span class="nomer">03</span>Все поддомены — ${ch(sp.vzyato)} штук</h2>
  <p class="vvod">Полный список. «Триггер» — конверсия, после которой сайт отдали в работу.
     «Темп» — конверсий в сутки до передачи и после неё: по нему видно, ускорился сайт или нет.</p>
  ${stroki(D.pod, 'Поддомены')}
</section>

<section>
  <h2><span class="nomer">04</span>Все домены — ${ch(sd.vzyato)} штук</h2>
  <p class="vvod">По чужим доменам трекер данных не отдаёт: видно только те конверсии,
     что были в отчёте исполнителей. Поэтому у большинства в колонке «триггер» стоит
     «нет данных», а не «не было конверсии».</p>
  ${stroki(D.dom, 'Домены', true)}
</section>

<section>
  <h2><span class="nomer">05</span>По брендам</h2>
  <div class="karta tablica-obertka"><table>
    <thead><tr><th>Бренд</th><th class="num">Доменов</th><th class="num">Поддоменов</th>
      <th class="num">Всего сайтов</th><th class="num">Конверсий после передачи</th></tr></thead>
    <tbody>${Object.entries(D.brendy).map(([b,v]) => `<tr>
      <td>${b}</td><td class="num">${v.dom || '—'}</td><td class="num">${v.pod || '—'}</td>
      <td class="num"><b>${ch(v.dom + v.pod)}</b></td>
      <td class="num">${v.posle ? '<b>' + ch(v.posle) + '</b>' : '—'}</td></tr>`).join('')}
    </tbody></table></div>
</section>

<div class="vyvod">
  <h3>Итог</h3>
  <ul>
    <li><b>Из ${ch(sv.vzyato)} переданных сайтов после постановки на крутку сработали ${ch(sv.srabotali)} — ${pr(sv.uspeh)}.</b>
        Они дали ${ch(sv.reg_posle)} регистраций и ${ch(sv.fd_posle)} депозита за ${D.okno.dney} дней.</li>
    <li><b>Поддомены и домены сработали одинаково:</b> ${pr(sp.uspeh)} против ${pr(sd.uspeh)}.
        Разрыв, который был виден без учёта даты передачи, целиком объяснялся триггерными
        конверсиями — теми, за которые сайт и попал в работу.</li>
    <li><b>Депозитов после крутки почти нет.</b> ${ch(sv.fd_posle)} на ${ch(sv.reg_posle)} регистраций,
        и оба с одного домена <span style="font-family:var(--mono)">dripslots777wins.buzz</span>.
        По поддоменам — ни одного.</li>
    <li><b>Больше половины результата — один сайт.</b>
        <span style="font-family:var(--mono)">leon.2663.lol</span> дал
        ${ch(D.pod['leon.2663.lol'].reg_posle)} регистраций из ${ch(sv.reg_posle)}.
        Но он конвертил и до крутки: темп ${D.pod['leon.2663.lol'].temp_do} конверсии в сутки до передачи
        против ${D.pod['leon.2663.lol'].temp_posle} после. Прирост есть, но сайт не был пустым.</li>
    <li><b>${ch(sp.bez_trigger.length)} поддоменов попали в работу без конверсии-триггера.</b>
        По данным трекера у них до передачи конверсий не было вовсе:
        <span style="font-family:var(--mono);font-size:12px">${sp.bez_trigger.join(', ')}</span>.
        Либо их брали по другому признаку, либо конверсия была отнесена к другому сайту.
        Один из них, <span style="font-family:var(--mono)">vodka.3393.lol</span>, после передачи
        дал ${ch(D.pod['vodka.3393.lol'].reg_posle)} регистрации.</li>
  </ul>
</div>`;
</script>
'''
open(VYHOD, 'w', encoding='utf-8').write(
    SHABLON.replace('__DANNYE__', json.dumps(D, ensure_ascii=False)))
print(f'-> {VYHOD}')

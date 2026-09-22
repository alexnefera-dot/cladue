# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ryadom import para, STRANICY

S = os.path.dirname(os.path.abspath(__file__))
KON = os.path.join(S, 'new100x')
NASH = '/home/user/cladue/samples/v5-final'

PARY = [
    ('obychnaya', 'Обычная манера', os.path.join(KON,'beef-4'), os.path.join(NASH,'nabor-679'),
     'конкурент beef-4', 'наш набор 679'),
    ('gustaya', 'Густая манера, вариант с брендом в заголовках', os.path.join(KON,'atom-2'), os.path.join(NASH,'nabor-674'),
     'конкурент atom-2', 'наш набор 674'),
    ('gustaya2', 'Густая манера, основной вариант', os.path.join(KON,'trix'), os.path.join(NASH,'nabor-674'),
     'конкурент trix', 'наш набор 674'),
]

SVODKA = '''
<table class="svod">
<thead><tr><th>параметр</th><th>корпус NEW100<br><span>обычные, 82 набора</span></th><th>наш 679</th>
<th>корпус NEW100<br><span>густые, 18 наборов</span></th><th>наш 674</th></tr></thead>
<tbody>
<tr><td>бренд-переменных на страницу</td><td>2.4 <span>(0.5–6.7)</span></td><td class="ok">2.3</td><td>16.2 <span>(8.4–28.0)</span></td><td class="miss">8.2</td></tr>
<tr><td>доля латиницы в бренде</td><td>0 % <span>(3 набора из 82 &gt;0)</span></td><td class="ok">0 %</td><td>34.7 % <span>(0–79.8)</span></td><td class="ok">26.3 %</td></tr>
<tr><td>бренд в h2</td><td>6.7 % <span>(2.3–34.0)</span></td><td class="ok">6.5 %</td><td>1.1 % <span>(у 13 из 18 ровно 1.1 %)</span></td><td class="miss">46.0 %</td></tr>
<tr><td>слов на странице, медиана</td><td>1618 <span>(102–2196)</span></td><td class="ok">1598</td><td>1186 <span>(682–1627)</span></td><td class="miss">1555</td></tr>
<tr><td>слов в абзаце, медиана</td><td>47.0 <span>(14.2–64.8)</span></td><td class="ok">43.0</td><td>17.9 <span>(17.6–47.6)</span></td><td class="miss">41.1</td></tr>
<tr><td>ссылок на страницу, медиана</td><td>44.5 <span>(3–77)</span></td><td class="ok">42.5</td><td>12.0 <span>(6.5–74)</span></td><td class="miss">45.0</td></tr>
<tr><td>h3 на страницу, медиана</td><td>9.5 <span>(2–33)</span></td><td class="ok">10.0</td><td>4.2 <span>(2–31.5)</span></td><td class="miss">9.5</td></tr>
<tr><td>доля густых наборов в корпусе</td><td colspan="4">18 из 100 (18 %). В прошлом корпусе было 29 из 102 (28 %), у нас в партии 671–680 — 3 из 10.</td></tr>
</tbody></table>'''

CSS = '''
:root{--bg:#fbfaf8;--fg:#1c1b19;--mut:#6f6b64;--line:#e2ded6;--card:#fff;--acc:#8a5a2b;--br:#ffe9a8;--l:#f6f2ec;--r:#eef4f7}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15140f;--fg:#ece8e1;--mut:#9b958b;--line:#332f28;--card:#1d1b16;--acc:#d8a76a;--br:#5a4a17;--l:#1a1915;--r:#15191d}}
:root[data-theme=dark]{--bg:#15140f;--fg:#ece8e1;--mut:#9b958b;--line:#332f28;--card:#1d1b16;--acc:#d8a76a;--br:#5a4a17;--l:#1a1915;--r:#15191d}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 Georgia,"Times New Roman",serif}
.wrap{max-width:1500px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--mut);font-size:14px;margin-bottom:24px}
h2.pair{font-size:20px;margin:40px 0 8px;padding-top:12px;border-top:2px solid var(--acc)}
.note{color:var(--mut);font-size:14px;margin:0 0 16px}
table{border-collapse:collapse;width:100%;font:14px/1.5 system-ui,sans-serif}
th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
th{background:var(--l);font-weight:600}
td span,th span{color:var(--mut);font-size:12px;font-weight:400}
.ok{color:#2f7a44}.miss{color:#a8442a;font-weight:600}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .ok{color:#7fc494}:root:not([data-theme=light]) .miss{color:#e59178}}
.svod{margin-bottom:8px}
nav{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 0;z-index:5;font:13px system-ui,sans-serif}
nav a{color:var(--acc);text-decoration:none;margin-right:12px;white-space:nowrap}
.page{margin:28px 0}
.ph{font-size:17px;margin:0 0 6px;color:var(--acc);font-family:system-ui,sans-serif}
.met{margin-bottom:10px;font-family:system-ui,sans-serif}
.met summary{cursor:pointer;color:var(--mut);font-size:13px}
.met table{margin-top:6px;max-width:560px}
.dual{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.col{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:14px 16px;overflow-wrap:anywhere}
.col.left{background:var(--l)}.col.right{background:var(--r)}
.colhead{font:12px/1.4 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);
  border-bottom:1px solid var(--line);padding-bottom:6px;margin-bottom:10px}
.b{margin:0 0 9px}
.b.h2{font-size:18px;font-weight:700;margin:18px 0 8px;line-height:1.3}
.b.h3{font-size:15px;font-weight:700;margin:14px 0 6px;font-family:system-ui,sans-serif}
.b.h4{font-size:14px;font-weight:700;margin:12px 0 5px;font-family:system-ui,sans-serif}
.b.li{margin-left:18px;list-style:disc;display:list-item;font-size:15px}
.b.figcaption{font-size:13px;color:var(--mut)}
mark.br{background:var(--br);color:inherit;padding:0 2px;border-radius:2px}
.b .a{color:var(--acc);border-bottom:1px solid color-mix(in srgb,var(--acc) 45%,transparent)}
.legend{font:13px system-ui,sans-serif;color:var(--mut);margin:10px 0 0}
.legend .a{color:var(--acc);border-bottom:1px solid var(--acc)}
@media (max-width:820px){.dual{grid-template-columns:1fr}.wrap{padding:16px}}
'''

blocks = []
nav = []
for kod, imya, kd, nd, kn, nn in PARY:
    nav.append('<a href="#%s">%s</a>' % (kod, imya))
    blocks.append('<h2 class="pair" id="%s">%s — %s против %s</h2>' % (kod, imya, kn, nn))
    if kod == 'gustaya':
        blocks.append('<p class="note">atom-2 выбран потому, что это один из пяти густых наборов конкурента, '
                      'которые ставят бренд в заголовки (48 % h2). Остальные тринадцать густых бренд в h2 почти '
                      'не ставят — ровно 1.1 %, то есть один заголовок на набор.</p>')
    elif kod == 'gustaya2':
        blocks.append('<p class="note">trix — как густой набор выглядит у конкурента на самом деле: '
                      'вдвое короче обычного набора (1186 слов против 1630), двенадцать ссылок на страницу '
                      'вместо сорока пяти, абзацы по восемнадцать слов вместо сорока семи, вчетверо меньше h3. '
                      'Наш 674 по всем этим параметрам остался обычным набором и отличается от 679 только '
                      'числом брендов. Справа та же наша страница, что и в предыдущей паре.</p>')
    else:
        blocks.append('<p class="note">beef-4 подобран как близнец нашего 679 по профилю: '
                      '2.4 бренда на страницу против наших 2.3, 6.1 % бренда в h2 против 6.5 %, '
                      '1596 слов против 1598. Расхождения в тексте — это язык, а не структура.</p>')
    blocks.append(para(kod, kd, nd, kn, nn))

html = '''<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Вычитка рядом</title>
<style>%s</style></head><body><div class="wrap">
<h1>Вычитка рядом: NEW100 против наших наборов</h1>
<p class="sub">Слева страница конкурента из свежей сотни, справа наша страница того же типа.
Бренд-переменные подсвечены. Метрики каждой страницы — под её заголовком.</p>
%s
<p class="legend"><mark class="br">%%brand_name_ru%%</mark> — бренд-переменная, <span class="a">подчёркнутое</span> — ссылка.</p>
<nav>%s</nav>
%s
</div></body></html>''' % (CSS, SVODKA, ' '.join(nav), '\n'.join(blocks))

out = os.path.join(S, 'vychitka-ryadom.html')
open(out, 'w', encoding='utf-8').write(html)
print(out, len(html))

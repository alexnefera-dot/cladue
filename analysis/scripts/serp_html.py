#!/usr/bin/env python3
"""HTML-отчёт «где наши в выдаче» по результату serp_nashi.py.

    python3 serp_html.py <serp.json> <out.html>
"""
import sys, json, html, collections, datetime as dt

inp, out_p = sys.argv[1:3]
D = json.load(open(inp, encoding='utf-8'))
Q = D['queries']
BR = [('Pinco', ('пинко', 'pinco')), ('Leon', ('леон', 'leon')), ('Banda', ('банда', 'banda')),
      ('Leebet', ('либет', 'leebet')), ('Apex', ('apex',)), ('Twin', ('твин', 'twin')), ('Trix', ('трикс', 'trix'))]
today = dt.date.fromisoformat(D['scrape'][:10])


def brand(q):
    for b, keys in BR:
        if any(k in q.lower() for k in keys):
            return b
    return 'Прочее'


e = html.escape
groups = collections.OrderedDict()
for q, items in Q.items():
    groups.setdefault(brand(q), []).append((q, sorted(items, key=lambda x: x['pos'])))
ours = [it for items in Q.values() for it in items if it['who']]
qwith = sum(1 for items in Q.values() if any(it['who'] for it in items))
top3 = sum(1 for it in ours if it['pos'] <= 3)
best = min((it['pos'] for it in ours), default=None)


def age(it):
    if not it.get('launch'):
        return ''
    return (today - dt.date.fromisoformat(it['launch'])).days


def zone(h):
    return h.rsplit('.', 1)[-1]


def cell(it):
    if not it['who']:
        return f'<td class="c"><span class="h">{e(it["host"])}</span></td>'
    a = age(it)
    return (f'<td class="c our"><span class="h">{e(it["host"])}</span>'
            f'<span class="m">{e(it.get("launch","")[8:10]+"."+it.get("launch","")[5:7]) if it.get("launch") else "дата ?"}'
            f'{" · "+str(a)+" дн." if a != "" else ""}</span></td>')


sec = []
for b, qs in groups.items():
    n_our = sum(1 for _, items in qs for it in items if it['who'])
    q_our = sum(1 for _, items in qs if any(it['who'] for it in items))
    rows = []
    for q, items in qs:
        by = {it['pos']: it for it in items}
        cells = ''.join(cell(by[p]) if p in by else '<td class="c"></td>' for p in range(1, 11))
        k = sum(1 for it in items if it['who'])
        rows.append(f'<tr><th class="q">{e(q)}<span class="k{" z" if not k else ""}">{k} наш.</span></th>{cells}</tr>')
    sec.append(f'''<section class="br" id="{e(b.lower())}">
<div class="bh"><h2>{e(b)}</h2><span>{q_our} из {len(qs)} запросов с нашими · {n_our} позиций в топ-10</span></div>
<div class="tw"><table><thead><tr><th class="q">запрос</th>{"".join(f"<th>{p}</th>" for p in range(1, 11))}</tr></thead>
<tbody>{"".join(rows)}</tbody></table></div></section>''')

# список наших сайтов
S = collections.OrderedDict()
for it in sorted(ours, key=lambda x: (x['pos'], x['host'])):
    s = S.setdefault(it['host'], dict(it=it, hits=[]))
    s['hits'].append((it['pos'], it['query']))
site_rows = []
for h, s in sorted(S.items(), key=lambda kv: (min(p for p, _ in kv[1]['hits']), -len(kv[1]['hits']))):
    it = s['it']
    hits = ', '.join(f'<b>{p}</b> «{e(q)}»' for p, q in sorted(s['hits']))
    a = age(it)
    site_rows.append(f'<tr><td class="h">{e(h)}</td><td><span class="chip z-{zone(h)}">.{zone(h)}</span></td>'
                     f'<td class="num">{e(it.get("launch","") or "—")}</td><td class="num">{a if a != "" else "—"}</td>'
                     f'<td class="ct">{e(it.get("content","") or "—")}</td><td class="num">{min(p for p,_ in s["hits"])}</td>'
                     f'<td class="hits">{hits}</td></tr>')

# по дню запуска и зоне
by_day = collections.Counter(it.get('launch', '') or '?' for it in ours)
by_zone = collections.Counter(zone(it['host']) for it in ours)
chips_day = ''.join(f'<span class="pill"><b class="num">{v}</b> {e(k[8:10]+"."+k[5:7]) if k!="?" else "дата ?"}</span>' for k, v in sorted(by_day.items(), reverse=True))
chips_zone = ''.join(f'<span class="pill"><b class="num">{v}</b> .{e(k)}</span>' for k, v in by_zone.most_common())

page = f'''<title>Наши в выдаче {today.strftime("%d.%m")}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--bg:#f5f7f7;--panel:#fff;--ink:#15201f;--muted:#5d6b6a;--line:#dde4e3;--soft:#eef3f2;--our:#dff3e6;--ourb:#1c7c3c;--accent:#0f6e6e;
--z-casino:#9a3b52;--z-team:#2c5f9e;--z-lol:#6b7a1f;--z-buzz:#8a5a12}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#0f1515;--panel:#162020;--ink:#e3ecea;--muted:#94a3a1;--line:#273433;--soft:#1c2828;--our:#17362a;--ourb:#6fd08f;--accent:#5cc2bb;--z-casino:#e08aa0;--z-team:#86b1ea;--z-lol:#c4d36a;--z-buzz:#e0ae62}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#0f1515;--panel:#162020;--ink:#e3ecea;--muted:#94a3a1;--line:#273433;--soft:#1c2828;--our:#17362a;--ourb:#6fd08f;--accent:#5cc2bb;--z-casino:#e08aa0;--z-team:#86b1ea;--z-lol:#c4d36a;--z-buzz:#e0ae62}}
body{{background:var(--bg);color:var(--ink);font:14px/1.45 "IBM Plex Sans",system-ui,sans-serif;padding-inline:16px;padding-block:24px 48px}}
.wrap{{max-width:1320px;margin:0 auto;display:flex;flex-direction:column;gap:22px}}
h1{{font-size:24px;font-weight:600;margin:0;text-wrap:balance}} h2{{font-size:18px;margin:0}}
.sub{{color:var(--muted);margin:4px 0 0;max-width:75ch}}
.num{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.kpi{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}
.kpi div{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}}
.kpi b{{display:block;font-size:22px;font-family:"IBM Plex Mono",monospace}} .kpi span{{color:var(--muted);font-size:12.5px}}
.pills{{display:flex;flex-wrap:wrap;gap:6px;align-items:center}} .pills>span.l{{color:var(--muted);font-size:12.5px;margin-right:4px}}
.pill{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:2px 9px;font-size:12.5px}}
nav{{display:flex;flex-wrap:wrap;gap:8px}} nav a{{color:var(--accent);text-decoration:none;border:1px solid var(--line);background:var(--panel);padding:4px 10px;border-radius:6px}}
nav a:hover{{border-color:var(--accent)}}
.br{{display:flex;flex-direction:column;gap:8px}} .bh{{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline}} .bh span{{color:var(--muted)}}
.tw{{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:8px}}
table{{border-collapse:collapse;width:100%}}
th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}
thead th{{background:var(--soft);font-weight:500;font-size:12px;color:var(--muted);position:sticky;top:0}}
th.q{{min-width:190px;font-weight:500;font-size:13px}} .k{{display:block;font-size:11.5px;color:var(--ourb);font-weight:600}} .k.z{{color:var(--muted);font-weight:400}}
td.c{{min-width:118px;max-width:150px;font-size:11.5px;color:var(--muted);overflow-wrap:anywhere}}
td.our{{background:var(--our);color:var(--ink);box-shadow:inset 3px 0 0 var(--ourb)}}
td.our .h{{font-weight:600;display:block}} td .m{{display:block;color:var(--ourb);font-size:11px}}
.list td{{font-size:13px}} .list td.h{{font-weight:600;overflow-wrap:anywhere}} .list td.ct{{overflow-wrap:anywhere;color:var(--muted)}} .list td.hits{{min-width:260px}}
.chip{{display:inline-block;padding:0 7px;border-radius:10px;font-size:12px;border:1px solid currentColor}}
.z-casino{{color:var(--z-casino)}}.z-team{{color:var(--z-team)}}.z-lol{{color:var(--z-lol)}}.z-buzz{{color:var(--z-buzz)}}
</style>
<div class="wrap">
<header><h1>Наши сайты в выдаче Яндекса, {today.strftime("%d.%m.%Y")}</h1>
<p class="sub">Снимок топ-10 от {e(D["scrape"][11:16])} по {len(Q)} запросам ({len(groups)} брендов). Наш сайт — если его базовый домен есть в реестре запусков (выгрузка dorgen по 24.09 включительно, {D["bases"]} баз). Зелёная ячейка — наш сайт, под ним дата запуска и возраст.</p></header>
<div class="kpi">
<div><b>{len(ours)}</b><span>наших позиций в топ-10 из {sum(len(v) for v in Q.values())}</span></div>
<div><b>{qwith} / {len(Q)}</b><span>запросов, где есть хотя бы один наш</span></div>
<div><b>{len(S)}</b><span>разных наших сайтов в выдаче</span></div>
<div><b>{top3}</b><span>наших в топ-3 · лучшая позиция {best if best else "—"}</span></div>
</div>
<div class="pills"><span class="l">По дню запуска:</span>{chips_day}</div>
<div class="pills"><span class="l">По зоне:</span>{chips_zone}</div>
<nav>{"".join(f'<a href="#{e(b.lower())}">{e(b)}</a>' for b in groups)}<a href="#spisok">Список наших сайтов</a></nav>
{"".join(sec)}
<section class="br" id="spisok"><div class="bh"><h2>Все наши сайты в выдаче</h2><span>по лучшей позиции</span></div>
<div class="tw list"><table><thead><tr><th>сайт</th><th>зона</th><th>запуск</th><th>дней</th><th>контент</th><th>лучшая</th><th>позиции по запросам</th></tr></thead>
<tbody>{"".join(site_rows)}</tbody></table></div></section>
</div>'''
open(out_p, 'w', encoding='utf-8').write(page)
print('ok', len(ours), len(S))

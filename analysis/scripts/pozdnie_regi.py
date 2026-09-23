#!/usr/bin/env python3
"""Поздние деньги: сколько рег/ФД приходит с сайтов старше N суток и что
потеряем, если удалять сайты на 10-е сутки (всё подряд или только без кликов на 7–10).

Берутся рег/ФД 01–21.09: панель плотная с 18.08, поэтому сайт вне панели с первым
поисковым кликом до 17.08 точно старше 14 суток («старый сток»). Остальные сайты
вне панели — «возраст неизвестен», мусорные subdomain — отдельно.

    python3 pozdnie_regi.py <panel.jsonl> <kliki_dni.jsonl> <out.txt> <out.csv> <конверсии...>
"""
import sys, json, csv, collections, datetime as dt

panel_p, kliki_p, out_p, csv_p = sys.argv[1:5]
conv_ps = sys.argv[5:]
D0 = dt.date(2026, 7, 1)


def dn(s):
    return (dt.date.fromisoformat(s[:10]) - D0).days


out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


site = {}
for line in open(panel_p, encoding='utf-8'):
    r = json.loads(line)
    if r.get('recrawl_sent_at'):
        site[r['subdomain'].lower()] = (dn(r['recrawl_sent_at']), r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН',
                                        r['recrawl_sent_at'][:10])
clk = {}
for line in open(kliki_p, encoding='utf-8'):
    s, dd = json.loads(line)
    clk[s] = {dn(d): c for d, c in dd.items()}

seen = set(); ev = []
for p in conv_ps:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r['event'] not in ('reg', 'fd') or not ('2026-09-01' <= r['at'][:10] <= '2026-09-21'):
            continue
        seen.add(k)
        ev.append((r['at'], r['event'], (r.get('subdomain') or '').lower()))
ev.sort()
P(f'Рег и ФД с 01.09 по 21.09 (без дублей): рег {sum(e=="reg" for _,e,_ in ev)}, ФД {sum(e=="fd" for _,e,_ in ev)}')


def bucket(a):
    return '0–3' if a <= 3 else '4–6' if a <= 6 else '7–9' if a <= 9 else '10–13' if a <= 13 else \
        '14–20' if a <= 20 else '21–30' if a <= 30 else '31+'


B = collections.Counter(); late = []
for at, e, s in ev:
    d = dn(at)
    if s in site:
        a = d - site[s][0]
        b = bucket(a) if a >= 0 else '0–3'
    elif s.count('.') != 2:
        b = 'мусор в subdomain'; a = None
    elif s in clk and min(clk[s]) <= dn('2026-08-17'):
        b = 'старый сток (в поиске до 18.08)'; a = None
    else:
        b = 'вне панели, возраст неизвестен'; a = None
    B[(b, e)] += 1
    if b == 'старый сток (в поиске до 18.08)' or (a is not None and a >= 10):
        c = clk.get(s, {})
        L = site[s][0] if s in site else None
        c710 = sum(x for dd, x in c.items() if L is not None and 7 <= dd - L <= 10)
        late.append(dict(at=at[:16].replace('T', ' '), event=e, site=s,
                         launch=site[s][2] if s in site else 'до 11.08',
                         age=a if a is not None else '', content=site[s][1] if s in site else '',
                         clicks_7_10=c710 if L is not None else '',
                         clicks_all=sum(c.values())))
treg = sum(B[k] for k in B if k[1] == 'reg'); tfd = sum(B[k] for k in B if k[1] == 'fd')
P(f'\n{"возраст сайта, сут.":<24} {"рег":>5} {"% рег":>6} {"ФД":>4} {"% ФД":>6}')
for b in ['0–3', '4–6', '7–9', '10–13', '14–20', '21–30', '31+', 'старый сток (в поиске до 18.08)',
          'вне панели, возраст неизвестен', 'мусор в subdomain']:
    P(f'{b:<24} {B[(b,"reg")]:>5} {100*B[(b,"reg")]/treg:>5.1f}% {B[(b,"fd")]:>4} {100*B[(b,"fd")]/tfd:>5.1f}%')

pan_late = [x for x in late if x['age'] != '']
P(f'\nСайты из панели, рег/ФД на 10+ сутки: событий {len(pan_late)}, разных сайтов {len({x["site"] for x in pan_late})}')
nz = [x for x in pan_late if x['clicks_7_10'] == 0]
P(f'   из них у сайта НЕ было поисковых кликов на 7–10 сутки: {len(nz)} событий '
  f'(рег {sum(x["event"]=="reg" for x in nz)}, ФД {sum(x["event"]=="fd" for x in nz)})')

# во что обходится хранение: сколько сайтов живы к 10-м суткам
alive = tot = 0
for s, (L, _, _) in site.items():
    if L <= dn('2026-09-12'):
        tot += 1
        if any(7 <= d - L <= 10 for d in clk.get(s, {})):
            alive += 1
P(f'\nСайты с переобходом до 12.09: {tot}; с кликом на 7–10 сутки: {alive} ({100*alive/tot:.1f}%).')

with open(csv_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['at', 'event', 'site', 'launch', 'age', 'content', 'clicks_7_10', 'clicks_all'])
    w.writeheader(); w.writerows(late)
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

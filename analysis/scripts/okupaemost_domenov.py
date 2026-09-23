#!/usr/bin/env python3
"""Окупаемость по каждому домену (базе): затраты = цена домена по зоне, доход = ФД × $40.

Индекс домена = доля его сайтов (брендов) с поисковым кликом за сутки 0–3 от переобхода.
Запуски 01–19.09, деньги по 22.09.

    python3 okupaemost_domenov.py <panel.jsonl> <boty.json> <out.txt> <out.csv> <конверсии...>
"""
import sys, json, csv, re, collections, datetime as dt

panel_p, boty_p, out_p, csv_p = sys.argv[1:5]
conv_ps = sys.argv[5:]
PRICE = {'casino': 7, 'team': 2, 'lol': 1, 'buzz': 3}
FD_USD = 40
LO, HI = '2026-09-01', '2026-09-19'
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


first = json.load(open(boty_p))['first']
site = {}
D = {}
for line in open(panel_p, encoding='utf-8'):
    r = json.loads(line)
    rc = r.get('recrawl_sent_at')
    if not (rc and LO <= rc[:10] <= HI):
        continue
    b = r['content_domain_url']
    s = r['subdomain'].lower()
    site[s] = b
    d = D.setdefault(b, dict(domain=b, zone=r['tld'], launch=rc[:10],
                             content=r.get('content_label') or r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН',
                             sites=0, idx=0, reg=0, fd=0, brands_fd=[]))
    d['sites'] += 1
    f = first.get(s)
    if f and f[1]:
        t0 = dt.datetime.fromisoformat(rc); t1 = dt.datetime.fromisoformat(f[1])
        if t0 - dt.timedelta(hours=1) <= t1 < t0 + dt.timedelta(days=4):
            d['idx'] += 1
seen = set()
for p in conv_ps:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen:
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        if s in site:
            d = D[site[s]]
            if r['event'] == 'reg':
                d['reg'] += 1
            elif r['event'] == 'fd':
                d['fd'] += 1; d['brands_fd'].append(s.split('.')[0])
fd_rate = sum(d['fd'] for d in D.values()) / sum(d['reg'] for d in D.values())
for d in D.values():
    d['index'] = round(100 * d['idx'] / d['sites'], 1)
    d['cost'] = PRICE.get(d['zone'], 0)
    d['profit'] = d['fd'] * FD_USD - d['cost']
    d['profit_exp'] = round(d['reg'] * fd_rate * FD_USD - d['cost'], 2)
    d['brands_fd'] = ' '.join(d['brands_fd'])
L = list(D.values())
tc = sum(d['cost'] for d in L); ti = sum(d['fd'] for d in L) * FD_USD
win = [d for d in L if d['profit'] > 0]
P(f'Доменов {len(L)}, затраты ${tc}, доход ${ti}, итог ${ti-tc:+}. Доля ФД от рег {fd_rate:.3f}.')
P(f'Окупились (есть хоть один ФД): {len(win)} доменов = {100*len(win)/len(L):.1f}%. '
  f'Их прибыль ${sum(d["profit"] for d in win)}; остальные {len(L)-len(win)} доменов: '
  f'${sum(d["profit"] for d in L if d["profit"]<=0)}.')
wr = [d for d in L if d['reg'] > 0]
P(f'С регистрацией: {len(wr)} доменов ({100*len(wr)/len(L):.1f}%), без единой рег: {len(L)-len(wr)}.')

P('\nПо индексу домена (что было бы, если запускать только такие):')
P(f'{"индекс домена":<14} {"доменов":>7} {"с рег":>6} {"окупилось":>10} {"рег":>5} {"ФД":>4} {"затраты":>8} {"доход":>6} '
  f'{"на домен":>9} {"на домен ожид.":>15}')
for lo, hi in [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 40), (40, 101)]:
    g = [d for d in L if lo <= d['index'] < hi]
    if not g:
        continue
    c = sum(d['cost'] for d in g); f = sum(d['fd'] for d in g); rg = sum(d['reg'] for d in g)
    P(f'{f"{lo}–{hi if hi<101 else 100}%":<14} {len(g):>7} {sum(d["reg"]>0 for d in g):>6} '
      f'{sum(d["profit"]>0 for d in g):>5} {100*sum(d["profit"]>0 for d in g)/len(g):>3.0f}% {rg:>5} {f:>4} '
      f'{c:>8} {f*FD_USD:>6} {(f*FD_USD-c)/len(g):>+9.2f} {(rg*fd_rate*FD_USD-c)/len(g):>+15.2f}')
P('\nПо зоне и индексу (на домен ожид.):')
for z in ('lol', 'team', 'buzz', 'casino'):
    row = []
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 101)]:
        g = [d for d in L if d['zone'] == z and lo <= d['index'] < hi]
        if g:
            rg = sum(d['reg'] for d in g)
            row.append(f'{lo}–{hi if hi<101 else 100}%: {len(g)} дом. {(rg*fd_rate*FD_USD-sum(d["cost"] for d in g))/len(g):+.2f}')
    P(f'   .{z:<7} ' + ' | '.join(row))

win.sort(key=lambda d: (-d['fd'], -d['reg']))
P(f'\nВсе {len(win)} окупившихся доменов:')
P(f'{"домен":<22} {"зона":<7} {"запуск":<11} {"контент":<48} {"индекс":>7} {"рег":>4} {"ФД":>3} {"прибыль":>8}  бренды ФД')
for d in win:
    P(f'{d["domain"]:<22} {d["zone"]:<7} {d["launch"]:<11} {d["content"]:<48} {d["index"]:>6.1f}% {d["reg"]:>4} '
      f'{d["fd"]:>3} {d["profit"]:>+8}  {d["brands_fd"]}')
keys = ['domain', 'zone', 'launch', 'content', 'sites', 'index', 'reg', 'fd', 'cost', 'profit', 'profit_exp', 'brands_fd']
with open(csv_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore'); w.writeheader()
    w.writerows(sorted(L, key=lambda d: (-d['profit'], -d['reg'])))
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

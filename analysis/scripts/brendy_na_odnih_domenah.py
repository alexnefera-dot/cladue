#!/usr/bin/env python3
"""Бренды на одних и тех же доменах: естественный эксперимент.

Система ставит каждый бренд на один и тот же набор доменов с одним контентом,
поэтому домен и текст держатся постоянными сами собой, и разница в кликах — это
чистый эффект бренда. Считает по каждому бренду клики за день наблюдения,
регистрации и ФД за всё время и корреляцию между трафиком и деньгами.

    python3 brendy_na_odnih_domenah.py <день кликов> <out.txt> --subs ... --clicks ... --conv ...
"""
import sys, json, collections

day, out_p = sys.argv[1:3]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[3:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


brand = {}; launch = collections.Counter()
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = r['subdomain'].lower(); b = r.get('brand_label')
        if s in brand or not b:
            continue
        brand[s] = b
        if r.get('recrawl_sent_at'):
            launch[b] += 1
seen = set(); conv = collections.defaultdict(collections.Counter)
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r['event'] not in ('reg', 'fd') or r.get('campaign') != 'dorgen_engine':
            continue
        seen.add(k)
        b = brand.get((r.get('subdomain') or '').lower())
        if b:
            conv[b][r['event']] += 1
clicks = collections.Counter()
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot') or r['at'][:10] != day:
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        b = brand.get((r.get('subdomain') or '').lower())
        if b:
            clicks[b] += 1

bs = [b for b in launch if launch[b] >= 2000]      # только бренды с полным охватом


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); rk = [0] * len(v); i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            rk[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return rk


def spear(x, y):
    rx, ry = rank(x), rank(y); n = len(x)
    mx = sum(rx) / n; my = sum(ry) / n
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** .5
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / den if den else 0


cl = [clicks[b] for b in bs]; rg = [conv[b]['reg'] for b in bs]; fd = [conv[b]['fd'] for b in bs]
P(f'Брендов {len(bs)}, у каждого 2000+ запущенных сайтов. Клики за {day}.')
P(f'Спирмен клики ↔ регистрации: {spear(cl, rg):+.2f}; клики ↔ ФД: {spear(cl, fd):+.2f}; '
  f'регистрации ↔ ФД: {spear(rg, fd):+.2f}')
tc = sum(cl) or 1; tr = sum(rg) or 1
for name, key in (('трафику', lambda b: -clicks[b]), ('регистрациям', lambda b: -conv[b]['reg'])):
    t = sorted(bs, key=key)[:10]
    P(f'топ-10 по {name}: {100*sum(clicks[b] for b in t)/tc:.0f}% кликов, '
      f'{100*sum(conv[b]["reg"] for b in t)/tr:.0f}% регистраций')
P(f'\n{"бренд":<22} {"запущено":>9} {"кликов":>8} {"рег":>5} {"ФД":>4} {"рег на 1000 сайтов":>19}')
for b in sorted(bs, key=lambda b: -clicks[b]):
    P(f'{b[:22]:<22} {launch[b]:>9} {clicks[b]:>8} {conv[b]["reg"]:>5} {conv[b]["fd"]:>4} '
      f'{1000*conv[b]["reg"]/launch[b]:>19.2f}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

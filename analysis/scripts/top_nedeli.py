#!/usr/bin/env python3
"""Лучшие домены недели по регистрациям — кандидаты на повтор.

Исключаются тексты (content_label с номером экземпляра), которые уже стояли на двух и более
доменах, то есть уже повторялись. Индекс — доля сайтов с поисковым кликом за 72 ч от переобхода
(пусто, если 72 ч ещё не прошли).

    python3 top_nedeli.py <с> <конец кликов ISO> <out.csv> --subs ... --panel ... --clicks ... --conv ...
"""
import sys, json, csv, collections, datetime as dt

lo, end_s, out_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
T = dt.datetime.fromisoformat
END = T(end_s)

site = {}
for p in opt['subs']:  # свежие файлы — первыми
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('pipeline_started') or '')[:10]
        s = r['subdomain'].lower()
        if d < lo or s in site:
            continue
        site[s] = dict(d=d, b=r['content_domain_url'], c=r.get('content_label') or '?', rc=r.get('recrawl_sent_at'))
used = collections.defaultdict(set)
for line in open(opt['panel'][0], encoding='utf-8'):
    r = json.loads(line)
    if r.get('content_label'):
        used[r['content_label']].add(r['content_domain_url'])
for v in site.values():
    used[v['c']].add(v['b'])
first = {}
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s in site and (s not in first or r['at'] < first[s]):
            first[s] = r['at']
B = collections.defaultdict(lambda: dict(n=0, h=0, reg=0, fd=0))
for s, v in site.items():
    b = B[v['b']]; b.update(d=v['d'], c=v['c'])
    if v['rc'] and T(v['rc']) + dt.timedelta(hours=72) <= END:
        b['n'] += 1
        f = first.get(s)
        if f and T(v['rc']) - dt.timedelta(hours=1) <= T(f) < T(v['rc']) + dt.timedelta(hours=72):
            b['h'] += 1
seen = set()
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r.get('campaign') != 'dorgen_engine' or r['event'] not in ('reg', 'fd'):
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        if s in site:
            B[site[s]['b']]['reg' if r['event'] == 'reg' else 'fd'] += 1
rows = []
for b, x in B.items():
    if x['reg'] > 0:
        rows.append(dict(content=x['c'], domain=b, launch=x['d'], index72=round(100 * x['h'] / x['n'], 1) if x['n'] else '',
                         reg=x['reg'], fd=x['fd'], already_repeated='да' if len(used[x['c']]) > 1 else ''))
rows.sort(key=lambda r: (r['already_repeated'] != '', -r['fd'], -r['reg']))
with open(out_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in rows:
    print('|'.join(str(r[k]) for k in r))

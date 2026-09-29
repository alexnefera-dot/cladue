#!/usr/bin/env python3
"""Когда у свежего домена обвалились поисковые клики.

По каждому домену, запущенному в заданном окне: клики из поиска по суткам от переобхода
(сутки 0 — первые 24 часа). «Пик» — самые высокие сутки, «обвал» — первые сутки после пика,
где кликов меньше четверти пика. Сравнение — с нормой сентября (та же мера на запусках
первой половины месяца).

    python3 obval_domenov.py <с> <по> <конец кликов ISO> <out.csv> --subs ... --clicks ... --panel ...
"""
import sys, json, csv, collections, datetime as dt

lo, hi, end_s, out_p = sys.argv[1:5]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[5:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
T = dt.datetime.fromisoformat
END = T(end_s)

site = {}
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('pipeline_started') or '')[:10]
        s = r['subdomain'].lower()
        if not (lo <= d <= hi) or s in site or not r.get('recrawl_sent_at'):
            continue
        site[s] = (r['content_domain_url'], T(r['recrawl_sent_at']), r.get('content_label') or '?')
for p in opt['panel']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('pipeline_started') or '')[:10]
        s = r['subdomain'].lower()
        if not (lo <= d <= hi) or s in site or not r.get('recrawl_sent_at'):
            continue
        site[s] = (r['content_domain_url'], T(r['recrawl_sent_at']), r.get('content_label') or '?')

# клики по суткам жизни домена
D = collections.defaultdict(collections.Counter)   # база -> сутки -> клики
meta = {}
for s, (b, rc, c) in site.items():
    if b not in meta or rc < meta[b][0]:
        meta[b] = (rc, c)
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        v = site.get(s)
        if not v:
            continue
        age = int((T(r['at']) - v[1]).total_seconds() // 86400)
        if age >= 0:
            D[v[0]][age] += 1

rows = []
for b, (rc, c) in meta.items():
    obs = int((END - rc).total_seconds() // 86400)      # сколько полных суток прожил домен
    if obs < 1:
        continue
    cur_d = D[b]
    series = [cur_d.get(a, 0) for a in range(obs)]
    tot = sum(series)
    if tot < 20:
        state = 'почти без кликов'
        peak = peak_day = drop = ''
    else:
        peak = max(series); peak_day = series.index(peak)
        drop = ''
        for a in range(peak_day + 1, obs):
            if series[a] < peak * 0.25:
                drop = a
                break
        last = series[-1]
        state = 'обвал' if drop != '' else ('держится' if last >= peak * 0.5 else 'снижается')
    rows.append(dict(domain=b, content=c, recrawl=rc.strftime('%d.%m %H:%M'), days=obs, clicks=tot,
                     peak=peak, peak_day=peak_day, drop_day=drop, state=state,
                     series=' '.join(str(x) for x in series)))
rows.sort(key=lambda r: (r['recrawl'], -r['clicks']))
with open(out_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# сводка
print(f'Доменов {len(rows)}, кликов {sum(r["clicks"] for r in rows)}. Клики до {END:%d.%m %H:%M}.')
st = collections.Counter(r['state'] for r in rows)
print('состояние:', dict(st))
live = [r for r in rows if r['peak'] != '']
if live:
    pk = collections.Counter(r['peak_day'] for r in live)
    print('сутки пика:', dict(sorted(pk.items())))
    dr = collections.Counter(r['drop_day'] for r in live if r['drop_day'] != '')
    print('сутки обвала (ниже четверти пика):', dict(sorted(dr.items())))
byday = collections.defaultdict(list)
for r in live:
    byday[r['recrawl'][:5]].append(r)
print(f'\n{"переобход":>10} {"доменов":>8} {"кликов на домен":>16} {"пик, сутки":>11} {"обвал, сутки":>13} {"обвалилось":>11}')
for d in sorted(byday):
    g = byday[d]
    dd = [r['drop_day'] for r in g if r['drop_day'] != '']
    print(f'{d:>10} {len(g):>8} {sum(r["clicks"] for r in g)/len(g):>16.0f} '
          f'{sum(r["peak_day"] for r in g)/len(g):>11.1f} {(sum(dd)/len(dd) if dd else 0):>13.1f} {len(dd):>11}')

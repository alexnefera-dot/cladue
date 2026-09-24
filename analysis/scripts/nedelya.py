#!/usr/bin/env python3
"""Статистика недели: запуски, выход в поиск, регистрации и ФД.

Запуски недели — сайты с pipeline_started в [с, по]. Индекс — доля сайтов с живым
поисковым кликом (реферер Яндекса, не бот) после переобхода; «за сутки» — в первые
24 часа, «на сейчас» — за всё время до конца выгрузки кликов.
Конверсии — только кампания dorgen_engine, без дублей (clickid+event+at).

    python3 nedelya.py <с> <по> <out.json> --subs <реестр.jsonl ...> --clicks <клики.jsonl ...>
        --conv <конверсии.jsonl ...> --panel <panel.jsonl>
"""
import sys, json, re, collections, datetime as dt

lo, hi, out_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)

site = {}
for p in opt['subs']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d = (r.get('pipeline_started') or '')[:10]
        if not (lo <= d <= hi):
            continue
        s = r['subdomain'].lower()
        if s in site:
            continue
        b = r['content_domain_url']
        site[s] = dict(day=d, base=b, zone=b.rsplit('.', 1)[1], rc=r.get('recrawl_sent_at'),
                       content=r.get('content_label') or r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН')
first = {}
last_click = ''
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = (r.get('subdomain') or '').lower()
        if r['at'] > last_click:
            last_click = r['at']
        if s not in site or r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        if s not in first or r['at'] < first[s]:
            first[s] = r['at']
old = set()
for line in open(opt['panel'][0], encoding='utf-8'):
    old.add(json.loads(line)['subdomain'].lower())
seen = set(); conv = []
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r['event'] not in ('reg', 'fd') or r.get('campaign') != 'dorgen_engine':
            continue
        seen.add(k); conv.append(r)
last_conv = max(r['at'] for r in conv)


def t(s):
    return dt.datetime.fromisoformat(s)


def cohort_key(v, how):
    if how == 'day':
        return v['day']
    if how == 'zone':
        return v['zone']
    return re.sub(r'_\d+$', '', v['content'])


def cohorts(how):
    C = collections.OrderedDict()
    for s, v in sorted(site.items(), key=lambda kv: kv[1]['day']):
        c = C.setdefault(cohort_key(v, how), dict(sites=0, bases=set(), rc=0, i1=0, inow=0, reg=0, fd=0, zones=collections.Counter()))
        c['sites'] += 1; c['bases'].add(v['base']); c['zones'][v['zone']] += 0
        if v['rc']:
            c['rc'] += 1
            f = first.get(s)
            if f and t(f) >= t(v['rc']) - dt.timedelta(hours=1):
                c['inow'] += 1
                if t(f) < t(v['rc']) + dt.timedelta(days=1):
                    c['i1'] += 1
    for r in conv:
        s = (r.get('subdomain') or '').lower()
        if s in site:
            c = C[cohort_key(site[s], how)]
            c['reg' if r['event'] == 'reg' else 'fd'] += 1
    out = []
    for k, c in C.items():
        zb = collections.Counter(b.rsplit('.', 1)[1] for b in c['bases'])
        out.append(dict(key=k, domains=len(c['bases']), sites=c['sites'], recrawled=c['rc'], i1=c['i1'], inow=c['inow'],
                        reg=c['reg'], fd=c['fd'], zones=dict(zb)))
    return out


daily = collections.defaultdict(lambda: collections.Counter())
for r in conv:
    d = r['at'][:10]
    s = (r.get('subdomain') or '').lower()
    src = 'week' if s in site else ('prev' if s in old else 'stock')
    daily[d][r['event']] += 1
    daily[d][r['event'] + '_' + src] += 1
res = dict(lo=lo, hi=hi, last_click=last_click, last_conv=last_conv,
           by_day=cohorts('day'), by_zone=cohorts('zone'), by_content=cohorts('content'),
           daily={d: dict(c) for d, c in sorted(daily.items())})
json.dump(res, open(out_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for x in res['by_day']:
    print(x)
print('клики до', last_click, 'конверсии до', last_conv)

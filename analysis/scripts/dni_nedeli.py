#!/usr/bin/env python3
"""Есть ли удачные дни недели: по дню запуска и по дню конверсии.

Часть 1. День запуска: индекс за 24 ч (доля сайтов с живым поисковым кликом от переобхода),
регистрации и ФД за 72 ч. Поправка на тренд: индекс делится на скользящее среднее ±3 дня,
иначе ранний сентябрь (когда всё было лучше) перетянет те дни недели, на которые он попал.

Часть 2. День конверсии: сколько рег и ФД приходит по дням недели, нормировано на живые
поисковые клики того дня.

    python3 dni_nedeli.py <с> <по> <out.txt> --subs ... --panel ... --clicks ... --conv ...
"""
import sys, json, collections, datetime as dt

lo, hi, out_p = sys.argv[1:4]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[4:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
T = dt.datetime.fromisoformat
DOW = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


site = {}
for p in opt['subs'] + opt['panel']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        s = r['subdomain'].lower()
        rc = r.get('recrawl_sent_at')
        if s in site or not rc or not (lo <= rc[:10] <= hi):
            continue
        site[s] = (r['content_domain_url'], T(rc), rc[:10])
first = {}
for p in opt['first']:
    for s, f in json.load(open(p))['first'].items():
        if f[1]:
            first[s] = f[1]
END = ''
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r['at'] > END:
            END = r['at']
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        s = (r.get('subdomain') or '').lower()
        if s in site and (s not in first or r['at'] < first[s]):
            first[s] = r['at']
ENDT = T(END)
seen = set(); conv = collections.defaultdict(list); conv_day = collections.defaultdict(collections.Counter)
for p in opt['conv']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen or r['event'] not in ('reg', 'fd') or r.get('campaign') != 'dorgen_engine':
            continue
        seen.add(k)
        conv[(r.get('subdomain') or '').lower()].append((r['at'], r['event']))
        conv_day[r['at'][:10]][r['event']] += 1

# ---------- часть 1: день запуска ----------
by_day = collections.defaultdict(lambda: [0, 0, 0, 0, 0])   # день -> [вышло, сайтов, доменов, рег, фд]
for s, (b, rc, d) in site.items():
    if rc + dt.timedelta(hours=24) > ENDT:
        continue
    g = by_day[d]
    g[1] += 1
    f = first.get(s)
    if f and rc - dt.timedelta(hours=1) <= T(f) < rc + dt.timedelta(hours=24):
        g[0] += 1
    for at, e in conv.get(s, []):
        if T(at) < rc + dt.timedelta(hours=72):
            g[3 if e == 'reg' else 4] += 1
for b, ss in collections.Counter(site[s][0] for s in site).items():
    pass
dom = collections.defaultdict(set)
for s, (b, rc, d) in site.items():
    dom[d].add(b)
days = sorted(d for d in by_day if by_day[d][1])
idx = {d: 100 * by_day[d][0] / by_day[d][1] for d in days}
# скользящее среднее ±3 дня
sm = {}
for i, d in enumerate(days):
    w = [idx[x] for x in days[max(0, i - 3):i + 4]]
    sm[d] = sum(w) / len(w)
P(f'Дни {days[0]}–{days[-1]}, кликов до {ENDT:%d.%m %H:%M}.')
P('\n=== 1. День запуска (день переобхода) ===')
P(f'{"дата":<12} {"день":<13} {"доменов":>7} {"индекс 24ч":>11} {"к тренду":>9} {"рег":>5} {"ФД":>4} {"рег/домен":>10}')
for d in days:
    g = by_day[d]; nd = len(dom[d]); w = DOW[dt.date.fromisoformat(d).weekday()]
    P(f'{d:<12} {w:<13} {nd:>7} {idx[d]:>10.1f}% {idx[d]/sm[d]:>9.2f} {g[3]:>5} {g[4]:>4} {g[3]/nd:>10.2f}')
W = collections.defaultdict(lambda: [0, 0, 0, 0, 0, 0.0, 0])  # вышло, сайтов, доменов, рег, фд, сумма_к_тренду, дней
for d in days:
    g = by_day[d]; w = dt.date.fromisoformat(d).weekday()
    x = W[w]
    x[0] += g[0]; x[1] += g[1]; x[2] += len(dom[d]); x[3] += g[3]; x[4] += g[4]
    x[5] += idx[d] / sm[d]; x[6] += 1
P(f'\n{"день недели":<13} {"дней":>5} {"доменов":>8} {"индекс 24ч":>11} {"к тренду":>9} {"рег":>5} {"ФД":>4} {"рег/домен":>10} {"ФД/домен":>9}')
for w in range(7):
    x = W[w]
    if not x[6]:
        continue
    P(f'{DOW[w]:<13} {x[6]:>5} {x[2]:>8} {100*x[0]/x[1]:>10.1f}% {x[5]/x[6]:>9.2f} {x[3]:>5} {x[4]:>4} {x[3]/x[2]:>10.3f} {x[4]/x[2]:>9.3f}')

# ---------- часть 2: день конверсии ----------
P('\n=== 2. День конверсии (когда пришли деньги) ===')
cl = collections.Counter()
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        if (r.get('subdomain') or '').count('.') == 2:
            cl[r['at'][:10]] += 1
C = collections.defaultdict(lambda: [0, 0, 0, 0])   # дней, рег, фд, клики
for d in sorted(set(conv_day) | set(cl)):
    if not (lo <= d <= hi) or not cl.get(d):
        continue
    w = dt.date.fromisoformat(d).weekday()
    x = C[w]; x[0] += 1; x[1] += conv_day[d]['reg']; x[2] += conv_day[d]['fd']; x[3] += cl[d]
P(f'{"день недели":<13} {"дней":>5} {"рег":>5} {"ФД":>4} {"живых кликов":>13} {"рег на 10тыс":>13} {"ФД на 10тыс":>12}')
for w in range(7):
    x = C[w]
    if not x[0]:
        continue
    P(f'{DOW[w]:<13} {x[0]:>5} {x[1]:>5} {x[2]:>4} {x[3]:>13} {10000*x[1]/x[3]:>13.2f} {10000*x[2]/x[3]:>12.2f}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

#!/usr/bin/env python3
"""Сколько доменов мертвы по трафику: ни один сайт домена не дал живого поискового
клика за окно наблюдения.

Домен = база вида `9253.lol`, на ней 150–206 сайтов вида `бренд.база.зона`. Домен
считается живым, если хотя бы один его сайт получил живой клик с Яндекса в окне.
Окон несколько, потому что «мёртв» зависит от того, за сколько дней смотреть.

    python3 mertvye_domeny.py <последний день> <out.txt> --kesh ... --clicks ...
"""
import sys, csv, json, collections, datetime as dt

last, out_p = sys.argv[1:3]
opt = collections.defaultdict(list); cur = None
for a in sys.argv[3:]:
    if a.startswith('--'):
        cur = a[2:]
    else:
        opt[cur].append(a)
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


D = dt.date.fromisoformat(last)
WIN = {'1 день': 1, '3 дня': 3, '7 дней': 7, '14 дней': 14}
days = {k: {(D - dt.timedelta(days=i)).isoformat() for i in range(n)} for k, n in WIN.items()}

dom = collections.defaultdict(lambda: dict(n=0, z=None, first=None, last=None))
sub2dom = {}
with open(opt['kesh'][0], encoding='utf-8') as f:
    for r in csv.DictReader(f, delimiter='\t'):
        if not r['recrawl']:
            continue
        b = r['base']; g = dom[b]
        g['n'] += 1; g['z'] = r['tld']
        d = r['recrawl'][:10]
        if not g['first'] or d < g['first']:
            g['first'] = d
        if not g['last'] or d > g['last']:
            g['last'] = d
        sub2dom[r['subdomain']] = b

hit = collections.defaultdict(set)      # домен -> дни, когда были живые клики
for p in opt['clicks']:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        if r.get('is_bot'):
            continue
        h = r.get('referer') or ''
        if 'yandex' not in h and 'ya.ru' not in h:
            continue
        b = sub2dom.get((r.get('subdomain') or '').lower())
        if b:
            hit[b].add(r['at'][:10])

P(f'Домены с отправленным переобходом: {len(dom)}, сайтов на них {sum(g["n"] for g in dom.values())}.')
P(f'Окна считаются назад от {last} включительно. Живой = хотя бы один сайт домена')
P('дал живой поисковый клик в окне.\n')
P(f'{"окно":<10} {"мёртвых доменов":>17} {"доля":>7} {"сайтов на них":>15} {"живых доменов":>15}')
for k in WIN:
    dead = [b for b in dom if not (hit.get(b, set()) & days[k])]
    ds = sum(dom[b]['n'] for b in dead)
    P(f'{k:<10} {len(dead):>17} {100*len(dead)/len(dom):>6.1f}% {ds:>15} {len(dom)-len(dead):>15}')

# разрез по возрасту и зоне, окно 7 дней
k = '7 дней'
P(f'\nРазрез по месяцу запуска, окно {k}:')
P(f'{"месяц":<10} {"доменов":>8} {"мёртвых":>9} {"доля":>7} {"сайтов мёртвых":>16}')
M = collections.defaultdict(lambda: [0, 0, 0])
for b, g in dom.items():
    m = (g['first'] or '?')[:7]
    x = M[m]; x[0] += 1
    if not (hit.get(b, set()) & days[k]):
        x[1] += 1; x[2] += g['n']
for m in sorted(M):
    x = M[m]
    P(f'{m:<10} {x[0]:>8} {x[1]:>9} {100*x[1]/x[0]:>6.1f}% {x[2]:>16}')
P(f'\nРазрез по зоне, окно {k}:')
P(f'{"зона":<10} {"доменов":>8} {"мёртвых":>9} {"доля":>7}')
Z = collections.defaultdict(lambda: [0, 0])
for b, g in dom.items():
    x = Z[g['z'] or '?']; x[0] += 1
    if not (hit.get(b, set()) & days[k]):
        x[1] += 1
for z in sorted(Z, key=lambda z: -Z[z][0]):
    x = Z[z]
    P(f'.{z:<9} {x[0]:>8} {x[1]:>9} {100*x[1]/x[0]:>6.1f}%')
# сколько домен прожил: от первого переобхода до последнего дня с кликом
P(f'\nСрок жизни домена (от переобхода до последнего дня с живым кликом):')
life = collections.Counter()
for b, g in dom.items():
    hs = hit.get(b)
    if not hs or not g['first']:
        life['ни одного клика'] += 1
        continue
    d0 = dt.date.fromisoformat(g['first']); d1 = dt.date.fromisoformat(max(hs))
    n = (d1 - d0).days
    life['0–1 сутки' if n <= 1 else '2–3 суток' if n <= 3 else '4–7 суток' if n <= 7
         else '8–14 суток' if n <= 14 else 'больше 14 суток'] += 1
for k2 in ('ни одного клика', '0–1 сутки', '2–3 суток', '4–7 суток', '8–14 суток', 'больше 14 суток'):
    if life[k2]:
        P(f'   {k2:<20} {life[k2]:>6} ({100*life[k2]/len(dom):>4.1f}%)')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

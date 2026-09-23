#!/usr/bin/env python3
"""Пункт 5: не завышают ли боты индекс. Пункт 7: окупаемость наборов контента.

Индекс набора = доля сайтов с поисковым кликом за сутки 0–3 от переобхода, в четырёх
вариантах (из proverka_botov.py). Окупаемость: запуск = домен (база) × 206 брендов,
затраты = цена домена по зоне, доход = ФД × $40. Набор = имя контента без номера
экземпляра в конце (_N). Цены аккаунта и генерации контента
не учтены.

    python3 boty_i_okupaemost.py <panel.jsonl> <boty.json> <out.txt> <out.csv> <конверсии...>
"""
import sys, json, csv, math, re, collections, datetime as dt

panel_p, boty_p, out_p, csv_p = sys.argv[1:5]
conv_ps = sys.argv[5:]
PRICE = {'casino': 7, 'team': 2, 'lol': 1, 'buzz': 3}
FD_USD = 40
LO, HI = '2026-09-01', '2026-09-19'
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def t(s):
    return dt.datetime.fromisoformat(s)


B = json.load(open(boty_p))
first = B['first']

P('=== 5. Боты и индекс ===')
P('Клики на наших сайтах, сентябрь:')
agg = collections.Counter()
for f, bot, ya, n in B['stat']:
    agg[(bot, ya)] += n
tot = sum(agg.values())
P(f'   без реферера Яндекса: люди {agg[(False,False)]:>9}, боты {agg[(True,False)]:>9}')
P(f'   с реферером Яндекса:  люди {agg[(False,True)]:>9}, боты {agg[(True,True)]:>9}  '
  f'→ ботов среди поисковых {100*agg[(True,True)]/(agg[(True,True)]+agg[(False,True)]):.2f}%')
P('   по выгрузкам (доля ботов среди поисковых):')
byf = collections.defaultdict(collections.Counter)
for f, bot, ya, n in B['stat']:
    if ya:
        byf[f][bot] += n
for f in sorted(byf):
    P(f'     {f:<46} {100*byf[f][True]/sum(byf[f].values()):5.2f}%')
cs = B['country']; ct = sum(n for _, n in cs)
P('   страны поисковых кликов (не боты): ' + ', '.join(f'{c} {100*n/ct:.1f}%' for c, n in cs[:10]))

site = {}
for line in open(panel_p, encoding='utf-8'):
    r = json.loads(line)
    rc = r.get('recrawl_sent_at')
    if rc and LO <= rc[:10] <= HI:
        site[r['subdomain'].lower()] = dict(rc=t(rc), content=re.sub(r'_\d+$', '', r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН'),
                                            base=r['content_domain_url'], tld=r['tld'])
seen = set(); reg = collections.Counter(); fd = collections.Counter(); cconv = collections.Counter()
for p in conv_ps:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen:
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        if s in site:
            if r['event'] == 'reg':
                reg[s] += 1; cconv[r.get('country') or '?'] += 1
            elif r['event'] == 'fd':
                fd[s] += 1
cc = sum(cconv.values())
P('   страны регистраций: ' + ', '.join(f'{c} {100*n/cc:.1f}%' for c, n in cconv.most_common(8)))

VAR = ['любой клик, с ботами', 'не бот (как сейчас)', 'не бот из СНГ', '2+ клика не бот']
G = collections.defaultdict(lambda: dict(n=0, idx=[0, 0, 0, 0], reg=0, fd=0, bases=set(), tld=collections.Counter()))
for s, v in site.items():
    g = G[v['content']]
    g['n'] += 1; g['reg'] += reg[s]; g['fd'] += fd[s]
    g['bases'].add(v['base']); g['tld'][v['tld']] += 1
    f = first.get(s)
    if f:
        for i in range(4):
            if f[i] and (t(f[i]) - v['rc']).total_seconds() <= 4 * 86400 - 1 and t(f[i]) >= v['rc'] - dt.timedelta(hours=1):
                g['idx'][i] += 1
sets = [k for k, g in G.items() if g['n'] >= 400 and k != 'КОНТЕНТ НЕ ЗАПИСАН']


def rank(v):
    o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for j, i in enumerate(o): r[i] = j
    return r


def spear(a, b):
    ra, rb = rank(a), rank(b); n = len(a); m = (n - 1) / 2
    return sum((x - m) * (y - m) for x, y in zip(ra, rb)) / math.sqrt(sum((x - m) ** 2 for x in ra) * sum((y - m) ** 2 for y in rb))


ix = [[G[k]['idx'][i] / G[k]['n'] for k in sets] for i in range(4)]
totn = sum(G[k]['n'] for k in sets)
P(f'\nИндекс по {len(sets)} наборам (запуски {LO}–{HI}, сутки 0–3), в среднем по всем сайтам:')
for i in range(4):
    P(f'   {VAR[i]:<24} {100*sum(G[k]["idx"][i] for k in sets)/totn:5.2f}%   '
      f'Спирмен с текущим: {spear(ix[i], ix[1]):.3f}')
regs_ = [G[k]['reg'] / G[k]['n'] for k in sets]
for i in range(4):
    P(f'   Спирмен «{VAR[i]}» ↔ рег на сайт: {spear(ix[i], regs_):.3f}')
P('\nНаборы, у которых индекс сильнее всего меняется при фильтре «СНГ» и «2+ клика»:')
P(f'{"набор":<44} {"сайтов":>6} {"сейчас":>7} {"СНГ":>6} {"2+":>6} {"место сейчас→СНГ→2+":>22}')
r1 = rank([-x for x in ix[1]]); r2 = rank([-x for x in ix[2]]); r3 = rank([-x for x in ix[3]])
order = sorted(range(len(sets)), key=lambda j: -max(abs(r1[j] - r2[j]), abs(r1[j] - r3[j])))
for j in order[:12]:
    k = sets[j]
    P(f'{k:<44} {G[k]["n"]:>6} {100*ix[1][j]:>6.1f}% {100*ix[2][j]:>5.1f}% {100*ix[3][j]:>5.1f}% '
      f'{r1[j]+1:>8}→{r2[j]+1}→{r3[j]+1}')

# ---------- 7. окупаемость ----------
P('\n=== 7. Окупаемость наборов (запуски 01–19.09, деньги по 22.09) ===')
fd_rate = sum(G[k]['fd'] for k in G) / max(1, sum(G[k]['reg'] for k in G))
P(f'Цена домена: ' + ', '.join(f'.{z} ${p}' for z, p in PRICE.items()) + f'; ФД ${FD_USD}. '
  f'Доля ФД от рег по сети {fd_rate:.3f} → рег стоит в среднем ${fd_rate*FD_USD:.2f}.')
P('Цена аккаунта и генерации контента НЕ учтены. Доход «ожид.» = рег × доля ФД × $40 (сглаживает случай).')
rows = []
for k, g in G.items():
    nb = len(g['bases'])
    if nb < 3:
        continue
    cost = sum(PRICE.get(z, 0) * c for z, c in g['tld'].items()) / 206  # сайтов/206 = доменов по зонам
    inc = g['fd'] * FD_USD; exp = g['reg'] * fd_rate * FD_USD
    rows.append(dict(content=k, domains=nb, sites=g['n'], index=round(100 * g['idx'][1] / g['n'], 1),
                     reg=g['reg'], fd=g['fd'], cost=round(cost, 1), income=inc, profit=round(inc - cost, 1),
                     profit_exp=round(exp - cost, 1), per_domain=round((inc - cost) / nb, 2),
                     per_domain_exp=round((exp - cost) / nb, 2),
                     cost_per_reg=round(cost / g['reg'], 2) if g['reg'] else '',
                     cost_per_fd=round(cost / g['fd'], 2) if g['fd'] else ''))
rows.sort(key=lambda r: -r['per_domain_exp'])
P(f'{"набор":<44} {"доменов":>7} {"индекс":>7} {"рег":>4} {"ФД":>3} {"затраты":>8} {"доход ФД":>9} '
  f'{"прибыль":>8} {"на домен":>9} {"на домен ожид.":>15} {"$ за рег":>9}')
for r in rows:
    P(f'{r["content"]:<44} {r["domains"]:>7} {r["index"]:>6.1f}% {r["reg"]:>4} {r["fd"]:>3} {r["cost"]:>8.0f} '
      f'{r["income"]:>9} {r["profit"]:>8.0f} {r["per_domain"]:>9.2f} {r["per_domain_exp"]:>15.2f} {str(r["cost_per_reg"]):>9}')
T = {x: sum(r[x] for r in rows) for x in ('domains', 'reg', 'fd', 'cost', 'income')}
P(f'{"ИТОГО":<44} {T["domains"]:>7} {"":>7} {T["reg"]:>4} {T["fd"]:>3} {T["cost"]:>8.0f} {T["income"]:>9} '
  f'{T["income"]-T["cost"]:>8.0f} {(T["income"]-T["cost"])/T["domains"]:>9.2f}')
P('\nПо зоне (все наборы вместе):')
Z = collections.defaultdict(lambda: [0, 0, 0])
for s, v in site.items():
    Z[v['tld']][0] += 1; Z[v['tld']][1] += reg[s]; Z[v['tld']][2] += fd[s]
for z, (n, rg, f) in sorted(Z.items()):
    dom = n / 206; cost = dom * PRICE.get(z, 0)
    P(f'   .{z:<7} доменов {dom:>6.0f}  рег {rg:>4}  ФД {f:>3}  затраты ${cost:>6.0f}  доход ${f*FD_USD:>5}  '
      f'на домен ${(f*FD_USD-cost)/dom:+.2f} (ожид. ${(rg*fd_rate*FD_USD-cost)/dom:+.2f})')
with open(csv_p, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

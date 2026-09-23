#!/usr/bin/env python3
"""Срок жизни сайта и насыщение бренда.

Вход: панель сайтов (panel.py), суточный ряд поисковых кликов (kliki_po_dnyam.py),
выгрузки конверсий трекера (перекрываются — дедупликация по clickid+event+at).

    python3 zhizn_i_brendy.py <panel.jsonl> <kliki_dni.jsonl> <out.txt> <конверсии...>

Часть 1. Жизнь сайта: кривая кликов по возрасту от переобхода (с проверкой на
выбросы), когда сайт умирает (последний поисковый клик), в каком возрасте
приходят деньги, какие наборы контента живут дольше.

Часть 2. Насыщение бренда: когда бренду запускают много новых сайтов, теряют ли
клики его старые сайты (возраст 7+ суток). Бренд × день, фиксированные эффекты
бренда и дня, ошибки кластеризованы по бренду; плацебо — будущие запуски.
"""
import sys, json, math, collections, datetime as dt

panel_p, kliki_p, out_p = sys.argv[1:4]
conv_ps = sys.argv[4:]
END = '2026-09-22'
D0 = dt.date(2026, 7, 1)


def dn(s):
    return (dt.date.fromisoformat(s[:10]) - D0).days


def ds(n):
    return (D0 + dt.timedelta(n)).isoformat()


END_N = dn(END)
out = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    out.append(s)


# ---------- данные ----------
site = {}
for line in open(panel_p, encoding='utf-8'):
    r = json.loads(line)
    rc = r.get('recrawl_sent_at')
    if not rc:
        continue
    site[r['subdomain'].lower()] = dict(L=dn(rc), brand=r['brand_label'] or '?',
                                        content=r.get('content') or 'КОНТЕНТ НЕ ЗАПИСАН',
                                        tld=r['tld'])
clk = {}
for line in open(kliki_p, encoding='utf-8'):
    s, dd = json.loads(line)
    if s in site:
        L = site[s]['L']
        clk[s] = {dn(d) - L: c for d, c in dd.items() if dn(d) >= L}
seen = set()
conv = collections.defaultdict(list)  # сайт -> [(возраст, event)]
for p in conv_ps:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        k = (r['clickid'], r['event'], r['at'])
        if k in seen:
            continue
        seen.add(k)
        s = (r.get('subdomain') or '').lower()
        if s in site and r['event'] in ('reg', 'fd'):
            conv[s].append((dn(r['at']) - site[s]['L'], r['event']))
P(f'Сайтов в панели с переобходом: {len(site)}; с поисковым кликом: {len(clk)}; '
  f'конверсий (рег+ФД) на них: {sum(len(v) for v in conv.values())}')
P(f'Наблюдение до {END}. Возраст = сутки от переобхода.')

# ---------- 1a. кривая по возрасту, с выбросами и без ----------
P('\n=== 1a. Клики на сайт по возрасту (все сайты когорты в знаменателе) ===')
AGES = [0, 1, 2, 3, 4, 5, 7, 10, 14, 21, 28, 30, 35, 40]
num = collections.Counter(); den = collections.Counter(); alive = collections.Counter()
per_age = collections.defaultdict(list)
for s, v in site.items():
    obs = END_N - v['L']
    c = clk.get(s, {})
    for a in AGES:
        if a <= obs:
            den[a] += 1
            x = c.get(a, 0)
            num[a] += x
            if x:
                alive[a] += 1
                per_age[a].append(x)
P(f'{"сутки":>6} {"сайтов":>8} {"кликов/сайт":>12} {"без топ-1% сайтов":>18} {"доля с кликом":>14} {"топ-3 сайта, % кликов":>22}')
for a in AGES:
    if not den[a]:
        continue
    xs = sorted(per_age[a], reverse=True)
    cut = max(1, len(xs) // 100)
    trimmed = sum(xs[cut:]) / den[a]
    top3 = 100 * sum(xs[:3]) / max(1, num[a])
    P(f'{a:>6} {den[a]:>8} {num[a]/den[a]:>12.3f} {trimmed:>18.3f} {100*alive[a]/den[a]:>13.2f}% {top3:>21.1f}%')

# ---------- 1b. смерть: последний поисковый клик ----------
P('\n=== 1b. Когда сайт умирает (сайты, получившие хоть один клик) ===')
P('Последний поисковый клик, по когортам с достаточным наблюдением.')
for lo, hi, maxa, lbl in [(dn('2026-08-11'), dn('2026-08-22'), 31, '11–22.08 (наблюдение 31+ сут.)'),
                          (dn('2026-09-01'), dn('2026-09-08'), 14, '01–08.09 (наблюдение 14+ сут.)')]:
    B = collections.Counter(); n = 0
    for s, v in site.items():
        if lo <= v['L'] <= hi and s in clk and clk[s]:
            last = max(clk[s])
            n += 1
            if last <= 3: B['0–3'] += 1
            elif last <= 7: B['4–7'] += 1
            elif last <= 14: B['8–14'] += 1
            elif last <= 30: B['15–30'] += 1
            else: B['31+'] += 1
    P(f'Когорта {lbl}: сайтов с кликом {n}')
    for k in ['0–3', '4–7', '8–14', '15–30', '31+']:
        if k == '31+' and maxa < 31:
            continue
        P(f'   последний клик на сутках {k:>6}: {B[k]:>6}  {100*B[k]/max(1,n):5.1f}%')

P('\nЖив ли сайт сейчас (клик за последние 3 суток, 20–22.09), по неделе запуска:')
wk = collections.defaultdict(lambda: [0, 0, 0])
for s, v in site.items():
    if v['L'] > END_N - 7:
        continue
    w = ds(v['L'] - (dt.date.fromisoformat(ds(v['L'])).weekday()))
    wk[w][0] += 1
    c = clk.get(s, {})
    if c:
        wk[w][1] += 1
        if any(END_N - v['L'] - k <= 2 for k in c):
            wk[w][2] += 1
P(f'{"неделя с":>11} {"сайтов":>8} {"был клик":>9} {"жив сейчас":>11} {"% от кликнувших":>16}')
for w in sorted(wk):
    a, b, c = wk[w]
    P(f'{w:>11} {a:>8} {b:>9} {c:>11} {100*c/max(1,b):>15.1f}%')

# ---------- 1c. деньги по возрасту ----------
P('\n=== 1c. В каком возрасте сайт приносит деньги ===')
for lo, hi, lbl in [(dn('2026-08-11'), dn('2026-08-22'), '11–22.08 (31+ сут.)'),
                    (dn('2026-09-01'), dn('2026-09-08'), '01–08.09 (14+ сут.)')]:
    B = collections.Counter(); tot = collections.Counter()
    for s, v in site.items():
        if lo <= v['L'] <= hi:
            for a, e in conv.get(s, []):
                if a < 0:
                    continue
                k = '0' if a == 0 else '1' if a == 1 else '2' if a == 2 else '3' if a == 3 else \
                    '4–7' if a <= 7 else '8–14' if a <= 14 else '15–30' if a <= 30 else '31+'
                B[(k, e)] += 1; tot[e] += 1
    P(f'Когорта {lbl}: рег {tot["reg"]}, ФД {tot["fd"]}')
    acc = collections.Counter()
    for k in ['0', '1', '2', '3', '4–7', '8–14', '15–30', '31+']:
        if not (B[(k, 'reg')] or B[(k, 'fd')]):
            continue
        acc['reg'] += B[(k, 'reg')]; acc['fd'] += B[(k, 'fd')]
        P(f'   сутки {k:>6}: рег {B[(k,"reg")]:>4} ({100*B[(k,"reg")]/max(1,tot["reg"]):4.1f}%, накоплено {100*acc["reg"]/max(1,tot["reg"]):5.1f}%)'
          f'   ФД {B[(k,"fd")]:>3} ({100*B[(k,"fd")]/max(1,tot["fd"]):4.1f}%, накоплено {100*acc["fd"]/max(1,tot["fd"]):5.1f}%)')

# ---------- 1d. какие наборы живут дольше ----------
P('\n=== 1d. Живучесть по наборам контента (запуски 01–12.09, наблюдение 10+ сут.) ===')
P('индекс = доля сайтов с кликом за сутки 0–3; хвост = доля кликов 4–10 суток от кликов 0–10;')
P('жив на 7–10 = доля вышедших в индекс сайтов, у которых был клик на сутках 7–10.')
G = collections.defaultdict(lambda: dict(n=0, idx=0, c03=0, c410=0, al=0, reg=0, reg4=0, fd=0))
lo, hi = dn('2026-09-01'), dn('2026-09-12')
for s, v in site.items():
    if not (lo <= v['L'] <= hi):
        continue
    g = G[v['content']]
    g['n'] += 1
    c = clk.get(s, {})
    if any(k <= 3 for k in c):
        g['idx'] += 1
        if any(7 <= k <= 10 for k in c):
            g['al'] += 1
    g['c03'] += sum(x for k, x in c.items() if k <= 3)
    g['c410'] += sum(x for k, x in c.items() if 4 <= k <= 10)
    for a, e in conv.get(s, []):
        if e == 'reg':
            g['reg'] += 1
            if a >= 4:
                g['reg4'] += 1
        else:
            g['fd'] += 1
rows = [(k, g) for k, g in G.items() if g['idx'] >= 20]
rows.sort(key=lambda kg: -kg[1]['al'] / kg[1]['idx'])
P(f'{"набор":<44} {"сайтов":>6} {"индекс":>7} {"жив 7–10":>9} {"хвост":>6} {"рег":>4} {"рег с 4 сут.":>12} {"ФД":>3}')
for k, g in rows:
    P(f'{k:<44} {g["n"]:>6} {100*g["idx"]/g["n"]:>6.1f}% {100*g["al"]/g["idx"]:>8.1f}% '
      f'{100*g["c410"]/max(1,g["c03"]+g["c410"]):>5.1f}% {g["reg"]:>4} {g["reg4"]:>12} {g["fd"]:>3}')
tot = {k: sum(g[k] for _, g in rows) for k in ('n', 'idx', 'al', 'c03', 'c410', 'reg', 'reg4', 'fd')}
P(f'{"ИТОГО":<44} {tot["n"]:>6} {100*tot["idx"]/tot["n"]:>6.1f}% {100*tot["al"]/tot["idx"]:>8.1f}% '
  f'{100*tot["c410"]/max(1,tot["c03"]+tot["c410"]):>5.1f}% {tot["reg"]:>4} {tot["reg4"]:>12} {tot["fd"]:>3}')
# связь живучести с индексом по наборам
xs = [g['idx'] / g['n'] for _, g in rows]; ys = [g['al'] / g['idx'] for _, g in rows]


def spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
        for j, i in enumerate(o): r[i] = j
        return r
    ra, rb = rk(a), rk(b); n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return cov / math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))


P(f'Спирмен «индекс набора» ↔ «жив на 7–10»: {spearman(xs, ys):.2f} (наборов {len(rows)})')

# ---------- 2. насыщение бренда ----------
P('\n=== 2. Насыщение бренда: отнимают ли новые сайты клики у старых того же бренда ===')
F0, F1 = dn('2026-08-18'), END_N  # панель плотная с 18.08
launch = collections.defaultdict(collections.Counter)   # бренд -> день -> запущено
for s, v in site.items():
    launch[v['brand']][v['L']] += 1
old_cl = collections.defaultdict(collections.Counter)   # бренд -> день -> клики старых (7+ сут.)
old_n = collections.defaultdict(collections.Counter)    # бренд -> день -> число старых живых сайтов
new_cl = collections.defaultdict(collections.Counter)   # бренд -> день -> клики сайтов 0–3 сут.
for s, c in clk.items():
    v = site[s]; b = v['brand']
    first = min(c) if c else None
    for a, x in c.items():
        d = v['L'] + a
        if a >= 7:
            old_cl[b][d] += x
        elif a <= 3:
            new_cl[b][d] += x
    if first is not None:
        for d in range(max(F0, v['L'] + 7), F1 + 1):
            if d - v['L'] >= first:   # уже был в выдаче к этому дню
                old_n[b][d] += 1
brands = [b for b in launch if sum(launch[b].values()) >= 200]
obs = []  # (бренд, день, y, x_now, x_lead, ctrl)
for b in brands:
    for d in range(F0 + 3, F1 - 3 + 1):
        if old_n[b][d] < 20:
            continue
        x = sum(launch[b][d - k] for k in range(3))
        xl = sum(launch[b][d + k] for k in range(1, 4))
        obs.append((b, d, math.log1p(old_cl[b][d]), math.log1p(x), math.log1p(xl), math.log(old_n[b][d])))
P(f'Брендов: {len(brands)} (200+ сайтов), наблюдений бренд×день: {len(obs)}, дни {ds(F0+3)}–{ds(F1-3)}')


def twoway(vals, keys_a, keys_b, it=50):
    v = list(vals)
    for _ in range(it):
        for keys in (keys_a, keys_b):
            s = collections.defaultdict(float); n = collections.Counter()
            for k, x in zip(keys, v):
                s[k] += x; n[k] += 1
            v = [x - s[k] / n[k] for k, x in zip(keys, v)]
    return v


def ols_cluster(y, X, cl):
    k = len(X)
    XtX = [[sum(X[i][t] * X[j][t] for t in range(len(y))) for j in range(k)] for i in range(k)]
    Xty = [sum(X[i][t] * y[t] for t in range(len(y))) for i in range(k)]
    inv = invert(XtX)
    beta = [sum(inv[i][j] * Xty[j] for j in range(k)) for i in range(k)]
    e = [y[t] - sum(beta[i] * X[i][t] for i in range(k)) for t in range(len(y))]
    S = collections.defaultdict(lambda: [0.0] * k)
    for t in range(len(y)):
        for i in range(k):
            S[cl[t]][i] += X[i][t] * e[t]
    meat = [[sum(S[g][i] * S[g][j] for g in S) for j in range(k)] for i in range(k)]
    G = len(S)
    V = [[sum(inv[i][a] * meat[a][b] * inv[b][j] for a in range(k) for b in range(k)) * G / (G - 1)
          for j in range(k)] for i in range(k)]
    return beta, [math.sqrt(V[i][i]) for i in range(k)]


def invert(M):
    n = len(M); A = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        pv = A[c][c]; A[c] = [x / pv for x in A[c]]
        for r in range(n):
            if r != c:
                f = A[r][c]; A[r] = [x - f * y for x, y in zip(A[r], A[c])]
    return [row[n:] for row in A]


kb = [o[0] for o in obs]; kd = [o[1] for o in obs]
Y = twoway([o[2] for o in obs], kb, kd)
Xn = twoway([o[3] for o in obs], kb, kd)
Xl = twoway([o[4] for o in obs], kb, kd)
Xc = twoway([o[5] for o in obs], kb, kd)
beta, se = ols_cluster(Y, [Xn, Xl, Xc], kb)
P('log(1+клики старых сайтов бренда в день d) ~ log(1+запущено бренду за d-2..d)')
P('   + log(1+запущено за d+1..d+3, плацебо) + log(число старых сайтов в выдаче); FE бренд, день.')
for nm, b_, s_ in zip(['запуски d-2..d', 'плацебо d+1..d+3', 'старых сайтов (контроль)'], beta, se):
    P(f'   {nm:<26} β={b_:+.3f}  ±{1.96*s_:.3f} (95%)  t={b_/s_:+.2f}')
P('   β<0 у «запуски d-2..d» при плацебо≈0 = новые сайты отнимают клики у старых.')

# в человеческих единицах: день с большим запуском против обычного
P('\nТо же без регрессии: клики старых сайтов бренда относительно его собственной медианы,')
P('по размеру запуска бренду за последние 3 дня (к среднему по сети в этот день).')
rel = collections.defaultdict(list)
byd = collections.defaultdict(list)
for o in obs:
    byd[o[1]].append(o)
bm = {}
for b in brands:
    xs_ = sorted(math.expm1(o[2]) / math.exp(o[5]) for o in obs if o[0] == b)
    bm[b] = xs_[len(xs_) // 2] if xs_ else 0
for d, os_ in byd.items():
    r = [(math.expm1(o[2]) / math.exp(o[5])) / bm[o[0]] for o in os_ if bm[o[0]] > 0]
    if not r:
        continue
    net = sorted(r)[len(r) // 2]
    for o in os_:
        if bm[o[0]] > 0 and net > 0:
            x = round(math.expm1(o[3]))
            k = '0' if x == 0 else '1–10' if x <= 10 else '11–30' if x <= 30 else '31–60' if x <= 60 else '61+'
            rel[k].append((math.expm1(o[2]) / math.exp(o[5])) / bm[o[0]] / net)
P(f'{"запущено за 3 дня":>18} {"бренд×дней":>11} {"клики старых, к норме":>22}')
for k in ['0', '1–10', '11–30', '31–60', '61+']:
    v = sorted(rel[k])
    if v:
        P(f'{k:>18} {len(v):>11} {v[len(v)//2]:>21.2f}×')

# потолок бренда: растут ли суммарные клики бренда с числом сайтов в выдаче
P('\nСуммарные клики бренда за день ~ число его сайтов в выдаче (FE бренд, день):')
obs2 = []
for b in brands:
    for d in range(F0 + 3, F1 + 1):
        tot = old_cl[b][d] + new_cl[b][d]
        new_live = sum(launch[b][d - k] for k in range(4))
        if tot > 0 and old_n[b][d] + new_live > 0:
            obs2.append((b, d, math.log(tot), math.log(old_n[b][d] + new_live)))
kb2 = [o[0] for o in obs2]; kd2 = [o[1] for o in obs2]
beta2, se2 = ols_cluster(twoway([o[2] for o in obs2], kb2, kd2), [twoway([o[3] for o in obs2], kb2, kd2)], kb2)
P(f'   эластичность β={beta2[0]:+.3f} ±{1.96*se2[0]:.3f}: 1 = каждый сайт добавляет свои клики,')
P('   0 = спрос бренда фиксирован и просто делится. Наблюдений ' + str(len(obs2)))
P('   Оговорка: число сайтов в выдаче внутри бренда растёт почти как тренд времени, а запуски')
P('   делятся между брендами поровну, поэтому эта оценка плохо определена; опираться на 2b.')

open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

# ---------- 2b. естественный опыт: бренду в день дали вдвое больше сайтов ----------
P('\n=== 2b. Бренду в день дали в 1,5+ раза больше сайтов, чем медиане брендов: хуже ли каждый сайт? ===')
P('Сравнение внутри страты «набор + день + зона»: ожидание = средняя страты, O/E по группам.')
cnt = collections.defaultdict(collections.Counter)
for s, v in site.items():
    cnt[v['L']][v['brand']] += 1
med = {d: sorted(c.values())[len(c) // 2] for d, c in cnt.items()}
strat = collections.defaultdict(list)
for s, v in site.items():
    if v['L'] > END_N - 3 or v['content'] == 'КОНТЕНТ НЕ ЗАПИСАН':
        continue
    k = cnt[v['L']][v['brand']] / med[v['L']]
    grp = 'двойная порция (1,5×+)' if k >= 1.5 else 'меньше медианы (<0,8×)' if k < 0.8 else 'обычная'
    c = clk.get(s, {})
    idx = 1 if any(a <= 3 for a in c) else 0
    cl = sum(x for a, x in c.items() if a <= 3)
    rg = sum(1 for a, e in conv.get(s, []) if e == 'reg' and a <= 3)
    strat[(v['content'], v['L'], v['tld'])].append((grp, idx, cl, rg, v['brand'], v['L']))
O = collections.defaultdict(lambda: [0, 0.0, 0, 0.0, 0, 0.0, 0, set()])
for k, rows_ in strat.items():
    if len({r[0] for r in rows_}) < 2:
        continue
    n = len(rows_)
    mi = sum(r[1] for r in rows_) / n; mc = sum(r[2] for r in rows_) / n; mr = sum(r[3] for r in rows_) / n
    for g, i, c, r, b, d in rows_:
        o = O[g]
        o[0] += i; o[1] += mi; o[2] += c; o[3] += mc; o[4] += r; o[5] += mr; o[6] += 1; o[7].add((b, d))
P(f'{"группа":<26} {"сайтов":>7} {"бренд×дней":>11} {"индекс O/E":>11} {"клики O/E":>10} {"рег O/E":>8} {"рег факт/ожид":>14}')
for g in ['меньше медианы (<0,8×)', 'обычная', 'двойная порция (1,5×+)']:
    o = O[g]
    if o[6]:
        P(f'{g:<26} {o[6]:>7} {len(o[7]):>11} {o[0]/o[1]:>11.2f} {o[2]/o[3]:>10.2f} {o[4]/max(o[5],1e-9):>8.2f} {o[4]:>7}/{o[5]:<6.1f}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

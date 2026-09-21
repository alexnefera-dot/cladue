#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Скептическая проверка гипотезы №5: определения и воспроизводимость. Только stdlib."""
import csv, math, os, random, re
from collections import Counter, defaultdict
from datetime import date

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'

def f(x):
    try: return float(x)
    except: return 0.0

rows = list(csv.DictReader(open(SRC, encoding='utf-8', newline='')))
print('строк', len(rows))

# ---- 0. зоны
zc = Counter(r['зона'] for r in rows)
print('зон всего', len(zc), '; не team/lol/casino/buzz:', sum(v for k, v in zc.items() if k not in ('team','lol','casino','buzz')),
      dict((k, v) for k, v in zc.items() if k not in ('team','lol','casino','buzz') and v > 1))

# ---- 1. порядок на cf по всем строкам, ничьи в (день, час)
by_cf = defaultdict(list)
for r in rows: by_cf[r['cf-аккаунт']].append(r)
ties = 0
for k, lst in by_cf.items():
    if k == '': continue
    lst.sort(key=lambda r: (r['день запуска'], int(f(r['час запуска']))))
    keys = [(r['день запуска'], int(f(r['час запуска']))) for r in lst]
    if len(keys) != len(set(keys)): ties += 1
    prev = None
    for i, r in enumerate(lst):
        r['_ord'] = i + 1
        d = date.fromisoformat(r['день запуска'])
        r['_gap'] = (d - prev).days if prev else None
        prev = d
for r in by_cf['']: r['_ord'] = None; r['_gap'] = None
print('cf с ничьей (день, час) между базами:', ties)
same_day = sum(1 for r in rows if r.get('_gap') == 0)
print('баз с разрывом 0 (тот же день):', same_day)

# ---- 2. оконные колонки: сайтов в окне vs сайтов, вышли ≤ сайтов в окне
keep = [r for r in rows if r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS and r['набор контента'] != NO_CONTENT and r['cf-аккаунт'] != '']
print('оставлено', len(keep))
diff_sites = Counter((r['сайтов'], r['сайтов в окне'], r['дней']) for r in keep if r['сайтов'] != r['сайтов в окне'])
print('сайтов != сайтов в окне (сайтов, в окне, дней):', dict(diff_sites) if diff_sites else 'нет')
bad = [r['домен'] for r in keep if f(r['вышли за 3 суток']) > f(r['сайтов в окне'])]
print('вышли3 > сайтов в окне:', len(bad))
# проверка колонки "выход 3 суток %" против вышли/сайтов в окне
mism = 0
for r in keep:
    s = f(r['сайтов в окне'])
    if s and abs(100 * f(r['вышли за 3 суток']) / s - f(r['выход 3 суток %'])) > 0.6: mism += 1
print('несовпадений "выход 3 суток %" с вышли3/сайтов в окне (>0.6 п.п.):', mism)
d1 = [r for r in keep if r['дней'] == '1']
print('дней=1 в keep:', len(d1), 'сайтов:', Counter(r['сайтов'] for r in d1), 'дни:', Counter(r['день запуска'][5:] for r in d1))
print('окно закрыто=нет: дни', Counter(r['день запуска'][5:] for r in rows if r['окно закрыто']=='нет'))

# ---- 3. пулы как в h05
def strip(n): return re.sub(r'_\d+$', '', n)
for r in keep:
    r['_set'] = strip(r['набор контента']); r['_s150'] = '150' if r['сайтов']=='150' else '206'
    r['_sites'] = f(r['сайтов в окне']); r['_ex3'] = f(r['вышли за 3 суток']); r['_reg'] = f(r['регистраций в окне 3 суток'])
    r['_rep'] = 'повт' if r['_ord'] > 1 else '1-я'
pk = lambda r: (r['_set'], r['день запуска'], r['_s150'])
pools = defaultdict(list)
for r in keep: pools[pk(r)].append(r)
mixed = sorted([k for k, v in pools.items() if len({x['_rep'] for x in v}) > 1], key=lambda k: (k[1], k[0]))
main = [r for k in mixed for r in pools[k]]
print('\nпулов смешанных', len(mixed), 'доменов', len(main), 'первых', sum(1 for r in main if r['_rep']=='1-я'), 'повт', sum(1 for r in main if r['_rep']=='повт'))
print('сайтов: первые', int(sum(r['_sites'] for r in main if r['_rep']=='1-я')), 'повт', int(sum(r['_sites'] for r in main if r['_rep']=='повт')))
print('рег: первые', int(sum(r['_reg'] for r in main if r['_rep']=='1-я')), 'повт', int(sum(r['_reg'] for r in main if r['_rep']=='повт')))
print('суффикс _NN в keep:', sum(1 for r in keep if r['_set'] != r['набор контента']), '; во всех 2077:', sum(1 for r in rows if strip(r['набор контента']) != r['набор контента']))

# ---- 4. суффиксы _NN по группам внутри пулов
print('\nСуффиксы _NN внутри смешанных пулов (первые | повторные):')
for k in mixed:
    lst = pools[k]
    if not any(r['_set'] != r['набор контента'] for r in lst): continue
    def sfx(r):
        m = re.search(r'_(\d+)$', r['набор контента']); return int(m.group(1)) if m else None
    a = sorted(sfx(r) for r in lst if r['_rep']=='1-я'); b = sorted(sfx(r) for r in lst if r['_rep']=='повт')
    print(f'  {k[1][5:]} {k[0][:34]} {k[2]}: первые {a}\n      повторные {b}')

# ---- 5. по пулам: доли и отношение повт/первые, O/E по группам
def oe(rs, pool_rates):
    o = e = 0.0
    for r in rs:
        o += r['_ex3']; e += pool_rates[pk(r)] * r['_sites']
    return o, e
rates = {k: sum(r['_ex3'] for r in v) / sum(r['_sites'] for r in v) for k, v in pools.items()}
print('\nПо пулам: n1/n_rep, выход первых %, повторных %, отношение, вклад в E первых / E повторных')
mh_num = mh_den = 0.0
for k in mixed:
    lst = pools[k]; fi = [r for r in lst if r['_rep']=='1-я']; rp = [r for r in lst if r['_rep']=='повт']
    s1 = sum(r['_sites'] for r in fi); s2 = sum(r['_sites'] for r in rp)
    x1 = sum(r['_ex3'] for r in fi); x2 = sum(r['_ex3'] for r in rp)
    N = s1 + s2
    mh_num += x2 * s1 / N; mh_den += x1 * s2 / N
    print(f'  {k[1][5:]} {k[0][:34]:<35} {k[2]} {len(fi):>3}/{len(rp):<3} {100*x1/s1:5.1f} {100*x2/s2:5.1f}  отн {(x2/s2)/(x1/s1):4.2f}  E1={rates[k]*s1:7.1f} Erep={rates[k]*s2:7.1f}')
print(f'Мантель-Хензель отношение выхода повт/первые: {mh_num/mh_den:.3f}')

o1, e1 = oe([r for r in main if r['_rep']=='1-я'], rates); o2, e2 = oe([r for r in main if r['_rep']=='повт'], rates)
print(f'O/E первые {o1:.0f}/{e1:.1f}={o1/e1:.3f}; повт {o2:.0f}/{e2:.1f}={o2/e2:.3f}; отношение {(o2/e2)/(o1/e1):.3f}')

# ---- 6. без каждого пула по очереди
print('\nБез одного пула (отношение O/E повт / первые):')
for k in mixed:
    sub = [r for r in main if pk(r) != k]
    a = oe([r for r in sub if r['_rep']=='1-я'], rates); b = oe([r for r in sub if r['_rep']=='повт'], rates)
    print(f'  без {k[1][5:]} {k[0][:34]:<35} {k[2]}: {(b[0]/b[1])/(a[0]/a[1]):.3f}')

# ---- 7. бутстреп доменов внутри пула для интервала отношения
random.seed(7)
def ratio_from(rs):
    pr = {}
    pp = defaultdict(list)
    for r in rs: pp[pk(r)].append(r)
    for k, v in pp.items():
        s = sum(r['_sites'] for r in v); pr[k] = sum(r['_ex3'] for r in v) / s if s else 0
    a = oe([r for r in rs if r['_rep']=='1-я'], pr); b = oe([r for r in rs if r['_rep']=='повт'], pr)
    if a[1] == 0 or b[1] == 0 or a[0] == 0: return None
    return (b[0]/b[1])/(a[0]/a[1])
bs = []
groups = defaultdict(list)
for r in main: groups[(pk(r), r['_rep'])].append(r)
for _ in range(4000):
    samp = []
    for g, lst in groups.items():
        samp += [random.choice(lst) for _ in lst]
    v = ratio_from(samp)
    if v is not None: bs.append(v)
bs.sort()
print(f'\nБутстреп (домены внутри пул×группа, 4000): отношение повт/первые 95% [{bs[int(0.025*len(bs))]:.2f}; {bs[int(0.975*len(bs))]:.2f}], медиана {bs[len(bs)//2]:.2f}')

# бутстреп для быстрого повтора (разрыв ≤2) против первых в тех же пулах
q = [r for r in main if r['_rep']=='1-я' or (r['_gap'] is not None and r['_gap'] <= 2)]
pq = {pk(r) for r in q if r['_rep']=='повт'}
q = [r for r in q if pk(r) in pq]
print('быстрый повтор: пулов', len(pq), 'доменов', len(q), 'первых', sum(1 for r in q if r['_rep']=='1-я'), 'сайтов первых', int(sum(r['_sites'] for r in q if r['_rep']=='1-я')))
bs = []
groups = defaultdict(list)
for r in q: groups[(pk(r), r['_rep'])].append(r)
for _ in range(4000):
    samp = []
    for g, lst in groups.items():
        samp += [random.choice(lst) for _ in lst]
    v = ratio_from(samp)
    if v is not None: bs.append(v)
bs.sort()
print(f'Бутстреп быстрый повтор ≤2 / первые: 95% [{bs[int(0.025*len(bs))]:.2f}; {bs[int(0.975*len(bs))]:.2f}], медиана {bs[len(bs)//2]:.2f}')
for k in sorted(pq):
    fi = [r for r in q if pk(r)==k and r['_rep']=='1-я']; rp = [r for r in q if pk(r)==k and r['_rep']=='повт']
    print(f'   {k[1][5:]} {k[0][:34]} первые n={len(fi)} вых {100*sum(r["_ex3"] for r in fi)/sum(r["_sites"] for r in fi):.1f}% | повт n={len(rp)} вых {100*sum(r["_ex3"] for r in rp)/sum(r["_sites"] for r in rp):.1f}%')

# ---- 8. пул × зона полная страта (все ячейки с обеими группами)
zc_ = defaultdict(list)
for r in main: zc_[(pk(r), r['зона'])].append(r)
cells = [k for k, v in zc_.items() if len({x['_rep'] for x in v}) > 1]
zrs = [r for k in cells for r in zc_[k]]
zr = {k: sum(r['_ex3'] for r in v)/sum(r['_sites'] for r in v) for k, v in zc_.items()}
o1=e1=o2=e2=0.0
for r in zrs:
    k = (pk(r), r['зона'])
    if r['_rep']=='1-я': o1 += r['_ex3']; e1 += zr[k]*r['_sites']
    else: o2 += r['_ex3']; e2 += zr[k]*r['_sites']
print(f'\nПул×зона, все ячейки с обеими группами: ячеек {len(cells)}, доменов {len(zrs)}; O/E первые {o1/e1:.3f}, повт {o2/e2:.3f}, отношение {(o2/e2)/(o1/e1):.3f}')
print('Зона × группа внутри пулов (n доменов):')
for k in mixed:
    lst = pools[k]
    c = Counter((r['зона'], r['_rep']) for r in lst)
    print(f'  {k[1][5:]} {k[0][:34]:<35} {dict(sorted(c.items()))}')

# ---- 9. который раз аккаунт вебмастера / свежий — баланс между группами в пулах
c = Counter((r['_rep'], r['аккаунт свежий']) for r in main)
print('\nаккаунт свежий × группа:', dict(sorted(c.items())))
c = Counter((r['_rep'], r['который раз аккаунт']) for r in main)
print('который раз аккаунт × группа:', dict(sorted(c.items())))

# ---- 10. регистрации: сырые доли на 100 сайтов по группам в главных пулах
for g in ('1-я', 'повт'):
    rs = [r for r in main if r['_rep']==g]
    s = sum(r['_sites'] for r in rs); rg = sum(r['_reg'] for r in rs); cl = sum(f(r['кликов из поиска в окне']) for r in rs)
    print(f'{g}: рег {int(rg)} на {int(s)} сайтов = {100*rg/s:.3f}/100; кликов из поиска в окне {int(cl)}, рег/10тыс кликов {10000*rg/cl if cl else 0:.1f}')

# ---- 11. 16.09: наборы content-2026-09-15-* — где ещё стоят и на каких порядках (по всем keep)
print('\nНаборы 15-* и 14c-* по всем keep (день, порядок, n, вых%):')
for s in ('content-2026-09-15-7str-oform-1','content-2026-09-15-7str-oform-2','content-2026-09-14c-7str-oform-1','content-2026-09-14c-7str-oform-2','content-2026-09-14b-7str-oform-2'):
    cc = defaultdict(list)
    for r in keep:
        if r['_set']==s: cc[(r['день запуска'][5:], r['_ord'])].append(r)
    print('  ', s, {k: (len(v), round(100*sum(r['_ex3'] for r in v)/sum(r['_sites'] for r in v),1)) for k, v in sorted(cc.items())})

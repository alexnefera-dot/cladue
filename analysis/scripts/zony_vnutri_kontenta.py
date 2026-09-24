#!/usr/bin/env python3
"""Есть ли разница между доменными зонами внутри одного контента.

Страта = группа контента + день запуска; берутся только страты, где стоят 2+ зоны.
Ожидание для зоны = её домены × средняя страты (индекс по сайтам, рег и ФД на домен).
Значимость — перестановка меток зон между доменами внутри страты (5000 раз).
Отдельно — только пара team/lol и то же без учёта дня (страта = группа).

    python3 zony_vnutri_kontenta.py <okupaemost_domenov.csv> <out.txt>
"""
import sys, csv, re, random, collections

inp, out_p = sys.argv[1:3]
rows = []
for r in csv.DictReader(open(inp, encoding='utf-8')):
    rows.append(dict(g=re.sub(r'_\d+$', '', r['content']), day=r['launch'], zone=r['zone'], n=int(r['sites']),
                     i=float(r['index']) * int(r['sites']) / 100, reg=int(r['reg']), fd=int(r['fd'])))
Z = ['casino', 'team', 'lol', 'buzz']
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


def strata(rs, key, zones=None):
    S = collections.defaultdict(list)
    for r in rs:
        if zones and r['zone'] not in zones:
            continue
        S[key(r)].append(r)
    return [v for v in S.values() if len({r['zone'] for r in v}) >= 2]


def oe(st, labels=None):
    O = collections.defaultdict(lambda: [0.0] * 6)   # i, Ei, reg, Ereg, fd, Efd
    k = 0
    for v in st:
        N = sum(r['n'] for r in v); I = sum(r['i'] for r in v)
        R = sum(r['reg'] for r in v); F = sum(r['fd'] for r in v); D = len(v)
        for r in v:
            z = labels[k] if labels else r['zone']; k += 1
            o = O[z]
            o[0] += r['i']; o[1] += r['n'] * I / N
            o[2] += r['reg']; o[3] += R / D
            o[4] += r['fd']; o[5] += F / D
    return O


def run(title, st, zones):
    real = oe(st)
    lab = [r['zone'] for v in st for r in v]
    idx = [(sum(len(v) for v in st[:j]), len(v)) for j, v in enumerate(st)]
    rnd = random.Random(1)
    ext = collections.Counter()
    ITER = 5000
    for _ in range(ITER):
        L = lab[:]
        for a, n in idx:
            seg = L[a:a + n]; rnd.shuffle(seg); L[a:a + n] = seg
        o = oe(st, L)
        for z in zones:
            if z not in real:
                continue
            for m, (a, b) in enumerate([(0, 1), (2, 3), (4, 5)]):
                rv = real[z][a] / real[z][b] - 1 if real[z][b] else 0
                pv = o[z][a] / o[z][b] - 1 if o[z][b] else 0
                if abs(pv) >= abs(rv) - 1e-12:
                    ext[(z, m)] += 1
    P(f'\n{title}: страт {len(st)}, доменов {sum(len(v) for v in st)}')
    P(f'{"зона":<8} {"доменов":>7} {"индекс факт/ожид":>18} {"p":>6} {"рег факт/ожид":>20} {"p":>6} {"ФД факт/ожид":>18} {"p":>6}')
    for z in zones:
        if z not in real:
            continue
        o = real[z]; nd = sum(1 for v in st for r in v if r['zone'] == z)
        P(f'.{z:<7} {nd:>7} {o[0]/o[1]:>8.2f}× ({o[0]:.0f}/{o[1]:.0f}) {ext[(z,0)]/ITER:>5.3f} '
          f'{o[2]/o[3] if o[3] else 0:>8.2f}× ({o[2]}/{o[3]:.1f}) {ext[(z,1)]/ITER:>5.3f} '
          f'{o[4]/o[5] if o[5] else 0:>7.2f}× ({o[4]}/{o[5]:.1f}) {ext[(z,2)]/ITER:>5.3f}')


P('Зоны внутри одного контента. Запуски 01–19.09, деньги по 22.09. p — доля перестановок с таким же или большим отклонением.')
run('Все зоны, страта = контент + день', strata(rows, lambda r: (r['g'], r['day'])), Z)
run('Только team и lol, страта = контент + день', strata(rows, lambda r: (r['g'], r['day']), {'team', 'lol'}), ['team', 'lol'])
run('Все зоны, страта = контент (дни смешаны)', strata(rows, lambda r: r['g']), Z)

# по каждой группе: где зоны расходятся по индексу и что с рег
P('\nГруппы, где team и lol стоят в один день (по каждой группе, сумма по дням):')
P(f'{"группа":<44} {"team: дом / индекс / рег / ФД":>32} {"lol: дом / индекс / рег / ФД":>32}')
G = collections.defaultdict(lambda: {z: [0, 0, 0.0, 0, 0] for z in ('team', 'lol')})
for v in strata(rows, lambda r: (r['g'], r['day']), {'team', 'lol'}):
    for r in v:
        a = G[r['g']][r['zone']]; a[0] += 1; a[1] += r['n']; a[2] += r['i']; a[3] += r['reg']; a[4] += r['fd']
for g, d in sorted(G.items(), key=lambda kv: -(kv[1]['team'][0] + kv[1]['lol'][0])):
    t, l = d['team'], d['lol']
    P(f'{g:<44} {t[0]:>6} / {100*t[2]/t[1]:5.1f}% / {t[3]:>3} / {t[4]:>2}     {l[0]:>6} / {100*l[2]/l[1]:5.1f}% / {l[3]:>3} / {l[4]:>2}')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')

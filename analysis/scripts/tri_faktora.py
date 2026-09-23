#!/usr/bin/env python3
"""Три подозреваемых ещё раз: час постановки, повторность аккаунта, длина метки.

Проверка идёт на всех доменах с закрытым окном, внутри страты
«набор контента + день запуска + зона»: для каждой группы считается ожидание
по доле страты, затем O/E. Значимость — перестановка признака внутри страты.

    python3 tri_faktora.py <свод.csv> <out.txt>
"""
import sys, csv, re, random, collections, statistics

svod_p, out_p = sys.argv[1], sys.argv[2]
random.seed(1)
root = lambda n: re.sub(r'_\d+$', '', n)
I = lambda r, k: int(r[k]) if r[k] not in ('', 'None') else 0

R = [r for r in csv.DictReader(open(svod_p, encoding='utf-8'))
     if r['окно закрыто'] == 'да' and I(r, 'сайтов в окне') > 0]
for r in R:
    r['_st'] = (root(r['набор контента']), r['день запуска'], r['зона'])

def groups(key):
    return {r['домен']: key(r) for r in R}

def oe(key, metric, denom):
    """O/E по группам признака внутри страт, где признак меняется."""
    st = collections.defaultdict(list)
    for r in R:
        st[r['_st']].append(r)
    use = [v for v in st.values() if len({key(r) for r in v}) >= 2]
    tot = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])   # O, E, доменов, сайтов
    for v in use:
        S = sum(I(r, denom) for r in v); M = sum(I(r, metric) for r in v)
        if not S:
            continue
        for r in v:
            g = tot[key(r)]
            g[0] += I(r, metric); g[1] += M * I(r, denom) / S
            g[2] += 1; g[3] += I(r, denom)
    return tot, use

def perm_p(key, metric, denom, use, real_spread, n=2000):
    """Доля перестановок, где разброс O/E между группами не меньше наблюдённого."""
    hit = 0
    for _ in range(n):
        tot = collections.defaultdict(lambda: [0.0, 0.0])
        for v in use:
            S = sum(I(r, denom) for r in v); M = sum(I(r, metric) for r in v)
            if not S:
                continue
            ks = [key(r) for r in v]; random.shuffle(ks)
            for r, k in zip(v, ks):
                g = tot[k]
                g[0] += I(r, metric); g[1] += M * I(r, denom) / S
        vals = [o / e for o, e in tot.values() if e > 30]
        if vals and max(vals) / min(vals) >= real_spread:
            hit += 1
    return hit / n

L = []
P = L.append
P(f'ВСЕ ДОМЕНЫ С ЗАКРЫТЫМ ОКНОМ: {len(R)}; страт «набор + день + зона»: '
  f'{len({r["_st"] for r in R})}')
P('O/E — во сколько раз группа лучше ожидания по своей страте. Значимость — перестановка признака внутри страты.')

TESTS = [
    ('ЧАС ПОСТАНОВКИ (блок)', lambda r: r['блок часа']),
    ('ЧАС ПОСТАНОВКИ (ровно час, только крупные)', lambda r: r['час запуска'] if r['час запуска'] in ('2', '3', '12', '13', '14', '15') else 'прочие'),
    ('КОТОРЫЙ РАЗ АККАУНТ ВЕБМАСТЕРА', lambda r: 'первый' if r['который раз аккаунт'] == '1' else ('второй' if r['который раз аккаунт'] == '2' else 'третий+')),
    ('ДЛИНА МЕТКИ ДОМЕНА', lambda r: '3 символа' if r['длина метки'] == '3' else ('4 символа' if r['длина метки'] == '4' else '5+ символов')),
    ('ПАТТЕРН ИМЕНИ', lambda r: r['паттерн имени']),
]
for title, key in TESTS:
    P(''); P(title)
    for metric, denom, name in [('вышли за 3 суток', 'сайтов в окне', 'индекс'),
                                ('регистраций в окне 3 суток', 'сайтов в окне', 'деньги')]:
        tot, use = oe(key, metric, denom)
        rows = [(k, v) for k, v in tot.items() if v[1] > 30 or name == 'деньги']
        if not rows:
            continue
        P(f'   по {name}: страт с разными значениями {len(use)}, доменов {sum(v[2] for _, v in rows)}')
        for k, v in sorted(rows, key=lambda kv: -kv[1][0] / max(kv[1][1], 1e-9)):
            P(f'      {str(k):<22} доменов {v[2]:>4}  сайтов {v[3]:>7}  наблюдено {v[0]:>7.0f}  ожидалось {v[1]:>8.1f}  O/E {v[0]/max(v[1],1e-9):>5.2f}')
        vals = [v[0] / v[1] for _, v in rows if v[1] > 30]
        if len(vals) >= 2:
            spread = max(vals) / min(vals)
            p = perm_p(key, metric, denom, use, spread, 2000 if name == 'индекс' else 2000)
            P(f'      размах O/E {spread:.2f}; перестановочное p = {p:.3f}'
              + ('  <- различие реально' if p < 0.05 else '  <- в пределах случайного'))
open(out_p, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
print('\n'.join(L))

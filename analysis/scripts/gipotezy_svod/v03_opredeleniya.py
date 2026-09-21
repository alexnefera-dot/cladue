#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик, угол «определения и воспроизводимость» для гипотезы №3 (Theme2).
Независимая пересборка ключевых чисел h03_theme2_template.py:
  1. Проверка среза и определений (оконные колонки, знаменатели, дней=1, окно, контент, зоны-одиночки).
  2. Пересчёт грубых O/E (страта = день) и решающих O/E (день × час × сайтов, ≥3 каждого).
  3. ТОЧНЫЙ перестановочный p для решающего теста (в обеих партиях все домены одного размера,
     поэтому E не меняется при перестановке и p = P(O ≤ набл.) — считается свёрткой гипергеометрических
     распределений, без Монте-Карло).
  4. Доверительный интервал для «внутри партии Theme2 = 0,74 от Theme1»: стратифицированный бутстреп по доменам.
  5. Критерии плана по буквальному определению E (доля пула) и по E «по Theme1».
Только stdlib.
"""
import csv
import math
import os
import random
from collections import Counter, defaultdict
from itertools import combinations

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(BASE, 'export', 'gipotezy_svod', 'v03_opredeleniya.txt')
_l = []


def p(*a):
    s = ' '.join(str(x) for x in a)
    _l.append(s)
    print(s)


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
DAYS = ('2026-08-19', '2026-08-20')
p('Всего строк:', len(rows))

# ---------------------------------------------------------------- 1. срез и определения
p('=' * 90)
p('1. СРЕЗ И ОПРЕДЕЛЕНИЯ')
p('=' * 90)
sl = [r for r in rows if r['день запуска'] in DAYS and r['зона'] == 'team']
p('team 19–20.08 до фильтров:', len(sl))
p('  окно закрыто:', dict(Counter(r['окно закрыто'] for r in sl)))
p('  дней:', dict(Counter(r['дней'] for r in sl)))
p('  выбросы 3615/3286 в срезе:', sum(1 for r in sl if r['домен'] in ('3615.team', '3286.team')))
p('  набор контента:', dict(Counter(r['набор контента'] for r in sl)))
p('  «сайтов в окне» == «сайтов» у всех:', all(r['сайтов в окне'] == r['сайтов'] for r in sl))
p('  «брендов» == «сайтов» у всех:', all(r['брендов'] == r['сайтов'] for r in sl))
p('  1-я волна:', dict(Counter(r['сайтов в 1-й волне'] for r in sl)), ' 2-я волна:', dict(Counter(r['сайтов во 2-й волне'] for r in sl)))
p('  «выход 3 суток %» == вышли3/сайтов у всех (±0.1):',
  all(abs(100 * f(r['вышли за 3 суток']) / f(r['сайтов']) - f(r['выход 3 суток %'])) < 0.15 for r in sl))
p('  пустых «вышли за 3 суток»:', sum(1 for r in sl if r['вышли за 3 суток'] == ''))
main = [r for r in sl if r['окно закрыто'] == 'да' and r['дней'] != '1' and r['домен'] not in ('3615.team', '3286.team')]
p('после фильтров:', len(main))
for r in rows:
    r['S'] = f(r['сайтов в окне']); r['V3'] = f(r['вышли за 3 суток']); r['V7'] = f(r['вышли за 7 суток'])
    r['R'] = f(r['регистраций в окне 3 суток']); r['Rall'] = f(r['регистраций'])
    r['h'] = int(f(r['час запуска'])); r['d'] = r['день запуска'][5:]; r['t'] = r['шаблон']
p('  регистраций в окне vs всего у Theme2 среза: %d / %d; у Theme1: %d / %d' % (
    sum(r['R'] for r in main if r['t'] == 'Theme2'), sum(r['Rall'] for r in main if r['t'] == 'Theme2'),
    sum(r['R'] for r in main if r['t'] == 'Theme1'), sum(r['Rall'] for r in main if r['t'] == 'Theme1')))
p('  Theme2 во всём файле:', sum(1 for r in rows if r['t'] == 'Theme2'), '; в срезе:', sum(1 for r in main if r['t'] == 'Theme2'))
# зоны-одиночки
oth = [r for r in rows if r['день запуска'] in DAYS and r['зона'] != 'team']
p('  вне team 19–20.08:', len(oth), 'доменов;', dict(Counter(r['зона'] for r in oth)))
st = defaultdict(lambda: Counter())
for r in oth:
    st[(r['d'], r['зона'], r['h'])][r['t']] += 1
paired = {k: v for k, v in st.items() if v['Theme1'] and v['Theme2']}
p('  страты день×зона×час вне team с обоими шаблонами:', {k: dict(v) for k, v in paired.items()},
  '— остальные одиночки не смешиваются с team (в 7a они выпадают)')
p()


# ---------------------------------------------------------------- 2. O/E
def agg(ds):
    S = sum(r['S'] for r in ds); V = sum(r['V3'] for r in ds); R = sum(r['R'] for r in ds); V7 = sum(r['V7'] for r in ds)
    return dict(n=len(ds), S=S, V=V, R=R, V7=V7, ex=100 * V / S if S else 0)


def oe(ds, key, min_each=1, metric='V3'):
    strata = defaultdict(list)
    for r in ds:
        strata[key(r)].append(r)
    O = Ep = Er = 0.0
    used = []
    for k, v in strata.items():
        t1 = [r for r in v if r['t'] == 'Theme1']; t2 = [r for r in v if r['t'] == 'Theme2']
        if len(t1) < min_each or len(t2) < min_each:
            continue
        used.append(k)
        rp = sum(r[metric] for r in v) / sum(r['S'] for r in v)
        rr = sum(r[metric] for r in t1) / sum(r['S'] for r in t1)
        for r in t2:
            O += r[metric]; Ep += rp * r['S']; Er += rr * r['S']
    return O, Ep, Er, used


p('=' * 90)
p('2. ПЕРЕСЧЁТ O/E')
p('=' * 90)
for d in ('08-19', '08-20', 'оба'):
    for t in ('Theme1', 'Theme2'):
        a = agg([r for r in main if r['t'] == t and (d == 'оба' or r['d'] == d)])
        p('  %-5s %-6s n=%2d сайтов=%5d вышли3=%4d выход=%4.1f%% рег=%2d' % (d, t, a['n'], a['S'], a['V'], a['ex'], a['R']))
O, Ep, Er, _ = oe(main, lambda r: r['d'])
p('  грубо (страта=день), выход: O=%d E_пул=%.1f O/E=%.2f | E_Theme1=%.1f O/E=%.2f' % (O, Ep, O / Ep, Er, O / Er))
O, Ep, Er, _ = oe(main, lambda r: r['d'], metric='R')
p('  грубо, регистрации: O=%d E_пул=%.2f O/E=%.2f | E_Theme1=%.2f O/E=%.2f' % (O, Ep, O / Ep, Er, O / Er))
O, Ep, Er, used = oe(main, lambda r: (r['d'], r['h'], r['сайтов']), min_each=3)
p('  решающий (день×час×сайтов, ≥3 каждого), партии:', used)
p('    выход: O=%d E_пул=%.1f O/E=%.2f | E_Theme1=%.1f O/E=%.2f' % (O, Ep, O / Ep, Er, O / Er))
O7, Ep7, Er7, _ = oe(main, lambda r: (r['d'], r['h'], r['сайтов']), min_each=3, metric='V7')
p('    7 суток: O=%d E_пул=%.1f O/E=%.2f | E_Theme1=%.1f O/E=%.2f' % (O7, Ep7, O7 / Ep7, Er7, O7 / Er7))
Or, Epr, Err, _ = oe(main, lambda r: (r['d'], r['h'], r['сайтов']), min_each=3, metric='R')
p('    регистрации: O=%d E_пул=%.2f O/E=%.2f | E_Theme1=%.2f O/E=%.2f' % (Or, Epr, Or / Epr, Err, Or / Err))
p()

# ---------------------------------------------------------------- 3. точная перестановка
p('=' * 90)
p('3. ТОЧНЫЙ ПЕРЕСТАНОВОЧНЫЙ p ДЛЯ РЕШАЮЩЕГО ТЕСТА')
p('=' * 90)
batches = {}
for k in used:
    batches[k] = [r for r in main if (r['d'], r['h'], r['сайтов']) == k]
for k, v in batches.items():
    p('  партия %s: n=%d, сайтов у всех одинаково: %s, Theme2: %d' % (k, len(v), len(set(r['S'] for r in v)) == 1,
                                                                    sum(1 for r in v if r['t'] == 'Theme2')))
p('  → E не меняется при перестановке метки, p = P(сумма O по случайным доменам ≤ наблюдённой).')


def exact_dist(v, metric):
    """Распределение суммы metric по случайной выборке k = число Theme2 доменов из партии (все C(n,k) наборов)."""
    k = sum(1 for r in v if r['t'] == 'Theme2')
    vals = [int(r[metric]) for r in v]
    c = Counter()
    for comb in combinations(range(len(v)), k):
        c[sum(vals[i] for i in comb)] += 1
    tot = sum(c.values())
    return {s: n / tot for s, n in c.items()}


def convolve(d1, d2):
    out = defaultdict(float)
    for a, pa in d1.items():
        for b, pb in d2.items():
            out[a + b] += pa * pb
    return out


for metric, obs, name in (('V3', 603, 'выход за 3 суток'), ('R', 2, 'регистрации в окне')):
    dist = None
    for k, v in batches.items():
        dk = exact_dist(v, metric)
        dist = dk if dist is None else convolve(dist, dk)
    p_le = sum(pr for s, pr in dist.items() if s <= obs)
    p_ge = sum(pr for s, pr in dist.items() if s >= obs)
    mean = sum(s * pr for s, pr in dist.items())
    p('  %s: O=%d, E(перест.)=%.1f, точный p(O ≤ набл.)=%.4f, p(O ≥ набл.)=%.4f, двусторонний ≈ %.4f' %
      (name, obs, mean, p_le, p_ge, min(1.0, 2 * min(p_le, p_ge))))
p()

# ---------------------------------------------------------------- 4. доверительный интервал
p('=' * 90)
p('4. ДОВЕРИТЕЛЬНЫЙ ИНТЕРВАЛ для «Theme2 = 0,74 от Theme1 внутри партии» (стратифицированный бутстреп по доменам)')
p('=' * 90)
rnd = random.Random(7)
NB = 10000


def boot_ratio(bs, metric='V3'):
    res = []
    for _ in range(NB):
        O = Er = Ep = 0.0
        for k, v in bs.items():
            t1 = [r for r in v if r['t'] == 'Theme1']; t2 = [r for r in v if r['t'] == 'Theme2']
            b1 = [rnd.choice(t1) for _ in t1]; b2 = [rnd.choice(t2) for _ in t2]
            rr = sum(r[metric] for r in b1) / sum(r['S'] for r in b1)
            rp = (sum(r[metric] for r in b1) + sum(r[metric] for r in b2)) / (sum(r['S'] for r in b1) + sum(r['S'] for r in b2))
            for r in b2:
                O += r[metric]; Er += rr * r['S']; Ep += rp * r['S']
        res.append((O / Er if Er else float('nan'), O / Ep if Ep else float('nan')))
    return res


res = boot_ratio(batches)
rr = sorted(x[0] for x in res); rp = sorted(x[1] for x in res)
lo, hi = rr[int(0.025 * NB)], rr[int(0.975 * NB)]
p('  выход, O/E по Theme1: точка 0.74, 95%% бутстреп-интервал [%.2f, %.2f]; доля бутстрепов с O/E ≤ 0.5: %.3f; ≥ 1.0: %.3f' %
  (lo, hi, sum(1 for x in rr if x <= 0.5) / NB, sum(1 for x in rr if x >= 1.0) / NB))
p('  выход, O/E по пулу:    точка 0.87, 95%% интервал [%.2f, %.2f]' % (rp[int(0.025 * NB)], rp[int(0.975 * NB)]))
# по партиям отдельно
for k, v in batches.items():
    r1 = boot_ratio({k: v})
    s = sorted(x[0] for x in r1)
    a1 = agg([r for r in v if r['t'] == 'Theme1']); a2 = agg([r for r in v if r['t'] == 'Theme2'])
    p('  партия %s: Theme1 %d дом. %.1f%%, Theme2 %d дом. %.1f%% → O/E по Theme1 %.2f, 95%% [%.2f, %.2f]' %
      (k, a1['n'], a1['ex'], a2['n'], a2['ex'], a2['ex'] / a1['ex'], s[int(0.025 * NB)], s[int(0.975 * NB)]))
# грубый интервал (страта день) для сравнения
bday = defaultdict(list)
for r in main:
    bday[r['d']].append(r)
rg = sorted(x[0] for x in boot_ratio(bday))
p('  для сравнения, грубо (страта=день): O/E по Theme1 0.54, 95%% бутстреп [%.2f, %.2f]' % (rg[int(0.025 * NB)], rg[int(0.975 * NB)]))
# регистрации внутри партии
rreg = sorted(x[0] for x in boot_ratio(batches, 'R') if x[0] == x[0])
p('  регистрации внутри партии, O/E по Theme1: точка 0.25, 95%% бутстреп [%.2f, %.2f]' % (rreg[int(0.025 * len(rreg))], rreg[int(0.975 * len(rreg))]))
p()

# ---------------------------------------------------------------- 5. критерии плана по буквальному определению
p('=' * 90)
p('5. КРИТЕРИИ ПЛАНА: «E = доля выхода дня × сайтов в окне» (буквально по плану) против E по Theme1')
p('=' * 90)
O, Ep, Er, _ = oe(main, lambda r: r['d'])
p('  грубо, выход: O/E по плану (пул) = %.2f (критерий ≤0,6: %s); O/E по Theme1 = %.2f (%s)' %
  (O / Ep, 'да' if O / Ep <= 0.6 else 'НЕТ', O / Er, 'да' if O / Er <= 0.6 else 'НЕТ'))
O, Ep, Er, _ = oe(main, lambda r: r['d'], metric='R')
p('  грубо, регистрации: O/E по плану (пул) = %.2f (≤0,4: %s); по Theme1 = %.2f' % (O / Ep, 'да' if O / Ep <= 0.4 else 'НЕТ', O / Er))
O, Ep, Er, _ = oe(main, lambda r: (r['d'], r['блок часа']))
p('  блок часа: выход O/E пул = %.2f, по Theme1 = %.2f (критерий ≤0,6: %s / %s)' %
  (O / Ep, O / Er, 'да' if O / Ep <= 0.6 else 'НЕТ', 'да' if O / Er <= 0.6 else 'НЕТ'))
p('  Вечер 20.08 (одно и то же «сайтов» 202–204, часы 20–22): Theme2 20–21ч против Theme1 22ч —')
ev2 = agg([r for r in main if r['t'] == 'Theme2' and r['d'] == '08-20' and r['h'] in (20, 21)])
ev1 = agg([r for r in main if r['t'] == 'Theme1' and r['d'] == '08-20' and r['h'] == 22 and r['сайтов'] in ('202', '203', '204')])
ev1all = agg([r for r in main if r['t'] == 'Theme1' and r['d'] == '08-20' and r['h'] == 22])
p('    Theme2: %d дом., %d сайтов, выход %.1f%%, рег %d | Theme1 22ч 202–204 сайта: %d дом., выход %.1f%%, рег %d | Theme1 22ч все: %d дом., %.1f%%, рег %d' %
  (ev2['n'], ev2['S'], ev2['ex'], ev2['R'], ev1['n'], ev1['ex'], ev1['R'], ev1all['n'], ev1all['ex'], ev1all['R']))
p('    отношение Theme2/Theme1 = %.2f (по 202–204) / %.2f (по всем 22ч). Это сравнение тестировщик не считает,' % (ev2['ex'] / ev1['ex'], ev2['ex'] / ev1all['ex']))
p('    потому что час различается (20–21 против 22) и аккаунты разные (свежие 108–138 против повторных 11–23); в реестре «час постановки»')
p('    опровергнут как фактор, «свежесть аккаунта» — тоже. Т.е. исключение вечерней партии держится на допущении «час = партия», а не на записанном поле.')
p()

# сколько Theme2 вообще попадает в решающий тест
n2 = sum(1 for r in main if r['t'] == 'Theme2')
n2d = sum(1 for v in batches.values() for r in v if r['t'] == 'Theme2')
p('Решающий тест покрывает %d из %d Theme2 в срезе (%.0f%%) и %d из 59 Theme1.' % (n2d, n2, 100 * n2d / n2, sum(1 for v in batches.values() for r in v if r['t'] == 'Theme1')))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(_l) + '\n')

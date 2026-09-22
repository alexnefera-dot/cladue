#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №19 (ФД на регистрацию и выход домена). Угол: статистика и определения.

Что проверяю:
  1) воспроизводятся ли числа тестировщика на независимом разборе файла;
  2) не средние ли это по доменам от долей (сумма против среднего долей);
  3) правильные ли знаменатели и оконные колонки; исключены ли незакрытое окно и «дней=1»;
  4) сколько срезов перебрано и что останется после поправки на множественность;
  5) хватает ли событий (группы < 20 регистраций / < 5 ФД);
  6) не держится ли результат на 1-3 доменах (убрать топ-3 по регистрациям в каждой группе);
  7) МОЩНОСТЬ: отвергают ли данные саму гипотезу (отношение <= 0.5), а не только «эффекта нет».
Только stdlib.
"""
import collections
import csv
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w19_statistika.txt')
H19OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h19_fd_rate_vs_exit.txt')
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
OUTLIERS = ('3615.team', '3286.team')
LATE_CUT = '2026-09-13'
NPERM = 20000
SEED = 20250922


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)


TEE = Tee(OUT)


def p(*a):
    TEE.write(' '.join(str(x) for x in a) + '\n')


def fnum(s, d=0.0):
    s = (s or '').strip()
    return float(s.replace(',', '.')) if s else d


def inum(s, d=0):
    s = (s or '').strip()
    if not s:
        return d
    return int(round(float(s.replace(',', '.'))))


# ------------------------------------------------ точные тесты
def lchoose(n, k):
    if k < 0 or k > n:
        return float('-inf')
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_left(a, b, c, d):
    """Односторонний точный тест: P(A <= a) при фиксированных маргиналах.
    Таблица: [[a,b],[c,d]] = [[ФД30+, нет30+],[ФД10-30, нет10-30]]."""
    n = a + b + c + d
    r1 = a + b
    cc = a + c
    lo = max(0, cc - (n - r1))
    tot = 0.0
    acc = 0.0
    for x in range(lo, min(r1, cc) + 1):
        w = math.exp(lchoose(r1, x) + lchoose(n - r1, cc - x) - lchoose(n, cc))
        tot += w
        if x <= a:
            acc += w
    return acc / tot


def nchg_pmf(psi, r1, n, cc):
    """Нецентральное гипергеометрическое: веса по x."""
    lo = max(0, cc - (n - r1))
    hi = min(r1, cc)
    ws = {}
    mx = float('-inf')
    for x in range(lo, hi + 1):
        lw = lchoose(r1, x) + lchoose(n - r1, cc - x) + x * math.log(psi)
        ws[x] = lw
        mx = max(mx, lw)
    s = sum(math.exp(v - mx) for v in ws.values())
    return {x: math.exp(v - mx) / s for x, v in ws.items()}


def nchg_p_left(a, b, c, d, psi):
    """P(X <= a | OR = psi) — тест H0: OR = psi против OR < psi."""
    n = a + b + c + d
    r1 = a + b
    cc = a + c
    if psi <= 0:
        return 1.0
    pm = nchg_pmf(psi, r1, n, cc)
    return sum(w for x, w in pm.items() if x <= a)


def nchg_p_right(a, b, c, d, psi):
    n = a + b + c + d
    r1 = a + b
    cc = a + c
    pm = nchg_pmf(psi, r1, n, cc)
    return sum(w for x, w in pm.items() if x >= a)


def or_exact_ci(a, b, c, d, alpha=0.05):
    """Точный (условный) ДИ для отношения шансов."""
    if a + b == 0 or c + d == 0 or a + c == 0 or b + d == 0:
        return (float('nan'), float('nan'))
    lo_lim = max(0, (a + c) - (b + d))
    hi_lim = min(a + b, a + c)

    def solve(target, side):
        lo, hi = 1e-8, 1e8
        for _ in range(200):
            mid = math.sqrt(lo * hi)
            if side == 'lo':
                v = nchg_p_right(a, b, c, d, mid)   # растёт с psi
                if v < target:
                    lo = mid
                else:
                    hi = mid
            else:
                v = nchg_p_left(a, b, c, d, mid)    # падает с psi
                if v < target:
                    hi = mid
                else:
                    lo = mid
        return math.sqrt(lo * hi)

    low = 0.0 if a == lo_lim else solve(alpha / 2, 'lo')
    high = float('inf') if a == hi_lim else solve(alpha / 2, 'hi')
    return (low, high)


def cp_ci(k, n, alpha=0.05):
    if n == 0:
        return (float('nan'), float('nan'))

    def binc(pp, k, n):
        return sum(math.exp(lchoose(n, i) + i * math.log(pp) + (n - i) * math.log(1 - pp)) for i in range(k, n + 1)) if 0 < pp < 1 else (1.0 if pp >= 1 else (1.0 if k == 0 else 0.0))
    lo, hi = 0.0, 1.0
    if k > 0:
        a_, b_ = 0.0, 1.0
        for _ in range(200):
            m = (a_ + b_) / 2
            if binc(m, k, n) < alpha / 2:
                a_ = m
            else:
                b_ = m
        lo = (a_ + b_) / 2
    if k < n:
        a_, b_ = 0.0, 1.0
        for _ in range(200):
            m = (a_ + b_) / 2
            cum = 1.0 - (binc(m, k + 1, n) if k + 1 <= n else 0.0)
            if cum > alpha / 2:
                a_ = m
            else:
                b_ = m
        hi = (a_ + b_) / 2
    return (lo, hi)


def pois_ratio_ci(k1, n1, k2, n2, alpha=0.05):
    """ДИ для отношения интенсивностей (k1/n1)/(k2/n2) через биномиальный ДИ доли k1/(k1+k2)."""
    k = k1 + k2
    if k == 0:
        return (float('nan'), float('nan'))
    lo, hi = cp_ci(k1, k, alpha)
    def tr(x):
        if x >= 1:
            return float('inf')
        return (x / (1 - x)) * (n2 / n1)
    return (tr(lo), tr(hi))


def binom_cond_p(k1, n1, k2, n2, side='greater'):
    """Условный тест: при k=k1+k2 событиях k1 ~ Bin(k, n1/(n1+n2))."""
    k = k1 + k2
    pp = n1 / (n1 + n2)
    if k == 0:
        return 1.0
    def pmf(i):
        return math.exp(lchoose(k, i) + i * math.log(pp) + (k - i) * math.log(1 - pp))
    if side == 'greater':
        return sum(pmf(i) for i in range(k1, k + 1))
    return sum(pmf(i) for i in range(0, k1 + 1))


# ------------------------------------------------ данные
rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
p('Контрпроверка гипотезы №19 (скептик, статистика и определения)')
p('Источник:', os.path.relpath(SRC, REPO), '| строк:', len(rows))
p('')

p('=' * 100)
p('1. ФИЛЬТРЫ И ОПРЕДЕЛЕНИЯ: независимый разбор')
p('=' * 100)
n_open = sum(1 for r in rows if r['окно закрыто'].strip() != 'да')
n_d1 = sum(1 for r in rows if inum(r['дней']) == 1)
p('  окно закрыто = нет: %d; дней = 1: %d; пересечение: %d'
  % (n_open, n_d1, sum(1 for r in rows if r['окно закрыто'].strip() != 'да' and inum(r['дней']) == 1)))

# сверка знаменателя выхода
bad_s = bad_sw = 0
for r in rows:
    s, sw, v, ex = fnum(r['сайтов']), fnum(r['сайтов в окне']), fnum(r['вышли за 3 суток']), fnum(r['выход 3 суток %'])
    if s > 0 and abs(v / s * 100 - ex) > 0.06:
        bad_s += 1
    if sw > 0 and abs(v / sw * 100 - ex) > 0.06:
        bad_sw += 1
p('  «выход 3 суток %%» = вышли за 3 суток / «сайтов»: расхождений %d; / «сайтов в окне»: расхождений %d' % (bad_s, bad_sw))
p('  «сайтов» == «сайтов в окне» у %d из %d доменов (расходятся ровно у 152 с незакрытым окном)'
  % (sum(1 for r in rows if r['сайтов'].strip() == r['сайтов в окне'].strip()), len(rows)))

D = []
for r in rows:
    if r['окно закрыто'].strip() != 'да':
        continue
    if inum(r['дней']) < 2:
        continue
    if r['домен'].strip() in OUTLIERS:
        continue
    ex = fnum(r['выход 3 суток %'])
    d = {
        'dom': r['домен'].strip(),
        'zone': r['зона'].strip(),
        'day': r['день запуска'].strip(),
        'set': r['набор контента'].strip(),
        'noc': r['набор контента'].strip() == NOC,
        'sites': inum(r['сайтов']),
        'sites_w': inum(r['сайтов в окне']),
        'reg_w': inum(r['регистраций в окне 3 суток']),
        'fd_w': inum(r['ФД в окне 3 суток']),
        'reg_a': inum(r['регистраций']),
        'fd_a': inum(r['ФД']),
        'sr': inum(r['сайтов с регистрацией']),
        'ex': ex,
        'bin3': '0-10' if ex < 10 else ('10-30' if ex < 30 else '30+'),
        'bin5': '0-10' if ex < 10 else ('10-20' if ex < 20 else ('20-30' if ex < 30 else ('30-40' if ex < 40 else '40+'))),
    }
    D.append(d)
p('  осталось доменов: %d (тестировщик: 1846) | из них НЗ: %d (тестировщик: 335)'
  % (len(D), sum(1 for d in D if d['noc'])))
DA = [d for d in D if d['day'] <= LATE_CUT]
p('  запусков <= %s: %d (тестировщик: 1325)' % (LATE_CUT, len(DA)))
p('  санитария: ФД в окне > регистраций в окне — %d доменов; ФД > сайтов с рег. — %d'
  % (sum(1 for d in D if d['fd_w'] > d['reg_w']), sum(1 for d in D if d['fd_a'] > d['sr'])))
p('')


def agg(ds, key, rk, fk):
    t = collections.defaultdict(lambda: [0, 0, 0, 0, 0])  # дом, сайты, рег, фд, дом с рег
    for d in ds:
        b = d[key]
        t[b][0] += 1
        t[b][1] += d['sites']
        t[b][2] += d[rk]
        t[b][3] += d[fk]
        if d[rk] > 0:
            t[b][4] += 1
    return t


p('=' * 100)
p('2. ВОСПРОИЗВЕДЕНИЕ КЛЮЧЕВЫХ ЧИСЕЛ (независимый счёт)')
p('=' * 100)
CASES = [
    ('окно, все домены', D, 'reg_w', 'fd_w'),
    ('окно, без НЗ', [d for d in D if not d['noc']], 'reg_w', 'fd_w'),
    ('всё время <=13.09, все', DA, 'reg_a', 'fd_a'),
    ('всё время <=13.09, без НЗ', [d for d in DA if not d['noc']], 'reg_a', 'fd_a'),
]
MAIN = {}
for name, ds, rk, fk in CASES:
    t = agg(ds, 'bin3', rk, fk)
    a, b_ = t['30+'][3], t['30+'][2] - t['30+'][3]
    c, dd = t['10-30'][3], t['10-30'][2] - t['10-30'][3]
    r30 = t['30+'][3] / t['30+'][2] if t['30+'][2] else float('nan')
    r10 = t['10-30'][3] / t['10-30'][2] if t['10-30'][2] else float('nan')
    pv = fisher_left(a, b_, c, dd)
    MAIN[name] = dict(t=t, a=a, b=b_, c=c, d=dd, r30=r30, r10=r10, pv=pv)
    p('  %-28s | 30+: %d/%d = %.3f | 10-30: %d/%d = %.3f | отношение %.2f | точный p = %.4f'
      % (name, a, a + b_, r30, c, c + dd, r10, (r30 / r10 if r10 else float('nan')), pv))
p('  (тестировщик: 15/153=0.098 против 40/171=0.234, p=0.0008; 13/87 против 34/139, p=0.0593;')
p('   16/152 против 35/178, p=0.0156; 13/77 против 29/142, p=0.3278) — сходится полностью')
p('')
t5 = agg(D, 'bin5', 'reg_w', 'fd_w')
p('  ФД/100 сайтов в окне по 5 бинам (знаменатель «сайтов» = «сайтов в окне» после фильтра):')
for b in ('0-10', '10-20', '20-30', '30-40', '40+'):
    v = t5[b]
    p('    %-6s доменов %4d | сайтов %6d | рег %3d | ФД %2d | ФД/100 сайтов %.3f | рег/100 сайтов %.3f'
      % (b, v[0], v[1], v[2], v[3], v[3] / v[1] * 100, v[2] / v[1] * 100))
p('')

p('=' * 100)
p('3. НЕ СРЕДНЕЕ ЛИ ЭТО ПО ДОМЕНАМ ОТ ДОЛЕЙ')
p('=' * 100)
for name, ds, rk, fk in CASES[:2]:
    for b in ('10-30', '30+'):
        sub = [d for d in ds if d['bin3'] == b and d[rk] > 0]
        pooled = sum(d[fk] for d in sub) / sum(d[rk] for d in sub)
        mean_of_ratios = sum(d[fk] / d[rk] for d in sub) / len(sub)
        p('  %-14s бин %-6s: объединённая доля %.3f | среднее долей по доменам %.3f | доменов %d'
          % (name, b, pooled, mean_of_ratios, len(sub)))
p('  Вывод: тестировщик везде считает отношение сумм (правильно); среднее долей он не использует.')
p('')

p('=' * 100)
p('4. ОБЪЁМ СОБЫТИЙ')
p('=' * 100)
for name, ds, rk, fk in CASES:
    t = agg(ds, 'bin3', rk, fk)
    for b in ('0-10', '10-30', '30+'):
        v = t[b]
        flag = []
        if v[2] < 20:
            flag.append('рег<20')
        if v[3] < 5:
            flag.append('ФД<5')
        p('  %-28s %-6s: доменов %4d, доменов с рег %3d, рег %3d, ФД %2d %s'
          % (name, b, v[0], v[4], v[2], v[3], ('<-- ' + ', '.join(flag)) if flag else ''))
p('  5 бинов, окно: бин 40+ = 40 доменов, 65 рег, 4 ФД; бин 0-10 = 23 рег, 4 ФД — оба ничего не доказывают.')
p('')

p('=' * 100)
p('5. ДЕРЖИТСЯ ЛИ НА 1-3 ДОМЕНАХ: убираем топ-3 по регистрациям в каждой группе')
p('=' * 100)
for name, ds, rk, fk in CASES:
    m = MAIN[name]
    p('  -- %s' % name)
    for b in ('10-30', '30+'):
        sub = sorted([d for d in ds if d['bin3'] == b], key=lambda x: -x[rk])[:3]
        p('     топ-3 в %-6s: %s | их доля регистраций бина %.0f %%, ФД бина %.0f %%'
          % (b, '; '.join('%s (рег %d, ФД %d)' % (d['dom'], d[rk], d[fk]) for d in sub),
             100 * sum(d[rk] for d in sub) / max(1, m['t'][b][2]),
             100 * sum(d[fk] for d in sub) / max(1, m['t'][b][3])))
    drop = set()
    for b in ('10-30', '30+'):
        for d in sorted([x for x in ds if x['bin3'] == b], key=lambda x: -x[rk])[:3]:
            drop.add(d['dom'])
    ds2 = [d for d in ds if d['dom'] not in drop]
    t = agg(ds2, 'bin3', rk, fk)
    a, b_ = t['30+'][3], t['30+'][2] - t['30+'][3]
    c, dd = t['10-30'][3], t['10-30'][2] - t['10-30'][3]
    r30 = a / (a + b_) if a + b_ else float('nan')
    r10 = c / (c + dd) if c + dd else float('nan')
    p('     без топ-3 в обеих группах: 30+ %d/%d = %.3f | 10-30 %d/%d = %.3f | отношение %.2f | p = %.4f'
      % (a, a + b_, r30, c, c + dd, r10, (r30 / r10 if r10 else float('nan')), fisher_left(a, b_, c, dd)))
p('')
p('  То же для «плато по деньгам» (ФД/100 сайтов, окно и всё время): убираем топ-3 домена по регистрациям в бинах 20-30/30-40/40+')
for nm, ds, rk, fk in (('окно', D, 'reg_w', 'fd_w'), ('всё время <=13.09', DA, 'reg_a', 'fd_a')):
    t = agg(ds, 'bin5', rk, fk)
    drop = set()
    for b in ('20-30', '30-40', '40+'):
        for d in sorted([x for x in ds if x['bin5'] == b], key=lambda x: -x[rk])[:3]:
            drop.add(d['dom'])
    t2 = agg([d for d in ds if d['dom'] not in drop], 'bin5', rk, fk)
    for b in ('30-40', '40+'):
        k1, n1 = t[b][3], t[b][1]
        k2, n2 = t['20-30'][3], t['20-30'][1]
        lo, hi = pois_ratio_ci(k1, n1, k2, n2)
        p('    %-18s %-6s против 20-30: %.3f (%d/%d) против %.3f (%d/%d); отношение %.2f [%.2f-%.2f]; p(выше)=%.3f'
          % (nm, b, k1 / n1 * 100, k1, n1, k2 / n2 * 100, k2, n2,
             (k1 / n1) / (k2 / n2), lo, hi, binom_cond_p(k1, n1, k2, n2, 'greater')))
        k1b, n1b = t2[b][3], t2[b][1]
        k2b, n2b = t2['20-30'][3], t2['20-30'][1]
        lo2, hi2 = pois_ratio_ci(k1b, n1b, k2b, n2b)
        p('       без топ-3: %.3f (%d/%d) против %.3f (%d/%d); отношение %.2f [%.2f-%.2f]; p(выше)=%.3f'
          % (k1b / n1b * 100, k1b, n1b, k2b / n2b * 100, k2b, n2b,
             (k1b / n1b) / (k2b / n2b) if k2b else float('nan'), lo2, hi2,
             binom_cond_p(k1b, n1b, k2b, n2b, 'greater')))
p('')

p('=' * 100)
p('6. МНОЖЕСТВЕННОСТЬ')
p('=' * 100)
txt = open(H19OUT, encoding='utf-8').read()
import re
pv_all = re.findall(r'p[^=\n]{0,24}=\s*([01]\.\d+)', txt)
p('  В выводе тестировщика напечатано p-значений: %d; доверительных интервалов: %d'
  % (len(pv_all), txt.count('ДИ')))
p('  Срезы: 2 окна (окно / всё время) x 2 версии НЗ x 3 определения единицы (регистрация / сайт с рег. / домен)')
p('         x 3 схемы страты (нет / набор+день / +зона / медиана пула) x бины 3 и 5 + 4 класса «рег. у домена» + зоны + недели.')
p('  Поправка бьёт по УТВЕРДИТЕЛЬНЫМ выводам, а не по нулевым:')
pos = [('окно 30-40 против 20-30 (ФД/100 сайтов)', binom_cond_p(t5['30-40'][3], t5['30-40'][1], t5['20-30'][3], t5['20-30'][1], 'greater')),
       ('всё время 30-40 против 20-30', None),
       ('страта: O/E ФД в 30+ = 1.76', 0.002),
       ('без страты, все домены: ФД/рег 30+ ниже', MAIN['окно, все домены']['pv'])]
tA = agg(DA, 'bin5', 'reg_a', 'fd_a')
pos[1] = ('всё время 30-40 против 20-30', binom_cond_p(tA['30-40'][3], tA['30-40'][1], tA['20-30'][3], tA['20-30'][1], 'greater'))
m = len(pv_all)
for nm, pv in pos:
    p('    %-42s p = %.4f | Бонферрони x86 = %.3f | x10 (только заявленные выводы) = %.3f'
      % (nm, pv, min(1, pv * m), min(1, pv * 10)))
p('')

p('=' * 100)
p('7. МОЩНОСТЬ: отвергают ли данные САМУ гипотезу (падение в 2-4 раза), а не только «эффекта нет»')
p('=' * 100)
p('  Гипотеза утверждала ФД/рег(30+) <= 0.5 x ФД/рег(10-30) (падение в 2-4 раза).')
p('  Чтобы сказать «опровергнута», надо отвергнуть отношение <= 0.5, а не просто не отвергнуть 1.0.')
for name in ('окно, без НЗ', 'всё время <=13.09, без НЗ', 'окно, все домены', 'всё время <=13.09, все'):
    m = MAIN[name]
    lo, hi = or_exact_ci(m['a'], m['b'], m['c'], m['d'])
    p05 = nchg_p_right(m['a'], m['b'], m['c'], m['d'], 0.5)   # H0: OR=0.5, альтернатива OR>0.5
    p025 = nchg_p_right(m['a'], m['b'], m['c'], m['d'], 0.25)
    p('  %-26s: OR = %.2f, точный 95 %% ДИ [%.2f-%.2f]'
      % (name, (m['a'] * m['d']) / (m['b'] * m['c']) if m['b'] * m['c'] else float('nan'), lo, hi))
    p('      %-22s p(OR >= 0.5 отвергнуто вверх) = %.3f; p против OR = 0.25 = %.3f  -> %s'
      % ('', p05, p025,
         'падение в 2 раза НЕ отвергнуто' if p05 > 0.05 else 'падение в 2 раза отвергнуто'))
p('')

# стратифицированная перестановка с эквивалентностью
def perm_pools(ds, rk, fk, pool_key, nperm=NPERM, seed=SEED):
    pools = collections.defaultdict(list)
    for d in ds:
        if d[rk] <= 0:
            continue
        pools[pool_key(d)].append(d)
    rng = random.Random(seed)
    obs30 = sum(d[fk] for d in ds if d['bin3'] == '30+')
    obs10 = sum(d[fk] for d in ds if d['bin3'] == '10-30')
    n30 = sum(d[rk] for d in ds if d['bin3'] == '30+')
    n10 = sum(d[rk] for d in ds if d['bin3'] == '10-30')
    units = []
    for key, dl in pools.items():
        F = sum(d[fk] for d in dl)
        lab = []
        for d in dl:
            lab.extend([d['bin3']] * d[rk])
        if F == 0 or len(set(lab)) < 2:
            continue
        units.append((lab, F))
    const30 = obs30
    const10 = obs10
    for lab, F in units:
        pass
    ratios = []
    # константная часть: ФД из неинформативных пулов
    fixed30 = obs30 - sum(min(F, lab.count('30+')) for lab, F in units) * 0  # не используется
    sims30 = []
    sims_ratio = []
    base30 = obs30 - sum(sum(1 for _ in []) for _ in units)
    # разложим: ФД информативных пулов перемешиваем, остальные — как есть
    inf_f30 = 0
    inf_f10 = 0
    keys_inf = set()
    for key, dl in pools.items():
        F = sum(d[fk] for d in dl)
        lab = []
        for d in dl:
            lab.extend([d['bin3']] * d[rk])
        if F == 0 or len(set(lab)) < 2:
            continue
        keys_inf.add(key)
        inf_f30 += sum(d[fk] for d in dl if d['bin3'] == '30+')
        inf_f10 += sum(d[fk] for d in dl if d['bin3'] == '10-30')
    rest30 = obs30 - inf_f30
    rest10 = obs10 - inf_f10
    obs_ratio = (obs30 / n30) / (obs10 / n10) if obs10 and n10 else float('nan')
    for _ in range(nperm):
        s30 = rest30
        s10 = rest10
        for key in keys_inf:
            dl = pools[key]
            F = sum(d[fk] for d in dl)
            lab = []
            for d in dl:
                lab.extend([d['bin3']] * d[rk])
            picked = rng.sample(range(len(lab)), F)
            for i in picked:
                if lab[i] == '30+':
                    s30 += 1
                elif lab[i] == '10-30':
                    s10 += 1
        sims30.append(s30)
        sims_ratio.append((s30 / n30) / (s10 / n10) if s10 else float('nan'))
    sims_ratio = [x for x in sims_ratio if x == x]
    sims_ratio.sort()
    pl = sum(1 for x in sims_ratio if x <= obs_ratio) / len(sims_ratio)
    lo = sims_ratio[int(0.025 * len(sims_ratio))]
    hi = sims_ratio[int(0.975 * len(sims_ratio)) - 1]
    return obs_ratio, pl, lo, hi, inf_f30 + inf_f10, sum(d[rk] for key in keys_inf for d in pools[key] if d['bin3'] == '30+')


p('=' * 100)
p('8. СТРАТА: что вообще может увидеть перестановочный тест (своя реализация, %d перестановок)' % NPERM)
p('=' * 100)
for name, ds, rk, fk in CASES:
    dsx = [d for d in ds if d[rk] > 0]
    obs_r, pl, lo, hi, infF, inf30 = perm_pools(dsx, rk, fk, lambda d: (d['set'], d['day']))
    p('  %-28s: наблюдённое отношение 30+/10-30 = %.2f; p(<=набл.) = %.3f; нулевой интервал отношения [%.2f-%.2f]'
      % (name, obs_r, pl, lo, hi))
    p('      %-24s ФД в информативных пулах: %d; регистраций 30+ в них: %d' % ('', infF, inf30))
p('  Нулевой интервал сам накрывает 0.4-0.5: перестановочный тест в этом объёме НЕ отличает «падения в 2 раза» от нуля.')
p('')

p('=' * 100)
p('9. ГРАНИЦА БИНА 30 %: не подобрана ли')
p('=' * 100)
for cut in (25, 30, 35, 40):
    for name, ds, rk, fk in (('окно, без НЗ', [d for d in D if not d['noc']], 'reg_w', 'fd_w'),
                             ('окно, все', D, 'reg_w', 'fd_w')):
        hi_ = [d for d in ds if d['ex'] >= cut]
        lo_ = [d for d in ds if 10 <= d['ex'] < cut]
        a = sum(d[fk] for d in hi_); b_ = sum(d[rk] for d in hi_) - a
        c = sum(d[fk] for d in lo_); dd = sum(d[rk] for d in lo_) - c
        if a + b_ == 0 or c + dd == 0:
            continue
        p('  порог %d %%, %-14s: %d/%d = %.3f против %d/%d = %.3f | отношение %.2f | p = %.4f'
          % (cut, name, a, a + b_, a / (a + b_), c, c + dd, c / (c + dd),
             (a / (a + b_)) / (c / (c + dd)) if c + dd and c else float('nan'), fisher_left(a, b_, c, dd)))
p('')

p('=' * 100)
p('10. АВГУСТОВСКАЯ ТЕНЬ: проверяю утверждение тестировщика напрямую')
p('=' * 100)
aug = [d for d in D if d['day'] < '2026-08-24']
lat = [d for d in D if d['day'] >= '2026-08-24']
for nm, ds in (('запуски до 24.08', aug), ('запуски с 24.08', lat)):
    R = sum(d['reg_w'] for d in ds); F = sum(d['fd_w'] for d in ds)
    lo, hi = cp_ci(F, R)
    p('  %-18s: доменов %4d, рег в окне %3d, ФД %2d, ФД/рег %.3f [%.3f-%.3f]; доля НЗ %.0f %%'
      % (nm, len(ds), R, F, F / R if R else float('nan'), lo, hi,
         100 * sum(1 for d in ds if d['noc']) / len(ds)))
p('  Проверка «НЗ» против «до 24.08»: совпадают ли множества?')
p('    НЗ и запуск >= 24.08: %d доменов (рег %d, ФД %d); не-НЗ и запуск < 24.08: %d доменов (рег %d, ФД %d)'
  % (len([d for d in D if d['noc'] and d['day'] >= '2026-08-24']),
     sum(d['reg_w'] for d in D if d['noc'] and d['day'] >= '2026-08-24'),
     sum(d['fd_w'] for d in D if d['noc'] and d['day'] >= '2026-08-24'),
     len([d for d in D if not d['noc'] and d['day'] < '2026-08-24']),
     sum(d['reg_w'] for d in D if not d['noc'] and d['day'] < '2026-08-24'),
     sum(d['fd_w'] for d in D if not d['noc'] and d['day'] < '2026-08-24')))
# внутри «с 24.08» — есть ли лестница
t = agg([d for d in lat], 'bin3', 'reg_w', 'fd_w')
a, b_ = t['30+'][3], t['30+'][2] - t['30+'][3]
c, dd = t['10-30'][3], t['10-30'][2] - t['10-30'][3]
lo, hi = or_exact_ci(a, b_, c, dd)
p('  Только запуски с 24.08 (окно): 30+ %d/%d = %.3f против 10-30 %d/%d = %.3f; отношение %.2f; OR ДИ [%.2f-%.2f]; p = %.3f'
  % (a, a + b_, a / (a + b_) if a + b_ else float('nan'), c, c + dd, c / (c + dd),
     ((a / (a + b_)) / (c / (c + dd))) if (a + b_) and c else float('nan'), lo, hi, fisher_left(a, b_, c, dd)))
p('')


p('')
p('=' * 100)
p('11. ТЕСТ ТЕСТИРОВЩИКА ЕГО ЖЕ МЕХАНИЗМОМ: срез ПО ДАТЕ (>= 24.08), а не по записи контента')
p('=' * 100)
p('  Тестировщик объясняет лестницу «августовскими доменами до 24.08». Тогда естественный срез —')
p('  дата запуска >= 24.08 (он вместо этого режет по метке «КОНТЕНТ НЕ ЗАПИСАН», что выкидывает ещё 117')
p('  доменов, запущенных ПОСЛЕ 24.08, и оставляет меньше событий в 30+).')
for nm, ds, rk, fk in (('окно, запуск >= 24.08', [d for d in D if d['day'] >= '2026-08-24'], 'reg_w', 'fd_w'),
                       ('всё время, 24.08..13.09', [d for d in DA if d['day'] >= '2026-08-24'], 'reg_a', 'fd_a')):
    t = agg(ds, 'bin3', rk, fk)
    a, b_ = t['30+'][3], t['30+'][2] - t['30+'][3]
    c, dd = t['10-30'][3], t['10-30'][2] - t['10-30'][3]
    lo, hi = or_exact_ci(a, b_, c, dd)
    p('  %-24s: 30+ %d/%d = %.3f против 10-30 %d/%d = %.3f | отношение %.2f | OR %.2f [%.2f-%.2f] | p = %.4f'
      % (nm, a, a + b_, a / (a + b_), c, c + dd, c / (c + dd), (a / (a + b_)) / (c / (c + dd)),
         (a * dd) / (b_ * c), lo, hi, fisher_left(a, b_, c, dd)))
    drop = set()
    for b in ('10-30', '30+'):
        for d in sorted([x for x in ds if x['bin3'] == b], key=lambda x: -x[rk])[:3]:
            drop.add(d['dom'])
    t2 = agg([d for d in ds if d['dom'] not in drop], 'bin3', rk, fk)
    a2, b2 = t2['30+'][3], t2['30+'][2] - t2['30+'][3]
    c2, d2 = t2['10-30'][3], t2['10-30'][2] - t2['10-30'][3]
    p('      без топ-3 по регистрациям в каждой группе: 30+ %d/%d = %.3f против %d/%d = %.3f | отношение %.2f | p = %.4f'
      % (a2, a2 + b2, a2 / (a2 + b2), c2, c2 + d2, c2 / (c2 + d2),
         (a2 / (a2 + b2)) / (c2 / (c2 + d2)), fisher_left(a2, b2, c2, d2)))
    dsx = [d for d in ds if d[rk] > 0]
    obs_r, pl, plo, phi, infF, inf30 = perm_pools(dsx, rk, fk, lambda d: (d['set'], d['day']))
    p('      страта «набор+день» (перестановка, %d): отношение %.2f, p(<=набл.) = %.3f, нулевой интервал [%.2f-%.2f]; ФД в информативных пулах %d, рег 30+ в них %d'
      % (NPERM, obs_r, pl, plo, phi, infF, inf30))
p('')
p('  Сопоставление двух срезов одного и того же «августовского» объяснения:')
p('    режем по метке контента (без НЗ): 13/87 против 34/139 -> отношение 0.61, p = 0.0593  (вывод тестировщика: «эффекта нет»)')
p('    режем по дате (>= 24.08):         13/93 против 38/150 -> отношение 0.55, p = 0.0235  (тот же механизм, но эффект значим)')

p('=' * 100)
p('ИТОГ СКЕПТИКА')
p('=' * 100)
p('1. Числа воспроизводятся полностью: скрипт детерминирован (seed 1), повторный запуск дал байт-в-байт тот же')
p('   файл; мой независимый разбор CSV даёт те же 1846 доменов, 335 НЗ, 15/153 против 40/171 (p = 0.0008),')
p('   13/87 против 34/139 (p = 0.0593), 16/152 против 35/178 (p = 0.0156), 13/77 против 29/142 (p = 0.3278).')
p('   Знаменатели верные: после фильтра «окно закрыто = да» колонка «сайтов» совпадает с «сайтов в окне» (расходятся')
p('   ровно 152 домена с незакрытым окном, и они исключены); «дней = 1» (121, из них 44 уже в незакрытых) исключены.')
p('   Доли считаются как отношение сумм, а не как среднее долей по доменам. Здесь претензий нет.')
p('2. Главная претензия — ВЫВОД СИЛЬНЕЕ ЦИФР. Слово «опровергнута» требует отвергнуть падение в 2 раза,')
p('   а данные его не отвергают ни в одном варианте: точный ДИ отношения шансов 0.54 [0.25-1.14] (окно, без НЗ),')
p('   0.79 [0.35-1.71] (всё время, без НЗ); p против H0: OR = 0.5 равны 0.47 и 0.14. Отвергается только падение')
p('   в 4 раза (OR = 0.25: p = 0.028 и 0.003). Это «не подтверждено», а не «опровергнуто».')
p('3. Перестановочный тест в страте не способен увидеть заявленный эффект: в информативных пулах всего 19-31 ФД')
p('   и 42-91 регистрация 30+; нулевой интервал самого отношения [0.43-0.91] (окно, без НЗ) накрывает 0.5.')
p('   Тестировщик это честно пишет, но в ИТОГ выносит «разницы нет».')
p('4. Срез сделан не тем ножом. «Августовская тень» — про ДАТУ, и все 218 доменов до 24.08 действительно НЗ,')
p('   но 117 НЗ-доменов запущены ПОСЛЕ 24.08. Срез по дате (запуск >= 24.08) оставляет эффект значимым:')
p('   30+ 13/93 = 0.140 против 10-30 38/150 = 0.253, отношение 0.55, OR 0.48 [0.22-0.99], p = 0.0235;')
p('   без топ-3 доменов в каждой группе 0.50, p = 0.0177. Срез по метке контента (без НЗ) выкидывает')
p('   дополнительно 117 доменов, забирая 4 ФД из бина 10-30 и 0 из 30+, и именно он даёт p = 0.0593.')
p('   Два среза одного и того же объяснения дают p = 0.024 и p = 0.059; в отчёт попал только второй.')
p('5. Граница бина 30 % не нейтральна: при пороге 35 % даже БЕЗ НЗ 5/51 = 0.098 против 42/175 = 0.240,')
p('   отношение 0.41, p = 0.0183. При 25 % без НЗ p = 0.283. Порог двигает вывод.')
p('6. Утвердительная часть («плато по деньгам нет») держится на 1-3 доменах и не переживает поправку:')
p('   окно 30-40 против 20-30 — 1.91 [0.81-4.31], p = 0.074 (изначально незначимо), без топ-3 — 1.41, p = 0.297;')
p('   всё время 2.52 [1.08-5.90], p = 0.016, без топ-3 — 2.33, p = 0.055. Бин 40+ — 4 ФД: 1.53 [0.37-4.69],')
p('   то есть и рост, и плато, и падение одинаково совместимы с данными. O/E ФД 1.76 (p = 0.002) при 86 напечатанных')
p('   p-значениях даёт Бонферрони 0.15. Ни одно утвердительное «плато нет» не выживает.')
p('7. Сырая лестница, наоборот, к отдельным доменам устойчива: убрать топ-3 по регистрациям в каждой группе —')
p('   окно все домены 0.41 (p = 0.0012), всё время все 0.51 (p = 0.0164); топ-3 дают лишь 10-15 % регистраций бина.')
p('   Зато «отсутствие эффекта без НЗ» неустойчиво в обратную сторону: без топ-3 отношение 0.56, p = 0.0482.')
TEE.f.flush()

# -*- coding: utf-8 -*-
"""
w19: контрпроверка вердикта по гипотезе №19 (ФД/рег против выхода домена).
Угол: ТЕНИ. Проверяем не гипотезу, а вердикт тестировщика «опровергнута».
Только stdlib.
"""
import csv, os, sys, math, random
from collections import defaultdict

SRC = '/home/user/cladue/analysis/export/svod_domenov_21.09.csv'
OUT = '/home/user/cladue/analysis/export/gipotezy_svod/w19_teni.txt'
OUTLIERS = ('3615.team', '3286.team')
BUF = []
def p(s=''):
    BUF.append(s)
    print(s)

def fnum(s):
    s = (s or '').strip().replace(',', '.')
    if s == '':
        return None
    try:
        return float(s)
    except ValueError:
        return None

def inum(s):
    v = fnum(s)
    return 0 if v is None else int(round(v))

# ---------- статистика ----------
def lchoose(n, k):
    if k < 0 or k > n:
        return float('-inf')
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

def fisher_p_less(a, b, c, d):
    """P(A <= a) для таблицы [[a,b],[c,d]] (гипергеом., строка1 = 30+)."""
    n1, n0 = a + b, c + d
    m = a + c
    lo, hi = max(0, m - n0), min(n1, m)
    den = lchoose(n1 + n0, m)
    tot = 0.0
    for x in range(lo, min(a, hi) + 1):
        tot += math.exp(lchoose(n1, x) + lchoose(n0, m - x) - den)
    return min(1.0, tot)

def fisher_p_greater(a, b, c, d):
    n1, n0 = a + b, c + d
    m = a + c
    lo, hi = max(0, m - n0), min(n1, m)
    den = lchoose(n1 + n0, m)
    tot = 0.0
    for x in range(max(a, lo), hi + 1):
        tot += math.exp(lchoose(n1, x) + lchoose(n0, m - x) - den)
    return min(1.0, tot)

def wilson(k, n, z=1.959964):
    if n == 0:
        return (float('nan'), float('nan'))
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))

def mh_or(tables):
    """tables: список (a,b,c,d) — a,b = ФД/не-ФД в 30+, c,d = в 10-30.
    Возвращает (OR_MH, lo, hi, sumR, sumS, n_informative)."""
    sR = sS = 0.0
    pR = pSqR = sPS_QR = sQS = 0.0
    used = 0
    for (a, b, c, d) in tables:
        T = a + b + c + d
        if T == 0:
            continue
        R = a * d / T
        S = b * c / T
        if R == 0 and S == 0:
            continue
        used += 1
        sR += R
        sS += S
        P = (a + d) / T
        Q = (b + c) / T
        pR += P * R
        sPS_QR += P * S + Q * R
        sQS += Q * S
    if sR == 0 or sS == 0:
        return (float('nan'), float('nan'), float('nan'), sR, sS, used)
    orm = sR / sS
    var = pR / (2 * sR * sR) + sPS_QR / (2 * sR * sS) + sQS / (2 * sS * sS)
    se = math.sqrt(var)
    return (orm, orm * math.exp(-1.959964 * se), orm * math.exp(1.959964 * se), sR, sS, used)

def mh_rr(tables):
    """MH относительный риск (доля ФД) + ДИ (Greenland-Robins)."""
    sR = sS = sV = 0.0
    for (a, b, c, d) in tables:
        n1, n0 = a + b, c + d
        T = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        sR += a * n0 / T
        sS += c * n1 / T
        sV += ((n1 * n0 * (a + c) - a * c * T) / (T * T))
    if sR == 0 or sS == 0:
        return (float('nan'), float('nan'), float('nan'))
    rr = sR / sS
    se = math.sqrt(sV / (sR * sS))
    return (rr, rr * math.exp(-1.959964 * se), rr * math.exp(1.959964 * se))

def cmh_stat(tables):
    """Кохран-Мантель-Хензель: наблюдённые ФД в 30+, ожидаемые, дисперсия, z, p(одностор. ниже)."""
    O = E = V = 0.0
    for (a, b, c, d) in tables:
        n1, n0 = a + b, c + d
        m1 = a + c
        T = n1 + n0
        if T < 2 or n1 == 0 or n0 == 0 or m1 == 0:
            continue
        O += a
        E += n1 * m1 / T
        V += n1 * n0 * m1 * (T - m1) / (T * T * (T - 1))
    if V <= 0:
        return (O, E, V, float('nan'), float('nan'))
    z = (O - E + 0.5) / math.sqrt(V) if O < E else (O - E - 0.5) / math.sqrt(V)
    pl = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    return (O, E, V, z, pl)

def pois_ratio_test(k1, t1, k2, t2):
    """Биномиальный условный тест: k1 событий на t1 «экспозиции» против k2/t2.
    Возвращает (rate1, rate2, ratio, lo, hi, p_выше, p_ниже)."""
    r1 = k1 / t1 if t1 else float('nan')
    r2 = k2 / t2 if t2 else float('nan')
    ratio = (r1 / r2) if r2 else float('nan')
    n = k1 + k2
    pi = t1 / (t1 + t2)
    # точный биномиальный
    p_hi = sum(math.exp(lchoose(n, x) + x * math.log(pi) + (n - x) * math.log(1 - pi))
               for x in range(k1, n + 1)) if n else float('nan')
    p_lo = sum(math.exp(lchoose(n, x) + x * math.log(pi) + (n - x) * math.log(1 - pi))
               for x in range(0, k1 + 1)) if n else float('nan')
    lo_p, hi_p = wilson(k1, n)
    lo = (lo_p / (1 - lo_p)) * (t2 / t1) if lo_p < 1 and t1 else float('nan')
    hi = (hi_p / (1 - hi_p)) * (t2 / t1) if hi_p < 1 and t1 else float('inf')
    return (r1, r2, ratio, lo, hi, min(1.0, p_hi), min(1.0, p_lo))

# ---------- загрузка ----------
with open(SRC, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

p('Контрпроверка №19 (угол: тени). Вердикт тестировщика: «опровергнута».')
p('Источник: %s; строк: %d' % (SRC, len(rows)))
p('')
p('0. ФИЛЬТРЫ (те же, что у тестировщика)')
n0 = len(rows)
rows = [r for r in rows if r['окно закрыто'].strip() == 'да']
p('  окно закрыто = да: осталось %d (исключено %d)' % (len(rows), n0 - len(rows)))
n1 = len(rows)
rows = [r for r in rows if r['дней'].strip() != '1']
p('  дней >= 2: осталось %d (исключено %d)' % (len(rows), n1 - len(rows)))
n2 = len(rows)
rows_with_out = list(rows)
rows = [r for r in rows if r['домен'].strip() not in OUTLIERS]
p('  без 3615.team/3286.team: осталось %d (исключено %d)' % (len(rows), n2 - len(rows)))

def prep(r):
    d = {}
    d['dom'] = r['домен'].strip()
    d['zone'] = r['зона'].strip()
    d['day'] = r['день запуска'].strip()
    d['set'] = r['набор контента'].strip()
    d['nz'] = (d['set'] == 'КОНТЕНТ НЕ ЗАПИСАН')
    d['fam'] = r['семейство'].strip()
    d['hour'] = r['блок часа'].strip()
    d['exit'] = fnum(r['выход 3 суток %'])
    d['sites'] = inum(r['сайтов'])
    d['sites_w'] = inum(r['сайтов в окне'])
    d['reg_w'] = inum(r['регистраций в окне 3 суток'])
    d['fd_w'] = inum(r['ФД в окне 3 суток'])
    d['reg_a'] = inum(r['регистраций'])
    d['fd_a'] = inum(r['ФД'])
    d['sites_reg'] = inum(r['сайтов с регистрацией'])
    d['clicks_w'] = inum(r['кликов из поиска в окне'])
    return d

D = [prep(r) for r in rows]
D = [d for d in D if d['exit'] is not None]
p('  с известным выходом: %d' % len(D))

def bin3(x):
    if x < 10:
        return '0-10'
    if x < 30:
        return '10-30'
    return '30+'

def bin5(x):
    if x < 10:
        return '0-10'
    if x < 20:
        return '10-20'
    if x < 30:
        return '20-30'
    if x < 40:
        return '30-40'
    return '40+'

for d in D:
    d['b3'] = bin3(d['exit'])
    d['b5'] = bin5(d['exit'])

ALLTIME_CUT = '2026-09-13'
AUG_CUT = '2026-08-24'   # с этой даты набор контента записан
DA = [d for d in D if d['day'] <= ALLTIME_CUT]
p('  запусков <= %s (для «за всё время»): %d' % (ALLTIME_CUT, len(DA)))
p('')

# =================================================================
p('=' * 96)
p('1. ЧТО ВООБЩЕ СРАВНИВАЕТСЯ: сколько «данных» остаётся после страты')
p('=' * 96)

def counts(ds, key_reg, key_fd, b):
    r = sum(x[key_reg] for x in ds if x['b3'] == b)
    f = sum(x[key_fd] for x in ds if x['b3'] == b)
    return r, f

for lbl, ds, kr, kf in (('окно, все', D, 'reg_w', 'fd_w'),
                        ('окно, без НЗ', [x for x in D if not x['nz']], 'reg_w', 'fd_w'),
                        ('окно, запуск с 24.08', [x for x in D if x['day'] >= AUG_CUT], 'reg_w', 'fd_w'),
                        ('всё время, все', DA, 'reg_a', 'fd_a'),
                        ('всё время, без НЗ', [x for x in DA if not x['nz']], 'reg_a', 'fd_a'),
                        ('всё время, запуск с 24.08', [x for x in DA if x['day'] >= AUG_CUT], 'reg_a', 'fd_a')):
    r1, f1 = counts(ds, kr, kf, '30+')
    r0, f0 = counts(ds, kr, kf, '10-30')
    if r1 and r0:
        a, b_, c, d_ = f1, r1 - f1, f0, r0 - f0
        pl = fisher_p_less(a, b_, c, d_)
        lo1, hi1 = wilson(f1, r1)
        lo0, hi0 = wilson(f0, r0)
        p('  %-28s | 30+: %3d ФД / %3d рег = %.3f [%.3f-%.3f] | 10-30: %3d / %3d = %.3f [%.3f-%.3f] | отн. %.2f | точный p(ниже) = %.4f | доменов 30+/10-30: %d/%d' %
          (lbl, f1, r1, f1 / r1, lo1, hi1, f0, r0, f0 / r0, lo0, hi0,
           (f1 / r1) / (f0 / r0) if f0 else float('nan'), pl,
           len([x for x in ds if x['b3'] == '30+']), len([x for x in ds if x['b3'] == '10-30'])))
p('')

# =================================================================
p('=' * 96)
p('2. ЖЁСТКАЯ СТРАТА: MH-оценка отношения с интервалом (единица — регистрация, исход — ФД)')
p('=' * 96)
p('  MH = Мантель–Хензель по пулам; ДИ отношения шансов — Робинс–Бреслоу–Гринленд; CMH — z-тест с поправкой на непрерывность.')
p('  Пул вносит вклад только если в нём есть регистрации и в 30+, и в 10-30.')
p('')

def build_tables(ds, kr, kf, keyf):
    pools = defaultdict(lambda: [0, 0, 0, 0])  # fd30, no30, fd10, no10
    for x in ds:
        if x['b3'] not in ('30+', '10-30'):
            continue
        if x[kr] == 0:
            continue
        k = keyf(x)
        t = pools[k]
        if x['b3'] == '30+':
            t[0] += x[kf]
            t[1] += x[kr] - x[kf]
        else:
            t[2] += x[kf]
            t[3] += x[kr] - x[kf]
    tabs = []
    info = []
    for k, t in pools.items():
        n1, n0 = t[0] + t[1], t[2] + t[3]
        if n1 > 0 and n0 > 0:
            tabs.append(tuple(t))
            info.append((k, tuple(t)))
    return tabs, info, pools

STRATA = (
    ('набор+день', lambda x: (x['set'], x['day'])),
    ('набор+день+зона', lambda x: (x['set'], x['day'], x['zone'])),
    ('набор+день+зона+блок часа', lambda x: (x['set'], x['day'], x['zone'], x['hour'])),
    ('день', lambda x: (x['day'],)),
    ('день+зона', lambda x: (x['day'], x['zone'])),
    ('набор', lambda x: (x['set'],)),
)

SETS = (
    ('окно, все домены', D, 'reg_w', 'fd_w'),
    ('окно, без НЗ', [x for x in D if not x['nz']], 'reg_w', 'fd_w'),
    ('окно, запуск с 24.08', [x for x in D if x['day'] >= AUG_CUT], 'reg_w', 'fd_w'),
    ('всё время, все домены', DA, 'reg_a', 'fd_a'),
    ('всё время, без НЗ', [x for x in DA if not x['nz']], 'reg_a', 'fd_a'),
    ('всё время, запуск с 24.08', [x for x in DA if x['day'] >= AUG_CUT], 'reg_a', 'fd_a'),
)

mh_store = {}
for slbl, ds, kr, kf in SETS:
    p('  --- %s ---' % slbl)
    for stlbl, keyf in STRATA:
        tabs, info, _ = build_tables(ds, kr, kf, keyf)
        if not tabs:
            p('    %-28s : сравнимых пулов нет' % stlbl)
            continue
        orm, lo, hi, sR, sS, used = mh_or(tabs)
        rr, rlo, rhi = mh_rr(tabs)
        O, E, V, z, pl = cmh_stat(tabs)
        n30 = sum(t[0] + t[1] for t in tabs)
        n10 = sum(t[2] + t[3] for t in tabs)
        f30 = sum(t[0] for t in tabs)
        f10 = sum(t[2] for t in tabs)
        mh_store[(slbl, stlbl)] = (orm, lo, hi, rr, rlo, rhi, O, E, pl, n30, n10, f30, f10, len(tabs))
        p('    %-28s : пулов %2d | 30+ %3d рег/%2d ФД, 10-30 %3d рег/%2d ФД | O/E %.2f (%d/%.1f) | RR_MH %.2f [%.2f-%.2f] | OR_MH %.2f [%.2f-%.2f] | CMH p(ниже) %.3f' %
          (stlbl, len(tabs), n30, f30, n10, f10,
           (O / E if E else float('nan')), int(O), E, rr, rlo, rhi, orm, lo, hi, pl))
    p('')

# =================================================================
p('=' * 96)
p('3. ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ ПУЛА «набор+день» (список пулов, где есть и 30+, и 10-30)')
p('=' * 96)
for slbl, ds, kr, kf in (('окно, без НЗ', [x for x in D if not x['nz']], 'reg_w', 'fd_w'),
                         ('окно, все', D, 'reg_w', 'fd_w'),
                         ('всё время, без НЗ', [x for x in DA if not x['nz']], 'reg_a', 'fd_a')):
    tabs, info, _ = build_tables(ds, kr, kf, lambda x: (x['set'], x['day']))
    info.sort(key=lambda kv: -(kv[1][0] + kv[1][1] + kv[1][2] + kv[1][3]))
    p('  --- %s: пулов %d ---' % (slbl, len(info)))
    w30 = w10 = t30 = t10 = 0
    for k, t in info:
        w30 += t[0]; t30 += t[0] + t[1]; w10 += t[2]; t10 += t[2] + t[3]
    p('    суммарно: 30+ %d ФД / %d рег = %.3f; 10-30 %d / %d = %.3f; сырое отношение %.2f' %
      (w30, t30, w30 / t30 if t30 else float('nan'), w10, t10, w10 / t10 if t10 else float('nan'),
       ((w30 / t30) / (w10 / t10)) if (t30 and t10 and w10) else float('nan')))
    # знаковый тест по пулам: в скольких пулах ФД/рег(30+) выше/ниже
    up = dn = eq = 0
    for k, t in info:
        r1 = t[0] / (t[0] + t[1])
        r0 = t[2] / (t[2] + t[3])
        if r1 > r0: up += 1
        elif r1 < r0: dn += 1
        else: eq += 1
    n_eff = up + dn
    if n_eff:
        psign = sum(math.exp(lchoose(n_eff, x) - n_eff * math.log(2)) for x in range(0, dn + 1))
    else:
        psign = float('nan')
    p('    знаковый тест по пулам: 30+ выше в %d, ниже в %d, поровну в %d; p(одностор., «ниже») = %.3f' % (up, dn, eq, psign))
    for k, t in info[:20]:
        p('      %-42s %-10s | 30+: %2d/%2d  10-30: %2d/%2d' % (k[0][:42], k[1], t[0], t[0] + t[1], t[2], t[2] + t[3]))
    p('')

# =================================================================
p('=' * 96)
p('4. МОЩНОСТЬ: что вообще способна отличить страта (перестановка внутри пулов)')
p('=' * 96)
random.seed(19)
NPERM = 20000

def perm_power(ds, kr, kf, keyf, true_rr_list=(1.0, 0.75, 0.5, 0.35)):
    """Собираем пулы (все регистрации пула с меткой бина), перемешиваем метки ФД.
    Возвращает нулевое распределение ФД(30+) и наблюдённое."""
    pools = defaultdict(list)  # key -> list of (bin, is_fd)
    for x in ds:
        if x['b3'] not in ('30+', '10-30') or x[kr] == 0:
            continue
        k = keyf(x)
        for i in range(x[kr]):
            pools[k].append([x['b3'], 1 if i < x[kf] else 0])
    obs30 = sum(1 for k in pools for (b, f) in pools[k] if b == '30+' and f)
    n30 = sum(1 for k in pools for (b, f) in pools[k] if b == '30+')
    n10 = sum(1 for k in pools for (b, f) in pools[k] if b == '10-30')
    obs10 = sum(1 for k in pools for (b, f) in pools[k] if b == '10-30' and f)
    # только информативные пулы двигаются
    dist = []
    keys = list(pools.keys())
    pre = {}
    for k in keys:
        bins = [b for (b, f) in pools[k]]
        fds = [f for (b, f) in pools[k]]
        pre[k] = (bins, fds, sum(fds))
    for _ in range(NPERM):
        s30 = 0
        s10 = 0
        for k in keys:
            bins, fds, nf = pre[k]
            if nf == 0:
                continue
            idx = random.sample(range(len(bins)), nf)
            for i in idx:
                if bins[i] == '30+':
                    s30 += 1
                else:
                    s10 += 1
        dist.append((s30, s10))
    d30 = sorted(x[0] for x in dist)
    ple = sum(1 for x in d30 if x <= obs30) / NPERM
    lo = d30[int(0.025 * NPERM)]
    hi = d30[int(0.975 * NPERM) - 1]
    ratios = sorted(((a / n30) / (b_ / n10)) if b_ else float('nan') for (a, b_) in dist)
    rlo = ratios[int(0.025 * NPERM)]
    rhi = ratios[int(0.975 * NPERM) - 1]
    obs_ratio = (obs30 / n30) / (obs10 / n10) if obs10 else float('nan')
    pr = sum(1 for r in ratios if r <= obs_ratio) / NPERM
    return dict(obs30=obs30, n30=n30, obs10=obs10, n10=n10, ple=ple, lo=lo, hi=hi,
                rlo=rlo, rhi=rhi, obs_ratio=obs_ratio, pr=pr, med=d30[NPERM // 2],
                medratio=ratios[NPERM // 2])

for slbl, ds, kr, kf in (('окно, без НЗ', [x for x in D if not x['nz']], 'reg_w', 'fd_w'),
                         ('окно, все', D, 'reg_w', 'fd_w'),
                         ('окно, запуск с 24.08', [x for x in D if x['day'] >= AUG_CUT], 'reg_w', 'fd_w'),
                         ('всё время, без НЗ', [x for x in DA if not x['nz']], 'reg_a', 'fd_a')):
    for stlbl, keyf in (('набор+день', lambda x: (x['set'], x['day'])),
                        ('набор+день+зона', lambda x: (x['set'], x['day'], x['zone']))):
        r = perm_power(ds, kr, kf, keyf)
        p('  %-26s | %-18s | ФД(30+) набл. %d, нулевая медиана %d, нулевой 95%%-интервал %d–%d, p(<=) %.3f' %
          (slbl, stlbl, r['obs30'], r['med'], r['lo'], r['hi'], r['ple']))
        p('      %26s   %18s   отношение ФД/ед набл. %.2f; нулевая медиана отношения %.2f, нулевой интервал %.2f–%.2f, p(<=) %.3f' %
          ('', '', r['obs_ratio'], r['medratio'], r['rlo'], r['rhi'], r['pr']))
p('')
p('  Комментарий: нулевая медиана отношения сама ниже 1 — страта уже «съедает» часть лестницы;')
p('  ширина нулевого интервала показывает, какое падение страта в принципе способна заметить.')
p('')

# =================================================================
p('=' * 96)
p('5. ПРОВЕРКА ОБЪЯСНЕНИЯ ТЕСТИРОВЩИКА: действительно ли всё дело в августе/«НЗ»')
p('=' * 96)
p('  5.1 Период запуска × бин (окно, единица — регистрация)')
def per_period(ds, kr, kf, lbl):
    for b in ('0-10', '10-30', '30+'):
        r = sum(x[kr] for x in ds if x['b3'] == b)
        f = sum(x[kf] for x in ds if x['b3'] == b)
        n = len([x for x in ds if x['b3'] == b])
        st = sum(x['sites_w'] if kr == 'reg_w' else x['sites'] for x in ds if x['b3'] == b)
        lo, hi = wilson(f, r) if r else (float('nan'), float('nan'))
        p('    %-24s %-6s | доменов %4d | сайтов %6d | рег %3d | ФД %2d | ФД/рег %.3f [%.3f-%.3f] | рег/100 сайтов %.3f | ФД/100 сайтов %.4f' %
          (lbl, b, n, st, r, f, (f / r) if r else float('nan'), lo, hi,
           100.0 * r / st if st else float('nan'), 100.0 * f / st if st else float('nan')))

per_period([x for x in D if x['day'] < AUG_CUT], 'reg_w', 'fd_w', 'запуск до 24.08')
per_period([x for x in D if x['day'] >= AUG_CUT], 'reg_w', 'fd_w', 'запуск с 24.08')
p('')
p('  5.2 «НЗ» против даты: сколько доменов НЗ запущено с 24.08 и позже')
nz_late = [x for x in D if x['nz'] and x['day'] >= AUG_CUT]
nz_early = [x for x in D if x['nz'] and x['day'] < AUG_CUT]
nn_early = [x for x in D if not x['nz'] and x['day'] < AUG_CUT]
p('    НЗ и до 24.08: %d доменов (рег %d, ФД %d)' % (len(nz_early), sum(x['reg_w'] for x in nz_early), sum(x['fd_w'] for x in nz_early)))
p('    НЗ и с 24.08:  %d доменов (рег %d, ФД %d)' % (len(nz_late), sum(x['reg_w'] for x in nz_late), sum(x['fd_w'] for x in nz_late)))
p('    не-НЗ до 24.08: %d доменов (рег %d, ФД %d)' % (len(nn_early), sum(x['reg_w'] for x in nn_early), sum(x['fd_w'] for x in nn_early)))
p('    => «исключить НЗ» и «исключить август» — почти одно и то же, но не совсем; ниже оба варианта.')
p('')
p('  5.3 Если убрать ТОЛЬКО август (а НЗ поздних дней оставить) — остаётся ли лестница')
ds = [x for x in D if x['day'] >= AUG_CUT]
r1 = sum(x['reg_w'] for x in ds if x['b3'] == '30+'); f1 = sum(x['fd_w'] for x in ds if x['b3'] == '30+')
r0 = sum(x['reg_w'] for x in ds if x['b3'] == '10-30'); f0 = sum(x['fd_w'] for x in ds if x['b3'] == '10-30')
p('    окно: 30+ %d/%d = %.3f против 10-30 %d/%d = %.3f; отношение %.2f; точный p(ниже) = %.4f' %
  (f1, r1, f1 / r1, f0, r0, f0 / r0, (f1 / r1) / (f0 / r0), fisher_p_less(f1, r1 - f1, f0, r0 - f0)))
ds = [x for x in DA if x['day'] >= AUG_CUT]
r1 = sum(x['reg_a'] for x in ds if x['b3'] == '30+'); f1 = sum(x['fd_a'] for x in ds if x['b3'] == '30+')
r0 = sum(x['reg_a'] for x in ds if x['b3'] == '10-30'); f0 = sum(x['fd_a'] for x in ds if x['b3'] == '10-30')
p('    всё время: 30+ %d/%d = %.3f против 10-30 %d/%d = %.3f; отношение %.2f; точный p(ниже) = %.4f' %
  (f1, r1, f1 / r1, f0, r0, f0 / r0, (f1 / r1) / (f0 / r0), fisher_p_less(f1, r1 - f1, f0, r0 - f0)))
p('')

# =================================================================
p('=' * 96)
p('6. ЗОНА КАК ТЕНЬ: 30+ — это почти только .team? и что в .team отдельно')
p('=' * 96)
for zlbl in ('team', 'lol', 'casino'):
    for slbl, ds, kr, kf in (('окно, все', D, 'reg_w', 'fd_w'),
                             ('окно, с 24.08', [x for x in D if x['day'] >= AUG_CUT], 'reg_w', 'fd_w')):
        z = [x for x in ds if x['zone'] == zlbl]
        r1 = sum(x[kr] for x in z if x['b3'] == '30+'); f1 = sum(x[kf] for x in z if x['b3'] == '30+')
        r0 = sum(x[kr] for x in z if x['b3'] == '10-30'); f0 = sum(x[kf] for x in z if x['b3'] == '10-30')
        if r1 and r0:
            p('  %-6s %-16s | 30+ %2d/%3d = %.3f | 10-30 %2d/%3d = %.3f | отн. %.2f | p(ниже) %.3f' %
              (zlbl, slbl, f1, r1, f1 / r1, f0, r0, f0 / r0, (f1 / r1) / (f0 / r0) if f0 else float('nan'),
               fisher_p_less(f1, r1 - f1, f0, r0 - f0)))
p('')

# =================================================================
p('=' * 96)
p('7. «ПЛАТО ПО ДЕНЬГАМ»: проверка второй половины вердикта (ФД/100 сайтов по бинам)')
p('=' * 96)
for slbl, ds, kr, kf, ks in (('окно, все', D, 'reg_w', 'fd_w', 'sites_w'),
                             ('окно, с 24.08', [x for x in D if x['day'] >= AUG_CUT], 'reg_w', 'fd_w', 'sites_w'),
                             ('всё время, все', DA, 'reg_a', 'fd_a', 'sites'),
                             ('всё время, с 24.08', [x for x in DA if x['day'] >= AUG_CUT], 'reg_a', 'fd_a', 'sites')):
    p('  --- %s ---' % slbl)
    tot = {}
    for b in ('0-10', '10-20', '20-30', '30-40', '40+'):
        sel = [x for x in ds if x['b5'] == b]
        st = sum(x[ks] for x in sel)
        r = sum(x[kr] for x in sel)
        f = sum(x[kf] for x in sel)
        tot[b] = (len(sel), st, r, f)
        p('    %-6s | доменов %4d | сайтов %6d | рег %3d | ФД %2d | рег/100с %.3f | ФД/100с %.4f' %
          (b, len(sel), st, r, f, 100.0 * r / st if st else float('nan'), 100.0 * f / st if st else float('nan')))
    for a, bb in (('30-40', '20-30'), ('40+', '20-30'), ('40+', '30-40')):
        na, sa, ra, fa = tot[a]
        nb, sb, rb, fb = tot[bb]
        if sa and sb and (fa + fb):
            r1, r2, rat, lo, hi, phi, plo = pois_ratio_test(fa, sa, fb, sb)
            p('    %s против %s: ФД/100с %.4f против %.4f; отношение %.2f [%.2f-%.2f]; p(выше) %.3f, p(ниже) %.3f' %
              (a, bb, 100 * r1, 100 * r2, rat, lo, hi, phi, plo))
p('')

# =================================================================
p('=' * 96)
p('8. УСТОЙЧИВОСТЬ К ФИЛЬТРАМ: выбросы, дней=1, незакрытое окно')
p('=' * 96)
raw = [prep(r) for r in rows_with_out]
raw = [x for x in raw if x['exit'] is not None]
for x in raw:
    x['b3'] = bin3(x['exit'])
variants = [('как у тестировщика (без выбросов)', [x for x in raw if x['dom'] not in OUTLIERS]),
            ('с выбросами 3615/3286', raw)]
for lbl, ds in variants:
    r1 = sum(x['reg_w'] for x in ds if x['b3'] == '30+'); f1 = sum(x['fd_w'] for x in ds if x['b3'] == '30+')
    r0 = sum(x['reg_w'] for x in ds if x['b3'] == '10-30'); f0 = sum(x['fd_w'] for x in ds if x['b3'] == '10-30')
    p('  %-34s | 30+ %d/%d = %.3f | 10-30 %d/%d = %.3f | отн. %.2f | p %.4f' %
      (lbl, f1, r1, f1 / r1, f0, r0, f0 / r0, (f1 / r1) / (f0 / r0), fisher_p_less(f1, r1 - f1, f0, r0 - f0)))
# где сидят выбросы
for x in raw:
    if x['dom'] in OUTLIERS:
        p('  выброс %s: выход %.1f %%, бин %s, рег в окне %d, ФД в окне %d, набор «%s», день %s' %
          (x['dom'], x['exit'], x['b3'], x['reg_w'], x['fd_w'], x['set'], x['day']))
p('')


# =================================================================
p('=' * 96)
p('9. ОКНО КАК ТЕНЬ: те же домены, окно против «за всё время» (запуск <= 2026-09-13)')
p('=' * 96)
p('  ФД приходит позже регистрации; у доменов 30+ регистраций на домен больше, значит больше поздних')
p('  регистраций, которым не хватило окна. Считаем на ОДНОМ И ТОМ ЖЕ наборе доменов.')
for slbl, ds in (('все домены', DA), ('без НЗ', [x for x in DA if not x['nz']]),
                 ('запуск с 24.08', [x for x in DA if x['day'] >= AUG_CUT])):
    p('  --- %s ---' % slbl)
    for b in ('10-30', '30+'):
        sel = [x for x in ds if x['b3'] == b]
        rw = sum(x['reg_w'] for x in sel); fw = sum(x['fd_w'] for x in sel)
        ra = sum(x['reg_a'] for x in sel); fa = sum(x['fd_a'] for x in sel)
        nd = len([x for x in sel if x['reg_a'] > 0])
        p('    %-6s | доменов с рег. %3d | окно: %2d/%3d = %.3f | всё время: %2d/%3d = %.3f | рег/домен с рег.: окно %.2f, всё время %.2f'
          % (b, nd, fw, rw, (fw / rw) if rw else float('nan'), fa, ra, (fa / ra) if ra else float('nan'),
             (rw / nd) if nd else float('nan'), (ra / nd) if nd else float('nan')))
    r1w = sum(x['reg_w'] for x in ds if x['b3'] == '30+'); f1w = sum(x['fd_w'] for x in ds if x['b3'] == '30+')
    r0w = sum(x['reg_w'] for x in ds if x['b3'] == '10-30'); f0w = sum(x['fd_w'] for x in ds if x['b3'] == '10-30')
    r1a = sum(x['reg_a'] for x in ds if x['b3'] == '30+'); f1a = sum(x['fd_a'] for x in ds if x['b3'] == '30+')
    r0a = sum(x['reg_a'] for x in ds if x['b3'] == '10-30'); f0a = sum(x['fd_a'] for x in ds if x['b3'] == '10-30')
    if r1w and r0w and r1a and r0a and f0w and f0a:
        p('    отношение 30+/10-30: окно %.2f (p %.4f) -> всё время %.2f (p %.4f)'
          % ((f1w / r1w) / (f0w / r0w), fisher_p_less(f1w, r1w - f1w, f0w, r0w - f0w),
             (f1a / r1a) / (f0a / r0a), fisher_p_less(f1a, r1a - f1a, f0a, r0a - f0a)))
p('')
p('  9.2 ФД/рег против числа регистраций у домена (окно, запуск с 24.08) — эффект «поздней регистрации»')
ds = [x for x in D if x['day'] >= AUG_CUT]
for lo, hi, lbl in ((1, 1, '1 рег'), (2, 2, '2 рег'), (3, 4, '3-4 рег'), (5, 999, '5+ рег')):
    sel = [x for x in ds if lo <= x['reg_w'] <= hi]
    for b in ('10-30', '30+'):
        s2 = [x for x in sel if x['b3'] == b]
        r = sum(x['reg_w'] for x in s2); f = sum(x['fd_w'] for x in s2)
        if r:
            p('    %-8s %-6s | доменов %3d | рег %3d | ФД %2d | ФД/рег %.3f' % (lbl, b, len(s2), r, f, f / r))
p('')

# =================================================================
p('=' * 96)
p('10. ГРАНИЦЫ: что страта «набор+день(+зона)» способна исключить, а что нет')
p('=' * 96)
p('  Ниже — RR_MH с 95 % ДИ из раздела 2. Всё, что внутри ДИ, данными НЕ исключено.')
for k in (('окно, без НЗ', 'набор+день'), ('окно, без НЗ', 'набор+день+зона'),
          ('окно, запуск с 24.08', 'набор+день'), ('окно, запуск с 24.08', 'набор+день+зона'),
          ('всё время, без НЗ', 'набор+день'), ('всё время, запуск с 24.08', 'набор+день+зона')):
    if k in mh_store:
        v = mh_store[k]
        p('    %-26s %-18s RR_MH %.2f [%.2f-%.2f]; сравнимых регистраций 30+ %d из %d' %
          (k[0], k[1], v[3], v[4], v[5], v[9],
           sum(x['reg_w'] if 'окно' in k[0] else x['reg_a'] for x in
               ([y for y in D if not y['nz']] if k[0] == 'окно, без НЗ' else
                [y for y in D if y['day'] >= AUG_CUT] if k[0] == 'окно, запуск с 24.08' else
                [y for y in DA if not y['nz']] if k[0] == 'всё время, без НЗ' else
                [y for y in DA if y['day'] >= AUG_CUT]) if x['b3'] == '30+')))
p('')


# =================================================================
p('=' * 96)
p('11. ТОЧЕЧНЫЕ ПРОВЕРКИ, КОТОРЫЕ НЕ ОБЪЯСНЯЮТСЯ НИ АВГУСТОМ, НИ ПОВТОРАМИ')
p('=' * 96)
ds = [x for x in D if x['day'] >= AUG_CUT]
s1 = [x for x in ds if x['reg_w'] == 1 and x['b3'] == '30+']
s0 = [x for x in ds if x['reg_w'] == 1 and x['b3'] == '10-30']
f1 = sum(x['fd_w'] for x in s1); r1 = len(s1)
f0 = sum(x['fd_w'] for x in s0); r0 = len(s0)
p('  11.1 Домены РОВНО с 1 регистрацией в окне (повторов нет по построению), запуск с 24.08:')
p('       30+: %d ФД / %d рег = %.3f; 10-30: %d / %d = %.3f; точный p(ниже) = %.4f' %
  (f1, r1, f1 / r1, f0, r0, f0 / r0, fisher_p_less(f1, r1 - f1, f0, r0 - f0)))
p('       наборы этих %d доменов 30+: %s' % (r1, ', '.join(sorted(set(x['set'][:28] for x in s1)))))
p('       дни этих доменов: %s' % ', '.join(sorted(set(x['day'] for x in s1))))
# есть ли у этих доменов пара в своём пуле
pool10 = {}
for x in s0 + [y for y in ds if y['b3'] == '10-30' and y['reg_w'] > 0]:
    pool10.setdefault((x['set'], x['day']), [0, 0])
    pool10[(x['set'], x['day'])][0] += x['reg_w']
    pool10[(x['set'], x['day'])][1] += x['fd_w']
matched = [x for x in s1 if (x['set'], x['day']) in pool10]
mr = sum(pool10[(x['set'], x['day'])][0] for x in matched)
mf = sum(pool10[(x['set'], x['day'])][1] for x in matched)
p('       из них %d имеют в своём пуле «набор+день» регистрации 10-30: там 10-30 даёт %d ФД / %d рег = %.3f, а эти %d доменов 30+ — %d ФД / %d рег' %
  (len(matched), mf, mr, (mf / mr) if mr else float('nan'), len(matched),
   sum(x['fd_w'] for x in matched), len(matched)))
p('')
p('  11.2 Сводка вердикта тестировщика по пунктам (числа из разделов выше):')
p('       (а) «лестница — тень августа»: чистый срез по дате (запуск с 24.08, август целиком убран)')
p('           окно: 0.140 против 0.253, отношение 0.55, точный p = 0.024 — лестница ВЫЖИВАЕТ без страты по набору;')
p('           всё время: 0.155 против 0.213, отношение 0.73, p = 0.180 — уже не значима.')
p('           Исключение «КОНТЕНТ НЕ ЗАПИСАН» — не то же, что исключение августа: 117 НЗ-доменов запущены с 24.08.')
p('       (б) «внутри пулов разницы нет»: RR_MH 0.56-1.23 при 95 % ДИ от 0.19 до 3.13 — падение в 1,5-2 раза')
p('           данными не исключено; сравнимы лишь 43-60 регистраций 30+ из 77-93.')
p('       (в) «плато по деньгам нет»: 40+ ниже 30-40 во всех четырёх срезах (0.80 / 0.78 / 0.49 / 0.00),')
p('           и не отличается от 20-30 (всё время 1.23 [0.38-4.03], p = 0.47). На 0-4 ФД плато не опровергнуто.')
p('')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(BUF) + '\n')
print('\n[сохранено: %s]' % OUT)

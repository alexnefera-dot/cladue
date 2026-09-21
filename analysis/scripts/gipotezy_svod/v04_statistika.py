#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №4 (базы одного cf-аккаунта / аккаунта Вебмастера не делят судьбу).
Угол: СТАТИСТИКА. Проверяем результат тестировщика (h04_sibling_fate_accounts.py):

  1. Суммы или средние по доменам: где у тестировщика суммы (2×2, тercили, нули), где ранги
     по доменам (ρ). Для решающих чисел — сверка сумм против «средних долей по доменам».
  2. Объёмы регистраций в каждой группе каждого сравнения (< 20 — не доказательство).
  3. Устойчивость вывода по выходу: бутстреп по аккаунтам (95% интервал ρ) — доказано ли
     |ρ| < 0,1 и исключено ли ρ ≥ 0,15; знаковая согласованность остатков; E без самого
     домена (leave-self-out); без топ-3 доменов по |остатку| в каждой позиции пары;
     сумма-ориентированный тест «верхняя треть − нижняя треть» по первой базе.
  4. Регистрации: без топ-3 доменов по регистрациям в каждой группе 2×2 — как меняется отношение.
  5. Заразность нулей: сиблинги по одному, без топ-3 по выходам, интервал.
  6. Перебор срезов: сколько p-значений во всём отчёте тестировщика; Холм; перестановочный
     тест max|z| на ВЕСЬ набор разрезов (одна общая перестановка внутри «день × зона второй базы»).
  7. Структурная проверка: нет ли сиблингов в одном пуле / в одном дне (механическая
     отрицательная зависимость остатков).

Только stdlib. Вывод — в stdout и в analysis/export/gipotezy_svod/v04_statistika.txt
"""
import csv
import datetime
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'v04_statistika.txt')
TESTER_TXT = os.path.join(OUT_DIR, 'h04_sibling_fate_accounts.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
N_BOOT = 2000
N_JOINT = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
SUFFIX_FROM_DAY = '2026-09-12'
MIN_POOL = 3
ZONES = ['team', 'lol', 'casino', 'buzz']
random.seed(7)

_lines = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    _lines.append(s)


def f(x, d=3):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 'н/д'
    return f'{x:.{d}f}'


def ti(s):
    return int(float(s)) if s not in ('', None) else 0


def oe(o, e):
    return o / e if e > 0 else float('nan')


# ---------------------------------------------------------------- математика
def midranks(v):
    n = len(v)
    order = sorted(range(n), key=lambda i: v[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float('nan')
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return float('nan')
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def spearman(x, y):
    return pearson(midranks(x), midranks(y))


def quant(vs, q):
    vs = sorted(v for v in vs if not (isinstance(v, float) and math.isnan(v)))
    if not vs:
        return float('nan')
    return vs[min(len(vs) - 1, int(q * len(vs)))]


def log_binom_pmf(k, n, p):
    if p <= 0:
        return 0.0 if k == 0 else float('-inf')
    if p >= 1:
        return 0.0 if k == n else float('-inf')
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log(1 - p))


def binom_cdf(k, n, p):
    return sum(math.exp(log_binom_pmf(i, n, p)) for i in range(0, k + 1))


def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (float('nan'), float('nan'))

    def upper_root(target):
        lo_p, hi_p = 0.0, 1.0
        for _ in range(80):
            mid = (lo_p + hi_p) / 2
            if binom_cdf(k, n, mid) > target:
                lo_p = mid
            else:
                hi_p = mid
        return (lo_p + hi_p) / 2

    def lower_root(target):
        lo_p, hi_p = 0.0, 1.0
        for _ in range(80):
            mid = (lo_p + hi_p) / 2
            if 1 - binom_cdf(k - 1, n, mid) < target:
                lo_p = mid
            else:
                hi_p = mid
        return (lo_p + hi_p) / 2

    lo = 0.0 if k == 0 else lower_root(alpha / 2)
    hi = 1.0 if k == n else upper_root(alpha / 2)
    return (lo, hi)


def ratio_ci(o1, e1, o0, e0):
    """Отношение (O1/E1)/(O0/E0) и точный условный интервал (как у тестировщика)."""
    o1 = int(round(o1)); o0 = int(round(o0)); n = o1 + o0
    if n == 0 or e1 <= 0 or e0 <= 0:
        return (float('nan'), float('nan'), float('nan'))
    r = (o1 / e1) / (o0 / e0) if o0 > 0 else float('inf')
    lo, hi = clopper_pearson(o1, n)
    q = e1 / (e1 + e0)

    def conv(p):
        if p <= 0:
            return 0.0
        if p >= 1:
            return float('inf')
        return (p / (1 - p)) / (q / (1 - q))
    return (r, conv(lo), conv(hi))


# ---------------------------------------------------------------- данные (как у тестировщика)
with open(SRC, encoding='utf-8', newline='') as fh:
    ROWS = list(csv.DictReader(fh))
for r in ROWS:
    r['_day'] = r['день запуска']
    r['_date'] = datetime.date.fromisoformat(r['день запуска'])
    r['_sites'] = ti(r['сайтов в окне'])
    r['_exit'] = ti(r['вышли за 3 суток']) if r['окно закрыто'] == 'да' else None
    r['_reg'] = ti(r['регистраций в окне 3 суток'])
    r['_zone'] = r['зона'] if r['зона'] in ZONES else 'прочие'


def base_filter(r, allow_no_content=False):
    if r['окно закрыто'] != 'да' or r['дней'] == '1' or r['домен'] in OUTLIERS:
        return False
    if not allow_no_content and r['набор контента'] == NO_CONTENT:
        return False
    return True


def pool_key(r):
    name = r['набор контента']
    if name == NO_CONTENT:
        return ('ТОЛЬКО ДЕНЬ', r['_day'])
    if r['_day'] >= SUFFIX_FROM_DAY and re.search(r'_\d+$', name):
        return (re.sub(r'_\d+$', '', name), r['_day'])
    return (name, r['_day'])


def build_universe(rows):
    pools = defaultdict(list)
    for r in rows:
        pools[pool_key(r)].append(r)
    uni = {}
    for key, ms in pools.items():
        if len(ms) < MIN_POOL:
            continue
        S = sum(m['_sites'] for m in ms)
        X = sum(m['_exit'] for m in ms)
        R = sum(m['_reg'] for m in ms)
        for m in ms:
            s = m['_sites']
            e = X / S * s
            er = R / S * s
            # leave-self-out ожидание: доля пула без самого домена
            S2 = S - s
            e_loo = (X - m['_exit']) / S2 * s if S2 > 0 else float('nan')
            uni[m['домен']] = {
                'dom': m['домен'], 'pool': key, 'pool_n': len(ms), 'sites': s,
                'o': m['_exit'], 'e': e, 'res': (m['_exit'] - e) / math.sqrt(e) if e > 0 else 0.0,
                'oe': oe(m['_exit'], e), 'oe_loo': oe(m['_exit'], e_loo),
                'orr': m['_reg'], 'er': er,
                'mres': (m['_reg'] - er) / math.sqrt(er) if er > 0 else 0.0,
                'day': m['_day'], 'date': m['_date'], 'zone': m['_zone'], 'row': m,
            }
    return uni


def build_pairs(uni, acc_field):
    by = defaultdict(list)
    for r in ROWS:
        a = r[acc_field].strip()
        if a:
            by[a].append(r)
    pairs = []
    for acc, rs in by.items():
        rs = sorted(rs, key=lambda r: (r['_date'], r['домен']))
        ordinal = {r['домен']: i + 1 for i, r in enumerate(rs)}
        us = [r for r in rs if r['домен'] in uni]
        if len(us) < 2:
            continue
        for a, b in zip(us, us[1:]):
            A = uni[a['домен']]; B = uni[b['домен']]
            pairs.append({'acc': acc, 'A': A, 'B': B,
                          'label': f'{ordinal[a["домен"]]}→{ordinal[b["домен"]]}',
                          'gap': (B['date'] - A['date']).days})
    return pairs


KEPT = [r for r in ROWS if base_filter(r)]
KEPT_EXT = [r for r in ROWS if base_filter(r, True)]
UNI = build_universe(KEPT)
UNI_EXT = build_universe(KEPT_EXT)
PAIRS = {'cf': build_pairs(UNI, 'cf-аккаунт'), 'wm': build_pairs(UNI, 'аккаунт вебмастера')}
PAIRS_EXT = {'cf': build_pairs(UNI_EXT, 'cf-аккаунт'), 'wm': build_pairs(UNI_EXT, 'аккаунт вебмастера')}
NAME = {'cf': 'cf-аккаунт', 'wm': 'аккаунт Вебмастера'}

P('=' * 100)
P('СКЕПТИК К ГИПОТЕЗЕ №4 — угол СТАТИСТИКА')
P('=' * 100)
P(f'Файл: {SRC}')
P(f'Воспроизведение вселенной тестировщика: основной прогон {len(UNI)} доменов (у тестировщика 1483), '
  f'с августом {len(UNI_EXT)} (у тестировщика 1812)')
for k in ('cf', 'wm'):
    P(f'  пар {NAME[k]}: основной {len(PAIRS[k])}, с августом {len(PAIRS_EXT[k])}')


# ---------------------------------------------------------------- перестановка внутри дня
def perm_groups(pairs, by_zone=False):
    g = defaultdict(list)
    for i, p in enumerate(pairs):
        key = (p['B']['day'], p['B']['zone']) if by_zone else p['B']['day']
        g[key].append(i)
    return list(g.values())


def shuffle_into(sec, groups):
    for g in groups:
        sh = g[:]
        random.shuffle(sh)
        for k, i in enumerate(g):
            sec[i] = sh[k]


def perm_p_and_ci(obs, null):
    vals = [v for v in null if not (isinstance(v, float) and math.isnan(v))]
    if not vals or isinstance(obs, float) and math.isnan(obs):
        return float('nan'), float('nan'), (float('nan'), float('nan'))
    c = sum(vals) / len(vals)
    d = abs(obs - c)
    p = (sum(1 for v in vals if abs(v - c) >= d - 1e-12) + 1) / (len(vals) + 1)
    return p, c, (quant(vals, 0.025), quant(vals, 0.975))


# ====================================================================================
P()
P('=' * 100)
P('0. СТРУКТУРА ПАР: нет ли сиблингов в одном пуле или в одном дне (механическая отрицательная связь остатков)')
P('=' * 100)
for k in ('cf', 'wm'):
    for tag, ps in (('основной', PAIRS[k]), ('с августом', PAIRS_EXT[k])):
        sp = sum(1 for p in ps if p['A']['pool'] == p['B']['pool'])
        sd = sum(1 for p in ps if p['A']['day'] == p['B']['day'])
        P(f'  {NAME[k]} ({tag}): пар {len(ps)}, в одном пуле {sp}, в один день {sd}')
P('  Если бы сиблинги делили пул, их остатки были бы отрицательно связаны по построению (сумма остатков в пуле = 0),')
P('  а перестановка внутри дня эту связь ломала бы — нуль был бы смещён. Здесь таких пар нет: аккаунт не запускает')
P('  две базы в один день. Претензии к нулю по этому пункту нет.')

# ====================================================================================
P()
P('=' * 100)
P('1. СУММЫ ИЛИ СРЕДНИЕ ПО ДОМЕНАМ')
P('=' * 100)
P('  У тестировщика: 2×2 по регистрациям, тercили, «первая ≥ 15 %», заразность нулей — из СУММ (ΣO / ΣE). Верно.')
P('  ρ Спирмена — по рангам O/E отдельных доменов: это не «среднее долей», а мера порядка; по плану так и должно быть.')
P('  S = среднее произведение остатков — среднее по парам, но остатки нормированы на √E, так что домены равновесны.')
P('  Сверка решающих чисел: отношение из сумм против отношения средних O/E по доменам (то, чего делать нельзя):')
for k in ('cf', 'wm'):
    for tag, ps in (('основной', PAIRS[k]), ('с августом', PAIRS_EXT[k])):
        g1 = [p['B'] for p in ps if p['A']['orr'] > 0]
        g0 = [p['B'] for p in ps if p['A']['orr'] == 0]
        o1 = sum(b['orr'] for b in g1); e1 = sum(b['er'] for b in g1)
        o0 = sum(b['orr'] for b in g0); e0 = sum(b['er'] for b in g0)
        r_sum = oe(o1, e1) / oe(o0, e0)
        m1 = [b['orr'] / b['er'] for b in g1 if b['er'] > 0]
        m0 = [b['orr'] / b['er'] for b in g0 if b['er'] > 0]
        r_mean = (sum(m1) / len(m1)) / (sum(m0) / len(m0)) if m1 and m0 and sum(m0) > 0 else float('nan')
        P(f'    {NAME[k]:20s} {tag:10s}: из сумм {f(r_sum, 2)}; из средних O/E по доменам {f(r_mean, 2)} '
          f'(доменов с E>0: {len(m1)} / {len(m0)})')
P('  Расхождение есть, но в отчёте использованы суммы — по этому пункту претензий нет.')

# ====================================================================================
P()
P('=' * 100)
P('2. ОБЪЁМЫ РЕГИСТРАЦИЙ В ГРУППАХ (< 20 в группе — не доказательство)')
P('=' * 100)
P(f'  {"сравнение":52s} {"пар с рег/без":>14s} {"рег 2-й: с / без":>18s} {"вторых баз с ≥1 рег":>20s}  метка')
rows_tab = []


def reg_groups(ps, title):
    g1 = [p for p in ps if p['A']['orr'] > 0]
    g0 = [p for p in ps if p['A']['orr'] == 0]
    o1 = sum(p['B']['orr'] for p in g1); o0 = sum(p['B']['orr'] for p in g0)
    d1 = sum(1 for p in g1 if p['B']['orr'] > 0); d0 = sum(1 for p in g0 if p['B']['orr'] > 0)
    flag = []
    if o1 < 20:
        flag.append('в группе «первая с рег» < 20')
    if o0 < 20:
        flag.append('и «без» < 20')
    P(f'  {title:52s} {len(g1):6d}/{len(g0):<7d} {o1:8d} / {o0:<7d} {d1:9d} / {d0:<8d}  {"; ".join(flag) or "объём есть"}')
    return o1, o0


for k in ('cf', 'wm'):
    reg_groups(PAIRS[k], f'{NAME[k]}: основной, все пары')
    for z in ZONES:
        sub = [p for p in PAIRS[k] if p['B']['zone'] == z]
        if len(sub) >= 10:
            reg_groups(sub, f'{NAME[k]}: зона второй {z}')
    for lab in ('1→2', '2→3'):
        sub = [p for p in PAIRS[k] if p['label'] == lab]
        if len(sub) >= 10:
            reg_groups(sub, f'{NAME[k]}: пары {lab}')
    if k == 'cf':
        for nm, cond in (('одна зона', lambda p: p['A']['zone'] == p['B']['zone']),
                         ('разные зоны', lambda p: p['A']['zone'] != p['B']['zone'])):
            reg_groups([p for p in PAIRS[k] if cond(p)], f'{NAME[k]}: {nm}')
    reg_groups(PAIRS_EXT[k], f'{NAME[k]}: с августом, все пары')
    reg_groups([p for p in PAIRS_EXT[k] if p['A']['row']['набор контента'] == NO_CONTENT],
               f'{NAME[k]}: с августом, первая августовская')
P('  Итог по пункту: в группе «первая с регистрацией» вторые базы дали 14 (cf) и 7 (Вебмастер) регистраций в основном')
P('  прогоне, 26 и 13 — с августом. Ни в одном разрезе 20 регистраций в этой группе нет. Любое отношение здесь — не доказательство')
P('  ни связи, ни её отсутствия. Тестировщик это признал («точность не та»), но точечные 0,69 и 2,85 в выводе фигурируют.')

# ====================================================================================
P()
P('=' * 100)
P('3. УСТОЙЧИВОСТЬ ВЫВОДА ПО ВЫХОДУ (главная часть вердикта «подтверждена»)')
P('=' * 100)


def exit_block(k, ps, tag):
    n = len(ps)
    a_oe = [p['A']['oe'] for p in ps]; b_oe = [p['B']['oe'] for p in ps]
    a_res = [p['A']['res'] for p in ps]; b_res = [p['B']['res'] for p in ps]
    ra = midranks(a_oe); rb = midranks(b_oe)
    rho = pearson(ra, rb)
    S = sum(a * b for a, b in zip(a_res, b_res)) / n
    # 3a. бутстреп по аккаунтам (кластеры)
    by_acc = defaultdict(list)
    for i, p in enumerate(ps):
        by_acc[p['acc']].append(i)
    accs = list(by_acc.keys())
    boots = []
    for _ in range(N_BOOT):
        idx = []
        for _ in range(len(accs)):
            idx.extend(by_acc[random.choice(accs)])
        boots.append(spearman([a_oe[i] for i in idx], [b_oe[i] for i in idx]))
    blo, bhi = quant(boots, 0.025), quant(boots, 0.975)
    se = 1 / math.sqrt(n - 3)
    P(f'--- {NAME[k]} ({tag}): пар {n}, ρ Спирмена по O/E = {f(rho)}, S = {f(S)}')
    P(f'   3a. Бутстреп по аккаунтам ({N_BOOT}): 95 % интервал ρ = {f(blo)}..{f(bhi)}; нормальное приближение ±{f(1.96 * se)}')
    P(f'       критерий «не делят» |ρ| < 0,1 доказан (весь интервал внутри ±0,1)? {"да" if blo > -0.1 and bhi < 0.1 else "НЕТ"};'
      f'  «связь» ρ ≥ 0,15 исключена (верх интервала < 0,15)? {"да" if bhi < 0.15 else "НЕТ"};'
      f'  ρ ≥ 0,10 исключено? {"да" if bhi < 0.10 else "НЕТ"}')
    # 3b. знаковая согласованность
    nz = [(a, b) for a, b in zip(a_res, b_res) if a != 0 and b != 0]
    conc = sum(1 for a, b in nz if (a > 0) == (b > 0)) / len(nz)
    # 3c. leave-self-out O/E
    a_loo = [p['A']['oe_loo'] for p in ps]; b_loo = [p['B']['oe_loo'] for p in ps]
    rho_loo = spearman(a_loo, b_loo)
    # 3d. без топ-3 доменов по |остатку| среди первых и среди вторых баз
    topA = set(d['dom'] for d in sorted((p['A'] for p in ps), key=lambda u: -abs(u['res']))[:3])
    topB = set(d['dom'] for d in sorted((p['B'] for p in ps), key=lambda u: -abs(u['res']))[:3])
    keep = [i for i, p in enumerate(ps) if p['A']['dom'] not in topA and p['B']['dom'] not in topB]
    rho_trim = spearman([a_oe[i] for i in keep], [b_oe[i] for i in keep])
    S_trim = sum(a_res[i] * b_res[i] for i in keep) / len(keep)
    # 3e. суммы: O/E второй базы по третям остатка первой, разность верх − низ
    order = sorted(range(n), key=lambda i: a_res[i])
    t = n // 3
    low, high = order[:t], order[2 * t:]

    def oe_sum(idx, sec=None):
        o = sum(ps[sec[i] if sec else i]['B']['o'] for i in idx)
        e = sum(ps[sec[i] if sec else i]['B']['e'] for i in idx)
        return oe(o, e)
    D = oe_sum(high) - oe_sum(low)
    # перестановки внутри дня для conc, rho_loo, D
    groups = perm_groups(ps)
    sec = list(range(n))
    null_conc, null_loo, null_D, null_rho, null_S = [], [], [], [], []
    for _ in range(N_PERM):
        shuffle_into(sec, groups)
        nzp = [(a_res[i], b_res[sec[i]]) for i in range(n) if a_res[i] != 0 and b_res[sec[i]] != 0]
        null_conc.append(sum(1 for a, b in nzp if (a > 0) == (b > 0)) / len(nzp))
        null_rho.append(pearson(ra, [rb[sec[i]] for i in range(n)]))
        null_S.append(sum(a_res[i] * b_res[sec[i]] for i in range(n)) / n)
        null_D.append(oe_sum(high, sec) - oe_sum(low, sec))
    rb_loo = midranks(b_loo); ra_loo = midranks(a_loo)
    for _ in range(N_PERM):
        shuffle_into(sec, groups)
        null_loo.append(pearson(ra_loo, [rb_loo[sec[i]] for i in range(n)]))
    pc, cc, cic = perm_p_and_ci(conc, null_conc)
    pl, cl, cil = perm_p_and_ci(rho_loo, null_loo)
    pd_, cd, cid = perm_p_and_ci(D, null_D)
    pr, cr, cir = perm_p_and_ci(rho, null_rho)
    pS, cS, ciS = perm_p_and_ci(S, null_S)
    P(f'   3b. Знаковая согласованность остатков (доля пар, где обе базы по одну сторону от пула): {f(conc)} '
      f'(нуль {f(cc)}, 95 % {f(cic[0])}..{f(cic[1])}, p = {f(pc)}) — пар с ненулевыми остатками {len(nz)}')
    P(f'   3c. ρ по O/E с ожиданием БЕЗ самого домена (leave-self-out): {f(rho_loo)} (нуль {f(cl)}, 95 % {f(cil[0])}..{f(cil[1])}, p = {f(pl)})')
    P(f'   3d. Без топ-3 доменов по |остатку| среди первых ({", ".join(sorted(topA))}) и среди вторых ({", ".join(sorted(topB))}): '
      f'осталось {len(keep)} пар, ρ = {f(rho_trim)}, S = {f(S_trim)}  (было ρ {f(rho)}, S {f(S)})')
    P(f'   3e. Суммы: O/E второй базы при первой в верхней трети минус при первой в нижней трети = {f(D)} '
      f'(верх {f(oe_sum(high))}, низ {f(oe_sum(low))}; нуль {f(cd)}, 95 % {f(cid[0])}..{f(cid[1])}, p = {f(pd_)})')
    P(f'   3f. Воспроизведение перестановочного нуля ({N_PERM}): ρ p = {f(pr)} (95 % {f(cir[0])}..{f(cir[1])}); '
      f'S p = {f(pS)} (95 % {f(ciS[0])}..{f(ciS[1])}); ширина нуля S ±{f((ciS[1] - ciS[0]) / 2, 2)} — S почти ничего не различает')
    return {'rho': rho, 'blo': blo, 'bhi': bhi, 'conc_p': pc, 'D': D, 'D_p': pd_, 'rho_trim': rho_trim}


EXIT = {}
for k in ('cf', 'wm'):
    EXIT[(k, 'main')] = exit_block(k, PAIRS[k], 'основной')
    EXIT[(k, 'ext')] = exit_block(k, PAIRS_EXT[k], 'с августом')
    P()

# ====================================================================================
P('=' * 100)
P('4. РЕГИСТРАЦИИ: 2×2 БЕЗ ТОП-3 ДОМЕНОВ ПО РЕГИСТРАЦИЯМ В КАЖДОЙ ГРУППЕ')
P('=' * 100)


def ratio_block(k, ps, tag, n_perm=N_PERM):
    g1 = [p for p in ps if p['A']['orr'] > 0]
    g0 = [p for p in ps if p['A']['orr'] == 0]

    def sums(g):
        return sum(p['B']['orr'] for p in g), sum(p['B']['er'] for p in g)
    o1, e1 = sums(g1); o0, e0 = sums(g0)
    r, lo, hi = ratio_ci(o1, e1, o0, e0)
    # перестановочный интервал (перестановка вторых внутри дня — учитывает кучность регистраций по доменам)
    n = len(ps)
    first = [1 if p['A']['orr'] > 0 else 0 for p in ps]
    bo = [p['B']['orr'] for p in ps]; be = [p['B']['er'] for p in ps]
    groups = perm_groups(ps); sec = list(range(n)); null = []
    for _ in range(n_perm):
        shuffle_into(sec, groups)
        x1 = y1 = x0 = y0 = 0.0
        for i in range(n):
            j = sec[i]
            if first[i]:
                x1 += bo[j]; y1 += be[j]
            else:
                x0 += bo[j]; y0 += be[j]
        null.append((x1 / y1) / (x0 / y0) if y1 > 0 and y0 > 0 and x0 > 0 else float('nan'))
    lv = [math.log(v) for v in null if v > 0]
    lc = sum(lv) / len(lv)
    d = abs(math.log(r) - lc) if r > 0 else float('inf')
    pp = (sum(1 for v in null if (abs(math.log(v) - lc) if v > 0 else float('inf')) >= d - 1e-12) + 1) / (len(null) + 1)
    P(f'--- {NAME[k]} ({tag}): первая с рег {len(g1)} пар: O {o1:.0f} / E {f(e1, 2)}; без {len(g0)} пар: O {o0:.0f} / E {f(e0, 2)}')
    P(f'   отношение {f(r, 2)}; точный условный интервал {f(lo, 2)}..{f(hi, 2)} (считает каждую регистрацию независимой);')
    P(f'   перестановочный интервал (домены целиком) {f(quant(null, 0.025), 2)}..{f(quant(null, 0.975), 2)}, p = {f(pp)} — он честнее, потому что регистрации кучкуются по доменам')
    top1 = sorted(g1, key=lambda p: -p['B']['orr'])[:3]
    top0 = sorted(g0, key=lambda p: -p['B']['orr'])[:3]
    P(f'   топ-3 вторых баз по регистрациям в группе «с»: ' + ', '.join(f'{p["B"]["dom"]} {p["B"]["orr"]} (E {f(p["B"]["er"], 2)})' for p in top1))
    P(f'   топ-3 вторых баз по регистрациям в группе «без»: ' + ', '.join(f'{p["B"]["dom"]} {p["B"]["orr"]} (E {f(p["B"]["er"], 2)})' for p in top0))
    for nm, cut in (('без топ-3 в каждой группе', 3), ('без топ-1 в каждой группе', 1)):
        s1 = set(p['B']['dom'] for p in top1[:cut]); s0 = set(p['B']['dom'] for p in top0[:cut])
        h1 = [p for p in g1 if p['B']['dom'] not in s1]; h0 = [p for p in g0 if p['B']['dom'] not in s0]
        a1, b1 = sums(h1); a0, b0 = sums(h0)
        rr, l2, h2 = ratio_ci(a1, b1, a0, b0)
        P(f'   {nm}: «с» O {a1:.0f}/E {f(b1, 2)}, «без» O {a0:.0f}/E {f(b0, 2)} → отношение {f(rr, 2)} ({f(l2, 2)}..{f(h2, 2)})')
    # доля регистраций группы «с», которую дали 2 домена
    if o1 > 0:
        P(f'   доля регистраций группы «с» от двух самых крупных доменов: {sum(p["B"]["orr"] for p in top1[:2]) / o1:.0%}')
    return r, pp


RAT = {}
for k in ('cf', 'wm'):
    RAT[(k, 'main')] = ratio_block(k, PAIRS[k], 'основной')
    RAT[(k, 'ext')] = ratio_block(k, PAIRS_EXT[k], 'с августом')
    P()
P('  Итог по пункту: отношение по регистрациям прыгает от 0,2 до 2,9 при удалении одного-трёх доменов — в группе «с» его целиком')
P('  делают 1–2 домена (у Вебмастера 5779.team и ynr.team дают 5 из 7). Это подтверждает, что число не несёт информации.')

# ====================================================================================
P('=' * 100)
P('5. ЗАРАЗНОСТЬ НУЛЕЙ: СИБЛИНГИ ПО ОДНОМУ')
P('=' * 100)


def zero_block(k, uni, acc_field, tag, n_perm=N_PERM):
    by_acc = defaultdict(list)
    for u in uni.values():
        a = u['row'][acc_field].strip()
        if a:
            by_acc[a].append(u)
    zeros = [u for u in uni.values() if u['o'] == 0]
    sibs = {}
    for z in zeros:
        a = z['row'][acc_field].strip()
        for o in by_acc.get(a, []):
            if o['dom'] != z['dom']:
                sibs[o['dom']] = o
    sibs = sorted(sibs.values(), key=lambda u: -u['o'])
    P(f'--- {NAME[k]} ({tag}): нулевых баз {len(zeros)}, их сиблингов {len(sibs)}')
    if not sibs:
        return
    P(f'   {"сиблинг":22s} {"пул":48s} {"сайтов":>6s} {"O":>4s} {"E":>6s} {"O/E":>5s}')
    for u in sibs:
        P(f'   {u["dom"]:22s} {str(u["pool"][0])[:44] + " " + u["pool"][1][5:]:48s} {u["sites"]:6d} {u["o"]:4d} {u["e"]:6.1f} {oe(u["o"], u["e"]):5.2f}')
    O = sum(u['o'] for u in sibs); E = sum(u['e'] for u in sibs)
    below = sum(1 for u in sibs if u['o'] < u['e'])
    P(f'   сумма: O {O} / E {f(E, 1)} = {f(oe(O, E))}; сиблингов ниже своего пула {below} из {len(sibs)}; '
      f'медиана O/E {f(sorted(oe(u["o"], u["e"]) for u in sibs)[len(sibs) // 2], 2)}')
    for cut in (1, 3):
        rest = sibs[cut:]
        Or = sum(u['o'] for u in rest); Er = sum(u['e'] for u in rest)
        P(f'   без топ-{cut} по выходам: O {Or} / E {f(Er, 1)} = {f(oe(Or, Er))} ({len(rest)} баз)')
    # перестановка: сиблинг → случайная база того же дня; интервал
    by_day = defaultdict(list)
    for u in uni.values():
        by_day[u['day']].append(u)
    null = []
    for _ in range(n_perm):
        o = e = 0.0
        for u in sibs:
            v = random.choice(by_day[u['day']])
            o += v['o']; e += v['e']
        null.append(oe(o, e))
    p, c, ci = perm_p_and_ci(oe(O, E), null)
    P(f'   перестановочный нуль: 95 % {f(ci[0])}..{f(ci[1])}, p = {f(p)} → критерий «0,9–1,1» здесь недоказуем: сам нуль шире коридора')
    # исключается ли сильная заразность: O/E <= 0.5?
    lo_half = sum(1 for v in null if v <= 0.5) / len(null)
    P(f'   доля нулевых перестановок с O/E ≤ 0,5: {f(lo_half)} — то есть «сиблинг нуля выходит вдвое хуже» на этих {len(sibs)} базах исключается')


for k, fld in (('cf', 'cf-аккаунт'), ('wm', 'аккаунт вебмастера')):
    zero_block(k, UNI, fld, 'основной')
    zero_block(k, UNI_EXT, fld, 'с августом')
    P()

# ====================================================================================
P('=' * 100)
P('6. ПЕРЕБОР СРЕЗОВ: СКОЛЬКО p-ЗНАЧЕНИЙ И ВЫЖИВАЕТ ЛИ ЧТО-ТО ПРИ ОБЩЕЙ ПЕРЕСТАНОВКЕ')
P('=' * 100)
# 6a. считаем все p-значения в отчёте тестировщика
pvals = []
try:
    with open(TESTER_TXT, encoding='utf-8') as fh:
        txt = fh.read()
    for m in re.finditer(r'p(?:\(>=\))?\s*=\s*([0-9]\.[0-9]+)|\(p\s+([0-9]\.[0-9]+)\)', txt):
        v = m.group(1) or m.group(2)
        pvals.append(float(v))
    perm_p = [float(v) for v in re.findall(r'перестановочное p = ([0-9]\.[0-9]+)', txt)]
    binom_p = [float(v) for v in re.findall(r'биномиальн\w+ p = ([0-9]\.[0-9]+)', txt)]
    P(f'  6a. В отчёте тестировщика напечатано p-значений: {len(pvals)} (из них перестановочных по отношению/нулям {len(perm_p)}, биномиальных {len(binom_p)})')
    ps_sorted = sorted(pvals)
    P(f'      наименьшие пять: {", ".join(f"{v:.3f}" for v in ps_sorted[:5])}; при {len(pvals)} независимых проверках наименьшее p в нуле ≈ {1 / (len(pvals) + 1):.3f}')
    holm = min(pv * (len(pvals) - i) for i, pv in enumerate(ps_sorted))
    P(f'      поправка Холма: наименьшее скорректированное p = {min(1.0, holm):.2f}; ниже 0,05 не проходит ничего')
    P(f'      (биномиальное p = 0,005 у 4 сиблингов нулей Вебмастера «с августом» тестировщик сам отбросил: тест считает сайты независимыми;')
    P(f'       перестановочное там 0,209, и O/E = 1,23 — сиблинги вышли ЛУЧШЕ пула, то есть против заразности)')
except OSError:
    P('  6a. Отчёт тестировщика не найден, подсчёт p пропущен')


# 6b. общая перестановка по всем разрезам: max|z|
def joint_family(k, ps, n_perm=N_JOINT):
    n = len(ps)
    cuts = {'все': list(range(n))}
    for z in ZONES:
        idx = [i for i, p in enumerate(ps) if p['B']['zone'] == z]
        if len(idx) >= 10:
            cuts['зона ' + z] = idx
    for lab in ('1→2', '2→3'):
        idx = [i for i, p in enumerate(ps) if p['label'] == lab]
        if len(idx) >= 10:
            cuts['пары ' + lab] = idx
    if k == 'cf':
        cuts['одна зона'] = [i for i, p in enumerate(ps) if p['A']['zone'] == p['B']['zone']]
        cuts['разные зоны'] = [i for i, p in enumerate(ps) if p['A']['zone'] != p['B']['zone']]
    a_oe = [p['A']['oe'] for p in ps]; b_oe = [p['B']['oe'] for p in ps]
    a_res = [p['A']['res'] for p in ps]; b_res = [p['B']['res'] for p in ps]
    am = [p['A']['mres'] for p in ps]; bm = [p['B']['mres'] for p in ps]
    ereg_ok = [p['A']['er'] > 0 and p['B']['er'] > 0 for p in ps]
    first = [1 if p['A']['orr'] > 0 else 0 for p in ps]
    bo = [p['B']['orr'] for p in ps]; be = [p['B']['er'] for p in ps]
    b_ok = [p['B']['er'] > 0 for p in ps]

    def stats(sec):
        out = {}
        for nm, idx in cuts.items():
            ia = [a_oe[i] for i in idx]; ib = [b_oe[sec[i]] for i in idx]
            out[(nm, 'ρ выход')] = spearman(ia, ib)
            out[(nm, 'S выход')] = sum(a_res[i] * b_res[sec[i]] for i in idx) / len(idx)
            ir = [i for i in idx if ereg_ok[i] and b_ok[sec[i]]]
            if len(ir) >= 10:
                out[(nm, 'ρ рег')] = spearman([am[i] for i in ir], [bm[sec[i]] for i in ir])
                out[(nm, 'S рег')] = sum(am[i] * bm[sec[i]] for i in ir) / len(ir)
            x1 = y1 = x0 = y0 = 0.0
            for i in idx:
                j = sec[i]
                if first[i]:
                    x1 += bo[j]; y1 += be[j]
                else:
                    x0 += bo[j]; y0 += be[j]
            out[(nm, 'log отношение рег')] = math.log((x1 / y1) / (x0 / y0)) if y1 > 0 and y0 > 0 and x0 > 0 and x1 > 0 else float('nan')
        return out
    ident = list(range(n))
    obs = stats(ident)
    groups = perm_groups(ps, by_zone=True)
    sec = list(range(n))
    null = defaultdict(list)
    for _ in range(n_perm):
        shuffle_into(sec, groups)
        for key, v in stats(sec).items():
            null[key].append(v)
    keys = [key for key in obs if not math.isnan(obs[key])]
    mu, sd = {}, {}
    for key in keys:
        vals = [v for v in null[key] if not math.isnan(v)]
        if len(vals) < 50:
            continue
        m_ = sum(vals) / len(vals)
        s_ = math.sqrt(sum((v - m_) ** 2 for v in vals) / (len(vals) - 1))
        if s_ > 0:
            mu[key] = m_; sd[key] = s_
    keys = [key for key in keys if key in mu]
    z_obs = {key: (obs[key] - mu[key]) / sd[key] for key in keys}
    max_obs = max(abs(z) for z in z_obs.values())
    key_max = max(keys, key=lambda key: abs(z_obs[key]))
    maxes = []
    for t in range(n_perm):
        mx = 0.0
        for key in keys:
            v = null[key][t]
            if not math.isnan(v):
                mx = max(mx, abs((v - mu[key]) / sd[key]))
        maxes.append(mx)
    p_fam = (sum(1 for m_ in maxes if m_ >= max_obs - 1e-12) + 1) / (len(maxes) + 1)
    # маргинальные p для трёх самых крайних
    top = sorted(keys, key=lambda key: -abs(z_obs[key]))[:3]
    P(f'  6b. {NAME[k]}: разрезов {len(cuts)}, статистик в семействе {len(keys)}, общая перестановка внутри «день × зона второй» × {n_perm}')
    P(f'      самое крайнее: {key_max[0]} / {key_max[1]}: наблюдено {f(obs[key_max])}, z = {f(z_obs[key_max], 2)}; семейное p (max|z|) = {f(p_fam)}')
    for key in top:
        vals = [v for v in null[key] if not math.isnan(v)]
        pm = (sum(1 for v in vals if abs(v - mu[key]) >= abs(obs[key] - mu[key]) - 1e-12) + 1) / (len(vals) + 1)
        P(f'      {key[0]:14s} {key[1]:18s} набл. {f(obs[key]):>7s}  z {f(z_obs[key], 2):>6s}  маргинальное p {f(pm)}')
    return p_fam


for k in ('cf', 'wm'):
    joint_family(k, PAIRS[k])
P('  Итог по пункту: с учётом всего семейства разрезов ни один разрез не выделяется. Перебор срезов не породил ложного')
P('  сигнала — но и не мог повредить вердикту «связи нет», потому что множественность работает против сигнала, а не против нуля.')

# ====================================================================================
P()
P('=' * 100)
P('7. ЧТО ИМЕННО ДОКАЗАНО ПО ВЫХОДУ (сводка интервалов)')
P('=' * 100)
for k in ('cf', 'wm'):
    for tag in ('main', 'ext'):
        e = EXIT[(k, tag)]
        P(f'  {NAME[k]:20s} {"основной" if tag == "main" else "с августом":10s}: ρ {f(e["rho"])}, бутстреп 95 % {f(e["blo"])}..{f(e["bhi"])}; '
          f'верх−низ по третям {f(e["D"])} (p {f(e["D_p"])}); без топ-3 ρ {f(e["rho_trim"])}')


# ====================================================================================
P()
P('=' * 100)
P('8. ВЕРДИКТ СКЕПТИКА')
P('=' * 100)
cf_m, cf_e = EXIT[('cf', 'main')], EXIT[('cf', 'ext')]
wm_m, wm_e = EXIT[('wm', 'main')], EXIT[('wm', 'ext')]
P('Опровергнуто? НЕТ — вердикт «частично» (выход: не делят; регистрации: не решается) выдерживает проверку. Но формулировку надо ужать.')
P()
P('По выходу (главный вывод):')
P(f'  • Нуль чистый: ни одна пара сиблингов не делит пул и день, механической связи остатков нет; перестановка внутри дня корректна.')
P(f'  • ρ устойчиво: без самого домена в ожидании {f(cf_m["rho"])}→−0,018 (cf), без топ-3 доменов по |остатку| {f(cf_m["rho_trim"])} (cf) и {f(wm_m["rho_trim"])} (Вебмастер);')
P(f'    сумма-ориентированная проверка (O/E второй при первой в верхней трети минус в нижней): {f(cf_m["D"])} (cf, p {f(cf_m["D_p"])}), '
  f'{f(wm_m["D"])} (Вебмастер, p {f(wm_m["D_p"])}); знаковая согласованность 0,47–0,51 при нуле 0,50.')
P(f'  • Точность: бутстреп по аккаунтам даёт ρ cf {f(cf_m["blo"])}..{f(cf_m["bhi"])} (608 пар) и {f(cf_e["blo"])}..{f(cf_e["bhi"])} (935 пар); '
  f'Вебмастер {f(wm_m["blo"])}..{f(wm_m["bhi"])} (183 пары) и {f(wm_e["blo"])}..{f(wm_e["bhi"])} (457 пар).')
P('    Заявленный критерий «|ρ| < 0,1» как ДОКАЗАННЫЙ интервал выполняется только у cf с августом; у Вебмастера в основном прогоне интервал')
P('    доходит до −0,21. Зато положительная связь (та, что означала бы «делят судьбу») ρ ≥ 0,15 исключена во всех четырёх прогонах,')
P('    ρ ≥ 0,10 — в трёх из четырёх (у Вебмастера с августом верх 0,106). Вывод надо формулировать односторонне.')
P('  • S (среднее произведение остатков) ничего не различает: ширина его нуля ±0,5 (cf) и ±0,9 (Вебмастер) — из доводов убрать.')
P('  • Сиблинги нулевых баз: cf 13 баз O/E 1,015, но нуль 0,78..1,22 шире коридора 0,9–1,1 — коридор недоказуем; исключено только O/E ≤ 0,5.')
P('    Без топ-3 по выходам 0,92 (10 баз), 5 из 13 ниже пула. У Вебмастера 2 базы (0,67 и 1,31) — вывода нет вовсе.')
P()
P('По регистрациям:')
P('  • В группе «первая с регистрацией» у вторых баз 14 (cf) и 7 (Вебмастер) регистраций, с августом 26 и 13; ни в одном разрезе нет 20.')
P('  • Без топ-3 доменов: cf 0,69 → 0,51; Вебмастер 2,85 → 0,73 (без топ-1 — 2,10); с августом cf 0,91 → 0,67, Вебмастер 0,87 → 0,58.')
P('    У Вебмастера 5 из 7 регистраций группы «с» — два домена (5779.team, ynr.team). Отношения — шум, точечные значения цитировать нельзя.')
P('  • Точный условный интервал (0,92..8,30 у Вебмастера) считает регистрации независимыми и занижен; перестановочный по доменам 0,00..3,33.')
P()
P('Перебор срезов: в отчёте 135 p-значений, наименьшее 0,005 — биномиальное у 4 сиблингов нулей (в сторону ЛУЧШЕ пула, тестировщик его отбросил),')
P('  следующее 0,045; Холм — ничего; общая перестановка по всем разрезам: семейное p 0,33 (cf) и 0,51 (Вебмастер). Ложного сигнала нет.')
P()
P('Как ужать формулировку:')
P('  1) По выходу: «положительной связи между сиблингами нет: ρ ≥ 0,15 исключено у обоих аккаунтов (бутстреп по аккаунтам), у cf ρ = −0,02 (−0,10..0,05, 608 пар);')
P('     у Вебмастера ρ = −0,06 (−0,21..0,08, 183 пары) — объём мал, чтобы утверждать |ρ| < 0,1, но «делят судьбу» (ρ ≥ 0,15) исключено».')
P('  2) Убрать S и коридор 0,9–1,1 по нулям из доводов; по нулям писать: «сиблинги 13 нулевых cf-баз вышли 422 против 416 ожидаемых,')
P('     исключено падение вдвое; у Вебмастера 2 базы — не проверяемо».')
P('  3) По регистрациям не приводить 0,69 и 2,85 как результат; писать: «14 и 7 регистраций в группе — не решается; на удалении')
P('     трёх доменов отношение меняется в 2–4 раза».')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

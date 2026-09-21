#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №4 (базы одного cf-аккаунта / аккаунта Вебмастера не делят судьбу). Угол — ТЕНИ (конфаундинг).

Тестировщик получил «нуль» по выходу (ρ −0,022 у cf, −0,061 у Вебмастера) и «нет связи, но точность плохая» по
регистрациям (отношение 0,69 у cf, 2,85 у Вебмастера, оба интервала накрывают 1). Здесь проверяем, не тень ли это:
  1. ЗОНА. Пул тестировщика — «набор + день», зона в страту не входит, а 337 из 608 cf-пар — в разных зонах.
     Внутри пула зона сдвигает выход (.buzz худший), значит остатки e_A и e_B несут зонную примесь, которая у
     однозонных пар даёт «+», у разнозонных — «−». Ужесточаем страту до «набор + день + зона» и смотрим,
     выживает ли нуль и не всплывает ли связь.
  2. ОГРУБЛЕНИЕ 12.09+. 490 доменов сидят в пулах «корень имени + день» (набор на самом деле один на домен).
     Считаем без них.
  3. .buzz и «прочие» зоны — без них.
  4. САМЫЙ ЖЁСТКИЙ ПАРНЫЙ ДИЗАЙН: группа = (пул первой базы, пул второй базы). Внутри группы у всех пар одинаковые
     набор и день и у первой, и у второй базы (а в варианте с зоной — и зоны). Согласованность порядка
     (Кендалл) внутри групп, ожидание регистраций — по группе. Перестановка второй базы внутри группы.
  5. ОБЪЁМ ДНЯ. Разрез по числу запусков в день второй базы.
  6. «КОНТЕНТ НЕ ЗАПИСАН». В прогоне «с августом» у cf-пар с августовской первой базой тестировщик получил
     ρ по рангам 0,117 (p 0,045) — проверяем, не тень ли это зоны (у августовских баз страта была «только день»,
     без набора и без зоны): пересчитываем со стратой «день + зона» для августовских первых баз.
  7. Выбросы 3615.team / 3286.team исключены везде, как у тестировщика (они прошли бы остальные фильтры).
Фильтр везде как у тестировщика: окно закрыто, дней ≠ 1, без выбросов, без «КОНТЕНТ НЕ ЗАПИСАН» (кроме п. 6).
Только stdlib. Вывод — stdout и analysis/export/gipotezy_svod/v04_teni.txt
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(BASE, 'export', 'gipotezy_svod', 'v04_teni.txt')
N_PERM = 5000
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
SUFFIX_FROM_DAY = '2026-09-12'
ZONES = ('team', 'lol', 'casino', 'buzz')
random.seed(7)

_lines = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    _lines.append(s)
    print(s)


def f(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 'н/д'
    return f'{x:.{d}f}'


def oe(o, e):
    return o / e if e > 0 else float('nan')


def to_int(s):
    return int(float(s)) if s not in ('', None) else 0


# ------------------------------------------------------------------ математика (stdlib)
def midranks(vals):
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
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


def log_binom_pmf(k, n, p):
    if p <= 0:
        return 0.0 if k == 0 else float('-inf')
    if p >= 1:
        return 0.0 if k == n else float('-inf')
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log(1 - p))


def binom_cdf(k, n, p):
    return sum(math.exp(log_binom_pmf(i, n, p)) for i in range(0, k + 1))


def binom_test_two_sided(k, n, p):
    if n == 0:
        return float('nan')
    lp_obs = log_binom_pmf(k, n, p)
    tot = 0.0
    for i in range(0, n + 1):
        lp = log_binom_pmf(i, n, p)
        if lp <= lp_obs + 1e-12:
            tot += math.exp(lp)
    return min(1.0, tot)


def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (float('nan'), float('nan'))

    def upper_root(target, lo_p, hi_p):
        for _ in range(80):
            mid = (lo_p + hi_p) / 2
            if binom_cdf(k, n, mid) > target:
                lo_p = mid
            else:
                hi_p = mid
        return (lo_p + hi_p) / 2

    def lower_root(target, lo_p, hi_p):
        for _ in range(80):
            mid = (lo_p + hi_p) / 2
            if 1 - binom_cdf(k - 1, n, mid) < target:
                lo_p = mid
            else:
                hi_p = mid
        return (lo_p + hi_p) / 2

    lo = 0.0 if k == 0 else lower_root(alpha / 2, 0.0, 1.0)
    hi = 1.0 if k == n else upper_root(alpha / 2, 0.0, 1.0)
    return (lo, hi)


def ratio_ci(o1, e1, o0, e0):
    """(O1/E1)/(O0/E0) с точным условным интервалом (при фиксированной сумме O1 ~ Binom(O1+O0, E1/(E1+E0)))."""
    o1 = int(round(o1))
    o0 = int(round(o0))
    n = o1 + o0
    if n == 0 or e1 <= 0 or e0 <= 0:
        return (float('nan'), float('nan'), float('nan'), float('nan'))
    r = (o1 / e1) / (o0 / e0) if o0 > 0 else float('inf')
    lo, hi = clopper_pearson(o1, n)
    q = e1 / (e1 + e0)

    def conv(p):
        if p <= 0:
            return 0.0
        if p >= 1:
            return float('inf')
        return (p / (1 - p)) / (q / (1 - q))
    return (r, conv(lo), conv(hi), binom_test_two_sided(o1, n, q))


def perm_p_and_ci(vals, obs, log=False):
    vals = [v for v in vals if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))]
    if not vals or obs is None or (isinstance(obs, float) and (math.isnan(obs) or math.isinf(obs))):
        return float('nan'), (float('nan'), float('nan')), float('nan')
    vs = sorted(vals)
    lo = vs[int(0.025 * len(vs))]
    hi = vs[min(len(vs) - 1, int(0.975 * len(vs)))]
    if log:
        lv = [math.log(v) for v in vals if v > 0]
        centre = sum(lv) / len(lv) if lv else 0.0
        d_obs = abs(math.log(obs) - centre) if obs > 0 else float('inf')
        cnt = sum(1 for v in vals if (abs(math.log(v) - centre) if v > 0 else float('inf')) >= d_obs - 1e-12)
        return (cnt + 1) / (len(vals) + 1), (lo, hi), math.exp(centre)
    centre = sum(vals) / len(vals)
    d_obs = abs(obs - centre)
    cnt = sum(1 for v in vals if abs(v - centre) >= d_obs - 1e-12)
    return (cnt + 1) / (len(vals) + 1), (lo, hi), centre


# ------------------------------------------------------------------ данные
with open(SRC, encoding='utf-8', newline='') as fh:
    ROWS = list(csv.DictReader(fh))

for r in ROWS:
    r['_day'] = r['день запуска']
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_exit'] = to_int(r['вышли за 3 суток']) if r['окно закрыто'] == 'да' else None
    r['_reg'] = to_int(r['регистраций в окне 3 суток'])
    r['_zone'] = r['зона'] if r['зона'] in ZONES else 'прочие'
    r['_coarse'] = bool(r['_day'] >= SUFFIX_FROM_DAY and re.search(r'_\d+$', r['набор контента']))

DAY_VOLUME = Counter(r['_day'] for r in ROWS)


def base_filter(r, allow_no_content=False):
    if r['окно закрыто'] != 'да' or r['дней'] == '1' or r['домен'] in OUTLIERS:
        return False
    if not allow_no_content and r['набор контента'] == NO_CONTENT:
        return False
    return True


KEPT = [r for r in ROWS if base_filter(r)]
KEPT_EXT = [r for r in ROWS if base_filter(r, allow_no_content=True)]


def content_name(r):
    name = r['набор контента']
    if r['_coarse']:
        return re.sub(r'_\d+$', '', name)
    return name


def pool_key(r, mode):
    """mode: 'cd' = набор + день; 'cdz' = набор + день + зона; суффикс '_nc' = без огрублённых 12.09+;
    для «КОНТЕНТ НЕ ЗАПИСАН»: 'cd' -> только день, 'cdz' -> день + зона."""
    if mode.endswith('_nc') and r['_coarse']:
        return None
    name = 'ТОЛЬКО ДЕНЬ' if r['набор контента'] == NO_CONTENT else content_name(r)
    if mode.startswith('cdz'):
        return (name, r['_day'], r['_zone'])
    return (name, r['_day'])


def build_universe(rows, mode, min_pool=3):
    pools = defaultdict(list)
    for r in rows:
        k = pool_key(r, mode)
        if k is not None:
            pools[k].append(r)
    uni = {}
    n_pools = 0
    for key, members in pools.items():
        if len(members) < min_pool:
            continue
        n_pools += 1
        sites = sum(m['_sites'] for m in members)
        exits = sum(m['_exit'] for m in members)
        regs = sum(m['_reg'] for m in members)
        p_exit = exits / sites if sites else 0.0
        p_reg = regs / sites if sites else 0.0
        n_m = len(members)
        pr_exit = midranks([m['_exit'] / m['_sites'] for m in members])
        pr_reg = midranks([m['_reg'] / m['_sites'] for m in members]) if regs > 0 else [None] * n_m
        for idx, m in enumerate(members):
            e_exit = p_exit * m['_sites']
            e_reg = p_reg * m['_sites']
            uni[m['домен']] = {
                'row': m, 'pool': key, 'pool_n': n_m, 'sites': m['_sites'], 'day': m['_day'], 'zone': m['_zone'],
                'o_exit': m['_exit'], 'e_exit': e_exit, 'oe_exit': oe(m['_exit'], e_exit),
                'res_exit': (m['_exit'] - e_exit) / math.sqrt(e_exit) if e_exit > 0 else 0.0,
                'pr_exit': (pr_exit[idx] - 0.5) / n_m,
                'o_reg': m['_reg'], 'e_reg': e_reg, 'oe_reg': oe(m['_reg'], e_reg),
                'res_reg': (m['_reg'] - e_reg) / math.sqrt(e_reg) if e_reg > 0 else 0.0,
                'pr_reg': (pr_reg[idx] - 0.5) / n_m if pr_reg[idx] is not None else None,
            }
    return uni, n_pools


def build_pairs(universe, acc_field):
    by_acc = defaultdict(list)
    for r in ROWS:
        a = r[acc_field].strip()
        if a:
            by_acc[a].append(r)
    pairs = []
    for acc, rs in by_acc.items():
        rs_sorted = sorted(rs, key=lambda r: (r['_day'], r['домен']))
        ordinal = {r['домен']: i + 1 for i, r in enumerate(rs_sorted)}
        usable = [r for r in rs_sorted if r['домен'] in universe]
        for a, b in zip(usable, usable[1:]):
            A, B = universe[a['домен']], universe[b['домен']]
            pairs.append({'acc': acc, 'A': A, 'B': B, 'label': f'{ordinal[a["домен"]]}→{ordinal[b["домен"]]}'})
    return pairs


# ------------------------------------------------------------------ статистики по парам (как у тестировщика)
def pair_stats(pairs, n_perm=N_PERM):
    n = len(pairs)
    res = {'n': n}
    if n < 10:
        return res
    a_oe = [p['A']['oe_exit'] for p in pairs]
    b_oe = [p['B']['oe_exit'] for p in pairs]
    ra, rb = midranks(a_oe), midranks(b_oe)
    a_pr = [p['A']['pr_exit'] for p in pairs]
    b_pr = [p['B']['pr_exit'] for p in pairs]
    a_res = [p['A']['res_exit'] for p in pairs]
    b_res = [p['B']['res_exit'] for p in pairs]
    first_reg = [1 if p['A']['o_reg'] > 0 else 0 for p in pairs]
    b_oreg = [p['B']['o_reg'] for p in pairs]
    b_ereg = [p['B']['e_reg'] for p in pairs]
    groups = list(defaultdict(list, {}).values())
    g = defaultdict(list)
    for i, p in enumerate(pairs):
        g[p['B']['day']].append(i)
    groups = list(g.values())

    def rho_from(sec):
        return pearson(ra, [rb[sec[i]] for i in range(n)])

    def rho_pr_from(sec):
        return pearson(a_pr, [b_pr[sec[i]] for i in range(n)])

    def S_from(sec):
        return sum(a_res[i] * b_res[sec[i]] for i in range(n)) / n

    def ratio_from(sec):
        o1 = e1 = o0 = e0 = 0.0
        for i in range(n):
            j = sec[i]
            if first_reg[i]:
                o1 += b_oreg[j]; e1 += b_ereg[j]
            else:
                o0 += b_oreg[j]; e0 += b_ereg[j]
        return o1, e1, o0, e0

    ident = list(range(n))
    res['rho_exit'] = rho_from(ident)
    res['rho_pr_exit'] = rho_pr_from(ident)
    res['S_exit'] = S_from(ident)
    o1, e1, o0, e0 = ratio_from(ident)
    res['ratio'] = (o1, e1, o0, e0)
    res['ratio_val'] = (o1 / e1) / (o0 / e0) if e1 > 0 and e0 > 0 and o0 > 0 else float('nan')
    res['ratio_exact'] = ratio_ci(o1, e1, o0, e0)
    res['n_first_reg'] = sum(first_reg)
    res['contrib'] = sorted([(p['B']['row']['домен'], p['B']['o_reg'], p['B']['e_reg'], p['A']['row']['домен'], p['A']['o_reg'])
                             for p in pairs if p['A']['o_reg'] > 0 and p['B']['o_reg'] > 0], key=lambda t: -t[1])
    # регистрации: пары, где у обеих баз E_reg > 0
    idx_reg = [i for i, p in enumerate(pairs) if p['A']['e_reg'] > 0 and p['B']['e_reg'] > 0]
    m = len(idx_reg)
    res['n_reg'] = m
    do_reg = m >= 10
    if do_reg:
        pr = [pairs[i] for i in idx_reg]
        am_pr = [p['A']['pr_reg'] for p in pr]
        bm_pr = [p['B']['pr_reg'] for p in pr]
        am = [p['A']['res_reg'] for p in pr]
        bm = [p['B']['res_reg'] for p in pr]
        gr = defaultdict(list)
        for i, p in enumerate(pr):
            gr[p['B']['day']].append(i)
        groups_r = list(gr.values())

        def rho_reg_pr_from(sec):
            return pearson(am_pr, [bm_pr[sec[i]] for i in range(m)])

        def S_reg_from(sec):
            return sum(am[i] * bm[sec[i]] for i in range(m)) / m
        identm = list(range(m))
        res['rho_reg_pr'] = rho_reg_pr_from(identm)
        res['S_reg'] = S_reg_from(identm)
        secm = list(range(m))
    null = defaultdict(list)
    sec = list(range(n))
    for _ in range(n_perm):
        for gg in groups:
            sh = gg[:]
            random.shuffle(sh)
            for k, i in enumerate(gg):
                sec[i] = sh[k]
        null['rho_exit'].append(rho_from(sec))
        null['rho_pr_exit'].append(rho_pr_from(sec))
        null['S_exit'].append(S_from(sec))
        o1, e1, o0, e0 = ratio_from(sec)
        null['ratio_val'].append((o1 / e1) / (o0 / e0) if e1 > 0 and e0 > 0 and o0 > 0 else float('nan'))
        if do_reg:
            for gg in groups_r:
                sh = gg[:]
                random.shuffle(sh)
                for k, i in enumerate(gg):
                    secm[i] = sh[k]
            null['rho_reg_pr'].append(rho_reg_pr_from(secm))
            null['S_reg'].append(S_reg_from(secm))
    for name in ('rho_exit', 'rho_pr_exit', 'S_exit', 'ratio_val') + (('rho_reg_pr', 'S_reg') if do_reg else ()):
        pv, ci, centre = perm_p_and_ci(null[name], res[name], log=(name == 'ratio_val'))
        res[name + '_p'] = pv
        res[name + '_ci'] = ci
        res[name + '_null'] = centre
    res['sites'] = sum(p['A']['sites'] + p['B']['sites'] for p in pairs)
    res['regs'] = sum(p['A']['o_reg'] + p['B']['o_reg'] for p in pairs)
    res['same_zone'] = sum(1 for p in pairs if p['A']['zone'] == p['B']['zone'])
    return res


def print_stats(title, st, contrib=False):
    P(f'--- {title}')
    if st.get('n', 0) < 10:
        P(f'   пар: {st.get("n", 0)} — мало')
        return
    P(f'   пар {st["n"]} (в одной зоне {st["same_zone"]}), сайтов {st["sites"]}, регистраций в окне {st["regs"]}')
    P(f'   ВЫХОД: ρ Спирмена по O/E = {f(st["rho_exit"], 3)} (p {f(st["rho_exit_p"], 3)}; нуль {f(st["rho_exit_null"], 3)}, 95% {f(st["rho_exit_ci"][0], 3)}..{f(st["rho_exit_ci"][1], 3)});'
      f'  ρ по рангам внутри пула = {f(st["rho_pr_exit"], 3)} (p {f(st["rho_pr_exit_p"], 3)});'
      f'  S = {f(st["S_exit"], 3)} (p {f(st["S_exit_p"], 3)}; нуль 95% {f(st["S_exit_ci"][0], 3)}..{f(st["S_exit_ci"][1], 3)})')
    if 'rho_reg_pr' in st:
        P(f'   РЕГИСТРАЦИИ ({st["n_reg"]} пар с E>0): ρ по рангам внутри пула = {f(st["rho_reg_pr"], 3)} (p {f(st["rho_reg_pr_p"], 3)}; нуль 95% {f(st["rho_reg_pr_ci"][0], 3)}..{f(st["rho_reg_pr_ci"][1], 3)});'
          f'  S = {f(st["S_reg"], 3)} (p {f(st["S_reg_p"], 3)}; нуль 95% {f(st["S_reg_ci"][0], 3)}..{f(st["S_reg_ci"][1], 3)})')
    o1, e1, o0, e0 = st['ratio']
    r, lo, hi, pb = st['ratio_exact']
    P(f'   2×2 рег. второй: первая С рег. ({st["n_first_reg"]} пар) O {o1:.0f} / E {f(e1)} = {f(oe(o1, e1))};  первая БЕЗ ({st["n"] - st["n_first_reg"]} пар) O {o0:.0f} / E {f(e0)} = {f(oe(o0, e0))};'
      f'  отношение {f(r)} (точн. 95% {f(lo)}..{f(hi)}, бином. p {f(pb, 3)}; перест. p {f(st["ratio_val_p"], 3)}, нуль 95% {f(st["ratio_val_ci"][0])}..{f(st["ratio_val_ci"][1])})')
    if contrib and st['contrib']:
        P('   вклад во «вторая с рег. при первой с рег.» (вторая: O / E; первая: O): ' +
          '; '.join(f'{d} {o:.0f}/{f(e)} ← {da} {oa:.0f}' for d, o, e, da, oa in st['contrib'][:6]))


# ------------------------------------------------------------------ самый жёсткий парный дизайн: группа = (пул A, пул B)
def group_design(pairs, n_perm=N_PERM, title=''):
    """Внутри группы (пул A, пул B) у всех пар одинаковые набор/день (и зона в варианте cdz) обеих баз.
    Выход: Кендалл-согласованность порядка (сумма C−D по группам) и знаковый вариант «B лучше при A лучше».
    Регистрации: 2×2 «первая с рег./без» × O/E второй, ожидание — по группе (доля рег. на сайт среди B группы).
    Перестановка: вторые базы тасуются внутри группы."""
    P(f'--- {title}')
    grp = defaultdict(list)
    for p in pairs:
        grp[(p['A']['pool'], p['B']['pool'])].append(p)
    G = [v for v in grp.values() if len(v) >= 2]
    n_pairs = sum(len(v) for v in G)
    P(f'   групп (пул A, пул B) с >= 2 парами: {len(G)}; пар в них: {n_pairs} из {len(pairs)}; '
      f'размеры групп: ' + ', '.join(f'{k}:{v}' for k, v in sorted(Counter(len(v) for v in G).items())))
    if len(G) < 3:
        P('   мало групп')
        return None
    # подготовка
    data = []
    for v in G:
        xa = [p['A']['o_exit'] / p['A']['sites'] for p in v]
        xb = [p['B']['o_exit'] / p['B']['sites'] for p in v]
        ra_ = [p['A']['o_reg'] for p in v]
        rb_ = [p['B']['o_reg'] for p in v]
        sb = [p['B']['sites'] for p in v]
        data.append((xa, xb, ra_, rb_, sb))

    def kendall_T(sec_list):
        C = D = 0
        for (xa, xb, _, _, _), sec in zip(data, sec_list):
            k = len(xa)
            for i in range(k):
                for j in range(i + 1, k):
                    s = (xa[i] - xa[j]) * (xb[sec[i]] - xb[sec[j]])
                    if s > 0:
                        C += 1
                    elif s < 0:
                        D += 1
        return C, D

    def ratio_T(sec_list):
        o1 = e1 = o0 = e0 = 0.0
        for (xa, xb, ra_, rb_, sb), sec in zip(data, sec_list):
            tot_r = sum(rb_)
            if tot_r == 0:
                continue
            has = [1 if r > 0 else 0 for r in ra_]
            if sum(has) == 0 or sum(has) == len(has):
                continue
            rate = tot_r / sum(sb)
            for i in range(len(xa)):
                j = sec[i]
                if has[i]:
                    o1 += rb_[j]; e1 += rate * sb[j]
                else:
                    o0 += rb_[j]; e0 += rate * sb[j]
        return o1, e1, o0, e0

    def exit_split_T(sec_list):
        """выход второй при первой выше/ниже медианы группы (по A), ожидание — по группе."""
        o1 = e1 = o0 = e0 = 0.0
        for (xa, xb, _, _, sb), sec in zip(data, sec_list):
            k = len(xa)
            srt = sorted(xa)
            med = srt[k // 2] if k % 2 else (srt[k // 2 - 1] + srt[k // 2]) / 2
            tot_o = sum(xb[i] * sb[i] for i in range(k))
            rate = tot_o / sum(sb)
            for i in range(k):
                j = sec[i]
                if xa[i] > med:
                    o1 += xb[j] * sb[j]; e1 += rate * sb[j]
                elif xa[i] < med:
                    o0 += xb[j] * sb[j]; e0 += rate * sb[j]
        return o1, e1, o0, e0

    ident = [list(range(len(v))) for v in G]
    C, D = kendall_T(ident)
    tau = (C - D) / (C + D) if (C + D) else float('nan')
    o1, e1, o0, e0 = ratio_T(ident)
    ratio = (o1 / e1) / (o0 / e0) if e1 > 0 and e0 > 0 and o0 > 0 else float('nan')
    x1, y1, x0, y0 = exit_split_T(ident)
    ex_ratio = (x1 / y1) / (x0 / y0) if y1 > 0 and y0 > 0 and x0 > 0 else float('nan')
    null_tau, null_ratio, null_ex = [], [], []
    for _ in range(n_perm):
        secs = []
        for v in G:
            s = list(range(len(v)))
            random.shuffle(s)
            secs.append(s)
        c, d = kendall_T(secs)
        null_tau.append((c - d) / (c + d) if (c + d) else float('nan'))
        a1, b1, a0, b0 = ratio_T(secs)
        null_ratio.append((a1 / b1) / (a0 / b0) if b1 > 0 and b0 > 0 and a0 > 0 else float('nan'))
        a1, b1, a0, b0 = exit_split_T(secs)
        null_ex.append((a1 / b1) / (a0 / b0) if b1 > 0 and b0 > 0 and a0 > 0 else float('nan'))
    p_tau, ci_tau, c_tau = perm_p_and_ci(null_tau, tau)
    p_r, ci_r, c_r = perm_p_and_ci(null_ratio, ratio, log=True)
    p_ex, ci_ex, c_ex = perm_p_and_ci(null_ex, ex_ratio, log=True)
    n_used_reg = sum(len(v) for (xa, xb, ra_, rb_, sb), v in zip(data, G) if sum(rb_) > 0 and 0 < sum(1 for r in ra_ if r > 0) < len(ra_))
    P(f'   ВЫХОД, согласованность порядка внутри групп: C = {C}, D = {D}, τ = {f(tau, 3)} (перест. p {f(p_tau, 3)}; нуль {f(c_tau, 3)}, 95% {f(ci_tau[0], 3)}..{f(ci_tau[1], 3)})')
    P(f'   ВЫХОД, вторая при первой выше / ниже медианы группы: O/E {f(oe(x1, y1), 3)} ({x1:.0f}/{f(y1, 1)}) против {f(oe(x0, y0), 3)} ({x0:.0f}/{f(y0, 1)}); '
      f'отношение {f(ex_ratio, 3)} (перест. p {f(p_ex, 3)}, нуль 95% {f(ci_ex[0], 3)}..{f(ci_ex[1], 3)})')
    r_ex = ratio_ci(o1, e1, o0, e0)
    P(f'   РЕГИСТРАЦИИ, ожидание по группе (пар в пригодных группах: {n_used_reg}): первая С рег. O {o1:.0f} / E {f(e1)}; БЕЗ O {o0:.0f} / E {f(e0)}; '
      f'отношение {f(ratio)} (точн. 95% {f(r_ex[1])}..{f(r_ex[2])}; перест. p {f(p_r, 3)}, нуль 95% {f(ci_r[0])}..{f(ci_r[1])})')
    return {'tau': tau, 'p_tau': p_tau, 'ratio': ratio, 'p_r': p_r, 'ex_ratio': ex_ratio, 'p_ex': p_ex, 'n_groups': len(G), 'n_pairs': n_pairs}


def zero_contagion(universe, acc_field, title, n_perm=N_PERM):
    by_acc = defaultdict(list)
    for d, u in universe.items():
        a = u['row'][acc_field].strip()
        if a:
            by_acc[a].append(u)
    sibs = {}
    zero_bases = [u for u in universe.values() if u['o_exit'] == 0]
    for z in zero_bases:
        a = z['row'][acc_field].strip()
        for o in by_acc.get(a, []):
            if o['row']['домен'] != z['row']['домен']:
                sibs[o['row']['домен']] = o
    sibs = list(sibs.values())
    if not sibs:
        P(f'   {title}: сиблингов нулевых баз нет')
        return
    S = sum(u['sites'] for u in sibs)
    O = sum(u['o_exit'] for u in sibs)
    E = sum(u['e_exit'] for u in sibs)
    by_day = defaultdict(list)
    for u in universe.values():
        by_day[u['day']].append(u)
    null = []
    for _ in range(n_perm):
        o = e = 0.0
        for u in sibs:
            v = random.choice(by_day[u['day']])
            o += v['o_exit']; e += v['e_exit']
        null.append(o / e if e > 0 else float('nan'))
    pv, ci, c = perm_p_and_ci(null, oe(O, E))
    P(f'   {title}: нулевых баз {len(zero_bases)}, их сиблингов {len(sibs)} ({S} сайтов): O {O:.0f} / E {f(E, 1)} = {f(oe(O, E), 3)} (перест. p {f(pv, 3)}, нуль 95% {f(ci[0], 3)}..{f(ci[1], 3)})')


# ------------------------------------------------------------------ 0. базовые числа
P('=' * 110)
P('СКЕПТИК К ГИПОТЕЗЕ №4 — ТЕНИ (конфаундинг). Фильтр как у тестировщика: окно закрыто, дней ≠ 1, без 3615/3286, без «КОНТЕНТ НЕ ЗАПИСАН»')
P('=' * 110)
P(f'Доменов после фильтра: {len(KEPT)} (с августом: {len(KEPT_EXT)}); перестановок в каждом тесте: {N_PERM}, random.seed(7)')

UNI = {}
for mode in ('cd', 'cdz', 'cd_nc', 'cdz_nc'):
    UNI[mode], npools = build_universe(KEPT, mode)
    P(f'   страта «{mode}»: пулов >= 3 баз: {npools}, доменов в них: {len(UNI[mode])}, сайтов {sum(u["sites"] for u in UNI[mode].values())}, '
      f'вышло {sum(u["o_exit"] for u in UNI[mode].values())}, регистраций {sum(u["o_reg"] for u in UNI[mode].values())}')
P('   (cd = набор + день; cdz = набор + день + зона; _nc = без 490 огрублённых доменов 12.09+ с именем набора content-…_NN)')

# ------------------------------------------------------------------ 1. зона как примесь внутри пула «набор + день»
P()
P('=' * 110)
P('1. ЗОНА ВНУТРИ ПУЛА «НАБОР + ДЕНЬ»: насколько остатки e_i несут зонную примесь')
P('=' * 110)
zs = defaultdict(lambda: [0, 0.0, 0, 0.0, 0])
for u in UNI['cd'].values():
    z = zs[u['zone']]
    z[0] += u['o_exit']; z[1] += u['e_exit']; z[2] += u['o_reg']; z[3] += u['e_reg']; z[4] += 1
for z in list(ZONES) + ['прочие']:
    if z in zs:
        o, e, orr, er, n = zs[z]
        P(f'   зона {z:7s}: {n:4d} баз; выход O/E внутри пулов «набор+день» = {f(oe(o, e), 3)} ({o}/{f(e, 1)}); регистрации O/E = {f(oe(orr, er))} ({orr}/{f(er, 1)})')
# доля пулов, где есть несколько зон
mixed = defaultdict(set)
for u in UNI['cd'].values():
    mixed[u['pool']].add(u['zone'])
n_mixed = sum(1 for v in mixed.values() if len(v) > 1)
P(f'   пулов «набор+день» с несколькими зонами: {n_mixed} из {len(mixed)} → зонная примесь в остатках есть в большинстве пулов')
for acc_field, acc_name in (('cf-аккаунт', 'cf'), ('аккаунт вебмастера', 'Вебмастер')):
    pairs = build_pairs(UNI['cd'], acc_field)
    zz = Counter((p['A']['zone'], p['B']['zone']) for p in pairs)
    P(f'   {acc_name}: пары по зонам (A→B): ' + ', '.join(f'{a}→{b}: {c}' for (a, b), c in zz.most_common(8)))

# ------------------------------------------------------------------ 2. жёсткие страты
P()
P('=' * 110)
P('2. ЖЁСТКИЕ СТРАТЫ: те же статистики, что у тестировщика, при пуле «набор + день + зона», без огрубления 12.09+, без .buzz/прочих')
P('=' * 110)
RES = {}
for acc_field, acc_name in (('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')):
    P()
    P(f'### {acc_name}')
    for mode, label in (('cd', 'набор + день (воспроизведение тестировщика)'),
                        ('cdz', 'набор + день + ЗОНА'),
                        ('cd_nc', 'набор + день, без огрублённых 12.09+'),
                        ('cdz_nc', 'набор + день + зона, без огрублённых 12.09+')):
        pairs = build_pairs(UNI[mode], acc_field)
        st = pair_stats(pairs)
        RES[(acc_field, mode)] = st
        print_stats(f'{acc_name}, страта «{label}»', st, contrib=(mode == 'cdz'))
    # без .buzz и прочих (страта cdz)
    pairs = [p for p in build_pairs(UNI['cdz'], acc_field) if p['A']['zone'] in ('team', 'lol', 'casino') and p['B']['zone'] in ('team', 'lol', 'casino')]
    st = pair_stats(pairs)
    RES[(acc_field, 'cdz_nobuzz')] = st
    print_stats(f'{acc_name}, страта «набор + день + зона», обе базы в team/lol/casino', st)
    # только пары одной зоны при страте cdz (у тестировщика при cd: ρ выход −0,111, p 0,053)
    pairs = [p for p in build_pairs(UNI['cdz'], acc_field) if p['A']['zone'] == p['B']['zone']]
    st = pair_stats(pairs)
    RES[(acc_field, 'cdz_samezone')] = st
    print_stats(f'{acc_name}, страта «набор + день + зона», только пары одной зоны', st)
    pairs = [p for p in build_pairs(UNI['cdz'], acc_field) if p['A']['zone'] != p['B']['zone']]
    st = pair_stats(pairs)
    RES[(acc_field, 'cdz_diffzone')] = st
    print_stats(f'{acc_name}, страта «набор + день + зона», только пары разных зон', st)
    P()
    P(f'--- {acc_name}: заразность нулей при жёстких стратах')
    for mode in ('cd', 'cdz', 'cdz_nc'):
        zero_contagion(UNI[mode], acc_field, f'страта «{mode}»')

# ------------------------------------------------------------------ 3. самый жёсткий парный дизайн
P()
P('=' * 110)
P('3. САМЫЙ ЖЁСТКИЙ ПАРНЫЙ ДИЗАЙН: группа = (пул первой базы, пул второй базы); тасуем вторые базы внутри группы')
P('=' * 110)
P('   Внутри группы все пары имеют один и тот же набор и день у первой базы И один и тот же набор и день у второй')
P('   (в варианте cdz — и зоны). Тени набора, дня, зоны, объёма дня, партии — сняты полностью: сравниваются только аккаунты.')
GD = {}
for acc_field, acc_name in (('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')):
    P()
    for mode in ('cd', 'cdz'):
        pairs = build_pairs(UNI[mode], acc_field)
        GD[(acc_field, mode)] = group_design(pairs, title=f'{acc_name}, группы по страте «{mode}»')

# ------------------------------------------------------------------ 4. объём дня
P()
P('=' * 110)
P('4. ОБЪЁМ ДНЯ: разрез по числу запусков в день второй базы (страта «набор + день + зона»)')
P('=' * 110)
for acc_field, acc_name in (('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')):
    pairs = build_pairs(UNI['cdz'], acc_field)
    vols = sorted(DAY_VOLUME[p['B']['day']] for p in pairs)
    t1, t2 = vols[len(vols) // 3], vols[2 * len(vols) // 3]
    for name, cond in ((f'день B малый (<= {t1} запусков)', lambda p: DAY_VOLUME[p['B']['day']] <= t1),
                       (f'день B средний ({t1 + 1}..{t2})', lambda p: t1 < DAY_VOLUME[p['B']['day']] <= t2),
                       (f'день B большой (> {t2})', lambda p: DAY_VOLUME[p['B']['day']] > t2)):
        sub = [p for p in pairs if cond(p)]
        st = pair_stats(sub, n_perm=2000)
        if st.get('n', 0) < 10:
            P(f'   {acc_name}, {name}: {len(sub)} пар — мало')
            continue
        o1, e1, o0, e0 = st['ratio']
        r, lo, hi, pb = st['ratio_exact']
        P(f'   {acc_name}, {name}: {st["n"]} пар; ρ выход {f(st["rho_exit"], 3)} (p {f(st["rho_exit_p"], 3)}), S {f(st["S_exit"], 3)} (p {f(st["S_exit_p"], 3)}); '
          + (f'ρ рег (ранги в пуле) {f(st["rho_reg_pr"], 3)} (p {f(st["rho_reg_pr_p"], 3)}) на {st["n_reg"]} парах; ' if 'rho_reg_pr' in st else 'ρ рег: мало пар; ')
          + f'отношение по рег {f(r)} ({f(lo)}..{f(hi)}; O {o1:.0f}/{o0:.0f})')

# ------------------------------------------------------------------ 5. вклад пар «первая с регистрацией» и порядок внутри аккаунта
P()
P('=' * 110)
P('5. ОТНОШЕНИЕ ПО РЕГИСТРАЦИЯМ: откуда берётся 0,69 (cf) и 2,85 (Вебмастер), и что с ним делает зона в страте')
P('=' * 110)
for acc_field, acc_name in (('cf-аккаунт', 'cf'), ('аккаунт вебмастера', 'Вебмастер')):
    for mode in ('cd', 'cdz'):
        st = RES[(acc_field, mode)]
        o1, e1, o0, e0 = st['ratio']
        r, lo, hi, pb = st['ratio_exact']
        P(f'   {acc_name}, страта «{mode}»: отношение {f(r)} ({f(lo)}..{f(hi)}); первая С рег.: O {o1:.0f} / E {f(e1)}; БЕЗ: O {o0:.0f} / E {f(e0)}')
    # без двух самых «тяжёлых» вторых баз
    for mode in ('cd', 'cdz'):
        pairs = build_pairs(UNI[mode], acc_field)
        st = RES[(acc_field, mode)]
        top = [t[0] for t in st['contrib'][:2]]
        sub = [p for p in pairs if p['B']['row']['домен'] not in top]
        o1 = sum(p['B']['o_reg'] for p in sub if p['A']['o_reg'] > 0); e1 = sum(p['B']['e_reg'] for p in sub if p['A']['o_reg'] > 0)
        o0 = sum(p['B']['o_reg'] for p in sub if p['A']['o_reg'] == 0); e0 = sum(p['B']['e_reg'] for p in sub if p['A']['o_reg'] == 0)
        r, lo, hi, pb = ratio_ci(o1, e1, o0, e0)
        P(f'   {acc_name}, страта «{mode}», без двух самых тяжёлых вторых баз ({", ".join(top)}): отношение {f(r)} ({f(lo)}..{f(hi)}); O {o1:.0f}/{f(e1)} против {o0:.0f}/{f(e0)}')
    # обратное направление: вторая с регистрацией → O/E первой (симметрия; если «аккаунт», связь симметрична)
    pairs = build_pairs(UNI['cdz'], acc_field)
    o1 = sum(p['A']['o_reg'] for p in pairs if p['B']['o_reg'] > 0); e1 = sum(p['A']['e_reg'] for p in pairs if p['B']['o_reg'] > 0)
    o0 = sum(p['A']['o_reg'] for p in pairs if p['B']['o_reg'] == 0); e0 = sum(p['A']['e_reg'] for p in pairs if p['B']['o_reg'] == 0)
    r, lo, hi, pb = ratio_ci(o1, e1, o0, e0)
    P(f'   {acc_name}, страта «cdz», ОБРАТНО (первая по второй): вторая С рег. → O/E первой {f(oe(o1, e1))} ({o1:.0f}/{f(e1)}); БЕЗ → {f(oe(o0, e0))} ({o0:.0f}/{f(e0)}); отношение {f(r)} ({f(lo)}..{f(hi)})')
    # симметричный вариант: обе базы с регистрацией — сколько аккаунтов против ожидания при независимости внутри пулов
    n_both = sum(1 for p in pairs if p['A']['o_reg'] > 0 and p['B']['o_reg'] > 0)
    # ожидание: сумма по парам P(A>0)·P(B>0) при пуассоне с E
    exp_both = sum((1 - math.exp(-p['A']['e_reg'])) * (1 - math.exp(-p['B']['e_reg'])) for p in pairs)
    P(f'   {acc_name}, страта «cdz»: пар, где ОБЕ базы с регистрацией: {n_both} при ожидании {f(exp_both, 1)} (пуассон по E пулов, независимость)')

# ------------------------------------------------------------------ 6. август: ρ 0,117 у cf-пар с августовской первой — тень зоны?
P()
P('=' * 110)
P('6. ПРОГОН «С АВГУСТОМ»: у тестировщика cf-пары с августовской первой базой дали ρ по рангам 0,117 (p 0,045) при страте «только день».')
P('   Проверка: страта для августовских баз «день + зона», для остальных «набор + день + зона»')
P('=' * 110)
UNI_E = {}
for mode in ('cd', 'cdz'):
    UNI_E[mode], npools = build_universe(KEPT_EXT, mode)
    P(f'   страта «{mode}» с августом: пулов {npools}, доменов {len(UNI_E[mode])} (без записанного набора: {sum(1 for u in UNI_E[mode].values() if u["row"]["набор контента"] == NO_CONTENT)})')
for acc_field, acc_name in (('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')):
    for mode in ('cd', 'cdz'):
        pairs = build_pairs(UNI_E[mode], acc_field)
        sub = [p for p in pairs if p['A']['row']['набор контента'] == NO_CONTENT]
        st = pair_stats(sub)
        RES[(acc_field, 'aug_' + mode)] = st
        print_stats(f'{acc_name} с августом, только пары с августовской первой базой, страта «{mode}»', st)
        st_all = pair_stats(pairs)
        RES[(acc_field, 'ext_' + mode)] = st_all
        print_stats(f'{acc_name} с августом, все пары, страта «{mode}»', st_all)
    P()
    pairs = build_pairs(UNI_E['cdz'], acc_field)
    GD[(acc_field, 'ext_cdz')] = group_design(pairs, title=f'{acc_name} с августом, группы (пул A, пул B) по страте «cdz»')
    P()

# ------------------------------------------------------------------ 6б. знакопеременные разрезы: одна/разные зоны × месяц первой базы × порядок
P()
P('=' * 110)
P('6б. ЗНАКОПЕРЕМЕННЫЕ РАЗРЕЗЫ: в п. 2 у cf пары одной зоны дали ρ −0,134 (p 0,023), разных зон +0,114 (p 0,030).')
P('    Смотрим, держится ли знак при добавлении августа, по месяцу первой базы, по порядку и по зоне; группы (пул A, пул B) отдельно')
P('=' * 110)


def short(title, pairs, n_perm=3000):
    st = pair_stats(pairs, n_perm=n_perm)
    if st.get('n', 0) < 10:
        P(f'   {title}: {st.get("n", 0)} пар — мало')
        return
    P(f'   {title}: пар {st["n"]}; ρ по O/E {f(st["rho_exit"], 3)} (p {f(st["rho_exit_p"], 3)}); ρ по рангам в пуле {f(st["rho_pr_exit"], 3)} (p {f(st["rho_pr_exit_p"], 3)}); '
      f'S {f(st["S_exit"], 3)} (p {f(st["S_exit_p"], 3)})')


for acc_field, acc_name in (('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')):
    P(f'--- {acc_name}, основной прогон, страта «cdz»')
    pairs = build_pairs(UNI['cdz'], acc_field)
    same = [p for p in pairs if p['A']['zone'] == p['B']['zone']]
    for lab in ('1→2', '2→3'):
        short(f'одна зона, пары {lab}', [p for p in same if p['label'] == lab])
    for z in ('team', 'lol'):
        short(f'одна зона = {z}', [p for p in same if p['B']['zone'] == z])
    group_design(same, n_perm=3000, title=f'{acc_name}, cdz, группы (пул A, пул B), только пары одной зоны')
    group_design([p for p in pairs if p['A']['zone'] != p['B']['zone']], n_perm=3000, title=f'{acc_name}, cdz, группы (пул A, пул B), только пары разных зон')
    P(f'--- {acc_name}, прогон с августом, страта «cdz» (августовские базы — «день + зона»)')
    pairs_e = build_pairs(UNI_E['cdz'], acc_field)
    same_e = [p for p in pairs_e if p['A']['zone'] == p['B']['zone']]
    diff_e = [p for p in pairs_e if p['A']['zone'] != p['B']['zone']]
    short('одна зона, все', same_e)
    short('разные зоны, все', diff_e)
    short('одна зона, первая база августовская (без набора)', [p for p in same_e if p['A']['row']['набор контента'] == NO_CONTENT])
    short('одна зона, первая база с записанным набором', [p for p in same_e if p['A']['row']['набор контента'] != NO_CONTENT])
    short('разные зоны, первая база августовская (без набора)', [p for p in diff_e if p['A']['row']['набор контента'] == NO_CONTENT])
    short('разные зоны, первая база с записанным набором', [p for p in diff_e if p['A']['row']['набор контента'] != NO_CONTENT])
    group_design(same_e, n_perm=3000, title=f'{acc_name} с августом, cdz, группы (пул A, пул B), одна зона')
    group_design(diff_e, n_perm=3000, title=f'{acc_name} с августом, cdz, группы (пул A, пул B), разные зоны')
    P()

# ------------------------------------------------------------------ 7. итог
P()
P('=' * 110)
P('7. СВОДКА ПО ТЕНЯМ')
P('=' * 110)
P(f'{"аккаунт":11s} {"страта":34s} {"пар":>4s} {"ρ выход":>8s} {"p":>6s} {"S выход":>8s} {"p":>6s} {"ρ рег":>7s} {"p":>6s} {"отн.рег":>8s} {"95%":>13s}')
for acc_field, acc_name in (('cf-аккаунт', 'cf'), ('аккаунт вебмастера', 'Вебмастер')):
    for mode, label in (('cd', 'набор+день'), ('cdz', 'набор+день+зона'), ('cd_nc', 'набор+день, без 12.09+'),
                        ('cdz_nc', 'набор+день+зона, без 12.09+'), ('cdz_nobuzz', 'cdz, без buzz/прочих'),
                        ('cdz_samezone', 'cdz, одна зона'), ('cdz_diffzone', 'cdz, разные зоны'),
                        ('aug_cd', 'август: первая «день»'), ('aug_cdz', 'август: первая «день+зона»'),
                        ('ext_cd', 'с августом, все, cd'), ('ext_cdz', 'с августом, все, cdz')):
        st = RES.get((acc_field, mode), {})
        if st.get('n', 0) < 10:
            continue
        r, lo, hi, pb = st['ratio_exact']
        P(f'{acc_name:11s} {label:34s} {st["n"]:4d} {f(st["rho_exit"], 3):>8s} {f(st["rho_exit_p"], 3):>6s} {f(st["S_exit"], 3):>8s} {f(st["S_exit_p"], 3):>6s} '
          f'{f(st.get("rho_reg_pr", float("nan")), 3):>7s} {f(st.get("rho_reg_pr_p", float("nan")), 3):>6s} {f(r):>8s} {f(lo) + ".." + f(hi):>13s}')
P()
P('Группы (пул A, пул B):')
for (acc_field, mode), g in GD.items():
    if g:
        P(f'   {acc_field:20s} {mode:8s}: групп {g["n_groups"]}, пар {g["n_pairs"]}; τ выход {f(g["tau"], 3)} (p {f(g["p_tau"], 3)}); '
          f'выход второй при первой выше/ниже медианы {f(g["ex_ratio"], 3)} (p {f(g["p_ex"], 3)}); отношение по рег {f(g["ratio"])} (p {f(g["p_r"], 3)})')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

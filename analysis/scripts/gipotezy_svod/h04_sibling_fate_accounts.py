#!/usr/bin/env python3
"""
Гипотеза №4. Базы одного cf-аккаунта (и одного аккаунта Вебмастера) не делят судьбу.

Что проверяем.
  Отклонения сиблингов (баз одного аккаунта) от своих пулов «набор контента + день
  запуска» по выходу в поиск и по регистрациям в окне 3 суток независимы: ни удача,
  ни провал, ни «нуль» первой базы не переносятся на следующую базу того же аккаунта.
  Два аккаунта проверяются отдельно: cf-аккаунт (поле «cf-аккаунт», ни разу не
  проверялось) и аккаунт Вебмастера (поле «аккаунт вебмастера»).

Как проверяем.
  Фильтр: окно закрыто = да; дней != 1; без выбросов 3615.team и 3286.team;
  без «КОНТЕНТ НЕ ЗАПИСАН» (основной прогон). Печатаем, сколько строк отсеяно.
  Пул = набор контента + день запуска; берём только пулы с >= 3 базами.
  Огрубление: с 12.09 часть наборов именуется по одному на домен (корень + _NN);
  для таких имён пул = корень имени (без суффикса _NN) + день. Это оговорено.
  Остатки для каждой базы i:
    выход:       O_i = вышли за 3 суток, E_i = доля пула × сайтов в окне,
                 e_i = (O_i − E_i)/√E_i;
    регистрации: O_i = регистраций в окне 3 суток, E_i = рег пула на сайт × сайтов
                 в окне, m_i = (O_i − E_i)/√E_i (пулы без единой регистрации дают
                 E_i = 0 — такие базы в статистиках по регистрациям не участвуют).
  Пары сиблингов: у каждого аккаунта его пригодные базы упорядочены по дате, пары —
  соседние по дате (1→2, 2→3). Порядковый номер считается по всем базам аккаунта
  во всём своде (в том числе отсеянным).
  Статистики по парам:
    ρ — Спирмен между O/E сиблингов (выход; регистрации — по остаткам m и по O/E);
    S — среднее произведение остатков по парам (выход и регистрации отдельно);
    отношение — 2×2: «первая с регистрацией в окне / без» × O/E регистраций второй,
    точный биномиальный (условный пуассоновский) интервал 95% по Клопперу—Пирсону.
  Нуль: 10 000 раз переназначить вторую базу среди вторых баз того же дня запуска
  (сохраняет день и состав пулов, ломает родство), пересчитать ρ, S, отношение;
  p двусторонние, для S — перестановочный интервал 95%. random.seed(1).
  Разрезы: зона второй базы (team/lol/casino/buzz), пары 1→2 и 2→3, для Вебмастера —
  разрыв между запусками (окно первой закрыто до второго запуска или нет).
  Заразность нулей: сиблинги баз с нулём выходов за 3 суток — сумма O против суммы E
  по пулам, точный биномиальный тест (при объединённой доле) и та же перестановка.
  Отдельный прогон «с августом»: базы «КОНТЕНТ НЕ ЗАПИСАН» включаются со стратой
  «только день» (набор не записан и полностью сцеплен с датой) — оговорено как
  огрубление, чтобы захватить августовские первые базы.
  Критерии: «не делят» — |ρ| < 0,1, S внутри перестановочного нуля, отношение по
  регистрациям 0,8–1,25, сиблинги нулей O/E 0,9–1,1; «связь» — ρ >= 0,15 при
  p < 0,05 или отношение >= 1,5 / <= 0,67.

Только стандартная библиотека Python 3. Вывод пишется и в stdout, и в файл
analysis/export/gipotezy_svod/h04_sibling_fate_accounts.txt.
"""

import csv
import datetime
import math
import os
import random
import re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'h04_sibling_fate_accounts.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
SUFFIX_FROM_DAY = '2026-09-12'
MIN_POOL = 3
ZONES = ['team', 'lol', 'casino', 'buzz']

random.seed(1)
_out_lines = []


def P(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _out_lines.append(s)


def f2(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 'н/д'
    return f'{x:.{d}f}'


def oe(o, e):
    return o / e if e > 0 else float('nan')


def to_int(s):
    return int(float(s)) if s not in ('', None) else 0


# ----------------------------------------------------------------------------
# Математика (stdlib)
# ----------------------------------------------------------------------------

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
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sxx * syy)


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
    """Точный двусторонний биномиальный тест: сумма вероятностей исходов не более
    вероятных, чем наблюдённый."""
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
    """Точный интервал для биномиальной доли (бисекция по функции распределения)."""
    if n == 0:
        return (float('nan'), float('nan'))

    def upper_root(target, lo_p, hi_p):
        # ищем p, при котором P(X <= k) = target (убывает по p)
        for _ in range(80):
            mid = (lo_p + hi_p) / 2
            if binom_cdf(k, n, mid) > target:
                lo_p = mid
            else:
                hi_p = mid
        return (lo_p + hi_p) / 2

    def lower_root(target, lo_p, hi_p):
        # ищем p, при котором P(X >= k) = target, т.е. 1 - P(X <= k-1) = target
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
    """Отношение (O1/E1)/(O0/E0) с точным условным интервалом: при фиксированной
    сумме O1 ~ Binom(O1+O0, E1/(E1+E0)) в нуле."""
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
    p0 = q
    pval = binom_test_two_sided(o1, n, p0)
    return (r, conv(lo), conv(hi), pval)


# ----------------------------------------------------------------------------
# Данные
# ----------------------------------------------------------------------------

with open(CSV_PATH, encoding='utf-8', newline='') as fh:
    ROWS = list(csv.DictReader(fh))

P('=' * 100)
P('ГИПОТЕЗА №4. Базы одного cf-аккаунта и одного аккаунта Вебмастера не делят судьбу')
P('=' * 100)
P(f'Файл: {CSV_PATH}')
P(f'Строк (доменов) в своде: {len(ROWS)}')

n_open = sum(1 for r in ROWS if r['окно закрыто'] != 'да')
n_day1 = sum(1 for r in ROWS if r['дней'] == '1')
n_out = sum(1 for r in ROWS if r['домен'] in OUTLIERS)
n_noc = sum(1 for r in ROWS if r['набор контента'] == NO_CONTENT)


def base_filter(r, allow_no_content=False):
    if r['окно закрыто'] != 'да':
        return False
    if r['дней'] == '1':
        return False
    if r['домен'] in OUTLIERS:
        return False
    if not allow_no_content and r['набор контента'] == NO_CONTENT:
        return False
    return True


KEPT = [r for r in ROWS if base_filter(r)]
KEPT_EXT = [r for r in ROWS if base_filter(r, allow_no_content=True)]
P()
P('Исключения (строки могут попадать в несколько категорий):')
P(f'  окно не закрыто (окно 3 суток ещё идёт): {n_open}')
P(f'  дней = 1 (150 сайтов, второго дня ещё не было): {n_day1}')
n_out_pass = sum(1 for r in ROWS if r['домен'] in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] != '1' and r['набор контента'] != NO_CONTENT)
P(f'  выбросы по «прочим» кликам {sorted(OUTLIERS)}: {n_out} (из них прошли бы остальные фильтры основного прогона: {n_out_pass})')
P(f'  «{NO_CONTENT}» (набор не записан, сцеплен с датой): {n_noc}')
P(f'Осталось после всех исключений (основной прогон): {len(KEPT)} доменов')
P(f'Осталось для прогона «с августом» (без исключения «{NO_CONTENT}»): {len(KEPT_EXT)} доменов')

for r in ROWS:
    r['_day'] = r['день запуска']
    r['_date'] = datetime.date.fromisoformat(r['день запуска'])
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_exit'] = to_int(r['вышли за 3 суток']) if r['окно закрыто'] == 'да' else None
    r['_reg'] = to_int(r['регистраций в окне 3 суток'])
    r['_zone'] = r['зона'] if r['зона'] in ZONES else 'прочие'


def content_root(name):
    return re.sub(r'_\d+$', '', name)


def pool_key(r, ext=False):
    name = r['набор контента']
    if name == NO_CONTENT:
        return ('ТОЛЬКО ДЕНЬ', r['_day'])
    if r['_day'] >= SUFFIX_FROM_DAY and re.search(r'_\d+$', name):
        return (content_root(name), r['_day'])
    return (name, r['_day'])


def build_universe(rows, ext=False):
    """Пулы >= MIN_POOL баз; остатки по выходу и регистрациям."""
    pools = defaultdict(list)
    for r in rows:
        pools[pool_key(r, ext)].append(r)
    n_coarse = sum(1 for r in rows if r['_day'] >= SUFFIX_FROM_DAY and re.search(r'_\d+$', r['набор контента']))
    universe = {}
    for key, members in pools.items():
        if len(members) < MIN_POOL:
            continue
        sites = sum(m['_sites'] for m in members)
        exits = sum(m['_exit'] for m in members)
        regs = sum(m['_reg'] for m in members)
        p_exit = exits / sites if sites else 0.0
        p_reg = regs / sites if sites else 0.0
        # ранги внутри пула, нормированные в (0,1): одинаково распределены в любом пуле
        n_m = len(members)
        pr_exit = midranks([m['_exit'] / m['_sites'] for m in members])
        pr_reg = midranks([m['_reg'] / m['_sites'] for m in members]) if regs > 0 else [None] * n_m
        for idx, m in enumerate(members):
            e_exit = p_exit * m['_sites']
            e_reg = p_reg * m['_sites']
            universe[m['домен']] = {
                'pr_exit': (pr_exit[idx] - 0.5) / n_m,
                'pr_reg': (pr_reg[idx] - 0.5) / n_m if pr_reg[idx] is not None else None,
                'row': m,
                'pool': key,
                'pool_n': len(members),
                'sites': m['_sites'],
                'o_exit': m['_exit'],
                'e_exit': e_exit,
                'res_exit': (m['_exit'] - e_exit) / math.sqrt(e_exit) if e_exit > 0 else 0.0,
                'oe_exit': oe(m['_exit'], e_exit),
                'o_reg': m['_reg'],
                'e_reg': e_reg,
                'res_reg': (m['_reg'] - e_reg) / math.sqrt(e_reg) if e_reg > 0 else 0.0,
                'oe_reg': oe(m['_reg'], e_reg),
                'day': m['_day'],
                'date': m['_date'],
                'zone': m['_zone'],
            }
    n_pools = sum(1 for v in pools.values() if len(v) >= MIN_POOL)
    dropped = len(rows) - len(universe)
    return universe, n_pools, dropped, n_coarse


# ----------------------------------------------------------------------------
# Пары сиблингов
# ----------------------------------------------------------------------------

def build_pairs(universe, acc_field):
    """Соседние по дате пары пригодных баз одного аккаунта.
    Порядковый номер — по всем базам аккаунта в своде (включая отсеянные)."""
    all_by_acc = defaultdict(list)
    for r in ROWS:
        a = r[acc_field].strip()
        if a:
            all_by_acc[a].append(r)
    pairs = []
    n_acc_usable = 0
    for acc, rs in all_by_acc.items():
        rs_sorted = sorted(rs, key=lambda r: (r['_date'], r['домен']))
        ordinal = {r['домен']: i + 1 for i, r in enumerate(rs_sorted)}
        usable = [r for r in rs_sorted if r['домен'] in universe]
        if len(usable) < 2:
            continue
        n_acc_usable += 1
        for a, b in zip(usable, usable[1:]):
            A = universe[a['домен']]
            B = universe[b['домен']]
            pairs.append({
                'acc': acc,
                'A': A, 'B': B,
                'label': f'{ordinal[a["домен"]]}→{ordinal[b["домен"]]}',
                'gap': (B['date'] - A['date']).days,
                'acc_total': len(rs_sorted),
            })
    return pairs, n_acc_usable


# ----------------------------------------------------------------------------
# Перестановочный тест по парам
# ----------------------------------------------------------------------------

def pair_stats(pairs, n_perm=N_PERM, do_reg=True):
    """Наблюдённые статистики и перестановочный нуль (вторая база переназначается
    среди вторых баз того же дня запуска)."""
    n = len(pairs)
    res = {'n': n}
    if n < 3:
        return res
    # --- выход: все пары
    a_oe = [p['A']['oe_exit'] for p in pairs]
    b_oe = [p['B']['oe_exit'] for p in pairs]
    a_res = [p['A']['res_exit'] for p in pairs]
    b_res = [p['B']['res_exit'] for p in pairs]
    ra = midranks(a_oe)
    rb = midranks(b_oe)
    a_pr = [p['A']['pr_exit'] for p in pairs]
    b_pr = [p['B']['pr_exit'] for p in pairs]
    first_has_reg = [1 if p['A']['o_reg'] > 0 else 0 for p in pairs]
    b_oreg = [p['B']['o_reg'] for p in pairs]
    b_ereg = [p['B']['e_reg'] for p in pairs]
    b_oexit = [p['B']['o_exit'] for p in pairs]
    b_eexit = [p['B']['e_exit'] for p in pairs]

    groups = defaultdict(list)
    for i, p in enumerate(pairs):
        groups[p['B']['day']].append(i)
    groups = list(groups.values())
    res['n_singleton'] = sum(len(g) for g in groups if len(g) == 1)

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
            if first_has_reg[i]:
                o1 += b_oreg[j]; e1 += b_ereg[j]
            else:
                o0 += b_oreg[j]; e0 += b_ereg[j]
        return o1, e1, o0, e0

    def ratio_exit_from(sec):
        o1 = e1 = o0 = e0 = 0.0
        for i in range(n):
            j = sec[i]
            if first_has_reg[i]:
                o1 += b_oexit[j]; e1 += b_eexit[j]
            else:
                o0 += b_oexit[j]; e0 += b_eexit[j]
        return o1, e1, o0, e0

    ident = list(range(n))
    res['rho_exit'] = rho_from(ident)
    res['rho_pr_exit'] = rho_pr_from(ident)
    res['S_exit'] = S_from(ident)
    # кто дал регистрации во второй базе при первой с регистрацией
    res['contrib'] = sorted(
        [(p['B']['row']['домен'], p['B']['o_reg'], p['B']['e_reg'], p['A']['row']['домен'], p['A']['o_reg'])
         for p in pairs if p['A']['o_reg'] > 0 and p['B']['o_reg'] > 0],
        key=lambda t: -t[1])
    o1, e1, o0, e0 = ratio_from(ident)
    res['ratio_reg'] = (o1, e1, o0, e0)
    res['ratio_reg_val'] = (o1 / e1) / (o0 / e0) if e1 > 0 and e0 > 0 and o0 > 0 else float('nan')
    res['ratio_reg_exact'] = ratio_ci(o1, e1, o0, e0)
    res['n_first_reg'] = sum(first_has_reg)
    res['ratio_exit_given_reg'] = ratio_exit_from(ident)

    # --- регистрации: только пары, где у обеих баз E_reg > 0
    idx_reg = [i for i, p in enumerate(pairs) if p['A']['e_reg'] > 0 and p['B']['e_reg'] > 0]
    res['n_reg'] = len(idx_reg)
    if do_reg and len(idx_reg) >= 3:
        pr = [pairs[i] for i in idx_reg]
        m = len(pr)
        am = [p['A']['res_reg'] for p in pr]
        bm = [p['B']['res_reg'] for p in pr]
        ram = midranks(am)
        rbm = midranks(bm)
        ram_oe = midranks([p['A']['oe_reg'] for p in pr])
        rbm_oe = midranks([p['B']['oe_reg'] for p in pr])
        am_pr = [p['A']['pr_reg'] for p in pr]
        bm_pr = [p['B']['pr_reg'] for p in pr]
        groups_r = defaultdict(list)
        for i, p in enumerate(pr):
            groups_r[p['B']['day']].append(i)
        groups_r = list(groups_r.values())

        def rho_reg_from(sec):
            return pearson(ram, [rbm[sec[i]] for i in range(m)])

        def rho_reg_oe_from(sec):
            return pearson(ram_oe, [rbm_oe[sec[i]] for i in range(m)])

        def S_reg_from(sec):
            return sum(am[i] * bm[sec[i]] for i in range(m)) / m

        def rho_reg_pr_from(sec):
            return pearson(am_pr, [bm_pr[sec[i]] for i in range(m)])

        identm = list(range(m))
        res['rho_reg'] = rho_reg_from(identm)
        res['rho_reg_oe'] = rho_reg_oe_from(identm)
        res['rho_reg_pr'] = rho_reg_pr_from(identm)
        res['S_reg'] = S_reg_from(identm)
        res['sites_reg'] = sum(p['A']['sites'] + p['B']['sites'] for p in pr)
        res['regs_reg'] = sum(p['A']['o_reg'] + p['B']['o_reg'] for p in pr)
    else:
        do_reg = False

    # --- перестановки
    null = defaultdict(list)
    sec = list(range(n))
    secm = list(range(res['n_reg'])) if do_reg else None
    for _ in range(n_perm):
        for g in groups:
            sh = g[:]
            random.shuffle(sh)
            for k, i in enumerate(g):
                sec[i] = sh[k]
        null['rho_exit'].append(rho_from(sec))
        null['rho_pr_exit'].append(rho_pr_from(sec))
        null['S_exit'].append(S_from(sec))
        o1, e1, o0, e0 = ratio_from(sec)
        null['ratio_reg'].append((o1 / e1) / (o0 / e0) if e1 > 0 and e0 > 0 and o0 > 0 else float('nan'))
        if do_reg:
            for g in groups_r:
                sh = g[:]
                random.shuffle(sh)
                for k, i in enumerate(g):
                    secm[i] = sh[k]
            null['rho_reg'].append(rho_reg_from(secm))
            null['rho_reg_oe'].append(rho_reg_oe_from(secm))
            null['rho_reg_pr'].append(rho_reg_pr_from(secm))
            null['S_reg'].append(S_reg_from(secm))

    def summarize(name, centered=True, log=False):
        vals = [v for v in null[name] if not (isinstance(v, float) and math.isnan(v))]
        obs = res.get(name if name != 'ratio_reg' else 'ratio_reg_val')
        if not vals or obs is None or (isinstance(obs, float) and math.isnan(obs)):
            res[name + '_p'] = float('nan')
            res[name + '_ci'] = (float('nan'), float('nan'))
            return
        vs = sorted(vals)
        lo = vs[int(0.025 * len(vs))]
        hi = vs[min(len(vs) - 1, int(0.975 * len(vs)))]
        if log:
            lv = [math.log(v) for v in vals if v > 0]
            centre = sum(lv) / len(lv) if lv else 0.0
            d_obs = abs(math.log(obs) - centre) if obs > 0 else float('inf')
            cnt = sum(1 for v in vals if (abs(math.log(v) - centre) if v > 0 else float('inf')) >= d_obs - 1e-12)
        else:
            centre = sum(vals) / len(vals) if centered else 0.0
            d_obs = abs(obs - centre)
            cnt = sum(1 for v in vals if abs(v - centre) >= d_obs - 1e-12)
        res[name + '_p'] = (cnt + 1) / (len(vals) + 1)
        res[name + '_ci'] = (lo, hi)
        res[name + '_null_mean'] = centre if not log else math.exp(centre)

    summarize('rho_exit')
    summarize('rho_pr_exit')
    summarize('S_exit')
    summarize('ratio_reg', log=True)
    if do_reg:
        summarize('rho_reg')
        summarize('rho_reg_oe')
        summarize('rho_reg_pr')
        summarize('S_reg')
    res['sites'] = sum(p['A']['sites'] + p['B']['sites'] for p in pairs)
    res['regs'] = sum(p['A']['o_reg'] + p['B']['o_reg'] for p in pairs)
    res['exits'] = sum(p['A']['o_exit'] + p['B']['o_exit'] for p in pairs)
    return res


def print_stats(title, st):
    P(f'--- {title}')
    if st.get('n', 0) < 3:
        P(f'   пар: {st.get("n", 0)} — слишком мало для оценки')
        return
    P(f'   пар: {st["n"]}, сайтов в парах: {st["sites"]}, вышедших сайтов: {st["exits"]}, регистраций в окне: {st["regs"]}'
      f' (пар, чья вторая база одна в своём дне и не перемешивается: {st["n_singleton"]})')
    P(f'   ВЫХОД:  ρ Спирмена по O/E = {f2(st["rho_exit"], 3)}  (p = {f2(st["rho_exit_p"], 3)}; нуль: среднее {f2(st["rho_exit_null_mean"], 3)}, 95%: {f2(st["rho_exit_ci"][0], 3)}..{f2(st["rho_exit_ci"][1], 3)})')
    P(f'           ρ по рангам внутри пула = {f2(st["rho_pr_exit"], 3)}  (p = {f2(st["rho_pr_exit_p"], 3)}; нуль: среднее {f2(st["rho_pr_exit_null_mean"], 3)}, 95%: {f2(st["rho_pr_exit_ci"][0], 3)}..{f2(st["rho_pr_exit_ci"][1], 3)})')
    P(f'           S = среднее e_A·e_B = {f2(st["S_exit"], 3)}  (p = {f2(st["S_exit_p"], 3)}; нуль: среднее {f2(st["S_exit_null_mean"], 3)}, 95%: {f2(st["S_exit_ci"][0], 3)}..{f2(st["S_exit_ci"][1], 3)})')
    if 'rho_reg' in st:
        P(f'   РЕГИСТРАЦИИ (пары, где у обеих баз пул с регистрациями: {st["n_reg"]} пар, {st["sites_reg"]} сайтов, {st["regs_reg"]} рег.):')
        P(f'           ρ Спирмена по остаткам m = {f2(st["rho_reg"], 3)}  (p = {f2(st["rho_reg_p"], 3)}; нуль: среднее {f2(st["rho_reg_null_mean"], 3)}, 95%: {f2(st["rho_reg_ci"][0], 3)}..{f2(st["rho_reg_ci"][1], 3)})')
        P(f'           ρ Спирмена по O/E = {f2(st["rho_reg_oe"], 3)}  (p = {f2(st["rho_reg_oe_p"], 3)}; нуль: среднее {f2(st["rho_reg_oe_null_mean"], 3)})')
        P(f'           ρ по рангам внутри пула = {f2(st["rho_reg_pr"], 3)}  (p = {f2(st["rho_reg_pr_p"], 3)}; нуль: среднее {f2(st["rho_reg_pr_null_mean"], 3)}, 95%: {f2(st["rho_reg_pr_ci"][0], 3)}..{f2(st["rho_reg_pr_ci"][1], 3)})')
        P(f'           S = среднее m_A·m_B = {f2(st["S_reg"], 3)}  (p = {f2(st["S_reg_p"], 3)}; нуль: среднее {f2(st["S_reg_null_mean"], 3)}, 95%: {f2(st["S_reg_ci"][0], 3)}..{f2(st["S_reg_ci"][1], 3)})')
    else:
        P(f'   РЕГИСТРАЦИИ: пар с E_reg > 0 у обеих баз: {st.get("n_reg", 0)} — слишком мало для ρ и S')
    o1, e1, o0, e0 = st['ratio_reg']
    r, lo, hi, pb = st['ratio_reg_exact']
    P(f'   2×2 по регистрациям второй базы: первая С регистрацией ({st["n_first_reg"]} пар): O = {o1:.0f}, E = {f2(e1)}, O/E = {f2(oe(o1, e1))};'
      f'  первая БЕЗ ({st["n"] - st["n_first_reg"]} пар): O = {o0:.0f}, E = {f2(e0)}, O/E = {f2(oe(o0, e0))}')
    P(f'           отношение = {f2(r)}  (точный интервал 95%: {f2(lo)}..{f2(hi)}, биномиальное p = {f2(pb, 3)}; '
      f'перестановочное p = {f2(st["ratio_reg_p"], 3)}, нуль 95%: {f2(st["ratio_reg_ci"][0])}..{f2(st["ratio_reg_ci"][1])})')
    x1, y1, x0, y0 = st['ratio_exit_given_reg']
    P(f'   выход второй базы при первой с регистрацией: O/E = {f2(oe(x1, y1))} ({x1:.0f}/{f2(y1, 1)}); без: {f2(oe(x0, y0))} ({x0:.0f}/{f2(y0, 1)})')
    if st['contrib']:
        P(f'   из чего сложились {o1:.0f} регистраций второй базы при первой с регистрацией (вторая: рег / ожид.; первая: рег):')
        for dom, o, e, dom_a, oa in st['contrib'][:8]:
            P(f'      {dom:22s} {o:.0f} / {f2(e)}   ← {dom_a:22s} {oa:.0f}')
        if len(st['contrib']) > 8:
            P(f'      ... и ещё {len(st["contrib"]) - 8} пар')


def tercile_table(pairs, title):
    """Вторая база по третям остатка первой (выход) — сырой, но наглядный вид."""
    if len(pairs) < 9:
        return
    P(f'--- {title}: вторая база по третям остатка e первой (выход)')
    srt = sorted(pairs, key=lambda p: p['A']['res_exit'])
    k = len(srt) // 3
    parts = [('нижняя треть (первая провалилась)', srt[:k]),
             ('средняя треть', srt[k:2 * k]),
             ('верхняя треть (первая удалась)', srt[2 * k:])]
    P(f'   {"треть по первой базе":38s} {"пар":>4s} {"e_A средн.":>10s} {"сайтов B":>9s} {"вышло B O/E":>12s} {"рег B O":>7s} {"рег B E":>8s} {"рег B O/E":>9s}')
    for name, ps in parts:
        n = len(ps)
        ea = sum(p['A']['res_exit'] for p in ps) / n
        sb = sum(p['B']['sites'] for p in ps)
        ox = sum(p['B']['o_exit'] for p in ps)
        ex = sum(p['B']['e_exit'] for p in ps)
        orr = sum(p['B']['o_reg'] for p in ps)
        er = sum(p['B']['e_reg'] for p in ps)
        P(f'   {name:38s} {n:4d} {ea:10.2f} {sb:9d} {oe(ox, ex):12.3f} {orr:7.0f} {er:8.2f} {f2(oe(orr, er)):>9s}')


def raw_exit_split(pairs, title, thr=0.15):
    """Сырая прикидка: выход второй базы при выходе первой >= 15% и < 15%."""
    hi = [p for p in pairs if p['A']['o_exit'] / p['A']['sites'] >= thr]
    lo = [p for p in pairs if p['A']['o_exit'] / p['A']['sites'] < thr]

    def summ(ps):
        s = sum(p['B']['sites'] for p in ps)
        o = sum(p['B']['o_exit'] for p in ps)
        e = sum(p['B']['e_exit'] for p in ps)
        return len(ps), s, o, e
    n1, s1, o1, e1 = summ(hi)
    n0, s0, o0, e0 = summ(lo)
    P(f'--- {title}: выход второй при выходе первой >= {thr:.0%} / < {thr:.0%}')
    P(f'   первая >= {thr:.0%}: {n1} пар, сырой выход второй {f2(100 * o1 / s1 if s1 else float("nan"), 1)}%, O/E внутри пулов {f2(oe(o1, e1), 3)}')
    P(f'   первая <  {thr:.0%}: {n0} пар, сырой выход второй {f2(100 * o0 / s0 if s0 else float("nan"), 1)}%, O/E внутри пулов {f2(oe(o0, e0), 3)}')


def zero_contagion(universe, acc_field, title, n_perm=N_PERM):
    """Сиблинги баз с нулём выходов: сумма O против суммы E; биномиальный тест
    при объединённой доле и перестановка (сиблинг заменяется случайной базой того же дня)."""
    by_acc = defaultdict(list)
    for d, u in universe.items():
        a = u['row'][acc_field].strip()
        if a:
            by_acc[a].append(u)
    zero_bases = [u for u in universe.values() if u['o_exit'] == 0]
    sibs = {}
    n_zero_with_sib = 0
    for z in zero_bases:
        a = z['row'][acc_field].strip()
        if not a:
            continue
        others = [u for u in by_acc[a] if u['row']['домен'] != z['row']['домен']]
        if others:
            n_zero_with_sib += 1
        for o in others:
            sibs[o['row']['домен']] = o
    sibs = list(sibs.values())
    P(f'--- {title}: заразность нулей')
    P(f'   баз с нулём выходов за 3 суток в пулах: {len(zero_bases)}, из них с сиблингом по аккаунту: {n_zero_with_sib}; уникальных сиблингов: {len(sibs)}')
    if not sibs:
        return None
    S = sum(u['sites'] for u in sibs)
    O = sum(u['o_exit'] for u in sibs)
    E = sum(u['e_exit'] for u in sibs)
    Or = sum(u['o_reg'] for u in sibs)
    Er = sum(u['e_reg'] for u in sibs)
    n_zero_sib = sum(1 for u in sibs if u['o_exit'] == 0)
    p_bin = binom_test_two_sided(int(O), S, E / S) if S else float('nan')
    # перестановка: каждый сиблинг заменяется случайной базой того же дня из вселенной
    by_day = defaultdict(list)
    for u in universe.values():
        by_day[u['day']].append(u)
    null_oe = []
    null_oe_reg = []
    null_zero = []
    for _ in range(n_perm):
        o = e = 0.0
        orr = er = 0.0
        nz = 0
        for u in sibs:
            v = random.choice(by_day[u['day']])
            o += v['o_exit']; e += v['e_exit']
            orr += v['o_reg']; er += v['e_reg']
            nz += 1 if v['o_exit'] == 0 else 0
        null_oe.append(o / e if e > 0 else float('nan'))
        null_oe_reg.append(orr / er if er > 0 else float('nan'))
        null_zero.append(nz)
    obs_oe = oe(O, E)
    vs = sorted(v for v in null_oe if not math.isnan(v))
    centre = sum(vs) / len(vs)
    p_perm = (sum(1 for v in vs if abs(v - centre) >= abs(obs_oe - centre) - 1e-12) + 1) / (len(vs) + 1)
    lo, hi = vs[int(0.025 * len(vs))], vs[min(len(vs) - 1, int(0.975 * len(vs)))]
    obs_oer = oe(Or, Er)
    vr = sorted(v for v in null_oe_reg if not math.isnan(v))
    if vr and not math.isnan(obs_oer):
        cr = sum(vr) / len(vr)
        p_perm_r = (sum(1 for v in vr if abs(v - cr) >= abs(obs_oer - cr) - 1e-12) + 1) / (len(vr) + 1)
        lor, hir = vr[int(0.025 * len(vr))], vr[min(len(vr) - 1, int(0.975 * len(vr)))]
    else:
        p_perm_r, lor, hir = float('nan'), float('nan'), float('nan')
    nz_mean = sum(null_zero) / len(null_zero)
    p_zero = (sum(1 for v in null_zero if v >= n_zero_sib) + 1) / (len(null_zero) + 1)
    P(f'   сиблинги: {len(sibs)} баз, {S} сайтов; вышло O = {O:.0f}, ожидание по пулам E = {f2(E, 1)}, O/E = {f2(obs_oe, 3)}')
    P(f'   биномиальный тест (объединённая доля {f2(100 * E / S, 2)}%): p = {f2(p_bin, 3)}; перестановочное p = {f2(p_perm, 3)}, нуль 95%: {f2(lo, 3)}..{f2(hi, 3)}')
    P(f'   (биномиальный тест считает сайты независимыми и не учитывает известный разброс доменов внутри пула — он занижает p; опираться на перестановочное)')
    P(f'   у сиблингов тоже нуль выходов: {n_zero_sib} баз (в нуле ожидалось {f2(nz_mean, 1)}; p(>=) = {f2(p_zero, 3)})')
    P(f'   регистрации у сиблингов: O = {Or:.0f}, E = {f2(Er, 2)}, O/E = {f2(obs_oer, 2)} (перестановочное p = {f2(p_perm_r, 3)}, нуль 95%: {f2(lor, 2)}..{f2(hir, 2)})')
    return {'n_sibs': len(sibs), 'sites': S, 'O': O, 'E': E, 'oe': obs_oe, 'p_bin': p_bin, 'p_perm': p_perm,
            'oe_reg': obs_oer, 'n_zero': len(zero_bases), 'n_zero_sib': n_zero_sib}


# ----------------------------------------------------------------------------
# ОСНОВНОЙ ПРОГОН
# ----------------------------------------------------------------------------

UNI, n_pools, n_dropped, n_coarse = build_universe(KEPT)
P()
P('=' * 100)
P('ОСНОВНОЙ ПРОГОН: пулы «набор контента + день», >= 3 баз в пуле')
P('=' * 100)
P(f'Огрубление: у {n_coarse} доменов запусков с {SUFFIX_FROM_DAY} имя набора с суффиксом _NN (по одному на домен) — '
  f'пул = корень имени + день.')
P(f'Пулов с >= {MIN_POOL} базами: {n_pools}; доменов в них: {len(UNI)}; отброшено доменов в мелких пулах: {n_dropped}')
P(f'Сайтов во вселенной: {sum(u["sites"] for u in UNI.values())}, вышло за 3 суток: {sum(u["o_exit"] for u in UNI.values())}, '
  f'регистраций в окне: {sum(u["o_reg"] for u in UNI.values())}')
n_e0 = sum(1 for u in UNI.values() if u['e_reg'] == 0)
P(f'Доменов в пулах без единой регистрации (E_reg = 0, в статистиках по регистрациям не участвуют): {n_e0}')

RESULTS = {}

for acc_field, acc_name in [('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')]:
    P()
    P('=' * 100)
    P(f'{acc_name} (поле «{acc_field}»)')
    P('=' * 100)
    pairs, n_acc = build_pairs(UNI, acc_field)
    labels = Counter(p['label'] for p in pairs)
    gaps = Counter(p['gap'] for p in pairs)
    P(f'Аккаунтов с >= 2 пригодными базами: {n_acc}; пар соседних по дате: {len(pairs)}')
    P(f'Пары по порядковым номерам внутри аккаунта: ' + ', '.join(f'{k}: {v}' for k, v in sorted(labels.items())))
    gap_bins = Counter()
    for g, c in gaps.items():
        b = '0–3 дня' if g <= 3 else ('4–13 дней' if g <= 13 else ('14–28 дней' if g <= 28 else '> 28 дней'))
        gap_bins[b] += c
    P(f'Разрыв между запусками в паре: ' + ', '.join(f'{k}: {v}' for k, v in sorted(gap_bins.items())))
    same_zone = sum(1 for p in pairs if p['A']['zone'] == p['B']['zone'])
    P(f'Пар в одной зоне: {same_zone}, в разных зонах: {len(pairs) - same_zone}')
    if acc_field == 'аккаунт вебмастера':
        mism = sum(1 for p in pairs if str(p['label'].split('→')[1]) != p['B']['row']['который раз аккаунт'])
        P(f'Сверка порядкового номера с полем «который раз аккаунт» у второй базы: расхождений {mism} из {len(pairs)}')

    P()
    st = pair_stats(pairs)
    print_stats(f'{acc_name}: все пары', st)
    RESULTS[(acc_field, 'all')] = st
    P()
    raw_exit_split(pairs, acc_name)
    P()
    tercile_table(pairs, acc_name)

    # разрезы
    P()
    P(f'--- {acc_name}: разрез по зоне второй базы (перестановка внутри дня и зоны)')
    for z in ZONES:
        sub = [p for p in pairs if p['B']['zone'] == z]
        if len(sub) < 10:
            P(f'   зона {z}: {len(sub)} пар — мало, пропуск')
            continue
        s = pair_stats(sub, n_perm=N_PERM)
        RESULTS[(acc_field, 'zone_' + z)] = s
        o1, e1, o0, e0 = s['ratio_reg']
        r, lo, hi, pb = s['ratio_reg_exact']
        P(f'   зона {z:6s}: {s["n"]:4d} пар, {s["sites"]:6d} сайтов, {s["regs"]:3d} рег.; ρ выход {f2(s["rho_exit"], 3)} (p {f2(s["rho_exit_p"], 3)}), '
          f'S выход {f2(s["S_exit"], 3)} (p {f2(s["S_exit_p"], 3)}); '
          + (f'ρ рег {f2(s["rho_reg"], 3)} (p {f2(s["rho_reg_p"], 3)}), S рег {f2(s["S_reg"], 3)} (p {f2(s["S_reg_p"], 3)}) на {s["n_reg"]} парах; ' if 'rho_reg' in s else 'ρ/S рег: мало пар; ')
          + f'отношение по рег {f2(r)} ({f2(lo)}..{f2(hi)}; O {o1:.0f}/{o0:.0f})')

    P()
    P(f'--- {acc_name}: разрез по порядковому номеру пары')
    for lab in ['1→2', '2→3']:
        sub = [p for p in pairs if p['label'] == lab]
        if len(sub) < 10:
            P(f'   пары {lab}: {len(sub)} — мало, пропуск')
            continue
        s = pair_stats(sub, n_perm=N_PERM)
        RESULTS[(acc_field, 'ord_' + lab)] = s
        o1, e1, o0, e0 = s['ratio_reg']
        r, lo, hi, pb = s['ratio_reg_exact']
        P(f'   пары {lab}: {s["n"]:4d} пар, {s["sites"]:6d} сайтов, {s["regs"]:3d} рег.; ρ выход {f2(s["rho_exit"], 3)} (p {f2(s["rho_exit_p"], 3)}), '
          f'S выход {f2(s["S_exit"], 3)} (p {f2(s["S_exit_p"], 3)}); '
          + (f'ρ рег {f2(s["rho_reg"], 3)} (p {f2(s["rho_reg_p"], 3)}), S рег {f2(s["S_reg"], 3)} (p {f2(s["S_reg_p"], 3)}) на {s["n_reg"]} парах; ' if 'rho_reg' in s else 'ρ/S рег: мало пар; ')
          + f'отношение по рег {f2(r)} ({f2(lo)}..{f2(hi)}; O {o1:.0f}/{o0:.0f})')
    other = [p for p in pairs if p['label'] not in ('1→2', '2→3')]
    if other:
        P(f'   прочие пары (через отсеянную базу и т.п.): {len(other)} — в разрез не входят, в общем счёте есть')

    if acc_field == 'аккаунт вебмастера':
        P()
        P(f'--- {acc_name}: разрез по разрыву между запусками (окно первой закрыто до второго запуска = разрыв >= 4 дней)')
        for name, cond in [('разрыв >= 4 дней', lambda p: p['gap'] >= 4), ('разрыв <= 3 дней', lambda p: p['gap'] <= 3)]:
            sub = [p for p in pairs if cond(p)]
            if len(sub) < 10:
                P(f'   {name}: {len(sub)} пар — мало, пропуск')
                continue
            s = pair_stats(sub, n_perm=N_PERM)
            RESULTS[(acc_field, 'gap_' + name)] = s
            o1, e1, o0, e0 = s['ratio_reg']
            r, lo, hi, pb = s['ratio_reg_exact']
            P(f'   {name}: {s["n"]:4d} пар, {s["sites"]:6d} сайтов, {s["regs"]:3d} рег.; ρ выход {f2(s["rho_exit"], 3)} (p {f2(s["rho_exit_p"], 3)}), '
              f'S выход {f2(s["S_exit"], 3)} (p {f2(s["S_exit_p"], 3)}); '
              + (f'ρ рег {f2(s["rho_reg"], 3)} (p {f2(s["rho_reg_p"], 3)}), S рег {f2(s["S_reg"], 3)} (p {f2(s["S_reg_p"], 3)}) на {s["n_reg"]} парах; ' if 'rho_reg' in s else 'ρ/S рег: мало пар; ')
              + f'отношение по рег {f2(r)} ({f2(lo)}..{f2(hi)}; O {o1:.0f}/{o0:.0f})')
    else:
        P()
        P(f'--- {acc_name}: разрез по совпадению зоны сиблингов')
        for name, cond in [('одна зона', lambda p: p['A']['zone'] == p['B']['zone']), ('разные зоны', lambda p: p['A']['zone'] != p['B']['zone'])]:
            sub = [p for p in pairs if cond(p)]
            if len(sub) < 10:
                P(f'   {name}: {len(sub)} пар — мало, пропуск')
                continue
            s = pair_stats(sub, n_perm=N_PERM)
            RESULTS[(acc_field, 'samezone_' + name)] = s
            o1, e1, o0, e0 = s['ratio_reg']
            r, lo, hi, pb = s['ratio_reg_exact']
            P(f'   {name}: {s["n"]:4d} пар, {s["sites"]:6d} сайтов, {s["regs"]:3d} рег.; ρ выход {f2(s["rho_exit"], 3)} (p {f2(s["rho_exit_p"], 3)}), '
              f'S выход {f2(s["S_exit"], 3)} (p {f2(s["S_exit_p"], 3)}); '
              + (f'ρ рег {f2(s["rho_reg"], 3)} (p {f2(s["rho_reg_p"], 3)}), S рег {f2(s["S_reg"], 3)} (p {f2(s["S_reg_p"], 3)}) на {s["n_reg"]} парах; ' if 'rho_reg' in s else 'ρ/S рег: мало пар; ')
              + f'отношение по рег {f2(r)} ({f2(lo)}..{f2(hi)}; O {o1:.0f}/{o0:.0f})')

    P()
    zc = zero_contagion(UNI, acc_field, acc_name)
    RESULTS[(acc_field, 'zero')] = zc

# ----------------------------------------------------------------------------
# ПРОГОН «С АВГУСТОМ»: базы без записанного набора со стратой «только день»
# ----------------------------------------------------------------------------

P()
P('=' * 100)
P(f'ПРОГОН «С АВГУСТОМ»: базы «{NO_CONTENT}» включены со стратой «только день запуска»')
P('=' * 100)
P('Оговорка: для этих баз набор не записан и полностью сцеплен с датой, поэтому пул = день; это грубее,')
P('чем «набор + день», и остатки у августовских баз шире (внутри дня смешаны разные наборы). Прогон нужен,')
P('чтобы захватить августовские первые базы аккаунтов; выводы по нему — вспомогательные.')
UNI_EXT, n_pools_e, n_dropped_e, _ = build_universe(KEPT_EXT, ext=True)
n_noc_in = sum(1 for u in UNI_EXT.values() if u['row']['набор контента'] == NO_CONTENT)
P(f'Пулов с >= {MIN_POOL} базами: {n_pools_e}; доменов: {len(UNI_EXT)} (из них без записанного набора: {n_noc_in}); отброшено: {n_dropped_e}')
for acc_field, acc_name in [('cf-аккаунт', 'CF-АККАУНТ'), ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')]:
    P()
    pairs_e, n_acc_e = build_pairs(UNI_EXT, acc_field)
    n_aug = sum(1 for p in pairs_e if p['A']['row']['набор контента'] == NO_CONTENT)
    P(f'{acc_name}: аккаунтов с >= 2 пригодными базами: {n_acc_e}; пар: {len(pairs_e)} (в {n_aug} парах первая база — без записанного набора, страта «день»)')
    st_e = pair_stats(pairs_e)
    print_stats(f'{acc_name} (с августом): все пары', st_e)
    RESULTS[(acc_field, 'ext')] = st_e
    sub = [p for p in pairs_e if p['A']['row']['набор контента'] == NO_CONTENT]
    if len(sub) >= 10:
        s = pair_stats(sub)
        RESULTS[(acc_field, 'ext_aug')] = s
        P()
        print_stats(f'{acc_name} (с августом): только пары, где первая база августовская без набора', s)
    P()
    zero_contagion(UNI_EXT, acc_field, acc_name + ' (с августом)')

# ----------------------------------------------------------------------------
# ИТОГ ПО КРИТЕРИЯМ
# ----------------------------------------------------------------------------

P()
P('=' * 100)
P('ИТОГ ПО КРИТЕРИЯМ')
P('=' * 100)
P('Заявленные критерии: «не делят» — |ρ| < 0,1, S внутри перестановочного нуля, отношение по регистрациям 0,8–1,25,')
P('сиблинги нулей O/E 0,9–1,1; «связь» — ρ >= 0,15 при p < 0,05 или отношение >= 1,5 / <= 0,67.')
P('ρ сравнивается со средним перестановочного нуля (оно не равно нулю, потому что пары связывают конкретные дни).')


def verdict_block(acc_field, acc_name):
    st = RESULTS[(acc_field, 'all')]
    zc = RESULTS[(acc_field, 'zero')]
    ext = RESULTS[(acc_field, 'ext')]
    rho_e = st['rho_exit'] - st['rho_exit_null_mean']
    rho_r = (st['rho_reg'] - st['rho_reg_null_mean']) if 'rho_reg' in st else float('nan')
    S_e_in = st['S_exit_ci'][0] <= st['S_exit'] <= st['S_exit_ci'][1]
    S_r_in = ('S_reg' in st) and (st['S_reg_ci'][0] <= st['S_reg'] <= st['S_reg_ci'][1])
    r, lo, hi, pb = st['ratio_reg_exact']
    r_ext = ext['ratio_reg_exact'] if ext.get('n', 0) >= 3 else (float('nan'),) * 4
    zoe = zc['oe'] if zc else float('nan')
    ok_rho = abs(rho_e) < 0.1 and abs(rho_r) < 0.1
    ok_S = S_e_in and S_r_in
    ok_ratio = 0.8 <= r <= 1.25
    ok_zero = 0.9 <= zoe <= 1.1
    link_rho = (abs(rho_e) >= 0.15 and st['rho_exit_p'] < 0.05) or (abs(rho_r) >= 0.15 and st['rho_reg_p'] < 0.05)
    link_ratio_formal = (r >= 1.5 or r <= 0.67)
    link_ratio_sig = link_ratio_formal and (lo > 1 or hi < 1)
    P()
    P(f'{acc_name}: пар {st["n"]}, сайтов {st["sites"]}, регистраций в окне {st["regs"]} (у вторых баз: {st["ratio_reg"][0] + st["ratio_reg"][2]:.0f})')
    P(f'   |ρ − нуль| < 0,1:  выход {f2(rho_e, 3)} ({"да" if abs(rho_e) < 0.1 else "НЕТ"}), регистрации {f2(rho_r, 3)} ({"да" if abs(rho_r) < 0.1 else "НЕТ"})'
      f'  [сырые ρ: {f2(st["rho_exit"], 3)} / {f2(st.get("rho_reg", float("nan")), 3)}; по рангам внутри пула: {f2(st["rho_pr_exit"], 3)} / {f2(st.get("rho_reg_pr", float("nan")), 3)}]')
    P(f'   S внутри перестановочного нуля: выход {"да" if S_e_in else "НЕТ"} ({f2(st["S_exit"], 3)} в {f2(st["S_exit_ci"][0], 3)}..{f2(st["S_exit_ci"][1], 3)}), '
      f'регистрации {"да" if S_r_in else "НЕТ"}' + (f' ({f2(st["S_reg"], 3)} в {f2(st["S_reg_ci"][0], 3)}..{f2(st["S_reg_ci"][1], 3)})' if 'S_reg' in st else ''))
    P(f'   отношение по регистрациям 0,8–1,25: {f2(r)} ({"да" if ok_ratio else "НЕТ"}); точный интервал {f2(lo)}..{f2(hi)}, биномиальное p = {f2(pb, 3)}, перестановочное p = {f2(st["ratio_reg_p"], 3)}')
    P(f'      то же в прогоне с августом ({ext.get("n", 0)} пар): {f2(r_ext[0])} ({f2(r_ext[1])}..{f2(r_ext[2])})')
    P(f'   сиблинги нулей O/E 0,9–1,1: {f2(zoe, 3)} ({"да" if ok_zero else "НЕТ"}; {zc["n_sibs"] if zc else 0} сиблингов, перестановочное p = {f2(zc["p_perm"] if zc else float("nan"), 3)})')
    P(f'   «не делят» по всем четырём пунктам: {"да" if (ok_rho and ok_S and ok_ratio and ok_zero) else "нет"} '
      f'(ρ: {"да" if ok_rho else "нет"}, S: {"да" if ok_S else "нет"}, отношение: {"да" if ok_ratio else "нет"}, нули: {"да" if ok_zero else "нет"})')
    P(f'   «связь» по ρ (>= 0,15 при p < 0,05): {"ДА" if link_rho else "нет"}; по отношению (>= 1,5 / <= 0,67): формальный порог {"пройден" if link_ratio_formal else "не пройден"}, '
      f'интервал {"исключает" if link_ratio_sig else "включает"} 1 → {"ДА" if link_ratio_sig else "не подтверждается"}')
    return {'ok_rho': ok_rho, 'ok_S': ok_S, 'ok_ratio': ok_ratio, 'ok_zero': ok_zero,
            'link_rho': link_rho, 'link_ratio_formal': link_ratio_formal, 'link_ratio_sig': link_ratio_sig,
            'ratio': r, 'lo': lo, 'hi': hi, 'ratio_ext': r_ext}


V_CF = verdict_block('cf-аккаунт', 'CF-АККАУНТ')
V_WM = verdict_block('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА')

P()
P('Разрезы и множественные сравнения (правило: много срезов — много сравнений):')
cut_keys = [k for k in RESULTS if k[1].startswith(('zone_', 'ord_', 'gap_', 'samezone_')) and RESULTS[k].get('n', 0) >= 10]
n_tests = 0
min_p = (1.0, '')
excl = []
for k in cut_keys:
    s_ = RESULTS[k]
    for name in ('rho_exit_p', 'S_exit_p', 'rho_reg_p', 'S_reg_p', 'ratio_reg_p'):
        if name in s_ and not math.isnan(s_[name]):
            n_tests += 1
            if s_[name] < min_p[0]:
                min_p = (s_[name], f'{k[0]} / {k[1]} / {name}')
    r_, lo_, hi_, pb_ = s_['ratio_reg_exact']
    if not math.isnan(r_) and (lo_ > 1 or hi_ < 1):
        excl.append(f'{k[0]} / {k[1]}: отношение {f2(r_)} ({f2(lo_)}..{f2(hi_)}; O {s_["ratio_reg"][0]:.0f}/{s_["ratio_reg"][2]:.0f})')
P(f'   разрезов: {len(cut_keys)}, перестановочных p в них: {n_tests}; наименьшее p = {f2(min_p[0], 3)} ({min_p[1]}); '
  f'при {n_tests} независимых проверках наименьшее p в нуле ожидается около {f2(1 / (n_tests + 1), 3)}')
if excl:
    P('   разрезы, где точный интервал отношения по регистрациям не накрывает 1:')
    for e in excl:
        P(f'      {e}')
    P('   это разрезы с единицами регистраций; при таком числе сравнений один интервал без единицы ожидаем и сам по себе доводом не является.')
else:
    P('   ни в одном разрезе точный интервал отношения по регистрациям не исключает 1.')

# ----------------------------------------------------------------------------
# ВЫВОД
# ----------------------------------------------------------------------------

P()
P('=' * 100)
P('ВЫВОД')
P('=' * 100)
cf = RESULTS[('cf-аккаунт', 'all')]
wm = RESULTS[('аккаунт вебмастера', 'all')]
cfz = RESULTS[('cf-аккаунт', 'zero')]
wmz = RESULTS[('аккаунт вебмастера', 'zero')]
cfe = RESULTS[('cf-аккаунт', 'ext')]
wme = RESULTS[('аккаунт вебмастера', 'ext')]


def describe(num, acc_name, st, zc, ext, V):
    o1, e1, o0, e0 = st['ratio_reg']
    r, lo, hi, pb = st['ratio_reg_exact']
    P(f'{num}. {acc_name}. Пар соседних баз одного аккаунта: {st["n"]} ({st["sites"]} сайтов, {st["regs"]} регистраций в окне 3 суток).')
    P(f'   Выход в поиск: удача или провал первой базы не передаются второй. ρ = {f2(st["rho_exit"], 3)} (p = {f2(st["rho_exit_p"], 3)}), '
      f'S = {f2(st["S_exit"], 3)} при нуле {f2(st["S_exit_ci"][0], 3)}..{f2(st["S_exit_ci"][1], 3)}; по рангам внутри пула ρ = {f2(st["rho_pr_exit"], 3)}.')
    if 'rho_reg' in st:
        P(f'   Регистрации: ρ = {f2(st["rho_reg"], 3)} при среднем нуля {f2(st["rho_reg_null_mean"], 3)} (p = {f2(st["rho_reg_p"], 3)}), '
          f'S = {f2(st["S_reg"], 3)} при нуле {f2(st["S_reg_ci"][0], 3)}..{f2(st["S_reg_ci"][1], 3)} ({st["n_reg"]} пар в пулах с регистрациями).')
    P(f'   Если у первой базы была регистрация ({st["n_first_reg"]} пар), вторая дала {o1:.0f} регистраций против ожидаемых {f2(e1, 1)} по её пулу (O/E {f2(oe(o1, e1))}); '
      f'если не было ({st["n"] - st["n_first_reg"]} пар) — {o0:.0f} против {f2(e0, 1)} (O/E {f2(oe(o0, e0))}).')
    P(f'   Отношение {f2(r)}, точный интервал {f2(lo)}..{f2(hi)} (биномиальное p = {f2(pb, 3)}, перестановочное p = {f2(st["ratio_reg_p"], 3)}); '
      f'в прогоне с августом ({ext.get("n", 0)} пар) — {f2(V["ratio_ext"][0])} ({f2(V["ratio_ext"][1])}..{f2(V["ratio_ext"][2])}).')
    if st['contrib'] and o1 > 0:
        top2 = sum(t[1] for t in st['contrib'][:2])
        P(f'   Из этих {o1:.0f} регистраций {top2:.0f} дали два домена ({", ".join(f"{t[0]} {t[1]:.0f} при ожидании {f2(t[2])}" for t in st["contrib"][:2])}).')
    if zc:
        P(f'   Сиблинги «нулевых» баз ({zc["n_sibs"]} баз, {zc["sites"]} сайтов): вышло {zc["O"]:.0f} против ожидаемых {f2(zc["E"], 1)}, O/E = {f2(zc["oe"], 3)} '
          f'(перестановочное p = {f2(zc["p_perm"], 3)}); регистрации O/E = {f2(zc["oe_reg"], 2)}.')


describe(1, 'CF-аккаунт', cf, cfz, cfe, V_CF)
describe(2, 'Аккаунт Вебмастера', wm, wmz, wme, V_WM)

any_link = V_CF['link_rho'] or V_WM['link_rho'] or V_CF['link_ratio_sig'] or V_WM['link_ratio_sig']
exit_clean = V_CF['ok_S'] and V_WM['ok_S'] and abs(cf['rho_exit'] - cf['rho_exit_null_mean']) < 0.1 and abs(wm['rho_exit'] - wm['rho_exit_null_mean']) < 0.1
P()
P('3. Итог.')
P(f'   По выходу в поиск гипотеза {"подтверждена" if exit_clean else "НЕ подтверждена"}: ни у cf-аккаунта, ни у аккаунта Вебмастера сиблинги не тянут друг друга '
  f'(ρ {f2(cf["rho_exit"], 3)} и {f2(wm["rho_exit"], 3)}, S внутри нуля, сиблинги нулей O/E {f2(cfz["oe"], 2)} и {f2(wmz["oe"], 2)}).')
if not any_link:
    P('   По регистрациям связи не найдено: ρ и S у нуля у обоих аккаунтов, а отношение «вторая после регистрационной первой / после пустой»')
    P(f'   cf {f2(V_CF["ratio"])} ({f2(V_CF["lo"])}..{f2(V_CF["hi"])}), Вебмастер {f2(V_WM["ratio"])} ({f2(V_WM["lo"])}..{f2(V_WM["hi"])}) — оба интервала накрывают 1,')
    P(f'   а в прогоне с августом отношения {f2(V_CF["ratio_ext"][0])} и {f2(V_WM["ratio_ext"][0])}.')
    tight = V_CF['ok_ratio'] and V_WM['ok_ratio']
    if tight:
        P('   Коридор 0,8–1,25 по отношению выдержан у обоих аккаунтов — гипотеза подтверждена и по регистрациям.')
    else:
        P('   Но коридор 0,8–1,25 по отношению на этом объёме не выдерживается: регистраций у вторых баз слишком мало'
          f' ({cf["ratio_reg"][0] + cf["ratio_reg"][2]:.0f} у cf, {wm["ratio_reg"][0] + wm["ratio_reg"][2]:.0f} у Вебмастера), точечные оценки прыгают в обе стороны,')
        P('   интервалы шириной в 3–9 раз. Поэтому по регистрациям честный итог: связи нет, но и «не делят» в узком смысле доказать нельзя —')
        P('   не решается на этих данных с заявленной точностью; сырое 2,7× по Вебмастеру после стратификации осталось точечно, но не значимо и обращается на августовских парах.')
else:
    P('   По регистрациям найдена значимая связь между сиблингами — см. числа выше (интервал отношения не накрывает 1 или ρ >= 0,15 при p < 0,05).')
P('   Как читать: ρ около нуля и S внутри перестановочного коридора означают, что удача или провал первой базы')
P('   ничего не говорят о второй базе того же аккаунта сверх того, что уже задают её набор контента и день запуска.')
P()
P('ЧТО С ЭТИМ ДЕЛАТЬ:')
if not any_link:
    P('   Ничего, это знание, не рычаг: судьба базы по выходу не наследуется ни по cf-аккаунту, ни по аккаунту Вебмастера,')
    P('   а по регистрациям сигнала нет. «Списывать аккаунт по первой базе» нельзя — вторая база того же аккаунта в своём пуле')
    P('   не хуже и не лучше чужой. Оба аккаунта вычёркиваются из подозреваемых в разбросе внутри пула «набор + день» по выходу:')
    P('   разброс не объясняется общими NS/IP Cloudflare или общим Вебмастером.')
    P('   Проверяемо на уже запущенных данных: когда закроются окна запусков 17–21.09 (к 24–25.09), пересчитать этим же скриптом —')
    P('   добавятся пары со вторыми базами сентября (сейчас 152 домена с открытым окном и 121 с одним днём); если отношение по регистрациям')
    P('   у Вебмастера уйдёт к 1 (как в прогоне с августом), вопрос закрыт целиком; если снова >= 1,5 при интервале без единицы — вернуться.')
else:
    P('   Найдена связь между сиблингами — см. числа выше. Прежде чем действовать, повторить расчёт после закрытия окон')
    P('   запусков 17–21.09 (к 24–25.09) тем же скриптом и убедиться, что знак и величина сохраняются в разрезах по зоне и порядку.')
    P('   Если сохраняются — использовать первую базу аккаунта как сигнал (не запускать вторую базу на аккаунте с провалом первой).')

with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_out_lines) + '\n')
print(f'\n[записано: {OUT_PATH}]')

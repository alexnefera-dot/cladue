#!/usr/bin/env python3
"""
Гипотеза №11. Хвост регистраций (после окна 3 суток) приходит с доменов, где сайты
продолжали выходить в поиск на 4–7 сутки, а не с «дозревающих» рано вышедших сайтов;
после окна поисковый трафик на сайто-сутки падает в ~20 раз и конвертирует хуже;
«второй жизни» у домена нет, но домены с поздними выходами надо оценивать на 7-й день.

Что проверяем.
  1. Куда приходит хвост (регистрации после окна): к доменам с поздними выходами
     (late = вышли за 7 суток − вышли за 3 суток) или пропорционально ранним выходам.
  2. Сколько даёт один поздний сайт по сравнению с ранним.
  3. Как падает плотность поискового трафика после окна и как меняется конверсия
     клика в регистрацию; есть ли зона или семейство, где хвост конвертирует лучше окна.
  4. То же по первым депозитам (ФД).

Как проверяем.
  Фильтр: окно закрыто = да; дней ≠ 1; без выбросов 3615.team и 3286.team; без
  «КОНТЕНТ НЕ ЗАПИСАН» (отдельный проход с ним — в конце). Возраст домена =
  2026-09-21 − день запуска. Для регистраций хвоста берём домены возрастом ≥10 суток
  (день запуска ≤ 2026-09-11), для плотности и конверсии — ≥14 суток (≤ 2026-09-07).
  Хвост цензурирован возрастом (у молодых доменов он ещё не пришёл), поэтому сравнения
  идут только внутри пула «набор контента + день запуска», где возраст одинаков.

  На домен: early = вышли за 3 суток; late47 = вышли за 7 − вышли за 3;
  late8 = сайтов с поиском − вышли за 7 (вышли после 7-х суток); late_alt = сайтов с
  поиском − вышли за 3 (дубль-определение из постановки); tail = регистраций −
  регистраций в окне (колонки свода); search_after = из поиска − кликов из поиска в
  окне; ФД_after = ФД − ФД в окне. Для проверки — хвост по датам регистраций:
  tail_d4 = регистраций с 4-го дня от запуска, tail_d5 = с 5-го (день 4 — последний
  день окна для волны 2, поэтому tail_d5 — «наверняка после окна»).

  (а) Ожидание хвоста домена по ранним выходам: E = (Σ tail пула / Σ early пула) × early
      домена — нуль «поздние деньги идут с ранних сайтов». Группы late47 = 0 / 1–3 / ≥4
      и терцили доли late47 от сайтов внутри пула. O/E по группам. Два нуля с 10 000
      розыгрышами (random.seed(1)): (i) хвост пула раздаётся доменам пропорционально
      early (мультиномиально); (ii) метки late-групп переставляются между доменами
      внутри пула. Контроль: то же для регистраций В ОКНЕ — O/E по группам late должно
      быть ≈1, иначе домены с поздними выходами просто лучше в целом.
      Дополнительно: нули «хвост равномерен по сайтам» (E ∝ сайтов), «хвост —
      фиксированная доля оконных регистраций домена» (E ∝ регистраций в окне), «хвост
      идёт за трафиком после окна» (E ∝ кликов после окна); разрез хвоста по доменам с
      нулём оконных регистраций; повтор главной таблицы для tail_d4 и tail_d5.
  (б) Отдача позднего сайта: Σ tail / Σ late47 против раннего Σ рег в окне / Σ early —
      пуассоновское отношение ставок с точным 95 % ДИ (условное биномиальное); это
      верхняя граница, потому что приписывает поздним сайтам весь хвост. Честнее —
      модель долей внутри пула: доля хвоста пула, приходящая с ранних сайтов (1 − θ47
      − θ8), с поздних 4–7 суток (θ47) и с поздних после 7 суток (θ8); внутри пула
      каждая доля раздаётся доменам пропорционально их сайтам этого типа. Условное
      правдоподобие по сетке θ с шагом 0,02, профильные 95 % ДИ, LR-тест против
      θ47 = θ8 = 0. Отсюда — регистраций хвоста на 100 сайтов каждого типа.
  (в) Плотность: Σ search_after / Σ(сайтов × суток после окна) против Σ кликов в окне /
      Σ(сайтов × 3), по зонам и семействам (сутки после окна: волна 1 — возраст − 3,
      волна 2 — возраст − 4, так как её переобход на день позже). Конверсия:
      Σ tail / Σ search_after против Σ рег в окне / Σ кликов в окне — точный
      биномиальный тест при известных экспозициях; в страте пул: E = оконная ставка
      пула на клик × search_after домена, O/E суммарно и по зонам, Монте-Карло под
      нулём «клик после окна конвертирует как клик в окне того же домена»; для набора
      групп (зоны, семейства) — Монте-Карло на весь набор: есть ли группа, где хвост
      конвертирует лучше окна (статистика — наименьшее «верхнее» p по группам).
  (г) То же по ФД: ФД_after против ФД в окне на клик и на регистрацию.

  Критерии постановки: O/E(late≥4) ≥ 2 и O/E(late=0) ≤ 0,5 при p < 0,01 при O/E ≈ 1 для
  регистраций в окне; конверсия хвоста ≤ 0,8 оконной при p < 0,05; плотность ≤ 0,1 во
  всех зонах; ни одна зона/семейство с конверсией хвоста выше оконной.
"""
import collections
import csv
import datetime
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h11_tail_from_late_exits.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
REF = datetime.date(2026, 9, 21)
AGE_TAIL = 10      # для регистраций хвоста: день запуска <= 2026-09-11
AGE_DENS = 14      # для плотности и конверсии: день запуска <= 2026-09-07
NSIM = 10000
ZONES = ('team', 'lol', 'casino', 'buzz')
LATE_GROUPS = ('0', '1-3', '>=4')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)

    def flush(self):
        sys.stdout.flush()
        self.f.flush()


def I(x):
    return int(float(x)) if x not in ('', None) else 0


def D(s):
    return datetime.date.fromisoformat(s)


def fmt(x, nd=2):
    if x is None:
        return 'н/д'
    if isinstance(x, float) and math.isnan(x):
        return 'н/д'
    if isinstance(x, float) and math.isinf(x):
        return 'беск.'
    return f'{x:.{nd}f}'


def ratio(a, b):
    return a / b if b else float('nan')


# ---------- точные биномиальные расчёты ----------
def log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_pmf(k, n, p):
    if p <= 0:
        return 1.0 if k == 0 else 0.0
    if p >= 1:
        return 1.0 if k == n else 0.0
    return math.exp(log_choose(n, k) + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_cdf(k, n, p):
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(0, k + 1)))


def binom_sf(k, n, p):  # P(X >= k)
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(k, n + 1)))


def bisect_root(f, lo, hi, it=200):
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm <= 0) == (flo <= 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0 if k == 0 else bisect_root(lambda p: binom_sf(k, n, p) - alpha / 2, 0.0, 1.0)
    hi = 1.0 if k == n else bisect_root(lambda p: binom_cdf(k, n, p) - alpha / 2, 0.0, 1.0)
    return (lo, hi)


def rate_ratio_ci(x1, t1, x2, t2):
    """Отношение ставок (x1/t1) : (x2/t2) с точным 95 % ДИ (условное биномиальное)."""
    n = x1 + x2
    rr = ratio(ratio(x1, t1), ratio(x2, t2))
    if n == 0 or t1 <= 0 or t2 <= 0:
        return rr, float('nan'), float('nan')
    lo, hi = clopper_pearson(x1, n)

    def conv(pi):
        return float('inf') if pi >= 1 else (pi * t2) / ((1 - pi) * t1)
    return rr, conv(lo), conv(hi)


def chi2_sf(x, df):
    x = max(x, 0.0)
    if df == 1:
        return math.erfc(math.sqrt(x / 2))
    if df == 2:
        return math.exp(-x / 2)
    raise ValueError(df)


# ---------- чтение и фильтры ----------
def load():
    with open(SRC, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def make_domain(r):
    age = (REF - D(r['день запуска'])).days
    age2 = (REF - D(r['последний день'])).days if r['последний день'] else age
    sites = I(r['сайтов'])
    w1 = I(r['сайтов в 1-й волне'])
    w2 = I(r['сайтов во 2-й волне'])
    if w1 + w2 != sites:
        w1, w2 = sites, 0
    early = I(r['вышли за 3 суток'])
    out7 = I(r['вышли за 7 суток'])
    ssearch = I(r['сайтов с поиском'])
    offs = [(D(s) - D(r['день запуска'])).days for s in r['даты регистраций'].split()]
    d = {
        'домен': r['домен'],
        'зона': r['зона'] if r['зона'] in ZONES else 'прочие',
        'день': r['день запуска'],
        'набор': r['набор контента'],
        'семейство': r['семейство'],
        'пул': (r['набор контента'], r['день запуска']),
        'возраст': age,
        'сайтов': sites,
        'early': early,
        'late47': out7 - early,
        'late8': ssearch - out7,
        'late_alt': ssearch - early,
        'reg': I(r['регистраций']),
        'reg_w': I(r['регистраций в окне 3 суток']),
        'fd': I(r['ФД']),
        'fd_w': I(r['ФД в окне 3 суток']),
        'search': I(r['из поиска']),
        'search_w': I(r['кликов из поиска в окне']),
        'exp_w': sites * 3,
        'exp_after': w1 * max(0, age - 3) + w2 * max(0, age2 - 3),
        'даты': offs,
        'tail_d4': sum(1 for o in offs if o >= 4),
        'tail_d5': sum(1 for o in offs if o >= 5),
        'n03': sum(1 for o in offs if o <= 3),
    }
    d['tail'] = d['reg'] - d['reg_w']
    d['search_after'] = d['search'] - d['search_w']
    d['fd_after'] = d['fd'] - d['fd_w']
    d['late_group'] = '0' if d['late47'] == 0 else ('1-3' if d['late47'] <= 3 else '>=4')
    return d


def apply_filters(rows, out, keep_nocontent=False):
    n0 = len(rows)
    a = [r for r in rows if r['окно закрыто'] == 'да']
    n1 = n0 - len(a)
    b = [r for r in a if r['дней'] != '1']
    n2 = len(a) - len(b)
    c = [r for r in b if r['домен'] not in OUTLIERS]
    n3 = len(b) - len(c)
    if keep_nocontent:
        d = c
        n4 = 0
    else:
        d = [r for r in c if r['набор контента'] != NOCONTENT]
        n4 = len(c) - len(d)
    out.write(f'Строк в своде: {n0}. Исключено: окно не закрыто {n1}; дней = 1 {n2}; '
              f'выбросы {n3} ({", ".join(OUTLIERS)}); «{NOCONTENT}» {n4}. Осталось {len(d)}.\n')
    doms = [make_domain(r) for r in d]
    neg = sum(1 for x in doms if x['tail'] < 0 or x['search_after'] < 0 or x['late47'] < 0 or x['late8'] < 0)
    mism = sum(1 for r in d if I(r['сайтов']) != I(r['сайтов в окне']))
    out.write(f'Проверка: отрицательных хвостов/поздних выходов {neg}; строк, где «сайтов» ≠ «сайтов в окне»: {mism}.\n')
    return doms


def subset_age(doms, min_age):
    return [d for d in doms if d['возраст'] >= min_age]


def by_pool(doms):
    pools = collections.defaultdict(list)
    for d in doms:
        pools[d['пул']].append(d)
    return pools


# ---------- (а) стратифицированное O/E по группам ----------
def strat_oe(doms, num_key, exp_key, group_of, groups, rng=None, nsim=0):
    """E домена = (Σ num пула / Σ exp пула) × exp домена; O/E по группам.
    Пулы из одного домена и пулы с Σ exp = 0 не участвуют."""
    pools = [v for v in by_pool(doms).values() if len(v) >= 2 and sum(d[exp_key] for d in v) > 0]
    used = [d for v in pools for d in v]
    lost = sum(d[num_key] for d in doms) - sum(d[num_key] for d in used)
    O = collections.Counter()
    E = collections.Counter()
    N = collections.Counter()
    S = collections.Counter()
    EXP = collections.Counter()
    for v in pools:
        tot_n = sum(d[num_key] for d in v)
        tot_e = sum(d[exp_key] for d in v)
        for d in v:
            g = group_of(d)
            O[g] += d[num_key]
            E[g] += tot_n * d[exp_key] / tot_e
            N[g] += 1
            S[g] += d['сайтов']
            EXP[g] += d[exp_key]
    table = {g: (N[g], S[g], EXP[g], O[g], E[g], ratio(O[g], E[g])) for g in groups}
    res = {'table': table, 'n_pools': len(pools), 'n_dom': len(used), 'lost': lost,
           'total_num': sum(d[num_key] for d in used)}
    if rng is not None and nsim:
        obs_hi = ratio(O[groups[-1]], E[groups[-1]])
        obs_lo = ratio(O[groups[0]], E[groups[0]])
        obs_chi = sum((O[g] - E[g]) ** 2 / E[g] for g in groups if E[g] > 0)
        c_hi = c_lo = c_chi = 0
        p_hi = p_lo = p_chi = 0
        prep = []
        for v in pools:
            tot_n = sum(d[num_key] for d in v)
            tot_e = sum(d[exp_key] for d in v)
            cum = []
            acc = 0.0
            for d in v:
                acc += d[exp_key] / tot_e
                cum.append(acc)
            prep.append((v, tot_n, tot_e, cum, [group_of(d) for d in v]))
        for _ in range(nsim):
            Oi = collections.Counter()
            Op = collections.Counter()
            Ep = collections.Counter()
            for v, tot_n, tot_e, cum, labels in prep:
                for _k in range(tot_n):          # нуль (i): раздача суммы пула ∝ exp
                    u = rng.random()
                    j = 0
                    while j < len(cum) - 1 and cum[j] < u:
                        j += 1
                    Oi[labels[j]] += 1
                lab = labels[:]                  # нуль (ii): перестановка меток в пуле
                rng.shuffle(lab)
                for d, g in zip(v, lab):
                    Op[g] += d[num_key]
                    Ep[g] += tot_n * d[exp_key] / tot_e
            if ratio(Oi[groups[-1]], E[groups[-1]]) >= obs_hi - 1e-12:
                c_hi += 1
            if ratio(Oi[groups[0]], E[groups[0]]) <= obs_lo + 1e-12:
                c_lo += 1
            if sum((Oi[g] - E[g]) ** 2 / E[g] for g in groups if E[g] > 0) >= obs_chi - 1e-12:
                c_chi += 1
            if ratio(Op[groups[-1]], Ep[groups[-1]]) >= obs_hi - 1e-12:
                p_hi += 1
            if ratio(Op[groups[0]], Ep[groups[0]]) <= obs_lo + 1e-12:
                p_lo += 1
            if sum((Op[g] - Ep[g]) ** 2 / Ep[g] for g in groups if Ep[g] > 0) >= obs_chi - 1e-12:
                p_chi += 1
        res['p'] = {'multi_hi': (c_hi + 1) / (nsim + 1), 'multi_lo': (c_lo + 1) / (nsim + 1),
                    'multi_chi': (c_chi + 1) / (nsim + 1), 'perm_hi': (p_hi + 1) / (nsim + 1),
                    'perm_lo': (p_lo + 1) / (nsim + 1), 'perm_chi': (p_chi + 1) / (nsim + 1)}
    return res


def print_oe_table(out, res, groups, num_name, exp_name, group_name):
    out.write(f'  Страта: пулов {res["n_pools"]}, доменов {res["n_dom"]}, {num_name} в страте {res["total_num"]} '
              f'(вне страты — пулы из 1 домена или без {exp_name}: {res["lost"]}).\n')
    out.write(f'  {group_name:12s} {"доменов":>8s} {"сайтов":>8s} {exp_name:>14s} {"O":>5s} {"E":>7s} {"O/E":>6s}\n')
    for g in groups:
        n, s, ex, o, e, oe = res['table'][g]
        out.write(f'  {g:12s} {n:8d} {s:8d} {ex:14d} {o:5d} {e:7.2f} {fmt(oe):>6s}\n')
    if 'p' in res:
        p = res['p']
        out.write(f'  p (нуль i, раздача пропорционально {exp_name}): O/E({groups[-1]}) ≥ набл. {p["multi_hi"]:.4f}; '
                  f'O/E({groups[0]}) ≤ набл. {p["multi_lo"]:.4f}; χ² по группам {p["multi_chi"]:.4f}\n')
        out.write(f'  p (нуль ii, перестановка меток в пуле): O/E({groups[-1]}) ≥ набл. {p["perm_hi"]:.4f}; '
                  f'O/E({groups[0]}) ≤ набл. {p["perm_lo"]:.4f}; χ² по группам {p["perm_chi"]:.4f}\n')


def tertile_labels(doms):
    """Терциль доли late47 от сайтов внутри пула (пулы ≥3 доменов)."""
    lab = {}
    for v in by_pool(doms).values():
        if len(v) < 3:
            continue
        order = sorted(v, key=lambda d: (ratio(d['late47'], d['сайтов']), d['домен']))
        n = len(order)
        for i, d in enumerate(order):
            lab[d['домен']] = 'низкая' if i * 3 < n else ('средняя' if i * 3 < 2 * n else 'высокая')
    return lab


def raw_group_table(out, doms, key_group, groups, title):
    out.write(f'  {title}\n')
    out.write(f'  {"группа":12s} {"доменов":>8s} {"сайтов":>8s} {"early":>7s} {"late47":>7s} {"late8":>7s} '
              f'{"рег окно":>9s} {"хвост":>6s} {"хвост/100с":>10s} {"окно/100с":>10s} {"хвост/окно":>10s} {"хвост/late47":>12s}\n')
    for g in groups:
        v = [d for d in doms if key_group(d) == g]
        n = len(v)
        s = sum(d['сайтов'] for d in v)
        e = sum(d['early'] for d in v)
        l47 = sum(d['late47'] for d in v)
        l8 = sum(d['late8'] for d in v)
        rw = sum(d['reg_w'] for d in v)
        t = sum(d['tail'] for d in v)
        out.write(f'  {g:12s} {n:8d} {s:8d} {e:7d} {l47:7d} {l8:7d} {rw:9d} {t:6d} {fmt(100 * ratio(t, s), 3):>10s} '
                  f'{fmt(100 * ratio(rw, s), 3):>10s} {fmt(ratio(t, rw)):>10s} {fmt(100 * ratio(t, l47), 2):>12s}\n')


def traffic_group_table(out, doms, key_group, groups, title):
    out.write(f'  {title}\n')
    out.write(f'  {"группа":12s} {"доменов":>8s} {"кл.окно":>9s} {"кл.после":>9s} {"пл.окно":>8s} {"пл.после":>8s} {"после/окно":>10s} '
              f'{"рег окно":>9s} {"хвост":>6s} {"конв.окно":>9s} {"конв.хвост":>10s}\n')
    for g in groups:
        v = [d for d in doms if key_group(d) == g]
        cw = sum(d['search_w'] for d in v)
        ca = sum(d['search_after'] for d in v)
        ew = sum(d['exp_w'] for d in v)
        ea = sum(d['exp_after'] for d in v)
        rw = sum(d['reg_w'] for d in v)
        t = sum(d['tail'] for d in v)
        out.write(f'  {g:12s} {len(v):8d} {cw:9d} {ca:9d} {fmt(100 * ratio(cw, ew), 1):>8s} {fmt(100 * ratio(ca, ea), 1):>8s} '
                  f'{fmt(ratio(ratio(ca, ea), ratio(cw, ew)), 3):>10s} {rw:9d} {t:6d} {fmt(1e4 * ratio(rw, cw)):>9s} {fmt(1e4 * ratio(t, ca)):>10s}\n')


# ---------- (б) модель долей хвоста внутри пула ----------
COMPS = ('early', 'late47', 'late8')


def share_loglik(pools, theta):
    """theta = (θ_early, θ47, θ8), сумма 1. Внутри пула доля каждого типа раздаётся
    доменам пропорционально их сайтам этого типа; типы, которых в пуле нет, выпадают,
    остальные доли перенормируются."""
    ll = 0.0
    for v, sums in pools:
        avail = [(theta[k], k) for k in range(3) if sums[k] > 0]
        wsum = sum(w for w, _ in avail)
        if wsum <= 0:
            return float('-inf')
        for d in v:
            if d['tail'] > 0:
                p = sum(w * d[COMPS[k]] / sums[k] for w, k in avail) / wsum
                if p <= 0:
                    return float('-inf')
                ll += d['tail'] * math.log(p)
    return ll


def fit_share_model(doms, step=0.02):
    raw = [v for v in by_pool(doms).values() if len(v) >= 2 and sum(d['tail'] for d in v) > 0]
    pools = [(v, tuple(sum(d[k] for d in v) for k in COMPS)) for v in raw]
    n = int(round(1 / step))
    surf = {}
    best = (float('-inf'), None)
    for i in range(n + 1):
        for j in range(n + 1 - i):
            t47 = i * step
            t8 = j * step
            th = (1 - t47 - t8, t47, t8)
            ll = share_loglik(pools, th)
            surf[(round(t47, 4), round(t8, 4))] = ll
            if ll > best[0]:
                best = (ll, (round(t47, 4), round(t8, 4)))
    llmax, (b47, b8) = best

    def profile(fn):
        prof = collections.defaultdict(lambda: float('-inf'))
        for (t47, t8), ll in surf.items():
            key = round(fn(t47, t8), 4)
            prof[key] = max(prof[key], ll)
        ok = [k for k, ll in prof.items() if ll >= llmax - 1.92]
        return (min(ok), max(ok))
    res = {
        'pools': len(pools), 'doms': sum(len(v) for v, _ in pools), 'tail': sum(d['tail'] for v, _ in pools for d in v),
        'llmax': llmax, 't47': b47, 't8': b8, 'tlate': round(b47 + b8, 4),
        'ci47': profile(lambda a, b: a), 'ci8': profile(lambda a, b: b), 'ci_late': profile(lambda a, b: a + b),
        'll0': surf[(0.0, 0.0)],
        'll_no47': max(ll for (a, b), ll in surf.items() if a == 0.0),
        'll_no8': max(ll for (a, b), ll in surf.items() if b == 0.0),
        'surf': surf,
    }
    return res


# ---------- (в) конверсия и плотность ----------
def conv_block(out, doms, key_group, groups, title, rng, nsim, numw='reg_w', tail='tail', what='рег'):
    out.write(f'  {title}\n')
    out.write(f'  {"группа":14s} {"доменов":>7s} {"сайтов":>7s} {"кл.окно":>9s} {"кл.после":>9s} {"пл.окно":>8s} {"пл.после":>8s} '
              f'{"после/окно":>10s} {what + " окно":>9s} {what + " хвост":>9s} {"конв.окно":>9s} {"конв.хвост":>10s} '
              f'{"хвост/окно":>10s} {"p хуже":>8s} {"p лучше":>8s}\n')
    rows = []
    for g in groups:
        v = [d for d in doms if key_group(d) == g]
        if not v:
            continue
        n = len(v)
        s = sum(d['сайтов'] for d in v)
        cw = sum(d['search_w'] for d in v)
        ca = sum(d['search_after'] for d in v)
        ew = sum(d['exp_w'] for d in v)
        ea = sum(d['exp_after'] for d in v)
        rw = sum(d[numw] for d in v)
        rt = sum(d[tail] for d in v)
        dens_w = 100 * ratio(cw, ew)
        dens_a = 100 * ratio(ca, ea)
        conv_w = 1e4 * ratio(rw, cw)
        conv_a = 1e4 * ratio(rt, ca)
        N = rw + rt
        p0 = ratio(ca, ca + cw)
        p_worse = binom_cdf(rt, N, p0) if N else float('nan')
        p_better = binom_sf(rt, N, p0) if N else float('nan')
        rows.append((g, N, p0, rt, p_better, rw, ca, cw))
        out.write(f'  {g:14s} {n:7d} {s:7d} {cw:9d} {ca:9d} {fmt(dens_w, 1):>8s} {fmt(dens_a, 1):>8s} '
                  f'{fmt(ratio(dens_a, dens_w), 3):>10s} {rw:9d} {rt:9d} {fmt(conv_w):>9s} {fmt(conv_a):>10s} '
                  f'{fmt(ratio(conv_a, conv_w)):>10s} {fmt(p_worse, 4):>8s} {fmt(p_better, 4):>8s}\n')
    valid = [r for r in rows if r[1] > 0]
    if len(valid) >= 2:
        obs = min(r[4] for r in valid)
        cnt = 0
        for _ in range(nsim):
            m = 1.0
            for g, N, p0, rt, _pb, _rw, _ca, _cw in valid:
                x = sum(1 for _k in range(N) if rng.random() < p0)
                m = min(m, binom_sf(x, N, p0))
            if m <= obs + 1e-12:
                cnt += 1
        best = min(valid, key=lambda r: r[4])
        out.write(f'  Монте-Карло на весь набор ({len(valid)} групп, {nsim} розыгрышей): наименьшее «p лучше» = {obs:.4f} '
                  f'(группа {best[0]}), p с поправкой на перебор = {(cnt + 1) / (nsim + 1):.4f}\n')
    return rows


def strat_conv(doms, tail='tail', numw='reg_w'):
    """E хвоста домена = (Σ рег в окне пула / Σ кликов в окне пула) × search_after домена."""
    pools = [v for v in by_pool(doms).values() if sum(d['search_w'] for d in v) > 0]
    O = collections.Counter()
    E = collections.Counter()
    for v in pools:
        rate = sum(d[numw] for d in v) / sum(d['search_w'] for d in v)
        for d in v:
            O[d['зона']] += d[tail]
            E[d['зона']] += rate * d['search_after']
            O['всего'] += d[tail]
            E['всего'] += rate * d['search_after']
    lost = sum(d[tail] for d in doms) - O['всего']
    return O, E, len(pools), lost


def strat_conv_mc(doms, rng, nsim, tail='tail', numw='reg_w'):
    """Нуль: в каждом домене клик после окна конвертирует как клик в окне; регистрации
    домена делятся между окном и хвостом биномиально; считаем O/E страты."""
    pools = [v for v in by_pool(doms).values() if sum(d['search_w'] for d in v) > 0]
    O, E, _, _ = strat_conv(doms, tail, numw)
    obs = ratio(O['всего'], E['всего'])
    cnt = 0
    for _ in range(nsim):
        o = e = 0.0
        for v in pools:
            tw = ta = 0
            for d in v:
                N = d[numw] + d[tail]
                tot = d['search_after'] + d['search_w']
                p0 = ratio(d['search_after'], tot) if tot else 0.0
                x = sum(1 for _k in range(N) if rng.random() < p0)
                ta += x
                tw += N - x
            rate = tw / sum(d['search_w'] for d in v)
            o += ta
            e += rate * sum(d['search_after'] for d in v)
        if ratio(o, e) <= obs + 1e-12:
            cnt += 1
    return obs, (cnt + 1) / (nsim + 1)


# ---------- разделы ----------
def section_a(out, doms, label, rng, full=True):
    out.write(f'\n--- (а) Куда идёт хвост: {label} ---\n')
    T = sum(d['tail'] for d in doms)
    out.write(f'  Доменов {len(doms)}, сайтов {sum(d["сайтов"] for d in doms)}, регистраций всего {sum(d["reg"] for d in doms)}, '
              f'в окне {sum(d["reg_w"] for d in doms)}, хвост {T} '
              f'({fmt(100 * ratio(T, sum(d["reg"] for d in doms)), 1)} % регистраций); '
              f'early {sum(d["early"] for d in doms)}, late47 {sum(d["late47"] for d in doms)}, late8 {sum(d["late8"] for d in doms)}.\n')
    out.write(f'  Хвост по датам: с 4-го дня {sum(d["tail_d4"] for d in doms)}, с 5-го дня {sum(d["tail_d5"] for d in doms)}; '
              f'регистраций на 0–3-й день, не попавших «в окно» по своду: {sum(max(0, d["n03"] - d["reg_w"]) for d in doms)} '
              f'(например, регистрация в день запуска на сайте волны 2 — до его переобхода).\n')
    raw_group_table(out, doms, lambda d: d['late_group'], LATE_GROUPS, 'Сырые суммы по группам late47 (без страты):')
    traffic_group_table(out, doms, lambda d: d['late_group'], LATE_GROUPS,
                        'Трафик после окна по группам late47 (клики на 100 сайто-суток; конверсия на 10 тыс. кликов):')
    out.write('\n  Хвост: E ∝ early (вышли за 3 суток) внутри пула — нуль «поздние деньги идут с ранних сайтов».\n')
    res = strat_oe(doms, 'tail', 'early', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
    print_oe_table(out, res, LATE_GROUPS, 'хвост', 'early', 'late47')
    out.write('\n  КОНТРОЛЬ — регистрации В ОКНЕ: E ∝ early внутри пула (должно быть O/E ≈ 1).\n')
    resc = strat_oe(doms, 'reg_w', 'early', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
    print_oe_table(out, resc, LATE_GROUPS, 'рег в окне', 'early', 'late47')
    out.write('\n  Хвост: E ∝ сайтов внутри пула (нуль «хвост равномерен по сайтам», как в обосновании гипотезы).\n')
    ress = strat_oe(doms, 'tail', 'сайтов', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
    print_oe_table(out, ress, LATE_GROUPS, 'хвост', 'сайтов', 'late47')
    out.write('\n  Хвост: E ∝ регистраций в окне внутри пула (нуль «хвост — дозревание оконных регистраций домена»).\n')
    resr = strat_oe(doms, 'tail', 'reg_w', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
    print_oe_table(out, resr, LATE_GROUPS, 'хвост', 'reg_w', 'late47')
    out.write('\n  Хвост: E ∝ кликов из поиска после окна внутри пула (нуль «хвост идёт за трафиком после окна, кто бы его ни давал»).\n')
    resk = strat_oe(doms, 'tail', 'search_after', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
    print_oe_table(out, resk, LATE_GROUPS, 'хвост', 'search_after', 'late47')
    tl = tertile_labels(doms)
    tdoms = [d for d in doms if d['домен'] in tl]
    tgroups = ('низкая', 'средняя', 'высокая')
    out.write(f'\n  Терцили доли late47 от сайтов внутри пула (пулы ≥3 доменов; доменов {len(tdoms)}), хвост, E ∝ early:\n')
    rest = strat_oe(tdoms, 'tail', 'early', lambda d: tl[d['домен']], tgroups, rng, NSIM)
    print_oe_table(out, rest, tgroups, 'хвост', 'early', 'терциль')
    out.write('  Контроль по терцилям — регистрации в окне, E ∝ early:\n')
    restc = strat_oe(tdoms, 'reg_w', 'early', lambda d: tl[d['домен']], tgroups, rng, NSIM)
    print_oe_table(out, restc, tgroups, 'рег в окне', 'early', 'терциль')

    def alt_group(d):
        return '0' if d['late_alt'] == 0 else ('1-3' if d['late_alt'] <= 3 else '>=4')
    out.write('\n  Дубль-определение late_alt = сайтов с поиском − вышли за 3 суток (включая выходы после 7-х суток), хвост, E ∝ early:\n')
    resa = strat_oe(doms, 'tail', 'early', alt_group, LATE_GROUPS, rng, NSIM)
    print_oe_table(out, resa, LATE_GROUPS, 'хвост', 'early', 'late_alt')
    out.write('  Контроль по late_alt — регистрации в окне, E ∝ early:\n')
    resac = strat_oe(doms, 'reg_w', 'early', alt_group, LATE_GROUPS, rng, NSIM)
    print_oe_table(out, resac, LATE_GROUPS, 'рег в окне', 'early', 'late_alt')
    resd4 = resd5 = None
    if full:
        out.write('\n  Проверка определения хвоста — по датам регистраций, с 4-го дня от запуска (tail_d4), E ∝ early:\n')
        resd4 = strat_oe(doms, 'tail_d4', 'early', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
        print_oe_table(out, resd4, LATE_GROUPS, 'хвост d4', 'early', 'late47')
        out.write('  То же с 5-го дня (tail_d5 — наверняка после окна обеих волн), E ∝ early:\n')
        resd5 = strat_oe(doms, 'tail_d5', 'early', lambda d: d['late_group'], LATE_GROUPS, rng, NSIM)
        print_oe_table(out, resd5, LATE_GROUPS, 'хвост d5', 'early', 'late47')
    out.write('\n  Хвост по доменам с нулём / с ≥1 регистрацией в окне (сырые суммы):\n')
    out.write(f'  {"late47":8s} {"рег.окно=0: доменов":>20s} {"хвост":>6s} {"рег.окно≥1: доменов":>20s} {"хвост":>6s} {"рег в окне":>10s}\n')
    for g in LATE_GROUPS:
        v0 = [d for d in doms if d['late_group'] == g and d['reg_w'] == 0]
        v1 = [d for d in doms if d['late_group'] == g and d['reg_w'] > 0]
        out.write(f'  {g:8s} {len(v0):20d} {sum(d["tail"] for d in v0):6d} {len(v1):20d} {sum(d["tail"] for d in v1):6d} {sum(d["reg_w"] for d in v1):10d}\n')
    return {'res': res, 'resc': resc, 'ress': ress, 'resr': resr, 'resk': resk, 'rest': rest, 'restc': restc,
            'resa': resa, 'resac': resac, 'resd4': resd4, 'resd5': resd5}


def section_b(out, doms, label):
    out.write(f'\n--- (б) Отдача позднего сайта: {label} ---\n')
    T = sum(d['tail'] for d in doms)
    L47 = sum(d['late47'] for d in doms)
    L8 = sum(d['late8'] for d in doms)
    RW = sum(d['reg_w'] for d in doms)
    EA = sum(d['early'] for d in doms)
    rr, lo, hi = rate_ratio_ci(T, L47, RW, EA)
    out.write(f'  Наивно (весь хвост приписан поздним сайтам 4–7 суток): Σ tail / Σ late47 = {T}/{L47} = '
              f'{fmt(100 * ratio(T, L47))} рег/100 поздних сайтов; ранний сайт в окне: Σ рег в окне / Σ early = {RW}/{EA} = '
              f'{fmt(100 * ratio(RW, EA))} рег/100. Отношение поздний/ранний = {fmt(rr)} (95 % ДИ {fmt(lo)}–{fmt(hi)}).\n')
    rr2, lo2, hi2 = rate_ratio_ci(T, L47 + L8, RW, EA)
    out.write(f'  То же, хвост на все поздние сайты (late47 + late8 = {L47 + L8}): {fmt(100 * ratio(T, L47 + L8))} рег/100, '
              f'отношение {fmt(rr2)} (95 % ДИ {fmt(lo2)}–{fmt(hi2)}). Это верхняя граница: считает, что с ранних сайтов хвоста нет.\n')
    m = fit_share_model(doms)
    out.write(f'\n  Модель долей внутри пула (пулов {m["pools"]}, доменов {m["doms"]}, хвост {m["tail"]}): доля хвоста с ранних сайтов '
              f'{fmt(1 - m["tlate"])}, с поздних 4–7 суток θ47 = {fmt(m["t47"])} (профильный 95 % ДИ {fmt(m["ci47"][0])}–{fmt(m["ci47"][1])}), '
              f'с поздних после 7 суток θ8 = {fmt(m["t8"])} (95 % ДИ {fmt(m["ci8"][0])}–{fmt(m["ci8"][1])}); '
              f'всего с поздних θ47 + θ8 = {fmt(m["tlate"])} (95 % ДИ {fmt(m["ci_late"][0])}–{fmt(m["ci_late"][1])}).\n')
    lr = 2 * (m['llmax'] - m['ll0'])
    out.write(f'  LR-тест «весь хвост с ранних сайтов» (θ47 = θ8 = 0): 2Δll = {fmt(lr)}, p ≈ {chi2_sf(lr, 2):.4f} (χ² 2 df, на границе — консервативно).\n')
    lr1 = 2 * (m['llmax'] - m['ll_no47'])
    lr2 = 2 * (m['llmax'] - m['ll_no8'])
    out.write(f'  Вклад θ47 сверх θ8: 2Δll = {fmt(lr1)}, p ≈ {chi2_sf(lr1, 1):.4f}; вклад θ8 сверх θ47: 2Δll = {fmt(lr2)}, p ≈ {chi2_sf(lr2, 1):.4f}.\n')
    y_e = 100 * ratio((1 - m['tlate']) * T, EA)
    y47 = 100 * ratio(m['t47'] * T, L47)
    y8 = 100 * ratio(m['t8'] * T, L8)
    y47_lo = 100 * ratio(m['ci47'][0] * T, L47)
    y47_hi = 100 * ratio(m['ci47'][1] * T, L47)
    out.write(f'  Регистраций хвоста на 100 сайтов (по долям модели): ранний сайт {fmt(y_e, 3)}, поздний 4–7 суток {fmt(y47, 2)} '
              f'(ДИ {fmt(y47_lo, 2)}–{fmt(y47_hi, 2)}), поздний после 7 суток {fmt(y8, 2)}; для сравнения ранний сайт в окне '
              f'{fmt(100 * ratio(RW, EA), 3)} рег/100 → поздний сайт 4–7 суток относительно раннего в окне: {fmt(ratio(y47, 100 * ratio(RW, EA)))}.\n')
    out.write(f'  Разложение хвоста по модели: с ранних сайтов {fmt((1 - m["tlate"]) * T, 1)}, с поздних 4–7 {fmt(m["t47"] * T, 1)}, '
              f'с поздних 8+ {fmt(m["t8"] * T, 1)} из {T}.\n')
    prof = collections.defaultdict(lambda: float('-inf'))
    for (a, b), ll in m['surf'].items():
        prof[round(a + b, 4)] = max(prof[round(a + b, 4)], ll)
    pts = [0.0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    out.write('  Профиль правдоподобия по доле хвоста с поздних сайтов (Δll от максимума): ' +
              '; '.join(f'{p:g}: {fmt(prof[p] - m["llmax"], 2)}' for p in pts if p in prof) + '\n')
    m['y47'] = y47
    m['y8'] = y8
    m['y_e'] = y_e
    m['rr_naive'] = (rr, lo, hi)
    return m


def section_c(out, doms, label, rng):
    out.write(f'\n--- (в) Плотность трафика и конверсия хвоста: {label} ---\n')
    out.write(f'  Доменов {len(doms)}, сайтов {sum(d["сайтов"] for d in doms)}, сайто-суток в окне {sum(d["exp_w"] for d in doms)}, '
              f'после окна {sum(d["exp_after"] for d in doms)}; поисковых кликов в окне {sum(d["search_w"] for d in doms)}, '
              f'после {sum(d["search_after"] for d in doms)}; регистраций в окне {sum(d["reg_w"] for d in doms)}, хвост {sum(d["tail"] for d in doms)}.\n')
    out.write('  Плотность = поисковых кликов на 100 сайто-суток; конверсия = регистраций на 10 тыс. поисковых кликов; '
              'p — точный биномиальный тест при известных кликах («p хуже» — хвост конвертирует хуже окна, «p лучше» — лучше).\n')
    rows_all = conv_block(out, doms, lambda d: 'всего', ('всего',), 'Всего:', rng, NSIM)
    rows_z = conv_block(out, doms, lambda d: d['зона'], ZONES + ('прочие',), 'По зонам:', rng, NSIM)
    fams = sorted(set(d['семейство'] for d in doms), key=lambda f: -sum(d['сайтов'] for d in doms if d['семейство'] == f))
    rows_f = conv_block(out, doms, lambda d: d['семейство'], tuple(fams), 'По семействам:', rng, NSIM)
    cw = sum(d['search_w'] for d in doms)
    ca = sum(d['search_after'] for d in doms)
    ew = sum(d['exp_w'] for d in doms)
    ea = sum(d['exp_after'] for d in doms)
    out.write(f'  Чувствительность: окно как 4 календарных даты (день запуска + 3): плотность окна {fmt(100 * cw / (ew * 4 / 3), 1)}, '
              f'после/окно = {fmt((ca / ea) / (cw / (ew * 4 / 3)), 3)}.\n')
    O, E, npools, lost = strat_conv(doms)
    obs, p = strat_conv_mc(doms, rng, NSIM)
    out.write(f'\n  В страте пул (E хвоста = оконная ставка пула на клик × клики после окна; пулов {npools}, хвост вне страты {lost}):\n')
    out.write(f'  {"зона":8s} {"O":>5s} {"E":>8s} {"O/E":>6s}\n')
    for z in ZONES + ('прочие', 'всего'):
        if E[z] > 0 or O[z] > 0:
            out.write(f'  {z:8s} {O[z]:5d} {E[z]:8.2f} {fmt(ratio(O[z], E[z])):>6s}\n')
    out.write(f'  Монте-Карло (нуль: клик после окна конвертирует как клик в окне того же домена; {NSIM} розыгрышей): '
              f'p(O/E ≤ {fmt(obs)}) = {p:.4f}\n')
    return {'all': rows_all, 'zones': rows_z, 'fams': rows_f, 'strat': (O, E, obs, p)}


def section_d(out, doms, label, rng):
    out.write(f'\n--- (г) Первые депозиты: {label} ---\n')
    FW = sum(d['fd_w'] for d in doms)
    FA = sum(d['fd_after'] for d in doms)
    RW = sum(d['reg_w'] for d in doms)
    T = sum(d['tail'] for d in doms)
    out.write(f'  ФД в окне {FW}, ФД после окна {FA} (из {FW + FA}); регистраций в окне {RW}, хвост {T}.\n')
    conv_block(out, doms, lambda d: 'всего', ('всего',), 'ФД на 10 тыс. кликов, всего:', rng, NSIM,
               numw='fd_w', tail='fd_after', what='ФД')
    conv_block(out, doms, lambda d: d['зона'], ZONES + ('прочие',), 'ФД по зонам:', rng, NSIM,
               numw='fd_w', tail='fd_after', what='ФД')
    rr, lo, hi = rate_ratio_ci(FA, T, FW, RW) if T and RW else (float('nan'),) * 3
    out.write(f'  ФД на регистрацию: в окне {FW}/{RW} = {fmt(ratio(FW, RW), 3)}, в хвосте {FA}/{T} = {fmt(ratio(FA, T), 3)}; '
              f'отношение хвост/окно = {fmt(rr)} (95 % ДИ {fmt(lo)}–{fmt(hi)}).\n')
    out.write(f'  {"late47":8s} {"доменов":>8s} {"ФД окно":>8s} {"ФД хвост":>9s}\n')
    for g in LATE_GROUPS:
        v = [d for d in doms if d['late_group'] == g]
        out.write(f'  {g:8s} {len(v):8d} {sum(d["fd_w"] for d in v):8d} {sum(d["fd_after"] for d in v):9d}\n')
    O, E, npools, lost = strat_conv(doms, tail='fd_after', numw='fd_w')
    out.write(f'  В страте пул по ФД: O = {O["всего"]}, E = {E["всего"]:.2f}, O/E = {fmt(ratio(O["всего"], E["всего"]))} '
              f'(пулов {npools}, ФД хвоста вне страты {lost}).\n')
    return {'FW': FW, 'FA': FA, 'RW': RW, 'T': T, 'rr': (rr, lo, hi), 'oe': ratio(O['всего'], E['всего'])}


def offsets_block(out, doms, label):
    out.write(f'\n  Когда приходят регистрации (по датам регистраций, дней от дня запуска): {label}\n')
    c = collections.Counter()
    for d in doms:
        for o in d['даты']:
            c[o] += 1
    tot = sum(c.values())
    bands = [('0–3 (окно волны 1)', 0, 3), ('4–7', 4, 7), ('8–14', 8, 14), ('15+', 15, 10 ** 6)]
    parts = []
    for name, a, b in bands:
        k = sum(v for o, v in c.items() if a <= o <= b)
        parts.append(f'{name} {k} ({fmt(100 * ratio(k, tot), 1)} %)')
    out.write(f'  всего {tot}: ' + '; '.join(parts) + '\n')
    out.write('  по дням: ' + ' '.join(f'{k}:{v}' for k, v in sorted(c.items())) + '\n')
    return c


def main():
    out = Tee(OUT)
    rng = random.Random(1)
    random.seed(1)
    out.write('=' * 110 + '\n')
    out.write('Гипотеза №11. Хвост регистраций после окна 3 суток: с поздних выходов или с ранних сайтов?\n')
    out.write(f'Источник: {os.path.relpath(SRC, REPO)}; дата среза {REF}; розыгрышей {NSIM}, random.seed(1).\n')
    out.write('=' * 110 + '\n')
    rows = load()
    doms_all = apply_filters(rows, out)
    A = subset_age(doms_all, AGE_TAIL)
    C = subset_age(doms_all, AGE_DENS)
    old = subset_age(doms_all, 21)
    out.write(f'Возраст ≥{AGE_TAIL} суток (день запуска ≤ 2026-09-11): доменов {len(A)}; возраст ≥{AGE_DENS}: {len(C)}; возраст ≥21: {len(old)}.\n')
    out.write('Определение окна по своду: регистрации на 0–3-й день от запуска попадают «в окно», с 4-го дня — нет '
              '(окно = 3 суток после переобхода сайта; у волны 2 переобход на день позже).\n')

    out.write('\n' + '=' * 110 + '\nОПИСАНИЕ ХВОСТА\n' + '=' * 110 + '\n')
    cA = offsets_block(out, A, f'возраст ≥{AGE_TAIL} ({len(A)} доменов)')
    cold = offsets_block(out, old, f'возраст ≥21 ({len(old)} доменов, хвост виден полностью)')
    out.write(f'  Поздние выходы в наборе возраста ≥{AGE_TAIL}: early {sum(d["early"] for d in A)}, late47 {sum(d["late47"] for d in A)}, '
              f'late8 {sum(d["late8"] for d in A)} из {sum(d["сайтов"] for d in A)} сайтов.\n')

    out.write('\n' + '=' * 110 + '\n(а) КУДА ИДЁТ ХВОСТ — СТРАТА «НАБОР КОНТЕНТА + ДЕНЬ»\n' + '=' * 110 + '\n')
    ra = section_a(out, A, f'возраст ≥{AGE_TAIL}, без «{NOCONTENT}»', rng)
    out.write('\n' + '-' * 110 + '\nЧувствительность (а): возраст ≥14 (хвост менее цензурирован)\n')
    ra14 = section_a(out, C, 'возраст ≥14', rng, full=False)

    out.write('\n' + '=' * 110 + '\n(б) ОТДАЧА ПОЗДНЕГО САЙТА\n' + '=' * 110 + '\n')
    mb = section_b(out, A, f'возраст ≥{AGE_TAIL}')
    mb14 = section_b(out, C, 'возраст ≥14')

    out.write('\n' + '=' * 110 + '\n(в) ПЛОТНОСТЬ ТРАФИКА И КОНВЕРСИЯ ПОСЛЕ ОКНА\n' + '=' * 110 + '\n')
    rc = section_c(out, C, f'возраст ≥{AGE_DENS}', rng)

    out.write('\n' + '=' * 110 + '\n(г) ПЕРВЫЕ ДЕПОЗИТЫ\n' + '=' * 110 + '\n')
    rd = section_d(out, C, f'возраст ≥{AGE_DENS}', rng)

    out.write('\n' + '=' * 110 + f'\nОТДЕЛЬНО: С «{NOCONTENT}» (335 баз до 24.08; пул «{NOCONTENT} + день» = просто день)\n' + '=' * 110 + '\n')
    doms_noc = apply_filters(rows, out, keep_nocontent=True)
    An = subset_age(doms_noc, AGE_TAIL)
    Cn = subset_age(doms_noc, AGE_DENS)
    ran = section_a(out, An, f'возраст ≥{AGE_TAIL}, с «{NOCONTENT}»', rng, full=False)
    mbn = section_b(out, An, f'возраст ≥{AGE_TAIL}, с «{NOCONTENT}»')
    rcn = section_c(out, Cn, f'возраст ≥{AGE_DENS}, с «{NOCONTENT}»', rng)

    # ---------- ВЫВОД ----------
    out.write('\n' + '=' * 110 + '\nВЫВОД\n' + '=' * 110 + '\n')
    res, resc, ress, resr, resk = ra['res'], ra['resc'], ra['ress'], ra['resr'], ra['resk']
    rest, restc, resa, resac, resd4, resd5 = ra['rest'], ra['restc'], ra['resa'], ra['resac'], ra['resd4'], ra['resd5']
    t, tc, ts, tr, tk = res['table'], resc['table'], ress['table'], resr['table'], resk['table']
    tt, ttc, ta, tac = rest['table'], restc['table'], resa['table'], resac['table']
    t14, tc14 = ra14['res']['table'], ra14['resc']['table']
    tn, tcn = ran['res']['table'], ran['resc']['table']
    oe4, oe0, oe13 = t['>=4'][5], t['0'][5], t['1-3'][5]
    coe4, coe0 = tc['>=4'][5], tc['0'][5]
    p4, p0 = res['p']['multi_hi'], res['p']['multi_lo']
    pp4, pp0 = res['p']['perm_hi'], res['p']['perm_lo']
    T = sum(d['tail'] for d in A)
    R = sum(d['reg'] for d in A)
    RW = sum(d['reg_w'] for d in A)
    raw = {g: [d for d in A if d['late_group'] == g] for g in LATE_GROUPS}
    tail0 = sum(d['tail'] for d in raw['0'])
    regw0 = sum(d['reg_w'] for d in raw['0'])
    tail_zero_w = sum(d['tail'] for d in A if d['reg_w'] == 0)
    O, E, obs_c, p_c = rc['strat']
    On, En, obs_cn, p_cn = rcn['strat']
    C_cw = sum(d['search_w'] for d in C)
    C_ca = sum(d['search_after'] for d in C)
    C_ew = sum(d['exp_w'] for d in C)
    C_ea = sum(d['exp_after'] for d in C)
    C_rw = sum(d['reg_w'] for d in C)
    C_t = sum(d['tail'] for d in C)
    dens_ratio = (C_ca / C_ea) / (C_cw / C_ew)
    conv_w = 1e4 * C_rw / C_cw
    conv_a = 1e4 * C_t / C_ca
    p_worse = binom_cdf(C_t, C_rw + C_t, C_ca / (C_ca + C_cw))
    Cn_cw = sum(d['search_w'] for d in Cn)
    Cn_ca = sum(d['search_after'] for d in Cn)
    Cn_rw = sum(d['reg_w'] for d in Cn)
    Cn_t = sum(d['tail'] for d in Cn)
    conv_wn = 1e4 * Cn_rw / Cn_cw
    conv_an = 1e4 * Cn_t / Cn_ca
    p_worse_n = binom_cdf(Cn_t, Cn_rw + Cn_t, Cn_ca / (Cn_ca + Cn_cw))
    zone_dens = {}
    zone_conv = {}
    for z in ZONES:
        v = [d for d in C if d['зона'] == z]
        if not v:
            continue
        zone_dens[z] = (sum(d['search_after'] for d in v) / sum(d['exp_after'] for d in v)) / (sum(d['search_w'] for d in v) / sum(d['exp_w'] for d in v))
        zone_conv[z] = (sum(d['tail'] for d in v), sum(d['reg_w'] for d in v),
                        ratio(1e4 * ratio(sum(d['tail'] for d in v), sum(d['search_after'] for d in v)),
                              1e4 * ratio(sum(d['reg_w'] for d in v), sum(d['search_w'] for d in v))))
    best_z = min([r for r in rc['zones'] if r[1] > 0], key=lambda r: r[4])
    best_f = min([r for r in rc['fams'] if r[1] > 0], key=lambda r: r[4])
    fam_test = [d for d in C if d['семейство'] == best_f[0]]
    fam_test_doms = sorted(((d['tail'], d['домен'], ' '.join(str(o) for o in d['даты'] if o >= 4)) for d in fam_test if d['tail'] > 0), reverse=True)
    old_tot = sum(cold.values())
    old_47 = sum(v for k, v in cold.items() if 4 <= k <= 7)
    old_8 = sum(v for k, v in cold.items() if k >= 8)
    A_47 = sum(v for k, v in cA.items() if 4 <= k <= 7)
    A_8 = sum(v for k, v in cA.items() if k >= 8)
    dens_after = {g: 100 * ratio(sum(d['search_after'] for d in raw[g]), sum(d['exp_after'] for d in raw[g])) for g in LATE_GROUPS}
    conv_after = {g: 1e4 * ratio(sum(d['tail'] for d in raw[g]), sum(d['search_after'] for d in raw[g])) for g in LATE_GROUPS}
    conv_win = {g: 1e4 * ratio(sum(d['reg_w'] for d in raw[g]), sum(d['search_w'] for d in raw[g])) for g in LATE_GROUPS}

    out.write(f'1. Что за хвост. Возраст ≥{AGE_TAIL} суток, без «{NOCONTENT}»: {len(A)} доменов, {sum(d["сайтов"] for d in A)} сайтов, '
              f'{R} регистраций, из них после окна {T} ({fmt(100 * T / R, 1)} %). У доменов возрастом ≥21 суток (хвост виден целиком; '
              f'{len(old)} доменов, {old_tot} регистраций) на 4–7-й день пришло {old_47} ({fmt(100 * ratio(old_47, old_tot), 1)} %), '
              f'после 7-го дня — {old_8} ({fmt(100 * ratio(old_8, old_tot), 1)} %): хвост не кончается на 7-м дне. '
              f'Поздних выходов на 4–7-е сутки {sum(d["late47"] for d in A)} сайтов, после 7-х суток — {sum(d["late8"] for d in A)}, '
              f'ранних — {sum(d["early"] for d in A)}. Почти половина хвоста ({tail_zero_w} из {T}) сидит в доменах, у которых в окне '
              f'не было ни одной регистрации.\n')
    out.write(f'2. Куда идёт хвост (страта набор+день, E ∝ ранним выходам; {res["n_pools"]} пулов, {res["n_dom"]} доменов, хвост {res["total_num"]}): '
              f'late47 = 0 — O/E {fmt(oe0)} ({t["0"][3]} при ожидаемых {t["0"][4]:.1f}, {t["0"][0]} доменов), 1–3 — {fmt(oe13)} '
              f'({t["1-3"][3]} при {t["1-3"][4]:.1f}), ≥4 — {fmt(oe4)} ({t[">=4"][3]} при {t[">=4"][4]:.1f}, {t[">=4"][0]} доменов). '
              f'p: O/E(0) ≤ набл. {p0:.4f} (перестановка {pp0:.4f}); O/E(≥4) ≥ набл. {p4:.3f} (перестановка {pp4:.3f}). '
              f'Контроль по регистрациям в окне: O/E {fmt(coe0)} / {fmt(tc["1-3"][5])} / {fmt(coe4)} — домены с поздними выходами '
              f'в окне не лучше других, значит дело не в общем качестве домена. '
              f'То же при E ∝ сайтов: {fmt(ts["0"][5])} / {fmt(ts["1-3"][5])} / {fmt(ts[">=4"][5])}; при E ∝ оконным регистрациям: '
              f'{fmt(tr["0"][5])} / {fmt(tr["1-3"][5])} / {fmt(tr[">=4"][5])}; при E ∝ кликам после окна: {fmt(tk["0"][5])} / {fmt(tk["1-3"][5])} / {fmt(tk[">=4"][5])} '
              f'(p O/E(0) ≤ набл. {resk["p"]["multi_lo"]:.4f}). По датам регистраций (с 4-го дня): {fmt(resd4["table"]["0"][5])} / '
              f'{fmt(resd4["table"]["1-3"][5])} / {fmt(resd4["table"][">=4"][5])}; с 5-го дня: {fmt(resd5["table"]["0"][5])} / '
              f'{fmt(resd5["table"]["1-3"][5])} / {fmt(resd5["table"][">=4"][5])}. '
              f'Возраст ≥14: {fmt(t14["0"][5])} / {fmt(t14["1-3"][5])} / {fmt(t14[">=4"][5])} (контроль {fmt(tc14["0"][5])} / '
              f'{fmt(tc14["1-3"][5])} / {fmt(tc14[">=4"][5])}); с «{NOCONTENT}»: {fmt(tn["0"][5])} / {fmt(tn["1-3"][5])} / {fmt(tn[">=4"][5])} '
              f'(p O/E(0) {ran["res"]["p"]["multi_lo"]:.4f}, O/E(≥4) {ran["res"]["p"]["multi_hi"]:.3f}). '
              f'Терцили доли поздних внутри пула (хвост / контроль): низкая {fmt(tt["низкая"][5])} / {fmt(ttc["низкая"][5])}, '
              f'средняя {fmt(tt["средняя"][5])} / {fmt(ttc["средняя"][5])}, высокая {fmt(tt["высокая"][5])} / {fmt(ttc["высокая"][5])} '
              f'(p высокая {rest["p"]["multi_hi"]:.4f}). По late_alt (любой поздний выход, включая после 7-х суток): '
              f'{fmt(ta["0"][5])} ({ta["0"][3]} при {ta["0"][4]:.1f}) / {fmt(ta["1-3"][5])} / {fmt(ta[">=4"][5])} '
              f'(p O/E(≥4) {resa["p"]["multi_hi"]:.4f}; контроль {fmt(tac["0"][5])} / {fmt(tac["1-3"][5])} / {fmt(tac[">=4"][5])}).\n')
    out.write(f'   Сырые ставки хвоста на 100 сайтов: late=0 {fmt(100 * ratio(tail0, sum(d["сайтов"] for d in raw["0"])), 3)} '
              f'({tail0} рег, {len(raw["0"])} доменов), 1–3 {fmt(100 * ratio(sum(d["tail"] for d in raw["1-3"]), sum(d["сайтов"] for d in raw["1-3"])), 3)} '
              f'({sum(d["tail"] for d in raw["1-3"])} рег, {len(raw["1-3"])} доменов), ≥4 {fmt(100 * ratio(sum(d["tail"] for d in raw[">=4"]), sum(d["сайтов"] for d in raw[">=4"])), 3)} '
              f'({sum(d["tail"] for d in raw[">=4"])} рег, {len(raw[">=4"])} доменов); хвост к оконным регистрациям: late=0 {fmt(ratio(tail0, regw0))} '
              f'({tail0}/{regw0}), 1–3 {fmt(ratio(sum(d["tail"] for d in raw["1-3"]), sum(d["reg_w"] for d in raw["1-3"])))}, '
              f'≥4 {fmt(ratio(sum(d["tail"] for d in raw[">=4"]), sum(d["reg_w"] for d in raw[">=4"])))}.\n')
    out.write(f'3. Отдача позднего сайта. Модель долей внутри пула ({mb["pools"]} пулов, хвост {mb["tail"]}): с поздних сайтов приходит '
              f'{fmt(mb["tlate"])} хвоста (95 % ДИ {fmt(mb["ci_late"][0])}–{fmt(mb["ci_late"][1])}), из них с вышедших на 4–7-е сутки '
              f'{fmt(mb["t47"])} ({fmt(mb["ci47"][0])}–{fmt(mb["ci47"][1])}) и с вышедших после 7-х суток {fmt(mb["t8"])} '
              f'({fmt(mb["ci8"][0])}–{fmt(mb["ci8"][1])}); LR-тест против «весь хвост с ранних сайтов» p ≈ {chi2_sf(2 * (mb["llmax"] - mb["ll0"]), 2):.4f}. '
              f'На 100 сайтов: ранний сайт даёт в хвосте {fmt(mb["y_e"], 3)}, поздний 4–7 суток {fmt(mb["y47"], 2)}, поздний после 7-х {fmt(mb["y8"], 2)} — '
              f'против {fmt(100 * ratio(RW, sum(d["early"] for d in A)), 2)} у раннего сайта в окне. Наивная верхняя граница (весь хвост поздним 4–7): '
              f'{fmt(100 * ratio(T, sum(d["late47"] for d in A)))} рег/100, отношение к раннему {fmt(mb["rr_naive"][0])} '
              f'(ДИ {fmt(mb["rr_naive"][1])}–{fmt(mb["rr_naive"][2])}). Возраст ≥14: доля с поздних {fmt(mb14["tlate"])} '
              f'({fmt(mb14["ci_late"][0])}–{fmt(mb14["ci_late"][1])}), поздний 4–7 суток {fmt(mb14["y47"], 2)} рег/100; '
              f'с «{NOCONTENT}»: доля с поздних {fmt(mbn["tlate"])} ({fmt(mbn["ci_late"][0])}–{fmt(mbn["ci_late"][1])}).\n')
    out.write(f'4. После окна (возраст ≥{AGE_DENS}, {len(C)} доменов, {sum(d["сайтов"] for d in C)} сайтов): плотность поисковых кликов '
              f'{fmt(100 * C_ca / C_ea, 1)} на 100 сайто-суток против {fmt(100 * C_cw / C_ew, 1)} в окне — в {fmt(1 / dens_ratio, 1)} раза меньше '
              f'(после/окно {fmt(dens_ratio, 3)}; если окно считать за 4 календарных дня — {fmt((C_ca / C_ea) / (C_cw / (C_ew * 4 / 3)), 3)}); по зонам после/окно: '
              + ', '.join(f'{z} {fmt(zone_dens[z], 3)}' for z in zone_dens) +
              f'. Конверсия клика: хвост {C_t} рег на {C_ca} кликов = {fmt(conv_a)} на 10 тыс. против {fmt(conv_w)} в окне ({C_rw} на {C_cw}); '
              f'хвост/окно = {fmt(conv_a / conv_w)}, точный биномиальный p (хвост хуже) = {p_worse:.3f}. В страте пул O/E = {fmt(obs_c)} '
              f'(O={O["всего"]}, E={E["всего"]:.1f}; Монте-Карло p = {p_c:.4f}). С «{NOCONTENT}» ({len(Cn)} доменов): хвост/окно {fmt(conv_an / conv_wn)} '
              f'({Cn_t} на {Cn_ca} против {Cn_rw} на {Cn_cw}; p = {p_worse_n:.3f}), в страте O/E {fmt(obs_cn)} (p = {p_cn:.4f}). '
              f'По зонам хвост/окно: ' + ', '.join(f'{z} {fmt(zone_conv[z][2])} ({zone_conv[z][0]} против {zone_conv[z][1]})' for z in zone_conv) +
              f'; ни одна зона не лучше окна (наименьшее p лучше {best_z[4]:.3f}, {best_z[0]}). По семействам единственное «лучше окна» — '
              f'{best_f[0]}: {best_f[3]} рег хвоста при {best_f[5]} в окне (домены: ' + '; '.join(f'{dm} {tl} рег на дни {ds}' for tl, dm, ds in fam_test_doms) +
              f'), p = {best_f[4]:.4f}, с поправкой на перебор семейств — см. Монте-Карло выше; это {len(fam_test)} доменов одного набора '
              f'{fam_test[0]["набор"] if fam_test else ""}, результат держится на {fam_test_doms[0][0] if fam_test_doms else 0} регистрациях одного домена за один день.\n')
    out.write(f'5. ФД (возраст ≥{AGE_DENS}): в окне {rd["FW"]}, после окна {rd["FA"]}; ФД на регистрацию в окне {fmt(ratio(rd["FW"], rd["RW"]), 3)}, '
              f'в хвосте {fmt(ratio(rd["FA"], rd["T"]), 3)} (отношение {fmt(rd["rr"][0])}, 95 % ДИ {fmt(rd["rr"][1])}–{fmt(rd["rr"][2])}); '
              f'в страте пул по кликам O/E = {fmt(rd["oe"])}. Хвостовые регистрации депонируют не хуже оконных, но ФД слишком мало для деления по группам.\n')
    checks = [
        (f'O/E(late≥4) ≥ 2 при p < 0,01: {fmt(oe4)}, p = {p4:.4f}', oe4 >= 2 and p4 < 0.01),
        (f'O/E(late=0) ≤ 0,5 при p < 0,01: {fmt(oe0)}, p = {p0:.4f}', oe0 <= 0.5 and p0 < 0.01),
        (f'O/E по регистрациям в окне ≈ 1 (0,8–1,25) для late=0 и late≥4: {fmt(coe0)} / {fmt(coe4)}', 0.8 <= coe0 <= 1.25 and 0.8 <= coe4 <= 1.25),
        (f'конверсия хвоста ≤ 0,8 оконной при p < 0,05: {fmt(conv_a / conv_w)}, p = {p_worse:.4f} (с «{NOCONTENT}»: {fmt(conv_an / conv_wn)}, p = {p_worse_n:.4f})',
         conv_a / conv_w <= 0.8 and p_worse < 0.05),
        ('плотность после окна ≤ 0,1 оконной во всех зонах: ' + ', '.join(f'{z} {fmt(zone_dens[z], 3)}' for z in zone_dens),
         all(v <= 0.1 for v in zone_dens.values())),
        (f'ни одна зона/семейство с хвостом значимо лучше окна (наименьшее p лучше: зоны {best_z[4]:.3f}, семейства {best_f[4]:.4f} — {best_f[0]}, {best_f[3]} рег)',
         best_z[4] >= 0.05 and best_f[4] >= 0.05),
    ]
    out.write('6. Сверка с критериями постановки:\n')
    for text, ok in checks:
        out.write(f'   {"да  " if ok else "НЕТ "} {text}\n')
    out.write('   Ожидания постановки: хвост у late≥4 в 3–5 раз сильнее ожидаемого — '
              f'{"да" if 3 <= oe4 <= 5 else "нет"} ({fmt(oe4)}); у late=0 хвост <10 % оконных регистраций — '
              f'{"да" if ratio(tail0, regw0) < 0.1 else "нет"} ({fmt(100 * ratio(tail0, regw0), 1)} %); '
              f'поздний сайт 0,3–0,5 рег/100 — {"да" if 0.3 <= mb["y47"] <= 0.5 else "нет"} (по модели {fmt(mb["y47"], 2)}, ДИ '
              f'{fmt(100 * ratio(mb["ci47"][0] * T, sum(d["late47"] for d in A)), 2)}–{fmt(100 * ratio(mb["ci47"][1] * T, sum(d["late47"] for d in A)), 2)}; '
              f'наивно {fmt(100 * ratio(T, sum(d["late47"] for d in A)))}); трафик после окна 5–10 % оконного — '
              f'{"да" if 0.05 <= dens_ratio <= 0.10 else "нет"} ({fmt(100 * dens_ratio, 1)} %); конверсия 0,7–0,8 оконной — '
              f'{"да" if 0.7 <= conv_a / conv_w <= 0.8 else "нет"} ({fmt(conv_a / conv_w)}; в страте {fmt(obs_c)}).\n')
    out.write('7. Простыми словами.\n')
    out.write(f'   Хвост — это примерно каждая пятая регистрация ({fmt(100 * T / R, 0)} % у доменов старше {AGE_TAIL} суток). '
              f'Он почти не приходит на домены, где после 3-х суток ни один новый сайт не вышел в поиск: у {t["0"][0]} таких доменов '
              f'{t["0"][3]} хвостовых регистраций вместо {t["0"][4]:.0f} ожидаемых по их ранним выходам (O/E {fmt(oe0)}, p ≈ {p0:.3f}), '
              f'а если считать «поздним» любой выход после 3-х суток, включая после 7-х, то у доменов без поздних выходов хвоста нет совсем '
              f'({ta["0"][3]} при {ta["0"][4]:.1f} ожидаемых). Но дальше зависимость не растёт: домены с 1–3 поздними выходами получают хвост '
              f'{fmt(oe13)} от ожидаемого, с ≥4 — {fmt(oe4)}, то есть «в 3–5 раз сильнее» не выходит; хвост скорее «есть/нет», чем «чем больше '
              f'поздних, тем больше». В окне эти же домены не отличаются от соседей по пулу (O/E {fmt(coe0)} / {fmt(tc["1-3"][5])} / {fmt(coe4)}), '
              f'так что это не «домены получше». Модель долей относит хвост к поздним сайтам целиком (точечная оценка {fmt(100 * mb["tlate"], 0)} %, '
              f'ДИ {fmt(100 * mb["ci_late"][0], 0)}–{fmt(100 * mb["ci_late"][1], 0)} %; с «{NOCONTENT}» {fmt(100 * mbn["tlate"], 0)} %), '
              f'«дозреванию» ранних сайтов почти ничего не остаётся. По той же модели поздний сайт 4–7 суток даёт в хвосте порядка '
              f'{fmt(mb["y47"], 1)} рег/100 (ДИ {fmt(100 * ratio(mb["ci47"][0] * T, sum(d["late47"] for d in A)), 1)}–'
              f'{fmt(100 * ratio(mb["ci47"][1] * T, sum(d["late47"] for d in A)), 1)}; при возрасте ≥14 — {fmt(mb14["y47"], 1)}) против '
              f'{fmt(100 * ratio(RW, sum(d["early"] for d in A)), 2)} у раннего сайта в окне, то есть не хуже; но это расчёт по тому, как хвост '
              f'делится между доменами пула, а не прямой счёт по сайтам, и он не отличает «поздний сайт сам конвертирует» от «домен с поздними '
              f'выходами продолжает собирать трафик». Механизм, который виден прямо: у доменов с поздними выходами после окна в '
              f'{fmt(ratio(dens_after[">=4"], dens_after["0"]), 1)} раза больше поисковых кликов на сайто-сутки ({fmt(dens_after[">=4"], 1)} против '
              f'{fmt(dens_after["0"], 1)} на 100 у late=0; late 1–3 — {fmt(dens_after["1-3"], 1)}), а клик после окна конвертирует во всех группах '
              f'примерно как оконный ({fmt(conv_after["0"])} / {fmt(conv_after["1-3"])} / {fmt(conv_after[">=4"])} против {fmt(conv_win["0"])} / '
              f'{fmt(conv_win["1-3"])} / {fmt(conv_win[">=4"])} на 10 тыс.); если ждать хвост пропорционально кликам после окна, группы почти '
              f'выравниваются (O/E {fmt(tk["0"][5])} / {fmt(tk["1-3"][5])} / {fmt(tk[">=4"][5])}). Итого: поздние выходы → трафик после окна → хвост.\n')
    out.write(f'   После окна на сайто-сутки приходится {fmt(100 * dens_ratio, 0)} % оконного поискового трафика (падение в {fmt(1 / dens_ratio, 0)} раз, '
              f'во всех зонах ≤ {fmt(max(zone_dens.values()), 2)}), и клик после окна конвертирует {"не хуже" if conv_a / conv_w >= 0.9 else "хуже"} оконного '
              f'сырым счётом ({fmt(conv_a / conv_w)}, p = {p_worse:.2f}), а внутри пула — на четверть хуже ({fmt(obs_c)}, p = {p_c:.2f}; '
              f'с «{NOCONTENT}» {fmt(obs_cn)}, p = {p_cn:.3f}) — «на четверть хуже» держится только на пулах и на старых базах без записи контента. '
              f'«Второй жизни» в смысле нового подъёма трафика нет, но хвост не обрывается на 7-м дне: после 7-го дня приходит '
              f'{fmt(100 * ratio(old_8, old_tot), 0)} % регистраций доменов старше 21 суток ({old_8} из {old_tot}) и {fmt(100 * ratio(A_8, R), 0)} % '
              f'у доменов старше {AGE_TAIL} суток ({A_8} из {R}, хвост ещё не полный). Хвостовые регистрации депонируют так же, как оконные.\n')
    out.write('8. Что с этим делать.\n')
    out.write(f'   Рычага для роста здесь нет: хвост — это следствие поздних выходов, а поздние выходы, как и ранние, задаются брендом и набором '
              f'контента, а не действиями оператора. Но есть правило учёта: оценивать домен и набор контента на 3-й день можно только там, где '
              f'после 3-х суток новых сайтов в поиске не появилось; если появились (late47 ≥ 1 — это {t["1-3"][0] + t[">=4"][0]} из {res["n_dom"]} доменов), '
              f'к оконным регистрациям в среднем добавится ещё {fmt(100 * ratio(sum(d["tail"] for d in raw["1-3"]) + sum(d["tail"] for d in raw[">=4"]), sum(d["reg_w"] for d in raw["1-3"]) + sum(d["reg_w"] for d in raw[">=4"])), 0)} %, '
              f'у доменов без поздних выходов — {fmt(100 * ratio(tail0, regw0), 0)} %. Проверяемо на уже запущенных данных: пересчитать рейтинг '
              f'наборов контента по регистрациям за 7 суток вместо 3 и посмотреть, какие наборы меняют место, — по этому своду сдвиг должен быть '
              f'у наборов с большой долей поздних выходов. Про срок жизни домена: выключать его на 3-й день рано, если после 3-х суток у него '
              f'ещё выходят сайты — 4–7-й дни дают {fmt(100 * ratio(A_47, R), 0)} % регистраций ({A_47} из {R} у доменов старше {AGE_TAIL} суток; '
              f'{fmt(100 * ratio(old_47, old_tot), 0)} % у старше 21); после 7-го дня остаётся струйка в {fmt(100 * ratio(A_8, R), 0)}–'
              f'{fmt(100 * ratio(old_8, old_tot), 0)} % регистраций при трафике в {fmt(1 / dens_ratio, 0)} раз реже оконного на сайто-сутки — '
              f'стоит ли ради неё держать домен, свод не скажет: в нём нет цены жизни домена. Это знание про учёт, не рычаг роста.\n')
    out.flush()


if __name__ == '__main__':
    main()

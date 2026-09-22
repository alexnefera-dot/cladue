# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №14 («прочие» клики — тень активности домена; всплески — краулерная ловушка).
Угол: ТЕНИ (конфаундинг). Проверяем, переживает ли «денежный» сигнал
(O/E верх/низ 1,82 при выровненных поисковых) более жёсткую страту
(набор + день + зона [+ блок часа]) и парные сравнения внутри пула
с почти равным поисковым объёмом.

Только stdlib. Вывод дублируется в analysis/export/gipotezy_svod/w14_teni.txt
"""
import collections
import csv
import math
import os
import random
import sys

REPO = '/home/user/cladue'
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w14_teni.txt')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
THR_WINDOW = 5000
THR_TOTAL = 50000
NSIM = 4000


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)

    def close(self):
        self.f.close()


def iv(x):
    try:
        return int(float(str(x).replace(' ', '').replace(',', '.')))
    except Exception:
        return 0


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return '—'
    return f'{x:.{nd}f}'


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return float('nan')
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return float('nan')
    p = q * (len(xs) - 1)
    lo = int(math.floor(p))
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (p - lo)


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    if len(xs) < 3:
        return float('nan')
    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return num / (dx * dy) if dx and dy else float('nan')


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s, t = 0.0, math.exp(-lam)
    for i in range(int(k) + 1):
        if i:
            t *= lam / i
        s += t
    return min(1.0, s)


def poisson_ci(k, alpha=0.05):
    """Точный (Гарвуда) ДИ для пуассоновского среднего."""
    lo = 0.0 if k == 0 else _chi2_inv(alpha / 2, 2 * k) / 2
    hi = _chi2_inv(1 - alpha / 2, 2 * k + 2) / 2
    return lo, hi


def _chi2_inv(p, df):
    lo, hi = 0.0, max(1000.0, df * 10.0)
    for _ in range(200):
        mid = (lo + hi) / 2
        if _chi2_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _chi2_cdf(x, df):
    if x <= 0:
        return 0.0
    return _lower_gamma_reg(df / 2.0, x / 2.0)


def _lower_gamma_reg(a, x):
    if x < a + 1:
        s = 1.0 / a
        t = s
        n = 0
        while n < 1000:
            n += 1
            t *= x / (a + n)
            s += t
            if abs(t) < abs(s) * 1e-14:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # continued fraction для верхней неполной
    tiny = 1e-300
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b if b else 1 / tiny
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-14:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1 - q


def binom_two_sided(k, n, p=0.5):
    if n == 0:
        return float('nan')
    def pmf(i):
        return math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * math.log(p) + (n - i) * math.log(1 - p))
    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1) if pmf(i) <= obs * (1 + 1e-9)))


# ------------------------------------------------------------------ загрузка
def load():
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    for r in rows:
        r['_sw'] = iv(r['кликов из поиска в окне'])
        r['_tw'] = iv(r['кликов всего в окне'])
        r['_bw'] = iv(r['ботов в окне'])
        ow = r['_tw'] - r['_sw'] - r['_bw']
        r['_ow'] = max(0, ow)
        r['_ot'] = iv(r['прочих'])
        r['_sites'] = iv(r['сайтов в окне']) or iv(r['сайтов'])
        r['_reg'] = iv(r['регистраций в окне 3 суток'])
        r['_fd'] = iv(r['ФД в окне 3 суток'])
        r['_ex3'] = iv(r['вышли за 3 суток'])
        r['_ops'] = r['_ow'] / r['_sites'] if r['_sites'] else 0.0
        r['_exs'] = r['_ex3'] / r['_sites'] if r['_sites'] else 0.0
        r['_bps'] = r['_bw'] / r['_sites'] if r['_sites'] else 0.0
        r['_mes'] = r['день запуска'][:7]
        r['_pool'] = (r['набор контента'], r['день запуска'])
        r['_poolz'] = (r['набор контента'], r['день запуска'], r['зона'])
        r['_poolzh'] = (r['набор контента'], r['день запуска'], r['зона'], r['блок часа'])
    outl = {r['домен'] for r in rows if r['_ow'] > THR_WINDOW or r['_ot'] > THR_TOTAL}
    closed = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1']
    base_all = [r for r in closed if r['домен'] not in outl]
    base = [r for r in base_all if r['набор контента'] != NOCONTENT]
    return rows, outl, base, base_all


# ------------------------------------------------------------------ страты
def sub_terciles(doms, pool_key, key, min_pool=9):
    """Разбивает пулы на терцили по key -> новая метка страты (пул, t)."""
    by = collections.defaultdict(list)
    for d in doms:
        by[d[pool_key]].append(d)
    lab = {}
    for p, ds in by.items():
        if len(ds) < min_pool:
            continue
        order = sorted(ds, key=lambda d: (key(d), d['домен']))
        n = len(order)
        for i, d in enumerate(order):
            lab[d['домен']] = (p, min(2, (3 * i) // n))
    return lab


def tercile_oe(doms, strat_of, key, name, out, rng, min_str=3, nsim=NSIM):
    by = collections.defaultdict(list)
    for d in doms:
        s = strat_of.get(d['домен'])
        if s is not None:
            by[s].append(d)
    strata = {s: ds for s, ds in by.items() if len(ds) >= min_str}
    used = [d for ds in strata.values() for d in ds]
    if not used:
        out.write(f'\n  {name}: пусто\n')
        return None
    rate = {}
    for s, ds in strata.items():
        sw = sum(d['_sw'] for d in ds)
        rate[s] = (sum(d['_reg'] for d in ds) / sw) if sw else 0.0
    lab = {}
    for s, ds in strata.items():
        order = sorted(ds, key=lambda d: (key(d), d['домен']))
        n = len(order)
        for i, d in enumerate(order):
            lab[d['домен']] = min(2, (3 * i) // n)
    strat_by_dom = {d['домен']: s for s, ds in strata.items() for d in ds}

    def acc_of(labels):
        a = {t: collections.Counter() for t in range(3)}
        for d in used:
            t = labels[d['домен']]
            a[t]['n'] += 1
            a[t]['reg'] += d['_reg']
            a[t]['sw'] += d['_sw']
            a[t]['ow'] += d['_ow']
            a[t]['sites'] += d['_sites']
            a[t]['E'] += rate[strat_by_dom[d['домен']]] * d['_sw']
        return a

    a = acc_of(lab)
    out.write(f'\n  {name}\n')
    out.write(f'    страт: {len(strata)}; доменов: {len(used)}; рег: {sum(d["_reg"] for d in used)}; '
              f'поисковых в окне: {sum(d["_sw"] for d in used)}\n')
    out.write(f'    {"терциль":<9}{"дом.":>6}{"поисковых":>11}{"прочих":>9}{"рег":>5}{"E":>8}{"O/E":>7}{"рег/10тыс":>11}\n')
    nm = ('нижний', 'средний', 'верхний')
    for t in range(3):
        c = a[t]
        oe = c['reg'] / c['E'] if c['E'] else float('nan')
        out.write(f'    {nm[t]:<9}{c["n"]:>6}{c["sw"]:>11}{c["ow"]:>9}{c["reg"]:>5}{c["E"]:>8.1f}{fmt(oe):>7}'
                  f'{fmt(1e4*c["reg"]/c["sw"] if c["sw"] else float("nan"),1):>11}\n')

    def stat(a):
        if not a[2]['E'] or not a[0]['E']:
            return float('nan')
        bot = a[0]['reg'] / a[0]['E']
        top = a[2]['reg'] / a[2]['E']
        return top / bot if bot > 0 else float('inf')

    obs = stat(a)
    ge = two = valid = 0
    sl = list(strata.values())
    for _ in range(nsim):
        lb = {}
        for ds in sl:
            names = [d['домен'] for d in ds]
            tl = [lab[x] for x in names]
            rng.shuffle(tl)
            lb.update(dict(zip(names, tl)))
        r = stat(acc_of(lb))
        if isinstance(r, float) and math.isnan(r):
            continue
        valid += 1
        if r >= obs:
            ge += 1
        if math.isinf(r) or r == 0 or obs <= 0 or math.isinf(obs):
            two += 1
        elif abs(math.log(r)) >= abs(math.log(obs)):
            two += 1
    p_ge = ge / valid if valid else float('nan')
    p_two = two / valid if valid else float('nan')
    out.write(f'    O/E верх/низ = {fmt(obs)}; перестановок {valid}: p(одност.) = {fmt(p_ge,3)}, p(двуст.) = {fmt(p_two,3)}\n')
    return {'ratio': obs, 'p_two': p_two, 'p_ge': p_ge, 'acc': a, 'used': used,
            'strata': strata, 'lab': lab, 'rate': rate, 'strat_by_dom': strat_by_dom}


# ------------------------------------------------------------------ пары
def make_pairs(doms, pool_key, ratio_max, rng, key=lambda d: d['_ops']):
    """Непересекающиеся пары внутри пула с близкими поисковыми кликами."""
    by = collections.defaultdict(list)
    for d in doms:
        if d['_sw'] > 0:
            by[d[pool_key]].append(d)
    pairs = []
    for p, ds in by.items():
        if len(ds) < 2:
            continue
        ds = sorted(ds, key=lambda d: (d['_sw'], d['домен']))
        used = set()
        # жадно: ближайший по поисковым сосед
        cand = []
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                r = ds[j]['_sw'] / ds[i]['_sw']
                if r > ratio_max:
                    break
                cand.append((r, i, j))
        cand.sort(key=lambda t: (t[0], ds[t[1]]['домен'], ds[t[2]]['домен']))
        for r, i, j in cand:
            if i in used or j in used:
                continue
            a, b = ds[i], ds[j]
            ka, kb = key(a), key(b)
            if ka == kb:
                continue
            hi, lo = (a, b) if ka > kb else (b, a)
            pairs.append((hi, lo))
            used.add(i)
            used.add(j)
    return pairs


def make_pairs2(doms, pool_key, ratio_max, rng, key, match2=None, m2_tol=0.25):
    """Пары внутри пула: поисковые в пределах ratio_max раз И (опц.) второй признак в пределах m2_tol
    относительной разности; «верх» — больший по key."""
    by = collections.defaultdict(list)
    for d in doms:
        if d['_sw'] > 0:
            by[d[pool_key]].append(d)
    pairs = []
    for p, ds in by.items():
        if len(ds) < 2:
            continue
        ds = sorted(ds, key=lambda d: (d['_sw'], d['домен']))
        used = set()
        cand = []
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                r = ds[j]['_sw'] / ds[i]['_sw']
                if r > ratio_max:
                    break
                if match2 is not None:
                    a, b = match2(ds[i]), match2(ds[j])
                    m = max(abs(a), abs(b))
                    if m > 0 and abs(a - b) / m > m2_tol:
                        continue
                cand.append((r, i, j))
        cand.sort(key=lambda t: (t[0], ds[t[1]]['домен'], ds[t[2]]['домен']))
        for r, i, j in cand:
            if i in used or j in used:
                continue
            a, b = ds[i], ds[j]
            ka, kb = key(a), key(b)
            if ka == kb:
                continue
            hi, lo = (a, b) if ka > kb else (b, a)
            pairs.append((hi, lo))
            used.add(i)
            used.add(j)
    return pairs


def pair_report(pairs, name, out, rng, nsim=20000):
    if not pairs:
        out.write(f'\n  {name}: пар нет\n')
        return
    rh = sum(h['_reg'] for h, l in pairs)
    rl = sum(l['_reg'] for h, l in pairs)
    swh = sum(h['_sw'] for h, l in pairs)
    swl = sum(l['_sw'] for h, l in pairs)
    owh = sum(h['_ow'] for h, l in pairs)
    owl = sum(l['_ow'] for h, l in pairs)
    win = sum(1 for h, l in pairs if h['_reg'] > l['_reg'])
    loss = sum(1 for h, l in pairs if h['_reg'] < l['_reg'])
    disc = win + loss
    pb = binom_two_sided(win, disc) if disc else float('nan')
    obs = rh - rl
    ge = two = 0
    for _ in range(nsim):
        s = 0
        for h, l in pairs:
            if rng.random() < 0.5:
                s += h['_reg'] - l['_reg']
            else:
                s += l['_reg'] - h['_reg']
        if s >= obs:
            ge += 1
        if abs(s) >= abs(obs):
            two += 1
    # отношение «рег на поисковый клик»
    r10h = 1e4 * rh / swh if swh else float('nan')
    r10l = 1e4 * rl / swl if swl else float('nan')
    ratio = (r10h / r10l) if r10l else float('nan')
    out.write(f'\n  {name}\n')
    out.write(f'    пар: {len(pairs)}; поисковых в паре: Σ верх {swh}, Σ низ {swl} (баланс {fmt(swh/swl if swl else float("nan"))}×); '
              f'прочих: Σ верх {owh}, Σ низ {owl} ({fmt(owh/owl if owl else float("nan"))}×)\n')
    out.write(f'    регистраций: верх «прочих» {rh}, низ {rl} (разность {obs:+d}); '
              f'рег/10 тыс. поисковых: {fmt(r10h,2)} против {fmt(r10l,2)} — отношение {fmt(ratio)}\n')
    out.write(f'    пар с разным исходом: {disc} (верх выиграл {win}, низ {loss}); точный биномиальный p(двуст.) = {fmt(pb,3)}\n')
    out.write(f'    перестановка знаков внутри пар ({nsim}): p(одност.) = {fmt(ge/nsim,3)}, p(двуст.) = {fmt(two/nsim,3)}\n')


# ------------------------------------------------------------------ main
def main():
    out = Tee(OUT)
    rng = random.Random(20260922)
    rows, outl, base, base_all = load()
    out.write('КОНТРПРОВЕРКА №14 — УГОЛ «ТЕНИ» (конфаундинг)\n')
    out.write(f'Источник: {SRC}; строк {len(rows)}\n')
    out.write(f'Выбросы (исключены): {sorted(outl)}\n')
    out.write(f'Фон (окно закрыто, дней≠1, без выбросов): {len(base)} доменов без «не записан», '
              f'{len(base_all)} с ним; рег в окне {sum(r["_reg"] for r in base)} / {sum(r["_reg"] for r in base_all)}\n')

    # -------------------------------------------------- 0. чем является «прочих на сайт»
    out.write('\n' + '=' * 78 + '\n0. ЧТО ТАКОЕ ПРИЗНАК «ПРОЧИХ НА САЙТ»\n' + '=' * 78 + '\n')
    cnt_sites = collections.Counter(r['_sites'] for r in base)
    top = cnt_sites.most_common(4)
    out.write(f'  «сайтов в окне»: {len(base)} доменов, самые частые значения {top}; '
              f'доля с 206 сайтами {fmt(100*cnt_sites[206]/len(base),1)} %\n')
    rho = spearman([r['_ops'] for r in base], [r['_ow'] for r in base])
    out.write(f'  Спирмен «прочих на сайт» ↔ «прочих в окне» (сырых) = {fmt(rho,3)} — знаменатель почти константа, '
              f'терциль «на сайт» = терциль сырых «прочих»\n')
    out.write(f'  Спирмен «прочих в окне» ↔ «ботов в окне» = {fmt(spearman([r["_ow"] for r in base],[r["_bw"] for r in base]),3)}; '
              f'↔ «кликов всего в окне» = {fmt(spearman([r["_ow"] for r in base],[r["_tw"] for r in base]),3)}; '
              f'↔ «поисковых в окне» = {fmt(spearman([r["_ow"] for r in base],[r["_sw"] for r in base]),3)}\n')
    out.write('  («прочие в окне» = всего − поиск − боты: это остаток трёх колонок, а не отдельный замер)\n')

    aug = [r for r in base if r['_mes'] == '2026-08']
    sep = [r for r in base if r['_mes'] == '2026-09']
    out.write(f'  период: август {len(aug)} доменов, медиана «прочих на сайт» {fmt(median([r["_ops"] for r in aug]),3)}; '
              f'сентябрь {len(sep)} доменов, {fmt(median([r["_ops"] for r in sep]),3)}\n')
    nz = [r for r in base_all if r['набор контента'] == NOCONTENT]
    out.write(f'  «{NOCONTENT}»: {len(nz)} доменов, медиана «прочих на сайт» {fmt(median([r["_ops"] for r in nz]),3)}, '
              f'рег в окне {sum(r["_reg"] for r in nz)} на {sum(r["_sw"] for r in nz)} поисковых '
              f'({fmt(1e4*sum(r["_reg"] for r in nz)/max(1,sum(r["_sw"] for r in nz)),2)} рег/10 тыс.)\n')
    out.write(f'  записанный контент: {len(base)} доменов, {sum(r["_reg"] for r in base)} рег на {sum(r["_sw"] for r in base)} поисковых '
              f'({fmt(1e4*sum(r["_reg"] for r in base)/max(1,sum(r["_sw"] for r in base)),2)} рег/10 тыс.)\n')

    # -------------------------------------------------- 1. воспроизведение Б9
    out.write('\n' + '=' * 78 + '\n1. ВОСПРОИЗВЕДЕНИЕ ЭФФЕКТА (страта = «набор+день» × терциль поисковых)\n' + '=' * 78 + '\n')
    lab_pool_sw = sub_terciles(base, '_pool', lambda d: d['_sw'], min_pool=9)
    r_base = tercile_oe(base, lab_pool_sw, lambda d: d['_ops'], 'терцили «прочих на сайт» — как у тестировщика (Б9)', out, rng)

    # разброс поисковых внутри страт
    if r_base:
        rr = []
        for s, ds in r_base['strata'].items():
            sw = [d['_sw'] for d in ds if d['_sw'] > 0]
            if len(sw) >= 2 and min(sw) > 0:
                rr.append(max(sw) / min(sw))
        out.write(f'    остаточный разброс поисковых внутри страт: медиана макс/мин {fmt(median(rr))}×, '
                  f'кв3 {fmt(quantile(rr,.75))}×, макс {fmt(max(rr))}×\n')
        # средние поисковые по терцилям
        a = r_base['acc']
        out.write(f'    поисковых на домен по терцилям: {a[0]["sw"]//max(1,a[0]["n"])} / {a[1]["sw"]//max(1,a[1]["n"])} / '
                  f'{a[2]["sw"]//max(1,a[2]["n"])} — выравнивание неполное\n')

    # -------------------------------------------------- 2. жёсткая страта
    out.write('\n' + '=' * 78 + '\n2. БОЛЕЕ ЖЁСТКАЯ СТРАТА: + ЗОНА, + БЛОК ЧАСА\n' + '=' * 78 + '\n')
    out.write('  Пулы здесь — «набор+день+зона» (и +блок часа), внутри пула терциль поисковых → страта.\n')
    for pk, ttl, mp in (('_poolz', 'набор+день+ЗОНА × терциль поисковых', 9),
                        ('_poolz', 'набор+день+ЗОНА × терциль поисковых (пулы ≥6)', 6),
                        ('_poolzh', 'набор+день+зона+БЛОК ЧАСА × терциль поисковых (пулы ≥6)', 6)):
        lb = sub_terciles(base, pk, lambda d: d['_sw'], min_pool=mp)
        tercile_oe(base, lb, lambda d: d['_ops'], ttl, out, rng)

    out.write('\n  Без под-терциля поисковых (сырая жёсткая страта — сам пул):\n')
    for pk, ttl in (('_pool', 'страта = набор+день (пулы ≥3)'),
                    ('_poolz', 'страта = набор+день+ЗОНА (пулы ≥3)'),
                    ('_poolzh', 'страта = набор+день+зона+БЛОК ЧАСА (пулы ≥3)')):
        strat = {d['домен']: d[pk] for d in base}
        tercile_oe(base, strat, lambda d: d['_ops'], ttl, out, rng)

    # -------------------------------------------------- 3. период / не записан
    out.write('\n' + '=' * 78 + '\n3. ПЕРИОД И «КОНТЕНТ НЕ ЗАПИСАН»\n' + '=' * 78 + '\n')
    lb_all = sub_terciles(base_all, '_pool', lambda d: d['_sw'], min_pool=9)
    tercile_oe(base_all, lb_all, lambda d: d['_ops'], 'с «не записан» как собственной стратой (весь фон)', out, rng)
    for sub, ttl in ((sep, 'только СЕНТЯБРЬ (записанный контент)'), (aug, 'только АВГУСТ (записанный контент)')):
        lb = sub_terciles(sub, '_pool', lambda d: d['_sw'], min_pool=9)
        tercile_oe(sub, lb, lambda d: d['_ops'], ttl, out, rng)

    # -------------------------------------------------- 4. пары
    out.write('\n' + '=' * 78 + '\n4. ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ ПУЛА ПРИ ПОЧТИ РАВНЫХ ПОИСКОВЫХ\n' + '=' * 78 + '\n')
    out.write('  Пара = два домена одного пула, поисковые клики в окне отличаются не более чем в R раз;\n'
              '  «верх» — тот, у кого больше «прочих на сайт». E не нужен: объём уравнен конструкцией.\n')
    for pk, pname in (('_pool', 'набор+день'), ('_poolz', 'набор+день+зона')):
        for R in (1.25, 1.5, 2.0):
            pr = make_pairs(base, pk, R, rng)
            pair_report(pr, f'пул «{pname}», поисковые в пределах {R}×', out, rng)

    out.write('\n  То же на всём фоне с «не записан» (пул «набор+день», «не записан» — свой пул):\n')
    for R in (1.25, 1.5):
        pr = make_pairs(base_all, '_pool', R, rng)
        pair_report(pr, f'весь фон, поисковые в пределах {R}×', out, rng)

    out.write('\n  Контроль-подмена: тот же парный тест, но «верх» — по широте выхода (вышли/сайтов):\n')
    for R in (1.25, 1.5):
        pr = make_pairs(base, '_pool', R, rng, key=lambda d: d['_exs'])
        pair_report(pr, f'ключ = широта выхода, поисковые в пределах {R}×', out, rng)

    out.write('\n  Контроль-подмена: «верх» — по ботам на сайт:\n')
    pr = make_pairs(base, '_pool', 1.5, rng, key=lambda d: d['_bps'])
    pair_report(pr, 'ключ = боты на сайт, поисковые в пределах 1.5×', out, rng)


    # -------------------------------------------------- 4б. двойное сопоставление
    out.write('\n' + '=' * 78 + '\n4б. ДВОЙНОЕ СОПОСТАВЛЕНИЕ: ПОИСКОВЫЕ + ШИРОТА ВЫХОДА\n' + '=' * 78 + '\n')
    out.write('  Пара = один пул, поисковые в пределах 1,5× И широта выхода (вышли/сайтов) в пределах ±25 %.\n'
              '  Если «прочие» — самостоятельный признак, разница останется; если тень выхода — исчезнет.\n')
    for pk, pname in (('_pool', 'набор+день'), ('_poolz', 'набор+день+зона')):
        pr = make_pairs2(base, pk, 1.5, rng, key=lambda d: d['_ops'], match2=lambda d: d['_exs'])
        pair_report(pr, f'пул «{pname}»: ключ «прочие», выход уравнен ±25 %', out, rng)
    pr = make_pairs2(base_all, '_pool', 1.5, rng, key=lambda d: d['_ops'], match2=lambda d: d['_exs'])
    pair_report(pr, 'весь фон (с «не записан»): ключ «прочие», выход уравнен ±25 %', out, rng)

    out.write('\n  Зеркало: ключ — широта выхода, «прочие на сайт» уравнены ±25 %:\n')
    pr = make_pairs2(base, '_pool', 1.5, rng, key=lambda d: d['_exs'], match2=lambda d: d['_ops'])
    pair_report(pr, 'пул «набор+день»: ключ «выход», прочие уравнены ±25 %', out, rng)
    pr = make_pairs2(base_all, '_pool', 1.5, rng, key=lambda d: d['_exs'], match2=lambda d: d['_ops'])
    pair_report(pr, 'весь фон (с «не записан»): ключ «выход», прочие уравнены ±25 %', out, rng)

    # -------------------------------------------------- 4в. откуда значимость «всего фона»
    out.write('\n' + '=' * 78 + '\n4в. ОТКУДА ЗНАЧИМОСТЬ НА «ВСЁМ ФОНЕ»: «НЕ ЗАПИСАН» ОТДЕЛЬНО\n' + '=' * 78 + '\n')
    only_nz = [r for r in base_all if r['набор контента'] == NOCONTENT]
    for R in (1.25, 1.5):
        pair_report(make_pairs(only_nz, '_pool', R, rng), f'ТОЛЬКО «не записан» (август), поисковые в пределах {R}×', out, rng)
        pair_report(make_pairs(base, '_pool', R, rng), f'ТОЛЬКО записанный контент, поисковые в пределах {R}×', out, rng)
    out.write('\n  Контроль на «всём фоне»: ключ — широта выхода (для сравнения силы признаков):\n')
    pair_report(make_pairs(base_all, '_pool', 1.25, rng, key=lambda d: d['_exs']), 'весь фон, ключ = широта выхода, 1.25×', out, rng)

    # -------------------------------------------------- 5. влияние отдельных доменов
    out.write('\n' + '=' * 78 + '\n5. НА ЧЁМ ДЕРЖИТСЯ ЭФФЕКТ: ВКЛАД ОТДЕЛЬНЫХ ДОМЕНОВ И СТРАТ\n' + '=' * 78 + '\n')
    if r_base:
        used = r_base['used']
        lab = r_base['lab']
        rate = r_base['rate']
        sbd = r_base['strat_by_dom']
        tops = [d for d in used if lab[d['домен']] == 2 and d['_reg'] > 0]
        tops.sort(key=lambda d: -d['_reg'])
        out.write(f'  В верхнем терциле {sum(1 for d in used if lab[d["домен"]]==2)} доменов, '
                  f'{sum(d["_reg"] for d in tops)} рег. распределены по {len(tops)} доменам:\n')
        for d in tops[:10]:
            e = rate[sbd[d['домен']]] * d['_sw']
            out.write(f'    {d["домен"]:<14} рег {d["_reg"]}, поисковых {d["_sw"]:>6}, прочих {d["_ow"]:>5}, E {fmt(e)}, '
                      f'зона {d["зона"]}, день {d["день запуска"]}, набор «{d["набор контента"]}»\n')
        out.write(f'    доля рег. верхнего терциля из 3 самых «урожайных» доменов: '
                  f'{fmt(100*sum(d["_reg"] for d in tops[:3])/max(1,sum(d["_reg"] for d in tops)),1)} %\n')

        def ratio_without(drop):
            a = {t: collections.Counter() for t in range(3)}
            for d in used:
                if d['домен'] in drop:
                    continue
                t = lab[d['домен']]
                a[t]['reg'] += d['_reg']
                a[t]['E'] += rate[sbd[d['домен']]] * d['_sw']
            if not a[0]['E'] or not a[2]['E'] or a[0]['reg'] == 0:
                return float('nan')
            return (a[2]['reg'] / a[2]['E']) / (a[0]['reg'] / a[0]['E'])

        for k in (1, 2, 3, 5):
            drop = {d['домен'] for d in tops[:k]}
            out.write(f'    без {k} самых «урожайных» доменов верхнего терциля: O/E верх/низ = {fmt(ratio_without(drop))}\n')
        # jackknife по стратам
        jk = []
        for s, ds in r_base['strata'].items():
            jk.append((ratio_without({d['домен'] for d in ds}), s))
        jk = [(v, s) for v, s in jk if not math.isnan(v)]
        jk.sort()
        out.write(f'    jackknife по стратам ({len(jk)}): O/E верх/низ от {fmt(jk[0][0])} до {fmt(jk[-1][0])}, '
                  f'медиана {fmt(median([v for v,_ in jk]))}\n')
        out.write(f'      самая влиятельная страта (без неё минимум): {jk[0][1]}\n')

    # -------------------------------------------------- 6. нелинейность объёма
    out.write('\n' + '=' * 78 + '\n6. ЛИНЕЙНАЯ ЛИ E: РЕГИСТРАЦИИ ПРОТИВ ПОИСКОВОГО ОБЪЁМА\n' + '=' * 78 + '\n')
    dec = sorted(base, key=lambda d: d['_sw'])
    n = len(dec)
    out.write(f'  {"децили поисковых":<20}{"дом.":>6}{"Σпоисковых":>12}{"рег":>6}{"рег/10тыс":>11}{"медиана прочих":>16}\n')
    for i in range(10):
        g = dec[i * n // 10:(i + 1) * n // 10]
        sw = sum(d['_sw'] for d in g)
        rg = sum(d['_reg'] for d in g)
        out.write(f'  дециль {i+1:<13}{len(g):>6}{sw:>12}{rg:>6}'
                  f'{fmt(1e4*rg/sw if sw else float("nan"),2):>11}{fmt(median([d["_ow"] for d in g]),0):>16}\n')
    out.write('  E = ставка страты × поисковые клики предполагает линейность; если рег/10 тыс. падает с объёмом,\n'
              '  E завышена у крупных и занижена у мелких — это сдвигает O/E по любому признаку, коррелирующему с объёмом.\n')

    # -------------------------------------------------- 7. всплески
    out.write('\n' + '=' * 78 + '\n7. ВСПЛЕСКИ: ДЕНЬГИ\n' + '=' * 78 + '\n')
    spikes = [r for r in rows if r['домен'] in outl]
    tot_o = sum(r['_reg'] for r in spikes)
    tot_sw = sum(r['_sw'] for r in spikes)
    # E по ставке соседей «набор+день» (без самого выброса), фон = все закрытые не-выбросы
    pool_stats = collections.defaultdict(lambda: [0, 0])
    for r in base_all:
        pool_stats[r['_pool']][0] += r['_reg']
        pool_stats[r['_pool']][1] += r['_sw']
    E = 0.0
    out.write(f'  {"домен":<12}{"рег":>5}{"поисковых":>11}{"E(соседи набор+день)":>22}\n')
    for r in spikes:
        rg, sw = pool_stats[r['_pool']]
        e = (rg / sw * r['_sw']) if sw else 0.0
        E += e
        out.write(f'  {r["домен"]:<12}{r["_reg"]:>5}{r["_sw"]:>11}{fmt(e):>22}\n')
    lo, hi = poisson_ci(tot_o)
    out.write(f'  Σ: O = {tot_o} на {tot_sw} поисковых, E = {fmt(E)}, O/E = {fmt(tot_o/E if E else float("nan"))} '
              f'[точный ДИ O/E {fmt(lo/E if E else float("nan"))}–{fmt(hi/E if E else float("nan"))}]\n')
    p2 = 2 * min(poisson_cdf(tot_o, E), 1 - poisson_cdf(tot_o - 1, E))
    out.write(f'  p(двуст., пуассон) = {fmt(min(1.0,p2),3)} — согласуется с O/E = 1\n')
    # без 4863 (у него аномальный поиск)
    sp2 = [r for r in spikes if r['домен'] != '4863.team']
    o2 = sum(r['_reg'] for r in sp2)
    e2 = 0.0
    for r in sp2:
        rg, sw = pool_stats[r['_pool']]
        e2 += (rg / sw * r['_sw']) if sw else 0.0
    lo2, hi2 = poisson_ci(o2)
    out.write(f'  без 4863.team (его поисковый поток сам аномален): O = {o2}, E = {fmt(e2)}, '
              f'O/E = {fmt(o2/e2 if e2 else float("nan"))} [ДИ {fmt(lo2/e2 if e2 else float("nan"))}–{fmt(hi2/e2 if e2 else float("nan"))}]\n')

    # -------------------------------------------------- 8. фон: постоянная добавка?
    out.write('\n' + '=' * 78 + '\n8. «ПОСТОЯННАЯ ДОБАВКА НА ДОМЕН» — ПРОВЕРКА\n' + '=' * 78 + '\n')
    byday = collections.defaultdict(list)
    for r in base:
        byday[r['день запуска']].append(r)
    ks = []
    for day, ds in sorted(byday.items()):
        if len(ds) < 10:
            continue
        s_ow = sum(d['_ow'] for d in ds)
        s_si = sum(d['_sites'] for d in ds)
        ks.append(s_ow / s_si)
    mk = sum(ks) / len(ks)
    sd = math.sqrt(sum((k - mk) ** 2 for k in ks) / (len(ks) - 1))
    out.write(f'  дней с ≥10 доменами: {len(ks)}; «прочих на сайт» по дням от {fmt(min(ks),3)} до {fmt(max(ks),3)}, '
              f'среднее {fmt(mk,3)}, CV {fmt(sd/mk,2)} — разброс 5,1× между днями, «константой» это не является\n')
    # внутридневной разброс
    cvs = []
    for day, ds in byday.items():
        if len(ds) < 10:
            continue
        v = [d['_ops'] for d in ds]
        m = sum(v) / len(v)
        if m:
            cvs.append(math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)) / m)
    out.write(f'  внутри дня CV «прочих на сайт»: медиана {fmt(median(cvs),2)} — разброс внутри дня того же порядка, '
              f'что и между днями\n')

    # -------------------------------------------------- ВЫВОД
    out.write('\n' + '=' * 78 + '\nВЫВОД КОНТРПРОВЕРКИ\n' + '=' * 78 + '\n')
    out.write("""  1. Признак «прочих на сайт» — это ранг сырых «прочих» (ρ = 1,000: 98,6 % доменов имеют ровно 206 сайтов),
     а сами «прочие в окне» — остаток «всего − поиск − боты», связанный с ботами (ρ 0,58) и общим объёмом (ρ 0,67).
  2. Денежный эффект держится на страте «набор + день». Достаточно добавить ЗОНУ, и он рассыпается:
     1,85 (p 0,021) -> 1,46 (p 0,29) при «набор+день+зона × терциль поисковых»; монотонность рвётся
     (O/E 0,67 / 1,39 / 0,98 — максимум у среднего терциля). Пулы ≥6: 1,55 (p 0,17); +блок часа: 1,61 (p 0,18).
     Без под-терциля поисковых: 1,32 (p 0,16) -> 1,20 (p 0,38) -> 1,14 (p 0,49) по мере ужесточения страты.
     O/E верхнего терциля в жёстких стратах: 0,98 [0,52–1,68], 1,14 [0,69–1,76], 1,23 [0,72–1,97] — все накрывают 1.
  3. Парные сравнения при поисковых, выровненных до 1 %: 1,68 (p 0,071) при допуске 1,25×, 1,34 (p 0,22) при 1,5×,
     1,22 (p 0,32) при 2,0×. Эффект УБЫВАЕТ с ростом числа пар — подпись шума, а не сигнала.
  4. Подмена признака: тот же парный тест по ШИРОТЕ ВЫХОДА даёт больше и значимо — 1,89 (p 0,027) при 1,25×
     и 1,83 (p 0,010; биномиальный 0,030) при 1,5×; по ботам — 1,13 (p 0,66). При выровненном выходе «прочие»
     падают до 1,42 (p 0,24); при выровненных «прочих» выход держит 1,52. Деньги метит выход, «прочие» — его тень.
  5. Значимость «на всём фоне» (1,70, p 0,007) — сумма двух незначимых половин: «не записан» (август) 1,73 (p 0,062)
     и записанный контент 1,68 (p 0,071); объединяет их только сцепка «нет записи ⇔ август» (1,61 против 2,22 рег/10 тыс.).
  6. Всплески по деньгам: O = 5 при E = 2,55, O/E 1,96 [0,64–4,58], p 0,23; без 4863.team — O/E 1,45 [0,18–5,22].
  7. «Постоянная добавка на домен» не постоянна: по дням 0,179–0,921 «прочих на сайт» (5,1×, CV 0,39),
     внутри дня CV 0,48 — разброс внутри дня того же порядка, что между днями.
""")
    out.close()


if __name__ == '__main__':
    main()

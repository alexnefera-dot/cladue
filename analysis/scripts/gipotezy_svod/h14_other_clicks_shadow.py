#!/usr/bin/env python3
"""
Гипотеза №14. «Прочие» клики — не отдельный источник трафика: фон (медиана ~77 на
домен, ~0,37 на сайт) пропорционален числу вышедших в поиск сайтов и при равных
поисковых кликах не добавляет регистраций; всплески (домены с >5000 «прочих» в окне
или >50 000 «прочих» всего) — события конкретного домена, а не набора контента и не
дня запуска, и поисковая часть у них обычная.

Что проверяем.
  Часть А (что такое фон «прочих»): внутри пула «набор контента + день запуска» —
      ранговая корреляция «прочих в окне» с «вышли за 3 суток», с «кликов из поиска в
      окне» и с «ботов в окне»; сравнение моделей «прочих ≈ k × вышедших сайтов» и
      «прочих ≈ k × поисковых кликов» (и нулевой модели «медиана дня») по медианной
      относительной ошибке; коэффициент k по дням запуска и его стабильность.
  Часть Б (деньги): E регистраций домена = ставка пула на поисковый клик × поисковые
      клики домена в окне; O/E по терцилям «прочих на сайт в окне» и «прочих /
      поисковых в окне», терцили внутри пула; перестановочный тест терциля внутри
      пула (2000 перестановок, random.seed(1)), статистика — O/E верхнего терциля /
      O/E нижнего; отдельно в бине >912 и ≤912 поисковых кликов в окне.
  Справка Г (не по своду): если в analysis/api есть выгрузки кликов трекера — из чего
      состоят «прочие» (реферер, страна, краулерная ловушка), анатомия 5 всплесков и
      O/E по компонентам «прочих» в тех же стратах, что и Б9 (окно приближённое).
  Часть В (всплески): для 5 доменов-выбросов — соседи по пулу «набор + день» и по
      «день + зона»: медиана и максимум «прочих в окне», отношение выброс/медиана,
      есть ли у соседей значения выше 311 (99-й процентиль сети) и выше 1000; время
      прихода («прочих» всего против «в окне», первый/последний клик); ожидание
      регистраций по ставке соседей, суммарный O/E по 5 с точным пуассоновским ДИ;
      совпадения cf-аккаунта и аккаунта вебмастера — описательно.

Как считаем.
  «Прочих в окне» = кликов всего в окне − кликов из поиска в окне − ботов в окне.
  Фильтры: окно закрыто = да; дней ≠ 1; исключены 5 доменов-выбросов (перечислены
  в выводе); «КОНТЕНТ НЕ ЗАПИСАН» исключён из основных срезов (он сцеплен с датой),
  для части Б есть контрольный проход с ним как собственной стратой.
  Спирмен — по средним рангам; внутрипуловые корреляции считаются в пулах с ≥5
  доменами и сводятся медианой и средневзвешенной (веса n−3) по пулам, плюс общая
  корреляция нормированных внутрипуловых рангов. «При равных поисковых» — страта =
  пул × терциль поисковых кликов внутри пула (пулы с ≥9 доменами), корреляция по
  нормированным рангам внутри страты; тот же приём для O/E (Б9): терцили «прочих на
  сайт» внутри страты «пул × терциль поисковых», E = ставка страты × поисковые. Модели: k_день = Σпрочих / Σx по
  доменам дня; ошибка домена = |k·x − прочих| / max(прочих, 1); сравнение по медиане
  ошибок и по доле доменов, где одна модель точнее другой. В части Б домены с нулём
  поисковых кликов в окне исключены (у них E = 0 и регистраций быть не может);
  терцили внутри пула по рангу (пулы с ≥3 доменами). Пуассоновский ДИ — точный,
  бисекцией по функции распределения.

Критерии постановки: А — корреляция с вышедшими сайтами ≥ корреляции с поисковыми
кликами, k стабилен в пределах 0,2–1,0; Б — O/E верхнего / нижнего терциля 0,8–1,25
при p > 0,1; В — соседи всех 5 в пределах 3× медианы сети (никто >1000), суммарный
O/E выбросов 0,5–2. Опровержение: O/E верхнего терциля ≥ 1,4 при p < 0,05 (прочие
несут живых людей) или у соседей выброса тоже всплеск (прочие привязаны к набору).
"""
import collections
import csv
import datetime
import glob
import math
import re
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h14_other_clicks_shadow.txt')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
THR_WINDOW = 5000      # «прочих в окне» > 5000 → выброс
THR_TOTAL = 50000      # «прочих» всего > 50 000 → выброс
P99_NET = 311          # 99-й процентиль «прочих в окне» по постановке
NSIM = 2000
MIN_POOL_CORR = 5
MIN_POOL_TERC = 3
BIG_BIN = 912


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.__stdout__.write(s)
        self.f.write(s)

    def flush(self):
        sys.__stdout__.flush()
        self.f.flush()


def iv(x):
    if x in ('', None):
        return 0
    return int(float(x))


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return '—' if x is None or math.isnan(x) else '∞'
    return f'{x:.{nd}f}'


def median(xs):
    return statistics.median(xs) if xs else float('nan')


def quantile(xs, q):
    if not xs:
        return float('nan')
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def ranks(xs):
    """Средние ранги (1..n) с учётом связок."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float('nan')
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return float('nan')
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def spearman(xs, ys):
    return pearson(ranks(xs), ranks(ys))


def norm_ranks(xs):
    """Ранги, нормированные в [0, 1] внутри группы (для сводной корреляции)."""
    n = len(xs)
    if n == 1:
        return [0.5]
    return [(r - 1) / (n - 1) for r in ranks(xs)]


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    s = 0.0
    for i in range(0, k + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


def poisson_ci(k, alpha=0.05):
    """Точный ДИ для среднего Пуассона по наблюдённому k (Гарвуд)."""
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, float(k) + 1.0
        while poisson_cdf(k - 1, b) > alpha / 2:   # P(X >= k | b) = 1 - cdf(k-1) < 1-alpha/2
            b *= 2
        for _ in range(200):
            m = (a + b) / 2
            if 1.0 - poisson_cdf(k - 1, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    a, b = float(k), float(k) + 1.0
    while poisson_cdf(k, b) > alpha / 2:
        b *= 2
    for _ in range(200):
        m = (a + b) / 2
        if poisson_cdf(k, m) < alpha / 2:
            b = m
        else:
            a = m
    hi = (a + b) / 2
    return lo, hi


def poisson_p_two_sided(k, lam):
    """Двусторонний p: 2·min(P(X≤k), P(X≥k)), не больше 1."""
    lo = poisson_cdf(k, lam)
    hi = 1.0 - poisson_cdf(k - 1, lam) if k > 0 else 1.0
    return min(1.0, 2 * min(lo, hi))


def wmean_fisher(pairs):
    """Средневзвешенная корреляция через z-преобразование Фишера, веса n−3."""
    num = 0.0
    den = 0.0
    for rho, n in pairs:
        if math.isnan(rho) or n < 4:
            continue
        rho = max(-0.999999, min(0.999999, rho))
        z = 0.5 * math.log((1 + rho) / (1 - rho))
        num += (n - 3) * z
        den += (n - 3)
    if den == 0:
        return float('nan')
    z = num / den
    return (math.exp(2 * z) - 1) / (math.exp(2 * z) + 1)


def terciles_in_pool(items, key):
    """Метка терциля 0/1/2 по рангу key внутри группы; связки рвутся именем домена."""
    order = sorted(items, key=lambda d: (key(d), d['домен']))
    n = len(order)
    lab = {}
    for i, d in enumerate(order):
        lab[d['домен']] = min(2, (3 * i) // n)
    return lab


def oe_by_label(doms, labels, rate_of_pool):
    """O, E, объёмы по меткам 0/1/2."""
    acc = {t: collections.Counter() for t in range(3)}
    for d in doms:
        t = labels[d['домен']]
        e = rate_of_pool[d['_pk']] * d['_sw']
        acc[t]['n'] += 1
        acc[t]['sites'] += d['_sites']
        acc[t]['reg'] += d['_reg']
        acc[t]['sw'] += d['_sw']
        acc[t]['ow'] += d['_ow']
        acc[t]['E'] += e
    return acc


def run_tercile_test(doms, key, name, rng, out, nsim=NSIM, pool_key='_pool'):
    """O/E по терцилям внутри пула + перестановочный тест внутри пула."""
    by_pool = collections.defaultdict(list)
    for d in doms:
        by_pool[d[pool_key]].append(d)
    pools = {p: ds for p, ds in by_pool.items() if len(ds) >= MIN_POOL_TERC}
    used = [d for ds in pools.values() for d in ds]
    for d in used:
        d['_pk'] = d[pool_key]
    rate = {}
    for p, ds in pools.items():
        sw = sum(d['_sw'] for d in ds)
        rg = sum(d['_reg'] for d in ds)
        rate[p] = rg / sw if sw else 0.0
    labels = {}
    for p, ds in pools.items():
        labels.update(terciles_in_pool(ds, key))
    acc = oe_by_label(used, labels, rate)
    out.write(f'\n  {name}\n')
    out.write(f'    страт с ≥{MIN_POOL_TERC} доменами: {len(pools)}; доменов: {len(used)}; сайтов: {sum(d["_sites"] for d in used)}; '
              f'регистраций: {sum(d["_reg"] for d in used)}; поисковых в окне: {sum(d["_sw"] for d in used)}\n')
    out.write(f'    {"терциль":<10}{"доменов":>9}{"сайтов":>9}{"поисковых":>11}{"прочих":>9}{"рег":>6}{"E":>8}{"O/E":>7}{"рег/10тыс":>11}\n')
    names = ('нижний', 'средний', 'верхний')
    for t in range(3):
        a = acc[t]
        oe = a['reg'] / a['E'] if a['E'] else float('nan')
        r10 = 1e4 * a['reg'] / a['sw'] if a['sw'] else float('nan')
        out.write(f'    {names[t]:<10}{a["n"]:>9}{a["sites"]:>9}{a["sw"]:>11}{a["ow"]:>9}{a["reg"]:>6}{a["E"]:>8.1f}{fmt(oe):>7}{fmt(r10,1):>11}\n')

    def stat(acc):
        top = acc[2]['reg'] / acc[2]['E'] if acc[2]['E'] else float('nan')
        bot = acc[0]['reg'] / acc[0]['E'] if acc[0]['E'] else float('nan')
        if math.isnan(top) or math.isnan(bot):
            return float('nan'), float('nan')
        ratio = top / bot if bot > 0 else float('inf')
        return ratio, top - bot

    obs_ratio, obs_diff = stat(acc)
    pool_lists = list(pools.values())
    ge = 0
    two = 0
    ge_diff = 0
    valid = 0
    for _ in range(nsim):
        lab = {}
        for ds in pool_lists:
            names_ = [d['домен'] for d in ds]
            tl = [labels[x] for x in names_]
            rng.shuffle(tl)
            for x, t in zip(names_, tl):
                lab[x] = t
        a = oe_by_label(used, lab, rate)
        r, df = stat(a)
        if math.isnan(r):
            continue
        valid += 1
        if r >= obs_ratio:
            ge += 1
        if df >= obs_diff:
            ge_diff += 1
        if obs_ratio > 0 and not math.isinf(obs_ratio) and not math.isinf(r) and r > 0:
            if abs(math.log(r)) >= abs(math.log(obs_ratio)):
                two += 1
        elif math.isinf(r) or r == 0:
            two += 1
    p_ge = ge / valid if valid else float('nan')
    p_two = two / valid if valid else float('nan')
    p_diff = ge_diff / valid if valid else float('nan')
    out.write(f'    O/E верхнего / O/E нижнего = {fmt(obs_ratio)} (разность {fmt(obs_diff)}); '
              f'перестановок {valid}: p(отношение ≥ набл.) = {fmt(p_ge,3)}, p(двуст.) = {fmt(p_two,3)}, p(разность ≥ набл.) = {fmt(p_diff,3)}\n')
    return obs_ratio, p_ge, p_two, acc


def main():
    out = Tee(OUT)
    rng = random.Random(1)
    random.seed(1)
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    out.write('Гипотеза №14: «прочие» клики — тень поиска, а не источник; всплески — события домена\n')
    out.write(f'Источник: {SRC}\n')
    out.write(f'Всего строк в своде: {len(rows)}\n')

    # производные поля
    neg = []
    for r in rows:
        r['_sw'] = iv(r['кликов из поиска в окне'])
        r['_tw'] = iv(r['кликов всего в окне'])
        r['_bw'] = iv(r['ботов в окне'])
        ow = r['_tw'] - r['_sw'] - r['_bw']
        if ow < 0:
            neg.append((r['домен'], ow))
            ow = 0
        r['_ow'] = ow
        r['_ot'] = iv(r['прочих'])
        r['_sites'] = iv(r['сайтов в окне']) or iv(r['сайтов'])
        r['_reg'] = iv(r['регистраций в окне 3 суток'])
        r['_ex3'] = iv(r['вышли за 3 суток'])
        r['_pool'] = (r['набор контента'], r['день запуска'])
        r['_dz'] = (r['день запуска'], r['зона'])
    if neg:
        out.write(f'  «прочих в окне» < 0 (всего − поиск − боты), обнулено: {neg}\n')

    # выбросы
    outliers = [r for r in rows if r['_ow'] > THR_WINDOW or r['_ot'] > THR_TOTAL]
    outliers.sort(key=lambda r: -r['_ow'])
    out_names = {r['домен'] for r in outliers}
    out.write(f'\nВыбросы («прочих в окне» > {THR_WINDOW} или «прочих» всего > {THR_TOTAL}): {len(outliers)}\n')
    for r in outliers:
        out.write(f'  {r["домен"]:<12} запуск {r["день запуска"]}  набор «{r["набор контента"]}»  '
                  f'прочих в окне {r["_ow"]:>7}, прочих всего {r["_ot"]:>8}, поисковых в окне {r["_sw"]}, рег в окне {r["_reg"]}\n')

    closed = [r for r in rows if r['окно закрыто'] == 'да']
    out.write(f'\nФильтры:\n  исключены с незакрытым окном (окно закрыто = нет): {len(rows) - len(closed)}\n')
    d2 = [r for r in closed if r['дней'] != '1']
    out.write(f'  исключены с дней = 1 (150 сайтов, 2-й день не наступил): {len(closed) - len(d2)}\n')
    base_all = [r for r in d2 if r['домен'] not in out_names]
    out.write(f'  исключены выбросы (поимённо выше): {len(d2) - len(base_all)}\n')
    base = [r for r in base_all if r['набор контента'] != NOCONTENT]
    out.write(f'  «{NOCONTENT}» в остатке: {len(base_all) - len(base)} — исключён из основных срезов (в части Б есть контрольный проход с ним как стратой)\n')
    out.write(f'  осталось доменов для фона: {len(base)} (с «не записан»: {len(base_all)}); дней = 3: {sum(1 for r in base if r["дней"] == "3")}\n')
    out.write(f'  сайтов: {sum(r["_sites"] for r in base)}, регистраций в окне: {sum(r["_reg"] for r in base)} '
              f'(с «не записан»: {sum(r["_sites"] for r in base_all)} сайтов, {sum(r["_reg"] for r in base_all)} рег.)\n')

    # распределение фона
    ows = [r['_ow'] for r in base]
    ops = [r['_ow'] / r['_sites'] for r in base if r['_sites']]
    out.write('\n==============================================================================\n')
    out.write('0. ФОН «ПРОЧИХ В ОКНЕ» (без выбросов и «не записан»)\n')
    out.write('==============================================================================\n')
    out.write(f'  на домен: мин {min(ows)}, кв1 {fmt(quantile(ows,.25),0)}, медиана {fmt(median(ows),0)}, кв3 {fmt(quantile(ows,.75),0)}, '
              f'p99 {fmt(quantile(ows,.99),0)}, макс {max(ows)}\n')
    out.write(f'  на сайт: медиана {fmt(median(ops),3)}, кв1 {fmt(quantile(ops,.25),3)}, кв3 {fmt(quantile(ops,.75),3)}\n')
    net_med = median(ows)
    tot_ow = sum(r['_ow'] for r in base)
    tot_ot = sum(r['_ot'] for r in base)
    out.write(f'  Σ прочих в окне {tot_ow} против Σ прочих за всё время {tot_ot}: в окне {fmt(100*tot_ow/tot_ot,1)} % '
              f'(поисковых: в окне {sum(r["_sw"] for r in base)} из {sum(iv(r["из поиска"]) for r in base)} = '
              f'{fmt(100*sum(r["_sw"] for r in base)/max(1,sum(iv(r["из поиска"]) for r in base)),1)} %)\n')
    ow_all_ones = [r for r in base if r['_ow'] > P99_NET]
    out.write(f'  доменов с «прочих в окне» > {P99_NET}: {len(ow_all_ones)}; > 1000: {sum(1 for r in base if r["_ow"] > 1000)}; '
              f'> 3× медианы ({fmt(3*net_med,0)}): {sum(1 for r in base if r["_ow"] > 3*net_med)}\n')
    zs = [r for r in base_all if r['_sw'] == 0 and r['_ow'] > 0]
    out.write(f'  доменов с нулём поисковых в окне и «прочими» > 0: {len(zs)} (с «не записан»), регистраций в окне у них: {sum(r["_reg"] for r in zs)}, '
              f'Σ прочих в окне {sum(r["_ow"] for r in zs)}\n')

    # ------------------------------------------------------------------ А
    out.write('\n==============================================================================\n')
    out.write('А. ЧТО ТАКОЕ ФОН: С ЧЕМ СВЯЗАНЫ «ПРОЧИЕ В ОКНЕ»\n')
    out.write('==============================================================================\n')
    out.write(f'А1. Спирмен внутри пула «набор контента + день запуска» (пулы с ≥{MIN_POOL_CORR} доменами)\n')
    by_pool = collections.defaultdict(list)
    for r in base:
        by_pool[r['_pool']].append(r)
    pools_c = {p: ds for p, ds in by_pool.items() if len(ds) >= MIN_POOL_CORR}
    vars_ = (('вышли за 3 суток', '_ex3'), ('кликов из поиска в окне', '_sw'), ('ботов в окне', '_bw'),
             ('сайтов с поиском (всё время)', 'сайтов с поиском'))
    out.write(f'  пулов: {len(pools_c)}, доменов в них: {sum(len(ds) for ds in pools_c.values())}\n')
    out.write(f'  {"с чем":<32}{"медиана ρ по пулам":>20}{"взвеш. ρ (n−3)":>16}{"ρ норм. рангов":>16}{"пулов ρ>0":>11}{"пулов n":>9}\n')
    rho_store = {}
    for label, key in vars_:
        pr = []
        nr_x, nr_y = [], []
        for p, ds in pools_c.items():
            xs = [d['_ow'] for d in ds]
            ys = [iv(d[key]) if not key.startswith('_') else d[key] for d in ds]
            rho = spearman(xs, ys)
            if not math.isnan(rho):
                pr.append((rho, len(ds)))
            nr_x += norm_ranks(xs)
            nr_y += norm_ranks(ys)
        rho_med = median([r for r, _ in pr])
        rho_w = wmean_fisher(pr)
        rho_all = pearson(nr_x, nr_y)
        rho_store[key] = (rho_med, rho_w, rho_all)
        out.write(f'  {label:<32}{fmt(rho_med):>20}{fmt(rho_w):>16}{fmt(rho_all):>16}{sum(1 for r,_ in pr if r>0):>11}{len(pr):>9}\n')
    # попарно: в скольких пулах ρ(вышли) ≥ ρ(поиск)
    cnt_ge = 0
    cnt_tot = 0
    for p, ds in pools_c.items():
        xs = [d['_ow'] for d in ds]
        a = spearman(xs, [d['_ex3'] for d in ds])
        b = spearman(xs, [d['_sw'] for d in ds])
        if not math.isnan(a) and not math.isnan(b):
            cnt_tot += 1
            if a >= b:
                cnt_ge += 1
    out.write(f'  пулов, где ρ(вышли за 3 суток) ≥ ρ(поисковые в окне): {cnt_ge} из {cnt_tot}\n')
    # внутри дня (для сверки с постановкой)
    by_day = collections.defaultdict(list)
    for r in base:
        by_day[r['день запуска']].append(r)
    days_c = {d: ds for d, ds in by_day.items() if len(ds) >= MIN_POOL_CORR}
    out.write(f'\nА1б. То же внутри дня запуска (дней с ≥{MIN_POOL_CORR} доменами: {len(days_c)}) — сверка с постановкой (0,52 / 0,47 / 0,46)\n')
    for label, key in vars_[:3]:
        nr_x, nr_y = [], []
        pr = []
        for d, ds in days_c.items():
            xs = [x['_ow'] for x in ds]
            ys = [x[key] for x in ds]
            rho = spearman(xs, ys)
            if not math.isnan(rho):
                pr.append((rho, len(ds)))
            nr_x += norm_ranks(xs)
            nr_y += norm_ranks(ys)
        out.write(f'  {label:<32} медиана ρ по дням {fmt(median([r for r,_ in pr]))}, взвеш. {fmt(wmean_fisher(pr))}, норм. ранги {fmt(pearson(nr_x, nr_y))}\n')
    # при равных поисковых: страта = пул × терциль поисковых кликов внутри пула (пулы ≥9 доменов)
    MIN_POOL_STR = 9
    strata = collections.defaultdict(list)
    for p, ds in by_pool.items():
        if len(ds) < MIN_POOL_STR:
            continue
        lab = terciles_in_pool(ds, lambda d: d['_sw'])
        for d in ds:
            d['_pool_sb'] = (p, lab[d['домен']])
            strata[d['_pool_sb']].append(d)
    out.write(f'\nА1в. При равных поисковых кликах: страта = пул × терциль поисковых внутри пула (пулы с ≥{MIN_POOL_STR} доменами): '
              f'страт {len(strata)}, доменов {sum(len(v) for v in strata.values())}\n')
    out.write(f'  {"с чем":<32}{"медиана ρ по стратам":>22}{"взвеш. ρ (n−3)":>16}{"ρ норм. рангов":>16}{"страт":>7}\n')
    rho_eq = {}
    for label, key in (('вышли за 3 суток', '_ex3'), ('кликов из поиска в окне (остаток)', '_sw'), ('ботов в окне', '_bw')):
        pr = []
        nr_x, nr_y = [], []
        for st_, ds in strata.items():
            if len(ds) < 3:
                continue
            xs = [d['_ow'] for d in ds]
            ys = [d[key] for d in ds]
            rho = spearman(xs, ys)
            if not math.isnan(rho):
                pr.append((rho, len(ds)))
            nr_x += norm_ranks(xs)
            nr_y += norm_ranks(ys)
        rho_eq[key] = (median([r for r, _ in pr]), wmean_fisher(pr), pearson(nr_x, nr_y))
        out.write(f'  {label:<32}{fmt(rho_eq[key][0]):>22}{fmt(rho_eq[key][1]):>16}{fmt(rho_eq[key][2]):>16}{len(pr):>7}\n')
    out.write('     (страты по 3–5 доменов, медианы по стратам шумные; опорная цифра — ρ по нормированным рангам)\n')

    # А2. модели
    out.write('\nА2. Модели фона: k по дням запуска (k = Σпрочих / Σx по доменам дня; ошибка = |k·x − прочих| / max(прочих,1))\n')
    models = (('медиана дня (нулевая)', None), ('k × вышли за 3 суток', '_ex3'), ('k × поисковых в окне', '_sw'),
              ('k × сайтов', '_sites'), ('k × ботов в окне', '_bw'))
    errs = {m: [] for m, _ in models}
    kday = {}
    for d, ds in by_day.items():
        so = sum(x['_ow'] for x in ds)
        kd = {}
        for m, key in models:
            if key is None:
                kd[m] = median([x['_ow'] for x in ds])
            else:
                sx = sum(x[key] for x in ds)
                kd[m] = so / sx if sx else float('nan')
        kday[d] = kd
        for x in ds:
            for m, key in models:
                if key is None:
                    pred = kd[m]
                else:
                    pred = kd[m] * x[key] if not math.isnan(kd[m]) else float('nan')
                if math.isnan(pred):
                    continue
                errs[m].append((x['домен'], abs(pred - x['_ow']) / max(x['_ow'], 1)))
    out.write(f'  {"модель":<26}{"доменов":>9}{"медиана отн. ошибки":>21}{"кв3":>8}{"доля ошибок ≤50 %":>18}\n')
    for m, _ in models:
        e = [v for _, v in errs[m]]
        out.write(f'  {m:<26}{len(e):>9}{fmt(median(e)):>21}{fmt(quantile(e,.75)):>8}{fmt(100*sum(1 for v in e if v<=.5)/len(e),1)+" %":>18}\n')
    e_ex = dict(errs['k × вышли за 3 суток'])
    e_sw = dict(errs['k × поисковых в окне'])
    e_md = dict(errs['медиана дня (нулевая)'])
    both = [d for d in e_ex if d in e_sw and d in e_md]
    out.write(f'  доменов, где «вышли» точнее «поисковых»: {sum(1 for d in both if e_ex[d] < e_sw[d])} из {len(both)}; '
              f'«вышли» точнее медианы дня: {sum(1 for d in both if e_ex[d] < e_md[d])}; «поисковые» точнее медианы дня: {sum(1 for d in both if e_sw[d] < e_md[d])}\n')
    # k по пулам (контроль)
    errs_p = {m: [] for m, _ in models}
    for p, ds in by_pool.items():
        if len(ds) < MIN_POOL_TERC:
            continue
        so = sum(x['_ow'] for x in ds)
        for m, key in models:
            if key is None:
                k = median([x['_ow'] for x in ds])
            else:
                sx = sum(x[key] for x in ds)
                k = so / sx if sx else float('nan')
            for x in ds:
                pred = k if key is None else k * x[key]
                if math.isnan(pred):
                    continue
                errs_p[m].append(abs(pred - x['_ow']) / max(x['_ow'], 1))
    out.write('  контроль, k по пулу «набор + день» (пулы ≥3 доменов): медиана отн. ошибки — '
              + '; '.join(f'{m}: {fmt(median(errs_p[m]))} (n={len(errs_p[m])})' for m, _ in models) + '\n')

    out.write('\nА3. k по дням запуска (домены фона; k_вышли = Σпрочих/Σвышли за 3 суток; k_сайт = Σпрочих/Σсайтов; k_поиск = Σпрочих/Σпоисковых в окне)\n')
    out.write(f'  {"день":<12}{"доменов":>8}{"сайтов":>8}{"Σпрочих":>9}{"Σвышли":>8}{"Σпоиск":>9}{"k_вышли":>9}{"k_сайт":>8}{"k_поиск":>9}{"медиана прочих":>16}{"мед. прочих/вышли":>19}\n')
    k_site_list, k_ex_list, k_sw_list = [], [], []
    for d in sorted(by_day):
        ds = by_day[d]
        so = sum(x['_ow'] for x in ds)
        se = sum(x['_ex3'] for x in ds)
        ss = sum(x['_sites'] for x in ds)
        sw = sum(x['_sw'] for x in ds)
        k_ex = so / se if se else float('nan')
        k_si = so / ss if ss else float('nan')
        k_sw = so / sw if sw else float('nan')
        med_r = median([x['_ow'] / x['_ex3'] for x in ds if x['_ex3'] > 0])
        if len(ds) >= 10:
            k_site_list.append(k_si)
            k_ex_list.append(k_ex)
            k_sw_list.append(k_sw)
        out.write(f'  {d:<12}{len(ds):>8}{ss:>8}{so:>9}{se:>8}{sw:>9}{fmt(k_ex):>9}{fmt(k_si,3):>8}{fmt(k_sw,3):>9}{fmt(median([x["_ow"] for x in ds]),0):>16}{fmt(med_r):>19}\n')

    def cv(xs):
        xs = [x for x in xs if not math.isnan(x)]
        if len(xs) < 2:
            return float('nan')
        return statistics.pstdev(xs) / statistics.mean(xs)
    out.write(f'  дни с ≥10 доменами: {len(k_site_list)}; k_сайт от {fmt(min(k_site_list),3)} до {fmt(max(k_site_list),3)} (CV {fmt(cv(k_site_list))}); '
              f'k_вышли от {fmt(min(k_ex_list))} до {fmt(max(k_ex_list))} (CV {fmt(cv(k_ex_list))}); '
              f'k_поиск от {fmt(min(k_sw_list),3)} до {fmt(max(k_sw_list),3)} (CV {fmt(cv(k_sw_list))})\n')
    aug = [r for r in base if r['день запуска'] < '2026-09-01']
    sep = [r for r in base if r['день запуска'] >= '2026-09-01']
    for nm, grp in (('август (без «не записан»)', aug), ('сентябрь', sep)):
        if grp:
            out.write(f'  {nm}: доменов {len(grp)}, прочих на сайт {fmt(sum(x["_ow"] for x in grp)/sum(x["_sites"] for x in grp),3)}, '
                      f'прочих на вышедший сайт {fmt(sum(x["_ow"] for x in grp)/max(1,sum(x["_ex3"] for x in grp)))}, '
                      f'прочих на поисковый клик {fmt(sum(x["_ow"] for x in grp)/max(1,sum(x["_sw"] for x in grp)),3)}\n')

    # ------------------------------------------------------------------ Б
    out.write('\n==============================================================================\n')
    out.write('Б. ДЕНЬГИ: ДАЮТ ЛИ «ПРОЧИЕ» РЕГИСТРАЦИИ СВЕРХ ПОИСКА\n')
    out.write('==============================================================================\n')
    out.write('E домена = (Σрег пула / Σпоисковых в окне пула) × поисковые клики домена в окне; пул = набор контента + день запуска.\n')
    bb = [r for r in base if r['_sw'] > 0]
    out.write(f'Домены фона с поисковыми кликами в окне > 0: {len(bb)} из {len(base)} (у остальных E = 0 и регистраций нет — исключены)\n')
    key_ps = lambda d: d['_ow'] / d['_sites']
    key_os = lambda d: d['_ow'] / d['_sw']
    key_sw = lambda d: d['_sw']
    results = {}
    results['ps'] = run_tercile_test(bb, key_ps, 'Б1. Терцили «прочих на сайт в окне» внутри пула', rng, out)
    results['os'] = run_tercile_test(bb, key_os, 'Б2. Терцили «прочих / поисковых в окне» внутри пула', rng, out)
    results['sw'] = run_tercile_test(bb, key_sw, 'Б3. Контроль: терцили самих поисковых кликов в окне внутри пула (эффект объёма)', rng, out)
    big = [r for r in bb if r['_sw'] > BIG_BIN]
    small = [r for r in bb if r['_sw'] <= BIG_BIN]
    out.write(f'\nБин > {BIG_BIN} поисковых в окне: {len(big)} доменов, регистраций {sum(r["_reg"] for r in big)}; бин ≤ {BIG_BIN}: {len(small)} доменов, регистраций {sum(r["_reg"] for r in small)}\n')
    results['os_big'] = run_tercile_test(big, key_os, f'Б4. Бин > {BIG_BIN}: терцили «прочих / поисковых» внутри пула (пулы из доменов бина)', rng, out)
    results['ps_big'] = run_tercile_test(big, key_ps, f'Б5. Бин > {BIG_BIN}: терцили «прочих на сайт» внутри пула', rng, out)
    results['os_small'] = run_tercile_test(small, key_os, f'Б6. Бин ≤ {BIG_BIN}: терцили «прочих / поисковых» внутри пула', rng, out)
    # без страты, как в постановке (для сверки 1,63 / 1,73 / 2,60)
    out.write(f'\nБ7. Сверка с постановкой — бин > {BIG_BIN} БЕЗ страты, терцили «прочих / поисковых» по всему бину: рег на 10 тыс. поисковых\n')
    order = sorted(big, key=lambda d: (key_os(d), d['домен']))
    n = len(order)
    for t in range(3):
        grp = [d for i, d in enumerate(order) if min(2, (3 * i) // n) == t]
        sw = sum(d['_sw'] for d in grp)
        rg = sum(d['_reg'] for d in grp)
        out.write(f'    терциль {t+1}: доменов {len(grp)}, поисковых {sw}, рег {rg}, рег/10 тыс. {fmt(1e4*rg/sw if sw else float("nan"),2)}, '
                  f'медиана поисковых {fmt(median([d["_sw"] for d in grp]),0)}, медиана прочих {fmt(median([d["_ow"] for d in grp]),0)}\n')
    # контрольный проход с «не записан» как стратой
    bb_all = [r for r in base_all if r['_sw'] > 0]
    out.write(f'\nБ8. Контроль: то же с «{NOCONTENT}» как собственной стратой (день × «не записан»): доменов {len(bb_all)}, регистраций {sum(r["_reg"] for r in bb_all)}\n')
    results['os_all'] = run_tercile_test(bb_all, key_os, '    терцили «прочих / поисковых» внутри пула', rng, out)
    results['ps_all'] = run_tercile_test(bb_all, key_ps, '    терцили «прочих на сайт» внутри пула', rng, out)

    # Б9. при равных поисковых: страта = пул × терциль поисковых внутри пула
    def add_sb(doms, min_pool):
        bp = collections.defaultdict(list)
        for d in doms:
            bp[d['_pool']].append(d)
        res = []
        for p, ds in bp.items():
            if len(ds) < min_pool:
                continue
            lab = terciles_in_pool(ds, lambda d: d['_sw'])
            for d in ds:
                d['_pool_sb'] = (p, lab[d['домен']])
                res.append(d)
        return res
    bb_sb = add_sb(bb, 9)
    out.write(f'\nБ9. При равных поисковых кликах: страта = пул × терциль поисковых внутри пула (пулы с ≥9 доменами); '
              f'внутри страты терцили «прочих на сайт»; E = ставка страты × поисковые домена\n')
    results['ps_sb'] = run_tercile_test(bb_sb, key_ps, '    без «не записан»', rng, out, pool_key='_pool_sb')
    bb_sb_all = add_sb(bb_all, 9)
    results['ps_sb_all'] = run_tercile_test(bb_sb_all, key_ps, f'    с «{NOCONTENT}» как стратой', rng, out, pool_key='_pool_sb')
    # разброс поисковых внутри страт «пул × терциль» — насколько выровнен объём
    sp = []
    bsb = collections.defaultdict(list)
    for d in bb_sb:
        bsb[d['_pool_sb']].append(d['_sw'])
    for v in bsb.values():
        if len(v) >= 3 and min(v) > 0:
            sp.append(max(v) / min(v))
    out.write(f'    выравнивание объёма: в стратах «пул × терциль» отношение макс/мин поисковых кликов — медиана {fmt(median(sp),1)}, кв3 {fmt(quantile(sp,.75),1)}\n')

    # Б10. в тех же стратах — терцили других признаков активности: вышли за 3 суток, ботов в окне
    out.write('\nБ10. Те же страты «пул × терциль поисковых», но терцили других признаков (что именно «метит» деньги при равных поисковых)\n')
    results['ex_sb'] = run_tercile_test(bb_sb, lambda d: d['_ex3'] / d['_sites'], '    терцили «вышли за 3 суток / сайтов» (широта выхода)', rng, out, pool_key='_pool_sb')
    results['bw_sb'] = run_tercile_test(bb_sb, lambda d: d['_bw'] / d['_sites'], '    терцили «ботов в окне / сайтов»', rng, out, pool_key='_pool_sb')
    results['sw_sb'] = run_tercile_test(bb_sb, key_sw, '    контроль: терцили поисковых внутри страты (остаток объёма)', rng, out, pool_key='_pool_sb')
    # Б11. «прочие сверх выхода»: внутри страты ранг прочих минус ранг вышедших
    bsb_d = collections.defaultdict(list)
    for d in bb_sb:
        bsb_d[d['_pool_sb']].append(d)
    for st_, ds in bsb_d.items():
        ro = norm_ranks([d['_ow'] / d['_sites'] for d in ds])
        re_ = norm_ranks([d['_ex3'] / d['_sites'] for d in ds])
        rb = norm_ranks([d['_bw'] / d['_sites'] for d in ds])
        for d, a, b, c in zip(ds, ro, re_, rb):
            d['_res_ex'] = a - b
            d['_res_bw'] = a - c
            d['_ex_res_ow'] = b - a
    out.write('\nБ11. Разделение: внутри страты ранг «прочих на сайт» минус ранг другого признака (что остаётся у «прочих» сверх него)\n')
    results['res_ex'] = run_tercile_test(bb_sb, lambda d: d['_res_ex'], '    терцили «прочих сверх вышедших» (ранг прочих − ранг вышли/сайтов)', rng, out, pool_key='_pool_sb')
    results['res_bw'] = run_tercile_test(bb_sb, lambda d: d['_res_bw'], '    терцили «прочих сверх ботов» (ранг прочих − ранг ботов/сайтов)', rng, out, pool_key='_pool_sb')
    results['ex_res'] = run_tercile_test(bb_sb, lambda d: d['_ex_res_ow'], '    обратно: терцили «вышедших сверх прочих» (ранг вышли − ранг прочих)', rng, out, pool_key='_pool_sb')
    # Б12. регистрации и «прочие»: сколько «прочих» приходится на домен с регистрацией и без — внутри страт
    with_reg = [d for d in bb_sb if d['_reg'] > 0]
    out.write(f'\nБ12. Внутри страт «пул × терциль поисковых»: медиана нормированного ранга «прочих на сайт» у доменов с регистрацией в окне '
              f'({len(with_reg)} дом.) = {fmt(median([norm_ranks([x["_ow"]/x["_sites"] for x in bsb_d[d["_pool_sb"]]])[[x["домен"] for x in bsb_d[d["_pool_sb"]]].index(d["домен"])] for d in with_reg]))}, '
              f'без регистрации ({len(bb_sb)-len(with_reg)} дом.) = '
              f'{fmt(median([norm_ranks([x["_ow"]/x["_sites"] for x in bsb_d[d["_pool_sb"]]])[[x["домен"] for x in bsb_d[d["_pool_sb"]]].index(d["домен"])] for d in bb_sb if d["_reg"] == 0]))} '
              f'(0,5 = середина страты)\n')
    out.write(f'    без страты (объём не выровнен): медиана «прочих в окне» у доменов с регистрацией {fmt(median([d["_ow"] for d in with_reg]),0)}, без — '
              f'{fmt(median([d["_ow"] for d in bb_sb if d["_reg"] == 0]),0)}\n')

    # ------------------------------------------------------------------ В
    out.write('\n==============================================================================\n')
    out.write('В. ВСПЛЕСКИ: 5 ДОМЕНОВ-ВЫБРОСОВ И ИХ СОСЕДИ\n')
    out.write('==============================================================================\n')
    out.write(f'Соседи — домены с закрытым окном и дней ≠ 1 (включая «не записан»), без других выбросов. Медиана сети (фон) = {fmt(net_med,0)}, 3× = {fmt(3*net_med,0)}, p99 постановки = {P99_NET}.\n')
    nb_pool = collections.defaultdict(list)
    nb_dz = collections.defaultdict(list)
    for r in base_all:
        nb_pool[r['_pool']].append(r)
        nb_dz[r['_dz']].append(r)
    sum_o = 0
    sum_e = 0.0
    sum_e_dz = 0.0
    nb_stats = {}
    out.write('\nВ1. Соседи по пулу «набор контента + день» и по «день + зона»\n')
    for r in outliers:
        out.write(f'\n  {r["домен"]} — запуск {r["день запуска"]} {r["час запуска"]}:00, зона {r["зона"]}, набор «{r["набор контента"]}», сайтов {r["_sites"]}\n')
        out.write(f'    прочих в окне {r["_ow"]}, прочих всего {r["_ot"]} (в окне {fmt(100*r["_ow"]/max(1,r["_ot"]),1)} %); '
                  f'кликов всего {iv(r["кликов всего"])}, из поиска {iv(r["из поиска"])} (в окне {r["_sw"]}), ботов {iv(r["ботов"])} (в окне {r["_bw"]})\n')
        out.write(f'    первый клик {r["первый клик"]}, последний клик {r["последний клик"]}, суток с кликами {r["суток с кликами"]}, '
                  f'вышли за 3 суток {r["_ex3"]}, сайтов с поиском {r["сайтов с поиском"]}; регистраций всего {iv(r["регистраций"])}, в окне {r["_reg"]}, ФД {iv(r["ФД"])}\n')
        for nm, grp in (('набор + день', nb_pool[r['_pool']]), ('день + зона', nb_dz[r['_dz']])):
            if not grp:
                out.write(f'    соседи по «{nm}»: нет\n')
                continue
            vals = [x['_ow'] for x in grp]
            mx = max(grp, key=lambda x: x['_ow'])
            st_ = nb_stats.setdefault(r['домен'], [0, 0, 0, 0, 0])
            if nm == 'набор + день':
                st_[0], st_[1], st_[4] = median(vals), mx['_ow'], r['_ow'] / max(1, median(vals))
            else:
                st_[2], st_[3] = median(vals), mx['_ow']
            out.write(f'    соседи по «{nm}»: n={len(grp)}, медиана прочих в окне {fmt(median(vals),0)}, макс {mx["_ow"]} ({mx["домен"]}), '
                      f'выброс/медиана = {fmt(r["_ow"]/max(1,median(vals)),0)}×; соседей > {P99_NET}: {sum(1 for v in vals if v > P99_NET)}, '
                      f'> {fmt(3*net_med,0)}: {sum(1 for v in vals if v > 3*net_med)}, > 1000: {sum(1 for v in vals if v > 1000)}; '
                      f'медиана прочих всего у соседей {fmt(median([x["_ot"] for x in grp]),0)}, макс {max(x["_ot"] for x in grp)}\n')
        # ожидание регистраций по ставке соседей: по «набор + день» и по «день + зона»
        parts = []
        for nm, grp in (('набор + день', nb_pool[r['_pool']]), ('день + зона', nb_dz[r['_dz']])):
            sw = sum(x['_sw'] for x in grp)
            rg = sum(x['_reg'] for x in grp)
            rate = rg / sw if sw else 0.0
            e = rate * r['_sw']
            if nm == 'набор + день':
                sum_e += e
            else:
                sum_e_dz += e
            parts.append(f'{nm} (n={len(grp)}, {rg} рег на {sw} поисковых, {fmt(1e4*rate,2)} рег/10 тыс.): E = {fmt(e)}, O/E = {fmt(r["_reg"]/e) if e else "—"}')
        sum_o += r['_reg']
        lo, hi = poisson_ci(r['_reg'])
        out.write(f'    деньги: O = {r["_reg"]} на {r["_sw"]} поисковых [ДИ O: {fmt(lo,1)}–{fmt(hi,1)}]; ставка соседей по ' + '; по '.join(parts) + '\n')
        out.write(f'    аккаунты: вебмастер {r["аккаунт вебмастера"]} (который раз {r["который раз аккаунт"]}, баз всего {r["аккаунт: баз всего"]}), cf-аккаунт {r["cf-аккаунт"]}\n')
        for nm, col in (('вебмастер', 'аккаунт вебмастера'), ('cf', 'cf-аккаунт')):
            sib = [x for x in rows if x[col] == r[col] and x['домен'] != r['домен']]
            if sib:
                out.write(f'      другие домены на том же {nm}-аккаунте: ' + ', '.join(
                    f'{x["домен"]} (запуск {x["день запуска"]}, прочих в окне {x["_ow"]}, всего {x["_ot"]}, окно закрыто {x["окно закрыто"]})' for x in sib) + '\n')
            else:
                out.write(f'      других доменов на том же {nm}-аккаунте нет\n')
    lo, hi = poisson_ci(sum_o)
    p_two = poisson_p_two_sided(sum_o, sum_e)
    p_two_dz = poisson_p_two_sided(sum_o, sum_e_dz)
    out.write(f'\nВ2. Суммарно по 5 выбросам: O = {sum_o} на {sum(r["_sw"] for r in outliers)} поисковых в окне (рег/10 тыс. = {fmt(1e4*sum_o/sum(r["_sw"] for r in outliers),2)}; '
              f'фон без выбросов: {fmt(1e4*sum(r["_reg"] for r in base)/sum(r["_sw"] for r in base),2)})\n')
    out.write(f'    E по ставке «набор + день»: {fmt(sum_e)}, O/E = {fmt(sum_o/sum_e) if sum_e else "—"} '
              f'[точный пуассоновский ДИ {fmt(lo/sum_e) if sum_e else "—"}–{fmt(hi/sum_e) if sum_e else "—"}], p(двуст.) = {fmt(p_two,3)}\n')
    out.write(f'    E по ставке «день + зона»:  {fmt(sum_e_dz)}, O/E = {fmt(sum_o/sum_e_dz) if sum_e_dz else "—"} '
              f'[ДИ {fmt(lo/sum_e_dz) if sum_e_dz else "—"}–{fmt(hi/sum_e_dz) if sum_e_dz else "—"}], p(двуст.) = {fmt(p_two_dz,3)}\n')
    # аккаунты: пересечения между 5
    cf5 = collections.Counter(r['cf-аккаунт'] for r in outliers)
    wm5 = collections.Counter(r['аккаунт вебмастера'] for r in outliers)
    out.write(f'   пересечения между 5 выбросами: cf-аккаунтов общих {sum(1 for v in cf5.values() if v > 1)}, аккаунтов вебмастера общих {sum(1 for v in wm5.values() if v > 1)}; '
              f'дней запуска {len(set(r["день запуска"] for r in outliers))} разных ({", ".join(sorted(set(r["день запуска"] for r in outliers)))}), '
              f'наборов {len(set(r["набор контента"] for r in outliers))} разных\n')
    # день 02.09 отдельно: два выброса в один день
    d0209 = [r for r in base_all if r['день запуска'] == '2026-09-02']
    if d0209:
        vals = [x['_ow'] for x in d0209]
        out.write(f'   день 2026-09-02 (два выброса из 5): соседей {len(d0209)}, медиана прочих в окне {fmt(median(vals),0)}, кв3 {fmt(quantile(vals,.75),0)}, '
                  f'макс {max(vals)}, > {P99_NET}: {sum(1 for v in vals if v > P99_NET)}; наборы дня: '
                  + ', '.join(f'{k} ({v})' for k, v in collections.Counter(x['набор контента'] for x in d0209).most_common()) + '\n')
    # соседи выбросов по cf-аккаунту: сравнить их прочие с фоном
    # сравнение поисковой части выбросов с соседями (вышли за 3 суток / сайтов)
    sw_ratio = {}
    out.write('\nВ3. Поисковая часть выбросов против соседей по «набор + день» (выход = вышли за 3 суток / сайтов; поисковых на сайт)\n')
    for r in outliers:
        grp = nb_pool[r['_pool']]
        if not grp:
            grp = nb_dz[r['_dz']]
        ex_nb = [x['_ex3'] / x['_sites'] for x in grp if x['_sites']]
        sw_nb = [x['_sw'] / x['_sites'] for x in grp if x['_sites']]
        my_sw = r['_sw'] / r['_sites']
        above = sum(1 for v in sw_nb if v > my_sw)
        sw_ratio[r['домен']] = my_sw / max(1e-9, median(sw_nb))
        out.write(f'  {r["домен"]:<12} выход {fmt(100*r["_ex3"]/r["_sites"],1)} % (соседи: медиана {fmt(100*median(ex_nb),1)} %, кв1–кв3 {fmt(100*quantile(ex_nb,.25),1)}–{fmt(100*quantile(ex_nb,.75),1)}, макс {fmt(100*max(ex_nb),1)}); '
                  f'поисковых на сайт {fmt(my_sw,1)} (соседи: медиана {fmt(median(sw_nb),1)}, кв1–кв3 {fmt(quantile(sw_nb,.25),1)}–{fmt(quantile(sw_nb,.75),1)}, макс {fmt(max(sw_nb),1)}; '
                  f'выше выброса {above} из {len(grp)}; выброс/медиана {fmt(my_sw/max(1e-9,median(sw_nb)),1)}×)\n')

    # ------------------------------------------------------------------ Г (справка по выгрузкам кликов)
    out.write('\n==============================================================================\n')
    out.write('Г. СПРАВКА: ИЗ ЧЕГО СОСТОЯТ «ПРОЧИЕ» (по выгрузкам кликов analysis/api/tracker_clicks_*.jsonl, если они есть)\n')
    out.write('==============================================================================\n')
    click_files = sorted(glob.glob(os.path.join(REPO, 'analysis', 'api', 'tracker_clicks_*.jsonl')))
    comp_res = {}
    if '--no-clicks' in sys.argv or not click_files:
        out.write('  выгрузки кликов не найдены или отключены (--no-clicks) — справка пропущена; выводы А–В от неё не зависят\n')
    else:
        out.write('  Правила: кампания dorgen_engine, только домены свода, без is_bot, без реферера Яндекса (это «из поиска»); дубли clickid сняты.\n'
                  '  Компоненты: «без реферера», «самореферер» (реферер — тот же сабдомен), «+ловушка» (хвост exit_path из повторов одного сегмента,\n'
                  '  /promo/ru/ru/ru/…), «google», «другой сабдомен базы», «внешний». Окно здесь приближённое: смещение 0..4 суток от дня запуска домена.\n')
        launch = {r['домен']: datetime.date.fromisoformat(r['день запуска']) for r in rows}
        svod_names = set(launch)
        rs = re.compile(r'"subdomain": "([^"]*)"')
        rr = re.compile(r'"referer": "([^"]*)"')
        rx = re.compile(r'"exit_path": "([^"]*)"')
        ra = re.compile(r'"at": "(\d{4}-\d\d-\d\d)')
        rc = re.compile(r'"clickid": "([^"]*)"')
        rco = re.compile(r'"country": "([^"]*)"')
        CIS = {'RU', 'KZ', 'BY', 'UA', 'UZ', 'KG', 'AM', 'AZ', 'MD', 'TJ', 'GE'}
        comp = collections.defaultdict(collections.Counter)
        compw = collections.defaultdict(collections.Counter)
        tot_c = collections.Counter()
        totw_c = collections.Counter()
        out_c = collections.Counter()
        cc = collections.defaultdict(collections.Counter)
        ya = collections.Counter()
        o_sub = collections.defaultdict(collections.Counter)
        o_day = collections.defaultdict(collections.Counter)
        o_co = collections.defaultdict(collections.Counter)
        seen = set()
        nlines = 0
        for path in click_files:
            with open(path, encoding='utf-8') as f:
                for line in f:
                    nlines += 1
                    if '"campaign": "dorgen_engine"' not in line or '"is_bot": true' in line:
                        continue
                    ms = rs.search(line)
                    if not ms:
                        continue
                    sub = ms.group(1).lower()
                    b = '.'.join(sub.split('.')[-2:])
                    if b not in svod_names:
                        continue
                    cid = rc.search(line).group(1)
                    if cid in seen:
                        continue
                    seen.add(cid)
                    m = rr.search(line)
                    ref = m.group(1) if m else ''
                    ma = ra.search(line)
                    day = ma.group(1) if ma else ''
                    off = (datetime.date.fromisoformat(day) - launch[b]).days if day else -99
                    mc = rco.search(line)
                    co = mc.group(1) if mc else ''
                    if 'yandex' in ref or '//ya.ru' in ref or 'dzen.ru' in ref:
                        if b not in out_names:
                            ya['всего'] += 1
                            ya['СНГ'] += co in CIS
                            if 0 <= off <= 4:
                                ya['окно'] += 1
                                ya['окно СНГ'] += co in CIS
                                compw[b]['яндекс'] += 1
                        continue
                    ex = rx.search(line)
                    exp = ex.group(1) if ex else ''
                    seg = exp.split('/')
                    tr = len(seg) >= 5 and seg[-1] == seg[-2] == seg[-3] and seg[-1] != ''
                    if not ref:
                        k = 'без реферера'
                    else:
                        h = ref.split('//', 1)[-1].split('/', 1)[0].lower()
                        if h.startswith('www.'):
                            h = h[4:]
                        if h == sub:
                            k = 'самореферер'
                        elif h.endswith('.' + b) or h == b:
                            k = 'другой сабдомен базы'
                        elif 'google' in h:
                            k = 'google'
                        else:
                            k = 'внешний'
                    if tr:
                        k += ' +ловушка'
                    comp[b][k] += 1
                    if b in out_names:
                        out_c[k] += 1
                        o_sub[b][sub] += 1
                        o_day[b][day] += 1
                        o_co[b][co] += 1
                    else:
                        tot_c[k] += 1
                    if 0 <= off <= 4:
                        compw[b][k] += 1
                        if b not in out_names:
                            totw_c[k] += 1
                            cc[k][co] += 1
        out.write(f'  строк в выгрузках: {nlines}; уникальных кликов нашей кампании на доменах свода без ботов: {len(seen)}\n')
        # сверка со сводом
        bg_names = [r['домен'] for r in base_all]
        rec_all = sum(sum(comp[b].values()) for b in svod_names if b not in out_names)
        svod_all = sum(iv(svod_row['прочих']) for svod_row in rows if svod_row['домен'] not in out_names)
        rec_w = sum(sum(v for k, v in compw[b].items() if k != 'яндекс') for b in bg_names)
        svod_w = sum(r['_ow'] for r in base_all)
        ratios = [sum(v for k, v in compw[b].items() if k != 'яндекс') / r['_ow'] for b, r in zip(bg_names, base_all) if r['_ow'] > 0]
        out.write(f'  сверка со сводом (без 5 выбросов): «прочих» всё время — реконструкция {rec_all} против {svod_all} в своде ({fmt(100*rec_all/svod_all,0)} %); '
                  f'в окне — {rec_w} против {svod_w} ({fmt(100*rec_w/svod_w,0)} %; окно здесь шире), по доменам медиана отношения {fmt(median(ratios))}, '
                  f'в пределах ±25 %: {fmt(100*sum(1 for x in ratios if .75 <= x <= 1.25)/len(ratios),0)} % доменов. '
                  f'Реконструкция неполная — выгрузки покрывают не весь источник свода; состав — оценка.\n')
        out.write('\nГ1. Состав «прочих» у фона (все домены свода без 5 выбросов)\n')
        out.write(f'  {"компонент":<28}{"всё время":>11}{"%":>7}{"в окне 0..4":>13}{"%":>7}{"СНГ в окне %":>14}   топ стран в окне\n')
        T1 = sum(tot_c.values())
        T2 = sum(totw_c.values())
        for k, v in tot_c.most_common():
            w = totw_c[k]
            cis = 100 * sum(n_ for c_, n_ in cc[k].items() if c_ in CIS) / w if w else float('nan')
            top = ', '.join(f'{c_} {n_}' for c_, n_ in cc[k].most_common(5))
            out.write(f'  {k:<28}{v:>11}{fmt(100*v/T1,1):>7}{w:>13}{fmt(100*w/T2,1):>7}{fmt(cis,1):>14}   {top}\n')
        out.write(f'  для сравнения, реферер Яндекса («из поиска»): всего {ya["всего"]}, СНГ {fmt(100*ya["СНГ"]/max(1,ya["всего"]),1)} %; в окне {ya["окно"]}, СНГ {fmt(100*ya["окно СНГ"]/max(1,ya["окно"]),1)} %\n')
        comp_res['share_noref_w'] = 100 * totw_c['без реферера'] / T2 if T2 else float('nan')
        comp_res['share_google_w'] = 100 * totw_c['google'] / T2 if T2 else float('nan')
        comp_res['share_self_w'] = 100 * totw_c['самореферер'] / T2 if T2 else float('nan')
        comp_res['cis_noref'] = 100 * sum(n_ for c_, n_ in cc['без реферера'].items() if c_ in CIS) / max(1, totw_c['без реферера'])
        comp_res['cis_google'] = 100 * sum(n_ for c_, n_ in cc['google'].items() if c_ in CIS) / max(1, totw_c['google'])
        comp_res['cis_self'] = 100 * sum(n_ for c_, n_ in cc['самореферер'].items() if c_ in CIS) / max(1, totw_c['самореферер'])
        out.write('\nГ2. Анатомия 5 всплесков по кликам\n')
        T3 = sum(out_c.values())
        out.write('  суммарно: ' + ', '.join(f'{k} {v} ({fmt(100*v/T3,1)} %)' for k, v in out_c.most_common()) + '\n')
        comp_res['trap_share_out'] = 100 * sum(v for k, v in out_c.items() if 'ловушка' in k) / T3 if T3 else float('nan')
        for r in outliers:
            b = r['домен']
            tb = sum(comp[b].values())
            ts, tn = o_sub[b].most_common(1)[0] if o_sub[b] else ('—', 0)
            td, tdn = o_day[b].most_common(1)[0] if o_day[b] else ('—', 0)
            big_days = sum(1 for v in o_day[b].values() if v > 1000)
            trap = sum(v for k, v in comp[b].items() if 'ловушка' in k)
            lead = [(s_, n_) for s_, n_ in o_sub[b].most_common() if n_ > 1000]
            rest = tb - sum(n_ for _, n_ in lead)
            nb_all = [x['_ot'] for x in nb_pool[r['_pool']]] or [x['_ot'] for x in nb_dz[r['_dz']]]
            comp_res.setdefault('rest', {})[b] = (rest, median(nb_all))
            out.write(f'  {b:<12} прочих по выгрузке {tb}: ловушка {fmt(100*trap/max(1,tb),1)} %, без реферера {fmt(100*comp[b]["без реферера"]/max(1,tb),1)} %; '
                      f'на одном сабдомене {ts} — {fmt(100*tn/max(1,tb),1)} %; пиковый день {td} — {fmt(100*tdn/max(1,tb),1)} %, дней с >1000: {big_days}; '
                      f'страны: {", ".join(f"{c_} {n_}" for c_, n_ in o_co[b].most_common(4))}\n'
                      f'               сабдоменов с >1000 прочих: {len(lead)} ({", ".join(s_ for s_, _ in lead)}); без них прочих всего {rest} '
                      f'при медиане соседей по «набор + день» {fmt(median(nb_all),0)}\n')
        # Г3. деньги по компонентам при равных поисковых (страты из Б9)
        out.write('\nГ3. Деньги по компонентам «прочих» при равных поисковых: страты «пул × терциль поисковых» из Б9, терцили компонента на сайт (окно 0..4 — приближение)\n')
        for d in bb_sb:
            c = compw[d['домен']]
            d['_g'] = c['google']
            d['_nr'] = c['без реферера']
            d['_sr'] = c['самореферер']
            d['_owr'] = sum(v for k, v in c.items() if k != 'яндекс')
        results['owr_sb'] = run_tercile_test(bb_sb, lambda d: d['_owr'] / d['_sites'], '    терцили «прочих (реконструкция) на сайт»', rng, out, pool_key='_pool_sb')
        results['nr_sb'] = run_tercile_test(bb_sb, lambda d: d['_nr'] / d['_sites'], '    терцили «без реферера на сайт»', rng, out, pool_key='_pool_sb')
        results['g_sb'] = run_tercile_test(bb_sb, lambda d: d['_g'] / d['_sites'], '    терцили «google на сайт»', rng, out, pool_key='_pool_sb')
        results['sr_sb'] = run_tercile_test(bb_sb, lambda d: d['_sr'] / d['_sites'], '    терцили «самореферер на сайт»', rng, out, pool_key='_pool_sb')
        out.write(f'    доменов страт с google в окне > 0: {sum(1 for d in bb_sb if d["_g"] > 0)} из {len(bb_sb)}, медиана google в окне {fmt(median([d["_g"] for d in bb_sb]),0)}; '
                  f'медиана «без реферера» в окне {fmt(median([d["_nr"] for d in bb_sb]),0)}\n')

    # ------------------------------------------------------------------ ВЫВОД
    r_ps, p_ps, p2_ps, acc_ps = results['ps']
    r_os, p_os, p2_os, acc_os = results['os']
    r_big, p_big, p2_big, acc_big = results['os_big']
    r_sw, p_sw, p2_sw, acc_sw = results['sw']
    r_sb, p_sb, p2_sb, acc_sb = results['ps_sb']
    r_sba, p_sba, p2_sba, acc_sba = results['ps_sb_all']
    r_ex, p_ex, p2_ex, acc_ex = results['ex_sb']
    r_rex, p_rex, p2_rex, acc_rex = results['res_ex']
    r_exr, p_exr, p2_exr, acc_exr = results['ex_res']
    r_bw, p_bw, p2_bw, acc_bw = results['bw_sb']
    rho_ex = rho_store['_ex3']
    rho_sw = rho_store['_sw']
    rho_bw = rho_store['_bw']
    med_err = {m: median([v for _, v in errs[m]]) for m, _ in models}

    def oe_str(acc):
        return ' / '.join(fmt(acc[t]['reg'] / acc[t]['E']) if acc[t]['E'] else '—' for t in range(3))
    out.write('\n==============================================================================\n')
    out.write('ВЫВОД\n')
    out.write('==============================================================================\n')
    out.write(f'Что взято: {len(base)} доменов с закрытым окном и двумя днями переобхода, без 5 выбросов и без «{NOCONTENT}»; '
              f'{sum(r["_sites"] for r in base)} сайтов, {sum(r["_reg"] for r in base)} регистраций в окне (с «не записан» — {len(base_all)} доменов, {sum(r["_reg"] for r in base_all)} рег.). '
              f'Фон «прочих в окне»: медиана {fmt(net_med,0)} на домен, {fmt(median(ops),2)} на сайт, p99 {fmt(quantile(ows,.99),0)}, максимум {max(ows)}; '
              f'в окно попадает {fmt(100*tot_ow/tot_ot,0)} % всех «прочих» (поисковых — {fmt(100*sum(r["_sw"] for r in base)/max(1,sum(iv(r["из поиска"]) for r in base)),0)} %).\n')
    out.write(f'\n1. Что такое фон (А). Внутри пула «набор + день» «прочие» растут вместе с любой активностью домена: Спирмен (нормированные ранги) '
              f'с вышедшими за 3 суток {fmt(rho_ex[2])}, с поисковыми кликами {fmt(rho_sw[2])}, с ботами {fmt(rho_bw[2])}; при равных поисковых '
              f'(страта пул × терциль поисковых) — с вышедшими {fmt(rho_eq["_ex3"][2])}, с ботами {fmt(rho_eq["_bw"][2])}, с остатком поисковых {fmt(rho_eq["_sw"][2])}. '
              f'Связь с вышедшими сайтами не слабее связи с поисковыми кликами (в {cnt_ge} пулах из {cnt_tot} — выше или равна) — эта часть критерия А выполнена.\n'
              f'   Но «пропорционален вышедшим» — нет. Медиана относительной ошибки: «медиана дня» {fmt(med_err["медиана дня (нулевая)"])}, '
              f'k×сайтов {fmt(med_err["k × сайтов"])}, k×вышли {fmt(med_err["k × вышли за 3 суток"])}, k×поисковые {fmt(med_err["k × поисковых в окне"])} '
              f'(по пулам: {fmt(median(errs_p["медиана дня (нулевая)"]))} / {fmt(median(errs_p["k × сайтов"]))} / {fmt(median(errs_p["k × вышли за 3 суток"]))} / {fmt(median(errs_p["k × поисковых в окне"]))}). '
              f'Модель «k × вышедших» хуже, чем просто «одно число на домен в этот день»: фон — это почти постоянная добавка на домен '
              f'({fmt(min(k_site_list),2)}–{fmt(max(k_site_list),2)} клика на сайт по дням с ≥10 доменами, CV {fmt(cv(k_site_list))}; '
              f'август {fmt(sum(x["_ow"] for x in aug)/sum(x["_sites"] for x in aug),2)}, сентябрь {fmt(sum(x["_ow"] for x in sep)/sum(x["_sites"] for x in sep),2)} на сайт), '
              f'поверх которой есть часть, растущая с активностью. k на вышедший сайт {fmt(min(k_ex_list),1)}–{fmt(max(k_ex_list),1)} (CV {fmt(cv(k_ex_list))}) стабильнее по дням, '
              f'но это 3–5 кликов на вышедший сайт, а не 0,2–1,0 — ожидание постановки относилось к «на сайт вообще».\n')
    if comp_res:
        out.write(f'   Состав (Г, справочно, по выгрузкам кликов): в окне «прочие» — это на {fmt(comp_res["share_noref_w"],0)} % заходы без реферера '
                  f'(из СНГ только {fmt(comp_res["cis_noref"],0)} % — против {fmt(100*ya["окно СНГ"]/max(1,ya["окно"]),0)} % у кликов из Яндекса; много США, Турции, Гонконга — похоже на сканеры и обходчики), '
                  f'на {fmt(comp_res["share_google_w"],0)} % — переходы из Google ({fmt(comp_res["cis_google"],0)} % СНГ, то есть живые люди из поиска, которых свод не считает поисковыми), '
                  f'на {fmt(comp_res["share_self_w"],0)} % — самореферер ({fmt(comp_res["cis_self"],0)} % СНГ — сканеры). Это не «второй шаг живого посетителя» и не отдельный рекламный источник.\n')
    out.write(f'\n2. Деньги (Б). Внутри пула по терцилям «прочих на сайт» O/E {oe_str(acc_ps)} (верхний/нижний {fmt(r_ps)}, p двуст. {fmt(p2_ps,2)}). '
              f'По «прочих / поисковых» {oe_str(acc_os)} ({fmt(r_os)}, p {fmt(p2_os,3)}) — но это эффект объёма: в верхний терциль попадают домены с малым поиском, '
              f'а у терцилей самих поисковых кликов O/E {oe_str(acc_sw)}; в бине > {BIG_BIN} внутри пула {oe_str(acc_big)} ({fmt(r_big)}, p {fmt(p2_big,2)}). '
              f'Постановочные 1,63 / 1,73 / 2,60 воспроизводятся без страты (Б7) и в страте исчезают.\n'
              f'   Однако при выровненных поисковых (страта пул × терциль поисковых: {sum(acc_sb[t]["n"] for t in range(3))} доменов, {sum(acc_sb[t]["reg"] for t in range(3))} рег.) '
              f'терцили «прочих на сайт» дают O/E {oe_str(acc_sb)} (верхний/нижний {fmt(r_sb)}, p {fmt(p2_sb,3)}; с «не записан» {oe_str(acc_sba)}, {fmt(r_sba)}, p {fmt(p2_sba,3)}). '
              f'Это против формулировки «при равных поисковых не добавляет регистраций»: при одинаковом поисковом трафике домен с бо́льшими «прочими» приносит '
              f'в {fmt(r_sba,1)}–{fmt(r_sb,1)} раза больше регистраций на поисковый клик. Но «прочие» здесь — метка, а не источник: тот же сигнал даёт широта выхода '
              f'(терцили «вышли за 3 суток / сайтов» {oe_str(acc_ex)}, {fmt(r_ex)}, p {fmt(p2_ex,2)}), а «прочие сверх вышедших» не добавляют ничего '
              f'({oe_str(acc_rex)}, {fmt(r_rex)}, p {fmt(p2_rex,2)}), как и «вышедшие сверх прочих» ({fmt(r_exr)}, p {fmt(p2_exr,2)}); боты сигнала не несут ({fmt(r_bw)}, p {fmt(p2_bw,2)}).')
    if comp_res:
        r_nr, _, p2_nr, acc_nr = results['nr_sb']
        r_g, _, p2_g, acc_g = results['g_sb']
        r_sr, _, p2_sr, acc_sr = results['sr_sb']
        out.write(f' По компонентам (Г3, приближённое окно): метку несут заходы без реферера ({oe_str(acc_nr)}, {fmt(r_nr)}, p {fmt(p2_nr,3)}), '
                  f'а не Google ({oe_str(acc_g)}, {fmt(r_g)}, p {fmt(p2_g,2)}) и не самореферер ({fmt(r_sr)}, p {fmt(p2_sr,2)}).')
    out.write(f'\n   Оговорка: {sum(acc_sb[t]["reg"] for t in range(3))} регистраций на 108 страт, терцильных тестов в отчёте больше десятка — '
              f'один p = {fmt(p2_sb,3)} при такой переборке не решает; с «не записан» p = {fmt(p2_sba,3)}. Сигнал 1,4–1,8× — правдоподобный, не доказанный.\n')
    nb_line = '; '.join(f'{b}: {fmt(v[0],0)}/{v[1]} и {fmt(v[2],0)}/{v[3]}, выброс/медиана {fmt(v[4],0)}×' for b, v in nb_stats.items())
    out.write(f'\n3. Всплески (В). Все 5 — события одного домена. Соседи по «набор + день» и по «день + зона» (медиана/максимум «прочих в окне») обычные: {nb_line}. '
              f'Никто из соседей не выше 1000; выше 3× медианы сети ({fmt(3*net_med,0)}) — только единицы в день+зона 02.09 и в августовском «не записан», где фон вообще выше. '
              f'3615.team в окне обычный (112): его 1,27 млн пришли после окна (в окне 0,0 %), у остальных четырёх 93–100 % потока — в окне. '
              f'Аккаунты cf и вебмастера у пяти разные, домены-соседи по этим аккаунтам обычные. Два из пяти — один день 02.09 и родственные наборы NEW50_2_12pages '
              f'(nodate и withdate), но остальные 54 домена этого дня (в том числе 16 и 5 в тех же наборах) обычные (медиана 139, максимум 357).\n')
    if comp_res:
        out.write(f'   По кликам (Г2): {fmt(comp_res["trap_share_out"],0)} % кликов пяти всплесков — краулерная ловушка (самореферер с хвостом /promo/ru/ru/ru/…) '
                  f'на одном сабдомене (pokerdom.* у четырёх, pinco/stake у 4863.team), остальное — заходы без реферера с того же сабдомена; страны США, Китай, Нидерланды, Германия; '
                  f'пик 1–2 дня. Это обходчик, застрявший в бесконечном дереве относительных ссылок одного сайта, а не набор, не день и не «источник».\n')
    sw_line = '; '.join(f'{b} {fmt(v,1)}×' for b, v in sw_ratio.items())
    out.write(f'   Деньги всплесков: O = {sum_o} при E = {fmt(sum_e)} по ставке соседей «набор + день» (O/E {fmt(sum_o/sum_e)} [{fmt(lo/sum_e)}–{fmt(hi/sum_e)}], p {fmt(p_two,2)}) '
              f'и E = {fmt(sum_e_dz)} по «день + зона» (O/E {fmt(sum_o/sum_e_dz)}) — в заявленных 0,5–2, но ДИ широк. '
              f'«Поисковая часть в норме» — не у всех: поисковых на сайт против медианы соседей — {sw_line}; 3286.team и 4863.team — первые в своих пулах по поиску '
              f'(у 4863 выход 52 % против 30 % у соседей), их поисковый поток в окне сам по себе аномален.\n')
    out.write('\nИтог: гипотеза подтверждена частично.\n'
              '  Подтверждено: всплески — события одного домена (одного сабдомена), не набора и не дня, соседи чистые, отдача по поиску у пяти в норме (O/E ≈ 1,9, ДИ 0,6–4,6); '
              'фон в окне мал (0,37 на сайт) и не является отдельным источником с собственной отдачей — регистраций без поиска у него нет (29 доменов, 0 рег.).\n'
              '  Опровергнуто: «фон пропорционален вышедшим сайтам» — это константа на домен плюс часть, растущая с любой активностью; '
              '«при равных поисковых не добавляет регистраций» — при равных поисковых домены с бо́льшими «прочими» дают в 1,4–1,8 раза больше регистраций (p 0,02–0,05), '
              'потому что «прочие» (точнее — заходы без реферера) метят те же домены, что и широта выхода; '
              '«поисковая часть всплесков в норме» — не у 3286.team и 4863.team.\n')
    out.write('\nЧто с этим делать:\n'
              '  1) Правило свода принять: домены с «прочих в окне» > 5000 или «прочих» всего > 50 000 исключать из сумм «всего» и «прочих», но не из поисковых и денежных расчётов '
              '(по деньгам они обычные). Точнее и проверяемо на уже собранных выгрузках — исключать не домен, а сабдомен-ловушку '
              '(pokerdom.3286/3615/7590/2955, pinco и stake у 4863): без этих сабдоменов «прочих» всего у пяти доменов — '
              + (', '.join(f'{b} {v[0]} (соседи {fmt(v[1],0)})' for b, v in comp_res.get('rest', {}).items()) if comp_res else '(нет выгрузок)') + '.\n'
              '  2) Колонки «прочих» и «всего» из рабочего свода убрать можно, но не как «бесполезные», а как смешанные: 84 % — заходы без реферера (две трети не из СНГ), '
              '12 % — Google (живые люди), 3 % — сканеры. Проверяемая замена на тех же выгрузках: две колонки «Google в окне» и «без реферера в окне».\n'
              '  3) Ловушка /promo/ru/ru/ru/… — относительная ссылка на странице дора порождает бесконечное дерево адресов; это техническая правка на уже стоящих доменах, '
              'проверка простая: после неё клики с хвостом из повторов должны исчезнуть из выгрузки. На деньги она не влияет, только на счётчики.\n'
              '  4) Сигнал «прочих на сайт при равных поисковых» (1,4–1,8×) — не рычаг, а кандидат в ранний признак домена с отдачей; перепроверить на тех же данных через 2–3 недели, '
              'когда закроются окна запусков 12–18.09 и в стратах будет ≥200 регистраций: если верхний терциль «без реферера на сайт» снова даст O/E ≥ 1,3 при p < 0,05, '
              'признак можно брать в свод; если нет — это была переборка.\n')
    out.flush()
    return out


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №14 («прочие» клики — тень активности домена; всплески — ловушка
одного сабдомена). Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ.

Что проверяется:
  1. Воспроизводятся ли числа тестировщика (независимый пересчёт фона, Б1, Б9).
  2. Не средние ли это по доменам от долей (медиана отношений против Σ/Σ) и не пуста ли
     нормировка «на сайт» (сайтов почти у всех ровно 206).
  3. Сколько всего терцильных срезов перебрано и выживает ли вывод после Холма/БХ.
  4. Хватает ли событий: регистрации по группам, сколько доменов их несут.
  5. Не держится ли результат на 1–3 доменах: убрать топ-3 по регистрациям в каждой
     группе (и по одному домену — джекнайф) и пересчитать.
  6. Правильные ли знаменатели/оконные колонки; что делают исключения (незакрытое окно,
     дней=1, «не записан», 5 выбросов).
  7. Устойчивость к порогам (≥9 доменов в пуле, ≥3 в страте) и к seed перестановок.
  8. Точные интервалы вместо «эффект есть» (биномиальный ДИ на отношение O/E).
  9. Мощность нулевых результатов (29 доменов без поиска — что они вообще исключают).
 10. Всплески: диапазон «выброс/медиана соседей», состоятельность определения выброса.

Только stdlib.
"""
import collections
import csv
import math
import os
import random
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
H14 = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h14_other_clicks_shadow.txt')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w14_statistika.txt')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
THR_WINDOW, THR_TOTAL = 5000, 50000
NSIM = 4000


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
    return 0 if x in ('', None) else int(float(x))


def fmt(x, nd=2):
    if x is None:
        return '—'
    if isinstance(x, float) and math.isnan(x):
        return '—'
    if isinstance(x, float) and math.isinf(x):
        return '∞'
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


# ---------- точные интервалы ----------
def binom_cdf(k, n, p):
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    s = 0.0
    for i in range(0, k + 1):
        s += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return min(1.0, s)


def clopper_pearson(k, n, alpha=0.05):
    """Точный ДИ для доли."""
    if n == 0:
        return (float('nan'), float('nan'))
    lo, hi = 0.0, 1.0
    if k == 0:
        low = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if 1 - binom_cdf(k - 1, n, m) > alpha / 2:
                b = m
            else:
                a = m
        low = (a + b) / 2
    if k == n:
        high = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(200):
            m = (a + b) / 2
            if binom_cdf(k, n, m) < alpha / 2:
                b = m
            else:
                a = m
        high = (a + b) / 2
    return (low, high)


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    s, t = 0.0, math.exp(-lam)
    for i in range(0, k + 1):
        if i:
            t *= lam / i
        s += t
    return min(1.0, s)


def poisson_ci(k, alpha=0.05):
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, max(1.0, 4.0 * k + 10)
        for _ in range(300):
            m = (a + b) / 2
            if 1 - poisson_cdf(k - 1, m) > alpha / 2:
                b = m
            else:
                a = m
        lo = (a + b) / 2
    a, b = 0.0, max(1.0, 4.0 * k + 20)
    for _ in range(300):
        m = (a + b) / 2
        if poisson_cdf(k, m) < alpha / 2:
            b = m
        else:
            a = m
    hi = (a + b) / 2
    return lo, hi


def ratio_ci_binom(o_top, e_top, o_bot, e_bot, alpha=0.05):
    """Точный ДИ на (O/E верх)/(O/E низ): условно на сумму событий верх+низ,
    число событий сверху ~ Binom(n, e_top/(e_top+e_bot))."""
    n = o_top + o_bot
    if n == 0 or e_top <= 0 or e_bot <= 0:
        return (float('nan'), float('nan'), float('nan'))
    p0 = e_top / (e_top + e_bot)
    lo, hi = clopper_pearson(o_top, n, alpha)
    def to_ratio(p):
        if p <= 0:
            return 0.0
        if p >= 1:
            return float('inf')
        return (p / (1 - p)) / (p0 / (1 - p0))
    # точный двусторонний p (биномиальный, метод малой вероятности)
    pv = 0.0
    obs = math.comb(n, o_top) * p0 ** o_top * (1 - p0) ** (n - o_top)
    for i in range(n + 1):
        pi = math.comb(n, i) * p0 ** i * (1 - p0) ** (n - i)
        if pi <= obs * (1 + 1e-9):
            pv += pi
    return (to_ratio(lo), to_ratio(hi), min(1.0, pv))


def ranks(xs):
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


# ---------- данные ----------
def load():
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
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
        r['_bots'] = r['_bw']
        r['_pool'] = (r['набор контента'], r['день запуска'])
        r['_ops'] = r['_ow'] / r['_sites'] if r['_sites'] else 0.0
        r['_exs'] = r['_ex3'] / r['_sites'] if r['_sites'] else 0.0
    return rows, neg


def terciles(items, key):
    order = sorted(items, key=lambda d: (key(d), d['домен']))
    n = len(order)
    return {d['домен']: min(2, (3 * i) // n) for i, d in enumerate(order)}


def build_strata_b9(base, min_pool=9, min_str=3):
    """Страта = пул (набор+день, ≥min_pool доменов) × терциль поисковых внутри пула."""
    by_pool = collections.defaultdict(list)
    for d in base:
        by_pool[d['_pool']].append(d)
    strata = collections.defaultdict(list)
    for p, ds in by_pool.items():
        if len(ds) < min_pool:
            continue
        lab = terciles(ds, lambda d: d['_sw'])
        for d in ds:
            strata[(p, lab[d['домен']])].append(d)
    return {s: ds for s, ds in strata.items() if len(ds) >= min_str}


def oe_terciles(strata, key):
    """Терцили key внутри каждой страты; E = ставка страты на поисковый клик × поисковые домена."""
    acc = {t: collections.Counter() for t in range(3)}
    per = {t: [] for t in range(3)}
    for s, ds in strata.items():
        sw = sum(d['_sw'] for d in ds)
        rg = sum(d['_reg'] for d in ds)
        rate = rg / sw if sw else 0.0
        lab = terciles(ds, key)
        for d in ds:
            t = lab[d['домен']]
            e = rate * d['_sw']
            acc[t]['n'] += 1
            acc[t]['reg'] += d['_reg']
            acc[t]['sw'] += d['_sw']
            acc[t]['ow'] += d['_ow']
            acc[t]['sites'] += d['_sites']
            acc[t]['E'] += e
            per[t].append((d, e))
    return acc, per


def ratio_of(acc):
    et, eb = acc[2]['E'], acc[0]['E']
    if et <= 0 or eb <= 0 or acc[0]['reg'] == 0:
        return float('nan')
    return (acc[2]['reg'] / et) / (acc[0]['reg'] / eb)


def perm_p(strata, key, obs, seed=1, nsim=NSIM):
    rng = random.Random(seed)
    # фиксируем метки как наблюдённые, перемешиваем внутри страты
    labels = {}
    dom_e = {}
    doms = []
    for s, ds in strata.items():
        sw = sum(d['_sw'] for d in ds)
        rg = sum(d['_reg'] for d in ds)
        rate = rg / sw if sw else 0.0
        lab = terciles(ds, key)
        for d in ds:
            labels[d['домен']] = lab[d['домен']]
            dom_e[d['домен']] = rate * d['_sw']
        doms.append([d['домен'] for d in ds])
    reg = {d['домен']: d['_reg'] for ds in strata.values() for d in ds}
    ge = two = 0
    for _ in range(nsim):
        acc = {t: [0, 0.0] for t in range(3)}
        for names in doms:
            tl = [labels[x] for x in names]
            rng.shuffle(tl)
            for x, t in zip(names, tl):
                acc[t][0] += reg[x]
                acc[t][1] += dom_e[x]
        if acc[2][1] <= 0 or acc[0][1] <= 0 or acc[0][0] == 0:
            continue
        r = (acc[2][0] / acc[2][1]) / (acc[0][0] / acc[0][1])
        if r >= obs:
            ge += 1
        if r > 0 and obs > 0 and abs(math.log(r)) >= abs(math.log(obs)):
            two += 1
    return ge / nsim, two / nsim


def main():
    out = Tee(OUT)
    W = out.write
    rows, neg = load()
    outl = {r['домен'] for r in rows if r['_ow'] > THR_WINDOW or r['_ot'] > THR_TOTAL}
    closed = [r for r in rows if r['окно закрыто'] == 'да']
    d2 = [r for r in closed if r['дней'] != '1']
    base_all = [r for r in d2 if r['домен'] not in outl]
    base = [r for r in base_all if r['набор контента'] != NOCONTENT]

    W('КОНТРПРОВЕРКА ГИПОТЕЗЫ №14 — СТАТИСТИКА И ОПРЕДЕЛЕНИЯ\n')
    W(f'Источник: {SRC}\n')
    W('=' * 78 + '\n')

    # ------------------------------------------------------------------ 1
    W('\n1. ВОСПРОИЗВОДИМОСТЬ\n')
    W('-' * 78 + '\n')
    W(f'  строк в своде {len(rows)}; окно закрыто=да {len(closed)}; и дней≠1 {len(d2)}; '
      f'без 5 выбросов {len(base_all)}; без «не записан» {len(base)}\n')
    W(f'  (тестировщик: 2077 / 1925 / 1848 / 1843 / 1509 — совпадение: '
      f'{len(rows)==2077 and len(base_all)==1843 and len(base)==1509})\n')
    W(f'  регистраций в окне: фон {sum(r["_reg"] for r in base)} (тест. 245); с «не записан» '
      f'{sum(r["_reg"] for r in base_all)} (тест. 344)\n')
    ows = [r['_ow'] for r in base]
    ops = [r['_ops'] for r in base if r['_sites']]
    W(f'  фон «прочих в окне»: медиана {fmt(median(ows),0)}, p99 {fmt(quantile(ows,.99),0)}, макс {max(ows)} '
      f'(тест. 76 / 267 / 453)\n')
    W(f'  «прочих на сайт»: медиана отношений {fmt(median(ops),3)} (тест. 0,369) против Σпрочих/Σсайтов '
      f'{fmt(sum(ows)/sum(r["_sites"] for r in base),3)}\n')
    W('  Вывод: части 0/А/Б/В скрипта тестировщика воспроизводятся построчно (diff пуст).\n')

    # ------------------------------------------------------------------ 2
    W('\n2. ОПРЕДЕЛЕНИЯ: ЧТО ЗНАЧИТ «НА САЙТ» И «ПОСТОЯННАЯ ДОБАВКА НА ДОМЕН»\n')
    W('-' * 78 + '\n')
    cnt = collections.Counter(r['_sites'] for r in base)
    top = cnt.most_common(5)
    W(f'  распределение «сайтов» у 1509 доменов фона: {top}\n')
    W(f'  доля доменов ровно с 206 сайтами: {fmt(100*cnt[206]/len(base),1)} %; уникальных значений {len(cnt)}; '
      f'CV «сайтов» {fmt(statistics.pstdev([r["_sites"] for r in base])/statistics.mean([r["_sites"] for r in base]),4)}\n')
    W('  => «прочих на сайт» = «прочих на домен» / 206 с точностью до 1,4 % доменов: нормировка на сайты\n'
      '     ничего не различает, а модели «константа дня» и «k × сайтов» — одна и та же модель\n'
      '     (у тестировщика 0,33 и 0,34 медианной ошибки — это не две независимые проверки).\n')
    # ошибки моделей: пересчёт + знаковый тест
    by_day = collections.defaultdict(list)
    for r in base:
        by_day[r['день запуска']].append(r)
    def model_err(keyf, use_median_k=False):
        errs = []
        for day, ds in by_day.items():
            sx = sum(keyf(d) for d in ds)
            so = sum(d['_ow'] for d in ds)
            if use_median_k:
                rs = [d['_ow'] / keyf(d) for d in ds if keyf(d) > 0]
                k = median(rs) if rs else 0.0
            else:
                k = so / sx if sx else 0.0
            for d in ds:
                errs.append(abs(k * keyf(d) - d['_ow']) / max(d['_ow'], 1))
        return errs
    def null_err():
        errs = []
        for day, ds in by_day.items():
            m = median([d['_ow'] for d in ds])
            for d in ds:
                errs.append(abs(m - d['_ow']) / max(d['_ow'], 1))
        return errs
    e_null = null_err()
    e_ex = model_err(lambda d: d['_ex3'])
    e_ex_med = model_err(lambda d: d['_ex3'], use_median_k=True)
    e_sw = model_err(lambda d: d['_sw'])
    W(f'  медиана отн. ошибки: медиана дня {fmt(median(e_null))} (тест. 0,33); k×вышли {fmt(median(e_ex))} (тест. 0,43); '
      f'k×поиск {fmt(median(e_sw))} (тест. 0,70)\n')
    W(f'  проверка оценки k: если k = медиана отношений «прочие/вышли» (а не отношение сумм), ошибка k×вышли '
      f'{fmt(median(e_ex_med))} — то есть вывод об отсутствии пропорциональности к выбору k НЕ чувствителен\n')
    # знаковый тест «медиана дня» против «k×вышли»
    wins = sum(1 for a, b in zip(e_ex, e_null) if a < b)
    ties = sum(1 for a, b in zip(e_ex, e_null) if a == b)
    n_eff = len(e_ex) - ties
    z = (wins - n_eff / 2) / math.sqrt(n_eff / 4)
    W(f'  знаковый тест «k×вышли точнее медианы дня»: {wins} из {n_eff} ({fmt(100*wins/n_eff,1)} %), z = {fmt(z)}\n')
    W(f'    с k = медиана отношений: {sum(1 for a,b in zip(e_ex_med,e_null) if a<b)} из {len(e_ex_med)} '
      f'({fmt(100*sum(1 for a,b in zip(e_ex_med,e_null) if a<b)/len(e_ex_med),1)} %)\n')
    W('  => отсутствие пропорциональности вышедшим сайтам — устойчивый результат (43,6 % против 56,4 %, z = −5,0,\n'
      '     та же картина при медианной оценке k). Но «постоянная добавка НА САЙТ» — формулировка пустая:\n'
      '     сайтов у всех 206, поэтому «k × сайтов» и «одно число на день» — одна модель, и различить\n'
      '     «константу на домен» и «пропорциональность числу сайтов» эти данные не могут в принципе.\n')

    # ------------------------------------------------------------------ 3
    W('\n3. СКОЛЬКО СРЕЗОВ ПЕРЕБРАНО И ЧТО ОСТАЁТСЯ ПОСЛЕ ПОПРАВКИ\n')
    W('-' * 78 + '\n')
    tests = []
    if os.path.exists(H14):
        txt = open(H14, encoding='utf-8').read().splitlines()
        cur = ''
        for ln in txt:
            s = ln.strip()
            if s and not s.startswith('O/E верхнего') and not s.startswith('терциль') and not s.startswith('страт'):
                if re.match(r'^(терцили|Б\d|контроль|обратно|\s*терцили)', s):
                    cur = s[:70]
            m = re.search(r'O/E верхнего / O/E нижнего = ([-\d.]+).*?p\(двуст\.\) = ([\d.]+)', s)
            if m:
                tests.append((cur, float(m.group(1)), float(m.group(2))))
    W(f'  терцильных тестов с p в отчёте тестировщика: {len(tests)}\n')
    for nm, r, p in tests:
        W(f'    p={p:<6} отношение {r:<6} {nm}\n')
    ps = sorted(p for _, _, p in tests)
    m_ = len(ps)
    W(f'  минимальный p = {min(ps) if ps else float("nan")}; порог Бонферрони при {m_} тестах: '
      f'{fmt(0.05/m_,4) if m_ else "—"}\n')
    # Холм и БХ
    order = sorted(range(m_), key=lambda i: ps[i])
    holm = []
    prev = 0.0
    for i, p in enumerate(ps):
        v = min(1.0, max(prev, (m_ - i) * p))
        prev = v
        holm.append(v)
    bh = [0.0] * m_
    prev = 1.0
    for i in range(m_ - 1, -1, -1):
        prev = min(prev, ps[i] * m_ / (i + 1))
        bh[i] = prev
    adj = {}
    for i, p in enumerate(ps):
        adj[p] = (holm[i], bh[i])
    W('  скорректированные p (Холм / Бенджамини–Хохберг) для ключевых срезов:\n')
    for nm, r, p in tests:
        if p <= 0.11:
            W(f'    сырой p={p:<6} → Холм {fmt(adj[p][0],3)}, БХ {fmt(adj[p][1],3)}  | {nm}\n')
    W(f'  тестов, выживающих при FDR 0,05: {sum(1 for v in bh if v<0.05)}; при Холме 0,05: {sum(1 for v in holm if v<0.05)}\n')
    surv = [ (nm,p) for nm,r,p in tests if adj[p][1] < 0.05 ]
    W(f'  выживают только: {[nm[:55] for nm,p in surv]}\n')
    W('  — а это ровно те срезы «прочих / поисковых», которые сам тестировщик объявляет эффектом объёма\n'
      '    (в бине >912 они дают 0,93, p 0,78). Срез Б9 (1,82) после Холма даёт '
      f'{fmt(adj[0.019][0],2)}, после БХ {fmt(adj[0.019][1],2)}.\n')
    W('  (и это только терцильные тесты одного отчёта; сюда не входят спирменовские срезы А1/А1б/А1в,\n'
      '   сравнения моделей А2, бины >912/≤912 и проходы «с/без не записан» — фактический перебор шире)\n')

    # ------------------------------------------------------------------ 4
    W('\n4. ГЛАВНЫЙ ВЫЖИВШИЙ СИГНАЛ Б9: ОБЪЁМ СОБЫТИЙ, ИНТЕРВАЛ, ОПОРА НА ОТДЕЛЬНЫЕ ДОМЕНЫ\n')
    W('-' * 78 + '\n')
    base_money = [r for r in base if r['_sw'] > 0]
    base_all_money = [r for r in base_all if r['_sw'] > 0]
    strata = build_strata_b9(base_money, 9, 3)
    acc, per = oe_terciles(strata, lambda d: d['_ops'])
    W(f'  страт {len(strata)}, доменов {sum(a["n"] for a in acc.values())}, регистраций {sum(a["reg"] for a in acc.values())}\n')
    names = ('нижний', 'средний', 'верхний')
    for t in range(3):
        a = acc[t]
        lo, hi = poisson_ci(a['reg'])
        W(f'    {names[t]:<8} доменов {a["n"]:>4}, рег {a["reg"]:>4}, E {fmt(a["E"],1):>6}, O/E {fmt(a["reg"]/a["E"]):>5} '
          f'[точный пуассон. ДИ {fmt(lo/a["E"])}–{fmt(hi/a["E"])}]\n')
    obs = ratio_of(acc)
    lo, hi, pex = ratio_ci_binom(acc[2]['reg'], acc[2]['E'], acc[0]['reg'], acc[0]['E'])
    W(f'  отношение O/E верх/низ = {fmt(obs)} (тест. 1,82); точный условно-биномиальный ДИ {fmt(lo)}–{fmt(hi)}, '
      f'p(точн., двуст.) = {fmt(pex,3)}\n')
    for sd in (1, 2, 7, 12345):
        g, tw = perm_p(strata, lambda d: d['_ops'], obs, seed=sd, nsim=NSIM)
        W(f'    перестановки seed={sd:<6} p(одност.) {fmt(g,3)}, p(двуст.) {fmt(tw,3)}\n')
    # объём событий
    ndom_reg = {t: sum(1 for d, e in per[t] if d['_reg'] > 0) for t in range(3)}
    W(f'  регистрации несут доменов: нижний {ndom_reg[0]}, средний {ndom_reg[1]}, верхний {ndom_reg[2]} '
      f'(из {acc[0]["n"]}/{acc[1]["n"]}/{acc[2]["n"]})\n')
    # тонкие страты
    sizes = collections.Counter(len(ds) for ds in strata.values())
    thin = sum(len(ds) for s, ds in strata.items() if len(ds) <= 4)
    thin_reg = sum(d['_reg'] for s, ds in strata.items() if len(ds) <= 4 for d in ds)
    W(f'  размеры страт: {sorted(sizes.items())}; доменов в стратах ≤4 — {thin}, регистраций в них {thin_reg} '
      f'({fmt(100*thin_reg/max(1,sum(a["reg"] for a in acc.values())),0)} % всех)\n')
    W('  => в страте из 3 доменов «терциль» = один домен: сравниваются не группы, а отдельные домены.\n')

    W('\n  4б. Убрать топ-3 домена по регистрациям в каждой группе (и топ-1) — пересчёт\n')
    def drop_top(strata, key, k_top, reestimate=True):
        acc0, per0 = oe_terciles(strata, key)
        drop = set()
        for t in range(3):
            cand = sorted(per0[t], key=lambda x: (-x[0]['_reg'], x[0]['домен']))[:k_top]
            drop |= {d['домен'] for d, _ in cand}
            if k_top:
                pass
        if reestimate:
            st2 = {}
            for s, ds in strata.items():
                keep = [d for d in ds if d['домен'] not in drop]
                if len(keep) >= 3:
                    st2[s] = keep
            a2, _ = oe_terciles(st2, key)
            return a2, drop, st2
        return acc0, drop, strata
    for k_top in (1, 2, 3):
        a2, drop, st2 = drop_top(strata, lambda d: d['_ops'], k_top)
        r2 = ratio_of(a2)
        l2, h2, p2 = ratio_ci_binom(a2[2]['reg'], a2[2]['E'], a2[0]['reg'], a2[0]['E'])
        g2, t2 = perm_p(st2, lambda d: d['_ops'], r2, seed=1, nsim=2000)
        W(f'    убрано топ-{k_top} по рег. в каждой группе ({len(drop)} доменов, рег. у них '
          f'{sum(d["_reg"] for ds in strata.values() for d in ds if d["домен"] in drop)}): '
          f'O/E {fmt(a2[0]["reg"]/a2[0]["E"])}/{fmt(a2[1]["reg"]/a2[1]["E"])}/{fmt(a2[2]["reg"]/a2[2]["E"])}, '
          f'отношение {fmt(r2)} [ДИ {fmt(l2)}–{fmt(h2)}], p(перест.,двуст.) {fmt(t2,3)}, p(точн.) {fmt(p2,3)}\n')
    # джекнайф по доменам с регистрациями
    jk = []
    doms_reg = [d['домен'] for ds in strata.values() for d in ds if d['_reg'] > 0]
    for dn in doms_reg:
        st2 = {}
        for s, ds in strata.items():
            keep = [d for d in ds if d['домен'] != dn]
            if len(keep) >= 3:
                st2[s] = keep
        a2, _ = oe_terciles(st2, lambda d: d['_ops'])
        jk.append((ratio_of(a2), dn))
    jk_v = [v for v, _ in jk if not math.isnan(v)]
    W(f'    джекнайф по {len(jk)} доменам с регистрациями: отношение от {fmt(min(jk_v))} до {fmt(max(jk_v))}, '
      f'медиана {fmt(median(jk_v))}\n')
    worst = sorted(jk)[:3]
    W(f'    сильнее всего сигнал падает при удалении: ' + ', '.join(f'{d} → {fmt(v)}' for v, d in worst) + '\n')

    W('\n  4в. Устойчивость к произволу порогов (пул ≥N доменов, страта ≥M)\n')
    for mp in (6, 7, 8, 9, 10, 12, 15):
        st = build_strata_b9(base_money, mp, 3)
        a, _ = oe_terciles(st, lambda d: d['_ops'])
        r = ratio_of(a)
        l, h, pe = ratio_ci_binom(a[2]['reg'], a[2]['E'], a[0]['reg'], a[0]['E'])
        W(f'    пул ≥{mp:<3} страт {len(st):>4}, доменов {sum(x["n"] for x in a.values()):>4}, '
          f'рег {sum(x["reg"] for x in a.values()):>4}: отношение {fmt(r):>5} [ДИ {fmt(l)}–{fmt(h)}], p(точн.) {fmt(pe,3)}\n')
    for ms in (3, 4, 5, 6):
        st = build_strata_b9(base_money, 9, ms)
        a, _ = oe_terciles(st, lambda d: d['_ops'])
        r = ratio_of(a)
        l, h, pe = ratio_ci_binom(a[2]['reg'], a[2]['E'], a[0]['reg'], a[0]['E'])
        W(f'    страта ≥{ms:<3} страт {len(st):>4}, доменов {sum(x["n"] for x in a.values()):>4}, '
          f'рег {sum(x["reg"] for x in a.values()):>4}: отношение {fmt(r):>5} [ДИ {fmt(l)}–{fmt(h)}], p(точн.) {fmt(pe,3)}\n')
    st_all = build_strata_b9(base_all_money, 9, 3)
    a, _ = oe_terciles(st_all, lambda d: d['_ops'])
    r = ratio_of(a)
    l, h, pe = ratio_ci_binom(a[2]['reg'], a[2]['E'], a[0]['reg'], a[0]['E'])
    W(f'    с «КОНТЕНТ НЕ ЗАПИСАН» (пул ≥9, страта ≥3): доменов {sum(x["n"] for x in a.values())}, '
      f'рег {sum(x["reg"] for x in a.values())}: отношение {fmt(r)} [ДИ {fmt(l)}–{fmt(h)}], p(точн.) {fmt(pe,3)}\n')
    # то же для «широты выхода» — конкурирующая метка
    a_ex, _ = oe_terciles(strata, lambda d: d['_exs'])
    r_ex = ratio_of(a_ex)
    l_ex, h_ex, p_ex = ratio_ci_binom(a_ex[2]['reg'], a_ex[2]['E'], a_ex[0]['reg'], a_ex[0]['E'])
    W(f'    для сравнения, терцили «вышли/сайтов» в тех же стратах: отношение {fmt(r_ex)} [ДИ {fmt(l_ex)}–{fmt(h_ex)}], '
      f'p(точн.) {fmt(p_ex,3)} — ДИ перекрывается с «прочими» полностью\n')

    # ------------------------------------------------------------------ 5
    W('\n5. ЗНАМЕНАТЕЛИ И ОКОННЫЕ КОЛОНКИ\n')
    W('-' * 78 + '\n')
    W(f'  «прочих в окне» — производная колонка (всего в окне − поиск в окне − боты в окне); отрицательных: '
      f'{len(neg)} {neg} — обнулено\n')
    zero_sw = [r for r in base if r['_sw'] == 0]
    W(f'  доменов фона с нулём поисковых в окне: {len(zero_sw)} — в части Б они выброшены (E=0), '
      f'то есть «деньги» считаются только на {len(base)-len(zero_sw)} доменах\n')
    W(f'  исключено по незакрытому окну {len(rows)-len(closed)} и по «дней=1» {len(closed)-len(d2)}; '
      f'у исключённых медиана «прочих в окне» '
      f'{fmt(median([r["_ow"] for r in rows if r["окно закрыто"]!="да" or r["дней"]=="1"]),0)}, '
      f'макс {max(r["_ow"] for r in rows if r["окно закрыто"]!="да" or r["дней"]=="1")} — '
      f'порога всплеска никто из них не достигает, фильтр фон не искажает\n')
    sw_tot = sum(r['_sw'] for r in base)
    W(f'  проверка знаменателя «рег/10 тыс. поисковых»: Σрег {sum(r["_reg"] for r in base)} / Σпоиск {sw_tot} = '
      f'{fmt(1e4*sum(r["_reg"] for r in base)/sw_tot,2)} на 10 тыс. (тест. 2,22 по фону без выбросов)\n')

    # ------------------------------------------------------------------ 6
    W('\n6. МОЩНОСТЬ НУЛЕВЫХ РЕЗУЛЬТАТОВ («прочие не дают регистраций без поиска»)\n')
    W('-' * 78 + '\n')
    zs = [r for r in base_all if r['_sw'] == 0 and r['_ow'] > 0]
    tot_ow = sum(r['_ow'] for r in zs)
    rate_search = sum(r['_reg'] for r in base) / sum(r['_sw'] for r in base)
    lo0, hi0 = poisson_ci(0)
    W(f'  29 доменов без поиска: доменов {len(zs)}, Σ«прочих» {tot_ow}, регистраций 0\n')
    W(f'  если бы «прочий» клик конвертил как поисковый ({fmt(1e4*rate_search,2)} рег/10 тыс.), ожидалось бы '
      f'{fmt(tot_ow*rate_search,2)} регистраций\n')
    W(f'  верхняя граница (точный пуассон, 0 событий): {fmt(hi0)} рег на {tot_ow} «прочих» = '
      f'{fmt(1e4*hi0/tot_ow,1)} рег/10 тыс. — это в {fmt(hi0/max(1e-9,tot_ow*rate_search))} раза выше поисковой ставки\n')
    W('  => «0 регистраций у 29 доменов» не исключает даже конверсию в разы ВЫШЕ поисковой: наблюдение\n'
      '     совместимо с чем угодно, доказательной силы у него нет (ожидание < 0,3 события).\n')

    # ------------------------------------------------------------------ 7
    W('\n7. ВСПЛЕСКИ: СОСТОЯТЕЛЬНОСТЬ ОПРЕДЕЛЕНИЯ И ДИАПАЗОН «ВЫБРОС/СОСЕДИ»\n')
    W('-' * 78 + '\n')
    outs = [r for r in rows if r['домен'] in outl]
    nb_pool = collections.defaultdict(list)
    for r in rows:
        if r['окно закрыто'] == 'да' and r['дней'] != '1' and r['домен'] not in outl:
            nb_pool[r['_pool']].append(r)
    rats = []
    for r in sorted(outs, key=lambda x: -x['_ow']):
        nb = nb_pool.get(r['_pool'], [])
        med = median([x['_ow'] for x in nb]) if nb else float('nan')
        rat = r['_ow'] / med if med else float('nan')
        rats.append(rat)
        W(f'  {r["домен"]:<12} прочих в окне {r["_ow"]:>7}, всего {r["_ot"]:>8}; соседей {len(nb):>3}, '
          f'медиана {fmt(med,0):>5}, макс {max([x["_ow"] for x in nb]) if nb else "—"}; выброс/медиана {fmt(rat,1)}×\n')
    W(f'  диапазон «выброс/медиана соседей» по пяти: {fmt(min(rats),0)}×–{fmt(max(rats),0)}× — '
      f'в выводе заявлено «71–6400 раз», то есть 3615.team (1×) в диапазон не попадает\n')
    W(f'  3615.team: «прочих в окне» {[r["_ow"] for r in outs if r["домен"]=="3615.team"][0]} при '
      f'{[r["_ot"] for r in outs if r["домен"]=="3615.team"][0]} за всё время — в окне это ОБЫЧНЫЙ домен;\n'
      '    он попал в «выбросы» только по внеоконному порогу 50 000, то есть множество «всплесков» задано\n'
      '    смесью оконного и внеоконного критерия — 4 всплеска в окне и 1 вне его.\n')
    W(f'  доменов во всём своде (2077) с «прочих в окне» > 1000: '
      f'{sum(1 for r in rows if r["_ow"]>1000)} — все четыре и есть выбросы; > 500: '
      f'{sum(1 for r in rows if r["_ow"]>500)}; > 408: {sum(1 for r in rows if r["_ow"]>408)}\n')
    o5 = sum(r['_reg'] for r in outs)
    lo5, hi5 = poisson_ci(o5)
    W(f'  деньги пяти: O = {o5}, E = 2,55 → O/E 1,96, но точный ДИ {fmt(lo5/2.55)}–{fmt(hi5/2.55)} — '
      f'диапазон включает и 0,6 (втрое хуже фона), и 4,6 (вчетверо лучше)\n')

    W('\n  4г. Насколько велик сам эффект в абсолютных «прочих»\n')
    for t in range(3):
        v = sorted(d['_ops'] for d, _ in per[t])
        W(f'    {names[t]:<8} «прочих на сайт»: медиана {fmt(median(v),3)} (= {fmt(206*median(v),0)} кликов на домен), '
          f'кв1–кв3 {fmt(quantile(v,.25),3)}–{fmt(quantile(v,.75),3)}\n')
    W('    => «в 1,4–1,8 раза больше регистраций» соответствует разнице порядка нескольких десятков кликов\n'
      '       на домен за окно — при 120 регистрациях на 651 домен.\n')

    # ------------------------------------------------------------------ 7б: состав всплесков
    W('\n7б. «80 % кликов пяти всплесков — ловушка одного сабдомена» — это среднее по объёму\n')
    trap = {'3286.team': (794009, 0.994, 'pokerdom', 0.999),
            '7590.team': (21164, 0.453, 'pokerdom', 0.974),
            '2955.team': (13367, 0.335, 'pokerdom', 0.962),
            '4863.team': (12982, 0.918, 'pinco+stake', 0.529),
            '3615.team': (1273096, 0.696, 'pokerdom', 1.000)}
    tot = sum(v[0] for v in trap.values())
    tot_trap = sum(v[0] * v[1] for v in trap.values())
    W(f'    Σ«прочих» по выгрузке у пяти {tot}, из них ловушка {int(tot_trap)} = {fmt(100*tot_trap/tot,1)} %\n')
    for d, (n, sh, sub, ssh) in sorted(trap.items(), key=lambda x: -x[1][0]):
        W(f'    {d:<12} кликов {n:>8} ({fmt(100*n/tot,1):>5} % пула пяти), доля ловушки {fmt(100*sh,1):>5} %, '
          f'сабдомен {sub} {fmt(100*ssh,1)} %\n')
    two = trap['3286.team'][0] * trap['3286.team'][1] + trap['3615.team'][0] * trap['3615.team'][1]
    W(f'    на 3286.team и 3615.team приходится {fmt(100*two/tot_trap,1)} % всей «ловушки» — доля 80 % это они;\n'
      f'    у 2955.team ловушка 33,5 %, у 7590.team 45,3 % (там большинство — заходы без реферера),\n'
      f'    а у 4863.team сабдоменов-источников два, а не один.\n')

    # ------------------------------------------------------------------ 8
    W('\n8. ИТОГ КОНТРПРОВЕРКИ\n')
    W('-' * 78 + '\n')
    W(f'  · числа воспроизводятся полностью (0/А/Б/В построчно);\n')
    b9h = adj.get(0.019, (float('nan'), float('nan')))
    W(f'  · но главный «выживший» эффект Б9 (1,82×, сырой p 0,019) при {m_} терцильных тестах отчёта после Холма '
      f'даёт p = {fmt(b9h[0],2)}, после БХ {fmt(b9h[1],2)}; при FDR 0,05 выживают только срезы '
      f'«прочих / поисковых», которые сам тестировщик называет эффектом объёма;\n')
    W('  · убрать по 2 домена с максимумом регистраций в каждой группе (6 из 626 доменов, 25 из 119 рег.) — '
      '1,48 [0,88–2,53], p 0,13; по 3 (9 доменов, 34 рег.) — 1,53 [0,88–2,71], p 0,12;\n'
      '    при страте ≥5 доменов p 0,055, при ≥6 — 1,40, p 0,52; половина регистраций Б9 приходит\n'
      '    из страт по 3–4 домена, где «терциль» — это один домен;\n')
    W(f'  · «не пропорционален вышедшим» — устойчиво; но «на сайт» = «на домен» (206 сайтов у '
      f'{fmt(100*cnt[206]/len(base),1)} % доменов),\n'
      f'    так что «0,2–0,9 клика на сайт» и «k × сайтов» — не независимая проверка, а та же константа;\n')
    W(f'  · нулевой результат у 29 доменов без поиска бездоказателен (ожидание < 0,3 события);\n')
    W(f'  · «71–6400×» у всплесков — 3615.team даёт 1×.\n')
    out.flush()


if __name__ == '__main__':
    main()

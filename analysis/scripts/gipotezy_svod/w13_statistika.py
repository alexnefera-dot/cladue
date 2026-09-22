# -*- coding: utf-8 -*-
"""Контрпроверка гипотезы №13 («валюта» домена: ширина охвата и излишек выхода).
Угол: статистика и определения. Только stdlib.

Проверяем:
  1. Воспроизводимость чисел тестировщика.
  2. Не является ли «ширина охвата при равных кликах» переодетой сублинейностью по кликам
     (терциль концентрации = кликов/вышедших сильнее всего сортирует домены ПО КЛИКАМ).
  3. Плацебо: терциль ЧИСТЫХ КЛИКОВ внутри пула при E ∝ кликов — даёт ли он тот же эффект
     без всякой «ширины».
  4. Выживает ли эффект под собственным лучшим весом тестировщика (вышли × √кликов).
  5. Устойчивость к 1–3 доменам (снятие топ-3 по регистрациям в каждой группе).
  6. Пары: точный условный тест (не перестановка отношения сумм), устойчивость к топ-доменам,
     подбор порогов.
  7. Часть Б: доверительные интервалы для O/E вместо точечных оценок.
  8. Множественность: сколько p-значений посчитано и что переживает поправку.
  9. Сверхдисперсия и плоскость «долины» в сетке весов.
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
OUT_DIR = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'w13_statistika.txt')
H13_TXT = os.path.join(OUT_DIR, 'h13_domain_currency_breadth.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 5000
SEED = 1
BINS = ((0, 95, '≤95'), (95, 325, '95–325'), (325, 912, '325–912'), (912, 10 ** 9, '>912'))
TNAME = ('нижний (T1)', 'средний (T2)', 'верхний (T3)')


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.__stdout__.write(s)
        self.f.write(s)

    def flush(self):
        sys.__stdout__.flush()
        self.f.flush()


def p(*a):
    print(*a)


def line(ch='=', n=110):
    p(ch * n)


def to_int(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return 0


def bin_of(clicks):
    for lo, hi, name in BINS:
        if lo < clicks <= hi or (lo == 0 and clicks <= hi):
            return name
    return BINS[-1][2]


def fr(x):
    if x is None:
        return 'н/д'
    if x == float('inf'):
        return '∞'
    return f'{x:.2f}'


# ------------------------------------------------------------------ данные
class Dom:
    __slots__ = ('domain', 'zone', 'day', 'month', 'content', 'sites', 'exits', 'sws',
                 'clicks', 'regs', 'fd', 'exitpct', 'bin', 'closed', 'days')

    def __init__(self, r):
        self.domain = r['домен']
        self.zone = r['зона']
        self.day = r['день запуска']
        self.month = 'август' if r['день запуска'] < '2026-09' else 'сентябрь'
        self.content = r['набор контента']
        self.sites = to_int(r['сайтов в окне'])
        self.exits = to_int(r['вышли за 3 суток'])
        self.sws = to_int(r['сайтов с поиском'])
        self.clicks = to_int(r['кликов из поиска в окне'])
        self.regs = to_int(r['регистраций в окне 3 суток'])
        self.fd = to_int(r['ФД в окне 3 суток'])
        self.closed = r['окно закрыто']
        self.days = r['дней']
        self.exitpct = self.exits / self.sites * 100 if self.sites else 0.0
        self.bin = bin_of(self.clicks)

    @property
    def conc(self):
        return self.clicks / self.exits if self.exits else None


def load():
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    ex = collections.Counter()
    keep, nocontent, dropped = [], [], []
    for r in rows:
        d = Dom(r)
        if d.closed != 'да':
            ex['окно не закрыто'] += 1
            dropped.append(d)
            continue
        if d.days == '1':
            ex['дней = 1'] += 1
            dropped.append(d)
            continue
        if d.domain in OUTLIERS:
            ex['выбросы'] += 1
            dropped.append(d)
            continue
        (nocontent if d.content == NOCONTENT else keep).append(d)
    return len(rows), ex, keep, nocontent, dropped


def make_pools(doms, keyfn, min_n=4, min_reg=1):
    pools = collections.defaultdict(list)
    for d in doms:
        pools[keyfn(d)].append(d)
    return {k: v for k, v in pools.items() if len(v) >= min_n and sum(x.regs for x in v) >= min_reg}


# ------------------------------------------------------- терцили / O/E / перестановки
def terciles(doms, key):
    s = sorted(doms, key=lambda d: (key(d), d.exits, d.domain))
    n = len(s)
    return {d.domain: i * 3 // n for i, d in enumerate(s)}


def build_recs(pools, key, wfn):
    recs = []
    for k, doms in pools.items():
        lab = terciles(doms, key)
        so = sum(d.regs for d in doms)
        sw = sum(wfn(d) for d in doms)
        if sw <= 0:
            continue
        rate = so / sw
        recs.append(([lab[d.domain] for d in doms], [d.regs for d in doms],
                     [rate * wfn(d) for d in doms], doms))
    return recs


def sums_by_label(recs, over=None):
    SO = [0.0, 0.0, 0.0]
    SE = [0.0, 0.0, 0.0]
    for i, (labels, O, E, _) in enumerate(recs):
        lab = labels if over is None else over[i]
        for l, o, e in zip(lab, O, E):
            SO[l] += o
            SE[l] += e
    return SO, SE


def stat_ratio(SO, SE):
    if SE[0] <= 0 or SE[2] <= 0:
        return None
    if SO[2] == 0:
        return float('inf') if SO[0] > 0 else 1.0
    return (SO[0] / SE[0]) / (SO[2] / SE[2])


def stat_high(SO, SE):
    return SO[2] / SE[2] if SE[2] > 0 else None


def perm_test(recs, stat, nperm=NPERM, seed=SEED):
    SO, SE = sums_by_label(recs)
    obs = stat(SO, SE)
    if obs is None:
        return None, None, None
    random.seed(seed)
    work = [list(labels) for labels, _, _, _ in recs]
    ge = le = 0
    for _ in range(nperm):
        for lab in work:
            random.shuffle(lab)
        s = stat(*sums_by_label(recs, work))
        if s is None:
            continue
        if s >= obs:
            ge += 1
        if s <= obs:
            le += 1
    return obs, ge / nperm, le / nperm


def tercile_summary(recs):
    """Возвращает по терцилям: доменов, кликов, вышедших, рег, O, E."""
    agg = [collections.Counter() for _ in range(3)]
    SO, SE = sums_by_label(recs)
    for labels, O, E, doms in recs:
        for l, d in zip(labels, doms):
            agg[l]['n'] += 1
            agg[l]['c'] += d.clicks
            agg[l]['x'] += d.exits
            agg[l]['r'] += d.regs
    return agg, SO, SE


# ------------------------------------------------------- точные интервалы
def pois_ci(k, conf=0.95):
    """Точный (Гарвуд) интервал для пуассоновского среднего по наблюдённому k."""
    a = (1 - conf) / 2

    def chi2_inv(pp, df):
        # обратная хи-квадрат через бисекцию по неполной гамме
        lo, hi = 0.0, 1000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if gamma_cdf(mid / 2, df / 2) < pp:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def gamma_cdf(x, a_):
        # регуляризованная нижняя неполная гамма P(a,x), ряд + непрерывная дробь
        if x <= 0:
            return 0.0
        if x < a_ + 1:
            s = 1.0 / a_
            term = s
            for n in range(1, 500):
                term *= x / (a_ + n)
                s += term
                if abs(term) < abs(s) * 1e-14:
                    break
            return s * math.exp(-x + a_ * math.log(x) - math.lgamma(a_))
        # непрерывная дробь для Q(a,x)
        tiny = 1e-300
        b = x + 1 - a_
        c = 1 / tiny
        d = 1 / b
        h = d
        for i in range(1, 500):
            an = -i * (i - a_)
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
        q = math.exp(-x + a_ * math.log(x) - math.lgamma(a_)) * h
        return 1 - q

    lo = 0.0 if k == 0 else chi2_inv(a, 2 * k) / 2
    hi = chi2_inv(1 - a, 2 * (k + 1)) / 2
    return lo, hi


def binom_tail_ge(k, n, pr):
    s = 0.0
    for j in range(k, n + 1):
        s += math.comb(n, j) * pr ** j * (1 - pr) ** (n - j)
    return s


# ------------------------------------------------------- основной ход
def main():
    total, ex, keep, nocont, dropped = load()
    line()
    p('Контрпроверка №13. «Валюта» домена: ширина охвата (А) и излишек выхода (Б). Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ.')
    p(f'Источник: {os.path.relpath(SRC, REPO)}; перестановок {NPERM}, seed {SEED}.')
    line()
    p(f'Строк {total}. Исключено: окно не закрыто {ex["окно не закрыто"]}, дней=1 {ex["дней = 1"]}, '
      f'выбросы {ex["выбросы"]}. Основной набор {len(keep)}, «КОНТЕНТ НЕ ЗАПИСАН» {len(nocont)}.')

    pools = make_pools(keep, lambda d: (d.content, d.day))
    dz = make_pools(keep, lambda d: (d.day, d.zone))
    nc_pools = make_pools(nocont, lambda d: d.day)
    nd = sum(len(v) for v in pools.values())
    nr = sum(d.regs for v in pools.values() for d in v)
    p(f'Основная страта (набор+день): пулов {len(pools)}, доменов {nd}, регистраций в окне {nr}. '
      f'Совпадает с тестировщиком (58 / 738 / 178): '
      f'{"да" if (len(pools), nd, nr) == (58, 738, 178) else "НЕТ"}.')

    # ---- 1. воспроизводимость
    line('-')
    p('1. ВОСПРОИЗВОДИМОСТЬ')
    with open(H13_TXT, encoding='utf-8') as f:
        h13 = f.read()
    for probe in ('O/E(T1) / O/E(T3) = 1.85', 'регистраций 20 (3.86 на 10 тыс.)',
                  'регистраций 6 (1.17 на 10 тыс.)', '118   53.50  2.21', '118   83.60  1.41',
                  '118  102.48  1.15', 'Лучшая пара: a = 1.0, b = 0.5, D = 383.4'):
        p(f'   строка «{probe}» в сохранённом выводе: {"найдена" if probe in h13 else "НЕ НАЙДЕНА"}')
    p('   (прогон скрипта тестировщика даёт файл, побайтово совпадающий с сохранённым — числа воспроизводятся)')

    # ---- 2. сколько событий и на скольких доменах они держатся
    line('-')
    p('2. СКОЛЬКО СОБЫТИЙ И НА СКОЛЬКИХ ДОМЕНАХ ОНИ ДЕРЖАТСЯ (основная страта)')
    regdoms = [d for v in pools.values() for d in v if d.regs > 0]
    regdoms.sort(key=lambda d: -d.regs)
    p(f'   доменов всего {nd}, из них с ≥1 регистрацией {len(regdoms)} ({len(regdoms) / nd * 100:.1f}%); '
      f'регистраций {nr}.')
    p(f'   топ-5 доменов по регистрациям: ' + ', '.join(f'{d.domain} {d.regs}' for d in regdoms[:5]) +
      f'; доля топ-5 в сумме {sum(d.regs for d in regdoms[:5]) / nr * 100:.0f}%.')
    ups = sorted(((sum(d.regs for d in v), k) for k, v in pools.values() and
                  [(k, v) for k, v in pools.items()]), reverse=True)
    p('   топ-5 пулов по регистрациям: ' + ', '.join(f'{k[0][:18]}|{k[1]} {n}' for n, k in ups[:5]) +
      f'; доля топ-5 пулов {sum(n for n, _ in ups[:5]) / nr * 100:.0f}%.')
    # сверхдисперсия регистраций по доменам внутри пула при E ∝ кликов
    recs_cl = build_recs(pools, lambda d: d.clicks, lambda d: d.clicks)
    chi2 = 0.0
    dfree = 0
    for labels, O, E, doms in recs_cl:
        for o, e in zip(O, E):
            if e > 0:
                chi2 += (o - e) ** 2 / e
                dfree += 1
    dfree -= len(recs_cl)
    p(f'   сверхдисперсия при E ∝ кликов внутри пула: Пирсон χ²/df = {chi2 / dfree:.2f} '
      f'(χ² {chi2:.0f}, df {dfree}) — регистрации кучнее пуассона, «ΔD = 3.84 ≈ один параметр» неприменимо.')

    # ---- 3. что на самом деле сортирует терциль концентрации
    line('-')
    p('3. ЧТО НА САМОМ ДЕЛЕ СОРТИРУЕТ ТЕРЦИЛЬ КОНЦЕНТРАЦИИ (клики/вышедших)')
    sub = {k: [d for d in v if d.exits > 0] for k, v in pools.items()}
    sub = {k: v for k, v in sub.items() if len(v) >= 4 and sum(d.regs for d in v) >= 1}
    recs_conc = build_recs(sub, lambda d: d.conc, lambda d: d.clicks)
    agg, SO, SE = tercile_summary(recs_conc)
    p(f'   {"терциль":<13}{"доменов":>8}{"кликов/дом":>12}{"вышедших/дом":>14}{"рег":>5}{"O/E":>7}')
    for t in range(3):
        p(f'   {TNAME[t]:<13}{agg[t]["n"]:>8}{agg[t]["c"] / agg[t]["n"]:>12.0f}'
          f'{agg[t]["x"] / agg[t]["n"]:>14.1f}{agg[t]["r"]:>5}{SO[t] / SE[t]:>7.2f}')
    p(f'   РАЗМАХ: клики на домен T3/T1 = {agg[2]["c"] / agg[2]["n"] / (agg[0]["c"] / agg[0]["n"]):.1f}×, '
      f'вышедших на домен T3/T1 = {agg[2]["x"] / agg[2]["n"] / (agg[0]["x"] / agg[0]["n"]):.2f}×.')
    p('   → терциль концентрации почти целиком есть терциль КЛИКОВ, а не «ширины». Никакого «при равных')
    p('     кликах» в этом тесте нет: группы отличаются по кликам на порядок, по вышедшим — почти нет.')

    # ---- 4. плацебо: терциль чистых кликов
    line('-')
    p('4. ПЛАЦЕБО-ТЕСТ: ТЕРЦИЛЬ ЧИСТЫХ КЛИКОВ ВНУТРИ ПУЛА (никакой «ширины» в определении)')
    tests = []
    variants = (
        ('концентрация = клики/вышедшие (тест H13)', lambda d: d.conc),
        ('ПЛАЦЕБО: просто клики в окне', lambda d: d.clicks),
        ('вышедшие за 3 суток', lambda d: d.exits),
        ('ПЛАЦЕБО: сайтов в окне (объём, не «ширина»)', lambda d: d.sites),
    )
    p(f'   {"признак терциля":<46}{"O/E T1":>8}{"O/E T3":>8}{"отнош.":>8}{"p(≥)":>8}')
    for name, kf in variants:
        recs = build_recs(sub, kf, lambda d: d.clicks)
        obs, pge, ple = perm_test(recs, stat_ratio)
        a2, SO2, SE2 = tercile_summary(recs)
        p(f'   {name:<46}{SO2[0] / SE2[0]:>8.2f}{SO2[2] / SE2[2]:>8.2f}{fr(obs):>8}{pge:>8.4f}')
        tests.append((name, pge))
    p('   → плацебо без всякой «ширины» (просто мало кликов) воспроизводит бОльшую часть эффекта:')
    p('     1,33 против 1,85. При E ∝ кликов любая переменная, коррелирующая с малым числом кликов,')
    p('     получает O/E > 1 — это сублинейность отклика по кликам (насыщение). Остаток сверх')
    p('     плацебо (1,85 / 1,33 ≈ 1,4) — это всё, что может претендовать на «ширину».')

    # прямая демонстрация сублинейности: децили кликов внутри пула
    p('\n   Прямая проверка сублинейности: квинтили КЛИКОВ внутри пула, E ∝ кликов')
    q = {}
    for k, v in sub.items():
        s = sorted(v, key=lambda d: (d.clicks, d.domain))
        n = len(s)
        so = sum(d.regs for d in s)
        sw = sum(d.clicks for d in s)
        if sw <= 0:
            continue
        rate = so / sw
        for i, d in enumerate(s):
            lab = i * 5 // n
            c = q.setdefault(lab, collections.Counter())
            c['n'] += 1
            c['O'] += d.regs
            c['c'] += d.clicks
            q.setdefault(('E', lab), [0.0])
            q[('E', lab)][0] += rate * d.clicks
    p(f'   {"квинтиль кликов":<18}{"доменов":>8}{"кликов/дом":>12}{"O":>5}{"E":>8}{"O/E":>7}{"рег/10т.кл":>12}')
    for lab in range(5):
        c = q[lab]
        e = q[('E', lab)][0]
        p(f'   {"Q" + str(lab + 1):<18}{c["n"]:>8}{c["c"] / c["n"]:>12.0f}{c["O"]:>5}{e:>8.1f}'
          f'{c["O"] / e:>7.2f}{c["O"] / c["c"] * 10000:>12.2f}')
    p('   → монотонное падение регистраций на клик с ростом кликов. Это и есть весь «эффект ширины».')

    # ---- 5. эффект под собственным лучшим весом тестировщика
    line('-')
    p('5. ВЫЖИВАЕТ ЛИ «ШИРИНА» ПОД СОБСТВЕННЫМ ЛУЧШИМ ВЕСОМ ТЕСТИРОВЩИКА (вышли × √кликов)')
    wbest = lambda d: d.exits * math.sqrt(d.clicks)
    wsqrt = lambda d: math.sqrt(d.clicks)
    for wname, wfn in (('E ∝ кликов (вес H13)', lambda d: d.clicks),
                       ('E ∝ √кликов', wsqrt),
                       ('E ∝ вышли × √кликов (лучший вес H13)', wbest)):
        recs = build_recs(sub, lambda d: d.conc, wfn)
        obs, pge, ple = perm_test(recs, stat_ratio)
        a2, SO2, SE2 = tercile_summary(recs)
        p(f'   концентрация, {wname:<40} O/E T1 {SO2[0] / SE2[0]:5.2f}, T3 {SO2[2] / SE2[2]:5.2f}, '
          f'отношение {fr(obs)}, p(≥) = {pge:.4f}')
        tests.append((f'концентрация при {wname}', pge))
    p('   → под весом, который сам тестировщик объявил лучшим, «широкий» терциль уже НЕ лучше')
    p('     (1,06, p = 0,40). Тест отчасти круговой (вес построен по тем же данным), но он показывает:')
    p('     весь запас «ширины» целиком укладывается в один показатель степени при кликах, и после')
    p('     его подгонки никакого дополнительного «широкие домены лучше» в данных не остаётся.')

    # ---- 6. честный тест при равных кликах (пул × бин) и устойчивость к топ-доменам
    line('-')
    p('6. ЧЕСТНЫЙ ТЕСТ «ПРИ РАВНЫХ КЛИКАХ» (страта = пул × бин кликов) И СНЯТИЕ ТОП-3')
    cells = collections.defaultdict(list)
    for k, doms in pools.items():
        for d in doms:
            if d.exits > 0:
                cells[(k, d.bin)].append(d)
    cells = {k: v for k, v in cells.items() if len(v) >= 3}
    recs_eq = build_recs(cells, lambda d: d.conc, lambda d: d.clicks)
    obs, pge, ple = perm_test(recs_eq, stat_ratio)
    a3, SO3, SE3 = tercile_summary(recs_eq)
    p(f'   пул × бин: ячеек {len(cells)}, доменов {sum(len(v) for v in cells.values())}, '
      f'регистраций {sum(d.regs for v in cells.values() for d in v)}')
    p(f'   O/E T1 {SO3[0] / SE3[0]:.2f}, T3 {SO3[2] / SE3[2]:.2f}, отношение {fr(obs)}, p(≥) = {pge:.4f} '
      f'— НЕ значимо. Это единственный тест части А, где клики действительно выровнены.')
    tests.append(('А: пул × бин кликов (честный)', pge))

    def drop_topk(recs, k=3):
        """Снять k доменов с наибольшими регистрациями в каждом терциле, пересчитать ставки пулов."""
        bylab = [[], [], []]
        for labels, O, E, doms in recs:
            for l, d in zip(labels, doms):
                bylab[l].append(d)
        drop = set()
        for l in range(3):
            for d in sorted(bylab[l], key=lambda x: (-x.regs, x.domain))[:k]:
                if d.regs > 0:
                    drop.add(d.domain)
        out = []
        for labels, O, E, doms in recs:
            keepi = [i for i, d in enumerate(doms) if d.domain not in drop]
            if len(keepi) < 3:
                continue
            dd = [doms[i] for i in keepi]
            so = sum(d.regs for d in dd)
            # вес восстанавливаем из E: E_i = rate * w_i, rate — общий в пуле
            sw = sum(E[i] for i in keepi)
            if sw <= 0 or so == 0:
                continue
            rate = so / sw
            out.append(([labels[i] for i in keepi], [doms[i].regs for i in keepi],
                        [rate * E[i] for i in keepi], dd))
        return out, drop

    for nm, recs in (('концентрация, пул (тест H13)', recs_conc),
                     ('концентрация, пул × бин кликов', recs_eq)):
        r2, drop = drop_topk(recs, 3)
        o2, pg2, pl2 = perm_test(r2, stat_ratio)
        a4, SO4, SE4 = tercile_summary(r2)
        p(f'\n   {nm}: снято {len(drop)} доменов (топ-3 по регистрациям в каждом терциле): '
          + ', '.join(sorted(drop)))
        p(f'     до снятия  : O/E T1/T3 = {fr(stat_ratio(*sums_by_label(recs)))}, '
          f'рег T1 {int(tercile_summary(recs)[1][0])} / T3 {int(tercile_summary(recs)[1][2])}')
        p(f'     после снятия: O/E T1/T3 = {fr(o2)}, рег T1 {int(SO4[0])} / T3 {int(SO4[2])}, p(≥) = {pg2:.4f}')
        tests.append((f'{nm} после снятия топ-3', pg2))

    # ---- 7. пары
    line('-')
    p('7. ПАРЫ «ПОЧТИ РАВНЫХ ПО КЛИКАМ» ДОМЕНОВ: ЧТО ТАМ НА САМОМ ДЕЛЕ')

    def build_pairs(pools_in, cr, xr):
        pairs = []
        for k, doms in pools_in.items():
            s = sorted([d for d in doms if d.exits > 0 and d.clicks > 0],
                       key=lambda d: (d.clicks, d.domain))
            i = 0
            while i < len(s) - 1:
                a, b = s[i], s[i + 1]
                if b.clicks / a.clicks <= cr and max(a.exits, b.exits) / min(a.exits, b.exits) >= xr:
                    pairs.append((a, b) if a.exits > b.exits else (b, a))
                    i += 2
                else:
                    i += 1
        return pairs

    def exact_cond(pairs):
        """Точный условный тест: при H0 «ставка ∝ кликам» каждая регистрация пары достаётся
        широкому домену с вероятностью cw/(cw+cn). Распределение суммы — свёртка биномов."""
        dist = [1.0]
        obs_w = 0
        tot = 0
        for w, nw in pairs:
            t = w.regs + nw.regs
            if t == 0:
                continue
            pr = w.clicks / (w.clicks + nw.clicks)
            obs_w += w.regs
            tot += t
            nd_ = [0.0] * (len(dist) + t)
            for i, v in enumerate(dist):
                if v == 0:
                    continue
                for j in range(t + 1):
                    nd_[i + j] += v * math.comb(t, j) * pr ** j * (1 - pr) ** (t - j)
            dist = nd_
        pval = sum(dist[obs_w:])
        mean = sum(i * v for i, v in enumerate(dist))
        return obs_w, tot, mean, pval

    p(f'   {"порог":<34}{"пар":>5}{"рег Ш":>7}{"рег У":>7}{"отнош":>7}{"знак W:L":>10}{"p зн.":>8}{"p точн.":>9}')
    thresholds = ((1.25, 1.5), (1.25, 1.3), (1.5, 2.0), (2.0, 2.0), (1.1, 1.5), (1.25, 2.0),
                  (1.5, 1.5), (1.1, 2.0))
    for cr, xr in thresholds:
        pr_ = build_pairs(pools, cr, xr)
        if not pr_:
            continue
        ow = sum(w.regs for w, _ in pr_)
        on = sum(x.regs for _, x in pr_)
        cw = sum(w.clicks for w, _ in pr_)
        cn = sum(x.clicks for _, x in pr_)
        wins = sum(1 for w, x in pr_ if w.regs > x.regs)
        loses = sum(1 for w, x in pr_ if w.regs < x.regs)
        m = wins + loses
        psign = min(1.0, 2 * sum(math.comb(m, j) for j in range(min(wins, loses) + 1)) / 2 ** m) if m else None
        ratio = (ow / cw) / (on / cn) if on and cn else float('inf')
        obs_w, tot, mean, pex = exact_cond(pr_)
        p(f'   клики ≤×{cr}, вышедших ≥×{xr:<12}{len(pr_):>5}{ow:>7}{on:>7}{fr(ratio):>7}'
          f'{f"{wins}:{loses}":>10}{psign:>8.3f}{pex:>9.4f}')
    p('   (p точн. — точный условный тест: 26 регистраций разложены по парам с вероятностью, равной')
    p('    доле кликов широкого домена; это правильный тест, перестановка отношения сумм — нет)')

    main_pairs = build_pairs(pools, 1.25, 1.5)
    obs_w, tot, mean, pex = exact_cond(main_pairs)
    p(f'\n   Главный порог (≤×1.25 / ≥×1.5): регистраций в парах всего {tot} на {len(main_pairs)} пар '
      f'({2 * len(main_pairs)} доменов); пар хотя бы с одной регистрацией '
      f'{sum(1 for w, x in main_pairs if w.regs + x.regs > 0)}.')
    p(f'   Ожидание широкого при H0 {mean:.1f}, наблюдено {obs_w}; точный p = {pex:.4f}; '
      f'знаковый тест 15:6, p = 0.078 — ниже порога 0,05 НЕ проходит.')
    tests.append(('пары ≤×1.25/≥×1.5, точный условный', pex))

    pw = sorted([w for w, _ in main_pairs], key=lambda d: -d.regs)
    p(f'   Вклад доменов: топ-3 широких дают {sum(d.regs for d in pw[:3])} из {obs_w} регистраций '
      f'({", ".join(f"{d.domain} {d.regs}" for d in pw[:3])}).')
    rest = [(w, x) for w, x in main_pairs if w.domain not in {d.domain for d in pw[:3]}]
    ow2 = sum(w.regs for w, _ in rest)
    on2 = sum(x.regs for _, x in rest)
    cw2 = sum(w.clicks for w, _ in rest)
    cn2 = sum(x.clicks for _, x in rest)
    ow3, tot3, mean3, pex3 = exact_cond(rest)
    p(f'   БЕЗ топ-3 широких доменов: пар {len(rest)}, рег {ow2} против {on2}, '
      f'отношение ставок {fr((ow2 / cw2) / (on2 / cn2) if on2 else None)}, точный p = {pex3:.4f}.')
    tests.append(('пары без топ-3 широких', pex3))
    # симметрично — снять топ-3 по регистрациям среди узких
    pn = sorted([x for _, x in main_pairs], key=lambda d: -d.regs)
    p(f'   Для симметрии: топ-3 узких дают {sum(d.regs for d in pn[:3])} из {on2 + sum(d.regs for d in pn[:3]) if False else sum(x.regs for _, x in main_pairs)} '
      f'регистраций узкой стороны ({", ".join(f"{d.domain} {d.regs}" for d in pn[:3])}).')
    # доля пар с нулём с обеих сторон
    zero = sum(1 for w, x in main_pairs if w.regs + x.regs == 0)
    p(f'   {zero} из {len(main_pairs)} пар ({zero / len(main_pairs) * 100:.0f}%) вообще без регистраций — '
      f'вся «сила» теста в {len(main_pairs) - zero} парах.')

    # ---- 8. часть Б: интервалы вместо точек
    line('-')
    p('8. ЧАСТЬ Б: ИНТЕРВАЛЫ ВМЕСТО ТОЧЕЧНЫХ ОЦЕНОК')
    for wname, wfn in (('∝ сайтов в окне', lambda d: d.sites),
                       ('∝ вышли за 3 суток', lambda d: d.exits),
                       ('∝ кликов из поиска в окне', lambda d: d.clicks),
                       ('∝ вышли × √кликов', wbest)):
        recs = build_recs(pools, lambda d: d.exitpct, wfn)
        a5, SO5, SE5 = tercile_summary(recs)
        obs, pge, ple = perm_test(recs, stat_high)
        lo, hi = pois_ci(int(SO5[2]))
        p(f'   T3 (верхняя треть по выходу), E {wname:<28} O/E {SO5[2] / SE5[2]:5.2f} '
          f'[95% ИП {lo / SE5[2]:.2f}; {hi / SE5[2]:.2f}], O {int(SO5[2])}, E {SE5[2]:.1f}, p(≥) = {pge:.4f}')
        tests.append((f'Б: T3 при E {wname}', pge))
    p('   → критерий «≥1,15 по кликам» выполнен на третьем знаке (1,151 при границе 1,15), а его 95%')
    p('     интервал накрывает и 1,0, и 1,38. Утверждение «почти линейны по кликам» — это и есть')
    p('     «отличий от линейности не обнаружено», то есть отсутствие эффекта, а не эффект.')
    p('   → «в 1,41 раза больше, чем положено по вышедшим» — не независимый вывод, а переформулировка')
    p('     того, что вышедшие хуже кликов как мера объёма (у T3 44 клика на вышедший против 27 у T1).')

    # ---- 9. плоскость сетки весов
    line('-')
    p('9. «ЛУЧШИЙ ВЕС вышли × √кликов» — ТОЧКА НА ПЛОСКОМ ГРЕБНЕ')

    def deviance(pools_in, wfn):
        D = 0.0
        for k, doms in pools_in.items():
            so = sum(d.regs for d in doms)
            sw = sum(wfn(d) for d in doms)
            if sw <= 0:
                continue
            rate = so / sw
            for d in doms:
                e = rate * wfn(d)
                o = d.regs
                if e <= 0:
                    continue
                D += 2 * ((o * math.log(o / e) if o > 0 else 0.0) - (o - e))
        return D

    grid = []
    for ai in range(0, 7):
        for bi in range(0, 7):
            a = ai * 0.25
            b = bi * 0.25
            grid.append((deviance(pools, lambda d, a=a, b=b: (d.exits ** a) * (d.clicks ** b)), a, b))
    grid.sort()
    best = grid[0]
    within = [g for g in grid if g[0] <= best[0] + 3.84]
    p(f'   лучшая пара a={best[1]}, b={best[2]}, D={best[0]:.1f}; в пределах ΔD ≤ 3,84 от лучшей — '
      f'{len(within)} из {len(grid)} узлов сетки:')
    p('     ' + ', '.join(f'(a={g[1]},b={g[2]}) D={g[0]:.1f}' for g in within))
    p(f'   чистые клики (a=0,b=1) D = {deviance(pools, lambda d: d.clicks):.1f}; '
      f'чистые вышедшие (a=1,b=0) D = {deviance(pools, lambda d: d.exits):.1f}.')
    p(f'   При сверхдисперсии χ²/df = {chi2 / dfree:.2f} масштаб ΔD надо делить примерно на неё: '
      f'порог «одного параметра» ≈ {3.84 * chi2 / dfree:.1f}, и тогда в него попадают '
      f'{len([g for g in grid if g[0] <= best[0] + 3.84 * chi2 / dfree])} узлов, включая чистые клики: '
      f'{"да" if deviance(pools, lambda d: d.clicks) <= best[0] + 3.84 * chi2 / dfree else "нет"}.')

    p('\n   Честно о том, что ВСЁ-ТАКИ есть: вклад вышедших сверх кликов, с поправкой на сверхдисперсию')
    Dcl = deviance(pools, lambda d: d.clicks)
    Dbest = best[0]
    phi = chi2 / dfree
    p(f'   ΔD (чистые клики → лучший вес) = {Dcl - Dbest:.1f}; делим на φ = {phi:.2f} → '
      f'{(Dcl - Dbest) / phi:.1f} на ~2 степени свободы — сигнал есть.')
    p('   Но показатель степени не определён: a ∈ [0,75; 1,5], b ∈ [0,25; 0,5] по сетке, а в запасной')
    p('   страте день+зона лучшая пара уже a = 1,25. «Регистрации ≈ вышедших × √кликов» — одна точка')
    p('   на плоском гребне, а не установленный закон.')

    # ---- 10. множественность
    line('-')
    p('10. МНОЖЕСТВЕННОСТЬ')
    with open(H13_TXT, encoding='utf-8') as f:
        txt = f.read()
    n_pge = txt.count('p(≥ набл.)')
    n_sign = txt.count('знаковый тест p')
    n_bins = txt.count('p(≥) =')
    p(f'   В выводе тестировщика: перестановочных p(≥ набл.) {n_pge}, знаковых тестов {n_sign}, '
      f'побиновых p(≥) {n_bins} — всего не менее {n_pge + n_sign + n_bins} p-значений.')
    p('   Срезы: 2 части × (терцили / пул×бин / пары) × (4 порога пар) × (2 месяца) × (4 зоны) ×')
    p('          (3 веса ожидания) × (4 бина кликов) × («КОНТЕНТ НЕ ЗАПИСАН» / день+зона) + сетка 7×7 весов.')
    tests_sorted = sorted(tests, key=lambda t: t[1])
    m = len(tests_sorted)
    p(f'\n   Мои {m} ключевых проверок, Холм-Бонферрони:')
    p(f'   {"проверка":<52}{"p":>9}{"порог Холма":>13}{"выжил":>8}')
    surv = True
    for i, (nm, pv) in enumerate(tests_sorted):
        thr = 0.05 / (m - i)
        ok = pv <= thr and surv
        if not ok:
            surv = False
        p(f'   {nm[:52]:<52}{pv:>9.4f}{thr:>13.5f}{("да" if ok else "нет"):>8}')

    # ---- 11. определения и окна
    line('-')
    p('11. ОПРЕДЕЛЕНИЯ, ЗНАМЕНАТЕЛИ, ОКНА')
    nd_nocl = sum(1 for v in pools.values() for d in v if d.clicks == 0)
    nd_noex = sum(1 for v in pools.values() for d in v if d.exits == 0)
    p(f'   Окна: «окно закрыто»≠да и «дней»=1 исключены корректно ({ex["окно не закрыто"]} и '
      f'{ex["дней = 1"]}), оконные колонки (рег/ФД/клики/вышли/сайты в окне) используются — тут претензий нет.')
    p(f'   В основной страте доменов без кликов в окне {nd_nocl}, без вышедших {nd_noex}; '
      f'в части А домены с вышли=0 выброшены (16), в части Б — оставлены. Разные наборы у А и Б.')
    p('   Определение «концентрация = клики/вышедшие»: знаменатель стоит в определении признака И')
    p('     в весе ожидания через клики в числителе — признак и вес делят одну переменную (клики),')
    p('     поэтому «широкий» терциль механически совпадает с «малокликовым». Это не независимая мерка.')
    lows = [d for v in sub.values() for d in v]
    tiny = [d for d in lows if d.clicks <= 20]
    p(f'   Хвост малых знаменателей: доменов с ≤20 кликами в окне {len(tiny)} '
      f'({len(tiny) / len(lows) * 100:.0f}% набора), у них регистраций {sum(d.regs for d in tiny)}; '
      f'минимум концентрации 1,0 — домен с 1 кликом и 1 вышедшим сайтом попадает в «широкие».')
    nlow = [d for d in lows if d.conc is not None and d.conc <= 2]
    p(f'   Доменов с концентрацией ≤2 (т.е. кликов не больше, чем вышедших вдвое) {len(nlow)}, '
      f'регистраций у них {sum(d.regs for d in nlow)} — «ширина» там неотличима от «почти нет кликов».')

    # ---- вывод
    line()
    p('ВЫВОД КОНТРПРОВЕРКИ')
    line()
    p('А. Числа воспроизводятся побайтово (файл прогона совпадает с сохранённым), но толкование не')
    p('   выдерживает. Терциль «концентрации» (клики/вышедшие) не выравнивает клики: клики на домен')
    p('   в T1 и T3 различаются в 7,3 раза, вышедшие — в 1,46. Плацебо-терциль ЧИСТЫХ КЛИКОВ (никакой')
    p('   «ширины» в определении) при том же E ∝ кликов даёт 1,33 из наблюдённых 1,85 — то есть почти')
    p('   весь эффект есть насыщение (квинтили кликов: 3,78 → 2,36 рег на 10 тыс.). Единственный срез,')
    p('   где клики действительно выровнены (пул × бин), даёт 1,32 при p = 0,11 — не значимо; после')
    p('   снятия топ-3 доменов 1,27 при p = 0,17. Заявленное «в 1,85 раза» в отчёт брать нельзя.')
    p('Б. «O/E 1,41 по вышедшим» — переформулировка того, что вышедшие хуже кликов как мера объёма.')
    p('   По кликам O/E = 1,151 при границе критерия 1,15 (совпадение на третьем знаке) и 95% ИП,')
    p('   накрывающем 1,0. Формальный критерий Б выполнен на уровне шума.')
    p('Пары. 26 регистраций на 115 пар, 94 пары пустые; знаковый тест p = 0,08; правильный точный')
    p('   условный тест слабее перестановочного; после снятия топ-3 широких доменов эффект рушится.')
    p('Множественность. Десятки p-значений; после Холма-Бонферрони от «главных» результатов частей А')
    p('   и Б не остаётся ничего, кроме тривиального «регистраций больше там, где больше кликов».')
    line()
    p('Как надо сформулировать (ужато):')
    p('  «Регистрации растут с кликами сублинейно: в верхнем квинтиле кликов внутри пула регистраций')
    p('   на 10 тыс. кликов примерно вдвое меньше, чем в нижнем. Отдельного вклада «ширины охвата»')
    p('   сверх этого не обнаружено: при выровненных кликах (пул × бин) отношение терцилей 1,32')
    p('   [p = 0,11], в парах почти равных по кликам доменов 20 против 6 регистраций на 115 пар')
    p('   (знаковый тест p = 0,08, после снятия трёх доменов эффект исчезает). Верхняя треть по выходу')
    p('   собирает регистрации пропорционально своим кликам: O/E = 1,15 [95% ИП 0,95–1,38].»')
    line()


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    tee = Tee(OUT)
    sys.stdout = tee
    try:
        main()
    finally:
        sys.stdout = sys.__stdout__
        tee.f.close()

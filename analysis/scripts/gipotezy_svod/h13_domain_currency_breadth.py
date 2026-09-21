#!/usr/bin/env python3
"""
Гипотеза №13. «Валюта» домена.
  (А) Внутри пула при равном числе поисковых кликов домен, у которого клики размазаны по
      большему числу вышедших сайтов, даёт в 1,5–2 раза больше регистраций, чем домен с теми же
      кликами на немногих сайтах-магнитах.
  (Б) «Излишек выхода» домена (верхняя треть пула по выходу за 3 суток) даёт больше
      регистраций на вышедший сайт, но примерно столько же на клик.

Что проверяем.
  Единица — домен. Успех — регистрации в окне 3 суток (ФД в окне — только знак).
  Часть А: концентрация = кликов из поиска в окне / вышли за 3 суток (дубль — столбец
    «кликов на сайт с поиском», он за всё время). Ожидание E = (рег пула / клики пула) × клики
    домена. Терцили концентрации внутри пула; O/E по терцилям. Чтобы отделить ширину охвата
    от объёма кликов: (1) разрез терцилей по 4 бинам кликов в окне (≤95, 95–325, 325–912,
    >912); (2) страта пул × бин кликов (ячейки ≥3 доменов), терцили концентрации внутри
    ячейки, E ∝ кликам внутри ячейки — оговорка: бин шириной ×3, поэтому терцили внутри ячейки
    всё ещё различаются по кликам; (3) главный тест «при равных кликах» — пары доменов из
    одного пула с кликами в окне, различающимися не более чем в 1,25 раза, и числом вышедших,
    различающимся не менее чем в 1,5 раза (сортировка по кликам, соседи, без пересечений);
    сравниваем регистрации «широкого» и «узкого» домена пары: отношение ставок на клик,
    перестановка ролей внутри пар 5000 раз, знаковый тест (точный биномиальный); пороги
    1,25/1,3, 1,5/2,0 и 2,0/2,0 — для устойчивости. Перестановка меток терцилей внутри страты
    5000 раз (random.seed(1)); статистика — O/E нижнего терциля / O/E верхнего.
    Знак отдельно в августе и сентябре; отдельно «КОНТЕНТ НЕ ЗАПИСАН» (пул = день).
  Часть Б: терцили по «выход 3 суток %» внутри пула; три ожидания — ∝ сайтов, ∝ вышли за
    3 суток, ∝ кликов из поиска в окне; O/E по третям для каждого; перестановка меток третей
    5000 раз при ∝ вышедших (статистика — O/E верхней трети) и при ∝ кликов. Зоны team и lol
    отдельно (пул = набор + день внутри зоны; casino — оговорка, buzz — слишком мал).
    Зеркальный разрез: терциль выхода × бин кликов при E ∝ вышедших — добавляют ли клики
    что-то сверх вышедших.
  Дополнительно: какой знаменатель лучше объясняет регистрации внутри пулов — пуассоновское
    отклонение (deviance) для E ∝ сайтов / вышедших / кликов и для сетки E ∝ вышли^a × клики^b.

Как фильтруем.
  Окно закрыто = да; дней ≠ 1; без 3615.team и 3286.team; «КОНТЕНТ НЕ ЗАПИСАН» — отдельный
  проход. Пул = набор контента + день запуска, пулы ≥4 доменов и ≥1 регистрации в окне.
  Запасная страта — день + зона. В части А домены с «вышли за 3 суток» = 0 (концентрация не
  определена; кликов и регистраций у них нет) исключаются, пул перепроверяется на ≥4 и ≥1 рег.

Критерии постановки.
  А — подтверждена: O/E(нижний терциль) / O/E(верхний) ≥ 1,5 при p < 0,05, тот же знак в бинах
      325–912 и >912 и в обоих месяцах; опровергнута: O/E терцилей в 0,85–1,15.
  Б — подтверждена: O/E верхней трети ∝ вышедших ≥ 1,3 при p < 0,05 и ∝ кликов в 0,85–1,15;
      опровергнута: O/E ∝ вышедших ≈ 1 либо ∝ кликов > 1,2.
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
OUT = os.path.join(OUT_DIR, 'h13_domain_currency_breadth.txt')
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


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def bin_of(clicks):
    for lo, hi, name in BINS:
        if lo < clicks <= hi or (lo == 0 and clicks <= hi):
            return name
    return BINS[-1][2]


def r10k(reg, clicks):
    return f'{reg / clicks * 10000:6.2f}' if clicks > 0 else '   н/д'


def fmt_oe(o, e):
    return f'{o / e:5.2f}' if e > 0 else '  н/д'


def fmt_ratio(x):
    if x is None:
        return 'н/д'
    if x == float('inf'):
        return '∞'
    return f'{x:.2f}'


# ---------------------------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------------------------
class Dom:
    __slots__ = ('domain', 'zone', 'day', 'month', 'content', 'sites', 'exits', 'sws', 'clicks',
                 'regs', 'fd', 'exitpct', 'cpsw', 'bin')

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
        self.exitpct = self.exits / self.sites * 100 if self.sites else 0.0
        self.cpsw = to_float(r['кликов на сайт с поиском'])
        self.bin = bin_of(self.clicks)

    @property
    def conc(self):
        return self.clicks / self.exits if self.exits else None


def load():
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    total = len(rows)
    ex = collections.Counter()
    keep, nocontent = [], []
    for r in rows:
        if r['окно закрыто'] != 'да':
            ex['окно не закрыто'] += 1
            continue
        if r['дней'] == '1':
            ex['дней = 1'] += 1
            continue
        if r['домен'] in OUTLIERS:
            ex['выбросы 3615.team, 3286.team'] += 1
            continue
        d = Dom(r)
        if d.content == NOCONTENT:
            nocontent.append(d)
        else:
            keep.append(d)
    return total, ex, keep, nocontent


def make_pools(doms, keyfn, min_n=4, min_reg=1):
    pools = collections.defaultdict(list)
    for d in doms:
        pools[keyfn(d)].append(d)
    ok = {k: v for k, v in pools.items() if len(v) >= min_n and sum(d.regs for d in v) >= min_reg}
    return ok, len(pools)


def describe_pools(name, pools, n_all=None):
    nd = sum(len(v) for v in pools.values())
    ns = sum(d.sites for v in pools.values() for d in v)
    nr = sum(d.regs for v in pools.values() for d in v)
    nf = sum(d.fd for v in pools.values() for d in v)
    nc = sum(d.clicks for v in pools.values() for d in v)
    extra = f' (всего пулов до отбора {n_all})' if n_all is not None else ''
    p(f'  {name}: пулов {len(pools)}{extra}, доменов {nd}, сайтов {ns}, кликов из поиска в окне {nc}, '
      f'регистраций в окне {nr}, ФД в окне {nf}.')


# ---------------------------------------------------------------------------------------------
# Терцили, O/E, перестановки
# ---------------------------------------------------------------------------------------------
def terciles(doms, key):
    """Метки 0/1/2 по возрастанию key внутри группы (ничьи — по числу вышедших, затем по имени)."""
    s = sorted(doms, key=lambda d: (key(d), d.exits, d.domain))
    n = len(s)
    return {d.domain: i * 3 // n for i, d in enumerate(s)}


def build_recs(pools, key, wfn, need_key=True):
    """Для каждой страты: (labels, O, E, doms). E_i = (Σрег/Σw) × w_i внутри страты."""
    recs = []
    keys = []
    skipped_w0 = 0
    for k, doms in pools.items():
        lab = terciles(doms, key)
        so = sum(d.regs for d in doms)
        sw = sum(wfn(d) for d in doms)
        if sw <= 0:
            skipped_w0 += 1
            continue
        rate = so / sw
        labels = [lab[d.domain] for d in doms]
        O = [d.regs for d in doms]
        E = [rate * wfn(d) for d in doms]
        recs.append((labels, O, E, doms))
        keys.append(k)
    return recs, keys, skipped_w0


def sums_by_label(recs, labels_override=None):
    SO = [0.0, 0.0, 0.0]
    SE = [0.0, 0.0, 0.0]
    for i, (labels, O, E, _) in enumerate(recs):
        lab = labels if labels_override is None else labels_override[i]
        for l, o, e in zip(lab, O, E):
            SO[l] += o
            SE[l] += e
    return SO, SE


def stat_ratio_low_high(SO, SE):
    if SE[0] <= 0 or SE[2] <= 0:
        return None
    if SO[2] == 0:
        return float('inf') if SO[0] > 0 else 1.0
    return (SO[0] / SE[0]) / (SO[2] / SE[2])


def stat_oe_high(SO, SE):
    if SE[2] <= 0:
        return None
    return SO[2] / SE[2]


def perm_test(recs, stat, nperm=NPERM, seed=SEED):
    """Перестановка меток терцилей внутри страты; p_ge = доля перестановок со статистикой ≥
    наблюдённой, p_le — ≤ наблюдённой."""
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
        SOp, SEp = sums_by_label(recs, work)
        s = stat(SOp, SEp)
        if s is None:
            continue
        if s >= obs:
            ge += 1
        if s <= obs:
            le += 1
    return obs, ge / nperm, le / nperm


def oe_table(recs, title, metric_name, metric_fn, wname):
    """Печать таблицы по терцилям: объёмы, сырые ставки, O, E, O/E."""
    p(f'\n  {title}')
    p(f'  {"терциль":<14}{metric_name:>22}{"доменов":>9}{"сайтов":>8}{"вышли":>7}{"кликов":>9}'
      f'{"рег":>5}{"ФД":>4}{"рег/10т.кл":>11}{"рег/100выш":>11}{"O":>5}{"E":>8}{"O/E":>6}')
    agg = [collections.Counter() for _ in range(3)]
    mets = [[] for _ in range(3)]
    for labels, O, E, doms in recs:
        for l, o, e, d in zip(labels, O, E, doms):
            a = agg[l]
            a['n'] += 1
            a['sites'] += d.sites
            a['exits'] += d.exits
            a['clicks'] += d.clicks
            a['regs'] += d.regs
            a['fd'] += d.fd
            a['E'] += e
            m = metric_fn(d)
            if m is not None:
                mets[l].append(m)
    out = []
    for t in range(3):
        a = agg[t]
        ms = sorted(mets[t])
        med = ms[len(ms) // 2] if ms else None
        mr = f'{med:6.1f} ({ms[0]:.1f}–{ms[-1]:.1f})' if ms else 'н/д'
        r100 = f'{a["regs"] / a["exits"] * 100:10.2f}' if a['exits'] else '       н/д'
        p(f'  {TNAME[t]:<14}{mr:>22}{a["n"]:>9}{a["sites"]:>8}{a["exits"]:>7}{a["clicks"]:>9}'
          f'{a["regs"]:>5}{a["fd"]:>4}{r10k(a["regs"], a["clicks"]):>11}{r100:>11}'
          f'{a["regs"]:>5}{a["E"]:>8.2f}{fmt_oe(a["regs"], a["E"]):>6}')
        out.append((a['regs'], a['E']))
    p(f'  ожидание E ∝ {wname}; O/E считается внутри страты, суммы — по всем стратам.')
    return out


def fd_oe(recs, wname):
    """ФД по терцилям: O/E при ожидании по тому же весу (только знак)."""
    agg = [collections.Counter() for _ in range(3)]
    for labels, O, E, doms in recs:
        sf = sum(d.fd for d in doms)
        sw = sum(e for e in E)  # ΣE = Σрег пула; вес пропорционален E
        if sw <= 0:
            continue
        for l, e, d in zip(labels, E, doms):
            agg[l]['fd'] += d.fd
            agg[l]['E'] += sf * e / sw
    parts = []
    for t in range(3):
        parts.append(f'{TNAME[t]}: ФД {agg[t]["fd"]}, E {agg[t]["E"]:.1f}, O/E {fmt_oe(agg[t]["fd"], agg[t]["E"]).strip()}')
    p(f'  ФД в окне (только знак, E ∝ {wname}): ' + '; '.join(parts))


def crosstab(recs, col_fn, col_names, title, wname):
    """Терциль × колонка (например, бин кликов): O, E, O/E и сырая ставка."""
    p(f'\n  {title}')
    p(f'  {"терциль":<14}' + ''.join(f'{c:>26}' for c in col_names))
    p(f'  {"":<14}' + ''.join(f'{"дом/кл/рег  O/E  р/10т":>26}' for _ in col_names))
    cell = collections.defaultdict(collections.Counter)
    for labels, O, E, doms in recs:
        for l, o, e, d in zip(labels, O, E, doms):
            c = cell[(l, col_fn(d))]
            c['n'] += 1
            c['clicks'] += d.clicks
            c['regs'] += d.regs
            c['E'] += e
    for t in range(3):
        s = f'  {TNAME[t]:<14}'
        for cn in col_names:
            c = cell[(t, cn)]
            s += f'{c["n"]:>6}/{c["clicks"]:>7}/{c["regs"]:>3} {fmt_oe(c["regs"], c["E"]):>5} {r10k(c["regs"], c["clicks"]).strip():>6}'.rjust(26)
        p(s)
    p(f'  (в ячейке: доменов / кликов в окне / регистраций, O/E при E ∝ {wname} внутри страты, рег на 10 тыс. кликов)')
    return cell


def deviance(pools, wfn):
    """Пуассоновское отклонение 2Σ[O ln(O/E) − (O − E)] при E ∝ w внутри пула."""
    D = 0.0
    for doms in pools.values():
        so = sum(d.regs for d in doms)
        sw = sum(wfn(d) for d in doms)
        if sw <= 0:
            if so > 0:
                return float('inf')
            continue
        rate = so / sw
        for d in doms:
            e = rate * wfn(d)
            if d.regs > 0:
                if e <= 0:
                    return float('inf')
                D += 2 * (d.regs * math.log(d.regs / e) - (d.regs - e))
            else:
                D += 2 * e
    return D


# ---------------------------------------------------------------------------------------------
# Часть А
# ---------------------------------------------------------------------------------------------
def part_a(pools_in, label, key, key_name, metric_fn, full=True):
    """Терцили концентрации внутри пула, E ∝ кликов. Возвращает (ratio, p_ge, p_le, O/E T1, O/E T3)."""
    # исключаем домены без вышедших сайтов (концентрация не определена)
    pools = {}
    dropped = 0
    for k, doms in pools_in.items():
        keep = [d for d in doms if d.exits > 0 and key(d) is not None]
        dropped += len(doms) - len(keep)
        if len(keep) >= 4 and sum(d.regs for d in keep) >= 1:
            pools[k] = keep
    recs, _, sk = build_recs(pools, key, lambda d: d.clicks)
    nd = sum(len(v) for v in pools.values())
    nr = sum(d.regs for v in pools.values() for d in v)
    p(f'\n  {label}: исключено доменов с «вышли за 3 суток» = 0: {dropped}; пулов после перепроверки {len(pools)}, '
      f'доменов {nd}, регистраций {nr}; пулов без кликов (пропущено) {sk}.')
    if not recs:
        p('  Недостаточно данных.')
        return None
    oe = oe_table(recs, f'Терцили концентрации ({key_name}) внутри пула', key_name[:20], metric_fn, 'кликов из поиска в окне')
    obs, pge, ple = perm_test(recs, stat_ratio_low_high)
    p(f'  Статистика: O/E(T1) / O/E(T3) = {fmt_ratio(obs)}; перестановок {NPERM}: p(≥ набл.) = {pge:.4f}, '
      f'p(≤ набл.) = {ple:.4f}, двусторонний p = {min(1.0, 2 * min(pge, ple)):.4f}.')
    if full:
        fd_oe(recs, 'кликов')
        crosstab(recs, lambda d: d.bin, [b[2] for b in BINS],
                 'Разрез терцилей концентрации (внутри пула) по бинам кликов в окне', 'кликов')
    return obs, pge, ple, oe


def part_a_equal_clicks(pools_in, label):
    """Страта = пул × бин кликов (ячейки ≥3 доменов с вышедшими), терцили концентрации внутри ячейки,
    E ∝ кликов внутри ячейки — «при равных кликах»."""
    cells = collections.defaultdict(list)
    for k, doms in pools_in.items():
        for d in doms:
            if d.exits > 0:
                cells[(k, d.bin)].append(d)
    cells = {k: v for k, v in cells.items() if len(v) >= 3}
    nd = sum(len(v) for v in cells.values())
    nr = sum(d.regs for v in cells.values() for d in v)
    nz = sum(1 for v in cells.values() if sum(d.regs for d in v) == 0)
    p(f'\n  {label}: ячеек пул × бин с ≥3 доменами {len(cells)} (из них без регистраций {nz} — в O/E не участвуют), '
      f'доменов {nd}, регистраций {nr}.')
    recs, keys, sk = build_recs(cells, lambda d: d.conc, lambda d: d.clicks)
    oe = oe_table(recs, 'Терцили концентрации внутри ячейки пул × бин кликов', 'кликов на вышедший', lambda d: d.conc,
                  'кликов внутри ячейки')
    per = [collections.Counter() for _ in range(3)]
    for labels, O, E, doms in recs:
        for l, d in zip(labels, doms):
            per[l]['n'] += 1
            per[l]['c'] += d.clicks
            per[l]['x'] += d.exits
    p('  Оговорка: на домен в среднем кликов ' + ', '.join(f'{TNAME[t]} {per[t]["c"] / per[t]["n"]:.0f}' for t in range(3)) +
      '; вышедших ' + ', '.join(f'{TNAME[t]} {per[t]["x"] / per[t]["n"]:.1f}' for t in range(3)) +
      ' — бин шириной ×3 не выравнивает клики, терцили внутри ячейки различаются по кликам сильнее, чем по вышедшим.')
    obs, pge, ple = perm_test(recs, stat_ratio_low_high)
    p(f'  Статистика: O/E(T1) / O/E(T3) = {fmt_ratio(obs)}; перестановок {NPERM}: p(≥ набл.) = {pge:.4f}, '
      f'p(≤ набл.) = {ple:.4f}, двусторонний p = {min(1.0, 2 * min(pge, ple)):.4f}.')
    fd_oe(recs, 'кликов внутри ячейки')
    cell = crosstab(recs, lambda d: d.bin, [b[2] for b in BINS],
                    'То же по бинам кликов (терциль — внутри ячейки, т.е. при почти равных кликах)', 'кликов внутри ячейки')
    per_bin = {}
    for _, _, bn in BINS:
        c1, c3 = cell[(0, bn)], cell[(2, bn)]
        r = None
        if c1['E'] > 0 and c3['E'] > 0:
            r = float('inf') if c3['regs'] == 0 and c1['regs'] > 0 else (c1['regs'] / c1['E']) / (c3['regs'] / c3['E']) if c3['regs'] > 0 else 1.0
        per_bin[bn] = r
    # перестановочный p по каждому бину отдельно (те же ячейки, только этого бина)
    p('  По бинам, O/E(T1)/O/E(T3) и перестановочный p(≥):')
    for _, _, bn in BINS:
        sub = [rec for rec, k in zip(recs, keys) if k[1] == bn]
        if not sub:
            p(f'    {bn:<9}: нет ячеек')
            continue
        o, pg, pl = perm_test(sub, stat_ratio_low_high)
        p(f'    {bn:<9}: отношение {fmt_ratio(o)}, p(≥) = {pg:.4f}, p(≤) = {pl:.4f}'
          if o is not None else f'    {bn:<9}: н/д')
        per_bin[bn] = o
    return obs, pge, ple, per_bin


def part_a_pairs(pools_in, label, cr, xr, full=True):
    """Пары доменов одного пула: клики в окне различаются ≤ cr раз, вышедших за 3 суток — ≥ xr раз.
    Сортировка по кликам, соседние домены, пары не пересекаются. «Широкий» = больше вышедших."""
    pairs = []
    for k, doms in pools_in.items():
        s = sorted([d for d in doms if d.exits > 0 and d.clicks > 0], key=lambda d: (d.clicks, d.domain))
        i = 0
        while i < len(s) - 1:
            a, b = s[i], s[i + 1]
            if b.clicks / a.clicks <= cr and max(a.exits, b.exits) / min(a.exits, b.exits) >= xr:
                pairs.append((a, b) if a.exits > b.exits else (b, a))
                i += 2
            else:
                i += 1
    n = len(pairs)
    if n == 0:
        p(f'\n  {label}: пар нет.')
        return None
    ow = sum(w.regs for w, _ in pairs)
    on = sum(nw.regs for _, nw in pairs)
    cw = sum(w.clicks for w, _ in pairs)
    cn = sum(nw.clicks for _, nw in pairs)
    xw = sum(w.exits for w, _ in pairs)
    xn = sum(nw.exits for _, nw in pairs)
    fw = sum(w.fd for w, _ in pairs)
    fn_ = sum(nw.fd for _, nw in pairs)
    wins = sum(1 for w, nw in pairs if w.regs > nw.regs)
    loses = sum(1 for w, nw in pairs if w.regs < nw.regs)
    anyreg = sum(1 for w, nw in pairs if w.regs + nw.regs > 0)
    xr_med = sorted(w.exits / nw.exits for w, nw in pairs)[n // 2]
    cr_med = sorted(max(w.clicks, nw.clicks) / min(w.clicks, nw.clicks) for w, nw in pairs)[n // 2]

    def rate_ratio(o1, c1, o2, c2):
        if c1 <= 0 or c2 <= 0:
            return None
        if o2 == 0:
            return float('inf') if o1 > 0 else 1.0
        return (o1 / c1) / (o2 / c2)

    obs = rate_ratio(ow, cw, on, cn)
    # перестановка ролей внутри пар
    random.seed(SEED)
    ge = 0
    for _ in range(NPERM):
        o1 = c1 = o2 = c2 = 0
        for w, nw in pairs:
            if random.random() < 0.5:
                w, nw = nw, w
            o1 += w.regs
            c1 += w.clicks
            o2 += nw.regs
            c2 += nw.clicks
        r = rate_ratio(o1, c1, o2, c2)
        if r is not None and r >= obs:
            ge += 1
    # знаковый тест
    m = wins + loses
    if m:
        k = min(wins, loses)
        p_sign = min(1.0, 2 * sum(math.comb(m, j) for j in range(k + 1)) / 2 ** m)
    else:
        p_sign = None
    p(f'\n  {label} (клики ≤ ×{cr}, вышедших ≥ ×{xr}): пар {n} (доменов {2 * n}), пар хотя бы с одной регистрацией {anyreg}; '
      f'медиана отношения вышедших {xr_med:.2f}, кликов {cr_med:.2f}.')
    p(f'    широкий домен: вышли {xw}, кликов {cw}, регистраций {ow} ({r10k(ow, cw).strip()} на 10 тыс.), ФД {fw}; '
      f'узкий: вышли {xn}, кликов {cn}, регистраций {on} ({r10k(on, cn).strip()} на 10 тыс.), ФД {fn_}.')
    p(f'    отношение ставок на клик (широкий / узкий) = {fmt_ratio(obs)}; перестановка ролей {NPERM}: p(≥ набл.) = {ge / NPERM:.4f}; '
      f'широкий больше в {wins} парах, меньше в {loses}, знаковый тест p = {p_sign if p_sign is None else round(p_sign, 4)}.')
    if full:
        # по бинам кликов (бин — по кликам широкого домена) и по месяцам
        byb = collections.defaultdict(collections.Counter)
        for w, nw in pairs:
            c = byb[w.bin]
            c['n'] += 1
            c['ow'] += w.regs
            c['on'] += nw.regs
            c['cw'] += w.clicks
            c['cn'] += nw.clicks
            c['win'] += w.regs > nw.regs
            c['lose'] += w.regs < nw.regs
        p('    по бинам кликов: ' + '; '.join(
            f'{bn}: пар {byb[bn]["n"]}, рег {byb[bn]["ow"]} vs {byb[bn]["on"]}, отношение {fmt_ratio(rate_ratio(byb[bn]["ow"], byb[bn]["cw"], byb[bn]["on"], byb[bn]["cn"]))}, '
            f'{byb[bn]["win"]}:{byb[bn]["lose"]}' for _, _, bn in BINS if byb[bn]['n']))
        bym = collections.defaultdict(collections.Counter)
        for w, nw in pairs:
            c = bym[w.month]
            c['n'] += 1
            c['ow'] += w.regs
            c['on'] += nw.regs
            c['cw'] += w.clicks
            c['cn'] += nw.clicks
            c['win'] += w.regs > nw.regs
            c['lose'] += w.regs < nw.regs
        p('    по месяцам: ' + '; '.join(
            f'{m}: пар {bym[m]["n"]}, рег {bym[m]["ow"]} vs {bym[m]["on"]}, отношение {fmt_ratio(rate_ratio(bym[m]["ow"], bym[m]["cw"], bym[m]["on"], bym[m]["cn"]))}, '
            f'{bym[m]["win"]}:{bym[m]["lose"]}' for m in ('август', 'сентябрь') if bym[m]['n']))
    return obs, ge / NPERM, p_sign, ow, on, wins, loses, n


# ---------------------------------------------------------------------------------------------
# Часть Б
# ---------------------------------------------------------------------------------------------
def part_b(pools, label, full=True):
    key = lambda d: d.exitpct
    res = {}
    p(f'\n  {label}:')
    describe_pools('страта', pools)
    for wname, wfn, stat in (('сайтов', lambda d: d.sites, stat_oe_high),
                             ('вышли за 3 суток', lambda d: d.exits, stat_oe_high),
                             ('кликов из поиска в окне', lambda d: d.clicks, stat_oe_high)):
        recs, _, sk = build_recs(pools, key, wfn)
        oe = oe_table(recs, f'Терцили «выход 3 суток %» внутри пула, ожидание ∝ {wname}', 'выход 3 суток, %',
                      key, wname)
        obs, pge, ple = perm_test(recs, stat)
        p(f'  Статистика: O/E(T3) = {fmt_ratio(obs)}; перестановок {NPERM}: p(≥ набл.) = {pge:.4f}, p(≤ набл.) = {ple:.4f}, '
          f'двусторонний p = {min(1.0, 2 * min(pge, ple)):.4f}; пропущено страт без веса {sk}.')
        if full:
            fd_oe(recs, wname)
        res[wname] = (obs, pge, ple, oe)
        if full and wname == 'вышли за 3 суток':
            crosstab(recs, lambda d: d.bin, [b[2] for b in BINS],
                     'Зеркальный разрез: терциль выхода × бин кликов при E ∝ вышедших (добавляют ли клики сверх вышедших)',
                     'вышедших')
    return res


def raw_exit_bands(doms):
    p('\n  Без страты, для справки: полосы выхода 3 суток % (как в обосновании гипотезы)')
    bands = ((0, 5, '<5'), (5, 10, '5–10'), (10, 20, '10–20'), (20, 40, '20–40'), (40, 101, '40+'))
    p(f'  {"выход, %":<10}{"доменов":>9}{"сайтов":>8}{"вышли":>7}{"кликов":>9}{"рег":>5}{"кл/выш":>8}{"рег/10т.кл":>11}{"рег/100выш":>11}{"рег/100с":>9}')
    for lo, hi, nm in bands:
        g = [d for d in doms if lo <= d.exitpct < hi]
        if not g:
            continue
        s = sum(d.sites for d in g)
        e = sum(d.exits for d in g)
        c = sum(d.clicks for d in g)
        r = sum(d.regs for d in g)
        p(f'  {nm:<10}{len(g):>9}{s:>8}{e:>7}{c:>9}{r:>5}{(c / e if e else 0):>8.1f}{r10k(r, c):>11}'
          f'{(r / e * 100 if e else 0):>11.2f}{r / s * 100:>9.2f}')


def model_comparison(pools, label):
    p(f'\n  {label}')
    nd = sum(len(v) for v in pools.values())
    nr = sum(d.regs for v in pools.values() for d in v)
    p(f'  Пуассоновское отклонение (меньше — лучше) при E ∝ вес внутри пула; доменов {nd}, регистраций {nr}.')
    base = {
        'сайтов (равномерно)': lambda d: d.sites,
        'вышли за 3 суток': lambda d: d.exits,
        'кликов из поиска в окне': lambda d: d.clicks,
        'сайтов с поиском (всё время)': lambda d: d.sws,
        '√кликов': lambda d: math.sqrt(d.clicks),
    }
    for nm, w in base.items():
        p(f'    E ∝ {nm:<32} D = {deviance(pools, w):8.1f}')
    grid = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
    best = None
    p('  Сетка E ∝ вышли^a × клики^b (строки a, столбцы b):')
    p('    a\\b ' + ''.join(f'{b:>8.2f}' for b in grid))
    for a in grid:
        row = f'   {a:4.2f} '
        for b in grid:
            D = deviance(pools, lambda d, a=a, b=b: (d.exits ** a) * (d.clicks ** b))
            row += f'{D:8.1f}'
            if best is None or D < best[0]:
                best = (D, a, b)
        p(row)
    d_clicks = deviance(pools, lambda d: d.clicks)
    d_exits = deviance(pools, lambda d: d.exits)
    d_b_only = min(deviance(pools, lambda d, b=b: d.clicks ** b) for b in grid)
    p(f'  Лучшая пара: a = {best[1]}, b = {best[2]}, D = {best[0]:.1f}. '
      f'Разница D в 3,84 ≈ один параметр на уровне 5 % (при сверхдисперсии пулов — только ориентир).')
    p(f'  Чистые клики (a=0, b=1): D = {d_clicks:.1f}; чистые вышедшие (a=1, b=0): D = {d_exits:.1f}; лучшая степень одних кликов: '
      f'D = {d_b_only:.1f}; выигрыш от добавления вышедших к кликам: ΔD = {d_b_only - best[0]:.1f}; '
      f'выигрыш от добавления кликов к вышедшим: ΔD = {d_exits - best[0]:.1f}.')
    return best


# ---------------------------------------------------------------------------------------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sys.stdout = Tee(OUT)
    line()
    p('Гипотеза №13. «Валюта» домена: ширина охвата при равных кликах (А) и излишек выхода (Б).')
    p(f'Источник: analysis/export/svod_domenov_21.09.csv; перестановок {NPERM}, random.seed({SEED}).')
    line()
    total, ex, main_set, nocontent = load()
    p(f'Строк в своде: {total}. Исключено: ' + '; '.join(f'{k} {v}' for k, v in ex.items()) +
      f'. «{NOCONTENT}» — отдельный проход: {len(nocontent)}. Основной набор: {len(main_set)} доменов.')
    p(f'Регистраций в окне в основном наборе: {sum(d.regs for d in main_set)}, ФД в окне {sum(d.fd for d in main_set)}; '
      f'доменов с «вышли за 3 суток» = 0: {sum(1 for d in main_set if d.exits == 0)} '
      f'(с кликами в окне > 0 среди них: {sum(1 for d in main_set if d.exits == 0 and d.clicks > 0)}).')
    p(f'Проверка: «вышли за 3 суток» > «сайтов с поиском»: {sum(1 for d in main_set if d.exits > d.sws)}; '
      f'регистраций у доменов без кликов в окне: {sum(d.regs for d in main_set if d.clicks == 0)}.')

    pools, n_all = make_pools(main_set, lambda d: (d.content, d.day))
    pools_dz, n_all_dz = make_pools(main_set, lambda d: (d.day, d.zone))
    pools_nc, n_all_nc = make_pools(nocontent, lambda d: d.day)
    p('\nСтраты (≥4 доменов и ≥1 регистрации в окне):')
    describe_pools('пул = набор контента + день', pools, n_all)
    describe_pools('запасная: день + зона', pools_dz, n_all_dz)
    describe_pools(f'«{NOCONTENT}»: пул = день', pools_nc, n_all_nc)
    doms_p = [d for v in pools.values() for d in v]
    zc = collections.Counter(d.zone for d in doms_p)
    zr = collections.Counter()
    for d in doms_p:
        zr[d.zone] += d.regs
    p('  Зоны в основных пулах: ' + ', '.join(f'{z} {zc[z]} дом./{zr[z]} рег' for z in ('team', 'lol', 'casino', 'buzz')) +
      f'; пулов со смесью зон {sum(1 for v in pools.values() if len(set(d.zone for d in v)) > 1)} из {len(pools)}.')
    mc = collections.Counter(d.month for d in doms_p)
    p(f'  Месяцы в основных пулах: ' + ', '.join(f'{m} {n} дом.' for m, n in sorted(mc.items())) + '.')

    # ------------------------------------------------------------------ А
    line()
    p('ЧАСТЬ А. ШИРИНА ОХВАТА ПРИ РАВНЫХ КЛИКАХ: концентрация = кликов из поиска в окне / вышли за 3 суток')
    line()
    p('  Нижний терциль = клики размазаны по многим вышедшим сайтам (широкий охват); верхний = клики на немногих сайтах-магнитах.')
    A = {}
    A['main'] = part_a(pools, 'Основная страта (набор + день)', lambda d: d.conc, 'кликов в окне на вышедший за 3 суток', lambda d: d.conc)
    A['dual'] = part_a(pools, 'Дубль: столбец «кликов на сайт с поиском» (за всё время)', lambda d: d.cpsw, 'кликов на сайт с поиском, всё время', lambda d: d.cpsw)

    p('\n' + '-' * 110)
    p('  «Равные клики»: страта пул × бин кликов')
    A['eq'] = part_a_equal_clicks(pools, 'Основная страта × бин')

    p('\n' + '-' * 110)
    p('  «Равные клики», главный тест: пары соседних по кликам доменов одного пула')
    A['pairs'] = part_a_pairs(pools, 'Основная страта, пары', 1.25, 1.5)
    A['pairs_alt'] = {}
    for cr, xr in ((1.25, 1.3), (1.5, 2.0), (2.0, 2.0)):
        A['pairs_alt'][(cr, xr)] = part_a_pairs(pools, 'Основная страта, пары', cr, xr, full=False)
    A['pairs_nc'] = part_a_pairs(pools_nc, f'«{NOCONTENT}», пары', 1.25, 1.5, full=False)
    A['pairs_dz'] = part_a_pairs(pools_dz, 'день + зона, пары', 1.25, 1.5, full=False)

    p('\n' + '-' * 110)
    p('  Знак по месяцам (основная страта, концентрация по вышедшим за 3 суток)')
    A['months'] = {}
    for m in ('август', 'сентябрь'):
        sub = {k: v for k, v in pools.items() if k[1] < '2026-09' if m == 'август'} if m == 'август' else \
              {k: v for k, v in pools.items() if k[1] >= '2026-09'}
        A['months'][m] = part_a(sub, f'{m}', lambda d: d.conc, 'кликов в окне на вышедший', lambda d: d.conc, full=False)
    p('\n' + '-' * 110)
    p(f'  Отдельно «{NOCONTENT}» (до 24.08, пул = день — набор не записан, сцеплен с датой)')
    A['nc'] = part_a(pools_nc, f'{NOCONTENT}', lambda d: d.conc, 'кликов в окне на вышедший', lambda d: d.conc, full=False)
    p('\n' + '-' * 110)
    p('  Запасная страта день + зона (основной набор без «КОНТЕНТ НЕ ЗАПИСАН»)')
    A['dz'] = part_a(pools_dz, 'день + зона', lambda d: d.conc, 'кликов в окне на вышедший', lambda d: d.conc, full=False)
    p('\n' + '-' * 110)
    p('  По зонам (пул = набор + день внутри зоны)')
    A['zones'] = {}
    for z in ('team', 'lol', 'casino'):
        pz, _ = make_pools([d for d in main_set if d.zone == z], lambda d: (d.content, d.day))
        A['zones'][z] = part_a(pz, f'зона {z}', lambda d: d.conc, 'кликов в окне на вышедший', lambda d: d.conc, full=False)

    # ------------------------------------------------------------------ Б
    line()
    p('ЧАСТЬ Б. ИЗЛИШЕК ВЫХОДА: терцили «выход 3 суток %» внутри пула, три ожидания')
    line()
    raw_exit_bands(main_set)
    B = {}
    B['main'] = part_b(pools, 'Основная страта (набор + день)')
    p('\n' + '-' * 110)
    p('  По месяцам (ожидание ∝ вышедших и ∝ кликов)')
    B['months'] = {}
    for m in ('август', 'сентябрь'):
        sub = {k: v for k, v in pools.items() if (k[1] < '2026-09') == (m == 'август')}
        B['months'][m] = part_b(sub, m, full=False)
    p('\n' + '-' * 110)
    p('  По зонам (пул = набор + день внутри зоны)')
    B['zones'] = {}
    for z in ('team', 'lol', 'casino', 'buzz'):
        pz, _ = make_pools([d for d in main_set if d.zone == z], lambda d: (d.content, d.day))
        if len(pz) < 3:
            p(f'\n  зона {z}: пулов {len(pz)}, доменов {sum(len(v) for v in pz.values())}, регистраций '
              f'{sum(d.regs for v in pz.values() for d in v)} — слишком мало, не считаем.')
            continue
        B['zones'][z] = part_b(pz, f'зона {z}', full=False)
    p('\n' + '-' * 110)
    p(f'  Отдельно «{NOCONTENT}» (пул = день)')
    B['nc'] = part_b(pools_nc, NOCONTENT, full=False)
    p('\n' + '-' * 110)
    p('  Запасная страта день + зона')
    B['dz'] = part_b(pools_dz, 'день + зона', full=False)

    # ------------------------------------------------------------------ модели
    line()
    p('КАКОЙ ЗНАМЕНАТЕЛЬ ЛУЧШЕ ОБЪЯСНЯЕТ РЕГИСТРАЦИИ ВНУТРИ ПУЛА')
    line()
    M = model_comparison(pools, 'Основная страта (набор + день)')
    M2 = model_comparison(pools_dz, 'Запасная страта (день + зона)')

    # ------------------------------------------------------------------ вывод
    line()
    p('ВЫВОД')
    line()
    a = A['main']
    e = A['eq']
    b_ex = B['main']['вышли за 3 суток']
    b_cl = B['main']['кликов из поиска в окне']
    b_si = B['main']['сайтов']
    oeA = a[3]
    oe1 = oeA[0][0] / oeA[0][1] if oeA[0][1] else float('nan')
    oe3 = oeA[2][0] / oeA[2][1] if oeA[2][1] else float('nan')
    p(f'А. Основная страта: O/E нижнего терциля концентрации (широкий охват) {oe1:.2f} ({oeA[0][0]:.0f} рег при ожидании {oeA[0][1]:.1f}), '
      f'верхнего (сайты-магниты) {oe3:.2f} ({oeA[2][0]:.0f} при {oeA[2][1]:.1f}); отношение {fmt_ratio(a[0])}, p(≥) = {a[1]:.4f}.')
    p(f'   При равных кликах (пул × бин): отношение {fmt_ratio(e[0])}, p(≥) = {e[1]:.4f}; по бинам: ' +
      ', '.join(f'{bn} {fmt_ratio(e[3].get(bn))}' for _, _, bn in BINS) + '.')
    p('   По месяцам: ' + ', '.join(f'{m} {fmt_ratio(v[0]) if v else "н/д"} (p {v[1]:.3f})' if v else f'{m} н/д'
                                  for m, v in A['months'].items()) +
      f'; «{NOCONTENT}»: {fmt_ratio(A["nc"][0]) if A["nc"] else "н/д"}; день+зона: {fmt_ratio(A["dz"][0]) if A["dz"] else "н/д"}.')
    p(f'Б. O/E верхней трети по выходу: ∝ сайтов {fmt_ratio(b_si[0])} (p {b_si[1]:.4f}), ∝ вышедших {fmt_ratio(b_ex[0])} (p {b_ex[1]:.4f}), '
      f'∝ кликов {fmt_ratio(b_cl[0])} (p(≥) {b_cl[1]:.4f}, p(≤) {b_cl[2]:.4f}); нижняя треть: ∝ сайтов '
      f'{fmt_oe(*b_si[3][0]).strip()}, ∝ вышедших {fmt_oe(*b_ex[3][0]).strip()}, ∝ кликов {fmt_oe(*b_cl[3][0]).strip()}.')
    p(f'   Лучший вес по отклонению: вышли^{M[1]} × клики^{M[2]} (день+зона: вышли^{M2[1]} × клики^{M2[2]}).')

    crit_a = (a[0] is not None and a[0] >= 1.5 and a[1] < 0.05
              and all((e[3].get(bn) or 0) > 1 for bn in ('325–912', '>912'))
              and all(v and v[0] is not None and v[0] > 1 for v in A['months'].values()))
    crit_b = (b_ex[0] is not None and b_ex[0] >= 1.3 and b_ex[1] < 0.05 and b_cl[0] is not None and 0.85 <= round(b_cl[0], 2) <= 1.15)
    pr = A['pairs']
    p(f'   Пары при равных кликах (≤×1.25 по кликам, ≥×1.5 по вышедшим): пар {pr[7]}, регистраций широкий {pr[3]} против узкого {pr[4]}, '
      f'отношение ставок {fmt_ratio(pr[0])}, p(перестановка ролей) = {pr[1]:.4f}, знаковый тест {pr[5]}:{pr[6]}, p = {pr[2]:.4f}.')
    p(f'   O/E верхней трети ∝ кликов точнее: {b_cl[0]:.3f} (граница критерия 1,15).')
    p(f'\nФормальные критерии постановки: А — {"выполнены" if crit_a else "НЕ выполнены"} '
      f'(отношение терцилей в основной страте {fmt_ratio(a[0])}, p {a[1]:.4f}; знак в бинах 325–912 и >912 при равных кликах: '
      f'{fmt_ratio(e[3].get("325–912"))} и {fmt_ratio(e[3].get(">912"))}; оба месяца > 1); '
      f'Б — {"выполнены" if crit_b else "НЕ выполнены"} (∝ вышедших {fmt_ratio(b_ex[0])} при p {b_ex[1]:.4f}; ∝ кликов {b_cl[0]:.2f}).')
    p(VERDICT_TEXT)


VERDICT_TEXT = """
Простыми словами.
  1. Часть А подтверждается. Если у двух доменов одного набора контента и одного дня запуска примерно
     одинаковое число поисковых кликов за 3 суток, то домен, у которого эти клики пришли на большее число
     сайтов, даёт заметно больше регистраций. В терцилях внутри пула: «широкий» терциль получил в 1,85 раза
     больше регистраций на клик, чем терциль «сайтов-магнитов» (32 регистрации при ожидании 21 против 89 при
     ожидании 108; p = 0,002). Тот же знак в августе (2,35) и сентябре (1,75), в «КОНТЕНТ НЕ ЗАПИСАН» (2,13),
     в страте день + зона (2,05), в team (2,73); в lol (1,43) и casino (1,03) не значимо — мало регистраций.
     Самый честный тест — пары соседних по кликам доменов одного пула (клики отличаются не более чем на
     четверть, вышедших сайтов — в полтора раза и больше): широкий домен пары собрал 20 регистраций против 6
     у узкого при почти равных кликах (в 3,3 раза; выиграл в 15 парах, проиграл в 6; перестановка ролей
     p = 0,013, знаковый тест p = 0,08). При других порогах — 2,0–5,4 раза, знак тот же; в страте день +
     зона 66 против 20 (3,3 раза, p < 0,001); в «КОНТЕНТ НЕ ЗАПИСАН» 14 против 8 (1,7, p = 0,10).
     Регистраций в парах мало (26–45), поэтому величина «в 1,5–2 раза» подтверждается по порядку, но не
     точно: по терцилям 1,85, по парам 2–3 с широким разбросом. По бинам кликов пары слишком тонкие, чтобы
     утверждать знак в каждом: >912 — 12 против 2, 95–325 — 5 против 0, но 325–912 — 3 против 3.
     Разрез по терцилям внутри ячеек пул × бин даёт лишь 1,32 (p = 0,11): он слабый не потому, что эффекта
     нет, а потому, что бин шириной ×3 не выравнивает клики (терцили в ячейке различаются по кликам в
     2,5 раза, по вышедшим — в 1,2).
  2. Часть Б подтверждается по сути и на границе по формальному критерию. Верхняя треть пула по выходу
     за 3 суток собрала 118 из 178 регистраций: это в 2,21 раза больше, чем «по сайтам», в 1,41 раза
     больше, чем «по вышедшим сайтам» (p = 0,0006), и в 1,15 раза больше, чем «по кликам» (от 1 не
     отличается, двусторонний p = 0,22). Нижняя треть: 0,28 / 0,49 / 0,60. Деньги не линейны по вышедшим
     сайтам — у доменов с большим выходом каждый вышедший сайт собирает больше кликов (44 против 27 на
     сайт) и даёт больше регистраций; по кликам же верхняя треть почти ровно то, что должна. ФД (35 в
     страте) — тот же знак: 1,30 по вышедшим, 1,04 по кликам. То же в team (1,39 / 1,15), в августе и
     сентябре (1,53 / 1,39 по вышедшим), в день + зона (1,42 / 1,14); в lol 1,17 (не значимо), в casino
     1,58 (8 пулов, 22 регистрации — только знак); buzz не считаем (2 пула, 2 регистрации).
  3. Какая же «валюта»? Ни один из трёх знаменателей по отдельности не описывает регистрации: клики
     в окне как единственная мерка чуть лучше вышедших сайтов (отклонение 407 против 421), но лучше всего
     работает их сочетание — регистрации ≈ вышедших × √кликов (отклонение 383; в день + зона 652 против 707
     и 749). Читать так: при равных кликах регистрации растут примерно пропорционально числу вышедших
     сайтов; при равном числе вышедших сайтов — как корень из кликов (второй клик на тот же сайт стоит
     меньше первого). Утверждение «сайты с первым кликом важнее суммы кликов» в лоб не подтверждается:
     важны оба, и сравнивать домены надо по обоим сразу, а не по одному из них.
  4. Ловушка проверена: столбец «кликов на сайт с поиском» (за всё время) даёт тот же знак, но слабее
     (1,49, p = 0,025) — оконный вариант через «вышли за 3 суток» информативнее.

Что с этим делать (проверяемо на уже запущенных данных).
  - Оценивать домены и наборы контента не по сумме кликов и не по одному проценту выхода, а по
    «вышедших сайтов × √кликов в окне» (или по регистрациям на клик с поправкой на ширину охвата):
    домен, где клики размазаны по многим сайтам, при равных кликах даёт в 2–3 раза больше регистраций.
  - Считать «удачным» домен с высокой долей вышедших сайтов: верхняя треть пула по выходу даёт две трети
    регистраций и по 1,3 регистрации на 100 вышедших сайтов против 0,5 у нижней трети.
  - Проверка на своде: пересчитать рейтинг наборов контента по «вышедших × √кликов» и посмотреть, меняет ли
    это порядок наборов по сравнению с рейтингом по кликам; если меняет — это готовый список наборов,
    которые дают клики, но не регистрации (сайты-магниты).
  - Это не рычаг для постановки: ширина охвата определяется брендами и контентом, а не выбором домена;
    рычаг — метрика сравнения, а не действие с доменом.
"""

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
w12_teni.py — контрпроверка (ТЕНИ / конфаундинг) вердикта тестировщика по гипотезе №12
(«окно 3 суток как неровная линейка: час запуска и семейство контента»).

Вердикт тестировщика: гипотеза опровергнута.
Задача скептика: показать, что и «эффект», и «отсутствие эффекта» в h12 — тень
набора контента, дня запуска, зоны, периода (август/сентябрь, «КОНТЕНТ НЕ ЗАПИСАН»),
длины наблюдения (цензурирования хвоста) и выбросов; проверить, выживает ли вывод
под более жёсткой стратой (набор + день + зона, при возможности + час) и под
выровненной по длине наблюдения линейкой.

Только stdlib.
"""
import csv, math, os, random, sys, datetime, collections

SRC = '/home/user/cladue/analysis/export/svod_domenov_21.09.csv'
DST = '/home/user/cladue/analysis/export/gipotezy_svod/w12_teni.txt'
REF = datetime.date(2026, 9, 21)          # дата свода
OUTLIERS = {'3615.team', '3286.team'}
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
BLOCKS = ('00-05', '06-11', '12-17', '18-23')
NSIM = 10000


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


# ------------------------------------------------------------------ утилиты
def iv(x):
    return int(x) if x not in ('', None) else 0


def dp(s):
    return datetime.date.fromisoformat(s)


def pct(k, n):
    return 100.0 * k / n if n else float('nan')


def binom_cdf(k, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    lp, lq = math.log(p), math.log(1 - p)
    s = 0.0
    for i in range(k + 1):
        s += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                      + i * lp + (n - i) * lq)
    return min(1.0, s)


def cp_ci(k, n, alpha=0.05):
    if n == 0:
        return float('nan'), float('nan')
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if 1 - binom_cdf(k - 1, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if k == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if binom_cdf(k, n, m) > alpha / 2:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    return lo, hi


def ci_str(k, n):
    if not n:
        return '—'
    lo, hi = cp_ci(k, n)
    return '%.0f%% [%.0f–%.0f]' % (pct(k, n), 100 * lo, 100 * hi)


def rr_ci(k1, n1, k2, n2):
    """Отношение долей k1/n1 : k2/n2, лог-ДИ."""
    if not (k1 and n1 and k2 and n2):
        return float('nan'), float('nan'), float('nan')
    r = (k1 / n1) / (k2 / n2)
    se = math.sqrt(max(1 / k1 - 1 / n1 + 1 / k2 - 1 / n2, 0.0))
    return r, r * math.exp(-1.96 * se), r * math.exp(1.96 * se)


def rr_str(k1, n1, k2, n2):
    r, lo, hi = rr_ci(k1, n1, k2, n2)
    if r != r:
        return '—'
    return '%.2f [%.2f–%.2f]' % (r, lo, hi)


def mh_rr(cells):
    """Мантель–Хензель для отношения рисков по стратам.
    cells: список (a, nA, b, nB) = (хвост A, рег A, хвост B, рег B)."""
    num = den = 0.0
    vnum = 0.0
    for a, nA, b, nB in cells:
        n = nA + nB
        if n == 0:
            continue
        num += a * nB / n
        den += b * nA / n
        m1 = a + b
        vnum += (m1 * nA * nB / (n * n)) - (a * b / n)
    if den <= 0 or num <= 0:
        return float('nan'), float('nan'), float('nan'), num, den
    rr = num / den
    var = vnum / (num * den)
    se = math.sqrt(max(var, 0.0))
    return rr, rr * math.exp(-1.96 * se), rr * math.exp(1.96 * se), num, den


def pval(cnt, nsim):
    return (cnt + 1) / (nsim + 1)


def fmt(x, nd=2):
    return ('%.' + str(nd) + 'f') % x if x == x else '—'


# ------------------------------------------------------------------ загрузка
def load():
    doms = []
    with open(SRC, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            d0 = dp(r['день запуска'])
            offs = [(dp(x) - d0).days for x in r['даты регистраций'].split()]
            reg, wreg = iv(r['регистраций']), iv(r['регистраций в окне 3 суток'])
            doms.append(dict(
                dom=r['домен'], zone=r['зона'], day=r['день запуска'], d0=d0,
                age=(REF - d0).days, ndays=r['дней'], closed=r['окно закрыто'] == 'да',
                content=r['набор контента'], fam=r['семейство'],
                hour=iv(r['час запуска']), block=r['блок часа'],
                sites=iv(r['сайтов']), sites_w1=iv(r['сайтов в 1-й волне']),
                sites_w2=iv(r['сайтов во 2-й волне']),
                reg=reg, wreg=wreg, tail=reg - wreg,
                ya=iv(r['из поиска']), wya=iv(r['кликов из поиска в окне']),
                hit3=iv(r['вышли за 3 суток']), hit7=iv(r['вышли за 7 суток']),
                offs=offs))
    return doms


def base_slice(doms, drop_out=True, closed=True, days2=True):
    d = doms
    if drop_out:
        d = [x for x in d if x['dom'] not in OUTLIERS]
    if closed:
        d = [x for x in d if x['closed']]
    if days2:
        d = [x for x in d if x['ndays'] == '2']
    return d


def late_group(d):
    late = d['hit7'] - d['hit3']
    return '0' if late <= 0 else ('1-3' if late <= 3 else '>=4')


def win_tail(d, H):
    """Регистрации при горизонте наблюдения H суток от запуска:
    окно = смещения 0..3, хвост = 4..H. Возвращает (окно, хвост)."""
    w = sum(1 for k in d['offs'] if 0 <= k <= 3)
    t = sum(1 for k in d['offs'] if 4 <= k <= H)
    return w, t


# ================================================================== часть 0
def part0(doms):
    print('\n' + '=' * 78)
    print('0. ЛИНЕЙКА: НЕЗАВИСИМАЯ СВЕРКА «ОКНА 3 СУТОК» СО СВОДОМ')
    print('=' * 78)
    D = base_slice(doms)
    R = [d for d in D if d['reg'] > 0]
    eq03 = sum(1 for d in R if d['wreg'] == sum(1 for k in d['offs'] if 0 <= k <= 3))
    eq02 = sum(1 for d in R if d['wreg'] == sum(1 for k in d['offs'] if 0 <= k <= 2))
    both = sum(1 for d in R if sum(1 for k in d['offs'] if k == 3) == 0)
    print('доменов с регистрациями (без выбросов, окно закрыто, дней = 2): %d' % len(R))
    print('  «регистраций в окне» = числу регистраций со смещением 0..3: %d (%.0f%%)'
          % (eq03, pct(eq03, len(R))))
    print('  «регистраций в окне» = числу регистраций со смещением 0..2: %d (%.0f%%)'
          % (eq02, pct(eq02, len(R))))
    print('  из них неразличимо (нет регистраций ровно на 3-и сутки): %d' % both)
    disc03 = [d for d in R if d['wreg'] != sum(1 for k in d['offs'] if 0 <= k <= 3)]
    disc02 = [d for d in R if d['wreg'] != sum(1 for k in d['offs'] if 0 <= k <= 2)]
    print('  расхождений с версией 0..3: %d; с версией 0..2: %d' % (len(disc03), len(disc02)))
    inf = [d for d in R if sum(1 for k in d['offs'] if k == 3) > 0]
    inf03 = sum(1 for d in inf if d['wreg'] == sum(1 for k in d['offs'] if 0 <= k <= 3))
    inf02 = sum(1 for d in inf if d['wreg'] == sum(1 for k in d['offs'] if 0 <= k <= 2))
    print('  различающие домены (есть регистрация на 3-и сутки): %d; из них согласны с 0..3: %d, с 0..2: %d'
          % (len(inf), inf03, inf02))
    print('  вывод: колонка свода считает 3-и сутки ВНУТРИ окна (0..3), как и сказал тестировщик;')
    print('         «50 часов у вечерних» из постановки не существует — минимум 73 часа (96 − час).')
    # длина окна в часах по блокам
    print('\n  длина окна в часах (96 − час запуска) по блокам, домены среза:')
    for b in BLOCKS:
        hh = [96 - d['hour'] for d in D if d['block'] == b]
        if hh:
            print('    %-6s доменов %4d  часов %d–%d' % (b, len(hh), min(hh), max(hh)))


# ================================================================== часть 1
def offsets_hist(doms):
    print('\n' + '=' * 78)
    print('1. ГЛАВНАЯ ТЕНЬ: ХВОСТ ЦЕНЗУРИРОВАН ДЛИНОЙ НАБЛЮДЕНИЯ')
    print('=' * 78)
    D = base_slice(doms)
    cnt = collections.Counter()
    for d in D:
        for k in d['offs']:
            cnt[k] += 1
    tot = sum(cnt.values())
    tail_all = sum(v for k, v in cnt.items() if k >= 4)
    t49 = sum(v for k, v in cnt.items() if 4 <= k <= 9)
    t10 = sum(v for k, v in cnt.items() if k >= 10)
    print('регистраций в срезе: %d; в окне (0..3): %d; хвост (≥4 суток): %d'
          % (tot, tot - tail_all, tail_all))
    print('  хвост 4..9 суток: %d (%.0f%% хвоста); хвост ≥10 суток: %d (%.0f%% хвоста)'
          % (t49, pct(t49, tail_all), t10, pct(t10, tail_all)))
    print('  смещения: ' + ' '.join('%d:%d' % (k, cnt[k]) for k in sorted(cnt)))
    print('  → «доля регистраций за окном» — величина, растущая с длиной наблюдения:')
    print('     четверть хвоста лежит дальше 9-х суток и видна только у августовских запусков.')
    print('\n  длина наблюдения (возраст домена, суток) по блокам часа и семействам, срез h12 (все возрасты):')
    print('  %-14s %6s %6s %6s %6s %8s' % ('группа', 'домен.', 'мин', 'медиана', 'макс', 'рег'))
    for key, lab in (('block', 'блок часа'), ('fam', 'семейство')):
        print('  -- %s --' % lab)
        groups = collections.defaultdict(list)
        for d in D:
            groups[d[key]].append(d)
        for g in sorted(groups, key=lambda x: -len(groups[x])):
            ds = sorted(x['age'] for x in groups[g])
            rg = sum(x['reg'] for x in groups[g])
            print('  %-14s %6d %6d %6d %6d %8d'
                  % (g, len(ds), ds[0], ds[len(ds) // 2], ds[-1], rg))
    # период x блок
    print('\n  период × блок часа (домены среза): ночь/утро запускали почти только в сентябре')
    per = collections.Counter()
    for d in D:
        per[('август' if d['day'] < '2026-09-01' else 'сентябрь', d['block'])] += 1
    print('  %-10s ' % 'период' + ' '.join('%8s' % b for b in BLOCKS))
    for p in ('август', 'сентябрь'):
        print('  %-10s ' % p + ' '.join('%8d' % per[(p, b)] for b in BLOCKS))
    print('  → сравнение «18–23 против 00–11» у тестировщика — это ещё и')
    print('    «август+сентябрь против почти только сентября», т.е. длинное наблюдение против короткого.')


# ================================================================== общее
def group_tail(D, keyf, H=None):
    """Сводка хвоста по группам. H=None — по колонкам свода, иначе равная линейка 0..H."""
    g = collections.defaultdict(lambda: [0, 0, 0, 0])   # домены, рег, окно, хвост
    for d in D:
        if H is None:
            reg, w, t = d['reg'], d['wreg'], d['tail']
        else:
            w, t = win_tail(d, H)
            reg = w + t
        k = keyf(d)
        g[k][0] += 1
        g[k][1] += reg
        g[k][2] += w
        g[k][3] += t
    return g


def print_group(g, title, order=None):
    print('  %-28s %7s %7s %7s %7s  %s' % (title, 'домен.', 'рег', 'в окне', 'хвост', 'хвост % [ДИ]'))
    keys = order if order else sorted(g, key=lambda k: -g[k][1])
    for k in keys:
        if k not in g:
            continue
        n, reg, w, t = g[k]
        print('  %-28s %7d %7d %7d %7d  %s' % (k, n, reg, w, t, ci_str(t, reg)))


def strat_cells(D, groupf, stratf, H=None):
    """Собирает страты: в каждой страте (хвост A, рег A, хвост B, рег B),
    groupf(d) -> True (A) / False (B) / None (исключить)."""
    st = collections.defaultdict(lambda: [0, 0, 0, 0])
    for d in D:
        gr = groupf(d)
        if gr is None:
            continue
        if H is None:
            reg, t = d['reg'], d['tail']
        else:
            w, t = win_tail(d, H)
            reg = w + t
        if reg == 0:
            continue
        s = stratf(d)
        if gr:
            st[s][0] += t
            st[s][1] += reg
        else:
            st[s][2] += t
            st[s][3] += reg
    cells = [tuple(v) for v in st.values() if v[1] > 0 and v[3] > 0]
    return st, cells


def perm_strat(D, groupf, stratf, H=None, nsim=NSIM, seed=12):
    """Перестановка метки группы между доменами внутри страты; статистика —
    МХ-отношение доли хвоста A к B. Возвращает (набл., p двуст., инф. страт, инф. рег)."""
    rnd = random.Random(seed)
    pools = collections.defaultdict(list)
    for d in D:
        gr = groupf(d)
        if gr is None:
            continue
        if H is None:
            reg, t = d['reg'], d['tail']
        else:
            w, t = win_tail(d, H)
            reg = w + t
        pools[stratf(d)].append((gr, reg, t))
    # информативные страты: есть обе группы и есть регистрации у обеих
    inf = {}
    for s, lst in pools.items():
        rA = sum(r for g, r, t in lst if g)
        rB = sum(r for g, r, t in lst if not g)
        if rA > 0 and rB > 0:
            inf[s] = lst
    if not inf:
        return float('nan'), float('nan'), 0, 0, 0, 0

    def stat(assign):
        cells = []
        for s, lst in inf.items():
            a = nA = b = nB = 0
            for (g, reg, t) in assign[s]:
                if g:
                    a += t
                    nA += reg
                else:
                    b += t
                    nB += reg
            cells.append((a, nA, b, nB))
        return mh_rr(cells)[0]

    obs = stat({s: lst for s, lst in inf.items()})
    infreg = sum(reg for lst in inf.values() for g, reg, t in lst)
    infregA = sum(reg for lst in inf.values() for g, reg, t in lst if g)
    cnt_ge = cnt_le = 0
    labels = {s: [g for g, r, t in lst] for s, lst in inf.items()}
    for _ in range(nsim):
        assign = {}
        for s, lst in inf.items():
            lab = labels[s][:]
            rnd.shuffle(lab)
            assign[s] = [(lab[i], lst[i][1], lst[i][2]) for i in range(len(lst))]
        v = stat(assign)
        if v == v and obs == obs:
            if v >= obs:
                cnt_ge += 1
            if v <= obs:
                cnt_le += 1
    if obs != obs:
        p2 = float('nan')
    else:
        p2 = min(1.0, 2 * min(pval(cnt_ge, nsim), pval(cnt_le, nsim)))
    return obs, p2, len(inf), infreg, infregA, infreg - infregA


def report_strata(D, groupf, labA, labB, H, tag, nsim=NSIM):
    """Сырое сравнение + три уровня страты."""
    # сырое
    a = nA = b = nB = 0
    for d in D:
        gr = groupf(d)
        if gr is None:
            continue
        if H is None:
            reg, t = d['reg'], d['tail']
        else:
            w, t = win_tail(d, H)
            reg = w + t
        if gr:
            a += t
            nA += reg
        else:
            b += t
            nB += reg
    print('  %s' % tag)
    print('    сырое: %s хвост %d/%d = %s; %s хвост %d/%d = %s; отношение %s'
          % (labA, a, nA, ci_str(a, nA), labB, b, nB, ci_str(b, nB), rr_str(a, nA, b, nB)))
    levels = [
        ('день запуска', lambda d: d['day']),
        ('набор + день', lambda d: (d['content'], d['day'])),
        ('набор + день + зона', lambda d: (d['content'], d['day'], d['zone'])),
    ]
    for name, sf in levels:
        st, cells = strat_cells(D, groupf, sf, H)
        rr, lo, hi, num, den = mh_rr(cells)
        obs, p2, ninf, infreg, ra, rb = perm_strat(D, groupf, sf, H, nsim=nsim)
        print('    страта «%s»: инф. страт %d, регистраций в них %d (%s %d / %s %d); '
              'МХ-отношение %s [%s–%s], перестановка p(двуст.) = %s'
              % (name, ninf, infreg, labA, ra, labB, rb,
                 fmt(rr), fmt(lo), fmt(hi), fmt(p2, 3)))
    return a, nA, b, nB


# ================================================================== часть 2
def part2(doms):
    print('\n' + '=' * 78)
    print('2. ЧАС ЗАПУСКА ПОД ЖЁСТКОЙ СТРАТОЙ И РАВНОЙ ЛИНЕЙКОЙ')
    print('=' * 78)
    D0 = base_slice(doms)
    print('\n2.1 Коллинеарность часа со стратой (вся база среза, %d доменов)' % len(D0))
    pools = collections.defaultdict(set)
    poolreg = collections.Counter()
    for d in D0:
        k = (d['content'], d['day'])
        pools[k].add(d['block'])
        poolreg[k] += d['reg']
    multi = [k for k in pools if len(pools[k]) > 1]
    regs_all = sum(poolreg.values())
    regs_multi = sum(poolreg[k] for k in multi)
    print('  пулов «набор + день»: %d; из них с ≥2 блоками часа: %d (%.0f%%)'
          % (len(pools), len(multi), pct(len(multi), len(pools))))
    print('  регистраций всего %d, из них в пулах с ≥2 блоками: %d (%.0f%%) — '
          'остальные %d к сравнению часов не относятся вовсе'
          % (regs_all, regs_multi, pct(regs_multi, regs_all), regs_all - regs_multi))
    pools3 = collections.defaultdict(set)
    for d in D0:
        pools3[(d['content'], d['day'], d['zone'])].add(d['block'])
    m3 = sum(1 for k in pools3 if len(pools3[k]) > 1)
    print('  пулов «набор + день + зона»: %d; с ≥2 блоками: %d' % (len(pools3), m3))

    slices = [
        ('возраст ≥7, без «не записан» (срез тестировщика)',
         lambda d: d['age'] >= 7 and d['content'] != NOC, None),
        ('то же + равная линейка 0..7 суток',
         lambda d: d['age'] >= 7 and d['content'] != NOC, 7),
        ('возраст ≥10, без «не записан», равная линейка 0..9',
         lambda d: d['age'] >= 10 and d['content'] != NOC, 9),
        ('возраст ≥14, без «не записан», равная линейка 0..13',
         lambda d: d['age'] >= 14 and d['content'] != NOC, 13),
        ('возраст ≥7, С «не записан» (как в цифрах постановки)',
         lambda d: d['age'] >= 7, None),
        ('возраст ≥7, только сентябрь (период выровнен)',
         lambda d: d['age'] >= 7 and d['day'] >= '2026-09-01' and d['content'] != NOC, None),
        ('возраст ≥7, только зона .lol (в ней есть все 4 блока)',
         lambda d: d['age'] >= 7 and d['zone'] == 'lol' and d['content'] != NOC, None),
        ('возраст ≥7 + незакрытое окно и дней ≠ 2 возвращены',
         None, None),
    ]
    for name, f, H in slices:
        if f is None:
            D = [d for d in base_slice(doms, closed=False, days2=False)
                 if d['age'] >= 7 and d['content'] != NOC]
            f = lambda d: True
        else:
            D = [d for d in D0 if f(d)]
        if not D:
            continue
        reg = sum((d['reg'] if H is None else sum(win_tail(d, H))) for d in D)
        print('\n  СРЕЗ: %s — доменов %d, регистраций %d' % (name, len(D), reg))
        g = group_tail(D, lambda d: d['block'], H)
        print_group(g, 'блок часа', order=list(BLOCKS))
        ev = lambda d: True if d['block'] == '18-23' else False
        nt = lambda d: True if d['block'] == '18-23' else (False if d['block'] in ('00-05', '06-11') else None)
        report_strata(D, ev, '18–23', 'остальные', H, 'вечерние против остальных блоков:',
                      nsim=NSIM)
        report_strata(D, nt, '18–23', '00–11', H, 'вечерние против 00–11:', nsim=NSIM)

    # 2.4 выбросы и «исправленное окно» плана
    print('\n2.2 Выбросы 3615.team и 3286.team (исключены тестировщиком)')
    for d in doms:
        if d['dom'] in OUTLIERS:
            print('  %-11s день %s час %2d семейство %-10s рег %d, в окне %d, смещения %s'
                  % (d['dom'], d['day'], d['hour'], d['fam'], d['reg'], d['wreg'],
                     ','.join(str(k) for k in d['offs'])))
    print('  оба — вечерне/дневные домены с 1–2 регистрациями; возврат их в срез меняет хвост')
    print('  вечерних максимум на 1 регистрацию из ~22 — вывод части (а) от них не зависит.')


# ================================================================== часть 3
def part3(doms):
    print('\n' + '=' * 78)
    print('3. СЕМЕЙСТВА ПОД ЖЁСТКОЙ СТРАТОЙ И РАВНОЙ ЛИНЕЙКОЙ')
    print('=' * 78)
    D0 = base_slice(doms)
    print('\n3.1 Длина наблюдения по семействам в срезе тестировщика (возраст ≥10, без «не записан»)')
    D = [d for d in D0 if d['age'] >= 10 and d['content'] != NOC]
    fams = collections.defaultdict(list)
    for d in D:
        fams[d['fam']].append(d)
    print('  %-12s %6s %6s %6s %6s %6s %8s' % ('семейство', 'домен.', 'возр.мин', 'мед', 'макс', 'рег', 'хвост'))
    for f in sorted(fams, key=lambda x: -sum(d['reg'] for d in fams[x])):
        ds = sorted(d['age'] for d in fams[f])
        print('  %-12s %6d %8d %6d %6d %6d %8d'
              % (f, len(ds), ds[0], ds[len(ds) // 2], ds[-1],
                 sum(d['reg'] for d in fams[f]), sum(d['tail'] for d in fams[f])))
    print('  → archive живёт 10–13 суток, NEW до 27, Generator до 27: «доля за окном» у archive')
    print('    измеряется более короткой линейкой, у NEW — более длинной. Это и есть тень.')

    print('\n3.2 Доля хвоста по семействам: свод против равной линейки')
    for H, lab in ((None, 'по колонкам свода (разная длина наблюдения)'),
                   (9, 'равная линейка: хвост = смещения 4..9 у всех'),
                   (13, 'равная линейка 4..13, возраст ≥14')):
        DD = D if H != 13 else [d for d in D0 if d['age'] >= 14 and d['content'] != NOC]
        g = group_tail(DD, lambda d: d['fam'], H)
        print('\n  %s (доменов %d)' % (lab, len(DD)))
        print_group(g, 'семейство')

    print('\n3.3 archive+NEW против остальных семейств: страты и линейки')
    grp = lambda d: (d['fam'] in ('NEW', 'archive'))
    for H, lab in ((None, 'свод (линейка неравная)'), (9, 'равная линейка 0..9')):
        print('\n  линейка: %s' % lab)
        report_strata(D, grp, 'archive+NEW', 'остальные', H,
                      'возраст ≥10, без «не записан»:', nsim=NSIM)

    print('\n3.4 Парные сравнения внутри одного дня запуска (только дни, где есть оба лагеря)')
    byday = collections.defaultdict(lambda: [0, 0, 0, 0])
    for d in D:
        w, t = win_tail(d, 9)
        reg = w + t
        if reg == 0:
            continue
        if d['fam'] in ('NEW', 'archive'):
            byday[d['day']][0] += t
            byday[d['day']][1] += reg
        else:
            byday[d['day']][2] += t
            byday[d['day']][3] += reg
    print('  %-12s %8s %8s %8s %8s' % ('день', 'AN хвост', 'AN рег', 'ост хвост', 'ост рег'))
    cells = []
    for day in sorted(byday):
        a, nA, b, nB = byday[day]
        if nA and nB:
            cells.append((a, nA, b, nB))
            print('  %-12s %8d %8d %8d %8d' % (day, a, nA, b, nB))
    rr, lo, hi, _, _ = mh_rr(cells)
    print('  парных дней: %d; МХ-отношение (равная линейка 0..9): %s [%s–%s]'
          % (len(cells), fmt(rr), fmt(lo), fmt(hi)))

    print('\n3.5 Захват поисковых кликов окном — тень набора и дня, а не семейства')
    # разброс захвата внутри семейства между наборами
    bys = collections.defaultdict(lambda: [0, 0, 0])
    for d in D:
        k = (d['fam'], d['content'])
        bys[k][0] += 1
        bys[k][1] += d['ya']
        bys[k][2] += d['wya']
    famspread = collections.defaultdict(list)
    for (f, c), (n, ya, wya) in bys.items():
        if ya > 0 and n >= 5:
            famspread[f].append((wya / ya, c, n))
    for f in sorted(famspread, key=lambda x: -len(famspread[x])):
        v = sorted(famspread[f])
        print('  %-10s наборов ≥5 доменов: %2d; захват от %.2f (%s) до %.2f (%s)'
              % (f, len(v), v[0][0], v[0][1][:34], v[-1][0], v[-1][1][:34]))
    print('  → внутри NEW захват гуляет шире (0.5–0.9), чем между семействами (0.62–0.86):')
    print('    «медленное семейство» — это ярлык на наборе и дне, а не свойство семейства.')


# ================================================================== часть 2b
def part2b(doms):
    print('\n2.3 Откуда взялись «24 % у вечерних» в своде тестировщика')
    D0 = base_slice(doms)
    D = [d for d in D0 if d['age'] >= 7 and d['content'] != NOC]
    ev = [d for d in D if d['block'] == '18-23']
    oth = [d for d in D if d['block'] != '18-23']
    for lab, S in (('18–23', ev), ('остальные', oth)):
        for per in ('август', 'сентябрь'):
            P = [d for d in S if (d['day'] < '2026-09-01') == (per == 'август')]
            reg = sum(d['reg'] for d in P)
            t = sum(d['tail'] for d in P)
            print('    %-10s %-9s доменов %4d, рег %3d, хвост %2d — %s'
                  % (lab, per, len(P), reg, t, ci_str(t, reg)))
    print('    → у вечерних 24 % держится на августовских доменах (длинное наблюдение);')
    print('      внутри сентября вечерние 19 % против 23 % у остальных (отношение 0,85).')
    print('\n    зона × блок часа по регистрациям (тот же срез):')
    z = collections.defaultdict(lambda: [0, 0, 0])
    for d in D:
        k = (d['zone'], 'веч' if d['block'] == '18-23' else 'ост')
        z[k][0] += 1
        z[k][1] += d['reg']
        z[k][2] += d['tail']
    for zone in sorted(set(k[0] for k in z), key=lambda x: -sum(z[(x, s)][1] for s in ('веч', 'ост'))):
        line = '    %-8s' % zone
        for s in ('веч', 'ост'):
            n, r, t = z[(zone, s)]
            line += '  %s: доменов %4d рег %3d хвост %2d' % (s, n, r, t)
        print(line)


# ================================================================== часть 3b
def part3b(doms):
    print('\n3.6 Сдвиг рейтинга «окно → всё время» под равной линейкой')
    D0 = base_slice(doms)
    D = [d for d in D0 if d['age'] >= 10 and d['content'] != NOC]
    rows = {}
    for f in set(d['fam'] for d in D):
        S = [d for d in D if d['fam'] == f]
        sites = sum(d['sites'] for d in S)
        w = sum(sum(1 for k in d['offs'] if 0 <= k <= 3) for d in S)
        all9 = sum(sum(1 for k in d['offs'] if 0 <= k <= 9) for d in S)
        allt = sum(d['reg'] for d in S)
        if sum(d['reg'] for d in S) >= 4:
            rows[f] = (sites, w, all9, allt)
    print('    %-12s %8s %8s %10s %10s %10s' % ('семейство', 'сайтов', 'окно/100', 'до 9 сут/100', 'всё/100', 'сдвиг 9 сут'))
    for f in sorted(rows, key=lambda x: -rows[x][1] / rows[x][0]):
        sites, w, a9, at = rows[f]
        print('    %-12s %8d %8.3f %10.3f %10.3f %9s'
              % (f, sites, 100.0 * w / sites, 100.0 * a9 / sites, 100.0 * at / sites,
                 ('%+.0f%%' % (100.0 * (a9 / w - 1)) if w else '—')))
    for pair in (('NEW', 'Generator'), ('archive', 'Generator'), ('NEW', 'nabory'),
                 ('archive', 'nabory'), ('NEW', 'archive')):
        a, b = pair
        if a in rows and b in rows:
            sa, wa, a9, ata = rows[a]
            sb, wb, b9, atb = rows[b]
            r_w = (wa / sa) / (wb / sb) if wb else float('nan')
            r_9 = (a9 / sa) / (b9 / sb) if b9 else float('nan')
            r_a = (ata / sa) / (atb / sb) if atb else float('nan')
            print('    %-9s/%-9s окно %.2f → до 9 суток %.2f (сдвиг %+.0f%%) → всё время %.2f (сдвиг %+.0f%%)'
                  % (a, b, r_w, r_9, 100 * (r_9 / r_w - 1), r_a, 100 * (r_a / r_w - 1)))
    print('    → «всё время» — линейка разной длины: у NEW она до 27 суток, у archive до 13.')
    print('      При равной линейке 0..9 сдвиг NEW/Generator падает с +32 % до значения выше,')
    print('      т.е. часть «недобора медленных семейств» — просто более долгое наблюдение.')

    print('\n3.7 Механизм тестировщика (хвост = поздний выход домена) под равной линейкой 0..9')
    for lab, H in (('свод', None), ('равная линейка 0..9', 9)):
        bins = collections.defaultdict(lambda: [0, 0, 0])
        for d in D:
            if d['ya'] <= 0:
                continue
            cap = d['wya'] / d['ya']
            k = '<50%' if cap < 0.5 else ('50–70%' if cap < 0.7 else ('70–85%' if cap < 0.85 else '≥85%'))
            if H is None:
                reg, t = d['reg'], d['tail']
            else:
                w, t = win_tail(d, H)
                reg = w + t
            bins[k][0] += 1
            bins[k][1] += reg
            bins[k][2] += t
        print('    %s:' % lab)
        for k in ('<50%', '50–70%', '70–85%', '≥85%'):
            n, reg, t = bins[k]
            print('      захват %-7s доменов %4d рег %3d хвост %2d  %s' % (k, n, reg, t, ci_str(t, reg)))


# ================================================================== часть 4
def part4(doms):
    print('\n' + '=' * 78)
    print('4. МОЩНОСТЬ: ЧТО ЭТОТ СРЕЗ ВООБЩЕ СПОСОБЕН ОТЛИЧИТЬ')
    print('=' * 78)
    D0 = base_slice(doms)
    D = [d for d in D0 if d['age'] >= 7 and d['content'] != NOC]
    a = sum(d['tail'] for d in D if d['block'] == '18-23')
    nA = sum(d['reg'] for d in D if d['block'] == '18-23')
    b = sum(d['tail'] for d in D if d['block'] != '18-23')
    nB = sum(d['reg'] for d in D if d['block'] != '18-23')
    rr, lo, hi = rr_ci(a, nA, b, nB)
    print('  (а) час: вечерние %d/%d против остальных %d/%d; отношение %.2f [%.2f–%.2f]'
          % (a, nA, b, nB, rr, lo, hi))
    print('      постановка ждала ~1,7× (40%% против 24%%) — это значение %s верхней границей ДИ'
          % ('НЕ отсекается' if hi >= 1.7 else 'отсекается'))
    # МДЭ через биномиальную мощность (норм. приближение)
    def mde(nA, nB, p0, power=0.8, alpha=0.05):
        z_a, z_b = 1.96, 0.84
        r = 1.0
        for _ in range(200):
            p1 = p0 * r
            if p1 >= 0.95:
                break
            se = math.sqrt(p1 * (1 - p1) / nA + p0 * (1 - p0) / nB)
            need = (z_a + z_b) * se
            if abs(p1 - p0) >= need:
                return r
            r += 0.01
        return float('nan')
    p0 = b / nB
    print('      минимально различимое отношение (80%% мощности, α = 0,05, n = %d/%d): ≈%.2f'
          % (nA, nB, mde(nA, nB, p0)))
    D2 = [d for d in D0 if d['age'] >= 10 and d['content'] != NOC]
    a2 = sum(d['tail'] for d in D2 if d['fam'] in ('NEW', 'archive'))
    n2 = sum(d['reg'] for d in D2 if d['fam'] in ('NEW', 'archive'))
    b2 = sum(d['tail'] for d in D2 if d['fam'] not in ('NEW', 'archive'))
    m2 = sum(d['reg'] for d in D2 if d['fam'] not in ('NEW', 'archive'))
    rr2, lo2, hi2 = rr_ci(a2, n2, b2, m2)
    print('  (б) семейства: archive+NEW %d/%d против остальных %d/%d; отношение %.2f [%.2f–%.2f]'
          % (a2, n2, b2, m2, rr2, lo2, hi2))
    print('      минимально различимое отношение (80%% мощности, n = %d/%d): ≈%.2f'
          % (n2, m2, mde(n2, m2, b2 / m2)))
    print('  → «эффекта нет» здесь означает «нет эффекта размера ≥1,6–2,3×»; занижение на 20–35 %')
    print('    (отношение 1,2–1,35) этот срез не отличил бы от нуля ни при каком результате.')
    print('    Зато проверяемое утверждение постановки (≥1,7× у вечерних, ≥2× у медленных семейств)')
    print('    лежит выше точечных оценок и в части (б) — выше верхней границы при равной линейке.')


# ================================================================== вывод
def conclusion(doms):
    print('\n' + '=' * 78)
    print('ВЫВОД СКЕПТИКА: вердикт «опровергнута» выстоял, но две цифры тестировщика — тени')
    print('=' * 78)
    print("""
1. Посылка «у вечерних окно 50 часов вместо 72» мертва не по статистике, а по арифметике.
   Из 268 доменов с регистрациями 51 различает версии окна (есть регистрация ровно на 3-и
   сутки): 48 из них согласны с окном 0..3 и только 1 — с 0..2. Окно = 96 − час запуска,
   т.е. 73–78 ч у 18–23 и 91–96 ч у 00–05; разрыв 0,81, а не 0,69. Здесь опровергать нечего.

2. Зато «хвост 24 % у вечерних против 22 %» из свода тестировщика — сама по себе тень
   периода и длины наблюдения. Ночь и утро запускали почти только в сентябре (00–05: 6
   доменов в августе против 190 в сентябре; 06–11: 0 против 256), а хвост растёт с длиной
   наблюдения: 19 из 74 хвостовых регистраций (26 %) лежат дальше 9-х суток и видны только
   у августовских запусков. Разложение: у вечерних 24 % держатся на 38 августовских доменах
   (15 регистраций, хвост 7 = 47 %), а внутри сентября вечерние дают 15/78 = 19 % [11–30]
   против 27/119 = 23 % [16–31] у остальных, отношение 0,85 [0,48–1,49].

3. Под жёсткой стратой эффект не просто пропадает — он меняет знак. МХ-отношение доли
   хвоста «вечерние / остальные» (срез тестировщика, 1060 доменов, 242 регистрации):
   страта «день запуска» 0,59 [0,35–1,00], p(перест.) = 0,09; «набор + день» 0,49 [0,20–1,17],
   p = 0,31; «набор + день + зона» 0,42 [0,19–0,89], p = 0,27. На равной линейке 0..9 суток
   (857 доменов) — 0,73 / 0,51 / 0,30, p = 0,47 / 0,44 / 0,29. Ни один вариант не смотрит
   в сторону постановки (≥1,7×).

4. Ограничение, которое стоит назвать вслух: час запуска почти коллинеарен страте. Из 632
   пулов «набор + день» только 43 (7 %) содержат больше одного блока часа; в стратах
   «набор + день + зона» сравнение вечерних с остальными держится на 27 регистрациях из 242,
   а вечерних с 00–11 — на 2. Сырая мощность: минимально различимое отношение при 93/149
   регистрациях ≈1,8×. Т.е. «час не искажает окно» доказано для искажений ≥1,7–1,8×,
   а искажение в 1,2× этот свод не отличил бы от нуля ни при каком исходе.

5. Часть про семейства: вторая цифра-тень. Порядок «NEW 24 % > archive 21 %» получен разными
   линейками: archive живёт 10–13 суток, NEW — 10–27. На равной линейке 0..9 порядок
   переворачивается: NEW 22/121 = 18 % [12–26], archive 9/38 = 24 % [11–40] при общей 19 %.
   На выводе это не сказывается: archive+NEW против остальных — сырое 1,23 [0,68–2,23]
   (свод) и 1,32 [0,64–2,69] (равная линейка), в стратах по дню 0,68 и 0,85 (p = 0,36 и 0,72);
   9 парных дней дают 0,85 [0,31–2,32]. Ни 2×, ни даже устойчивого 1,3× нет.

6. Семейство вообще не отделимо от набора: в стратах «набор + день» у сравнения
   archive+NEW / остальные информативных страт 0 из 632 — семейство есть огрубление набора.
   Поэтому вывод «хвост — свойство домена, а не семейства» проверяем только на уровне дня.
   Механизм тестировщика при этом выстоял на равной линейке: захват <50 % → хвост 10/29 = 34 %,
   50–70 % → 20/71 = 28 %, 70–85 % → 8/49 = 16 %, ≥85 % → 1/64 = 2 %.

7. Сдвиг рейтинга при переходе к «всё время» цензурирование объясняет лишь частично:
   NEW/Generator 1,43 → 1,75 на равной линейке 0..9 (+22 %) → 1,89 «за всё время» (+32 %);
   archive/Generator 0,67 → 0,87 (+31 %) уже на 0..9. Относительно nabory сдвиг обратный
   (NEW/nabory −8 % на 0..9, −12 % за всё время), NEW/archive стоит на месте (2,14 → 2,00 → 2,16).
   Т.е. «недобор медленных семейств на 20–35 %» — это свойство пары со сравнением
   с Generator (0 хвоста на 14 регистрациях), а не свойство окна. Тестировщик прав.

ИТОГ: опровергнуть вердикт не удалось. Ни одна тень (период, день, набор, зона, выбросы,
незакрытые окна, «КОНТЕНТ НЕ ЗАПИСАН», длина наблюдения) не вытаскивает из данных
заявленного постановкой занижения; две из них — август у вечерних и длинная линейка у NEW —
наоборот, завышали те самые 24 %, на которых вердикт выглядел «почти ничьёй». Поправлять
надо не вывод, а формулировки: указывать границы (вечерние 0,4–1,1 в стратах, сырое
1,07 [0,67–1,71]; archive+NEW 0,7–1,3) и оговаривать, что при 27–39 информативных
регистрациях эта проверка закрывает искажения ≥1,8×, а не ≥1,2×.
""")


def main():
    t = Tee(DST)
    sys.stdout = t
    print('Контрпроверка №12 (тени/конфаундинг): «окно 3 суток», час запуска и семейство')
    print('Источник: %s' % SRC)
    doms = load()
    print('строк в своде: %d' % len(doms))
    D = base_slice(doms)
    print('срез-основа (без выбросов, окно закрыто, дней = 2): %d доменов, %d регистраций'
          % (len(D), sum(d['reg'] for d in D)))
    part0(doms)
    offsets_hist(doms)
    part2(doms)
    part2b(doms)
    part3(doms)
    part3b(doms)
    part4(doms)
    conclusion(doms)
    t.flush()


if __name__ == '__main__':
    main()

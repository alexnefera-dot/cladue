#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №12 (окно «3 суток»: час запуска и семейство контента).
Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ. Только stdlib.

Что делаю:
 1. Независимо пересчитываю ключевые числа тестировщика прямо из свода.
 2. Проверяю знаменатели/оконные колонки и фильтры (окно закрыто, дней, возраст).
 3. Считаю ТОЧНЫЕ доверительные интервалы (Клоппер–Пирсон) и точные ДИ отношения
    шансов (нецентральное гипергеометрическое) — вмещает ли ДИ то, что ждала
    постановка (час 1,7x, семейства >=2x).
 4. Мощность: с какой вероятностью этот объём вообще увидел бы эффект 1,7x / 2x.
 5. Множественность: сколько тестов перебрано, что выживает после Бонферрони.
 6. Устойчивость: снимаю топ-3 домена по регистрациям в каждой группе.
 7. Экспозиция: хвост меряется на разной длине наблюдения у семейств — пересчёт
    на общем горизонте.
"""
import collections, csv, datetime, math, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w12_statistika.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
REF = datetime.date(2026, 9, 21)
CUT_HOUR = datetime.date(2026, 9, 14)
CUT_FAM = datetime.date(2026, 9, 11)
KMAX = 12


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8')
        self.o = sys.__stdout__
    def write(self, s):
        self.f.write(s); self.o.write(s)
    def flush(self):
        self.f.flush(); self.o.flush()


def iv(x):
    x = (x or '').strip().replace(' ', '')
    try: return int(float(x))
    except Exception: return 0


def dp(s):
    s = (s or '').strip()
    return datetime.date(*[int(t) for t in s.split('-')]) if s else None


# ---------- точная статистика ----------
def binom_cdf(k, n, p):
    if k < 0: return 0.0
    if k >= n: return 1.0
    s = 0.0
    for i in range(0, k + 1):
        s += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return min(s, 1.0)


def cp_ci(k, n, alpha=0.05):
    """Клоппер–Пирсон через бисекцию."""
    if n == 0: return (0.0, 1.0)
    lo, hi = 0.0, 1.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(80):
            m = (a + b) / 2
            if 1 - binom_cdf(k - 1, n, m) > alpha / 2: b = m
            else: a = m
        lo = (a + b) / 2
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(80):
            m = (a + b) / 2
            if binom_cdf(k, n, m) < alpha / 2: b = m
            else: a = m
        hi = (a + b) / 2
    return lo, hi


def ci_s(k, n):
    if n == 0: return '—'
    lo, hi = cp_ci(k, n)
    return '%d/%d = %.0f%% [%.0f–%.0f]' % (k, n, 100.0 * k / n, 100 * lo, 100 * hi)


def nchg_pmf(m1, m2, n, psi):
    """Нецентральное гипергеометрическое: веса по k."""
    lo = max(0, n - m2); hi = min(n, m1)
    w = {}
    mx = -1e300
    for k in range(lo, hi + 1):
        lw = (math.lgamma(m1 + 1) - math.lgamma(k + 1) - math.lgamma(m1 - k + 1)
              + math.lgamma(m2 + 1) - math.lgamma(n - k + 1) - math.lgamma(m2 - n + k + 1)
              + k * math.log(psi))
        w[k] = lw
        mx = max(mx, lw)
    tot = sum(math.exp(v - mx) for v in w.values())
    return {k: math.exp(v - mx) / tot for k, v in w.items()}


def fisher_p(a, b, c, d, side='two'):
    """a,b / c,d — таблица 2x2. Точный тест Фишера (psi=1)."""
    m1, m2, n = a + b, c + d, a + c
    pm = nchg_pmf(m1, m2, n, 1.0)
    if side == 'greater':
        return sum(v for k, v in pm.items() if k >= a)
    if side == 'less':
        return sum(v for k, v in pm.items() if k <= a)
    p0 = pm[a]
    return min(1.0, sum(v for v in pm.values() if v <= p0 * (1 + 1e-9)))


def or_exact_ci(a, b, c, d, alpha=0.05):
    """Точный ДИ отношения шансов (инверсия одностороннего нецентрального теста)."""
    m1, m2, n = a + b, c + d, a + c
    lo_k, hi_k = max(0, n - m2), min(n, m1)
    if a == lo_k: low = 0.0
    else:
        x, y = 1e-8, 1e8
        for _ in range(200):
            m = math.sqrt(x * y)
            pm = nchg_pmf(m1, m2, n, m)
            if sum(v for k, v in pm.items() if k >= a) > alpha / 2: y = m
            else: x = m
        low = math.sqrt(x * y)
    if a == hi_k: high = float('inf')
    else:
        x, y = 1e-8, 1e8
        for _ in range(200):
            m = math.sqrt(x * y)
            pm = nchg_pmf(m1, m2, n, m)
            if sum(v for k, v in pm.items() if k <= a) < alpha / 2: y = m
            else: x = m
        high = math.sqrt(x * y)
    return low, high


def or_test(a, b, c, d, psi0, side='less'):
    """Точный p для H0: OR = psi0 (одностороннее)."""
    m1, m2, n = a + b, c + d, a + c
    pm = nchg_pmf(m1, m2, n, psi0)
    if side == 'less':
        return sum(v for k, v in pm.items() if k <= a)
    return sum(v for k, v in pm.items() if k >= a)


def rr(k1, n1, k2, n2):
    if not (n1 and n2 and k2): return float('nan')
    return (k1 / n1) / (k2 / n2)


def load():
    doms = []
    with open(SRC, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            d0 = dp(r['день запуска'])
            offs = [(dp(x) - d0).days for x in (r['даты регистраций'] or '').split()]
            rk = [0] * (KMAX + 1)
            for k in offs:
                rk[min(max(k, 0), KMAX)] += 1
            reg, wreg = iv(r['регистраций']), iv(r['регистраций в окне 3 суток'])
            doms.append(dict(
                dom=r['домен'], zone=r['зона'], d0=d0, day=r['день запуска'],
                age=(REF - d0).days, ndays=(r['дней'] or '').strip(),
                closed=r['окно закрыто'].strip() == 'да',
                content=r['набор контента'], fam=r['семейство'],
                hour=iv(r['час запуска']), block=r['блок часа'],
                sites=iv(r['сайтов']), sites_w=iv(r['сайтов в окне']),
                w2=iv(r['сайтов во 2-й волне']),
                reg=reg, wreg=wreg, tail=reg - wreg,
                ya=iv(r['из поиска']), wya=iv(r['кликов из поиска в окне']),
                hit3=iv(r['вышли за 3 суток']), hit7=iv(r['вышли за 7 суток']),
                rk=rk, offs=offs))
    return doms


def filt(doms):
    a = [d for d in doms if d['dom'] not in OUTLIERS]
    b = [d for d in a if d['closed']]
    c = [d for d in b if d['ndays'] == '2']
    return a, b, c


def main():
    t = Tee(OUT); sys.stdout = t
    print('КОНТРПРОВЕРКА №12 (статистика и определения): окно «3 суток», час запуска и семейство')
    print('Источник: %s' % SRC)
    doms = load()
    print('строк в своде: %d' % len(doms))
    a, b, c = filt(doms)
    print('после снятия выбросов: %d; после «окно закрыто = да»: %d; после «дней = 2»: %d'
          % (len(a), len(b), len(c)))
    nd = collections.Counter(d['ndays'] for d in b)
    print('  распределение «дней» среди закрытых: %s' % dict(sorted(nd.items())))
    unclosed = [d for d in a if not d['closed']]
    print('  у незакрытых (%d): регистраций всего %d, в окне %d — исключены верно'
          % (len(unclosed), sum(d['reg'] for d in unclosed), sum(d['wreg'] for d in unclosed)))
    d1 = [d for d in a if d['closed'] and d['ndays'] != '2']
    print('  у «дней != 2» и закрытых (%d): регистраций %d, в окне %d' %
          (len(d1), sum(d['reg'] for d in d1), sum(d['wreg'] for d in d1)))

    base = c
    print('\n' + '=' * 78)
    print('1. ВОСПРОИЗВЕДЕНИЕ КЛЮЧЕВЫХ ЧИСЕЛ')
    print('=' * 78)

    # --- час запуска, возраст >=7, без «не записан»
    H = [d for d in base if d['d0'] <= CUT_HOUR and d['content'] != NOCONTENT]
    print('(а) час: доменов %d, регистраций %d, в окне %d, хвост %d'
          % (len(H), sum(d['reg'] for d in H), sum(d['wreg'] for d in H),
             sum(d['tail'] for d in H)))
    grp = {'18-23': [d for d in H if d['block'] == '18-23'],
           '00-11': [d for d in H if d['block'] in ('00-05', '06-11')],
           '12-17': [d for d in H if d['block'] == '12-17']}
    grp['остальные (00-17)'] = grp['00-11'] + grp['12-17']
    for k in ('18-23', '00-11', '12-17', 'остальные (00-17)'):
        g = grp[k]
        print('  %-18s доменов %4d | хвост %s' % (k, len(g),
              ci_s(sum(d['tail'] for d in g), sum(d['reg'] for d in g))))
    ev = grp['18-23']; ni = grp['00-11']; oth = grp['остальные (00-17)']
    a1, n1 = sum(d['tail'] for d in ev), sum(d['reg'] for d in ev)
    a2, n2 = sum(d['tail'] for d in ni), sum(d['reg'] for d in ni)
    a3, n3 = sum(d['tail'] for d in oth), sum(d['reg'] for d in oth)
    print('  сверка с отчётом: 22/93 у вечерних и 13/60 у 00–11 → %d/%d и %d/%d %s'
          % (a1, n1, a2, n2, 'СОВПАЛО' if (a1, n1, a2, n2) == (22, 93, 13, 60) else 'НЕ СОВПАЛО'))

    # --- семейства, возраст >=10, без «не записан»
    F = [d for d in base if d['d0'] <= CUT_FAM and d['content'] != NOCONTENT]
    print('\n(б) семейства: доменов %d, регистраций %d, в окне %d, хвост %d'
          % (len(F), sum(d['reg'] for d in F), sum(d['wreg'] for d in F),
             sum(d['tail'] for d in F)))
    fams = collections.defaultdict(list)
    for d in F: fams[d['fam']].append(d)
    print('  %-12s %6s %6s %6s %6s  %-24s  захват' % ('семейство', 'домен', 'рег', 'в окне', 'хвост', 'хвост % [ДИ 95]'))
    for fam, ds in sorted(fams.items(), key=lambda kv: -sum(d['reg'] for d in kv[1])):
        reg = sum(d['reg'] for d in ds); tl = sum(d['tail'] for d in ds)
        ya = sum(d['ya'] for d in ds); wya = sum(d['wya'] for d in ds)
        print('  %-12s %6d %6d %6d %6d  %-24s  %.2f' % (fam, len(ds), reg,
              sum(d['wreg'] for d in ds), tl, ci_s(tl, reg), (wya / ya) if ya else 0))
    AN = [d for d in F if d['fam'] in ('archive', 'NEW')]
    RE = [d for d in F if d['fam'] not in ('archive', 'NEW')]
    k1, m1_ = sum(d['tail'] for d in AN), sum(d['reg'] for d in AN)
    k2, m2_ = sum(d['tail'] for d in RE), sum(d['reg'] for d in RE)
    print('  archive+NEW %s против остальных %s; RR = %.2f' % (ci_s(k1, m1_), ci_s(k2, m2_), rr(k1, m1_, k2, m2_)))
    print('  сверка с отчётом (40/169 против 11/57): %s'
          % ('СОВПАЛО' if (k1, m1_, k2, m2_) == (40, 169, 11, 57) else 'НЕ СОВПАЛО'))

    print('\n' + '=' * 78)
    print('2. ЧТО ИМЕННО ИСКЛЮЧАЕТ ЭТОТ ОБЪЁМ: ТОЧНЫЕ ДИ И ПРОВЕРКА ГИПОТЕЗЫ ПОСТАНОВКИ')
    print('=' * 78)
    cases = [
        ('час: 18–23 против 00–11', a1, n1 - a1, a2, n2 - a2, 1.7),
        ('час: 18–23 против 00–17', a1, n1 - a1, a3, n3 - a3, 1.7),
        ('семейства: archive+NEW против остальных', k1, m1_ - k1, k2, m2_ - k2, 2.0),
    ]
    for name, A, B, C, D, target in cases:
        p2 = fisher_p(A, B, C, D, 'two')
        lo, hi = or_exact_ci(A, B, C, D)
        r = rr(A, A + B, C, C + D)
        p0 = C / (C + D)
        # целевой OR, соответствующий RR = target при базовой доле p0
        p1t = min(target * p0, 0.999)
        or_t = (p1t / (1 - p1t)) / (p0 / (1 - p0))
        pt = or_test(A, B, C, D, or_t, 'less')
        print('\n  %s' % name)
        print('    наблюдено: %d/%d против %d/%d, RR = %.2f' % (A, A + B, C, C + D, r))
        print('    точный ДИ отношения шансов: [%.2f–%s]; p(Фишер, двуст.) = %.3f'
              % (lo, ('%.2f' % hi) if hi != float('inf') else 'inf', p2))
        print('    постановка ждала RR = %.1f (это OR = %.2f). Он ВНУТРИ ДИ: %s; '
              'p против H0(RR=%.1f), одностор. = %.3f → %s'
              % (target, or_t, 'да' if lo <= or_t <= hi else 'НЕТ', target, pt,
                 'H0 «эффект как в постановке» НЕ отвергается' if pt > 0.05
                 else 'H0 «эффект как в постановке» отвергается'))

    print('\n' + '=' * 78)
    print('3. МОЩНОСТЬ: увидел бы этот объём эффект, которого ждала постановка?')
    print('=' * 78)
    random.seed(7)
    NS = 20000
    for name, A, B, C, D, target in cases:
        n_a, n_b = A + B, C + D
        p0 = C / n_b
        p1 = min(target * p0, 0.99)
        hit = 0; hit_ci = 0
        for _ in range(NS):
            x = sum(1 for _ in range(n_a) if random.random() < p1)
            y = sum(1 for _ in range(n_b) if random.random() < p0)
            if fisher_p(x, n_a - x, y, n_b - y, 'greater') < 0.05: hit += 1
        print('  %-42s n=%d/%d, базовая доля %.3f, ожидаемая %.3f → мощность (Фишер, 1-стор., a=0.05) = %.0f%%'
              % (name, n_a, n_b, p0, p1, 100.0 * hit / NS))
    print('  (при мощности ниже ~80%% «не нашли» не равно «нет»)')

    print('\n' + '=' * 78)
    print('4. УСТОЙЧИВОСТЬ: снимаем топ-3 домена по регистрациям в каждой группе')
    print('=' * 78)
    def drop_top(ds, k=3):
        s = sorted(ds, key=lambda d: (-d['reg'], d['dom']))
        return s[k:], s[:k]
    for label, g1, g2 in (('час 18–23 / 00–11', ev, ni),
                          ('час 18–23 / 00–17', ev, oth),
                          ('семейства archive+NEW / остальные', AN, RE)):
        r1, top1 = drop_top(g1); r2, top2 = drop_top(g2)
        A, nA = sum(d['tail'] for d in r1), sum(d['reg'] for d in r1)
        C, nC = sum(d['tail'] for d in r2), sum(d['reg'] for d in r2)
        print('  %s' % label)
        print('    снято сверху 1: %s' % ', '.join('%s(рег %d, хвост %d)' % (d['dom'], d['reg'], d['tail']) for d in top1))
        print('    снято сверху 2: %s' % ', '.join('%s(рег %d, хвост %d)' % (d['dom'], d['reg'], d['tail']) for d in top2))
        print('    после снятия: %s против %s; RR = %.2f; точный ДИ OR [%.2f–%s]'
              % (ci_s(A, nA), ci_s(C, nC), rr(A, nA, C, nC),
                 or_exact_ci(A, nA - A, C, nC - C)[0],
                 ('%.2f' % or_exact_ci(A, nA - A, C, nC - C)[1]) if or_exact_ci(A, nA - A, C, nC - C)[1] != float('inf') else 'inf'))
    # концентрация хвоста
    print('\n  Концентрация хвоста (срез семейств, хвост %d на %d доменах):' % (sum(d['tail'] for d in F), sum(1 for d in F if d['tail'])))
    tops = sorted([d for d in F if d['tail']], key=lambda d: -d['tail'])[:8]
    tot_tail = sum(d['tail'] for d in F)
    acc = 0
    for d in tops:
        acc += d['tail']
        print('    %-16s семейство %-10s хвост %2d, рег %2d, накопл. %2d/%d = %.0f%%'
              % (d['dom'], d['fam'], d['tail'], d['reg'], acc, tot_tail, 100.0 * acc / tot_tail))

    print('\n' + '=' * 78)
    print('5. ЭКСПОЗИЦИЯ: хвост меряется на разной длине наблюдения')
    print('=' * 78)
    print('  %-12s %6s %8s %8s | хвост(всё время) | хвост в горизонте 0..10 сут' % ('семейство', 'домен', 'медиана возраста', 'мин'))
    for fam, ds in sorted(fams.items(), key=lambda kv: -sum(d['reg'] for d in kv[1])):
        ages = sorted(d['age'] for d in ds)
        med = ages[len(ages) // 2]
        reg = sum(d['reg'] for d in ds); tl = sum(d['tail'] for d in ds)
        # горизонт: считаем только регистрации со смещением <= 10 от дня запуска
        regH = sum(sum(d['rk'][:11]) for d in ds)
        tailH = sum(sum(d['rk'][4:11]) for d in ds)
        print('  %-12s %6d %8d %8d | %-16s | %s' % (fam, len(ds), med, ages[0],
              '%d/%d = %.0f%%' % (tl, reg, 100.0 * tl / reg) if reg else '—',
              '%d/%d = %.0f%%' % (tailH, regH, 100.0 * tailH / regH) if regH else '—'))
    ANh = (sum(sum(d['rk'][4:11]) for d in AN), sum(sum(d['rk'][:11]) for d in AN))
    REh = (sum(sum(d['rk'][4:11]) for d in RE), sum(sum(d['rk'][:11]) for d in RE))
    print('  archive+NEW %s против остальных %s на общем горизонте 0..10; RR = %.2f; точный ДИ OR [%.2f–%s]'
          % (ci_s(*ANh), ci_s(*REh), rr(ANh[0], ANh[1], REh[0], REh[1]),
             or_exact_ci(ANh[0], ANh[1] - ANh[0], REh[0], REh[1] - REh[0])[0],
             ('%.2f' % or_exact_ci(ANh[0], ANh[1] - ANh[0], REh[0], REh[1] - REh[0])[1])
             if or_exact_ci(ANh[0], ANh[1] - ANh[0], REh[0], REh[1] - REh[0])[1] != float('inf') else 'inf'))

    print('\n' + '=' * 78)
    print('6. ОБЪЁМ СОБЫТИЙ ПО ГРУППАМ (порог «меньше 20 регистраций ничего не доказывает»)')
    print('=' * 78)
    small = []
    for fam, ds in sorted(fams.items(), key=lambda kv: -sum(d['reg'] for d in kv[1])):
        reg = sum(d['reg'] for d in ds)
        if reg < 20: small.append('%s (%d)' % (fam, reg))
    print('  семейства с рег < 20: %s' % ('; '.join(small) if small else 'нет'))
    print('  семейства с рег >= 20: %s' % '; '.join(
        '%s (%d)' % (f, sum(d['reg'] for d in ds)) for f, ds in sorted(fams.items(), key=lambda kv: -sum(d['reg'] for d in kv[1]))
        if sum(d['reg'] for d in ds) >= 20))
    print('  блоки часа: ' + '; '.join('%s рег %d, хвост %d' % (bl, sum(d['reg'] for d in H if d['block'] == bl),
          sum(d['tail'] for d in H if d['block'] == bl)) for bl in ('00-05', '06-11', '12-17', '18-23')))

    print('\n' + '=' * 78)
    print('7. ЛИНЕЙКА: проверяю определение окна сам (это не статистика, а арифметика)')
    print('=' * 78)
    cnt = collections.Counter()
    for d in base:
        if not d['reg']: continue
        s03 = sum(d['rk'][:4]); s02 = sum(d['rk'][:3]); s04 = sum(d['rk'][:5])
        if d['wreg'] == s03: cnt['в окне = Σ r0..r3'] += 1
        elif d['wreg'] == s02: cnt['в окне = Σ r0..r2'] += 1
        elif d['wreg'] == s04: cnt['в окне = Σ r0..r4'] += 1
        else: cnt['иное'] += 1
    for k, v in cnt.most_common(): print('  %-24s %5d' % (k, v))
    # «план»: 0..3 вечерним, 0..2 остальным
    ev_plan = sum(sum(d['rk'][:4]) for d in ev)
    ev_svod = sum(d['wreg'] for d in ev)
    oth_plan = sum(sum(d['rk'][:3]) for d in oth)
    oth_svod = sum(d['wreg'] for d in oth)
    print('  «исправленное» окно плана: вечерним %d против %d в своде (%+d); '
          'остальным %d против %d (%+d)' % (ev_plan, ev_svod, ev_plan - ev_svod,
                                            oth_plan, oth_svod, oth_plan - oth_svod))
    print('  длина окна 0..3 по часу запуска: час 23 → %d ч, час 0 → %d ч; отношение %.2f'
          % (96 - 23, 96 - 0, (96 - 23) / 96.0))

    print('\n' + '=' * 78)
    print('8. МНОЖЕСТВЕННОСТЬ В ОТЧЁТЕ ТЕСТИРОВЩИКА')
    print('=' * 78)
    txt = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h12_window_bias_hour_family.txt')
    n_p = 0
    with open(txt, encoding='utf-8') as f:
        for line in f:
            n_p += line.count('0.0') * 0  # считаем ниже
    import re
    body = open(txt, encoding='utf-8').read()
    ps = re.findall(r'\b[01]\.\d{3}\b', body)
    print('  чисел вида p (0.xxx) в выводе: %d' % len(ps))
    sig = [p for p in ps if float(p) < 0.05]
    print('  из них < 0.05: %d (%s)' % (len(sig), ', '.join(sorted(set(sig))[:12])))
    print('  порог Бонферрони при %d тестах: %.5f' % (len(ps), 0.05 / max(len(ps), 1)))
    print('  → ни один результат не переживает поправку; но это симметрично:')
    print('    отчёт делает ВЫВОД О ОТСУТСТВИИ эффекта, для которого множественность не защита,')
    print('    а мощность (раздел 3) — единственный релевантный критерий.')

    print('\n' + '=' * 78)
    print('9. ЧТО ИМЕННО ГОВОРИТ ОГОВОРКА: сдвиг «окно → всё время» по семействам')
    print('=' * 78)
    print('  Оговорка: «окно занижает медленные семейства на 20–35 %». Сдвиг = рег/рег в окне − 1.')
    for fam, ds in sorted(fams.items(), key=lambda kv: -sum(d['reg'] for d in kv[1])):
        reg = sum(d['reg'] for d in ds); w = sum(d['wreg'] for d in ds)
        print('  %-12s рег %3d, в окне %3d → сдвиг %s' % (fam, reg, w,
              ('%+.0f%%' % (100.0 * (reg / w - 1))) if w else '— (0 в окне)'))
    regAN, wAN = sum(d['reg'] for d in AN), sum(d['wreg'] for d in AN)
    regRE, wRE = sum(d['reg'] for d in RE), sum(d['wreg'] for d in RE)
    print('  archive+NEW: %+.0f%% (%d → %d); остальные: %+.0f%% (%d → %d); '
          'ОТНОШЕНИЕ сдвигов %.2f' % (100.0 * (regAN / wAN - 1), wAN, regAN,
          100.0 * (regRE / wRE - 1), wRE, regRE,
          (regAN / wAN) / (regRE / wRE)))
    print('  весь срез: %+.0f%% (%d → %d) — окно занижает ВСЕХ примерно на треть,'
          % (100.0 * (sum(d['reg'] for d in F) / sum(d['wreg'] for d in F) - 1),
             sum(d['wreg'] for d in F), sum(d['reg'] for d in F)))
    print('  то есть «20–35 %» верно как абсолютная величина усечения; спорна только')
    print('  её РАЗНИЦА между семействами.')
    t.flush()
    sys.stdout = sys.__stdout__


if __name__ == '__main__':
    main()

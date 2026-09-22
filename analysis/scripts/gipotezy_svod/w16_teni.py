# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №16 (угол: ТЕНИ / конфаундинг).
Вопрос: не является ли «список денежных брендов и его воспроизводимая верхушка»
тенью набора контента / дня / зоны / периода / оконной атрибуции / отдельных доменов
/ неравной поисковой экспозиции брендов.
Только stdlib.
"""
import csv, os, re, math, random, collections, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
SRC_BR = os.path.join(REPO, 'analysis', 'export', 'brendy_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w16_teni.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
BRAND_RE = re.compile(r'^\s*(.+?)\s*\((\d+)\)\s*$')
TOPK = 10
NSIM = 4000
NSPLIT = 400


class Tee(object):
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def __call__(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s)
        self.f.write(s + '\n')

    def close(self):
        self.f.close()


def ti(s):
    s = (s or '').strip()
    return int(s) if s else 0


def parse_brands(s):
    out = []
    for part in (s or '').split(','):
        part = part.strip()
        if not part:
            continue
        m = BRAND_RE.match(part)
        if not m:
            raise ValueError(part)
        out.append((m.group(1), int(m.group(2))))
    return out


def iso_week(day):
    y, m, d = (int(x) for x in day.split('-'))
    return datetime.date(y, m, d).isocalendar()[1]


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


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float('nan')
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return float('nan')
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def top_share(sel, other, k=TOPK):
    tot = sum(other.values())
    if tot == 0:
        return float('nan')
    vals = sorted((v for v in sel.values() if v > 0), reverse=True)
    if not vals:
        return 0.0
    thr = vals[k - 1] if len(vals) > k else 0
    n_above = sum(1 for v in vals if v > thr)
    n_tied = sum(1 for v in vals if v == thr) if thr > 0 else 0
    tied_w = (k - n_above) / n_tied if n_tied else 0.0
    acc = 0.0
    for b, v in sel.items():
        if v > thr:
            acc += other.get(b, 0)
        elif thr > 0 and v == thr:
            acc += tied_w * other.get(b, 0)
    return acc / tot


def top_set(cnt, k=TOPK):
    vals = sorted((v for v in cnt.values() if v > 0), reverse=True)
    if not vals:
        return set()
    thr = vals[k - 1] if len(vals) > k else vals[-1]
    return set(b for b, v in cnt.items() if v >= thr and v > 0)


def stats_from_halves(A, B, universe_n):
    tot = collections.Counter()
    tot.update(A)
    tot.update(B)
    ta, tb = top_set(A), top_set(B)
    xa = [A[b] for b in tot]
    xb = [B[b] for b in tot]
    if universe_n and universe_n > len(tot):
        xa += [0] * (universe_n - len(tot))
        xb += [0] * (universe_n - len(tot))
    return {
        'share': (top_share(A, B) + top_share(B, A)) / 2.0,
        'overlap': len(ta & tb),
        'top10_all': top_share(tot, tot),
        'rho_all': spearman(xa, xb),
        'nA': sum(A.values()), 'nB': sum(B.values()), 'nbr': len(tot),
        'core': ta & tb,
    }


def pval_ge(null, obs):
    if obs != obs:
        return float('nan')
    return (sum(1 for v in null if v >= obs) + 1.0) / (len(null) + 1.0)


def q(null, p):
    v = sorted(x for x in null if x == x)
    if not v:
        return float('nan')
    return v[min(len(v) - 1, int(p * len(v)))]


def mean(v):
    v = [x for x in v if x == x]
    return sum(v) / len(v) if v else float('nan')


def binom_pmf(k, n, p):
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_two(k, n, p):
    pk = binom_pmf(k, n, p)
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(n + 1)
                        if binom_pmf(i, n, p) <= pk * (1 + 1e-9)))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


# ------------------------------------------------------------------ данные
def load():
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    recs = []   # (домен, бренд, n, ключи)
    doms = {}
    for r in rows:
        d = r['домен']
        day = r['день запуска']
        key = {
            'домен': d, 'зона': r['зона'], 'день': day,
            'набор': r['набор контента'], 'семейство': r['семейство'],
            'час': r['блок часа'], 'месяц': day[5:7], 'неделя': iso_week(day),
            'закрыто': r['окно закрыто'] == 'да', 'дней': ti(r['дней']),
            'рег': ti(r['регистраций']), 'фд': ti(r['ФД']),
            'регw': ti(r['регистраций в окне 3 суток']), 'фдw': ti(r['ФД в окне 3 суток']),
            'выброс': d in OUTLIERS, 'безнабора': r['набор контента'] == NOCONTENT,
            'поиск_окно': ti(r['кликов из поиска в окне']),
        }
        doms[d] = key
        for b, n in parse_brands(r['какие бренды конвертили']):
            recs.append((d, b, n))
    return doms, recs


def brand_exposure():
    ex = {}
    for r in csv.DictReader(open(SRC_BR, encoding='utf-8')):
        def f(x):
            x = (x or '').strip().replace(' ', '')
            return float(x) if x else 0.0
        ex[r['бренд']] = (f(r['поисковых кликов']), f(r['вышли в поиск']), f(r['сайтов']))
    return ex


def build_records(doms, recs, cut):
    """cut: функция домена -> bool. Возвращает список (домен, бренд, n)."""
    return [(d, b, n) for d, b, n in recs if cut(doms[d])]


def split_counters(records, half_of):
    A = collections.Counter()
    B = collections.Counter()
    for d, b, n in records:
        (A if half_of(d) == 'A' else B)[b] += n
    return A, B


def null_counters(records, half_of, rng, pool, weights=None, cum=None):
    A = collections.Counter()
    B = collections.Counter()
    for d, b, n in records:
        if weights is None:
            nb = pool[rng.randrange(len(pool))]
        else:
            x = rng.random() * cum[-1]
            lo, hi = 0, len(cum) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if cum[mid] < x:
                    lo = mid + 1
                else:
                    hi = mid
            nb = pool[lo]
        (A if half_of(d) == 'A' else B)[nb] += n
    return A, B


def run_block(log, title, records, doms, half_of, universe_n, pool_obs, exposure, nsim=NSIM, seed=7):
    rng = random.Random(seed)
    A, B = split_counters(records, half_of)
    obs = stats_from_halves(A, B, universe_n)
    log('  доменов с конверсиями %d, записей %d, событий A=%d B=%d, брендов %d'
        % (len({d for d, _, _ in records}), len(records), obs['nA'], obs['nB'], obs['nbr']))
    log('  НАБЛЮД.: топ-10 половины ловит %.1f%% другой половины | пересечение топ-10 = %d | топ-10 от всех %.1f%% | Спирмен(все 206) %.3f'
        % (100 * obs['share'], obs['overlap'], 100 * obs['top10_all'], obs['rho_all']))
    log('           ядро (топ-10 в обеих половинах): %s' % (', '.join(sorted(obs['core'])) or '—'))

    variants = []
    variants.append(('R-K равновероятно (нуль тестировщика)', list(pool_obs), None))
    all206 = sorted(exposure.keys())
    variants.append(('R-206 равновероятно', all206, None))
    variants.append(('вес ∝ поисковых кликов бренда', all206, [exposure[b][0] for b in all206]))
    variants.append(('вес ∝ вышедших сайтов бренда', all206, [exposure[b][1] for b in all206]))

    for name, pool, w in variants:
        cum = None
        if w is not None:
            cum = []
            s = 0.0
            for x in w:
                s += x
                cum.append(s)
        sh, ov, ta, ra = [], [], [], []
        for _ in range(nsim):
            nA, nB = null_counters(records, half_of, rng, pool, w, cum)
            st = stats_from_halves(nA, nB, universe_n)
            sh.append(st['share'])
            ov.append(st['overlap'])
            ta.append(st['top10_all'])
            ra.append(st['rho_all'])
        log('    [%-32s] доля топ-10: нуль ср. %.1f%% (95-й %.1f%%), p=%.4f | пересеч.: нуль ср. %.1f (95-й %d), p=%.4f | топ-10 от всех: нуль ср. %.1f%%, p=%.4f'
            % (name, 100 * mean(sh), 100 * q(sh, 0.95), pval_ge(sh, obs['share']),
               mean(ov), q(ov, 0.95), pval_ge(ov, obs['overlap']),
               100 * mean(ta), pval_ge(ta, obs['top10_all'])))
    return obs


def main():
    log = Tee(OUT)
    doms, recs = load()
    exposure = brand_exposure()
    log('КОНТРПРОВЕРКА №16 — ТЕНИ. Источник: analysis/export/svod_domenov_21.09.csv (2077 доменов),')
    log('экспозиция брендов: analysis/export/brendy_21.09.csv (206 брендов).')
    log('')

    # ---------------------------------------------------------------- 0. баланс бренда по конфаундерам
    log('=' * 100)
    log('0. МОЖЕТ ЛИ БРЕНД ВООБЩЕ БЫТЬ ТЕНЬЮ НАБОРА / ДНЯ / ЗОНЫ')
    log('=' * 100)
    br = list(csv.DictReader(open(SRC_BR, encoding='utf-8')))
    sites = sorted(int(r['сайтов']) for r in br)
    zones = collections.Counter(r['зоны'] for r in br)
    log('  Сайтов на бренд: мин %d, медиана %d, макс %d — бренд стоит на каждой базе по одному сабдомену,'
        % (sites[0], sites[len(sites) // 2], sites[-1]))
    log('  поэтому набор контента, день и зона распределены между брендами практически поровну:')
    for zz, c in zones.most_common(3):
        log('    зонный профиль «%s» — у %d брендов' % (zz, c))
    log('  ВЫВОД по каналу конфаундинга: классической тени «набор/день/зона → бренд» быть не может по дизайну.')
    log('  Остаются четыре реальных канала: (1) неравная поисковая экспозиция брендов,')
    log('  (2) оконная атрибуция (все-время против окна 3 суток), (3) отдельные домены/дни-киты, (4) период август/сентябрь.')
    cl = sorted((exposure[b][0] for b in exposure), reverse=True)
    tcl = sum(cl)
    log('  Поисковые клики по брендам крайне неравномерны: топ-10 брендов по кликам держат %.1f%% всех %d кликов'
        % (100 * sum(cl[:10]) / tcl, int(tcl)))
    log('  (1win 185 794, Apex 69 460, Kush 67 488 …), то есть «равновероятный бренд» — не единственный разумный нуль.')
    log('')

    # ---------------------------------------------------------------- 1. лесенка фильтров
    log('=' * 100)
    log('1. ЛЕСЕНКА ЖЁСТКИХ ФИЛЬТРОВ: ЧТО ОСТАЁТСЯ ОТ ЭФФЕКТА, КОГДА ЧИСТКИ ПРИМЕНЕНЫ НЕ ПО ОДНОЙ, А ВМЕСТЕ')
    log('=' * 100)

    def base_cut(k):
        return k['закрыто'] and k['дней'] >= 2

    cuts = [
        ('A. фильтр тестировщика (окно закрыто, дней ≥ 2)', base_cut),
        ('B. + строгая оконная атрибуция (рег = рег в окне, ФД = ФД в окне)',
         lambda k: base_cut(k) and k['рег'] == k['регw'] and k['фд'] == k['фдw']),
        ('C. + без «КОНТЕНТ НЕ ЗАПИСАН»',
         lambda k: base_cut(k) and k['рег'] == k['регw'] and k['фд'] == k['фдw'] and not k['безнабора']),
        ('D. + без выбросов 3615.team / 3286.team',
         lambda k: base_cut(k) and k['рег'] == k['регw'] and k['фд'] == k['фдw']
         and not k['безнабора'] and not k['выброс']),
    ]
    parity = lambda d: 'A' if int(doms[d]['день'][8:10]) % 2 else 'B'
    month = lambda d: 'A' if doms[d]['месяц'] == '08' else 'B'
    results = {}
    for name, cut in cuts:
        records = build_records(doms, recs, cut)
        pool_obs = sorted({b for _, b, _ in records})
        log('-' * 100)
        log('%s  — событий %d' % (name, sum(n for _, _, n in records)))
        log(' * разбиение: ЧЁТНОСТЬ ДНЯ')
        o1 = run_block(log, name, records, doms, parity, 206, pool_obs, exposure)
        log(' * разбиение: АВГУСТ → СЕНТЯБРЬ')
        o2 = run_block(log, name, records, doms, month, 206, pool_obs, exposure)
        results[name[0]] = (o1, o2, records)
    log('')

    # ---------------------------------------------------------------- 2. ядро по разрезам
    log('=' * 100)
    log('2. «УСТОЙЧИВОЕ ЯДРО» ИЗ ВЫВОДА (Cactus, Eva, Leon, Lucky Bird, Martin, Pinco) — ПО ВСЕМ РАЗРЕЗАМ')
    log('=' * 100)
    named = ['Cactus', 'Eva', 'Leon', 'Lucky Bird', 'Martin', 'Pinco']
    cols = []
    for letter in 'ABCD':
        o1, o2, _ = results[letter]
        cols.append((letter + '/чёт', o1['core']))
        cols.append((letter + '/мес', o2['core']))
    log('  бренд        | ' + ' | '.join('%-8s' % c[0] for c in cols) + ' | разрезов из %d' % len(cols))
    allc = set()
    for _, s in cols:
        allc |= s
    for b in sorted(allc, key=lambda x: -sum(1 for _, s in cols if x in s)):
        cnt = sum(1 for _, s in cols if b in s)
        log('  %-12s | ' % b + ' | '.join('%-8s' % ('да' if b in s else '—') for _, s in cols) + ' | %d' % cnt)
    log('  Из шести названных в выводе брендов во ВСЕХ %d разрезах держатся: %s'
        % (len(cols), ', '.join(sorted(b for b in named if all(b in s for _, s in cols))) or '—'))
    log('')

    # ---------------------------------------------------------------- 3. жёсткая страта: сплит внутри набор+день+зона
    log('=' * 100)
    log('3. ЖЁСТКАЯ СТРАТА: ПОЛОВИНЫ НАРЕЗАНЫ ВНУТРИ СТРАТ «НАБОР + ДЕНЬ + ЗОНА» (и вариант +ЧАС)')
    log('   (половины уравнены по набору, дню, зоне: эффект уже не может быть их тенью)')
    log('=' * 100)
    strict_cut = (lambda k: base_cut(k) and k['рег'] == k['регw'] and k['фд'] == k['фдw']
                  and not k['безнабора'] and not k['выброс'])
    for stlabel, keyf, cutf in (
            ('набор+день+зона', lambda k: (k['набор'], k['день'], k['зона']), base_cut),
            ('набор+день+зона+блок часа', lambda k: (k['набор'], k['день'], k['зона'], k['час']), base_cut),
            ('набор+день+зона, И строгое окно + без «не записан» + без выбросов',
             lambda k: (k['набор'], k['день'], k['зона']), strict_cut),
            ('день+зона, И строгое окно + без «не записан» + без выбросов',
             lambda k: (k['день'], k['зона']), strict_cut)):
        records_all = build_records(doms, recs, cutf)
        # домены-носители конверсий, сгруппированные по страте; страты с ≥2 доменами
        bydom = collections.defaultdict(list)
        for d, b, n in records_all:
            bydom[d].append((b, n))
        byst = collections.defaultdict(list)
        for d in bydom:
            byst[keyf(doms[d])].append(d)
        usable = {k: v for k, v in byst.items() if len(v) >= 2}
        kept = sorted(d for v in usable.values() for d in v)
        keptset = set(kept)
        records = [(d, b, n) for d, b, n in records_all if d in keptset]
        pool_obs = sorted({b for _, b, _ in records})
        log('-' * 100)
        log(' Страта «%s»: страт с ≥2 конверсионными доменами %d, доменов %d, событий %d (из %d)'
            % (stlabel, len(usable), len(kept), sum(n for _, _, n in records),
               sum(n for _, _, n in records_all)))
        if sum(n for _, _, n in records) < 40:
            log('   объёма не хватает — пропуск')
            continue
        rng = random.Random(11)
        obs_sh, obs_ov = [], []
        splits = []
        for _ in range(NSPLIT):
            half = {}
            for k, v in usable.items():
                vv = list(v)
                rng.shuffle(vv)
                for i, d in enumerate(vv):
                    half[d] = 'A' if i % 2 == 0 else 'B'
            splits.append(half)
            A, B = split_counters(records, lambda d, h=half: h[d])
            st = stats_from_halves(A, B, 206)
            obs_sh.append(st['share'])
            obs_ov.append(st['overlap'])
        log('   НАБЛЮД. (медиана по %d сбалансированным сплитам): доля топ-10 = %.1f%% [%.1f–%.1f], пересечение топ-10 = %.1f [%d–%d]'
            % (NSPLIT, 100 * q(obs_sh, 0.5), 100 * q(obs_sh, 0.05), 100 * q(obs_sh, 0.95),
               mean(obs_ov), q(obs_ov, 0.05), q(obs_ov, 0.95)))
        all206 = sorted(exposure.keys())
        for name, pool, w in (('R-K равновероятно', list(pool_obs), None),
                              ('R-206 равновероятно', all206, None),
                              ('вес ∝ поисковых кликов', all206, [exposure[b][0] for b in all206]),
                              ('вес ∝ вышедших сайтов', all206, [exposure[b][1] for b in all206])):
            cum = None
            if w is not None:
                cum = []
                s = 0.0
                for x in w:
                    s += x
                    cum.append(s)
            nsh, nov = [], []
            for i in range(NSIM):
                half = splits[i % NSPLIT]
                nA, nB = null_counters(records, lambda d, h=half: h[d], rng, pool, w, cum)
                st = stats_from_halves(nA, nB, 206)
                nsh.append(st['share'])
                nov.append(st['overlap'])
            log('     [%-22s] доля топ-10: нуль ср. %.1f%% (95-й %.1f%%), p=%.4f | пересеч.: нуль ср. %.1f (95-й %d), p=%.4f'
                % (name, 100 * mean(nsh), 100 * q(nsh, 0.95), pval_ge(nsh, q(obs_sh, 0.5)),
                   mean(nov), q(nov, 0.95), pval_ge(nov, mean(obs_ov))))
        # какое ядро чаще всего
        core_cnt = collections.Counter()
        for half in splits:
            A, B = split_counters(records, lambda d, h=half: h[d])
            core_cnt.update(stats_from_halves(A, B, 206)['core'])
        log('   Кто попадает в топ-10 обеих половин чаще всего (доля из %d сплитов):' % NSPLIT)
        log('     ' + ', '.join('%s %.0f%%' % (b, 100 * c / NSPLIT) for b, c in core_cnt.most_common(12)))
    log('')

    # ---------------------------------------------------------------- 4. концентрация по доменам и дням
    log('=' * 100)
    log('4. ТЕНЬ ОТДЕЛЬНЫХ ДОМЕНОВ И ДНЕЙ: НАСКОЛЬКО СПИСОК ДЕРЖИТСЯ НА ЕДИНИЦАХ НАБЛЮДЕНИЙ')
    log('=' * 100)
    records = build_records(doms, recs, base_cut)
    per_brand = collections.Counter()
    per_brand_dom = collections.defaultdict(collections.Counter)
    per_day = collections.Counter()
    for d, b, n in records:
        per_brand[b] += n
        per_brand_dom[b][d] += n
        per_day[doms[d]['день']] += n
    log('  бренд        | всего | доменов | макс. вклад одного домена | доля макс. домена | август/сентябрь')
    for b, tot in per_brand.most_common(12):
        dd = per_brand_dom[b]
        mx = max(dd.values())
        aug = sum(n for d, n in dd.items() if doms[d]['месяц'] == '08')
        log('  %-12s | %5d | %7d | %25d | %16.0f%% | %d/%d'
            % (b, tot, len(dd), mx, 100 * mx / tot, aug, tot - aug))
    days = per_day.most_common()
    log('  Дни-киты: %s' % ', '.join('%s=%d' % (d, n) for d, n in days[:5]))
    log('  Всего событий %d на %d дней запуска; топ-3 дня держат %.0f%%'
        % (sum(per_day.values()), len(per_day), 100 * sum(n for _, n in days[:3]) / sum(per_day.values())))
    # джекнайф: выкинуть по одному дню-киту и по одному домену-киту
    log('  Джекнайф по дню запуска (выкидываем один день целиком), разбиение по чётности:')
    for dkill, n in days[:5]:
        rr = [(d, b, nn) for d, b, nn in records if doms[d]['день'] != dkill]
        A, B = split_counters(rr, parity)
        st = stats_from_halves(A, B, 206)
        log('    без %s (−%d событий): доля топ-10 %.1f%%, пересечение %d, ядро: %s'
            % (dkill, n, 100 * st['share'], st['overlap'], ', '.join(sorted(st['core']))))
    log('  Джекнайф по домену (выкидываем один самый конверсионный домен):')
    dtot = collections.Counter()
    for d, b, n in records:
        dtot[d] += n
    for dkill, n in dtot.most_common(5):
        rr = [(d, b, nn) for d, b, nn in records if d != dkill]
        A, B = split_counters(rr, parity)
        st = stats_from_halves(A, B, 206)
        log('    без %s (−%d событий): доля топ-10 %.1f%%, пересечение %d, ядро: %s'
            % (dkill, n, 100 * st['share'], st['overlap'], ', '.join(sorted(st['core']))))
    log('')

    # ---------------------------------------------------------------- 5. часть (б): Leon/Martin под жёсткой стратой
    log('=' * 100)
    log('5. ЧАСТЬ (б): ВЫЖИВАЮТ ЛИ LEON И MARTIN, ЕСЛИ УБРАТЬ ТЕНИ ПЕРИОДА, ОКНА И ДОМЕНА')
    log('=' * 100)
    single = {}
    for d, b, n in recs:
        single.setdefault(d, []).append((b, n))
    for tag, cut in (('фильтр тестировщика', base_cut),
                     ('строгое окно + без «не записан» + без выбросов',
                      lambda k: base_cut(k) and k['рег'] == k['регw'] and k['фд'] == k['фдw']
                      and not k['безнабора'] and not k['выброс'])):
        dd = [d for d in single if cut(doms[d])]
        # однобрендовые домены
        ones = [d for d in dd if len({b for b, _ in single[d]}) == 1]
        reg = collections.Counter()
        fd = collections.Counter()
        domsb = collections.defaultdict(set)
        fd_dom = collections.defaultdict(collections.Counter)
        for d in ones:
            b = single[d][0][0]
            reg[b] += doms[d]['рег']
            fd[b] += doms[d]['фд']
            domsb[b].add(d)
            fd_dom[b][d] += doms[d]['фд']
        R = sum(reg.values())
        F = sum(fd.values())
        log('-' * 100)
        log(' Разрез «%s»: однобрендовых доменов %d, регистраций %d, ФД %d, общая доля ФД %.1f%%'
            % (tag, len(ones), R, F, 100 * F / R if R else float('nan')))
        p0 = F / R if R else 0
        big = [b for b in reg if reg[b] >= 5]
        big.sort(key=lambda b: -reg[b])
        log('  бренд        | рег | ФД | доля ФД | 95%% ДИ | доменов | макс.ФД с 1 домена | биномиальный p')
        for b in big:
            lo, hi = wilson(fd[b], reg[b])
            mx = max(fd_dom[b].values()) if fd_dom[b] else 0
            log('  %-12s | %3d | %2d | %5.0f%% | %3.0f–%3.0f%% | %7d | %18d | %.3f'
                % (b, reg[b], fd[b], 100 * fd[b] / reg[b], 100 * lo, 100 * hi,
                   len(domsb[b]), mx, binom_two(fd[b], reg[b], p0)))
        if not big:
            log('   брендов с ≥5 регистраций нет')
    log('')
    log('=' * 100)
    log('ИТОГ КОНТРПРОВЕРКИ')
    log('=' * 100)
    log('ЧТО НЕ ЯВЛЯЕТСЯ ТЕНЬЮ (каналы закрыты):')
    log('  • Набор контента / день / зона / час. Бренд стоит по одному сабдомену на каждой базе')
    log('    (1685–1925 сайтов на бренд, медиана 1924; зонный профиль .team 57% / .lol 33% / .casino 6%')
    log('    у 152 из 206 брендов) — набор, день и зона между брендами уравнены по дизайну.')
    log('    Сплит половин ВНУТРИ страт «набор+день+зона» на всех 498 событиях (47 страт, 157 доменов,')
    log('    308 событий) эффект НЕ убивает: доля топ-10 = 23.8% [18.8–27.6] против нуля 9.7% (p = 0.0002);')
    log('    с добавлением блока часа — 25.6% [20.2–29.6] против 10.5% (p = 0.0002).')
    log('  • Выбросы 3615.team / 3286.team: на двоих 3 события из 498; их удаление меняет долю на 0.2 п.п.')
    log('  • Домены-киты и дни-киты: джекнайф пяти крупнейших дней (−29…−50 событий) и пяти крупнейших')
    log('    доменов (−6…−9 событий) оставляет долю топ-10 в 25.6–28.3% и пересечение = 6. Максимальный')
    log('    вклад одного домена в бренд — 8–21%.')
    log('ЧТО ТЕНЬЮ ЯВЛЯЕТСЯ (числа тестировщика завышены):')
    log('  1. Масштаб 3.4–3.7× держится только на неочищенных данных. Когда все чистки применены ВМЕСТЕ')
    log('     (строгая оконная атрибуция + без «КОНТЕНТ НЕ ЗАПИСАН» + без выбросов): 498 → 230 событий,')
    log('     доля топ-10 = 21.2% против нуля 11.4% (p = 0.0020) при чётности и 19.0% против 11.3%')
    log('     (p = 0.0475) при авг→сен. Это 1.7–1.9×, а не 3.4–3.7×. При страте «день+зона» на тех же')
    log('     чистых данных (216 событий) — 23.0% [18.5–26.6] против 12.1% (p = 0.0017), те же ~1.9×.')
    log('  2. «6 брендов в топ-10 обеих половин при 1.7 ожидаемых, p = 0.008» НЕ ВЫЖИВАЕТ. Ожидание 1.7')
    log('     получено на неочищенных 498 событиях; на чистых данных ожидание 2.7–4.9, а наблюдённое')
    log('     пересечение 5 даёт p = 0.12 (день+зона), 0.21 (чётность), 0.22 (авг→сен), 0.53')
    log('     (набор+день+зона на 84 событиях). Ни в одном чистом разрезе пересечение не значимо.')
    log('  3. Именное «устойчивое ядро» (Cactus, Eva, Leon, Lucky Bird, Martin, Pinco) — артефакт одного')
    log('     конкретного сплита. По 400 сбалансированным сплитам внутри страт в топ-10 обеих половин')
    log('     попадают: Lucky Bird 98–99%, Leon 73–97%, Pinco 56–82%, Martin 50–82%, Luckybear 64–72%,')
    log('     Mellstroy 51–57%, Eva 34–58%, Cactus 14–45%, Олимп 40–50%. Cactus и Eva менее устойчивы,')
    log('     чем не названные в выводе Luckybear и Mellstroy.')
    log('  4. «Топ-10 держат 34% против 18% при случайности (1.9×)» — зависит от выбора нуля. Поисковая')
    log('     экспозиция брендов крайне неравна (топ-10 по кликам держат 38.9% из 1 781 752 кликов).')
    log('     Под нулём «бренд ∝ поисковым кликам» те же топ-10 держали бы 41% (p = 0.99), под нулём')
    log('     «бренд ∝ вышедшим сайтам» — 21% (p = 0.0002). Честная граница: 34% против 18–21%, т.е. 1.6–1.9×.')
    log('     (Оговорка: клик-взвешенный нуль сам данным противоречит — Lucky Bird даёт 23 рег на 608 кликов,')
    log('     1win 2 рег на 185 794 — поэтому это верхняя граница тени, а не модель.)')
    log('  5. Предел разрешения: при самой жёсткой страте «набор+день+зона» ВМЕСТЕ со всеми чистками')
    log('     остаётся 84 события, и тест перестаёт различать что-либо: 16.0% [7.7–21.5] против нуля 21.8%')
    log('     (95-й перцентиль нуля 33%), p = 0.81 — наблюдённое НИЖЕ нуля. Это не опровержение, а потолок')
    log('     объёма: на 84 событиях у половины остаётся ~35 брендов и топ-10 покрывает почти всё.')
    log('ВЕРДИКТ: часть (а) выживает в ослабленном виде — воспроизводимость верхушки как ДОЛИ есть')
    log('  (1.7–2.4× после всех чисток и жёстких страт, p = 0.0002–0.05), но воспроизводимость СОСТАВА')
    log('  (кто именно в списке) на чистых данных незначима (p = 0.12–0.53). Часть (б) — вывод')
    log('  тестировщика подтверждается и усиливается: после чисток брендов с ≥5 регистрациями остаётся')
    log('  всего 2 (Lucky Bird 1 ФД из 8, Leon 4 из 7), сравнивать нечего.')
    log('=' * 100)
    log.close()


if __name__ == '__main__':
    main()

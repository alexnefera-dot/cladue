#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №9 (объём дня запуска не разбавляет результат домена).
Угол: ТЕНИ. Класс ">=110" внутри главной страты - это не "объём", а два
конкретных календарных дня (08.09 и 11.09). Проверяем, переживает ли вывод
переход к честной единице (день, а не домен/пул), к более жёсткой страте
(+час), к парам с достаточным объёмом с обеих сторон, к джекнайфу по стратам
и к разделению августа и сентября.
Только stdlib.
"""
import collections
import csv
import itertools
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w09_teni.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NBOOT = 10000
random.seed(20260922)

METRICS = [('выход', 'out3', 'sites'),
           ('клики/вышедш', 'clk', 'out3'),
           ('регистрации', 'reg', 'sites'),
           ('скорость', 'out1', 'out3')]


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def __call__(self, *a):
        s = ' '.join(str(x) for x in a)
        print(s)
        self.f.write(s + '\n')

    def close(self):
        self.f.close()


def num(s, d=0.0):
    s = (s or '').strip()
    return d if s == '' else float(s)


def zg(z):
    return z if z in ('team', 'lol', 'casino', 'buzz') else 'прочие'


def vcls(n):
    return '<60' if n < 60 else ('60-110' if n < 110 else '>=110')


def f(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return '—'
    return ('%.' + str(d) + 'f') % x


def pois_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s, t = 0.0, math.exp(-lam)
    for i in range(k + 1):
        s += t
        t *= lam / (i + 1)
    return min(1.0, s)


def pois_ci(k, alpha=0.05):
    """Точный (Garwood) доверительный интервал для среднего пуассона."""
    if k == 0:
        hi = 0.0
        lo_b, hi_b = 0.0, 100.0
        for _ in range(200):
            m = (lo_b + hi_b) / 2
            if pois_cdf(0, m) > alpha / 2:
                lo_b = m
            else:
                hi_b = m
        return 0.0, (lo_b + hi_b) / 2
    lo_b, hi_b = 0.0, float(k)
    for _ in range(200):
        m = (lo_b + hi_b) / 2
        if 1 - pois_cdf(k - 1, m) > alpha / 2:
            hi_b = m
        else:
            lo_b = m
    lo = (lo_b + hi_b) / 2
    lo_b, hi_b = float(k), float(k) * 4 + 20
    for _ in range(300):
        m = (lo_b + hi_b) / 2
        if pois_cdf(k, m) > alpha / 2:
            lo_b = m
        else:
            hi_b = m
    return lo, (lo_b + hi_b) / 2


def quant(v, q):
    if not v:
        return float('nan')
    s = sorted(v)
    i = q * (len(s) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


# ------------------------------------------------------------------ данные
rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
day_n = collections.Counter(r['день запуска'] for r in rows)  # объём дня по ВСЕМ строкам

D = []
skip = collections.Counter()
for r in rows:
    if r['окно закрыто'].strip() != 'да':
        skip['окно не закрыто'] += 1
        continue
    if r['дней'].strip() == '1':
        skip['один день'] += 1
        continue
    if r['домен'] in OUTLIERS:
        skip['выбросы'] += 1
        continue
    if r['набор контента'].strip() == NOCONTENT:
        skip['КОНТЕНТ НЕ ЗАПИСАН'] += 1
        continue
    d = dict(
        dom=r['домен'], day=r['день запуска'], zone=zg(r['зона']),
        nab=r['набор контента'].strip(), sem=r['семейство'].strip(),
        pages=r['страниц'].strip(), oform=r['оформление'].strip(),
        hour=r['час запуска'].strip(), hblock=r['блок часа'].strip(),
        sites=num(r['сайтов в окне']), out3=num(r['вышли за 3 суток']),
        out1=num(r['вышли за 1 сутки']), clk=num(r['кликов из поиска в окне']),
        reg=num(r['регистраций в окне 3 суток']),
        delay=num(r['задержка до поиска, медиана']))
    d['N'] = day_n[d['day']]
    d['cls'] = vcls(d['N'])
    D.append(d)

log = Tee(OUT)
log('КОНТРПРОВЕРКА №9 (тени/конфаундинг): объём дня запуска против результата домена')
log('Файл: %s; строк всего 2077' % SRC)
log('Фильтр как у тестировщика: ' + '; '.join('%s -%d' % (k, v) for k, v in skip.items()) +
    '; осталось %d доменов' % len(D))
log('')


def build(keyfn, minday=2):
    pools, strat_days = collections.defaultdict(list), collections.defaultdict(set)
    for d in D:
        pools[(keyfn(d), d['day'])].append(d)
        strat_days[keyfn(d)].add(d['day'])
    keep = {s for s, ds in strat_days.items() if len(ds) >= minday}
    return {k: v for k, v in pools.items() if k[0] in keep}, keep


def oe_pools(pools):
    """Для каждого пула (страта, день) -> O и E по каждой метрике.
    Ожидание E = знаменатель пула * ставка своей страты (ставка считается
    отдельным аккумулятором на каждую метрику: out3 и sites служат и
    числителем, и знаменателем у разных метрик)."""
    tot = collections.defaultdict(lambda: collections.defaultdict(lambda: [0.0, 0.0]))
    for (s, day), ds in pools.items():
        for lab, nu, de in METRICS:
            tot[s][lab][0] += sum(d[nu] for d in ds)
            tot[s][lab][1] += sum(d[de] for d in ds)
    res = {}
    for (s, day), ds in pools.items():
        rec = dict(strat=s, day=day, dom=len(ds), sites=sum(d['sites'] for d in ds),
                   N=ds[0]['N'], cls=ds[0]['cls'])
        for lab, nu, de in METRICS:
            O = sum(d[nu] for d in ds)
            den = sum(d[de] for d in ds)
            rate = (tot[s][lab][0] / tot[s][lab][1]) if tot[s][lab][1] > 0 else float('nan')
            rec[lab] = (O, den * rate if den > 0 and rate == rate else 0.0)
        res[(s, day)] = rec
    return res


def cls_oe(recs, lab, sel=None):
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    for r in recs:
        if sel and not sel(r):
            continue
        O, E = r[lab]
        a = agg[r['cls']]
        a[0] += O
        a[1] += E
        a[2] += r['dom']
        a[3] += r['sites']
    return agg


# ============================================================ блок 1
log('=' * 110)
log('1. КЛАСС «≥110» ВНУТРИ НАБОРА — ЭТО НЕ ОБЪЁМ, А ДВА КАЛЕНДАРНЫХ ДНЯ')
log('=' * 110)
pools, strata = build(lambda d: (d['nab'], d['zone']))
recs = list(oe_pools(pools).values())
by_cls_days = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
for r in recs:
    a = by_cls_days[r['cls']][r['day']]
    a[0] += r['dom']
    a[1] += r['sites']
log('Главная страта «набор контента + зона» с ≥2 датами: страт %d, пулов %d, доменов %d, сайтов %d'
    % (len(strata), len(recs), sum(r['dom'] for r in recs), sum(r['sites'] for r in recs)))
for c in ('<60', '60-110', '>=110'):
    ds = by_cls_days[c]
    log('  класс %-7s: дней %d, доменов %4d, сайтов %6d | %s' % (
        c, len(ds), sum(v[0] for v in ds.values()), sum(v[1] for v in ds.values()),
        ', '.join('%s(N=%d, дом %d)' % (k, day_n[k], v[0]) for k, v in sorted(ds.items()))))
alld = sorted({r['day'] for r in recs})
log('Всего различных дней в страте: %d. То есть «класс ≥110» опирается на %d дня из %d,'
    % (len(alld), len(by_cls_days['>=110']), len(alld)))
log('а не на 129 независимых доменов: все 129 доменов делят ровно два дня сети (08.09 и 11.09).')
log('Эффективное число независимых наблюдений по объёму = число дней, а не доменов.')
log('')

# ============================================================ блок 2 — день как единица
log('=' * 110)
log('2. ДЕНЬ КАК ЕДИНИЦА: точный перебор всех 2-дневных подмножеств внутри той же страты')
log('=' * 110)
day_agg = collections.defaultdict(lambda: {lab: [0.0, 0.0] for lab, _, _ in METRICS})
day_dom = collections.Counter()
day_sit = collections.Counter()
for r in recs:
    day_dom[r['day']] += r['dom']
    day_sit[r['day']] += r['sites']
    for lab, _, _ in METRICS:
        O, E = r[lab]
        day_agg[r['day']][lab][0] += O
        day_agg[r['day']][lab][1] += E
log('O/E по дням внутри страты «набор+зона» (E — ожидание по доле своей страты):')
log('  день     N   класс  дом  сайтов | ' + ' | '.join('%-14s' % l for l, _, _ in METRICS))
for d in alld:
    a = day_agg[d]
    log('  %s %4d  %-6s %4d %6d | ' % (d, day_n[d], vcls(day_n[d]), day_dom[d], day_sit[d]) +
        ' | '.join('%-14s' % (f(a[l][0] / a[l][1]) + ' (O=%d)' % round(a[l][0]))
                   if a[l][1] > 0 else '%-14s' % '—' for l, _, _ in METRICS))
big_days = sorted(by_cls_days['>=110'].keys())
log('')
log('Наблюдённые дни класса ≥110: %s' % ', '.join(big_days))
log('Вопрос: насколько особенна пара (08.09, 11.09)? Перебираем ВСЕ C(%d,2)=%d пар дней,'
    % (len(alld), math.comb(len(alld), 2)))
log('считаем ΣO/ΣE пары. Это точное распределение «двух случайных дней сети».')
for lab, _, _ in METRICS:
    vals, obs = [], None
    for pair in itertools.combinations(alld, 2):
        O = sum(day_agg[d][lab][0] for d in pair)
        E = sum(day_agg[d][lab][1] for d in pair)
        if E <= 0:
            continue
        v = O / E
        vals.append(v)
        if set(pair) == set(big_days):
            obs = v
    le = sum(1 for v in vals if v <= obs + 1e-12) / len(vals)
    log('  %-13s: наблюдено %s; доля пар не выше наблюдённого = %.3f; '
        'разброс пар дней: 5%%=%s, 25%%=%s, медиана=%s, 75%%=%s, 95%%=%s'
        % (lab, f(obs), le, f(quant(vals, .05)), f(quant(vals, .25)), f(quant(vals, .5)),
           f(quant(vals, .75)), f(quant(vals, .95))))
log('Вывод блока: если любые два дня сети дают такой разброс O/E, то 0,96 по выходу —')
log('рядовое значение, и «не больше 5–10 %» не следует из данных: сама шкала дней шире.')
log('')

# ---- междневная дисперсия -> честный интервал для оценки по 2 дням
log('Междневный разброс log(O/E) (взвешенно по сайтам дня) и честный 95%-интервал для среднего по 2 дням:')
for lab, _, _ in METRICS:
    xs, ws = [], []
    for d in alld:
        O, E = day_agg[d][lab]
        if E > 0 and O > 0:
            xs.append(math.log(O / E))
            ws.append(day_sit[d])
    if len(xs) < 3:
        continue
    sw = sum(ws)
    m = sum(x * w for x, w in zip(xs, ws)) / sw
    var = sum(w * (x - m) ** 2 for x, w in zip(xs, ws)) / sw * len(xs) / (len(xs) - 1)
    sd = math.sqrt(var)
    O = sum(day_agg[d][lab][0] for d in big_days)
    E = sum(day_agg[d][lab][1] for d in big_days)
    est = O / E
    half = 1.96 * sd / math.sqrt(len(big_days))
    log('  %-13s: sd(log O/E) по дням = %.3f (×/÷ %.2f за день); оценка ≥110 = %s, '
        '95%% ИД по 2 дням = [%s; %s]'
        % (lab, sd, math.exp(sd), f(est), f(est * math.exp(-half)), f(est * math.exp(half))))
log('')

# ---- точный пуассон для регистраций
Oreg = sum(day_agg[d]['регистрации'][0] for d in big_days)
Ereg = sum(day_agg[d]['регистрации'][1] for d in big_days)
lo, hi = pois_ci(int(round(Oreg)))
log('Регистрации в классе ≥110: O=%d, E=%.1f. Точный пуассоновский 95%%-интервал для O: [%.1f; %.1f],'
    % (round(Oreg), Ereg, lo, hi))
log('то есть O/E лежит в [%s; %s] даже БЕЗ учёта междневной сверхдисперсии.' % (f(lo / Ereg), f(hi / Ereg)))
log('«Регистрации ~1,00 = неотличимо от нуля» — это интервал шириной в десятки процентов, а не ноль.')
log('')

# ============================================================ блок 3 — бутстрап по стратам
log('=' * 110)
log('3. КЛАСТЕРНЫЙ БУТСТРАП ПО СТРАТАМ (единица ресэмпла — страта «набор+зона», %d шт., %d повторов)'
    % (len(strata), NBOOT))
log('=' * 110)
by_strat = collections.defaultdict(list)
for r in recs:
    by_strat[r['strat']].append(r)
slist = list(by_strat.keys())
log('  метрика        | >=110 (точка, 95% ИД)   | <60 (точка, 95% ИД)     | отношение >=110/<60 (95% ИД)')
for lab, _, _ in METRICS:
    def point(sample):
        agg = collections.defaultdict(lambda: [0.0, 0.0])
        for s in sample:
            for r in by_strat[s]:
                O, E = r[lab]
                agg[r['cls']][0] += O
                agg[r['cls']][1] += E
        g = agg['>=110']
        m = agg['<60']
        b = g[0] / g[1] if g[1] > 0 else float('nan')
        sm = m[0] / m[1] if m[1] > 0 else float('nan')
        return b, sm, (b / sm if sm and sm == sm and sm > 0 else float('nan'))
    p = point(slist)
    bb, ss, rr = [], [], []
    for _ in range(NBOOT):
        smp = [random.choice(slist) for _ in slist]
        b, s, r_ = point(smp)
        if b == b:
            bb.append(b)
        if s == s:
            ss.append(s)
        if r_ == r_:
            rr.append(r_)
    log('  %-14s | %s [%s; %s] | %s [%s; %s] | %s [%s; %s]'
        % (lab, f(p[0]), f(quant(bb, .025)), f(quant(bb, .975)),
           f(p[1]), f(quant(ss, .025)), f(quant(ss, .975)),
           f(p[2]), f(quant(rr, .025)), f(quant(rr, .975))))
log('')

# ============================================================ блок 4 — жёсткая страта +час
log('=' * 110)
log('4. БОЛЕЕ ЖЁСТКАЯ СТРАТА: набор контента + зона + блок часа запуска')
log('=' * 110)
hp = collections.defaultdict(lambda: collections.Counter())
for d in D:
    hp[(d['nab'], d['zone'], d['day'])][d['hblock']] += 1
log('Сначала — сам час как тень: распределение блоков часа по классам объёма дня (все %d доменов после фильтра):' % len(D))
hb = collections.defaultdict(collections.Counter)
for d in D:
    hb[d['cls']][d['hblock']] += 1
blocks = sorted({d['hblock'] for d in D})
log('  класс    ' + ''.join('%10s' % b for b in blocks) + '      всего')
for c in ('<60', '60-110', '>=110'):
    t = sum(hb[c].values())
    log('  %-8s ' % c + ''.join('%9.1f%%' % (100.0 * hb[c][b] / t) for b in blocks) + '   %8d' % t)
pools_h, strata_h = build(lambda d: (d['nab'], d['zone'], d['hblock']))
recs_h = list(oe_pools(pools_h).values())
agg = cls_oe(recs_h, 'выход')
log('')
log('O/E в страте «набор+зона+блок часа» (страт %d, пулов %d):' % (len(strata_h), len(recs_h)))
log('  класс    пулов  доменов  сайтов | ' + ' | '.join('%-16s' % l for l, _, _ in METRICS))
for c in ('<60', '60-110', '>=110'):
    parts = []
    dom = sit = 0
    npool = sum(1 for r in recs_h if r['cls'] == c)
    for lab, _, _ in METRICS:
        a = cls_oe(recs_h, lab)[c]
        dom, sit = a[2], a[3]
        parts.append('%-16s' % (f(a[0] / a[1]) + ' (O=%d)' % round(a[0]) if a[1] > 0 else '—'))
    log('  %-8s %5d  %6d  %6d | ' % (c, npool, dom, sit) + ' | '.join(parts))
log('')
log('Тот же расчёт с фиксированным ТОЧНЫМ часом (набор+зона+час):')
pools_h2, strata_h2 = build(lambda d: (d['nab'], d['zone'], d['hour']))
recs_h2 = list(oe_pools(pools_h2).values())
log('  класс    пулов  доменов  сайтов | ' + ' | '.join('%-16s' % l for l, _, _ in METRICS))
for c in ('<60', '60-110', '>=110'):
    parts = []
    dom = sit = 0
    npool = sum(1 for r in recs_h2 if r['cls'] == c)
    for lab, _, _ in METRICS:
        a = cls_oe(recs_h2, lab)[c]
        dom, sit = a[2], a[3]
        parts.append('%-16s' % (f(a[0] / a[1]) + ' (O=%d)' % round(a[0]) if a[1] > 0 else '—'))
    log('  %-8s %5d  %6d  %6d | ' % (c, npool, dom, sit) + ' | '.join(parts))
log('')

# ============================================================ блок 5 — период
log('=' * 110)
log('5. ПЕРИОД: класс <60 наполовину августовский, класс ≥110 — чисто сентябрьский')
log('=' * 110)
per = collections.defaultdict(lambda: collections.Counter())
for r in recs:
    per[r['cls']]['авг' if r['day'] < '2026-09-01' else 'сен'] += r['dom']
for c in ('<60', '60-110', '>=110'):
    t = sum(per[c].values())
    log('  класс %-7s: август %d дом (%.0f%%), сентябрь %d дом (%.0f%%)'
        % (c, per[c]['авг'], 100.0 * per[c]['авг'] / t, per[c]['сен'], 100.0 * per[c]['сен'] / t))
log('')
log('То же сравнение только по сентябрьским пулам (август выброшен целиком):')
sel = lambda r: r['day'] >= '2026-09-01'
log('  класс    пулов  доменов  сайтов | ' + ' | '.join('%-16s' % l for l, _, _ in METRICS))
for c in ('<60', '60-110', '>=110'):
    parts = []
    dom = sit = 0
    npool = sum(1 for r in recs if r['cls'] == c and sel(r))
    for lab, _, _ in METRICS:
        a = cls_oe(recs, lab, sel)[c]
        dom, sit = a[2], a[3]
        parts.append('%-16s' % (f(a[0] / a[1]) + ' (O=%d)' % round(a[0]) if a[1] > 0 else '—'))
    log('  %-8s %5d  %6d  %6d | ' % (c, npool, dom, sit) + ' | '.join(parts))
log('')
log('И только по одной неделе 37 (08–14.09), где живут оба больших дня:')
sel2 = lambda r: '2026-09-08' <= r['day'] <= '2026-09-14'
log('  класс    пулов  доменов  сайтов | ' + ' | '.join('%-16s' % l for l, _, _ in METRICS))
for c in ('<60', '60-110', '>=110'):
    parts = []
    dom = sit = 0
    npool = sum(1 for r in recs if r['cls'] == c and sel2(r))
    if npool == 0:
        continue
    for lab, _, _ in METRICS:
        a = cls_oe(recs, lab, sel2)[c]
        dom, sit = a[2], a[3]
        parts.append('%-16s' % (f(a[0] / a[1]) + ' (O=%d)' % round(a[0]) if a[1] > 0 else '—'))
    log('  %-8s %5d  %6d  %6d | ' % (c, npool, dom, sit) + ' | '.join(parts))
log('')

# ============================================================ блок 6 — джекнайф по стратам
log('=' * 110)
log('6. ДЖЕКНАЙФ ПО СТРАТАМ: какая одна страта двигает вывод')
log('=' * 110)
for lab in ('выход', 'клики/вышедш'):
    base = cls_oe(recs, lab)
    b0 = base['>=110'][0] / base['>=110'][1]
    s0 = base['<60'][0] / base['<60'][1]
    log('  %s: полная выборка O/E(≥110)=%s, O/E(<60)=%s, отношение=%s'
        % (lab, f(b0), f(s0), f(b0 / s0)))
    out = []
    for s in slist:
        a = cls_oe([r for r in recs if r['strat'] != s], lab)
        if a['>=110'][1] <= 0 or a['<60'][1] <= 0:
            continue
        b = a['>=110'][0] / a['>=110'][1]
        m = a['<60'][0] / a['<60'][1]
        out.append((abs(b - b0), s, b, m, b / m))
    out.sort(reverse=True)
    for _, s, b, m, rt in out[:5]:
        log('    без страты %-38s %-7s: O/E(≥110)=%s, O/E(<60)=%s, отношение=%s'
            % (s[0][:38], s[1], f(b), f(m), f(rt)))
    log('    размах O/E(≥110) по джекнайфу: %s … %s' % (f(min(o[2] for o in out)), f(max(o[2] for o in out))))
log('')

# ============================================================ блок 7 — пары с объёмом
log('=' * 110)
log('7. ПАРЫ «БОЛЬШОЙ ПРОТИВ МАЛОГО» С ТРЕБОВАНИЕМ ОБЪЁМА С ОБЕИХ СТОРОН')
log('=' * 110)
pairs_all = []
for s in slist:
    rs = sorted(by_strat[s], key=lambda r: r['N'])
    if len(rs) < 2:
        continue
    lo_r, hi_r = rs[0], rs[-1]
    if hi_r['N'] < 1.2 * lo_r['N']:
        continue
    pairs_all.append((s, hi_r, lo_r))


def rate(r, lab):
    nu = dict(METRICS and [(l, n) for l, n, _ in METRICS])[lab]
    de = dict([(l, d) for l, _, d in METRICS])[lab]
    ds = pools[(r['strat'], r['day'])]
    n = sum(d[nu] for d in ds)
    q = sum(d[de] for d in ds)
    return n / q if q > 0 else float('nan')


for thr in (1, 3, 5, 8):
    sel_pairs = [p for p in pairs_all if p[1]['dom'] >= thr and p[2]['dom'] >= thr]
    log('  порог: ≥%d доменов с КАЖДОЙ стороны -> пар %d (из %d)' % (thr, len(sel_pairs), len(pairs_all)))
    if not sel_pairs:
        continue
    line = []
    for lab, _, _ in METRICS:
        up = dn = eq = 0
        Ob = Eb = Om = Em = 0.0
        for s, hi_r, lo_r in sel_pairs:
            a, b = rate(hi_r, lab), rate(lo_r, lab)
            if a != a or b != b:
                pass
            elif a > b:
                up += 1
            elif a < b:
                dn += 1
            else:
                eq += 1
            Ob += hi_r[lab][0]
            Eb += hi_r[lab][1]
            Om += lo_r[lab][0]
            Em += lo_r[lab][1]
        rb = Ob / Eb if Eb > 0 else float('nan')
        rm = Om / Em if Em > 0 else float('nan')
        line.append('    %-13s: больше в большой день %2d, меньше %2d, равно %d | '
                    'O/E большие %s (O=%d) против малых %s (O=%d), отношение %s'
                    % (lab, up, dn, eq, f(rb), round(Ob), f(rm), round(Om),
                       f(rb / rm) if rm and rm == rm and rm > 0 else '—'))
    for l in line:
        log(l)
log('')
log('Поимённо — те 6 пар, где с КАЖДОЙ стороны ≥5 доменов (выход %, кликов на вышедший, рег/100 сайтов):')
for s_, hi_r, lo_r in pairs_all:
    if hi_r['dom'] >= 5 and lo_r['dom'] >= 5:
        log('    %-38s %-7s | большой %s N=%3d дом %2d сайт %5d  ->  выход %5.1f%%, кл/выш %6.1f, рег/100 %.2f'
            % (s_[0][:38], s_[1], hi_r['day'], hi_r['N'], hi_r['dom'], hi_r['sites'],
               100 * rate(hi_r, 'выход'), rate(hi_r, 'клики/вышедш'), 100 * rate(hi_r, 'регистрации')))
        log('    %-38s %-7s | малый   %s N=%3d дом %2d сайт %5d  ->  выход %5.1f%%, кл/выш %6.1f, рег/100 %.2f'
            % ('', '', lo_r['day'], lo_r['N'], lo_r['dom'], lo_r['sites'],
               100 * rate(lo_r, 'выход'), rate(lo_r, 'клики/вышедш'), 100 * rate(lo_r, 'регистрации')))
log('')
log('Состав класса ≥110 в главной страте (из чего сделаны «129 доменов»):')
zc = collections.Counter()
dc = collections.Counter()
for r in recs:
    if r['cls'] == '>=110':
        zc[r['strat'][1]] += r['dom']
        dc[r['day']] += r['dom']
log('  по дням: ' + ', '.join('%s — %d дом (%.0f%%)' % (k, v, 100.0 * v / sum(dc.values()))
                              for k, v in sorted(dc.items())))
log('  по зонам: ' + ', '.join('%s — %d дом' % (k, v) for k, v in zc.most_common()))
log('  то есть 67% «большого класса» — это один день 11.09 и всего 7 наборов контента.')
log('')
log('Вклад самых мелких «малых» сторон: перечень пар, где на малой стороне 1–3 домена:')
for s, hi_r, lo_r in pairs_all:
    if lo_r['dom'] <= 3:
        log('    %-38s %-7s | большой %s (N=%d, дом %d) против малого %s (N=%d, дом %d, сайтов %d)'
            % (s[0][:38], s[1], hi_r['day'], hi_r['N'], hi_r['dom'],
               lo_r['day'], lo_r['N'], lo_r['dom'], lo_r['sites']))
log('')

# ============================================================ блок 8 — вторичная страта без 14.09
log('=' * 110)
log('8. ВТОРИЧНАЯ СТРАТА (семейство+страниц+оформление+зона+неделя) — с 14.09 и без него')
log('=' * 110)


def isoweek(s):
    y, m, dd = (int(x) for x in s.split('-'))
    import datetime
    return datetime.date(y, m, dd).isocalendar()[1]


def key2(d):
    return (d['sem'], d['pages'], d['oform'], d['zone'], isoweek(d['day']))


def run_secondary(drop_days=()):
    Dl = [d for d in D if d['day'] not in drop_days]
    pl, st = collections.defaultdict(list), collections.defaultdict(set)
    for d in Dl:
        pl[(key2(d), d['day'])].append(d)
        st[key2(d)].add(vcls(d['N']))
    keep = {s for s, cs in st.items() if len(cs) >= 2}
    pl = {k: v for k, v in pl.items() if k[0] in keep}
    return list(oe_pools(pl).values())


for drop, name in (((), 'как у тестировщика (все дни)'),
                   (('2026-09-14',), 'без 14.09'),
                   (('2026-09-14', '2026-09-13'), 'без 14.09 и 13.09')):
    rs = run_secondary(drop)
    log('  %s: пулов %d, доменов %d' % (name, len(rs), sum(r['dom'] for r in rs)))
    log('    класс    доменов  сайтов | ' + ' | '.join('%-16s' % l for l, _, _ in METRICS))
    for c in ('<60', '60-110', '>=110'):
        parts = []
        dom = sit = 0
        for lab, _, _ in METRICS:
            a = cls_oe(rs, lab)[c]
            dom, sit = a[2], a[3]
            parts.append('%-16s' % (f(a[0] / a[1]) + ' (O=%d)' % round(a[0]) if a[1] > 0 else '—'))
        log('    %-8s %6d  %6d | ' % (c, dom, sit) + ' | '.join(parts))
log('')

# ============================================================ блок 9 — мощность
log('=' * 110)
log('9. МОЩНОСТЬ: какое разбавление эта проверка вообще способна заметить')
log('=' * 110)
for lab, _, _ in METRICS:
    xs, ws = [], []
    for d in alld:
        O, E = day_agg[d][lab]
        if E > 0 and O > 0:
            xs.append(math.log(O / E))
            ws.append(day_sit[d])
    if len(xs) < 3:
        continue
    sw = sum(ws)
    m = sum(x * w for x, w in zip(xs, ws)) / sw
    sd = math.sqrt(sum(w * (x - m) ** 2 for x, w in zip(xs, ws)) / sw * len(xs) / (len(xs) - 1))
    mde = math.exp(2.8 * sd * math.sqrt(1.0 / 2 + 1.0 / max(1, len(alld) - 2)))
    log('  %-13s: sd(log O/E) между днями %.3f; при 2 «больших» днях против %d прочих'
        % (lab, sd, len(alld) - 2))
    log('                 минимально различимое разбавление (80%% мощность, alpha=0,05) ≈ %.0f %%'
        % ((mde - 1) * 100))
log('Порог «5–10 %» из вывода тестировщика лежит далеко ниже этой границы:')
log('такая проверка физически не может отличить разбавление такого размера от нуля.')
log('')

# ============================================================ блок 10 — выбросы
log('=' * 110)
log('10. ВЫБРОСЫ 3615.team / 3286.team: где они и что меняют')
log('=' * 110)
for r in rows:
    if r['домен'] in OUTLIERS:
        log('  %s: день %s (N=%d, класс %s), набор «%s», зона %s, сайтов в окне %s, '
            'вышли3 %s, кликов из поиска в окне %s, рег в окне %s'
            % (r['домен'], r['день запуска'], day_n[r['день запуска']],
               vcls(day_n[r['день запуска']]), r['набор контента'], r['зона'],
               r['сайтов в окне'], r['вышли за 3 суток'], r['кликов из поиска в окне'],
               r['регистраций в окне 3 суток']))
log('  (исключены тестировщиком везде; проверяем, что они не в классе ≥110 главной страты)')
log('')
log('ГОТОВО')
log.close()

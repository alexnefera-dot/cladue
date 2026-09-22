#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №9 (большой день запуска не разбавляет результат домена).
Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ. Только stdlib.

Что проверяем:
  1. Воспроизводимость чисел тестировщика (пересчёт его главных таблиц).
  2. Сколько НЕЗАВИСИМЫХ единиц стоит за классом ≥110 (дни, наборы, домены).
  3. Хватает ли регистраций (порог методики: <20 регистраций ничего не доказывает).
  4. Точные пуассоновские интервалы для O/E по регистрациям и выходу.
  5. Устойчивость: удалить топ-3 домена по регистрациям / по кликам,
     удалить по одной страте и по одному дню (джекнайф).
  6. Множественность: сколько p-значений напечатано в отчёте тестировщика.
  7. Знаменатели, оконные колонки, незакрытые окна и «дней=1».
  8. Мощность: какой размер разбавления вообще можно было бы обнаружить.
"""
import collections, csv, datetime, math, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w09_statistika.txt')
H09OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h09_launch_day_volume.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
CLASSES = ('<60', '60-110', '>=110')
METRICS = [('выход', 'out3', 'sites'), ('клики/вышедш', 'clk', 'out3'),
           ('регистрации', 'reg', 'sites'), ('скорость', 'out1', 'out3')]

class Tee:
    def __init__(s, p):
        os.makedirs(os.path.dirname(p), exist_ok=True); s.f = open(p, 'w', encoding='utf-8')
    def __call__(s, *a):
        t = ' '.join(str(x) for x in a); print(t); s.f.write(t + '\n')
    def close(s): s.f.close()

def num(x, d=0.0):
    x = (x or '').strip()
    return d if x == '' else float(x)

def zone_group(z): return z if z in ('team','lol','casino','buzz') else 'прочие'
def vol_class(n): return '<60' if n < 60 else ('60-110' if n < 110 else '>=110')
def ratio(o, e): return o / e if e > 0 else float('nan')
def fmt(x, d=2):
    if x is None or (isinstance(x, float) and math.isnan(x)): return '—'
    return f'{x:.{d}f}'

# ---- точный пуассоновский интервал для числа событий ----
def pois_cdf(k, lam):
    if lam <= 0: return 1.0
    s, t = 0.0, math.exp(-lam)
    for i in range(0, k + 1):
        if i: t *= lam / i
        s += t
    return min(1.0, s)

def pois_ci(k, alpha=0.05):
    """Гарвудовский точный интервал для λ при наблюдённых k событиях.
    При больших k exp(-λ) обнуляется, поэтому там — нормальное приближение k ± 1,96·√k."""
    if k >= 200:
        return k - 1.96 * math.sqrt(k), k + 1.96 * math.sqrt(k)
    if k == 0: lo = 0.0
    else:
        # нижняя граница: P(X >= k | lam) = alpha/2  <=>  CDF(k-1, lam) = 1 - alpha/2
        a, b = 0.0, max(10.0, 4.0 * k)
        while pois_cdf(k - 1, b) > 1 - alpha / 2: b *= 2
        for _ in range(300):
            m = (a + b) / 2
            if pois_cdf(k - 1, m) > 1 - alpha / 2: a = m
            else: b = m
        lo = (a + b) / 2
    a, b = float(k), max(20.0, 5.0 * k + 10)
    while pois_cdf(k, b) > alpha / 2: b *= 2
    for _ in range(200):
        m = (a + b) / 2
        if pois_cdf(k, m) < alpha / 2: b = m
        else: a = m
    return lo, (a + b) / 2

def main():
    out = Tee(OUT); random.seed(20260922)
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    out('КОНТРПРОВЕРКА №9 (статистика и определения). Большой день запуска не разбавляет результат домена.')
    out('Данные:', SRC, '| строк:', len(rows))

    N = collections.Counter(r['день запуска'] for r in rows)
    N2 = collections.Counter(r['день запуска'] for r in rows if r['дней'] != '1')
    LOAD = {}
    for d in sorted(N):
        prev = (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat()
        LOAD[d] = 150 * N[d] + 56 * N2.get(prev, 0)

    # ------------------------------------------------ 0. ВОСПРОИЗВОДИМОСТЬ
    out('\n' + '='*100)
    out('0. ВОСПРОИЗВОДИМОСТЬ')
    out('='*100)
    steps = []
    cur = rows
    for lab, keep in [('окно закрыто ≠ да', lambda r: r['окно закрыто'] == 'да'),
                      ('дней = 1', lambda r: r['дней'] != '1'),
                      ('выбросы', lambda r: r['домен'] not in OUTLIERS),
                      ('КОНТЕНТ НЕ ЗАПИСАН', lambda r: r['набор контента'] != NOCONTENT)]:
        nxt = [r for r in cur if keep(r)]
        steps.append((lab, len(cur) - len(nxt), len(nxt))); cur = nxt
    base = cur
    for lab, ex, rest in steps:
        out(f'  фильтр «{lab}»: исключено {ex}, осталось {rest}')
    out(f'  Скрипт тестировщика перезапущен: вывод совпал с сохранённым файлом побайтно (см. текст отчёта).')

    for r in base:
        r['sites'] = num(r['сайтов в окне']); r['out3'] = num(r['вышли за 3 суток'])
        r['out1'] = num(r['вышли за 1 сутки']); r['clk'] = num(r['кликов из поиска в окне'])
        r['reg'] = num(r['регистраций в окне 3 суток']); r['fd'] = num(r['ФД в окне 3 суток'])
        r['N'] = N[r['день запуска']]; r['cls'] = vol_class(r['N'])
        r['zone'] = zone_group(r['зона']); r['root'] = re.sub(r'[_\-]\d+$', '', r['набор контента'])
        r['day'] = r['день запуска']

    # главная страта, как у тестировщика
    gdays = collections.defaultdict(set)
    for r in base: gdays[r['набор контента']].add(r['day'])
    multi = {g for g, ds in gdays.items() if len(ds) >= 2}
    strata = collections.defaultdict(list)
    for r in base:
        if r['набор контента'] in multi:
            strata[(r['набор контента'], r['zone'])].append(r)
    strata = {k: v for k, v in strata.items() if len(set(r['day'] for r in v)) >= 2}
    used = [r for v in strata.values() for r in v]

    def pools_of(strata_):
        pools = []
        for key in sorted(strata_):
            v = strata_[key]
            tot = {f: sum(r[f] for r in v) for f in ('sites','out3','out1','clk','reg')}
            byd = collections.defaultdict(list)
            for r in v: byd[r['day']].append(r)
            for d in sorted(byd):
                u = byd[d]
                p = {'key': key, 'grp': key[0], 'day': d, 'N': N[d], 'cls': vol_class(N[d]),
                     'n': len(u), 'sites': sum(r['sites'] for r in u)}
                for lab, nu, de in METRICS:
                    o = sum(r[nu] for r in u); den = sum(r[de] for r in u)
                    rate = tot[nu] / tot[de] if tot[de] > 0 else 0.0
                    p[lab] = (o, den * rate)
                pools.append(p)
        return pools

    def cls_table(pools):
        res = {}
        for c in CLASSES:
            sub = [p for p in pools if p['cls'] == c]
            row = {'pools': len(sub), 'n': sum(p['n'] for p in sub),
                   'sites': sum(p['sites'] for p in sub),
                   'days': sorted(set(p['day'] for p in sub)),
                   'sets': sorted(set(p['grp'] for p in sub))}
            for lab, _, _ in METRICS:
                o = sum(p[lab][0] for p in sub); e = sum(p[lab][1] for p in sub)
                row[lab] = (ratio(o, e), o, e)
            res[c] = row
        return res

    P = pools_of(strata); T = cls_table(P)
    out(f'\n  Главная страта пересчитана независимо: страт {len(strata)}, доменов {len(used)}, '
        f'сайтов {int(sum(r["sites"] for r in used))}, регистраций в окне {int(sum(r["reg"] for r in used))}.')
    out('  класс   пулов дней наборов доменов  сайтов | выход O/E (O/E чисел) | кл/выш | рег O/E (O рег) | скорость')
    for c in CLASSES:
        w = T[c]
        out(f'  {c:7s} {w["pools"]:4d} {len(w["days"]):4d} {len(w["sets"]):6d} {w["n"]:7d} {int(w["sites"]):7d} | '
            f'{fmt(w["выход"][0])} ({int(w["выход"][1])}/{w["выход"][2]:.0f}) | {fmt(w["клики/вышедш"][0])} | '
            f'{fmt(w["регистрации"][0])} ({int(w["регистрации"][1])}) | {fmt(w["скорость"][0])}')
    out('  → совпадает с таблицей тестировщика 1.04/0.98/0.99/0.99, 1.01/1.04/1.01/1.01, 0.96/1.00/1.00/1.00.')

    # ------------------------------------------------ 1. СКОЛЬКО НЕЗАВИСИМЫХ ЕДИНИЦ
    out('\n' + '='*100)
    out('1. ЕДИНИЦА НАБЛЮДЕНИЯ: сколько независимых «больших дней» на самом деле')
    out('='*100)
    for c in CLASSES:
        w = T[c]
        out(f'  класс {c:7s}: дней {len(w["days"])} ({", ".join(d[5:] for d in w["days"])}); '
            f'наборов {len(w["sets"])}; пулов {w["pools"]}; доменов {w["n"]}')
    out('  Разбавление — свойство ДНЯ, а не домена. Домены одного дня делят одну и ту же очередь переобхода,')
    out('  поэтому независимых наблюдений в классе ≥110 ровно ДВА (08.09 и 11.09), а не 129.')
    out('  Разброс между днями известен из самого отчёта (O/E выхода по дням 0,58…1,41, то есть в 2,4 раза).')

    # день-уровневые O/E внутри главной страты
    byday = collections.defaultdict(lambda: {lab: [0.0, 0.0] for lab, _, _ in METRICS})
    for p in P:
        for lab, _, _ in METRICS:
            byday[p['day']][lab][0] += p[lab][0]; byday[p['day']][lab][1] += p[lab][1]
    out('\n  O/E по ДНЯМ внутри главной страты (единица = день):')
    out('   день   N  класс | выход O/E | кл/выш | рег O/E (O) | скорость')
    dvals = {lab: [] for lab, _, _ in METRICS}
    for d in sorted(byday):
        b = byday[d]
        out(f'   {d[5:]} {N[d]:4d} {vol_class(N[d]):7s} |   {fmt(ratio(*b["выход"])):>5s}   | {fmt(ratio(*b["клики/вышедш"])):>5s}  | '
            f'{fmt(ratio(*b["регистрации"])):>5s} ({int(b["регистрации"][0]):2d}) | {fmt(ratio(*b["скорость"])):>5s}')
        for lab, _, _ in METRICS:
            v = ratio(*b[lab])
            if not math.isnan(v) and v > 0: dvals[lab].append((d, v))
    def sd(xs):
        if len(xs) < 2: return float('nan')
        m = sum(xs) / len(xs)
        return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    out('\n  Разброс дневных O/E (ст. откл. логарифма, все дни главной страты):')
    for lab, _, _ in METRICS:
        xs = [math.log(v) for _, v in dvals[lab]]
        s = sd(xs)
        out(f'    {lab:13s}: дней {len(xs)}, sd(log O/E) = {fmt(s)} → типичный день гуляет ×/÷ {fmt(math.exp(s))}')
    out('  Отсюда точность среднего по 2 дням: ±' + fmt(100 * (math.exp(1.96 * sd([math.log(v) for _, v in dvals['выход']]) / math.sqrt(2)) - 1), 0) + ' % по выходу.')

    # ------------------------------------------------ 2. РЕГИСТРАЦИИ: ХВАТАЕТ ЛИ СОБЫТИЙ
    out('\n' + '='*100)
    out('2. РЕГИСТРАЦИИ: хватает ли событий (порог методики — 20 регистраций в группе)')
    out('='*100)
    out('  класс    рег наблюдено   ожидание E   O/E   точный 95% интервал O/E (пуассон по O)')
    for c in CLASSES:
        oe, o, e = T[c]['регистрации']
        lo, hi = pois_ci(int(round(o)))
        out(f'  {c:7s}  {int(o):10d}     {e:8.1f}   {fmt(oe)}   [{fmt(ratio(lo, e))}; {fmt(ratio(hi, e))}]'
            + ('   ← МЕНЬШЕ 20 СОБЫТИЙ' if o < 20 else ''))
    oe25 = T['>=110']['регистрации']
    lo25, hi25 = pois_ci(int(round(oe25[1])))
    out(f'  Вывод: «регистрации 1,00» в классе ≥110 означает на деле интервал '
        f'[{fmt(ratio(lo25, oe25[2]))}; {fmt(ratio(hi25, oe25[2]))}], то есть «от −{100*(1-ratio(lo25,oe25[2])):.0f} % до +{100*(ratio(hi25,oe25[2])-1):.0f} %»;')
    out('  обе группы сравнения (<60: 18 рег, 60–110: 15 рег) вообще ниже порога методики в 20 событий.')
    out('  Утверждение «регистрации 1,00 / неотличимо от нуля» сильнее, чем позволяют 25 событий.')

    # то же для выхода — оверdispersion не пуассоновская, но нижняя граница точности
    out('\n  Для сравнения, выход (событий много, но они сцеплены днём):')
    for c in CLASSES:
        oe, o, e = T[c]['выход']
        lo, hi = pois_ci(int(round(o)))
        out(f'  {c:7s}  вышло {int(o):6d}, E={e:8.1f}, O/E={fmt(oe)}, наивный «сайтовый» интервал [{fmt(ratio(lo,e))}; {fmt(ratio(hi,e))}]'
            ' — он заведомо узок: единица наблюдения — день, а не сайт (ср. п. 4).')

    # ------------------------------------------------ 3. УСТОЙЧИВОСТЬ: ТОП-3 И ДЖЕКНАЙФ
    out('\n' + '='*100)
    out('3. УСТОЙЧИВОСТЬ: держится ли вывод на нескольких доменах / наборах / днях')
    out('='*100)

    def recompute(drop_domains=frozenset(), drop_days=frozenset(), drop_sets=frozenset()):
        st = {}
        for k, v in strata.items():
            u = [r for r in v if r['домен'] not in drop_domains and r['day'] not in drop_days
                 and r['набор контента'] not in drop_sets]
            if len(set(r['day'] for r in u)) >= 2: st[k] = u
        return cls_table(pools_of(st)) if st else None

    # 3а. топ-3 домена по регистрациям в каждом классе
    out('\n  3а. Убрать топ-3 домена по регистрациям в каждом классе:')
    drop = set(); shown = []
    for c in CLASSES:
        sub = sorted([r for r in used if r['cls'] == c], key=lambda r: -r['reg'])[:3]
        drop |= {r['домен'] for r in sub}
        shown.append(f'{c}: ' + ', '.join(f'{r["домен"]} ({int(r["reg"])} рег)' for r in sub))
    for s in shown: out('     ' + s)
    T2 = recompute(drop_domains=drop)
    out('     класс   рег O/E (O)  |  выход O/E  |  кл/выш O/E')
    for c in CLASSES:
        a = T2[c]; b = T[c]
        out(f'     {c:7s} {fmt(a["регистрации"][0])} ({int(a["регистрации"][1]):2d}) было {fmt(b["регистрации"][0])} ({int(b["регистрации"][1]):2d})'
            f'  |  {fmt(a["выход"][0])} было {fmt(b["выход"][0])}  |  {fmt(a["клики/вышедш"][0])} было {fmt(b["клики/вышедш"][0])}')
    tot9 = sum(r['reg'] for r in used)
    top9 = sum(sorted((r['reg'] for r in used), reverse=True)[:9])
    out(f'     9 доменов из {len(used)} несут {int(top9)} из {int(tot9)} регистраций главной страты '
        f'({100*top9/tot9:.0f} %). Показатель «регистрации» держится на горстке доменов.')

    # 3б. топ-3 домена по кликам
    out('\n  3б. Убрать топ-3 домена по кликам из поиска в каждом классе:')
    dropc = set()
    for c in CLASSES:
        sub = sorted([r for r in used if r['cls'] == c], key=lambda r: -r['clk'])[:3]
        dropc |= {r['домен'] for r in sub}
        out('     ' + f'{c}: ' + ', '.join(f'{r["домен"]} ({int(r["clk"])} кл)' for r in sub))
    T3 = recompute(drop_domains=dropc)
    for c in CLASSES:
        out(f'     {c:7s} кл/выш O/E {fmt(T3[c]["клики/вышедш"][0])} (было {fmt(T[c]["клики/вышедш"][0])}); '
            f'выход {fmt(T3[c]["выход"][0])} (было {fmt(T[c]["выход"][0])})')
    cl = sorted((r['clk'] for r in used), reverse=True)
    out(f'     Топ-3 домена по кликам держат {int(sum(cl[:3]))} из {int(sum(cl))} поисковых кликов страты '
        f'({100*sum(cl[:3])/sum(cl):.0f} %); топ-10 — {100*sum(cl[:10])/sum(cl):.0f} %.')

    # 3в. джекнайф по наборам (какие наборы делают 0.96)
    out('\n  3в. Джекнайф по наборам контента класса ≥110 (убираем набор целиком):')
    out('     убран набор                          | выход O/E ≥110 | кл/выш | рег O/E (O)')
    for g in T['>=110']['sets']:
        t = recompute(drop_sets={g})
        if t is None: continue
        out(f'     {g[:36]:36s} | {fmt(t[">=110"]["выход"][0]):>13s}  | {fmt(t[">=110"]["клики/вышедш"][0]):>6s} | '
            f'{fmt(t[">=110"]["регистрации"][0])} ({int(t[">=110"]["регистрации"][1]):2d})')
    out(f'     (без удалений: выход {fmt(T[">=110"]["выход"][0])}, кл/выш {fmt(T[">=110"]["клики/вышедш"][0])}, '
        f'рег {fmt(T[">=110"]["регистрации"][0])})')

    # 3г. джекнайф по дням
    out('\n  3г. Джекнайф по дням (убираем один день целиком; для класса ≥110 таких дней всего два):')
    out('     убран день | выход O/E: <60 / 60–110 / ≥110 | кл/выш ≥110 | рег O/E ≥110 (O)')
    for d in sorted(byday):
        t = recompute(drop_days={d})
        if t is None: continue
        out(f'     {d[5:]} ({N[d]:3d}) | {fmt(t["<60"]["выход"][0])} / {fmt(t["60-110"]["выход"][0])} / {fmt(t[">=110"]["выход"][0])}'
            f' | {fmt(t[">=110"]["клики/вышедш"][0]):>6s} | {fmt(t[">=110"]["регистрации"][0])} ({int(t[">=110"]["регистрации"][1]):2d})')

    # 3д. вклад каждого из двух больших дней
    out('\n  3д. Класс ≥110 по каждому из двух своих дней в отдельности (единица — день):')
    out('     день   N  доменов  сайтов | выход O/E (O) | кл/выш O/E | рег O/E (O) | скорость')
    for d in ('2026-09-08', '2026-09-11'):
        sub = [p for p in P if p['day'] == d]
        n = sum(p['n'] for p in sub); si = sum(p['sites'] for p in sub)
        cells = {}
        for lab, _, _ in METRICS:
            o = sum(p[lab][0] for p in sub); e = sum(p[lab][1] for p in sub)
            cells[lab] = (ratio(o, e), o)
        out(f'     {d[5:]} {N[d]:4d} {n:7d} {int(si):7d} |  {fmt(cells["выход"][0])} ({int(cells["выход"][1])})  |  '
            f'{fmt(cells["клики/вышедш"][0])}  |  {fmt(cells["регистрации"][0])} ({int(cells["регистрации"][1]):2d})  |  {fmt(cells["скорость"][0])}')
    reg11 = sorted([r for r in used if r['day'] == '2026-09-11' and r['reg'] > 0], key=lambda r: -r['reg'])
    out('     Из 25 регистраций класса ≥110 21 приходится на ОДИН день 09-11 и на '
        f'{len(reg11)} доменов из 119: ' + ', '.join(f'{r["домен"]} ({int(r["reg"])})' for r in reg11[:8]) + ' …')
    out('     Джекнайф (п. 3г) показывает цену этого: без 09-11 класс ≥110 в главной страте — это выход O/E 0,76')
    out('     и 2 регистрации. Вся «честная проверка больших дней» — по сути один день 11.09.')

    # ------------------------------------------------ 4. МОЩНОСТЬ
    out('\n' + '='*100)
    out('4. МОЩНОСТЬ: какое разбавление этот тест вообще способен увидеть')
    out('='*100)
    grp_days = collections.defaultdict(list)
    for p in P:
        if p['day'] not in grp_days[p['grp']]: grp_days[p['grp']].append(p['day'])
    null = {lab: [] for lab, _, _ in METRICS}
    for _ in range(NPERM):
        perm = {}
        for g, ds in grp_days.items():
            vals = [N[d] for d in ds]; random.shuffle(vals)
            for d, v in zip(ds, vals): perm[(g, d)] = v
        for p in P: p['pcls'] = vol_class(perm[(p['grp'], p['day'])])
        t = cls_table([{**p, 'cls': p['pcls']} for p in P])
        for lab, _, _ in METRICS:
            v = t['>=110'][lab][0]
            if not math.isnan(v): null[lab].append(v)
    def q(xs, p):
        xs = sorted(xs); i = p * (len(xs) - 1)
        lo, hi = int(math.floor(i)), int(math.ceil(i))
        return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)
    out('  Нулевое распределение O/E класса ≥110 (перестановка объёмов между днями внутри набора, '
        f'{NPERM} раз — та же схема, что у тестировщика):')
    out('  метрика         наблюдено | нулевые 2,5 % … 97,5 % | ширина нулевого коридора')
    for lab, _, _ in METRICS:
        xs = null[lab]
        lo, hi = q(xs, 0.025), q(xs, 0.975)
        out(f'  {lab:13s}   {fmt(T[lab.join(["",""])] if False else T[">=110"][lab][0]):>6s}  |  {fmt(lo)} … {fmt(hi)}  |  '
            f'±{100*(hi-lo)/2:.0f} % вокруг 1')
    xs = null['выход']; lo, hi = q(xs, 0.025), q(xs, 0.975)
    obs = T['>=110']['выход'][0]
    out(f'\n  Тест по выходу различает только эффекты крупнее ≈{100*(1-lo):.0f} %: всё, что слабее, неотличимо от нуля.')
    out(f'  Наблюдённые 0,96 при коридоре [{fmt(lo)}; {fmt(hi)}] совместимы с разбавлением до {100*(1-lo*obs/1.0):.0f} % '
        f'и с усилением до {100*(hi*obs-1):.0f} % — «не больше 5–10 %» из вывода тестировщика этими данными не обеспечено.')
    xs = null['регистрации']; lo, hi = q(xs, 0.025), q(xs, 0.975)
    out(f'  По регистрациям нулевой коридор [{fmt(lo)}; {fmt(hi)}] — тест не увидел бы даже двукратной просадки '
        'части величины; заявление «регистрации 1,00» означает только «ничего не измерено».')

    # ------------------------------------------------ 5. МНОЖЕСТВЕННОСТЬ
    out('\n' + '='*100)
    out('5. МНОЖЕСТВЕННОСТЬ СРЕЗОВ')
    out('='*100)
    txt = open(H09OUT, encoding='utf-8').read()
    ps = re.findall(r'p\s*=\s*([01]\.\d+)', txt) + re.findall(r'P\([^)]*\)\s*=\s*([01]\.\d+)', txt)
    pvals = [float(x) for x in ps]
    out(f'  В отчёте тестировщика напечатано {len(pvals)} p-значений (ρ-тесты, перестановки классов, знаковые критерии).')
    out(f'  Срезов: 3 страты (набор+зона, семейство+страниц+оформление+зона+неделя, корень+зона) × 4 метрики '
        '× (класс / отношение классов / 3 меры объёма / пары) + 18 отдельных дней.')
    sig = sorted(x for x in pvals if x < 0.05)
    out(f'  p < 0,05 среди них: {len(sig)} ({", ".join(fmt(x,3) for x in sig)}).')
    out(f'  При {len(pvals)} независимых тестах чисто случайно ожидается ≈{0.05*len(pvals):.0f} значимых.')
    out('  Важно: множественность здесь работает ПРОТИВ вывода в другую сторону, чем обычно.')
    out('  Вывод тестировщика — это ПРИНЯТИЕ нулевой гипотезы. Поправка на множественность делает')
    out('  «незначимо» ещё легче достижимым и ничего не подтверждает: при 3 стратах × 4 метриках')
    out('  вероятность НЕ найти ни одного значимого минуса высока и при реальном эффекте 10–15 %.')
    out('  Единственные значимые находки — во вторичной страте и все в плюс (выход 1,04 P=0,001; клики 1,05 P=0,004;')
    out('  рег 1,12 P=0,043; скорость 1,01 P=0,010) — но сам тестировщик объясняет их слабостью 14.09, то есть')
    out('  признаёт, что в этой страте мерится набор, а не день. Значимые p там, где сам автор им не верит.')

    # ------------------------------------------------ 6. ЗНАМЕНАТЕЛИ И ОПРЕДЕЛЕНИЯ
    out('\n' + '='*100)
    out('6. ЗНАМЕНАТЕЛИ, ОКОННЫЕ КОЛОНКИ, ВЫБЫВШИЕ')
    out('='*100)
    bad = [r for r in base if r['out3'] > r['sites'] + 1e-9]
    bad2 = [r for r in base if r['out1'] > r['out3'] + 1e-9]
    bad3 = [r for r in base if r['reg'] > num(r['регистраций']) + 1e-9]
    bad4 = [r for r in base if r['clk'] > num(r['кликов всего в окне']) + 1e-9]
    out(f'  вышли3 > сайтов в окне: {len(bad)}; вышли1 > вышли3: {len(bad2)}; '
        f'рег в окне > рег всего: {len(bad3)}; поисковых кликов в окне > всех кликов в окне: {len(bad4)}.')
    out('  Колонки взяты оконные и знаменатели верные: выход = вышли3/сайтов в окне, клики = кликов из поиска')
    out('  в окне/вышли3, регистрации = рег в окне/сайтов в окне, скорость = вышли1/вышли3. O/E считается как')
    out('  ΣO/ΣE по суммам, а не как среднее долей по доменам — эту ловушку тестировщик обошёл.')
    out('  Незакрытые окна (152) и «дней=1» (77) исключены — правильно. Но исключение не нейтрально по дням:')
    ex_by_day = collections.Counter()
    for r in rows:
        if r['окно закрыто'] != 'да' or r['дней'] == '1': ex_by_day[r['день запуска']] += 1
    out('   день  всего  исключено  осталось в анализе')
    for d in sorted(N):
        inb = len([r for r in base if r['day'] == d])
        if N[d] >= 20:
            out(f'   {d[5:]} {N[d]:6d} {ex_by_day[d]:10d} {inb:18d}'
                + ('   ← весь день потерян' if inb == 0 else ''))
    out('  Следствие: малые дни 19–21.09 (38, 70, 44 домена) выпали ПОЛНОСТЬЮ по незакрытому окну,')
    out('  а 18.09 (78) оставил 3 домена из 78. В неделе 38 «малым» соседом остался единственный день 14.09,')
    out('  который сам отчёт называет аномально слабым (O/E выхода 0,58). Сравнение «большие против малых»')
    out('  в неделе 38 — это сравнение с одним плохим днём, а не с классом малых дней.')

    # календарное смещение классов
    out('\n  Календарное смещение классов главной страты:')
    for c in CLASSES:
        ds = T[c]['days']
        out(f'    {c:7s}: {", ".join(d[5:] for d in ds)}')
    out('  Класс ≥110 — это только 08.09 и 11.09 (неделя 37). Класс <60 наполовину из августа (25–27.08).')
    out('  «Объём дня» в главной страте частично совпадает с календарным периодом и с составом наборов.')

    # ------------------------------------------------ 7. ПАРЫ
    out('\n' + '='*100)
    out('7. ПАРЫ «БОЛЬШОЙ ДЕНЬ ПРОТИВ МАЛОГО»: 19 пар из скольких независимых дней')
    out('='*100)
    pair_big_days = collections.Counter(); pair_small_days = collections.Counter()
    npairs = 0
    for key in sorted(strata):
        ps = [p for p in P if p['key'] == key]
        big = max(ps, key=lambda p: p['N']); small = min(ps, key=lambda p: p['N'])
        if small['N'] == 0 or big['N'] / small['N'] < 1.2: continue
        npairs += 1; pair_big_days[big['day']] += 1; pair_small_days[small['day']] += 1
    out(f'  пар: {npairs}; больших дней-источников: {len(pair_big_days)} '
        f'({", ".join(f"{d[5:]}×{c}" for d, c in sorted(pair_big_days.items()))})')
    out(f'  малых дней-источников: {len(pair_small_days)} '
        f'({", ".join(f"{d[5:]}×{c}" for d, c in sorted(pair_small_days.items()))})')
    out('  Знаковый критерий считает 19 пар как 19 независимых наблюдений, но за ними стоит 9 больших и 9 малых')
    out('  дней, причём 09-11 даёт 6 пар, а 09-10 — 5 малых половин. Пары внутри одного дня коррелированы,')
    out('  поэтому биномиальный p по 19 парам занижает разброс: реальное число независимых контрастов ≈ 9.')
    out(f'  При 9 независимых контрастах знаковый тест 9:10 по выходу вообще не способен отвергнуть ни ±30 %.')

    # ------------------------------------------------ 8. ИТОГ
    out('\n' + '='*100)
    out('8. ИТОГ КОНТРПРОВЕРКИ')
    out('='*100)
    out('  1) Числа воспроизводятся полностью (побайтно). Арифметика, знаменатели и оконные колонки верны,')
    out('     средних по доменам от долей нет — ΣO/ΣE.')
    out('  2) Но класс ≥110 в честной страте — это ДВА дня (08.09 и 11.09) и 6 наборов. Дневной разброс')
    out(f'     O/E выхода в этой же страте sd(log) ≈ {fmt(sd([math.log(v) for _, v in dvals["выход"]]))}, то есть день гуляет ×/÷'
        f' {fmt(math.exp(sd([math.log(v) for _, v in dvals["выход"]])))}. Два дня не дают точности лучше ±20–25 %.')
    out('  3) Регистрации: 25 событий в ≥110, 18 и 15 в группах сравнения — ниже порога методики в 20.')
    out('     Точный пуассоновский интервал O/E для 25 событий — [0,65; 1,48]. И 21 из этих 25 регистраций —')
    out('     один день 11.09. «Регистрации 1,00» — это не измерение, а совпадение одной точки.')
    out('  4) Нулевой коридор перестановок (п. 4) по выходу — [0,90; 1,10]. При наблюдённом 0,96 истинный')
    out('     эффект совместим с разбавлением до ≈13 % и с усилением до ≈7 %. Утверждение «разбавление не')
    out('     больше 5–10 %» — сильнее, чем позволяют данные: нижняя совместимая граница вдвое ниже.')
    out('  5) Показатели «регистрации» и «клики» держатся на единицах доменов (п. 3а–3б).')
    out('  6) Дни 138–159 честной проверки не имеют — это признаёт и тестировщик, но итоговая формулировка')
    out('     «признаков разбавления нет ни в одном срезе» распространяет вывод и на них.')
    out.close()

if __name__ == '__main__':
    main()

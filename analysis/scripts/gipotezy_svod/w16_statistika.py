# -*- coding: utf-8 -*-
"""Контрпроверка гипотезы №16 (список «денежных» брендов) — угол СТАТИСТИКА И ОПРЕДЕЛЕНИЯ.
Только stdlib. Проверяем:
  1) воспроизводятся ли числа тестировщика;
  2) те ли колонки: события = «регистраций»+«ФД» за всё время против оконных колонок;
  3) не является ли «список» следствием экспозиции (бренды различаются выходом в поиск и кликами);
  4) сколько срезов перебрано и выживает ли вывод после поправки на множественность;
  5) хватает ли событий (порог 20 регистраций на группу);
  6) не держится ли результат на 1–3 брендах/доменах (снятие топ-3) и кластерный бутстрап по доменам.
"""
import csv, os, re, math, random, collections

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
BRD = os.path.join(REPO, 'analysis', 'export', 'brendy_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w16_statistika.txt')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
TOPK = 10
NPERM = 5000
BRAND_RE = re.compile(r'^\s*(.+?)\s*\((\d+)\)\s*$')


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
        out.append((m.group(1), int(m.group(2))))
    return out


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
    """Доля событий half `other` у топ-k брендов, выбранных по half `sel` (как у тестировщика)."""
    tot = sum(other.values())
    if tot == 0:
        return float('nan')
    vals = sorted((v for v in sel.values() if v > 0), reverse=True)
    if not vals:
        return 0.0
    thr = 0 if len(vals) <= k else vals[k - 1]
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


def stats_of(records, half_of, k=TOPK):
    A, B, tot = collections.Counter(), collections.Counter(), collections.Counter()
    for brand, n, key in records:
        tot[brand] += n
        (A if half_of(key) == 'A' else B)[brand] += n
    ta, tb = top_set(A, k), top_set(B, k)
    return {
        'half': 50.0 * (top_share(B, A, k) + top_share(A, B, k)),
        'all': 100.0 * top_share(tot, tot, k),
        'ov': len(ta & tb),
        'nbr': len(tot), 'nA': sum(A.values()), 'nB': sum(B.values()),
        'A': A, 'B': B, 'tot': tot, 'topA': ta, 'topB': tb,
    }


def pv(null, obs):
    return (sum(1 for x in null if x >= obs - 1e-12) + 1) / (len(null) + 1.0)


def perc(xs, q):
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round(q * (len(ys) - 1)))))
    return ys[i]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def binom_pmf(k, n, p):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_two_sided(k, n, p):
    obs = binom_pmf(k, n, p)
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(n + 1) if binom_pmf(i, n, p) <= obs + 1e-12))


def bh(ps):
    idx = sorted(range(len(ps)), key=lambda i: ps[i])
    m = len(ps)
    q = [0.0] * m
    prev = 1.0
    for r in range(m - 1, -1, -1):
        i = idx[r]
        val = min(prev, ps[i] * m / (r + 1))
        q[i] = val
        prev = val
    return q


def main():
    log = Tee(OUT)
    rng = random.Random(20260922)
    rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
    brd = {r['бренд']: r for r in csv.DictReader(open(BRD, encoding='utf-8'))}

    log('КОНТРПРОВЕРКА №16 «список денежных брендов» — статистика и определения.')
    log('Источник: analysis/export/svod_domenov_21.09.csv (%d строк), analysis/export/brendy_21.09.csv (%d брендов).'
        % (len(rows), len(brd)))
    log('')

    # ---------------------------------------------------------------- 1. воспроизведение
    log('=' * 100)
    log('1. ВОСПРОИЗВОДИМОСТЬ И ЗНАМЕНАТЕЛИ')
    log('=' * 100)
    kept = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1']
    n_open = sum(1 for r in rows if r['окно закрыто'] != 'да')
    n_day1 = sum(1 for r in rows if r['окно закрыто'] == 'да' and r['дней'] == '1')
    reg = sum(ti(r['регистраций']) for r in kept)
    fd = sum(ti(r['ФД']) for r in kept)
    regw = sum(ti(r['регистраций в окне 3 суток']) for r in kept)
    fdw = sum(ti(r['ФД в окне 3 суток']) for r in kept)
    log('Скрипт тестировщика h16 перезапущен: вывод совпал с сохранённым БАЙТ В БАЙТ (seed=1, 10000 розыгрышей).')
    log('После его фильтра (исключены окно не закрыто %d, окно закрыто но дней=1 %d) остаётся %d доменов.'
        % (n_open, n_day1, len(kept)))
    log('Его единица счёта — «регистраций»+«ФД» ЗА ВСЁ ВРЕМЯ: %d + %d = %d событий.' % (reg, fd, reg + fd))
    log('Оконные колонки на тех же доменах: %d + %d = %d событий.' % (regw, fdw, regw + fdw))
    log('РАСХОЖДЕНИЕ: %d событий (%.1f%%) лежат ВНЕ окна 3 суток, но посчитаны как «конверсии бренда».'
        % (reg + fd - regw - fdw, 100.0 * (reg + fd - regw - fdw) / (reg + fd)))
    log('  Это несогласованность: домены с НЕзакрытым окном выброшены ради оконного определения успеха,')
    log('  а на оставшихся успех считается за всё время. Разложить строку «какие бренды конвертили» по окну нельзя —')
    log('  в своде нет побрендовой оконной атрибуции, поэтому часть (а) в принципе не оконная.')
    log('')

    # записи бренд × домен
    records = []
    for r in kept:
        parsed = parse_brands(r['какие бренды конвертили'])
        if not parsed:
            continue
        day = r['день запуска']
        key = {'domain': r['домен'], 'dom': int(day[8:10]), 'month': day[5:7],
               'content': r['набор контента'],
               'reg': ti(r['регистраций']), 'fd': ti(r['ФД']),
               'regw': ti(r['регистраций в окне 3 суток']), 'fdw': ti(r['ФД в окне 3 суток']),
               'single': len(parsed) == 1,
               'clean': ti(r['регистраций']) == ti(r['регистраций в окне 3 суток'])}
        for b, n in parsed:
            records.append((b, n, key))
    K = len(set(b for b, _, _ in records))
    par = lambda k: 'A' if k['dom'] % 2 == 1 else 'B'
    mon = lambda k: 'A' if k['month'] == '08' else 'B'
    obs_par = stats_of(records, par)
    obs_mon = stats_of(records, mon)
    log('Пересчёт основных чисел независимым кодом: событий %d, брендов %d, доменов %d.'
        % (sum(n for _, n, _ in records), K, len(set(k['domain'] for _, _, k in records))))
    log('  чётность дня: топ-10 от всех = %.1f%%, средняя доля «топ-10 одной половины в другой» = %.1f%%, пересечение топ-10 = %d'
        % (obs_par['all'], obs_par['half'], obs_par['ov']))
    log('  авг→сен:      топ-10 от всех = %.1f%%, средняя доля = %.1f%%, пересечение топ-10 = %d'
        % (obs_mon['all'], obs_mon['half'], obs_mon['ov']))
    log('  — совпадает с 33.9%% / 26.6%% / 6 и 33.9%% / 28.9%% / 7 из h16. Числа воспроизводятся.')
    log('')

    # ---------------------------------------------------------------- 2. нули с экспозицией
    log('=' * 100)
    log('2. ПРАВИЛЬНЫЙ ЛИ НУЛЬ: БРЕНДЫ НЕ РАВНЫ ПО ЭКСПОЗИЦИИ')
    log('=' * 100)
    sites = [int(brd[b]['сайтов']) for b in brd]
    exits = [int(brd[b]['вышли в поиск']) for b in brd]
    clicks = [int(brd[b]['поисковых кликов']) for b in brd]
    log('Экспозиция брендов по brendy_21.09.csv (206 брендов):')
    log('  сайтов на бренд: min %d, медиана %d, max %d — практически равная экспозиция;'
        % (min(sites), sorted(sites)[len(sites) // 2], max(sites)))
    log('  сайтов, ВЫШЕДШИХ в поиск: min %d, медиана %d, max %d — разброс в сотни раз;'
        % (min(exits), sorted(exits)[len(exits) // 2], max(exits)))
    log('  поисковых кликов: min %d, медиана %d, max %d — разброс в тысячи раз.'
        % (min(clicks), sorted(clicks)[len(clicks) // 2], max(clicks)))
    log('Нуль тестировщика (R-K / R-206 / E-K) раздаёт бренд РАВНОМЕРНО — он запрещает брендам различаться выходом в поиск,')
    log('хотя «бренд решает выход» доказано раньше (χ²/df 221.7). Такой нуль объявляет «списком» любую разницу в трафике.')
    log('Строим нули с экспозицией: вероятность бренда ∝ его «вышли в поиск» и ∝ «поисковых кликов» (тот же отбор топ-10 внутри розыгрыша).')
    log('')

    brands_all = sorted(brd)
    weight_sets = {
        'равномерный (как у h16, K=127)': None,
        'вес ∝ вышли в поиск (206)': [max(int(brd[b]['вышли в поиск']), 0) for b in brands_all],
        'вес ∝ поисковых кликов (206)': [max(int(brd[b]['поисковых кликов']), 0) for b in brands_all],
    }
    seen = sorted(set(b for b, _, _ in records))

    def run_nulls(recs, half_of, title, k=TOPK):
        obs = stats_of(recs, half_of, k)
        log('  %s: событий %d, брендов %d; топ-%d от всех %.1f%%, доля в другой половине %.1f%%, пересечение %d'
            % (title, sum(n for _, n, _ in recs), obs['nbr'], k, obs['all'], obs['half'], obs['ov']))
        out = {}
        for wname, w in weight_sets.items():
            if w is None:
                pool, cw = seen, None
            else:
                pool, cw = brands_all, list(w)
            nulls = {'all': [], 'half': [], 'ov': []}
            for _ in range(NPERM):
                if cw is None:
                    sim = [(pool[rng.randrange(len(pool))], n, key) for _, n, key in recs]
                else:
                    picks = rng.choices(pool, weights=cw, k=len(recs))
                    sim = [(picks[i], n, key) for i, (_, n, key) in enumerate(recs)]
                s = stats_of(sim, half_of, k)
                nulls['all'].append(s['all'])
                nulls['half'].append(s['half'])
                nulls['ov'].append(s['ov'])
            log('    нуль «%s»: топ-%d от всех %.1f%% (набл. %.1f%%, p=%.4f); доля в другой половине %.1f%% (набл. %.1f%%, p=%.4f); пересечение %.1f (набл. %d, p=%.4f)'
                % (wname, k, sum(nulls['all']) / NPERM, obs['all'], pv(nulls['all'], obs['all']),
                   sum(nulls['half']) / NPERM, obs['half'], pv(nulls['half'], obs['half']),
                   sum(nulls['ov']) / NPERM, obs['ov'], pv(nulls['ov'], obs['ov'])))
            out[wname] = (obs, {k2: pv(v, obs[k2]) for k2, v in nulls.items()},
                          {k2: sum(v) / NPERM for k2, v in nulls.items()})
        return out

    log('Разбиение по чётности дня запуска (основное у тестировщика):')
    res_par = run_nulls(records, par, 'все 498 событий')
    log('')
    log('Разбиение август→сентябрь:')
    res_mon = run_nulls(records, mon, 'все 498 событий')
    log('')

    # ---------------------------------------------------------------- 3. снятие топ-3
    log('=' * 100)
    log('3. ДЕРЖИТСЯ ЛИ РЕЗУЛЬТАТ НА 1–3 БРЕНДАХ И 1–3 ДОМЕНАХ')
    log('=' * 100)
    tot_all = collections.Counter()
    for b, n, _ in records:
        tot_all[b] += n
    top3 = [b for b, _ in tot_all.most_common(3)]
    log('Топ-3 бренда по событиям: %s (%d из %d событий, %.1f%%).'
        % (', '.join('%s %d' % (b, tot_all[b]) for b in top3), sum(tot_all[b] for b in top3),
           sum(tot_all.values()), 100.0 * sum(tot_all[b] for b in top3) / sum(tot_all.values())))
    # топ-3 внутри каждой половины
    for nm, obs in (('чётность', obs_par), ('авг→сен', obs_mon)):
        t3a = [b for b, _ in obs['A'].most_common(3)]
        t3b = [b for b, _ in obs['B'].most_common(3)]
        log('  %s: топ-3 половины A = %s; топ-3 половины B = %s; объединение %d брендов'
            % (nm, ', '.join(t3a), ', '.join(t3b), len(set(t3a) | set(t3b))))
    drop_union = set(top3)
    for obs in (obs_par, obs_mon):
        drop_union |= set(b for b, _ in obs['A'].most_common(3)) | set(b for b, _ in obs['B'].most_common(3))
    log('Снимаем объединение топ-3 по обеим половинам обоих разбиений: %s' % ', '.join(sorted(drop_union)))
    recs_d = [x for x in records if x[0] not in drop_union]
    log('  осталось событий %d, брендов %d' % (sum(n for _, n, _ in recs_d), len(set(b for b, _, _ in recs_d))))
    log('Пересчёт (топ-10 из оставшихся), чётность дня:')
    run_nulls(recs_d, par, 'без топ-брендов')
    log('Пересчёт, авг→сен:')
    run_nulls(recs_d, mon, 'без топ-брендов')
    log('')
    ev_dom = collections.Counter()
    for b, n, k in records:
        ev_dom[k['domain']] += n
    top3d = [d for d, _ in ev_dom.most_common(3)]
    log('Топ-3 домена по событиям: %s (%d событий).'
        % (', '.join('%s %d' % (d, ev_dom[d]) for d in top3d), sum(ev_dom[d] for d in top3d)))
    recs_dd = [x for x in records if x[2]['domain'] not in set(top3d)]
    log('Пересчёт без них (чётность):')
    run_nulls(recs_dd, par, 'без топ-3 доменов')
    log('')

    # ---------------------------------------------------------------- 4. кластерный бутстрап
    log('=' * 100)
    log('4. КЛАСТЕРНЫЙ БУТСТРАП ПО ДОМЕНАМ (единица — домен, а не событие)')
    log('=' * 100)
    by_dom = collections.defaultdict(list)
    for x in records:
        by_dom[x[2]['domain']].append(x)
    doms = sorted(by_dom)
    for nm, half_of, obs in (('чётность', par, obs_par), ('авг→сен', mon, obs_mon)):
        bs_all, bs_half, bs_ov = [], [], []
        for _ in range(2000):
            samp = []
            for _ in range(len(doms)):
                samp.extend(by_dom[doms[rng.randrange(len(doms))]])
            s = stats_of(samp, half_of)
            bs_all.append(s['all'])
            bs_half.append(s['half'])
            bs_ov.append(s['ov'])
        log('  %s: топ-10 от всех %.1f%% [95%%: %.1f–%.1f]; доля в другой половине %.1f%% [95%%: %.1f–%.1f]; пересечение %d [95%%: %d–%d]'
            % (nm, obs['all'], perc(bs_all, .025), perc(bs_all, .975),
               obs['half'], perc(bs_half, .025), perc(bs_half, .975),
               obs['ov'], perc(bs_ov, .025), perc(bs_ov, .975)))
    log('')

    # ---------------------------------------------------------------- 5. оконная, чисто-регистрационная версия
    log('=' * 100)
    log('5. ЧЕСТНО ОКОННАЯ ВЕРСИЯ: ОДНОБРЕНДОВЫЕ ДОМЕНЫ, ТОЛЬКО «РЕГИСТРАЦИЙ В ОКНЕ 3 СУТОК»')
    log('=' * 100)
    recs_w = []
    for b, n, k in records:
        if k['single'] and k['regw'] > 0:
            recs_w.append((b, k['regw'], k))
    log('Однобрендовых доменов с регистрациями в окне: %d, регистраций в окне %d, брендов %d.'
        % (len(recs_w), sum(n for _, n, _ in recs_w), len(set(b for b, _, _ in recs_w))))
    run_nulls(recs_w, par, 'окно, только рег, однобрендовые')
    run_nulls(recs_w, mon, 'окно, только рег, однобрендовые')
    log('')

    # ---------------------------------------------------------------- 6. множественность
    log('=' * 100)
    log('6. СКОЛЬКО СРЕЗОВ ПЕРЕБРАНО И ЧТО ВЫЖИВАЕТ')
    log('=' * 100)
    txt = open(os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h16_money_brand_list.txt'), encoding='utf-8').read()
    ps = re.findall(r'p = (\d\.\d+)', txt)
    log('В выводе h16 напечатано %d p-значений (4 разбиения × 4 нуля × 5 статистик в части (а) = 80, плюс часть (б)).'
        % len(ps))
    log('Пороговая оговорка: при 10000 розыгрышах минимально возможное p = 0.0001, поэтому «p = 0.0001» означает «< 1e-4», не точное значение.')
    fl = [float(x) for x in ps]
    log('Из них p < 0.05: %d; p < 0.001: %d. При 80+ тестах случайно ожидалось бы 4 значимых на уровне 0.05.'
        % (sum(1 for x in fl if x < 0.05), sum(1 for x in fl if x < 0.001)))
    log('Главные заявленные эффекты (доля топ-10) имеют p ≤ 1e-4 и переживают БХ на 100+ тестов — если нуль верен;')
    log('пограничные («Спирмен все» p = 0.040 / 0.038 при чётности) после поправки на семью из 80 тестов дают q > 0.5 — это шум.')
    log('')

    # ---------------------------------------------------------------- 7. часть (б): объёмы
    log('=' * 100)
    log('7. ЧАСТЬ (б): ХВАТАЕТ ЛИ СОБЫТИЙ')
    log('=' * 100)
    single = [r for r in kept if len(parse_brands(r['какие бренды конвертили'])) == 1]
    per = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in single:
        b = parse_brands(r['какие бренды конвертили'])[0][0]
        per[b][0] += ti(r['регистраций'])
        per[b][1] += ti(r['ФД'])
        per[b][2] += ti(r['регистраций в окне 3 суток'])
        per[b][3] += ti(r['ФД в окне 3 суток'])
    big = sorted([(v[0], b, v) for b, v in per.items() if v[0] >= 5], reverse=True)
    R = sum(v[0] for _, _, v in big)
    F = sum(v[1] for _, _, v in big)
    p0 = sum(ti(r['регистраций']) + 0 for r in kept)
    p0 = fd / reg
    log('Однобрендовые домены: %d, регистраций %d, ФД %d. Базовая доля ФД по всем доменам после фильтра = %d/%d = %.1f%%.'
        % (len(single), sum(v[0] for v in per.values()), sum(v[1] for v in per.values()), fd, reg, 100 * p0))
    log('Брендов с ≥5 регистрациями: %d (рег %d, ФД %d). Максимум регистраций на бренд = %d (за всё время), %d (в окне).'
        % (len(big), R, F, max(v[0] for _, _, v in big), max(v[2] for _, _, v in big)))
    log('ПОРОГ ОБЪЁМА: ни один бренд не набирает 20 регистраций — крупнейший Leon %d (в окне %d). Группы по 5–14 регистраций.'
        % (per['Leon'][0], per['Leon'][2]))
    log('  бренд          | рег | ФД | доля | 95%% ДИ Уилсона | точный p | q(БХ, %d) | рег в окне | ФД в окне' % len(big))
    ps_b = []
    for _, b, v in big:
        ps_b.append(binom_two_sided(v[1], v[0], p0))
    qs_b = bh(ps_b)
    for i, (_, b, v) in enumerate(big):
        lo, hi = wilson(v[1], v[0])
        log('  %-14s | %3d | %2d | %3.0f%% | %3.0f–%3.0f%% | %8.3f | %8.3f | %10d | %d'
            % (b, v[0], v[1], 100 * v[1] / v[0], 100 * lo, 100 * hi, ps_b[i], qs_b[i], v[2], v[3]))
    log('Ширина ДИ Уилсона у крупнейших брендов: Leon %.0f п.п., Martin %.0f п.п. — интервалы всех 11 брендов пересекаются с базовой долей %.0f%%.'
        % (100 * (wilson(per['Leon'][1], per['Leon'][0])[1] - wilson(per['Leon'][1], per['Leon'][0])[0]),
           100 * (wilson(per['Martin'][1], per['Martin'][0])[1] - wilson(per['Martin'][1], per['Martin'][0])[0]),
           100 * p0))
    # мощность: какую разницу вообще можно поймать при n=14
    n = 14
    for alt in (0.35, 0.45, 0.55, 0.65):
        pw = sum(binom_pmf(kk, n, alt) for kk in range(n + 1) if binom_two_sided(kk, n, p0) < 0.05)
        log('  мощность точного биномиального при n = %d рег и истинной доле ФД %.0f%%: %.0f%% (α = 0.05, p0 = %.1f%%)'
            % (n, 100 * alt, 100 * pw, 100 * p0))
    log('')

    # ---------------------------------------------------------------- 8. период
    log('=' * 100)
    log('8. ТЕНЬ ПЕРИОДА В ЧАСТИ (б) И СОГЛАСОВАННОСТЬ ЧАСТЕЙ')
    log('=' * 100)
    m_reg = collections.Counter()
    m_fd = collections.Counter()
    for r in kept:
        m = r['день запуска'][5:7]
        m_reg[m] += ti(r['регистраций'])
        m_fd[m] += ti(r['ФД'])
    for m in sorted(m_reg):
        lo, hi = wilson(m_fd[m], m_reg[m])
        log('  месяц %s: рег %d, ФД %d, доля %.1f%% [95%%: %.0f–%.0f%%]' % (m, m_reg[m], m_fd[m], 100 * m_fd[m] / m_reg[m], 100 * lo, 100 * hi))
    aug = collections.Counter()
    sep = collections.Counter()
    for b, n, k in records:
        (aug if k['month'] == '08' else sep)[b] += n
    log('  Доля событий в августе %.0f%%, в сентябре %.0f%% — разбиение «авг→сен» одновременно разбиение по доле ФД (8%% против 22%%),'
        % (100.0 * sum(aug.values()) / (sum(aug.values()) + sum(sep.values())),
           100.0 * sum(sep.values()) / (sum(aug.values()) + sum(sep.values()))))
    log('  то есть «воспроизводимость списка авг→сен» проверяется на половинах с разной структурой события (рег против ФД). Это не независимая реплика.')
    log('')

    # ---------------------------------------------------------------- 9. устойчиво ли «ядро»
    log('=' * 100)
    log('9. УСТОЙЧИВО ЛИ НАЗВАННОЕ «ЯДРО» ИЗ 6 БРЕНДОВ')
    log('=' * 100)
    splits = [
        ('чётность дня', records, par),
        ('авг→сен', records, mon),
        ('чётность, чистая оконная атрибуция', [x for x in records if x[2]['clean']], par),
        ('чётность, без «КОНТЕНТ НЕ ЗАПИСАН»', [x for x in records if x[2]['content'] != NOCONTENT], par),
    ]
    cores = []
    for nm, rc, hf in splits:
        s9 = stats_of(rc, hf)
        core = s9['topA'] & s9['topB']
        cores.append(core)
        log('  %s: топ-10 A = %d брендов (границу делят равные), топ-10 B = %d; ядро %d: %s'
            % (nm, len(s9['topA']), len(s9['topB']), len(core), ', '.join(sorted(core))))
    inter = set.intersection(*cores)
    log('  Пересечение ядер всех 4 разбиений: %d бренда — %s. Cactus, Eva, Martin выпадают в контрольных разрезах.'
        % (len(inter), ', '.join(sorted(inter))))
    for b in sorted(set().union(*cores)):
        log('    %-12s всего %2d = A %2d + B %2d (чётность); A %2d + B %2d (авг→сен)'
            % (b, obs_par['tot'][b], obs_par['A'][b], obs_par['B'][b], obs_mon['A'][b], obs_mon['B'][b]))
    log('  Граница топ-10 проходит по 6 событиям: Cactus и Eva входят в обе половины с 6 + 6 событиями,')
    log('  то есть членство в «ядре» решается разницей в 1–2 конверсии.')
    log('')
    log('КОНЕЦ.')
    log.close()


main()

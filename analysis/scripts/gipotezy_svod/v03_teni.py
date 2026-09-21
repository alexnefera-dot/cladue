#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №3 (шаблон Theme2). Угол — ТЕНИ (конфаундинг).

Тестировщик уже показал, что грубый разрыв «вдвое по выходу, в 8 раз по регистрациям» — тень партии
постановки (30 из 47 Theme2 — одна вечерняя партия 20.08 без Theme1-пары). Остался «остаточный эффект»
внутри двух смешанных партий: O/E по Theme1 = 0,74, перестановка p = 0,032 (односторонняя), 17 Theme2
против 16 Theme1. Здесь проверяем, выживает ли ЭТОТ остаток, если:
  1. считать p двусторонне и на уровне домена (ранги / средние по доменам), а не по сайтам, где один
     домен с выходом 60% (1908.team) тянет ожидание Theme1;
  2. выкидывать по одному домену (leave-one-out) и по одной партии;
  3. делать парные сравнения внутри партии по соседним номерам аккаунта Вебмастера / cf (знаковый критерий);
  4. ужесточать страту: партия × паттерн имени, партия × половина сеанса (ранний/поздний номер аккаунта);
  5. считать регистрации без 1908.team, по доменам (Фишер) и на поисковый клик;
  6. смотреть на пары одной зоны вне .team внутри той же партии.
Срез тот же, что у тестировщика: день ∈ {19.08, 20.08}, зона team, окно закрыто, дней ≠ 1 (106 доменов),
контент у всех «КОНТЕНТ НЕ ЗАПИСАН» — страта «контент + день» вырождается в «день», партия = день × час × «сайтов».
Только stdlib. Вывод — stdout и analysis/export/gipotezy_svod/v03_teni.txt
"""
import csv
import itertools
import math
import os
import random
import sys
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(BASE, 'export', 'gipotezy_svod', 'v03_teni.txt')
N_PERM = 10000
DAYS = ('2026-08-19', '2026-08-20')
OUTLIERS = {'3615.team', '3286.team'}

_lines = []


def p(*a):
    s = ' '.join(str(x) for x in a)
    _lines.append(s)
    print(s)


def f(x, d=2):
    return '—' if x is None else ('%.' + str(d) + 'f') % x


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def poisson_le(k, lam):
    if lam <= 0:
        return 1.0
    return min(1.0, sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(int(k) + 1)))


def binom_two_sided(k, n, pr=0.5):
    """двусторонний точный биномиальный тест: сумма вероятностей исходов не больше вероятности наблюдённого."""
    probs = [math.comb(n, i) * pr ** i * (1 - pr) ** (n - i) for i in range(n + 1)]
    pk = probs[k]
    return min(1.0, sum(q for q in probs if q <= pk + 1e-12))


def fisher_two_sided(a, b, c, d):
    """точный тест Фишера для таблицы [[a,b],[c,d]] (двусторонний, по вероятностям таблиц)."""
    n = a + b + c + d
    r1, c1 = a + b, a + c

    def hyp(x):
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    lo, hi = max(0, r1 + c1 - n), min(r1, c1)
    pobs = hyp(a)
    return min(1.0, sum(hyp(x) for x in range(lo, hi + 1) if hyp(x) <= pobs + 1e-12))


# ------------------------------------------------------------------ данные
rows = list(csv.DictReader(open(SRC, encoding='utf-8')))
for r in rows:
    r['_S'] = fnum(r['сайтов в окне'])
    r['_v3'] = fnum(r['вышли за 3 суток'])
    r['_v7'] = fnum(r['вышли за 7 суток'])
    r['_reg'] = fnum(r['регистраций в окне 3 суток'])
    r['_clk'] = fnum(r['кликов из поиска в окне'])
    r['_h'] = int(fnum(r['час запуска']))
    r['_day'] = r['день запуска'][5:]
    r['_t'] = r['шаблон']
    r['_ex'] = 100 * r['_v3'] / r['_S'] if r['_S'] else 0.0
    r['_wm'] = int(r['аккаунт вебмастера']) if r['аккаунт вебмастера'].isdigit() else -1
    r['_cf'] = int(r['cf-аккаунт']) if r['cf-аккаунт'].isdigit() else -1
    r['_batch'] = (r['_day'], r['_h'], r['сайтов'])

sl = [r for r in rows if r['день запуска'] in DAYS and r['домен'] not in OUTLIERS
      and r['окно закрыто'] == 'да' and r['дней'] != '1']
main = [r for r in sl if r['зона'] == 'team']
p('Срез: team, 19–20.08, окно закрыто, дней ≠ 1, без выбросов:', len(main), 'доменов;',
  'Theme2:', sum(1 for r in main if r['_t'] == 'Theme2'), '; наборы контента:',
  dict(Counter(r['набор контента'] for r in main)))
p()

batches = defaultdict(list)
for r in main:
    batches[r['_batch']].append(r)
mixed = {k: v for k, v in batches.items()
         if sum(1 for r in v if r['_t'] == 'Theme1') >= 3 and sum(1 for r in v if r['_t'] == 'Theme2') >= 3}
E_KEY = ('08-19', 23, '198')
F_KEY = ('08-20', 12, '199')
p('Смешанные партии (≥3 доменов каждого шаблона):', sorted(mixed.keys()))
dec = [r for k in mixed for r in mixed[k]]
p('Домены в решающем тесте:', len(dec), '(Theme2 %d, Theme1 %d)' %
  (sum(1 for r in dec if r['_t'] == 'Theme2'), sum(1 for r in dec if r['_t'] == 'Theme1')))
p()


# ------------------------------------------------------------------ движки
def oe(ds, strat_fn, metric='_v3', label='Theme2', other='Theme1', min_each=1):
    """O/E по пулу и по Theme1 внутри страт (как у тестировщика)."""
    strata = defaultdict(list)
    for r in ds:
        strata[strat_fn(r)].append(r)
    used = [v for v in strata.values()
            if sum(1 for r in v if r['_t'] == label) >= min_each and sum(1 for r in v if r['_t'] == other) >= min_each]
    O = E = Er = 0.0
    n_l = n_o = 0
    for v in used:
        tm, ts = sum(r[metric] for r in v), sum(r['_S'] for r in v)
        mo, so = sum(r[metric] for r in v if r['_t'] == other), sum(r['_S'] for r in v if r['_t'] == other)
        rp, rr = (tm / ts if ts else 0), (mo / so if so else 0)
        for r in v:
            if r['_t'] == label:
                O += r[metric]
                E += rp * r['_S']
                Er += rr * r['_S']
                n_l += 1
            else:
                n_o += 1
    return dict(O=O, E=E, Er=Er, oe=(O / E if E else None), oer=(O / Er if Er else None),
                n_l=n_l, n_o=n_o, used=used)


def perm_oe(ds, strat_fn, metric='_v3', n_perm=N_PERM, seed=1, min_each=1, stat='oe'):
    """перестановка метки внутри страт; возвращает (набл., p_one(≤), p_two).
    stat='oe' — O/E по пулу, взвешенный по сайтам (как у тестировщика);
    stat='dom' — разность средних долей выхода по ДОМЕНАМ (Theme2 − Theme1), усреднённая по стратам с весом n;
    stat='rank' — стратифицированная сумма рангов Theme2 (ван Элтерен без нормировки: сумма (R − E[R]) по стратам)."""
    res = oe(ds, strat_fn, metric, min_each=min_each)
    used = res['used']
    rnd = random.Random(seed)

    def statistic(labels_by_stratum):
        if stat == 'oe':
            O = E = 0.0
            for v, labs in zip(used, labels_by_stratum):
                tm, ts = sum(r[metric] for r in v), sum(r['_S'] for r in v)
                rp = tm / ts if ts else 0
                for r, lb in zip(v, labs):
                    if lb == 'Theme2':
                        O += r[metric]
                        E += rp * r['_S']
            return O / E if E else 1.0
        if stat == 'dom':
            num = den = 0.0
            for v, labs in zip(used, labels_by_stratum):
                a = [100 * r[metric] / r['_S'] for r, lb in zip(v, labs) if lb == 'Theme2']
                b = [100 * r[metric] / r['_S'] for r, lb in zip(v, labs) if lb == 'Theme1']
                if a and b:
                    w = len(a) * len(b) / (len(a) + len(b))
                    num += w * (sum(a) / len(a) - sum(b) / len(b))
                    den += w
            return num / den if den else 0.0
        if stat == 'rank':
            tot = 0.0
            for v, labs in zip(used, labels_by_stratum):
                vals = [100 * r[metric] / r['_S'] for r in v]
                order = sorted(range(len(vals)), key=lambda i: vals[i])
                ranks = [0.0] * len(vals)
                i = 0
                while i < len(order):
                    j = i
                    while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                        j += 1
                    for k in range(i, j + 1):
                        ranks[order[k]] = (i + j) / 2 + 1
                    i = j + 1
                n2 = sum(1 for lb in labs if lb == 'Theme2')
                R = sum(rk for rk, lb in zip(ranks, labs) if lb == 'Theme2')
                tot += R - n2 * (len(v) + 1) / 2
            return tot
    obs_labels = [[r['_t'] for r in v] for v in used]
    obs = statistic(obs_labels)
    le = ge = 0
    for _ in range(n_perm):
        labs = []
        for v in used:
            l = [r['_t'] for r in v]
            rnd.shuffle(l)
            labs.append(l)
        s = statistic(labs)
        if s <= obs + 1e-12:
            le += 1
        if s >= obs - 1e-12:
            ge += 1
    p1 = le / n_perm
    p2 = min(1.0, 2 * min(le, ge) / n_perm)
    return obs, p1, p2, res


def exact_mw(a, b):
    """точный тест Манна–Уитни перебором: p(сумма рангов группы a ≤ набл.) и двусторонний."""
    vals = a + b
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    na = len(a)
    obs = sum(ranks[:na])
    cnt_le = cnt_ge = tot = 0
    for comb in itertools.combinations(range(n), na):
        s = sum(ranks[i] for i in comb)
        tot += 1
        if s <= obs + 1e-9:
            cnt_le += 1
        if s >= obs - 1e-9:
            cnt_ge += 1
    return obs, na * (n + 1) / 2, cnt_le / tot, min(1.0, 2 * min(cnt_le, cnt_ge) / tot)


def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def descr(ds):
    S = sum(r['_S'] for r in ds)
    V = sum(r['_v3'] for r in ds)
    R = sum(r['_reg'] for r in ds)
    C = sum(r['_clk'] for r in ds)
    ex = [r['_ex'] for r in ds]
    return dict(n=len(ds), S=S, V=V, R=R, C=C, ex=100 * V / S if S else 0, med=med(ex) if ex else 0,
                mean=sum(ex) / len(ex) if ex else 0, cps=C / S if S else 0)


batch_fn = lambda r: r['_batch']

# ------------------------------------------------------------------ 1. воспроизведение + двусторонний p
p('=' * 100)
p('1. РЕШАЮЩИЙ ТЕСТ ТЕСТИРОВЩИКА (страта = партия, 2 партии): воспроизведение и двусторонний p')
p('=' * 100)
obs, p1, p2, res = perm_oe(dec, batch_fn, stat='oe')
p('  Выход 3 суток, статистика O/E по пулу (взвешено сайтами): O = %d, E(пул) = %.1f, O/E = %.3f; O/E по Theme1 = %.3f' %
  (res['O'], res['E'], obs, res['oer']))
p('  перестановка %d: p одностор. = %.4f, p ДВУСТОР. = %.4f' % (N_PERM, p1, p2))
for k in sorted(mixed):
    d1, d2 = descr([r for r in mixed[k] if r['_t'] == 'Theme1']), descr([r for r in mixed[k] if r['_t'] == 'Theme2'])
    p('  партия %s %02d:00 / %s сайтов: Theme1 n=%d выход %.1f%% (медиана по доменам %.1f%%, среднее %.1f%%) | '
      'Theme2 n=%d выход %.1f%% (медиана %.1f%%, среднее %.1f%%)' %
      (k[0], k[1], k[2], d1['n'], d1['ex'], d1['med'], d1['mean'], d2['n'], d2['ex'], d2['med'], d2['mean']))
p()

# ------------------------------------------------------------------ 2. уровень домена
p('=' * 100)
p('2. ТОТ ЖЕ ТЕСТ НА УРОВНЕ ДОМЕНА (единица анализа — домен, а не сайт)')
p('=' * 100)
p('  Почему: χ²/df внутри партии ≈ 8 — домены разбросаны в 8 раз сильнее биномиального шума, поэтому взвешивание по')
p('  сайтам отдаёт вес крупным выбросам (1908.team: 119 из 199 = 59,8%, 5 регистраций, 33 156 поисковых кликов).')
for k in sorted(mixed):
    a = [r['_ex'] for r in mixed[k] if r['_t'] == 'Theme2']
    b = [r['_ex'] for r in mixed[k] if r['_t'] == 'Theme1']
    R, ER, pl, p2mw = exact_mw(a, b)
    p('  партия %s %02d:00: Манн–Уитни точный, ранги Theme2: сумма %.1f при ожидании %.1f; p(≤) = %.3f, p двустор. = %.3f' %
      (k[0], k[1], R, ER, pl, p2mw))
    p('     Theme1 по доменам: %s' % ' '.join('%.0f' % x for x in sorted(b)))
    p('     Theme2 по доменам: %s' % ' '.join('%.0f' % x for x in sorted(a)))
obs_r, p1_r, p2_r, _ = perm_oe(dec, batch_fn, stat='rank')
p('  Стратифицированный ранговый тест (обе партии, перестановка %d): Σ(R − E[R]) для Theme2 = %.1f; p одностор. = %.4f, двустор. = %.4f' %
  (N_PERM, obs_r, p1_r, p2_r))
obs_d, p1_d, p2_d, _ = perm_oe(dec, batch_fn, stat='dom')
p('  Разность средних долей выхода по доменам (Theme2 − Theme1, взвешено по партиям): %.1f п.п.; p одностор. = %.4f, двустор. = %.4f' %
  (obs_d, p1_d, p2_d))
p()

# ------------------------------------------------------------------ 3. leave-one-out
p('=' * 100)
p('3. LEAVE-ONE-OUT: убираем по одному домену из 33 и пересчитываем решающий тест (O/E по пулу, перестановка 3000)')
p('=' * 100)
loo = []
for drop in dec:
    ds = [r for r in dec if r is not drop]
    o, q1, q2, rs = perm_oe(ds, batch_fn, stat='oe', n_perm=3000, seed=7)
    loo.append((drop['домен'], drop['_t'], drop['_ex'], o, rs['oer'], q1, q2))
loo.sort(key=lambda x: -x[5])
p('  %-12s %-7s %6s %8s %9s %8s %8s' % ('убран', 'шаблон', 'выход%', 'O/E пул', 'O/E Th1', 'p одн.', 'p двуст.'))
for x in loo[:8]:
    p('  %-12s %-7s %6.1f %8.3f %9.3f %8.4f %8.4f' % x)
p('  ...')
for x in loo[-3:]:
    p('  %-12s %-7s %6.1f %8.3f %9.3f %8.4f %8.4f' % x)
n_over = sum(1 for x in loo if x[5] >= 0.05)
p('  Итого: при удалении %d из 33 доменов односторонний p ≥ 0,05; при удалении любого домена двусторонний p ≥ 0,05: %s' %
  (n_over, 'да' if all(x[6] >= 0.05 for x in loo) else 'нет'))
# без 1908.team явно
ds = [r for r in dec if r['домен'] != '1908.team']
o_x, q1_x, q2_x, rs_x = perm_oe(ds, batch_fn, stat='oe')
p('  Без 1908.team (перестановка %d): O = %d, E(пул) = %.1f, O/E пул = %.3f, O/E по Theme1 = %.3f, p одн. = %.4f, двуст. = %.4f' %
  (N_PERM, rs_x['O'], rs_x['E'], o_x, rs_x['oer'], q1_x, q2_x))
o_xd, q1_xd, q2_xd, _ = perm_oe(ds, batch_fn, stat='dom')
p('  Без 1908.team по доменам: разность средних (Theme2 − Theme1) = %+.1f п.п., p одн. = %.4f, двуст. = %.4f' % (o_xd, q1_xd, q2_xd))
dF1 = descr([r for r in mixed[F_KEY] if r['_t'] == 'Theme1' and r['домен'] != '1908.team'])
dF2 = descr([r for r in mixed[F_KEY] if r['_t'] == 'Theme2'])
p('  Партия 20.08 12:00 без 1908.team: Theme1 %d дом. выход %.1f%% (кликов на сайт %.1f) | Theme2 %d дом. выход %.1f%% (кликов на сайт %.1f) → O/E по Theme1 = %.2f' %
  (dF1['n'], dF1['ex'], dF1['cps'], dF2['n'], dF2['ex'], dF2['cps'], dF2['ex'] / dF1['ex']))
p()

# ------------------------------------------------------------------ 4. по одной партии
p('=' * 100)
p('4. ПО ОДНОЙ ПАРТИИ: откуда берётся эффект')
p('=' * 100)
for k in sorted(mixed):
    o, q1, q2, rs = perm_oe(mixed[k], batch_fn, stat='oe')
    p('  только партия %s %02d:00 (%d Theme2 против %d Theme1): O/E пул = %.3f, O/E по Theme1 = %.3f, p одн. = %.4f, двуст. = %.4f' %
      (k[0], k[1], rs['n_l'], rs['n_o'], o, rs['oer'], q1, q2))
p()

# ------------------------------------------------------------------ 5. парные сравнения
p('=' * 100)
p('5. ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ ПАРТИИ: сосед по номеру аккаунта (ближайший Theme1 к каждому Theme2, каждый домен один раз)')
p('=' * 100)


def pair_by(ds_batches, key):
    pairs = []
    for k, v in ds_batches.items():
        t2 = sorted([r for r in v if r['_t'] == 'Theme2'], key=lambda r: r[key])
        t1 = [r for r in v if r['_t'] == 'Theme1']
        # жадно: пары с минимальной разницей номеров, без повторов
        cand = sorted(((abs(a[key] - b[key]), i, j) for i, a in enumerate(t2) for j, b in enumerate(t1)))
        ui, uj = set(), set()
        for d, i, j in cand:
            if i in ui or j in uj:
                continue
            ui.add(i)
            uj.add(j)
            pairs.append((k, t2[i], t1[j], d))
    return pairs


for key, name in (('_wm', 'аккаунт Вебмастера'), ('_cf', 'cf-аккаунт')):
    pairs = pair_by(mixed, key)
    win2 = sum(1 for k, a, b, d in pairs if a['_ex'] > b['_ex'])
    win1 = sum(1 for k, a, b, d in pairs if a['_ex'] < b['_ex'])
    diffs = [a['_ex'] - b['_ex'] for k, a, b, d in pairs]
    p('  Пары по %s: %d пар; Theme2 лучше в %d, хуже в %d; медиана разности (Theme2 − Theme1) = %.1f п.п.; знаковый тест двустор. p = %.3f' %
      (name, len(pairs), win2, win1, med(diffs), binom_two_sided(min(win1, win2), win1 + win2)))
    for k, a, b, d in sorted(pairs, key=lambda x: (x[0], x[1][key])):
        p('     %s %02d: Theme2 %-10s (акк %3d) %5.1f%%  vs  Theme1 %-10s (акк %3d) %5.1f%%  → %+5.1f' %
          (k[0], k[1], a['домен'], a[key], a['_ex'], b['домен'], b[key], b['_ex'], a['_ex'] - b['_ex']))
p()

# ------------------------------------------------------------------ 6. ужесточение страты
p('=' * 100)
p('6. ЖЁСТКИЕ СТРАТЫ ВНУТРИ ПАРТИИ')
p('=' * 100)


def half(r):
    v = batches[r['_batch']]
    m = med([x['_wm'] for x in v])
    return 'ранний' if r['_wm'] <= m else 'поздний'


def quarter(r):
    v = sorted(batches[r['_batch']], key=lambda x: x['_wm'])
    i = [x['домен'] for x in v].index(r['домен'])
    return 'q%d' % (1 + i * 4 // len(v))


for name, fn in (('партия × паттерн имени', lambda r: r['_batch'] + (r['паттерн имени'],)),
                 ('партия × половина сеанса (номер wm-аккаунта ≤/> медианы партии)', lambda r: r['_batch'] + (half(r),)),
                 ('партия × четверть сеанса (ранг wm-аккаунта внутри партии, 4 корзины)', lambda r: r['_batch'] + (quarter(r),)),
                 ('партия × аккаунт свежий', lambda r: r['_batch'] + (r['аккаунт свежий'],)),
                 ('партия × паттерн имени × половина сеанса', lambda r: r['_batch'] + (r['паттерн имени'], half(r)))):
    for st in ('oe', 'dom'):
        o, q1, q2, rs = perm_oe(dec, fn, stat=st)
        if st == 'oe':
            p('  %s: страт с парой %d (Theme2 %d, Theme1 %d); O = %d, E(пул) = %.1f → O/E = %.3f, O/E по Theme1 = %.3f; p одн. = %.4f, двуст. = %.4f' %
              (name, len(rs['used']), rs['n_l'], rs['n_o'], rs['O'], rs['E'], o, rs['oer'], q1, q2))
        else:
            p('     по доменам: разность средних (Theme2 − Theme1) = %+.1f п.п., p одн. = %.4f, двуст. = %.4f' % (o, q1, q2))
p()
p('  Состав страт партия × паттерн имени (выход, %):')
for k in sorted(mixed):
    for pat in ('numeric', 'alpha_other'):
        a = [r for r in mixed[k] if r['паттерн имени'] == pat and r['_t'] == 'Theme1']
        b = [r for r in mixed[k] if r['паттерн имени'] == pat and r['_t'] == 'Theme2']
        p('     %s %02d %-11s Theme1 n=%2d выход %5.1f%% [%s] | Theme2 n=%2d выход %5.1f%% [%s]' %
          (k[0], k[1], pat, len(a), descr(a)['ex'], ' '.join('%.0f' % r['_ex'] for r in sorted(a, key=lambda r: r['_ex'])),
           len(b), descr(b)['ex'], ' '.join('%.0f' % r['_ex'] for r in sorted(b, key=lambda r: r['_ex']))))
p()
p('  Положение в сеансе (партия 20.08 12:00, номер wm-аккаунта): аккаунты ≥ 100 — хвост сеанса:')
for r in sorted(mixed[F_KEY], key=lambda r: r['_wm']):
    p('     акк %3d %-7s %-10s выход %5.1f%%  кликов/сайт %5.1f  рег %d' % (r['_wm'], r['_t'], r['домен'], r['_ex'], r['_clk'] / r['_S'], r['_reg']))
tail = [r for r in mixed[F_KEY] if r['_wm'] >= 100]
head = [r for r in mixed[F_KEY] if 80 <= r['_wm'] < 100]
p('  хвост (акк ≥100): %d доменов, выход %.1f%% (Theme2 %d из %d); середина (80–99): %d доменов, выход %.1f%% (Theme2 %d)' %
  (len(tail), descr(tail)['ex'], sum(1 for r in tail if r['_t'] == 'Theme2'), len(tail),
   len(head), descr(head)['ex'], sum(1 for r in head if r['_t'] == 'Theme2')))
p()

# ------------------------------------------------------------------ 7. регистрации
p('=' * 100)
p('7. РЕГИСТРАЦИИ ВНУТРИ ПАРТИИ')
p('=' * 100)
F = mixed[F_KEY]
t1F = [r for r in F if r['_t'] == 'Theme1']
t2F = [r for r in F if r['_t'] == 'Theme2']
p('  Все регистрации решающего теста — в партии 20.08 12:00 (в партии 19.08 23:00 их нет ни у кого).')
p('  Theme1: %d регистраций на %d доменах: %s' % (sum(r['_reg'] for r in t1F), len(t1F),
  ', '.join('%s %d' % (r['домен'], r['_reg']) for r in t1F if r['_reg'] > 0)))
p('  Theme2: %d регистраций на %d доменах: %s' % (sum(r['_reg'] for r in t2F), len(t2F),
  ', '.join('%s %d' % (r['домен'], r['_reg']) for r in t2F if r['_reg'] > 0)))
a = sum(1 for r in t2F if r['_reg'] > 0)
b = sum(1 for r in t1F if r['_reg'] > 0)
p('  Доменов хотя бы с одной регистрацией: Theme2 %d из %d, Theme1 %d из %d; Фишер двустор. p = %.3f' %
  (a, len(t2F), b, len(t1F), fisher_two_sided(a, len(t2F) - a, b, len(t1F) - b)))
t1x = [r for r in t1F if r['домен'] != '1908.team']
R1, S1, C1 = sum(r['_reg'] for r in t1x), sum(r['_S'] for r in t1x), sum(r['_clk'] for r in t1x)
R2, S2, C2 = sum(r['_reg'] for r in t2F), sum(r['_S'] for r in t2F), sum(r['_clk'] for r in t2F)
lam_site = R1 / S1 * S2
lam_clk = R1 / C1 * C2
p('  Без 1908.team: Theme1 %d рег / %d сайтов / %d поисковых кликов; Theme2 %d / %d / %d' % (R1, S1, C1, R2, S2, C2))
p('     ожидание для Theme2 по сайтам = %.2f → O/E = %.2f, пуассон P(X ≤ %d) = %.3f' % (lam_site, R2 / lam_site, R2, poisson_le(R2, lam_site)))
p('     ожидание по поисковым кликам = %.2f → O/E = %.2f, пуассон P(X ≤ %d) = %.3f' % (lam_clk, R2 / lam_clk, R2, poisson_le(R2, lam_clk)))
R1a, S1a, C1a = sum(r['_reg'] for r in t1F), sum(r['_S'] for r in t1F), sum(r['_clk'] for r in t1F)
p('  С 1908.team (как у тестировщика): по сайтам E = %.2f (O/E %.2f, p = %.3f); по кликам E = %.2f (O/E %.2f, p = %.3f)' %
  (R1a / S1a * S2, R2 / (R1a / S1a * S2), poisson_le(R2, R1a / S1a * S2), R1a / C1a * C2, R2 / (R1a / C1a * C2), poisson_le(R2, R1a / C1a * C2)))
p('  Рег на 10 тыс. поисковых кликов: Theme1 с 1908 = %.1f, без 1908 = %.1f; Theme2 = %.1f' % (1e4 * R1a / C1a, 1e4 * R1 / C1, 1e4 * R2 / C2))
t2x = [r for r in t2F if r['домен'] != '1467.team']
R2x, S2x, C2x = sum(r['_reg'] for r in t2x), sum(r['_S'] for r in t2x), sum(r['_clk'] for r in t2x)
lam_clk_x = R1 / C1 * C2x
p('  «По кликам» разницу делает один Theme2-домен 1467.team: %d поисковых кликов, 0 регистраций (известный эффект: больше кликов у домена → хуже отдача с клика).' %
  next(r['_clk'] for r in t2F if r['домен'] == '1467.team'))
p('     без 1908.team и без 1467.team: Theme1 %d рег / %d кликов, Theme2 %d / %d; E по кликам = %.2f → O/E = %.2f, пуассон P(X ≤ %d) = %.3f' %
  (R1, C1, R2x, C2x, lam_clk_x, R2x / lam_clk_x, R2x, poisson_le(R2x, lam_clk_x)))
p()

# ------------------------------------------------------------------ 8. клики на сайт
p('=' * 100)
p('8. ПОИСКОВЫЕ КЛИКИ НА САЙТ ВНУТРИ ПАРТИИ (объяснение, не цель)')
p('=' * 100)
for k in sorted(mixed):
    for t in ('Theme1', 'Theme2'):
        ds = [r for r in mixed[k] if r['_t'] == t]
        d = descr(ds)
        dsx = [r for r in ds if r['домен'] != '1908.team']
        dx = descr(dsx)
        p('  %s %02d %s: кликов/сайт %.1f (медиана по доменам %.1f)%s' %
          (k[0], k[1], t, d['cps'], med([r['_clk'] / r['_S'] for r in ds]),
           '; без 1908.team %.1f' % dx['cps'] if len(dsx) != len(ds) else ''))
p()

# ------------------------------------------------------------------ 9. вне team, та же партия
p('=' * 100)
p('9. ТА ЖЕ ПАРТИЯ, ОДНА ЗОНА ВНЕ .team (единичные домены — только как знак направления)')
p('=' * 100)
tail_all = [r for r in sl if r['зона'] != 'team']
bz = defaultdict(list)
for r in tail_all:
    bz[(r['_batch'], r['зона'])].append(r)
for k in sorted(bz):
    v = bz[k]
    if len(set(r['_t'] for r in v)) < 2:
        continue
    p('  партия %s %02d / %s сайтов, зона %s: %s' % (k[0][0], k[0][1], k[0][2], k[1],
      '; '.join('%s [%s] %.1f%% рег %d' % (r['домен'], r['_t'], r['_ex'], r['_reg']) for r in sorted(v, key=lambda r: r['_t']))))
p('  Все Theme2 вне team в партии 20.08 12:00: %s' % '; '.join('%s %.1f%%' % (r['домен'], r['_ex']) for r in tail_all if r['_t'] == 'Theme2' and r['_batch'] == F_KEY))
p('  Все Theme1 вне team в той же партии: %s' % '; '.join('%s %.1f%%' % (r['домен'], r['_ex']) for r in tail_all if r['_t'] == 'Theme1' and r['_batch'] == F_KEY))
p()

# ------------------------------------------------------------------ 10. семь суток и «догоняет ли» по доменам
p('=' * 100)
p('10. 7 СУТОК, ПО ДОМЕНАМ (тот же решающий срез)')
p('=' * 100)
obs7, p17, p27, rs7 = perm_oe(dec, batch_fn, metric='_v7', stat='oe')
obs7d, p17d, p27d, _ = perm_oe(dec, batch_fn, metric='_v7', stat='dom')
p('  7 суток: O/E пул = %.3f (по Theme1 %.3f), p одн. = %.4f, двуст. = %.4f; по доменам разность %+.1f п.п., p двуст. = %.4f' %
  (obs7, rs7['oer'], p17, p27, obs7d, p27d))
p()

# ------------------------------------------------------------------ ВЫВОД
p('=' * 100)
p('ВЫВОД СКЕПТИКА')
p('=' * 100)
dE1 = descr([r for r in mixed[E_KEY] if r['_t'] == 'Theme1'])
dE2 = descr([r for r in mixed[E_KEY] if r['_t'] == 'Theme2'])
dF1a = descr([r for r in mixed[F_KEY] if r['_t'] == 'Theme1'])
p('1. Грубый разрыв (0,54 по выходу, 3 регистрации вместо 23) — тень партии постановки: это уже показал тестировщик, спорить не с чем.')
p('2. «Остаточный эффект внутри партии» (O/E 0,74, p = 0,032) не выживает более жёсткой проверки:')
p('   — p односторонний; двусторонний p = %.3f (та же статистика, те же 10 000 перестановок).' % p2)
p('   — на уровне домена: ранговый стратифицированный тест p двустор. = %.3f, разность средних по доменам %+.1f п.п. (p = %.3f).' % (p2_r, obs_d, p2_d))
p('   — эффект целиком в одной партии 19.08 23:00 (4 Theme1 против 9 Theme2: медианы %.1f%% против %.1f%%); во второй партии 20.08 12:00' % (dE1['med'], dE2['med']))
p('     (12 против 8) медианы по доменам %.1f%% против %.1f%% — знак ОБРАТНЫЙ, а O/E по Theme1 0,81 держится на одном домене 1908.team (59,8%%).' % (dF1a['med'], dF2['med']))
p('   — без 1908.team O/E по Theme1 = %.2f, p одн. = %.3f, двуст. = %.3f; в партии 20.08 12:00 без него Theme2 %.1f%% против Theme1 %.1f%%.' % (rs_x['oer'], q1_x, q2_x, dF2['ex'], dF1['ex']))
p('   — парные сравнения по соседним номерам аккаунта (12 пар): по wm-аккаунту Theme2 хуже в 7, лучше в 5 (знаковый p = 0,77);')
p('     по cf-аккаунту хуже в 8, лучше в 4 (p = 0,39); медиана разности −4…−7 п.п.')
p('   — жёсткие страты: партия × паттерн имени O/E по Theme1 0,76 (p двуст. 0,067); партия × половина сеанса 0,73 (0,066);')
p('     партия × четверть сеанса 0,73 (0,196); партия × паттерн × половина 0,74 (0,088). Знак не меняется, но нигде не значимо.')
p('3. Регистрации внутри партии: 2 против 12, но 5 из 12 — один домен 1908.team; без него ожидание для Theme2 %.1f при 2 наблюдённых (p = %.2f);' % (lam_site, poisson_le(R2, lam_site)))
p('   доменов с регистрацией %d из %d против %d из %d (Фишер p = %.2f). На поисковый клик разница (p = 0,008) держится на одном' % (a, len(t2F), b, len(t1F), fisher_two_sided(a, len(t2F) - a, b, len(t1F) - b)))
p('   Theme2-домене 1467.team (11 478 кликов, 0 регистраций); без него и без 1908.team O/E = %.2f, p = %.2f. Разницы нет.' % (R2x / lam_clk_x, poisson_le(R2x, lam_clk_x)))
p('4. Вне .team в той же партии 20.08 12:00 единственная пара одной зоны — .buzz: Theme2 20,1% против Theme1 11,1% (знак обратный, n = 1 + 1).')
p()
p('ИТОГ: заявленный эффект шаблона (вдвое по выходу, в 4–8 раз по регистрациям) опровергнут как тень партии постановки;')
p('остаточный эффект ≈0,75 внутри партии не устойчив: он односторонний, держится на 4 доменах Theme1 одной партии и одном домене-выбросе')
p('другой, на уровне домена и в парах не отличим от нуля, в большей партии по медианам доменов меняет знак (24,6% против 23,6%).')
p('По заранее заданным критериям плана (O/E выхода ≤ 0,6 и регистраций ≤ 0,4 при p < 0,05, не совпадать с недоборной подгруппой)')
p('не выполнен ни один. На этом файле шаблон Theme2 — не фактор; вердикт «частично» завышен.')
p()
p('ЧТО С ЭТИМ ДЕЛАТЬ: ничего по шаблону — это знание, не рычаг. Не запрещать Theme2 и не приписывать ему потери. Если шаблон нужен как')
p('рычаг — нужен запуск с Theme1 и Theme2 вперемешку в одной партии (одна дата, один час, один записанный набор, по 20–30 доменов) и')
p('заранее заданная двусторонняя проверка на уровне домена. На уже запущенных данных проверяемо одно: дозаписать набор контента для')
p('106 доменов 19–20.08 и пересчитать тем же скриптом со стратой «набор + день + партия».')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT, file=sys.stderr)

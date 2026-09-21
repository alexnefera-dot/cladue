#!/usr/bin/env python3
"""
Гипотеза №19. Качество регистраций падает с ростом выхода домена: доля первых
депозитов (ФД) на регистрацию у доменов с выходом 30 %+ в 2–4 раза ниже, чем при
выходе 10–30 %, поэтому по ФД на 100 сайтов домены с выходом выше ~30 % не лучше
доменов с выходом 20–30 % (насыщение есть, но только в депозитах). Отдельно
проверить, не сводится ли падение к повторным регистрациям с одного сайта (№17).

Что проверяем.
  Выход домена = «выход 3 суток %» (= вышли за 3 суток / сайтов). Бины: 0–10
  (отдельно, регистраций мало), 10–30, 30+; в описательных таблицах ещё 10–20,
  20–30, 30–40, 40+ — как в формулировке гипотезы.
  Единица основного теста — регистрация в окне 3 суток, с меткой «дала ФД в окне»
  и выходом её домена. Так как в своде есть только числа по домену (регистраций
  в окне, ФД в окне), регистрации домена — это R одинаковых единиц, из которых
  F помечены ФД; какая именно — не важно, статистики зависят только от сумм.

Как проверяем.
  Фильтры: окно закрыто = да; дней ≥ 2; без выбросов 3615.team и 3286.team
  (у них 2 и 0 регистраций в окне, оба без ФД — на итог не влияют, но
  исключены для единообразия). «КОНТЕНТ НЕ ЗАПИСАН» (335 доменов до 24.08)
  оставлен в описательных таблицах, чтобы воспроизвести цифры гипотезы, но в
  стратифицированных тестах сначала исключён, затем добавлен отдельным пулом
  «КОНТЕНТ НЕ ЗАПИСАН + день» (это не набор контента, а отсутствие записи,
  сцепленное с датой, — оговорено).
  1. Описание: по бинам выхода — доменов, сайтов, доменов с регистрацией,
     регистраций, ФД, ФД/рег с точным биномиальным ДИ (Клоппер–Пирсон),
     регистраций и ФД на 100 сайтов с точным пуассоновским ДИ.
  2. Главный тест без страты: точный тест 2×2 (ФД / не-ФД × 10–30 / 30+),
     односторонний (ФД/рег в 30+ ниже), гипергеометрическое распределение;
     отношение ФД/рег с приближённым ДИ (по логарифму отношения).
  3. Страта «набор контента + день запуска» (пул): внутри пула метки ФД
     перемешиваются между регистрациями пула 5000 раз (random.seed(1)).
     Ожидание E(бин) = Σ по пулам ФД_пула × рег_бина_в_пуле / рег_пула; O/E.
     p = доля перестановок, где ФД/рег(30+) ≤ наблюдённого; отдельно p для
     отношения ФД/рег(30+)/ФД/рег(10–30) и для тренда (средний выход домена
     у ФД-регистраций ≤ наблюдённого — без бинов). Информативны только пулы,
     где есть ФД и регистрации из разных бинов; остальные входят константой.
     Варианты: без «КОНТЕНТ НЕ ЗАПИСАН»; с ним (пул = запись + день);
     набор + день + зона.
  4. Повтор на «регистраций» / «ФД» за всё время для запусков ≤ 2026-09-13
     (чтобы депозит успел прийти после регистрации в конце окна): те же
     тесты 2 и 3.
  5. Контроль повторов с одного сайта: единица — «сайтов с регистрацией»
     (за всё время; в окне такого поля нет), метка — «на сайте был ФД»
     (по №17 ФД ложится на сайт регистрации; у 9051.team ФД = 2 при 1 сайте —
     обрезаем до 1 и говорим об этом). ФД / сайт с регистрацией по бинам, точный
     тест 2×2 и перестановка внутри пулов. Если падение ФД/рег есть, а ФД/сайт
     ровный — это повторы; если падает и ФД/сайт — это не повторы.
     Дополнительно: ФД/рег по бинам выхода внутри классов «регистраций у домена»
     1 / 2 / 3+ (у доменов с 1 регистрацией повторов нет по построению).
  6. Внутри пула без бинов: домены выше медианы выхода своего пула против
     остальных (перестановка меток ФД внутри пула) — самая прямая проверка
     «тот же контент, тот же день, домен вышел лучше — регистрации хуже?».
  7. ФД на 100 сайтов по бинам 20–30 / 30–40 / 40+: пуассоновские ДИ и
     условный биномиальный тест (при заданной сумме ФД двух бинов доля ФД в
     бине следует биномиальному с p = доля сайтов); стратифицированный O/E по
     сайтам внутри пулов (ФД пула раскладываются по доменам пула ∝ сайтов,
     5000 раз) для регистраций и ФД.
  8. Описательно: зоны × бины; неделя запуска (где сидят регистрации 30+ и
     какой там ФД/рег — тень даты); бренды.

Критерии из постановки: подтверждена — ФД/рег(30+) ≤ 0,5 × ФД/рег(10–30) при
p < 0,05 в обоих окнах (в окне и за всё время) и ФД/100 сайтов в 30–40 и 40+ не
выше, чем в 20–30; опровергнута — доли одинаковы в пределах шума, или падение
уходит при счёте на сайт с регистрацией (тогда это повторы, №17, а не выход).
"""
import collections
import csv
import datetime
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h19_fd_rate_vs_exit.txt')
OUTLIERS = ('3615.team', '3286.team')
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 5000
SEED = 1
LATE_CUT = '2026-09-13'   # для «за всё время»: запуск не позже этой даты
BINS5 = ('0-10', '10-20', '20-30', '30-40', '40+')
BINS3 = ('0-10', '10-30', '30+')
ZONES = ('team', 'lol', 'casino', 'buzz')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)

    def flush(self):
        sys.stdout.flush()
        self.f.flush()


def p(*args):
    s = ' '.join(str(a) for a in args)
    TEE.write(s + '\n')


# ---------------------------------------------------------------- вспомогательное
def fnum(s, default=0.0):
    s = (s or '').strip()
    if s == '':
        return default
    return float(s.replace(',', '.'))


def inum(s, default=0):
    s = (s or '').strip()
    if s == '':
        return default
    return int(float(s))


def bin5(e):
    if e < 10:
        return '0-10'
    if e < 20:
        return '10-20'
    if e < 30:
        return '20-30'
    if e < 40:
        return '30-40'
    return '40+'


def bin3(e):
    if e < 10:
        return '0-10'
    if e < 30:
        return '10-30'
    return '30+'


def zone4(z):
    return z if z in ZONES else 'прочие'


def r3(x):
    return '%.3f' % x


def div(a, b):
    return a / b if b else float('nan')


# ---------------------------------------------------------------- статистика (stdlib)
def log_comb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_cdf(k, n, q):
    """P(X <= k), X ~ Bin(n, q)."""
    if q <= 0:
        return 1.0
    if q >= 1:
        return 1.0 if k >= n else 0.0
    s = 0.0
    lq, l1q = math.log(q), math.log(1 - q)
    for i in range(0, min(k, n) + 1):
        s += math.exp(log_comb(n, i) + i * lq + (n - i) * l1q)
    return min(1.0, s)


def cp_ci(k, n, alpha=0.05):
    """Точный биномиальный ДИ Клоппера–Пирсона для доли k/n."""
    if n == 0:
        return (float('nan'), float('nan'))
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            # P(X >= k | m) = 1 - P(X <= k-1 | m); ищем = alpha/2
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
    return (lo, hi)


def pois_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = 0.0
    for i in range(0, k + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


def pois_ci(k, alpha=0.05):
    """Точный ДИ для среднего Пуассона по наблюдённому k."""
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, k + 1.0
        for _ in range(80):
            m = (a + b) / 2
            if 1 - pois_cdf(k - 1, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    a, b = float(k), 10.0 * k + 20.0
    for _ in range(80):
        m = (a + b) / 2
        if pois_cdf(k, m) > alpha / 2:
            a = m
        else:
            b = m
    hi = (a + b) / 2
    return (lo, hi)


def fisher_lower(a, b, c, d):
    """Односторонний точный тест: P(X <= a) для таблицы [[a, b], [c, d]],
    X — число «успехов» (a) в первой строке при фиксированных краях."""
    n1 = a + b
    k = a + c
    n = a + b + c + d
    lo = max(0, k - (n - n1))
    s = 0.0
    for i in range(lo, a + 1):
        s += math.exp(log_comb(k, i) + log_comb(n - k, n1 - i) - log_comb(n, n1))
    return min(1.0, s)


def ratio_ci(k1, n1, k2, n2):
    """Отношение долей k1/n1 : k2/n2 с приближённым 95 % ДИ (лог-шкала; +0,5 при нулях)."""
    if k1 == 0 or k2 == 0:
        k1a, k2a, n1a, n2a = k1 + 0.5, k2 + 0.5, n1 + 0.5, n2 + 0.5
    else:
        k1a, k2a, n1a, n2a = k1, k2, n1, n2
    rr = (k1a / n1a) / (k2a / n2a)
    se = math.sqrt(max(1e-12, 1 / k1a - 1 / n1a + 1 / k2a - 1 / n2a))
    return rr, rr * math.exp(-1.96 * se), rr * math.exp(1.96 * se)


def cond_binom_upper(k_a, n_a, k_b, n_b):
    """Сравнение двух пуассоновских частот: при заданной сумме ФД доля в A
    ~ Bin(k_a + k_b, n_a/(n_a+n_b)). Возвращает P(X >= k_a) и P(X <= k_a)."""
    k = k_a + k_b
    q = n_a / (n_a + n_b)
    up = 1 - binom_cdf(k_a - 1, k, q) if k_a > 0 else 1.0
    lo = binom_cdf(k_a, k, q)
    return up, lo


def quant(xs, q):
    xs = sorted(xs)
    if not xs:
        return float('nan')
    i = int(round(q * (len(xs) - 1)))
    return xs[max(0, min(len(xs) - 1, i))]


# ---------------------------------------------------------------- перестановки
def perm_labels(units, groups, nperm, rng):
    """units: список (pool, group, exit, n_units, n_marked) — домен даёт n_units
    одинаковых единиц (регистраций или сайтов), из них n_marked с меткой ФД.
    Внутри пула метки перемешиваются между всеми единицами пула.
    Возвращает наблюдённые ФД по группам, E по группам, число единиц по группам,
    список нулевых (ФД по группам, тренд), наблюдённый тренд, сведения о пулах."""
    by_pool = collections.defaultdict(list)
    for u in units:
        if u[3] > 0:
            by_pool[u[0]].append(u)
    n_by = collections.Counter()
    obs = collections.Counter()
    E = collections.defaultdict(float)
    const = collections.Counter()
    const_tr = 0.0
    obs_tr = 0.0
    var_pools = []
    n_inf = 0
    inf_units = collections.Counter()
    inf_fd = collections.Counter()
    for pool, us in by_pool.items():
        k = sum(u[4] for u in us)
        n = sum(u[3] for u in us)
        for u in us:
            n_by[u[1]] += u[3]
            obs[u[1]] += u[4]
            obs_tr += u[4] * u[2]
        grp_n = collections.Counter()
        for u in us:
            grp_n[u[1]] += u[3]
        for g, gn in grp_n.items():
            E[g] += k * gn / n
        exits = set(u[2] for u in us)
        if k == 0 or n == 1 or (len(grp_n) == 1 and len(exits) == 1):
            for u in us:
                const[u[1]] += u[4]
                const_tr += u[4] * u[2]
            continue
        # развернуть единицы
        g_list, e_list = [], []
        for u in us:
            g_list.extend([u[1]] * u[3])
            e_list.extend([u[2]] * u[3])
        var_pools.append((k, g_list, e_list))
        if len(grp_n) > 1:
            n_inf += 1
            for g, gn in grp_n.items():
                inf_units[g] += gn
            for u in us:
                inf_fd[u[1]] += u[4]
    null = []
    for _ in range(nperm):
        cnt = collections.Counter(const)
        tr = const_tr
        for k, g_list, e_list in var_pools:
            for i in rng.sample(range(len(g_list)), k):
                cnt[g_list[i]] += 1
                tr += e_list[i]
        null.append((cnt, tr))
    info = {'pools': len(by_pool), 'informative': n_inf, 'inf_units': inf_units, 'inf_fd': inf_fd}
    return obs, E, n_by, null, obs_tr, info


def list_pools(doms, regf, fdf, title):
    """Пулы, где есть регистрации и в 10–30, и в 30+ (сравнение «как на как»)."""
    pools = collections.defaultdict(list)
    for d in doms:
        pools[d['pool']].append(d)
    rows = []
    for k, ds in pools.items():
        cnt = {b: [0, 0, 0] for b in BINS3}
        for d in ds:
            cnt[d['bin3']][0] += 1
            cnt[d['bin3']][1] += d[regf]
            cnt[d['bin3']][2] += d[fdf]
        if cnt['10-30'][1] > 0 and cnt['30+'][1] > 0:
            rows.append((k, cnt))
    rows.sort(key=lambda x: -(x[1]['10-30'][1] + x[1]['30+'][1]))
    p('  ' + title)
    p('    набор контента | день | 0–10: доменов (рег/ФД) | 10–30: доменов (рег/ФД) | 30+: доменов (рег/ФД) | ФД/рег 10–30 | ФД/рег 30+')
    s1 = s2 = f1 = f2 = 0
    for k, cnt in rows:
        s1 += cnt['10-30'][1]; f1 += cnt['10-30'][2]; s2 += cnt['30+'][1]; f2 += cnt['30+'][2]
        p('    %-40s | %s | %3d (%2d/%2d) | %3d (%2d/%2d) | %3d (%2d/%2d) | %s | %s' % (
            k[0][:40], k[1], cnt['0-10'][0], cnt['0-10'][1], cnt['0-10'][2], cnt['10-30'][0], cnt['10-30'][1], cnt['10-30'][2],
            cnt['30+'][0], cnt['30+'][1], cnt['30+'][2], r3(div(cnt['10-30'][2], cnt['10-30'][1])), r3(div(cnt['30+'][2], cnt['30+'][1]))))
    p('    итого по этим %d пулам: 10–30 — %d рег, %d ФД (%s); 30+ — %d рег, %d ФД (%s)' % (len(rows), s1, f1, r3(div(f1, s1)), s2, f2, r3(div(f2, s2))))


def report_perm(title, units, groups, ga, gb, nperm, rng, unit_name='регистраций'):
    """ga — «худшая» группа (30+), gb — базовая (10–30). p для ФД/ед(ga) ≤ набл.,
    для отношения ga/gb ≤ набл., для тренда (средний выход у ФД) ≤ набл."""
    obs, E, n_by, null, obs_tr, info = perm_labels(units, groups, nperm, rng)
    p('  ' + title)
    p('    пулов с ФД: %d; информативных (ФД и единицы из разных бинов в одном пуле): %d' % (
        sum(1 for _ in set(u[0] for u in units if u[4] > 0)), info['informative']))
    p('    в информативных пулах: ' + '; '.join('%s: %s %d, ФД %d (%.3f)' % (
        g, unit_name, info['inf_units'][g], info['inf_fd'][g], div(info['inf_fd'][g], info['inf_units'][g]))
        for g in groups if info['inf_units'][g] > 0))
    p('    бин | %s | ФД набл. | ФД ожид. (по пулам) | O/E | ФД/ед набл.' % unit_name)
    for g in groups:
        p('    %5s | %6d | %3d | %6.2f | %s | %s' % (
            g, n_by[g], obs[g], E[g], ('%.2f' % (obs[g] / E[g])) if E[g] > 0 else '  —', r3(div(obs[g], n_by[g]))))
    fd_tot = sum(obs.values())
    units_tot = sum(n_by.values())
    obs_rate_a = div(obs[ga], n_by[ga])
    obs_rate_b = div(obs[gb], n_by[gb])
    obs_ratio = div(obs_rate_a, obs_rate_b) if obs_rate_b else float('nan')
    p_a = sum(1 for cnt, _ in null if cnt[ga] <= obs[ga]) / len(null)
    p_a_hi = sum(1 for cnt, _ in null if cnt[ga] >= obs[ga]) / len(null)
    ratios = []
    for cnt, _ in null:
        ra = div(cnt[ga], n_by[ga]) if n_by[ga] else float('nan')
        rb = div(cnt[gb], n_by[gb]) if n_by[gb] else float('nan')
        ratios.append(ra / rb if rb else float('inf'))
    p_ratio = sum(1 for r in ratios if r <= obs_ratio) / len(ratios)
    fin = [r for r in ratios if math.isfinite(r)]
    obs_mean_exit = obs_tr / fd_tot if fd_tot else float('nan')
    null_means = [tr / fd_tot for _, tr in null] if fd_tot else []
    p_tr = sum(1 for m in null_means if m <= obs_mean_exit) / len(null_means) if null_means else float('nan')
    p('    ФД/ед %s = %s, %s = %s; отношение %s/%s = %.2f' % (ga, r3(obs_rate_a), gb, r3(obs_rate_b), ga, gb, obs_ratio))
    p('    перестановка меток ФД внутри пулов (%d): p(ФД в %s ≤ набл.) = %.4f [p(≥) = %.4f]; нулевой интервал ФД(%s) %d–%d' % (
        len(null), ga, p_a, p_a_hi, ga, quant([cnt[ga] for cnt, _ in null], 0.025), quant([cnt[ga] for cnt, _ in null], 0.975)))
    p('    p(отношение ФД/ед %s/%s ≤ %.2f) = %.4f; нулевой интервал отношения %.2f–%.2f' % (
        ga, gb, obs_ratio, p_ratio, quant(fin, 0.025) if fin else float('nan'), quant(fin, 0.975) if fin else float('nan')))
    p('    тренд без бинов: средний выход домена у ФД-единиц %.1f %% (у всех единиц %.1f %%); p(≤ набл.) = %.4f; нулевой интервал %.1f–%.1f' % (
        obs_mean_exit, div(sum(u[2] * u[3] for u in units), units_tot), p_tr,
        quant(null_means, 0.025) if null_means else float('nan'), quant(null_means, 0.975) if null_means else float('nan')))
    return {'obs': obs, 'E': E, 'n': n_by, 'p_a': p_a, 'p_ratio': p_ratio, 'ratio': obs_ratio, 'p_tr': p_tr,
            'rate_a': obs_rate_a, 'rate_b': obs_rate_b, 'inf': info,
            'null_ratio_lo': quant(fin, 0.025) if fin else float('nan'), 'null_ratio_hi': quant(fin, 0.975) if fin else float('nan')}


def perm_on_sites(doms, field, groups, nperm, rng):
    """Стратифицированный O/E «на сайт»: события поля field пула раскладываются
    по доменам пула с вероятностью ∝ сайтов. Возвращает O, E, сайты, p(≥), p(≤)."""
    by_pool = collections.defaultdict(list)
    for d in doms:
        by_pool[d['pool']].append(d)
    obs = collections.Counter()
    E = collections.defaultdict(float)
    sites_by = collections.Counter()
    const = collections.Counter()
    var_pools = []
    for pool, ds in by_pool.items():
        k = sum(d[field] for d in ds)
        s = sum(d['sites'] for d in ds)
        for d in ds:
            obs[d['bin3']] += d[field]
            sites_by[d['bin3']] += d['sites']
            E[d['bin3']] += k * d['sites'] / s if s else 0
        bins = set(d['bin3'] for d in ds)
        if k == 0 or len(bins) == 1:
            for d in ds:
                const[d['bin3']] += d[field]
            continue
        var_pools.append((k, [d['bin3'] for d in ds], [d['sites'] for d in ds]))
    null = []
    for _ in range(nperm):
        cnt = collections.Counter(const)
        for k, b_list, w_list in var_pools:
            for b in rng.choices(b_list, weights=w_list, k=k):
                cnt[b] += 1
        null.append(cnt)
    res = {}
    for g in groups:
        res[g] = (obs[g], E[g], sites_by[g],
                  sum(1 for c in null if c[g] >= obs[g]) / len(null),
                  sum(1 for c in null if c[g] <= obs[g]) / len(null))
    return res, len(var_pools)


# ---------------------------------------------------------------- данные
def load():
    with open(SRC, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return rows


def prep(rows):
    """Фильтры с печатью числа исключённых."""
    p('1. Фильтры')
    n0 = len(rows)
    ex_win = [r for r in rows if r['окно закрыто'].strip() != 'да']
    rows = [r for r in rows if r['окно закрыто'].strip() == 'да']
    p('  исключено: окно закрыто = нет: %d' % len(ex_win))
    ex_days = [r for r in rows if r['дней'].strip() == '1']
    rows = [r for r in rows if r['дней'].strip() != '1']
    p('  исключено: дней = 1 (ещё не было дня 2): %d' % len(ex_days))
    ex_out = [r for r in rows if r['домен'] in OUTLIERS]
    rows = [r for r in rows if r['домен'] not in OUTLIERS]
    p('  исключено: выброс 3615.team / 3286.team: %d (у них регистраций в окне %s, ФД в окне %s)' % (
        len(ex_out), '+'.join(r['регистраций в окне 3 суток'] for r in ex_out), '+'.join(r['ФД в окне 3 суток'] for r in ex_out)))
    p('  осталось доменов: %d из %d' % (len(rows), n0))
    doms = []
    for r in rows:
        e = fnum(r['выход 3 суток %'])
        d = {
            'dom': r['домен'], 'zone': zone4(r['зона'].strip()), 'day': r['день запуска'].strip(),
            'content': r['набор контента'].strip(), 'family': r['семейство'].strip(),
            'exit': e, 'bin5': bin5(e), 'bin3': bin3(e),
            'sites': inum(r['сайтов в окне']), 'out3': inum(r['вышли за 3 суток']),
            'reg_w': inum(r['регистраций в окне 3 суток']), 'fd_w': inum(r['ФД в окне 3 суток']),
            'reg_a': inum(r['регистраций']), 'fd_a': inum(r['ФД']), 'S': inum(r['сайтов с регистрацией']),
            'brands': r['какие бренды конвертили'].strip(),
        }
        d['pool'] = (d['content'], d['day'])
        d['pool_z'] = (d['content'], d['day'], d['zone'])
        d['noc'] = d['content'] == NOC
        doms.append(d)
    p('  из них «КОНТЕНТ НЕ ЗАПИСАН»: %d (в описательных таблицах оставлены — так воспроизводятся цифры гипотезы; в стратах — отдельно без них и с ними)' % sum(1 for d in doms if d['noc']))
    p('  проверка на файле: ФД в окне > регистраций в окне — %d доменов; ФД > сайтов с регистрацией — %d (%s)' % (
        sum(1 for d in doms if d['fd_w'] > d['reg_w']), sum(1 for d in doms if d['fd_a'] > d['S']),
        ', '.join('%s: рег %d, сайтов %d, ФД %d' % (d['dom'], d['reg_a'], d['S'], d['fd_a']) for d in doms if d['fd_a'] > d['S'])))
    p('  запусков ≤ %s (для расчёта «за всё время»): %d доменов' % (LATE_CUT, sum(1 for d in doms if d['day'] <= LATE_CUT)))
    return doms


# ---------------------------------------------------------------- таблицы
def table_bins(doms, bins, binkey, regf, fdf, title, sitesf='sites', with_S=False):
    p('  ' + title)
    hdr = '  бин выхода | доменов | сайтов | доменов с рег. | регистраций | ФД | ФД/рег [95 % ДИ] | рег/100 сайтов | ФД/100 сайтов [95 % ДИ]'
    if with_S:
        hdr += ' | сайтов с рег. | ФД/сайт с рег. [ДИ] | повторов (R−S)/R'
    p(hdr)
    out = {}
    for b in bins:
        ds = [d for d in doms if d[binkey] == b]
        nd = len(ds)
        sites = sum(d[sitesf] for d in ds)
        reg = sum(d[regf] for d in ds)
        fd = sum(d[fdf] for d in ds)
        ndr = sum(1 for d in ds if d[regf] > 0)
        ci = cp_ci(fd, reg)
        pci = pois_ci(fd)
        line = '  %10s | %7d | %6d | %6d | %5d | %3d | %s [%s–%s] | %6.3f | %6.3f [%.3f–%.3f]' % (
            b, nd, sites, ndr, reg, fd, r3(div(fd, reg)), r3(ci[0]), r3(ci[1]),
            100 * div(reg, sites), 100 * div(fd, sites), 100 * pci[0] / sites if sites else 0, 100 * pci[1] / sites if sites else 0)
        row = {'n': nd, 'sites': sites, 'reg': reg, 'fd': fd, 'ndr': ndr}
        if with_S:
            S = sum(d['S'] for d in ds)
            fdS = sum(min(d['fd_a'], d['S']) for d in ds)
            sci = cp_ci(fdS, S)
            line += ' | %5d | %s [%s–%s] | %s' % (S, r3(div(fdS, S)), r3(sci[0]), r3(sci[1]), r3(div(reg - S, reg)))
            row.update({'S': S, 'fdS': fdS})
        p(line)
        out[b] = row
    tot_reg = sum(v['reg'] for v in out.values())
    tot_fd = sum(v['fd'] for v in out.values())
    p('  итого: доменов %d, сайтов %d, регистраций %d, ФД %d, ФД/рег %s' % (
        sum(v['n'] for v in out.values()), sum(v['sites'] for v in out.values()), tot_reg, tot_fd, r3(div(tot_fd, tot_reg))))
    return out


def fisher_block(t, ga, gb, regkey='reg', fdkey='fd', label='ФД/рег'):
    a, n_a = t[ga][fdkey], t[ga][regkey]
    c, n_b = t[gb][fdkey], t[gb][regkey]
    pl = fisher_lower(a, n_a - a, c, n_b - c)
    rr, lo, hi = ratio_ci(a, n_a, c, n_b)
    p('  точный тест 2×2 (%s в %s ниже, чем в %s): %d/%d = %s против %d/%d = %s; отношение %.2f (ДИ %.2f–%.2f); p = %.4f' % (
        label, ga, gb, a, n_a, r3(div(a, n_a)), c, n_b, r3(div(c, n_b)), rr, lo, hi, pl))
    return pl, rr


# ---------------------------------------------------------------- основной ход
def main():
    global TEE
    TEE = Tee(OUT)
    rng = random.Random(SEED)
    p('Гипотеза №19: ФД на регистрацию падает с ростом выхода домена; ФД на 100 сайтов выходит на плато после 30 %; не повторы ли это с одного сайта')
    p('Источник: %s' % os.path.relpath(SRC, REPO))
    rows = load()
    p('строк (доменов) в своде: %d' % len(rows))
    p('')
    doms = prep(rows)
    late = [d for d in doms if d['day'] <= LATE_CUT]
    p('')

    # ---------------- 2. описание
    p('=' * 100)
    p('2. ОПИСАНИЕ ПО БИНАМ ВЫХОДА (без страты; «КОНТЕНТ НЕ ЗАПИСАН» включён — как в формулировке гипотезы)')
    p('=' * 100)
    t5w = table_bins(doms, BINS5, 'bin5', 'reg_w', 'fd_w', 'Окно 3 суток, 5 бинов (все %d доменов):' % len(doms))
    p('')
    t3w = table_bins(doms, BINS3, 'bin3', 'reg_w', 'fd_w', 'Окно 3 суток, 3 бина:')
    p('')
    t5a = table_bins(late, BINS5, 'bin5', 'reg_a', 'fd_a', 'За всё время, запуск ≤ %s (%d доменов), 5 бинов:' % (LATE_CUT, len(late)), with_S=True)
    p('')
    t3a = table_bins(late, BINS3, 'bin3', 'reg_a', 'fd_a', 'За всё время, запуск ≤ %s, 3 бина:' % LATE_CUT, with_S=True)
    p('')
    nn = [d for d in doms if not d['noc']]
    t3w_nn = table_bins(nn, BINS3, 'bin3', 'reg_w', 'fd_w', 'Окно 3 суток, 3 бина, без «КОНТЕНТ НЕ ЗАПИСАН» (%d доменов):' % len(nn))
    p('')
    nl = [d for d in late if not d['noc']]
    t3a_nn = table_bins(nl, BINS3, 'bin3', 'reg_a', 'fd_a', 'За всё время ≤ %s, 3 бина, без «КОНТЕНТ НЕ ЗАПИСАН» (%d доменов):' % (LATE_CUT, len(nl)), with_S=True)
    p('')

    # ---------------- 3. точный тест без страты
    p('=' * 100)
    p('3. ГЛАВНЫЙ ТЕСТ БЕЗ СТРАТЫ: ФД/рег в 30+ против 10–30')
    p('=' * 100)
    p('  Окно 3 суток, все домены:')
    pw, rrw = fisher_block(t3w, '30+', '10-30')
    p('  Окно 3 суток, без «КОНТЕНТ НЕ ЗАПИСАН»:')
    pw_nn, rrw_nn = fisher_block(t3w_nn, '30+', '10-30')
    p('  За всё время, запуск ≤ %s, все домены:' % LATE_CUT)
    pa, rra = fisher_block(t3a, '30+', '10-30')
    p('  За всё время, запуск ≤ %s, без «КОНТЕНТ НЕ ЗАПИСАН»:' % LATE_CUT)
    pa_nn, rra_nn = fisher_block(t3a_nn, '30+', '10-30')
    p('  Для полноты — 0–10 против 10–30 (окно): %d/%d = %s против %d/%d = %s' % (
        t3w['0-10']['fd'], t3w['0-10']['reg'], r3(div(t3w['0-10']['fd'], t3w['0-10']['reg'])),
        t3w['10-30']['fd'], t3w['10-30']['reg'], r3(div(t3w['10-30']['fd'], t3w['10-30']['reg']))))
    p('')

    # ---------------- 4. страта набор контента + день, окно
    p('=' * 100)
    p('4. СТРАТА «НАБОР КОНТЕНТА + ДЕНЬ ЗАПУСКА»: перестановка меток ФД между регистрациями пула (%d раз, seed %d), окно 3 суток' % (NPERM, SEED))
    p('=' * 100)
    p('  Единица — регистрация в окне; группа — бин выхода её домена. Регистрации из пулов, где нет ФД или все домены в одном бине с одинаковым выходом, входят константой.')
    units_w_nn = [(d['pool'], d['bin3'], d['exit'], d['reg_w'], d['fd_w']) for d in doms if not d['noc']]
    res_w_nn = report_perm('4.1 Без «КОНТЕНТ НЕ ЗАПИСАН», пул = набор + день', units_w_nn, BINS3, '30+', '10-30', NPERM, rng)
    p('')
    units_w_all = [(d['pool'], d['bin3'], d['exit'], d['reg_w'], d['fd_w']) for d in doms]
    res_w_all = report_perm('4.2 С «КОНТЕНТ НЕ ЗАПИСАН» отдельным пулом «запись + день» (оговорка: это не набор, а отсутствие записи)', units_w_all, BINS3, '30+', '10-30', NPERM, rng)
    p('')
    units_wz_nn = [(d['pool_z'], d['bin3'], d['exit'], d['reg_w'], d['fd_w']) for d in doms if not d['noc']]
    res_wz_nn = report_perm('4.3 Без «КОНТЕНТ НЕ ЗАПИСАН», пул = набор + день + зона', units_wz_nn, BINS3, '30+', '10-30', NPERM, rng)
    p('')
    list_pools(nn, 'reg_w', 'fd_w', '4.4 Пулы (набор + день) без «КОНТЕНТ НЕ ЗАПИСАН», где есть регистрации в окне и в 10–30, и в 30+:')
    p('')
    list_pools([d for d in doms if d['noc']], 'reg_w', 'fd_w', '4.5 То же среди пулов «КОНТЕНТ НЕ ЗАПИСАН + день»:')
    p('')
    p('  4.6 Сколько регистраций 30+ вообще попадает в информативные пулы (остальные сравнить не с чем — в их пуле все домены в одном бине):')
    for lab, units in (('без НЗ', units_w_nn), ('с НЗ', units_w_all)):
        pools = collections.defaultdict(lambda: collections.defaultdict(int))
        for u in units:
            pools[u[0]][u[1]] += u[3]
        r30 = sum(v['30+'] for v in pools.values())
        r30_inf = sum(v['30+'] for v in pools.values() if v['30+'] > 0 and (v['10-30'] > 0 or v['0-10'] > 0))
        r30_inf2 = sum(v['30+'] for v in pools.values() if v['30+'] > 0 and v['10-30'] > 0)
        p('    %s: регистраций 30+ всего %d; из них в пулах, где есть и регистрации 10–30: %d; где есть регистрации любого другого бина: %d' % (lab, r30, r30_inf2, r30_inf))
    p('')

    # ---------------- 5. за всё время
    p('=' * 100)
    p('5. ЗА ВСЁ ВРЕМЯ (запуск ≤ %s): регистрации и ФД без ограничения окном — снимает задержку депозита' % LATE_CUT)
    p('=' * 100)
    units_a_nn = [(d['pool'], d['bin3'], d['exit'], d['reg_a'], d['fd_a']) for d in late if not d['noc']]
    res_a_nn = report_perm('5.1 Регистрации, без «КОНТЕНТ НЕ ЗАПИСАН», пул = набор + день', units_a_nn, BINS3, '30+', '10-30', NPERM, rng)
    p('')
    units_a_all = [(d['pool'], d['bin3'], d['exit'], d['reg_a'], d['fd_a']) for d in late]
    res_a_all = report_perm('5.2 Регистрации, с «КОНТЕНТ НЕ ЗАПИСАН» отдельным пулом', units_a_all, BINS3, '30+', '10-30', NPERM, rng)
    p('')

    # ---------------- 6. контроль повторов: единица — сайт с регистрацией
    p('=' * 100)
    p('6. КОНТРОЛЬ ПОВТОРОВ С ОДНОГО САЙТА: единица — сайт с регистрацией (за всё время, запуск ≤ %s)' % LATE_CUT)
    p('=' * 100)
    p('  Метка сайта — «на сайте был ФД» (ФД ложится на сайт регистрации, №17). ФД обрезаны до числа сайтов с регистрацией у домена (затронуто: %s).' % (
        ', '.join('%s (ФД %d → %d)' % (d['dom'], d['fd_a'], min(d['fd_a'], d['S'])) for d in late if d['fd_a'] > d['S']) or 'никого'))
    p('  Если бы падение ФД/рег было из-за повторов, ФД/сайт по бинам был бы ровным.')
    p('  6.1 Без страты, без «КОНТЕНТ НЕ ЗАПИСАН»:')
    pS_nn, rrS_nn = fisher_block(t3a_nn, '30+', '10-30', regkey='S', fdkey='fdS', label='ФД/сайт с рег.')
    p('  6.1 Без страты, все домены:')
    pS_all, rrS_all = fisher_block(t3a, '30+', '10-30', regkey='S', fdkey='fdS', label='ФД/сайт с рег.')
    units_S_nn = [(d['pool'], d['bin3'], d['exit'], d['S'], min(d['fd_a'], d['S'])) for d in late if not d['noc']]
    res_S_nn = report_perm('6.2 Страта набор + день, без «КОНТЕНТ НЕ ЗАПИСАН», единица — сайт с регистрацией', units_S_nn, BINS3, '30+', '10-30', NPERM, rng, unit_name='сайтов с рег.')
    p('')
    units_S_all = [(d['pool'], d['bin3'], d['exit'], d['S'], min(d['fd_a'], d['S'])) for d in late]
    res_S_all = report_perm('6.3 Страта набор + день, с «КОНТЕНТ НЕ ЗАПИСАН» отдельным пулом, единица — сайт с регистрацией', units_S_all, BINS3, '30+', '10-30', NPERM, rng, unit_name='сайтов с рег.')
    p('')
    p('  6.4 ФД/рег по бинам выхода внутри классов «регистраций у домена» (у доменов с 1 регистрацией повторов с одного сайта нет по построению):')
    for lab, ds, regf, fdf in (('окно 3 суток, все домены', doms, 'reg_w', 'fd_w'),
                               ('окно 3 суток, без НЗ', nn, 'reg_w', 'fd_w'),
                               ('за всё время ≤ %s, все домены' % LATE_CUT, late, 'reg_a', 'fd_a'),
                               ('за всё время ≤ %s, без НЗ' % LATE_CUT, nl, 'reg_a', 'fd_a')):
        p('    %s:' % lab)
        p('    рег. у домена | бин | доменов | регистраций | ФД | ФД/рег [ДИ]')
        ct = {}
        for cls in ('1', '2', '3+'):
            for b in BINS3:
                sel = [d for d in ds if d['bin3'] == b and reg_class(d[regf]) == cls]
                reg = sum(d[regf] for d in sel)
                fd = sum(d[fdf] for d in sel)
                ct[(cls, b)] = (len(sel), reg, fd)
                if reg:
                    ci = cp_ci(fd, reg)
                    p('    %13s | %5s | %7d | %5d | %3d | %s [%s–%s]' % (cls, b, len(sel), reg, fd, r3(div(fd, reg)), r3(ci[0]), r3(ci[1])))
        a, na = ct[('1', '30+')][2], ct[('1', '30+')][1]
        c, nb = ct[('1', '10-30')][2], ct[('1', '10-30')][1]
        if na and nb:
            p('    только домены с 1 регистрацией: 30+ %d/%d = %s против 10–30 %d/%d = %s; точный тест (30+ ниже) p = %.4f' % (
                a, na, r3(div(a, na)), c, nb, r3(div(c, nb)), fisher_lower(a, na - a, c, nb - c)))
        a, na = ct[('3+', '30+')][2], ct[('3+', '30+')][1]
        c, nb = ct[('3+', '10-30')][2], ct[('3+', '10-30')][1]
        if na and nb:
            p('    только домены с 3+ регистрациями: 30+ %d/%d = %s против 10–30 %d/%d = %s; точный тест (30+ ниже) p = %.4f' % (
                a, na, r3(div(a, na)), c, nb, r3(div(c, nb)), fisher_lower(a, na - a, c, nb - c)))
    p('')

    # ---------------- 7. внутри пула: выше/ниже медианы выхода пула
    p('=' * 100)
    p('7. ВНУТРИ ПУЛА БЕЗ БИНОВ: домен выше медианы выхода своего пула (набор + день) против остальных')
    p('=' * 100)
    p('  Медиана выхода считается по всем доменам пула (не только с регистрациями); пулы из 1 домена не участвуют. Метки ФД перемешиваются внутри пула.')
    for lab, ds, regf, fdf, unit_name in (('окно 3 суток, без НЗ', nn, 'reg_w', 'fd_w', 'регистраций'),
                                          ('окно 3 суток, все (НЗ отдельным пулом)', doms, 'reg_w', 'fd_w', 'регистраций'),
                                          ('за всё время ≤ %s, без НЗ' % LATE_CUT, nl, 'reg_a', 'fd_a', 'регистраций'),
                                          ('за всё время ≤ %s, без НЗ, единица — сайт с рег.' % LATE_CUT, nl, 'S', 'fdS', 'сайтов с рег.')):
        pools = collections.defaultdict(list)
        for d in ds:
            pools[d['pool']].append(d['exit'])
        med = {k: statistics.median(v) for k, v in pools.items() if len(v) >= 2}
        units = []
        for d in ds:
            if d['pool'] not in med:
                continue
            g = 'выше медианы' if d['exit'] > med[d['pool']] else 'не выше'
            fdv = min(d['fd_a'], d['S']) if fdf == 'fdS' else d[fdf]
            units.append((d['pool'], g, d['exit'], d[regf], fdv))
        report_perm('7. %s' % lab, units, ('не выше', 'выше медианы'), 'выше медианы', 'не выше', NPERM, rng, unit_name=unit_name)
        p('')

    # ---------------- 8. ФД на 100 сайтов: плато?
    p('=' * 100)
    p('8. ФД НА 100 САЙТОВ ПО БИНАМ: есть ли плато после 30 %')
    p('=' * 100)
    p('  8.1 Окно 3 суток, без страты (все домены), 5 бинов — см. таблицу 2; попарно с 20–30 (условный биномиальный тест по сайтам):')
    for b in ('30-40', '40+', '10-20'):
        ka, na = t5w[b]['fd'], t5w[b]['sites']
        kb, nb = t5w['20-30']['fd'], t5w['20-30']['sites']
        up, lo = cond_binom_upper(ka, na, kb, nb)
        rr, l, h = ratio_ci(ka, na, kb, nb)
        p('    %5s: ФД/100 сайтов %.3f (%d ФД / %d сайтов) против 20–30: %.3f (%d / %d); отношение %.2f (ДИ %.2f–%.2f); p(выше) = %.3f, p(ниже) = %.3f' % (
            b, 100 * ka / na, ka, na, 100 * kb / nb, kb, nb, rr, l, h, up, lo))
        p('          регистраций/100 сайтов: %.3f против %.3f' % (100 * t5w[b]['reg'] / na, 100 * t5w['20-30']['reg'] / nb))
    p('  8.2 То же за всё время ≤ %s:' % LATE_CUT)
    for b in ('30-40', '40+'):
        ka, na = t5a[b]['fd'], t5a[b]['sites']
        kb, nb = t5a['20-30']['fd'], t5a['20-30']['sites']
        up, lo = cond_binom_upper(ka, na, kb, nb)
        rr, l, h = ratio_ci(ka, na, kb, nb)
        p('    %5s: ФД/100 сайтов %.3f (%d / %d) против 20–30: %.3f (%d / %d); отношение %.2f (ДИ %.2f–%.2f); p(выше) = %.3f, p(ниже) = %.3f' % (
            b, 100 * ka / na, ka, na, 100 * kb / nb, kb, nb, rr, l, h, up, lo))
    p('  8.3 Страта набор + день, события пула раскладываются по доменам ∝ сайтов (%d раз): O/E по бинам' % NPERM)
    site_oe = {}
    for lab, ds in (('окно, без НЗ', nn), ('окно, все (НЗ отдельным пулом)', doms)):
        for field, fl in (('reg_w', 'регистрации'), ('fd_w', 'ФД')):
            res, nvp = perm_on_sites(ds, field, BINS3, NPERM, rng)
            site_oe[(lab, field)] = res
            p('    %s, %s (пулов с событиями и ≥2 бинами: %d): ' % (lab, fl, nvp) + '; '.join(
                '%s: O %d, E %.1f, O/E %s, p(≥) %.3f, p(≤) %.3f' % (g, res[g][0], res[g][1], ('%.2f' % (res[g][0] / res[g][1])) if res[g][1] else '—', res[g][3], res[g][4]) for g in BINS3))
    p('')

    # ---------------- 9. описательно
    p('=' * 100)
    p('9. ОПИСАТЕЛЬНО')
    p('=' * 100)
    p('  9.1 Зоны × бины (окно 3 суток, все домены):')
    p('    зона | бин | доменов | сайтов | регистраций | ФД | ФД/рег | рег/100 сайтов | ФД/100 сайтов')
    for z in ZONES + ('прочие',):
        for b in BINS3:
            sel = [d for d in doms if d['zone'] == z and d['bin3'] == b]
            if not sel:
                continue
            s = sum(d['sites'] for d in sel)
            reg = sum(d['reg_w'] for d in sel)
            fd = sum(d['fd_w'] for d in sel)
            p('    %6s | %5s | %5d | %6d | %4d | %3d | %s | %.3f | %.3f' % (z, b, len(sel), s, reg, fd, r3(div(fd, reg)), 100 * div(reg, s), 100 * div(fd, s)))
    p('  9.1б Зоны × бины (за всё время, запуск ≤ %s):' % LATE_CUT)
    p('    зона | бин | доменов | сайтов | регистраций | ФД | ФД/рег | сайтов с рег. | ФД/сайт с рег.')
    for z in ZONES + ('прочие',):
        for b in BINS3:
            sel = [d for d in late if d['zone'] == z and d['bin3'] == b]
            if not sel:
                continue
            s = sum(d['sites'] for d in sel)
            reg = sum(d['reg_a'] for d in sel)
            fd = sum(d['fd_a'] for d in sel)
            S = sum(d['S'] for d in sel)
            fdS = sum(min(d['fd_a'], d['S']) for d in sel)
            p('    %6s | %5s | %5d | %6d | %4d | %3d | %s | %4d | %s' % (z, b, len(sel), s, reg, fd, r3(div(fd, reg)), S, r3(div(fdS, S))))
    p('  9.2 Неделя запуска × бин (окно): где сидят регистрации 30+ и какой там ФД/рег — тень даты')
    p('    неделя (пн) | бин | доменов | регистраций | ФД | ФД/рег | доля НЗ среди доменов')
    weeks = collections.defaultdict(list)
    for d in doms:
        dt = datetime.date.fromisoformat(d['day'])
        wk = (dt - datetime.timedelta(days=dt.weekday())).isoformat()
        weeks[wk].append(d)
    for wk in sorted(weeks):
        for b in BINS3:
            sel = [d for d in weeks[wk] if d['bin3'] == b]
            if not sel:
                continue
            reg = sum(d['reg_w'] for d in sel)
            fd = sum(d['fd_w'] for d in sel)
            p('    %s | %5s | %5d | %4d | %3d | %s | %.0f %%' % (wk, b, len(sel), reg, fd, r3(div(fd, reg)) if reg else '  —  ', 100 * sum(1 for d in sel if d['noc']) / len(sel)))
    p('  9.3 Семейство × бин: откуда берутся домены 30+ (окно, все домены)')
    p('    семейство | доменов 0–10 / 10–30 / 30+ | регистраций 10–30 (ФД) | регистраций 30+ (ФД)')
    fams = collections.defaultdict(list)
    for d in doms:
        fams[d['family']].append(d)
    for f, ds in sorted(fams.items(), key=lambda x: -len(x[1])):
        c = collections.Counter(d['bin3'] for d in ds)
        r1 = sum(d['reg_w'] for d in ds if d['bin3'] == '10-30'); f1 = sum(d['fd_w'] for d in ds if d['bin3'] == '10-30')
        r2 = sum(d['reg_w'] for d in ds if d['bin3'] == '30+'); f2 = sum(d['fd_w'] for d in ds if d['bin3'] == '30+')
        p('    %-12s | %4d / %4d / %3d | %4d (%2d) | %4d (%2d)' % (f, c['0-10'], c['10-30'], c['30+'], r1, f1, r2, f2))
    p('  9.4 Бренды (за всё время ≤ %s; число в скобках в своде = регистрации + ФД бренда): топ по событиям в 10–30 и 30+' % LATE_CUT)
    for b in ('10-30', '30+'):
        cnt = collections.Counter()
        for d in late:
            if d['bin3'] != b or not d['brands']:
                continue
            for part in d['brands'].split(','):
                part = part.strip()
                if '(' in part:
                    name, num = part.rsplit('(', 1)
                    cnt[name.strip()] += inum(num.rstrip(')'))
        tot = sum(cnt.values())
        p('    %5s: событий %d по %d брендам; топ: %s' % (b, tot, len(cnt), ', '.join('%s %d' % (k, v) for k, v in cnt.most_common(10))))
    p('')

    # ---------------- 10. критерии и вывод
    p('=' * 100)
    p('10. КРИТЕРИИ ПОСТАНОВКИ')
    p('=' * 100)
    rw = div(t3w['30+']['fd'], t3w['30+']['reg']) / div(t3w['10-30']['fd'], t3w['10-30']['reg'])
    ra = div(t3a['30+']['fd'], t3a['30+']['reg']) / div(t3a['10-30']['fd'], t3a['10-30']['reg'])
    rS = div(t3a['30+']['fdS'], t3a['30+']['S']) / div(t3a['10-30']['fdS'], t3a['10-30']['S'])
    p('  (а) ФД/рег(30+) ≤ 0,5 × ФД/рег(10–30), p < 0,05, в окне: отношение %.2f, точный p = %.4f, стратифицированный p (без НЗ) = %.4f, (с НЗ) = %.4f' % (rw, pw, res_w_nn['p_ratio'], res_w_all['p_ratio']))
    p('      за всё время ≤ %s: отношение %.2f, точный p = %.4f, стратифицированный p (без НЗ) = %.4f, (с НЗ) = %.4f' % (LATE_CUT, ra, pa, res_a_nn['p_ratio'], res_a_all['p_ratio']))
    p('  (б) ФД/100 сайтов в 30–40 и 40+ не выше, чем в 20–30 (окно): 20–30 %.3f, 30–40 %.3f, 40+ %.3f' % (
        100 * t5w['20-30']['fd'] / t5w['20-30']['sites'], 100 * t5w['30-40']['fd'] / t5w['30-40']['sites'], 100 * t5w['40+']['fd'] / t5w['40+']['sites']))
    p('  (в) повторы: ФД/сайт с рег. 30+ к 10–30 = %.2f (все домены), p = %.4f; без НЗ %.2f, p = %.4f; страта без НЗ p = %.4f' % (rS, pS_all, rrS_nn, pS_nn, res_S_nn['p_ratio']))
    p('')
    p('=' * 100)
    p('ВЫВОД')
    p('=' * 100)
    conclusion(doms, nn, late, nl, t5w, t5a, t3w, t3w_nn, t3a, t3a_nn, pw, pw_nn, pa, pa_nn,
               res_w_nn, res_w_all, res_wz_nn, res_a_nn, res_a_all, res_S_nn, res_S_all, pS_nn, pS_all, rS, rrS_nn, site_oe)
    TEE.flush()


def reg_class(r):
    if r == 0:
        return '0'
    if r == 1:
        return '1'
    if r == 2:
        return '2'
    return '3+'


def conclusion(doms, nn, late, nl, t5w, t5a, t3w, t3w_nn, t3a, t3a_nn, pw, pw_nn, pa, pa_nn,
               res_w_nn, res_w_all, res_wz_nn, res_a_nn, res_a_all, res_S_nn, res_S_all, pS_nn, pS_all, rS, rrS_nn, site_oe):
    w30, w1030 = t3w['30+'], t3w['10-30']
    a30, a1030 = t3a['30+'], t3a['10-30']
    n30, n1030 = t3w_nn['30+'], t3w_nn['10-30']
    # август: неделя 17.08 (все домены — «КОНТЕНТ НЕ ЗАПИСАН»)
    aug = [d for d in doms if d['day'] < '2026-08-24']
    aug30 = [d for d in aug if d['bin3'] == '30+']
    aug_reg = sum(d['reg_w'] for d in aug)
    aug_fd = sum(d['fd_w'] for d in aug)
    aug30_reg = sum(d['reg_w'] for d in aug30)
    aug30_fd = sum(d['fd_w'] for d in aug30)
    sep = [d for d in doms if d['day'] >= '2026-08-24']
    sep_reg = sum(d['reg_w'] for d in sep)
    sep_fd = sum(d['fd_w'] for d in sep)
    one30 = [d for d in doms if d['bin3'] == '30+' and d['reg_w'] == 1]
    one1030 = [d for d in doms if d['bin3'] == '10-30' and d['reg_w'] == 1]
    fd_oe = site_oe[('окно, без НЗ', 'fd_w')]['30+']
    reg_oe = site_oe[('окно, без НЗ', 'reg_w')]['30+']
    fd_oe_all = site_oe[('окно, все (НЗ отдельным пулом)', 'fd_w')]['30+']
    reg_oe_all = site_oe[('окно, все (НЗ отдельным пулом)', 'reg_w')]['30+']
    ratio_w = div(w30['fd'], w30['reg']) / div(w1030['fd'], w1030['reg'])
    ratio_a = div(a30['fd'], a30['reg']) / div(a1030['fd'], a1030['reg'])

    p('1. Лестница из гипотезы на файле воспроизводится, но только без страты. В окне 3 суток у %d доменов с выходом 30 %%+ — %d ФД на %d регистраций (%s),' % (
        w30['n'], w30['fd'], w30['reg'], r3(div(w30['fd'], w30['reg']))))
    p('   у %d доменов с выходом 10–30 %% — %d на %d (%s): в %.1f раза ниже, точный тест p = %.4f. За всё время (запуск до %s): %s против %s, в %.1f раза, p = %.4f.' % (
        w1030['n'], w1030['fd'], w1030['reg'], r3(div(w1030['fd'], w1030['reg'])), 1 / ratio_w, pw, LATE_CUT,
        r3(div(a30['fd'], a30['reg'])), r3(div(a1030['fd'], a1030['reg'])), 1 / ratio_a, pa))
    p('')
    p('2. Это тень даты и контента, а не выхода. %d из %d регистраций 30 %%+ (окно) дали домены, запущенные до 24.08 («КОНТЕНТ НЕ ЗАПИСАН»), и там всего %d ФД;' % (
        aug30_reg, w30['reg'], aug30_fd))
    p('   у этих августовских доменов ФД/рег низкий во всех бинах (%d ФД на %d регистраций = %s против %s у запусков с 24.08). Уберём их — отношение 30+/10–30 становится %.2f (%s против %s, p = %.3f);' % (
        aug_fd, aug_reg, r3(div(aug_fd, aug_reg)), r3(div(sep_fd, sep_reg)), div(n30['fd'], n30['reg']) / div(n1030['fd'], n1030['reg']),
        r3(div(n30['fd'], n30['reg'])), r3(div(n1030['fd'], n1030['reg'])), pw_nn))
    p('   за всё время без них — %.2f (p = %.2f). Внутри пулов «набор контента + день запуска» разницы нет: ФД в 30+ наблюдено/ожидаемо %.2f (окно, без НЗ; p = %.2f),' % (
        div(t3a_nn['30+']['fd'], t3a_nn['30+']['reg']) / div(t3a_nn['10-30']['fd'], t3a_nn['10-30']['reg']), pa_nn,
        res_w_nn['obs']['30+'] / res_w_nn['E']['30+'], res_w_nn['p_a']))
    p('   %.2f (окно, НЗ отдельным пулом; p = %.2f), %.2f (за всё время, без НЗ; p = %.2f), %.2f (за всё время, с НЗ; p = %.2f); тренд по выходу без бинов p = %.2f–%.2f.' % (
        res_w_all['obs']['30+'] / res_w_all['E']['30+'], res_w_all['p_a'], res_a_nn['obs']['30+'] / res_a_nn['E']['30+'], res_a_nn['p_a'],
        res_a_all['obs']['30+'] / res_a_all['E']['30+'], res_a_all['p_a'], min(res_w_nn['p_tr'], res_w_all['p_tr'], res_a_nn['p_tr'], res_a_all['p_tr']),
        max(res_w_nn['p_tr'], res_w_all['p_tr'], res_a_nn['p_tr'], res_a_all['p_tr'])))
    p('   Важно: даже при случайной раздаче ФД внутри пулов отношение 30+/10–30 ожидается ниже единицы (нулевой интервал %.2f–%.2f в окне без НЗ) — именно потому, что регистрации 30+ сидят в пулах с низким ФД/рег у всех.' % (
        res_w_nn['null_ratio_lo'], res_w_nn['null_ratio_hi']))
    p('   Сравнить «как на как» можно лишь %d регистраций 30+ (без НЗ) — в тех пулах ФД/рег 30+ = %s против 10–30 = %s; за всё время %s против %s. Объём мал: падение в 1,3–1,5 раза исключить нельзя, в 2–4 раза — не видно.' % (
        res_w_nn['inf']['inf_units']['30+'], r3(div(res_w_nn['inf']['inf_fd']['30+'], res_w_nn['inf']['inf_units']['30+'])),
        r3(div(res_w_nn['inf']['inf_fd']['10-30'], res_w_nn['inf']['inf_units']['10-30'])),
        r3(div(res_a_nn['inf']['inf_fd']['30+'], res_a_nn['inf']['inf_units']['30+'])), r3(div(res_a_nn['inf']['inf_fd']['10-30'], res_a_nn['inf']['inf_units']['10-30']))))
    p('')
    p('3. Повторы с одного сайта (№17) ни при чём. Повторов мало в обоих бинах (доля R−S: %s в 10–30, %s в 30+). При счёте ФД на сайт с регистрацией (за всё время) отношение 30+/10–30 = %.2f без НЗ (p = %.2f),' % (
        r3(div(t3a['10-30']['reg'] - t3a['10-30']['S'], t3a['10-30']['reg'])), r3(div(t3a['30+']['reg'] - t3a['30+']['S'], t3a['30+']['reg'])), rrS_nn, pS_nn))
    p('   %.2f со всеми (p = %.3f) — то есть та же августовская тень; в страте O/E = %.2f (p = %.2f). Наоборот, самое сильное падение — у доменов с единственной регистрацией, где повторов нет: %d ФД на %d регистраций в 30+ против %d на %d в 10–30' % (
        rS, pS_all, res_S_nn['obs']['30+'] / res_S_nn['E']['30+'], res_S_nn['p_a'], sum(d['fd_w'] for d in one30), len(one30), sum(d['fd_w'] for d in one1030), len(one1030)))
    p('   (окно; без НЗ %d на %d против %d на %d), а у доменов с 3+ регистрациями ФД/рег в 30+ обычный. Это срез, найденный после просмотра многих таблиц, и без страты; как рычаг не годится, как повод перепроверить позже — да.' % (
        sum(d['fd_w'] for d in one30 if not d['noc']), sum(1 for d in one30 if not d['noc']), sum(d['fd_w'] for d in one1030 if not d['noc']), sum(1 for d in one1030 if not d['noc'])))
    p('')
    p('4. Плато по деньгам нет. ФД на 100 сайтов: 20–30 %% — %.3f, 30–40 %% — %.3f (в %.1f раза выше, p = %.3f), 40+ %% — %.3f (%d ФД на %d доменов — не отличимо ни от роста, ни от плато);' % (
        100 * t5w['20-30']['fd'] / t5w['20-30']['sites'], 100 * t5w['30-40']['fd'] / t5w['30-40']['sites'],
        (t5w['30-40']['fd'] / t5w['30-40']['sites']) / (t5w['20-30']['fd'] / t5w['20-30']['sites']),
        cond_binom_upper(t5w['30-40']['fd'], t5w['30-40']['sites'], t5w['20-30']['fd'], t5w['20-30']['sites'])[0],
        100 * t5w['40+']['fd'] / t5w['40+']['sites'], t5w['40+']['fd'], t5w['40+']['n']))
    p('   за всё время 30–40 %% даёт %.3f против %.3f (в %.1f раза, p = %.3f). Внутри пулов домены 30+ собирают регистраций в %.2f раза больше ожидаемого по сайтам и ФД — в %.2f раза (p = %.3f): деньги растут вслед за выходом в той же пропорции.' % (
        100 * t5a['30-40']['fd'] / t5a['30-40']['sites'], 100 * t5a['20-30']['fd'] / t5a['20-30']['sites'],
        (t5a['30-40']['fd'] / t5a['30-40']['sites']) / (t5a['20-30']['fd'] / t5a['20-30']['sites']),
        cond_binom_upper(t5a['30-40']['fd'], t5a['30-40']['sites'], t5a['20-30']['fd'], t5a['20-30']['sites'])[0],
        reg_oe[0] / reg_oe[1], fd_oe[0] / fd_oe[1], fd_oe[3]))
    p('')
    p('ИТОГ: гипотеза опровергнута. Регистрации у доменов с большим выходом не хуже — хуже были регистрации августовских доменов (до 24.08), у которых заодно был высокий выход.')
    p('Насыщения по депозитам после 30 % нет: ФД на сайт у 30–40 % выше, чем у 20–30 %, и внутри пула ФД растут вместе с регистрациями. Повторы с одного сайта тут ни при чём.')
    p('Оговорки: ФД мало (%d в окне, %d за всё время), «как на как» сравнимы лишь %d (окно, без НЗ) – %d (за всё время, с НЗ) регистраций 30+; слабое падение (до 1,5 раза) не исключено; бин 40+ (%d доменов, %d ФД) отдельно не проверяем; ' % (
        sum(d['fd_w'] for d in doms), sum(d['fd_a'] for d in late), res_w_nn['inf']['inf_units']['30+'], res_a_all['inf']['inf_units']['30+'], t5w['40+']['n'], t5w['40+']['fd']))
    p('почему у августовских доменов почти не было депозитов (%d ФД на %d регистраций) — на своде не видно (дата, бренды, учёт?) и здесь не решается.' % (aug_fd, aug_reg))
    p('')
    p('ЧТО С ЭТИМ ДЕЛАТЬ:')
    p('  — Не вводить «ФД / сайты с регистрацией» вместо регистраций как целевую метрику и не ограничивать выход «ровными 20–30 %»: рычага здесь нет. Целевая метрика остаётся ФД (и регистрации) на 100 сайтов; выход — первая ступень, и деньги идут за ней пропорционально.')
    p('  — Любое сравнение ФД/рег между группами доменов считать только внутри «набор контента + день»; без этого августовские домены (ФД/рег %s против %s) рисуют лестницу из ничего. Проверяемо на этом же своде: разница 30+ против 10–30 после исключения запусков до 24.08 сжимается с %.1f до %.1f раза в окне и с %.1f до %.1f раза за всё время, а остаток внутри пулов не отличим от нуля.' % (
        r3(div(aug_fd, aug_reg)), r3(div(sep_fd, sep_reg)), 1 / ratio_w, div(n1030['fd'], n1030['reg']) / div(n30['fd'], n30['reg']),
        1 / ratio_a, div(t3a_nn['10-30']['fd'], t3a_nn['10-30']['reg']) / div(t3a_nn['30+']['fd'], t3a_nn['30+']['reg'])))
    p('  — Знание, не рычаг: откуда взялся провал ФД в августе — отдельный вопрос к учёту конверсий за 18–22.08, а не к выходу.')


if __name__ == '__main__':
    main()

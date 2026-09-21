#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептическая проверка результата h06 («золотых» баз нет) под углом СТАТИСТИКИ.

Что проверяем:
  1. Суммы или средние по доменам — какие величины сравнивал тестировщик; объёмы групп
     (доменов / регистраций / ФД) у каждого утверждения.
  2. Перебор срезов: сколько p-значений в отчёте h06; глобальный перестановочный тест
     «минимальное p по всем 7 статистикам» на тех же 5000 симуляциях (min-p против
     распределения min-p по симуляциям) — выживает ли избыток «3+»; Холм по 7 статистикам.
  3. Состав совпадения «2+»: ровно 2 регистрации — наблюдено против симуляций
     (совпадение 40 ≈ 42,6 может быть суммой недостачи «двоек» и избытка «троек»).
  4. Устойчивость: убрать топ-3 домена по регистрациям (в группе «3+» и в группе повторов
     на одном сайте) и пересчитать; убрать каждый пул по очереди (пулы, где есть домены с 3+).
  5. Разные сайты в окне: у 21 домена с 3+ рег в окне — сколько разных конвертивших сайтов
     (нижняя/верхняя границы, т.к. «сайтов с регистрацией» есть только за всё время) против
     ожидаемого числа доменов с ≥3 РАЗНЫМИ сайтами при случайной раскладке (розыгрыш бренда
     из общего распределения, как у тестировщика, и из более кучного — чувствительность).
     Это прямая проверка утверждения «избыток 3+ целиком от повторов на одном сайте».
  6. Мощность «нулевых» результатов: 3+ разных сайтов 23 vs 18,9 (p=0,12) — какой O/E
     вообще различим; ФД 20/110 vs 31/134 — 95 % интервал отношения и минимально различимый эффект.

Только stdlib. Вывод — stdout и analysis/export/gipotezy_svod/v06_statistika.txt
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
H06_TXT = os.path.join(BASE, 'export', 'gipotezy_svod', 'h06_no_golden_domain.txt')
OUT = os.path.join(BASE, 'export', 'gipotezy_svod', 'v06_statistika.txt')

N_SIM = 5000
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
_lines = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    _lines.append(s)
    print(s)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fmt(x, d=2):
    if x is None:
        return '—'
    return f'{x:.{d}f}'


def pct(sorted_vals, q):
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def binom_pmf(k, n, q):
    if q <= 0:
        return 1.0 if k == 0 else 0.0
    if q >= 1:
        return 1.0 if k == n else 0.0
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(q) + (n - k) * math.log(1 - q))


def binom_two_sided(k, n, q):
    lo = sum(binom_pmf(i, n, q) for i in range(0, k + 1))
    hi = sum(binom_pmf(i, n, q) for i in range(k, n + 1))
    return min(1.0, 2 * min(lo, hi))


def gini(vals):
    n = len(vals)
    tot = sum(vals)
    if n == 0 or tot <= 0:
        return 0.0
    s = sorted(vals)
    acc = 0.0
    for i, v in enumerate(s, start=1):
        acc += i * v
    return 2.0 * acc / (n * tot) - (n + 1.0) / n


def stats_of(counts):
    tot = sum(counts)
    n = len(counts)
    n1 = n2 = n3 = e2 = 0
    for c in counts:
        if c >= 1:
            n1 += 1
        if c >= 2:
            n2 += 1
        if c >= 3:
            n3 += 1
        if c == 2:
            e2 += 1
    mx = max(counts) if counts else 0
    half = 0
    acc = 0
    for c in sorted(counts, reverse=True):
        acc += c
        half += 1
        if acc * 2 >= tot:
            break
    mean = tot / n
    var = sum((c - mean) ** 2 for c in counts) / n
    return {'n1': n1, 'n2': n2, 'n3': n3, 'e2': e2, 'half': half, 'gini': gini(counts),
            'max': mx, 'vm': var / mean if mean > 0 else 0.0}


STAT_DEF = [('n2', 'доменов с ≥2 рег', +1), ('n3', 'доменов с ≥3 рег', +1),
            ('half', 'доменов на половину рег', -1), ('gini', 'Джини', +1),
            ('max', 'максимум', +1), ('n1', 'доменов с ≥1 рег', -1), ('vm', 'дисп/среднее', +1)]


def strip_suffix(name):
    return re.sub(r'_\d+$', '', name)


# ------------------------------------------------------------------ данные и фильтры (как в h06)
with open(SRC, encoding='utf-8', newline='') as fh:
    rows = list(csv.DictReader(fh))
for r in rows:
    r['_reg_w'] = int(fnum(r['регистраций в окне 3 суток']))
    r['_fd_w'] = int(fnum(r['ФД в окне 3 суток']))
    r['_reg_all'] = int(fnum(r['регистраций']))
    r['_fd_all'] = int(fnum(r['ФД']))
    r['_clk_w'] = fnum(r['кликов из поиска в окне'])
    r['_clk_all'] = fnum(r['из поиска'])
    r['_ex3'] = fnum(r['вышли за 3 суток'])
    r['_sites_w'] = fnum(r['сайтов в окне'])
    r['_brands'] = int(fnum(r['брендов с конверсией']))
    r['_sites_reg'] = int(fnum(r['сайтов с регистрацией']))
    r['_set'] = strip_suffix(r['набор контента'])

brand_events = Counter()
for r in rows:
    s = r['какие бренды конвертили'].strip()
    if s:
        for part in s.split(', '):
            m = re.match(r'^(.+) \((\d+)\)$', part)
            if m:
                brand_events[m.group(1)] += int(m.group(2))
BRANDS = sorted(brand_events)
BRAND_W = [brand_events[b] for b in BRANDS]
N_EV = sum(BRAND_W)


def cum_of(ws):
    out = []
    a = 0.0
    for w in ws:
        a += w
        out.append(a)
    return out


BRAND_CUM1 = cum_of(BRAND_W)
BRAND_CUM2 = cum_of([w * w for w in BRAND_W])          # кучнее: p ∝ w²
sp2_1 = sum((w / N_EV) ** 2 for w in BRAND_W)
s2 = sum(w * w for w in BRAND_W)
sp2_2 = sum((w * w / s2) ** 2 for w in BRAND_W)

main_rows = [r for r in rows if r['окно закрыто'] == 'да' and int(fnum(r['дней'])) >= 2
             and r['домен'] not in OUTLIERS and r['набор контента'] != NO_CONTENT]


def build_pools(domains, key_fn, min_size=3):
    pools = defaultdict(list)
    for r in domains:
        pools[key_fn(r)].append(r)
    return {k: v for k, v in pools.items() if len(v) >= min_size}


pools_main = build_pools(main_rows, lambda r: (r['_set'], r['день запуска']))
doms_main = [r for v in pools_main.values() for r in v]
R_main = sum(r['_reg_w'] for r in doms_main)

p('=' * 100)
p('v06 / СТАТИСТИКА. Скептическая проверка результата h06 («золотых» баз нет)')
p('=' * 100)
p(f'Файл: {SRC}; строк {len(rows)}. Фильтры как в h06: окно закрыто = да, дней ≥ 2, без выбросов, '
  f'без «{NO_CONTENT}» → {len(main_rows)} доменов; пулы «набор без _NN + день» ≥3 доменов → '
  f'{len(pools_main)} пулов, {len(doms_main)} доменов, {R_main} регистраций в окне.')
p('')


# ------------------------------------------------------------------ симулятор
def simulate(pools, wkey, rkey, n_sim, seed=1, brands=False, brand_cum=None, keys=None):
    """Возвращает obs (dict) и sims (dict of lists). brands=True — ещё и число разных сайтов на домен."""
    random.seed(seed)
    doms, specs = [], []
    for k, v in pools.items():
        R = sum(r[rkey] for r in v)
        start = len(doms)
        doms.extend(v)
        if R == 0:
            continue
        w = [r[wkey] for r in v]
        if sum(w) <= 0:
            w = [1.0] * len(v)
        specs.append((R, list(range(start, start + len(v))), cum_of(w)))
    n = len(doms)
    obs = stats_of([r[rkey] for r in doms])
    sims = defaultdict(list)
    for _ in range(n_sim):
        counts = [0] * n
        for R, idxs, cum in specs:
            for i in random.choices(idxs, cum_weights=cum, k=R):
                counts[i] += 1
        st = stats_of(counts)
        if brands:
            d2 = d3 = rep = 0
            for c in counts:
                if c >= 2:
                    d = len(set(random.choices(BRANDS, cum_weights=brand_cum, k=c)))
                    d2 += d >= 2
                    d3 += d >= 3
                    rep += c - d
            st['d2'], st['d3'], st['rep'] = d2, d3, rep
        for key, val in st.items():
            if keys is None or key in keys:
                sims[key].append(val)
    return doms, obs, sims


def summarize(obs_val, vals, direction):
    s = sorted(vals)
    mean = sum(s) / len(s)
    if direction > 0:
        pv = sum(1 for v in vals if v >= obs_val) / len(vals)
    else:
        pv = sum(1 for v in vals if v <= obs_val) / len(vals)
    return mean, pct(s, 0.025), pct(s, 0.975), pv


# ================================================================== 1. суммы/средние, объёмы
p('=' * 100)
p('1. СУММЫ ИЛИ СРЕДНИЕ; ОБЪЁМЫ ГРУПП')
p('=' * 100)
p('  Все статистики h06 — целые счётчики по доменам (сколько доменов с ≥k регистрациями, Джини по вектору '
  'счётчиков, max) и суммы ФД/рег по группам; средних от долей по доменам нет. Претензии к типу величины нет.')
c = Counter(min(r['_reg_w'], 3) for r in doms_main)
p(f'  Распределение регистраций в окне по доменам: 0 — {c[0]}, 1 — {c[1]}, 2 — {c[2]}, 3+ — {c[3]}')
g3 = [r for r in doms_main if r['_reg_w'] >= 3]
g2 = [r for r in doms_main if r['_reg_w'] == 2]
g1 = [r for r in doms_main if r['_reg_w'] == 1]
p(f'  Группа «3+ в окне»: {len(g3)} доменов, {sum(r["_reg_w"] for r in g3)} рег в окне, {sum(r["_fd_w"] for r in g3)} ФД; '
  f'группа «2»: {len(g2)} доменов, {sum(r["_reg_w"] for r in g2)} рег, {sum(r["_fd_w"] for r in g2)} ФД; '
  f'«1»: {len(g1)} доменов, {sum(r["_fd_w"] for r in g1)} ФД.')
rep_doms = [r for r in doms_main if r['_reg_all'] >= 2 and r['_reg_all'] > r['_sites_reg']]
p(f'  Повторы на одном сайте (за всё время, R − S): {sum(r["_reg_all"] - r["_sites_reg"] for r in rep_doms)} повторов на '
  f'{len(rep_doms)} доменах; из них доменов с одним сайтом: {sum(1 for r in rep_doms if r["_sites_reg"] == 1)}.')
p('  → Утверждения «3+ избыток» опираются на 21 домен / 72 регистрации; «ФД не лучше» — на 20 ФД против 31; '
  '«повторы» — на 26 событий с 19 доменов. Это малые группы; см. мощность в разделе 6.')
p('')

# ================================================================== 2. перебор срезов / глобальный тест
p('=' * 100)
p('2. ПЕРЕБОР СРЕЗОВ: сколько p в отчёте h06 и глобальный тест по всем статистикам')
p('=' * 100)
n_p = n_sig = 0
with open(H06_TXT, encoding='utf-8') as fh:
    for line in fh:
        m = re.match(r'^\s{2}\S.*?\s(\d\.\d{3})(\s+\d+\.\d %)?\s*$', line)
        if m and ('[' in line):
            n_p += 1
            if float(m.group(1)) < 0.05:
                n_sig += 1
p(f'  В таблицах h06 напечатано {n_p} p-значений (7 статистик × 8 прогонов + 3 брендовых × 2), из них < 0,05: {n_sig}.')
p('  Выводы тестировщика опираются на ОДИН прогон (1а, λ по кликам в окне) с 7 статистиками; статистики сильно '
  'скоррелированы (все считаются по одному вектору счётчиков). Правильный глобальный тест — распределение '
  'минимального p по 7 статистикам на тех же симуляциях.')

doms, obs, sims = simulate(pools_main, '_clk_w', '_reg_w', N_SIM, seed=1, brands=True, brand_cum=BRAND_CUM1)
n_dom = len(doms)
p(f'  Прогон 1а воспроизведён: seed 1, {N_SIM} симуляций, {n_dom} доменов, {R_main} рег.')
p(f'  {"статистика":26} {"набл.":>8} {"средн.сим":>10} {"95 %":>16} {"p":>7}')
obs_p = {}
for key, label, direction in STAT_DEF:
    mean, lo, hi, pv = summarize(obs[key], sims[key], direction)
    obs_p[key] = pv
    d = 3 if key == 'gini' else (2 if key == 'vm' else 1)
    p(f'  {label:26} {fmt(obs[key], 0 if isinstance(obs[key], int) else d):>8} {fmt(mean, d):>10} '
      f'{("[" + fmt(lo, d) + "; " + fmt(hi, d) + "]"):>16} {fmt(pv, 3):>7}')

# min-p по симуляциям: p каждой симуляции = доля симуляций не менее экстремальных (включая себя)
def sim_pvalues(vals, direction):
    s = sorted(vals)
    n = len(s)
    out = []
    import bisect
    for v in vals:
        if direction > 0:
            out.append((n - bisect.bisect_left(s, v)) / n)
        else:
            out.append(bisect.bisect_right(s, v) / n)
    return out


for name, keys in [('все 7 статистик', [k for k, _, _ in STAT_DEF]),
                   ('4 статистики плана (а)–(в): ≥2, ≥3, половина, Джини', ['n2', 'n3', 'half', 'gini']),
                   ('только ≥2 и ≥3', ['n2', 'n3'])]:
    per = {k: sim_pvalues(sims[k], d) for k, _, d in STAT_DEF if k in keys}
    minp_sim = [min(per[k][j] for k in keys) for j in range(N_SIM)]
    minp_obs = min(obs_p[k] for k in keys)
    glob = sum(1 for v in minp_sim if v <= minp_obs) / N_SIM
    p(f'  Глобальный тест ({name}): набл. min-p = {minp_obs:.4f}; P(min-p сим ≤ набл.) = {glob:.4f}; '
      f'Бонферрони {min(1.0, minp_obs * len(keys)):.3f}')
sorted_p = sorted((obs_p[k], k) for k, _, _ in STAT_DEF)
holm = []
for i, (pv, k) in enumerate(sorted_p):
    holm.append((k, pv, min(1.0, pv * (7 - i))))
p('  Холм по 7 статистикам (p → скорректированное): ' + '; '.join(f'{k} {pv:.3f}→{h:.3f}' for k, pv, h in holm))
p('  → Избыток «3+» — не артефакт перебора: глобальный min-p тест его держит. Но и остальные статистики'
  ' (Джини, половина, дисп/среднее, ≥1) все отклоняются в одну сторону — «кучнее, чем клики».')
p('')

# ================================================================== 3. состав совпадения «2+»
p('=' * 100)
p('3. СОСТАВ СОВПАДЕНИЯ «2+»: ровно 2 регистрации против симуляций')
p('=' * 100)
mean_e2, lo_e2, hi_e2, p_e2 = summarize(obs['e2'], sims['e2'], -1)
mean_n3, lo_n3, hi_n3, p_n3 = summarize(obs['n3'], sims['n3'], +1)
mean_n2, _, _, _ = summarize(obs['n2'], sims['n2'], +1)
p(f'  Ровно 2 рег: наблюдено {obs["e2"]}, ожидается {mean_e2:.1f} [{lo_e2:.0f}; {hi_e2:.0f}], p(≤набл.) = {p_e2:.3f}')
p(f'  3+ рег:      наблюдено {obs["n3"]}, ожидается {mean_n3:.1f} [{lo_n3:.0f}; {hi_n3:.0f}], p(≥набл.) = {p_n3:.3f}')
p(f'  ≥2 = (ровно 2) + (3+): {obs["e2"]} + {obs["n3"]} = {obs["n2"]} против {mean_e2:.1f} + {mean_n3:.1f} = {mean_n2:.1f}')
p(f'  → «40 против 42,6, объяснено» — это недостача двоек ({obs["e2"] - mean_e2:+.1f}) и избыток троек ({obs["n3"] - mean_n3:+.1f}), '
  'которые гасят друг друга в сумме. Совпадение числа «повторных» баз с кликами — арифметическая случайность, а не «объяснение».')
# распределение по k: наблюдено vs ожидаемое
p('  Наблюдённое против среднего симуляций по числу регистраций на домен:')
kmax = max(r['_reg_w'] for r in doms)
random.seed(1)
# быстрая оценка ожидаемого распределения по k
exp_k = Counter()
n_rep = 1000
specs = []
for k, v in pools_main.items():
    R = sum(r['_reg_w'] for r in v)
    if R == 0:
        continue
    specs.append((R, list(range(len(v))), cum_of([r['_clk_w'] for r in v]), len(v)))
for _ in range(n_rep):
    for R, idxs, cum, m in specs:
        cnt = Counter(random.choices(idxs, cum_weights=cum, k=R))
        for i in idxs:
            exp_k[min(cnt.get(i, 0), 5)] += 1
obs_k = Counter(min(r['_reg_w'], 5) for r in doms)
p('    k: ' + '  '.join(f'{k}: {obs_k[k]} / {exp_k[k] / n_rep:.1f}' for k in range(0, 6)) + '   (набл. / ожид.; 5 = 5+)')
p('')

# ================================================================== 4. устойчивость: топ-3 и пулы
p('=' * 100)
p('4. УСТОЙЧИВОСТЬ ИЗБЫТКА «3+»: без топ-3 доменов; без каждого пула по очереди')
p('=' * 100)
top3 = sorted(doms_main, key=lambda r: (-r['_reg_w'], -r['_clk_w']))[:3]
p('  Топ-3 домена по рег в окне: ' + ', '.join(f'{r["домен"]} ({r["_reg_w"]})' for r in top3))
drop = {r['домен'] for r in top3}
pools_wo = {k: [r for r in v if r['домен'] not in drop] for k, v in pools_main.items()}
pools_wo = {k: v for k, v in pools_wo.items() if len(v) >= 3}
d_wo, obs_wo, sims_wo = simulate(pools_wo, '_clk_w', '_reg_w', N_SIM, seed=1)
p(f'  Без них: {len(d_wo)} доменов, {sum(r["_reg_w"] for r in d_wo)} рег.')
for key, label, direction in STAT_DEF[:4]:
    mean, lo, hi, pv = summarize(obs_wo[key], sims_wo[key], direction)
    d = 3 if key == 'gini' else 1
    p(f'    {label:26} {fmt(obs_wo[key], 0 if isinstance(obs_wo[key], int) else d):>8} vs {fmt(mean, d):>7} '
      f'[{fmt(lo, d)}; {fmt(hi, d)}]  O/E {obs_wo[key] / mean:.2f}  p={pv:.3f}')
# без топ-3 по повторам на одном сайте
top3rep = sorted(rep_doms, key=lambda r: -(r['_reg_all'] - r['_sites_reg']))[:3]
p('  Топ-3 домена по повторам на одном сайте (за всё время): ' + ', '.join(
    f'{r["домен"]} R={r["_reg_all"]} S={r["_sites_reg"]}' for r in top3rep))
drop2 = {r['домен'] for r in top3rep}
pools_wo2 = {k: [r for r in v if r['домен'] not in drop2] for k, v in pools_main.items()}
pools_wo2 = {k: v for k, v in pools_wo2.items() if len(v) >= 3}
d2_, obs2_, sims2_ = simulate(pools_wo2, '_clk_all', '_reg_all', N_SIM, seed=1, brands=True, brand_cum=BRAND_CUM1)
obs_rep = sum(r['_reg_all'] - r['_sites_reg'] for r in d2_ if r['_reg_all'] >= 2)
mean, lo, hi, pv = summarize(obs_rep, sims2_['rep'], +1)
p(f'  Без них повторов на одном сайте: {obs_rep} vs {mean:.1f} [{lo:.0f}; {hi:.0f}], p={pv:.3f} — избыток повторов остаётся.')
obs_d3 = sum(1 for r in d2_ if r['_brands'] >= 3)
mean, lo, hi, pv = summarize(obs_d3, sims2_['d3'], +1)
p(f'  Без них доменов с 3+ разными сайтами (всё время): {obs_d3} vs {mean:.1f} [{lo:.0f}; {hi:.0f}], O/E {obs_d3 / mean:.2f}, p={pv:.3f}')

p('  Без каждого пула, где есть домены с 3+ рег в окне (λ по кликам, 2000 симуляций):')
pools_with3 = [k for k, v in pools_main.items() if any(r['_reg_w'] >= 3 for r in v)]
worst = None
for k in pools_with3:
    sub = {kk: vv for kk, vv in pools_main.items() if kk != k}
    d_, o_, s_ = simulate(sub, '_clk_w', '_reg_w', 2000, seed=1, keys={'n3', 'n2'})
    mean, lo, hi, pv = summarize(o_['n3'], s_['n3'], +1)
    n3_in = sum(1 for r in pools_main[k] if r['_reg_w'] >= 3)
    p(f'    без {k[0][:30]:30} {k[1][5:]}  (доменов {len(pools_main[k]):>2}, с 3+ {n3_in}): 3+ {o_["n3"]} vs {mean:.1f} [{lo:.0f}; {hi:.0f}] '
      f'O/E {o_["n3"] / mean:.2f} p={pv:.3f}')
    if worst is None or pv > worst[0]:
        worst = (pv, k, o_['n3'], mean)
p(f'  Худший случай: без пула {worst[1][0][:30]} {worst[1][1][5:]} — 3+ {worst[2]} vs {worst[3]:.1f}, p={worst[0]:.3f}. '
  'Избыток «3+» не держится на одном пуле и не на топ-3 доменах.')
p('')

# ================================================================== 5. разные сайты в окне
p('=' * 100)
p('5. РАЗНЫЕ САЙТЫ В ОКНЕ у доменов с 3+ регистрациями: целиком ли избыток от повторов на одном сайте?')
p('=' * 100)
p('  «Сайтов с регистрацией» (S) есть только за всё время. Для домена с r рег в окне и R за всё время число разных')
p('  сайтов в окне лежит в [max(0, r − (R − S)); min(r, S)]: нижняя граница — все повторы попали в окно, верхняя — ни один.')
p(f'  {"домен":18} {"рег окно":>8} {"рег всего":>9} {"сайтов":>6} {"разн.в окне":>12}')
lo3 = hi3 = 0
lo2 = hi2 = 0
for r in sorted(doms_main, key=lambda r: -r['_reg_w']):
    rw, R, S = r['_reg_w'], r['_reg_all'], r['_sites_reg']
    lo_d = max(0, rw - (R - S))
    hi_d = min(rw, S)
    if rw >= 3:
        p(f'  {r["домен"]:18} {rw:>8} {R:>9} {S:>6} {("[" + str(lo_d) + "; " + str(hi_d) + "]"):>12}')
    lo3 += lo_d >= 3
    hi3 += hi_d >= 3
    lo2 += lo_d >= 2
    hi2 += hi_d >= 2
p(f'  Доменов с ≥3 РАЗНЫМИ конвертившими сайтами в окне: от {lo3} до {hi3} (из 21 с 3+ рег); с ≥2 разными: от {lo2} до {hi2}.')
m3, l3, h3, p3lo = summarize(lo3, sims['d3'], +1)
_, _, _, p3hi = summarize(hi3, sims['d3'], +1)
m2, l2, h2, p2lo = summarize(lo2, sims['d2'], +1)
p(f'  Ожидание при случайной раскладке по кликам + бренд из общего распределения (Σp² = {sp2_1:.3f}, как у тестировщика):')
p(f'    доменов с ≥3 разными сайтами в окне: {m3:.1f} [{l3:.0f}; {h3:.0f}]; наблюдено {lo3}…{hi3} → O/E {lo3 / m3:.2f}…{hi3 / m3:.2f}, '
  f'p = {p3lo:.3f} (нижняя граница) … {p3hi:.3f} (верхняя)')
p(f'    доменов с ≥2 разными сайтами в окне: {m2:.1f} [{l2:.0f}; {h2:.0f}]; наблюдено {lo2}…{hi2}, p(нижн.) = {p2lo:.3f}')
# чувствительность: кучнее розыгрыш бренда
_, obs_c, sims_c = simulate(pools_main, '_clk_w', '_reg_w', N_SIM, seed=1, brands=True, brand_cum=BRAND_CUM2, keys={'d3', 'd2', 'rep', 'n3'})
m3c, l3c, h3c, p3c = summarize(lo3, sims_c['d3'], +1)
p(f'  Чувствительность: бренд из более кучного распределения (p ∝ w², Σp² = {sp2_2:.3f}): ожидание ≥3 разных сайтов '
  f'{m3c:.1f} [{l3c:.0f}; {h3c:.0f}], p(нижн. {lo3}) = {p3c:.3f}')
p('  → Даже по нижней границе (все повторы в окне) доменов с 3+ РАЗНЫМИ сайтами больше ожидаемого; '
  'фраза «доменов с 3+ разными конвертившими сайтами ровно столько, сколько ждёт случай» на окне не подтверждается.')
p('')

# ================================================================== 6. мощность нулевых результатов
p('=' * 100)
p('6. МОЩНОСТЬ «НУЛЕВЫХ» РЕЗУЛЬТАТОВ (что вообще можно было увидеть)')
p('=' * 100)
# 3+ разных сайтов за всё время: 23 vs 18.9 [13;25]
_, obs_a, sims_a = simulate(pools_main, '_clk_all', '_reg_all', N_SIM, seed=1, brands=True, brand_cum=BRAND_CUM1, keys={'d3', 'd2', 'rep'})
ob3 = sum(1 for r in doms_main if r['_brands'] >= 3)
m, lo, hi, pv = summarize(ob3, sims_a['d3'], +1)
s = sorted(sims_a['d3'])
thr = None
for t in range(int(m), 60):
    if sum(1 for v in s if v >= t) / len(s) < 0.05:
        thr = t
        break
p(f'  3+ разных сайтов за всё время: {ob3} vs {m:.1f} [{lo:.0f}; {hi:.0f}], O/E {ob3 / m:.2f}, p={pv:.3f}; '
  f'значимо было бы от {thr} (O/E ≥ {thr / m:.2f}). Тест не отличает O/E 1,0 от 1,3 — «в пределах случая» ≠ «как ждёт случай».')
# ФД
F2, R2 = 20, 110
F1, R1 = 31, 134
rr = (F2 / R2) / (F1 / R1)
se = math.sqrt(1 / F2 - 1 / R2 + 1 / F1 - 1 / R1)
p(f'  ФД: 2+ базы {F2}/{R2} = {100 * F2 / R2:.1f} % против одиночных {F1}/{R1} = {100 * F1 / R1:.1f} %; отношение {rr:.2f}, '
  f'95 % ДИ [{rr * math.exp(-1.96 * se):.2f}; {rr * math.exp(1.96 * se):.2f}].')
q1 = F1 / R1
need = None
for f in range(F2, R2 + 1):
    if binom_two_sided(f, R2, q1) < 0.05:
        need = f
        break
p(f'    Чтобы «повторные» базы значимо конвертили ЛУЧШЕ, им нужно было ≥{need} ФД на {R2} рег ({100 * need / R2:.1f} %, '
  f'в {need / R2 / q1:.2f} раза лучше одиночных). Интервал допускает и в 1,3 раза лучше, и в 2 раза хуже.')
p('  → Оба «нулевых» вывода (разные сайты — как случай; ФД — не лучше) недоказуемы на этих объёмах; они не могут '
  'служить опорой формулировки «золотой базы нет».')
p('')

# ================================================================== 7. вывод
p('=' * 100)
p('ВЫВОД v06 / статистика')
p('=' * 100)
p(f'  1) Суммы, не средние: претензий нет. Объёмы малы: «3+» — 21 домен / 72 рег; ФД — 20 против 31; повторы — 26 событий.')
p(f'  2) Перебор срезов не спасает гипотезу: глобальный min-p по 7 статистикам держит избыток «3+» (см. раздел 2), '
  f'Холм даёт ≥3 p={dict((k, h) for k, _, h in holm)["n3"]:.3f}. Направление у всех 7 статистик одно — кучнее кликов.')
p(f'  3) «2+ объяснено (40 vs 42,6)» — сумма недостачи «двоек» ({obs["e2"]} vs {mean_e2:.1f}) и избытка «троек» ({obs["n3"]} vs {mean_n3:.1f}).')
p(f'  4) Устойчивость: без топ-3 доменов 3+ {obs_wo["n3"]} vs {summarize(obs_wo["n3"], sims_wo["n3"], +1)[0]:.1f} '
  f'(p={summarize(obs_wo["n3"], sims_wo["n3"], +1)[3]:.3f}); без любого пула p ≤ {worst[0]:.3f}. Избыток реален.')
p(f'  5) Но объяснение избытка «повторами на одном сайте» на окне не сходится: у {hi3} из 21 домена с 3+ рег в окне 3+ разных '
  f'конвертивших сайта за всё время, по нижней границе в окне — {lo3}, против {m3:.1f} ожидаемых [{l3:.0f}; {h3:.0f}] (p ≤ {p3lo:.3f}).')
p('     Значит часть избытка сидит на разных сайтах одной базы — это и есть «свойство базы», которое гипотеза отрицает.')
p('  6) «Разные сайты как случай» (p=0,12) и «ФД не лучше» (p=0,26) — недостаток мощности, а не подтверждение равенства.')
p('  Итог: сами числа h06 воспроизводятся и устойчивы, но ВЕРДИКТ и формулировка вывода («всё, что называли золотыми базами, '
  'раскладка воспроизводит; избыток — не свойство базы») статистически не держатся: 5 из 7 статистик кучности отклоняются от '
  'кликов в одну сторону, а домены с 3+ разными конвертившими сайтами в окне превышают ожидание.')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

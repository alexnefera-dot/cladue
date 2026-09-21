#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №6 (h06_no_golden_domain), угол «ТЕНИ» (конфаундинг).

Проверяемый результат тестировщика: (1) число баз с 2+ регистрациями в окне
объяснено кликами (40 vs 42.6); (2) баз с 3+ регистрациями 21 против 12.8 —
избыток 1.64×, p=0.002, держится при страте с зоной; (3) избыток идёт от
повторных регистраций на одном сайте (26 vs 2.5); (4) ФД у повторных баз не
лучше.

Что пробуем показать: что избыток «3+» (и/или «≥2 объяснено», и «повторы на
одном сайте») — тень набора контента, дня, зоны, даты, выбросов, объёма дня,
кривых весов или одного-двух пулов. Инструменты:
  1. Воспроизведение главного расчёта и сигнатура «≥1 меньше, ≥3 больше».
  2. Разложение избытка «3+» по пулам / дням / наборам; выкидывание самых
     влиятельных (leave-one-out): исчезает ли избыток.
  3. Более жёсткие страты: набор+день+зона, +блок часа, +час, +аккаунт,
     +дней, +паттерн имени, имя как есть+день+зона.
  4. Подвыборки: зона, период запуска, размер пула, объём дня, дней 2/3,
     семейство — где именно сидит избыток.
  5. Веса: w = кликов^α (α от 0.5 до 3) — можно ли объяснить «≥1 меньше, ≥3
     больше» выпуклостью связи клики→регистрации, без скрытого фактора;
     отдача с клика по терцилям кликов внутри пула.
  6. Внепулевая парная проверка: регистрации ПОСЛЕ окна (всё время − окно)
     у баз с 3+/2/1/0 регистрациями в окне против их пуловых соседей при
     раскладке по кликам после окна.
  7. Повторы на одном сайте: ожидание при брендовом распределении своего
     пула / дня (а не общем); трекер (clickid, subdomain) — дубль клика или
     разные люди; те же даты или разные.
  8. ФД у баз 2+ против одиночных внутри пула (стратифицированное O/E).

Только stdlib. Вывод — в stdout и analysis/export/gipotezy_svod/v06_teni.txt
"""
import csv
import json
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
TRK = os.path.join(BASE, 'export', 'tracker_conversions.jsonl')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'v06_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_SIM = 5000
N_SIM_FAST = 3000
random.seed(1)
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
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return '—'
    return f'{x:.{d}f}'


def pois_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def percentile(sorted_vals, q):
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


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
    n1 = sum(1 for c in counts if c >= 1)
    n2 = sum(1 for c in counts if c >= 2)
    n3 = sum(1 for c in counts if c >= 3)
    n4 = sum(1 for c in counts if c >= 4)
    half = 0
    if tot > 0:
        acc = 0
        for c in sorted(counts, reverse=True):
            acc += c
            half += 1
            if acc * 2 >= tot:
                break
    mean = tot / n if n else 0.0
    var = sum((c - mean) ** 2 for c in counts) / n if n else 0.0
    vm = var / mean if mean > 0 else 0.0
    return {'n1': n1, 'n2': n2, 'n3': n3, 'n4': n4, 'half': half, 'gini': gini(counts), 'vm': vm}


STAT_DEF = [('n1', 'доменов с ≥1 рег', -1), ('n2', 'доменов с ≥2 рег', +1), ('n3', 'доменов с ≥3 рег', +1),
            ('n4', 'доменов с ≥4 рег', +1), ('half', 'доменов на половину рег', -1),
            ('gini', 'Джини', +1), ('vm', 'дисперсия/среднее', +1)]


def strip_suffix(name):
    return re.sub(r'_\d+$', '', name)


# ------------------------------------------------------------------ чтение
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
    r['_set'] = strip_suffix(r['набор контента'])
    r['_reg_after'] = max(0, r['_reg_all'] - r['_reg_w'])
    r['_clk_after'] = max(0.0, r['_clk_all'] - r['_clk_w'])
    r['_days'] = int(fnum(r['дней']))

day_volume = Counter(r['день запуска'] for r in rows)  # объём дня по всему своду

# события по брендам (общее распределение), как в h06
brand_events_dom = {}
for r in rows:
    d = {}
    s = r['какие бренды конвертили'].strip()
    if s:
        for part in s.split(', '):
            m = re.match(r'^(.+) \((\d+)\)$', part)
            if m:
                d[m.group(1)] = int(m.group(2))
    brand_events_dom[r['домен']] = d

# ------------------------------------------------------------------ фильтры (как в h06)
cur = [r for r in rows if r['окно закрыто'] == 'да']
cur = [r for r in cur if r['_days'] >= 2]
cur = [r for r in cur if r['домен'] not in OUTLIERS]
with_unrec = cur
main_rows = [r for r in cur if r['набор контента'] != NO_CONTENT]
unrec_rows = [r for r in cur if r['набор контента'] == NO_CONTENT]

p(f'Файл: {SRC}; строк {len(rows)}; после фильтров h06 (окно закрыто, дней ≥ 2, без выбросов, без «{NO_CONTENT}»): {len(main_rows)} доменов')
p(f'Симуляций: {N_SIM} (главные), {N_SIM_FAST} (страты/подвыборки); random.seed(1)')
p('')


# ------------------------------------------------------------------ пулы и симуляция
def build_pools(domains, key_fn, min_size=3):
    pools = defaultdict(list)
    for r in domains:
        pools[key_fn(r)].append(r)
    return {k: v for k, v in pools.items() if len(v) >= min_size}


def simulate(pools, wfn, rkey, n_sim, per_pool=False):
    """wfn(r) -> вес; регистрации пула раскидываются мультиномиально. Возвращает obs, sims, λ, per-pool E[n3]."""
    doms, specs = [], []
    for k, v in pools.items():
        R = sum(r[rkey] for r in v)
        start = len(doms)
        doms.extend(v)
        if R == 0:
            continue
        w = [max(0.0, wfn(r)) for r in v]
        if sum(w) <= 0:
            w = [1.0] * len(v)
        cum, a = [], 0.0
        for x in w:
            a += x
            cum.append(a)
        specs.append((k, R, list(range(start, start + len(v))), cum))
    n = len(doms)
    obs_counts = [r[rkey] for r in doms]
    obs = stats_of(obs_counts)
    lam = [0.0] * n
    for k, R, idxs, cum in specs:
        tot, prev = cum[-1], 0.0
        for i, c in zip(idxs, cum):
            lam[i] = R * (c - prev) / tot
            prev = c
    sims = defaultdict(list)
    pool_n3 = Counter()
    pool_n1 = Counter()
    for _ in range(n_sim):
        counts = [0] * n
        for k, R, idxs, cum in specs:
            for i in random.choices(idxs, cum_weights=cum, k=R):
                counts[i] += 1
            if per_pool:
                pool_n3[k] += sum(1 for i in idxs if counts[i] >= 3)
                pool_n1[k] += sum(1 for i in idxs if counts[i] >= 1)
        st = stats_of(counts)
        for key, val in st.items():
            sims[key].append(val)
    res = {'doms': doms, 'lam': lam, 'obs': obs, 'sims': sims, 'R': sum(obs_counts), 'n': n,
           'n_pools': len(pools), 'n_pools_reg': len(specs)}
    if per_pool:
        res['pool_e3'] = {k: pool_n3[k] / n_sim for k, R, idxs, cum in specs}
        res['pool_e1'] = {k: pool_n1[k] / n_sim for k, R, idxs, cum in specs}
        res['pool_o3'] = {k: sum(1 for r in pools[k] if r[rkey] >= 3) for k, R, idxs, cum in specs}
        res['pool_o1'] = {k: sum(1 for r in pools[k] if r[rkey] >= 1) for k, R, idxs, cum in specs}
        res['pool_R'] = {k: R for k, R, idxs, cum in specs}
    return res


def summarize(res, key):
    vals = res['sims'][key]
    s = sorted(vals)
    mean = sum(s) / len(s)
    o = res['obs'][key]
    direction = dict((k, d) for k, _, d in STAT_DEF)[key]
    if direction > 0:
        pv = sum(1 for v in vals if v >= o) / len(vals)
    else:
        pv = sum(1 for v in vals if v <= o) / len(vals)
    return o, mean, percentile(s, 0.025), percentile(s, 0.975), (o / mean if mean > 0 else None), pv


def line(res, label, keys=('n1', 'n2', 'n3', 'n4', 'half', 'vm')):
    parts = []
    for k in keys:
        o, m, lo, hi, oe, pv = summarize(res, k)
        d = 2 if k in ('vm', 'gini') else 1
        if k == 'gini':
            parts.append(f'{k} {o:.3f}/{m:.3f} p={pv:.3f}')
        else:
            parts.append(f'{k} {fmt(o, 0 if isinstance(o, int) else d)}/{m:.1f} [{lo:.0f};{hi:.0f}] O/E {fmt(oe)} p={pv:.3f}')
    p(f'  {label:44} n={res["n"]:5d} рег={res["R"]:4d} пулов={res["n_pools"]:3d}: ' + '; '.join(parts))


def full_table(res, title):
    p('-' * 100)
    p(title)
    p(f'  доменов {res["n"]}, регистраций {res["R"]}, пулов {res["n_pools"]} (с регистрациями {res["n_pools_reg"]})')
    p(f'  {"статистика":28} {"набл.":>8} {"средн.сим":>10} {"95% интервал":>18} {"O/E":>6} {"p":>7}')
    for key, label, direction in STAT_DEF:
        o, m, lo, hi, oe, pv = summarize(res, key)
        d = 3 if key == 'gini' else (2 if key == 'vm' else 1)
        p(f'  {label:28} {fmt(o, 0 if isinstance(o, int) else d):>8} {fmt(m, d):>10} {("[" + fmt(lo, d) + "; " + fmt(hi, d) + "]"):>18} {fmt(oe):>6} {fmt(pv, 3):>7}')


W_CLK = lambda r: r['_clk_w']
KEY_MAIN = lambda r: (r['_set'], r['день запуска'])

# ================================================================ 1. ВОСПРОИЗВЕДЕНИЕ
p('=' * 100)
p('1. ВОСПРОИЗВЕДЕНИЕ ГЛАВНОГО РАСЧЁТА h06 (пул = набор без _NN + день, ≥3 доменов, w = клики в окне)')
p('=' * 100)
pools_main = build_pools(main_rows, KEY_MAIN)
res_main = simulate(pools_main, W_CLK, '_reg_w', N_SIM, per_pool=True)
full_table(res_main, '1а. главный расчёт')
o1, m1, *_ = summarize(res_main, 'n1')
o3, m3, *_ = summarize(res_main, 'n3')
p(f'  → сигнатура: доменов с ≥1 регистрацией МЕНЬШЕ ожидаемого ({o1} vs {m1:.1f}), с ≥3 БОЛЬШЕ ({o3} vs {m3:.1f}), ')
p('    с ≥2 столько же — это не «≥2 объяснено, ≥3 нет», а одно и то же: регистрации ложатся кучнее, чем клики.')
p('')

# ================================================================ 2. РАЗЛОЖЕНИЕ ИЗБЫТКА «3+» ПО ПУЛАМ
p('=' * 100)
p('2. ГДЕ СИДИТ ИЗБЫТОК «3+»: разложение по пулам, дням, наборам; выкидывание самых влиятельных')
p('=' * 100)
excess = []
for k in res_main['pool_o3']:
    o = res_main['pool_o3'][k]
    e = res_main['pool_e3'][k]
    excess.append((o - e, o, e, k))
excess.sort(reverse=True)
p(f'  пулов с регистрациями {len(excess)}; пулов с наблюдённым «3+» {sum(1 for x in excess if x[1] > 0)}; '
  f'сумма избытка (O−E) по всем пулам {sum(x[0] for x in excess):.1f}')
p(f'  {"пул (набор | день)":58} {"дом.":>4} {"рег":>4} {"O 3+":>5} {"E 3+":>6} {"O−E":>6} {"O 1+":>5} {"E 1+":>6}')
for ex, o, e, k in excess[:14]:
    v = pools_main[k]
    p(f'  {(k[0][:44] + " | " + k[1][5:]):58} {len(v):>4} {res_main["pool_R"][k]:>4} {o:>5} {e:>6.2f} {ex:>6.2f} '
      f'{res_main["pool_o1"][k]:>5} {res_main["pool_e1"][k]:>6.1f}')
p(f'  пулов с O−E > 0: {sum(1 for x in excess if x[0] > 0.05)}, с O−E < 0: {sum(1 for x in excess if x[0] < -0.05)}; '
  f'доля избытка в топ-3 пулах: {sum(x[0] for x in excess[:3]) / max(1e-9, sum(x[0] for x in excess)) * 100:.0f} %, '
  f'в топ-5: {sum(x[0] for x in excess[:5]) / max(1e-9, sum(x[0] for x in excess)) * 100:.0f} %')
p('')

p('2а. Выкидываем самые «избыточные» пулы (по O−E для 3+) и пересчитываем:')
for drop in (1, 2, 3, 5, 8):
    dropped = {x[3] for x in excess[:drop]}
    pools_d = {k: v for k, v in pools_main.items() if k not in dropped}
    res_d = simulate(pools_d, W_CLK, '_reg_w', N_SIM_FAST)
    line(res_d, f'без топ-{drop} пулов', keys=('n1', 'n2', 'n3', 'half'))
p('  (оговорка: выбор пулов по самому избытку — подгонка; это про то, «сколько пулов делают эффект», а не тест)')
p('')

p('2б. Leave-one-out по ДНЮ запуска (убираем все пулы одного дня) — минимум O/E для 3+ и максимум p:')
days = sorted({k[1] for k in pools_main})
loo_day = []
for d in days:
    pools_d = {k: v for k, v in pools_main.items() if k[1] != d}
    if sum(sum(r['_reg_w'] for r in v) for v in pools_d.values()) == 0:
        continue
    res_d = simulate(pools_d, W_CLK, '_reg_w', 1500)
    o, m, lo, hi, oe, pv = summarize(res_d, 'n3')
    loo_day.append((pv, oe, o, m, d, res_d['n'], res_d['R']))
loo_day.sort(reverse=True)
for pv, oe, o, m, d, n, R in loo_day[:5]:
    p(f'  без дня {d}: n={n}, рег={R}, 3+ {o} vs {m:.1f}, O/E {oe:.2f}, p={pv:.3f}')
p(f'  … всего дней {len(loo_day)}; диапазон O/E для 3+ при выкидывании любого дня: {min(x[1] for x in loo_day):.2f}–{max(x[1] for x in loo_day):.2f}, p от {min(x[0] for x in loo_day):.3f} до {max(x[0] for x in loo_day):.3f}')
p('')

p('2в. Leave-one-out по НАБОРУ контента:')
sets = sorted({k[0] for k in pools_main})
loo_set = []
for s_ in sets:
    pools_d = {k: v for k, v in pools_main.items() if k[0] != s_}
    if sum(sum(r['_reg_w'] for r in v) for v in pools_d.values()) == 0:
        continue
    res_d = simulate(pools_d, W_CLK, '_reg_w', 1000)
    o, m, lo, hi, oe, pv = summarize(res_d, 'n3')
    loo_set.append((pv, oe, o, m, s_, res_d['n'], res_d['R']))
loo_set.sort(reverse=True)
for pv, oe, o, m, s_, n, R in loo_set[:5]:
    p(f'  без набора {s_[:40]}: n={n}, рег={R}, 3+ {o} vs {m:.1f}, O/E {oe:.2f}, p={pv:.3f}')
p(f'  … всего наборов {len(loo_set)}; диапазон O/E: {min(x[1] for x in loo_set):.2f}–{max(x[1] for x in loo_set):.2f}, p до {max(x[0] for x in loo_set):.3f}')
p('')

# ================================================================ 3. ЖЁСТКИЕ СТРАТЫ
p('=' * 100)
p('3. БОЛЕЕ ЖЁСТКИЕ СТРАТЫ (пулы ≥3 доменов; w = клики в окне)')
p('=' * 100)
strata = [
    ('набор + день (база h06)', KEY_MAIN),
    ('набор + день + зона', lambda r: (r['_set'], r['день запуска'], r['зона'])),
    ('имя как есть + день + зона', lambda r: (r['набор контента'], r['день запуска'], r['зона'])),
    ('набор + день + зона + блок часа', lambda r: (r['_set'], r['день запуска'], r['зона'], r['блок часа'])),
    ('набор + день + зона + час запуска', lambda r: (r['_set'], r['день запуска'], r['зона'], r['час запуска'])),
    ('набор + день + зона + дней (2/3)', lambda r: (r['_set'], r['день запуска'], r['зона'], r['_days'])),
    ('набор + день + зона + паттерн имени', lambda r: (r['_set'], r['день запуска'], r['зона'], r['паттерн имени'])),
    ('набор + день + зона + который раз акк.', lambda r: (r['_set'], r['день запуска'], r['зона'], r['который раз аккаунт'])),
    ('набор + день + зона + длина метки', lambda r: (r['_set'], r['день запуска'], r['зона'], r['длина метки'])),
]
p('  (страты с аккаунтом вебмастера или cf-аккаунтом не дают ни одного пула ≥3 доменов — у аккаунта ≤5 баз, на день+набор ≤2)')
strata_res = {}
for label, kf in strata:
    pools_s = build_pools(main_rows, kf)
    res_s = simulate(pools_s, W_CLK, '_reg_w', N_SIM_FAST)
    strata_res[label] = res_s
    line(res_s, label, keys=('n1', 'n2', 'n3', 'half', 'vm'))
p('')

# ================================================================ 4. ПОДВЫБОРКИ
p('=' * 100)
p('4. ПОДВЫБОРКИ: где сидит избыток «3+» (пул = набор + день внутри подвыборки, ≥3 доменов)')
p('=' * 100)
vol_sorted = sorted(day_volume.values())
v_lo, v_hi = percentile(vol_sorted, 1 / 3), percentile(vol_sorted, 2 / 3)
pool_size_of = {}
for k, v in pools_main.items():
    for r in v:
        pool_size_of[r['домен']] = len(v)
subsets = [
    ('зона team', lambda r: r['зона'] == 'team'),
    ('зона lol', lambda r: r['зона'] == 'lol'),
    ('зона casino/buzz/прочие', lambda r: r['зона'] not in ('team', 'lol')),
    ('запуск ≤ 09-04', lambda r: r['день запуска'] <= '2026-09-04'),
    ('запуск 09-05..09-10', lambda r: '2026-09-05' <= r['день запуска'] <= '2026-09-10'),
    ('запуск ≥ 09-11', lambda r: r['день запуска'] >= '2026-09-11'),
    ('пул 3–9 доменов', lambda r: pool_size_of.get(r['домен'], 0) <= 9),
    ('пул ≥10 доменов', lambda r: pool_size_of.get(r['домен'], 0) >= 10),
    (f'объём дня ≤ {v_lo:.0f} доменов', lambda r: day_volume[r['день запуска']] <= v_lo),
    (f'объём дня {v_lo:.0f}–{v_hi:.0f}', lambda r: v_lo < day_volume[r['день запуска']] <= v_hi),
    (f'объём дня > {v_hi:.0f}', lambda r: day_volume[r['день запуска']] > v_hi),
    ('дней = 2', lambda r: r['_days'] == 2),
    ('дней = 3', lambda r: r['_days'] == 3),
    ('семейство NEW', lambda r: r['семейство'] == 'NEW'),
    ('семейство content-дата', lambda r: r['семейство'] == 'content-дата'),
    ('семейство archive', lambda r: r['семейство'] == 'archive'),
    ('семейство nabory', lambda r: r['семейство'] == 'nabory'),
    ('прочие семейства', lambda r: r['семейство'] not in ('NEW', 'content-дата', 'archive', 'nabory')),
    ('день недели пн–пт', lambda r: int(fnum(r['день недели'])) <= 5),
    ('день недели сб–вс', lambda r: int(fnum(r['день недели'])) >= 6),
]
sub_res = {}
for label, f in subsets:
    sub = [r for r in main_rows if f(r)]
    pools_s = build_pools(sub, KEY_MAIN)
    if not pools_s or sum(sum(r['_reg_w'] for r in v) for v in pools_s.values()) < 5:
        p(f'  {label:44} мало регистраций — пропуск')
        continue
    res_s = simulate(pools_s, W_CLK, '_reg_w', N_SIM_FAST)
    sub_res[label] = res_s
    line(res_s, label, keys=('n1', 'n2', 'n3', 'half'))
p('')

# ================================================================ 5. ВЕСА
p('=' * 100)
p('5. ВЕСА: w = кликов^α — объясняется ли сигнатура «≥1 меньше, ≥3 больше» выпуклостью связи клики→регистрации')
p('=' * 100)
p('  (α > 1: домены с большими кликами конвертят непропорционально лучше; α < 1 — хуже. Установлено ранее: по всему')
p('   своду больше кликов → ХУЖЕ отдача с клика, т.е. α < 1, что делает избыток «3+» только больше.)')
alpha_res = {}
for a in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0):
    res_a = simulate(pools_main, lambda r, a=a: r['_clk_w'] ** a, '_reg_w', N_SIM_FAST)
    alpha_res[a] = res_a
    line(res_a, f'α = {a}', keys=('n1', 'n2', 'n3', 'half', 'vm'))
p('')
p('5а. Отдача с клика ВНУТРИ пула по терцилям кликов домена (ранг внутри пула; O = рег, E = рег пула × доля кликов):')
tert = defaultdict(lambda: [0, 0.0, 0, 0.0])  # O, E, доменов, кликов
for k, v in pools_main.items():
    R = sum(r['_reg_w'] for r in v)
    W = sum(r['_clk_w'] for r in v)
    if W <= 0:
        continue
    srt = sorted(v, key=lambda r: r['_clk_w'])
    n = len(srt)
    for i, r in enumerate(srt):
        t = min(2, int(3 * i / n))
        tert[t][0] += r['_reg_w']
        tert[t][1] += R * r['_clk_w'] / W
        tert[t][2] += 1
        tert[t][3] += r['_clk_w']
def tert_expect(alpha):
    e = [0.0, 0.0, 0.0]
    for k, v in pools_main.items():
        R = sum(r['_reg_w'] for r in v)
        W = sum(r['_clk_w'] ** alpha for r in v)
        if W <= 0:
            continue
        srt = sorted(v, key=lambda r: r['_clk_w'])
        n = len(srt)
        for i, r in enumerate(srt):
            e[min(2, int(3 * i / n))] += R * r['_clk_w'] ** alpha / W
    return e
e125, e150 = tert_expect(1.25), tert_expect(1.5)
for t, lab in enumerate(('нижняя треть по кликам', 'средняя треть', 'верхняя треть')):
    O, E, nd, W = tert[t]
    p(f'  {lab:26} доменов {nd:5d} кликов {int(W):8d} рег {O:4d} ожид.(α=1) {E:6.1f} O/E {O / E if E else 0:.2f}; '
      f'ожид.(α=1.25) {e125[t]:6.1f} O/E {O / e125[t] if e125[t] else 0:.2f}; ожид.(α=1.5) {e150[t]:6.1f} O/E {O / e150[t] if e150[t] else 0:.2f}; '
      f'рег/10 тыс. кликов {10000 * O / W if W else 0:.2f}')
p('  → средняя отдача с клика внутри пула ПАДАЕТ с кликами (α < 1 по среднему), а α > 1 подгоняет только разброс:')
p('    выпуклость связи клики→регистрации избыток «3+» не объясняет — при α ≥ 1.25 верхняя треть недобирает ещё сильнее.')
p('')

# ================================================================ 6. ВНЕПУЛЕВАЯ ПАРНАЯ ПРОВЕРКА: ПОСЛЕ ОКНА
p('=' * 100)
p('6. ПОСЛЕ ОКНА: регистрации за пределами окна (всё время − окно) у баз, отобранных по регистрациям В окне')
p('   Раскладка после-оконных регистраций пула по доменам пула ∝ после-оконным кликам (всё время − окно).')
p('   Если база «золотая» — у баз с 3+ в окне после окна должно быть больше, чем полагается по кликам.')
p('=' * 100)
after_R = sum(r['_reg_after'] for r in main_rows if r['домен'] in pool_size_of)
p(f'  регистраций после окна в главном наборе: {after_R} (всё время {sum(r["_reg_all"] for r in main_rows if r["домен"] in pool_size_of)}, в окне {res_main["R"]})')
groups = [('3+ в окне', lambda r: r['_reg_w'] >= 3), ('2 в окне', lambda r: r['_reg_w'] == 2),
          ('2+ в окне', lambda r: r['_reg_w'] >= 2), ('1 в окне', lambda r: r['_reg_w'] == 1),
          ('0 в окне', lambda r: r['_reg_w'] == 0)]
# симуляция: для каждой группы считаем сколько после-оконных рег попало
specs_after = []
for k, v in pools_main.items():
    R = sum(r['_reg_after'] for r in v)
    if R == 0:
        continue
    w = [r['_clk_after'] for r in v]
    if sum(w) <= 0:
        w = [1.0] * len(v)
    cum, a = [], 0.0
    for x in w:
        a += x
        cum.append(a)
    specs_after.append((v, R, cum))
gsim = {g: [] for g, _ in groups}
for _ in range(N_SIM):
    cnt = Counter()
    for v, R, cum in specs_after:
        for r in random.choices(v, cum_weights=cum, k=R):
            cnt[r['домен']] += 1
    for g, f in groups:
        gsim[g].append(sum(cnt[r['домен']] for v, R, cum in specs_after for r in v if f(r)))
p(f'  {"группа":12} {"доменов":>8} {"кликов после":>13} {"рег после":>10} {"ожид.":>7} {"95% инт.":>12} {"O/E":>6} {"p(≥)":>7} {"p(≤)":>7}')
for g, f in groups:
    doms_g = [r for v, R, cum in specs_after for r in v if f(r)]
    nd = sum(1 for k, v in pools_main.items() for r in v if f(r))
    O = sum(r['_reg_after'] for k, v in pools_main.items() for r in v if f(r))
    W = sum(r['_clk_after'] for k, v in pools_main.items() for r in v if f(r))
    s = sorted(gsim[g])
    m = sum(s) / len(s)
    pge = sum(1 for x in s if x >= O) / len(s)
    ple = sum(1 for x in s if x <= O) / len(s)
    p(f'  {g:12} {nd:>8} {int(W):>13} {O:>10} {m:>7.1f} {("[" + fmt(percentile(s, .025), 0) + "; " + fmt(percentile(s, .975), 0) + "]"):>12} {fmt(O / m if m else None):>6} {pge:>7.3f} {ple:>7.3f}')
# на каком сайте после-оконные регистрации у баз с 1 в окне: тот же (S=1) или другой (S≥2)
g1a = [r for v in pools_main.values() for r in v if r['_reg_w'] == 1 and r['_reg_after'] >= 1]
p(f'  Базы с 1 рег в окне и ≥1 после окна: {len(g1a)} доменов, рег всего {sum(r["_reg_all"] for r in g1a)}, '
  f'сайтов с регистрацией {sum(r["_brands"] for r in g1a)}; из них все регистрации на ОДНОМ сайте: {sum(1 for r in g1a if r["_brands"] == 1)}, '
  f'на разных: {sum(1 for r in g1a if r["_brands"] >= 2)}')
g0a = [r for v in pools_main.values() for r in v if r['_reg_w'] == 0 and r['_reg_after'] >= 1]
p(f'  Базы с 0 в окне и ≥1 после: {len(g0a)} доменов, рег {sum(r["_reg_all"] for r in g0a)}')
p('  оговорка: после-оконные регистрации — 15 % всех, у окна 3 суток хвост мал; клики после окна включают клики на')
p('  сайты, вышедшие поздно. Но ранжирование доменов по кликам после окна не зависит от их регистраций в окне.')
p('')

# ================================================================ 7. ПОВТОРЫ НА ОДНОМ САЙТЕ
p('=' * 100)
p('7. ПОВТОРЫ НА ОДНОМ САЙТЕ (R − S): ожидание при брендовом распределении своего пула / дня; трекер')
p('=' * 100)
doms_main = [r for v in pools_main.values() for r in v]
# распределения брендов: общее (по всем строкам), по пулу, по дню, по набору — по СОБЫТИЯМ (как в h06), LOO домена
glob = Counter()
for r in rows:
    glob.update(brand_events_dom[r['домен']])
by_pool = defaultdict(Counter)
by_day = defaultdict(Counter)
by_set = defaultdict(Counter)
for r in rows:
    if r['домен'] in OUTLIERS:
        continue
    by_pool[(r['_set'], r['день запуска'])].update(brand_events_dom[r['домен']])
    by_day[r['день запуска']].update(brand_events_dom[r['домен']])
    by_set[r['_set']].update(brand_events_dom[r['домен']])


def exp_repeats(dist_fn, loo=True):
    """Σ_доменов (k − E[разных брендов при k независимых розыгрышах])."""
    tot_e = 0.0
    tot_o = 0
    for r in doms_main:
        k = r['_reg_all']
        if k < 2:
            continue
        dist = Counter(dist_fn(r))
        if loo:
            dist.subtract(brand_events_dom[r['домен']])
            dist = Counter({b: c for b, c in dist.items() if c > 0})
        N = sum(dist.values())
        if N <= 0:
            dist = glob
            N = sum(dist.values())
        e_distinct = sum(1 - (1 - c / N) ** k for c in dist.values())
        tot_e += k - e_distinct
        tot_o += k - r['_brands']
    return tot_o, tot_e


for lab, fn in (('общее распределение 536 событий (как h06), LOO домена', lambda r: glob),
                ('распределение своего ДНЯ запуска, LOO', lambda r: by_day[r['день запуска']]),
                ('распределение своего НАБОРА, LOO', lambda r: by_set[r['_set']]),
                ('распределение своего ПУЛА (набор+день), LOO', lambda r: by_pool[(r['_set'], r['день запуска'])])):
    O, E = exp_repeats(fn)
    p(f'  {lab:56} повторов набл. {O}, ожид. {E:.1f}, O/E {O / E if E else 0:.1f}')
p('  (LOO: события самого домена вычтены из распределения; для пула с малым числом событий ожидание шумное)')
p('')

# трекер
if os.path.exists(TRK):
    trk = [json.loads(l) for l in open(TRK, encoding='utf-8')]
    regs = [t for t in trk if t['event'] == 'reg' and t['subdomain']]
    by_dom = defaultdict(list)
    for t in regs:
        parts = t['subdomain'].split('.')
        if len(parts) >= 3:
            by_dom['.'.join(parts[-2:])].append(t)
    rep_doms = [r for r in doms_main if r['_reg_all'] > r['_brands']]
    n_rep = sum(r['_reg_all'] - r['_brands'] for r in rep_doms)
    same_click = 0
    diff_click = 0
    same_day = 0
    diff_day = 0
    detail = []
    for r in rep_doms:
        ev = by_dom.get(r['домен'], [])
        bysite = defaultdict(list)
        for t in ev:
            bysite[t['subdomain'].split('.')[0]].append(t)
        for site, lst in bysite.items():
            if len(lst) < 2:
                continue
            lst.sort(key=lambda t: t['at'])
            first = lst[0]
            for t in lst[1:]:
                if t['clickid'] == first['clickid'] or any(t['clickid'] == u['clickid'] for u in lst if u is not t):
                    same_click += 1
                else:
                    diff_click += 1
                if t['at'][:10] == first['at'][:10]:
                    same_day += 1
                else:
                    diff_day += 1
            detail.append(f'{r["домен"]} {site} ×{len(lst)} ({", ".join(t["at"][5:10] for t in lst)}; clickid {"разные" if len({t["clickid"] for t in lst}) == len(lst) else "ПОВТОР"})')
    p(f'  Трекер (tracker_conversions.jsonl, {len(regs)} регистраций с subdomain): у {len(rep_doms)} доменов главного набора с R > S')
    p(f'    повторов по своду {n_rep}; в трекере найдено повторных регистраций на том же сайте {same_click + diff_click}: '
      f'тот же clickid (дубль одного клика) {same_click}, другой clickid (другой визит) {diff_click}; '
      f'в тот же день, что первая: {same_day}, в другой день: {diff_day}')
    for d in detail[:20]:
        p('    ' + d)
    p('  → повторы на одном сайте — это в основном разные клики в разные дни, т.е. сайт стабильно собирает регистрации,')
    p('    а не дубль одной записи.')
    p('')
    p('7а. Перестановка бренда регистрации ВНУТРИ ДНЯ / ВНУТРИ ПУЛА (число регистраций у каждого домена сохранено; бренды —')
    p('    из трекера по subdomain; домены главного набора, у которых число регистраций в трекере = «регистраций» свода):')
    dom_by_name = {r['домен']: r for r in doms_main}
    trk_regs = defaultdict(list)
    for t in regs:
        parts = t['subdomain'].split('.')
        if len(parts) >= 3:
            d = '.'.join(parts[-2:])
            if d in dom_by_name:
                trk_regs[d].append(parts[0])
    ok = [d for d, r in dom_by_name.items() if r['_reg_all'] >= 1 and len(trk_regs.get(d, [])) == r['_reg_all']]
    bad = [d for d, r in dom_by_name.items() if r['_reg_all'] >= 1 and len(trk_regs.get(d, [])) != r['_reg_all']]
    p(f'    доменов с регистрациями {sum(1 for r in doms_main if r["_reg_all"] >= 1)}; совпало с трекером {len(ok)}, не совпало {len(bad)} '
      '(пример: ' + ', '.join(d + ' свод ' + str(dom_by_name[d]['_reg_all']) + '/трекер ' + str(len(trk_regs.get(d, []))) for d in bad[:5]) + ')')
    obs_rep = sum(len(trk_regs[d]) - len(set(trk_regs[d])) for d in ok)
    for lab, keyf in (('внутри дня запуска', lambda d: dom_by_name[d]['день запуска']),
                      ('внутри пула (набор+день)', lambda d: (dom_by_name[d]['_set'], dom_by_name[d]['день запуска'])),
                      ('внутри набора', lambda d: dom_by_name[d]['_set']),
                      ('по всем доменам', lambda d: 0)):
        grp = defaultdict(list)
        for d in ok:
            grp[keyf(d)].append(d)
        sims_rep = []
        for _ in range(N_SIM):
            tot = 0
            for g, ds in grp.items():
                labels = [b for d in ds for b in trk_regs[d]]
                random.shuffle(labels)
                i = 0
                for d in ds:
                    k = len(trk_regs[d])
                    if k >= 2:
                        tot += k - len(set(labels[i:i + k]))
                    i += k
            sims_rep.append(tot)
        ss = sorted(sims_rep)
        m = sum(ss) / len(ss)
        n_multi = sum(1 for ds in grp.values() if sum(1 for d in ds if len(trk_regs[d]) >= 2) >= 1 and len(ds) >= 2)
        p(f'    {lab:28} групп {len(grp):4d} (с ≥2 доменами и повторяемым доменом {n_multi:3d}): повторов набл. {obs_rep}, ожид. {m:.1f} '
          f'[{percentile(ss, .025):.0f}; {percentile(ss, .975):.0f}], O/E {obs_rep / m if m else 0:.1f}, p = {sum(1 for x in ss if x >= obs_rep) / len(ss):.3f}')
    p('    (внутри пула у многих доменов нет соседей с регистрациями — перестановка там ничего не меняет, поэтому ожидание завышено)')
else:
    p('  трекер не найден — пропуск')
p('')

# ================================================================ 8. ФД ВНУТРИ ПУЛА
p('=' * 100)
p('8. ФД у баз с 2+ регистрациями в окне против одиночных — стратифицированно по пулу (E = ставка ФД пула × рег группы)')
p('=' * 100)
O2 = E2 = O1 = E1 = 0.0
R2 = R1 = 0
for k, v in pools_main.items():
    Rp = sum(r['_reg_w'] for r in v)
    Fp = sum(r['_fd_w'] for r in v)
    if Rp == 0:
        continue
    q = Fp / Rp
    for r in v:
        if r['_reg_w'] >= 2:
            O2 += r['_fd_w']
            E2 += q * r['_reg_w']
            R2 += r['_reg_w']
        elif r['_reg_w'] == 1:
            O1 += r['_fd_w']
            E1 += q
            R1 += 1
# перестановка: внутри пула перемешиваем ФД между регистрациями (гипергеометрически): проще — перестановка меток «2+» между доменами пула с сохранением рег? нет: сравниваем ФД/рег
# перестановочный тест: внутри пула случайно раздаём ФД пула по регистрациям пула (каждая регистрация равновероятна)
sim_o2 = []
for _ in range(N_SIM):
    tot = 0
    for k, v in pools_main.items():
        Fp = sum(r['_fd_w'] for r in v)
        if Fp == 0:
            continue
        slots = []
        for r in v:
            slots.extend([r['_reg_w'] >= 2] * r['_reg_w'])
        tot += sum(random.sample(slots, Fp))
    sim_o2.append(tot)
s = sorted(sim_o2)
p(f'  2+ рег: ФД {int(O2)} на {R2} рег ({100 * O2 / R2 if R2 else 0:.1f} %), ожид. по пулам {E2:.1f} (O/E {O2 / E2 if E2 else 0:.2f}); '
  f'перестановка ФД по регистрациям внутри пула: 95 % [{percentile(s, .025):.0f}; {percentile(s, .975):.0f}], p(≤) = {sum(1 for x in s if x <= O2) / len(s):.3f}, p(≥) = {sum(1 for x in s if x >= O2) / len(s):.3f}')
p(f'  1 рег:  ФД {int(O1)} на {R1} рег ({100 * O1 / R1 if R1 else 0:.1f} %), ожид. по пулам {E1:.1f} (O/E {O1 / E1 if E1 else 0:.2f})')
p('')

# ================================================================ ИТОГ
p('=' * 100)
p('ИТОГ СКЕПТИКА (тени)')
p('=' * 100)
b = res_main
o3, m3, lo3, hi3, oe3, p3 = summarize(b, 'n3')
o1, m1, lo1, hi1, oe1, p1 = summarize(b, 'n1')
o2, m2, lo2, hi2, oe2, p2 = summarize(b, 'n2')
p(f'База h06: ≥1 {o1} vs {m1:.1f} (O/E {oe1:.2f}, p={p1:.3f}); ≥2 {o2} vs {m2:.1f} (O/E {oe2:.2f}); ≥3 {o3} vs {m3:.1f} (O/E {oe3:.2f}, p={p3:.3f}).')
p('Жёсткие страты (3+: O/E, p):')
for label, res_s in strata_res.items():
    o, m, lo, hi, oe, pv = summarize(res_s, 'n3')
    o1_, m1_, *_r, pv1 = summarize(res_s, 'n1')
    p(f'  {label:44} n={res_s["n"]:5d} рег={res_s["R"]:4d}: 3+ {o} vs {m:.1f} O/E {fmt(oe)} p={pv:.3f}; ≥1 {o1_} vs {m1_:.1f} p={pv1:.3f}')
p('Подвыборки (3+: O/E, p):')
for label, res_s in sub_res.items():
    o, m, lo, hi, oe, pv = summarize(res_s, 'n3')
    p(f'  {label:44} n={res_s["n"]:5d} рег={res_s["R"]:4d}: 3+ {o} vs {m:.1f} O/E {fmt(oe)} p={pv:.3f}')
p('Веса кликов^α (≥1 O/E, ≥3 O/E, p3):')
for a, res_a in alpha_res.items():
    o, m, lo, hi, oe, pv = summarize(res_a, 'n3')
    o1_, m1_, *_r, pv1 = summarize(res_a, 'n1')
    p(f'  α={a}: ≥1 {o1_} vs {m1_:.1f} (p={pv1:.3f}); ≥3 {o} vs {m:.1f} O/E {fmt(oe)} p={pv:.3f}')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

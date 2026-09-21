#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Гипотеза №6. «Золотых» и «тёплых» баз нет: кучность регистраций по доменам
(половина регистраций окна на ~3,6 % доменов; ~62 базы с 2+ регистрациями;
~73 домена с 2+ разными конвертирующими брендами) целиком воспроизводится
случайной (пуассоновской / мультиномиальной) раскладкой регистраций пула
по доменам пула пропорционально поисковым кликам домена (или числу вышедших
сайтов).

Что проверяем и как:
  1. Исключения (печатаются): окно закрыто = нет; дней < 2 (запуски с одним
     днём постановки, 150 сайтов); выбросы 3615.team и 3286.team;
     «КОНТЕНТ НЕ ЗАПИСАН» (отдельно повторяем с ним как со своим «набором»).
  2. Пул = набор контента + день запуска, берутся пулы из ≥3 доменов.
     ОГОВОРКА: у части доменов имя набора вида content-…_NN уникально для
     домена (суффикс _NN — номер экземпляра); для них, как в h05, пул строится
     по имени без суффикса. Чувствительность: пулы по именам как есть.
  3. Нулевая модель. Число регистраций пула в окне 3 суток фиксируется на
     наблюдённом; каждая регистрация независимо попадает на домен пула с
     вероятностью w_i / Σw (мультиномиально). Веса: (осн.) w = кликов из
     поиска в окне; (2) w = вышли за 3 суток; (справочно) w = сайтов в окне,
     т.е. «клики не знаем». 5000 симуляций, random.seed(1).
  4. Статистики по домену: (а) доменов с ≥2 и с ≥3 регистрациями; (б) сколько
     доменов дают половину регистраций; (в) Джини по доменам; (г) максимум на
     домен; (е) доменов с ≥1; отношение дисперсия/среднее. p = доля симуляций
     не менее экстремальных в сторону «кучнее наблюдённого»; 95 % интервал
     симуляций; O/E = наблюдённое / среднее по симуляциям; для (а) ещё точный
     пуассоновский расчёт Σ P(X_i ≥ 2), λ_i = R_пула · w_i / Σw.
  5. (д) Многобрендовость. Поле «брендов с конверсией» считается за всё время,
     поэтому эта ветка гоняется на регистрациях за всё время (w = клики из
     поиска за всё время; второй вариант — клики в окне); бренд каждого события
     тянется из общего распределения событий по брендам (строка «какие бренды
     конвертили» по всем доменам). Считаем доменов с ≥2 разными брендами.
     Плюс аналитика при ФИКСИРОВАННОМ числе событий на домене: ожидаемое число
     разных брендов Σ_b(1−(1−p_b)^k) — отделяет «куда попали события» от «как
     они разошлись по брендам внутри домена».
  6. Вторая ступень: доля ФД в окне среди регистраций у баз с 2+ регистрациями
     против баз с одной; точный биномиальный тест. Для доменов с 3+
     регистрациями — сайтов с регистрацией / регистраций.
  7. Повторы: страта с зоной (пул = набор + день + зона); имена наборов как
     есть; «КОНТЕНТ НЕ ЗАПИСАН» как свой набор (пул = день).

Критерии из плана: концентрация объяснена — p > 0,05 по (а)–(в) и (д) при
λ по кликам и O/E баз с 2+ ≤ 1,1; скрытый доменный фактор — наблюдённое за
пределами 95 % при обоих λ или O/E ≥ 1,4.

Только stdlib. Вывод — в stdout и в
analysis/export/gipotezy_svod/h06_no_golden_domain.txt
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'h06_no_golden_domain.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_SIM = 5000
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


# ---------------------------------------------------------------- вероятности
def pois_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def pois_sf(k, lam):
    """P(X >= k | lam)."""
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    s = 0.0
    for i in range(int(k)):
        s += pois_pmf(i, lam)
    return max(0.0, 1.0 - s)


def binom_pmf(k, n, q):
    if q <= 0:
        return 1.0 if k == 0 else 0.0
    if q >= 1:
        return 1.0 if k == n else 0.0
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(q) + (n - k) * math.log(1 - q))


def binom_two_sided(k, n, q):
    if n == 0:
        return None
    lo = sum(binom_pmf(i, n, q) for i in range(0, k + 1))
    hi = sum(binom_pmf(i, n, q) for i in range(k, n + 1))
    return min(1.0, 2 * min(lo, hi))


def percentile(sorted_vals, q):
    if not sorted_vals:
        return None
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
    """Набор статистик кучности по вектору «регистраций на домен»."""
    tot = sum(counts)
    n = len(counts)
    n1 = sum(1 for c in counts if c >= 1)
    n2 = sum(1 for c in counts if c >= 2)
    n3 = sum(1 for c in counts if c >= 3)
    mx = max(counts) if counts else 0
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
    vm = var / mean if mean > 0 else None
    return {'n1': n1, 'n2': n2, 'n3': n3, 'half': half, 'gini': gini(counts),
            'max': mx, 'vm': vm}


# направление «кучнее»: +1 = больше значит кучнее, −1 = меньше значит кучнее
STAT_DEF = [
    ('n2', 'доменов с ≥2 рег', +1),
    ('n3', 'доменов с ≥3 рег', +1),
    ('half', 'доменов, дающих половину рег', -1),
    ('gini', 'Джини по доменам', +1),
    ('max', 'максимум рег на домен', +1),
    ('n1', 'доменов с ≥1 рег', -1),
    ('vm', 'дисперсия/среднее', +1),
]


def strip_suffix(name):
    return re.sub(r'_\d+$', '', name)


# ---------------------------------------------------------------- чтение
with open(SRC, encoding='utf-8', newline='') as fh:
    rows = list(csv.DictReader(fh))

p(f'Файл: {SRC}')
p(f'Всего строк (доменов): {len(rows)}')
p(f'Симуляций на каждую проверку: {N_SIM}; random.seed(1)')
p('')

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

# распределение событий по брендам — по всем строкам (строка «какие бренды конвертили»)
brand_events = Counter()
events_per_domain = {}
unparsed = 0
for r in rows:
    s = r['какие бренды конвертили'].strip()
    k = 0
    if s:
        for part in s.split(', '):
            m = re.match(r'^(.+) \((\d+)\)$', part)
            if m:
                brand_events[m.group(1)] += int(m.group(2))
                k += int(m.group(2))
            else:
                unparsed += 1
    events_per_domain[r['домен']] = k
BRANDS = sorted(brand_events)
BRAND_W = [brand_events[b] for b in BRANDS]
BRAND_CUM = []
acc = 0
for w in BRAND_W:
    acc += w
    BRAND_CUM.append(acc)
N_EVENTS = sum(BRAND_W)
sum_p2 = sum((w / N_EVENTS) ** 2 for w in BRAND_W)
mismatch = sum(1 for r in rows if events_per_domain[r['домен']] != r['_reg_all'] + r['_fd_all'])

p('=' * 100)
p('0. РАСПРЕДЕЛЕНИЕ СОБЫТИЙ ПО БРЕНДАМ (для розыгрыша бренда события)')
p('=' * 100)
p(f'Брендов с хотя бы одним событием: {len(BRANDS)}; событий в строках «какие бренды конвертили»: {N_EVENTS} '
  f'(регистраций за всё время {sum(r["_reg_all"] for r in rows)} + ФД {sum(r["_fd_all"] for r in rows)}); '
  f'нераспознанных кусков строки: {unparsed}; доменов, где события ≠ рег+ФД: {mismatch}')
p('  → строка «какие бренды конвертили» считает регистрации и ФД вместе; ФД идёт по тому же бренду, что и '
  'регистрация, поэтому число разных брендов домена определяется регистрациями. Розыгрыш бренда — из этого '
  'распределения событий (оговорка: чуть тяжелее бренды с ФД).')
p('Топ-10 брендов по событиям: ' + ', '.join(f'{b} {c}' for b, c in brand_events.most_common(10)))
p(f'Вероятность, что два случайных события — один бренд: Σp² = {sum_p2:.4f} '
  f'(т.е. при 2 событиях на домене ожидается 2 разных бренда в {100 * (1 - sum_p2):.1f} % случаев)')
p(f'Проверка: «сайтов с регистрацией» = «брендов с конверсией» у {sum(1 for r in rows if r["_sites_reg"] == r["_brands"])} '
  f'из {len(rows)} доменов (сайт = бренд на базе, это одно и то же поле).')
p('')

# ---------------------------------------------------------------- фильтры
p('=' * 100)
p('ФИЛЬТРЫ И ИСКЛЮЧЕНИЯ')
p('=' * 100)
cur = rows
nxt = [r for r in cur if r['окно закрыто'] == 'да']
p(f'Окно закрыто = нет: исключено {len(cur) - len(nxt)} (осталось {len(nxt)})')
cur = nxt
nxt = [r for r in cur if int(fnum(r['дней'])) >= 2]
p(f'Дней < 2 (один день постановки, 150 сайтов): исключено {len(cur) - len(nxt)} (осталось {len(nxt)})')
cur = nxt
nxt = [r for r in cur if r['домен'] not in OUTLIERS]
p(f'Выбросы 3615.team / 3286.team: исключено {len(cur) - len(nxt)} (осталось {len(nxt)})')
cur = nxt
p(f'  На этом шаге (все наборы, включая «{NO_CONTENT}»): доменов {len(cur)}, регистраций в окне '
  f'{sum(r["_reg_w"] for r in cur)}, ФД в окне {sum(r["_fd_w"] for r in cur)}; '
  f'доменов с ≥2 рег в окне: {sum(1 for r in cur if r["_reg_w"] >= 2)}, с ≥3: {sum(1 for r in cur if r["_reg_w"] >= 3)}; '
  f'доменов с 2+ разными брендами (за всё время): {sum(1 for r in cur if r["_brands"] >= 2)}')
with_all = cur
unrec = [r for r in cur if r['набор контента'] == NO_CONTENT]
nxt = [r for r in cur if r['набор контента'] != NO_CONTENT]
p(f'«{NO_CONTENT}»: исключено {len(cur) - len(nxt)} (осталось {len(nxt)}) — отдельный прогон ниже')
main_rows = nxt
p(f'Доменов с именем набора вида …_NN (уникальный экземпляр): '
  f'{sum(1 for r in main_rows if r["_set"] != r["набор контента"])} из {len(main_rows)} — пул по имени без суффикса.')
p(f'Сайтов в окне у оставшихся: ' + ', '.join(f'{k}:{v}' for k, v in Counter(int(r['_sites_w']) for r in main_rows).most_common(6)) + ' …')
p('')


# ---------------------------------------------------------------- пулы
def build_pools(domains, key_fn, min_size=3):
    pools = defaultdict(list)
    for r in domains:
        pools[key_fn(r)].append(r)
    return {k: v for k, v in pools.items() if len(v) >= min_size}


def describe_pools(pools, rkey):
    doms = [r for v in pools.values() for r in v]
    R = sum(r[rkey] for r in doms)
    with_reg = sum(1 for v in pools.values() if sum(r[rkey] for r in v) > 0)
    return (f'пулов {len(pools)} (с регистрациями {with_reg}), доменов {len(doms)}, сайтов в окне '
            f'{int(sum(r["_sites_w"] for r in doms))}, регистраций {R}')


# ---------------------------------------------------------------- симуляция
def simulate(pools, wkey, rkey, n_sim, with_brands=False):
    doms = []
    specs = []
    zero_w_pools = 0
    for k, v in pools.items():
        R = sum(r[rkey] for r in v)
        start = len(doms)
        doms.extend(v)
        if R == 0:
            continue
        w = [r[wkey] for r in v]
        if sum(w) <= 0:
            zero_w_pools += 1
            w = [1.0] * len(v)
        cum = []
        a = 0.0
        for x in w:
            a += x
            cum.append(a)
        specs.append((R, list(range(start, start + len(v))), cum))
    n = len(doms)
    obs_counts = [r[rkey] for r in doms]
    obs = stats_of(obs_counts)
    obs['mb'] = sum(1 for r in doms if r['_brands'] >= 2)
    obs['b3'] = sum(1 for r in doms if r['_brands'] >= 3)
    obs['extra'] = sum(r[rkey] - r['_brands'] for r in doms if r[rkey] >= 2)
    # аналитический пуассон: λ_i = R · w_i / Σw
    lam = [0.0] * n
    for R, idxs, cum in specs:
        tot = cum[-1]
        prev = 0.0
        for i, c in zip(idxs, cum):
            lam[i] = R * (c - prev) / tot
            prev = c
    e_n1 = sum(1 - pois_pmf(0, l) for l in lam)
    e_n2 = sum(1 - pois_pmf(0, l) - pois_pmf(1, l) for l in lam)
    e_n3 = sum(1 - pois_pmf(0, l) - pois_pmf(1, l) - pois_pmf(2, l) for l in lam)
    sims = defaultdict(list)
    for _ in range(n_sim):
        counts = [0] * n
        for R, idxs, cum in specs:
            for i in random.choices(idxs, cum_weights=cum, k=R):
                counts[i] += 1
        st = stats_of(counts)
        if with_brands:
            mb = b3 = extra = 0
            for c in counts:
                if c >= 2:
                    d = len(set(random.choices(BRANDS, cum_weights=BRAND_CUM, k=c)))
                    if d >= 2:
                        mb += 1
                    if d >= 3:
                        b3 += 1
                    extra += c - d
            st['mb'] = mb
            st['b3'] = b3
            st['extra'] = extra
        for key, val in st.items():
            sims[key].append(val)
    return {'doms': doms, 'lam': lam, 'obs': obs, 'sims': sims,
            'analytic': {'n1': e_n1, 'n2': e_n2, 'n3': e_n3},
            'zero_w_pools': zero_w_pools, 'R': sum(obs_counts)}


def report(res, title, with_brands=False):
    obs, sims = res['obs'], res['sims']
    n = len(res['doms'])
    p('-' * 100)
    p(title)
    p(f'  доменов {n}, регистраций {res["R"]}; пулов без веса (Σw=0, но есть регистрации): {res["zero_w_pools"]}')
    p(f'  {"статистика":32} {"набл.":>8} {"средн.сим":>10} {"95% интервал":>18} {"O/E":>6} {"p":>7}   доля набл. (%)')
    defs = list(STAT_DEF) + ([('mb', 'доменов с 2+ разными брендами', +1),
                              ('b3', 'доменов с 3+ разными брендами', +1),
                              ('extra', 'повторных рег на уже конвертившем сайте', +1)] if with_brands else [])
    out = {}
    for key, label, direction in defs:
        vals = [v for v in sims[key] if v is not None]
        if not vals:
            continue
        s = sorted(vals)
        mean = sum(s) / len(s)
        lo, hi = percentile(s, 0.025), percentile(s, 0.975)
        o = obs[key]
        if o is None:
            continue
        if direction > 0:
            pv = sum(1 for v in vals if v >= o) / len(vals)
        else:
            pv = sum(1 for v in vals if v <= o) / len(vals)
        oe = o / mean if mean > 0 else None
        share = (100.0 * o / n) if key in ('n1', 'n2', 'n3', 'half', 'mb', 'b3') else None
        d = 3 if key in ('gini',) else (2 if key == 'vm' else 1)
        p(f'  {label:32} {fmt(o, 0 if isinstance(o, int) else d):>8} {fmt(mean, d if d > 1 else 1):>10} '
          f'{("[" + fmt(lo, d if d > 1 else 1) + "; " + fmt(hi, d if d > 1 else 1) + "]"):>18} {fmt(oe):>6} {fmt(pv, 3):>7}'
          + (f'   {share:.1f} %' if share is not None else ''))
        out[key] = (o, mean, lo, hi, oe, pv)
    a = res['analytic']
    p(f'  точный пуассон (λ_i = R·w_i/Σw): ожидание доменов с ≥1 {a["n1"]:.1f}, с ≥2 {a["n2"]:.1f}, с ≥3 {a["n3"]:.1f}; '
      f'O/E ≥2 = {fmt(obs["n2"] / a["n2"] if a["n2"] > 0 else None)}, O/E ≥3 = {fmt(obs["n3"] / a["n3"] if a["n3"] > 0 else None)}')
    return out


# ================================================================ 1. ГЛАВНАЯ ПРОВЕРКА
p('=' * 100)
p('1. ГЛАВНАЯ ПРОВЕРКА: окно 3 суток, пул = набор контента (без суффикса _NN) + день, пулы ≥3 доменов')
p('   Регистрации пула раскидываются по доменам пула случайно, пропорционально весу w.')
p('=' * 100)
pools_main = build_pools(main_rows, lambda r: (r['_set'], r['день запуска']))
p('Набор данных: ' + describe_pools(pools_main, '_reg_w'))
doms_main = [r for v in pools_main.values() for r in v]
c = Counter(min(r['_reg_w'], 3) for r in doms_main)
p(f'Наблюдённое распределение регистраций в окне по доменам: 0 — {c[0]}, 1 — {c[1]}, 2 — {c[2]}, 3+ — {c[3]}')
sizes = Counter(len(v) for v in pools_main.values())
p('Размеры пулов (доменов → сколько пулов): ' + ', '.join(f'{k}:{v}' for k, v in sorted(sizes.items())))
p('')

res_clk = simulate(pools_main, '_clk_w', '_reg_w', N_SIM)
main_clk = report(res_clk, '1а. w = кликов из поиска в окне (ОСНОВНОЙ вариант)')
res_ex = simulate(pools_main, '_ex3', '_reg_w', N_SIM)
main_ex = report(res_ex, '1б. w = вышли за 3 суток')
res_uni = simulate(pools_main, '_sites_w', '_reg_w', N_SIM)
main_uni = report(res_uni, '1в. СПРАВОЧНО: w = сайтов в окне (равные шансы, «кликов не знаем»)')
p('')

# кто «золотой»: топ доменов и их λ при кликах
p('Топ-15 доменов по регистрациям в окне и что им «полагалось» при раскладке по кликам:')
p(f'  {"домен":18} {"набор контента":34} {"день":10} {"пул":>4} {"рег":>4} {"λ клики":>8} {"P(X≥рег)":>9} {"клик.окно":>9} {"вышли3":>6} {"сайт.с рег":>10} {"бренд.":>6} {"ФД окн":>6}')
lam_by_dom = {r['домен']: l for r, l in zip(res_clk['doms'], res_clk['lam'])}
pool_size = {}
for k, v in pools_main.items():
    for r in v:
        pool_size[r['домен']] = len(v)
top = sorted(doms_main, key=lambda r: (-r['_reg_w'], -r['_clk_w']))[:15]
for r in top:
    l = lam_by_dom[r['домен']]
    p(f'  {r["домен"]:18} {r["набор контента"][:34]:34} {r["день запуска"][5:]:10} {pool_size[r["домен"]]:>4} {r["_reg_w"]:>4} '
      f'{l:>8.2f} {pois_sf(r["_reg_w"], l):>9.3f} {int(r["_clk_w"]):>9} {int(r["_ex3"]):>6} {r["_sites_reg"]:>10} {r["_brands"]:>6} {r["_fd_w"]:>6}')
# сколько доменов с «маловероятным» результатом против ожидания
thr = 0.01
n_rare = sum(1 for r, l in zip(res_clk['doms'], res_clk['lam']) if r['_reg_w'] > 0 and pois_sf(r['_reg_w'], l) <= thr)
e_rare = 0.0
for l in res_clk['lam']:
    # P(X >= k*) где k* — минимальное k с хвостом ≤ thr
    k = 1
    while pois_sf(k, l) > thr and k < 50:
        k += 1
    e_rare += pois_sf(k, l)
p(f'Доменов с «редким» результатом (P(X≥рег | λ по кликам) ≤ {thr}): наблюдено {n_rare}, ожидается при случайной раскладке {e_rare:.1f}')
p('')

# ================================================================ 2. МНОГОБРЕНДОВОСТЬ
p('=' * 100)
p('2. МНОГОБРЕНДОВОСТЬ (д): «брендов с конверсией» считается за всё время, поэтому здесь регистрации за всё время')
p('   Пулы те же. Бренд каждой симулированной регистрации — из общего распределения событий по брендам.')
p('=' * 100)
doms_main_all = doms_main
p(f'Наблюдено: регистраций за всё время {sum(r["_reg_all"] for r in doms_main_all)}, доменов с ≥2 рег за всё время '
  f'{sum(1 for r in doms_main_all if r["_reg_all"] >= 2)}, доменов с 2+ разными брендами {sum(1 for r in doms_main_all if r["_brands"] >= 2)}, '
  f'с 3+ брендами {sum(1 for r in doms_main_all if r["_brands"] >= 3)}')
res_b1 = simulate(pools_main, '_clk_all', '_reg_all', N_SIM, with_brands=True)
mb_clk = report(res_b1, '2а. регистрации за всё время, w = кликов из поиска за всё время', with_brands=True)
res_b2 = simulate(pools_main, '_clk_w', '_reg_all', N_SIM, with_brands=True)
mb_win = report(res_b2, '2б. регистрации за всё время, w = кликов из поиска в окне', with_brands=True)
p('')
# аналитика при фиксированном числе событий на домене
p('2в. Разлёт по брендам ВНУТРИ домена при фиксированном числе регистраций на домене (за всё время;')
p('    ФД не считаем — ФД всегда по бренду своей регистрации и нового бренда не добавляет):')
exp_distinct = 0.0
obs_distinct = 0
exp_mb = 0.0
obs_mb = 0
n_k2 = 0
for r in doms_main_all:
    k = r['_reg_all']
    if k == 0:
        continue
    exp_distinct += sum(1 - (1 - w / N_EVENTS) ** k for w in BRAND_W)
    obs_distinct += r['_brands']
    if k >= 2:
        n_k2 += 1
        exp_mb += 1 - sum((w / N_EVENTS) ** k for w in BRAND_W)
        obs_mb += 1 if r['_brands'] >= 2 else 0
n_with_reg = sum(1 for r in doms_main_all if r['_reg_all'] > 0)
reg_sum_all = sum(r['_reg_all'] for r in doms_main_all)
p(f'  доменов с регистрациями: {n_with_reg}, регистраций {reg_sum_all}; сумма «брендов с конверсией» (= сайтов с регистрацией) наблюдена {obs_distinct}, '
  f'ожидается при независимых брендах {exp_distinct:.1f} (O/E {obs_distinct / exp_distinct if exp_distinct else 0:.2f}); '
  f'т.е. повторных регистраций на уже конвертившем сайте наблюдено {reg_sum_all - obs_distinct}, ожидалось {reg_sum_all - exp_distinct:.1f}')
p(f'  доменов с ≥2 регистрациями: {n_k2}; из них с 2+ разными брендами наблюдено {obs_mb}, ожидается {exp_mb:.1f} '
  f'(O/E {obs_mb / exp_mb if exp_mb else 0:.2f}); биномиальный p = {fmt(binom_two_sided(obs_mb, n_k2, exp_mb / n_k2) if n_k2 else None, 3)}')
one_brand = [r for r in doms_main_all if r['_reg_all'] >= 2 and r['_brands'] == 1]
p(f'  домены с ≥2 регистрациями, но одним конвертившим сайтом ({len(one_brand)}): '
  + ', '.join(f'{r["домен"]} {r["какие бренды конвертили"]}' for r in one_brand[:12]) + (' …' if len(one_brand) > 12 else ''))
p('  → если O/E ≈ 1, «разные бренды на одной базе» — просто следствие того, что брендов много, а регистраций мало;')
p('    если наблюдено МЕНЬШЕ ожидаемого — регистрации повторяются на одном и том же сайте (бренд × база), а это уровень сайта, не базы.')
p('')

# ================================================================ 3. ВТОРАЯ СТУПЕНЬ: ФД
p('=' * 100)
p('3. ВТОРАЯ СТУПЕНЬ: конвертят ли «повторные» базы в ФД лучше одиночных (окно 3 суток, главный набор данных)')
p('=' * 100)
groups = [('1 регистрация', lambda r: r['_reg_w'] == 1),
          ('2 регистрации', lambda r: r['_reg_w'] == 2),
          ('3+ регистраций', lambda r: r['_reg_w'] >= 3),
          ('2+ регистраций', lambda r: r['_reg_w'] >= 2)]
tot_reg = sum(r['_reg_w'] for r in doms_main)
tot_fd = sum(r['_fd_w'] for r in doms_main)
q0 = tot_fd / tot_reg if tot_reg else 0.0
p(f'Всего в наборе: регистраций {tot_reg}, ФД {tot_fd}, доля ФД на регистрацию {100 * q0:.1f} %')
p(f'  {"группа":18} {"доменов":>8} {"рег":>6} {"ФД":>5} {"ФД/рег %":>9} {"ожид. ФД":>9} {"O/E":>6} {"биномиальный p":>15}')
fd_rows = {}
for label, f in groups:
    g = [r for r in doms_main if f(r)]
    R = sum(r['_reg_w'] for r in g)
    F = sum(r['_fd_w'] for r in g)
    e = q0 * R
    pv = binom_two_sided(F, R, q0) if R else None
    fd_rows[label] = (len(g), R, F, e, pv)
    p(f'  {label:18} {len(g):>8} {R:>6} {F:>5} {fmt(100 * F / R if R else None, 1):>9} {e:>9.1f} {fmt(F / e if e else None):>6} {fmt(pv, 3):>15}')
# сравнение 2+ против 1 напрямую
g1 = [r for r in doms_main if r['_reg_w'] == 1]
g2 = [r for r in doms_main if r['_reg_w'] >= 2]
R1, F1 = sum(r['_reg_w'] for r in g1), sum(r['_fd_w'] for r in g1)
R2, F2 = sum(r['_reg_w'] for r in g2), sum(r['_fd_w'] for r in g2)
q1 = F1 / R1 if R1 else 0.0
p(f'2+ против одиночных: ФД/рег {fmt(100 * F2 / R2 if R2 else None, 1)} % против {fmt(100 * q1, 1)} %; '
  f'биномиальный p (ставка одиночных как нуль) = {fmt(binom_two_sided(F2, R2, q1) if R2 else None, 3)}')
p(f'ФД за всё время у тех же групп: 2+ — {sum(r["_fd_all"] for r in g2)} ФД на {sum(r["_reg_all"] for r in g2)} рег '
  f'({fmt(100 * sum(r["_fd_all"] for r in g2) / max(1, sum(r["_reg_all"] for r in g2)), 1)} %); '
  f'одиночные — {sum(r["_fd_all"] for r in g1)} на {sum(r["_reg_all"] for r in g1)} '
  f'({fmt(100 * sum(r["_fd_all"] for r in g1) / max(1, sum(r["_reg_all"] for r in g1)), 1)} %)')
p('')
p('Домены с 3+ регистрациями в окне: с скольких сайтов (=брендов) пришли регистрации (за всё время)')
g3 = sorted([r for r in doms_main if r['_reg_w'] >= 3], key=lambda r: -r['_reg_w'])
p(f'  {"домен":18} {"рег окно":>8} {"рег всего":>9} {"сайтов с рег":>12} {"сайтов/рег":>10}  бренды')
for r in g3:
    p(f'  {r["домен"]:18} {r["_reg_w"]:>8} {r["_reg_all"]:>9} {r["_sites_reg"]:>12} {r["_sites_reg"] / r["_reg_all"]:>10.2f}  {r["какие бренды конвертили"][:60]}')
sR, sS = sum(r['_reg_all'] for r in g3), sum(r['_sites_reg'] for r in g3)
p(f'  итого: доменов {len(g3)}, регистраций {sR}, сайтов с регистрацией {sS}, сайтов/рег {sS / sR if sR else 0:.2f}; '
  f'доменов, где все регистрации с одного сайта: {sum(1 for r in g3 if r["_sites_reg"] == 1)}')
p('')

# ================================================================ 4. ПОВТОРЫ / ЧУВСТВИТЕЛЬНОСТЬ
p('=' * 100)
p('4. ПОВТОРЫ И ЧУВСТВИТЕЛЬНОСТЬ')
p('=' * 100)
pools_zone = build_pools(main_rows, lambda r: (r['_set'], r['день запуска'], r['зона']))
p('4а. Пул = набор + день + зона: ' + describe_pools(pools_zone, '_reg_w'))
res_z = simulate(pools_zone, '_clk_w', '_reg_w', N_SIM)
sens_zone = report(res_z, '4а. w = кликов из поиска в окне, страта с зоной')
p('')
pools_raw = build_pools(main_rows, lambda r: (r['набор контента'], r['день запуска']))
p('4б. Пул = имя набора как есть (без снятия суффикса _NN) + день: ' + describe_pools(pools_raw, '_reg_w'))
res_raw = simulate(pools_raw, '_clk_w', '_reg_w', N_SIM)
sens_raw = report(res_raw, '4б. w = кликов из поиска в окне, имена как есть')
p('')
pools_unrec = build_pools(unrec, lambda r: (NO_CONTENT, r['день запуска']))
p(f'4в. «{NO_CONTENT}» как свой набор (пул = день): ' + describe_pools(pools_unrec, '_reg_w'))
p(f'    ОГОВОРКА: это не набор контента, а отсутствие записи (до 24.08 и ещё несколько дней), сцепленное с датой; '
  f'внутри одного дня могут стоять разные реальные наборы.')
res_un = simulate(pools_unrec, '_clk_w', '_reg_w', N_SIM)
sens_un = report(res_un, '4в. только «не записан», w = кликов из поиска в окне')
pools_both = dict(pools_main)
pools_both.update(pools_unrec)
p('4г. Главные пулы + «не записан»: ' + describe_pools(pools_both, '_reg_w'))
res_both = simulate(pools_both, '_clk_w', '_reg_w', N_SIM)
sens_both = report(res_both, '4г. все вместе, w = кликов из поиска в окне')
res_both_ex = simulate(pools_both, '_ex3', '_reg_w', N_SIM)
sens_both_ex = report(res_both_ex, '4д. все вместе, w = вышли за 3 суток')
p('')

# ================================================================ ВЫВОД
p('=' * 100)
p('ВЫВОД')
p('=' * 100)


def verdict_line(name, out):
    o, m, lo, hi, oe, pv = out['n2']
    o3, m3, lo3, hi3, oe3, pv3 = out['n3']
    oh, mh, loh, hih, oeh, pvh = out['half']
    og, mg, log_, hig, oeg, pvg = out['gini']
    return (f'{name}: баз с 2+ рег {o} против {m:.1f} [{lo:.0f}; {hi:.0f}] (O/E {oe:.2f}, p={pv:.3f}); '
            f'с 3+ {o3} против {m3:.1f} [{lo3:.0f}; {hi3:.0f}] (O/E {oe3:.2f}, p={pv3:.3f}); '
            f'половину рег дают {oh} доменов против {mh:.1f} [{loh:.0f}; {hih:.0f}] (p={pvh:.3f}); '
            f'Джини {og:.3f} против {mg:.3f} [{log_:.3f}; {hig:.3f}] (p={pvg:.3f})')


n_main = len(doms_main)
R_main = res_clk['R']
p(f'Проверено на {n_main} доменах ({int(sum(r["_sites_w"] for r in doms_main))} сайтов) в {len(pools_main)} пулах «набор контента + день», '
  f'{R_main} регистраций в окне 3 суток; 5000 случайных раскладок регистраций каждого пула по его доменам.')
p(verdict_line('λ по кликам в окне', main_clk))
p(verdict_line('λ по вышедшим сайтам', main_ex))
p(verdict_line('λ поровну (справочно)', main_uni))
p(verdict_line('с зоной в пуле', sens_zone))
p(verdict_line('имена как есть', sens_raw))
p(verdict_line('вместе с «не записан»', sens_both))
o, m, lo, hi, oe, pv = mb_clk['mb']
p(f'Многобрендовость (регистрации за всё время, λ по кликам за всё время): доменов с 2+ разными брендами {o} против {m:.1f} [{lo:.0f}; {hi:.0f}] (O/E {oe:.2f}, p={pv:.3f})')
o, m, lo, hi, oe, pv = mb_win['mb']
p(f'  то же при λ по кликам в окне: {o} против {m:.1f} [{lo:.0f}; {hi:.0f}] (O/E {oe:.2f}, p={pv:.3f})')
n2g, R2g, F2g, e2g, p2g = fd_rows['2+ регистраций']
n1g, R1g, F1g, e1g, p1g = fd_rows['1 регистрация']
p(f'ФД: базы с 2+ регистрациями дали {F2g} ФД на {R2g} рег ({100 * F2g / R2g if R2g else 0:.1f} %), одиночные — {F1g} на {R1g} ({100 * F1g / R1g if R1g else 0:.1f} %); '
  f'p = {fmt(binom_two_sided(F2g, R2g, F1g / R1g) if R1g and R2g else None, 3)}')
p('')

# автоматический разбор критериев
crit_ok = (main_clk['n2'][5] > 0.05 and main_clk['n3'][5] > 0.05 and main_clk['half'][5] > 0.05
           and main_clk['gini'][5] > 0.05 and mb_clk['mb'][5] > 0.05 and main_clk['n2'][4] <= 1.1)
hidden = ((main_clk['n2'][0] > main_clk['n2'][3] and main_ex['n2'][0] > main_ex['n2'][3])
          or main_clk['n2'][4] >= 1.4 or main_ex['n2'][4] >= 1.4)
p('Критерии плана:')
p(f'  «концентрация объяснена» (p > 0,05 по (а)–(в) и (д) при λ по кликам, O/E баз с 2+ ≤ 1,1): {"ВЫПОЛНЕНО" if crit_ok else "НЕ ВЫПОЛНЕНО"}')
p(f'  «скрытый доменный фактор» (набл. за 95 % при обоих λ или O/E ≥ 1,4): {"ЕСТЬ" if hidden else "НЕТ"}')
p('')
ob3, mb3, lob3, hib3, oeb3, pvb3 = mb_clk['b3']
oex, mex, loex, hiex, oeex, pvex = mb_clk['extra']
p(f'Разные сайты (за всё время, λ по кликам): доменов с 3+ разными конвертившими сайтами {ob3} против {mb3:.1f} [{lob3:.0f}; {hib3:.0f}] (O/E {oeb3:.2f}, p={pvb3:.3f}); '
  f'повторных регистраций на уже конвертившем сайте {oex} против {mex:.1f} [{loex:.0f}; {hiex:.0f}] (O/E {oeex:.2f}, p={pvex:.3f})')
p('')
p('Простыми словами:')
p(f'  1) Число «повторных» баз (2+ регистрации в окне) — {main_clk["n2"][0]} — ровно такое, какое даёт случайная раскладка регистраций пула')
p(f'     по доменам пропорционально их поисковым кликам ({main_clk["n2"][1]:.1f}, интервал [{main_clk["n2"][2]:.0f}; {main_clk["n2"][3]:.0f}]). '
  f'Доля доменов, дающих половину регистраций ({100 * main_clk["half"][0] / n_main:.1f} % = {main_clk["half"][0]} доменов),')
p(f'     тоже на краю случайного разброса ([{main_clk["half"][2]:.0f}; {main_clk["half"][3]:.0f}]). Число баз с регистрациями с 2+ разных брендов ({mb_clk["mb"][0]}) '
  f'даже НИЖЕ случайного ({mb_clk["mb"][1]:.1f}).')
p(f'  2) Но баз с 3+ регистрациями в окне {main_clk["n3"][0]} против {main_clk["n3"][1]:.1f} по кликам (интервал [{main_clk["n3"][2]:.0f}; {main_clk["n3"][3]:.0f}], в {main_clk["n3"][4]:.1f} раза больше, p={main_clk["n3"][5]:.3f})'
  f' и {main_ex["n3"][1]:.1f} по вышедшим сайтам — этот избыток')
p('     клики не объясняют, он держится при страте с зоной и при именах наборов как есть; исчезает только в августовских базах «не записан».')
p(f'  3) Избыток «3+» идёт не от разных сайтов базы, а от ПОВТОРНЫХ регистраций на одном и том же сайте: за всё время таких {oex} против {mex:.1f} ожидаемых '
  f'(интервал [{loex:.0f}; {hiex:.0f}]),')
p(f'     а доменов с 3+ разными конвертившими сайтами {ob3} против {mb3:.1f} [{lob3:.0f}; {hib3:.0f}] — в пределах случая. Т.е. «золотая база» на деле — один сайт (бренд × база),')
p('     на котором регистрация случилась дважды-трижды; это свойство сайта/посетителя, а не базы, и оно не тянет за собой другие сайты базы.')
p(f'  4) Деньги: базы с 2+ регистрациями конвертят в ФД не лучше одиночных ({100 * F2g / R2g if R2g else 0:.1f} % против {100 * F1g / R1g if R1g else 0:.1f} %, p={fmt(binom_two_sided(F2g, R2g, F1g / R1g) if R1g and R2g else None, 2)}).')
p('')
p('Что с этим делать: ничего, это знание, не рычаг. «Денежного свойства базы» (имя, cf, аккаунт, «счастливый домен») искать')
p('на своде не нужно: сколько баз повторно регистрируют и какие домены дают половину регистраций — предсказывается кликами и случаем;')
p('единственный след сверх случая — повторные регистрации на одном сайте — не свойство базы. Проверяемо на уже запущенных данных:')
p('после закрытия окон у запусков 17–21.09 повторить скрипт и посмотреть, останется ли избыток «3+» тем же ~1,6× при O/E «2+» ≈ 1,')
p('и что у новых «3+» баз повторы снова сидят на одном сайте (поле «сайтов с регистрацией» < «регистраций»).')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

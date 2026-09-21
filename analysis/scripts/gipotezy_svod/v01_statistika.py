#!/usr/bin/env python3
"""
Скептик, угол «статистика» для гипотезы №1 (паттерн имени домена).

Проверяем результат h01_domain_name_pattern.py:
  1. Суммы или средние по доменам? (воспроизводим O/E из сумм и показываем, что дали бы средние долей).
  2. Перебор срезов: сколько p-величин напечатано; глобальный min-p-перестановочный тест по всему
     набору срезов основного блока (16 ячеек + 5 контрастов) и по двум объявленным контрастам.
  3. Статистика теста: p для casino_infix по |O−E| (как в h01) против p по |log(O/E)|.
  4. Регистраций в группах и по зонам: где меньше 20.
  5. Топ-1/2/3 доменов по регистрациям в КАЖДОЙ группе: убрать и пересчитать (два способа:
     из сумм группы; из набора с пересчётом пулов и перестановочного p).
  6. Альтернативные исходы: «сайтов с регистрацией», домен с >= 1 регистрацией, регистрации с потолком 2.
  7. Leave-one-pool-out для casino_infix: разброс O/E, вклад пулов в O−E.
  8. Устойчивость к seed.
Только стандартная библиотека. Использует функции h01 (фильтр, пулы, перестановочный движок).
"""

import bisect
import math
import os
import random
import sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import h01_domain_name_pattern as h  # noqa: E402

ANALYSIS = os.path.dirname(os.path.dirname(HERE))
OUT_PATH = os.path.join(ANALYSIS, 'export', 'gipotezy_svod', 'v01_statistika.txt')
N_PERM = 10000
PATTERNS = h.PATTERNS

_lines = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    _lines.append(s)


def oe(o, e):
    return f'{o / e:.2f}' if e > 0 else '—'


# ---------------------------------------------------------------------------
# загрузка тем же фильтром, что и в h01 (печать фильтра подавлена)
# ---------------------------------------------------------------------------
rows = h.load()
h.P = lambda *a: None  # глушим печать h01
kept = h.apply_filter(rows)
h.P = h.P  # (не восстанавливаем — h01 печатать не нужно)

# дописываем поля для альтернативных исходов
by_domain = {r['домен']: r for r in rows}
for d in kept:
    r = by_domain[d['домен']]
    d['сайтов_с_рег'] = h.toi(r['сайтов с регистрацией'])
    d['рег_бин'] = 1 if d['рег'] > 0 else 0
    d['рег_cap2'] = min(d['рег'], 2)


def build_items(kept_list):
    pools_all = h.build_pools(kept_list)
    multi = {k: v for k, v in pools_all.items() if len(set(d['паттерн'] for d in v)) >= 2}
    items = [d for v in multi.values() for d in v]
    h.add_expectations(h.build_pools(items))
    # ожидания для альтернативных исходов (ставка пула на сайт × сайтов)
    for k, ds in h.build_pools(items).items():
        S = sum(d['сайтов'] for d in ds)
        for fld in ('сайтов_с_рег', 'рег_бин', 'рег_cap2'):
            T = sum(d[fld] for d in ds)
            for d in ds:
                d['E_' + fld] = T / S * d['сайтов'] if S else 0.0
    return items, multi


items, multi = build_items(kept)
P('=' * 100)
P('СКЕПТИК, угол «статистика»: гипотеза №1 (паттерн имени домена)')
P('=' * 100)
P(f'После фильтра h01: {len(kept)} доменов; пулов с >= 2 паттернами: {len(multi)}; доменов в них: {len(items)}; '
  f'регистраций в окне: {sum(d["рег"] for d in items)}; сайтов с регистрацией: {sum(d["сайтов_с_рег"] for d in items)}; '
  f'доменов с >= 1 рег: {sum(d["рег_бин"] for d in items)}')

# ---------------------------------------------------------------------------
# 1. Суммы, а не средние
# ---------------------------------------------------------------------------
P()
P('--- 1. Суммы или средние по доменам? ---')
P('h01 считает O = Σ регистраций, E = Σ (ставка пула × сайтов) — это суммы, не средние долей. Воспроизводим и показываем разницу:')
P(f'{"паттерн":<14} {"доменов":>7} {"рег":>5} {"E_сайт":>7} {"O/E (суммы)":>12} {"ср. по доменам рег/100 сайтов":>30} {"ср. по доменам O/E":>19}')
for g in PATTERNS:
    ds = [d for d in items if d['паттерн'] == g]
    O = sum(d['рег'] for d in ds); E = sum(d['E_рег_сайт'] for d in ds)
    mean_rate = sum(100 * d['рег'] / d['сайтов'] for d in ds) / len(ds)
    ratios = [d['рег'] / d['E_рег_сайт'] for d in ds if d['E_рег_сайт'] > 0]
    mean_ratio = sum(ratios) / len(ratios) if ratios else float('nan')
    P(f'{g:<14} {len(ds):>7} {O:>5} {E:>7.1f} {oe(O, E):>12} {mean_rate:>30.3f} {mean_ratio:>19.2f}')
P('(средние O/E по доменам — для справки: они и не должны использоваться; h01 их не использует)')

# ---------------------------------------------------------------------------
# 2. Перебор срезов: глобальный min-p
# ---------------------------------------------------------------------------
P()
P('--- 2. Перебор срезов ---')
txt = open(os.path.join(ANALYSIS, 'export', 'gipotezy_svod', 'h01_domain_name_pattern.txt'), encoding='utf-8').read()
import re
pvals = re.findall(r'p(?: \(двуст\.\))? = ([0-9.]+)', txt)
pv_f = [float(x.rstrip('.')) for x in pvals]
P(f'В выводе h01 напечатано p-величин: {len(pv_f)}; из них < 0,05: {sum(1 for x in pv_f if x < 0.05)} '
  f'({", ".join(f"{x:.3f}" for x in sorted(x for x in pv_f if x < 0.05))}); < 0,10: {sum(1 for x in pv_f if x < 0.10)}')
P(f'Ожидание при чистом нуле: ~5% ложных p < 0,05, то есть ~{0.05 * len(pv_f):.0f} из {len(pv_f)} (часть p повторяется в тексте вывода). Уникальные p < 0,05: 0,001/0,002 — сверхдисперсия, 0,022/0,009 — зона lol, 0,041 — casino_infix.')

groups, obs, perms = h.perm_engine(items, lambda d: d['паттерн'], lambda d: d['пул'], N_PERM, seed=1)

# ячейки: 4 группы × {выход, рег E_сайт, рег E_вышли, рег E_клик}; контрасты: A1, A2, A2_вышли, A2_клик, casino_* рег
cells = []
for g in groups:
    cells.append((f'{g} выход', [g], 'вышли3', 'E_выход'))
    cells.append((f'{g} рег E_сайт', [g], 'рег', 'E_рег_сайт'))
    cells.append((f'{g} рег E_вышли', [g], 'рег', 'E_рег_вышли'))
    cells.append((f'{g} рег E_клик', [g], 'рег', 'E_рег_клик'))
contrasts = [
    ('A1 casino_* выход', ['casino_prefix', 'casino_infix'], 'вышли3', 'E_выход'),
    ('A2 casino_infix рег E_сайт', ['casino_infix'], 'рег', 'E_рег_сайт'),
    ('casino_infix рег E_вышли', ['casino_infix'], 'рег', 'E_рег_вышли'),
    ('casino_infix рег E_клик', ['casino_infix'], 'рег', 'E_рег_клик'),
    ('casino_* рег E_сайт', ['casino_prefix', 'casino_infix'], 'рег', 'E_рег_сайт'),
]


def stat(s, gs, o_f, e_f):
    return sum(s[g][o_f] for g in gs) - sum(s[g][e_f] for g in gs)


def per_cell_p(cell_list):
    """Для каждой ячейки: наблюдённое двустороннее p и p каждой перестановки (по |O−E|)."""
    res = {}
    for name, gs, o_f, e_f in cell_list:
        o_stat = abs(stat(obs, gs, o_f, e_f))
        vals = [abs(stat(p, gs, o_f, e_f)) for p in perms]
        srt = sorted(vals)
        n = len(vals)

        def pv(x):
            return (n - bisect.bisect_left(srt, x) + 1) / (n + 1)
        res[name] = (pv(o_stat), [pv(v) for v in vals])
    return res


def minp_adjust(cell_list, target, title):
    res = per_cell_p(cell_list)
    n = len(perms)
    obs_min = min(v[0] for v in res.values())
    perm_min = [min(res[k][1][j] for k in res) for j in range(n)]
    p_target = res[target][0]
    adj_target = (sum(1 for m in perm_min if m <= p_target) + 1) / (n + 1)
    adj_min = (sum(1 for m in perm_min if m <= obs_min) + 1) / (n + 1)
    P(f'  {title}: срезов {len(cell_list)}; сырое p «{target}» = {p_target:.3f}; '
      f'скорректированное (min-p по всему набору) = {adj_target:.3f}; самый малый сырой p в наборе = {obs_min:.3f} → скорр. {adj_min:.3f}')
    return adj_target


P('Глобальный перестановочный тест на весь набор срезов (min-p: как часто при нуле самый малый p среди срезов <= наблюдённого):')
adj_2 = minp_adjust(contrasts[:2], 'A2 casino_infix рег E_сайт', 'два объявленных контраста A1+A2')
adj_5 = minp_adjust(contrasts, 'A2 casino_infix рег E_сайт', 'пять напечатанных контрастов')
adj_reg4 = minp_adjust([c for c in cells if 'рег E_сайт' in c[0]], 'casino_infix рег E_сайт', '4 группы по регистрациям при E_сайт')
adj_reg12 = minp_adjust([c for c in cells if 'рег' in c[0]], 'casino_infix рег E_сайт', '4 группы × 3 ожидания по регистрациям (12 ячеек)')
adj_all = minp_adjust(cells + contrasts, 'A2 casino_infix рег E_сайт', 'все 16 ячеек + 5 контрастов основного блока')
P(f'Бонферрони по двум объявленным контрастам: 0,041 × 2 = {0.041 * 2:.3f}.')

# ---------------------------------------------------------------------------
# 3. Статистика теста: |O−E| против |log(O/E)|
# ---------------------------------------------------------------------------
P()
P('--- 3. p зависит от выбора статистики ---')
o_obs = obs['casino_infix']['рег']; e_obs = obs['casino_infix']['E_рег_сайт']
lr_obs = abs(math.log(o_obs / e_obs))
ratios = [p['casino_infix']['рег'] / p['casino_infix']['E_рег_сайт'] for p in perms if p['casino_infix']['E_рег_сайт'] > 0 and p['casino_infix']['рег'] > 0]
n_zero = sum(1 for p in perms if p['casino_infix']['рег'] == 0)
p_ratio = (sum(1 for r in ratios if abs(math.log(r)) >= lr_obs) + n_zero + 1) / (len(perms) + 1)
p_ratio_hi = (sum(1 for r in ratios if r >= o_obs / e_obs) + 1) / (len(perms) + 1)
diffs = [p['casino_infix']['рег'] - p['casino_infix']['E_рег_сайт'] for p in perms]
p_diff = (sum(1 for v in diffs if abs(v) >= abs(o_obs - e_obs)) + 1) / (len(perms) + 1)
srt_r = sorted(p['casino_infix']['рег'] / p['casino_infix']['E_рег_сайт'] for p in perms if p['casino_infix']['E_рег_сайт'] > 0)
P(f'casino_infix: O = {o_obs:.0f}, E = {e_obs:.1f}, O/E = {o_obs / e_obs:.2f}.')
P(f'  p по |O−E| (как в h01) = {p_diff:.3f}; p по |log(O/E)| (двуст.) = {p_ratio:.3f}; односторонний p по O/E >= 1,56 = {p_ratio_hi:.3f}')
P(f'  коридор O/E при нуле (2,5–97,5%) = {srt_r[int(0.025 * len(srt_r))]:.2f}–{srt_r[int(0.975 * len(srt_r))]:.2f} — наблюдённое 1,56 внутри коридора, '
  f'который сам h01 напечатал. Значимость держится на выборе статистики (разность вместо отношения).')
for seed in (2, 3):
    _, _, pp = h.perm_engine(items, lambda d: d['паттерн'], lambda d: d['пул'], 5000, seed=seed)
    dd = [p['casino_infix']['рег'] - p['casino_infix']['E_рег_сайт'] for p in pp]
    P(f'  seed {seed} (5000 перестановок): p по |O−E| = {(sum(1 for v in dd if abs(v) >= abs(o_obs - e_obs)) + 1) / (len(pp) + 1):.3f}')

# ---------------------------------------------------------------------------
# 4. Регистраций в группах
# ---------------------------------------------------------------------------
P()
P('--- 4. Регистраций в группах (порог доказательности 20) ---')
for g in PATTERNS:
    ds = [d for d in items if d['паттерн'] == g]
    P(f'  {g:<14} доменов {len(ds):>3}, регистраций {sum(d["рег"] for d in ds):>3}, доменов с рег {sum(d["рег_бин"] for d in ds):>3}, '
      f'сайтов с рег {sum(d["сайтов_с_рег"] for d in ds):>3}, ФД {sum(d["фд"] for d in ds):>2}'
      + ('   <-- меньше 20 регистраций' if sum(d['рег'] for d in ds) < 20 else ''))
for z in ('team', 'lol', 'casino'):
    ds = [d for d in items if d['паттерн'] == 'casino_infix' and d['зона'] == z]
    P(f'  casino_infix в зоне {z}: доменов {len(ds)}, регистраций {sum(d["рег"] for d in ds)} — '
      + ('меньше 20, «один знак в team и lol» держится на ' + str(sum(d["рег"] for d in ds)) + ' регистрациях' if sum(d['рег'] for d in ds) < 20 else 'достаточно'))

# ---------------------------------------------------------------------------
# 5. Топ-1/2/3 доменов по регистрациям в каждой группе
# ---------------------------------------------------------------------------
P()
P('--- 5. Убираем топ-1/2/3 домена по регистрациям в КАЖДОЙ группе ---')
P('Способ А: из сумм группы (O и E домена), ставки пулов не пересчитываются:')
for k in (1, 2, 3):
    parts = []
    for g in PATTERNS:
        ds = sorted([d for d in items if d['паттерн'] == g], key=lambda d: -d['рег'])
        rest = ds[k:]
        O = sum(d['рег'] for d in rest); E = sum(d['E_рег_сайт'] for d in rest)
        parts.append(f'{g} {oe(O, E)} ({O}/{E:.1f})')
    P(f'  без топ-{k}: ' + '; '.join(parts))
P('Способ Б: домены удаляются из набора, пулы/ставки/ожидания и перестановочный p пересчитываются:')
for k in (1, 2, 3):
    drop = set()
    for g in PATTERNS:
        ds = sorted([d for d in items if d['паттерн'] == g], key=lambda d: (-d['рег'], d['домен']))
        drop.update(d['домен'] for d in ds[:k])
    kept2 = [dict(d) for d in kept if d['домен'] not in drop]
    items2, multi2 = build_items(kept2)
    g2, obs2, perms2 = h.perm_engine(items2, lambda d: d['паттерн'], lambda d: d['пул'], 5000, seed=1)
    parts = []
    for g in PATTERNS:
        parts.append(f'{g} {oe(obs2[g]["рег"], obs2[g]["E_рег_сайт"])} ({obs2[g]["рег"]:.0f}/{obs2[g]["E_рег_сайт"]:.1f})')
    d_obs = obs2['casino_infix']['рег'] - obs2['casino_infix']['E_рег_сайт']
    dd = [p['casino_infix']['рег'] - p['casino_infix']['E_рег_сайт'] for p in perms2]
    pv = (sum(1 for v in dd if abs(v) >= abs(d_obs)) + 1) / (len(dd) + 1)
    chi_o = h.chi_stat(obs2, g2, 'рег', 'E_рег_сайт'); chi_p = [h.chi_stat(p, g2, 'рег', 'E_рег_сайт') for p in perms2]
    p4 = h.pval_ge(chi_o, chi_p)
    P(f'  без топ-{k} в каждой группе (удалено {len(drop)} доменов, осталось {len(items2)} доменов, {sum(d["рег"] for d in items2)} рег): '
      + '; '.join(parts) + f';  A2 p = {pv:.3f}; 4 группы p = {p4:.3f}')
# те же топ-домены — что это за домены
P('  Топ-3 домена по регистрациям в casino_infix: ' + ', '.join(
    f'{d["домен"]} ({d["рег"]} рег, {d["сайтов_с_рег"]} сайтов с рег, выход {d["вышли3"]}/{d["сайтов"]}, кликов {d["клик"]})'
    for d in sorted([d for d in items if d['паттерн'] == 'casino_infix'], key=lambda d: -d['рег'])[:3]))

# ---------------------------------------------------------------------------
# 6. Альтернативные исходы
# ---------------------------------------------------------------------------
P()
P('--- 6. Альтернативные исходы (та же страта, те же пулы, ставка пула на сайт × сайтов) ---')
FIELDS2 = ['сайтов', 'сайтов_с_рег', 'E_сайтов_с_рег', 'рег_бин', 'E_рег_бин', 'рег_cap2', 'E_рег_cap2', 'рег', 'E_рег_сайт']
g3, obs3, perms3 = h.perm_engine(items, lambda d: d['паттерн'], lambda d: d['пул'], N_PERM, seed=1, fields=FIELDS2)
for title, o_f, e_f in [('регистраций (как в h01)', 'рег', 'E_рег_сайт'),
                        ('сайтов с регистрацией', 'сайтов_с_рег', 'E_сайтов_с_рег'),
                        ('доменов с >= 1 регистрацией', 'рег_бин', 'E_рег_бин'),
                        ('регистраций с потолком 2 на домен', 'рег_cap2', 'E_рег_cap2')]:
    parts = []
    for g in PATTERNS:
        parts.append(f'{g} {oe(obs3[g][o_f], obs3[g][e_f])} ({obs3[g][o_f]:.0f}/{obs3[g][e_f]:.1f})')
    d_obs = obs3['casino_infix'][o_f] - obs3['casino_infix'][e_f]
    dd = [p['casino_infix'][o_f] - p['casino_infix'][e_f] for p in perms3]
    pv = (sum(1 for v in dd if abs(v) >= abs(d_obs)) + 1) / (len(dd) + 1)
    chi_o = h.chi_stat(obs3, g3, o_f, e_f); chi_p = [h.chi_stat(p, g3, o_f, e_f) for p in perms3]
    p4 = h.pval_ge(chi_o, chi_p)
    P(f'  {title:<36}: ' + '; '.join(parts) + f';  A2 p = {pv:.3f}; 4 группы p = {p4:.3f}')

# ---------------------------------------------------------------------------
# 7. Leave-one-pool-out и вклад пулов
# ---------------------------------------------------------------------------
P()
P('--- 7. На каких пулах держится casino_infix (O−E по пулам, E_сайт) ---')
contrib = []
for k, ds in h.build_pools(items).items():
    ci = [d for d in ds if d['паттерн'] == 'casino_infix']
    if not ci:
        continue
    O = sum(d['рег'] for d in ci); E = sum(d['E_рег_сайт'] for d in ci)
    contrib.append((O - E, k, len(ci), len(ds), O, E, sum(d['рег'] for d in ds)))
contrib.sort(reverse=True)
P(f'Пулов с casino_infix: {len(contrib)}; Σ(O−E) = {sum(c[0] for c in contrib):+.1f}. Пулы с наибольшим вкладом:')
for c in contrib[:6]:
    P(f'  {c[0]:+5.1f}  набор «{c[1][0]}», день {c[1][1]}: casino_infix {c[2]} из {c[3]} доменов, O = {c[4]}, E = {c[5]:.1f}, регистраций в пуле {c[6]}')
P(f'  вклад двух верхних пулов: {contrib[0][0] + contrib[1][0]:+.1f} из {sum(c[0] for c in contrib):+.1f}; '
  f'пулов с O−E > 0: {sum(1 for c in contrib if c[0] > 0)}, < 0: {sum(1 for c in contrib if c[0] < 0)}, = 0 (нет рег в пуле): {sum(1 for c in contrib if c[0] == 0)}')
# leave-one-pool-out
loo = []
tot_o = sum(c[4] for c in contrib); tot_e = sum(c[5] for c in contrib)
for c in contrib:
    o = tot_o - c[4]; e = tot_e - c[5]
    loo.append((o / e if e else float('nan'), c[1]))
loo.sort()
P(f'  leave-one-pool-out O/E casino_infix: от {loo[0][0]:.2f} (без «{loo[0][1][0]}» {loo[0][1][1]}) до {loo[-1][0]:.2f}; '
  f'пулов, без которых O/E < 1,25: {sum(1 for x in loo if x[0] < 1.25)} из {len(loo)}')
# знаковый тест по пулам: в скольких пулах с регистрациями casino_infix выше ставки пула
win = lose = 0
for c in contrib:
    if c[6] == 0:
        continue
    if c[0] > 0: win += 1
    elif c[0] < 0: lose += 1
P(f'  знаковый тест по пулам с регистрациями: casino_infix выше ставки пула в {win} пулах, ниже в {lose}; p = {h.binom_two_sided(win, win + lose):.3f}')

# ---------------------------------------------------------------------------
# 8. Выход: устойчивость главного «нулевого» результата
# ---------------------------------------------------------------------------
P()
P('--- 8. Выход (главный результат «нет эффекта»): объёмы и разброс по пулам ---')
for g in PATTERNS:
    P(f'  {g:<14} доменов {obs[g]["_n"] if "_n" in obs[g] else sum(1 for d in items if d["паттерн"] == g):>3}, вышедших сайтов {obs[g]["вышли3"]:.0f}, E {obs[g]["E_выход"]:.0f}, O/E {oe(obs[g]["вышли3"], obs[g]["E_выход"])}')
cas_loo = []
pools_i = h.build_pools(items)
tot_o = sum(d['вышли3'] for d in items if d['паттерн'].startswith('casino'))
tot_e = sum(d['E_выход'] for d in items if d['паттерн'].startswith('casino'))
for k, ds in pools_i.items():
    o = sum(d['вышли3'] for d in ds if d['паттерн'].startswith('casino')); e = sum(d['E_выход'] for d in ds if d['паттерн'].startswith('casino'))
    if e > 0:
        cas_loo.append(((tot_o - o) / (tot_e - e), k))
cas_loo.sort()
P(f'  casino_* по выходу: O/E {tot_o / tot_e:.2f}; leave-one-pool-out от {cas_loo[0][0]:.2f} до {cas_loo[-1][0]:.2f} — устойчиво (десятки тысяч сайтов).')

# ---------------------------------------------------------------------------
# ИТОГ
# ---------------------------------------------------------------------------
P()
P('=' * 100)
P('ИТОГ СКЕПТИКА')
P('=' * 100)
P(f'1. Суммы, не средние — верно. 2. Срезов много: {len(pv_f)} p-величин; с поправкой min-p по всему набору срезов основного блока p(casino_infix) = {adj_all:.2f}, '
  f'по 12 ячейкам регистраций {adj_reg12:.2f}, даже по двум объявленным контрастам {adj_2:.2f}.')
P(f'3. По |log(O/E)| p = {p_ratio:.3f}, наблюдённое 1,56 внутри собственного коридора нуля h01 (0,52–1,64).')
P('4. casino_prefix 13 рег, casino_infix по зонам 8 и 7 рег — ниже порога 20; «один знак в team и lol» не доказательство.')
P('5–7. См. выше: без топ-2/3 доменов, по сайтам с регистрацией, по доменам с >= 1 рег и с потолком 2 сигнал casino_infix уходит к ~1,0.')

with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT_PATH}]')

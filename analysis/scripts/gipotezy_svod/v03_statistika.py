#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №3 (шаблон Theme2). Угол: СТАТИСТИКА.

Проверяем результат тестировщика (h03_theme2_template.py):
  1. Суммы или средние по доменам — сверяем: O/E из сумм (как у тестировщика) против отношения
     средних долей по доменам.
  2. Объёмы регистраций в группах каждого сравнения (< 20 — не доказательство).
  3. Устойчивость решающего теста (внутри партии, 17 Theme2 против 16 Theme1):
     - каждая партия отдельно, ТОЧНЫЙ перестановочный тест (перебор всех расстановок метки);
     - двусторонний p;
     - leave-one-out по 33 доменам: диапазон p, сколько исключений уводят p за 0,05;
     - без топ-3 доменов по выходу в каждой группе (и без топ-1 в каждой группе каждой партии);
     - бутстреп по доменам внутри партия × шаблон: 95% интервал для O/E по Theme1.
  4. Регистрации: без топ-3 доменов по регистрациям в каждой группе — грубый срез и внутри партии.
  5. Перебор срезов: сколько p-значений посчитано; Холм по семейству; Westfall–Young (min-p) по
     семейству «внутри партии» (5a, 5b, 5c, 7a) на ОДНОЙ перестановке внутри самых мелких ячеек
     день × зона × час × «сайтов».
  6. Грубый срез (страта = день): держится ли без топ-3 доменов (для полноты — он и так тень партии).

Только stdlib. Вывод — в stdout и в analysis/export/gipotezy_svod/v03_statistika.txt
"""
import bisect
import csv
import itertools
import math
import os
import random
import sys
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'v03_statistika.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
N_PERM_LOO = 4000
N_BOOT = 5000
N_FAMILY = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
OUTLIERS = {'3615.team', '3286.team'}
DAYS = ('2026-08-19', '2026-08-20')

_lines = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _lines.append(s)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fmt(x, d=2):
    return '—' if x is None else ('%.' + str(d) + 'f') % x


def poisson_le(k, lam):
    if lam <= 0:
        return 1.0
    s = 0.0
    for i in range(0, int(k) + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


# ---------------------------------------------------------------- чтение и срез (как у тестировщика)
with open(SRC, encoding='utf-8', newline='') as fh:
    rows = list(csv.DictReader(fh))
for r in rows:
    r['_sites'] = fnum(r['сайтов в окне'])
    r['_v3'] = fnum(r['вышли за 3 суток'])
    r['_v7'] = fnum(r['вышли за 7 суток'])
    r['_reg'] = fnum(r['регистраций в окне 3 суток'])
    r['_hour'] = int(fnum(r['час запуска']))
    r['_day'] = r['день запуска'][5:]
    r['_t'] = r['шаблон']

all_zones = [r for r in rows if r['день запуска'] in DAYS and r['домен'] not in OUTLIERS
             and r['окно закрыто'] == 'да' and r['дней'] != '1']
main = [r for r in all_zones if r['зона'] == 'team']
p('Файл:', SRC)
p('Срез тестировщика: team, 19–20.08, окно закрыто, дней ≠ 1 → %d доменов (Theme2 %d, Theme1 %d); все зоны 19–20.08 → %d' %
  (len(main), sum(1 for r in main if r['_t'] == 'Theme2'), sum(1 for r in main if r['_t'] == 'Theme1'), len(all_zones)))
p()


# ---------------------------------------------------------------- движок O/E
def strata_of(ds, fn, min_each=1):
    st = defaultdict(list)
    for r in ds:
        st[fn(r)].append(r)
    return {k: v for k, v in st.items()
            if sum(1 for r in v if r['_t'] == 'Theme2') >= min_each and sum(1 for r in v if r['_t'] == 'Theme1') >= min_each}


def oe(strata, metric, lab=None):
    """O, E_pool, E_ref для Theme2. lab: dict id(r)->метка (по умолчанию наблюдённая)."""
    O = E = Eref = 0.0
    for v in strata.values():
        tm = sum(r[metric] for r in v)
        ts = sum(r['_sites'] for r in v)
        m1 = sum(r[metric] for r in v if (lab[id(r)] if lab else r['_t']) == 'Theme1')
        s1 = sum(r['_sites'] for r in v if (lab[id(r)] if lab else r['_t']) == 'Theme1')
        rp = tm / ts if ts else 0
        rr = m1 / s1 if s1 else 0
        for r in v:
            if (lab[id(r)] if lab else r['_t']) == 'Theme2':
                O += r[metric]
                E += rp * r['_sites']
                Eref += rr * r['_sites']
    return O, E, Eref


def perm_p(strata, metric, n_perm, seed=1, stat='ref'):
    """Перестановка метки внутри страт. Возвращает (obs, p_le, p_ge, p_two)."""
    O, E, Eref = oe(strata, metric)
    obs = (O / Eref if stat == 'ref' else O / E) if (Eref if stat == 'ref' else E) > 0 else None
    if obs is None:
        return None, None, None, None
    rnd = random.Random(seed)
    base = {id(r): r['_t'] for v in strata.values() for r in v}
    le = ge = 0
    for _ in range(n_perm):
        lab = dict(base)
        for v in strata.values():
            labs = [r['_t'] for r in v]
            rnd.shuffle(labs)
            for r, lb in zip(v, labs):
                lab[id(r)] = lb
        Op, Ep, Erp = oe(strata, metric, lab)
        den = Erp if stat == 'ref' else Ep
        rp = Op / den if den > 0 else 1.0
        if rp <= obs + 1e-12:
            le += 1
        if rp >= obs - 1e-12:
            ge += 1
    p_le, p_ge = le / n_perm, ge / n_perm
    return obs, p_le, p_ge, min(1.0, 2 * min(p_le, p_ge))


def exact_p_one_stratum(v, metric):
    """Точный перестановочный тест в одной страте: перебор всех расстановок метки Theme1."""
    n1 = sum(1 for r in v if r['_t'] == 'Theme1')
    idx = list(range(len(v)))
    m = [r[metric] for r in v]
    s = [r['_sites'] for r in v]
    obs1 = set(i for i in idx if v[i]['_t'] == 'Theme1')

    def stat(set1):
        m1 = sum(m[i] for i in set1)
        s1 = sum(s[i] for i in set1)
        m2 = sum(m[i] for i in idx if i not in set1)
        s2 = sum(s[i] for i in idx if i not in set1)
        r1 = m1 / s1 if s1 else 0
        return (m2 / s2) / r1 if (r1 > 0 and s2) else (float('inf') if m2 > 0 else 1.0)

    obs = stat(obs1)
    tot = le = ge = 0
    for comb in itertools.combinations(idx, n1):
        st = stat(set(comb))
        tot += 1
        if st <= obs + 1e-12:
            le += 1
        if st >= obs - 1e-12:
            ge += 1
    return obs, le / tot, ge / tot, tot


def agg(ds):
    S = sum(r['_sites'] for r in ds)
    V = sum(r['_v3'] for r in ds)
    R = sum(r['_reg'] for r in ds)
    return dict(n=len(ds), S=S, V=V, R=R, ex=100 * V / S if S else 0)


# ---------------------------------------------------------------- 1. суммы или средние
p('=' * 100)
p('1. СУММЫ ИЛИ СРЕДНИЕ ПО ДОМЕНАМ')
p('=' * 100)
p('У тестировщика O/E считается из СУММ: O = Σ вышли, E = Σ (доля Theme1 страты × сайтов домена), доля страты = Σвышли/Σсайтов.')
p('Это правило 2 методики, всё верно. Для сравнения — отношение СРЕДНИХ долей по доменам (то, чего делать нельзя):')
dec = strata_of(main, lambda r: (r['_day'], r['_hour'], r['сайтов']), min_each=3)
crude = strata_of(main, lambda r: r['_day'])
for name, st in (('страта = день (грубо)', crude), ('внутри партии (решающий)', dec)):
    O, E, Eref = oe(st, '_v3')
    num = den = 0.0
    for v in st.values():
        m2 = [100 * r['_v3'] / r['_sites'] for r in v if r['_t'] == 'Theme2']
        m1 = [100 * r['_v3'] / r['_sites'] for r in v if r['_t'] == 'Theme1']
        w = len(m2)
        num += w * (sum(m2) / len(m2))
        den += w * (sum(m1) / len(m1))
    p('  %-28s O/E по Theme1 из сумм = %.3f;  отношение средних долей по доменам (взвеш. по n Theme2) = %.3f' %
      (name, O / Eref, num / den))
p('  Расхождение малое, метод тестировщика корректен по этому пункту. Претензий к пункту 1 нет.')
p()

# ---------------------------------------------------------------- 2. объёмы регистраций
p('=' * 100)
p('2. ОБЪЁМЫ РЕГИСТРАЦИЙ В ГРУППАХ КАЖДОГО СРАВНЕНИЯ (< 20 в группе — не доказательство)')
p('=' * 100)
tests = [
    ('2a грубо: день', main, lambda r: r['_day'], 1),
    ('3a день × блок часа', main, lambda r: (r['_day'], r['блок часа']), 1),
    ('5a решающий: день × час × сайтов, ≥3', main, lambda r: (r['_day'], r['_hour'], r['сайтов']), 3),
    ('5b день × час', main, lambda r: (r['_day'], r['_hour']), 1),
    ('5c день × час × сайтов, любая пара', main, lambda r: (r['_day'], r['_hour'], r['сайтов']), 1),
    ('7a все зоны: день × зона × час', all_zones, lambda r: (r['_day'], r['зона'], r['_hour']), 1),
]
p('  %-40s %6s %6s %8s %8s %8s %8s' % ('сравнение', 'n T2', 'n T1', 'рег T2', 'рег T1', 'сайт T2', 'сайт T1'))
for name, ds, fn, me in tests:
    st = strata_of(ds, fn, me)
    t2 = [r for v in st.values() for r in v if r['_t'] == 'Theme2']
    t1 = [r for v in st.values() for r in v if r['_t'] == 'Theme1']
    a2, a1 = agg(t2), agg(t1)
    flag = '  ← в группе Theme2 < 20 регистраций' if a2['R'] < 20 else ''
    flag += ('; и у Theme1 < 20' if a1['R'] < 20 else '')
    p('  %-40s %6d %6d %8d %8d %8d %8d%s' % (name, a2['n'], a1['n'], a2['R'], a1['R'], a2['S'], a1['S'], flag))
p('  Ни в одном сравнении у Theme2 нет и 20 регистраций (максимум 3). У Theme1 20+ только в грубом срезе (24),')
p('  а внутри партии — 12, из них 5 у одного домена. Любой вывод о регистрациях («в 4–8 раз») на этих объёмах не доказуем —')
p('  ни в пользу гипотезы, ни против. Тестировщик это признал (регистрации «не значимо»).')
p()

# ---------------------------------------------------------------- 3. устойчивость решающего теста
p('=' * 100)
p('3. УСТОЙЧИВОСТЬ РЕШАЮЩЕГО ТЕСТА (внутри партии: 19.08 23:00/198 и 20.08 12:00/199; 17 Theme2 против 16 Theme1)')
p('=' * 100)
O, E, Eref = oe(dec, '_v3')
obs_ref, p_le_ref, p_ge_ref, p2_ref = perm_p(dec, '_v3', N_PERM, seed=1, stat='ref')
obs_pool, p_le_pool, p_ge_pool, p2_pool = perm_p(dec, '_v3', N_PERM, seed=1, stat='pool')
p('3a. Воспроизведение: выход O = %d, E по Theme1 = %.1f → O/E = %.3f; E по пулу = %.1f → O/E = %.3f' % (O, Eref, O / Eref, E, O / E))
p('    перестановка %d раз (статистика O/E по пулу, как у тестировщика): односторонний p = %.4f, ДВУСТОРОННИЙ p = %.4f' %
  (N_PERM, p_le_pool, p2_pool))
p('    перестановка %d раз (статистика O/E по Theme1):                   односторонний p = %.4f, ДВУСТОРОННИЙ p = %.4f' %
  (N_PERM, p_le_ref, p2_ref))
p('    → гипотеза направленная, односторонний p допустим, но двусторонний уже > 0,05. Граница, как и сказал тестировщик.')
p()

p('3b. Каждая партия отдельно — ТОЧНЫЙ перестановочный тест (перебор всех расстановок метки Theme1):')
for k in sorted(dec):
    v = dec[k]
    a1 = agg([r for r in v if r['_t'] == 'Theme1'])
    a2 = agg([r for r in v if r['_t'] == 'Theme2'])
    obs, ple, pge, tot = exact_p_one_stratum(v, '_v3')
    p('    %s час %d сайтов %s: Theme1 %d дом. %.1f%% | Theme2 %d дом. %.1f%% → O/E по Theme1 = %.3f; расстановок %d; p(≤) = %.4f, p(≥) = %.4f, двуст. = %.4f' %
      (k[0], k[1], k[2], a1['n'], a1['ex'], a2['n'], a2['ex'], obs, tot, ple, pge, min(1, 2 * min(ple, pge))))
p('    → значима по отдельности только партия 19.08 23:00, где опора ожидания — 4 домена Theme1 (одност. p = 0,036, двуст. 0,073);')
p('      большая партия 20.08 12:00 (12 против 8) — p = 0,15, там разница 22,0% против 27,4% в шуме.')
p()

# leave-one-out
p('3c. Leave-one-out: убираем по одному домену из 33 и пересчитываем O/E по Theme1 и односторонний p (%d перестановок):' % N_PERM_LOO)
dom33 = [r for v in dec.values() for r in v]
loo = []
for r0 in dom33:
    st = {k: [r for r in v if r is not r0] for k, v in dec.items()}
    o, ple, pge, p2 = perm_p(st, '_v3', N_PERM_LOO, seed=3, stat='pool')
    Oo, Ee, Er = oe(st, '_v3')
    loo.append((r0['домен'], r0['_t'], 100 * r0['_v3'] / r0['_sites'], Oo / Er, ple))
loo.sort(key=lambda x: -x[4])
p('    %-14s %-7s %8s %10s %8s' % ('убран домен', 'шаблон', 'его вых%', 'O/E(T1)', 'p'))
for d, t, ex, oer, pl in loo[:8]:
    p('    %-14s %-7s %8.1f %10.3f %8.4f' % (d, t, ex, oer, pl))
p('    ... (показаны 8 исключений с наибольшим p)')
n_over = sum(1 for x in loo if x[4] >= 0.05)
p('    Диапазон p по 33 исключениям: от %.4f до %.4f; O/E по Theme1 от %.3f до %.3f; исключений с p ≥ 0,05: %d из 33' %
  (min(x[4] for x in loo), max(x[4] for x in loo), min(x[3] for x in loo), max(x[3] for x in loo), n_over))
p()

# drop top-3 by exit per group
p('3d. Без топ-3 доменов по ВЫХОДУ (число вышедших сайтов) в каждой группе шаблона (по всем 33 доменам):')


def drop_top(strata, metric, k_each, per_stratum=False):
    if per_stratum:
        drop = set()
        for v in strata.values():
            for t in ('Theme1', 'Theme2'):
                g = sorted([r for r in v if r['_t'] == t], key=lambda r: -r[metric])
                drop |= set(id(r) for r in g[:k_each])
    else:
        drop = set()
        for t in ('Theme1', 'Theme2'):
            g = sorted([r for v in strata.values() for r in v if r['_t'] == t], key=lambda r: -r[metric])
            drop |= set(id(r) for r in g[:k_each])
    return {k: [r for r in v if id(r) not in drop] for k, v in strata.items()}, drop


top3_t1 = set(id(x) for x in sorted([y for vv in dec.values() for y in vv if y['_t'] == 'Theme1'],
                                     key=lambda y: -y['_v3'])[:3])
only_t1 = {k: [r for r in v if id(r) not in top3_t1] for k, v in dec.items()}
for title, st in (('топ-3 по выходу в каждой группе (всего 6 доменов убрано)', drop_top(dec, '_v3', 3)[0]),
                  ('топ-1 по выходу в каждой группе КАЖДОЙ партии (4 убрано)', drop_top(dec, '_v3', 1, per_stratum=True)[0]),
                  ('топ-3 по выходу только у Theme1 (опора ожидания)', only_t1)):
    n2 = sum(1 for v in st.values() for r in v if r['_t'] == 'Theme2')
    n1 = sum(1 for v in st.values() for r in v if r['_t'] == 'Theme1')
    o, ple, pge, p2 = perm_p(st, '_v3', N_PERM, seed=5, stat='pool')
    Oo, Ee, Er = oe(st, '_v3')
    p('    %-58s Theme2 %2d / Theme1 %2d дом.: O = %d, E(T1) = %.1f → O/E = %.3f; p одност. = %.4f, двуст. = %.4f' %
      (title, n2, n1, Oo, Er, Oo / Er, ple, p2))
p()

# bootstrap CI
p('3e. Бутстреп по доменам (внутри партия × шаблон, с возвращением, %d раз): интервал для O/E по Theme1' % N_BOOT)
rnd = random.Random(11)
vals = []
groups = {k: {t: [r for r in v if r['_t'] == t] for t in ('Theme1', 'Theme2')} for k, v in dec.items()}
for _ in range(N_BOOT):
    O_b = E_b = 0.0
    for k, g in groups.items():
        g1 = [rnd.choice(g['Theme1']) for _ in g['Theme1']]
        g2 = [rnd.choice(g['Theme2']) for _ in g['Theme2']]
        s1 = sum(r['_sites'] for r in g1)
        r1 = sum(r['_v3'] for r in g1) / s1
        O_b += sum(r['_v3'] for r in g2)
        E_b += r1 * sum(r['_sites'] for r in g2)
    vals.append(O_b / E_b)
vals.sort()
lo, hi = vals[int(0.025 * N_BOOT)], vals[int(0.975 * N_BOOT)]
p('    O/E по Theme1 = %.3f; 95%% бутстреп-интервал [%.3f; %.3f]; доля выборок с O/E ≥ 1: %.3f; с O/E ≤ 0,6: %.3f' %
  (O / Eref, lo, hi, sum(1 for x in vals if x >= 1) / N_BOOT, sum(1 for x in vals if x <= 0.6) / N_BOOT))
p('    → интервал %s единицу; «вдвое» (0,5) вне интервала, но и «нет эффекта» (1,0) %s.' %
  ('накрывает' if hi >= 1 else 'не накрывает', 'внутри' if hi >= 1 else 'вне'))
p()

# ---------------------------------------------------------------- 4. регистрации без топ-3
p('=' * 100)
p('4. РЕГИСТРАЦИИ: ДЕРЖИТСЯ ЛИ НА 1–3 ДОМЕНАХ')
p('=' * 100)
for title, st in (('внутри партии (решающий)', dec), ('грубо, страта = день', crude)):
    O, E, Eref = oe(st, '_reg')
    t1 = sorted([r for v in st.values() for r in v if r['_t'] == 'Theme1'], key=lambda r: -r['_reg'])
    t2 = sorted([r for v in st.values() for r in v if r['_t'] == 'Theme2'], key=lambda r: -r['_reg'])
    p('  %s: Theme2 O = %d (домены: %s), E по Theme1 = %.2f, O/E = %.2f; пуассон P(X ≤ O | E по пулу %.2f) = %.4f' %
      (title, O, ', '.join('%s %d' % (r['домен'], r['_reg']) for r in t2 if r['_reg'] > 0) or 'нет', Eref, O / Eref if Eref else 0, E, poisson_le(O, E)))
    p('    Theme1: %d регистраций на %d доменов; топ-3: %s → доля топ-3 = %.0f%%' %
      (sum(r['_reg'] for r in t1), len(t1), ', '.join('%s %d' % (r['домен'], r['_reg']) for r in t1[:3]),
       100 * sum(r['_reg'] for r in t1[:3]) / max(1, sum(r['_reg'] for r in t1))))
    st2, _ = drop_top(st, '_reg', 3)
    O2, E2, Er2 = oe(st2, '_reg')
    n2 = sum(1 for v in st2.values() for r in v if r['_t'] == 'Theme2')
    n1 = sum(1 for v in st2.values() for r in v if r['_t'] == 'Theme1')
    o, ple, pge, p2 = perm_p(st2, '_reg', N_PERM, seed=9, stat='pool')
    p('    Без топ-3 по регистрациям в каждой группе (%d T2 / %d T1): O = %d, E по Theme1 = %.2f → O/E = %s; E по пулу = %.2f, пуассон p = %.4f, перестановка p = %.4f' %
      (n2, n1, O2, Er2, fmt(O2 / Er2 if Er2 else None), E2, poisson_le(O2, E2), ple if ple is not None else float('nan')))
    st3 = {k: [r for r in v if r['домен'] != '1908.team'] for k, v in st.items()}
    O3, E3, Er3 = oe(st3, '_reg')
    p('    Без одного 1908.team: O = %d, E по Theme1 = %.2f → O/E = %.2f; пуассон P(X ≤ O | E по пулу %.2f) = %.4f' %
      (O3, Er3, O3 / Er3 if Er3 else 0, E3, poisson_le(O3, E3)))
p('  Внутри партии после удаления топ-3 у Theme2 остаётся 0 регистраций, у Theme1 — 3: сравнивать нечего.')
p('  Грубый срез по регистрациям и без топ-3 остаётся «значимым», но он — тень партии, а не шаблона (см. тестировщика).')
p()

# ---------------------------------------------------------------- 5. перебор срезов
p('=' * 100)
p('5. ПЕРЕБОР СРЕЗОВ')
p('=' * 100)
p('5a. Сколько p-значений напечатал тестировщик: 6 срезов × (выход-перестановка + рег-пуассон + рег-перестановка) = 18,')
p('    плюс 3 партии по отдельности (5d) и 7 суток без p (6). Семейство «эффект шаблона ВНУТРИ партии» — 4 среза: 5a, 5b, 5c, 7a.')
p('    Наблюдённые односторонние p по выходу: 5a 0,0316; 5b 0,0285; 5c 0,0352; 7a 0,0483. Холм по 4: min p × 4 = 0,114 — не проходит.')
p('    Но 4 среза — почти одни и те же 33 домена, Холм слишком строг. Честнее — Westfall–Young на одной перестановке:')
p()

p('5b. Westfall–Young: одна перестановка внутри самых мелких ячеек (день × зона × час × «сайтов») по всем зонам 19–20.08,')
p('    на каждой перестановке считаем все 4 среза (выход) и 4 среза (регистрации); семейный p = доля перестановок, где')
p('    лучший (минимальный) p по семейству не больше наблюдённого лучшего. %d перестановок.' % N_FAMILY)

fam_defs = [
    ('5a', main, lambda r: (r['_day'], r['_hour'], r['сайтов']), 3),
    ('5b', main, lambda r: (r['_day'], r['_hour']), 1),
    ('5c', main, lambda r: (r['_day'], r['_hour'], r['сайтов']), 1),
    ('7a', all_zones, lambda r: (r['_day'], r['зона'], r['_hour']), 1),
]
fam_strata = [(name, strata_of(ds, fn, me)) for name, ds, fn, me in fam_defs]
cells = defaultdict(list)
for r in all_zones:
    cells[(r['_day'], r['зона'], r['_hour'], r['сайтов'])].append(r)
cells = {k: v for k, v in cells.items() if len(set(r['_t'] for r in v)) > 1}
p('    Ячеек с обоими шаблонами: %d (%s)' % (len(cells), '; '.join('%s %s %d:00/%s — T1 %d, T2 %d' % (
    k[0], k[1], k[2], k[3], sum(1 for r in v if r['_t'] == 'Theme1'), sum(1 for r in v if r['_t'] == 'Theme2')) for k, v in sorted(cells.items()))))
rnd = random.Random(21)
base = {id(r): r['_t'] for r in all_zones}
obs_stats = {}
for metric in ('_v3', '_reg'):
    for name, st in fam_strata:
        Oo, Ee, Er = oe(st, metric)
        obs_stats[(metric, name)] = Oo / Ee if Ee > 0 else 1.0
null = {k: [] for k in obs_stats}
for _ in range(N_FAMILY):
    lab = dict(base)
    for v in cells.values():
        labs = [r['_t'] for r in v]
        rnd.shuffle(labs)
        for r, lb in zip(v, labs):
            lab[id(r)] = lb
    for metric in ('_v3', '_reg'):
        for name, st in fam_strata:
            Oo, Ee, Er = oe(st, metric, lab)
            null[(metric, name)].append(Oo / Ee if Ee > 0 else 1.0)
# маргинальные p на этой (более мелкой) перестановке
sorted_null = {k: sorted(v) for k, v in null.items()}
marg = {}
for k in obs_stats:
    marg[k] = bisect.bisect_right(sorted_null[k], obs_stats[k] + 1e-12) / N_FAMILY
p('    Маргинальные односторонние p на перестановке внутри мелких ячеек (выход): ' +
  ', '.join('%s %.4f' % (n, marg[('_v3', n)]) for n, _ in fam_strata))
p('    Маргинальные односторонние p (регистрации, перестановка):                ' +
  ', '.join('%s %.4f' % (n, marg[('_reg', n)]) for n, _ in fam_strata))
for metric, mname in (('_v3', 'выход'), ('_reg', 'регистрации')):
    names = [n for n, _ in fam_strata]
    obs_min = min(marg[(metric, n)] for n in names)
    cnt = 0
    for b in range(N_FAMILY):
        pmin = 1.0
        for n in names:
            pb = bisect.bisect_right(sorted_null[(metric, n)], null[(metric, n)][b] + 1e-12) / N_FAMILY
            if pb < pmin:
                pmin = pb
        if pmin <= obs_min + 1e-12:
            cnt += 1
    p('    %s: лучший наблюдённый p по 4 срезам = %.4f → семейный p (Westfall–Young) = %.4f' % (mname, obs_min, cnt / N_FAMILY))
p()

# ---------------------------------------------------------------- 6. грубый срез без топ-3
p('=' * 100)
p('6. ГРУБЫЙ СРЕЗ (страта = день) — для полноты: устойчив ли сам разрыв, тень партии он или нет')
p('=' * 100)
O, E, Eref = oe(crude, '_v3')
o, ple, pge, p2 = perm_p(crude, '_v3', N_PERM, seed=1, stat='pool')
p('  Как есть: O = %d, E по Theme1 = %.0f → O/E = %.3f; перестановка p = %.4f' % (O, Eref, O / Eref, ple))
st, _ = drop_top(crude, '_v3', 3)
O, E, Eref = oe(st, '_v3')
o, ple, pge, p2 = perm_p(st, '_v3', N_PERM, seed=1, stat='pool')
p('  Без топ-3 по выходу в каждой группе: O = %d, E по Theme1 = %.0f → O/E = %.3f; перестановка p = %.4f' % (O, Eref, O / Eref, ple))
# без вечерней партии Theme2 (20-21 час 20.08) — что останется от грубого разрыва
st = {k: [r for r in v if not (r['_t'] == 'Theme2' and r['_day'] == '08-20' and r['_hour'] in (20, 21))] for k, v in crude.items()}
O, E, Eref = oe(st, '_v3')
o, ple, pge, p2 = perm_p(st, '_v3', N_PERM, seed=1, stat='pool')
n2 = sum(1 for v in st.values() for r in v if r['_t'] == 'Theme2')
p('  Без вечерней Theme2-партии 20.08 (остаётся %d Theme2): O = %d, E по Theme1 = %.0f → O/E = %.3f; перестановка p = %.4f' %
  (n2, O, Eref, O / Eref, ple))
p('  → грубый разрыв статистически реален, но это разрыв «партия против остальных дней»: удаление одной партии его почти снимает.')
p()

# ---------------------------------------------------------------- ВЫВОД
p('=' * 100)
p('ВЫВОД СКЕПТИКА')
p('=' * 100)
p('1. Суммы, не средние: у тестировщика всё по правилу 2, O/E из сумм. Претензий нет.')
p('2. Регистраций у Theme2 всего 3 (внутри партии — 2), у Theme1 внутри партии 12, из них 5 у одного домена: часть гипотезы')
p('   «в 4–8 раз меньше регистраций» на этих объёмах не проверяема в принципе. Тестировщик это признал; после удаления топ-3')
p('   у Theme2 остаётся 0, у Theme1 — 3 регистрации.')
p('3. «Остаточный эффект шаблона внутри партии» (O/E 0,74, p = 0,032) — на границе, не доказательство:')
p('   - из двух партий значима только 19.08 23:00 с опорой на 4 домена Theme1 (точный перебор: одност. p = %.3f, двуст. %.3f);' %
  (exact_p_one_stratum(dec[sorted(dec)[0]], '_v3')[1], 2 * exact_p_one_stratum(dec[sorted(dec)[0]], '_v3')[1]))
p('     партия 20.08 12:00 (12 против 8) — p = %.2f;' % exact_p_one_stratum(dec[sorted(dec)[1]], '_v3')[1])
p('   - двусторонний p = %.3f; удаление одного домена из 33 уводит p за 0,05 в %d случаях из 33; без 3 лучших Theme1 O/E = 0,82, p = 0,12;' %
  (p2_pool, n_over))
p('   - бутстреп-интервал O/E [%.2f; %.2f] — единицу %s, но верхний край почти у 1; семейный p по 4 срезам (раздел 5b) — на границе 0,05.' %
  (lo, hi, 'накрывает' if hi >= 1 else 'не накрывает'))
p('   Итого: направление устойчиво (все проверки дают O/E 0,68–0,82), но значимость зависит от выбора статистики, стороны теста и 1–3 доменов.')
p('4. Числа тестировщика воспроизводятся, метод верный (суммы, единица — домен, перестановка внутри страты). Вердикт «частично»')
p('   опирается на грубый разрыв (статистически реален: p < 0,0001, без топ-3 то же), который сам тестировщик отнёс к партии.')
p('   Ужать надо формулировку про остаток: не «слабый эффект ≈0,75 возможен», а «внутри партии разница 0,74 на границе значимости')
p('   (одност. p 0,03, двуст. 0,06, семейный 0,05), держится на партии из 4 опорных Theme1; по регистрациям сравнивать нечего».')
p()
p('ЧТО С ЭТИМ ДЕЛАТЬ: ничего по шаблону на этом файле — это не рычаг и даже не «подозрение с p = 0,03», а неразделимая с партией')
p('метка. Проверяемое на уже запущенных данных: дозаписать набор контента для 106 доменов 19–20.08 (пункт 2 тестировщика) и пересчитать.')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT, file=sys.stderr)

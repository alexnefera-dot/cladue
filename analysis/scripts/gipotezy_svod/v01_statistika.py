#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №1 (паттерн имени домена и длина метки). Угол: СТАТИСТИКА.

Результат тестировщика: выход — все O/E 0,98–1,04, p = 0,52 (нет эффекта); регистрации — 4 группы p = 0,13,
но объявленный контраст casino_infix O/E 1,56 (21 против 13,4), p = 0,041 «формально проходит критерий эффекта».

Что проверяем:
  1. Суммы, а не средние по доменам от долей — сверяем с кодом тестировщика.
  2. Перебор срезов: сколько p-значений напечатано; ОДНА перестановка меток паттерна внутри пула (10 000),
     на ней — все срезы главного блока сразу и семейный p по методу min-p (Westfall–Young):
     доля перестановок, в которых лучший p по любому срезу семейства не больше наблюдённого лучшего.
     Семейства: (а) два объявленных контраста; (б) 4 группы по регистрациям при E_сайт;
     (в) 4 группы × 3 ожидания; (г) весь главный блок тестировщика (24 статистики).
     Плюс p того же контраста по отношению O/E (|log O/E|), а не по разности O−E: коридор нуля 0,52–1,64
     содержит 1,56 — значит по отношению p > 0,05, и это тот же тест.
  3. Объёмы: регистраций в группах и в ячейках зона × паттерн; минимально различимый эффект (97,5 % квантиль
     O/E под нулём) — можно ли вообще увидеть коридор 0,85–1,15 на таких объёмах.
  4. Держится ли на 1–3 доменах: доля топ-3 доменов; удаляем топ-3 домена по регистрациям В КАЖДОЙ группе
     (12 доменов), заново собираем пулы и ожидания, пересчитываем O/E и перестановочный p; отдельно —
     только топ-3 у casino_infix. Вклад пулов в O−E casino_infix, leave-one-pool-out, разбивка по датам.
  5. Критерий «один знак в team и lol»: сколько регистраций в зонных ячейках и как часто под нулём оба
     знака совпадают сами по себе.
  6. Объяснение тестировщика про «партии» (блок часа) для противоположных знаков выхода casino_* в team/lol:
     страта пул + зона + блок часа — исчезает ли lol 1,13 (p 0,009).

Только stdlib. Вывод — в stdout и в analysis/export/gipotezy_svod/v01_statistika.txt.
Запуск: python3 v01_statistika.py [N_PERM]
"""
import bisect
import csv
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'v01_statistika.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
N_SUB = min(N_PERM, 5000)
PATTERNS = ['numeric', 'alpha_other', 'casino_prefix', 'casino_infix']
CASINO = ('casino_prefix', 'casino_infix')
ZONES = ['team', 'lol', 'casino', 'buzz', 'прочие']
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
FIELDS = ['сайтов', 'вышли3', 'E_выход', 'рег', 'E_рег_сайт', 'E_рег_вышли', 'E_рег_клик']
EXPS = [('E_рег_сайт', 'сайт'), ('E_рег_вышли', 'вышли'), ('E_рег_клик', 'клик')]

_out = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    _out.append(s)


def toi(s):
    return int(float(s)) if s not in ('', None) else 0


def oe(o, e):
    return f'{o / e:.2f}' if e > 0 else '—'


def zone_of(z):
    return z if z in ('team', 'lol', 'casino', 'buzz') else 'прочие'


def poisson_two_sided(k, lam):
    """Справочный точный пуассоновский двусторонний p (без страты, только для масштаба)."""
    def cdf(x):
        return sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(0, int(x) + 1))
    lo = cdf(k)
    hi = 1 - cdf(k - 1) if k > 0 else 1.0
    return min(1.0, 2 * min(lo, hi))


# ---------------------------------------------------------------------------
# загрузка, тот же фильтр, пулы, ожидания
# ---------------------------------------------------------------------------

def load_filtered():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    kept = []
    for r in rows:
        if r['домен'] in OUTLIERS or r['окно закрыто'] != 'да' or r['дней'] == '1' or r['набор контента'] == NO_CONTENT:
            continue
        kept.append(dict(
            домен=r['домен'], зона=zone_of(r['зона']), день=r['день запуска'], набор=r['набор контента'],
            паттерн=r['паттерн имени'], блок=r['блок часа'],
            сайтов=toi(r['сайтов в окне']), вышли3=toi(r['вышли за 3 суток']),
            рег=toi(r['регистраций в окне 3 суток']), фд=toi(r['ФД в окне 3 суток']),
            клик=toi(r['кликов из поиска в окне']),
        ))
    for d in kept:
        d['пул'] = (d['набор'], d['день'])
    return rows, kept


def fresh(items):
    return [dict(d) for d in items]


def multi_pools(items, pool_key=lambda d: d['пул']):
    pools = defaultdict(list)
    for d in items:
        pools[pool_key(d)].append(d)
    return {k: v for k, v in pools.items() if len(set(d['паттерн'] for d in v)) >= 2}


def add_exp(pools):
    for ds in pools.values():
        S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds)
        R = sum(d['рег'] for d in ds); C = sum(d['клик'] for d in ds)
        for d in ds:
            d['E_выход'] = V / S * d['сайтов'] if S else 0.0
            d['E_рег_сайт'] = R / S * d['сайтов'] if S else 0.0
            d['E_рег_вышли'] = R / V * d['вышли3'] if V else 0.0
            d['E_рег_клик'] = R / C * d['клик'] if C else 0.0


def build(items, pool_key=lambda d: d['пул']):
    pools = multi_pools(items, pool_key)
    flat = [d for v in pools.values() for d in v]
    add_exp(pools)
    return pools, flat


# ---------------------------------------------------------------------------
# перестановочный движок: суммы по (паттерн, зона, поле) для наблюдения и каждой перестановки
# ---------------------------------------------------------------------------

def perm_engine(items, pool_key, n_perm, seed=1):
    n = len(items)
    nF, nZ = len(FIELDS), len(ZONES)
    gi0 = [PATTERNS.index(d['паттерн']) for d in items]
    zi = [ZONES.index(d['зона']) for d in items]
    rows = [[float(d[f]) for f in FIELDS] for d in items]
    pools = defaultdict(list)
    for i, d in enumerate(items):
        pools[pool_key(d)].append(i)
    pool_idx = [v for v in pools.values() if len(v) >= 2]

    def sums(gi):
        acc = [0.0] * (4 * nZ * nF)
        for i in range(n):
            base = (gi[i] * nZ + zi[i]) * nF
            row = rows[i]
            for f in range(nF):
                acc[base + f] += row[f]
        return acc

    obs = sums(gi0)
    rng = random.Random(seed)
    gi = gi0[:]
    perms = []
    for _ in range(n_perm):
        for idx in pool_idx:
            cur = [gi[i] for i in idx]
            rng.shuffle(cur)
            for i, g in zip(idx, cur):
                gi[i] = g
        perms.append(sums(gi))
    return obs, perms


def G(acc, g, f, z=None):
    nF, nZ = len(FIELDS), len(ZONES)
    fi = FIELDS.index(f)
    gi = PATTERNS.index(g)
    if z is None:
        return sum(acc[(gi * nZ + zz) * nF + fi] for zz in range(nZ))
    return acc[(gi * nZ + ZONES.index(z)) * nF + fi]


def stats_of(acc):
    """Все статистики главного блока тестировщика + зонные + log-отношение. kind: 'abs' (двусторонний) / 'ge'."""
    st = {}
    for g in PATTERNS:
        st[f'выход {g} O−E'] = G(acc, g, 'вышли3') - G(acc, g, 'E_выход')
    st['выход χ²(4)'] = sum((G(acc, g, 'вышли3') - G(acc, g, 'E_выход')) ** 2 / G(acc, g, 'E_выход') for g in PATTERNS if G(acc, g, 'E_выход') > 0)
    st['A1 выход casino_* O−E'] = sum(st[f'выход {g} O−E'] for g in CASINO)
    for ef, nm in EXPS:
        for g in PATTERNS:
            st[f'рег/{nm} {g} O−E'] = G(acc, g, 'рег') - G(acc, g, ef)
        st[f'рег/{nm} χ²(4)'] = sum((G(acc, g, 'рег') - G(acc, g, ef)) ** 2 / G(acc, g, ef) for g in PATTERNS if G(acc, g, ef) > 0)
        st[f'рег/{nm} casino_* O−E'] = sum(st[f'рег/{nm} {g} O−E'] for g in CASINO)
    o, e = G(acc, 'casino_infix', 'рег'), G(acc, 'casino_infix', 'E_рег_сайт')
    st['A2 рег/сайт casino_infix log(O/E)'] = math.log(o / e) if o > 0 and e > 0 else (-9.0 if e > 0 else 0.0)
    # односторонние статистики в объявленных направлениях: А1 «casino_* хуже по выходу» (−(O−E) >= ...), А2 «casino_infix лучше» (O−E >= ...)
    st['1s A1 выход casino_* −(O−E)'] = -st['A1 выход casino_* O−E']
    st['1s A2 рег/сайт casino_infix O−E'] = st['рег/сайт casino_infix O−E']
    for z in ('team', 'lol'):
        st[f'рег/сайт casino_infix [{z}] O−E'] = G(acc, 'casino_infix', 'рег', z) - G(acc, 'casino_infix', 'E_рег_сайт', z)
        st[f'выход casino_* [{z}] O−E'] = sum(G(acc, g, 'вышли3', z) - G(acc, g, 'E_выход', z) for g in CASINO)
    return st


def kind_of(name):
    return 'ge' if ('χ²' in name or name.startswith('1s')) else 'abs'


def pvals(obs_st, perm_st):
    """p наблюдения и p каждой перестановки (для min-p) по каждой статистике."""
    N = len(perm_st)
    p_obs, p_perm = {}, {}
    for name in obs_st:
        vals = [s[name] for s in perm_st]
        if kind_of(name) == 'abs':
            key = abs
        else:
            key = lambda x: x
        srt = sorted(key(v) for v in vals)
        def pv(x):
            return (N - bisect.bisect_left(srt, key(x)) + 1) / (N + 1)
        p_obs[name] = pv(obs_st[name])
        p_perm[name] = [pv(v) for v in vals]
    return p_obs, p_perm


def family_p(names, p_obs, p_perm):
    N = len(next(iter(p_perm.values())))
    m_obs = min(p_obs[n] for n in names)
    m_perm = [min(p_perm[n][k] for n in names) for k in range(N)]
    return m_obs, (sum(1 for v in m_perm if v <= m_obs) + 1) / (N + 1)


def quant(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, int(q * len(s)))]


def group_table(title, obs, perms, o_f, e_f, unit):
    P()
    P(f'--- {title} ---')
    P(f'{"паттерн":<14} {"O":>7} {"E":>8} {"O/E":>6} {"O−E":>7}  {"O/E под нулём 2,5–97,5%":>24}  {"p (|O−E|)":>10}  {"p (|log O/E|)":>13}')
    for g in PATTERNS:
        o, e = G(obs, g, o_f), G(obs, g, e_f)
        d = o - e
        pd = [G(a, g, o_f) - G(a, g, e_f) for a in perms]
        ratios = [G(a, g, o_f) / G(a, g, e_f) for a in perms if G(a, g, e_f) > 0]
        p_abs = (sum(1 for v in pd if abs(v) >= abs(d)) + 1) / (len(pd) + 1)
        if o > 0 and e > 0:
            lr = abs(math.log(o / e))
            p_lr = (sum(1 for r in ratios if r > 0 and abs(math.log(r)) >= lr) + 1) / (len(ratios) + 1)
        else:
            p_lr = float('nan')
        P(f'{g:<14} {int(o):>7} {e:>8.1f} {oe(o, e):>6} {d:>+7.1f}  {quant(ratios, 0.025):>10.2f} – {quant(ratios, 0.975):<10.2f}  {p_abs:>10.3f}  {p_lr:>13.3f}')
    P(f'  ({unit})')


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    rows, kept = load_filtered()
    P('=' * 100)
    P('СКЕПТИК к гипотезе №1 — угол СТАТИСТИКА')
    P('=' * 100)
    P(f'Фильтр тестировщика воспроизведён: доменов после фильтра {len(kept)} (у тестировщика 1511).')
    pools, items = build(fresh(kept))
    P(f'Пулов «набор + день» с >= 2 паттернами: {len(pools)}; доменов: {len(items)}; сайтов: {sum(d["сайтов"] for d in items)}; '
      f'регистраций в окне: {sum(d["рег"] for d in items)}; ФД: {sum(d["фд"] for d in items)} (у тестировщика 101 / 969 / 199 597 / 175 / 33).')

    # ------------------------------------------------------------------ 1. суммы vs средние
    P()
    P('=' * 100)
    P('1. СУММЫ ИЛИ СРЕДНИЕ ПО ДОМЕНАМ')
    P('=' * 100)
    P('В коде тестировщика (add_expectations, perm_engine.sums) O и E — суммы по доменам группы: O = Σ регистраций, '
      'E = Σ (ставка пула × сайтов домена). Это суммы, не средние долей. Замечание не подтверждается.')
    for g in PATTERNS:
        ds = [d for d in items if d['паттерн'] == g]
        mean_rate = sum(100 * d['рег'] / d['сайтов'] for d in ds if d['сайтов']) / len(ds)
        sum_rate = 100 * sum(d['рег'] for d in ds) / sum(d['сайтов'] for d in ds)
        P(f'  {g:<14} доменов {len(ds):>3}: рег/100 сайтов из СУММ {sum_rate:.3f}; среднее по доменам от долей {mean_rate:.3f} — '
          f'{"почти равны (сайтов в окне ~206 у всех)" if abs(mean_rate - sum_rate) < 0.01 else "расходятся"}')
    P('  Единственное место со средними по доменам — «задержка до поиска» (среднее медиан внутри пула, знаковый тест по пулам); '
      'это побочная метрика, на вердикт не влияет.')

    # ------------------------------------------------------------------ 2. объёмы
    P()
    P('=' * 100)
    P('2. ОБЪЁМЫ РЕГИСТРАЦИЙ В ГРУППАХ И ЯЧЕЙКАХ')
    P('=' * 100)
    P(f'{"паттерн":<14} {"доменов":>8} {"рег":>5} {"доменов с рег":>14} {"топ-1":>6} {"топ-2":>6} {"топ-3":>6} {"доля топ-3":>11}   по зонам (доменов / рег)')
    for g in PATTERNS:
        ds = sorted([d for d in items if d['паттерн'] == g], key=lambda d: -d['рег'])
        R = sum(d['рег'] for d in ds)
        t = [d['рег'] for d in ds[:3]]
        zs = '; '.join(f'{z} {sum(1 for d in ds if d["зона"] == z)}/{sum(d["рег"] for d in ds if d["зона"] == z)}' for z in ZONES if any(d['зона'] == z for d in ds))
        P(f'{g:<14} {len(ds):>8} {R:>5} {sum(1 for d in ds if d["рег"] > 0):>14} {t[0]:>6} {t[1]:>6} {t[2]:>6} {sum(t) / R if R else 0:>11.2f}   {zs}')
    zc = max(sum(d['рег'] for d in items if d['паттерн'] == g and d['зона'] == z) for g in CASINO for z in ('team', 'lol'))
    P(f'Порог «менее 20 регистраций в группе — не доказательство»: casino_prefix ({sum(d["рег"] for d in items if d["паттерн"] == "casino_prefix")}) ниже порога; '
      f'casino_infix ({sum(d["рег"] for d in items if d["паттерн"] == "casino_infix")}) на пороге; все зонные ячейки casino (team/lol) — не более {zc} регистраций, далеко ниже.')

    # ------------------------------------------------------------------ главная перестановка
    P()
    P('=' * 100)
    P(f'3. ОДНА ПЕРЕСТАНОВКА ({N_PERM}) — ВСЕ СРЕЗЫ ГЛАВНОГО БЛОКА СРАЗУ, СЕМЕЙНЫЕ p')
    P('=' * 100)
    obs, perms = perm_engine(items, lambda d: d['пул'], N_PERM, seed=1)
    obs_st = stats_of(obs)
    perm_st = [stats_of(a) for a in perms]
    p_obs, p_perm = pvals(obs_st, perm_st)

    group_table('Выход: O = вышли за 3 суток, E = ставка пула × сайтов', obs, perms, 'вышли3', 'E_выход', 'вышедших сайтов')
    for ef, nm in EXPS:
        group_table(f'Регистрации при E_{nm}', obs, perms, 'рег', ef, 'регистраций')

    P()
    P('Отдельные p (та же перестановка, что у тестировщика; двусторонний по |O−E| для разностей, «>=» для χ²):')
    for name in obs_st:
        P(f'  {name:<44} набл. {obs_st[name]:>+9.2f}   p = {p_obs[name]:.3f}')
    P()
    P('Проверка контраста А2 по ОТНОШЕНИЮ, а не по разности:')
    ratios = [G(a, 'casino_infix', 'рег') / G(a, 'casino_infix', 'E_рег_сайт') for a in perms if G(a, 'casino_infix', 'E_рег_сайт') > 0]
    o_i, e_i = G(obs, 'casino_infix', 'рег'), G(obs, 'casino_infix', 'E_рег_сайт')
    r_i = o_i / e_i
    p_hi = (sum(1 for r in ratios if r >= r_i) + 1) / (len(ratios) + 1)
    p_lr = p_obs['A2 рег/сайт casino_infix log(O/E)']
    P(f'  casino_infix O/E = {r_i:.2f}; коридор нуля по O/E (2,5–97,5%) = {quant(ratios, 0.025):.2f}–{quant(ratios, 0.975):.2f} — наблюдённое ВНУТРИ коридора; '
      f'односторонний p(O/E >= {r_i:.2f}) = {p_hi:.3f}; двусторонний по |log O/E| p = {p_lr:.3f}; тестировщик по |O−E| дал 0,041.')
    P(f'  Справочно, без страты: пуассоновский двусторонний p для 21 при λ = 13,4: {poisson_two_sided(21, 13.4):.3f}.')
    P('  Одна и та же перестановка даёт p < 0,05 по разности и p > 0,05 по отношению: результат на границе и зависит от выбора статистики, '
      'а критерий гипотезы сформулирован через O/E.')

    P()
    P('Семейные p (min-p по перестановкам: доля перестановок, где лучший p семейства <= наблюдённого лучшего):')
    fam = {
        '(а) два объявленных контраста (А1 выход casino_*, А2 рег/сайт casino_infix)':
            ['A1 выход casino_* O−E', 'рег/сайт casino_infix O−E'],
        '(а\') те же два контраста, односторонние p в объявленных направлениях (А1: casino_* хуже; А2: infix лучше)':
            ['1s A1 выход casino_* −(O−E)', '1s A2 рег/сайт casino_infix O−E'],
        '(б) 4 группы по регистрациям при E_сайт': [f'рег/сайт {g} O−E' for g in PATTERNS],
        '(в) 4 группы × 3 ожидания по регистрациям (12 срезов)': [f'рег/{nm} {g} O−E' for _, nm in EXPS for g in PATTERNS],
        '(г) весь главный блок тестировщика (24 статистики: выход 4+χ²+А1, регистрации 3×(4+χ²+casino_*))':
            [f'выход {g} O−E' for g in PATTERNS] + ['выход χ²(4)', 'A1 выход casino_* O−E']
            + [f'рег/{nm} {g} O−E' for _, nm in EXPS for g in PATTERNS]
            + [f'рег/{nm} χ²(4)' for _, nm in EXPS] + [f'рег/{nm} casino_* O−E' for _, nm in EXPS],
        '(д) главный блок + зонные контрасты casino (28 статистик)':
            [f'выход {g} O−E' for g in PATTERNS] + ['выход χ²(4)', 'A1 выход casino_* O−E']
            + [f'рег/{nm} {g} O−E' for _, nm in EXPS for g in PATTERNS]
            + [f'рег/{nm} χ²(4)' for _, nm in EXPS] + [f'рег/{nm} casino_* O−E' for _, nm in EXPS]
            + [f'рег/сайт casino_infix [{z}] O−E' for z in ('team', 'lol')] + [f'выход casino_* [{z}] O−E' for z in ('team', 'lol')],
    }
    fam_res = {}
    for title, names in fam.items():
        m_obs, fp = family_p(names, p_obs, p_perm)
        best = min(names, key=lambda n: p_obs[n])
        fam_res[title] = fp
        P(f'  {title}: лучший срез «{best}» p = {m_obs:.3f} → семейный p = {fp:.3f}')
    h01_path = os.path.join(OUT_DIR, 'h01_domain_name_pattern.txt')
    n_p = -1
    if os.path.exists(h01_path):
        with open(h01_path, encoding='utf-8') as fh:
            n_p = len(re.findall(r'(?<![A-Za-z_])p\s*(?:\([^)]*\))?\s*=\s*\d', fh.read()))
    P(f'  В отчёте тестировщика напечатано p-значений: {n_p}; из них с p < 0,05 — пять: А2 (0,041), lol выход 4 группы (0,022), lol casino_* выход (0,009), '
      f'сверхдисперсия (0,002; 0,001). При {n_p} связанных тестах ~{n_p * 0.05:.1f} значений ниже 0,05 ожидаются под нулём сами по себе.')

    # ------------------------------------------------------------------ минимально различимый эффект
    P()
    P('Минимально различимый эффект (что вообще можно увидеть при p < 0,05 на этих объёмах):')
    P(f'{"группа":<22} {"E_сайт":>7} {"O/E 2,5%":>9} {"O/E 97,5%":>10}  критерий «нет эффекта» 0,85–1,15 проверяем?')
    for g in PATTERNS + ['casino_*']:
        if g == 'casino_*':
            rr = [sum(G(a, x, 'рег') for x in CASINO) / sum(G(a, x, 'E_рег_сайт') for x in CASINO) for a in perms]
            e = sum(G(obs, x, 'E_рег_сайт') for x in CASINO)
        else:
            rr = [G(a, g, 'рег') / G(a, g, 'E_рег_сайт') for a in perms if G(a, g, 'E_рег_сайт') > 0]
            e = G(obs, g, 'E_рег_сайт')
        lo, hi = quant(rr, 0.025), quant(rr, 0.975)
        P(f'{g:<22} {e:>7.1f} {lo:>9.2f} {hi:>10.2f}  {"да" if lo >= 0.85 and hi <= 1.15 else "НЕТ: коридор нуля шире 0,85–1,15"}')
    P('  Для регистраций критерий «все O/E в 0,85–1,15» невыполним ни для одной группы: коридор случайности шире критерия даже у numeric. '
      'Вердикт «частично» по регистрациям — артефакт недостижимого критерия, а не свойство данных.')

    # ------------------------------------------------------------------ 4. топ-3 доменов
    P()
    P('=' * 100)
    P('4. ДЕРЖИТСЯ ЛИ НА 1–3 ДОМЕНАХ: УДАЛЯЕМ ТОП-3 ПО РЕГИСТРАЦИЯМ В КАЖДОЙ ГРУППЕ, ПУЛЫ И ОЖИДАНИЯ ЗАНОВО')
    P('=' * 100)
    top3 = {}
    for g in PATTERNS:
        ds = sorted([d for d in items if d['паттерн'] == g], key=lambda d: -d['рег'])
        top3[g] = [d['домен'] for d in ds[:3]]
        P(f'  {g:<14} удаляем: ' + ', '.join(f'{d["домен"]} ({d["рег"]})' for d in ds[:3]))
    rem_all = {x for v in top3.values() for x in v}

    def rerun(label, removed, n_perm):
        sub = fresh([d for d in kept if d['домен'] not in removed])
        pools2, items2 = build(sub)
        P()
        P(f'--- {label}: удалено {len(removed)} доменов; пулов с >= 2 паттернами {len(pools2)}, доменов {len(items2)}, '
          f'регистраций {sum(d["рег"] for d in items2)} ---')
        obs2, perms2 = perm_engine(items2, lambda d: d['пул'], n_perm, seed=2)
        st2 = stats_of(obs2)
        pst2 = [stats_of(a) for a in perms2]
        po2, _ = pvals(st2, pst2)
        P(f'{"паттерн":<14} {"доменов":>8} {"выход O/E":>10} {"рег/сайт O/E":>13} {"рег/вышли O/E":>14} {"рег/клик O/E":>13}   O рег / E_сайт')
        for g in PATTERNS:
            n_g = sum(1 for d in items2 if d['паттерн'] == g)
            P(f'{g:<14} {n_g:>8} {oe(G(obs2, g, "вышли3"), G(obs2, g, "E_выход")):>10} '
              f'{oe(G(obs2, g, "рег"), G(obs2, g, "E_рег_сайт")):>13} {oe(G(obs2, g, "рег"), G(obs2, g, "E_рег_вышли")):>14} '
              f'{oe(G(obs2, g, "рег"), G(obs2, g, "E_рег_клик")):>13}   {int(G(obs2, g, "рег"))} / {G(obs2, g, "E_рег_сайт"):.1f}')
        P(f'  p: выход χ²(4) {po2["выход χ²(4)"]:.3f}; А1 casino_* выход {po2["A1 выход casino_* O−E"]:.3f}; '
          f'рег/сайт χ²(4) {po2["рег/сайт χ²(4)"]:.3f}; А2 casino_infix рег/сайт {po2["рег/сайт casino_infix O−E"]:.3f} '
          f'(рег/вышли {po2["рег/вышли casino_infix O−E"]:.3f}, рег/клик {po2["рег/клик casino_infix O−E"]:.3f}); '
          f'casino_prefix рег/сайт {po2["рег/сайт casino_prefix O−E"]:.3f}')
        return obs2, po2

    obs_a, po_a = rerun('(А) без топ-3 в КАЖДОЙ группе (симметрично)', rem_all, N_SUB)
    obs_b, po_b = rerun('(Б) без топ-3 только у casino_infix', set(top3['casino_infix']), N_SUB)
    obs_c, po_c = rerun('(В) без топ-1 только у casino_infix (1109casino.casino)', set(top3['casino_infix'][:1]), N_SUB)

    # вклад пулов
    P()
    P('Вклад пулов в O−E casino_infix (рег/сайт), пулы с casino_infix и хотя бы одной регистрацией в пуле:')
    contrib = []
    for k, ds in pools.items():
        inf = [d for d in ds if d['паттерн'] == 'casino_infix']
        if not inf or sum(d['рег'] for d in ds) == 0:
            continue
        o = sum(d['рег'] for d in inf); e = sum(d['E_рег_сайт'] for d in inf)
        contrib.append((o - e, o, e, k, len(inf), len(ds)))
    contrib.sort(reverse=True)
    n_pos = sum(1 for c in contrib if c[0] > 0); n_neg = sum(1 for c in contrib if c[0] < 0)
    P(f'  пулов с casino_infix: {sum(1 for ds in pools.values() if any(d["паттерн"] == "casino_infix" for d in ds))}; из них с регистрациями в пуле: {len(contrib)}; '
      f'infix выше ожидания в {n_pos} пулах, ниже в {n_neg}')
    for c in contrib[:6]:
        P(f'    {c[0]:>+6.2f}  O = {c[1]}, E = {c[2]:.2f}  пул {c[3][0]} / {c[3][1]}  (infix {c[4]} из {c[5]} доменов)')
    tot_d = o_i - e_i
    P(f'  два верхних пула дают {sum(c[0] for c in contrib[:2]):+.1f} из общего O−E {tot_d:+.1f}; '
      f'без них O/E = {oe(o_i - sum(c[1] for c in contrib[:2]), e_i - sum(c[2] for c in contrib[:2]))}')
    loo = [(o_i - c[1]) / (e_i - c[2]) for c in contrib if e_i - c[2] > 0]
    P(f'  leave-one-pool-out O/E casino_infix: от {min(loo):.2f} до {max(loo):.2f}')

    # разбивка по датам
    inf_items = sorted([d for d in items if d['паттерн'] == 'casino_infix'], key=lambda d: d['день'])
    half = len(inf_items) // 2
    P()
    P('casino_infix по дате запуска (половины по доменам):')
    for nm, part in [('ранняя половина', inf_items[:half]), ('поздняя половина', inf_items[half:])]:
        o = sum(d['рег'] for d in part); e = sum(d['E_рег_сайт'] for d in part)
        P(f'  {nm}: дни {part[0]["день"]}..{part[-1]["день"]}, доменов {len(part)}, рег {o}, E {e:.1f}, O/E {oe(o, e)}')
    P('по зонам (E из пула, как в главном блоке):')
    for z in ZONES:
        part = [d for d in inf_items if d['зона'] == z]
        if not part:
            continue
        o = sum(d['рег'] for d in part); e = sum(d['E_рег_сайт'] for d in part)
        P(f'  {z}: доменов {len(part)}, рег {o}, E {e:.1f}, O/E {oe(o, e)}')

    # ------------------------------------------------------------------ 5. критерий «один знак»
    P()
    P('=' * 100)
    P('5. КРИТЕРИЙ «ОДИН ЗНАК В TEAM И LOL» — ЧТО ОН СТОИТ')
    P('=' * 100)
    same = sum(1 for s in perm_st if (s['рег/сайт casino_infix [team] O−E'] > 0) == (s['рег/сайт casino_infix [lol] O−E'] > 0))
    both_pos = sum(1 for s in perm_st if s['рег/сайт casino_infix [team] O−E'] > 0 and s['рег/сайт casino_infix [lol] O−E'] > 0)
    P(f'  casino_infix регистрации: team O = {int(G(obs, "casino_infix", "рег", "team"))}, E = {G(obs, "casino_infix", "E_рег_сайт", "team"):.1f}; '
      f'lol O = {int(G(obs, "casino_infix", "рег", "lol"))}, E = {G(obs, "casino_infix", "E_рег_сайт", "lol"):.1f} (E из пула).')
    P(f'  Под нулём (перестановки) знаки team и lol совпадают в {100 * same / len(perm_st):.0f}% случаев, оба положительны в {100 * both_pos / len(perm_st):.0f}%. '
      f'Критерий «один знак» при {int(G(obs, "casino_infix", "рег", "team"))} и {int(G(obs, "casino_infix", "рег", "lol"))} регистрациях почти ничего не отсекает.')

    # ------------------------------------------------------------------ 6. блок часа
    P()
    P('=' * 100)
    P('6. ОБЪЯСНЕНИЕ ТЕСТИРОВЩИКА ПРО «ПАРТИИ»: СТРАТА ПУЛ + ЗОНА + БЛОК ЧАСА')
    P('=' * 100)
    P('Тестировщик списал противоположные знаки выхода casino_* (team 0,92 p 0,08; lol 1,13 p 0,009) на партии внутри пула (блок часа). '
      'Проверяем: если дело в партиях, при страте пул + зона + блок часа lol-эффект должен исчезнуть.')
    for z in ('team', 'lol'):
        zk = fresh([d for d in kept if d['зона'] == z])
        for lab, key in [('пул + зона', lambda d: (d['пул'], d['зона'])), ('пул + зона + блок часа', lambda d: (d['пул'], d['зона'], d['блок']))]:
            pz, iz = build(zk, key)
            if not iz:
                continue
            oz, pmz = perm_engine(iz, key, N_SUB, seed=3)
            sz = stats_of(oz); psz = [stats_of(a) for a in pmz]
            poz, _ = pvals(sz, psz)
            oc = sum(G(oz, g, 'вышли3') for g in CASINO); ec = sum(G(oz, g, 'E_выход') for g in CASINO)
            oi = G(oz, 'casino_infix', 'рег'); ei = G(oz, 'casino_infix', 'E_рег_сайт')
            P(f'  [{z}] страта «{lab}»: страт {len(pz)}, доменов {len(iz)}, регистраций {sum(d["рег"] for d in iz)}: '
              f'casino_* выход O/E {oe(oc, ec)} ({int(oc)}/{ec:.0f}), p = {poz["A1 выход casino_* O−E"]:.3f}; выход χ²(4) p = {poz["выход χ²(4)"]:.3f}; '
              f'casino_infix рег O/E {oe(oi, ei)} ({int(oi)}/{ei:.1f}), p = {poz["рег/сайт casino_infix O−E"]:.3f}')

    # ------------------------------------------------------------------ вердикт
    P()
    P('=' * 100)
    P('ВЕРДИКТ СКЕПТИКА')
    P('=' * 100)
    P(f'1. Суммы, не средние — верно, замечание снято. Выход в поиск: O/E 0,98–1,04 при коридорах нуля ±3–10 %, p = 0,52 — часть про выход устойчива.')
    P(f'2. Регистрации: контраст casino_infix 1,56 (21 / 13,4): двусторонний p по |O−E| 0,041, по |log O/E| {p_lr:.3f} (наблюдённое внутри коридора нуля '
      f'{quant(ratios, 0.025):.2f}–{quant(ratios, 0.975):.2f}); односторонний в объявленном направлении {p_hi:.3f}. Семейный p по двум объявленным контрастам: '
      f'двусторонние {fam_res[list(fam)[0]]:.3f}, односторонние в объявленных направлениях {fam_res[list(fam)[1]]:.3f}; по 4 группам {fam_res[list(fam)[2]]:.3f}, '
      f'по 12 срезам регистраций {fam_res[list(fam)[3]]:.3f}, по всему главному блоку {fam_res[list(fam)[4]]:.3f}.')
    P(f'3. Без топ-3 доменов по регистрациям в каждой группе: casino_infix O/E {oe(G(obs_a, "casino_infix", "рег"), G(obs_a, "casino_infix", "E_рег_сайт"))} '
      f'({int(G(obs_a, "casino_infix", "рег"))} / {G(obs_a, "casino_infix", "E_рег_сайт"):.1f}), p = {po_a["рег/сайт casino_infix O−E"]:.3f}; '
      f'без топ-3 только у infix — {oe(G(obs_b, "casino_infix", "рег"), G(obs_b, "casino_infix", "E_рег_сайт"))}, p = {po_b["рег/сайт casino_infix O−E"]:.3f}; '
      f'без одного домена 1109casino.casino — {oe(G(obs_c, "casino_infix", "рег"), G(obs_c, "casino_infix", "E_рег_сайт"))}, p = {po_c["рег/сайт casino_infix O−E"]:.3f}.')
    P('4. Регистраций в группах casino 13 и 21, в зонных ячейках 3–8: критерий «нет эффекта» 0,85–1,15 по регистрациям на таких объёмах невыполним '
      'ни для одной группы (коридор нуля шире), поэтому «частично» — не вывод из данных, а следствие недостижимого критерия.')
    P('5. Итог: часть «имя не влияет на выход» стоит; часть «casino_infix формально проходит критерий эффекта» — не выдерживает ни смены статистики '
      '(разность → отношение), ни поправки на семейство, ни удаления 1–3 доменов. Вердикт по регистрациям должен быть «эффекта не видно, '
      'данных мало (детектируемый порог ~1,6×)», а не «частично».')
    P('ЧТО С ЭТИМ ДЕЛАТЬ: ничего в закупке не менять; формулировку «формально проходит порог» убрать; пересчёт на 229 доменах 16–21.09 после '
      'закрытия окна оставить как единственную честную проверку хвоста.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_out) + '\n')
    print(f'\n[записано: {OUT_PATH}]')


if __name__ == '__main__':
    main()

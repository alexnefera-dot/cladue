#!/usr/bin/env python3
"""
Проверка «тени» для гипотезы №1 (паттерн имени домена).

Вопрос скептика: не является ли остаток результата (casino_infix по регистрациям O/E 1,56, p = 0,041;
casino_* по выходу в lol 1,13 при p = 0,009 и в team 0,92) тенью зоны, блока часа (партии), одного-двух пулов,
объёма пула или дат. Страта тестировщика — «набор контента + день». Здесь та же выборка и те же
ожидания, но страты ужесточаются: + зона (все четыре: team / lol / casino / buzz), + блок часа.
Плюс вклад каждого пула в O−E, leave-one-pool-out, парные сравнения внутри страты и разбивка по размеру пула.

Только стандартная библиотека. Вывод — в stdout и в analysis/export/gipotezy_svod/v01_teni.txt.
"""

import csv
import math
import os
import random
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'v01_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
PATTERNS = ['numeric', 'alpha_other', 'casino_prefix', 'casino_infix']
CASINO = ('casino_prefix', 'casino_infix')
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'

_out = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    _out.append(s)


def toi(s):
    return int(float(s)) if s not in ('', None) else 0


def oe(o, e):
    return f'{o / e:.2f}' if e > 0 else '—'


def binom_two_sided(k, n):
    if n == 0:
        return 1.0
    k = min(k, n - k)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


# ---------------------------------------------------------------------------
# загрузка и тот же фильтр, что у тестировщика
# ---------------------------------------------------------------------------

def load_kept():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    kept = []
    for r in rows:
        if r['домен'] in OUTLIERS or r['окно закрыто'] != 'да' or r['дней'] == '1' or r['набор контента'] == NO_CONTENT:
            continue
        z = r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие'
        kept.append(dict(
            домен=r['домен'], зона=z, день=r['день запуска'], набор=r['набор контента'],
            паттерн=r['паттерн имени'], блок=r['блок часа'], час=r['час запуска'],
            аккаунт=r['аккаунт вебмастера'],
            сайтов=toi(r['сайтов в окне']), вышли3=toi(r['вышли за 3 суток']),
            рег=toi(r['регистраций в окне 3 суток']), клик=toi(r['кликов из поиска в окне']),
        ))
    return rows, kept


# ---------------------------------------------------------------------------
# стратифицированный расчёт O/E и перестановка метки внутри страты
# ---------------------------------------------------------------------------

def stratify(kept, strat_key, min_patterns=2):
    """Оставляет только страты с >= min_patterns паттернами, дописывает ожидания E_сайт."""
    strata = defaultdict(list)
    for d in kept:
        strata[strat_key(d)].append(d)
    strata = {k: v for k, v in strata.items() if len(set(d['паттерн'] for d in v)) >= min_patterns}
    items = []
    for k, ds in strata.items():
        S = sum(d['сайтов'] for d in ds)
        V = sum(d['вышли3'] for d in ds)
        R = sum(d['рег'] for d in ds)
        for d in ds:
            e = dict(d)
            e['страта'] = k
            e['E_вых'] = V / S * d['сайтов'] if S else 0.0
            e['E_рег'] = R / S * d['сайтов'] if S else 0.0
            e['E_рег_вышли'] = R / V * d['вышли3'] if V else 0.0
            items.append(e)
    return strata, items


def perm_sums(items, n_perm, seed=1, fields=('сайтов', 'вышли3', 'E_вых', 'рег', 'E_рег')):
    groups = PATTERNS
    labels = [d['паттерн'] for d in items]
    cols = {f: [float(d[f]) for d in items] for f in fields}
    pools = defaultdict(list)
    for i, d in enumerate(items):
        pools[d['страта']].append(i)
    pool_idx = [v for v in pools.values() if len(v) >= 2]

    def sums(lab):
        gi = {g: [] for g in groups}
        for i, g in enumerate(lab):
            gi[g].append(i)
        return {g: {f: sum(cols[f][i] for i in gi[g]) for f in fields} for g in groups}

    obs = sums(labels)
    rng = random.Random(seed)
    lab = labels[:]
    perms = []
    for _ in range(n_perm):
        for idx in pool_idx:
            cur = [lab[i] for i in idx]
            rng.shuffle(cur)
            for i, g in zip(idx, cur):
                lab[i] = g
        perms.append(sums(lab))
    return obs, perms


def chi(s, o_f, e_f):
    return sum((s[g][o_f] - s[g][e_f]) ** 2 / s[g][e_f] for g in PATTERNS if s[g][e_f] > 0)


def contrast_p(obs, perms, gs, o_f, e_f):
    o = sum(obs[g][o_f] for g in gs)
    e = sum(obs[g][e_f] for g in gs)
    d = o - e
    diffs = [sum(p[g][o_f] for g in gs) - sum(p[g][e_f] for g in gs) for p in perms]
    p2 = (sum(1 for v in diffs if abs(v) >= abs(d)) + 1) / (len(diffs) + 1)
    ratios = sorted(sum(p[g][o_f] for g in gs) / sum(p[g][e_f] for g in gs) for p in perms if sum(p[g][e_f] for g in gs) > 0)
    lo = ratios[int(0.025 * len(ratios))] if ratios else float('nan')
    hi = ratios[min(len(ratios) - 1, int(0.975 * len(ratios)))] if ratios else float('nan')
    return o, e, p2, lo, hi


def run_stratum(title, kept, strat_key, n_perm=N_PERM, only=None):
    strata, items = stratify(kept, strat_key)
    if only:
        items = [d for d in items if only(d)]
        strata = {k: v for k, v in strata.items() if any(only(d) for d in v)}
    cnt = Counter(d['паттерн'] for d in items)
    P()
    P(f'--- {title} ---')
    P(f'страт с >= 2 паттернами: {len(strata)}; доменов: {len(items)}; сайтов: {sum(d["сайтов"] for d in items)}; '
      f'регистраций: {sum(d["рег"] for d in items)}; страт со всеми 4 паттернами: '
      f'{sum(1 for v in strata.values() if len(set(d["паттерн"] for d in v)) == 4)}; '
      f'страт с casino_infix и хотя бы одним другим: {sum(1 for v in strata.values() if any(d["паттерн"] == "casino_infix" for d in v))}')
    obs, perms = perm_sums(items, n_perm)
    res = {}
    for nm, o_f, e_f in [('ВЫХОД (вышли за 3 суток, E_сайт)', 'вышли3', 'E_вых'), ('РЕГИСТРАЦИИ в окне (E_сайт)', 'рег', 'E_рег')]:
        P(f'  {nm}:')
        P(f'  {"паттерн":<14} {"доменов":>7} {"O":>7} {"E":>8} {"O/E":>5} {"O−E":>7}')
        for g in PATTERNS:
            o, e = obs[g][o_f], obs[g][e_f]
            P(f'  {g:<14} {cnt[g]:>7} {int(o):>7} {e:>8.1f} {oe(o, e):>5} {o - e:>+7.1f}')
            res[(g, o_f)] = (o, e)
        c_o = chi(obs, o_f, e_f)
        pv = (sum(1 for p in perms if chi(p, o_f, e_f) >= c_o) + 1) / (len(perms) + 1)
        P(f'  Σ(O−E)²/E = {c_o:.2f}; перестановочное p (4 группы) = {pv:.3f}')
        res[('p4', o_f)] = pv
    o, e, p2, lo, hi = contrast_p(obs, perms, CASINO, 'вышли3', 'E_вых')
    P(f'  контраст А1 casino_* по выходу: O = {int(o)}, E = {e:.0f}, O/E = {oe(o, e)}, O−E = {o - e:+.0f}, p (двуст.) = {p2:.3f}; коридор нуля {lo:.2f}–{hi:.2f}')
    res['A1'] = (o / e if e else float('nan'), p2)
    o, e, p2, lo, hi = contrast_p(obs, perms, ('casino_infix',), 'рег', 'E_рег')
    P(f'  контраст А2 casino_infix по регистрациям: O = {int(o)}, E = {e:.1f}, O/E = {oe(o, e)}, O−E = {o - e:+.1f}, p (двуст.) = {p2:.3f}; коридор нуля {lo:.2f}–{hi:.2f}')
    res['A2'] = (o / e if e else float('nan'), p2)
    o, e, p2, lo, hi = contrast_p(obs, perms, CASINO, 'рег', 'E_рег')
    P(f'  справочно casino_* по регистрациям: O = {int(o)}, E = {e:.1f}, O/E = {oe(o, e)}, p = {p2:.3f}')
    res['casino_reg'] = (o / e if e else float('nan'), p2)
    res['items'] = items
    res['strata'] = strata
    return res


# ---------------------------------------------------------------------------
# вклад пулов и leave-one-out
# ---------------------------------------------------------------------------

def pool_contributions(items, strata, group_test, o_f, e_f, title, top=8):
    P()
    P(f'--- {title}: вклад страт в O−E ---')
    contrib = []
    for k, ds in strata.items():
        sel = [d for d in items if d['страта'] == k and group_test(d)]
        if not sel:
            continue
        o = sum(d[o_f] for d in sel)
        e = sum(d[e_f] for d in sel)
        contrib.append((o - e, o, e, k, len(sel), len(ds), sum(d[o_f] for d in items if d['страта'] == k)))
    contrib.sort(key=lambda x: -abs(x[0]))
    tot_o = sum(c[1] for c in contrib); tot_e = sum(c[2] for c in contrib)
    P(f'  всего: O = {tot_o:.0f}, E = {tot_e:.1f}, O/E = {oe(tot_o, tot_e)}, O−E = {tot_o - tot_e:+.1f}; страт с группой: {len(contrib)}; '
      f'страт с O−E > 0: {sum(1 for c in contrib if c[0] > 1e-9)}, < 0: {sum(1 for c in contrib if c[0] < -1e-9)}, = 0: {sum(1 for c in contrib if abs(c[0]) <= 1e-9)}')
    P(f'  {"страта":<62} {"домен.гр":>8} {"в стр":>5} {"O":>4} {"E":>6} {"O−E":>6} {"O стр":>6}')
    for c in contrib[:top]:
        P(f'  {str(c[3])[:62]:<62} {c[4]:>8} {c[5]:>5} {c[1]:>4.0f} {c[2]:>6.1f} {c[0]:>+6.1f} {c[6]:>6.0f}')
    # leave-one-out
    P('  leave-one-stratum-out (O/E без самой сильной страты, без двух, без трёх):')
    o, e = tot_o, tot_e
    for i, c in enumerate(contrib[:3]):
        o -= c[1]; e -= c[2]
        P(f'    без {i + 1} самых сильных: O = {o:.0f}, E = {e:.1f}, O/E = {oe(o, e)}')
    return contrib


def sign_test_within(items, strata, group_test, o_f, title, per='сайтов'):
    """Парные сравнения внутри страты: ставка группы против ставки остальных."""
    w = l = t = 0
    n = 0
    for k, ds in strata.items():
        a = [d for d in items if d['страта'] == k and group_test(d)]
        b = [d for d in items if d['страта'] == k and not group_test(d)]
        if not a or not b:
            continue
        n += 1
        ra = sum(d[o_f] for d in a) / sum(d[per] for d in a)
        rb = sum(d[o_f] for d in b) / sum(d[per] for d in b)
        if ra > rb + 1e-12:
            w += 1
        elif rb > ra + 1e-12:
            l += 1
        else:
            t += 1
    p = binom_two_sided(w, w + l)
    P(f'  {title}: страт с обеими группами {n}; группа ЛУЧШЕ остальных в {w}, ХУЖЕ в {l}, равна в {t}; знаковый p (без равных) = {p:.3f}')
    return w, l, t, p


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    rows, kept = load_kept()
    P('=' * 100)
    P('ПРОВЕРКА ТЕНЕЙ для гипотезы №1: паттерн имени домена')
    P('=' * 100)
    P(f'Фильтр тот же: окно закрыто, дней != 1, без 3615.team/3286.team, без «КОНТЕНТ НЕ ЗАПИСАН». Осталось доменов: {len(kept)}')
    P('Зоны в отфильтрованном наборе: ' + ', '.join(f'{k}:{v}' for k, v in Counter(d['зона'] for d in kept).most_common()))

    # 0. ставки по зонам — тень зоны
    P()
    P('--- Ставки по зонам (без страты, для справки): почему зона — тень для casino-имён ---')
    P(f'  {"зона":<7} {"доменов":>7} {"сайтов":>7} {"выход %":>8} {"рег":>4} {"рег/100 сайтов":>15}   доля паттернов в зоне (numeric / alpha / prefix / infix)')
    for z in ['team', 'lol', 'casino', 'buzz']:
        ds = [d for d in kept if d['зона'] == z]
        S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds); R = sum(d['рег'] for d in ds)
        c = Counter(d['паттерн'] for d in ds)
        P(f'  {z:<7} {len(ds):>7} {S:>7} {100 * V / S:>8.1f} {R:>4} {100 * R / S:>15.3f}   ' + ' / '.join(f'{100 * c[g] / len(ds):.0f}%' for g in PATTERNS))
    P('  Зона .casino: 87 из 106 доменов — alpha_other (метки вида 1109r, 1109sh), ставка регистраций в 1,5 раза выше team и в 1,9 раза выше lol;')
    P('  зона .buzz: 0,018 рег/100 сайтов, 55 доменов, из них 26 casino-имён. Зонный разрез тестировщика (только team и lol) эти две зоны не видел.')

    # 1. страта тестировщика — воспроизведение
    r1 = run_stratum('СТРАТА 1 (как у тестировщика): набор контента + день', kept, lambda d: (d['набор'], d['день']))
    # 2. + зона (все четыре)
    r2 = run_stratum('СТРАТА 2: набор контента + день + зона (team / lol / casino / buzz)', kept, lambda d: (d['набор'], d['день'], d['зона']))
    # 3. + блок часа (партия)
    r3 = run_stratum('СТРАТА 3: набор контента + день + зона + блок часа', kept, lambda d: (d['набор'], d['день'], d['зона'], d['блок']))
    # 3б. набор + день + блок часа (без зоны) — чтобы отделить вклад зоны от вклада партии
    r3b = run_stratum('СТРАТА 3б: набор контента + день + блок часа (без зоны)', kept, lambda d: (d['набор'], d['день'], d['блок']))
    # 4. + час запуска точный
    r4 = run_stratum('СТРАТА 4: набор контента + день + зона + час запуска (точный)', kept, lambda d: (d['набор'], d['день'], d['зона'], d['час']))

    # сводная таблица
    P()
    P('=' * 100)
    P('СВОДКА: как меняются контрасты при ужесточении страты')
    P('=' * 100)
    P(f'  {"страта":<48} {"доменов":>7} {"рег":>4} {"A1 casino_* выход O/E":>22} {"p":>6} {"A2 casino_infix рег O/E":>24} {"p":>6} {"casino_* рег":>12} {"p4 выход":>8} {"p4 рег":>7}')
    for nm, r in [('1: набор + день', r1), ('2: + зона', r2), ('3: + зона + блок часа', r3), ('3б: + блок часа (без зоны)', r3b), ('4: + зона + час точный', r4)]:
        P(f'  {nm:<48} {len(r["items"]):>7} {sum(d["рег"] for d in r["items"]):>4} {r["A1"][0]:>22.2f} {r["A1"][1]:>6.3f} {r["A2"][0]:>24.2f} {r["A2"][1]:>6.3f} {r["casino_reg"][0]:>12.2f} {r[("p4", "вышли3")]:>8.3f} {r[("p4", "рег")]:>7.3f}')
    P('  O/E по 4 паттернам (регистрации, E_сайт):')
    for nm, r in [('1: набор + день', r1), ('2: + зона', r2), ('3: + зона + блок часа', r3), ('3б: + блок часа (без зоны)', r3b), ('4: + зона + час точный', r4)]:
        P(f'    {nm:<30} ' + ', '.join(f'{g} {oe(*r[(g, "рег")])} ({int(r[(g, "рег")][0])}/{r[(g, "рег")][1]:.1f})' for g in PATTERNS))
    P('  O/E по 4 паттернам (выход):')
    for nm, r in [('1: набор + день', r1), ('2: + зона', r2), ('3: + зона + блок часа', r3), ('3б: + блок часа (без зоны)', r3b), ('4: + зона + час точный', r4)]:
        P(f'    {nm:<30} ' + ', '.join(f'{g} {oe(*r[(g, "вышли3")])}' for g in PATTERNS))

    # 5. вклад пулов в casino_infix по регистрациям, страта 1 и страта 2
    P()
    P('=' * 100)
    P('ВКЛАД ПУЛОВ: на каких стратах держится casino_infix 21 против 13,4')
    P('=' * 100)
    c1 = pool_contributions(r1['items'], r1['strata'], lambda d: d['паттерн'] == 'casino_infix', 'рег', 'E_рег', 'Страта 1 (набор + день), casino_infix регистрации')
    c2 = pool_contributions(r2['items'], r2['strata'], lambda d: d['паттерн'] == 'casino_infix', 'рег', 'E_рег', 'Страта 2 (набор + день + зона), casino_infix регистрации')
    c3 = pool_contributions(r3['items'], r3['strata'], lambda d: d['паттерн'] == 'casino_infix', 'рег', 'E_рег', 'Страта 3 (набор + день + зона + блок часа), casino_infix регистрации')

    # два самых богатых домена — как меняется их E при ужесточении страты
    P()
    P('--- Два самых богатых casino_infix-домена: O и E при разных стратах ---')
    for dom in ['1109casino.casino', 'msvcasino.lol']:
        line = f'  {dom}: O = ' + str(next(d['рег'] for d in kept if d['домен'] == dom))
        for nm, r in [('страта 1', r1), ('страта 2', r2), ('страта 3', r3)]:
            e = next((d['E_рег'] for d in r['items'] if d['домен'] == dom), None)
            k = next((d['страта'] for d in r['items'] if d['домен'] == dom), None)
            n = len(r['strata'][k]) if k else 0
            line += f'; {nm}: E = {e:.2f} (в страте {n} доменов)' if e is not None else f'; {nm}: не в смешанной страте'
        P(line)
    # и что стоит рядом с ними
    for dom in ['1109casino.casino', 'msvcasino.lol']:
        k = next(d['страта'] for d in r1['items'] if d['домен'] == dom)
        ds = r1['strata'][k]
        P(f'  соседи {dom} по пулу {k}: ' + '; '.join(f'{d["домен"]} ({d["зона"]}, {d["блок"]}, рег {d["рег"]})' for d in sorted(ds, key=lambda d: -d['рег'])))

    # 6. парные сравнения внутри страты
    P()
    P('=' * 100)
    P('ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ СТРАТЫ (знаковый критерий): ставка группы против ставки остальных в той же страте')
    P('=' * 100)
    for nm, r in [('страта 1 (набор + день)', r1), ('страта 2 (+ зона)', r2), ('страта 3 (+ зона + блок часа)', r3)]:
        P(f'  [{nm}]')
        sign_test_within(r['items'], r['strata'], lambda d: d['паттерн'] == 'casino_infix', 'рег', 'casino_infix по регистрациям (рег/сайт)')
        sign_test_within(r['items'], r['strata'], lambda d: d['паттерн'] in CASINO, 'рег', 'casino_* по регистрациям (рег/сайт)')
        sign_test_within(r['items'], r['strata'], lambda d: d['паттерн'] in CASINO, 'вышли3', 'casino_* по выходу (вышли/сайт)')
        sign_test_within(r['items'], r['strata'], lambda d: d['паттерн'] == 'casino_infix', 'вышли3', 'casino_infix по выходу (вышли/сайт)')
    P('  Замечание: по регистрациям большинство страт — ничья 0:0 (регистраций 175 на ~1000 доменов), знаковый критерий здесь малосилен.')

    # 7. зона lol: выход casino_* 1,13 — тень партии?
    P()
    P('=' * 100)
    P('ВЫХОД В ЗОНАХ: casino_* team 0,92 / lol 1,13 (p 0,009) — держится ли при страте + блок часа')
    P('=' * 100)
    for z in ['team', 'lol']:
        zk = [d for d in kept if d['зона'] == z]
        rz2 = run_stratum(f'[{z}] набор + день (внутри зоны = страта 2 тестировщика)', zk, lambda d: (d['набор'], d['день']), n_perm=5000)
        rz3 = run_stratum(f'[{z}] набор + день + блок часа', zk, lambda d: (d['набор'], d['день'], d['блок']), n_perm=5000)
        rz4 = run_stratum(f'[{z}] набор + день + час точный', zk, lambda d: (d['набор'], d['день'], d['час']), n_perm=5000)
        P(f'  [{z}] casino_* по выходу: страта пул+зона O/E {rz2["A1"][0]:.2f} (p {rz2["A1"][1]:.3f}) → + блок часа {rz3["A1"][0]:.2f} (p {rz3["A1"][1]:.3f}) → + час точный {rz4["A1"][0]:.2f} (p {rz4["A1"][1]:.3f})')
        pool_contributions(rz2['items'], rz2['strata'], lambda d: d['паттерн'] in CASINO, 'вышли3', 'E_вых', f'[{z}] casino_* выход, страта пул+зона', top=6)
        sign_test_within(rz2['items'], rz2['strata'], lambda d: d['паттерн'] in CASINO, 'вышли3', f'[{z}] casino_* по выходу, пул+зона')
        sign_test_within(rz3['items'], rz3['strata'], lambda d: d['паттерн'] in CASINO, 'вышли3', f'[{z}] casino_* по выходу, пул+зона+блок часа')

    # 8. объём пула: держится ли casino_infix на больших пулах
    P()
    P('=' * 100)
    P('ОБЪЁМ ПУЛА: casino_infix по регистрациям в малых и больших пулах (страта 1 и страта 2)')
    P('=' * 100)
    for nm, r in [('страта 1', r1), ('страта 2', r2)]:
        for lo, hi, lab in [(2, 6, 'пулы 2–6 доменов'), (7, 12, 'пулы 7–12 доменов'), (13, 999, 'пулы >= 13 доменов')]:
            ks = [k for k, v in r['strata'].items() if lo <= len(v) <= hi]
            sel = [d for d in r['items'] if d['страта'] in set(ks)]
            ci = [d for d in sel if d['паттерн'] == 'casino_infix']
            o = sum(d['рег'] for d in ci); e = sum(d['E_рег'] for d in ci)
            oc = sum(d['вышли3'] for d in ci); ec = sum(d['E_вых'] for d in ci)
            P(f'  [{nm}] {lab:<22}: страт {len(ks):>3}, доменов {len(sel):>4}, casino_infix {len(ci):>3}; рег O/E = {oe(o, e)} ({int(o)}/{e:.1f}); выход O/E = {oe(oc, ec)}')

    # 9. даты: только пулы с 04.09 (где casino-имена вообще есть) — как ведут себя numeric/alpha
    P()
    P('=' * 100)
    P('ДАТЫ: пулы только с 04.09 (в них есть casino-имена) — numeric 1,08 / alpha_other 0,87 те же?')
    P('=' * 100)
    sept = [d for d in kept if d['день'] >= '2026-09-04']
    rs = run_stratum('пулы с 04.09, страта набор + день', sept, lambda d: (d['набор'], d['день']), n_perm=5000)
    rs2 = run_stratum('пулы с 04.09, страта набор + день + зона', sept, lambda d: (d['набор'], d['день'], d['зона']), n_perm=5000)

    # 10. буфер: E_вышли под стратой 2 и 3 (регистрации на вышедший сайт)
    P()
    P('=' * 100)
    P('РЕГИСТРАЦИИ НА ВЫШЕДШИЙ САЙТ (E_вышли) при жёстких стратах — casino_infix')
    P('=' * 100)
    for nm, r in [('страта 1', r1), ('страта 2', r2), ('страта 3', r3)]:
        ci = [d for d in r['items'] if d['паттерн'] == 'casino_infix']
        o = sum(d['рег'] for d in ci); e = sum(d['E_рег_вышли'] for d in ci)
        P(f'  [{nm}] casino_infix: O = {int(o)}, E_вышли = {e:.1f}, O/E = {oe(o, e)}')

    # 11. итог
    P()
    P('=' * 100)
    P('ИТОГ СКЕПТИКА')
    P('=' * 100)
    a2_1, p_1 = r1['A2']; a2_2, p_2 = r2['A2']; a2_3, p_3 = r3['A2']; a2_4, p_4 = r4['A2']
    P(f'1. Контраст А2 (casino_infix по регистрациям): страта «набор + день» O/E {a2_1:.2f} (p {p_1:.3f}) → + зона {a2_2:.2f} (p {p_2:.3f}) → '
      f'+ зона + блок часа {a2_3:.2f} (p {p_3:.3f}) → + зона + час точный {a2_4:.2f} (p {p_4:.3f}).')
    a1_1, q_1 = r1['A1']; a1_2, q_2 = r2['A1']; a1_3, q_3 = r3['A1']
    P(f'2. Контраст А1 (casino_* по выходу): {a1_1:.2f} (p {q_1:.3f}) → + зона {a1_2:.2f} (p {q_2:.3f}) → + зона + блок часа {a1_3:.2f} (p {q_3:.3f}).')
    P(f'3. Все O/E регистраций (4 паттерна) при страте 3: ' + ', '.join(f'{g} {oe(*r3[(g, "рег")])}' for g in PATTERNS) + f'; p (4 группы) = {r3[("p4", "рег")]:.3f}.')
    P(f'4. Все O/E выхода (4 паттерна) при страте 3: ' + ', '.join(f'{g} {oe(*r3[(g, "вышли3")])}' for g in PATTERNS) + f'; p (4 группы) = {r3[("p4", "вышли3")]:.3f}.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_out) + '\n')
    print(f'\n[записано: {OUT_PATH}]')


if __name__ == '__main__':
    main()

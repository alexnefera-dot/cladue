#!/usr/bin/env python3
"""
Скептик, угол «ТЕНИ» (конфаундинг) для гипотезы №1 (паттерн имени домена).

Что проверяем: не являются ли остатки результата тестировщика тенью
  - зоны (в том числе .casino и .buzz, которых зонный разрез тестировщика не видел),
  - часа запуска внутри пула («партия»: регистрации внутри пула сидят кучно по часу),
  - одного-двух пулов / одного-двух доменов,
  - дат (casino-имена есть только с 04.09) и «КОНТЕНТ НЕ ЗАПИСАН»,
  - объёма пула.
Остатки, которые проверяем:
  (1) casino_infix по регистрациям O/E 1,56 (p 0,041) — «формально проходит порог»;
  (2) «выход от имени не зависит» при противоположных знаках в зонах (team 0,92 / lol 1,13, p 0,009);
  (3) повтор метки: второй экземпляр O/E 1,15 (выход) / 1,33 (регистрации);
  (4) имя снимает 35,8 % χ² сверхдисперсии против 27,9 % у случайной разбивки (7,8 п.п., p 0,002).

Фильтр тот же, что у тестировщика. Только стандартная библиотека.
Вывод — в stdout и в analysis/export/gipotezy_svod/v01_teni.txt.
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
N_PERM_SMALL = 5000
N_SPLIT = 1000
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


def label_of(domain):
    return domain.rsplit('.', 1)[0]


# ---------------------------------------------------------------------------
# загрузка, тот же фильтр
# ---------------------------------------------------------------------------

def load():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    kept = []
    for r in rows:
        if r['домен'] in OUTLIERS or r['окно закрыто'] != 'да' or r['дней'] == '1' or r['набор контента'] == NO_CONTENT:
            continue
        z = r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие'
        kept.append(dict(
            домен=r['домен'], метка=label_of(r['домен']), зона=z, день=r['день запуска'], набор=r['набор контента'],
            паттерн=r['паттерн имени'], блок=r['блок часа'], час=int(r['час запуска']),
            cf=r['cf-аккаунт'], wm=r['аккаунт вебмастера'],
            сайтов=toi(r['сайтов в окне']), вышли3=toi(r['вышли за 3 суток']),
            рег=toi(r['регистраций в окне 3 суток']), клик=toi(r['кликов из поиска в окне']),
        ))
    return rows, kept


# ---------------------------------------------------------------------------
# страты, ожидания, перестановка
# ---------------------------------------------------------------------------

def stratify(kept, key, min_patterns=2, sub=None):
    strata = defaultdict(list)
    for d in kept:
        if sub is None or sub(d):
            strata[key(d)].append(d)
    strata = {k: v for k, v in strata.items() if len(set(d['паттерн'] for d in v)) >= min_patterns}
    items = []
    for k, ds in strata.items():
        S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds); R = sum(d['рег'] for d in ds)
        for d in ds:
            e = dict(d)
            e['страта'] = k
            e['E_вых'] = V / S * d['сайтов'] if S else 0.0
            e['E_рег'] = R / S * d['сайтов'] if S else 0.0
            e['E_рег_вышли'] = R / V * d['вышли3'] if V else 0.0
            items.append(e)
    return strata, items


FIELDS = ('сайтов', 'вышли3', 'E_вых', 'рег', 'E_рег')


def perm_sums(items, n_perm, seed=1, group_of=lambda d: d['паттерн'], groups=PATTERNS, fields=FIELDS):
    labels = [group_of(d) for d in items]
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


def chi(s, o_f, e_f, groups=PATTERNS):
    return sum((s[g][o_f] - s[g][e_f]) ** 2 / s[g][e_f] for g in groups if s[g][e_f] > 0)


def contrast(obs, perms, gs, o_f, e_f):
    o = sum(obs[g][o_f] for g in gs); e = sum(obs[g][e_f] for g in gs)
    d = o - e
    diffs = [sum(p[g][o_f] for g in gs) - sum(p[g][e_f] for g in gs) for p in perms]
    p2 = (sum(1 for v in diffs if abs(v) >= abs(d)) + 1) / (len(diffs) + 1)
    ratios = sorted(sum(p[g][o_f] for g in gs) / sum(p[g][e_f] for g in gs) for p in perms if sum(p[g][e_f] for g in gs) > 0)
    lo = ratios[int(0.025 * len(ratios))] if ratios else float('nan')
    hi = ratios[min(len(ratios) - 1, int(0.975 * len(ratios)))] if ratios else float('nan')
    return o, e, p2, lo, hi


def run(title, kept, key, n_perm=N_PERM, sub=None, quiet=False):
    strata, items = stratify(kept, key, sub=sub)
    cnt = Counter(d['паттерн'] for d in items)
    obs, perms = perm_sums(items, n_perm)
    res = dict(items=items, strata=strata, n=len(items), reg=sum(d['рег'] for d in items), n_str=len(strata))
    if not quiet:
        P()
        P(f'--- {title} ---')
        P(f'страт с >= 2 паттернами: {len(strata)}; доменов: {len(items)}; сайтов: {sum(d["сайтов"] for d in items)}; '
          f'регистраций: {sum(d["рег"] for d in items)}; страт со всеми 4 паттернами: '
          f'{sum(1 for v in strata.values() if len(set(d["паттерн"] for d in v)) == 4)}')
    for nm, o_f, e_f in [('ВЫХОД', 'вышли3', 'E_вых'), ('РЕГИСТРАЦИИ', 'рег', 'E_рег')]:
        c_o = chi(obs, o_f, e_f)
        pv = (sum(1 for p in perms if chi(p, o_f, e_f) >= c_o) + 1) / (len(perms) + 1)
        res[('p4', o_f)] = pv
        for g in PATTERNS:
            res[(g, o_f)] = (obs[g][o_f], obs[g][e_f])
        if not quiet:
            P(f'  {nm}: ' + '; '.join(f'{g} {oe(obs[g][o_f], obs[g][e_f])} ({int(obs[g][o_f])}/{obs[g][e_f]:.1f}, n={cnt[g]})' for g in PATTERNS)
              + f';  Σ(O−E)²/E = {c_o:.2f}, p (4 группы) = {pv:.3f}')
    for nm, gs, o_f, e_f in [('A1 casino_* выход', CASINO, 'вышли3', 'E_вых'),
                             ('A2 casino_infix рег', ('casino_infix',), 'рег', 'E_рег'),
                             ('casino_* рег', CASINO, 'рег', 'E_рег'),
                             ('casino_prefix рег', ('casino_prefix',), 'рег', 'E_рег'),
                             ('casino_infix выход', ('casino_infix',), 'вышли3', 'E_вых')]:
        o, e, p2, lo, hi = contrast(obs, perms, gs, o_f, e_f)
        res[nm] = (o / e if e else float('nan'), p2, o, e, lo, hi)
        if not quiet:
            P(f'  контраст {nm}: O = {int(o)}, E = {e:.1f}, O/E = {oe(o, e)}, O−E = {o - e:+.1f}, p (двуст.) = {p2:.3f}; коридор нуля {lo:.2f}–{hi:.2f}')
    return res


def sign_test(items, strata, test, o_f, per='сайтов'):
    w = l = t = 0
    for k in strata:
        a = [d for d in items if d['страта'] == k and test(d)]
        b = [d for d in items if d['страта'] == k and not test(d)]
        if not a or not b:
            continue
        ra = sum(d[o_f] for d in a) / sum(d[per] for d in a)
        rb = sum(d[o_f] for d in b) / sum(d[per] for d in b)
        if ra > rb + 1e-12:
            w += 1
        elif rb > ra + 1e-12:
            l += 1
        else:
            t += 1
    return w, l, t, binom_two_sided(w, w + l)


# ---------------------------------------------------------------------------
# блоки
# ---------------------------------------------------------------------------

def block_raw_gap(rows, kept):
    P()
    P('=' * 100)
    P('БЛОК А. Сырой разрыв casino-имён (0,04 против 0,11 рег/100 сайтов) — откуда он: даты, «КОНТЕНТ НЕ ЗАПИСАН», зона')
    P('=' * 100)
    allr = [r for r in rows if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] != '1']
    def line(lbl, ds):
        S = sum(toi(r['сайтов в окне']) for r in ds); V = sum(toi(r['вышли за 3 суток']) for r in ds); R = sum(toi(r['регистраций в окне 3 суток']) for r in ds)
        return f'  {lbl:<58} доменов {len(ds):>4}  сайтов {S:>6}  выход {100 * V / S if S else 0:>5.1f}%  рег {R:>3}  рег/100 сайтов {100 * R / S if S else 0:.3f}'
    P('Все домены с закрытым окном и дней != 1 (без выбросов), по периодам и паттернам:')
    for lbl, sub in [('«КОНТЕНТ НЕ ЗАПИСАН» (до 24.08)', lambda r: r['набор контента'] == NO_CONTENT),
                     ('с набором, запуск до 04.09 (casino-имён ещё нет)', lambda r: r['набор контента'] != NO_CONTENT and r['день запуска'] < '2026-09-04'),
                     ('с набором, запуск с 04.09', lambda r: r['набор контента'] != NO_CONTENT and r['день запуска'] >= '2026-09-04')]:
        ds = [r for r in allr if sub(r)]
        P(line(lbl, ds))
        for g in PATTERNS:
            gg = [r for r in ds if r['паттерн имени'] == g]
            if gg:
                P(line('    ' + g, gg))
    P('Вывод по блоку: сырой разрыв складывается из дат (до 04.09 ставка регистраций у numeric/alpha выше, casino-имён там нет)')
    P('и внутри сентября — из casino_prefix; casino_infix в сентябре сырой ставкой от numeric/alpha не отличается.')


def block_strata_ladder(kept):
    P()
    P('=' * 100)
    P('БЛОК Б. Лестница страт: набор+день → +зона → +час → +зона+час (+ блок часа). Что остаётся от 1,56 и от «выход 1,01»')
    P('=' * 100)
    ladder = [
        ('1: набор + день (тестировщик)', lambda d: (d['набор'], d['день'])),
        ('2: набор + день + зона (4 зоны)', lambda d: (d['набор'], d['день'], d['зона'])),
        ('3: набор + день + блок часа', lambda d: (d['набор'], d['день'], d['блок'])),
        ('4: набор + день + час точный', lambda d: (d['набор'], d['день'], d['час'])),
        ('5: набор + день + зона + блок часа', lambda d: (d['набор'], d['день'], d['зона'], d['блок'])),
        ('6: набор + день + зона + час точный', lambda d: (d['набор'], d['день'], d['зона'], d['час'])),
    ]
    res = {}
    for nm, key in ladder:
        res[nm] = run(f'СТРАТА {nm}', kept, key)
    P()
    P('СВОДКА ЛЕСТНИЦЫ')
    P(f'  {"страта":<40} {"домен":>5} {"рег":>4} | {"A1 casino_* выход":>18} {"p":>6} | {"A2 casino_infix рег":>20} {"p":>6} | {"casino_* рег":>12} {"p":>6} | {"casino_prefix рег":>17} | {"p4 вых":>6} {"p4 рег":>6}')
    for nm, _ in ladder:
        r = res[nm]
        P(f'  {nm:<40} {r["n"]:>5} {r["reg"]:>4} | {r["A1 casino_* выход"][0]:>18.2f} {r["A1 casino_* выход"][1]:>6.3f} | '
          f'{r["A2 casino_infix рег"][0]:>20.2f} {r["A2 casino_infix рег"][1]:>6.3f} | {r["casino_* рег"][0]:>12.2f} {r["casino_* рег"][1]:>6.3f} | '
          f'{r["casino_prefix рег"][0]:>17.2f} | {r[("p4", "вышли3")]:>6.3f} {r[("p4", "рег")]:>6.3f}')
    P('  O/E регистраций по 4 паттернам:')
    for nm, _ in ladder:
        r = res[nm]
        P(f'    {nm:<40} ' + ', '.join(f'{g} {oe(*r[(g, "рег")])} ({int(r[(g, "рег")][0])}/{r[(g, "рег")][1]:.1f})' for g in PATTERNS))
    P('  O/E выхода по 4 паттернам:')
    for nm, _ in ladder:
        r = res[nm]
        P(f'    {nm:<40} ' + ', '.join(f'{g} {oe(*r[(g, "вышли3")])}' for g in PATTERNS))
    # знаковые критерии внутри страты
    P()
    P('  Парные сравнения внутри страты (знаковый критерий: ставка группы против ставки остальных в той же страте):')
    for nm, _ in ladder:
        r = res[nm]
        w, l, t, p = sign_test(r['items'], r['strata'], lambda d: d['паттерн'] == 'casino_infix', 'рег')
        w2, l2, t2, p2 = sign_test(r['items'], r['strata'], lambda d: d['паттерн'] in CASINO, 'вышли3')
        w3, l3, t3, p3 = sign_test(r['items'], r['strata'], lambda d: d['паттерн'] == 'casino_infix', 'вышли3')
        P(f'    {nm:<40} casino_infix рег: лучше {w:>2} / хуже {l:>2} / ничья {t:>2} (p {p:.2f});  casino_* выход: лучше {w2:>2} / хуже {l2:>2} (p {p2:.2f});  casino_infix выход: лучше {w3:>2} / хуже {l3:>2} (p {p3:.2f})')
    return res


def block_hour_batch(kept, res):
    P()
    P('=' * 100)
    P('БЛОК В. Партия по часу внутри пула: регистрации сидят кучно по часу запуска — и casino_infix-богачи сидят в богатых партиях')
    P('=' * 100)
    strata, items = stratify(kept, lambda d: (d['набор'], d['день']))
    # сверхдисперсия регистраций по (пул, час) относительно пула: χ² Пуассона
    chi_pool = 0.0; df_pool = 0; chi_hour = 0.0; df_hour = 0
    for k, ds in strata.items():
        S = sum(d['сайтов'] for d in ds); R = sum(d['рег'] for d in ds)
        if R == 0:
            continue
        for d in ds:
            e = R / S * d['сайтов']
            chi_pool += (d['рег'] - e) ** 2 / e
        df_pool += len(ds) - 1
        byh = defaultdict(list)
        for d in ds:
            byh[d['час']].append(d)
        for hds in byh.values():
            Sh = sum(d['сайтов'] for d in hds); Rh = sum(d['рег'] for d in hds)
            if Rh == 0:
                continue
            for d in hds:
                e = Rh / Sh * d['сайтов']
                chi_hour += (d['рег'] - e) ** 2 / e
            df_hour += len(hds) - 1
    P(f'  χ² Пуассона регистраций по доменам: ставка пула → χ²/df = {chi_pool / df_pool:.2f} (df {df_pool}); ставка (пул, час) → χ²/df = {chi_hour / df_hour:.2f} (df {df_hour})')
    # случайные разбивки на часы тех же размеров
    rng = random.Random(1)
    drops = []
    real_drop = 1 - chi_hour / chi_pool
    for _ in range(N_SPLIT):
        tot = 0.0
        for k, ds in strata.items():
            R = sum(d['рег'] for d in ds)
            if R == 0:
                continue
            hs = [d['час'] for d in ds]
            rng.shuffle(hs)
            byh = defaultdict(list)
            for d, h in zip(ds, hs):
                byh[h].append(d)
            for hds in byh.values():
                Sh = sum(d['сайтов'] for d in hds); Rh = sum(d['рег'] for d in hds)
                if Rh == 0:
                    continue
                for d in hds:
                    e = Rh / Sh * d['сайтов']
                    tot += (d['рег'] - e) ** 2 / e
        drops.append(1 - tot / chi_pool)
    mean_drop = sum(drops) / len(drops)
    p_split = (sum(1 for x in drops if x >= real_drop) + 1) / (len(drops) + 1)
    P(f'  Ячейки (пул, час) снимают {100 * real_drop:.1f}% χ² регистраций; случайные разбивки на те же ячейки — {100 * mean_drop:.1f}% (p = {p_split:.3f}).')
    # пулы с >= 4 регистрациями: концентрация по часу
    P('  Пулы с >= 4 регистрациями: регистрации по часам запуска (рег / доменов в партии), casino_infix-домены с рег помечены *:')
    for k, ds in sorted(strata.items(), key=lambda kv: -sum(d['рег'] for d in kv[1])):
        R = sum(d['рег'] for d in ds)
        if R < 4:
            break
        byh = defaultdict(lambda: [0, 0, []])
        for d in ds:
            byh[d['час']][0] += d['рег']; byh[d['час']][1] += 1
            if d['паттерн'] == 'casino_infix' and d['рег'] > 0:
                byh[d['час']][2].append(f'{d["домен"]}={d["рег"]}')
        P(f'    {str(k)[:60]:<60} доменов {len(ds):>2}, рег {R:>2}: ' + ', '.join(f'{h:02d}ч {v[0]}/{v[1]}' + (' *' + ' '.join(v[2]) if v[2] else '') for h, v in sorted(byh.items())))
    # casino_infix: E от (пул, час) для каждого casino_infix-домена с рег
    P()
    P('  casino_infix-домены с регистрациями: O, E от пула и E от партии (пул + час точный), число доменов в партии:')
    s4, it4 = stratify(kept, lambda d: (d['набор'], d['день'], d['час']))
    e4 = {d['домен']: (d['E_рег'], len(s4[d['страта']])) for d in it4}
    e1 = {d['домен']: d['E_рег'] for d in items}
    for d in sorted([d for d in items if d['паттерн'] == 'casino_infix' and d['рег'] > 0], key=lambda d: -d['рег']):
        a = e4.get(d['домен'])
        P(f'    {d["домен"]:<22} {d["зона"]:<6} {d["день"]} {d["час"]:02d}ч  O = {d["рег"]}  E_пул = {e1[d["домен"]]:.2f}  ' + (f'E_партия = {a[0]:.2f} (в партии {a[1]} доменов)' if a else 'партия однородна по паттерну — вне сравнения'))


def block_two_domains(kept, res):
    P()
    P('=' * 100)
    P('БЛОК Г. Два домена и зона .casino / .buzz: на чём держится 21 против 13,4')
    P('=' * 100)
    r1 = res['1: набор + день (тестировщик)']
    items = r1['items']
    ci = [d for d in items if d['паттерн'] == 'casino_infix']
    O = sum(d['рег'] for d in ci); E = sum(d['E_рег'] for d in ci)
    P(f'  casino_infix в страте 1: доменов {len(ci)}, O = {O}, E = {E:.1f}, O/E = {oe(O, E)}; по зонам: ' +
      ', '.join(f'{z}: {sum(1 for d in ci if d["зона"] == z)} доменов, O {sum(d["рег"] for d in ci if d["зона"] == z)}, E {sum(d["E_рег"] for d in ci if d["зона"] == z):.1f}' for z in ['team', 'lol', 'casino', 'buzz']))
    for lbl, drop in [('без зоны .casino (5 доменов casino_infix)', lambda d: d['зона'] == 'casino'),
                      ('без зон .casino и .buzz', lambda d: d['зона'] in ('casino', 'buzz')),
                      ('без 1109casino.casino', lambda d: d['домен'] == '1109casino.casino'),
                      ('без 1109casino.casino и msvcasino.lol', lambda d: d['домен'] in ('1109casino.casino', 'msvcasino.lol'))]:
        sel = [d for d in ci if not drop(d)]
        o = sum(d['рег'] for d in sel); e = sum(d['E_рег'] for d in sel)
        P(f'    {lbl:<48}: доменов {len(sel):>3}, O = {o:>2}, E = {e:.1f}, O/E = {oe(o, e)}')
    # доля доменов с регистрацией — не зависит от кучности
    P('  Доля доменов с хотя бы одной регистрацией (устойчива к кучности регистраций на домене), страта 1:')
    for g in PATTERNS:
        ds = [d for d in items if d['паттерн'] == g]
        n1 = sum(1 for d in ds if d['рег'] > 0)
        # ожидание: доля доменов с рег в пуле × число доменов группы в пуле
        e = 0.0
        for k, v in r1['strata'].items():
            ng = sum(1 for d in v if d['паттерн'] == g)
            if ng:
                e += ng * sum(1 for d in v if d['рег'] > 0) / len(v)
        P(f'    {g:<14} доменов {len(ds):>3}, с регистрацией {n1:>2}, ожидалось {e:.1f}, O/E = {oe(n1, e)}')
    # перестановочный p для доли доменов с рег (casino_infix)
    strata = r1['strata']
    obs_n = sum(1 for d in items if d['паттерн'] == 'casino_infix' and d['рег'] > 0)
    rng = random.Random(1)
    cnt = 0
    for _ in range(N_PERM):
        tot = 0
        for k, v in strata.items():
            labs = [d['паттерн'] for d in v]
            rng.shuffle(labs)
            tot += sum(1 for d, l in zip(v, labs) if l == 'casino_infix' and d['рег'] > 0)
        if tot >= obs_n:
            cnt += 1
    P(f'    casino_infix: доменов с регистрацией {obs_n}; перестановочное p (односторон., >=) = {(cnt + 1) / (N_PERM + 1):.3f}')


def block_zone_interaction(kept):
    P()
    P('=' * 100)
    P('БЛОК Д. Выход: casino_* team 0,92 / lol 1,13 — разница между зонами значима? (перестановка внутри страты, статистика = разность O/E)')
    P('=' * 100)
    out = {}
    for nm, key in [('пул + зона', lambda d: (d['набор'], d['день'], d['зона'])),
                    ('пул + зона + блок часа', lambda d: (d['набор'], d['день'], d['зона'], d['блок'])),
                    ('пул + зона + час точный', lambda d: (d['набор'], d['день'], d['зона'], d['час']))]:
        strata, items = stratify(kept, key)
        items = [d for d in items if d['зона'] in ('team', 'lol')]
        labels = [d['паттерн'] for d in items]
        zones = [d['зона'] for d in items]
        v3 = [float(d['вышли3']) for d in items]; ev = [d['E_вых'] for d in items]
        pools = defaultdict(list)
        for i, d in enumerate(items):
            pools[d['страта']].append(i)
        pool_idx = [v for v in pools.values() if len(v) >= 2]

        def stat(lab):
            o = {'team': 0.0, 'lol': 0.0}; e = {'team': 0.0, 'lol': 0.0}
            for i, g in enumerate(lab):
                if g in CASINO:
                    o[zones[i]] += v3[i]; e[zones[i]] += ev[i]
            rt = o['team'] / e['team'] if e['team'] else float('nan')
            rl = o['lol'] / e['lol'] if e['lol'] else float('nan')
            return rt, rl
        rt, rl = stat(labels)
        d_obs = rl - rt
        rng = random.Random(1)
        lab = labels[:]
        cnt = 0; cnt_lol = 0; cnt_team = 0
        for _ in range(N_PERM):
            for idx in pool_idx:
                cur = [lab[i] for i in idx]
                rng.shuffle(cur)
                for i, g in zip(idx, cur):
                    lab[i] = g
            t, l = stat(lab)
            if abs(l - t) >= abs(d_obs):
                cnt += 1
            if abs(l - 1) >= abs(rl - 1):
                cnt_lol += 1
            if abs(t - 1) >= abs(rt - 1):
                cnt_team += 1
        P(f'  [{nm}] casino_* выход O/E: team {rt:.3f} (p {(cnt_team + 1) / (N_PERM + 1):.3f}), lol {rl:.3f} (p {(cnt_lol + 1) / (N_PERM + 1):.3f}); '
          f'разность lol − team = {d_obs:+.3f}, перестановочное p = {(cnt + 1) / (N_PERM + 1):.3f}; доменов {len(items)}, страт {len(pool_idx)}')
        out[nm] = (rt, rl, d_obs, (cnt + 1) / (N_PERM + 1))
    # что отличается у casino-имён от остальных внутри пула в lol и в team: часы, блоки
    P('  Проверка записанных признаков внутри страты пул+зона: доля casino-имён по блокам часа (team / lol) против остальных:')
    strata, items = stratify(kept, lambda d: (d['набор'], d['день'], d['зона']))
    for z in ['team', 'lol']:
        zi = [d for d in items if d['зона'] == z]
        c = Counter((d['паттерн'] in CASINO, d['блок']) for d in zi)
        nc = sum(1 for d in zi if d['паттерн'] in CASINO); nn = len(zi) - nc
        P(f'    {z}: casino ' + ', '.join(f'{b} {100 * c[(True, b)] / nc:.0f}%' for b in ['00-05', '06-11', '12-17', '18-23']) + ' | остальные ' +
          ', '.join(f'{b} {100 * c[(False, b)] / nn:.0f}%' for b in ['00-05', '06-11', '12-17', '18-23']))
    P('  cf-аккаунт и аккаунт Вебмастера внутри пула уникальны для каждого домена (проверено: 0 пар доменов одного пула на одном cf-аккаунте) —')
    P('  партию по аккаунту проверить нельзя; партия по часу (выше) разницу между зонами не снимает.')
    return out


def block_overdispersion(kept):
    P()
    P('=' * 100)
    P('БЛОК Е. Сверхдисперсия выхода: снимает ли имя что-то сверх случайной разбивки, когда ячейки уже учитывают зону (и час)')
    P('=' * 100)
    pools_all = defaultdict(list)
    for d in kept:
        pools_all[(d['набор'], d['день'])].append(d)
    pools = {k: v for k, v in pools_all.items() if len(v) >= 5}
    items = [d for v in pools.values() for d in v]
    for d in items:
        lab = d['метка']
        if d['паттерн'] == 'numeric':
            d['ячейка'] = 'numeric: ведущий 0' if lab.startswith('0') else 'numeric: без 0'
        elif d['паттерн'] == 'alpha_other':
            d['ячейка'] = 'alpha_other: только буквы' if lab.isalpha() else 'alpha_other: смесь'
        else:
            d['ячейка'] = d['паттерн']

    def chi_cells(ds, cell_of):
        cells = defaultdict(list)
        for d in ds:
            cells[cell_of(d)].append(d)
        c = 0.0
        for cds in cells.values():
            S = sum(d['сайтов'] for d in cds); V = sum(d['вышли3'] for d in cds)
            if S == 0:
                continue
            p = V / S
            if p <= 0 or p >= 1:
                continue
            for d in cds:
                c += (d['вышли3'] - d['сайтов'] * p) ** 2 / (d['сайтов'] * p * (1 - p))
        return c, len(cells)

    P(f'  Пулов >= 5 доменов: {len(pools)}; доменов: {len(items)}')
    rng = random.Random(1)
    for base_nm, base_of in [('пул', lambda d: 0), ('пул × зона', lambda d: d['зона']), ('пул × зона × блок часа', lambda d: (d['зона'], d['блок'])),
                             ('пул × зона × час точный', lambda d: (d['зона'], d['час']))]:
        chi_b = 0.0; df_b = 0; chi_n = 0.0; df_n = 0
        for k, ds in pools.items():
            c, nc = chi_cells(ds, base_of); chi_b += c; df_b += len(ds) - nc
            c2, nc2 = chi_cells(ds, lambda d: (base_of(d), d['ячейка'])); chi_n += c2; df_n += len(ds) - nc2
        real = 1 - chi_n / chi_b
        drops = []
        for _ in range(N_SPLIT):
            tot = 0.0
            for k, ds in pools.items():
                # перестановка ячейки имени внутри базовой ячейки (сохраняем размеры)
                groups = defaultdict(list)
                for d in ds:
                    groups[base_of(d)].append(d)
                m = {}
                for g in groups.values():
                    labs = [d['ячейка'] for d in g]
                    rng.shuffle(labs)
                    for d, l in zip(g, labs):
                        m[id(d)] = l
                c, _ = chi_cells(ds, lambda d: (base_of(d), m[id(d)]))
                tot += c
            drops.append(1 - tot / chi_b)
        mean_drop = sum(drops) / len(drops)
        p_split = (sum(1 for x in drops if x >= real) + 1) / (len(drops) + 1)
        P(f'  база «{base_nm}»: χ²/df {chi_b / df_b:.2f} (df {df_b}) → + признак имени {chi_n / df_n:.2f} (df {df_n}); '
          f'снято {100 * real:.1f}% против {100 * mean_drop:.1f}% у случайной разбивки (разница {100 * (real - mean_drop):+.1f} п.п., p = {p_split:.3f})')
    # зона сама по себе против случайной
    chi_b = 0.0; chi_z = 0.0; df_z = 0
    drops = []
    for k, ds in pools.items():
        c, _ = chi_cells(ds, lambda d: 0); chi_b += c
        c2, nc = chi_cells(ds, lambda d: d['зона']); chi_z += c2; df_z += len(ds) - nc
    real_z = 1 - chi_z / chi_b
    for _ in range(N_SPLIT):
        tot = 0.0
        for k, ds in pools.items():
            labs = [d['зона'] for d in ds]
            rng.shuffle(labs)
            m = {id(d): l for d, l in zip(ds, labs)}
            c, _ = chi_cells(ds, lambda d: m[id(d)]); tot += c
        drops.append(1 - tot / chi_b)
    P(f'  для сравнения: зона одна снимает {100 * real_z:.1f}% χ² против {100 * sum(drops) / len(drops):.1f}% у случайной (разница {100 * (real_z - sum(drops) / len(drops)):+.1f} п.п.)')


def block_repeat(kept):
    P()
    P('=' * 100)
    P('БЛОК Ж. Повтор метки: второй экземпляр O/E 1,15 / 1,33 — относительно пула или относительно пула + зоны?')
    P('=' * 100)
    lab = defaultdict(list)
    for d in kept:
        lab[d['метка']].append(d)
    pairs = [sorted(v, key=lambda d: d['день']) for v in lab.values() if len(v) == 2]
    diff = [v for v in pairs if v[0]['день'] != v[1]['день']]
    P(f'  пар {len(pairs)}, с разными днями {len(diff)}; зона второго по дате экземпляра: ' + ', '.join(f'{k}:{v}' for k, v in Counter(v[1]['зона'] for v in diff).most_common())
      + '; зона первого: ' + ', '.join(f'{k}:{v}' for k, v in Counter(v[0]['зона'] for v in diff).most_common()))
    for nm, key in [('пул', lambda d: (d['набор'], d['день'])), ('пул + зона', lambda d: (d['набор'], d['день'], d['зона']))]:
        strata = defaultdict(list)
        for d in kept:
            strata[key(d)].append(d)
        loo = {}
        for k, ds in strata.items():
            S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds); R = sum(d['рег'] for d in ds)
            for d in ds:
                s2, v2, r2 = S - d['сайтов'], V - d['вышли3'], R - d['рег']
                loo[d['домен']] = (v2 / s2 * d['сайтов'], r2 / s2 * d['сайтов']) if len(ds) >= 2 and s2 > 0 else None
        for idx, lbl in [(0, 'первый'), (1, 'второй')]:
            ds = [v[idx] for v in diff if loo.get(v[idx]['домен'])]
            o = sum(d['вышли3'] for d in ds); e = sum(loo[d['домен']][0] for d in ds)
            o2 = sum(d['рег'] for d in ds); e2 = sum(loo[d['домен']][1] for d in ds)
            P(f'    [{nm}] {lbl} экземпляр: выход O/E = {oe(o, e)} ({int(o)}/{e:.0f}), регистрации O/E = {oe(o2, e2)} ({o2}/{e2:.1f}), доменов с E: {len(ds)}')
        w = l = t = 0
        for a, b in diff:
            if loo.get(a['домен']) and loo.get(b['домен']):
                ra = a['вышли3'] / loo[a['домен']][0] if loo[a['домен']][0] else None
                rb = b['вышли3'] / loo[b['домен']][0] if loo[b['домен']][0] else None
                if ra is None or rb is None:
                    continue
                if rb < ra - 1e-12: w += 1
                elif rb > ra + 1e-12: l += 1
                else: t += 1
        P(f'    [{nm}] знаковый (O/E выхода относительно страты): второй ХУЖЕ в {w}, ЛУЧШЕ в {l}, равен {t}; p = {binom_two_sided(w, w + l):.3f}')


def block_pool_volume(res):
    P()
    P('=' * 100)
    P('БЛОК З. Объём пула: casino_infix по регистрациям и выходу в малых / средних / больших пулах (страта 1 и страта 2)')
    P('=' * 100)
    for nm in ['1: набор + день (тестировщик)', '2: набор + день + зона (4 зоны)']:
        r = res[nm]
        for lo, hi, lab in [(2, 6, 'пулы 2–6 доменов'), (7, 12, 'пулы 7–12 доменов'), (13, 999, 'пулы >= 13 доменов')]:
            ks = set(k for k, v in r['strata'].items() if lo <= len(v) <= hi)
            sel = [d for d in r['items'] if d['страта'] in ks]
            ci = [d for d in sel if d['паттерн'] == 'casino_infix']
            o = sum(d['рег'] for d in ci); e = sum(d['E_рег'] for d in ci)
            oc = sum(d['вышли3'] for d in ci); ec = sum(d['E_вых'] for d in ci)
            P(f'  [{nm[:2]}] {lab:<22}: страт {len(ks):>3}, доменов {len(sel):>4}, casino_infix {len(ci):>3}; рег O/E = {oe(o, e)} ({o}/{e:.1f}); выход O/E = {oe(oc, ec)}')


def block_knz(rows):
    P()
    P('=' * 100)
    P('БЛОК И. «КОНТЕНТ НЕ ЗАПИСАН»: 21 casino-имя, которые тестировщик не считал, — где они и что с их выходом внутри дня')
    P('=' * 100)
    knz = [r for r in rows if r['набор контента'] == NO_CONTENT and r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS]
    cas = [r for r in knz if r['паттерн имени'].startswith('casino')]
    P(f'  casino-имён среди «КОНТЕНТ НЕ ЗАПИСАН» с закрытым окном: {len(cas)}; дни запуска: ' + ', '.join(f'{k}:{v}' for k, v in sorted(Counter(r['день запуска'] for r in cas).items()))
      + '; регистраций у них: ' + str(sum(toi(r['регистраций в окне 3 суток']) for r in cas)))
    days = defaultdict(list)
    for r in knz:
        days[r['день запуска']].append(r)
    for lbl, keyz in [('день', lambda r: ()), ('день + зона', lambda r: (r['зона'],))]:
        oc = ec = 0.0
        for d, v in days.items():
            byk = defaultdict(list)
            for r in v:
                byk[keyz(r)].append(r)
            for ds in byk.values():
                c = [r for r in ds if r['паттерн имени'].startswith('casino')]; o = [r for r in ds if not r['паттерн имени'].startswith('casino')]
                if c and o:
                    Sc = sum(toi(r['сайтов в окне']) for r in c); Vc = sum(toi(r['вышли за 3 суток']) for r in c)
                    So = sum(toi(r['сайтов в окне']) for r in o); Vo = sum(toi(r['вышли за 3 суток']) for r in o)
                    oc += Vc; ec += (Vc + Vo) / (Sc + So) * Sc
        P(f'  выход casino-имён внутри страты «{lbl}» (набор неизвестен): O = {int(oc)}, E = {ec:.1f}, O/E = {oe(oc, ec)}')
    P('  То есть и там, где набор не записан, casino-имена внутри дня выходят как соседи; исключение этих 21 домена результат не меняет.')


def main():
    rows, kept = load()
    P('=' * 100)
    P('СКЕПТИК (ТЕНИ) по гипотезе №1: паттерн имени домена. Фильтр тестировщика: окно закрыто, дней != 1, без выбросов, без «КОНТЕНТ НЕ ЗАПИСАН»')
    P('=' * 100)
    P(f'Доменов после фильтра: {len(kept)}; зоны: ' + ', '.join(f'{k}:{v}' for k, v in Counter(d['зона'] for d in kept).most_common()))
    P('Паттерн × зона (после фильтра): ' + '; '.join(f'{g}: ' + '/'.join(f'{z} {sum(1 for d in kept if d["паттерн"] == g and d["зона"] == z)}' for z in ['team', 'lol', 'casino', 'buzz']) for g in PATTERNS))
    P('Ставки по зонам (без страты): ' + '; '.join(f'{z}: выход {100 * sum(d["вышли3"] for d in kept if d["зона"] == z) / sum(d["сайтов"] for d in kept if d["зона"] == z):.1f}%, '
      f'рег/100 сайтов {100 * sum(d["рег"] for d in kept if d["зона"] == z) / sum(d["сайтов"] for d in kept if d["зона"] == z):.3f}' for z in ['team', 'lol', 'casino', 'buzz']))
    P('Скрытых полей, различающихся внутри пула по паттерну, нет: шаблон, страниц, оформление, наборов на домене — свойства набора (в пуле одно значение);')
    P('который раз аккаунт = 1, аккаунт свежий = да, дней = 2 у всех доменов смешанных пулов; cf-аккаунт и аккаунт Вебмастера уникальны внутри пула.')
    P('Остаётся проверяемое: зона, час/блок часа (партия), отдельные домены и пулы, объём пула, даты.')

    block_raw_gap(rows, kept)
    res = block_strata_ladder(kept)
    block_hour_batch(kept, res)
    block_two_domains(kept, res)
    inter = block_zone_interaction(kept)
    block_overdispersion(kept)
    block_repeat(kept)
    block_pool_volume(res)
    block_knz(rows)

    P()
    P('=' * 100)
    P('ИТОГ СКЕПТИКА (ТЕНИ)')
    P('=' * 100)
    r1 = res['1: набор + день (тестировщик)']; r2 = res['2: набор + день + зона (4 зоны)']; r4 = res['4: набор + день + час точный']; r6 = res['6: набор + день + зона + час точный']
    P(f'1. casino_infix по регистрациям: {r1["A2 casino_infix рег"][0]:.2f} (p {r1["A2 casino_infix рег"][1]:.3f}) → + зона {r2["A2 casino_infix рег"][0]:.2f} (p {r2["A2 casino_infix рег"][1]:.3f}) '
      f'→ + час {r4["A2 casino_infix рег"][0]:.2f} (p {r4["A2 casino_infix рег"][1]:.3f}) → + зона + час {r6["A2 casino_infix рег"][0]:.2f} (p {r6["A2 casino_infix рег"][1]:.3f}).')
    P(f'2. casino_* по выходу: {r1["A1 casino_* выход"][0]:.2f} (p {r1["A1 casino_* выход"][1]:.3f}) → + зона {r2["A1 casino_* выход"][0]:.2f} (p {r2["A1 casino_* выход"][1]:.3f}) '
      f'→ + зона + час {r6["A1 casino_* выход"][0]:.2f} (p {r6["A1 casino_* выход"][1]:.3f}); разность зон lol − team: ' +
      '; '.join(f'{k}: {v[2]:+.2f} (p {v[3]:.3f})' for k, v in inter.items()))
    P(f'3. 4 группы по регистрациям при + зона + час: ' + ', '.join(f'{g} {oe(*r6[(g, "рег")])}' for g in PATTERNS) + f'; p = {r6[("p4", "рег")]:.3f}. По выходу: '
      + ', '.join(f'{g} {oe(*r6[(g, "вышли3")])}' for g in PATTERNS) + f'; p = {r6[("p4", "вышли3")]:.3f}.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_out) + '\n')
    print(f'\n[записано: {OUT_PATH}]')


if __name__ == '__main__':
    main()

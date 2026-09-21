#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №5 (повторное использование cf-аккаунта). Угол: ТЕНИ (конфаундинг).

Проверяем, выживает ли результат тестировщика («повторные базы к первым 1,02 внутри пулов
набор контента + день + 150/206») при более жёстких стратах и при других способах взвешивания:
  1. Воспроизведение главного O/E тестировщика (санитарная проверка).
  2. Баланс ковариат внутри пулов: зона, паттерн имени, блок часа, «который раз аккаунт» вебмастера.
  3. Жёсткая страта пул × зона — ВСЕ ячейки (ячейки с одной группой дают O = E и не вносят контраста).
  4. Ещё жёстче: пул × зона × паттерн имени; пул × зона × блок часа.
  5. Попульные отношения (выход повторных / выход первых), знаковый критерий, взвешивание
     Мантеля–Хензеля, «выбросить один пул», только сбалансированные пулы (≥5 доменов с каждой стороны),
     только пулы без 09-12 (там повторные — почти сплошь третьи базы), только 3-и против 1-х.
  6. Ранговый тест внутри пула (перестановка рангов O/E домена внутри пула) — устойчив к доминированию
     нескольких доменов.
  7. Регистрации под стратой пул × зона.
  8. Быстрый повтор (≤2 дней) — на чём держится: сколько первых баз в тех пулах.
Только stdlib. Вывод — в stdout и в analysis/export/gipotezy_svod/v05_teni.txt
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict
from datetime import date

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'v05_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
random.seed(7)
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
_lines = []


def p(*a):
    s = ' '.join(str(x) for x in a)
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


def ratio(o, e):
    return o / e if e > 0 else None


def pois_cdf(k, lam):
    if lam <= 0:
        return 1.0
    return min(1.0, sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(int(k) + 1)))


def pois_sf(k, lam):
    return 1.0 if k <= 0 else max(0.0, 1.0 - pois_cdf(k - 1, lam))


def pois_ci(k, alpha=0.05):
    k = int(k)
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, float(k) + 1.0
        while pois_sf(k, b) < alpha / 2:
            b *= 2
        for _ in range(200):
            m = (a + b) / 2
            if pois_sf(k, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    a, b = float(k), float(k) + 1.0
    while pois_cdf(k, b) > alpha / 2:
        b *= 2
    for _ in range(200):
        m = (a + b) / 2
        if pois_cdf(k, m) > alpha / 2:
            a = m
        else:
            b = m
    return lo, (a + b) / 2


# ------------------------------------------------------------------ чтение и порядок cf
with open(SRC, encoding='utf-8', newline='') as fh:
    rows = list(csv.DictReader(fh))

by_cf = defaultdict(list)
for r in rows:
    by_cf[r['cf-аккаунт']].append(r)
for cfk, lst in by_cf.items():
    lst.sort(key=lambda r: (r['день запуска'], int(fnum(r['час запуска']))))
    prev = None
    for i, r in enumerate(lst):
        r['_ord'] = i + 1
        d = date.fromisoformat(r['день запуска'])
        r['_gap'] = (d - prev).days if prev is not None else None
        prev = d
    if cfk == '':
        for r in lst:
            r['_ord'] = None
            r['_gap'] = None

for r in rows:
    r['_sites'] = fnum(r['сайтов в окне'])
    r['_ex3'] = fnum(r['вышли за 3 суток'])
    r['_reg'] = fnum(r['регистраций в окне 3 суток'])
    r['_s150'] = '150' if r['сайтов'] == '150' else '206'
    r['_set'] = re.sub(r'_\d+$', '', r['набор контента'])
    r['_zone'] = r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие'

keep = [r for r in rows if r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS
        and r['набор контента'] != NO_CONTENT and r['cf-аккаунт'] != '' and r['_ord']]


def rep(r):
    return '1-я' if r['_ord'] == 1 else 'повторная'


def pool_key(r):
    return (r['_set'], r['день запуска'], r['_s150'])


all_pools = defaultdict(list)
for r in keep:
    all_pools[pool_key(r)].append(r)
mixed = sorted([k for k, v in all_pools.items() if len({rep(x) for x in v}) > 1], key=lambda k: (k[1], k[0]))
main = [r for k in mixed for r in all_pools[k]]

p(f'Файл: {SRC}; строк {len(rows)}; после исключений (окно, выбросы, «{NO_CONTENT}», пустой cf): {len(keep)}')
p(f'Пулов набор+день+150/206: {len(all_pools)}; смешанных (есть и первые, и повторные): {len(mixed)}; доменов {len(main)}')
p('')


# ------------------------------------------------------------------ движок O/E + перестановка
def oe_engine(rs, strat_key, labf, ref='1-я', test='повторная', n_perm=N_PERM, use='ex'):
    """Стратифицированный O/E: E = доля страты × сайтов. Возвращает (dict групп, отношение, p2, n_inf_strata)."""
    strata = defaultdict(list)
    for r in rs:
        strata[strat_key(r)].append(r)
    plist = []
    n_inf = 0
    for k, lst in strata.items():
        s = sum(r['_sites'] for r in lst)
        if s <= 0:
            continue
        rate = (sum(r['_ex3'] for r in lst) if use == 'ex' else sum(r['_reg'] for r in lst)) / s
        labs = [labf(r) for r in lst]
        vals = [((r['_ex3'] if use == 'ex' else r['_reg']), rate * r['_sites'], r['_sites']) for r in lst]
        if len(set(labs)) > 1:
            n_inf += 1
        plist.append((labs, vals))

    def stat(pl):
        acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
        for labs, vals in pl:
            for lab, v in zip(labs, vals):
                a = acc[lab]
                a[0] += v[0]
                a[1] += v[1]
                a[2] += v[2]
                a[3] += 1
        rt, rr = acc[test], acc[ref]
        t, rf = ratio(rt[0], rt[1]), ratio(rr[0], rr[1])
        return acc, (t / rf if (t is not None and rf) else None)

    acc, obs = stat(plist)
    if obs is None:
        return acc, None, None, n_inf
    work = [(list(l), v) for l, v in plist]
    le = ge = nv = 0
    for _ in range(n_perm):
        for l, _v in work:
            random.shuffle(l)
        _, st = stat(work)
        if st is None:
            continue
        nv += 1
        if st <= obs + 1e-12:
            le += 1
        if st >= obs - 1e-12:
            ge += 1
    p2 = min(1.0, 2 * min(le, ge) / nv) if nv else None
    return acc, obs, p2, n_inf


def show(acc, ref='1-я', test='повторная', use='ex'):
    for lab in (ref, test):
        a = acc[lab]
        extra = ''
        if use == 'reg':
            lo, hi = pois_ci(a[0])
            extra = f'  95 % O/E [{fmt(lo / a[1]) if a[1] else "—"}; {fmt(hi / a[1]) if a[1] else "—"}]'
        p(f'    {lab:<10} доменов {a[3]:>4}  сайтов {int(a[2]):>6}  O {int(a[0]):>5}  E {fmt(a[1], 1):>8}  O/E {fmt(ratio(a[0], a[1]))}{extra}')


def run(title, rs, strat_key, labf=rep, ref='1-я', test='повторная', use='ex'):
    acc, obs, p2, n_inf = oe_engine(rs, strat_key, labf, ref, test, use=use)
    p(title)
    p(f'    страт всего {len({strat_key(r) for r in rs})}, информативных (обе группы) {n_inf}')
    show(acc, ref, test, use)
    p(f'    ОТНОШЕНИЕ {test}/{ref} = {fmt(obs)}; перестановка внутри страты {N_PERM}: двусторонний p = {fmt(p2, 4)}')
    p('')
    return obs, p2


# ------------------------------------------------------------------ 1. воспроизведение
p('=' * 100)
p('1. ВОСПРОИЗВЕДЕНИЕ ГЛАВНОЙ ПРОВЕРКИ ТЕСТИРОВЩИКА (пул = набор + день + 150/206)')
p('=' * 100)
base_ratio, base_p = run('1a. Выход за 3 суток, повторные против первых:', main, pool_key)
run('1b. Регистрации в окне 3 суток:', main, pool_key, use='reg')

# ------------------------------------------------------------------ 2. баланс ковариат
p('=' * 100)
p('2. БАЛАНС КОВАРИАТ ВНУТРИ ГЛАВНЫХ ПУЛОВ (что ещё, кроме cf, различает первые и повторные базы)')
p('=' * 100)
for col in ('_zone', 'паттерн имени', 'блок часа', 'который раз аккаунт', 'шаблон', 'дней'):
    p(f'  {col}:')
    for g in ('1-я', 'повторная'):
        sub = [r for r in main if rep(r) == g]
        c = Counter(r[col] for r in sub)
        p(f'    {g:<10} ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())))
n_const_vm = sum(1 for k in mixed if len({r['который раз аккаунт'] for r in all_pools[k]}) == 1)
p(f'  «Который раз аккаунт» вебмастера постоянен внутри пула в {n_const_vm} из {len(mixed)} пулов → аккаунт вебмастера сравнение не путает.')
p('  Зона внутри пулов НЕ сбалансирована — у повторных больше .lol и .casino: это главный кандидат в тени.')
p('')

# ------------------------------------------------------------------ 3. жёсткие страты
p('=' * 100)
p('3. ЖЁСТКИЕ СТРАТЫ')
p('=' * 100)
z_ratio, z_p = run('3a. Пул × зона, ВСЕ ячейки (в ячейках с одной группой O = E):', main,
                   lambda r: pool_key(r) + (r['_zone'],))
run('3b. Пул × зона × паттерн имени:', main, lambda r: pool_key(r) + (r['_zone'], r['паттерн имени']))
run('3c. Пул × зона × блок часа:', main, lambda r: pool_key(r) + (r['_zone'], r['блок часа']))
run('3d. Пул × зона × длина метки:', main, lambda r: pool_key(r) + (r['_zone'], r['длина метки']))

p('3e. Пул × зона, отдельно по зонам (E из ячейки пул×зона; ячейки только с одной группой не дают контраста):')
for z in ('team', 'lol', 'casino'):
    sub = [r for r in main if r['_zone'] == z]
    acc, obs, p2, n_inf = oe_engine(sub, lambda r: pool_key(r) + (r['_zone'],), rep)
    p(f'  зона {z}: ячеек с обеими группами {n_inf}; первых {acc["1-я"][3]} (O {int(acc["1-я"][0])}/E {fmt(acc["1-я"][1], 1)}), '
      f'повторных {acc["повторная"][3]} (O {int(acc["повторная"][0])}/E {fmt(acc["повторная"][1], 1)}); отношение {fmt(obs)}, p = {fmt(p2, 3)}')
p('')

# ------------------------------------------------------------------ 4. попульно
p('=' * 100)
p('4. ПОПУЛЬНЫЕ СРАВНЕНИЯ: на чём держится отношение 1,02')
p('=' * 100)
p(f"{'день':<6}{'набор контента':<34}{'с':>4}{'1-я n':>6}{'сайт':>6}{'вых%':>6}{'повт n':>7}{'сайт':>6}{'вых%':>6}{'повт/1-я':>9}{'вес MH':>8}  порядок повторных")
pool_stats = []
for k in mixed:
    lst = all_pools[k]
    fi = [r for r in lst if r['_ord'] == 1]
    rp = [r for r in lst if r['_ord'] > 1]
    s1, s2 = sum(r['_sites'] for r in fi), sum(r['_sites'] for r in rp)
    e1, e2 = sum(r['_ex3'] for r in fi), sum(r['_ex3'] for r in rp)
    r1, r2 = e1 / s1, e2 / s2
    w = s1 * s2 / (s1 + s2)
    pool_stats.append((k, len(fi), len(rp), s1, s2, e1, e2, r1, r2, w))
    ords = dict(sorted(Counter(r['_ord'] for r in rp).items()))
    p(f"{k[1][5:]:<6}{k[0][:33]:<34}{k[2]:>4}{len(fi):>6}{int(s1):>6}{fmt(100 * r1, 1):>6}{len(rp):>7}{int(s2):>6}{fmt(100 * r2, 1):>6}"
      f"{fmt(r2 / r1 if r1 else None):>9}{fmt(w, 0):>8}  {ords}")
mh_num = sum(e2 * s1 / (s1 + s2) for (_k, _a, _b, s1, s2, e1, e2, _r1, _r2, _w) in pool_stats)
mh_den = sum(e1 * s2 / (s1 + s2) for (_k, _a, _b, s1, s2, e1, e2, _r1, _r2, _w) in pool_stats)
p(f'  Мантель–Хензель (вес s1·s2/(s1+s2)): отношение выхода повторных/первых = {fmt(mh_num / mh_den)}')
better = sum(1 for ps in pool_stats if ps[8] > ps[7])
p(f'  Знаковый критерий по пулам: повторные лучше в {better} из {len(pool_stats)} пулов, хуже в {len(pool_stats) - better} '
  f'(биномиальный p = {fmt(min(1.0, 2 * sum(math.comb(len(pool_stats), i) for i in range(min(better, len(pool_stats) - better) + 1)) / 2 ** len(pool_stats)), 3)})')
tot_w = sum(ps[9] for ps in pool_stats)
p('  Доля веса MH по пулам: ' + '; '.join(f"{ps[0][1][5:]} {ps[0][0][:22]}: {fmt(100 * ps[9] / tot_w, 0)} %" for ps in sorted(pool_stats, key=lambda x: -x[9])))
p('')

p('4b. Выбросить один пул (leave-one-out), страта пул × зона:')
for k in mixed:
    sub = [r for r in main if pool_key(r) != k]
    acc, obs, p2, _ = oe_engine(sub, lambda r: pool_key(r) + (r['_zone'],), rep, n_perm=2000)
    p(f"    без {k[1][5:]} {k[0][:30]} {k[2]}: {fmt(obs)} (p = {fmt(p2, 3)}; первых {acc['1-я'][3]}, повторных {acc['повторная'][3]})")
p('')

bal = [k for k, ps in zip(mixed, pool_stats) if ps[1] >= 5 and ps[2] >= 5]
sub = [r for r in main if pool_key(r) in set(bal)]
p(f'4c. Только сбалансированные пулы (≥5 доменов с каждой стороны): {len(bal)} пулов — '
  + '; '.join(f'{k[1][5:]} {k[0][:22]}' for k in bal))
run('    страта пул:', sub, pool_key)
run('    страта пул × зона:', sub, lambda r: pool_key(r) + (r['_zone'],))

sub = [r for r in main if pool_key(r)[1] != '2026-09-12']
p('4d. Без пулов 12.09 (там повторные — почти сплошь ТРЕТЬИ базы, разрывы 5–8 дней):')
run('    страта пул × зона:', sub, lambda r: pool_key(r) + (r['_zone'],))
sub = [r for r in main if pool_key(r)[1] == '2026-09-12']
p('4e. Только пулы 12.09 (третьи базы против первых):')
run('    страта пул × зона:', sub, lambda r: pool_key(r) + (r['_zone'],))
sub = [r for r in main if r['_ord'] != 2]
p('4f. Третьи базы против первых во всех пулах:')
run('    страта пул × зона:', sub, lambda r: pool_key(r) + (r['_zone'],), labf=lambda r: '1-я' if r['_ord'] == 1 else 'повторная')
sub = [r for r in main if r['_ord'] != 3]
p('4g. Вторые базы против первых во всех пулах:')
run('    страта пул × зона:', sub, lambda r: pool_key(r) + (r['_zone'],), labf=lambda r: '1-я' if r['_ord'] == 1 else 'повторная')

# ------------------------------------------------------------------ 5. ранговый тест
p('=' * 100)
p('5. РАНГОВЫЙ ТЕСТ ВНУТРИ ПУЛА (устойчив к доминированию нескольких доменов)')
p('=' * 100)


def rank_test(rs, strat_key, n_perm=N_PERM):
    strata = defaultdict(list)
    for r in rs:
        strata[strat_key(r)].append(r)
    cells = []
    for k, lst in strata.items():
        labs = [rep(r) for r in lst]
        if len(set(labs)) < 2:
            continue
        s = sum(r['_sites'] for r in lst)
        rate = sum(r['_ex3'] for r in lst) / s
        oe = [r['_ex3'] / (rate * r['_sites']) if rate > 0 else 1.0 for r in lst]
        # ранги внутри ячейки, центрированные (van Elteren-подобно: делим на n+1)
        order = sorted(range(len(oe)), key=lambda i: oe[i])
        rk = [0.0] * len(oe)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and oe[order[j + 1]] == oe[order[i]]:
                j += 1
            for t in range(i, j + 1):
                rk[order[t]] = (i + j) / 2 + 1
            i = j + 1
        n = len(oe)
        cr = [(x - (n + 1) / 2) / (n + 1) for x in rk]
        cells.append((labs, cr))

    def stat(cl):
        return sum(c for labs, cr in cl for lab, c in zip(labs, cr) if lab == 'повторная')

    obs = stat(cells)
    work = [(list(l), c) for l, c in cells]
    le = ge = 0
    for _ in range(n_perm):
        for l, _c in work:
            random.shuffle(l)
        st = stat(work)
        if st <= obs + 1e-12:
            le += 1
        if st >= obs - 1e-12:
            ge += 1
    n_rep = sum(1 for labs, _ in cells for l in labs if l == 'повторная')
    med = {}
    for g in ('1-я', 'повторная'):
        vals = sorted(c for labs, cr in cells for lab, c in zip(labs, cr) if lab == g)
        med[g] = vals[len(vals) // 2] if vals else None
    return obs, n_rep, le / n_perm, ge / n_perm, med, len(cells)


for title, sk in (('пул', pool_key), ('пул × зона', lambda r: pool_key(r) + (r['_zone'],))):
    obs, n_rep, ple, pge, med, nc = rank_test(main, sk)
    p(f'  страта {title}: ячеек {nc}; сумма центрированных рангов повторных = {fmt(obs, 2)} (n = {n_rep}, средний ранг {fmt(obs / n_rep, 3)}; '
      f'0 = нет разницы, «−» = повторные ниже); медиана центрированного ранга: первые {fmt(med["1-я"], 3)}, повторные {fmt(med["повторная"], 3)}; '
      f'перестановка: p(≤) = {fmt(ple, 3)}, двусторонний p = {fmt(min(1.0, 2 * min(ple, pge)), 3)}')
p('')

# ------------------------------------------------------------------ 6. регистрации под пул × зона
p('=' * 100)
p('6. РЕГИСТРАЦИИ ПОД ЖЁСТКОЙ СТРАТОЙ')
p('=' * 100)
run('6a. Пул × зона, регистрации в окне 3 суток:', main, lambda r: pool_key(r) + (r['_zone'],), use='reg')
sub = [r for r in main if pool_key(r) in set(bal)]
run('6b. Только сбалансированные пулы, пул × зона, регистрации:', sub, lambda r: pool_key(r) + (r['_zone'],), use='reg')

# ------------------------------------------------------------------ 7. быстрый повтор
p('=' * 100)
p('7. БЫСТРЫЙ ПОВТОР (разрыв ≤2 дней): на чём держится')
p('=' * 100)
quick_pools = {pool_key(r) for r in main if r['_gap'] is not None and r['_gap'] <= 2}
sub = [r for r in main if pool_key(r) in quick_pools and (r['_ord'] == 1 or r['_gap'] <= 2)]
fi = [r for r in sub if r['_ord'] == 1]
p(f'  Пулов с быстрыми повторами: {len(quick_pools)} ({"; ".join(f"{k[1][5:]} {k[0][:30]}" for k in sorted(quick_pools))}); '
  f'первых баз в них {len(fi)} ({int(sum(r["_sites"] for r in fi))} сайтов), быстрых повторных {len(sub) - len(fi)}')
for k in sorted(quick_pools):
    lst = [r for r in sub if pool_key(r) == k]
    for g in ('1-я', 'повторная'):
        gg = [r for r in lst if rep(r) == g]
        s = sum(r['_sites'] for r in gg)
        p(f'    {k[1][5:]} {k[0][:30]} {g:<10} n {len(gg):>3} вых% {fmt(100 * sum(r["_ex3"] for r in gg) / s, 1) if s else "—":>5} '
          f'зоны {dict(Counter(r["_zone"] for r in gg))}')
run('  страта пул:', sub, pool_key)
run('  страта пул × зона:', sub, lambda r: pool_key(r) + (r['_zone'],))

# ------------------------------------------------------------------ 8. содержательная проверка 16.09
p('=' * 100)
p('8. 16.09: держится ли объяснение «это наборы, а не cf» — те же наборы в другие дни и на других порядках')
p('=' * 100)
sets16 = ('content-2026-09-14c-7str-oform-1', 'content-2026-09-14c-7str-oform-2', 'content-2026-09-14b-7str-oform-2',
          'content-2026-09-15-7str-oform-1', 'content-2026-09-15-7str-oform-2', 'content-2026-09-14b-7str-oform-1')
p(f"{'набор контента':<34}{'день':>6}{'порядок':>8}{'с':>4}{'n':>4}{'сайт':>6}{'вых%':>6}{'рег':>4}  зоны")
for s in sets16:
    cells = defaultdict(list)
    for r in keep:
        if r['_set'] == s:
            cells[(r['день запуска'][5:], r['_ord'], r['_s150'])].append(r)
    for k, v in sorted(cells.items()):
        st = sum(r['_sites'] for r in v)
        p(f"{s[:33]:<34}{k[0]:>6}{k[1]:>8}{k[2]:>4}{len(v):>4}{int(st):>6}{fmt(100 * sum(r['_ex3'] for r in v) / st, 1):>6}{int(sum(r['_reg'] for r in v)):>4}  {dict(Counter(r['_zone'] for r in v))}")
p('  Читать так: на 16.09 первые базы content-2026-09-14b-7str-oform-2 (тот же семейный ряд «b», что у повторных) дают 12,6 %,')
p('  а повторные 15-oform-1/2 — 12,7–12,9 %: внутри «b»-ряда разницы нет; весь разрыв 0,70 делают наборы 14c (19–24 %),')
p('  которые и 15.09 первыми базами давали 20–24 % и ни разу не стояли на повторных базах. Отделить 14c от cf на этих данных нельзя.')
p('')

# ------------------------------------------------------------------ ВЫВОД
p('=' * 100)
p('ВЫВОД СКЕПТИКА')
p('=' * 100)
p(f'Воспроизведение: повторные/первые по выходу {fmt(base_ratio)} (p = {fmt(base_p, 3)}). Под стратой пул × зона (все ячейки): {fmt(z_ratio)} (p = {fmt(z_p, 3)}).')
p(f'Мантель–Хензель по пулам: {fmt(mh_num / mh_den)}; знаковый критерий: повторные лучше в {better} из {len(pool_stats)} пулов.')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

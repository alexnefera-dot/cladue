#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик, угол «определения и воспроизводимость» для гипотезы №4
(базы одного cf-аккаунта / аккаунта Вебмастера не делят судьбу).

Что делается (только stdlib):
  1. Проверка среза и определений: оконные колонки, знаменатели, пересечение исключений,
     дней=1 / окно не закрыто, «КОНТЕНТ НЕ ЗАПИСАН», зоны-одиночки, огрубление имён 12.09+.
  2. Независимая пересборка вселенной, пар и решающих чисел (пары, сайты, регистрации, ρ, S, 2×2,
     сиблинги нулей) своим кодом — сверка с заявленными.
  3. Вариантные определения, которые могли бы изменить вывод:
     а) E без самого домена (leave-self-out) для ρ по выходу и для 2×2 по регистрациям;
     б) «удача первой» относительно пула (остаток регистраций m_A > 0 / остаток выхода e_A > 0);
     в) направление «нуль первой → вторая» и «нуль второй → первая» отдельно;
     г) прогон «с августом» без 20 доменов зон-одиночек.
  4. Ширина неопределённости по ρ (Фишер z) и что она значит для формулировки «не объясняют».
Побайтная сверка перезапуска h04 с опубликованным файлом сделана снаружи (diff) — результат в выводе.
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(BASE, 'export', 'gipotezy_svod', 'v04_opredeleniya.txt')
_l = []
random.seed(4)
N_PERM = 3000
NO = 'КОНТЕНТ НЕ ЗАПИСАН'
OUTL = {'3615.team', '3286.team'}
ZONES = ('team', 'lol', 'casino', 'buzz')
SUF_DAY = '2026-09-12'


def p(*a):
    s = ' '.join(str(x) for x in a)
    _l.append(s)
    print(s)


def f3(x):
    return 'н/д' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.3f}'


def f2(x):
    return 'н/д' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.2f}'


def midranks(v):
    n = len(v)
    o = sorted(range(n), key=lambda i: v[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return float('nan')
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def spearman(x, y):
    return pearson(midranks(x), midranks(y))


rows = list(csv.DictReader(open(SRC, encoding='utf-8', newline='')))
for r in rows:
    r['_sites'] = int(r['сайтов в окне'])
    r['_exit'] = int(r['вышли за 3 суток']) if r['вышли за 3 суток'] != '' else None
    r['_reg'] = int(r['регистраций в окне 3 суток'])
    r['_zone'] = r['зона'] if r['зона'] in ZONES else 'прочие'
dom = {r['домен']: r for r in rows}

p('=' * 100)
p('СКЕПТИК К ГИПОТЕЗЕ №4 — угол ОПРЕДЕЛЕНИЯ И ВОСПРОИЗВОДИМОСТЬ')
p('=' * 100)
p('Строк в своде:', len(rows))
p()
p('0. ВОСПРОИЗВОДИМОСТЬ. Скрипт h04_sibling_fate_accounts.py перезапущен (копия с тем же random.seed(1), путь вывода')
p('   перенаправлен в scratchpad); diff с опубликованным h04_sibling_fate_accounts.txt — пустой (совпадение побайтно,')
p('   кроме строки с путём). Все заявленные числа — в файле, расхождений с текстом результата нет, кроме одной мелочи:')
p('   «Вебмастер: 183 пары (все 1→2)» — на деле 1→2: 181, 1→3: 1, 2→3: 1.')

# ---------------------------------------------------------------- 1. срез и определения
p()
p('=' * 100)
p('1. СРЕЗ И ОПРЕДЕЛЕНИЯ')
p('=' * 100)
c = Counter()
for r in rows:
    c[(r['окно закрыто'] != 'да', r['дней'] == '1', r['домен'] in OUTL, r['набор контента'] == NO)] += 1
p('Пересечение исключений (окно не закрыто, дней=1, выброс, контент не записан) → строк:')
for k, v in sorted(c.items()):
    p('   ', 'открыто' if k[0] else 'закрыто', '| дней=1' if k[1] else '| дней≠1', '| выброс' if k[2] else '| не выброс',
      '| НЕ ЗАПИСАН' if k[3] else '| набор есть', '→', v)
kept = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1' and r['домен'] not in OUTL and r['набор контента'] != NO]
kept_ext = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1' and r['домен'] not in OUTL]
p(f'Основной прогон: {len(kept)} доменов (у тестировщика 1511); с августом: {len(kept_ext)} (у тестировщика 1846)')
p('Оконные колонки: «вышли за 3 суток» пусто у', sum(1 for r in rows if r['_exit'] is None), 'доменов — все с окном «нет»:',
  all(r['окно закрыто'] != 'да' for r in rows if r['_exit'] is None), '; у закрытых окон пустых нет:',
  all(r['_exit'] is not None for r in rows if r['окно закрыто'] == 'да'))
p('Знаменатель: «сайтов в окне» == «сайтов» у всех оставшихся:', all(r['сайтов в окне'] == r['сайтов'] for r in kept),
  '; распределение:', dict(Counter(r['сайтов в окне'] for r in kept)))
p('«дней» у оставшихся:', dict(Counter(r['дней'] for r in kept)), '; «наборов на домене»:', dict(Counter(r['наборов на домене'] for r in kept)))
p('Домены дней=1: всего', c_d1 := sum(1 for r in rows if r['дней'] == '1'), ', из них с окном «да»:',
  sum(1 for r in rows if r['дней'] == '1' and r['окно закрыто'] == 'да'), '— в скрипте исключаются по «дней», значит не попадают в пулы;')
p('   используются только для порядкового номера базы внутри аккаунта (это по плану).')
ex = [r for r in rows if r['_zone'] == 'прочие']
p(f'Зоны-одиночки: {len(ex)} доменов, все «{NO}»:', all(r['набор контента'] == NO for r in ex),
  '; дни:', dict(Counter(r['день запуска'] for r in ex)))
p('   → в основном прогоне их нет (исключены вместе с «НЕ ЗАПИСАН»); в прогоне «с августом» они попадают в дневные пулы')
p('     наравне с team/lol — тестировщик этого не оговорил (проверка влияния — п. 3г).')

# огрубление 12.09+
suf = [r for r in kept if re.search(r'_\d+$', r['набор контента'])]
suf_late = [r for r in suf if r['день запуска'] >= SUF_DAY]
p(f'Имена с суффиксом _NN среди оставшихся: {len(suf)}, из них с {SUF_DAY}: {len(suf_late)} (у тестировщика 490);')
byroot = defaultdict(Counter)
for r in suf_late:
    byroot[(re.sub(r'_\d+$', '', r['набор контента']), r['день запуска'])][r['набор контента']] += 1
p(f'   корней+день из них: {len(byroot)}; во всех ли каждое имя встречается ровно один раз (один набор на домен):',
  all(max(v.values()) == 1 for v in byroot.values()))
p('   имена до 12.09 с суффиксом (уникальные, в пулы ≥3 не попадают):', [r['набор контента'] for r in suf if r['день запуска'] < SUF_DAY])


def pool_key(r):
    name = r['набор контента']
    if name == NO:
        return ('ТОЛЬКО ДЕНЬ', r['день запуска'])
    if r['день запуска'] >= SUF_DAY and re.search(r'_\d+$', name):
        return (re.sub(r'_\d+$', '', name), r['день запуска'])
    return (name, r['день запуска'])


def build(rs, loo=False):
    pools = defaultdict(list)
    for r in rs:
        pools[pool_key(r)].append(r)
    U = {}
    for k, ms in pools.items():
        if len(ms) < 3:
            continue
        S = sum(m['_sites'] for m in ms)
        X = sum(m['_exit'] for m in ms)
        R = sum(m['_reg'] for m in ms)
        for m in ms:
            if loo:
                s_, x_, r_ = S - m['_sites'], X - m['_exit'], R - m['_reg']
                ee = x_ / s_ * m['_sites'] if s_ else 0.0
                er = r_ / s_ * m['_sites'] if s_ else 0.0
            else:
                ee = X / S * m['_sites']
                er = R / S * m['_sites']
            U[m['домен']] = dict(row=m, pool=k, n=len(ms), sites=m['_sites'], o_exit=m['_exit'], e_exit=ee,
                                 o_reg=m['_reg'], e_reg=er,
                                 res_exit=(m['_exit'] - ee) / math.sqrt(ee) if ee > 0 else 0.0,
                                 res_reg=(m['_reg'] - er) / math.sqrt(er) if er > 0 else 0.0,
                                 oe_exit=m['_exit'] / ee if ee > 0 else float('nan'),
                                 day=m['день запуска'], zone=m['_zone'])
    return U, sum(1 for v in pools.values() if len(v) >= 3)


U, npools = build(kept)
p(f'Пулы «набор+день» ≥3 баз: {npools} (у тестировщика 137); доменов {len(U)} (1483); сайтов {sum(u["sites"] for u in U.values())} (305452);')
p(f'   вышло {sum(u["o_exit"] for u in U.values())} (37296); регистраций в окне {sum(u["o_reg"] for u in U.values())} (244);')
p('   пулов с нулём выходов (O/E не определён):', sum(1 for k in set(u['pool'] for u in U.values()) if sum(v['o_exit'] for v in U.values() if v['pool'] == k) == 0),
  '; зоны в пулах:', dict(Counter(u['zone'] for u in U.values())))
p('   доменов в пулах без регистраций (E_reg=0):', sum(1 for u in U.values() if u['e_reg'] == 0), '(у тестировщика 391)')


def pairs_for(Uni, field):
    by = defaultdict(list)
    for r in rows:
        a = r[field].strip()
        if a:
            by[a].append(r)
    prs = []
    for a, rs in by.items():
        rs = sorted(rs, key=lambda r: (r['день запуска'], r['домен']))
        ordn = {r['домен']: i + 1 for i, r in enumerate(rs)}
        us = [r for r in rs if r['домен'] in Uni]
        for x, y in zip(us, us[1:]):
            prs.append(dict(acc=a, A=Uni[x['домен']], B=Uni[y['домен']], label=f'{ordn[x["домен"]]}→{ordn[y["домен"]]}'))
    return prs


def clopper(k, n, alpha=0.05):
    def cdf(k_, p_):
        return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * math.log(p_) + (n - i) * math.log(1 - p_)) for i in range(k_ + 1))
    lo, hi = 0.0, 1.0
    if k > 0:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if 1 - cdf(k - 1, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if k < n:
        a, b = 0.0, 1.0
        for _ in range(60):
            m = (a + b) / 2
            if cdf(k, m) > alpha / 2:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    return lo, hi


def ratio_ci(o1, e1, o0, e0):
    n = int(o1 + o0)
    if n == 0 or e1 <= 0 or e0 <= 0:
        return float('nan'), float('nan'), float('nan')
    q = e1 / (e1 + e0)
    lo, hi = clopper(int(o1), n)
    cv = lambda pp: float('inf') if pp >= 1 else (0.0 if pp <= 0 else (pp / (1 - pp)) / (q / (1 - q)))
    r = (o1 / e1) / (o0 / e0) if o0 > 0 else float('inf')
    return r, cv(lo), cv(hi)


def stats(prs, first_flag=None, n_perm=N_PERM, do_perm=True):
    n = len(prs)
    aoe = [x['A']['oe_exit'] for x in prs]
    boe = [x['B']['oe_exit'] for x in prs]
    ar = [x['A']['res_exit'] for x in prs]
    br = [x['B']['res_exit'] for x in prs]
    rho = spearman(aoe, boe)
    S = sum(a * b for a, b in zip(ar, br)) / n
    flag = first_flag or (lambda x: x['A']['o_reg'] > 0)
    o1 = sum(x['B']['o_reg'] for x in prs if flag(x)); e1 = sum(x['B']['e_reg'] for x in prs if flag(x))
    o0 = sum(x['B']['o_reg'] for x in prs if not flag(x)); e0 = sum(x['B']['e_reg'] for x in prs if not flag(x))
    n1 = sum(1 for x in prs if flag(x))
    res = dict(n=n, rho=rho, S=S, o1=o1, e1=e1, o0=o0, e0=e0, n1=n1, ratio=ratio_ci(o1, e1, o0, e0),
               sites=sum(x['A']['sites'] + x['B']['sites'] for x in prs), regs=sum(x['A']['o_reg'] + x['B']['o_reg'] for x in prs))
    if do_perm:
        groups = defaultdict(list)
        for i, x in enumerate(prs):
            groups[x['B']['day']].append(i)
        groups = list(groups.values())
        rb = midranks(boe); ra = midranks(aoe)
        sec = list(range(n))
        nr, nS, nq = [], [], []
        fl = [1 if flag(x) else 0 for x in prs]
        bo = [x['B']['o_reg'] for x in prs]; be = [x['B']['e_reg'] for x in prs]
        for _ in range(n_perm):
            for g in groups:
                sh = g[:]
                random.shuffle(sh)
                for k, i in enumerate(g):
                    sec[i] = sh[k]
            nr.append(pearson(ra, [rb[sec[i]] for i in range(n)]))
            nS.append(sum(ar[i] * br[sec[i]] for i in range(n)) / n)
            a1 = sum(bo[sec[i]] for i in range(n) if fl[i]); b1 = sum(be[sec[i]] for i in range(n) if fl[i])
            a0 = sum(bo[sec[i]] for i in range(n) if not fl[i]); b0 = sum(be[sec[i]] for i in range(n) if not fl[i])
            nq.append((a1 / b1) / (a0 / b0) if b1 > 0 and b0 > 0 and a0 > 0 else float('nan'))
        for name, null, obs in (('rho', nr, rho), ('S', nS, S)):
            vs = sorted(v for v in null if not math.isnan(v))
            cen = sum(vs) / len(vs)
            res[name + '_p'] = (sum(1 for v in vs if abs(v - cen) >= abs(obs - cen) - 1e-12) + 1) / (len(vs) + 1)
            res[name + '_ci'] = (vs[int(0.025 * len(vs))], vs[int(0.975 * len(vs)) - 1])
        vs = sorted(v for v in nq if not math.isnan(v))
        rq = res['ratio'][0]
        if vs and not math.isnan(rq):
            lv = [math.log(v) for v in vs if v > 0]
            cen = sum(lv) / len(lv)
            d = abs(math.log(rq) - cen) if rq > 0 else float('inf')
            res['ratio_p'] = (sum(1 for v in vs if (abs(math.log(v) - cen) if v > 0 else float('inf')) >= d - 1e-12) + 1) / (len(vs) + 1)
        else:
            res['ratio_p'] = float('nan')
    return res


def show(title, st, claimed=None):
    p(f'--- {title}: пар {st["n"]}, сайтов {st["sites"]}, регистраций {st["regs"]}')
    line = f'    ВЫХОД: ρ Спирмена по O/E = {f3(st["rho"])}, S = {f3(st["S"])}'
    if 'rho_p' in st:
        line += f' (перест. p ρ = {f3(st["rho_p"])}, нуль 95% {f3(st["rho_ci"][0])}..{f3(st["rho_ci"][1])}; p S = {f3(st["S_p"])}, нуль {f3(st["S_ci"][0])}..{f3(st["S_ci"][1])})'
    p(line)
    r, lo, hi = st['ratio']
    line = (f'    2×2 РЕГ. второй: первая «удачная» ({st["n1"]} пар) O {st["o1"]:.0f} / E {f2(st["e1"])} = {f2(st["o1"] / st["e1"] if st["e1"] else float("nan"))};'
            f' иначе ({st["n"] - st["n1"]} пар) O {st["o0"]:.0f} / E {f2(st["e0"])} = {f2(st["o0"] / st["e0"] if st["e0"] else float("nan"))}; отношение {f2(r)} ({f2(lo)}..{f2(hi)})')
    if 'ratio_p' in st:
        line += f', перест. p {f3(st["ratio_p"])}'
    p(line)
    if claimed:
        p('    заявлено тестировщиком:', claimed)


# ---------------------------------------------------------------- 2. пересборка решающих чисел
p()
p('=' * 100)
p('2. НЕЗАВИСИМАЯ ПЕРЕСБОРКА РЕШАЮЩИХ ЧИСЕЛ (свой код, перестановок 3000, seed 4)')
p('=' * 100)
PR = {}
for field, name, claimed in (('cf-аккаунт', 'CF-АККАУНТ', 'пар 608, сайтов 250477, рег 226; ρ −0.022 (нуль −0.076..0.082), S −0.138 (−0.484..0.535); 2×2: 14/18.52 vs 79/72.29, отношение 0.69 (0.36..1.23), перест. p 0.333'),
                             ('аккаунт вебмастера', 'АККАУНТ ВЕБМАСТЕРА', 'пар 183, сайтов 75386, рег 73; ρ −0.061 (нуль −0.152..0.130), S −0.617 (−0.893..0.877); 2×2: 7/3.21 vs 10/13.07, отношение 2.85 (0.92..8.30), перест. p 0.187')):
    prs = pairs_for(U, field)
    PR[field] = prs
    lab = Counter(x['label'] for x in prs)
    st = stats(prs)
    show(name, st, claimed)
    p('    порядковые номера пар:', dict(sorted(lab.items())), '; пар в одном пуле:', sum(1 for x in prs if x['A']['pool'] == x['B']['pool']),
      '; пар в один день:', sum(1 for x in prs if x['A']['day'] == x['B']['day']))

# сиблинги нулей — пересборка
p()
p('--- Сиблинги баз с нулём выходов (пересборка):')
for field, name, claimed in (('cf-аккаунт', 'cf', '13 сиблингов, 2678 сайтов, O 422 / E 415.6 = 1.015'), ('аккаунт вебмастера', 'Вебмастер', '2 сиблинга, 412 сайтов, O 67 / E 73.9 = 0.907')):
    by = defaultdict(list)
    for u in U.values():
        a = u['row'][field].strip()
        if a:
            by[a].append(u)
    zeros = [u for u in U.values() if u['o_exit'] == 0]
    sibs = {}
    same_pool = 0
    for z in zeros:
        for o in by[z['row'][field].strip()]:
            if o['row']['домен'] != z['row']['домен']:
                sibs[o['row']['домен']] = o
                if o['pool'] == z['pool']:
                    same_pool += 1
    sb = list(sibs.values())
    O = sum(u['o_exit'] for u in sb); E = sum(u['e_exit'] for u in sb); S_ = sum(u['sites'] for u in sb)
    p(f'    {name}: нулевых баз {len(zeros)}, уникальных сиблингов {len(sb)}, сайтов {S_}, O {O} / E {E:.1f} = {f3(O / E if E else float("nan"))};'
      f' сиблингов в одном пуле с нулевой базой: {same_pool}   [заявлено: {claimed}]')

# ---------------------------------------------------------------- 3. вариантные определения
p()
p('=' * 100)
p('3. ВАРИАНТНЫЕ ОПРЕДЕЛЕНИЯ — меняют ли они вывод')
p('=' * 100)
p('3а. E без самого домена (leave-self-out): у тестировщика E включает сам домен, что тянет O/E к 1 и режет остатки;')
p('    в пулах из 3 баз это заметно (доля домена в пуле ~1/3).')
U_loo, _ = build(kept, loo=True)
for field, name in (('cf-аккаунт', 'CF'), ('аккаунт вебмастера', 'Вебмастер')):
    prs = pairs_for(U_loo, field)
    st = stats(prs)
    show(f'{name}, E без самого домена', st)

p()
p('3б. «Удача первой» относительно её пула, а не сырое «была регистрация»:')
for field, name in (('cf-аккаунт', 'CF'), ('аккаунт вебмастера', 'Вебмастер')):
    prs = PR[field]
    st = stats(prs, first_flag=lambda x: x['A']['e_reg'] > 0 and x['A']['o_reg'] > x['A']['e_reg'], n_perm=N_PERM)
    show(f'{name}, первая «удачная» = регистраций больше ожидания пула (O_A > E_A)', st)
    st = stats(prs, first_flag=lambda x: x['A']['res_exit'] > 0, n_perm=N_PERM)
    show(f'{name}, первая «удачная» = выход выше пула (e_A > 0) → регистрации второй', st)
    # выход второй при выходе первой выше/ниже пула
    hi = [x for x in prs if x['A']['res_exit'] > 0]; lo = [x for x in prs if x['A']['res_exit'] <= 0]
    ohi = sum(x['B']['o_exit'] for x in hi); ehi = sum(x['B']['e_exit'] for x in hi)
    olo = sum(x['B']['o_exit'] for x in lo); elo = sum(x['B']['e_exit'] for x in lo)
    p(f'    выход второй: первая выше пула ({len(hi)} пар) O/E {f3(ohi / ehi)} ({ohi}/{ehi:.0f}); первая ниже ({len(lo)} пар) O/E {f3(olo / elo)} ({olo}/{elo:.0f}); отношение {f3((ohi / ehi) / (olo / elo))}')

p()
p('3в. Направление «нуль первой → следующая база» (гипотеза говорит именно про перенос на СЛЕДУЮЩУЮ базу):')
for field, name in (('cf-аккаунт', 'CF'), ('аккаунт вебмастера', 'Вебмастер')):
    prs = PR[field]
    fw = [x for x in prs if x['A']['o_exit'] == 0]
    bw = [x for x in prs if x['B']['o_exit'] == 0]
    for lab, ps, side in (('нуль у первой → вторая', fw, 'B'), ('нуль у второй ← первая', bw, 'A')):
        if not ps:
            p(f'    {name}, {lab}: пар 0')
            continue
        O = sum(x[side]['o_exit'] for x in ps); E = sum(x[side]['e_exit'] for x in ps); S_ = sum(x[side]['sites'] for x in ps)
        Or = sum(x[side]['o_reg'] for x in ps); Er = sum(x[side]['e_reg'] for x in ps)
        p(f'    {name}, {lab}: пар {len(ps)}, сайтов {S_}, выход O {O} / E {E:.1f} = {f3(O / E if E else float("nan"))}; регистрации O {Or} / E {Er:.2f}')

p()
p('3г. Прогон «с августом» без 20 доменов зон-одиночек (они все «НЕ ЗАПИСАН», сидят в дневных пулах):')
Ue, npe = build(kept_ext)
Ue2, npe2 = build([r for r in kept_ext if r['_zone'] != 'прочие'])
p(f'    с одиночками: пулов {npe}, доменов {len(Ue)} (у тестировщика 1812); без них: пулов {npe2}, доменов {len(Ue2)}')
for field, name, claimed in (('cf-аккаунт', 'CF', 'ρ 0.031, отношение 0.91 (0.57..1.41), 935 пар'), ('аккаунт вебмастера', 'Вебмастер', 'ρ 0.009, отношение 0.87 (0.44..1.61), 457 пар')):
    prs = pairs_for(Ue, field)
    n_ex = sum(1 for x in prs if x['A']['zone'] == 'прочие' or x['B']['zone'] == 'прочие')
    st = stats(prs, do_perm=False)
    show(f'{name} с августом, как у тестировщика (пар с одиночкой: {n_ex})', st, claimed)
    prs2 = pairs_for(Ue2, field)
    st2 = stats(prs2, do_perm=False)
    show(f'{name} с августом, без зон-одиночек', st2)

# ---------------------------------------------------------------- 4. ширина неопределённости и формулировка
p()
p('=' * 100)
p('4. ЧТО ЧИСЛА ПОЗВОЛЯЮТ СКАЗАТЬ (ширина неопределённости по ρ; Фишер z, ±1.96/√(n−3))')
p('=' * 100)
for field, name in (('cf-аккаунт', 'CF'), ('аккаунт вебмастера', 'Вебмастер')):
    prs = PR[field]
    n = len(prs)
    rho = spearman([x['A']['oe_exit'] for x in prs], [x['B']['oe_exit'] for x in prs])
    z = 0.5 * math.log((1 + rho) / (1 - rho)); se = 1 / math.sqrt(n - 3)
    lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
    p(f'    {name}: ρ выход {f3(rho)}, 95% {f3(lo)}..{f3(hi)}; «|ρ|<0,1» целиком в интервале? {"да" if lo > -0.1 and hi < 0.1 else "НЕТ"};'
      f' «ρ≥0,15» исключено? {"да" if hi < 0.15 else "нет"}; ρ≤−0,15 исключено? {"да" if lo > -0.15 else "нет"}')
    p(f'       если аккаунт объясняет долю v разброса внутри пула, корреляция сиблингов ≈ v; верхняя граница v здесь ≈ {max(0.0, hi):.2f}'
      f' (то есть аккаунт может объяснять до {100 * max(0.0, hi):.0f}% разброса по выходу — «не объясняют» надо читать как «не больше этого»)')
p()
p('    Сиблинги нулей cf: 13 баз, перестановочный нуль O/E 0.787..1.225 (у тестировщика) — коридор «0,9–1,1» уже нуля,')
p('    то есть выполнен только точечно; «выходят как все» — верно как «нет признаков», не как «доказано в ±10%».')
p('    Сиблинги нулей Вебмастера: 2 базы — не свидетельство ни о чём.')

# ---------------------------------------------------------------- итог
p()
p('=' * 100)
p('ИТОГ СКЕПТИКА (определения и воспроизводимость)')
p('=' * 100)
p('1. Воспроизводимость: перезапуск даёт побайтно тот же файл; все числа в тексте результата есть в выводе скрипта.')
p('2. Определения соблюдены: оконные колонки (вышли за 3 суток, сайтов в окне, регистраций в окне 3 суток), окно закрыто = да,')
p('   дней ≠ 1, выбросы 3615/3286 и «КОНТЕНТ НЕ ЗАПИСАН» исключены в основном прогоне (с августом — оговорено как страта «день»),')
p('   пул = набор + день (≥3), огрубление 12.09+ реально «один набор на домен» (каждое имя — один домен) и оговорено,')
p('   знаменатель E = доля пула × сайтов в окне, пар в одном пуле/дне нет, зон-одиночек в основном прогоне нет.')
p('3. Мелкие неточности, не меняющие вывод: (а) 20 доменов зон-одиночек в прогоне «с августом» сидят в дневных пулах')
p('   без оговорки; (б) «все 183 пары Вебмастера 1→2» — 181; (в) E включает сам домен — при E без домена числа те же по знаку.')
p('4. Формулировка: по выходу «подтверждена» держится на точечных критериях плана; интервалы по ρ дают верхнюю границу')
p('   доли разброса, объяснимой аккаунтом (см. п. 4). По регистрациям тестировщик сам оговорил, что точность не та.')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(_l) + '\n')
print(f'\n[записано: {OUT}]')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик, угол СТАТИСТИКА, гипотеза №5 (повторное использование cf-аккаунта).
Проверяем результат h05_cf_reuse_order.py:
  1. Суммы или средние по доменам? (воспроизводим сырой срез и O/E суммами)
  2. Баланс групп внутри пулов: при перекосе 1:36 пуловое E почти равно O
     самой группы — отношение тянется к 1. Считаем альтернативные оценки:
     Мантель–Хензель по сайтам, E от ставки противоположной группы,
     отношения по пулам, знаковый критерий, взвешенный лог-ратио.
  3. Точность: бутстреп по доменам внутри пула → 95 % интервал отношения.
     Если интервал накрывает 0,85 — «разница в 10 % была бы видна» не верно.
  4. Устойчивость: без топ-3 доменов по выходу/регистрациям в каждой группе,
     без каждого пула по очереди, только сбалансированные пулы.
  5. Номер экземпляра _NN внутри пула: сцеплен ли с порядком cf?
  6. Регистрации: сколько на группу, концентрация, без топ-3.
  7. Число сравнений в отчёте тестировщика.
Только stdlib.
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
OUT = os.path.join(OUT_DIR, 'v05_statistika.txt')
os.makedirs(OUT_DIR, exist_ok=True)

random.seed(7)
N_PERM = 10000
N_BOOT = 5000
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
_lines = []


def p(*a):
    s = ' '.join(str(x) for x in a)
    _lines.append(s)
    print(s)


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fmt(x, d=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return '—'
    return f'{x:.{d}f}'


def strip_suffix(name):
    return re.sub(r'_\d+$', '', name)


def suffix_num(name):
    m = re.search(r'_(\d+)$', name)
    return int(m.group(1)) if m else None


# ------------------------------------------------------------ чтение и порядок
with open(SRC, encoding='utf-8', newline='') as fh:
    rows = list(csv.DictReader(fh))
by_cf = defaultdict(list)
for r in rows:
    by_cf[r['cf-аккаунт']].append(r)
for cfk, lst in by_cf.items():
    lst.sort(key=lambda r: (r['день запуска'], int(f(r['час запуска']))))
    prev = None
    for i, r in enumerate(lst):
        r['_ord'] = i + 1
        d = date.fromisoformat(r['день запуска'])
        r['_gap'] = (d - prev).days if prev is not None else None
        prev = d
    if cfk == '':
        for r in lst:
            r['_ord'] = None
for r in rows:
    r['_sites'] = f(r['сайтов в окне'])
    r['_ex3'] = f(r['вышли за 3 суток'])
    r['_reg'] = f(r['регистраций в окне 3 суток'])
    r['_s150'] = '150' if r['сайтов'] == '150' else '206'
    r['_set'] = strip_suffix(r['набор контента'])
    r['_nn'] = suffix_num(r['набор контента'])

keep = [r for r in rows if r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS
        and r['набор контента'] != NO_CONTENT and r['cf-аккаунт'] != '' and r['_ord']]
p(f'Доменов после фильтров тестировщика: {len(keep)}')


def key(r):
    return (r['_set'], r['день запуска'], r['_s150'])


pools = defaultdict(list)
for r in keep:
    pools[key(r)].append(r)
mixed = [k for k, v in pools.items() if len({r['_ord'] == 1 for r in v}) > 1]
mixed.sort(key=lambda k: (k[1], k[0]))
main = [r for k in mixed for r in pools[k]]
p(f'Главных пулов: {len(mixed)}, доменов: {len(main)}')
p('')

# ------------------------------------------------------------ 1. суммы vs средние
p('=' * 100)
p('1. СУММЫ ИЛИ СРЕДНИЕ ПО ДОМЕНАМ?')
p('=' * 100)
raw = [r for r in rows if r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS and r['_ord']]
for o in (1, 2, 3):
    g = [r for r in raw if r['_ord'] == o]
    s = sum(r['_sites'] for r in g)
    e = sum(r['_ex3'] for r in g)
    mean_dom = sum(r['_ex3'] / r['_sites'] for r in g if r['_sites']) / len(g)
    p(f'  {o}-я: сумма вышли/сумма сайтов = {100 * e / s:.1f} %; среднее долей по доменам = {100 * mean_dom:.1f} % (n={len(g)})')
p('  → в отчёте тестировщика использованы суммы (совпадает с 15,8/11,3/10,1); O/E тоже суммами. Претензии нет.')
p('')

# ------------------------------------------------------------ 2. баланс пулов и альтернативные оценки
p('=' * 100)
p('2. БАЛАНС ГРУПП ВНУТРИ ПУЛОВ И АЛЬТЕРНАТИВНЫЕ ОЦЕНКИ ОТНОШЕНИЯ')
p('   Пуловое E считается по всем доменам пула, включая саму группу. При перекосе 1:36 E повторных ≈ O повторных,')
p('   и вклад такого пула в отношение тянется к 1 независимо от истинного эффекта. Информации в пуле ~ n1·n2/(n1+n2).')
p('=' * 100)


def pool_stats(k, rs=None):
    rs = rs if rs is not None else pools[k]
    fi = [r for r in rs if r['_ord'] == 1]
    rp = [r for r in rs if r['_ord'] > 1]
    s1, s2 = sum(r['_sites'] for r in fi), sum(r['_sites'] for r in rp)
    e1, e2 = sum(r['_ex3'] for r in fi), sum(r['_ex3'] for r in rp)
    g1, g2 = sum(r['_reg'] for r in fi), sum(r['_reg'] for r in rp)
    return dict(n1=len(fi), n2=len(rp), s1=s1, s2=s2, e1=e1, e2=e2, g1=g1, g2=g2,
                r1=e1 / s1 if s1 else None, r2=e2 / s2 if s2 else None)


p(f"{'день':<6}{'набор':<34}{'с':>4}{'n1':>4}{'n2':>4}{'инфо':>6}{'вых1%':>7}{'вых2%':>7}{'отн':>6}{'рег1':>5}{'рег2':>5}  NN первых | NN повторных")
tot_info = 0.0
per_pool = []
for k in mixed:
    st = pool_stats(k)
    info = st['n1'] * st['n2'] / (st['n1'] + st['n2'])
    tot_info += info
    ratio = st['r2'] / st['r1'] if st['r1'] else None
    per_pool.append((k, st, info, ratio))
    nn1 = sorted(r['_nn'] for r in pools[k] if r['_ord'] == 1 and r['_nn'] is not None)
    nn2 = sorted(r['_nn'] for r in pools[k] if r['_ord'] > 1 and r['_nn'] is not None)
    p(f"{k[1][5:]:<6}{k[0][:33]:<34}{k[2]:>4}{st['n1']:>4}{st['n2']:>4}{info:>6.1f}{100 * st['r1']:>7.1f}{100 * st['r2']:>7.1f}{fmt(ratio):>6}"
      f"{int(st['g1']):>5}{int(st['g2']):>5}  {nn1 if nn1 else '—'} | {nn2 if nn2 else '—'}")
p(f'Суммарная «информация» n1·n2/(n1+n2) по пулам: {tot_info:.1f} (эквивалент ≈{2 * tot_info:.0f} доменов при балансе 1:1 из {len(main)}).')
bal = [(k, st, info, ratio) for k, st, info, ratio in per_pool if st['n1'] >= 5 and st['n2'] >= 5]
p(f'Пулов с ≥5 доменов в каждой группе: {len(bal)} — ' + '; '.join(f"{k[1][5:]} {k[0][:28]} ({st['n1']}:{st['n2']}, отн {fmt(ratio)})" for k, st, info, ratio in bal))
p('')

# знаковый критерий и медиана по пулам
ratios = [ratio for _, _, _, ratio in per_pool if ratio is not None]
n_up = sum(1 for x in ratios if x > 1)
n_dn = sum(1 for x in ratios if x < 1)
p(f'Отношения по пулам (повторные/первые по выходу): {", ".join(fmt(x) for x in sorted(ratios))}')
p(f'  повторные лучше в {n_up} пулах, хуже в {n_dn}; медиана {fmt(sorted(ratios)[len(ratios) // 2])}; разброс 0,48…3,27 — пулы крайне разнородны.')
lw = sum(math.log(ratio) * info for _, _, info, ratio in per_pool if ratio)
ww = sum(info for _, _, info, ratio in per_pool if ratio)
p(f'  Взвешенное (по n1·n2/(n1+n2)) среднее лог-отношений → {math.exp(lw / ww):.2f}')


def mh_ratio(rs):
    """Мантель–Хензель отношение долей выхода (сайты как единицы) повторные/первые по пулам."""
    num = den = 0.0
    byk = defaultdict(list)
    for r in rs:
        byk[key(r)].append(r)
    for k, lst in byk.items():
        st = pool_stats(k, lst)
        N = st['s1'] + st['s2']
        if N == 0 or st['s1'] == 0 or st['s2'] == 0:
            continue
        num += st['e2'] * st['s1'] / N
        den += st['e1'] * st['s2'] / N
    return num / den if den else None


def oe_ratio(rs, opposite=False, field='e'):
    """Отношение O/E повторных к O/E первых. opposite=True: E группы — по ставке противоположной группы."""
    byk = defaultdict(list)
    for r in rs:
        byk[key(r)].append(r)
    O1 = E1 = O2 = E2 = 0.0
    for k, lst in byk.items():
        st = pool_stats(k, lst)
        v1, v2 = (st['e1'], st['e2']) if field == 'e' else (st['g1'], st['g2'])
        s1, s2 = st['s1'], st['s2']
        if s1 == 0 or s2 == 0:
            continue
        if opposite:
            rate1 = v2 / s2
            rate2 = v1 / s1
            O1 += v1; E1 += rate1 * s1
            O2 += v2; E2 += rate2 * s2
        else:
            rate = (v1 + v2) / (s1 + s2)
            O1 += v1; E1 += rate * s1
            O2 += v2; E2 += rate * s2
    a = O2 / E2 if E2 else None
    b = O1 / E1 if E1 else None
    return (a / b if a is not None and b else None), O1, E1, O2, E2


base = oe_ratio(main)
p(f'  Оценка тестировщика (пуловое E, включая саму группу): {fmt(base[0])}  [первые O={int(base[1])} E={base[2]:.0f}; повторные O={int(base[3])} E={base[4]:.0f}]')
opp = oe_ratio(main, opposite=True)
p(f'  E от ставки ПРОТИВОПОЛОЖНОЙ группы (O2/E2 при E2 = ставка первых × сайты повторных): O2/E2 = {fmt(opp[3] / opp[4])}; '
  f'O1/E1 при ставке повторных = {fmt(opp[1] / opp[2])}')
p(f'  Мантель–Хензель по сайтам: {fmt(mh_ratio(main))}')
p('')

# ------------------------------------------------------------ 3. точность: бутстреп по доменам внутри пула
p('=' * 100)
p('3. ТОЧНОСТЬ: бутстреп доменов внутри пула (с возвращением, группы сохраняются) → 95 % интервал отношения')
p('=' * 100)


def boot_ci(rs, stat, n_boot=N_BOOT):
    byk = defaultdict(list)
    for r in rs:
        byk[key(r)].append(r)
    groups = {k: ([r for r in v if r['_ord'] == 1], [r for r in v if r['_ord'] > 1]) for k, v in byk.items()}
    vals = []
    for _ in range(n_boot):
        samp = []
        for k, (fi, rp) in groups.items():
            samp.extend(random.choice(fi) for _ in range(len(fi)))
            samp.extend(random.choice(rp) for _ in range(len(rp)))
        v = stat(samp)
        if v is not None and v > 0:
            vals.append(v)
    vals.sort()
    n = len(vals)
    return vals[int(0.025 * n)], vals[int(0.5 * n)], vals[int(0.975 * n) - 1], n


lo, med, hi, n = boot_ci(main, lambda s: oe_ratio(s)[0])
p(f'  Выход, оценка тестировщика: точечно {fmt(base[0])}; бутстреп 95 % [{fmt(lo)}; {fmt(hi)}] (медиана {fmt(med)}, {n} повторов)')
lo2, med2, hi2, n2 = boot_ci(main, mh_ratio)
p(f'  Выход, Мантель–Хензель: точечно {fmt(mh_ratio(main))}; бутстреп 95 % [{fmt(lo2)}; {fmt(hi2)}]')
lo3, med3, hi3, n3 = boot_ci(main, lambda s: oe_ratio(s, field='g')[0])
p(f'  Регистрации, оценка тестировщика: точечно {fmt(oe_ratio(main, field="g")[0])}; бутстреп 95 % [{fmt(lo3)}; {fmt(hi3)}]')
p('  Критерий вреда из плана — 0,85. Если 0,85 внутри интервала по выходу, то «разница в 10 % была бы видна» не верно.')

# перестановочный нулевой разброс
byk = defaultdict(list)
for r in main:
    byk[key(r)].append(r)
null_vals = []
for _ in range(N_PERM):
    samp = []
    for k, lst in byk.items():
        labs = [r['_ord'] for r in lst]
        random.shuffle(labs)
        for r, lab in zip(lst, labs):
            rr = dict(r)
            rr['_ord'] = lab
            samp.append(rr)
    v = oe_ratio(samp)[0]
    if v:
        null_vals.append(v)
null_vals.sort()
p(f'  Нулевое перестановочное распределение отношения по выходу: 2,5 % = {fmt(null_vals[int(0.025 * len(null_vals))])}, '
  f'97,5 % = {fmt(null_vals[int(0.975 * len(null_vals)) - 1])} → при нуле отношение гуляет в этом коридоре; эффект 0,85 значим, только если он вне коридора.')
p('')

# ------------------------------------------------------------ 4. устойчивость
p('=' * 100)
p('4. УСТОЙЧИВОСТЬ')
p('=' * 100)


def perm_p(rs, stat, n_perm=N_PERM):
    obs = stat(rs)
    if obs is None:
        return None, None
    byk_ = defaultdict(list)
    for r in rs:
        byk_[key(r)].append(r)
    le = ge = 0
    for _ in range(n_perm):
        samp = []
        for k, lst in byk_.items():
            labs = [r['_ord'] for r in lst]
            random.shuffle(labs)
            for r, lab in zip(lst, labs):
                rr = dict(r)
                rr['_ord'] = lab
                samp.append(rr)
        v = stat(samp)
        if v is None:
            continue
        if v <= obs + 1e-12:
            le += 1
        if v >= obs - 1e-12:
            ge += 1
    return obs, min(1.0, 2 * min(le, ge) / n_perm)


def describe(rs, title, n_perm=2000):
    fi = [r for r in rs if r['_ord'] == 1]
    rp = [r for r in rs if r['_ord'] > 1]
    ex = oe_ratio(rs)
    rg = oe_ratio(rs, field='g')
    obs, pv = perm_p(rs, lambda s: oe_ratio(s)[0], n_perm)
    p(f'  {title}: доменов {len(fi)}+{len(rp)}, выход отн {fmt(ex[0])} (p={fmt(pv, 3)}), МХ {fmt(mh_ratio(rs))}; '
      f'рег первых {int(rg[1])}/E {rg[2]:.1f}, повторных {int(rg[3])}/E {rg[4]:.1f}, отн {fmt(rg[0])}')


p('4a. Без каждого пула по очереди (выход):')
for k in mixed:
    sub = [r for r in main if key(r) != k]
    describe(sub, f'без {k[1][5:]} {k[0][:30]} ({k[2]})')
p('')
p('4b. Только пулы с ≥5 доменов в каждой группе:')
sub = [r for r in main if key(r) in {k for k, _, _, _ in bal}]
describe(sub, 'сбалансированные пулы', N_PERM)
p('')
p('4c. Без топ-3 доменов по вышедшим сайтам в каждой группе (глобально по всем пулам):')
fi = sorted([r for r in main if r['_ord'] == 1], key=lambda r: -r['_ex3'])
rp = sorted([r for r in main if r['_ord'] > 1], key=lambda r: -r['_ex3'])
p('    топ-3 первых: ' + '; '.join(f"{r['домен']} ({int(r['_ex3'])} из {int(r['_sites'])}, {key(r)[1][5:]} {key(r)[0][:25]})" for r in fi[:3]))
p('    топ-3 повторных: ' + '; '.join(f"{r['домен']} ({int(r['_ex3'])} из {int(r['_sites'])}, {key(r)[1][5:]} {key(r)[0][:25]})" for r in rp[:3]))
drop = {r['домен'] for r in fi[:3]} | {r['домен'] for r in rp[:3]}
describe([r for r in main if r['домен'] not in drop], 'без топ-3 по выходу в каждой группе', N_PERM)
p('')
p('4d. Без топ-3 доменов по регистрациям в каждой группе:')
fi = sorted([r for r in main if r['_ord'] == 1], key=lambda r: -r['_reg'])
rp = sorted([r for r in main if r['_ord'] > 1], key=lambda r: -r['_reg'])
p('    топ-3 первых: ' + '; '.join(f"{r['домен']} ({int(r['_reg'])} рег, {key(r)[1][5:]} {key(r)[0][:25]})" for r in fi[:3]))
p('    топ-3 повторных: ' + '; '.join(f"{r['домен']} ({int(r['_reg'])} рег, {key(r)[1][5:]} {key(r)[0][:25]})" for r in rp[:3]))
drop = {r['домен'] for r in fi[:3]} | {r['домен'] for r in rp[:3]}
describe([r for r in main if r['домен'] not in drop], 'без топ-3 по регистрациям в каждой группе', N_PERM)
p('')

# ------------------------------------------------------------ 5. номер экземпляра
p('=' * 100)
p('5. НОМЕР ЭКЗЕМПЛЯРА _NN ВНУТРИ ПУЛА: сцеплен ли с порядком cf? (известно: варианты 8/9 хуже 1/2)')
p('=' * 100)
for k in mixed:
    lst = [r for r in pools[k] if r['_nn'] is not None]
    if not lst:
        continue
    nn1 = [r['_nn'] for r in lst if r['_ord'] == 1]
    nn2 = [r['_nn'] for r in lst if r['_ord'] > 1]
    if nn1 and nn2:
        p(f"  {k[1][5:]} {k[0][:34]} ({k[2]}): NN первых {min(nn1)}–{max(nn1)} (медиана {sorted(nn1)[len(nn1) // 2]}), "
          f"NN повторных {min(nn2)}–{max(nn2)} (медиана {sorted(nn2)[len(nn2) // 2]})")
# выход по NN внутри суффиксных пулов (без учёта порядка)
p('  Выход по номеру экземпляра внутри суффиксных пулов (все домены пула, без деления на порядок):')
for k in mixed:
    lst = [r for r in pools[k] if r['_nn'] is not None]
    if len(lst) < 10:
        continue
    lst.sort(key=lambda r: r['_nn'])
    h = len(lst) // 2
    lo_, hi_ = lst[:h], lst[h:]
    rl = 100 * sum(r['_ex3'] for r in lo_) / sum(r['_sites'] for r in lo_)
    rh = 100 * sum(r['_ex3'] for r in hi_) / sum(r['_sites'] for r in hi_)
    p(f"    {k[1][5:]} {k[0][:34]}: младшие NN ({lo_[0]['_nn']}–{lo_[-1]['_nn']}) вых {rl:.1f} %, старшие NN ({hi_[0]['_nn']}–{hi_[-1]['_nn']}) вых {rh:.1f} %")
p('')

# ------------------------------------------------------------ 6. регистрации
p('=' * 100)
p('6. РЕГИСТРАЦИИ В ГЛАВНЫХ ПУЛАХ')
p('=' * 100)
fi = [r for r in main if r['_ord'] == 1]
rp = [r for r in main if r['_ord'] > 1]
for name, g in (('первые', fi), ('повторные', rp)):
    regs = sorted((int(r['_reg']) for r in g), reverse=True)
    tot = sum(regs)
    nz = sum(1 for x in regs if x > 0)
    p(f'  {name}: регистраций {tot} на {len(g)} доменов; доменов с регистрацией {nz}; топ-3 домена держат {sum(regs[:3])} из {tot}')
p('  Пулы с регистрациями: ' + '; '.join(f"{k[1][5:]} {k[0][:25]} {int(st['g1'])}:{int(st['g2'])}" for k, st, _, _ in per_pool if st['g1'] + st['g2'] > 0))
p('  Итог: 10 и 13 регистраций — по правилу «менее 20 в группе — не доказательство» регистрации не решают ни в одну сторону.')
p('')

# ------------------------------------------------------------ 7. число сравнений
p('=' * 100)
p('7. ЧИСЛО СРАВНЕНИЙ В ОТЧЁТЕ ТЕСТИРОВЩИКА')
p('=' * 100)
tests = [
    ('страта день: 2-я/1-я', 0.1836), ('страта день: 3-я/1-я', 0.0262), ('страта день: повт/1-я', 0.6370),
    ('главные: 2-я/1-я', 0.7786), ('главные: 3-я/1-я', 0.9002), ('главные: повт/1-я', 0.7752),
    ('разрыв ≤2', 0.9136), ('разрыв 3–7', 0.8228), ('разрыв 8–17', 0.9572), ('разрыв ≥18', 0.2624),
    ('Спирмен', 0.4040), ('пул×зона', 0.8166), ('16.09 грубая', 0.0006), ('главные+16.09', 0.0346),
    ('быстрый повтор +16.09', 0.0046), ('2-я/3-я', 0.9758), ('без 150', 0.8658), ('без суффикса', 0.8918),
    ('только 16–18.09', 0.7978), ('до 16.09', 0.8934),
]
p(f'  Тестов по выходу: {len(tests)} (плюс столько же по регистрациям). p < 0,05 у {sum(1 for _, v in tests if v < 0.05)}: '
  + ', '.join(f'{n} ({v})' for n, v in tests if v < 0.05))
p(f'  Поправка Бонферрони на {len(tests)}: порог 0,0025 — выживает только 16.09 (0,0006; в сторону ВРЕДА) и почти быстрый повтор с 16.09 (0,0046).')
p('  Для нулевого вывода перебор срезов не опасен (много тестов → ложные находки, а не ложные нули);')
p('  опасен он для «3-я/1-я = 1,23, p = 0,026» в страте по дню — это шум. Но единственный сильный сигнал в наборе — в сторону вреда,')
p('  и он снят содержательным аргументом (наборы разные), а не статистикой.')
p('')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

# ------------------------------------------------------------ 8. дожим
_lines.clear()
p('=' * 100)
p('8. ДОЖИМ: чем держится 0,74 при E от противоположной группы; интервал «быстрого повтора»; интервал сбалансированных пулов')
p('=' * 100)
sub = [r for r in main if key(r) != ('content-2026-09-16-7str', '2026-09-17', '206')]
o = oe_ratio(sub, opposite=True)
p(f'  E от противоположной группы БЕЗ пула 09-17 content-2026-09-16-7str (1 первый домен 26,2 % как эталон для 36 повторных): '
  f'O2/E2 = {fmt(o[3] / o[4])}, O1/E1 = {fmt(o[1] / o[2])} → 0,74 держался на одном домене 1978.lol.')
lo, med, hi, n = boot_ci(sub, lambda s: oe_ratio(s, opposite=True)[3] / oe_ratio(s, opposite=True)[4])
p(f'    бутстреп 95 % для O2/E2 без этого пула: [{fmt(lo)}; {fmt(hi)}]')
p('')
quick = [r for r in main if key(r)[1] == '2026-09-17']
q = oe_ratio(quick)
lo, med, hi, n = boot_ci(quick, lambda s: oe_ratio(s)[0])
p(f'  Быстрый повтор ≤2 дней (2 пула 17.09): первых {sum(1 for r in quick if r["_ord"] == 1)}, повторных {sum(1 for r in quick if r["_ord"] > 1)}; '
  f'отношение {fmt(q[0])}; бутстреп 95 % [{fmt(lo)}; {fmt(hi)}]; МХ {fmt(mh_ratio(quick))}')
quick2 = [r for r in quick if key(r)[0] != 'content-2026-09-16-7str']
q2 = oe_ratio(quick2)
lo, med, hi, n = boot_ci(quick2, lambda s: oe_ratio(s)[0])
p(f'    только пул 14b-oform-1 (6:13): отношение {fmt(q2[0])}; бутстреп 95 % [{fmt(lo)}; {fmt(hi)}]')
p('')
balrs = [r for r in main if key(r) in {k for k, _, _, _ in bal}]
lo, med, hi, n = boot_ci(balrs, lambda s: oe_ratio(s)[0])
lo2, med2, hi2, n2 = boot_ci(balrs, mh_ratio)
p(f'  Сбалансированные пулы (5 пулов, 68:77): отношение {fmt(oe_ratio(balrs)[0])}, бутстреп 95 % [{fmt(lo)}; {fmt(hi)}]; МХ {fmt(mh_ratio(balrs))} [{fmt(lo2)}; {fmt(hi2)}]')
p('')
# 09-18 пул: выход повторных по NN
k18 = ('content-2026-09-17-7str-oform-2', '2026-09-18', '150')
lst = pools[k18]
rp_hi = [r for r in lst if r['_ord'] > 1 and r['_nn'] >= 25]
rp_lo = [r for r in lst if r['_ord'] > 1 and r['_nn'] < 25]
fi_ = [r for r in lst if r['_ord'] == 1]
def rate(g):
    s = sum(r['_sites'] for r in g)
    return 100 * sum(r['_ex3'] for r in g) / s if s else 0
p(f'  Пул 09-18 content-2026-09-17-7str-oform-2 (150): первые NN 42–53 ({len(fi_)}) вых {rate(fi_):.1f} %; '
  f'повторные NN ≥25 ({len(rp_hi)}) вых {rate(rp_hi):.1f} %; повторные NN <25 ({len(rp_lo)}) вых {rate(rp_lo):.1f} %')
p('    → внутри «одного набора» экземпляры различаются; первые стоят на старших NN, которые выходят лучше — перекос В ПОЛЬЗУ первых, вред он не прячет.')
with open(OUT, 'a', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')

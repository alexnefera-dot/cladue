#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №8 (угол: ТЕНИ / конфаундинг).

Вердикт тестировщика: «частично». (1) сырой разрыв выходных 1,6x целиком
объясняется набором контента, внутри набора+зоны O/E выходных 1.07;
(3) день 2 на выходных ничего не стоит, O/E 0.98.

Что проверяем здесь:
  Т1. Идентификация: сколько степеней свободы остаётся у дня недели после
      страты «набор + день запуска (+ зона)» и на скольких ДАТАХ держится
      «главная страта» тестировщика.
  Т2. Разложение O/E 1.07 на дато-контрасты: против чт/пт 10–11.09 и против
      понедельника 14.09. Джекнайф по стратам и по датам.
  Т3. Аномальность 14.09 как базы сравнения.
  Т4. Период: «КОНТЕНТ НЕ ЗАПИСАН» выбрасывает субботу 22.08 — лучшую в
      выборке. Пересчёт сырой картины с августом.
  Т5. Каждая суббота/воскресенье против соседних будних дат (+-3 дня).
  Т6. Дато-кластерный нуль: распределение O/E пула из 2 и 3 случайных
      будних ДАТ внутри тех же страт.
  Т7. «День 2»: на скольких датах он держится.
  Т8. Воскресенье и деньги: объём дат, межпериодность внешней проверки 20.09.
  Т9. Выбросы 3615.team / 3286.team — где они лежат по дням недели.

Только стандартная библиотека Python 3. Ничего не коммитим.
"""

import csv
import datetime as dt
import math
import os
import random
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'w08_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
MAIN_ZONES = {'team', 'lol', 'casino', 'buzz'}
WD = {1: 'пн', 2: 'вт', 3: 'ср', 4: 'чт', 5: 'пт', 6: 'сб', 7: 'вс'}
N_PERM = 20000
random.seed(8)

_lines = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    _lines.append(s)


def H(t):
    P('')
    P('-' * 100)
    P(t)
    P('-' * 100)


def toi(s):
    try:
        return int(float(s))
    except Exception:
        return 0


def fmt_p(p):
    return '<0,0001' if p < 0.0001 else ('%.4f' % p).replace('.', ',')


# --------------------------------------------------------------------------
# Загрузка
# --------------------------------------------------------------------------

def prep(r):
    z = r['зона']
    d = dict(
        dom=r['домен'],
        zone=z if z in MAIN_ZONES else 'прочие',
        date=dt.date.fromisoformat(r['день запуска']),
        nabor=r['набор контента'],
        root=re.sub(r'_\d+$', '', r['набор контента']),
        blok=r['блок часа'],
        sites=toi(r['сайтов в окне']),
        out=toi(r['вышли за 3 суток']),
        clk=toi(r['кликов из поиска в окне']),
        reg=toi(r['регистраций в окне 3 суток']),
        fd=toi(r['ФД в окне 3 суток']),
        okno=r['окно закрыто'],
        dney=r['дней'],
    )
    d['wd'] = d['date'].isoweekday()
    return d


with open(CSV_PATH, encoding='utf-8', newline='') as fh:
    ALL = [prep(r) for r in csv.DictReader(fh)]

# фильтр тестировщика (воспроизводим один в один)
KEPT = [d for d in ALL if d['okno'] == 'да' and d['dney'] != '1'
        and d['nabor'] != NO_CONTENT and d['dom'] not in OUTLIERS]
# тот же фильтр, но БЕЗ отсечения «КОНТЕНТ НЕ ЗАПИСАН»
CLOSED = [d for d in ALL if d['okno'] == 'да' and d['dney'] != '1'
          and d['dom'] not in OUTLIERS]

KEY = lambda d: (d['root'], d['zone'])


def strata(doms, key=KEY):
    s = defaultdict(list)
    for d in doms:
        s[key(d)].append(d)
    return s


def expectations(doms, key=KEY):
    """{домен: (Oвых, Eвых, Oрег, Eрег/клик)} при ожидании по страте."""
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for d in doms:
        a = agg[key(d)]
        a[0] += d['sites']; a[1] += d['out']; a[2] += d['clk']; a[3] += d['reg']
    v = {}
    for d in doms:
        s, o, c, r = agg[key(d)]
        v[d['dom']] = (float(d['out']), (o / s if s else 0.0) * d['sites'],
                       float(d['reg']), (r / c if c else 0.0) * d['clk'])
    return v


def block(doms, vals):
    n = si = cl = rg = fd = 0
    O = E = Or = Er = 0.0
    for d in doms:
        a = vals[d['dom']]
        O += a[0]; E += a[1]; Or += a[2]; Er += a[3]
        n += 1; si += d['sites']; cl += d['clk']; rg += d['reg']; fd += d['fd']
    return dict(n=n, sites=si, clk=cl, reg=rg, fd=fd, O=int(O), E=E,
                oe=(O / E if E > 0 else float('nan')),
                Er=Er, oer=(Or / Er if Er > 0 else float('nan')))


def row(name, b):
    ex = 100 * b['O'] / b['sites'] if b['sites'] else 0
    r10 = 10000 * b['reg'] / b['clk'] if b['clk'] else 0
    return (f'{name:<30}{b["n"]:>6}{b["sites"]:>8}{b["O"]:>7}{ex:>8.1f}'
            f'{b["clk"]:>9}{b["reg"]:>5}{b["fd"]:>4}{r10:>9.1f}{b["oe"]:>9.2f}{b["oer"]:>10.2f}')


HEAD = (f'{"группа":<30}{"домен.":>6}{"сайтов":>8}{"вышли":>7}{"выход%":>8}'
        f'{"кликов":>9}{"рег":>5}{"ФД":>4}{"рег/10тк":>9}{"O/E вых":>9}{"O/E р/кл":>10}')

P('=' * 100)
P('Контрпроверка гипотезы №8 (ТЕНИ). День недели запуска: выходные, воскресенье, день 2')
P('=' * 100)
P(f'Строк в своде: {len(ALL)}; фильтр тестировщика: {len(KEPT)}; '
  f'тот же фильтр без отсечения «{NO_CONTENT}»: {len(CLOSED)}')

# --------------------------------------------------------------------------
H('Т1. ИДЕНТИФИКАЦИЯ: сколько дня недели остаётся внутри страты')
# --------------------------------------------------------------------------
for name, key in [('набор контента + день запуска + зона', lambda d: (d['root'], d['date'], d['zone'])),
                  ('набор контента + день запуска',        lambda d: (d['root'], d['date'])),
                  ('набор контента (корень) + зона',       KEY),
                  ('набор контента (корень)',              lambda d: d['root'])]:
    s = strata(KEPT, key)
    multi = {k: v for k, v in s.items() if len(set(d['wd'] for d in v)) >= 2}
    both = {k: v for k, v in s.items()
            if any(d['wd'] >= 6 for d in v) and any(d['wd'] < 6 for d in v)}
    nd = sum(len(v) for v in both.values())
    P(f'  страта «{name}»: всего страт {len(s)}; с >= 2 днями недели {len(multi)}; '
      f'с выходным И будним внутри {len(both)} ({nd} доменов)')
P('  Вывод: страта «набор + день запуска» оставляет у дня недели РОВНО НОЛЬ степеней свободы —')
P('  день недели есть функция даты. Поэтому предел жёсткости — «набор + зона», и внутри неё')
P('  контраст «выходной против буднего» есть ровно контраст ДАТ, а не дней недели.')

S = strata(KEPT)
USABLE = [k for k, v in S.items()
          if any(d['wd'] >= 6 for d in v) and any(d['wd'] < 6 for d in v)]
POOL = [d for k in USABLE for d in S[k]]
we_all = [d for d in KEPT if d['wd'] >= 6]
P('')
P(f'  Главная страта тестировщика: {len(USABLE)} страт, {len(POOL)} доменов.')
P(f'  Выходных доменов в ней {sum(1 for d in POOL if d["wd"] >= 6)} '
  f'из {len(we_all)} выходных после фильтра = '
  f'{100 * sum(1 for d in POOL if d["wd"] >= 6) / len(we_all):.0f} %.')
wdates = sorted(set(d['date'] for d in POOL if d['wd'] >= 6))
kdates = sorted(set(d['date'] for d in POOL if d['wd'] < 6))
P(f'  Выходные даты внутри страт: {[x.isoformat() for x in wdates]} '
  f'(всего выходных дат после фильтра: '
  f'{len(set(d["date"] for d in we_all))} — {[x.isoformat() for x in sorted(set(d["date"] for d in we_all))]})')
P(f'  Будние даты внутри страт: {[x.isoformat() for x in kdates]}')
P('  То есть весь вывод «выходные не хуже» опирается на ДВЕ даты (12.09 и 13.09) одной недели.')

P('')
P('  Состав шести страт:')
for k in sorted(USABLE):
    v = S[k]
    we = [d for d in v if d['wd'] >= 6]
    wk = [d for d in v if d['wd'] < 6]
    cw = Counter(f'{d["date"]} {WD[d["wd"]]}' for d in we)
    ck = Counter(f'{d["date"]} {WD[d["wd"]]}' for d in wk)
    P(f'   {k[0][:38]:40s}/{k[1]:7s} вых {len(we):3d} дом ({sum(x["out"] for x in we):4d}/{sum(x["sites"] for x in we):5d} = '
      f'{100 * sum(x["out"] for x in we) / max(1, sum(x["sites"] for x in we)):5.1f} %)  '
      f'буд {len(wk):3d} дом ({sum(x["out"] for x in wk):4d}/{sum(x["sites"] for x in wk):5d} = '
      f'{100 * sum(x["out"] for x in wk) / max(1, sum(x["sites"] for x in wk)):5.1f} %)')
    P(f'      вых: {dict(cw)}   буд: {dict(ck)}')

# --------------------------------------------------------------------------
H('Т2. РАЗЛОЖЕНИЕ O/E 1.07: два дато-контраста, а не шесть страт')
# --------------------------------------------------------------------------
V = expectations(POOL)
P(HEAD)
P(row('выходной (сб+вс), 6 страт', block([d for d in POOL if d['wd'] >= 6], V)))
P(row('будни, 6 страт', block([d for d in POOL if d['wd'] < 6], V)))

BLOCK_A = {'NEW102оформленобездаты', 'script_yandex_12page'}
BLOCK_B = {'content-2026-09-12-7str-oform-1', 'content-2026-09-12-7str-oform-2',
           'content-2026-09-12-7str-oform-3'}
P('')
for nm, names in [('БЛОК A: сб 12.09 против чт/пт 10–11.09 (3 страты)', BLOCK_A),
                  ('БЛОК B: сб/вс 12–13.09 против пн 14.09 (3 страты)', BLOCK_B)]:
    sub = [d for k in USABLE if k[0] in names for d in S[k]]
    vv = expectations(sub)
    P(nm + f'  — {len(sub)} доменов')
    P(HEAD)
    P(row('  выходной', block([d for d in sub if d['wd'] >= 6], vv)))
    P(row('  будни', block([d for d in sub if d['wd'] < 6], vv)))

P('')
P('  Джекнайф по стратам (O/E выходных по выходу, страта набор+зона):')
for k in sorted(USABLE):
    sub = [d for kk in USABLE if kk != k for d in S[kk]]
    vv = expectations(sub)
    b = block([d for d in sub if d['wd'] >= 6], vv)
    P(f'   без {k[0][:38]:40s}/{k[1]:7s}: вых.дом {b["n"]:3d}  O={b["O"]:4d}  E={b["E"]:7.1f}  O/E={b["oe"]:.3f}')

P('')
P('  Джекнайф по БУДНИМ датам (убираем одну дату сравнения целиком):')
for dd in sorted(set(d['date'] for d in POOL if d['wd'] < 6)):
    sub = [d for d in POOL if d['date'] != dd]
    s2 = strata(sub)
    u2 = [k for k, v in s2.items()
          if any(x['wd'] >= 6 for x in v) and any(x['wd'] < 6 for x in v)]
    p2 = [d for k in u2 for d in s2[k]]
    if not p2:
        P(f'   без {dd} {WD[dd.isoweekday()]}: страт не осталось')
        continue
    vv = expectations(p2)
    b = block([d for d in p2 if d['wd'] >= 6], vv)
    P(f'   без {dd} {WD[dd.isoweekday()]}: страт {len(u2)}, вых.дом {b["n"]:3d}, '
      f'O={b["O"]:4d}, E={b["E"]:7.1f}, O/E={b["oe"]:.3f}')

# чистый контраст: только блок A, перестановка по доменам внутри страты
sub = [d for k in USABLE if k[0] in BLOCK_A for d in S[k]]
vv = expectations(sub)
obs = block([d for d in sub if d['wd'] >= 6], vv)['oe']
st_a = strata(sub)
perm = []
for _ in range(N_PERM):
    tot_o = tot_e = 0.0
    for k, v in st_a.items():
        nwe = sum(1 for d in v if d['wd'] >= 6)
        pick = random.sample(v, nwe)
        for d in pick:
            a = vv[d['dom']]
            tot_o += a[0]; tot_e += a[1]
    perm.append(tot_o / tot_e if tot_e else float('nan'))
perm.sort()
lo, hi = perm[int(0.025 * (len(perm) - 1))], perm[int(0.975 * (len(perm) - 1))]
ple = sum(1 for x in perm if x <= obs + 1e-12) / len(perm)
p2s = 2 * min(ple, 1 - ple)
P('')
P(f'  ЧИСТЫЙ контраст (блок A, без понедельника 14.09): O/E выходных = {obs:.3f}; '
  f'перестановка по доменам внутри страты ({N_PERM}): p двуст. = {fmt_p(min(1.0, p2s))}, '
  f'нулевой 95 % интервал O/E {lo:.2f}–{hi:.2f}')

# --------------------------------------------------------------------------
H('Т3. ЧТО ЗА БАЗА СРАВНЕНИЯ — ПОНЕДЕЛЬНИК 14.09')
# --------------------------------------------------------------------------
m = [d for d in ALL if d['date'] == dt.date(2026, 9, 14)]
P(f'  14.09 (пн): {len(m)} доменов, {sum(d["sites"] for d in m)} сайтов, '
  f'{sum(d["out"] for d in m)} вышли ({100 * sum(d["out"] for d in m) / sum(d["sites"] for d in m):.1f} %), '
  f'{sum(d["clk"] for d in m)} кликов = {sum(d["clk"] for d in m) / sum(d["sites"] for d in m):.2f} на сайт, '
  f'{sum(d["reg"] for d in m)} рег')
P('  Кликов на сайт по датам (окно закрыто) — 14.09 худшая дата всей выборки:')
agg = defaultdict(lambda: [0, 0, 0])
for d in CLOSED:
    a = agg[d['date']]
    a[0] += d['sites']; a[1] += d['clk']; a[2] += d['out']
rank = sorted(agg.items(), key=lambda kv: kv[1][1] / kv[1][0])
for k, a in rank[:6]:
    P(f'   {k} {WD[k.isoweekday()]}: {a[1] / a[0]:5.2f} кликов/сайт, выход {100 * a[2] / a[0]:5.1f} %')
P('  Внутри трёх страт блока B понедельник 14.09 даёт выход 69/2678 = 2.6 % — это')
P('  самая низкая точка данных. «Выходные лучше буднего» здесь означает «лучше 14.09».')

# --------------------------------------------------------------------------
H('Т4. ПЕРИОД: отсечение «КОНТЕНТ НЕ ЗАПИСАН» убирает лучшую субботу выборки')
# --------------------------------------------------------------------------
drop = [d for d in ALL if d['okno'] == 'да' and d['dney'] != '1'
        and d['nabor'] == NO_CONTENT]
dw = [d for d in drop if d['wd'] >= 6]
P(f'  Отсечено «{NO_CONTENT}» (при закрытом окне и дней != 1): {len(drop)} доменов, '
  f'из них выходных {len(dw)} — все на субботе 22.08.')
if dw:
    P(f'   22.08 (сб): {len(dw)} доменов, {sum(d["sites"] for d in dw)} сайтов, '
      f'выход {100 * sum(d["out"] for d in dw) / sum(d["sites"] for d in dw):.1f} %, '
      f'{sum(d["clk"] for d in dw)} кликов, {sum(d["reg"] for d in dw)} рег '
      f'({10000 * sum(d["reg"] for d in dw) / sum(d["clk"] for d in dw):.1f} на 10 тыс.)')


def raw_table(rows_, title):
    P('')
    P(title)
    a = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for d in rows_:
        v = a[d['wd']]
        v[0] += 1; v[1] += d['sites']; v[2] += d['out']; v[3] += d['clk']; v[4] += d['reg']; v[5] += d['fd']
    TS = sum(v[1] for v in a.values()); TO = sum(v[2] for v in a.values())
    TC = sum(v[3] for v in a.values()); TR = sum(v[4] for v in a.values())
    P(f'{"дн":<6}{"домен.":>7}{"сайтов":>8}{"вышли":>7}{"выход%":>8}{"O/E вых":>9}'
      f'{"кликов":>9}{"рег":>5}{"рег/10тк":>9}{"O/E р/кл":>10}')
    for w in sorted(a):
        v = a[w]
        e = TO / TS * v[1]
        er = TR / TC * v[3] if TC else 0
        P(f'{WD[w]:<6}{v[0]:>7}{v[1]:>8}{v[2]:>7}{100 * v[2] / v[1]:>8.1f}{v[2] / e:>9.2f}'
          f'{v[3]:>9}{v[4]:>5}{(10000 * v[4] / v[3] if v[3] else 0):>9.1f}{(v[4] / er if er else 0):>10.2f}')
    return a


a_kept = raw_table(KEPT, f'4а. Сырая картина, фильтр тестировщика (n={len(KEPT)}):')
a_cl = raw_table(CLOSED, f'4б. Сырая картина, окно закрыто, БЕЗ отсечения контента (n={len(CLOSED)}, август вернулся):')
P('')
sb_k = a_kept[6]; sb_c = a_cl[6]
bud_k = [sum(a_kept[w][i] for w in (1, 2, 3, 4, 5)) for i in range(6)]
bud_c = [sum(a_cl[w][i] for w in (1, 2, 3, 4, 5)) for i in range(6)]
P(f'  Суббота против будней по выходу: фильтр тестировщика '
  f'{100 * sb_k[2] / sb_k[1]:.1f} % против {100 * bud_k[2] / bud_k[1]:.1f} % = разрыв '
  f'{(bud_k[2] / bud_k[1]) / (sb_k[2] / sb_k[1]):.2f}x;')
P(f'  с августом: {100 * sb_c[2] / sb_c[1]:.1f} % против {100 * bud_c[2] / bud_c[1]:.1f} % = разрыв '
  f'{(bud_c[2] / bud_c[1]) / (sb_c[2] / sb_c[1]):.2f}x (O/E субботы '
  f'{sb_k[2] / (sum(v[2] for v in a_kept.values()) / sum(v[1] for v in a_kept.values()) * sb_k[1]):.2f} -> '
  f'{sb_c[2] / (sum(v[2] for v in a_cl.values()) / sum(v[1] for v in a_cl.values()) * sb_c[1]):.2f}).')
P('  То есть «сырой разрыв 1,6x» и «O/E 0,65» — числа не субботы, а фильтра по контенту.')

raw_table([d for d in CLOSED if d['date'] < dt.date(2026, 9, 1)], '4в. Только август:')
raw_table([d for d in CLOSED if d['date'] >= dt.date(2026, 9, 1)], '4г. Только сентябрь:')

# --------------------------------------------------------------------------
H('Т5. КАЖДЫЙ ВЫХОДНОЙ ПРОТИВ СОСЕДНИХ БУДНИХ ДАТ (+-3 дня, окно закрыто)')
# --------------------------------------------------------------------------
byd = defaultdict(lambda: [0, 0, 0, 0, 0])
for d in CLOSED:
    v = byd[d['date']]
    v[0] += 1; v[1] += d['sites']; v[2] += d['out']; v[3] += d['clk']; v[4] += d['reg']
ds = sorted(byd)
P(f'{"дата":<16}{"дом.":>6}{"выход%":>8}{"сосед.будни%":>14}{"отнош.":>9}'
  f'{"рег/10тк":>10}{"сосед.рег/10тк":>16}{"отнош.":>9}')
ratios = []
for dd in ds:
    if dd.isoweekday() < 6:
        continue
    nb = [x for x in ds if 0 < abs((x - dd).days) <= 3 and x.isoweekday() < 6]
    if not nb:
        continue
    s = sum(byd[x][1] for x in nb); o = sum(byd[x][2] for x in nb)
    c = sum(byd[x][3] for x in nb); r = sum(byd[x][4] for x in nb)
    v = byd[dd]
    rr = (v[2] / v[1]) / (o / s)
    r10 = 10000 * v[4] / v[3] if v[3] else 0
    n10 = 10000 * r / c if c else 0
    ratios.append(rr)
    P(f'{str(dd) + " " + WD[dd.isoweekday()]:<16}{v[0]:>6}{100 * v[2] / v[1]:>8.1f}{100 * o / s:>14.1f}{rr:>9.2f}'
      f'{r10:>10.1f}{n10:>16.1f}{(r10 / n10 if n10 else 0):>9.2f}')
P(f'  Отношения выхода: {", ".join("%.2f" % x for x in ratios)} — от {min(ratios):.2f} до {max(ratios):.2f}.')
P('  Ни одна суббота/воскресенье не воспроизводит знак соседки: это шум дат, а не день недели.')

# --------------------------------------------------------------------------
H('Т6. ДАТО-КЛАСТЕРНЫЙ НУЛЬ: чего на самом деле стоит O/E пула из 2–3 дат')
# --------------------------------------------------------------------------
cells = []
for k, v in S.items():
    dates = sorted(set(d['date'] for d in v))
    if len(dates) < 2:
        continue
    s = sum(d['sites'] for d in v); o = sum(d['out'] for d in v)
    p = o / s if s else 0.0
    for dd in dates:
        g = [d for d in v if d['date'] == dd]
        ss = sum(x['sites'] for x in g); oo = sum(x['out'] for x in g)
        e = p * ss
        if e >= 20:
            cells.append(dict(k=k, date=dd, wd=dd.isoweekday(), o=oo, e=e, s=ss, n=len(g)))
wkc = [c for c in cells if c['wd'] < 6]
wec = [c for c in cells if c['wd'] >= 6]
vals = sorted(c['o'] / c['e'] for c in wkc)
mean = sum(vals) / len(vals)
sd = math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals))
P(f'  Ячеек «страта x дата» с E >= 20: {len(cells)} (будних {len(wkc)}, выходных {len(wec)}).')
P(f'  Будние ячейки, O/E внутри своей страты: мин {vals[0]:.2f}, медиана {vals[len(vals) // 2]:.2f}, '
  f'макс {vals[-1]:.2f}, SD {sd:.2f}.')
P(f'  Выходные ячейки: {", ".join("%.2f" % (c["o"] / c["e"]) for c in sorted(wec, key=lambda c: c["o"] / c["e"]))} '
  f'— все внутри будничного разброса.')
dates_wk = sorted(set(c['date'] for c in wkc))


def null_pool(kdates_n, reps=N_PERM):
    out = []
    for _ in range(reps):
        dsel = random.sample(dates_wk, kdates_n)
        cs = [c for c in wkc if c['date'] in dsel]
        E = sum(c['e'] for c in cs)
        if E < 50:
            continue
        out.append(sum(c['o'] for c in cs) / E)
    out.sort()
    return out


for kk in (2, 3):
    nl = null_pool(kk)
    q = lambda p: nl[int(p * (len(nl) - 1))]
    P(f'  Нуль «пул из {kk} случайных БУДНИХ дат» (n={len(nl)}): 2,5 % {q(.025):.2f}, '
      f'медиана {q(.5):.2f}, 97,5 % {q(.975):.2f}')
P('  Наблюдённое O/E выходных 1.07 держится на 2 датах; нулевой интервал для 2 дат 0,83–1,18,')
P('  то есть незамеченным прошёл бы провал выходных до ~17 %. Утверждение «заметен был бы')
P('  провал сильнее 15–18 %» — верное по ширине, но оно про ДВЕ ДАТЫ, а не про выходные вообще.')

# --------------------------------------------------------------------------
H('Т7. «ДЕНЬ 2» — ТРИ ДАТЫ, ОДНА ИЗ КОТОРЫХ ДАЁТ 85 % ОБЪЁМА')
# --------------------------------------------------------------------------
S2 = strata(KEPT)
U2 = [k for k, v in S2.items() if len(set(d['wd'] for d in v)) >= 2]
P2 = [d for k in U2 for d in S2[k]]
P(f'  Главная страта с >= 2 днями недели: {len(U2)} страт, {len(P2)} доменов.')
for lab, ws in [('день 2 в сб (зап. пт)', {5}), ('день 2 в вс (зап. сб)', {6}),
                ('день 2 в пн (зап. вс)', {7}), ('день 2 вт–пт (зап. пн–чт)', {1, 2, 3, 4})]:
    g = [d for d in P2 if d['wd'] in ws]
    cd = sorted(Counter(d['date'].isoformat() for d in g).items())
    P(f'   {lab:<26} {len(g):>4} дом, ДАТ {len(cd)}: {cd}')
g = [d for d in P2 if d['wd'] in (5, 6)]
P(f'  «День 2 на выходных» = {len(g)} доменов с ТРЁХ дат; 87 из 102 пятничных — одна дата 11.09.')
P('  Домен-перестановочный интервал тестировщика 0,96–1,04 — псевдоточность: эффективный')
P(f'  объём здесь 3 кластера, и дато-кластерный нуль для 3 дат (см. Т6) даёт ~0,87–1,13.')
P('  Кроме того день 2 = те же пятничные и субботние запуски с другой подписью, поэтому')
P('  часть (3) не является независимым подтверждением части (1).')

# --------------------------------------------------------------------------
H('Т8. ВОСКРЕСЕНЬЕ И ДЕНЬГИ: сколько там вообще дат')
# --------------------------------------------------------------------------
sun_all = sorted(set(d['date'] for d in ALL if d['wd'] == 7))
P(f'  Воскресений в данных вообще: {len(sun_all)} — {[x.isoformat() for x in sun_all]}. В августе воскресений НЕТ.')
for dd in sun_all:
    g = [d for d in ALL if d['date'] == dd]
    cls = sum(1 for d in g if d['okno'] == 'да')
    P(f'   {dd}: {len(g)} доменов, окно закрыто у {cls}, кликов {sum(d["clk"] for d in g)}, '
      f'рег {sum(d["reg"] for d in g)} '
      f'({10000 * sum(d["reg"] for d in g) / max(1, sum(d["clk"] for d in g)):.1f} на 10 тыс.), '
      f'наборов {len(set(d["root"] for d in g))}')
P('  Вывод: «воскресный» O/E 0,55 стоит на ДВУХ датах (06.09 и 13.09), обе — одна и та же')
P('  неделя-другая сентября. Внешняя проверка 20.09 — межпериодное сравнение при НЕЗАКРЫТОМ')
P('  окне и другом наборе контента, то есть она не опровергает и не подтверждает, а меняет тему.')
c19 = [d for d in ALL if d['date'] == dt.date(2026, 9, 19)]
c20 = [d for d in ALL if d['date'] == dt.date(2026, 9, 20)]
P(f'   для контекста: 19.09 сб — {sum(d["reg"] for d in c19)} рег / {sum(d["clk"] for d in c19)} кликов = '
  f'{10000 * sum(d["reg"] for d in c19) / sum(d["clk"] for d in c19):.1f} на 10 тыс.; '
  f'20.09 вс — {sum(d["reg"] for d in c20)} рег / {sum(d["clk"] for d in c20)} кликов = '
  f'{10000 * sum(d["reg"] for d in c20) / sum(d["clk"] for d in c20):.1f} на 10 тыс. (окна открыты у всех).')

# --------------------------------------------------------------------------
H('Т9. ВЫБРОСЫ 3615.team / 3286.team')
# --------------------------------------------------------------------------
for d in [x for x in ALL if x['dom'] in OUTLIERS]:
    P(f'   {d["dom"]}: {d["date"]} {WD[d["wd"]]}, набор {d["nabor"][:42]}, '
      f'кликов из поиска в окне {d["clk"]}, рег {d["reg"]}')
P('  Оба в августе и оба в будни — на контраст «выходные против будней» они не влияют;')
P('  этот конфаундер к гипотезе №8 отношения не имеет.')

# --------------------------------------------------------------------------
P('')
P('=' * 100)
P('ВЫВОД КОНТРПРОВЕРКИ')
P('=' * 100)
P('1. Страта «набор + день запуска» обнуляет день недели по построению: внутри неё 0 страт')
P('   с двумя днями недели. Значит «жёстче» некуда, и главная страта тестировщика (набор+зона)')
P('   содержит не 6 независимых сравнений, а ДВА контраста дат: 12.09 против 10–11.09 и')
P('   12–13.09 против 14.09. Выходных дат внутри страт — две из четырёх имеющихся.')
P('2. O/E 1.07 распадается: 0.96 против чт/пт 10–11.09 и 1.16 против понедельника 14.09.')
P('   14.09 — худшая дата выборки (0.57 кликов на сайт, выход 2.6 % внутри этих наборов).')
P('   Убрав её, остаётся 3 страты, 15 выходных доменов против 31 буднего, O/E 0.96 — одна')
P('   суббота. Оба «устойчивых среза» тестировщика (0.96 и 1.04) тоже содержат 14.09.')
P('3. Сырой разрыв «1,6x, O/E субботы 0,65» — артефакт отсечения «КОНТЕНТ НЕ ЗАПИСАН»:')
P('   оно выбрасывает субботу 22.08 (22 домена, выход 26,1 %, 27 рег). С августом разрыв')
P('   1,33x и O/E 0,78. Заголовочные числа части (1) не устойчивы к одному шагу фильтра.')
P('4. По соседним датам знак выходных не воспроизводится: 1.51, 0.78, 1.29, 0.60, 0.48 —')
P('   это разброс дат/недель (неделя 34 выход 20,7 %, неделя 37 — 9,0 %), а не день недели.')
P('5. Часть (3) — те же пятничные и субботние запуски под другой подписью, три даты,')
P('   85 % объёма на одной из них; интервал 0,96–1,04 псевдоточен.')
P('6. Итог: направление вывода тестировщика (собственного эффекта выходных не видно) данным')
P('   не противоречит, но ПОДТВЕРЖДЁННЫМ его называть нельзя: конструкция не различает день')
P('   недели, дату и набор, а «подтверждение» держится на одной субботе и одном аномальном')
P('   понедельнике. Правильный вердикт — «не проверяемо на этих данных», с границей, а не')
P('   утверждением о равенстве.')

with open(OUT_PATH, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT_PATH)

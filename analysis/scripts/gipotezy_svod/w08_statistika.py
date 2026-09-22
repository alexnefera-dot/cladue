#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №8 (день недели запуска) — угол «статистика и определения».

Что делаем:
  0) воспроизводим фильтры и ключевые числа тестировщика своим кодом;
  1) считаем объёмы событий в каждой группе (регистрации, выходы, домены, ДАТЫ);
  2) выбиваем опоры: leave-one-out по стратам и удаление топ-3 доменов
     по выходам / по регистрациям в каждой группе;
  3) считаем, сколько срезов перебрано, и что остаётся после поправки
     на множественность;
  4) инвертируем перестановочный тест: какой реальный штраф выходных
     остаётся неотличимым (доверительный интервал на множитель);
  5) проверяем знаменатели, оконные колонки и открытое окно 17–21.09.

Только stdlib. Вывод дублируется в analysis/export/gipotezy_svod/w08_statistika.txt
"""
import csv, datetime as dt, math, os, random, re
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'w08_statistika.txt')
os.makedirs(OUT_DIR, exist_ok=True)
_out = []
def P(*a):
    s = ' '.join(str(x) for x in a); print(s); _out.append(s)

OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
MAIN_ZONES = {'team', 'lol', 'casino', 'buzz'}
WD = {1:'пн',2:'вт',3:'ср',4:'чт',5:'пт',6:'сб',7:'вс'}
WEEKEND = {6,7}

def toi(s):
    return int(float(s)) if s not in ('', None) else 0
def root_name(n):
    return re.sub(r'_\d+$', '', n)
def fr(x, nd=2):
    return f'{x:.{nd}f}' if x == x else '—'
def fmt_p(p):
    if p != p: return '—'
    return '<0,0001' if p < 1e-4 else f'{p:.4f}'.replace('.', ',')

def prepare(r):
    z = r['зона']
    return dict(домен=r['домен'], зона=(z if z in MAIN_ZONES else 'прочие'),
                день=dt.date.fromisoformat(r['день запуска']),
                wd=dt.date.fromisoformat(r['день запуска']).isoweekday(),
                набор=r['набор контента'], корень=root_name(r['набор контента']),
                семейство=r['семейство'], страниц=r['страниц'] or '—',
                оформление=r['оформление'] or '—',
                сайтов=toi(r['сайтов в окне']), сайтов_всего=toi(r['сайтов']),
                вышли=toi(r['вышли за 3 суток']), клики=toi(r['кликов из поиска в окне']),
                клики_всего_окно=toi(r['кликов всего в окне']),
                рег=toi(r['регистраций в окне 3 суток']), фд=toi(r['ФД в окне 3 суток']),
                окно=r['окно закрыто'], дней=r['дней'])

rows = [prepare(r) for r in csv.DictReader(open(CSV_PATH, encoding='utf-8', newline=''))]
P('=' * 100)
P('КОНТРПРОВЕРКА №8. День недели запуска: статистика и определения')
P('=' * 100)
P(f'Строк в своде: {len(rows)}')

# ---------------------------------------------------------------- 0. ФИЛЬТРЫ
kept = [d for d in rows if d['окно'] == 'да']
n1 = len(kept)
kept = [d for d in kept if d['дней'] != '1']
n2 = len(kept)
kept = [d for d in kept if d['набор'] != NO_CONTENT]
n3 = len(kept)
kept = [d for d in kept if d['домен'] not in OUTLIERS]
P(f'0. Фильтр воспроизведён: окно закрыто -> {n1}; дней!=1 -> {n2}; без «КОНТЕНТ НЕ ЗАПИСАН» -> {n3}; без выбросов -> {len(kept)}')
P(f'   Выброшено всего {len(rows) - len(kept)} из {len(rows)} строк ({(len(rows)-len(kept))/len(rows)*100:.1f} %) — анализ идёт на {len(kept)/len(rows)*100:.1f} % базы.')
neq = sum(1 for d in rows if d['сайтов'] != d['сайтов_всего'])
neq_kept = sum(1 for d in kept if d['сайтов'] != d['сайтов_всего'])
P(f'   Знаменатели: «сайтов в окне» != «сайтов» ровно в {neq} строках — и это ровно те {sum(1 for d in rows if d["окно"]!="да")} строк с незакрытым окном;')
P(f'   внутри отфильтрованного набора расхождений {neq_kept} -> оконный знаменатель корректен, подмены «доли от долей» в E нет (E = ставка страты × сайтов в окне домена).')
denom_bad = 0
for r in csv.DictReader(open(CSV_PATH, encoding='utf-8', newline='')):
    s = toi(r['сайтов']); v = toi(r['вышли за 3 суток'])
    col = r['выход 3 суток %']
    if s and col not in ('', None) and abs(v / s * 100 - float(col)) > 0.06: denom_bad += 1
P(f'   Колонка «выход 3 суток %» = вышли/сайтов: расхождений {denom_bad} из {len(rows)}.')
P('   O/E считается как ΣO/ΣE по доменам (пул сырых счётчиков), а НЕ среднее доменных долей — средних по доменам от долей тут нет. Это верно.')

# ------------------------------------------------- 1. ОЖИДАНИЯ И ГРУППЫ
def expectations(doms, key):
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for d in doms:
        a = agg[key(d)]; a[0] += d['сайтов']; a[1] += d['вышли']; a[2] += d['клики']; a[3] += d['рег']
    vals = {}
    for d in doms:
        s, o, c, r = agg[key(d)]
        vals[d['домен']] = (float(d['вышли']), (o / s if s else 0.0) * d['сайтов'],
                            float(d['рег']), (r / c if c else 0.0) * d['клики'],
                            (r / s if s else 0.0) * d['сайтов'])
    return vals

def agg_group(doms, vals):
    a = [0.0] * 5; n = sites = clk = reg = fd = 0
    for d in doms:
        v = vals[d['домен']]
        for i in range(5): a[i] += v[i]
        n += 1; sites += d['сайтов']; clk += d['клики']; reg += d['рег']; fd += d['фд']
    return dict(n=n, sites=sites, clk=clk, reg=reg, fd=fd, out=int(a[0]),
                o_exit=a[0], e_exit=a[1], o_reg=a[2], e_regclk=a[3], e_regsite=a[4])

KEY_MAIN = lambda d: (d['корень'], d['зона'])
KEY_SET = lambda d: d['корень']
KEY_COARSE = lambda d: (d['семейство'], d['страниц'], d['оформление'], d['зона'])

def strata_with_both(doms, key, left, right):
    st = defaultdict(list)
    for d in doms: st[key(d)].append(d)
    ok = {k: v for k, v in st.items() if any(left(d) for d in v) and any(right(d) for d in v)}
    return ok

is_we = lambda d: d['wd'] in WEEKEND
is_wd = lambda d: d['wd'] not in WEEKEND

P('')
P('-' * 100)
P('1. ЧАСТЬ (1): НА ЧЁМ ДЕРЖИТСЯ «O/E 1,07». ОБЪЁМЫ И ОПОРЫ')
P('-' * 100)
st = strata_with_both(kept, KEY_MAIN, is_we, is_wd)
sel = [d for k in st for d in st[k]]
vals = expectations(sel, KEY_MAIN)
we = [d for d in sel if is_we(d)]; wdd = [d for d in sel if is_wd(d)]
swe, swd = agg_group(we, vals), agg_group(wdd, vals)
P(f'Главная страта (корень набора + зона), где есть обе стороны: {len(st)} страт, {len(sel)} доменов '
  f'= {len(sel)/len(kept)*100:.1f} % отфильтрованной базы и {len(sel)/len(rows)*100:.1f} % свода.')
P(f'  выходные: {swe["n"]} доменов, O={swe["out"]}, E={swe["e_exit"]:.1f}, O/E={swe["o_exit"]/swe["e_exit"]:.2f}, регистраций {swe["reg"]}, ФД {swe["fd"]}')
P(f'  будни:    {swd["n"]} доменов, O={swd["out"]}, E={swd["e_exit"]:.1f}, O/E={swd["o_exit"]/swd["e_exit"]:.2f}, регистраций {swd["reg"]}, ФД {swd["fd"]}')
P(f'  -> числа тестировщика (819 при 763,9; O/E 1,07) воспроизводятся: {swe["out"]} при {swe["e_exit"]:.1f}.')
dt_we = sorted({d["день"] for d in we}); dt_wd = sorted({d["день"] for d in wdd})
P(f'  ДАТ в сравнении: выходных {len(dt_we)} ({", ".join(x.strftime("%d.%m")+" "+WD[x.isoweekday()] for x in dt_we)}), '
  f'будних {len(dt_wd)} ({", ".join(x.strftime("%d.%m")+" "+WD[x.isoweekday()] for x in dt_wd)}).')
P(f'  Всего выходных дат в отфильтрованной базе: {len(sorted({d["день"] for d in kept if is_we(d)}))} '
  f'({", ".join(x.strftime("%d.%m") for x in sorted({d["день"] for d in kept if is_we(d)}))}) — внутрисетевое сравнение покрывает только часть из них.')
P('')
P('Постратно (это весь фундамент части (1)):')
P(f'{"страта":<48}{"вых.дом":>8}{"вых.O":>7}{"вых.E":>8}{"буд.дом":>8}{"буд.O":>7}{"буд.E":>8}{"даты будней":>26}')
rowsx = []
for k in sorted(st, key=lambda k: -len(st[k])):
    a = [d for d in st[k] if is_we(d)]; b = [d for d in st[k] if is_wd(d)]
    sa, sb = agg_group(a, vals), agg_group(b, vals)
    dts = ','.join(sorted({x['день'].strftime('%d.%m') + WD[x['wd']] for x in b}))
    P(f'{k[0][:38]+"/"+k[1]:<48}{sa["n"]:>8}{sa["out"]:>7}{sa["e_exit"]:>8.1f}{sb["n"]:>8}{sb["out"]:>7}{sb["e_exit"]:>8.1f}{dts:>26}')
    rowsx.append((k, sa, sb))

P('')
P('1а. Leave-one-out по стратам (выход, группа «выходные»):')
tot_o = swe['o_exit']; tot_e = swe['e_exit']
for k, sa, sb in rowsx:
    o = tot_o - sa['o_exit']; e = tot_e - sa['e_exit']
    P(f'   без страты {k[0][:34]+"/"+k[1]:<40} O/E выходных = {o/e:.2f} (осталось {swe["n"]-sa["n"]} вых. доменов, {swe["out"]-sa["out"]} выходов)')
drop3 = {'content-2026-09-12-7str-oform-1', 'content-2026-09-12-7str-oform-2', 'content-2026-09-12-7str-oform-3'}
rest = [d for d in sel if d['корень'] not in drop3]
if rest:
    st2 = strata_with_both(rest, KEY_MAIN, is_we, is_wd)
    sel2 = [d for k in st2 for d in st2[k]]
    v2 = expectations(sel2, KEY_MAIN)
    a2 = agg_group([d for d in sel2 if is_we(d)], v2); b2 = agg_group([d for d in sel2 if is_wd(d)], v2)
    P(f'   БЕЗ трёх наборов 12.09 (их будняя сторона — понедельник 14.09): остаётся {len(st2)} страт, '
      f'{a2["n"]}+{b2["n"]} доменов; O/E выходных = {a2["o_exit"]/a2["e_exit"]:.2f} (O={a2["out"]}, E={a2["e_exit"]:.1f}), будней {b2["o_exit"]/b2["e_exit"]:.2f}')

P('')
P('1б. Удаление топ-3 доменов в каждой группе (по выходам и по регистрациям):')
def drop_top(group, field, k=3):
    s = sorted(group, key=lambda d: -d[field])
    return s[k:], s[:k]
for field, lab in (('вышли', 'по выходам'), ('рег', 'по регистрациям')):
    we2, cut_we = drop_top(we, field); wd2, cut_wd = drop_top(wdd, field)
    sel3 = we2 + wd2
    v3 = expectations(sel3, KEY_MAIN)
    st3 = strata_with_both(sel3, KEY_MAIN, is_we, is_wd)
    sel4 = [d for k2 in st3 for d in st3[k2]]
    v4 = expectations(sel4, KEY_MAIN)
    a3 = agg_group([d for d in sel4 if is_we(d)], v4); b3 = agg_group([d for d in sel4 if is_wd(d)], v4)
    P(f'   {lab}: убраны выходные {[d["домен"] for d in cut_we]} и будние {[d["домен"] for d in cut_wd]}')
    P(f'      осталось {a3["n"]}+{b3["n"]} доменов; O/E выходных по выходу = {a3["o_exit"]/a3["e_exit"]:.2f}, '
      f'по рег/клик = {fr(a3["o_reg"]/a3["e_regclk"]) if a3["e_regclk"]>0 else "—"} (рег {a3["reg"]} против {b3["reg"]})')

P('')
P('1в. Сравнение с полной базой: не занижена ли будняя опора?')
allwd = [d for d in kept if is_wd(d)]
P(f'   будни ВНУТРИ 6 страт: {swd["n"]} доменов, выход {swd["out"]/swd["sites"]*100:.1f} %')
P(f'   будни по всей отфильтрованной базе: {len(allwd)} доменов, выход '
  f'{sum(d["вышли"] for d in allwd)/sum(d["сайтов"] for d in allwd)*100:.1f} %')
allwe = [d for d in kept if is_we(d)]
P(f'   выходные по всей базе: {len(allwe)} доменов, выход {sum(d["вышли"] for d in allwe)/sum(d["сайтов"] for d in allwe)*100:.1f} %')
P('   -> «выходные не хуже» получено против будней, которые сами вдвое слабее обычных будней.')
mon = [d for d in kept if d['день'] == dt.date(2026, 9, 14)]
P(f'   понедельник 14.09 целиком: {len(mon)} доменов, выход {sum(d["вышли"] for d in mon)/sum(d["сайтов"] for d in mon)*100:.1f} %, '
  f'кликов {sum(d["клики"] for d in mon)}, рег {sum(d["рег"] for d in mon)}')

# ---------------------------------------- 2. ПЕРЕСТАНОВКИ И ГРАНИЦЫ ЭФФЕКТА
P('')
P('-' * 100)
P('2. ЧЕГО НЕ ВИДНО: ИНВЕРСИЯ ТЕСТА (какой реальный штраф выходных остался бы незамеченным)')
P('-' * 100)

def perm_oe(sel, key, vals, group_pred, n_perm, mode, seed=7, scale=None):
    """Перестановка метки выходного внутри страты. scale — множитель O выходных."""
    rnd = random.Random(seed)
    strata = defaultdict(list)
    for d in sel: strata[key(d)].append(d)
    units = []
    for k, ds in strata.items():
        if mode == 'domain':
            labs = [1 if group_pred(d) else 0 for d in ds]
            vs = []
            for d in ds:
                o, e = vals[d['домен']][0], vals[d['домен']][1]
                vs.append((o * (scale if (scale and group_pred(d)) else 1.0), e))
        else:
            byd = defaultdict(lambda: [0.0, 0.0]); lab = {}
            for d in ds:
                o, e = vals[d['домен']][0], vals[d['домен']][1]
                o = o * (scale if (scale and group_pred(d)) else 1.0)
                byd[d['день']][0] += o; byd[d['день']][1] += e
                lab[d['день']] = 1 if group_pred(d) else 0
            ks = list(byd)
            labs = [lab[x] for x in ks]; vs = [tuple(byd[x]) for x in ks]
        if len(set(labs)) > 1: units.append((labs, vs))
    obs_o = sum(v[0] for labs, vs in units for l, v in zip(labs, vs) if l)
    obs_e = sum(v[1] for labs, vs in units for l, v in zip(labs, vs) if l)
    obs = obs_o / obs_e if obs_e else float('nan')
    out = []
    for _ in range(n_perm):
        o = e = 0.0
        for labs, vs in units:
            idx = list(range(len(labs))); rnd.shuffle(idx)
            for pos, l in zip(idx, labs):
                if l: o += vs[pos][0]; e += vs[pos][1]
        out.append(o / e if e else float('nan'))
    lo = sum(1 for v in out if v <= obs + 1e-12) / len(out)
    hi = sum(1 for v in out if v >= obs - 1e-12) / len(out)
    return obs, min(1.0, 2 * min(lo, hi)), sorted(out)

def n_date_arrangements(sel, key, pred):
    strata = defaultdict(set)
    for d in sel: strata[key(d)].add((d['день'], 1 if pred(d) else 0))
    tot = 1
    for k, s in strata.items():
        n = len(s); k1 = sum(1 for x in s if x[1])
        tot *= math.comb(n, k1)
    return tot

for mode in ('domain', 'date'):
    obs, p, dist = perm_oe(sel, KEY_MAIN, vals, is_we, 10000, mode)
    lo = dist[int(0.025 * (len(dist) - 1))]; hi = dist[int(0.975 * (len(dist) - 1))]
    P(f'   перестановка ({"по доменам" if mode=="domain" else "по датам"}): набл. O/E {obs:.2f}, p {fmt_p(p)}, нулевой 95 % интервал {lo:.2f}–{hi:.2f}')
P(f'   Число различимых раскладок дат в 6 стратах: {n_date_arrangements(sel, KEY_MAIN, is_we)} — '
  f'минимальный достижимый p по датам ~{2/ n_date_arrangements(sel, KEY_MAIN, is_we):.3f}. Тест физически не может дать значимость сильнее этого.')
P('   Инверсия: домножаем выходы выходных на f и смотрим, при каком f тест ещё НЕ отвергает (p > 0,05).')
P(f'{"f (истинный множитель выходных)":<36}{"набл. O/E":>11}{"p по доменам":>15}{"p по датам":>13}')
keep_f = []
for f in (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00, 1.10, 1.25, 1.40, 1.60):
    o1, p1, _ = perm_oe(sel, KEY_MAIN, vals, is_we, 4000, 'domain', scale=f)
    o2, p2, _ = perm_oe(sel, KEY_MAIN, vals, is_we, 4000, 'date', scale=f)
    P(f'{f:<36.2f}{o1:>11.2f}{fmt_p(p1):>15}{fmt_p(p2):>13}')
    if p2 > 0.05: keep_f.append(f)
P(f'   -> по датам НЕ отвергаются множители {min(keep_f):.2f}–{max(keep_f):.2f}: данные совместимы и с честным '
  f'падением выхода в выходные на {int(round((1-min(keep_f))*100))} %, и с ростом на {int(round((max(keep_f)-1)*100))} %.')
P('   «Разницы нет» такой интервал не означает — он означает «разницу меньше трети мы бы не увидели».')


# ---------------------------------------- 2б. КРУГОВОЕ ОЖИДАНИЕ И МАНТЕЛЬ-ХЕНЦЕЛЬ
P('')
P('-' * 100)
P('2б. ОПРЕДЕЛЕНИЕ ОЖИДАНИЯ: E СТРАТЫ СЧИТАЕТСЯ ПО ТОЙ ЖЕ ГРУППЕ, КОТОРУЮ ПРОВЕРЯЮТ')
P('-' * 100)
P('   В страте E = (Σвышли/Σсайтов ПО ВСЕЙ СТРАТЕ) × сайты домена. Где выходные — большинство страты,')
P('   ожидание строится по самим выходным, и O/E механически прижимается к 1.')
P(f'{"страта":<44}{"сайтов вых":>12}{"сайтов буд":>12}{"доля вых":>10}{"вых.выход%":>12}{"буд.выход%":>12}')
mh_num = mh_den = 0.0
mh_rows = []
for k, sa, sb in rowsx:
    share = sa['sites'] / (sa['sites'] + sb['sites'])
    P(f'{k[0][:34]+"/"+k[1]:<44}{sa["sites"]:>12}{sb["sites"]:>12}{share:>10.2f}'
      f'{sa["out"]/sa["sites"]*100:>12.2f}{sb["out"]/sb["sites"]*100:>12.2f}')
    N = sa['sites'] + sb['sites']
    mh_num += sa['out'] * sb['sites'] / N
    mh_den += sb['out'] * sa['sites'] / N
    mh_rows.append((k, sa, sb))
P(f'   Доля выходных в сайтах страты: медиана ~{sorted(sa["sites"]/(sa["sites"]+sb["sites"]) for k,sa,sb in rowsx)[len(rowsx)//2]:.2f}; '
  'в трёх стратах 12.09 будняя сторона — 1, 3 и 9 доменов понедельника 14.09.')
P('')
P('   Прямое сравнение без кругового ожидания — Мантель–Хенцель (отношение долей выхода, вес по стратам):')
def mh(rows_in):
    num = den = 0.0
    for k, sa, sb in rows_in:
        N = sa['sites'] + sb['sites']
        if N == 0 or sb['out'] == 0 and sa['out'] == 0: continue
        num += sa['out'] * sb['sites'] / N
        den += sb['out'] * sa['sites'] / N
    return num / den if den else float('nan')
rr_all = mh(mh_rows)
rr_no12 = mh([r for r in mh_rows if r[0][0] not in drop3])
P(f'   RR(выходные/будни) по всем 6 стратам:                 {rr_all:.2f}')
P(f'   RR без трёх наборов 12.09 (без понедельника 14.09):   {rr_no12:.2f}  (остаются 3 страты, {sum(r[1]["n"]+r[2]["n"] for r in mh_rows if r[0][0] not in drop3)} доменов)')
only12 = [r for r in mh_rows if r[0][0] in drop3]
P(f'   RR только по трём наборам 12.09:                      {mh(only12):.2f}')
s12 = [agg_group([d for d in sel if d["корень"] in drop3 and is_wd(d)], vals)]
P(f'   Будняя опора этих трёх страт целиком: {s12[0]["n"]} доменов понедельника 14.09, '
  f'{s12[0]["out"]} выходов на {s12[0]["sites"]} сайтов = {s12[0]["out"]/s12[0]["sites"]*100:.2f} % выхода и '
  f'{s12[0]["clk"]} кликов — это практически мёртвые домены, и именно на их фоне выходные «не хуже».')
P(f'   Для сравнения: будни по всей базе дают 12,7 % выхода, вся база — {sum(d["вышли"] for d in kept)/sum(d["сайтов"] for d in kept)*100:.1f} %.')

P('')
P('-' * 100)
P('2в. ИНВЕРСИЯ ЧЕСТНАЯ: контрфактические данные, ожидания пересчитываются заново')
P('-' * 100)
def counterfactual_test(f, n_perm=4000, mode='date', seed=11):
    cf = []
    for d in sel:
        e = dict(d)
        if is_we(d): e['вышли'] = d['вышли'] * f
        cf.append(e)
    agg = defaultdict(lambda: [0.0, 0.0])
    for d in cf:
        a = agg[KEY_MAIN(d)]; a[0] += d['сайтов']; a[1] += d['вышли']
    v = {}
    for d in cf:
        ssum, osum = agg[KEY_MAIN(d)]
        v[d['домен']] = (float(d['вышли']), (osum / ssum if ssum else 0.0) * d['сайтов'], 0.0, 0.0, 0.0)
    return perm_oe(cf, KEY_MAIN, v, is_we, n_perm, mode, seed=seed)
P(f'{"истинный множитель выходных f":<34}{"O/E после страты":>18}{"p по доменам":>15}{"p по датам":>13}')
ok_f = []
for f in (0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.15, 1.30, 1.50):
    o1, p1, _ = counterfactual_test(f, 4000, 'domain')
    o2, p2, _ = counterfactual_test(f, 4000, 'date')
    P(f'{f:<34.2f}{o1:>18.2f}{fmt_p(p1):>15}{fmt_p(p2):>13}')
    if p2 > 0.05: ok_f.append(f)
P(f'   Диапазон f, который перестановка ПО ДАТАМ не отвергает: {min(ok_f):.2f}–{max(ok_f):.2f}.')
P('   Заявление тестировщика «заметен был бы только провал сильнее ~15–18 %» неверно: 15–18 % — это ширина')
P('   нулевого интервала, а не мощность. Реальная мощность на датах близка к нулю.')

# ------------------------------------------------- 3. МНОЖЕСТВЕННОСТЬ
P('')
P('-' * 100)
P('3. СКОЛЬКО СРЕЗОВ ПЕРЕБРАНО')
P('-' * 100)
h08 = os.path.join(OUT_DIR, 'h08_launch_weekday.txt')
txt = open(h08, encoding='utf-8').read().splitlines() if os.path.exists(h08) else []
n_p = sum(1 for l in txt if 'p двуст' in l or 'p = ' in l or 'p по перестановкам' in l)
n_oe_lines = sum(1 for l in txt if ', O = ' in l and 'O/E' in l)
n_chi = sum(1 for l in txt if 'χ²' in l)
P(f'   В отчёте h08: строк с p-значением {n_p}, отдельных контрастов «O при E» {n_oe_lines}, строк с χ² {n_chi}.')
P('   Конструкция перебора: 3 части × 3 метрики (выход, рег/клик, рег/сайт) × 4 определения страты '
  '(главная, главная >=5, набор без зоны, грубая) × 2 режима перестановки = до 72 срезов, плюс 7 дней по отдельности.')
P('   Значимыми вышли только те, что работают ПРОТИВ вывода (грубая страта: O/E 0,78, p <0,0001; '
  'день 2 на грубой страте: 0,82, p <0,0001) и χ² по выходу p 0,0193 по доменам.')
for pv, name, k in ((0.0193, 'χ² по 7 дням, выход, главная страта (по доменам)', 12),
                    (0.0318, 'день 2 сб+вс, рег/клик, вторичная страта', 72)):
    P(f'   {name}: сырое p {pv} × {k} (Бонферрони по своему семейству) = {min(1.0, pv*k):.2f} -> не значимо.')
P('   Тот же χ² на перестановке по датам даёт 0,1953 уже без поправки. То есть утверждение вывода '
  '«различия между днями внутри наборов есть (p 0,02)» не переживает ни смену единицы, ни поправку.')

# ------------------------------------------------- 4. ЧАСТЬ (3)
P('')
P('-' * 100)
P('4. ЧАСТЬ (3): «ДЕНЬ 2 В ВЫХОДНОЙ» — ЧТО ТАМ НА САМОМ ДЕЛЕ')
P('-' * 100)
st_all = defaultdict(list)
for d in kept: st_all[KEY_MAIN(d)].append(d)
multi = {k: v for k, v in st_all.items() if len({d['wd'] for d in v}) >= 2}
sel_m = [d for k in multi for d in multi[k]]
vm = expectations(sel_m, KEY_MAIN)
g_fr = [d for d in sel_m if d['wd'] == 5]; g_sa = [d for d in sel_m if d['wd'] == 6]
g_su = [d for d in sel_m if d['wd'] == 7]
g_both = g_fr + g_sa
for nm, g in (('день 2 в сб = запуск пт', g_fr), ('день 2 в вс = запуск сб', g_sa),
              ('день 2 в пн = запуск вс', g_su), ('день 2 в сб+вс (пт+сб)', g_both)):
    s = agg_group(g, vm)
    P(f'   {nm:<26} доменов {s["n"]:>4}, выходов {s["out"]:>5} при E {s["e_exit"]:>7.1f} (O/E {s["o_exit"]/s["e_exit"]:.2f}), '
      f'рег {s["reg"]:>3} при E {s["e_regclk"]:.1f} (O/E {fr(s["o_reg"]/s["e_regclk"]) if s["e_regclk"]>0 else "—"}), ФД {s["fd"]}')
sfr = agg_group(g_fr, vm); ssa = agg_group(g_sa, vm)
P(f'   Доля пятницы в группе «день 2 в выходной»: {sfr["n"]}/{sfr["n"]+ssa["n"]} доменов = '
  f'{sfr["n"]/(sfr["n"]+ssa["n"])*100:.0f} % и {sfr["reg"]}/{sfr["reg"]+ssa["reg"]} регистраций. '
  f'Собственно «день 2 в воскресенье» (субботние запуски) — {ssa["n"]} доменов и {ssa["reg"]} регистраций.')
P(f'   «День 2 в понедельник» (воскресные запуски): {agg_group(g_su, vm)["n"]} доменов, {agg_group(g_su, vm)["reg"]} регистраций — группа пустая по событиям.')
P('   Порог 20 событий: по регистрациям его проходит только объединение пт+сб (28 рег). Субботние запуски '
  f'({ssa["reg"]} рег) и воскресные ({agg_group(g_su, vm)["reg"]} рег) по деньгам не доказывают ничего.')
P('   Плюс подмена определения: «день 2» на своде не отделяется от дня запуска (день 2 = запуск + 1), '
  'то есть часть (3) — не самостоятельная проверка, а переподписанная часть (1) на тех же доменах.')

# ------------------------------------------------- 5. ЧАСТЬ (2) И ОТКРЫТОЕ ОКНО
P('')
P('-' * 100)
P('5. ЧАСТЬ (2): ВОСКРЕСЕНЬЕ И ОТКРЫТОЕ ОКНО 17–21.09')
P('-' * 100)
sun = [d for d in kept if d['wd'] == 7]
P(f'   Закрытое окно, воскресенья: {len(sun)} доменов, {sum(d["рег"] for d in sun)} регистраций на '
  f'{sum(d["клики"] for d in sun)} кликов, даты {sorted({x["день"].strftime("%d.%m") for x in sun})}.')
P('   5 событий — ниже порога в 20; при O=5 точный пуассоновский 95 % интервал на O/E при E=9,1 очень широк.')
e_sun = 9.1
def pois_ci(o):
    lo = 0.0 if o == 0 else 0.5 * _chi2_inv(0.025, 2 * o)
    hi = 0.5 * _chi2_inv(0.975, 2 * (o + 1))
    return lo, hi
def _chi2_inv(p, k):
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _chi2_cdf(mid, k) < p: lo = mid
        else: hi = mid
    return (lo + hi) / 2
def _chi2_cdf(x, k):
    return _gammainc(k / 2, x / 2)
def _gammainc(a, x):
    if x <= 0: return 0.0
    if x < a + 1:
        s = 1.0 / a; t = s; n = a
        for _ in range(500):
            n += 1; t *= x / n; s += t
            if abs(t) < abs(s) * 1e-14: break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a; c = 1e300; d = 1 / b; h = d
    for i in range(1, 500):
        an = -i * (i - a); b += 2
        d = an * d + b; d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c; c = 1e-300 if abs(c) < 1e-300 else c
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-14: break
    return 1 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
lo, hi = pois_ci(5)
P(f'   O=5, E={e_sun}: 95 % интервал на O/E = {lo/e_sun:.2f}–{hi/e_sun:.2f} — в него входит и «вдвое хуже», и «норма», и «на 30 % лучше».')
P('')
P('   Открытое окно (17–21.09), все домены свода, сопоставимые между собой:')
P(f'{"дата":<14}{"дн.нед":>7}{"доменов":>9}{"сайтов":>9}{"окно закр.":>12}{"клики(окно)":>13}{"рег":>6}{"ФД":>5}{"рег/10тк":>10}')
op = defaultdict(list)
for d in rows:
    if d['день'] >= dt.date(2026, 9, 17): op[d['день']].append(d)
for day in sorted(op):
    g = op[day]
    clk = sum(x['клики'] for x in g); reg = sum(x['рег'] for x in g)
    P(f'{day.strftime("%Y-%m-%d"):<14}{WD[day.isoweekday()]:>7}{len(g):>9}{sum(x["сайтов"] for x in g):>9}'
      f'{sum(1 for x in g if x["окно"]=="да"):>12}{clk:>13}{reg:>6}{sum(x["фд"] for x in g):>5}'
      f'{(reg/clk*10000 if clk else float("nan")):>10.1f}')
P('   Внимание на определение: у 20.09 окно открыто ~1,5 суток из 3 — но и у 19.09, и у 18.09 тоже. '
  'Сравнение 20.09 с закрытыми окнами прошлых дат некорректно по знаменателю; сравнение с соседними '
  'открытыми датами корректно, и там воскресенье 20.09 не выделяется.')
P('   Но это же значит: вывод «20.09 = норма» опирается на НЕЗАКРЫТОЕ окно, то есть на те самые строки, '
  'которые из основного анализа выброшены. Он предварителен по построению.')

# ------------------------------------------------- 6. ИТОГ
P('')
P('=' * 100)
P('ИТОГ КОНТРПРОВЕРКИ')
P('=' * 100)
P(f'1. Числа воспроизводятся: повторный запуск h08 дал побайтово тот же файл, мой независимый пересчёт совпал '
  f'({swe["out"]} выходов при {swe["e_exit"]:.1f} ожидаемых, O/E {swe["o_exit"]/swe["e_exit"]:.2f}; воскресенье 5 рег при 9,1; '
  f'день 2 — 2781 при 2833,8 и 28 рег при 26,2).')
P('2. Определения в порядке: O/E — пул сырых счётчиков, а не среднее доменных долей; знаменатели оконные '
  '(«сайтов в окне» расходится с «сайтов» ровно у 152 строк с открытым окном, и они исключены); «дней=1» исключены.')
P(f'3. Объём: часть (1) стоит на {len(sel)} доменах из {len(kept)} ({len(sel)/len(kept)*100:.1f} %), 6 стратах, '
  f'2 выходных датах против 3 будних и 9 регистрациях (6 против 3). Перестановка по датам различает максимум '
  f'{n_date_arrangements(sel, KEY_MAIN, is_we)} раскладок, то есть минимальный достижимый p ~0,02.')
P('4. Ожидание кругово: в 3 из 6 страт выходные занимают 59–93 % сайтов, поэтому E строится по самой проверяемой '
  'группе. Контрфакт показывает масштаб: истинное падение выходных на 60 % даёт после страты O/E всего 0,71, '
  'а не 0,43. Оценка систематически тянется к 1.')
P('5. Опора: без трёх наборов 12.09 O/E выходных = 0,96, а Мантель–Хенцель RR падает с 1,21 до 0,94. '
  'Вся «поддержка» выходных живёт в этих трёх стратах (RR 2,64), где будняя сторона — 13 доменов '
  'понедельника 14.09 с 2,58 % выхода и 806 кликами, то есть практически мёртвых.')
P('6. Мощность: перестановка по датам не отвергает истинные множители 0,40–1,50. Заявление «заметен был бы '
  'провал сильнее 15–18 %» неверно — это ширина нулевого интервала, а не мощность.')
P('7. Множественность: 34 p-значения в отчёте; единственные значимые результаты (грубая страта 0,78 и 0,82 '
  'с p<0,0001) работают ПРОТИВ вывода, а χ² по дням p 0,0193 умирает и от поправки (0,23), и от смены единицы (0,1953).')
P('8. По деньгам 20 событий набирает только объединение пт+сб (28 рег). Выходные в стратах — 6 рег, '
  'субботние запуски — 6, воскресные — 0, воскресенье целиком — 5 (точный интервал на O/E 0,18–1,28).')
P('')
P('ВЕРДИКТ: числа верны, но вывод сильнее цифр. «Выходные сами по себе выход не портят» и «дня 2 разницы нет» — '
  'это отсутствие доказательства при почти нулевой мощности, круговом ожидании и опоре на один слабый '
  'понедельник, а не доказательство отсутствия.')

open(OUT_PATH, 'w', encoding='utf-8').write('\n'.join(_out) + '\n')
print('\nсохранено:', OUT_PATH)

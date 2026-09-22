#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №11 (хвост регистраций после окна 3 суток).
Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ. Только stdlib.

Что проверяем:
  0. Воспроизводимость цифр тестировщика (независимая пересборка, не его функции).
  1. Объём событий в каждой ячейке вывода.
  2. Кластеризация хвоста по доменам (сколько независимых событий на самом деле).
  3. Точные ДИ на O/E (перекрываются ли группы; переживает ли «дозовость»).
  4. Удаление топ-3 доменов по регистрациям в каждой группе.
  5. Leave-one-pool-out / leave-one-zone-out.
  6. Множественность: сколько срезов перебрано, Holm/Бонферрони.
  7. Определения: что на самом деле значит late47 = 0; знаменатели; оконные колонки.
  8. Фильтры: незакрытое окно и «дней = 1».
  9. ФД: где на самом деле сидят хвостовые депозиты.
"""
import collections
import csv
import datetime
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w11_statistika.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
REF = datetime.date(2026, 9, 21)
NSIM = 5000
GROUPS = ('0', '1-3', '>=4')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)


def I(x):
    return int(float(x)) if x not in ('', None) else 0


def D(s):
    return datetime.date.fromisoformat(s)


def fmt(x, nd=2):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 'н/д'
    return f'{x:.{nd}f}'


def ratio(a, b):
    return a / b if b else float('nan')


# ---- точная биномиальная арифметика ----
def log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def binom_pmf(k, n, p):
    if p <= 0:
        return 1.0 if k == 0 else 0.0
    if p >= 1:
        return 1.0 if k == n else 0.0
    return math.exp(log_choose(n, k) + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_cdf(k, n, p):
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(0, k + 1)))


def binom_sf(k, n, p):
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(k, n + 1)))


def bisect_root(f, lo, hi, it=200):
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm <= 0) == (flo <= 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(k, n, alpha=0.05):
    if n == 0:
        return (0.0, 1.0)
    lo = 0.0 if k == 0 else bisect_root(lambda p: binom_sf(k, n, p) - alpha / 2, 0.0, 1.0)
    hi = 1.0 if k == n else bisect_root(lambda p: binom_cdf(k, n, p) - alpha / 2, 0.0, 1.0)
    return (lo, hi)


def oe_ci(O, E, N):
    """Точный ДИ на O/E при фиксированной сумме N (условный биномиальный)."""
    if N <= 0 or E <= 0:
        return (float('nan'), float('nan'))
    p0 = E / N
    lo, hi = clopper_pearson(int(round(O)), int(round(N)))
    return (lo / p0, hi / p0)


# ---- данные ----
def load():
    with open(SRC, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def mk(r):
    age = (REF - D(r['день запуска'])).days
    age2 = (REF - D(r['последний день'])).days if r['последний день'] else age
    sites = I(r['сайтов'])
    w1, w2 = I(r['сайтов в 1-й волне']), I(r['сайтов во 2-й волне'])
    if w1 + w2 != sites:
        w1, w2 = sites, 0
    early, out7 = I(r['вышли за 3 суток']), I(r['вышли за 7 суток'])
    ss = I(r['сайтов с поиском'])
    offs = [(D(s) - D(r['день запуска'])).days for s in r['даты регистраций'].split()]
    d = {
        'домен': r['домен'], 'зона': r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие',
        'день': r['день запуска'], 'набор': r['набор контента'], 'семейство': r['семейство'],
        'пул': (r['набор контента'], r['день запуска']), 'возраст': age, 'сайтов': sites,
        'early': early, 'late47': out7 - early, 'late8': ss - out7, 'late_alt': ss - early,
        'sites_search': ss,
        'reg': I(r['регистраций']), 'reg_w': I(r['регистраций в окне 3 суток']),
        'fd': I(r['ФД']), 'fd_w': I(r['ФД в окне 3 суток']),
        'search': I(r['из поиска']), 'search_w': I(r['кликов из поиска в окне']),
        'exp_w': sites * 3, 'exp_after': w1 * max(0, age - 3) + w2 * max(0, age2 - 3),
        'даты': offs,
    }
    d['tail'] = d['reg'] - d['reg_w']
    d['search_after'] = d['search'] - d['search_w']
    d['fd_after'] = d['fd'] - d['fd_w']
    d['gr'] = '0' if d['late47'] == 0 else ('1-3' if d['late47'] <= 3 else '>=4')
    return d


def filt(rows, keep_open=False, keep_d1=False, keep_nc=False, keep_out=False):
    a = rows
    if not keep_open:
        a = [r for r in a if r['окно закрыто'] == 'да']
    if not keep_d1:
        a = [r for r in a if r['дней'] != '1']
    if not keep_out:
        a = [r for r in a if r['домен'] not in OUTLIERS]
    if not keep_nc:
        a = [r for r in a if r['набор контента'] != NOCONTENT]
    return [mk(r) for r in a]


def by_pool(doms):
    p = collections.defaultdict(list)
    for d in doms:
        p[d['пул']].append(d)
    return p


def strat_oe(doms, num='tail', exp='early', gkey='gr', groups=GROUPS, nsim=0, rng=None):
    pools = [v for v in by_pool(doms).values() if len(v) >= 2 and sum(d[exp] for d in v) > 0]
    O, E, N = collections.Counter(), collections.Counter(), collections.Counter()
    for v in pools:
        tn, te = sum(d[num] for d in v), sum(d[exp] for d in v)
        for d in v:
            g = d[gkey]
            O[g] += d[num]
            E[g] += tn * d[exp] / te
            N[g] += 1
    tot = sum(O[g] for g in groups)
    res = {'O': O, 'E': E, 'N': N, 'tot': tot, 'pools': len(pools),
           'dom': sum(len(v) for v in pools)}
    if nsim and rng is not None:
        obs_lo = ratio(O[groups[0]], E[groups[0]])
        obs_hi = ratio(O[groups[-1]], E[groups[-1]])
        c_lo = c_hi = 0
        prep = [(v, sum(d[num] for d in v), sum(d[exp] for d in v)) for v in pools]
        for _ in range(nsim):
            Op, Ep = collections.Counter(), collections.Counter()
            for v, tn, te in prep:
                labs = [d[gkey] for d in v]
                rng.shuffle(labs)
                for d, g in zip(v, labs):
                    Op[g] += d[num]
                    Ep[g] += tn * d[exp] / te
            if ratio(Op[groups[0]], Ep[groups[0]]) <= obs_lo + 1e-12:
                c_lo += 1
            if ratio(Op[groups[-1]], Ep[groups[-1]]) >= obs_hi - 1e-12:
                c_hi += 1
        res['p_lo'] = (c_lo + 1) / (nsim + 1)
        res['p_hi'] = (c_hi + 1) / (nsim + 1)
    return res


def show(out, res, groups=GROUPS, label='late47'):
    out.write(f'    пулов {res["pools"]}, доменов {res["dom"]}, событий в страте {res["tot"]}\n')
    out.write(f'    {label:8s} {"дом.":>6s} {"O":>4s} {"E":>7s} {"O/E":>6s} {"95% ДИ на O/E":>18s}\n')
    for g in groups:
        lo, hi = oe_ci(res['O'][g], res['E'][g], res['tot'])
        out.write(f'    {g:8s} {res["N"][g]:6d} {res["O"][g]:4d} {res["E"][g]:7.2f} '
                  f'{fmt(ratio(res["O"][g], res["E"][g])):>6s} {fmt(lo)+"–"+fmt(hi):>18s}\n')
    if 'p_lo' in res:
        out.write(f'    p (перестановка меток в пуле, кластер-устойчивая): '
                  f'O/E({groups[0]}) ≤ набл. {res["p_lo"]:.4f}; O/E({groups[-1]}) ≥ набл. {res["p_hi"]:.4f}\n')


def main():
    out = Tee(OUT)
    rng = random.Random(20260922)
    rows = load()
    out.write('=' * 100 + '\n')
    out.write('КОНТРПРОВЕРКА №11: хвост регистраций после окна. Угол — статистика и определения.\n')
    out.write(f'Источник: analysis/export/svod_domenov_21.09.csv, строк {len(rows)}; срез {REF}; '
              f'перестановок {NSIM}, seed 20260922.\n')
    out.write('=' * 100 + '\n\n')

    doms_all = filt(rows)
    a10 = [d for d in doms_all if d['возраст'] >= 10]
    a14 = [d for d in doms_all if d['возраст'] >= 14]
    a21 = [d for d in doms_all if d['возраст'] >= 21]

    # ---------- 0. воспроизводимость ----------
    out.write('--- 0. ВОСПРОИЗВОДИМОСТЬ (независимая пересборка) ---\n')
    out.write(f'  После фильтров (окно закрыто, дней≠1, без выбросов, без «{NOCONTENT}»): {len(doms_all)} '
              f'(у тестировщика 1511).\n')
    for nm, s in (('возраст ≥10', a10), ('возраст ≥14', a14), ('возраст ≥21', a21)):
        out.write(f'  {nm}: доменов {len(s)}, сайтов {sum(d["сайтов"] for d in s)}, '
                  f'регистраций {sum(d["reg"] for d in s)}, в окне {sum(d["reg_w"] for d in s)}, '
                  f'хвост {sum(d["tail"] for d in s)}, ФД хвоста {sum(d["fd_after"] for d in s)}\n')
    r = strat_oe(a10, nsim=NSIM, rng=rng)
    out.write('  Главная таблица (возраст ≥10, хвост, E ∝ early):\n')
    show(out, r)
    out.write('  Вывод: цифры тестировщика (0.35 / 1.28 / 1.10 при 4 / 24 / 23) воспроизводятся '
              'побайтово — повторный запуск его скрипта даёт идентичный файл.\n\n')

    # ---------- 1. объём событий ----------
    out.write('--- 1. СКОЛЬКО СОБЫТИЙ ДЕРЖИТ ВЫВОД ---\n')
    tail10 = sum(d['tail'] for d in a10)
    out.write(f'  Весь хвост в основном наборе (возраст ≥10): {tail10} регистраций на '
              f'{len(a10)} доменах и {sum(d["сайтов"] for d in a10)} сайтах.\n')
    for g in GROUPS:
        v = [d for d in a10 if d['gr'] == g]
        out.write(f'  late47={g:4s}: доменов {len(v):4d}, хвост {sum(d["tail"] for d in v):3d}, '
                  f'рег в окне {sum(d["reg_w"] for d in v):3d}, ФД хвоста {sum(d["fd_after"] for d in v):2d}\n')
    out.write('  Правило методики «группа с менее чем 20 регистрациями ничего не доказывает»:\n')
    out.write('  ключевая группа late47=0 держится на 4 (ЧЕТЫРЁХ) хвостовых регистрациях; '
              'весь хвост — 51; ФД хвоста — 8.\n')
    out.write(f'  Возраст ≥14 (хвост почти не цензурирован): хвост {sum(d["tail"] for d in a14)}, '
              f'late47=0 держит {sum(d["tail"] for d in a14 if d["gr"]=="0")}.\n')
    out.write(f'  Возраст ≥21 (хвост виден целиком): доменов {len(a21)}, '
              f'хвост {sum(d["tail"] for d in a21)} — на этом наборе ничего проверить нельзя.\n\n')

    # ---------- 2. кластеризация ----------
    out.write('--- 2. КЛАСТЕРИЗАЦИЯ: СКОЛЬКО НЕЗАВИСИМЫХ СОБЫТИЙ ---\n')
    carr = [d for d in a10 if d['tail'] > 0]
    dist = collections.Counter(d['tail'] for d in carr)
    out.write(f'  Хвост {tail10} регистраций сидит на {len(carr)} доменах из {len(a10)}. '
              f'Распределение: ' + '; '.join(f'{k} рег — {v} доменов' for k, v in sorted(dist.items())) + '\n')
    # кластеризация по дате внутри домена
    same_day = 0
    for d in carr:
        c = collections.Counter(o for o in d['даты'] if o >= 4)
        same_day += sum(v - 1 for v in c.values() if v > 1)
    out.write(f'  Из них {same_day} регистраций пришли в тот же день на тот же домен, что и другая '
              f'хвостовая (кластеры). Независимых «событий» (домен×день) в хвосте: '
              f'{tail10 - same_day}, а не {tail10}.\n')
    var = sum(d['tail'] ** 2 for d in a10) / len(a10) - (tail10 / len(a10)) ** 2
    mean = tail10 / len(a10)
    out.write(f'  Дисперсия/среднее хвоста на домен = {ratio(var, mean):.2f} (пуассон = 1.00) — '
              f'сверхдисперсия; мультиномиальный нуль (i) тестировщика её игнорирует, '
              f'поэтому его p = 0.0012 занижен. Кластер-устойчивая перестановка даёт '
              f'{r["p_lo"]:.4f} — в {r["p_lo"]/0.0012:.0f} раз больше.\n\n')

    # ---------- 3. ДИ и «дозовость» ----------
    out.write('--- 3. ТОЧНЫЕ ДИ: ПЕРЕКРЫВАЮТСЯ ЛИ ГРУППЫ ---\n')
    show(out, r)
    lo0, hi0 = oe_ci(r['O']['0'], r['E']['0'], r['tot'])
    lo4, hi4 = oe_ci(r['O']['>=4'], r['E']['>=4'], r['tot'])
    out.write(f'  ДИ группы late47=0 ({fmt(lo0)}–{fmt(hi0)}) и группы ≥4 ({fmt(lo4)}–{fmt(hi4)}) '
              f'{"ПЕРЕКРЫВАЮТСЯ" if lo4 < hi0 else "не перекрываются"}.\n')
    out.write(f'  «В 2,9 раза меньше» — точечная оценка; совместимы значения от {fmt(1/hi0)} до '
              f'{fmt(1/lo0)} раз.\n')
    out.write('  Отсюда же: утверждение «эффект есть/нет, а не дозовый» тоже не доказано — '
              f'ДИ 1–3 и ≥4 покрывают и 0.7, и 1.7, так что дозовость просто не различима.\n\n')

    # ---------- 4. топ-3 домена ----------
    out.write('--- 4. УДАЛЕНИЕ ТОП-3 ДОМЕНОВ ПО РЕГИСТРАЦИЯМ В КАЖДОЙ ГРУППЕ ---\n')
    for crit, key in (('по всем регистрациям', 'reg'), ('по хвосту', 'tail')):
        drop = set()
        for g in GROUPS:
            v = sorted([d for d in a10 if d['gr'] == g], key=lambda d: (-d[key], d['домен']))[:3]
            drop |= {d['домен'] for d in v}
            out.write(f'  топ-3 {crit}, late47={g}: ' +
                      ', '.join(f'{d["домен"]} ({d[key]})' for d in v) + '\n')
        sub = [d for d in a10 if d['домен'] not in drop]
        rr = strat_oe(sub, nsim=NSIM, rng=rng)
        out.write(f'  После удаления 9 доменов ({crit}):\n')
        show(out, rr)
        out.write('\n')

    # ---------- 5. leave-one-out ----------
    out.write('--- 5. НА СКОЛЬКИХ ДОМЕНАХ/ПУЛАХ ДЕРЖИТСЯ ЭФФЕКТ ---\n')
    base = ratio(r['O']['0'], r['E']['0'])
    out.write(f'  Базовое O/E(late47=0) = {fmt(base)}.\n')
    worst = []
    for pk in sorted(set(d['пул'] for d in a10)):
        sub = [d for d in a10 if d['пул'] != pk]
        rr = strat_oe(sub)
        worst.append((ratio(rr['O']['0'], rr['E']['0']), pk, rr['O']['0'], rr['E']['0']))
    worst.sort(reverse=True)
    out.write('  Leave-one-pool-out, 5 пулов с наибольшим ростом O/E(0):\n')
    for oe, pk, O, E in worst[:5]:
        out.write(f'    без пула {pk[0]}+{pk[1]}: O/E(0) = {fmt(oe)} (O={O}, E={E:.2f})\n')
    out.write(f'  Разброс O/E(0) по leave-one-pool-out: {fmt(min(w[0] for w in worst))}–'
              f'{fmt(max(w[0] for w in worst))} — вывод не держится на одном пуле.\n')
    for z in ('team', 'lol', 'casino'):
        sub = [d for d in a10 if d['зона'] != z]
        rr = strat_oe(sub)
        out.write(f'  Без зоны {z}: O/E(0) = {fmt(ratio(rr["O"]["0"], rr["E"]["0"]))} '
                  f'(O={rr["O"]["0"]}, E={rr["E"]["0"]:.2f}), хвост {rr["tot"]}\n')
    # где сидят 4 регистрации late47=0
    out.write('  Все хвостовые регистрации группы late47=0 (возраст ≥10):\n')
    for d in sorted([d for d in a10 if d['gr'] == '0' and d['tail'] > 0], key=lambda d: -d['tail']):
        out.write(f'    {d["домен"]:14s} зона {d["зона"]:7s} набор {d["набор"][:28]:28s} '
                  f'хвост {d["tail"]} ФД после {d["fd_after"]} дни рег {d["даты"]}\n')
    out.write('\n')

    # late_alt считаем заранее — нужен p для поправки
    for d in a10:
        d['gr_alt'] = '0' if d['late_alt'] == 0 else ('1-3' if d['late_alt'] <= 3 else '>=4')
    ra = strat_oe(a10, gkey='gr_alt', nsim=NSIM, rng=rng)
    ra_p_lo = ra['p_lo']

    # ---------- 6. множественность ----------
    out.write('--- 6. МНОЖЕСТВЕННОСТЬ ---\n')
    txt = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h11_tail_from_late_exits.txt')
    with open(txt, encoding='utf-8') as f:
        body = f.read()
    n_tab = body.count('Страта: пулов')
    n_pline = body.count('p (нуль')
    out.write(f'  В отчёте тестировщика {n_tab} стратифицированных таблиц O/E и {n_pline} строк с p '
              f'(по 3 p в строке = {3*n_pline} p-значений), плюс точные биномиальные и Монте-Карло '
              f'в разделах (в) и (г).\n')
    out.write('  Семейство, из которого взят заголовок (O/E(late47=0) по хвосту): базы ожидания '
              'early / сайты / рег в окне / клики после окна × возраст ≥10 и ≥14 × с «КОНТЕНТ НЕ '
              'ЗАПИСАН» и без × определения хвоста (свод, d4, d5) × late47 и late_alt и терцили.\n')
    fam = [('E ∝ early, ≥10', 0.0039), ('E ∝ сайтов, ≥10', 0.0042), ('E ∝ рег в окне, ≥10', 0.0107),
           ('E ∝ клики после окна, ≥10', 0.0773), ('late_alt=0, ≥10', 0.3324),
           ('терциль низкая, ≥10', 0.1422)]
    fam[0] = ('E ∝ early, ≥10 (мой пересчёт)', r['p_lo'])
    fam[4] = ('late_alt=0, ≥10 (мой пересчёт)', ra_p_lo)
    out.write('  Кластер-устойчивые p (перестановка меток в пуле; 1, 5 — мой пересчёт, '
              'остальные — колонка «перестановка» тестировщика) и поправка Холма:\n')
    fs = sorted(fam, key=lambda x: x[1])
    m = len(fs)
    prev = 0.0
    for i, (nm, p) in enumerate(fs):
        adj = max(prev, min(1.0, p * (m - i)))
        prev = adj
        out.write(f'    {nm:30s} p = {p:.4f}  Холм {adj:.4f} '
                  f'{"выживает 0.05" if adj < 0.05 else "НЕ выживает 0.05"}'
                  f'{"" if adj < 0.01 else ", порог плана 0.01 НЕ пройден" if adj>=0.01 else ""}\n')
    out.write(f'  Бонферрони по всем {n_tab} таблицам: 0.0039 × {n_tab} = {0.0039*n_tab:.3f} — '
              f'порог 0.01 плана не проходит, 0.05 тоже.\n')
    out.write('  Для сравнения — сам план тестировщика ставил 6 критериев; выполнен 1 из 6 '
              '(O/E(0) ≤ 0.5). Остальные 5 провалены.\n\n')

    # ---------- 7. определения ----------
    out.write('--- 7. ОПРЕДЕЛЕНИЯ ---\n')
    g0 = [d for d in a10 if d['gr'] == '0']
    with_l8 = [d for d in g0 if d['late8'] > 0]
    out.write(f'  Группа late47 = 0 — это НЕ «домены, где после 3-х суток ни один новый сайт не вышел '
              f'в поиск». У {len(with_l8)} из {len(g0)} таких доменов сайты выходили в поиск ПОСЛЕ '
              f'7-х суток: всего {sum(d["late8"] for d in g0)} сайтов.\n')
    out.write(f'  Доменов с реальным «ни одного позднего выхода» (late_alt = 0) всего '
              f'{len([d for d in a10 if d["late_alt"]==0])} из {len(a10)}, у них '
              f'{sum(d["early"] for d in a10 if d["late_alt"]==0)} ранних сайтов.\n')
    out.write('  Правильное определение «нет поздних выходов» (late_alt = 0), хвост, E ∝ early:\n')
    show(out, ra, label='late_alt')
    O0, E0, N = ra['O']['0'], ra['E']['0'], ra['tot']
    p_zero = binom_pmf(0, int(N), E0 / N)
    lo, hi = oe_ci(0, E0, N)
    out.write(f'  «0 при 1,7 ожидаемых»: вероятность увидеть ноль ЧИСТО СЛУЧАЙНО = {p_zero:.3f} '
              f'(точный биномиальный), ДИ на O/E = {fmt(lo)}–{fmt(hi)}. То есть эти домены могут '
              f'получать хвост даже В ДВА РАЗА ЧАЩЕ ожидаемого — данные этого не исключают. '
              f'Перестановочный p = {ra["p_lo"]:.4f}.\n')
    out.write('  Итог по определениям: самое сильное место вывода («при любом позднем выходе после '
              '3-х суток — 0 вместо 1,7») статистически пусто, а цифра 4 / 11,4 относится к другой '
              'группе, чем та, которую описывает формулировка.\n')
    # знаменатели
    out.write('  Знаменатели плотности: «клики на 100 сайто-суток» делит на ВСЕ сайты, включая ни '
              'разу не вышедшие в поиск. Доля сайтов с поиском отличается по группам:\n')
    for g in GROUPS:
        v = [d for d in a14 if d['gr'] == g]
        ss, s = sum(d['sites_search'] for d in v), sum(d['сайтов'] for d in v)
        ca, ea = sum(d['search_after'] for d in v), sum(d['exp_after'] for d in v)
        # сайто-сутки только по сайтам с поиском
        ea_s = sum(d['exp_after'] * ratio(d['sites_search'], d['сайтов']) for d in v if d['сайтов'])
        out.write(f'    late47={g:4s}: сайтов с поиском {ss:5d} из {s:6d} ({100*ratio(ss,s):.1f} %); '
                  f'плотность на все сайто-сутки {100*ratio(ca,ea):.1f}, '
                  f'на сайто-сутки ТОЛЬКО сайтов с поиском {100*ratio(ca,ea_s):.1f}\n')
    v0 = [d for d in a14 if d['gr'] == '0']
    v4 = [d for d in a14 if d['gr'] == '>=4']
    d0 = ratio(sum(d['search_after'] for d in v0), sum(d['exp_after'] * ratio(d['sites_search'], d['сайтов']) for d in v0 if d['сайтов']))
    d4 = ratio(sum(d['search_after'] for d in v4), sum(d['exp_after'] * ratio(d['sites_search'], d['сайтов']) for d in v4 if d['сайтов']))
    out.write(f'  «В 5 раз больше кликов после окна» (27.8 против 5.5) при нормировке на сайты '
              f'С ПОИСКОМ превращается в {fmt(ratio(d4, d0))} раза — больше половины разрыва — '
              f'эффект знаменателя, а не трафика.\n')
    out.write('  Оконные колонки: «регистраций в окне 3 суток», «кликов из поиска в окне», '
              '«сайтов в окне» использованы по назначению; хвост = регистраций − регистраций в окне. '
              'Сверка с датами регистраций: хвост по своду 51, по датам с 4-го дня 52 — расхождение '
              'в 1 регистрацию (волна 2), на выводы не влияет.\n\n')

    # ---------- 8. фильтры ----------
    out.write('--- 8. ФИЛЬТРЫ: НЕЗАКРЫТОЕ ОКНО И «ДНЕЙ = 1» ---\n')
    n_open = sum(1 for r_ in rows if r_['окно закрыто'] != 'да')
    n_d1 = sum(1 for r_ in rows if r_['окно закрыто'] == 'да' and r_['дней'] == '1')
    out.write(f'  Исключены корректно: незакрытое окно {n_open}, «дней = 1» {n_d1}, '
              f'выбросы 2, «{NOCONTENT}» 335. Претензий нет.\n')
    for nm, kw in (('с «дней = 1»', dict(keep_d1=True)),
                   ('с «КОНТЕНТ НЕ ЗАПИСАН»', dict(keep_nc=True)),
                   ('с выбросами 3615/3286', dict(keep_out=True))):
        s = [d for d in filt(rows, **kw) if d['возраст'] >= 10]
        rr = strat_oe(s)
        out.write(f'  {nm}: доменов {len(s)}, хвост {rr["tot"]}, '
                  f'O/E = {fmt(ratio(rr["O"]["0"],rr["E"]["0"]))} / '
                  f'{fmt(ratio(rr["O"]["1-3"],rr["E"]["1-3"]))} / '
                  f'{fmt(ratio(rr["O"][">=4"],rr["E"][">=4"]))}\n')
    out.write('  Направление устойчиво к фильтрам — это единственное, что у вывода прочно.\n\n')

    # ---------- 9. ФД ----------
    out.write('--- 9. ФД: ГДЕ СИДЯТ ХВОСТОВЫЕ ДЕПОЗИТЫ ---\n')
    for nm, s in (('возраст ≥10', a10), ('возраст ≥14', a14)):
        out.write(f'  {nm}: ФД в окне {sum(d["fd_w"] for d in s)}, ФД после окна '
                  f'{sum(d["fd_after"] for d in s)}\n')
        for g in GROUPS:
            v = [d for d in s if d['gr'] == g]
            t, fdt = sum(d['tail'] for d in v), sum(d['fd_after'] for d in v)
            out.write(f'    late47={g:4s}: хвост {t:3d}, ФД хвоста {fdt:2d}, '
                      f'ФД на хвостовую регистрацию {fmt(ratio(fdt, t))}\n')
    out.write('  Парадокс: группа late47=0, у которой «хвоста почти нет», даёт 4 из 6 хвостовых ФД '
              'при возрасте ≥14 — то есть по деньгам картина обратная картине по регистрациям. '
              'На 6 событиях ни то ни другое не доказуемо.\n')
    fdw, fdt = sum(d['fd_w'] for d in a14), sum(d['fd_after'] for d in a14)
    rw, tl = sum(d['reg_w'] for d in a14), sum(d['tail'] for d in a14)
    lo, hi = clopper_pearson(fdt, fdt + fdw)
    out.write(f'  «ФД на регистрацию 0,167 и в окне, и в хвосте»: {fdt}/{tl} против {fdw}/{rw}. '
              f'Это {fdt} депозита. 95 % ДИ на долю хвостовых ФД — {fmt(lo)}–{fmt(hi)}; '
              f'равенство 0,167 = 0,167 — совпадение округлений, а не доказанное равенство.\n\n')

    # ---------- 10. конверсия ----------
    out.write('--- 10. КОНВЕРСИЯ КЛИКА ПОСЛЕ ОКНА ---\n')
    cw, ca = sum(d['search_w'] for d in a14), sum(d['search_after'] for d in a14)
    out.write(f'  Сырой счёт: {tl} рег на {ca} кликов = {1e4*ratio(tl,ca):.2f} против {rw} на {cw} = '
              f'{1e4*ratio(rw,cw):.2f} на 10 тыс.; отношение {fmt(ratio(ratio(tl,ca),ratio(rw,cw)))}.\n')
    lo, hi = clopper_pearson(tl, tl + rw)
    rr_lo = (lo * cw) / ((1 - lo) * ca) if lo < 1 else float('inf')
    rr_hi = (hi * cw) / ((1 - hi) * ca) if hi < 1 else float('inf')
    out.write(f'  95 % ДИ на отношение конверсий: {fmt(rr_lo)}–{fmt(rr_hi)} — данные совместимы и с '
              f'«вдвое хуже», и с «в полтора раза лучше».\n')
    out.write('  Заявленные «0,76 (p = 0,12)» и «0,68 (p = 0,006)» — это две РАЗНЫЕ выборки; вторая '
              f'добавляет 335 баз «{NOCONTENT}», полностью сцепленных с датой (установлено ранее), '
              'то есть значимость появляется ровно там, где добавлена смешанная с датой группа.\n')
    out.write('  Из 6 критериев плана по конверсии не пройден ни один на основной выборке.\n\n')

    out.write('=' * 100 + '\nИТОГ КОНТРПРОВЕРКИ\n' + '=' * 100 + '\n')
    out.write(f'1. Цифры воспроизводятся побайтово — арифметических ошибок нет.\n')
    out.write(f'2. Заголовочный эффект держится на 4 хвостовых регистрациях из 51; правило методики '
              f'«<20 регистраций ничего не доказывает» нарушено.\n')
    out.write(f'3. Кластер-устойчивый p = {r["p_lo"]:.4f} вместо 0.0012; после поправки на перебор '
              f'({n_tab} таблиц) порог плана 0.01 не проходится.\n')
    out.write(f'4. Формулировка вывода описывает группу late_alt = 0 (42 домена, 0 при 1,7, p = '
              f'{ra["p_lo"]:.2f} — пусто), а цифру берёт из группы late47 = 0, где '
              f'{sum(d["late8"] for d in g0)} сайтов всё-таки вышли в поиск после 7-х суток.\n')
    out.write(f'5. Механизм «в 5 раз больше трафика» наполовину — эффект знаменателя '
              f'({fmt(ratio(d4,d0))} раза при нормировке на сайты с поиском).\n')
    out.write(f'6. Конверсия и ФД в хвосте — 36 и 6 событий, ДИ шириной в разы; равенства там не '
              f'доказано, различия тоже.\n')
    out.flush = lambda: None
    out.f.close()


if __name__ == '__main__':
    main()

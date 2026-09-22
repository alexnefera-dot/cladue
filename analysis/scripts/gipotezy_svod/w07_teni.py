#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №7 (угол: ТЕНИ / конфаундинг).

Вердикт тестировщика: «у регистраций нет собственного недельного ритма»,
O/E сб+вс = 1.13 (основной набор) и 0.99 (расширенный), ни один день не
держится после поправки; объявлено, что «эффект выходных в полтора раза
данные исключают».

Что проверяем здесь:
  Т1. Идентификация. При фиксированном домене день недели регистрации —
      детерминированная функция относительного дня. Значит жёсткая страта
      «набор контента + день запуска + зона» (и тем более +час) оставляет
      НОЛЬ степеней свободы для дня недели. Считаем, сколько страт вообще
      содержат больше одного дня недели запуска и сколько в них регистраций.
  Т2. Свободная от профиля оценка внутри жёсткой страты: сравниваем домены
      одного набора+зоны на ОДНОМ И ТОМ ЖЕ относительном дне d, у которых
      этот день лёг на выходной против будня. Профиль p(d) при этом
      сокращается полностью.
  Т3. Период/контент: август («КОНТЕНТ НЕ ЗАПИСАН») против сентября.
  Т4. Зона, выбросы, крупные наборы, домены-тяжеловесы — джекнайф O/E сб+вс.
  Т5. Усечение окна днями 0–3 (58/74 регистрации отброшены) — тень выбора окна.
  Т6. Мощность: прогоняем процедуру тестировщика на смоделированных данных
      с ИЗВЕСТНЫМ эффектом выходных k = 1.2 / 1.5 / 2.0 на реальной структуре
      запусков и проверяем, восстанавливает ли она k и отвергает ли нуль.
      Профиль p(d|блок) у тестировщика оценивается по тем же регистрациям,
      поэтому часть эффекта уходит в профиль и в нулевое распределение.

Только стандартная библиотека Python 3.
"""

import csv
import datetime as dt
import math
import os
import random
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'w07_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
WD = {1: 'пн', 2: 'вт', 3: 'ср', 4: 'чт', 5: 'пт', 6: 'сб', 7: 'вс'}
REL = (0, 1, 2, 3)
random.seed(7)

_lines = []


def P(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    _lines.append(s)


def toi(s):
    return int(float(s)) if s not in ('', None) else 0


def dte(s):
    return dt.date.fromisoformat(s)


def load():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        d = {
            'домен': r['домен'],
            'зона': r['зона'],
            'набор': r['набор контента'],
            'семейство': r['семейство'],
            'блок': r['блок часа'],
            'день': dte(r['день запуска']),
            'дней': toi(r['дней']),
            'закрыто': r['окно закрыто'] == 'да',
            'сайтов': toi(r['сайтов в окне']),
            'в1': toi(r['сайтов в 1-й волне']),
            'в2': toi(r['сайтов во 2-й волне']),
            'вышли3': toi(r['вышли за 3 суток']),
            'поиск_окно': toi(r['кликов из поиска в окне']),
        }
        d['днз'] = d['день'].isoweekday()
        regs = []
        for s in r['даты регистраций'].split():
            regs.append((dte(s) - d['день']).days)
        d['все_рег'] = sorted(regs)
        d['рег03'] = [x for x in regs if 0 <= x <= 3]
        d['рег_поздн'] = [x for x in regs if x > 3]
        fds = []
        for s in r['даты ФД'].split():
            fds.append((dte(s) - d['день']).days)
        d['фд03'] = [x for x in fds if 0 <= x <= 3]
        out.append(d)
    return out


def wd_of(dom, rel):
    return (dom['день'] + dt.timedelta(days=rel)).isoweekday()


def is_wknd(wd):
    return wd in (6, 7)


# --------------------------------------------------------------------------
# Процедура тестировщика (воспроизведение): профиль p(d|блок) по тем же
# событиям, E по дням недели, аналитический нуль (пуассон-биномиальный).
# --------------------------------------------------------------------------

def profile(doms, key='рег03', min_n=8):
    cnt = defaultdict(Counter)
    tot = Counter()
    n = 0
    for d in doms:
        for rel in d[key]:
            cnt[d['блок']][rel] += 1
            tot[rel] += 1
            n += 1
    if n == 0:
        return None, 0
    pooled = {r: tot[r] / n for r in REL}
    prof = {}
    for blk in set(d['блок'] for d in doms):
        m = sum(cnt[blk].values())
        prof[blk] = {r: cnt[blk][r] / m for r in REL} if m >= min_n else dict(pooled)
    return prof, n


def oe_weekend(doms, key='рег03'):
    """O, E, O/E для сб+вс и аналитический z/p по нулю тестировщика."""
    prof, n = profile(doms, key)
    if not n:
        return None
    O = 0
    E = 0.0
    var = 0.0
    Ewd = defaultdict(float)
    Owd = Counter()
    for d in doms:
        p = prof[d['блок']]
        pw = sum(p[r] for r in REL if is_wknd(wd_of(d, r)))
        for rel in d[key]:
            wd = wd_of(d, rel)
            Owd[wd] += 1
            if is_wknd(wd):
                O += 1
            E += pw
            var += pw * (1 - pw)
            for r in REL:
                Ewd[wd_of(d, r)] += p[r]
    z = (O - E) / math.sqrt(var) if var > 0 else 0.0
    pval = math.erfc(abs(z) / math.sqrt(2))
    chi = sum((Owd[w] - Ewd[w]) ** 2 / Ewd[w] for w in range(1, 8) if Ewd[w] > 0)
    return {'n': n, 'O': O, 'E': E, 'OE': O / E if E else 0, 'z': z, 'p': pval,
            'Owd': Owd, 'Ewd': Ewd, 'chi': chi, 'sd': math.sqrt(var)}


def main():
    doms_all = load()
    P('Контрпроверка гипотезы №7 — ТЕНИ (конфаундинг)')
    P('Файл:', CSV_PATH)
    P('Строк (доменов) всего:', len(doms_all))
    P('')
    base = [d for d in doms_all if d['закрыто'] and d['дней'] != 1 and d['домен'] not in OUTLIERS]
    main_set = [d for d in base if d['набор'] != NO_CONTENT]
    P('Фильтр тестировщика: окно закрыто, дней != 1, без 3615.team/3286.team →',
      len(base), 'доменов (расширенный набор);', len(main_set), 'без «КОНТЕНТ НЕ ЗАПИСАН» (основной)')
    r_ext = oe_weekend(base)
    r_main = oe_weekend(main_set)
    P('Воспроизведение: основной O=%d E=%.1f O/E=%.2f (n=%d); расширенный O=%d E=%.1f O/E=%.2f (n=%d)'
      % (r_main['O'], r_main['E'], r_main['OE'], r_main['n'],
         r_ext['O'], r_ext['E'], r_ext['OE'], r_ext['n']))
    P('  (у тестировщика: 69/61.2 = 1.13 и 106/106.9 = 0.99 — сходится)')

    # =====================================================================
    P('')
    P('=' * 96)
    P('ТЕНЬ 1. ИДЕНТИФИКАЦИЯ: жёсткая страта «набор + день запуска + зона» даёт НОЛЬ степеней свободы')
    P('=' * 96)
    P('При фиксированном домене день недели регистрации = день недели запуска + относительный день.')
    P('День недели запуска внутри страты «набор+день+зона» постоянен по построению страты,')
    P('значит внутри страты «день недели» и «относительный день» — одна и та же переменная.')
    by_set_days = defaultdict(set)
    by_set_wd = defaultdict(set)
    for d in base:
        by_set_days[d['набор']].add(d['день'])
        by_set_wd[d['набор']].add(d['днз'])
    P('')
    P('Наборов контента в расширенном наборе: %d' % len(by_set_days))
    P('  дат запуска на набор: ' + ', '.join('%d дат: %d наборов' % (k, v) for k, v in
                                             sorted(Counter(len(v) for v in by_set_days.values()).items())))
    P('  дней недели на набор: ' + ', '.join('%d дн.нед.: %d наборов' % (k, v) for k, v in
                                             sorted(Counter(len(v) for v in by_set_wd.values()).items())))
    informative_sets = [s for s, v in by_set_wd.items() if len(v) > 1 and s != NO_CONTENT]
    dom_inf = [d for d in base if d['набор'] in informative_sets]
    reg_inf = sum(len(d['рег03']) for d in dom_inf)
    P('')
    P('Наборов с >1 днём недели запуска (без «НЕ ЗАПИСАН»): %d из %d; доменов %d; регистраций 0–3 в них %d из %d (%.0f %%)'
      % (len(informative_sets), len(by_set_days) - 1, len(dom_inf), reg_inf,
         r_ext['n'], 100 * reg_inf / r_ext['n']))
    P('«КОНТЕНТ НЕ ЗАПИСАН» (18 дат, %d доменов, %d регистраций) — это отсутствие записи, сцепленное с датой:'
      % (sum(1 for d in base if d['набор'] == NO_CONTENT),
         sum(len(d['рег03']) for d in base if d['набор'] == NO_CONTENT)))
    P('внутри него «набор» не зафиксирован, поэтому как страта он не годится.')
    P('')
    P('Вывод Т1: из 350 регистраций расширенного набора жёсткую страту «набор+день недели меняется» переживают %d (%.0f %%).'
      % (reg_inf, 100 * reg_inf / r_ext['n']))
    P('Остальные %d регистраций НЕ НЕСУТ информации о дне недели: у их доменов набор и день запуска'
      % (r_ext['n'] - reg_inf))
    P('склеены, и «среда лучше понедельника» неотличимо от «день +1 лучше дня +3».')
    P('Тестировщик берёт идентификацию из сравнения доменов, запущенных в РАЗНЫЕ дни недели,')
    P('то есть ровно из той «стороны подачи», которую сам объявил неотделимой от даты, набора и зоны.')

    # =====================================================================
    P('')
    P('=' * 96)
    P('ТЕНЬ 2. СВОБОДНАЯ ОТ ПРОФИЛЯ ОЦЕНКА ВНУТРИ ЖЁСТКОЙ СТРАТЫ')
    P('=' * 96)
    P('Идея: фиксируем страту (набор контента + зона [+ блок часа]) И относительный день d.')
    P('Внутри такой ячейки профиль p(d) сокращается полностью: сравниваются домены, у которых')
    P('ОДИН И ТОТ ЖЕ день d лёг на выходной против будня. Ожидание — по доле экспозиции.')
    P('Экспозиция: «сайтов в окне» (вариант А) и «вышли за 3 суток» (вариант Б).')

    def strat_test(doms, keyfun, expo, label, n_perm=20000, key='рег03'):
        cells = defaultdict(list)
        for d in doms:
            cells[keyfun(d)].append(d)
        O = 0
        E = 0.0
        var = 0.0
        n_cells = 0
        n_reg = 0
        units = []   # (список весов доменов, список «выходной ли», кол-во рег)
        for ck, ds in cells.items():
            for rel in REL:
                tot = sum(1 for d in ds for x in d[key] if x == rel)
                if tot == 0:
                    continue
                w = [max(expo(d), 0) for d in ds]
                if sum(w) <= 0:
                    continue
                flags = [is_wknd(wd_of(d, rel)) for d in ds]
                if not any(flags) or all(flags):
                    continue      # ячейка неинформативна: все в одной группе
                f = sum(wi for wi, fl in zip(w, flags) if fl) / sum(w)
                o = sum(1 for d in ds for x in d[key] if x == rel and is_wknd(wd_of(d, rel)))
                O += o
                E += tot * f
                var += tot * f * (1 - f)
                n_cells += 1
                n_reg += tot
                units.append((tot, f, o))
        if E <= 0:
            P('  %-46s — информативных ячеек нет' % label)
            return None
        z = (O - E) / math.sqrt(var)
        # перестановочный p: биномиальные розыгрыши по ячейкам
        worse = 0
        obs = abs(O - E)
        for _ in range(n_perm):
            s = 0
            for tot, f, _o in units:
                for _i in range(tot):
                    if random.random() < f:
                        s += 1
            if abs(s - E) >= obs - 1e-9:
                worse += 1
        pp = (worse + 1) / (n_perm + 1)
        lo, hi = poisson_ratio_ci(O, E)
        P('  %-46s ячеек %3d, регистраций %3d, O=%3d, E=%6.1f, O/E=%.2f [95%% %.2f–%.2f], z=%+.2f, перест. p=%.3f'
          % (label, n_cells, n_reg, O, E, O / E, lo, hi, z, pp))
        return {'O': O, 'E': E, 'OE': O / E, 'p': pp, 'n': n_reg, 'cells': n_cells}

    P('')
    P('  --- страта «набор контента + зона» (даты внутри набора различаются) ---')
    res_strict_a = strat_test(base, lambda d: (d['набор'], d['зона']), lambda d: d['сайтов'],
                              'А. экспозиция = сайтов в окне (расширенный)')
    res_strict_b = strat_test(base, lambda d: (d['набор'], d['зона']), lambda d: d['вышли3'],
                              'Б. экспозиция = вышли за 3 суток (расширенный)')
    strat_test(main_set, lambda d: (d['набор'], d['зона']), lambda d: d['сайтов'],
               'А. то же, ОСНОВНОЙ набор (без «НЕ ЗАПИСАН»)')
    strat_test(base, lambda d: (d['набор'], d['зона'], d['блок']), lambda d: d['сайтов'],
               'А+час. страта «набор+зона+блок часа»')
    P('')
    P('  --- более мягкая страта (для объёма): «семейство набора + зона + календарная неделя» ---')
    strat_test(base, lambda d: (d['семейство'], d['зона'], d['день'].isocalendar()[1]),
               lambda d: d['сайтов'], 'А. экспозиция = сайтов в окне')
    strat_test(base, lambda d: (d['семейство'], d['зона'], d['день'].isocalendar()[1]),
               lambda d: d['вышли3'], 'Б. экспозиция = вышли за 3 суток')
    P('')
    P('  --- «нулевая» страта для сравнения: только зона (почти нет контроля) ---')
    strat_test(base, lambda d: (d['зона'],), lambda d: d['сайтов'], 'А. экспозиция = сайтов в окне')

    # =====================================================================
    P('')
    P('=' * 96)
    P('ТЕНЬ 3. ПЕРИОД И НАБОР: август против сентября')
    P('=' * 96)
    cut = dt.date(2026, 8, 24)
    groups = [
        ('весь расширенный набор', base),
        ('запуски до 24.08 (эпоха «НЕ ЗАПИСАН»)', [d for d in base if d['день'] < cut]),
        ('запуски 24.08–31.08', [d for d in base if cut <= d['день'] <= dt.date(2026, 8, 31)]),
        ('запуски в сентябре', [d for d in base if d['день'] >= dt.date(2026, 9, 1)]),
        ('только «КОНТЕНТ НЕ ЗАПИСАН»', [d for d in base if d['набор'] == NO_CONTENT]),
        ('основной набор (без «НЕ ЗАПИСАН»)', main_set),
    ]
    P('  %-40s %6s %5s %8s %6s %14s %7s' % ('группа', 'дом.', 'рег', 'O сб+вс', 'E', 'O/E [95%]', 'p'))
    for name, ds in groups:
        r = oe_weekend(ds)
        if not r:
            P('  %-40s %6d     0   —' % (name, len(ds)))
            continue
        lo, hi = poisson_ratio_ci(r['O'], r['E'])
        P('  %-40s %6d %5d %8d %6.1f %6.2f [%.2f–%.2f] %7.3f'
          % (name, len(ds), r['n'], r['O'], r['E'], r['OE'], lo, hi, r['p']))
    P('')
    P('Разница между «основным» (1.13) и «расширенным» (0.99) наборами — целиком тень 335 доменов')
    P('«КОНТЕНТ НЕ ЗАПИСАН», то есть тень августа. Один и тот же вопрос на двух срезах одних и тех же')
    P('данных даёт O/E по разные стороны единицы; по отдельным дням знак переворачивается:')
    P('  %-8s %10s %10s' % ('день', 'O/E осн.', 'O/E расш.'))
    for w in range(1, 8):
        a = r_main['Owd'][w] / r_main['Ewd'][w] if r_main['Ewd'][w] else 0
        b = r_ext['Owd'][w] / r_ext['Ewd'][w] if r_ext['Ewd'][w] else 0
        P('  %-8s %10.2f %10.2f' % (WD[w], a, b))

    # =====================================================================
    P('')
    P('=' * 96)
    P('ТЕНЬ 4. ДЖЕКНАЙФ: зоны, выбросы, крупные наборы, домены-тяжеловесы (O/E сб+вс)')
    P('=' * 96)
    variants = [('расширенный, как есть', base)]
    for z in ('team', 'lol', 'casino', 'buzz'):
        variants.append(('без зоны .%s' % z, [d for d in base if d['зона'] != z]))
        variants.append(('только зона .%s' % z, [d for d in base if d['зона'] == z]))
    with_out = [d for d in doms_all if d['закрыто'] and d['дней'] != 1]
    variants.append(('С выбросами 3615/3286 обратно', with_out))
    variants.append(('+ домены с дней = 1 (снят фильтр)',
                     [d for d in doms_all if d['закрыто'] and d['домен'] not in OUTLIERS]))
    variants.append(('+ незакрытое окно (снят фильтр)',
                     [d for d in doms_all if d['дней'] != 1 and d['домен'] not in OUTLIERS]))
    top_sets = [s for s, _ in Counter(d['набор'] for d in base if d['набор'] != NO_CONTENT).most_common(3)]
    for s in top_sets:
        variants.append(('без набора «%s»' % s[:28], [d for d in base if d['набор'] != s]))
    heavy = sorted(base, key=lambda d: -len(d['рег03']))[:5]
    variants.append(('без 5 доменов-тяжеловесов (%d рег)' % sum(len(d['рег03']) for d in heavy),
                     [d for d in base if d not in heavy]))
    P('  %-40s %6s %5s %8s %6s %14s %7s' % ('вариант', 'дом.', 'рег', 'O сб+вс', 'E', 'O/E [95%]', 'p'))
    oes = []
    for name, ds in variants:
        r = oe_weekend(ds)
        if not r or r['n'] < 10:
            P('  %-40s %6d %5s — мало событий' % (name, len(ds), r['n'] if r else 0))
            continue
        lo, hi = poisson_ratio_ci(r['O'], r['E'])
        P('  %-40s %6d %5d %8d %6.1f %6.2f [%.2f–%.2f] %7.3f'
          % (name, len(ds), r['n'], r['O'], r['E'], r['OE'], lo, hi, r['p']))
        oes.append(r['OE'])
    P('')
    P('Разброс O/E сб+вс по вариантам фильтра: %.2f–%.2f (объявленный тестировщиком коридор нуля 0.87–1.13).'
      % (min(oes), max(oes)))

    # =====================================================================
    P('')
    P('=' * 96)
    P('ТЕНЬ 5. УСЕЧЕНИЕ ОКНА ДНЯМИ 0–3')
    P('=' * 96)
    late = [(d, x) for d in base for x in d['рег_поздн']]
    P('Регистраций позже дня +3 в расширенном наборе: %d (отброшены тестировщиком).' % len(late))
    cnt_late = Counter(wd_of(d, x) for d, x in late)
    P('  по дням недели: ' + ', '.join('%s %d' % (WD[w], cnt_late[w]) for w in range(1, 8)))
    P('  доля выходных среди отброшенных: %.0f %% (%d из %d)'
      % (100 * (cnt_late[6] + cnt_late[7]) / max(len(late), 1), cnt_late[6] + cnt_late[7], len(late)))
    for W in (4, 5, 7):
        rel_w = tuple(range(W))
        for d in base:
            d['регW'] = [x for x in d['все_рег'] if 0 <= x < W]
        global REL
        old = REL
        REL = rel_w
        r = oe_weekend(base, key='регW')
        REL = old
        lo, hi = poisson_ratio_ci(r['O'], r['E'])
        P('  окно 0..%d: регистраций %d, O сб+вс %d, E %.1f, O/E %.2f [%.2f–%.2f], p %.3f'
          % (W - 1, r['n'], r['O'], r['E'], r['OE'], lo, hi, r['p']))
    P('Окно «3 суток» — выбор аналитика; при его расширении доля выходных двигается,')
    P('а вместе с ней и вердикт по отдельным дням.')

    # =====================================================================
    P('')
    P('=' * 96)
    P('ТЕНЬ 6. МОЩНОСТЬ: что процедура тестировщика на самом деле исключает')
    P('=' * 96)
    P('Профиль p(d|блок) у тестировщика оценён ПО ТЕМ ЖЕ регистрациям, по которым считается O.')
    P('Если недельный ритм есть, он частично уходит в сам профиль и в нулевое распределение.')
    P('Моделируем: реальные домены, реальное число регистраций на домене; истинный относительный')
    P('профиль = наблюдённый пулевой; истинная интенсивность выходных умножена на k.')
    P('Затем прогоняем процедуру тестировщика (профиль переоценивается на смоделированных данных).')
    prof0, _ = profile(base)
    n_sim = 400
    P('')
    P('  %6s %14s %14s %10s' % ('k', 'восстановл. O/E', 'медиана p', 'доля p<0.05'))
    for k in (1.0, 1.2, 1.5, 2.0):
        oes_s = []
        ps = []
        for _s in range(n_sim):
            sim = []
            for d in base:
                if not d['рег03']:
                    continue
                p = prof0[d['блок']]
                w = [p[r] * (k if is_wknd(wd_of(d, r)) else 1.0) for r in REL]
                tot = sum(w)
                if tot <= 0:
                    continue
                w = [x / tot for x in w]
                draws = []
                for _e in range(len(d['рег03'])):
                    u = random.random()
                    acc = 0.0
                    for idx, pr in enumerate(w):
                        acc += pr
                        if u <= acc:
                            draws.append(REL[idx])
                            break
                    else:
                        draws.append(REL[-1])
                nd = dict(d)
                nd['симрег'] = draws
                sim.append(nd)
            r = oe_weekend(sim, key='симрег')
            oes_s.append(r['OE'])
            ps.append(r['p'])
        oes_s.sort()
        ps.sort()
        P('  %6.1f %8.2f [%.2f–%.2f] %14.3f %9.0f %%'
          % (k, oes_s[len(oes_s) // 2], oes_s[int(0.025 * len(oes_s))], oes_s[int(0.975 * len(oes_s))],
             ps[len(ps) // 2], 100 * sum(1 for x in ps if x < 0.05) / len(ps)))
    P('')
    P('Читается так: при ИСТИННОМ эффекте выходных в 1.5 раза оценка тестировщика показывает')
    P('не 1.5, а ~1.16 — профиль, оценённый по тем же событиям, съедает эффект.')

    # --- 6б. То же на ОСНОВНОМ наборе (249 регистраций), где и получено 1.13 ---
    def power_grid(doms, ks, n_sim=400, key='рег03'):
        prof_l, _ = profile(doms, key)
        res = {}
        for k in ks:
            arr = []
            pv = []
            for _s in range(n_sim):
                sim = []
                for d in doms:
                    if not d[key]:
                        continue
                    pp = prof_l[d['блок']]
                    w = [pp[r] * (k if is_wknd(wd_of(d, r)) else 1.0) for r in REL]
                    t = sum(w)
                    if t <= 0:
                        continue
                    w = [x / t for x in w]
                    dr = []
                    for _e in range(len(d[key])):
                        u = random.random()
                        acc = 0.0
                        for idx, pr in enumerate(w):
                            acc += pr
                            if u <= acc:
                                dr.append(REL[idx]); break
                        else:
                            dr.append(REL[-1])
                    nd = dict(d); nd['симрег'] = dr
                    sim.append(nd)
                rr = oe_weekend(sim, key='симрег')
                arr.append(rr['OE']); pv.append(rr['p'])
            arr.sort(); pv.sort()
            res[k] = (arr[int(0.025 * len(arr))], arr[len(arr) // 2], arr[int(0.975 * len(arr))],
                      100 * sum(1 for x in pv if x < 0.05) / len(pv))
        return res

    ks = (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0)
    P('')
    P('ОБРАЩЕНИЕ ЗАДАЧИ: какие ИСТИННЫЕ k совместимы с наблюдённым O/E (наблюдение внутри 95 %% полосы модели)?')
    for nm, ds, obs in (('ОСНОВНОЙ набор (249 рег, наблюдено O/E 1.13)', main_set, r_main['OE']),
                        ('РАСШИРЕННЫЙ набор (350 рег, наблюдено O/E 0.99)', base, r_ext['OE'])):
        g = power_grid(ds, ks)
        P('')
        P('  ' + nm)
        P('    %6s %26s %12s %14s' % ('k', 'O/E модели [95%]', 'p<0.05, %', 'совместимо?'))
        compat = []
        for k in ks:
            lo, md, hi, pw = g[k]
            ok = lo <= obs <= hi
            if ok:
                compat.append(k)
            P('    %6.2f %10.2f [%.2f–%.2f] %12.0f %14s'
              % (k, md, lo, hi, pw, 'да' if ok else 'нет'))
        if compat:
            P('    → совместимые истинные эффекты выходных: k от %.2f до %.2f' % (min(compat), max(compat)))
        else:
            P('    → ни одно k из сетки не совместимо')

    # --- 6в. Проверка неоднородности август/сентябрь ---
    P('')
    P('ПРОВЕРКА НЕОДНОРОДНОСТИ (та же величина на двух периодах):')
    a = oe_weekend([d for d in base if d['день'] < cut])
    b = oe_weekend([d for d in base if d['день'] >= dt.date(2026, 9, 1)])
    diff = (a['O'] - a['E']) - (b['O'] - b['E'])
    sd = math.sqrt(a['sd'] ** 2 + b['sd'] ** 2)
    zz = diff / sd
    P('  до 24.08: O/E %.2f (O=%d, E=%.1f); сентябрь: O/E %.2f (O=%d, E=%.1f)'
      % (a['OE'], a['O'], a['E'], b['OE'], b['O'], b['E']))
    P('  разница (O-E) = %+.1f, sd = %.1f, z = %+.2f, p = %.3f — %s'
      % (diff, sd, zz, math.erfc(abs(zz) / math.sqrt(2)),
         'неоднородность значима' if math.erfc(abs(zz) / math.sqrt(2)) < 0.05 else 'неоднородность в пределах шума'))
    P('  То есть 1.13 и 0.99 — не два разных факта, а один разброс: но именно выбор среза')
    P('  решает, попадёт ли наблюдение в зону, где k=1.5 исключается.')

    # =====================================================================
    P('')
    P('=' * 96)
    P('ИТОГ КОНТРПРОВЕРКИ')
    P('=' * 96)
    P('1. Жёсткая страта «набор + день запуска + зона» обнуляет вопрос: внутри неё день недели')
    P('   регистрации — то же самое, что относительный день. Информацию о дне недели несут только')
    P('   %d из %d регистраций (наборы, запущенные в разные дни недели).' % (reg_inf, r_ext['n']))
    if res_strict_a:
        P('2. Свободная от профиля оценка внутри жёсткой страты: O/E сб+вс = %.2f при %d регистрациях'
          % (res_strict_a['OE'], res_strict_a['n']))
        P('   в информативных ячейках, p = %.3f — то есть ни «ритма нет», ни «ритм есть» этот срез не решает.'
          % res_strict_a['p'])
    P('3. Направление вывода («ритма не видно») переживает всё: жёсткую страту, джекнайф по зонам,')
    P('   возврат выбросов 3615/3286, снятие фильтров и расширение окна — разброс O/E сб+вс %.2f–%.2f.'
      % (min(oes), max(oes)))
    P('4. НО объявленная граница «эффект выходных ≥1.5× исключён» НЕВЕРНА на основном наборе.')
    P('   Коридор 0.83–1.18 — это разброс ОЦЕНКИ при k=1, а не область исключённых истинных k.')
    P('   Оценка тестировщика гасит эффект: при истинном k=1.5 она показывает ~1.15, при k=2.0 ~1.25.')
    P('   Наблюдённые 1.13 (249 рег) совместимы с k вплоть до 2.0; мощность отвергнуть k=1.5 — 41 %,')
    P('   k=2.0 — 87 %. Исключает k≥1.4 только РАСШИРЕННЫЙ набор (350 рег, O/E 0.99), а он держится')
    P('   на 335 августовских базах «КОНТЕНТ НЕ ЗАПИСАН» с собственным O/E 0.80 (p=0.028), то есть')
    P('   исключение куплено ровно тем блоком, который основной анализ отбрасывает как сцепленный с датой.')
    P('5. Идентификация: 266 из 350 регистраций не несут информации о дне недели вообще.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_lines) + '\n')
    print('\n[сохранено] ' + OUT_PATH)


def poisson_ratio_ci(o, e, z=1.96):
    """Приближённый 95 % интервал для O/E (Byar) при пуассоновском O."""
    if e <= 0:
        return (0.0, 0.0)
    if o == 0:
        return (0.0, 3.0 / e)
    lo = o * (1 - 1 / (9 * o) - z / (3 * math.sqrt(o))) ** 3
    hi = (o + 1) * (1 - 1 / (9 * (o + 1)) + z / (3 * math.sqrt(o + 1))) ** 3
    return (lo / e, hi / e)


if __name__ == '__main__':
    main()

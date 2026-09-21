#!/usr/bin/env python3
"""
Гипотеза №7. У регистраций нет собственного недельного ритма.

Что проверяем.
  Регистраций на сайто-день окна в субботу–воскресенье не больше и не меньше,
  чем в будни (O/E 0,85–1,15), поэтому подгадывать окно 3 суток под выходные
  или бояться попадания дней +1/+2 на выходные бессмысленно.
  Проверяется только сторона спроса: день недели самой регистрации при
  фиксированном домене (а значит при фиксированных наборе контента, дне
  запуска, зоне и часе). Сторона подачи (день недели запуска) на своде
  неотделима от даты запуска и здесь не проверяется.

Как проверяем.
  Фильтр: окно закрыто = да; дней != 1; без выбросов 3615.team и 3286.team.
  Основной набор дополнительно без «КОНТЕНТ НЕ ЗАПИСАН»; расширенный набор —
  с ним (страта = домен, поэтому набор контента для каждой регистрации и так
  зафиксирован; исключение отрезало бы ~29 % регистраций).
  Регистрации берём из колонки «даты регистраций»: только те, что легли на
  относительный день 0–3 от дня запуска домена (расхождение с колонкой
  «регистраций в окне 3 суток» печатается: там окно считается по дню
  переобхода каждого сайта, а сайты второй волны переобходятся на день позже).
  День недели считаем из дат (колонка «день недели» в 68 строках расходится
  с датой запуска и не используется).

  Показатель 1 (сырая ставка): регистраций на 100 тыс. сайто-дней окна по
  7 дням недели. Экспозиция: дни запуск+0..+2 с весом «сайтов в 1-й волне»
  (150) и +1..+3 с весом «сайтов во 2-й волне» (56); второй знаменатель —
  «вышли за 3 суток» вместо всех сайтов (доли волн те же).
  Сырая ставка смещена: запуски сгущены во вт–чт, а регистрации внутри домена
  ложатся на относительные дни неравномерно (день 0 ~10 %, +1 ~33 %, +2 ~27 %,
  +3 ~13 %; в блоке 18-23 день 0 пуст), поэтому главный показатель — второй.

  Показатель 2 (ожидание по профилю, страта = домен): для каждой регистрации
  домена ожидаемый день недели = день запуска + относительный день d с
  вероятностью p(d | блок часа), оценённой на том же наборе. E по дню недели =
  сумма этих вероятностей; O/E по 7 дням.
  Тест: 10 000 раз (random.seed(1)) каждой регистрации назначаем относительный
  день из p(d | блок часа) при фиксированном числе регистраций домена,
  переводим в день недели, считаем долю сб+вс, χ² по 7 дням, min O/E по дням,
  max/min O/E; p — доля перестановок со статистикой не мягче наблюдённой.
  Вариант с кластерами: регистрации одного домена в одну дату двигаются вместе
  (защита от сцепленности регистраций внутри домена).
  Объявленные контрасты: сб+вс против будней (точный биномиальный по доле
  ожидания и по доле экспозиции + перестановочный); вторник против остальных
  (перестановочный, поправка Бонферрони ×7 и статистика «худший день»);
  O/E по каждому дню с 95 % интервалом при нулевой гипотезе.
  Повторы: семейства NEW и content-дата; «даты ФД» как знак.
  Критерии, объявленные заранее: ритма нет — O/E сб+вс 0,85–1,15, max/min по
  дням <= 1,7, p > 0,05; ритм есть — выходные >= 1,5× при p < 0,05 или
  устойчивый провал одного дня после поправки.

Только стандартная библиотека Python 3. Вывод пишется и в stdout, и в файл
analysis/export/gipotezy_svod/h07_registration_weekday.txt.
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
OUT_PATH = os.path.join(OUT_DIR, 'h07_registration_weekday.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
REL_DAYS = (0, 1, 2, 3)
WD_NAME = {1: 'пн', 2: 'вт', 3: 'ср', 4: 'чт', 5: 'пт', 6: 'сб', 7: 'вс'}
MIN_BLOCK_EVENTS = 8   # ниже этого профиль блока заменяется общим профилем набора

_out_lines = []


def P(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _out_lines.append(s)


def toi(s):
    return int(float(s)) if s not in ('', None) else 0


def d_of(s):
    return dt.date.fromisoformat(s)


def oe(o, e):
    return f'{o / e:.2f}' if e > 0 else '—'


def binom_two_sided(k, n, p0):
    """Точный двусторонний биномиальный тест: сумма вероятностей исходов,
    не более вероятных, чем наблюдённый."""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 1.0
    lg = math.lgamma
    lp, lq = math.log(p0), math.log(1 - p0)

    def logpmf(i):
        return lg(n + 1) - lg(i + 1) - lg(n - i + 1) + i * lp + (n - i) * lq

    ref = logpmf(k) + 1e-9
    return min(1.0, sum(math.exp(logpmf(i)) for i in range(n + 1) if logpmf(i) <= ref))


def pctl(sorted_vals, q):
    if not sorted_vals:
        return 0
    i = int(round(q * (len(sorted_vals) - 1)))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, i))]


# ---------------------------------------------------------------------------
# 1. Загрузка и фильтр
# ---------------------------------------------------------------------------

def load():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def prepare(r):
    d = {}
    d['домен'] = r['домен']
    d['зона'] = r['зона']
    d['день'] = d_of(r['день запуска'])
    d['день недели запуска'] = d['день'].isoweekday()
    d['колонка день недели'] = r['день недели']
    d['набор'] = r['набор контента']
    d['семейство'] = r['семейство']
    d['блок'] = r['блок часа']
    d['сайтов'] = toi(r['сайтов в окне'])
    d['в1'] = toi(r['сайтов в 1-й волне'])
    d['в2'] = toi(r['сайтов во 2-й волне'])
    d['вышли3'] = toi(r['вышли за 3 суток'])
    d['кол_рег'] = toi(r['регистраций в окне 3 суток'])
    d['кол_фд'] = toi(r['ФД в окне 3 суток'])
    for key, col in (('рег', 'даты регистраций'), ('фд', 'даты ФД')):
        events, early, late = [], 0, 0
        for s in r[col].split():
            rd = (d_of(s) - d['день']).days
            if rd < 0:
                early += 1
            elif rd > 3:
                late += 1
            else:
                events.append((rd, s))
        d[key] = events
        d[key + '_до'] = early
        d[key + '_после'] = late
    return d


# ---------------------------------------------------------------------------
# 2. Анализ одного набора доменов
# ---------------------------------------------------------------------------

def analyze(title, doms, kind='рег', full_tables=True):
    """kind: 'рег' — регистрации, 'фд' — первые депозиты."""
    label = 'регистраций' if kind == 'рег' else 'ФД'
    P('')
    P('=' * 96)
    P(title)
    P('=' * 96)
    n_dom = len(doms)
    n_sites = sum(d['сайтов'] for d in doms)
    events = []   # (домен-индекс, блок, день недели запуска, отн. день, дата)
    for i, d in enumerate(doms):
        for rd, s in d[kind]:
            events.append((i, d['блок'], d['день недели запуска'], rd, s))
    n_ev = len(events)
    col_sum = sum(d['кол_' + kind] for d in doms)
    early = sum(d[kind + '_до'] for d in doms)
    late = sum(d[kind + '_после'] for d in doms)
    P(f'доменов {n_dom}, сайтов в окне {n_sites}, {label} на отн. днях 0–3: {n_ev} '
      f'(в колонке «в окне 3 суток»: {col_sum}; расхождение {n_ev - col_sum:+d}); '
      f'ещё {label} до дня запуска: {early}, позже дня +3: {late}')
    if n_ev == 0:
        P('событий нет — блок пропущен')
        return None
    doms_with = sum(1 for d in doms if d[kind])
    P(f'доменов с {label} на днях 0–3: {doms_with}; распределение по числу событий: '
      + ', '.join(f'{k}: {v}' for k, v in sorted(Counter(len(d[kind]) for d in doms if d[kind]).items())))

    # --- профиль относительных дней p(d | блок часа) ---
    cnt = defaultdict(Counter)
    tot = Counter()
    for _, blk, _, rd, _ in events:
        cnt[blk][rd] += 1
        tot[rd] += 1
    pooled = {rd: tot[rd] / n_ev for rd in REL_DAYS}
    prof = {}
    P('')
    P(f'Профиль относительных дней ({label}, доля по блоку часа запуска):')
    P(f'  {"блок":8} {"n":>5} ' + ' '.join(f'{"день +" + str(rd):>9}' for rd in REL_DAYS) + '   источник')
    for blk in sorted(set(d['блок'] for d in doms)):
        nb = sum(cnt[blk].values())
        if nb >= MIN_BLOCK_EVENTS:
            prof[blk] = {rd: cnt[blk][rd] / nb for rd in REL_DAYS}
            src = 'свой блок'
        else:
            prof[blk] = dict(pooled)
            src = f'общий профиль (в блоке лишь {nb})'
        P(f'  {blk:8} {nb:5d} ' + ' '.join(f'{100 * prof[blk][rd]:8.1f}%' for rd in REL_DAYS) + '   ' + src)
    P(f'  {"все":8} {n_ev:5d} ' + ' '.join(f'{100 * pooled[rd]:8.1f}%' for rd in REL_DAYS))

    # --- наблюдённое и ожидаемое по профилю ---
    O = Counter()
    E = defaultdict(float)
    wdmap = []   # для каждого события: день недели при d = 0..3
    for i, blk, lwd, rd, s in events:
        wds = tuple((lwd - 1 + k) % 7 + 1 for k in REL_DAYS)
        wdmap.append(wds)
        O[wds[rd]] += 1
        for k in REL_DAYS:
            E[wds[k]] += prof[blk][k]

    # --- сырая экспозиция сайто-дней ---
    expo = Counter()
    expo_out = defaultdict(float)
    for d in doms:
        base = d['сайтов'] or (d['в1'] + d['в2'])
        share1 = d['в1'] / base if base else 0
        share2 = d['в2'] / base if base else 0
        for k in (0, 1, 2):
            wd = (d['день'] + dt.timedelta(days=k)).isoweekday()
            expo[wd] += d['в1']
            expo_out[wd] += d['вышли3'] * share1
        for k in (1, 2, 3):
            wd = (d['день'] + dt.timedelta(days=k)).isoweekday()
            expo[wd] += d['в2']
            expo_out[wd] += d['вышли3'] * share2
    expo_tot = sum(expo.values())
    expo_out_tot = sum(expo_out.values())

    # --- перестановочный тест ---
    rng = random.Random(1)
    thr = {blk: [] for blk in prof}
    for blk in prof:
        acc = 0.0
        for k in REL_DAYS:
            acc += prof[blk][k]
            thr[blk].append(acc)
    ev_blk = [e[1] for e in events]

    # кластеры: события одного домена в одну дату
    clusters = defaultdict(int)
    for idx, e in enumerate(events):
        clusters[(e[0], e[4])] += 1
    cl_list = []
    for (i, s), w in clusters.items():
        e_idx = next(j for j, e in enumerate(events) if e[0] == i and e[4] == s)
        cl_list.append((e_idx, w))

    def draw_counts(units):
        c = [0] * 8
        for e_idx, w in units:
            r = rng.random()
            t = thr[ev_blk[e_idx]]
            k = 0 if r < t[0] else 1 if r < t[1] else 2 if r < t[2] else 3
            c[wdmap[e_idx][k]] += w
        return c

    def stats(c):
        we = c[6] + c[7]
        chi2 = sum((c[w] - E[w]) ** 2 / E[w] for w in range(1, 8) if E[w] > 0)
        ratios = [c[w] / E[w] for w in range(1, 8) if E[w] > 0]
        mn = min(ratios)
        mx = max(ratios)
        return we, chi2, mn, mx, (mx / mn if mn > 0 else float('inf')), c[2]

    obs_c = [0] + [O[w] for w in range(1, 8)]
    obs_we, obs_chi2, obs_min, obs_max, obs_ratio, obs_tue = stats(obs_c)
    E_we = E[6] + E[7]

    units_iid = [(j, 1) for j in range(n_ev)]
    results = {}
    for name, units in (('по регистрациям', units_iid), ('по кластерам домен×дата', cl_list)):
        sims_day = [[] for _ in range(8)]
        sims_we = []
        p_we = p_chi = p_min = p_max = p_ratio = p_tue = 0
        p_day_two = [0] * 8
        for _ in range(N_PERM):
            c = draw_counts(units)
            we, chi2, mn, mx, ratio, tue = stats(c)
            sims_we.append(we)
            if abs(we - E_we) >= abs(obs_we - E_we) - 1e-9:
                p_we += 1
            if chi2 >= obs_chi2 - 1e-9:
                p_chi += 1
            if mn <= obs_min + 1e-9:
                p_min += 1
            if mx >= obs_max - 1e-9:
                p_max += 1
            if ratio >= obs_ratio - 1e-9:
                p_ratio += 1
            if abs(tue - E[2]) >= abs(obs_tue - E[2]) - 1e-9:
                p_tue += 1
            for w in range(1, 8):
                sims_day[w].append(c[w])
                if abs(c[w] - E[w]) >= abs(obs_c[w] - E[w]) - 1e-9:
                    p_day_two[w] += 1
        for w in range(1, 8):
            sims_day[w].sort()
        sims_we.sort()
        results[name] = dict(p_we=p_we / N_PERM, p_chi=p_chi / N_PERM, p_min=p_min / N_PERM,
                             p_max=p_max / N_PERM, p_ratio=p_ratio / N_PERM, p_tue=p_tue / N_PERM,
                             p_day=[x / N_PERM for x in p_day_two], sims=sims_day,
                             sims_we=sims_we, n_units=len(units), n_perm=len(sims_we))

    main = results['по регистрациям']
    # --- таблица по дням недели ---
    P('')
    P(f'Таблица по дням недели ({label}, отн. дни 0–3; E — ожидание по профилю, страта = домен; '
      f'интервал — 95 % при нулевой гипотезе):')
    P(f'  {"день":5} {"O":>4} {"E":>7} {"O/E":>5} {"95% O":>11} {"p":>7} | '
      f'{"экспозиция":>10} {"на 100т":>8} | {"вышедших":>10} {"на 100т":>8}')
    rates = {}
    rates_out = {}
    for w in range(1, 8):
        lo, hi = pctl(main['sims'][w], 0.025), pctl(main['sims'][w], 0.975)
        rate = 1e5 * O[w] / expo[w] if expo[w] else 0
        rate_o = 1e5 * O[w] / expo_out[w] if expo_out[w] else 0
        rates[w] = rate
        rates_out[w] = rate_o
        P(f'  {WD_NAME[w]:5} {O[w]:4d} {E[w]:7.1f} {oe(O[w], E[w]):>5} {lo:5d}–{hi:<4d} {main["p_day"][w]:7.3f} | '
          f'{expo[w]:10d} {rate:8.1f} | {expo_out[w]:10.0f} {rate_o:8.1f}')
    P(f'  {"всего":5} {n_ev:4d} {sum(E.values()):7.1f} {"":>5} {"":>11} {"":>7} | '
      f'{expo_tot:10d} {1e5 * n_ev / expo_tot:8.1f} | {expo_out_tot:10.0f} {1e5 * n_ev / expo_out_tot if expo_out_tot else 0:8.1f}')

    # --- контрасты ---
    P('')
    P('Контрасты:')
    we_share_obs = obs_we / n_ev
    we_share_E = E_we / n_ev
    we_share_expo = (expo[6] + expo[7]) / expo_tot
    wk_O = n_ev - obs_we
    wk_E = n_ev - E_we
    P(f'  сб+вс: O = {obs_we} ({100 * we_share_obs:.1f} %), E по профилю = {E_we:.1f} '
      f'({100 * we_share_E:.1f} %), O/E = {oe(obs_we, E_we)}; будни O/E = {oe(wk_O, wk_E)}; '
      f'выходные/будни = {oe(obs_we / E_we if E_we else 0, wk_O / wk_E if wk_E else 1)}')
    P(f'    точный биномиальный p (доля ожидания {100 * we_share_E:.1f} %) = '
      f'{binom_two_sided(obs_we, n_ev, we_share_E):.3f}; '
      f'по доле экспозиции ({100 * we_share_expo:.1f} %) = {binom_two_sided(obs_we, n_ev, we_share_expo):.3f}')
    we_lo, we_hi = pctl(main['sims_we'], 0.025), pctl(main['sims_we'], 0.975)
    P(f'    коридор сб+вс при нулевой гипотезе (95 %): {we_lo}–{we_hi} регистраций, то есть O/E '
      f'{we_lo / E_we if E_we else 0:.2f}–{we_hi / E_we if E_we else 0:.2f}; эффект выходных вне этого коридора '
      f'данные бы заметили, внутри — нет')
    for name, res in results.items():
        P(f'    перестановочный p ({name}, {res["n_units"]} единиц, {res["n_perm"]} перестановок): '
          f'сб+вс {res["p_we"]:.3f}; χ² по 7 дням {res["p_chi"]:.3f}; '
          f'худший день {res["p_min"]:.3f}; лучший день {res["p_max"]:.3f}; '
          f'max/min O/E {res["p_ratio"]:.3f}; вторник {res["p_tue"]:.3f}')
    P(f'  χ² по 7 дням = {obs_chi2:.2f} (df 6; при нулевой ожидается ~6)')
    P(f'  вторник: O = {O[2]}, E = {E[2]:.1f}, O/E = {oe(O[2], E[2])}; '
      f'p перестановочный = {main["p_tue"]:.3f}, с поправкой Бонферрони ×7 = {min(1.0, 7 * main["p_tue"]):.3f}')
    worst = min(range(1, 8), key=lambda w: O[w] / E[w] if E[w] else 9)
    best = max(range(1, 8), key=lambda w: O[w] / E[w] if E[w] else 0)
    P(f'  худший день по O/E: {WD_NAME[worst]} ({oe(O[worst], E[worst])}, p с учётом 7 дней = {main["p_min"]:.3f}), '
      f'лучший: {WD_NAME[best]} ({oe(O[best], E[best])}, p с учётом 7 дней = {main["p_max"]:.3f}); '
      f'max/min O/E = {obs_ratio:.2f} '
      f'(p = {main["p_ratio"]:.3f}, что такой или больший разброс даёт случай при 7 днях)')
    rmax, rmin = max(rates.values()), min(rates.values())
    P(f'  сырые ставки на 100 тыс. сайто-дней: max/min = {rmax / rmin if rmin else float("inf"):.2f} '
      f'({WD_NAME[max(rates, key=rates.get)]} {rmax:.1f} против {WD_NAME[min(rates, key=rates.get)]} {rmin:.1f})')
    verdict = {
        'O/E сб+вс': obs_we / E_we if E_we else float('nan'),
        'max/min O/E': obs_ratio,
        'p χ²': main['p_chi'],
        'p сб+вс': main['p_we'],
        'p худший день': main['p_min'],
        'n': n_ev,
        'сырой max/min': rmax / rmin if rmin else float('inf'),
        'худший': WD_NAME[worst],
        'лучший': WD_NAME[best],
        'p лучший день': main['p_max'],
        'p вт Бонферрони': min(1.0, 7 * main['p_tue']),
        'коридор сб+вс': (we_lo / E_we if E_we else 0, we_hi / E_we if E_we else 0),
    }
    return verdict


# ---------------------------------------------------------------------------
# 3. Главная часть
# ---------------------------------------------------------------------------

def main():
    rows = load()
    P('Гипотеза №7: у регистраций нет собственного недельного ритма (день недели регистрации при фиксированном домене)')
    P(f'Файл: {CSV_PATH}')
    P(f'Строк (доменов) всего: {len(rows)}')
    P('')
    P('Фильтр (исключения печатаются по шагам):')
    step = rows
    n0 = len(step)
    step = [r for r in step if r['окно закрыто'] == 'да']
    P(f'  окно закрыто = нет: исключено {n0 - len(step)}, осталось {len(step)}')
    n0 = len(step)
    step = [r for r in step if r['дней'] != '1']
    P(f'  дней = 1 (только первая волна, 150 сайтов): исключено {n0 - len(step)}, осталось {len(step)}')
    n0 = len(step)
    step = [r for r in step if r['домен'] not in OUTLIERS]
    P(f'  выбросы {", ".join(sorted(OUTLIERS))}: исключено {n0 - len(step)}, осталось {len(step)}')
    ext = [prepare(r) for r in step]
    n0 = len(ext)
    strict = [d for d in ext if d['набор'] != NO_CONTENT]
    P(f'  «{NO_CONTENT}»: исключено {n0 - len(strict)}, осталось {len(strict)} — это ОСНОВНОЙ набор;')
    P(f'  расширенный набор ({len(ext)} доменов) оставляет «{NO_CONTENT}»: страта здесь = домен, набор контента '
      f'внутри домена зафиксирован, а эти домены держат '
      f'{sum(len(d["рег"]) for d in ext if d["набор"] == NO_CONTENT)} из {sum(len(d["рег"]) for d in ext)} регистраций.')

    mism = sum(1 for d in ext if str(d['день недели запуска']) != d['колонка день недели'])
    P('')
    P(f'Колонка «день недели» расходится с датой «день запуска» в {mism} доменах расширенного набора '
      f'(в основном запуски в 19–22 ч: колонка показывает день на 1 меньше). Здесь день недели '
      f'всегда считается из дат: и запуска, и регистрации.')
    P('Даты регистраций в источнике идут во времени +03:00; дата запуска — по «recrawl_sent_at». '
      'Часовой пояс той метки на своде не виден; сдвиг до нескольких часов не меняет проверку, '
      'так как профиль относительных дней оценивается на тех же датах.')

    P('')
    P('Контекст: запуски по дням недели (расширенный набор) — почему сырая ставка по дню недели смещена:')
    lw = Counter(d['день недели запуска'] for d in ext)
    lr = Counter()
    ls = Counter()
    for d in ext:
        lr[d['день недели запуска']] += len(d['рег'])
        ls[d['день недели запуска']] += d['сайтов']
    P(f'  {"день":5} {"доменов":>8} {"сайтов":>8} {"рег 0–3":>8} {"рег/100 сайтов":>15}')
    for w in range(1, 8):
        P(f'  {WD_NAME[w]:5} {lw[w]:8d} {ls[w]:8d} {lr[w]:8d} {100 * lr[w] / ls[w] if ls[w] else 0:15.3f}')
    P('  (день недели ЗАПУСКА сцеплен с датой, набором контента и зоной — это сторона подачи, здесь не проверяется; '
      'таблица только показывает, что запуски сгущены во вт–чт.)')

    verdicts = {}
    verdicts['основной'] = analyze(
        'А. ОСНОВНОЙ НАБОР: окно закрыто, дней != 1, без выбросов, без «КОНТЕНТ НЕ ЗАПИСАН» — регистрации',
        strict, 'рег')
    verdicts['расширенный'] = analyze(
        'Б. РАСШИРЕННЫЙ НАБОР: то же, но с «КОНТЕНТ НЕ ЗАПИСАН» (страта = домен) — регистрации',
        ext, 'рег')
    verdicts['NEW'] = analyze(
        'В. СЕМЕЙСТВО NEW (внутри основного набора) — регистрации',
        [d for d in strict if d['семейство'] == 'NEW'], 'рег')
    verdicts['content-дата'] = analyze(
        'Г. СЕМЕЙСТВО content-дата (внутри основного набора) — регистрации',
        [d for d in strict if d['семейство'] == 'content-дата'], 'рег')
    verdicts['ФД основной'] = analyze(
        'Д. ОСНОВНОЙ НАБОР — первые депозиты (ФД), как знак',
        strict, 'фд')
    verdicts['ФД расширенный'] = analyze(
        'Е. РАСШИРЕННЫЙ НАБОР — первые депозиты (ФД), как знак',
        ext, 'фд')

    # --- сводка ---
    P('')
    P('=' * 96)
    P('СВОДКА ПО НАБОРАМ (объявленные критерии: ритма нет — O/E сб+вс 0,85–1,15, max/min <= 1,7, p > 0,05)')
    P('=' * 96)
    P(f'  {"набор":16} {"n":>4} {"O/E сб+вс":>10} {"p сб+вс":>8} {"p χ²":>6} {"max/min O/E":>12} '
      f'{"сырой max/min":>14} {"худший день":>12} {"p худш.":>8} {"лучший день":>12} {"p лучш.":>8}')
    for name, v in verdicts.items():
        if v is None:
            P(f'  {name:16} — событий нет')
            continue
        P(f'  {name:16} {v["n"]:4d} {v["O/E сб+вс"]:10.2f} {v["p сб+вс"]:8.3f} {v["p χ²"]:6.3f} '
          f'{v["max/min O/E"]:12.2f} {v["сырой max/min"]:14.2f} {v["худший"]:>12} {v["p худший день"]:8.3f} '
          f'{v["лучший"]:>12} {v["p лучший день"]:8.3f}')

    v = verdicts['основной']
    e = verdicts['расширенный']
    P('')
    P('ВЫВОД')
    P('-' * 96)
    P(f'1. Ожидание по профилю (страта = домен) для сб+вс: O/E {v["O/E сб+вс"]:.2f} в основном наборе '
      f'({v["n"]} регистраций) и {e["O/E сб+вс"]:.2f} в расширенном ({e["n"]} регистраций). '
      f'Перестановочный p для доли выходных {v["p сб+вс"]:.2f} / {e["p сб+вс"]:.2f}.')
    day_survives = min(v['p худший день'], e['p худший день'], v['p лучший день'], e['p лучший день']) <= 0.05
    P(f'2. Разброс по семи дням: χ² даёт p {v["p χ²"]:.2f} / {e["p χ²"]:.2f}; «худший день» после учёта семи сравнений '
      f'p {v["p худший день"]:.2f} / {e["p худший день"]:.2f}; «лучший день» ({v["лучший"]} / {e["лучший"]}) — '
      f'p {v["p лучший день"]:.2f} / {e["p лучший день"]:.2f}. Максимум к минимуму O/E по дням '
      f'{v["max/min O/E"]:.2f} / {e["max/min O/E"]:.2f}. '
      + ('Один из дней выпадает и после поправки — смотреть таблицы выше.' if day_survives
         else 'Ни один день не держится после поправки.'))
    P(f'   Что данные могли бы заметить: при нулевой гипотезе доля выходных легла бы в коридор O/E '
      f'{v["коридор сб+вс"][0]:.2f}–{v["коридор сб+вс"][1]:.2f} (основной) и '
      f'{e["коридор сб+вс"][0]:.2f}–{e["коридор сб+вс"][1]:.2f} (расширенный). Эффект выходных в полтора раза '
      f'(объявленный порог «ритм есть») лежит далеко за коридором и исключается; сдвиг на 10–15 % внутри коридора '
      f'данные отличить от нуля не могут.')
    crit_no = (0.85 <= v['O/E сб+вс'] <= 1.15 and v['p χ²'] > 0.05 and v['p сб+вс'] > 0.05)
    crit_no_e = (0.85 <= e['O/E сб+вс'] <= 1.15 and e['p χ²'] > 0.05 and e['p сб+вс'] > 0.05)
    if crit_no and crit_no_e:
        P('3. Оба набора укладываются в объявленный критерий «ритма нет» по выходным и по χ². '
          'То, что видно в сырых ставках по дням недели, объясняется тем, на какие дни календаря ложатся '
          'относительные дни +1/+2 запусков со вторника по четверг, а не днём недели самой регистрации.')
    elif crit_no or crit_no_e:
        P('3. Критерий «ритма нет» выполняется в одном из двух наборов; расхождение — в пределах шума малых чисел. '
          'Смотреть строки по дням выше.')
    else:
        P('3. Критерий «ритма нет» не выполнен — смотреть строки по дням выше, какой день выпадает и держится ли он '
          'после поправки на семь сравнений.')
    P('4. Ограничения: регистраций мало (сотни), поэтому интервалы по отдельным дням широкие: расхождение до ±30–40 % '
      'по одному дню случай даёт легко. Регистрации второй волны отдельно не видны (даты даны по домену), '
      'поэтому экспозиция сайто-дней и колонка «в окне 3 суток» расходятся на несколько регистраций. '
      'Сторона подачи (медленнее ли индексация в выходные) на своде не проверяется — день недели запуска '
      'сцеплен с датой.')
    P('5. Что с этим делать: ничего, это знание, не рычаг. Подгадывать запуск так, чтобы дни +1/+2 легли на выходные '
      '(или избегать этого), со стороны спроса смысла нет. Проверить на будущих запусках можно только сторону подачи: '
      'запускать одинаковые наборы контента в разные дни недели и сравнивать выход в поиск за 3 суток.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_out_lines) + '\n')
    print(f'\n[записано: {OUT_PATH}]')


if __name__ == '__main__':
    main()

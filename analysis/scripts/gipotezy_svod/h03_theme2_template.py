#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Гипотеза №3. Шаблон Theme2 (55 доменов, почти все 19–20.08, 47 в .team) вдвое
снижает выход в поиск и в 4–8 раз — регистрации по сравнению с Theme1 того же
дня и зоны. Оговорка гипотезы: в эти дни набор контента не записан, поэтому
обязателен контроль, что Theme2 — не скрытая партия (одна закупка/один сеанс
постановки), а именно шаблон.

Что проверяем:
  1. Срез: день запуска ∈ {2026-08-19, 2026-08-20}, зона team, окно закрыто = да,
     дней ≠ 1, без выбросов 3615.team и 3286.team. Число исключённых печатается.
     «КОНТЕНТ НЕ ЗАПИСАН» — у всех доменов среза, исключить нельзя; поэтому
     страта «набор контента + день» здесь вырождается в «день», и это честно
     оговаривается: тень набора контента в эти дни не снимается.
  2. Грубая проверка (страта = день): E для Theme2 = доля выхода дня × сайтов
     в окне домена, O = вышли за 3 суток; O/E суммарно по двум дням. Рядом —
     O/E, где E считается по доле Theme1 того же дня («во сколько раз хуже
     Theme1»). Перестановка метки шаблона внутри дня 10 000 раз (random.seed(1)),
     единица — домен; p — доля перестановок с O/E не выше наблюдённого.
     Регистрации в окне 3 суток: O/E, точный пуассоновский тест P(X ≤ O | λ=E)
     и та же перестановка. Вышли за 7 суток — догоняет ли Theme2.
  3. Контроль часа: то же внутри страты день × блок часа (в блоке 18-23
     39 Theme2 против 24 Theme1).
  4. Контроль скрытой партии: таблица шаблон × «сайтов» × час × паттерн имени;
     диапазоны номеров аккаунтов Вебмастера и cf-аккаунтов по партиям
     (партия = день × час постановки × «сайтов»). Если Theme2 сидит в своих
     партиях, а Theme1 — в своих, эффект шаблона от партии не отделим.
  5. Решающая проверка: страта = день × час × «сайтов» (партия), в расчёт идут
     только партии, где стоят не меньше 3 доменов каждого шаблона (иначе
     ожидание по Theme1 строится на одном домене). O/E, перестановка внутри
     партии, пуассон по регистрациям, вышли за 7 суток. Чувствительность —
     те же расчёты при страте день × час и день × час × сайтов с любой парой.
  6. Сверхдисперсия: χ²/df пулов 19–20.08 (пул = день) до и после разбиения
     по шаблону, и отдельно — после разбиения по партии (день × час × сайтов).
  7. Робастность: все зоны 19–20.08, страта день × зона × час (добавляет
     8 Theme2 вне .team).

Критерии подтверждения из плана: O/E выхода ≤ 0,6 и регистраций ≤ 0,4 при
p < 0,05, держится в блоке 18-23 и не совпадает с недоборной подгруппой.

Только stdlib. Вывод — в stdout и в
analysis/export/gipotezy_svod/h03_theme2_template.txt
"""
import csv
import math
import os
import random
import sys
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'h03_theme2_template.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
random.seed(1)
OUTLIERS = {'3615.team', '3286.team'}
DAYS = ('2026-08-19', '2026-08-20')

_lines = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    _lines.append(s)
    print(s)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def fmt(x, d=2):
    if x is None:
        return '—'
    return ('%.' + str(d) + 'f') % x


def ratio(o, e):
    return None if e <= 0 else o / e


def poisson_le(k, lam):
    """P(X <= k) при X ~ Пуассон(lam)."""
    if lam <= 0:
        return 1.0
    s = 0.0
    for i in range(0, int(k) + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


def poisson_ge(k, lam):
    if lam <= 0:
        return 0.0 if k > 0 else 1.0
    return max(0.0, 1.0 - poisson_le(int(k) - 1, lam)) if k > 0 else 1.0


# ---------------------------------------------------------------- чтение
with open(SRC, encoding='utf-8') as fh:
    rows = list(csv.DictReader(fh))
p('Файл:', SRC)
p('Всего строк (доменов):', len(rows))
p()

# ---------------------------------------------------------------- фильтры
p('=' * 100)
p('ФИЛЬТРЫ И ИСКЛЮЧЕНИЯ')
p('=' * 100)
n_all = len(rows)
step = [r for r in rows if r['день запуска'] in DAYS]
p('День запуска 19.08 или 20.08:', len(step), '(отброшено других дней:', n_all - len(step), ')')
n0 = len(step)
step = [r for r in step if r['домен'] not in OUTLIERS]
p('Выбросы 3615.team / 3286.team в срезе:', n0 - len(step), '(исключено)')
n0 = len(step)
step = [r for r in step if r['окно закрыто'] == 'да']
p('Окно закрыто = нет в срезе:', n0 - len(step), '(исключено)')
n0 = len(step)
step = [r for r in step if r['дней'] != '1']
p('Дней = 1 в срезе:', n0 - len(step), '(исключено)')
all_zones = step
zone_cnt = Counter(r['зона'] for r in all_zones)
p('Зоны в срезе 19–20.08:', dict(zone_cnt))
main = [r for r in all_zones if r['зона'] == 'team']
p('Зона team (основной срез):', len(main), 'доменов; вне team:', len(all_zones) - len(main))
nz = Counter(r['набор контента'] for r in main)
p('Набор контента в основном срезе:', dict(nz))
p('  → «КОНТЕНТ НЕ ЗАПИСАН» у 100% доменов среза: исключить нельзя, иначе среза не останется.')
p('  → Страта «набор контента + день» вырождается в «день». Тень набора контента в эти дни НЕ снимается —')
p('    это и есть главный риск гипотезы (скрытая партия).')
p()

# всего Theme2 в файле
t2_all = [r for r in rows if r['шаблон'] == 'Theme2']
p('Theme2 во всём файле:', len(t2_all), 'доменов; по дню и зоне:',
  dict(Counter((r['день запуска'][5:], r['зона']) for r in t2_all)))
p('Theme2 в основном срезе (team, 19–20.08):', sum(1 for r in main if r['шаблон'] == 'Theme2'))
p('Theme2 вне основного среза:', len(t2_all) - sum(1 for r in main if r['шаблон'] == 'Theme2'),
  '— смотрим отдельно в разделе 7.')
p()

# ---------------------------------------------------------------- подготовка
for r in rows:
    r['_sites'] = fnum(r['сайтов в окне'])
    r['_v3'] = fnum(r['вышли за 3 суток'])
    r['_v7'] = fnum(r['вышли за 7 суток'])
    r['_reg'] = fnum(r['регистраций в окне 3 суток'])
    r['_fd'] = fnum(r['ФД в окне 3 суток'])
    r['_sclk'] = fnum(r['кликов из поиска в окне'])
    r['_hour'] = int(fnum(r['час запуска']))
    r['_day'] = r['день запуска'][5:]
    r['_t'] = r['шаблон']


def agg(ds):
    S = sum(r['_sites'] for r in ds)
    V3 = sum(r['_v3'] for r in ds)
    V7 = sum(r['_v7'] for r in ds)
    R = sum(r['_reg'] for r in ds)
    FD = sum(r['_fd'] for r in ds)
    C = sum(r['_sclk'] for r in ds)
    return dict(n=len(ds), S=S, V3=V3, V7=V7, R=R, FD=FD, C=C,
                ex3=100 * V3 / S if S else 0, ex7=100 * V7 / S if S else 0,
                r100=100 * R / S if S else 0, r10k=1e4 * R / C if C else 0,
                cps=C / S if S else 0)


HDR = ('%-6s %-7s %4s %7s %7s %6s %7s %6s %4s %3s %8s %8s %7s' %
       ('день', 'шаблон', 'n', 'сайтов', 'вышли3', 'вых%', 'вышли7', 'вых7%', 'рег', 'ФД', 'поиск.кл', 'рег/10к', 'кл/сайт'))


def line(day, t, a):
    return ('%-6s %-7s %4d %7d %7d %6.1f %7d %6.1f %4d %3d %8d %8.1f %7.1f' %
            (day, t, a['n'], a['S'], a['V3'], a['ex3'], a['V7'], a['ex7'], a['R'], a['FD'], a['C'], a['r10k'], a['cps']))


# ---------------------------------------------------------------- 1. описание
p('=' * 100)
p('1. ОПИСАНИЕ: день × шаблон (team, 19–20.08). Сайтов = сайтов в окне; рег = регистраций в окне 3 суток;')
p('   поиск.кл = кликов из поиска в окне; рег/10к = регистраций на 10 тыс. поисковых кликов в окне; кл/сайт = поисковых кликов на сайт')
p('=' * 100)
p(HDR)
for d in ('08-19', '08-20', 'оба'):
    for t in ('Theme1', 'Theme2'):
        ds = [r for r in main if r['_t'] == t and (d == 'оба' or r['_day'] == d)]
        p(line(d, t, agg(ds)))
p()
for d in ('08-19', '08-20'):
    a1 = agg([r for r in main if r['_t'] == 'Theme1' and r['_day'] == d])
    a2 = agg([r for r in main if r['_t'] == 'Theme2' and r['_day'] == d])
    p('  %s: выход Theme2/Theme1 = %.1f%% / %.1f%% = %.2f; рег на 100 сайтов %.2f / %.2f = %s' %
      (d, a2['ex3'], a1['ex3'], a2['ex3'] / a1['ex3'] if a1['ex3'] else 0,
       a2['r100'], a1['r100'], fmt(ratio(a2['r100'], a1['r100']))))
p()


# ---------------------------------------------------------------- движок O/E + перестановка
def oe_test(ds, strat_fn, metric, n_perm=N_PERM, label='Theme2', other='Theme1', seed=1, min_each=1):
    """
    O/E для доменов с меткой label внутри страт strat_fn(r). Берутся только страты, где есть обе метки.
    E_pool = доля страты (все домены) × сайтов домена; E_ref = доля Theme1 страты × сайтов домена.
    min_each — минимум доменов каждого шаблона в страте, чтобы страта шла в расчёт.
    Перестановка метки внутри страты; p = доля перестановок с O/E_pool <= наблюдённого.
    Возвращает словарь.
    """
    strata = defaultdict(list)
    for r in ds:
        strata[strat_fn(r)].append(r)
    used = {k: v for k, v in strata.items()
            if sum(1 for r in v if r['_t'] == label) >= min_each and sum(1 for r in v if r['_t'] == other) >= min_each}
    skipped = {k: v for k, v in strata.items() if k not in used}

    def stat(assign):  # assign: dict id(r)->label
        O = E = Eref = 0.0
        S_l = S_o = 0.0
        n_l = n_o = 0
        for k, v in used.items():
            tot_m = sum(r[metric] for r in v)
            tot_s = sum(r['_sites'] for r in v)
            m_o = sum(r[metric] for r in v if assign[id(r)] == other)
            s_o = sum(r['_sites'] for r in v if assign[id(r)] == other)
            rate_pool = tot_m / tot_s if tot_s else 0
            rate_ref = m_o / s_o if s_o else 0
            for r in v:
                if assign[id(r)] == label:
                    O += r[metric]
                    E += rate_pool * r['_sites']
                    Eref += rate_ref * r['_sites']
                    S_l += r['_sites']
                    n_l += 1
                else:
                    S_o += r['_sites']
                    n_o += 1
        return O, E, Eref, S_l, S_o, n_l, n_o

    obs_assign = {id(r): r['_t'] for r in ds}
    O, E, Eref, S_l, S_o, n_l, n_o = stat(obs_assign)
    obs = ratio(O, E)
    rnd = random.Random(seed)
    cnt_le = 0
    cnt_ge = 0
    if obs is not None and n_perm > 0:
        for _ in range(n_perm):
            assign = dict(obs_assign)
            for k, v in used.items():
                labs = [r['_t'] for r in v]
                rnd.shuffle(labs)
                for r, lb in zip(v, labs):
                    assign[id(r)] = lb
            Op, Ep, _, _, _, _, _ = stat(assign)
            rp = ratio(Op, Ep)
            if rp is None:
                rp = 1.0
            if rp <= obs + 1e-12:
                cnt_le += 1
            if rp >= obs - 1e-12:
                cnt_ge += 1
    return dict(O=O, E=E, Eref=Eref, oe=obs, oe_ref=ratio(O, Eref),
                p_le=(cnt_le / n_perm if n_perm else None), p_ge=(cnt_ge / n_perm if n_perm else None),
                n_strata=len(used), n_skipped=len(skipped), n_l=n_l, n_o=n_o, S_l=S_l, S_o=S_o,
                skipped_domains=sum(len(v) for v in skipped.values()),
                skipped_label=sum(1 for v in skipped.values() for r in v if r['_t'] == label))


def report_block(title, ds, strat_fn, strat_name, min_each=1):
    p('-' * 100)
    p(title)
    p('  Страта = %s. Учитываются только страты, где есть оба шаблона (не меньше %d доменов каждого).' % (strat_name, min_each))
    res3 = oe_test(ds, strat_fn, '_v3', min_each=min_each)
    p('  Страт использовано: %d (пропущено страт без пары: %d, в них %d доменов, из них Theme2: %d)' %
      (res3['n_strata'], res3['n_skipped'], res3['skipped_domains'], res3['skipped_label']))
    p('  Theme2: %d доменов, %d сайтов;  Theme1: %d доменов, %d сайтов' %
      (res3['n_l'], res3['S_l'], res3['n_o'], res3['S_o']))
    p('  ВЫХОД за 3 суток: O = %d, E(по пулу) = %.1f → O/E = %s; E(по Theme1) = %.1f → O/E = %s (во сколько раз хуже Theme1)' %
      (res3['O'], res3['E'], fmt(res3['oe']), res3['Eref'], fmt(res3['oe_ref'])))
    p('     перестановка %d раз: p(O/E ≤ набл.) = %s; p(O/E ≥ набл.) = %s' %
      (N_PERM, fmt(res3['p_le'], 4), fmt(res3['p_ge'], 4)))
    res7 = oe_test(ds, strat_fn, '_v7', n_perm=0, min_each=min_each)
    p('  ВЫХОД за 7 суток: O = %d, E(по пулу) = %.1f → O/E = %s; E(по Theme1) = %.1f → O/E = %s  %s' %
      (res7['O'], res7['E'], fmt(res7['oe']), res7['Eref'], fmt(res7['oe_ref']),
       '(догоняет)' if (res7['oe'] or 0) > (res3['oe'] or 0) + 0.05 else '(не догоняет)'))
    resr = oe_test(ds, strat_fn, '_reg', min_each=min_each)
    pois = poisson_le(resr['O'], resr['E'])
    p('  РЕГИСТРАЦИИ в окне 3 суток: O = %d, E(по пулу) = %.2f → O/E = %s; E(по Theme1) = %.2f → O/E = %s' %
      (resr['O'], resr['E'], fmt(resr['oe']), resr['Eref'], fmt(resr['oe_ref'])))
    p('     пуассон P(X ≤ %d | λ = %.2f) = %s; перестановка: p(O/E ≤ набл.) = %s' %
      (resr['O'], resr['E'], fmt(pois, 4), fmt(resr['p_le'], 4)))
    return res3, res7, resr


# ---------------------------------------------------------------- 2. грубая проверка
p('=' * 100)
p('2. ГРУБАЯ ПРОВЕРКА (как в плане): страта = день')
p('=' * 100)
crude = report_block('2a. Страта = день', main, lambda r: r['_day'], 'день запуска')
p()
p('  Примечание: на 20.08 Theme2 — это 38 из 70 доменов дня, поэтому E «по пулу» наполовину состоит из самих Theme2 и')
p('  O/E по пулу приближено к 1. Честнее смотреть на O/E «по Theme1»: это и есть «во сколько раз хуже Theme1 того же дня».')
p()

# ---------------------------------------------------------------- 3. контроль часа
p('=' * 100)
p('3. КОНТРОЛЬ ЧАСА: страта = день × блок часа')
p('=' * 100)
p('  Распределение шаблонов по блокам часа и дням:')
c = Counter((r['_day'], r['блок часа'], r['_t']) for r in main)
for k in sorted(c):
    p('    %s %s %s: %d' % (k[0], k[1], k[2], c[k]))
hb = report_block('3a. Страта = день × блок часа', main, lambda r: (r['_day'], r['блок часа']), 'день × блок часа')
p()
p('  Только блок 18-23 (оба дня):')
b18 = [r for r in main if r['блок часа'] == '18-23']
p('  ' + HDR)
for d in ('08-19', '08-20', 'оба'):
    for t in ('Theme1', 'Theme2'):
        ds = [r for r in b18 if r['_t'] == t and (d == 'оба' or r['_day'] == d)]
        if ds:
            p('  ' + line(d, t, agg(ds)))
p('  Но внутри блока 18-23 шаблоны стоят в РАЗНЫЕ часы: см. раздел 4. Блок часа партию не разделяет.')
p()

# ---------------------------------------------------------------- 4. контроль скрытой партии
p('=' * 100)
p('4. КОНТРОЛЬ СКРЫТОЙ ПАРТИИ')
p('=' * 100)
p('4a. Таблица шаблон × «сайтов» × час запуска × паттерн имени (число доменов):')
c = Counter((r['_day'], r['сайтов'], r['_hour'], r['паттерн имени'], r['_t']) for r in main)
keys = sorted(set((k[0], k[1], k[2], k[3]) for k in c))
p('    %-6s %-7s %-4s %-12s %7s %7s' % ('день', 'сайтов', 'час', 'паттерн', 'Theme1', 'Theme2'))
for k in keys:
    p('    %-6s %-7s %-4d %-12s %7d %7d' % (k[0], k[1], k[2], k[3], c.get(k + ('Theme1',), 0), c.get(k + ('Theme2',), 0)))
p()

p('4b. Партии = день × час × «сайтов»: выход, регистрации, диапазоны номеров аккаунтов.')
p('    (аккаунты Вебмастера и cf — по одному домену на аккаунт: %d и %d уникальных на %d доменов; но их НОМЕРА идут' %
  (len(set(r['аккаунт вебмастера'] for r in main)), len(set(r['cf-аккаунт'] for r in main)), len(main)))
p('     подряд внутри сеанса постановки, поэтому диапазон номеров — маркер партии)')


def rng(vals):
    ints = []
    for v in vals:
        try:
            ints.append(int(v))
        except ValueError:
            return ','.join(sorted(set(vals)))[:20]
    return '%d–%d' % (min(ints), max(ints))


batches = defaultdict(list)
for r in main:
    batches[(r['_day'], r['_hour'], r['сайтов'])].append(r)
p('    %-6s %-4s %-7s %-7s %3s %7s %7s %6s %4s %8s %10s %10s %s' %
  ('день', 'час', 'сайтов', 'шаблон', 'n', 'сайтов', 'вышли3', 'вых%', 'рег', 'поиск.кл', 'wm-акк', 'cf-акк', 'кто раз (аккаунт)'))
for k in sorted(batches):
    for t in ('Theme1', 'Theme2'):
        ds = [r for r in batches[k] if r['_t'] == t]
        if not ds:
            continue
        a = agg(ds)
        raz = dict(Counter(r['который раз аккаунт'] for r in ds))
        p('    %-6s %-4d %-7s %-7s %3d %7d %7d %6.1f %4d %8d %10s %10s %s' %
          (k[0], k[1], k[2], t, a['n'], a['S'], a['V3'], a['ex3'], a['R'], a['C'],
           rng([r['аккаунт вебмастера'] for r in ds]), rng([r['cf-аккаунт'] for r in ds]), raz))
p()

# крупные партии по (день, час)
p('4c. Партии = день × час (без «сайтов»): состав по шаблону.')
bh = defaultdict(list)
for r in main:
    bh[(r['_day'], r['_hour'])].append(r)
mixed_hour = []
for k in sorted(bh):
    n1 = sum(1 for r in bh[k] if r['_t'] == 'Theme1')
    n2 = sum(1 for r in bh[k] if r['_t'] == 'Theme2')
    a1 = agg([r for r in bh[k] if r['_t'] == 'Theme1'])
    a2 = agg([r for r in bh[k] if r['_t'] == 'Theme2'])
    kind = 'смешанная' if n1 and n2 else ('только Theme1' if n1 else 'только Theme2')
    if n1 and n2:
        mixed_hour.append(k)
    p('    %s час %2d: Theme1 %2d дом. (выход %5.1f%%, рег %2d) | Theme2 %2d дом. (выход %5.1f%%, рег %2d) — %s' %
      (k[0], k[1], n1, a1['ex3'], a1['R'], n2, a2['ex3'], a2['R'], kind))
n_t2_main = sum(1 for r in main if r['_t'] == 'Theme2')
n_t2_mixed = sum(1 for k in mixed_hour for r in bh[k] if r['_t'] == 'Theme2')
n_t1_mixed = sum(1 for k in mixed_hour for r in bh[k] if r['_t'] == 'Theme1')
p('  Итого: из %d Theme2 в смешанных партиях (день × час) сидят %d, в чисто-Theme2 партиях — %d.' %
  (n_t2_main, n_t2_mixed, n_t2_main - n_t2_mixed))
p('  Theme1 в смешанных партиях: %d из %d.' % (n_t1_mixed, len(main) - n_t2_main))
p()
p('4d. Чисто-однотипные партии на тех же днях — для масштаба разброса МЕЖДУ партиями одного шаблона:')
pure = []
for k in sorted(batches):
    n1 = sum(1 for r in batches[k] if r['_t'] == 'Theme1')
    n2 = sum(1 for r in batches[k] if r['_t'] == 'Theme2')
    if (n1 == 0) != (n2 == 0) and len(batches[k]) >= 3:
        a = agg(batches[k])
        pure.append((k, 'Theme1' if n1 else 'Theme2', a))
for k, t, a in pure:
    p('    %s час %2d сайтов %s — %s: %2d дом., выход %5.1f%%, рег %d' % (k[0], k[1], k[2], t, a['n'], a['ex3'], a['R']))
ex_t1 = [a['ex3'] for k, t, a in pure if t == 'Theme1']
ex_t2 = [a['ex3'] for k, t, a in pure if t == 'Theme2']
if ex_t1:
    p('  Разброс выхода между чисто-Theme1 партиями: от %.1f%% до %.1f%%' % (min(ex_t1), max(ex_t1)))
if ex_t2:
    p('  Чисто-Theme2 партии: от %.1f%% до %.1f%%' % (min(ex_t2), max(ex_t2)))
p()

# ---------------------------------------------------------------- 5. внутри партии
p('=' * 100)
p('5. РЕШАЮЩАЯ ПРОВЕРКА: шаблон внутри партии')
p('=' * 100)
p('Решающий тест задан заранее: страта = день × час × «сайтов», в расчёт идут только партии, где стоят не меньше')
p('3 доменов КАЖДОГО шаблона (иначе «ожидание по Theme1» строится на одном домене). Это две партии: 19.08 23:00 (198 сайтов)')
p('и 20.08 12:00 (199 сайтов). Варианты 5b/5c — проверка чувствительности, они добавляют партию 20.08 21:00, где Theme1 — один домен.')
p()
decisive = report_block('5a. РЕШАЮЩИЙ: страта = день × час × «сайтов», ≥3 доменов каждого шаблона', main,
                        lambda r: (r['_day'], r['_hour'], r['сайтов']), 'день × час × сайтов', min_each=3)
p()
inb_h = report_block('5b. Чувствительность: страта = день × час (любая пара, включая 1 против 25)', main,
                     lambda r: (r['_day'], r['_hour']), 'день × час')
p()
inb_hs = report_block('5c. Чувствительность: страта = день × час × «сайтов» (любая пара)', main,
                      lambda r: (r['_day'], r['_hour'], r['сайтов']), 'день × час × сайтов')
p()
p('5d. Смешанные партии по отдельности (день × час × сайтов):')
for k in sorted(batches):
    v = batches[k]
    n1 = [r for r in v if r['_t'] == 'Theme1']
    n2 = [r for r in v if r['_t'] == 'Theme2']
    if not n1 or not n2:
        continue
    a1, a2 = agg(n1), agg(n2)
    e_pool = (a1['V3'] + a2['V3']) / (a1['S'] + a2['S']) * a2['S']
    e_ref = a1['ex3'] / 100 * a2['S']
    er_ref = a1['r100'] / 100 * a2['S']
    p('    %s час %d сайтов %s: Theme1 %d дом. выход %.1f%% (рег %d, рег/10к %.1f) | Theme2 %d дом. выход %.1f%% (рег %d, рег/10к %.1f)'
      % (k[0], k[1], k[2], a1['n'], a1['ex3'], a1['R'], a1['r10k'], a2['n'], a2['ex3'], a2['R'], a2['r10k']))
    p('       выход: O/E(пул) = %s, O/E(Theme1) = %s; регистрации Theme2: O = %d, E(по Theme1) = %.2f' %
      (fmt(ratio(a2['V3'], e_pool)), fmt(ratio(a2['V3'], e_ref)), a2['R'], er_ref))
    # по доменам: медианы выхода
    m1 = sorted(100 * r['_v3'] / r['_sites'] for r in n1)
    m2 = sorted(100 * r['_v3'] / r['_sites'] for r in n2)
    p('       выход по доменам, Theme1: %s' % ' '.join('%.0f' % x for x in m1))
    p('       выход по доменам, Theme2: %s' % ' '.join('%.0f' % x for x in m2))
p()
p('5e. Регистрации внутри смешанных партий — кто дал:')
for k in sorted(batches):
    v = batches[k]
    if not (any(r['_t'] == 'Theme1' for r in v) and any(r['_t'] == 'Theme2' for r in v)):
        continue
    regs = [(r['домен'], r['_t'], int(r['_reg']), r['какие бренды конвертили']) for r in v if r['_reg'] > 0]
    p('    %s час %d сайтов %s: %s' % (k[0], k[1], k[2],
      '; '.join('%s [%s] %d (%s)' % x for x in regs) if regs else 'регистраций нет ни у кого'))
p()

# ---------------------------------------------------------------- 6. сверхдисперсия
p('=' * 100)
p('6. СВЕРХДИСПЕРСИЯ: χ²/df по выходу за 3 суток (биномиальное ожидание внутри пула)')
p('=' * 100)


def chi2_df(ds, pool_fn):
    pools = defaultdict(list)
    for r in ds:
        pools[pool_fn(r)].append(r)
    chi = 0.0
    df = 0
    for k, v in pools.items():
        if len(v) < 2:
            continue
        S = sum(r['_sites'] for r in v)
        V = sum(r['_v3'] for r in v)
        pr = V / S if S else 0
        if pr <= 0 or pr >= 1:
            continue
        for r in v:
            e = pr * r['_sites']
            var = r['_sites'] * pr * (1 - pr)
            chi += (r['_v3'] - e) ** 2 / var
        df += len(v) - 1
    return chi, df, len(pools)


chi_res = {}
for name, fn in [('пул = день', lambda r: r['_day']),
                 ('пул = день × шаблон', lambda r: (r['_day'], r['_t'])),
                 ('пул = день × блок часа', lambda r: (r['_day'], r['блок часа'])),
                 ('пул = день × час', lambda r: (r['_day'], r['_hour'])),
                 ('пул = день × час × шаблон', lambda r: (r['_day'], r['_hour'], r['_t'])),
                 ('пул = день × час × сайтов', lambda r: (r['_day'], r['_hour'], r['сайтов'])),
                 ('пул = день × час × сайтов × шаблон', lambda r: (r['_day'], r['_hour'], r['сайтов'], r['_t']))]:
    chi, df, npools = chi2_df(main, fn)
    chi_res[name] = chi / df if df else 0
    p('  %-38s пулов %2d, χ² = %8.1f, df = %3d, χ²/df = %6.1f' % (name, npools, chi, df, chi / df if df else 0))
p('  Ориентир: χ²/df ≈ 1 — домены внутри пула различаются только биномиальным шумом.')
p()

# ---------------------------------------------------------------- 7. робастность: все зоны
p('=' * 100)
p('7. РОБАСТНОСТЬ: все зоны 19–20.08, страта = день × зона × час')
p('=' * 100)
tail = [r for r in all_zones if r['зона'] != 'team']
p('  Домены вне team на 19–20.08: %d, из них Theme2: %d' % (len(tail), sum(1 for r in tail if r['_t'] == 'Theme2')))
for r in sorted(tail, key=lambda r: (r['_day'], r['зона'], r['_t'])):
    p('    %-14s %s %-6s %-7s сайтов %s час %2d вышли3 %3d выход %5.1f%% рег %d' %
      (r['домен'], r['_day'], r['зона'], r['_t'], r['сайтов'], r['_hour'], r['_v3'], 100 * r['_v3'] / r['_sites'], r['_reg']))
rz = report_block('7a. Все зоны, страта = день × зона × час', all_zones,
                  lambda r: (r['_day'], r['зона'], r['_hour']), 'день × зона × час')
p()
other_t2 = [r for r in rows if r['_t'] == 'Theme2' and r['день запуска'] not in DAYS]
p('  Theme2 не 19–20.08: %s' % ('; '.join('%s (%s, %s, сайтов %s, выход %.1f%%, рег %d)' %
                                            (r['домен'], r['день запуска'], r['зона'], r['сайтов'],
                                             100 * r['_v3'] / r['_sites'] if r['_sites'] else 0, r['_reg'])
                                            for r in other_t2) or 'нет'))
p()

# ---------------------------------------------------------------- ВЫВОД
p('=' * 100)
p('ВЫВОД')
p('=' * 100)
c3, c7, cr = crude
d3, d7, dr = decisive
h3, h7, hr = inb_h
s3, s7, sr = inb_hs
a1_19 = agg([r for r in main if r['_t'] == 'Theme1' and r['_day'] == '08-19'])
a2_19 = agg([r for r in main if r['_t'] == 'Theme2' and r['_day'] == '08-19'])
a1_20 = agg([r for r in main if r['_t'] == 'Theme1' and r['_day'] == '08-20'])
a2_20 = agg([r for r in main if r['_t'] == 'Theme2' and r['_day'] == '08-20'])
a1 = agg([r for r in main if r['_t'] == 'Theme1'])
a2 = agg([r for r in main if r['_t'] == 'Theme2'])
t2_evening = [r for r in main if r['_t'] == 'Theme2' and r['_day'] == '08-20' and r['_hour'] in (20, 21)]
t1_evening = [r for r in main if r['_t'] == 'Theme1' and r['_day'] == '08-20' and r['_hour'] in (20, 21)]
t1_22 = [r for r in main if r['_t'] == 'Theme1' and r['_day'] == '08-20' and r['_hour'] == 22]
ev2, ev1, e22 = agg(t2_evening), agg(t1_evening), agg(t1_22)
b184 = agg(batches[('08-19', 17, '184')])
b186 = agg(batches[('08-19', 17, '186')])
mixF1 = agg([r for r in batches[('08-20', 12, '199')] if r['_t'] == 'Theme1'])
mixF2 = agg([r for r in batches[('08-20', 12, '199')] if r['_t'] == 'Theme2'])
mixE1 = agg([r for r in batches[('08-19', 23, '198')] if r['_t'] == 'Theme1'])
mixE2 = agg([r for r in batches[('08-19', 23, '198')] if r['_t'] == 'Theme2'])
reg1908 = int(next((r['_reg'] for r in main if r['домен'] == '1908.team'), 0))
pois_d = poisson_le(dr['O'], dr['E'])

p('1. Без страты (только день) гипотеза выглядит верной. Theme2 в .team 19–20.08: %d доменов, %d сайтов, %d регистрации;'
  % (a2['n'], a2['S'], a2['R']))
p('   Theme1: %d доменов, %d сайтов, %d регистрации. Выход Theme2 против Theme1: 19.08 %.1f%% против %.1f%%, 20.08 %.1f%% против %.1f%%.'
  % (a1['n'], a1['S'], a1['R'], a2_19['ex3'], a1_19['ex3'], a2_20['ex3'], a1_20['ex3']))
p('   По двум дням выход Theme2 = %s от Theme1 (O = %d, E по Theme1 = %.0f; O/E по пулу дня %s; перестановка p = %s).'
  % (fmt(c3['oe_ref']), c3['O'], c3['Eref'], fmt(c3['oe']), fmt(c3['p_le'], 4)))
p('   Регистраций %d при ожидании %.1f по Theme1 (в %.0f раз меньше; по пулу дня E = %.1f, пуассон p = %s).'
  % (cr['O'], cr['Eref'], cr['Eref'] / max(cr['O'], 1), cr['E'], fmt(poisson_le(cr['O'], cr['E']), 4)))
p()
p('2. Но Theme2 — это не метка, случайно рассыпанная по доменам дня, а свои сеансы постановки (раздел 4):')
p('   %d из %d Theme2 в .team стоят в один вечер 20.08 в 20–21 час с номерами аккаунтов Вебмастера и cf подряд; Theme1 там %d домен.'
  % (len(t2_evening), a2['n'], len(t1_evening)))
p('   19 Theme1 того же вечера стоят в 22:00 отдельной партией, в основном на повторных аккаунтах. Эта вечерняя Theme2-партия — худшая')
p('   группа среза (выход %.1f%%), но и чисто-Theme1 партии на тех же днях разбросаны от %.1f%% до %.1f%% (184 сайта в 17:00 19.08 — %.1f%%,'
  % (ev2['ex3'], min(ex_t1), max(ex_t1), b184['ex3']))
p('   186 сайтов в тот же час — %.1f%%; Theme1 в 22:00 20.08 — %.1f%%). Плохая партия бывает у обоих шаблонов; для %d вечерних Theme2 пары по Theme1 нет.'
  % (b186['ex3'], e22['ex3'], len(t2_evening)))
p()
p('3. Шаблон отделим от партии только там, где оба стоят в одной партии. Таких партий две (%d Theme2 против %d Theme1):'
  % (d3['n_l'], d3['n_o']))
p('   19.08 23:00, 198 сайтов: Theme1 %d дом. %.1f%% против Theme2 %d дом. %.1f%%; 20.08 12:00, 199 сайтов: %d дом. %.1f%% против %d дом. %.1f%%.'
  % (mixE1['n'], mixE1['ex3'], mixE2['n'], mixE2['ex3'], mixF1['n'], mixF1['ex3'], mixF2['n'], mixF2['ex3']))
p('   Внутри партии выход Theme2: O = %d, E по Theme1 = %.0f → O/E = %s (по пулу партии %s), перестановка внутри партии p = %s.'
  % (d3['O'], d3['Eref'], fmt(d3['oe_ref']), fmt(d3['oe']), fmt(d3['p_le'], 4)))
p('   За 7 суток O/E = %s — Theme2 не догоняет. Чувствительность (с партией 21:00, где Theme1 один домен): O/E по Theme1 %s / %s, p = %s / %s.'
  % (fmt(d7['oe_ref']), fmt(h3['oe_ref']), fmt(s3['oe_ref']), fmt(h3['p_le'], 3), fmt(s3['p_le'], 3)))
p('   Регистрации внутри партии: %d у Theme2 при ожидании %.1f по Theme1 (O/E = %s), пуассон p = %s, перестановка p = %s.'
  % (dr['O'], dr['Eref'], fmt(dr['oe_ref']), fmt(pois_d, 4), fmt(dr['p_le'], 4)))
p('   Все ожидаемые регистрации — из одной партии 20.08 12:00: Theme1 дал %d (из них %d у одного домена 1908.team), Theme2 — %d;'
  % (mixF1['R'], reg1908, mixF2['R']))
p('   в партии 19.08 23:00 регистраций нет ни у кого. Разница по регистрациям на этих объёмах не отличима от случайности.')
p()
p('4. Сверхдисперсия пулов 19–20.08 (χ²/df по выходу): пул = день %.1f; + шаблон %.1f; пул = партия (день × час × сайтов) %.1f;'
  % (chi_res['пул = день'], chi_res['пул = день × шаблон'], chi_res['пул = день × час × сайтов']))
p('   партия + шаблон %.1f. Шаблон снимает малую часть разброса, партия — вдвое больше, шаблон поверх партии почти ничего не добавляет.'
  % chi_res['пул = день × час × сайтов × шаблон'])
p('   «Необъяснимый» разброс в этих днях — это партии постановки, и он остаётся большим (%.1f) даже внутри партии.'
  % chi_res['пул = день × час × сайтов × шаблон'])
p()
crit_exit = (d3['oe_ref'] is not None and d3['oe_ref'] <= 0.6 and (d3['p_le'] or 1) < 0.05)
crit_reg = (dr['oe_ref'] is not None and dr['oe_ref'] <= 0.4 and pois_d < 0.05)
p('5. Критерии плана внутри партии: выход O/E ≤ 0,6 при p < 0,05 — %s (O/E = %s, p = %s); регистрации O/E ≤ 0,4 при p < 0,05 — %s (O/E = %s, p = %s);'
  % ('да' if crit_exit else 'нет', fmt(d3['oe_ref']), fmt(d3['p_le'], 3), 'да' if crit_reg else 'нет', fmt(dr['oe_ref']), fmt(pois_d, 3)))
p('   «держится в блоке 18-23» — в блоке 18-23 разница есть (раздел 3), но там шаблоны стоят в разные часы, то есть блок часа — тоже партия;')
p('   «не совпадает с недоборной подгруппой» — нет: %d из %d Theme2 — это одна вечерняя партия 20.08 (202–204 сайта, 20–21 час) без пары.'
  % (len(t2_evening), a2['n']))
p()
p('ИТОГ ПО ГИПОТЕЗЕ: частично. Грубые цифры гипотезы верны (выход %s от Theme1, регистраций %d вместо %.0f), но большая часть разрыва —'
  % (fmt(c3['oe_ref']), cr['O'], cr['Eref']))
p('партия постановки, а не шаблон: %d из %d Theme2 — отдельная вечерняя партия 20.08, для которой Theme1-пары нет (шаблон ≡ партия, не разделимо).'
  % (len(t2_evening), a2['n']))
p('Там, где оба шаблона стоят в одной партии (%d против %d доменов), Theme2 выходит хуже на %.0f%% (O/E = %s, p = %s) — направление то же, но это'
  % (d3['n_l'], d3['n_o'], 100 * (1 - (d3['oe_ref'] or 1)), fmt(d3['oe_ref']), fmt(d3['p_le'], 3)))
p('не «вдвое», и по регистрациям (%d против %.1f ожидаемых, p = %s) разница не доказана. Заявленные «вдвое по выходу и в 4–8 раз по регистрациям»'
  % (dr['O'], dr['Eref'], fmt(pois_d, 3)))
p('внутри партии не подтверждаются; слабый остаточный эффект шаблона ≈0,75 возможен, но на 33 доменах и без записанного контента не доказуем.')
p()
p('ЧТО С ЭТИМ ДЕЛАТЬ:')
p('1) Не вводить запрет Theme2 по этим цифрам: главный вклад — одна вечерняя партия 20.08 (%d доменов, выход %.1f%%), а столь же слабые партии'
  % (len(t2_evening), ev2['ex3']))
p('   были и у Theme1 (19.08 17:00, 184 сайта — %.1f%%; 20.08 22:00 — %.1f%%). Запрет шаблона по партии — это запрет случайного маркера.'
  % (b184['ex3'], e22['ex3']))
p('2) Проверяемо на уже запущенных данных: дозаписать в свод для 106 доменов 19–20.08, какой набор контента реально стоял и почему «сайтов»')
p('   184/185/186/198/199/202–206 (какие бренды не встали). Если вечерняя Theme2-партия 20.08 и партия 184 сайта 17:00 19.08 — один набор,')
p('   разброс объяснится набором, и шаблон можно пересчитать этим же скриптом со стратой «набор контента + день».')
p('3) Если шаблон важен как рычаг — нужен запуск, где Theme1 и Theme2 стоят вперемешку в одной партии (один день, один час, один записанный')
p('   набор, по 20–30 доменов). Тогда разница ≈0,75 по выходу либо подтвердится, либо исчезнет. До этого Theme2 — не рычаг, а подозрение.')
p('4) 8 Theme2 вне .team (раздел 7): в партии 20.08 12:00 .lol 29,6%, .sbs 20,6%, .buzz 20,1% — не хуже соседних Theme1; объёмы единичные, выводов не строить.')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT, file=sys.stderr)

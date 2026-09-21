#!/usr/bin/env python3
"""
Гипотеза №1. Паттерн имени домена и длина метки.

Что проверяем.
  Паттерн имени домена (numeric / alpha_other / casino_prefix / casino_infix) и
  длина метки внутри пула «набор контента + день запуска» НЕ меняют ни выход
  сайтов в поиск, ни регистрации (O/E в 0,85–1,15). Сырой разрыв casino-имён
  (0,04 против 0,11 рег/100 сайтов) — тень дней и наборов контента.
  Две заранее заявленные альтернативы:
    (А1) casino_* хуже по выходу (скорость: догоняют к 7 суткам);
    (А2) casino_infix лучше по регистрациям при том же выходе.

Как проверяем (один фильтр для всех контрастов, пулы по регистрациям НЕ отбираем).
  Фильтр: окно закрыто = да; дней != 1; без выбросов 3615.team и 3286.team;
  без «КОНТЕНТ НЕ ЗАПИСАН».
  Пул = набор контента + день запуска; берём пулы, где есть >= 2 паттернов.
  Для каждого домена три ожидания:
    E_сайт  = ставка пула на сайт × сайтов домена в окне;
    E_вышли = ставка пула на вышедший сайт × вышли за 3 суток у домена;
    E_клик  = ставка пула на поисковый клик × кликов из поиска в окне у домена.
  Суммы O и E по четырём паттернам:
    (а) выход: O = вышли за 3 суток, E = E_сайт (по выходу);
    (б) регистрации в окне 3 суток: O = регистраций в окне, E = E_сайт / E_вышли / E_клик.
  Значимость: перестановка метки паттерна внутри пула 10 000 раз (random.seed(1)),
  статистика Σ(O−E)²/E по 4 группам на весь набор + два объявленных контраста
  (casino_* против остальных по выходу; casino_infix против остальных по
  регистрациям при E_сайт), p по той же перестановке.
  Разрез по зонам team / lol (страта = пул + зона).
  Длина метки: внутри alpha_other (3/4/5/6/7) и внутри casino-имён (8/9/10/11,
  страта пул + паттерн) той же перестановкой.
  Скорость: вышли за 7 суток / вышли за 3 суток по паттернам (только домены, у
  которых 7 суток уже полностью прошли) и «задержка до поиска, медиана».
  Повтор метки: метки, стоящие в двух зонах: O/E второго по дате экземпляра
  относительно пула (leave-one-out) и знаковый критерий по парам с разными днями.
  Замыкание: χ²/df сверхдисперсии выхода в пулах >= 5 доменов с ячейками
  пул × признак имени (numeric: ведущий ноль / нет; alpha_other: только буквы /
  смесь; casino_prefix; casino_infix) против 1000 случайных разбивок.

Только стандартная библиотека Python 3. Вывод пишется и в stdout, и в файл
analysis/export/gipotezy_svod/h01_domain_name_pattern.txt.
"""

import csv
import math
import os
import random
import re
import sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'h01_domain_name_pattern.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
N_SPLIT = 1000
PATTERNS = ['numeric', 'alpha_other', 'casino_prefix', 'casino_infix']
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
LAST_DATA_DAY = '2026-09-21'   # дата свода
DAY7_COMPLETE_LAST_DAY = '2026-09-14'  # последний день переобхода + 7 суток <= 21.09

_out_lines = []


def P(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _out_lines.append(s)


def fnum(x, d=2):
    return f'{x:.{d}f}'


def oe(o, e):
    return f'{o / e:.2f}' if e > 0 else '—'


def binom_two_sided(k, n):
    """Точный двусторонний биномиальный тест при p = 0,5."""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    p = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)


# ---------------------------------------------------------------------------
# 1. Загрузка и фильтр
# ---------------------------------------------------------------------------

def toi(s):
    return int(float(s)) if s not in ('', None) else 0


def load():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = list(csv.DictReader(fh))
    return rows


def label_of(domain):
    return domain.rsplit('.', 1)[0]


def prepare(r):
    d = {}
    d['домен'] = r['домен']
    d['метка'] = label_of(r['домен'])
    d['зона'] = r['зона']
    d['день'] = r['день запуска']
    d['последний день'] = r['последний день']
    d['набор'] = r['набор контента']
    d['паттерн'] = r['паттерн имени']
    d['длина'] = int(r['длина метки'])
    d['сайтов'] = toi(r['сайтов в окне'])
    d['вышли3'] = toi(r['вышли за 3 суток'])
    d['вышли7'] = toi(r['вышли за 7 суток'])
    d['рег'] = toi(r['регистраций в окне 3 суток'])
    d['фд'] = toi(r['ФД в окне 3 суток'])
    d['клик'] = toi(r['кликов из поиска в окне'])
    z = r['задержка до поиска, медиана']
    d['задержка'] = float(z) if z != '' else None
    d['пул'] = (d['набор'], d['день'])
    # признак имени для замыкания
    lab = d['метка']
    if d['паттерн'] == 'numeric':
        d['ячейка имени'] = 'numeric: ведущий 0' if lab.startswith('0') else 'numeric: без 0'
    elif d['паттерн'] == 'alpha_other':
        d['ячейка имени'] = 'alpha_other: только буквы' if lab.isalpha() else 'alpha_other: смесь'
    else:
        d['ячейка имени'] = d['паттерн']
    return d


def apply_filter(rows):
    P('=' * 100)
    P('ГИПОТЕЗА №1: паттерн имени домена (numeric / alpha_other / casino_prefix / casino_infix) и длина метки')
    P('Файл:', CSV_PATH)
    P('=' * 100)
    P()
    P('--- Фильтр (один и тот же для всех контрастов) ---')
    n0 = len(rows)
    P(f'Всего доменов в своде: {n0}')
    excl = Counter()
    kept = []
    for r in rows:
        if r['домен'] in OUTLIERS:
            excl['выбросы 3615.team / 3286.team (миллионы «прочих» кликов)'] += 1
            continue
        if r['окно закрыто'] != 'да':
            excl['окно 3 суток ещё не закрыто'] += 1
            continue
        if r['дней'] == '1':
            excl['дней = 1 (только 150 сайтов, день 2 не наступил)'] += 1
            continue
        if r['набор контента'] == NO_CONTENT:
            excl['«КОНТЕНТ НЕ ЗАПИСАН» (не набор, сцеплен с датой)'] += 1
            continue
        kept.append(prepare(r))
    for k, v in excl.items():
        P(f'  исключено: {v:4d}  — {k}')
    n_cas_nc = sum(1 for r in rows if r['набор контента'] == NO_CONTENT and r['паттерн имени'].startswith('casino'))
    P(f'  (среди «КОНТЕНТ НЕ ЗАПИСАН» casino-имён: {n_cas_nc} — не считаем)')
    P(f'Осталось доменов: {len(kept)}')
    return kept


# ---------------------------------------------------------------------------
# 2. Пулы и ожидания
# ---------------------------------------------------------------------------

def build_pools(items, key=lambda d: d['пул']):
    pools = defaultdict(list)
    for d in items:
        pools[key(d)].append(d)
    return pools


def add_expectations(pools, prefix=''):
    """Дописывает каждому домену E_сайт (выход), E_сайт/E_вышли/E_клик (рег) и E_сайт для вышли7."""
    for k, ds in pools.items():
        S = sum(d['сайтов'] for d in ds)
        V3 = sum(d['вышли3'] for d in ds)
        V7 = sum(d['вышли7'] for d in ds)
        R = sum(d['рег'] for d in ds)
        C = sum(d['клик'] for d in ds)
        for d in ds:
            d[prefix + 'E_выход'] = V3 / S * d['сайтов'] if S else 0.0
            d[prefix + 'E_выход7'] = V7 / S * d['сайтов'] if S else 0.0
            d[prefix + 'E_рег_сайт'] = R / S * d['сайтов'] if S else 0.0
            d[prefix + 'E_рег_вышли'] = R / V3 * d['вышли3'] if V3 else 0.0
            d[prefix + 'E_рег_клик'] = R / C * d['клик'] if C else 0.0


# ---------------------------------------------------------------------------
# 3. Перестановочный движок
# ---------------------------------------------------------------------------

FIELDS = ['сайтов', 'вышли3', 'E_выход', 'рег', 'E_рег_сайт', 'E_рег_вышли', 'E_рег_клик', 'вышли7', 'E_выход7', 'клик']


def perm_engine(items, group_key, pool_key, n_perm, seed=1, fields=FIELDS):
    """Перестановка меток групп внутри пулов.
    Возвращает: список групп, наблюдённые суммы {группа: {поле: сумма}},
    список перестановочных сумм такой же формы."""
    groups = sorted(set(group_key(d) for d in items))
    labels = [group_key(d) for d in items]
    cols = {f: [float(d[f]) for d in items] for f in fields}
    pools = defaultdict(list)
    for i, d in enumerate(items):
        pools[pool_key(d)].append(i)
    pool_idx = [v for v in pools.values() if len(v) >= 2]

    def sums(lab):
        gi = {g: [] for g in groups}
        for i, g in enumerate(lab):
            gi[g].append(i)
        out = {}
        for g in groups:
            idx = gi[g]
            out[g] = {f: sum(map(cols[f].__getitem__, idx)) for f in fields}
        return out

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
    return groups, obs, perms


def chi_stat(s, groups, o_f, e_f):
    t = 0.0
    for g in groups:
        e = s[g][e_f]
        if e > 0:
            t += (s[g][o_f] - e) ** 2 / e
    return t


def pval_ge(obs, perm_vals):
    k = sum(1 for v in perm_vals if v >= obs)
    return (k + 1) / (len(perm_vals) + 1)


def pval_abs(obs, perm_vals):
    a = abs(obs)
    k = sum(1 for v in perm_vals if abs(v) >= a)
    return (k + 1) / (len(perm_vals) + 1)


def perm_interval(ratios):
    r = sorted(ratios)
    n = len(r)
    lo = r[int(0.025 * n)]
    hi = r[min(n - 1, int(0.975 * n))]
    return lo, hi


def report_groups(title, groups, obs, perms, o_f, e_f, unit, group_name='паттерн', extra_cols=None):
    """Таблица O/E по группам + Σ(O−E)²/E с p по перестановке."""
    P()
    P(f'--- {title} ---')
    hdr = f'{group_name:<26} {"доменов":>8} {"сайтов":>8} {"O":>8} {"E":>9} {"O/E":>6} {"O−E":>8}  {"O/E при нуле (2,5–97,5%)":>24}'
    P(hdr)
    n_dom = {g: 0 for g in groups}
    for g in groups:
        n_dom[g] = obs[g]['_n']
    for g in groups:
        o = obs[g][o_f]
        e = obs[g][e_f]
        ratios = [p[g][o_f] / p[g][e_f] for p in perms if p[g][e_f] > 0]
        lo, hi = perm_interval(ratios) if ratios else (float('nan'), float('nan'))
        P(f'{g:<26} {n_dom[g]:>8} {int(obs[g]["сайтов"]):>8} {int(o):>8} {e:>9.1f} {oe(o, e):>6} {o - e:>+8.1f}  {lo:>10.2f} – {hi:<10.2f}')
    chi_o = chi_stat(obs, groups, o_f, e_f)
    chi_p = [chi_stat(p, groups, o_f, e_f) for p in perms]
    pv = pval_ge(chi_o, chi_p)
    P(f'Σ(O−E)²/E по {len(groups)} группам = {chi_o:.2f};  перестановочное p = {pv:.3f}  (N = {len(perms)}; {unit})')
    return pv


def add_counts(items, group_key, groups, obs, perms):
    cnt = Counter(group_key(d) for d in items)
    for g in groups:
        obs[g]['_n'] = cnt[g]
    return obs


def contrast(groups_in, groups, obs, perms, o_f, e_f, name):
    """Объявленный контраст: сумма по groups_in против остальных; p двусторонний по |O−E|."""
    def d_of(s):
        o = sum(s[g][o_f] for g in groups_in)
        e = sum(s[g][e_f] for g in groups_in)
        return o, e
    o, e = d_of(obs)
    o_rest = sum(obs[g][o_f] for g in groups) - o
    e_rest = sum(obs[g][e_f] for g in groups) - e
    diffs = [(lambda oe_: oe_[0] - oe_[1])(d_of(p)) for p in perms]
    pv2 = pval_abs(o - e, diffs)
    lo_dir = sum(1 for v in diffs if v <= (o - e))
    hi_dir = sum(1 for v in diffs if v >= (o - e))
    p_one = (min(lo_dir, hi_dir) + 1) / (len(diffs) + 1)
    ratios = [d_of(p)[0] / d_of(p)[1] for p in perms if d_of(p)[1] > 0]
    lo, hi = perm_interval(ratios) if ratios else (float('nan'), float('nan'))
    P(f'  контраст «{name}»: O = {int(o)}, E = {e:.1f}, O/E = {oe(o, e)}, O−E = {o - e:+.1f}; '
      f'остальные: O = {int(o_rest)}, E = {e_rest:.1f}, O/E = {oe(o_rest, e_rest)};  '
      f'p (двуст.) = {pv2:.3f}, p (односторон.) = {p_one:.3f}; O/E при нуле {lo:.2f}–{hi:.2f}')
    return (o / e if e > 0 else float('nan')), pv2


# ---------------------------------------------------------------------------
# 4. Основной блок: 4 паттерна в пулах с >= 2 паттернами
# ---------------------------------------------------------------------------

def raw_table(items, title):
    P()
    P(f'--- {title} ---')
    P(f'{"паттерн":<16} {"доменов":>8} {"сайтов":>8} {"вышли3":>7} {"выход %":>8} {"рег":>5} {"рег/100 сайтов":>15} {"кликов из поиска":>17} {"рег/10тыс кликов":>17} {"ФД":>4}')
    for g in PATTERNS:
        ds = [d for d in items if d['паттерн'] == g]
        if not ds:
            continue
        S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds); R = sum(d['рег'] for d in ds)
        C = sum(d['клик'] for d in ds); F = sum(d['фд'] for d in ds)
        P(f'{g:<16} {len(ds):>8} {S:>8} {V:>7} {100 * V / S:>8.1f} {R:>5} {100 * R / S:>15.3f} {C:>17} {(1e4 * R / C if C else 0):>17.2f} {F:>4}')


def main_block(kept):
    pools_all = build_pools(kept)
    multi = {k: v for k, v in pools_all.items() if len(set(d['паттерн'] for d in v)) >= 2}
    items = [d for v in multi.values() for d in v]
    add_expectations(build_pools(items))
    P()
    P('=' * 100)
    P('БЛОК 1. Паттерн имени: 4 группы внутри пулов «набор контента + день запуска» с >= 2 паттернами')
    P('=' * 100)
    P(f'Пулов всего после фильтра: {len(pools_all)}; пулов с >= 2 паттернами: {len(multi)}; '
      f'доменов в них: {len(items)}; сайтов: {sum(d["сайтов"] for d in items)}; '
      f'регистраций в окне: {sum(d["рег"] for d in items)}; ФД в окне: {sum(d["фд"] for d in items)}')
    comp = Counter(tuple(sorted(set(d['паттерн'] for d in v))) for v in multi.values())
    P('Состав пулов по паттернам:')
    for k, v in comp.most_common():
        P(f'  {v:3d} пулов: {" + ".join(k)}')
    P('Размер пулов (доменов): ' + ', '.join(f'{k}:{v}' for k, v in sorted(Counter(len(v) for v in multi.values()).items())))
    raw_table(kept, 'СЫРЫЕ суммы по паттернам, весь отфильтрованный набор (без страты — для справки)')
    raw_table(items, 'СЫРЫЕ суммы по паттернам, только домены в смешанных пулах (без страты)')

    groups, obs, perms = perm_engine(items, lambda d: d['паттерн'], lambda d: d['пул'], N_PERM, seed=1)
    add_counts(items, lambda d: d['паттерн'], groups, obs, perms)
    res = {}
    res['p_exit'] = report_groups('(а) ВЫХОД: O = вышли за 3 суток, E = ставка пула на сайт × сайтов',
                                  groups, obs, perms, 'вышли3', 'E_выход', 'сайтов, вышедших в поиск')
    res['casino_exit'] = contrast(['casino_prefix', 'casino_infix'], groups, obs, perms, 'вышли3', 'E_выход',
                                  'А1: casino_* против остальных по выходу')
    res['p_reg_site'] = report_groups('(б) РЕГИСТРАЦИИ в окне 3 суток: E_сайт = ставка пула на сайт × сайтов',
                                      groups, obs, perms, 'рег', 'E_рег_сайт', 'регистраций')
    res['infix_reg'] = contrast(['casino_infix'], groups, obs, perms, 'рег', 'E_рег_сайт',
                                'А2: casino_infix против остальных по регистрациям при E_сайт')
    res['casino_reg'] = contrast(['casino_prefix', 'casino_infix'], groups, obs, perms, 'рег', 'E_рег_сайт',
                                 'справочно: casino_* против остальных по регистрациям при E_сайт')
    res['p_reg_exit'] = report_groups('(б) РЕГИСТРАЦИИ: E_вышли = ставка пула на вышедший сайт × вышли за 3 суток',
                                      groups, obs, perms, 'рег', 'E_рег_вышли', 'регистраций')
    res['infix_reg_vy'] = contrast(['casino_infix'], groups, obs, perms, 'рег', 'E_рег_вышли', 'casino_infix при E_вышли')
    res['p_reg_click'] = report_groups('(б) РЕГИСТРАЦИИ: E_клик = ставка пула на поисковый клик × кликов из поиска в окне',
                                       groups, obs, perms, 'рег', 'E_рег_клик', 'регистраций')
    res['infix_reg_cl'] = contrast(['casino_infix'], groups, obs, perms, 'рег', 'E_рег_клик', 'casino_infix при E_клик')
    # устойчивость: на скольких доменах держатся регистрации каждой группы; O/E без 1–2 самых «богатых» доменов
    P()
    P('Устойчивость регистраций по паттернам (E_сайт): сколько доменов дали регистрации, доля двух самых «богатых» доменов,')
    P('O/E после удаления самого богатого домена (и его E) и после удаления двух:')
    res['infix_loo'] = None
    for g in groups:
        ds = sorted([d for d in items if d['паттерн'] == g], key=lambda d: -d['рег'])
        O = sum(d['рег'] for d in ds); E = sum(d['E_рег_сайт'] for d in ds)
        n_with = sum(1 for d in ds if d['рег'] > 0)
        top2 = ds[:2]
        o1, e1 = O - top2[0]['рег'], E - top2[0]['E_рег_сайт']
        o2, e2 = o1 - top2[1]['рег'], e1 - top2[1]['E_рег_сайт']
        P(f'  {g:<16} доменов с рег: {n_with:>3} из {len(ds):>3}; топ-2 домена: {top2[0]["домен"]} ({top2[0]["рег"]}), {top2[1]["домен"]} ({top2[1]["рег"]}) '
          f'= {top2[0]["рег"] + top2[1]["рег"]} из {int(O)} рег; O/E {oe(O, E)} → без топ-1 {oe(o1, e1)} ({int(o1)}/{e1:.1f}) → без топ-2 {oe(o2, e2)} ({int(o2)}/{e2:.1f})')
        if g == 'casino_infix':
            res['infix_loo'] = (o1 / e1 if e1 else float('nan'), o2 / e2 if e2 else float('nan'), top2[0]['домен'], top2[1]['домен'], top2[0]['рег'] + top2[1]['рег'], int(O))
    # клики на сайт как побочная метрика
    P()
    P('Справочно: поисковые клики в окне по паттернам (O = кликов из поиска в окне, E = ставка пула на сайт × сайтов):')
    for k, ds in build_pools(items).items():
        S = sum(d['сайтов'] for d in ds); C = sum(d['клик'] for d in ds)
        for d in ds:
            d['E_клик_сайт'] = C / S * d['сайтов'] if S else 0
    for g in groups:
        o = sum(d['клик'] for d in items if d['паттерн'] == g)
        e = sum(d['E_клик_сайт'] for d in items if d['паттерн'] == g)
        P(f'  {g:<16} O = {o:>7}  E = {e:>9.0f}  O/E = {oe(o, e)}')
    res['obs'] = obs
    res['items'] = items
    res['multi'] = multi
    return res


# ---------------------------------------------------------------------------
# 5. Разрез по зонам team / lol
# ---------------------------------------------------------------------------

def zone_block(kept):
    P()
    P('=' * 100)
    P('БЛОК 2. Разрез по зонам team и lol (страта = пул + зона)')
    P('=' * 100)
    out = {}
    for z in ['team', 'lol']:
        zk = [d for d in kept if d['зона'] == z]
        pools = build_pools(zk)
        multi = {k: v for k, v in pools.items() if len(set(d['паттерн'] for d in v)) >= 2}
        items = [d for v in multi.values() for d in v]
        for d in items:
            d['пул_зона'] = (d['пул'], z)
        add_expectations(build_pools(items, key=lambda d: d['пул_зона']))
        P()
        P(f'### Зона {z}: страт (пул+зона) с >= 2 паттернами: {len(multi)}; доменов: {len(items)}; '
          f'сайтов: {sum(d["сайтов"] for d in items)}; регистраций: {sum(d["рег"] for d in items)}')
        groups, obs, perms = perm_engine(items, lambda d: d['паттерн'], lambda d: d['пул_зона'], N_PERM, seed=1)
        add_counts(items, lambda d: d['паттерн'], groups, obs, perms)
        p_e = report_groups(f'[{z}] ВЫХОД (E_сайт)', groups, obs, perms, 'вышли3', 'E_выход', 'вышедших сайтов')
        c1 = contrast([g for g in groups if g.startswith('casino')], groups, obs, perms, 'вышли3', 'E_выход',
                      f'[{z}] А1: casino_* по выходу')
        p_r = report_groups(f'[{z}] РЕГИСТРАЦИИ (E_сайт)', groups, obs, perms, 'рег', 'E_рег_сайт', 'регистраций')
        c2 = contrast(['casino_infix'], groups, obs, perms, 'рег', 'E_рег_сайт', f'[{z}] А2: casino_infix по регистрациям') \
            if 'casino_infix' in groups else (float('nan'), 1.0)
        # строгая страта: >= 3 casino и >= 3 не-casino
        strict = {k: v for k, v in pools.items()
                  if sum(1 for d in v if d['паттерн'].startswith('casino')) >= 3
                  and sum(1 for d in v if not d['паттерн'].startswith('casino')) >= 3}
        sitems = [d for v in strict.values() for d in v]
        for d in sitems:
            d['пул_зона_с'] = (d['пул'], z, 's')
        add_expectations(build_pools(sitems, key=lambda d: d['пул_зона_с']), prefix='s_')
        ocas = sum(d['вышли3'] for d in sitems if d['паттерн'].startswith('casino'))
        ecas = sum(d['s_E_выход'] for d in sitems if d['паттерн'].startswith('casino'))
        orc = sum(d['рег'] for d in sitems if d['паттерн'].startswith('casino'))
        erc = sum(d['s_E_рег_сайт'] for d in sitems if d['паттерн'].startswith('casino'))
        ori = sum(d['рег'] for d in sitems if d['паттерн'] == 'casino_infix')
        eri = sum(d['s_E_рег_сайт'] for d in sitems if d['паттерн'] == 'casino_infix')
        P(f'  строгая страта (>= 3 casino и >= 3 не-casino в пуле): страт {len(strict)}, доменов {len(sitems)}, '
          f'casino-доменов {sum(1 for d in sitems if d["паттерн"].startswith("casino"))}, регистраций {sum(d["рег"] for d in sitems)}: '
          f'casino_* выход O/E = {oe(ocas, ecas)} ({int(ocas)}/{ecas:.0f}); casino_* рег O/E = {oe(orc, erc)} ({int(orc)}/{erc:.1f}); '
          f'casino_infix рег O/E = {oe(ori, eri)} ({int(ori)}/{eri:.1f})')
        out[z] = dict(p_exit=p_e, casino_exit=c1, p_reg=p_r, infix_reg=c2)
    return out


# ---------------------------------------------------------------------------
# 6. Длина метки внутри паттерна
# ---------------------------------------------------------------------------

def length_block(kept):
    P()
    P('=' * 100)
    P('БЛОК 3. Длина метки внутри паттерна (перестановка длины внутри пула)')
    P('=' * 100)
    out = {}
    # alpha_other
    al = [d for d in kept if d['паттерн'] == 'alpha_other']
    pools = build_pools(al)
    multi = {k: v for k, v in pools.items() if len(set(d['длина'] for d in v)) >= 2}
    items = [d for v in multi.values() for d in v]
    for d in items:
        d['пул_a'] = ('alpha', d['пул'])
    add_expectations(build_pools(items, key=lambda d: d['пул_a']), prefix='a_')
    P()
    P(f'### alpha_other: всего доменов {len(al)} (длины: ' +
      ', '.join(f'{k}:{v}' for k, v in sorted(Counter(d['длина'] for d in al).items())) +
      f'); пулов с >= 2 длинами: {len(multi)}; доменов в них: {len(items)}; регистраций: {sum(d["рег"] for d in items)}')
    fields = ['сайтов', 'вышли3', 'a_E_выход', 'рег', 'a_E_рег_сайт']
    groups, obs, perms = perm_engine(items, lambda d: f'длина {d["длина"]}', lambda d: d['пул_a'], N_PERM, seed=1, fields=fields)
    add_counts(items, lambda d: f'длина {d["длина"]}', groups, obs, perms)
    out['alpha_exit'] = report_groups('alpha_other: ВЫХОД по длине метки', groups, obs, perms, 'вышли3', 'a_E_выход', 'вышедших сайтов', 'длина')
    out['alpha_reg'] = report_groups('alpha_other: РЕГИСТРАЦИИ по длине метки (E_сайт)', groups, obs, perms, 'рег', 'a_E_рег_сайт', 'регистраций', 'длина')
    out['alpha_obs'] = obs
    # casino
    ca = [d for d in kept if d['паттерн'].startswith('casino')]
    pools = build_pools(ca, key=lambda d: (d['пул'], d['паттерн']))
    multi = {k: v for k, v in pools.items() if len(set(d['длина'] for d in v)) >= 2}
    items = [d for v in multi.values() for d in v]
    for d in items:
        d['пул_c'] = ('casino', d['пул'], d['паттерн'])
    add_expectations(build_pools(items, key=lambda d: d['пул_c']), prefix='c_')
    P()
    P(f'### casino-имена: всего доменов {len(ca)} (' +
      ', '.join(f'{k[0]} {k[1]}:{v}' for k, v in sorted(Counter((d['паттерн'], d['длина']) for d in ca).items())) +
      f'); страт (пул + паттерн) с >= 2 длинами: {len(multi)}; доменов в них: {len(items)}; регистраций: {sum(d["рег"] for d in items)}')
    fields = ['сайтов', 'вышли3', 'c_E_выход', 'рег', 'c_E_рег_сайт']
    groups, obs, perms = perm_engine(items, lambda d: f'длина {d["длина"]:>2}', lambda d: d['пул_c'], N_PERM, seed=1, fields=fields)
    add_counts(items, lambda d: f'длина {d["длина"]:>2}', groups, obs, perms)
    out['casino_exit'] = report_groups('casino-имена: ВЫХОД по длине метки (страта пул + паттерн)', groups, obs, perms, 'вышли3', 'c_E_выход', 'вышедших сайтов', 'длина')
    out['casino_reg'] = report_groups('casino-имена: РЕГИСТРАЦИИ по длине метки (E_сайт)', groups, obs, perms, 'рег', 'c_E_рег_сайт', 'регистраций', 'длина')
    out['casino_obs'] = obs
    # дополнительные признаки имени внутри паттерна: numeric — ведущий ноль; alpha_other — только буквы / смесь
    for pat, title in [('numeric', 'numeric: ведущий ноль против остальных'), ('alpha_other', 'alpha_other: только буквы против смеси букв и цифр')]:
        sub = [d for d in kept if d['паттерн'] == pat]
        pools = build_pools(sub)
        multi = {k: v for k, v in pools.items() if len(set(d['ячейка имени'] for d in v)) >= 2}
        items = [d for v in multi.values() for d in v]
        for d in items:
            d['пул_x'] = ('x', pat, d['пул'])
        add_expectations(build_pools(items, key=lambda d: d['пул_x']), prefix='x_')
        P()
        P(f'### {title}: пулов с обоими вариантами: {len(multi)}; доменов: {len(items)}; регистраций: {sum(d["рег"] for d in items)}')
        fields = ['сайтов', 'вышли3', 'x_E_выход', 'рег', 'x_E_рег_сайт']
        groups, obs, perms = perm_engine(items, lambda d: d['ячейка имени'], lambda d: d['пул_x'], N_PERM, seed=1, fields=fields)
        add_counts(items, lambda d: d['ячейка имени'], groups, obs, perms)
        out[pat + '_x_exit'] = report_groups(f'{pat}: ВЫХОД по признаку имени', groups, obs, perms, 'вышли3', 'x_E_выход', 'вышедших сайтов', 'признак')
        out[pat + '_x_reg'] = report_groups(f'{pat}: РЕГИСТРАЦИИ по признаку имени (E_сайт)', groups, obs, perms, 'рег', 'x_E_рег_сайт', 'регистраций', 'признак')
        for g in groups:
            r = obs[g]['вышли3'] / obs[g]['x_E_выход'] if obs[g]['x_E_выход'] else float('nan')
            if g == 'numeric: ведущий 0': out['num0'] = r
            if g == 'alpha_other: только буквы': out['alpha_letters'] = r
            if g == 'alpha_other: смесь': out['alpha_mixed'] = r
    return out


# ---------------------------------------------------------------------------
# 7. Скорость: 7 суток против 3 суток и задержка до поиска
# ---------------------------------------------------------------------------

def speed_block(kept):
    P()
    P('=' * 100)
    P('БЛОК 4. Скорость выхода: вышли за 7 суток против 3 суток; задержка до поиска')
    P('=' * 100)
    sub = [d for d in kept if d['последний день'] <= DAY7_COMPLETE_LAST_DAY]
    pools = build_pools(sub)
    multi = {k: v for k, v in pools.items() if len(set(d['паттерн'] for d in v)) >= 2}
    items = [d for v in multi.values() for d in v]
    for d in items:
        d['пул_7'] = ('d7', d['пул'])
    add_expectations(build_pools(items, key=lambda d: d['пул_7']), prefix='d7_')
    P(f'Домены, у которых 7 суток от последнего дня переобхода уже прошли (последний день <= {DAY7_COMPLETE_LAST_DAY}): {len(sub)}; '
      f'из них в смешанных пулах: {len(items)} (пулов {len(multi)})')
    P()
    P(f'{"паттерн":<16} {"доменов":>8} {"сайтов":>8} {"вышли3":>7} {"вышли7":>7} {"выход3 %":>9} {"выход7 %":>9} {"7/3":>6} {"O/E вых3":>9} {"O/E вых7":>9}')
    r73 = {}
    for g in PATTERNS:
        ds = [d for d in items if d['паттерн'] == g]
        if not ds:
            continue
        S = sum(d['сайтов'] for d in ds); V3 = sum(d['вышли3'] for d in ds); V7 = sum(d['вышли7'] for d in ds)
        E3 = sum(d['d7_E_выход'] for d in ds); E7 = sum(d['d7_E_выход7'] for d in ds)
        r73[g] = (V7 / V3 if V3 else float('nan'), V3 / E3 if E3 else float('nan'), V7 / E7 if E7 else float('nan'))
        P(f'{g:<16} {len(ds):>8} {S:>8} {V3:>7} {V7:>7} {100 * V3 / S:>9.1f} {100 * V7 / S:>9.1f} {V7 / V3 if V3 else 0:>6.3f} {oe(V3, E3):>9} {oe(V7, E7):>9}')
    fields = ['сайтов', 'вышли3', 'd7_E_выход', 'вышли7', 'd7_E_выход7']
    groups, obs, perms = perm_engine(items, lambda d: d['паттерн'], lambda d: d['пул_7'], N_PERM, seed=1, fields=fields)
    add_counts(items, lambda d: d['паттерн'], groups, obs, perms)
    p7 = report_groups('ВЫХОД за 7 суток по паттернам (E = ставка пула на сайт за 7 суток × сайтов)', groups, obs, perms, 'вышли7', 'd7_E_выход7', 'вышедших за 7 суток')
    c7 = contrast([g for g in groups if g.startswith('casino')], groups, obs, perms, 'вышли7', 'd7_E_выход7', 'casino_* по выходу за 7 суток')
    c3 = contrast([g for g in groups if g.startswith('casino')], groups, obs, perms, 'вышли3', 'd7_E_выход', 'casino_* по выходу за 3 суток (тот же поднабор)')
    # задержка до поиска
    P()
    P('«Задержка до поиска, медиана» (суток) по паттернам, домены в смешанных пулах основного блока:')
    P(f'{"паттерн":<16} {"доменов с данными":>17} {"медиана медиан":>15} {"среднее":>8} {"доля 0 сут":>11} {"доля <=1 сут":>13} {"доля >=2 сут":>13}')
    base_items = [d for v in {k: v for k, v in build_pools(kept).items() if len(set(d['паттерн'] for d in v)) >= 2}.values() for d in v]
    for g in PATTERNS:
        zs = [d['задержка'] for d in base_items if d['паттерн'] == g and d['задержка'] is not None]
        if not zs:
            continue
        zs_s = sorted(zs)
        med = zs_s[len(zs_s) // 2]
        P(f'{g:<16} {len(zs):>17} {med:>15.1f} {sum(zs) / len(zs):>8.2f} {sum(1 for z in zs if z == 0) / len(zs):>11.2f} {sum(1 for z in zs if z <= 1) / len(zs):>13.2f} {sum(1 for z in zs if z >= 2) / len(zs):>13.2f}')
    # парно внутри пула: средняя задержка casino против не-casino
    win = lose = tie = 0
    for k, ds in build_pools(base_items).items():
        a = [d['задержка'] for d in ds if d['паттерн'].startswith('casino') and d['задержка'] is not None]
        b = [d['задержка'] for d in ds if not d['паттерн'].startswith('casino') and d['задержка'] is not None]
        if not a or not b:
            continue
        ma, mb = sum(a) / len(a), sum(b) / len(b)
        if ma > mb + 1e-9:
            win += 1
        elif mb > ma + 1e-9:
            lose += 1
        else:
            tie += 1
    p_delay = binom_two_sided(win, win + lose)
    P(f'Внутри пула: средняя задержка casino-имён БОЛЬШЕ, чем у остальных, в {win} пулах, МЕНЬШЕ в {lose}, равна в {tie}; '
      f'знаковый p = {p_delay:.3f}')
    return dict(r73=r73, p7=p7, c7=c7, c3=c3, n=len(items), p_delay=p_delay, win=win, lose=lose)


# ---------------------------------------------------------------------------
# 8. Повтор метки в двух зонах
# ---------------------------------------------------------------------------

def repeat_block(kept, all_rows):
    P()
    P('=' * 100)
    P('БЛОК 5. Повтор метки: одна и та же метка в двух зонах')
    P('=' * 100)
    lab_all = defaultdict(list)
    for r in all_rows:
        lab_all[label_of(r['домен'])].append(r)
    n_all = sum(1 for v in lab_all.values() if len(v) >= 2)
    P(f'В своде меток, стоящих в >= 2 доменах: {n_all} (' +
      ', '.join(f'{"+".join(k)}:{v}' for k, v in Counter(tuple(sorted(r["зона"] for r in v)) for v in lab_all.values() if len(v) >= 2).most_common()) + ')')
    # LOO-ожидание по всем пулам отфильтрованного набора (размер пула >= 2)
    pools = build_pools(kept)
    for k, ds in pools.items():
        S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds); R = sum(d['рег'] for d in ds)
        for d in ds:
            s2, v2, r2 = S - d['сайтов'], V - d['вышли3'], R - d['рег']
            d['loo_E_выход'] = v2 / s2 * d['сайтов'] if len(ds) >= 2 and s2 > 0 else None
            d['loo_E_рег'] = r2 / s2 * d['сайтов'] if len(ds) >= 2 and s2 > 0 else None
    lab = defaultdict(list)
    for d in kept:
        lab[d['метка']].append(d)
    pairs = [v for v in lab.values() if len(v) == 2]
    P(f'Пар, где оба домена прошли фильтр: {len(pairs)}; из них с разными днями запуска: '
      f'{sum(1 for v in pairs if v[0]["день"] != v[1]["день"])}, в один день: {sum(1 for v in pairs if v[0]["день"] == v[1]["день"])}; '
      f'один и тот же набор контента у обоих: {sum(1 for v in pairs if v[0]["набор"] == v[1]["набор"])}')
    P('Паттерны повторяющихся меток: ' + ', '.join(f'{k}:{v}' for k, v in Counter(v[0]['паттерн'] for v in pairs).most_common()))
    diff = [sorted(v, key=lambda d: d['день']) for v in pairs if v[0]['день'] != v[1]['день']]

    def sums(ds, key_o, key_e):
        o = sum(d[key_o] for d in ds if d[key_e] is not None)
        e = sum(d[key_e] for d in ds if d[key_e] is not None)
        n = sum(1 for d in ds if d[key_e] is not None)
        return o, e, n
    P()
    P('O/E относительно своего пула (leave-one-out, пулы >= 2 доменов), пары с разными днями:')
    second = {}
    for nm, idx in [('первый по дате экземпляр', 0), ('второй по дате экземпляр', 1)]:
        ds = [v[idx] for v in diff]
        o, e, n = sums(ds, 'вышли3', 'loo_E_выход')
        o2, e2, n2 = sums(ds, 'рег', 'loo_E_рег')
        P(f'  {nm:<26}: выход O = {int(o)}, E = {e:.1f}, O/E = {oe(o, e)} (доменов с E: {n}); '
          f'регистрации O = {int(o2)}, E = {e2:.1f}, O/E = {oe(o2, e2)} (доменов с E: {n2})')
        if idx == 1:
            second = dict(exit=o / e if e else float('nan'), reg=o2 / e2 if e2 else float('nan'))
    same = [v for v in pairs if v[0]['день'] == v[1]['день']]
    ds = [d for v in same for d in v]
    o, e, n = sums(ds, 'вышли3', 'loo_E_выход')
    o2, e2, n2 = sums(ds, 'рег', 'loo_E_рег')
    P(f'  {"пары в один день (оба)":<26}: выход O = {int(o)}, E = {e:.1f}, O/E = {oe(o, e)} (доменов с E: {n}); '
      f'регистрации O = {int(o2)}, E = {e2:.1f}, O/E = {oe(o2, e2)} (доменов с E: {n2})')
    # знаковые критерии
    w = l = t = 0
    for a, b in diff:
        ra, rb = a['вышли3'] / a['сайтов'], b['вышли3'] / b['сайтов']
        if rb < ra - 1e-12: w += 1
        elif rb > ra + 1e-12: l += 1
        else: t += 1
    p_raw = binom_two_sided(w, w + l)
    P(f'Знаковый критерий (сырой выход): второй экземпляр ХУЖЕ первого в {w} парах, ЛУЧШЕ в {l}, равен в {t}; p = {p_raw:.3f}')
    w = l = t = 0
    for a, b in diff:
        if a['loo_E_выход'] and b['loo_E_выход']:
            ra, rb = a['вышли3'] / a['loo_E_выход'], b['вышли3'] / b['loo_E_выход']
            if rb < ra - 1e-12: w += 1
            elif rb > ra + 1e-12: l += 1
            else: t += 1
    p_rel = binom_two_sided(w, w + l)
    P(f'Знаковый критерий (O/E относительно пула): второй ХУЖЕ в {w} парах, ЛУЧШЕ в {l}, равен в {t} (пар с обоими E: {w + l + t}); p = {p_rel:.3f}')
    w = l = t = 0
    for a, b in diff:
        ra, rb = a['рег'], b['рег']
        if rb < ra: w += 1
        elif rb > ra: l += 1
        else: t += 1
    p_reg = binom_two_sided(w, w + l)
    P(f'Знаковый критерий (регистрации в окне): второй МЕНЬШЕ в {w} парах, БОЛЬШЕ в {l}, равен в {t}; p = {p_reg:.3f}')
    return dict(n_pairs=len(pairs), n_diff=len(diff), second=second, p_raw=p_raw, p_rel=p_rel, p_reg=p_reg)


# ---------------------------------------------------------------------------
# 9. Замыкание: сверхдисперсия выхода и ячейки имени
# ---------------------------------------------------------------------------

def overdispersion_block(kept):
    P()
    P('=' * 100)
    P('БЛОК 6. Замыкание: сколько сверхдисперсии выхода внутри пулов снимает имя')
    P('=' * 100)
    pools = {k: v for k, v in build_pools(kept).items() if len(v) >= 5}
    items = [d for v in pools.values() for d in v]
    P(f'Пулов >= 5 доменов: {len(pools)}; доменов: {len(items)}; сайтов: {sum(d["сайтов"] for d in items)}')
    P('Ячейки имени: ' + ', '.join(f'{k}:{v}' for k, v in Counter(d['ячейка имени'] for d in items).most_common()))

    def chi_by_cells(pool_ds, cell_of):
        """χ² Пирсона выхода с биномиальной дисперсией, ставка — по ячейке внутри пула."""
        cells = defaultdict(list)
        for d in pool_ds:
            cells[cell_of(d)].append(d)
        chi = 0.0
        for cds in cells.values():
            S = sum(d['сайтов'] for d in cds); V = sum(d['вышли3'] for d in cds)
            if S == 0:
                continue
            p = V / S
            if p <= 0 or p >= 1:
                continue
            for d in cds:
                chi += (d['вышли3'] - d['сайтов'] * p) ** 2 / (d['сайтов'] * p * (1 - p))
        return chi, len(cells)

    chi_pool = 0.0; df_pool = 0; chi_cell = 0.0; df_cell = 0
    for k, ds in pools.items():
        c, _ = chi_by_cells(ds, lambda d: 0)
        chi_pool += c; df_pool += len(ds) - 1
        c2, nc = chi_by_cells(ds, lambda d: d['ячейка имени'])
        chi_cell += c2; df_cell += len(ds) - nc
    drop_real = 1 - chi_cell / chi_pool if chi_pool else float('nan')
    P(f'χ² по пулам (ставка пула): {chi_pool:.0f}, df = {df_pool}, χ²/df = {chi_pool / df_pool:.1f}')
    P(f'χ² по ячейкам пул × признак имени: {chi_cell:.0f}, df = {df_cell}, χ²/df = {chi_cell / df_cell:.1f}; '
      f'снято {100 * drop_real:.1f}% χ²')
    # случайные разбивки: те же размеры ячеек в каждом пуле
    rng = random.Random(1)
    drops = []
    for _ in range(N_SPLIT):
        tot = 0.0
        for k, ds in pools.items():
            labs = [d['ячейка имени'] for d in ds]
            rng.shuffle(labs)
            m = {id(d): l for d, l in zip(ds, labs)}
            c, _ = chi_by_cells(ds, lambda d: m[id(d)])
            tot += c
        drops.append(1 - tot / chi_pool)
    drops_s = sorted(drops)
    mean_drop = sum(drops) / len(drops)
    p_split = (sum(1 for x in drops if x >= drop_real) + 1) / (len(drops) + 1)
    P(f'Случайные разбивки на те же ячейки (N = {N_SPLIT}): снимают в среднем {100 * mean_drop:.1f}% χ² '
      f'(2,5–97,5%: {100 * drops_s[int(0.025 * N_SPLIT)]:.1f}–{100 * drops_s[int(0.975 * N_SPLIT) - 1]:.1f}%); '
      f'доля разбивок, снявших не меньше реальной: p = {p_split:.3f}')
    # только 4 паттерна (без подразбивки) — и тот же случайный ориентир
    chi_pat = 0.0; df_pat = 0
    for k, ds in pools.items():
        c2, nc = chi_by_cells(ds, lambda d: d['паттерн'])
        chi_pat += c2; df_pat += len(ds) - nc
    drop_pat = 1 - chi_pat / chi_pool
    drops4 = []
    for _ in range(N_SPLIT):
        tot = 0.0
        for k, ds in pools.items():
            labs = [d['паттерн'] for d in ds]
            rng.shuffle(labs)
            m = {id(d): l for d, l in zip(ds, labs)}
            c, _ = chi_by_cells(ds, lambda d: m[id(d)])
            tot += c
        drops4.append(1 - tot / chi_pool)
    mean4 = sum(drops4) / len(drops4)
    p4 = (sum(1 for x in drops4 if x >= drop_pat) + 1) / (len(drops4) + 1)
    P(f'Только 4 паттерна (без ведущего нуля / букв): χ² = {chi_pat:.0f}, df = {df_pat}, χ²/df = {chi_pat / df_pat:.1f}; снято {100 * drop_pat:.1f}% χ²; '
      f'случайные разбивки на 4 паттерна снимают {100 * mean4:.1f}% (p = {p4:.3f})')
    P('Что это значит: любая разбивка пула на ячейки снимает часть χ² механически (больше параметров); '
      'мерить надо разницу между реальной и случайной разбивкой.')
    P(f'  Реальная минус случайная: {100 * (drop_real - mean_drop):.1f} процентных пункта χ² (6 ячеек), '
      f'{100 * (drop_pat - mean4):.1f} п.п. (4 паттерна). χ²/df остаётся {chi_cell / df_cell:.1f} — сверхдисперсия почти вся на месте.')
    return dict(chi_df_pool=chi_pool / df_pool, chi_df_cell=chi_cell / df_cell, drop_real=drop_real, mean_drop=mean_drop, p_split=p_split,
                drop_pat=drop_pat, mean4=mean4, p4=p4)


# ---------------------------------------------------------------------------
# 10. Вывод
# ---------------------------------------------------------------------------

def verdict_block(main, zones, lens, speed, rep, od):
    obs = main['obs']
    P()
    P('=' * 100)
    P('ИТОГ ПО КРИТЕРИЯМ')
    P('=' * 100)
    ratios_exit = {g: obs[g]['вышли3'] / obs[g]['E_выход'] for g in PATTERNS}
    ratios_reg = {g: obs[g]['рег'] / obs[g]['E_рег_сайт'] for g in PATTERNS}
    P('O/E по выходу:       ' + ', '.join(f'{g} {ratios_exit[g]:.2f}' for g in PATTERNS) + f';  p (4 группы) = {main["p_exit"]:.3f}')
    P('O/E по регистрациям: ' + ', '.join(f'{g} {ratios_reg[g]:.2f}' for g in PATTERNS) + f';  p (4 группы) = {main["p_reg_site"]:.3f}')
    ce, pce = main['casino_exit']
    ci, pci = main['infix_reg']
    P(f'Контраст А1 casino_* по выходу: O/E = {ce:.2f}, p = {pce:.3f}; в team {zones["team"]["casino_exit"][0]:.2f} (p {zones["team"]["casino_exit"][1]:.3f}), '
      f'в lol {zones["lol"]["casino_exit"][0]:.2f} (p {zones["lol"]["casino_exit"][1]:.3f})')
    P(f'Контраст А2 casino_infix по регистрациям: O/E = {ci:.2f}, p = {pci:.3f}; в team {zones["team"]["infix_reg"][0]:.2f} (p {zones["team"]["infix_reg"][1]:.3f}), '
      f'в lol {zones["lol"]["infix_reg"][0]:.2f} (p {zones["lol"]["infix_reg"][1]:.3f})')
    all_in = all(0.85 <= v <= 1.15 for v in list(ratios_exit.values()) + list(ratios_reg.values()))
    P(f'Все восемь O/E в 0,85–1,15: {"да" if all_in else "НЕТ"}')
    eff_a1 = (ce < 0.8 or ce > 1.25) and pce < 0.05 and ((zones['team']['casino_exit'][0] < 1) == (zones['lol']['casino_exit'][0] < 1))
    eff_a2 = (ci < 0.8 or ci > 1.25) and pci < 0.05 and ((zones['team']['infix_reg'][0] < 1) == (zones['lol']['infix_reg'][0] < 1))
    P(f'Критерий «эффект» (O/E вне 0,8–1,25, p < 0,05, один знак в team и lol): А1 — {"выполнен" if eff_a1 else "не выполнен"}; А2 — {"выполнен" if eff_a2 else "не выполнен"}')
    return dict(ratios_exit=ratios_exit, ratios_reg=ratios_reg, all_in=all_in, eff_a1=eff_a1, eff_a2=eff_a2)


def pending_block(rows):
    """Что можно будет проверить на уже запущенных, но ещё не закрытых доменах."""
    P()
    P('=' * 100)
    P('БЛОК 7. Запас для повторной проверки: домены, у которых окно ещё не закрыто или день 2 не наступил')
    P('=' * 100)
    pend = [prepare(r) for r in rows if r['домен'] not in OUTLIERS and r['набор контента'] != NO_CONTENT
            and (r['окно закрыто'] != 'да' or r['дней'] == '1')]
    pools = build_pools(pend)
    multi = {k: v for k, v in pools.items() if len(set(d['паттерн'] for d in v)) >= 2}
    P(f'Таких доменов: {len(pend)} (' + ', '.join(f'{k}:{v}' for k, v in Counter(d['паттерн'] for d in pend).most_common()) + '); '
      f'дни запуска: ' + ', '.join(f'{k}:{v}' for k, v in sorted(Counter(d['день'] for d in pend).items())))
    P(f'Пулов «набор + день» среди них: {len(pools)}, из них с >= 2 паттернами: {len(multi)}.')
    roots = Counter(re.sub(r'_\d+$', '', d['набор']) for d in pend)
    rp = build_pools(pend, key=lambda d: (re.sub(r'_\d+$', '', d['набор']), d['день']))
    rmulti = {k: v for k, v in rp.items() if len(set(d['паттерн'] for d in v)) >= 2}
    P(f'С 17.09 наборы именуются по одному на домен (корень + _номер): корней {len(roots)}; '
      f'страт «корень набора + день» с >= 2 паттернами: {len(rmulti)}, доменов в них: {sum(len(v) for v in rmulti.values())} '
      f'(casino_infix: {sum(1 for v in rmulti.values() for d in v if d["паттерн"] == "casino_infix")}, '
      f'casino_prefix: {sum(1 for v in rmulti.values() for d in v if d["паттерн"] == "casino_prefix")}).')
    P('Это независимый от нынешнего расчёта материал: когда окна закроются (к 24–25.09), контраст casino_infix по регистрациям')
    P('можно пересчитать на нём той же схемой (страта «корень набора + день»), не трогая ничего в закупке.')
    return dict(n=len(pend), n_r=sum(len(v) for v in rmulti.values()),
                n_infix=sum(1 for d in pend if d['паттерн'] == 'casino_infix'), n_prefix=sum(1 for d in pend if d['паттерн'] == 'casino_prefix'))


def main():
    rows = load()
    kept = apply_filter(rows)
    main_res = main_block(kept)
    zones = zone_block(kept)
    lens = length_block(kept)
    speed = speed_block(kept)
    rep = repeat_block(kept, rows)
    od = overdispersion_block(kept)
    pend = pending_block(rows)
    v = verdict_block(main_res, zones, lens, speed, rep, od)

    obs = main_res['obs']
    re_ = v['ratios_exit']; rr = v['ratios_reg']
    ce, pce = main_res['casino_exit']; ci, pci = main_res['infix_reg']
    n_items = len(main_res['items']); n_pools = len(main_res['multi'])
    n_reg = sum(d['рег'] for d in main_res['items'])
    casino_n = obs['casino_prefix']['_n'] + obs['casino_infix']['_n']
    loo = main_res['infix_loo']
    P()
    P('=' * 100)
    P('ВЫВОД')
    P('=' * 100)
    P(f'1. Выход в поиск от имени домена не зависит. В {n_pools} пулах «набор контента + день», где стоят домены с разными')
    P(f'   именами ({n_items} доменов, {sum(d["сайтов"] for d in main_res["items"])} сайтов, {n_reg} регистраций в окне), O/E по выходу: '
      f'numeric {re_["numeric"]:.2f}, alpha_other {re_["alpha_other"]:.2f}, casino_prefix {re_["casino_prefix"]:.2f}, '
      f'casino_infix {re_["casino_infix"]:.2f}; перестановочное p = {main_res["p_exit"]:.3f}.')
    P(f'   Сырой разрыв выхода (casino ~10% против 12–13%) — тень дней и наборов: внутри пула casino-имена ({casino_n} доменов) дают O/E {ce:.2f} '
      f'(p = {pce:.3f}), то есть {int(obs["casino_prefix"]["вышли3"] + obs["casino_infix"]["вышли3"])} вышедших сайтов против '
      f'{obs["casino_prefix"]["E_выход"] + obs["casino_infix"]["E_выход"]:.0f} ожидаемых.')
    P(f'   Альтернатива А1 «casino_* хуже по выходу» опровергнута: по зонам знаки противоположные (team {zones["team"]["casino_exit"][0]:.2f}, '
      f'lol {zones["lol"]["casino_exit"][0]:.2f}), за 7 суток O/E {speed["c7"][0]:.2f} — догонять нечего; задержка до поиска внутри пула у casino больше в {speed["win"]} пулах, меньше в {speed["lose"]} (p = {speed["p_delay"]:.2f}).')
    P(f'2. Регистрации в окне 3 суток (ожидание от сайтов): numeric {rr["numeric"]:.2f}, alpha_other {rr["alpha_other"]:.2f}, '
      f'casino_prefix {rr["casino_prefix"]:.2f}, casino_infix {rr["casino_infix"]:.2f}; тест на все 4 группы p = {main_res["p_reg_site"]:.3f} — '
      f'в целом имя регистрации не двигает; casino-имена вместе O/E {main_res["casino_reg"][0]:.2f}.')
    P(f'   Альтернатива А2 «casino_infix лучше по регистрациям»: O/E = {ci:.2f} ({int(obs["casino_infix"]["рег"])} против ожидаемых '
      f'{obs["casino_infix"]["E_рег_сайт"]:.1f} на {obs["casino_infix"]["_n"]} доменах), p = {pci:.3f}, в team {zones["team"]["infix_reg"][0]:.2f} и в lol '
      f'{zones["lol"]["infix_reg"][0]:.2f} (оба p > 0,4). Формально это проходит объявленный порог (вне 0,8–1,25, p < 0,05, один знак в зонах),')
    P(f'   но сигнал хрупкий: (а) {loo[4]} из {loo[5]} регистраций дали два домена ({loo[2]}, {loo[3]}) — без первого O/E {loo[0]:.2f}, без обоих {loo[1]:.2f};')
    P(f'   (б) при ожидании от вышедших сайтов O/E {obs["casino_infix"]["рег"] / obs["casino_infix"]["E_рег_вышли"]:.2f} (p {main_res["infix_reg_vy"][1]:.2f}), от кликов '
      f'{obs["casino_infix"]["рег"] / obs["casino_infix"]["E_рег_клик"]:.2f} (p {main_res["infix_reg_cl"][1]:.2f}); (в) это те же {int(obs["casino_infix"]["рег"])} против {obs["casino_infix"]["E_рег_сайт"]:.1f}, которые были видны до объявления контраста, '
      f'то есть p не подтверждающее; (г) casino_prefix зеркально {rr["casino_prefix"]:.2f} — механизма, почему «casino» в конце метки лучше, чем в начале, нет.')
    P(f'3. Длина метки не работает: внутри alpha_other p = {lens["alpha_exit"]:.3f} (выход) / {lens["alpha_reg"]:.3f} (регистрации); '
      f'внутри casino-имён p = {lens["casino_exit"]:.3f} / {lens["casino_reg"]:.3f}. Ведущий ноль у numeric: выход O/E {lens["num0"]:.2f} (p = {lens["numeric_x_exit"]:.2f}); '
      f'только буквы у alpha_other: {lens["alpha_letters"]:.2f} против смеси {lens["alpha_mixed"]:.2f} (p = {lens["alpha_other_x_exit"]:.2f}) — в коридоре 0,85–1,15, значимости нет.')
    r73 = speed['r73']
    P(f'4. Скорость: вышли-7/вышли-3 — ' + ', '.join(f'{g} {r73[g][0]:.2f}' for g in PATTERNS if g in r73)
      + f'; casino-имена не догоняют, потому что и не отстают (O/E за 3 суток {speed["c3"][0]:.2f}, за 7 суток {speed["c7"][0]:.2f}).')
    P(f'5. Повтор метки в другой зоне не наказывается: пар {rep["n_pairs"]} (с разными днями {rep["n_diff"]}); второй по дате экземпляр относительно '
      f'своего пула не хуже (выход O/E {rep["second"]["exit"]:.2f}, регистрации {rep["second"]["reg"]:.2f}), знаковые p = {rep["p_raw"]:.2f} / {rep["p_rel"]:.2f} / {rep["p_reg"]:.2f} — всё в пределах случайности.')
    P(f'6. Разброс доменов внутри пула именем не объясняется: ячейки пул × признак имени снимают {100 * od["drop_real"]:.1f}% χ² против '
      f'{100 * od["mean_drop"]:.1f}% у случайной разбивки (разница {100 * (od["drop_real"] - od["mean_drop"]):.1f} п.п., p = {od["p_split"]:.3f}); '
      f'χ²/df {od["chi_df_pool"]:.1f} → {od["chi_df_cell"]:.1f}. Небольшой излишек над случайной разбивкой идёт от пулов, где casino-имена')
    P('   в team хуже, а в lol лучше соседей, — это разные партии внутри пула (одинаковый паттерн чаще ставится в один блок часа), а не имя.')
    P()
    P('ЧТО С ЭТИМ ДЕЛАТЬ:')
    P('   По выходу и длине метки — ничего, это знание, не рычаг: имя домена при закупке можно выбирать по цене и удобству,')
    P('   паттерн и длина на выход и регистрации не влияют; сырой разрыв casino-имён (0,04 против 0,11 рег/100 сайтов) — тень дней')
    P('   и наборов, и его нельзя больше приводить как довод. Повторять метку в другой зоне можно.')
    P(f'   Единственный хвост — casino_infix по регистрациям (1,56 на 21 регистрации, из них 9 на двух доменах). Закупку под него не менять.')
    P(f'   Проверка бесплатна и уже в данных: {pend["n"]} доменов запусков 16–21.09 (casino_infix {pend["n_infix"]}, casino_prefix {pend["n_prefix"]}) ждут закрытия окна;')
    P(f'   к 24–25.09 пересчитать O/E casino_infix по регистрациям на них в стратах «корень набора + день» ({pend["n_r"]} доменов в смешанных стратах).')
    P('   Если там O/E снова >= 1,3 при том же выходе — тогда есть предмет для разговора; если ~1,0 — вопрос имени закрыт целиком.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_out_lines) + '\n')
    print(f'\n[записано: {OUT_PATH}]')


if __name__ == '__main__':
    main()

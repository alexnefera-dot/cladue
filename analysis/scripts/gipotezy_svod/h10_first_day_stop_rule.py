#!/usr/bin/env python3
"""
Гипотеза №10. Правило первого дня: если к концу первых суток после переобхода
в поиск вышло ≤5 сайтов из 150, домен не даст регистраций в окне 3 суток даже
внутри своего пула «набор контента + день»; счётчик первого дня — ранний
прогноз уровня выхода, а не скорости; домен с нулём выходов к 3-м суткам
не оживает.

Что проверяем (три части).
  1. Правило. Домены с «вышли за 1 сутки» ≤5 дают регистраций в окне 3 суток
     сильно меньше, чем ожидается по их пулу «набор контента + день запуска».
     Ожидание домена E_i = (Σ регистраций пула / Σ сайтов пула) × сайтов_i;
     сравниваем ΣO/ΣE по группам «вышли за 1 сутки»: 0, 1–3, 4–5, 6–10, >10.
     Значимость — перестановка значений «вышли за 1 сутки» между доменами
     внутри пула (10 000 раз), p = доля перестановок, где O(v1≤5) ≤ наблюдённого.
     Отдельно по зонам team/lol/casino/buzz внутри страты пул + зона (≥2 домена),
     чтобы правило не оказалось тенью зоны (.buzz худшая, там v1≤5 чаще).
     Перебор порога {0, ≤3, ≤5, ≤8, ≤10}: сколько доменов помечено, сколько
     регистраций/ФД потеряно (в окне и за всё время), O/E, слоты квоты 56 ×
     помеченные. Альтернативная отсечка — «задержка до поиска, медиана» ≥2.
     Догоняют ли помеченные: «вышли за 3 суток» и «за 7 суток» у v1≤5.
  2. Скорость. При равном уровне выхода скорость (вышли за 1 / вышли за 3)
     ничего не добавляет. Ожидание считаем по вышедшим сайтам: ставка страты
     на вышедший сайт × «вышли за 3 суток» домена (только домены с ≥1 выходом),
     страта = пул × блок часа (вечерний запуск не может выйти в день 0);
     терцили скорости внутри страты; O/E терцилей, перестановка 10 000 раз;
     знаковый критерий «самый быстрый против самого медленного домена страты».
     Повтор со стратой = пул (больше объёма). Указана мощность: минимальное
     различимое отношение O/E быстрых к медленным.
  3. Нули. Базы с «вышли за 3 суток» = 0 при закрытом окне: сколько ожило
     к 7 суткам (≥3 выходов), регистраций за всё время; сравнение с базами
     1–5 и 6–15 выходов; сидят ли нули в пулах с выходом <5% — перестановка
     метки «нуль» между базами внутри дня запуска (10 000 раз).

Фильтр основного набора: окно закрыто = да; дней = 2 (домены с одной волной
и один домен с «дней»=3 исключены); семейство ≠ «не записан» (повтор с ним —
отдельной строкой, с оговоркой о сцепке с датой); выбросы 3615.team и
3286.team исключены везде. Все счётчики берутся из свода: «вышли за K суток»
— число сайтов домена с первым поисковым кликом в K суток от переобхода
этого сайта (то есть включает и 56 сайтов второй волны).

Только стандартная библиотека Python 3. random.seed(1).
"""
import collections
import csv
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h10_first_day_stop_rule.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
ZONES = ('team', 'lol', 'casino', 'buzz')
V1_GROUPS = ('0', '1-3', '4-5', '6-10', '>10')
LAST_DAY = '2026-09-21'   # дата свода; «вышли за 7 суток» полны только для запусков ≤ 14.09


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)

    def flush(self):
        sys.stdout.flush()
        self.f.flush()


def P(*a):
    print(*a, file=TEE)


def I(x):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def F(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def zone_of(r):
    return r['зона'] if r['зона'] in ZONES else 'прочие'


def v1_group(v):
    if v == 0:
        return '0'
    if v <= 3:
        return '1-3'
    if v <= 5:
        return '4-5'
    if v <= 10:
        return '6-10'
    return '>10'


def ratio(o, e):
    return o / e if e > 0 else float('nan')


def fmt_oe(o, e):
    return '%.2f' % (o / e) if e > 0 else '  —  '


def binom_two_sided(k, n):
    """Точный двусторонний биномиальный p при p0 = 0,5."""
    if n == 0:
        return float('nan')
    probs = [math.comb(n, i) / 2 ** n for i in range(n + 1)]
    pk = probs[k]
    return min(1.0, sum(p for p in probs if p <= pk + 1e-12))


def pool_expectations(rows, key_fn, num='reg', den='sites'):
    """E_i = ставка страты × знаменатель домена. Возвращает {домен: E}."""
    num_s = collections.Counter()
    den_s = collections.Counter()
    for r in rows:
        k = key_fn(r)
        num_s[k] += r[num]
        den_s[k] += r[den]
    E = {}
    for r in rows:
        k = key_fn(r)
        E[r['id']] = (num_s[k] / den_s[k]) * r[den] if den_s[k] > 0 else 0.0
    return E


def load():
    rows = []
    with open(SRC, encoding='utf-8') as f:
        for i, raw in enumerate(csv.DictReader(f)):
            r = dict(raw)
            r['id'] = i
            r['z'] = zone_of(raw)
            r['sites'] = I(raw['сайтов в окне']) or 0
            r['v1'] = I(raw['вышли за 1 сутки'])
            r['v3'] = I(raw['вышли за 3 суток'])
            r['v7'] = I(raw['вышли за 7 суток'])
            r['reg'] = I(raw['регистраций в окне 3 суток']) or 0
            r['fd'] = I(raw['ФД в окне 3 суток']) or 0
            r['reg_all'] = I(raw['регистраций']) or 0
            r['fd_all'] = I(raw['ФД']) or 0
            r['delay'] = F(raw['задержка до поиска, медиана'])
            r['pool'] = (raw['набор контента'], raw['день запуска'])
            r['block'] = raw['блок часа']
            r['day'] = raw['день запуска']
            rows.append(r)
    return rows


def filter_main(rows):
    P('Фильтр (исключения по шагам):')
    cur = rows
    steps = [
        ('окно закрыто = нет (3 суток ещё не прошли)', lambda r: r['окно закрыто'] == 'да'),
        ('дней ≠ 2 (77 доменов с одной волной 150 сайтов и 1 домен с «дней»=3)', lambda r: r['дней'] == '2'),
        ('выбросы 3615.team, 3286.team (миллионы «прочих» кликов; исключены везде)', lambda r: r['домен'] not in OUTLIERS),
        ('«КОНТЕНТ НЕ ЗАПИСАН» (не набор, сцеплен с датой)', lambda r: r['семейство'] != 'не записан'),
    ]
    for name, fn in steps:
        nxt = [r for r in cur if fn(r)]
        P('  %s: исключено %d, осталось %d' % (name, len(cur) - len(nxt), len(nxt)))
        cur = nxt
    return cur


# ----------------------------------------------------------------------------
def part_context(main):
    P('')
    P('Контекст БЕЗ страты (не доказательство — набор контента и день сцеплены с выходом):')
    P('  «вышли за 1 сутки»  доменов   сайтов   рег в окне  рег/100 сайтов   ФД в окне  рег всё время  ФД всё время   ср. вышли за 3   ср. вышли за 7')
    tot = collections.Counter()
    by = collections.defaultdict(list)
    for r in main:
        by[v1_group(r['v1'])].append(r)
    for g in V1_GROUPS:
        rs = by[g]
        n = len(rs)
        s = sum(r['sites'] for r in rs)
        reg = sum(r['reg'] for r in rs)
        fd = sum(r['fd'] for r in rs)
        ra = sum(r['reg_all'] for r in rs)
        fa = sum(r['fd_all'] for r in rs)
        m3 = sum(r['v3'] for r in rs) / n if n else 0
        m7 = sum(r['v7'] for r in rs) / n if n else 0
        P('  %-18s %8d %8d %11d %14s %11d %14d %13d %16.1f %16.1f' % (
            g, n, s, reg, ('%.3f' % (100 * reg / s)) if s else '—', fd, ra, fa, m3, m7))
    n = len(main)
    s = sum(r['sites'] for r in main)
    reg = sum(r['reg'] for r in main)
    P('  %-18s %8d %8d %11d %14.3f %11d %14d %13d' % (
        'всего', n, s, reg, 100 * reg / s, sum(r['fd'] for r in main),
        sum(r['reg_all'] for r in main), sum(r['fd_all'] for r in main)))
    le5 = [r for r in main if r['v1'] <= 5]
    ge6 = [r for r in main if r['v1'] >= 6]
    s5 = sum(r['sites'] for r in le5)
    s6 = sum(r['sites'] for r in ge6)
    r5 = sum(r['reg'] for r in le5)
    r6 = sum(r['reg'] for r in ge6)
    P('  Итого v1≤5: %d доменов, %d сайтов, %d рег в окне (%.3f/100); v1≥6: %d доменов, %d сайтов, %d рег (%.3f/100); отношение %.0f×' % (
        len(le5), s5, r5, 100 * r5 / s5, len(ge6), s6, r6, 100 * r6 / s6,
        (r6 / s6) / (r5 / s5) if r5 else float('inf')))


# ----------------------------------------------------------------------------
def part_rule(main):
    P('')
    P('=' * 110)
    P('А. ПРАВИЛО ПЕРВОГО ДНЯ: O/E по группам «вышли за 1 сутки» внутри пула «набор контента + день запуска»')
    P('=' * 110)
    pools = collections.defaultdict(list)
    for r in main:
        pools[r['pool']].append(r)
    with_reg = {k for k, v in pools.items() if sum(r['reg'] for r in v) > 0}
    multi = {k for k, v in pools.items() if len(v) >= 2}
    d_in = [r for r in main if r['pool'] in with_reg]
    P('Пулов: %d (из них с ≥2 доменами %d, одиночных %d — это в основном запуски 15–17.09, где на каждом домене свой набор).' % (
        len(pools), len(multi), len(pools) - len(multi)))
    P('Пулов с ≥1 регистрацией в окне: %d; в них %d доменов, %d сайтов, %d регистраций. Только они дают ожидание E > 0; остальные пулы (E = 0, O = 0) на O/E не влияют.' % (
        len(with_reg), len(d_in), sum(r['sites'] for r in d_in), sum(r['reg'] for r in d_in)))
    E = pool_expectations(main, lambda r: r['pool'])

    P('')
    P('Таблица А1. O/E по группам (все зоны). Последний столбец — пуассоновская вероятность получить не больше наблюдённого при данном E (ориентир, не главный тест).')
    P('  группа   доменов  из них в пулах с рег   сайтов (в пулах с рег)      O       E     O/E   P(O ≤ набл | E)')
    for g in V1_GROUPS:
        rs = [r for r in main if v1_group(r['v1']) == g]
        rin = [r for r in rs if r['pool'] in with_reg]
        o = sum(r['reg'] for r in rs)
        e = sum(E[r['id']] for r in rs)
        p_le = poisson_cdf(o, e)
        P('  %-8s %8d %20d %26d %6d %7.1f  %6s   %s' % (
            g, len(rs), len(rin), sum(r['sites'] for r in rin), o, e, fmt_oe(o, e), '%.4f' % p_le if e > 0 else '—'))
    le5 = [r for r in main if r['v1'] <= 5]
    o5 = sum(r['reg'] for r in le5)
    e5 = sum(E[r['id']] for r in le5)
    rin5 = [r for r in le5 if r['pool'] in with_reg]
    P('  v1≤5 вместе: %d доменов (%d в пулах с рег, %d сайтов), O = %d, E = %.1f, O/E = %s' % (
        len(le5), len(rin5), sum(r['sites'] for r in rin5), o5, e5, fmt_oe(o5, e5)))

    # перестановка v1 внутри пула
    random.seed(1)
    obs = o5
    cnt_le = 0
    dist = []
    pool_lists = [v for k, v in pools.items() if len(v) >= 2 and k in with_reg]
    fixed = sum(r['reg'] for k, v in pools.items() if (len(v) < 2) for r in v if r['v1'] <= 5)
    for _ in range(NPERM):
        tot = fixed
        for v in pool_lists:
            vals = [r['v1'] for r in v]
            random.shuffle(vals)
            for r, x in zip(v, vals):
                if x <= 5:
                    tot += r['reg']
        dist.append(tot)
        if tot <= obs:
            cnt_le += 1
    dist.sort()
    res = {'n_le5': len(le5), 'o5': o5, 'e5': e5, 'p_perm': cnt_le / NPERM, 'null_mean': sum(dist) / len(dist),
           'null_lo': dist[int(0.025 * NPERM)], 'null_hi': dist[int(0.975 * NPERM) - 1], 'zone': {}}
    P('  Перестановка «вышли за 1 сутки» между доменами внутри пула (%d раз): наблюдённое O(v1≤5) = %d; под нулевой гипотезой O в среднем %.1f, 95%% интервал [%d; %d]; p = P(O ≤ %d) = %.4f (%d из %d).' % (
        NPERM, obs, res['null_mean'], res['null_lo'], res['null_hi'], obs, res['p_perm'], cnt_le, NPERM))

    # по зонам: страта пул (все зоны вместе) и страта пул+зона
    P('')
    P('Таблица А2. v1≤5 по зонам. Слева — ожидание по пулу (все зоны в пуле вместе), справа — страта пул + зона (только страты с ≥2 доменами).')
    Ez = pool_expectations(main, lambda r: (r['pool'], r['z']))
    strata_z = collections.Counter((r['pool'], r['z']) for r in main)
    P('  зона     доменов  v1≤5   доля v1≤5 | пул: O    E    O/E  | пул+зона (≥2 дом.): доменов v1≤5   O     E    O/E   | v1≥6 в пул+зона: O    E   O/E')
    for z in ZONES + ('прочие',):
        rs = [r for r in main if r['z'] == z]
        if not rs:
            continue
        f = [r for r in rs if r['v1'] <= 5]
        o = sum(r['reg'] for r in f)
        e = sum(E[r['id']] for r in f)
        f2 = [r for r in f if strata_z[(r['pool'], r['z'])] >= 2]
        o2 = sum(r['reg'] for r in f2)
        e2 = sum(Ez[r['id']] for r in f2)
        g2 = [r for r in rs if r['v1'] >= 6 and strata_z[(r['pool'], r['z'])] >= 2]
        o3 = sum(r['reg'] for r in g2)
        e3 = sum(Ez[r['id']] for r in g2)
        res['zone'][z] = (len(f2), o2, e2)
        P('  %-8s %7d %6d %9.1f%% | %5d %6.1f %6s | %26d %5d %6.1f %6s | %19d %6.1f %6s' % (
            z, len(rs), len(f), 100 * len(f) / len(rs), o, e, fmt_oe(o, e), len(f2), o2, e2, fmt_oe(o2, e2), o3, e3, fmt_oe(o3, e3)))

    # перебор порога
    P('')
    P('Таблица А3. Перебор порога «пометить домен, если вышли за 1 сутки ≤ T». Потери — все регистрации/ФД помеченных доменов (верхняя граница: в своде нельзя отделить регистрации второй волны от первой).')
    tot_reg = sum(r['reg'] for r in main)
    tot_fd = sum(r['fd'] for r in main)
    tot_ra = sum(r['reg_all'] for r in main)
    tot_fa = sum(r['fd_all'] for r in main)
    P('  Всего в наборе: %d доменов, %d регистраций в окне (%d за всё время), %d ФД в окне (%d за всё время).' % (
        len(main), tot_reg, tot_ra, tot_fd, tot_fa))
    P('  порог   помечено  доля    сайтов   рег окно (потеря %)    рег всё время (потеря %)    ФД окно   ФД всё время     O      E    O/E   слотов 56× (авг / сен)')
    for T in (0, 3, 5, 8, 10):
        f = [r for r in main if r['v1'] <= T]
        o = sum(r['reg'] for r in f)
        e = sum(E[r['id']] for r in f)
        ra = sum(r['reg_all'] for r in f)
        aug = sum(1 for r in f if r['day'] < '2026-09')
        P('  ≤%-4d %9d %6.1f%% %8d %6d (%5.2f%%)  %14d (%5.2f%%) %12d %12d %10d %6.1f %6s   %6d (%d / %d)' % (
            T, len(f), 100 * len(f) / len(main), sum(r['sites'] for r in f), o, 100 * o / tot_reg, ra, 100 * ra / tot_ra,
            sum(r['fd'] for r in f), sum(r['fd_all'] for r in f), o, e, fmt_oe(o, e), 56 * len(f), 56 * aug, 56 * (len(f) - aug)))
    # кто именно дал регистрации при v1≤10
    P('  Домены с v1≤10 и хоть одной регистрацией за всё время:')
    for r in sorted((r for r in main if r['v1'] <= 10 and r['reg_all'] > 0), key=lambda r: r['v1']):
        P('    %-22s %-7s %s  набор=%s  v1=%d v3=%d v7=%d  рег окно=%d рег всего=%d ФД=%d  блок=%s  бренды: %s' % (
            r['домен'], r['z'], r['day'], r['набор контента'], r['v1'], r['v3'], r['v7'], r['reg'], r['reg_all'], r['fd_all'], r['block'], r['какие бренды конвертили']))

    # альтернативная отсечка: задержка до поиска, медиана ≥2
    P('')
    P('Таблица А4. Альтернативная отсечка «задержка до поиска, медиана» ≥2 суток (пусто = у домена ни одного поискового клика).')
    P('  Оговорка: медиана задержки становится известна только после того, как сайты вышли; на утро 2-го дня её нет — это не операционное правило, а проверка «медленные = пустые».')
    P('  группа                 доменов  сайтов   рег окно   рег всё   ФД окно     O      E    O/E   ср. v1  ср. v3')
    for name, fn in (('задержка < 2', lambda r: r['delay'] is not None and r['delay'] < 2),
                     ('задержка ≥ 2', lambda r: r['delay'] is not None and r['delay'] >= 2),
                     ('нет поиска (пусто)', lambda r: r['delay'] is None),
                     ('≥2 или пусто', lambda r: r['delay'] is None or r['delay'] >= 2)):
        f = [r for r in main if fn(r)]
        o = sum(r['reg'] for r in f)
        e = sum(E[r['id']] for r in f)
        n = len(f)
        P('  %-22s %7d %8d %9d %9d %8d %7d %6.1f %6s %7.1f %7.1f' % (
            name, n, sum(r['sites'] for r in f), o, sum(r['reg_all'] for r in f), sum(r['fd'] for r in f), o, e, fmt_oe(o, e),
            sum(r['v1'] for r in f) / n if n else 0, sum(r['v3'] for r in f) / n if n else 0))
    # перестановка для «≥2 или пусто»
    random.seed(1)
    flag = lambda r: r['delay'] is None or r['delay'] >= 2
    obs = sum(r['reg'] for r in main if flag(r))
    fixed = sum(r['reg'] for k, v in pools.items() if len(v) < 2 for r in v if flag(r))
    cnt = 0
    for _ in range(NPERM):
        tot = fixed
        for v in pool_lists:
            vals = [flag(r) for r in v]
            random.shuffle(vals)
            for r, x in zip(v, vals):
                if x:
                    tot += r['reg']
        if tot <= obs:
            cnt += 1
    res['delay_flag_n'] = sum(1 for r in main if flag(r))
    res['delay_o'] = obs
    res['delay_e'] = sum(E[r['id']] for r in main if flag(r))
    res['delay_p'] = cnt / NPERM
    P('  Перестановка метки «≥2 или пусто» внутри пула: наблюдённое O = %d, p = P(O ≤ набл.) = %.4f.' % (obs, cnt / NPERM))
    # пересечение с v1≤5
    both = [r for r in main if flag(r) and r['v1'] <= 5]
    only_d = [r for r in main if flag(r) and r['v1'] > 5]
    only_v = [r for r in main if not flag(r) and r['v1'] <= 5]
    P('  Пересечение с v1≤5: обе метки %d доменов; только задержка ≥2/пусто %d (рег в окне %d, E %.1f); только v1≤5 %d (рег %d, E %.1f).' % (
        len(both), len(only_d), sum(r['reg'] for r in only_d), sum(E[r['id']] for r in only_d),
        len(only_v), sum(r['reg'] for r in only_v), sum(E[r['id']] for r in only_v)))

    # догоняют ли
    P('')
    P('Таблица А5. Догоняют ли помеченные: «вышли за 3 суток» и «за 7 суток» по группам первого дня.')
    P('  Оговорка: «вышли за 7 суток» полны только у запусков до 14.09 включительно (свод от %s); для более поздних это нижняя оценка.' % LAST_DAY)
    res['catch'] = {}
    P('  группа v1   доменов   ср. v1   ср. v3   ср. v7   доля v3≥6   доля v7≥6   доля v7≥11   v3/сайтов %   v7/сайтов %  | запусков ≤14.09: доменов  ср. v7  доля v7≥6')
    for g in V1_GROUPS:
        rs = [r for r in main if v1_group(r['v1']) == g]
        n = len(rs)
        s = sum(r['sites'] for r in rs)
        old = [r for r in rs if r['day'] <= '2026-09-14']
        res['catch'][g] = (n, sum(r['v3'] for r in rs) / n, sum(r['v7'] for r in rs) / n,
                           100 * sum(1 for r in rs if r['v3'] >= 6) / n, 100 * sum(1 for r in rs if r['v7'] >= 6) / n)
        P('  %-10s %8d %8.1f %8.1f %8.1f %10.1f%% %10.1f%% %11.1f%% %12.2f %12.2f  | %20d %7.1f %9.1f%%' % (
            g, n, sum(r['v1'] for r in rs) / n, sum(r['v3'] for r in rs) / n, sum(r['v7'] for r in rs) / n,
            100 * sum(1 for r in rs if r['v3'] >= 6) / n, 100 * sum(1 for r in rs if r['v7'] >= 6) / n,
            100 * sum(1 for r in rs if r['v7'] >= 11) / n,
            100 * sum(r['v3'] for r in rs) / s, 100 * sum(r['v7'] for r in rs) / s,
            len(old), (sum(r['v7'] for r in old) / len(old)) if old else 0,
            (100 * sum(1 for r in old if r['v7'] >= 6) / len(old)) if old else 0))
    return E, pools, with_reg, res


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = 0.0
    term = math.exp(-lam)
    for i in range(k + 1):
        s += term
        term *= lam / (i + 1)
    return min(1.0, s)


# ----------------------------------------------------------------------------
def part_repeat_with_nocontent(rows):
    P('')
    P('Повтор правила с «КОНТЕНТ НЕ ЗАПИСАН» (пул = «КОНТЕНТ НЕ ЗАПИСАН» + день; это не набор, а отсутствие записи до 24.08, полностью сцеплено с датой — считать только как проверку, что картина не меняется):')
    cur = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] == '2' and r['домен'] not in OUTLIERS]
    E = pool_expectations(cur, lambda r: r['pool'])
    nc = [r for r in cur if r['семейство'] == 'не записан']
    P('  Набор: %d доменов, из них «не записан» %d (%d сайтов, %d регистраций в окне, v1≤5 у %d).' % (
        len(cur), len(nc), sum(r['sites'] for r in nc), sum(r['reg'] for r in nc), sum(1 for r in nc if r['v1'] <= 5)))
    P('  группа   доменов   сайтов     O      E    O/E')
    for g in V1_GROUPS:
        rs = [r for r in cur if v1_group(r['v1']) == g]
        o = sum(r['reg'] for r in rs)
        e = sum(E[r['id']] for r in rs)
        P('  %-8s %8d %8d %6d %6.1f %6s' % (g, len(rs), sum(r['sites'] for r in rs), o, e, fmt_oe(o, e)))
    f = [r for r in cur if r['v1'] <= 5]
    P('  v1≤5: %d доменов, O = %d, E = %.1f, O/E = %s; слоты 56× = %d (август %d, сентябрь %d).' % (
        len(f), sum(r['reg'] for r in f), sum(E[r['id']] for r in f), fmt_oe(sum(r['reg'] for r in f), sum(E[r['id']] for r in f)),
        56 * len(f), 56 * sum(1 for r in f if r['day'] < '2026-09'), 56 * sum(1 for r in f if r['day'] >= '2026-09')))
    return len(f)


# ----------------------------------------------------------------------------
def half_labels(rs):
    """Половины скорости внутри страты по средним рангам: ниже медианы — медленная, выше — быстрая, ровно на медиане — «середина»."""
    n = len(rs)
    vals = sorted(r['speed'] for r in rs)
    rank = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[j + 1] == vals[i]:
            j += 1
        rank[vals[i]] = (i + j) / 2
        i = j + 1
    lab = {}
    mid = (n - 1) / 2
    for r in rs:
        q = rank[r['speed']]
        lab[r['id']] = 'медленные' if q < mid - 1e-9 else ('быстрые' if q > mid + 1e-9 else 'средние')
    return lab


def tertile_labels(rs):
    """Терцили скорости внутри страты по средним рангам (связи — один ярлык). n=2 → медленный/быстрый."""
    n = len(rs)
    vals = sorted(r['speed'] for r in rs)
    # средний ранг
    rank = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[j + 1] == vals[i]:
            j += 1
        rank[vals[i]] = (i + j) / 2
        i = j + 1
    lab = {}
    for r in rs:
        p = rank[r['speed']] / (n - 1)
        lab[r['id']] = 'медленные' if p < 1 / 3 - 1e-9 else ('быстрые' if p > 2 / 3 + 1e-9 else 'средние')
    return lab


def speed_analysis(rows, key_fn, title, split='терцили'):
    P('')
    P(title)
    strata = collections.defaultdict(list)
    for r in rows:
        strata[key_fn(r)].append(r)
    use = {k: v for k, v in strata.items() if len(v) >= 2}
    used = [r for v in use.values() for r in v]
    E = pool_expectations(used, key_fn, num='reg', den='v3')
    lab = {}
    for v in use.values():
        lab.update(tertile_labels(v) if split == 'терцили' else half_labels(v))
    with_reg = {k for k, v in use.items() if sum(r['reg'] for r in v) > 0}
    P('  Страт с ≥2 доменами: %d (%d доменов, %d вышедших сайтов, %d регистраций); из них с регистрациями %d (%d доменов, %d рег). Одиночные страты отброшены: %d доменов.' % (
        len(use), len(used), sum(r['v3'] for r in used), sum(r['reg'] for r in used), len(with_reg),
        sum(len(use[k]) for k in with_reg), sum(r['reg'] for k in with_reg for r in use[k]), len(rows) - len(used)))

    def oe_by_label(labels):
        o = collections.Counter()
        e = collections.Counter()
        for r in used:
            o[labels[r['id']]] += r['reg']
            e[labels[r['id']]] += E[r['id']]
        return o, e

    o, e = oe_by_label(lab)
    P('  %-11s доменов   вышли за 3 (сум.)   ср. скорость v1/v3     O      E     O/E' % ('терциль' if split == 'терцили' else 'половина'))
    for t in ('медленные', 'средние', 'быстрые'):
        rs = [r for r in used if lab[r['id']] == t]
        P('  %-11s %8d %18d %20.3f %6d %6.1f  %6s' % (
            t, len(rs), sum(r['v3'] for r in rs), sum(r['speed'] for r in rs) / len(rs) if rs else 0, o[t], e[t], fmt_oe(o[t], e[t])))
    obs_ratio = ratio(o['быстрые'], e['быстрые']) / ratio(o['медленные'], e['медленные']) if o['медленные'] > 0 and e['медленные'] > 0 and e['быстрые'] > 0 else float('nan')
    P('  Отношение O/E быстрых к O/E медленных: %.2f' % obs_ratio)
    # мощность
    of, om = o['быстрые'], o['медленные']
    if of > 0 and om > 0:
        mdr = math.exp(1.96 * math.sqrt(1 / of + 1 / om))
        P('  Мощность: при %d и %d регистрациях в крайних терцилях минимальное различимое отношение (двусторонний 5%%) ≈ %.2f×; эффект меньше этого на своде не виден.' % (of, om, mdr))
    # перестановка ярлыков внутри страты
    random.seed(1)
    ids_by_stratum = [[r['id'] for r in v] for k, v in use.items() if k in with_reg]
    fixed_o = collections.Counter()
    fixed_e = collections.Counter()
    for k, v in use.items():
        if k not in with_reg:
            for r in v:
                fixed_o[lab[r['id']]] += r['reg']
                fixed_e[lab[r['id']]] += E[r['id']]
    reg_of = {r['id']: r['reg'] for r in used}
    cnt_fast_ge = cnt_fast_le = cnt_ratio = 0
    obs_f = ratio(o['быстрые'], e['быстрые'])
    obs_s = ratio(o['медленные'], e['медленные'])
    obs_log = abs(math.log(obs_ratio)) if obs_ratio == obs_ratio and obs_ratio > 0 else float('inf')
    lab_p = dict(lab)
    for _ in range(NPERM):
        for ids in ids_by_stratum:
            ls = [lab[i] for i in ids]
            random.shuffle(ls)
            for i, l in zip(ids, ls):
                lab_p[i] = l
        oo = collections.Counter(fixed_o)
        ee = collections.Counter(fixed_e)
        for ids in ids_by_stratum:
            for i in ids:
                oo[lab_p[i]] += reg_of[i]
                ee[lab_p[i]] += E[i]
        f = ratio(oo['быстрые'], ee['быстрые'])
        s = ratio(oo['медленные'], ee['медленные'])
        if f >= obs_f - 1e-12:
            cnt_fast_ge += 1
        if f <= obs_f + 1e-12:
            cnt_fast_le += 1
        if oo['медленные'] > 0 and oo['быстрые'] > 0 and ee['медленные'] > 0 and ee['быстрые'] > 0:
            lg = abs(math.log(f / s))
        else:
            lg = float('inf')   # один из терцилей без регистраций — крайний случай
        if lg >= obs_log - 1e-12:
            cnt_ratio += 1
    p_ratio = cnt_ratio / NPERM
    P('  Перестановка ярлыков внутри страты (%d раз): P(O/E быстрых ≥ набл.) = %.3f, P(O/E быстрых ≤ набл.) = %.3f; двусторонний p для отношения быстрые/медленные = %.3f.' % (
        NPERM, cnt_fast_ge / NPERM, cnt_fast_le / NPERM, p_ratio))
    # знаковый критерий: самый быстрый против самого медленного
    w = l = t = skipped = 0
    for k, v in use.items():
        sp = sorted(v, key=lambda r: r['speed'])
        if sp[0]['speed'] == sp[-1]['speed']:
            skipped += 1
            continue
        a = sp[-1]['reg'] / sp[-1]['v3']
        b = sp[0]['reg'] / sp[0]['v3']
        if a > b:
            w += 1
        elif a < b:
            l += 1
        else:
            t += 1
    p_sign = binom_two_sided(w, w + l)
    P('  Знаковый критерий «самый быстрый против самого медленного домена страты» по регистрациям на вышедший сайт: быстрый лучше %d, медленный лучше %d, ничья (обычно 0 = 0) %d, страт без разброса скорости %d; точный биномиальный p = %.3f.' % (
        w, l, t, skipped, p_sign))
    return {'ratio': obs_ratio, 'p_ratio': p_ratio, 'p_sign': p_sign, 'wins': w, 'losses': l, 'ties': t,
            'o_fast': o['быстрые'], 'o_slow': o['медленные'], 'oe_fast': obs_f, 'oe_slow': obs_s,
            'mdr': math.exp(1.96 * math.sqrt(1 / of + 1 / om)) if of > 0 and om > 0 else float('nan')}


def part_speed(main):
    P('')
    P('=' * 110)
    P('Б. КОНТРОЛЬ СКОРОСТИ: при равном уровне (ожидание по «вышли за 3 суток») добавляет ли что-то скорость v1/v3')
    P('=' * 110)
    rows = [r for r in main if r['v3'] >= 1]
    for r in rows:
        r['speed'] = r['v1'] / r['v3']
    P('Домены с ≥1 выходом за 3 суток: %d из %d.' % (len(rows), len(main)))
    P('Скорость по блоку часа (без страты, для справки — вечерний запуск):')
    P('  блок    доменов   ср. скорость   доля v1≤5   доля скорости <0,5')
    for b in ('00-05', '06-11', '12-17', '18-23'):
        rs = [r for r in rows if r['block'] == b]
        P('  %-6s %8d %13.3f %10.1f%% %14.1f%%' % (
            b, len(rs), sum(r['speed'] for r in rs) / len(rs), 100 * sum(1 for r in rs if r['v1'] <= 5) / len(rs),
            100 * sum(1 for r in rs if r['speed'] < 0.5) / len(rs)))
    r1 = speed_analysis(rows, lambda r: (r['pool'], r['block']), 'Б1. Страта = пул (набор + день) × блок часа; ставка страты на вышедший сайт; терцили скорости.')
    r2 = speed_analysis(rows, lambda r: r['pool'], 'Б2. Страта = пул (набор + день) без блока часа (больше объёма; час уже опровергнут как фактор); терцили.')
    r3 = speed_analysis(rows, lambda r: (r['pool'], r['block']), 'Б3. Страта = пул × блок часа; половины скорости (выше/ниже медианы страты) — больше регистраций в сравнении, мощность выше.', split='половины')
    r4 = speed_analysis(rows, lambda r: r['pool'], 'Б4. Страта = пул; половины скорости.', split='половины')
    P('  Мощность (в постановке ≈1,35): минимальное различимое отношение быстрые/медленные по терцилям %.2f× (Б1) и %.2f× (Б2), по половинам %.2f× (Б3) и %.2f× (Б4).' % (r1['mdr'], r2['mdr'], r3['mdr'], r4['mdr']))
    # грубый контекст: задержка 0 vs остальное без страты
    P('')
    P('Для сравнения, грубый эффект без страты (тот, что выглядел как «задержка 0 → больше регистраций»):')
    P('  медиана задержки   доменов   сайтов   вышли за 3   рег окно   рег/100 сайтов   рег на 100 вышедших')
    for name, fn in (('0', lambda r: r['delay'] == 0), ('0,5–1', lambda r: r['delay'] is not None and 0 < r['delay'] <= 1),
                     ('1,5–2', lambda r: r['delay'] is not None and 1 < r['delay'] <= 2), ('>2', lambda r: r['delay'] is not None and r['delay'] > 2)):
        rs = [r for r in rows if fn(r)]
        s = sum(r['sites'] for r in rs)
        v3 = sum(r['v3'] for r in rs)
        reg = sum(r['reg'] for r in rs)
        P('  %-17s %8d %8d %11d %9d %15.3f %19.2f' % (name, len(rs), s, v3, reg, 100 * reg / s if s else 0, 100 * reg / v3 if v3 else 0))
    return r1, r2, r3, r4


# ----------------------------------------------------------------------------
def part_zeros(rows, main):
    P('')
    P('=' * 110)
    P('В. НУЛИ: базы с «вышли за 3 суток» = 0 при закрытом окне')
    P('=' * 110)
    closed = [r for r in rows if r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS]
    zeros = [r for r in closed if r['v3'] == 0]
    P('Закрытых окон (без выбросов): %d; из них нулей: %d (%.1f%%). Здесь взяты все закрытые, включая «не записан» и одноволновые — для описания; тест концентрации ниже — на основном наборе.' % (
        len(closed), len(zeros), 100 * len(zeros) / len(closed)))
    # pool-mates exit for all closed
    pools = collections.defaultdict(list)
    for r in closed:
        pools[r['pool']].append(r)

    def mates_rate(r):
        v = pools[r['pool']]
        if len(v) < 2:
            return None
        s = sum(x['sites'] for x in v if x is not r)
        return sum(x['v3'] for x in v if x is not r) / s if s else None

    P('  домен                 зона    день        дней  блок   семейство      набор контента                         v7  рег всего  выход соседей по пулу %')
    for r in sorted(zeros, key=lambda r: (r['day'], r['домен'])):
        mr = mates_rate(r)
        P('  %-21s %-7s %s %4s  %-6s %-14s %-38s %3d %9d   %s' % (
            r['домен'], r['z'], r['day'], r['дней'], r['block'], r['семейство'], r['набор контента'][:38], r['v7'], r['reg_all'],
            ('%.1f' % (100 * mr)) if mr is not None else 'один в пуле'))
    days = collections.Counter(r['day'] for r in zeros)
    alld = collections.Counter(r['day'] for r in closed)
    P('  По дням запуска (нулей / всех закрытых в этот день):')
    for d, c in days.most_common():
        P('    %s: %d / %d (%.1f%%)' % (d, c, alld[d], 100 * c / alld[d]))
    top3 = sum(c for d, c in days.most_common(3))
    P('    три самых больших дня дают %d из %d нулей (%.0f%%), при том что на них %d из %d закрытых доменов (%.0f%%).' % (
        top3, len(zeros), 100 * top3 / len(zeros), sum(alld[d] for d, c in days.most_common(3)), len(closed),
        100 * sum(alld[d] for d, c in days.most_common(3)) / len(closed)))
    P('  По зонам (нулей / всех закрытых в зоне):')
    zc = collections.Counter(r['z'] for r in zeros)
    za = collections.Counter(r['z'] for r in closed)
    for z in ZONES + ('прочие',):
        P('    %-7s %d / %d (%.1f%%)' % (z, zc[z], za[z], 100 * zc[z] / za[z] if za[z] else 0))
    P('  По семействам (нулей / всех закрытых в семействе):')
    fc = collections.Counter(r['семейство'] for r in zeros)
    fa = collections.Counter(r['семейство'] for r in closed)
    for f, c in fc.most_common():
        P('    %-14s %d / %d (%.1f%%)' % (f, c, fa[f], 100 * c / fa[f]))
    # оживание
    rev = [r for r in zeros if r['v7'] >= 3]
    old = [r for r in zeros if r['day'] <= '2026-09-14']
    P('  Ожили к 7 суткам (вышли за 7 суток ≥3): %d из %d (%.1f%%); среди запусков ≤14.09 (7 суток прошли полностью): %d из %d (%.1f%%). Остались с нулём и на 7-е сутки: %d.' % (
        len(rev), len(zeros), 100 * len(rev) / len(zeros), sum(1 for r in old if r['v7'] >= 3), len(old),
        100 * sum(1 for r in old if r['v7'] >= 3) / len(old) if old else 0, sum(1 for r in zeros if r['v7'] == 0)))
    P('  Регистраций за всё время у нулей: %d (в окне %d), ФД %d.' % (sum(r['reg_all'] for r in zeros), sum(r['reg'] for r in zeros), sum(r['fd_all'] for r in zeros)))
    P('')
    P('  Сравнение с базами 1–5 и 6–15 выходов за 3 суток (все закрытые):')
    P('  группа v3   доменов   сайтов   ср. v3   ср. v7   прибавили ≥3 к 7 сут.   с рег. за всё время   рег всё время   рег окно   рег/100 сайтов (окно)   ФД всё время')
    for name, fn in (('0', lambda r: r['v3'] == 0), ('1-5', lambda r: 1 <= r['v3'] <= 5), ('6-15', lambda r: 6 <= r['v3'] <= 15), ('>15', lambda r: r['v3'] > 15)):
        rs = [r for r in closed if fn(r)]
        n = len(rs)
        s = sum(r['sites'] for r in rs)
        P('  %-10s %8d %8d %8.1f %8.1f %18d (%4.1f%%) %16d (%4.1f%%) %13d %10d %20.3f %14d' % (
            name, n, s, sum(r['v3'] for r in rs) / n, sum(r['v7'] for r in rs) / n,
            sum(1 for r in rs if r['v7'] - r['v3'] >= 3), 100 * sum(1 for r in rs if r['v7'] - r['v3'] >= 3) / n,
            sum(1 for r in rs if r['reg_all'] > 0), 100 * sum(1 for r in rs if r['reg_all'] > 0) / n,
            sum(r['reg_all'] for r in rs), sum(r['reg'] for r in rs), 100 * sum(r['reg'] for r in rs) / s, sum(r['fd_all'] for r in rs)))
    # концентрация нулей в пулах с выходом <5%: основной набор
    P('')
    P('  Сидят ли нули в пулах с выходом <5%? Основной набор; для каждого домена — выход соседей по пулу (Σ вышли за 3 / Σ сайтов остальных доменов пула), только пулы с ≥2 доменами.')
    mp = collections.defaultdict(list)
    for r in main:
        mp[r['pool']].append(r)
    cand = []
    for r in main:
        v = mp[r['pool']]
        if len(v) < 2:
            continue
        s = sum(x['sites'] for x in v if x is not r)
        r['mates'] = sum(x['v3'] for x in v if x is not r) / s
        cand.append(r)
    z_main = [r for r in main if r['v3'] == 0]
    z_cand = [r for r in cand if r['v3'] == 0]
    P('  Нулей в основном наборе: %d, из них в пулах с ≥2 доменами: %d (остальные — одни в своём пуле, проверить нельзя). Доменов с известным выходом соседей: %d.' % (
        len(z_main), len(z_cand), len(cand)))
    if z_cand:
        obs = sum(1 for r in z_cand if r['mates'] < 0.05)
        mean_z = sum(r['mates'] for r in z_cand) / len(z_cand)
        nz = [r for r in cand if r['v3'] > 0]
        mean_nz = sum(r['mates'] for r in nz) / len(nz)
        share_all = sum(1 for r in cand if r['mates'] < 0.05) / len(cand)
        P('  Нули: соседи с выходом <5%% у %d из %d (%.0f%%), средний выход соседей %.1f%%; у остальных доменов соседи <5%% в %.0f%% случаев, средний выход соседей %.1f%%.' % (
            obs, len(z_cand), 100 * obs / len(z_cand), 100 * mean_z, 100 * share_all, 100 * mean_nz))
        # permutation within day
        random.seed(1)
        byday = collections.defaultdict(list)
        for r in cand:
            byday[r['day']].append(r)
        nz_by_day = collections.Counter(r['day'] for r in z_cand)
        cnt = 0
        cnt_mean = 0
        for _ in range(NPERM):
            tot = 0
            sm = 0.0
            for d, k in nz_by_day.items():
                pick = random.sample(byday[d], k)
                tot += sum(1 for r in pick if r['mates'] < 0.05)
                sm += sum(r['mates'] for r in pick)
            if tot >= obs:
                cnt += 1
            if sm / len(z_cand) <= mean_z:
                cnt_mean += 1
        P('  Перестановка метки «нуль» между доменами внутри дня запуска (%d раз): P(число нулей с соседями <5%% ≥ %d) = %.4f; P(средний выход соседей ≤ %.1f%%) = %.4f.' % (
            NPERM, obs, cnt / NPERM, 100 * mean_z, cnt_mean / NPERM))
        conc = {'n': len(z_cand), 'lt5': obs, 'mean_z': mean_z, 'mean_nz': mean_nz, 'p_cnt': cnt / NPERM, 'p_mean': cnt_mean / NPERM}
        P('  Нули основного набора и их соседи:')
        for r in sorted(z_cand, key=lambda r: r['mates']):
            v = mp[r['pool']]
            P('    %-21s %-7s %s набор=%-32s соседей %d, их выход %.1f%%, их рег в окне %d' % (
                r['домен'], r['z'], r['day'], r['набор контента'][:32], len(v) - 1, 100 * r['mates'], sum(x['reg'] for x in v if x is not r)))
    top = {'n3': top3, 'days': ', '.join(d[5:].replace('-', '.')[3:] + '.' + d[5:7] for d, c in days.most_common(3)),
           'share_dom': 100 * sum(alld[d] for d, c in days.most_common(3)) / len(closed), 'buzz': (zc['buzz'], za['buzz'])}
    return zeros, rev, (conc if z_cand else None), top


# ----------------------------------------------------------------------------
def main():
    global TEE
    TEE = Tee(OUT)
    rows = load()
    P('Гипотеза №10: правило первого дня — «вышли за 1 сутки» ≤5 из 150 → регистраций в окне не будет; счётчик = уровень, не скорость; нули не оживают')
    P('Файл: %s' % SRC)
    P('Строк (доменов) всего: %d' % len(rows))
    P('')
    main_rows = filter_main(rows)
    P('Оговорка о счётчике: «вышли за 1 сутки» в своде считается от переобхода каждого сайта и включает 56 сайтов второй волны; первые сутки первой волны заканчиваются к концу 2-го календарного дня — на утро 2-го дня оператор видит меньше выходов, чем записано в v1. Поэтому операционное правило пометит не меньше доменов, чем группа v1≤5 здесь; верхнюю границу потерь даёт перебор до ≤10.')
    part_context(main_rows)
    E, pools, with_reg, res = part_rule(main_rows)
    n_le5_nc = part_repeat_with_nocontent(rows)
    r1, r2, r3, r4 = part_speed(main_rows)
    zeros, rev, conc, top = part_zeros(rows, main_rows)

    # --- итоговые числа для вывода
    le5 = [r for r in main_rows if r['v1'] <= 5]
    o5 = res['o5']
    e5 = res['e5']
    tot_reg = sum(r['reg'] for r in main_rows)
    tot_fd = sum(r['fd'] for r in main_rows)
    fd5 = sum(r['fd_all'] for r in le5)
    ra5 = sum(r['reg_all'] for r in le5)
    zt = res['zone'].get('team', (0, 0, 0.0))
    zl = res['zone'].get('lol', (0, 0, 0.0))
    c5 = res['catch']
    P('')
    P('=' * 110)
    P('ВЫВОД')
    P('=' * 110)
    P('1. Правило первого дня. В основном наборе (%d доменов: окно закрыто, две волны, набор контента записан) домены, у которых за первые сутки вышло не больше 5 сайтов, — это %d доменов (%.0f%%), %d сайтов. Регистраций в окне 3 суток у них %d; по своим пулам «набор контента + день» ожидалось %.1f, O/E = %s. Перестановка счётчика внутри пула: под случайностью у этой группы было бы в среднем %.1f регистраций (95%% интервал %d–%d), p = %.4f.' % (
        len(main_rows), len(le5), 100 * len(le5) / len(main_rows), sum(r['sites'] for r in le5), o5, e5, fmt_oe(o5, e5),
        res['null_mean'], res['null_lo'], res['null_hi'], res['p_perm']))
    P('   По зонам внутри страты пул + зона: team — %d доменов v1≤5, O = %d при E = %.1f (O/E %s); lol — %d доменов, O = %d при E = %.1f (O/E %s). То есть это не тень зоны .buzz: в обеих больших зонах помеченные домены пусты.' % (
        zt[0], zt[1], zt[2], fmt_oe(zt[1], zt[2]), zl[0], zl[1], zl[2], fmt_oe(zl[1], zl[2])))
    n45 = c5['4-5'][0]
    n03 = sum(1 for r in main_rows if r['v1'] <= 3)
    P('2. Цена правила при пороге ≤5: потеряно %d из %d регистраций в окне (%.1f%%), %d из %d за всё время, ФД %d. Помеченные подрастают, но не догоняют: группа 4–5 к 3-м суткам имеет в среднем %.1f вышедших сайтов, к 7-м %.1f (≈%.0f%% сайтов против %.0f%% у группы >10), и регистраций у неё нет и за всё время (0 у %d доменов; у ≤3 — 1 на %d доменов). Отсечка по медианной задержке ≥2 суток (или без поиска вовсе) помечает %d доменов с O = %d при E = %.1f (p = %.4f), то есть работает так же, но её нельзя применить утром 2-го дня — она известна только после факта.' % (
        o5, tot_reg, 100 * o5 / tot_reg, ra5, sum(r['reg_all'] for r in main_rows), fd5,
        c5['4-5'][1], c5['4-5'][2], 100 * c5['4-5'][2] / 206, 100 * c5['>10'][2] / 206, n45, n03,
        res['delay_flag_n'], res['delay_o'], res['delay_e'], res['delay_p']))
    P('3. Скорость при равном уровне выхода ничего не добавляет. Отношение O/E быстрых к медленным: терцили %.2f (страта пул × блок часа, перестановочный p = %.3f; знаковый критерий %d:%d, p = %.3f) и %.2f (страта пул, p = %.3f; знаковый %d:%d, p = %.3f); половины %.2f (пул × блок, p = %.3f) и %.2f (пул, p = %.3f). Средний терциль при этом выше обоих крайних (O/E ≈1,2) — это шум, а не тренд. Минимальное различимое отношение ≈%.2f× по терцилям и ≈%.2f× по половинам: большого эффекта скорости нет, эффект до ~1,3× на этом объёме не исключить. Грубый эффект «задержка 0 → больше регистраций» (без страты: 0,93 против 0,62 и 0,33 рег на 100 вышедших сайтов) — тень пула: быстрые домены сидят в лучших наборах и днях, внутри пула при ожидании по вышедшим сайтам он исчезает.' % (
        r1['ratio'], r1['p_ratio'], r1['wins'], r1['losses'], r1['p_sign'], r2['ratio'], r2['p_ratio'], r2['wins'], r2['losses'], r2['p_sign'],
        r3['ratio'], r3['p_ratio'], r4['ratio'], r4['p_ratio'], r1['mdr'], r3['mdr']))
    old_z = [r for r in zeros if r['day'] <= '2026-09-14']
    P('4. Нули: %d закрытых баз с нулём выходов к 3-м суткам; к 7-м суткам ≥3 выходов набрали %d (%.0f%%; среди запусков до 14.09, где 7 суток прошли полностью, — %d из %d), регистраций за всё время 0 у всех, ФД 0. Списание на 4-й день ничего не теряет.' % (
        len(zeros), len(rev), 100 * len(rev) / len(zeros), sum(1 for r in old_z if r['v7'] >= 3), len(old_z)))
    if conc:
        P('   Где сидят нули: %d из %d — на трёх днях (%s; на них лишь %.0f%% закрытых доменов), .buzz даёт %d из %d. Соседи нулей по пулу выходят хуже среднего (у %d из %d нулей выход соседей <5%%, средний %.1f%% против %.1f%% у остальных доменов), но внутри дня это не отличимо от случайности (перестановка метки «нуль» внутри дня: p = %.2f по числу пулов <5%%, p = %.2f по среднему выходу соседей). Так что «нуль сидит в пустом пуле» показано только на уровне дня запуска: нули — это плохие дни (и .buzz), а не особые пулы внутри дня; на своде это не решается точнее, пулов с нулями мало (%d).' % (
            top['n3'], len(zeros), top['days'], top['share_dom'], top['buzz'][0], top['buzz'][1],
            conc['lt5'], conc['n'], 100 * conc['mean_z'], 100 * conc['mean_nz'], conc['p_cnt'], conc['p_mean'], conc['n']))
    P('')
    P('Что с этим делать. Правило дешёвое и проверяемо на уже запущенных данных: домен, у которого к концу первых суток вышло ≤5 сайтов, можно не вести дальше — не ставить вторую волну (за август–сентябрь по основному набору это %d доменов и %d слотов квоты, с «не записан» — %d слотов) и списывать на 4-й день домены с нулём выходов. Но выигрыш — не регистрации (эти домены их и так не дают: %d из %d), а только экономия квоты Вебмастера и внимания; главный рычаг остаётся набор контента и день. Прежде чем внедрять, проверить две вещи на 1–2 новых запусках: (а) в своде нет счётчика «на утро 2-го дня» — «вышли за 1 сутки» включает вторую волну и весь следующий день, поэтому живое правило пометит не меньше доменов, чем здесь; записать выходы на утро дня 2 и сверить с v1 (перебор порогов до ≤10 показывает, что даже при вдвое большем захвате потери ≤%d регистраций из %d, ≈2%%, и 1 ФД), либо ставить вторую волну на день позже, когда v1 известен полностью; (б) регистрации второй волны отдельно не видны, но суммарно у помеченных ≤%d, так что верхняя граница потерь ясна.' % (
        len(le5), 56 * len(le5), 56 * n_le5_nc, o5, tot_reg, sum(r['reg'] for r in main_rows if r['v1'] <= 10), tot_reg, o5))
    TEE.flush()


if __name__ == '__main__':
    main()

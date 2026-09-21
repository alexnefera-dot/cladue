#!/usr/bin/env python3
"""
Гипотеза №20. Внутри семейства content-дата два признака из имени набора
управляют результатом при одинаковых дне запуска, зоне, страницах и оформлении:
  (1) буква генерации после даты (content-2026-09-14c-…, 17b-…): повторные
      генерации той же даты (b, c) дают выход в 1,5–2 раза и регистраций в 3–5 раз
      больше первой генерации (без буквы);
  (2) разрыв «день запуска − дата в имени»: партия, поставленная через ≥2 суток
      после даты в имени, хуже партии, поставленной на следующий день.

Что считаем.
  Из имени набора: дата, буква (нет / b / c), страниц, оформление, номер варианта
  (-1/-2/-3/-8/-9 или нет), хвост _NN (экземпляр). Генерация = имя без хвоста _NN.
  Разрыв = день запуска − дата из имени (в сутках).
  Выход домена = «вышли за 3 суток» / «сайтов в окне» (только окно закрыто = да).
  Деньги = «регистраций в окне 3 суток», «ФД в окне 3 суток» на 100 сайтов.

Как проверяем.
  Фильтры: семейство content-дата; окно закрыто = да (запуски 19–21.09 — открыты,
  исключены; 23 домена 14b-oform-1 от 21.09 оставлены только для прогноза);
  выбросы 3615.team и 3286.team и «КОНТЕНТ НЕ ЗАПИСАН» в семействе не встречаются
  (проверяется и печатается). Домены 18.09 с «дней» = 1 (150 сайтов) оставлены —
  выход считается на «сайтов в окне» — и отдельно проверено без них.

  Контраст 1 (буква). Страта = день запуска × зона × страниц × оформление × дата
  в имени (так буква не смешана с разрывом: у всех генераций страты один разрыв).
  Берутся страты с ≥2 разными буквами. E домена = доля выхода страты × сайтов в
  окне; O = вышли за 3 суток. O/E по группам нет / b / c суммарно по стратам,
  а также отношение O/E(c) / O/E(нет). Перестановка буквы между доменами внутри
  страты 10 000 раз (random.seed(1)): p = доля перестановок, где статистика не
  ниже наблюдённой. Деньги: то же с E = доля регистраций страты × сайтов, плюс
  точный биномиальный дележ регистраций страты пропорционально сайтам (свёртка
  по стратам). Чувствительность: (а) страта без даты в имени — буквально как в
  плане (буква смешана с разрывом); (б) страта ещё и с номером варианта
  (-1/-2/…), потому что «нет буквы» на 15.09 — это в основном варианты 8/9,
  которые в реестре уже отмечены как худшие; (в) без доменов с «дней» = 1.
  Контроль: распределение разрыва по буквам внутри страт.

  Контраст 2 (разрыв). Пары «генерация × зона», где у генерации есть закрытые
  запуски и с разрывом ≤1 (свежие), и с разрывом ≥2 (старые). Дневной
  коэффициент d(день, зона, страниц) = доля выхода по всем генерациям с разрывом
  ≤1 в этот день. E старого домена = доля выхода генерации на свежих запусках в
  этой зоне × d(старый день) / d(свежий день, взвешенно по свежим доменам) ×
  сайтов в окне (двойная разность: день вычтен). Суммы O и E по старым доменам,
  O/E; знаковый критерий по парам (точный биномиальный); перестановка метки
  «старый» между доменами одной пары 10 000 раз с фиксированными E доменов
  (p = доля перестановок, где O/E не выше наблюдённого). Чувствительность:
  дневной коэффициент без проверяемой генерации (leave-one-out) и вовсе без
  поправки на день. Деньги: регистраций на 100 сайтов у свежих и старых внутри
  пар, точный биномиальный дележ пропорционально сайтам и пропорционально E.
  Отдельно: разрыв 0 против 1 (описательно — они не отделимы от дня и
  генерации), 14b-oform-1 разрыв 3 → 4, прогноз для 14b-oform-1 от 21.09.

Критерии из постановки: буква — O/E(c) ≥ 1,5 при p < 0,01, O/E регистраций ≥ 2,
b между «нет» и «c», 17b против 17 — тот же знак; разрыв — O/E(≥2) ≤ 0,8 при
p < 0,05, знак в ≥ 2/3 пар, рег/100 сайтов у старых ≤ 0,6 от свежих.
"""
import collections
import csv
import datetime
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h20_content_gen_letter_gap.txt')
OUTLIERS = ('3615.team', '3286.team')
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
FAMILY = 'content-дата'
NPERM = 10000
SEED = 1
FORECAST_GEN = 'content-2026-09-14b-7str-oform-1'
FORECAST_DAY = '2026-09-21'


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


TEE = Tee(OUT)


def p(*args):
    TEE.write(' '.join(str(a) for a in args) + '\n')


def inum(s, default=0):
    s = (s or '').strip()
    return default if s == '' else int(float(s))


def fmt_ratio(o, e):
    return '%.2f' % (o / e) if e > 0 else '—'


def pct(a, b):
    return '%.3f' % (a / b) if b > 0 else '—'


def per100(a, b):
    return '%.3f' % (100.0 * a / b) if b > 0 else '—'


def binom_pmf(n, k, pr):
    if pr <= 0:
        return 1.0 if k == 0 else 0.0
    if pr >= 1:
        return 1.0 if k == n else 0.0
    return math.comb(n, k) * pr ** k * (1 - pr) ** (n - k)


def convolve_binoms(pairs):
    """Распределение суммы независимых Bin(n_i, p_i). pairs = [(n_i, p_i)]."""
    dist = [1.0]
    for n, pr in pairs:
        if n == 0:
            continue
        pm = [binom_pmf(n, k, pr) for k in range(n + 1)]
        new = [0.0] * (len(dist) + n)
        for i, a in enumerate(dist):
            if a == 0:
                continue
            for k, b in enumerate(pm):
                new[i + k] += a * b
        dist = new
    return dist


def tail_ge(dist, x):
    return sum(dist[x:]) if x < len(dist) else 0.0


def tail_le(dist, x):
    return sum(dist[:x + 1])


def sign_test_le(n_less, n_total):
    """Точный биномиальный: P(X >= n_less | n_total, 0.5)."""
    return sum(math.comb(n_total, k) for k in range(n_less, n_total + 1)) / 2 ** n_total


NAME_RE = re.compile(r'^content-(\d{4}-\d{2}-\d{2})([a-z]?)-(\d+)str(?:-oform(?:-(\d+))?)?(?:_(\d+))?$')


def parse_name(name):
    m = NAME_RE.match(name)
    if not m:
        return None
    date_s, letter, pages, variant, nn = m.groups()
    gen = name[:name.rfind('_')] if nn is not None else name
    return {
        'date': datetime.date.fromisoformat(date_s),
        'letter': letter or 'нет',
        'pages': int(pages),
        'variant': variant or '',
        'nn': nn,
        'gen': gen,
    }


# ------------------------------------------------------------------ загрузка
with open(SRC, encoding='utf-8', newline='') as f:
    rows_all = list(csv.DictReader(f))

p('=' * 100)
p('Гипотеза №20: буква генерации (b/c) и разрыв «день запуска − дата в имени» в семействе content-дата')
p('Файл:', os.path.relpath(SRC, REPO), '| строк (доменов):', len(rows_all))
p('=' * 100)

fam = [r for r in rows_all if r['семейство'] == FAMILY]
p('\nИСКЛЮЧЕНИЯ')
p('  не семейство content-дата: исключено %d, осталось %d' % (len(rows_all) - len(fam), len(fam)))
n_out = sum(1 for r in fam if r['домен'] in OUTLIERS)
p('  выбросы 3615.team / 3286.team в семействе: %d (они в семействах NEW и тест — не участвуют)' % n_out)
fam = [r for r in fam if r['домен'] not in OUTLIERS]
n_noc = sum(1 for r in fam if r['набор контента'] == NOC)
p('  «КОНТЕНТ НЕ ЗАПИСАН» в семействе: %d (это семейство «не записан», сюда не попадает)' % n_noc)
fam = [r for r in fam if r['набор контента'] != NOC]

doms = []
bad = 0
for r in fam:
    info = parse_name(r['набор контента'])
    if info is None:
        bad += 1
        p('  НЕ РАЗОБРАНО имя:', r['набор контента'])
        continue
    d = dict(info)
    d['domain'] = r['домен']
    d['zone'] = r['зона']
    d['day_s'] = r['день запуска']
    d['day'] = datetime.date.fromisoformat(r['день запуска'])
    d['gap'] = (d['day'] - d['date']).days
    d['closed'] = r['окно закрыто'] == 'да'
    d['days'] = inum(r['дней'])
    d['oform'] = r['оформление'] or 'пусто'
    d['pages_col'] = r['страниц']
    d['sites'] = inum(r['сайтов'])
    d['sites_w'] = inum(r['сайтов в окне'])
    d['exit3'] = inum(r['вышли за 3 суток'])
    d['reg'] = inum(r['регистраций в окне 3 суток'])
    d['fd'] = inum(r['ФД в окне 3 суток'])
    d['search_w'] = inum(r['кликов из поиска в окне'])
    d['sites_search_all'] = inum(r['сайтов с поиском'])
    d['reg_all'] = inum(r['регистраций'])
    doms.append(d)
p('  имён набора не разобрано: %d' % bad)

open_doms = [d for d in doms if not d['closed']]
closed = [d for d in doms if d['closed']]
p('  окно закрыто = нет (запуски 19–21.09): исключено %d, осталось %d' % (len(open_doms), len(closed)))
fc = [d for d in open_doms if d['gen'] == FORECAST_GEN and d['day_s'] == FORECAST_DAY]
p('    из них %d доменов %s от %s оставлены только для блока «прогноз»' % (len(fc), FORECAST_GEN, FORECAST_DAY))
n_day1 = sum(1 for d in closed if d['days'] == 1)
p('  домены с «дней» = 1 среди закрытых: %d (все 18.09, 150 сайтов) — оставлены, выход на «сайтов в окне»; '
  'проверка без них ниже' % n_day1)
n_sw = sum(1 for d in closed if d['sites_w'] != d['sites'])
p('  у закрытых «сайтов в окне» ≠ «сайтов»: %d доменов' % n_sw)
p('  сверка: страниц из имени ≠ колонка «страниц»: %d; оформление из имени ≠ колонка: %d' % (
    sum(1 for d in closed if str(d['pages']) != d['pages_col']),
    sum(1 for d in closed if ('-oform' in d['gen']) != (d['oform'] == 'оформлено'))))

# ------------------------------------------------------------ описательные таблицы


def agg(items, keyf, sites_key='sites_w'):
    out = collections.OrderedDict()
    for d in items:
        k = keyf(d)
        a = out.setdefault(k, collections.Counter())
        a['n'] += 1
        a['sites'] += d[sites_key]
        a['exit'] += d['exit3']
        a['reg'] += d['reg']
        a['fd'] += d['fd']
        a['search'] += d['search_w']
    return out


def print_table(title, table, head):
    p('\n' + title)
    p('  %-52s %6s %7s %6s %7s %5s %8s %5s' % (head, 'домен', 'сайтов', 'вышли', 'выход', 'рег', 'рег/100', 'ФД'))
    for k, a in table.items():
        p('  %-52s %6d %7d %6d %7s %5d %8s %5d' % (
            k, a['n'], a['sites'], a['exit'], pct(a['exit'], a['sites']), a['reg'], per100(a['reg'], a['sites']), a['fd']))


p('\n' + '-' * 100)
p('1. ОПИСАНИЕ: закрытые домены семейства content-дата (n = %d, сайтов %d, регистраций в окне %d, ФД %d)' % (
    len(closed), sum(d['sites_w'] for d in closed), sum(d['reg'] for d in closed), sum(d['fd'] for d in closed)))
p('-' * 100)

t = agg(sorted(closed, key=lambda d: (d['day_s'], d['zone'], d['gen'])),
        lambda d: '%s %-6s %-36s разр=%d' % (d['day_s'], d['zone'], d['gen'].replace('content-2026-09-', ''), d['gap']))
print_table('1а. Генерация × день запуска × зона (имена сокращены: content-2026-09- опущено)', t, 'день зона генерация')

t = agg(sorted(closed, key=lambda d: ('нет', 'b', 'c').index(d['letter'])), lambda d: 'буква: ' + d['letter'])
print_table('1б. По букве генерации (все дни, без страты — только описание)', t, 'группа')
t = agg(sorted(closed, key=lambda d: d['gap']), lambda d: 'разрыв: %d' % d['gap'])
print_table('1в. По разрыву «день запуска − дата в имени» (без страты — только описание)', t, 'группа')
t = agg(sorted(closed, key=lambda d: (d['date'], d['letter'])), lambda d: 'дата %s буква %s' % (d['date'], d['letter']))
print_table('1г. Дата в имени × буква', t, 'группа')

# --------------------------------------------------------------- контраст 1: буква


def letter_contrast(items, keyf, title, nperm=NPERM, show_strata=True):
    strata = collections.OrderedDict()
    for d in items:
        strata.setdefault(keyf(d), []).append(d)
    strata = collections.OrderedDict((k, v) for k, v in strata.items() if len(set(x['letter'] for x in v)) >= 2)
    p('\n' + title)
    if not strata:
        p('  нет страт с двумя и более буквами — контраст не строится')
        return None
    # E по стратам
    recs = []  # (stratum, letter, O_exit, E_exit, O_reg, E_reg, sites)
    for k, v in strata.items():
        s_sites = sum(x['sites_w'] for x in v)
        s_exit = sum(x['exit3'] for x in v)
        s_reg = sum(x['reg'] for x in v)
        r_exit = s_exit / s_sites
        r_reg = s_reg / s_sites
        for x in v:
            recs.append((k, x['letter'], x['exit3'], r_exit * x['sites_w'], x['reg'], r_reg * x['sites_w'], x['sites_w'], x))
    if show_strata:
        p('  Страты (≥2 буквы) и генерации внутри:')
        for k, v in strata.items():
            s_sites = sum(x['sites_w'] for x in v)
            s_exit = sum(x['exit3'] for x in v)
            s_reg = sum(x['reg'] for x in v)
            p('   %s: доменов %d, сайтов %d, выход %s, рег %d' % (k, len(v), s_sites, pct(s_exit, s_sites), s_reg))
            gens = agg(sorted(v, key=lambda x: x['gen']), lambda x: x['gen'])
            for g, a in gens.items():
                e_exit = s_exit / s_sites * a['sites']
                e_reg = s_reg / s_sites * a['sites']
                gaps = sorted(set(x['gap'] for x in v if x['gen'] == g))
                p('      %-40s буква %-3s разрыв %s  доменов %3d сайтов %5d вышли %4d выход %s O/E %s | рег %2d O/E %s' % (
                    g.replace('content-2026-09-', ''), v[[x['gen'] for x in v].index(g)]['letter'],
                    ','.join(map(str, gaps)), a['n'], a['sites'], a['exit'], pct(a['exit'], a['sites']),
                    fmt_ratio(a['exit'], e_exit), a['reg'], fmt_ratio(a['reg'], e_reg)))

    def sums(letters):
        acc = {L: [0, 0, 0.0, 0, 0.0, 0] for L in ('нет', 'b', 'c')}
        for (k, _, oe, ee, orr, er, s, x), L in zip(recs, letters):
            a = acc[L]
            a[0] += 1
            a[1] += s
            a[2] += ee
            a[3] += oe
            a[4] += er
            a[5] += orr
        return acc

    obs_letters = [r[1] for r in recs]
    acc = sums(obs_letters)
    # знаки попарно внутри страт: выход группы буквы в страте
    signs = collections.Counter()
    for k, v in strata.items():
        rate = {}
        for L in ('нет', 'b', 'c'):
            s = sum(x['sites_w'] for x in v if x['letter'] == L)
            if s:
                rate[L] = sum(x['exit3'] for x in v if x['letter'] == L) / s
        for hi, lo in (('c', 'нет'), ('b', 'нет'), ('c', 'b')):
            if hi in rate and lo in rate:
                signs[(hi, lo, rate[hi] > rate[lo])] += 1
    p('  Знаки по стратам (выход группы выше?): ' + '; '.join(
        '%s > %s в %d из %d' % (hi, lo, signs[(hi, lo, True)], signs[(hi, lo, True)] + signs[(hi, lo, False)])
        for hi, lo in (('c', 'нет'), ('b', 'нет'), ('c', 'b')) if signs[(hi, lo, True)] + signs[(hi, lo, False)]))
    p('  Итог по группам буквы (E = доля страты × сайтов):')
    p('   %-5s %6s %7s %6s %7s %7s | %4s %6s %7s %8s' % ('буква', 'домен', 'сайтов', 'вышли', 'E вышли', 'O/E', 'рег', 'E рег', 'O/E', 'рег/100'))
    for L in ('нет', 'b', 'c'):
        a = acc[L]
        p('   %-5s %6d %7d %6d %7.1f %7s | %4d %6.2f %7s %8s' % (
            L, a[0], a[1], a[3], a[2], fmt_ratio(a[3], a[2]), a[5], a[4], fmt_ratio(a[5], a[4]), per100(a[5], a[1])))

    def stats(a):
        oe = {L: (a[L][3] / a[L][2] if a[L][2] > 0 else float('nan')) for L in a}
        oer = {L: (a[L][5] / a[L][4] if a[L][4] > 0 else float('nan')) for L in a}
        return oe, oer

    oe0, oer0 = stats(acc)

    def ratio(x, y):
        return x / y if (y and y > 0 and not math.isnan(y) and not math.isnan(x)) else float('nan')

    obs = {
        'O/E выход c': oe0['c'], 'O/E выход b': oe0['b'], 'O/E выход нет': oe0['нет'],
        'c / нет (выход)': ratio(oe0['c'], oe0['нет']), 'b / нет (выход)': ratio(oe0['b'], oe0['нет']),
        'c / b (выход)': ratio(oe0['c'], oe0['b']),
        'O/E рег c': oer0['c'], 'O/E рег b': oer0['b'],
    }
    # перестановки буквы внутри страты
    random.seed(SEED)
    by_str = collections.OrderedDict()
    for i, r in enumerate(recs):
        by_str.setdefault(r[0], []).append(i)
    cnt = {k: 0 for k in obs}
    valid = {k: 0 for k in obs}
    for _ in range(nperm):
        letters = list(obs_letters)
        for idx in by_str.values():
            sub = [letters[i] for i in idx]
            random.shuffle(sub)
            for i, L in zip(idx, sub):
                letters[i] = L
        a = sums(letters)
        oe, oer = stats(a)
        vals = {
            'O/E выход c': oe['c'], 'O/E выход b': oe['b'], 'O/E выход нет': oe['нет'],
            'c / нет (выход)': ratio(oe['c'], oe['нет']), 'b / нет (выход)': ratio(oe['b'], oe['нет']),
            'c / b (выход)': ratio(oe['c'], oe['b']),
            'O/E рег c': oer['c'], 'O/E рег b': oer['b'],
        }
        for k in obs:
            if math.isnan(obs[k]) or math.isnan(vals[k]):
                continue
            valid[k] += 1
            if k == 'O/E выход нет':
                if vals[k] <= obs[k]:
                    cnt[k] += 1
            elif vals[k] >= obs[k]:
                cnt[k] += 1
    p('  Перестановка буквы внутри страты, %d раз (p = доля перестановок со статистикой не ниже наблюдённой;'
      ' для «нет» — не выше):' % nperm)
    for k in obs:
        if math.isnan(obs[k]):
            p('   %-18s наблюдено —  (группы нет в этих стратах)' % k)
        else:
            p('   %-18s наблюдено %.2f   p = %.4f' % (k, obs[k], cnt[k] / valid[k] if valid[k] else float('nan')))
    # точный биномиальный дележ регистраций
    for L in ('c', 'b'):
        pairs = []
        o = 0
        for k, v in strata.items():
            R = sum(x['reg'] for x in v)
            S = sum(x['sites_w'] for x in v)
            SL = sum(x['sites_w'] for x in v if x['letter'] == L)
            if SL == 0 or SL == S:
                continue
            o += sum(x['reg'] for x in v if x['letter'] == L)
            pairs.append((R, SL / S))
        if pairs:
            dist = convolve_binoms(pairs)
            exp = sum(n * pr for n, pr in pairs)
            p('  Точный биномиальный дележ регистраций страт пропорционально сайтам, буква %s: наблюдено %d, ожидание %.2f, '
              'P(X ≥ набл.) = %.4f' % (L, o, exp, tail_ge(dist, o)))
    # контроль: разрыв по буквам
    gaps = collections.defaultdict(collections.Counter)
    for r in recs:
        gaps[r[1]][r[7]['gap']] += r[7]['sites_w']
    p('  Контроль смешения с разрывом (сайтов по разрыву внутри страт): ' + '; '.join(
        '%s: %s' % (L, dict(sorted(gaps[L].items()))) for L in ('нет', 'b', 'c') if gaps[L]))
    return obs, {k: (cnt[k] / valid[k] if valid[k] else float('nan')) for k in obs}, acc


p('\n' + '-' * 100)
p('2. КОНТРАСТ 1 — БУКВА ГЕНЕРАЦИИ (нет / b / c) внутри страты')
p('-' * 100)

key_main = lambda d: '%s %s %dстр %s дата %s' % (d['day_s'], d['zone'], d['pages'], d['oform'], d['date'])
res_letter = letter_contrast(closed, key_main,
                             '2а. ОСНОВНОЙ: страта = день × зона × страниц × оформление × дата в имени (разрыв одинаков внутри страты)')

key_plan = lambda d: '%s %s %dстр %s' % (d['day_s'], d['zone'], d['pages'], d['oform'])
res_letter_plan = letter_contrast(closed, key_plan,
                                  '2б. ЧУВСТВИТЕЛЬНОСТЬ: страта без даты в имени (буквально по плану; буква смешана с разрывом)',
                                  show_strata=False)

key_var = lambda d: '%s %s %dстр %s дата %s вар %s' % (d['day_s'], d['zone'], d['pages'], d['oform'], d['date'], d['variant'] or '—')
res_letter_var = letter_contrast(closed, key_var,
                                 '2в. ЧУВСТВИТЕЛЬНОСТЬ: страта ещё и с номером варианта (-1/-2/-8/-9): буква при одинаковом варианте',
                                 show_strata=True)

res_letter_day2 = letter_contrast([d for d in closed if d['days'] >= 2], key_main,
                                  '2г. ЧУВСТВИТЕЛЬНОСТЬ: без доменов с «дней» = 1 (выпадает страта 18.09 .lol с 17b)',
                                  show_strata=False)

# 17b против 17 отдельно
p('\n2д. 17b против 17-oform-2 на 18.09 (единственная пара b/нет с одной датой в имени):')
for z in ('lol', 'team'):
    sub = [d for d in closed if d['day_s'] == '2026-09-18' and d['zone'] == z and d['date'] == datetime.date(2026, 9, 17)]
    if not sub:
        continue
    t = agg(sorted(sub, key=lambda d: d['gen']), lambda d: d['gen'])
    for g, a in t.items():
        p('   %-6s %-40s доменов %3d сайтов %5d выход %s рег %d (рег/100 %s) ФД %d' % (
            z, g, a['n'], a['sites'], pct(a['exit'], a['sites']), a['reg'], per100(a['reg'], a['sites']), a['fd']))

# Деньги «удачного дня» 15.09
p('\n2е. Регистрации 15.09 по генерациям (доля 14c в деньгах «удачного дня»):')
sub = [d for d in closed if d['day_s'] == '2026-09-15']
t = agg(sorted(sub, key=lambda d: (d['zone'], d['gen'])), lambda d: '%s %s' % (d['zone'], d['gen']))
tot_reg = sum(a['reg'] for a in t.values())
c_reg = sum(a['reg'] for k, a in t.items() if '14c' in k)
c_n = sum(a['n'] for k, a in t.items() if '14c' in k)
for k, a in t.items():
    p('   %-48s доменов %3d сайтов %5d выход %s рег %2d ФД %d' % (k, a['n'], a['sites'], pct(a['exit'], a['sites']), a['reg'], a['fd']))
p('   всего 15.09: %d регистраций на %d доменах; из них на 14c: %d на %d доменах' % (tot_reg, len(sub), c_reg, c_n))

# --------------------------------------------------------------- контраст 2: разрыв
p('\n' + '-' * 100)
p('3. КОНТРАСТ 2 — РАЗРЫВ «день запуска − дата в имени» (≤1 свежие против ≥2 старые) внутри генерации × зоны')
p('-' * 100)

# дневные коэффициенты по свежим генерациям
def day_coef_table(items, exclude_gen=None):
    acc = collections.defaultdict(lambda: [0, 0])
    for d in items:
        if d['gap'] <= 1 and (exclude_gen is None or d['gen'] != exclude_gen):
            a = acc[(d['day_s'], d['zone'], d['pages'])]
            a[0] += d['exit3']
            a[1] += d['sites_w']
    return {k: v[0] / v[1] for k, v in acc.items() if v[1] > 0}


dc = day_coef_table(closed)
p('\n3а. Дневные коэффициенты d(день, зона, страниц) = выход по генерациям с разрывом ≤1:')
gens_fresh = collections.defaultdict(set)
for d in closed:
    if d['gap'] <= 1:
        gens_fresh[(d['day_s'], d['zone'], d['pages'])].add(d['gen'].replace('content-2026-09-', ''))
for k in sorted(dc):
    n = sum(1 for d in closed if d['gap'] <= 1 and (d['day_s'], d['zone'], d['pages']) == k)
    s = sum(d['sites_w'] for d in closed if d['gap'] <= 1 and (d['day_s'], d['zone'], d['pages']) == k)
    p('   %s %-6s %2dстр  d = %.3f  (доменов %3d, сайтов %5d; генерации: %s)' % (
        k[0], k[1], k[2], dc[k], n, s, ', '.join(sorted(gens_fresh[k]))))


def gap_contrast(items, title, adjust='full', nperm=NPERM, verbose=True):
    """adjust: 'full' — d по всем свежим; 'loo' — без проверяемой генерации; 'none' — без поправки."""
    groups = collections.OrderedDict()
    for d in sorted(items, key=lambda d: (d['date'], d['gen'], d['zone'], d['day_s'])):
        groups.setdefault((d['gen'], d['zone']), []).append(d)
    pairs = []
    for (g, z), v in groups.items():
        fresh = [d for d in v if d['gap'] <= 1]
        old = [d for d in v if d['gap'] >= 2]
        if not fresh or not old:
            continue
        pages = fresh[0]['pages']
        if adjust == 'loo':
            dct = day_coef_table(items, exclude_gen=g)
            fallback = False
            for d in fresh + old:
                if (d['day_s'], d['zone'], pages) not in dct:
                    fallback = True
            if fallback:
                dct = dc
        else:
            dct = dc
        s_f = sum(d['sites_w'] for d in fresh)
        r_f = sum(d['exit3'] for d in fresh) / s_f
        if adjust == 'none':
            d_f = 1.0
        else:
            d_f = sum(dct[(d['day_s'], d['zone'], pages)] * d['sites_w'] for d in fresh) / s_f
        recs = []
        for d in fresh:
            recs.append((d, False, d['exit3'], r_f * d['sites_w']))
        for d in old:
            k = (d['day_s'], d['zone'], pages)
            if adjust == 'none':
                mult = 1.0
            else:
                if k not in dct:
                    continue
                mult = dct[k] / d_f
            recs.append((d, True, d['exit3'], r_f * mult * d['sites_w']))
        pairs.append(((g, z), recs, r_f, d_f, fresh, old, ('loo-fallback' if adjust == 'loo' and fallback else '')))
    p('\n' + title)
    if verbose:
        p('   %-34s %-6s | свежие: разр  дом  сайтов выход | старые: разр  дом сайтов выход  E-выход  O/E  | рег св. рег ст.' % ('генерация', 'зона'))
    tot_o = 0
    tot_e = 0.0
    n_less = 0
    n_pairs = 0
    per_pair = []
    for (g, z), recs, r_f, d_f, fresh, old, note in pairs:
        o = sum(r[2] for r in recs if r[1])
        e = sum(r[3] for r in recs if r[1])
        s_old = sum(r[0]['sites_w'] for r in recs if r[1])
        s_f = sum(d['sites_w'] for d in fresh)
        gaps_f = sorted(set(d['gap'] for d in fresh))
        gaps_o = sorted(set(d['gap'] for d in old))
        tot_o += o
        tot_e += e
        n_pairs += 1
        if o / e < 1:
            n_less += 1
        per_pair.append(((g, z), o, e))
        if verbose:
            p('   %-34s %-6s | %-6s %4d %6d %s | %-6s %4d %6d %s %8.1f %5.2f | %3d %3d %s' % (
                g.replace('content-2026-09-', ''), z, ','.join(map(str, gaps_f)), len(fresh), s_f,
                pct(sum(d['exit3'] for d in fresh), s_f),
                ','.join(map(str, gaps_o)), len(old), s_old, pct(o, s_old), e, o / e,
                sum(d['reg'] for d in fresh), sum(d['reg'] for d in old), note))
    if not pairs:
        p('   пар нет')
        return None
    obs = tot_o / tot_e
    p('   ИТОГО старые (разрыв ≥2): пар %d, доменов %d, сайтов %d, вышли %d, ожидание %.1f, O/E = %.3f; пар с O/E < 1: %d из %d '
      '(знаковый критерий, точный: p = %.3f)' % (
          n_pairs, sum(len(o) for _, _, _, _, _, o, _ in pairs), sum(sum(d['sites_w'] for d in o) for _, _, _, _, _, o, _ in pairs),
          tot_o, tot_e, obs, n_less, n_pairs, sign_test_le(n_less, n_pairs)))
    if verbose:
        for label, keyf in (('по разрыву', lambda d: 'разрыв %d' % d['gap']), ('по зоне', lambda d: d['zone']),
                            ('по дате в имени', lambda d: 'дата %s' % d['date'])):
            br = collections.OrderedDict()
            for _, recs, _, _, _, _, _ in pairs:
                for d, is_old, o, e in recs:
                    if is_old:
                        a = br.setdefault(keyf(d), [0, 0, 0, 0.0])
                        a[0] += 1
                        a[1] += d['sites_w']
                        a[2] += o
                        a[3] += e
            p('   старые %s: ' % label + '; '.join('%s — доменов %d, сайтов %d, O/E %.2f' % (k, a[0], a[1], a[2] / a[3])
                                                    for k, a in sorted(br.items())))
    # перестановка метки «старый» внутри пары
    random.seed(SEED)
    cnt = 0
    cnt_sign = 0
    for _ in range(nperm):
        so = 0
        se = 0.0
        nl = 0
        for _, recs, _, _, _, _, _ in pairs:
            labels = [r[1] for r in recs]
            random.shuffle(labels)
            po = sum(r[2] for r, L in zip(recs, labels) if L)
            pe = sum(r[3] for r, L in zip(recs, labels) if L)
            so += po
            se += pe
            if pe > 0 and po / pe < 1:
                nl += 1
        if so / se <= obs:
            cnt += 1
        if nl >= n_less:
            cnt_sign += 1
    p('   Перестановка метки «старый» внутри пары, %d раз: P(O/E ≤ %.3f) = %.4f; P(пар с O/E<1 ≥ %d) = %.4f' % (
        nperm, obs, cnt / nperm, n_less, cnt_sign / nperm))
    return obs, cnt / nperm, n_less, n_pairs, pairs


res_gap = gap_contrast(closed, '3б. ОСНОВНОЙ: E старых = выход генерации на свежих × d(старый день)/d(свежий день) × сайтов', 'full')
res_gap_loo = gap_contrast(closed, '3в. ЧУВСТВИТЕЛЬНОСТЬ: дневной коэффициент без проверяемой генерации (leave-one-out; '
                                   'где иначе нельзя — обычный d, помечено loo-fallback)', 'loo', verbose=True)
res_gap_raw = gap_contrast(closed, '3г. ЧУВСТВИТЕЛЬНОСТЬ: без поправки на день (сырое падение: день + разрыв вместе)', 'none', verbose=False)
res_gap_d2 = gap_contrast([d for d in closed if d['days'] >= 2],
                          '3д. ЧУВСТВИТЕЛЬНОСТЬ: без доменов с «дней» = 1 (выпадают старые запуски 16-7str на 18.09)', 'full', verbose=False)
res_gap_no12 = gap_contrast([d for d in closed if d['date'] != datetime.date(2026, 9, 12)],
                            '3д2. ЧУВСТВИТЕЛЬНОСТЬ: без генераций даты 12.09 (их старые запуски 14.09 почти не вышли, '
                            'а дневной коэффициент 14.09 держится на одной генерации 14-oform-8)', 'full', verbose=False)

# деньги по разрыву внутри пар
p('\n3е. Регистрации внутри пар «генерация × зона» (свежие ≤1 против старых ≥2):')
if res_gap:
    pairs = res_gap[4]
    sf = so = rf = ro = 0
    fdf = fdo = 0
    bin_sites = []
    bin_e = []
    for (g, z), recs, r_f, d_f, fresh, old, _ in pairs:
        s1 = sum(d['sites_w'] for d in fresh)
        s2 = sum(d['sites_w'] for d in old)
        r1 = sum(d['reg'] for d in fresh)
        r2 = sum(d['reg'] for d in old)
        e1 = sum(r[3] for r in recs if not r[1])
        e2 = sum(r[3] for r in recs if r[1])
        sf += s1
        so += s2
        rf += r1
        ro += r2
        fdf += sum(d['fd'] for d in fresh)
        fdo += sum(d['fd'] for d in old)
        bin_sites.append((r1 + r2, s2 / (s1 + s2)))
        bin_e.append((r1 + r2, e2 / (e1 + e2)))
    p('   свежие: доменов %d, сайтов %d, регистраций %d (%s на 100 сайтов), ФД %d' % (
        sum(len(f) for _, _, _, _, f, _, _ in pairs), sf, rf, per100(rf, sf), fdf))
    p('   старые: доменов %d, сайтов %d, регистраций %d (%s на 100 сайтов), ФД %d' % (
        sum(len(o) for _, _, _, _, _, o, _ in pairs), so, ro, per100(ro, so), fdo))
    ratio_reg = (ro / so) / (rf / sf) if rf > 0 and so > 0 else float('nan')
    p('   отношение рег/100 сайтов старые / свежие = %.2f' % ratio_reg)
    dist = convolve_binoms(bin_sites)
    p('   точный дележ регистраций пары пропорционально сайтам: ожидание старых %.2f, наблюдено %d, P(X ≤ набл.) = %.4f' % (
        sum(n * pr for n, pr in bin_sites), ro, tail_le(dist, ro)))
    dist = convolve_binoms(bin_e)
    p('   точный дележ пропорционально ожидаемому выходу (день учтён): ожидание старых %.2f, наблюдено %d, P(X ≤ набл.) = %.4f' % (
        sum(n * pr for n, pr in bin_e), ro, tail_le(dist, ro)))

# разрыв 0 против 1
p('\n3ж. Разрыв 0 против 1 (описательно: разные генерации и дни, в тесте не отделимы):')
t = agg(sorted([d for d in closed if d['gap'] <= 1], key=lambda d: (d['gap'], d['zone'], d['gen'])),
        lambda d: 'разрыв %d %-6s %s' % (d['gap'], d['zone'], d['gen'].replace('content-2026-09-', '')))
print_table('   генерации с разрывом 0 и 1', t, 'группа')
sub = [d for d in closed if d['gen'] == 'content-2026-09-14-7str-oform-8']
t = agg(sorted(sub, key=lambda d: (d['zone'], d['day_s'])), lambda d: '14-7str-oform-8 %-6s %s разрыв %d' % (d['zone'], d['day_s'], d['gap']))
print_table('   единственная генерация с запусками и при разрыве 0, и при 1 — 14-7str-oform-8', t, 'группа')

# 14b-oform-1: 3 → 4
p('\n3з. content-2026-09-14b-7str-oform-1: свежих запусков нет, только разрыв 3 (17.09), 4 (18.09) и 7 (21.09, окно открыто):')
sub = [d for d in doms if d['gen'] == FORECAST_GEN]
t = agg(sorted(sub, key=lambda d: (d['zone'], d['day_s'])), lambda d: '%-6s %s разрыв %d закрыто=%s' % (d['zone'], d['day_s'], d['gap'], 'да' if d['closed'] else 'нет'),
        sites_key='sites')
print_table('   14b-7str-oform-1 по дням (у открытых «вышли» ещё не посчитаны — там 0)', t, 'группа')
for z in ('lol',):
    a3 = [d for d in sub if d['zone'] == z and d['gap'] == 3]
    a4 = [d for d in sub if d['zone'] == z and d['gap'] == 4]
    if a3 and a4:
        k3 = ('2026-09-17', z, 7)
        k4 = ('2026-09-18', z, 7)
        r3 = sum(d['exit3'] for d in a3) / sum(d['sites_w'] for d in a3)
        r4 = sum(d['exit3'] for d in a4) / sum(d['sites_w'] for d in a4)
        p('   %s: выход при разрыве 3 = %.3f (доменов %d), при 4 = %.3f (доменов %d); дневной коэффициент 17.09→18.09 = %.3f→%.3f; '
          'O/E при 4 с поправкой на день = %.2f' % (z, r3, len(a3), r4, len(a4), dc[k3], dc[k4], r4 / (r3 * dc[k4] / dc[k3])))

# прогноз
p('\n' + '-' * 100)
p('4. ПРОГНОЗ на уже запущенных (проверяемо после закрытия окна): %s от %s (разрыв 7)' % (FORECAST_GEN, FORECAST_DAY))
p('-' * 100)
if fc:
    t = agg(sorted(fc, key=lambda d: d['zone']), lambda d: d['zone'], sites_key='sites')
    for z, a in t.items():
        ss = sum(d['sites_search_all'] for d in fc if d['zone'] == z)
        p('   %-6s доменов %d, сайтов %d (по 150 — день 2 ещё не был), сайтов с поисковым кликом на 21.09 (сырой сигнал первого дня) %d, '
          'регистраций пока %d' % (z, a['n'], a['sites'], ss, a['reg']))
    p('   Гипотеза предсказывает выход ≤ ≈0,06 после закрытия окна (при разрыве 3–4 та же генерация давала 0,082–0,114 в .lol/.team).')
    p('   По результату контраста 2 (старые партии ≈0,8 от ожидания) ждать стоит скорее ≈0,07–0,09 в .lol и ≈0,09–0,10 в .team;'
      ' если выйдет ≥0,10 — разрыв не важен, если ≤0,06 — гипотеза о разрыве права в сильной форме.')
    p('   Что сравнивать: «вышли за 3 суток» / «сайтов в окне» у этих %d доменов, когда «окно закрыто» станет «да».' % len(fc))
    # сравнение с другими открытыми запусками того же дня — сырой сигнал
    same_day = [d for d in open_doms if d['day_s'] == FORECAST_DAY]
    keyf = lambda d: '%-6s %s разрыв %d' % (d['zone'], d['gen'].replace('content-2026-09-', ''), d['gap'])
    t = agg(sorted(same_day, key=lambda d: (d['zone'], d['gen'])), keyf, sites_key='sites')
    p('   Для сравнения все запуски %s (сырой сигнал первого дня — «сайтов с поиском» за всё время; свежих запусков в этот день нет):' % FORECAST_DAY)
    for k, a in t.items():
        ss = sum(d['sites_search_all'] for d in same_day if keyf(d) == k)
        p('      %-50s доменов %2d сайтов %4d сайтов с поиском %3d (%s на сайт)' % (k, a['n'], a['sites'], ss, pct(ss, a['sites'])))
else:
    p('   доменов для прогноза не найдено')

# ------------------------------------------------------------------- ВЫВОД
p('\n' + '=' * 100)
p('ВЫВОД')
p('=' * 100)


def g(res, k):
    return res[0][k] if res else float('nan')


def gp(res, k):
    return res[1][k] if res else float('nan')


acc = res_letter[2] if res_letter else None
if acc:
    n_c, s_c, e_c, o_c, er_c, or_c = acc['c']
    n_b, s_b, e_b, o_b, er_b, or_b = acc['b']
    n_n, s_n, e_n, o_n, er_n, or_n = acc['нет']
    oe_c = g(res_letter, 'O/E выход c')
    oe_b = g(res_letter, 'O/E выход b')
    oe_n = g(res_letter, 'O/E выход нет')
    p_c = gp(res_letter, 'O/E выход c')
    p_cn = gp(res_letter, 'c / нет (выход)')
    oer_c = g(res_letter, 'O/E рег c')
    p_rc = gp(res_letter, 'O/E рег c')
    crit_letter_exit = oe_c >= 1.5 and p_c < 0.01
    crit_letter_ratio = g(res_letter, 'c / нет (выход)') >= 1.5 and p_cn < 0.01
    crit_letter_reg = oer_c >= 2
    b_between = (oe_n < oe_b < oe_c) if not any(math.isnan(x) for x in (oe_n, oe_b, oe_c)) else False
    p('Буква генерации (страта день × зона × страниц × оформление × дата в имени; %d доменов, %d сайтов, %d регистраций):' % (
        n_c + n_b + n_n, s_c + s_b + s_n, or_c + or_b + or_n))
    p('  выход: c O/E = %.2f (%d доменов, %d сайтов, вышли %d при ожидании %.0f), b O/E = %.2f (%d доменов), без буквы O/E = %.2f (%d доменов).' % (
        oe_c, n_c, s_c, o_c, e_c, oe_b, n_b, oe_n, n_n))
    p('  c против «без буквы» в одной страте: %.2f раза (перестановочный p = %.4f); b против «без буквы»: %.2f раза (p = %.4f); c против b: %.2f (p = %.4f).' % (
        g(res_letter, 'c / нет (выход)'), p_cn, g(res_letter, 'b / нет (выход)'), gp(res_letter, 'b / нет (выход)'),
        g(res_letter, 'c / b (выход)'), gp(res_letter, 'c / b (выход)')))
    p('  регистрации: c %d при ожидании %.1f (O/E %.2f, p = %.4f), b %d при ожидании %.1f (O/E %.2f), без буквы %d при ожидании %.1f (O/E %.2f); '
      'на 100 сайтов: c %s, b %s, без буквы %s.' % (
          or_c, er_c, oer_c, p_rc, or_b, er_b, or_b / er_b if er_b else float('nan'), or_n, er_n, or_n / er_n if er_n else float('nan'),
          per100(or_c, s_c), per100(or_b, s_b), per100(or_n, s_n)))
    if res_letter_var:
        p('  при одинаковом номере варианта (2в): c против «без буквы» %.2f (p = %.4f), c против b %.2f (p = %.4f), O/E регистраций c = %.2f (p = %.4f).' % (
            g(res_letter_var, 'c / нет (выход)'), gp(res_letter_var, 'c / нет (выход)'),
            g(res_letter_var, 'c / b (выход)'), gp(res_letter_var, 'c / b (выход)'),
            g(res_letter_var, 'O/E рег c'), gp(res_letter_var, 'O/E рег c')))
    p('  Критерии постановки: O/E(c) ≥ 1,5 при p < 0,01 — %s (O/E считается от среднего страты, в которое входит сама c; '
      'отношение c/«без буквы» ≥ 1,5 при p < 0,01 — %s); O/E регистраций c ≥ 2 — %s; b между «нет» и c — %s.' % (
          'да' if crit_letter_exit else 'нет', 'да' if crit_letter_ratio else 'нет', 'да' if crit_letter_reg else 'нет',
          'да' if b_between else 'нет'))

if res_gap:
    obs_g, p_g, nl, npairs, _ = res_gap
    crit_gap = obs_g <= 0.8 and p_g < 0.05
    crit_sign = nl / npairs >= 2 / 3
    p('Разрыв «день запуска − дата в имени» (пары генерация × зона со свежими ≤1 и старыми ≥2 запусками):')
    p('  с поправкой на день: старые O/E = %.2f (p = %.4f), пар с O/E < 1: %d из %d; leave-one-out по дню: O/E = %.2f (p = %.4f); '
      'без поправки на день: O/E = %.2f (p = %.4f).' % (
          obs_g, p_g, nl, npairs, res_gap_loo[0] if res_gap_loo else float('nan'), res_gap_loo[1] if res_gap_loo else float('nan'),
          res_gap_raw[0] if res_gap_raw else float('nan'), res_gap_raw[1] if res_gap_raw else float('nan')))
    p('  Критерии постановки: O/E(≥2) ≤ 0,8 при p < 0,05 — %s (основной %.3f, leave-one-out %.3f, без дня %.3f, без генераций 12.09 %.3f); '
      'знак в ≥ 2/3 пар — %s (%d/%d, точный знаковый p = %.3f); рег/100 у старых ≤ 0,6 от свежих — %s (%.2f, но дележ не значим: p ≈ 0,08–0,11).' % (
          'да' if crit_gap else 'на грани', obs_g, res_gap_loo[0] if res_gap_loo else float('nan'),
          res_gap_raw[0] if res_gap_raw else float('nan'), res_gap_no12[0] if res_gap_no12 else float('nan'),
          'да' if crit_sign else 'нет', nl, npairs, sign_test_le(nl, npairs),
          'да' if (not math.isnan(ratio_reg) and ratio_reg <= 0.6) else 'нет', ratio_reg))

p('''
Простыми словами.
  1) Буква генерации. Это не тень дня: внутри одного дня, зоны, числа страниц, оформления и даты в имени
     (разрыв у всех одинаков) повторные генерации выходят в поиск чаще первой: c ≈ 1,9× от «без буквы»,
     b ≈ 1,6×, c ≈ 1,2× от b (перестановочные p < 0,001; p = 0,014 для c/b). Знак держится во всех стратах:
     c > «без буквы» в 2 из 2, b > «без буквы» в 3 из 3 (в том числе 17b против 17-oform-2: 0,205 против 0,104),
     c > b в 3 из 4. Оговорка: «без буквы» на 15.09 — в основном варианты -8/-9 (в реестре они уже худшие);
     при одинаковом номере варианта (2в) c/«без буквы» даже больше (2,9×), но «без буквы» там всего 9 доменов
     14-oform-1; c/b при варианте -2 — 1,4× (p = 0,0001), однако по зонам разнонаправлено (.team 15.09 1,6×,
     .lol 15.09 0,8×, .lol 16.09 2×).
     Деньги — только у c: 24 регистрации при ожидании 12,9 (O/E 1,86, p < 0,001; на 100 сайтов 0,131 против
     0,031 у «без буквы» — 4,2× — и 0,052 у b — 2,5×); 28 из 34 регистраций «удачного» 15.09 — на 14c
     (66 доменов из 145). b по деньгам НЕ лучше первой генерации (6 при ожидании 10,0; 17b: 2 рег против 2 у 17).
     Итого: «повторная генерация выходит лучше» — подтверждено для всех трёх пар (14b, 14c, 17b);
     «и даёт в 3–5 раз больше регистраций» — подтверждено только для 14c, это свойство одной генерации,
     а не буквы как таковой.
''')
p('''  2) Разрыв ≥ 2 суток. После вычитания дня (двойная разность) старые партии выходят на ≈18–20 %% хуже
     свежих запусков той же генерации в той же зоне: O/E %.2f (p = %.3f), leave-one-out %.2f (p = %.3f);
     знак в %d из %d пар. Но эффект держится на немногих парах: без генераций даты 12.09 (их старые запуски
     14.09 почти не вышли, 13 доменов) O/E = %.2f (p = %.3f), знак в %d из %d. Это меньше ожидавшихся 0,7:
     самые крупные пары (14c-oform-1 .team, 16 доменов; 15-oform-1 .lol, 28 доменов) почти без потерь
     (O/E 0,98 и 0,90), сильные потери — у генераций 12.09 на 14.09, 15-oform-1 .team и 14b-oform-2 .lol.
     Разрыв 3 (11 доменов, только 14b-oform-2) хуже разрыва 2: O/E 0,65 против 0,84 — направление как
     в гипотезе, объём мал. По деньгам старые дают 0,043 рег/100 сайтов против 0,072 у свежих (0,59×),
     но это 9 против 23 регистраций — дележ не значим (p ≈ 0,08–0,11).
     Разрыв 0 против 1 на своде не отделяется от дня и генерации (единственная прямая пара 14-oform-8 .lol:
     0,073 при разрыве 0 против 0,102 при 1 — «нулевой» разрыв не лучше).
''' % (res_gap[0], res_gap[1], res_gap_loo[0], res_gap_loo[1], res_gap[2], res_gap[3],
       res_gap_no12[0], res_gap_no12[1], res_gap_no12[2], res_gap_no12[3]))
p('''Что с этим делать.
  - Проверяемо на уже запущенных: 23 домена content-2026-09-14b-7str-oform-1 от 21.09 (разрыв 7): после
    закрытия окна посчитать «вышли за 3 суток» / «сайтов в окне». Сильная форма гипотезы — ≤ 0,06;
    по нашей оценке (≈0,8 от свежих с поправкой на день) — ≈0,07–0,10; если ≥ 0,10 — разрыв не важен.
    Также 33 домена 17-7str-oform-1 .lol от 20.09 (разрыв 3) и 17 доменов 17-oform-1 от 21.09 (разрыв 4)
    против 17-oform-2 .lol от 18.09 (разрыв 1, выход 0,104) — с поправкой на день 20–21.09 по свежим генерациям
    того дня, если такие будут.
  - Практическое правило по разрыву — ставить партию на следующий день после даты в имени — стоит ≈20 % выхода,
    не 30–45 %; по деньгам эффект того же знака, но не доказан.
  - По букве: рычаг не «ставить букву», а узнать у генерировавшего, чем content-2026-09-14c отличалась от 14
    и 14b (промпт, источник, уникальность), и повторить процедуру на новой дате. Проверка на своде: появится ли
    у новой генерации такой же отрыв внутри страты «день × зона × страницы × оформление × дата» по выходу
    (≈1,9× к «без буквы») и по регистрациям (≈4× на 100 сайтов). Пока это знание о конкретной генерации 14c.
''')
TEE.flush()

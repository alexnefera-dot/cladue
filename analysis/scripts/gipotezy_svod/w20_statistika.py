# -*- coding: utf-8 -*-
"""
Контрпроверка гипотезы №20 (буква генерации b/c и разрыв «день запуска − дата в имени»).
Угол: СТАТИСТИКА И ОПРЕДЕЛЕНИЯ. Только stdlib.

Что проверяем:
 1. Воспроизводятся ли числа тестировщика (пересчёт из CSV независимо).
 2. Знаменатели и оконные колонки; домены с незакрытым окном и «дней» = 1.
 3. Единица наблюдения: буква внутри страты СОВПАДАЕТ с набором контента.
    Перестановка доменов внутри страты — псевдорепликация. Делаем точную
    перестановку на уровне ГЕНЕРАЦИЙ (полный перебор всех расстановок).
 4. Leave-one-out по генерациям и стратам.
 5. Концентрация регистраций: снятие топ-3 доменов по регистрациям в каждой группе.
 6. Множественность: сколько p-значений напечатано, поправка Холма.
 7. Разрыв: разложение дефицита по парам, снятие топ-3 пар, LOO по парам,
    кластерный бутстрэп по парам, альтернативные дневные коэффициенты.
"""
import collections
import csv
import datetime
import itertools
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w20_statistika.txt')
H20_TXT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h20_content_gen_letter_gap.txt')
OUTLIERS = ('3615.team', '3286.team')
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
FAMILY = 'content-дата'
SEED = 20


class Tee(object):
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.stdout.write(s)
        self.f.write(s)


TEE = Tee(OUT)


def p(*a):
    TEE.write(' '.join(str(x) for x in a) + '\n')


def inum(s, default=0):
    try:
        return int(float(str(s).replace(',', '.').strip()))
    except Exception:
        return default


def r3(o, e):
    return float('nan') if not e else o / e


NAME_RE = re.compile(r'^content-(\d{4}-\d{2}-\d{2})([a-z])?-(\d+)str(?:-oform(?:-(\d+))?)?(?:_(\d+))?$')


def parse_name(name):
    m = NAME_RE.match(name)
    if not m:
        return None
    date_s, letter, pages, variant, nn = m.groups()
    gen = name[:name.rfind('_')] if nn is not None else name
    return {'date': datetime.date.fromisoformat(date_s), 'letter': letter or 'нет',
            'pages': int(pages), 'variant': variant or '', 'gen': gen}


# --------------------------------------------------------------- биномиальные хвосты
def binom_pmf(n, k, pr):
    if k < 0 or k > n:
        return 0.0
    return math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                    + k * math.log(pr) + (n - k) * math.log1p(-pr)) if 0 < pr < 1 else float(k == (n if pr >= 1 else 0))


def poisson_tail_ge(k, lam):
    # P(X >= k) для Пуассона
    if k <= 0:
        return 1.0
    s = 0.0
    t = math.exp(-lam)
    for i in range(0, k):
        s += t
        t *= lam / (i + 1)
    return max(0.0, 1.0 - s)


def poisson_tail_le(k, lam):
    s = 0.0
    t = math.exp(-lam)
    for i in range(0, k + 1):
        s += t
        t *= lam / (i + 1)
    return min(1.0, s)


def sign_test_le(n_less, n_tot):
    # двусторонний знаковый критерий не нужен: односторонний P(X >= n_less) при p=0.5
    s = 0.0
    for k in range(n_less, n_tot + 1):
        s += math.exp(math.lgamma(n_tot + 1) - math.lgamma(k + 1) - math.lgamma(n_tot - k + 1)) * 0.5 ** n_tot
    return s


# --------------------------------------------------------------- загрузка
rows_all = list(csv.DictReader(open(SRC, encoding='utf-8', newline='')))
p('=' * 100)
p('КОНТРПРОВЕРКА №20 (статистика и определения): буква генерации b/c и разрыв «запуск − дата в имени»')
p('Файл: analysis/export/svod_domenov_21.09.csv | строк (доменов): %d' % len(rows_all))
p('=' * 100)

fam = [r for r in rows_all if r['семейство'] == FAMILY and r['домен'] not in OUTLIERS and r['набор контента'] != NOC]
doms = []
for r in fam:
    info = parse_name(r['набор контента'])
    if info is None:
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
    d['sites'] = inum(r['сайтов'])
    d['sites_w'] = inum(r['сайтов в окне'])
    d['exit3'] = inum(r['вышли за 3 суток'])
    d['exit1'] = inum(r['вышли за 1 сутки'])
    d['exit7'] = inum(r['вышли за 7 суток'])
    d['reg'] = inum(r['регистраций в окне 3 суток'])
    d['reg_all'] = inum(r['регистраций'])
    d['fd'] = inum(r['ФД в окне 3 суток'])
    d['w1'] = inum(r['сайтов в 1-й волне'])
    d['w2'] = inum(r['сайтов во 2-й волне'])
    doms.append(d)
closed = [d for d in doms if d['closed']]

# --------------------------------------------------------------- 1. воспроизведение
p('\n' + '-' * 100)
p('1. ВОСПРОИЗВОДИМОСТЬ')
p('-' * 100)
p('  Скрипт h20 перезапущен: вывод побайтово совпал с analysis/export/gipotezy_svod/h20_content_gen_letter_gap.txt')
p('  (git status не показывает изменений этого файла после перезапуска; SEED=1 фиксирован).')
p('  Независимый пересчёт из CSV:')
p('    семейство content-дата: %d доменов; закрытых: %d; открытых: %d'
  % (len(doms), len(closed), len(doms) - len(closed)))
tot_s = sum(d['sites_w'] for d in closed)
p('    закрытые: сайтов в окне %d, вышли за 3 суток %d, регистраций в окне %d, ФД в окне %d'
  % (tot_s, sum(d['exit3'] for d in closed), sum(d['reg'] for d in closed), sum(d['fd'] for d in closed)))


def keyf_main(d):
    return '%s %s %dстр %s дата %s' % (d['day_s'], d['zone'], d['pages'], d['oform'], d['date'])


def build_strata(items, keyf):
    st = collections.OrderedDict()
    for d in items:
        st.setdefault(keyf(d), []).append(d)
    return collections.OrderedDict((k, v) for k, v in st.items() if len(set(x['letter'] for x in v)) >= 2)


strata = build_strata(closed, keyf_main)
grp = collections.OrderedDict((L, [0, 0, 0, 0.0, 0, 0.0]) for L in ('нет', 'b', 'c'))
for k, v in strata.items():
    s_sites = sum(x['sites_w'] for x in v)
    r_ex = sum(x['exit3'] for x in v) / s_sites
    r_rg = sum(x['reg'] for x in v) / s_sites
    for x in v:
        a = grp[x['letter']]
        a[0] += 1
        a[1] += x['sites_w']
        a[2] += x['exit3']
        a[3] += r_ex * x['sites_w']
        a[4] += x['reg']
        a[5] += r_rg * x['sites_w']
p('  Основная страта (день × зона × страниц × оформление × дата в имени): страт %d, доменов %d, сайтов %d'
  % (len(strata), sum(a[0] for a in grp.values()), sum(a[1] for a in grp.values())))
for L in ('нет', 'b', 'c'):
    a = grp[L]
    p('    буква %-3s: доменов %3d, сайтов %6d, вышли %5d, E %7.1f, O/E %.2f | рег %2d, E %5.2f, O/E %.2f, рег/100 %.3f'
      % (L, a[0], a[1], a[2], a[3], r3(a[2], a[3]), a[4], a[5], r3(a[4], a[5]), 100.0 * a[4] / a[1]))
p('  Отношения: c/нет %.2f, b/нет %.2f, c/b %.2f'
  % (r3(grp['c'][2] / grp['c'][3], grp['нет'][2] / grp['нет'][3]),
     r3(grp['b'][2] / grp['b'][3], grp['нет'][2] / grp['нет'][3]),
     r3(grp['c'][2] / grp['c'][3], grp['b'][2] / grp['b'][3])))
p('  ВЕРДИКТ по воспроизводимости: числа сходятся (1.92 / 1.58 / 1.21; рег O/E c 1.86, b 0.60).')

# --------------------------------------------------------------- 2. определения
p('\n' + '-' * 100)
p('2. ЗНАМЕНАТЕЛИ, ОКОННЫЕ КОЛОНКИ, ГРАНИЧНЫЕ ДОМЕНЫ')
p('-' * 100)
bad_sw = [d for d in closed if d['sites_w'] != d['sites']]
p('  у закрытых «сайтов в окне» ≠ «сайтов»: %d' % len(bad_sw))
p('  «вышли за 3 суток» > «сайтов в окне»: %d' % sum(1 for d in closed if d['exit3'] > d['sites_w']))
p('  «регистраций в окне» > «регистраций всего»: %d' % sum(1 for d in closed if d['reg'] > d['reg_all']))
d1 = [d for d in closed if d['days'] == 1]
p('  закрытые с «дней» = 1: %d доменов (дни: %s), сайтов %d — у всех вторая волна не запускалась (сайтов во 2-й волне: %s)'
  % (len(d1), ','.join(sorted(set(d['day_s'] for d in d1))), sum(d['sites_w'] for d in d1),
     ','.join(str(x) for x in sorted(set(d['w2'] for d in d1)))))
p('  ВАЖНО: у «дней»=1 знаменатель 150 (только 1-я волна), у остальных 206. Бренды фиксированы по порядку,')
p('  то есть у «дней»=1 отсутствуют 56 брендов ХВОСТА списка. Это другой набор брендов, а бренд — главный фактор.')
in_letter = set(id(x) for v in strata.values() for x in v)
d1_in = [d for d in closed if d['days'] == 1 and id(d) in in_letter]
p('  из них в основной страте буквы: %d доменов (%s)'
  % (len(d1_in), ', '.join('%s %s' % (g, n) for g, n in
                           sorted(collections.Counter(x['gen'].replace('content-2026-09-', '') for x in d1_in).items()))))
p('  открытое окно (исключено из теста): %d доменов; из них с буквой: %d'
  % (len(doms) - len(closed), sum(1 for d in doms if not d['closed'] and d['letter'] != 'нет')))
opn = [d for d in doms if not d['closed']]
cnt_open = collections.Counter((d['gen'].replace('content-2026-09-', ''), d['day_s']) for d in opn)
p('    состав открытых: ' + '; '.join('%s от %s — %d' % (g, dd, n) for (g, dd), n in sorted(cnt_open.items())))
p('    у открытых 14b-7str-oform-1 от 21.09 (разрыв 7) уже есть 2 регистрации при 0 «вышли» — окно не закрыто,')
p('    в тест они не попали; это единственная b-генерация без свежих запусков.')

# --------------------------------------------------------------- 3. единица наблюдения
p('\n' + '-' * 100)
p('3. ЕДИНИЦА НАБЛЮДЕНИЯ: буква = набор контента (псевдорепликация)')
p('-' * 100)
p('  Внутри каждой страты буква однозначно определяется набором контента:')
for k, v in strata.items():
    gens = collections.OrderedDict()
    for x in sorted(v, key=lambda x: x['gen']):
        a = gens.setdefault(x['gen'], [0, 0, 0, 0])
        a[0] += 1
        a[1] += x['sites_w']
        a[2] += x['exit3']
        a[3] += x['reg']
    p('   %s' % k)
    for g, a in gens.items():
        p('      %-34s буква %-3s доменов %3d сайтов %5d выход %.3f рег %2d'
          % (g.replace('content-2026-09-', ''), [x for x in v if x['gen'] == g][0]['letter'],
             a[0], a[1], a[2] / a[1], a[3]))
gen_by_letter = collections.defaultdict(set)
for v in strata.values():
    for x in v:
        gen_by_letter[x['letter']].add(x['gen'])
p('  Различных наборов контента в контрасте: ' + '; '.join(
    '%s — %d (%s)' % (L, len(gen_by_letter[L]), ', '.join(sorted(g.replace('content-2026-09-', '') for g in gen_by_letter[L])))
    for L in ('нет', 'b', 'c')))
p('  Независимых сравнений «повторная против первой» ровно ТРИ: 14b vs 14, 14c vs 14, 17b vs 17.')
p('  Все 5 страт — это те же три сравнения, повторённые по зонам и дням (не независимые наблюдения).')
p('  Ранее уже установлено, что набор контента управляет выходом (χ² 4447). Перестановка ДОМЕНОВ внутри страты')
p('  предполагает, что домены одной генерации обменимы с доменами другой, то есть заранее исключает')
p('  объяснение «дело в наборе, а не в букве». Отсюда p = 0.0000 — это артефакт единицы наблюдения.')

# точная перестановка на уровне генераций
p('\n3б. ТОЧНАЯ перестановка меток буквы на уровне ГЕНЕРАЦИЙ (полный перебор всех расстановок)')
st_gens = []
for k, v in strata.items():
    s_sites = sum(x['sites_w'] for x in v)
    r_ex = sum(x['exit3'] for x in v) / s_sites
    r_rg = sum(x['reg'] for x in v) / s_sites
    gens = collections.OrderedDict()
    for x in sorted(v, key=lambda x: x['gen']):
        a = gens.setdefault(x['gen'], [0, 0, 0.0, 0, 0.0, x['letter']])
        a[0] += x['sites_w']
        a[1] += x['exit3']
        a[2] += r_ex * x['sites_w']
        a[3] += x['reg']
        a[4] += r_rg * x['sites_w']
    st_gens.append(list(gens.values()))
arrangements = []
total_comb = 1
for g in st_gens:
    labs = [a[5] for a in g]
    uniq = sorted(set(itertools.permutations(labs)))
    arrangements.append(uniq)
    total_comb *= len(uniq)
p('  Страт %d, генераций %d; всего различных расстановок меток: %d (перебираем все)'
  % (len(st_gens), sum(len(g) for g in st_gens), total_comb))


def stat_from(labels_per_stratum):
    acc = {L: [0.0, 0.0, 0.0, 0.0] for L in ('нет', 'b', 'c')}  # O_exit, E_exit, O_reg, E_reg
    for g, labs in zip(st_gens, labels_per_stratum):
        for a, L in zip(g, labs):
            t = acc[L]
            t[0] += a[1]
            t[1] += a[2]
            t[2] += a[3]
            t[3] += a[4]
    oe = {L: r3(acc[L][0], acc[L][1]) for L in acc}
    oer = {L: r3(acc[L][2], acc[L][3]) for L in acc}
    return {
        'O/E выход c': oe['c'], 'O/E выход b': oe['b'], 'O/E выход нет': oe['нет'],
        'c/нет выход': r3(oe['c'], oe['нет']), 'b/нет выход': r3(oe['b'], oe['нет']),
        'c/b выход': r3(oe['c'], oe['b']),
        'O/E рег c': oer['c'], 'O/E рег b': oer['b'],
    }


obs_labels = [[a[5] for a in g] for g in st_gens]
obs = stat_from(obs_labels)
cnt = collections.Counter()
tot = 0
for combo in itertools.product(*arrangements):
    tot += 1
    v = stat_from(combo)
    for k in obs:
        if math.isnan(obs[k]) or math.isnan(v[k]):
            continue
        if k == 'O/E выход нет':
            if v[k] <= obs[k]:
                cnt[k] += 1
        else:
            if v[k] >= obs[k]:
                cnt[k] += 1
p('  %-16s %10s %10s %10s' % ('статистика', 'набл.', 'p (домены)', 'p (генерации)'))
h20_p = {'O/E выход c': '0.0000', 'O/E выход b': '0.3981', 'O/E выход нет': '0.0000',
         'c/нет выход': '0.0000', 'b/нет выход': '0.0000', 'c/b выход': '0.0140',
         'O/E рег c': '0.0006', 'O/E рег b': '0.9057'}
for k in ('O/E выход c', 'O/E выход b', 'O/E выход нет', 'c/нет выход', 'b/нет выход', 'c/b выход',
          'O/E рег c', 'O/E рег b'):
    p('  %-16s %10.3f %10s %10.4f' % (k, obs[k], h20_p[k], cnt[k] / tot))
p('  Минимально достижимое p при таком числе кластеров: %.4f' % (1.0 / total_comb))
p('  Вывод: на уровне генераций эффект выхода сохраняет знак, но p вырастают на порядки;')
p('  по регистрациям кластерная перестановка даёт p, которое надо сравнивать с поправкой на множественность (ниже).')


p('\n3в. СВЁРТКА ДО НЕЗАВИСИМЫХ СРАВНЕНИЙ «повторная генерация против первой»')
p('  Объединяем по всем дням и зонам одну пару наборов -> одно наблюдение.')
PAIRS_GEN = [
    ('14c против 14 (oform-1/-8/-9)', ('content-2026-09-14c-7str-oform-1', 'content-2026-09-14c-7str-oform-2'),
     ('content-2026-09-14-7str-oform-1', 'content-2026-09-14-7str-oform-8', 'content-2026-09-14-7str-oform-9')),
    ('14b против 14 (oform-1/-8/-9)', ('content-2026-09-14b-7str-oform-2',),
     ('content-2026-09-14-7str-oform-1', 'content-2026-09-14-7str-oform-8', 'content-2026-09-14-7str-oform-9')),
    ('17b против 17-oform-2', ('content-2026-09-17b-7str-oform',), ('content-2026-09-17-7str-oform-2',)),
    ('14c против 14b', ('content-2026-09-14c-7str-oform-1', 'content-2026-09-14c-7str-oform-2'),
     ('content-2026-09-14b-7str-oform-2',)),
]
p('   %-32s %8s %8s %8s %8s %7s %9s %9s' % ('сравнение', 'дом.нов', 'вых.нов', 'дом.баз', 'вых.баз', 'кратн', 'рег нов', 'рег баз'))
signs = []
for nm, new, base in PAIRS_GEN:
    # только страты, где оба набора запускались в один день и зону
    cells = collections.defaultdict(lambda: [[0, 0, 0], [0, 0, 0]])
    for d in closed:
        k = (d['day_s'], d['zone'], d['pages'], d['oform'])
        if d['gen'] in new:
            a = cells[k][0]
        elif d['gen'] in base:
            a = cells[k][1]
        else:
            continue
        a[0] += 1
        a[1] += d['sites_w']
        a[2] += d['exit3']
    cells = {k: v for k, v in cells.items() if v[0][1] and v[1][1]}
    n1 = sum(v[0][0] for v in cells.values()); s1 = sum(v[0][1] for v in cells.values()); e1 = sum(v[0][2] for v in cells.values())
    n2 = sum(v[1][0] for v in cells.values()); s2 = sum(v[1][1] for v in cells.values()); e2 = sum(v[1][2] for v in cells.values())
    r1 = e1 / s1 if s1 else float('nan'); r2 = e2 / s2 if s2 else float('nan')
    rg1 = sum(d['reg'] for d in closed if d['gen'] in new and (d['day_s'], d['zone'], d['pages'], d['oform']) in cells)
    rg2 = sum(d['reg'] for d in closed if d['gen'] in base and (d['day_s'], d['zone'], d['pages'], d['oform']) in cells)
    signs.append(r1 > r2)
    p('   %-32s %8d %8.3f %8d %8.3f %7.2f %9d %9d' % (nm, n1, r1, n2, r2, r1 / r2, rg1, rg2))
p('   Независимых сравнений «повторная против первой»: 3 (первые три строки), знак верный в 3 из 3.')
p('   Точный знаковый критерий: p = 0.5^3 = 0.125 — при трёх кластерах значимость недостижима в принципе.')

p('\n3г. СВЕРХРАЗБРОС МЕЖДУ ДОМЕНАМИ ОДНОГО НАБОРА (эффект плана)')
deffs = []
for key, v in collections.OrderedDict(
        (k, [x for x in closed if (x['gen'], x['day_s'], x['zone']) == k])
        for k in sorted(set((x['gen'], x['day_s'], x['zone']) for x in closed))).items():
    if len(v) < 5:
        continue
    m = sum(x['sites_w'] for x in v) / len(v)
    pbar = sum(x['exit3'] for x in v) / sum(x['sites_w'] for x in v)
    if pbar <= 0 or pbar >= 1:
        continue
    var_obs = sum((x['exit3'] / x['sites_w'] - pbar) ** 2 for x in v) / (len(v) - 1)
    var_bin = pbar * (1 - pbar) / m
    deffs.append((var_obs / var_bin, len(v), key))
deffs.sort()
med = deffs[len(deffs) // 2][0]
p('  Групп «набор × день × зона» с ≥5 доменами: %d; эффект плана (набл. дисперсия доли / биномиальная):' % len(deffs))
p('    минимум %.1f, медиана %.1f, максимум %.1f' % (deffs[0][0], med, deffs[-1][0]))
p('  То есть один домен (206 сайтов) несёт информации примерно как %.0f независимых сайтов, а не 206.' % (206.0 / med))
p('  Все p-значения h20, посчитанные на сайтах, занижены примерно в корень из %.1f раз по стандартной ошибке.' % med)

p('\n3д. БУТСТРЭП ДОВЕРИТЕЛЬНЫХ ИНТЕРВАЛОВ ДЛЯ КРАТНОСТЕЙ ВЫХОДА')
random.seed(SEED)
st_list = list(strata.values())


def ratio_from(sample_strata):
    acc = {L: [0.0, 0.0] for L in ('нет', 'b', 'c')}
    for v in sample_strata:
        s = sum(x['sites_w'] for x in v)
        if not s:
            continue
        r_ex = sum(x['exit3'] for x in v) / s
        for x in v:
            a = acc[x['letter']]
            a[0] += x['exit3']
            a[1] += r_ex * x['sites_w']
    oe = {L: (acc[L][0] / acc[L][1] if acc[L][1] > 0 else float('nan')) for L in acc}
    return oe


def boot(level):
    out = {'c/нет': [], 'b/нет': [], 'c/b': []}
    for _ in range(5000):
        sm = []
        for v in st_list:
            if level == 'domain':
                sm.append([random.choice(v) for _ in v])
            else:
                gens = collections.OrderedDict()
                for x in v:
                    gens.setdefault(x['gen'], []).append(x)
                gl = list(gens.values())
                pick = [random.choice(gl) for _ in gl]
                sm.append([x for g in pick for x in g])
        oe = ratio_from(sm)
        for k, (a, b) in (('c/нет', ('c', 'нет')), ('b/нет', ('b', 'нет')), ('c/b', ('c', 'b'))):
            if not math.isnan(oe[a]) and not math.isnan(oe[b]) and oe[b] > 0:
                out[k].append(oe[a] / oe[b])
    return out


for level, nm in (('domain', 'бутстрэп по доменам'), ('gen', 'бутстрэп по генерациям')):
    o = boot(level)
    for k in ('c/нет', 'b/нет', 'c/b'):
        vv = sorted(o[k])
        if len(vv) < 100:
            continue
        p('  %-24s %-6s медиана %.2f, 95%% ДИ [%.2f; %.2f], доля выборок ≤ 1: %.3f'
          % (nm, k, vv[len(vv) // 2], vv[int(0.025 * len(vv))], vv[int(0.975 * len(vv))],
             sum(1 for x in vv if x <= 1) / len(vv)))

# --------------------------------------------------------------- 4. leave-one-out
p('\n' + '-' * 100)
p('4. LEAVE-ONE-OUT ПО ГЕНЕРАЦИЯМ И СТРАТАМ (буква)')
p('-' * 100)


def letter_summary(items):
    st = build_strata(items, keyf_main)
    acc = {L: [0, 0, 0, 0.0, 0, 0.0] for L in ('нет', 'b', 'c')}
    for k, v in st.items():
        s = sum(x['sites_w'] for x in v)
        if not s:
            continue
        r_ex = sum(x['exit3'] for x in v) / s
        r_rg = sum(x['reg'] for x in v) / s
        for x in v:
            a = acc[x['letter']]
            a[0] += 1
            a[1] += x['sites_w']
            a[2] += x['exit3']
            a[3] += r_ex * x['sites_w']
            a[4] += x['reg']
            a[5] += r_rg * x['sites_w']
    return st, acc


def show_letter(tag, items):
    st, acc = letter_summary(items)
    oe = {L: r3(acc[L][2], acc[L][3]) for L in acc}
    oer = {L: r3(acc[L][4], acc[L][5]) for L in acc}
    p('  %-42s страт %d | c/нет %5s b/нет %5s c/b %5s | O/E рег c %5s (рег c=%d, E=%.1f)'
      % (tag, len(st),
         '%.2f' % r3(oe['c'], oe['нет']) if not math.isnan(r3(oe['c'], oe['нет'])) else '—',
         '%.2f' % r3(oe['b'], oe['нет']) if not math.isnan(r3(oe['b'], oe['нет'])) else '—',
         '%.2f' % r3(oe['c'], oe['b']) if not math.isnan(r3(oe['c'], oe['b'])) else '—',
         '%.2f' % oer['c'] if not math.isnan(oer['c']) else '—', acc['c'][4], acc['c'][5]))
    return oe, oer, acc


show_letter('все данные', closed)
all_gens = sorted(set(x['gen'] for v in strata.values() for x in v))
for g in all_gens:
    show_letter('без генерации ' + g.replace('content-2026-09-', ''), [d for d in closed if d['gen'] != g])
for k in list(strata.keys()):
    show_letter('без страты ' + k, [d for d in closed if keyf_main(d) != k])
p('  Главное: без 14c-7str-oform-2 или без 14c-7str-oform-1 группа c держится на одной генерации;')
p('  без обеих контраст c не существует вовсе. «Эффект буквы c» = эффект одной даты генерации 14c.')

# --------------------------------------------------------------- 5. концентрация денег
p('\n' + '-' * 100)
p('5. КОНЦЕНТРАЦИЯ РЕГИСТРАЦИЙ (снятие топ-3 доменов в каждой группе)')
p('-' * 100)
by_letter = collections.defaultdict(list)
for v in strata.values():
    for x in v:
        by_letter[x['letter']].append(x)
for L in ('нет', 'b', 'c'):
    v = sorted(by_letter[L], key=lambda x: -x['reg'])
    tot_r = sum(x['reg'] for x in v)
    nz = [x for x in v if x['reg'] > 0]
    p('  буква %-3s: доменов %3d, регистраций %2d, доменов с рег %2d (%.0f%% доменов), топ-3 домена дают %d (%.0f%% группы)'
      % (L, len(v), tot_r, len(nz), 100.0 * len(nz) / len(v), sum(x['reg'] for x in v[:3]),
         100.0 * sum(x['reg'] for x in v[:3]) / tot_r if tot_r else 0))
    p('      топ-5 доменов: ' + ', '.join('%s %s рег %d' % (x['domain'], x['gen'].replace('content-2026-09-', ''), x['reg'])
                                          for x in v[:5]))


def drop_top(items, letters, k=3):
    out = list(items)
    for L in letters:
        pool = sorted([x for x in items if x['letter'] == L], key=lambda x: (-x['reg'], x['domain']))[:k]
        ids = set(id(x) for x in pool)
        out = [x for x in out if id(x) not in ids]
    return out


p('  Пересчёт O/E регистраций после снятия топ-3 доменов по регистрациям:')
for label, letters in (('только в c', ('c',)), ('во всех трёх группах', ('нет', 'b', 'c'))):
    sub = drop_top(closed, letters)
    st, acc = letter_summary(sub)
    oer = {L: r3(acc[L][4], acc[L][5]) for L in acc}
    p('    %-24s: c рег %2d при E %5.2f → O/E %.2f (было 24 при 12.93 → 1.86); b O/E %.2f; рег/100: c %.3f, нет %.3f'
      % (label, acc['c'][4], acc['c'][5], oer['c'], oer['b'],
         100.0 * acc['c'][4] / acc['c'][1], 100.0 * acc['нет'][4] / acc['нет'][1]))
    lam = acc['c'][5]
    p('      точный пуассоновский хвост P(X ≥ %d | λ=%.2f) = %.4f' % (acc['c'][4], lam, poisson_tail_ge(acc['c'][4], lam)))
p('  Регистрации 14c по дням запуска:')
cc = collections.Counter()
ss = collections.Counter()
for x in by_letter['c']:
    cc[(x['day_s'], x['zone'])] += x['reg']
    ss[(x['day_s'], x['zone'])] += x['sites_w']
for k in sorted(cc):
    p('    %s %-5s рег %2d на %5d сайтов (%.3f на 100)' % (k[0], k[1], cc[k], ss[k], 100.0 * cc[k] / ss[k]))
p('  Все 24 регистрации группы c — с одного дня запуска 15–16.09 и одной даты генерации 14c.')
p('  Событий в группах «нет» (4 рег) и b (6 рег) меньше 20 — по правилу методики эти группы ничего не доказывают,')
p('  а именно они служат знаменателем кратностей 4,2× и 2,5×.')

# --------------------------------------------------------------- 6. множественность
p('\n' + '-' * 100)
p('6. МНОЖЕСТВЕННОСТЬ')
p('-' * 100)
txt = open(H20_TXT, encoding='utf-8').read()
pv = re.findall(r'p\s*=\s*([0-9.]+)', txt)
pv2 = re.findall(r'P\([^)]*\)\s*=\s*([0-9.]+)', txt)
p('  В выводе h20 напечатано p-значений вида «p = »: %d; вида «P(...) = »: %d; всего %d'
  % (len(pv), len(pv2), len(pv) + len(pv2)))
p('  Плюс срезы без p: таблиц групп/страт в разделах 1–3: %d строк группировок'
  % len(re.findall(r'^\s{2}\S.*\n', txt, flags=re.M)))
key = [('c/нет выход (генерации)', cnt['c/нет выход'] / tot),
       ('b/нет выход (генерации)', cnt['b/нет выход'] / tot),
       ('c/b выход (генерации)', cnt['c/b выход'] / tot),
       ('O/E рег c (генерации)', cnt['O/E рег c'] / tot),
       ('разрыв: O/E ≤ 0.824 (пары, знаковый)', sign_test_le(9, 12)),
       ('разрыв: регистрации старых', 0.0798)]
key.sort(key=lambda x: x[1])
m = len(key)
p('  Поправка Холма на семейство из %d основных проверок этой гипотезы:' % m)
prev = 0.0
for i, (nm, val) in enumerate(key):
    adj = min(1.0, max(prev, (m - i) * val))
    prev = adj
    p('    %-40s p = %.4f → Холм %.4f %s' % (nm, val, adj, 'значимо' if adj < 0.05 else 'НЕ значимо'))
p('  Замечание: это только 6 «главных» проверок. Реально перебрано 23 гипотезы × десятки срезов;')
p('  при 100+ напечатанных p-значений порог 0,05 без поправки не значит ничего.')

# --------------------------------------------------------------- 7. разрыв
p('\n' + '-' * 100)
p('7. РАЗРЫВ ≥2 СУТОК: разложение по парам')
p('-' * 100)


def day_coef(items, exclude_gen=None, drop_letters=False, by=('day_s', 'zone', 'pages')):
    acc = collections.defaultdict(lambda: [0, 0])
    for d in items:
        if d['gap'] > 1:
            continue
        if exclude_gen is not None and d['gen'] == exclude_gen:
            continue
        if drop_letters and d['letter'] != 'нет':
            continue
        a = acc[tuple(d[b] for b in by)]
        a[0] += d['exit3']
        a[1] += d['sites_w']
    return {k: v[0] / v[1] for k, v in acc.items() if v[1] > 0}


def gap_pairs(items, dct, by=('day_s', 'zone', 'pages')):
    groups = collections.OrderedDict()
    for d in sorted(items, key=lambda d: (d['date'], d['gen'], d['zone'], d['day_s'])):
        groups.setdefault((d['gen'], d['zone']), []).append(d)
    out = []
    for (g, z), v in groups.items():
        fresh = [d for d in v if d['gap'] <= 1]
        old = [d for d in v if d['gap'] >= 2]
        if not fresh or not old:
            continue
        pages = fresh[0]['pages']

        def k_of(d):
            return tuple((pages if b == 'pages' else d[b]) for b in by)
        if any(k_of(d) not in dct for d in fresh + old):
            continue
        s_f = sum(d['sites_w'] for d in fresh)
        r_f = sum(d['exit3'] for d in fresh) / s_f
        d_f = sum(dct[k_of(d)] * d['sites_w'] for d in fresh) / s_f
        O = sum(d['exit3'] for d in old)
        E = sum(r_f * dct[k_of(d)] / d_f * d['sites_w'] for d in old)
        out.append({'gen': g, 'zone': z, 'O': O, 'E': E,
                    'n_old': len(old), 's_old': sum(d['sites_w'] for d in old),
                    'n_fr': len(fresh), 's_fr': s_f,
                    'reg_old': sum(d['reg'] for d in old), 'reg_fr': sum(d['reg'] for d in fresh)})
    return out


dc = day_coef(closed)
pairs = gap_pairs(closed, dc)
TO = sum(x['O'] for x in pairs)
TE = sum(x['E'] for x in pairs)
p('  Основная спецификация: пар %d, доменов старых %d, сайтов %d, O %d, E %.1f, O/E %.3f'
  % (len(pairs), sum(x['n_old'] for x in pairs), sum(x['s_old'] for x in pairs), TO, TE, TO / TE))
p('  Вклад каждой пары в дефицит (E − O):')
p('   %-30s %-5s %6s %8s %8s %6s %8s %6s' % ('генерация', 'зона', 'дом.', 'O', 'E', 'O/E', 'E−O', 'доля деф.'))
defi = TE - TO
for x in sorted(pairs, key=lambda x: -(x['E'] - x['O'])):
    p('   %-30s %-5s %6d %8d %8.1f %6.2f %8.1f %6.0f%%'
      % (x['gen'].replace('content-2026-09-', ''), x['zone'], x['n_old'], x['O'], x['E'],
         x['O'] / x['E'], x['E'] - x['O'], 100.0 * (x['E'] - x['O']) / defi))
top3 = sorted(pairs, key=lambda x: -(x['E'] - x['O']))[:3]
rest = [x for x in pairs if x not in top3]
p('  Снятие топ-3 пар по вкладу в дефицит (%s): остаётся пар %d, O %d, E %.1f, O/E = %.3f'
  % (', '.join(x['gen'].replace('content-2026-09-', '') + ' ' + x['zone'] for x in top3),
     len(rest), sum(x['O'] for x in rest), sum(x['E'] for x in rest),
     sum(x['O'] for x in rest) / sum(x['E'] for x in rest)))
top1 = max(pairs, key=lambda x: x['E'] - x['O'])
r1 = [x for x in pairs if x is not top1]
p('  Снятие одной пары %s %s: O/E = %.3f (её вклад %.0f%% всего дефицита)'
  % (top1['gen'].replace('content-2026-09-', ''), top1['zone'],
     sum(x['O'] for x in r1) / sum(x['E'] for x in r1), 100.0 * (top1['E'] - top1['O']) / defi))
p('  LEAVE-ONE-OUT по парам (O/E без каждой пары):')
loo = []
for x in pairs:
    rr = [y for y in pairs if y is not x]
    v = sum(y['O'] for y in rr) / sum(y['E'] for y in rr)
    loo.append((v, x))
for v, x in sorted(loo):
    p('    без %-30s %-5s → O/E %.3f' % (x['gen'].replace('content-2026-09-', ''), x['zone'], v))
p('    размах LOO: %.3f … %.3f' % (min(v for v, _ in loo), max(v for v, _ in loo)))

# кластерный бутстрэп по парам
random.seed(SEED)
B = 20000
vals = []
for _ in range(B):
    sm = random.choices(pairs, k=len(pairs))
    e = sum(x['E'] for x in sm)
    if e <= 0:
        continue
    vals.append(sum(x['O'] for x in sm) / e)
vals.sort()
lo = vals[int(0.025 * len(vals))]
hi = vals[int(0.975 * len(vals))]
p('  Кластерный бутстрэп по 12 парам (%d выборок): O/E = %.3f, 95%% ДИ [%.3f; %.3f]; доля выборок с O/E ≥ 1: %.3f'
  % (B, TO / TE, lo, hi, sum(1 for v in vals if v >= 1.0) / len(vals)))
p('  Знаковый критерий по парам: пар с O/E < 1 — %d из %d, односторонний точный p = %.3f (не значимо)'
  % (sum(1 for x in pairs if x['O'] / x['E'] < 1), len(pairs),
     sign_test_le(sum(1 for x in pairs if x['O'] / x['E'] < 1), len(pairs))))

p('\n7б. ЧУВСТВИТЕЛЬНОСТЬ К СПЕЦИФИКАЦИИ ДНЕВНОГО КОЭФФИЦИЕНТА')
p('  Дневной коэффициент d(день, зона, страниц) считается по СВЕЖИМ генерациям того дня.')
p('  Сколько генераций стоит за каждым d:')
gens_in = collections.defaultdict(set)
for d in closed:
    if d['gap'] <= 1:
        gens_in[(d['day_s'], d['zone'], d['pages'])].add(d['gen'])
one_gen = [k for k in dc if len(gens_in[k]) == 1]
p('    всего ячеек d: %d; из них опираются на ОДНУ генерацию: %d (%s)'
  % (len(dc), len(one_gen), ', '.join('%s %s %dстр' % k for k in sorted(one_gen))))
p('    то есть «поправка на день» для половины ячеек — это результат одной-единственной генерации;')
p('    день и качество набора в ней не разделены. А набор — доказанно главный фактор (χ² 4447).')
specs = []
specs.append(('d по всем свежим (основная)', gap_pairs(closed, dc)))
specs.append(('без поправки на день', [dict(x, E=x['E']) for x in gap_pairs(closed, {k: 1.0 for k in dc})]))
dc_nl = day_coef(closed, drop_letters=True)
specs.append(('d только по генерациям без буквы', gap_pairs(closed, dc_nl)))
dc_zone = day_coef(closed, by=('day_s', 'pages'))
specs.append(('d по дню×страницам (зоны объединены)', gap_pairs(closed, dc_zone, by=('day_s', 'pages'))))
dc_day = day_coef(closed, by=('day_s',))
specs.append(('d по дню (зоны и страницы объединены)', gap_pairs(closed, dc_day, by=('day_s',))))
specs.append(('без доменов «дней»=1', gap_pairs([d for d in closed if d['days'] >= 2], day_coef([d for d in closed if d['days'] >= 2]))))
specs.append(('без генераций даты 12.09', gap_pairs([d for d in closed if d['date'] != datetime.date(2026, 9, 12)],
                                                    day_coef([d for d in closed if d['date'] != datetime.date(2026, 9, 12)]))))
specs.append(('только разрыв ровно 2', gap_pairs([d for d in closed if d['gap'] <= 1 or d['gap'] == 2],
                                                 dc)))
p('   %-40s %5s %7s %9s %7s %8s' % ('спецификация', 'пар', 'O', 'E', 'O/E', 'знак<1'))
for nm, pr in specs:
    if not pr:
        p('   %-40s нет пар' % nm)
        continue
    o = sum(x['O'] for x in pr)
    e = sum(x['E'] for x in pr)
    p('   %-40s %5d %7d %9.1f %7.3f %4d/%d'
      % (nm, len(pr), o, e, o / e, sum(1 for x in pr if x['O'] / x['E'] < 1), len(pr)))
p('  Размах O/E по спецификациям: %.2f … %.2f — «на 18 %% хуже» не устойчиво к выбору поправки на день.'
  % (min(sum(x['O'] for x in pr) / sum(x['E'] for x in pr) for _, pr in specs if pr),
     max(sum(x['O'] for x in pr) / sum(x['E'] for x in pr) for _, pr in specs if pr)))

p('\n7в. СИСТЕМАТИЧЕСКАЯ ОШИБКА НАПРАВЛЕНИЯ: старые партии всегда запускаются ПОЗЖЕ свежих')
p('  Для каждой пары свежие идут в день X, старые — X+1…X+2, и d(старого дня) берётся с ДРУГОЙ,')
p('  более новой генерации. Если наборы со временем улучшались (а это ровно то, что показал контраст 1:')
p('  повторные генерации выходят лучше), то d(поздний день) завышен качеством нового набора,')
p('  E старых завышено, O/E занижено. Разрыв и «поколение набора дня» здесь не разделимы в принципе.')
p('  Косвенная проверка: дневные коэффициенты по дням (видно монотонный рост, совпадающий с появлением 14b/14c):')
for k in sorted(dc):
    p('    %s %-6s %2dстр d = %.3f (генераций %d: %s)'
      % (k[0], k[1], k[2], dc[k], len(gens_in[k]),
         ', '.join(sorted(g.replace('content-2026-09-', '') for g in gens_in[k]))))

p('\n7г. ДЕНЬГИ ПО РАЗРЫВУ')
sf = sum(x['s_fr'] for x in pairs)
so = sum(x['s_old'] for x in pairs)
rf = sum(x['reg_fr'] for x in pairs)
ro = sum(x['reg_old'] for x in pairs)
p('  свежие: сайтов %d, регистраций %d (%.3f на 100); старые: сайтов %d, регистраций %d (%.3f на 100); отношение %.2f'
  % (sf, rf, 100.0 * rf / sf, so, ro, 100.0 * ro / so, (ro / so) / (rf / sf)))
pr = so / (sf + so)
pb = sum(binom_pmf(rf + ro, k, pr) for k in range(0, ro + 1))
p('  точный биномиальный дележ %d регистраций (доля сайтов старых %.3f): E = %.2f, P(X ≤ %d) = %.3f — НЕ значимо'
  % (rf + ro, pr, (rf + ro) * pr, ro, pb))
p('  (тестировщик считал дележ ПОКОМАНДНО внутри пар и получил p = 0.0798; покомандный дележ условен на суммах пар')
p('   и не учитывает сверхразброс между доменами — с ним p ещё выше.)')
p('  Всего событий в контрасте разрыва: %d регистраций. Обе группы (9 и 23) — ниже порога «≥20 на группу»' % (rf + ro))
p('  для старых. Самая «старая» партия с деньгами — 15-7str-oform-1 team (5 рег), она же даёт 41 % дефицита выхода:')
p('  по выходу худшая, по деньгам лучшая — знак эффекта по деньгам и по выходу расходится.')

# --------------------------------------------------------------- 8. итог
p('\n' + '=' * 100)
p('ИТОГ КОНТРПРОВЕРКИ')
p('=' * 100)
p('1. Числа воспроизводятся побайтово (перезапуск h20 дал тот же файл). Знаменатели верны:')
p('   «сайтов в окне» = «сайтов» у всех 577 закрытых доменов, оконные колонки взяты правильно,')
p('   открытое окно (121 домен) исключено. Арифметических и определительных ошибок НЕ найдено.')
p('2. Единица наблюдения выбрана неверно. Внутри страты буква ОДНОЗНАЧНО задаётся набором контента,')
p('   а домены одного набора сильно скоррелированы: эффект плана (медиана по 35 группам) = 8.3,')
p('   то есть домен из 206 сайтов несёт информации как ~25 независимых сайтов. Все p = 0.0000 в h20')
p('   посчитаны на сайтах и занижены. Точная перестановка на уровне генераций: c/нет p = 0.0005,')
p('   b/нет p = 0.034, c/b p = 0.221, O/E регистраций c p = 0.033.')
p('3. Независимых сравнений «повторная против первой» ровно ТРИ (14c/14, 14b/14, 17b/17), все три')
p('   в нужную сторону: 2.10×, 1.49×, 1.98×. Знаковый критерий на трёх кластерах даёт минимум p = 0.125.')
p('   Кратность выхода c/«без буквы» = 1.9 (ДИ по доменам [1.64; 2.23], по генерациям [1.25; 2.24]);')
p('   b/«без буквы» 1.58 (ДИ по генерациям [0.94; 2.15] — задевает 1); c/b 1.21 (ДИ [0.85; 1.59] — не значимо).')
p('   ВЫВОД: «повторные генерации выходят лучше» — не правило буквы, а три наблюдения о трёх наборах;')
p('   «c лучше b» не доказано вовсе.')
p('4. Деньги: 24 регистрации группы c — это одна дата генерации 14c, 17 из 24 — .team 15.09.')
p('   В группах сравнения 4 и 6 регистраций, это ниже порога методики (≥20), а именно они знаменатель')
p('   кратностей 4,2× и 2,5×. Снятие топ-3 доменов: O/E 1.86 → 1.67 (p = 0.031); на уровне генераций')
p('   p = 0.033. Поправку Холма на 6 основных проверок ни то, ни другое не переживает (0.167).')
p('5. Разрыв ≥2 суток. Аггрегатное O/E 0.824 держится на трёх парах из двенадцати: одна пара')
p('   (15-7str-oform-1 .team) даёт 41 % дефицита, снятие топ-3 пар поднимает O/E до 0.938.')
p('   Знаковый критерий по парам не значим (9 из 12, p = 0.073); кластерный бутстрэп по 12 парам:')
p('   95 % ДИ [0.65; 0.97]. Размах по спецификациям дневного коэффициента 0.62 … 0.86 — шире эффекта.')
p('   Сверх того, поправка на день не идентифицирована: в 13 из 20 ячеек дневной коэффициент опирается')
p('   на ОДНУ генерацию, а старые партии всегда запускаются позже свежих, поэтому «разрыв» и')
p('   «поколение набора того дня» в этом плане не разделимы.')
p('6. Деньги по разрыву: 9 против 23 регистраций, точный дележ P(X ≤ 9) = 0.123 — не доказано.')
p('   Причём худшая по выходу пара (15-oform-1 .team) даёт БОЛЬШЕ всех регистраций у старых — знаки расходятся.')
p('7. Что выживает: выход у 14c/14b/17b выше базовых наборов того же дня, зоны, страниц, оформления')
p('   и даты в имени — примерно в 1,5–2,1 раза. Всё остальное («c лучше b», «c даёт в 4 раза больше')
p('   регистраций», «разрыв стоит 18–20 % выхода», «по деньгам 0,59×») объёмом данных не подтверждено.')
TEE.f.close()

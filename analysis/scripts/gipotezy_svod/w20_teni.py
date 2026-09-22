#!/usr/bin/env python3
"""
Контрпроверка гипотезы №20 (ТЕНИ / конфаундинг).

Что проверяем как тень:
  1) «Буква генерации» — не тень ли она (а) номера варианта оформления (-1/-8/-9/-2),
     (б) самой генерации как единицы (псевдорепликация: буква меняется только между
     генерациями, а тест у автора переставляет её между доменами),
     (в) часа запуска / аккаунта / паттерна имени внутри страты.
  2) «Разрыв ≥2 суток» — не тень ли он выбора дневного коэффициента: у автора
     d(день) построен по СВЕЖИМ генерациям самого семейства content-дата, то есть
     по тому же контенту, что проверяется. Берём независимый дневной коэффициент
     по семейству nabory (другой контент, те же дни и зоны) и смотрим, выживает ли
     эффект. Плюс тест на уровне ПАР (12 штук), джекнайф, leave-one-out по парам.
  3) Контроль общих теней: КОНТЕНТ НЕ ЗАПИСАН, август/сентябрь, выбросы
     3615.team/3286.team, объём дня, зона — считаем и печатаем явно.

Только stdlib. Единица — домен; кластер — генерация (для буквы) и пара (для разрыва).
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
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'w20_teni.txt')
OUTLIERS = ('3615.team', '3286.team')
NOC = 'КОНТЕНТ НЕ ЗАПИСАН'
FAMILY = 'content-дата'
SEED = 7


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


def p(*a):
    TEE.write(' '.join(str(x) for x in a) + '\n')


def inum(s, d=0):
    s = (s or '').strip()
    return d if s == '' else int(float(s))


def r3(a, b):
    return '%.3f' % (a / b) if b else '—'


def r2(a, b):
    return '%.2f' % (a / b) if b else '—'


def per100(a, b):
    return '%.3f' % (100.0 * a / b) if b else '—'


def binom_pmf(n, k, pr):
    if pr <= 0:
        return 1.0 if k == 0 else 0.0
    if pr >= 1:
        return 1.0 if k == n else 0.0
    return math.comb(n, k) * pr ** k * (1 - pr) ** (n - k)


def convolve(pairs):
    dist = [1.0]
    for n, pr in pairs:
        if n == 0:
            continue
        pm = [binom_pmf(n, k, pr) for k in range(n + 1)]
        new = [0.0] * (len(dist) + n)
        for i, a in enumerate(dist):
            if a:
                for k, b in enumerate(pm):
                    new[i + k] += a * b
        dist = new
    return dist


def tail_ge(d, x):
    return sum(d[x:]) if x < len(d) else 0.0


def tail_le(d, x):
    return sum(d[:x + 1])


def sign_p(n_less, n):
    return sum(math.comb(n, k) for k in range(n_less, n + 1)) / 2 ** n


NAME_RE = re.compile(r'^content-(\d{4}-\d{2}-\d{2})([a-z]?)-(\d+)str(?:-oform(?:-(\d+))?)?(?:_(\d+))?$')


def parse(name):
    m = NAME_RE.match(name)
    if not m:
        return None
    ds, letter, pages, variant, nn = m.groups()
    gen = name[:name.rfind('_')] if nn is not None else name
    return dict(date=datetime.date.fromisoformat(ds), letter=letter or 'нет',
                pages=int(pages), variant=variant or '—', gen=gen)


with open(SRC, encoding='utf-8', newline='') as f:
    rows_all = list(csv.DictReader(f))

p('=' * 100)
p('КОНТРПРОВЕРКА №20 (тени/конфаундинг): буква генерации и разрыв «день запуска − дата в имени»')
p('Файл:', os.path.relpath(SRC, REPO), '| доменов в своде:', len(rows_all))
p('=' * 100)


def load(r):
    info = parse(r['набор контента'])
    if info is None:
        return None
    d = dict(info)
    d.update(domain=r['домен'], zone=r['зона'], day_s=r['день запуска'],
             day=datetime.date.fromisoformat(r['день запуска']),
             closed=r['окно закрыто'] == 'да', days=inum(r['дней']),
             oform=r['оформление'] or 'пусто', sites=inum(r['сайтов']),
             sites_w=inum(r['сайтов в окне']), exit3=inum(r['вышли за 3 суток']),
             reg=inum(r['регистраций в окне 3 суток']), fd=inum(r['ФД в окне 3 суток']),
             hour=inum(r['час запуска'], -1), hblock=r['блок часа'],
             acc=r['аккаунт вебмастера'], accfresh=r['аккаунт свежий'],
             pattern=r['паттерн имени'], lab=r['длина метки'],
             regsites=inum(r['сайтов с регистрацией']))
    d['gap'] = (d['day'] - d['date']).days
    return d


fam = [r for r in rows_all if r['семейство'] == FAMILY and r['домен'] not in OUTLIERS
       and r['набор контента'] != NOC]
doms = [x for x in (load(r) for r in fam) if x]
closed = [d for d in doms if d['closed']]

p('\n0. КОНТРОЛЬ ОБЩИХ ТЕНЕЙ (проверяем, а не верим на слово)')
p('  семейство content-дата, окно закрыто: доменов %d, сайтов %d, вышли %d, регистраций %d, ФД %d'
  % (len(closed), sum(d['sites_w'] for d in closed), sum(d['exit3'] for d in closed),
     sum(d['reg'] for d in closed), sum(d['fd'] for d in closed)))
p('  «КОНТЕНТ НЕ ЗАПИСАН» внутри семейства: %d доменов — тень «нет имени набора» ИСКЛЮЧЕНА конструкцией'
  % sum(1 for r in rows_all if r['семейство'] == FAMILY and r['набор контента'] == NOC))
p('  выбросы 3615.team/3286.team внутри семейства: %d — тень выбросов ИСКЛЮЧЕНА'
  % sum(1 for r in rows_all if r['семейство'] == FAMILY and r['домен'] in OUTLIERS))
days = sorted(set(d['day_s'] for d in closed))
p('  дни запуска семейства: %s — ВСЁ сентябрь 12–18, тень «август против сентября» ИСКЛЮЧЕНА'
  % (days[0] + '…' + days[-1]))
p('  зоны: %s' % dict(collections.Counter(d['zone'] for d in closed)))

# ------------------------------------------------------------------ БЛОК 1: буква
key_main = lambda d: '%s %s %dстр %s дата %s' % (d['day_s'], d['zone'], d['pages'], d['oform'], d['date'])
strata = collections.OrderedDict()
for d in sorted(closed, key=lambda d: (d['day_s'], d['zone'], d['gen'])):
    strata.setdefault(key_main(d), []).append(d)
strata = collections.OrderedDict((k, v) for k, v in strata.items()
                                 if len(set(x['letter'] for x in v)) >= 2)

p('\n' + '-' * 100)
p('1. БУКВА: из чего на самом деле состоит контраст')
p('-' * 100)
p('  Страт с ≥2 буквами: %d. Внутри них доменов %d, сайтов %d, регистраций %d.'
  % (len(strata), sum(len(v) for v in strata.values()),
     sum(x['sites_w'] for v in strata.values() for x in v),
     sum(x['reg'] for v in strata.values() for x in v)))
gens_by_letter = collections.defaultdict(set)
for v in strata.values():
    for x in v:
        gens_by_letter[x['letter']].add(x['gen'].replace('content-2026-09-', ''))
for L in ('нет', 'b', 'c'):
    p('   буква %-3s: генераций %d — %s' % (L, len(gens_by_letter[L]), ', '.join(sorted(gens_by_letter[L]))))
p('  ВАЖНО: «c» — это ОДНА дата генерации (14c) в двух-трёх вариантах оформления; «b» — две даты (14b, 17b).')
p('  Значит буква меняется только МЕЖДУ генерациями. Домены одной генерации — не независимые повторы буквы.')

p('\n1а. Баланс страт по неучтённым признакам (час, блок часа, аккаунт, паттерн имени, длина метки)')
for k, v in strata.items():
    p('   %s' % k)
    for L in ('нет', 'b', 'c'):
        sub = [x for x in v if x['letter'] == L]
        if not sub:
            continue
        hrs = sorted(set(x['hour'] for x in sub))
        p('      %-3s доменов %3d | часы %-28s | блоки %-22s | свежий акк: %-12s | паттерны %s'
          % (L, len(sub), (','.join(map(str, hrs)))[:28],
             str(dict(collections.Counter(x['hblock'] for x in sub)))[:22],
             str(dict(collections.Counter(x['accfresh'] for x in sub))),
             str(dict(collections.Counter(x['pattern'] for x in sub)))[:40]))

p('\n1б. НОМЕР ВАРИАНТА ОФОРМЛЕНИЯ — прямой конфаундер буквы')
vc = collections.defaultdict(collections.Counter)
for v in strata.values():
    for x in v:
        vc[x['letter']][x['variant']] += 1
for L in ('нет', 'b', 'c'):
    p('   буква %-3s: варианты (доменов) %s' % (L, dict(sorted(vc[L].items()))))
p('   Внутри страт ищем ПАРЫ с ОДИНАКОВЫМ вариантом и разной буквой:')
matched = collections.Counter()
for k, v in strata.items():
    byvar = collections.defaultdict(set)
    for x in v:
        byvar[x['variant']].add(x['letter'])
    for var, ls in byvar.items():
        for a, b in itertools.combinations(sorted(ls), 2):
            matched[(a, b, var)] += 1
p('   ' + ('; '.join('%s vs %s при варианте %s — в %d стратах' % (a, b, var, n)
                     for (a, b, var), n in sorted(matched.items())) or 'ни одной'))
n_b_vs_net = sum(n for (a, b, var), n in matched.items() if {a, b} == {'b', 'нет'})
p('   ⇒ пар «b против без буквы» при одинаковом варианте: %d. Заявленное «b = 1,58× от «без буквы»»'
  % n_b_vs_net)
p('     построено ИСКЛЮЧИТЕЛЬНО на сравнении разных вариантов оформления:')
p('       14b-oform-2 против 14-oform-1 / -8 / -9 (варианты -8/-9 в реестре уже помечены как худшие)')
p('       17b-oform (БЕЗ номера варианта) против 17-oform-2 (вариант 2)')

# --------- перестановка на уровне ГЕНЕРАЦИИ (правильный кластер)
recs = []
for k, v in strata.items():
    S = sum(x['sites_w'] for x in v)
    E = sum(x['exit3'] for x in v)
    R = sum(x['reg'] for x in v)
    for x in v:
        recs.append(dict(st=k, gen=x['gen'], letter=x['letter'], o=x['exit3'],
                         e=E / S * x['sites_w'], orr=x['reg'], er=R / S * x['sites_w'],
                         s=x['sites_w']))

gen_of_stratum = collections.OrderedDict()
for r in recs:
    gen_of_stratum.setdefault(r['st'], collections.OrderedDict()).setdefault(r['gen'], r['letter'])


def stat(assign):
    """assign: {(stratum, gen): letter} -> словарь статистик"""
    acc = {L: [0.0, 0.0, 0.0, 0.0, 0, 0] for L in ('нет', 'b', 'c')}
    for r in recs:
        a = acc[assign[(r['st'], r['gen'])]]
        a[0] += r['o']; a[1] += r['e']; a[2] += r['orr']; a[3] += r['er']
        a[4] += r['s']; a[5] += 1
    oe = {L: (acc[L][0] / acc[L][1] if acc[L][1] else float('nan')) for L in acc}
    oer = {L: (acc[L][2] / acc[L][3] if acc[L][3] else float('nan')) for L in acc}
    return acc, oe, oer


obs_assign = {(r['st'], r['gen']): r['letter'] for r in recs}
acc0, oe0, oer0 = stat(obs_assign)

p('\n1в. ПЕРЕСТАНОВКА БУКВЫ НА УРОВНЕ ГЕНЕРАЦИИ (а не домена) — полный перебор')
p('   Смысл: буква приписана генерации, а не домену. Автор переставляет букву между доменами —')
p('   это псевдорепликация: 89 доменов «c» это 2–3 генерации, а не 89 независимых наблюдений.')
combos = []
for st, gmap in gen_of_stratum.items():
    gens = list(gmap.keys())
    letters = [gmap[g] for g in gens]
    seen = set()
    opts = []
    for perm in itertools.permutations(letters):
        if perm in seen:
            continue
        seen.add(perm)
        opts.append(dict(zip([(st, g) for g in gens], perm)))
    combos.append(opts)
    p('   страта %-46s генераций %d, различимых перестановок буквы %d' % (st[:46], len(gens), len(opts)))
total = 1
for o in combos:
    total *= len(o)
p('   всего комбинаций: %d (перебираются все)' % total)

targets = {
    'O/E выход c': lambda oe, oer: oe['c'],
    'c / нет (выход)': lambda oe, oer: oe['c'] / oe['нет'] if oe['нет'] else float('nan'),
    'b / нет (выход)': lambda oe, oer: oe['b'] / oe['нет'] if oe['нет'] else float('nan'),
    'c / b (выход)': lambda oe, oer: oe['c'] / oe['b'] if oe['b'] else float('nan'),
    'O/E рег c': lambda oe, oer: oer['c'],
    'рег c / рег нет': lambda oe, oer: oer['c'] / oer['нет'] if oer['нет'] else float('nan'),
}
obs_vals = {k: f(oe0, oer0) for k, f in targets.items()}
cnt = {k: 0 for k in targets}
val = {k: 0 for k in targets}
for prod in itertools.product(*combos):
    assign = {}
    for d in prod:
        assign.update(d)
    _, oe, oer = stat(assign)
    for k, f in targets.items():
        x = f(oe, oer)
        if math.isnan(x) or math.isnan(obs_vals[k]):
            continue
        val[k] += 1
        if x >= obs_vals[k]:
            cnt[k] += 1
p('   Статистика            наблюдено   p (доля комбинаций ≥ наблюдённой)   p у автора (перестановка доменов)')
author_p = {'O/E выход c': 0.0000, 'c / нет (выход)': 0.0000, 'b / нет (выход)': 0.0000,
            'c / b (выход)': 0.0140, 'O/E рег c': 0.0006, 'рег c / рег нет': float('nan')}
for k in targets:
    ap = author_p.get(k, float('nan'))
    p('   %-22s %9.2f   %-34s %s' % (k, obs_vals[k], '%.4f' % (cnt[k] / val[k]) if val[k] else '—',
                                     ('%.4f' % ap) if not math.isnan(ap) else '—'))

p('\n1г. Leave-one-generation-out: держится ли «буква c» без каждой из своих генераций')
for drop in sorted(gens_by_letter['c']):
    full = 'content-2026-09-' + drop
    sub_recs = [r for r in recs if r['gen'] != full]
    accd = {L: [0.0, 0.0, 0.0, 0.0, 0] for L in ('нет', 'b', 'c')}
    for r in sub_recs:
        a = accd[r['letter']]
        a[0] += r['o']; a[1] += r['e']; a[2] += r['orr']; a[3] += r['er']; a[4] += r['s']
    oec = accd['c'][0] / accd['c'][1] if accd['c'][1] else float('nan')
    oen = accd['нет'][0] / accd['нет'][1] if accd['нет'][1] else float('nan')
    p('   без %-22s: c O/E выход %.2f (c/нет %.2f), регистраций c %d при ожидании %.1f (O/E %s), рег/100 c %s'
      % (drop, oec, oec / oen if oen else float('nan'), int(accd['c'][2]), accd['c'][3],
         r2(accd['c'][2], accd['c'][3]), per100(accd['c'][2], accd['c'][4])))

p('\n1д. Откуда берутся 24 регистрации группы «c» (кластеризация денег)')
creg = [x for v in strata.values() for x in v if x['letter'] == 'c']
nz = [x for x in creg if x['reg'] > 0]
p('   доменов «c» в стратах: %d, сайтов %d; регистраций %d на %d доменах (%.0f%% доменов «c» дали 0)'
  % (len(creg), sum(x['sites_w'] for x in creg), sum(x['reg'] for x in creg), len(nz),
     100.0 * (len(creg) - len(nz)) / len(creg)))
top = sorted(creg, key=lambda x: -x['reg'])[:5]
p('   топ-5 доменов «c» по регистрациям: %s — это %d из %d регистраций группы'
  % (', '.join('%s (%s, %d рег)' % (x['domain'], x['gen'].replace('content-2026-09-', ''), x['reg']) for x in top),
     sum(x['reg'] for x in top), sum(x['reg'] for x in creg)))
netreg = [x for v in strata.values() for x in v if x['letter'] == 'нет']
p('   для сравнения «без буквы»: доменов %d, сайтов %d, регистраций %d на %d доменах'
  % (len(netreg), sum(x['sites_w'] for x in netreg), sum(x['reg'] for x in netreg),
     sum(1 for x in netreg if x['reg'] > 0)))
p('   из них 14-7str-oform-9 (вариант 9, в реестре худший): доменов %d, сайтов %d, регистраций %d'
  % (sum(1 for x in netreg if 'oform-9' in x['gen']), sum(x['sites_w'] for x in netreg if 'oform-9' in x['gen']),
     sum(x['reg'] for x in netreg if 'oform-9' in x['gen'])))


p('\n1е. ТЕНЬ «ЧАС ЗАПУСКА / ПОРЯДОК ПАРТИИ ВНУТРИ ДНЯ» (в стратах буква почти совпадает с часовым окном)')
p('   1е-1. Есть ли вообще градиент по часу ВНУТРИ одной генерации × день × зона (медианный сплит):')
gg = collections.defaultdict(list)
for d in closed:
    gg[(d['gen'], d['day_s'], d['zone'])].append(d)
OO = 0; EE = 0.0; ng = 0; ratios = []
for k, v in gg.items():
    if len(v) < 8:
        continue
    hs = sorted(x['hour'] for x in v); med = hs[len(v) // 2]
    early = [x for x in v if x['hour'] < med]; late = [x for x in v if x['hour'] >= med]
    if len(early) < 3 or len(late) < 3:
        continue
    ng += 1
    se = sum(x['sites_w'] for x in early); sl = sum(x['sites_w'] for x in late)
    r_e = sum(x['exit3'] for x in early) / se; r_l = sum(x['exit3'] for x in late) / sl
    ratios.append(r_l / r_e if r_e else float('nan'))
    OO += sum(x['exit3'] for x in late)
    EE += (sum(x['exit3'] for x in v) / sum(x['sites_w'] for x in v)) * sl
p('      групп %d; поздняя половина: вышли %d при ожидании %.1f, O/E = %.3f; групп с поздние>ранние: %d из %d'
  % (ng, OO, EE, OO / EE, sum(1 for r in ratios if r > 1), ng))
p('      ⇒ систематического преимущества поздних часов ВНУТРИ генерации нет — час/порядок партии сам по себе не двигает выход')
p('   1е-2. Буква × часовой блок ВНУТРИ пяти страт буквы:')
hb = collections.defaultdict(lambda: [0, 0])
for v in strata.values():
    for x in v:
        blk = '00-05' if x['hour'] < 6 else '06-11' if x['hour'] < 12 else '12-17' if x['hour'] < 18 else '18-23'
        a = hb[(blk, x['letter'])]; a[0] += x['exit3']; a[1] += x['sites_w']
p('      %-7s %-12s %-12s %-12s' % ('блок', 'нет', 'b', 'c'))
for blk in ('00-05', '06-11', '12-17', '18-23'):
    cells = []
    for L in ('нет', 'b', 'c'):
        a = hb.get((blk, L))
        cells.append('%s (%d)' % (r3(a[0], a[1]), a[1]) if a and a[1] else '—')
    p('      %-7s %-12s %-12s %-12s' % (blk, cells[0], cells[1], cells[2]))
p('      ⇒ «c» выше «без буквы» в КАЖДОМ часовом блоке — тень часа/порядка партии НЕ объясняет букву')

p('\n1ж. «Без буквы» без заведомо худших вариантов -8/-9 (реестр помечает их как худшие)')
accx = {L: [0, 0.0, 0, 0.0, 0] for L in ('нет', 'b', 'c')}
for r in recs:
    if r['letter'] == 'нет' and ('oform-8' in r['gen'] or 'oform-9' in r['gen']):
        continue
    a = accx[r['letter']]
    a[0] += r['o']; a[1] += r['e']; a[2] += r['orr']; a[3] += r['er']; a[4] += r['s']
for L in ('нет', 'b', 'c'):
    a = accx[L]
    p('   %-3s: доменов-сайтов %6d, вышли %5d при ожидании %7.1f, O/E %s | рег %2d при ожидании %5.2f, O/E %s, рег/100 %s'
      % (L, a[4], a[0], a[1], r2(a[0], a[1]), a[2], a[3], r2(a[2], a[3]), per100(a[2], a[4])))
oen = accx['нет'][0] / accx['нет'][1]
p('   c / «без буквы» = %.2f (было 1,92 со слабыми вариантами); b / «без буквы» = %.2f (было 1,58)'
  % (accx['c'][0] / accx['c'][1] / oen, accx['b'][0] / accx['b'][1] / oen))
p('   рег/100: c %s против «без буквы» %s — отношение %.1f× (было 4,2×)'
  % (per100(accx['c'][2], accx['c'][4]), per100(accx['нет'][2], accx['нет'][4]),
     (accx['c'][2] / accx['c'][4]) / (accx['нет'][2] / accx['нет'][4]) if accx['нет'][2] else float('nan')))

# ------------------------------------------------------------------ БЛОК 2: разрыв
p('\n' + '-' * 100)
p('2. РАЗРЫВ: дневной коэффициент — не тень ли он самого проверяемого контента')
p('-' * 100)


def day_coef_own(items, exclude_gen=None):
    acc = collections.defaultdict(lambda: [0, 0])
    for d in items:
        if d['gap'] <= 1 and (exclude_gen is None or d['gen'] != exclude_gen):
            a = acc[(d['day_s'], d['zone'], d['pages'])]
            a[0] += d['exit3']; a[1] += d['sites_w']
    return {k: v[0] / v[1] for k, v in acc.items() if v[1] > 0}


# независимый дневной коэффициент: семейство nabory (другой контент, те же дни/зоны)
nab = collections.defaultdict(lambda: [0, 0])
for r in rows_all:
    if r['семейство'] == 'nabory' and r['окно закрыто'] == 'да' and r['домен'] not in OUTLIERS:
        a = nab[(r['день запуска'], r['зона'])]
        a[0] += inum(r['вышли за 3 суток']); a[1] += inum(r['сайтов в окне'])
nab_day = {k: v[0] / v[1] for k, v in nab.items() if v[1] > 0}
nab_n = {k: v[1] for k, v in nab.items()}

dc_own = day_coef_own(closed)
p('\n2а. Два дневных коэффициента на одни и те же дни/зоны')
p('   %-22s %-10s %-10s %-10s' % ('день / зона', 'd(content,', 'd(nabory,', 'сайтов'))
p('   %-22s %-10s %-10s %-10s' % ('', 'свежие)', 'независ.)', 'nabory'))
for day in sorted(set(d['day_s'] for d in closed)):
    for z in ('lol', 'team'):
        k7 = (day, z, 7)
        own = dc_own.get(k7)
        ind = nab_day.get((day, z))
        if own is None and ind is None:
            continue
        p('   %-22s %-10s %-10s %-10s' % ('%s %s' % (day, z),
                                          '%.3f' % own if own else '—',
                                          '%.3f' % ind if ind else '—',
                                          nab_n.get((day, z), 0)))
p('   Корреляция дней между двумя коэффициентами (по 7стр, где есть оба):')
both = [(dc_own[(d, z, 7)], nab_day[(d, z)]) for d in sorted(set(x['day_s'] for x in closed))
        for z in ('lol', 'team') if (d, z, 7) in dc_own and (d, z) in nab_day]
if len(both) > 2:
    n = len(both)
    mx = sum(a for a, _ in both) / n
    my = sum(b for _, b in both) / n
    cov = sum((a - mx) * (b - my) for a, b in both)
    sx = math.sqrt(sum((a - mx) ** 2 for a, _ in both))
    sy = math.sqrt(sum((b - my) ** 2 for _, b in both))
    p('   Пирсон r = %.2f по %d точкам (день×зона). Если бы «день» был общей силой, r был бы высоким.'
      % (cov / (sx * sy) if sx and sy else float('nan'), n))


def gap_pairs(items, mode, dc=None):
    """mode: 'own' — d по свежим content; 'nabory' — d по независимому семейству; 'none' — без поправки."""
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
        s_f = sum(d['sites_w'] for d in fresh)
        r_f = sum(d['exit3'] for d in fresh) / s_f

        def coef(d):
            if mode == 'none':
                return 1.0
            if mode == 'own':
                return dc.get((d['day_s'], d['zone'], pages))
            return nab_day.get((d['day_s'], d['zone']))

        cf = [coef(d) for d in fresh]
        if any(c is None for c in cf):
            continue
        d_f = sum(c * d['sites_w'] for c, d in zip(cf, fresh)) / s_f
        o = e = 0
        e = 0.0
        s_old = 0
        skipped = 0
        for d in old:
            c = coef(d)
            if c is None:
                skipped += 1
                continue
            o += d['exit3']
            e += r_f * (c / d_f) * d['sites_w']
            s_old += d['sites_w']
        if s_old == 0:
            continue
        out.append(dict(gen=g, zone=z, o=o, e=e, s_old=s_old, s_f=s_f, r_f=r_f,
                        n_old=len(old), n_f=len(fresh), skipped=skipped,
                        reg_f=sum(d['reg'] for d in fresh), reg_o=sum(d['reg'] for d in old),
                        gaps_o=sorted(set(d['gap'] for d in old))))
    return out


def report_pairs(title, prs, show=True):
    if not prs:
        p('\n' + title); p('   пар нет'); return None
    O = sum(x['o'] for x in prs)
    E = sum(x['e'] for x in prs)
    nl = sum(1 for x in prs if x['o'] / x['e'] < 1)
    p('\n' + title)
    if show:
        p('   %-32s %-5s %5s %6s %8s %8s %6s' % ('генерация', 'зона', 'дом', 'сайтов', 'вышли', 'ожид.', 'O/E'))
        for x in sorted(prs, key=lambda y: y['o'] / y['e']):
            p('   %-32s %-5s %5d %6d %8d %8.1f %6.2f' % (x['gen'].replace('content-2026-09-', ''), x['zone'],
                                                         x['n_old'], x['s_old'], x['o'], x['e'], x['o'] / x['e']))
    p('   ИТОГО: пар %d, старых доменов %d, сайтов %d, вышли %d, ожидание %.1f, O/E = %.3f; пар с O/E<1: %d/%d (знаковый p = %.3f)'
      % (len(prs), sum(x['n_old'] for x in prs), sum(x['s_old'] for x in prs), O, E, O / E, nl, len(prs),
         sign_p(nl, len(prs))))
    # кластерный интервал: лог-отношения по парам, вес = ожидание
    logs = [(math.log(x['o'] / x['e']), x['e']) for x in prs if x['o'] > 0]
    W = sum(w for _, w in logs)
    m = sum(l * w for l, w in logs) / W
    # джекнайф по парам
    js = []
    for i in range(len(logs)):
        rest = logs[:i] + logs[i + 1:]
        Wr = sum(w for _, w in rest)
        js.append(sum(l * w for l, w in rest) / Wr)
    nj = len(js)
    mj = sum(js) / nj
    se = math.sqrt((nj - 1) / nj * sum((x - mj) ** 2 for x in js)) if nj > 1 else float('nan')
    p('   Кластерный (по парам) взвешенный log O/E = %.3f ⇒ O/E = %.2f; джекнайф-SE = %.3f; 95%% ДИ O/E = [%.2f; %.2f]'
      % (m, math.exp(m), se, math.exp(m - 1.96 * se), math.exp(m + 1.96 * se)))
    # leave-one-pair-out по пулу
    loo = []
    for i in range(len(prs)):
        rest = prs[:i] + prs[i + 1:]
        loo.append((sum(x['o'] for x in rest) / sum(x['e'] for x in rest), prs[i]['gen'], prs[i]['zone']))
    lo = min(loo); hi = max(loo)
    p('   Leave-one-pair-out пула: от %.2f (без %s %s) до %.2f (без %s %s)'
      % (lo[0], lo[1].replace('content-2026-09-', ''), lo[2], hi[0], hi[1].replace('content-2026-09-', ''), hi[2]))
    return O / E, math.exp(m), math.exp(m - 1.96 * se), math.exp(m + 1.96 * se), nl, len(prs)


res_own = report_pairs('2б. ВОСПРОИЗВЕДЕНИЕ автора: d(день) по свежим генерациям самого content-дата', gap_pairs(closed, 'own', dc_own))
res_nab = report_pairs('2в. ТА ЖЕ СХЕМА, но d(день) — по НЕЗАВИСИМОМУ семейству nabory (тот же день, та же зона, другой контент)',
                       gap_pairs(closed, 'nabory'))
res_none = report_pairs('2г. Без поправки на день (день + разрыв вместе)', gap_pairs(closed, 'none'), show=False)

p('\n2д. Совместные чувствительности (жёсткая страта: убираем сразу обе подозрительные группы)')
sub = [d for d in closed if d['date'] != datetime.date(2026, 9, 12) and d['days'] >= 2]
report_pairs('   без генераций даты 12.09 И без доменов с «дней»=1, d по свежим content', gap_pairs(sub, 'own', day_coef_own(sub)), show=True)
report_pairs('   то же, но d по независимому nabory', gap_pairs(sub, 'nabory'), show=False)

p('\n2е. Разрыв 2 отдельно от разрыва 3 (в «старых» смешаны 2 и 3)')
for gmin, gmax in ((2, 2), (3, 4)):
    sel = [d for d in closed if d['gap'] <= 1 or gmin <= d['gap'] <= gmax]
    r = gap_pairs(sel, 'own', dc_own)
    if r:
        O = sum(x['o'] for x in r); E = sum(x['e'] for x in r)
        p('   разрыв %d–%d: пар %d, доменов %d, сайтов %d, O/E = %.2f'
          % (gmin, gmax, len(r), sum(x['n_old'] for x in r), sum(x['s_old'] for x in r), O / E))

p('\n2ж. Деньги по разрыву (внутри пар автора)')
prs = gap_pairs(closed, 'own', dc_own)
sf = sum(x['s_f'] for x in prs); so = sum(x['s_old'] for x in prs)
rf = sum(x['reg_f'] for x in prs); ro = sum(x['reg_o'] for x in prs)
p('   свежие: сайтов %d, регистраций %d (%s на 100); старые: сайтов %d, регистраций %d (%s на 100); отношение %.2f'
  % (sf, rf, per100(rf, sf), so, ro, per100(ro, so), (ro / so) / (rf / sf) if rf and so else float('nan')))
dist = convolve([(x['reg_f'] + x['reg_o'], x['s_old'] / (x['s_f'] + x['s_old'])) for x in prs])
exp = sum((x['reg_f'] + x['reg_o']) * x['s_old'] / (x['s_f'] + x['s_old']) for x in prs)
p('   точный дележ пропорционально сайтам: ожидание старых %.2f, наблюдено %d, P(X ≤ набл.) = %.4f — НЕ значимо'
  % (exp, ro, tail_le(dist, ro)))
p('   5 из 9 регистраций «старых» — одна генерация 15-7str-oform-1 .team на 17.09; без неё старых остаётся %d.'
  % (ro - 5))

p('\n' + '=' * 100)
p('ИТОГ КОНТРПРОВЕРКИ')
p('=' * 100)
p("""1. БУКВА — что осталось и что оказалось тенью.
   Тень ЧАСА/ПОРЯДКА ПАРТИИ: не подтвердилась. Внутри генерации поздние по часу домены идут вровень
     с ранними (O/E 1,013 на 29 группах), и «c» выше «без буквы» в каждом часовом блоке.
   Тень НОМЕРА ВАРИАНТА: подтвердилась для ДЕНЕГ и для «b».
     — пар «b против без буквы при одинаковом варианте» в данных НЕТ ни одной: 14b-oform-2 сравнивается
       с 14-oform-1/-8/-9, 17b-oform (без номера) — с 17-oform-2. Заявленные 1,58× — контраст вариантов.
     — если убрать из «без буквы» заведомо худшие варианты -8/-9, первая генерация перестаёт быть
       денежно провальной (O/E регистраций 0,81 вместо 0,36), и отрыв c по деньгам падает
       с 4,2× до 2,5× (0,131 против 0,053 рег/100 сайтов).
   ПСЕВДОРЕПЛИКАЦИЯ: подтвердилась. Буква приписана генерации, а не домену; при полном переборе
     перестановок буквы на уровне генерации (21600 комбинаций) p растут: O/E выход c 0,0000 -> 0,0333;
     b/нет 0,0000 -> 0,0341; c/b 0,0140 -> 0,2211 (перестаёт быть значимым); O/E регистраций c
     0,0006 -> 0,0333. Устойчиво значимым остаётся только c/«без буквы» = 1,92 (p = 0,0005).
   ВЫВОД по букве: «повторная генерация лучше первой» как правило — не доказано (b неотделима от
     варианта, c от b не отличается). Выживает узкое: одна генерация content-2026-09-14c выходит
     в поиск примерно вдвое чаще первой генерации той же даты в той же страте.""")
p("""2. РАЗРЫВ — эффект не выживает жёсткой страты.
   Дневной коэффициент у автора построен по свежим генерациям ТОГО ЖЕ семейства content-дата,
     то есть по тому же контенту, что проверяется. Независимый коэффициент по семейству nabory
     (те же дни, те же зоны, другой контент) коррелирует с авторским всего на r = 0,39 по 13 точкам:
     «день» как общая сила не опознаётся. Итог O/E скачет по спецификациям: 0,72 (без поправки),
     0,82 (автор), 0,80 (leave-one-out), 0,47 (независимый день) — при разбросе по парам от 0,16 до 5,30.
   Кластер — пара, а не домен. По 12 парам: знаковый критерий 9/12, p = 0,073 (не значимо);
     взвешенный кластерный O/E 0,77 с 95% ДИ [0,61; 0,97] — впритык.
   ЖЁСТКАЯ СТРАТА (без генераций даты 12.09 и без доменов с «дней» = 1): пар 7, доменов 86,
     O/E = 0,87, кластерный 0,84, 95% ДИ [0,68; 1,05] — НАКРЫВАЕТ 1; знаковый 5/7, p = 0,227.
   Деньги: 9 регистраций у старых против 23 у свежих, P = 0,080 — не значимо, и 5 из 9 регистраций
     старых дала одна генерация 15-7str-oform-1 .team на 17.09.
   ВЫВОД по разрыву: направление держится, но величина не определена, а значимость исчезает,
     как только убрать две самые влиятельные группы. «Старые партии на 18 % хуже» — переоценка.""")
TEE.flush()

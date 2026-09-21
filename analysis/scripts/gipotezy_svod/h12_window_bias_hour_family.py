#!/usr/bin/env python3
"""
Гипотеза №12. Окно «3 календарных суток» — неровная линейка: у вечерних запусков
(18–23) оно захватывает ~50 часов вместо 72, а у семейств с длинным хвостом поиска
(archive, NEW — захват кликов 60–70 %) — меньшую долю денег, чем у Generator/nabory
(82–86 %); оконная метрика занижает вечерние домены на ~1/5 и медленные семейства
на 20–35 %.

Что проверяем.
  0. Саму линейку: что именно считается «окном 3 суток» в своде и сколько часов оно
     даёт домену, запущенному в разные часы.
  (а) Час запуска: зависит ли от блока часа доля регистраций домена, попавшая в окно
      (и доля регистраций на 3-х и 4-х сутках), и меняет ли «исправленное» окно
      сравнение блоков часа и рейтинг наборов/пулов.
  (б) Семейства: захватывает ли окно у archive/NEW меньшую долю поисковых кликов и
      регистраций, чем у Generator/nabory; держится ли это после контроля часа и
      поздних выходов; насколько сдвигается рейтинг семейств при переходе от
      оконных регистраций к регистрациям за всё время.

Как проверяем.
  Линейка. По analysis/scripts/okno_3sutok.py окно сайта = сутки переобхода плюс трое
  следующих включительно, т.е. смещения 0..3 от дня переобхода сайта (4 календарных
  дня; у сайтов 2-й волны переобход на день позже — смещения 1..4 от дня запуска
  домена). Сверяем со сводом: «регистраций в окне 3 суток» против суммы регистраций
  на смещениях 0..3 от дня запуска, восстановленной из колонки «даты регистраций».
  Фактическая длина окна для запуска в час h: от h до конца 3-х суток = 96 − h часов.

  Фильтры: окно закрыто = да; дней = 2; без 3615.team и 3286.team; без
  «КОНТЕНТ НЕ ЗАПИСАН» (для части (а) есть дополнительный проход с ним, потому что
  цифры постановки его включали; в пуле он остаётся собственной стратой).
  Часть (а): возраст ≥7 суток (день запуска ≤ 2026-09-14). Часть (б): по постановке
  возраст ≥14 (≤ 2026-09-07), но семейство archive целиком запущено 08–11.09 и в этом
  срезе отсутствует, поэтому основной срез — возраст ≥10 (≤ 2026-09-11), срез ≥14
  показан рядом; хвост на возрасте ≥10 собран на ~93 % (проверено по старым доменам).

  (а) На домен: r_k — регистраций на смещении k суток от дня запуска (k = 0..4, 5+),
      tail = регистраций − регистраций в окне (по своду). По блокам часа и по часу
      шагом 3: share3 = Σr3/Σ(r0..r3), share4 = Σr4/Σ(r0..r4), доля хвоста =
      Σtail/Σрегистраций; точные биномиальные ДИ (Клоппер–Пирсон). Перестановочный
      тест: 10 000 раз (random.seed(1)) перемешать блок часа между доменами внутри
      пула «набор контента + день запуска»; статистики — отношения share3, share4 и
      доли хвоста у 18–23 к 00–11 и к остальным блокам. Альтернативные окна от дня
      запуска: 0..2, 0..3 (≈ свод), 0..4, «план» (0..3 при часе ≥18, иначе 0..2) и
      «вечерним +1 день» (0..4 при часе ≥18, иначе 0..3). Для каждого: регистраций по
      блокам; сколько прибавляется/убавляется вечерним и остальным против свода;
      O/E по блокам внутри пулов (E = ставка пула на сайт × сайтов домена);
      Спирмен рангов наборов (≥5 доменов) и пулов (≥5 доменов) по рег/100 сайтов
      между сводным окном и альтернативой.
  (б) Захват = кликов из поиска в окне / из поиска: сумма и медиана по семействам и
      по пулам (≥8 доменов). Доля хвоста по семействам с ДИ. Перестановочный тест
      на максимальное отклонение: 10 000 раз перемешать метку семейства между
      доменами внутри страт «день запуска × блок часа»; статистика — максимум
      |доля хвоста семейства − общая доля| по семействам с ≥4 регистраций, считается
      только по стратам, где метка реально переставляется (≥2 семейства и есть
      регистрации; семейство, запущенное в одиночку в свой день, иначе задаёт максимум
      навсегда); отдельно — отношение доли хвоста archive+NEW к остальным. Контроль механизмов: E хвоста
      домена = ставка ячейки × регистраций домена, ячейки — «блок часа», «блок часа ×
      поздние выходы (0 / 1–3 / ≥4, где поздние = вышли за 7 суток − вышли за 3)»
      и «день запуска × блок часа»; O/E по семействам и Монте-Карло p (10 000
      биномиальных розыгрышей хвоста по ячейкам). Внутри NEW — по наборам (≥5
      доменов), оформлению, страницам. Разрез по захвату кликов домена (бины) — в
      целом и внутри NEW. Два рейтинга семейств: рег в окне / 100 сайтов и рег за
      всё время / 100 сайтов, сдвиг в %, отношения NEW и archive к Generator и nabory.

Критерии постановки: (а) share3(18–23)/share3(00–11) ≥ 1,5 при p < 0,05 и добавка
вечерним ≥10 % их оконных регистраций; (б) хвост archive/NEW ≥ 2× остальных при
p < 0,05, O/E ≥ 1,5 после контроля часа и поздних выходов, рейтинг сдвигается ≥20 %;
иначе — окно честное для всех.
"""
import collections
import csv
import datetime
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, 'analysis', 'export', 'svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h12_window_bias_hour_family.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
REF = datetime.date(2026, 9, 21)
CUT_HOUR = datetime.date(2026, 9, 14)    # возраст >= 7 суток
CUT_FAM = datetime.date(2026, 9, 11)     # возраст >= 10 суток (archive запущен 08–11.09)
CUT_FAM14 = datetime.date(2026, 9, 7)    # возраст >= 14 суток по постановке
NSIM = 10000
BLOCKS = ('00-05', '06-11', '12-17', '18-23')
KMAX = 5                                  # смещения 0..4 и «5+»


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def write(self, s):
        sys.__stdout__.write(s)
        self.f.write(s)

    def flush(self):
        sys.__stdout__.flush()
        self.f.flush()


def iv(x):
    return int(x) if x not in ('', None) else 0


def dparse(s):
    return datetime.date.fromisoformat(s)


def pct(k, n):
    return 100.0 * k / n if n else float('nan')


def fmt(x, nd=2):
    return ('%.' + str(nd) + 'f') % x if x == x and x not in (float('inf'),) else '—'


def binom_cdf(k, n, p):
    """P(X <= k) для X ~ Bin(n, p)."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    lp, lq = math.log(p), math.log(1 - p)
    s = 0.0
    for i in range(k + 1):
        s += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                      + i * lp + (n - i) * lq)
    return min(1.0, s)


def cp_ci(k, n, alpha=0.05):
    """Точный биномиальный ДИ Клоппера–Пирсона для доли k/n."""
    if n == 0:
        return float('nan'), float('nan')
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, 1.0
        for _ in range(50):
            m = (a + b) / 2
            if 1 - binom_cdf(k - 1, n, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    if k == n:
        hi = 1.0
    else:
        a, b = 0.0, 1.0
        for _ in range(50):
            m = (a + b) / 2
            if binom_cdf(k, n, m) > alpha / 2:
                a = m
            else:
                b = m
        hi = (a + b) / 2
    return lo, hi


def ci_str(k, n):
    lo, hi = cp_ci(k, n)
    return '%.0f%% [%.0f–%.0f]' % (pct(k, n), 100 * lo, 100 * hi) if n else '—'


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for t in range(i, j + 1):
            r[order[t]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    if len(xs) < 3:
        return float('nan')
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float('nan')


def ratio(a, b):
    return a / b if b else float('nan')


def ratio_ci(k1, n1, k2, n2):
    """Отношение двух долей k1/n1 : k2/n2 с приближённым 95 % ДИ (лог-метод)."""
    if not (k1 and n1 and k2 and n2):
        return '—'
    r = (k1 / n1) / (k2 / n2)
    se = math.sqrt(max(1 / k1 - 1 / n1 + 1 / k2 - 1 / n2, 0.0))
    return '%.2f [%.2f–%.2f]' % (r, r * math.exp(-1.96 * se), r * math.exp(1.96 * se))


def pval(count, nsim):
    return (count + 1) / (nsim + 1)


def late_group(d):
    late = d['hit7'] - d['hit3']
    return '0' if late <= 0 else ('1-3' if late <= 3 else '>=4')


# ---------------------------------------------------------------- загрузка
def load():
    doms = []
    with open(SRC, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            d0 = dparse(r['день запуска'])
            offs = [(dparse(x) - d0).days for x in r['даты регистраций'].split()]
            rk = [0] * (KMAX + 1)
            for k in offs:
                rk[min(max(k, 0), KMAX)] += 1
            reg, wreg = iv(r['регистраций']), iv(r['регистраций в окне 3 суток'])
            doms.append(dict(
                dom=r['домен'], zone=r['зона'], day=r['день запуска'], d0=d0,
                age=(REF - d0).days, ndays=r['дней'], closed=r['окно закрыто'] == 'да',
                content=r['набор контента'], fam=r['семейство'],
                pages=r['страниц'] or 'пусто', oform=r['оформление'] or 'пусто',
                hour=iv(r['час запуска']), block=r['блок часа'],
                sites=iv(r['сайтов']), reg=reg, wreg=wreg, tail=reg - wreg,
                fd=iv(r['ФД']), wfd=iv(r['ФД в окне 3 суток']),
                ya=iv(r['из поиска']), wya=iv(r['кликов из поиска в окне']),
                hit3=iv(r['вышли за 3 суток']), hit7=iv(r['вышли за 7 суток']),
                rk=rk, nreg_dates=len(offs)))
    return doms


def apply_filters(doms):
    print('Всего строк в своде: %d' % len(doms))
    n0 = len(doms)
    doms = [d for d in doms if d['dom'] not in OUTLIERS]
    print('  исключены выбросы 3615.team и 3286.team: %d' % (n0 - len(doms)))
    n0 = len(doms)
    doms = [d for d in doms if d['closed']]
    print('  исключены с незакрытым окном (окно закрыто = нет): %d' % (n0 - len(doms)))
    n0 = len(doms)
    doms = [d for d in doms if d['ndays'] == '2']
    print('  исключены с дней ≠ 2 (150 сайтов без 2-го дня или 3 дня): %d' % (n0 - len(doms)))
    nc = [d for d in doms if d['content'] == NOCONTENT]
    print('  «КОНТЕНТ НЕ ЗАПИСАН» в остатке: %d (исключается из основных срезов, '
          'для части (а) — отдельный проход)' % len(nc))
    print('  осталось доменов (с «не записан»): %d' % len(doms))
    return doms


# ---------------------------------------------------------------- часть 0
def part0(base):
    print('\n' + '=' * 78)
    print('0. ЛИНЕЙКА: ЧТО ТАКОЕ «ОКНО 3 СУТОК» В СВОДЕ')
    print('=' * 78)
    print('По okno_3sutok.py окно сайта = сутки переобхода + трое следующих включительно,')
    print('т.е. смещения 0..3 от дня переобхода сайта (4 календарных дня).')
    print('Сверка со сводом на доменах с регистрациями (окно закрыто, дней = 2, без выбросов):')
    c = collections.Counter()
    for d in base:
        if d['reg'] == 0:
            c['без регистраций'] += 1
            continue
        s02, s03, s04 = sum(d['rk'][:3]), sum(d['rk'][:4]), sum(d['rk'][:5])
        s13 = sum(d['rk'][1:4])
        if d['wreg'] == s03:
            c['в окне = Σ r0..r3'] += 1
        elif d['wreg'] > s03 and d['wreg'] <= s04:
            c['в окне > Σ r0..r3 (сайт 2-й волны, окно 1..4)'] += 1
        elif d['wreg'] < s03 and d['wreg'] >= s13:
            c['в окне < Σ r0..r3 (рег. в день 0 на сайте 2-й волны, вне его окна)'] += 1
        else:
            c['иное'] += 1
        if d['wreg'] == s02 and d['rk'][3] > 0:
            c['из них неоднозначных: в окне = Σ r0..r2 при r3 > 0 (может быть и 2-я волна)'] += 1
    for k, v in c.most_common():
        print('  %-70s %5d' % (k, v))
    nreg = sum(1 for d in base if d['reg'])
    print('  доменов с регистрациями: %d; сумма регистраций по «даты регистраций» = '
          'колонке «регистраций» у всех %d' % (nreg, sum(1 for d in base if d['nreg_dates'] == d['reg'])))
    print('\nВывод по линейке: регистрация 3-х суток (смещение 3) ВНУТРИ окна; вне окна — ')
    print('смещения ≥4 (и день 0 у сайтов 2-й волны). Постановка считала день 3 «за окном».')
    print('\nФактическая длина окна по часу запуска (сайт 1-й волны): 96 − час, часов:')
    for b in BLOCKS:
        lo, hi = [int(x) for x in b.split('-')]
        print('  блок %s: %d–%d ч (постановка: у 18–23 «~50 ч вместо 72»)' % (b, 96 - hi, 96 - lo))
    print('  «3 календарных суток» (0..2) дало бы 49–72 ч; 0..3 даёт всем ≥73 ч.')
    print('  Разрыв 18–23 против 00–05 по часам: %.2f (73–78 против 91–96), а не 50/72 = 0,69.'
          % (75.5 / 93.5))
    print('  Час регистрации в своде отсутствует — окно ровно в 72 ч от постановки')
    print('  посчитать нельзя, только календарные варианты.')


# ---------------------------------------------------------------- часть (а)
def block_row(ds):
    rk = [sum(d['rk'][k] for d in ds) for k in range(KMAX + 1)]
    reg = sum(d['reg'] for d in ds)
    wreg = sum(d['wreg'] for d in ds)
    tail = reg - wreg
    return dict(n=len(ds), sites=sum(d['sites'] for d in ds), reg=reg, wreg=wreg, tail=tail,
                rk=rk, s03=sum(rk[:4]), s04=sum(rk[:5]))


def print_block_table(D, title, by='block'):
    print('\n%s' % title)
    print('  %-7s %6s %7s %5s %6s %5s  %-14s | %4s %4s %4s %4s %4s %4s | %-15s %-15s'
          % ('срез', 'домен.', 'сайтов', 'рег', 'в окне', 'хвост', 'хвост % [ДИ]',
             'r0', 'r1', 'r2', 'r3', 'r4', 'r5+', 'share3 % [ДИ]', 'share4 % [ДИ]'))
    if by == 'block':
        keys = [(b, [d for d in D if d['block'] == b]) for b in BLOCKS]
    else:
        keys = [('%02d-%02d' % (h, h + 2), [d for d in D if h <= d['hour'] <= h + 2]) for h in range(0, 24, 3)]
    keys.append(('всего', D))
    for name, ds in keys:
        t = block_row(ds)
        print('  %-7s %6d %7d %5d %6d %5d  %-14s | %4d %4d %4d %4d %4d %4d | %-15s %-15s'
              % (name, t['n'], t['sites'], t['reg'], t['wreg'], t['tail'], ci_str(t['tail'], t['reg']),
                 t['rk'][0], t['rk'][1], t['rk'][2], t['rk'][3], t['rk'][4], t['rk'][5],
                 ci_str(t['rk'][3], t['s03']), ci_str(t['rk'][4], t['s04'])))


def stats_from_acc(acc):
    """acc[block] = [r3, s03, r4, s04, tail, reg]. Возвращает набор отношений 18–23 к 00–11 и к остальным."""
    def agg(blocks):
        return [sum(acc[b][i] for b in blocks) for i in range(6)]
    ev = agg(['18-23'])
    night = agg(['00-05', '06-11'])
    rest = agg(['00-05', '06-11', '12-17'])
    out = {}
    out['share3 18-23 / 00-11'] = ratio(ratio(ev[0], ev[1]), ratio(night[0], night[1]))
    out['share4 18-23 / 00-11'] = ratio(ratio(ev[2], ev[3]), ratio(night[2], night[3]))
    out['хвост 18-23 / 00-11'] = ratio(ratio(ev[4], ev[5]), ratio(night[4], night[5]))
    out['хвост 18-23 / остальные'] = ratio(ratio(ev[4], ev[5]), ratio(rest[4], rest[5]))
    out['share4 18-23 / остальные'] = ratio(ratio(ev[2], ev[3]), ratio(rest[2], rest[3]))
    return out


def dom_vec(d):
    return (d['rk'][3], sum(d['rk'][:4]), d['rk'][4], sum(d['rk'][:5]), d['tail'], d['reg'])


def perm_hour(D, nsim, seed=1):
    random.seed(seed)
    pools = collections.defaultdict(list)
    for i, d in enumerate(D):
        pools[(d['content'], d['day'])].append(i)
    fixed = {b: [0] * 6 for b in BLOCKS}
    plist = []
    nmixed = 0
    for key, idx in pools.items():
        labs = [D[i]['block'] for i in idx]
        regpos = [j for j, i in enumerate(idx) if D[i]['reg'] > 0]
        if len(set(labs)) < 2 or not regpos:
            for i in idx:
                v = dom_vec(D[i])
                for t in range(6):
                    fixed[D[i]['block']][t] += v[t]
            continue
        nmixed += 1
        plist.append((labs, [(j, dom_vec(D[idx[j]])) for j in regpos]))
    obs_acc = {b: [0] * 6 for b in BLOCKS}
    for d in D:
        v = dom_vec(d)
        for t in range(6):
            obs_acc[d['block']][t] += v[t]
    obs = stats_from_acc(obs_acc)
    ge = collections.Counter()
    two = collections.Counter()
    for _ in range(nsim):
        acc = {b: list(fixed[b]) for b in BLOCKS}
        for labs, vecs in plist:
            random.shuffle(labs)
            for j, v in vecs:
                a = acc[labs[j]]
                for t in range(6):
                    a[t] += v[t]
        st = stats_from_acc(acc)
        for k, o in obs.items():
            s = st[k]
            if o != o:
                continue
            if s == s and s >= o:
                ge[k] += 1
            if s == s and s > 0 and o > 0 and abs(math.log(s)) >= abs(math.log(o)):
                two[k] += 1
            elif s == s and (s == 0 or o == 0):
                two[k] += 1
    nreg_mixed = sum(len(v) for _, v in plist)
    print('  пулов «набор + день»: %d, из них с ≥2 блоками часа и регистрациями: %d; '
          'доменов с регистрациями внутри таких пулов: %d' % (len(pools), nmixed, nreg_mixed))
    print('  %-28s %8s %10s %10s' % ('статистика', 'набл.', 'p(≥набл.)', 'p(двуст.)'))
    for k, o in obs.items():
        print('  %-28s %8s %10.3f %10.3f' % (k, fmt(o), pval(ge[k], nsim), pval(two[k], nsim)))
    ev = obs_acc['18-23']
    ni = [sum(obs_acc[b][i] for b in ('00-05', '06-11')) for i in range(6)]
    rest = [sum(obs_acc[b][i] for b in BLOCKS[:3]) for i in range(6)]
    print('  приближённые 95 %% ДИ отношений (лог-метод, без страты): хвост 18–23 / 00–11 = %s; '
          'хвост 18–23 / остальные = %s; share4 18–23 / 00–11 = %s'
          % (ratio_ci(ev[4], ev[5], ni[4], ni[5]), ratio_ci(ev[4], ev[5], rest[4], rest[5]),
             ratio_ci(ev[2], ev[3], ni[2], ni[3])))
    return obs


METRICS = [
    ('свод: окно по сайту (0..3 / 2-я волна 1..4)', lambda d: d['wreg']),
    ('0..2 от дня запуска (3 календ. дня)', lambda d: sum(d['rk'][:3])),
    ('0..3 от дня запуска', lambda d: sum(d['rk'][:4])),
    ('0..4 от дня запуска', lambda d: sum(d['rk'][:5])),
    ('план: 0..3 при часе ≥18, иначе 0..2', lambda d: sum(d['rk'][:4]) if d['hour'] >= 18 else sum(d['rk'][:3])),
    ('вечерним +1 день: 0..4 при часе ≥18, иначе 0..3', lambda d: sum(d['rk'][:5]) if d['hour'] >= 18 else sum(d['rk'][:4])),
    ('всё время', lambda d: d['reg']),
]


def oe_by_block(D, f):
    pools = collections.defaultdict(lambda: [0, 0])
    for d in D:
        p = pools[(d['content'], d['day'])]
        p[0] += f(d)
        p[1] += d['sites']
    O = collections.Counter()
    E = collections.defaultdict(float)
    for d in D:
        p = pools[(d['content'], d['day'])]
        O[d['block']] += f(d)
        E[d['block']] += p[0] / p[1] * d['sites'] if p[1] else 0.0
    return O, E


def group_rates(D, f, keyf, minn):
    g = collections.defaultdict(lambda: [0, 0, 0])
    for d in D:
        t = g[keyf(d)]
        t[0] += 1
        t[1] += f(d)
        t[2] += d['sites']
    return {k: 100.0 * v[1] / v[2] for k, v in g.items() if v[0] >= minn and v[2] > 0}


def alt_metrics(D):
    print('\nА3. Альтернативные окна от дня запуска (домены возраста ≥7, без «не записан»)')
    base_f = METRICS[0][1]
    base_sum = {b: sum(base_f(d) for d in D if d['block'] == b) for b in BLOCKS}
    base_nab = group_rates(D, base_f, lambda d: d['content'], 5)
    base_pool = group_rates(D, base_f, lambda d: (d['content'], d['day']), 5)
    print('  наборов с ≥5 доменами: %d; пулов с ≥5 доменами: %d' % (len(base_nab), len(base_pool)))
    print('  %-48s | %6s %6s %6s %6s | %-22s %-22s | %-20s | %6s %6s'
          % ('окно', '00-05', '06-11', '12-17', '18-23', 'Δ вечерним (18-23)', 'Δ остальным (00-17)',
             'O/E по блокам в пулах', 'ρ наб.', 'ρ пул.'))
    for name, f in METRICS:
        sums = {b: sum(f(d) for d in D if d['block'] == b) for b in BLOCKS}
        dev = sums['18-23'] - base_sum['18-23']
        drest = sum(sums[b] for b in BLOCKS[:3]) - sum(base_sum[b] for b in BLOCKS[:3])
        O, E = oe_by_block(D, f)
        oe = ' '.join('%.2f' % ratio(O[b], E[b]) if E[b] else '—' for b in BLOCKS)
        nab = group_rates(D, f, lambda d: d['content'], 5)
        pool = group_rates(D, f, lambda d: (d['content'], d['day']), 5)
        keys_n = sorted(base_nab)
        keys_p = sorted(base_pool)
        rho_n = spearman([base_nab[k] for k in keys_n], [nab[k] for k in keys_n])
        rho_p = spearman([base_pool[k] for k in keys_p], [pool[k] for k in keys_p])
        print('  %-48s | %6d %6d %6d %6d | %+5d (%+5.1f%%)         %+5d (%+5.1f%%)          | %-20s | %6s %6s'
              % (name, sums['00-05'], sums['06-11'], sums['12-17'], sums['18-23'],
                 dev, pct(dev, base_sum['18-23']), drest, pct(drest, sum(base_sum[b] for b in BLOCKS[:3])),
                 oe, fmt(rho_n, 3), fmt(rho_p, 3)))
    # отдельно: O/E 18-23 против остальных на каждой метрике
    print('\n  O/E вечерних (18–23) против остальных блоков внутри пулов, по метрикам:')
    for name, f in METRICS:
        O, E = oe_by_block(D, f)
        oe_ev = ratio(O['18-23'], E['18-23'])
        oe_rest = ratio(sum(O[b] for b in BLOCKS[:3]), sum(E[b] for b in BLOCKS[:3]))
        print('  %-48s  18–23: O %3d / E %6.1f = %s   остальные: O %3d / E %6.1f = %s'
              % (name, O['18-23'], E['18-23'], fmt(oe_ev), sum(O[b] for b in BLOCKS[:3]),
                 sum(E[b] for b in BLOCKS[:3]), fmt(oe_rest)))


def part_a(D, label, nsim):
    print('\n' + '=' * 78)
    print('(а) ЧАС ЗАПУСКА — %s' % label)
    print('=' * 78)
    print('доменов: %d, сайтов: %d, регистраций: %d, в окне: %d, хвост: %d (%.1f%%)'
          % (len(D), sum(d['sites'] for d in D), sum(d['reg'] for d in D), sum(d['wreg'] for d in D),
             sum(d['tail'] for d in D), pct(sum(d['tail'] for d in D), sum(d['reg'] for d in D))))
    print_block_table(D, 'А1. По блокам часа (r_k — регистраций на смещении k суток от дня запуска; '
                         'share3 = r3/(r0..r3), share4 = r4/(r0..r4))')
    print_block_table(D, 'А1б. По часу шагом 3', by='hour')
    print('\nА2. Перестановочный тест: блок часа перемешан между доменами внутри пула '
          '«набор контента + день запуска», %d раз' % nsim)
    obs = perm_hour(D, nsim)
    return obs


# ---------------------------------------------------------------- часть (б)
def fam_table(D, title, minreg=1):
    print('\n%s' % title)
    fams = collections.defaultdict(list)
    for d in D:
        fams[d['fam']].append(d)
    print('  %-12s %6s %7s | %8s %8s %6s %6s | %4s %6s %5s %-14s | %7s %7s %6s'
          % ('семейство', 'домен.', 'сайтов', 'из поиска', 'в окне', 'захв.', 'медиан',
             'рег', 'в окне', 'хвост', 'хвост % [ДИ]', 'окно/100', 'всё/100', 'сдвиг'))
    rows = []
    for f, ds in sorted(fams.items(), key=lambda x: -sum(d['reg'] for d in x[1])):
        ya = sum(d['ya'] for d in ds)
        wya = sum(d['wya'] for d in ds)
        caps = [d['wya'] / d['ya'] for d in ds if d['ya'] > 0]
        med = statistics.median(caps) if caps else float('nan')
        reg = sum(d['reg'] for d in ds)
        wreg = sum(d['wreg'] for d in ds)
        sites = sum(d['sites'] for d in ds)
        r_w = 100.0 * wreg / sites if sites else float('nan')
        r_a = 100.0 * reg / sites if sites else float('nan')
        shift = pct(r_a - r_w, r_w) if r_w else float('nan')
        rows.append((f, len(ds), sites, ya, wya, ratio(wya, ya), med, reg, wreg, reg - wreg, r_w, r_a, shift))
        print('  %-12s %6d %7d | %8d %8d %6s %6s | %4d %6d %5d %-14s | %7.3f %7.3f %6s'
              % (f, len(ds), sites, ya, wya, fmt(ratio(wya, ya)), fmt(med), reg, wreg, reg - wreg,
                 ci_str(reg - wreg, reg) if reg else '—', r_w, r_a,
                 ('%+.0f%%' % shift) if shift == shift else '—'))
    tot_reg = sum(d['reg'] for d in D)
    tot_w = sum(d['wreg'] for d in D)
    print('  %-12s %6d %7d | %8d %8d %6s %6s | %4d %6d %5d %-14s'
          % ('всего', len(D), sum(d['sites'] for d in D), sum(d['ya'] for d in D), sum(d['wya'] for d in D),
             fmt(ratio(sum(d['wya'] for d in D), sum(d['ya'] for d in D))), '', tot_reg, tot_w,
             tot_reg - tot_w, ci_str(tot_reg - tot_w, tot_reg)))
    return rows


def pool_capture(D):
    print('\nБ1б. Захват поисковых кликов окном по пулам «набор + день» (≥8 доменов), от худшего к лучшему:')
    pools = collections.defaultdict(list)
    for d in D:
        pools[(d['content'], d['day'])].append(d)
    items = []
    for (c, day), ds in pools.items():
        if len(ds) < 8:
            continue
        ya = sum(d['ya'] for d in ds)
        wya = sum(d['wya'] for d in ds)
        reg = sum(d['reg'] for d in ds)
        wreg = sum(d['wreg'] for d in ds)
        items.append((ratio(wya, ya), c, day, ds[0]['fam'], len(ds), ya, wya, reg, wreg))
    items.sort(key=lambda x: (x[0] if x[0] == x[0] else 9))
    print('  %-42s %-10s %-10s %6s %8s %6s %4s %6s %5s'
          % ('набор контента', 'день', 'семейство', 'домен.', 'из поиска', 'захв.', 'рег', 'в окне', 'хвост'))
    for cap, c, day, fam, n, ya, wya, reg, wreg in items:
        print('  %-42s %-10s %-10s %6d %8d %6s %4d %6d %5d'
              % (c[:42], day, fam, n, ya, fmt(cap), reg, wreg, reg - wreg))
    byfam = collections.defaultdict(list)
    for it in items:
        if it[0] == it[0]:
            byfam[it[3]].append(it[0])
    print('  медиана захвата по пулам семейства: ' + '; '.join(
        '%s %.2f (пулов %d)' % (f, statistics.median(v), len(v)) for f, v in sorted(byfam.items())))


def perm_family(D, nsim, seed=1):
    random.seed(seed)
    regs = collections.Counter()
    tails = collections.Counter()
    for d in D:
        regs[d['fam']] += d['reg']
        tails[d['fam']] += d['tail']
    fams = sorted(f for f in regs if regs[f] >= 4)
    tot_reg = sum(regs.values())
    tot_tail = sum(tails.values())
    p_all = tot_tail / tot_reg
    print('  семейства с ≥4 регистраций: %s' % ', '.join(fams))
    print('  общая доля хвоста: %d / %d = %.3f' % (tot_tail, tot_reg, p_all))

    strata = collections.defaultdict(list)
    for i, d in enumerate(D):
        strata[(d['day'], d['block'])].append(i)
    slist = []
    nmixed = 0
    fixed_fams = collections.Counter()
    for key, idx in strata.items():
        labs = [D[i]['fam'] for i in idx]
        regpos = [(j, D[idx[j]]['reg'], D[idx[j]]['tail']) for j in range(len(idx)) if D[idx[j]]['reg'] > 0]
        if len(set(labs)) < 2 or not regpos:
            for i in idx:
                fixed_fams[D[i]['fam']] += D[i]['reg']
            continue
        nmixed += 1
        slist.append((labs, regpos))
    # статистика считается только по стратам, где метка семейства реально переставляется:
    # семейство, запущенное в одиночку в свой день (например «тест» 24.08), иначе задаёт
    # максимум навсегда и тест теряет смысл
    mreg = collections.Counter()
    mtail = collections.Counter()
    for labs, regpos in slist:
        for j, r, t in regpos:
            mreg[labs[j]] += r
            mtail[labs[j]] += t
    m_tot_reg = sum(mreg.values())
    m_tot_tail = sum(mtail.values())
    p_mixed = m_tot_tail / m_tot_reg if m_tot_reg else float('nan')
    mfams = sorted(f for f in mreg if mreg[f] >= 4)
    print('  страт «день × блок часа»: %d, из них с ≥2 семействами и регистрациями: %d; '
          'регистраций внутри таких страт: %d из %d (хвост %d, доля %.3f)'
          % (len(strata), nmixed, m_tot_reg, tot_reg, m_tot_tail, p_mixed))
    print('  регистраций семейств в стратах без перестановки (одно семейство в день × блок): %s'
          % ', '.join('%s %d' % (f, n) for f, n in fixed_fams.most_common() if n))
    print('  семейства с ≥4 регистраций внутри переставляемых страт: %s' % ', '.join(mfams))

    def stat(regc, tailc):
        share = {f: (tailc[f] / regc[f] if regc[f] else float('nan')) for f in mfams}
        mx = max(abs(share[f] - p_mixed) for f in mfams if share[f] == share[f])
        g1 = ('archive', 'NEW')
        r1 = sum(regc[f] for f in g1)
        t1 = sum(tailc[f] for f in g1)
        rat = ratio(ratio(t1, r1), ratio(m_tot_tail - t1, m_tot_reg - r1))
        return mx, rat, share

    obs_mx, obs_rat, obs_share = stat(mreg, mtail)
    ge_mx = 0
    ge_rat = 0
    ge_f = collections.Counter()
    le_f = collections.Counter()
    for _ in range(nsim):
        regc = collections.Counter()
        tailc = collections.Counter()
        for labs, regpos in slist:
            random.shuffle(labs)
            for j, r, t in regpos:
                regc[labs[j]] += r
                tailc[labs[j]] += t
        mx, rat, share = stat(regc, tailc)
        if mx >= obs_mx:
            ge_mx += 1
        if rat == rat and obs_rat == obs_rat and rat >= obs_rat:
            ge_rat += 1
        for f in mfams:
            if share[f] == share[f] and share[f] >= obs_share[f]:
                ge_f[f] += 1
            if share[f] == share[f] and share[f] <= obs_share[f]:
                le_f[f] += 1
    print('  максимум |доля хвоста семейства − общая| по переставляемым стратам: набл. %.3f, '
          'p = %.3f (%d перестановок)' % (obs_mx, pval(ge_mx, nsim), nsim))
    print('  отношение доли хвоста archive+NEW к остальным (переставляемые страты): набл. %s, '
          'p(≥набл.) = %.3f' % (fmt(obs_rat), pval(ge_rat, nsim)))
    g1r = regs['archive'] + regs['NEW']
    g1t = tails['archive'] + tails['NEW']
    print('  то же по всему срезу без страты: archive+NEW %d/%d против остальных %d/%d, отношение %s'
          % (g1t, g1r, tot_tail - g1t, tot_reg - g1r, ratio_ci(g1t, g1r, tot_tail - g1t, tot_reg - g1r)))
    print('  по семействам (доля хвоста в переставляемых стратах; p без поправки на множественность):')
    print('  %-12s %5s %5s %8s %9s %9s | %s' % ('семейство', 'рег', 'хвост', 'доля', 'p(≥)', 'p(≤)',
                                                 'весь срез: рег хвост доля'))
    for f in mfams:
        print('  %-12s %5d %5d %8.3f %9.3f %9.3f | %5d %5d %.3f'
              % (f, mreg[f], mtail[f], obs_share[f], pval(ge_f[f], nsim), pval(le_f[f], nsim),
                 regs[f], tails[f], ratio(tails[f], regs[f])))


def oe_control(D, nsim, seed=1):
    random.seed(seed)
    cells = [
        ('блок часа', lambda d: d['block']),
        ('блок часа × поздние выходы (0 / 1–3 / ≥4)', lambda d: (d['block'], late_group(d))),
        ('день запуска × блок часа', lambda d: (d['day'], d['block'])),
    ]
    fams = sorted({d['fam'] for d in D}, key=lambda f: -sum(d['reg'] for d in D if d['fam'] == f))
    fams = [f for f in fams if sum(d['reg'] for d in D if d['fam'] == f) >= 4]
    for cname, keyf in cells:
        rate = collections.defaultdict(lambda: [0, 0])
        for d in D:
            t = rate[keyf(d)]
            t[0] += d['tail']
            t[1] += d['reg']
        print('\n  ячейки «%s»: %d ячеек, из них с регистрациями %d'
              % (cname, len(rate), sum(1 for v in rate.values() if v[1])))
        E = collections.defaultdict(float)
        O = collections.Counter()
        regdoms = collections.defaultdict(list)
        for d in D:
            r = rate[keyf(d)]
            p = r[0] / r[1] if r[1] else 0.0
            E[d['fam']] += p * d['reg']
            O[d['fam']] += d['tail']
            if d['reg'] > 0:
                regdoms[d['fam']].append((d['reg'], p))
        ge = collections.Counter()
        le = collections.Counter()
        for _ in range(nsim):
            for f in fams:
                s = 0
                for n, p in regdoms[f]:
                    for _k in range(n):
                        if random.random() < p:
                            s += 1
                if s >= O[f]:
                    ge[f] += 1
                if s <= O[f]:
                    le[f] += 1
        print('  %-12s %5s %6s %6s %6s %8s %8s | %s'
              % ('семейство', 'рег', 'O', 'E', 'O/E', 'p(O≥)', 'p(O≤)', 'в ячейках семейства хвост у ОСТАЛЬНЫХ: хвост/рег'))
        for f in fams:
            reg = sum(d['reg'] for d in D if d['fam'] == f)
            cells_f = {keyf(d) for d in D if d['fam'] == f}
            oth = [d for d in D if d['fam'] != f and keyf(d) in cells_f]
            print('  %-12s %5d %6d %6.1f %6s %8.3f %8.3f | %d/%d'
                  % (f, reg, O[f], E[f], fmt(ratio(O[f], E[f])), pval(ge[f], nsim), pval(le[f], nsim),
                     sum(d['tail'] for d in oth), sum(d['reg'] for d in oth)))


def new_breakdown(D):
    new = [d for d in D if d['fam'] == 'NEW']
    print('\nБ4. Внутри NEW (доменов %d, регистраций %d, хвост %d):'
          % (len(new), sum(d['reg'] for d in new), sum(d['tail'] for d in new)))
    for title, keyf, minn in (('по наборам (≥5 доменов)', lambda d: d['content'], 5),
                              ('по оформлению', lambda d: d['oform'], 1),
                              ('по страницам', lambda d: d['pages'], 1)):
        g = collections.defaultdict(list)
        for d in new:
            g[keyf(d)].append(d)
        print('  %s:' % title)
        print('    %-40s %6s %7s %5s %6s %5s %-14s %6s' % ('группа', 'домен.', 'сайтов', 'рег', 'в окне', 'хвост', 'хвост % [ДИ]', 'захв.'))
        for k, ds in sorted(g.items(), key=lambda x: -sum(d['reg'] for d in x[1])):
            if len(ds) < minn:
                continue
            reg = sum(d['reg'] for d in ds)
            wreg = sum(d['wreg'] for d in ds)
            print('    %-40s %6d %7d %5d %6d %5d %-14s %6s'
                  % (str(k)[:40], len(ds), sum(d['sites'] for d in ds), reg, wreg, reg - wreg,
                     ci_str(reg - wreg, reg) if reg else '—',
                     fmt(ratio(sum(d['wya'] for d in ds), sum(d['ya'] for d in ds)))))


def capture_bins(D, title):
    print('\n%s' % title)
    bins = [('<50%', 0.0, 0.5), ('50–70%', 0.5, 0.7), ('70–85%', 0.7, 0.85), ('≥85%', 0.85, 1.01)]
    print('  %-8s %6s %5s %6s %5s %-14s  семейства по регистрациям' % ('захват', 'домен.', 'рег', 'в окне', 'хвост', 'хвост % [ДИ]'))
    for name, lo, hi in bins:
        ds = [d for d in D if d['ya'] > 0 and lo <= d['wya'] / d['ya'] < hi]
        reg = sum(d['reg'] for d in ds)
        wreg = sum(d['wreg'] for d in ds)
        fc = collections.Counter()
        for d in ds:
            fc[d['fam']] += d['reg']
        print('  %-8s %6d %5d %6d %5d %-14s  %s'
              % (name, len(ds), reg, wreg, reg - wreg, ci_str(reg - wreg, reg) if reg else '—',
                 ', '.join('%s %d' % (f, n) for f, n in fc.most_common(5) if n)))


def ratings(rows, title):
    print('\n%s' % title)
    r = {x[0]: x for x in rows if x[7] >= 4}
    order_w = sorted(r, key=lambda f: -r[f][10])
    order_a = sorted(r, key=lambda f: -r[f][11])
    print('  %-12s %9s %5s %9s %5s %7s' % ('семейство', 'окно/100', 'ранг', 'всё/100', 'ранг', 'сдвиг'))
    for f in order_w:
        print('  %-12s %9.3f %5d %9.3f %5d %7s'
              % (f, r[f][10], order_w.index(f) + 1, r[f][11], order_a.index(f) + 1,
                 ('%+.0f%%' % r[f][12]) if r[f][12] == r[f][12] else '—'))
    keys = sorted(r)
    rho_all = spearman([r[f][10] for f in keys], [r[f][11] for f in keys])
    keys2 = [f for f in keys if f != 'тест']
    rho2 = spearman([r[f][10] for f in keys2], [r[f][11] for f in keys2])
    keys3 = [f for f in keys if r[f][1] >= 20]
    rho3 = spearman([r[f][10] for f in keys3], [r[f][11] for f in keys3])
    print('  Спирмен рангов двух рейтингов: все семейства (%d) %s; без «тест» (0 в окне, 4 в хвосте, один день '
          'запуска) %s; семейства с ≥20 доменами (%s) %s'
          % (len(keys), fmt(rho_all, 3), fmt(rho2, 3), ', '.join(keys3), fmt(rho3, 3)))
    for a, b in (('NEW', 'Generator'), ('archive', 'Generator'), ('NEW', 'nabory'), ('archive', 'nabory')):
        if a in r and b in r and r[b][10] > 0 and r[b][11] > 0:
            rw, ra = r[a][10] / r[b][10], r[a][11] / r[b][11]
            print('  %s / %s: в окне %.2f, за всё время %.2f (сдвиг %+.0f%%)' % (a, b, rw, ra, pct(ra - rw, rw)))


def part_b(D, label, nsim, full=True):
    print('\n' + '=' * 78)
    print('(б) СЕМЕЙСТВА — %s' % label)
    print('=' * 78)
    print('доменов: %d, сайтов: %d, регистраций: %d, в окне: %d'
          % (len(D), sum(d['sites'] for d in D), sum(d['reg'] for d in D), sum(d['wreg'] for d in D)))
    rows = fam_table(D, 'Б1. Захват поисковых кликов окном (захв. = Σ в окне / Σ из поиска; медиан — по доменам '
                        'с поиском), доля хвоста регистраций, два рейтинга')
    if full:
        pool_capture(D)
        print('\nБ2. Перестановочный тест: метка семейства перемешана между доменами внутри страт '
              '«день запуска × блок часа», %d раз' % nsim)
        perm_family(D, nsim)
        print('\nБ3. Контроль механизмов: E хвоста домена = ставка ячейки × регистраций домена; '
              'Монте-Карло p — %d биномиальных розыгрышей' % nsim)
        oe_control(D, nsim)
        new_breakdown(D)
        capture_bins(D, 'Б5. Разрез по захвату кликов домена (все семейства):')
        capture_bins([d for d in D if d['fam'] == 'NEW'], 'Б5б. То же внутри NEW:')
    ratings(rows, 'Б6. Два рейтинга семейств (≥4 регистраций): рег в окне / 100 сайтов и рег за всё время / 100 сайтов')
    return rows


# ---------------------------------------------------------------- вывод
def main():
    sys.stdout = Tee(OUT)
    print('Гипотеза №12: окно «3 суток» как неровная линейка по часу запуска и семейству')
    print('Источник: %s' % SRC)
    doms = load()
    base = apply_filters(doms)
    part0(base)

    core = [d for d in base if d['content'] != NOCONTENT]
    a7 = [d for d in core if d['d0'] <= CUT_HOUR]
    a7nc = [d for d in base if d['d0'] <= CUT_HOUR]
    print('\nСрез (а): возраст ≥7 суток (день запуска ≤ %s): %d доменов без «не записан», %d с ним'
          % (CUT_HOUR, len(a7), len(a7nc)))
    obs_a = part_a(a7, 'возраст ≥7 суток, без «КОНТЕНТ НЕ ЗАПИСАН»', NSIM)
    alt_metrics(a7)
    obs_a_nc = part_a(a7nc, 'дополнительно: с «КОНТЕНТ НЕ ЗАПИСАН» (как в цифрах постановки; '
                            'он — своя страта в пуле)', NSIM)

    b10 = [d for d in core if d['d0'] <= CUT_FAM]
    b14 = [d for d in core if d['d0'] <= CUT_FAM14]
    print('\nСрез (б): возраст ≥10 суток (≤ %s): %d доменов; возраст ≥14 (≤ %s): %d доменов; '
          'archive в срезе ≥14: %d'
          % (CUT_FAM, len(b10), CUT_FAM14, len(b14), sum(1 for d in b14 if d['fam'] == 'archive')))
    rows10 = part_b(b10, 'возраст ≥10 суток, без «КОНТЕНТ НЕ ЗАПИСАН» (основной срез)', NSIM, full=True)
    rows14 = part_b(b14, 'возраст ≥14 суток по постановке (archive здесь нет)', NSIM, full=False)

    final(a7, obs_a, obs_a_nc, b10, rows10)
    sys.stdout.flush()


def final(a7, obs_a, obs_a_nc, b10, rows10):
    print('\n' + '=' * 78)
    print('ВЫВОД')
    print('=' * 78)
    ev = block_row([d for d in a7 if d['block'] == '18-23'])
    ni = block_row([d for d in a7 if d['block'] in ('00-05', '06-11')])
    r = {x[0]: x for x in rows10}
    tot_reg = sum(d['reg'] for d in b10)
    tot_tail = sum(d['tail'] for d in b10)
    rest = block_row([d for d in a7 if d['block'] != '18-23'])
    plan_ev = sum(sum(d['rk'][:4]) for d in a7 if d['block'] == '18-23')
    plan_rest = sum(sum(d['rk'][:3]) for d in a7 if d['block'] != '18-23')
    gen = r.get('Generator')
    lines = []
    lines.append(
        '1. Линейка не та, что в постановке. «Окно 3 суток» в своде — это сутки переобхода плюс три\n'
        '   следующих (смещения 0..3 от переобхода сайта), т.е. у всех доменов не меньше 73 часов:\n'
        '   18–23 получают 73–78 ч, 12–17 — 79–84, 06–11 — 85–90, 00–05 — 91–96. День 3 внутри окна,\n'
        '   за окном — день 4 и дальше. Разрыв по часам 0,81 (73–78 против 91–96), а не 0,69 (50/72).\n'
        '   Окно ровно в 72 часа от постановки на своде посчитать нельзя: нет часа регистрации.')
    lines.append(
        '2. Час запуска (возраст ≥7, без «не записан»: %d доменов, %d рег.). У вечерних (18–23: %d доменов,\n'
        '   %d рег.) за окном остаётся %s регистраций, у 00–11 (%d доменов, %d рег.) — %s,\n'
        '   у всех остальных блоков вместе (%d рег.) — %s. Отношение хвоста 18–23 к 00–11 %s,\n'
        '   доля 4-го дня (share4) %s; перестановка блока внутри пула «набор + день» (10 000 раз) —\n'
        '   p > 0,4 по всем статистикам (А2). Регистрации вечерних действительно сдвинуты на сутки позже\n'
        '   (день 0 пустой, 3-й день 20 %% против 5–14 %% у 00–11), но окно 0..3 это уже покрывает. Постановка\n'
        '   ждала хвост 40 %% у 18–23 против 24 %% у 00–05 — этого нет. С «не записан» то же (А, доп.).'
        % (len(a7), sum(d['reg'] for d in a7), ev['n'], ev['reg'], ci_str(ev['tail'], ev['reg']),
           ni['n'], ni['reg'], ci_str(ni['tail'], ni['reg']), rest['reg'], ci_str(rest['tail'], rest['reg']),
           fmt(obs_a['хвост 18-23 / 00-11']), fmt(obs_a['share4 18-23 / 00-11'])))
    lines.append(
        '3. «Исправленное» окно из плана (0..3 вечерним, 0..2 остальным) вечерним не добавляет ничего\n'
        '   (%d против %d в своде: они и так на 0..3), а у остальных отнимает 3-й день (%d против %d, −%.0f %%) —\n'
        '   линейка стала бы неровнее в другую сторону. O/E вечерних против остальных внутри пулов на любой\n'
        '   метрике 0,98–1,03 (реестровое 1,07 против 1,02 не меняется). Ранги наборов и пулов между\n'
        '   календарными вариантами окна почти не меняются (Спирмен 0,96–1,00, А3).'
        % (plan_ev, ev['wreg'], plan_rest, rest['wreg'], 100.0 * (rest['wreg'] - plan_rest) / rest['wreg']))
    fam_line = ', '.join('%s %d/%d = %s' % (f, r[f][9], r[f][7], ci_str(r[f][9], r[f][7]))
                         for f in ('NEW', 'archive', 'Generator', 'nabory', 'clean', 'script') if f in r)
    lines.append(
        '4. Семейства (возраст ≥10, чтобы archive вообще был в срезе: %d доменов, %d рег., хвост %d = %.0f %%).\n'
        '   Захват поисковых кликов окном и правда разный: NEW %s, archive %s, clean %s против Generator %s,\n'
        '   nabory %s, script %s — но на деньги это не переносится. Доля регистраций за окном:\n'
        '   %s.\n'
        '   NEW и archive сидят на общей доле (~%.0f %%); отличаются от неё Generator и script (0 хвоста) и\n'
        '   nabory (3 из 9). Отношение хвоста archive+NEW к остальным 1,23 [0,68–2,23] по срезу и 1,67 внутри\n'
        '   переставляемых страт «день × блок часа», p = 0,28; максимум отклонения по семействам p = 0,90 (Б2).\n'
        '   После контроля часа и поздних выходов O/E хвоста NEW 1,06, archive 0,75 (Б3), в ячейках\n'
        '   «день × блок» — 1,01 и 1,10. Ноль хвоста у Generator (0 из 14; p = 0,03 при контроле одного часа,\n'
        '   0,12 при часе × поздних выходах) объясняется его днями запуска: в его стратах «день × блок» у\n'
        '   остальных семейств хвост 1 из 12 регистраций, E = 0. Длинный хвост — свойство конкретных\n'
        '   доменов с поздними выходами (Б5: захват <50 %% → хвост 32 %%, ≥85 %% → 3 %%, и так же внутри NEW),\n'
        '   а не семейства.'
        % (len(b10), tot_reg, tot_tail, pct(tot_tail, tot_reg),
           fmt(r['NEW'][5]) if 'NEW' in r else '—', fmt(r['archive'][5]) if 'archive' in r else '—',
           fmt(r['clean'][5]) if 'clean' in r else '—', fmt(r['Generator'][5]) if 'Generator' in r else '—',
           fmt(r['nabory'][5]) if 'nabory' in r else '—', fmt(r['script'][5]) if 'script' in r else '—',
           fam_line, pct(tot_tail, tot_reg)))
    lines.append(
        '5. Два рейтинга (Б6). Относительно Generator оконный рейтинг NEW и archive сдвигается на +%.0f %% и\n'
        '   +%.0f %% при переходе к «за всё время» (NEW/Generator %.2f → %.2f, archive/Generator %.2f → %.2f) —\n'
        '   формально ≥20 %%, но это целиком ноль хвоста у Generator на 14 регистрациях, а не недобор у NEW и\n'
        '   archive; относительно nabory сдвиг обратный (NEW/nabory %.2f → %.2f). Порядок объёмных семейств\n'
        '   тот же: NEW впереди, archive и nabory позади. Единственный переворот — «тест» (10 доменов одного\n'
        '   дня, 0 в окне, 4 в хвосте), на нём рейтинг не строится.'
        % (r['NEW'][12] if 'NEW' in r else float('nan'), r['archive'][12] if 'archive' in r else float('nan'),
           r['NEW'][10] / gen[10] if gen else float('nan'), r['NEW'][11] / gen[11] if gen else float('nan'),
           r['archive'][10] / gen[10] if gen else float('nan'), r['archive'][11] / gen[11] if gen else float('nan'),
           r['NEW'][10] / r['nabory'][10] if 'nabory' in r else float('nan'),
           r['NEW'][11] / r['nabory'][11] if 'nabory' in r else float('nan')))
    lines.append(
        'Итог: гипотеза опровергнута в обеих частях. Первая посылка неверна (окно 0..3, не 0..2; вечерним\n'
        '73–78 ч, а не 50), и на деньгах неровность часов не видна: хвост вечерних 24 % против 22 %. Вторая\n'
        'посылка верна только про клики (окно захватывает у archive/NEW 62–69 % поисковых кликов против 78–86 %\n'
        'у nabory/Generator), но регистрации за окном у NEW и archive такие же, как у всех (24 % и 21 % при\n'
        'общих 23 %), и после контроля дня, часа и поздних выходов O/E ≈ 1. Оговорку «окно занижает вечерние\n'
        'на 1/5 и медленные семейства на 20–35 %» снять. Оговорка по мощности: регистраций мало (хвост 55 в\n'
        'части (а), 51 в части (б)), ДИ отношений широкие (0,6–2,0), но точечные оценки стоят на 1,0–1,2, а\n'
        'не на 1,5–2,5, как ждала постановка.')
    lines.append(
        'Что с этим делать: ничего менять в метрике не нужно — считать успех по окну 0..3 суток от\n'
        'переобхода, как сейчас, и сравнивать наборы по «рег в окне / 100 сайтов»; поправок на час запуска и\n'
        'на семейство не вводить. Проверяемо на уже запущенных данных: (1) если в выгрузку конверсий добавить\n'
        'час регистрации, пересчитать окно ровно в 72 ч от переобхода и сверить ранги наборов с нынешними —\n'
        'ожидание Спирмен > 0,95, как между календарными вариантами здесь; (2) через 2–3 недели, когда у\n'
        'запусков 12–18.09 (content-дата, 514 доменов) хвост дособерётся, повторить Б2–Б3 на них.')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()

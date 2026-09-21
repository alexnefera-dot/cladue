#!/usr/bin/env python3
"""
Гипотеза №16. Список «денежных» брендов существует и воспроизводим, но бренды
регистраций и бренды первых депозитов (ФД) — не одни и те же.

Что проверяем.
  (а) Устойчивость списка. Если у брендов есть собственная «денежность»
      (одни и те же бренды приносят регистрации и ФД раз за разом), то при
      разрезании запусков на две половины бренды-лидеры одной половины будут
      лидерами и другой: Спирмен между половинами по брендам с ≥3 конверсиями
      ≥0,5; топ-10 брендов, выбранных по одной половине, собирают ≥25%
      конверсий другой половины (при случайности ≈10/133 ≈ 7,5%).
  (б) Расхождение регистраций и ФД. Доля ФД на регистрацию различается по
      брендам сильнее биномиального шума (Leon 6 из 14, Martin 5 из 10 против
      Олимп 0 из 10, Dragon Money 0 из 6, Luckybear 0 из 5), а ранг бренда по
      регистрациям не предсказывает его долю ФД.

Как проверяем.
  Источник — колонка «какие бренды конвертили» вида «Martin (5), Twin (2)»:
  разбирается регуляркой в записи бренд × домен × N, где N = регистраций + ФД
  бренда на домене за всё время. Сумма N сверяется с колонками «регистраций»
  и «ФД» по каждому домену (совпадает: 536 = 461 + 75 на всех 2077 строках).

  Фильтр: окно закрыто = да и дней ≠ 1 (незакрытое окно и запуски без дня 2
  исключены, число исключённых печатается). «КОНТЕНТ НЕ ЗАПИСАН» (август)
  в части (а) оставлен — бренд не зависит от набора контента, а без августа
  нечего делить на «авг→сен»; это оговаривается, и есть контрольный прогон
  без него. Выбросы 3615.team и 3286.team клики не дают, здесь клики не
  используются, поэтому они оставлены (их вклад печатается: одна регистрация).

  (а) Три разбиения на половины: по чётности числа дня в «день запуска»
      (перемешивает контент, зоны и месяцы), август → сентябрь, и то же
      разбиение по чётности только на доменах, у которых регистраций =
      регистраций в окне 3 суток (чистая оконная атрибуция).
      Статистики: Спирмен между конверсиями бренда в половинах A и B по
      брендам с суммарно ≥3 конверсиями; доля половины A, собранная топ-10
      брендами по B (и наоборот); при равенстве на границе топ-10 доли
      делятся поровну между равными. Дополнительно (они не из постановки,
      но нужны, потому что у Спирмена по брендам с ≥3 конверсиями нуль не
      0, а отрицательный — A + B у малого бренда почти постоянна): Спирмен
      по всем брендам с нулями (нуль около 0) и число брендов, входящих в
      топ-10 обеих половин (равные на границе входят все).
      Нули (по 10 000 розыгрышей, random.seed(1)), единица розыгрыша —
      запись бренд × домен (все N событий записи идут в одну половину вместе,
      как в данных, — это защищает от «одного везучего домена»):
        R-K   — каждой записи имя бренда назначается случайно из K брендов,
                которые конвертировали хоть раз (консервативный нуль, как
                «10/133»);
        R-206 — то же из всех 206 брендов сети;
        E-K   — то же, но каждое из событий независимо (без учёта сцепки
                событий одного домена) — чувствительность к кластеризации;
        ПЕРЕСТ — буквальная перестановка имён брендов между записями
                (сохраняет суммарные конверсии каждого бренда и число
                событий в половинах). Этот нуль проверяет лишь, случайно ли
                бренд делится между половинами, а не существует ли список,
                — поэтому он печатается с оговоркой, а решает R-K.
      Подтверждение — наблюдённое выше 95-го перцентиля нуля (p < 0,05),
      по постановке — p < 0,01, Спирмен 0,4–0,7, топ-10 ≥25%.
      Дополнительно «существование»: число разных брендов и доля топ-10
      от всех конверсий против R-206 и R-K.

  (б) Только домены с «брендов с конверсией» = 1 — там регистрации и ФД
      домена принадлежат одному бренду. Многобрендовые домены (с их ФД)
      исключаются, потеря печатается. Бренды с ≥5 регистрациями: таблица
      рег / ФД / доля с 95% ДИ Уилсона, точный двусторонний биномиальный
      тест против общей доли с поправкой Бенджамини–Хохберга.
      Неоднородность:
        1) параметрический тест — 10 000 раз ФД бренда ~ Binom(рег, общая
           доля), статистика χ² однородности (2×k), p = доля розыгрышей
           с χ² ≥ наблюдённого;
        2) перестановка имён брендов между однобрендовыми доменами (домен
           хранит свои рег и ФД — учитывает «один везучий домен»), без
           страты и внутри страт «ISO-неделя запуска» и «день запуска»;
           статистика χ²/df по брендам с ≥5 рег;
        3) O/E со стратой: E ФД бренда = Σ по его доменам (рег домена ×
           доля ФД страты), страты — «набор контента + день» (по плану;
           степень вырождения печатается), «день запуска», «ISO-неделя»;
           доля ФД страты считается по всем доменам страты, включая
           многобрендовые (там атрибуция бренда не нужна).
      Спирмен между рангом бренда по регистрациям и по ФД/рег с
      перестановочным p. Оконная версия — «регистраций в окне 3 суток» и
      «ФД в окне 3 суток» на тех же доменах.
      Тень периода: доля ФД по месяцам и неделям на всех доменах и
      распределение доменов каждого бренда по месяцам.

  Критерии из постановки. (а) Спирмен 0,4–0,7, топ-10 ≥25%, p < 0,01 —
  список есть; Спирмен ≈0–0,2 и 8–12% — шум. (б) p < 0,05, 2–3 бренда с
  ФД/рег ≥35% и 3–4 с 0 ФД при 5–10 рег, Спирмен «рег против ФД/рег» ≤0,1.
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
OUT = os.path.join(REPO, 'analysis', 'export', 'gipotezy_svod', 'h16_money_brand_list.txt')
OUTLIERS = ('3615.team', '3286.team')
NOCONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
NPERM = 10000
NBRANDS_NET = 206
TOPK = 10
MIN_TOTAL = 3      # бренды с ≥3 конверсиями для Спирмена в (а)
MIN_REG = 5        # бренды с ≥5 регистрациями в (б)
BRAND_RE = re.compile(r'^\s*(.+?)\s*\((\d+)\)\s*$')


class Tee:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.f = open(path, 'w', encoding='utf-8')

    def __call__(self, *args):
        s = ' '.join(str(a) for a in args)
        print(s)
        self.f.write(s + '\n')

    def close(self):
        self.f.close()


def toint(s):
    s = (s or '').strip()
    return int(s) if s else 0


def parse_brands(s):
    out = []
    for part in (s or '').split(','):
        part = part.strip()
        if not part:
            continue
        m = BRAND_RE.match(part)
        if not m:
            raise ValueError('не разобрано: %r' % part)
        out.append((m.group(1), int(m.group(2))))
    return out


def iso_week(day):
    y, m, d = (int(x) for x in day.split('-'))
    return datetime.date(y, m, d).isocalendar()[1]


# ---------------------------------------------------------------- статистика
def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    if n < 3:
        return float('nan')
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return float('nan')
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return sxy / math.sqrt(sxx * syy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


def top_share(sel, other, k=TOPK):
    """Доля событий половины other у топ-k брендов по половине sel.
    Равные на границе делят оставшиеся места поровну (дробные веса)."""
    tot = sum(other.values())
    if tot == 0:
        return float('nan')
    vals = sorted((v for v in sel.values() if v > 0), reverse=True)
    if not vals:
        return 0.0
    if len(vals) <= k:
        thr = 0
        above_w = 1.0
    else:
        thr = vals[k - 1]
        above_w = 1.0
    n_above = sum(1 for v in vals if v > thr)
    n_tied = sum(1 for v in vals if v == thr) if thr > 0 else 0
    tied_w = (k - n_above) / n_tied if n_tied else 0.0
    acc = 0.0
    for b, v in sel.items():
        if v > thr:
            acc += above_w * other.get(b, 0)
        elif thr > 0 and v == thr:
            acc += tied_w * other.get(b, 0)
    return acc / tot


def top_set(cnt, k=TOPK):
    """Бренды с числом ≥ k-го по величине положительного числа (равные на границе входят все)."""
    vals = sorted((v for v in cnt.values() if v > 0), reverse=True)
    if not vals:
        return set()
    thr = vals[k - 1] if len(vals) > k else vals[-1]
    return set(b for b, v in cnt.items() if v >= thr and v > 0)


def half_stats(records, half_of, universe_n=None, min_total=MIN_TOTAL):
    """records: список (brand, n, key). Возвращает словарь статистик.
    universe_n — до скольких брендов дополнять нулями Спирмен «по всем брендам»."""
    A = collections.Counter()
    B = collections.Counter()
    tot = collections.Counter()
    for brand, n, key in records:
        tot[brand] += n
        if half_of(key) == 'A':
            A[brand] += n
        else:
            B[brand] += n
    brands = [b for b in tot if tot[b] >= min_total]
    rho = spearman([A[b] for b in brands], [B[b] for b in brands]) if len(brands) >= 3 else float('nan')
    xa = [A[b] for b in tot]
    xb = [B[b] for b in tot]
    if universe_n and universe_n > len(tot):
        pad = universe_n - len(tot)
        xa += [0] * pad
        xb += [0] * pad
    rho_all = spearman(xa, xb)
    ta, tb = top_set(A), top_set(B)
    ntot = sum(tot.values())
    return {
        'A': A, 'B': B, 'tot': tot, 'nA': sum(A.values()), 'nB': sum(B.values()),
        'n_brands': len(tot), 'n_ge': len(brands), 'rho': rho, 'rho_all': rho_all,
        't10_BA': top_share(B, A), 't10_AB': top_share(A, B),
        'top10_all': top_share(tot, tot),
        'max_share': (max(tot.values()) / ntot) if ntot else float('nan'),
        'top_A': ta, 'top_B': tb, 'overlap': len(ta & tb),
    }


def simulate(records, half_of, mode, universe, rng, brand_pool):
    """Один розыгрыш нуля. Возвращает список записей с новыми брендами."""
    if mode == 'R':      # запись целиком получает случайный бренд
        return [(rng.randrange(universe), n, key) for _, n, key in records]
    if mode == 'E':      # каждое событие независимо
        out = []
        for _, n, key in records:
            for _ in range(n):
                out.append((rng.randrange(universe), 1, key))
        return out
    if mode == 'P':      # перестановка имён между записями
        names = list(brand_pool)
        rng.shuffle(names)
        return [(names[i], n, key) for i, (_, n, key) in enumerate(records)]
    raise ValueError(mode)


def pval_ge(null, obs):
    if obs != obs:
        return float('nan')
    return (sum(1 for v in null if v >= obs) + 1) / (len(null) + 1)


def pct(null, q):
    v = sorted(x for x in null if x == x)
    if not v:
        return float('nan')
    return v[min(len(v) - 1, int(q * len(v)))]


def fmt(x, d=2):
    return 'nan' if x != x else ('%.*f' % (d, x))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def binom_pmf(k, n, p):
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_two_sided(k, n, p):
    pk = binom_pmf(k, n, p)
    return min(1.0, sum(binom_pmf(i, n, p) for i in range(n + 1) if binom_pmf(i, n, p) <= pk * (1 + 1e-9)))


def bh_fdr(ps):
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    q = [0.0] * m
    prev = 1.0
    for rank_i in range(m - 1, -1, -1):
        i = order[rank_i]
        val = min(prev, ps[i] * m / (rank_i + 1))
        q[i] = val
        prev = val
    return q


def chi2_hom(pairs):
    """pairs: список (fd, reg). χ² однородности долей (2×k) и df."""
    R = sum(r for _, r in pairs)
    F = sum(f for f, _ in pairs)
    if R == 0 or F == 0 or F == R:
        return 0.0, max(1, len(pairs) - 1)
    p = F / R
    chi = 0.0
    for f, r in pairs:
        e = r * p
        chi += (f - e) ** 2 / (e * (1 - p))
    return chi, len(pairs) - 1


# ---------------------------------------------------------------- данные
def main():
    log = Tee(OUT)
    rng = random.Random(1)
    random.seed(1)
    with open(SRC, encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    log('Гипотеза №16. Список «денежных» брендов: существует ли, воспроизводим ли,')
    log('и те ли это бренды по регистрациям и по ФД.')
    log('Источник: %s, строк %d' % (os.path.relpath(SRC, REPO), len(rows)))
    log('')

    # сверка разбора
    ev_all = reg_all = fd_all = 0
    for r in rows:
        parsed = parse_brands(r['какие бренды конвертили'])
        n = sum(x[1] for x in parsed)
        reg, fd = toint(r['регистраций']), toint(r['ФД'])
        if n != reg + fd:
            raise SystemExit('расхождение на %s: %d != %d + %d' % (r['домен'], n, reg, fd))
        if len(parsed) != toint(r['брендов с конверсией']):
            raise SystemExit('число брендов не сходится на %s' % r['домен'])
        ev_all += n
        reg_all += reg
        fd_all += fd
    log('Сверка разбора «какие бренды конвертили»: событий %d = регистраций %d + ФД %d — сходится на всех строках.'
        % (ev_all, reg_all, fd_all))

    # фильтр
    n_open = sum(1 for r in rows if r['окно закрыто'] != 'да')
    n_day1 = sum(1 for r in rows if r['окно закрыто'] == 'да' and r['дней'] == '1')
    kept = [r for r in rows if r['окно закрыто'] == 'да' and r['дней'] != '1']
    log('ИСКЛЮЧЕНИЯ: окно не закрыто — %d доменов; окно закрыто, но дней = 1 (нет дня 2) — %d доменов; осталось %d.'
        % (n_open, n_day1, len(kept)))
    ev_kept = sum(toint(r['регистраций']) + toint(r['ФД']) for r in kept)
    ev_lost = ev_all - ev_kept
    log('  С ними ушло %d событий из %d (регистраций %d, ФД %d).'
        % (ev_lost, ev_all,
           reg_all - sum(toint(r['регистраций']) for r in kept),
           fd_all - sum(toint(r['ФД']) for r in kept)))
    n_noc = sum(1 for r in kept if r['набор контента'] == NOCONTENT)
    ev_noc = sum(toint(r['регистраций']) + toint(r['ФД']) for r in kept if r['набор контента'] == NOCONTENT)
    log('  «%s»: %d доменов, %d событий — ОСТАВЛЕНЫ в части (а) (бренд от набора не зависит; это весь август до 24.08),'
        % (NOCONTENT, n_noc, ev_noc))
    log('  в части (б) для страты «набор + день» такие домены образуют страты «не записан + день» — это оговорено, и есть страты «день» и «неделя».')
    for d in OUTLIERS:
        for r in kept:
            if r['домен'] == d:
                log('  Выброс %s (миллионы прочих кликов) — клики здесь не используются, оставлен: регистраций %s, ФД %s, бренды: %s'
                    % (d, r['регистраций'], r['ФД'], r['какие бренды конвертили'] or '—'))
    log('')

    # записи бренд × домен
    records = []   # (brand, n, key)  key = dict с полями домена
    for r in kept:
        parsed = parse_brands(r['какие бренды конвертили'])
        if not parsed:
            continue
        day = r['день запуска']
        key = {
            'domain': r['домен'], 'day': day, 'dom': int(day[8:10]), 'month': day[5:7],
            'week': iso_week(day), 'content': r['набор контента'], 'zone': r['зона'],
            'reg': toint(r['регистраций']), 'fd': toint(r['ФД']),
            'regw': toint(r['регистраций в окне 3 суток']), 'fdw': toint(r['ФД в окне 3 суток']),
            'single': len(parsed) == 1,
            'clean': toint(r['регистраций']) == toint(r['регистраций в окне 3 суток']),
        }
        for brand, n in parsed:
            records.append((brand, n, key))
    brand_pool = [b for b, _, _ in records]
    K = len(set(brand_pool))
    n_conv_dom = len(set(k['domain'] for _, _, k in records))
    log('После фильтра: %d доменов с конверсиями, %d записей бренд × домен, %d событий, %d разных брендов из %d.'
        % (n_conv_dom, len(records), sum(n for _, n, _ in records), K, NBRANDS_NET))
    log('')

    # ------------------------------------------------------------ часть (а)
    log('=' * 100)
    log('ЧАСТЬ (а). УСТОЙЧИВОСТЬ СПИСКА: ПОЛОВИНЫ ЗАПУСКОВ')
    log('=' * 100)
    splits = [
        ('чётность числа дня запуска (нечётные = A, чётные = B)', records, lambda k: 'A' if k['dom'] % 2 == 1 else 'B'),
        ('август = A, сентябрь = B', records, lambda k: 'A' if k['month'] == '08' else 'B'),
        ('чётность дня, только домены с регистраций = регистраций в окне 3 суток',
         [x for x in records if x[2]['clean']], lambda k: 'A' if k['dom'] % 2 == 1 else 'B'),
        ('чётность дня, без «%s»' % NOCONTENT,
         [x for x in records if x[2]['content'] != NOCONTENT], lambda k: 'A' if k['dom'] % 2 == 1 else 'B'),
    ]
    null_modes = [('R-K', 'R', K), ('R-206', 'R', NBRANDS_NET), ('E-K', 'E', K), ('ПЕРЕСТ', 'P', None)]
    summary_a = []
    nb206_null = {}
    for title, recs, half_of in splits:
        log('-' * 100)
        log('Разбиение: %s' % title)
        obs = half_stats(recs, half_of, K)
        obs206 = half_stats(recs, half_of, NBRANDS_NET)
        ndom = len(set(k['domain'] for _, _, k in recs))
        log('  доменов %d, записей %d, событий: A = %d, B = %d; брендов всего %d, с ≥%d конверсиями %d'
            % (ndom, len(recs), obs['nA'], obs['nB'], obs['n_brands'], MIN_TOTAL, obs['n_ge']))
        log('  Спирмен A~B (бренды с ≥%d) = %s;  Спирмен A~B по всем %d брендам (с нулями) = %s'
            % (MIN_TOTAL, fmt(obs['rho'], 3), K, fmt(obs['rho_all'], 3)))
        log('  Топ-10 по A (с равными на границе, %d брендов) и топ-10 по B (%d брендов) пересекаются по %d брендам: %s'
            % (len(obs['top_A']), len(obs['top_B']), obs['overlap'], ', '.join(sorted(obs['top_A'] & obs['top_B'])) or '—'))
        log('  Доля A у топ-10 по B = %s%%;  доля B у топ-10 по A = %s%%;  среднее = %s%%'
            % (fmt(100 * obs['t10_BA'], 1), fmt(100 * obs['t10_AB'], 1),
               fmt(50 * (obs['t10_BA'] + obs['t10_AB']), 1)))
        log('  Существование: доля топ-10 от всех событий = %s%%, самый частый бренд = %s%%, разных брендов %d'
            % (fmt(100 * obs['top10_all'], 1), fmt(100 * obs['max_share'], 1), obs['n_brands']))
        # таблица топ-15
        log('  Топ-15 брендов по сумме: бренд | всего | A | B')
        for b, v in sorted(obs['tot'].items(), key=lambda x: (-x[1], x[0]))[:15]:
            log('    %-14s %4d %4d %4d' % (b, v, obs['A'][b], obs['B'][b]))
        # нули
        log('  Нули (%d розыгрышей): статистика | наблюд. | среднее нуля | 95-й перц. | p (нуль ≥ наблюд.)' % NPERM)
        for nm, mode, uni in null_modes:
            sims = collections.defaultdict(list)
            uni_n = uni if uni else K
            ob = obs206 if uni == NBRANDS_NET else obs
            for _ in range(NPERM):
                sr = simulate(recs, half_of, mode, uni, rng, [b for b, _, _ in recs])
                st = half_stats(sr, half_of, uni_n)
                sims['rho'].append(st['rho'])
                sims['rho_all'].append(st['rho_all'])
                sims['t10'].append(0.5 * (st['t10_BA'] + st['t10_AB']))
                sims['top10_all'].append(st['top10_all'])
                sims['n_brands'].append(st['n_brands'])
                sims['overlap'].append(st['overlap'])
            t10_obs = 0.5 * (obs['t10_BA'] + obs['t10_AB'])
            rho_null = [x for x in sims['rho'] if x == x]
            log('    [%s] Спирмен ≥%d   | %6s | %6s | %6s | p = %s'
                % (nm, MIN_TOTAL, fmt(obs['rho'], 3), fmt(sum(rho_null) / len(rho_null), 3) if rho_null else 'nan',
                   fmt(pct(sims['rho'], 0.95), 3), fmt(pval_ge(sims['rho'], obs['rho']), 4)))
            log('    [%s] Спирмен все  | %6s | %6s | %6s | p = %s   (по %d брендам с нулями)'
                % (nm, fmt(ob['rho_all'], 3), fmt(sum(sims['rho_all']) / NPERM, 3),
                   fmt(pct(sims['rho_all'], 0.95), 3), fmt(pval_ge(sims['rho_all'], ob['rho_all']), 4), uni_n))
            log('    [%s] пересеч. топ-10| %6d | %6.1f | %6d | p = %s'
                % (nm, obs['overlap'], sum(sims['overlap']) / NPERM, pct(sims['overlap'], 0.95),
                   fmt(pval_ge(sims['overlap'], obs['overlap']), 4)))
            log('    [%s] топ-10 доля  | %5s%% | %5s%% | %5s%% | p = %s'
                % (nm, fmt(100 * t10_obs, 1), fmt(100 * sum(sims['t10']) / NPERM, 1),
                   fmt(100 * pct(sims['t10'], 0.95), 1), fmt(pval_ge(sims['t10'], t10_obs), 4)))
            if mode != 'P':
                log('    [%s] топ-10 от всех| %5s%% | %5s%% | %5s%% | p = %s;   разных брендов: наблюд. %d, нуль в среднем %.1f'
                    % (nm, fmt(100 * obs['top10_all'], 1), fmt(100 * sum(sims['top10_all']) / NPERM, 1),
                       fmt(100 * pct(sims['top10_all'], 0.95), 1), fmt(pval_ge(sims['top10_all'], obs['top10_all']), 4),
                       obs['n_brands'], sum(sims['n_brands']) / NPERM))
            if nm == 'R-206':
                nb206_null[title] = sum(sims['n_brands']) / NPERM
            if nm == 'R-K':
                summary_a.append({
                    'title': title, 'obs': obs, 't10': t10_obs,
                    'p_rho': pval_ge(sims['rho'], obs['rho']), 'p_t10': pval_ge(sims['t10'], t10_obs),
                    'rho_null': sum(rho_null) / len(rho_null) if rho_null else float('nan'),
                    't10_null': sum(sims['t10']) / NPERM,
                    'p_rho_all': pval_ge(sims['rho_all'], obs['rho_all']),
                    'rho_all_null': sum(sims['rho_all']) / NPERM,
                    'p_top10_all': pval_ge(sims['top10_all'], obs['top10_all']),
                    'top10_all_null': sum(sims['top10_all']) / NPERM,
                    'p_overlap': pval_ge(sims['overlap'], obs['overlap']),
                    'overlap_null': sum(sims['overlap']) / NPERM,
                })
        log('  Оговорка к [ПЕРЕСТ]: перестановка имён сохраняет сумму конверсий каждого бренда, поэтому под этим нулём')
        log('  большие бренды остаются большими в обеих половинах — он отвечает только «делится ли бренд между')
        log('  половинами случайно», а не «есть ли список». Решает нуль R-K.')
    log('')

    # ------------------------------------------------------------ часть (б)
    log('=' * 100)
    log('ЧАСТЬ (б). БРЕНДЫ РЕГИСТРАЦИЙ И БРЕНДЫ ФД — ТОЛЬКО ОДНОБРЕНДОВЫЕ ДОМЕНЫ')
    log('=' * 100)
    single = {}
    for brand, n, k in records:
        if k['single']:
            single[k['domain']] = (brand, k)
    multi_dom = set(k['domain'] for _, _, k in records if not k['single'])
    multi_fd = sum(k['fd'] for d, k in {k['domain']: k for _, _, k in records if not k['single']}.items())
    multi_fd_dom = sum(1 for d, k in {k['domain']: k for _, _, k in records if not k['single']}.items() if k['fd'] > 0)
    s_reg = sum(k['reg'] for _, k in single.values())
    s_fd = sum(k['fd'] for _, k in single.values())
    all_reg = sum(k['reg'] for k in {k['domain']: k for _, _, k in records}.values())
    all_fd = sum(k['fd'] for k in {k['domain']: k for _, _, k in records}.values())
    log('Однобрендовых доменов %d: регистраций %d, ФД %d (доля ФД %s%%).'
        % (len(single), s_reg, s_fd, fmt(100 * s_fd / s_reg, 1)))
    log('ИСКЛЮЧЕНО многобрендовых доменов %d (из них с ФД %d): они держат %d ФД из %d после фильтра —'
        % (len(multi_dom), multi_fd_dom, multi_fd, all_fd))
    log('  там ФД нельзя приписать бренду. Потеря %s%% ФД; если ФД на многобрендовых доменах распределены по брендам иначе,'
        % fmt(100 * multi_fd / all_fd, 0))
    log('  чем на однобрендовых, оценка смещена — проверить нечем.')
    log('Общая доля ФД по всем доменам после фильтра: %d / %d = %s%%.' % (all_fd, all_reg, fmt(100 * all_fd / all_reg, 1)))
    log('')

    # тень периода
    log('Тень периода: доля ФД на регистрацию по месяцам и ISO-неделям (все домены после фильтра)')
    by_month = collections.defaultdict(lambda: [0, 0])
    by_week = collections.defaultdict(lambda: [0, 0])
    doms_all = {k['domain']: k for _, _, k in records}
    for k in doms_all.values():
        by_month[k['month']][0] += k['reg']
        by_month[k['month']][1] += k['fd']
        by_week[k['week']][0] += k['reg']
        by_week[k['week']][1] += k['fd']
    for m in sorted(by_month):
        reg, fd = by_month[m]
        lo, hi = wilson(fd, reg)
        log('  месяц %s: рег %3d, ФД %2d, доля %s%% [%s–%s]' % (m, reg, fd, fmt(100 * fd / reg, 1), fmt(100 * lo, 0), fmt(100 * hi, 0)))
    for w in sorted(by_week):
        reg, fd = by_week[w]
        log('  неделя %2d: рег %3d, ФД %2d, доля %s%%' % (w, reg, fd, fmt(100 * fd / reg, 1) if reg else 'nan'))
    log('')

    # по брендам
    def brand_table(field_reg, field_fd, label):
        breg = collections.Counter()
        bfd = collections.Counter()
        bdom = collections.Counter()
        bmon = collections.defaultdict(collections.Counter)
        for brand, k in single.values():
            breg[brand] += k[field_reg]
            bfd[brand] += k[field_fd]
            bdom[brand] += 1
            bmon[brand][k['month']] += k[field_reg]
        sel = sorted([b for b in breg if breg[b] >= MIN_REG], key=lambda b: (-breg[b], b))
        R = sum(breg[b] for b in sel)
        F = sum(bfd[b] for b in sel)
        p0 = s_fd / s_reg if field_reg == 'reg' else (sum(bfd.values()) / sum(breg.values()))
        log('%s: бренды с ≥%d регистрациями на однобрендовых доменах — %d брендов, рег %d, ФД %d; общая доля для теста p0 = %s%%'
            % (label, MIN_REG, len(sel), R, F, fmt(100 * p0, 1)))
        log('  бренд          | доменов | рег | ФД | доля ФД | 95% ДИ Уилсона | рег авг/сен | точный биномиальный p | q (БХ)')
        ps = [binom_two_sided(bfd[b], breg[b], p0) for b in sel]
        qs = bh_fdr(ps)
        pq = {b: (p, q) for b, p, q in zip(sel, ps, qs)}
        for b, p, q in zip(sel, ps, qs):
            lo, hi = wilson(bfd[b], breg[b])
            log('  %-14s | %7d | %3d | %2d | %5s%% | %3s–%3s%% | %3d/%-3d | %s | %s'
                % (b, bdom[b], breg[b], bfd[b], fmt(100 * bfd[b] / breg[b], 0), fmt(100 * lo, 0), fmt(100 * hi, 0),
                   bmon[b]['08'], bmon[b]['09'], fmt(p, 3), fmt(q, 3)))
        return breg, bfd, bdom, sel, p0, pq

    breg, bfd, bdom, sel, p0, pq = brand_table('reg', 'fd', 'ЗА ВСЁ ВРЕМЯ')
    n_hi = sum(1 for b in sel if bfd[b] / breg[b] >= 0.35)
    n_zero = sum(1 for b in sel if bfd[b] == 0)
    log('  Брендов с долей ФД ≥35%%: %d; брендов с 0 ФД при ≥%d рег: %d.' % (n_hi, MIN_REG, n_zero))
    log('')

    # 1) параметрический биномиальный тест неоднородности
    pairs_obs = [(bfd[b], breg[b]) for b in sel]
    chi_obs, df = chi2_hom(pairs_obs)
    R = sum(r for _, r in pairs_obs)
    F = sum(f for f, _ in pairs_obs)
    pbar = F / R
    sims = []
    for _ in range(NPERM):
        pairs = []
        for _, r in pairs_obs:
            f = sum(1 for _ in range(r) if rng.random() < pbar)
            pairs.append((f, r))
        sims.append(chi2_hom(pairs)[0])
    p_param = pval_ge(sims, chi_obs)
    log('Тест 1 (параметрический): ФД бренда ~ Binom(рег, %s%%) для %d брендов, %d розыгрышей.' % (fmt(100 * pbar, 1), len(sel), NPERM))
    log('  χ² однородности наблюд. = %s (df = %d, χ²/df = %s); нуль: среднее %s, 95-й перц. %s; p = %s'
        % (fmt(chi_obs, 2), df, fmt(chi_obs / df, 2), fmt(sum(sims) / NPERM, 2), fmt(pct(sims, 0.95), 2), fmt(p_param, 4)))
    log('')

    # 2) перестановка имён брендов между однобрендовыми доменами
    dom_list = list(single.items())   # (domain, (brand, k))
    labels = [b for _, (b, _) in dom_list]
    keys = [k for _, (_, k) in dom_list]

    def perm_stat(lbls, field_reg='reg', field_fd='fd'):
        rr = collections.Counter()
        ff = collections.Counter()
        for lb, k in zip(lbls, keys):
            rr[lb] += k[field_reg]
            ff[lb] += k[field_fd]
        pr = [(ff[b], rr[b]) for b in rr if rr[b] >= MIN_REG]
        if len(pr) < 2:
            return float('nan'), 0
        c, d = chi2_hom(pr)
        return c / d, len(pr)

    stat_obs, nb_obs = perm_stat(labels)
    p_perm = {}
    log('Тест 2 (перестановка имён брендов между %d однобрендовыми доменами, домен хранит свои рег и ФД; статистика χ²/df по брендам с ≥%d рег):'
        % (len(dom_list), MIN_REG))
    for strat_name, strat_fn in [('без страты', lambda k: 0), ('внутри ISO-недели запуска', lambda k: k['week']),
                                 ('внутри дня запуска', lambda k: k['day'])]:
        groups = collections.defaultdict(list)
        for i, k in enumerate(keys):
            groups[strat_fn(k)].append(i)
        sims = []
        nbs = []
        for _ in range(NPERM):
            lb = list(labels)
            for idx in groups.values():
                vals = [lb[i] for i in idx]
                rng.shuffle(vals)
                for i, v in zip(idx, vals):
                    lb[i] = v
            s, nb = perm_stat(lb)
            sims.append(s)
            nbs.append(nb)
        p_perm[strat_name] = pval_ge(sims, stat_obs)
        log('  %-28s страт %3d: наблюд. χ²/df = %s (брендов %d); нуль: среднее %s, 95-й перц. %s (брендов в среднем %.1f); p = %s'
            % (strat_name, len(groups), fmt(stat_obs, 2), nb_obs, fmt(sum(x for x in sims if x == x) / max(1, sum(1 for x in sims if x == x)), 2),
               fmt(pct(sims, 0.95), 2), sum(nbs) / NPERM, fmt(p_perm[strat_name], 4)))
    log('')

    # 3) O/E со стратой
    log('Тест 3 (O/E со стратой): E ФД бренда = Σ по его однобрендовым доменам (рег домена × доля ФД страты по всем доменам страты).')
    strata_defs = [('набор контента + день', lambda k: (k['content'], k['day'])),
                   ('день запуска', lambda k: k['day']),
                   ('ISO-неделя', lambda k: k['week'])]
    oe_tables = {}
    E_tables = {}
    for sname, sfn in strata_defs:
        st_reg = collections.Counter()
        st_fd = collections.Counter()
        st_ndom = collections.Counter()
        for k in doms_all.values():
            st_reg[sfn(k)] += k['reg']
            st_fd[sfn(k)] += k['fd']
            st_ndom[sfn(k)] += 1
        E = collections.Counter()
        E_alone = collections.Counter()   # часть E из страт, где домен бренда — единственный конвертирующий
        for brand, k in single.values():
            s = sfn(k)
            share = st_fd[s] / st_reg[s]
            E[brand] += k['reg'] * share
            if st_ndom[s] == 1:
                E_alone[brand] += k['reg'] * share
        n_alone = sum(1 for s in st_ndom if st_ndom[s] == 1)
        log('  Страта «%s»: страт с конверсиями %d, из них с одним доменом %d (в такой страте O/E домена = 1 по построению).'
            % (sname, len(st_ndom), n_alone))
        log('    бренд          | O ФД | E ФД | O/E | доля E из одиночных страт')
        oe_tables[sname] = {}
        E_tables[sname] = E
        for b in sel:
            oe = bfd[b] / E[b] if E[b] > 0 else float('nan')
            oe_tables[sname][b] = oe
            log('    %-14s | %4d | %5s | %5s | %s%%' % (b, bfd[b], fmt(E[b], 2), fmt(oe, 2),
                                                        fmt(100 * E_alone[b] / E[b], 0) if E[b] else 'nan'))
        so = sum(bfd[b] for b in sel)
        se = sum(E[b] for b in sel)
        log('    итого по %d брендам: O = %d, E = %s' % (len(sel), so, fmt(se, 2)))
    log('')

    # 4) Спирмен ранг по регистрациям против ФД/рег
    log('Тест 4: Спирмен между регистрациями бренда и его долей ФД/рег (однобрендовые домены), перестановочный p (%d):' % NPERM)
    rho_regfd = {}
    for thr in (MIN_REG, 3):
        bl = [b for b in breg if breg[b] >= thr]
        x = [breg[b] for b in bl]
        y = [bfd[b] / breg[b] for b in bl]
        rho = spearman(x, y)
        sims = []
        for _ in range(NPERM):
            yy = list(y)
            rng.shuffle(yy)
            sims.append(spearman(x, yy))
        p2 = (sum(1 for v in sims if abs(v) >= abs(rho)) + 1) / (NPERM + 1)
        rho_regfd[thr] = (rho, p2, len(bl))
        log('  бренды с ≥%d рег (n = %d): Спирмен = %s, двусторонний p = %s' % (thr, len(bl), fmt(rho, 3), fmt(p2, 3)))
    log('')

    # оконная версия
    bregw, bfdw, bdomw, selw, p0w, pqw = brand_table('regw', 'fdw', 'В ОКНЕ 3 СУТОК')
    pairs_w = [(bfdw[b], bregw[b]) for b in selw]
    chi_w, dfw = chi2_hom(pairs_w)
    Rw = sum(r for _, r in pairs_w)
    Fw = sum(f for f, _ in pairs_w)
    pbw = Fw / Rw if Rw else 0
    sims = []
    for _ in range(NPERM):
        sims.append(chi2_hom([(sum(1 for _ in range(r) if rng.random() < pbw), r) for _, r in pairs_w])[0])
    p_param_w = pval_ge(sims, chi_w)
    log('  Параметрический тест в окне: χ² = %s (df = %d), p = %s.' % (fmt(chi_w, 2), dfw, fmt(p_param_w, 4)))
    stat_w, nb_w = perm_stat(labels, 'regw', 'fdw')
    sims = []
    groups = collections.defaultdict(list)
    for i, k in enumerate(keys):
        groups[k['week']].append(i)
    for _ in range(NPERM):
        lb = list(labels)
        for idx in groups.values():
            vals = [lb[i] for i in idx]
            rng.shuffle(vals)
            for i, v in zip(idx, vals):
                lb[i] = v
        sims.append(perm_stat(lb, 'regw', 'fdw')[0])
    p_perm_w = pval_ge(sims, stat_w)
    log('  Перестановка внутри ISO-недели в окне: χ²/df = %s (брендов %d), p = %s.' % (fmt(stat_w, 2), nb_w, fmt(p_perm_w, 4)))
    log('')

    # ------------------------------------------------------------ вывод
    log('=' * 100)
    log('ВЫВОД')
    log('=' * 100)
    par, aug, cln, noc = summary_a
    n_events = sum(n for _, n, _ in records)
    core = sorted(par['obs']['top_A'] & par['obs']['top_B'])
    log('Часть (а) — есть ли список брендов по конверсиям и воспроизводим ли он (%d событий = регистрации + ФД на %d доменах после фильтра).'
        % (n_events, n_conv_dom))
    log('  1. Список существует: топ-10 брендов держат %s%% всех конверсий, тогда как при случайном бренде записи было бы %s%%'
        % (fmt(100 * par['obs']['top10_all'], 0), fmt(100 * par['top10_all_null'], 0)))
    log('     (нуль R-K, p = %s); брендов с конверсиями %d вместо ожидаемых при случайном выборе из 206 — около %.0f.'
        % (fmt(par['p_top10_all'], 4), K, nb206_null[par['title']]))
    log('  2. Верхушка списка воспроизводится: топ-10 по одной половине запусков собирает %s%% другой половины при разбиении'
        % fmt(100 * par['t10'], 0))
    log('     по чётности дня (при случайности %s%%, p = %s), %s%% при разбиении август → сентябрь (p = %s),'
        % (fmt(100 * par['t10_null'], 0), fmt(par['p_t10'], 4), fmt(100 * aug['t10'], 0), fmt(aug['p_t10'], 4)))
    log('     %s%% на доменах с чистой оконной атрибуцией (p = %s) и %s%% без «%s» (p = %s). Порог постановки 25%% выполнен'
        % (fmt(100 * cln['t10'], 0), fmt(cln['p_t10'], 4), fmt(100 * noc['t10'], 0), NOCONTENT, fmt(noc['p_t10'], 4)))
    log('     в двух главных разбиениях и почти выполнен в двух контрольных. В обеих половинах по чётности в топ-10 входят %d брендов'
        % len(core))
    log('     (%s) при %.1f ожидаемых по случайности (p = %s); авг → сен — %d брендов при %.1f (p = %s).'
        % (', '.join(core) or '—', par['overlap_null'], fmt(par['p_overlap'], 4),
           aug['obs']['overlap'], aug['overlap_null'], fmt(aug['p_overlap'], 4)))
    log('  3. Но порядок внутри списка не воспроизводится. Спирмен по брендам с ≥3 конверсиями = %s (чётность) и %s (авг → сен) —'
        % (fmt(par['obs']['rho'], 2), fmt(aug['obs']['rho'], 2)))
    log('     это далеко от 0,4–0,7 из постановки. Однако сам критерий здесь неприменим: у бренда с 3–6 конверсиями A + B почти'
        )
    log('     постоянна, поэтому под нулём «бренд случаен» Спирмен по таким брендам не 0, а около %s; наблюдённое выше нуля с p = %s.'
        % (fmt(par['rho_null'], 2), fmt(par['p_rho'], 4)))
    log('     Честная мера порядка — Спирмен по всем %d брендам с нулями (нуль около %s): %s при чётности (p = %s), %s авг → сен (p = %s).'
        % (K, fmt(par['rho_all_null'], 2), fmt(par['obs']['rho_all'], 2), fmt(par['p_rho_all'], 4),
           fmt(aug['obs']['rho_all'], 2), fmt(aug['p_rho_all'], 4)))
    log('     То есть: «эти 10–15 брендов конвертируют, остальные почти нет» — устойчиво; «кто из них первый, кто десятый» — шум.')
    log('')
    log('Часть (б) — те ли это бренды по ФД (только %d однобрендовых доменов: %d рег, %d ФД; потеряно %d из %d ФД на многобрендовых доменах).'
        % (len(single), s_reg, s_fd, multi_fd, all_fd))
    top_names = ', '.join('%s %d из %d' % (b, bfd[b], breg[b]) for b in sel if bfd[b] / breg[b] >= 0.35)
    zero_names = ', '.join('%s 0 из %d' % (b, breg[b]) for b in sel if bfd[b] == 0)
    log('  1. Картина из постановки воспроизводится буквально: с долей ФД ≥35%% — %s; с 0 ФД при ≥%d рег — %s.'
        % (top_names or 'никого', MIN_REG, zero_names or 'никого'))
    log('  2. Но разброс долей не больше биномиального шума: биномиальный тест неоднородности по %d брендам p = %s;'
        % (len(sel), fmt(p_param, 2)))
    log('     перестановка брендов между доменами p = %s без страты, %s внутри недели запуска, %s внутри дня запуска;'
        % (fmt(p_perm['без страты'], 2), fmt(p_perm['внутри ISO-недели запуска'], 2), fmt(p_perm['внутри дня запуска'], 2)))
    hi_b = [b for b in sel if bfd[b] / breg[b] >= 0.35]
    zero_b = [b for b in sel if bfd[b] == 0]
    log('     в окне 3 суток p = %s и %s. Точный биномиальный на бренд: %s до поправки, после поправки'
        % (fmt(p_param_w, 2), fmt(p_perm_w, 2),
           '; '.join('%s p = %s' % (b, fmt(pq[b][0], 2)) for b in hi_b) or 'нет брендов с долей ≥35%'))
    log('     на %d сравнений %s; у брендов с 0 ФД p ≥ %s даже без поправки (0 из %d при доле %s%% ожидается в %s%% случаев).'
        % (len(sel), ', '.join('q = %s' % fmt(pq[b][1], 2) for b in hi_b) or '—',
           fmt(min(pq[b][0] for b in zero_b), 2) if zero_b else 'nan',
           max(breg[b] for b in zero_b) if zero_b else 0, fmt(100 * p0, 0),
           fmt(100 * (1 - p0) ** max(breg[b] for b in zero_b), 0) if zero_b else 'nan'))
    Ew = E_tables['ISO-неделя']
    log('  3. Тень периода: доля ФД в августе %s%% (%d из %d), в сентябре %s%% (%d из %d). Олимп поставил %d из %d регистраций в августе,'
        % (fmt(100 * by_month['08'][1] / by_month['08'][0], 0), by_month['08'][1], by_month['08'][0],
           fmt(100 * by_month['09'][1] / by_month['09'][0], 0), by_month['09'][1], by_month['09'][0],
           sum(k['reg'] for b, k in single.values() if b == 'Олимп' and k['month'] == '08'), breg['Олимп']))
    log('     поэтому его ожидание ФД по страте «неделя» всего %s, у Dragon Money %s, у Luckybear %s — ноль ФД у них ничего не значит.'
        % (fmt(Ew['Олимп'], 1), fmt(Ew['Dragon Money'], 1), fmt(Ew['Luckybear'], 1)))
    log('     Leon (O/E %s) и Martin (O/E %s) по той же страте — единственный намёк на «депозитные» бренды, но вдвоём они не делают тест значимым.'
        % (fmt(oe_tables['ISO-неделя']['Leon'], 1), fmt(oe_tables['ISO-неделя']['Martin'], 1)))
    r5 = rho_regfd[MIN_REG]
    r3 = rho_regfd[3]
    log('  4. Ранг по регистрациям против ФД/рег: Спирмен %s (n = %d, p = %s) и %s (n = %d, p = %s) — не отрицательный и не ≤0,1,'
        % (fmt(r5[0], 2), r5[2], fmt(r5[1], 2), fmt(r3[0], 2), r3[2], fmt(r3[1], 2)))
    log('     как ждала постановка; если что-то и есть, то бренды с большим числом регистраций дают ФД не реже, а чаще.')
    log('')
    log('ИТОГ. Гипотеза подтверждена частично. Список «конвертирующих» брендов существует и его верхушка воспроизводится между')
    log('  половинами запусков (топ-10 одной половины собирает %s–%s%% другой против %s%% при случайности, p ≤ %s), но ранги внутри'
        % (fmt(100 * min(par['t10'], aug['t10'], cln['t10'], noc['t10']), 0),
           fmt(100 * max(par['t10'], aug['t10'], cln['t10'], noc['t10']), 0), fmt(100 * par['t10_null'], 0),
           fmt(max(par['p_t10'], aug['p_t10'], cln['p_t10'], noc['p_t10']), 4)))
    log('  списка шумные. Вторая половина — «бренды ФД не те же, что бренды регистраций» — на этих данных НЕ подтверждается:')
    log('  различия долей ФД между брендами укладываются в биномиальный шум (p = %s–%s), а бренды с нулём ФД — это бренды,'
        % (fmt(min(p_param, *p_perm.values()), 2), fmt(max(p_param, *p_perm.values()), 2)))
    log('  чьи регистрации пришлись на август, когда ФД было вдвое меньше у всех. Для решения нужны примерно вчетверо больше')
    log('  регистраций на бренд внутри одного периода (сейчас 5–14 на бренд).')
    log('')
    log('ЧТО С ЭТИМ ДЕЛАТЬ (проверяемо на уже запущенных данных).')
    log('  1. Вести список конвертирующих брендов по сумме «регистрации + ФД» и обновлять его по половинам запусков, как здесь:')
    log('     устойчивое ядро — бренды, входящие в топ-10 в обеих половинах (%s); остальные позиции списка не считать рангом.'
        % (', '.join(core) or '—'))
    log('  2. Отдельный «список брендов по ФД» не вести — он не отличим от списка по регистрациям, и его нули объясняются месяцем запуска.')
    log('  3. Не отбрасывать Олимп, Dragon Money, Luckybear за «0 ФД»: их ожидание ФД по неделе запуска ≈1, ноль — норма.')
    log('  4. Проверить на своде, устойчив ли скачок доли ФД %s%% → %s%% между августом и сентябрём внутри одного набора контента и зоны:'
        % (fmt(100 * by_month['08'][1] / by_month['08'][0], 0), fmt(100 * by_month['09'][1] / by_month['09'][0], 0)))
    log('     если это период (трекер, оффер), а не контент, любые сравнения по ФД между запусками разных месяцев надо стратифицировать по неделе.')
    log('  5. Восстановить атрибуцию %d ФД на %d многобрендовых доменах из журнала конверсий (в своде её нет) — тогда объём по ФД вырастет почти вдвое.'
        % (multi_fd, len(multi_dom)))
    log.close()


if __name__ == '__main__':
    main()

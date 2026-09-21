#!/usr/bin/env python3
"""
Гипотеза №8. День недели запуска.

Что проверяем.
  (1) Запуск в субботу–воскресенье сам по себе не снижает выход в поиск:
      сырое отставание выходных — это состав наборов контента, которые ставили
      в выходные. Ожидание после страты по набору: O/E 0,9–1,1, p > 0,2.
  (2) Воскресный запуск — единственный день, где регистраций на поисковый
      клик в 2–3 раза меньше при нормальном выходе (O/E по рег/клик 0,4–0,5,
      p < 0,05). Внешняя проверка на воскресенье 20.09 (70 доменов, окно
      закроется 24.09): по гипотезе <= 5 регистраций и <= 1 рег на 10 тыс.
      кликов; опровержение — >= 10 регистраций.
  (3) Попадание дня 2 (остатка 56 брендов) на сб/вс ничего не стоит:
      O/E 0,9–1,1 по выходу и регистрациям.

Как проверяем.
  Данные: analysis/export/svod_domenov_21.09.csv, csv.DictReader, только
  стандартная библиотека.
  Фильтр: окно закрыто = да; дней != 1; без «КОНТЕНТ НЕ ЗАПИСАН» (не набор,
  сцеплен с датой); без выбросов 3615.team и 3286.team (миллионы «прочих»
  кликов) — исключены везде, чтобы не путать; оба августовские и в главные
  страты всё равно не попали бы. День недели считаем из даты запуска
  (колонка «день недели» расходится с датой в 68 строках и не используется).
  Страта главная: набор контента + зона. Набором считаем имя из колонки
  «набор контента» без номера экземпляра «_N» на конце (так делали все
  прошлые разборы «корней»; варианты -1/-2/-3 остаются разными наборами).
  Зоны team/lol/casino/buzz, остальные — «прочие». В расчёт входят только
  страты, где есть обе сравниваемые группы (для (1) — выходной и будний
  запуск; для (2) — воскресенье и не-воскресенье; для 7 уровней и (3) —
  не менее двух разных дней недели).
  Страта вторичная (грубая): семейство + страниц + оформление + зона по
  запускам с 01.09 (в августе после фильтра выходных запусков нет).
  Три метрики, ожидание считается по доле страты:
    выход: O = вышли за 3 суток, E = (Σвышли/Σсайтов в страте) × сайтов в окне;
    рег/клик: O = регистраций в окне 3 суток, E = (Σрег/Σкликов из поиска
      в окне по страте) × кликов из поиска в окне домена;
    рег/сайт: E = (Σрег/Σсайтов по страте) × сайтов в окне.
  O/E группы = ΣO/ΣE по доменам группы.
  Тесты: перестановка дня недели внутри страты, 10 000 раз, random.seed(1),
  два уровня — по доменам (единица = домен) и по датам запуска (внутри
  страты перемешиваются метки дат: честнее, потому что день недели — свойство
  даты, а не домена; перестановок мало, интервалы шире). p двусторонний =
  2·min(P(T* <= T), P(T* >= T)), не больше 1. Для (2) дополнительно точный
  пуассоновский тест O при E и поправка Бонферрони ×7; семейный тест
  «худший день» — min O/E по дням в перестановках. Знаковый критерий по
  пулам (страта набор+зона) для (1). χ² по 7 дням = Σ(O−E)²/E, p по
  перестановкам.
  (3): день 2 = день запуска + 1, поэтому «день 2 в сб» = пятничные запуски,
  «в вс» = субботние, «в пн» = воскресные; это те же группы дня недели
  запуска с другой подписью, отдельно от (1) на своде не отделяется.
  Чувствительность оговорена: остаток 56 брендов даёт ~17 % выходов
  (по реестру: 8,7 % против 15,4 % у первых 150), падение остатка вдвое =
  −9 % по домену; сравниваем с нулевым 95 % интервалом O/E.
  Внешняя проверка: воскресенье 20.09 (окно не закрыто) — регистрации и клики
  в окне на момент выгрузки 21.09; суббота 19.09 рядом для сравнения.

Вывод пишется и в stdout, и в файл
analysis/export/gipotezy_svod/h08_launch_weekday.txt.
"""

import csv
import datetime as dt
import math
import os
import random
import re
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(ANALYSIS, 'export', 'gipotezy_svod')
OUT_PATH = os.path.join(OUT_DIR, 'h08_launch_weekday.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
SEED = 1
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'
MAIN_ZONES = {'team', 'lol', 'casino', 'buzz'}
WD = {1: 'пн', 2: 'вт', 3: 'ср', 4: 'чт', 5: 'пт', 6: 'сб', 7: 'вс'}
WEEKEND = {6, 7}
SEPT_START = dt.date(2026, 9, 1)
CHECK_SUNDAY = dt.date(2026, 9, 20)
CHECK_SATURDAY = dt.date(2026, 9, 19)
# метрики: индексы в векторе (Oвыход, Eвыход, Oрег, Eрег/клик, Eрег/сайт)
M_EXIT, M_REGCLK, M_REGSITE = 0, 1, 2
METRIC_NAME = {M_EXIT: 'выход', M_REGCLK: 'рег/клик', M_REGSITE: 'рег/сайт'}

_out = []


def P(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _out.append(s)


def toi(s):
    return int(float(s)) if s not in ('', None) else 0


def ratio(o, e, nd=2):
    return f'{o / e:.{nd}f}' if e > 0 else '—'


def per(o, n, k=100, nd=1):
    return f'{o / n * k:.{nd}f}' if n > 0 else '—'


def pctl(sorted_vals, q):
    if not sorted_vals:
        return float('nan')
    i = int(round(q * (len(sorted_vals) - 1)))
    return sorted_vals[max(0, min(len(sorted_vals) - 1, i))]


def p_two_sided(perm_vals, obs):
    """Двусторонний перестановочный p: 2·min(P(T* <= T), P(T* >= T)), <= 1."""
    vals = [v for v in perm_vals if v == v]  # без nan
    if not vals or obs != obs:
        return float('nan')
    lo = sum(1 for v in vals if v <= obs + 1e-12) / len(vals)
    hi = sum(1 for v in vals if v >= obs - 1e-12) / len(vals)
    return min(1.0, 2 * min(lo, hi))


def p_ge(perm_vals, obs):
    vals = [v for v in perm_vals if v == v]
    if not vals or obs != obs:
        return float('nan')
    return sum(1 for v in vals if v >= obs - 1e-12) / len(vals)


def p_le(perm_vals, obs):
    vals = [v for v in perm_vals if v == v]
    if not vals or obs != obs:
        return float('nan')
    return sum(1 for v in vals if v <= obs + 1e-12) / len(vals)


def poisson_tests(o, e):
    """Точный пуассоновский тест: односторонний P(X <= o | e) и двусторонний
    (сумма вероятностей исходов не вероятнее наблюдённого)."""
    if e <= 0:
        return float('nan'), float('nan')

    def logpmf(k):
        return -e + k * math.log(e) - math.lgamma(k + 1)

    kmax = int(e + 10 * math.sqrt(e) + 50)
    pm = [math.exp(logpmf(k)) for k in range(kmax + 1)]
    one = sum(pm[:o + 1]) if o <= kmax else 1.0
    ref = pm[o] if o <= kmax else 0.0
    two = sum(v for v in pm if v <= ref + 1e-15)
    return min(1.0, one), min(1.0, two)


def binom_two_sided(k, n, p0=0.5):
    if n == 0:
        return 1.0
    lg = math.lgamma

    def logpmf(i):
        return lg(n + 1) - lg(i + 1) - lg(n - i + 1) + i * math.log(p0) + (n - i) * math.log(1 - p0)

    ref = logpmf(k) + 1e-9
    return min(1.0, sum(math.exp(logpmf(i)) for i in range(n + 1) if logpmf(i) <= ref))


def fmt_p(p):
    if p != p:
        return '—'
    if p < 1e-4:
        return '<0,0001'
    return f'{p:.4f}'.replace('.', ',')


def fr(x, nd=2):
    return f'{x:.{nd}f}' if x == x else '—'


# ---------------------------------------------------------------------------
# 1. Загрузка, подготовка, фильтр
# ---------------------------------------------------------------------------

def root_name(name):
    """Имя набора без номера экземпляра «_N» на конце."""
    return re.sub(r'_\d+$', '', name)


def prepare(r):
    d = {}
    d['домен'] = r['домен']
    zone = r['зона']
    d['зона'] = zone if zone in MAIN_ZONES else 'прочие'
    d['день'] = dt.date.fromisoformat(r['день запуска'])
    d['wd'] = d['день'].isoweekday()
    d['wd_col'] = r['день недели']
    d['набор'] = r['набор контента']
    d['корень'] = root_name(r['набор контента'])
    d['семейство'] = r['семейство']
    d['страниц'] = r['страниц'] or '—'
    d['оформление'] = r['оформление'] or '—'
    d['сайтов'] = toi(r['сайтов в окне'])
    d['сайтов всего'] = toi(r['сайтов'])
    d['вышли'] = toi(r['вышли за 3 суток'])
    d['клики'] = toi(r['кликов из поиска в окне'])
    d['рег'] = toi(r['регистраций в окне 3 суток'])
    d['фд'] = toi(r['ФД в окне 3 суток'])
    d['окно'] = r['окно закрыто']
    d['дней'] = r['дней']
    return d


def load_and_filter():
    with open(CSV_PATH, encoding='utf-8', newline='') as fh:
        rows = [prepare(r) for r in csv.DictReader(fh)]
    P(f'Строк в своде: {len(rows)}')
    mism = sum(1 for d in rows if str(d['wd']) != d['wd_col'])
    P(f'Колонка «день недели» расходится с датой запуска в {mism} строках — '
      f'день недели везде берём из даты запуска.')
    steps = [
        ('окно закрыто = нет', lambda d: d['окно'] != 'да'),
        ('дней = 1 (день 2 не наступил)', lambda d: d['дней'] == '1'),
        ('«КОНТЕНТ НЕ ЗАПИСАН»', lambda d: d['набор'] == NO_CONTENT),
        ('выбросы 3615.team, 3286.team', lambda d: d['домен'] in OUTLIERS),
    ]
    kept = rows
    for name, bad in steps:
        n0 = len(kept)
        kept = [d for d in kept if not bad(d)]
        P(f'  исключено «{name}»: {n0 - len(kept)} строк, осталось {len(kept)}')
    return rows, kept


# ---------------------------------------------------------------------------
# 2. Ожидания по страте и таблицы O/E
# ---------------------------------------------------------------------------

def attach_expectations(doms, key):
    """Возвращает {домен: (Oвыход, Eвыход, Oрег, Eрег/клик, Eрег/сайт)} по страте key."""
    agg = defaultdict(lambda: [0, 0, 0, 0])  # сайтов, вышли, клики, рег
    for d in doms:
        a = agg[key(d)]
        a[0] += d['сайтов']
        a[1] += d['вышли']
        a[2] += d['клики']
        a[3] += d['рег']
    vals = {}
    for d in doms:
        s, o, c, r = agg[key(d)]
        p_exit = o / s if s else 0.0
        c_reg = r / c if c else 0.0
        r_site = r / s if s else 0.0
        vals[d['домен']] = (float(d['вышли']), p_exit * d['сайтов'],
                            float(d['рег']), c_reg * d['клики'], r_site * d['сайтов'])
    return vals


def sums(doms, vals):
    """ΣO, ΣE по трём метрикам и объёмы группы."""
    acc = [0.0] * 5
    n = sites = clk = reg = fd = 0
    for d in doms:
        v = vals[d['домен']]
        for i in range(5):
            acc[i] += v[i]
        n += 1
        sites += d['сайтов']
        clk += d['клики']
        reg += d['рег']
        fd += d['фд']
    return dict(n=n, sites=sites, clk=clk, reg=reg, fd=fd, o_exit=acc[0], e_exit=acc[1],
                o_reg=acc[2], e_regclk=acc[3], e_regsite=acc[4], out=int(acc[0]))


def oe_from_sums(s, m):
    if m == M_EXIT:
        return s['o_exit'] / s['e_exit'] if s['e_exit'] > 0 else float('nan')
    if m == M_REGCLK:
        return s['o_reg'] / s['e_regclk'] if s['e_regclk'] > 0 else float('nan')
    return s['o_reg'] / s['e_regsite'] if s['e_regsite'] > 0 else float('nan')


def print_group_table(title, groups, vals, with_oe=True):
    """groups: список (имя группы, список доменов)."""
    P(title)
    head = (f'{"группа":<22}{"домен.":>7}{"сайтов":>8}{"вышли":>7}{"выход%":>8}'
            f'{"кликов":>9}{"рег":>5}{"ФД":>4}{"рег/100с":>9}{"рег/10тк":>9}')
    if with_oe:
        head += f'{"O/E вых":>9}{"O/E р/кл":>10}{"O/E р/с":>9}'
    P(head)
    for name, doms in groups:
        if not doms:
            continue
        s = sums(doms, vals)
        line = (f'{name:<22}{s["n"]:>7}{s["sites"]:>8}{s["out"]:>7}{per(s["out"], s["sites"]):>8}'
                f'{s["clk"]:>9}{s["reg"]:>5}{s["fd"]:>4}{per(s["reg"], s["sites"]):>9}'
                f'{per(s["reg"], s["clk"], 10000):>9}')
        if with_oe:
            line += (f'{fr(oe_from_sums(s, M_EXIT)):>9}{fr(oe_from_sums(s, M_REGCLK)):>10}'
                     f'{fr(oe_from_sums(s, M_REGSITE)):>9}')
        P(line)


# ---------------------------------------------------------------------------
# 3. Перестановки
# ---------------------------------------------------------------------------

def perm_run(doms, vals, key, n_perm, mode):
    """Перестановка дня недели внутри страты.
    mode='domain' — перемешиваем метки по доменам; mode='date' — по датам
    запуска (кластерам) внутри страты. Возвращает список перестановок, каждая —
    список по 8 меткам (индекс = день недели 1..7) из 5 сумм."""
    strata = defaultdict(list)
    for d in doms:
        strata[key(d)].append(d)
    units = []  # (labels, values) по стратам
    for k, ds in strata.items():
        if mode == 'domain':
            labels = [d['wd'] for d in ds]
            values = [vals[d['домен']] for d in ds]
        else:
            by_date = defaultdict(lambda: [0.0] * 5)
            lab_of = {}
            for d in ds:
                v = vals[d['домен']]
                a = by_date[d['день']]
                for i in range(5):
                    a[i] += v[i]
                lab_of[d['день']] = d['wd']
            dates = sorted(by_date)
            labels = [lab_of[x] for x in dates]
            values = [tuple(by_date[x]) for x in dates]
        units.append((labels, values))
    rng = random.Random(SEED)
    out = []
    for _ in range(n_perm):
        acc = [[0.0] * 5 for _ in range(8)]
        for labels, values in units:
            labs = labels[:]
            rng.shuffle(labs)
            for lab, v in zip(labs, values):
                a = acc[lab]
                a[0] += v[0]
                a[1] += v[1]
                a[2] += v[2]
                a[3] += v[3]
                a[4] += v[4]
        out.append(acc)
    return out


def observed_acc(doms, vals):
    acc = [[0.0] * 5 for _ in range(8)]
    for d in doms:
        v = vals[d['домен']]
        a = acc[d['wd']]
        for i in range(5):
            a[i] += v[i]
    return acc


def stat_group(acc, labels, m):
    """O/E метрики m по объединению меток labels."""
    o = e = 0.0
    for lab in labels:
        a = acc[lab]
        if m == M_EXIT:
            o += a[0]
            e += a[1]
        elif m == M_REGCLK:
            o += a[2]
            e += a[3]
        else:
            o += a[2]
            e += a[4]
    return o / e if e > 0 else float('nan')


def stat_chi2(acc, m):
    x = 0.0
    for lab in range(1, 8):
        a = acc[lab]
        o, e = (a[0], a[1]) if m == M_EXIT else (a[2], a[3]) if m == M_REGCLK else (a[2], a[4])
        if e > 0:
            x += (o - e) ** 2 / e
    return x


def stat_min_day(acc, m, e_min=3.0):
    best = float('nan')
    for lab in range(1, 8):
        a = acc[lab]
        o, e = (a[0], a[1]) if m == M_EXIT else (a[2], a[3]) if m == M_REGCLK else (a[2], a[4])
        if e >= e_min:
            v = o / e
            if best != best or v < best:
                best = v
    return best


def strata_with(doms, key, group_fn, need_groups=2):
    """Оставляет домены из страт, где представлено >= need_groups разных групп."""
    seen = defaultdict(set)
    for d in doms:
        seen[key(d)].add(group_fn(d))
    ok = {k for k, g in seen.items() if len(g) >= need_groups}
    return [d for d in doms if key(d) in ok], len(ok)


def report_contrast(label, doms, vals, key, sel_labels, m, modes=('domain', 'date'),
                    extra=None, n_perm=N_PERM):
    """Печатает O/E группы sel_labels по метрике m с перестановочными p и
    нулевым 95 % интервалом. extra — список доп. статистик (имя, функция от acc)."""
    obs_acc = observed_acc(doms, vals)
    obs = stat_group(obs_acc, sel_labels, m)
    o = sum(obs_acc[l][0 if m == M_EXIT else 2] for l in sel_labels)
    e = sum(obs_acc[l][1 if m == M_EXIT else 3 if m == M_REGCLK else 4] for l in sel_labels)
    P(f'{label}: O = {o:.0f}, E = {e:.1f}, O/E = {fr(obs)}')
    res = {'obs': obs, 'O': o, 'E': e}
    for mode in modes:
        perms = perm_run(doms, vals, key, n_perm, mode)
        vals_t = [stat_group(acc, sel_labels, m) for acc in perms]
        sv = sorted(v for v in vals_t if v == v)
        p2 = p_two_sided(vals_t, obs)
        pl = p_le(vals_t, obs)
        P(f'    перестановка по {"доменам" if mode == "domain" else "датам"} внутри страты '
          f'({n_perm}): p двуст. = {fmt_p(p2)}, P(O/E* <= набл.) = {fmt_p(pl)}, '
          f'нулевой 95 % интервал O/E {fr(pctl(sv, 0.025))}–{fr(pctl(sv, 0.975))}')
        res[mode] = dict(p2=p2, pl=pl, lo=pctl(sv, 0.025), hi=pctl(sv, 0.975), perms=perms)
        if extra:
            for name, fn in extra:
                ov = fn(obs_acc)
                pv = [fn(acc) for acc in perms]
                if name.startswith('χ²'):
                    P(f'      {name}: набл. {fr(ov, 1)}, p = {fmt_p(p_ge(pv, ov))}')
                else:
                    P(f'      {name}: набл. {fr(ov)}, P(min* <= набл.) = {fmt_p(p_le(pv, ov))}')
    return res


def print_weekday_oe(title, doms, vals):
    groups = [(WD[w], [d for d in doms if d['wd'] == w]) for w in range(1, 8)]
    print_group_table(title, groups, vals)


# ---------------------------------------------------------------------------
# 4. Основной ход
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    P('=' * 100)
    P('Гипотеза №8. День недели запуска: выходные, воскресенье и день 2')
    P('=' * 100)
    all_rows, doms = load_and_filter()
    key_main = lambda d: (d['корень'], d['зона'])
    key_sec = lambda d: (d['семейство'], d['страниц'], d['оформление'], d['зона'])
    is_wend = lambda d: d['wd'] in WEEKEND
    is_sun = lambda d: d['wd'] == 7

    n_names = len({d['набор'] for d in doms})
    n_roots = len({d['корень'] for d in doms})
    P(f'Наборов контента (имён) после фильтра: {n_names}; без номера экземпляра «_N»: {n_roots}.')

    # ---- 1. сырая картина по дням недели
    P('')
    P('-' * 100)
    P('1. СЫРАЯ КАРТИНА ПО ДНЯМ НЕДЕЛИ ЗАПУСКА (после фильтра, без страт)')
    P('-' * 100)
    vals_none = attach_expectations(doms, lambda d: 'все')
    print_weekday_oe('O/E здесь — к общему среднему по всему набору (без страт):', doms, vals_none)
    P('')
    P('Выходные даты и наборы на них (после фильтра):')
    for day in sorted({d['день'] for d in doms if is_wend(d)}):
        ds = [d for d in doms if d['день'] == day]
        s = sums(ds, vals_none)
        P(f'  {day} ({WD[day.isoweekday()]}): {s["n"]} доменов, {s["sites"]} сайтов, выход '
          f'{per(s["out"], s["sites"])} %, {s["clk"]} кликов, {s["reg"]} рег '
          f'({per(s["reg"], s["clk"], 10000)} на 10 тыс.)')
        roots = Counter(d['корень'] for d in ds)
        for rname, cnt in roots.most_common():
            rd = [d for d in ds if d['корень'] == rname]
            sr = sums(rd, vals_none)
            other_days = sorted({(x['день'], WD[x['день'].isoweekday()]) for x in doms
                                 if x['корень'] == rname and x['день'] != day})
            od = ', '.join(f'{x[0].strftime("%d.%m")} {x[1]}' for x in other_days) or 'нет'
            P(f'      {rname:<44} {cnt:>3} дом., выход {per(sr["out"], sr["sites"]):>5} %, '
              f'{sr["reg"]:>2} рег, {per(sr["reg"], sr["clk"], 10000):>5}/10 тыс.; '
              f'другие даты набора: {od}')

    # ---- 2. страты
    P('')
    P('-' * 100)
    P('2. СТРАТЫ')
    P('-' * 100)
    roots_days = defaultdict(lambda: defaultdict(int))
    for d in doms:
        roots_days[d['корень']][d['день']] += 1
    multi = {r: v for r, v in roots_days.items() if len({x.isoweekday() for x in v}) >= 2}
    P(f'Наборов (без «_N») с запусками в >= 2 разных дня недели: {len(multi)} '
      f'({sum(sum(v.values()) for v in multi.values())} доменов). Перечень:')
    for rname in sorted(multi, key=lambda r: -sum(multi[r].values())):
        v = multi[rname]
        P(f'  {rname:<46} {sum(v.values()):>3} дом.: ' +
          ', '.join(f'{x.strftime("%d.%m")} {WD[x.isoweekday()]} ×{v[x]}' for x in sorted(v)))
    doms_multi = [d for d in doms if d['корень'] in multi]
    main_c, n_main_c = strata_with(doms_multi, key_main, lambda d: d['wd'], 2)
    main_a, n_main_a = strata_with(doms_multi, key_main, is_wend, 2)
    main_b, n_main_b = strata_with(doms_multi, key_main, is_sun, 2)
    sept = [d for d in doms if d['день'] >= SEPT_START]
    sec_c, n_sec_c = strata_with(sept, key_sec, lambda d: d['wd'], 2)
    sec_a, n_sec_a = strata_with(sept, key_sec, is_wend, 2)
    sec_b, n_sec_b = strata_with(sept, key_sec, is_sun, 2)
    P('')
    P('Главная страта = набор контента (без «_N») + зона; вторичная = семейство + страниц + '
      'оформление + зона, запуски с 01.09.')
    P(f'  главная, >= 2 дней недели в страте:      {n_main_c} страт, {len(main_c)} доменов')
    P(f'  главная, выходной и будний в страте:      {n_main_a} страт, {len(main_a)} доменов')
    P(f'  главная, воскресенье и не-вс в страте:    {n_main_b} страт, {len(main_b)} доменов')
    P(f'  вторичная (сентябрь, {len(sept)} дом.), >= 2 дней недели: {n_sec_c} страт, {len(sec_c)} доменов')
    P(f'  вторичная, выходной и будний:             {n_sec_a} страт, {len(sec_a)} доменов')
    P(f'  вторичная, воскресенье и не-вс:           {n_sec_b} страт, {len(sec_b)} доменов')

    # ---- 3. контраст 1: выходные vs будни по выходу
    P('')
    P('-' * 100)
    P('3. КОНТРАСТ (1): сб+вс против будней по выходу в поиск')
    P('-' * 100)
    vals_sec_a = attach_expectations(sec_a, key_sec)
    print_group_table('3а. Грубая страта (семейство + страниц + оформление + зона, сентябрь):',
                      [('выходной (сб+вс)', [d for d in sec_a if is_wend(d)]),
                       ('будни', [d for d in sec_a if not is_wend(d)])], vals_sec_a)
    r_sec_a = report_contrast('   выходной, выход, грубая страта', sec_a, vals_sec_a, key_sec,
                              [6, 7], M_EXIT)
    P('')
    vals_main_a = attach_expectations(main_a, key_main)
    print_group_table('3б. Главная страта (набор контента + зона):',
                      [('выходной (сб+вс)', [d for d in main_a if is_wend(d)]),
                       ('будни', [d for d in main_a if not is_wend(d)])], vals_main_a)
    r_main_a = report_contrast('   выходной, выход, главная страта', main_a, vals_main_a, key_main,
                               [6, 7], M_EXIT)
    P('   те же страты, деньги (для полноты):')
    r_main_a_reg = report_contrast('   выходной, рег/клик, главная страта', main_a, vals_main_a,
                                   key_main, [6, 7], M_REGCLK, modes=('domain',))
    r_main_a_rs = report_contrast('   выходной, рег/сайт, главная страта', main_a, vals_main_a,
                                  key_main, [6, 7], M_REGSITE, modes=('domain',))
    # знаковый критерий по пулам
    P('')
    P('3в. Знаковый критерий по пулам (страта набор+зона; выход выходной против буднего):')
    P(f'   {"страта":<58}{"вых.дом":>8}{"вых.%":>7}{"буд.дом":>8}{"буд.%":>7} знак')
    pools = defaultdict(list)
    for d in main_a:
        pools[key_main(d)].append(d)
    plus = minus = ties = 0
    for k in sorted(pools):
        ds = pools[k]
        w = sums([d for d in ds if is_wend(d)], vals_main_a)
        b = sums([d for d in ds if not is_wend(d)], vals_main_a)
        pw = w['out'] / w['sites'] if w['sites'] else 0
        pb = b['out'] / b['sites'] if b['sites'] else 0
        sign = '+' if pw > pb else '−' if pw < pb else '='
        plus += sign == '+'
        minus += sign == '−'
        ties += sign == '='
        P(f'   {k[0][:44] + " / " + k[1]:<58}{w["n"]:>8}{pw * 100:>7.1f}{b["n"]:>8}{pb * 100:>7.1f}  {sign}')
    P(f'   выходной лучше в {plus} пулах, хуже в {minus}, ничья {ties}; '
      f'биномиальный p = {fmt_p(binom_two_sided(plus, plus + minus))}')
    # устойчивость: будняя сторона у наборов 12.09 — это 1–3 домена понедельника 14.09
    P('')
    P('3г. Устойчивость контраста (1):')
    big = defaultdict(lambda: [0, 0])
    for d in main_a:
        big[key_main(d)][1 if is_wend(d) else 0] += 1
    ok_big = {k for k, v in big.items() if min(v) >= 5}
    main_a5 = [d for d in main_a if key_main(d) in ok_big]
    P(f'   (i) только страты набор+зона с >= 5 доменов с каждой стороны: {len(ok_big)} страт, '
      f'{len(main_a5)} доменов ({", ".join(k[0][:34] + "/" + k[1] for k in sorted(ok_big))})')
    vals_a5 = attach_expectations(main_a5, key_main)
    print_group_table('   страты >= 5 с каждой стороны:',
                      [('выходной (сб+вс)', [d for d in main_a5 if is_wend(d)]),
                       ('будни', [d for d in main_a5 if not is_wend(d)])], vals_a5)
    r_a5 = report_contrast('   выходной, выход, страты >= 5 с каждой стороны', main_a5, vals_a5,
                           key_main, [6, 7], M_EXIT)
    key_root = lambda d: d['корень']
    main_ar, n_main_ar = strata_with(doms_multi, key_root, is_wend, 2)
    P(f'   (ii) страта = набор без зоны: {n_main_ar} страт, {len(main_ar)} доменов')
    vals_ar = attach_expectations(main_ar, key_root)
    print_group_table('   набор без зоны:',
                      [('выходной (сб+вс)', [d for d in main_ar if is_wend(d)]),
                       ('будни', [d for d in main_ar if not is_wend(d)])], vals_ar)
    r_ar = report_contrast('   выходной, выход, набор без зоны', main_ar, vals_ar, key_root,
                           [6, 7], M_EXIT)
    mon = [d for d in doms if d['день'] == dt.date(2026, 9, 14)]
    sm = sums(mon, vals_none)
    P(f'   Оговорка: будняя сторона у наборов content-2026-09-12-7str-oform-1/-2/-3 — это '
      f'понедельник 14.09, сам по себе слабый день: {sm["n"]} доменов, выход '
      f'{per(sm["out"], sm["sites"])} %, {sm["reg"]} рег ({per(sm["reg"], sm["clk"], 10000)}/10 тыс.).')

    # ---- 4. контраст 2: воскресенье по рег/клик
    P('')
    P('-' * 100)
    P('4. КОНТРАСТ (2): воскресенье против остальных дней по деньгам с поискового клика')
    P('-' * 100)
    vals_sec_c = attach_expectations(sec_c, key_sec)
    print_weekday_oe('4а. Вторичная страта (семейство + страниц + оформление + зона, сентябрь), '
                     'страты с >= 2 днями недели; O/E по всем трём метрикам:', sec_c, vals_sec_c)
    obs_sec = observed_acc(sec_c, vals_sec_c)
    o_sun, e_sun = obs_sec[7][2], obs_sec[7][3]
    p1, p2 = poisson_tests(int(o_sun), e_sun)
    P(f'   воскресенье, рег/клик: O = {o_sun:.0f}, E = {e_sun:.1f}, O/E = {ratio(o_sun, e_sun)}; '
      f'пуассон: P(X <= O) = {fmt_p(p1)}, двуст. = {fmt_p(p2)}, '
      f'с поправкой ×7: {fmt_p(min(1, p2 * 7))}')
    r_sec_sun = report_contrast('   воскресенье, рег/клик, вторичная страта', sec_c, vals_sec_c,
                                key_sec, [7], M_REGCLK,
                                extra=[('χ² по 7 дням, рег/клик', lambda a: stat_chi2(a, M_REGCLK)),
                                       ('min O/E по дням (E >= 3), рег/клик',
                                        lambda a: stat_min_day(a, M_REGCLK))])
    P(f'   перестановочный p воскресенья с поправкой Бонферрони ×7: '
      f'{fmt_p(min(1, r_sec_sun["domain"]["p2"] * 7))} (по доменам), '
      f'{fmt_p(min(1, r_sec_sun["date"]["p2"] * 7))} (по датам)')
    P('   те же страты, воскресенье по выходу и рег/сайт:')
    report_contrast('   воскресенье, выход, вторичная страта', sec_c, vals_sec_c, key_sec, [7],
                    M_EXIT, modes=('domain',))
    report_contrast('   воскресенье, рег/сайт, вторичная страта', sec_c, vals_sec_c, key_sec, [7],
                    M_REGSITE, modes=('domain',))
    P('')
    P('4б. Два воскресенья отдельно (вторичная страта, ожидание по той же страте):')
    for day in (dt.date(2026, 9, 6), dt.date(2026, 9, 13)):
        ds = [d for d in sec_c if d['день'] == day]
        s = sums(ds, vals_sec_c)
        p1d, p2d = poisson_tests(s['reg'], s['e_regclk'])
        P(f'   {day}: {s["n"]} доменов, {s["sites"]} сайтов, {s["clk"]} кликов, {s["reg"]} рег '
          f'({per(s["reg"], s["clk"], 10000)}/10 тыс.); выход O/E {fr(oe_from_sums(s, M_EXIT))}; '
          f'рег/клик O = {s["reg"]}, E = {s["e_regclk"]:.1f}, O/E {fr(oe_from_sums(s, M_REGCLK))}, '
          f'пуассон P(X <= O) = {fmt_p(p1d)}; рег/сайт O/E {fr(oe_from_sums(s, M_REGSITE))}')
    P('')
    P('4в. Главная страта (набор контента + зона): воскресенье есть только у '
      'content-2026-09-12-7str-oform-3 (вс 13.09 против пн 14.09):')
    vals_main_b = attach_expectations(main_b, key_main)
    print_group_table(f'   страт: {n_main_b}, доменов: {len(main_b)} '
                      f'({", ".join(k[0][:34] + "/" + k[1] for k in sorted({key_main(d) for d in main_b}))})',
                      [('воскресенье', [d for d in main_b if is_sun(d)]),
                       ('не воскресенье', [d for d in main_b if not is_sun(d)])], vals_main_b)
    obs_mb = observed_acc(main_b, vals_main_b)
    p1m, p2m = poisson_tests(int(obs_mb[7][2]), obs_mb[7][3])
    P(f'   пуассон: P(X <= O) = {fmt_p(p1m)}, двуст. = {fmt_p(p2m)}; '
      f'ожидание воскресенья E = {obs_mb[7][3]:.1f} регистрации — объём не позволяет ничего решить.')
    report_contrast('   воскресенье, рег/клик, главная страта', main_b, vals_main_b, key_main, [7],
                    M_REGCLK)
    report_contrast('   воскресенье, выход, главная страта', main_b, vals_main_b, key_main, [7],
                    M_EXIT, modes=('domain',))
    P('')
    P('4г. Контекст: три варианта одного дня генерации content-2026-09-12-7str-oform-1/-2/-3 '
      '(разные наборы, не страта):')
    groups = []
    for v in ('1', '2', '3'):
        rname = f'content-2026-09-12-7str-oform-{v}'
        for w in (6, 7, 1):
            ds = [d for d in doms if d['корень'] == rname and d['wd'] == w]
            if ds:
                groups.append((f'oform-{v} {WD[w]}', ds))
    print_group_table('   сырые ставки по вариантам и дням:', groups, vals_none, with_oe=False)

    # ---- 5. контраст 3: день 2
    P('')
    P('-' * 100)
    P('5. КОНТРАСТ (3): день недели «последнего дня» (день 2 = день запуска + 1)')
    P('-' * 100)
    P('   день 2 в сб = запуск в пт; в вс = запуск в сб; в пн = запуск в вс; будни вт–пт = '
      'запуск пн–чт. Это те же группы дня недели запуска с другой подписью.')
    vals_main_c = attach_expectations(main_c, key_main)
    day2_groups = [('день 2 в сб (зап. пт)', [d for d in main_c if d['wd'] == 5]),
                   ('день 2 в вс (зап. сб)', [d for d in main_c if d['wd'] == 6]),
                   ('день 2 в пн (зап. вс)', [d for d in main_c if d['wd'] == 7]),
                   ('день 2 вт–пт (зап. пн–чт)', [d for d in main_c if d['wd'] in (1, 2, 3, 4)])]
    print_group_table('5а. Главная страта (набор + зона, >= 2 дней недели в страте):', day2_groups,
                      vals_main_c)
    r_d2_exit = report_contrast('   день 2 в сб+вс (зап. пт+сб), выход, главная страта', main_c,
                                vals_main_c, key_main, [5, 6], M_EXIT)
    r_d2_reg = report_contrast('   день 2 в сб+вс (зап. пт+сб), рег/клик, главная страта', main_c,
                               vals_main_c, key_main, [5, 6], M_REGCLK, modes=('domain',))
    r_d2_rs = report_contrast('   день 2 в сб+вс (зап. пт+сб), рег/сайт, главная страта', main_c,
                              vals_main_c, key_main, [5, 6], M_REGSITE, modes=('domain',))
    lo, hi = r_d2_exit['domain']['lo'], r_d2_exit['domain']['hi']
    lo2, hi2 = r_d2_exit['date']['lo'], r_d2_exit['date']['hi']
    obs_d2 = r_d2_exit['obs']
    # сколько выходов остатка могло пропасть незаметно: нижний край «набл. минус ширина нуля»
    hidden_dom = max(0.0, 1 - (obs_d2 - (1 - lo))) / 0.17 * 100
    hidden_date = max(0.0, 1 - (obs_d2 - (1 - lo2))) / 0.17 * 100
    P(f'   чувствительность: остаток 56 брендов даёт ~17 % выходов домена; если выходной '
      f'режет выход остатка вдвое, O/E домена = 0,91, если в ноль — 0,83. Нулевой 95 % '
      f'интервал O/E: {fr(lo)}–{fr(hi)} по доменам, {fr(lo2)}–{fr(hi2)} по датам. '
      f'Наблюдённые {fr(obs_d2)} допускают незамеченную потерю не более ~{hidden_dom:.0f} % '
      f'выходов остатка по доменам и ~{hidden_date:.0f} % по датам: полная потеря остатка '
      f'исключена, потеря половины — на границе различимости по датам.')
    vals_sec_c2 = vals_sec_c
    day2_groups_sec = [('день 2 в сб (зап. пт)', [d for d in sec_c if d['wd'] == 5]),
                       ('день 2 в вс (зап. сб)', [d for d in sec_c if d['wd'] == 6]),
                       ('день 2 в пн (зап. вс)', [d for d in sec_c if d['wd'] == 7]),
                       ('день 2 вт–пт (зап. пн–чт)', [d for d in sec_c if d['wd'] in (1, 2, 3, 4)])]
    print_group_table('5б. Вторичная страта (сентябрь):', day2_groups_sec, vals_sec_c2)
    report_contrast('   день 2 в сб+вс (зап. пт+сб), выход, вторичная страта', sec_c, vals_sec_c2,
                    key_sec, [5, 6], M_EXIT, modes=('domain',))
    report_contrast('   день 2 в сб+вс (зап. пт+сб), рег/клик, вторичная страта', sec_c,
                    vals_sec_c2, key_sec, [5, 6], M_REGCLK, modes=('domain',))

    # ---- 6. семь уровней, главная страта
    P('')
    P('-' * 100)
    P('6. СЕМЬ ДНЕЙ НЕДЕЛИ, ГЛАВНАЯ СТРАТА (набор + зона, >= 2 дней недели в страте)')
    P('-' * 100)
    print_weekday_oe('6а. O/E по дням недели:', main_c, vals_main_c)
    obs_mc = observed_acc(main_c, vals_main_c)
    chi_p_main = {}
    for m in (M_EXIT, M_REGCLK, M_REGSITE):
        perms = perm_run(main_c, vals_main_c, key_main, N_PERM, 'domain')
        ov = stat_chi2(obs_mc, m)
        pv = [stat_chi2(a, m) for a in perms]
        perms_d = perm_run(main_c, vals_main_c, key_main, N_PERM, 'date')
        pvd = [stat_chi2(a, m) for a in perms_d]
        chi_p_main[m] = (p_ge(pv, ov), p_ge(pvd, ov))
        P(f'   χ² по 7 дням, {METRIC_NAME[m]}: набл. {ov:.1f}; p по перестановкам: '
          f'{fmt_p(p_ge(pv, ov))} (по доменам), {fmt_p(p_ge(pvd, ov))} (по датам)')
        if m == M_REGCLK:
            omin = stat_min_day(obs_mc, m)
            pmin = [stat_min_day(a, m) for a in perms]
            P(f'   «худший день» по рег/клик (E >= 3): набл. min O/E {fr(omin)}, '
              f'P(min* <= набл.) = {fmt_p(p_le(pmin, omin))} (по доменам)')
    P('')
    P('6б. Вторичная страта, χ² по 7 дням (сентябрь):')
    for m in (M_EXIT, M_REGCLK, M_REGSITE):
        perms = perm_run(sec_c, vals_sec_c, key_sec, N_PERM, 'domain')
        ov = stat_chi2(obs_sec, m)
        pv = [stat_chi2(a, m) for a in perms]
        P(f'   χ² по 7 дням, {METRIC_NAME[m]}: набл. {ov:.1f}; p = {fmt_p(p_ge(pv, ov))} (по доменам)')

    # ---- 7. внешняя проверка 20.09
    P('')
    P('-' * 100)
    P('7. ВНЕШНЯЯ ПРОВЕРКА: воскресенье 20.09 (окно не закрыто, данные на выгрузку 21.09)')
    P('-' * 100)
    for day in (CHECK_SATURDAY, CHECK_SUNDAY):
        ds = [d for d in all_rows if d['день'] == day]
        n = len(ds)
        sites = sum(d['сайтов всего'] for d in ds)
        clk = sum(d['клики'] for d in ds)
        reg = sum(d['рег'] for d in ds)
        fd = sum(d['фд'] for d in ds)
        closed = sum(1 for d in ds if d['окно'] == 'да')
        P(f'   {day} ({WD[day.isoweekday()]}): {n} доменов, {sites} сайтов, окно закрыто у {closed}; '
          f'пока {clk} кликов из поиска в окне, {reg} регистраций, {fd} ФД -> '
          f'{per(reg, clk, 10000)} рег на 10 тыс. кликов, {per(reg, sites)} на 100 сайтов')
    ds = [d for d in all_rows if d['день'] == CHECK_SUNDAY]
    reg20 = sum(d['рег'] for d in ds)
    clk20 = sum(d['клики'] for d in ds)
    rate20 = reg20 / clk20 * 10000 if clk20 else float('nan')
    P(f'   Прогноз гипотезы (2) для 20.09: <= 5 регистраций и <= 1 рег на 10 тыс. кликов; '
      f'опровержение: >= 10 регистраций. Сейчас: {reg20} регистраций, {fr(rate20, 1)} на 10 тыс. — '
      f'окно закроется 24.09, число только вырастет.')
    verdict20 = ('уже вне прогноза гипотезы (> 5 регистраций)' if reg20 > 5 else
                 'пока в прогнозе гипотезы, ждать 24.09')
    P(f'   Итог по 20.09 на сегодня: {verdict20}.')

    # ---- 8. вывод
    P('')
    P('=' * 100)
    P('ВЫВОД')
    P('=' * 100)
    oe_sec_a = r_sec_a['obs']
    oe_main_a = r_main_a['obs']
    oe_sun_sec = r_sec_sun['obs']
    s_w = sums([d for d in main_a if is_wend(d)], vals_main_a)
    s_b = sums([d for d in main_a if not is_wend(d)], vals_main_a)
    s_sun = sums([d for d in sec_c if is_sun(d)], vals_sec_c)
    s_sat = sums([d for d in doms if d['wd'] == 6], vals_none)
    s_sun_raw = sums([d for d in doms if d['wd'] == 7], vals_none)
    s_wk = sums([d for d in doms if not is_wend(d)], vals_none)
    crit1 = 0.9 <= oe_main_a <= 1.1 and r_main_a['domain']['p2'] > 0.2
    crit2 = oe_sun_sec <= 0.5 and p2 < 0.05 and reg20 <= 5
    refute2 = oe_sun_sec >= 0.8 or reg20 >= 10
    P('Простыми словами.')
    P(f'(1) Выходные и выход в поиск. Сырое отставание есть: суббота {s_sat["n"]} доменов, выход '
      f'{per(s_sat["out"], s_sat["sites"])} %, воскресенье {s_sun_raw["n"]} доменов, '
      f'{per(s_sun_raw["out"], s_sun_raw["sites"])} %, будни {s_wk["n"]} доменов, '
      f'{per(s_wk["out"], s_wk["sites"])} %. Грубая страта (семейство + страниц + оформление + '
      f'зона) отставание не убирает: O/E выходных {fr(oe_sec_a)} (p {fmt_p(r_sec_a["domain"]["p2"])} '
      f'по доменам, {fmt_p(r_sec_a["date"]["p2"])} по датам). Но внутри одного набора контента '
      f'и зоны ({n_main_a} страт, {len(main_a)} доменов: {s_w["n"]} выходных, {s_b["n"]} будних) '
      f'выходные не хуже: O/E {fr(oe_main_a)}, p {fmt_p(r_main_a["domain"]["p2"])} по доменам '
      f'и {fmt_p(r_main_a["date"]["p2"])} по датам, знаковый счёт {plus}:{minus}. '
      f'То есть в выходные просто ставили слабые наборы. Критерий (O/E 0,9–1,1, p > 0,2): '
      f'{"выполнен" if crit1 else "не выполнен"}. Оговорка: в двух из шести страт будняя сторона '
      f'— 1–3 домена понедельника 14.09; на стратах с >= 5 доменов с каждой стороны O/E '
      f'{fr(r_a5["obs"])} (p {fmt_p(r_a5["domain"]["p2"])}), по набору без зоны {fr(r_ar["obs"])} '
      f'(p {fmt_p(r_ar["domain"]["p2"])}). Точность: нулевой интервал O/E '
      f'{fr(r_main_a["domain"]["lo"])}–{fr(r_main_a["domain"]["hi"])} по доменам, '
      f'{fr(r_main_a["date"]["lo"])}–{fr(r_main_a["date"]["hi"])} по датам, то есть заметен был бы '
      f'только провал выходных сильнее ~{(1 - r_main_a["date"]["lo"]) * 100:.0f} %; наблюдённые '
      f'{fr(oe_main_a)} его не показывают.')
    P(f'(2) Воскресенье и деньги с клика. Две воскресные даты (06.09 и 13.09) дали {s_sun["reg"]} '
      f'регистраций при ожидании {s_sun["e_regclk"]:.1f} по страте (O/E {fr(oe_sun_sec)}, '
      f'{per(s_sun["reg"], s_sun["clk"], 10000)} на 10 тыс. кликов). Но это в пределах шума: '
      f'пуассон p = {fmt_p(p2)} (двусторонний), перестановка p = {fmt_p(r_sec_sun["domain"]["p2"])}, '
      f'а с поправкой на то, что худший из семи дней ищется перебором, p = '
      f'{fmt_p(min(1, p2 * 7))}; «худший день» по перестановкам p = {fmt_p(p_le([stat_min_day(a, M_REGCLK) for a in r_sec_sun["domain"]["perms"]], stat_min_day(obs_sec, M_REGCLK)))}. '
      f'Внутри набора (oform-3, вс против пн) объём слишком мал (E = {obs_mb[7][3]:.1f}). '
      f'Внешняя проверка: воскресенье 20.09 уже дало {reg20} регистраций и {fr(rate20, 1)} на '
      f'10 тыс. кликов при окне, которое закроется только 24.09, — прогноз гипотезы '
      f'(<= 5 и <= 1 на 10 тыс.) уже не сбылся, до порога опровержения (>= 10) не хватает '
      f'{max(0, 10 - reg20)}. Критерий гипотезы: {"выполнен" if crit2 else "не выполнен"}; '
      f'формальное опровержение: {"да" if refute2 else "пока нет, но 20.09 идёт к нему"}.')
    P(f'(3) День 2 в выходной. День 2 — всегда следующий день после запуска, так что «день 2 в '
      f'сб/вс» — это пятничные и субботние запуски, отдельного эффекта дня 2 свод не выделяет. '
      f'Внутри набора + зоны эти запуски в норме: выход O/E {fr(r_d2_exit["obs"])} '
      f'(p {fmt_p(r_d2_exit["domain"]["p2"])} / {fmt_p(r_d2_exit["date"]["p2"])}), рег/клик '
      f'{fr(r_d2_reg["obs"])} (p {fmt_p(r_d2_reg["domain"]["p2"])}), рег/сайт {fr(r_d2_rs["obs"])} '
      f'(p {fmt_p(r_d2_rs["domain"]["p2"])}). Незаметно могло пропасть не более ~{hidden_dom:.0f} % '
      f'выходов остатка по доменам и ~{hidden_date:.0f} % по датам: полная потеря исключена, '
      f'потеря половины (−9 % по домену) — на границе различимости.')
    P(f'Общее: день недели почти сцеплен с датой (в сентябре четыре выходных даты), поэтому '
      f'страта по набору отделяет день недели от состава наборов, но не от самого дня; '
      f'по дням внутри наборов различия по выходу есть (χ² по 7 дням p = '
      f'{fmt_p(chi_p_main[M_EXIT][0])} по доменам, {fmt_p(chi_p_main[M_EXIT][1])} по датам), '
      f'по деньгам нет (p = {fmt_p(chi_p_main[M_REGCLK][0])}), и они не ложатся на границу '
      f'«выходной/будни».')
    P('Что с этим делать: расписание запусков по дню недели не рычаг — ни выходные, ни день 2 '
      'на выходных, ни воскресенье как «дешёвый» день на своде не подтверждаются. Проверяемое '
      'на уже запущенных данных: 24.09, когда закроется окно у 70 доменов 20.09, пересчитать '
      'регистрации в окне — при >= 10 гипотезу о воскресенье закрыть окончательно; при <= 5 '
      'вернуться к ней с третьим воскресеньем в руках.')
    P(f'Время счёта: {time.time() - t0:.0f} с.')

    with open(OUT_PATH, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_out) + '\n')
    print(f'\nСохранено: {OUT_PATH}')


if __name__ == '__main__':
    main()

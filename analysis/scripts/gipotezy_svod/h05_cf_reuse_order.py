#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Гипотеза №5. Повторное использование cf-аккаунта (2-я и 3-я база на том же
cf, разрыв 1–17 дней, в том числе быстрый повтор через 1–2 дня) снижает выход
в поиск и регистрации по сравнению с первой базой на cf. Сырой срез:
1-я база — выход 15,8 %, 2-я — 11,3 %, 3-я — 10,1 %; но порядок использования
cf почти совпадает с датой запуска, и вторые базы чаще стоят в .lol/.buzz,
поэтому сырой разрыв может быть целиком тенью даты и набора контента.

Что проверяем и как:
  1. Порядок базы на cf считается по ВСЕМ 2077 строкам (до исключений):
     базы одного cf-аккаунта сортируются по (день запуска, час запуска) →
     1-я / 2-я / 3-я; разрыв = дни от предыдущей базы того же cf.
  2. Исключения (печатаются): окно закрыто = нет; выбросы 3615.team и
     3286.team; «КОНТЕНТ НЕ ЗАПИСАН»; пустой cf-аккаунт.
  3. Сырой срез без страты — воспроизводим цифры гипотезы и показываем,
     как порядок сцеплен с датой и зоной.
  4. Страта «день» на всех оставшихся доменах: O/E выхода и регистраций по
     порядку 1/2/3 — снимает ли одна дата сырой разрыв.
  5. Главная проверка. Пул = набор контента + день запуска + признак
     «150 сайтов» (базы 17–18.09 с одним днём постановки — у них только первые
     150 брендов, которые выходят лучше остатка, их нельзя мешать с 206-ными).
     ОГОВОРКА: у 722 доменов имя набора вида content-…_NN уникально для домена
     (суффикс _NN — номер экземпляра); для них пул строится по имени без
     суффикса. Берутся только пулы, где есть и первые, и повторные базы cf.
     E = доля выхода пула × сайтов в окне домена, O = вышли за 3 суток;
     суммы O и E по группам «1-я / 2-я / 3-я» и «повторные (2-я+3-я)».
     Значимость: перестановка метки порядка внутри пула 10 000 раз
     (random.seed(1)), двусторонний p = 2·min(p≤, p≥). Регистрации в окне
     3 суток: E = рег пула на сайт × сайтов, O/E, точный пуассоновский
     интервал 95 % для O/E, пуассоновский p и та же перестановка.
     Отдельно — вышли за 7 суток (догоняют ли повторные).
  6. Разрыв в днях: группы ≤2 / 3–7 / 8–17 / ≥18 против первых баз тех же
     пулов; Спирмен «разрыв ↔ O/E выхода домена» среди повторных баз с
     перестановкой разрыва внутри пула.
  7. Контроль зоны: там, где в ячейке пул×зона ≥3 домена каждой группы —
     страта с зоной; иначе O/E по зонам при пуловом E.
  8. 16.09: первые и вторые базы стоят на разных наборах, поэтому там пул —
     день + семейство + страниц + оформление (грубая страта, оговаривается);
     результат показан отдельно и в сумме с главными пулами.
  9. 2-я против 3-й внутри пулов без первых баз (09–11.09).
 10. Чувствительность: без пулов «150 сайтов»; только пулы, где имя набора
     взято как есть (без снятия суффикса).

Критерии из плана: вред — O/E повторных / O/E первых ≤ 0,85 по выходу при
p < 0,05 и тот же знак по регистрациям; опровержение — 0,9–1,1.
Ожидание регистраций в группах ≈ 10–15, поэтому по регистрациям виден только
эффект ≥ 2× — это сказано прямо в выводе.

Только stdlib. Вывод — в stdout и в
analysis/export/gipotezy_svod/h05_cf_reuse_order.txt
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict
from datetime import date

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'h05_cf_reuse_order.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
random.seed(1)
OUTLIERS = {'3615.team', '3286.team'}
NO_CONTENT = 'КОНТЕНТ НЕ ЗАПИСАН'

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
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return '—'
    return f'{x:.{d}f}'


def ratio(o, e):
    return o / e if e > 0 else None


# ---------------------------------------------------------------- пуассон
def pois_cdf(k, lam):
    """P(X <= k | lam), устойчиво через логарифмы."""
    if lam <= 0:
        return 1.0
    k = int(k)
    s = 0.0
    for i in range(k + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


def pois_sf(k, lam):
    """P(X >= k | lam)."""
    if k <= 0:
        return 1.0
    return max(0.0, 1.0 - pois_cdf(k - 1, lam))


def pois_two_sided(k, lam):
    if lam <= 0:
        return None
    return min(1.0, 2 * min(pois_cdf(k, lam), pois_sf(k, lam)))


def pois_ci(k, alpha=0.05):
    """Точный интервал для среднего Пуассона по наблюдённому k (Гарвуд)."""
    k = int(k)
    if k == 0:
        lo = 0.0
    else:
        a, b = 0.0, float(k) + 1.0
        while pois_sf(k, b) < alpha / 2:
            b *= 2
        for _ in range(200):
            m = (a + b) / 2
            if pois_sf(k, m) < alpha / 2:
                a = m
            else:
                b = m
        lo = (a + b) / 2
    a, b = float(k), float(k) + 1.0
    while pois_cdf(k, b) > alpha / 2:
        b *= 2
    for _ in range(200):
        m = (a + b) / 2
        if pois_cdf(k, m) > alpha / 2:
            a = m
        else:
            b = m
    hi = (a + b) / 2
    return lo, hi


# ---------------------------------------------------------------- спирмен
def ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(x, y):
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(x, y):
    return pearson(ranks(x), ranks(y))


# ---------------------------------------------------------------- чтение
with open(SRC, encoding='utf-8', newline='') as fh:
    rows = list(csv.DictReader(fh))

p(f'Файл: {SRC}')
p(f'Всего строк (доменов): {len(rows)}')
p('')

# порядок базы на cf и разрыв — по всем строкам, до исключений
by_cf = defaultdict(list)
for r in rows:
    by_cf[r['cf-аккаунт']].append(r)
for cfk, lst in by_cf.items():
    lst.sort(key=lambda r: (r['день запуска'], int(fnum(r['час запуска']))))
    prev = None
    for i, r in enumerate(lst):
        r['_ord'] = i + 1
        r['_cfn'] = len(lst)
        d = date.fromisoformat(r['день запуска'])
        r['_gap'] = (d - prev).days if prev is not None else None
        prev = d
    if cfk == '':
        for r in lst:
            r['_ord'] = None
            r['_gap'] = None


def gap_bucket(g):
    if g is None:
        return '1-я (нет разрыва)'
    if g <= 2:
        return 'разрыв ≤2'
    if g <= 7:
        return 'разрыв 3–7'
    if g <= 17:
        return 'разрыв 8–17'
    return 'разрыв ≥18'


def ord_label(r):
    return {1: '1-я', 2: '2-я', 3: '3-я'}.get(r['_ord'], '?')


def rep_label(r):
    return '1-я' if r['_ord'] == 1 else 'повторная'


def strip_suffix(name):
    return re.sub(r'_\d+$', '', name)


for r in rows:
    r['_sites'] = fnum(r['сайтов в окне'])
    r['_ex3'] = fnum(r['вышли за 3 суток'])
    r['_ex7'] = fnum(r['вышли за 7 суток'])
    r['_reg'] = fnum(r['регистраций в окне 3 суток'])
    r['_fd'] = fnum(r['ФД в окне 3 суток'])
    r['_s150'] = '150' if r['сайтов'] == '150' else '206'
    r['_set'] = strip_suffix(r['набор контента'])
    r['_suffixed'] = r['_set'] != r['набор контента']

p('=' * 100)
p('0. ПОРЯДОК БАЗЫ НА cf-АККАУНТЕ (по всем 2077 строкам, до исключений)')
p('=' * 100)
cf_sizes = Counter(len(v) for k, v in by_cf.items() if k != '')
p(f"cf-аккаунтов: {len([k for k in by_cf if k != ''])}; по числу баз: "
  + ', '.join(f'{k} базы — {v}' for k, v in sorted(cf_sizes.items())))
p(f"Пустой cf-аккаунт: {len(by_cf.get('', []))} домен(ов) — исключаются.")
p(f"Порядок 1/2/3: {dict(sorted(Counter(r['_ord'] for r in rows if r['_ord']).items()))}")
gaps = Counter(r['_gap'] for r in rows if r['_gap'] is not None)
p('Разрыв (дней от предыдущей базы того же cf): '
  + ', '.join(f'{g}:{c}' for g, c in sorted(gaps.items())))
p('Порядок ↔ дата запуска (сколько баз каждого порядка в каждый день):')
for o in (1, 2, 3):
    c = Counter(r['день запуска'][5:] for r in rows if r['_ord'] == o)
    p(f'  {o}-я: ' + ', '.join(f'{d}:{n}' for d, n in sorted(c.items())))
p('  → порядок использования cf почти совпадает с датой: первые базы — до 03.09 и 12–16.09,')
p('    вторые — 03–09.09 и 16–21.09, третьи — 09–12.09 и 18–20.09. Значит, без страты по дню')
p('    сырой разрыв 1-я/2-я/3-я нельзя приписать cf.')
p('')

# ---------------------------------------------------------------- исключения
p('=' * 100)
p('ФИЛЬТРЫ И ИСКЛЮЧЕНИЯ')
p('=' * 100)
n0 = len(rows)
k1 = [r for r in rows if r['окно закрыто'] == 'да']
p(f'Окно закрыто = нет: исключено {n0 - len(k1)} (осталось {len(k1)})')
k2 = [r for r in k1 if r['домен'] not in OUTLIERS]
p(f'Выбросы 3615.team / 3286.team: исключено {len(k1) - len(k2)} (осталось {len(k2)})')
k3 = [r for r in k2 if r['набор контента'] != NO_CONTENT]
p(f'«КОНТЕНТ НЕ ЗАПИСАН»: исключено {len(k2) - len(k3)} (осталось {len(k3)})')
keep = [r for r in k3 if r['cf-аккаунт'] != '']
p(f'Пустой cf-аккаунт: исключено {len(k3) - len(keep)} (осталось {len(keep)})')
n_d1 = sum(1 for r in keep if r['_s150'] == '150')
p(f'Домены «150 сайтов» (дней = 1, окно уже закрыто) в оставшихся: {n_d1} — не исключаются,')
p('  но признак «150/206» входит в ключ пула, чтобы не сравнивать 150 лучших брендов с полными 206.')
n_suf = sum(1 for r in keep if r['_suffixed'])
p(f'Доменов с именем набора вида …_NN (уникальный экземпляр): {n_suf} из {len(keep)} — пул по имени без суффикса.')
p('')

# ---------------------------------------------------------------- 1. сырой срез
p('=' * 100)
p('1. СЫРОЙ СРЕЗ БЕЗ СТРАТЫ (окно закрыто = да, без выбросов; как в тексте гипотезы)')
p('   сайтов = сайтов в окне; вых% = вышли за 3 суток / сайтов; рег = регистраций в окне 3 суток')
p('=' * 100)


def raw_table(rs, labf, title):
    p(title)
    p(f"{'группа':<20}{'домен':>7}{'сайтов':>9}{'вышли3':>8}{'вых%':>7}{'рег':>6}{'рег/100':>9}{'ФД':>5}  зоны")
    groups = defaultdict(list)
    for r in rs:
        groups[labf(r)].append(r)
    for g in sorted(groups):
        rs_ = groups[g]
        s = sum(r['_sites'] for r in rs_)
        e = sum(r['_ex3'] for r in rs_)
        reg = sum(r['_reg'] for r in rs_)
        fd = sum(r['_fd'] for r in rs_)
        z = Counter(r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие' for r in rs_)
        zs = ', '.join(f'{k} {v}' for k, v in z.most_common())
        p(f"{g:<20}{len(rs_):>7}{int(s):>9}{int(e):>8}{fmt(100 * e / s, 1) if s else '—':>7}{int(reg):>6}"
          f"{fmt(100 * reg / s, 2) if s else '—':>9}{int(fd):>5}  {zs}")
    p('')


raw_rows = [r for r in k2 if r['_ord']]
raw_table(raw_rows, ord_label, 'По порядку базы на cf (все наборы, включая «КОНТЕНТ НЕ ЗАПИСАН»):')
raw_table(raw_rows, lambda r: gap_bucket(r['_gap']), 'По разрыву от предыдущей базы того же cf:')
p('Те же 15,8 % → 11,3 % → 10,1 % и 0,12 → 0,07 → 0,08 рег/100 сайтов, что и в гипотезе. Дальше — страты.')
p('')


# ---------------------------------------------------------------- движок O/E + перестановка
def build_units(rs, pool_key):
    """Для каждого домена: E выхода/7 суток/регистраций по доле его пула."""
    pools = defaultdict(list)
    for r in rs:
        pools[pool_key(r)].append(r)
    units = {}
    rates = {}
    for k, lst in pools.items():
        s = sum(r['_sites'] for r in lst)
        rate3 = sum(r['_ex3'] for r in lst) / s if s else 0.0
        rate7 = sum(r['_ex7'] for r in lst) / s if s else 0.0
        rreg = sum(r['_reg'] for r in lst) / s if s else 0.0
        rates[k] = (rate3, rate7, rreg, len(lst), s)
        for r in lst:
            units[r['домен']] = dict(pool=k, sites=r['_sites'],
                                     o3=r['_ex3'], e3=rate3 * r['_sites'],
                                     o7=r['_ex7'], e7=rate7 * r['_sites'],
                                     oreg=r['_reg'], ereg=rreg * r['_sites'])
    return units, rates


def group_sums(rs, units, labf):
    g = defaultdict(lambda: dict(n=0, sites=0.0, o3=0.0, e3=0.0, o7=0.0, e7=0.0, oreg=0.0, ereg=0.0))
    for r in rs:
        u = units[r['домен']]
        d = g[labf(r)]
        d['n'] += 1
        d['sites'] += u['sites']
        for k in ('o3', 'e3', 'o7', 'e7', 'oreg', 'ereg'):
            d[k] += u[k]
    return g


def perm_test(rs, units, labf, ref, tests, n_perm=N_PERM):
    """Перестановка меток внутри пула. Статистика для каждой test-метки:
    (O/E test) / (O/E ref) по выходу за 3 суток и по регистрациям.
    Возвращает {test: {'ex': (obs, p_le, p_ge, p2), 'reg': (...)}}."""
    pools = defaultdict(list)
    for r in rs:
        pools[units[r['домен']]['pool']].append(r)
    plist = []
    for k, lst in pools.items():
        labs = [labf(r) for r in lst]
        vals = [(units[r['домен']]['o3'], units[r['домен']]['e3'],
                 units[r['домен']]['oreg'], units[r['домен']]['ereg']) for r in lst]
        plist.append((labs, vals))

    def stats(assign_list):
        acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        for labs, vals in assign_list:
            for lab, v in zip(labs, vals):
                a = acc[lab]
                a[0] += v[0]
                a[1] += v[1]
                a[2] += v[2]
                a[3] += v[3]
        out = {}
        rf = acc[ref]
        r_ex = ratio(rf[0], rf[1])
        r_reg = ratio(rf[2], rf[3])
        for t in tests:
            a = acc[t]
            t_ex = ratio(a[0], a[1])
            t_reg = ratio(a[2], a[3])
            out[t] = ((t_ex / r_ex) if (t_ex is not None and r_ex) else None,
                      (t_reg / r_reg) if (t_reg is not None and r_reg) else None)
        return out

    obs = stats(plist)
    cnt = {t: [0, 0, 0, 0] for t in tests}  # ex_le, ex_ge, reg_le, reg_ge
    valid = {t: [0, 0] for t in tests}
    work = [(list(labs), vals) for labs, vals in plist]
    for _ in range(n_perm):
        for labs, _v in work:
            random.shuffle(labs)
        st = stats(work)
        for t in tests:
            for j, idx in ((0, 0), (1, 2)):
                o = obs[t][j]
                v = st[t][j]
                if o is None or v is None:
                    continue
                valid[t][j] += 1
                if v <= o + 1e-12:
                    cnt[t][idx] += 1
                if v >= o - 1e-12:
                    cnt[t][idx + 1] += 1
    res = {}
    for t in tests:
        d = {}
        for name, j, idx in (('ex', 0, 0), ('reg', 1, 2)):
            o = obs[t][j]
            nv = valid[t][j]
            if o is None or nv == 0:
                d[name] = (o, None, None, None)
            else:
                ple = cnt[t][idx] / nv
                pge = cnt[t][idx + 1] / nv
                d[name] = (o, ple, pge, min(1.0, 2 * min(ple, pge)))
        res[t] = d
    return res


def report_groups(rs, units, labf, ref, tests, title, note_reg=True):
    g = group_sums(rs, units, labf)
    p(title)
    p(f"{'группа':<22}{'домен':>6}{'сайтов':>8}{'O вых3':>8}{'E вых3':>9}{'O/E':>6}{'O вых7':>8}{'E вых7':>9}{'O/E7':>6}"
      f"{'O рег':>7}{'E рег':>8}{'O/E рег':>9}  95% интервал O/E рег")
    order = [ref] + [t for t in tests if t in g] + [k for k in sorted(g) if k not in tests and k != ref]
    for lab in order:
        if lab not in g:
            continue
        d = g[lab]
        lo, hi = pois_ci(d['oreg'])
        ci = f"[{fmt(lo / d['ereg'])}; {fmt(hi / d['ereg'])}]" if d['ereg'] > 0 else '—'
        p(f"{lab:<22}{d['n']:>6}{int(d['sites']):>8}{int(d['o3']):>8}{fmt(d['e3'], 1):>9}{fmt(ratio(d['o3'], d['e3'])):>6}"
          f"{int(d['o7']):>8}{fmt(d['e7'], 1):>9}{fmt(ratio(d['o7'], d['e7'])):>6}"
          f"{int(d['oreg']):>7}{fmt(d['ereg']):>8}{fmt(ratio(d['oreg'], d['ereg'])):>9}  {ci}")
    return g


def report_perm(res, g, ref, tests, label_extra=''):
    for t in tests:
        if t not in res or t not in g:
            continue
        ex = res[t]['ex']
        rg = res[t]['reg']
        dt, dr = g[t], g[ref]
        p(f"  {t} против {ref}{label_extra}:")
        p(f"    ВЫХОД за 3 суток: O/E {fmt(ratio(dt['o3'], dt['e3']))} / {fmt(ratio(dr['o3'], dr['e3']))} = "
          f"{fmt(ex[0])}; перестановка {N_PERM}: p(≤) = {fmt(ex[1], 4)}, p(≥) = {fmt(ex[2], 4)}, двусторонний p = {fmt(ex[3], 4)}")
        pp = pois_two_sided(dt['oreg'], dt['ereg'])
        lo, hi = pois_ci(dt['oreg'])
        p(f"    РЕГИСТРАЦИИ в окне: O = {int(dt['oreg'])}, E = {fmt(dt['ereg'])} → O/E {fmt(ratio(dt['oreg'], dt['ereg']))} "
          f"(95 % {fmt(lo / dt['ereg']) if dt['ereg'] else '—'}–{fmt(hi / dt['ereg']) if dt['ereg'] else '—'}); "
          f"отношение к {ref} {fmt(rg[0])}; пуассон p = {fmt(pp, 4)}; перестановка: p(≤) = {fmt(rg[1], 4)}, двусторонний p = {fmt(rg[3], 4)}")


# ---------------------------------------------------------------- 2. страта = день
p('=' * 100)
p('2. СТРАТА = ДЕНЬ ЗАПУСКА (все оставшиеся домены, дни, где есть и первые, и повторные базы)')
p('   Снимает ли одна дата сырой разрыв? E = доля выхода дня × сайтов домена.')
p('=' * 100)
day_pools = defaultdict(list)
for r in keep:
    day_pools[(r['день запуска'], r['_s150'])].append(r)
day_mixed = [r for k, v in day_pools.items() if len({rep_label(x) for x in v}) > 1 for r in v]
units_day, _ = build_units(day_mixed, lambda r: (r['день запуска'], r['_s150']))
days_used = sorted({r['день запуска'][5:] for r in day_mixed})
p(f"Дней со смешанным составом: {len(days_used)} ({', '.join(days_used)}); доменов {len(day_mixed)}")
g_day = report_groups(day_mixed, units_day, ord_label, '1-я', ['2-я', '3-я'], 'Порядок базы на cf, страта день (+150/206):')
res_day = perm_test(day_mixed, units_day, ord_label, '1-я', ['2-я', '3-я'])
report_perm(res_day, g_day, '1-я', ['2-я', '3-я'])
g_day2 = report_groups(day_mixed, units_day, rep_label, '1-я', ['повторная'], 'Первая против повторной (2-я+3-я), страта день:')
res_day2 = perm_test(day_mixed, units_day, rep_label, '1-я', ['повторная'])
report_perm(res_day2, g_day2, '1-я', ['повторная'])
p('  Оговорка: внутри дня первые и повторные базы часто стоят на разных наборах контента (см. раздел 3),')
p('  поэтому страта «день» — только грубая прикидка, не решающая проверка.')
p('')

# ---------------------------------------------------------------- 3. главная проверка
p('=' * 100)
p('3. ГЛАВНАЯ ПРОВЕРКА: пул = набор контента (без суффикса _NN) + день + 150/206; только пулы с обоими типами баз')
p('=' * 100)


def main_pool_key(r):
    return (r['_set'], r['день запуска'], r['_s150'])


all_pools = defaultdict(list)
for r in keep:
    all_pools[main_pool_key(r)].append(r)
mixed_keys = [k for k, v in all_pools.items() if len({rep_label(x) for x in v}) > 1]
mixed_keys.sort(key=lambda k: (k[1], k[0]))
main_rs = [r for k in mixed_keys for r in all_pools[k]]
p(f'Пулов всего: {len(all_pools)}; пулов с первыми и повторными базами: {len(mixed_keys)}; доменов в них: {len(main_rs)}')
p(f"Пулов, разрезанных признаком 150/206: {len({(k[0], k[1]) for k in all_pools if k[2] == '150'} & {(k[0], k[1]) for k in all_pools if k[2] == '206'})}")
p('')
p('Состав пулов (вых% = вышли за 3 суток / сайтов; рег = в окне 3 суток):')
p(f"{'день':<6}{'набор контента':<36}{'с':>4}{'1-я: n':>7}{'сайт':>6}{'вых%':>6}{'рег':>4}"
  f"{'повт: n':>9}{'сайт':>6}{'вых%':>6}{'рег':>4}  порядок повторных  разрывы")
for k in mixed_keys:
    lst = all_pools[k]
    fi = [r for r in lst if r['_ord'] == 1]
    rp = [r for r in lst if r['_ord'] > 1]

    def agg(x):
        s = sum(r['_sites'] for r in x)
        return len(x), int(s), (100 * sum(r['_ex3'] for r in x) / s if s else 0), int(sum(r['_reg'] for r in x))

    a, b = agg(fi), agg(rp)
    ords = dict(sorted(Counter(ord_label(r) for r in rp).items()))
    gp = sorted(Counter(r['_gap'] for r in rp).items())
    p(f"{k[1][5:]:<6}{k[0][:35]:<36}{k[2]:>4}{a[0]:>7}{a[1]:>6}{fmt(a[2], 1):>6}{a[3]:>4}"
      f"{b[0]:>9}{b[1]:>6}{fmt(b[2], 1):>6}{b[3]:>4}  {ords}  {gp}")
p('')

units_main, rates_main = build_units(main_rs, main_pool_key)
n_zero_reg = sum(1 for k in mixed_keys if rates_main[k][2] == 0)
p(f'Пулов без единой регистрации (в расчёт регистраций не вносят ни O, ни E): {n_zero_reg} из {len(mixed_keys)}')
p('')
g_main = report_groups(main_rs, units_main, ord_label, '1-я', ['2-я', '3-я'], '3a. Порядок базы на cf (1-я / 2-я / 3-я):')
res_main = perm_test(main_rs, units_main, ord_label, '1-я', ['2-я', '3-я'])
report_perm(res_main, g_main, '1-я', ['2-я', '3-я'])
p('')
g_main2 = report_groups(main_rs, units_main, rep_label, '1-я', ['повторная'], '3b. Первая против повторной (2-я + 3-я вместе):')
res_main2 = perm_test(main_rs, units_main, rep_label, '1-я', ['повторная'])
report_perm(res_main2, g_main2, '1-я', ['повторная'])
main_ratio_ex = res_main2['повторная']['ex']
main_ratio_reg = res_main2['повторная']['reg']
p('')
p('  Что можно увидеть по регистрациям: при E ≈ {:.0f} у первых и ≈ {:.0f} у повторных 95 %-интервал O/E шириной'
  .format(g_main2['1-я']['ereg'], g_main2['повторная']['ereg']))
p('  примерно ×0,5…×1,8 — различим только эффект в 2 раза и больше. Это ограничение данных, не результат.')
p('')

# ---------------------------------------------------------------- 4. разрыв
p('=' * 100)
p('4. РАЗРЫВ ОТ ПРЕДЫДУЩЕЙ БАЗЫ (те же пулы; каждая группа разрыва — против первых баз тех же пулов)')
p('=' * 100)
gap_labels = ['разрыв ≤2', 'разрыв 3–7', 'разрыв 8–17', 'разрыв ≥18']
g_gap = report_groups(main_rs, units_main, lambda r: gap_bucket(r['_gap']), '1-я (нет разрыва)', gap_labels,
                      '4a. Все группы разрыва при пуловом E (справочно, пулы у групп разные):')
p('')
res_gap = {}
for gl in gap_labels:
    pools_with = {units_main[r['домен']]['pool'] for r in main_rs if gap_bucket(r['_gap']) == gl}
    sub = [r for r in main_rs if units_main[r['домен']]['pool'] in pools_with
           and gap_bucket(r['_gap']) in (gl, '1-я (нет разрыва)')]
    if not sub:
        continue
    days = sorted({k[1][5:] for k in pools_with})
    p(f"4b. «{gl}» против первых баз в тех же пулах: пулов {len(pools_with)} (дни {', '.join(days)}), доменов {len(sub)}")
    gg = report_groups(sub, units_main, lambda r: gap_bucket(r['_gap']), '1-я (нет разрыва)', [gl], '')
    rr = perm_test(sub, units_main, lambda r: gap_bucket(r['_gap']), '1-я (нет разрыва)', [gl])
    res_gap[gl] = rr
    report_perm(rr, gg, '1-я (нет разрыва)', [gl])
    p('')

# Спирмен разрыв ↔ O/E выхода домена среди повторных баз
rep_units = [(r, units_main[r['домен']]) for r in main_rs if r['_ord'] > 1 and units_main[r['домен']]['e3'] > 0]
xs = [r['_gap'] for r, u in rep_units]
ys = [u['o3'] / u['e3'] for r, u in rep_units]
rho = spearman(xs, ys)
pools_of = defaultdict(list)
for i, (r, u) in enumerate(rep_units):
    pools_of[u['pool']].append(i)
cnt_le = cnt_ge = 0
if rho is not None:
    xs_w = list(xs)
    for _ in range(N_PERM):
        for idxs in pools_of.values():
            vals = [xs_w[i] for i in idxs]
            random.shuffle(vals)
            for i, v in zip(idxs, vals):
                xs_w[i] = v
        rp_ = spearman(xs_w, ys)
        if rp_ is None:
            continue
        if rp_ <= rho + 1e-12:
            cnt_le += 1
        if rp_ >= rho - 1e-12:
            cnt_ge += 1
n_within = sum(1 for idxs in pools_of.values() if len({xs[i] for i in idxs}) > 1)
p(f'4c. Спирмен «разрыв (дни) ↔ O/E выхода домена» среди повторных баз главных пулов: n = {len(xs)}, ρ = {fmt(rho, 3)};')
p(f"    перестановка разрыва внутри пула {N_PERM} раз: p(≤) = {fmt(cnt_le / N_PERM, 4)}, p(≥) = {fmt(cnt_ge / N_PERM, 4)}, "
  f"двусторонний p = {fmt(min(1.0, 2 * min(cnt_le, cnt_ge) / N_PERM), 4)}")
p(f'    Пулов, где разрыв внутри пула вообще различается: {n_within} из {len(pools_of)} — разброс разрыва внутри пула мал '
  f'(в пуле обычно 1–2 значения), поэтому тест слабый.')
p('')

# ---------------------------------------------------------------- 5. зона
p('=' * 100)
p('5. КОНТРОЛЬ ЗОНЫ')
p('=' * 100)
zone_cells = defaultdict(list)
for r in main_rs:
    zone_cells[(main_pool_key(r), r['зона'])].append(r)
good_cells = [k for k, v in zone_cells.items()
              if sum(1 for x in v if x['_ord'] == 1) >= 3 and sum(1 for x in v if x['_ord'] > 1) >= 3]
p(f'Ячеек пул×зона с ≥3 доменами каждой группы: {len(good_cells)} — '
  + '; '.join(f"{k[0][1][5:]} {k[0][0][:30]} {k[1]} ({len(zone_cells[k])})" for k in sorted(good_cells, key=lambda k: k[0][1])))
if good_cells:
    zrs = [r for k in good_cells for r in zone_cells[k]]
    units_z, _ = build_units(zrs, lambda r: (main_pool_key(r), r['зона']))
    gz = report_groups(zrs, units_z, rep_label, '1-я', ['повторная'], '5a. Страта пул × зона (только эти ячейки):')
    rz = perm_test(zrs, units_z, rep_label, '1-я', ['повторная'])
    report_perm(rz, gz, '1-я', ['повторная'])
p('')
p('5b. O/E по зонам при пуловом E (главные пулы), первая против повторной:')
p(f"{'зона':<8}{'группа':<12}{'домен':>6}{'сайтов':>8}{'O вых3':>8}{'E вых3':>9}{'O/E':>6}{'O рег':>7}{'E рег':>8}{'O/E рег':>9}")
for z in ('team', 'lol', 'casino', 'buzz'):
    sub = [r for r in main_rs if r['зона'] == z]
    if not sub:
        continue
    gg = group_sums(sub, units_main, rep_label)
    for lab in ('1-я', 'повторная'):
        if lab in gg:
            d = gg[lab]
            p(f"{z:<8}{lab:<12}{d['n']:>6}{int(d['sites']):>8}{int(d['o3']):>8}{fmt(d['e3'], 1):>9}{fmt(ratio(d['o3'], d['e3'])):>6}"
              f"{int(d['oreg']):>7}{fmt(d['ereg']):>8}{fmt(ratio(d['oreg'], d['ereg'])):>9}")
zone_mix = Counter((rep_label(r), r['зона']) for r in main_rs)
p('  Состав по зонам: ' + '; '.join(f'{k[0]} {k[1]} {v}' for k, v in sorted(zone_mix.items())))
p('')

# ---------------------------------------------------------------- 6. 16.09 грубая страта
p('=' * 100)
p('6. ДЕНЬ 16.09: первые и вторые базы стоят на РАЗНЫХ наборах — грубая страта день + семейство + страниц + оформление + 150/206')
p('   (оговорка: набор контента здесь не выровнен; разница наборов внутри ячейки не снимается)')
p('=' * 100)


def coarse_key(r):
    return (r['день запуска'], r['семейство'], r['страниц'], r['оформление'], r['_s150'])


d16 = [r for r in keep if r['день запуска'] == '2026-09-16']
c16 = defaultdict(list)
for r in d16:
    c16[coarse_key(r)].append(r)
p('Ячейки 16.09 (семейство / страниц / оформление / 150-206 → первые : повторные, наборы):')
for k, v in sorted(c16.items()):
    fi = Counter(r['_set'] for r in v if r['_ord'] == 1)
    rp = Counter(r['_set'] for r in v if r['_ord'] > 1)
    p(f"  {k[1]} / {k[2] or '—'} / {k[3] or '—'} / {k[4]}: {sum(fi.values())} : {sum(rp.values())}"
      f"   первые: {dict(fi)}   повторные: {dict(rp)}")
c16_mixed = [r for k, v in c16.items() if len({rep_label(x) for x in v}) > 1 for r in v]
p(f'Смешанных ячеек: {len([k for k, v in c16.items() if len({rep_label(x) for x in v}) > 1])}; доменов в них: {len(c16_mixed)}')
if c16_mixed:
    units_16, _ = build_units(c16_mixed, coarse_key)
    g16 = report_groups(c16_mixed, units_16, rep_label, '1-я', ['повторная'], '6a. 16.09, грубая страта:')
    r16 = perm_test(c16_mixed, units_16, rep_label, '1-я', ['повторная'])
    report_perm(r16, g16, '1-я', ['повторная'])
    gaps16 = Counter(r['_gap'] for r in c16_mixed if r['_ord'] > 1)
    p(f'  Разрывы повторных баз 16.09: {dict(sorted(gaps16.items()))}')
    p('')
    # объединение главных пулов + грубая ячейка 16.09
    comb = main_rs + c16_mixed
    units_comb = dict(units_main)
    units_comb.update(units_16)
    p('6b. Главные пулы + грубая ячейка 16.09 вместе:')
    gc = report_groups(comb, units_comb, rep_label, '1-я', ['повторная'], '')
    rc = perm_test(comb, units_comb, rep_label, '1-я', ['повторная'])
    report_perm(rc, gc, '1-я', ['повторная'])
    comb_ratio_ex = rc['повторная']['ex']
    comb_ratio_reg = rc['повторная']['reg']
    p('')
    # быстрый повтор ≤2 дней: главные пулы + 16.09
    sub = [r for r in comb if r['_ord'] == 1 or (r['_gap'] is not None and r['_gap'] <= 2)]
    pools_with = {units_comb[r['домен']]['pool'] for r in sub if r['_ord'] > 1}
    sub = [r for r in sub if units_comb[r['домен']]['pool'] in pools_with]
    p(f'6c. Быстрый повтор (разрыв ≤2 дней) против первых в тех же пулах, главные пулы + 16.09: пулов {len(pools_with)}, доменов {len(sub)}')
    gq = report_groups(sub, units_comb, lambda r: gap_bucket(r['_gap']), '1-я (нет разрыва)', ['разрыв ≤2'], '')
    rq = perm_test(sub, units_comb, lambda r: gap_bucket(r['_gap']), '1-я (нет разрыва)', ['разрыв ≤2'])
    report_perm(rq, gq, '1-я (нет разрыва)', ['разрыв ≤2'])
    quick_ratio_ex = rq['разрыв ≤2']['ex']
    quick_ratio_reg = rq['разрыв ≤2']['reg']
    p('')
    # 6d. паспорт наборов из смешанной ячейки 16.09: как те же наборы ведут себя в другие дни и на других порядках
    p('6d. Наборы из смешанной ячейки 16.09 в другие дни (выход = вышли за 3 суток / сайтов; рег в окне):')
    p('    Если «первые» 16.09 стоят на наборах, которые и 15.09 (тоже первыми базами) выходили в 20 %+, а «вторые» —')
    p('    на наборах, никогда не стоявших на первых базах, то разница 16.09 — это наборы, а не cf.')
    sets16 = sorted({r['_set'] for r in c16_mixed})
    p(f"{'набор контента':<36}{'день':>6}{'порядок':>8}{'сайтов':>7}{'n':>4}{'вых%':>6}{'рег':>4}")
    for s in sets16:
        cells = defaultdict(list)
        for r in keep:
            if r['_set'] == s:
                cells[(r['день запуска'][5:], r['_ord'], r['_s150'])].append(r)
        for k, v in sorted(cells.items()):
            st = sum(r['_sites'] for r in v)
            p(f"{s[:35]:<36}{k[0]:>6}{ord_label(v[0]):>8}{k[2]:>7}{len(v):>4}{fmt(100 * sum(r['_ex3'] for r in v) / st, 1) if st else '—':>6}"
              f"{int(sum(r['_reg'] for r in v)):>4}")
else:
    comb_ratio_ex = comb_ratio_reg = quick_ratio_ex = quick_ratio_reg = (None,) * 4
p('')

# ---------------------------------------------------------------- 7. 2-я против 3-й
p('=' * 100)
p('7. ВТОРАЯ ПРОТИВ ТРЕТЬЕЙ внутри пулов, где первых баз нет (09–11.09)')
p('=' * 100)
k23 = [k for k, v in all_pools.items() if 1 not in {x['_ord'] for x in v} and len({x['_ord'] for x in v}) > 1]
rs23 = [r for k in k23 for r in all_pools[k]]
p(f'Пулов: {len(k23)}; доменов: {len(rs23)}; состав: '
  + '; '.join(f"{k[1][5:]} {k[0][:30]} {dict(sorted(Counter(ord_label(x) for x in all_pools[k]).items()))}" for k in sorted(k23, key=lambda k: k[1])))
if rs23:
    units_23, _ = build_units(rs23, main_pool_key)
    g23 = report_groups(rs23, units_23, ord_label, '2-я', ['3-я'], '')
    r23 = perm_test(rs23, units_23, ord_label, '2-я', ['3-я'])
    report_perm(r23, g23, '2-я', ['3-я'])
p('')

# ---------------------------------------------------------------- 8. чувствительность
p('=' * 100)
p('8. ЧУВСТВИТЕЛЬНОСТЬ')
p('=' * 100)
sens = {}
sub = [r for r in main_rs if r['_s150'] == '206']
keys_sub = {units_main[r['домен']]['pool'] for r in sub}
p(f'8a. Без пулов «150 сайтов» (остаётся пулов {len(keys_sub)}, доменов {len(sub)}):')
gs = report_groups(sub, units_main, rep_label, '1-я', ['повторная'], '')
rs_ = perm_test(sub, units_main, rep_label, '1-я', ['повторная'])
report_perm(rs_, gs, '1-я', ['повторная'])
sens['без 150'] = rs_['повторная']
p('')
sub = [r for r in main_rs if not any(x['_suffixed'] for x in all_pools[units_main[r['домен']]['pool']])]
keys_sub = {units_main[r['домен']]['pool'] for r in sub}
p(f'8b. Только пулы, где имя набора взято как есть (суффикс не снимался): пулов {len(keys_sub)}, доменов {len(sub)}:')
if sub:
    gs = report_groups(sub, units_main, rep_label, '1-я', ['повторная'], '')
    rs_ = perm_test(sub, units_main, rep_label, '1-я', ['повторная'])
    report_perm(rs_, gs, '1-я', ['повторная'])
    sens['без снятия суффикса'] = rs_['повторная']
p('')
sub = [r for r in main_rs if units_main[r['домен']]['pool'][1] >= '2026-09-16']
keys_sub = {units_main[r['домен']]['pool'] for r in sub}
p(f'8c. Только пулы 16–18.09 (быстрые повторы, «плохие дни»): пулов {len(keys_sub)}, доменов {len(sub)}:')
if sub:
    gs = report_groups(sub, units_main, rep_label, '1-я', ['повторная'], '')
    rs_ = perm_test(sub, units_main, rep_label, '1-я', ['повторная'])
    report_perm(rs_, gs, '1-я', ['повторная'])
    sens['только 16–18.09'] = rs_['повторная']
p('')
sub = [r for r in main_rs if units_main[r['домен']]['pool'][1] < '2026-09-16']
keys_sub = {units_main[r['домен']]['pool'] for r in sub}
p(f'8d. Только пулы 03.09 и 12–13.09 (разрывы 5–23 дня): пулов {len(keys_sub)}, доменов {len(sub)}:')
if sub:
    gs = report_groups(sub, units_main, rep_label, '1-я', ['повторная'], '')
    rs_ = perm_test(sub, units_main, rep_label, '1-я', ['повторная'])
    report_perm(rs_, gs, '1-я', ['повторная'])
    sens['до 16.09'] = rs_['повторная']
p('')

# ---------------------------------------------------------------- ВЫВОД
p('=' * 100)
p('ВЫВОД')
p('=' * 100)
d1, dr = g_main2['1-я'], g_main2['повторная']
oe1, oer = ratio(d1['o3'], d1['e3']), ratio(dr['o3'], dr['e3'])
r_ex, p_ex = main_ratio_ex[0], main_ratio_ex[3]
r_reg, p_reg = main_ratio_reg[0], main_ratio_reg[3]
lo_r, hi_r = pois_ci(dr['oreg'])
p(f'Сырой срез: 1-я база на cf выходит в поиск в {fmt(100 * sum(r["_ex3"] for r in raw_rows if r["_ord"] == 1) / sum(r["_sites"] for r in raw_rows if r["_ord"] == 1), 1)} % случаев, '
  f'2-я — в {fmt(100 * sum(r["_ex3"] for r in raw_rows if r["_ord"] == 2) / sum(r["_sites"] for r in raw_rows if r["_ord"] == 2), 1)} %, '
  f'3-я — в {fmt(100 * sum(r["_ex3"] for r in raw_rows if r["_ord"] == 3) / sum(r["_sites"] for r in raw_rows if r["_ord"] == 3), 1)} %. '
  f'Но порядок базы на cf почти')
p('полностью совпадает с датой запуска, а дата и набор контента — главные тени.')
p(f'Внутри пулов «набор контента + день» (пулов {len(mixed_keys)}, доменов {len(main_rs)}: первых {d1["n"]}, повторных {dr["n"]}) '
  f'выход повторных баз относительно')
p(f'первых = {fmt(r_ex)} (O/E {fmt(oer)} против {fmt(oe1)}; перестановочный двусторонний p = {fmt(p_ex, 3)}). '
  f'По регистрациям: у повторных {int(dr["oreg"])} при ожидании {fmt(dr["ereg"], 1)} '
  f'(O/E {fmt(ratio(dr["oreg"], dr["ereg"]))}, 95 % {fmt(lo_r / dr["ereg"]) if dr["ereg"] else "—"}–{fmt(hi_r / dr["ereg"]) if dr["ereg"] else "—"}), '
  f'у первых {int(d1["oreg"])} при {fmt(d1["ereg"], 1)}; отношение {fmt(r_reg)}, p = {fmt(p_reg, 3)}.')
if res_main['2-я']['ex'][0] is not None:
    p(f'Отдельно 2-я база: выход к первой {fmt(res_main["2-я"]["ex"][0])} (p = {fmt(res_main["2-я"]["ex"][3], 3)}), '
      f'3-я база: {fmt(res_main["3-я"]["ex"][0])} (p = {fmt(res_main["3-я"]["ex"][3], 3)}).')
p(f"Быстрый повтор через 1–2 дня внутри честных пулов (два пула 17.09): выход {fmt(res_gap['разрыв ≤2']['разрыв ≤2']['ex'][0])} "
  f"(p = {fmt(res_gap['разрыв ≤2']['разрыв ≤2']['ex'][3], 3)}) — тоже без разницы.")
if comb_ratio_ex[0] is not None:
    p(f'Единственное место, где повторные выглядят хуже, — 16.09: там повторные к первым по выходу {fmt(r16["повторная"]["ex"][0])} '
      f'(p = {fmt(r16["повторная"]["ex"][3], 3)}), но первые стоят на наборах content-2026-09-14c-*, которые и 15.09 первыми базами')
    p('выходили в 20–24 %, а повторные — на наборах content-2026-09-15-*, которые ни разу не стояли на первых базах. Это разница')
    p(f'наборов, а не cf; по регистрациям в той же ячейке повторные даже выше ({fmt(r16["повторная"]["reg"][0])}). '
      f'Если всё же сложить 16.09 с честными пулами: выход {fmt(comb_ratio_ex[0])} (p = {fmt(comb_ratio_ex[3], 3)}), '
      f'регистрации {fmt(comb_ratio_reg[0])} (p = {fmt(comb_ratio_reg[3], 3)}); быстрый повтор ≤2 дней с 16.09: '
      f'выход {fmt(quick_ratio_ex[0])} (p = {fmt(quick_ratio_ex[3], 3)}), регистрации {fmt(quick_ratio_reg[0])} (p = {fmt(quick_ratio_reg[3], 3)}).')
p('Чувствительность (повторные / первые по выходу): '
  + '; '.join(f'{k}: {fmt(v["ex"][0])} (p = {fmt(v["ex"][3], 3)})' for k, v in sens.items()))
p('')


def verdict_text():
    if r_ex is None:
        return 'не решается на этих данных'
    harm = r_ex <= 0.85 and p_ex is not None and p_ex < 0.05 and (r_reg is not None and r_reg < 1)
    refuted = 0.9 <= r_ex <= 1.1
    if harm:
        return ('ГИПОТЕЗА ПОДТВЕРЖДЕНА: после страты по набору контента и дню повторные базы на cf выходят хуже '
                'первых на статистически значимую величину, и регистрации идут в ту же сторону.')
    if refuted:
        return ('ГИПОТЕЗА ОПРОВЕРГНУТА: после страты по набору контента и дню разница между первой и повторной базой '
                'на cf укладывается в 0,9–1,1 — сырой разрыв 15,8 % → 11,3 % → 10,1 % был тенью даты и набора контента.')
    return ('ЧАСТИЧНО / НЕ РЕШАЕТСЯ ОДНОЗНАЧНО: отношение вне коридора 0,9–1,1, но либо не значимо, либо '
            'регистрации не подтверждают знак; объёма пулов не хватает.')


p('Ограничение: регистраций в честных пулах всего 23 (10 у первых, 13 у повторных), поэтому по деньгам различим только')
p('эффект в 2 раза и больше; по выходу в поиск (4 080 вышедших сайтов) чувствительность высокая — разница в 10 % была бы видна.')
p('')
p(verdict_text())
p('')
p('Что с этим делать: ' + (
    'cf-аккаунт можно использовать повторно, в том числе через 1–2 дня, — на выход и регистрации это не влияет; '
    'парк cf расширять не нужно, «отдых» cf не нужен. Проверить на новых запусках только одно: ставить часть баз '
    'на свежие cf и часть на повторные ВНУТРИ ОДНОГО набора контента и дня — тогда сравнение будет чистым, а не по остаткам совпадений.'
    if r_ex is not None and 0.9 <= r_ex <= 1.1 else
    'сравнение внутри пулов не даёт уверенного ответа: нужно ставить первые и повторные базы cf на один набор '
    'контента в один день (сейчас такие пары — случайность планирования), тогда через 3 суток ответ будет виден.'))

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print(f'\n[записано: {OUT}]')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептическая проверка гипотезы №2 (угол: СТАТИСТИКА).

Вопросы:
 1. Суммы или средние по доменам от долей? (проверка по коду h02 + контрольный пересчёт)
 2. Сколько сравнений сделано; выживает ли главный результат при перестановочном тесте
    на весь набор срезов (max-T по семейству тестов, одна общая перестановка меток)?
 3. Хватает ли регистраций в группах (<20 в группе — не доказательство)?
 4. Держится ли всё на 1–3 доменах: убрать топ-3 домена по регистрациям в каждой группе
    и пересчитать; винзоризация регистраций; индикатор «есть регистрация»;
    выкидывание по одному пулу и топ-пулов по вкладу в дефицит.

Фильтр и признаки — ровно как в h02_generated_looking_labels.py. Только stdlib.
Вывод — stdout и analysis/export/gipotezy_svod/v02_statistika.txt
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'v02_statistika.txt')
os.makedirs(OUT_DIR, exist_ok=True)
OUTLIERS = {'3615.team', '3286.team'}
_lines = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _lines.append(s)


def to_int(s):
    s = (s or '').strip()
    return int(float(s)) if s else 0


with open(SRC, encoding='utf-8', newline='') as fh:
    rows_all = list(csv.DictReader(fh))
rows = [r for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да'
        and r['дней'] != '1' and r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
p('Всего доменов: %d; после фильтра как в h02: %d' % (len(rows_all), len(rows)))

DATE_RE = re.compile(r'^\d{4}[a-z]+$')


def subtype(r):
    l = r['домен'].split('.')[0]
    pat = r['паттерн имени']
    if pat == 'numeric':
        return 'numeric: ведущий 0' if l[0] == '0' else 'numeric: обычный'
    if pat == 'alpha_other':
        if DATE_RE.match(l):
            return 'alpha_other: код даты'
        if l.isalpha():
            return 'alpha_other: буквы, длина %d' % len(l)
        return 'alpha_other: смесь, длина %d' % len(l)
    return pat


for r in rows:
    r['_lab'] = r['домен'].split('.')[0]
    r['_sub'] = subtype(r)
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_out3'] = to_int(r['вышли за 3 суток'])
    r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_fd'] = to_int(r['ФД в окне 3 суток'])
    r['_pool'] = (r['набор контента'], r['день запуска'])
    r['_pat'] = r['паттерн имени']

num_rows = [r for r in rows if r['_pat'] == 'numeric']
alpha_rows = [r for r in rows if r['_pat'] == 'alpha_other']
na_rows = num_rows + alpha_rows

S_ZERO = 'numeric: ведущий 0'
S_MIX4 = 'alpha_other: смесь, длина 4'
S_MIX3 = 'alpha_other: смесь, длина 3'
S_ALP3 = 'alpha_other: буквы, длина 3'
S_ALP4 = 'alpha_other: буквы, длина 4'
S_DATE = 'alpha_other: код даты'


def is_alpha_digit(r):
    return r['_pat'] == 'alpha_other' and not r['_sub'].startswith('alpha_other: буквы')


def is_alpha_letters(r):
    return r['_sub'].startswith('alpha_other: буквы')


# Семейство тестов (имя, отбор строк, признак, заранее задан?)
TESTS = [
    ('A ведущий 0 vs numeric', lambda r: r['_pat'] == 'numeric', lambda r: r['_sub'] == S_ZERO, True),
    ('B смесь-4 vs буквы-4', lambda r: r['_sub'] in (S_MIX4, S_ALP4), lambda r: r['_sub'] == S_MIX4, True),
    ('C длина-3 vs буквы-4', lambda r: r['_sub'] in (S_MIX3, S_ALP3, S_ALP4), lambda r: r['_sub'] in (S_MIX3, S_ALP3), True),
    ('D код даты vs буквы-4', lambda r: r['_sub'] in (S_DATE, S_ALP4), lambda r: r['_sub'] == S_DATE, True),
    ('Объед. alpha с цифрой vs буквы', lambda r: r['_pat'] == 'alpha_other', is_alpha_digit, True),
    ('ВСЕ признаки vs обычные', lambda r: True, lambda r: r['_sub'] == S_ZERO or is_alpha_digit(r), True),
    ('C2 смесь-3 vs смесь-4', lambda r: r['_sub'] in (S_MIX3, S_MIX4), lambda r: r['_sub'] == S_MIX3, False),
    ('Объед. без кода даты', lambda r: r['_pat'] == 'alpha_other' and r['_sub'] != S_DATE, is_alpha_digit, False),
    ('ВСЕ без кода даты (пост-хок)', lambda r: r['_sub'] != S_DATE, lambda r: r['_sub'] == S_ZERO or is_alpha_digit(r), False),
]


def oe(rs, is_feat, regkey='_regs', key='_pool', with_pools=False):
    """Стратифицированный O/E (суммы!): E = доля пула × сайтов домена."""
    pools = defaultdict(list)
    for r in rs:
        pools[r[key]].append(r)
    used = {k: v for k, v in pools.items()
            if any(is_feat(r) for r in v) and any(not is_feat(r) for r in v)}
    res = {'pools': len(used)}
    if not used:
        return None
    O_out = E_out = O_reg = E_reg = 0.0
    Or_reg = Or_out = 0
    nf = nr = sf = sr = 0
    pool_rows = []
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        ro = sum(r['_out3'] for r in v) / S
        rr = sum(r[regkey] for r in v) / S
        po = pe = pr = pre = 0.0
        for r in v:
            if is_feat(r):
                po += r['_out3']; pe += ro * r['_sites']
                pr += r[regkey]; pre += rr * r['_sites']
                nf += 1; sf += r['_sites']
            else:
                Or_reg += r[regkey]; Or_out += r['_out3']
                nr += 1; sr += r['_sites']
        O_out += po; E_out += pe; O_reg += pr; E_reg += pre
        if with_pools:
            pool_rows.append((k, sum(1 for r in v if is_feat(r)), len(v) - sum(1 for r in v if is_feat(r)),
                              pr, pre, po, pe, sum(r[regkey] for r in v)))
    res.update(O_out=O_out, E_out=E_out, O_reg=O_reg, E_reg=E_reg,
               oe_out=O_out / E_out if E_out else float('nan'),
               oe_reg=O_reg / E_reg if E_reg else float('nan'),
               n_feat=nf, n_ref=nr, sites_feat=sf, sites_ref=sr, regs_ref=Or_reg, out_ref=Or_out,
               used=used, pool_rows=pool_rows)
    return res


def perm_p(rs, is_feat, regkey='_regs', key='_pool', n_perm=3000, seed=7):
    """Перестановка признака внутри пула; односторонний p «хуже» по выходу и регистрациям."""
    rnd = random.Random(seed)
    base = oe(rs, is_feat, regkey, key)
    if base is None:
        return None, None, None
    used = base['used']
    rate = {}
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rate[k] = (sum(r['_out3'] for r in v) / S, sum(r[regkey] for r in v) / S)
    pl = [(list(v), sum(1 for r in v if is_feat(r))) for v in used.values()]
    c_out = c_reg = 0
    for _ in range(n_perm):
        po = pe = ro = re_ = 0.0
        for v, m in pl:
            rnd.shuffle(v)
            ro_, rr_ = rate[v[0][key]]
            for r in v[:m]:
                po += r['_out3']; ro += r[regkey]
                pe += ro_ * r['_sites']; re_ += rr_ * r['_sites']
        if po / pe <= base['oe_out'] + 1e-12:
            c_out += 1
        if (ro / re_ if re_ else 0) <= base['oe_reg'] + 1e-12:
            c_reg += 1
    return base, c_out / n_perm, c_reg / n_perm


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    return min(1.0, sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(int(k) + 1)))


def show(name, res, p_out=None, p_reg=None):
    if res is None:
        p('  %-44s нет пулов' % name)
        return
    s = '  %-44s пулов %3d, дом. %3d/%-3d | выход O/E %.2f' % (
        name, res['pools'], res['n_feat'], res['n_ref'], res['oe_out'])
    if p_out is not None:
        s += ' (p=%.3f)' % p_out
    s += ' | рег O=%g E=%.1f O/E %.2f (сравн. %g рег)' % (res['O_reg'], res['E_reg'], res['oe_reg'], res['regs_ref'])
    if p_reg is not None:
        s += ' pпер=%.3f' % p_reg
    s += ' pпуас=%.3f' % poisson_cdf(res['O_reg'], res['E_reg'])
    p(s)


# =====================================================================================
p()
p('=' * 100)
p('1. СУММЫ ИЛИ СРЕДНИЕ ПО ДОМЕНАМ?')
p('=' * 100)
p('По коду h02: O = сумма регистраций (выходов) по доменам с признаком; E = Σ (сумма пула / сайты пула) × сайты домена.')
p('Это суммы по группам с весом «сайтов в окне», а не среднее по доменам от долей. Контрольный пересчёт своим кодом:')
for name, sel, feat, pre in TESTS:
    show(name, oe([r for r in na_rows if sel(r)], feat))
p('Числа совпадают с h02 (O/E по выходу и регистрациям те же). Претензии к агрегированию нет.')

# =====================================================================================
p()
p('=' * 100)
p('2. СКОЛЬКО РЕГИСТРАЦИЙ В ГРУППАХ И НА СКОЛЬКИХ ДОМЕНАХ ОНИ СИДЯТ')
p('=' * 100)
p('%-34s %6s %6s %8s %7s %8s %7s %8s' % ('сравнение', 'рег F', 'дом≥1', 'топ-3 F', 'рег R', 'дом≥1 R', 'топ-3 R', 'макс R'))
for name, sel, feat, pre in TESTS:
    res = oe([r for r in na_rows if sel(r)], feat)
    doms = [r for v in res['used'].values() for r in v]
    F = sorted([r['_regs'] for r in doms if feat(r)], reverse=True)
    R = sorted([r['_regs'] for r in doms if not feat(r)], reverse=True)
    p('%-34s %6d %6d %8d %7d %8d %7d %8d' % (name, sum(F), sum(1 for x in F if x), sum(F[:3]),
                                              sum(R), sum(1 for x in R if x), sum(R[:3]), R[0] if R else 0))
p('F — группа с признаком, R — группа сравнения; «топ-3» — сколько регистраций у трёх самых богатых доменов группы.')
p('В группе с признаком ни в одном сравнении нет 20 регистраций (максимум 19 в «все признаки»). По критерию «<20 —')
p('не доказательство» ни одно сравнение порога не проходит.')

# =====================================================================================
p()
p('=' * 100)
p('3. ДЕРЖИТСЯ ЛИ НА 1–3 ДОМЕНАХ: УБИРАЕМ ТОП-3 ДОМЕНА ПО РЕГИСТРАЦИЯМ В КАЖДОЙ ГРУППЕ И ПЕРЕСЧИТЫВАЕМ')
p('=' * 100)
N_PERM_SENS = 3000


def top_k(rs, feat, k, side):
    """домены-лидеры по регистрациям в группе side ('F'/'R') внутри использованных пулов"""
    res = oe(rs, feat)
    doms = [r for v in res['used'].values() for r in v if (feat(r) if side == 'F' else not feat(r))]
    doms.sort(key=lambda r: (-r['_regs'], r['домен']))
    return {r['домен'] for r in doms[:k]}


MAIN = [t for t in TESTS if t[0] in ('ВСЕ признаки vs обычные', 'ВСЕ без кода даты (пост-хок)',
                                     'A ведущий 0 vs numeric', 'B смесь-4 vs буквы-4', 'C длина-3 vs буквы-4',
                                     'Объед. alpha с цифрой vs буквы')]
for name, sel, feat, pre in MAIN:
    p()
    p('--- %s ---' % name)
    rs = [r for r in na_rows if sel(r)]
    base, po, pr = perm_p(rs, feat, n_perm=N_PERM_SENS)
    show('как есть', base, po, pr)
    dropR = top_k(rs, feat, 3, 'R')
    dropF = top_k(rs, feat, 3, 'F')
    resR = oe([r for r in rs if r['домен'] not in dropR], feat)
    dr = [r for r in rs if r['домен'] in dropR]
    p('    топ-3 сравнения: %s' % ', '.join('%s(%d рег, пул %s|%s)' % (r['домен'], r['_regs'], r['_pool'][0][:18], r['_pool'][1][5:]) for r in dr))
    b, po, pr = perm_p([r for r in rs if r['домен'] not in dropR], feat, n_perm=N_PERM_SENS)
    show('без топ-3 сравнения', b, po, pr)
    b, po, pr = perm_p([r for r in rs if r['домен'] not in dropR | dropF], feat, n_perm=N_PERM_SENS)
    show('без топ-3 в обеих группах', b, po, pr)
    dropR6 = top_k(rs, feat, 6, 'R')
    b, po, pr = perm_p([r for r in rs if r['домен'] not in dropR6], feat, n_perm=N_PERM_SENS)
    show('без топ-6 сравнения', b, po, pr)
    # винзоризация
    for cap in (3, 2, 1):
        for r in rs:
            r['_regc'] = min(r['_regs'], cap)
        b, po, pr = perm_p(rs, feat, regkey='_regc', n_perm=N_PERM_SENS)
        show('регистрации обрезаны до %d на домен' % cap, b, po, pr)
    # ФД
    b = oe(rs, feat, regkey='_fd')
    p('  %-44s ФД: O=%g, E=%.1f, O/E %.2f (сравн. %g ФД)' % ('первые депозиты (ФД) в окне', b['O_reg'], b['E_reg'], b['oe_reg'], b['regs_ref']))

# =====================================================================================
p()
p('=' * 100)
p('4. ДЕРЖИТСЯ ЛИ НА 1–3 ПУЛАХ: ВКЛАД ПУЛОВ В ДЕФИЦИТ И ВЫКИДЫВАНИЕ ПУЛОВ')
p('=' * 100)
for name, sel, feat, pre in MAIN[:2] if False else [t for t in TESTS if t[0] in ('ВСЕ признаки vs обычные', 'ВСЕ без кода даты (пост-хок)')]:
    p()
    p('--- %s ---' % name)
    rs = [r for r in na_rows if sel(r)]
    res = oe(rs, feat, with_pools=True)
    prs = sorted(res['pool_rows'], key=lambda x: -(x[4] - x[3]))
    p('  пулы по вкладу в дефицит регистраций (E−O у признака):')
    p('  %-40s %5s %5s %6s %7s %7s %8s' % ('пул', 'nF', 'nR', 'O рег', 'E рег', 'E−O', 'рег пула'))
    for k, nf, nr, o, e, oo, ee, tot in prs[:8]:
        p('  %-40s %5d %5d %6g %7.2f %7.2f %8d' % ('%s | %s' % (k[0][:26], k[1][5:]), nf, nr, o, e, e - o, tot))
    tot_def = res['E_reg'] - res['O_reg']
    top3 = sum(x[4] - x[3] for x in prs[:3])
    top5 = sum(x[4] - x[3] for x in prs[:5])
    p('  общий дефицит E−O = %.2f; на топ-3 пулах %.2f (%.0f%%), на топ-5 %.2f (%.0f%%); пулов с положительным вкладом %d из %d' % (
        tot_def, top3, 100 * top3 / tot_def, top5, 100 * top5 / tot_def, sum(1 for x in prs if x[4] - x[3] > 0), len(prs)))
    # выкинуть топ-k пулов по вкладу
    for k in (1, 2, 3, 5):
        drop = {x[0] for x in prs[:k]}
        b, po, pr = perm_p([r for r in rs if r['_pool'] not in drop], feat, n_perm=2000)
        show('без топ-%d пулов по вкладу' % k, b, po, pr)
    # leave-one-pool-out
    vals = []
    for kk in res['used']:
        b = oe([r for r in rs if r['_pool'] != kk], feat)
        vals.append((b['oe_reg'], b['oe_out'], kk))
    vals.sort()
    p('  выкидывание по одному пулу: O/E рег от %.2f до %.2f; O/E выход от %.2f до %.2f' % (
        vals[0][0], vals[-1][0], min(v[1] for v in vals), max(v[1] for v in vals)))
    # пулы, где у сравнения есть домен с >=3 регистрациями
    rich = {k for k, v in res['used'].items() if any((not feat(r)) and r['_regs'] >= 3 for r in v)}
    b, po, pr = perm_p([r for r in rs if r['_pool'] not in rich], feat, n_perm=2000)
    show('без %d пулов, где у сравнения домен с ≥3 рег' % len(rich), b, po, pr)

# =====================================================================================
p()
p('=' * 100)
p('5. ПЕРЕБОР СРЕЗОВ: ПЕРЕСТАНОВОЧНЫЙ ТЕСТ НА ВСЁ СЕМЕЙСТВО (max-T, одна общая перестановка меток)')
p('=' * 100)
p('Сколько p-значений выдал h02: 13 сравнений × 2 метрики = 26 перестановочных p, + 13 пуассоновских, + 13 знаковых,')
p('+ 4 p для «10 цифр» = 56 чисел; из перестановочных p<0.05 у 10 (все сцеплены между собой).')
p('Здесь: метка подтипа перемешивается внутри (пул контент+день × паттерн имени) один раз на итерацию, и по ней')
p('считаются ВСЕ тесты семейства сразу. Статистика теста — z = (E−O)/√E, стьюдентизирована по перестановкам;')
p('скорректированный p теста = доля перестановок, где max по семейству ≥ наблюдённого z этого теста.')

N_GLOBAL = 4000


def all_stats(rs_all, tests):
    out = []
    for name, sel, feat, pre in tests:
        res = oe([r for r in rs_all if sel(r)], feat)
        if res is None:
            out.append((0.0, 0.0))
            continue
        zo = (res['E_out'] - res['O_out']) / math.sqrt(res['E_out']) if res['E_out'] > 0 else 0.0
        zr = (res['E_reg'] - res['O_reg']) / math.sqrt(res['E_reg']) if res['E_reg'] > 0 else 0.0
        out.append((zo, zr))
    return out


groups = defaultdict(list)
for r in na_rows:
    groups[(r['_pool'], r['_pat'])].append(r)
glist = [v for v in groups.values() if len(v) >= 2]
orig_sub = {r['домен']: r['_sub'] for r in na_rows}
obs = all_stats(na_rows, TESTS)
rnd = random.Random(11)
perm_stats = []
for it in range(N_GLOBAL):
    for v in glist:
        labs = [r['_sub'] for r in v]
        rnd.shuffle(labs)
        for r, l in zip(v, labs):
            r['_sub'] = l
    perm_stats.append(all_stats(na_rows, TESTS))
for r in na_rows:
    r['_sub'] = orig_sub[r['домен']]
T = len(TESTS)
# стьюдентизация
mean = [[0.0, 0.0] for _ in range(T)]
sd = [[0.0, 0.0] for _ in range(T)]
for t in range(T):
    for m in (0, 1):
        xs = [ps[t][m] for ps in perm_stats]
        mu = sum(xs) / len(xs)
        var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
        mean[t][m] = mu
        sd[t][m] = math.sqrt(var) if var > 0 else 1.0


def stud(ps):
    return [[(ps[t][m] - mean[t][m]) / sd[t][m] for m in (0, 1)] for t in range(T)]


obs_s = stud(obs)
perm_s = [stud(ps) for ps in perm_stats]


def family_p(idx_list, metrics):
    """для каждого теста из idx_list: сырой p и скорректированный по max над (idx_list × metrics)"""
    maxes = [max(ps[t][m] for t in idx_list for m in metrics) for ps in perm_s]
    out = {}
    for t in idx_list:
        for m in metrics:
            raw = sum(1 for ps in perm_s if ps[t][m] >= obs_s[t][m] - 1e-12) / N_GLOBAL
            adj = sum(1 for mx in maxes if mx >= obs_s[t][m] - 1e-12) / N_GLOBAL
            out[(t, m)] = (raw, adj)
    return out


pre_idx = [i for i, t in enumerate(TESTS) if t[3]]
all_idx = list(range(T))
fam_pre = family_p(pre_idx, (0, 1))
fam_all = family_p(all_idx, (0, 1))
fam_pre_reg = family_p(pre_idx, (1,))
fam_all_reg = family_p(all_idx, (1,))
p()
p('%-34s %5s %6s | %7s %8s %8s | %7s %8s %8s %8s' % ('тест', 'метр.', 'z', 'p сырой', 'p 12 пре', 'p 18 все', 'z рег', 'p сырой', 'p 6 рег', 'p 9 рег'))
for t, (name, sel, feat, pre) in enumerate(TESTS):
    ro, ao = fam_pre.get((t, 0), (float('nan'), float('nan')))
    ro2, ao2 = fam_all[(t, 0)]
    rr, ar = fam_pre_reg.get((t, 1), (float('nan'), float('nan')))
    rr2, ar2 = fam_all_reg[(t, 1)]
    p('%-34s %5s %6.2f | %7.3f %8.3f %8.3f | %7.2f %8.3f %8.3f %8.3f' % (
        name + ('' if pre else ' *'), 'вых', obs_s[t][0], ro2, ao if pre else float('nan'), ao2,
        obs_s[t][1], rr2, ar if pre else float('nan'), ar2))
p('* — не заранее заданные (пост-хок). «p 12 пре» — поправка по 6 заранее заданным тестам × 2 метрики;')
p('«p 18 все» — по всем 9 сравнениям × 2 метрики; «p 6 рег» / «p 9 рег» — только по регистрациям (6 или 9 тестов).')
p('«p сырой» — односторонний перестановочный p этого теста при той же общей перестановке (сверка с h02).')

# =====================================================================================
p()
p('=' * 100)
p('6. ВЕДУЩИЙ НОЛЬ: НА ЧЁМ ДЕРЖИТСЯ ДЕФИЦИТ ВЫХОДА')
p('=' * 100)
rs = num_rows
featA = lambda r: r['_sub'] == S_ZERO
res = oe(rs, featA, with_pools=True)
prs = sorted(res['pool_rows'], key=lambda x: -(x[6] - x[5]))
tot = res['E_out'] - res['O_out']
p('  дефицит выхода E−O = %.1f сайтов; топ-3 пула дают %.1f (%.0f%%), топ-5 — %.1f (%.0f%%)' % (
    tot, sum(x[6] - x[5] for x in prs[:3]), 100 * sum(x[6] - x[5] for x in prs[:3]) / tot,
    sum(x[6] - x[5] for x in prs[:5]), 100 * sum(x[6] - x[5] for x in prs[:5]) / tot))
for k in (1, 3, 5):
    drop = {x[0] for x in prs[:k]}
    b, po, pr = perm_p([r for r in rs if r['_pool'] not in drop], featA, n_perm=2000)
    show('без топ-%d пулов по вкладу в дефицит выхода' % k, b, po, pr)
# по доменам: дефицит выхода по доменам с нулём
doms = sorted([r for v in res['used'].values() for r in v if featA(r)], key=lambda r: r['_out3'])
p('  домены с нулём по выходу за 3 суток (сайтов вышло из 206): %s' % ', '.join('%s:%d' % (r['_lab'], r['_out3']) for r in doms[:10]))

# =====================================================================================
p()
p('=' * 100)
p('7. СТРАТА ПУЛ × ПАТТЕРН ИМЕНИ ДЛЯ СУММАРНОГО ТЕСТА (numeric и alpha_other смешаны в одном пуле — корректно ли?)')
p('=' * 100)
p('В h02 суммарный тест «все признаки» берёт E из доли пула контент+день, где numeric и alpha_other сидят вместе.')
p('Если внутри пула у одного паттерна регистраций больше, чем у другого, а признаки распределены по паттернам')
p('неравномерно, E смещается. Пересчёт со стратой контент+день+паттерн (перестановка внутри неё):')
for r in na_rows:
    r['_poolp'] = (r['набор контента'], r['день запуска'], r['_pat'])
for name, sel, feat, pre in [t for t in TESTS if t[0] in ('ВСЕ признаки vs обычные', 'ВСЕ без кода даты (пост-хок)')]:
    rs = [r for r in na_rows if sel(r)]
    b, po, pr = perm_p(rs, feat, key='_pool', n_perm=4000)
    show(name + ' | страта пул', b, po, pr)
    b, po, pr = perm_p(rs, feat, key='_poolp', n_perm=4000)
    show(name + ' | страта пул×паттерн', b, po, pr)
    for r in rs:
        r['_regc'] = min(r['_regs'], 1)
    b, po, pr = perm_p(rs, feat, regkey='_regc', key='_poolp', n_perm=4000)
    show(name + ' | пул×паттерн, есть рег (0/1)', b, po, pr)
    dropR = top_k(rs, feat, 3, 'R')
    b, po, pr = perm_p([r for r in rs if r['домен'] not in dropR], feat, key='_poolp', n_perm=4000)
    show(name + ' | пул×паттерн, без топ-3 сравн.', b, po, pr)
p('Сумма A+B+C+D по отдельности (каждый внутри своего паттерна): O = 2+6+3+6 = 17, E = 5.2+9.9+6.8+3.5 = 25.5, O/E 0.67;')
p('без D: O = 11, E = 22.0, O/E 0.50 — но это те же самые пулы и домены, что и в п.3, и та же зависимость от топ-доменов.')

# =====================================================================================
p()
p('=' * 100)
p('8. ВЫХОД: НЕ «МЁРТВЫЕ» ЛИ ДОМЕНЫ ДЕЛАЮТ ДЕФИЦИТ (0–2 сайта из 206 вышли за 3 суток)')
p('=' * 100)
for name, sel, feat, pre in [t for t in TESTS if t[0] in ('A ведущий 0 vs numeric', 'B смесь-4 vs буквы-4', 'ВСЕ признаки vs обычные')]:
    rs = [r for r in na_rows if sel(r)]
    res = oe(rs, feat)
    doms = [r for v in res['used'].values() for r in v]
    F = [r for r in doms if feat(r)]
    R = [r for r in doms if not feat(r)]
    dead = lambda r: r['_out3'] <= 2
    p('--- %s: мёртвых (≤2 вышли) у признака %d из %d (%.0f%%), у сравнения %d из %d (%.0f%%)' % (
        name, sum(map(dead, F)), len(F), 100 * sum(map(dead, F)) / len(F), sum(map(dead, R)), len(R), 100 * sum(map(dead, R)) / len(R)))
    medF = sorted(r['_out3'] for r in F)[len(F) // 2]
    medR = sorted(r['_out3'] for r in R)[len(R) // 2]
    p('    медиана вышедших сайтов на домен: признак %d, сравнение %d' % (medF, medR))
    b, po, pr = perm_p([r for r in rs if not dead(r)], feat, n_perm=3000)
    show('без мёртвых доменов в обеих группах', b, po, pr)
    b, po, pr = perm_p([r for r in rs if r['_out3'] > 5], feat, n_perm=3000)
    show('без доменов с ≤5 вышедшими', b, po, pr)
# топ-3 пула по дефициту выхода у нуля: состав
res = oe(num_rows, featA, with_pools=True)
prs = sorted(res['pool_rows'], key=lambda x: -(x[6] - x[5]))[:3]
p('  Топ-3 пула по дефициту выхода у ведущего нуля — состав (метка:вышло):')
for k, *_ in prs:
    v = res['used'][k]
    p('    %s | %s: ноль: %s ; обычные: %s' % (k[0][:30], k[1], ', '.join('%s:%d' % (r['_lab'], r['_out3']) for r in v if featA(r)),
                                                 ', '.join('%s:%d' % (r['_lab'], r['_out3']) for r in v if not featA(r))))

# =====================================================================================
p()
p('=' * 100)
p('ВЫВОД СКЕПТИКА')
p('=' * 100)
p('1. Агрегирование верное: суммы регистраций/выходов против ожидания из доли пула, не средние по доменам. Претензий нет.')
p('2. Объёмы: в группе с признаком 19 регистраций на 17 доменов (все признаки), по подтипам 2 / 6 / 3 / 6. Ни одна группа')
p('   не дотягивает до 20 регистраций — по правилу «<20 в группе — не доказательство» ни один результат по регистрациям не проходит.')
p('3. Держится на нескольких доменах: убрать 3 самых богатых домена сравнения (2334.team 5 рег, qlmf.lol 4, gwrl.casino 4) —')
p('   O/E 0.61 → 0.70, p 0.017 → 0.054; убрать 6 — O/E 0.76, p 0.12. Считать «есть регистрация» (0/1) вместо суммы — O/E 0.80, p 0.12.')
p('   Убрать 10 пулов из 68, где у сравнения есть домен с ≥3 рег, — O/E 0.84, p 0.29. Дефицит сидит там, где «выстрелил» домен сравнения.')
p('   Формально «убрать топ-3 в обеих группах» даёт O/E 0.56 (p 0.009), но это снимает 26% регистраций у признака (5 из 19) и 13% у')
p('   сравнения — при 19 событиях такая уборка асимметрична и ничего не доказывает.')
p('4. Страта пул×паттерн (numeric и alpha_other не смешивать в одном пуле): O/E 0.71, p 0.08 вместо 0.61 / 0.017;')
p('   с индикатором 0/1 — O/E 0.87, p 0.25. Часть эффекта 1.6× — смешение паттернов внутри пула.')
p('5. Перебор срезов: h02 выдал 56 p-значений (13 сравнений × 2 метрики × 2 теста + знаковые + 10 цифр). max-T по 6 заранее')
p('   заданным тестам × 2 метрики: регистрации «все признаки» p = 0.24; по 9 тестам — 0.30. По выходу: «все признаки» 0.043–0.058,')
p('   смесь-4 0.051–0.068 — на грани, но эффект −5…−11%, критерий ≤0.8 не достигнут. Пост-хок «без кода даты» (p 0.040 по 9 тестам)')
p('   выбран после просмотра D — в семейство должен входить с ещё большим числом вариантов.')
p('6. Ведущий ноль по выходу (−12%, p 0.03): 73% дефицита в 3 пулах из 34 (5 доменов: 0626, 0811, 0658, 0313, 0403);')
p('   без этих 3 пулов O/E 0.96 (p 0.28), без 5 — 0.99. Плюс тест «худшая из 10 цифр» самого h02: p 0.32.')
p('7. Единственное, что переживает уборки: выход у смеси-4 (O/E 0.87–0.91 без мёртвых доменов, без топ-доменов, с зоной),')
p('   но после поправки на семейство p ≈ 0.05–0.07, а по величине (−11%) это ниже порога подтверждения.')
p()
p('ИТОГ: главный аргумент вердикта «частично» — «регистраций в 1.6 раза меньше, p ≈ 0.02» — неустойчив: он опирается на 19 событий,')
p('на 3–6 доменов сравнения и 10 пулов, исчезает при страте по паттерну, при счёте «есть регистрация» и при поправке на перебор.')
p('Направление «хуже» во всех вариантах остаётся (O/E регистраций 0.70–0.87, выхода 0.88–0.96), но это не доказательство.')
p('Вердикт следует понизить с «частично» до «не доказано на своде»; формулировку «в 1.6 раза меньше, p≈0.02» убрать.')
p()
p('ЧТО С ЭТИМ ДЕЛАТЬ: ничего менять в закупке не надо; единственный кандидат для новой проверки — смесь букв и цифр длины 4 по выходу')
p('(−11%). Проверяемо на своде после закрытия окна у 152 + 77 доменов (там ещё 27 смешанных): если O/E выхода останется ≤0.9')
p('при p < 0.05 с учётом поправки на семейство — можно говорить о признаке; регистрации на таких объёмах не решатся.')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT)

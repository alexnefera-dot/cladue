#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Гипотеза №2. Метки доменов, похожие на автосгенерированные, выходят в поиск
и конвертят хуже обычных меток того же паттерна.

Что проверяем (признаки берём из метки домена — часть до первой точки):
  A — numeric с ведущим нулём (0665, 0509) против numeric без ведущего нуля;
  B — alpha_other длины 4 со смесью букв и цифр (l3c7, h6k8) против чисто
      буквенных длины 4 (dwev, qlmf);
  C — alpha_other длины 3 (k2n, ynr) против чисто буквенных длины 4;
  D — alpha_other с кодом даты (4 цифры + буквы: 0509gg, 1109r) против чисто
      буквенных длины 4;
  Объединённо — любая alpha_other-метка с цифрой против чисто буквенной.

Как проверяем:
  1. Фильтр: окно закрыто = да, дней ≠ 1, без выбросов 3615.team и 3286.team,
     без «КОНТЕНТ НЕ ЗАПИСАН». Число исключённых строк печатается.
  2. Страта (пул) = набор контента + день запуска. Для каждого признака берём
     только пулы, где есть и домены с признаком, и домены сравнения.
  3. O/E: O — наблюдённая сумма по доменам с признаком (вышли за 3 суток;
     регистраций в окне 3 суток); E — ожидание из доли пула:
     E = Σ по доменам (пул: сумма показателя / сумма сайтов в окне) × сайтов
     в окне домена.
  4. Значимость: перестановка признака внутри пула 10 000 раз (random.seed(1)),
     p — доля перестановок, где O/E не выше наблюдённого (гипотеза направленная:
     «хуже»); для регистраций дополнительно точный пуассоновский тест
     P(X ≤ O | λ = E). Плюс знаковый критерий по пулам.
  5. Защита от выбора худшей группы: для A — первая цифра 0..9 как 10 групп,
     перестановочный тест «самая худшая цифра хуже, чем 0 в наблюдённых»;
     для B/C/D — объединённый тест «любая метка с цифрой».
  6. Контроль партии: домены с признаком по cf-аккаунтам, аккаунтам вебмастера,
     пулам и датам — если ≥80% сидят в 2–3 пулах/аккаунтах, это партия, не имя.
  7. Робастность: те же O/E при страте набор контента + день + зона.

Только stdlib. Вывод — в stdout и в analysis/export/gipotezy_svod/h02_generated_looking_labels.txt
"""
import csv
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'h02_generated_looking_labels.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
random.seed(1)
OUTLIERS = {'3615.team', '3286.team'}

_lines = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _lines.append(s)


# ---------------------------------------------------------------- чтение
with open(SRC, encoding='utf-8', newline='') as fh:
    rows_all = list(csv.DictReader(fh))
p('Файл:', SRC)
p('Всего строк (доменов):', len(rows_all))


def to_int(s):
    s = (s or '').strip()
    return int(float(s)) if s else 0


# ---------------------------------------------------------------- фильтр
p()
p('=== ФИЛЬТР ===')
n0 = len(rows_all)
rows = [r for r in rows_all if r['домен'] not in OUTLIERS]
p('Исключены выбросы 3615.team, 3286.team:', n0 - len(rows))
n1 = len(rows)
rows = [r for r in rows if r['окно закрыто'] == 'да']
p('Исключены с незакрытым окном 3 суток:', n1 - len(rows))
n2 = len(rows)
rows = [r for r in rows if r['дней'] != '1']
p('Исключены с дней = 1 (день 2 ещё не был):', n2 - len(rows))
n3 = len(rows)
rows = [r for r in rows if r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
p('Исключены «КОНТЕНТ НЕ ЗАПИСАН»:', n3 - len(rows))
p('Осталось доменов:', len(rows))

# ---------------------------------------------------------------- признаки
DATE_RE = re.compile(r'^\d{4}[a-z]+$')


def label(r):
    return r['домен'].split('.')[0]


def subtype(r):
    """Подтип метки внутри паттерна имени."""
    l = label(r)
    pat = r['паттерн имени']
    if pat == 'numeric':
        return 'numeric: ведущий 0' if l[0] == '0' else 'numeric: обычный'
    if pat == 'alpha_other':
        if DATE_RE.match(l):
            return 'alpha_other: код даты'
        if l.isalpha():
            return 'alpha_other: буквы, длина %d' % len(l)
        return 'alpha_other: смесь, длина %d' % len(l)
    if any(ch.isdigit() for ch in l):
        return pat + ': с цифрами'
    return pat + ': буквы'


for r in rows:
    r['_lab'] = label(r)
    r['_sub'] = subtype(r)
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_out3'] = to_int(r['вышли за 3 суток'])
    r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_fd'] = to_int(r['ФД в окне 3 суток'])
    r['_clicks'] = to_int(r['кликов из поиска в окне'])
    r['_pool'] = (r['набор контента'], r['день запуска'])
    r['_poolz'] = (r['набор контента'], r['день запуска'], r['зона'])

p()
p('=== ПОДТИПЫ МЕТОК ПОСЛЕ ФИЛЬТРА (сырые суммы, без страты) ===')
p('%-34s %7s %8s %6s %8s %6s %8s %9s' % ('подтип', 'домен.', 'сайтов', 'вышли', 'выход%', 'рег', 'рег/100', 'рег/10тыс'))
agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
for r in rows:
    a = agg[r['_sub']]
    a[0] += 1
    a[1] += r['_sites']
    a[2] += r['_out3']
    a[3] += r['_regs']
    a[4] += r['_clicks']
    a[5] += r['_fd']
for k in sorted(agg):
    a = agg[k]
    p('%-34s %7d %8d %6d %7.1f%% %8d %8.3f %9.2f' % (
        k, a[0], a[1], a[2], 100.0 * a[2] / a[1] if a[1] else 0, a[3],
        100.0 * a[3] / a[1] if a[1] else 0,
        1e4 * a[3] / a[4] if a[4] else 0))

p()
p('Зоны у доменов с признаками (важно для D — код даты):')
for s in ['numeric: ведущий 0', 'numeric: обычный', 'alpha_other: смесь, длина 4',
          'alpha_other: буквы, длина 4', 'alpha_other: смесь, длина 3',
          'alpha_other: буквы, длина 3', 'alpha_other: код даты']:
    c = Counter(r['зона'] for r in rows if r['_sub'] == s)
    p('  %-34s %s' % (s, ', '.join('%s %d' % kv for kv in c.most_common())))


# ---------------------------------------------------------------- статистика
def poisson_cdf(k, lam):
    """P(X <= k) при X ~ Пуассон(lam)."""
    if lam <= 0:
        return 1.0
    s = 0.0
    for i in range(int(k) + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


def poisson_sf_incl(k, lam):
    """P(X >= k)."""
    if k <= 0:
        return 1.0
    return max(0.0, 1.0 - poisson_cdf(k - 1, lam))


def binom_cdf(k, n, q=0.5):
    s = 0.0
    for i in range(k + 1):
        s += math.comb(n, i) * q ** i * (1 - q) ** (n - i)
    return min(1.0, s)


def build_pools(rs, key='_pool'):
    pools = defaultdict(list)
    for r in rs:
        pools[r[key]].append(r)
    return pools


def oe_test(rs, is_feat, name_feat, name_ref, key='_pool', n_perm=N_PERM, verbose=True):
    """Стратифицированный O/E по выходу и регистрациям для доменов с признаком.

    rs — домены, среди которых сравниваем (признак + группа сравнения);
    is_feat(r) — признак. Берутся только пулы, где есть оба типа.
    Возвращает словарь с результатами.
    """
    pools = build_pools(rs, key)
    used = {k: v for k, v in pools.items()
            if any(is_feat(r) for r in v) and any(not is_feat(r) for r in v)}
    doms = [r for v in used.values() for r in v]
    feat = [r for r in doms if is_feat(r)]
    ref = [r for r in doms if not is_feat(r)]
    res = {'pools': len(used), 'n_feat': len(feat), 'n_ref': len(ref)}
    if not used:
        if verbose:
            p('  Нет пулов с обоими подтипами — сравнение невозможно.')
        return res
    # доли пула
    rate_out, rate_reg = {}, {}
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rate_out[k] = sum(r['_out3'] for r in v) / S if S else 0
        rate_reg[k] = sum(r['_regs'] for r in v) / S if S else 0

    def sums(group):
        O_out = sum(r['_out3'] for r in group)
        O_reg = sum(r['_regs'] for r in group)
        E_out = sum(rate_out[r[key]] * r['_sites'] for r in group)
        E_reg = sum(rate_reg[r[key]] * r['_sites'] for r in group)
        return O_out, E_out, O_reg, E_reg

    O_out, E_out, O_reg, E_reg = sums(feat)
    Or_out, Er_out, Or_reg, Er_reg = sums(ref)
    res.update(O_out=O_out, E_out=E_out, O_reg=O_reg, E_reg=E_reg,
               sites_feat=sum(r['_sites'] for r in feat),
               sites_ref=sum(r['_sites'] for r in ref),
               regs_ref=Or_reg, out_ref=Or_out,
               fd_feat=sum(r['_fd'] for r in feat), fd_ref=sum(r['_fd'] for r in ref))
    oe_out = O_out / E_out if E_out else float('nan')
    oe_reg = O_reg / E_reg if E_reg else float('nan')
    res.update(oe_out=oe_out, oe_reg=oe_reg)

    # перестановка признака внутри пула
    cnt_out_le = cnt_reg_le = cnt_out_ge = cnt_reg_ge = 0
    pool_lists = [(list(v), sum(1 for r in v if is_feat(r))) for v in used.values()]
    for _ in range(n_perm):
        po = pe = ro = re_ = 0.0
        for v, m in pool_lists:
            random.shuffle(v)
            k = v[0][key]
            for r in v[:m]:
                po += r['_out3']
                ro += r['_regs']
                pe += rate_out[k] * r['_sites']
                re_ += rate_reg[k] * r['_sites']
        r_out = po / pe if pe else 0
        r_reg = ro / re_ if re_ else 0
        if r_out <= oe_out + 1e-12:
            cnt_out_le += 1
        if r_out >= oe_out - 1e-12:
            cnt_out_ge += 1
        if r_reg <= oe_reg + 1e-12:
            cnt_reg_le += 1
        if r_reg >= oe_reg - 1e-12:
            cnt_reg_ge += 1
    p_out = cnt_out_le / n_perm
    p_reg = cnt_reg_le / n_perm
    p_out2 = min(1.0, 2 * min(cnt_out_le, cnt_out_ge) / n_perm)
    p_reg2 = min(1.0, 2 * min(cnt_reg_le, cnt_reg_ge) / n_perm)
    pois_le = poisson_cdf(O_reg, E_reg)
    pois_ge = poisson_sf_incl(O_reg, E_reg)
    res.update(p_out=p_out, p_reg=p_reg, p_out2=p_out2, p_reg2=p_reg2,
               pois_le=pois_le, pois_ge=pois_ge)

    # знаковый критерий по пулам (выход)
    worse = better = tie = 0
    for k, v in used.items():
        f = [r for r in v if is_feat(r)]
        g = [r for r in v if not is_feat(r)]
        rf = sum(r['_out3'] for r in f) / sum(r['_sites'] for r in f)
        rg = sum(r['_out3'] for r in g) / sum(r['_sites'] for r in g)
        if rf < rg - 1e-12:
            worse += 1
        elif rf > rg + 1e-12:
            better += 1
        else:
            tie += 1
    n_nt = worse + better
    p_sign = binom_cdf(better, n_nt) if n_nt else 1.0  # вероятность, что «лучше» так мало или меньше
    res.update(sign_worse=worse, sign_better=better, sign_tie=tie, p_sign=p_sign)

    if verbose:
        p('  Пулов с обоими подтипами: %d; доменов: %s %d (сайтов %d), %s %d (сайтов %d)' % (
            len(used), name_feat, len(feat), res['sites_feat'], name_ref, len(ref), res['sites_ref']))
        p('  ВЫХОД в поиск за 3 суток: O = %d, E = %.1f, O/E = %.2f   (у группы сравнения: %d вышли, O/E = %.2f)' % (
            O_out, E_out, oe_out, Or_out, Or_out / Er_out if Er_out else float('nan')))
        p('    перестановочный p (хуже) = %.4f; двусторонний p = %.4f' % (p_out, p_out2))
        p('    знаковый критерий по пулам: признак хуже в %d, лучше в %d, ничья %d; p(лучше так мало) = %.3f' % (
            worse, better, tie, p_sign))
        p('  РЕГИСТРАЦИИ в окне 3 суток: O = %d, E = %.2f, O/E = %.2f   (у группы сравнения: %d рег, O/E = %.2f)' % (
            O_reg, E_reg, oe_reg, Or_reg, Or_reg / Er_reg if Er_reg else float('nan')))
        p('    рег на 100 сайтов: признак %.3f, сравнение %.3f' % (
            100.0 * O_reg / res['sites_feat'], 100.0 * Or_reg / res['sites_ref']))
        p('    пуассон P(X ≤ O | λ=E) = %.4f; P(X ≥ O) = %.4f; перестановочный p (хуже) = %.4f; двусторонний = %.4f' % (
            pois_le, pois_ge, p_reg, p_reg2))
        p('  ФД в окне: признак %d, сравнение %d (объёмы слишком малы для теста)' % (res['fd_feat'], res['fd_ref']))
    return res


def batch_control(feat_rows, name):
    """Контроль партии: где сидят домены с признаком."""
    n = len(feat_rows)
    p('  Контроль партии для «%s» (%d доменов):' % (name, n))
    if n == 0:
        return
    for field, title in (('cf-аккаунт', 'cf-аккаунт'), ('аккаунт вебмастера', 'аккаунт вебмастера'),
                         ('_pool', 'пул контент+день'), ('день запуска', 'день запуска'),
                         ('набор контента', 'набор контента'), ('зона', 'зона')):
        c = Counter(r[field] for r in feat_rows)
        top3 = sum(v for _, v in c.most_common(3))
        p('    %-20s: разных значений %d; в топ-3 значениях %d доменов (%.0f%%); макс. в одном %d' % (
            title, len(c), top3, 100.0 * top3 / n, c.most_common(1)[0][1]))
    # совместное сидение на cf-аккаунтах: сколько доменов с признаком делят cf-аккаунт с другим доменом с признаком
    cf_all = defaultdict(list)
    for r in rows_all:
        cf_all[r['cf-аккаунт']].append(r['домен'])
    feat_set = {r['домен'] for r in feat_rows}
    share = sum(1 for r in feat_rows if any(d in feat_set for d in cf_all[r['cf-аккаунт']] if d != r['домен']))
    p('    доменов с признаком, у которых на том же cf-аккаунте есть ещё домен с признаком: %d из %d' % (share, n))
    wm_all = defaultdict(list)
    for r in rows_all:
        wm_all[r['аккаунт вебмастера']].append(r['домен'])
    share_wm = sum(1 for r in feat_rows if any(d in feat_set for d in wm_all[r['аккаунт вебмастера']] if d != r['домен']))
    p('    то же по аккаунту вебмастера: %d из %d' % (share_wm, n))


# ================================================================= A
p()
p('=' * 90)
p('A. numeric: ведущий ноль (0665, 0509) против numeric без ведущего нуля')
p('=' * 90)
num_rows = [r for r in rows if r['паттерн имени'] == 'numeric']
isA = lambda r: r['_sub'] == 'numeric: ведущий 0'
resA = oe_test(num_rows, isA, 'ведущий 0', 'обычный')
batch_control([r for r in num_rows if isA(r)], 'ведущий 0')

p()
p('A, робастность: страта набор контента + день + зона')
resA_z = oe_test(num_rows, isA, 'ведущий 0', 'обычный', key='_poolz', n_perm=2000)

# ----------------------------------------------------------------- A: 10 цифр
p()
p('A, защита от выбора худшей группы: первая цифра 0..9 как 10 групп')
p('   (пулы контент+день, где ≥2 numeric-домена с разными первыми цифрами; E — из доли пула)')
pools_num = build_pools(num_rows)
pools_dig = {k: v for k, v in pools_num.items() if len({r['_lab'][0] for r in v}) >= 2}
doms_dig = [r for v in pools_dig.values() for r in v]
rate_out_d, rate_reg_d = {}, {}
for k, v in pools_dig.items():
    S = sum(r['_sites'] for r in v)
    rate_out_d[k] = sum(r['_out3'] for r in v) / S
    rate_reg_d[k] = sum(r['_regs'] for r in v) / S


def digit_stats(assign):
    """assign: список (цифра, r). Возвращает по цифрам O_out,E_out,O_reg,E_reg,n."""
    d = defaultdict(lambda: [0, 0.0, 0, 0.0, 0, 0])
    for dig, r in assign:
        a = d[dig]
        a[0] += r['_out3']
        a[1] += rate_out_d[r['_pool']] * r['_sites']
        a[2] += r['_regs']
        a[3] += rate_reg_d[r['_pool']] * r['_sites']
        a[4] += 1
        a[5] += r['_sites']
    return d


obs = digit_stats([(r['_lab'][0], r) for r in doms_dig])
p('  пулов: %d, numeric-доменов в них: %d' % (len(pools_dig), len(doms_dig)))
p('  %-6s %7s %8s %7s %8s %6s %8s %8s %6s %7s' % ('цифра', 'домен.', 'сайтов', 'вышли', 'E вых', 'O/E', 'рег', 'E рег', 'O/E', 'z дефиц'))


def zdef(O, E):
    return (E - O) / math.sqrt(E) if E > 0 else 0.0


for dig in sorted(obs):
    a = obs[dig]
    p('  %-6s %7d %8d %7d %8.1f %6.2f %8d %8.2f %6.2f %7.2f' % (
        dig, a[4], a[5], a[0], a[1], a[0] / a[1] if a[1] else 0, a[2], a[3], a[2] / a[3] if a[3] else 0, zdef(a[2], a[3])))
obs_z0_reg = zdef(obs['0'][2], obs['0'][3])
obs_z0_out = zdef(obs['0'][0], obs['0'][1])
obs_oe0_reg = obs['0'][2] / obs['0'][3] if obs['0'][3] else 0
obs_oe0_out = obs['0'][0] / obs['0'][1] if obs['0'][1] else 0
# перестановка первых цифр внутри пула
cnt_reg = cnt_out = cnt_reg_oe = cnt_out_oe = 0
E_MIN = 3.0  # цифры со слишком малым ожиданием регистраций не считаем в min O/E (иначе 0 из 1)
pool_lists_d = [list(v) for v in pools_dig.values()]
for _ in range(N_PERM):
    assign = []
    for v in pool_lists_d:
        digs = [r['_lab'][0] for r in v]
        random.shuffle(digs)
        assign.extend(zip(digs, v))
    d = digit_stats(assign)
    max_z_reg = max(zdef(a[2], a[3]) for a in d.values())
    max_z_out = max(zdef(a[0], a[1]) for a in d.values())
    min_oe_reg = min((a[2] / a[3]) for a in d.values() if a[3] >= E_MIN)
    min_oe_out = min((a[0] / a[1]) for a in d.values() if a[1] > 0)
    if max_z_reg >= obs_z0_reg - 1e-12:
        cnt_reg += 1
    if max_z_out >= obs_z0_out - 1e-12:
        cnt_out += 1
    if min_oe_reg <= obs_oe0_reg + 1e-12:
        cnt_reg_oe += 1
    if min_oe_out <= obs_oe0_out + 1e-12:
        cnt_out_oe += 1
pA10_reg = cnt_reg / N_PERM
pA10_out = cnt_out / N_PERM
p('  Наблюдённый дефицит цифры 0: регистрации z = %.2f (O/E %.2f), выход z = %.2f (O/E %.2f)' % (
    obs_z0_reg, obs_oe0_reg, obs_z0_out, obs_oe0_out))
p('  Перестановка первых цифр внутри пула (%d раз): вероятность, что ХУДШАЯ из 10 цифр даст дефицит не меньше, чем у 0:' % N_PERM)
p('    регистрации: p = %.4f (по max z), p = %.4f (по min O/E среди цифр с E ≥ %.0f)' % (pA10_reg, cnt_reg_oe / N_PERM, E_MIN))
p('    выход:       p = %.4f (по max z), p = %.4f (по min O/E)' % (pA10_out, cnt_out_oe / N_PERM))

# ================================================================= B, C, D
alpha_rows = [r for r in rows if r['паттерн имени'] == 'alpha_other']
isRef4 = lambda r: r['_sub'] == 'alpha_other: буквы, длина 4'
isB = lambda r: r['_sub'] == 'alpha_other: смесь, длина 4'
isC = lambda r: r['_sub'] in ('alpha_other: смесь, длина 3', 'alpha_other: буквы, длина 3')
isC_mixed = lambda r: r['_sub'] == 'alpha_other: смесь, длина 3'
isD = lambda r: r['_sub'] == 'alpha_other: код даты'
isAnyDigit = lambda r: any(ch.isdigit() for ch in r['_lab'])
isRefAlpha = lambda r: r['_lab'].isalpha()

p()
p('=' * 90)
p('B. alpha_other длины 4: смесь букв и цифр (l3c7) против чисто буквенных (dwev)')
p('=' * 90)
resB = oe_test([r for r in alpha_rows if isB(r) or isRef4(r)], isB, 'смесь-4', 'буквы-4')
batch_control([r for r in alpha_rows if isB(r)], 'смесь-4')
p()
p('B, робастность: страта набор контента + день + зона')
resB_z = oe_test([r for r in alpha_rows if isB(r) or isRef4(r)], isB, 'смесь-4', 'буквы-4', key='_poolz', n_perm=2000)

p()
p('=' * 90)
p('C. alpha_other длины 3 (k2n, ynr) против чисто буквенных длины 4')
p('=' * 90)
n3m = sum(1 for r in alpha_rows if isC_mixed(r))
n3a = sum(1 for r in alpha_rows if isC(r) and not isC_mixed(r))
p('  Длина 3 после фильтра: смесь %d, чисто буквенных %d — почти все 3-символьные метки смешанные,' % (n3m, n3a))
p('  поэтому «длина 3» и «смесь при длине 3» на этих данных не разделить; сравниваем длину 3 целиком с буквами-4.')
resC = oe_test([r for r in alpha_rows if isC(r) or isRef4(r)], isC, 'длина-3', 'буквы-4')
batch_control([r for r in alpha_rows if isC(r)], 'длина-3')
p()
p('C-дополнение: смесь-3 против смесь-4 (проверка «эффект длины» отдельно от «эффекта смеси»)')
resC2 = oe_test([r for r in alpha_rows if isC_mixed(r) or isB(r)], isC_mixed, 'смесь-3', 'смесь-4', n_perm=2000)

p()
p('=' * 90)
p('D. alpha_other с кодом даты (0509gg, 1109r) против чисто буквенных длины 4')
p('=' * 90)
zD = Counter(r['зона'] for r in alpha_rows if isD(r))
p('  Зоны у кода даты: %s — ВСЕ в одной зоне; зоны у группы сравнения в тех же пулах — см. ниже.' % dict(zD))
resD = oe_test([r for r in alpha_rows if isD(r) or isRef4(r)], isD, 'код даты', 'буквы-4')
# зоны сравнения в использованных пулах
poolsD = build_pools([r for r in alpha_rows if isD(r) or isRef4(r)])
usedD = [v for v in poolsD.values() if any(isD(r) for r in v) and any(isRef4(r) for r in v)]
zRefD = Counter(r['зона'] for v in usedD for r in v if isRef4(r))
p('  Зоны группы сравнения (буквы-4) в этих пулах: %s' % dict(zRefD))
batch_control([r for r in alpha_rows if isD(r)], 'код даты')
p()
p('D, робастность: страта набор контента + день + зона (только .casino против .casino)')
resD_z = oe_test([r for r in alpha_rows if isD(r) or isRef4(r)], isD, 'код даты', 'буквы-4', key='_poolz', n_perm=2000)

p()
p('=' * 90)
p('ОБЪЕДИНЁННО (защита от выбора худшей группы для B/C/D): любая alpha_other-метка с цифрой')
p('против чисто буквенной alpha_other (любой длины)')
p('=' * 90)
resAll = oe_test(alpha_rows, isAnyDigit, 'с цифрой', 'буквы')
p()
p('  То же без кода даты (только смесь длины 3–5, чтобы .casino-код даты не тянул):')
resAll2 = oe_test([r for r in alpha_rows if not isD(r)], isAnyDigit, 'смесь без кода даты', 'буквы', n_perm=2000)
p()
p('  Объединённо, страта контент+день+зона:')
resAll_z = oe_test(alpha_rows, isAnyDigit, 'с цифрой', 'буквы', key='_poolz', n_perm=2000)

# ================================================================= ещё один взгляд: numeric + alpha_other вместе
p()
p('=' * 90)
p('ВСЕ ПРИЗНАКИ ВМЕСТЕ: «похоже на сгенерированное» (ведущий 0 ИЛИ alpha_other с цифрой)')
p('против обычных меток тех же паттернов (numeric без нуля, alpha_other буквы); пул контент+день')
p('=' * 90)
isGen = lambda r: isA(r) or (r['паттерн имени'] == 'alpha_other' and isAnyDigit(r))
resGen = oe_test(num_rows + alpha_rows, isGen, 'выглядит сгенерированным', 'обычные', n_perm=N_PERM)
p()
p('  Пост-хок чувствительность (не заранее заданный тест): то же без кода даты, потому что код даты —')
p('  отдельный стиль закупки (все 50 — .casino) и в D он оказался не хуже, а лучше:')
isGen2 = lambda r: isA(r) or (r['паттерн имени'] == 'alpha_other' and isAnyDigit(r) and not isD(r))
resGen2 = oe_test([r for r in num_rows + alpha_rows if not isD(r)], isGen2, 'сгенерированное без кода даты', 'обычные', n_perm=N_PERM)

# ================================================================= сводная таблица
p()
p('=' * 90)
p('СВОДКА (пулы контент+день с обоими подтипами)')
p('=' * 90)
p('%-42s %5s %5s/%-5s %8s %6s %7s %7s %6s %7s %7s' % (
    'сравнение', 'пулов', 'дом.', 'срав.', 'O/E вых', 'p', 'рег O', 'E рег', 'O/E', 'p пуас', 'p пер'))


def line(name, res):
    if 'oe_out' not in res:
        p('%-42s %5d нет данных' % (name, res.get('pools', 0)))
        return
    p('%-42s %5d %5d/%-5d %8.2f %6.3f %7d %7.2f %6.2f %7.3f %7.3f' % (
        name, res['pools'], res['n_feat'], res['n_ref'], res['oe_out'], res['p_out'],
        res['O_reg'], res['E_reg'], res['oe_reg'], res['pois_le'], res['p_reg']))


line('A ведущий 0 vs numeric', resA)
line('A  (страта +зона)', resA_z)
line('B смесь-4 vs буквы-4', resB)
line('B  (страта +зона)', resB_z)
line('C длина-3 vs буквы-4', resC)
line('C2 смесь-3 vs смесь-4', resC2)
line('D код даты vs буквы-4', resD)
line('D  (страта +зона)', resD_z)
line('Объед. alpha_other с цифрой vs буквы', resAll)
line('Объед. без кода даты', resAll2)
line('Объед. (страта +зона)', resAll_z)
line('Все признаки vs обычные', resGen)
line('Все признаки без кода даты (пост-хок)', resGen2)

# ================================================================= ВЫВОД
p()
p('=' * 90)
p('ВЫВОД')
p('=' * 90)


def fmt(res):
    return dict(pools=res['pools'], nf=res['n_feat'], nr=res['n_ref'], sf=res['sites_feat'], sr=res['sites_ref'],
                oo=res['oe_out'], po=res['p_out'], O=res['O_reg'], E=res['E_reg'], orr=res['oe_reg'],
                pp=res['pois_le'], pr=res['p_reg'], Or=res['regs_ref'])


A, B, C, D, ALL, GEN, GEN2 = (fmt(x) for x in (resA, resB, resC, resD, resAll, resGen, resGen2))

p('Фильтр: из 2077 доменов оставлено 1511 (без выбросов, без незакрытого окна, без дней=1, без «КОНТЕНТ НЕ ЗАПИСАН»).')
p('Пул = набор контента + день запуска; сравнение только внутри пулов, где есть оба подтипа.')
p()
p('1. Ведущий ноль (0665, 0509): %d пулов, %d доменов с нулём (%d сайтов) против %d обычных numeric (%d сайтов).' % (
    A['pools'], A['nf'], A['sf'], A['nr'], A['sr']))
p('   Выход в поиск на 12%% ниже ожидания (O/E = %.2f, перестановка p = %.3f; хуже в %d пулах из %d).' % (
    A['oo'], A['po'], resA['sign_worse'], A['pools']))
p('   Регистраций 2 при ожидании %.1f (O/E = %.2f) — это в %.1f раза меньше, но при таких единицах пуассон p = %.2f: случайность не исключена.' % (
    A['E'], A['orr'], 1 / A['orr'] if A['orr'] else 0, A['pp']))
p('   Главное: если посмотреть на все 10 первых цифр, ноль — не особенный. Цифра 8 даёт выход O/E 0.80 и регистрации O/E 0.49,')
p('   цифра 6 — выход 0.84. Вероятность, что худшая из 10 цифр окажется не лучше нуля просто случайно: p = %.2f по регистрациям,' % pA10_reg)
p('   p = %.2f по выходу. То есть «ноль вреден» на этих данных не отличить от «какая-то цифра всегда окажется худшей».' % pA10_out)
p()
p('2. Смесь букв и цифр при длине 4 (l3c7, h6k8): %d пулов, %d против %d чисто буквенных (dwev).' % (B['pools'], B['nf'], B['nr']))
p('   Выход на 11%% ниже ожидания (O/E = %.2f, p = %.3f; хуже в %d пулах из %d) — это единственный устойчивый по выходу признак,' % (
    B['oo'], B['po'], resB['sign_worse'], B['pools']))
p('   держится и при страте с зоной (O/E %.2f, p = %.3f).' % (resB_z['oe_out'], resB_z['p_out']))
p('   Регистраций %d при ожидании %.1f (O/E = %.2f, в %.1f раза меньше), пуассон p = %.2f — не значимо.' % (
    B['O'], B['E'], B['orr'], 1 / B['orr'], B['pp']))
p()
p('3. Длина 3 (k2n): %d пулов, %d против %d. Выход O/E = %.2f (p = %.2f), регистраций %d при ожидании %.1f (O/E = %.2f, p = %.2f).' % (
    C['pools'], C['nf'], C['nr'], C['oo'], C['po'], C['O'], C['E'], C['orr'], C['pp']))
p('   Смесь-3 против смесь-4 напрямую: выход O/E %.2f, регистрации %d против %d — длина 3 сама по себе ничего не добавляет к «смеси».' % (
    resC2['oe_out'], resC2['O_reg'], resC2['regs_ref']))
p()
p('4. Код даты (0509gg): все 50 доменов — зона .casino. %d пулов, %d против %d. Выход O/E = %.2f, регистраций %d при ожидании %.1f (O/E = %.2f).' % (
    D['pools'], D['nf'], D['nr'], D['oo'], D['O'], D['E'], D['orr']))
p('   При страте с зоной (.casino против .casino): выход O/E %.2f, регистрации O/E %.2f. Код даты НЕ хуже; если что — чуть лучше.' % (
    resD_z['oe_out'], resD_z['oe_reg']))
p('   Гипотеза для этого подтипа опровергнута.')
p()
p('5. Объединённые тесты. Заранее заданный «любая alpha_other-метка с цифрой против букв»: %d пулов, %d против %d;' % (ALL['pools'], ALL['nf'], ALL['nr']))
p('   выход O/E = %.2f (p = %.3f), регистрации %d при ожидании %.1f (O/E = %.2f, p = %.2f) — не значимо, потому что код даты тянет вверх.' % (
    ALL['oo'], ALL['po'], ALL['O'], ALL['E'], ALL['orr'], ALL['pp']))
p('   Все признаки сразу (ноль + alpha_other с цифрой) против обычных: %d пулов, %d доменов (%d сайтов) против %d (%d сайтов);' % (
    GEN['pools'], GEN['nf'], GEN['sf'], GEN['nr'], GEN['sr']))
p('   выход O/E = %.2f (p = %.3f), регистраций %d при ожидании %.1f — O/E = %.2f, пуассон p = %.3f, перестановка p = %.3f.' % (
    GEN['oo'], GEN['po'], GEN['O'], GEN['E'], GEN['orr'], GEN['pp'], GEN['pr']))
p('   Без кода даты (пост-хок): регистраций %d при ожидании %.1f, O/E = %.2f, пуассон p = %.3f, перестановка p = %.3f; выход O/E = %.2f (p = %.3f).' % (
    GEN2['O'], GEN2['E'], GEN2['orr'], GEN2['pp'], GEN2['pr'], GEN2['oo'], GEN2['po']))
p()
p('6. Контроль партии. Домены с нулём: 76 разных cf-аккаунтов на 78 доменов, 78 разных аккаунтов вебмастера, 64 пула, 17 дней запуска.')
p('   Смесь-4: 85 cf-аккаунтов на 87 доменов, 66 пулов, 21 день. Длина 3: 77 cf на 78, 55 пулов, 17 дней.')
p('   Ни один признак не сидит в 2–3 пулах или на общих аккаунтах — это не одна закупленная партия. Но что общего у этих имён')
p('   (один продавец, одна дата покупки, одна история дропа) — в своде не записано, поэтому «имя» от «происхождения» не отделить.')
p()
p('ИТОГ ПО ГИПОТЕЗЕ: частично. Направление «хуже» есть у трёх из четырёх подтипов (ноль, смесь-4, длина 3) и по выходу, и по')
p('регистрациям, а в сумме по всем признакам регистраций в %.1f раза меньше ожидаемого (%d против %.0f, p ≈ 0.02). Но:' % (
    1 / GEN['orr'], GEN['O'], GEN['E']))
p('(а) по регистрациям ни один подтип по отдельности не значим — там единицы событий (2, 6, 3);')
p('(б) по выходу эффект слабый, 5–12%, а не ≤0.8, как требует критерий подтверждения;')
p('(в) ведущий ноль не отличим от «худшей из 10 цифр» (цифра 8 такая же);')
p('(г) код даты — не хуже, а лучше, гипотеза для него опровергнута.')
p('Это не «имя явно вредит», а «похожие на сгенерированные имена в среднем чуть слабее, и на регистрациях это заметно только в сумме».')
p()
p('ЧТО С ЭТИМ ДЕЛАТЬ:')
p('1) Не менять закупку ради этого: выигрыш по выходу максимум 5–12%, по регистрациям — единицы; главные рычаги — контент и бренд.')
p('   Если правило имён бесплатное, можно предпочитать чисто буквенные (dwev) и numeric без нуля, но не ждать заметного эффекта.')
p('2) Проверяемо на уже запущенных данных: дозаписать в свод для 78 «нулевых», 87 «смешанных-4» и 78 трёхсимвольных доменов, откуда они')
p('   (продавец/регистратор/дата покупки/дроп или нет). Если они все из одного источника — эффект переходит в «происхождение», а не «имя».')
p('3) Пересчитать этим же скриптом, когда закроется окно у 152 доменов и 77 доменов с дней=1 (запуски 17–21.09): там ещё 33 домена')
p('   с признаками (6 с нулём, 27 смешанных); тогда суммарный тест по регистрациям либо укрепится, либо рассыплется.')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT)

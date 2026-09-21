#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №2 (метки, похожие на сгенерированные). Угол — ТЕНИ (конфаундинг).

Что делаем:
  1. Тот же фильтр и те же признаки, что в h02 (окно закрыто, дней≠1, без выбросов, без «КОНТЕНТ НЕ ЗАПИСАН»).
  2. Баланс ковариат внутри пулов контент+день: зона, паттерн имени, дней, шаблон, сайтов в окне,
     который раз аккаунт — у доменов с признаком против ожидания из состава пула.
  3. Более жёсткие страты для суммарного теста «все признаки против обычных»:
     контент+день, +зона, +паттерн, +зона+паттерн, +зона+паттерн+дней. O/E по регистрациям и выходу,
     перестановка внутри страты.
  4. Leave-one-pool-out: насколько результат держится на 1–2 пулах. Вклад пулов в дефицит E−O.
  5. Парные сравнения: знаковый критерий по пулам, где есть хоть одна регистрация.
  6. Кластерный бутстрэп по пулам — 95% интервал для O/E по регистрациям.
  7. Раздельно по зонам team / lol.
  8. Чувствительность: добавить «КОНТЕНТ НЕ ЗАПИСАН» как пул «не записан + день».
Только stdlib. Вывод: stdout и analysis/export/gipotezy_svod/v02_teni.txt
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
OUT = os.path.join(OUT_DIR, 'v02_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 5000
random.seed(7)
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

DATE_RE = re.compile(r'^\d{4}[a-z]+$')


def label(r):
    return r['домен'].split('.')[0]


def subtype(r):
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


for r in rows_all:
    r['_lab'] = label(r)
    r['_sub'] = subtype(r)
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_out3'] = to_int(r['вышли за 3 суток'])
    r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_fd'] = to_int(r['ФД в окне 3 суток'])
    r['_pat'] = r['паттерн имени']
    r['_zone'] = r['зона'] if r['зона'] in ('team', 'lol', 'casino', 'buzz') else 'прочие'

isA = lambda r: r['_sub'] == 'numeric: ведущий 0'
isD = lambda r: r['_sub'] == 'alpha_other: код даты'
isAnyDigit = lambda r: any(ch.isdigit() for ch in r['_lab'])
isGen = lambda r: isA(r) or (r['_pat'] == 'alpha_other' and isAnyDigit(r))
isGen2 = lambda r: isA(r) or (r['_pat'] == 'alpha_other' and isAnyDigit(r) and not isD(r))
inScope = lambda r: r['_pat'] in ('numeric', 'alpha_other')

# ------------------------------------------------------------------ фильтр как в h02
base = [r for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] != '1']
rows = [r for r in base if r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
p('Файл:', SRC)
p('Фильтр как в h02: без выбросов, окно закрыто, дней≠1 -> %d; без «КОНТЕНТ НЕ ЗАПИСАН» -> %d доменов' % (len(base), len(rows)))
scope = [r for r in rows if inScope(r)]
p('numeric + alpha_other после фильтра: %d доменов, из них «выглядит сгенерированным»: %d' % (
    len(scope), sum(1 for r in scope if isGen(r))))


# ------------------------------------------------------------------ статистика
def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = 0.0
    for i in range(int(k) + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


def binom_cdf(k, n, q=0.5):
    return min(1.0, sum(math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k + 1)))


def strat(rs, is_feat, keyf, n_perm=N_PERM, verbose=True, title=''):
    """O/E внутри страт keyf(r); только страты с обоими типами. Возвращает dict."""
    pools = defaultdict(list)
    for r in rs:
        pools[keyf(r)].append(r)
    used = {k: v for k, v in pools.items() if any(is_feat(r) for r in v) and any(not is_feat(r) for r in v)}
    doms = [r for v in used.values() for r in v]
    feat = [r for r in doms if is_feat(r)]
    ref = [r for r in doms if not is_feat(r)]
    res = dict(pools=len(used), n_feat=len(feat), n_ref=len(ref),
               sites_feat=sum(r['_sites'] for r in feat), sites_ref=sum(r['_sites'] for r in ref))
    if not used:
        if verbose:
            p('  %s: нет страт с обоими типами' % title)
        return res
    rate_out, rate_reg = {}, {}
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rate_out[k] = sum(r['_out3'] for r in v) / S
        rate_reg[k] = sum(r['_regs'] for r in v) / S
    O_out = sum(r['_out3'] for r in feat)
    O_reg = sum(r['_regs'] for r in feat)
    E_out = sum(rate_out[keyf(r)] * r['_sites'] for r in feat)
    E_reg = sum(rate_reg[keyf(r)] * r['_sites'] for r in feat)
    oe_out = O_out / E_out if E_out else float('nan')
    oe_reg = O_reg / E_reg if E_reg else float('nan')
    ref_reg = sum(r['_regs'] for r in ref)
    res.update(O_out=O_out, E_out=E_out, O_reg=O_reg, E_reg=E_reg, oe_out=oe_out, oe_reg=oe_reg, ref_reg=ref_reg)
    # перестановка
    pool_lists = [(list(v), sum(1 for r in v if is_feat(r)), k) for k, v in used.items()]
    c_out = c_reg = 0
    for _ in range(n_perm):
        po = pe = ro = re_ = 0.0
        for v, m, k in pool_lists:
            random.shuffle(v)
            for r in v[:m]:
                po += r['_out3']
                ro += r['_regs']
                pe += rate_out[k] * r['_sites']
                re_ += rate_reg[k] * r['_sites']
        if (po / pe if pe else 0) <= oe_out + 1e-12:
            c_out += 1
        if (ro / re_ if re_ else 0) <= oe_reg + 1e-12:
            c_reg += 1
    res.update(p_out=c_out / n_perm, p_reg=c_reg / n_perm, pois=poisson_cdf(O_reg, E_reg))
    if verbose:
        p('  %s' % title)
        p('    страт %d; признак %d доменов (%d сайтов), сравнение %d (%d сайтов)' % (
            len(used), len(feat), res['sites_feat'], len(ref), res['sites_ref']))
        p('    выход: O=%d E=%.1f O/E=%.3f перест. p=%.4f' % (O_out, E_out, oe_out, res['p_out']))
        p('    регистрации: O=%d E=%.2f O/E=%.3f (сравнение %d рег) пуассон p=%.4f перест. p=%.4f; рег/100 сайтов %.3f против %.3f' % (
            O_reg, E_reg, oe_reg, ref_reg, res['pois'], res['p_reg'],
            100.0 * O_reg / res['sites_feat'], 100.0 * ref_reg / res['sites_ref']))
    return res


# ================================================================== 1. баланс ковариат внутри пулов
p()
p('=' * 100)
p('1. БАЛАНС КОВАРИАТ ВНУТРИ ПУЛОВ КОНТЕНТ+ДЕНЬ (68 пулов суммарного теста)')
p('   Ожидание = доля значения ковариаты в пуле (по сайтам) × сайты доменов с признаком; O — сколько у признака на самом деле')
p('=' * 100)
poolkey = lambda r: (r['набор контента'], r['день запуска'])
pools = defaultdict(list)
for r in scope:
    pools[poolkey(r)].append(r)
used68 = {k: v for k, v in pools.items() if any(isGen(r) for r in v) and any(not isGen(r) for r in v)}
doms68 = [r for v in used68.values() for r in v]
feat68 = [r for r in doms68 if isGen(r)]
ref68 = [r for r in doms68 if not isGen(r)]
p('пулов %d, доменов с признаком %d, сравнения %d' % (len(used68), len(feat68), len(ref68)))

# доля регистраций по зонам и паттернам среди ВСЕХ 1511 после фильтра (сырые, для ориентира)
p()
p('  Ориентир (сырые суммы среди 1511 доменов после фильтра): рег на 100 сайтов по зонам и паттернам')
for fld, nm in (('_zone', 'зона'), ('_pat', 'паттерн'), ('дней', 'дней'), ('шаблон', 'шаблон')):
    agg = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        a = agg[r[fld]]
        a[0] += 1
        a[1] += r['_sites']
        a[2] += r['_regs']
        a[3] += r['_out3']
    p('   %s: ' % nm + '; '.join('%s: %d дом., рег/100 %.3f, выход %.1f%%' % (
        k, a[0], 100.0 * a[2] / a[1] if a[1] else 0, 100.0 * a[3] / a[1] if a[1] else 0) for k, a in sorted(agg.items())))


def balance(field, name, doms, feat, is_feat, keyf):
    pl = defaultdict(list)
    for r in doms:
        pl[keyf(r)].append(r)
    vals = sorted({r[field] for r in doms})
    p('  %s:' % name)
    for val in vals:
        O = sum(1 for r in feat if r[field] == val)
        E = 0.0
        for k, v in pl.items():
            n = len(v)
            share = sum(1 for r in v if r[field] == val) / n
            E += share * sum(1 for r in v if is_feat(r))
        flag = ''
        if E > 0 and (O / E > 1.25 or O / E < 0.8) and abs(O - E) >= 3:
            flag = '   <-- перекос'
        p('    %-12s: у признака %3d, ожидание из состава пулов %6.1f, O/E %.2f%s' % (str(val), O, E, O / E if E else 0, flag))


for fld, nm in (('_zone', 'зона'), ('_pat', 'паттерн имени'), ('дней', 'дней'), ('шаблон', 'шаблон'),
                ('который раз аккаунт', 'который раз аккаунт'), ('аккаунт свежий', 'аккаунт свежий'),
                ('блок часа', 'блок часа')):
    balance(fld, nm, doms68, feat68, isGen, poolkey)

# сайтов в окне
p('  сайтов в окне: признак ' + ', '.join('%s×%d' % kv for kv in Counter(r['_sites'] for r in feat68).most_common()) +
  '; сравнение ' + ', '.join('%s×%d' % kv for kv in Counter(r['_sites'] for r in ref68).most_common()))

# ================================================================== 2. страты жёстче
p()
p('=' * 100)
p('2. СУММАРНЫЙ ТЕСТ «ВСЕ ПРИЗНАКИ ПРОТИВ ОБЫЧНЫХ» ПРИ РАЗНЫХ СТРАТАХ')
p('=' * 100)
K = {
    'контент+день': lambda r: (r['набор контента'], r['день запуска']),
    'контент+день+зона': lambda r: (r['набор контента'], r['день запуска'], r['_zone']),
    'контент+день+паттерн': lambda r: (r['набор контента'], r['день запуска'], r['_pat']),
    'контент+день+зона+паттерн': lambda r: (r['набор контента'], r['день запуска'], r['_zone'], r['_pat']),
    'контент+день+зона+паттерн+дней': lambda r: (r['набор контента'], r['день запуска'], r['_zone'], r['_pat'], r['дней']),
    'контент+день+зона+паттерн+шаблон': lambda r: (r['набор контента'], r['день запуска'], r['_zone'], r['_pat'], r['шаблон']),
}
resG = {}
for nm, kf in K.items():
    resG[nm] = strat(scope, isGen, kf, title='Все признаки (ноль + alpha_other с цифрой), страта: ' + nm)
p()
p('  То же для пост-хок варианта «без кода даты»:')
resG2 = {}
scope2 = [r for r in scope if not isD(r)]
for nm in ('контент+день', 'контент+день+зона', 'контент+день+паттерн', 'контент+день+зона+паттерн'):
    resG2[nm] = strat(scope2, isGen2, K[nm], title='Без кода даты, страта: ' + nm)

p()
p('  Подтипы отдельно при страте контент+день+зона+паттерн (паттерн тут тривиален, проверка что +зона не ломает):')
num_rows = [r for r in scope if r['_pat'] == 'numeric']
alpha_rows = [r for r in scope if r['_pat'] == 'alpha_other']
isB = lambda r: r['_sub'] == 'alpha_other: смесь, длина 4'
isRef4 = lambda r: r['_sub'] == 'alpha_other: буквы, длина 4'
isC = lambda r: r['_sub'] in ('alpha_other: смесь, длина 3', 'alpha_other: буквы, длина 3')
resA_z = strat(num_rows, isA, K['контент+день+зона'], title='A ведущий 0, контент+день+зона', n_perm=2000)
resB_z = strat([r for r in alpha_rows if isB(r) or isRef4(r)], isB, K['контент+день+зона'], title='B смесь-4 vs буквы-4, контент+день+зона', n_perm=2000)
resC_z = strat([r for r in alpha_rows if isC(r) or isRef4(r)], isC, K['контент+день+зона'], title='C длина-3 vs буквы-4, контент+день+зона', n_perm=2000)
resAll_z = strat(alpha_rows, isAnyDigit, K['контент+день+зона'], title='alpha_other с цифрой vs буквы, контент+день+зона', n_perm=2000)

# ================================================================== 3. leave-one-pool-out и вклад пулов
p()
p('=' * 100)
p('3. LEAVE-ONE-POOL-OUT И ВКЛАД ПУЛОВ (страта контент+день, все признаки)')
p('=' * 100)


def pool_contrib(used, is_feat):
    out = []
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rr = sum(r['_regs'] for r in v) / S
        f = [r for r in v if is_feat(r)]
        g = [r for r in v if not is_feat(r)]
        O = sum(r['_regs'] for r in f)
        E = rr * sum(r['_sites'] for r in f)
        out.append((E - O, k, len(f), len(g), O, E, sum(r['_regs'] for r in g)))
    return out


contrib = pool_contrib(used68, isGen)
contrib.sort(reverse=True)
tot_O = sum(c[4] for c in contrib)
tot_E = sum(c[5] for c in contrib)
p('  Всего: O=%d E=%.2f, дефицит E−O=%.2f' % (tot_O, tot_E, tot_E - tot_O))
p('  Пулы с наибольшим вкладом в дефицит (E−O):')
p('  %-8s %-40s %-12s %5s %5s %5s %7s %7s' % ('E−O', 'набор контента', 'день', 'nпр', 'nср', 'Oпр', 'Eпр', 'рег ср'))
cum = 0.0
for i, (d, k, nf, ng, O, E, rg) in enumerate(contrib[:12]):
    cum += d
    p('  %8.2f %-40s %-12s %5d %5d %5d %7.2f %7d   (накоплено %.2f)' % (d, k[0][:40], k[1], nf, ng, O, E, rg, cum))
n_pos = sum(1 for c in contrib if c[0] > 1e-9)
n_neg = sum(1 for c in contrib if c[0] < -1e-9)
n_zero = len(contrib) - n_pos - n_neg
p('  Пулов, где признак хуже ожидания (E−O>0): %d; лучше: %d; ровно (обычно 0 рег в пуле): %d' % (n_pos, n_neg, n_zero))
p('  Пулов, где у признака 0 регистраций, а у сравнения ≥1: %d; где у признака ≥1, а у сравнения 0: %d' % (
    sum(1 for c in contrib if c[4] == 0 and c[6] >= 1), sum(1 for c in contrib if c[4] >= 1 and c[6] == 0)))

# leave-one-out
p()
p('  Leave-one-pool-out: O/E и пуассон p после удаления каждого пула (показаны 8 самых влиятельных):')
loo = []
for d, k, nf, ng, O, E, rg in contrib:
    O2 = tot_O - O
    E2 = tot_E - E
    loo.append((poisson_cdf(O2, E2), O2 / E2 if E2 else float('nan'), k, O2, E2))
loo.sort(reverse=True)
for pp, oe, k, O2, E2 in loo[:8]:
    p('    без пула %-40s %-12s: O=%d E=%.2f O/E=%.3f пуассон p=%.4f' % (k[0][:40], k[1], O2, E2, oe, pp))
p('  Диапазон O/E при удалении одного пула: %.3f … %.3f; максимум пуассон p = %.4f; пулов, при удалении которых p>0.05: %d из %d' % (
    min(x[1] for x in loo), max(x[1] for x in loo), max(x[0] for x in loo), sum(1 for x in loo if x[0] > 0.05), len(loo)))

# leave-two-out worst pair
best2 = None
for i in range(len(contrib)):
    for j in range(i + 1, len(contrib)):
        O2 = tot_O - contrib[i][4] - contrib[j][4]
        E2 = tot_E - contrib[i][5] - contrib[j][5]
        pp = poisson_cdf(O2, E2)
        if best2 is None or pp > best2[0]:
            best2 = (pp, O2, E2, contrib[i][1], contrib[j][1])
p('  Худшая пара пулов для результата: без «%s / %s» и «%s / %s»: O=%d E=%.2f O/E=%.3f пуассон p=%.4f' % (
    best2[3][0][:30], best2[3][1], best2[4][0][:30], best2[4][1], best2[1], best2[2], best2[1] / best2[2], best2[0]))

# ================================================================== 4. парные сравнения по пулам с регистрациями
p()
p('=' * 100)
p('4. ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ ПУЛА ПО РЕГИСТРАЦИЯМ (только пулы, где есть хоть одна регистрация)')
p('=' * 100)


def paired_sign(used, is_feat, nm):
    worse = better = tie = 0
    for k, v in used.items():
        f = [r for r in v if is_feat(r)]
        g = [r for r in v if not is_feat(r)]
        Rf = sum(r['_regs'] for r in f)
        Rg = sum(r['_regs'] for r in g)
        if Rf + Rg == 0:
            continue
        rf = Rf / sum(r['_sites'] for r in f)
        rg = Rg / sum(r['_sites'] for r in g)
        if rf < rg - 1e-12:
            worse += 1
        elif rf > rg + 1e-12:
            better += 1
        else:
            tie += 1
    n = worse + better
    p('  %s: пулов с регистрациями %d; признак хуже (рег/сайт ниже) в %d, лучше в %d, ничья %d; знаковый p(лучше так мало)=%.3f' % (
        nm, worse + better + tie, worse, better, tie, binom_cdf(better, n) if n else 1.0))


paired_sign(used68, isGen, 'контент+день, все признаки')
pz = defaultdict(list)
for r in scope:
    pz[K['контент+день+зона+паттерн'](r)].append(r)
usedz = {k: v for k, v in pz.items() if any(isGen(r) for r in v) and any(not isGen(r) for r in v)}
paired_sign(usedz, isGen, 'контент+день+зона+паттерн, все признаки')

# ================================================================== 5. кластерный бутстрэп по пулам
p()
p('=' * 100)
p('5. КЛАСТЕРНЫЙ БУТСТРЭП ПО ПУЛАМ (2000 выборок пулов с возвращением) — 95% интервал O/E по регистрациям')
p('=' * 100)


def boot(used, is_feat, nm, nb=2000):
    keys = list(used.keys())
    per = {}
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rr = sum(r['_regs'] for r in v) / S
        f = [r for r in v if is_feat(r)]
        per[k] = (sum(r['_regs'] for r in f), rr * sum(r['_sites'] for r in f))
    vals = []
    for _ in range(nb):
        O = E = 0.0
        for _ in keys:
            k = random.choice(keys)
            O += per[k][0]
            E += per[k][1]
        vals.append(O / E if E else float('nan'))
    vals.sort()
    lo, hi = vals[int(0.025 * nb)], vals[int(0.975 * nb) - 1]
    p('  %s: точечно O/E=%.3f, 95%% интервал [%.3f, %.3f]; доля выборок с O/E ≥ 1: %.3f; с O/E ≥ 0.85: %.3f' % (
        nm, sum(v[0] for v in per.values()) / sum(v[1] for v in per.values()), lo, hi,
        sum(1 for v in vals if v >= 1) / nb, sum(1 for v in vals if v >= 0.85) / nb))


boot(used68, isGen, 'контент+день, все признаки')
boot(usedz, isGen, 'контент+день+зона+паттерн, все признаки')

# ================================================================== 6. по зонам отдельно
p()
p('=' * 100)
p('6. РАЗДЕЛЬНО ПО ЗОНАМ (страта контент+день+паттерн внутри зоны)')
p('=' * 100)
for z in ('team', 'lol', 'casino', 'buzz'):
    strat([r for r in scope if r['_zone'] == z], isGen, K['контент+день+паттерн'], n_perm=2000,
          title='зона %s' % z)

# ================================================================== 7. чувствительность: «КОНТЕНТ НЕ ЗАПИСАН» как пул по дню
p()
p('=' * 100)
p('7. ЧУВСТВИТЕЛЬНОСТЬ: добавить 335 «КОНТЕНТ НЕ ЗАПИСАН» как страту «не записан + день + зона + паттерн»')
p('   (это НЕ набор контента; проверка лишь того, меняет ли исключение знак эффекта)')
p('=' * 100)
scope_nz = [r for r in base if inScope(r)]
nz_feat = [r for r in scope_nz if r['набор контента'] == 'КОНТЕНТ НЕ ЗАПИСАН' and isGen(r)]
nz_ref = [r for r in scope_nz if r['набор контента'] == 'КОНТЕНТ НЕ ЗАПИСАН' and not isGen(r)]
p('  среди «не записан»: признак %d доменов (%d рег), обычные %d (%d рег)' % (
    len(nz_feat), sum(r['_regs'] for r in nz_feat), len(nz_ref), sum(r['_regs'] for r in nz_ref)))
strat([r for r in scope_nz if r['набор контента'] == 'КОНТЕНТ НЕ ЗАПИСАН'], isGen,
      lambda r: (r['день запуска'], r['_zone'], r['_pat']), n_perm=2000, title='только «не записан», страта день+зона+паттерн')
strat(scope_nz, isGen, K['контент+день+зона+паттерн'], n_perm=2000, title='все 1511+335, страта контент+день+зона+паттерн')

# ================================================================== 8. объём дня
p()
p('=' * 100)
p('8. ОБЪЁМ ДНЯ: сколько доменов запущено в день у доменов с признаком и у сравнения (внутри пулов день фиксирован —')
p('   это лишь проверка, что признак не сидит на «тяжёлых» днях; плюс страта по размеру пула)')
p('=' * 100)
day_vol = Counter(r['день запуска'] for r in rows_all)
mv_f = sum(day_vol[r['день запуска']] for r in feat68) / len(feat68)
mv_r = sum(day_vol[r['день запуска']] for r in ref68) / len(ref68)
p('  средний объём дня (доменов в день, по всем 2077): признак %.1f, сравнение %.1f' % (mv_f, mv_r))
# размер пула
sizes = {k: len(v) for k, v in used68.items()}
for lo, hi, nm in ((2, 4, 'пулы из 2–4 доменов'), (5, 9, 'пулы из 5–9'), (10, 10 ** 6, 'пулы из 10+')):
    sub = {k: v for k, v in used68.items() if lo <= sizes[k] <= hi}
    doms = [r for v in sub.values() for r in v]
    if doms:
        strat(doms, isGen, poolkey, n_perm=1000, title=nm)

# ================================================================== 9. сводка
p()
p('=' * 100)
p('СВОДКА: суммарный тест при разных стратах')
p('=' * 100)
p('%-40s %5s %5s/%-5s %8s %6s %6s %7s %6s %7s %7s' % ('страта', 'страт', 'приз', 'срав', 'O/E вых', 'p', 'рег O', 'E', 'O/E', 'пуас', 'перест'))
for nm, res in list(resG.items()) + [('без кода даты: ' + k, v) for k, v in resG2.items()]:
    if 'oe_out' in res:
        p('%-40s %5d %5d/%-5d %8.3f %6.3f %6d %7.2f %6.3f %7.3f %7.3f' % (
            nm[:40], res['pools'], res['n_feat'], res['n_ref'], res['oe_out'], res['p_out'], res['O_reg'], res['E_reg'],
            res['oe_reg'], res['pois'], res['p_reg']))

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT)

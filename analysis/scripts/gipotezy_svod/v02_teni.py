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
  Второй проход (разделы 10–12):
  10. Держится ли дефицит на «горячих» доменах: бинарный исход, потолок, без доменов с ≥3 рег, регистрации за всё время,
      сайтов с регистрацией, ФД; выход без «мёртвых» доменов и с потолком.
  11. След партии: ID cf-аккаунта и аккаунта Вебмастера (ранг внутри пула, страта +половина дня, +блок cf-ID).
  12. Негативный контроль: «ложные признаки» (произвольные разбиения обычных меток) при той же страте.
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

# ================================================================== 9. откуда разница 0.61 -> 0.71: паттерн внутри пула
p()
p('=' * 100)
p('9. ОТКУДА РАЗНИЦА 0.61 → 0.71 ПРИ ДОБАВЛЕНИИ ПАТТЕРНА В СТРАТУ')
p('=' * 100)
agg = defaultdict(lambda: [0, 0, 0, 0])
for v in used68.values():
    for r in v:
        a = agg[(r['_pat'], 'признак' if isGen(r) else 'обычный')]
        a[0] += 1
        a[1] += r['_sites']
        a[2] += r['_regs']
        a[3] += r['_out3']
p('  Внутри 68 пулов контент+день, по паттернам:')
for k, a in sorted(agg.items()):
    p('    %-24s дом %4d сайтов %6d рег %3d рег/100 %.3f выход %.1f%%' % (k, a[0], a[1], a[2], 100.0 * a[2] / a[1], 100.0 * a[3] / a[1]))
cross = [(k, r) for k, v in used68.items() for r in v if isGen(r) and not any((not isGen(x)) and x['_pat'] == r['_pat'] for x in v)]
cO = sum(r['_regs'] for _, r in cross)
cE = 0.0
for k, r in cross:
    v = used68[k]
    cE += sum(x['_regs'] for x in v) / sum(x['_sites'] for x in v) * r['_sites']
p('  Доменов с признаком, у которых в пуле нет обычных ТОГО ЖЕ паттерна (сравнение только с чужим паттерном): %d; их O=%d, E=%.2f' % (len(cross), cO, cE))
p('  => разница 19/31.1 (0.61) против 17/24.0 (0.71) — не из-за этих %d доменов, а из-за того, что в смешанных пулах ожидание бралось' % len(cross))
p('     по общей доле пула, где обычные numeric конвертили лучше, чем обычные alpha_other того же пула; признак же на 72% alpha_other.')

# ------------------------------------------------------------------ калибровка знакового теста
p()
p('  Калибровка знакового теста по регистрациям (признак — меньшая группа, при 1 регистрации в пуле «хуже» ожидается чаще 50%):')
for r in scope:
    r['_g'] = isGen(r)


def sign_counts(used):
    w = b = t = 0
    for k, v in used.items():
        f = [r for r in v if r['_g']]
        g = [r for r in v if not r['_g']]
        Rf = sum(r['_regs'] for r in f)
        Rg = sum(r['_regs'] for r in g)
        if Rf + Rg == 0:
            continue
        rf = Rf / sum(r['_sites'] for r in f)
        rg = Rg / sum(r['_sites'] for r in g)
        if rf < rg - 1e-12:
            w += 1
        elif rf > rg + 1e-12:
            b += 1
        else:
            t += 1
    return w, b, t


obs_s = sign_counts(used68)
cnt = 0
ws = []
for _ in range(3000):
    for v in used68.values():
        gs = [r['_g'] for r in v]
        random.shuffle(gs)
        for r, g in zip(v, gs):
            r['_g'] = g
    w, b, t = sign_counts(used68)
    ws.append(w)
    if w >= obs_s[0]:
        cnt += 1
for r in scope:
    r['_g'] = isGen(r)
p('    наблюдено: хуже %d, лучше %d, ничья %d; под нулём (перестановка в пуле) среднее «хуже» = %.1f; p(хуже ≥ %d) = %.3f' % (
    obs_s[0], obs_s[1], obs_s[2], sum(ws) / len(ws), obs_s[0], cnt / 3000))

# ------------------------------------------------------------------ клики в окне
p()
p('  Клики из поиска в окне (страта контент+день+зона+паттерн): где сидит дефицит — в охвате или в конверсии с клика')
for r in scope:
    r['_clk'] = to_int(r['кликов из поиска в окне'])
O_c = E_c = 0.0
fc = rc = fr = rr_ = 0
O_rc = E_rc = 0.0
for k, v in usedz.items():
    Sp = sum(x['_sites'] for x in v)
    rate_c = sum(x['_clk'] for x in v) / Sp
    C = sum(x['_clk'] for x in v)
    rate_rc = sum(x['_regs'] for x in v) / C if C else 0
    for x in v:
        if isGen(x):
            O_c += x['_clk']
            E_c += rate_c * x['_sites']
            fc += x['_clk']
            fr += x['_regs']
            O_rc += x['_regs']
            E_rc += rate_rc * x['_clk']
        else:
            rc += x['_clk']
            rr_ += x['_regs']
p('    клики из поиска в окне: O=%d E=%.0f O/E=%.3f' % (O_c, E_c, O_c / E_c))
p('    рег на 10 тыс. поисковых кликов: признак %.2f (%d рег / %d кликов), сравнение %.2f (%d / %d)' % (
    1e4 * fr / fc, fr, fc, 1e4 * rr_ / rc, rr_, rc))
p('    регистрации при ожидании ПО КЛИКАМ (E = рег/клик пула × клики домена): O=%d E=%.2f O/E=%.3f' % (O_rc, E_rc, O_rc / E_rc))

# ------------------------------------------------------------------ зона × подтип
p()
p('  Зона × подтип (страта контент+день+паттерн внутри зоны):')
isB_ = lambda r: r['_sub'] == 'alpha_other: смесь, длина 4'
isC3 = lambda r: r['_sub'] == 'alpha_other: смесь, длина 3'
tests = (('ноль vs numeric', isA, lambda r: r['_pat'] == 'numeric'),
         ('смесь-4 vs буквы-4', isB_, lambda r: isB_(r) or isRef4(r)),
         ('смесь-3 vs буквы-4', isC3, lambda r: isC3(r) or isRef4(r)),
         ('код даты vs буквы-4', isD, lambda r: isD(r) or isRef4(r)),
         ('все признаки', isGen, lambda r: True))
for z in ('team', 'lol', 'casino'):
    zr = [r for r in scope if r['_zone'] == z]
    for nm, ff, sub in tests:
        pl = defaultdict(list)
        for r in zr:
            if sub(r):
                pl[K['контент+день+паттерн'](r)].append(r)
        used = {k: v for k, v in pl.items() if any(ff(r) for r in v) and any(not ff(r) for r in v)}
        if not used:
            continue
        Oo = Eo = Or = Er = 0.0
        nf = 0
        for k, v in used.items():
            S = sum(r['_sites'] for r in v)
            ro = sum(r['_out3'] for r in v) / S
            rr = sum(r['_regs'] for r in v) / S
            for r in v:
                if ff(r):
                    Oo += r['_out3']
                    Eo += ro * r['_sites']
                    Or += r['_regs']
                    Er += rr * r['_sites']
                    nf += 1
        p('    %-7s %-22s страт %2d, дом %3d: выход O=%5d E=%7.1f O/E=%.2f; рег O=%2d E=%5.2f O/E=%s' % (
            z, nm, len(used), nf, Oo, Eo, Oo / Eo if Eo else 0, Or, Er, ('%.2f' % (Or / Er)) if Er else 'nan'))


# ================================================================== 10. устойчивость к тяжёлым доменам
p()
p('=' * 100)
p('10. ДЕРЖИТСЯ ЛИ ДЕФИЦИТ НА «ГОРЯЧИХ» ДОМЕНАХ СРАВНЕНИЯ (второй проход скептика)')
p('    Страта контент+день+зона+паттерн (самая жёсткая) и контент+день (тестировщик). Исходы: регистрации в окне как есть;')
p('    бинарно «домен с ≥1 рег в окне»; потолок 2 рег на домен; без доменов с ≥3 рег (обе группы); без топ-3 сравнения;')
p('    регистраций за всё время (больше событий); сайтов с регистрацией; ФД в окне.')
p('=' * 100)
for r in scope:
    r['_regall'] = to_int(r['регистраций'])
    r['_any'] = 1 if r['_regs'] >= 1 else 0
    r['_cap2'] = min(r['_regs'], 2)
    r['_sreg'] = to_int(r['сайтов с регистрацией'])

heavy_f = [r for r in scope if isGen(r) and r['_regs'] >= 3]
heavy_r = [r for r in scope if (not isGen(r)) and r['_regs'] >= 3]
p('  Доменов с ≥3 рег в окне среди numeric+alpha_other после фильтра: признак %d из %d, обычные %d из %d; макс. рег у признака = %d' % (
    len(heavy_f), sum(1 for r in scope if isGen(r)), len(heavy_r), sum(1 for r in scope if not isGen(r)),
    max(r['_regs'] for r in scope if isGen(r))))


def strat_field(rs, is_feat, keyf, field, n_perm=3000):
    """O/E по произвольному полю-исходу внутри страт keyf; перестановка признака внутри страты (односторонний p «хуже»)."""
    pools_ = defaultdict(list)
    for r in rs:
        pools_[keyf(r)].append(r)
    used_ = {k: v for k, v in pools_.items() if any(is_feat(r) for r in v) and any(not is_feat(r) for r in v)}
    rate = {}
    for k, v in used_.items():
        S = sum(r['_sites'] for r in v)
        rate[k] = sum(r[field] for r in v) / S
    feat = [r for v in used_.values() for r in v if is_feat(r)]
    ref = [r for v in used_.values() for r in v if not is_feat(r)]
    O = sum(r[field] for r in feat)
    E = sum(rate[keyf(r)] * r['_sites'] for r in feat)
    oe = O / E if E else float('nan')
    pl = [(list(v), sum(1 for r in v if is_feat(r)), k) for k, v in used_.items()]
    c = 0
    for _ in range(n_perm):
        po = pe = 0.0
        for v, m, k in pl:
            random.shuffle(v)
            for r in v[:m]:
                po += r[field]
                pe += rate[k] * r['_sites']
        if (po / pe if pe else 0) <= oe + 1e-12:
            c += 1
    return dict(pools=len(used_), nf=len(feat), nr=len(ref), O=O, E=E, oe=oe, p=c / n_perm,
                ref=sum(r[field] for r in ref), pois=poisson_cdf(O, E) if float(O).is_integer() else float('nan'))


def show_field(title, res):
    p('    %-46s страт %3d, %3d/%-3d: O=%6.1f E=%6.2f O/E=%.3f перест. p=%.3f (у сравнения %d)' % (
        title, res['pools'], res['nf'], res['nr'], res['O'], res['E'], res['oe'], res['p'], res['ref']))


top3_ref = sorted([r for r in scope if not isGen(r)], key=lambda r: -r['_regs'])[:3]
p('  Топ-3 домена сравнения по рег в окне: %s' % ', '.join('%s (%d)' % (r['домен'], r['_regs']) for r in top3_ref))
rob = {}
for snm in ('контент+день+зона+паттерн', 'контент+день'):
    kf = K[snm]
    p('  --- страта %s ---' % snm)
    rob[(snm, 'as_is')] = strat_field(scope, isGen, kf, '_regs')
    show_field('регистрации в окне, как есть', rob[(snm, 'as_is')])
    rob[(snm, 'any')] = strat_field(scope, isGen, kf, '_any')
    show_field('бинарно: доменов с ≥1 рег', rob[(snm, 'any')])
    rob[(snm, 'cap2')] = strat_field(scope, isGen, kf, '_cap2')
    show_field('потолок 2 рег на домен', rob[(snm, 'cap2')])
    rob[(snm, 'no3')] = strat_field([r for r in scope if r['_regs'] < 3], isGen, kf, '_regs')
    show_field('без доменов с ≥3 рег (обе группы, %d дом.)' % (len(heavy_f) + len(heavy_r)), rob[(snm, 'no3')])
    rob[(snm, 'notop3')] = strat_field([r for r in scope if r not in top3_ref], isGen, kf, '_regs')
    show_field('без топ-3 сравнения', rob[(snm, 'notop3')])
    rob[(snm, 'sreg')] = strat_field(scope, isGen, kf, '_sreg')
    show_field('сайтов с регистрацией', rob[(snm, 'sreg')])
    rob[(snm, 'all')] = strat_field(scope, isGen, kf, '_regall')
    show_field('регистраций за всё время', rob[(snm, 'all')])
    rob[(snm, 'fd')] = strat_field(scope, isGen, kf, '_fd')
    show_field('ФД в окне', rob[(snm, 'fd')])

# сколько «горячих» доменов ждать у признака под нулём (перестановка в самой жёсткой страте)
cnt_hot = 0
NP = 3000
plz = [(list(v), sum(1 for r in v if isGen(r))) for v in usedz.values()]
obs_hot = sum(1 for v in usedz.values() for r in v if isGen(r) and r['_regs'] >= 3)
hot_tot = sum(1 for v in usedz.values() for r in v if r['_regs'] >= 3)
hist_hot = Counter()
for _ in range(NP):
    h = 0
    for v, m in plz:
        random.shuffle(v)
        h += sum(1 for r in v[:m] if r['_regs'] >= 3)
    hist_hot[h] += 1
    if h <= obs_hot:
        cnt_hot += 1
p('  «Горячих» (≥3 рег) доменов у признака в страте контент+день+зона+паттерн: %d при %d таких доменах в стратах; под нулём среднее %.2f, P(≤%d) = %.3f' % (
    obs_hot, hot_tot, sum(k * v for k, v in hist_hot.items()) / NP, obs_hot, cnt_hot / NP))


# 10b. выход: не сидит ли дефицит на «мёртвых» доменах (0–5 вышедших сайтов из 206)
p()
p('  10b. ВЫХОД: держится ли −8% на «мёртвых» доменах (≤5 вышедших сайтов из 206) — страта контент+день+зона+паттерн')
for r in scope:
    r['_dead'] = 1 if r['_out3'] <= 5 else 0
    r['_out_alive'] = r['_out3']
dead_f = sum(1 for v in usedz.values() for r in v if isGen(r) and r['_dead'])
dead_r = sum(1 for v in usedz.values() for r in v if (not isGen(r)) and r['_dead'])
p('    «мёртвых» доменов в стратах: признак %d из %d, сравнение %d из %d' % (
    dead_f, sum(1 for v in usedz.values() for r in v if isGen(r)), dead_r, sum(1 for v in usedz.values() for r in v if not isGen(r))))
show_field('доля мёртвых (O/E по числу доменов)', strat_field(scope, isGen, K['контент+день+зона+паттерн'], '_dead'))
show_field('выход без мёртвых доменов', strat_field([r for r in scope if not r['_dead']], isGen, K['контент+день+зона+паттерн'], '_out3'))
show_field('выход как есть', strat_field(scope, isGen, K['контент+день+зона+паттерн'], '_out3'))
# выход с потолком: медианный домен пула — робастно к «звёздам»
for r in scope:
    r['_out_cap'] = min(r['_out3'], 40)
show_field('выход с потолком 40 сайтов на домен', strat_field(scope, isGen, K['контент+день+зона+паттерн'], '_out_cap'))

# ================================================================== 11. порядок запуска внутри дня / cf как партия
p()
p('=' * 100)
p('11. СЛЕД ПАРТИИ: ID cf-аккаунта и ID аккаунта Вебмастера (последовательные номера ≈ порядок в дне / партия закупки)')
p('=' * 100)
for r in scope:
    r['_cfid'] = int(r['cf-аккаунт']) if r['cf-аккаунт'].isdigit() else -1
    r['_wmid'] = int(r['аккаунт вебмастера']) if r['аккаунт вебмастера'].isdigit() else -1
# ID cf по дням: насколько cf сцеплен с днём
byday = defaultdict(list)
for r in rows:
    byday[r['день запуска']].append(int(r['cf-аккаунт']))
p('  cf-аккаунт ID по дням запуска (мин/медиана/макс) — ID идут блоками по датам, т.е. cf ≈ тень дня, пул его закрывает:')
p('    ' + '; '.join('%s: %d–%d' % (d[5:], min(v), max(v)) for d, v in sorted(byday.items())[:12]) + ' …')
# внутри пула: ранг ID у признака (0..1), ожидание 0.5
def rank_balance(field, name):
    tot = 0.0
    n = 0
    lo = hi = 0
    for k, v in used68.items():
        ids = sorted(r[field] for r in v)
        if len(set(ids)) < 2:
            continue
        for r in v:
            if isGen(r):
                rk = (ids.index(r[field])) / (len(ids) - 1)
                tot += rk
                n += 1
                if rk < 0.5:
                    lo += 1
                elif rk > 0.5:
                    hi += 1
    p('  %s: средний ранг признака внутри пула %.3f (ожидание 0.5), ниже медианы %d, выше %d из %d' % (name, tot / n if n else 0, lo, hi, n))


rank_balance('_cfid', 'ID cf-аккаунта')
rank_balance('_wmid', 'ID аккаунта Вебмастера (порядок постановки в дне)')
# страта контент+день+зона+паттерн + половина дня по ID Вебмастера (ранняя/поздняя)
med_wm = {}
wm_by_day = defaultdict(list)
for r in scope:
    wm_by_day[r['день запуска']].append(r['_wmid'])
for d, v in wm_by_day.items():
    s = sorted(v)
    med_wm[d] = s[len(s) // 2]
half = lambda r: 'ранняя' if r['_wmid'] < med_wm[r['день запуска']] else 'поздняя'
res_half = strat(scope, isGen, lambda r: (r['набор контента'], r['день запуска'], r['_zone'], r['_pat'], half(r)),
                 n_perm=3000, title='Все признаки, страта контент+день+зона+паттерн+половина дня (по ID Вебмастера)')
res_cf = strat(scope, isGen, lambda r: (r['набор контента'], r['день запуска'], r['_zone'], r['_pat'], r['_cfid'] // 50),
               n_perm=3000, title='Все признаки, страта контент+день+зона+паттерн+блок cf-ID по 50')

# ================================================================== 12. негативный контроль: ложные признаки
p()
p('=' * 100)
p('12. НЕГАТИВНЫЙ КОНТРОЛЬ: «ложные признаки» той же природы (произвольные разбиения ОБЫЧНЫХ меток), та же страта')
p('    Если ложный признак даёт такой же дефицит, наблюдённый — не про «сгенерированность». Страта контент+день+зона+паттерн.')
p('=' * 100)
normal = [r for r in scope if not isGen(r)]
fakes = (
    ('numeric: первая цифра 1–4 vs 5–9', lambda r: r['_pat'] == 'numeric', lambda r: r['_lab'][0] in '1234'),
    ('numeric: последняя цифра нечётная', lambda r: r['_pat'] == 'numeric', lambda r: r['_lab'][-1] in '13579'),
    ('numeric: есть цифра 8 в метке', lambda r: r['_pat'] == 'numeric', lambda r: '8' in r['_lab']),
    ('буквы: первая буква a–m vs n–z', lambda r: r['_pat'] == 'alpha_other', lambda r: r['_lab'][0] <= 'm'),
    ('буквы: есть гласная (aeiouy)', lambda r: r['_pat'] == 'alpha_other', lambda r: any(c in 'aeiouy' for c in r['_lab'])),
    ('буквы: последняя буква a–m', lambda r: r['_pat'] == 'alpha_other', lambda r: r['_lab'][-1] <= 'm'),
)
p('  %-40s %5s %8s %8s %6s %6s | %6s %6s %6s %6s' % ('ложный признак', 'страт', 'дом.', 'срав.', 'O/Eвых', 'p', 'рег O', 'E', 'O/E', 'p'))
fake_oes = []
fake_oes_out = []
for nm, sub, ff in fakes:
    rr = [r for r in normal if sub(r)]
    res = strat(rr, ff, K['контент+день+зона+паттерн'], n_perm=2000, verbose=False)
    if 'oe_out' in res:
        fake_oes.append(res['oe_reg'])
        fake_oes_out.append(res['oe_out'])
        p('  %-40s %5d %8d %8d %6.3f %6.3f | %6d %6.2f %6.3f %6.3f' % (
            nm, res['pools'], res['n_feat'], res['n_ref'], res['oe_out'], res['p_out'], res['O_reg'], res['E_reg'], res['oe_reg'], res['p_reg']))
# объединённый ложный признак того же объёма
fake_all = lambda r: (r['_pat'] == 'numeric' and r['_lab'][0] in '1234') or (r['_pat'] == 'alpha_other' and r['_lab'][0] <= 'm')
resF = strat(normal, fake_all, K['контент+день+зона+паттерн'], n_perm=2000, verbose=False)
p('  %-40s %5d %8d %8d %6.3f %6.3f | %6d %6.2f %6.3f %6.3f' % (
    'объединённый ложный (1–4 или a–m)', resF['pools'], resF['n_feat'], resF['n_ref'], resF['oe_out'], resF['p_out'], resF['O_reg'], resF['E_reg'], resF['oe_reg'], resF['p_reg']))
_gz = resG['контент+день+зона+паттерн']
p('  Для сравнения настоящий признак при той же страте: выход O/E %.3f (p=%.4f), регистрации O/E %.3f (перест. p=%.3f)' % (
    _gz['oe_out'], _gz['p_out'], _gz['oe_reg'], _gz['p_reg']))

# ================================================================== 10. сводка
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

gz = resG['контент+день+зона+паттерн']
gp = resG['контент+день+паттерн']
g0 = resG['контент+день']
p()
p('=' * 100)
p('ВЫВОД СКЕПТИКА (тени)')
p('=' * 100)
p('1. Внутри 68 пулов контент+день признак перекошен по паттерну: alpha_other %d доменов при ожидании 80.6 (O/E 1.55), numeric 48 при 92.4.' % sum(1 for r in feat68 if r['_pat'] == 'alpha_other'))
p('   Ожидание в суммарном тесте бралось по общей доле пула, и в смешанных пулах чужой паттерн (numeric обычный) тянул E вверх.')
p('   Гипотеза сформулирована как «против обычных меток того же паттерна», поэтому честная страта — контент+день+паттерн:')
p('   регистрации %d против %.1f, O/E %.2f (пуассон p=%.3f, перестановка p=%.3f) вместо %d против %.1f, O/E %.2f (p=%.3f).' % (
    gp['O_reg'], gp['E_reg'], gp['oe_reg'], gp['pois'], gp['p_reg'], g0['O_reg'], g0['E_reg'], g0['oe_reg'], g0['pois']))
p('   Самая жёсткая страта контент+день+зона+паттерн (%d страт, %d против %d доменов): регистрации %d против %.1f, O/E %.2f' % (
    gz['pools'], gz['n_feat'], gz['n_ref'], gz['O_reg'], gz['E_reg'], gz['oe_reg']))
p('   (пуассон p=%.3f, перестановка p=%.3f); выход O/E %.3f (p=%.4f). Знак не меняется, эффект не исчезает, но значимость по регистрациям — на границе.' % (
    gz['pois'], gz['p_reg'], gz['oe_out'], gz['p_out']))
p('2. Ни день, ни зона, ни шаблон, ни дней, ни «который раз аккаунт», ни сайтов в окне, ни объём дня — не тени: внутри пулов они сбалансированы')
p('   (все дней=2, Theme1, аккаунт 1-й раз, 206 сайтов), а добавление зоны в страту эффект по выходу даже усиливает (0.95 → 0.92, p 0.07 → 0.002).')
p('3. Не один пул: leave-one-pool-out даёт O/E 0.57…0.65, максимум p=0.036; худшая пара пулов — p=0.058. Кластерный бутстрэп по пулам:')
p('   95% интервал O/E по регистрациям [0.42, 0.86] (контент+день) и [0.43, 0.93] (контент+день+зона+паттерн).')
p('4. Парный знаковый тест по регистрациям неинформативен: признак — меньшая группа, при 1 регистрации в пуле «хуже» ожидается в 61%%; %d из %d «хуже» даёт p=%.2f.' % (
    obs_s[0], obs_s[0] + obs_s[1] + obs_s[2], cnt / 3000))
p('5. Выход и регистрации проваливаются в разных зонах: .lol — выход 0.77 (p=0.0005; ноль vs numeric 0.60), регистрации 0.80 (n.s.);')
p('   .team — выход 0.98 (ничего), регистрации 0.50 (p≈0.03–0.05); .casino — 0.91 / 0.85 (n.s.). Единого механизма «имя мешает» не видно:')
p('   там, где хуже выход, регистрации в норме, и наоборот. Дефицит регистраций сидит в конверсии с клика (1.6 против 3.1 рег/10 тыс.), а не в охвате (клики O/E 0.94).')
p('6. «КОНТЕНТ НЕ ЗАПИСАН» исключён правильно: среди этих 335 признак чаще (37% против 28%) и «эффект» там втрое сильнее (выход 0.71, рег 0.42)')
p('   без контроля контента — то есть в августе имена с признаком шли вместе с определённым контентом/партией. Включать их нельзя.')
p()
rz = rob[('контент+день+зона+паттерн', 'as_is')]
rb = rob[('контент+день+зона+паттерн', 'any')]
rn = rob[('контент+день+зона+паттерн', 'no3')]
rc = rob[('контент+день+зона+паттерн', 'cap2')]
ra = rob[('контент+день+зона+паттерн', 'all')]
r0b = rob[('контент+день', 'any')]
r0n = rob[('контент+день', 'no3')]
p('7. (второй проход) Дефицит регистраций держится на «горячих» доменах сравнения: среди numeric+alpha_other 19 доменов с ≥3 рег в окне,')
p('   и все 19 — обычные метки (у признака максимум 2 рег). В самой жёсткой страте: как есть O/E %.2f (p=%.3f); бинарно «домен с ≥1 рег» %.2f (p=%.2f);' % (
    rz['oe'], rz['p'], rb['oe'], rb['p']))
p('   потолок 2 рег %.2f (p=%.2f); без доменов с ≥3 рег %.2f (p=%.2f) — это уже коридор опровержения 0.85–1.15. При страте тестировщика то же: бинарно %.2f (p=%.2f), без горячих %.2f (p=%.2f).' % (
    rc['oe'], rc['p'], rn['oe'], rn['p'], r0b['oe'], r0b['p'], r0n['oe'], r0n['p']))
p('   Оговорка: «у признака нет ни одного горячего домена» — само по себе часть сигнала (0 при ожидании %.1f в стратах, p=%.3f), поэтому выкидывать их нельзя;' % (
    sum(k * v for k, v in hist_hot.items()) / NP, cnt_hot / NP))
p('   но значит, «в 1.6 раза меньше регистраций» — это не «каждый домен с признаком конвертит хуже», а «домены с признаком реже дают ≥1 рег (−18…−20%, n.s.) и ни разу не выстрелили».')
p('   Регистрации за всё время (событий больше: %d против %.1f) дают O/E %.2f (p=%.3f) — то же, что в окне.' % (ra['O'], ra['E'], ra['oe'], ra['p']))
p('8. (второй проход) След партии по ID cf-аккаунта и аккаунта Вебмастера: cf-ID сцеплен с днём (пул закрывает), ранг признака внутри пула 0.46 / 0.52')
p('   (ожидание 0.5); страта +половина дня по ID Вебмастера: рег O/E %.2f (p=%.3f), выход %.3f; +блок cf-ID: рег %.2f (p=%.3f), выход %.3f. Порядок постановки и cf — не тени.' % (
    res_half['oe_reg'], res_half['p_reg'], res_half['oe_out'], res_cf['oe_reg'], res_cf['p_reg'], res_cf['oe_out']))
p('9. (второй проход) Негативный контроль — 7 «ложных признаков» (цифра 1–4, нечётная последняя цифра, есть 8, буква a–m, есть гласная …) при той же страте:')
fake_oes_out.append(resF['oe_out'])
fake_oes.append(resF['oe_reg'])
p('   по выходу O/E %.2f–%.2f (ни один не ниже 0.96; настоящий %.2f, p=%.3f) — дефицит выхода не воспроизводится произвольным разбиением;' % (
    min(fake_oes_out), max(fake_oes_out), _gz['oe_out'], _gz['p_out']))
p('   по регистрациям O/E %.2f–%.2f (два ложных признака дали 0.73 при p 0.08–0.15) — настоящий 0.67 (p=0.037) на самом краю того, что даёт случайное разбиение.' % (
    min(fake_oes), max(fake_oes)))
p()
p('ИТОГ: тенями контента, дня, зоны, даты, объёма дня, порядка постановки и cf-аккаунта эффект не объясняется — при самой жёсткой страте знак тот же')
p('(рег O/E 0.67, выход 0.92), ложные признаки дефицита выхода не дают. Но заявленные «в 1.6 раза меньше регистраций, p≈0.02» завышены дважды:')
p('(а) тенью паттерна внутри пула — по правилам самой гипотезы (тот же паттерн) это O/E 0.67–0.71 при p 0.04–0.09;')
p('(б) тяжёлым хвостом — весь дефицит сверх −20% сделан 19 «горячими» обычными доменами; на устойчивых исходах (≥1 рег, потолок 2, без горячих)')
p('    O/E 0.75–0.90 и ничего не значимо. Выход −8% (p=0.002) — единственная устойчивая часть, но она внутри коридора опровержения 0.85–1.15 по критерию постановки.')
p('Вердикт «частично» выживает только как «выход чуть ниже (−8%), регистрации — слабый сигнал того же знака»; формулировку про регистрации надо ужать (см. fix).')

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT)

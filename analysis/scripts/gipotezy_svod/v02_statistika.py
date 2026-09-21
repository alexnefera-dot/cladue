#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик к гипотезе №2 (метки, похожие на сгенерированные). Угол: СТАТИСТИКА.

Проверяем:
  1. Суммы, а не средние по доменам — сверяем с методом тестировщика (O/E из сумм пула).
  2. Перебор срезов: тестировщик посчитал 13 сравнений × 2 метрики. Делаем ОДНУ перестановку подтипов
     внутри пула (и внутри паттерна имени) и считаем все срезы сразу; семейный p по методу min-p
     (Westfall–Young): p семейства = доля перестановок, где лучший (минимальный) p по любому срезу
     не больше наблюдённого лучшего p.
  3. Объёмы регистраций в группах: где < 20 — не доказательство.
  4. Держится ли на 1–3 доменах: доля регистраций у топ-3 доменов в каждой группе; удаляем топ-3
     домена по регистрациям в группе признака и в группе сравнения (в каждом срезе) и пересчитываем
     O/E и перестановочный p. Плюс leave-one-pool-out и вклад пулов в дефицит.
  5. Независимая реплика: в паттернах casino_prefix / casino_infix тоже есть метки с цифрами и без —
     их тестировщик не трогал. Если «цифры в имени вредят», там должно быть то же самое.

Только stdlib. Вывод — в stdout и в analysis/export/gipotezy_svod/v02_statistika.txt
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
OUT = os.path.join(OUT_DIR, 'v02_statistika.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM_FAMILY = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
N_PERM = 10000
OUTLIERS = {'3615.team', '3286.team'}
random.seed(7)

_lines = []


def p(*args):
    s = ' '.join(str(a) for a in args)
    print(s)
    _lines.append(s)


def to_int(s):
    s = (s or '').strip()
    return int(float(s)) if s else 0


# ---------------------------------------------------------------- чтение и фильтр (как у тестировщика)
with open(SRC, encoding='utf-8', newline='') as fh:
    rows_all = list(csv.DictReader(fh))
rows = [r for r in rows_all if r['домен'] not in OUTLIERS
        and r['окно закрыто'] == 'да' and r['дней'] != '1'
        and r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
p('Файл:', SRC)
p('Всего доменов: %d; после фильтра тестировщика (без выбросов, окно закрыто, дней≠1, контент записан): %d' % (
    len(rows_all), len(rows)))

DATE_RE = re.compile(r'^\d{4}[a-z]+$')


def subtype(r):
    l = r['домен'].split('.')[0]
    pat = r['паттерн имени']
    if pat == 'numeric':
        return 'num0' if l[0] == '0' else 'numN'
    if pat == 'alpha_other':
        if DATE_RE.match(l):
            return 'date'
        if l.isalpha():
            return 'alpha%d' % len(l)
        return 'mix%d' % len(l)
    if any(ch.isdigit() for ch in l):
        return pat + '_dig'
    return pat + '_alpha'


for r in rows:
    r['_lab'] = r['домен'].split('.')[0]
    r['_pat'] = r['паттерн имени']
    r['_sub'] = subtype(r)
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_out3'] = to_int(r['вышли за 3 суток'])
    r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_fd'] = to_int(r['ФД в окне 3 суток'])
    r['_pool'] = (r['набор контента'], r['день запуска'])

p()
p('Подтипы после фильтра (домены / сайтов / вышли за 3 суток / регистраций в окне):')
cnt = defaultdict(lambda: [0, 0, 0, 0])
for r in rows:
    a = cnt[r['_sub']]
    a[0] += 1
    a[1] += r['_sites']
    a[2] += r['_out3']
    a[3] += r['_regs']
for k in sorted(cnt):
    a = cnt[k]
    p('  %-20s %5d %8d %7d %5d' % (k, *a))

# ---------------------------------------------------------------- срезы
# Срез = (имя, множество подтипов-участников, множество подтипов-признака, направление «хуже»)
ALPHA_ALL = {'alpha3', 'alpha4', 'alpha5', 'alpha6', 'alpha7', 'alpha8', 'alpha9', 'alpha10', 'alpha11'}
MIX_ALL = {'mix3', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9', 'mix10', 'mix11'}
alpha_subs = {r['_sub'] for r in rows if r['_pat'] == 'alpha_other'}
ALPHA_ALL &= alpha_subs
MIX_ALL &= alpha_subs
DIGIT_ALL = MIX_ALL | {'date'}

SLICES = [
    ('A  ведущий 0 vs numeric', {'num0', 'numN'}, {'num0'}),
    ('B  смесь-4 vs буквы-4', {'mix4', 'alpha4'}, {'mix4'}),
    ('C  длина-3 vs буквы-4', {'mix3', 'alpha3', 'alpha4'}, {'mix3', 'alpha3'}),
    ('C2 смесь-3 vs смесь-4', {'mix3', 'mix4'}, {'mix3'}),
    ('D  код даты vs буквы-4', {'date', 'alpha4'}, {'date'}),
    ('Об. alpha с цифрой vs буквы', DIGIT_ALL | ALPHA_ALL, DIGIT_ALL),
    ('Об. без кода даты', MIX_ALL | ALPHA_ALL, MIX_ALL),
    ('GEN все признаки vs обычные', {'num0', 'numN'} | DIGIT_ALL | ALPHA_ALL, {'num0'} | DIGIT_ALL),
    ('GEN2 без кода даты (пост-хок)', {'num0', 'numN'} | MIX_ALL | ALPHA_ALL, {'num0'} | MIX_ALL),
]
PREREG_NAMES = {'A  ведущий 0 vs numeric', 'B  смесь-4 vs буквы-4', 'C  длина-3 vs буквы-4',
                'D  код даты vs буквы-4', 'Об. alpha с цифрой vs буквы', 'GEN все признаки vs обычные'}


def slice_oe(rs, subs, subset, feat):
    """O/E по выходу и регистрациям для среза. rs — строки; subs — текущие подтипы (список по индексу).
    Возвращает (O_out, E_out, O_reg, E_reg, n_feat, n_ref, pools, O_fd, E_fd)."""
    pools = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0])
    # [sites_all, out_all, reg_all, fd_all, n_feat, n_ref, sites_f, out_f, reg_f, fd_f, _]
    for i, r in enumerate(rs):
        s = subs[i]
        if s not in subset:
            continue
        a = pools[r['_pool']]
        a[0] += r['_sites']
        a[1] += r['_out3']
        a[2] += r['_regs']
        a[3] += r['_fd']
        if s in feat:
            a[4] += 1
            a[6] += r['_sites']
            a[7] += r['_out3']
            a[8] += r['_regs']
            a[9] += r['_fd']
        else:
            a[5] += 1
    O_out = E_out = O_reg = E_reg = O_fd = E_fd = 0.0
    nf = nr = npools = 0
    for a in pools.values():
        if a[4] == 0 or a[5] == 0 or a[0] == 0:
            continue
        npools += 1
        nf += a[4]
        nr += a[5]
        O_out += a[7]
        O_reg += a[8]
        O_fd += a[9]
        E_out += a[1] / a[0] * a[6]
        E_reg += a[2] / a[0] * a[6]
        E_fd += a[3] / a[0] * a[6]
    return O_out, E_out, O_reg, E_reg, nf, nr, npools, O_fd, E_fd


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    s = 0.0
    for i in range(int(k) + 1):
        s += math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1))
    return min(1.0, s)


# ---------------------------------------------------------------- 1. воспроизведение наблюдённого
p()
p('=' * 100)
p('1. ВОСПРОИЗВЕДЕНИЕ. Суммы по группам (O) против ожидания из долей пула (E) — как у тестировщика.')
p('   Метод тестировщика — суммы, не средние по доменам от долей: здесь претензии нет.')
p('=' * 100)
work = [r for r in rows if r['_pat'] in ('numeric', 'alpha_other')]
subs_obs = [r['_sub'] for r in work]
obs = {}
p('%-32s %5s %5s/%-5s %7s %7s %5s | %5s %6s %5s %7s | %4s %5s' % (
    'срез', 'пулов', 'приз', 'срав', 'O вых', 'E вых', 'O/E', 'O рег', 'E рег', 'O/E', 'пуасс.', 'ФД O', 'ФД E'))
for name, subset, feat in SLICES:
    o = slice_oe(work, subs_obs, subset, feat)
    obs[name] = o
    p('%-32s %5d %5d/%-5d %7d %7.1f %5.2f | %5d %6.2f %5.2f %7.3f | %4d %5.2f' % (
        name, o[6], o[4], o[5], o[0], o[1], o[0] / o[1], o[2], o[3], o[2] / o[3] if o[3] else float('nan'),
        poisson_cdf(o[2], o[3]), o[7], o[8]))

# ---------------------------------------------------------------- 2. объёмы регистраций
p()
p('=' * 100)
p('2. ОБЪЁМЫ РЕГИСТРАЦИЙ В ГРУППАХ (правило: < 20 регистраций в группе — не доказательство)')
p('=' * 100)
for name, subset, feat in SLICES:
    o = obs[name]
    # регистрации группы сравнения в тех же пулах
    idx = [i for i, r in enumerate(work) if subs_obs[i] in subset]
    poolsets = defaultdict(lambda: [0, 0, 0, 0])
    for i in idx:
        r = work[i]
        a = poolsets[r['_pool']]
        if subs_obs[i] in feat:
            a[0] += 1
            a[2] += r['_regs']
        else:
            a[1] += 1
            a[3] += r['_regs']
    reg_f = sum(a[2] for a in poolsets.values() if a[0] and a[1])
    reg_r = sum(a[3] for a in poolsets.values() if a[0] and a[1])
    flag = 'МАЛО (<20)' if reg_f < 20 else 'ok'
    p('  %-32s регистраций: признак %3d, сравнение %3d  -> группа признака: %s' % (name, reg_f, reg_r, flag))

# ---------------------------------------------------------------- 3. семейный перестановочный тест
p()
p('=' * 100)
p('3. ПЕРЕБОР СРЕЗОВ: одна перестановка подтипов внутри (пул × паттерн имени), все %d срезов × 2 метрики сразу.' % len(SLICES))
p('   Семейный p (min-p, Westfall–Young): доля перестановок, в которых лучший p по ЛЮБОМУ срезу не больше')
p('   лучшего наблюдённого p. Перестановок: %d.' % N_PERM_FAMILY)
p('=' * 100)
groups = defaultdict(list)
for i, r in enumerate(work):
    groups[(r['_pool'], r['_pat'])].append(i)
group_lists = [g for g in groups.values() if len(g) >= 2]
stat_names = []
for name, _, _ in SLICES:
    stat_names.append((name, 'вых'))
    stat_names.append((name, 'рег'))
obs_stats = []
for name, subset, feat in SLICES:
    o = obs[name]
    obs_stats.append(o[0] / o[1])
    obs_stats.append(o[2] / o[3] if o[3] else 1.0)

perm_stats = [[] for _ in stat_names]
subs_cur = list(subs_obs)
for it in range(N_PERM_FAMILY):
    for g in group_lists:
        labs = [subs_cur[i] for i in g]
        random.shuffle(labs)
        for i, l in zip(g, labs):
            subs_cur[i] = l
    for si, (name, subset, feat) in enumerate(SLICES):
        o = slice_oe(work, subs_cur, subset, feat)
        perm_stats[2 * si].append(o[0] / o[1] if o[1] else 1.0)
        perm_stats[2 * si + 1].append(o[2] / o[3] if o[3] else 1.0)

# p по каждому срезу из общей перестановки (односторонний «хуже»)
per_slice_p = []
p('  Односторонние p «хуже» из общей перестановки (для сверки с тестировщиком):')
for k, (name, m) in enumerate(stat_names):
    arr = perm_stats[k]
    pk = sum(1 for v in arr if v <= obs_stats[k] + 1e-12) / len(arr)
    per_slice_p.append(pk)
    p('    %-32s %-4s O/E = %.2f  p = %.4f' % (name, m, obs_stats[k], pk))

# min-p семейства
def family_minp(indices, label):
    n = N_PERM_FAMILY
    # ранговые p для каждой перестановки по каждому срезу
    obs_min = min(per_slice_p[k] for k in indices)
    # для каждой перестановки i: p_k(i) = доля j с stat_k(j) <= stat_k(i)
    minp_perm = [1.0] * n
    for k in indices:
        arr = perm_stats[k]
        order = sorted(range(n), key=lambda j: arr[j])
        # p для i = (число значений <= arr[i]) / n; учитываем связки
        srt = [arr[j] for j in order]
        # позиция последнего элемента <= значения
        import bisect
        for i in range(n):
            cnt_le = bisect.bisect_right(srt, arr[i] + 1e-12)
            pi = cnt_le / n
            if pi < minp_perm[i]:
                minp_perm[i] = pi
    fam = sum(1 for v in minp_perm if v <= obs_min + 1e-12) / n
    best = min(indices, key=lambda k: per_slice_p[k])
    p('  %s: срезов %d; лучший наблюдённый p = %.4f (%s, %s); СЕМЕЙНЫЙ p = %.3f' % (
        label, len(indices), obs_min, stat_names[best][0].strip(), stat_names[best][1], fam))
    return fam


fam_all = family_minp(list(range(len(stat_names))), 'Все срезы × обе метрики')
fam_reg = family_minp([k for k, (n_, m) in enumerate(stat_names) if m == 'рег'], 'Все срезы, только регистрации')
fam_out = family_minp([k for k, (n_, m) in enumerate(stat_names) if m == 'вых'], 'Все срезы, только выход')
prereg_idx = [k for k, (n_, m) in enumerate(stat_names) if n_ in PREREG_NAMES]
fam_pre = family_minp(prereg_idx, 'Только заранее заданные срезы (A,B,C,D,объед.,GEN) × обе метрики')
prereg_reg_idx = [k for k, (n_, m) in enumerate(stat_names) if n_ in PREREG_NAMES and m == 'рег']
fam_pre_reg = family_minp(prereg_reg_idx, 'Только заранее заданные срезы, регистрации')
noposthoc_idx = [k for k, (n_, m) in enumerate(stat_names) if 'пост-хок' not in n_]
fam_nph = family_minp(noposthoc_idx, 'Все срезы кроме пост-хок GEN2 × обе метрики')

# ---------------------------------------------------------------- 4. концентрация: домены и пулы
p()
p('=' * 100)
p('4. ДЕРЖИТСЯ ЛИ НА 1–3 ДОМЕНАХ / ПУЛАХ')
p('=' * 100)


def slice_rows(subset, feat):
    """Строки среза (только пулы с обоими типами) с флагом признака."""
    idx = [i for i, r in enumerate(work) if subs_obs[i] in subset]
    pools = defaultdict(list)
    for i in idx:
        pools[work[i]['_pool']].append(i)
    out = []
    for k, v in pools.items():
        f = [i for i in v if subs_obs[i] in feat]
        g = [i for i in v if subs_obs[i] not in feat]
        if f and g:
            out.extend((work[i], subs_obs[i] in feat) for i in v)
    return out


def oe_perm(pairs, n_perm=N_PERM, seed=11):
    """O/E по выходу и регистрациям + перестановочный p (признак внутри пула), как у тестировщика."""
    rnd = random.Random(seed)
    pools = defaultdict(list)
    for r, f in pairs:
        pools[r['_pool']].append((r, f))
    used = {k: v for k, v in pools.items() if any(f for _, f in v) and any(not f for _, f in v)}
    rate_out, rate_reg = {}, {}
    for k, v in used.items():
        S = sum(r['_sites'] for r, _ in v)
        rate_out[k] = sum(r['_out3'] for r, _ in v) / S
        rate_reg[k] = sum(r['_regs'] for r, _ in v) / S
    feat = [(r, k) for k, v in used.items() for r, f in v if f]
    O_out = sum(r['_out3'] for r, _ in feat)
    O_reg = sum(r['_regs'] for r, _ in feat)
    E_out = sum(rate_out[k] * r['_sites'] for r, k in feat)
    E_reg = sum(rate_reg[k] * r['_sites'] for r, k in feat)
    oe_out = O_out / E_out if E_out else float('nan')
    oe_reg = O_reg / E_reg if E_reg else float('nan')
    pool_lists = [([r for r, _ in v], sum(1 for _, f in v if f), k) for k, v in used.items()]
    c_out = c_reg = 0
    for _ in range(n_perm):
        po = pe = ro = re_ = 0.0
        for v, m, k in pool_lists:
            rnd.shuffle(v)
            for r in v[:m]:
                po += r['_out3']
                ro += r['_regs']
                pe += rate_out[k] * r['_sites']
                re_ += rate_reg[k] * r['_sites']
        if pe and po / pe <= oe_out + 1e-12:
            c_out += 1
        if re_ and ro / re_ <= oe_reg + 1e-12:
            c_reg += 1
    n_f = len(feat)
    n_r = sum(len(v) for v in used.values()) - n_f
    return dict(pools=len(used), nf=n_f, nr=n_r, O_out=O_out, E_out=E_out, oe_out=oe_out,
                p_out=c_out / n_perm if n_perm else float('nan'),
                O_reg=O_reg, E_reg=E_reg, oe_reg=oe_reg, p_reg=c_reg / n_perm if n_perm else float('nan'),
                pois=poisson_cdf(O_reg, E_reg),
                regs_ref=sum(r['_regs'] for v in used.values() for r, f in v if not f))


def fmt_res(tag, d):
    p('    %-52s пулов %3d, %3d/%3d; выход O/E %.2f (p %.3f); рег O=%d E=%.1f O/E %.2f (перест. p %.3f, пуассон %.3f); рег сравн. %d' % (
        tag, d['pools'], d['nf'], d['nr'], d['oe_out'], d['p_out'], d['O_reg'], d['E_reg'], d['oe_reg'], d['p_reg'], d['pois'], d['regs_ref']))


for name, subset, feat in SLICES:
    if name.startswith('C2') or name.startswith('D '):
        continue
    pairs = slice_rows(subset, feat)
    fr = sorted([r for r, f in pairs if f], key=lambda r: -r['_regs'])
    rr = sorted([r for r, f in pairs if not f], key=lambda r: -r['_regs'])
    reg_f = sum(r['_regs'] for r in fr)
    reg_r = sum(r['_regs'] for r in rr)
    top3_f = [(r['домен'], r['_regs']) for r in fr[:3]]
    top3_r = [(r['домен'], r['_regs']) for r in rr[:3]]
    p()
    p('  --- %s ---' % name.strip())
    p('    регистрации признака: %d у %d доменов (с регистрацией: %d); топ-3: %s -> %d из %d (%.0f%%)' % (
        reg_f, len(fr), sum(1 for r in fr if r['_regs']), top3_f, sum(v for _, v in top3_f), reg_f,
        100.0 * sum(v for _, v in top3_f) / reg_f if reg_f else 0))
    p('    регистрации сравнения: %d у %d доменов (с регистрацией: %d); топ-3: %s -> %d из %d (%.0f%%)' % (
        reg_r, len(rr), sum(1 for r in rr if r['_regs']), top3_r, sum(v for _, v in top3_r), reg_r,
        100.0 * sum(v for _, v in top3_r) / reg_r if reg_r else 0))
    base = oe_perm(pairs, n_perm=4000)
    fmt_res('как есть', base)
    drop_f = {r['домен'] for r in fr[:3]}
    drop_r = {r['домен'] for r in rr[:3]}
    fmt_res('без топ-3 доменов по рег. в ОБЕИХ группах', oe_perm([(r, f) for r, f in pairs if r['домен'] not in drop_f | drop_r], n_perm=4000))
    fmt_res('без топ-3 только в группе сравнения', oe_perm([(r, f) for r, f in pairs if r['домен'] not in drop_r], n_perm=4000))
    fmt_res('без топ-3 только в группе признака', oe_perm([(r, f) for r, f in pairs if r['домен'] not in drop_f], n_perm=4000))
    drop_r5 = {r['домен'] for r in rr[:5]}
    drop_f5 = {r['домен'] for r in fr[:5]}
    fmt_res('без топ-5 в обеих группах', oe_perm([(r, f) for r, f in pairs if r['домен'] not in drop_f5 | drop_r5], n_perm=4000))
    # вклад пулов в дефицит регистраций
    pools = defaultdict(list)
    for r, f in pairs:
        pools[r['_pool']].append((r, f))
    contrib = []
    for k, v in pools.items():
        S = sum(r['_sites'] for r, _ in v)
        rate = sum(r['_regs'] for r, _ in v) / S
        Ef = sum(rate * r['_sites'] for r, f in v if f)
        Of = sum(r['_regs'] for r, f in v if f)
        contrib.append((Ef - Of, k, Of, Ef, sum(1 for _, f in v if f), sum(1 for _, f in v if not f), sum(r['_regs'] for r, f in v if not f)))
    contrib.sort(reverse=True)
    tot_def = sum(c[0] for c in contrib)
    top3_def = sum(c[0] for c in contrib[:3])
    p('    дефицит регистраций (E−O) = %.1f по %d пулам; топ-3 пула дают %.1f (%.0f%%): %s' % (
        tot_def, len(contrib), top3_def, 100.0 * top3_def / tot_def if tot_def else 0,
        '; '.join('%s/%s: приз. O=%d E=%.1f (%d дом.), сравн. %d рег (%d дом.)' % (k[0][:18], k[1][5:], Of, Ef, nf_, nr_, rr_)
                  for d_, k, Of, Ef, nf_, nr_, rr_ in contrib[:3])))
    # leave-one-pool-out
    oes = []
    for drop_k in pools:
        sub = [(r, f) for r, f in pairs if r['_pool'] != drop_k]
        d = oe_perm(sub, n_perm=0)
        oes.append((d['oe_reg'], d['pois'], drop_k))
    oes.sort()
    p('    leave-one-pool-out: O/E рег от %.2f до %.2f; пуассон p от %.3f до %.3f (макс. при исключении пула %s/%s)' % (
        oes[0][0], oes[-1][0], min(x[1] for x in oes), max(x[1] for x in oes), oes[-1][2][0][:18], oes[-1][2][1][5:]))
    # leave-one-domain-out
    oes_d = []
    for drop_d in {r['домен'] for r, _ in pairs if r['_regs'] > 0}:
        sub = [(r, f) for r, f in pairs if r['домен'] != drop_d]
        d = oe_perm(sub, n_perm=0)
        oes_d.append((d['pois'], d['oe_reg'], drop_d))
    oes_d.sort()
    p('    leave-one-domain-out (домены с рег.): пуассон p от %.3f до %.3f; O/E рег от %.2f до %.2f (макс. p при исключении %s)' % (
        oes_d[0][0], oes_d[-1][0], min(x[1] for x in oes_d), max(x[1] for x in oes_d), oes_d[-1][2]))

# ---------------------------------------------------------------- 5. реплика на casino-паттернах
p()
p('=' * 100)
p('5. НЕЗАВИСИМАЯ РЕПЛИКА: casino_prefix / casino_infix — метки с цифрами против чисто буквенных (тестировщик не трогал).')
p('   Если «цифры в имени = сгенерированное = хуже», здесь должно быть то же. Пул контент+день, тот же O/E.')
p('=' * 100)
cas = [r for r in rows if r['_pat'] in ('casino_prefix', 'casino_infix')]
for pat in ('casino_prefix', 'casino_infix', 'оба casino-паттерна вместе'):
    if pat.startswith('оба'):
        sub_rows = cas
    else:
        sub_rows = [r for r in cas if r['_pat'] == pat]
    pairs = [(r, r['_sub'].endswith('_dig')) for r in sub_rows]
    d = oe_perm(pairs, n_perm=N_PERM, seed=5)
    p('  %-28s: пулов %d; с цифрами %d, буквы %d; выход O/E %.2f (p %.3f); регистрации O=%d E=%.1f O/E %.2f (перест. p %.3f, пуассон %.3f); рег сравн. %d' % (
        pat, d['pools'], d['nf'], d['nr'], d['oe_out'], d['p_out'], d['O_reg'], d['E_reg'], d['oe_reg'], d['p_reg'], d['pois'], d['regs_ref']))
# и в общей куче: все паттерны, «с цифрой» против «без цифры» внутри пула и паттерна
p()
p('  Все четыре паттерна сразу: «в метке есть цифра / ведущий ноль» против «нет» внутри пула × паттерн (numeric: ноль против не-ноль):')
allp = [r for r in rows]
def is_gen_any(r):
    if r['_pat'] == 'numeric':
        return r['_sub'] == 'num0'
    return any(ch.isdigit() for ch in r['_lab'])
# страта пул × паттерн
for r in allp:
    r['_pool_pat'] = (r['_pool'], r['_pat'])
saved = {}
for r in allp:
    saved[r['домен']] = r['_pool']
    r['_pool'] = r['_pool_pat']
d = oe_perm([(r, is_gen_any(r)) for r in allp], n_perm=N_PERM, seed=9)
for r in allp:
    r['_pool'] = saved[r['домен']]
p('    пулов %d; признак %d, обычные %d; выход O/E %.2f (p %.3f); регистрации O=%d E=%.1f O/E %.2f (перест. p %.3f, пуассон %.3f); рег сравн. %d' % (
    d['pools'], d['nf'], d['nr'], d['oe_out'], d['p_out'], d['O_reg'], d['E_reg'], d['oe_reg'], d['p_reg'], d['pois'], d['regs_ref']))

# ---------------------------------------------------------------- 6. GEN: тот же паттерн, а не любой
p()
p('=' * 100)
p('6. ОБЪЕДИНЁННЫЙ ТЕСТ GEN: гипотеза говорит «против обычных меток ТОГО ЖЕ паттерна», но у тестировщика')
p('   перестановка признака в GEN идёт внутри пула между паттернами (num0 может «стать» буквенной alpha_other).')
p('   Пересчёт со стратой пул × паттерн (ячейки, где есть и признак, и обычные того же паттерна).')
p('=' * 100)
gen_rows = [r for r in work]
for r in gen_rows:
    r['_pool_pat'] = (r['_pool'], r['_pat'])
saved = {r['домен']: r['_pool'] for r in gen_rows}
def is_gen(r):
    return r['_sub'] == 'num0' or (r['_pat'] == 'alpha_other' and any(ch.isdigit() for ch in r['_lab']))
def is_gen2(r):
    return is_gen(r) and r['_sub'] != 'date'
d_pool = oe_perm([(r, is_gen(r)) for r in gen_rows], n_perm=N_PERM, seed=21)
for r in gen_rows:
    r['_pool'] = r['_pool_pat']
d_pp = oe_perm([(r, is_gen(r)) for r in gen_rows], n_perm=N_PERM, seed=21)
d_pp2 = oe_perm([(r, is_gen2(r)) for r in gen_rows if r['_sub'] != 'date'], n_perm=N_PERM, seed=21)
for r in gen_rows:
    r['_pool'] = saved[r['домен']]
fmt_res('GEN, страта пул (как у тестировщика)', d_pool)
fmt_res('GEN, страта пул × паттерн', d_pp)
fmt_res('GEN2 без кода даты, страта пул × паттерн', d_pp2)

# нулевые распределения O/E рег для GEN при двух схемах перестановки
def null_dist(pairs, scheme, n=4000, seed=33):
    rnd = random.Random(seed)
    pools = defaultdict(list)
    for r, f in pairs:
        pools[r['_pool']].append((r, f))
    used = {k: v for k, v in pools.items() if any(f for _, f in v) and any(not f for _, f in v)}
    rate = {}
    for k, v in used.items():
        S = sum(r['_sites'] for r, _ in v)
        rate[k] = sum(r['_regs'] for r, _ in v) / S
    vals = []
    if scheme == 'pool':
        lists = [([r for r, _ in v], sum(1 for _, f in v if f), k) for k, v in used.items()]
        for _ in range(n):
            ro = re_ = 0.0
            for v, m, k in lists:
                rnd.shuffle(v)
                for r in v[:m]:
                    ro += r['_regs']
                    re_ += rate[k] * r['_sites']
            vals.append(ro / re_)
    else:
        cells = defaultdict(list)
        for k, v in used.items():
            for r, f in v:
                cells[(k, r['_pat'])].append((r, f))
        lists = []
        for (k, pat), v in cells.items():
            lists.append(([r for r, _ in v], sum(1 for _, f in v if f), k))
        for _ in range(n):
            ro = re_ = 0.0
            for v, m, k in lists:
                rnd.shuffle(v)
                for r in v[:m]:
                    ro += r['_regs']
                    re_ += rate[k] * r['_sites']
            vals.append(ro / re_)
    mean = sum(vals) / len(vals)
    sd = (sum((x - mean) ** 2 for x in vals) / len(vals)) ** 0.5
    return mean, sd, sum(1 for x in vals if x <= 0.6107 + 1e-9) / len(vals)
pairs_gen = [(r, is_gen(r)) for r in gen_rows]
m1, s1, p1 = null_dist(pairs_gen, 'pool')
m2, s2, p2 = null_dist(pairs_gen, 'pool_pat')
p('  Нулевое распределение O/E рег для GEN (E из пула, как у тестировщика):')
p('    перестановка внутри пула (между паттернами): среднее %.3f, sd %.3f, доля <= 0.61: %.3f' % (m1, s1, p1))
p('    перестановка внутри пула × паттерн:          среднее %.3f, sd %.3f, доля <= 0.61: %.3f' % (m2, s2, p2))
# сколько доменов признака сидят в ячейках пул×паттерн без обычных того же паттерна
cells = defaultdict(list)
for r, f in pairs_gen:
    cells[(r['_pool'], r['_pat'])].append(f)
pools_used = {k for k, v in defaultdict(list, {}).items()}
stuck = 0
tot = 0
for (k, pat), v in cells.items():
    if any(v) and not all(v):
        continue
    if any(v):
        stuck += sum(v)
n_feat_used = d_pool['nf']
p('  Доменов признака в GEN-пулах тестировщика, у которых в пуле НЕТ обычного домена того же паттерна: %d из %d' % (
    d_pool['nf'] - d_pp['nf'], d_pool['nf']))
# их регистрации и ожидание
lost = [r for r in gen_rows if is_gen(r)]

# ---------------------------------------------------------------- 6. сводка
p()
p('=' * 100)
p('СВОДКА СКЕПТИКА')
p('=' * 100)
p('Семейный p (все %d срезов × 2 метрики): %.3f; только регистрации: %.3f; только выход: %.3f;' % (len(SLICES), fam_all, fam_reg, fam_out))
p('только заранее заданные срезы: %.3f (регистрации: %.3f); без пост-хок GEN2: %.3f.' % (fam_pre, fam_pre_reg, fam_nph))

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT)

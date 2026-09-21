#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептик, угол «тени» (конфаундинг) к гипотезе №3 (шаблон Theme2).

Что проверяем поверх h03_theme2_template.py:
  1. Решающие партии (19.08 23:00/198 и 20.08 12:00/199) на уровне ДОМЕНА:
     медианы, ранговый тест (стратифицированный Манн–Уитни через перестановку),
     двусторонний p к статистике тестировщика, каждая партия отдельно.
  2. Влияние одного домена: leave-one-out по 33 доменам решающих партий;
     отдельно — без 1908.team (119 вышедших, 5 регистраций).
  3. Регистрации на уровне домена (есть/нет) внутри партий; без 1908.team.
  4. Ещё более жёсткая страта: партия × паттерн имени; партия × «аккаунт свежий».
  5. Сеанс постановки по номерам аккаунтов: вечер 20.08. Theme2 стоит на wm 108–137,
     сразу за ними Theme1 на wm 138–142 (2328 в 21:00, 2650/2872/3164/fjnv в 22:00),
     а остальные Theme1 в 22:00 — на повторных аккаунтах wm 4–23. Сравниваем
     Theme2 с Theme1 того же сеанса и Theme1 свежие против Theme1 повторные
     (тот же шаблон, тот же час — масштаб «тени сеанса»).
  6. Страта = сеанс (день × блок номеров wm): решающие партии + вечерний сеанс,
     все 47 Theme2 получают пару. O/E, перестановка, ранговый тест.
  7. Плацебо: пары чисто-Theme1 партий тех же дней как «псевдо-Theme2»:
     распределение грубого O/E по дню — насколько 0,54 выделяется на фоне
     разброса между партиями одного шаблона.
  8. Позиция в сеансе (номер wm) против выхода внутри решающих партий.

Только stdlib. Вывод — stdout и analysis/export/gipotezy_svod/v03_teni.txt
"""
import csv
import math
import os
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUT_DIR = os.path.join(BASE, 'export', 'gipotezy_svod')
OUT = os.path.join(OUT_DIR, 'v03_teni.txt')
os.makedirs(OUT_DIR, exist_ok=True)

N_PERM = 10000
OUTLIERS = {'3615.team', '3286.team'}
DAYS = ('2026-08-19', '2026-08-20')
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
    return '—' if x is None else ('%.' + str(d) + 'f') % x


def ratio(o, e):
    return None if e <= 0 else o / e


def poisson_le(k, lam):
    if lam <= 0:
        return 1.0
    return min(1.0, sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(int(k) + 1)))


def hypergeom_le(k, K, n, N):
    """P(X <= k), X — число «успехов» в выборке n из N, где K успехов всего."""
    def c(a, b):
        return math.comb(a, b) if 0 <= b <= a else 0
    tot = c(N, n)
    return sum(c(K, i) * c(N - K, n - i) for i in range(0, int(k) + 1)) / tot


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


# ---------------------------------------------------------------- чтение и срез (как в h03)
with open(SRC, encoding='utf-8') as fh:
    rows = list(csv.DictReader(fh))
for r in rows:
    r['_sites'] = fnum(r['сайтов в окне'])
    r['_v3'] = fnum(r['вышли за 3 суток'])
    r['_v7'] = fnum(r['вышли за 7 суток'])
    r['_v1'] = fnum(r['вышли за 1 сутки'])
    r['_reg'] = fnum(r['регистраций в окне 3 суток'])
    r['_hour'] = int(fnum(r['час запуска']))
    r['_day'] = r['день запуска'][5:]
    r['_t'] = r['шаблон']
    r['_wm'] = int(fnum(r['аккаунт вебмастера']))
    r['_cf'] = int(fnum(r['cf-аккаунт']))
    r['_rate'] = r['_v3'] / r['_sites'] if r['_sites'] else 0.0
    r['_hasreg'] = 1.0 if r['_reg'] > 0 else 0.0

main = [r for r in rows if r['день запуска'] in DAYS and r['домен'] not in OUTLIERS
        and r['окно закрыто'] == 'да' and r['дней'] != '1' and r['зона'] == 'team']
p('Файл:', SRC)
p('Срез (как в h03): team, 19–20.08, окно закрыто, дней ≠ 1, без выбросов:', len(main), 'доменов;',
  'Theme2:', sum(1 for r in main if r['_t'] == 'Theme2'), '; Theme1:', sum(1 for r in main if r['_t'] == 'Theme1'))
p('Набор контента:', dict(Counter(r['набор контента'] for r in main)), '— страта «контент + день + зона» = «день».')
p()


def batch_key(r):
    return (r['_day'], r['_hour'], r['сайтов'])


batches = defaultdict(list)
for r in main:
    batches[batch_key(r)].append(r)
DEC_KEYS = [('08-19', 23, '198'), ('08-20', 12, '199')]
dec = [r for k in DEC_KEYS for r in batches[k]]


# ---------------------------------------------------------------- движок O/E + перестановка (как у тестировщика) + ранговый тест
def oe_stat(strata, assign, metric, label='Theme2', other='Theme1'):
    O = E = Eref = 0.0
    for v in strata:
        tot_m = sum(r[metric] for r in v)
        tot_s = sum(r['_sites'] for r in v)
        m_o = sum(r[metric] for r in v if assign[id(r)] == other)
        s_o = sum(r['_sites'] for r in v if assign[id(r)] == other)
        rp = tot_m / tot_s if tot_s else 0
        rr = m_o / s_o if s_o else 0
        for r in v:
            if assign[id(r)] == label:
                O += r[metric]
                E += rp * r['_sites']
                Eref += rr * r['_sites']
    return O, E, Eref


def rank_stat(strata, assign, metric='_rate', label='Theme2', other='Theme1'):
    """Стратифицированный Манн–Уитни: доля пар (Theme2, Theme1) внутри страты, где Theme2 < Theme1 (ничья = 0,5)."""
    u = 0.0
    pairs = 0
    for v in strata:
        a = [r[metric] for r in v if assign[id(r)] == label]
        b = [r[metric] for r in v if assign[id(r)] == other]
        for x in a:
            for y in b:
                u += 1.0 if x < y else (0.5 if x == y else 0.0)
        pairs += len(a) * len(b)
    return u / pairs if pairs else 0.5


def perm_test(strata, metric, n_perm=N_PERM, seed=1, rank=False):
    """Возвращает O, E, Eref, O/E_pool, O/E_ref, p_le (одностор.), p_two (двустор.), AUC, p_rank."""
    ds = [r for v in strata for r in v]
    obs_assign = {id(r): r['_t'] for r in ds}
    O, E, Eref = oe_stat(strata, obs_assign, metric)
    obs = ratio(O, E)
    auc = rank_stat(strata, obs_assign, metric if metric == '_rate' else metric)
    rnd = random.Random(seed)
    le = ge = 0
    rk = 0
    for _ in range(n_perm):
        assign = dict(obs_assign)
        for v in strata:
            labs = [r['_t'] for r in v]
            rnd.shuffle(labs)
            for r, lb in zip(v, labs):
                assign[id(r)] = lb
        Op, Ep, _ = oe_stat(strata, assign, metric)
        rp = ratio(Op, Ep)
        rp = 1.0 if rp is None else rp
        if rp <= obs + 1e-12:
            le += 1
        if rp >= obs - 1e-12:
            ge += 1
        if rank:
            if rank_stat(strata, assign, metric) >= auc - 1e-12:
                rk += 1
    return dict(O=O, E=E, Eref=Eref, oe=obs, oe_ref=ratio(O, Eref), p_le=le / n_perm,
                p_two=min(1.0, 2 * min(le, ge) / n_perm), auc=auc, p_rank=(rk / n_perm if rank else None),
                n_l=sum(1 for r in ds if r['_t'] == 'Theme2'), n_o=sum(1 for r in ds if r['_t'] == 'Theme1'))


def show(title, strata, metric='_v3', rank=True, n_perm=N_PERM):
    res = perm_test(strata, metric, n_perm=n_perm, rank=rank)
    p('  %s' % title)
    p('     Theme2 %d дом., Theme1 %d дом.; O = %d, E(пул) = %.1f → O/E = %s; E(Theme1) = %.1f → O/E = %s; перестановка p одностор. = %s, двустор. = %s' %
      (res['n_l'], res['n_o'], res['O'], res['E'], fmt(res['oe']), res['Eref'], fmt(res['oe_ref']), fmt(res['p_le'], 4), fmt(res['p_two'], 4)))
    if rank:
        p('     ранговый тест (единица — домен): доля пар «Theme2 ниже Theme1» = %.3f (0,5 = нет разницы), p = %s' % (res['auc'], fmt(res['p_rank'], 4)))
    return res


# ================================================================ 1. решающие партии на уровне домена
p('=' * 100)
p('1. РЕШАЮЩИЕ ПАРТИИ НА УРОВНЕ ДОМЕНА (единица анализа — домен, правило 1 методики)')
p('=' * 100)
for k in DEC_KEYS:
    v = batches[k]
    for t in ('Theme1', 'Theme2'):
        ds = sorted((r for r in v if r['_t'] == t), key=lambda r: r['_v3'])
        rates = [r['_rate'] * 100 for r in ds]
        p('  %s %02d:00 сайтов %s %s: n = %d, вышли3 по доменам: %s' % (k[0], k[1], k[2], t, len(ds), ' '.join('%d' % r['_v3'] for r in ds)))
        p('       выход %%: медиана %.1f, среднее %.1f, мин %.1f, макс %.1f; регистрации по доменам: %s' %
          (median(rates), sum(rates) / len(rates), min(rates), max(rates), ' '.join('%d' % r['_reg'] for r in ds)))
p()
p('  Ранговый тест и двусторонний p (10 000 перестановок метки внутри партии):')
r_dec = show('1a. Обе решающие партии вместе (как 5a у тестировщика):', [batches[k] for k in DEC_KEYS])
r_b1 = show('1b. Только 19.08 23:00/198 (4 Theme1 против 9 Theme2):', [batches[DEC_KEYS[0]]])
r_b2 = show('1c. Только 20.08 12:00/199 (12 Theme1 против 8 Theme2):', [batches[DEC_KEYS[1]]])
r_v1 = show('1d. Обе партии, показатель «вышли за 1 сутки»:', [batches[k] for k in DEC_KEYS], metric='_v1', rank=False)
r_v7 = show('1e. Обе партии, показатель «вышли за 7 суток»:', [batches[k] for k in DEC_KEYS], metric='_v7', rank=False)
p()

# ================================================================ 2. влияние одного домена
p('=' * 100)
p('2. ВЛИЯНИЕ ОДНОГО ДОМЕНА: leave-one-out по 33 доменам решающих партий (3000 перестановок на прогон)')
p('=' * 100)
loo = []
for drop in dec:
    strata = [[r for r in batches[k] if r is not drop] for k in DEC_KEYS]
    res = perm_test(strata, '_v3', n_perm=3000, seed=7)
    loo.append((drop['домен'], drop['_t'], drop['_v3'], res['oe_ref'], res['p_le'], res['oe']))
loo.sort(key=lambda x: -x[4])
p('  %-12s %-7s %6s %10s %10s %8s' % ('убран', 'шаблон', 'вышли3', 'O/E(T1)', 'O/E(пул)', 'p'))
for d, t, v, oe_ref, pl, oe in loo[:8]:
    p('  %-12s %-7s %6d %10s %10s %8s' % (d, t, v, fmt(oe_ref), fmt(oe), fmt(pl, 4)))
p('  ... (всего %d прогонов; p ≥ 0,05 у %d из %d, p ≥ 0,10 у %d)' %
  (len(loo), sum(1 for x in loo if x[4] >= 0.05), len(loo), sum(1 for x in loo if x[4] >= 0.10)))
strata_no1908 = [[r for r in batches[k] if r['домен'] != '1908.team'] for k in DEC_KEYS]
r_no1908 = show('2a. Без 1908.team (Theme1, 119 вышедших из 199, 5 регистраций):', strata_no1908)
top2 = max((r for r in dec if r['_t'] == 'Theme2'), key=lambda r: r['_v3'])
strata_sym = [[r for r in batches[k] if r['домен'] not in ('1908.team', top2['домен'])] for k in DEC_KEYS]
r_sym = show('2b. Симметрично: без лучшего Theme1 (1908.team) и лучшего Theme2 (%s, %d вышедших):' % (top2['домен'], top2['_v3']), strata_sym)
p()

# ================================================================ 3. регистрации на уровне домена
p('=' * 100)
p('3. РЕГИСТРАЦИИ ВНУТРИ РЕШАЮЩИХ ПАРТИЙ НА УРОВНЕ ДОМЕНА')
p('=' * 100)
v12 = batches[DEC_KEYS[1]]
t1 = [r for r in v12 if r['_t'] == 'Theme1']
t2 = [r for r in v12 if r['_t'] == 'Theme2']
k1 = sum(1 for r in t1 if r['_reg'] > 0)
k2 = sum(1 for r in t2 if r['_reg'] > 0)
p('  20.08 12:00/199: доменов с ≥1 регистрацией: Theme1 %d из %d, Theme2 %d из %d (в 19.08 23:00 регистраций нет ни у кого)' % (k1, len(t1), k2, len(t2)))
p('     точный гипергеометрический тест P(у Theme2 ≤ %d из %d при %d «успешных» на %d доменов) = %s' %
  (k2, len(t2), k1 + k2, len(v12), fmt(hypergeom_le(k2, k1 + k2, len(t2), len(v12)), 3)))
reg1 = sum(r['_reg'] for r in t1)
reg1_no = sum(r['_reg'] for r in t1 if r['домен'] != '1908.team')
s1_no = sum(r['_sites'] for r in t1 if r['домен'] != '1908.team')
s2 = sum(r['_sites'] for r in t2)
reg2 = sum(r['_reg'] for r in t2)
e_no = reg1_no / s1_no * s2
p('  Регистрации: Theme1 %d (из них 5 у 1908.team и 3 у cfpm.team), Theme2 %d.' % (reg1, reg2))
p('     без 1908.team: Theme1 %d на %d сайтов → E для Theme2 = %.2f, O = %d, O/E = %s, пуассон P(X ≤ %d) = %s' %
  (reg1_no, s1_no, e_no, reg2, fmt(ratio(reg2, e_no)), reg2, fmt(poisson_le(reg2, e_no), 3)))
e_pool_no = (reg1_no + reg2) / (s1_no + s2) * s2
p('     без 1908.team, E по пулу = %.2f → O/E = %s, пуассон = %s' % (e_pool_no, fmt(ratio(reg2, e_pool_no)), fmt(poisson_le(reg2, e_pool_no), 3)))
p()

# ================================================================ 4. ещё более жёсткие страты
p('=' * 100)
p('4. ЖЁСТЧЕ: партия × паттерн имени; партия × «аккаунт свежий» (только страты с обоими шаблонами)')
p('=' * 100)


def strata_by(fn, ds, min_each=1):
    d = defaultdict(list)
    for r in ds:
        d[fn(r)].append(r)
    return [v for v in d.values() if sum(1 for r in v if r['_t'] == 'Theme2') >= min_each and sum(1 for r in v if r['_t'] == 'Theme1') >= min_each]


s_pat = strata_by(lambda r: batch_key(r) + (r['паттерн имени'],), dec)
p('  Страт партия × паттерн: %d; состав: %s' % (len(s_pat), '; '.join('%s/%s/%s/%s: T1 %d, T2 %d' %
  (v[0]['_day'], v[0]['_hour'], v[0]['сайтов'], v[0]['паттерн имени'], sum(1 for r in v if r['_t'] == 'Theme1'), sum(1 for r in v if r['_t'] == 'Theme2')) for v in s_pat)))
r_pat = show('4a. Страта = партия × паттерн имени:', s_pat)
s_fresh = strata_by(lambda r: batch_key(r) + (r['аккаунт свежий'],), dec)
p('  Страт партия × свежесть аккаунта: %d; состав: %s' % (len(s_fresh), '; '.join('%s/%s/свежий=%s: T1 %d, T2 %d' %
  (v[0]['_day'], v[0]['_hour'], v[0]['аккаунт свежий'], sum(1 for r in v if r['_t'] == 'Theme1'), sum(1 for r in v if r['_t'] == 'Theme2')) for v in s_fresh)))
r_fresh = show('4b. Страта = партия × «аккаунт свежий»:', s_fresh)
s_both = strata_by(lambda r: batch_key(r) + (r['паттерн имени'], r['аккаунт свежий']), dec)
r_both = show('4c. Страта = партия × паттерн × свежесть (%d страт):' % len(s_both), s_both)
p()

# ================================================================ 5. сеанс по номерам аккаунтов: вечер 20.08
p('=' * 100)
p('5. СЕАНС ПОСТАНОВКИ ПО НОМЕРАМ АККАУНТОВ: ВЕЧЕР 20.08 (пропущенная пара для 30 вечерних Theme2)')
p('=' * 100)
ev = sorted((r for r in main if r['_day'] == '08-20' and r['_hour'] >= 20), key=lambda r: r['_wm'])
p('  Все домены 20.08 с 20:00, по возрастанию номера аккаунта Вебмастера:')
p('  %-11s %-7s %3s %6s %4s %4s %5s %7s %7s %5s %3s' % ('домен', 'шаблон', 'час', 'сайтов', 'wm', 'cf', 'раз', 'свежий', 'вышли3', 'вых%', 'рег'))
for r in ev:
    p('  %-11s %-7s %3d %6s %4d %4d %5s %7s %7d %5.1f %3d' %
      (r['домен'], r['_t'], r['_hour'], r['сайтов'], r['_wm'], r['_cf'], r['который раз аккаунт'], r['аккаунт свежий'], r['_v3'], 100 * r['_rate'], r['_reg']))
p()
ev_t2 = [r for r in ev if r['_t'] == 'Theme2']
ev_t1_fresh = [r for r in ev if r['_t'] == 'Theme1' and r['аккаунт свежий'] == 'да']
ev_t1_reused = [r for r in ev if r['_t'] == 'Theme1' and r['аккаунт свежий'] == 'нет']


def agg(ds):
    S = sum(r['_sites'] for r in ds)
    V = sum(r['_v3'] for r in ds)
    R = sum(r['_reg'] for r in ds)
    return dict(n=len(ds), S=S, V=V, R=R, ex=100 * V / S if S else 0, wm='%d–%d' % (min(r['_wm'] for r in ds), max(r['_wm'] for r in ds)),
                cf='%d–%d' % (min(r['_cf'] for r in ds), max(r['_cf'] for r in ds)), rates=[r['_rate'] * 100 for r in ds])


for name, ds in (('Theme2, 20–21 час, свежие аккаунты', ev_t2), ('Theme1, 21–22 час, свежие аккаунты', ev_t1_fresh), ('Theme1, 22 час, повторные аккаунты', ev_t1_reused)):
    a = agg(ds)
    p('  %-38s n = %2d, сайтов %5d, вышли3 %4d, выход %5.1f%%, медиана по доменам %5.1f%%, рег %d, wm %s, cf %s' %
      (name, a['n'], a['S'], a['V'], a['ex'], median(a['rates']), a['R'], a['wm'], a['cf']))
p('  Номера идут одной цепочкой: Theme2 wm 108–137 → Theme1 2328.team wm 138 (21:00) → 2650/2872/3164/fjnv wm 139–142 (22:00);')
p('  по cf: Theme1 свежие cf 132–135 → Theme2 cf 136–165. Это один сеанс постановки с одной пачки аккаунтов; Theme1 на повторных')
p('  аккаунтах (wm 4–23, «который раз» = 2) — другая пачка. Тестировщик сравнивал Theme2 (7,4%%) с ВСЕМИ Theme1 22:00 (13,4%%).')
p()
sess_ev = ev_t2 + ev_t1_fresh
r_ev = show('5a. Вечерний сеанс: Theme2 (30) против Theme1 на свежих аккаунтах того же сеанса (%d):' % len(ev_t1_fresh), [sess_ev])
# отрицательный контроль: внутри Theme1 22:00 свежие против повторных
t1_22 = [r for r in ev if r['_t'] == 'Theme1' and r['_hour'] == 22]
a_f = agg([r for r in t1_22 if r['аккаунт свежий'] == 'да'])
a_r = agg([r for r in t1_22 if r['аккаунт свежий'] == 'нет'])
e_f = a_r['ex'] / 100 * a_f['S']
# перестановка метки «свежий» внутри Theme1 22:00
rnd = random.Random(3)
obs_f = a_f['V'] / ((a_f['V'] + a_r['V']) / (a_f['S'] + a_r['S']) * a_f['S'])
cnt = 0
labs0 = [r['аккаунт свежий'] for r in t1_22]
for _ in range(N_PERM):
    labs = labs0[:]
    rnd.shuffle(labs)
    Vf = sum(r['_v3'] for r, lb in zip(t1_22, labs) if lb == 'да')
    Sf = sum(r['_sites'] for r, lb in zip(t1_22, labs) if lb == 'да')
    st = Vf / ((a_f['V'] + a_r['V']) / (a_f['S'] + a_r['S']) * Sf)
    if st <= obs_f + 1e-12:
        cnt += 1
p('  5b. Отрицательный контроль, ТОЛЬКО Theme1 в 22:00 20.08: свежие аккаунты (n = %d) выход %.1f%% против повторных (n = %d) %.1f%%' %
  (a_f['n'], a_f['ex'], a_r['n'], a_r['ex']))
p('      O/E свежих по повторным = %s (O = %d, E = %.1f); O/E по пулу = %s, перестановка p = %s.' %
  (fmt(ratio(a_f['V'], e_f)), a_f['V'], e_f, fmt(obs_f), fmt(cnt / N_PERM, 4)))
p('      Тот же шаблон, тот же час, те же 202–206 сайтов — а разница такого же размера, как «эффект шаблона» (0,54–0,74).')
p()

# ================================================================ 6. страта = сеанс
p('=' * 100)
p('6. СТРАТА = СЕАНС (партия по дню × часу × сайтов для 12:00 и 23:00 + вечерний сеанс по цепочке аккаунтов): все 47 Theme2 с парой')
p('=' * 100)
sess_strata = [batches[k] for k in DEC_KEYS] + [sess_ev]
r_sess = show('6a. Выход за 3 суток, страта = сеанс:', sess_strata)
r_sess7 = show('6b. Выход за 7 суток, страта = сеанс:', sess_strata, metric='_v7', rank=False)
r_sess_no = show('6c. То же без 1908.team:', [[r for r in v if r['домен'] != '1908.team'] for v in sess_strata])
r_sreg = perm_test(sess_strata, '_reg', n_perm=N_PERM)
p('  6d. Регистрации, страта = сеанс: O = %d, E(пул) = %.2f → O/E = %s, пуассон P(X ≤ %d) = %s, перестановка p = %s; E(Theme1) = %.2f (из них вечер: 2 регистрации одного домена 2650.team на 5 доменов)' %
  (r_sreg['O'], r_sreg['E'], fmt(r_sreg['oe']), r_sreg['O'], fmt(poisson_le(r_sreg['O'], r_sreg['E']), 3), fmt(r_sreg['p_le'], 3), r_sreg['Eref']))
r_shas = perm_test(sess_strata, '_hasreg', n_perm=N_PERM)
p('  6e. Доменов с ≥1 регистрацией, страта = сеанс: O = %d, E(пул) = %.2f → O/E = %s, перестановка p = %s' %
  (r_shas['O'], r_shas['E'], fmt(r_shas['oe']), fmt(r_shas['p_le'], 3)))
p()

# ================================================================ 7. плацебо: партии Theme1 как псевдо-Theme2
p('=' * 100)
p('7. ПЛАЦЕБО: чисто-Theme1 партии тех же дней в роли «псевдо-Theme2» (грубая страта = день, как в плане)')
p('=' * 100)
t1_only = [r for r in main if r['_t'] == 'Theme1']
groups = defaultdict(list)
for r in t1_only:
    groups[(r['_day'], r['_hour'], r['сайтов'])].append(r)
g19 = [k for k in groups if k[0] == '08-19' and len(groups[k]) >= 3]
g20 = [k for k in groups if k[0] == '08-20' and len(groups[k]) >= 3]
p('  Партии Theme1 (день × час × сайтов, ≥3 доменов): 19.08 — %d, 20.08 — %d. Для каждой пары (одна партия 19.08 + одна 20.08)' % (len(g19), len(g20)))
p('  считаем O/E «псевдо-Theme2» по остальным Theme1 того же дня — ровно как грубый O/E по Theme1 в п.2 у тестировщика.')
res_pl = []
for a in g19:
    for b in g20:
        O = E = 0.0
        for d, k in (('08-19', a), ('08-20', b)):
            ps = groups[k]
            rest = [r for r in t1_only if r['_day'] == d and (r['_day'], r['_hour'], r['сайтов']) != k]
            rate = sum(r['_v3'] for r in rest) / sum(r['_sites'] for r in rest)
            O += sum(r['_v3'] for r in ps)
            E += rate * sum(r['_sites'] for r in ps)
        res_pl.append((O / E, a, b, len(groups[a]) + len(groups[b])))
res_pl.sort()
p('  Пар: %d; O/E от %.2f до %.2f; медиана %.2f; пар с O/E ≤ 0,54: %d; ≤ 0,60: %d; ≤ 0,74: %d' %
  (len(res_pl), res_pl[0][0], res_pl[-1][0], median([x[0] for x in res_pl]),
   sum(1 for x in res_pl if x[0] <= 0.54), sum(1 for x in res_pl if x[0] <= 0.60), sum(1 for x in res_pl if x[0] <= 0.74)))
for oe, a, b, n in res_pl[:5]:
    p('     O/E = %.2f: %s %02d:00/%s + %s %02d:00/%s (%d доменов)' % (oe, a[0], a[1], a[2], b[0], b[1], b[2], n))
# уровень часа (как «блок 18-23» у тестировщика): 22:00 Theme1 против 12:00 Theme1 на 20.08
a22 = agg([r for r in t1_only if r['_day'] == '08-20' and r['_hour'] == 22])
a12 = agg([r for r in t1_only if r['_day'] == '08-20' and r['_hour'] == 12])
p('  Тот же день 20.08, только Theme1: 22:00 (n = %d) %.1f%% против 12:00 (n = %d) %.1f%% → отношение %.2f; регистраций %d против %d.' %
  (a22['n'], a22['ex'], a12['n'], a12['ex'], a22['ex'] / a12['ex'], a22['R'], a12['R']))
p()

# ================================================================ 8. позиция в сеансе
p('=' * 100)
p('8. ПОЗИЦИЯ В СЕАНСЕ: номер wm-аккаунта (свежие) против выхода внутри решающих партий')
p('=' * 100)


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                rk[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return rk
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


for k in DEC_KEYS:
    v = [r for r in batches[k] if r['аккаунт свежий'] == 'да']
    v.sort(key=lambda r: r['_wm'])
    rho = spearman([r['_wm'] for r in v], [r['_rate'] for r in v])
    p('  %s %02d:00/%s, свежие аккаунты (n = %d): по порядку wm → выход%%: %s' %
      (k[0], k[1], k[2], len(v), ' '.join('%s%d' % ('T2:' if r['_t'] == 'Theme2' else 'T1:', round(100 * r['_rate'])) for r in v)))
    p('     Спирмен(номер wm, выход) = %.2f; средняя позиция Theme2 в сеансе (1 = первый): %.1f из %d, Theme1: %.1f' %
      (rho, sum(i + 1 for i, r in enumerate(v) if r['_t'] == 'Theme2') / max(1, sum(1 for r in v if r['_t'] == 'Theme2')), len(v),
       sum(i + 1 for i, r in enumerate(v) if r['_t'] == 'Theme1') / max(1, sum(1 for r in v if r['_t'] == 'Theme1'))))
p()

# ================================================================ ВЫВОД
p('=' * 100)
p('ВЫВОД СКЕПТИКА (тени)')
p('=' * 100)
p('1. Внутри решающих партий на уровне домена разницы почти нет. В партии 20.08 12:00 медиана выхода по доменам у Theme2 %.1f%% против %.1f%% у Theme1;' %
  (median([r['_rate'] * 100 for r in batches[DEC_KEYS[1]] if r['_t'] == 'Theme2']), median([r['_rate'] * 100 for r in batches[DEC_KEYS[1]] if r['_t'] == 'Theme1'])))
p('   весь разрыв по сумме (27,4%% против 22,0%%) даёт один домен 1908.team (119 из 199). Ранговый тест по двум партиям: доля пар «Theme2 ниже» %.2f, p = %s;' % (r_dec['auc'], fmt(r_dec['p_rank'], 3)))
p('   двусторонний p к статистике тестировщика = %s; партия 12:00 отдельно p = %s, партия 23:00 отдельно (4 против 9 доменов) p = %s.' %
  (fmt(r_dec['p_two'], 3), fmt(r_b2['p_le'], 3), fmt(r_b1['p_le'], 3)))
p('2. Без 1908.team: O/E по Theme1 = %s, p = %s; ранговый p = %s. Leave-one-out: p ≥ 0,05 при удалении %d из 33 доменов. Результат p = 0,032 держится на одном домене.' %
  (fmt(r_no1908['oe_ref']), fmt(r_no1908['p_le'], 3), fmt(r_no1908['p_rank'], 3), sum(1 for x in loo if x[4] >= 0.05)))
p('3. Регистрации внутри партии: доменов с регистрацией %d из %d против %d из %d, гипергеометрический p = %s; без 1908.team O/E = %s, пуассон p = %s. Разницы нет.' %
  (k1, len(t1), k2, len(t2), fmt(hypergeom_le(k2, k1 + k2, len(t2), len(v12)), 2), fmt(ratio(reg2, e_no)), fmt(poisson_le(reg2, e_no), 2)))
p('4. Вечер 20.08: Theme2 (30 дом., wm 108–137) выход %.1f%%, Theme1 на свежих аккаунтах той же цепочки (wm 138–142, 5 дом.) %.1f%% — O/E = %s, p = %s.' %
  (agg(ev_t2)['ex'], agg(ev_t1_fresh)['ex'], fmt(r_ev['oe_ref']), fmt(r_ev['p_le'], 2)))
p('   А внутри одного Theme1 в 22:00 свежие аккаунты против повторных: %.1f%% против %.1f%% (O/E %s, p = %s) — «тень сеанса» того же размера, что весь «эффект шаблона».' %
  (a_f['ex'], a_r['ex'], fmt(ratio(a_f['V'], e_f)), fmt(cnt / N_PERM, 3)))
p('5. Страта = сеанс (все 47 Theme2 с парой, 3 страты): выход O/E по пулу %s, по Theme1 %s, p одностор. %s, двустор. %s; ранговый p = %s; без 1908.team O/E %s, p = %s.' %
  (fmt(r_sess['oe']), fmt(r_sess['oe_ref']), fmt(r_sess['p_le'], 3), fmt(r_sess['p_two'], 3), fmt(r_sess['p_rank'], 3), fmt(r_sess_no['oe_ref']), fmt(r_sess_no['p_le'], 3)))
p('   Регистрации в этой страте: O = %d, E = %.1f, p = %s.' % (r_sreg['O'], r_sreg['E'], fmt(poisson_le(r_sreg['O'], r_sreg['E']), 2)))
p('6. Плацебо: пары чисто-Theme1 партий тех же дней дают грубый O/E от %.2f до %.2f, %d из %d пар не хуже «0,54» Theme2. Грубая «вдвое» — обычный разброс между партиями.' %
  (res_pl[0][0], res_pl[-1][0], sum(1 for x in res_pl if x[0] <= 0.54), len(res_pl)))
p()
p('ИТОГ: опровергнуто как эффект шаблона. Грубые «вдвое» и «в 8 раз» — тень партии/сеанса постановки (плацебо-партии Theme1 дают тот же размер).')
p('Остаточный «0,74, p = 0,03» внутри партии не переживает ни ранговый тест по доменам, ни удаление одного домена 1908.team, ни двусторонний p,')
p('ни добавление вечернего сеанса с Theme1-парой на тех же аккаунтах. По регистрациям различий нет ни в одном разрезе. Вердикт «частично» завышен:')
p('на этом файле шаблон от сеанса постановки неотделим, а там, где отделим, разницы нет.')
p()
p('ЧТО С ЭТИМ ДЕЛАТЬ: ничего по шаблону — это не рычаг и не подозрение, а артефакт того, что Theme2 ставили отдельными сеансами.')
p('Проверяемо на уже запущенных данных: (а) дозаписать набор контента для 106 доменов 19–20.08; (б) взять «сеанс» (день × цепочка номеров wm/cf)')
p('как страту в других гипотезах о днях до 24.08 — разница свежие/повторные аккаунты внутри Theme1 22:00 (%.1f%% против %.1f%%) говорит, что')
p('сеанс постановки объясняет часть «необъяснимого» разброса внутри пула «КОНТЕНТ НЕ ЗАПИСАН».' % (a_f['ex'], a_r['ex']))

with open(OUT, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(_lines) + '\n')
print('\nСохранено:', OUT, file=sys.stderr)

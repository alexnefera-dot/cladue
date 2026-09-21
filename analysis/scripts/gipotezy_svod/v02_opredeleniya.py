#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка гипотезы №2 (скептик, угол: определения и воспроизводимость).

Что проверяем:
  1. Фильтр и оконные колонки: те же 1511 доменов; «сайтов в окне», «вышли за 3 суток»,
     «регистраций в окне 3 суток» непусты; «КОНТЕНТ НЕ ЗАПИСАН» исключён.
  2. Что такое «ведущий ноль»: доля нулевых среди numeric против 1/10 при случайной
     4-значной генерации; совпадение с датой запуска.
  3. Объединённый тест «все признаки» (ноль + alpha_other с цифрой):
     а) воспроизведение O/E и p;
     б) страта пул + паттерн имени (ноль сравнивается только с numeric, смесь — только
        с буквами того же пула), чтобы разные паттерны не смешивались;
     в) подмена нуля любой другой первой цифрой d = 0..9: сколько цифр дают O/E и p
        не слабее, чем ноль — если много, «ноль» в сумме — выбор худшей цифры;
     г) вклад пулов: без какого одного пула суммарный дефицит рассыпается.
  4. Сколько тестов сделано (множественность).
Только stdlib.
"""
import csv
import math
import os
import random
import re
from collections import Counter, defaultdict

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(BASE, 'export', 'svod_domenov_21.09.csv')
OUTLIERS = {'3615.team', '3286.team'}
N_PERM = 4000


def to_int(s):
    s = (s or '').strip()
    return int(float(s)) if s else 0


with open(SRC, encoding='utf-8', newline='') as fh:
    rows_all = list(csv.DictReader(fh))

rows = [r for r in rows_all if r['домен'] not in OUTLIERS
        and r['окно закрыто'] == 'да' and r['дней'] != '1'
        and r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
print('1. ФИЛЬТР И ОКОННЫЕ КОЛОНКИ')
print('   после фильтра доменов:', len(rows), '(заявлено 1511)')
print('   «сайтов в окне» == «сайтов»:', sum(1 for r in rows if r['сайтов в окне'] == r['сайтов']), 'из', len(rows))
print('   «вышли за 3 суток» пусто:', sum(1 for r in rows if not r['вышли за 3 суток'].strip()))
print('   «регистраций в окне 3 суток» пусто:', sum(1 for r in rows if not r['регистраций в окне 3 суток'].strip()))
print('   сумма «регистраций в окне 3 суток» после фильтра:', sum(to_int(r['регистраций в окне 3 суток']) for r in rows))
print('   «КОНТЕНТ НЕ ЗАПИСАН» после фильтра:', sum(1 for r in rows if r['набор контента'] == 'КОНТЕНТ НЕ ЗАПИСАН'))
print('   дней=1 / окно не закрыто после фильтра:', sum(1 for r in rows if r['дней'] == '1' or r['окно закрыто'] != 'да'))

DATE_RE = re.compile(r'^\d{4}[a-z]+$')
for r in rows:
    r['_lab'] = r['домен'].split('.')[0]
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_out3'] = to_int(r['вышли за 3 суток'])
    r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_pool'] = (r['набор контента'], r['день запуска'])
    r['_poolp'] = (r['набор контента'], r['день запуска'], r['паттерн имени'])
    r['_digit'] = any(ch.isdigit() for ch in r['_lab'])
    r['_isD'] = bool(DATE_RE.match(r['_lab']))

num = [r for r in rows if r['паттерн имени'] == 'numeric']
alpha = [r for r in rows if r['паттерн имени'] == 'alpha_other']

print()
print('2. ЧТО ТАКОЕ «ВЕДУЩИЙ НОЛЬ»')
n0 = sum(1 for r in num if r['_lab'][0] == '0')
print('   numeric всего %d, все 4-значные: %s; с ведущим 0: %d (%.1f%%; при случайной 4-значной генерации ждём 10%%)' % (
    len(num), all(len(r['_lab']) == 4 and r['_lab'].isdigit() for r in num), n0, 100.0 * n0 / len(num)))
fd = Counter(r['_lab'][0] for r in num)
print('   первая цифра numeric:', ' '.join('%s:%d' % kv for kv in sorted(fd.items())))
# биномиальный тест: 78 из 658 при p=0.1
def binom_sf(k, n, q):
    return sum(math.comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(k, n + 1))
print('   P(нулевых ≥ %d из %d | p=0.1) = %.3f — доля нуля не отличается от любой другой цифры' % (n0, len(num), binom_sf(n0, len(num), 0.1)))
def eq_launch(r):
    y, mo, da = r['день запуска'].split('-')
    return r['_lab'] in (da + mo, mo + da)
print('   нулевых меток, совпадающих с датой запуска (ДДММ/ММДД): %d из %d' % (sum(1 for r in num if r['_lab'][0] == '0' and eq_launch(r)), n0))


# ------------------------------------------------------------------ O/E движок
def oe(rs, is_feat, key='_pool', n_perm=N_PERM, seed=1):
    pools = defaultdict(list)
    for r in rs:
        pools[r[key]].append(r)
    used = {k: v for k, v in pools.items() if any(is_feat(r) for r in v) and any(not is_feat(r) for r in v)}
    rate_out, rate_reg = {}, {}
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rate_out[k] = sum(r['_out3'] for r in v) / S
        rate_reg[k] = sum(r['_regs'] for r in v) / S
    doms = [r for v in used.values() for r in v]
    feat = [r for r in doms if is_feat(r)]
    ref = [r for r in doms if not is_feat(r)]
    O_out = sum(r['_out3'] for r in feat)
    E_out = sum(rate_out[r[key]] * r['_sites'] for r in feat)
    O_reg = sum(r['_regs'] for r in feat)
    E_reg = sum(rate_reg[r[key]] * r['_sites'] for r in feat)
    oe_out = O_out / E_out if E_out else float('nan')
    oe_reg = O_reg / E_reg if E_reg else float('nan')
    rng = random.Random(seed)
    lists = [(list(v), sum(1 for r in v if is_feat(r))) for v in used.values()]
    c_out = c_reg = 0
    for _ in range(n_perm):
        po = pe = ro = re_ = 0.0
        for v, m in lists:
            rng.shuffle(v)
            k = v[0][key]
            for r in v[:m]:
                po += r['_out3']; ro += r['_regs']
                pe += rate_out[k] * r['_sites']; re_ += rate_reg[k] * r['_sites']
        if po / pe <= oe_out + 1e-12:
            c_out += 1
        if (ro / re_ if re_ else 0) <= oe_reg + 1e-12:
            c_reg += 1
    # пуассон
    lam = E_reg
    pois = sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(O_reg + 1)) if lam > 0 else 1.0
    return dict(pools=len(used), nf=len(feat), nr=len(ref), sf=sum(r['_sites'] for r in feat), sr=sum(r['_sites'] for r in ref),
                O_out=O_out, E_out=E_out, oe_out=oe_out, p_out=c_out / n_perm,
                O_reg=O_reg, E_reg=E_reg, oe_reg=oe_reg, p_reg=c_reg / n_perm, pois=pois,
                regs_ref=sum(r['_regs'] for r in ref), used=used, rate_reg=rate_reg)


def show(name, s):
    print('   %-46s пулов %3d, %3d/%3d дом.; выход O/E %.2f (p %.3f); рег %2d при E %.2f, O/E %.2f, пуассон %.3f, перест. %.3f' % (
        name, s['pools'], s['nf'], s['nr'], s['oe_out'], s['p_out'], s['O_reg'], s['E_reg'], s['oe_reg'], s['pois'], s['p_reg']))


print()
print('3. ОБЪЕДИНЁННЫЙ ТЕСТ «ВСЕ ПРИЗНАКИ» (ноль ИЛИ alpha_other с цифрой) против обычных')
isA = lambda r: r['паттерн имени'] == 'numeric' and r['_lab'][0] == '0'
isGen = lambda r: isA(r) or (r['паттерн имени'] == 'alpha_other' and r['_digit'])
both = num + alpha
gen = oe(both, isGen)
show('а) как у тестировщика (пул контент+день)', gen)
genp = oe(both, isGen, key='_poolp')
show('б) страта контент+день+ПАТТЕРН', genp)
# сколько пулов в (а) смешивают паттерны: домен с признаком, у которого в пуле нет сравнения того же паттерна
mixed = 0
for k, v in gen['used'].items():
    for r in v:
        if isGen(r) and not any((not isGen(x)) and x['паттерн имени'] == r['паттерн имени'] for x in v):
            mixed += 1
print('   в (а) доменов с признаком, у которых в пуле нет обычной метки ТОГО ЖЕ паттерна: %d из %d' % (mixed, gen['nf']))

print()
print('   в) подмена нуля другой первой цифрой: признак = «numeric с первой цифрой d» ИЛИ «alpha_other с цифрой»')
print('      %-5s %6s %8s %6s %5s %7s %6s %7s %7s' % ('d', 'пулов', 'дом.', 'O/Eвых', 'p', 'регO', 'E', 'O/E', 'p пер'))
res_d = {}
for d in '0123456789':
    isG = lambda r, d=d: (r['паттерн имени'] == 'numeric' and r['_lab'][0] == d) or (r['паттерн имени'] == 'alpha_other' and r['_digit'])
    s = oe(both, isG, n_perm=2000)
    res_d[d] = s
    print('      %-5s %6d %8d %6.2f %5.3f %7d %7.2f %6.2f %7.3f' % (d, s['pools'], s['nf'], s['oe_out'], s['p_out'], s['O_reg'], s['E_reg'], s['oe_reg'], s['p_reg']))
n_as_bad = sum(1 for d, s in res_d.items() if s['oe_reg'] <= gen['oe_reg'] + 1e-9)
n_sig = sum(1 for d, s in res_d.items() if s['p_reg'] < 0.05)
print('      цифр, у которых суммарный O/E по регистрациям ≤ %.2f (как у нуля): %d из 10; с p < 0.05: %d из 10' % (gen['oe_reg'], n_as_bad, n_sig))
print('      без numeric вообще (только alpha_other с цифрой vs буквы, заранее заданный тест):')
al = oe(alpha, lambda r: r['_digit'])
show('      alpha_other с цифрой vs буквы', al)
al2 = oe([r for r in alpha if not r['_isD']], lambda r: r['_digit'])
show('      то же без кода даты (пост-хок)', al2)

print()
print('   г) вклад пулов в дефицит регистраций (E − O) в тесте (а): топ-5 пулов и «без одного пула»')
contrib = []
for k, v in gen['used'].items():
    f = [r for r in v if isGen(r)]
    O = sum(r['_regs'] for r in f)
    E = gen['rate_reg'][k] * sum(r['_sites'] for r in f)
    regs_pool = sum(r['_regs'] for r in v)
    contrib.append((E - O, k, O, E, regs_pool, len(f), len(v) - len(f)))
contrib.sort(reverse=True)
tot = sum(c[0] for c in contrib)
print('      суммарный дефицит E−O = %.2f' % tot)
for c in contrib[:5]:
    print('      %-40s день %s: признак %d дом. (O=%d, E=%.2f), сравнение %d дом., рег в пуле %d; вклад %.2f (%.0f%%)' % (
        c[1][0][:40], c[1][1], c[5], c[2], c[3], c[6], c[4], c[0], 100 * c[0] / tot))
top3 = sum(c[0] for c in contrib[:3])
print('      топ-3 пула дают %.0f%% дефицита' % (100 * top3 / tot))
# без самого тяжёлого пула
worst_key = contrib[0][1]
gen_wo = oe([r for r in both if r['_pool'] != worst_key], isGen, n_perm=2000)
show('      без самого тяжёлого пула', gen_wo)
gen_wo3 = oe([r for r in both if r['_pool'] not in {c[1] for c in contrib[:3]}], isGen, n_perm=2000)
show('      без трёх самых тяжёлых пулов', gen_wo3)

print()
print('4. МНОЖЕСТВЕННОСТЬ: в отчёте 13 строк сводки (A, A+зона, B, B+зона, C, C2, D, D+зона, объед.×3, все×2),')
print('   каждая с 2 метриками и 2–3 p. Самый малый p среди ЗАРАНЕЕ заданных тестов по регистрациям:')
pre = {'A': 0.106, 'B': 0.133, 'C': 0.091, 'D': 0.933, 'объед. alpha': 0.229, 'все признаки': 0.014}
print('   ', ', '.join('%s %.3f' % kv for kv in pre.items()))
print('   Бонферрони по 6 заранее заданным тестам регистраций: порог 0.05/6 = %.4f; «все признаки» p=0.014 — %s' % (
    0.05 / 6, 'проходит' if 0.014 < 0.05 / 6 else 'НЕ проходит'))

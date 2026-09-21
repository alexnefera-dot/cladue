#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скептическая проверка гипотезы №2 (угол: определения и воспроизводимость).
Независимый пересчёт O/E по выходу и регистрациям для признаков «похоже на
сгенерированное», проверка определений меток, страт, вкладов пулов.
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

with open(SRC, encoding='utf-8', newline='') as fh:
    rows_all = list(csv.DictReader(fh))
print('Всего строк:', len(rows_all))


def to_int(s):
    s = (s or '').strip()
    return int(float(s)) if s else 0


# ------------------------------------------------------------ 1. фильтр
print('\n=== 1. ФИЛЬТР (пошагово, независимо) ===')
n_out = sum(1 for r in rows_all if r['домен'] in OUTLIERS)
n_open = sum(1 for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] != 'да')
n_d1 = sum(1 for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] == '1')
n_nz = sum(1 for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] != '1'
           and r['набор контента'] == 'КОНТЕНТ НЕ ЗАПИСАН')
rows = [r for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] != '1'
        and r['набор контента'] != 'КОНТЕНТ НЕ ЗАПИСАН']
print('выбросы %d, окно не закрыто %d, дней=1 %d, КОНТЕНТ НЕ ЗАПИСАН %d, осталось %d' % (n_out, n_open, n_d1, n_nz, len(rows)))
print('среди всех: окно закрыто=нет и дней=1 одновременно:', sum(1 for r in rows_all if r['окно закрыто'] != 'да' and r['дней'] == '1'))
print('среди всех: дней=1 при окно закрыто=да:', sum(1 for r in rows_all if r['окно закрыто'] == 'да' and r['дней'] == '1'))
print('дней у оставшихся:', Counter(r['дней'] for r in rows))
print('сайтов у оставшихся:', Counter(r['сайтов'] for r in rows))
print('сайтов в окне у оставшихся:', Counter(r['сайтов в окне'] for r in rows))
print('пустых «вышли за 3 суток» у оставшихся:', sum(1 for r in rows if not r['вышли за 3 суток'].strip()))
print('пустых «регистраций в окне 3 суток»:', sum(1 for r in rows if not r['регистраций в окне 3 суток'].strip()))
# соответствие «сайтов в окне» и «сайтов»
print('сайтов в окне != сайтов у оставшихся:', sum(1 for r in rows if r['сайтов в окне'] != r['сайтов']))
print('зоны у оставшихся:', Counter(r['зона'] for r in rows).most_common())

for r in rows:
    r['_lab'] = r['домен'].split('.')[0]
    r['_sites'] = to_int(r['сайтов в окне'])
    r['_out3'] = to_int(r['вышли за 3 суток'])
    r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_pool'] = (r['набор контента'], r['день запуска'])
    r['_poolz'] = (r['набор контента'], r['день запуска'], r['зона'])
    r['_poolp'] = (r['набор контента'], r['день запуска'], r['паттерн имени'])
    r['_poolpz'] = (r['набор контента'], r['день запуска'], r['паттерн имени'], r['зона'])

# ------------------------------------------------------------ 2. определения меток
print('\n=== 2. ОПРЕДЕЛЕНИЯ МЕТОК ===')
print('метка (до точки) длина != «длина метки»:', sum(1 for r in rows if str(len(r['_lab'])) != r['длина метки']))
print('меток с заглавными/не-ascii:', sum(1 for r in rows if not re.match(r'^[a-z0-9-]*$', r['_lab'])))
print('меток с дефисом:', sum(1 for r in rows if '-' in r['_lab']))
print('numeric, но не только цифры:', sum(1 for r in rows if r['паттерн имени'] == 'numeric' and not r['_lab'].isdigit()))
print('не numeric, но только цифры:', sum(1 for r in rows if r['паттерн имени'] != 'numeric' and r['_lab'].isdigit()))
print('длины numeric:', Counter(len(r['_lab']) for r in rows if r['паттерн имени'] == 'numeric'))
print('первая цифра numeric:', sorted(Counter(r['_lab'][0] for r in rows if r['паттерн имени'] == 'numeric').items()))
print('точек в домене > 1:', sum(1 for r in rows if r['домен'].count('.') > 1))

DATE_RE = re.compile(r'^\d{4}[a-z]+$')


def sub(r):
    l = r['_lab']
    pat = r['паттерн имени']
    if pat == 'numeric':
        return 'num0' if l[0] == '0' else 'num'
    if pat == 'alpha_other':
        if DATE_RE.match(l):
            return 'date'
        if l.isalpha():
            return 'alpha%d' % len(l)
        return 'mix%d' % len(l)
    return pat


for r in rows:
    r['_s'] = sub(r)
print('подтипы alpha_other + numeric:', sorted(Counter(r['_s'] for r in rows if r['паттерн имени'] in ('numeric', 'alpha_other')).items()))
print('примеры code даты:', [r['_lab'] for r in rows if r['_s'] == 'date'][:12])
print('примеры mix5+:', [r['_lab'] for r in rows if r['_s'].startswith('mix') and len(r['_lab']) >= 5][:15])
print('примеры mix4:', [r['_lab'] for r in rows if r['_s'] == 'mix4'][:15])
print('примеры mix3:', [r['_lab'] for r in rows if r['_s'] == 'mix3'][:15])
print('примеры alpha5+:', [r['_lab'] for r in rows if r['_s'].startswith('alpha') and len(r['_lab']) >= 5][:15])
print('примеры num0:', [r['_lab'] for r in rows if r['_s'] == 'num0'][:15])
# alpha_other с цифрами, которые «похожи на код даты» но с другой структурой (цифры в конце и т.п.)
mixes = [r['_lab'] for r in rows if r['_s'].startswith('mix')]
print('структура mix (Ц=цифра, Б=буква):', Counter(''.join('Ц' if c.isdigit() else 'Б' for c in l) for l in mixes).most_common(20))
# mix, у которых 4 цифры подряд в начале (потенциально код даты, но затем не только буквы)
print('mix с 4 цифрами впереди (не попали в «код даты»):', [l for l in mixes if re.match(r'^\d{4}', l)][:20])
# сколько «кодов даты» действительно похожи на дату ММДД / ДДММ
def is_datey(l):
    a, b = int(l[:2]), int(l[2:4])
    return (1 <= a <= 12 and 1 <= b <= 31) or (1 <= b <= 12 and 1 <= a <= 31)
print('код даты: похоже на дату ММДД/ДДММ:', sum(1 for r in rows if r['_s'] == 'date' and is_datey(r['_lab'])), 'из',
      sum(1 for r in rows if r['_s'] == 'date'))
print('num0: похоже на дату ММДД/ДДММ:', sum(1 for r in rows if r['_s'] == 'num0' and is_datey(r['_lab'])), 'из',
      sum(1 for r in rows if r['_s'] == 'num0'))
print('num (без нуля): похоже на дату:', sum(1 for r in rows if r['_s'] == 'num' and is_datey(r['_lab'])), 'из',
      sum(1 for r in rows if r['_s'] == 'num'))


# ------------------------------------------------------------ 3. O/E независимо
def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0
    return min(1.0, sum(math.exp(-lam + i * math.log(lam) - math.lgamma(i + 1)) for i in range(int(k) + 1)))


def oe(rs, feat, key='_pool', nperm=0, seed=7, label=''):
    pools = defaultdict(list)
    for r in rs:
        pools[r[key]].append(r)
    used = {k: v for k, v in pools.items() if any(feat(r) for r in v) and any(not feat(r) for r in v)}
    rate_o, rate_r = {}, {}
    for k, v in used.items():
        S = sum(r['_sites'] for r in v)
        rate_o[k] = sum(r['_out3'] for r in v) / S
        rate_r[k] = sum(r['_regs'] for r in v) / S
    F = [r for v in used.values() for r in v if feat(r)]
    R = [r for v in used.values() for r in v if not feat(r)]
    Oo = sum(r['_out3'] for r in F); Eo = sum(rate_o[r[key]] * r['_sites'] for r in F)
    Or = sum(r['_regs'] for r in F); Er = sum(rate_r[r[key]] * r['_sites'] for r in F)
    Rr = sum(r['_regs'] for r in R)
    sF = sum(r['_sites'] for r in F); sR = sum(r['_sites'] for r in R)
    res = dict(pools=len(used), nF=len(F), nR=len(R), sF=sF, sR=sR, Oo=Oo, Eo=Eo, Or=Or, Er=Er, Rr=Rr,
               oeo=Oo / Eo if Eo else float('nan'), oer=Or / Er if Er else float('nan'),
               pois=poisson_cdf(Or, Er))
    if nperm:
        rnd = random.Random(seed)
        pl = [(list(v), sum(1 for r in v if feat(r))) for v in used.values()]
        co = cr = 0
        for _ in range(nperm):
            po = pe = ro = re_ = 0.0
            for v, m in pl:
                rnd.shuffle(v)
                k = v[0][key]
                for r in v[:m]:
                    po += r['_out3']; ro += r['_regs']
                    pe += rate_o[k] * r['_sites']; re_ += rate_r[k] * r['_sites']
            if po / pe <= res['oeo'] + 1e-12:
                co += 1
            if (ro / re_ if re_ else 0) <= res['oer'] + 1e-12:
                cr += 1
        res['p_o'] = co / nperm; res['p_r'] = cr / nperm
    print('  %-44s пулов %3d, %3d/%-3d дом., сайтов %6d/%-6d | выход O=%5d E=%7.1f O/E=%.3f p=%s | рег O=%2d E=%6.2f O/E=%.2f (срав. %d рег, %.3f/100) пуассон=%.4f p=%s' % (
        label, res['pools'], res['nF'], res['nR'], sF, sR, Oo, Eo, res['oeo'], ('%.4f' % res['p_o']) if nperm else '-',
        Or, Er, res['oer'], Rr, 100.0 * Rr / sR if sR else 0, res['pois'], ('%.4f' % res['p_r']) if nperm else '-'))
    res['used'] = used
    res['rate_r'] = rate_r
    return res


num = [r for r in rows if r['паттерн имени'] == 'numeric']
alpha = [r for r in rows if r['паттерн имени'] == 'alpha_other']
isA = lambda r: r['_s'] == 'num0'
isB = lambda r: r['_s'] == 'mix4'
isC = lambda r: r['_s'] in ('mix3', 'alpha3')
isD = lambda r: r['_s'] == 'date'
isRef4 = lambda r: r['_s'] == 'alpha4'
anyDigit = lambda r: any(c.isdigit() for c in r['_lab'])
isGen = lambda r: isA(r) or (r['паттерн имени'] == 'alpha_other' and anyDigit(r))
isGen2 = lambda r: isA(r) or (r['паттерн имени'] == 'alpha_other' and anyDigit(r) and not isD(r))

print('\n=== 3. НЕЗАВИСИМЫЙ ПЕРЕСЧЁТ O/E (пул = контент+день), перестановки 4000, seed 7 ===')
NP = 4000
rA = oe(num, isA, nperm=NP, label='A ноль vs numeric')
rB = oe([r for r in alpha if isB(r) or isRef4(r)], isB, nperm=NP, label='B смесь-4 vs буквы-4')
rC = oe([r for r in alpha if isC(r) or isRef4(r)], isC, nperm=NP, label='C длина-3 vs буквы-4')
rD = oe([r for r in alpha if isD(r) or isRef4(r)], isD, nperm=NP, label='D код даты vs буквы-4')
rAll = oe(alpha, anyDigit, nperm=NP, label='Объед. alpha с цифрой vs буквы')
rGen = oe(num + alpha, isGen, nperm=NP, label='Все признаки vs обычные')
rGen2 = oe([r for r in num + alpha if not isD(r)], isGen2, nperm=NP, label='Все без кода даты (пост-хок)')

print('\n=== 4. ОБЪЕДИНЁННЫЙ ТЕСТ ПРИ ДРУГИХ СТРАТАХ ===')
oe(num + alpha, isGen, key='_poolp', nperm=NP, label='Все признаки, страта +паттерн')
oe(num + alpha, isGen, key='_poolz', nperm=NP, label='Все признаки, страта +зона')
oe(num + alpha, isGen, key='_poolpz', nperm=NP, label='Все признаки, страта +паттерн+зона')
oe([r for r in num + alpha if not isD(r)], isGen2, key='_poolp', nperm=NP, label='Без кода даты, страта +паттерн')
oe([r for r in num + alpha if not isD(r)], isGen2, key='_poolpz', nperm=NP, label='Без кода даты, +паттерн+зона')
# без зон-одиночек (прочие) и без buzz
main_z = {'team', 'lol', 'casino', 'buzz'}
oe([r for r in num + alpha if r['зона'] in main_z], isGen, nperm=NP, label='Все признаки, только 4 зоны')
oe([r for r in num + alpha if r['зона'] in ('team', 'lol')], isGen, nperm=NP, label='Все признаки, только team+lol')
oe([r for r in num + alpha if r['зона'] in ('team', 'lol')], isGen, key='_poolpz', nperm=NP, label='team+lol, +паттерн+зона')

print('\n=== 5. ВКЛАД ПУЛОВ В ДЕФИЦИТ РЕГИСТРАЦИЙ (все признаки vs обычные) ===')
used = rGen['used']; rate_r = rGen['rate_r']
contrib = []
for k, v in used.items():
    F = [r for r in v if isGen(r)]; R = [r for r in v if not isGen(r)]
    O = sum(r['_regs'] for r in F); E = sum(rate_r[k] * r['_sites'] for r in F)
    regs_tot = sum(r['_regs'] for r in v)
    contrib.append((E - O, k, len(F), len(R), O, E, regs_tot, sum(r['_regs'] for r in R)))
contrib.sort(reverse=True)
print('пулов с хотя бы 1 регистрацией: %d из %d; сумма регистраций в пулах: %d' % (
    sum(1 for c in contrib if c[6] > 0), len(contrib), sum(c[6] for c in contrib)))
print('топ-10 пулов по (E−O) у признака:')
for c in contrib[:10]:
    print('   E−O=%+.2f  %s | признак %d дом. (O=%d, E=%.2f), обычные %d дом. (рег %d)' % (c[0], c[1], c[2], c[4], c[5], c[3], c[7]))
print('нижние 5 (где признак лучше):')
for c in contrib[-5:]:
    print('   E−O=%+.2f  %s | признак %d дом. (O=%d, E=%.2f), обычные %d дом. (рег %d)' % (c[0], c[1], c[2], c[4], c[5], c[3], c[7]))
# выкинуть по одному самому «тяжёлому» пулу
print('leave-one-pool-out: без k самых тяжёлых пулов:')
O_all = sum(c[4] for c in contrib); E_all = sum(c[5] for c in contrib)
for k in (0, 1, 2, 3, 5):
    O = O_all - sum(c[4] for c in contrib[:k]); E = E_all - sum(c[5] for c in contrib[:k])
    print('   без %d: O=%d E=%.2f O/E=%.2f пуассон=%.4f' % (k, O, E, O / E, poisson_cdf(O, E)))
# доля E от пулов, где у признака 0 регистраций и весь E от одного домена сравнения
print('распределение регистраций у доменов сравнения в использованных пулах:',
      sorted(Counter(r['_regs'] for v in used.values() for r in v if not isGen(r)).items()))
print('распределение регистраций у доменов с признаком:',
      sorted(Counter(r['_regs'] for v in used.values() for r in v if isGen(r)).items()))
# домены с признаком в используемых пулах по подтипам
print('состав признака в 68 пулах:', Counter(r['_s'] for v in used.values() for r in v if isGen(r)).most_common())
print('состав обычных в 68 пулах:', Counter(r['_s'] for v in used.values() for r in v if not isGen(r)).most_common())
print('зоны признака в 68 пулах:', Counter(r['зона'] for v in used.values() for r in v if isGen(r)).most_common())
print('зоны обычных в 68 пулах:', Counter(r['зона'] for v in used.values() for r in v if not isGen(r)).most_common())

print('\n=== 6. ПУАССОН: проверка чисел ===')
for O, E in ((19, 31.11), (13, 25.74), (2, 5.24), (6, 9.95), (3, 6.83), (6, 3.52), (15, 18.79)):
    print('   P(X<=%d | %.2f) = %.4f' % (O, E, poisson_cdf(O, E)))

print('\n=== 7. ДЕНЬ-ОДИНОЧКИ / ПУЛЫ-ОДИНОЧКИ ===')
# сколько используемых пулов состоят из 1 признака + 1 обычного
sz = Counter((sum(1 for r in v if isGen(r)), sum(1 for r in v if not isGen(r))) for v in used.values())
print('размеры пулов (признак, обычные):', sorted(sz.items())[:25])
print('пулов 1+1:', sz.get((1, 1), 0))

print('\n=== 8. КОНТРОЛЬ ПАРТИИ (все домены после фильтра) ===')
for name, f in (('num0', isA), ('mix4', isB), ('len3', isC), ('date', isD)):
    F = [r for r in rows if f(r)]
    print('  %-5s n=%d cf=%d wm=%d пулов=%d дней=%d наборов=%d зон=%s' % (
        name, len(F), len(set(r['cf-аккаунт'] for r in F)), len(set(r['аккаунт вебмастера'] for r in F)),
        len(set(r['_pool'] for r in F)), len(set(r['день запуска'] for r in F)), len(set(r['набор контента'] for r in F)),
        dict(Counter(r['зона'] for r in F))))

print('\n=== 9. СЫРЫЕ СУММЫ ПОСЛЕ ФИЛЬТРА (сверка) ===')
agg = defaultdict(lambda: [0, 0, 0, 0])
for r in rows:
    if r['паттерн имени'] in ('numeric', 'alpha_other'):
        a = agg[r['_s']]; a[0] += 1; a[1] += r['_sites']; a[2] += r['_out3']; a[3] += r['_regs']
for k in sorted(agg):
    a = agg[k]
    print('  %-8s дом %4d сайтов %6d вышли %5d (%.1f%%) рег %3d (%.3f/100)' % (k, a[0], a[1], a[2], 100.0 * a[2] / a[1], a[3], 100.0 * a[3] / a[1]))

print('\n=== 10. ЧУВСТВИТЕЛЬНОСТЬ К ФИЛЬТРУ: включить дней=1 и незакрытое окно НЕЛЬЗЯ (пустые вышли), но проверим: с «КОНТЕНТ НЕ ЗАПИСАН» как отдельным пулом по дню ===')
rows_nz = [r for r in rows_all if r['домен'] not in OUTLIERS and r['окно закрыто'] == 'да' and r['дней'] != '1'
           and r['набор контента'] == 'КОНТЕНТ НЕ ЗАПИСАН']
for r in rows_nz:
    r['_lab'] = r['домен'].split('.')[0]
    r['_sites'] = to_int(r['сайтов в окне']); r['_out3'] = to_int(r['вышли за 3 суток']); r['_regs'] = to_int(r['регистраций в окне 3 суток'])
    r['_pool'] = ('НЕ ЗАПИСАН', r['день запуска']); r['_s'] = sub(r)
nz_na = [r for r in rows_nz if r['паттерн имени'] in ('numeric', 'alpha_other')]
print('  «КОНТЕНТ НЕ ЗАПИСАН» после прочих фильтров: %d, из них numeric/alpha_other %d, с признаком %d' % (
    len(rows_nz), len(nz_na), sum(1 for r in nz_na if isGen(r))))
oe(nz_na, isGen, nperm=NP, label='Только НЕ ЗАПИСАН, пул=день (справочно)')

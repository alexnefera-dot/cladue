#!/usr/bin/env python3
"""
Проверка гипотезы №1 (паттерн имени домена) с угла «определения и воспроизводимость».
Независимый пересчёт основных чисел h01_domain_name_pattern.py плюс проверки:
  1) оконные колонки и целостность (сайтов в окне = сайтов, вышли3 <= сайтов, прочие зоны);
  2) те же O/E при страте «набор + день + зона» по всем четырём зонам (team/lol/casino/buzz);
  3) способ двусторонности p для контраста casino_infix: |O−E| против 2×min(хвост) и коридор 2,5–97,5%;
  4) утверждение «одинаковый паттерн чаще в одном блоке часа: 0,75 против 0,65» — пересчёт;
  5) чувствительность к фильтру дней = 1 (77 доменов с закрытым окном);
  6) состав регистраций casino_infix по зонам и доменам.
Только stdlib.
"""
import csv, os, random, sys
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ANALYSIS = os.path.dirname(os.path.dirname(HERE))
CSV_PATH = os.path.join(ANALYSIS, 'export', 'svod_domenov_21.09.csv')
OUT = {'3615.team', '3286.team'}
NC = 'КОНТЕНТ НЕ ЗАПИСАН'
PATS = ['numeric', 'alpha_other', 'casino_prefix', 'casino_infix']
N_PERM = 10000


def toi(s):
    return int(float(s)) if s not in ('', None) else 0


rows = list(csv.DictReader(open(CSV_PATH, encoding='utf-8', newline='')))


def prep(r):
    return dict(домен=r['домен'], зона=r['зона'], день=r['день запуска'], набор=r['набор контента'],
                паттерн=r['паттерн имени'], блок=r['блок часа'], час=r['час запуска'], дней=r['дней'],
                сайтов=toi(r['сайтов в окне']), вышли3=toi(r['вышли за 3 суток']),
                рег=toi(r['регистраций в окне 3 суток']), клик=toi(r['кликов из поиска в окне']),
                акк=r['аккаунт вебмастера'], cf=r['cf-аккаунт'])


def filt(rows, keep_day1=False):
    out = []
    for r in rows:
        if r['домен'] in OUT or r['окно закрыто'] != 'да' or r['набор контента'] == NC:
            continue
        if r['дней'] == '1' and not keep_day1:
            continue
        out.append(prep(r))
    return out


def pools_of(items, key):
    p = defaultdict(list)
    for d in items:
        p[key(d)].append(d)
    return p


def add_E(pools):
    for ds in pools.values():
        S = sum(d['сайтов'] for d in ds); V = sum(d['вышли3'] for d in ds); R = sum(d['рег'] for d in ds); C = sum(d['клик'] for d in ds)
        for d in ds:
            d['E_вых'] = V / S * d['сайтов'] if S else 0.0
            d['E_рег'] = R / S * d['сайтов'] if S else 0.0
            d['E_рег_в'] = R / V * d['вышли3'] if V else 0.0
            d['E_рег_к'] = R / C * d['клик'] if C else 0.0


def perm(items, pool_key, n=N_PERM, seed=1):
    """Возвращает obs и список перестановочных сумм по паттернам для полей O/E."""
    fields = ['сайтов', 'вышли3', 'E_вых', 'рег', 'E_рег', 'E_рег_в', 'E_рег_к']
    labels = [d['паттерн'] for d in items]
    cols = {f: [float(d[f]) for d in items] for f in fields}
    pl = defaultdict(list)
    for i, d in enumerate(items):
        pl[pool_key(d)].append(i)
    pidx = [v for v in pl.values() if len(v) >= 2]

    def sums(lab):
        out = {g: {f: 0.0 for f in fields} for g in PATS}
        for i, g in enumerate(lab):
            o = out[g]
            for f in fields:
                o[f] += cols[f][i]
        return out
    obs = sums(labels)
    rng = random.Random(seed)
    lab = labels[:]
    res = []
    for _ in range(n):
        for idx in pidx:
            cur = [lab[i] for i in idx]
            rng.shuffle(cur)
            for i, g in zip(idx, cur):
                lab[i] = g
        res.append(sums(lab))
    return obs, res


def chi(s, o, e):
    return sum((s[g][o] - s[g][e]) ** 2 / s[g][e] for g in PATS if s[g][e] > 0)


def report(title, items, obs, perms, o, e):
    print(f'--- {title} ---')
    cnt = Counter(d['паттерн'] for d in items)
    for g in PATS:
        O, E = obs[g][o], obs[g][e]
        rat = sorted(p[g][o] / p[g][e] for p in perms if p[g][e] > 0)
        lo, hi = (rat[int(0.025 * len(rat))], rat[int(0.975 * len(rat))]) if rat else (float('nan'),) * 2
        print(f'  {g:<14} n={cnt[g]:>3}  O={O:>7.0f}  E={E:>8.1f}  O/E={O / E if E else float("nan"):.2f}  O−E={O - E:+.1f}  коридор нуля {lo:.2f}–{hi:.2f}')
    c0 = chi(obs, o, e); pc = (sum(1 for p in perms if chi(p, o, e) >= c0) + 1) / (len(perms) + 1)
    print(f'  Σ(O−E)²/E = {c0:.2f}, p = {pc:.3f}')


def contrast(groups, obs, perms, o, e, name):
    O = sum(obs[g][o] for g in groups); E = sum(obs[g][e] for g in groups); d0 = O - E
    diffs = [sum(p[g][o] for g in groups) - sum(p[g][e] for g in groups) for p in perms]
    p_abs = (sum(1 for v in diffs if abs(v) >= abs(d0)) + 1) / (len(diffs) + 1)
    hi = (sum(1 for v in diffs if v >= d0) + 1) / (len(diffs) + 1)
    lo = (sum(1 for v in diffs if v <= d0) + 1) / (len(diffs) + 1)
    p_2min = min(1.0, 2 * min(hi, lo))
    rat = sorted((sum(p[g][o] for g in groups) / sum(p[g][e] for g in groups)) for p in perms if sum(p[g][e] for g in groups) > 0)
    qlo, qhi = rat[int(0.025 * len(rat))], rat[int(0.975 * len(rat))]
    print(f'  контраст {name}: O={O:.0f} E={E:.1f} O/E={O / E:.2f}  p(|O−E|)={p_abs:.3f}  p(одностор.)={min(hi, lo):.3f}  p(2×min хвост)={p_2min:.3f}  коридор нуля 2,5–97,5%: {qlo:.2f}–{qhi:.2f}')
    return O / E if E else float('nan'), p_abs, p_2min


print('=' * 90)
print('1. ФИЛЬТР И ЦЕЛОСТНОСТЬ')
print('=' * 90)
kept = filt(rows)
print('доменов после фильтра:', len(kept))
print('прочие зоны в наборе:', sum(1 for d in kept if d['зона'] not in ('team', 'lol', 'casino', 'buzz')))
print('casino_infix c «casino» в конце метки:', sum(1 for r in rows if r['паттерн имени'] == 'casino_infix' and r['домен'].rsplit('.', 1)[0].endswith('casino')), 'из', sum(1 for r in rows if r['паттерн имени'] == 'casino_infix'))
zp = Counter((d['зона'], d['паттерн']) for d in kept)
for z in ['team', 'lol', 'casino', 'buzz']:
    zz = [d for d in kept if d['зона'] == z]
    S = sum(d['сайтов'] for d in zz); V = sum(d['вышли3'] for d in zz); R = sum(d['рег'] for d in zz)
    print(f'  зона {z:<6} доменов {len(zz):>4}  ' + '  '.join(f'{p} {zp[(z, p)]:>3}' for p in PATS) + f'  | выход {100 * V / S:.1f}%  рег {R}  рег/100 сайтов {100 * R / S:.3f}')

print()
print('=' * 90)
print('2. ОСНОВНОЙ БЛОК: страта «набор + день» (как у тестировщика) — независимый пересчёт')
print('=' * 90)
pools = pools_of(kept, lambda d: d['пул'] if 'пул' in d else (d['набор'], d['день']))
multi = {k: v for k, v in pools.items() if len(set(d['паттерн'] for d in v)) >= 2}
items = [d for v in multi.values() for d in v]
add_E(pools_of(items, lambda d: (d['набор'], d['день'])))
print(f'пулов с >=2 паттернами: {len(multi)}, доменов {len(items)}, сайтов {sum(d["сайтов"] for d in items)}, рег {sum(d["рег"] for d in items)}')
# зонный состав смешанных пулов по паттернам
zc = Counter((d['паттерн'], d['зона']) for d in items)
for g in PATS:
    tot = sum(zc[(g, z)] for z in ['team', 'lol', 'casino', 'buzz'])
    print(f'  {g:<14} ' + '  '.join(f'{z} {zc[(g, z)]:>3} ({100 * zc[(g, z)] / tot:.0f}%)' for z in ['team', 'lol', 'casino', 'buzz']))
# сколько пулов содержат >1 зоны
nz = Counter(len(set(d['зона'] for d in v)) for v in multi.values())
print('  пулов по числу зон внутри:', dict(sorted(nz.items())))
obs, perms = perm(items, lambda d: (d['набор'], d['день']))
report('ВЫХОД (E_сайт)', items, obs, perms, 'вышли3', 'E_вых')
contrast(['casino_prefix', 'casino_infix'], obs, perms, 'вышли3', 'E_вых', 'casino_* по выходу')
report('РЕГИСТРАЦИИ (E_сайт)', items, obs, perms, 'рег', 'E_рег')
r_pool = contrast(['casino_infix'], obs, perms, 'рег', 'E_рег', 'casino_infix по рег (E_сайт)')
contrast(['casino_infix'], obs, perms, 'рег', 'E_рег_в', 'casino_infix по рег (E_вышли)')
contrast(['casino_infix'], obs, perms, 'рег', 'E_рег_к', 'casino_infix по рег (E_клик)')
# состав регистраций casino_infix
ci = sorted([d for d in items if d['паттерн'] == 'casino_infix' and d['рег'] > 0], key=lambda d: -d['рег'])
print('  casino_infix с регистрациями в смешанных пулах:')
for d in ci:
    pool = [x for x in items if (x['набор'], x['день']) == (d['набор'], d['день'])]
    S = sum(x['сайтов'] for x in pool); R = sum(x['рег'] for x in pool)
    zones_in_pool = Counter(x['зона'] for x in pool)
    print(f'    {d["домен"]:<24} зона {d["зона"]:<6} день {d["день"]} рег {d["рег"]}  E_сайт {d["E_рег"]:.2f}  пул: {len(pool)} доменов, {R} рег, зоны {dict(zones_in_pool)}')
print('  регистрации casino_infix по зонам:', dict(Counter(d['зона'] for d in items if d['паттерн'] == 'casino_infix' and d['рег'] > 0)),
      '; суммы рег:', {z: sum(d['рег'] for d in items if d['паттерн'] == 'casino_infix' and d['зона'] == z) for z in ['team', 'lol', 'casino', 'buzz']})

print()
print('=' * 90)
print('3. СТРАТА «набор + день + зона» ПО ВСЕМ ЧЕТЫРЁМ ЗОНАМ (team/lol/casino/buzz)')
print('=' * 90)
kept_z = [dict(d) for d in kept]
pz = pools_of(kept_z, lambda d: (d['набор'], d['день'], d['зона']))
multi_z = {k: v for k, v in pz.items() if len(set(d['паттерн'] for d in v)) >= 2}
items_z = [d for v in multi_z.values() for d in v]
add_E(pools_of(items_z, lambda d: (d['набор'], d['день'], d['зона'])))
print(f'страт с >=2 паттернами: {len(multi_z)}, доменов {len(items_z)}, сайтов {sum(d["сайтов"] for d in items_z)}, рег {sum(d["рег"] for d in items_z)}; '
      f'по зонам: {dict(Counter(k[2] for k in multi_z))}')
obs_z, perms_z = perm(items_z, lambda d: (d['набор'], d['день'], d['зона']))
report('ВЫХОД (E_сайт), страта пул+зона', items_z, obs_z, perms_z, 'вышли3', 'E_вых')
contrast(['casino_prefix', 'casino_infix'], obs_z, perms_z, 'вышли3', 'E_вых', 'casino_* по выходу')
report('РЕГИСТРАЦИИ (E_сайт), страта пул+зона', items_z, obs_z, perms_z, 'рег', 'E_рег')
r_zone = contrast(['casino_infix'], obs_z, perms_z, 'рег', 'E_рег', 'casino_infix по рег (E_сайт)')
contrast(['casino_infix'], obs_z, perms_z, 'рег', 'E_рег_в', 'casino_infix по рег (E_вышли)')
contrast(['casino_infix'], obs_z, perms_z, 'рег', 'E_рег_к', 'casino_infix по рег (E_клик)')
contrast(['casino_prefix', 'casino_infix'], obs_z, perms_z, 'рег', 'E_рег', 'casino_* по рег (E_сайт)')
# по зонам внутри этой же страты
print('  casino_infix по регистрациям, разложение по зонам (страта пул+зона):')
for z in ['team', 'lol', 'casino', 'buzz']:
    O = sum(d['рег'] for d in items_z if d['паттерн'] == 'casino_infix' and d['зона'] == z)
    E = sum(d['E_рег'] for d in items_z if d['паттерн'] == 'casino_infix' and d['зона'] == z)
    n = sum(1 for d in items_z if d['паттерн'] == 'casino_infix' and d['зона'] == z)
    print(f'    {z:<6} n={n:>3}  O={O:>3}  E={E:.1f}  O/E={O / E if E else float("nan"):.2f}')
print('  casino_* по выходу, разложение по зонам (страта пул+зона):')
for z in ['team', 'lol', 'casino', 'buzz']:
    O = sum(d['вышли3'] for d in items_z if d['паттерн'].startswith('casino') and d['зона'] == z)
    E = sum(d['E_вых'] for d in items_z if d['паттерн'].startswith('casino') and d['зона'] == z)
    n = sum(1 for d in items_z if d['паттерн'].startswith('casino') and d['зона'] == z)
    print(f'    {z:<6} n={n:>3}  O={O:>5}  E={E:.0f}  O/E={O / E if E else float("nan"):.2f}')

print()
print('=' * 90)
print('4. ПРОВЕРКА УТВЕРЖДЕНИЯ «одинаковый паттерн чаще в одном блоке часа: 0,75 против 0,65»')
print('=' * 90)
for name, its, key in [('страта пул', items, lambda d: (d['набор'], d['день'])), ('страта пул+зона', items_z, lambda d: (d['набор'], d['день'], d['зона']))]:
    same_p = [0, 0]; diff_p = [0, 0]
    same_acc = [0, 0]; diff_acc = [0, 0]
    same_cf = [0, 0]; diff_cf = [0, 0]
    for ds in pools_of(its, key).values():
        for i in range(len(ds)):
            for j in range(i + 1, len(ds)):
                a, b = ds[i], ds[j]
                tgt = same_p if a['паттерн'] == b['паттерн'] else diff_p
                tgt[0] += 1; tgt[1] += a['блок'] == b['блок']
                t2 = same_acc if a['паттерн'] == b['паттерн'] else diff_acc
                t2[0] += 1; t2[1] += a['акк'] == b['акк']
                t3 = same_cf if a['паттерн'] == b['паттерн'] else diff_cf
                t3[0] += 1; t3[1] += a['cf'] == b['cf']
    print(f'  {name}: пар с одним паттерном {same_p[0]}, из них в одном блоке часа {same_p[1] / same_p[0]:.3f}; '
          f'пар с разными паттернами {diff_p[0]}, в одном блоке {diff_p[1] / diff_p[0]:.3f}')
    print(f'    тот же аккаунт вебмастера: одинаковый паттерн {same_acc[1] / same_acc[0]:.3f} против разных {diff_acc[1] / diff_acc[0]:.3f}; '
          f'тот же cf-аккаунт: {same_cf[1] / same_cf[0]:.3f} против {diff_cf[1] / diff_cf[0]:.3f}')

print()
print('=' * 90)
print('5. ЧУВСТВИТЕЛЬНОСТЬ К ФИЛЬТРУ дней = 1 (добавить 77 доменов с закрытым окном и 150 сайтами)')
print('=' * 90)
kept1 = filt(rows, keep_day1=True)
print('доменов:', len(kept1), '(дней=1:', sum(1 for d in kept1 if d['дней'] == '1'), ')')
p1 = pools_of(kept1, lambda d: (d['набор'], d['день']))
m1 = {k: v for k, v in p1.items() if len(set(d['паттерн'] for d in v)) >= 2}
it1 = [d for v in m1.values() for d in v]
add_E(pools_of(it1, lambda d: (d['набор'], d['день'])))
print(f'пулов с >=2 паттернами: {len(m1)}, доменов {len(it1)}, рег {sum(d["рег"] for d in it1)}')
obs1, perms1 = perm(it1, lambda d: (d['набор'], d['день']), n=4000)
report('ВЫХОД (E_сайт), с дней=1', it1, obs1, perms1, 'вышли3', 'E_вых')
report('РЕГИСТРАЦИИ (E_сайт), с дней=1', it1, obs1, perms1, 'рег', 'E_рег')
contrast(['casino_infix'], obs1, perms1, 'рег', 'E_рег', 'casino_infix по рег (E_сайт), с дней=1')

print()
print('=' * 90)
print('6. ПЛАН ОЖИДАЛ ≈109 пулов / ≈1110 доменов — при каком фильтре это получается?')
print('=' * 90)
for name, cond in [('без фильтра дней и окна (только выбросы и НЕ ЗАПИСАН)', lambda r: r['домен'] not in OUT and r['набор контента'] != NC),
                   ('окно закрыто, без дней-фильтра', lambda r: r['домен'] not in OUT and r['набор контента'] != NC and r['окно закрыто'] == 'да'),
                   ('фильтр тестировщика', lambda r: r['домен'] not in OUT and r['набор контента'] != NC and r['окно закрыто'] == 'да' and r['дней'] != '1')]:
    ds = [prep(r) for r in rows if cond(r)]
    pp = pools_of(ds, lambda d: (d['набор'], d['день']))
    mm = {k: v for k, v in pp.items() if len(set(d['паттерн'] for d in v)) >= 2}
    print(f'  {name}: доменов {len(ds)}, пулов ≥2 паттернов {len(mm)}, доменов в них {sum(len(v) for v in mm.values())}')

print()
print('=' * 90)
print('ИТОГ ПРОВЕРКИ')
print('=' * 90)
print(f'casino_infix по регистрациям: страта пул O/E {r_pool[0]:.2f}, p(|O−E|) {r_pool[1]:.3f}, p(2×min) {r_pool[2]:.3f}; '
      f'страта пул+зона O/E {r_zone[0]:.2f}, p(|O−E|) {r_zone[1]:.3f}, p(2×min) {r_zone[2]:.3f}')

print()
print('=' * 90)
print('7. ОТКУДА «0,04 против 0,11 рег/100 сайтов» (сырой разрыв casino-имён из формулировки гипотезы)')
print('=' * 90)
def rate_table(name, rs):
    S = sum(toi(r['сайтов в окне']) for r in rs); R = sum(toi(r['регистраций в окне 3 суток']) for r in rs)
    Sa = sum(toi(r['сайтов']) for r in rs); Ra = sum(toi(r['регистраций']) for r in rs)
    print(f'  {name:<58} n={len(rs):>4}  рег в окне/100 сайтов в окне {100 * R / S if S else 0:.3f}   рег за всё время/100 сайтов {100 * Ra / Sa if Sa else 0:.3f}')
for scope, cond in [('весь свод (без выбросов)', lambda r: r['домен'] not in OUT),
                    ('весь свод, окно закрыто', lambda r: r['домен'] not in OUT and r['окно закрыто'] == 'да'),
                    ('фильтр тестировщика', lambda r: r['домен'] not in OUT and r['окно закрыто'] == 'да' and r['дней'] != '1' and r['набор контента'] != NC)]:
    print(f' {scope}:')
    rate_table('casino_prefix', [r for r in rows if cond(r) and r['паттерн имени'] == 'casino_prefix'])
    rate_table('casino_infix', [r for r in rows if cond(r) and r['паттерн имени'] == 'casino_infix'])
    rate_table('casino_* вместе', [r for r in rows if cond(r) and r['паттерн имени'].startswith('casino')])
    rate_table('numeric + alpha_other', [r for r in rows if cond(r) and not r['паттерн имени'].startswith('casino')])
    rate_table('numeric + alpha_other, только с 04.09 (когда есть casino)', [r for r in rows if cond(r) and not r['паттерн имени'].startswith('casino') and r['день запуска'] >= '2026-09-04'])

print()
print('=' * 90)
print('8. ПЛАНОВЫЕ «≈109 пулов / ≈1110 доменов»: получаются ли с «КОНТЕНТ НЕ ЗАПИСАН» как набором?')
print('=' * 90)
for name, cond in [('с НЕ ЗАПИСАН как набором, без прочих фильтров', lambda r: r['домен'] not in OUT),
                   ('с НЕ ЗАПИСАН, окно закрыто', lambda r: r['домен'] not in OUT and r['окно закрыто'] == 'да'),
                   ('с НЕ ЗАПИСАН, окно закрыто, дней != 1', lambda r: r['домен'] not in OUT and r['окно закрыто'] == 'да' and r['дней'] != '1')]:
    ds = [prep(r) for r in rows if cond(r)]
    pp = pools_of(ds, lambda d: (d['набор'], d['день']))
    mm = {k: v for k, v in pp.items() if len(set(d['паттерн'] for d in v)) >= 2}
    nc_pools = sum(1 for k in mm if k[0] == NC)
    print(f'  {name}: доменов {len(ds)}, пулов ≥2 паттернов {len(mm)} (из них НЕ ЗАПИСАН: {nc_pools}), доменов в них {sum(len(v) for v in mm.values())}')
print('  => каузация в оговорке 7 тестировщика («из-за фильтра дней ≠ 1 и закрытого окна») проверяется здесь и в разделе 6.')

print()
print('=' * 90)
print('9. КОНТРАСТ casino_infix: p по ОТНОШЕНИЮ O/E и чувствительность к seed')
print('=' * 90)
def contrast_ratio_p(obs, perms, groups, o, e):
    O = sum(obs[g][o] for g in groups); E = sum(obs[g][e] for g in groups); r0 = O / E
    rats = [sum(p[g][o] for g in groups) / sum(p[g][e] for g in groups) for p in perms if sum(p[g][e] for g in groups) > 0]
    hi = (sum(1 for v in rats if v >= r0) + 1) / (len(rats) + 1)
    lo = (sum(1 for v in rats if v <= r0) + 1) / (len(rats) + 1)
    p_abs_log = (sum(1 for v in rats if v > 0 and abs(__import__('math').log(v)) >= abs(__import__('math').log(r0))) + 1) / (len(rats) + 1)
    return r0, hi, min(1.0, 2 * min(hi, lo)), p_abs_log
r0, p_hi, p_2m, p_lg = contrast_ratio_p(obs, perms, ['casino_infix'], 'рег', 'E_рег')
print(f'  страта пул, seed=1: O/E={r0:.2f}; p(O/E >= набл., одностор.)={p_hi:.3f}; p(2×min хвост по O/E)={p_2m:.3f}; p(|log O/E|)={p_lg:.3f}')
for sd in (2, 3, 4):
    obs_s, perms_s = perm(items, lambda d: (d['набор'], d['день']), n=10000, seed=sd)
    O = obs_s['casino_infix']['рег']; E = obs_s['casino_infix']['E_рег']; d0 = O - E
    diffs = [p['casino_infix']['рег'] - p['casino_infix']['E_рег'] for p in perms_s]
    p_abs = (sum(1 for v in diffs if abs(v) >= abs(d0)) + 1) / (len(diffs) + 1)
    hi = (sum(1 for v in diffs if v >= d0) + 1) / (len(diffs) + 1)
    lo = (sum(1 for v in diffs if v <= d0) + 1) / (len(diffs) + 1)
    r0, p_hi, p_2m, p_lg = contrast_ratio_p(obs_s, perms_s, ['casino_infix'], 'рег', 'E_рег')
    print(f'  страта пул, seed={sd}: p(|O−E|)={p_abs:.3f}, p(2×min по O−E)={min(1.0, 2 * min(hi, lo)):.3f}, p(2×min по O/E)={p_2m:.3f}, p(|log O/E|)={p_lg:.3f}')
r0, p_hi, p_2m, p_lg = contrast_ratio_p(obs_z, perms_z, ['casino_infix'], 'рег', 'E_рег')
print(f'  страта пул+зона (все 4 зоны), seed=1: O/E={r0:.2f}; p(одностор. по O/E)={p_hi:.3f}; p(2×min по O/E)={p_2m:.3f}; p(|log O/E|)={p_lg:.3f}')
# без зоны casino (только team/lol/buzz), страта пул+зона
items_nz = [d for d in items_z if d['зона'] != 'casino']
pz2 = pools_of(items_nz, lambda d: (d['набор'], d['день'], d['зона']))
m2 = {k: v for k, v in pz2.items() if len(set(d['паттерн'] for d in v)) >= 2}
it2 = [d for v in m2.values() for d in v]
add_E(pools_of(it2, lambda d: (d['набор'], d['день'], d['зона'])))
obs2, perms2 = perm(it2, lambda d: (d['набор'], d['день'], d['зона']), n=10000)
print(f'  страта пул+зона без зоны casino: страт {len(m2)}, доменов {len(it2)}, рег {sum(d["рег"] for d in it2)}')
contrast(['casino_infix'], obs2, perms2, 'рег', 'E_рег', 'casino_infix по рег (E_сайт), пул+зона, без .casino')
contrast(['casino_prefix', 'casino_infix'], obs2, perms2, 'вышли3', 'E_вых', 'casino_* по выходу, пул+зона, без .casino')

print()
print('=' * 90)
print('10. ЗОНА .casino: у 87 alpha_other-доменов «casino» стоит в самом имени домена (зона) — они считаются НЕ casino-именами')
print('=' * 90)
cz = [d for d in items if d['зона'] == 'casino']
print(f'  в смешанных пулах основного блока доменов зоны .casino: {len(cz)} (паттерны {dict(Counter(d["паттерн"] for d in cz))}); '
      f'рег {sum(d["рег"] for d in cz)}, E_сайт {sum(d["E_рег"] for d in cz):.1f}, O/E {sum(d["рег"] for d in cz) / sum(d["E_рег"] for d in cz):.2f}; '
      f'выход O/E {sum(d["вышли3"] for d in cz) / sum(d["E_вых"] for d in cz):.2f}')
# альтернативная классификация: «casino в полном имени домена» (метка или зона) против остальных, страта пул
for d in items:
    d['casino_full'] = 'casino в имени (метка или зона)' if (d['паттерн'].startswith('casino') or d['зона'] == 'casino') else 'без casino'
grp = defaultdict(lambda: dict(n=0, O=0, E=0.0, V=0, EV=0.0))
for d in items:
    g = grp[d['casino_full']]; g['n'] += 1; g['O'] += d['рег']; g['E'] += d['E_рег']; g['V'] += d['вышли3']; g['EV'] += d['E_вых']
for k, g in grp.items():
    print(f'  {k:<34} n={g["n"]:>3}  рег O={g["O"]:>3} E={g["E"]:.1f} O/E={g["O"] / g["E"]:.2f}   выход O={g["V"]} E={g["EV"]:.0f} O/E={g["V"] / g["EV"]:.2f}')

print()
print('=' * 90)
print('11. ПОЛНОТА 7-СУТОЧНОГО ВЫХОДА: свод от 21.09, последний день <= 14.09 => 7-е сутки = 21.09 (день свода)')
print('=' * 90)
by_last = defaultdict(lambda: [0, 0, 0])
for r in rows:
    if r['домен'] in OUT or r['окно закрыто'] != 'да' or r['набор контента'] == NC or r['дней'] == '1':
        continue
    if r['вышли за 7 суток'] == '':
        continue
    b = by_last[r['последний день']]; b[0] += 1; b[1] += toi(r['вышли за 3 суток']); b[2] += toi(r['вышли за 7 суток'])
for k in sorted(by_last):
    if k >= '2026-09-08':
        n, v3, v7 = by_last[k]
        print(f'  последний день {k}: доменов {n:>3}, вышли3 {v3:>5}, вышли7 {v7:>5}, 7/3 = {v7 / v3 if v3 else 0:.3f}')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""w17_teni.py — скептик/ТЕНИ к гипотезе №17 (повторные регистрации с одного сайта).
Вопрос: эффект «33 повтора против 4.3 случайных (7.6x)» — не тень ли он
(а) совместного пула «набор контента + день запуска (+ зона, + блок часа)»,
(б) ДАТЫ самой регистрации (бренд бывает «горячим» в конкретный день по всему парку),
(в) объёма домена (богатые домены с R>=5),
(г) августа («КОНТЕНТ НЕ ЗАПИСАН») против сентября, зоны,
(д) одного и того же человека (все регистрации домена в один день).
Только stdlib. Единица — домен. Тест — перестановочный.
"""
import csv, os, sys, random, collections, math, re

REPO = '/home/user/cladue'
SRC = os.path.join(REPO, 'analysis/export/svod_domenov_21.09.csv')
OUT = os.path.join(REPO, 'analysis/export/gipotezy_svod/w17_teni.txt')
NPERM = 10000
random.seed(17)

class Tee:
    def __init__(self, path):
        self.f = open(path, 'w', encoding='utf-8'); self.o = sys.__stdout__
    def write(self, s): self.f.write(s); self.o.write(s)
    def flush(self): self.f.flush(); self.o.flush()

BRAND_RE = re.compile(r'^(.*?)\s*\((\d+)\)$')

def I(x):
    x = (x or '').strip()
    try: return int(float(x.replace(',', '.')))
    except Exception: return 0

def parse_brands(s):
    out = []
    for item in (s or '').strip().split(','):
        m = BRAND_RE.match(item.strip())
        if m: out.append((m.group(1), int(m.group(2))))
    return out

def attribute_fd(bc, fd):
    """как у тестировщика: депозиты снимаются с брендов, начиная с самого крупного"""
    regs = dict(bc); left = fd
    for b in sorted(bc, key=lambda b: -bc[b]):
        if left == 0: break
        take = min(bc[b] - 1, left)
        regs[b] -= take; left -= take
    return {b: c for b, c in regs.items() if c > 0}

def attribute_fd_min(bc, fd):
    """противоположный крайний вариант: депозиты снимаются с самых мелких подходящих брендов"""
    regs = dict(bc); left = fd
    for b in sorted(bc, key=lambda b: bc[b]):
        if left == 0: break
        take = min(bc[b] - 1, left)
        regs[b] -= take; left -= take
    return {b: c for b, c in regs.items() if c > 0}

def bh_fdr(ps):
    n = len(ps); idx = sorted(range(n), key=lambda i: ps[i]); q = [0.0]*n; prev = 1.0
    for r in range(n-1, -1, -1):
        i = idx[r]; v = min(prev, ps[i]*n/(r+1)); q[i] = v; prev = v
    return q

def pct(a, b): return 100.0*a/b if b else 0.0

# ---------------------------------------------------------------- данные
sys.stdout = Tee(OUT)
rows_all = list(csv.DictReader(open(SRC, encoding='utf-8')))
print('w17 ТЕНИ к гипотезе №17: повторы с одного сайта — не тень ли пула, даты, объёма, августа?')
print(f'Источник: analysis/export/svod_domenov_21.09.csv; доменов в своде {len(rows_all)}')
print()

OUTLIERS = {'3615.team', '3286.team'}
kept, drop_day1, drop_open, drop_out = [], 0, 0, 0
for r in rows_all:
    if r['домен'] in OUTLIERS: drop_out += 1; continue
    if I(r['дней']) == 1: drop_day1 += 1; continue
    if r['окно закрыто'].strip() != 'да': drop_open += 1; continue
    kept.append(r)
print('ФИЛЬТРЫ (те же, что у тестировщика, чтобы числа были сравнимы)')
print(f'  выброшено: дней = 1 — {drop_day1}; окно не закрыто — {drop_open}; выбросы 3615/3286 — {drop_out}; осталось {len(kept)}')

D = []   # список доменов с регистрациями
for r in kept:
    R = I(r['регистраций']); S = I(r['сайтов с регистрацией'])
    if R == 0: continue
    bc = dict(parse_brands(r['какие бренды конвертили']))
    regs = attribute_fd(bc, I(r['ФД']))
    regs_min = attribute_fd_min(bc, I(r['ФД']))
    dates = r['даты регистраций'].split()
    D.append(dict(dom=r['домен'], zone=r['зона'], day=r['день запуска'], hb=r['блок часа'],
                  setn=r['набор контента'], R=R, S=S, fd=I(r['ФД']), regs=regs, regs_min=regs_min,
                  dates=dates, ndates=len(set(dates))))

R_tot = sum(d['R'] for d in D); S_tot = sum(d['S'] for d in D)
rep_obs = R_tot - S_tot
print(f'  доменов с регистрациями {len(D)}; регистраций {R_tot}; сайтов с регистрацией {S_tot}; '
      f'повторов R−S = {rep_obs} ({pct(rep_obs,R_tot):.1f} % регистраций)')

# сверка: восстановленные по брендам числа сайтов должны совпасть с колонкой
mism = sum(1 for d in D if len(d['regs']) != d['S'] or sum(d['regs'].values()) != d['R'])
mism_min = sum(1 for d in D if len(d['regs_min']) != d['S'] or sum(d['regs_min'].values()) != d['R'])
print(f'  сверка «бренды после снятия ФД» с колонками R/S: расхождений {mism} (при обратной раздаче ФД {mism_min})')
print(f'  ВАЖНО: сама величина 33 взята из колонок «регистраций» и «сайтов с регистрацией» — от раздачи ФД не зависит.')
print()

# плоский список регистраций
items = []   # (домен_idx, бренд, дата)
for i, d in enumerate(D):
    lab = []
    for b, c in d['regs'].items(): lab += [b]*c
    # даты домена раздаём меткам произвольно (внутри домена порядок неизвестен) — учтено ниже усреднением
    for j, b in enumerate(lab): items.append([i, b, d['dates'][j]])
labels = [it[1] for it in items]
dom_of = [it[0] for it in items]
NI = len(items)
brand_tot = collections.Counter(labels)
print(f'  регистраций-событий с брендом {NI}; разных брендов {len(brand_tot)}; '
      f'Σp² = {sum((v/NI)**2 for v in brand_tot.values()):.4f} (эффективных брендов {1/sum((v/NI)**2 for v in brand_tot.values()):.0f})')
print()

def repeats_from(assign):
    """assign: список брендов по позициям items -> Σ(R − S)"""
    per = collections.defaultdict(set); cnt = collections.Counter()
    for k, b in enumerate(assign):
        per[dom_of[k]].add(b); cnt[dom_of[k]] += 1
    return sum(cnt[i] - len(per[i]) for i in cnt)

assert repeats_from(labels) == rep_obs, (repeats_from(labels), rep_obs)

def perm_test(groups, nperm=NPERM, subset=None):
    """groups: список ключей страты по позициям items. Перестановка меток внутри страты.
       subset: множество позиций, по которым считать статистику (None = все)."""
    by = collections.defaultdict(list)
    for k, g in enumerate(groups): by[g].append(k)
    sel = set(range(NI)) if subset is None else subset
    def stat(assign):
        per = collections.defaultdict(set); cnt = collections.Counter()
        for k in sel:
            per[dom_of[k]].add(assign[k]); cnt[dom_of[k]] += 1
        return sum(cnt[i] - len(per[i]) for i in cnt)
    obs = stat(labels)
    cur = list(labels); vals = []
    idxs = [v for v in by.values() if len(v) > 1]
    pools = [[labels[k] for k in v] for v in idxs]
    for _ in range(nperm):
        for v, p in zip(idxs, pools):
            random.shuffle(p)
            for k, b in zip(v, p): cur[k] = b
        vals.append(stat(cur))
    vals.sort()
    m = sum(vals)/len(vals)
    p = (sum(1 for x in vals if x >= obs) + 1)/(len(vals) + 1)
    lo, hi = vals[int(0.025*len(vals))], vals[int(0.975*len(vals))-1]
    return obs, m, lo, hi, vals[-1], p, len(set(groups))

print('='*100)
print('(1) ГЛАВНОЕ: одно и то же наблюдение 33 против РАЗНЫХ нулей — от самого слабого к самому жёсткому')
print('='*100)
print('  Ноль тем жёстче, чем больше он удерживает постоянным: бренд редко «ходит» равномерно по всему парку и по всем дням.')
print()
hdr = '  ноль (что удерживается постоянным) | страт | набл. | ожид. | 95 %-й интервал нуля | макс | O/E | p'
print(hdr); print('  ' + '-'*98)
res = {}
def line(name, groups, subset=None, nperm=NPERM):
    o, m, lo, hi, mx, p, ns = perm_test(groups, nperm, subset)
    res[name] = (o, m, lo, hi, mx, p)
    print(f'  {name:<52} | {ns:>5} | {o:>5} | {m:>5.1f} | {lo:>3}–{hi:<16} | {mx:>4} | {o/m if m else float("inf"):>4.1f} | {p:.4f}')
    return res[name]

line('глобальный (только маргиналы брендов)', ['ALL']*NI)
line('зона', [D[dom_of[k]]['zone'] for k in range(NI)])
line('день запуска', [D[dom_of[k]]['day'] for k in range(NI)])
line('набор контента', [D[dom_of[k]]['setn'] for k in range(NI)])
line('пул: набор + день запуска', [(D[dom_of[k]]['setn'], D[dom_of[k]]['day']) for k in range(NI)])
line('пул: набор + день + зона', [(D[dom_of[k]]['setn'], D[dom_of[k]]['day'], D[dom_of[k]]['zone']) for k in range(NI)])
line('пул: набор + день + зона + блок часа',
     [(D[dom_of[k]]['setn'], D[dom_of[k]]['day'], D[dom_of[k]]['zone'], D[dom_of[k]]['hb']) for k in range(NI)])
line('ДАТА самой регистрации', [items[k][2] for k in range(NI)])
line('ДАТА регистрации + зона', [(items[k][2], D[dom_of[k]]['zone']) for k in range(NI)])
print()
g, e = res['глобальный (только маргиналы брендов)'], res['пул: набор + день + зона + блок часа']
print(f'  Уже здесь видно: «в 7.6 раза больше случайного» держится ТОЛЬКО на самом слабом нуле ({g[0]}/{g[1]:.1f} = {g[0]/g[1]:.1f}).')
print(f'  При жёсткой страте «набор + день + зона + блок часа» ожидание {e[1]:.1f}, то есть кратность падает до {e[0]/e[1]:.1f}.')
print()

# ------------- дата: усреднение по раздаче дат внутри домена -------------
print('='*100)
print('(2) ДАТА РЕГИСТРАЦИИ: в своде не видно, какая регистрация домена какому бренду и какой дате отвечает.')
print('    Усредняем по случайным раздачам дат внутри домена (множественное восполнение), 40 раздач × 400 перестановок.')
print('='*100)
mrep = []
for rep in range(40):
    dts = []
    for i, d in enumerate(D):
        dd = list(d['dates']); random.shuffle(dd); dts.append(dd)
    grp = []; ptr = collections.Counter()
    for k in range(NI):
        i = dom_of[k]; grp.append(dts[i][ptr[i]]); ptr[i] += 1
    o, m, lo, hi, mx, p, ns = perm_test(grp, 400)
    mrep.append((m, p))
mm = sum(x[0] for x in mrep)/len(mrep)
pm = sum(x[1] for x in mrep)/len(mrep)
print(f'  усреднённое ожидание при перестановке внутри даты регистрации: {mm:.1f} (разброс по раздачам '
      f'{min(x[0] for x in mrep):.1f}–{max(x[0] for x in mrep):.1f}); O/E = {rep_obs/mm:.1f}; средний p = {pm:.4f}')
print(f'  Дат регистраций всего {len(set(it[2] for it in items))}; в среднем {NI/len(set(it[2] for it in items)):.1f} регистраций в день по всему парку.')
print()

# ------------- (3) объём домена / выбросы -------------
print('='*100)
print('(3) ОБЪЁМ ДОМЕНА: сколько повторов держат «богатые» домены, и что остаётся без них')
print('='*100)
pool_g = [(D[dom_of[k]]['setn'], D[dom_of[k]]['day']) for k in range(NI)]
hard_g = [(D[dom_of[k]]['setn'], D[dom_of[k]]['day'], D[dom_of[k]]['zone']) for k in range(NI)]
print('  R домена | доменов | регистраций | повторов | доля всех повторов')
buck = collections.defaultdict(lambda: [0,0,0])
for d in D:
    key = d['R'] if d['R'] <= 4 else 5
    buck[key][0] += 1; buck[key][1] += d['R']; buck[key][2] += d['R']-d['S']
for k in sorted(buck):
    nm = str(k) if k <= 4 else '≥5'
    b = buck[k]
    print(f'  {nm:>8} | {b[0]:>7} | {b[1]:>11} | {b[2]:>8} | {pct(b[2],rep_obs):.0f} %')
top = sorted(D, key=lambda d: -(d['R']-d['S']))[:5]
print('  Топ-домены по числу повторов: ' + '; '.join(f"{d['dom']} (R{d['R']}/S{d['S']} = {d['R']-d['S']})" for d in top))
for drop in (1, 3):
    dropset = {D.index(d) for d in top[:drop]}
    sub = {k for k in range(NI) if dom_of[k] not in dropset}
    o, m, lo, hi, mx, p, ns = perm_test(pool_g, NPERM, sub)
    o2, m2, lo2, hi2, mx2, p2, _ = perm_test(hard_g, NPERM, sub)
    print(f'  без {drop} самых «повторных» доменов: повторов {o}; пул набор+день E {m:.1f} (O/E {o/m:.1f}, p {p:.4f}); '
          f'набор+день+зона E {m2:.1f} (O/E {o2/m2:.1f}, p {p2:.4f})')
sub2 = {k for k in range(NI) if D[dom_of[k]]['R'] == 2}
o, m, lo, hi, mx, p, ns = perm_test(pool_g, NPERM, sub2)
print(f'  только домены с R = 2 ({sum(1 for d in D if d["R"]==2)} доменов, {len(sub2)} регистраций): повторов {o}; '
      f'пул набор+день E {m:.1f} (интервал {lo}–{hi}); O/E {o/m:.1f}; p {p:.4f}')
print()

# ------------- (4) август/сентябрь, зона -------------
print('='*100)
print('(4) АВГУСТ («КОНТЕНТ НЕ ЗАПИСАН») ПРОТИВ СЕНТЯБРЯ И ЗОНЫ: где живут повторы')
print('='*100)
def split_report(name, keyf, groups):
    ks = sorted(set(keyf(D[dom_of[k]]) for k in range(NI)))
    print(f'  срез: {name}')
    print('    группа | доменов | регистраций | повторов | доля рег. | ожид. (пул набор+день) | O/E | p')
    for kk in ks:
        sub = {k for k in range(NI) if keyf(D[dom_of[k]]) == kk}
        nd = len({dom_of[k] for k in sub})
        o, m, lo, hi, mx, p, _ = perm_test(groups, 3000, sub)
        print(f'    {str(kk):<22} | {nd:>7} | {len(sub):>11} | {o:>8} | {pct(o,len(sub)):>7.1f} % | {m:>21.1f} | {o/m if m else 0:>4.1f} | {p:.4f}')
split_report('набор записан или нет', lambda d: 'КОНТЕНТ НЕ ЗАПИСАН' if d['setn'].startswith('КОНТЕНТ НЕ') else 'набор записан', pool_g)
split_report('месяц запуска', lambda d: d['day'][:7], pool_g)
split_report('зона', lambda d: d['zone'] if d['zone'] in ('team','lol') else 'прочие', pool_g)
print()

# ------------- (5) один человек: все регистрации в один день -------------
print('='*100)
print('(5) ОДИН ЧЕЛОВЕК ИЛИ ДВА: повторы, у которых даты домена не расходятся')
print('='*100)
same_day_dom = [d for d in D if d['R'] > d['S'] and d['ndates'] == 1]
sd_rep = sum(d['R']-d['S'] for d in same_day_dom)
# повторы, которые обязаны быть в один день: если дат меньше, чем сайтов+повторов — оценка снизу
forced = 0
for d in D:
    if d['R'] > d['S']:
        # минимальное число пар «одинаковый бренд в одну дату»
        forced += max(0, (d['R']-d['S']) - (d['ndates']-1))
print(f'  доменов с повтором, где ВСЕ регистрации в один день: {len(same_day_dom)} из {sum(1 for d in D if d["R"]>d["S"])}; '
      f'в них повторов {sd_rep} из {rep_obs} ({pct(sd_rep,rep_obs):.0f} %)')
print(f'  нижняя оценка числа повторов, которые заведомо пришлись на одну дату (дат домена не хватает, чтобы их развести): {forced}')
sub = {k for k in range(NI) if D[dom_of[k]]['ndates'] > 1}
o, m, lo, hi, mx, p, _ = perm_test(pool_g, NPERM, sub)
o2, m2, _, _, _, p2, _ = perm_test(hard_g, NPERM, sub)
print(f'  если однодневные домены выкинуть целиком ({len(D)-len({dom_of[k] for k in sub})} доменов): '
      f'повторов {o}; пул набор+день E {m:.1f} (O/E {o/m:.1f}, p {p:.4f}); набор+день+зона E {m2:.1f} (O/E {o2/m2:.1f}, p {p2:.4f})')
print()

# ------------- (6) сгущение брендов под жёстким нулём -------------
print('='*100)
print('(6) СГУЩЕНИЕ ПЯТИ БРЕНДОВ (Leon, Martin, Pinco, Mellstroy, Twin) — под нулём с пулом вместо глобального')
print('='*100)
FOCUS = ['Leon','Martin','Pinco','Mellstroy','Twin','Олимп','Lucky Bird','Shuffle','Goodwin']
def cond_index(groups, nperm=4000, regs_key='regs'):
    # пересобрать метки под выбранную раздачу ФД
    lab = []; dm = []
    for i, d in enumerate(D):
        for b, c in d[regs_key].items():
            lab += [b]*c; dm += [i]*c
    n = len(lab)
    by = collections.defaultdict(list)
    for k, g in enumerate(groups[:n] if len(groups) >= n else groups): by[g].append(k)
    idxs = [v for v in by.values() if len(v) > 1]
    pools = [[lab[k] for k in v] for v in idxs]
    obsD = collections.defaultdict(set)
    for k, b in enumerate(lab): obsD[b].add(dm[k])
    Dobs = {b: len(v) for b, v in obsD.items()}
    acc = collections.defaultdict(float); le = collections.Counter()
    cur = list(lab)
    for _ in range(nperm):
        for v, p in zip(idxs, pools):
            random.shuffle(p)
            for k, b in zip(v, p): cur[k] = b
        dd = collections.defaultdict(set)
        for k, b in enumerate(cur): dd[b].add(dm[k])
        for b in Dobs:
            v = len(dd[b]); acc[b] += v
            if v <= Dobs[b]: le[b] += 1
    return Dobs, {b: acc[b]/nperm for b in Dobs}, {b: (le[b]+1)/(nperm+1) for b in Dobs}, collections.Counter(lab)
for gname, groups in (('глобальный', ['ALL']*NI), ('пул: набор + день', pool_g), ('пул: набор + день + зона', hard_g)):
    Dobs, Eexp, pv, nreg = cond_index(groups)
    cands = [b for b in Dobs if nreg[b] >= 5]
    qs = dict(zip(cands, bh_fdr([pv[b] for b in cands])))
    print(f'  ноль: {gname} (перестановка меток бренда, число регистраций у домена сохранено); брендов с ≥5 рег.: {len(cands)}')
    print('    бренд | рег. | D_набл | E[D] | индекс E/D | p | q')
    for b in FOCUS:
        if b not in Dobs or b not in qs: continue
        print(f'    {b:<12} | {nreg[b]:>4} | {Dobs[b]:>6} | {Eexp[b]:>4.1f} | {Eexp[b]/Dobs[b]:>10.2f} | {pv[b]:.4f} | {qs[b]:.3f}')
    print(f'    брендов с q < 0,05: {sum(1 for b in cands if qs[b] < 0.05)} из {len(cands)}')
print()
print('  Чувствительность к раздаче ФД (в своде «конверсии» = регистрации + ФД; кому из брендов домена отдать депозит — неизвестно):')
for kk, nm in (('regs','ФД снимаем с крупнейшего бренда (как у тестировщика)'), ('regs_min','ФД снимаем с мельчайшего подходящего')):
    Dobs, Eexp, pv, nreg = cond_index(pool_g, 2000, kk)
    cands = [b for b in Dobs if nreg[b] >= 5]
    qs = dict(zip(cands, bh_fdr([pv[b] for b in cands])))
    s = '; '.join(f'{b} {nreg.get(b,0)}рег D{Dobs.get(b,0)} индекс {Eexp[b]/Dobs[b]:.2f} q {qs.get(b,1):.3f}' for b in ['Leon','Martin','Pinco','Mellstroy','Twin'] if b in Dobs and b in qs)
    print(f'    {nm}: {s}')
print()

# ------------- (7) парные сравнения внутри пула -------------
print('='*100)
print('(7) ПАРНЫЕ СРАВНЕНИЯ ВНУТРИ ПУЛА: доля повторов у домена против соседей по «набор + день + зона»')
print('='*100)
bypool = collections.defaultdict(list)
for d in D: bypool[(d['setn'], d['day'], d['zone'])].append(d)
usable = {k: v for k, v in bypool.items() if len(v) >= 2 and sum(x['R'] for x in v) >= 3}
nrep_pool = sum(x['R']-x['S'] for v in usable.values() for x in v)
nreg_pool = sum(x['R'] for v in usable.values() for x in v)
print(f'  пулов с ≥2 доменами с регистрациями и ≥3 регистрациями: {len(usable)}; доменов {sum(len(v) for v in usable.values())}; '
      f'регистраций {nreg_pool}; повторов {nrep_pool}')
sub = {k for k in range(NI) if (D[dom_of[k]]['setn'], D[dom_of[k]]['day'], D[dom_of[k]]['zone']) in usable}
o, m, lo, hi, mx, p, _ = perm_test(hard_g, NPERM, sub)
print(f'  внутри этих пулов: повторов {o}, ожидание {m:.1f} (95 %-й интервал нуля {lo}–{hi}, максимум {mx}); O/E {o/m:.1f}; p = {p:.4f}')
print(f'  оставшиеся {rep_obs-o} повторов лежат в пулах, где сравнивать не с кем (домен в пуле один) — '
      f'то есть {pct(rep_obs-o,rep_obs):.0f} % эффекта вообще не проходят парного сравнения.')
print()


print('  (7б) ЧТО ИМЕННО ПОРТИТ ЖЁСТКУЮ СТРАТУ: страты, где домен один, перестановка не двигает — их повторы')
print('       попадают и в наблюдение, и в ожидание. Считаем долю таких «запертых» повторов.')
for nm, keyf in (('набор + день', lambda d:(d['setn'],d['day'])),
                 ('набор + день + зона', lambda d:(d['setn'],d['day'],d['zone'])),
                 ('набор + день + зона + блок часа', lambda d:(d['setn'],d['day'],d['zone'],d['hb']))):
    bp = collections.defaultdict(set)
    for d in D: bp[keyf(d)].add(d['dom'])
    locked = sum(d['R']-d['S'] for d in D if len(bp[keyf(d)]) == 1)
    lockreg = sum(d['R'] for d in D if len(bp[keyf(d)]) == 1)
    print(f'    {nm:<34}: страт с одним доменом держат {locked} из {rep_obs} повторов ({pct(locked,rep_obs):.0f} %) и {lockreg} из {R_tot} регистраций')
print()
print('  (7в) ЧЕСТНАЯ ОЦЕНКА: только пулы «набор + день + зона» с ≥2 доменами, три варианта очистки')
def clean(name, keep):
    sub = {k for k in range(NI) if keep(D[dom_of[k]])}
    sub = {k for k in sub if (D[dom_of[k]]['setn'], D[dom_of[k]]['day'], D[dom_of[k]]['zone']) in usable}
    if not sub: return
    nd = len({dom_of[k] for k in sub})
    o, m, lo, hi, mx, p, _ = perm_test(hard_g, NPERM, sub)
    print(f'    {name:<46} доменов {nd:>3}, рег. {len(sub):>3}: повторов {o:>2}, E {m:>4.1f} '
          f'(интервал нуля {lo}–{hi}, макс {mx}); O/E {o/m:.1f}; p = {p:.4f}')
clean('все', lambda d: True)
clean('без «КОНТЕНТ НЕ ЗАПИСАН»', lambda d: not d['setn'].startswith('КОНТЕНТ НЕ'))
clean('без однодневных доменов (возможный дубль человека)', lambda d: d['ndates'] > 1)
clean('без «КОНТЕНТ НЕ ЗАПИСАН» и без однодневных', lambda d: d['ndates'] > 1 and not d['setn'].startswith('КОНТЕНТ НЕ'))
clean('без домена-рекордсмена 2334.team', lambda d: d['dom'] != '2334.team')
print()

# ------------- ИТОГ -------------
print('='*100)
print('ВЫВОД')
print('='*100)
g = res['глобальный (только маргиналы брендов)']
p1 = res['пул: набор + день запуска']
p2 = res['пул: набор + день + зона']
p3 = res['пул: набор + день + зона + блок часа']
dt = res['ДАТА самой регистрации']
print(f'  наблюдение одно и то же: {rep_obs} повторов из {R_tot} регистраций ({pct(rep_obs,R_tot):.1f} %) на {len(D)} доменах с регистрациями.')
print(f'  глобальный ноль: E {g[1]:.1f}, O/E {g[0]/g[1]:.1f}  <- это и есть «в 7.6 раза»')
print(f'  набор + день:            E {p1[1]:.1f}, O/E {p1[0]/p1[1]:.1f}, p {p1[5]:.4f}')
print(f'  набор + день + зона:     E {p2[1]:.1f}, O/E {p2[0]/p2[1]:.1f}, p {p2[5]:.4f}')
print(f'  + блок часа:             E {p3[1]:.1f}, O/E {p3[0]/p3[1]:.1f}, p {p3[5]:.4f}')
print(f'  дата регистрации:        E {dt[1]:.1f}, O/E {dt[0]/dt[1]:.1f}, p {dt[5]:.4f}; с усреднением по раздачам дат E {mm:.1f}, O/E {rep_obs/mm:.1f}')
